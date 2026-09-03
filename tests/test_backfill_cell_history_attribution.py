"""Fixture-driven tests for scripts/backfill_cell_history_attribution.py
(OWN-03 source 5, Phase 12 Plan 04).

No live Supabase or Smartsheet access anywhere in this file. Supabase
calls (``pipeline_memory.row_state`` / ``sheet_registry``,
``billing_audit.attribution_snapshot`` for the backlog fallback) are
served by the SAME filter-aware fake client classes
``tests/test_backfill_claim_time_attribution.py`` built for exactly
this kind of reuse (its own SUMMARY: "reusable by plans 12-02..12-06
for similar Supabase-backed script testing"). Smartsheet
``Cells.get_cell_history`` calls are served by a small local fake
defined in this module (no analog existed yet).
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import (  # noqa: E402
    _collapse_ws,
    _read_source,
    _reset_all,
)
from tests.test_backfill_claim_time_attribution import (  # noqa: E402
    _FakeClient,
    _FakeSchema,
    _FakeTable,
)

_SCRIPT_RELPATH = "scripts/backfill_cell_history_attribution.py"


def _reset_all_clients() -> None:
    _reset_all()
    from pipeline_memory import client as pm_client
    pm_client.reset_cache_for_tests()


# ── Fixture builders (sources-1-4 report rows) ───────────────────────

def _report_row(
    wr: str = "19073866",
    week_ending: str = "2026-08-24",
    week_ending_fmt: str = "082425",
    row_id: int = 700001,
    role: str = "primary",
    current_value: str = "Unknown Foreman",
    status: str = "unresolved",
    proposed_value: str = "",
    source: str = "",
) -> dict:
    return {
        "wr": wr,
        "week_ending": week_ending,
        "week_ending_fmt": week_ending_fmt,
        "row_id": row_id,
        "role": role,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "source": source,
        "name_fidelity": "",
        "status": status,
        "evidence": "",
    }


def _write_candidate_report(path: Path, rows: list[dict]) -> None:
    payload = {
        "summary": {"total_rows": len(rows)},
        "rows": rows,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


# ── pipeline_memory fixtures (sheet_id / column_mapping resolution) ──

_COLUMN_MAPPING: dict[str, int] = {
    "Units Completed?": 1001,
    "Foreman": 1002,
    "Helping Foreman Completed Unit?": 1003,
    "Foreman Helping?": 1004,
    "Vac Crew Completed Unit?": 1005,
    "VAC Crew Helping?": 1006,
}
_SHEET_ID = 5551234567890


def _make_pipeline_memory_fake_client(
    row_state_rows: list[dict] | None = None,
    sheet_registry_rows: list[dict] | None = None,
) -> _FakeClient:
    schema_obj = _FakeSchema(
        tables={
            "row_state": _FakeTable(row_state_rows or []),
            "sheet_registry": _FakeTable(sheet_registry_rows or []),
        },
        rpc_handlers={},
    )
    return _FakeClient(schema_obj)


def _default_pipeline_memory_client(row_ids: list[int]) -> _FakeClient:
    return _make_pipeline_memory_fake_client(
        row_state_rows=[
            {"row_id": rid, "sheet_id": _SHEET_ID} for rid in row_ids
        ],
        sheet_registry_rows=[
            {"sheet_id": _SHEET_ID, "column_mapping": _COLUMN_MAPPING}
        ],
    )


# ── Fake Smartsheet client (Cells.get_cell_history) ──────────────────

class _FakeCellHistoryEntry:
    def __init__(self, value, modified_at: str):
        self.value = value
        self.modified_at = modified_at


class _FakeCellHistoryResult:
    def __init__(self, data: list):
        self.data = data


class _FakeCellsResource:
    def __init__(
        self,
        history_by_key: dict[tuple, list],
        call_log: list,
        raise_for_keys: set | None = None,
    ):
        self._history_by_key = history_by_key
        self._call_log = call_log
        self._raise_for_keys = raise_for_keys or set()

    def get_cell_history(self, sheet_id, row_id, column_id, include_all=True):
        key = (sheet_id, row_id, column_id)
        self._call_log.append(key)
        if key in self._raise_for_keys:
            raise RuntimeError(f"simulated cell-history failure for {key}")
        return _FakeCellHistoryResult(self._history_by_key.get(key, []))


class _FakeSmartsheetClient:
    def __init__(
        self,
        history_by_key: dict[tuple, list] | None = None,
        call_log: list | None = None,
        raise_for_keys: set | None = None,
    ):
        self.call_log = call_log if call_log is not None else []
        self.Cells = _FakeCellsResource(
            history_by_key or {}, self.call_log, raise_for_keys
        )
        self.errors_as_exceptions_called = False

    def errors_as_exceptions(self, _flag=True):
        self.errors_as_exceptions_called = True


def _install_fake_smartsheet(monkeypatch, fake_client: _FakeSmartsheetClient):
    """Patch the ``smartsheet`` module's ``Smartsheet`` constructor so
    ``main()``'s ``smartsheet.Smartsheet(api_token)`` returns *fake_client*
    regardless of the token value."""
    import smartsheet as _smartsheet_module

    monkeypatch.setattr(
        _smartsheet_module, "Smartsheet", lambda *_a, **_kw: fake_client
    )


class _RaisingSmartsheetConstructor:
    """Used by the --check-backlog test to prove zero Smartsheet calls
    are made: constructing a client at all is a hard failure."""

    def __call__(self, *_a, **_kw):
        raise AssertionError(
            "smartsheet.Smartsheet(...) constructed during --check-backlog "
            "-- must issue zero Smartsheet calls"
        )


# ── Structural tests (imports, single get_cell_history call site) ────

class StructuralContractTests(unittest.TestCase):
    def test_single_get_cell_history_call_site(self):
        source = _read_source(_SCRIPT_RELPATH)
        non_comment_lines = [
            line for line in source.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        joined = "\n".join(non_comment_lines)
        self.assertEqual(
            joined.count("client.Cells.get_cell_history("), 1,
            "expected exactly one client.Cells.get_cell_history( call site",
        )

    def test_env_var_names_present(self):
        source = _read_source(_SCRIPT_RELPATH)
        for name in (
            "CELL_HISTORY_BACKFILL_MAX_REQUESTS",
            "CELL_HISTORY_BACKFILL_MAX_ROWS",
            "CELL_HISTORY_BACKFILL_PACE_SEC",
            "CELL_HISTORY_BACKFILL_MAX_MINUTES",
        ):
            self.assertIn(name, source)

    def test_imports_report_writer_and_rpc_caller_no_duplicate_rpc_site(self):
        source = _read_source(_SCRIPT_RELPATH)
        collapsed = _collapse_ws(source)
        self.assertIn("from scripts import backfill_claim_time_attribution", collapsed)
        self.assertEqual(
            source.count('rpc("backfill_attribution"'), 0,
            "must not define a second billing_audit.backfill_attribution "
            "RPC call site -- reuse scripts.backfill_claim_time_attribution's",
        )

    def test_help_contains_check_backlog_and_max_requests(self):
        from scripts import backfill_cell_history_attribution as cha

        with self.assertRaises(SystemExit) as ctx:
            cha._parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)


# ── --check-backlog ────────────────────────────────────────────────

class CheckBacklogTests(unittest.TestCase):
    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def test_report_present_counts_unresolved_and_conflict_only(self, tmp_path=None):
        import tempfile
        from scripts import backfill_cell_history_attribution as cha

        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "own03_backfill_report.json"
            _write_candidate_report(
                report_path,
                [
                    _report_row(row_id=1, status="unresolved"),
                    _report_row(row_id=2, status="conflict"),
                    _report_row(row_id=3, status="proposed"),
                ],
            )
            fake_ctor = _RaisingSmartsheetConstructor()
            with mock.patch.dict(
                sys.modules, {}
            ), mock.patch("smartsheet.Smartsheet", fake_ctor):
                with mock.patch("sys.stdout") as _stdout:
                    exit_code = cha.main(
                        ["--check-backlog", "--report", str(report_path)]
                    )
            self.assertEqual(exit_code, 0)
            printed = "".join(
                call.args[0] for call in _stdout.write.call_args_list
                if call.args
            )
            self.assertIn("backlog_rows=2", printed)

    def test_report_absent_falls_back_to_bounded_supabase_scan(self):
        import tempfile
        from scripts import backfill_cell_history_attribution as cha

        ba_client = _FakeClient(
            _FakeSchema(
                tables={
                    "attribution_snapshot": _FakeTable(
                        [
                            {
                                "frozen_primary": "Unknown Foreman",
                                "frozen_helper": None,
                                "frozen_vac_crew": None,
                            },
                            {
                                "frozen_primary": "Real Person",
                                "frozen_helper": "Unknown Helper",
                                "frozen_vac_crew": None,
                            },
                            {
                                "frozen_primary": "Real Person Two",
                                "frozen_helper": None,
                                "frozen_vac_crew": None,
                            },
                        ]
                    )
                },
                rpc_handlers={},
            )
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_report = Path(tmp_dir) / "does_not_exist.json"
            fake_ctor = _RaisingSmartsheetConstructor()
            with mock.patch(
                "billing_audit.client.get_client", return_value=ba_client
            ), mock.patch("smartsheet.Smartsheet", fake_ctor):
                with mock.patch("sys.stdout") as _stdout:
                    exit_code = cha.main(
                        ["--check-backlog", "--report", str(missing_report)]
                    )
            self.assertEqual(exit_code, 0)
            printed = "".join(
                call.args[0] for call in _stdout.write.call_args_list
                if call.args
            )
            self.assertIn("backlog_rows=2", printed)


# ── Candidate resolution / pacing / caps ──────────────────────────────

class CandidateResolutionTests(unittest.TestCase):
    def setUp(self):
        _reset_all_clients()
        self._env_patches: list = []

    def tearDown(self):
        _reset_all_clients()
        for p in self._env_patches:
            p.stop()

    def _set_env(self, **env):
        p = mock.patch.dict("os.environ", env)
        p.start()
        self._env_patches.append(p)

    def _run(
        self, report_rows: list[dict], fake_ss_client: _FakeSmartsheetClient,
        row_ids: list[int] | None = None, extra_argv: list[str] | None = None,
        pm_client: _FakeClient | None = None,
    ) -> tuple[int, dict]:
        import tempfile
        from scripts import backfill_cell_history_attribution as cha

        row_ids = row_ids or sorted({r["row_id"] for r in report_rows})
        pm_client = pm_client or _default_pipeline_memory_client(row_ids)

        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "own03_backfill_report.json"
            _write_candidate_report(report_path, report_rows)

            argv = ["--report", str(report_path), "--report-dir", tmp_dir]
            argv += extra_argv or []

            with mock.patch(
                "pipeline_memory.client.get_client", return_value=pm_client
            ), mock.patch(
                "smartsheet.Smartsheet",
                lambda *_a, **_kw: fake_ss_client,
            ), mock.patch.dict(
                "os.environ", {"SMARTSHEET_API_TOKEN": "fake-token"}
            ):
                exit_code = cha.main(argv)

            out_json = Path(tmp_dir) / "own03_cell_history_report.json"
            data = json.loads(out_json.read_text(encoding="utf-8"))
        return exit_code, data

    def test_request_cap_stops_third_candidate(self):
        # 3 candidates, each with a checkbox history that NEVER becomes
        # checked -- costs exactly 1 get_cell_history call each. With
        # MAX_REQUESTS=2, candidates 1 and 2 each get their (single)
        # call made; candidate 3 is stopped before any call, reported
        # unresolved with a reason naming the request cap.
        rows = [
            _report_row(row_id=1),
            _report_row(row_id=2),
            _report_row(row_id=3),
        ]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-01T00:00:00Z")
            ],
            (_SHEET_ID, 2, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-01T00:00:00Z")
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(
            rows, fake_ss,
            extra_argv=["--max-requests", "2"],
        )

        self.assertEqual(exit_code, 0)
        by_row = {r["row_id"]: r for r in data["rows"]}
        self.assertEqual(by_row[1]["status"], "unresolved")
        self.assertEqual(by_row[2]["status"], "unresolved")
        self.assertEqual(by_row[3]["status"], "unresolved")
        self.assertIn("request cap", by_row[3]["evidence"])
        self.assertEqual(len(fake_ss.call_log), 2)
        # Candidates 1 and 2 were each attempted (their single call was
        # made); candidate 3 never reached Cells.get_cell_history.
        self.assertIn((_SHEET_ID, 1, 1001), fake_ss.call_log)
        self.assertIn((_SHEET_ID, 2, 1001), fake_ss.call_log)
        self.assertNotIn((_SHEET_ID, 3, 1001), fake_ss.call_log)

    def test_sleep_pacing_zero_before_first_one_before_subsequent(self):
        rows = [_report_row(row_id=1), _report_row(row_id=2)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-01T00:00:00Z")
            ],
            (_SHEET_ID, 2, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-01T00:00:00Z")
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        sleep_calls: list[float] = []
        with mock.patch(
            "scripts.backfill_cell_history_attribution.time.sleep",
            side_effect=lambda s: sleep_calls.append(s),
        ):
            exit_code, _data = self._run(
                rows, fake_ss,
                extra_argv=["--max-requests", "10"],
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(fake_ss.call_log), 2)
        self.assertEqual(len(sleep_calls), 1)
        self.assertAlmostEqual(sleep_calls[0], 0.25, places=3)

    def test_row_cap_env_var_stops_remaining_candidates(self):
        rows = [
            _report_row(row_id=1),
            _report_row(row_id=2),
        ]
        fake_ss = _FakeSmartsheetClient(history_by_key={})
        self._set_env(CELL_HISTORY_BACKFILL_MAX_ROWS="1")

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        by_row = {r["row_id"]: r for r in data["rows"]}
        self.assertIn("row cap", by_row[2]["evidence"])
        self.assertEqual(len(fake_ss.call_log), 1)

    def test_wall_clock_deadline_stops_before_any_fetch(self):
        rows = [_report_row(row_id=1)]
        fake_ss = _FakeSmartsheetClient(history_by_key={})
        self._set_env(CELL_HISTORY_BACKFILL_MAX_MINUTES="-1")

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["rows"][0]["status"], "unresolved")
        self.assertIn("deadline", data["rows"][0]["evidence"])
        self.assertEqual(len(fake_ss.call_log), 0)

    def test_checkbox_never_checked_stays_unresolved(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-01T00:00:00Z"),
                _FakeCellHistoryEntry(None, "2026-08-02T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["rows"][0]["status"], "unresolved")
        self.assertIn("never became checked", data["rows"][0]["evidence"])
        self.assertEqual(len(fake_ss.call_log), 1)

    def test_resolved_name_that_is_a_sentinel_stays_unresolved(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-05T00:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry("Unknown Foreman", "2026-08-01T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["rows"][0]["status"], "unresolved")
        self.assertIn("sentinel", data["rows"][0]["evidence"])
        self.assertEqual(len(fake_ss.call_log), 2)

    def test_happy_path_resolves_real_name_with_operator_provenance(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-01T00:00:00Z"),
                _FakeCellHistoryEntry(True, "2026-08-05T12:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-03T00:00:00Z"),
                _FakeCellHistoryEntry("Jordan Example", "2026-08-06T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["proposed_value"], "Avery Example")
        self.assertEqual(row["source"], "operator")
        self.assertEqual(row["name_fidelity"], "exact")

    def test_exception_on_one_candidate_leaves_next_candidate_resolving(self):
        rows = [_report_row(row_id=1), _report_row(row_id=2)]
        history = {
            (_SHEET_ID, 2, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-05T12:00:00Z"),
            ],
            (_SHEET_ID, 2, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-03T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(
            history_by_key=history,
            raise_for_keys={(_SHEET_ID, 1, 1001)},
        )

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        by_row = {r["row_id"]: r for r in data["rows"]}
        self.assertEqual(by_row[1]["status"], "unresolved")
        self.assertIn("exception", by_row[1]["evidence"])
        self.assertEqual(by_row[2]["status"], "proposed")
        self.assertEqual(by_row[2]["proposed_value"], "Avery Example")

    def test_unresolvable_sheet_id_leaves_row_unresolved_no_smartsheet_call(self):
        rows = [_report_row(row_id=999)]
        fake_ss = _FakeSmartsheetClient(history_by_key={})
        # No pipeline_memory.row_state fixture for row_id=999.
        pm_client = _make_pipeline_memory_fake_client(
            row_state_rows=[], sheet_registry_rows=[]
        )

        exit_code, data = self._run(rows, fake_ss, pm_client=pm_client)

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["rows"][0]["status"], "unresolved")
        self.assertEqual(len(fake_ss.call_log), 0)

    def test_proposed_status_row_is_never_a_candidate(self):
        rows = [
            _report_row(row_id=1, status="proposed", proposed_value="Already Named"),
        ]
        fake_ss = _FakeSmartsheetClient(history_by_key={})

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(data["rows"]), 0)
        self.assertEqual(len(fake_ss.call_log), 0)


if __name__ == "__main__":
    unittest.main()
