"""``sheet_registry`` bulk upsert must be key-homogeneous per request.

postgrest-py sends ``columns=`` as the UNION of keys across a list
payload and PostgREST applies that list to every row, so on the
``ON CONFLICT DO UPDATE`` half a row that omitted ``column_mapping``
writes NULL into a ``NOT NULL`` column (23502 -> HTTP 400, whole call
fails). Production hit this the moment discovery found one sheet more
than the registry held (ledger ``[2026-08-28 15:05]``).

Also pins that ``with_retry``'s final "RPC failed" warning names the
PostgREST code and message (never ``details``, which can carry row
values) so the next failure is diagnosable from the Actions log.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pipeline_memory_shadow as shadow  # noqa: E402

_make_client = shadow._make_fake_pipeline_memory_client


class RegistryUpsertKeyHomogeneityTests(unittest.TestCase):

    def setUp(self):
        shadow._reset_all()
        shadow._pop_env()
        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"

    def tearDown(self):
        shadow._reset_all()
        shadow._pop_env()

    @staticmethod
    def _sheets():
        return [
            {"id": 1, "name": "A", "column_mapping": {"F": 1}},
            {"id": 2, "name": "B", "column_mapping": {"F": 2}},
            {"id": 3, "name": "C", "column_mapping": {"F": 3}},
        ]

    @staticmethod
    def _call(client, **kwargs):
        from pipeline_memory import writer as mem_writer

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            mem_writer.upsert_sheet_registry(
                RegistryUpsertKeyHomogeneityTests._sheets(), "run-1",
                lambda sid: "primary", {}, **kwargs,
            )
        return mem_writer.get_counters()

    def test_registered_plus_new_sheet_splits_by_key_set(self):
        cap: list = []
        client = _make_client(upsert_capture=cap)

        counters = self._call(client, column_mapping_sheets={3})

        self.assertEqual(len(cap), 2)
        for call in cap:
            payload = call.args[0]
            self.assertEqual(call.kwargs.get("on_conflict"), "sheet_id")
            self.assertEqual(len({frozenset(r) for r in payload}), 1)
        by_id = {r["sheet_id"]: r for c in cap for r in c.args[0]}
        self.assertEqual(sorted(by_id), [1, 2, 3])
        self.assertIn("column_mapping", by_id[3])
        self.assertNotIn("column_mapping", by_id[1])
        self.assertNotIn("column_mapping", by_id[2])
        self.assertEqual(counters["sheets_registry_written"], 3)
        self.assertEqual(counters.get("sheets_registry_errored", 0), 0)

    def test_full_and_delta_read_mix_splits_too(self):
        cap: list = []
        client = _make_client(upsert_capture=cap)

        self._call(client, column_mapping_sheets=set(),
                   full_read_sheets={1})

        self.assertEqual(len(cap), 2)
        by_id = {r["sheet_id"]: r for c in cap for r in c.args[0]}
        self.assertIn("last_full_read_at", by_id[1])
        self.assertNotIn("last_full_read_at", by_id[2])
        self.assertNotIn("last_full_read_at", by_id[3])
        for call in cap:
            self.assertEqual(
                len({frozenset(r) for r in call.args[0]}), 1,
            )

    def test_homogeneous_payload_still_one_request(self):
        cap: list = []
        client = _make_client(upsert_capture=cap)

        counters = self._call(client)  # deep-run shape: mapping on all

        self.assertEqual(len(cap), 1)
        self.assertEqual(len(cap[0].args[0]), 3)
        self.assertEqual(counters["sheets_registry_written"], 3)

    def test_one_failing_group_does_not_take_the_other_down(self):
        cap: list = []
        client = _make_client(upsert_capture=cap)
        table = client.schema.return_value.table.return_value

        def _execute():
            payload = table.upsert.call_args.args[0]
            cap.append(table.upsert.call_args)
            if "column_mapping" not in payload[0]:
                raise RuntimeError("boom")
            return mock.Mock(data=[])

        table.upsert.return_value.execute.side_effect = _execute

        counters = self._call(client, column_mapping_sheets={3})

        self.assertEqual(len(cap), 2)
        self.assertEqual(counters["sheets_registry_written"], 1)
        self.assertEqual(counters["sheets_registry_errored"], 2)


class WithRetryFailureMessageTests(unittest.TestCase):

    def setUp(self):
        shadow._reset_all()

    def tearDown(self):
        shadow._reset_all()

    def test_final_warning_names_postgrest_code_and_message(self):
        from postgrest.exceptions import APIError
        from pipeline_memory import client as mem_client

        exc = APIError({
            "message": 'null value in column "column_mapping" of '
                       'relation "sheet_registry" violates not-null '
                       'constraint',
            "code": "23502",
            "details": "Failing row contains (1, secret-row-value).",
            "hint": None,
        })

        def _boom():
            raise exc

        crumbs: list = []
        with mock.patch(
            "pipeline_memory.client._sentry_breadcrumb",
            side_effect=lambda *a, **k: crumbs.append((a, k)),
        ), self.assertLogs(level="WARNING") as logs:
            result = mem_client.with_retry(_boom, op="sheet_registry_upsert")

        self.assertIsNone(result)
        line = next(l for l in logs.output if "RPC failed after" in l)
        self.assertIn("23502", line)
        self.assertIn("violates not-null constraint", line)
        self.assertNotIn("secret-row-value", line)
        crumb = next(k for a, k in crumbs if a[1] == "RPC failed")
        self.assertEqual(crumb["data"]["error_code"], "23502")
        self.assertIn("not-null", crumb["data"]["error_message"])
        self.assertNotIn("secret-row-value", crumb["data"]["error_message"])

    def test_non_postgrest_error_logs_str_truncated_to_200(self):
        from pipeline_memory import client as mem_client

        def _boom():
            raise ValueError("x" * 500)

        with self.assertLogs(level="WARNING") as logs:
            mem_client.with_retry(_boom, op="sheet_registry_upsert")

        line = next(l for l in logs.output if "RPC failed after" in l)
        self.assertIn("ValueError", line)
        self.assertTrue(line.endswith(": " + "x" * 200))
        self.assertNotIn("x" * 201, line)

    def _final_warning(self, exc):
        from pipeline_memory import client as mem_client

        def _boom():
            raise exc

        crumbs: list = []
        with mock.patch(
            "pipeline_memory.client._sentry_breadcrumb",
            side_effect=lambda *a, **k: crumbs.append((a, k)),
        ), self.assertLogs(level="WARNING") as logs:
            mem_client.with_retry(_boom, op="sheet_registry_upsert")
        line = next(l for l in logs.output if "RPC failed after" in l)
        crumb = next(k for a, k in crumbs if a[1] == "RPC failed")
        return line, crumb["data"]

    def test_data_exception_message_is_withheld(self):
        """22xxx messages quote the offending literal -- never logged."""
        from postgrest.exceptions import APIError

        line, data = self._final_warning(APIError({
            "message": 'invalid input syntax for type integer: '
                       '"literal-row-value"',
            "code": "22P02", "details": None, "hint": None,
        }))

        self.assertIn("code=22P02", line)
        self.assertNotIn("literal-row-value", line)
        self.assertEqual(data["error_code"], "22P02")
        self.assertEqual(data["error_message"], "")

    def test_hint_and_details_never_logged(self):
        from postgrest.exceptions import APIError

        line, data = self._final_warning(APIError({
            "message": 'duplicate key value violates unique constraint '
                       '"sheet_registry_pkey"',
            "code": "23505",
            "details": "Key (sheet_id)=(1) secret-detail-text",
            "hint": "secret-hint-text",
        }))

        self.assertIn("unique constraint", line)
        for leak in ("secret-detail-text", "secret-hint-text"):
            self.assertNotIn(leak, line)
            self.assertNotIn(leak, data["error_message"])

    def test_http_status_in_code_does_not_match_sqlstate_allowlist(self):
        """postgrest-py stores the HTTP status (int) in ``code`` when the
        body is not JSON; ``422`` must not pass as a ``42xxx`` code."""
        from postgrest.exceptions import APIError

        line, data = self._final_warning(APIError({
            "message": "raw-body-echo", "code": 422,
            "details": None, "hint": None,
        }))

        self.assertIn("code=422", line)
        self.assertNotIn("raw-body-echo", line)
        self.assertEqual(data["error_message"], "")

    def test_details_bearing_error_is_never_str_dumped(self):
        """Duck-typing guard: anything with ``details`` is summarised
        like an APIError, even if it is not one (import-guard path)."""

        class _FakeApiError(Exception):
            code = "23502"
            message = 'null value in column "x" violates not-null constraint'
            details = "Failing row contains (secret-row-value)."
            hint = None

            def __str__(self):
                return f"{self.message} {self.details}"

        line, data = self._final_warning(_FakeApiError())

        self.assertIn("violates not-null constraint", line)
        self.assertNotIn("secret-row-value", line)
        self.assertNotIn("secret-row-value", data["error_message"])


class PostgrestColumnsUnionContractTests(unittest.TestCase):
    """Pins the library behaviour the writer fix rests on: a mixed list
    payload yields a ``columns=`` union, a homogeneous one does not
    widen. If a postgrest upgrade changes this, revisit the grouping."""

    def test_pre_upsert_columns_is_union_of_row_keys(self):
        from postgrest.base_request_builder import pre_upsert
        from postgrest.types import ReturnMethod

        mixed = [{"sheet_id": 1, "name": "A"},
                 {"sheet_id": 2, "name": "B", "column_mapping": {}}]
        _, params, _, _ = pre_upsert(
            mixed, count=None, returning=ReturnMethod.representation,
            ignore_duplicates=False, on_conflict="sheet_id",
        )
        self.assertIn('"column_mapping"', params["columns"])

        same = [{"sheet_id": 1, "name": "A"}, {"sheet_id": 2, "name": "B"}]
        _, params, _, _ = pre_upsert(
            same, count=None, returning=ReturnMethod.representation,
            ignore_duplicates=False, on_conflict="sheet_id",
        )
        self.assertNotIn("column_mapping", params["columns"])


if __name__ == "__main__":
    unittest.main()
