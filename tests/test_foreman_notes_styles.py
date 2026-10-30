"""Phase 15 plan 02 Task 2: palette, descriptor precedence, lazy style fetch.

Fictional data only. Offline by default; two opt-in live classes are skipped
unless FN_LIVE_PROBE=1 (+ token) / FN_PALETTE_LIVE=1.
"""
import json
import logging
import os
import re
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

from pipeline import foreman_notes as fn

SHEET = 5001
MAPPING = {
    'Pole #': 11, 'CU': 12, 'Work Type': 13, 'CU Description': 14,
    'Unit of Measure': 15, 'Quantity': 16, 'Units Total Price': 17,
    'Foreman Notes': 18,
}
YELLOW = ',,,,,,,,,21,,,,,,,'
GREEN = ',,,,,,,,,30,,,,,,,'


class _Sheets:
    def __init__(self, behaviour=None):
        self.calls = []
        self.behaviour = behaviour

    def get_sheet(self, sheet_id, **kwargs):
        self.calls.append((sheet_id, kwargs))
        if self.behaviour is not None:
            return self.behaviour(sheet_id, kwargs)
        ids = [int(x) for x in kwargs['row_ids'].split(',')]
        rows = [
            NS(id=i, conditional_format=YELLOW, format_=None, cells=[])
            for i in ids
        ]
        return NS(rows=rows)


def _client(behaviour=None):
    return NS(Sheets=_Sheets(behaviour))


def _group(n, wr='90003', sheet=SHEET, start=1):
    return [
        {
            'Work Request #': wr, '__source_sheet_id': sheet,
            '__row_id': start + i
        }
        for i in range(n)
    ]


class PaletteTests(unittest.TestCase):
    def test_pinned_values(self):
        self.assertEqual(len(fn.PALETTE), 42)
        self.assertEqual(fn.PALETTE[0], 'none')
        self.assertEqual(fn.PALETTE[3], 'transparent')
        self.assertEqual(fn.PALETTE[21], '#FEFF00')
        self.assertEqual(fn.PALETTE[28], '#FF8D00')
        self.assertEqual(fn.PALETTE[30], '#40B14B')

    def test_style_columns_contract(self):
        self.assertEqual(
            [c for c, _ in fn.STYLE_COLUMNS], [1, 2, 3, 4, 5, 6, 8, 9]
        )
        self.assertEqual(fn.STYLE_COLUMNS[-1], (9, 'Foreman Notes'))
        self.assertEqual(fn.STYLE_KEY, '__fn_style')


class ParseDescriptorTests(unittest.TestCase):
    def test_absent(self):
        self.assertIsNone(fn.parse_descriptor(None))
        self.assertIsNone(fn.parse_descriptor(''))

    def test_background_slot(self):
        self.assertEqual(fn.parse_descriptor(YELLOW), (None, 'FEFF00'))

    def test_text_slot(self):
        self.assertEqual(
            fn.parse_descriptor(',,,,,,,,27,,,,,,,,'), ('EA352E', None)
        )

    def test_none_and_transparent_are_no_colour(self):
        self.assertEqual(
            fn.parse_descriptor(',,,,,,,,0,3,,,,,,,'), (None, None)
        )

    def test_invalid_raises(self):
        for bad in (',' * 17, ',,,,,,,,x,,,,,,,,', ',,,,,,,,,42,,,,,,,',
                    ',,,,,,,,,-1,,,,,,,',
                    ',,,,,,,,,2.0,,,,,,,', 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    fn.parse_descriptor(bad)

    def test_exactly_17_parts_ok(self):
        self.assertEqual(fn.parse_descriptor(',' * 16), (None, None))


class ResolveCellStyleTests(unittest.TestCase):
    def test_all_absent(self):
        self.assertEqual(
            fn.resolve_cell_style(None, None, None, None), (None, None)
        )

    def test_precedence_per_slot(self):
        cell_cf = ',,,,,,,,,21,,,,,,,'      # bg yellow
        row_cf = ',,,,,,,,,30,,,,,,,'       # bg green
        cell_fmt = ',,,,,,,,27,28,,,,,,,'   # text red, bg orange
        row_fmt = ',,,,,,,,1,2,,,,,,,'      # text black, bg white
        self.assertEqual(fn.resolve_cell_style(cell_cf, row_cf, cell_fmt,
                                               row_fmt),
                         ('FEFF00', 'EA352E'))
        self.assertEqual(fn.resolve_cell_style(None, row_cf, cell_fmt,
                                               row_fmt),
                         ('40B14B', 'EA352E'))
        self.assertEqual(fn.resolve_cell_style(None, None, cell_fmt, row_fmt),
                         ('FF8D00', 'EA352E'))
        self.assertEqual(fn.resolve_cell_style(None, None, None, row_fmt),
                         ('FFFFFF', '000000'))

    def test_row_conditional_bg_with_cell_static_text(self):
        self.assertEqual(
            fn.resolve_cell_style(None, YELLOW, ',,,,,,,,27,,,,,,,,', None),
            ('FEFF00', 'EA352E'))

    def test_transparent_slot_falls_through(self):
        self.assertEqual(
            fn.resolve_cell_style(',,,,,,,,,3,,,,,,,', YELLOW, None, None),
            ('FEFF00', None))

    def test_invalid_anywhere_fails_whole_cell(self):
        for args in ((YELLOW, 'garbage', None, None),
                     (None, YELLOW, ',,,,,,,,,99,,,,,,,', None),
                     ('x', YELLOW, None, None), (None, None, None, ',' * 20)):
            with self.subTest(args=args):
                self.assertEqual(fn.resolve_cell_style(*args), (None, None))


class BuildMapsTests(unittest.TestCase):
    def test_build(self):
        got = fn.build_sheet_column_maps([
            {'id': '7', 'column_mapping': {'CU': 1}},
            {'id': 'x', 'column_mapping': {}},
            {'column_mapping': {}},
            None,
            {'id': 9},
        ])
        self.assertEqual(got, {7: {'CU': 1}})


class AttachGroupStylesTests(unittest.TestCase):
    def setUp(self):
        fn.reset_state()
        fn.set_state(fn.FnState(scope='pilot', pilot_wrs=frozenset({'90003'})))
        self.maps = {SHEET: dict(MAPPING)}

    def tearDown(self):
        fn.reset_state()

    def test_non_pilot_group_makes_no_calls(self):
        client = _client()
        rows = _group(3, wr='11111')
        self.assertEqual(fn.attach_group_styles(client, rows, self.maps), 0)
        self.assertEqual(client.Sheets.calls, [])
        self.assertTrue(all(fn.STYLE_KEY not in r for r in rows))

    def test_off_scope_makes_no_calls(self):
        fn.reset_state()
        client = _client()
        self.assertEqual(
            fn.attach_group_styles(client, _group(2), self.maps), 0
        )
        self.assertEqual(client.Sheets.calls, [])

    def test_pilot_group_attaches_row_level_colour_to_every_column(self):
        client = _client()
        rows = _group(2)
        self.assertEqual(fn.attach_group_styles(client, rows, self.maps), 2)
        (sid, kw), = client.Sheets.calls
        self.assertEqual(sid, SHEET)
        self.assertEqual(kw['include'], 'format')
        self.assertEqual(kw['row_ids'], '1,2')
        self.assertEqual(kw['column_ids'], '11,12,13,14,15,16,17,18')
        for r in rows:
            self.assertEqual(
                set(r[fn.STYLE_KEY]), {n for _, n in fn.STYLE_COLUMNS}
            )
            self.assertTrue(
                all(v == ('FEFF00', None) for v in r[fn.STYLE_KEY].values())
            )

    def test_column_ids_limited_to_mapped_names(self):
        maps = {SHEET: {'CU': 12, 'Quantity': 16, 'Other': 99}}
        client = _client()
        fn.attach_group_styles(client, _group(1), maps)
        self.assertEqual(client.Sheets.calls[0][1]['column_ids'], '12,16')

    def test_cell_level_overrides_row_level(self):
        def behaviour(sid, kw):
            cell = NS(column_id=16, conditional_format=GREEN, format_=None)
            return NS(
                rows=[NS(id=1, conditional_format=YELLOW, format_=None,
                         cells=[cell])]
            )
        client = _client(behaviour)
        rows = _group(1)
        fn.attach_group_styles(client, rows, self.maps)
        st = rows[0][fn.STYLE_KEY]
        self.assertEqual(st['Quantity'], ('40B14B', None))
        self.assertEqual(st['CU'], ('FEFF00', None))

    def test_second_call_is_cached(self):
        client = _client()
        fn.attach_group_styles(client, _group(3), self.maps)
        rows = _group(3)
        self.assertEqual(fn.attach_group_styles(client, rows, self.maps), 3)
        self.assertEqual(len(client.Sheets.calls), 1)
        self.assertIn(fn.STYLE_KEY, rows[0])

    def test_chunks_of_100(self):
        client = _client()
        fn.attach_group_styles(client, _group(250), self.maps)
        chunks = [
            len(kw['row_ids'].split(',')) for _, kw in client.Sheets.calls
        ]
        self.assertEqual(chunks, [100, 100, 50])

    def test_one_call_per_sheet(self):
        maps = {SHEET: dict(MAPPING), 6002: dict(MAPPING)}
        rows = _group(2) + _group(2, sheet=6002, start=500)
        client = _client()
        fn.attach_group_styles(client, rows, maps)
        self.assertEqual(
            sorted(c[0] for c in client.Sheets.calls), [SHEET, 6002]
        )

    def test_exception_leaves_rows_plain_and_does_not_raise(self):
        def boom(sid, kw):
            raise ValueError('secret-note-text')
        client = _client(boom)
        rows = _group(2)
        self.assertEqual(fn.attach_group_styles(client, rows, self.maps), 0)
        self.assertTrue(all(fn.STYLE_KEY not in r for r in rows))

    def test_missing_response_row_is_plain(self):
        def behaviour(sid, kw):
            return NS(
                rows=[NS(id=1, conditional_format=YELLOW, format_=None,
                         cells=[])]
            )
        rows = _group(2)
        self.assertEqual(
            fn.attach_group_styles(_client(behaviour), rows, self.maps), 1
        )
        self.assertIn(fn.STYLE_KEY, rows[0])
        self.assertNotIn(fn.STYLE_KEY, rows[1])

    def test_unknown_sheet_or_missing_ids_skipped(self):
        client = _client()
        rows = [
            {'Work Request #': '90003'},
            {'Work Request #': '90003', '__source_sheet_id': 1}
        ]
        self.assertEqual(fn.attach_group_styles(client, rows, self.maps), 0)
        rows = _group(1, sheet=424242)
        self.assertEqual(fn.attach_group_styles(client, rows, self.maps), 0)
        self.assertEqual(client.Sheets.calls, [])

    def test_only_allowed_row_keys_touched(self):
        allowed = {
            '__source_sheet_id', '__row_id', fn.STYLE_KEY, 'Work Request #'
        }
        seen = set()

        class Spy(dict):
            def __getitem__(self, k):
                seen.add(k)
                return super().__getitem__(k)

            def get(self, k, d=None):
                seen.add(k)
                return super().get(k, d)

            def __setitem__(self, k, v):
                seen.add(k)
                super().__setitem__(k, v)

        rows = [Spy(r) for r in _group(2)]
        fn.attach_group_styles(_client(), rows, self.maps)
        self.assertTrue(seen <= allowed, seen - allowed)

    def test_logs_carry_no_fixture_text(self):
        def boom(sid, kw):
            raise ValueError('Avery Example note text')
        rows = _group(2)
        rows[0]['Foreman Notes'] = 'Avery Example note text'
        with self.assertLogs(level='WARNING') as cm:
            fn.attach_group_styles(_client(boom), rows, self.maps)
        text = ' '.join(r.getMessage() for r in cm.records)
        for needle in ('Avery', 'note text', '90003', YELLOW):
            self.assertNotIn(needle, text)


class ReadOnlyModuleTests(unittest.TestCase):
    def test_no_write_api_referenced(self):
        src = Path(fn.__file__).read_text(encoding='utf-8')
        for token in ('update_rows', 'add_rows', 'attach_file', 'delete_'):
            self.assertNotIn(token, src)


@unittest.skipUnless(
    os.environ.get(
        'FN_LIVE_PROBE'
    ) == '1' and os.environ.get('SMARTSHEET_API_TOKEN'),
    'live probe is opt-in: FN_LIVE_PROBE=1 and SMARTSHEET_API_TOKEN',
)
class LiveRowIdsProbeTests(unittest.TestCase):
    def test_row_ids_form_returns_conditional_format(self):
        import smartsheet
        client = smartsheet.Smartsheet(os.environ['SMARTSHEET_API_TOKEN'])
        client.errors_as_exceptions(True)
        sheet_id = 3756603854507908
        base = client.Sheets.get_sheet(sheet_id, page_size=5)
        ids = ','.join(str(r.id) for r in base.rows[:5])
        got = client.Sheets.get_sheet(sheet_id, include='format', row_ids=ids)
        self.assertTrue(
            any(getattr(r, 'conditional_format', None) for r in got.rows)
        )


@unittest.skipUnless(os.environ.get('FN_PALETTE_LIVE') == '1',
                     'palette drift check is opt-in: FN_PALETTE_LIVE=1')
class LivePaletteDriftTests(unittest.TestCase):
    def test_palette_matches_serverinfo(self):
        with urllib.request.urlopen(
            'https://api.smartsheet.com/2.0/serverinfo', timeout=30
        ) as r:
            info = json.loads(r.read().decode('utf-8'))
        self.assertEqual(tuple(info['formats']['color']), fn.PALETTE)


if __name__ == '__main__':
    unittest.main()
