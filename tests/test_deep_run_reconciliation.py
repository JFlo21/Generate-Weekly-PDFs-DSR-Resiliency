"""Tests for Phase 11 Plan 06 (INC-03): the weekly deep run's
deletion-reconciliation, ``sheet_registry.column_mapping`` refresh, and
formula-only reconciliation.

Class layout, in commit order (RED then GREEN per task -- 11-06-PLAN.md):
  - RowStateRowIdsReadTests / MarkRowsDeletedTests -- Task 1's new
    pipeline_memory reader/writer surface.
  - DeepRunDeletionReconciliationTests -- Task 1's standalone
    orchestrate.py helpers (``_reconcile_deep_run_deletions``,
    ``_repair_group_state_for_affected_pairs``) plus the main() wiring
    structural checks.
  - ColumnMappingRefreshTests -- Task 2 (``upsert_sheet_registry``'s new
    ``column_mapping_sheets`` kwarg, ``_compute_registry_mapping_sheets``,
    ``_log_column_mapping_drift``).
  - FormulaOnlyReconciliationTests -- Task 3 (the formula-only fixture
    and the ordinary content-hash reconciliation path).

Self-contained like ``tests/test_pipeline_memory_shadow.py`` /
``tests/test_incremental_read.py`` -- there is no ``tests/conftest.py``
in this repo to share fixtures from.
"""

from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures" / "incremental"


def _reset_pipeline_memory():
    from pipeline_memory import client as mem_client
    mem_client.reset_cache_for_tests()


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


# ── Task 1: pipeline_memory.reader.get_row_state_row_ids ────────────────

class RowStateRowIdsReadTests(unittest.TestCase):
    def setUp(self):
        _reset_pipeline_memory()

    def tearDown(self):
        _reset_pipeline_memory()

    def test_returns_set_of_row_ids(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.eq.return_value.is_.return_value
            .range.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[
            {"row_id": 1}, {"row_id": 2}, {"row_id": 3},
        ])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_row_state_row_ids(111)

        self.assertEqual(result, {1, 2, 3})

    def test_none_sheet_id_returns_empty_set_zero_calls(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_row_state_row_ids(None)

        self.assertEqual(result, set())
        client.schema.assert_not_called()

    def test_client_unavailable_returns_empty_set(self):
        from pipeline_memory import reader as mem_reader

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=None
        ):
            result = mem_reader.get_row_state_row_ids(111)

        self.assertEqual(result, set())

    def test_supabase_failure_returns_empty_set(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.eq.return_value.is_.return_value
            .range.return_value
        )
        query.execute.side_effect = Exception("transport boom")

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_row_state_row_ids(111)

        self.assertEqual(result, set())

    def test_none_response_payload_returns_empty_set(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.eq.return_value.is_.return_value
            .range.return_value
        )
        query.execute.return_value = SimpleNamespace(data=None)

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_row_state_row_ids(111)

        self.assertEqual(result, set())

    def test_paginates_across_multiple_pages(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        page_size = mem_reader._ROW_STATE_PAGE_SIZE
        call_count = {"n": 0}

        def _execute():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return SimpleNamespace(
                    data=[{"row_id": i} for i in range(page_size)]
                )
            return SimpleNamespace(data=[{"row_id": page_size}])

        (
            client.schema.return_value.table.return_value
            .select.return_value.eq.return_value.is_.return_value
            .range.return_value.execute.side_effect
        ) = _execute

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            result = mem_reader.get_row_state_row_ids(111)

        self.assertEqual(call_count["n"], 2)
        self.assertEqual(len(result), page_size + 1)

    def test_filters_out_already_deleted_rows_via_is_null(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.eq.return_value.is_.return_value
            .range.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[])

        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client
        ):
            mem_reader.get_row_state_row_ids(111)

        is_call = (
            client.schema.return_value.table.return_value
            .select.return_value.eq.return_value.is_
        )
        self.assertEqual(is_call.call_args[0][0], "deleted_at")


# ── Task 1: pipeline_memory.writer.mark_rows_deleted ─────────────────────

class MarkRowsDeletedTests(unittest.TestCase):
    def setUp(self):
        _reset_pipeline_memory()

    def tearDown(self):
        _reset_pipeline_memory()

    def test_empty_row_ids_returns_zero_count_no_calls(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ):
            result = mem_writer.mark_rows_deleted(111, set(), "run-1")

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["affected_pairs"], set())
        client.schema.assert_not_called()

    def test_client_unavailable_returns_zero_count(self):
        from pipeline_memory import writer as mem_writer

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=None
        ):
            result = mem_writer.mark_rows_deleted(111, {1, 2}, "run-1")

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["affected_pairs"], set())

    def test_write_disabled_returns_zero_count(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=False,
        ):
            result = mem_writer.mark_rows_deleted(111, {1, 2}, "run-1")

        self.assertEqual(result["count"], 0)
        client.schema.assert_not_called()

    def test_marks_rows_and_returns_affected_pairs(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .update.return_value.eq.return_value.in_.return_value
            .is_.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[
            {"row_id": 1, "wr": "90001", "week_ending": "2026-08-30"},
        ])

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            result = mem_writer.mark_rows_deleted(111, {1}, "run-1")

        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["affected_pairs"], {("90001", "2026-08-30")}
        )
        update_call = client.schema.return_value.table.return_value.update
        self.assertIn("deleted_at", update_call.call_args[0][0])

    def test_failure_returns_zero_count_empty_pairs(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .update.return_value.eq.return_value.in_.return_value
            .is_.return_value
        )
        query.execute.side_effect = Exception("transport boom")

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            result = mem_writer.mark_rows_deleted(111, {1, 2}, "run-1")

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["affected_pairs"], set())

    def test_chunks_large_row_id_set(self):
        from pipeline_memory import writer as mem_writer

        row_ids = set(range(mem_writer._CHUNK_ROWS + 5))
        client = mock.Mock()
        call_count = {"n": 0}

        def _execute():
            call_count["n"] += 1
            return SimpleNamespace(data=[])

        (
            client.schema.return_value.table.return_value
            .update.return_value.eq.return_value.in_.return_value
            .is_.return_value.execute.side_effect
        ) = _execute

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            mem_writer.mark_rows_deleted(111, row_ids, "run-1")

        self.assertEqual(call_count["n"], 2)

    def test_never_rewrites_already_deleted_row_via_is_null_filter(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .update.return_value.eq.return_value.in_.return_value
            .is_.return_value
        )
        query.execute.return_value = SimpleNamespace(data=[])

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            mem_writer.mark_rows_deleted(111, {1}, "run-1")

        is_call = (
            client.schema.return_value.table.return_value
            .update.return_value.eq.return_value.in_.return_value.is_
        )
        self.assertEqual(is_call.call_args[0], ("deleted_at", "null"))


# ── Task 1: orchestrate.py standalone reconciliation helpers ────────────

class DeepRunDeletionReconciliationTests(unittest.TestCase):
    def test_zero_row_full_read_marks_zero_deleted_and_skips(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        mark_fn = mock.Mock()
        result = _reconcile_deep_run_deletions(
            [{"id": 111}],
            {111: set()},
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value={1, 2}),
            mark_rows_deleted_fn=mark_fn,
        )

        self.assertEqual(result["rows_marked_deleted"], 0)
        self.assertEqual(result["sheets_skipped_zero_row"], 1)
        mark_fn.assert_not_called()

    def test_sheet_absent_from_live_map_is_treated_as_zero_row(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        mark_fn = mock.Mock()
        result = _reconcile_deep_run_deletions(
            [{"id": 111}],
            {},  # sheet never appeared with any row this run
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value={1}),
            mark_rows_deleted_fn=mark_fn,
        )

        self.assertEqual(result["sheets_skipped_zero_row"], 1)
        mark_fn.assert_not_called()

    def test_deletion_diff_marks_only_rows_absent_from_live_read(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        mark_fn = mock.Mock(return_value={
            "count": 1, "affected_pairs": {("90001", "2026-08-30")},
        })
        result = _reconcile_deep_run_deletions(
            [{"id": 111}],
            {111: {2, 3}},
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value={1, 2, 3}),
            mark_rows_deleted_fn=mark_fn,
        )

        mark_fn.assert_called_once()
        args = mark_fn.call_args[0]
        self.assertEqual(args[0], 111)
        self.assertEqual(set(args[1]), {1})
        self.assertEqual(result["rows_marked_deleted"], 1)
        self.assertEqual(
            result["affected_pairs"], {("90001", "2026-08-30")}
        )

    def test_no_stored_rows_is_a_noop_never_calls_mark(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        mark_fn = mock.Mock()
        result = _reconcile_deep_run_deletions(
            [{"id": 111}],
            {111: {1, 2}},
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value=set()),
            mark_rows_deleted_fn=mark_fn,
        )

        mark_fn.assert_not_called()
        self.assertEqual(result["rows_marked_deleted"], 0)

    def test_no_diff_is_a_noop_never_calls_mark(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        mark_fn = mock.Mock()
        _reconcile_deep_run_deletions(
            [{"id": 111}],
            {111: {1, 2}},
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value={1, 2}),
            mark_rows_deleted_fn=mark_fn,
        )

        mark_fn.assert_not_called()

    def test_multiple_sheets_aggregate_across_calls(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        def _stored(sheet_id):
            return {111: {1, 2}, 222: {5, 6}}[sheet_id]

        def _mark(sheet_id, ids, run_id):
            return {
                "count": len(ids),
                "affected_pairs": {(f"WR{sheet_id}", "2026-08-30")},
            }

        result = _reconcile_deep_run_deletions(
            [{"id": 111}, {"id": 222}],
            {111: {2}, 222: {5}},
            "run-1",
            get_row_state_row_ids_fn=_stored,
            mark_rows_deleted_fn=_mark,
        )

        self.assertEqual(result["rows_marked_deleted"], 2)
        self.assertEqual(
            result["affected_pairs"],
            {("WR111", "2026-08-30"), ("WR222", "2026-08-30")},
        )

    def test_never_raises_on_unexpected_mark_result_shape(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        result = _reconcile_deep_run_deletions(
            [{"id": 111}],
            {111: {2}},
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value={1, 2}),
            mark_rows_deleted_fn=mock.Mock(return_value=None),
        )

        self.assertEqual(result["rows_marked_deleted"], 0)

    def test_defaults_to_real_reader_writer_functions_when_unset(self):
        import pipeline.orchestrate as orch

        with mock.patch.object(
            orch._mem_reader, "get_row_state_row_ids",
            return_value=set(),
        ) as mocked_reader:
            orch._reconcile_deep_run_deletions(
                [{"id": 111}], {111: {1}}, "run-1",
            )
        mocked_reader.assert_called_once_with(111)

    def test_fixture_deleted_row_drives_expected_diff(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        cassette = _load_fixture("deleted_row.json")
        sheet_id = cassette["sheet_id"]
        stored = set(cassette["stored_row_state_row_ids"])
        live = set(cassette["live_full_read_row_ids"])
        expected_deleted = set(cassette["expected_deleted_row_ids"])
        pair = (
            cassette["affected_pair"]["wr"],
            cassette["affected_pair"]["week_ending"],
        )

        captured = {}

        def _mark(sheet_id_arg, ids, run_id):
            captured["ids"] = set(ids)
            return {"count": len(ids), "affected_pairs": {pair}}

        zero = cassette["zero_row_sheet_scenario"]
        result = _reconcile_deep_run_deletions(
            [{"id": sheet_id}, {"id": zero["sheet_id"]}],
            {
                sheet_id: live,
                zero["sheet_id"]: set(zero["live_full_read_row_ids"]),
            },
            "run-1",
            get_row_state_row_ids_fn=lambda sid: (
                stored if sid == sheet_id
                else set(zero["stored_row_state_row_ids"])
            ),
            mark_rows_deleted_fn=_mark,
        )

        self.assertEqual(captured["ids"], expected_deleted)
        self.assertEqual(result["sheets_skipped_zero_row"], 1)
        self.assertEqual(result["affected_pairs"], {pair})


class GroupStateRepairTests(unittest.TestCase):
    def test_empty_affected_pairs_returns_empty_list(self):
        from pipeline.orchestrate import (
            _repair_group_state_for_affected_pairs,
        )

        result = _repair_group_state_for_affected_pairs(
            set(), [{"wr_num": "90001", "week_iso": "2026-08-30"}],
        )
        self.assertEqual(result, [])

    def test_filters_to_matching_pairs_only(self):
        from pipeline.orchestrate import (
            _repair_group_state_for_affected_pairs,
        )

        deferred = [
            {
                "wr_num": "90001", "week_iso": "2026-08-30",
                "data_hash": "abc123",
            },
            {
                "wr_num": "99999", "week_iso": "2026-08-30",
                "data_hash": "zzz999",
            },
        ]
        result = _repair_group_state_for_affected_pairs(
            {("90001", "2026-08-30")}, deferred,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["data_hash"], "abc123")

    def test_repaired_records_never_carry_attachment_keys(self):
        """Deferred-group-state entries never carry attachment_id /
        attachment_name (see the _deferred_group_state.append call site
        in orchestrate.py's group loop) -- proving by construction that
        upsert_group_state's payload omits both keys for these records,
        so PostgREST's upsert leaves whatever attachment id is already
        stored untouched (the COALESCE-by-omission contract IN-01
        already proved live)."""
        from pipeline.orchestrate import (
            _repair_group_state_for_affected_pairs,
        )

        deferred = [
            {
                "wr_num": "90001", "week_iso": "2026-08-30",
                "variant": "primary", "identifier": "",
                "data_hash": "abc123", "row_count": 4,
            },
        ]
        result = _repair_group_state_for_affected_pairs(
            {("90001", "2026-08-30")}, deferred,
        )
        self.assertNotIn("attachment_id", result[0])
        self.assertNotIn("attachment_name", result[0])

    def test_orphaned_pair_not_present_in_deferred_state_yields_nothing(self):
        """A (wr, week_ending) pair whose LAST remaining row was deleted
        this run produces no entry in deferred_group_state at all (the
        group no longer exists for group_source_rows to build) -- a
        documented, out-of-scope limitation, not a crash."""
        from pipeline.orchestrate import (
            _repair_group_state_for_affected_pairs,
        )

        result = _repair_group_state_for_affected_pairs(
            {("90001", "2026-08-30")},
            [{"wr_num": "11111", "week_iso": "2026-08-30"}],
        )
        self.assertEqual(result, [])


class MainWiringStructuralTests(unittest.TestCase):
    """Source-inspection regression tests for the deep-run reconciliation
    call sites too deep inside main() to invoke directly -- extends the
    established inspect.getsource convention (11-02/11-04's
    RunLedgerSheetsChangedCallSiteTests / AttachmentSideChannelTests)."""

    def test_main_gates_reconciliation_on_weekly_comprehensive_execution_type(
        self,
    ):
        import pipeline.orchestrate as orch

        source = inspect.getsource(orch.main)
        self.assertIn("_reconcile_deep_run_deletions(", source)
        self.assertIn("weekly_comprehensive", source)
        # The reconciliation call site must sit behind the SAME
        # RUN_MEMORY_WRITE_ENABLED / TEST_MODE double gate every other
        # pipeline_memory hook uses.
        call_index = source.index("_reconcile_deep_run_deletions(")
        preceding = source[max(0, call_index - 800):call_index]
        self.assertIn("RUN_MEMORY_WRITE_ENABLED", preceding)
        self.assertIn("TEST_MODE", preceding)

    def test_main_never_marks_deleted_on_non_deep_run_by_construction(
        self,
    ):
        """production_frequent (or any non-weekly_comprehensive
        EXECUTION_TYPE) must never reach the reconciliation call --
        proven by the same gating condition governing both the mapping
        refresh AND the deletion phase (_is_deep_run)."""
        import pipeline.orchestrate as orch

        source = inspect.getsource(orch.main)
        self.assertIn("_is_deep_run", source)


# ── Task 2: sheet_registry.column_mapping refresh ────────────────────────

class ColumnMappingRefreshTests(unittest.TestCase):
    def setUp(self):
        _reset_pipeline_memory()

    def tearDown(self):
        _reset_pipeline_memory()

    def test_upsert_sheet_registry_includes_mapping_when_sheets_none(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        client.schema.return_value.table.return_value.upsert.return_value.execute.return_value = (
            SimpleNamespace(data=[{"sheet_id": 111}])
        )

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            mem_writer.upsert_sheet_registry(
                [{"id": 111, "name": "S1", "column_mapping": {"A": 1}}],
                "run-1", lambda sid: "primary", {111: 5},
                column_mapping_sheets=None,
            )

        payload = (
            client.schema.return_value.table.return_value.upsert
            .call_args[0][0]
        )
        self.assertIn("column_mapping", payload[0])

    def test_upsert_sheet_registry_echoes_stored_mapping_for_sheets_not_in_set(
        self,
    ):
        """PR #363: ``column_mapping`` is NOT NULL and PostgreSQL checks
        the INSERT candidate before ``ON CONFLICT``, so a registered
        sheet can never omit it -- it echoes the STORED mapping from
        the watermarks (never the freshly discovered one)."""
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        client.schema.return_value.table.return_value.upsert.return_value.execute.return_value = (
            SimpleNamespace(data=[{"sheet_id": 111}])
        )

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            mem_writer.upsert_sheet_registry(
                [{"id": 111, "name": "S1", "column_mapping": {"A": 1}}],
                "run-1", lambda sid: "primary", {111: 5},
                column_mapping_sheets=set(),
                watermarks={111: {"column_mapping": {"A": 999}}},
            )

        payload = (
            client.schema.return_value.table.return_value.upsert
            .call_args[0][0]
        )
        self.assertEqual(payload[0]["column_mapping"], {"A": 999})

    def test_upsert_sheet_registry_includes_mapping_for_sheets_in_set(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        client.schema.return_value.table.return_value.upsert.return_value.execute.return_value = (
            SimpleNamespace(data=[{"sheet_id": 111}])
        )

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            mem_writer.upsert_sheet_registry(
                [{"id": 111, "name": "S1", "column_mapping": {"A": 1}}],
                "run-1", lambda sid: "primary", {111: 5},
                column_mapping_sheets={111},
            )

        payload = (
            client.schema.return_value.table.return_value.upsert
            .call_args[0][0]
        )
        self.assertIn("column_mapping", payload[0])

    def test_compute_registry_mapping_sheets_deep_run_returns_none(self):
        from pipeline.orchestrate import _compute_registry_mapping_sheets

        result = _compute_registry_mapping_sheets(
            True, [{"id": 111}, {"id": 222}], {111: {}},
        )
        self.assertIsNone(result)

    def test_compute_registry_mapping_sheets_frequent_run_new_sheets_only(
        self,
    ):
        from pipeline.orchestrate import _compute_registry_mapping_sheets

        result = _compute_registry_mapping_sheets(
            False, [{"id": 111}, {"id": 222}], {111: {}},
        )
        self.assertEqual(result, {222})

    def test_production_frequent_run_issues_zero_refresh_writes_when_all_registered(
        self,
    ):
        """A frequent run where every sheet already has a registry row
        computes an EMPTY mapping-refresh set -- upsert_sheet_registry
        then writes ZERO discovered mappings: every row echoes the
        stored one (the column is NOT NULL, so it is never omitted)."""
        from pipeline.orchestrate import _compute_registry_mapping_sheets
        from pipeline_memory import writer as mem_writer

        watermarks = {111: {"column_mapping": {"A": 999}}}
        mapping_sheets = _compute_registry_mapping_sheets(
            False, [{"id": 111}], watermarks,
        )
        self.assertEqual(mapping_sheets, set())

        client = mock.Mock()
        client.schema.return_value.table.return_value.upsert.return_value.execute.return_value = (
            SimpleNamespace(data=[{"sheet_id": 111}])
        )
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=True,
        ):
            mem_writer.upsert_sheet_registry(
                [{"id": 111, "name": "S1", "column_mapping": {"A": 1}}],
                "run-1", lambda sid: "primary", {111: 5},
                column_mapping_sheets=mapping_sheets,
                watermarks=watermarks,
            )
        payload = (
            client.schema.return_value.table.return_value.upsert
            .call_args[0][0]
        )
        self.assertEqual(payload[0]["column_mapping"], {"A": 999})

    def test_log_column_mapping_drift_detects_change_and_uses_shared_normaliser(
        self,
    ):
        from pipeline.orchestrate import _log_column_mapping_drift

        # Stored value uses string-typed ids (a JSONB round-trip
        # artifact); fresh value uses native ints. The SHARED
        # _normalize_column_mapping helper must coerce both before
        # comparing -- a genuine drift (extra key) must still surface.
        sheets = [
            {"id": 111, "column_mapping": {"Work Request #": 1, "Foreman": 2}},
        ]
        watermarks = {
            111: {"column_mapping": {"Work Request #": "1"}},
        }
        changed = _log_column_mapping_drift(sheets, watermarks)
        self.assertEqual(changed, [111])

    def test_log_column_mapping_drift_no_change_returns_empty_list(self):
        from pipeline.orchestrate import _log_column_mapping_drift

        sheets = [
            {"id": 111, "column_mapping": {"Work Request #": 1}},
        ]
        watermarks = {
            111: {"column_mapping": {"Work Request #": "1"}},
        }
        changed = _log_column_mapping_drift(sheets, watermarks)
        self.assertEqual(changed, [])

    def test_log_column_mapping_drift_missing_watermark_treated_as_drift(
        self,
    ):
        from pipeline.orchestrate import _log_column_mapping_drift

        sheets = [{"id": 111, "column_mapping": {"A": 1}}]
        changed = _log_column_mapping_drift(sheets, {})
        self.assertEqual(changed, [111])

    def test_main_gates_mapping_refresh_on_weekly_comprehensive(self):
        import pipeline.orchestrate as orch

        source = inspect.getsource(orch.main)
        self.assertIn("_compute_registry_mapping_sheets(", source)
        self.assertIn("weekly_comprehensive", source)


# ── Task 3: formula-only reconciliation ──────────────────────────────────

class FormulaOnlyReconciliationTests(unittest.TestCase):
    def test_fixture_loads_and_names_mem04_provenance(self):
        cassette = _load_fixture("formula_only_change.json")
        self.assertIn("mem04", cassette["provenance"].lower())
        self.assertIn("hash_field_change", cassette)
        self.assertIn("non_hash_field_change", cassette)

    def test_hash_field_formula_change_produces_different_content_hash(
        self,
    ):
        from pipeline_memory.writer import (
            _row_to_payload, compute_content_hash,
        )

        cassette = _load_fixture("formula_only_change.json")["hash_field_change"]
        before_payload = _row_to_payload(
            cassette["before"], "run-1", "2026-08-30", "2026-08-25",
        )
        after_payload = _row_to_payload(
            cassette["after"], "run-1", "2026-08-30", "2026-08-25",
        )

        self.assertNotEqual(
            compute_content_hash(before_payload),
            compute_content_hash(after_payload),
        )

    def test_non_hash_field_formula_change_yields_same_hash_no_repair(
        self,
    ):
        """A formula-only change to a field OUTSIDE HASH_FIELDS (here,
        'Customer Name' -- never read by _row_to_payload at all) must
        produce the IDENTICAL content_hash and therefore drive NO
        group_state repair -- this is correct, not a miss."""
        from pipeline_memory.writer import (
            _row_to_payload, compute_content_hash,
        )

        cassette = _load_fixture(
            "formula_only_change.json"
        )["non_hash_field_change"]
        before_payload = _row_to_payload(
            cassette["before"], "run-1", "2026-08-30", "2026-08-25",
        )
        after_payload = _row_to_payload(
            cassette["after"], "run-1", "2026-08-30", "2026-08-25",
        )

        self.assertEqual(
            compute_content_hash(before_payload),
            compute_content_hash(after_payload),
        )

    def test_hash_field_change_pair_is_pickable_by_group_state_repair(self):
        """Wires Task 1's _repair_group_state_for_affected_pairs into
        Task 3's formula-only scenario: once a hash-affecting change
        drives a group_state entry into _deferred_group_state, the
        repair filter correctly selects it by (wr, week_ending)."""
        from pipeline.orchestrate import (
            _repair_group_state_for_affected_pairs,
        )
        from pipeline_memory.writer import (
            _row_to_payload, compute_content_hash,
        )

        cassette = _load_fixture("formula_only_change.json")["hash_field_change"]
        after_payload = _row_to_payload(
            cassette["after"], "run-1", "2026-08-30", "2026-08-25",
        )
        new_hash = compute_content_hash(after_payload)
        deferred = [{
            "wr_num": "90001", "week_iso": "2026-08-30",
            "data_hash": new_hash,
        }]

        result = _repair_group_state_for_affected_pairs(
            {("90001", "2026-08-30")}, deferred,
        )
        self.assertEqual(result[0]["data_hash"], new_hash)

    def test_checklist_names_weekly_comprehensive_deep_run_verification(
        self,
    ):
        checklist = (
            _REPO_ROOT / "docs" / "run-memory-write-flip-checklist.md"
        ).read_text(encoding="utf-8")
        self.assertIn("weekly_comprehensive", checklist)
        self.assertIn("Deep-run live verification", checklist)


if __name__ == "__main__":
    unittest.main()


# ── Greptile P1 on PR #353: partial reads must never trigger deletions ───

class PartialReadGuardTests(unittest.TestCase):
    """``_reconcile_deep_run_deletions`` must skip any sheet whose full
    read did not complete cleanly, EVEN IF that sheet contributed a
    non-empty (partial) live row-id set. ``pipeline.fetch.
    get_all_source_rows`` returns whatever rows were processed before a
    mid-sheet exception, so a non-empty live set is not proof of a
    complete read; the caller passes ``pipeline.fetch.
    get_last_full_read_failed_sheet_ids()`` as ``failed_sheet_ids``.
    """

    def test_failed_read_sheet_is_skipped_even_with_nonempty_live_rows(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        mark_fn = mock.Mock()
        result = _reconcile_deep_run_deletions(
            [{"id": 111}],
            {111: {1, 2}},  # partial: rows 1-2 read, then the sheet raised
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value={1, 2, 3}),
            mark_rows_deleted_fn=mark_fn,
            failed_sheet_ids={111},
        )

        mark_fn.assert_not_called()
        self.assertEqual(result["rows_marked_deleted"], 0)
        self.assertEqual(result["sheets_skipped_failed_read"], 1)
        self.assertEqual(result["sheets_checked"], 0)

    def test_failed_read_sheet_does_not_block_sibling_sheets(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        stored = {111: {1, 2, 3}, 222: {5, 6}}
        mark_fn = mock.Mock(return_value={"count": 1, "affected_pairs": set()})
        result = _reconcile_deep_run_deletions(
            [{"id": 111}, {"id": 222}],
            {111: {1, 2}, 222: {5}},
            "run-1",
            get_row_state_row_ids_fn=lambda sid: stored[sid],
            mark_rows_deleted_fn=mark_fn,
            failed_sheet_ids={111},
        )

        mark_fn.assert_called_once_with(222, {6}, "run-1")
        self.assertEqual(result["sheets_skipped_failed_read"], 1)
        self.assertEqual(result["sheets_checked"], 1)

    def test_no_failed_sheets_is_the_unchanged_path(self):
        from pipeline.orchestrate import _reconcile_deep_run_deletions

        mark_fn = mock.Mock(return_value={"count": 1, "affected_pairs": set()})
        result = _reconcile_deep_run_deletions(
            [{"id": 111}],
            {111: {1, 2}},
            "run-1",
            get_row_state_row_ids_fn=mock.Mock(return_value={1, 2, 3}),
            mark_rows_deleted_fn=mark_fn,
        )

        mark_fn.assert_called_once_with(111, {3}, "run-1")
        self.assertEqual(result["sheets_skipped_failed_read"], 0)

    def test_main_passes_fetch_failed_sheet_ids_and_gates_on_full_mode(self):
        import pipeline.orchestrate as orch

        source = inspect.getsource(orch.main)
        call_index = source.index("_reconcile_deep_run_deletions(")
        call_text = source[call_index:call_index + 600]
        self.assertIn(
            "failed_sheet_ids=_fetch.get_last_full_read_failed_sheet_ids()",
            call_text,
        )
        # The live set is only a full-read set in full mode; the
        # reconciliation must never run against PHASE 2b's narrowed rows.
        preceding = source[max(0, call_index - 1200):call_index]
        self.assertIn("_resolved_mode == 'full'", preceding)
