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
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import generate_weekly_pdfs  # noqa: E402
import pipeline.attribution as _attribution  # noqa: E402
import pipeline.discovery as _discovery  # noqa: E402
import pipeline.fetch as _fetch  # noqa: E402
import pipeline.grouping as _grouping  # noqa: E402
import pipeline.orchestrate as _orchestrate  # noqa: E402
from pipeline.config import _RE_SANITIZE_HELPER_NAME  # noqa: E402
from pipeline.orchestrate import derive_group_identity  # noqa: E402
from pipeline.types import (  # noqa: E402
    FORMULA_ERROR_VALUES,
    normalize_helper_value,
)
from tests.test_billing_audit_shadow import (  # noqa: E402
    _make_fake_supabase_client,
    _reset_all,
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


def _both_helpers_row(**overrides):
    """A row with BOTH a valid Helper #1 AND a valid Helper #2
    completion -- the O-14-A conflict case
    (.planning/phases/14-foreman-helper-2/14-DECISIONS.md
    'O-14-A RESOLVED')."""
    row = _helper2_row(
        __row_id=90003,
        __is_helper_row=True,
        __helper_foreman='Helper1 Person',
        __helper_dept='500',
        __helper_job='JOB-A',
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


class HelperTwoFabricatedClaimGuardTests(unittest.TestCase):
    """Task 3 (14-01): every non-claim input is proven inert on the
    Helper #2 detection path (HLP-05 / HLP-03, D-14-05)."""

    def setUp(self):
        # HELPER2_ENABLED defaults OFF (D-14-12) -- these tests probe the
        # detection FORMULA itself, so enable the flag here; the one test
        # that specifically proves the flag-off behavior overrides this
        # locally.
        patcher = mock.patch.object(_fetch, 'HELPER2_ENABLED', True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _detect(self, foreman_helping2, *, completed=True,
                units_completed=True, dept='NA-01', job='J-1',
                sheet_has_helper2_columns=True):
        row_data = {
            'Foreman Helping? #2': foreman_helping2,
            'Helping Foreman #2 Completed Unit?': completed,
            'Helper #2 Dept #': dept,
            'Helper #2 Job #': job,
        }
        is_claim = _fetch._detect_helper2_row(
            row_data,
            sheet_has_helper2_columns=sheet_has_helper2_columns,
            units_completed_checked=units_completed,
        )
        return is_claim, row_data

    def test_blank_value_is_no_claim(self):
        is_claim, row_data = self._detect('')
        self.assertFalse(is_claim)
        self.assertFalse(row_data['__is_helper2_row'])
        self.assertNotIn('__helper2_foreman', row_data)

    def test_none_value_is_no_claim(self):
        is_claim, row_data = self._detect(None)
        self.assertFalse(is_claim)
        self.assertFalse(row_data['__is_helper2_row'])

    def test_whitespace_only_value_is_no_claim(self):
        is_claim, _ = self._detect('   ')
        self.assertFalse(is_claim)

    def test_na_variants_are_no_claim(self):
        # D-14-05: the case Helper #1 gets wrong today (accepts "NA" as a
        # fabricated name) -- Helper #2 must reject it from day one.
        for value in ('NA', 'na', 'Na', ' NA '):
            with self.subTest(value=value):
                is_claim, _ = self._detect(value)
                self.assertFalse(is_claim)

    def test_every_formula_error_value_is_no_claim(self):
        self.assertIn('#NO MATCH', FORMULA_ERROR_VALUES)
        for value in sorted(FORMULA_ERROR_VALUES):
            with self.subTest(value=value):
                is_claim, _ = self._detect(value)
                self.assertFalse(is_claim)
            with self.subTest(value=value.lower()):
                is_claim, _ = self._detect(value.lower())
                self.assertFalse(is_claim)

    def test_unchecked_completion_is_no_claim(self):
        is_claim, _ = self._detect('Jamie Helper2', completed=False)
        self.assertFalse(is_claim)

    def test_unchecked_units_completed_is_no_claim(self):
        is_claim, _ = self._detect('Jamie Helper2', units_completed=False)
        self.assertFalse(is_claim)

    def test_capability_absent_disables_detection_for_an_otherwise_valid_row(self):
        is_claim, row_data = self._detect(
            'Jamie Helper2', sheet_has_helper2_columns=False
        )
        self.assertFalse(is_claim)
        self.assertFalse(row_data['__is_helper2_row'])

    def test_helper2_enabled_off_disables_detection_for_an_otherwise_valid_row(self):
        with mock.patch.object(_fetch, 'HELPER2_ENABLED', False):
            is_claim, row_data = self._detect('Jamie Helper2')
        self.assertFalse(is_claim)
        self.assertFalse(row_data['__is_helper2_row'])

    def test_valid_name_and_both_checkboxes_is_a_claim(self):
        # Sanity control -- the fixture battery above is not accidentally
        # rejecting everything.
        is_claim, row_data = self._detect('Jamie Helper2')
        self.assertTrue(is_claim)
        self.assertTrue(row_data['__is_helper2_row'])
        self.assertEqual(row_data['__helper2_foreman'], 'Jamie Helper2')

    def test_job_blank_still_proceeds_as_a_claim(self):
        # Case 8: dept present, job blank -> claim proceeds (job optional,
        # mirrors Helper #1). The missing-job informational log is
        # grouping.py's HELPER_JOB= meta-block responsibility, not fetch's.
        is_claim, row_data = self._detect('Jamie Helper2', job='')
        self.assertTrue(is_claim)
        self.assertEqual(row_data['__helper2_job'], '')

    def test_dept_blank_row_is_still_flagged_is_helper2_row(self):
        # fetch.py does not itself validate dept presence -- that is
        # grouping.py's job (see HelperTwoMissingDeptExclusionTests below,
        # case 7). __is_helper2_row is True here; the dept field is blank.
        is_claim, row_data = self._detect('Jamie Helper2', dept='')
        self.assertTrue(is_claim)
        self.assertEqual(row_data['__helper2_dept'], '')


class HelperTwoMissingDeptExclusionTests(unittest.TestCase):
    """Case 7 (Task 3, D-14-04): a valid claim (name + both checkboxes)
    with a blank Helper #2 Dept # produces no helper2 group; the row
    still reaches wherever today's Helper #1/primary logic sends it."""

    def setUp(self):
        patcher = mock.patch.object(
            _discovery, '_FOLDER_DISCOVERED_SUB_IDS', frozenset()
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_dept_produces_no_helper2_group(self):
        row = _helper2_row(__helper2_dept='')
        groups = generate_weekly_pdfs.group_source_rows([row])

        helper2_keys = [
            k for k, rows in groups.items()
            if rows[0].get('__variant') == 'helper2'
        ]
        self.assertEqual(helper2_keys, [], groups.keys())

        # The row still reaches the primary file -- exactly what happens
        # to an invalid Helper #1 claim today (grouping.py's existing
        # "missing required Dept #... including in main Excel" fallback).
        primary_keys = [
            k for k, rows in groups.items()
            if rows[0].get('__variant') == 'primary'
        ]
        self.assertEqual(len(primary_keys), 1, groups.keys())
        primary_row_ids = {
            r.get('__row_id') for r in groups[primary_keys[0]]
        }
        self.assertIn(90002, primary_row_ids)


class HelperTwoCapabilityAbsentDiscoveryTests(unittest.TestCase):
    """Case 9 (Task 3, D-14-01/D-14-04): an Intake-8-shaped sheet (Helper
    #1 columns present, none of the six Helper #2 titles) is a legitimate
    capability-absent mapping outcome, not a discovery failure -- and the
    computed capability boolean correctly disables Helper #2 detection
    without touching Helper #1's own columns."""

    _SHEET_ID = 3333333333

    def _build_mock_client(self):
        from smartsheet.models.column import Column
        from smartsheet.models.sheet import Sheet as _Sheet

        titles = [
            'Weekly Reference Logged Date',
            'Work Request #',
            'Foreman Helping?',
            'Helping Foreman Completed Unit?',
            'Helper Dept #',
            'Helper Job [#]',
        ]
        columns = [
            Column({'id': 2000 + i, 'title': t, 'type': 'TEXT_NUMBER'})
            for i, t in enumerate(titles)
        ]
        sheet = _Sheet({
            'id': self._SHEET_ID, 'name': 'Intake-8-shaped Sheet',
            'columns': [], 'rows': [],
        })
        sheet.columns = columns
        sheet.rows = []
        mock_client = mock.MagicMock()
        mock_client.Sheets.get_sheet.return_value = sheet
        return mock_client

    def test_sheet_without_helper2_columns_is_not_rejected(self):
        client = self._build_mock_client()
        saved_env = {
            k: os.environ.get(k) for k in (
                'LIMITED_SHEET_IDS', 'FORCE_REDISCOVERY',
                'SUBCONTRACTOR_FOLDER_IDS', 'ORIGINAL_CONTRACT_FOLDER_IDS',
            )
        }
        saved_attrs = {
            k: getattr(generate_weekly_pdfs, k) for k in (
                'FORCE_REDISCOVERY', 'SUBCONTRACTOR_FOLDER_IDS',
                'ORIGINAL_CONTRACT_FOLDER_IDS',
            )
        }
        try:
            os.environ['LIMITED_SHEET_IDS'] = str(self._SHEET_ID)
            os.environ['FORCE_REDISCOVERY'] = '1'
            os.environ['SUBCONTRACTOR_FOLDER_IDS'] = ''
            os.environ['ORIGINAL_CONTRACT_FOLDER_IDS'] = ''
            generate_weekly_pdfs.FORCE_REDISCOVERY = True
            generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS = []
            generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS = []
            discovered = generate_weekly_pdfs.discover_source_sheets(client)
        finally:
            for k, v in saved_attrs.items():
                setattr(generate_weekly_pdfs, k, v)
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        # Not rejected: discovery returned a real mapping (the fixture
        # never routed into the failed-read / strict-mode-reject path).
        self.assertEqual(len(discovered), 1, discovered)
        mapping = discovered[0]['column_mapping']
        for helper2_title in (
            'Foreman Helping? #2', 'Helping Foreman #2 Completed Unit?',
            'Helper #2 Dept #',
        ):
            self.assertNotIn(helper2_title, mapping)

        # The same three-title check pipeline/fetch.py performs.
        sheet_has_helper2_columns = (
            'Foreman Helping? #2' in mapping
            and 'Helping Foreman #2 Completed Unit?' in mapping
            and 'Helper #2 Dept #' in mapping
        )
        self.assertFalse(sheet_has_helper2_columns)

        # Helper #1 columns are unaffected by the Helper #2 absence.
        self.assertIn('Foreman Helping?', mapping)
        self.assertIn('Helping Foreman Completed Unit?', mapping)

        # Bridges discovery -> fetch: feeding this real capability
        # boolean into row detection is inert even for an otherwise
        # fully valid Helper #2 row.
        row_data = {
            'Foreman Helping? #2': 'Jamie Helper2',
            'Helping Foreman #2 Completed Unit?': True,
            'Helper #2 Dept #': 'NA-07',
        }
        is_claim = _fetch._detect_helper2_row(
            row_data, sheet_has_helper2_columns=sheet_has_helper2_columns,
            units_completed_checked=True,
        )
        self.assertFalse(is_claim)
        self.assertFalse(row_data['__is_helper2_row'])


class MappingSchemaMarkerAdmissionTests(unittest.TestCase):
    """Task 2 (14-07, D-14-10-APPLIED): the mapping-schema marker is a
    sixth, additive-only admission condition in
    ``pipeline.discovery._build_discovery_skip_index`` -- a null, absent,
    or stale marker rejects cache admission even when every pre-existing
    condition (version match, valid mapping, name) is satisfied, and a
    current marker never overrides a rejection from one of the first
    five conditions."""

    @staticmethod
    def _client(list_sheets_data):
        client = mock.MagicMock()
        client.Sheets.list_sheets.return_value = SimpleNamespace(
            data=list_sheets_data
        )
        return client

    @staticmethod
    def _watermark(**overrides):
        row = {
            "sheet_id": 111222,
            "last_sheet_version": 8,
            "column_mapping": {"Weekly Reference Logged Date": 55},
            "name": "Test Sheet",
        }
        row.update(overrides)
        return row

    def test_null_marker_is_not_admitted(self):
        client = self._client([SimpleNamespace(id=111222, version=8)])
        watermarks = {111222: self._watermark(mapping_schema=None)}

        with mock.patch(
            "pipeline.discovery.get_sheet_watermarks",
            return_value=watermarks,
        ):
            index = _discovery._build_discovery_skip_index(client, [111222])

        self.assertEqual(index, {})

    def test_missing_marker_key_is_not_admitted(self):
        # A watermark row that never carried the key at all -- belt and
        # suspenders on the .get() default alongside the reader's own
        # degrade, which always injects an explicit None.
        client = self._client([SimpleNamespace(id=111222, version=8)])
        watermarks = {111222: self._watermark()}  # no 'mapping_schema' key

        with mock.patch(
            "pipeline.discovery.get_sheet_watermarks",
            return_value=watermarks,
        ):
            index = _discovery._build_discovery_skip_index(client, [111222])

        self.assertEqual(index, {})

    def test_stale_marker_is_not_admitted(self):
        client = self._client([SimpleNamespace(id=111222, version=8)])
        watermarks = {111222: self._watermark(mapping_schema="helper2-v0")}

        with mock.patch(
            "pipeline.discovery.get_sheet_watermarks",
            return_value=watermarks,
        ):
            index = _discovery._build_discovery_skip_index(client, [111222])

        self.assertEqual(index, {})

    def test_current_marker_is_admitted(self):
        client = self._client([SimpleNamespace(id=111222, version=8)])
        watermarks = {
            111222: self._watermark(
                mapping_schema=_discovery.MAPPING_SCHEMA_MARKER
            )
        }

        with mock.patch(
            "pipeline.discovery.get_sheet_watermarks",
            return_value=watermarks,
        ):
            index = _discovery._build_discovery_skip_index(client, [111222])

        self.assertIn(111222, index)
        self.assertEqual(
            index[111222]["column_mapping"],
            {"Weekly Reference Logged Date": 55},
        )

    def test_current_marker_does_not_override_version_mismatch(self):
        # The sixth condition can only ADD a rejection, never substitute
        # for one of the first five -- a current marker must not admit a
        # sheet a version mismatch already rejects.
        client = self._client([SimpleNamespace(id=111222, version=9)])
        watermarks = {
            111222: self._watermark(
                last_sheet_version=8,  # stale -- live is 9
                mapping_schema=_discovery.MAPPING_SCHEMA_MARKER,
            )
        }

        with mock.patch(
            "pipeline.discovery.get_sheet_watermarks",
            return_value=watermarks,
        ):
            index = _discovery._build_discovery_skip_index(client, [111222])

        self.assertEqual(index, {})


class MappingSchemaColumnDegradeTests(unittest.TestCase):
    """Task 2 (14-07, D-14-10-APPLIED):
    ``pipeline_memory.reader.get_sheet_watermarks`` degrades to the
    pre-marker column list, logging exactly once, when the database has
    not yet received the mapping_schema migration -- never raising,
    never admitting from cache (every returned row carries an explicit
    ``mapping_schema: None``)."""

    def setUp(self):
        from pipeline_memory import reader as mem_reader
        mem_reader.reset_mapping_schema_degrade_for_tests()
        self.addCleanup(mem_reader.reset_mapping_schema_degrade_for_tests)

    @staticmethod
    def _unknown_column_error():
        from postgrest import APIError
        return APIError({
            "code": "42703",
            "message": (
                "column sheet_registry.mapping_schema does not exist"
            ),
            "hint": None,
            "details": None,
        })

    @staticmethod
    def _legacy_row_response():
        return SimpleNamespace(data=[{
            "sheet_id": 111222,
            "last_sheet_version": 8,
            "last_read_at": None,
            "last_full_read_at": None,
            "column_mapping": {"Weekly Reference Logged Date": 1},
            "name": "Test Sheet",
        }])

    def _select_side_effect(self, call_log, exc):
        def _select(columns):
            call_log.append(columns)
            q = mock.Mock()
            if "mapping_schema" in columns:
                q.in_.return_value.execute.side_effect = exc
            else:
                q.in_.return_value.execute.return_value = (
                    self._legacy_row_response()
                )
            return q
        return _select

    def test_unknown_column_degrades_to_legacy_select_with_null_marker(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = client.schema.return_value.table.return_value.select
        call_log: list = []
        query.side_effect = self._select_side_effect(
            call_log, self._unknown_column_error()
        )

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ), self.assertLogs(level="WARNING") as cm:
            result = mem_reader.get_sheet_watermarks([111222])

        self.assertIn(111222, result)
        self.assertIsNone(result[111222]["mapping_schema"])
        self.assertEqual(result[111222]["last_sheet_version"], 8)
        self.assertTrue(
            any(
                "mapping_schema" in msg and "14-07" in msg
                for msg in cm.output
            )
        )

    def test_warning_and_marker_probe_fire_only_once_across_two_calls(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = client.schema.return_value.table.return_value.select
        call_log: list = []
        query.side_effect = self._select_side_effect(
            call_log, self._unknown_column_error()
        )

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ), self.assertLogs(level="WARNING") as cm:
            mem_reader.get_sheet_watermarks([111222])
            mem_reader.get_sheet_watermarks([111222])

        marker_attempts = [c for c in call_log if "mapping_schema" in c]
        self.assertEqual(len(marker_attempts), 1)
        degrade_warnings = [
            msg for msg in cm.output
            if "mapping_schema" in msg and "14-07" in msg
        ]
        self.assertEqual(len(degrade_warnings), 1)

    def test_non_mapping_schema_error_is_not_swallowed(self):
        """A DIFFERENT permanent error on the marker-inclusive select
        (not the unknown-column signature) must reach with_retry's
        existing classification unchanged -- never silently
        reinterpreted as a not-yet-migrated database."""
        from pipeline_memory import reader as mem_reader
        from postgrest import APIError

        client = mock.Mock()
        query = client.schema.return_value.table.return_value.select
        call_log: list = []
        exc = APIError({
            "code": "42501",  # permission denied -- unrelated signature
            "message": "permission denied for table sheet_registry",
            "hint": None,
            "details": None,
        })
        query.side_effect = self._select_side_effect(call_log, exc)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_sheet_watermarks([111222])

        self.assertEqual(result, {})
        # The legacy fallback was never attempted -- this is a genuine
        # outage, not the mapping_schema degrade signature.
        legacy_attempts = [c for c in call_log if "mapping_schema" not in c]
        self.assertEqual(len(legacy_attempts), 0)


class MappingSchemaMarkerWriterTests(unittest.TestCase):
    """Task 2 (14-07, D-14-10-APPLIED):
    ``pipeline_memory.writer.upsert_sheet_registry`` writes the
    mapping-schema marker only for a sheet id present in
    ``mapping_schema_by_sheet`` -- a sheet admitted from the discovery
    skip index (absent from that dict) never has its marker promoted,
    and the default (``None``) omits the key for every sheet."""

    def setUp(self):
        from pipeline_memory import client as mem_client
        from pipeline_memory import writer as mem_writer
        mem_client.reset_cache_for_tests()
        mem_writer._reset_counters_for_tests()
        self._saved_flag = os.environ.get("RUN_MEMORY_WRITE_ENABLED")
        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"

    def tearDown(self):
        from pipeline_memory import client as mem_client
        from pipeline_memory import writer as mem_writer
        mem_client.reset_cache_for_tests()
        mem_writer._reset_counters_for_tests()
        if self._saved_flag is None:
            os.environ.pop("RUN_MEMORY_WRITE_ENABLED", None)
        else:
            os.environ["RUN_MEMORY_WRITE_ENABLED"] = self._saved_flag

    @staticmethod
    def _fake_client(upsert_capture):
        client = mock.Mock()
        schema = mock.Mock()
        client.schema.return_value = schema
        table_obj = mock.Mock()
        schema.table.return_value = table_obj
        upsert_obj = mock.Mock()
        table_obj.upsert.return_value = upsert_obj

        def _execute():
            upsert_capture.append(table_obj.upsert.call_args)
            return mock.Mock(data=[])

        upsert_obj.execute.side_effect = _execute
        return client

    @staticmethod
    def _sheets():
        return [
            {"id": 111, "name": "Sheet A", "column_mapping": {"Foreman": 1}},
            {"id": 222, "name": "Sheet B", "column_mapping": {"Foreman": 2}},
        ]

    def _payload_rows(self, upsert_capture):
        rows = []
        for call in upsert_capture:
            rows.extend(call.args[0])
        return rows

    def test_full_validation_sheet_gets_marker_cache_admitted_does_not(self):
        from pipeline_memory import writer as mem_writer

        upsert_capture: list = []
        client = self._fake_client(upsert_capture)

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ):
            mem_writer.upsert_sheet_registry(
                self._sheets(), "run-1", lambda sid: "primary", {},
                mapping_schema_by_sheet={111: "helper2-v1"},
            )

        payload_rows = self._payload_rows(upsert_capture)
        row_111 = next(r for r in payload_rows if r["sheet_id"] == 111)
        row_222 = next(r for r in payload_rows if r["sheet_id"] == 222)
        self.assertEqual(row_111["mapping_schema"], "helper2-v1")
        self.assertNotIn("mapping_schema", row_222)

    def test_default_omits_marker_for_every_sheet(self):
        from pipeline_memory import writer as mem_writer

        upsert_capture: list = []
        client = self._fake_client(upsert_capture)

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ):
            mem_writer.upsert_sheet_registry(
                self._sheets(), "run-1", lambda sid: "primary", {},
            )

        payload_rows = self._payload_rows(upsert_capture)
        self.assertEqual(len(payload_rows), 2)
        for row in payload_rows:
            self.assertNotIn("mapping_schema", row)


# ── Task 3 (14-07) fixture helpers: a synthetic Smartsheet sheet ────────
# shaped by column_mapping + row cells, driven through
# pipeline.fetch.get_all_source_rows with smartsheet_call_with_retry
# patched -- mirrors tests/test_fetch_auth_errors.py's pattern.

def _column_id_map(*fields):
    return {field: idx + 1 for idx, field in enumerate(fields)}


def _fetch_cell(column_id, value):
    return SimpleNamespace(column_id=column_id, value=value, display_value=None)


def _fetch_row(row_id, values, column_mapping):
    cells = [
        _fetch_cell(column_mapping[field], value)
        for field, value in values.items()
        if field in column_mapping
    ]
    return SimpleNamespace(id=row_id, cells=cells, modified_at=None)


def _fetch_sheet(rows, version=1):
    return SimpleNamespace(rows=rows, version=version)


class HelperTwoPartialColumnCapabilityTests(unittest.TestCase):
    """Task 3 (14-07, D-14-02): a sheet mapping only SOME of the three
    key Helper #2 columns is treated as capability-unavailable, not
    partially capable -- the same distinct reason a zero-Helper-#2-
    column sheet logs. 14-02's live probe found no partial set on any
    of the 117 sheets surveyed; this is a defensive shape, not an
    observed one."""

    def test_partial_helper2_column_set_is_capability_unavailable(self):
        # Only 'Foreman Helping? #2' mapped; the other two key columns
        # ('Helping Foreman #2 Completed Unit?', 'Helper #2 Dept #')
        # are absent from column_mapping -- the D-14-04 three-column
        # AND-gate must still evaluate to capability-unavailable.
        column_mapping = _column_id_map(
            'Work Request #', 'Weekly Reference Logged Date',
            'Units Completed?', 'Units Total Price', 'CU', 'Foreman',
            'Foreman Helping? #2',
        )
        source = {
            'id': 4443456, 'name': 'Partial Helper2 Sheet',
            'column_mapping': column_mapping,
        }
        row = _fetch_row(90030, {
            'Work Request #': '90030',
            'Weekly Reference Logged Date': '2026-07-30',
            'Units Completed?': True,
            'Units Total Price': '$50.00',
            'CU': 'CU-500',
            'Foreman': 'Primary Person',
            'Foreman Helping? #2': 'Jamie Helper2',
        }, column_mapping)
        sheet = _fetch_sheet([row])

        def _side_effect(_fn, _sheet_id, **_kwargs):
            return sheet

        with mock.patch.object(
            _fetch, 'smartsheet_call_with_retry', side_effect=_side_effect,
        ), self.assertLogs(level='INFO') as cm:
            result = _fetch.get_all_source_rows(mock.Mock(), [source])

        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]['__is_helper2_row'])
        capability_lines = [
            m for m in cm.output if 'helper2_capability_unavailable' in m
        ]
        self.assertEqual(len(capability_lines), 1)


class HelperTwoNoQualifyingCompletionTests(unittest.TestCase):
    """Task 3 (14-07, D-14-02): the eligible-source-with-no-qualifying-
    completion condition logs a reason distinct from capability-
    unavailable -- capability present, but no row this run satisfies the
    Helper #2 completion criteria."""

    def setUp(self):
        patcher = mock.patch.object(_fetch, 'HELPER2_ENABLED', True)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _helper2_capable_columns():
        return _column_id_map(
            'Work Request #', 'Weekly Reference Logged Date',
            'Units Completed?', 'Units Total Price', 'CU', 'Foreman',
            'Foreman Helping? #2', 'Helping Foreman #2 Completed Unit?',
            'Helper #2 Dept #',
        )

    def _run(self, values, name='Helper2 Capable Sheet', sheet_id=4441234):
        column_mapping = self._helper2_capable_columns()
        source = {'id': sheet_id, 'name': name, 'column_mapping': column_mapping}
        row = _fetch_row(90040, values, column_mapping)
        sheet = _fetch_sheet([row])

        def _side_effect(_fn, _sheet_id, **_kwargs):
            return sheet

        with mock.patch.object(
            _fetch, 'smartsheet_call_with_retry', side_effect=_side_effect,
        ), self.assertLogs(level='INFO') as cm:
            result = _fetch.get_all_source_rows(mock.Mock(), [source])
        return result, cm.output

    def test_capability_present_no_qualifying_row_logs_distinct_reason(self):
        result, log_output = self._run({
            'Work Request #': '90005',
            'Weekly Reference Logged Date': '2026-07-30',
            'Units Completed?': True,
            'Units Total Price': '$75.00',
            'CU': 'CU-100',
            'Foreman': 'Primary Person',
            'Foreman Helping? #2': '',  # never qualifies
            'Helping Foreman #2 Completed Unit?': False,
            'Helper #2 Dept #': '',
        })

        self.assertEqual(len(result), 1)  # primary row still produced
        self.assertFalse(result[0]['__is_helper2_row'])
        no_qual_lines = [
            m for m in log_output if 'helper2_no_qualifying_completion' in m
        ]
        self.assertEqual(len(no_qual_lines), 1)
        # Distinct from the capability-unavailable reason -- capability
        # IS present here.
        self.assertEqual(
            [m for m in log_output if 'helper2_capability_unavailable' in m],
            [],
        )
        # No raw person's name in the reason line itself (only the
        # sheet name is interpolated).
        for line in no_qual_lines:
            self.assertNotIn('Primary Person', line)

    def test_qualifying_row_suppresses_no_qualifying_reason(self):
        result, log_output = self._run({
            'Work Request #': '90005',
            'Weekly Reference Logged Date': '2026-07-30',
            'Units Completed?': True,
            'Units Total Price': '$75.00',
            'CU': 'CU-100',
            'Foreman': 'Primary Person',
            'Foreman Helping? #2': 'Jamie Helper2',
            'Helping Foreman #2 Completed Unit?': True,
            'Helper #2 Dept #': 'NA-07',
        })

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['__is_helper2_row'])
        self.assertEqual(
            [m for m in log_output if 'helper2_no_qualifying_completion' in m],
            [],
        )


class HelperTwoPriceExclusionDiagnosticTagTests(unittest.TestCase):
    """Task 3 (14-07): the price-exclusion diagnostic's specialized-row
    condition covers the Helper #2 slot -- a price-excluded Helper #2
    row is tagged as a 'helper' row in the diagnostic WARNING (the SAME
    tag Helper #1 gets), not a VAC-crew row, and not falling through
    untagged."""

    def setUp(self):
        patcher = mock.patch.object(_fetch, 'HELPER2_ENABLED', True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_price_excluded_helper2_row_tagged_as_helper(self):
        column_mapping = _column_id_map(
            'Work Request #', 'Weekly Reference Logged Date',
            'Units Completed?', 'Units Total Price', 'CU', 'Foreman',
            'Foreman Helping? #2', 'Helping Foreman #2 Completed Unit?',
            'Helper #2 Dept #',
        )
        source = {
            'id': 4442345, 'name': 'Helper2 Price-Excluded Sheet',
            'column_mapping': column_mapping,
        }
        row = _fetch_row(90020, {
            'Work Request #': '90020',
            'Weekly Reference Logged Date': '2026-07-30',
            'Units Completed?': True,
            'Units Total Price': None,  # missing price -- excluded
            'CU': 'CU-400',
            'Foreman': 'Primary Person',
            'Foreman Helping? #2': 'Jamie Helper2',
            'Helping Foreman #2 Completed Unit?': True,
            'Helper #2 Dept #': 'NA-07',
        }, column_mapping)
        sheet = _fetch_sheet([row])

        def _side_effect(_fn, _sheet_id, **_kwargs):
            return sheet

        with mock.patch.object(
            _fetch, 'smartsheet_call_with_retry', side_effect=_side_effect,
        ), self.assertLogs(level='WARNING') as cm:
            result = _fetch.get_all_source_rows(mock.Mock(), [source])

        self.assertEqual(result, [])  # excluded, not appended
        dropped_helper_lines = [
            m for m in cm.output if 'Dropped helper row' in m
        ]
        self.assertEqual(len(dropped_helper_lines), 1)
        self.assertEqual(
            [m for m in cm.output if 'Dropped VAC crew row' in m], [],
        )


class HelperTwoIntake8ShapedFixtureTests(unittest.TestCase):
    """Task 3 (14-07, HLP-04): a source shaped exactly like Intake
    ProMax 8 (sheet id 2244739192541060, per the read-only live-column
    probe recorded in 14-DECISIONS.md, plan 14-02 Task 3) -- full
    Helper #1 column set, none of the six Helper #2 titles -- is
    accepted, produces normal (primary) output, produces NO Helper #2
    output, and logs the capability-unavailable reason.

    FIXTURE ONLY: this test never reads, repairs, reconnects, or
    migrates sheet 2244739192541060 or any other live Smartsheet sheet.
    A deliberately fictional sheet id is used below (mirroring
    HelperTwoCapabilityAbsentDiscoveryTests' precedent) so this fixture
    can never be mistaken for a live call -- everything here is a
    synthetic column_mapping + row fixture with
    smartsheet_call_with_retry patched out entirely."""

    def setUp(self):
        patcher = mock.patch.object(_fetch, 'HELPER2_ENABLED', True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_intake8_shaped_source_accepted_no_helper2_output(self):
        column_mapping = _column_id_map(
            'Work Request #', 'Weekly Reference Logged Date',
            'Units Completed?', 'Units Total Price', 'CU', 'Foreman',
            'Foreman Helping?', 'Helping Foreman Completed Unit?',
            'Helper Dept #', 'Helper Job #',
            # No Helper #2 titles -- the Intake-8 shape (0/6, D-14-01).
        )
        source = {
            # Fictional id -- NEVER the real Intake ProMax 8 id, and no
            # Smartsheet client call happens in this test regardless.
            'id': 9990008, 'name': 'Intake-8-shaped Sheet (fixture)',
            'column_mapping': column_mapping,
        }
        row = _fetch_row(90010, {
            'Work Request #': '90010',
            'Weekly Reference Logged Date': '2026-07-30',
            'Units Completed?': True,
            'Units Total Price': '$50.00',
            'CU': 'CU-300',
            'Foreman': 'Primary Person',
        }, column_mapping)
        sheet = _fetch_sheet([row])

        def _side_effect(_fn, _sheet_id, **_kwargs):
            return sheet

        with mock.patch.object(
            _fetch, 'smartsheet_call_with_retry', side_effect=_side_effect,
        ), self.assertLogs(level='INFO') as cm:
            result = _fetch.get_all_source_rows(mock.Mock(), [source])

        # Accepted: normal (primary) output produced, not rejected/empty.
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]['__is_helper2_row'])
        self.assertNotIn('__helper2_foreman', result[0])

        capability_lines = [
            m for m in cm.output if 'helper2_capability_unavailable' in m
        ]
        self.assertEqual(len(capability_lines), 1)


class HelperTwoDiscoveryFailedValidationUnchangedTests(unittest.TestCase):
    """Task 3 (14-07, D-14-02): pins that pipeline/discovery.py's
    strict-mode acceptance gate and failed-validation except branch are
    untouched by Helper #2 -- a genuine sheet-read failure still routes
    through _failed_validation_sids and still aborts the run; it is
    never reported as a Helper #2 absence. Test-only obligation (14-07
    Task 3 action text); no discovery.py code change accompanies this
    test (see `git diff pipeline/discovery.py`, empty for this task)."""

    def test_genuine_read_failure_still_aborts_not_reported_as_helper2_absence(self):
        saved_env = {
            k: os.environ.get(k) for k in (
                'LIMITED_SHEET_IDS', 'SUBCONTRACTOR_FOLDER_IDS',
                'ORIGINAL_CONTRACT_FOLDER_IDS',
            )
        }
        saved_attrs = {
            k: getattr(generate_weekly_pdfs, k) for k in (
                'SUBCONTRACTOR_FOLDER_IDS', 'ORIGINAL_CONTRACT_FOLDER_IDS',
            )
        }
        client = mock.MagicMock()
        client.Sheets.get_sheet.side_effect = RuntimeError("transport down")
        client.Sheets.list_sheets.return_value = SimpleNamespace(data=[])
        try:
            os.environ['LIMITED_SHEET_IDS'] = '5551111'
            os.environ['SUBCONTRACTOR_FOLDER_IDS'] = ''
            os.environ['ORIGINAL_CONTRACT_FOLDER_IDS'] = ''
            generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS = []
            generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS = []
            with mock.patch.object(
                _discovery, '_FOLDER_DISCOVERED_SUB_IDS', set()
            ), mock.patch.object(
                _discovery, '_FOLDER_DISCOVERED_ORIG_IDS', set()
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    _discovery.discover_source_sheets(client)
        finally:
            for k, v in saved_attrs.items():
                setattr(generate_weekly_pdfs, k, v)
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        self.assertIn('5551111', str(ctx.exception))


class HelperTwoConflictRuleTests(unittest.TestCase):
    """Plan 14-08 Task 2: the O-14-A RESOLVED conflict rule
    (.planning/phases/14-foreman-helper-2/14-DECISIONS.md) -- a source
    row with BOTH a valid Helper #1 completion AND a valid Helper #2
    completion is resolved helper2-wins: the Helper #2 key is emitted,
    the Helper #1 claim is dropped for that row, counted, and never
    aborts the run. Sibling of HelperTwoTracerTests above; same
    fixture idiom (non-subcontractor, non-VAC plain leg)."""

    def setUp(self):
        # Ensure this test's synthetic sheet id is never accidentally
        # treated as a subcontractor sheet by cross-test global state.
        patcher = mock.patch.object(
            _discovery, '_FOLDER_DISCOVERED_SUB_IDS', frozenset()
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_both_slots_valid_helper2_wins_helper1_dropped(self):
        """The conflicted row lands in exactly one helper2 group and no
        helper (Helper #1) group -- O-14-A precedence (Helper #2 >
        Helper #1) applies at the plain leg."""
        row = _both_helpers_row()
        groups = generate_weekly_pdfs.group_source_rows([row])

        helper2_keys = [
            k for k, rows in groups.items()
            if rows[0].get('__variant') == 'helper2'
        ]
        self.assertEqual(len(helper2_keys), 1, groups.keys())
        self.assertEqual(
            {r.get('__row_id') for r in groups[helper2_keys[0]]},
            {row['__row_id']},
        )

        helper_keys = [
            k for k, rows in groups.items()
            if rows[0].get('__variant') == 'helper'
        ]
        self.assertEqual(
            helper_keys, [],
            f"Helper #1 must not emit a group for a conflicted row; "
            f"got: {list(groups.keys())}",
        )

    def test_both_slots_valid_conflict_counted_once(self):
        """get_helper2_conflict_count() increments by exactly one for
        one conflicted row."""
        row = _both_helpers_row()
        generate_weekly_pdfs.group_source_rows([row])
        self.assertEqual(_grouping.get_helper2_conflict_count(), 1)

    def test_conflict_never_aborts_run_other_groups_still_generate(self):
        """T-14-08-03: one conflicted row never stops workbook
        generation for any other group -- the explicit rejection of
        the 2026-07 prototype's abort-before-workbook behavior."""
        conflicted = _both_helpers_row()
        unrelated_primary = _row(**{
            '__row_id': 90099,
            'Work Request #': '77777',
        })
        groups = generate_weekly_pdfs.group_source_rows(
            [conflicted, unrelated_primary]
        )
        primary_keys = [
            k for k, rows in groups.items()
            if rows[0].get('__variant') == 'primary'
            and rows[0].get('Work Request #') == '77777'
        ]
        self.assertEqual(
            len(primary_keys), 1,
            f"the unrelated row's primary group must still generate; "
            f"got: {list(groups.keys())}",
        )
        self.assertEqual(_grouping.get_helper2_conflict_count(), 1)

    def test_same_person_both_slots_collapses_to_single_credit(self):
        """Edge assumption (14-08-PLAN.md HLP-05 adjacency): the SAME
        person named in both slots on one row is still the conflict
        case; the person is credited exactly once, via Helper #2."""
        row = _both_helpers_row(
            __helper_foreman='Same Person',
            __helper2_foreman='Same Person',
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        variants_with_row = [
            rows[0].get('__variant')
            for rows in groups.values()
            if any(r.get('__row_id') == row['__row_id'] for r in rows)
        ]
        self.assertEqual(
            variants_with_row, ['helper2'], list(groups.keys())
        )


class HelperTwoRunSummaryCounterTests(unittest.TestCase):
    """Plan 14-08 Task 3: the four Helper #2 run-summary counters
    (D-14-02 four capability states; O-14-A row conflict) stay present
    on every run, flag on or off. Reachable, unit-level version of what
    Gate 6 (scripts/check_run_summary_structure.py) checks at the shell
    level after a TEST_MODE run."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def test_synthetic_run_summary_key_set_matches_golden_baseline(self):
        """A flag-off (repo default HELPER2_ENABLED='0') synthetic run's
        emitted run_summary.json key set equals the golden baseline's
        key set -- the same comparison Gate 6 makes, but reachable from
        the unit suite so a mismatch is caught before the gate."""
        with mock.patch.object(
            _orchestrate, 'OUTPUT_FOLDER', self._tmpdir.name
        ), mock.patch.object(
            generate_weekly_pdfs, 'OUTPUT_FOLDER', self._tmpdir.name
        ):
            _orchestrate._run_synthetic_test_mode(datetime.datetime.now())

        summary_path = os.path.join(self._tmpdir.name, 'run_summary.json')
        self.assertTrue(
            os.path.exists(summary_path),
            "synthetic TEST_MODE path did not write run_summary.json",
        )
        with open(summary_path, encoding='utf-8') as f:
            emitted = json.load(f)

        baseline_path = (
            _REPO_ROOT / 'tests' / 'golden' / 'run_summary_baseline.json'
        )
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))

        self.assertEqual(
            set(emitted.keys()), set(baseline.keys()),
            f"emitted keys: {sorted(emitted.keys())}\n"
            f"baseline keys: {sorted(baseline.keys())}",
        )

    def test_synthetic_run_summary_includes_four_helper2_counters_zeroed(self):
        """The four new keys are present with a zero int value on a
        run with no Helper #2 data -- the key set never varies."""
        with mock.patch.object(
            _orchestrate, 'OUTPUT_FOLDER', self._tmpdir.name
        ), mock.patch.object(
            generate_weekly_pdfs, 'OUTPUT_FOLDER', self._tmpdir.name
        ):
            _orchestrate._run_synthetic_test_mode(datetime.datetime.now())

        summary_path = os.path.join(self._tmpdir.name, 'run_summary.json')
        with open(summary_path, encoding='utf-8') as f:
            emitted = json.load(f)

        for key in (
            'helper2_capability_unavailable_sheets',
            'helper2_no_qualifying_completion_sheets',
            'helper2_conflict_hold',
            'helper2_groups_generated',
        ):
            self.assertIn(key, emitted, f"missing key: {key}")
            self.assertIsInstance(emitted[key], int)
            self.assertEqual(emitted[key], 0)

    def test_get_helper2_conflict_count_feeds_the_run_summary_key(self):
        """The counter Task 2 exposes is exactly what Task 3's
        helper2_conflict_hold key reads -- not a re-derived value."""
        row = _both_helpers_row()
        generate_weekly_pdfs.group_source_rows([row])
        self.assertEqual(
            _grouping.get_helper2_conflict_count(),
            _orchestrate.get_helper2_conflict_count(),
        )

    def test_synthetic_run_summary_includes_snapshots_helper2_filled_zeroed(
        self,
    ):
        """Plan 14-11 Task 1's fifth counter is present with a zero int
        value on a run with no Helper #2 fill activity -- the key set
        never varies."""
        with mock.patch.object(
            _orchestrate, 'OUTPUT_FOLDER', self._tmpdir.name
        ), mock.patch.object(
            generate_weekly_pdfs, 'OUTPUT_FOLDER', self._tmpdir.name
        ):
            _orchestrate._run_synthetic_test_mode(datetime.datetime.now())

        summary_path = os.path.join(self._tmpdir.name, 'run_summary.json')
        with open(summary_path, encoding='utf-8') as f:
            emitted = json.load(f)

        self.assertIn('snapshots_helper2_filled', emitted)
        self.assertIsInstance(emitted['snapshots_helper2_filled'], int)
        self.assertEqual(emitted['snapshots_helper2_filled'], 0)


class PrefetchedHelper2MissingKeysTests(unittest.TestCase):
    """Plan 14-11 Task 1: grouping publishes the Helper #2 'still
    missing' key set -- the fill-admission candidates -- only for
    prefetched rows whose helper2 is null, a named sentinel, or absent
    from the bulk map entirely (a pre-14-09 shape). Populated only
    after a successful prefetch, mirroring
    get_prefetched_frozen_row_keys() (INC-05 D-12 follow-up)."""

    def setUp(self):
        patcher = mock.patch.object(
            _discovery, '_FOLDER_DISCOVERED_SUB_IDS', frozenset()
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self._saved = {
            'attr': generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': generate_weekly_pdfs.BILLING_AUDIT_AVAILABLE,
            'mode': generate_weekly_pdfs.RES_GROUPING_MODE,
        }
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        generate_weekly_pdfs.BILLING_AUDIT_AVAILABLE = True
        generate_weekly_pdfs.RES_GROUPING_MODE = 'both'
        self.addCleanup(self._restore)
        self._last_key = None

    def _restore(self):
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = (
            self._saved['attr']
        )
        generate_weekly_pdfs.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        generate_weekly_pdfs.RES_GROUPING_MODE = self._saved['mode']

    def _run(self, frozen_row: dict, status: str = 'success'):
        def _fake_prefetch(pairs_filtered):
            wr, week = next(iter(pairs_filtered))
            self._last_key = (wr, week, 90001)
            return {self._last_key: frozen_row}, status

        with mock.patch(
            'billing_audit.writer.prefetch_attribution',
            side_effect=_fake_prefetch,
        ):
            generate_weekly_pdfs.group_source_rows([_row()])

    def test_missing_keys_cover_null_sentinel_and_absent_helper2(self):
        cases = {
            'null': {'helper2': None},
            'named_sentinel': {'helper2': 'Unknown Helper 2'},
            'absent_key': {},
        }
        for label, frozen_row in cases.items():
            with self.subTest(label=label):
                self._run(frozen_row)
                self.assertIn(
                    self._last_key,
                    _grouping.get_prefetched_helper2_missing_keys(),
                )

    def test_missing_keys_exclude_rows_with_a_real_helper2(self):
        self._run({'helper2': 'Jamie Helper2'})
        self.assertNotIn(
            self._last_key,
            _grouping.get_prefetched_helper2_missing_keys(),
        )

    def test_missing_keys_empty_on_fetch_failure(self):
        self._run({'helper2': None}, status='fetch_failure')
        self.assertEqual(
            _grouping.get_prefetched_helper2_missing_keys(), frozenset()
        )

    def test_missing_keys_reset_when_next_call_has_no_prefetch(self):
        self._run({'helper2': None})
        self.assertTrue(_grouping.get_prefetched_helper2_missing_keys())
        generate_weekly_pdfs.BILLING_AUDIT_AVAILABLE = False
        generate_weekly_pdfs.group_source_rows([_row()])
        self.assertEqual(
            _grouping.get_prefetched_helper2_missing_keys(), frozenset()
        )


class Helper2FillKeyHelpersTests(unittest.TestCase):
    """Plan 14-11 Task 1: pipeline.attribution's Helper #2 fill-
    admission helpers -- build_helper2_fill_keys() and
    helper2_fill_admits()."""

    _WR = '90005'
    _WEEK = datetime.date(2026, 7, 30)
    _ROW_ID = 90001

    def test_warm_billing_audit_row_cache_unchanged_output(self):
        """Factoring the key format into billing_audit_cache_key() must
        not change warm_billing_audit_row_cache's existing output
        (regression pin, mirrors
        tests/test_freeze_row_cache_warm_start.py::WarmCacheHelperTests)."""
        cache: set[str] = set()
        added = _attribution.warm_billing_audit_row_cache(
            cache, {('12345678', datetime.date(2026, 8, 30), 4242)},
        )
        self.assertEqual(added, 1)
        self.assertEqual(cache, {'12345678|083026|4242'})

    def test_build_helper2_fill_keys_matches_warm_start_key_format(self):
        keys = {(self._WR, self._WEEK, self._ROW_ID)}
        cache: set[str] = set()
        _attribution.warm_billing_audit_row_cache(cache, keys)
        fill_keys = _attribution.build_helper2_fill_keys(keys)
        self.assertEqual(fill_keys, cache)

    def test_admits_false_without_helper2_foreman(self):
        with mock.patch.object(_attribution, 'HELPER2_ENABLED', True):
            fill_keys = _attribution.build_helper2_fill_keys(
                {(self._WR, self._WEEK, self._ROW_ID)}
            )
            cache_key = next(iter(fill_keys))
            row = _row(__helper2_foreman='', __helper2_dept='NA-07')
            self.assertFalse(
                _attribution.helper2_fill_admits(row, cache_key, fill_keys)
            )

    def test_admits_false_for_sentinel_foreman(self):
        with mock.patch.object(_attribution, 'HELPER2_ENABLED', True):
            fill_keys = _attribution.build_helper2_fill_keys(
                {(self._WR, self._WEEK, self._ROW_ID)}
            )
            cache_key = next(iter(fill_keys))
            row = _row(
                __helper2_foreman='Unknown Helper 2',
                __helper2_dept='NA-07',
            )
            self.assertFalse(
                _attribution.helper2_fill_admits(row, cache_key, fill_keys)
            )

    def test_admits_false_without_helper2_dept(self):
        with mock.patch.object(_attribution, 'HELPER2_ENABLED', True):
            fill_keys = _attribution.build_helper2_fill_keys(
                {(self._WR, self._WEEK, self._ROW_ID)}
            )
            cache_key = next(iter(fill_keys))
            row = _row(__helper2_foreman='Jamie Helper2', __helper2_dept='')
            self.assertFalse(
                _attribution.helper2_fill_admits(row, cache_key, fill_keys)
            )

    def test_admits_false_when_key_not_in_fill_set(self):
        with mock.patch.object(_attribution, 'HELPER2_ENABLED', True):
            fill_keys = _attribution.build_helper2_fill_keys(set())
            row = _row(
                __helper2_foreman='Jamie Helper2',
                __helper2_dept='NA-07',
            )
            self.assertFalse(
                _attribution.helper2_fill_admits(
                    row, '90005|073026|90001', fill_keys,
                )
            )

    def test_admits_false_when_flag_off(self):
        with mock.patch.object(_attribution, 'HELPER2_ENABLED', False):
            fill_keys = _attribution.build_helper2_fill_keys(
                {(self._WR, self._WEEK, self._ROW_ID)}
            )
            cache_key = next(iter(fill_keys))
            row = _row(
                __helper2_foreman='Jamie Helper2',
                __helper2_dept='NA-07',
            )
            self.assertFalse(
                _attribution.helper2_fill_admits(row, cache_key, fill_keys)
            )

    def test_admits_true_for_the_one_admitted_shape(self):
        with mock.patch.object(_attribution, 'HELPER2_ENABLED', True):
            fill_keys = _attribution.build_helper2_fill_keys(
                {(self._WR, self._WEEK, self._ROW_ID)}
            )
            cache_key = next(iter(fill_keys))
            row = _row(
                __helper2_foreman='Jamie Helper2',
                __helper2_dept='NA-07',
            )
            self.assertTrue(
                _attribution.helper2_fill_admits(row, cache_key, fill_keys)
            )


class FreezeLoopHelper2AdmissionTests(unittest.TestCase):
    """Plan 14-11 Task 1: the freeze loop sends exactly the admitted
    row -- an already-frozen row stays skipped unless
    helper2_fill_admits allows it through. Mirrors
    tests/test_freeze_row_cache_warm_start.py::
    SeededKeySkipsFreezeRpcTests -- the loop's candidate filter,
    verbatim, extended with the Task 1 admission gate."""

    def test_only_the_admitted_row_reaches_freeze_row(self):
        wr_num, week_raw = '90005', '073026'
        cache_key_1 = f"{wr_num}|{week_raw}|90001"
        cache_key_2 = f"{wr_num}|{week_raw}|90002"
        cache = {cache_key_1, cache_key_2}  # both already frozen
        fill_keys = {cache_key_2}  # only row 90002 still lacks Helper #2

        with mock.patch.object(_attribution, 'HELPER2_ENABLED', True):
            row_no_fill = _row(
                __row_id=90001, __helper2_foreman='Jamie Helper2',
                __helper2_dept='NA-07',
            )
            row_admitted = _row(
                __row_id=90002, __helper2_foreman='Jamie Helper2',
                __helper2_dept='NA-07',
            )
            rows = [row_no_fill, row_admitted]

            # The freeze loop's candidate filter (pipeline/orchestrate.py),
            # verbatim, extended with the Task 1 admission gate.
            _rows_to_freeze = []
            for r in rows:
                _row_id = r.get('__row_id')
                _cache_key = f"{wr_num}|{week_raw}|{_row_id}"
                if _cache_key in cache:
                    if not _attribution.helper2_fill_admits(
                        r, _cache_key, fill_keys,
                    ):
                        continue
                _rows_to_freeze.append(r)

            freeze_row = mock.Mock(return_value=True)
            for r in _rows_to_freeze:
                freeze_row(r)

        self.assertEqual(
            [r['__row_id'] for r in _rows_to_freeze], [90002],
        )
        freeze_row.assert_called_once_with(row_admitted)


class FreezeRowHelper2FillCounterTests(unittest.TestCase):
    """Plan 14-11 Task 1: freeze_row classifies a fill (per-role
    Helper #2 write on an already-frozen row) as
    snapshots_helper2_filled, read from the returned provenance --
    never inferred from the request."""

    def setUp(self):
        _reset_all()
        self.addCleanup(_reset_all)

    @staticmethod
    def _row():
        return {
            "__row_id": 90001,
            "Work Request #": "90005",
            "__week_ending_date": datetime.date(2026, 7, 30),
            "Units Completed?": True,
            "__helper2_foreman": "Jamie Helper2",
            "__helper2_dept": "NA-07",
        }

    def test_bumps_helper2_filled_when_provenance_names_this_run(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        resp = mock.Mock()
        resp.data = {
            "source_run_id": "prior-run",
            "backfill_provenance": {
                "helper2": {"source": "live", "run_id": "current-run"},
            },
        }
        client.schema.return_value.rpc.return_value.execute.return_value = (
            resp
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client,
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True,
        ):
            result = ba_writer.freeze_row(
                self._row(), release="r", run_id="current-run",
            )
        self.assertIs(result, True)
        self.assertEqual(
            ba_writer.get_counters().get("snapshots_helper2_filled", 0), 1,
        )
        self.assertEqual(
            ba_writer.get_counters()["snapshots_already_frozen"], 0,
        )

    def test_stays_already_frozen_without_a_matching_provenance_entry(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        resp = mock.Mock()
        resp.data = {"source_run_id": "prior-run"}
        client.schema.return_value.rpc.return_value.execute.return_value = (
            resp
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client,
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True,
        ):
            result = ba_writer.freeze_row(
                self._row(), release="r", run_id="current-run",
            )
        self.assertIs(result, True)
        self.assertEqual(
            ba_writer.get_counters()["snapshots_already_frozen"], 1,
        )
        self.assertEqual(
            ba_writer.get_counters().get("snapshots_helper2_filled", 0), 0,
        )


if __name__ == "__main__":
    unittest.main()
