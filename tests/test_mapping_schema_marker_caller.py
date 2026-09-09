"""Phase 14 Plan 13 (O-14-E): the mapping-schema marker reaches production.

Plan 14-07 gave ``pipeline_memory.writer.upsert_sheet_registry`` an opt-in
``mapping_schema_by_sheet`` kwarg and pinned the WRITER; the first enabled
scheduled run (``34356004448``, 2026-09-09) showed no CALLER ever passes it,
so ``sheet_registry.mapping_schema`` stayed NULL on all 121 rows and the
D-11.1-01 registry skip was defeated on every run.

These tests pin the caller side:

- ``pipeline.discovery`` exposes which sheet ids were admitted from the
  skip index on the most recent ``discover_source_sheets`` call.
- ``pipeline.orchestrate._compute_registry_marker_sheets`` derives the
  marker set: fully validated this run AND column_mapping written this
  call. A skip-admitted sheet is never promoted; a frequent-run sheet whose
  stored mapping is merely echoed is not certified either.
- Both ``upsert_sheet_registry`` call sites in ``orchestrate.main`` pass
  the derived set.
- The derived set, fed to the real writer, lands the marker on the payload.

Evidence label: FIXTURE PASS only.
"""

from __future__ import annotations

import inspect
import os
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class DiscoverySkipSidsGetterTests(unittest.TestCase):
    """``pipeline.discovery.get_last_discovery_skip_sids`` mirrors
    ``pipeline.fetch.get_last_sheet_versions``: empty before the first
    call, a defensive copy, recorded by ``discover_source_sheets``."""

    def test_getter_exists_and_returns_defensive_copy(self):
        from pipeline import discovery

        first = discovery.get_last_discovery_skip_sids()
        self.assertIsInstance(first, set)
        first.add(999)
        self.assertNotIn(999, discovery.get_last_discovery_skip_sids())

    def test_discover_source_sheets_records_skip_sids(self):
        """Source pin: the function that owns ``_discovery_skip_sids``
        publishes it through the module-level record (reset at the top,
        stored after the validation-split log)."""
        from pipeline import discovery

        src = inspect.getsource(discovery.discover_source_sheets)
        self.assertIn("_set_last_discovery_skip_sids(", src)
        self.assertIn("_set_last_discovery_skip_sids(_discovery_skip_sids)", src)


class ComputeRegistryMarkerSheetsTests(unittest.TestCase):
    """Pure helper: marker set = (not skip-admitted) AND (column_mapping
    written this call)."""

    def _helper(self) -> Callable[..., dict[int, str]]:
        from pipeline.orchestrate import _compute_registry_marker_sheets
        return _compute_registry_marker_sheets

    def test_fully_validated_new_sheet_gets_marker(self):
        from pipeline.discovery import MAPPING_SCHEMA_MARKER

        result = self._helper()(
            [{"id": 111}, {"id": 222}], set(), {111},
        )
        self.assertEqual(result, {111: MAPPING_SCHEMA_MARKER})

    def test_skip_admitted_sheet_is_never_promoted(self):
        result = self._helper()(
            [{"id": 111}], {111}, None,
        )
        self.assertEqual(result, {})

    def test_frequent_run_echoed_mapping_is_not_certified(self):
        """Fully validated (not in skip_sids) but the frequent run echoes
        the stored mapping (id absent from column_mapping_sheets): no
        marker, because the marker certifies the mapping actually stored."""
        result = self._helper()(
            [{"id": 111}], set(), set(),
        )
        self.assertEqual(result, {})

    def test_deep_run_marks_every_non_admitted_sheet(self):
        from pipeline.discovery import MAPPING_SCHEMA_MARKER

        result = self._helper()(
            [{"id": 111}, {"id": 222}, {"id": 333}], {222}, None,
        )
        self.assertEqual(
            result,
            {111: MAPPING_SCHEMA_MARKER, 333: MAPPING_SCHEMA_MARKER},
        )


class OrchestrateCallSitesPassMarkerTests(unittest.TestCase):
    """Source pin (the repo's established ``inspect.getsource(orch.main)``
    convention): BOTH sheet_registry passes hand the derived marker set to
    the writer, and the set is derived from the discovery getter."""

    def test_both_upsert_calls_pass_mapping_schema_by_sheet(self):
        from pipeline import orchestrate as orch

        src = inspect.getsource(orch.main)
        self.assertEqual(
            src.count("mapping_schema_by_sheet=_registry_marker_sheets"), 2,
        )
        self.assertIn("_discovery.get_last_discovery_skip_sids()", src)
        self.assertIn("_compute_registry_marker_sheets(", src)


class MarkerReachesWriterPayloadTests(unittest.TestCase):
    """The helper's output, fed to the real writer, puts the marker on the
    fully-validated sheet's row and no key on the skip-admitted one."""

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

    def test_helper_output_lands_marker_on_validated_sheet_only(self):
        from pipeline.discovery import MAPPING_SCHEMA_MARKER
        from pipeline.orchestrate import _compute_registry_marker_sheets
        from pipeline_memory import writer as mem_writer

        sheets = [
            {"id": 111, "name": "New sheet", "column_mapping": {"Foreman": 1}},
            {"id": 222, "name": "Cached sheet", "column_mapping": {"Foreman": 2}},
        ]
        watermarks = {222: {"column_mapping": {"Foreman": 2}}}
        # Frequent run: 111 is new (mapping written), 222 was admitted
        # from the skip index (mapping echoed).
        column_mapping_sheets = {111}
        marker_sheets = _compute_registry_marker_sheets(
            sheets, {222}, column_mapping_sheets,
        )

        upsert_capture: list = []
        client = self._fake_client(upsert_capture)
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ):
            mem_writer.upsert_sheet_registry(
                sheets, "run-1", lambda sid: "primary", {},
                column_mapping_sheets=column_mapping_sheets,
                watermarks=watermarks,
                mapping_schema_by_sheet=marker_sheets,
            )

        rows = []
        for call in upsert_capture:
            rows.extend(call.args[0])
        row_111 = next(r for r in rows if r["sheet_id"] == 111)
        row_222 = next(r for r in rows if r["sheet_id"] == 222)
        self.assertEqual(row_111["mapping_schema"], MAPPING_SCHEMA_MARKER)
        self.assertNotIn("mapping_schema", row_222)


if __name__ == "__main__":
    unittest.main()
