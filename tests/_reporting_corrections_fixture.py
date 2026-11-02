"""Synthetic fixture for tests/test_reporting_corrections.py.

Fake people only ("Foreman A", "Foreman B", "Helper H", "Helper2 C"),
fake WRs (90000001 corrected, 90000002 unrelated) and fake sheet / row
ids. Imports nothing from the pipeline so the golden-hash generator can
load it against a pristine checkout too.

Week ending Sunday 2026-03-08: Mon 03-02, Tue 03-03, Wed 03-04 are the
corrected days; Sat 03-07 rows are outside the correction scope.
"""

from __future__ import annotations

import copy

SHEET = 7001
WR = '90000001'
OTHER_WR = '90000002'
WEEK = '2026-03-08'


def _base(row_id, snap, price, *, wr=WR, weekly=WEEK, pole='Point 1',
          cu='CU-1', work_type='Inst', qty=1.0):
    return {
        '__row_id': row_id,
        '__sheet_id': SHEET,
        '__source_sheet_id': SHEET,
        'Work Request #': float(wr),
        'Weekly Reference Logged Date': weekly,
        'Snapshot Date': snap,
        'Units Completed?': True,
        'Units Total Price': price,
        'CU': cu,
        'Work Type': work_type,
        'Pole #': pole,
        'Quantity': qty,
        'Dept #': 884.0,
        'Foreman': 'Foreman A',
        '__effective_user': 'Foreman A',
        '__assignment_method': 'FOREMAN_COLUMN',
        '__is_helper_row': False,
        '__is_helper2_row': False,
        '__is_vac_crew': False,
        '__is_subcontractor': False,
    }


def _helper(row):
    row.update({
        'Foreman Helping?': 'Helper H',
        'Helping Foreman Completed Unit?': True,
        'Helper Dept #': 489.0,
        '__is_helper_row': True,
        '__helper_foreman': 'Helper H',
        '__helper_dept': '489.0',
        '__helper_job': '',
    })
    return row


def _helper2(row):
    row.update({
        'Foreman Helping? #2': 'Helper2 C',
        'Helping Foreman #2 Completed Unit?': True,
        'Helper #2 Dept #': 543.0,
        '__is_helper2_row': True,
        '__helper2_foreman': 'Helper2 C',
        '__helper2_dept': '543.0',
        '__helper2_job': '',
    })
    return row


def admitted_rows():
    """Rows as get_all_source_rows admits them TODAY (no recovery)."""
    rows = [
        _base(101, '2026-03-02', '100.00', pole='Point 1', cu='CU-1'),
        _base(102, '2026-03-02', '110.00', pole='Point 2', cu='CU-2'),
        _base(103, '2026-03-02', '120.00', pole='Point 3', cu='CU-3'),
        _helper(_base(104, '2026-03-03', '200.00', pole='Point 4',
                      cu='CU-4')),
        _helper(_base(105, '2026-03-03', '210.00', pole='Point 5',
                      cu='CU-5')),
        _helper2(_base(106, '2026-03-03', '300.00', pole='Point 6',
                       cu='CU-6', qty=2.0)),
        _helper(_base(107, '2026-03-07', '400.00', pole='Point 7',
                      cu='CU-7')),
        _base(201, '2026-03-02', '55.00', wr=OTHER_WR, pole='Point 9',
              cu='CU-9'),
    ]
    return copy.deepcopy(rows)


def recovered_row():
    """Blank-date row the correction explicitly recovers (price 44.07)."""
    row = _base(108, None, '44.07', weekly=None, pole='Point 8',
                cu='CU-8', work_type='Rem', qty=3.0)
    row['Foreman'] = 'Foreman A'
    return row


def unlisted_blank_row():
    """Blank-date row NOT in the correction -- must stay excluded."""
    return _base(109, None, '9.99', weekly=None, pole='Point 10',
                 cu='CU-10')


def _expect(row):
    def _iso(v):
        return v
    return {
        'pole': row['Pole #'],
        'cu': row['CU'],
        'work_type': row['Work Type'],
        'quantity': row['Quantity'],
        'units_total_price': row['Units Total Price'],
        'snapshot_date': _iso(row['Snapshot Date']),
        'weekly_reference_logged_date': _iso(
            row['Weekly Reference Logged Date']),
        'units_completed': True,
    }


def correction_doc(revision=1, rows=None):
    """The approved correction for WR 90000001 / week 2026-03-08."""
    by_id = {r['__row_id']: r for r in (rows or admitted_rows())}
    by_id[108] = recovered_row()

    def entry(rid, name, variant, dept, workday, **extra):
        item = {
            'sheet_id': SHEET, 'row_id': rid,
            'credit': {'name': name, 'variant': variant, 'dept': dept,
                       'job': None},
            'workday': workday, 'expect': _expect(by_id[rid]),
        }
        item.update(extra)
        return item

    return {
        'schema': 1,
        'corrections': [{
            'id': 'WR90000001-WE2026-03-08',
            'revision': revision,
            'wr': WR,
            'week_ending': WEEK,
            'reason': 'synthetic test case',
            'scope_days': ['2026-03-02', '2026-03-03', '2026-03-04'],
            'expected_subtotals': {
                'Foreman B': {'2026-03-03': '100.00'},
                'Foreman A': {'2026-03-03': '200.00',
                              '2026-03-04': '110.00'},
                'Helper H': {'2026-03-03': '510.00',
                             '2026-03-04': '44.07'},
            },
            'rows': [
                entry(101, 'Foreman B', 'primary', '884', '2026-03-03'),
                entry(102, 'Foreman A', 'primary', '884', '2026-03-04'),
                entry(104, 'Foreman A', 'primary', '884', '2026-03-03'),
                entry(105, 'Helper H', 'helper', '489', '2026-03-03'),
                entry(106, 'Helper H', 'helper', '489', '2026-03-03'),
                entry(108, 'Helper H', 'helper', '489', '2026-03-04',
                      recover_missing_dates=True),
            ],
        }],
    }
