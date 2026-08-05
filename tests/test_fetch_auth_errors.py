"""Tests for the 401/403 authorization-failure diagnosis in
``pipeline.fetch`` (2026-08-05 all-sheets-403 incident).

Covers:
  * ``_is_auth_api_error`` — structured SDK attribute path, serialized
    payload fallback path, and negative cases.
  * ``get_all_source_rows`` — the all-sheets-auth-failure raise carries
    the actionable "Smartsheet authorization failure" message, while a
    zero-row run WITHOUT auth errors keeps the legacy contract (returns
    an empty list; the caller raises the generic message).
"""
import unittest
from unittest import mock

import pipeline.fetch as fetch


class _StructuredApiError(Exception):
    """Mimic the smartsheet SDK ApiError shape: exc.error.result.status_code."""

    def __init__(self, status_code):
        super().__init__("api error")
        result = mock.Mock()
        result.status_code = status_code
        error = mock.Mock()
        error.result = result
        self.error = error


# Serialized shape the SDK's ApiError stringifies to (matches the
# 2026-08-05 production log lines verbatim).
_SERIALIZED_403 = (
    '{"result": {"code": 0, "errorCode": 0, "name": "ApiError", '
    '"recommendation": "Do not retry without fixing the problem. ", '
    '"shouldRetry": false, "statusCode": 403}}'
)


class TestIsAuthApiError(unittest.TestCase):
    def test_structured_403_detected(self):
        self.assertTrue(fetch._is_auth_api_error(_StructuredApiError(403)))

    def test_structured_401_detected(self):
        self.assertTrue(fetch._is_auth_api_error(_StructuredApiError(401)))

    def test_structured_500_not_auth(self):
        self.assertFalse(fetch._is_auth_api_error(_StructuredApiError(500)))

    def test_serialized_403_payload_detected(self):
        self.assertTrue(fetch._is_auth_api_error(Exception(_SERIALIZED_403)))

    def test_plain_exception_not_auth(self):
        self.assertFalse(fetch._is_auth_api_error(Exception("boom")))


class TestGetAllSourceRowsAuthFailure(unittest.TestCase):
    SOURCES = [
        {'id': 111, 'name': 'Sheet A', 'column_mapping': {'Work Request #': 1}},
        {'id': 222, 'name': 'Sheet B', 'column_mapping': {'Work Request #': 1}},
    ]

    def test_all_sheets_403_raises_authorization_failure(self):
        # Every sheet fetch dies with the serialized 403 ApiError (the
        # 2026-08-05 incident shape). Zero rows + all-auth-failure must
        # raise the actionable diagnosis, not return an empty list that
        # the caller turns into "No valid data rows found".
        with mock.patch.object(
            fetch, 'smartsheet_call_with_retry',
            side_effect=Exception(_SERIALIZED_403),
        ):
            with self.assertRaises(Exception) as ctx:
                fetch.get_all_source_rows(mock.Mock(), self.SOURCES)
        msg = str(ctx.exception)
        self.assertIn('Smartsheet authorization failure', msg)
        self.assertIn('all 2', msg)
        self.assertIn('SMARTSHEET_API_TOKEN', msg)

    def test_non_auth_failures_keep_legacy_empty_return(self):
        # Non-auth per-sheet failures (e.g. transient 500s) preserve the
        # legacy contract: swallow per sheet, return [] — the caller
        # owns the generic zero-rows raise.
        with mock.patch.object(
            fetch, 'smartsheet_call_with_retry',
            side_effect=Exception("server exploded"),
        ):
            result = fetch.get_all_source_rows(mock.Mock(), self.SOURCES)
        self.assertEqual(result, [])

    def test_partial_auth_failure_logs_aggregate_summary_without_raise(self):
        # One sheet 403s, the other dies with a non-auth error: not an
        # all-sheets authorization failure, so no raise — but the
        # aggregate 🔐 summary MUST still emit (Copilot review, PR #297)
        # so a partial authorization loss is not buried in scattered
        # per-sheet error lines.
        def _per_sheet(_fn, sheet_id, **_kwargs):
            if sheet_id == 111:
                raise Exception(_SERIALIZED_403)
            raise Exception("server exploded")

        with mock.patch.object(
            fetch, 'smartsheet_call_with_retry', side_effect=_per_sheet,
        ):
            with self.assertLogs(level='ERROR') as logs:
                result = fetch.get_all_source_rows(mock.Mock(), self.SOURCES)
        self.assertEqual(result, [])
        self.assertTrue(
            any('1 of 2 source sheets failed with 401/403' in line
                for line in logs.output),
            f"aggregate auth summary missing from: {logs.output}",
        )


if __name__ == '__main__':
    unittest.main()
