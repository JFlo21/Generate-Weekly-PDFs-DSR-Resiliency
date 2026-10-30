"""Phase 15 Plan 15-05: pipeline wiring (run-start GF load, pre-render styles).

Two seams in ``pipeline/orchestrate.py`` call into ``pipeline/foreman_notes.py``:
``_fn.initialize(client)`` before PHASE 1 and ``_fn.attach_group_styles(...)``
just before ``generate_excel``.  Everything here is offline: a recording fake
client, fictional names (GF-style aliases) and fictional WR numbers only.
"""

from __future__ import annotations

import ast
import copy
import datetime
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

_TESTS = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS.parent
for _p in (str(_REPO_ROOT), str(_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import openpyxl  # noqa: E402

import _foreman_notes_golden as golden  # noqa: E402
import generate_weekly_pdfs as gwp  # noqa: E402
from pipeline import change_detection as cd  # noqa: E402
from pipeline import config  # noqa: E402
from pipeline import foreman_notes as fn  # noqa: E402
from pipeline import orchestrate as orch  # noqa: E402

ORCH_PATH = _REPO_ROOT / "pipeline" / "orchestrate.py"

SOURCE_SHEET = 7001
WR_COL_ID = 5180541294563204
GF_COL_ID = 2159630534528900
YELLOW = ",,,,,,,,,21,,,,,,,"
PILOT_WR = "90003"
OTHER_WR = "90004"

MAPPING = {
    "Pole #": 11, "CU": 12, "Work Type": 13, "CU Description": 14,
    "Unit of Measure": 15, "Quantity": 16, "Units Total Price": 17,
    "Foreman Notes": 18,
}


def _target_sheet():
    def cells(wr, gf):
        return NS(cells=[
            NS(column_id=WR_COL_ID, value=wr, display_value=wr),
            NS(column_id=GF_COL_ID, value=gf, display_value=gf),
        ])

    return NS(
        columns=[
            NS(id=WR_COL_ID, title="Work Request #"),
            NS(id=GF_COL_ID, title="General Foreman"),
        ],
        rows=[cells(PILOT_WR, "  avery   example "), cells(OTHER_WR, "NA")],
        total_row_count=2,
    )


class _Sheets:
    def __init__(self):
        self.calls = []

    def get_sheet(self, sheet_id, **kwargs):
        self.calls.append((sheet_id, kwargs))
        if sheet_id == config.TARGET_SHEET_ID:
            return _target_sheet()
        ids = [int(x) for x in kwargs["row_ids"].split(",")]
        return NS(rows=[
            NS(id=i, conditional_format=YELLOW, format_=None, cells=[])
            for i in ids
        ])


class _Client:
    def __init__(self):
        self.Sheets = _Sheets()


def _group(wr):
    """Golden-shaped primary rows re-labelled to a fictional WR."""
    rows = copy.deepcopy(golden._rows())
    for n, row in enumerate(rows, start=1):
        row["Work Request #"] = wr
        row["__source_sheet_id"] = SOURCE_SHEET
        row["__row_id"] = 1000 + n
    return f"{golden.WEEK_RAW}_{wr}", rows


class _Base(unittest.TestCase):
    def setUp(self):
        fn.reset_state()
        self.addCleanup(fn.reset_state)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def pilot_patches(self):
        stack = mock.patch.multiple(
            config, FOREMAN_NOTES_PILOT_GFS="Avery Example")
        scope = mock.patch.object(fn, "EFFECTIVE_SCOPE", "pilot")
        return stack, scope


class TracerTests(_Base):
    def test_pilot_path_end_to_end(self):
        client = _Client()
        patch_cfg, patch_scope = self.pilot_patches()
        with patch_cfg, patch_scope:
            state = fn.initialize(client)
        self.assertEqual(state.pilot_wrs, frozenset({PILOT_WR}))
        self.assertTrue(state.gf_loaded)

        maps = fn.build_sheet_column_maps(
            [{"id": SOURCE_SHEET, "column_mapping": MAPPING}])

        results = {}
        with golden.pinned_env(output_folder=self._tmp.name):
            for wr in (PILOT_WR, OTHER_WR):
                key, rows = _group(wr)
                hash_on = cd.calculate_data_hash(rows)
                fn.attach_group_styles(client, rows, maps)
                path, *_rest = gwp.generate_excel(
                    key, rows, golden.SNAPSHOT_DATE, data_hash=hash_on)
                # Hash of the same rows with the run state reset
                saved = fn.get_state()
                fn.reset_state()
                hash_off = cd.calculate_data_hash(rows)
                fn.set_state(saved)
                results[wr] = (path, hash_on, hash_off)

        # Exactly one target-sheet read and one style read.
        targets = [c for c in client.Sheets.calls
                   if c[0] == config.TARGET_SHEET_ID]
        styles = [c for c in client.Sheets.calls if c[0] == SOURCE_SHEET]
        self.assertEqual(len(targets), 1)
        self.assertEqual(len(styles), 1)
        self.assertEqual(styles[0][1].get("include"), "format")

        # Pilot workbook: note in I, carried fill on A-F/H/I of CU rows.
        ws = openpyxl.load_workbook(results[PILOT_WR][0]).active
        header = next(r for r in range(1, ws.max_row + 1)
                      if ws.cell(row=r, column=1).value == "Point Number")
        self.assertEqual(ws.cell(row=header, column=9).value, "Foreman Notes")
        first_cu = header + 1
        self.assertEqual(
            ws.cell(row=first_cu, column=9).value,
            fn.norm_note(golden.NOTE_TEXTS[0]))
        for col in (1, 2, 3, 4, 5, 6, 8, 9):
            cell = ws.cell(row=first_cu, column=col)
            self.assertEqual(cell.fill.fill_type, "solid", col)
            self.assertEqual(cell.fill.fgColor.rgb[-6:], "FEFF00", col)

        # Non-pilot workbook: no column I header, no carried fill.
        ws2 = openpyxl.load_workbook(results[OTHER_WR][0]).active
        for r in range(1, ws2.max_row + 1):
            self.assertNotEqual(ws2.cell(row=r, column=9).value, "Foreman Notes")
        header2 = next(r for r in range(1, ws2.max_row + 1)
                       if ws2.cell(row=r, column=1).value == "Point Number")
        for col in (1, 2, 3, 4, 5, 6, 8):
            fill = ws2.cell(row=header2 + 1, column=col).fill
            self.assertNotEqual(
                (fill.fgColor.rgb or "")[-6:] if fill.fill_type else None,
                "FEFF00", col)

        # Hash: differs for the pilot WR, identical for the other.
        self.assertNotEqual(results[PILOT_WR][1], results[PILOT_WR][2])
        self.assertEqual(results[OTHER_WR][1], results[OTHER_WR][2])


# ---------------------------------------------------------------------------
# Task 2: seam order, zero impact, dry-run persistence guard
# ---------------------------------------------------------------------------

ORCH_SOURCE = ORCH_PATH.read_text(encoding="utf-8")
ORCH_TREE = ast.parse(ORCH_SOURCE)
GATE_NAMES = {
    "RUN_MEMORY_WRITE_ENABLED", "SUPABASE_HASH_STORE_WRITE_ENABLED",
    "TEST_MODE", "AUDIT_MEMORY_ENABLED",
}
KINDS = (
    "row_state", "sheet_registry", "group_state", "run_ledger", "hash_store",
    "billing_audit_hash", "audit_findings",
)


def _func(name):
    return next(
        n for n in ast.walk(ORCH_TREE)
        if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(node, dotted):
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                text = f"{f.value.id}.{f.attr}"
            elif isinstance(f, ast.Name):
                text = f.id
            else:
                text = None
            if text == dotted:
                out.append(n)
    return out


def _uses_fn(node):
    return any(isinstance(x, ast.Name) and x.id == "_fn" for x in ast.walk(node))


class SeamOrderTests(unittest.TestCase):
    def test_initialize_runs_before_phase_one_and_memory_writes(self):
        main = _func("main")
        init = _calls(main, "_fn.initialize")
        self.assertEqual(len(init), 1)
        line = init[0].lineno
        seg_lines = ast.get_source_segment(ORCH_SOURCE, main).splitlines()

        def line_of(text):
            idxs = [i for i, ln in enumerate(seg_lines) if text in ln]
            self.assertTrue(idxs, text)
            return main.lineno + idxs[0]

        self.assertGreater(line, line_of("client.errors_as_exceptions(True)"))
        self.assertGreater(line, line_of("run_claimer_remediation("))
        self.assertLess(line, line_of("PHASE 1: Discovering source sheets"))
        for early in ("_run_memory_write_phase", "_run_phase2_incremental",
                      "discover_source_sheets"):
            calls = _calls(main, early)
            self.assertTrue(calls, early)
            for call in calls:
                self.assertLess(line, call.lineno, early)
        # not nested inside the REMEDIATE_CLAIMERS branch
        parents = {c: p for p in ast.walk(main) for c in ast.iter_child_nodes(p)}
        node = init[0]
        while node in parents:
            node = parents[node]
            if isinstance(node, ast.If):
                names = {n.id for n in ast.walk(node.test)
                         if isinstance(n, ast.Name)}
                self.assertNotIn("REMEDIATE_CLAIMERS", names)

    def test_attach_precedes_generate_excel_with_no_hash_between(self):
        main = _func("main")
        attach = _calls(main, "_fn.attach_group_styles")
        self.assertEqual(len(attach), 1)
        parents = {c: p for p in ast.walk(main) for c in ast.iter_child_nodes(p)}
        stmt = attach[0]
        while not isinstance(stmt, ast.stmt):
            stmt = parents[stmt]
        block = parents[stmt].body
        nxt = block[block.index(stmt) + 1]
        self.assertTrue(_calls(nxt, "generate_excel"))
        self.assertFalse(_calls(nxt, "calculate_data_hash"))
        # the only group hash computation in main precedes the attach
        hashes = _calls(main, "calculate_data_hash")
        self.assertEqual(len(hashes), 1)
        self.assertLess(hashes[0].lineno, attach[0].lineno)

    def test_fn_references_confined_to_expected_functions(self):
        top = {n.name: n for n in ORCH_TREE.body
               if isinstance(n, ast.FunctionDef)}
        users = {name for name, node in top.items() if _uses_fn(node)}
        self.assertEqual(
            users,
            {"main", "_run_memory_write_phase", "_note_pending_regen_pairs",
             "_reconcile_deep_run_deletions", "_run_audit_memory_phase"})
        for forbidden in ("_run_synthetic_test_mode", "_upload_one"):
            node = top.get(forbidden)
            if node is not None:
                self.assertFalse(_uses_fn(node), forbidden)
        self.assertIn("_run_synthetic_test_mode", top)


class _RecordingClient:
    def __init__(self):
        self.calls = []
        outer = self

        class _S:
            def get_sheet(self, *a, **k):
                outer.calls.append((a, k))
                raise AssertionError("no Smartsheet call expected")

        self.Sheets = _S()


class ZeroImpactTests(_Base):
    def test_off_scope_makes_zero_calls_and_leaves_rows_unchanged(self):
        client = _RecordingClient()
        key, rows = _group(PILOT_WR)
        before = copy.deepcopy(rows)
        with mock.patch.object(fn, "EFFECTIVE_SCOPE", "off"):
            state = fn.initialize(client)
        self.assertEqual(state, fn.FnState())
        maps = fn.build_sheet_column_maps(
            [{"id": SOURCE_SHEET, "column_mapping": MAPPING}])
        self.assertEqual(fn.attach_group_styles(client, rows, maps), 0)
        self.assertEqual(client.calls, [])
        self.assertEqual(rows, before)

    def test_non_pilot_group_makes_zero_calls_in_pilot_scope(self):
        client = _RecordingClient()
        key, rows = _group(OTHER_WR)
        fn.set_state(fn.FnState(
            scope="pilot", allowlist=frozenset({"avery example"}),
            pilot_wrs=frozenset({PILOT_WR}), gf_loaded=True))
        maps = fn.build_sheet_column_maps(
            [{"id": SOURCE_SHEET, "column_mapping": MAPPING}])
        self.assertEqual(fn.attach_group_styles(client, rows, maps), 0)
        self.assertEqual(client.calls, [])

    def test_default_effective_scope_is_off_for_production_env(self):
        if (config.TEST_MODE or config.FOREMAN_NOTES_UPLOAD
                or os.getenv("TEST_MODE") or os.getenv("FOREMAN_NOTES_UPLOAD")):
            self.skipTest("test process env sets TEST_MODE/FOREMAN_NOTES_UPLOAD")
        self.assertEqual(fn.EFFECTIVE_SCOPE, "off")
        self.assertEqual(config.FOREMAN_NOTES_PILOT_GFS, "")

    def test_memory_writes_possible_covers_audit_memory_flag(self):
        flags = dict(
            SUPABASE_HASH_STORE_WRITE_ENABLED=False,
            RUN_MEMORY_WRITE_ENABLED=False)
        with mock.patch.multiple(config, AUDIT_MEMORY_ENABLED=False, **flags):
            self.assertFalse(fn.memory_writes_possible())
        with mock.patch.multiple(config, AUDIT_MEMORY_ENABLED=True, **flags):
            self.assertTrue(fn.memory_writes_possible())


# --- write-guard drift test -------------------------------------------------

_MEM_PREFIXES = ("upsert_", "run_ledger_", "bump_")
# Helpers whose own raw write is guarded at function level but whose gate lives
# at their (single) call site in main(); each call is asserted gated below.
_CALLER_GATED = {"_note_pending_regen_pairs", "_reconcile_deep_run_deletions"}


def _write_sites():
    """Every raw pipeline_memory / hash-store write reference in orchestrate."""
    sites = []
    for n in ast.walk(ORCH_TREE):
        # mark_rows_deleted is bound as a default argument and invoked through
        # the local name; the invocation is the write.
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "mark_rows_deleted_fn"):
            sites.append(n.func)
            continue
        if not (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)):
            continue
        owner, attr = n.value.id, n.attr
        if owner == "_mem_writer" and attr.startswith(_MEM_PREFIXES):
            sites.append(n)
        elif owner == "_mem_audit_findings" and attr == "upsert_audit_findings":
            sites.append(n)
        elif owner == "_billing_audit_writer" and attr in (
                "upsert_group_hash", "emit_run_fingerprint"):
            sites.append(n)
    return sites


def _names(expr):
    return {x.id for x in ast.walk(expr) if isinstance(x, ast.Name)}


def _has_guard_call(expr):
    return any(
        isinstance(x, ast.Call)
        and isinstance(x.func, ast.Attribute)
        and x.func.attr == "memory_write_blocked"
        for x in ast.walk(expr))


def _parents():
    return {c: p for p in ast.walk(ORCH_TREE) for c in ast.iter_child_nodes(p)}


def _enclosing_ifs(node, parents):
    """Ancestor ``If`` nodes (innermost first) whose *body* holds ``node``."""
    out = []
    child, cur = node, parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.If) and any(child is b for b in cur.body):
            out.append(cur)
        child, cur = cur, parents.get(cur)
    return out


def _enclosing_func(node, parents):
    cur = parents.get(node)
    while cur is not None and not isinstance(cur, ast.FunctionDef):
        cur = parents.get(cur)
    return cur


def _function_level_guard(func, node_line):
    """(gated_before, guarded) for a function-level early-return pattern."""
    gated = guarded = False
    for stmt in func.body:
        if not isinstance(stmt, ast.If) or stmt.lineno >= node_line:
            continue
        returns = any(isinstance(x, ast.Return) for x in stmt.body)
        if returns and _has_guard_call(stmt.test):
            guarded = True
        elif returns and _names(stmt.test) & GATE_NAMES:
            gated = True
    return gated, guarded


class WriteGuardDriftTests(unittest.TestCase):
    # Inventory (plan 15-05 Task 2): one entry per raw write reference in
    # orchestrate.py. A new write site changes this count and fails the test
    # until it is guarded and listed in the SUMMARY inventory.
    EXPECTED_SITE_COUNT = 15

    def test_every_write_site_is_guarded_inside_its_existing_gate(self):
        parents = _parents()
        sites = _write_sites()
        self.assertEqual(len(sites), self.EXPECTED_SITE_COUNT)
        for site in sites:
            where = f"{ast.unparse(site)} line {site.lineno}"
            ifs = _enclosing_ifs(site, parents)
            guard_idx = next(
                (i for i, f in enumerate(ifs) if _has_guard_call(f.test)), None)
            if guard_idx is not None:
                outer = ifs[guard_idx + 1:]
                self.assertTrue(
                    any(_names(f.test) & GATE_NAMES for f in outer),
                    f"guard not nested inside an existing gate: {where}")
                continue
            func = _enclosing_func(site, parents)
            self.assertIsNotNone(func, where)
            gated, guarded = _function_level_guard(func, site.lineno)
            self.assertTrue(guarded, f"unguarded write site: {where}")
            self.assertTrue(
                gated or func.name in _CALLER_GATED,
                f"function-level guard without a gate: {where}")

    def test_run_memory_write_phase_callee_is_self_gated_and_guarded(self):
        func = _func("_run_memory_write_phase")
        gated, guarded = _function_level_guard(func, 10 ** 9)
        self.assertTrue(gated and guarded)
        callers = [
            n for n in ast.walk(ORCH_TREE)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_run_memory_write_phase"]
        self.assertEqual(len(callers), 2)

    def test_caller_gated_helpers_are_called_inside_a_gate(self):
        parents = _parents()
        for name in _CALLER_GATED:
            calls = [
                n for n in ast.walk(ORCH_TREE)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == name]
            self.assertTrue(calls, name)
            for call in calls:
                self.assertTrue(
                    any(_names(f.test) & GATE_NAMES
                        for f in _enclosing_ifs(call, parents)),
                    f"{name} called outside a gate at line {call.lineno}")

    def test_audit_memory_phase_guard_sits_after_its_gate(self):
        gated, guarded = _function_level_guard(
            _func("_run_audit_memory_phase"), 10 ** 9)
        self.assertTrue(gated and guarded)


# --- guard behaviour --------------------------------------------------------

class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def errors(self):
        return [r for r in self.records
                if r.levelno >= logging.ERROR
                and "Foreman notes" in r.getMessage()]


class GuardBehaviourTests(_Base):
    def setUp(self):
        super().setUp()
        self.cap = _LogCapture()
        root = logging.getLogger()
        root.addHandler(self.cap)
        self.addCleanup(root.removeHandler, self.cap)
        for p in (
            mock.patch.object(fn, "EFFECTIVE_SCOPE", "pilot"),
            mock.patch.object(config, "TEST_MODE", True),
            mock.patch.object(config, "FOREMAN_NOTES_UPLOAD", False),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_blocked_for_every_kind_logs_error_once_per_kind(self):
        for kind in KINDS:
            self.assertTrue(fn.memory_write_blocked(kind))
            self.assertTrue(fn.memory_write_blocked(kind))
        self.assertEqual(len(self.cap.errors()), len(KINDS))
        for rec in self.cap.errors():
            self.assertNotIn(PILOT_WR, rec.getMessage())

    def test_not_blocked_outside_a_dry_run_pilot(self):
        with mock.patch.object(config, "TEST_MODE", False):
            for kind in KINDS:
                self.assertFalse(fn.memory_write_blocked(kind))
        with mock.patch.object(config, "FOREMAN_NOTES_UPLOAD", True):
            self.assertFalse(fn.memory_write_blocked("row_state"))
        with mock.patch.object(fn, "EFFECTIVE_SCOPE", "off"):
            self.assertFalse(fn.memory_write_blocked("row_state"))
        self.assertEqual(self.cap.errors(), [])

    def test_normal_dry_run_emits_zero_guard_errors(self):
        # The recipe's flags: every write flag off, TEST_MODE on.
        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", False), \
                mock.patch.object(orch, "TEST_MODE", True), \
                mock.patch.object(orch, "AUDIT_MEMORY_ENABLED", False), \
                mock.patch.object(
                    orch._mem_writer, "upsert_rows_bulk_result") as w:
            result = orch._run_memory_write_phase(
                [{"x": 1}], "run", datetime.datetime.now())
            audit = orch._run_audit_memory_phase({"a": [1]}, [], "run")
            w.assert_not_called()
        self.assertEqual(result["sheets_written"], 0)
        self.assertEqual(audit["findings_emitted"], 0)
        # ...and the tracer path (init + attach) logs no guard ERROR either.
        client = _Client()
        with mock.patch.object(
                config, "FOREMAN_NOTES_PILOT_GFS", "Avery Example"):
            fn.initialize(client)
        maps = fn.build_sheet_column_maps(
            [{"id": SOURCE_SHEET, "column_mapping": MAPPING}])
        fn.attach_group_styles(client, _group(PILOT_WR)[1], maps)
        self.assertEqual(self.cap.errors(), [])

    def test_open_gate_in_a_dry_run_pilot_is_blocked_before_the_write(self):
        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
                mock.patch.object(orch, "TEST_MODE", False), \
                mock.patch.object(
                    orch._mem_writer, "upsert_rows_bulk_result") as w:
            result = orch._run_memory_write_phase(
                [{"x": 1}], "run", datetime.datetime.now())
            w.assert_not_called()
        self.assertEqual(result["sheets_written"], 0)
        self.assertEqual(len(self.cap.errors()), 1)

    def test_audit_and_helper_writes_are_blocked_when_reached(self):
        with mock.patch.object(orch, "AUDIT_MEMORY_ENABLED", True), \
                mock.patch.object(
                    orch._mem_audit_findings, "upsert_audit_findings") as up, \
                mock.patch.object(
                    orch._mem_writer, "run_ledger_note_pending") as note:
            out = orch._run_audit_memory_phase({"a": [1]}, [], "run")
            self.assertEqual(out["findings_emitted"], 0)
            self.assertFalse(
                orch._note_pending_regen_pairs("run", set(), False))
            up.assert_not_called()
            note.assert_not_called()
        marked = mock.Mock()
        res = orch._reconcile_deep_run_deletions(
            [{"id": SOURCE_SHEET}], {SOURCE_SHEET: {1}}, "run",
            get_row_state_row_ids_fn=mock.Mock(return_value={1, 2}),
            mark_rows_deleted_fn=marked)
        marked.assert_not_called()
        self.assertEqual(res["rows_marked_deleted"], 0)
        kinds = {r.getMessage().split("kind=")[-1].rstrip(")")
                 for r in self.cap.errors()}
        self.assertEqual(kinds, {"audit_findings", "run_ledger", "row_state"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
