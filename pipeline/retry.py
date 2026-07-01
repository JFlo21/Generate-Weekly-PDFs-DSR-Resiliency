"""pipeline.retry — centralized transient-failure retry for Smartsheet calls.

Phase 10: a single source of truth for the retry-with-backoff logic that was
previously duplicated three times inside ``pipeline.orchestrate.main`` (target
+ PPP attachment pre-fetch, and Excel upload) and entirely ABSENT on the hot
discovery / per-sheet fetch path (``pipeline.discovery`` /
``pipeline.fetch``) — the path that drops a whole source sheet (and its
billing rows) on the first transient blip.

Design contract
---------------
* Retry ONLY the transient failures the Smartsheet SDK does not itself drive
  to success:
    - generic ``ApiError`` with ``error.result.code == 4000`` ("An unexpected
      error has occurred. Please retry.") — matched by RESULT CODE via
      ``_RETRYABLE_API_CODES``, NOT by exception type: the SDK maps no
      ``should_retry`` typed exception to 4000, so it never retries it. This
      is the real gap-filler on the oversized-response discovery / per-sheet
      fetch path.
    - ``InternalServerError`` — a raw HTTP 500, retried transitively as an
      ``HttpError`` subclass via ``_TRANSIENT_EXC`` (it carries no
      ``should_retry`` flag). This is a DISTINCT failure from API code 4000;
      the two share no code path (and 500 is rare — the SDK 3.9.0
      ``InternalServerError`` constructor is broken, so a raw 500 usually
      surfaces as its ``HttpError`` base anyway).
    - ``ServerTimeoutExceededError`` / ``UnexpectedErrorShouldRetryError`` —
      the SDK retries these inside its own ~15s window; we add a bounded
      secondary backoff for the case where that window is exhausted.
    - ``RateLimitExceededError`` — back off long (15/30/45s) rather than
      hammer; backing off is the correct response to a 429.
    - transport-layer drops: the SDK's ``_request`` WRAPS every
      ``requests.RequestException`` (connection reset / read timeout) as
      ``UnexpectedRequestError`` and a ``requests.SSLError`` as a bare
      ``HttpError`` — so we retry those TYPES. (Matching by class name alone
      misses them, since neither name contains a network tag; the name-based
      ``is_transient_network_error`` remains only as a fallback for a raw
      requests/urllib3/ssl error that escapes the SDK's wrapping.)
* NEVER retry a non-transient error (e.g. a programming ``ValueError``): it is
  re-raised immediately so real bugs surface fast.
* Total sleep across all attempts is bounded by ``max_total_sleep`` so a
  single stuck call can never consume the attachment-prefetch sub-budget or
  the session ``TIME_BUDGET_MINUTES`` — the failure mode behind the
  2026-04-22 prefetch stall (see ``pipeline.config`` budget knobs).
* On exhaustion the last exception is re-raised. Callers decide the policy:
  the attachment paths degrade (``return (row_id, [])``); discovery escalates
  to a SANITIZED Sentry capture (frame locals stripped) so a dropped source
  sheet is loud — without exfiltrating sampled row PII.

This module imports only the stdlib and ``smartsheet.exceptions`` — no
``pipeline`` siblings — so it is safe to import anywhere with zero risk of an
import cycle.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import smartsheet.exceptions as ss_exc

__all__ = ["smartsheet_call_with_retry", "is_transient_network_error"]

# Typed exceptions that get an exponential backoff. Two groups:
#   (1) Smartsheet API codes the SDK marks should_retry=True — it retries them
#       inside its own ~15s window; we add a bounded secondary backoff.
#   (2) The SDK's transport-layer wrappers. This is the load-bearing fix: real
#       connection/timeout drops reach app code as ``UnexpectedRequestError``
#       (the SDK's ``_request`` wraps ``requests.RequestException``), and an SSL
#       handshake failure as a bare ``HttpError``. Matching by TYPE catches the
#       failures that the old class-name list silently missed. ``HttpError``
#       also covers ``InternalServerError`` (HTTP 500, an ``HttpError`` subclass
#       whose own constructor is broken in SDK 3.9.0, so it is rarely raised).
_TRANSIENT_EXC: tuple[type[BaseException], ...] = (
    ss_exc.UnexpectedErrorShouldRetryError,  # API 4004
    ss_exc.ServerTimeoutExceededError,       # API 4002
    ss_exc.SystemMaintenanceError,           # API 4001
    ss_exc.UnexpectedRequestError,           # SDK wrapper: requests.RequestException
    ss_exc.HttpError,                        # SDK wrapper: SSLError; base of 500
)

# Generic ``ApiError`` *result codes* that are transient but which the SDK
# does NOT map to a ``should_retry`` typed exception, so it never retries
# them. 4000 ("An unexpected error has occurred. Please retry.") is the
# oversized-/failed-response error that hammers the discovery + per-sheet
# fetch path for large sheets (see ``pipeline.discovery`` line ~416). Any
# OTHER code (1006 not-found, 1002 auth, …) is permanent and re-raised at
# once — retrying it would only burn the time budget.
_RETRYABLE_API_CODES: frozenset[int] = frozenset({4000})

# Fallback only: class-name substring match for a RAW requests/urllib3/ssl
# error that somehow escapes the SDK's wrapping (normally these arrive as the
# types in _TRANSIENT_EXC above). Defense in depth; mirrors the inline list
# the orchestrate retry blocks used pre-consolidation.
_TRANSIENT_NETWORK_TAGS: tuple[str, ...] = (
    "RemoteDisconnected",
    "ConnectionError",
    "ConnectionReset",
    "SSLError",
    "SSLEOFError",
    "Timeout",
)


def is_transient_network_error(exc: BaseException) -> bool:
    """Return True if ``exc`` looks like a transient network drop.

    Matched by class-name substring so the concrete requests/urllib3/ssl
    exception types do not all have to be imported here.
    """
    name = type(exc).__name__
    return any(tag in name for tag in _TRANSIENT_NETWORK_TAGS)


def _api_error_code(exc: BaseException) -> int | None:
    """Best-effort extraction of a Smartsheet ``ApiError`` result code.

    Returns the integer code (e.g. 4000) or None when the error carries no
    parseable ``error.result.code`` — in which case it is treated as
    non-retryable.
    """
    try:
        return exc.error.result.code  # type: ignore[attr-defined]
    except AttributeError:
        return None


def smartsheet_call_with_retry(
    func: Callable[..., Any],
    *args: Any,
    label: str = "Smartsheet call",
    max_attempts: int = 4,
    max_total_sleep: float = 90.0,
    **kwargs: Any,
) -> Any:
    """Call ``func(*args, **kwargs)``, retrying transient Smartsheet failures.

    Args:
        func: The Smartsheet SDK method (or any callable) to invoke.
        *args / **kwargs: Forwarded to ``func`` unchanged.
        label: Human-readable tag for the retry log lines.
        max_attempts: Total attempts (initial call + retries).
        max_total_sleep: Hard ceiling (seconds) on cumulative backoff across
            all retries. The next backoff that would breach it ends the loop.

    Returns:
        Whatever ``func`` returns on the first successful attempt.

    Raises:
        The last transient exception once ``max_attempts`` or
        ``max_total_sleep`` is exhausted, or any non-transient exception
        immediately (never retried).
    """
    slept = 0.0
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except ss_exc.RateLimitExceededError as exc:
            last_exc = exc
            backoff = 15.0 * attempt  # 15s, 30s, 45s — do not hammer a 429.
            kind = "rate limit"
        except _TRANSIENT_EXC as exc:
            last_exc = exc
            backoff = float(2 ** (attempt - 1)) + 0.5  # 1.5, 2.5, 4.5, ...
            kind = type(exc).__name__
        except ss_exc.ApiError as exc:
            # Generic API error: retry ONLY the transient codes (4000); any
            # other code is permanent and must surface immediately.
            code = _api_error_code(exc)
            if code not in _RETRYABLE_API_CODES:
                raise
            last_exc = exc
            backoff = float(2 ** (attempt - 1)) + 0.5
            kind = f"ApiError {code}"
        except Exception as exc:  # noqa: BLE001 — narrowed by the guard below.
            if not is_transient_network_error(exc):
                raise  # Non-transient (e.g. a real bug) — surface immediately.
            last_exc = exc
            backoff = float(2 ** (attempt - 1)) + 0.5
            kind = type(exc).__name__

        # We only reach here via one of the except branches above, each of
        # which sets last_exc/backoff/kind. The assert narrows last_exc from
        # Optional for mypy and documents that invariant.
        assert last_exc is not None
        # A transient failure was caught. Stop if out of attempts or budget.
        if attempt >= max_attempts or slept + backoff > max_total_sleep:
            logging.warning(
                "⚠️ %s: giving up after %d attempt(s) (%s)",
                label,
                attempt,
                kind,
            )
            raise last_exc
        logging.warning(
            "⚠️ %s: %s on attempt %d/%d — retrying in %.1fs",
            label,
            kind,
            attempt,
            max_attempts,
            backoff,
        )
        time.sleep(backoff)
        slept += backoff

    # Unreachable: the loop always returns a value or raises above. The
    # explicit narrowing keeps mypy happy (a ternary in the raise does not
    # narrow ``last_exc`` away from ``None``).
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{label}: retry loop exited without returning")
