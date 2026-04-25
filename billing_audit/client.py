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

# ── PostgREST error classification ────────────────────────────────
# PostgREST returns a JSON error body with a ``code`` field, and
# postgrest-py lifts that into ``APIError.code`` — **``str | int``**:
# usually a PostgREST error-code string (``PGRST106``, ``PGRST301``,
# …) or a SQLSTATE, but sometimes an HTTP status-code integer when
# the response body isn't valid JSON and the library falls back to
# ``generate_default_error_message``. The classifier normalizes
# both shapes to ``str`` before prefix / membership checks.
# Some codes indicate a PERMANENT error that no amount of retrying
# will fix (schema not exposed, JWT invalid, malformed query),
# while others (or a missing code on a transient body-parse
# failure) can still be transient.
#
# The pre-fix behaviour treated EVERY ``APIError`` as transient, so
# a misconfigured Supabase (e.g. ``billing_audit`` schema not in the
# project's "Exposed schemas" list → HTTP 406 / ``PGRST106`` on every
# call) burned the full 4-attempt × 8.5s backoff budget per call,
# per op, before each op's circuit breaker tripped. The result was
# ~60-120s of log-spammed retries per session with zero chance of
# success.
_PGRST_PERMANENT_PREFIXES: tuple[str, ...] = (
    "PGRST1",  # parser / schema / content-negotiation errors
    "PGRST2",  # auth errors (JWT invalid/expired, RLS denial)
    "PGRST3",  # miscellaneous permanent (e.g. profile-switching)
)

# PostgreSQL SQLSTATE class prefixes that PostgREST forwards verbatim
# in the JSON error body's ``code`` field when the underlying query
# fails at the database layer (as opposed to PostgREST's own parsing
# / auth layer, which uses PGRST codes). SQLSTATEs are exactly 5
# characters; the classes below cover every condition a malformed
# pipeline query / payload can produce, all of which are PERMANENT
# — retrying will never make a missing column appear or a uniqueness
# constraint relax. The motivating production incident:
#
#   2026-04-25: ``billing_audit.pipeline_run`` was first introduced
#   in writer code on 2026-04-23 but the matching ``CREATE TABLE``
#   was never deployed to Supabase. PostgREST returned
#   ``{"code":"42P01", ...}`` (or ``42703`` for missing columns
#   if a partial table existed). Without this prefix list, ``42703``
#   fell through every check in ``_classify_postgrest_error`` —
#   it doesn't start with PGRST1/2/3 and isn't a stringified HTTP
#   status — and landed in the catch-all transient branch, burning
#   the full 4-attempt backoff budget on every WR group's
#   ``pipeline_run_select`` call before the per-op circuit breaker
#   tripped.
#
# Classes captured here:
#   - ``22`` — Data exception (invalid datetime, division by zero,
#              numeric out of range, invalid text representation).
#   - ``23`` — Integrity constraint violation (unique, FK, NOT NULL,
#              check, exclusion).
#   - ``42`` — Syntax error or access rule violation (undefined
#              column ``42703``, undefined table ``42P01``,
#              undefined function ``42883``, syntax_error
#              ``42601``, insufficient_privilege ``42501``).
#
# Other SQLSTATE classes (``08`` connection failure, ``40``
# transaction rollback, ``53`` insufficient resources, ``57``
# operator intervention, ``XX`` internal error) ARE retryable and
# must NOT be added here — PostgREST surfaces them too, and the
# default-transient path correctly retries them.
_PG_SQLSTATE_PERMANENT_PREFIXES: tuple[str, ...] = (
    "22",
    "23",
    "42",
)

# SQLSTATE codes are exactly 5 ASCII characters per the PostgreSQL
# spec. The length guard prevents a hypothetical PGRST code that
# happens to start with these digits from being misclassified —
# none exist today, but PostgREST is free to mint new codes and the
# guard keeps the SQLSTATE check defensive against future drift.
_PG_SQLSTATE_LENGTH = 5

# HTTP status codes that PostgREST sometimes surfaces as stringified
# values via ``generate_default_error_message`` when the response
# body isn't valid JSON. A 4xx means "client request was rejected"
# — retrying the same request won't make the server change its mind
# — with two documented exceptions that are genuinely retryable:
# ``408 Request Timeout`` (server-side timeout, transient) and
# ``429 Too Many Requests`` (rate limit, transient with backoff).
# Treating the whole 4xx range minus those two as permanent keeps
# the contract honest against any code PostgREST might stringify
# in the future, rather than a hand-maintained subset that silently
# routes novel 4xxs (e.g. 411/413/414/418) into the retry-spam path
# the classifier was introduced to fix.
_HTTP_PERMANENT_CODES: frozenset[str] = frozenset(
    str(status_code)
    for status_code in range(400, 500)
    if status_code not in {408, 429}
)

# PostgREST error codes that indicate the ENTIRE billing_audit
# integration is misconfigured for this run — not a transient /
# per-endpoint issue. The schema-exposure / JWT problems here affect
# every table + RPC in ``billing_audit`` equally, so letting each op
# independently exhaust its per-op circuit breaker is pure waste.
# Detecting these once flips a run-global kill switch that makes
# ``get_client()`` return None for the rest of the run.
_PGRST_GLOBAL_KILL_CODES: frozenset[str] = frozenset({
    "PGRST106",  # Schema not in db-schemas (Supabase "Exposed schemas")
    "PGRST301",  # JWT expired
    "PGRST302",  # Anonymous access forbidden / JWT invalid
})

# Run-global kill switch. Set the first time a ``_PGRST_GLOBAL_KILL_CODES``
# error is observed by ``with_retry``. Once set, ``get_client()``
# short-circuits to ``None`` and the main pipeline's per-row
# ``freeze_row`` / ``emit_run_fingerprint`` calls all silently no-op
# — identical to the "credentials missing" path. Preserves the
# fail-safe contract: a misconfigured billing_audit integration must
# never break the billing pipeline itself.
_global_disable_reason: str | None = None
_global_disable_logged: bool = False


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
    - A run-global PostgREST misconfiguration was detected earlier
      this run (schema not exposed, JWT invalid); see
      ``_PGRST_GLOBAL_KILL_CODES`` and ``with_retry``.
    """
    global _client_cache, _client_initialized

    # Run-global kill switch: a prior call tripped a permanent,
    # integration-wide PostgREST error (e.g. the ``billing_audit``
    # schema is not in Supabase's exposed-schemas list). Every
    # subsequent RPC would hit the same error — short-circuit all
    # downstream callers to the same "client unavailable" path that
    # missing credentials and TEST_MODE already use. No log spam
    # (the disable WARNING was already emitted once by
    # ``_disable_for_run``).
    if _global_disable_reason is not None:
        return None

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
    global _global_disable_reason, _global_disable_logged
    _client_cache = None
    _client_initialized = False
    _flag_cache = {}
    _consecutive_failures.clear()
    _open_circuits.clear()
    _global_disable_reason = None
    _global_disable_logged = False


def _classify_postgrest_error(
    exc: Exception,
) -> tuple[bool, bool, str | None]:
    """Classify a ``postgrest.APIError`` for retry purposes.

    Returns ``(is_transient, is_global_kill, reason_code)``.

    - ``is_transient`` — True when retrying MIGHT succeed. Network-
      level issues surface as ``httpx.HTTPError`` / name-matched
      exceptions (handled separately in ``with_retry``). For
      ``APIError`` instances, transient cases are:
        * missing / malformed ``code`` (``None`` or empty string,
          after the ``int`` → ``str`` coercion);
        * unknown codes that don't match any ``PGRST`` prefix or
          ``_HTTP_PERMANENT_CODES`` membership;
        * HTTP status codes NOT listed as permanent, which includes
          the retryable 4xx escape hatches (``408`` request
          timeout, ``429`` rate-limit) and all 5xx server errors
          when ``APIError.code`` is populated from the raw HTTP
          status via ``generate_default_error_message``.
    - ``is_global_kill`` — True when the error applies to every
      table + RPC in the ``billing_audit`` schema (schema not
      exposed, auth invalid). Tripping the per-op breaker four
      times doesn't fix a schema-exposure problem.
    - ``reason_code`` — the ``APIError.code`` (stringified, after
      int coercion) for logs / breadcrumbs. ``None`` when the
      exception carries no code at all.

    Called only for already-confirmed APIError instances, so the
    ``getattr`` fallback is defensive — a malformed subclass with
    no ``code`` attribute still classifies cleanly.
    """
    code = getattr(exc, "code", None)

    # Coerce integer codes to string. ``postgrest.exceptions.
    # generate_default_error_message`` (invoked when the HTTP
    # response body isn't valid JSON) populates ``APIError.code``
    # with the raw ``httpx.Response.status_code`` — an ``int``.
    # Without this coercion a non-JSON 406 / 401 / 404 body would
    # fail the ``isinstance(code, str)`` check, fall into the
    # "no code → transient" branch, and burn the full retry
    # budget on an inherently-permanent HTTP rejection — exactly
    # the retry-spam mode this classifier exists to prevent.
    # (Codex P2 2026-04-24.)
    if isinstance(code, int):
        code = str(code)

    if not isinstance(code, str) or not code:
        # No code field — assume transient. This matches the
        # pre-fix behaviour for exotic APIError shapes and keeps
        # unrelated 5xx body-parse blips retryable.
        return True, False, None

    if code in _PGRST_GLOBAL_KILL_CODES:
        return False, True, code

    if code.startswith(_PGRST_PERMANENT_PREFIXES):
        return False, False, code

    # PostgreSQL SQLSTATE — forwarded verbatim by PostgREST when the
    # query fails at the DB layer (undefined column ``42703``,
    # undefined table ``42P01``, unique violation ``23505``, etc.).
    # Length-gated to exactly 5 chars so only true SQLSTATE values
    # match this branch; real PostgREST codes like ``PGRST116``
    # are longer (8 chars for the code, 6 chars for the prefix)
    # and therefore excluded. Order still matters: the PGRST
    # prefix check above runs first so PGRST codes are always
    # classified by their explicit prefix rather than accidentally
    # falling through to this numeric-SQLSTATE branch.
    if (
        len(code) == _PG_SQLSTATE_LENGTH
        and code.startswith(_PG_SQLSTATE_PERMANENT_PREFIXES)
    ):
        return False, False, code

    if code in _HTTP_PERMANENT_CODES:
        return False, False, code

    # Unknown code — default to transient. Better to waste one
    # backoff budget on a novel error than to silently suppress
    # a genuinely-retryable condition.
    return True, False, code


def _disable_for_run(reason_code: str, exc: Exception) -> None:
    """Trip the run-global kill switch.

    Subsequent ``get_client()`` calls return ``None``, which makes
    every downstream writer path (``freeze_row``,
    ``emit_run_fingerprint``, flag probes) silently no-op for the
    rest of the session. The pipeline's Excel generation, upload,
    and hash-history paths are unaffected.

    Idempotent in its user-visible output: the operator-facing
    WARNING fires only on the first trip. Subsequent calls update
    ``_global_disable_reason`` without re-emitting the log line.
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
            "The 'billing_audit' schema is not exposed by PostgREST. "
            "In Supabase: Project Settings → API → Data API Settings "
            "→ 'Exposed schemas': add 'billing_audit', save, and "
            "reload the schema cache. The billing pipeline itself "
            "continues unaffected."
        )
    elif reason_code in ("PGRST301", "PGRST302"):
        operator_hint = (
            "Supabase authentication rejected the service-role key. "
            "Verify SUPABASE_SERVICE_ROLE_KEY is current (check for "
            "rotation) and that the key grants access to the "
            "'billing_audit' schema. The billing pipeline itself "
            "continues unaffected."
        )
    else:  # Defensive — only codes in _PGRST_GLOBAL_KILL_CODES reach here.
        operator_hint = (
            f"billing_audit returned permanent error {reason_code}; "
            "integration disabled for this run."
        )

    # Keep the message sanitized — server response bodies can quote
    # identifiers, but for PGRST106/301/302 they only quote schema /
    # role names, which are operational context (not row PII).
    logging.warning(
        f"🔌 billing_audit disabled for this run "
        f"(code={reason_code}). {operator_hint} "
        f"Server message: {message.strip()!r}. "
        f"Server hint: {hint.strip()!r}."
    )
    _sentry_breadcrumb(
        "billing_audit",
        "Integration globally disabled",
        level="warning",
        data={
            "reason_code": reason_code,
            "server_message": message,
            "server_hint": hint,
        },
    )


def is_flag_resolved(key: str) -> bool:
    """Return True iff ``key``'s state has been read DEFINITIVELY
    from Supabase this run (either a successful value or a
    confirmed missing-row default — both cache).

    ``get_flag`` caches only on success, so an entry in
    ``_flag_cache`` means the flag's boolean state is trustworthy.
    Absence means either the key hasn't been read yet, or the last
    read exhausted retries and returned the fallback default.

    Callers use this to distinguish a genuine ``False`` flag from a
    ``False`` that's really a transient-failure fallback — important
    for fail-open logic where "unknown" should not be treated the
    same as "known-off" (e.g., to avoid silently dropping writes
    when a flag-read blip during a group causes the whole group's
    first-write-wins attribution window to be missed).
    """
    return key in _flag_cache


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
        # Client unavailable. Do NOT cache here — that would make
        # ``is_flag_resolved(key)`` return True and contradict its
        # contract ("key's state has been read DEFINITIVELY from
        # Supabase"). ``get_client()`` is already memoized via
        # ``_client_cache`` + ``_client_initialized``, so the hot
        # path doesn't re-enter client creation on every call.
        # Callers that need "client unavailable" semantics check
        # ``get_client() is None`` directly (as ``any_flag_enabled``
        # does).
        return default

    # Wrap the SELECT in with_retry so transient network blips get
    # the same bounded retry behaviour as RPC writers. Uses a
    # dedicated ``op="feature_flag"`` so the flag read's circuit
    # breaker is independent of the writer paths — a flag-read
    # outage must not trip the freeze_attribution or pipeline_run
    # breakers, and vice versa.
    def _fetch_flag():
        return (
            client.schema("billing_audit")
            .table("feature_flag")
            .select("enabled")
            .eq("flag_key", key)
            .limit(1)
            .execute()
        )

    res = with_retry(_fetch_flag, op="feature_flag")
    if res is None:
        # with_retry already logged the failure and emitted a
        # breadcrumb. Do NOT cache the default — a subsequent call
        # this run can retry (subject to the feature_flag breaker).
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
    identifier matching the endpoint being called. Current values
    in use:

    - ``"freeze_attribution"`` — the ``freeze_attribution`` RPC
    - ``"pipeline_run_select"`` — the ``pipeline_run`` SELECT for
      prior-fingerprint lookup
    - ``"pipeline_run_upsert"`` — the ``pipeline_run`` UPSERT for
      the new fingerprint row
    - ``"feature_flag"`` — the ``feature_flag`` SELECT for flag
      reads

    The SELECT and UPSERT sides of ``pipeline_run`` MUST stay on
    separate ops: sharing one op would let a healthy SELECT reset
    the breaker counter on every call, masking a sustained UPSERT
    outage from ever tripping the breaker. In general, any endpoint
    whose health can diverge from a neighbor's should get its own
    op. The default ``"default"`` exists only so non-writer callers
    need not adopt the convention.

    Returns ``fn``'s return value on success. On final failure, logs
    a WARNING, emits a Sentry breadcrumb, and returns ``None``.
    """
    # Run-global kill switch check: a prior op detected a
    # schema-exposure / auth misconfiguration. All subsequent calls
    # to any op short-circuit. ``get_client()`` already short-
    # circuits at the writer layer, but a caller that captured the
    # client reference before the kill switch tripped could still
    # reach here — this guard is the belt to the ``get_client``
    # suspenders.
    if _global_disable_reason is not None:
        return None

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
                # Classify by the PostgREST error code. Permanent
                # PGRST1xx / PGRST2xx / PGRST3xx codes and HTTP
                # 4xx codes bail after the first attempt — no
                # retry will fix a schema-not-exposed or auth
                # rejection. Run-global kill codes also trip the
                # module-wide kill switch so every other op
                # short-circuits to ``None`` without making the
                # doomed round trip.
                is_transient, is_global_kill, reason_code = (
                    _classify_postgrest_error(exc)
                )
                if is_global_kill:
                    _disable_for_run(reason_code or "UNKNOWN", exc)
                    # Global kill replaces ALL per-op bookkeeping for
                    # this call: skip the per-op circuit breaker
                    # counter, skip the generic "RPC failed after N
                    # attempt(s)" WARNING, skip the generic Sentry
                    # breadcrumb. The operator-facing WARNING from
                    # ``_disable_for_run`` is the single source of
                    # truth for this run, matching the "exactly one
                    # WARNING per run" contract in the PR description.
                    # Incrementing the per-op counter here would also
                    # race ahead of the breaker threshold (threshold
                    # = 3 but the integration is already disabled),
                    # producing a misleading "circuit breaker OPEN
                    # after 1 consecutive immediate failures" line
                    # that contradicts the disable message.
                    return None
            elif _HTTPError is not None and isinstance(exc, _HTTPError):
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
                # Re-check kill switch + circuit breaker BEFORE the
                # next attempt. The 2026-04-25 parallelization of
                # ``freeze_row`` in the main pipeline can put up to
                # ``PARALLEL_WORKERS`` (8 by default) concurrent
                # callers into ``with_retry`` for the same op
                # simultaneously. Without this re-check, an outage
                # on Supabase would let every in-flight worker
                # exhaust all 4 attempts even after another worker
                # tripped the breaker — recreating the per-op retry
                # storm (8 workers × 4 attempts = 32 doomed RPCs)
                # the breaker exists to bound. Checking AFTER the
                # backoff sleep (where the cross-thread state has
                # had time to update) ensures every worker observes
                # the breaker trip from any neighbor.
                if _global_disable_reason is not None:
                    return None
                if op in _open_circuits:
                    logging.warning(
                        f"⚠️ billing_audit[{op}] aborting retries: "
                        "circuit breaker opened by a concurrent "
                        f"worker mid-attempt (after {attempt + 1}/"
                        f"{max_attempts})"
                    )
                    return None
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
