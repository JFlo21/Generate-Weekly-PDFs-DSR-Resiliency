"""Attribution-resolution recent-week scoping (perf hotfix 2026-05-26).

The per-row ``lookup_attribution`` Supabase RPC was being called for EVERY
completed row across ALL historical weeks (~137k calls/run), dominated by
old weeks that change-detection skips anyway — blowing the workflow time
budget. The fix scopes frozen-attribution resolution to a recent-week
window (``ATTRIBUTION_RESOLUTION_WEEKS``): rows older than the window
resolve to use-current (their groups are already frozen-attributed +
skipped, so the result is unused). See the Living Ledger 2026-05-26 entry.
"""
import datetime
import inspect
import unittest
from unittest import mock

# Use the real Smartsheet SDK when installed; only inject the MagicMock
# stub when it is genuinely absent. This file sorts alphabetically first,
# so calling _ensure_smartsheet_mocked() unconditionally at import would
# install a bare ``smartsheet`` stub during collection and SHADOW the real
# SDK that other suites (e.g. TestDiscoverFolderSheets) need
# (``from smartsheet.models.sheet import Sheet``).
try:  # pragma: no cover - environment dependent
    import smartsheet  # noqa: F401
except ImportError:  # pragma: no cover
    from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked
    _ensure_smartsheet_mocked()

import generate_weekly_pdfs as gwp  # noqa: E402


class TestAttributionResolutionWeeksConfig(unittest.TestCase):
    def test_env_var_exists_and_is_int(self):
        self.assertIsInstance(gwp.ATTRIBUTION_RESOLUTION_WEEKS, int)

    def test_banner_logs_flag(self):
        src = inspect.getsource(gwp)
        self.assertIn("📋 ATTRIBUTION_RESOLUTION_WEEKS=", src)


class TestAttributionWeekInScope(unittest.TestCase):
    """Unit tests for the recent-week scope predicate."""

    def setUp(self):
        self._saved = gwp.ATTRIBUTION_RESOLUTION_WEEKS

    def tearDown(self):
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = self._saved

    def test_recent_week_in_scope(self):
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = 8
        recent = datetime.date.today() - datetime.timedelta(weeks=2)
        self.assertTrue(gwp._attribution_week_in_scope(recent))

    def test_old_week_out_of_scope(self):
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = 8
        old = datetime.date.today() - datetime.timedelta(weeks=30)
        self.assertFalse(gwp._attribution_week_in_scope(old))

    def test_boundary_week_in_scope(self):
        # Exactly at the cutoff is still in scope (>=).
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = 8
        boundary = datetime.date.today() - datetime.timedelta(weeks=8)
        self.assertTrue(gwp._attribution_week_in_scope(boundary))

    def test_disabled_resolves_all(self):
        # 0 (or negative) disables scoping — resolve every week (escape hatch).
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = 0
        old = datetime.date.today() - datetime.timedelta(weeks=200)
        self.assertTrue(gwp._attribution_week_in_scope(old))

    def test_datetime_input_normalized(self):
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = 8
        recent_dt = datetime.datetime.now() - datetime.timedelta(weeks=1)
        self.assertTrue(gwp._attribution_week_in_scope(recent_dt))
        old_dt = datetime.datetime.now() - datetime.timedelta(weeks=40)
        self.assertFalse(gwp._attribution_week_in_scope(old_dt))

    def test_none_is_in_scope_failsafe(self):
        # If we can't determine the week, resolve (fail-safe — never silently
        # drop attribution for a row whose date is unknown).
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = 8
        self.assertTrue(gwp._attribution_week_in_scope(None))


class TestPrePassRespectsWeekScope(unittest.TestCase):
    """Behavioral: group_source_rows must NOT resolve attribution for rows
    whose week_ending is older than the window."""

    def setUp(self):
        self._saved = {
            'weeks': gwp.ATTRIBUTION_RESOLUTION_WEEKS,
            'prim': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'mode': gwp.RES_GROUPING_MODE,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
        }
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = 8
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp.BILLING_AUDIT_AVAILABLE = True

    def tearDown(self):
        gwp.ATTRIBUTION_RESOLUTION_WEEKS = self._saved['weeks']
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['prim']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']

    def _primary_row(self, row_id, weeks_ago):
        wed = datetime.datetime.now() - datetime.timedelta(weeks=weeks_ago)
        return {
            'Work Request #': '90001',
            'Weekly Reference Logged Date': wed.strftime('%Y-%m-%d'),
            'Units Completed?': True,
            'Units Total Price': '$100.00',
            'CU': 'XYZ', 'Work Type': 'Install', 'Quantity': 1,
            'Customer Name': 'C', 'Foreman': 'PF', 'Dept #': '500',
            'Job #': 'J-1', 'User': 'PF',
            '__row_id': row_id,
            '__effective_user': 'PF',
            '__current_foreman': 'PF',
        }

    def test_old_week_primary_row_not_resolved(self):
        rows = [self._primary_row(1001, weeks_ago=1),
                self._primary_row(2002, weeks_ago=30)]
        seen_row_ids = []

        def _fake_resolve(variant, current, *, wr, week_ending, row_id, enabled):
            seen_row_ids.append(row_id)
            from billing_audit.writer import ResolveOutcome
            return ResolveOutcome("use", current, "current", "no_history")

        with mock.patch("billing_audit.writer.resolve_claimer",
                        side_effect=_fake_resolve):
            gwp.group_source_rows(rows)

        # The recent row (1001) is resolved; the 30-week-old row (2002) is not.
        self.assertIn(1001, seen_row_ids)
        self.assertNotIn(2002, seen_row_ids)


class TestResolveSitesGatedOnScope(unittest.TestCase):
    """Source-grep guard: all attribution resolve sites must consult the
    recent-week scope predicate so the perf fix can't be silently reverted."""

    def test_scope_predicate_referenced_in_group_source_rows(self):
        src = inspect.getsource(gwp.group_source_rows)
        # At least the three pre-passes (B/C/D) + the helper path = 4 gates.
        self.assertGreaterEqual(
            src.count("_attribution_week_in_scope("), 4,
            "expected >=4 _attribution_week_in_scope gates "
            "(B/C/D pre-passes + helper path)",
        )


if __name__ == "__main__":
    unittest.main()
