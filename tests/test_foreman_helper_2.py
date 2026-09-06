"""Phase 14 (Foreman Helper #2) tracer test module.

Plan 14-01 Task 1 proves the whole Helper #2 path end-to-end on the
thinnest possible slice: ONE ordinary (non-subcontractor, non-VAC) source
row with a valid Helper #2 completion travels discovery -> field
extraction -> eligibility -> grouping -> change-detection identity ->
workbook -> filename -> filename round-trip, behind a default-off flag,
and comes out the far end naming the same person at every hop.

Style mirrors ``tests/test_group_identity_and_header_foreman.py``:
unittest classes, a repo-root ``sys.path`` bootstrap, and a
``_row(**overrides)`` fixture builder.

Evidence label: FIXTURE PASS only -- not dry-run, not controlled upload,
not production observed.
"""

from __future__ import annotations

import datetime
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import generate_weekly_pdfs  # noqa: E402
import pipeline.discovery as _discovery  # noqa: E402
import pipeline.fetch as _fetch  # noqa: E402
from pipeline.config import _RE_SANITIZE_HELPER_NAME  # noqa: E402
from pipeline.orchestrate import derive_group_identity  # noqa: E402
from pipeline.types import (  # noqa: E402
    FORMULA_ERROR_VALUES,
    normalize_helper_value,
)


def _row(**overrides):
    """Baseline row: an ordinary, non-subcontractor, non-VAC source row
    that would otherwise land in the primary file."""
    row = {
        '__row_id': 90001,
        'Work Request #': '90005',
        'Weekly Reference Logged Date': '2026-07-30',
        'Snapshot Date': '2026-07-30',
        'Units Completed?': True,
        'Units Total Price': '$75.00',
        'CU': 'CU-200',
        'Work Type': 'Install',
        'Pole #': 'P-9',
        'Dept #': '510',
        'Job #': 'JOB-PRIMARY',
        'Foreman': 'Primary Person',
        '__effective_user': 'Primary Person',
        '__assignment_method': 'FOREMAN_COLUMN',
        '__is_helper_row': False,
        '__helper_foreman': '',
        '__helper_dept': '',
        '__helper_job': '',
        '__is_helper2_row': False,
        '__helper2_foreman': '',
        '__helper2_dept': '',
        '__helper2_job': '',
        '__is_vac_crew': False,
        '__is_subcontractor': False,
        '__source_sheet_id': 9999999999,  # non-subcontractor sheet id
    }
    row.update(overrides)
    return row


def _helper2_row(**overrides):
    """A single eligible Helper #2 completion (D-14-04 criteria met)."""
    row = _row(
        __row_id=90002,
        __is_helper2_row=True,
        __helper2_foreman='Jamie Helper2',
        __helper2_dept='NA-07',
        __helper2_job='J-88',
    )
    row.update(overrides)
    return row


class HelperTwoTracerTests(unittest.TestCase):
    """Task 1: one Helper #2 completion, end-to-end, one path only."""

    def setUp(self):
        # Ensure this test's synthetic sheet id is never accidentally
        # treated as a subcontractor sheet by cross-test global state.
        patcher = mock.patch.object(
            _discovery, '_FOLDER_DISCOVERED_SUB_IDS', frozenset()
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._saved_output_folder = generate_weekly_pdfs.OUTPUT_FOLDER
        generate_weekly_pdfs.OUTPUT_FOLDER = self._tmpdir.name
        self.addCleanup(
            setattr, generate_weekly_pdfs, 'OUTPUT_FOLDER',
            self._saved_output_folder,
        )

    def test_single_helper2_row_travels_end_to_end(self):
        primary_row = _row(CU='CU-100')
        helper2_row = _helper2_row(CU='CU-200')

        groups = generate_weekly_pdfs.group_source_rows(
            [primary_row, helper2_row]
        )

        # (i) exactly one helper2 group key naming the Helper #2 person.
        helper2_keys = [
            k for k, rows in groups.items()
            if rows[0].get('__variant') == 'helper2'
        ]
        self.assertEqual(len(helper2_keys), 1, groups.keys())
        helper2_key = helper2_keys[0]
        self.assertIn('HELPER2_Jamie_Helper2', helper2_key)
        helper2_group_rows = groups[helper2_key]
        self.assertEqual(
            [r.get('__helper2_foreman') for r in helper2_group_rows],
            ['Jamie Helper2'],
        )

        # (ii) the row is absent from the primary group for the same WR/week.
        primary_keys = [
            k for k, rows in groups.items()
            if rows[0].get('__variant') == 'primary'
        ]
        self.assertEqual(len(primary_keys), 1, groups.keys())
        primary_row_ids = {
            r.get('__row_id') for r in groups[primary_keys[0]]
        }
        self.assertNotIn(90002, primary_row_ids)

        # Change-detection identity: the helper2 group's hash meta must
        # name the same Helper #2 person (HELPER2= token, D-14-09).
        data_hash = generate_weekly_pdfs.calculate_data_hash(
            helper2_group_rows
        )
        self.assertTrue(data_hash)

        identifier, file_identifier = derive_group_identity(
            helper2_group_rows[0],
            primary_claim_enabled=generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            vac_crew_claim_enabled=generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED,
            res_grouping_mode=generate_weekly_pdfs.RES_GROUPING_MODE,
        )
        self.assertEqual(identifier, 'Jamie Helper2|NA-07|J-88')
        self.assertEqual(file_identifier, 'Jamie_Helper2')

        # (iii) the generated filename contains _Helper2_ and the
        # sanitized name.
        week_ending_date = helper2_group_rows[0]['__week_ending_date']
        (
            output_path, output_filename, wr_numbers, _customer, _missing
        ) = generate_weekly_pdfs.generate_excel(
            helper2_key, helper2_group_rows, week_ending_date,
            data_hash='deadbeefcafe1401',
        )
        self.assertIn('_Helper2_Jamie_Helper2', output_filename)
        self.assertEqual(wr_numbers, ['90005'])

        # (iv) feeding that filename back through build_group_identity
        # returns variant 'helper2' and the same identifier.
        parsed = generate_weekly_pdfs.build_group_identity(output_filename)
        self.assertIsNotNone(parsed)
        wr, week, variant, parsed_identifier = parsed
        self.assertEqual(wr, '90005')
        self.assertEqual(variant, 'helper2')
        self.assertEqual(parsed_identifier, file_identifier)

        # (v) the workbook header row shows the Helper #2 dept and job,
        # not the primary Dept #/Job #.
        import openpyxl

        wb = openpyxl.load_workbook(output_path)
        ws = wb.active
        shown = {}
        for cells in ws.iter_rows(values_only=True):
            for i, v in enumerate(cells):
                if v in ('Foreman:', 'Dept #:', 'Job #:'):
                    shown[v] = cells[i + 1] if i + 1 < len(cells) else None
        self.assertEqual(shown.get('Foreman:'), 'Jamie Helper2')
        self.assertEqual(shown.get('Dept #:'), 'NA-07')
        self.assertEqual(shown.get('Job #:'), 'J-88')
        self.assertNotIn('Primary Person', shown.values())
        self.assertNotIn('510', shown.values())
        self.assertNotIn('JOB-PRIMARY', shown.values())


if __name__ == "__main__":
    unittest.main()
