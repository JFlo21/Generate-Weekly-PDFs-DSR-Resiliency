"""G-11-37 mechanism A -- row_state hash-domain regression tests (11-11).

Defect: the D-04 candidate set is derived from ``row_state.content_hash``
deltas, but ``row_state`` hashed only ``pipeline_memory.writer.HASH_FIELDS``
while the group hash (``pipeline.change_detection.calculate_data_hash``)
also reads Dept #, Scope #/ID, Customer Name, Job #, Work Order #,
CU Description, Unit of Measure, Area and the raw Quantity/Snapshot text --
plus the group-key inputs (``Foreman Assigned?`` -> ``__effective_user``).
An edit to any of those regenerated a group with NO ``row_state`` change,
so the (wr, week_ending) pair never entered the affected set.

Fix under test: ``pipeline.orchestrate._run_memory_write_phase`` stamps
``__mem_group_fp`` (``pipeline.memory_candidate.row_group_hash_fingerprint``)
on each row; ``pipeline_memory.writer`` folds it into ``content_hash`` via
``HASH_ONLY_FIELDS`` and strips it from the sent payload (no DDL, RPC
``p_rows`` key set unchanged, ``HASH_FIELDS`` unchanged).
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import generate_weekly_pdfs  # noqa: E402
import pipeline.fetch as _fetch  # noqa: E402
import pipeline.orchestrate as orchestrate  # noqa: E402
import pipeline_memory.writer as mem_writer  # noqa: E402
from pipeline import change_detection  # noqa: E402

# The exact pre-plan ``_row_to_payload`` key set (what ``p_rows`` carries).
_PRE_PLAN_PAYLOAD_KEYS = frozenset({
    "row_id", "wr", "week_ending", "snapshot_date", "cu", "pole",
    "work_type", "quantity", "units_total_price", "units_completed",
    "foreman_observed", "helper_observed", "helper_completed",
    "helper_dept", "helper_job", "vac_crew_observed", "vac_completed",
    "helper2_observed", "helper2_completed", "helper2_dept", "helper2_job",
    "row_modified_at", "content_hash",
})

_PRE_PLAN_HASH_FIELDS = (
    "wr", "week_ending", "snapshot_date", "cu", "pole", "work_type",
    "quantity", "units_total_price", "units_completed", "foreman_observed",
    "helper_observed", "helper_completed", "helper_dept", "helper_job",
    "vac_crew_observed", "vac_completed", "helper2_observed",
    "helper2_completed", "helper2_dept", "helper2_job",
)


def _row(**overrides):
    """Baseline raw-mapped row, as the full-read path hands it on."""
    row = {
        "__row_id": 1001,
        "__source_sheet_id": 111,
        "__sheet_id": 111,
        "Work Request #": "90001",
        "Weekly Reference Logged Date": "2026-08-30",
        "Snapshot Date": "2026-08-25",
        "Units Completed?": True,
        "Units Total Price": "$75.00",
        "Quantity": "5",
        "CU": "CU-100",
        "Work Type": "Install",
        "Pole #": "P-1",
        "Dept #": "510",
        "Scope #": "S-1",
        "Customer Name": "AEP Ohio",
        "Job #": "J-100",
        "Work Order #": "WO-1",
        "CU Description": "Set pole",
        "Unit of Measure": "EA",
        "Area": "North",
        "Foreman": "Primary Person",
    }
    row.update(overrides)
    return row


class _FakeUpsert:
    """Stands in for ``upsert_rows_bulk_result``; records the rows it got."""

    def __init__(self):
        self.rows: list[dict] = []

    def __call__(self, sheet_id, run_id, rows):
        self.rows.extend(rows)
        return {"affected": set(), "status": "ok", "rows_errored": 0}


def _run_phase(rows):
    """Drive the REAL ``_run_memory_write_phase`` over ``rows`` with a
    recording fake writer; return the rows the writer received."""
    fake = _FakeUpsert()
    with mock.patch.object(orchestrate, "RUN_MEMORY_WRITE_ENABLED", True), \
            mock.patch.object(orchestrate, "TEST_MODE", False), \
            mock.patch.object(orchestrate, "GITHUB_ACTIONS_MODE", False), \
            mock.patch.object(
                orchestrate._mem_writer, "upsert_rows_bulk_result", fake,
            ):
        import datetime
        orchestrate._run_memory_write_phase(
            rows, "run-test", datetime.datetime.now(),
        )
    return fake.rows


def _stamped_payload(row):
    """Row -> (orchestrate's real stamping) -> the writer's real payload."""
    sent = _run_phase([copy.deepcopy(row)])
    assert len(sent) == 1
    payload = mem_writer._row_to_payload(
        sent[0], "run-test", sent[0].get("__mem_week_ending"),
        sent[0].get("__mem_snapshot_date"),
    )
    assert payload is not None
    return payload


def _content_hash(row):
    return _stamped_payload(row)["content_hash"]


class MechanismATracerTests(unittest.TestCase):
    """Task 1 tracer: a Job # edit flows row dict -> fingerprint ->
    content_hash -> affected pair."""

    def test_a_job_number_edit_alone_changes_content_hash(self):
        self.assertNotEqual(
            _content_hash(_row(**{"Job #": "J-100"})),
            _content_hash(_row(**{"Job #": "J-200"})),
        )

    def test_b_dept_edit_alone_changes_content_hash(self):
        self.assertNotEqual(
            _content_hash(_row(**{"Dept #": "510"})),
            _content_hash(_row(**{"Dept #": "520"})),
        )

    def test_c_phase_stamps_fingerprint_and_payload_keys_unchanged(self):
        sent = _run_phase([_row(), _row(__row_id=1002, **{"Job #": "J-9"})])
        self.assertEqual(len(sent), 2)
        for row in sent:
            self.assertTrue(row.get("__mem_group_fp"))
        for row in sent:
            payload = mem_writer._row_to_payload(
                row, "run-test", row.get("__mem_week_ending"),
                row.get("__mem_snapshot_date"),
            )
            self.assertEqual(set(payload), _PRE_PLAN_PAYLOAD_KEYS)
            self.assertNotIn("group_hash_fp", payload)
            self.assertNotIn("__mem_group_fp", payload)

    def test_d_hash_fields_unchanged_and_disjoint_from_hash_only(self):
        self.assertEqual(mem_writer.HASH_FIELDS, _PRE_PLAN_HASH_FIELDS)
        self.assertEqual(mem_writer.HASH_ONLY_FIELDS, ("group_hash_fp",))
        self.assertFalse(
            set(mem_writer.HASH_FIELDS) & set(mem_writer.HASH_ONLY_FIELDS)
        )


# -- Test E fixtures: a synthetic sheet through the REAL full-read path ----

def _column_id_map(*fields):
    return {field: idx + 1 for idx, field in enumerate(fields)}


def _fetch_row(row_id, values, column_mapping):
    cells = [
        SimpleNamespace(
            column_id=column_mapping[f], value=v, display_value=None,
        )
        for f, v in values.items() if f in column_mapping
    ]
    return SimpleNamespace(id=row_id, cells=cells, modified_at=None)


_FETCH_FIELDS = (
    "Work Request #", "Weekly Reference Logged Date", "Snapshot Date",
    "Units Completed?", "Units Total Price", "Quantity", "CU", "Work Type",
    "Pole #", "Dept #", "Job #", "Foreman", "Foreman Assigned?",
)


def _full_read_row(values, row_id=5001, sheet_id=7770001):
    """One row through the REAL ``get_all_source_rows`` (full-read path)."""
    column_mapping = _column_id_map(*_FETCH_FIELDS)
    source = {"id": sheet_id, "name": "tracer", "column_mapping": column_mapping}
    sheet = SimpleNamespace(
        rows=[_fetch_row(row_id, values, column_mapping)], version=1,
    )
    with mock.patch.object(
        _fetch, "smartsheet_call_with_retry",
        side_effect=lambda _fn, _sid, **_kw: sheet,
    ):
        result = _fetch.get_all_source_rows(mock.Mock(), [source])
    assert len(result) == 1, result
    return result[0]


def _fetch_values(**overrides):
    values = {
        "Work Request #": "90001",
        "Weekly Reference Logged Date": "2026-08-30",
        "Snapshot Date": "2026-08-25",
        "Units Completed?": True,
        "Units Total Price": "$75.00",
        "Quantity": "5",
        "CU": "CU-100",
        "Work Type": "Install",
        "Pole #": "P-1",
        "Dept #": "510",
        "Job #": "J-100",
        "Foreman": "Primary Person",
        "Foreman Assigned?": "Crew A",
    }
    values.update(overrides)
    return values


def _group_hash_like_grouping(row):
    """``calculate_data_hash`` over one row with ``__current_foreman`` set
    the way ``grouping.py`` (~1587) sets it on the per-group copy."""
    copy_ = dict(row)
    copy_["__variant"] = "primary"
    copy_["__current_foreman"] = row.get("__effective_user")
    return change_detection.calculate_data_hash([copy_])


class ForemanAssignedGroupKeyTests(unittest.TestCase):
    """Test E (checker blocker): ``Foreman Assigned?`` alone re-keys the
    group (it wins over ``Foreman`` in ``__effective_user``) so it must
    also change ``row_state.content_hash``."""

    def test_e_foreman_assigned_edit_alone_flips_group_and_content_hash(self):
        row_a = _full_read_row(_fetch_values(**{"Foreman Assigned?": "Crew A"}))
        row_b = _full_read_row(_fetch_values(**{"Foreman Assigned?": "Crew B"}))
        # Foreman itself is unchanged.
        self.assertEqual(row_a["Foreman"], row_b["Foreman"])
        # (i) the fetch derivation produces a different effective user.
        self.assertNotEqual(
            row_a["__effective_user"], row_b["__effective_user"],
        )
        # (ii) the group hash differs.
        self.assertNotEqual(
            _group_hash_like_grouping(row_a),
            _group_hash_like_grouping(row_b),
        )
        # (iii) the stamped row_state content_hash differs.
        self.assertNotEqual(_content_hash(row_a), _content_hash(row_b))
        # foreman_observed still stores raw Foreman only.
        self.assertEqual(
            _stamped_payload(row_a)["foreman_observed"], "Primary Person",
        )


if __name__ == "__main__":
    unittest.main()
