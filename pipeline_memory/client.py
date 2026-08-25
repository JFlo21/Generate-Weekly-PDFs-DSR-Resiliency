"""Thin Supabase client wrapper for the pipeline_memory writer.

Defensive, additive, and safe to import even when Supabase is not
installed or not configured. Mirrors ``billing_audit/client.py``'s
retry / PostgREST-error-classification PATTERN, but every piece of
module-level STATE here (client cache, kill switch, circuit breaker)
is its own, independent instance.

This independence is deliberate (10-RESEARCH.md Pitfall 5, CRITICAL):
``billing_audit.client``'s run-global kill switch is schema-agnostic
-- tripping it (e.g. a ``pipeline_memory``-only PGRST106 because the
new schema is not yet in Supabase's Exposed Schemas list) would
silently disable the unrelated, already-shipped ``freeze_row`` /
``emit_run_fingerprint`` writes for the rest of the run. This module
therefore imports NOTHING from ``billing_audit`` -- not the client
module, not its cache, not its kill switch. A misconfiguration here
must be able to disable ONLY ``pipeline_memory`` writes, never the
sibling package's.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

_TRANSIENT_ERROR_MARKERS: tuple[str, ...] = (
    "RemoteDisconnected",
    "ConnectionError",
    "ConnectionReset",
    "SSLError",
    "SSLEOFError",
    "Timeout",
)

# One-time best-effort imports of the external exception types we want to
# treat as transient. Kept at module scope so ``with_retry`` (called per
# sheet) doesn't repeat the try/except import dance on every invocation.
# Missing libraries resolve to ``None`` and are skipped by the
# ``isinstance`` check inside the retry loop.
try:
    from postgrest import APIError as _PGAPIError  # type: ignore
except Exception:
    # Bare ``type: ignore`` (not ``[assignment]``): mypy reports this
    # None-reassignment as ``[misc]`` ("Cannot assign to a type"), not
    # ``[assignment]`` -- billing_audit/client.py's identical pattern
    # uses the narrower code and is accepted mypy debt (frozen in
    # tests/golden/mypy_baseline.txt). New code should not reproduce
    # that debt.
    _PGAPIError = None  # type: ignore
try:
    from httpx import HTTPError as _HTTPError  # type: ignore
except Exception:
    _HTTPError = None  # type: ignore

# ── Independent module-level state (pipeline_memory's OWN, never shared
# with billing_audit.client) ────────────────────────────────────────────
_client_cache: Any = None
_client_initialized: bool = False

# Circuit breaker state, tracked PER OPERATION -- an outage on one
# pipeline_memory endpoint (e.g. ``run_ledger_upsert``) must not cascade
# into disabling an independent one (a future ``upsert_rows_bulk`` /
# ``upsert_sheet_registry`` / ``upsert_group_state`` op).
_CIRCUIT_BREAKER_THRESHOLD = 3
_consecutive_failures: dict[str, int] = {}
_open_circuits: set[str] = set()

# ── PostgREST error classification (pattern copied from
# billing_audit/client.py; see that module's extensive comments for the
# 2026-04-25 retry-storm incident this classifier exists to prevent) ────
_PGRST_PERMANENT_PREFIXES: tuple[str, ...] = (
    "PGRST1",  # parser / schema / content-negotiation errors
    "PGRST2",  # auth errors (JWT invalid/expired, RLS denial)
    "PGRST3",  # miscellaneous permanent (e.g. profile-switching)
)

_PG_SQLSTATE_PERMANENT_PREFIXES: tuple[str, ...] = (
    "22",  # Data exception
    "23",  # Integrity constraint violation
    "42",  # Syntax error or access rule violation
)

_PG_SQLSTATE_LENGTH = 5

_HTTP_PERMANENT_CODES: frozenset[str] = frozenset(
    str(status_code)
    for status_code in range(400, 500)
    if status_code not in {408, 429}
)

# PostgREST error codes that indicate the ENTIRE pipeline_memory
# integration is misconfigured for this run -- not a transient /
# per-endpoint issue. Detecting one flips THIS module's run-global kill
# switch only; it never touches billing_audit's.
_PGRST_GLOBAL_KILL_CODES: frozenset[str] = frozenset({
    "PGRST106",  # Schema not in db-schemas (Supabase "Exposed schemas")
    "PGRST301",  # JWT expired
    "PGRST302",  # Anonymous access forbidden / JWT invalid
})

# Run-global kill switch, independent of billing_audit's. Once set,
# get_client() short-circuits to None for the rest of the run and every
# subsequent pipeline_memory write silently no-ops.
_global_disable_reason: str | None = None
_global_disable_logged: bool = False


def _is_test_mode() -> bool:
    """Match the pipeline's TEST_MODE semantics without importing it.

    Keeping this local avoids a circular import from the main script
    and lets the writer disable itself under unit tests that set
    ``TEST_MODE=true`` before invoking the module.
    """
    return os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes", "on")


def _write_enabled() -> bool:
    """Re-read ``RUN_MEMORY_WRITE_ENABLED`` live from the environment.

    Defence in depth: ``pipeline.config.RUN_MEMORY_WRITE_ENABLED`` is the
    orchestrator's gate (read once at import time); this is the writer's
    OWN gate, re-read on every call. Both read the exact same environment
    variable with the same boolean coercion, and BOTH must be true for a
    write to actually happen -- a direct call into this module (bypassing
    the orchestrator's gate) still cannot write when the env var is off.
    """
    return os.getenv("RUN_MEMORY_WRITE_ENABLED", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _sentry_breadcrumb(category: str, message: str, level: str = "info",
                       data: dict | None = None) -> None:
    """Emit a Sentry breadcrumb without self-importing the pipeline.

    The pipeline runs as ``python generate_weekly_pdfs.py`` so its
    running module is ``__main__`` -- importing the facade here during
    error handling would load a SECOND copy of the script and re-execute
    its module-level Sentry init. ``sentry_sdk`` itself is a no-op when
    the SDK has not been initialized, so this is safe in every context.
    """
    try:
        import sentry_sdk  # type: ignore
    except Exception:
        return
    try:
        sentry_sdk.add_breadcrumb(
            category=category,
            message=message,
            level=level,
            data=data or {},
        )
    except Exception:
        pass


def get_client() -> Any:
    """Return a cached Supabase client, or None if unavailable.

    Returns None (and logs at INFO) when:
    - ``TEST_MODE`` is enabled (checked at construction time, not at each
      call site -- 10-RESEARCH.md Pitfall 7).
    - ``SUPABASE_URL`` or ``SUPABASE_SERVICE_ROLE_KEY`` is missing.
    - The ``supabase`` package is not installed.
    - Client construction raises.
    - A run-global PostgREST misconfiguration was detected earlier this
      run for THIS package (schema not exposed, JWT invalid); see
      ``_PGRST_GLOBAL_KILL_CODES`` and ``with_retry``. This kill switch
      is entirely independent of ``billing_audit.client``'s.
    """
    global _client_cache, _client_initialized

    if _global_disable_reason is not None:
        return None

    if _client_initialized:
        return _client_cache

    _client_initialized = True

    if _is_test_mode():
        logging.info(
            "ℹ️ Supabase credentials not configured (or TEST_MODE) — "
            "pipeline_memory writes disabled"
        )
        _client_cache = None
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logging.info(
            "ℹ️ Supabase credentials not configured (or TEST_MODE) — "
            "pipeline_memory writes disabled"
        )
        _client_cache = None
        return None

    try:
        from supabase import create_client  # type: ignore
    except Exception as exc:
        logging.info(
            "ℹ️ Supabase credentials not configured (or TEST_MODE) — "
            f"pipeline_memory writes disabled ({type(exc).__name__})"
        )
        _client_cache = None
        return None

    try:
        _client_cache = create_client(url, key)
    except Exception as exc:
        logging.warning(
            "⚠️ Supabase client init failed; pipeline_memory writes "
            f"disabled ({type(exc).__name__})"
        )
        _sentry_breadcrumb(
            "pipeline_memory",
            "Supabase client init failed",
            level="warning",
            data={"error_type": type(exc).__name__},
        )
        _client_cache = None

    return _client_cache


def get_disable_reason() -> str | None:
    """Return the run-global disable reason code, or None if not tripped."""
    return _global_disable_reason


def reset_cache_for_tests() -> None:
    """Clear module-level caches. Test-only helper."""
    global _client_cache, _client_initialized
    global _global_disable_reason, _global_disable_logged
    _client_cache = None
    _client_initialized = False
    _consecutive_failures.clear()
    _open_circuits.clear()
    _global_disable_reason = None
    _global_disable_logged = False


def _classify_postgrest_error(
    exc: Exception,
) -> tuple[bool, bool, str | None]:
    """Classify a ``postgrest.APIError`` for retry purposes.

    Returns ``(is_transient, is_global_kill, reason_code)``. See
    ``billing_audit/client.py::_classify_postgrest_error`` for the full
    rationale -- the classification rules are copied verbatim; only the
    schema/log prefix differs.
    """
    code = getattr(exc, "code", None)

    if isinstance(code, int):
        code = str(code)

    if not isinstance(code, str) or not code:
        return True, False, None

    if code in _PGRST_GLOBAL_KILL_CODES:
        return False, True, code

    if code.startswith(_PGRST_PERMANENT_PREFIXES):
        return False, False, code

    if (
        len(code) == _PG_SQLSTATE_LENGTH
        and code.startswith(_PG_SQLSTATE_PERMANENT_PREFIXES)
    ):
        return False, False, code

    if code in _HTTP_PERMANENT_CODES:
        return False, False, code

    return True, False, code


def _disable_for_run(reason_code: str, exc: Exception) -> None:
    """Trip the run-global kill switch for pipeline_memory ONLY.

    Subsequent ``get_client()`` calls return ``None``, which makes every
    downstream ``pipeline_memory.writer`` function silently no-op for the
    rest of the session. This never touches ``billing_audit``'s kill
    switch -- the two schemas' failure states are fully independent
    (10-RESEARCH.md Pitfall 5).

    Idempotent in its user-visible output: the operator-facing WARNING
    fires only on the first trip.
    """
    global _global_disable_reason, _global_disable_logged
    _global_disable_reason = reason_code

    if _global_disable_logged:
        return
    _global_disable_logged = True

    message = getattr(exc, "message", None) or ""
    hint = getattr(exc, "hint", None) or ""

    if reason_code == "PGRST106":
        operator_hint = (
            "The 'pipeline_memory' schema is not exposed by PostgREST. "
            "In Supabase: Project Settings → API → Data API Settings → "
            "'Exposed schemas': add 'pipeline_memory', save, and reload "
            "the schema cache. The billing pipeline itself and the "
            "billing_audit integration continue unaffected."
        )
    elif reason_code in ("PGRST301", "PGRST302"):
        operator_hint = (
            "Supabase authentication rejected the service-role key for "
            "pipeline_memory. Verify SUPABASE_SERVICE_ROLE_KEY is "
            "current and grants access to the 'pipeline_memory' schema. "
            "The billing pipeline itself continues unaffected."
        )
    else:  # Defensive -- only codes in _PGRST_GLOBAL_KILL_CODES reach here.
        operator_hint = (
            f"pipeline_memory returned permanent error {reason_code}; "
            "integration disabled for this run."
        )

    logging.warning(
        f"🔌 pipeline_memory disabled for this run "
        f"(code={reason_code}). {operator_hint} "
        f"Server message: {message.strip()!r}. "
        f"Server hint: {hint.strip()!r}."
    )
    _sentry_breadcrumb(
        "pipeline_memory",
        "Integration globally disabled",
        level="warning",
        data={
            "reason_code": reason_code,
            "server_message": message,
            "server_hint": hint,
        },
    )


def with_retry(fn: Callable[..., Any], *args: Any,
               op: str = "default", **kwargs: Any) -> Any:
    """Run ``fn`` with exponential backoff on transient errors.

    4 attempts, backoff ``2**attempt + 0.5`` seconds. Retries on:
    - ``postgrest.APIError`` (when importable)
    - ``httpx.HTTPError`` (when importable)
    - Any exception whose class name contains a marker from
      ``_TRANSIENT_ERROR_MARKERS``.

    A circuit breaker is tracked PER ``op``. Every ``pipeline_memory``
    table/RPC gets its own distinct ``op`` string so one dead endpoint
    cannot mask another (e.g. ``"run_ledger_upsert"``).

    Returns ``fn``'s return value on success. On final failure, logs a
    WARNING, emits a Sentry breadcrumb, and returns ``None`` -- NEVER
    raises.
    """
    if _global_disable_reason is not None:
        return None

    if op in _open_circuits:
        return None

    max_attempts = 4
    last_error_name = "Unknown"
    attempts_made = 0
    final_was_transient = False
    for attempt in range(max_attempts):
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            attempts_made = attempt + 1
            err_name = type(exc).__name__
            last_error_name = err_name
            is_transient = False
            if _PGAPIError is not None and isinstance(exc, _PGAPIError):
                is_transient, is_global_kill, reason_code = (
                    _classify_postgrest_error(exc)
                )
                if is_global_kill:
                    _disable_for_run(reason_code or "UNKNOWN", exc)
                    return None
            elif _HTTPError is not None and isinstance(exc, _HTTPError):
                is_transient = True
            if any(marker in err_name for marker in _TRANSIENT_ERROR_MARKERS):
                is_transient = True
            final_was_transient = is_transient

            if is_transient and attempt < max_attempts - 1:
                backoff = 2 ** attempt + 0.5
                logging.warning(
                    f"⚠️ pipeline_memory[{op}] RPC retry "
                    f"{attempt + 1}/{max_attempts} ({err_name}), "
                    f"backoff {backoff:.1f}s"
                )
                time.sleep(backoff)
                # Re-check kill switch + circuit breaker BEFORE the next
                # attempt -- mirrors billing_audit.client's concurrent-
                # worker re-check (a future pipeline_memory writer may
                # also parallelize per-sheet calls).
                if _global_disable_reason is not None:
                    return None
                if op in _open_circuits:
                    logging.warning(
                        f"⚠️ pipeline_memory[{op}] aborting retries: "
                        "circuit breaker opened by a concurrent worker "
                        f"mid-attempt (after {attempt + 1}/{max_attempts})"
                    )
                    return None
                continue
            break
        else:
            _consecutive_failures[op] = 0
            return result

    new_count = _consecutive_failures.get(op, 0) + 1
    _consecutive_failures[op] = new_count

    trip_label = (
        "exhausted retries" if final_was_transient else "immediate failures"
    )
    if new_count >= _CIRCUIT_BREAKER_THRESHOLD and op not in _open_circuits:
        _open_circuits.add(op)
        logging.warning(
            f"🔌 pipeline_memory[{op}] circuit breaker OPEN after "
            f"{new_count} consecutive {trip_label}; "
            f"remaining {op!r} RPC calls this run will fast-fail. "
            "Other pipeline_memory operations remain unaffected."
        )
        _sentry_breadcrumb(
            "pipeline_memory",
            "Circuit breaker opened",
            level="warning",
            data={
                "op": op,
                "consecutive_failures": new_count,
                "threshold": _CIRCUIT_BREAKER_THRESHOLD,
                "last_trip_mode": trip_label,
            },
        )

    logging.warning(
        f"⚠️ pipeline_memory[{op}] RPC failed after "
        f"{attempts_made}/{max_attempts} attempt(s) ({last_error_name})"
    )
    _sentry_breadcrumb(
        "pipeline_memory",
        "RPC failed",
        level="warning",
        data={
            "op": op,
            "error_type": last_error_name,
            "attempts": attempts_made,
            "max_attempts": max_attempts,
            "was_transient": final_was_transient,
        },
    )
    return None
