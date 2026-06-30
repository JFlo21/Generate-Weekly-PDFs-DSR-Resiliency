"""Unit tests for ``pipeline.retry.smartsheet_call_with_retry``.

The helper centralizes the transient-failure retry logic that was previously
duplicated three times inside ``pipeline.orchestrate.main`` and entirely
ABSENT on the hot discovery / per-sheet fetch path (``pipeline.fetch`` /
``pipeline.discovery``). It retries ONLY the transient failures the
Smartsheet SDK does not itself drive to success:

  * generic ``ApiError`` with ``error.result.code == 4000`` ("unexpected
    error, please retry" — the oversized-response failure that hammers the
    discovery / per-sheet fetch path; the SDK does NOT auto-retry it)
  * the typed ``should_retry`` exceptions (ServerTimeout 4002, Maintenance
    4001, UnexpectedShouldRetry 4004) for the case where the SDK's own retry
    window is exhausted
  * ``RateLimitExceededError`` 4003 (back off long, do not hammer)
  * network drops detected by class name (RemoteDisconnected, Timeout, …)

A non-transient error (a programming ``ValueError``, or an ``ApiError`` with a
PERMANENT code like 1006 not-found) is re-raised IMMEDIATELY — never retried.

Total sleep across all attempts is bounded by ``max_total_sleep`` so a single
call can never consume the attachment-prefetch / TIME_BUDGET window (the
2026-04-22 prefetch-stall incident). On exhaustion the last exception is
re-raised — callers decide whether to degrade (return ``[]``) or fail loud
(Sentry + raise).
"""
from __future__ import annotations

from unittest import mock

import pytest
import smartsheet.exceptions as ss_exc

from pipeline.retry import smartsheet_call_with_retry


def _api_error(code: int, message: str = "api error") -> ss_exc.ApiError:
    """Build a generic Smartsheet ``ApiError`` whose result code is ``code``.

    Mirrors the real SDK shape ``exc.error.result.code`` that the helper
    inspects to decide whether the code is transient (4000) or permanent.
    """
    err = mock.Mock()
    err.result.code = code
    return ss_exc.ApiError(err, message)


def _rate_limit_error() -> ss_exc.RateLimitExceededError:
    # RateLimitExceededError(error, message) — should_retry=True in the SDK.
    return ss_exc.RateLimitExceededError(None, "rate limit exceeded")


def _server_timeout_error() -> ss_exc.ServerTimeoutExceededError:
    return ss_exc.ServerTimeoutExceededError(None, "server timeout")


def _unexpected_request_error() -> ss_exc.UnexpectedRequestError:
    # The SDK's _request wraps every requests.RequestException (connection
    # reset / read timeout / chunked-encoding) as this type — NOT the raw
    # requests exception. This is what actually reaches app code on a drop.
    return ss_exc.UnexpectedRequestError(None, None)


def _http_error_ssl() -> ss_exc.HttpError:
    # The SDK's _request wraps requests.exceptions.SSLError as a bare HttpError.
    return ss_exc.HttpError(500, "SSL handshake failed")


class _NamedTransient(Exception):
    """Stand-in for a requests network drop matched by class name."""


_NamedTransient.__name__ = "ConnectionResetError"


def test_returns_value_immediately_on_success():
    func = mock.Mock(return_value="ok")
    with mock.patch("pipeline.retry.time.sleep") as slept:
        result = smartsheet_call_with_retry(func, 1, 2, key="v")
    assert result == "ok"
    func.assert_called_once_with(1, 2, key="v")
    slept.assert_not_called()


def test_retries_api_error_4000_then_succeeds():
    func = mock.Mock(side_effect=[_api_error(4000), _api_error(4000), "ok"])
    with mock.patch("pipeline.retry.time.sleep") as slept:
        result = smartsheet_call_with_retry(func, max_attempts=4)
    assert result == "ok"
    assert func.call_count == 3
    assert slept.call_count == 2  # two failures → two backoffs


def test_retries_typed_server_timeout_then_succeeds():
    func = mock.Mock(side_effect=[_server_timeout_error(), "ok"])
    with mock.patch("pipeline.retry.time.sleep") as slept:
        result = smartsheet_call_with_retry(func, max_attempts=4)
    assert result == "ok"
    assert func.call_count == 2
    slept.assert_called_once()


def test_raises_after_exhausting_attempts_on_4000():
    func = mock.Mock(side_effect=_api_error(4000))
    with mock.patch("pipeline.retry.time.sleep"):
        with pytest.raises(ss_exc.ApiError):
            smartsheet_call_with_retry(func, max_attempts=4)
    assert func.call_count == 4  # all attempts used


def test_rate_limit_uses_long_backoff_schedule():
    func = mock.Mock(side_effect=_rate_limit_error())
    with mock.patch("pipeline.retry.time.sleep") as slept:
        with pytest.raises(ss_exc.RateLimitExceededError):
            smartsheet_call_with_retry(func, max_attempts=4,
                                       max_total_sleep=90.0)
    # 15s, 30s, 45s (matches the existing orchestrate rate-limit schedule).
    assert [c.args[0] for c in slept.call_args_list] == [15.0, 30.0, 45.0]


def test_retries_unexpected_request_error_sdk_transport_wrapper():
    # Regression: the SDK wraps real connection/timeout drops as
    # UnexpectedRequestError, whose class name matches none of the network
    # tags — so this MUST be retried by type, not by name-substring.
    func = mock.Mock(side_effect=[_unexpected_request_error(), "ok"])
    with mock.patch("pipeline.retry.time.sleep") as slept:
        result = smartsheet_call_with_retry(func, max_attempts=4)
    assert result == "ok"
    assert func.call_count == 2
    slept.assert_called_once()


def test_retries_http_error_ssl_wrapper():
    func = mock.Mock(side_effect=[_http_error_ssl(), "ok"])
    with mock.patch("pipeline.retry.time.sleep") as slept:
        result = smartsheet_call_with_retry(func, max_attempts=4)
    assert result == "ok"
    assert func.call_count == 2
    slept.assert_called_once()


def test_non_transient_value_error_raises_immediately():
    func = mock.Mock(side_effect=ValueError("programming error"))
    with mock.patch("pipeline.retry.time.sleep") as slept:
        with pytest.raises(ValueError):
            smartsheet_call_with_retry(func, max_attempts=4)
    func.assert_called_once()
    slept.assert_not_called()


def test_permanent_api_code_raises_immediately_without_retry():
    # 1006 (not found) is permanent — retrying would only burn the budget.
    func = mock.Mock(side_effect=_api_error(1006, "not found"))
    with mock.patch("pipeline.retry.time.sleep") as slept:
        with pytest.raises(ss_exc.ApiError):
            smartsheet_call_with_retry(func, max_attempts=4)
    func.assert_called_once()
    slept.assert_not_called()


def test_network_error_matched_by_class_name_is_retried():
    func = mock.Mock(side_effect=[_NamedTransient(), "ok"])
    with mock.patch("pipeline.retry.time.sleep") as slept:
        result = smartsheet_call_with_retry(func, max_attempts=4)
    assert result == "ok"
    assert func.call_count == 2
    slept.assert_called_once()


def test_max_total_sleep_caps_cumulative_backoff():
    func = mock.Mock(side_effect=_api_error(4000))
    with mock.patch("pipeline.retry.time.sleep") as slept:
        with pytest.raises(ss_exc.ApiError):
            # max_attempts is generous; the sleep budget is the real cap.
            smartsheet_call_with_retry(func, max_attempts=20,
                                       max_total_sleep=10.0)
    # Transient backoff = 2**(n-1)+0.5 → 1.5, 2.5, 4.5 (cum 8.5); the next
    # 8.5 would exceed 10.0, so it raises after exactly 3 sleeps.
    assert [c.args[0] for c in slept.call_args_list] == [1.5, 2.5, 4.5]
