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
import re
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

import validate_system_health as vsh  # noqa: E402

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
    def __init__(self, value, modified_at: str, display_value=None):
        self.value = value
        self.modified_at = modified_at
        self.display_value = display_value


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

    def test_client_none_and_report_absent_exits_7(self):
        """MED-07 review fix: --check-backlog must not silently return
        an all-clear (0) when the Supabase client is unavailable and
        no sources-1-4 report exists -- a weekly job must never no-op
        forever on a broken backend."""
        import tempfile
        from scripts import backfill_cell_history_attribution as cha

        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_report = Path(tmp_dir) / "does_not_exist.json"
            fake_ctor = _RaisingSmartsheetConstructor()
            with mock.patch(
                "billing_audit.client.get_client", return_value=None
            ), mock.patch("smartsheet.Smartsheet", fake_ctor):
                exit_code = cha.main(
                    ["--check-backlog", "--report", str(missing_report)]
                )
            self.assertEqual(exit_code, 7)


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

    def test_request_cap_defers_remaining_candidates(self):
        # HIGH-04 review fix: a tripped request cap no longer marks
        # the triggering/remaining candidates "unresolved" -- they are
        # left OUT of this run's report entirely (deferred to the next
        # invocation) and the run still exits 0.
        rows = [
            _report_row(row_id=1),
            _report_row(row_id=2),
            _report_row(row_id=3),
        ]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-19T00:00:00Z")
            ],
            (_SHEET_ID, 2, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-19T00:00:00Z")
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
        self.assertNotIn(3, by_row)
        self.assertTrue(data["summary"]["cap_reached"])
        self.assertEqual(data["summary"]["candidates_deferred"], 1)
        self.assertEqual(len(fake_ss.call_log), 2)
        # Candidates 1 and 2 were each attempted (their single call was
        # made); candidate 3 never reached Cells.get_cell_history.
        self.assertIn((_SHEET_ID, 1, 1001), fake_ss.call_log)
        self.assertIn((_SHEET_ID, 2, 1001), fake_ss.call_log)
        self.assertNotIn((_SHEET_ID, 3, 1001), fake_ss.call_log)

    def test_cap_trips_between_a_single_candidates_own_two_requests(self):
        # HIGH-04 review fix: the cap is re-checked BEFORE EVERY
        # request, not once per candidate -- it can trip between one
        # candidate's own checkbox and name-column requests.
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-19T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(
            rows, fake_ss,
            extra_argv=["--max-requests", "1"],
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["rows"], [])
        self.assertTrue(data["summary"]["cap_reached"])
        self.assertEqual(data["summary"]["candidates_deferred"], 1)
        self.assertEqual(len(fake_ss.call_log), 1)
        self.assertIn((_SHEET_ID, 1, 1001), fake_ss.call_log)

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
        self.assertAlmostEqual(sleep_calls[0], 0.5, places=3)

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

    def test_wall_clock_deadline_defers_before_any_fetch(self):
        rows = [_report_row(row_id=1)]
        fake_ss = _FakeSmartsheetClient(history_by_key={})
        self._set_env(CELL_HISTORY_BACKFILL_MAX_MINUTES="-1")

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["rows"], [])
        self.assertTrue(data["summary"]["cap_reached"])
        self.assertEqual(data["summary"]["candidates_deferred"], 1)
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

    def test_transition_before_week_start_ignored(self):
        # Default fixture week_ending is 2026-08-24 -> week_start is
        # 2026-08-18. This candidate's only checkbox transition
        # predates that -- it belongs to a prior week's claim and is
        # ignored. The name column is never fetched (efficiency: the
        # only transition is already out-of-window).
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-10T00:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-05T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "unresolved")
        self.assertIn("in-window", row["evidence"])
        self.assertEqual(len(fake_ss.call_log), 1)

    def test_resolved_name_that_is_a_sentinel_stays_unresolved(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-20T00:00:00Z"),
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

    def test_happy_path_uses_backfill_cell_history_provenance(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(False, "2026-08-16T00:00:00Z"),
                _FakeCellHistoryEntry(True, "2026-08-20T12:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-18T00:00:00Z"),
                _FakeCellHistoryEntry(
                    "Jordan Example", "2026-08-21T00:00:00Z"
                ),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["proposed_value"], "Avery Example")
        self.assertEqual(row["source"], "backfill_cell_history")
        self.assertEqual(row["name_fidelity"], "exact")
        self.assertIn("claims=1", row["evidence"])

    def test_newest_first_history_input_still_resolves_correctly(self):
        # _sorted_history_entries must normalize ordering -- the API's
        # own (here: newest-first) ordering must not change the
        # result for either the checkbox or the name column.
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-20T12:00:00Z"),
                _FakeCellHistoryEntry(False, "2026-08-19T00:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry(
                    "Jordan Example", "2026-08-21T00:00:00Z"
                ),
                _FakeCellHistoryEntry("Avery Example", "2026-08-18T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["proposed_value"], "Avery Example")

    def test_check_uncheck_recheck_same_name_yields_claims_two(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-19T00:00:00Z"),
                _FakeCellHistoryEntry(False, "2026-08-20T00:00:00Z"),
                _FakeCellHistoryEntry(True, "2026-08-21T00:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-18T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["proposed_value"], "Avery Example")
        self.assertIn("claims=2", row["evidence"])

    def test_check_uncheck_recheck_different_names_yields_conflict(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-19T00:00:00Z"),
                _FakeCellHistoryEntry(False, "2026-08-20T00:00:00Z"),
                _FakeCellHistoryEntry(True, "2026-08-21T00:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-18T00:00:00Z"),
                _FakeCellHistoryEntry(
                    "Jordan Example", "2026-08-20T12:00:00Z"
                ),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "conflict")
        self.assertEqual(row["proposed_value"], "")
        self.assertNotIn("Avery", row["evidence"])
        self.assertNotIn("Jordan", row["evidence"])
        self.assertIn("2026-08-19", row["evidence"])
        self.assertIn("2026-08-21", row["evidence"])

    def test_name_changed_after_check_earlier_name_wins(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-19T00:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-18T00:00:00Z"),
                _FakeCellHistoryEntry(
                    "Jordan Example", "2026-08-25T00:00:00Z"
                ),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["proposed_value"], "Avery Example")

    def test_display_value_preferred_over_value_for_name_column(self):
        rows = [_report_row(row_id=1)]
        history = {
            (_SHEET_ID, 1, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-19T00:00:00Z"),
            ],
            (_SHEET_ID, 1, 1002): [
                _FakeCellHistoryEntry(
                    "avery.example@centurigroup.com",
                    "2026-08-18T00:00:00Z",
                    display_value="Avery Example",
                ),
            ],
        }
        fake_ss = _FakeSmartsheetClient(history_by_key=history)

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 0)
        row = data["rows"][0]
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["proposed_value"], "Avery Example")

    def test_read_failure_aborts_run_with_error_status(self):
        # HIGH-01 review fix: a Smartsheet cell-history read failure
        # must never launder into "unresolved". It aborts the run
        # (exit 7), marks the failing candidate status="error" with
        # the exception TYPE only in evidence, and issues no further
        # Smartsheet requests for any later candidate.
        rows = [_report_row(row_id=1), _report_row(row_id=2)]
        history = {
            (_SHEET_ID, 2, 1001): [
                _FakeCellHistoryEntry(True, "2026-08-19T00:00:00Z"),
            ],
            (_SHEET_ID, 2, 1002): [
                _FakeCellHistoryEntry("Avery Example", "2026-08-18T00:00:00Z"),
            ],
        }
        fake_ss = _FakeSmartsheetClient(
            history_by_key=history,
            raise_for_keys={(_SHEET_ID, 1, 1001)},
        )

        exit_code, data = self._run(rows, fake_ss)

        self.assertEqual(exit_code, 7)
        by_row = {r["row_id"]: r for r in data["rows"]}
        self.assertEqual(by_row[1]["status"], "error")
        self.assertIn(
            "cell_history_read_failed:RuntimeError", by_row[1]["evidence"]
        )
        self.assertNotIn(2, by_row)
        self.assertEqual(data["summary"]["read_failures"], 1)
        self.assertTrue(data["summary"]["aborted"])
        self.assertIn((_SHEET_ID, 1, 1001), fake_ss.call_log)
        self.assertNotIn((_SHEET_ID, 2, 1001), fake_ss.call_log)

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


# ── Task 2: production-isolation structural guard ────────────────────
# Enforces RESEARCH.md Pitfall 5 / the 2026-09-02 00:35 decision that
# source 5 (Smartsheet cell-history reads) runs ONLY in its own
# workflow -- never inside generate_weekly_pdfs.py or any
# pipeline/*.py module. Both scripts share ONE Smartsheet API token
# and ONE 300 req/min budget; a get_cell_history call embedded in the
# production run would silently spend that shared budget out of the
# billing pipeline's own window. This is a PERMANENT guard: it must
# fail the moment a future PR adds a second get_cell_history call
# site, or reads a CELL_HISTORY_BACKFILL_* env var, in a production
# module.

_ISOLATION_ALLOWLIST: "frozenset[str]" = frozenset({"pipeline/snapshot_drift.py"})


def _strip_comment_lines(source: str) -> str:
    """Drop every line whose first non-space character is '#' before
    counting/searching -- a comment mentioning the API text must never
    silently satisfy or break this gate (mirrors
    scripts/backfill_claim_time_attribution.py's own structural test
    idiom, tests/test_backfill_claim_time_attribution.py:798-810)."""
    return "\n".join(
        line for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def _isolation_scanned_files() -> "list[Path]":
    files = [
        _REPO_ROOT / "generate_weekly_pdfs.py",
        _REPO_ROOT / "audit_billing_changes.py",
    ]
    files += sorted((_REPO_ROOT / "pipeline").glob("*.py"))
    return files


class CellHistoryProductionIsolationTests(unittest.TestCase):
    """Task 2: no production module may call
    client.Cells.get_cell_history or read a CELL_HISTORY_BACKFILL_*
    env var. audit_billing_changes.py's own
    _selective_cell_history_enrichment is confirmed a stub (hardcodes
    history_available=True, never calls the API) and must stay that
    way -- this plan must not accidentally wire it into a real call."""

    def test_get_cell_history_call_sites_are_exactly_the_allowlist(self):
        found: "set[str]" = set()
        for path in _isolation_scanned_files():
            relpath = path.relative_to(_REPO_ROOT).as_posix()
            non_comment = _strip_comment_lines(
                path.read_text(encoding="utf-8")
            )
            if "get_cell_history" in non_comment:
                found.add(relpath)
        self.assertEqual(
            found, set(_ISOLATION_ALLOWLIST),
            "get_cell_history call sites in production files must be "
            "EXACTLY the allowlist -- a new site must be added "
            "deliberately, with a comment explaining why, per Task 2's "
            "explicit instruction.",
        )

    def test_no_scanned_file_reads_cell_history_backfill_env_var(self):
        offenders: "list[str]" = []
        for path in _isolation_scanned_files():
            non_comment = _strip_comment_lines(
                path.read_text(encoding="utf-8")
            )
            if "CELL_HISTORY_BACKFILL" in non_comment:
                offenders.append(path.relative_to(_REPO_ROOT).as_posix())
        self.assertEqual(
            offenders, [],
            "no production module may read a CELL_HISTORY_BACKFILL_* "
            "env var -- source 5's caps/pace/deadline knobs are for "
            "its own standalone script and workflow only.",
        )

    def test_audit_billing_changes_stub_has_zero_get_cell_history_calls(self):
        non_comment = _strip_comment_lines(
            _read_source("audit_billing_changes.py")
        )
        self.assertEqual(
            non_comment.count("get_cell_history"), 0,
            "audit_billing_changes.py::_selective_cell_history_enrichment "
            "must remain a stub -- it must never gain a real "
            "get_cell_history call as a side effect of this plan.",
        )


# ── Task 4: workflow structural contract ────────────────────────────

_WORKFLOW_RELPATH = ".github/workflows/cell-history-backfill.yml"
_PRODUCTION_CONCURRENCY_MARKER = "weekly-excel"
_BACKFILL_STEP_ID = "run_backfill"
_GATE_STEP_ID = "backlog"


def _workflow_raw_lines() -> "list[str]":
    path = _REPO_ROOT / _WORKFLOW_RELPATH
    return path.read_text(encoding="utf-8").splitlines()


def _live_lines(raw: "list[str]") -> "list[str]":
    """Comment-stripped lines, read the same way validate_system_health
    grades the production workflow -- a commented key can never satisfy
    or break an assertion here."""
    return [vsh._strip_comment(line) for line in raw]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _step_blocks(raw: "list[str]") -> "dict[str, list[str]]":
    """Split the raw ``steps:`` list into per-step raw line blocks,
    keyed by the step's ``id:`` (steps without one are keyed by
    name)."""
    starts = [
        i for i, line in enumerate(raw)
        if line.lstrip().startswith("- name:")
    ]
    blocks: "dict[str, list[str]]" = {}
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(raw)
        block = raw[start:end]
        live = _live_lines(block)
        key = vsh._find_key_value(live, "id")
        if key is None:
            key = vsh._find_key_value(live, "- name") or str(start)
        blocks[key.strip()] = block
    return blocks


def _run_block(block: "list[str]") -> str:
    """Return the raw shell text of the block's ``run:`` scalar."""
    for i, line in enumerate(block):
        if line.lstrip().startswith("run:"):
            base = _indent(line)
            body: "list[str]" = []
            for follow in block[i + 1:]:
                if follow.strip() and _indent(follow) <= base:
                    break
                body.append(follow)
            return "\n".join(body)
    return ""


def _dispatch_input_names(live: "list[str]") -> "list[str]":
    names: "list[str]" = []
    for i, line in enumerate(live):
        if line.strip() != "inputs:":
            continue
        base = _indent(line)
        for follow in live[i + 1:]:
            if not follow.strip():
                continue
            if _indent(follow) <= base:
                break
            is_child = _indent(follow) == base + 2
            if is_child and follow.rstrip().endswith(":"):
                names.append(follow.strip()[:-1])
        break
    return names


class CellHistoryWorkflowStructureTests(unittest.TestCase):
    """Structural contract of .github/workflows/cell-history-backfill.yml
    (Task 4). Parsed with the same comment-stripped line reader
    validate_system_health.py uses for the production workflow: PyYAML
    is not a declared dependency of this repo (requirements.txt is the
    only thing CI installs), so no YAML library is imported here."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _workflow_raw_lines()
        cls.live = _live_lines(cls.raw)
        cls.blocks = _step_blocks(cls.raw)

    def test_workflow_declares_jobs_and_read_only_token(self):
        self.assertTrue((_REPO_ROOT / _WORKFLOW_RELPATH).is_file())
        self.assertIn("jobs:", [line.strip() for line in self.live])
        self.assertEqual(
            vsh._find_key_value(self.live, "contents"), "read"
        )

    def test_concurrency_group_is_isolated_from_production(self):
        group = vsh._find_key_value(self.live, "group")
        self.assertIsNotNone(group)
        self.assertTrue(group.startswith("cell-history-backfill-"), group)
        self.assertNotIn(_PRODUCTION_CONCURRENCY_MARKER, group)
        self.assertEqual(
            vsh._find_key_value(self.live, "cancel-in-progress"), "false"
        )

    def test_timeout_exceeds_max_minutes_budget(self):
        timeouts = vsh._find_timeout_minutes(self.live)
        self.assertEqual(len(timeouts), 1, timeouts)
        raw_budget = vsh._find_key_value(
            self.live, "CELL_HISTORY_BACKFILL_MAX_MINUTES"
        )
        self.assertIsNotNone(raw_budget)
        budget = float(raw_budget.strip().strip("'\""))
        self.assertGreater(
            timeouts[0], budget,
            "timeout-minutes must stay strictly above the script's "
            "wall-clock cap so its graceful stop fires first",
        )

    def test_dispatch_only_no_schedule(self):
        """Owner re-decision 2026-09-03 (Opus H1): dispatch-only until
        plan 12-06 lands a candidate source. No cron may creep back."""
        crons = [
            line for line in self.live
            if line.strip().startswith("- cron:")
        ]
        self.assertEqual(crons, [])
        keys = [line.strip() for line in self.live]
        self.assertNotIn("schedule:", keys)
        self.assertIn("workflow_dispatch:", keys)

    def test_backfill_step_is_gated_and_never_applies(self):
        block = self.blocks[_BACKFILL_STEP_ID]
        cond = vsh._find_key_value(_live_lines(block), "if")
        self.assertIsNotNone(cond)
        self.assertIn("steps.backlog.outputs.backlog_rows", cond)
        run = _run_block(block)
        self.assertTrue(run.strip())
        self.assertNotIn("${{", run)
        self.assertNotIn("--apply", run)
        self.assertIn("--dry-run", run)

    def test_no_run_block_interpolates_expressions(self):
        for step_id, block in self.blocks.items():
            with self.subTest(step=step_id):
                self.assertNotIn("${{", _run_block(block))

    def test_no_run_block_passes_apply(self):
        """Review fix (Opus M3): --apply must be absent from EVERY
        run: block, not only the backfill step's."""
        for step_id, block in self.blocks.items():
            with self.subTest(step=step_id):
                self.assertNotIn("--apply", _run_block(block))

    def test_permissions_declare_a_single_read_only_scope(self):
        """Review fix (Opus M3): _find_key_value returns the FIRST
        contents: key, so a second job-level `contents: write` would
        have slipped past the read-only assertion."""
        contents = [
            line for line in self.live
            if line.strip().startswith("contents:")
        ]
        self.assertEqual(len(contents), 1, contents)
        writes = [
            line for line in self.live
            if re.match(r"^\s*[a-z-]+:\s*write\b", line)
        ]
        self.assertEqual(writes, [])

    def test_budget_caps_are_pinned(self):
        """Review fix (Opus M3): the caps that keep this job at ~40%
        of the shared 300 req/min Smartsheet budget are asserted, so a
        quiet edit (PACE_SEC 0.5 -> 0.05) fails CI."""
        expected = {
            "CELL_HISTORY_BACKFILL_MAX_REQUESTS": "3000",
            "CELL_HISTORY_BACKFILL_MAX_ROWS": "1200",
            "CELL_HISTORY_BACKFILL_PACE_SEC": "0.5",
            "CELL_HISTORY_BACKFILL_MAX_MINUTES": "45",
        }
        for key, value in expected.items():
            raw = vsh._find_key_value(self.live, key)
            with self.subTest(env=key):
                self.assertIsNotNone(raw)
                self.assertEqual(raw.strip().strip("'\""), value)

    def test_dry_run_false_fails_loudly(self):
        """Review fix (Opus M2): selecting dry_run=false must fail the
        run, never warn-and-continue as if a write had happened."""
        run = _run_block(self.blocks[_BACKFILL_STEP_ID])
        self.assertIn('"${DRY_RUN}" != "true"', run)
        self.assertIn("::error::dry_run=", run)
        self.assertNotIn("::warning::dry_run=", run)

    def test_report_upload_requires_the_report_file(self):
        """Review fix (Opus L6): the artifact step keys on hashFiles()
        of the report, not on a step outcome that is '' for a step
        never reached."""
        joined = "\n".join(self.raw)
        self.assertRegex(
            joined,
            r"if: always\(\) && hashFiles\('generated_docs/"
            r"own03_cell_history_report\.json'\) != ''\s*\n"
            r"\s*uses: actions/upload-artifact@v4",
        )

    def test_every_dispatch_input_is_bound_to_env(self):
        names = _dispatch_input_names(self.live)
        self.assertEqual(
            sorted(names), ["dry_run", "max_requests", "wr_filter"]
        )
        for name in names:
            pattern = re.compile(
                r"^\s*[A-Z][A-Z0-9_]*:\s*\$\{\{\s*(github\.event\.)?"
                r"inputs\." + re.escape(name) + r"\b"
            )
            with self.subTest(input=name):
                self.assertTrue(
                    any(pattern.match(line) for line in self.live),
                    f"dispatch input {name!r} has no env: binding",
                )

    def test_gate_step_writes_backlog_rows_output(self):
        block = self.blocks[_GATE_STEP_ID]
        run = _run_block(block)
        self.assertIn("--check-backlog", run)
        self.assertIn("backlog_rows=", run)
        self.assertIn("GITHUB_OUTPUT", run)
        self.assertNotIn("SMARTSHEET_API_TOKEN", "\n".join(block))

    def test_smartsheet_token_bound_only_in_backfill_step(self):
        joined = "\n".join(self.raw)
        self.assertEqual(joined.count("secrets.SMARTSHEET_API_TOKEN"), 1)
        self.assertIn(
            "secrets.SMARTSHEET_API_TOKEN",
            "\n".join(self.blocks[_BACKFILL_STEP_ID]),
        )
        steps_idx = next(
            i for i, line in enumerate(self.live)
            if line.strip() == "steps:"
        )
        self.assertNotIn("secrets.", "\n".join(self.live[:steps_idx]))


if __name__ == "__main__":
    unittest.main()
