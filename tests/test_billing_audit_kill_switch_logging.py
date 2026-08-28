"""``billing_audit._disable_for_run`` must not log server text.

Same policy as ``pipeline_memory`` (PR #363): the PostgREST ``message`` /
``hint`` / ``details`` on the run-global kill switch (PGRST106/301/302)
are untrusted diagnostic text that can echo request or database data,
and this repository's Actions logs are public -- only the code, the
error type and the locally authored remediation guidance are logged or
sent to Sentry.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_billing_audit_shadow as shadow  # noqa: E402


class BillingAuditKillSwitchDiagnosticsTests(unittest.TestCase):

    def setUp(self):
        shadow._reset_all()

    def tearDown(self):
        shadow._reset_all()

    def _trip(self, reason_code, exc):
        from billing_audit import client as ba_client

        crumbs: list = []
        with mock.patch(
            "billing_audit.client._sentry_breadcrumb",
            side_effect=lambda *a, **k: crumbs.append((a, k)),
        ), self.assertLogs(level="WARNING") as logs:
            ba_client._disable_for_run(reason_code, exc)
        line = next(l for l in logs.output if "disabled for this run" in l)
        crumb = next(
            k for a, k in crumbs if a[1] == "Integration globally disabled"
        )
        self.assertIsNone(ba_client.get_client())
        return line, crumb["data"]

    def test_kill_switch_logs_code_and_local_guidance_only(self):
        from postgrest.exceptions import APIError

        line, data = self._trip("PGRST106", APIError({
            "message": "secret-message-marker",
            "code": "PGRST106",
            "details": "secret-details-marker",
            "hint": "secret-hint-marker",
        }))

        self.assertIn("code=PGRST106", line)
        self.assertIn("Exposed schemas", line)
        self.assertIn("billing_audit", line)
        self.assertEqual(data["reason_code"], "PGRST106")
        for marker in ("secret-message-marker", "secret-hint-marker",
                       "secret-details-marker"):
            self.assertNotIn(marker, line)
            self.assertNotIn(marker, repr(data))

    def test_auth_kill_switch_also_withholds_server_text(self):
        from postgrest.exceptions import APIError

        line, data = self._trip("PGRST301", APIError({
            "message": "secret-jwt-marker", "code": "PGRST301",
            "details": None, "hint": "secret-hint-marker",
        }))

        self.assertIn("code=PGRST301", line)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", line)
        for marker in ("secret-jwt-marker", "secret-hint-marker"):
            self.assertNotIn(marker, line)
            self.assertNotIn(marker, repr(data))


if __name__ == "__main__":
    unittest.main()
