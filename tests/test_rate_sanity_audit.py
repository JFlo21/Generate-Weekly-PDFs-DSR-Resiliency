"""
Tests for the report-only rate-sanity audit check.

Covers the 2026-08-12 SAA-DE-20 stale-quantity-formula incident
regression (WR 16881353 / Point 27): Quantity edited 6 -> 3 by the
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
from typing import Any, Dict
from unittest import mock

import generate_weekly_pdfs
from audit_billing_changes import BillingAudit


class RateSanityTestBase(unittest.TestCase):
    """Shared setUp/tearDown: patch the subcontractor rates table.

    Mirrors ``tests/test_subcontractor_pricing.py``
    ``TestResolveRowPriceCanonicalColumnNames`` (L1861-1877).
    """

    def setUp(self) -> None:
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

    def tearDown(self) -> None:
        generate_weekly_pdfs._SUBCONTRACTOR_RATES.clear()
        generate_weekly_pdfs._SUBCONTRACTOR_RATES.update(self._orig_rates)


class TestRateSanityIncidentRegression(RateSanityTestBase):
    """Task 1: the SAA-DE-20 incident row + the clean-case row."""

    def setUp(self) -> None:
        super().setUp()
        self.audit = BillingAudit(client=None, skip_cell_history=True)

    def test_incident_row_is_flagged(self) -> None:
        """qty 3 / $341.04 -> exactly one mismatch, expected 170.52, delta 170.52."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            # Post-cutoff: keeps the row inside the current-cycle
            # scope gate (260813 scoping follow-up).
            'Snapshot Date': '2026-08-09',
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)
        record = mismatches[0]
        self.assertAlmostEqual(record['expected_price'], 170.52)
        self.assertAlmostEqual(record['actual_price'], 341.04)
        self.assertAlmostEqual(record['delta'], 170.52)
        self.assertEqual(record['type'], 'rate_sanity_mismatch')
        self.assertEqual(record['work_request'], '16881353')

    def test_clean_row_is_not_flagged(self) -> None:
        """qty 1 / $56.84 (correct price) -> zero mismatches."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '1',
            'Units Total Price': '$56.84',
            'Snapshot Date': '2026-08-09',
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])


class TestRateSanityEndToEndWiring(RateSanityTestBase):
    """Task 1 Test 3: audit_financial_data() surfaces the record."""

    def test_audit_financial_data_surfaces_mismatch(self) -> None:
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
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

    def setUp(self) -> None:
        super().setUp()
        self.audit = BillingAudit(client=None, skip_cell_history=True)

    def _base_row(self, **overrides: Any) -> Dict[str, Any]:
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            # Post-cutoff: skip/tolerance classes are asserted for
            # IN-SCOPE rows (260813 scoping follow-up).
            'Snapshot Date': '2026-08-09',
        }
        row.update(overrides)
        return row

    def test_missing_cu_is_skipped(self) -> None:
        row = self._base_row(CU='NOT-IN-TABLE')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_zero_quantity_is_skipped(self) -> None:
        row = self._base_row(Quantity='0')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_missing_quantity_is_skipped(self) -> None:
        row = self._base_row(Quantity='')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_none_quantity_is_skipped(self) -> None:
        row = self._base_row(Quantity=None)
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_unparseable_quantity_is_skipped(self) -> None:
        row = self._base_row(Quantity='abc')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_unparseable_price_is_skipped(self) -> None:
        row = self._base_row(**{'Units Total Price': 'not-a-number'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_empty_price_is_skipped(self) -> None:
        row = self._base_row(**{'Units Total Price': ''})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_none_price_is_skipped(self) -> None:
        row = self._base_row(**{'Units Total Price': None})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_unknown_work_type_is_skipped(self) -> None:
        row = self._base_row(**{'Work Type': 'Splice'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_empty_work_type_is_skipped(self) -> None:
        row = self._base_row(**{'Work Type': ''})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_skipped, 1)

    def test_small_delta_within_tolerance_not_flagged(self) -> None:
        """expected 170.52 vs actual 170.53 -> within the $0.02 floor."""
        row = self._base_row(**{'Units Total Price': '$170.53'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])

    def test_mid_delta_within_pct_tolerance_not_flagged(self) -> None:
        """expected 170.52 vs actual 171.00 -> within 0.5% ($0.8526)."""
        row = self._base_row(**{'Units Total Price': '$171.00'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])

    def test_large_delta_exceeds_tolerance_flagged(self) -> None:
        """expected 170.52 vs actual 172.00 -> exceeds both floors."""
        row = self._base_row(**{'Units Total Price': '$172.00'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)

    def test_decorated_quantity_parses_and_flags(self) -> None:
        row = self._base_row(Quantity='3 EA')
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)
        self.assertAlmostEqual(mismatches[0]['expected_price'], 170.52)

    def test_kill_switch_disables_detector(self) -> None:
        row = self._base_row()
        with mock.patch.dict(
            os.environ, {'RATE_SANITY_AUDIT_ENABLED': 'false'}
        ):
            mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])


class TestRateSanitySummary(RateSanityTestBase):
    """Task 2: summary counters and risk-level escalation."""

    def test_summary_counts_and_escalates_risk(self) -> None:
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
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

    def test_kill_switch_zeroes_summary_counter(self) -> None:
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
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
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
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
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '1',
            'Units Total Price': '$56.84',
            'Snapshot Date': '2026-08-09',
        }
        mismatch_row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
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


class TestRateSanityCurrentCycleScoping(RateSanityTestBase):
    """Scoping follow-up (260813): current-cycle rows only.

    The expected price is the New Rates basis, which only applies to
    rows billed under the 2026-04-12 subcontractor rate contract. The
    2026-08-12 live dry run showed the unscoped detector flagging
    115,272/199,717 rows (58% -- old-rates history vs New-Rates
    expected) and pinning ``risk_level`` HIGH every CI run. The
    detector now reuses the production era gate (SUB-01 / D-08):
    ``Snapshot Date >= _AEP_BILLABLE_CUTOFF`` with the Weekly
    Reference Logged Date fallback of
    ``_resolve_rate_recalc_cutoff_date``.
    """

    def setUp(self) -> None:
        super().setUp()
        self.audit = BillingAudit(client=None, skip_cell_history=True)

    def _mismatch_row(self, **overrides: Any) -> Dict[str, Any]:
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        row.update(overrides)
        return row

    def test_pre_cutoff_snapshot_row_is_out_of_scope(self) -> None:
        row = self._mismatch_row(**{'Snapshot Date': '2026-03-01'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)
        self.assertEqual(self.audit._rate_sanity_skipped, 0)

    def test_post_cutoff_snapshot_mismatch_still_flagged(self) -> None:
        row = self._mismatch_row(**{'Snapshot Date': '2026-08-09'})
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 0)

    def test_blank_snapshot_with_post_cutoff_weekly_is_in_scope(
        self,
    ) -> None:
        """Weekly-Ref fallback rescues rows the snapshot automation
        has not stamped yet (the observed VAC crew failure mode).
        F1 (260813-m5j): the fallback is now sheet-gated on the row's
        own sheet mapping a Snapshot Date column -- supply a matching
        source_sheets entry so the rescue is exercised deliberately,
        not via the old default-True behavior."""
        row = self._mismatch_row(
            **{
                'Weekly Reference Logged Date': '2026-08-09',
                '__source_sheet_id': 555,
            }
        )
        source_sheets = [{
            'id': 555,
            'name': 'Fallback-Gated Sheet',
            'column_mapping': {'Snapshot Date': 1},
        }]
        mismatches = self.audit._detect_rate_sanity_mismatches(
            [row], source_sheets=source_sheets
        )
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 0)

    def test_blank_snapshot_with_pre_cutoff_weekly_is_out_of_scope(
        self,
    ) -> None:
        row = self._mismatch_row(
            **{'Weekly Reference Logged Date': '2026-03-01'}
        )
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)

    def test_undated_row_is_out_of_scope(self) -> None:
        """No Snapshot Date, no Weekly Reference Logged Date -> the
        row cannot be placed in the New-Rates era -> never checked."""
        row = self._mismatch_row()
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)
        self.assertEqual(self.audit._rate_sanity_skipped, 0)

    def test_pre_cutoff_snapshot_does_not_fall_back_to_weekly(
        self,
    ) -> None:
        """A parseable pre-cutoff Snapshot Date is authoritative --
        mirrors ``_resolve_rate_recalc_cutoff_date`` exactly. The
        sheet-gated fallback (F1, 260813-m5j) is deliberately ENABLED
        here (matching source_sheets metadata) so the test proves
        snapshot precedence over an available fallback, not merely
        that the fallback happens to be off."""
        row = self._mismatch_row(**{
            'Snapshot Date': '2026-03-01',
            'Weekly Reference Logged Date': '2026-08-09',
            '__source_sheet_id': 555,
        })
        source_sheets = [{
            'id': 555,
            'name': 'Fallback-Gated Sheet',
            'column_mapping': {'Snapshot Date': 1},
        }]
        mismatches = self.audit._detect_rate_sanity_mismatches(
            [row], source_sheets=source_sheets
        )
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)

    def test_out_of_scope_precedes_skip_classification(self) -> None:
        """An out-of-scope row with a bad CU counts as out-of-scope,
        not as a skip -- scope is evaluated first."""
        row = self._mismatch_row(**{
            'CU': 'NOT-IN-TABLE',
            'Snapshot Date': '2026-03-01',
        })
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)
        self.assertEqual(self.audit._rate_sanity_skipped, 0)

    def test_summary_reports_out_of_scope_and_stays_low_risk(
        self,
    ) -> None:
        """A history-only run (all rows pre-cutoff) must report LOW
        risk with the out-of-scope count surfaced in the summary."""
        row = self._mismatch_row(**{'Snapshot Date': '2026-03-01'})
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
        self.assertEqual(summary['total_rate_sanity_mismatches'], 0)
        self.assertEqual(summary['rate_sanity_out_of_scope'], 1)
        self.assertEqual(summary['risk_level'], 'LOW')


class TestRateSanityScopeHardening(RateSanityTestBase):
    """PR #332 review hardening (260813-m5j): corrected F1/F2 scope gate.

    F1 (Codex P1): the Weekly Reference Logged Date fallback must be
    gated on the row's own sheet actually mapping a Snapshot Date
    column (mirrors ``pipeline/fetch.py:276``), not defaulted on --
    unknown sheet / absent metadata falls closed to snapshot-only.

    F2 (Copilot, polarity corrected by research): ``__is_subcontractor``
    rows are out of scope -- their ``Units Total Price`` sits at the
    Subcontractor-Rates basis (``reduced_*_price`` / the pre-acceptance
    rescue overwrite at pipeline/fetch.py:477), not the New-Rates basis
    this detector compares against. The literal F2 ("restrict scope TO
    subcontractor rows") is REJECTED -- the SAA-DE-20 incident sheet
    ("Resiliency Promax Database Backup 86") is a non-subcontractor
    ProMax sheet and must stay in scope (see R1 below).

    Every case drives the public entry point
    ``_detect_rate_sanity_mismatches(rows, source_sheets=...)`` so the
    tests also pin the production wiring, per R10 which instead drives
    ``audit_financial_data`` to pin the summary counter contract.
    """

    def setUp(self) -> None:
        super().setUp()
        self.audit = BillingAudit(client=None, skip_cell_history=True)
        # Hermetic against a dev shell exporting RATE_RECALC_WEEKLY_
        # FALLBACK=0 -- the constant is frozen at import
        # (pipeline/pricing.py:64-66), so R6-R10 must not depend on
        # the ambient environment. R11/R12 override this locally with
        # their own mock.patch.object(..., False).
        patcher = mock.patch.object(
            generate_weekly_pdfs, 'RATE_RECALC_WEEKLY_FALLBACK', True
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_r1_incident_row_survives_f2_fix(self) -> None:
        """Anti-regression (the most important test here): the
        SAA-DE-20 incident row on the non-subcontractor Backup 86
        sheet must still be flagged after both fixes ship."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
            '__is_subcontractor': False,
            '__source_sheet_id': 1824542300262276,
        }
        source_sheets = [{
            'id': 1824542300262276,
            'name': 'Resiliency Promax Database Backup 86',
            'column_mapping': {'Snapshot Date': 1},
        }]
        mismatches = self.audit._detect_rate_sanity_mismatches(
            [row], source_sheets=source_sheets
        )
        self.assertEqual(len(mismatches), 1)
        self.assertAlmostEqual(mismatches[0]['expected_price'], 170.52)

    def test_r2_subcontractor_row_at_sub_rate_is_out_of_scope(
        self,
    ) -> None:
        """Subcontractor-sheet row priced at the sub-rate basis
        ($49.66, the correct price for that basis) is excluded with
        reason ``subcontractor_basis``, not flagged as a mismatch."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '1',
            'Units Total Price': '$49.66',
            'Snapshot Date': '2026-08-09',
            '__is_subcontractor': True,
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)
        self.assertEqual(
            self.audit._rate_sanity_out_of_scope_by_reason.get(
                'subcontractor_basis'
            ),
            1,
        )

    def test_r3_subcontractor_row_that_would_mismatch_is_excluded(
        self,
    ) -> None:
        """Same numbers as the incident row, but on a subcontractor
        sheet -- proves the gate excludes it, not the tolerance."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
            '__is_subcontractor': True,
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])

    def test_r4_vac_row_on_non_subcontractor_sheet_stays_in_scope(
        self,
    ) -> None:
        """Q5 decision record: VAC rows are not in the four
        subcontractor-variant names (pipeline/pricing.py L636-641), so
        a VAC row on a non-subcontractor sheet takes the same
        pass-through New-Rates basis as a primary row -- it stays IN
        scope. Excluding it would lose real detector coverage with no
        basis mismatch to justify the exclusion."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
            '__is_vac_crew': True,
            '__is_subcontractor': False,
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)

    def test_r5_vac_row_on_subcontractor_sheet_is_out_of_scope(
        self,
    ) -> None:
        """VAC rows on subcontractor sheets are excluded automatically
        by the ``__is_subcontractor`` gate -- no separate VAC rule
        needed."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
            '__is_vac_crew': True,
            '__is_subcontractor': True,
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(mismatches, [])

    def test_r6_fallback_disabled_without_snapshot_column_mapping(
        self,
    ) -> None:
        """F1 core: sheet 777's column_mapping has no Snapshot Date
        entry -> the weekly fallback never activates, fail closed to
        out-of-scope even though the weekly date is post-cutoff."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '',
            'Weekly Reference Logged Date': '2026-08-09',
            '__source_sheet_id': 777,
        }
        source_sheets = [{
            'id': 777,
            'name': 'Legacy No-Snapshot-Column Sheet',
            'column_mapping': {'Work Request #': 1},
        }]
        mismatches = self.audit._detect_rate_sanity_mismatches(
            [row], source_sheets=source_sheets
        )
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)
        self.assertEqual(
            self.audit._rate_sanity_out_of_scope_by_reason.get(
                'pre_cutoff_or_undated'
            ),
            1,
        )

    def test_r7_fallback_enabled_when_sheet_maps_snapshot_column(
        self,
    ) -> None:
        """Same row as R6, but sheet 777's column_mapping now DOES
        contain 'Snapshot Date' -> the fallback still rescues
        automation-lag rows."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '',
            'Weekly Reference Logged Date': '2026-08-09',
            '__source_sheet_id': 777,
        }
        source_sheets = [{
            'id': 777,
            'name': 'Legacy Sheet With Snapshot Column',
            'column_mapping': {'Snapshot Date': 1},
        }]
        mismatches = self.audit._detect_rate_sanity_mismatches(
            [row], source_sheets=source_sheets
        )
        self.assertEqual(len(mismatches), 1)

    def test_r8_unknown_sheet_fails_closed(self) -> None:
        """__source_sheet_id absent from the supplied source_sheets ->
        out of scope (fail closed), even with a post-cutoff weekly
        date and a blank snapshot."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '',
            'Weekly Reference Logged Date': '2026-08-09',
            '__source_sheet_id': 999999,
        }
        source_sheets = [{
            'id': 777,
            'name': 'A Different Sheet',
            'column_mapping': {'Snapshot Date': 1},
        }]
        mismatches = self.audit._detect_rate_sanity_mismatches(
            [row], source_sheets=source_sheets
        )
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)

    def test_r9_legacy_call_shape_without_source_sheets(self) -> None:
        """The snapshot branch needs no index -- omitting
        source_sheets entirely (the legacy call shape every
        pre-existing direct-call test in this file uses) must still
        flag a snapshot-dated post-cutoff mismatch."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
        }
        mismatches = self.audit._detect_rate_sanity_mismatches([row])
        self.assertEqual(len(mismatches), 1)

    def test_r10_out_of_scope_counter_equals_reason_breakdown_sum(
        self,
    ) -> None:
        """Counter contract: a mixed batch (one subcontractor row, one
        undatable row, one flagged incident row) run through
        ``audit_financial_data`` -> summary['rate_sanity_out_of_scope']
        is present under its original key name and equals the sum of
        the per-reason breakdown."""
        subcontractor_row = {
            'Work Request #': '1',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '1',
            'Units Total Price': '$49.66',
            'Snapshot Date': '2026-08-09',
            '__is_subcontractor': True,
        }
        undatable_row = {
            'Work Request #': '2',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
        }
        incident_row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
            '__is_subcontractor': False,
        }
        rows = [subcontractor_row, undatable_row, incident_row]
        with tempfile.TemporaryDirectory() as tmp_dir, \
                mock.patch.object(BillingAudit, '_save_audit_state'), \
                mock.patch.object(BillingAudit, '_log_to_audit_sheet'):
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                audit = BillingAudit(client=None, skip_cell_history=True)
                results = audit.audit_financial_data([], rows)
            finally:
                os.chdir(original_cwd)

        summary = results['summary']
        self.assertIn('rate_sanity_out_of_scope', summary)
        self.assertEqual(summary['rate_sanity_out_of_scope'], 2)
        self.assertEqual(
            summary['rate_sanity_out_of_scope'],
            sum(audit._rate_sanity_out_of_scope_by_reason.values()),
        )

    def test_r11_flag_off_blank_snapshot_stays_out_of_scope(self) -> None:
        """P2/#333 (RED): flag OFF, sheet 777 DOES map a Snapshot Date
        column, row has a blank Snapshot Date and a post-cutoff Weekly
        Reference Logged Date -> production's real gate
        (pipeline/fetch.py:389-403) would NOT recalculate this row, so
        the audit must not call it in scope either. Same fixture as
        R7, flag flipped. Fails on pre-fix code (today's gate ignores
        the flag entirely)."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '',
            'Weekly Reference Logged Date': '2026-08-09',
            '__source_sheet_id': 777,
        }
        source_sheets = [{
            'id': 777,
            'name': 'Legacy Sheet With Snapshot Column',
            'column_mapping': {'Snapshot Date': 1},
        }]
        with mock.patch.object(
            generate_weekly_pdfs, 'RATE_RECALC_WEEKLY_FALLBACK', False
        ):
            mismatches = self.audit._detect_rate_sanity_mismatches(
                [row], source_sheets=source_sheets
            )
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)
        self.assertEqual(
            self.audit._rate_sanity_out_of_scope_by_reason.get(
                'pre_cutoff_or_undated'
            ),
            1,
        )

    def test_r12_flag_off_snapshot_dated_row_stays_in_scope(self) -> None:
        """Over-correction guard: flag OFF, row carries a post-cutoff
        Snapshot Date -> still IN scope, exactly 1 mismatch. The flag
        gates only the weekly fallback branch;
        pipeline/utils.py:117-119 returns on the snapshot branch
        before the fallback branch is ever reached."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '2026-08-09',
            '__source_sheet_id': 777,
        }
        source_sheets = [{
            'id': 777,
            'name': 'Legacy Sheet With Snapshot Column',
            'column_mapping': {'Snapshot Date': 1},
        }]
        with mock.patch.object(
            generate_weekly_pdfs, 'RATE_RECALC_WEEKLY_FALLBACK', False
        ):
            mismatches = self.audit._detect_rate_sanity_mismatches(
                [row], source_sheets=source_sheets
            )
        self.assertEqual(len(mismatches), 1)

    def test_r13_flag_on_no_snapshot_column_stays_out_of_scope(
        self,
    ) -> None:
        """Conjunction guard: flag ON, sheet maps NO Snapshot Date
        column -> still out of scope. Pins AND, not OR, between the
        facade flag and the per-sheet column-mapping check."""
        row = {
            'Work Request #': '16881353',
            'CU': 'SAA-DE-20',
            'Work Type': 'Inst',
            'Quantity': '3',
            'Units Total Price': '$341.04',
            'Snapshot Date': '',
            'Weekly Reference Logged Date': '2026-08-09',
            '__source_sheet_id': 777,
        }
        source_sheets = [{
            'id': 777,
            'name': 'Legacy No-Snapshot-Column Sheet',
            'column_mapping': {'Work Request #': 1},
        }]
        with mock.patch.object(
            generate_weekly_pdfs, 'RATE_RECALC_WEEKLY_FALLBACK', True
        ):
            mismatches = self.audit._detect_rate_sanity_mismatches(
                [row], source_sheets=source_sheets
            )
        self.assertEqual(mismatches, [])
        self.assertEqual(self.audit._rate_sanity_out_of_scope, 1)
        self.assertEqual(
            self.audit._rate_sanity_out_of_scope_by_reason.get(
                'pre_cutoff_or_undated'
            ),
            1,
        )


if __name__ == '__main__':
    unittest.main()
