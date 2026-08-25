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
        payload_with = mem_writer.build_row_payload(row_with, "run-1")
        self.assertEqual(
            payload_with["row_modified_at"], "2026-08-24T10:15:00+00:00",
        )

        row_without = {"__row_id": 2, "Work Request #": "90001"}
        payload_without = mem_writer.build_row_payload(row_without, "run-1")
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
    """Task 3 edge invariants for ``upsert_rows_bulk`` / ``build_row_payload``
    / ``compute_content_hash`` -- the MEM-02 contract plan 10-02's
    per-sheet loop (chunking, sub-budget, orchestrator wiring) is built
    on top of. Asserts payload SHAPE, never database state (no live
    Supabase / Postgres in this suite).
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
        from pipeline_memory import writer as mem_writer

        blank_row = {
            "__row_id": 1,
            "Work Request #": "90001",
            "Foreman": "",
            "__effective_user": "Unknown Foreman",
        }
        payload = mem_writer.build_row_payload(blank_row, "run-1")
        self.assertIn(payload["foreman_observed"], (None, ""))
        self.assertNotEqual(payload["foreman_observed"], "Unknown Foreman")
        self.assertTrue(payload["content_hash"])
        self.assertIsInstance(payload["content_hash"], str)

        absent_row = dict(blank_row)
        del absent_row["Foreman"]
        payload2 = mem_writer.build_row_payload(absent_row, "run-1")
        self.assertIn(payload2["foreman_observed"], (None, ""))
        self.assertTrue(payload2["content_hash"])

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
        payload_a = mem_writer.build_row_payload(row_a, "run-1")
        payload_b = mem_writer.build_row_payload(row_b, "run-1")
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

    def test_forced_rpc_failure_bumps_only_the_errored_counter(self):
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
            after.get("rows_upsert_written", 0),
            before.get("rows_upsert_written", 0),
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
            "__helper_foreman": "Bob VerySecretHelper",
            "__vac_crew_name": "Carl VerySecretVac",
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


if __name__ == "__main__":
    unittest.main()
