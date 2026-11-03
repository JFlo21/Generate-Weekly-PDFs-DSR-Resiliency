"""Reporting corrections (pipeline/reporting_corrections.py).

Synthetic fixture only (tests/_reporting_corrections_fixture.py): fake
people, fake WR numbers, fake sheet/row ids. Evidence label: FIXTURE
PASS -- not a dry run, not production observed.
"""

from __future__ import annotations

import copy
import datetime
import inspect
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
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
import pipeline.grouping as _grouping  # noqa: E402
import pipeline.orchestrate as _orchestrate  # noqa: E402
from pipeline import config as _config  # noqa: E402
from pipeline import observability as _obs  # noqa: E402
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


# Fake attachment ids for the stale-attachment tests (one per identity).
_ATT_IDS = {
    '030826_90000001_USER_Foreman_B': 901,
    '030826_90000001_USER_Foreman_A': 902,
    '030826_90000001_HELPER2_Helper2_C': 903,
    '030826_90000001_HELPER_Helper_H': 904,
    '030826_90000002_USER_Foreman_A': 905,
    '030826_90000001_HELPER_Helper_Z': 906,
}
_FOREMAN_B = '030826_90000001_USER_Foreman_B'
_HELPER_Z = '030826_90000001_HELPER_Helper_Z'


def _real_filenames(test, rows, doc=None):
    """group key -> the filename generate_excel really writes for it
    (feature off, or with *doc* applied)."""
    if doc is None:
        _config.REPORTING_CORRECTIONS_FILE = None
        rc.reset_state()
        groups = generate_weekly_pdfs.group_source_rows(rows)
    else:
        groups, _ = test._run(doc, rows=rows)
    names = {}
    with mock.patch.object(generate_weekly_pdfs, 'OUTPUT_FOLDER',
                           test._tmp.name):
        for key, grows in groups.items():
            path, *_ = generate_weekly_pdfs.generate_excel(
                key, grows, grows[0]['__week_ending_date'],
                data_hash=generate_weekly_pdfs.calculate_data_hash(grows))
            names[key] = os.path.basename(path)
    rc.reset_state()
    return names


def _cache(*name_maps):
    atts = {}
    for names in name_maps:
        for key, name in names.items():
            atts[_ATT_IDS[key]] = SimpleNamespace(id=_ATT_IDS[key],
                                                  name=name)
    return {55: [atts[k] for k in sorted(atts)]}


def _client():
    return SimpleNamespace(Attachments=mock.Mock())


def _deleted(client):
    return sorted(c.args[1] for c in
                  client.Attachments.delete_attachment.call_args_list)


def _remove(groups, cache, client, **extra):
    kwargs = dict(target_sheet_id=1, skip_upload=False)
    kwargs.update(extra)
    # no run-level live listing: the on-demand live read returns what
    # the cache holds unless *fetched* says otherwise (a list, or an
    # exception for a failed read)
    fetched = kwargs.pop('fetched', None)
    if isinstance(fetched, Exception):
        client.Attachments.list_row_attachments.side_effect = fetched
    else:
        client.Attachments.list_row_attachments.return_value = (
            SimpleNamespace(data=list(
                cache.get(55, []) if fetched is None else fetched)))
    switches = dict(
        primary_claim_enabled=(
            generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED),
        vac_crew_claim_enabled=(
            generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED),
        res_grouping_mode=generate_weekly_pdfs.RES_GROUPING_MODE,
    )
    return _orchestrate._remove_empty_displaced_attachments(
        client, groups, {fx.WR: SimpleNamespace(id=55)}, cache, switches,
        **kwargs)


def _retired_doc():
    """Revision 1 (applied before) superseded by a retired revision 2."""
    doc = fx.correction_doc()
    rev2 = copy.deepcopy(doc['corrections'][0])
    rev2['revision'] = 2
    rev2['retired'] = True
    doc['corrections'].append(rev2)
    return doc


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
        # the identity pass reuses the last grouping's prefetch: start
        # and end every test without one
        _grouping._LAST_ATTR_PREFETCH = None
        self.addCleanup(setattr, _grouping, '_LAST_ATTR_PREFETCH', None)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _configure(self, doc):
        path = os.path.join(self._tmp.name, f'c{id(doc)}.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(doc, fh)
        _config.REPORTING_CORRECTIONS_FILE = path
        rc.reset_state()
        return path

    def _run(self, doc=None, rows=None, check=True):
        """fetch-recovery + prepare_run + grouping (+ the placement
        check unless *check* is False), like main() does."""
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
        if check and summary:
            rc.check_applied_placement(groups)
        return groups, summary


class LoaderValidationTests(_Base):

    def _problems(self, doc):
        with self.assertRaises(rc.CorrectionError) as cm:
            rc.parse_corrections(doc)
        return ' | '.join(cm.exception.problems)

    def test_valid_fixture_and_template_parse(self):
        cset = rc.parse_corrections(fx.correction_doc())
        self.assertEqual(len(cset.by_row), 7)
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

    def test_primary_credit_requires_dept(self):
        # A blank primary dept would skip the Dept # equality check in
        # row_differences(): the loader must reject it.
        for blank in ('', None, '  '):
            doc = fx.correction_doc()
            doc['corrections'][0]['rows'][0]['credit']['dept'] = blank
            self.assertIn('credit.dept is required for primary',
                          self._problems(doc))

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
        # The stale HELPER2 file is named exactly as generate_excel names
        # it on a feature-off run; the REAL delete helper must match it
        # through build_group_identity and remove only that attachment.
        names = _real_filenames(self, fx.admitted_rows())
        helper2 = names['030826_90000001_HELPER2_Helper2_C']
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(helper2),
            (fx.WR, '030826', 'helper2', 'Helper2_C'))
        groups, _ = self._run(fx.correction_doc())
        self.assertNotIn('030826_90000001_HELPER2_Helper2_C', groups)
        cache = _cache(names)
        for skip, deleted in ((True, []), (False, [903])):
            client = _client()
            handled = _remove(groups, cache, client, skip_upload=skip)
            self.assertEqual(handled, 1)
            self.assertEqual(_deleted(client), deleted)
        # held / quarantined pairs are never touched (L10)
        for extra in ({'blocked_wrs': {fx.WR}},
                      {'held_wr_weeks': {(fx.WR, '030826')}}):
            client = _client()
            self.assertEqual(_remove(groups, cache, client, **extra), 0)
            self.assertEqual(_deleted(client), [])
        # nothing stale left in the cache -> quiet no-op (L6)
        client = _client()
        rest = {55: [a for a in cache[55] if a.id != 903]}
        self.assertEqual(_remove(groups, rest, client), 0)
        self.assertEqual(_deleted(client), [])

    def test_removal_waits_for_the_receiving_groups_and_budget(self):
        names = _real_filenames(self, fx.admitted_rows())
        groups, _ = self._run(fx.correction_doc())
        cache = _cache(names)
        pair_keys = {k for k in groups if '_90000001_' in k}
        for kwargs in (
            {'settled_group_keys': set(groups) - {sorted(pair_keys)[0]}},
            {'time_budget_exceeded': True},
        ):
            client = _client()
            self.assertEqual(_remove(groups, cache, client, **kwargs), 0)
            self.assertEqual(_deleted(client), [])
        client = _client()
        self.assertEqual(
            _remove(groups, cache, client, settled_group_keys=pair_keys),
            1)
        self.assertEqual(_deleted(client), [903])

    def test_failed_placement_holds_the_pair_cleanup(self):
        # An applied row in no group (or in two) means no replacement
        # workbook holds it: the pair is not settled, keep the old file.
        names = _real_filenames(self, fx.admitted_rows())
        cache = _cache(names)
        groups, summary = self._run(fx.correction_doc())
        broken = dict(groups)
        broken[_FOREMAN_B] = [r for r in groups[_FOREMAN_B]
                              if r['__row_id'] != 101]
        with self.assertLogs(level='WARNING'):
            self.assertEqual(rc.check_applied_placement(broken), 1)
        self.assertEqual(rc.unplaced_pairs(), {(fx.WR, '030826')})
        client = _client()
        with self.assertLogs(level='WARNING') as cm:
            self.assertEqual(_remove(broken, cache, client), 0)
        self.assertEqual(_deleted(client), [])
        self.assertTrue(any('placement' in m for m in cm.output))
        self.assertEqual(rc.get_run_counts()['placement_held_pairs'], 1)
        # placement re-checked clean -> the pair is settled again
        self.assertEqual(rc.check_applied_placement(groups), 0)
        self.assertEqual(rc.unplaced_pairs(), set())
        client = _client()
        self.assertEqual(_remove(groups, cache, client), 1)
        self.assertEqual(_deleted(client), [903])
        # placement never checked this run -> unverified, held as well
        groups, _ = self._run(fx.correction_doc(), check=False)
        self.assertEqual(rc.unplaced_pairs(), {(fx.WR, '030826')})
        client = _client()
        self.assertEqual(_remove(groups, cache, client), 0)
        self.assertEqual(_deleted(client), [])


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

    def test_variant_the_grouping_switches_cannot_produce_blocks(self):
        # A helper credit under RES_GROUPING_MODE=primary (or a helper2
        # credit with HELPER2_ENABLED off) would land in the primary
        # workbook yet report APPLIED: block it before stamping.
        with mock.patch.object(generate_weekly_pdfs, 'RES_GROUPING_MODE',
                               'primary'), \
                self.assertLogs(level='WARNING') as cm:
            groups, summary = self._run(fx.correction_doc())
        self.assertEqual((summary['applied'], summary['blocked']), (0, 1))
        self.assertEqual(
            summary['findings']['variant_not_produced'], 1)
        blocked = [m for m in cm.output if 'BLOCKED' in m]
        self.assertTrue(blocked)
        self.assertIn('RES_GROUPING_MODE=primary', blocked[0])
        self.assertNotIn('Helper H', ' '.join(cm.output))
        self.assertFalse(any(r.get('__corr_credit')
                             for grows in groups.values() for r in grows))
        doc = fx.correction_doc()
        row106 = doc['corrections'][0]['rows'][4]
        self.assertEqual(row106['row_id'], 106)
        row106['credit']['variant'] = 'helper2'
        for enabled, applied in ((False, 0), (True, 1)):
            with mock.patch.object(_config, 'HELPER2_ENABLED', enabled):
                _, summary = self._run(doc)
            self.assertEqual(summary['applied'], applied)
            self.assertEqual(
                summary['findings']['variant_not_produced'], 1 - applied)

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


class ReconcileOnlyTests(_Base):
    """$0.00 rows are reconciliation-only (coordinator decision)."""

    def test_absent_zero_row_is_expected_and_never_credited(self):
        groups, summary = self._run(fx.correction_doc())
        self.assertEqual(summary['applied'], 1)
        self.assertEqual(summary['rows_reconcile_only'], 1)
        self.assertEqual(summary['rows_applied'], 6)
        seen = [r['__row_id'] for v in groups.values() for r in v]
        self.assertNotIn(110, seen)
        res = rc.evaluate(rc.get_active_set(), fx.admitted_rows())[0]
        self.assertEqual([e.row_id for e in res.reconcile_only], [110])
        self.assertNotIn(110, [e.row_id for e in res.missing])

    def test_zero_row_present_at_zero_in_a_dump_stays_reconcile_only(self):
        cset = rc.parse_corrections(fx.correction_doc())
        rows = fx.admitted_rows() + [fx.recovered_row(),
                                     fx.zero_price_row()]
        res = rc.evaluate(cset, rows)[0]
        self.assertEqual(res.status, 'applied')
        self.assertEqual([e.row_id for e in res.reconcile_only], [110])
        self.assertNotIn(110, [e.row_id for e in res.matched])

    def test_zero_row_admitted_live_with_price_blocks_the_case(self):
        live = fx.zero_price_row()
        live['Units Total Price'] = '12.50'
        rows = fx.admitted_rows() + [live]
        with self.assertLogs(level='WARNING') as cm:
            groups, summary = self._run(fx.correction_doc(), rows=rows)
        self.assertEqual(summary['blocked'], 1)
        text = ' | '.join(cm.output)
        # field name only: live / expected values never reach the log
        self.assertIn('row 110 for WR 90000001: 1 field(s) differ: '
                      'units_total_price', text)
        self.assertNotIn('12.50', text)
        res = rc.evaluate(rc.get_active_set(), rows)[0]
        self.assertIn('units_total_price: 12.50 != expected 0.00',
                      dict((e.row_id, d) for e, d in res.mismatched)[110])
        for grows in groups.values():
            for row in grows:
                self.assertFalse(row.get('__corr_credit'))

    def test_zero_row_cannot_be_recovered(self):
        doc = fx.correction_doc()
        doc['corrections'][0]['rows'][-1]['recover_missing_dates'] = True
        doc['corrections'][0]['rows'][-1]['expect'].update(
            snapshot_date=None, weekly_reference_logged_date=None)
        with self.assertRaises(rc.CorrectionError) as cm:
            rc.parse_corrections(doc)
        self.assertIn('reconciliation-only', ' '.join(cm.exception.problems))


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
        self.assertIn('matched 6 billable / reconcile-only 1 / '
                      'unmatched 0 / mismatched 0', text)
        self.assertIn('reconcile-only $0.00 rows (never admitted, never '
                      'credited): 1 rows, total 0.00', text)
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


class RollbackTests(_Base):
    """H2: retired / blocked / revised cases leave no stale file."""

    def test_retired_case_removes_correction_only_file_and_regenerates(
            self):
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = True
        applied_names = _real_filenames(
            self, fx.admitted_rows(), doc=fx.correction_doc())
        applied = _snapshot(self._run(fx.correction_doc())[0])
        self.assertIn(_FOREMAN_B, applied_names)
        groups, summary = self._run(_retired_doc())
        self.assertEqual((summary['applied'], summary['retired']), (0, 1))
        self.assertEqual(set(groups), set(_GOLDEN[True]))
        for grows in groups.values():
            self.assertFalse(any(r.get('__corr_credit') for r in grows))
        snap = _snapshot(groups)
        for key, (digest, row_ids) in _GOLDEN[True].items():
            self.assertEqual(snap[key][1], row_ids)
            if '90000002' in key:
                self.assertEqual(snap[key][0], digest)
            else:  # regenerates: differs from today AND the applied file
                self.assertNotEqual(snap[key][0], digest, key)
                self.assertNotEqual(snap[key][0],
                                    applied.get(key, [None])[0], key)
        self.assertIn(_FOREMAN_B, rc.displaced_groups())
        client = _client()
        self.assertEqual(_remove(groups, _cache(applied_names), client), 1)
        self.assertEqual(_deleted(client), [901])

    def test_retired_case_recovers_nothing(self):
        self._configure(_retired_doc())
        self.assertIsNone(
            rc.recovery_for_row(fx.recovered_row(), fx.SHEET, 108))

    def test_blocked_after_applied_removes_correction_only_file(self):
        applied_names = _real_filenames(
            self, fx.admitted_rows(), doc=fx.correction_doc())
        rows = fx.admitted_rows()
        rows[1]['Units Total Price'] = '111.00'  # live edit on row 102
        with self.assertLogs(level='WARNING'):
            groups, summary = self._run(fx.correction_doc(), rows=rows)
        self.assertEqual(summary['blocked'], 1)
        self.assertNotIn(_FOREMAN_B, groups)
        self.assertIn('030826_90000001_HELPER2_Helper2_C', groups)
        client = _client()
        self.assertEqual(_remove(groups, _cache(applied_names), client), 1)
        self.assertEqual(_deleted(client), [901])

    def test_revision_moving_credit_removes_the_old_identity(self):
        rev1_names = _real_filenames(
            self, fx.admitted_rows(), doc=fx.correction_doc())
        doc = fx.correction_doc()
        rev2 = copy.deepcopy(doc['corrections'][0])
        rev2['revision'] = 2
        rev2['rows'][0]['credit']['name'] = 'Foreman D'
        subs = rev2['expected_subtotals']
        subs['Foreman D'] = subs.pop('Foreman B')
        doc['corrections'].append(rev2)
        groups, summary = self._run(doc)
        self.assertEqual(summary['applied'], 1)
        self.assertIn('030826_90000001_USER_Foreman_D', groups)
        self.assertNotIn(_FOREMAN_B, groups)
        client = _client()
        self.assertEqual(_remove(groups, _cache(rev1_names), client), 1)
        self.assertEqual(_deleted(client), [901])

    @staticmethod
    def _recovered_only_doc():
        """Row 108 (recovered, blank dates) is the ONLY row credited to
        Helper Z: that identity exists only while the case applies."""
        doc = fx.correction_doc()
        corr = doc['corrections'][0]
        for row in corr['rows']:
            if row['row_id'] == 108:
                row['credit'] = dict(row['credit'], name='Helper Z')
        corr.pop('expected_subtotals', None)
        return doc

    def test_retired_case_removes_recovered_only_identity(self):
        doc = self._recovered_only_doc()
        applied_names = _real_filenames(self, fx.admitted_rows(), doc=doc)
        self.assertIn(_HELPER_Z, applied_names)
        rev2 = copy.deepcopy(doc['corrections'][0])
        rev2['revision'] = 2
        rev2['retired'] = True
        doc['corrections'].append(rev2)
        groups, summary = self._run(doc)
        self.assertEqual((summary['applied'], summary['retired']), (0, 1))
        self.assertNotIn(_HELPER_Z, groups)
        self.assertIn(_HELPER_Z, rc.displaced_groups())
        client = _client()
        self.assertEqual(_remove(groups, _cache(applied_names), client), 2)
        self.assertEqual(_deleted(client), [901, 906])

    def test_blocked_recovered_row_removes_recovered_only_identity(self):
        doc = self._recovered_only_doc()
        applied_names = _real_filenames(self, fx.admitted_rows(), doc=doc)
        self._configure(doc)
        rows = fx.admitted_rows()
        rec = fx.recovered_row()
        rec['Units Total Price'] = '45.00'  # its own expect now differs
        self.assertIsNone(rc.recovery_for_row(rec, fx.SHEET, 108))
        with self.assertLogs(level='WARNING'):
            summary = rc.prepare_run(
                rows, group_fn=generate_weekly_pdfs.group_source_rows)
        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertEqual(summary['blocked'], 1)
        self.assertNotIn(_HELPER_Z, groups)
        self.assertIn(_HELPER_Z, rc.displaced_groups())
        client = _client()
        self.assertEqual(_remove(groups, _cache(applied_names), client), 2)
        self.assertEqual(_deleted(client), [901, 906])

    def test_stale_check_reads_the_live_listing_before_the_cache(self):
        applied_names = _real_filenames(
            self, fx.admitted_rows(), doc=fx.correction_doc())
        groups, _ = self._run(_retired_doc())
        live = _cache(applied_names)
        no_stub = {55: []}  # group_state stubs missed the stale file
        client = _client()
        self.assertEqual(_remove(groups, no_stub, client), 0)
        self.assertEqual(_deleted(client), [])
        self.assertEqual(
            _remove(groups, no_stub, client, live_listings=live), 1)
        self.assertEqual(_deleted(client), [901])
        client = _client()  # in neither -> quiet skip
        self.assertEqual(
            _remove(groups, no_stub, client, live_listings={55: []}), 0)
        self.assertEqual(_deleted(client), [])

    def test_retired_must_be_boolean(self):
        doc = _retired_doc()
        doc['corrections'][1]['retired'] = 'yes'
        with self.assertRaises(rc.CorrectionError) as cm:
            rc.parse_corrections(doc)
        self.assertIn('retired must be boolean',
                      ' | '.join(cm.exception.problems))


class WeekGuardTests(_Base):
    """H1: a row must belong to the correction's week."""

    def test_loader_rejects_a_row_from_another_week(self):
        doc = fx.correction_doc()
        doc['corrections'][0]['rows'][0]['expect'][
            'weekly_reference_logged_date'] = '2026-03-01'
        with self.assertRaises(rc.CorrectionError) as cm:
            rc.parse_corrections(doc)
        self.assertIn('must equal week_ending',
                      ' | '.join(cm.exception.problems))

    def test_live_week_mismatch_blocks_the_case(self):
        doc = fx.correction_doc()
        corr = doc['corrections'][0]
        corr['week_ending'] = '2026-03-15'
        corr.pop('scope_days')
        corr.pop('expected_subtotals')
        corr['rows'] = [r for r in corr['rows']
                        if r['row_id'] not in (108, 110)]
        for row in corr['rows']:
            row['workday'] = '2026-03-10'
            row['expect']['weekly_reference_logged_date'] = '2026-03-15'
        with self.assertLogs(level='WARNING'):
            groups, summary = self._run(doc)
        self.assertEqual(summary['blocked'], 1)
        res = rc.evaluate(rc.get_active_set(), fx.admitted_rows())[0]
        self.assertEqual(len(res.mismatched), len(corr['rows']))
        for _, diffs in res.mismatched:
            self.assertTrue(any(d.startswith('week ending') for d in diffs))
        self.assertEqual(set(groups), set(_GOLDEN[True]))
        for grows in groups.values():
            self.assertFalse(any(r.get('__corr_credit') for r in grows))


class EarlyHoldAndFallbackTests(_Base):
    """M1 / M2: recovered rows never reach memory or audit inputs."""

    def _rows_with_recovered(self):
        rows = fx.admitted_rows()
        rec = fx.recovered_row()
        rec.update(rc.recovery_for_row(rec, fx.SHEET, 108))
        rows.insert(2, rec)
        return rows

    def test_recovered_row_is_held_out_until_prepare_run(self):
        self._configure(fx.correction_doc())
        rows = self._rows_with_recovered()
        held = rc.hold_recovered_rows(rows)
        self.assertEqual([r['__row_id'] for r in held], [108])
        self.assertNotIn(108, [r['__row_id'] for r in rows])
        rows.extend(held)  # what main() does just before prepare_run
        self.assertEqual(rc.prepare_run(rows, group_fn=None)['applied'], 1)

    def test_blocked_case_drops_the_recovered_row_early(self):
        self._configure(fx.correction_doc())
        rows = self._rows_with_recovered()
        rows[0]['Units Total Price'] = '101.00'  # row 101 drifted
        self.assertEqual(rc.hold_recovered_rows(rows), [])
        self.assertNotIn(108, [r['__row_id'] for r in rows])

    def test_feature_off_hold_is_a_no_op(self):
        rows = fx.admitted_rows()
        before = copy.deepcopy(rows)
        self.assertEqual(rc.hold_recovered_rows(rows), [])
        self.assertEqual(rows, before)

    def test_memory_write_never_sends_recovered_rows(self):
        self._configure(fx.correction_doc())
        rows = self._rows_with_recovered()
        sent = []

        def _upsert(_sheet_id, _run_id, bucket):
            sent.extend(r['__row_id'] for r in bucket)
            return {'affected': set(), 'status': 'ok'}

        with mock.patch.multiple(
                _orchestrate, RUN_MEMORY_WRITE_ENABLED=True,
                TEST_MODE=False, TIME_BUDGET_MINUTES=0), \
                mock.patch.object(_orchestrate._mem_writer,
                                  'upsert_rows_bulk_result',
                                  side_effect=_upsert), \
                mock.patch.object(_orchestrate._fn, 'memory_write_blocked',
                                  return_value=False):
            _orchestrate._run_memory_write_phase(
                rows, 'run-x', datetime.datetime.now())
        self.assertEqual(sorted(sent),
                         sorted(r['__row_id'] for r in fx.admitted_rows()))

    def test_fail_closed_fallback_drops_recovered_rows_first(self):
        self._configure(fx.correction_doc())
        rows = self._rows_with_recovered()
        rc.prepare_run(rows, group_fn=None)
        self.assertTrue(any(r.get('__corr_credit') for r in rows))
        rc.drop_all_corrections(rows)
        self.assertNotIn(108, [r['__row_id'] for r in rows])
        for row in rows:
            self.assertFalse(set(rc.STAMP_KEYS) & set(row))
        source = inspect.getsource(_orchestrate.main)
        self.assertIn('_rc.drop_all_corrections(all_rows)', source)
        self.assertIn('_rc.hold_recovered_rows(all_rows)', source)


class ShadowAndSideEffectTests(_Base):

    def test_full_mode_candidate_includes_correction_pairs(self):
        base = {('11111111', '2026-03-08')}
        self.assertEqual(
            _orchestrate._full_mode_candidate_pairs(base, set()), base)
        self._configure(fx.correction_doc())
        self.assertEqual(
            _orchestrate._full_mode_candidate_pairs(base, None),
            base | {(fx.WR, fx.WEEK)})

    @staticmethod
    def _vac_row():
        """VAC crew row in the corrected WR/week: on a prefetch
        fetch_failure the main pass records an attribution HOLD."""
        row = fx._base(111, '2026-03-04', '70.00', pole='Point 12',
                       cu='CU-12')
        row.update({'__is_vac_crew': True, '__vac_crew_name': 'Vac V',
                    '__vac_crew_dept': '777', '__vac_crew_job': ''})
        return row

    def _rows_prepared(self):
        rows = fx.admitted_rows()
        rows.append(self._vac_row())
        rec = fx.recovered_row()
        rec.update(rc.recovery_for_row(rec, fx.SHEET, 108))
        rows.append(rec)
        summary = rc.prepare_run(rows, group_fn=None)
        return rows, summary

    def test_identity_pass_reuses_prefetch_and_writes_nothing(self):
        import billing_audit.writer as ba_writer
        self._run(fx.correction_doc())
        expected = set(rc.displaced_groups())
        self.assertEqual(len(expected), 3)
        rows, _ = self._rows_prepared()
        prefetch = mock.Mock(return_value=({}, 'fetch_failure'))
        hold = mock.Mock()
        with mock.patch.multiple(generate_weekly_pdfs,
                                 BILLING_AUDIT_AVAILABLE=True,
                                 VAC_CREW_CLAIM_ATTRIBUTION_ENABLED=True), \
                mock.patch.object(ba_writer, 'prefetch_attribution',
                                  prefetch), \
                mock.patch.object(ba_writer, 'record_attribution_hold',
                                  hold), \
                mock.patch.object(_grouping,
                                  'sentry_capture_message_with_context'
                                  ) as sentry:
            generate_weekly_pdfs.group_source_rows(rows)
            holds, alerts = hold.call_count, sentry.call_count
            published = _grouping.get_prefetched_frozen_row_keys()
            conflicts = _grouping.get_helper2_conflict_count()
            registered = rc.register_displaced(
                rows, lambda r: generate_weekly_pdfs.group_source_rows(
                    r, side_effects=False))
        self.assertEqual(prefetch.call_count, 1)
        self.assertGreaterEqual(holds, 1)  # the main pass does write
        self.assertEqual(hold.call_count, holds)  # the side pass never
        self.assertEqual(sentry.call_count, alerts)
        self.assertEqual(_grouping.get_prefetched_frozen_row_keys(),
                         published)
        self.assertEqual(_grouping.get_helper2_conflict_count(), conflicts)
        self.assertEqual(registered, len(expected))
        self.assertEqual(set(rc.displaced_groups()), expected)

    def test_registration_fills_the_summary_count(self):
        _, summary = self._run(fx.correction_doc())
        self.assertEqual(summary['displaced_groups'], 3)
        self._configure(fx.correction_doc())
        audit = {}
        rows = fx.admitted_rows()
        rec = fx.recovered_row()
        rec.update(rc.recovery_for_row(rec, fx.SHEET, 108))
        rows.append(rec)
        summary = rc.prepare_run(rows, group_fn=None, audit_summary=audit)
        self.assertIsNone(summary['displaced_groups'])
        _grouping._LAST_ATTR_PREFETCH = ({}, 'success')
        _orchestrate._register_corr_displaced(rows, summary)
        self.assertEqual(summary['displaced_groups'], 3)
        self.assertEqual(
            audit['reporting_corrections']['displaced_groups'], 3)

    def test_rpc_missing_skips_the_identity_pass(self):
        self._configure(fx.correction_doc())
        rows, summary = self._rows_prepared()
        _grouping._LAST_ATTR_PREFETCH = ({}, 'rpc_missing')
        with mock.patch.object(rc, 'register_displaced') as reg, \
                self.assertLogs(level='WARNING') as logs:
            _orchestrate._register_corr_displaced(rows, summary)
        reg.assert_not_called()
        self.assertEqual(
            sum('rpc_missing' in line for line in logs.output), 1)
        self.assertIsNone(summary['displaced_groups'])
        self.assertEqual(rc.displaced_groups(), {})


class HardeningTests(_Base):
    """Review round 1 low-severity items (L1-L9)."""

    _COLS = FetchRecoveryTests._COLS
    _fetch = FetchRecoveryTests._fetch

    def _problems(self, doc):
        with self.assertRaises(rc.CorrectionError) as cm:
            rc.parse_corrections(doc)
        return ' | '.join(cm.exception.problems)

    def test_non_finite_numbers_and_bad_wr_are_rejected(self):
        for key, value in (('quantity', float('nan')),
                           ('units_total_price', float('inf'))):
            doc = fx.correction_doc()
            doc['corrections'][0]['rows'][0]['expect'][key] = value
            self.assertIn(f'expect.{key} must be a finite number',
                          self._problems(doc))
        doc = fx.correction_doc()
        doc['corrections'][0]['wr'] = 'WR-1'
        self.assertIn('wr must be a numeric', self._problems(doc))

    def test_expect_dates_are_normalised(self):
        doc = fx.correction_doc()
        doc['corrections'][0]['rows'][0]['expect'].update(
            weekly_reference_logged_date='20260308')
        entry = rc.parse_corrections(doc).corrections[0].rows[0]
        self.assertEqual(entry.expect['weekly_reference_logged_date'],
                         fx.WEEK)

    def test_bom_file_loads(self):
        path = os.path.join(self._tmp.name, 'bom.json')
        with open(path, 'w', encoding='utf-8-sig') as fh:
            json.dump(fx.correction_doc(), fh)
        self.assertEqual(len(rc.load_corrections(path).corrections), 1)

    def test_file_outside_allowed_roots_means_feature_off(self):
        path = self._configure(fx.correction_doc())
        elsewhere = os.path.join(self._tmp.name, 'other-root')
        with mock.patch.object(rc, '_allowed_roots',
                               return_value=(elsewhere,)):
            with self.assertRaises(rc.CorrectionError) as cm:
                rc.load_corrections(path)
            self.assertIn('must live under', cm.exception.problems[0])
            with self.assertLogs(level='ERROR'):
                self.assertIsNone(rc.get_active_set())

    def test_runner_temp_is_an_allowed_root(self):
        runner_tmp = os.path.join(self._tmp.name, 'runner')
        os.makedirs(runner_tmp)
        path = os.path.join(runner_tmp, 'reporting_corrections.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(fx.correction_doc(), fh)
        with mock.patch.dict(os.environ, {'RUNNER_TEMP': runner_tmp}), \
                mock.patch.object(tempfile, 'gettempdir',
                                  return_value=os.path.join(
                                      self._tmp.name, 'not-this')), \
                mock.patch.object(os, 'getcwd', return_value=os.path.join(
                    self._tmp.name, 'nor-this')):
            self.assertIn(os.path.normpath(os.path.realpath(runner_tmp)),
                          rc._allowed_roots())
            self.assertEqual(len(rc.load_corrections(path).corrections), 1)

    def test_unexpected_load_error_means_feature_off(self):
        self._configure(fx.correction_doc())
        with mock.patch.object(rc, 'load_corrections',
                               side_effect=RuntimeError('boom')), \
                self.assertLogs(level='ERROR'):
            self.assertIsNone(rc.get_active_set())
        self.assertEqual(rc.correction_pairs(), set())

    def test_summary_is_logged_at_info_counts_only(self):
        with self.assertLogs(level='INFO') as cm:
            self._run(fx.correction_doc())
        lines = [m for m in cm.output if 'corrections summary' in m]
        self.assertEqual(len(lines), 1)
        self.assertNotIn('Foreman', lines[0])

    def test_each_applied_row_lands_in_exactly_one_group(self):
        groups, _ = self._run(fx.correction_doc())
        self.assertEqual(rc.check_applied_placement(groups), 0)
        broken = dict(groups)
        broken[_FOREMAN_B] = [r for r in groups[_FOREMAN_B]
                              if r['__row_id'] != 101]
        with self.assertLogs(level='WARNING'):
            self.assertEqual(rc.check_applied_placement(broken), 1)

    def test_token_covers_every_group_of_an_aggregated_bucket(self):
        groups, _ = self._run(fx.correction_doc())
        a = [r for r in groups['030826_90000001_USER_Foreman_A']
             if not r.get('__corr_credit')]
        h = [r for r in groups['030826_90000001_HELPER_Helper_H']
             if not r.get('__corr_credit')]
        both = rc.group_correction_token(a + h)
        self.assertTrue(both)
        self.assertNotEqual(both, rc.group_correction_token(a))
        self.assertNotEqual(both, rc.group_correction_token(h))
        self.assertEqual(both, rc.group_correction_token(h + a))

    def test_cli_handles_bad_inputs(self):
        doc_path = self._configure(fx.correction_doc())
        buf = io.StringIO()
        with mock.patch('sys.stdout', buf):
            code = rc.main(['preview', '--file', doc_path, '--rows-json',
                            os.path.join(self._tmp.name, 'missing.json')])
        self.assertEqual(code, 2)
        self.assertIn('cannot read input JSON', buf.getvalue())
        dump = {'S': [
            {'sheet_id': str(fx.SHEET), 'row_id': '101',
             'cells': {'CU': ['CU-1', 'CU-1']}},
            {'sheet_id': fx.SHEET, 'row_id': 102, 'cells': ['bad']},
        ]}
        rows = rc._rows_from_dump(dump)
        self.assertEqual([(r['__sheet_id'], r['__row_id']) for r in rows],
                         [(fx.SHEET, 101)])

    def test_correction_file_is_read_once_on_the_calling_thread(self):
        self._configure(fx.correction_doc())
        threads = []
        real = rc.correction_sheet_ids

        def _spy():
            threads.append(threading.current_thread().name)
            return real()

        with mock.patch.object(rc, 'correction_sheet_ids',
                               side_effect=_spy):
            got = self._fetch([fx.recovered_row()])
        self.assertEqual([r['__row_id'] for r in got], [108])
        self.assertEqual(threads, [threading.current_thread().name])


class ReviewRoundTests(_Base):
    """PR #447 review round: fail-closed placement, identity cleanup,
    loader strictness and log hygiene."""

    def _vac_copy_of_101(self):
        vac = fx._base(301, '2026-03-02', '100.00', pole='Point 1',
                       cu='CU-1')
        vac.update({'__source_sheet_id': 7002, '__sheet_id': 7002,
                    '__is_vac_crew': True})
        return vac

    def test_vac_claimed_unit_blocks_the_case(self):
        # grouping bills a VAC-claimed unit on the VacCrew sheet only and
        # drops the foreman copy: a correction crediting that copy can
        # not be placed -> blocked, never reported APPLIED (no double
        # billing either).
        rows = fx.admitted_rows() + [self._vac_copy_of_101()]
        with self.assertLogs(level='WARNING') as cm:
            groups, summary = self._run(fx.correction_doc(), rows=rows)
        self.assertEqual((summary['applied'], summary['blocked']), (0, 1))
        self.assertEqual(summary['findings']['vac_claimed_unit'], 1)
        self.assertTrue(any('VAC crew' in m for m in cm.output))
        for grows in groups.values():
            self.assertFalse(any(r.get('__corr_credit') for r in grows))

    def test_legacy_primary_identity_blocks_an_owner_change(self):
        with mock.patch.object(generate_weekly_pdfs,
                               'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', False), \
                self.assertLogs(level='WARNING') as cm:
            groups, summary = self._run(fx.correction_doc())
        self.assertEqual((summary['applied'], summary['blocked']), (0, 1))
        self.assertEqual(summary['findings']['variant_not_produced'], 1)
        self.assertTrue(any('PRIMARY_CLAIM_ATTRIBUTION_ENABLED is off' in m
                            for m in cm.output))
        for grows in groups.values():
            self.assertFalse(any(r.get('__corr_credit') for r in grows))
        # same owner (workday only) is still produced in legacy mode
        doc = fx.correction_doc()
        corr = doc['corrections'][0]
        corr.pop('expected_subtotals')
        corr['rows'] = [r for r in corr['rows'] if r['row_id'] == 102]
        with mock.patch.object(generate_weekly_pdfs,
                               'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', False):
            _, summary = self._run(doc)
        self.assertEqual(summary['applied'], 1)

    def test_units_completed_must_be_boolean(self):
        doc = fx.correction_doc()
        doc['corrections'][0]['rows'][0]['expect'][
            'units_completed'] = 'false'
        with self.assertRaises(rc.CorrectionError) as cm:
            rc.parse_corrections(doc)
        self.assertIn('units_completed must be true or false',
                      ' | '.join(cm.exception.problems))

    def test_quantity_uses_the_shared_parser_without_rounding(self):
        doc = fx.correction_doc()
        doc['corrections'][0]['rows'][0]['expect']['quantity'] = 1.004
        cset = rc.parse_corrections(doc)
        corr, entry = cset.by_row[(fx.SHEET, 101)]
        row = fx.admitted_rows()[0]
        row['Quantity'] = 1.001
        self.assertTrue(any(d.startswith('quantity') for d in
                            rc.row_differences(entry, corr, row)))
        corr, entry = rc.parse_corrections(
            fx.correction_doc()).by_row[(fx.SHEET, 101)]
        row['Quantity'] = '1 EA'
        self.assertFalse(any(d.startswith('quantity') for d in
                             rc.row_differences(entry, corr, row)))

    def test_blocked_log_lines_carry_no_cell_values(self):
        rows = fx.admitted_rows()
        rows[1]['Units Total Price'] = '111.00'
        rows[1]['Pole #'] = 'Point 2X'
        rows[1]['Quantity'] = 7.0
        with self.assertLogs(level='INFO') as cm:
            self._run(fx.correction_doc(), rows=rows)
        text = ' | '.join(cm.output)
        for value in ('111.00', 'Point 2X', '7.0', "'Point 2'"):
            self.assertNotIn(value, text)
        self.assertIn('pole, quantity, units_total_price', text)
        # every correction line naming the WR is caught by the marker
        # sweep (GitHub log keeps it; Sentry breadcrumbs drop it)
        for rec in cm.records:
            msg = rec.getMessage()
            if 'correction' in msg and fx.WR in msg:
                self.assertTrue(
                    any(m in msg for m in _obs._PII_LOG_MARKERS), msg)

    def test_credited_identity_found_without_a_live_row(self):
        # row 101 unchecked (fetch drops it) or moved to another week:
        # the case blocks and Foreman B's correction-only identity must
        # still be registered for removal.
        for change in ('removed', 'moved'):
            rows = fx.admitted_rows()
            if change == 'removed':
                rows = [r for r in rows if r['__row_id'] != 101]
            else:
                rows[0]['Weekly Reference Logged Date'] = '2026-03-15'
            with self.assertLogs(level='WARNING'):
                groups, summary = self._run(fx.correction_doc(),
                                            rows=rows)
            self.assertEqual(summary['blocked'], 1, change)
            self.assertNotIn(_FOREMAN_B, groups)
            self.assertIn(_FOREMAN_B, rc.displaced_groups(), change)

    def test_cleanup_compares_identities_not_keys(self):
        names = _real_filenames(self, fx.admitted_rows())
        cache = _cache(names)
        groups, _ = self._run(fx.correction_doc())
        key = '030826_90000001_HELPER2_Helper2_C'
        stale_rows = rc.displaced_groups()[key]
        other = [dict(r, __helper2_foreman='Helper2 Z')
                 for r in stale_rows]
        # same key today, another identity -> the old file is stale
        client = _client()
        self.assertEqual(_remove(dict(groups, **{key: other}), cache,
                                 client), 1)
        self.assertEqual(_deleted(client), [903])
        # another key today carries the same identity -> never deleted
        client = _client()
        same = dict(groups, **{'030826_90000001_HELPER2_Other':
                               [dict(r) for r in stale_rows]})
        self.assertEqual(_remove(same, cache, client), 0)
        self.assertEqual(_deleted(client), [])

    def test_live_listing_decides_removal(self):
        names = _real_filenames(self, fx.admitted_rows())
        cache = _cache(names)
        groups, _ = self._run(fx.correction_doc())
        # run-level live listing lacks it: the stale cache stub loses
        client = _client()
        self.assertEqual(
            _remove(groups, cache, client, live_listings={55: []}), 0)
        self.assertEqual(_deleted(client), [])
        # cache misses it, the on-demand live read has it -> removed
        no_stub = {55: [a for a in cache[55] if a.id != 903]}
        client = _client()
        self.assertEqual(
            _remove(groups, no_stub, client, fetched=cache[55]), 1)
        self.assertEqual(_deleted(client), [903])
        # live read failed -> kept, retried next run
        client = _client()
        with self.assertLogs(level='WARNING') as cm:
            self.assertEqual(_remove(groups, cache, client,
                                     fetched=RuntimeError('down')), 0)
        self.assertEqual(_deleted(client), [])
        self.assertTrue(any('listing unavailable' in m
                            for m in cm.output))

    def test_incremental_full_read_never_writes_recovered_rows(self):
        self._configure(fx.correction_doc())
        rows = fx.admitted_rows()
        rec = fx.recovered_row()
        rec.update(rc.recovery_for_row(rec, fx.SHEET, 108))
        rows.append(rec)
        sent = []

        def _upsert(_sheet_id, _run_id, bucket):
            sent.extend(r['__row_id'] for r in bucket)
            return {'affected': set(), 'status': 'ok'}

        with mock.patch.multiple(
                _orchestrate, RUN_MEMORY_WRITE_ENABLED=True,
                TEST_MODE=False, TIME_BUDGET_MINUTES=0), \
                mock.patch.object(_orchestrate, 'get_all_source_rows',
                                  return_value=rows), \
                mock.patch.object(_orchestrate._mem_reader,
                                  'map_affected_to_sheets',
                                  return_value=set()), \
                mock.patch.object(_orchestrate._mem_writer,
                                  'upsert_rows_bulk_result',
                                  side_effect=_upsert), \
                mock.patch.object(_orchestrate._fn, 'memory_write_blocked',
                                  return_value=False):
            _orchestrate._run_phase2_incremental(
                client=mock.Mock(), source_sheets=[{'id': fx.SHEET}],
                watermarks={}, per_sheet_reasons={fx.SHEET: 'trigger1'},
                mem_run_id='run-x', session_start=datetime.datetime.now())
        self.assertTrue(sent)
        self.assertNotIn(108, sent)

    def test_read_failed_sheet_holds_cleanup(self):
        # the correction's sheet failed to read: the case blocks, its
        # credited identities are rebuilt from the approved entries and
        # no group holds the pair -- cleanup must hold, never delete the
        # published corrected files with no replacement.
        names = _real_filenames(self, fx.admitted_rows())
        cache = _cache(names)
        with self.assertLogs(level='WARNING'):
            groups, summary = self._run(fx.correction_doc(), rows=[])
        self.assertEqual(summary['blocked'], 1)
        getter = 'get_last_full_read_failed_sheet_ids'
        for failed in ({'return_value': {fx.SHEET}},
                       {'side_effect': RuntimeError('unknowable')}):
            client = _client()
            with mock.patch.object(_fetch, getter, **failed), \
                    self.assertLogs(level='WARNING') as cm:
                self.assertEqual(_remove(groups, cache, client), 0)
            self.assertEqual(_deleted(client), [])
            self.assertTrue(any('source sheet read failed' in m
                                for m in cm.output))
            self.assertEqual(
                rc.get_run_counts()['read_failed_held_pairs'], 1)
        # control: only an unrelated sheet failed -> not held
        client = _client()
        with mock.patch.object(_fetch, getter, return_value={1}):
            self.assertGreater(_remove(groups, cache, client), 0)
        self.assertTrue(_deleted(client))

    def test_cleanup_held_outside_both_grouping_mode(self):
        # helper / helper2 identities are not produced outside 'both':
        # a displaced identity cannot be judged stale -> nothing runs.
        names = _real_filenames(self, fx.admitted_rows())
        groups, _ = self._run(fx.correction_doc())
        key = '030826_90000001_HELPER2_Helper2_C'
        other = [dict(r, __helper2_foreman='Helper2 Z')
                 for r in rc.displaced_groups()[key]]
        client = _client()
        with mock.patch.object(generate_weekly_pdfs, 'RES_GROUPING_MODE',
                               'helper'), \
                self.assertLogs(level='WARNING') as cm:
            self.assertEqual(_remove(dict(groups, **{key: other}),
                                     _cache(names), client), 0)
        self.assertEqual(_deleted(client), [])
        client.Attachments.list_row_attachments.assert_not_called()
        self.assertTrue(any('only under RES_GROUPING_MODE=both' in m
                            for m in cm.output))
        self.assertEqual(rc.get_run_counts()['mode_held'], 1)

    def test_retire_with_attribution_off_keeps_the_file(self):
        # applied under attribution on; retired after it was turned off:
        # the stand-in re-groups to another identifier, so the old
        # correction-only file can not be matched -> held and logged.
        applied_names = _real_filenames(
            self, fx.admitted_rows(), doc=fx.correction_doc())
        self.assertIn(_FOREMAN_B, applied_names)
        with mock.patch.object(generate_weekly_pdfs,
                               'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', False):
            groups, summary = self._run(_retired_doc())
            self.assertEqual(summary['retired'], 1)
            client = _client()
            with self.assertLogs(level='WARNING') as cm:
                self.assertEqual(
                    _remove(groups, _cache(applied_names), client), 0)
        self.assertEqual(_deleted(client), [])
        self.assertTrue(any(
            'only under PRIMARY_CLAIM_ATTRIBUTION_ENABLED on' in m
            for m in cm.output))
        self.assertEqual(rc.get_run_counts()['switch_held'], 1)

    def test_feature_off_cleanup_touches_nothing(self):
        # REPORTING_CORRECTIONS_FILE unset: no listing, no delete.
        self.assertIsNone(rc.get_active_set())
        client = _client()
        self.assertEqual(_remove({}, {}, client), 0)
        client.Attachments.list_row_attachments.assert_not_called()
        self.assertEqual(_deleted(client), [])

    def test_preview_reports_the_unsupported_block(self):
        # preview must show BLOCKED (same reason) for a case prepare_run
        # blocks, and print the switches it read.
        cset = rc.load_corrections(self._configure(fx.correction_doc()))
        rows = fx.admitted_rows() + [fx.recovered_row()]
        buf = io.StringIO()
        with mock.patch.object(_config,
                               'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', False):
            code = rc.preview(cset, rows, out=buf)
        text = buf.getvalue()
        self.assertEqual(code, 1)
        self.assertIn('grouping switches read from pipeline.config', text)
        self.assertIn('PRIMARY_CLAIM_ATTRIBUTION_ENABLED=False', text)
        self.assertIn(': BLOCKED', text)
        self.assertIn('PRIMARY_CLAIM_ATTRIBUTION_ENABLED is off', text)
        self.assertIn('blocked=1', text)


if __name__ == '__main__':
    unittest.main()
