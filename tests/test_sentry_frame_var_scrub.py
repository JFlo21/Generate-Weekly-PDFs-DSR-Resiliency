"""Unit tests for ``observability._strip_frame_vars`` — the PII guard that
drops local-variable values from Sentry stacktrace frames.

The engine initializes Sentry with ``include_local_variables=True``, so a raw
``capture_exception`` / ``capture_message`` from inside a function whose locals
hold sampled billing rows (foreman / customer / WR / prices — e.g.
``_validate_single_sheet``'s ``_sample_rows_cache``) would exfiltrate that row
data to Sentry. ``sentry_capture_sheet_drop`` runs this processor on an
isolated scope so the loud "dropped source sheet" alert carries the sheet id
and exception class only, never frame-local row values.
"""
from __future__ import annotations

from unittest import mock

from pipeline.observability import _strip_frame_vars, sentry_capture_sheet_drop


def test_strips_vars_from_exception_and_thread_frames():
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"function": "f", "vars": {"_sample_rows_cache": [["WR123", "$500"]]}},
                            {"function": "g", "vars": {"foreman": "Jane Doe"}},
                        ]
                    }
                }
            ]
        },
        "threads": {
            "values": [
                {"stacktrace": {"frames": [{"function": "h", "vars": {"customer": "ACME"}}]}}
            ]
        },
    }
    out = _strip_frame_vars(event, {})
    exc_frames = out["exception"]["values"][0]["stacktrace"]["frames"]
    thread_frames = out["threads"]["values"][0]["stacktrace"]["frames"]
    assert "vars" not in exc_frames[0]
    assert "vars" not in exc_frames[1]
    assert "vars" not in thread_frames[0]
    # Non-vars frame metadata is preserved (grouping/debugging still works).
    assert exc_frames[0]["function"] == "f"


def test_handles_event_without_stacktraces_gracefully():
    event = {"message": "Discovery dropped source sheet 123 after retries"}
    assert _strip_frame_vars(dict(event), {}) == event


def test_handles_missing_frames_keys():
    # Partial structures (no 'frames', empty 'values') must not raise.
    event = {"exception": {"values": [{}]}, "threads": {}}
    assert _strip_frame_vars(event, {}) is event


def test_sheet_drop_noop_when_dsn_unset():
    # With Sentry disabled, the escalation must be a pure no-op — no
    # isolation scope opened, no event emitted.
    with mock.patch("pipeline.observability.sentry_sdk") as mock_sentry, \
            mock.patch("pipeline.observability.SENTRY_DSN", None):
        sentry_capture_sheet_drop(999, ValueError("boom"))
    mock_sentry.isolation_scope.assert_not_called()
    mock_sentry.capture_message.assert_not_called()


def test_sheet_drop_emits_sanitized_capture_with_processor():
    # With Sentry enabled, the drop escalates as a SANITIZED, grouped
    # capture_message (NOT capture_exception, which would attach frame
    # locals) on an isolated scope that registers the _strip_frame_vars
    # PII processor and tags the sheet id + error location.
    scope = mock.MagicMock()
    scope_cm = mock.MagicMock()
    scope_cm.__enter__.return_value = scope
    scope_cm.__exit__.return_value = False
    with mock.patch("pipeline.observability.sentry_sdk") as mock_sentry, \
            mock.patch(
                "pipeline.observability.SENTRY_DSN",
                "https://public@example.ingest.sentry.io/1",
            ):
        mock_sentry.isolation_scope.return_value = scope_cm
        sentry_capture_sheet_drop(7654321, ValueError("oversized response"))

    # Loud but sanitized: capture_message at error level, never
    # capture_exception (which would ship include_local_variables frames).
    mock_sentry.capture_exception.assert_not_called()
    mock_sentry.capture_message.assert_called_once()
    msg_args, msg_kwargs = mock_sentry.capture_message.call_args
    assert msg_kwargs.get("level") == "error"
    assert "7654321" in msg_args[0]
    assert "ValueError" in msg_args[0]
    # The PII processor is registered on the isolated scope.
    scope.add_event_processor.assert_called_once_with(_strip_frame_vars)
    # Filterable tags + grouped fingerprint (one issue per exception type).
    scope.set_tag.assert_any_call("error_location", "discovery_sheet_drop")
    scope.set_tag.assert_any_call("sheet_id", "7654321")
    assert scope.fingerprint == ["discovery-sheet-drop", "ValueError"]
