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

_client_cache: Any = None
_client_initialized: bool = False
_flag_cache: dict[str, bool] = {}


def _is_test_mode() -> bool:
    """Match the pipeline's TEST_MODE semantics without importing it.

    Keeping this local avoids a circular import from the main
    script and lets the writer disable itself under unit tests that
    set ``TEST_MODE=true`` before invoking the module.
    """
    return os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes", "on")


def _sentry_breadcrumb(category: str, message: str, level: str = "info",
                       data: dict | None = None) -> None:
    """Route a breadcrumb through the pipeline's helper when present.

    Falls back to a no-op if the main module has not been loaded (for
    example, when the billing_audit package is imported by the
    backfill script). Prevents the writer from exploding if Sentry is
    not wired up in the current process.
    """
    try:
        from generate_weekly_pdfs import sentry_add_breadcrumb  # type: ignore
    except Exception:
        return
    try:
        sentry_add_breadcrumb(category, message, level=level, data=data or {})
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


def get_flag(key: str, default: bool = False) -> bool:
    """Read a boolean from ``billing_audit.feature_flag``.

    Cached per-process: flags are read once per run. On any failure
    (client unavailable, RPC error, missing row, non-boolean value)
    return ``default`` and log at WARNING.
    """
    if key in _flag_cache:
        return _flag_cache[key]

    client = get_client()
    if client is None:
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
        rows = getattr(res, "data", None) or []
        if rows and isinstance(rows[0], dict) and isinstance(
            rows[0].get("enabled"), bool
        ):
            value = rows[0]["enabled"]
        else:
            value = default
    except Exception as exc:
        logging.warning(
            f"⚠️ billing_audit.feature_flag read failed for {key!r}: "
            f"{type(exc).__name__} — defaulting to {default}"
        )
        _sentry_breadcrumb(
            "billing_audit",
            "Feature flag read failed",
            level="warning",
            data={"flag": key, "error_type": type(exc).__name__},
        )
        value = default

    _flag_cache[key] = value
    return value


def with_retry(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run ``fn`` with exponential backoff on transient errors.

    4 attempts, backoff ``2**attempt + 0.5`` seconds. Retries on:
    - ``postgrest.APIError`` (when importable)
    - ``httpx.HTTPError`` (when importable)
    - Any exception whose class name contains a marker from
      ``_TRANSIENT_ERROR_MARKERS`` (RemoteDisconnected, ConnectionError,
      ConnectionReset, SSLError, SSLEOFError, Timeout).

    Returns ``fn``'s return value on success. On final failure, logs
    a WARNING, emits a Sentry breadcrumb, and returns ``None``.
    """
    max_attempts = 4

    # Best-effort dynamic imports — keep the writer importable when
    # these libraries are absent (e.g. under `pytest` with supabase
    # not installed).
    try:
        from postgrest import APIError as _PGAPIError  # type: ignore
    except Exception:
        _PGAPIError = None  # type: ignore
    try:
        from httpx import HTTPError as _HTTPError  # type: ignore
    except Exception:
        _HTTPError = None  # type: ignore

    last_error_name = "Unknown"
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            err_name = type(exc).__name__
            last_error_name = err_name
            is_transient = False
            if _PGAPIError is not None and isinstance(exc, _PGAPIError):
                is_transient = True
            if _HTTPError is not None and isinstance(exc, _HTTPError):
                is_transient = True
            if any(marker in err_name for marker in _TRANSIENT_ERROR_MARKERS):
                is_transient = True

            if is_transient and attempt < max_attempts - 1:
                backoff = 2 ** attempt + 0.5
                logging.warning(
                    f"⚠️ billing_audit RPC retry "
                    f"{attempt + 1}/{max_attempts} ({err_name}), "
                    f"backoff {backoff:.1f}s"
                )
                time.sleep(backoff)
                continue
            # Non-transient OR last attempt — fall through to failure.
            break

    logging.warning(
        "⚠️ billing_audit RPC failed after "
        f"{max_attempts} attempts ({last_error_name})"
    )
    _sentry_breadcrumb(
        "billing_audit",
        "RPC failed after retries",
        level="warning",
        data={"error_type": last_error_name, "attempts": max_attempts},
    )
    return None
