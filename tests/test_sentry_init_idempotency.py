"""Phase 09 Wave 1 (Task 3): regression guard for the relocated, idempotent
import-time Sentry initializer (D-04).

``pipeline.observability.init_sentry()`` wraps the module-scope Sentry init
block that previously ran as bare ``if SENTRY_DSN:`` code in
``generate_weekly_pdfs.py``. The facade body calls it exactly once at import
(preserving the original import-time Sentry trigger); a second call must be a
no-op. The module-level ``_SENTRY_INITIALIZED`` flag makes double-init
structurally impossible.

These tests force ``SENTRY_DSN`` empty so ``init_sentry()`` takes the
no-DSN (else) branch and never performs a real ``sentry_sdk.init`` against the
global SDK state, then assert the flag transitions and the operator-visible
logger name (Pitfall 4: the logger must stay ``generate_weekly_pdfs``, not
``pipeline.observability``).
"""
import os
from unittest import mock

import pipeline.observability as obs


def test_init_sentry_is_idempotent_and_sets_operator_logger():
    """Flag flips False -> True on first call; second call is a no-op; the
    module logger binds under the operator-visible name."""
    saved_flag = obs._SENTRY_INITIALIZED
    saved_logger = obs.logger
    try:
        with mock.patch.object(obs, "SENTRY_DSN", ""):
            obs._SENTRY_INITIALIZED = False
            obs.logger = None

            assert obs._SENTRY_INITIALIZED is False
            obs.init_sentry()
            assert obs._SENTRY_INITIALIZED is True
            assert obs.logger is not None
            assert obs.logger.name == "generate_weekly_pdfs"

            # Second call must short-circuit on the flag and never re-init.
            with mock.patch.object(obs.sentry_sdk, "init") as m_init:
                obs.init_sentry()
                m_init.assert_not_called()
            assert obs._SENTRY_INITIALIZED is True
    finally:
        obs._SENTRY_INITIALIZED = saved_flag
        obs.logger = saved_logger


def test_before_send_log_sanitizer_is_wired_and_importable():
    """The PII backstop ``sentry_before_send_log`` survives the relocation,
    is importable from observability, and still drops a known PII marker."""
    assert callable(obs.sentry_before_send_log)
    marker = obs._PII_LOG_MARKERS[0]
    assert obs.sentry_before_send_log({"body": f"{marker} leak"}, None) is None
    assert obs.sentry_before_send_log({"body": "benign run summary"}, None) == {
        "body": "benign run summary"
    }


def test_facade_import_triggers_import_time_init():
    """D-04: importing the facade runs init_sentry() once at import time, and
    the facade re-exports the observability surface consistently."""
    import generate_weekly_pdfs as gwp  # noqa: F401  (import already ran)

    assert obs._SENTRY_INITIALIZED is True
    assert gwp.SENTRY_DSN == obs.SENTRY_DSN
    assert gwp.sentry_before_send_log is obs.sentry_before_send_log
