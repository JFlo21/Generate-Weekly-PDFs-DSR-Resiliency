"""Phase 14 Plan 14 (O-14-E, second half): a frequent run adopts the
mapping it just fully validated, so the marker lands without the deep run.

Evidence that forced this (2026-09-09): 0 of 121 ``sheet_registry``
rows carried any Helper #2 key -- the stored mappings came from the last
deep run on pre-Helper-#2 code -- so stamping the marker by SQL would have
admitted every sheet from cache WITHOUT Helper #2 columns. The safe route
is to write the freshly validated mapping (and, via 14-13's marker helper,
the marker) for every sheet a frequent run fully validated, with the
deep run's drift log firing for each adopted change.

Evidence label: FIXTURE PASS only.
"""

from __future__ import annotations

import inspect
import os
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class ComputeRegistryMappingSheetsAdoptionTests(unittest.TestCase):
    """``_compute_registry_mapping_sheets`` gains ``fully_validated_sids``:
    on a frequent run the written set = new sheets ∪ fully-validated
    registered sheets. Default keeps the Phase 11 new-sheets-only shape."""

    def test_frequent_run_includes_fully_validated_registered_sheet(self):
        from pipeline.orchestrate import _compute_registry_mapping_sheets

        result = _compute_registry_mapping_sheets(
            False, [{"id": 111}, {"id": 222}], {111: {}, 222: {}},
            fully_validated_sids={111},
        )
        self.assertEqual(result, {111})

    def test_frequent_run_excludes_skip_admitted_registered_sheet(self):
        from pipeline.orchestrate import _compute_registry_mapping_sheets

        result = _compute_registry_mapping_sheets(
            False, [{"id": 111}], {111: {}}, fully_validated_sids=set(),
        )
        self.assertEqual(result, set())

    def test_frequent_run_new_sheet_written_even_if_not_listed(self):
        from pipeline.orchestrate import _compute_registry_mapping_sheets

        result = _compute_registry_mapping_sheets(
            False, [{"id": 111}, {"id": 333}], {111: {}},
            fully_validated_sids=set(),
        )
        self.assertEqual(result, {333})

    def test_default_keeps_new_sheets_only_behaviour(self):
        from pipeline.orchestrate import _compute_registry_mapping_sheets

        result = _compute_registry_mapping_sheets(
            False, [{"id": 111}, {"id": 222}], {111: {}},
        )
        self.assertEqual(result, {222})

    def test_deep_run_still_returns_none(self):
        from pipeline.orchestrate import _compute_registry_mapping_sheets

        result = _compute_registry_mapping_sheets(
            True, [{"id": 111}], {}, fully_validated_sids={111},
        )
        self.assertIsNone(result)


class DriftLogLabelTests(unittest.TestCase):
    """``_log_column_mapping_drift`` takes a ``label`` so the frequent-run
    adoption is visibly distinct from the deep-run refresh; the default
    keeps the deep-run text byte-identical."""

    def test_label_prefixes_warning(self):
        from pipeline.orchestrate import _log_column_mapping_drift

        sheets = [{"id": 111, "column_mapping": {"Foreman": 1, "Helper #2 Dept #": 9}}]
        watermarks = {111: {"column_mapping": {"Foreman": 1}}}
        with self.assertLogs(level="WARNING") as captured:
            changed = _log_column_mapping_drift(
                sheets, watermarks, label="Frequent-run full-validation",
            )
        self.assertEqual(changed, [111])
        self.assertTrue(
            any(
                "Frequent-run full-validation column_mapping refresh" in line
                for line in captured.output
            ),
            captured.output,
        )

    def test_default_label_is_deep_run(self):
        from pipeline.orchestrate import _log_column_mapping_drift

        sheets = [{"id": 111, "column_mapping": {"Foreman": 1}}]
        with self.assertLogs(level="WARNING") as captured:
            _log_column_mapping_drift(sheets, {})
        self.assertTrue(
            any("Deep-run column_mapping refresh" in line for line in captured.output),
            captured.output,
        )


class OrchestrateFrequentRunWiringTests(unittest.TestCase):
    """Source pin on ``orch.main`` (repo convention)."""

    def test_main_passes_fully_validated_sids_and_logs_frequent_drift(self):
        from pipeline import orchestrate as orch

        src = inspect.getsource(orch.main)
        self.assertIn("fully_validated_sids=_registry_fully_validated_sids", src)
        self.assertEqual(src.count("_log_column_mapping_drift("), 2)
        self.assertIn('label="Frequent-run full-validation"', src)


class AdoptedMappingReachesWriterTests(unittest.TestCase):
    """End to end through the real writer: on a frequent run a registered
    sheet that was fully validated gets its FRESH mapping written plus the
    marker; a skip-admitted registered sheet echoes the stored mapping
    with no marker."""

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
    def _fake_client(upsert_capture: list[Any]) -> mock.Mock:
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

    def test_fresh_mapping_and_marker_for_fully_validated_registered_sheet(self):
        from pipeline.discovery import MAPPING_SCHEMA_MARKER
        from pipeline.orchestrate import (
            _compute_registry_mapping_sheets,
            _compute_registry_marker_sheets,
        )
        from pipeline_memory import writer as mem_writer

        stored_old = {"Foreman": 1}
        fresh_111 = {"Foreman": 1, "Helper #2 Dept #": 9}
        sheets = [
            {"id": 111, "name": "Validated", "column_mapping": fresh_111},
            {"id": 222, "name": "Cached", "column_mapping": dict(stored_old)},
        ]
        watermarks = {
            111: {"column_mapping": dict(stored_old)},
            222: {"column_mapping": dict(stored_old)},
        }
        skip_sids = {222}
        fully_validated = {s["id"] for s in sheets if s["id"] not in skip_sids}
        mapping_sheets = _compute_registry_mapping_sheets(
            False, sheets, watermarks, fully_validated_sids=fully_validated,
        )
        marker_sheets = _compute_registry_marker_sheets(
            sheets, skip_sids, mapping_sheets,
        )

        upsert_capture: list[Any] = []
        client = self._fake_client(upsert_capture)
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ):
            mem_writer.upsert_sheet_registry(
                sheets, "run-1", lambda sid: "primary", {},
                column_mapping_sheets=mapping_sheets,
                watermarks=watermarks,
                mapping_schema_by_sheet=marker_sheets,
            )

        rows: list[dict[str, Any]] = []
        for call in upsert_capture:
            rows.extend(call.args[0])
        row_111 = next(r for r in rows if r["sheet_id"] == 111)
        row_222 = next(r for r in rows if r["sheet_id"] == 222)
        self.assertEqual(row_111["column_mapping"], fresh_111)
        self.assertEqual(row_111["mapping_schema"], MAPPING_SCHEMA_MARKER)
        self.assertEqual(row_222["column_mapping"], stored_old)
        self.assertNotIn("mapping_schema", row_222)


if __name__ == "__main__":
    unittest.main()
