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


def _full_read_row(
    values, row_id=5001, sheet_id=7770001, fields=_FETCH_FIELDS,
):
    """One row through the REAL ``get_all_source_rows`` (full-read path)."""
    column_mapping = _column_id_map(*fields)
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


# ===========================================================================
# Task 2 -- full hash-domain coverage
# ===========================================================================

def _group_hash(row, variant="primary"):
    """``calculate_data_hash`` over one row the way grouping presents it."""
    copy_ = dict(row)
    copy_["__variant"] = variant
    copy_["__current_foreman"] = (
        row.get("__effective_user") or row.get("Foreman")
    )
    return change_detection.calculate_data_hash([copy_])


# (perturbed key, extra baseline overrides, value A, value B)
_HASHED_FIELD_CASES = [
    ("Dept #", {}, "510", "520"),
    ("Scope #", {}, "S-1", "S-2"),
    ("Scope ID", {"Scope #": ""}, "SID-1", "SID-2"),
    ("Customer Name", {}, "AEP Ohio", "AEP Indiana"),
    ("Job #", {}, "J-100", "J-200"),
    ("Job Number", {"Job #": ""}, "JN-1", "JN-2"),
    ("Work Order #", {}, "WO-1", "WO-2"),
    ("Work Order Number", {"Work Order #": ""}, "WON-1", "WON-2"),
    ("CU Description", {}, "Set pole", "Set pole 40ft"),
    ("Unit of Measure", {}, "EA", "FT"),
    ("Area", {}, "North", "South"),
    ("Quantity", {}, "5", "5.0"),  # raw text, same parsed value
    ("Snapshot Date", {}, "2026-08-25", "2026-08-26"),
    ("Pole #", {}, "P-1", "P-2"),
    ("Work Type", {}, "Install", "Remove"),
    ("Units Completed?", {}, True, False),
    ("Units Total Price", {}, "$75.00", "$80.00"),
]


class PerturbationTests(unittest.TestCase):
    """Perturbing ONE group-hashed field flips BOTH ``calculate_data_hash``
    and the stamped ``row_state.content_hash`` (the two domains agree)."""

    def test_every_group_hashed_field_flips_both_hashes(self):
        for key, base_over, val_a, val_b in _HASHED_FIELD_CASES:
            with self.subTest(field=key):
                row_a = _row(**{**base_over, key: val_a})
                row_b = _row(**{**base_over, key: val_b})
                self.assertNotEqual(
                    _group_hash(row_a), _group_hash(row_b),
                    f"{key}: group hash did not flip (bad test case)",
                )
                self.assertNotEqual(
                    _content_hash(row_a), _content_hash(row_b),
                    f"{key}: row_state content_hash did not flip",
                )

    def test_group_key_inputs_flip_derived_key_and_content_hash(self):
        """Group-KEY / positional-meta inputs, through the REAL full-read
        derivation: the derived key flips AND ``content_hash`` flips.

        Derived keys are not fingerprinted directly (delta rows never
        carry them -- see ``ModeInvarianceTests``); their raw sources are.
        """
        helper_on = {
            "Foreman Helping?": "Helper One",
            "Helping Foreman Completed Unit?": True,
            "Helper Dept #": "500",
            "Helper Job #": "HJ-1",
        }
        vac_on = {
            "VAC Crew Helping?": "Vac Person",
            "Vac Crew Completed Unit?": True,
            "VAC Crew Dept #": "600",
            "Vac Crew Job #": "VJ-1",
        }
        cases = [
            ("Foreman Assigned?", {}, "__effective_user",
             "Crew A", "Crew B"),
            ("Foreman Helping?", helper_on, "__helper_foreman",
             "Helper One", "Helper Two"),
            ("Helper Dept #", helper_on, "__helper_dept", "500", "510"),
            ("Helper Job #", helper_on, "__helper_job", "HJ-1", "HJ-2"),
            ("VAC Crew Helping?", vac_on, "__vac_crew_name",
             "Vac Person", "Vac Other"),
            ("VAC Crew Dept #", vac_on, "__vac_crew_dept", "600", "610"),
            ("Vac Crew Job #", vac_on, "__vac_crew_job", "VJ-1", "VJ-2"),
        ]
        for key, base_over, derived, val_a, val_b in cases:
            with self.subTest(source=key):
                row_a = _full_read_row(
                    _fetch_values(**{**base_over, key: val_a}), fields=_ALL,
                )
                row_b = _full_read_row(
                    _fetch_values(**{**base_over, key: val_b}), fields=_ALL,
                )
                self.assertNotEqual(row_a[derived], row_b[derived])
                self.assertNotEqual(
                    _content_hash(row_a), _content_hash(row_b),
                )

    def test_helper_dept_group_hash_flips_with_content_hash(self):
        """Helper group: HELPER_DEPT= meta flips the group hash; the
        stamped content_hash flips with it."""
        helper_on = {
            "Foreman Helping?": "Helper One",
            "Helping Foreman Completed Unit?": True,
            "Helper Job #": "HJ-1",
        }
        rows = [
            _full_read_row(
                _fetch_values(**{**helper_on, "Helper Dept #": d}),
                fields=_ALL,
            )
            for d in ("500", "510")
        ]
        self.assertNotEqual(
            _group_hash(rows[0], "helper"), _group_hash(rows[1], "helper"),
        )
        self.assertNotEqual(_content_hash(rows[0]), _content_hash(rows[1]))


class DeterminismTests(unittest.TestCase):
    def test_unedited_row_hashes_identically_twice(self):
        row = _row()
        self.assertEqual(_content_hash(row), _content_hash(copy.deepcopy(row)))

    def test_key_insertion_order_does_not_matter(self):
        row = _row()
        reversed_row = dict(reversed(list(row.items())))
        self.assertEqual(_content_hash(row), _content_hash(reversed_row))

    def test_fingerprint_failure_returns_empty_string_and_never_raises(self):
        from pipeline.memory_candidate import row_group_hash_fingerprint

        with mock.patch.object(
            change_detection, "parse_price", side_effect=ValueError("boom"),
        ):
            with self.assertLogs(
                "pipeline.memory_candidate", level="WARNING",
            ):
                self.assertEqual(row_group_hash_fingerprint(_row()), "")


# -- Mode invariance: delta-read construction vs full-read construction ----

_HELPER_FIELDS = (
    "Foreman Helping?", "Helping Foreman Completed Unit?",
    "Helper Dept #", "Helper Job #",
)
_VAC_FIELDS = (
    "VAC Crew Helping?", "Vac Crew Completed Unit?", "VAC Crew Dept #",
    "Vac Crew Job #",
)
_ALL = _FETCH_FIELDS + _HELPER_FIELDS + _VAC_FIELDS


def _delta_read_row(values, row_id=5001, sheet_id=7770001, fields=_ALL):
    """The same cells through the REAL delta-read mapper."""
    column_mapping = _column_id_map(*fields)
    source = {"id": sheet_id, "name": "tracer", "column_mapping": column_mapping}
    sheet = SimpleNamespace(
        rows=[_fetch_row(row_id, values, column_mapping)], version=1,
    )
    rows = _fetch.map_delta_sheet_rows(sheet, source)
    assert len(rows) == 1, rows
    return rows[0]


class ModeInvarianceTests(unittest.TestCase):
    """A row built by the delta-read path hashes identically to the same
    row built by the full-read path -- otherwise production alternating
    frequent / weekly runs would churn ``row_event``.

    FINDING (11-11 Task 2): the two paths do NOT attach identical derived
    double-underscore keys -- only the full-read path sets
    ``__effective_user`` / ``__helper_*`` / ``__vac_crew_*``. So derived
    keys are excluded from the fingerprint and covered by their raw
    sources (``memory_candidate.DERIVED_KEY_SOURCES``).
    """

    def _both(self, values):
        return (
            _full_read_row(values, fields=_ALL),
            _delta_read_row(values),
        )

    def test_foreman_assigned_row_invariant(self):
        from pipeline.memory_candidate import row_group_hash_fingerprint

        full, delta = self._both(_fetch_values(**{"Foreman Assigned?": "Crew A"}))
        self.assertEqual(full["__effective_user"], "Crew A")
        self.assertNotIn("__effective_user", delta)  # the finding
        self.assertEqual(
            row_group_hash_fingerprint(full),
            row_group_hash_fingerprint(delta),
        )
        self.assertEqual(_content_hash(full), _content_hash(delta))

    def test_foreman_only_row_invariant(self):
        from pipeline.memory_candidate import row_group_hash_fingerprint

        full, delta = self._both(_fetch_values(**{"Foreman Assigned?": ""}))
        self.assertEqual(full["__effective_user"], "Primary Person")
        self.assertNotIn("__effective_user", delta)
        self.assertEqual(
            row_group_hash_fingerprint(full),
            row_group_hash_fingerprint(delta),
        )
        self.assertEqual(_content_hash(full), _content_hash(delta))

    def test_helper_and_vac_rows_invariant(self):
        from pipeline.memory_candidate import row_group_hash_fingerprint

        values = _fetch_values(**{
            "Foreman Helping?": "Helper One",
            "Helping Foreman Completed Unit?": True,
            "Helper Dept #": "500", "Helper Job #": "HJ-1",
            "VAC Crew Helping?": "Vac Person",
            "Vac Crew Completed Unit?": True,
            "VAC Crew Dept #": "600", "Vac Crew Job #": "VJ-1",
        })
        full, delta = self._both(values)
        self.assertEqual(full["__helper_dept"], "500")
        self.assertEqual(full["__vac_crew_dept"], "600")
        for derived in ("__helper_dept", "__vac_crew_dept"):
            self.assertNotIn(derived, delta)
        self.assertEqual(
            row_group_hash_fingerprint(full),
            row_group_hash_fingerprint(delta),
        )


# -- AST key-coverage drift detector ---------------------------------------

import ast  # noqa: E402

# Row keys the group builder / hash functions read that are NOT fingerprint
# inputs, each with the reason it is safe.
_FINGERPRINT_EXCLUSIONS = {
    "Weekly Reference Logged Date":
        "IS the (wr, week_ending) pair itself; row_state keys on it "
        "(week_ending is in HASH_FIELDS)",
    "__source_sheet_id":
        "row routing / bucketing identity, not billing content",
    "__row_id":
        "row identity (row_state PK), not billing content",
    "__variant":
        "written by grouping on per-group COPIES from covered inputs; "
        "never on the rows the memory write sees",
    "__current_foreman":
        "written by grouping on per-group COPIES (current_foreman or "
        "__effective_user); sources covered via DERIVED_KEY_SOURCES",
    "__grouping_key":
        "written by grouping on per-group copies from covered inputs",
    "__week_ending_date":
        "written by grouping on per-group copies from the week column",
    "User":
        "identity-only last-position sort tiebreaker in "
        "canonical_sorted_rows; hash-neutral by construction (it can only "
        "reorder rows whose hashed strings are identical)",
}

_ROW_RECEIVERS = {
    "row", "r", "x", "_r", "_vr", "_first", "_first2",
    "group_rows[0]", "sorted_rows[0]",
}


def _read_keys(func: ast.FunctionDef, receivers=_ROW_RECEIVERS) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and ast.unparse(node.func.value) in receivers
        ):
            keys.add(node.args[0].value)
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Load)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
            and ast.unparse(node.value) in receivers
        ):
            keys.add(node.slice.value)
    return keys


def _functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


class KeyCoverageDriftTests(unittest.TestCase):
    """Drift detector (T-11-48): every row key the group builder or the
    change-detection hash/sort functions read must be covered by the
    fingerprint, the payload, or a documented exclusion."""

    def test_every_group_input_key_is_covered_or_excluded(self):
        from pipeline import memory_candidate as mc

        cd_funcs = {
            f.name: f for f in _functions(_REPO_ROOT / "pipeline" / "change_detection.py")
        }
        wanted = (
            "_extended_row_fields", "canonical_sorted_rows",
            "_first_nonempty_foreman", "calculate_data_hash",
        )
        read: set[str] = set()
        for name in wanted:
            self.assertIn(name, cd_funcs)
            read |= _read_keys(cd_funcs[name])

        builder = [
            f for f in _functions(_REPO_ROOT / "pipeline" / "grouping.py")
            if "r_copy['__current_foreman']" in ast.unparse(f).replace('"', "'")
        ]
        self.assertEqual(
            [f.name for f in builder], ["group_source_rows"],
            "group builder not located by its __current_foreman assignment",
        )
        read |= _read_keys(builder[0])

        ext_fields = _read_keys(cd_funcs["_extended_row_fields"])
        payload_fn = [
            f for f in _functions(_REPO_ROOT / "pipeline_memory" / "writer.py")
            if f.name == "_row_to_payload"
        ][0]
        payload_keys = _read_keys(payload_fn, receivers={"row_data"})

        covered = (
            ext_fields
            | set(mc.GROUP_DERIVATION_KEYS)
            | set(mc.DERIVED_KEY_SOURCES)
            | payload_keys
            | set(_FINGERPRINT_EXCLUSIONS)
        )
        uncovered = sorted(read - covered)
        self.assertEqual(
            uncovered, [],
            "Row key(s) read by the group builder / hash functions but "
            "neither fingerprinted nor excluded with a reason -- add to "
            "memory_candidate.GROUP_DERIVATION_KEYS / DERIVED_KEY_SOURCES "
            f"or _FINGERPRINT_EXCLUSIONS: {uncovered}",
        )

    def test_every_derived_key_source_is_fingerprinted(self):
        from pipeline import memory_candidate as mc

        ext_fields = _read_keys(
            {f.name: f for f in _functions(
                _REPO_ROOT / "pipeline" / "change_detection.py"
            )}["_extended_row_fields"]
        )
        covered = ext_fields | set(mc.GROUP_DERIVATION_KEYS)
        for derived, sources in mc.DERIVED_KEY_SOURCES.items():
            for src in sources:
                with self.subTest(derived=derived, source=src):
                    self.assertIn(src, covered)

    def test_derived_keys_are_not_fingerprinted_directly(self):
        from pipeline import memory_candidate as mc

        self.assertFalse(
            set(mc.GROUP_DERIVATION_KEYS) & set(mc.DERIVED_KEY_SOURCES)
        )


# ===========================================================================
# Task 3 -- the row_state re-key cannot cause regeneration / upload
# ===========================================================================

class SkipGateIndependenceTests(unittest.TestCase):
    """The one-time ``row_state.content_hash`` re-key on the first
    post-deploy run must not regenerate or upload anything: the per-group
    skip / regenerate gate reads only ``calculate_data_hash``, the durable
    group hash and attachment existence -- never ``row_state``."""

    _FORBIDDEN = (
        "row_state", "_mem_affected", "upsert_rows_bulk", "__mem_group_fp",
    )

    def test_skip_gate_never_reads_row_state(self):
        lines = (
            _REPO_ROOT / "pipeline" / "orchestrate.py"
        ).read_text(encoding="utf-8").splitlines()
        hits = [
            i for i, line in enumerate(lines)
            if "Skip (unchanged + attachment exists)" in line
        ]
        self.assertEqual(len(hits), 1, "skip-gate log line not found once")
        end = hits[0] + 1
        window = lines[max(0, end - 120):end]
        code = [ln for ln in window if not ln.lstrip().startswith("#")]
        for token in self._FORBIDDEN:
            offenders = [ln.strip() for ln in code if token in ln]
            self.assertEqual(
                offenders, [],
                f"skip gate window reads {token!r}: {offenders}",
            )


if __name__ == "__main__":
    unittest.main()
