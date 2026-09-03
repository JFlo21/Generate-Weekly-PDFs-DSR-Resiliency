"""Fixture-driven tests for scripts/backfill_claim_time_attribution.py
(OWN-03, Phase 12).

No live Supabase or Smartsheet access. Every Supabase call is served by
small, FILTER-AWARE fake client objects defined in this module (the
existing ``_make_fake_supabase_client`` helper in
``tests/test_billing_audit_shadow.py`` is tailored to that module's own
feature_flag / pipeline_run domain and does not honor arbitrary
``.eq()``/``.in_()`` filters against a fixture row set -- this script's
negative/scoping tests, e.g. Task 2's no-cross-week-lookup assertions,
need filtering that is actually respected, so a dedicated minimal fake
is built here instead. ``_reset_all`` IS reused from
tests/test_billing_audit_shadow.py, since it correctly clears both the
billing_audit client cache and writer counters between tests).

Names are fictional -- public-repo rule. The WR number (19073866) and
the four week_ending_fmt tokens (082425, 083125, 091425, 092125) match
the plan's own known-good sample identifiers.
"""

from __future__ import annotations

import datetime
import json
import sys
import tempfile
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

_SCRIPT_RELPATH = "scripts/backfill_claim_time_attribution.py"

# ── Known-good sample fixture (module-level constants, mirrors
# tests/test_sentinel_superseded_cleanup.py's style) ─────────────────
_WR = "19073866"
_WEEK_TOKENS: tuple[str, ...] = ("082425", "083125", "091425", "092125")
_ROW_IDS: dict[str, int] = {
    "082425": 700001,
    "083125": 700002,
    "091425": 700003,
    "092125": 700004,
}
_PRE_DEFECT_UPDATED_AT = "2026-07-15T00:00:00+00:00"


def _token_to_date(token: str) -> datetime.date:
    month = int(token[0:2])
    day = int(token[2:4])
    year = 2000 + int(token[4:6])
    return datetime.date(year, month, day)


def _attribution_row(token: str, primary_value: str = "Unknown Foreman") -> dict:
    """One lookup_attribution_bulk RPC response row: a sentinel-frozen
    primary role, no helper/vac_crew yet."""
    return {
        "wr": _WR,
        "week_ending": _token_to_date(token).isoformat(),
        "smartsheet_row_id": _ROW_IDS[token],
        "primary_foreman": primary_value,
        "helper": None,
        "helper_dept": None,
        "vac_crew": None,
        "source_run_id": "prior-run",
    }


def _gch_row(
    token: str, identifier: str = "Avery_Example",
    variant: str = "primary", updated_at: str = _PRE_DEFECT_UPDATED_AT,
) -> dict:
    """One billing_audit.group_content_hash row."""
    return {
        "wr": _WR,
        "week_ending": _token_to_date(token).isoformat(),
        "variant": variant,
        "identifier": identifier,
        "updated_at": updated_at,
    }


def _gs_row(
    token: str, identifier: str = "Avery_Example",
    variant: str = "primary", updated_at: str = _PRE_DEFECT_UPDATED_AT,
) -> dict:
    """One pipeline_memory.group_state row (same shape as group_content_hash
    for this script's purposes)."""
    return {
        "wr": _WR,
        "week_ending": _token_to_date(token).isoformat(),
        "variant": variant,
        "identifier": identifier,
        "updated_at": updated_at,
    }


# ── Filter-aware fake Supabase client ─────────────────────────────────
# Deliberately small and self-contained. Unlike a Mock() with hardcoded
# return values, .eq()/.in_() calls here ACTUALLY narrow the row set,
# so a script bug that forgets to filter by week_ending (a cross-week
# leak) shows up as a wrong test result instead of being masked by an
# unconditional mock return.

class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = list(rows)
        self._filters: list[tuple] = []

    def select(self, *_a, **_kw):
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, str(value)))
        return self

    def in_(self, key, values):
        self._filters.append(("in", key, {str(v) for v in values}))
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def _matches(self, row: dict) -> bool:
        for kind, key, value in self._filters:
            if kind == "eq":
                if str(row.get(key)) != value:
                    return False
            elif kind == "in":
                if str(row.get(key)) not in value:
                    return False
        return True

    def execute(self):
        matched = [r for r in self._rows if self._matches(r)]
        resp = mock.Mock()
        resp.data = matched
        return resp


class _RaisingWrite:
    """Any write-shaped call on a fake table raises -- a script bug that
    attempts a mutating call during a dry run fails loudly instead of
    silently succeeding against an unconfigured mock."""

    def __call__(self, *_a, **_kw):
        raise AssertionError(
            "write attempted against a dry-run fake Supabase client "
            f"({self._name})"
        )

    def __init__(self, name: str):
        self._name = name


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.insert = _RaisingWrite("insert")
        self.update = _RaisingWrite("update")
        self.upsert = _RaisingWrite("upsert")
        self.delete = _RaisingWrite("delete")

    def select(self, *a, **kw):
        return _FakeQuery(self._rows).select(*a, **kw)


class _FakeRpcCall:
    def __init__(self, data):
        self._data = data

    def execute(self):
        resp = mock.Mock()
        resp.data = self._data
        return resp


class _FakeSchema:
    def __init__(self, tables: dict, rpc_handlers: dict):
        self._tables = tables
        self._rpc_handlers = rpc_handlers
        self.rpc_calls: list[tuple[str, dict]] = []

    def table(self, name: str):
        return self._tables.get(name, _FakeTable([]))

    def rpc(self, name: str, params: dict):
        self.rpc_calls.append((name, params))
        handler = self._rpc_handlers.get(name)
        if handler is None:
            raise AssertionError(
                f"unexpected RPC call in dry-run fixture: {name!r}"
            )
        return _FakeRpcCall(handler(params))


class _FakeClient:
    def __init__(self, schema_obj: _FakeSchema):
        self._schema_obj = schema_obj

    def schema(self, _name: str):
        return self._schema_obj


def _make_billing_audit_fake_client(
    rpc_rows: list[dict], group_content_hash_rows: list[dict]
) -> _FakeClient:
    schema_obj = _FakeSchema(
        tables={"group_content_hash": _FakeTable(group_content_hash_rows)},
        rpc_handlers={"lookup_attribution_bulk": lambda _params: rpc_rows},
    )
    return _FakeClient(schema_obj)


def _make_pipeline_memory_fake_client(group_state_rows: list[dict]) -> _FakeClient:
    schema_obj = _FakeSchema(
        tables={"group_state": _FakeTable(group_state_rows)},
        rpc_handlers={},
    )
    return _FakeClient(schema_obj)


def _reset_all_clients() -> None:
    _reset_all()
    from pipeline_memory import client as pm_client
    pm_client.reset_cache_for_tests()


class KnownGoodSampleDryRunTests(unittest.TestCase):
    """End-to-end: CLI -> sentinel discovery -> source 4 -> report, for
    the WR 19073866 known-good sample, across all four weeks."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def _run_dry_run(
        self, tmp_dir: str, rpc_rows=None, gch_rows=None, gs_rows=None,
        roles: str = "primary",
    ):
        from scripts import backfill_claim_time_attribution as bf

        rpc_rows = (
            [_attribution_row(t) for t in _WEEK_TOKENS]
            if rpc_rows is None else rpc_rows
        )
        gch_rows = (
            [_gch_row(t) for t in _WEEK_TOKENS] if gch_rows is None else gch_rows
        )
        gs_rows = [] if gs_rows is None else gs_rows

        ba_client = _make_billing_audit_fake_client(rpc_rows, gch_rows)
        pm_client = _make_pipeline_memory_fake_client(gs_rows)

        with mock.patch(
            "billing_audit.writer.get_client", return_value=ba_client
        ), mock.patch(
            "billing_audit.client.get_client", return_value=ba_client
        ), mock.patch(
            "pipeline_memory.client.get_client", return_value=pm_client
        ):
            argv = [
                "--wr", _WR,
                "--weeks", ",".join(_WEEK_TOKENS),
                "--roles", roles,
                "--report-dir", tmp_dir,
            ]
            exit_code = bf.main(argv)
        return exit_code, ba_client

    def test_resolves_all_four_weeks_via_source_4(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, ba_client = self._run_dry_run(tmp_dir)
            self.assertEqual(exit_code, 0)

            json_path = Path(tmp_dir) / "own03_backfill_report.json"
            csv_path = Path(tmp_dir) / "own03_backfill_report.csv"
            self.assertTrue(json_path.exists(), "JSON report must be written")
            self.assertTrue(csv_path.exists(), "CSV report must be written")

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            rows = payload["rows"]
            self.assertEqual(len(rows), len(_WEEK_TOKENS))

            for token in _WEEK_TOKENS:
                row = next(
                    r for r in rows
                    if r["week_ending_fmt"] == token and r["role"] == "primary"
                )
                self.assertEqual(row["wr"], _WR)
                self.assertEqual(row["proposed_value"], "Avery Example")
                self.assertEqual(row["source"], "backfill_hash_history")
                self.assertEqual(row["name_fidelity"], "desanitized")
                self.assertEqual(row["status"], "proposed")

            # Zero Supabase writes: only the read-only lookup_attribution_bulk
            # RPC was invoked; no other RPC (e.g. a future backfill_attribution
            # apply call) fired.
            rpc_names = {name for name, _params in ba_client._schema_obj.rpc_calls}
            self.assertEqual(rpc_names, {"lookup_attribution_bulk"})

    def test_csv_report_has_expected_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_dry_run(tmp_dir)
            self.assertEqual(exit_code, 0)
            csv_path = Path(tmp_dir) / "own03_backfill_report.csv"
            header = csv_path.read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(
                header,
                "wr,week_ending,week_ending_fmt,row_id,role,current_value,"
                "proposed_value,source,name_fidelity,status,evidence",
            )

    def test_json_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_dry_run(tmp_dir)
            self.assertEqual(exit_code, 0)
            json_path = Path(tmp_dir) / "own03_backfill_report.json"
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            summary = payload["summary"]
            self.assertEqual(summary["total_rows"], len(_WEEK_TOKENS))
            self.assertEqual(
                summary["rows_by_source"], {"backfill_hash_history": 4}
            )
            self.assertEqual(summary["rows_by_status"], {"proposed": 4})
            self.assertIn("run_id", summary)

    def test_unresolvable_row_reports_unresolved_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_dry_run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[],  # no source-4 candidate at all
                gs_rows=[],
            )
            self.assertEqual(exit_code, 0)
            json_path = Path(tmp_dir) / "own03_backfill_report.json"
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            rows = payload["rows"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "unresolved")
            self.assertEqual(rows[0]["proposed_value"], "")

    def test_group_state_alone_also_resolves(self):
        """Source 4 merges group_content_hash AND group_state -- a name
        that only exists in pipeline_memory.group_state must still
        resolve."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_dry_run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[],
                gs_rows=[_gs_row("082425")],
            )
            self.assertEqual(exit_code, 0)
            json_path = Path(tmp_dir) / "own03_backfill_report.json"
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            row = payload["rows"][0]
            self.assertEqual(row["proposed_value"], "Avery Example")
            self.assertEqual(row["source"], "backfill_hash_history")

    def test_two_names_in_source_4_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_dry_run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[
                    _gch_row("082425", identifier="Avery_Example"),
                    _gch_row("082425", identifier="Pat_Example"),
                ],
                gs_rows=[],
            )
            self.assertEqual(exit_code, 0)
            json_path = Path(tmp_dir) / "own03_backfill_report.json"
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            row = payload["rows"][0]
            self.assertEqual(row["status"], "conflict")
            self.assertEqual(row["proposed_value"], "")

    def test_default_roles_scope_covers_all_three_roles(self):
        """A row with no helper/vac_crew observation at all still has
        None for those columns, which satisfies is_sentinel_claimer --
        the default --roles (all three) surfaces them as unresolved
        candidates rather than silently dropping them."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_dry_run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                gs_rows=[],
                roles="primary,helper,vac_crew",
            )
            self.assertEqual(exit_code, 0)
            json_path = Path(tmp_dir) / "own03_backfill_report.json"
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            rows = payload["rows"]
            self.assertEqual(len(rows), 3)
            by_role = {r["role"]: r for r in rows}
            self.assertEqual(by_role["primary"]["status"], "proposed")
            self.assertEqual(by_role["helper"]["status"], "unresolved")
            self.assertEqual(by_role["vac_crew"]["status"], "unresolved")

    def test_report_is_deterministic_across_two_runs(self):
        with tempfile.TemporaryDirectory() as tmp_dir_a, \
                tempfile.TemporaryDirectory() as tmp_dir_b:
            exit_a, _c1 = self._run_dry_run(tmp_dir_a)
            _reset_all_clients()
            exit_b, _c2 = self._run_dry_run(tmp_dir_b)
            self.assertEqual(exit_a, 0)
            self.assertEqual(exit_b, 0)
            json_a = (Path(tmp_dir_a) / "own03_backfill_report.json").read_text(
                encoding="utf-8"
            )
            json_b = (Path(tmp_dir_b) / "own03_backfill_report.json").read_text(
                encoding="utf-8"
            )
            self.assertEqual(json_a, json_b)


class ScopeRequiredTests(unittest.TestCase):
    """--wr and --weeks are both effectively required -- documented
    limitation, not a silent no-op."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def test_missing_wr_and_weeks_exits_8(self):
        from scripts import backfill_claim_time_attribution as bf

        ba_client = _make_billing_audit_fake_client([], [])
        with mock.patch(
            "billing_audit.client.get_client", return_value=ba_client
        ):
            self.assertEqual(bf.main([]), 8)

    def test_missing_client_exits_2(self):
        from scripts import backfill_claim_time_attribution as bf

        with mock.patch("billing_audit.client.get_client", return_value=None):
            self.assertEqual(
                bf.main(["--wr", _WR, "--weeks", "082425"]), 2
            )


class SourceStubTests(unittest.TestCase):
    """Sources 1-3 are declared but return no candidates in this task --
    Task 2 of this plan fills in their bodies."""

    def test_sources_one_two_three_are_silent_stubs(self):
        from scripts import backfill_claim_time_attribution as bf

        target = bf.SentinelTarget(
            wr=_WR,
            week_ending=_token_to_date("082425"),
            week_ending_fmt="082425",
            row_id=700001,
            role="primary",
            current_value="Unknown Foreman",
        )
        cache: dict = {}
        self.assertIsNone(bf.resolve_source_1(target, cache))
        self.assertIsNone(bf.resolve_source_2(target, cache))
        self.assertIsNone(bf.resolve_source_3(target, cache))


class CliHelpTests(unittest.TestCase):
    def test_help_lists_i_approved_this_and_sources(self):
        from scripts import backfill_claim_time_attribution as bf
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ctx:
                bf._parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        help_text = buf.getvalue()
        self.assertIn("--i-approved-this", help_text)
        self.assertIn("--sources", help_text)

    def test_sources_five_is_rejected(self):
        from scripts import backfill_claim_time_attribution as bf
        import argparse

        with self.assertRaises(argparse.ArgumentTypeError):
            bf._parse_sources_csv("5")

    def test_sources_five_mixed_with_valid_is_rejected(self):
        from scripts import backfill_claim_time_attribution as bf
        import argparse

        with self.assertRaises(argparse.ArgumentTypeError):
            bf._parse_sources_csv("1,5")


class StructuralContractTests(unittest.TestCase):
    """Grep-level assertions on the script source, mirroring
    tests/test_billing_audit_shadow.py's _read_source/_collapse_ws idiom
    (used throughout that file for CLI/import-shape contracts)."""

    def test_resolve_source_4_is_defined(self):
        src = _read_source(_SCRIPT_RELPATH)
        self.assertIn("def resolve_source_4(", src)

    def test_imports_is_sentinel_claimer_and_does_not_redefine_it(self):
        src = _read_source(_SCRIPT_RELPATH)
        collapsed = _collapse_ws(src)
        self.assertRegex(
            collapsed,
            r"from\s+billing_audit\.writer\s+import\s+is_sentinel_claimer",
        )
        # No local re-implementation of the sentinel predicate.
        self.assertNotIn("def is_sentinel_claimer(", src)

    def test_never_reads_attribution_snapshot_table_directly(self):
        src = _read_source(_SCRIPT_RELPATH)
        self.assertNotIn('table("attribution_snapshot")', src)
        self.assertNotIn("table('attribution_snapshot')", src)
