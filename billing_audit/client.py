"""Thin Supabase client wrapper for the billing_audit writer.

Defensive, additive, and safe to import even when Supabase is not
installed or not configured. Mirrors the connection-error
name-matching pattern used by the Smartsheet retry helpers in
``generate_weekly_pdfs.py`` so transient network blips during a
production run do not break Excel generation.
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

# One-time best-effort imports of the external exception types we
# want to treat as transient. Kept at module scope so ``with_retry``
# (called per-row) doesn't repeat the try/except import dance on
# every invocation. Missing libraries resolve to ``None`` and are
# skipped by the ``isinstance`` check inside the retry loop.
try:
    from postgrest import APIError as _PGAPIError  # type: ignore
except Exception:
    _PGAPIError = None  # type: ignore[assignment]
try:
    from httpx import HTTPError as _HTTPError  # type: ignore
except Exception:
    _HTTPError = None  # type: ignore[assignment]

_client_cache: Any = None
_client_initialized: bool = False
_flag_cache: dict[str, bool] = {}

# Circuit breaker state. When a run is operating against an
# unavailable Supabase (extended outage, DNS failure, expired key),
# every ``with_retry`` call would otherwise burn the full
# 1.5s + 2.5s + 4.5s = 8.5s backoff budget (4 attempts with
# ``2**attempt + 0.5`` seconds between them; the 4th attempt has no
# following sleep). With ~550 rows per run, that's ~78 minutes of
# pure backoff on a dead endpoint. After
# ``_CIRCUIT_BREAKER_THRESHOLD`` consecutive exhausted retries the
# breaker trips and every subsequent call fast-fails with no
# retries — bounded per-run cost ≈ THRESHOLD × 8.5s plus fast-fail
# no-ops for the rest of the run.
#
# State is tracked PER OPERATION (per ``op`` argument to
# ``with_retry``). An outage on one endpoint (e.g.
# ``pipeline_run`` upsert) must not cascade into disabling
# independent endpoints (``freeze_attribution`` RPC, feature_flag
# read) that are still healthy — otherwise a localized fingerprint
# issue turns into broad attribution-snapshot data loss.
_CIRCUIT_BREAKER_THRESHOLD = 3
_consecutive_failures: dict[str, int] = {}
_open_circuits: set[str] = set()


def _is_test_mode() -> bool:
    """Match the pipeline's TEST_MODE semantics without importing it.

    Keeping this local avoids a circular import from the main
    script and lets the writer disable itself under unit tests that
    set ``TEST_MODE=true`` before invoking the module.
    """
    return os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes", "on")


def _sentry_breadcrumb(category: str, message: str, level: str = "info",
                       data: dict | None = None) -> None:
    """Emit a Sentry breadcrumb without self-importing the pipeline.

    Calls ``sentry_sdk.add_breadcrumb`` directly. The pipeline runs
    as ``python generate_weekly_pdfs.py`` so its running module is
    ``__main__`` — ``from generate_weekly_pdfs import
    sentry_add_breadcrumb`` would load a SECOND copy of the script
    during error handling, re-executing module-level Sentry init and
    duplicating telemetry state exactly when Supabase errors occur.
    ``sentry_sdk`` itself is a no-op when the SDK has not been
    initialized, so this is safe even in the backfill script path.
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
    - ``TEST_MODE`` is enabled.
    - ``SUPABASE_URL`` or ``SUPABASE_SERVICE_ROLE_KEY`` is missing.
    - The ``supabase`` package is not installed.
    - Client construction raises.
    """
    global _client_cache, _client_initialized

    if _client_initialized:
        return _client_cache

    _client_initialized = True

    if _is_test_mode():
        logging.info(
            "ℹ️ Supabase credentials not configured (or TEST_MODE) — "
            "attribution snapshot disabled"
        )
        _client_cache = None
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logging.info(
            "ℹ️ Supabase credentials not configured (or TEST_MODE) — "
            "attribution snapshot disabled"
        )
        _client_cache = None
        return None

    try:
        from supabase import create_client  # type: ignore
    except Exception as exc:
        logging.info(
            "ℹ️ Supabase credentials not configured (or TEST_MODE) — "
            f"attribution snapshot disabled ({type(exc).__name__})"
        )
        _client_cache = None
        return None

    try:
        _client_cache = create_client(url, key)
    except Exception as exc:
        logging.warning(
            "⚠️ Supabase client init failed; attribution snapshot "
            f"disabled ({type(exc).__name__})"
        )
        _sentry_breadcrumb(
            "billing_audit",
            "Supabase client init failed",
            level="warning",
            data={"error_type": type(exc).__name__},
        )
        _client_cache = None

    return _client_cache


def reset_cache_for_tests() -> None:
    """Clear module-level caches. Test-only helper."""
    global _client_cache, _client_initialized, _flag_cache
    _client_cache = None
    _client_initialized = False
    _flag_cache = {}
    _consecutive_failures.clear()
    _open_circuits.clear()


def get_flag(key: str, default: bool = False) -> bool:
    """Read a boolean from ``billing_audit.feature_flag``.

    Cached per-process on successful reads only. Missing rows cache
    as ``default`` (authoritative DB state). On transport / RPC
    failures the result is NOT cached, so subsequent calls in the
    same run retry the read instead of disabling the feature for
    the remainder of the process on a single transient error.
    """
    if key in _flag_cache:
        return _flag_cache[key]

    client = get_client()
    if client is None:
        # Client unavailable is a stable disabled state; cache it so
        # the hot path doesn't re-enter get_client() on every call.
        _flag_cache[key] = default
        return default

    try:
        res = (
            client.schema("billing_audit")
            .table("feature_flag")
            .select("enabled")
            .eq("flag_key", key)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logging.warning(
            f"⚠️ billing_audit.feature_flag read failed for {key!r}: "
            f"{type(exc).__name__} — returning {default} without "
            "caching (will retry on next call)"
        )
        _sentry_breadcrumb(
            "billing_audit",
            "Feature flag read failed",
            level="warning",
            data={"flag": key, "error_type": type(exc).__name__},
        )
        # Do NOT cache on transport failure — let the next call
        # retry. A single early-run blip would otherwise disable
        # the feature for the whole process.
        return default

    rows = getattr(res, "data", None) or []
    if rows and isinstance(rows[0], dict) and isinstance(
        rows[0].get("enabled"), bool
    ):
        value = rows[0]["enabled"]
    else:
        value = default
    _flag_cache[key] = value
    return value


def with_retry(fn: Callable[..., Any], *args: Any,
               op: str = "default", **kwargs: Any) -> Any:
    """Run ``fn`` with exponential backoff on transient errors.

    4 attempts, backoff ``2**attempt + 0.5`` seconds. Retries on:
    - ``postgrest.APIError`` (when importable)
    - ``httpx.HTTPError`` (when importable)
    - Any exception whose class name contains a marker from
      ``_TRANSIENT_ERROR_MARKERS`` (RemoteDisconnected, ConnectionError,
      ConnectionReset, SSLError, SSLEOFError, Timeout).

    A circuit breaker is tracked PER ``op`` — an outage on one
    endpoint must not cascade into disabling healthy ones. The
    breaker for a given op trips after
    ``_CIRCUIT_BREAKER_THRESHOLD`` consecutive call failures,
    counting BOTH transient retry exhaustions AND non-transient
    single-attempt failures. This is intentional: a run that keeps
    hitting a malformed RPC payload or auth error is just as
    wasteful to keep attempting as one hitting a dead endpoint, and
    operators want the same fast-fail protection in both cases.
    Once open the breaker stays open for the remainder of the run
    and every subsequent call for that op returns ``None``
    immediately. A single successful call resets that op's failure
    counter (but not an open breaker — the breaker is per-run by
    design so we don't oscillate).

    Callers in ``billing_audit.writer`` should pass a stable ``op``
    identifier (e.g. ``"freeze_attribution"``, ``"pipeline_run"``,
    ``"feature_flag"``). The default ``"default"`` exists only so
    non-writer callers need not adopt the convention.

    Returns ``fn``'s return value on success. On final failure, logs
    a WARNING, emits a Sentry breadcrumb, and returns ``None``.
    """
    if op in _open_circuits:
        # Fast path: breaker is open for THIS op; skip all RPC
        # work. Other ops are unaffected.
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
                is_transient = True
            if _HTTPError is not None and isinstance(exc, _HTTPError):
                is_transient = True
            if any(marker in err_name for marker in _TRANSIENT_ERROR_MARKERS):
                is_transient = True
            final_was_transient = is_transient

            if is_transient and attempt < max_attempts - 1:
                backoff = 2 ** attempt + 0.5
                logging.warning(
                    f"⚠️ billing_audit[{op}] RPC retry "
                    f"{attempt + 1}/{max_attempts} ({err_name}), "
                    f"backoff {backoff:.1f}s"
                )
                time.sleep(backoff)
                continue
            # Non-transient OR last attempt — fall through to failure.
            break
        else:
            _consecutive_failures[op] = 0
            return result

    # Increment this op's consecutive-failure counter.
    new_count = _consecutive_failures.get(op, 0) + 1
    _consecutive_failures[op] = new_count

    # Word the trip message correctly for both modes — "exhausted
    # retries" only applies to transient failures; non-transient
    # failures bail on the first attempt by design.
    trip_label = (
        "exhausted retries" if final_was_transient else "immediate failures"
    )
    if new_count >= _CIRCUIT_BREAKER_THRESHOLD and op not in _open_circuits:
        _open_circuits.add(op)
        logging.warning(
            f"🔌 billing_audit[{op}] circuit breaker OPEN after "
            f"{new_count} consecutive {trip_label}; "
            f"remaining {op!r} RPC calls this run will fast-fail. "
            "Other billing_audit operations remain unaffected."
        )
        _sentry_breadcrumb(
            "billing_audit",
            "Circuit breaker opened",
            level="warning",
            data={
                "op": op,
                "consecutive_failures": new_count,
                "threshold": _CIRCUIT_BREAKER_THRESHOLD,
                "last_trip_mode": trip_label,
            },
        )

    # ``attempts_made`` reflects how many times ``fn`` actually ran
    # — 1 for a non-transient failure, up to ``max_attempts`` for a
    # transient-retry exhaustion. Misreporting this to operators
    # made Supabase-outage postmortems harder than they needed to be.
    logging.warning(
        f"⚠️ billing_audit[{op}] RPC failed after "
        f"{attempts_made}/{max_attempts} attempt(s) ({last_error_name})"
    )
    _sentry_breadcrumb(
        "billing_audit",
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
