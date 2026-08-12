"""
Tests for the report-only rate-sanity audit check.

Covers the 2026-08-12 SAA-DE-20 stale-quantity-formula incident
regression (WR 91916464 / Point 27): Quantity edited 6 -> 3 by the
foreman, but the Smartsheet "Install Quantity" formula cell kept the
stale 6, so ``Units Total Price`` stayed 56.84 x 6 = $341.04 instead
of 56.84 x 3 = $170.52. The primary variant pass-through never caught
this; this REPORT-ONLY detector flags it via the New Rates table
(``data/subcontractor_rates.csv``) keyed by CU + Work Type.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import generate_weekly_pdfs
from audit_billing_changes import BillingAudit


class RateSanityTestBase(unittest.TestCase):
    """Shared setUp/tearDown: patch the subcontractor rates table.

    Mirrors ``tests/test_subcontractor_pricing.py``
    ``TestResolveRowPriceCanonicalColumnNames`` (L1861-1877).
    """

    def setUp(self):
        self._orig_rates = dict(generate_weekly_pdfs._SUBCONTRACTOR_RATES)
        generate_weekly_pdfs._SUBCONTRACTOR_RATES.clear()
        generate_weekly_pdfs._SUBCONTRACTOR_RATES['SAA-DE-20'] = {
            'cu_code': 'SAA-DE-20',
            'cu_wbs': '000',
            'compatible_unit_group': 'SAA',
            'new_install_price': 56.84,
            'new_remove_price': 17.72,
            'new_transfer_price': 48.12,
        }

    def tearDown(self):
        generate_weekly_pdfs._SUBCONTRACTOR_RATES.clear()
        generate_weekly_pdfs._SUBCONTRACTOR_RATES.update(self._orig_rates)


class TestRateSanityIncidentRegression(RateSanityTestBase):
    """Task 1: the SAA-DE-20 incident row + the clean-case row."""

    def setUp(self):
        super().setUp()
        self.audit = BillingAudit(client=None, skip_cell_history=True)

    def test_incident_row_is_flagged(self):
        """qty 3 / $341.04 -> exactly one mismatch, expected 170.52, delta 170.52."""
        row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)
        record = mismatches[0]
        self.assertAlmostEqual(record['expected_price'], 170.52)
        self.assertAlmostEqual(record['actual_price'], 341.04)
        self.assertAlmostEqual(record['delta'], 170.52)
        self.assertEqual(record['type'], 'rate_sanity_mismatch')
        self.assertEqual(record['work_request'], '91916464')

    def test_clean_row_is_not_flagged(self):
        """qty 1 / $56.84 (correct price) -> zero mismatches."""
        row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '1',
            'Units Total Price': '$56.84',
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])


class TestRateSanityEndToEndWiring(RateSanityTestBase):
    """Task 1 Test 3: audit_financial_data() surfaces the record."""

    def test_audit_financial_data_surfaces_mismatch(self):
        row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        with tempfile.TemporaryDirectory() as tmp_dir, \
                mock.patch.object(BillingAudit, '_save_audit_state'), \
                mock.patch.object(BillingAudit, '_log_to_audit_sheet'):
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                audit = BillingAudit(client=None, skip_cell_history=True)
                results = audit.audit_financial_data([], [row])
            finally:
                os.chdir(original_cwd)

        self.assertIn('rate_sanity_mismatches', results)
        self.assertEqual(len(results['rate_sanity_mismatches']), 1)
        self.assertAlmostEqual(
            results['rate_sanity_mismatches'][0]['expected_price'], 170.52
        )


class TestRateSanitySkipsAndTolerance(RateSanityTestBase):
    """Task 2: skip classes, tolerance edges, counters, kill-switch."""

    def setUp(self):
        super().setUp()
        self.audit = BillingAudit(client=None, skip_cell_history=True)

    def _base_row(self, **overrides):
        row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        row.update(overrides)
        return row

    def test_missing_cu_is_skipped(self):
        row = self._base_row(CU='NOT-IN-TABLE')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_zero_quantity_is_skipped(self):
        row = self._base_row(Quantity='0')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_missing_quantity_is_skipped(self):
        row = self._base_row(Quantity='')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_none_quantity_is_skipped(self):
        row = self._base_row(Quantity=None)
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_unparseable_quantity_is_skipped(self):
        row = self._base_row(Quantity='abc')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_unparseable_price_is_skipped(self):
        row = self._base_row(**{'Units Total Price': 'not-a-number'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_empty_price_is_skipped(self):
        row = self._base_row(**{'Units Total Price': ''})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_none_price_is_skipped(self):
        row = self._base_row(**{'Units Total Price': None})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_unknown_work_type_is_skipped(self):
        row = self._base_row(**{'Work Type': 'Splice'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_empty_work_type_is_skipped(self):
        row = self._base_row(**{'Work Type': ''})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_small_delta_within_tolerance_not_flagged(self):
        """expected 170.52 vs actual 170.53 -> within the $0.02 floor."""
        row = self._base_row(**{'Units Total Price': '$170.53'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])

    def test_mid_delta_within_pct_tolerance_not_flagged(self):
        """expected 170.52 vs actual 171.00 -> within 0.5% ($0.8526)."""
        row = self._base_row(**{'Units Total Price': '$171.00'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])

    def test_large_delta_exceeds_tolerance_flagged(self):
        """expected 170.52 vs actual 172.00 -> exceeds both floors."""
        row = self._base_row(**{'Units Total Price': '$172.00'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)

    def test_decorated_quantity_parses_and_flags(self):
        row = self._base_row(Quantity='3 EA')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)
        self.assertAlmostEqual(mismatches[0]['expected_price'], 170.52)

    def test_kill_switch_disables_detector(self):
        row = self._base_row()
        with mock.patch.dict(
            os.environ, {'RATE_SANITY_AUDIT_ENABLED': 'false'}
        ):
            mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])


class TestRateSanitySummary(RateSanityTestBase):
    """Task 2: summary counters and risk-level escalation."""

    def test_summary_counts_and_escalates_risk(self):
        row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        with tempfile.TemporaryDirectory() as tmp_dir, \
                mock.patch.object(BillingAudit, '_save_audit_state'), \
                mock.patch.object(BillingAudit, '_log_to_audit_sheet'):
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                audit = BillingAudit(client=None, skip_cell_history=True)
                results = audit.audit_financial_data([], [row])
            finally:
                os.chdir(original_cwd)

        summary = results['summary']
        self.assertEqual(summary['total_rate_sanity_mismatches'], 1)
        self.assertNotEqual(summary['risk_level'], 'LOW')

    def test_kill_switch_zeroes_summary_counter(self):
        row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        with tempfile.TemporaryDirectory() as tmp_dir, \
                mock.patch.object(BillingAudit, '_save_audit_state'), \
                mock.patch.object(BillingAudit, '_log_to_audit_sheet'), \
                mock.patch.dict(
                    os.environ, {'RATE_SANITY_AUDIT_ENABLED': 'false'}
                ):
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                audit = BillingAudit(client=None, skip_cell_history=True)
                results = audit.audit_financial_data([], [row])
            finally:
                os.chdir(original_cwd)

        self.assertEqual(results['rate_sanity_mismatches'], [])
        self.assertEqual(
            results['summary']['total_rate_sanity_mismatches'], 0
        )


class TestRateSanityAggregateInclusion(RateSanityTestBase):
    """CR-01 regression lock: rate-sanity mismatches must be counted in
    EVERY total_issues aggregate (persisted history entry, audit-sheet
    payload, and trend delta) -- not only in the risk-level sum inside
    ``_generate_audit_summary()``. A mismatch-only run (zero anomalies,
    zero unauthorized changes, zero data issues) previously recorded
    ``total_issues == 0`` in ``risk_trend.json`` and produced a zero
    trend delta, hiding the run from history/trend consumers even
    though the top-level summary and risk level correctly escalated.
    """

    def test_mismatch_only_run_records_nonzero_history_total_issues(
        self,
    ) -> None:
        row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        with tempfile.TemporaryDirectory() as tmp_dir, \
                mock.patch.object(BillingAudit, '_save_audit_state'), \
                mock.patch.object(BillingAudit, '_log_to_audit_sheet'):
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                # Mirrors the real pipeline, where generated_docs/
                # already exists before an audit runs.
                os.makedirs('generated_docs', exist_ok=True)
                audit = BillingAudit(client=None, skip_cell_history=True)
                results = audit.audit_financial_data([], [row])
                hist_path = os.path.join(
                    'generated_docs', 'risk_trend.json'
                )
                with open(hist_path) as hist_file:
                    history = json.load(hist_file)
            finally:
                os.chdir(original_cwd)

        summary = results['summary']
        self.assertEqual(summary['total_anomalies'], 0)
        self.assertEqual(summary['total_unauthorized_changes'], 0)
        self.assertEqual(summary['total_data_issues'], 0)
        self.assertEqual(summary['total_rate_sanity_mismatches'], 1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['total_issues'], 1)

    def test_mismatch_only_run_produces_correct_trend_issue_delta(
        self,
    ) -> None:
        clean_row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '1',
            'Units Total Price': '$56.84',
        }
        mismatch_row = {
            'Work Request #': '91916464',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        with tempfile.TemporaryDirectory() as tmp_dir, \
                mock.patch.object(BillingAudit, '_log_to_audit_sheet'):
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                audit = BillingAudit(client=None, skip_cell_history=True)
                audit.audit_financial_data([], [clean_row])
                results = audit.audit_financial_data([], [mismatch_row])
            finally:
                os.chdir(original_cwd)

        trend = results['trend']
        self.assertEqual(trend['issues_delta'], 1)
        self.assertEqual(trend['risk_direction'], 'worsening')


if __name__ == '__main__':
    unittest.main()
