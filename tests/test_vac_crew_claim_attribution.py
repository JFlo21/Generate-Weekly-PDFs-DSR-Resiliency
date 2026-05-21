"""Subproject C — VAC Crew claim attribution tests.

Drives real production code paths (parser, group_source_rows pre-pass +
emission, generate_excel, migration cleanup, hash prune, HOLD wiring) per
the [2026-05-20 00:26] rule 4: row-flow changes require TRUE end-to-end
tests, not static mirrors.
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


class TestVacCrewConfigFlags(unittest.TestCase):
    def test_attribution_flag_exists_and_is_bool(self):
        self.assertIsInstance(
            generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED, bool
        )

    def test_attribution_flag_default_on(self):
        # Env var unset in the test harness → default '1' → True.
        self.assertTrue(generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED)

    def test_legacy_cleanup_flag_exists_and_is_bool(self):
        self.assertIsInstance(
            generate_weekly_pdfs.VAC_CREW_LEGACY_CLEANUP_ENABLED, bool
        )

    def test_legacy_cleanup_flag_default_on(self):
        self.assertTrue(generate_weekly_pdfs.VAC_CREW_LEGACY_CLEANUP_ENABLED)

    def test_flags_pinned_in_workflow(self):
        wf = (_REPO_ROOT / ".github/workflows/weekly-excel-generation.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("VAC_CREW_CLAIM_ATTRIBUTION_ENABLED", wf)
        self.assertIn("VAC_CREW_LEGACY_CLEANUP_ENABLED", wf)


class TestVacCrewSuffixAndParser(unittest.TestCase):
    def test_suffix_embeds_name(self):
        self.assertEqual(
            generate_weekly_pdfs._vac_crew_variant_suffix('John Smith', '91467680', '041926'),
            '_VacCrew_John_Smith',
        )

    def test_suffix_empty_claimer_raises(self):
        with self.assertRaises(ValueError):
            generate_weekly_pdfs._vac_crew_variant_suffix('', '91467680', '041926')

    def test_parser_vaccrew_name_round_trips(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_John_Smith_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', 'John_Smith'),
        )

    def test_parser_name_containing_helper_token_stays_vac_crew(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_Pat_Helper_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', 'Pat_Helper'),
        )

    def test_parser_legacy_vaccrew_no_name(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', ''),
        )

    def test_suffix_truncates_long_name_and_round_trips(self):
        long_name = 'A' * 60
        suffix = generate_weekly_pdfs._vac_crew_variant_suffix(long_name, '91467680', '041926')
        self.assertEqual(suffix, '_VacCrew_' + 'A' * 50)
        fname = f'WR_91467680_WeekEnding_041926_120000{suffix}_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', 'A' * 50),
        )


def _make_vac_row(row_id=6001, wr='91467680', name='CurrentCrew', snapshot='2026-04-19'):
    return {
        '__row_id': row_id,
        'Work Request #': wr,
        'Weekly Reference Logged Date': '2026-04-19',
        'Snapshot Date': snapshot,
        'Units Completed?': True,
        'Units Total Price': '$100.00',
        'CU': 'ANC-M', 'Work Type': 'Inst', 'Quantity': 2,
        '__effective_user': 'PrimaryForeman',
        '__is_helper_row': False, '__helper_foreman': '', '__helper_dept': '', '__helper_job': '',
        '__is_vac_crew': True,
        '__vac_crew_name': name, '__vac_crew_dept': '700', '__vac_crew_job': 'VJ-1',
        '__source_sheet_id': 8162920222379908,
    }


class TestVacCrewPrePassConcurrency(unittest.TestCase):
    def setUp(self):
        _reset_all()
        self._orig = generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = self._orig
        _reset_all()

    def test_fifty_rows_each_partition_to_their_own_claimer(self):
        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            return ResolveOutcome('use', f'Crew{row_id}', 'frozen', 'success')
        rows = [_make_vac_row(row_id=7000 + i) for i in range(50)]
        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = generate_weekly_pdfs.group_source_rows(rows)
        keys = list(groups.keys())
        for i in range(50):
            self.assertTrue(
                any(f'VACCREW_Crew{7000 + i}' in k for k in keys),
                f"row {7000+i} must partition to its own claimer; got {keys[:5]}…",
            )


class TestVacCrewEmission(unittest.TestCase):
    def setUp(self):
        _reset_all()
        self._orig = generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = self._orig
        _reset_all()

    def test_frozen_claimer_partitions(self):
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('use', 'FrozenCrew', 'frozen', 'success')):
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row()])
        self.assertTrue(any('VACCREW_FrozenCrew' in k for k in groups))

    def test_no_history_falls_back_to_current_name(self):
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('use', 'CurrentCrew', 'current', 'no_history')):
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row(name='CurrentCrew')])
        self.assertTrue(any('VACCREW_CurrentCrew' in k for k in groups))

    def test_hold_suppresses_and_records(self):
        from billing_audit.writer import get_counters
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('hold', None, None, 'fetch_failure')):
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row()])
        self.assertFalse(any('VACCREW' in k for k in groups))
        self.assertEqual(get_counters()['attribution_rows_held'], 1)

    def test_disabled_emits_exact_legacy_key(self):
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = False
        with mock.patch('billing_audit.writer.resolve_claimer') as m:
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row(name='CurrentCrew')])
            m.assert_not_called()
        self.assertIn('041926_91467680_VACCREW', groups)
        self.assertFalse(any('VACCREW_' in k for k in groups))

    def test_map_miss_uses_current_name_not_hold(self):
        from billing_audit.writer import get_counters
        row = _make_vac_row()
        del row['__row_id']
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('use', 'X', 'frozen', 'success')):
            groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertTrue(any('VACCREW_CurrentCrew' in k for k in groups))
        self.assertEqual(get_counters()['attribution_rows_held'], 0)


class TestVacCrewIdentitySitesAndDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_current_keys_site_carries_vac_claimer(self):
        # Site 3: the hash-prune current_keys reconstruction must derive the
        # vac_crew identifier from __current_foreman, not hard-code ''.
        self.assertNotRegex(
            self._src,
            r"_variant == 'vac_crew':\s*\n\s*_ident = ''",
            "current_keys must derive vac_crew identifier from the claimer",
        )

    def test_main_loop_identity_site_carries_vac_claimer(self):
        # Site 1: the main-loop identifier/history_key for vac_crew must
        # derive from __current_foreman, not hard-code '' (else the hash
        # entry is stale-pruned every run → permanent regeneration churn).
        self.assertNotRegex(
            self._src,
            r"variant == 'vac_crew':\s*\n\s*# VAC Crew variant: no sub-identifier",
            "Site 1 main-loop must not use the old 'no sub-identifier' comment (legacy blank pattern)",
        )
        self.assertNotRegex(
            self._src,
            r"variant == 'vac_crew':[^\n]*\n[^\n]*\n\s*identifier = ''",
            "Site 1 main-loop identifier must not hard-code '' for vac_crew",
        )

    def test_generate_excel_vac_crew_file_named_by_claimer(self):
        import datetime as dt, tempfile, openpyxl
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        orig = generate_weekly_pdfs.OUTPUT_FOLDER
        generate_weekly_pdfs.OUTPUT_FOLDER = tmp.name
        self.addCleanup(lambda: setattr(generate_weekly_pdfs, 'OUTPUT_FOLDER', orig))
        row = {
            'Work Request #': '91467680', 'Units Completed?': True,
            'Units Total Price': '$100.00', 'Customer Name': 'Cust',
            'Dept #': '500', 'Job #': 'J-1', 'CU': 'ANC-M', 'Work Type': 'Inst', 'Quantity': 2,
            '__variant': 'vac_crew', '__current_foreman': 'FrozenCrew',
            '__vac_crew_name': 'CurrentCrew', '__vac_crew_dept': '700', '__vac_crew_job': 'VJ-1',
            '__week_ending_date': dt.datetime(2026, 4, 19),
        }
        result = generate_weekly_pdfs.generate_excel(
            '041926_91467680_VACCREW_FrozenCrew', [row], dt.datetime(2026, 4, 19),
            data_hash='deadbeefcafe0c01',
        )
        excel_path, filename = result[0], result[1]
        self.assertIn('_VacCrew_FrozenCrew', filename)
        wb = openpyxl.load_workbook(excel_path)
        ws = wb.active
        foreman = next(
            (ws.cell(row=r, column=7).value for r in range(1, ws.max_row + 1)
             if ws.cell(row=r, column=6).value == 'Foreman:'),
            None,
        )
        self.assertEqual(foreman, 'FrozenCrew')  # display = attributed claimer
