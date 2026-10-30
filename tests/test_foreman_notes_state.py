"""Phase 15 plan 02 Task 1: effective scope, GF map, pilot predicate.

Fictional names only (public repo). No network: fake clients via SimpleNamespace.
"""
import logging
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from pipeline import config
from pipeline import foreman_notes as fn
from pipeline.orchestrate import derive_row_wr

WR_COL = 111
GF_COL = 222
SHEET = 999


def _col(cid, title):
    return NS(id=cid, title=title)


def _row(wr, gf, wr_attr='value'):
    cells = [
        NS(column_id=WR_COL, value=wr if wr_attr == 'value' else None,
           display_value=wr if wr_attr == 'display' else None),
        NS(column_id=GF_COL, value=gf, display_value=None),
    ]
    return NS(cells=cells)


def _sheet(rows, wr_title='Work Request #', gf_title='General Foreman', total=None):
    return NS(
        columns=[_col(WR_COL, wr_title), _col(GF_COL, gf_title)],
        rows=rows,
        total_row_count=len(rows) if total is None else total,
    )


class _Sheets:
    def __init__(self, sheet=None, exc=None):
        self.sheet = sheet
        self.exc = exc
        self.calls = []

    def get_sheet(self, sheet_id, **kwargs):
        self.calls.append((sheet_id, kwargs))
        if self.exc:
            raise self.exc
        return self.sheet


def _client(sheet=None, exc=None):
    return NS(Sheets=_Sheets(sheet, exc))


class EffectiveScopeTests(unittest.TestCase):
    def tearDown(self):
        fn.reset_state()

    def _scope(self, configured, test_mode, upload, mem):
        return fn.compute_effective_scope(
            configured, test_mode=test_mode, upload_enabled=upload,
            memory_write_possible=mem,
        )

    def test_production_cron_is_off(self):
        self.assertEqual(self._scope('pilot', False, False, True), 'off')

    def test_skip_upload_alone_never_enables(self):
        self.assertEqual(self._scope('pilot', False, False, False), 'off')

    def test_dry_run_without_write_paths_is_pilot(self):
        self.assertEqual(self._scope('pilot', True, False, False), 'pilot')

    def test_dry_run_with_write_paths_is_off_with_one_warning(self):
        with self.assertLogs(level='WARNING') as cm:
            self.assertEqual(self._scope('pilot', True, False, True), 'off')
        self.assertEqual(len(cm.records), 1)

    def test_rollout_is_configured_scope(self):
        self.assertEqual(self._scope('pilot', False, True, True), 'pilot')
        self.assertEqual(self._scope('all', False, True, True), 'all')

    def test_off_and_invalid(self):
        for t in (True, False):
            for u in (True, False):
                for m in (True, False):
                    self.assertEqual(self._scope('off', t, u, m), 'off')
        with self.assertLogs(level='WARNING') as cm:
            self.assertEqual(self._scope('bogus', True, True, False), 'off')
        self.assertEqual(len(cm.records), 1)

    def test_all_gates_like_pilot(self):
        self.assertEqual(self._scope('all', True, False, False), 'all')
        self.assertEqual(self._scope('all', False, False, False), 'off')


class MemoryWriteBlockedTests(unittest.TestCase):
    def setUp(self):
        fn.reset_state()

    def tearDown(self):
        fn.reset_state()

    def test_blocked_only_for_dry_run_pilot(self):
        with mock.patch.object(fn, 'EFFECTIVE_SCOPE', 'pilot'), \
                mock.patch.object(config, 'TEST_MODE', True), \
                mock.patch.object(config, 'FOREMAN_NOTES_UPLOAD', False):
            self.assertTrue(fn.is_dry_run_pilot())
            self.assertTrue(fn.memory_write_blocked('row_state'))

    def test_not_blocked_when_off_or_rollout(self):
        with mock.patch.object(fn, 'EFFECTIVE_SCOPE', 'off'), \
                mock.patch.object(config, 'TEST_MODE', True):
            self.assertFalse(fn.memory_write_blocked('row_state'))
        with mock.patch.object(fn, 'EFFECTIVE_SCOPE', 'pilot'), \
                mock.patch.object(config, 'TEST_MODE', False), \
                mock.patch.object(config, 'FOREMAN_NOTES_UPLOAD', True):
            self.assertFalse(fn.is_dry_run_pilot())
            self.assertFalse(fn.memory_write_blocked('row_state'))

    def test_error_logged_once_per_kind_and_reset_clears(self):
        with mock.patch.object(fn, 'EFFECTIVE_SCOPE', 'pilot'), \
                mock.patch.object(config, 'TEST_MODE', True), \
                mock.patch.object(config, 'FOREMAN_NOTES_UPLOAD', False):
            with self.assertLogs(level='ERROR') as cm:
                fn.memory_write_blocked('row_state')
                fn.memory_write_blocked('row_state')
            self.assertEqual(len(cm.records), 1)
            with self.assertLogs(level='ERROR') as cm:
                fn.memory_write_blocked('group_state')
            self.assertEqual(len(cm.records), 1)
            fn.reset_state()
            with self.assertLogs(level='ERROR') as cm:
                fn.memory_write_blocked('row_state')
            self.assertEqual(len(cm.records), 1)


class MarkerTests(unittest.TestCase):
    def test_marker_follows_scope(self):
        with mock.patch.object(fn, 'EFFECTIVE_SCOPE', 'off'):
            self.assertFalse(fn.mapping_enabled())
            self.assertEqual(fn.mapping_schema_marker('helper2-v1'), 'helper2-v1')
        with mock.patch.object(fn, 'EFFECTIVE_SCOPE', 'pilot'):
            self.assertTrue(fn.mapping_enabled())
            self.assertEqual(fn.mapping_schema_marker('helper2-v1'), 'helper2-v1+fn1')


class NormalizeTests(unittest.TestCase):
    def test_name_normalisation(self):
        self.assertEqual(fn.normalize_name('  avery   EXAMPLE '),
                         fn.normalize_name('Avery Example'))
        for v in ('NA', 'na', ' Na ', '', None):
            self.assertEqual(fn.normalize_name(v), '')

    def test_allowlist(self):
        self.assertEqual(fn.parse_allowlist(''), frozenset())
        self.assertEqual(fn.parse_allowlist(None), frozenset())
        self.assertEqual(
            fn.parse_allowlist(' Avery  Example, ,pat example ,NA'),
            frozenset({'avery example', 'pat example'}),
        )


class LoadGfMapTests(unittest.TestCase):
    def test_happy_path_and_wr_float(self):
        client = _client(_sheet([_row('90003.0', 'Avery Example'),
                                 _row('90004', ' pat   example')]))
        got = fn.load_gf_map(client, SHEET, WR_COL, GF_COL)
        self.assertEqual(got, {'90003': 'avery example', '90004': 'pat example'})
        (sid, kwargs), = client.Sheets.calls
        self.assertEqual(sid, SHEET)
        self.assertEqual(kwargs['column_ids'], f'{WR_COL},{GF_COL}')

    def test_display_value_fallback(self):
        client = _client(_sheet([_row('90005', 'Avery Example', wr_attr='display')]))
        self.assertEqual(fn.load_gf_map(client, SHEET, WR_COL, GF_COL),
                         {'90005': 'avery example'})

    def test_title_mismatch_is_none(self):
        for kw in ({'wr_title': 'Other'}, {'gf_title': 'Other'}):
            client = _client(_sheet([_row('90003', 'Avery Example')], **kw))
            self.assertIsNone(fn.load_gf_map(client, SHEET, WR_COL, GF_COL))

    def test_exception_is_none(self):
        client = _client(exc=ValueError('boom'))
        self.assertIsNone(fn.load_gf_map(client, SHEET, WR_COL, GF_COL))

    def test_duplicates(self):
        client = _client(_sheet([
            _row('90003', 'Avery Example'), _row('90003', 'Pat Example'),
            _row('90004', 'Avery Example'), _row('90004', ' avery  example'),
        ]))
        got = fn.load_gf_map(client, SHEET, WR_COL, GF_COL)
        self.assertNotIn('90003', got)
        self.assertEqual(got['90004'], 'avery example')

    def test_short_read_warns_and_fails_closed(self):
        client = _client(_sheet([_row('90003', 'Avery Example')], total=5))
        with self.assertLogs(level='WARNING'):
            got = fn.load_gf_map(client, SHEET, WR_COL, GF_COL)
        self.assertIsNone(got)


class InitializeTests(unittest.TestCase):
    def setUp(self):
        fn.reset_state()

    def tearDown(self):
        fn.reset_state()

    def _init(self, scope, allowlist, client):
        with mock.patch.object(fn, 'EFFECTIVE_SCOPE', scope), \
                mock.patch.object(config, 'FOREMAN_NOTES_PILOT_GFS', allowlist), \
                mock.patch.object(config, 'FOREMAN_NOTES_GF_WR_COLUMN_ID', WR_COL), \
                mock.patch.object(config, 'FOREMAN_NOTES_GF_COLUMN_ID', GF_COL):
            return fn.initialize(client)

    def test_off_makes_no_calls(self):
        client = _client(_sheet([]))
        state = self._init('off', 'Avery Example', client)
        self.assertEqual(state.scope, 'off')
        self.assertEqual(client.Sheets.calls, [])
        self.assertFalse(fn.is_pilot_row({'Work Request #': '90003'}))

    def test_all_makes_no_calls_and_every_wr_is_pilot(self):
        client = _client(_sheet([]))
        state = self._init('all', '', client)
        self.assertEqual(state.scope, 'all')
        self.assertEqual(client.Sheets.calls, [])
        self.assertTrue(fn.is_pilot_row({'Work Request #': '12345.0'}))
        self.assertFalse(fn.is_pilot_row({'Work Request #': ''}))
        self.assertFalse(fn.is_pilot_row({}))

    def test_pilot_one_call_with_both_ids(self):
        client = _client(_sheet([_row('90003', 'Avery Example'),
                                 _row('90004', 'Jordan Sample')]))
        state = self._init('pilot', 'avery  example', client)
        self.assertEqual(len(client.Sheets.calls), 1)
        self.assertEqual(client.Sheets.calls[0][1]['column_ids'], f'{WR_COL},{GF_COL}')
        self.assertTrue(state.gf_loaded)
        self.assertEqual(state.pilot_wrs, frozenset({'90003'}))
        self.assertTrue(fn.is_pilot_row({'Work Request #': '90003.0'}))
        self.assertFalse(fn.is_pilot_row({'Work Request #': '90004'}))
        self.assertTrue(fn.is_pilot_group([{'Work Request #': 90003}]))

    def test_empty_allowlist_fail_closed_with_log(self):
        client = _client(_sheet([_row('90003', 'Avery Example')]))
        with self.assertLogs(level='INFO') as cm:
            state = self._init('pilot', '', client)
        self.assertEqual(client.Sheets.calls, [])
        self.assertEqual(state.pilot_wrs, frozenset())
        self.assertTrue(any('pilot allowlist empty' in r.getMessage()
                            and '0' in r.getMessage() for r in cm.records))

    def test_gf_failure_yields_no_pilot(self):
        client = _client(exc=RuntimeError('x'))
        state = self._init('pilot', 'Avery Example', client)
        self.assertFalse(state.gf_loaded)
        self.assertEqual(state.pilot_wrs, frozenset())

    def test_logs_contain_no_names_or_wrs(self):
        client = _client(_sheet([_row('90003', 'Avery Example')]))
        with self.assertLogs(level='INFO') as cm:
            self._init('pilot', 'Avery Example', client)
            logging.info('sentinel')
        text = ' '.join(r.getMessage() for r in cm.records).casefold()
        self.assertNotIn('avery', text)
        self.assertNotIn('90003', text)

    def test_state_is_frozen(self):
        with self.assertRaises(Exception):
            fn.get_state().scope = 'all'


class PilotPredicateTests(unittest.TestCase):
    def tearDown(self):
        fn.reset_state()

    def test_empty_group_not_pilot(self):
        fn.set_state(fn.FnState(scope='all'))
        self.assertFalse(fn.is_pilot_group([]))

    def test_same_wr_string_as_derive_row_wr(self):
        fn.set_state(fn.FnState(scope='pilot', pilot_wrs=frozenset({'90_3', '90003'})))
        for raw in ('90003.0', 90003, '90 3', 'ab/cd', '', None, 'X' * 80):
            row = {'Work Request #': raw}
            self.assertEqual(fn.norm_wr(raw), derive_row_wr(row))
        self.assertTrue(fn.is_pilot_row({'Work Request #': '90 3'}))


class ImportDefaultsTests(unittest.TestCase):
    def _run(self, extra_env):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('TEST_MODE', 'SKIP_UPLOAD', 'FOREMAN_NOTES',
                                    'SUPABASE_HASH_STORE_WRITE', 'RUN_MEMORY_WRITE'))}
        env.update(extra_env)
        env['SMARTSHEET_API_TOKEN'] = ''
        out = subprocess.run(
            [sys.executable, '-c',
             'import pipeline.foreman_notes as f; print(f.EFFECTIVE_SCOPE)'],
            capture_output=True, text=True, env=env, check=True,
        )
        return out.stdout.strip().splitlines()[-1]

    def test_defaults(self):
        self.assertEqual(self._run({}), 'off')
        self.assertEqual(self._run({'SKIP_UPLOAD': 'true'}), 'off')
        self.assertEqual(self._run({'TEST_MODE': 'true'}), 'off')
        self.assertEqual(
            self._run({'TEST_MODE': 'true', 'SUPABASE_HASH_STORE_WRITE_ENABLED': '0',
                       'RUN_MEMORY_WRITE_ENABLED': '0'}),
            'pilot')

    def test_allowlist_code_default_is_empty(self):
        out = subprocess.run(
            [sys.executable, '-c',
             'import pipeline.config as c; print(repr(c.FOREMAN_NOTES_PILOT_GFS))'],
            capture_output=True, text=True, check=True,
            env={k: v for k, v in os.environ.items() if k != 'FOREMAN_NOTES_PILOT_GFS'},
        )
        self.assertEqual(out.stdout.strip().splitlines()[-1], "''")


if __name__ == '__main__':
    unittest.main()
