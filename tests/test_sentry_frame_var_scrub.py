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

from pipeline.observability import _strip_frame_vars


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
