"""Shadow-mode tests for the pipeline_memory package.

Plan 10-01 (Task 1) covers the thinnest end-to-end path through every
layer -- config flag, orchestrator hook, writer, retry layer, PostgREST
transport -- for the ``run_ledger`` table only:

  - Test 1 (tracer, end-to-end): flag on + fake client -> exactly two
    PostgREST interactions (start, finish), both against pipeline_memory,
    both a run_ledger table upsert with on_conflict="run_id".
  - Test 2: flag absent -> zero calls.
  - Test 3: TEST_MODE=true -> get_client() returns None at construction.
  - Test 4 (fail-open): a PGRST106 error disables the package for the
    run without raising, bumps the errored counter, and short-circuits
    the next call without a second execute().
  - Test 5 (cross-feature isolation): the same PGRST106 kill leaves
    billing_audit's own kill switch untouched.
  - Test 6: resolve_run_id()'s three derivation branches.

Task 3 extends this file with the Python<->SQL column contract lock and
the MEM-02 edge invariants plan 10-02's row-level write path must
satisfy:

  - A reusable schema-column-extraction helper, exercised against
    ``run_ledger`` (parses ``pipeline_memory/schema.sql`` directly).
  - Empty input (zero calls, empty set) / single-element input (one
    call) for ``upsert_rows_bulk``.
  - Blank/absent Foreman never becomes a placeholder, and content_hash
    stays stable/non-empty regardless.
  - Hash order-stability: two dicts with the same key/value pairs in
    different insertion order hash identically.
  - Adjacency: two rows differing only by row_id never collapse into
    one payload entry.
  - Counter discipline: get_counters() returns ints; a forced RPC
    failure bumps only the errored counter.
  - PII discipline: no writer log record contains a personnel value.

Self-contained like ``tests/test_billing_audit_shadow.py`` -- there is
no ``tests/conftest.py`` in this repo to share fixtures from.
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_ENV_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "TEST_MODE",
    "RUN_MEMORY_WRITE_ENABLED",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT",
    "EXECUTION_TYPE",
)


def _reset_all():
    """Reset pipeline_memory's independent client/writer module state.

    Deliberately does NOT touch ``billing_audit``'s module state -- that
    independence is exactly what Test 5 verifies.
    """
    from pipeline_memory import client as mem_client
    from pipeline_memory import writer as mem_writer
    mem_client.reset_cache_for_tests()
    mem_writer._reset_counters_for_tests()


def _pop_env():
    for k in _ENV_KEYS:
        os.environ.pop(k, None)


def _make_fake_pipeline_memory_client(rpc_side_effect=None, upsert_capture=None):
    """Build a mock Supabase client with the chained API shape the
    pipeline_memory writer uses now (table upsert) and will use in a
    later plan (bulk RPC):
    ``client.schema('pipeline_memory').table(name).upsert(payload,
    on_conflict=...).execute()`` and
    ``client.schema('pipeline_memory').rpc(name, params).execute()``.

    Mirrors ``tests/test_billing_audit_shadow.py::_make_fake_supabase_client``.
    """
    client = mock.Mock()

    schema = mock.Mock()
    client.schema.return_value = schema

    rpc_obj = mock.Mock()
    if rpc_side_effect is None:
        rpc_obj.execute.return_value = mock.Mock(data=[])
    else:
        rpc_obj.execute.side_effect = rpc_side_effect
    schema.rpc.return_value = rpc_obj

    table_obj = mock.Mock()
    schema.table.return_value = table_obj

    upsert_obj = mock.Mock()
    table_obj.upsert.return_value = upsert_obj

    def _upsert_execute():
        if upsert_capture is not None:
            upsert_capture.append(table_obj.upsert.call_args)
        return mock.Mock(data=[])

    upsert_obj.execute.side_effect = _upsert_execute

    return client


class RunLedgerTracerTests(unittest.TestCase):
    """Test 1 + Test 2 -- the end-to-end tracer and the flag-off no-op."""

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def test_start_then_finish_produce_exactly_two_run_ledger_upserts(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = _make_fake_pipeline_memory_client(upsert_capture=upsert_capture)

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.run_ledger_start("run-1", mode="full", release="rel-1")
            mem_writer.run_ledger_finish(
                "run-1",
                status="success",
                sheets_checked=3,
                rows_seen=10,
                rows_changed=0,
                groups_generated=2,
            )

        self.assertEqual(len(upsert_capture), 2)
        self.assertEqual(
            client.schema.call_args_list,
            [mock.call("pipeline_memory")] * 2,
        )
        self.assertEqual(
            client.schema.return_value.table.call_args_list,
            [mock.call("run_ledger")] * 2,
        )

        start_call = upsert_capture[0]
        start_payload = start_call.args[0]
        self.assertEqual(start_call.kwargs.get("on_conflict"), "run_id")
        self.assertEqual(start_payload["run_id"], "run-1")
        self.assertEqual(start_payload["mode"], "full")
        self.assertIn("started_at", start_payload)
        self.assertEqual(start_payload["release"], "rel-1")
        self.assertEqual(start_payload["status"], "running")

        finish_call = upsert_capture[1]
        finish_payload = finish_call.args[0]
        self.assertEqual(finish_call.kwargs.get("on_conflict"), "run_id")
        self.assertEqual(finish_payload["run_id"], "run-1")
        # Regression (plan 10-06 Task 3, live-verified 2026-08-25 against
        # poeyztlmsawfoqlanucc): schema.sql's mode column is NOT NULL with
        # no DEFAULT, and PostgREST's merge-duplicates upsert validates the
        # proposed row against NOT NULL constraints before conflict
        # resolution -- omitting mode here raises a real 23502
        # not_null_violation on every finish upsert, even though the write
        # is an UPDATE of an existing row, not an INSERT.
        self.assertEqual(finish_payload["mode"], "full")
        self.assertIn("finished_at", finish_payload)
        self.assertEqual(finish_payload["status"], "success")
        self.assertEqual(finish_payload["sheets_checked"], 3)
        self.assertEqual(finish_payload["rows_seen"], 10)
        self.assertEqual(finish_payload["rows_changed"], 0)
        self.assertEqual(finish_payload["groups_generated"], 2)
        self.assertIsInstance(finish_payload["notes"], dict)

        self.assertEqual(mem_writer.get_counters()["run_ledger_written"], 2)
        self.assertEqual(mem_writer.get_counters()["run_ledger_errored"], 0)

    def test_noop_when_write_flag_absent(self):
        """RUN_MEMORY_WRITE_ENABLED intentionally absent (popped in setUp)."""
        from pipeline_memory import writer as mem_writer

        client = _make_fake_pipeline_memory_client()

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.run_ledger_start("run-2", mode="full", release="")
            mem_writer.run_ledger_finish("run-2", status="success")

        client.schema.assert_not_called()
        self.assertEqual(mem_writer.get_counters()["run_ledger_written"], 0)
        self.assertEqual(mem_writer.get_counters()["run_ledger_errored"], 0)


class ClientTestModeTests(unittest.TestCase):
    """Test 3 -- TEST_MODE no-ops at client construction (Pitfall 7)."""

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def test_get_client_returns_none_under_test_mode(self):
        from pipeline_memory import client as mem_client

        os.environ["TEST_MODE"] = "true"
        self.assertIsNone(mem_client.get_client())
        # Memoized: a second call must not re-evaluate TEST_MODE / retry
        # client construction.
        self.assertIsNone(mem_client.get_client())


try:
    from postgrest import APIError as _POSTGREST_API_ERROR_CLS  # type: ignore
except Exception:
    _POSTGREST_API_ERROR_CLS = None  # type: ignore[assignment]


@unittest.skipIf(
    _POSTGREST_API_ERROR_CLS is None,
    "postgrest not installed — skipping PostgREST fail-open/isolation tests.",
)
class FailOpenAndIsolationTests(unittest.TestCase):
    """Test 4 (fail-open) + Test 5 (cross-feature isolation, CRITICAL)."""

    def setUp(self):
        from billing_audit import client as ba_client
        ba_client.reset_cache_for_tests()
        _reset_all()
        _pop_env()

    def tearDown(self):
        from billing_audit import client as ba_client
        ba_client.reset_cache_for_tests()
        _reset_all()
        _pop_env()

    def _make_pgrst106(self):
        return _POSTGREST_API_ERROR_CLS({
            "code": "PGRST106",
            "message": "The schema must be one of the following: public",
            "hint": "",
            "details": "",
        })

    def test_pgrst106_is_fail_open_and_short_circuits_next_call(self):
        from pipeline_memory import writer as mem_writer
        from pipeline_memory import client as mem_client

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        call_count = {"n": 0}

        def _raise(*_a, **_kw):
            call_count["n"] += 1
            raise self._make_pgrst106()

        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.table.return_value.upsert.return_value.execute.side_effect = _raise

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            # Neither hook raises.
            mem_writer.run_ledger_start("run-x", mode="full", release="")
            mem_writer.run_ledger_finish("run-x", status="success")

        self.assertEqual(mem_client.get_disable_reason(), "PGRST106")
        self.assertGreaterEqual(
            mem_writer.get_counters()["run_ledger_errored"], 1
        )
        # Only the FIRST hook's attempt ever reaches execute(): with_retry
        # bails out on the global-kill branch of that one attempt (no
        # per-attempt retries on a permanent code), and the second hook's
        # with_retry call short-circuits on the already-tripped kill
        # switch before invoking the wrapped function at all.
        self.assertEqual(call_count["n"], 1)

    def test_pgrst106_does_not_disable_billing_audit_client(self):
        """CRITICAL isolation check (10-RESEARCH.md Pitfall 5): a
        pipeline_memory-only PostgREST misconfiguration must never trip
        billing_audit's own, independent kill switch.
        """
        from pipeline_memory import writer as mem_writer
        from billing_audit import client as ba_client

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"

        def _raise(*_a, **_kw):
            raise self._make_pgrst106()

        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.table.return_value.upsert.return_value.execute.side_effect = _raise

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.run_ledger_start("run-y", mode="full", release="")

        self.assertIsNone(ba_client._global_disable_reason)
        # billing_audit's own get_client() must still be reachable (not
        # short-circuited by a kill switch it never tripped). In this
        # sandboxed test env it returns None for a SEPARATE, expected
        # reason (missing SUPABASE_URL/KEY, popped in setUp) -- the load-
        # bearing assertion is the disable-reason check above.
        self.assertIsNone(ba_client.get_client())


class ResolveRunIdTests(unittest.TestCase):
    """Test 6 -- the three resolve_run_id() derivation branches."""

    def setUp(self):
        _pop_env()

    def tearDown(self):
        _pop_env()

    def test_id_and_attempt_both_set(self):
        from pipeline_memory import writer as mem_writer

        os.environ["GITHUB_RUN_ID"] = "998877"
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        self.assertEqual(mem_writer.resolve_run_id(), "998877.2")

    def test_only_id_set(self):
        from pipeline_memory import writer as mem_writer

        os.environ["GITHUB_RUN_ID"] = "998877"
        self.assertEqual(mem_writer.resolve_run_id(), "998877")

    def test_neither_set_returns_unique_local_prefixed_value(self):
        """A run without GITHUB_RUN_ID falls back to a "local-"-prefixed
        microsecond timestamp -- unique PER RUN in production (this is
        called once, at the top of main()). Assert the derivation shape
        (mirrors ``pipeline/orchestrate.py``'s
        ``f"local-{utcnow.strftime('%Y%m%dT%H%M%S%fZ')}"`` exactly)
        rather than cross-call inequality: two calls made back-to-back
        in a test can legitimately land in the same microsecond on a
        fast host, which is not a real production scenario.
        """
        import re

        from pipeline_memory import writer as mem_writer

        value = mem_writer.resolve_run_id()
        self.assertRegex(value, r"^local-\d{8}T\d{12}Z$")
        # The digits after "local-" and before "T" must be a real
        # calendar date (YYYYMMDD) close to "now", not an arbitrary
        # digit string -- catches a format/ordering typo in the mirror.
        date_part = re.match(r"^local-(\d{8})T", value).group(1)
        import datetime as _dt
        self.assertEqual(
            date_part, _dt.datetime.utcnow().strftime("%Y%m%d"),
        )


class RowModifiedAtHashNeutralityTests(unittest.TestCase):
    """Task 1 (MEM-02): ``__row_modified_at`` (pipeline/fetch.py) must be
    hash-neutral for ``pipeline.change_detection.calculate_data_hash`` (the
    EXISTING group-level hash -- unrelated to pipeline_memory's own
    ``content_hash``) and must map cleanly through the writer's row-payload
    builder, including tolerating its absence.

    Both properties predate this task by construction --
    ``calculate_data_hash`` reads only explicitly named fields via
    ``.get()`` (pipeline/change_detection.py) so an unnamed double-
    underscore key is invisible to it regardless of pipeline/fetch.py's
    state, and the payload builder's ``row_data.get("__row_modified_at")``
    already tolerates a missing key. These tests pin BOTH invariants so a
    future change to either function's field list can't silently break the
    contract this task's fetch.py capture line depends on. The new
    fetch.py capture line itself (``getattr(row, 'modified_at', None)`` ->
    ISO-serialise -> ``row_data['__row_modified_at']``) is proven by the
    bounded ``git diff --numstat`` gate, the full suite, and
    ``bash scripts/run_6_gates.sh`` -- unit-testing the Smartsheet SDK Row
    object itself is out of this test file's scope (no existing fixture
    mocks a full ``Sheet``/``Row`` success path in ``pipeline.fetch``).
    """

    def _group_row(self, **overrides):
        row = {
            'Work Request #': '90001',
            'Snapshot Date': '2026-08-01',
            'CU': 'ANC-M',
            'Pole #': 'P-1',
            'Quantity': '3',
        }
        row.update(overrides)
        return row

    def test_calculate_data_hash_is_neutral_to_row_modified_at(self):
        import generate_weekly_pdfs

        saved_ext = generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION
        saved_cutoff = generate_weekly_pdfs.RATE_CUTOFF_DATE
        saved_fp = generate_weekly_pdfs._RATES_FINGERPRINT
        try:
            generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = True
            generate_weekly_pdfs.RATE_CUTOFF_DATE = None
            generate_weekly_pdfs._RATES_FINGERPRINT = ''

            without_key = [self._group_row()]
            with_key = [self._group_row(
                __row_modified_at='2026-08-24T10:15:00+00:00',
            )]
            self.assertEqual(
                generate_weekly_pdfs.calculate_data_hash(without_key),
                generate_weekly_pdfs.calculate_data_hash(with_key),
            )
        finally:
            generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = saved_ext
            generate_weekly_pdfs.RATE_CUTOFF_DATE = saved_cutoff
            generate_weekly_pdfs._RATES_FINGERPRINT = saved_fp

    def test_payload_builder_maps_row_modified_at_and_tolerates_absence(self):
        from pipeline_memory import writer as mem_writer

        row_with = {
            "__row_id": 1,
            "Work Request #": "90001",
            "__row_modified_at": "2026-08-24T10:15:00+00:00",
        }
        payload_with = mem_writer._row_to_payload(
            row_with, "run-1", None, None,
        )
        self.assertEqual(
            payload_with["row_modified_at"], "2026-08-24T10:15:00+00:00",
        )

        row_without = {"__row_id": 2, "Work Request #": "90001"}
        payload_without = mem_writer._row_to_payload(
            row_without, "run-1", None, None,
        )
        self.assertIsNone(payload_without["row_modified_at"])


_SCHEMA_SQL_PATH = _REPO_ROOT / "pipeline_memory" / "schema.sql"


def _read_schema_sql() -> str:
    return _SCHEMA_SQL_PATH.read_text(encoding="utf-8")


_COLUMN_LINE_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s+"
    r"(BIGINT|TEXT|JSONB|BOOLEAN|DATE|TIMESTAMPTZ|INT|NUMERIC|INTEGER)\b"
)


def _extract_schema_table_columns(schema_sql: str, table_name: str) -> set[str]:
    """Parse the ``CREATE TABLE IF NOT EXISTS pipeline_memory.<table_name>
    ( ... );`` block out of ``schema_sql`` and return its column-name set.

    A small text scanner, not a real SQL parser -- sufficient for this
    repo's own DDL formatting convention (one ``name<spaces>TYPE`` per
    physical line; table-level constraints like ``PRIMARY KEY (...)`` /
    multi-line ``CHECK (...)`` are recognized by NOT matching the
    ``identifier TYPE`` shape, so they're skipped without an explicit
    keyword denylist). Reusable by later plans for row_state / row_event
    / group_state / sheet_registry -- this file only exercises it against
    ``run_ledger`` (the one table plan 10-01 actually wires).

    This is the mechanical guard for the DDL's own stated contract
    (pipeline_memory/schema.sql's closing comment block): a column
    rename here must update the Python writer in the same PR.
    """
    block_re = re.compile(
        r"CREATE TABLE IF NOT EXISTS pipeline_memory\."
        + re.escape(table_name)
        + r"\s*\((.*?)\n\);",
        re.DOTALL,
    )
    m = block_re.search(schema_sql)
    if not m:
        raise AssertionError(
            f"CREATE TABLE block for pipeline_memory.{table_name!r} "
            "not found in pipeline_memory/schema.sql"
        )
    columns: set[str] = set()
    for raw_line in m.group(1).splitlines():
        line = raw_line.strip().rstrip(",")
        col_match = _COLUMN_LINE_RE.match(line)
        if col_match:
            columns.add(col_match.group(1))
    return columns


class SchemaColumnContractTests(unittest.TestCase):
    """Task 3 contract test: the writer's run_ledger payload keys must be
    a subset of the schema's run_ledger column set, and the RPC
    parameter names the writer will call with must appear in the file.
    """

    def test_run_ledger_extraction_finds_expected_columns(self):
        schema_sql = _read_schema_sql()
        columns = _extract_schema_table_columns(schema_sql, "run_ledger")
        expected = {
            "run_id", "mode", "started_at", "finished_at", "release",
            "sheets_checked", "sheets_changed", "rows_seen", "rows_changed",
            "groups_affected", "groups_generated", "status", "notes",
        }
        self.assertEqual(columns, expected)

    def test_writer_run_ledger_payload_keys_are_schema_columns(self):
        from pipeline_memory import writer as mem_writer

        schema_columns = _extract_schema_table_columns(
            _read_schema_sql(), "run_ledger"
        )

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = _make_fake_pipeline_memory_client(upsert_capture=upsert_capture)
        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.run_ledger_start("run-c1", mode="full", release="r")
            mem_writer.run_ledger_finish(
                "run-c1",
                status="success",
                sheets_checked=1,
                rows_seen=1,
                rows_changed=0,
                groups_generated=1,
            )

        for call in upsert_capture:
            payload = call.args[0]
            extra = set(payload.keys()) - schema_columns
            self.assertEqual(
                extra, set(),
                f"payload key(s) {extra} are not columns of "
                "pipeline_memory.run_ledger per schema.sql",
            )

    def test_rpc_parameter_names_appear_in_schema_file(self):
        schema_sql = _read_schema_sql()
        for token in ("p_sheet_id", "p_run_id", "p_rows"):
            self.assertIn(token, schema_sql)


class BulkPayloadContractTests(unittest.TestCase):
    """Task 3 (10-01) + Task 2 (10-02) edge invariants for
    ``upsert_rows_bulk`` / ``_row_to_payload`` / ``compute_content_hash``
    -- the MEM-02 contract plan 10-02's per-sheet loop (chunking,
    sub-budget, orchestrator wiring) is built on top of. Asserts payload
    SHAPE, never database state (no live Supabase / Postgres in this
    suite).
    """

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def test_empty_input_performs_zero_calls_and_returns_empty_set(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            result = mem_writer.upsert_rows_bulk(123, "run-1", [])

        self.assertIsNotNone(result)
        self.assertEqual(result, set())
        client.schema.assert_not_called()

    def test_single_element_input_performs_exactly_one_call(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        row = {"__row_id": 1, "Work Request #": "90001", "Foreman": "Alice"}

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            result = mem_writer.upsert_rows_bulk(123, "run-1", [row])

        self.assertEqual(client.schema.return_value.rpc.call_count, 1)
        name, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(name, "upsert_rows_bulk")
        self.assertEqual(params["p_sheet_id"], 123)
        self.assertEqual(params["p_run_id"], "run-1")
        self.assertEqual(len(params["p_rows"]), 1)
        self.assertIsNotNone(result)

    def test_blank_or_absent_foreman_never_becomes_placeholder(self):
        """10-RESEARCH.md Pitfall 2 (CRITICAL): foreman_observed reads the
        RAW 'Foreman' column, never the resolved __effective_user (which
        substitutes the literal 'Unknown Foreman' sentinel when blank --
        the exact defect that corrupted 93 WRs / 5,824 rows in
        billing_audit.attribution_snapshot).
        """
        from pipeline_memory import writer as mem_writer

        blank_row = {
            "__row_id": 1,
            "Work Request #": "90001",
            "Foreman": "",
            "__effective_user": "Unknown Foreman",
        }
        payload = mem_writer._row_to_payload(blank_row, "run-1", None, None)
        self.assertIn(payload["foreman_observed"], (None, ""))
        self.assertNotEqual(payload["foreman_observed"], "Unknown Foreman")
        self.assertTrue(payload["content_hash"])
        self.assertIsInstance(payload["content_hash"], str)

        absent_row = dict(blank_row)
        del absent_row["Foreman"]
        payload2 = mem_writer._row_to_payload(absent_row, "run-1", None, None)
        self.assertIn(payload2["foreman_observed"], (None, ""))
        self.assertTrue(payload2["content_hash"])

    def test_foreman_observed_is_raw_column_not_resolved_assignee(self):
        """The positive half of the raw-not-resolved regression: a row
        with a real 'Foreman' value AND a DIFFERENT resolved assignee
        (from 'Foreman Assigned?', per pipeline/fetch.py's fallback
        chain) must still produce foreman_observed == the raw 'Foreman'
        text, never the resolved value.
        """
        from pipeline_memory import writer as mem_writer

        row = {
            "__row_id": 1,
            "Work Request #": "90001",
            "Foreman": "Alice Primary",
            "Foreman Assigned?": "someone.else@example.com",
            "__effective_user": "someone.else@example.com",
        }
        payload = mem_writer._row_to_payload(row, "run-1", None, None)
        self.assertEqual(payload["foreman_observed"], "Alice Primary")

    def test_helper_and_vac_observed_are_raw_not_the_gated_derivative(self):
        """10-RESEARCH.md Task 2 behavior: helper_observed / vac_crew_
        observed read the RAW mapped columns ('Foreman Helping?' /
        'VAC Crew Helping?'), independent of the pipeline's gated
        __helper_foreman / __vac_crew_name keys -- which are ABSENT
        whenever the row's completion checkbox is unchecked. A row that
        plainly shows a helper/VAC name but hasn't been marked complete
        yet must still be observed, not silently dropped.
        """
        from pipeline_memory import writer as mem_writer

        row = {
            "__row_id": 1,
            "Work Request #": "90001",
            "Foreman Helping?": "Bob Helper",
            "Helping Foreman Completed Unit?": False,
            "VAC Crew Helping?": "Carl Vac",
            "Vac Crew Completed Unit?": False,
            # The pipeline's gated keys are deliberately ABSENT here --
            # fetch.py only sets them when the completion checkbox is
            # checked (lines ~537-624), exactly the case under test.
        }
        payload = mem_writer._row_to_payload(row, "run-1", None, None)
        self.assertEqual(payload["helper_observed"], "Bob Helper")
        self.assertFalse(payload["helper_completed"])
        self.assertEqual(payload["vac_crew_observed"], "Carl Vac")
        self.assertFalse(payload["vac_completed"])

    def test_missing_or_non_int_row_id_returns_none(self):
        """Mirrors billing_audit/writer.py::freeze_row's identical guard
        -- _row_to_payload never fabricates a row_id.
        """
        from pipeline_memory import writer as mem_writer

        self.assertIsNone(
            mem_writer._row_to_payload(
                {"Work Request #": "90001"}, "run-1", None, None,
            )
        )
        self.assertIsNone(
            mem_writer._row_to_payload(
                {"__row_id": "not-an-int", "Work Request #": "90001"},
                "run-1", None, None,
            )
        )

    def test_cu_and_pole_fall_back_through_synonyms(self):
        from pipeline_memory import writer as mem_writer

        row_cu_fallback = {
            "__row_id": 1, "Work Request #": "90001",
            "Billable Unit Code": "ANC-M",
            "Point #": "P-2",
        }
        payload = mem_writer._row_to_payload(
            row_cu_fallback, "run-1", None, None,
        )
        self.assertEqual(payload["cu"], "ANC-M")
        self.assertEqual(payload["pole"], "P-2")

    def test_week_ending_and_snapshot_date_use_caller_resolved_values(self):
        """_coerce_date accepts an ALREADY-RESOLVED date/datetime (never a
        raw string) -- mirrors billing_audit/writer.py::_coerce_week_ending.
        """
        import datetime as _dt

        from pipeline_memory import writer as mem_writer

        row = {"__row_id": 1, "Work Request #": "90001"}
        payload = mem_writer._row_to_payload(
            row, "run-1",
            _dt.datetime(2026, 8, 30),
            _dt.date(2026, 8, 1),
        )
        self.assertEqual(payload["week_ending"], "2026-08-30")
        self.assertEqual(payload["snapshot_date"], "2026-08-01")

        # A raw string is explicitly REFUSED, not parsed -- the caller
        # must resolve it first (10-RESEARCH.md interfaces contract).
        payload_raw_str = mem_writer._row_to_payload(
            row, "run-1", "2026-08-30", None,
        )
        self.assertIsNone(payload_raw_str["week_ending"])

    def test_hash_order_stability(self):
        from pipeline_memory import writer as mem_writer

        fields = {
            "wr": "90001",
            "week_ending": "2026-08-30",
            "snapshot_date": None,
            "cu": "ANC-M",
            "pole": "P-1",
            "work_type": "Maintenance",
            "quantity": 3,
            "units_total_price": 150.0,
            "units_completed": True,
            "foreman_observed": "Alice",
            "helper_observed": None,
            "helper_completed": False,
            "helper_dept": None,
            "helper_job": None,
            "vac_crew_observed": None,
            "vac_completed": False,
        }
        forward = {k: fields[k] for k in list(fields.keys())}
        reversed_order = {k: fields[k] for k in list(fields.keys())[::-1]}
        # Sanity: the two dicts really were built with different
        # insertion order (a no-op test otherwise).
        self.assertNotEqual(list(forward.items()), list(reversed_order.items()))
        self.assertEqual(
            mem_writer.compute_content_hash(forward),
            mem_writer.compute_content_hash(reversed_order),
        )

    def test_hash_excludes_row_modified_at_and_run_scoped_fields(self):
        """Two payloads built from rows differing ONLY in the row-modified
        timestamp (or, equivalently, any run-scoped field never fed into
        HASH_FIELDS) have equal content_hash; changing any single member
        of HASH_FIELDS changes it (10-RESEARCH.md Pitfall 3 -- a second
        run with no Smartsheet edits must add zero row_event rows).
        """
        from pipeline_memory import writer as mem_writer

        base_row = {
            "__row_id": 1, "Work Request #": "90001",
            "Foreman": "Alice", "CU": "ANC-M", "Quantity": "3",
        }
        row_t1 = dict(base_row, __row_modified_at="2026-08-24T10:00:00Z")
        row_t2 = dict(base_row, __row_modified_at="2026-08-25T11:30:00Z")
        payload_t1 = mem_writer._row_to_payload(row_t1, "run-1", None, None)
        payload_t2 = mem_writer._row_to_payload(row_t2, "run-2", None, None)
        self.assertNotEqual(payload_t1["row_modified_at"], payload_t2["row_modified_at"])
        self.assertEqual(payload_t1["content_hash"], payload_t2["content_hash"])

        # Changing a REAL HASH_FIELDS member (Foreman -> foreman_observed)
        # must change the hash.
        row_changed = dict(base_row, Foreman="Bob")
        payload_changed = mem_writer._row_to_payload(
            row_changed, "run-1", None, None,
        )
        self.assertNotEqual(
            payload_t1["content_hash"], payload_changed["content_hash"],
        )

    def test_adjacency_distinct_row_ids_both_present(self):
        from pipeline_memory import writer as mem_writer

        row_a = {
            "__row_id": 1, "Work Request #": "90001",
            "Foreman": "Alice", "CU": "ANC-M",
        }
        row_b = {
            "__row_id": 2, "Work Request #": "90001",
            "Foreman": "Alice", "CU": "ANC-M",
        }
        payload_a = mem_writer._row_to_payload(row_a, "run-1", None, None)
        payload_b = mem_writer._row_to_payload(row_b, "run-1", None, None)
        self.assertNotEqual(payload_a["row_id"], payload_b["row_id"])
        # Same business content -> same hash (builder never de-dupes by
        # content; that would be an (sheet_id, row_id) collision, not a
        # content one).
        self.assertEqual(payload_a["content_hash"], payload_b["content_hash"])

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_rows_bulk(999, "run-1", [row_a, row_b])

        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(len(params["p_rows"]), 2)
        self.assertEqual(
            {r["row_id"] for r in params["p_rows"]}, {1, 2},
        )

    def test_row_to_payload_reads_preparsed_numeric_keys_not_raw_cells(self):
        """_row_to_payload maps quantity/units_total_price from the
        caller-parsed __mem_quantity / __mem_units_total_price keys,
        never falling back to the raw 'Quantity' / 'Units Total Price'
        cell -- proven by giving the row a raw decorated cell that
        would fail the Postgres NUMERIC cast if it ever reached the
        payload, alongside the clean pre-parsed value that must win.
        """
        from pipeline_memory import writer as mem_writer

        row = {
            "__row_id": 1, "Work Request #": "90001",
            "Quantity": "12 ea", "Units Total Price": "$1,234.50",
            "__mem_quantity": 12.0, "__mem_units_total_price": 1234.5,
        }
        payload = mem_writer._row_to_payload(row, "run-1", None, None)
        self.assertEqual(payload["quantity"], 12.0)
        self.assertIsInstance(payload["quantity"], float)
        self.assertEqual(payload["units_total_price"], 1234.5)
        self.assertIsInstance(payload["units_total_price"], float)

    def test_absent_preparse_keys_yield_none_and_chunk_still_upserts(self):
        """WR-01: a row dict handed straight to _row_to_payload WITHOUT
        the caller's __mem_quantity / __mem_units_total_price pre-parse
        step yields None on both fields -- never the raw decorated
        'Quantity' / 'Units Total Price' cell value, which is exactly
        the value that fails the Postgres NUMERIC cast and drops the
        whole chunk under fail-open. The chunk still upserts; nothing
        is dropped.
        """
        from pipeline_memory import writer as mem_writer

        row = {
            "__row_id": 1, "Work Request #": "90001",
            "Quantity": "12 ea", "Units Total Price": "$1,234.50",
            # No __mem_quantity / __mem_units_total_price key at all --
            # the caller's pre-parse step never ran.
        }
        payload = mem_writer._row_to_payload(row, "run-1", None, None)
        self.assertIsNone(payload["quantity"])
        self.assertIsNone(payload["units_total_price"])

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            result = mem_writer.upsert_rows_bulk(1, "run-1", [row])

        self.assertIsNotNone(result)
        self.assertEqual(client.schema.return_value.rpc.call_count, 1)
        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(len(params["p_rows"]), 1)


@unittest.skipIf(
    _POSTGREST_API_ERROR_CLS is None,
    "postgrest not installed — skipping counter/PII discipline tests "
    "that force an RPC failure.",
)
class CounterAndPiiDisciplineTests(unittest.TestCase):
    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def _raise_pgrst106(self, *_a, **_kw):
        raise _POSTGREST_API_ERROR_CLS({
            "code": "PGRST106", "message": "x", "hint": "", "details": "",
        })

    def test_get_counters_returns_dict_of_ints(self):
        from pipeline_memory import writer as mem_writer

        counters = mem_writer.get_counters()
        self.assertIsInstance(counters, dict)
        for value in counters.values():
            self.assertIsInstance(value, int)

    def test_forced_rpc_failure_bumps_errored_and_sent_but_not_changed(self):
        """A single-chunk RPC failure still counts the row as SENT
        (attempted) and ERRORED, but never CHANGED -- 'sent' tracks every
        row handed to the bulk upsert (MEM-02: "every accepted row ... is
        sent to the bulk upsert exactly once per run"), regardless of
        whether the RPC round-trip itself succeeded.
        """
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.rpc.return_value.execute.side_effect = (
            self._raise_pgrst106
        )
        row = {"__row_id": 1, "Work Request #": "90001", "Foreman": "Alice"}

        before = mem_writer.get_counters()
        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_rows_bulk(1, "run-1", [row])
        after = mem_writer.get_counters()

        self.assertEqual(
            after.get("rows_upsert_errored", 0),
            before.get("rows_upsert_errored", 0) + 1,
        )
        self.assertEqual(
            after.get("rows_upsert_sent", 0),
            before.get("rows_upsert_sent", 0) + 1,
        )
        self.assertEqual(
            after.get("rows_upsert_changed", 0),
            before.get("rows_upsert_changed", 0),
        )
        # An unrelated counter family (run_ledger) must be untouched by
        # a rows_upsert-only failure.
        self.assertEqual(
            after.get("run_ledger_errored", 0),
            before.get("run_ledger_errored", 0),
        )
        self.assertEqual(
            after.get("run_ledger_written", 0),
            before.get("run_ledger_written", 0),
        )

    def test_bad_row_id_bumps_skipped_counter(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        before = mem_writer.get_counters()

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            result = mem_writer.upsert_rows_bulk(
                1, "run-1", [{"Work Request #": "90001"}],
            )
        after = mem_writer.get_counters()

        self.assertEqual(result, set())
        client.schema.assert_not_called()
        self.assertEqual(
            after.get("rows_skipped_bad_row_id", 0),
            before.get("rows_skipped_bad_row_id", 0) + 1,
        )

    def test_no_writer_log_record_contains_a_personnel_value(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.rpc.return_value.execute.side_effect = (
            self._raise_pgrst106
        )
        row = {
            "__row_id": 1,
            "Work Request #": "90001",
            "Foreman": "Alice VerySecretName",
            "Foreman Helping?": "Bob VerySecretHelper",
            "VAC Crew Helping?": "Carl VerySecretVac",
        }

        # The forced PGRST106 failure guarantees at least one WARNING
        # log record exists to inspect (assertLogs requires >= 1).
        with self.assertLogs(level="WARNING") as cm, mock.patch(
            "pipeline_memory.writer.get_client", return_value=client
        ):
            mem_writer.upsert_rows_bulk(1, "run-1", [row])

        combined = "\n".join(cm.output)
        for secret in (
            "Alice VerySecretName",
            "Bob VerySecretHelper",
            "Carl VerySecretVac",
        ):
            self.assertNotIn(secret, combined)


class ChunkingAndPayloadSizeTests(unittest.TestCase):
    """Task 2 (10-RESEARCH.md Pitfall 4): 'one RPC per sheet' means 'not
    one RPC per row' -- the largest observed source sheet (6,054 rows,
    design spec section 2, run 32743959053) must be safely chunked, and a
    full chunk's serialised JSON body must stay well under PostgREST's
    ~1MB request-body limit.
    """

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def _rows(self, n, *, sheet_id=1):
        return [
            {
                "__row_id": i,
                "Work Request #": f"9{i:05d}",
                "Foreman": f"Foreman {i}",
                "CU": "ANC-M",
                "Pole #": f"P-{i}",
                "Work Type": "Maintenance",
                "Quantity": "3",
                "Units Total Price": "150.00",
                "Units Completed?": True,
            }
            for i in range(n)
        ]

    def test_6054_row_input_yields_13_chunked_rpc_invocations(self):
        import math

        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        rows = self._rows(6054)

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_rows_bulk(1, "run-1", rows)

        expected_chunks = math.ceil(6054 / mem_writer._CHUNK_ROWS)
        self.assertEqual(expected_chunks, 13)
        self.assertEqual(
            client.schema.return_value.rpc.call_count, expected_chunks,
        )
        seen_row_ids: set = set()
        for call in client.schema.return_value.rpc.call_args_list:
            _, params = call.args
            self.assertLessEqual(len(params["p_rows"]), mem_writer._CHUNK_ROWS)
            self.assertEqual(params["p_sheet_id"], 1)
            self.assertEqual(params["p_run_id"], "run-1")
            seen_row_ids.update(r["row_id"] for r in params["p_rows"])
        self.assertEqual(len(seen_row_ids), 6054)

    def test_full_chunk_payload_stays_under_postgrest_body_limit(self):
        """Asserts the measured size AND prints bytes/row for the SUMMARY
        (10-RESEARCH.md Pitfall 4 acceptance criterion).
        """
        import json

        from pipeline_memory import writer as mem_writer

        rows = self._rows(mem_writer._CHUNK_ROWS)
        payloads = [
            mem_writer._row_to_payload(r, "run-1", None, None) for r in rows
        ]
        self.assertEqual(len(payloads), mem_writer._CHUNK_ROWS)
        body = json.dumps(payloads, default=str).encode("utf-8")
        bytes_per_row = len(body) / len(payloads)
        print(
            f"[pipeline_memory] measured {len(body)} bytes for a full "
            f"{mem_writer._CHUNK_ROWS}-row chunk "
            f"({bytes_per_row:.1f} bytes/row)"
        )
        self.assertLess(len(body), 1_048_576)


@unittest.skipIf(
    _POSTGREST_API_ERROR_CLS is None,
    "postgrest not installed — skipping chunk fail-open tests that force "
    "an RPC failure.",
)
class ChunkFailOpenTests(unittest.TestCase):
    """Task 2: a middle chunk's failure must not lose the successful
    chunks' affected set, must bump the errored counter, must log exactly
    ONE aggregate WARNING for the whole call (not one per chunk), and must
    never raise.
    """

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def test_middle_chunk_failure_keeps_other_chunks_affected_set(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        chunk_rows = mem_writer._CHUNK_ROWS
        rows = [
            {
                "__row_id": i,
                "Work Request #": f"9{i:05d}",
                "Foreman": "Alice",
            }
            for i in range(chunk_rows + 5)  # 2 chunks: 500 + 5
        ]

        call_count = {"n": 0}

        def _side_effect(*_a, **_kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return mock.Mock(
                    data=[{"wr": "900001", "week_ending": "2026-08-30"}],
                )
            raise _POSTGREST_API_ERROR_CLS({
                "code": "PGRST106", "message": "x", "hint": "", "details": "",
            })

        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.rpc.return_value.execute.side_effect = (
            _side_effect
        )

        with self.assertLogs(level="WARNING") as cm, mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            # Reset the independent kill switch between the two chunk
            # calls would normally short-circuit call #2 -- but PGRST106
            # trips the run-global kill switch on the FIRST failing
            # chunk, so with_retry's own global-kill guard would skip
            # any FURTHER chunk after that one. This test therefore
            # asserts the documented behavior: chunk 1 succeeds BEFORE
            # the kill trips, chunk 2 fails and trips it, and the
            # returned set reflects exactly the chunks that completed
            # before the trip -- never raises, never loses chunk 1's
            # affected set.
            result = mem_writer.upsert_rows_bulk(1, "run-1", rows)

        self.assertEqual(result, {("900001", "2026-08-30")})
        aggregate_warnings = [
            line for line in cm.output
            if "pipeline_memory upsert_rows_bulk:" in line
        ]
        self.assertEqual(len(aggregate_warnings), 1)
        self.assertGreaterEqual(
            mem_writer.get_counters()["rows_upsert_errored"], 1,
        )


class AffectedSetParsingTests(unittest.TestCase):
    def test_none_response_data_yields_empty_set_never_none(self):
        from pipeline_memory.writer import _parse_affected_set

        self.assertEqual(_parse_affected_set(mock.Mock(data=None)), set())

    def test_malformed_response_rows_are_skipped_not_raised(self):
        from pipeline_memory.writer import _parse_affected_set

        result = _parse_affected_set(mock.Mock(data=[
            "not-a-dict", 42, None,
            {"wr": "90001", "week_ending": "2026-08-30"},
        ]))
        self.assertEqual(result, {("90001", "2026-08-30")})

    def test_upsert_rows_bulk_never_returns_none(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            mock.Mock(data=None)
        )
        row = {"__row_id": 1, "Work Request #": "90001"}

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            result = mem_writer.upsert_rows_bulk(1, "run-1", [row])

        self.assertIsNotNone(result)
        self.assertEqual(result, set())


class MemoryWritePhaseTests(unittest.TestCase):
    """Task 3 (MEM-02/MEM-03): pipeline.orchestrate._run_memory_write_phase
    -- the budgeted, sequential per-sheet memory-write loop wired into
    main() immediately after Phase 2 completes. Patches the module-level
    constants pipeline.orchestrate imports from pipeline.config (the
    established pattern for overriding a name read at import time --
    see tests/test_snapshot_drift_audit.py) rather than mutating
    os.environ, which pipeline.config already resolved before these
    tests run.
    """

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def _rows(self, sheet_id, n, start_id=1):
        return [
            {
                "__row_id": start_id + i,
                "__source_sheet_id": sheet_id,
                "Work Request #": f"9{start_id + i:05d}",
                "Foreman": "Alice",
                "Weekly Reference Logged Date": "2026-08-30",
            }
            for i in range(n)
        ]

    def test_flag_off_performs_zero_writer_calls(self):
        import datetime

        import pipeline.orchestrate as orch

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", False), \
             mock.patch.object(
                 orch._mem_writer, "upsert_rows_bulk_result"
             ) as mock_upsert:
            result = orch._run_memory_write_phase(
                self._rows(111, 2), "run-1", datetime.datetime.now(),
            )

        mock_upsert.assert_not_called()
        self.assertEqual(result["sheets_written"], 0)
        self.assertEqual(result["sheets_errored"], 0)
        self.assertEqual(result["rows_sent"], 0)
        self.assertEqual(result["rows_changed"], 0)

    def test_flag_on_calls_writer_once_per_sheet_with_bucketed_rows(self):
        import datetime

        import pipeline.orchestrate as orch

        rows = self._rows(111, 2, start_id=1) + self._rows(222, 1, start_id=3)

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
             mock.patch.object(orch, "TEST_MODE", False), \
             mock.patch.object(
                 orch._mem_writer, "upsert_rows_bulk_result",
                 return_value={
                     "affected": set(), "status": "ok", "rows_sent": 0,
                     "rows_errored": 0, "rows_skipped": 0,
                 },
             ) as mock_upsert:
            result = orch._run_memory_write_phase(
                rows, "run-1", datetime.datetime.now(),
            )

        self.assertEqual(mock_upsert.call_count, 2)
        calls_by_sheet = {
            call.args[0]: call.args[2]
            for call in mock_upsert.call_args_list
        }
        self.assertEqual(len(calls_by_sheet[111]), 2)
        self.assertEqual(len(calls_by_sheet[222]), 1)
        self.assertEqual(result["rows_sent"], 3)
        self.assertEqual(result["sheets_written"], 0)  # empty affected sets

    def test_writer_failure_on_first_sheet_still_processes_second(self):
        import datetime

        import pipeline.orchestrate as orch

        rows = self._rows(111, 1, start_id=1) + self._rows(222, 1, start_id=2)
        call_order: list = []

        def _side_effect(sheet_id, run_id, bucket_rows):
            call_order.append(sheet_id)
            if sheet_id == 111:
                raise RuntimeError("boom")
            return {
                "affected": set(), "status": "ok", "rows_sent": 1,
                "rows_errored": 0, "rows_skipped": 0,
            }

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
             mock.patch.object(orch, "TEST_MODE", False), \
             mock.patch.object(
                 orch._mem_writer, "upsert_rows_bulk_result",
                 side_effect=_side_effect,
             ):
            result = orch._run_memory_write_phase(
                rows, "run-1", datetime.datetime.now(),
            )

        # Both sheets were attempted, in order -- the first sheet's
        # exception never propagated and never stopped the second.
        self.assertEqual(call_order, [111, 222])
        self.assertEqual(result["sheets_errored"], 1)
        self.assertEqual(result["rows_sent"], 2)

    def test_preflight_guard_skips_when_subbudget_already_exhausted(self):
        import datetime

        import pipeline.orchestrate as orch

        stale_session_start = (
            datetime.datetime.now() - datetime.timedelta(minutes=200)
        )

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
             mock.patch.object(orch, "TEST_MODE", False), \
             mock.patch.object(orch, "TIME_BUDGET_MINUTES", 165), \
             mock.patch.object(orch, "GITHUB_ACTIONS_MODE", True), \
             mock.patch.object(orch, "RUN_MEMORY_WRITE_MAX_MINUTES", 10), \
             mock.patch.object(
                 orch, "RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN", 2,
             ), \
             mock.patch.object(
                 orch._mem_writer, "upsert_rows_bulk_result"
             ) as mock_upsert:
            result = orch._run_memory_write_phase(
                self._rows(111, 2), "run-1", stale_session_start,
            )

        mock_upsert.assert_not_called()
        self.assertEqual(result["sheets_written"], 0)
        self.assertEqual(result["rows_sent"], 0)

    def test_midloop_budget_exhaustion_breaks_before_second_sheet(self):
        import datetime

        import pipeline.orchestrate as orch

        rows = self._rows(111, 1, start_id=1) + self._rows(222, 1, start_id=2)

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
             mock.patch.object(orch, "TEST_MODE", False), \
             mock.patch.object(orch, "TIME_BUDGET_MINUTES", 165), \
             mock.patch.object(orch, "GITHUB_ACTIONS_MODE", True), \
             mock.patch.object(orch, "RUN_MEMORY_WRITE_MAX_MINUTES", 0), \
             mock.patch.object(
                 orch._mem_writer, "upsert_rows_bulk_result",
                 return_value={
                     "affected": set(), "status": "ok", "rows_sent": 0,
                     "rows_errored": 0, "rows_skipped": 0,
                 },
             ) as mock_upsert:
            result = orch._run_memory_write_phase(
                rows, "run-1", datetime.datetime.now(),
            )

        # Sheet 1 gets written; the per-iteration check (0min budget) then
        # fires immediately after it, breaking BEFORE sheet 2.
        self.assertEqual(mock_upsert.call_count, 1)
        self.assertEqual(result["rows_sent"], 1)

    def test_end_to_end_decorated_numeric_reaches_rpc_payload_as_float(self):
        """Task 1 (WR-01) tracer: a decorated 'Quantity' / 'Units Total
        Price' cell travels from the orchestrate caller's pre-parse,
        through the __mem_quantity / __mem_units_total_price row keys,
        into the REAL upsert_rows_bulk -> _row_to_payload RPC payload
        as a float -- never a raw decorated string that fails the
        Postgres NUMERIC cast and drops the whole 500-row chunk under
        fail-open. Only the transport (Supabase client) is faked; the
        writer stack runs for real end to end.
        """
        import datetime

        import pipeline.orchestrate as orch

        rows = [{
            "__row_id": 1,
            "__source_sheet_id": 111,
            "Work Request #": "90001",
            "Foreman": "Alice",
            "Quantity": "12 ea",
            "Units Total Price": "$1,234.50",
        }]

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
                mock.patch.object(orch, "TEST_MODE", False), \
                mock.patch(
                    "pipeline_memory.writer.get_client", return_value=client,
                ):
            orch._run_memory_write_phase(
                rows, "run-1", datetime.datetime.now(),
            )

        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(len(params["p_rows"]), 1)
        payload = params["p_rows"][0]
        self.assertEqual(payload["quantity"], 12.0)
        self.assertIsInstance(payload["quantity"], float)
        self.assertEqual(payload["units_total_price"], 1234.5)
        self.assertIsInstance(payload["units_total_price"], float)

    def test_quantity_preparse_is_idempotent_and_none_for_empty(self):
        """Caller-side pre-parse (orchestrate.py) stashes
        __mem_quantity / __mem_units_total_price on each row dict
        before calling upsert_rows_bulk: a clean float is unchanged
        (idempotent, no-op parse), and an empty/absent cell stays None
        -- never the pricing module's own 0.0-for-missing business
        default, which would fabricate an observed zero quantity that
        was never actually on the row.
        """
        import datetime

        import pipeline.orchestrate as orch

        rows = [
            {
                "__row_id": 1, "__source_sheet_id": 111,
                "Work Request #": "90001", "Quantity": 3.0,
            },
            {
                "__row_id": 2, "__source_sheet_id": 111,
                "Work Request #": "90002", "Quantity": None,
                "Units Total Price": "",
            },
        ]

        with mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
                mock.patch.object(orch, "TEST_MODE", False), \
                mock.patch.object(
                    orch._mem_writer, "upsert_rows_bulk_result",
                 return_value={
                     "affected": set(), "status": "ok", "rows_sent": 0,
                     "rows_errored": 0, "rows_skipped": 0,
                 },
                ) as mock_upsert:
            orch._run_memory_write_phase(
                rows, "run-1", datetime.datetime.now(),
            )

        bucket_rows = mock_upsert.call_args.args[2]
        self.assertEqual(bucket_rows[0]["__mem_quantity"], 3.0)
        self.assertIsNone(bucket_rows[1]["__mem_quantity"])
        self.assertIsNone(bucket_rows[1]["__mem_units_total_price"])


# ============================================================================
# Plan 10-03: sheet_registry + group_state (the remaining two MEM-01 tables)
# ============================================================================


class SheetVersionWatermarkTests(unittest.TestCase):
    """Task 1: pipeline.fetch._LAST_SHEET_VERSIONS / get_last_sheet_versions.

    The actual capture line (inside _fetch_and_process_sheet, deep in a
    ThreadPoolExecutor-driven closure) is proven correct the same way
    10-02's __row_modified_at capture was (see that plan's SUMMARY.md
    Issues Encountered): live SDK introspection + the full test suite +
    bash scripts/run_6_gates.sh, not a full mocked Sheet/Row fixture
    (none exists in this file's precedent). These tests prove the
    CONTRACT the capture line depends on: the module-level store's
    accessor returns a defensive copy, and getattr(obj, 'version', None)
    -- the exact idiom the capture line uses -- never raises when the
    attribute is absent.
    """

    def setUp(self):
        import pipeline.fetch as pf
        with pf._LAST_SHEET_VERSIONS_LOCK:
            pf._LAST_SHEET_VERSIONS.clear()

    def tearDown(self):
        import pipeline.fetch as pf
        with pf._LAST_SHEET_VERSIONS_LOCK:
            pf._LAST_SHEET_VERSIONS.clear()

    def test_empty_by_default(self):
        import pipeline.fetch as pf

        self.assertEqual(pf.get_last_sheet_versions(), {})

    def test_returns_defensive_copy(self):
        import pipeline.fetch as pf

        with pf._LAST_SHEET_VERSIONS_LOCK:
            pf._LAST_SHEET_VERSIONS[111] = 42
        snapshot = pf.get_last_sheet_versions()
        self.assertEqual(snapshot, {111: 42})

        snapshot[222] = 99  # mutating the returned copy...
        self.assertEqual(pf.get_last_sheet_versions(), {111: 42})  # ...must not leak back

    def test_missing_version_attribute_yields_none_without_raising(self):
        class _NoVersionSheet:
            pass

        self.assertIsNone(getattr(_NoVersionSheet(), 'version', None))


class SheetKindClassificationTests(unittest.TestCase):
    """Task 1: pipeline.orchestrate._resolve_mem_sheet_kind."""

    def test_subcontractor_static_set(self):
        import pipeline.discovery as disc
        import pipeline.orchestrate as orch

        with mock.patch.object(disc, "SUBCONTRACTOR_SHEET_IDS", {111}), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_SUB_IDS", set()), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_ORIG_IDS", set()):
            self.assertEqual(orch._resolve_mem_sheet_kind(111), "subcontractor")

    def test_subcontractor_folder_discovered_set(self):
        import pipeline.discovery as disc
        import pipeline.orchestrate as orch

        with mock.patch.object(disc, "SUBCONTRACTOR_SHEET_IDS", set()), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_SUB_IDS", {222}), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_ORIG_IDS", set()):
            self.assertEqual(orch._resolve_mem_sheet_kind(222), "subcontractor")

    def test_original_contract_set(self):
        import pipeline.discovery as disc
        import pipeline.orchestrate as orch

        with mock.patch.object(disc, "SUBCONTRACTOR_SHEET_IDS", set()), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_SUB_IDS", set()), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_ORIG_IDS", {333}):
            self.assertEqual(orch._resolve_mem_sheet_kind(333), "original_contract")

    def test_default_primary(self):
        import pipeline.discovery as disc
        import pipeline.orchestrate as orch

        with mock.patch.object(disc, "SUBCONTRACTOR_SHEET_IDS", set()), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_SUB_IDS", set()), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_ORIG_IDS", set()):
            self.assertEqual(orch._resolve_mem_sheet_kind(444), "primary")

    def test_return_value_always_in_ddl_check_set(self):
        """No sheet is ever classified with a value the DDL's CHECK
        constraint rejects -- 'vac_crew' must never be returned."""
        import pipeline.discovery as disc
        import pipeline.orchestrate as orch

        allowed = {"primary", "subcontractor", "original_contract"}
        with mock.patch.object(disc, "SUBCONTRACTOR_SHEET_IDS", {1}), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_SUB_IDS", {2}), \
             mock.patch.object(disc, "_FOLDER_DISCOVERED_ORIG_IDS", {3}):
            for sid in (1, 2, 3, 4):
                self.assertIn(orch._resolve_mem_sheet_kind(sid), allowed)


class SheetRegistryWriterTests(unittest.TestCase):
    """Task 1: pipeline_memory.writer.upsert_sheet_registry."""

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def _sheets(self):
        return [
            {"id": 111, "name": "Sheet A", "column_mapping": {"Foreman": 1}},
            {"id": 222, "name": "Sheet B", "column_mapping": {"Foreman": 2}},
        ]

    def test_empty_input_zero_calls(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_sheet_registry([], "run-1", lambda sid: "primary", {})

        client.schema.assert_not_called()

    def test_non_empty_issues_one_upsert_with_on_conflict_sheet_id(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = _make_fake_pipeline_memory_client(upsert_capture=upsert_capture)

        def _kind(sid):
            return "subcontractor" if sid == 111 else "primary"

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_sheet_registry(
                self._sheets(), "run-1", _kind, {111: 42},
            )

        self.assertEqual(len(upsert_capture), 1)
        call = upsert_capture[0]
        self.assertEqual(call.kwargs.get("on_conflict"), "sheet_id")
        payload = call.args[0]
        self.assertEqual(len(payload), 2)

        row_a = next(r for r in payload if r["sheet_id"] == 111)
        self.assertEqual(row_a["kind"], "subcontractor")
        self.assertEqual(row_a["last_sheet_version"], 42)
        self.assertNotIn("folder_id", row_a)
        self.assertTrue(row_a["active"])

        row_b = next(r for r in payload if r["sheet_id"] == 222)
        self.assertEqual(row_b["kind"], "primary")
        self.assertIsNone(row_b["last_sheet_version"])
        self.assertNotIn("folder_id", row_b)

    def test_fail_open_bumps_errored_counter(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.table.return_value.upsert.return_value.execute.side_effect = (
            RuntimeError("boom")
        )

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_sheet_registry(
                self._sheets(), "run-1", lambda sid: "primary", {},
            )

        self.assertEqual(
            mem_writer.get_counters()["sheets_registry_errored"], 2,
        )
        self.assertEqual(
            mem_writer.get_counters().get("sheets_registry_written", 0), 0,
        )


class GroupStateWriterTests(unittest.TestCase):
    """Task 2: pipeline_memory.writer.upsert_group_state /
    bump_group_state_withheld."""

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def _base_record(self, **overrides):
        rec = {
            "wr": "90001", "week_ending": "2026-08-30",
            "variant": "reduced_sub", "identifier": "",
            "target_sheet_id": 111,
            "content_hash": "abc123", "row_count": 5,
        }
        rec.update(overrides)
        return rec

    def test_empty_input_zero_calls(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_group_state([], "run-1")

        client.schema.assert_not_called()

    def test_one_upsert_with_on_conflict_and_core_columns(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = _make_fake_pipeline_memory_client(upsert_capture=upsert_capture)

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_group_state([self._base_record()], "run-42")

        self.assertEqual(len(upsert_capture), 1)
        call = upsert_capture[0]
        self.assertEqual(
            call.kwargs.get("on_conflict"),
            "wr,week_ending,variant,identifier,target_sheet_id",
        )
        row = call.args[0][0]
        self.assertEqual(row["content_hash"], "abc123")
        self.assertEqual(row["row_count"], 5)
        self.assertEqual(row["source"], "live")
        self.assertEqual(row["last_generated_run"], "run-42")
        self.assertEqual(row["last_verified_run"], "run-42")

    def test_attachment_present_includes_both_keys(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = _make_fake_pipeline_memory_client(upsert_capture=upsert_capture)
        rec = self._base_record(attachment_id=555, attachment_name="a.xlsx")

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_group_state([rec], "run-1")

        row = upsert_capture[0].args[0][0]
        self.assertEqual(row["attachment_id"], 555)
        self.assertEqual(row["attachment_name"], "a.xlsx")

    def test_attachment_absent_omits_both_keys_entirely(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = _make_fake_pipeline_memory_client(upsert_capture=upsert_capture)

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_group_state([self._base_record()], "run-1")

        row = upsert_capture[0].args[0][0]
        self.assertNotIn("attachment_id", row)
        self.assertNotIn("attachment_name", row)

    def test_fan_out_two_target_sheet_ids_produce_two_distinct_rows(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        upsert_capture: list = []
        client = _make_fake_pipeline_memory_client(upsert_capture=upsert_capture)
        records = [
            self._base_record(target_sheet_id=111, attachment_id=1, attachment_name="a.xlsx"),
            self._base_record(target_sheet_id=222, attachment_id=2, attachment_name="b.xlsx"),
        ]

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_group_state(records, "run-1")

        payload = upsert_capture[0].args[0]
        self.assertEqual(len(payload), 2)
        by_sheet = {r["target_sheet_id"]: r for r in payload}
        self.assertEqual(by_sheet[111]["attachment_id"], 1)
        self.assertEqual(by_sheet[222]["attachment_id"], 2)
        self.assertNotEqual(by_sheet[111], by_sheet[222])

    def test_fail_open_bumps_errored_counter_by_row_count(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()
        client.schema.return_value.table.return_value.upsert.return_value.execute.side_effect = (
            RuntimeError("boom")
        )
        records = [
            self._base_record(target_sheet_id=111),
            self._base_record(target_sheet_id=222),
        ]

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            mem_writer.upsert_group_state(records, "run-1")

        self.assertEqual(mem_writer.get_counters()["group_state_errored"], 2)

    def test_bump_group_state_withheld(self):
        from pipeline_memory import writer as mem_writer

        mem_writer.bump_group_state_withheld(3)
        self.assertEqual(mem_writer.get_counters()["group_state_withheld"], 3)


class AttachmentSideChannelTests(unittest.TestCase):
    """Task 2: pipeline.orchestrate._extract_attachment_id_name (pure,
    directly unit-tested) plus _upload_one's STRUCTURAL contract, proven
    via source inspection -- _upload_one is a closure nested inside
    main() (exactly like the delete-then-upload ordering already proven
    this way in tests/test_skip_upload_delete_gating.py), not directly
    invocable without running the whole session.
    """

    def test_extract_success_case(self):
        import pipeline.orchestrate as orch

        attach = mock.Mock()
        # NOTE: Mock(name=...) sets the mock's OWN repr name, not a
        # `.name` attribute -- must be set post-construction.
        attach.data = mock.Mock(id=999)
        attach.data.name = "foo.xlsx"
        self.assertEqual(
            orch._extract_attachment_id_name(attach), (999, "foo.xlsx"),
        )

    def test_extract_missing_data_attribute_returns_none_without_raising(self):
        import pipeline.orchestrate as orch

        attach = mock.Mock(spec=[])  # no .data attribute at all
        self.assertEqual(
            orch._extract_attachment_id_name(attach), (None, None),
        )

    def test_extract_none_result_returns_none_without_raising(self):
        import pipeline.orchestrate as orch

        self.assertEqual(
            orch._extract_attachment_id_name(None), (None, None),
        )

    def test_upload_one_source_delete_precedes_attach(self):
        import inspect

        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        fn_start = src.index("def _upload_one")
        delete_idx = src.index("delete_old_excel_attachments(", fn_start)
        attach_idx = src.index("attach_file_to_row(", fn_start)
        self.assertLess(delete_idx, attach_idx)

    def test_upload_one_source_returns_only_four_known_strings(self):
        import inspect

        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        fn_start = src.index("def _upload_one")
        fn_end = src.index("upload_results = list(executor.map", fn_start)
        body = src[fn_start:fn_end]
        returned = set(re.findall(r"return '([a-z_]+)'", body))
        self.assertEqual(
            returned, {'uploaded', 'skipped', 'skip_upload', 'error'},
        )

    def test_attachment_capture_wrapped_in_its_own_try_except(self):
        import inspect

        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        fn_start = src.index("def _upload_one")
        # Find the CALL site (not the def), which is inside _upload_one.
        capture_idx = src.index("_extract_attachment_id_name(", fn_start + 1)
        surrounding = src[max(0, capture_idx - 150):capture_idx + 900]
        self.assertIn("try:", surrounding)
        self.assertIn("except Exception:", surrounding)

    def test_side_channel_keyed_by_four_part_tuple(self):
        """Structural proof of the key shape -- (group_key, variant,
        file_identifier, target_sheet_id), read from task[...] -- so a
        reduced_sub fan-out's two legs (same group_key/variant, distinct
        target_sheet_id) never collide."""
        import inspect

        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        fn_start = src.index("def _upload_one")
        fn_end = src.index("upload_results = list(executor.map", fn_start)
        body = src[fn_start:fn_end]
        key_idx = body.index("_mem_key = (")
        key_src = body[key_idx:key_idx + 200]
        for token in (
            "task['group_key']", "task['variant']",
            "task['file_identifier']", "task['target_sheet_id']",
        ):
            self.assertIn(token, key_src)


class GroupStateFlushComputationTests(unittest.TestCase):
    """Task 3: pipeline.orchestrate._build_group_state_flush -- the PURE
    post-upload flush computation (withhold-on-not-ok, reduced_sub
    two-row expansion, attachment lookup by the 4-part side-channel
    key). Extracted as a standalone function (mirrors
    _run_memory_write_phase's testability pattern, 10-02 key-decision)
    specifically so these scenarios are directly unit-testable without
    invoking main()'s full Smartsheet/Excel/Sentry machinery.
    """

    def test_reduced_sub_two_leg_produces_two_distinct_records(self):
        import pipeline.orchestrate as orch

        deferred = [{
            'group_key': 'gk1', 'wr_num': '90001', 'week_iso': '2026-08-30',
            'variant': 'reduced_sub', 'identifier': '', 'file_identifier': '',
            'data_hash': 'hash1', 'row_count': 7,
        }]
        upload_ok = {'gk1': True}
        upload_tasks = [
            {'group_key': 'gk1', 'target_sheet_id': 111},
            {'group_key': 'gk1', 'target_sheet_id': 222},
        ]
        side_channel = {
            ('gk1', 'reduced_sub', '', 111): {'attachment_id': 1, 'attachment_name': 'a.xlsx'},
            ('gk1', 'reduced_sub', '', 222): {'attachment_id': 2, 'attachment_name': 'b.xlsx'},
        }

        records, withheld = orch._build_group_state_flush(
            deferred, upload_ok, upload_tasks, side_channel,
        )

        self.assertEqual(withheld, 0)
        self.assertEqual(len(records), 2)
        by_sheet = {r['target_sheet_id']: r for r in records}
        self.assertEqual(by_sheet[111]['attachment_id'], 1)
        self.assertEqual(by_sheet[222]['attachment_id'], 2)

    def test_group_with_error_leg_is_withheld_entirely(self):
        import pipeline.orchestrate as orch

        deferred = [{
            'group_key': 'gk2', 'wr_num': '90002', 'week_iso': '2026-08-30',
            'variant': 'primary', 'identifier': '', 'file_identifier': '',
            'data_hash': 'hash2', 'row_count': 3,
        }]
        upload_ok = {'gk2': False}  # a leg errored -> group not ok
        upload_tasks = [{'group_key': 'gk2', 'target_sheet_id': 111}]

        records, withheld = orch._build_group_state_flush(
            deferred, upload_ok, upload_tasks, {},
        )

        self.assertEqual(records, [])
        self.assertEqual(withheld, 1)

    def test_skip_upload_scenario_no_row_advances(self):
        """SKIP_UPLOAD makes every leg report 'skip_upload', which the
        caller's zip loop (mirrored here) marks _ok = False (not in
        ('uploaded', 'skipped')) -- upload_ok is False for every group,
        so no group_state record is produced."""
        import pipeline.orchestrate as orch

        deferred = [{
            'group_key': 'gk3', 'wr_num': '90003', 'week_iso': '2026-08-30',
            'variant': 'primary', 'identifier': '', 'file_identifier': '',
            'data_hash': 'hash3', 'row_count': 4,
        }]
        upload_ok = {'gk3': False}  # skip_upload -> not ('uploaded', 'skipped')
        upload_tasks = [{'group_key': 'gk3', 'target_sheet_id': 111}]

        records, withheld = orch._build_group_state_flush(
            deferred, upload_ok, upload_tasks, {},
        )

        self.assertEqual(records, [])
        self.assertEqual(withheld, 1)

    def test_flush_positioned_after_both_existing_flushes_and_writer_call_guarded(self):
        """The group_state flush computation/call happens strictly AFTER
        both the local hash-history flush and the durable hash-store
        flush in source order, and the writer call is wrapped in its
        own try/except -- so a raising writer cannot prevent (or ever
        run before) the two earlier, production-critical flushes."""
        import inspect

        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        json_flush_idx = src.index("Local hash-history entry withheld")
        durable_hash_idx = src.index("🧾 Durable hash store:")
        group_state_call_idx = src.index("_build_group_state_flush(")
        # The def-site is the FIRST occurrence; find the CALL site (the
        # SECOND occurrence, inside main()'s flush block) explicitly.
        group_state_call_idx = src.index(
            "_build_group_state_flush(", group_state_call_idx + 1,
        )
        self.assertLess(json_flush_idx, durable_hash_idx)
        self.assertLess(durable_hash_idx, group_state_call_idx)

        writer_call_idx = src.index("_mem_writer.upsert_group_state(")
        preceding = src[max(0, writer_call_idx - 200):writer_call_idx]
        self.assertIn("try:", preceding)

    def test_zero_deferred_records_never_calls_writer(self):
        import inspect

        import pipeline.orchestrate as orch

        records, withheld = orch._build_group_state_flush([], {}, [], {})
        self.assertEqual(records, [])
        self.assertEqual(withheld, 0)

        src = inspect.getsource(orch)
        guard_idx = src.index(
            "if RUN_MEMORY_WRITE_ENABLED and _deferred_group_state:"
        )
        call_idx = src.index("_mem_writer.upsert_group_state(")
        self.assertLess(guard_idx, call_idx)


if __name__ == "__main__":
    unittest.main()


class RpcTimeoutWiringTests(unittest.TestCase):
    """T-10-04 / REVIEW WR-02: RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC must bound
    every PostgREST call, not merely exist in config."""

    def setUp(self):
        import pipeline_memory.client as mem_client
        mem_client.reset_cache_for_tests()
        self.mem_client = mem_client

    def tearDown(self):
        self.mem_client.reset_cache_for_tests()

    def _build_with_env(self, extra_env):
        env = {"SUPABASE_URL": "https://example.invalid",
               "SUPABASE_SERVICE_ROLE_KEY": "not-a-real-key",
               "TEST_MODE": ""}
        env.update(extra_env)
        captured = {}

        def fake_create_client(url, key, options=None):
            captured["options"] = options
            return object()

        with mock.patch.dict(os.environ, env, clear=False),                 mock.patch("supabase.create_client", fake_create_client):
            client = self.mem_client.get_client()
        return client, captured

    def test_default_timeout_is_passed_to_postgrest_client(self):
        client, captured = self._build_with_env(
            {"RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC": ""})
        self.assertIsNotNone(client)
        self.assertIsNotNone(captured["options"])
        self.assertEqual(captured["options"].postgrest_client_timeout, 45)

    def test_env_override_is_honoured(self):
        client, captured = self._build_with_env(
            {"RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC": "7"})
        self.assertIsNotNone(client)
        self.assertEqual(captured["options"].postgrest_client_timeout, 7)

    def test_garbage_or_zero_falls_back_to_default(self):
        for bad in ("abc", "0", "-3"):
            with self.subTest(value=bad):
                self.mem_client.reset_cache_for_tests()
                _, captured = self._build_with_env(
                    {"RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC": bad})
                self.assertEqual(
                    captured["options"].postgrest_client_timeout, 45)

    def test_default_matches_pipeline_config_constant(self):
        from pipeline.config import RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC
        with mock.patch.dict(os.environ,
                             {"RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC": ""}):
            self.assertEqual(self.mem_client._rpc_timeout_sec(),
                             RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC)

    def test_missing_client_options_falls_back_to_plain_create_client(self):
        with mock.patch.object(self.mem_client, "_client_options",
                               return_value=None):
            client, captured = self._build_with_env({})
        self.assertIsNotNone(client)
        self.assertIsNone(captured["options"])

    def test_options_are_the_sync_variant_the_sdk_expects(self):
        """Regression for the 2026-08-27 post-flip incident: the base
        ``ClientOptions`` lacks ``.storage`` so supabase-py 2.x's sync
        ``create_client`` raised AttributeError and every run-memory write
        was lost. The mocked tests above cannot see that; this one asks
        the real SDK to build a client from our options with fake
        credentials (construction makes no network call)."""
        try:
            from supabase import create_client
            from supabase.lib.client_options import SyncClientOptions
        except Exception as exc:  # pragma: no cover - SDK absent locally
            self.skipTest(f"supabase SDK not importable: {exc}")
        options = self.mem_client._client_options(45)
        self.assertIsInstance(options, SyncClientOptions)
        self.assertEqual(options.postgrest_client_timeout, 45)
        client = create_client("https://example.supabase.co",
                               "eyJhbGciOiJIUzI1NiJ9.fake.fake",
                               options=options)
        self.assertIsNotNone(client)
        session = getattr(client.postgrest, "session", None)
        timeout = getattr(session, "timeout", None)
        self.assertEqual(getattr(timeout, "read", timeout), 45)

    def test_sdk_rejecting_options_falls_back_to_bare_client(self):
        """If the SDK ever rejects our options object again, get_client()
        must still return a (timeout-unbounded) client instead of None,
        and say so in the log."""
        env = {"SUPABASE_URL": "https://example.invalid",
               "SUPABASE_SERVICE_ROLE_KEY": "not-a-real-key",
               "TEST_MODE": ""}
        calls = []

        def picky_create_client(url, key, options=None):
            calls.append(options)
            if options is not None:
                raise AttributeError(
                    "'ClientOptions' object has no attribute 'storage'")
            return object()

        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch("supabase.create_client", picky_create_client), \
                self.assertLogs(level="WARNING") as logs:
            client = self.mem_client.get_client()
        self.assertIsNotNone(client)
        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(calls[0])
        self.assertIsNone(calls[1])
        self.assertTrue(any("retrying without" in line
                            and "no attribute 'storage'" in line
                            for line in logs.output))


class RunLedgerFailurePathTests(unittest.TestCase):
    """WR-03 / PR #350 review issue 1: a session that dies inside
    ``main()``'s ``try`` never reaches the success-path
    ``run_ledger_finish`` call, so its ``run_ledger`` row would stay
    ``status='running'`` / ``finished_at=NULL`` forever -- indistinguishable
    from a run still in progress. The ``finally`` block must finalize
    the row as ``'failed'`` (same flag/TEST_MODE guards, fail-open).

    ``_set_sentry_session_tags`` is the first call inside ``main()``'s
    ``try`` (before the Smartsheet client is built), so forcing it to
    raise is the cheapest way to reach the real ``except``/``finally``
    handlers with no network and no facade rebinding beyond the flags.
    """

    def _run_main_to_failure(self, *, test_mode=False, finish_side_effect=None):
        import generate_weekly_pdfs as gwp
        import pipeline.orchestrate as orch

        writer_mock = mock.Mock()
        writer_mock.resolve_run_id.return_value = "run-failed-1"
        if finish_side_effect is not None:
            writer_mock.run_ledger_finish.side_effect = finish_side_effect
        with mock.patch.object(orch, "_mem_writer", writer_mock), \
                mock.patch.object(orch, "RUN_MEMORY_WRITE_ENABLED", True), \
                mock.patch.object(gwp, "TEST_MODE", test_mode), \
                mock.patch.object(gwp, "SENTRY_DSN", None), \
                mock.patch.object(orch, "_set_sentry_session_tags",
                                  side_effect=RuntimeError("boom")), \
                mock.patch.object(orch, "sentry_capture_with_context"), \
                mock.patch.object(orch, "_sentry_cron_checkin_start",
                                  return_value=None):
            orch.main()  # main() swallows the exception; must not raise
        return writer_mock

    def test_session_failure_finalizes_run_ledger_as_failed(self):
        writer_mock = self._run_main_to_failure()
        writer_mock.run_ledger_finish.assert_called_once()
        args, kwargs = writer_mock.run_ledger_finish.call_args
        self.assertEqual(args[0], "run-failed-1")
        self.assertEqual(kwargs.get("status"), "failed")

    def test_failure_path_finish_is_fail_open(self):
        # A Supabase outage during the failure-path finish must never
        # turn a swallowed session error into a new exception out of main().
        writer_mock = self._run_main_to_failure(
            finish_side_effect=RuntimeError("supabase down"))
        writer_mock.run_ledger_finish.assert_called_once()

    def test_failure_path_finish_respects_test_mode_guard(self):
        writer_mock = self._run_main_to_failure(test_mode=True)
        writer_mock.run_ledger_finish.assert_not_called()

    def test_failure_path_finish_includes_sheets_changed(self):
        """WR-04 (CONTEXT.md D-10): the failure-path finish upsert must
        carry ``sheets_changed`` too, not just the success path -- a run
        that dies mid-session must not silently understate how much it
        saw before failing.
        """
        writer_mock = self._run_main_to_failure()
        writer_mock.run_ledger_finish.assert_called_once()
        _, kwargs = writer_mock.run_ledger_finish.call_args
        # No sheet was ever processed before the forced early failure
        # (`_set_sentry_session_tags` raises before Phase 2), so
        # `_mem_sheets_written` is still its hoisted-at-top-of-main 0.
        self.assertEqual(kwargs.get("sheets_changed"), 0)


class RunLedgerSheetsChangedCallSiteTests(unittest.TestCase):
    """WR-04 (CONTEXT.md D-10): both ``run_ledger_finish`` call sites in
    ``pipeline.orchestrate`` (the success path near the normal end of
    ``main()``, the failure path in the bottom ``finally`` block) must
    pass ``sheets_changed=_mem_sheets_written`` -- the writer already
    accepts the column (``_RUN_LEDGER_FINISH_COLUMNS`` in
    pipeline_memory/writer.py), so this is purely a caller-side gap.

    The success-path call site sits deep inside ``main()`` after full
    pipeline execution and is not directly invocable without running a
    whole session (same rationale documented on ``AttachmentSideChannelTests``
    in this file for ``_upload_one``) -- proven via source inspection
    instead, mirroring that established pattern. The failure path IS
    behaviorally covered above via ``RunLedgerFailurePathTests``, which
    runs the real ``finally`` block through ``orch.main()``.
    """

    def test_both_finish_call_sites_pass_sheets_changed(self):
        import inspect

        import pipeline.orchestrate as orch

        src = inspect.getsource(orch)
        # Phase 11 Plan 02 restructured both call sites to build a
        # `_finish_kwargs` dict first (so `mode=`/optional
        # `fallback_reason=` can be added -- 11-02-PLAN.md Task 3) and
        # then call `run_ledger_finish(_mem_run_id, **_finish_kwargs)`.
        # `sheets_changed=_mem_sheets_written` now lives in that dict
        # construction, not directly inside the call parentheses -- this
        # regex/anchor pair is updated to match, same WR-04 invariant.
        call_sites = [
            m.start()
            for m in re.finditer(
                r"_mem_writer\.run_ledger_finish\("
                r"_mem_run_id, \*\*_finish_kwargs\)",
                src,
            )
        ]
        self.assertEqual(
            len(call_sites), 2,
            "expected exactly one success-path and one failure-path "
            "run_ledger_finish call site in pipeline.orchestrate",
        )
        kwargs_blocks = [
            m.start()
            for m in re.finditer(
                r"_finish_kwargs(?::\s*dict\[str,\s*Any\])?\s*=\s*dict\(",
                src,
            )
        ]
        self.assertEqual(
            len(kwargs_blocks), 2,
            "expected exactly one success-path and one failure-path "
            "_finish_kwargs construction in pipeline.orchestrate",
        )
        for idx in kwargs_blocks:
            end = src.index(")\n", idx)
            block = src[idx:end]
            self.assertIn("sheets_changed=_mem_sheets_written", block)
