"""Unit tests for the discovery sheet-drop PII scrub.

The engine initializes Sentry with ``include_local_variables=True`` +
``attach_stacktrace=True``, so a ``capture_message`` from inside a function
whose locals hold sampled billing rows (foreman / customer / WR / prices — e.g.
``_validate_single_sheet``'s ``_sample_rows_cache``) would exfiltrate that row
data to Sentry via the frame ``vars`` (and any source literal in the frame's
context lines).

The scrub for the sheet-drop event MUST run at ``before_send`` time: with
``attach_stacktrace=True`` the SDK appends the current thread's stacktrace
frames AFTER scope event-processors run, so a scope processor never sees them
(Codex P1, PR #281). ``sentry_capture_sheet_drop`` tags the event; the global
``before_send_filter`` calls ``_scrub_sheet_drop_frame_vars`` which strips every
frame's data-bearing fields from THAT event only — keeping the loud, grouped
alert (sheet id + exception class) without row PII, while other events keep
their locals for debugging.
"""
from __future__ import annotations

from unittest import mock

from pipeline.observability import (
    _scrub_sheet_drop_frame_vars,
    _strip_frame_vars,
    sentry_capture_sheet_drop,
)


def _frame_with_pii():
    return {
        "function": "validate",
        "filename": "discovery.py",
        "lineno": 42,
        "vars": {"_sample_rows_cache": [["WR123", "$500", "ForemanX"]]},
        "pre_context": ["prev = 1"],
        "context_line": "cache.append(row)  # WR123 literal",
        "post_context": ["nxt = 2"],
    }


def test_strips_vars_and_source_context_from_all_frames():
    event = {
        "exception": {"values": [{"stacktrace": {"frames": [_frame_with_pii()]}}]},
        "threads": {"values": [{"stacktrace": {"frames": [_frame_with_pii()]}}]},
    }
    out = _strip_frame_vars(event, {})
    for container in ("exception", "threads"):
        frame = out[container]["values"][0]["stacktrace"]["frames"][0]
        # Data-bearing fields removed.
        assert "vars" not in frame
        assert "pre_context" not in frame
        assert "context_line" not in frame
        assert "post_context" not in frame
        # Structural metadata preserved (grouping / "where did it fail").
        assert frame["function"] == "validate"
        assert frame["filename"] == "discovery.py"
        assert frame["lineno"] == 42


def test_handles_event_without_stacktraces_gracefully():
    event = {"message": "Discovery dropped source sheet 123 after retries"}
    assert _strip_frame_vars(dict(event), {}) == event


def test_handles_missing_frames_keys():
    # Partial structures (no 'frames', empty 'values') must not raise.
    event = {"exception": {"values": [{}]}, "threads": {}}
    assert _strip_frame_vars(event, {}) is event


def test_scrub_sheet_drop_strips_frames_only_for_tagged_event():
    # The before_send hook scrubs frames ONLY for the discovery sheet-drop
    # event (identified by tag); every other event keeps its locals so
    # include_local_variables debugging is preserved.
    tagged = {
        "tags": {"error_location": "discovery_sheet_drop", "sheet_id": "9"},
        "threads": {"values": [{"stacktrace": {"frames": [_frame_with_pii()]}}]},
    }
    out = _scrub_sheet_drop_frame_vars(tagged)
    frame = out["threads"]["values"][0]["stacktrace"]["frames"][0]
    assert "vars" not in frame
    assert "context_line" not in frame
    assert frame["function"] == "validate"

    untagged = {
        "tags": {"error_location": "some_other_error"},
        "threads": {"values": [{"stacktrace": {"frames": [_frame_with_pii()]}}]},
    }
    out2 = _scrub_sheet_drop_frame_vars(untagged)
    frame2 = out2["threads"]["values"][0]["stacktrace"]["frames"][0]
    assert "vars" in frame2  # untouched — locals preserved for other events
    assert "context_line" in frame2

    # No tags at all: must not raise, must not scrub.
    out3 = _scrub_sheet_drop_frame_vars({"message": "x"})
    assert out3 == {"message": "x"}


def test_sheet_drop_noop_when_dsn_unset():
    # With Sentry disabled, the escalation must be a pure no-op — no
    # isolation scope opened, no event emitted.
    with mock.patch("pipeline.observability.sentry_sdk") as mock_sentry, \
            mock.patch("pipeline.observability.SENTRY_DSN", None):
        sentry_capture_sheet_drop(999, ValueError("boom"))
    mock_sentry.isolation_scope.assert_not_called()
    mock_sentry.capture_message.assert_not_called()


def test_sheet_drop_emits_tagged_sanitized_capture():
    # With Sentry enabled, the drop escalates as a grouped capture_message
    # (NOT capture_exception) tagged error_location=discovery_sheet_drop so the
    # before_send hook scrubs it. It must NOT rely on a scope event-processor
    # (which runs too early to see the attach_stacktrace thread frames).
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

    mock_sentry.capture_exception.assert_not_called()
    mock_sentry.capture_message.assert_called_once()
    msg_args, msg_kwargs = mock_sentry.capture_message.call_args
    assert msg_kwargs.get("level") == "error"
    assert "7654321" in msg_args[0]
    assert "ValueError" in msg_args[0]
    # The tag before_send keys on is set; no (ineffective) scope processor.
    scope.set_tag.assert_any_call("error_location", "discovery_sheet_drop")
    scope.set_tag.assert_any_call("sheet_id", "7654321")
    scope.add_event_processor.assert_not_called()
    assert scope.fingerprint == ["discovery-sheet-drop", "ValueError"]
