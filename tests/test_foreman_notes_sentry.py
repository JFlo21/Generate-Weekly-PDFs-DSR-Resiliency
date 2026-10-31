"""Quick 261030-suf Task 2: Foreman Notes Sentry gap closure (C1-C6).

Every Foreman Notes failure path must reach Sentry with enough detail to
audit and fix it, while General Foreman names and note text never leave.
WR numbers may appear only in the structured ``foreman_notes`` context
(owner-approved exception, docs/DECISIONS.md 2026-10-30).

Offline only: GF-1 / GF-2 aliases, fictional WRs, and a real
``sentry_sdk.init`` whose ``before_send`` records and drops every event.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any
import unittest
from unittest import mock

_TESTS = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS.parent
for _p in (str(_REPO_ROOT), str(_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sentry_sdk  # noqa: E402

from pipeline import config  # noqa: E402
from pipeline import foreman_notes as fn  # noqa: E402
from pipeline import observability  # noqa: E402
from test_foreman_notes_gf_hold import (  # noqa: E402
    NOTE_SENTINEL,
    PILOT_WR,
    SOURCE_SHEET,
    SentryCapture,
    _Client,
    _group,
    _target_sheet,
    fn_env,
)

ORCH_PATH = _REPO_ROOT / "pipeline" / "orchestrate.py"
SECRETS = ("GF-1", "GF-2", "gf-1", "gf-2", NOTE_SENTINEL)
LOOKUP_KEYS = (
    "reason", "exception_class", "exception_message", "target_sheet_id",
    "wr_column_id", "gf_column_id", "expected_titles", "allowlist_count",
    "remediation",
)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        fn.reset_state()
        self.addCleanup(fn.reset_state)
        patcher = mock.patch.object(config, "TEST_MODE", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_no_secrets(self, cap: SentryCapture) -> None:
        for text in cap.texts():
            for secret in SECRETS:
                self.assertNotIn(secret, text)


# ---------------------------------------------------------------------------
# C1: a failed lookup sends its own event at initialize time
# ---------------------------------------------------------------------------

class LookupFailedEventTests(_Base):
    def _failing_clients(self) -> dict[str, Any]:
        return {
            "exception": _Client(exc=RuntimeError("lookup broke")),
            "columns_mismatch": _Client(sheet=_target_sheet(gf_title="X")),
            "partial_read": _Client(sheet=_target_sheet(total=9)),
        }

    def _assert_one(
        self, cap: SentryCapture, reason: str, level: str = "error"
    ) -> None:
        events = cap.by_fingerprint("foreman-notes", "gf-lookup-failed")
        self.assertEqual(len(events), 1, reason)
        event = events[0]
        self.assertEqual(
            event["fingerprint"],
            ["foreman-notes", "gf-lookup-failed", reason])
        # D1: ERROR on a publishing run; a dry run stays a warning.
        self.assertEqual(event["level"], level)
        ctx = event["contexts"]["foreman_notes"]
        for key in LOOKUP_KEYS:
            self.assertIn(key, ctx, key)
        self.assertEqual(ctx["reason"], reason)
        self.assertEqual(ctx["allowlist_count"], 1)
        self.assert_no_secrets(cap)

    def test_each_reason_sends_one_event(self) -> None:
        for reason, client in self._failing_clients().items():
            with self.subTest(reason=reason):
                fn.reset_state()
                cap = SentryCapture(self)
                with fn_env():
                    fn.initialize(client)
                self._assert_one(cap, reason)

    def test_event_still_fires_in_test_mode(self) -> None:
        """D2: no hold in TEST_MODE, but the lookup failure is reported."""
        cap = SentryCapture(self)
        with fn_env(test_mode=True):
            fn.initialize(_Client(exc=RuntimeError("lookup broke")))
            self.assertFalse(fn.gf_lookup_failed())
        self._assert_one(cap, "exception", level="warning")

    def test_lookup_event_does_not_leak_onto_next_event(self) -> None:
        """F4: per-event tags / context / fingerprint stay scoped."""
        cap = SentryCapture(self)
        with fn_env():
            fn.initialize(_Client(exc=RuntimeError("lookup broke")))
        sentry_sdk.capture_message("probe")
        probe = cap.events[-1]
        self.assertEqual(probe.get("message"), "probe")
        self.assertNotIn("foreman_notes", probe.get("contexts") or {})
        self.assertNotIn("foreman_notes_reason", probe.get("tags") or {})
        self.assertNotIn("fingerprint", probe)

    def test_outer_handler_sends_one_event(self) -> None:
        cap = SentryCapture(self)
        with fn_env(), mock.patch.object(
                fn, "load_gf_lookup", side_effect=ValueError("boom")):
            fn.initialize(_Client())
        self._assert_one(cap, "initialize_failed")

    def test_no_event_without_a_failed_lookup(self) -> None:
        cases = (("off", "GF-1"), ("all", ""), ("pilot", ""),
                 ("pilot", "GF-1"))
        for scope, allowlist in cases:
            with self.subTest(scope=scope, allowlist=allowlist):
                fn.reset_state()
                cap = SentryCapture(self)
                with fn_env(scope, allowlist):
                    fn.initialize(_Client())
                self.assertEqual(cap.events, [])

    def _crumbs(self, scope: str, allowlist: str, client: Any) -> list:
        with mock.patch.object(sentry_sdk, "add_breadcrumb") as add:
            with fn_env(scope, allowlist):
                fn.initialize(client)
        return [c.kwargs for c in add.call_args_list
                if c.kwargs.get("category") == "foreman_notes"]

    def test_breadcrumbs(self) -> None:
        (ok,) = self._crumbs("pilot", "GF-1", _Client())
        self.assertEqual(ok["message"], "initialized")
        self.assertEqual(ok["level"], "info")
        self.assertEqual(
            ok["data"], {"allowlist_count": 1, "gf_rows": 2, "pilot_wrs": 1})
        fn.reset_state()
        (bad,) = self._crumbs(
            "pilot", "GF-1", _Client(exc=RuntimeError("x")))
        self.assertNotEqual(bad["message"], "initialized")
        self.assertEqual(bad["message"], "gf lookup failed")
        self.assertEqual(bad["level"], "warning")
        self.assertEqual(bad["data"]["reason"], "exception")
        fn.reset_state()
        (empty,) = self._crumbs("pilot", "", _Client())
        self.assertEqual(empty["message"], "pilot allowlist empty")
        self.assertEqual(empty["level"], "warning")


# ---------------------------------------------------------------------------
# C2: memory_write_blocked is tagged and fingerprinted on a forked scope
# ---------------------------------------------------------------------------

class MemoryWriteBlockedEventTests(_Base):
    def test_one_scoped_error_event(self) -> None:
        cap = SentryCapture(self)
        with mock.patch.object(fn, "EFFECTIVE_SCOPE", "pilot"), \
                mock.patch.object(config, "TEST_MODE", True), \
                mock.patch.object(config, "FOREMAN_NOTES_UPLOAD", False):
            self.assertTrue(fn.memory_write_blocked("row_state"))
            self.assertTrue(fn.memory_write_blocked("row_state"))
        self.assertEqual(len(cap.events), 1)
        event = cap.events[0]
        self.assertEqual(event["level"], "error")
        self.assertEqual(event["tags"]["foreman_notes"], "1")
        self.assertEqual(event["tags"]["memory_kind"], "row_state")
        self.assertEqual(
            event["fingerprint"],
            ["foreman-notes", "memory-write-blocked", "row_state"])
        self.assertEqual(
            event["logentry"]["message"],
            "Foreman notes: blocked pipeline_memory write during dry-run "
            "pilot (kind=%s)")
        sentry_sdk.capture_message("unrelated probe")
        probe = cap.events[-1]
        self.assertNotIn("foreman_notes", probe.get("tags") or {})
        self.assertNotIn("memory_kind", probe.get("tags") or {})
        self.assertNotIn("fingerprint", probe)


# ---------------------------------------------------------------------------
# C3 / C4: style-fetch and notes-digest failures reach Sentry at run end
# ---------------------------------------------------------------------------

class _FailingStyleSheets:
    def get_sheet(self, sheet_id: int, **kwargs: Any) -> Any:
        raise ConnectionError("style fetch down")


class _ExplodingMaps(dict):
    def __bool__(self) -> bool:
        return True

    def get(self, *args: Any, **kwargs: Any) -> Any:  # noqa: D102
        raise KeyError("maps broke")


MAPS = {SOURCE_SHEET: {"Pole #": 11, "CU": 12, "Quantity": 16}}


class RunEndFailureEventTests(_Base):
    def _pilot(self) -> None:
        with fn_env():
            fn.initialize(_Client())

    def _report(self) -> dict:
        with fn_env():
            return fn.report_run_end(held_groups=[], force_flags={})

    def test_style_failures_send_one_event(self) -> None:
        self._pilot()
        rows = _group(PILOT_WR)
        client = type("C", (), {"Sheets": _FailingStyleSheets()})()
        fn.attach_group_styles(client, rows, MAPS)
        fn.reset_style_cache()  # so the next call reaches the maps again
        fn.attach_group_styles(_Client(), _group(PILOT_WR), _ExplodingMaps())
        cap = SentryCapture(self)
        report = self._report()
        (event,) = cap.by_fingerprint("foreman-notes", "style-fetch-failed")
        self.assertEqual(event["level"], "warning")
        ctx = event["contexts"]["foreman_notes"]
        self.assertEqual(ctx["failed_chunks"], 1)
        self.assertEqual(ctx["rows_affected"], len(rows))
        self.assertEqual(ctx["attach_failures"], 1)
        self.assertEqual(
            ctx["exception_classes"], ["ConnectionError", "KeyError"])
        self.assertEqual(ctx["reason"], "style_fetch_failed")
        self.assertEqual(report["style_failed_chunks"], 1)
        self.assertEqual(report["style_attach_failures"], 1)
        self.assert_no_secrets(cap)

    def test_digest_failures_send_one_event(self) -> None:
        self._pilot()
        row = {"Work Request #": PILOT_WR, "Foreman Notes": NOTE_SENTINEL}
        with mock.patch.object(fn, "norm_note", side_effect=ValueError()):
            self.assertIsNone(fn.row_notes_component(row))

        def _bad_identity(_row: Any) -> str:
            raise TypeError("identity broke")

        self.assertEqual(fn.group_notes_token([row], _bad_identity), "")
        saved = fn.get_state()
        fn.set_state(fn.FnState(scope="pilot", allowlist=None))
        self.assertEqual(fn.globals_component(), "")
        fn.set_state(saved)
        cap = SentryCapture(self)
        report = self._report()
        (event,) = cap.by_fingerprint("foreman-notes", "notes-digest-failed")
        self.assertEqual(event["level"], "warning")
        ctx = event["contexts"]["foreman_notes"]
        self.assertEqual(ctx["failures"], {
            "row_notes_component": 1, "group_notes_token": 1,
            "globals_component": 1,
        })
        self.assertEqual(
            ctx["exception_classes"], ["TypeError", "ValueError"])
        self.assertEqual(report["digest_failures"], 3)
        self.assert_no_secrets(cap)

    def test_zero_failures_zero_events(self) -> None:
        self._pilot()
        fn.attach_group_styles(_Client(), _group(PILOT_WR), MAPS)
        cap = SentryCapture(self)
        report = self._report()
        self.assertEqual(cap.events, [])
        self.assertEqual(report["style_failed_chunks"], 0)
        self.assertEqual(report["digest_failures"], 0)

    def test_counters_reset(self) -> None:
        self._pilot()
        with mock.patch.object(fn, "norm_note", side_effect=ValueError()):
            fn.row_notes_component({"Work Request #": PILOT_WR})
        fn.reset_state()
        self._pilot()
        self.assertEqual(self._report()["digest_failures"], 0)
        with mock.patch.object(fn, "norm_note", side_effect=ValueError()):
            fn.row_notes_component({"Work Request #": PILOT_WR})
        self._pilot()  # initialize alone also resets the counters
        self.assertEqual(self._report()["digest_failures"], 0)


# ---------------------------------------------------------------------------
# C5: run-level tags on the isolation scope
# ---------------------------------------------------------------------------

class RunTagTests(_Base):
    def _probe(self, scope: str, allowlist: str, client: Any) -> dict:
        cap = SentryCapture(self)
        with fn_env(scope, allowlist):
            fn.initialize(client)
        sentry_sdk.capture_message("probe")
        return cap.events[-1]["tags"]

    def test_tags_follow_lookup_outcome(self) -> None:
        tags = self._probe("pilot", "GF-1", _Client())
        self.assertEqual(tags["foreman_notes_scope"], "pilot")
        self.assertEqual(tags["foreman_notes_pilot_wrs"], "1")
        self.assertEqual(tags["gf_lookup"], "ok")
        fn.reset_state()
        tags = self._probe("pilot", "GF-1", _Client(exc=RuntimeError("x")))
        self.assertEqual(tags["gf_lookup"], "failed")
        self.assertEqual(tags["foreman_notes_pilot_wrs"], "0")
        fn.reset_state()
        tags = self._probe("off", "", _Client())
        self.assertEqual(tags["foreman_notes_scope"], "off")
        self.assertEqual(tags["gf_lookup"], "skipped")

    def test_outer_handler_sets_failed_tag(self) -> None:
        cap = SentryCapture(self)
        with fn_env(), mock.patch.object(
                fn, "load_gf_lookup", side_effect=ValueError("boom")):
            fn.initialize(_Client())
        sentry_sdk.capture_message("probe")
        self.assertEqual(cap.events[-1]["tags"]["gf_lookup"], "failed")

    def test_noop_without_dsn(self) -> None:
        with mock.patch.object(observability, "SENTRY_DSN", None), \
                mock.patch.object(
                    sentry_sdk, "get_isolation_scope") as get_scope:
            observability.set_foreman_notes_run_tags("pilot", 1, "ok")
        get_scope.assert_not_called()


# ---------------------------------------------------------------------------
# C6: PII defence in depth + leak test
# ---------------------------------------------------------------------------

class PiiDefenceTests(_Base):
    def test_breadcrumb_keys_stripped(self) -> None:
        crumb = {"message": "m", "data": {
            "gf": "GF-1", "gf_name": "GF-1", "general_foreman": "GF-2",
            "allowlist": "GF-1", "note": "x", "notes": "x",
            "foreman_notes_text": "x", "allowlist_count": 1,
        }}
        out = observability.sentry_before_breadcrumb(crumb, None)
        self.assertEqual(out["data"], {"allowlist_count": 1})

    def test_narrow_log_marker_only(self) -> None:
        markers = observability._PII_LOG_MARKERS
        self.assertIn("foreman_notes_text", markers)
        for broad in ("note", "notes", "gf", "Foreman notes"):
            self.assertNotIn(broad, markers)
        body = "Foreman notes: allowlist=1 gf_rows=2 pilot_wrs=1"
        self.assertEqual(
            observability.sentry_before_send_log({"body": body}, None),
            {"body": body})

    def test_frame_locals_never_leak(self) -> None:
        fn.reset_state()
        with fn_env():
            fn.initialize(_Client(exc=RuntimeError("lookup broke")))
        cap = SentryCapture(self)

        def _inside_except() -> None:
            gf_name = "GF-1"  # noqa: F841 - leak bait
            other_gf = "GF-2"  # noqa: F841 - leak bait
            note = NOTE_SENTINEL  # noqa: F841 - leak bait
            try:
                raise RuntimeError("held")
            except RuntimeError:
                with fn_env():
                    fn.report_run_end(
                        held_groups=[(PILOT_WR, "081025", "primary")],
                        force_flags={})

        _inside_except()
        (event,) = cap.by_fingerprint("foreman-notes", "gf-hold")
        self.assertIn("foreman_notes", event["contexts"])
        self.assertEqual(
            event["contexts"]["foreman_notes"]["held_groups"][0]["wr"],
            PILOT_WR)
        text = json.dumps(event, default=str)
        for secret in SECRETS:
            self.assertNotIn(secret, text)


# ---------------------------------------------------------------------------
# session_summary carries the run report only when non-empty
# ---------------------------------------------------------------------------

class SessionSummaryTests(unittest.TestCase):
    def test_report_added_only_when_truthy(self) -> None:
        source = ORCH_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        guarded = [
            n for n in ast.walk(main) if isinstance(n, ast.If)
            and isinstance(n.test, ast.Name)
            and n.test.id == "_fn_run_report"
        ]
        self.assertEqual(len(guarded), 1)
        body_src = "".join(
            ast.get_source_segment(source, s) for s in guarded[0].body)
        self.assertIn('"foreman_notes"', body_src)


if __name__ == "__main__":
    unittest.main()
