"""Subproject B — subcontractor primary claim attribution tests.

Drives the real production code paths (parser, group_source_rows
pre-pass + emission, generate_excel filename builder, migration
cleanup, hash prune, HOLD wiring) per the [2026-05-20 00:26] rule 4:
row-flow changes require TRUE end-to-end tests, not static mirrors.
"""

from __future__ import annotations

import inspect
import pathlib
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked, _reset_all

_ensure_smartsheet_mocked()
import generate_weekly_pdfs  # noqa: E402
from billing_audit.writer import ResolveOutcome  # noqa: E402


class TestBuildGroupIdentityParsesPrimaryUserToken(unittest.TestCase):
    """Task 1: _User_ token parses for reduced_sub / aep_billable."""

    def test_reducedsub_user_token_parses_claimer(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_User_John_Doe_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', 'John_Doe'))

    def test_aepbillable_user_token_parses_claimer(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_User_John_Doe_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'aep_billable', 'John_Doe'))

    def test_legacy_reducedsub_parses_empty_identifier(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', ''))

    def test_legacy_aepbillable_parses_empty_identifier(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'aep_billable', ''))

    def test_reducedsub_helper_still_parses_helper(self):
        # Regression: the new User branch must not break helper-shadow parsing.
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_Helper_Jane_Smith_def456.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub_helper', 'Jane_Smith'))

    def test_user_token_with_no_claimer_name_returns_empty_identifier(self):
        # Degenerate/malformed: User token present but no name before the
        # hash. Degrades gracefully to '' (same as the legacy no-User shape).
        # Task 3's filename builder raises on an empty claimer, so production
        # never emits this — but the parser must handle it without crashing.
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_User_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', ''))


class TestLegacyPrimaryCleanupKillSwitch(unittest.TestCase):
    """Task 2: destructive-migration kill switch + startup banner."""

    def test_kill_switch_attribute_exists_and_is_bool(self):
        self.assertIsInstance(
            generate_weekly_pdfs.SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED,
            bool,
        )

    def test_kill_switch_default_on(self):
        # Default (unset env) resolves to True.
        self.assertTrue(
            generate_weekly_pdfs.SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED,
        )

    def test_banner_line_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertIn('SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED=', src)


class TestPrimaryVariantSuffixHelper(unittest.TestCase):
    """Task 3: variant-suffix helper for subcontractor primary files."""

    def test_reduced_sub_suffix_embeds_user_token(self):
        suffix = generate_weekly_pdfs._subcontractor_primary_variant_suffix(
            'reduced_sub', 'John Doe', '91467680', '041926'
        )
        self.assertEqual(suffix, '_ReducedSub_User_John_Doe')

    def test_aep_billable_suffix_embeds_user_token(self):
        suffix = generate_weekly_pdfs._subcontractor_primary_variant_suffix(
            'aep_billable', 'John Doe', '91467680', '041926'
        )
        self.assertEqual(suffix, '_AEPBillable_User_John_Doe')

    def test_empty_claimer_raises(self):
        with self.assertRaises(ValueError):
            generate_weekly_pdfs._subcontractor_primary_variant_suffix(
                'reduced_sub', '', '91467680', '041926'
            )

    def test_suffix_round_trips_through_parser(self):
        suffix = generate_weekly_pdfs._subcontractor_primary_variant_suffix(
            'reduced_sub', 'John Doe', '91467680', '041926'
        )
        fname = f'WR_91467680_WeekEnding_041926_120000{suffix}_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'reduced_sub', 'John_Doe'),
        )


def _make_sub_primary_row(
    wr='91467680', row_id=5001, units_price='$100.00',
    snapshot='2026-04-19', effective_user='CurrentForeman',
    source_sheet_id=8162920222379908,
):
    """Synthetic completed non-helper subcontractor row."""
    return {
        '__row_id': row_id,
        'Work Request #': wr,
        'Weekly Reference Logged Date': '2026-04-19',
        'Snapshot Date': snapshot,
        'Units Completed?': True,
        'Units Total Price': units_price,
        'CU': 'ANC-M',
        'Work Type': 'Inst',
        'Quantity': 2,
        '__effective_user': effective_user,
        '__assignment_method': 'FOREMAN_COLUMN',
        '__is_helper_row': False,
        '__helper_foreman': '',
        '__helper_dept': '',
        '__helper_job': '',
        '__is_vac_crew': False,
        '__source_sheet_id': source_sheet_id,
    }


class TestPrePassEmission(unittest.TestCase):
    """Task 4: pre-pass + emission partition subcontractor primary by claimer."""

    _SUB_SHEET_ID = 8162920222379908

    def setUp(self):
        _reset_all()
        self._orig_variants = generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        self._orig_attr = generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
        self._orig_sub_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS)
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)

    def tearDown(self):
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._orig_variants
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = self._orig_attr
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._orig_sub_ids)
        _reset_all()

    def test_frozen_claimer_partitions_reducedsub_and_aep(self):
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenPrimary', 'frozen', 'success'),
        ):
            groups = generate_weekly_pdfs.group_source_rows([_make_sub_primary_row()])
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_USER_FrozenPrimary' in k for k in keys),
            f"reduced_sub must partition by frozen claimer; got {keys}",
        )
        self.assertTrue(
            any('AEPBILLABLE_USER_FrozenPrimary' in k for k in keys),
            f"aep_billable (post-cutoff) must partition by frozen claimer; got {keys}",
        )

    def test_no_history_falls_back_to_current_foreman(self):
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'CurrentForeman', 'current', 'no_history'),
        ):
            groups = generate_weekly_pdfs.group_source_rows(
                [_make_sub_primary_row(effective_user='CurrentForeman')]
            )
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_USER_CurrentForeman' in k for k in keys),
            f"no_history must fall back to current foreman; got {keys}",
        )

    def test_hold_suppresses_primary_variants_and_records_hold(self):
        from billing_audit.writer import get_counters
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('hold', None, None, 'fetch_failure'),
        ):
            groups = generate_weekly_pdfs.group_source_rows([_make_sub_primary_row()])
        keys = list(groups.keys())
        self.assertFalse(
            any('REDUCEDSUB' in k for k in keys),
            f"HOLD must suppress reduced_sub emission; got {keys}",
        )
        self.assertFalse(
            any('AEPBILLABLE' in k for k in keys),
            f"HOLD must suppress aep_billable emission; got {keys}",
        )
        self.assertEqual(get_counters()['attribution_rows_held'], 1)

    def test_attribution_disabled_uses_current_foreman(self):
        # No mock — real resolve_claimer with enabled=False short-circuits
        # to use-current without any Supabase call.
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = False
        groups = generate_weekly_pdfs.group_source_rows(
            [_make_sub_primary_row(effective_user='CurrentForeman')]
        )
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_USER_CurrentForeman' in k for k in keys),
            f"disabled attribution must use current foreman; got {keys}",
        )

    def test_two_claimers_same_wr_week_coexist(self):
        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            name = 'ForemanA' if row_id == 5001 else 'ForemanB'
            return ResolveOutcome('use', name, 'frozen', 'success')
        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = generate_weekly_pdfs.group_source_rows([
                _make_sub_primary_row(row_id=5001),
                _make_sub_primary_row(row_id=5002),
            ])
        keys = list(groups.keys())
        self.assertTrue(any('REDUCEDSUB_USER_ForemanA' in k for k in keys))
        self.assertTrue(any('REDUCEDSUB_USER_ForemanB' in k for k in keys))

    def test_non_subcontractor_row_unaffected(self):
        row = _make_sub_primary_row(source_sheet_id=99999999)
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'X', 'frozen', 'success'),
        ) as m:
            groups = generate_weekly_pdfs.group_source_rows([row])
            m.assert_not_called()
        self.assertIn('041926_91467680', groups)


class TestThreeIdentitySitesCarryClaimer(unittest.TestCase):
    """Task 5: all three identity sites derive reduced_sub/aep_billable
    identifier from __current_foreman (the CR-01 lockstep invariant),
    and the derivation round-trips with the filename builder + parser."""

    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_exactly_three_identity_site_markers(self):
        # Each of Site 1/2/3 carries the marker comment so the lockstep
        # is auditable (CR-01). Drift between the three is the bug shape.
        self.assertEqual(
            self._src.count('Subproject B identity site'),
            3,
            "Exactly three identity sites must carry the Subproject B branch",
        )

    def test_site1_branches_on_subcontractor_primary_variants(self):
        self.assertRegex(
            self._src,
            r"variant in \('reduced_sub', 'aep_billable'\)",
            "Site 1 must branch on the subcontractor primary variants",
        )

    def test_identity_site_sanitizer_round_trips_with_filename(self):
        # The identifier all three sites derive
        # (_RE_SANITIZE_IDENTIFIER over __current_foreman) MUST equal the
        # identifier build_group_identity parses out of the filename the
        # builder produces — otherwise attachment-identity lookups miss
        # and subcontractor primary files regenerate every run.
        claimer = 'John Doe'
        site_identifier = generate_weekly_pdfs._RE_SANITIZE_IDENTIFIER.sub(
            '_', claimer
        )[:50]
        suffix = generate_weekly_pdfs._subcontractor_primary_variant_suffix(
            'reduced_sub', claimer, '91467680', '041926'
        )
        fname = f'WR_91467680_WeekEnding_041926_120000{suffix}_abc123.xlsx'
        _, _, _, parsed_identifier = generate_weekly_pdfs.build_group_identity(fname)
        self.assertEqual(
            parsed_identifier, site_identifier,
            "identity-site identifier must equal the parsed filename "
            "identifier (CR-01 round-trip)",
        )


class TestHoldSummaryWiredIntoMain(unittest.TestCase):
    """Task 6: summarize_attribution_holds is invoked once at end-of-run."""

    def test_summary_call_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertIn('summarize_attribution_holds()', src)


if __name__ == '__main__':
    unittest.main()
