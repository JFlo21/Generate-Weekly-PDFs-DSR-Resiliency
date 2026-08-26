"""Tests for Phase 11 Plan 02 (INC-01): the frequent run's per-sheet delta
read, the seven D-02 full-read escalation triggers, and capture-time
watermark persistence.

Class layout, in commit order (RED then GREEN per task -- 11-02-PLAN.md):
  - AbbreviatedResponseDetectionTests / RowsModifiedSinceTests /
    FetchSheetDeltaTests / SheetWatermarksReadTests -- Task 1 (the INC-01
    delta-read primitive: config flags, pipeline_memory/reader.py's first
    read surface, pipeline/fetch.py's probe).
  - ModeResolutionTests -- Task 2 (resolve_run_mode's seven D-02 full-read
    escalation triggers).
  - WatermarkPersistenceTests -- Task 3 (capture-time watermark
    persistence + run_ledger.mode visibility).

Self-contained like ``tests/test_pipeline_memory_shadow.py`` -- there is
no ``tests/conftest.py`` in this repo to share fixtures from.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures" / "incremental"

_ENV_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "TEST_MODE",
    "RUN_MEMORY_WRITE_ENABLED",
    "RUN_MEMORY_INCREMENTAL_ENABLED",
    "SAFETY_WINDOW_MINUTES",
    "EXECUTION_TYPE",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT",
    "RESET_HASH_HISTORY",
    "REGEN_WEEKS",
    "RESET_WR_LIST",
    "FORCE_GENERATION",
)


def _pop_env():
    for k in _ENV_KEYS:
        os.environ.pop(k, None)


def _reset_pipeline_memory():
    from pipeline_memory import client as mem_client
    mem_client.reset_cache_for_tests()


def _make_source(sheet_id=111222, name="Test Sheet"):
    return {
        "id": sheet_id,
        "name": name,
        "column_mapping": {"Work Request #": 1, "Foreman": 2},
    }


# ── Task 1: abbreviated-response detection ──────────────────────────────

class AbbreviatedResponseDetectionTests(unittest.TestCase):
    def test_missing_rows_attribute_is_abbreviated(self):
        from pipeline.fetch import _is_abbreviated_response
        sheet = SimpleNamespace(version=5)
        self.assertTrue(_is_abbreviated_response(sheet))

    def test_none_rows_is_abbreviated(self):
        from pipeline.fetch import _is_abbreviated_response
        sheet = SimpleNamespace(version=5, rows=None)
        self.assertTrue(_is_abbreviated_response(sheet))

    def test_empty_rows_list_is_abbreviated(self):
        from pipeline.fetch import _is_abbreviated_response
        sheet = SimpleNamespace(version=5, rows=[])
        self.assertTrue(_is_abbreviated_response(sheet))

    def test_present_rows_is_not_abbreviated(self):
        from pipeline.fetch import _is_abbreviated_response
        sheet = SimpleNamespace(version=5, rows=[object()])
        self.assertFalse(_is_abbreviated_response(sheet))


# ── Task 1: rows_modified_since overlap arithmetic ──────────────────────

class RowsModifiedSinceTests(unittest.TestCase):
    def test_subtracts_safety_window_from_capture_time(self):
        from pipeline.fetch import compute_rows_modified_since
        captured = datetime.datetime(
            2026, 8, 26, 18, 0, 0, tzinfo=datetime.timezone.utc
        )
        result = compute_rows_modified_since(captured, 15)
        expected = captured - datetime.timedelta(minutes=15)
        self.assertEqual(datetime.datetime.fromisoformat(result), expected)

    def test_accepts_iso_string_last_read_at(self):
        from pipeline.fetch import compute_rows_modified_since
        result = compute_rows_modified_since("2026-08-26T18:00:00+00:00", 15)
        expected = datetime.datetime(
            2026, 8, 26, 17, 45, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(datetime.datetime.fromisoformat(result), expected)


# ── Task 1: fetch_sheet_delta (the INC-01 probe) ────────────────────────

class FetchSheetDeltaTests(unittest.TestCase):
    def test_unchanged_sheet_costs_one_call_zero_rows(self):
        from pipeline.fetch import fetch_sheet_delta

        client = mock.Mock()
        client.Sheets.get_sheet.return_value = SimpleNamespace(version=8)
        source = _make_source()

        result = fetch_sheet_delta(
            client, source, 8, "2026-08-26T17:45:00+00:00"
        )

        self.assertEqual(client.Sheets.get_sheet.call_count, 1)
        _, kwargs = client.Sheets.get_sheet.call_args
        self.assertEqual(kwargs.get("if_version_after"), 8)
        self.assertFalse(result["escalate"])
        self.assertEqual(result["calls"], 1)
        self.assertIsNone(result.get("sheet"))

    def test_changed_sheet_costs_two_calls_second_carries_rows_modified_since(self):
        from pipeline.fetch import fetch_sheet_delta

        client = mock.Mock()
        probe_response = SimpleNamespace(version=9, rows=[object(), object()])
        delta_response = SimpleNamespace(version=9, rows=[object()])
        client.Sheets.get_sheet.side_effect = [probe_response, delta_response]
        source = _make_source()

        result = fetch_sheet_delta(
            client, source, 8, "2026-08-26T17:45:00+00:00"
        )

        self.assertEqual(client.Sheets.get_sheet.call_count, 2)
        _, second_kwargs = client.Sheets.get_sheet.call_args_list[1]
        self.assertEqual(
            second_kwargs.get("rows_modified_since"),
            "2026-08-26T17:45:00+00:00",
        )
        self.assertFalse(result["escalate"])
        self.assertEqual(result["calls"], 2)
        self.assertIs(result["sheet"], delta_response)

    def test_abbreviated_without_version_escalates(self):
        from pipeline.fetch import fetch_sheet_delta

        client = mock.Mock()
        client.Sheets.get_sheet.return_value = SimpleNamespace()
        source = _make_source()

        result = fetch_sheet_delta(
            client, source, 8, "2026-08-26T17:45:00+00:00"
        )

        self.assertTrue(result["escalate"])
        self.assertIn("version", result["reason"])

    def test_exception_escalates_never_unchanged(self):
        from pipeline.fetch import fetch_sheet_delta

        client = mock.Mock()
        client.Sheets.get_sheet.side_effect = ValueError("boom")
        source = _make_source()

        result = fetch_sheet_delta(
            client, source, 8, "2026-08-26T17:45:00+00:00"
        )

        self.assertTrue(result["escalate"])
        self.assertNotEqual(result.get("reason", ""), "")

    def test_abbreviated_response_fixture_parses_as_abbreviated(self):
        from pipeline.fetch import _is_abbreviated_response

        cassette = json.loads(
            (_FIXTURES_DIR / "abbreviated_sheet_response.json").read_text(
                encoding="utf-8"
            )
        )
        sheet = SimpleNamespace(**cassette["raw_response"])
        self.assertTrue(_is_abbreviated_response(sheet))


# ── Task 1: pipeline_memory.reader.get_sheet_watermarks ─────────────────

class SheetWatermarksReadTests(unittest.TestCase):
    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()

    def test_returns_dict_keyed_by_sheet_id(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[
            {
                "sheet_id": 111222,
                "last_sheet_version": 8,
                "last_read_at": "2026-08-26T18:00:00+00:00",
                "last_full_read_at": "2026-08-20T18:00:00+00:00",
                "column_mapping": {"Work Request #": 1},
            },
        ])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_sheet_watermarks([111222])

        self.assertIn(111222, result)
        self.assertEqual(result[111222]["last_sheet_version"], 8)

    def test_supabase_failure_returns_empty_dict(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value
            .execute.side_effect
        ) = Exception("boom")

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_sheet_watermarks([111222])

        self.assertEqual(result, {})

    def test_client_unavailable_returns_empty_dict(self):
        from pipeline_memory import reader as mem_reader

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=None
        ):
            result = mem_reader.get_sheet_watermarks([111222])

        self.assertEqual(result, {})

    def test_empty_sheet_ids_performs_zero_calls(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_sheet_watermarks([])

        self.assertEqual(result, {})
        client.schema.assert_not_called()


if __name__ == "__main__":
    unittest.main()
