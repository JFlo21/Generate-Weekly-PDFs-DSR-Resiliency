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

Self-contained like ``tests/test_billing_audit_shadow.py`` -- there is
no ``tests/conftest.py`` in this repo to share fixtures from.
"""

from __future__ import annotations

import os
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


if __name__ == "__main__":
    unittest.main()
