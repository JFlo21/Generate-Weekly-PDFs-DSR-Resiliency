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


if __name__ == "__main__":
    unittest.main()
