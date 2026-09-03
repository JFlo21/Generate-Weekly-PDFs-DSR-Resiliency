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


# ── Task 2 fixtures: row_event / row_state (source 1) and
# public.artifacts (source 3) ─────────────────────────────────────────

def _row_event(
    row_id: int, observed_at: str,
    units_completed: bool | None = None, foreman_observed: str | None = None,
    helper_completed: bool | None = None, helper_observed: str | None = None,
    vac_completed: bool | None = None, vac_crew_observed: str | None = None,
) -> dict:
    """One pipeline_memory.row_event row -- only the fields explicitly
    passed are present in after_image, mirroring a real event whose
    JSONB payload only ever carries the columns that changed."""
    after_image: dict = {}
    if units_completed is not None:
        after_image["units_completed"] = units_completed
    if foreman_observed is not None:
        after_image["foreman_observed"] = foreman_observed
    if helper_completed is not None:
        after_image["helper_completed"] = helper_completed
    if helper_observed is not None:
        after_image["helper_observed"] = helper_observed
    if vac_completed is not None:
        after_image["vac_completed"] = vac_completed
    if vac_crew_observed is not None:
        after_image["vac_crew_observed"] = vac_crew_observed
    return {"row_id": row_id, "observed_at": observed_at, "after_image": after_image}


def _row_state(row_id: int, row_modified_at: str, **fields) -> dict:
    """One pipeline_memory.row_state row."""
    row = {"row_id": row_id, "row_modified_at": row_modified_at}
    row.update(fields)
    return row


def _artifact_row(
    token: str, filename: str, variant: str = "primary",
) -> dict:
    """One public.artifacts row."""
    return {
        "work_request": _WR,
        "week_ending": _token_to_date(token).isoformat(),
        "week_ending_fmt": token,
        "variant": variant,
        "filename": filename,
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
        self._order_key: str | None = None
        self._order_desc: bool = False

    def select(self, *_a, **_kw):
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, str(value)))
        return self

    def in_(self, key, values):
        self._filters.append(("in", key, {str(v) for v in values}))
        return self

    def order(self, column, desc: bool = False, **_kw):
        self._order_key = column
        self._order_desc = desc
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
        if self._order_key is not None:
            key = self._order_key
            matched = sorted(
                matched,
                key=lambda r: (r.get(key) is None, r.get(key)),
                reverse=self._order_desc,
            )
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


try:
    from postgrest import APIError as _POSTGREST_API_ERROR_CLS  # type: ignore
except Exception:
    _POSTGREST_API_ERROR_CLS = None  # type: ignore[assignment]


def _make_api_error(code: str, message: str = "") -> Exception:
    """Build a real ``postgrest.APIError`` the same way postgrest-py does
    when unwrapping a JSON error body -- mirrors
    ``tests/test_billing_audit_shadow.py::PostgrestErrorClassificationTests
    ._make_api_error``. Callers needing this MUST be skip-gated on
    ``_POSTGREST_API_ERROR_CLS is None`` at the test/class level."""
    return _POSTGREST_API_ERROR_CLS(
        {"code": code, "message": message, "hint": "", "details": ""}
    )


class _RaisingTable:
    """A fake table whose ``.select(...)`` chain raises *exc* on
    ``.execute()`` -- simulates a missing relation (e.g. PGRST205) or a
    connectivity error for the Task 3 backup-table probe."""

    def __init__(self, exc: Exception):
        self._exc = exc
        self.insert = _RaisingWrite("insert")
        self.update = _RaisingWrite("update")
        self.upsert = _RaisingWrite("upsert")
        self.delete = _RaisingWrite("delete")

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def execute(self):
        raise self._exc


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.insert = _RaisingWrite("insert")
        self.update = _RaisingWrite("update")
        self.upsert = _RaisingWrite("upsert")
        self.delete = _RaisingWrite("delete")
        # Incremented on every .select(...) call -- one query issued
        # per call. Used by the batched-reads tests to assert the
        # script never issues one query per row_id.
        self.select_calls = 0

    def select(self, *a, **kw):
        self.select_calls += 1
        return _FakeQuery(self._rows).select(*a, **kw)


class _FakeQueryIgnoreOrder(_FakeQuery):
    """Same filtering/eq/in_ behavior as ``_FakeQuery`` but ``.order()``
    is a no-op -- simulates a server that does not guarantee row order
    for tied sort-key values, so the determinism test proves the
    SCRIPT's own Python-side sort (not this fake's convenience
    auto-sort-on-.order()) is what makes two runs byte-identical."""

    def order(self, column, desc: bool = False, **_kw):
        return self


class _FakeTableIgnoreOrder(_FakeTable):
    def select(self, *a, **kw):
        self.select_calls += 1
        return _FakeQueryIgnoreOrder(self._rows).select(*a, **kw)


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
    """Mirrors the real Supabase client's TWO table-access shapes:
    ``client.schema(name).table(...)`` for a named schema (billing_audit,
    pipeline_memory) and ``client.table(...)`` directly for the DEFAULT
    ``public`` schema (``public.artifacts``, per RESEARCH.md Pattern --
    "select it through the client's default schema, not
    client.schema('billing_audit')")."""

    def __init__(self, schema_obj: _FakeSchema, public_tables: dict | None = None):
        self._schema_obj = schema_obj
        self._public_tables = public_tables or {}

    def schema(self, _name: str):
        return self._schema_obj

    def table(self, name: str):
        return self._public_tables.get(name, _FakeTable([]))


def _make_billing_audit_fake_client(
    rpc_rows: list[dict],
    group_content_hash_rows: list[dict],
    artifacts_rows: list[dict] | None = None,
    rpc_handlers: dict | None = None,
    backup_table: dict | None = None,
) -> _FakeClient:
    """*backup_table*, when given, is
    ``{"name": str, "rows": list[dict]}`` (readable, Task 3 apply-path
    probe succeeds) or ``{"name": str, "raises": Exception}`` (probe
    fails -- missing relation or connectivity error, depending on the
    exception)."""
    tables: dict = {"group_content_hash": _FakeTable(group_content_hash_rows)}
    if backup_table is not None:
        name = backup_table["name"]
        if "raises" in backup_table:
            tables[name] = _RaisingTable(backup_table["raises"])
        else:
            tables[name] = _FakeTable(backup_table.get("rows", []))

    handlers: dict = {"lookup_attribution_bulk": lambda _params: rpc_rows}
    if rpc_handlers:
        handlers.update(rpc_handlers)

    schema_obj = _FakeSchema(tables=tables, rpc_handlers=handlers)
    return _FakeClient(
        schema_obj, public_tables={"artifacts": _FakeTable(artifacts_rows or [])}
    )


def _make_pipeline_memory_fake_client(
    group_state_rows: list[dict],
    row_event_rows: list[dict] | None = None,
    row_state_rows: list[dict] | None = None,
) -> _FakeClient:
    schema_obj = _FakeSchema(
        tables={
            "group_state": _FakeTable(group_state_rows),
            "row_event": _FakeTable(row_event_rows or []),
            "row_state": _FakeTable(row_state_rows or []),
        },
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
        roles: str = "primary", include_blank_roles: bool = False,
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
            if include_blank_roles:
                argv.append("--include-blank-roles")
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
        with --include-blank-roles, the default --roles (all three)
        surfaces them as unresolved candidates rather than silently
        dropping them. (Post-merge review fix: a blank role is NOT a
        target by default any more -- see BlankRoleTargetingTests for
        the new default behavior.)"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_dry_run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                gs_rows=[],
                roles="primary,helper,vac_crew",
                include_blank_roles=True,
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

    def test_report_dir_outside_generated_docs_warns_not_refuses(self):
        """Post-merge review fix (LOW): a --report-dir outside
        generated_docs/ (every test fixture's tmp_dir qualifies) must
        WARN, not refuse -- the run still exits 0 and writes the
        report."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertLogs(level="WARNING") as log_ctx:
                exit_code, _client = self._run_dry_run(tmp_dir)
            self.assertEqual(exit_code, 0)
            self.assertTrue(
                any(
                    "--report-dir" in msg and "generated_docs" in msg
                    for msg in log_ctx.output
                )
            )
            self.assertTrue(
                (Path(tmp_dir) / "own03_backfill_report.json").exists()
            )


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


class DiscoveryStatusTests(unittest.TestCase):
    """Post-merge review fix (MED): any prefetch_attribution status
    outside {'success', 'no_row'} is fatal -- 'unavailable' and
    'rpc_missing' used to fall through silently and yield zero
    targets (exit 0)."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def test_prefetch_unavailable_and_rpc_missing_exit_7(self):
        from scripts import backfill_claim_time_attribution as bf

        ba_client = _make_billing_audit_fake_client([], [])
        for status in ("unavailable", "rpc_missing"):
            with self.subTest(status=status):
                with mock.patch(
                    "billing_audit.client.get_client",
                    return_value=ba_client,
                ), mock.patch(
                    "billing_audit.writer.prefetch_attribution",
                    return_value=({}, status),
                ):
                    exit_code = bf.main(
                        ["--wr", _WR, "--weeks", "082425"]
                    )
                self.assertEqual(exit_code, 7)


class SourceStubTests(unittest.TestCase):
    """With no Supabase client configured (and no same-row attribution
    cached), sources 1-3 have nothing to read and are silent -- proves
    the ABSENCE-of-data path returns None rather than raising, distinct
    from the source-4-only Task 1 behavior these sources exhibited
    before Task 2 filled in their bodies."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def test_sources_one_two_three_are_silent_with_no_data(self):
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
        with mock.patch("billing_audit.client.get_client", return_value=None), \
                mock.patch("pipeline_memory.client.get_client", return_value=None):
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

    def test_no_last_known_before_week_literal_in_non_comment_lines(self):
        """D-12-A dropped the cross-week ladder rung (ledger
        [2026-09-01 19:55]) -- this asserts the literal token the
        REQUIREMENTS.md-stale wording used never appears in executable
        code (strip lines whose first non-space character is '#' before
        counting, per the plan's own instruction)."""
        src = _read_source(_SCRIPT_RELPATH)
        non_comment_lines = [
            line for line in src.splitlines()
            if not line.lstrip().startswith("#")
        ]
        code_text = "\n".join(non_comment_lines)
        self.assertNotIn("last_known_before_week", code_text)


class SourcesOneTwoThreeTests(unittest.TestCase):
    """Task 2: sources 1 (pipeline_memory.row_event/row_state), 2
    (same-row cross-role), and 3 (public.artifacts filenames), plus the
    total 1->2->3->4 precedence and the conflict/unresolved outcomes."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def _run(
        self, tmp_dir: str, rpc_rows, gch_rows=None, gs_rows=None,
        artifacts_rows=None, row_event_rows=None, row_state_rows=None,
        roles: str = "primary", sources: str = "1,2,3,4",
    ):
        from scripts import backfill_claim_time_attribution as bf

        ba_client = _make_billing_audit_fake_client(
            rpc_rows, gch_rows or [], artifacts_rows or []
        )
        pm_client = _make_pipeline_memory_fake_client(
            gs_rows or [], row_event_rows or [], row_state_rows or [],
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=ba_client
        ), mock.patch(
            "billing_audit.client.get_client", return_value=ba_client
        ), mock.patch(
            "pipeline_memory.client.get_client", return_value=pm_client
        ):
            argv = [
                "--wr", _WR,
                "--weeks", "082425",
                "--roles", roles,
                "--sources", sources,
                "--report-dir", tmp_dir,
            ]
            exit_code = bf.main(argv)
        return exit_code

    def _first_row(self, tmp_dir: str) -> dict:
        payload = json.loads(
            (Path(tmp_dir) / "own03_backfill_report.json").read_text(
                encoding="utf-8"
            )
        )
        return payload["rows"][0]

    # ── Source 1 ────────────────────────────────────────────────────

    def test_source_1_resolves_from_earliest_qualifying_row_event(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                row_event_rows=[
                    # Earlier event: not yet completed -- must NOT win.
                    _row_event(
                        _ROW_IDS["082425"], "2026-06-01T00:00:00+00:00",
                        units_completed=False, foreman_observed="Avery Example",
                    ),
                    # Qualifying event: completed + non-sentinel name.
                    _row_event(
                        _ROW_IDS["082425"], "2026-07-01T00:00:00+00:00",
                        units_completed=True, foreman_observed="Avery Example",
                    ),
                ],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["proposed_value"], "Avery Example")
            self.assertEqual(row["source"], "live")
            self.assertEqual(row["name_fidelity"], "exact")
            self.assertEqual(row["status"], "proposed")

    def test_source_1_falls_back_to_row_state_when_no_qualifying_event(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                row_state_rows=[
                    _row_state(
                        _ROW_IDS["082425"], "2026-07-02T00:00:00+00:00",
                        units_completed=True, foreman_observed="Avery Example",
                    ),
                ],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["proposed_value"], "Avery Example")
            self.assertEqual(row["source"], "live")

    def test_source_1_ignores_event_without_completion_flag(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                row_event_rows=[
                    _row_event(
                        _ROW_IDS["082425"], "2026-07-01T00:00:00+00:00",
                        units_completed=False, foreman_observed="Avery Example",
                    ),
                ],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["status"], "unresolved")

    # ── Source 2 ────────────────────────────────────────────────────

    def test_source_2_fills_from_same_row_other_role(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            rpc_row = _attribution_row("082425")
            rpc_row["helper"] = "Sam Sample"  # real, on the SAME row
            exit_code = self._run(tmp_dir, rpc_rows=[rpc_row])
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["proposed_value"], "Sam Sample")
            self.assertEqual(row["source"], "live")
            self.assertEqual(row["name_fidelity"], "exact")
            self.assertIn("helper", row["evidence"])

    def test_source_2_never_looks_at_another_row(self):
        """A real name on a DIFFERENT row_id must never leak into this
        row's proposal -- source 2 is confined to the same row_id."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            other_row = _attribution_row("082425")
            other_row["smartsheet_row_id"] = 999999
            other_row["helper"] = "Sam Sample"
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425"), other_row],
            )
            self.assertEqual(exit_code, 0)
            payload = json.loads(
                (Path(tmp_dir) / "own03_backfill_report.json").read_text(
                    encoding="utf-8"
                )
            )
            target_row = next(
                r for r in payload["rows"] if r["row_id"] == _ROW_IDS["082425"]
            )
            self.assertEqual(target_row["status"], "unresolved")

    # ── Source 3 ────────────────────────────────────────────────────

    def test_source_3_single_name_resolves(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                artifacts_rows=[
                    _artifact_row(
                        "082425",
                        "WR_19073866_WeekEnding_082425_120000_User_"
                        "Avery_Example_aabbcc.xlsx",
                    ),
                ],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["status"], "proposed")
            self.assertEqual(row["proposed_value"], "Avery Example")
            self.assertEqual(row["source"], "backfill_artifacts")
            self.assertEqual(row["name_fidelity"], "desanitized")

    def test_source_3_two_names_conflict(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                artifacts_rows=[
                    _artifact_row(
                        "082425",
                        "WR_19073866_WeekEnding_082425_120000_User_"
                        "Avery_Example_aabbcc.xlsx",
                    ),
                    _artifact_row(
                        "082425",
                        "WR_19073866_WeekEnding_082425_130000_User_"
                        "Pat_Example_bbccdd.xlsx",
                    ),
                ],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["status"], "conflict")
            self.assertEqual(row["proposed_value"], "")
            self.assertEqual(row["source"], "backfill_artifacts")

    def test_source_3_matches_subcontractor_helper_token(self):
        """Rule 2 (missing critical functionality): the subcontractor
        helper filename tokens (_ReducedSub_Helper_ / _AEPBillable_Helper_)
        map to role=helper and must resolve via source 3 even though the
        plan's own enumerated token list named only the bare _Helper_
        token -- omitting them would silently under-cover subcontractor
        sheets, exactly the class of gap OWN-03 exists to close."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            rpc_row = _attribution_row("082425")
            # Post-merge review fix: a blank helper is no longer a
            # target by default -- use a NAMED sentinel so this row
            # still qualifies (helper WAS populated once, then frozen
            # sentinel, the realistic OWN-03 scenario).
            rpc_row["helper"] = "Unknown Helper"
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[rpc_row],
                artifacts_rows=[
                    _artifact_row(
                        "082425",
                        "WR_19073866_WeekEnding_082425_120000_ReducedSub_"
                        "Helper_Sam_Sample_aabbcc.xlsx",
                        variant="reduced_sub_helper",
                    ),
                ],
                roles="helper",
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["proposed_value"], "Sam Sample")
            self.assertEqual(row["source"], "backfill_artifacts")

    def test_source_3_does_not_confuse_helper_with_reduced_sub_helper(self):
        """A bare _Helper_ filename must resolve only role=helper via the
        _Helper_ token -- NOT be double-counted as a reduced_sub_helper
        candidate too (specificity-ordered token matching, longest first)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            rpc_row = _attribution_row("082425")
            # Post-merge review fix: use a NAMED sentinel so role
            # "helper" is still a target under the new default
            # (blank-role-excluded) targeting rule.
            rpc_row["helper"] = "Unknown Helper"
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[rpc_row],
                artifacts_rows=[
                    _artifact_row(
                        "082425",
                        "WR_19073866_WeekEnding_082425_120000_Helper_"
                        "Sam_Sample_aabbcc.xlsx",
                        variant="helper",
                    ),
                ],
                roles="helper",
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["proposed_value"], "Sam Sample")
            self.assertEqual(row["source"], "backfill_artifacts")

    # ── Precedence and no-cross-week ───────────────────────────────

    def test_source_1_wins_over_3_and_4_when_all_present(self):
        """A row with candidates in sources 1, 3 and 4 resolves via
        source 1; sources 3/4's DELIBERATELY DIFFERENT names never
        surface, proving the later resolvers are not consulted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425", identifier="Pat_Example")],
                artifacts_rows=[
                    _artifact_row(
                        "082425",
                        "WR_19073866_WeekEnding_082425_120000_User_"
                        "Sam_Sample_aabbcc.xlsx",
                    ),
                ],
                row_event_rows=[
                    _row_event(
                        _ROW_IDS["082425"], "2026-07-01T00:00:00+00:00",
                        units_completed=True, foreman_observed="Avery Example",
                    ),
                ],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["proposed_value"], "Avery Example")
            self.assertEqual(row["source"], "live")
            self.assertEqual(row["name_fidelity"], "exact")

    def test_no_source_ever_reads_an_adjacent_week(self):
        """Fixture data for week 083125 must never leak into a row
        scoped to week 082425 -- proves the _WEEK_SCOPED filtering in
        every resolver's read site actually holds."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("083125", identifier="Avery_Example")],
                artifacts_rows=[
                    _artifact_row(
                        "083125",
                        "WR_19073866_WeekEnding_083125_120000_User_"
                        "Avery_Example_aabbcc.xlsx",
                    ),
                ],
                row_event_rows=[
                    _row_event(
                        _ROW_IDS["083125"], "2026-07-01T00:00:00+00:00",
                        units_completed=True, foreman_observed="Avery Example",
                    ),
                ],
                row_state_rows=[
                    _row_state(
                        _ROW_IDS["083125"], "2026-07-01T00:00:00+00:00",
                        units_completed=True, foreman_observed="Avery Example",
                    ),
                ],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["status"], "unresolved")

    def test_zero_candidates_across_all_sources_is_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
            )
            self.assertEqual(exit_code, 0)
            row = self._first_row(tmp_dir)
            self.assertEqual(row["status"], "unresolved")
            self.assertTrue(row["evidence"])
            self.assertEqual(row["proposed_value"], "")


class BlankRoleTargetingTests(unittest.TestCase):
    """Post-merge review fix (targeting, HIGH): a role whose CURRENT
    frozen value is blank/None is NOT a sentinel target by default --
    only a NAMED sentinel (e.g. 'Unknown Foreman') is. The
    --include-blank-roles flag restores the pre-hardening behavior."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def _run(self, tmp_dir: str, include_blank_roles: bool):
        from scripts import backfill_claim_time_attribution as bf

        rpc_rows = [_attribution_row("082425")]  # helper/vac_crew: None
        ba_client = _make_billing_audit_fake_client(rpc_rows, [])
        pm_client = _make_pipeline_memory_fake_client([])
        with mock.patch(
            "billing_audit.writer.get_client", return_value=ba_client
        ), mock.patch(
            "billing_audit.client.get_client", return_value=ba_client
        ), mock.patch(
            "pipeline_memory.client.get_client", return_value=pm_client
        ):
            argv = [
                "--wr", _WR, "--weeks", "082425",
                "--roles", "helper,vac_crew",
                "--report-dir", tmp_dir,
            ]
            if include_blank_roles:
                argv.append("--include-blank-roles")
            exit_code = bf.main(argv)
        return exit_code

    def test_blank_roles_excluded_by_default(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(tmp_dir, include_blank_roles=False)
            self.assertEqual(exit_code, 0)
            payload = json.loads(
                (Path(tmp_dir) / "own03_backfill_report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["rows"], [])
            self.assertEqual(payload["summary"]["total_rows"], 0)
            self.assertFalse(payload["summary"]["include_blank_roles"])

    def test_blank_roles_included_with_flag(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = self._run(tmp_dir, include_blank_roles=True)
            self.assertEqual(exit_code, 0)
            payload = json.loads(
                (Path(tmp_dir) / "own03_backfill_report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(payload["rows"]), 2)
            self.assertTrue(payload["summary"]["include_blank_roles"])
            for row in payload["rows"]:
                self.assertEqual(row["status"], "unresolved")


class BatchedReadsTests(unittest.TestCase):
    """Post-merge review fix (batched reads, HIGH): source 1 must issue
    chunked .in_() reads over the in-scope row_ids, never one
    row_event/row_state query per row."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def test_source_1_batches_row_event_and_row_state_reads(self):
        import math

        from scripts import backfill_claim_time_attribution as bf

        rpc_rows = [_attribution_row(t) for t in _WEEK_TOKENS]
        row_event_rows = [
            _row_event(
                _ROW_IDS[t], "2026-07-01T00:00:00+00:00",
                units_completed=True, foreman_observed="Avery Example",
            )
            for t in _WEEK_TOKENS
        ]
        ba_client = _make_billing_audit_fake_client(rpc_rows, [])
        pm_client = _make_pipeline_memory_fake_client(
            [], row_event_rows=row_event_rows,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
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
                    "--roles", "primary",
                    "--report-dir", tmp_dir,
                ]
                exit_code = bf.main(argv)
            self.assertEqual(exit_code, 0)
            payload = json.loads(
                (Path(tmp_dir) / "own03_backfill_report.json").read_text(
                    encoding="utf-8"
                )
            )
            for row in payload["rows"]:
                self.assertEqual(row["status"], "proposed")
                self.assertEqual(row["source"], "live")

        n = len(_WEEK_TOKENS)
        expected_max_calls = math.ceil(n / bf._ROW_ID_CHUNK_SIZE)
        row_event_table = pm_client._schema_obj._tables["row_event"]
        row_state_table = pm_client._schema_obj._tables["row_state"]
        self.assertGreater(row_event_table.select_calls, 0)
        self.assertLessEqual(
            row_event_table.select_calls, expected_max_calls
        )
        self.assertLessEqual(
            row_state_table.select_calls, expected_max_calls
        )
        # Never one query per row: strictly fewer calls than targets
        # whenever more than one row_id shares a chunk.
        self.assertLess(row_event_table.select_calls, n)


class SourceReadFailureTests(unittest.TestCase):
    """Post-merge review fix (silent read failure, HIGH): with_retry()
    returning None (retries exhausted / circuit breaker open) must
    exit 7, never be treated as "no evidence"."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def test_row_event_with_retry_none_exits_7(self):
        from scripts import backfill_claim_time_attribution as bf

        rpc_rows = [_attribution_row("082425")]
        ba_client = _make_billing_audit_fake_client(rpc_rows, [])
        pm_client = _make_pipeline_memory_fake_client([])
        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch(
                "billing_audit.writer.get_client", return_value=ba_client
            ), mock.patch(
                "billing_audit.client.get_client", return_value=ba_client
            ), mock.patch(
                "pipeline_memory.client.get_client",
                return_value=pm_client,
            ), mock.patch(
                "pipeline_memory.client.with_retry", return_value=None
            ):
                argv = [
                    "--wr", _WR, "--weeks", "082425",
                    "--roles", "primary", "--report-dir", tmp_dir,
                ]
                exit_code = bf.main(argv)
        self.assertEqual(exit_code, 7)


class DeterminismTests(unittest.TestCase):
    """Post-merge review fix (determinism, MED must_have): two runs
    over the SAME rows produce byte-identical reports regardless of
    server row order, even when the server does not honor .order()
    (simulated here via _FakeTableIgnoreOrder)."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def _run_once(self, gch_rows_order: list[dict], tmp_dir: str) -> str:
        from scripts import backfill_claim_time_attribution as bf

        rpc_rows = [_attribution_row("082425")]
        ba_client = _make_billing_audit_fake_client(rpc_rows, [])
        ba_client._schema_obj._tables["group_content_hash"] = (
            _FakeTableIgnoreOrder(gch_rows_order)
        )
        pm_client = _make_pipeline_memory_fake_client([])
        with mock.patch(
            "billing_audit.writer.get_client", return_value=ba_client
        ), mock.patch(
            "billing_audit.client.get_client", return_value=ba_client
        ), mock.patch(
            "pipeline_memory.client.get_client", return_value=pm_client
        ):
            argv = [
                "--wr", _WR, "--weeks", "082425", "--roles", "primary",
                "--report-dir", tmp_dir,
            ]
            exit_code = bf.main(argv)
        self.assertEqual(exit_code, 0)
        return (Path(tmp_dir) / "own03_backfill_report.json").read_text(
            encoding="utf-8"
        )

    def test_shuffled_tied_rows_produce_identical_report(self):
        # Two rows tied on updated_at (both pre-defect) that resolve
        # to the SAME desanitized name via two different variants --
        # the tie-break among them must not depend on input order.
        row_primary = _gch_row(
            "082425", identifier="Avery_Example", variant="primary",
            updated_at=_PRE_DEFECT_UPDATED_AT,
        )
        row_reduced_sub = _gch_row(
            "082425", identifier="Avery_Example", variant="reduced_sub",
            updated_at=_PRE_DEFECT_UPDATED_AT,
        )
        with tempfile.TemporaryDirectory() as tmp_a, \
                tempfile.TemporaryDirectory() as tmp_b:
            json_a = self._run_once(
                [row_primary, row_reduced_sub], tmp_a
            )
            _reset_all_clients()
            json_b = self._run_once(
                [row_reduced_sub, row_primary], tmp_b
            )
            self.assertEqual(json_a, json_b)


# ── Task 3: the --apply write path ────────────────────────────────────
# A fixed run date, NOT wall-clock "today" -- the backup table name is
# date-derived, so every apply-path test patches
# scripts.backfill_claim_time_attribution._run_date to this constant
# for a deterministic, known table name.
_RUN_DATE = datetime.date(2026, 9, 3)
_BACKUP_TABLE_NAME = "attribution_snapshot_backup_" + _RUN_DATE.strftime("%Y%m%d")


class ApplyPathTests(unittest.TestCase):
    """Task 3: approval gate, backup-table precondition, RPC caller,
    never-overwrite-a-real-name guarantee."""

    def setUp(self):
        _reset_all_clients()

    def tearDown(self):
        _reset_all_clients()

    def _run_apply(
        self, tmp_dir: str, rpc_rows, gch_rows=None, backup_table=None,
        rpc_handlers=None, apply: bool = True, approved: bool = True,
        roles: str = "primary",
    ):
        from scripts import backfill_claim_time_attribution as bf

        ba_client = _make_billing_audit_fake_client(
            rpc_rows, gch_rows or [], rpc_handlers=rpc_handlers,
            backup_table=backup_table,
        )
        pm_client = _make_pipeline_memory_fake_client([])

        argv = [
            "--wr", _WR, "--weeks", "082425", "--roles", roles,
            "--report-dir", tmp_dir,
        ]
        if apply:
            argv.append("--apply")
        if approved:
            argv.append("--i-approved-this")

        with mock.patch(
            "billing_audit.writer.get_client", return_value=ba_client
        ), mock.patch(
            "billing_audit.client.get_client", return_value=ba_client
        ), mock.patch(
            "pipeline_memory.client.get_client", return_value=pm_client
        ), mock.patch(
            "scripts.backfill_claim_time_attribution._run_date",
            return_value=_RUN_DATE,
        ):
            exit_code = bf.main(argv)
        return exit_code, ba_client

    def test_apply_without_approval_returns_4_and_no_rpc_calls(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, ba_client = self._run_apply(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                apply=True, approved=False,
            )
            self.assertEqual(exit_code, 4)
            rpc_names = {n for n, _p in ba_client._schema_obj.rpc_calls}
            self.assertNotIn("backfill_attribution", rpc_names)

    @unittest.skipIf(
        _POSTGREST_API_ERROR_CLS is None,
        "postgrest not installed -- cannot construct a real APIError to "
        "simulate PGRST205 (table not found)",
    )
    def test_apply_missing_backup_table_returns_3(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_apply(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                backup_table={
                    "name": _BACKUP_TABLE_NAME,
                    "raises": _make_api_error(
                        "PGRST205",
                        message=(
                            "Could not find the table 'billing_audit."
                            f"{_BACKUP_TABLE_NAME}' in the schema cache"
                        ),
                    ),
                },
            )
            self.assertEqual(exit_code, 3)

    def test_apply_backup_probe_connectivity_error_returns_7(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_apply(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                backup_table={
                    "name": _BACKUP_TABLE_NAME,
                    "raises": RuntimeError("connection reset"),
                },
            )
            self.assertEqual(exit_code, 7)

    def test_build_apply_payload_excludes_real_current_value(self):
        """Defense in depth (T-12-01): even a malformed report_rows entry
        whose status is 'proposed' but current_value is a REAL name (a
        state normal discovery could never produce) must never reach
        p_rows -- the Python-side is_sentinel_claimer guard does not
        trust the caller's own status classification."""
        from scripts import backfill_claim_time_attribution as bf

        rows = [
            {
                "wr": _WR, "week_ending": "2026-08-24",
                "row_id": _ROW_IDS["082425"], "role": "primary",
                "current_value": "Pat Example",
                "proposed_value": "Sam Sample",
                "source": "backfill_hash_history", "status": "proposed",
            },
        ]
        payload = bf._build_apply_payload(rows, run_id="test-run")
        self.assertEqual(payload, [])

    def test_apply_payload_key_set_is_exact_seven_keys(self):
        from scripts import backfill_claim_time_attribution as bf

        rows = [
            {
                "wr": _WR, "week_ending": "2026-08-24",
                "row_id": _ROW_IDS["082425"], "role": "primary",
                "current_value": "Unknown Foreman",
                "proposed_value": "Avery Example",
                "source": "backfill_hash_history", "status": "proposed",
            },
        ]
        payload = bf._build_apply_payload(rows, run_id="test-run")
        self.assertEqual(len(payload), 1)
        self.assertEqual(
            set(payload[0].keys()),
            {
                "wr", "week_ending", "smartsheet_row_id", "role", "value",
                "backfill_source", "backfill_run_id",
            },
        )

    def test_apply_raised_rpc_exception_returns_6(self):
        def _raising_handler(_params):
            raise RuntimeError("simulated RPC failure")

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_apply(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                backup_table={"name": _BACKUP_TABLE_NAME, "rows": []},
                rpc_handlers={"backfill_attribution": _raising_handler},
            )
            self.assertEqual(exit_code, 6)

    def test_apply_rpc_result_count_mismatch_returns_6(self):
        """Post-merge review fix (apply reconciliation, MED): a
        response whose per-row result count does not match the
        chunk's payload size must never be trusted -- treated as a
        chunk failure, exit 6."""

        def _truncated_handler(params):
            # One row was proposed/sent; return zero results -- a
            # response shorter than the chunk it answered.
            return [
                {**row, "result": "updated"}
                for row in params["p_rows"][:-1]
            ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertLogs(level="ERROR") as log_ctx:
                exit_code, _client = self._run_apply(
                    tmp_dir,
                    rpc_rows=[_attribution_row("082425")],
                    gch_rows=[_gch_row("082425")],
                    backup_table={"name": _BACKUP_TABLE_NAME, "rows": []},
                    rpc_handlers={
                        "backfill_attribution": _truncated_handler
                    },
                )
            self.assertEqual(exit_code, 6)
            self.assertTrue(
                any("result(s)" in msg for msg in log_ctx.output)
            )

    def test_apply_skipped_real_name_logs_warning_and_returns_0(self):
        def _skipped_handler(params):
            return [
                {**row, "result": "skipped_real_name"}
                for row in params["p_rows"]
            ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertLogs(level="WARNING") as log_ctx:
                exit_code, _client = self._run_apply(
                    tmp_dir,
                    rpc_rows=[_attribution_row("082425")],
                    gch_rows=[_gch_row("082425")],
                    backup_table={"name": _BACKUP_TABLE_NAME, "rows": []},
                    rpc_handlers={"backfill_attribution": _skipped_handler},
                )
            self.assertEqual(exit_code, 0)
            self.assertTrue(
                any("skipped_real_name" in msg for msg in log_ctx.output)
            )

    def test_apply_updated_result_returns_0_and_report_gets_rpc_result(self):
        def _updated_handler(params):
            return [
                {**row, "result": "updated"} for row in params["p_rows"]
            ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_apply(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                backup_table={"name": _BACKUP_TABLE_NAME, "rows": []},
                rpc_handlers={"backfill_attribution": _updated_handler},
            )
            self.assertEqual(exit_code, 0)
            payload = json.loads(
                (Path(tmp_dir) / "own03_backfill_report.json").read_text(
                    encoding="utf-8"
                )
            )
            row = payload["rows"][0]
            self.assertEqual(row["rpc_result"], "updated")
            self.assertIn("apply", payload["summary"])
            self.assertEqual(payload["summary"]["apply"]["updated"], 1)

    def test_dry_run_report_has_no_rpc_result_column(self):
        """A plain dry-run (no --apply) must not introduce an rpc_result
        column at all -- keeps the Task 1/2 CSV header contract stable."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, _client = self._run_apply(
                tmp_dir,
                rpc_rows=[_attribution_row("082425")],
                gch_rows=[_gch_row("082425")],
                apply=False, approved=False,
            )
            self.assertEqual(exit_code, 0)
            csv_path = Path(tmp_dir) / "own03_backfill_report.csv"
            header = csv_path.read_text(encoding="utf-8").splitlines()[0]
            self.assertNotIn("rpc_result", header)


class ApplyStructuralContractTests(unittest.TestCase):
    def test_script_calls_backfill_attribution_rpc_never_freeze_row(self):
        src = _read_source(_SCRIPT_RELPATH)
        self.assertIn('rpc("backfill_attribution"', src)
        self.assertNotIn("freeze_row(", src)
