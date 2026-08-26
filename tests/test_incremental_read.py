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


# ── Task 1: pipeline_memory.reader.get_last_run_ledger_status ───────────

class LastRunLedgerStatusReadTests(unittest.TestCase):
    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()

    def test_returns_newest_row_status_and_finished_at(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.order.return_value.limit.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[
            {"status": "success", "finished_at": "2026-08-26T18:00:00+00:00"},
        ])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_last_run_ledger_status()

        self.assertEqual(result["status"], "success")

    def test_failure_returns_none(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        (
            client.schema.return_value.table.return_value
            .select.return_value.order.return_value.limit.return_value
            .execute.side_effect
        ) = Exception("boom")

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_last_run_ledger_status()

        self.assertIsNone(result)

    def test_no_prior_run_returns_none(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.order.return_value.limit.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_last_run_ledger_status()

        self.assertIsNone(result)


# ── Task 2: resolve_run_mode -- the seven D-02 full-read escalation
#    triggers ────────────────────────────────────────────────────────────

def _healthy_kwargs(**overrides):
    """Baseline resolve_run_mode() kwargs for a clean, all-healthy run."""
    kwargs = dict(
        incremental_enabled=True,
        execution_type="production_frequent",
        auth_error_sheet_ids=set(),
        reset_hash_history=False,
        regen_weeks=set(),
        reset_wr_list=set(),
        force_generation=False,
    )
    kwargs.update(overrides)
    return kwargs


def _healthy_watermark(sheet_id, mapping):
    return {
        sheet_id: {
            "sheet_id": sheet_id,
            "last_sheet_version": 8,
            "last_read_at": "2026-08-26T18:00:00+00:00",
            "last_full_read_at": "2026-08-20T18:00:00+00:00",
            "column_mapping": mapping,
        }
    }


class ModeResolutionTests(unittest.TestCase):
    def _clean_last_run(self):
        return {"status": "success", "finished_at": "2026-08-26T17:00:00+00:00"}

    def test_happy_path_resolves_incremental_with_none_reason(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        mode, reason, per_sheet = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(),
        )

        self.assertEqual(mode, "incremental")
        self.assertIsNone(reason)
        self.assertEqual(per_sheet, {})

    def test_flag_off_resolves_full_even_when_everything_else_healthy(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        mode, reason, _ = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(incremental_enabled=False),
        )

        self.assertEqual(mode, "full")
        self.assertTrue(reason)

    def test_trigger1_no_watermark_row_marks_sheet_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        # Watermark map healthy for a DIFFERENT sheet so trigger 4 (empty
        # map) does not also fire -- isolates trigger 1.
        watermarks = _healthy_watermark(999999, {"X": 1})

        mode, reason, per_sheet = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(),
        )

        self.assertIn(source["id"], per_sheet)
        self.assertIn("trigger1", per_sheet[source["id"]])
        # Whole-run mode still resolves per the other (healthy) triggers.
        self.assertEqual(mode, "incremental")
        self.assertIsNone(reason)

    def test_trigger1_null_last_sheet_version_marks_sheet_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])
        watermarks[source["id"]]["last_sheet_version"] = None

        mode, reason, per_sheet = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(),
        )

        self.assertIn("trigger1", per_sheet[source["id"]])
        self.assertEqual(mode, "incremental")

    def test_trigger2_column_mapping_drift_marks_sheet_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(
            source["id"], {"Work Request #": 1, "Foreman": 999}
        )

        mode, reason, per_sheet = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(),
        )

        self.assertIn("trigger2", per_sheet[source["id"]])
        self.assertEqual(mode, "incremental")

    def test_trigger2_json_roundtrip_mapping_is_not_a_false_drift(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        # Stored mapping round-tripped through JSON: string keys/values
        # instead of the freshly-discovered dict's native int values.
        watermarks = _healthy_watermark(
            source["id"], {"Work Request #": "1", "Foreman": "2"}
        )

        mode, reason, per_sheet = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(),
        )

        self.assertNotIn(source["id"], per_sheet)
        self.assertEqual(mode, "incremental")

    def test_trigger3_auth_error_isolated_and_watermark_never_touched(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        mode, reason, per_sheet = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(auth_error_sheet_ids={source["id"]}),
        )

        self.assertIn("trigger3", per_sheet[source["id"]])
        self.assertEqual(mode, "incremental")

    def test_trigger4_empty_watermark_map_forces_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()

        mode, reason, _ = resolve_run_mode(
            [source], {}, self._clean_last_run(),
            **_healthy_kwargs(),
        )

        self.assertEqual(mode, "full")
        self.assertIn("trigger4", reason)

    def test_trigger5_operator_flags_force_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        for flag_kwargs in (
            {"reset_hash_history": True},
            {"regen_weeks": {"081725"}},
            {"reset_wr_list": {"WR123"}},
            {"force_generation": True},
        ):
            with self.subTest(flag_kwargs=flag_kwargs):
                mode, reason, _ = resolve_run_mode(
                    [source], watermarks, self._clean_last_run(),
                    **_healthy_kwargs(**flag_kwargs),
                )
                self.assertEqual(mode, "full")
                self.assertIn("trigger5", reason)

    def test_trigger6_previous_run_not_success_forces_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        mode, reason, _ = resolve_run_mode(
            [source], watermarks,
            {"status": "failed", "finished_at": "2026-08-26T17:00:00+00:00"},
            **_healthy_kwargs(),
        )

        self.assertEqual(mode, "full")
        self.assertIn("trigger6", reason)

    def test_trigger6_previous_run_missing_finished_at_forces_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        mode, reason, _ = resolve_run_mode(
            [source], watermarks,
            {"status": "running", "finished_at": None},
            **_healthy_kwargs(),
        )

        self.assertEqual(mode, "full")
        self.assertIn("trigger6", reason)

    def test_trigger6_last_run_status_none_forces_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        mode, reason, _ = resolve_run_mode(
            [source], watermarks, None,
            **_healthy_kwargs(),
        )

        self.assertEqual(mode, "full")
        self.assertIn("trigger6", reason)

    def test_trigger7_execution_type_not_production_frequent_forces_full(self):
        from pipeline.orchestrate import resolve_run_mode

        source = _make_source()
        watermarks = _healthy_watermark(source["id"], source["column_mapping"])

        mode, reason, _ = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(execution_type="weekly_comprehensive"),
        )

        self.assertEqual(mode, "full")
        self.assertIn("trigger7", reason)

    def test_never_raises_on_unexpected_exception(self):
        from pipeline.orchestrate import resolve_run_mode

        # A non-dict watermark value simulates a corrupt/unexpected shape;
        # resolve_run_mode must fail open, never propagate the exception.
        source = _make_source()
        watermarks = {source["id"]: "not-a-dict"}

        mode, reason, _ = resolve_run_mode(
            [source], watermarks, self._clean_last_run(),
            **_healthy_kwargs(),
        )

        self.assertEqual(mode, "full")
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
