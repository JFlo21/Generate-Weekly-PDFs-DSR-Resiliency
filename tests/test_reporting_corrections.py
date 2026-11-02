"""Reporting corrections (pipeline/reporting_corrections.py).

Synthetic fixture only (tests/_reporting_corrections_fixture.py): fake
people, fake WR numbers, fake sheet/row ids. Evidence label: FIXTURE
PASS -- not a dry run, not production observed.
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import openpyxl  # noqa: E402

import generate_weekly_pdfs  # noqa: E402
import pipeline.discovery as _discovery  # noqa: E402
import pipeline.fetch as _fetch  # noqa: E402
import pipeline.orchestrate as _orchestrate  # noqa: E402
from pipeline import config as _config  # noqa: E402
from pipeline import reporting_corrections as rc  # noqa: E402
from tests import _reporting_corrections_fixture as fx  # noqa: E402

# Feature-off group keys / hashes / row ids computed on a pristine
# export of the base commit (git archive HEAD before this change) with
# the same fixture -- the byte-identical "today" oracle.
_GOLDEN = {
    True: {
        '030826_90000001_HELPER2_Helper2_C': ['34d6c33f90b1434a', [106]],
        '030826_90000001_HELPER_Helper_H': [
            'fda4a878ba60b64a', [104, 105, 107]],
        '030826_90000001_USER_Foreman_A': [
            '39604a918005a9f4', [101, 102, 103]],
        '030826_90000002_USER_Foreman_A': ['4974a94ebd9ee191', [201]],
    },
    False: {
        '030826_90000001_HELPER2_Helper2_C': ['cf5dd50cec5d5dca', [106]],
        '030826_90000001_HELPER_Helper_H': [
            '21462a3b92883ade', [104, 105, 107]],
        '030826_90000001_USER_Foreman_A': [
            '63229efec9a9221d', [101, 102, 103]],
        '030826_90000002_USER_Foreman_A': ['62c5d6453e0da85d', [201]],
    },
}
_CORRECTED = (101, 102, 104, 105, 106, 108)
_DAY_RE = re.compile(r'^(\w+day) \((\d\d/\d\d/\d{4})\)$')


def _snapshot(groups):
    return {
        k: [generate_weekly_pdfs.calculate_data_hash(v),
            sorted(r['__row_id'] for r in v)]
        for k, v in sorted(groups.items())
    }


class _Base(unittest.TestCase):

    def setUp(self):
        for target, name, value in (
            (_discovery, '_FOLDER_DISCOVERED_SUB_IDS', frozenset()),
            (_config, 'REPORTING_CORRECTIONS_FILE', None),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        saved_ext = generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION
        self.addCleanup(setattr, generate_weekly_pdfs,
                        'EXTENDED_CHANGE_DETECTION', saved_ext)
        rc.reset_state()
        self.addCleanup(rc.reset_state)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _configure(self, doc):
        path = os.path.join(self._tmp.name, f'c{id(doc)}.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(doc, fh)
        _config.REPORTING_CORRECTIONS_FILE = path
        rc.reset_state()
        return path

    def _run(self, doc=None, rows=None):
        """fetch-recovery + prepare_run + grouping, like main() does."""
        if doc is not None:
            self._configure(doc)
        rows = rows if rows is not None else fx.admitted_rows()
        recovered = fx.recovered_row()
        stamps = rc.recovery_for_row(recovered, fx.SHEET, 108)
        if stamps:
            recovered.update(stamps)
            rows.append(recovered)
        summary = rc.prepare_run(
            rows, group_fn=generate_weekly_pdfs.group_source_rows)
        groups = generate_weekly_pdfs.group_source_rows(rows)
        return groups, summary


class LoaderValidationTests(_Base):

    def _problems(self, doc):
        with self.assertRaises(rc.CorrectionError) as cm:
            rc.parse_corrections(doc)
        return ' | '.join(cm.exception.problems)

    def test_valid_fixture_and_template_parse(self):
        cset = rc.parse_corrections(fx.correction_doc())
        self.assertEqual(len(cset.by_row), 6)
        template = _REPO_ROOT / 'docs' / 'templates' / (
            'reporting_corrections.template.json')
        tset = rc.load_corrections(str(template))
        self.assertTrue(tset.corrections)

    def test_rejects_bad_fields(self):
        doc = fx.correction_doc()
        corr = doc['corrections'][0]
        corr['revision'] = 0
        corr['rows'][0]['credit']['variant'] = 'boss'
        corr['rows'][3]['credit']['dept'] = None
        corr['rows'][1]['workday'] = '2026-03-12'
        del corr['rows'][2]['expect']['pole']
        text = self._problems(doc)
        for needle in ('revision must be', 'credit.variant',
                       'credit.dept is required', 'outside the reporting',
                       "missing ['pole']"):
            self.assertIn(needle, text)

    def test_rejects_schema_and_duplicate_rows(self):
        doc = fx.correction_doc()
        doc['schema'] = 2
        self.assertIn('schema must be 1', self._problems(doc))
        doc = fx.correction_doc()
        doc['corrections'][0]['rows'].append(
            copy.deepcopy(doc['corrections'][0]['rows'][0]))
        self.assertIn('more than once', self._problems(doc))

    def test_overlap_needs_superseding_revision(self):
        doc = fx.correction_doc()
        second = copy.deepcopy(doc['corrections'][0])
        second['id'] = 'another-id'
        doc['corrections'].append(second)
        self.assertIn('overlapping corrections', self._problems(doc))
        doc = fx.correction_doc()
        newer = copy.deepcopy(doc['corrections'][0])
        newer['revision'] = 2
        doc['corrections'].append(newer)
        cset = rc.parse_corrections(doc)
        self.assertEqual([c.revision for c in cset.corrections], [2])

    def test_recovery_requires_null_dates(self):
        doc = fx.correction_doc()
        doc['corrections'][0]['rows'][0]['recover_missing_dates'] = True
        self.assertIn('requires both expected', self._problems(doc))

    def test_invalid_file_means_feature_off(self):
        path = os.path.join(self._tmp.name, 'bad.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{"schema": 1, "corrections": []}')
        _config.REPORTING_CORRECTIONS_FILE = path
        with self.assertLogs(level='ERROR'):
            self.assertIsNone(rc.get_active_set())
        rows = fx.admitted_rows()
        self.assertEqual(rc.prepare_run(rows, group_fn=None), {})


class FeatureOffGoldenTests(_Base):

    def test_feature_off_is_byte_identical_to_base(self):
        for extended in (True, False):
            generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = extended
            rows = fx.admitted_rows()
            self.assertEqual(rc.prepare_run(rows, group_fn=None), {})
            self.assertIsNone(rc.recovery_for_row(
                fx.recovered_row(), fx.SHEET, 108))
            groups = generate_weekly_pdfs.group_source_rows(rows)
            self.assertEqual(_snapshot(groups), _GOLDEN[extended])
            for grows in groups.values():
                for row in grows:
                    self.assertFalse(
                        [k for k in row if k.startswith('__corr')])


class AppliedCorrectionTests(_Base):

    def test_exclusive_credit_and_no_duplicates(self):
        groups, summary = self._run(fx.correction_doc())
        self.assertEqual(summary['applied'], 1)
        self.assertEqual(summary['rows_recovered'], 1)
        snap = _snapshot(groups)
        self.assertEqual(snap['030826_90000001_USER_Foreman_B'][1], [101])
        self.assertEqual(
            snap['030826_90000001_USER_Foreman_A'][1], [102, 103, 104])
        self.assertEqual(
            snap['030826_90000001_HELPER_Helper_H'][1],
            [105, 106, 107, 108])
        # displaced Helper #2 group is now empty -> gone
        self.assertNotIn('030826_90000001_HELPER2_Helper2_C', snap)
        seen = [r['__row_id'] for v in groups.values() for r in v]
        for rid in _CORRECTED:
            self.assertEqual(seen.count(rid), 1, rid)
        self.assertNotIn(109, seen)
        # helper dept keeps today's representation -> stable identity
        helper_rows = groups['030826_90000001_HELPER_Helper_H']
        self.assertEqual({r['__helper_dept'] for r in helper_rows},
                         {'489.0'})
        # raw cells are never changed
        rec = [r for r in helper_rows if r['__row_id'] == 108][0]
        self.assertIsNone(rec['Weekly Reference Logged Date'])
        self.assertIsNone(rec['Snapshot Date'])

    def test_subtotals_reconcile(self):
        groups, _ = self._run(fx.correction_doc())
        totals = {}
        for grows in groups.values():
            for row in grows:
                if row['__row_id'] not in _CORRECTED:
                    continue
                key = (row['__current_foreman']
                       if row['__variant'] == 'primary'
                       else row['__helper_foreman'], row['__corr_workday'])
                totals[key] = totals.get(key, Decimal('0')) + Decimal(
                    row['Units Total Price'])
        want = {
            (name, day): Decimal(amount)
            for name, days in fx.correction_doc()['corrections'][0][
                'expected_subtotals'].items()
            for day, amount in days.items()
        }
        self.assertEqual(totals, want)

    def test_old_and_new_identities_regenerate_unrelated_untouched(self):
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = True
        groups, _ = self._run(fx.correction_doc())
        snap = _snapshot(groups)
        base = _GOLDEN[True]
        for key in ('030826_90000001_USER_Foreman_A',
                    '030826_90000001_HELPER_Helper_H'):
            self.assertNotEqual(snap[key][0], base[key][0], key)
        self.assertEqual(snap['030826_90000002_USER_Foreman_A'],
                         base['030826_90000002_USER_Foreman_A'])
        self.assertIn('030826_90000001_HELPER2_Helper2_C',
                      rc.displaced_groups())

    def test_displaced_group_keeps_corr_token_without_corrected_rows(self):
        # A displaced group with no corrected row left still hashes
        # differently from today (it lost rows), via the registry.
        groups, _ = self._run(fx.correction_doc())
        rows = [r for r in groups['030826_90000001_USER_Foreman_A']
                if not r.get('__corr_credit')]
        self.assertTrue(rc.group_correction_token(rows))

    def test_repeat_run_is_idempotent_and_revision_bump_regenerates(self):
        for extended in (True, False):
            generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = extended
            first = _snapshot(self._run(fx.correction_doc())[0])
            second = _snapshot(self._run(fx.correction_doc())[0])
            self.assertEqual(first, second)
            bumped = _snapshot(self._run(fx.correction_doc(revision=2))[0])
            for key in first:
                if '90000002' in key:
                    self.assertEqual(bumped[key], first[key])
                else:
                    self.assertNotEqual(bumped[key][0], first[key][0])

    def test_frozen_claimer_is_overridden_for_matched_rows_only(self):
        rows = fx.admitted_rows()
        self._configure(fx.correction_doc())
        recovered = fx.recovered_row()
        recovered.update(rc.recovery_for_row(recovered, fx.SHEET, 108))
        rows.append(recovered)
        self.assertEqual(rc.prepare_run(rows, group_fn=None)['applied'], 1)
        frozen = SimpleNamespace(action='use', name='Frozen Person')
        cmap = {101: frozen, 103: frozen}
        out = rc.apply_credit_overrides(rows, cmap)
        self.assertNotIn(101, cmap)
        self.assertIs(cmap[103], frozen)
        self.assertEqual(rc.get_run_counts()['frozen_overrides'], 1)
        by_id = {r['__row_id']: r for r in out}
        self.assertEqual(by_id[101]['__effective_user'], 'Foreman B')
        # the shared input dicts are not mutated
        self.assertEqual(rows[0]['__effective_user'], 'Foreman A')

    def test_empty_displaced_group_attachment_is_removed(self):
        groups, _ = self._run(fx.correction_doc())
        target_row = SimpleNamespace(id=55)
        calls = []

        def _fake_delete(*args, **kwargs):
            calls.append((args, kwargs))
            return 1, False

        switches = dict(
            primary_claim_enabled=(
                generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED),
            vac_crew_claim_enabled=(
                generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED),
            res_grouping_mode=generate_weekly_pdfs.RES_GROUPING_MODE,
        )
        with mock.patch.object(_orchestrate, 'delete_old_excel_attachments',
                               side_effect=_fake_delete):
            for skip in (False, True):
                handled = _orchestrate._remove_empty_displaced_attachments(
                    object(), groups, {fx.WR: target_row}, {55: []},
                    switches, target_sheet_id=1, skip_upload=skip)
                self.assertEqual(handled, 1)
            # held / quarantined pairs are never touched
            self.assertEqual(
                _orchestrate._remove_empty_displaced_attachments(
                    object(), groups, {fx.WR: target_row}, {}, switches,
                    target_sheet_id=1, skip_upload=False,
                    blocked_wrs={fx.WR}), 0)
        self.assertEqual(len(calls), 2)
        args, kwargs = calls[0]
        self.assertEqual(args[3:5], (fx.WR, '030826'))
        self.assertEqual(kwargs['variant'], 'helper2')
        self.assertEqual(kwargs['identifier'], 'Helper2_C')
        self.assertTrue(kwargs['force_generation'])
        self.assertEqual([c[1]['dry_run'] for c in calls], [False, True])


class BlockedCorrectionTests(_Base):

    def test_mismatch_blocks_whole_case_and_applies_nothing(self):
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = True
        rows = fx.admitted_rows()
        rows[1]['Units Total Price'] = '111.00'  # row 102 drifted
        doc = fx.correction_doc()  # expectations from the original rows
        with self.assertLogs(level='WARNING') as cm:
            groups, summary = self._run(doc, rows=rows)
        self.assertEqual(summary['blocked'], 1)
        self.assertTrue(any('BLOCKED' in m for m in cm.output))
        snap = _snapshot(groups)
        # recovered row dropped again; everything else as today
        seen = [r['__row_id'] for v in groups.values() for r in v]
        self.assertNotIn(108, seen)
        self.assertEqual(
            snap['030826_90000001_HELPER2_Helper2_C'],
            _GOLDEN[True]['030826_90000001_HELPER2_Helper2_C'])
        for grows in groups.values():
            for row in grows:
                self.assertFalse(row.get('__corr_credit'))

    def test_missing_row_and_wrong_wr_block(self):
        cset = rc.parse_corrections(fx.correction_doc())
        rows = fx.admitted_rows()
        rows = [r for r in rows if r['__row_id'] != 105]
        rows[0]['Work Request #'] = 90000003.0
        res = rc.evaluate(cset, rows)[0]
        self.assertEqual(res.status, 'blocked')
        self.assertEqual({e.row_id for e in res.missing}, {105, 108})
        diffs = dict((e.row_id, d) for e, d in res.mismatched)
        self.assertIn('work request differs', diffs[101])


class ExcelReadbackTests(_Base):

    def _read(self, path):
        ws = openpyxl.load_workbook(path).active
        foreman, days, day = None, {}, None
        for row in ws.iter_rows():
            vals = [c.value for c in row if c.value not in (None, '')]
            if not vals:
                continue
            if 'Foreman:' in vals:
                foreman = vals[vals.index('Foreman:') + 1]
            first = str(vals[0])
            match = _DAY_RE.match(first)
            if match:
                day = match.group(2)
                days[day] = {'items': [], 'total': None}
            elif day and first == 'TOTAL':
                days[day]['total'] = vals[-1]
                day = None
            elif day and re.match(r'^Point \d', first):
                days[day]['items'].append((first, vals[-1]))
        return foreman, days

    def test_generated_workbooks_read_back(self):
        groups, _ = self._run(fx.correction_doc())
        out = {}
        with mock.patch.object(generate_weekly_pdfs, 'OUTPUT_FOLDER',
                               self._tmp.name):
            for key, grows in groups.items():
                path, *_ = generate_weekly_pdfs.generate_excel(
                    key, grows, grows[0]['__week_ending_date'],
                    data_hash=generate_weekly_pdfs.calculate_data_hash(
                        grows))
                out[key] = self._read(path)
        foreman, days = out['030826_90000001_USER_Foreman_B']
        self.assertEqual(foreman, 'Foreman B')
        self.assertEqual(days, {'03/03/2026': {
            'items': [('Point 1', 100)], 'total': 100}})
        foreman, days = out['030826_90000001_USER_Foreman_A']
        self.assertEqual(foreman, 'Foreman A')
        self.assertEqual(sorted(days), ['03/02/2026', '03/03/2026',
                                        '03/04/2026'])
        self.assertEqual(days['03/02/2026']['items'], [('Point 3', 120)])
        self.assertEqual(days['03/03/2026']['total'], 200)
        self.assertEqual(days['03/04/2026']['items'], [('Point 2', 110)])
        _, days = out['030826_90000001_HELPER_Helper_H']
        self.assertEqual(days['03/03/2026']['total'], 510)
        self.assertEqual(days['03/04/2026']['items'], [('Point 8', 44.07)])
        # the out-of-scope Saturday row is preserved untouched
        self.assertEqual(days['03/07/2026']['items'], [('Point 7', 400)])


class FetchRecoveryTests(_Base):

    _COLS = ('Work Request #', 'Weekly Reference Logged Date',
             'Snapshot Date', 'Units Completed?', 'Units Total Price',
             'CU', 'Work Type', 'Pole #', 'Quantity', 'Foreman', 'Dept #')

    def _fetch(self, rows):
        mapping = {c: i + 1 for i, c in enumerate(self._COLS)}
        sheet_rows = [
            SimpleNamespace(
                id=r['__row_id'], modified_at=None,
                cells=[SimpleNamespace(column_id=mapping[c], value=r.get(c),
                                       display_value=None)
                       for c in self._COLS])
            for r in rows
        ]
        source = {'id': fx.SHEET, 'name': 'Synthetic',
                  'column_mapping': mapping}
        sheet = SimpleNamespace(rows=sheet_rows, version=1)
        with mock.patch.object(_fetch, 'smartsheet_call_with_retry',
                               return_value=sheet):
            return _fetch.get_all_source_rows(mock.Mock(), [source])

    def test_only_listed_blank_date_row_is_admitted_once(self):
        self._configure(fx.correction_doc())
        with self.assertLogs(level='WARNING') as cm:
            got = self._fetch([fx.recovered_row(), fx.unlisted_blank_row()])
        self.assertEqual([r['__row_id'] for r in got], [108])
        row = got[0]
        self.assertTrue(row['__corr_recovered'])
        self.assertEqual(row['__corr_week_ending'], fx.WEEK)
        self.assertIsNone(row['Weekly Reference Logged Date'])
        self.assertIsNone(row['Snapshot Date'])
        logged = [m for m in cm.output if 'recovery' in m]
        self.assertEqual(len(logged), 1)
        self.assertNotIn('Foreman', logged[0])

    def test_recovery_needs_matching_expectation_and_feature_on(self):
        drifted = fx.recovered_row()
        drifted['Units Total Price'] = '45.39'
        self._configure(fx.correction_doc())
        self.assertEqual(self._fetch([drifted]), [])
        _config.REPORTING_CORRECTIONS_FILE = None
        rc.reset_state()
        self.assertEqual(self._fetch([fx.recovered_row()]), [])


class IncrementalSeamTests(_Base):

    def test_correction_pairs_and_affected_filter(self):
        self.assertEqual(rc.correction_pairs(), set())
        self._configure(fx.correction_doc())
        self.assertEqual(rc.correction_pairs(), {(fx.WR, fx.WEEK)})
        self.assertEqual(rc.correction_sheet_ids(), {fx.SHEET})
        groups, _ = self._run()
        helper = groups['030826_90000001_HELPER_Helper_H']
        rec = [r for r in helper if r['__row_id'] == 108]
        kept = _orchestrate._filter_groups_to_affected(
            {'k': rec}, {(fx.WR, fx.WEEK)})
        self.assertEqual(list(kept), ['k'])


class PreviewZeroWriteTests(_Base):

    def _files(self):
        doc_path = self._configure(fx.correction_doc())
        rows = fx.admitted_rows() + [fx.recovered_row()]
        rows_path = os.path.join(self._tmp.name, 'rows.json')
        with open(rows_path, 'w', encoding='utf-8') as fh:
            json.dump(rows, fh)
        mem_path = os.path.join(self._tmp.name, 'mem.json')
        with open(mem_path, 'w', encoding='utf-8') as fh:
            json.dump({'108': {'units_total_price': 45.39,
                               'snapshot_date': '2026-03-04'}}, fh)
        return doc_path, rows_path, mem_path

    def test_preview_end_to_end_with_writers_rigged_to_raise(self):
        import billing_audit.writer as ba_writer
        import pipeline_memory.writer as pm_writer
        attempted = []

        def _boom(name):
            def _raise(*_a, **_k):
                attempted.append(name)
                raise AssertionError(f'write attempted: {name}')
            return _raise

        targets = [
            (pm_writer, n) for n in (
                'upsert_rows_bulk_result', 'upsert_rows_bulk',
                'upsert_group_state', 'upsert_sheet_registry',
                'mark_rows_deleted', 'run_ledger_start',
                'run_ledger_finish', 'run_ledger_note_pending')
        ] + [
            (ba_writer, n) for n in (
                'freeze_row', 'emit_run_fingerprint', 'upsert_group_hash',
                'prefetch_attribution', 'lookup_attribution')
        ]
        doc_path, rows_path, mem_path = self._files()
        buf = io.StringIO()
        with mock.patch('sys.stdout', buf):
            with mock.patch.multiple(  # noqa: SIM117
                    pm_writer, **{n: _boom(n) for m, n in targets
                                  if m is pm_writer}):
                with mock.patch.multiple(
                        ba_writer, **{n: _boom(n) for m, n in targets
                                      if m is ba_writer}):
                    code = rc.main(['preview', '--file', doc_path,
                                    '--rows-json', rows_path,
                                    '--memory-json', mem_path])
        self.assertEqual(code, 0)
        self.assertEqual(attempted, [])
        text = buf.getvalue()
        self.assertIn('matched 6 / unmatched 0 / mismatched 0', text)
        self.assertIn('source vs memory differences 1', text)
        self.assertIn('blocked=0', text)

    def test_cli_never_imports_writer_packages(self):
        doc_path, rows_path, _ = self._files()
        code = (
            'import sys, pipeline.reporting_corrections as r;'
            f'rc_ = r.main(["preview", "--file", {doc_path!r},'
            f' "--rows-json", {rows_path!r}]);'
            'bad = [m for m in sys.modules if m.split(".")[0] in'
            ' ("pipeline_memory", "billing_audit", "smartsheet",'
            ' "supabase")];'
            'print("LOADED", bad); sys.exit(rc_)'
        )
        env = dict(os.environ, PYTHONUTF8='1')
        env.pop('REPORTING_CORRECTIONS_FILE', None)
        proc = subprocess.run(
            [sys.executable, '-c', code], cwd=str(_REPO_ROOT), env=env,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('LOADED []', proc.stdout)

    def test_validate_cli_reports_problems(self):
        path = os.path.join(self._tmp.name, 'bad.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'schema': 1, 'corrections': [{'id': 'x'}]}, fh)
        buf = io.StringIO()
        with mock.patch('sys.stdout', buf):
            self.assertEqual(rc.main(['validate', '--file', path]), 2)
        self.assertIn('INVALID', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
