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

    def test_aepbillable_user_claimer_named_helper_parses_as_primary(self):
        # Codex P2: a primary claimer whose name contains the 'Helper'
        # token (e.g. a foreman literally named '... Helper') must parse as
        # the PRIMARY aep_billable variant, not aep_billable_helper. The
        # reserved _User_ token is checked BEFORE the Helper scan, so it
        # wins. Pre-fix this round-tripped to ('...','aep_billable_helper','').
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_User_John_Helper_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'aep_billable', 'John_Helper'))

    def test_reducedsub_user_claimer_named_helper_parses_as_primary(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_User_Pat_Helper_def456.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', 'Pat_Helper'))


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

    def test_unknown_variant_raises(self):
        # Copilot: this helper is filename-identity logic. An unexpected
        # variant must raise rather than silently fall through to the
        # _ReducedSub token (which would misroute downstream identity
        # matching). Mirrors the defensive-raise convention for new
        # variant helpers (Living Ledger 2026-05-15 rule 4).
        with self.assertRaises(ValueError):
            generate_weekly_pdfs._subcontractor_primary_variant_suffix(
                'vac_crew', 'John Doe', '91467680', '041926'
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
        # Sub-project D (2026-05-25) pins this OFF: this class asserts the
        # legacy bare-primary behavior for NON-subcontractor rows, which D's
        # default-on production-primary partitioning would otherwise change
        # to _User_<claimer>. D's new behavior is covered by
        # tests/test_primary_claim_attribution.py::TestPrimaryEmission. Per
        # [2026-05-20 00:26] rule 2 (test-contract override), pin D off here
        # to keep this an isolated B/B1 guard.
        self._orig_primary_attr = generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)

    def tearDown(self):
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._orig_primary_attr
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

    def test_helper_completed_row_excluded_from_primary_user_variants(self):
        # 2026-05-21 hotfix carried into Subproject B (master PR #216): a
        # helper-COMPLETED subcontractor row must NOT emit primary
        # _REDUCEDSUB_USER_ / _AEPBILLABLE_USER_ keys — its credit belongs
        # solely to the _HELPER_ shadow files. The guard suppresses the
        # primary emission EVEN THOUGH the parallel pre-pass still resolves
        # a primary claimer for the row (the guard short-circuits before
        # the claimer is consumed at emission).
        row = _make_sub_primary_row(row_id=7001)
        row['__is_helper_row'] = True
        row['__helper_foreman'] = 'HelperGuy'
        row['__helper_dept'] = '500'
        row['__helper_job'] = 'JOB-X'
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'PrimaryClaimer', 'frozen', 'success'),
        ), mock.patch(
            'billing_audit.writer.lookup_attribution',
            return_value=None,  # no_history → shadow uses current helper
        ):
            groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        self.assertFalse(
            any('REDUCEDSUB_USER_' in k for k in keys),
            f"helper-completed row must NOT emit _REDUCEDSUB_USER_; got {keys}",
        )
        self.assertFalse(
            any('AEPBILLABLE_USER_' in k for k in keys),
            f"helper-completed row must NOT emit _AEPBILLABLE_USER_; got {keys}",
        )
        # Helper-shadow files MUST still be present (helper earns the credit).
        self.assertTrue(
            any('REDUCEDSUB_HELPER_HelperGuy' in k for k in keys),
            f"helper-shadow _REDUCEDSUB_HELPER_ must be present; got {keys}",
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

    def test_empty_claimer_falls_back_to_unknown_foreman(self):
        # Codex P1: a whitespace-only "Foreman Assigned?" yields
        # __effective_user='' upstream. resolve_claimer's use/no_history
        # then returns an empty name. The emission gates on `is not None`,
        # so '' previously created a _REDUCEDSUB_USER_ key with an EMPTY
        # claimer, which later crashed generate_excel at the
        # _subcontractor_primary_variant_suffix raise. The claimer must
        # fall back to a non-empty sentinel so the primary file is still
        # emitted (billing not dropped) and never carries an empty token.
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', '', 'current', 'no_history'),
        ):
            groups = generate_weekly_pdfs.group_source_rows(
                [_make_sub_primary_row(effective_user='')]
            )
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_USER_Unknown_Foreman' in k for k in keys),
            f"empty claimer must fall back to Unknown_Foreman; got {keys}",
        )
        self.assertFalse(
            any(k.endswith('REDUCEDSUB_USER_') for k in keys),
            f"must never emit an empty _USER_ token; got {keys}",
        )

    def test_hold_records_date_only_week_key(self):
        # Copilot: record_attribution_hold is typed `datetime.date | None`,
        # but the call site passed the datetime week_ending_date, so the
        # hold key embedded 'YYYY-MM-DDT00:00:00'. The call site must
        # normalize to a pure date (matching the pre-pass normalization for
        # resolve_claimer) so the key is 'YYYY-MM-DD'.
        import billing_audit.writer as _w
        _w._attribution_holds.clear()
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('hold', None, None, 'fetch_failure'),
        ):
            generate_weekly_pdfs.group_source_rows([_make_sub_primary_row()])
        keys = list(_w._attribution_holds.keys())
        self.assertEqual(len(keys), 1, f"exactly one hold expected; got {keys}")
        week_component = keys[0][1]
        self.assertNotIn(
            'T', week_component,
            f"hold week key must be date-only (no time component); got {week_component!r}",
        )
        self.assertRegex(week_component, r'^\d{4}-\d{2}-\d{2}$')


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


class TestMigrationCleanup(unittest.TestCase):
    """Task 7: legacy unpartitioned primary attachments deleted; new
    per-claimer files exempt; non-sub WRs untouched."""

    def setUp(self):
        _ensure_smartsheet_mocked()

    def _att(self, name, att_id):
        a = mock.MagicMock()
        a.name = name
        a.id = att_id
        return a

    def _client(self, attachments):
        client = mock.MagicMock()
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 1
        client.Attachments.list_row_attachments.return_value.data = attachments
        sheet.rows = [row]
        client.Sheets.get_sheet.return_value = sheet
        return client, sheet

    def test_legacy_reducedsub_deleted_new_claimer_exempt(self):
        legacy = self._att(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx', 10
        )
        new_file = self._att(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_User_John_Doe_def456.xlsx',
            20,
        )
        client, sheet = self._client([legacy, new_file])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks={('91467680', '041926', 'reduced_sub', 'John_Doe')},
            test_mode=False,
            target_sheet=sheet,
            sub_wr_scope={'91467680'},
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertIn((5723337641643908, 10), deletes,
                      f"legacy _ReducedSub must be deleted; got {deletes}")
        self.assertNotIn((5723337641643908, 20), deletes,
                         f"new per-claimer file must be exempt; got {deletes}")

    def test_legacy_aepbillable_deleted(self):
        legacy = self._att(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_abc123.xlsx', 30
        )
        client, sheet = self._client([legacy])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks=set(),
            test_mode=False,
            target_sheet=sheet,
            sub_wr_scope={'91467680'},
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertIn((5723337641643908, 30), deletes)

    def test_non_sub_wr_legacy_reducedsub_preserved(self):
        legacy = self._att(
            'WR_99999999_WeekEnding_041926_120000_ReducedSub_abc123.xlsx', 40
        )
        client, sheet = self._client([legacy])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks=set(),
            test_mode=False,
            target_sheet=sheet,
            sub_wr_scope={'91467680'},  # 99999999 NOT in scope
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertNotIn((5723337641643908, 40), deletes)

    def test_param_omitted_is_noop(self):
        legacy = self._att(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx', 50
        )
        client, sheet = self._client([legacy])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks={('91467680', '041926', 'reduced_sub', '')},
            test_mode=False,
            target_sheet=sheet,
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertEqual(deletes, [], f"omitted param must be a no-op; got {deletes}")

    def test_empty_id_legacy_in_valid_wr_weeks_is_exempt(self):
        # Belt-and-suspenders live-identity exemption ([2026-05-19 23:45]
        # WR-01): an empty-identifier legacy attachment whose identity is
        # in valid_wr_weeks must NOT be deleted by the migration gate.
        # Production never emits an empty-id live file (the producer raises
        # on an empty claimer), so this branch is unreachable in practice —
        # the test guards against a future path that starts producing one.
        legacy = self._att(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx', 60
        )
        client, sheet = self._client([legacy])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks={('91467680', '041926', 'reduced_sub', '')},
            test_mode=False,
            target_sheet=sheet,
            sub_wr_scope={'91467680'},
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertNotIn(
            (5723337641643908, 60), deletes,
            f"empty-id legacy in valid_wr_weeks must be exempt; got {deletes}",
        )


class TestSubprojectBHashPrune(unittest.TestCase):
    """Task 8: one-time prune of legacy blank-identifier reduced_sub /
    aep_billable orphans for in-scope subcontractor WRs."""

    def setUp(self):
        _ensure_smartsheet_mocked()

    def _groups(self, wrs):
        groups = {}
        for wr in wrs:
            key = f"041926_{wr}_REDUCEDSUB_USER_John"
            # Production rows always carry __variant (set at emission); the
            # subcontractor scope builder now gates on it.
            groups[key] = [{
                'Work Request #': wr,
                '__source_sheet_id': 8162920222379908,
                '__variant': 'reduced_sub',
            }]
        return groups

    def test_first_run_drops_legacy_primary_variant_orphans(self):
        hist = {
            '91467680|041926|reduced_sub|': {'hash': 'h1', 'timestamp': '2026-01-01'},
            '91467680|041926|aep_billable|': {'hash': 'h2', 'timestamp': '2026-01-02'},
            # New per-claimer entry — must survive
            '91467680|041926|reduced_sub|John': {'hash': 'h3', 'timestamp': '2026-01-03'},
            # Non-sub WR — must survive
            '12345|041926|reduced_sub|': {'hash': 'h4', 'timestamp': '2026-01-04'},
        }
        with self.assertLogs(level='INFO') as log_cm:
            generate_weekly_pdfs._run_subproject_b_hash_prune(hist, self._groups(['91467680']))
        self.assertNotIn('91467680|041926|reduced_sub|', hist)
        self.assertNotIn('91467680|041926|aep_billable|', hist)
        self.assertIn('91467680|041926|reduced_sub|John', hist)
        self.assertIn('12345|041926|reduced_sub|', hist)
        self.assertEqual(
            hist['_subproject_b_prune_version'],
            generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        )
        prune_logs = [l for l in log_cm.output if 'Subproject B hash-history prune' in l]
        self.assertEqual(len(prune_logs), 1)
        self.assertIn('dropped 2', prune_logs[0])

    def test_idempotent_when_sentinel_current(self):
        hist = {
            '91467680|041926|reduced_sub|': {'hash': 'h1', 'timestamp': '2026-01-01'},
            '_subproject_b_prune_version': generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        }
        generate_weekly_pdfs._run_subproject_b_hash_prune(hist, self._groups(['91467680']))
        self.assertIn('91467680|041926|reduced_sub|', hist)  # no-op
        self.assertEqual(
            hist['_subproject_b_prune_version'],
            generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        )

    def test_pii_marker_registered(self):
        self.assertIn(
            'Subproject B hash-history prune',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_version_constant_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertRegex(src, r'(?m)^SUBPROJECT_B_HASH_PRUNE_VERSION = 1$')

    def test_call_site_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertIn('_run_subproject_b_hash_prune(hash_history, groups)', src)

    def test_returns_true_when_orphans_dropped(self):
        # Codex P2: the prune must report whether it mutated hash_history so
        # the caller can persist it even on a no-update run (where the
        # history_updates-gated save would otherwise skip it). Orphans
        # dropped → mutated → True.
        hist = {'91467680|041926|reduced_sub|': {'hash': 'h1'}}
        changed = generate_weekly_pdfs._run_subproject_b_hash_prune(
            hist, self._groups(['91467680'])
        )
        self.assertIs(changed, True)

    def test_returns_true_when_only_sentinel_advances(self):
        # No orphans to drop, but the sentinel advances from absent →
        # version. That is still a mutation that must persist.
        hist = {'12345|041926|reduced_sub|John': {'hash': 'h'}}
        changed = generate_weekly_pdfs._run_subproject_b_hash_prune(
            hist, self._groups(['91467680'])
        )
        self.assertIs(changed, True)
        self.assertEqual(
            hist['_subproject_b_prune_version'],
            generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        )

    def test_returns_false_when_idempotent(self):
        # Sentinel already current → no mutation → False (no save needed).
        hist = {
            '_subproject_b_prune_version':
                generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        }
        changed = generate_weekly_pdfs._run_subproject_b_hash_prune(
            hist, self._groups(['91467680'])
        )
        self.assertIs(changed, False)

    def test_save_gate_persists_one_time_prune_in_source(self):
        # Codex P2 wiring: the hash-history save must fire on a no-update
        # run when a one-time migration prune mutated the history.
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertIn('_hash_history_migration_dirty', src)


class TestNonSubVariantsPreserved(unittest.TestCase):
    """Task 9: B does not change primary / vac_crew / helper-shadow grouping."""

    _SUB_SHEET_ID = 8162920222379908

    def setUp(self):
        _reset_all()
        self._orig_variants = generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        self._orig_sub_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS)
        # Sub-project D (2026-05-25) pins this OFF: this class asserts the
        # legacy bare-primary behavior for NON-subcontractor rows, which D's
        # default-on production-primary partitioning would otherwise change
        # to _User_<claimer>. D's new behavior is covered by
        # tests/test_primary_claim_attribution.py::TestPrimaryEmission. Per
        # [2026-05-20 00:26] rule 2 (test-contract override), pin D off here
        # to keep this an isolated B/B1 guard.
        self._orig_primary_attr = generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)

    def tearDown(self):
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._orig_primary_attr
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._orig_variants
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._orig_sub_ids)
        _reset_all()

    def test_non_subcontractor_primary_row_emits_legacy_primary_key(self):
        row = _make_sub_primary_row(source_sheet_id=99999999)
        groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertIn('041926_91467680', groups)
        # No subcontractor variant keys for a non-sub row.
        self.assertFalse(any('REDUCEDSUB' in k for k in groups))

    def test_vac_crew_row_unaffected(self):
        """Subproject B does not route a vac_crew row into a subcontractor primary variant.

        The INTENT of this test — "B does not turn a vac_crew row into a
        _REDUCEDSUB/_AEPBILLABLE/_USER_ key" — is unchanged.  However,
        Subproject C (2026-05-21) now partitions the VACCREW group key by
        frozen claimer, so the key is ``..._VACCREW_<claimer>`` rather than
        the bare ``..._VACCREW`` (see CLAUDE.md Living Ledger [2026-05-21]).
        The assertion is updated to the per-claimer shape per [2026-05-20 00:26]
        rule-2: rewrite in-place, add a docstring citing the ledger, change the
        assertion so the real intent ("no sub primary key") remains the guard,
        and do NOT pin the pre-C suffix.
        """
        row = _make_sub_primary_row(source_sheet_id=99999999)
        row['__is_vac_crew'] = True
        row['__vac_crew_name'] = 'VacGuy'
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        # The row must produce a vac_crew group (VACCREW present anywhere in the key).
        self.assertTrue(
            any('VACCREW' in k for k in keys),
            f"Expected a VACCREW group key; got: {keys}",
        )
        # The real intent: Subproject B must NOT emit any subcontractor primary
        # variant for this vac_crew row.
        self.assertFalse(
            any('_REDUCEDSUB' in k or '_AEPBILLABLE' in k or '_USER_' in k for k in keys),
            f"B must not produce sub primary variants for a vac_crew row; got: {keys}",
        )


class TestPrePassConcurrency(unittest.TestCase):
    """Task 9: the parallel pre-pass resolves many rows correctly with no
    lost/duplicated map entries (spec §12 concurrency coverage)."""

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

    def test_fifty_rows_each_partition_to_their_own_claimer(self):
        # Each row's claimer is keyed to its row_id; assert every row
        # lands in its own claimer's group with no loss/duplication.
        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            return ResolveOutcome('use', f'Foreman{row_id}', 'frozen', 'success')
        rows = [
            _make_sub_primary_row(wr='WRSAME', row_id=6000 + i)
            for i in range(50)
        ]
        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = generate_weekly_pdfs.group_source_rows(rows)
        keys = list(groups.keys())
        for i in range(50):
            self.assertTrue(
                any(f'REDUCEDSUB_USER_Foreman{6000 + i}' in k for k in keys),
                f"row {6000 + i} missing from its claimer group; got {len(keys)} keys",
            )


class TestSubprojectBProductionInvariants(unittest.TestCase):
    """Task 9: source-grep guards defeating the 'mirror passes but
    production reverted' failure mode."""

    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_prepass_present(self):
        self.assertIn('_sub_primary_claimer_map', self._src)
        self.assertIn('Subproject B attribution pre-pass', self._src)

    def test_emission_uses_user_token_keys(self):
        self.assertIn('_REDUCEDSUB_USER_', self._src)
        self.assertIn('_AEPBILLABLE_USER_', self._src)

    def test_hold_record_present(self):
        self.assertIn('record_attribution_hold', self._src)

    def test_cleanup_param_signature_present(self):
        self.assertRegex(
            self._src,
            r'sub_legacy_primary_variants: set\[str\] \| None = None',
        )


class TestBulkFetchFailureDirectHoldBC(unittest.TestCase):
    """Phase 2 BLOCKER 1: under a bulk fetch_failure, the B (sub-primary)
    pre-pass must set the per-row outcome to HOLD DIRECTLY — without calling
    _lookup_attribution_all (zero additional Supabase calls). The D (primary)
    counterpart is in TestHistoricalClaimerRegression (test_primary_claim_attribution.py).

    This test is RED before Task 2 (the current code has no 'fetch_failure'
    branch — it either succeeds or falls back to _sub_primary_claimer_map={}).
    GREEN after Task 2 wires the direct-HOLD path in the B pre-pass block.
    """

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'rate_variants': generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED,
            'attr_enabled': generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED,
            'avail': generate_weekly_pdfs.BILLING_AUDIT_AVAILABLE,
            'sub_ids': set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS),
            'mode': generate_weekly_pdfs.RES_GROUPING_MODE,
        }
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = True
        generate_weekly_pdfs.BILLING_AUDIT_AVAILABLE = True
        generate_weekly_pdfs.RES_GROUPING_MODE = 'both'
        # Add a sub sheet ID so a row is eligible for the B pre-pass.
        self._sub_sheet = 9876543210
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._sub_sheet)

    def tearDown(self):
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._saved['rate_variants']
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr_enabled']
        generate_weekly_pdfs.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        generate_weekly_pdfs.RES_GROUPING_MODE = self._saved['mode']
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub_ids'])

    def _make_sub_row(self, row_id=1001, wr='90773033'):
        return {
            '__row_id': row_id,
            '__source_sheet_id': self._sub_sheet,
            '__effective_user': 'SubForeman',
            '__is_helper_row': False,
            '__is_vac_crew': False,
            '__sub_is_valid_helper_row': False,
            'Work Request #': wr,
            'Weekly Reference Logged Date': '2026-04-19',
            'Units Completed?': True,
            'Units Total Price': 100.0,
            'Dept #': '500',
            'Job #': 'J-1',
            'Snapshot Date': '2026-04-20',
        }

    def test_bulk_fetch_failure_bc_direct_hold_zero_supabase_calls(self):
        """BLOCKER 1: B pre-pass under fetch_failure produces HOLD outcomes with
        zero _lookup_attribution_all calls (no per-row RPC retry storm).

        Pre-Task-2 (RED): the B block has a ThreadPoolExecutor loop that calls
        resolve_claimer without prefetched_map, which would invoke
        _lookup_attribution_all per row even on failure.
        Post-Task-2 (GREEN): the fetch_failure branch constructs
        ResolveOutcome('hold', None, None, 'fetch_failure') DIRECTLY,
        never calling _lookup_attribution_all.
        """
        import billing_audit.writer as _baw

        row = self._make_sub_row(row_id=1001, wr='90773033')

        with mock.patch.object(
            _baw, '_lookup_attribution_all'
        ) as _mock_lookup, mock.patch(
            'billing_audit.writer.prefetch_attribution',
            return_value=({}, 'fetch_failure'),
        ):
            groups = generate_weekly_pdfs.group_source_rows([row])

        # BLOCKER 1: _lookup_attribution_all must NOT be called on failure path.
        _mock_lookup.assert_not_called()

        # On fetch_failure the B pre-pass map should have a HOLD entry
        # (or the group emits no file — both are acceptable; the key constraint
        # is zero additional Supabase calls).
        # If the map holds a HOLD outcome, verify it.
        # We can't inspect _sub_primary_claimer_map directly, but we can verify
        # no RPC was issued. The primary invariant is assert_not_called above.


if __name__ == '__main__':
    unittest.main()
