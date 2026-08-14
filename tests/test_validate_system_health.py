"""Tests for validate_system_health.py (offline, no network).

The script's contract with system-health-check.yml:
* always writes generated_docs/system_health.json,
* always exits 0 when the report was written (the workflow's
  evaluate step owns pass/fail),
* overall_status reduces check statuses: any critical -> CRITICAL,
  else any warn -> WARN, else OK; skipped never escalates.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import validate_system_health as vsh


def _result(name: str, status: str) -> vsh.CheckResult:
    return vsh.CheckResult(name=name, status=status, detail="test")


class TestOverallStatus(unittest.TestCase):
    """The OK/WARN/CRITICAL reduction the workflow consumes."""

    def test_all_ok_is_ok(self):
        checks = [_result("a", vsh.STATUS_OK)]
        self.assertEqual(vsh.overall_status(checks), "OK")

    def test_warn_escalates_to_warn(self):
        checks = [
            _result("a", vsh.STATUS_OK),
            _result("b", vsh.STATUS_WARN),
        ]
        self.assertEqual(vsh.overall_status(checks), "WARN")

    def test_critical_wins_over_warn(self):
        checks = [
            _result("a", vsh.STATUS_WARN),
            _result("b", vsh.STATUS_CRITICAL),
        ]
        self.assertEqual(vsh.overall_status(checks), "CRITICAL")

    def test_skipped_never_escalates(self):
        checks = [
            _result("a", vsh.STATUS_OK),
            _result("b", vsh.STATUS_SKIPPED),
        ]
        self.assertEqual(vsh.overall_status(checks), "OK")


class TestTimedWrapper(unittest.TestCase):
    """_timed must capture exceptions as CRITICAL, never raise."""

    def test_exception_becomes_critical(self):
        def boom():
            raise RuntimeError("kaput")

        result = vsh._timed("boom", boom)
        self.assertEqual(result.status, vsh.STATUS_CRITICAL)
        self.assertIn("RuntimeError", result.detail)

    def test_success_passes_through(self):
        result = vsh._timed("ok", lambda: (vsh.STATUS_OK, "fine"))
        self.assertEqual(result.status, vsh.STATUS_OK)
        self.assertEqual(result.detail, "fine")


class TestTokenCheck(unittest.TestCase):
    """SMARTSHEET_API_TOKEN presence gates the API checks."""

    def test_missing_token_is_critical(self):
        ctx = vsh.HealthContext()
        with mock.patch.dict(os.environ, {}, clear=True):
            status, detail = vsh.check_smartsheet_token(ctx)
        self.assertEqual(status, vsh.STATUS_CRITICAL)
        self.assertFalse(ctx.token_present)

    def test_present_token_is_ok_and_never_logged(self):
        ctx = vsh.HealthContext()
        env = {"SMARTSHEET_API_TOKEN": "secret-value"}
        with mock.patch.dict(os.environ, env, clear=True):
            status, detail = vsh.check_smartsheet_token(ctx)
        self.assertEqual(status, vsh.STATUS_OK)
        self.assertTrue(ctx.token_present)
        self.assertNotIn("secret-value", detail)


class TestApiChecks(unittest.TestCase):
    """API checks skip without a token and use the mocked client."""

    def test_api_check_skips_without_token(self):
        ctx = vsh.HealthContext()
        ctx.token_present = False
        status, _ = vsh.check_smartsheet_api(ctx)
        self.assertEqual(status, vsh.STATUS_SKIPPED)

    def test_api_check_authenticates_with_client(self):
        ctx = vsh.HealthContext()
        ctx.token_present = True
        fake_client = mock.Mock()
        env = {"SMARTSHEET_API_TOKEN": "t"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(
                    vsh, "_build_client", return_value=fake_client
                ):
            status, _ = vsh.check_smartsheet_api(ctx)
        self.assertEqual(status, vsh.STATUS_OK)
        fake_client.Users.get_current_user.assert_called_once()

    def test_target_sheet_skips_without_client(self):
        ctx = vsh.HealthContext()
        status, _ = vsh.check_target_sheet(ctx)
        self.assertEqual(status, vsh.STATUS_SKIPPED)

    def test_target_sheet_uses_default_id(self):
        ctx = vsh.HealthContext()
        ctx.client = mock.Mock()
        with mock.patch.dict(os.environ, {}, clear=True):
            status, _ = vsh.check_target_sheet(ctx)
        self.assertEqual(status, vsh.STATUS_OK)
        ctx.client.Sheets.get_sheet.assert_called_once_with(
            vsh.DEFAULT_TARGET_SHEET_ID, page_size=1
        )

    def test_target_sheet_honors_env_override(self):
        ctx = vsh.HealthContext()
        ctx.client = mock.Mock()
        env = {"TARGET_SHEET_ID": "12345"}
        with mock.patch.dict(os.environ, env, clear=True):
            vsh.check_target_sheet(ctx)
        ctx.client.Sheets.get_sheet.assert_called_once_with(
            12345, page_size=1
        )


class TestConfigSanity(unittest.TestCase):
    """Guardrail values: PARALLEL_WORKERS cap and budget parsing."""

    def test_workers_over_cap_warns(self):
        ctx = vsh.HealthContext()
        env = {"PARALLEL_WORKERS": "12"}
        with mock.patch.dict(os.environ, env, clear=True):
            status, detail = vsh.check_config_sanity(ctx)
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertIn("exceeds cap 8", detail)

    def test_workers_at_cap_ok(self):
        ctx = vsh.HealthContext()
        env = {"PARALLEL_WORKERS": "8"}
        with mock.patch.dict(os.environ, env, clear=True):
            status, _ = vsh.check_config_sanity(ctx)
        self.assertEqual(status, vsh.STATUS_OK)

    def test_bad_budget_warns(self):
        ctx = vsh.HealthContext()
        env = {"TIME_BUDGET_MINUTES": "ninety"}
        with mock.patch.dict(os.environ, env, clear=True):
            status, detail = vsh.check_config_sanity(ctx)
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertIn("TIME_BUDGET_MINUTES", detail)

    def test_sentry_absence_is_note_not_warn(self):
        ctx = vsh.HealthContext()
        with mock.patch.dict(os.environ, {}, clear=True):
            status, _ = vsh.check_config_sanity(ctx)
        self.assertEqual(status, vsh.STATUS_OK)
        self.assertTrue(
            any("SENTRY_DSN" in note for note in ctx.notes)
        )


class TestReport(unittest.TestCase):
    """Report assembly and writing."""

    def test_report_shape(self):
        checks = [_result("a", vsh.STATUS_OK)]
        report = vsh.build_report(checks, ["note"])
        self.assertEqual(report["overall_status"], "OK")
        self.assertIn("generated_at_utc", report)
        self.assertEqual(report["summary"], {"ok": 1})
        self.assertEqual(len(report["checks"]), 1)

    def test_write_report_round_trips(self):
        checks = [_result("a", vsh.STATUS_WARN)]
        report = vsh.build_report(checks, [])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "health.json")
            vsh.write_report(report, path)
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
        self.assertEqual(loaded["overall_status"], "WARN")


class TestMainContract(unittest.TestCase):
    """main() exits 0 whenever the report is written."""

    def _run_main_with_stubbed_checks(self, tmp: str) -> int:
        stub = [_result("stub", vsh.STATUS_CRITICAL)]
        path = os.path.join(tmp, "system_health.json")
        with mock.patch.object(
            vsh, "run_checks", return_value=stub
        ), mock.patch.object(vsh, "REPORT_PATH", path), \
                mock.patch.dict(os.environ, {}, clear=True):
            exit_code = vsh.main()
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            self.report = json.load(handle)
        return exit_code

    def test_critical_still_exits_zero_with_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            exit_code = self._run_main_with_stubbed_checks(tmp)
        self.assertEqual(exit_code, 0)
        self.assertEqual(self.report["overall_status"], "CRITICAL")

    def test_unwritable_report_exits_one(self):
        stub = [_result("stub", vsh.STATUS_OK)]
        with mock.patch.object(
            vsh, "run_checks", return_value=stub
        ), mock.patch.object(
            vsh, "write_report", side_effect=OSError("disk full")
        ), mock.patch.dict(os.environ, {}, clear=True):
            exit_code = vsh.main()
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
