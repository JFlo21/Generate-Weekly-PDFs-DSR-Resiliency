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


class TestProductionWorkflowConfig(unittest.TestCase):
    """Grades .github/workflows/weekly-excel-generation.yml directly.

    Each test writes a YAML fixture into a TemporaryDirectory and
    passes that path explicitly -- no network, no real workflow file.
    """

    def _fixture(self, tmp: str, text: str) -> str:
        path = os.path.join(tmp, "weekly-excel-generation.yml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_happy_path_mirrors_real_workflow_is_ok(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    timeout-minutes: 180\n"
            "    env:\n"
            "      PARALLEL_WORKERS: "
            "${{ github.event.inputs.parallel_workers || '8' }}\n"
            "      PARALLEL_WORKERS_DISCOVERY: "
            "${{ github.event.inputs.parallel_workers_discovery"
            " || '8' }}\n"
            "      TIME_BUDGET_MINUTES: '165'\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_OK)

    def test_comment_immunity(self):
        text = (
            "# Serialize runs. With timeout-minutes: 500 in prose,\n"
            "# and an example PARALLEL_WORKERS: 99 for reference.\n"
            "jobs:\n"
            "  core:\n"
            "    env:\n"
            "      TIME_BUDGET_MINUTES: '165'\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_OK)
        self.assertNotIn("99", detail)
        self.assertFalse(
            any("99" in note or "500" in note for note in ctx.notes)
        )

    def test_over_cap_primary_worker_warns(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    env:\n"
            "      PARALLEL_WORKERS: "
            "${{ github.event.inputs.parallel_workers || '12' }}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertIn("PARALLEL_WORKERS", detail)
        self.assertIn("8", detail)

    def test_over_cap_discovery_worker_warns(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    env:\n"
            "      PARALLEL_WORKERS_DISCOVERY: "
            "${{ github.event.inputs.parallel_workers_discovery"
            " || '16' }}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertIn("PARALLEL_WORKERS_DISCOVERY", detail)

    def test_at_cap_boundary_is_not_warn(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    env:\n"
            "      PARALLEL_WORKERS: "
            "${{ github.event.inputs.parallel_workers || '8' }}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, _ = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_OK)

    def test_non_numeric_budget_warns(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    env:\n"
            "      TIME_BUDGET_MINUTES: 'ninety'\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertIn("TIME_BUDGET_MINUTES", detail)

    def test_budget_not_below_ceiling_warns(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    timeout-minutes: 180\n"
            "    env:\n"
            "      TIME_BUDGET_MINUTES: '180'\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertIn("TIME_BUDGET_MINUTES", detail)

    def test_budget_below_ceiling_is_not_warn(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    timeout-minutes: 180\n"
            "    env:\n"
            "      TIME_BUDGET_MINUTES: '165'\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, _ = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_OK)

    def test_missing_file_is_critical(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "does-not-exist.yml")
            ctx = vsh.HealthContext()
            status, _ = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_CRITICAL)

    def test_unparseable_value_warns_but_grades_others(self):
        text = (
            "jobs:\n"
            "  core:\n"
            "    timeout-minutes: 180\n"
            "    env:\n"
            "      PARALLEL_WORKERS: "
            "${{ github.event.inputs.parallel_workers }}\n"
            "      PARALLEL_WORKERS_DISCOVERY: "
            "${{ github.event.inputs.parallel_workers_discovery"
            " || '8' }}\n"
            "      TIME_BUDGET_MINUTES: '165'\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertIn("PARALLEL_WORKERS", detail)
        self.assertNotIn("PARALLEL_WORKERS_DISCOVERY", detail)

    def test_absent_keys_are_notes_not_problems(self):
        text = "jobs:\n  core:\n    env: {}\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, _ = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_OK)
        self.assertTrue(
            any("PARALLEL_WORKERS" in note for note in ctx.notes)
        )
        self.assertTrue(
            any(
                "TIME_BUDGET_MINUTES" in note or "timeout" in note
                for note in ctx.notes
            )
        )

    def test_detail_hygiene_redacts_and_truncates(self):
        long_value = "x" * 300
        text = (
            "jobs:\n"
            "  core:\n"
            "    env:\n"
            "      PARALLEL_WORKERS: "
            "${{ secrets.SOME_TOKEN_NEVER_SHOWN }}\n"
            "      PARALLEL_WORKERS_DISCOVERY: '" + long_value
            + "'\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fixture(tmp, text)
            ctx = vsh.HealthContext()
            status, detail = vsh.check_production_workflow_config(
                ctx, path=path
            )
        self.assertEqual(status, vsh.STATUS_WARN)
        self.assertNotIn("SOME_TOKEN_NEVER_SHOWN", detail)
        self.assertNotIn(long_value, detail)
        self.assertLess(len(detail), 400)


class TestProductionCheckRegistration(unittest.TestCase):
    """production_workflow_config must be wired into run_checks()."""

    def test_production_check_is_registered(self):
        recorded_names = []

        def _fake_timed(name, fn):
            recorded_names.append(name)
            return _result(name, vsh.STATUS_OK)

        with mock.patch.object(vsh, "_timed", side_effect=_fake_timed):
            vsh.run_checks(vsh.HealthContext())
        self.assertIn("production_workflow_config", recorded_names)


class TestConfigSanityScopeLabel(unittest.TestCase):
    """check_config_sanity must state its process-env-only scope."""

    def test_env_check_detail_states_process_scope(self):
        ctx = vsh.HealthContext()
        with mock.patch.dict(os.environ, {}, clear=True):
            status, detail = vsh.check_config_sanity(ctx)
        self.assertEqual(status, vsh.STATUS_OK)
        self.assertIn("process", detail.lower())
        self.assertIn("environment", detail.lower())


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
