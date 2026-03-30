"""
Tests for _fetch_sheet_with_retry() in generate_weekly_pdfs.

Validates:
- Success on first attempt returns the sheet immediately.
- JSONDecodeError on the first N-1 calls triggers retries with backoff; succeeds on last.
- JSONDecodeError on every attempt re-raises after exhausting retries.
- ApiError with should_retry=True triggers retries; succeeds on later attempt.
- ApiError with should_retry=False is re-raised immediately (no retry).
- HttpError with 5xx status triggers retries; succeeds on later attempt.
- HttpError with 4xx status is re-raised immediately (no retry).
- time.sleep is called with the correct exponential-backoff delays.
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch, call

import smartsheet.exceptions

import generate_weekly_pdfs


def _make_api_error(should_retry: bool) -> smartsheet.exceptions.ApiError:
    """Build a minimal ApiError with the given should_retry flag."""
    err = MagicMock()
    exc = smartsheet.exceptions.ApiError(err)
    exc.should_retry = should_retry
    return exc


def _make_http_error(status_code: int) -> smartsheet.exceptions.HttpError:
    """Build a minimal HttpError with the given HTTP status code."""
    exc = smartsheet.exceptions.HttpError(status_code, b"error body")
    return exc


class TestFetchSheetWithRetry(unittest.TestCase):
    """Unit tests for the _fetch_sheet_with_retry helper."""

    SHEET_ID = 123456
    COLUMN_IDS = [1, 2, 3]

    # ------------------------------------------------------------------ helpers

    def _client(self, side_effects):
        """Return a mock client whose get_sheet raises/returns side_effects."""
        client = MagicMock()
        client.Sheets.get_sheet.side_effect = side_effects
        return client

    # ------------------------------------------------------------------ tests

    def test_success_on_first_attempt(self):
        """No retries needed; sheet returned immediately."""
        mock_sheet = MagicMock()
        client = self._client([mock_sheet])

        result = generate_weekly_pdfs._fetch_sheet_with_retry(
            client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=0
        )

        self.assertIs(result, mock_sheet)
        self.assertEqual(client.Sheets.get_sheet.call_count, 1)

    @patch("time.sleep")
    def test_json_decode_error_retries_then_succeeds(self, mock_sleep):
        """JSONDecodeError on attempts 1–2, success on attempt 3."""
        mock_sheet = MagicMock()
        client = self._client([
            json.JSONDecodeError("err", "", 0),
            json.JSONDecodeError("err", "", 0),
            mock_sheet,
        ])

        result = generate_weekly_pdfs._fetch_sheet_with_retry(
            client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=2
        )

        self.assertIs(result, mock_sheet)
        self.assertEqual(client.Sheets.get_sheet.call_count, 3)
        # sleep called with 2s (attempt 1) then 4s (attempt 2)
        mock_sleep.assert_has_calls([call(2), call(4)])

    @patch("time.sleep")
    def test_json_decode_error_exhausts_retries(self, mock_sleep):
        """JSONDecodeError on every attempt; re-raises after max retries."""
        client = self._client([
            json.JSONDecodeError("err", "", 0),
            json.JSONDecodeError("err", "", 0),
            json.JSONDecodeError("err", "", 0),
        ])

        with self.assertRaises(json.JSONDecodeError):
            generate_weekly_pdfs._fetch_sheet_with_retry(
                client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=2
            )

        self.assertEqual(client.Sheets.get_sheet.call_count, 3)
        # sleep called twice (after attempt 1 and 2; not after final attempt)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    def test_retryable_api_error_retries_then_succeeds(self, mock_sleep):
        """Retryable ApiError on attempt 1; success on attempt 2."""
        mock_sheet = MagicMock()
        client = self._client([_make_api_error(should_retry=True), mock_sheet])

        result = generate_weekly_pdfs._fetch_sheet_with_retry(
            client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=2
        )

        self.assertIs(result, mock_sheet)
        self.assertEqual(client.Sheets.get_sheet.call_count, 2)
        mock_sleep.assert_called_once_with(2)

    def test_non_retryable_api_error_raises_immediately(self):
        """ApiError with should_retry=False is re-raised without any sleep/retry."""
        client = self._client([_make_api_error(should_retry=False)])

        with self.assertRaises(smartsheet.exceptions.ApiError):
            generate_weekly_pdfs._fetch_sheet_with_retry(
                client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=0
            )

        # Only one attempt made — no retry for non-retryable errors
        self.assertEqual(client.Sheets.get_sheet.call_count, 1)

    @patch("time.sleep")
    def test_http_5xx_error_retries_then_succeeds(self, mock_sleep):
        """HttpError 503 on attempt 1; success on attempt 2."""
        mock_sheet = MagicMock()
        client = self._client([_make_http_error(503), mock_sheet])

        result = generate_weekly_pdfs._fetch_sheet_with_retry(
            client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=2
        )

        self.assertIs(result, mock_sheet)
        self.assertEqual(client.Sheets.get_sheet.call_count, 2)
        mock_sleep.assert_called_once_with(2)

    def test_http_4xx_error_raises_immediately(self):
        """HttpError 403 is re-raised immediately without retry."""
        client = self._client([_make_http_error(403)])

        with self.assertRaises(smartsheet.exceptions.HttpError):
            generate_weekly_pdfs._fetch_sheet_with_retry(
                client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=0
            )

        self.assertEqual(client.Sheets.get_sheet.call_count, 1)

    @patch("time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        """Delays double correctly: base, base*2, base*4, …"""
        mock_sheet = MagicMock()
        base = 1
        client = self._client([
            json.JSONDecodeError("e", "", 0),
            json.JSONDecodeError("e", "", 0),
            json.JSONDecodeError("e", "", 0),
            mock_sheet,
        ])

        generate_weekly_pdfs._fetch_sheet_with_retry(
            client, self.SHEET_ID, self.COLUMN_IDS, max_retries=4, base_delay=base
        )

        mock_sleep.assert_has_calls([call(1), call(2), call(4)])
        self.assertEqual(mock_sleep.call_count, 3)

    def test_traceback_preserved_on_exhaustion(self):
        """The exception raised after retries originates from get_sheet, not a re-raise site."""
        sentinel = json.JSONDecodeError("sentinel msg", "", 0)
        client = self._client([sentinel, sentinel, sentinel])

        with self.assertRaises(json.JSONDecodeError) as ctx:
            generate_weekly_pdfs._fetch_sheet_with_retry(
                client, self.SHEET_ID, self.COLUMN_IDS, max_retries=3, base_delay=0
            )

        # The caught exception must be the one raised by the mock, not a new one
        self.assertIs(ctx.exception, sentinel)


if __name__ == "__main__":
    unittest.main()
