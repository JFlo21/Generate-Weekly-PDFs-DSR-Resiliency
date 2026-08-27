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


# ── Task 3: capture-time watermark persistence + mode visibility ────────

class WatermarkPersistenceTests(unittest.TestCase):
    """upsert_sheet_registry's new capture_times / full_read_sheets
    contract (writer-side, behavioral) and the main()-side wiring
    (structural, mirroring RunLedgerSheetsChangedCallSiteTests in
    tests/test_pipeline_memory_shadow.py -- both are deep inside main()
    and not directly invocable without a whole session).
    """

    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()

    def test_persists_caller_supplied_capture_time_verbatim(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = mock.Mock()
        table = client.schema.return_value.table.return_value

        def _execute():
            upsert_capture.append(table.upsert.call_args)
            return SimpleNamespace(data=[])

        table.upsert.return_value.execute.side_effect = _execute

        captured = "2026-08-26T18:00:00.123456+00:00"
        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_sheet_registry(
                [{"id": 111222, "name": "Test Sheet", "column_mapping": {}}],
                "run-1",
                lambda _sid: "primary",
                {111222: 8},
                capture_times={111222: captured},
                full_read_sheets={111222},
            )

        self.assertEqual(len(upsert_capture), 1)
        payload = upsert_capture[0].args[0]
        self.assertEqual(payload[0]["last_read_at"], captured)

    def test_delta_read_omits_last_full_read_at(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = mock.Mock()
        table = client.schema.return_value.table.return_value

        def _execute():
            upsert_capture.append(table.upsert.call_args)
            return SimpleNamespace(data=[])

        table.upsert.return_value.execute.side_effect = _execute

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_sheet_registry(
                [{"id": 111222, "name": "Test Sheet", "column_mapping": {}}],
                "run-1",
                lambda _sid: "primary",
                {111222: 9},
                capture_times={111222: "2026-08-26T18:00:00+00:00"},
                full_read_sheets=set(),  # empty -- 111222 is a DELTA read
            )

        payload = upsert_capture[0].args[0]
        self.assertNotIn("last_full_read_at", payload[0])
        self.assertEqual(payload[0]["last_sheet_version"], 9)

    def test_full_read_writes_last_full_read_at_equal_to_capture_time(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = mock.Mock()
        table = client.schema.return_value.table.return_value

        def _execute():
            upsert_capture.append(table.upsert.call_args)
            return SimpleNamespace(data=[])

        table.upsert.return_value.execute.side_effect = _execute

        captured = "2026-08-26T18:00:00+00:00"
        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_sheet_registry(
                [{"id": 111222, "name": "Test Sheet", "column_mapping": {}}],
                "run-1",
                lambda _sid: "primary",
                {111222: 9},
                capture_times={111222: captured},
                full_read_sheets={111222},
            )

        payload = upsert_capture[0].args[0]
        self.assertEqual(payload[0]["last_full_read_at"], captured)

    def test_default_kwargs_preserve_phase10_backward_compatible_behavior(self):
        """No capture_times/full_read_sheets supplied (Phase 10's two
        existing call sites) -> every sheet gets the SAME freshly-computed
        `now` for both last_read_at and last_full_read_at, byte-identical
        to pre-Plan-02 behavior.
        """
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = mock.Mock()
        table = client.schema.return_value.table.return_value

        def _execute():
            upsert_capture.append(table.upsert.call_args)
            return SimpleNamespace(data=[])

        table.upsert.return_value.execute.side_effect = _execute

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_sheet_registry(
                [{"id": 111222, "name": "Test Sheet", "column_mapping": {}}],
                "run-1",
                lambda _sid: "primary",
                {111222: 9},
            )

        payload = upsert_capture[0].args[0]
        self.assertIn("last_read_at", payload[0])
        self.assertIn("last_full_read_at", payload[0])
        self.assertEqual(payload[0]["last_read_at"], payload[0]["last_full_read_at"])

    def test_build_registry_write_plan_excludes_trigger3_sheets(self):
        from pipeline.orchestrate import _build_registry_write_plan

        sheets = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
        ]
        capture_time = "2026-08-26T18:00:00+00:00"

        registry_sheets, capture_times, full_read_ids = (
            _build_registry_write_plan(sheets, {2}, capture_time)
        )

        self.assertEqual([s["id"] for s in registry_sheets], [1])
        self.assertEqual(capture_times, {1: capture_time})
        self.assertEqual(full_read_ids, {1})

    def test_build_registry_write_plan_empty_trigger3_keeps_all_sheets(self):
        from pipeline.orchestrate import _build_registry_write_plan

        sheets = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        capture_time = "2026-08-26T18:00:00+00:00"

        registry_sheets, capture_times, full_read_ids = (
            _build_registry_write_plan(sheets, set(), capture_time)
        )

        self.assertEqual({s["id"] for s in registry_sheets}, {1, 2})
        self.assertEqual(capture_times, {1: capture_time, 2: capture_time})
        self.assertEqual(full_read_ids, {1, 2})

    def test_resolve_run_mode_called_between_phase1_and_run_ledger_start(self):
        """Structural: resolve_run_mode() sits after PHASE 1 discovery and
        before run_ledger_start's call site -- mirrors
        RunLedgerSheetsChangedCallSiteTests' inspect.getsource pattern
        (both are deep inside main(), not directly invocable).
        """
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        phase1_idx = src.index("PHASE 1: Discovering source sheets")
        resolve_idx = src.index("resolve_run_mode(")
        start_idx = src.index("_mem_writer.run_ledger_start(")
        phase2_idx = src.index("PHASE 2: Fetching source data")

        self.assertLess(phase1_idx, resolve_idx)
        self.assertLess(resolve_idx, start_idx)
        self.assertLess(start_idx, phase2_idx)

    def test_run_ledger_start_carries_resolved_mode(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        idx = src.index("_mem_writer.run_ledger_start(")
        end = src.index(")\n", idx)
        block = src[idx:end]
        self.assertIn("mode=_resolved_mode", block)

    def test_both_run_ledger_finish_sites_carry_resolved_mode_and_optional_reason(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        kwargs_blocks = [
            m.start()
            for m in __import__("re").finditer(
                r"_finish_kwargs(?::\s*dict\[str,\s*Any\])?\s*=\s*dict\(",
                src,
            )
        ]
        self.assertEqual(len(kwargs_blocks), 2)
        for idx in kwargs_blocks:
            end = src.index(")\n", idx)
            block = src[idx:end]
            self.assertIn("mode=_resolved_mode", block)
        self.assertEqual(
            src.count('_finish_kwargs["fallback_reason"] = _resolved_fallback_reason'),
            2,
        )

    def test_run_summary_still_21_keys(self):
        """run_summary.json's frozen contract is untouched by this plan."""
        golden = _REPO_ROOT / "tests" / "golden" / "run_summary_baseline.json"
        data = json.loads(golden.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 21)

    def test_workflow_and_schema_untouched(self):
        """git diff --exit-code equivalent for the two protected paths."""
        import subprocess

        result = subprocess.run(
            [
                "git", "diff", "--exit-code", "--",
                ".github/workflows/", "pipeline_memory/schema.sql",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"protected paths were modified:\n{result.stdout.decode()}",
        )


# ── 11-03 Task 1 (D-06 attachment preservation): keep_historical
# call-boundary override on cleanup_untracked_sheet_attachments ────────

class CleanupPreservationTests(unittest.TestCase):
    """CONTEXT.md D-06's attachment half: ``keep_historical`` threaded
    from the incremental-mode call site to the existing
    ``KEEP_HISTORICAL_WEEKS`` identity-loop gate in
    ``pipeline.cleanup.cleanup_untracked_sheet_attachments``. Mirrors
    the mocking convention already established in
    ``tests/test_orphaned_primary_attachment.py``.
    """

    SHEET_ID = 5723337641643908
    WEEK = "041926"

    def setUp(self):
        import generate_weekly_pdfs as gwp
        self._gwp = gwp
        self._saved_keep_historical = gwp.KEEP_HISTORICAL_WEEKS

    def tearDown(self):
        self._gwp.KEEP_HISTORICAL_WEEKS = self._saved_keep_historical

    @staticmethod
    def _attachment(name, att_id):
        att = mock.MagicMock()
        att.name = name
        att.id = att_id
        return att

    @staticmethod
    def _sheet_and_cache(attachments):
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 111
        sheet.rows = [row]
        return sheet, {111: attachments}

    @staticmethod
    def _client(deleted_ids):
        client = mock.MagicMock()

        def _delete(sheet_id, att_id):
            deleted_ids.append(att_id)
            return mock.MagicMock()

        client.Attachments.delete_attachment.side_effect = _delete
        return client

    def _run(self, attachments, valid_wr_weeks, keep_historical, module_constant):
        from pipeline.cleanup import cleanup_untracked_sheet_attachments

        self._gwp.KEEP_HISTORICAL_WEEKS = module_constant
        sheet, cache = self._sheet_and_cache(attachments)
        deleted_ids: list[int] = []
        client = self._client(deleted_ids)
        cleanup_untracked_sheet_attachments(
            client=client,
            target_sheet_id=self.SHEET_ID,
            valid_wr_weeks=valid_wr_weeks,
            test_mode=False,
            attachment_cache=cache,
            target_sheet=sheet,
            keep_historical=keep_historical,
        )
        return deleted_ids

    def _name(self, wr, identifier, ts="120000"):
        return (
            f"WR_{wr}_WeekEnding_{self.WEEK}_{ts}_User_{identifier}_aabbcc.xlsx"
        )

    def _dup_pair(self, wr, identifier, newer_id, older_id):
        # cleanup_untracked_sheet_attachments' identity-loop only ever
        # deletes DUPLICATE attachments beyond the single newest one
        # per (wr, week, variant, identifier) -- a lone attachment is
        # never deleted through this loop regardless of any gate. So
        # every delete/preserve assertion here needs 2+ attachments
        # sharing one identity (`_ts()` sorts on the 6-digit token
        # right after WeekEnding_{week}_).
        newer = self._attachment(self._name(wr, identifier, ts="120001"), newer_id)
        older = self._attachment(self._name(wr, identifier, ts="120000"), older_id)
        return newer, older

    def test_keep_historical_none_matches_constant_off(self):
        # keep_historical=None must fall back to the module constant --
        # constant OFF prunes the older duplicate exactly as it does
        # today (no callers changed this path).
        newer, older = self._dup_pair("90001", "Bob", newer_id=20, older_id=10)
        deleted = self._run(
            [newer, older], valid_wr_weeks=set(), keep_historical=None,
            module_constant=False,
        )
        self.assertEqual(deleted, [older.id])

    def test_keep_historical_none_matches_constant_on(self):
        # Same fallback, constant ON preserves the older duplicate
        # exactly as it does today.
        newer, older = self._dup_pair("90001", "Bob", newer_id=20, older_id=10)
        deleted = self._run(
            [newer, older], valid_wr_weeks=set(), keep_historical=None,
            module_constant=True,
        )
        self.assertEqual(deleted, [])

    def test_keep_historical_true_skips_regardless_of_constant_off(self):
        newer, older = self._dup_pair("90001", "Bob", newer_id=20, older_id=10)
        deleted = self._run(
            [newer, older], valid_wr_weeks=set(), keep_historical=True,
            module_constant=False,
        )
        self.assertEqual(deleted, [])

    def test_keep_historical_false_deletes_regardless_of_constant_on(self):
        newer, older = self._dup_pair("90001", "Bob", newer_id=20, older_id=10)
        deleted = self._run(
            [newer, older], valid_wr_weeks=set(), keep_historical=False,
            module_constant=True,
        )
        self.assertEqual(deleted, [older.id])

    def test_strict_subset_groups_issues_zero_deletes_for_untouched_identities(self):
        # The load-bearing case: the sheet carries several identities;
        # this run's valid_wr_weeks (built from a strict-subset
        # `groups`, as an incremental run would produce) covers only
        # one of them (a single, non-duplicated attachment -- never
        # touched regardless of any gate). The two untouched identities
        # each carry a duplicate pair that keep_historical=True must
        # preserve in full.
        live = self._attachment(self._name("90001", "Bob"), 10)
        untouched_a_new, untouched_a_old = self._dup_pair(
            "90002", "Carol", newer_id=21, older_id=11,
        )
        untouched_b_new, untouched_b_old = self._dup_pair(
            "90003", "Dan", newer_id=22, older_id=12,
        )
        valid_wr_weeks = {("90001", self.WEEK, "primary", "Bob")}
        deleted = self._run(
            [live, untouched_a_new, untouched_a_old, untouched_b_new, untouched_b_old],
            valid_wr_weeks=valid_wr_weeks,
            keep_historical=True,
            module_constant=False,
        )
        self.assertEqual(deleted, [])

    def test_omitting_keep_historical_kwarg_matches_default_full_mode(self):
        # Regression: every pre-existing call site (and every existing
        # test) omits keep_historical entirely -- this must behave
        # byte-identically to explicitly passing None.
        from pipeline.cleanup import cleanup_untracked_sheet_attachments

        newer, older = self._dup_pair("90001", "Bob", newer_id=20, older_id=10)
        self._gwp.KEEP_HISTORICAL_WEEKS = False
        sheet, cache = self._sheet_and_cache([newer, older])
        deleted_ids: list[int] = []
        client = self._client(deleted_ids)
        cleanup_untracked_sheet_attachments(
            client=client,
            target_sheet_id=self.SHEET_ID,
            valid_wr_weeks=set(),
            test_mode=False,
            attachment_cache=cache,
            target_sheet=sheet,
            # keep_historical intentionally omitted.
        )
        self.assertEqual(deleted_ids, [older.id])


class OrchestrateKeepHistoricalWiringTests(unittest.TestCase):
    """Source-inspection guard: both cleanup_untracked_sheet_attachments
    call sites in pipeline.orchestrate pass keep_historical=True only
    when the resolved run mode is incremental, pass None otherwise, and
    never flip the global KEEP_HISTORICAL_WEEKS constant to achieve it.
    """

    def test_two_call_sites_pass_keep_historical_true_conditionally(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        self.assertEqual(
            src.count(
                "keep_historical=True if _resolved_mode == 'incremental' else None"
            ),
            2,
        )

    def test_global_constant_never_reassigned_in_orchestrate(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        # The one pre-existing facade-read prelude line (main()'s
        # test-mutable-constant binding, predates this plan) is the
        # ONLY assignment to this name -- no incremental-mode logic
        # added by this plan reassigns the global constant to achieve
        # the call-boundary override.
        self.assertEqual(
            src.count("KEEP_HISTORICAL_WEEKS = _gwp.KEEP_HISTORICAL_WEEKS"), 1,
        )
        self.assertNotIn("KEEP_HISTORICAL_WEEKS = True", src)
        self.assertNotIn("KEEP_HISTORICAL_WEEKS = False", src)
        self.assertNotIn('os.environ["KEEP_HISTORICAL_WEEKS"]', src)
        self.assertNotIn("os.environ['KEEP_HISTORICAL_WEEKS']", src)

# ── 11-03 Task 2 (D-06 hash-history preservation): gate the stale-key
# prune on full mode as well as the existing time-budget guard ─────────

class HashHistoryPruneTests(unittest.TestCase):
    """CONTEXT.md D-06's hash-history half: the stale-key prune's
    existing time-budget guard in ``pipeline.orchestrate.main`` is
    WIDENED (not replaced) to also require the resolved run mode be
    'full'. The prune block is deeply nested inside ``main()`` (not a
    standalone function), so behavior is pinned the same way
    ``tests/test_security_audit_followup.py::TestHashHistoryPruneUsesSanitizedWr``
    already pins this exact code region: replicate the verified-by-
    source-inspection gate/derivation locally against a small fixture.
    """

    @staticmethod
    def _gate(time_budget_exceeded, mode):
        return not time_budget_exceeded and mode == 'full'

    @staticmethod
    def _apply(hash_history, current_keys, time_budget_exceeded, mode):
        history = dict(hash_history)
        if HashHistoryPruneTests._gate(time_budget_exceeded, mode):
            stale_keys = [k for k in history if k not in current_keys]
            for sk in stale_keys:
                del history[sk]
        return history

    def test_gate_condition_matches_source_byte_for_byte(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        self.assertIn(
            "if not _time_budget_exceeded and _resolved_mode == 'full':",
            src,
        )

    def test_full_mode_not_exceeded_prunes_stale_keys_as_today(self):
        hash_history = {
            "90001|041926|primary|": {"hash": "a"},
            "STALE|041926|primary|": {"hash": "b"},
        }
        current_keys = {"90001|041926|primary|"}
        result = self._apply(
            hash_history, current_keys, time_budget_exceeded=False, mode="full",
        )
        self.assertEqual(set(result), {"90001|041926|primary|"})

    def test_full_mode_time_budget_exceeded_skips_as_today(self):
        hash_history = {
            "90001|041926|primary|": {"hash": "a"},
            "STALE|041926|primary|": {"hash": "b"},
        }
        current_keys = {"90001|041926|primary|"}
        result = self._apply(
            hash_history, current_keys, time_budget_exceeded=True, mode="full",
        )
        self.assertEqual(result, hash_history)

    def test_incremental_mode_preserves_every_key_regardless_of_time_budget(self):
        # The load-bearing case: current_keys (derived from this run's
        # strict-subset `groups`) holds one key, hash_history holds
        # several -- an incremental run must not prune ANY of them.
        hash_history = {
            "90001|041926|primary|": {"hash": "a"},
            "90002|041926|primary|": {"hash": "b"},
            "90003|041926|primary|": {"hash": "c"},
        }
        current_keys = {"90001|041926|primary|"}
        for time_budget_exceeded in (False, True):
            with self.subTest(time_budget_exceeded=time_budget_exceeded):
                result = self._apply(
                    hash_history, current_keys,
                    time_budget_exceeded=time_budget_exceeded, mode="incremental",
                )
                self.assertEqual(result, hash_history)

    def test_zero_keys_removed_for_strict_subset_groups_in_incremental_mode(self):
        hash_history = {
            f"9000{i}|041926|primary|": {"hash": str(i)} for i in range(5)
        }
        current_keys = {"90000|041926|primary|"}
        result = self._apply(
            hash_history, current_keys, time_budget_exceeded=False, mode="incremental",
        )
        self.assertEqual(len(result), len(hash_history))
        self.assertEqual(set(result), set(hash_history))

    def test_history_updates_write_stays_outside_the_gate(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        if_idx = src.index("if history_updates:")
        elif_idx = src.index("elif _hash_history_migration_dirty:", if_idx)
        block = src[if_idx:elif_idx]
        # save_hash_history must be called exactly once in this block,
        # unconditionally at the `if history_updates:` level -- never
        # only inside the mode/time-budget-gated prune.
        self.assertEqual(
            block.count("save_hash_history(HASH_HISTORY_PATH, hash_history)"), 1,
        )

    def test_incremental_skip_is_logged_with_preserved_key_count(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        self.assertIn("elif _resolved_mode != 'full':", src)
        elif_idx = src.index("elif _resolved_mode != 'full':")
        gate_idx = src.index(
            "if not _time_budget_exceeded and _resolved_mode == 'full':"
        )
        # The suppressed-path elif must be the sibling of the widened
        # gate `if` above (same prune block), not some unrelated
        # elif elsewhere in main().
        self.assertLess(gate_idx, elif_idx)
        self.assertLess(elif_idx - gate_idx, 9000)
        block = src[elif_idx:elif_idx + 500]
        self.assertIn("len(hash_history)", block)


# ── 11-03 Task 3 (D-06 off-contract gates): pin the already-safe
# legacy-migration scope builders and prove zero off-contract
# deletions for a WR absent from `groups` ───────────────────────────────

class ScopeDerivationTests(unittest.TestCase):
    """RESEARCH.md Pitfall 2 / Assumption A3: the seven off-contract /
    legacy-migration gates inside cleanup_untracked_sheet_attachments
    are already safe by construction because every scope set
    (sub_wr_scope, vac_legacy_wr_scope, primary_wr_scope) is built from
    this run's `groups`. This class PINS that safety argument with a
    regression test instead of re-gating the seven gates individually
    (Pitfall 2: re-gating them is risk-adding scope creep on
    billing-critical code the seven gates are already proven safe on).
    """

    IN_SCOPE_WR = "90001"
    ABSENT_WR = "90002"
    WEEK = "041926"
    SHEET_ID = 5723337641643908

    def _groups_with_only_in_scope_wr(self):
        # One subcontractor-variant group (feeds sub_wr_scope), one
        # vac_crew-variant group (feeds vac_legacy_wr_scope), one
        # primary-variant group (feeds primary_wr_scope) -- all keyed
        # to IN_SCOPE_WR. ABSENT_WR has NO entry in `groups` at all,
        # simulating "this run did not process it" (incremental mode).
        return {
            f"{self.WEEK}_sub": [{
                'Work Request #': self.IN_SCOPE_WR,
                '__variant': 'reduced_sub',
            }],
            f"{self.WEEK}_vac": [{
                'Work Request #': self.IN_SCOPE_WR,
                '__variant': 'vac_crew',
            }],
            # _build_primary_wr_scope additionally requires the group
            # KEY to carry the Subproject D `_USER_` partition token
            # (distinguishing a partitioned primary from a bare one).
            f"{self.WEEK}_USER_primary": [{
                'Work Request #': self.IN_SCOPE_WR,
                '__variant': 'primary',
            }],
        }

    @staticmethod
    def _att(name, att_id):
        att = mock.MagicMock()
        att.name = name
        att.id = att_id
        return att

    def test_absent_wr_excluded_from_all_three_scope_sets(self):
        from pipeline.attribution import (
            _build_primary_wr_scope,
            _build_subcontractor_wr_scope,
            _build_vac_crew_wr_scope,
        )

        groups = self._groups_with_only_in_scope_wr()
        sub_scope = _build_subcontractor_wr_scope(groups)
        vac_scope = _build_vac_crew_wr_scope(groups)
        primary_scope = _build_primary_wr_scope(groups)

        self.assertIn(self.IN_SCOPE_WR, sub_scope)
        self.assertIn(self.IN_SCOPE_WR, vac_scope)
        self.assertIn(self.IN_SCOPE_WR, primary_scope)
        self.assertNotIn(self.ABSENT_WR, sub_scope)
        self.assertNotIn(self.ABSENT_WR, vac_scope)
        self.assertNotIn(self.ABSENT_WR, primary_scope)

    def test_zero_offcontract_deletions_for_wr_absent_from_groups(self):
        from pipeline.attribution import (
            _build_primary_wr_scope,
            _build_subcontractor_wr_scope,
            _build_vac_crew_wr_scope,
        )
        from pipeline.cleanup import cleanup_untracked_sheet_attachments

        groups = self._groups_with_only_in_scope_wr()
        sub_scope = _build_subcontractor_wr_scope(groups)
        vac_scope = _build_vac_crew_wr_scope(groups)
        primary_scope = _build_primary_wr_scope(groups)

        # Legacy-shaped bare attachments for the ABSENT WR -- each
        # would be off-contract IF ABSENT_WR were in scope. Because
        # it's absent from every scope set above, none of the three
        # scope-gated off-contract branches can fire for it.
        atts = [
            self._att(
                f"WR_{self.ABSENT_WR}_WeekEnding_{self.WEEK}_120000_ReducedSub_aabbcc.xlsx",
                10,
            ),
            self._att(
                f"WR_{self.ABSENT_WR}_WeekEnding_{self.WEEK}_120001_VacCrew_ddeeff.xlsx",
                11,
            ),
            self._att(
                f"WR_{self.ABSENT_WR}_WeekEnding_{self.WEEK}_120002_ffgghh.xlsx",
                12,
            ),
        ]
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 111
        sheet.rows = [row]
        cache = {111: atts}

        deleted_ids: list[int] = []
        client = mock.MagicMock()

        def _delete(sheet_id, att_id):
            deleted_ids.append(att_id)
            return mock.MagicMock()

        client.Attachments.delete_attachment.side_effect = _delete

        cleanup_untracked_sheet_attachments(
            client=client,
            target_sheet_id=self.SHEET_ID,
            valid_wr_weeks=set(),
            test_mode=False,
            attachment_cache=cache,
            target_sheet=sheet,
            sub_wr_scope=sub_scope,
            sub_offcontract_variants={'helper', 'primary'},
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
            vac_legacy_wr_scope=vac_scope,
            primary_wr_scope=primary_scope,
            # keep_historical=True isolates the off-contract gates: with
            # the base identity-loop gate forced to preserve, any
            # delete_attachment call observed here can ONLY have come
            # from one of the (unconditional, KEEP_HISTORICAL_WEEKS-
            # independent) off-contract branches.
            keep_historical=True,
        )

        self.assertEqual(deleted_ids, [])

    def test_pipeline_cleanup_offcontract_gates_diff_is_untouched(self):
        # RESEARCH.md Pitfall 2: no incremental-mode conditional was
        # added inside the seven off-contract / legacy-migration gates
        # themselves -- the safety argument is pinned by the two tests
        # above, not by touching this region.
        import inspect
        import pipeline.cleanup as cleanup_mod

        src = inspect.getsource(cleanup_mod.cleanup_untracked_sheet_attachments)
        self.assertNotIn("_resolved_mode", src)
        self.assertNotIn("mode == 'incremental'", src)


# ── 11-04 Task 1 (D-04 Option C): PHASE 2a delta read -> memory write ->
# affected-set mapping -> PHASE 2b scoped re-fetch, plus the post-
# grouping affected-pair restriction ────────────────────────────────────

def _delta_source(sheet_id=111222, name="Test Sheet"):
    return {
        "id": sheet_id,
        "name": name,
        "column_mapping": {
            "Work Request #": 10,
            "Weekly Reference Logged Date": 20,
            "Foreman": 30,
        },
    }


def _delta_cell(column_id, value):
    return SimpleNamespace(column_id=column_id, value=value, display_value=None)


def _delta_sheet(rows, version=9):
    return SimpleNamespace(version=version, rows=rows)


def _delta_row(row_id, wr, week_iso, foreman="Bob"):
    return SimpleNamespace(
        id=row_id,
        modified_at=None,
        cells=[
            _delta_cell(10, wr),
            _delta_cell(20, week_iso),
            _delta_cell(30, foreman),
        ],
    )


class IncrementalScopeTests(unittest.TestCase):
    """Plan 04 Task 1: ``_run_phase2_incremental`` (PHASE 2a delta read
    -> the unmodified ``_run_memory_write_phase`` -> affected-set ->
    sheet mapping -> PHASE 2b scoped re-fetch), ``_filter_groups_to_
    affected`` (the post-grouping affected-pair restriction), and
    ``pipeline.fetch.map_delta_sheet_rows`` (the delta-probe row
    mapper). Mocked Smartsheet client + Supabase reader/writer
    throughout -- no live calls.
    """

    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()

    def test_full_mode_never_calls_delta_probe_or_mapping_query(self):
        # Structural: the ONLY call site touching fetch_sheet_delta /
        # map_affected_to_sheets (transitively, via
        # _run_phase2_incremental) sits strictly between the
        # incremental-mode guard and the full-mode guard in main() --
        # mirrors this file's established source-inspection convention
        # for logic too deep inside main() to invoke directly.
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        self.assertEqual(src.count("_run_phase2_incremental("), 1)
        incr_idx = src.index("if _resolved_mode == 'incremental':")
        call_idx = src.index("_run_phase2_incremental(")
        full_idx = src.index("if _resolved_mode == 'full':")
        self.assertLess(incr_idx, call_idx)
        self.assertLess(call_idx, full_idx)

    def test_one_changed_row_delta_reads_and_writes_only_delta_rows(self):
        import pipeline.orchestrate as orch

        source = _delta_source(sheet_id=111222)
        sheet = _delta_sheet([_delta_row(1, "90001", "2026-08-30")])
        captured: dict = {}

        def _fake_write(all_rows, run_id, session_start):
            captured["rows"] = all_rows
            return {
                "sheets_written": 1, "sheets_errored": 0,
                "rows_sent": len(all_rows), "rows_changed": 1,
                "affected": {("90001", "2026-08-30")},
                "memory_confirmed": True,
            }

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": sheet, "version": 9, "calls": 2,
            },
        ) as mock_probe, mock.patch.object(
            orch, "_run_memory_write_phase", side_effect=_fake_write,
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets",
            return_value={111222},
        ) as mock_map, mock.patch.object(
            orch, "get_all_source_rows",
            return_value=[{"Work Request #": "90001"}],
        ) as mock_full:
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[source],
                watermarks={
                    111222: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                },
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertTrue(result["ok"])
        mock_probe.assert_called_once()
        self.assertEqual(len(captured["rows"]), 1)
        self.assertEqual(captured["rows"][0]["Work Request #"], "90001")
        self.assertEqual(result["affected"], {("90001", "2026-08-30")})
        mock_map.assert_called_once_with({("90001", "2026-08-30")})
        mock_full.assert_called_once()

    def test_mapping_includes_sheet_with_no_changed_rows_this_run(self):
        import pipeline.orchestrate as orch

        source_a = _delta_source(sheet_id=111222, name="Sheet A")
        source_b = _delta_source(sheet_id=333444, name="Sheet B")
        sheet_a = _delta_sheet([_delta_row(1, "90001", "2026-08-30")])

        def _probe(client, source, last_version, rows_modified_since):
            if source["id"] == 111222:
                return {
                    "escalate": False, "sheet": sheet_a, "version": 9,
                    "calls": 2,
                }
            return {
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            }

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta", side_effect=_probe,
        ), mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                "sheets_written": 1, "sheets_errored": 0,
                "rows_sent": 1, "rows_changed": 1,
                "affected": {("90001", "2026-08-30")},
                "memory_confirmed": True,
            },
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets",
            return_value={111222, 333444},
        ), mock.patch.object(
            orch, "get_all_source_rows", return_value=[],
        ) as mock_full:
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[source_a, source_b],
                watermarks={
                    111222: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                    333444: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                },
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertTrue(result["ok"])
        narrowed_call_sheets = mock_full.call_args[0][1]
        self.assertEqual(
            {s["id"] for s in narrowed_call_sheets}, {111222, 333444},
        )

    def test_filter_groups_restricts_to_affected_pairs(self):
        import pipeline.orchestrate as orch

        groups = {
            "key_a": [{
                "Work Request #": "90001",
                "Weekly Reference Logged Date": "2026-08-30",
            }],
            "key_b": [{
                "Work Request #": "90002",
                "Weekly Reference Logged Date": "2026-08-30",
            }],
        }
        affected = {("90001", "2026-08-30")}

        filtered = orch._filter_groups_to_affected(groups, affected)

        self.assertEqual(set(filtered), {"key_a"})

    def test_filter_groups_empty_groups_is_noop(self):
        import pipeline.orchestrate as orch

        self.assertEqual(
            orch._filter_groups_to_affected({}, {("90001", "2026-08-30")}),
            {},
        )

    def test_moved_week_keeps_both_new_and_prior_pair_groups(self):
        import pipeline.orchestrate as orch

        groups = {
            "new_week_key": [{
                "Work Request #": "90001",
                "Weekly Reference Logged Date": "2026-08-30",
            }],
            "prior_week_key": [{
                "Work Request #": "90001",
                "Weekly Reference Logged Date": "2026-08-23",
            }],
            "unrelated_key": [{
                "Work Request #": "90002",
                "Weekly Reference Logged Date": "2026-08-30",
            }],
        }
        # upsert_rows_bulk's own server-side UNION already includes both
        # the new pair and the prior pair when week_ending moved.
        affected = {("90001", "2026-08-30"), ("90001", "2026-08-23")}

        filtered = orch._filter_groups_to_affected(groups, affected)

        self.assertEqual(set(filtered), {"new_week_key", "prior_week_key"})

    def test_empty_affected_set_yields_empty_groups_successful_run(self):
        import pipeline.orchestrate as orch

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            },
        ), mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                "sheets_written": 0, "sheets_errored": 0,
                "rows_sent": 0, "rows_changed": 0, "affected": set(),
                "memory_confirmed": True,
            },
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets",
        ) as mock_map, mock.patch.object(
            orch, "get_all_source_rows", return_value=[],
        ) as mock_full:
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[_delta_source()],
                watermarks={
                    111222: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                },
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["affected"], set())
        self.assertEqual(result["all_rows"], [])
        # An empty affected set never even queries the mapping table --
        # this is "nothing changed", not a failure.
        mock_map.assert_not_called()
        mock_full.assert_not_called()

        groups = orch._filter_groups_to_affected({}, result["affected"])
        self.assertEqual(groups, {})

    def test_delta_probe_escalation_falls_back_to_full_mode(self):
        import pipeline.orchestrate as orch

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={"escalate": True, "reason": "boom"},
        ):
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[_delta_source()],
                watermarks={},
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertFalse(result["ok"])
        self.assertIn(
            "trigger_delta_probe_escalation", result["fallback_reason"],
        )

    def test_memory_write_exception_falls_back_to_full_mode(self):
        import pipeline.orchestrate as orch

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            },
        ), mock.patch.object(
            orch, "_run_memory_write_phase",
            side_effect=RuntimeError("boom"),
        ):
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[_delta_source()],
                watermarks={},
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertFalse(result["ok"])
        self.assertIn(
            "trigger_memory_write_exception", result["fallback_reason"],
        )

    def test_empty_mapping_for_nonempty_affected_set_falls_back(self):
        import pipeline.orchestrate as orch

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            },
        ), mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                "sheets_written": 1, "sheets_errored": 0,
                "rows_sent": 1, "rows_changed": 1,
                "affected": {("90001", "2026-08-30")},
                "memory_confirmed": True,
            },
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets", return_value=set(),
        ):
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[_delta_source()],
                watermarks={},
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertFalse(result["ok"])
        self.assertIn(
            "trigger_affected_set_mapping_empty", result["fallback_reason"],
        )

    def test_trigger1_flagged_sheet_gets_full_read_not_delta_probe(self):
        import pipeline.orchestrate as orch

        source_full = _delta_source(sheet_id=555, name="New Sheet")
        source_delta = _delta_source(sheet_id=666, name="Known Sheet")

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            },
        ) as mock_probe, mock.patch.object(
            orch, "get_all_source_rows",
            return_value=[
                {"Work Request #": "90001", "__source_sheet_id": 555},
            ],
        ) as mock_full, mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                "sheets_written": 0, "sheets_errored": 0,
                "rows_sent": 0, "rows_changed": 0, "affected": set(),
                "memory_confirmed": True,
            },
        ):
            orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[source_full, source_delta],
                watermarks={
                    666: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                },
                per_sheet_reasons={555: "trigger1_no_watermark: ..."},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        probed_sheet_ids = {
            call.args[1]["id"] for call in mock_probe.call_args_list
        }
        self.assertEqual(probed_sheet_ids, {666})
        first_call_sheets = mock_full.call_args_list[0].args[1]
        self.assertEqual({s["id"] for s in first_call_sheets}, {555})

    def test_trigger3_flagged_sheet_is_skipped_entirely(self):
        import pipeline.orchestrate as orch

        source_isolated = _delta_source(sheet_id=777, name="Isolated Sheet")

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
        ) as mock_probe, mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                "sheets_written": 0, "sheets_errored": 0,
                "rows_sent": 0, "rows_changed": 0, "affected": set(),
                "memory_confirmed": True,
            },
        ):
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[source_isolated],
                watermarks={},
                per_sheet_reasons={
                    777: "trigger3_auth_error: sheet isolated (401/403)",
                },
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        mock_probe.assert_not_called()
        self.assertTrue(result["ok"])

    def test_map_delta_sheet_rows_maps_columns_and_provenance(self):
        from pipeline.fetch import map_delta_sheet_rows

        source = _delta_source(sheet_id=111222)
        sheet = _delta_sheet(
            [_delta_row(42, "90001", "2026-08-30", foreman="Alice")]
        )

        rows = map_delta_sheet_rows(sheet, source)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["Work Request #"], "90001")
        self.assertEqual(row["Weekly Reference Logged Date"], "2026-08-30")
        self.assertEqual(row["Foreman"], "Alice")
        self.assertEqual(row["__source_sheet_id"], 111222)
        self.assertEqual(row["__row_id"], 42)

    def test_map_delta_sheet_rows_drops_rows_missing_essential_fields(self):
        from pipeline.fetch import map_delta_sheet_rows

        source = _delta_source(sheet_id=111222)
        incomplete_row = SimpleNamespace(
            id=1, modified_at=None,
            cells=[_delta_cell(10, "90001")],  # no week-ending cell
        )
        sheet = _delta_sheet([incomplete_row])

        rows = map_delta_sheet_rows(sheet, source)

        self.assertEqual(rows, [])


# ── 11-04 Task 2: map_affected_to_sheets hardening -- parameterisation,
# batching, fail-open ────────────────────────────────────────────────────

class AffectedSetMappingTests(unittest.TestCase):
    """Plan 04 Task 2: ``map_affected_to_sheets`` bound parameterisation
    (never string interpolation), chunking at ``_MAPPING_CHUNK_SIZE``,
    all-or-nothing on a mid-chunk failure, and the three distinguishable
    empty outcomes (genuinely-empty match / None response / transport
    failure).
    """

    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()

    def test_empty_input_performs_zero_calls(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.map_affected_to_sheets(set())

        self.assertEqual(result, set())
        client.schema.assert_not_called()

    def test_client_unavailable_returns_empty_set(self):
        from pipeline_memory import reader as mem_reader

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=None
        ):
            result = mem_reader.map_affected_to_sheets(
                {("90001", "2026-08-30")}
            )

        self.assertEqual(result, set())

    def test_returns_matching_sheet_ids_for_exact_pair_membership(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value.in_.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[
            {"sheet_id": 111, "wr": "90001", "week_ending": "2026-08-30"},
            # A different pair sharing the same WR must NOT contribute a
            # false match through a wr x week cross-product artifact.
            {"sheet_id": 222, "wr": "90001", "week_ending": "2026-01-01"},
        ])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.map_affected_to_sheets(
                {("90001", "2026-08-30")}
            )

        self.assertEqual(result, {111})

    def test_wr_metacharacters_carried_as_bound_value_not_interpolated(self):
        from pipeline_memory import reader as mem_reader

        malicious_wr = "90001'; DROP TABLE row_state; --"
        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value.in_.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            mem_reader.map_affected_to_sheets({(malicious_wr, "2026-08-30")})

        in_call = (
            client.schema.return_value.table.return_value
            .select.return_value.in_
        )
        self.assertEqual(in_call.call_args[0][0], "wr")
        self.assertIn(malicious_wr, in_call.call_args[0][1])

    def test_affected_set_larger_than_chunk_threshold_issues_multiple_requests(self):
        from pipeline_memory import reader as mem_reader

        pairs = {
            (f"WR{i}", "2026-08-30")
            for i in range(mem_reader._MAPPING_CHUNK_SIZE + 5)
        }
        client = mock.Mock()
        call_count = {"n": 0}

        def _execute():
            call_count["n"] += 1
            sid = 100 + call_count["n"]
            return SimpleNamespace(data=[
                {"sheet_id": sid, "wr": "WR0", "week_ending": "2026-08-30"},
            ])

        (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value.in_.return_value
            .execute.side_effect
        ) = _execute

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.map_affected_to_sheets(pairs)

        self.assertEqual(call_count["n"], 2)
        self.assertEqual(result, {101, 102})

    def test_mid_chunk_failure_discards_partial_union_returns_empty(self):
        from pipeline_memory import reader as mem_reader

        pairs = {
            (f"WR{i}", "2026-08-30")
            for i in range(mem_reader._MAPPING_CHUNK_SIZE + 5)
        }
        client = mock.Mock()
        call_count = {"n": 0}

        def _execute():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return SimpleNamespace(data=[
                    {
                        "sheet_id": 101, "wr": "WR0",
                        "week_ending": "2026-08-30",
                    },
                ])
            raise Exception("transport boom")

        (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value.in_.return_value
            .execute.side_effect
        ) = _execute

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.map_affected_to_sheets(pairs)

        # A partial union (from the successful first chunk) must NEVER
        # be returned once a later chunk fails -- that would silently
        # narrow the regeneration scope while looking successful.
        self.assertEqual(result, set())

    def test_none_response_payload_returns_empty_distinct_from_transport_failure(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value.in_.return_value
        )
        query.execute.return_value = SimpleNamespace(data=None)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            with self.assertLogs(level="WARNING") as log_ctx:
                result = mem_reader.map_affected_to_sheets(
                    {("90001", "2026-08-30")}
                )

        self.assertEqual(result, set())
        self.assertTrue(
            any("None response payload" in m for m in log_ctx.output)
        )

    def test_transport_failure_returns_empty_and_is_logged_distinctly(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value.in_.return_value
            .execute.side_effect
        ) = Exception("boom")

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            with self.assertLogs(level="WARNING") as log_ctx:
                result = mem_reader.map_affected_to_sheets(
                    {("90001", "2026-08-30")}
                )

        self.assertEqual(result, set())
        self.assertTrue(
            any("transport or circuit-breaker" in m for m in log_ctx.output)
        )

    def test_genuinely_empty_match_returns_empty_set(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.in_.return_value.in_.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.map_affected_to_sheets(
                {("90001", "2026-08-30")}
            )

        self.assertEqual(result, set())

    def test_caller_falls_back_to_full_mode_on_empty_mapping(self):
        # Task 2's own acceptance criterion names this exact assertion;
        # kept here (in addition to IncrementalScopeTests) so this class
        # is self-contained for a reader auditing Task 2 alone.
        import pipeline.orchestrate as orch

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            },
        ), mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                "sheets_written": 1, "sheets_errored": 0,
                "rows_sent": 1, "rows_changed": 1,
                "affected": {("90001", "2026-08-30")},
                "memory_confirmed": True,
            },
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets", return_value=set(),
        ):
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[_delta_source()],
                watermarks={},
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertFalse(result["ok"])
        self.assertTrue(result["fallback_reason"])


# ── 11-04 Task 3: D-05 REQUIREMENTS.md note + scoped run_ledger
# counters ────────────────────────────────────────────────────────────

class ScopedCounterTests(unittest.TestCase):
    """Plan 04 Task 3: ``sheets_changed`` / ``rows_seen`` /
    ``groups_affected`` / ``groups_generated`` stay mode-aware and
    distinguishable at both ``run_ledger_finish`` call sites;
    ``run_summary.json``'s frozen 21-key contract is untouched.
    """

    def test_sheets_written_reflects_delta_change_not_phase2b_refetch_count(self):
        import pipeline.orchestrate as orch

        source_a = _delta_source(sheet_id=111222, name="Changed Sheet")
        source_b = _delta_source(sheet_id=333444, name="Unchanged Sheet")
        sheet_a = _delta_sheet([_delta_row(1, "90001", "2026-08-30")])

        def _probe(client, source, last_version, rows_modified_since):
            if source["id"] == 111222:
                return {
                    "escalate": False, "sheet": sheet_a, "version": 9,
                    "calls": 2,
                }
            return {
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            }

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta", side_effect=_probe,
        ), mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                # ONLY the sheet whose delta read produced a changed row.
                "sheets_written": 1,
                "sheets_errored": 0, "rows_sent": 1, "rows_changed": 1,
                "affected": {("90001", "2026-08-30")},
                "memory_confirmed": True,
            },
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets",
            # PHASE 2b re-fetches BOTH sheets (the mapping widened to
            # every sheet holding a row for the affected pair).
            return_value={111222, 333444},
        ), mock.patch.object(
            orch, "get_all_source_rows", return_value=[],
        ):
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[source_a, source_b],
                watermarks={
                    111222: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                    333444: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                },
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )

        self.assertEqual(result["mem_result"]["sheets_written"], 1)
        self.assertEqual(result["mapped_sheet_count"], 2)
        self.assertNotEqual(
            result["mem_result"]["sheets_written"],
            result["mapped_sheet_count"],
        )

    def test_run_ledger_finish_call_sites_report_phase2a_and_phase2b_counters_separately(self):
        import inspect
        import pipeline.orchestrate as orch
        from pipeline_memory.writer import _RUN_LEDGER_FINISH_COLUMNS

        src = inspect.getsource(orch.main)
        self.assertEqual(
            src.count(
                "mem_phase2a_delta_rows=_incremental_delta_rows_count"
            ),
            2,
        )
        self.assertEqual(
            src.count(
                "mem_phase2b_sheets_refetched="
                "_incremental_mapped_sheet_count"
            ),
            2,
        )
        # Both new counters land in notes (run_ledger_finish folds any
        # kwarg not in _RUN_LEDGER_FINISH_COLUMNS into notes
        # automatically) -- no new SQL column, no new run_summary.json
        # key.
        self.assertNotIn(
            "mem_phase2a_delta_rows", _RUN_LEDGER_FINISH_COLUMNS,
        )
        self.assertNotIn(
            "mem_phase2b_sheets_refetched", _RUN_LEDGER_FINISH_COLUMNS,
        )

    def test_rows_seen_and_groups_affected_source_from_correct_variables(self):
        import inspect
        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        # rows_seen reads all_rows -- the PHASE 2b re-fetch result on an
        # incremental run, the single full fetch on a full run -- never
        # a separate PHASE-2a-only count.
        self.assertIn(
            "rows_seen=len(all_rows) if 'all_rows' in dir() else 0", src,
        )
        # groups_affected reads _mem_affected -- the exact affected set
        # _run_phase2_incremental returned (or the full-mode
        # _run_memory_write_phase's own affected set) -- so a divergence
        # from groups_generated (the count that actually regenerated) is
        # directly visible.
        self.assertEqual(src.count("groups_affected=len(_mem_affected)"), 2)
        self.assertGreaterEqual(
            src.count("groups_generated=_groups_generated"), 2,
        )
        self.assertIn(
            "comparable only against another incremental run", src,
        )

    def test_run_summary_still_21_keys_and_unmodified(self):
        golden = _REPO_ROOT / "tests" / "golden" / "run_summary_baseline.json"
        data = json.loads(golden.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 21)


# ── Plan 07 Task 1: pipeline_memory.reader.get_parity_streak (D-09) ─────

def _streak_row(run_id, verdict=None, execution_type="production_frequent"):
    """Build a synthetic ``run_ledger`` row for the streak scan.

    ``verdict is None`` means the row's ``notes`` carries no
    ``parity_verdict`` key at all -- the "absent verdict" case, which the
    scan treats identically to an explicit ``skipped``.
    """
    notes = {"execution_type": execution_type}
    if verdict is not None:
        notes["parity_verdict"] = verdict
    return {
        "run_id": run_id,
        "started_at": "2026-08-26T00:00:00+00:00",
        "status": "success",
        "notes": notes,
    }


class ParityStreakTests(unittest.TestCase):
    """Phase 11 Plan 07, Task 1 (D-09): ``get_parity_streak`` scans
    ``run_ledger`` newest-first for consecutive ``production_frequent``
    ``pass`` verdicts -- pass counts, fail resets and stops, skipped (and
    an absent verdict) is excluded from the sequence entirely.
    """

    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()

    def _mock_rows(self, rows):
        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.order.return_value.limit.return_value
        )
        query.execute.return_value = SimpleNamespace(data=rows)
        return client

    def test_five_consecutive_pass_yields_streak_of_five(self):
        from pipeline_memory import reader as mem_reader

        rows = [_streak_row(f"r{i}", "pass") for i in range(5)]
        client = self._mock_rows(rows)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertEqual(result["streak"], 5)
        self.assertEqual(len(result["contributing_run_ids"]), 5)

    def test_skipped_between_two_pass_rows_yields_streak_of_two(self):
        """Load-bearing: a skipped row sandwiched between two passes must
        neither count nor reset -- the streak is two, not one and not a
        reset to zero."""
        from pipeline_memory import reader as mem_reader

        rows = [
            _streak_row("r-newest", "pass"),
            _streak_row("r-middle", "skipped"),
            _streak_row("r-oldest", "pass"),
        ]
        client = self._mock_rows(rows)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertEqual(result["streak"], 2)
        self.assertIn("r-newest", result["contributing_run_ids"])
        self.assertIn("r-oldest", result["contributing_run_ids"])
        self.assertNotIn("r-middle", result["contributing_run_ids"])

    def test_fail_row_yields_streak_of_zero(self):
        """Load-bearing: a lone fail row yields a streak of zero."""
        from pipeline_memory import reader as mem_reader

        rows = [_streak_row("r1", "fail")]
        client = self._mock_rows(rows)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertEqual(result["streak"], 0)
        self.assertEqual(result["stopped_run_id"], "r1")
        self.assertEqual(result["stopped_verdict"], "fail")

    def test_fail_resets_prior_passes_and_stops_scan(self):
        from pipeline_memory import reader as mem_reader

        rows = [
            _streak_row("r-new", "pass"),
            _streak_row("r-fail", "fail"),
            _streak_row("r-old", "pass"),  # never reached -- scan stopped
        ]
        client = self._mock_rows(rows)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertEqual(result["streak"], 0)
        self.assertEqual(result["contributing_run_ids"], [])
        self.assertEqual(result["rows_examined"], 2)

    def test_absent_verdict_treated_like_skipped(self):
        from pipeline_memory import reader as mem_reader

        rows = [
            _streak_row("r-newest", "pass"),
            _streak_row("r-no-verdict"),  # no parity_verdict key at all
            _streak_row("r-oldest", "pass"),
        ]
        client = self._mock_rows(rows)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertEqual(result["streak"], 2)

    def test_non_production_frequent_rows_are_ignored(self):
        from pipeline_memory import reader as mem_reader

        rows = [
            _streak_row(
                "r-weekly", "fail", execution_type="weekly_comprehensive",
            ),
            _streak_row("r1", "pass"),
            _streak_row("r2", "pass"),
        ]
        client = self._mock_rows(rows)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        # The weekly-run "fail" must not reset/stop a production_frequent
        # streak -- it is ignored entirely, not scanned as a candidate.
        self.assertEqual(result["streak"], 2)

    def test_streak_stops_scanning_once_target_reached(self):
        from pipeline_memory import reader as mem_reader

        rows = [_streak_row(f"r{i}", "pass") for i in range(10)]
        client = self._mock_rows(rows)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertEqual(result["streak"], 5)
        self.assertEqual(result["rows_examined"], 5)

    def test_supabase_failure_returns_none(self):
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
            result = mem_reader.get_parity_streak(limit=10)

        self.assertIsNone(result)

    def test_client_unavailable_returns_none(self):
        from pipeline_memory import reader as mem_reader

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=None
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertIsNone(result)

    def test_no_rows_yields_zero_streak_not_none(self):
        from pipeline_memory import reader as mem_reader

        client = self._mock_rows([])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_parity_streak(limit=10)

        self.assertIsNotNone(result)
        self.assertEqual(result["streak"], 0)

    def test_reports_op_name_for_independent_breaker(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.reader.with_retry",
            return_value=SimpleNamespace(data=[]),
        ) as mocked_retry:
            mem_reader.get_parity_streak(limit=10)

        _, kwargs = mocked_retry.call_args
        self.assertEqual(kwargs.get("op"), "run_ledger_parity_streak")


# ── Greptile P1 on PR #351: fail-open memory result ambiguity ─────────

class MemoryResultAmbiguityTests(unittest.TestCase):
    """A failed, unavailable, disabled or PARTIAL ``upsert_rows_bulk``
    must never be read as "nothing changed" by the incremental path
    (Greptile P1, PR #351, ``pipeline/orchestrate.py`` PHASE 2a).

    Three layers, each pinned here:
      1. ``pipeline_memory.writer.upsert_rows_bulk_result`` reports a
         ``status`` next to the affected set (``ok`` / ``noop`` /
         ``unavailable`` / ``disabled`` / ``partial`` / ``failed``); the
         legacy ``upsert_rows_bulk`` set-returning wrapper is unchanged.
      2. ``_run_memory_write_phase`` folds every sheet's status, the
         pre-flight skip and the mid-loop budget break into one
         ``memory_confirmed`` flag (True ONLY when every delta sheet was
         confirmed ``ok`` or ``noop``).
      3. ``_run_phase2_incremental`` escalates to full mode with
         ``trigger_memory_write_unconfirmed`` BEFORE it reads
         ``affected`` -- an unconfirmed empty or partial affected set can
         only ever WIDEN the regeneration scope, never narrow it
         (T-11-18). A legacy result dict with no ``memory_confirmed``
         key is treated as unconfirmed (fail-closed).
    """

    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()
        os.environ.pop("RUN_MEMORY_WRITE_ENABLED", None)

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()
        os.environ.pop("RUN_MEMORY_WRITE_ENABLED", None)

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _writer_rows(n, start_id=1):
        return [
            {
                "__row_id": start_id + i,
                "Work Request #": f"9{start_id + i:05d}",
                "Foreman": "Alice",
            }
            for i in range(n)
        ]

    @staticmethod
    def _fake_client(affected_rows=None):
        client = mock.Mock()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            mock.Mock(data=list(affected_rows or []))
        )
        return client

    @staticmethod
    def _phase_rows(sheet_id, n, start_id=1):
        return [
            {
                "__row_id": start_id + i,
                "__source_sheet_id": sheet_id,
                "Work Request #": f"9{start_id + i:05d}",
                "Weekly Reference Logged Date": "2026-08-30",
            }
            for i in range(n)
        ]

    @staticmethod
    def _writer_result(status, affected=None, rows_errored=0,
                       rows_skipped=0):
        return {
            "affected": set(affected or ()),
            "status": status,
            "rows_sent": 1,
            "rows_errored": rows_errored,
            "rows_skipped": rows_skipped,
        }

    def _run_phase(self, rows, writer_side_effect, **const_overrides):
        import contextlib

        import pipeline.orchestrate as orch

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True)
            )
            stack.enter_context(mock.patch.object(orch, "TEST_MODE", False))
            for name, value in const_overrides.items():
                stack.enter_context(mock.patch.object(orch, name, value))
            mock_upsert = stack.enter_context(mock.patch.object(
                orch._mem_writer, "upsert_rows_bulk_result",
                side_effect=writer_side_effect,
            ))
            result = orch._run_memory_write_phase(
                rows, "run-1", datetime.datetime.now(),
            )
        return result, mock_upsert

    def _phase2(self, mem_result, map_return=None):
        import pipeline.orchestrate as orch

        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": None, "version": 9, "calls": 1,
            },
        ), mock.patch.object(
            orch, "_run_memory_write_phase", return_value=mem_result,
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets",
            return_value=set(map_return or ()),
        ) as mock_map, mock.patch.object(
            orch, "get_all_source_rows", return_value=[],
        ) as mock_full:
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[_delta_source()],
                watermarks={
                    111222: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                },
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )
        return result, mock_map, mock_full

    # ── 1. writer status vocabulary ──────────────────────────────────

    def test_writer_empty_input_is_noop_with_zero_calls(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = self._fake_client()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            result = mem_writer.upsert_rows_bulk_result(1, "run-1", [])

        self.assertEqual(result["status"], "noop")
        self.assertEqual(result["affected"], set())
        client.schema.assert_not_called()

    def test_writer_client_unavailable_is_unavailable_not_no_change(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=None,
        ):
            result = mem_writer.upsert_rows_bulk_result(
                1, "run-1", self._writer_rows(2),
            )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["affected"], set())

    def test_writer_write_disabled_is_disabled_not_no_change(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "0"
        client = self._fake_client()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            result = mem_writer.upsert_rows_bulk_result(
                1, "run-1", self._writer_rows(2),
            )

        self.assertEqual(result["status"], "disabled")
        client.schema.assert_not_called()

    def test_writer_every_chunk_failing_is_failed(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = self._fake_client()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ), mock.patch(
            "pipeline_memory.writer.with_retry", return_value=None,
        ):
            result = mem_writer.upsert_rows_bulk_result(
                1, "run-1", self._writer_rows(3),
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["affected"], set())
        self.assertEqual(result["rows_errored"], 3)

    def test_writer_one_failed_chunk_is_partial_and_keeps_good_chunk(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = self._fake_client()
        rows = self._writer_rows(mem_writer._CHUNK_ROWS + 5)
        calls = {"n": 0}

        def _retry(fn, **_kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return mock.Mock(
                    data=[{"wr": "900001", "week_ending": "2026-08-30"}],
                )
            return None

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ), mock.patch(
            "pipeline_memory.writer.with_retry", side_effect=_retry,
        ):
            result = mem_writer.upsert_rows_bulk_result(1, "run-1", rows)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["affected"], {("900001", "2026-08-30")})
        self.assertEqual(result["rows_errored"], 5)

    def test_writer_all_chunks_ok_is_ok_even_when_nothing_changed(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = self._fake_client(affected_rows=[])
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            result = mem_writer.upsert_rows_bulk_result(
                1, "run-1", self._writer_rows(2),
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["affected"], set())
        self.assertEqual(result["rows_errored"], 0)
        self.assertEqual(result["rows_sent"], 2)

    def test_writer_skipped_bad_row_ids_are_never_silently_ok(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = self._fake_client()
        rows = [{"__row_id": "not-an-int", "Work Request #": "90001"}]
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            result = mem_writer.upsert_rows_bulk_result(1, "run-1", rows)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["rows_skipped"], 1)
        client.schema.assert_not_called()

    def test_writer_set_wrapper_returns_exactly_the_affected_set(self):
        from pipeline_memory import writer as mem_writer

        with mock.patch.object(
            mem_writer, "upsert_rows_bulk_result",
            return_value=self._writer_result(
                "partial", affected={("90001", "2026-08-30")},
                rows_errored=1,
            ),
        ):
            result = mem_writer.upsert_rows_bulk(
                1, "run-1", self._writer_rows(2),
            )

        self.assertEqual(result, {("90001", "2026-08-30")})

    # ── 2. _run_memory_write_phase: memory_confirmed ─────────────────

    def test_phase_every_sheet_ok_or_noop_is_confirmed(self):
        rows = self._phase_rows(111, 1) + self._phase_rows(222, 1, start_id=2)

        def _writer(sheet_id, run_id, bucket_rows):
            if sheet_id == 111:
                return self._writer_result(
                    "ok", affected={("900001", "2026-08-30")},
                )
            return self._writer_result("noop")

        result, _ = self._run_phase(rows, _writer)

        self.assertTrue(result["memory_confirmed"])
        self.assertEqual(result["sheets_errored"], 0)
        self.assertEqual(result["sheets_unconfirmed"], 0)
        self.assertIsNone(result["unconfirmed_reason"])
        self.assertEqual(result["affected"], {("900001", "2026-08-30")})

    def test_phase_unavailable_sheet_is_unconfirmed_and_counted_errored(self):
        rows = self._phase_rows(111, 1) + self._phase_rows(222, 1, start_id=2)

        def _writer(sheet_id, run_id, bucket_rows):
            if sheet_id == 111:
                return self._writer_result("unavailable")
            return self._writer_result("ok")

        result, mock_upsert = self._run_phase(rows, _writer)

        self.assertEqual(mock_upsert.call_count, 2)  # never stops early
        self.assertFalse(result["memory_confirmed"])
        self.assertEqual(result["sheets_errored"], 1)
        self.assertEqual(result["sheets_unconfirmed"], 1)
        self.assertIn("111", result["unconfirmed_reason"])
        self.assertIn("unavailable", result["unconfirmed_reason"])

    def test_phase_partial_sheet_is_unconfirmed_but_keeps_partial_set(self):
        rows = self._phase_rows(111, 2)

        result, _ = self._run_phase(
            rows,
            lambda *_a: self._writer_result(
                "partial", affected={("900001", "2026-08-30")},
                rows_errored=1,
            ),
        )

        self.assertFalse(result["memory_confirmed"])
        self.assertEqual(result["sheets_errored"], 1)
        # Observability keeps what WAS confirmed; the caller must not
        # narrow scope on it -- pinned by the PHASE 2a tests below.
        self.assertEqual(result["affected"], {("900001", "2026-08-30")})
        self.assertEqual(result["rows_changed"], 1)

    def test_phase_writer_exception_is_unconfirmed(self):
        rows = self._phase_rows(111, 1)

        def _writer(*_a):
            raise RuntimeError("boom")

        result, _ = self._run_phase(rows, _writer)

        self.assertFalse(result["memory_confirmed"])
        self.assertEqual(result["sheets_errored"], 1)
        self.assertIn("exception", result["unconfirmed_reason"])

    def test_phase_budget_break_leaving_sheets_unwritten_is_unconfirmed(self):
        rows = self._phase_rows(111, 1) + self._phase_rows(222, 1, start_id=2)

        result, mock_upsert = self._run_phase(
            rows,
            lambda *_a: self._writer_result("ok"),
            TIME_BUDGET_MINUTES=165,
            GITHUB_ACTIONS_MODE=True,
            RUN_MEMORY_WRITE_MAX_MINUTES=0,
        )

        self.assertEqual(mock_upsert.call_count, 1)
        self.assertFalse(result["memory_confirmed"])
        self.assertEqual(result["sheets_unwritten"], 1)
        self.assertIn("budget", result["unconfirmed_reason"])

    def test_phase_preflight_skip_is_unconfirmed(self):
        stale_start = (
            datetime.datetime.now() - datetime.timedelta(minutes=200)
        )
        import pipeline.orchestrate as orch

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
                mock.patch.object(orch, "TEST_MODE", False), \
                mock.patch.object(orch, "TIME_BUDGET_MINUTES", 165), \
                mock.patch.object(orch, "GITHUB_ACTIONS_MODE", True), \
                mock.patch.object(orch, "RUN_MEMORY_WRITE_MAX_MINUTES", 10), \
                mock.patch.object(
                    orch, "RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN", 2,
                ), \
                mock.patch.object(
                    orch._mem_writer, "upsert_rows_bulk_result",
                ) as mock_upsert:
            result = orch._run_memory_write_phase(
                self._phase_rows(111, 1), "run-1", stale_start,
            )

        mock_upsert.assert_not_called()
        self.assertFalse(result["memory_confirmed"])
        self.assertIn("budget", result["unconfirmed_reason"])

    def test_phase_flag_off_is_unconfirmed(self):
        import pipeline.orchestrate as orch

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", False), \
                mock.patch.object(
                    orch._mem_writer, "upsert_rows_bulk_result",
                ) as mock_upsert:
            result = orch._run_memory_write_phase(
                self._phase_rows(111, 1), "run-1", datetime.datetime.now(),
            )

        mock_upsert.assert_not_called()
        self.assertFalse(result["memory_confirmed"])

    # ── 3. _run_phase2_incremental: escalate before reading affected ──

    def test_phase2_unconfirmed_empty_affected_falls_back_to_full(self):
        mem_result = {
            "sheets_written": 0, "sheets_errored": 1,
            "rows_sent": 1, "rows_changed": 0, "affected": set(),
            "memory_confirmed": False,
            "unconfirmed_reason": "sheet 111222: unavailable",
        }

        result, mock_map, mock_full = self._phase2(mem_result)

        self.assertFalse(result["ok"])
        self.assertIn(
            "trigger_memory_write_unconfirmed", result["fallback_reason"],
        )
        self.assertIn("sheet 111222: unavailable", result["fallback_reason"])
        mock_map.assert_not_called()
        mock_full.assert_not_called()

    def test_phase2_unconfirmed_partial_affected_never_narrows_scope(self):
        mem_result = {
            "sheets_written": 1, "sheets_errored": 1,
            "rows_sent": 2, "rows_changed": 1,
            "affected": {("90001", "2026-08-30")},
            "memory_confirmed": False,
            "unconfirmed_reason": "sheet 111222: partial (1 row errored)",
        }

        result, mock_map, mock_full = self._phase2(
            mem_result, map_return={111222},
        )

        self.assertFalse(result["ok"])
        self.assertIn(
            "trigger_memory_write_unconfirmed", result["fallback_reason"],
        )
        mock_map.assert_not_called()
        mock_full.assert_not_called()

    def test_phase2_confirmed_empty_affected_is_a_legitimate_no_change_run(self):
        mem_result = {
            "sheets_written": 0, "sheets_errored": 0,
            "rows_sent": 0, "rows_changed": 0, "affected": set(),
            "memory_confirmed": True, "unconfirmed_reason": None,
        }

        result, mock_map, _ = self._phase2(mem_result)

        self.assertTrue(result["ok"])
        self.assertEqual(result["affected"], set())
        mock_map.assert_not_called()

    def test_phase2_legacy_result_without_flag_is_treated_as_unconfirmed(self):
        mem_result = {
            "sheets_written": 0, "sheets_errored": 0,
            "rows_sent": 0, "rows_changed": 0, "affected": set(),
        }

        result, mock_map, _ = self._phase2(mem_result)

        self.assertFalse(result["ok"])
        self.assertIn(
            "trigger_memory_write_unconfirmed", result["fallback_reason"],
        )
        mock_map.assert_not_called()

    # ── 4. main() wiring: shadow gate + run_ledger notes ─────────────

    def test_main_gates_shadow_parity_and_ledger_notes_on_memory_confirmed(self):
        import inspect

        import pipeline.orchestrate as orch

        src = inspect.getsource(orch.main)
        # Both run_ledger_finish call sites persist the flag as a note.
        self.assertEqual(src.count("mem_confirmed=_mem_memory_confirmed"), 2)
        # The shadow comparator is gated on the flag BEFORE it compares:
        # a write failure must report 'skipped', never masquerade as a
        # parity 'fail' (11-05 D-07: never-vacuous, never-false verdicts).
        gate_idx = src.index('"reason": "memory_write_unconfirmed"')
        compare_idx = src.index("_parity.compare_shadow_parity(")
        self.assertLess(gate_idx, compare_idx)


# ── Codex P1 on PR #353: a delta row that LOST its identity must still
# regenerate its prior group ─────────────────────────────────────────────

class LostIdentityRowTests(unittest.TestCase):
    """A row the delta read returns because it was modified, but whose
    ``Work Request #`` or ``Weekly Reference Logged Date`` is now blank,
    used to be dropped by ``map_delta_sheet_rows`` BEFORE the memory
    upsert -- so its prior ``(wr, week_ending)`` never entered the
    affected set and the old group (and its attachment) stayed stale.

    Fix: the mapper reports the dropped row ids; ``_run_phase2_incremental``
    looks up their stored identity in ``row_state``
    (``pipeline_memory.reader.get_row_state_pairs_for_rows``) and unions
    those prior pairs into the affected set. A lookup that cannot
    confirm (``None``) resolves the run to full mode -- the scope can
    only widen (T-11-18).
    """

    def setUp(self):
        _reset_pipeline_memory()
        _pop_env()

    def tearDown(self):
        _reset_pipeline_memory()
        _pop_env()

    # ── mapper ───────────────────────────────────────────────────────

    def test_map_delta_sheet_rows_reports_dropped_row_ids(self):
        from pipeline.fetch import map_delta_sheet_rows

        source = _delta_source(sheet_id=111222)
        lost_date = SimpleNamespace(
            id=1, modified_at=None, cells=[_delta_cell(10, "90001")],
        )
        lost_everything = SimpleNamespace(id=2, modified_at=None, cells=[])
        kept = _delta_row(3, "90003", "2026-08-30")
        sheet = _delta_sheet([lost_date, lost_everything, kept])
        dropped: set = set()

        rows = map_delta_sheet_rows(sheet, source, dropped_row_ids=dropped)

        self.assertEqual([r["__row_id"] for r in rows], [3])
        self.assertEqual(dropped, {1, 2})

    def test_map_delta_sheet_rows_without_collector_is_unchanged(self):
        from pipeline.fetch import map_delta_sheet_rows

        source = _delta_source(sheet_id=111222)
        lost_date = SimpleNamespace(
            id=1, modified_at=None, cells=[_delta_cell(10, "90001")],
        )
        self.assertEqual(
            map_delta_sheet_rows(_delta_sheet([lost_date]), source), [],
        )

    # ── reader ───────────────────────────────────────────────────────

    def test_reader_pairs_empty_row_ids_returns_empty_set_zero_calls(self):
        from pipeline_memory import reader as mem_reader

        with mock.patch.object(mem_reader, "get_client") as mock_client:
            result = mem_reader.get_row_state_pairs_for_rows(111222, set())

        self.assertEqual(result, set())
        mock_client.assert_not_called()

    def test_reader_pairs_client_unavailable_returns_none(self):
        from pipeline_memory import reader as mem_reader

        with mock.patch.object(mem_reader, "get_client", return_value=None):
            result = mem_reader.get_row_state_pairs_for_rows(111222, {1})

        self.assertIsNone(result)

    def test_reader_pairs_transport_failure_returns_none(self):
        from pipeline_memory import reader as mem_reader

        with mock.patch.object(
            mem_reader, "get_client", return_value=mock.Mock(),
        ), mock.patch.object(mem_reader, "with_retry", return_value=None):
            result = mem_reader.get_row_state_pairs_for_rows(111222, {1, 2})

        self.assertIsNone(result)

    def test_reader_pairs_success_returns_stored_pairs(self):
        from pipeline_memory import reader as mem_reader

        payload = mock.Mock(data=[
            {"wr": "90001", "week_ending": "2026-08-23"},
            {"wr": "90001", "week_ending": "2026-08-23"},  # duplicate row
            {"wr": "90002", "week_ending": None},
        ])
        with mock.patch.object(
            mem_reader, "get_client", return_value=mock.Mock(),
        ), mock.patch.object(
            mem_reader, "with_retry", return_value=payload,
        ) as mock_retry:
            result = mem_reader.get_row_state_pairs_for_rows(
                111222, {1, 2, 3},
            )

        self.assertEqual(
            result, {("90001", "2026-08-23"), ("90002", None)},
        )
        self.assertEqual(
            mock_retry.call_args.kwargs.get("op"), "row_state_pairs_for_rows",
        )

    def test_reader_pairs_chunks_large_inputs_and_discards_on_mid_chunk_failure(self):
        from pipeline_memory import reader as mem_reader

        ids = set(range(mem_reader._MAPPING_CHUNK_SIZE + 1))
        calls = {"n": 0}

        def _retry(fn, **_kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return mock.Mock(
                    data=[{"wr": "90001", "week_ending": "2026-08-23"}],
                )
            return None

        with mock.patch.object(
            mem_reader, "get_client", return_value=mock.Mock(),
        ), mock.patch.object(mem_reader, "with_retry", side_effect=_retry):
            result = mem_reader.get_row_state_pairs_for_rows(111222, ids)

        self.assertEqual(calls["n"], 2)
        self.assertIsNone(result)  # partial union is worse than none

    # ── PHASE 2a wiring ──────────────────────────────────────────────

    def _phase2_with_delta(self, sheet, lookup_return, mem_affected):
        import pipeline.orchestrate as orch

        source = _delta_source(sheet_id=111222)
        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": sheet, "version": 9, "calls": 2,
            },
        ), mock.patch.object(
            orch, "_run_memory_write_phase",
            return_value={
                "sheets_written": 1, "sheets_errored": 0,
                "rows_sent": 1, "rows_changed": 1,
                "affected": set(mem_affected), "memory_confirmed": True,
                "unconfirmed_reason": None,
            },
        ), mock.patch.object(
            orch._mem_reader, "get_row_state_pairs_for_rows",
            return_value=lookup_return,
        ) as mock_lookup, mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets",
            return_value={111222},
        ) as mock_map, mock.patch.object(
            orch, "get_all_source_rows", return_value=[],
        ):
            result = orch._run_phase2_incremental(
                client=mock.Mock(),
                source_sheets=[source],
                watermarks={
                    111222: {
                        "last_sheet_version": 8,
                        "last_read_at": "2026-08-26T18:00:00+00:00",
                    },
                },
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )
        return result, mock_lookup, mock_map

    def test_phase2_lost_identity_rows_add_prior_pairs_to_affected(self):
        lost = SimpleNamespace(
            id=7, modified_at=None, cells=[_delta_cell(10, "90007")],
        )
        sheet = _delta_sheet([_delta_row(1, "90001", "2026-08-30"), lost])

        result, mock_lookup, mock_map = self._phase2_with_delta(
            sheet,
            lookup_return={("90007", "2026-08-23")},
            mem_affected={("90001", "2026-08-30")},
        )

        self.assertTrue(result["ok"])
        mock_lookup.assert_called_once_with(111222, {7})
        expected = {("90001", "2026-08-30"), ("90007", "2026-08-23")}
        self.assertEqual(result["affected"], expected)
        mock_map.assert_called_once_with(expected)
        self.assertEqual(result["delta_rows_identity_lost"], 1)

    def test_phase2_lost_identity_lookup_failure_falls_back_to_full(self):
        lost = SimpleNamespace(
            id=7, modified_at=None, cells=[_delta_cell(10, "90007")],
        )
        sheet = _delta_sheet([_delta_row(1, "90001", "2026-08-30"), lost])

        result, _, mock_map = self._phase2_with_delta(
            sheet, lookup_return=None,
            mem_affected={("90001", "2026-08-30")},
        )

        self.assertFalse(result["ok"])
        self.assertIn(
            "trigger_prior_identity_lookup_failed", result["fallback_reason"],
        )
        mock_map.assert_not_called()

    def test_phase2_no_lost_identity_rows_performs_zero_lookups(self):
        sheet = _delta_sheet([_delta_row(1, "90001", "2026-08-30")])

        result, mock_lookup, _ = self._phase2_with_delta(
            sheet, lookup_return=set(),
            mem_affected={("90001", "2026-08-30")},
        )

        self.assertTrue(result["ok"])
        mock_lookup.assert_not_called()
        self.assertEqual(result["delta_rows_identity_lost"], 0)

    def test_fetch_exposes_failed_sheet_ids_accessor(self):
        import pipeline.fetch as fetch

        result = fetch.get_last_full_read_failed_sheet_ids()

        self.assertIsInstance(result, set)
        result.add("sentinel")  # defensive copy -- must not leak back
        self.assertNotIn(
            "sentinel", fetch.get_last_full_read_failed_sheet_ids(),
        )


if __name__ == "__main__":
    unittest.main()
