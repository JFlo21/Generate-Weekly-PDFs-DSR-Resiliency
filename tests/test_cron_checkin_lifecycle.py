"""Tests for the Sentry Crons check-in lifecycle guards.

Regression: ``PYTHON-6V`` ("Cron failure: a timeout check-in was detected").
When GitHub Actions cancels a run or hits ``timeout-minutes`` it delivers
SIGTERM; Python's default SIGTERM action kills the process without unwinding
the stack, so the terminal cron check-in in ``main()``'s ``finally`` never
fires and Sentry leaves the ``in_progress`` check-in open until it flags a
timeout. These tests lock in:

1. ``_install_sigterm_finalizer`` converts SIGTERM into ``SystemExit`` so
   the ``finally`` block runs and closes the check-in.
2. ``_resolve_cron_final_status`` reports ERROR for failed / interrupted
   sessions instead of OK (the old logic marked interrupted runs OK).
"""

import os
import signal
from unittest.mock import patch

import pytest

# Import under a patched environment so a developer's real SENTRY_DSN cannot
# trigger import-time Sentry initialization during pytest collection.
with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
    import generate_weekly_pdfs as gwp

from sentry_sdk.crons.consts import MonitorStatus


class TestResolveCronFinalStatus:
    """Terminal check-in status contract."""

    def test_clean_session_is_ok(self):
        status = gwp._resolve_cron_final_status(
            session_failed=False, exc_in_flight=False, groups_errored=0
        )
        assert status == MonitorStatus.OK

    def test_handled_session_failure_is_error(self):
        status = gwp._resolve_cron_final_status(
            session_failed=True, exc_in_flight=False, groups_errored=0
        )
        assert status == MonitorStatus.ERROR

    def test_in_flight_exception_is_error(self):
        # SystemExit from the SIGTERM guard / KeyboardInterrupt propagate
        # through main()'s finally — they must NOT close the monitor as OK.
        status = gwp._resolve_cron_final_status(
            session_failed=False, exc_in_flight=True, groups_errored=0
        )
        assert status == MonitorStatus.ERROR

    def test_errored_groups_is_error(self):
        status = gwp._resolve_cron_final_status(
            session_failed=False, exc_in_flight=False, groups_errored=3
        )
        assert status == MonitorStatus.ERROR

    def test_groups_errored_none_is_ok(self):
        # Early-exit paths where the counter was never assigned pass 0/None.
        status = gwp._resolve_cron_final_status(
            session_failed=False, exc_in_flight=False, groups_errored=None
        )
        assert status == MonitorStatus.OK


class TestSigtermFinalizer:
    """SIGTERM must unwind the stack so finally-based cleanup runs."""

    def test_installs_handler_that_raises_system_exit(self):
        original = signal.getsignal(signal.SIGTERM)
        try:
            gwp._install_sigterm_finalizer()
            handler = signal.getsignal(signal.SIGTERM)
            assert callable(handler)
            assert handler is not original
            with pytest.raises(SystemExit) as excinfo:
                handler(signal.SIGTERM, None)
            assert excinfo.value.code == 128 + signal.SIGTERM
        finally:
            signal.signal(signal.SIGTERM, original)

    def test_system_exit_reaches_finally_block(self):
        # End-to-end shape of the main() contract: SIGTERM-as-SystemExit
        # propagates through a finally block (where the terminal check-in
        # is sent) instead of killing the process outright.
        original = signal.getsignal(signal.SIGTERM)
        ran_finally = {}
        try:
            gwp._install_sigterm_finalizer()
            handler = signal.getsignal(signal.SIGTERM)
            with pytest.raises(SystemExit):
                try:
                    handler(signal.SIGTERM, None)
                finally:
                    import sys
                    ran_finally["exc_in_flight"] = sys.exc_info()[0] is not None
            assert ran_finally["exc_in_flight"] is True
        finally:
            signal.signal(signal.SIGTERM, original)
