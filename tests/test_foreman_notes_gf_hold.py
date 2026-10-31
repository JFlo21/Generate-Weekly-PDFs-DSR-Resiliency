"""Quick 261030-suf: hold pilot groups when the GF lookup fails.

Owner decision 2026-10-30 (option 1): after a good pilot run, a run whose
General Foreman lookup fails must regenerate and re-upload NO pilot group.
Nothing durable marks a group as pilot, so while the lookup has failed a
group is held iff its fresh hash differs from the stored hash.

Everything here is offline: a fake client, GF-1 / GF-2 aliases and
fictional WR numbers only. Sentry events are recorded by ``before_send``
returning ``None`` and a null transport, so nothing is ever sent.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any, Iterator
import unittest
from unittest import mock

_TESTS = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS.parent
for _p in (str(_REPO_ROOT), str(_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sentry_sdk  # noqa: E402
from sentry_sdk.transport import Transport  # noqa: E402

import _foreman_notes_golden as golden  # noqa: E402
import generate_weekly_pdfs as gwp  # noqa: E402
from pipeline import change_detection as cd  # noqa: E402
from pipeline import config  # noqa: E402
from pipeline import foreman_notes as fn  # noqa: E402
from pipeline import observability  # noqa: E402

ORCH_PATH = _REPO_ROOT / "pipeline" / "orchestrate.py"

SOURCE_SHEET = 7001
WR_COL_ID = 5180541294563204
GF_COL_ID = 2159630534528900
PILOT_WR = "90003"
OTHER_WR = "90004"
WEEK_ISO = "2026-07-26"
VARIANT = "primary"
IDENT = "ident-1"
NOTE_SENTINEL = "zz-note-sentinel-zz"
FAKE_DSN = "https://public@o0.ingest.invalid/0"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _target_sheet(
    wr_title: str = "Work Request #",
    gf_title: str = "General Foreman",
    total: int | None = None,
) -> NS:
    def cells(wr: str, gf: str) -> NS:
        return NS(cells=[
            NS(column_id=WR_COL_ID, value=wr, display_value=wr),
            NS(column_id=GF_COL_ID, value=gf, display_value=gf),
        ])

    rows = [cells(PILOT_WR, " GF-1 "), cells(OTHER_WR, "GF-2")]
    return NS(
        columns=[
            NS(id=WR_COL_ID, title=wr_title),
            NS(id=GF_COL_ID, title=gf_title),
        ],
        rows=rows,
        total_row_count=len(rows) if total is None else total,
    )


class _Sheets:
    def __init__(
        self, sheet: NS | None = None, exc: Exception | None = None
    ) -> None:
        self.sheet = sheet if sheet is not None else _target_sheet()
        self.exc = exc
        self.calls: list = []

    def get_sheet(self, sheet_id: int, **kwargs: Any) -> NS:
        self.calls.append((sheet_id, kwargs))
        if sheet_id == config.TARGET_SHEET_ID:
            if self.exc is not None:
                raise self.exc
            return self.sheet
        ids = [int(x) for x in kwargs["row_ids"].split(",")]
        return NS(rows=[
            NS(id=i, conditional_format=None, format_=None, cells=[])
            for i in ids
        ])


class _Client:
    def __init__(
        self, sheet: NS | None = None, exc: Exception | None = None
    ) -> None:
        self.Sheets = _Sheets(sheet, exc)


def _group(wr: str, **extra: Any) -> list[dict[str, Any]]:
    """Golden-shaped primary rows re-labelled to a fictional WR."""
    rows = copy.deepcopy(golden._rows(**extra))
    for n, row in enumerate(rows, start=1):
        row["Work Request #"] = wr
        row["__source_sheet_id"] = SOURCE_SHEET
        row["__row_id"] = 1000 + n
    return rows


def _history_key(wr: str) -> str:
    """The ``WR|week_iso|variant|identifier`` key main() builds."""
    return f"{wr}|{WEEK_ISO}|{VARIANT}|{IDENT}"


@contextlib.contextmanager
def fn_env(
    scope: str = "pilot", allowlist: str = "GF-1", test_mode: bool = False
) -> Iterator[None]:
    """Patch the effective scope, the allowlist, TEST_MODE and the GF
    column ids. ``test_mode`` defaults to False: a publishing run."""
    with mock.patch.object(fn, "EFFECTIVE_SCOPE", scope), \
            mock.patch.object(config, "FOREMAN_NOTES_PILOT_GFS", allowlist), \
            mock.patch.object(config, "TEST_MODE", test_mode), \
            mock.patch.object(
                config, "FOREMAN_NOTES_GF_WR_COLUMN_ID", WR_COL_ID), \
            mock.patch.object(
                config, "FOREMAN_NOTES_GF_COLUMN_ID", GF_COL_ID):
        yield


def _hash(rows: list[dict[str, Any]]) -> str:
    with golden.pinned_env():
        return cd.calculate_data_hash(rows)


def _unchanged(wr: str, data_hash: str, stored: dict) -> bool:
    with golden.pinned_env(), mock.patch.object(
            gwp, "SUPABASE_HASH_STORE_AUTHORITATIVE", False):
        return cd._resolve_unchanged_for_skip(
            _history_key(wr), data_hash, stored, wr, WEEK_ISO, VARIANT,
            IDENT, billing_audit_writer=None,
        )


class _NullTransport(Transport):
    """Transport that drops every envelope (belt and braces)."""

    def capture_envelope(self, envelope: Any) -> None:  # noqa: D102
        return None


class SentryCapture:
    """Real ``sentry_sdk.init`` whose ``before_send`` records and drops.

    The recorder runs the production frame scrub first, so assertions see
    what production would send. Nothing leaves the process.
    """

    RUN_TAGS = ("foreman_notes_scope", "foreman_notes_pilot_wrs",
                "gf_lookup")

    def __init__(self, test: unittest.TestCase) -> None:
        self.events: list[dict[str, Any]] = []

        def _before_send(event: Any, hint: Any) -> None:
            observability._scrub_sheet_drop_frame_vars(event)
            self.events.append(event)
            return None

        self._reset_scope()
        sentry_sdk.init(
            dsn=FAKE_DSN,
            include_local_variables=True,
            attach_stacktrace=True,
            before_breadcrumb=observability.sentry_before_breadcrumb,
            before_send=_before_send,
            transport=_NullTransport,
        )
        test.addCleanup(self._reset_scope)
        test.addCleanup(sentry_sdk.init, dsn=None)
        patcher = mock.patch.object(observability, "SENTRY_DSN", FAKE_DSN)
        patcher.start()
        test.addCleanup(patcher.stop)

    def _reset_scope(self) -> None:
        scope = sentry_sdk.get_isolation_scope()
        for tag in self.RUN_TAGS:
            scope.remove_tag(tag)
        scope.clear_breadcrumbs()

    def texts(self) -> list[str]:
        return [json.dumps(e, default=str) for e in self.events]

    def by_fingerprint(self, *head: str) -> list[dict[str, Any]]:
        n = len(head)
        return [
            e for e in self.events
            if list(e.get("fingerprint") or [])[:n] == list(head)
        ]


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        fn.reset_state()
        self.addCleanup(fn.reset_state)
        # A publishing run unless a test opts into TEST_MODE (D2).
        patcher = mock.patch.object(config, "TEST_MODE", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def init_good(self) -> fn.FnState:
        fn.reset_state()
        with fn_env():
            return fn.initialize(_Client())

    def init_failed(self, **client_kw: Any) -> fn.FnState:
        fn.reset_state()
        if not client_kw:
            client_kw = {"exc": RuntimeError("lookup broke")}
        with fn_env():
            return fn.initialize(_Client(**client_kw))


# ---------------------------------------------------------------------------
# Task 1: the hold sequence
# ---------------------------------------------------------------------------

class GfHoldSequenceTests(_Base):
    def test_good_then_failed_then_recovery(self) -> None:
        good = self.init_good()
        self.assertTrue(good.gf_loaded)
        self.assertFalse(good.gf_failed)
        self.assertEqual(good.pilot_wrs, frozenset({PILOT_WR}))
        stored = {
            _history_key(wr): {"hash": _hash(_group(wr))}
            for wr in (PILOT_WR, OTHER_WR)
        }

        failed = self.init_failed()
        self.assertTrue(failed.gf_failed)
        self.assertEqual(failed.gf_fail_reason, "exception")
        self.assertEqual(failed.gf_fail_exc, "RuntimeError")
        self.assertEqual(failed.pilot_wrs, frozenset())
        self.assertTrue(fn.gf_lookup_failed())

        pilot_match = _unchanged(PILOT_WR, _hash(_group(PILOT_WR)), stored)
        self.assertFalse(pilot_match)
        self.assertTrue(fn.should_hold_group(pilot_match))

        other_match = _unchanged(OTHER_WR, _hash(_group(OTHER_WR)), stored)
        self.assertTrue(other_match)
        self.assertFalse(fn.should_hold_group(other_match))

        # Accepted cost (owner-approved): a changed non-pilot group waits.
        changed = _group(OTHER_WR)
        changed[0]["Quantity"] = 99
        changed_match = _unchanged(OTHER_WR, _hash(changed), stored)
        self.assertFalse(changed_match)
        self.assertTrue(fn.should_hold_group(changed_match))

        # Recovery: the next good run re-sends nothing.
        self.init_good()
        self.assertFalse(fn.gf_lookup_failed())
        recovered = _hash(_group(PILOT_WR))
        self.assertEqual(recovered, stored[_history_key(PILOT_WR)]["hash"])
        self.assertTrue(_unchanged(PILOT_WR, recovered, stored))

    def test_failure_reasons(self) -> None:
        state = self.init_failed(sheet=_target_sheet(gf_title="Other"))
        self.assertTrue(state.gf_failed)
        self.assertEqual(state.gf_fail_reason, "columns_mismatch")
        state = self.init_failed(sheet=_target_sheet(total=5))
        self.assertTrue(state.gf_failed)
        self.assertEqual(state.gf_fail_reason, "partial_read")

    def test_failure_message_is_redacted(self) -> None:
        state = self.init_failed(exc=RuntimeError("WR 90003 broke"))
        self.assertTrue(state.gf_fail_msg.startswith("RuntimeError"))
        self.assertNotIn("90003", state.gf_fail_msg)

    def test_no_hold_outside_failed_pilot_lookup(self) -> None:
        cases = (("pilot", "GF-1", _Client()), ("off", "GF-1", _Client()),
                 ("all", "", _Client()), ("pilot", "", _Client()))
        for scope, allowlist, client in cases:
            with self.subTest(scope=scope, allowlist=allowlist):
                fn.reset_state()
                with fn_env(scope, allowlist):
                    state = fn.initialize(client)
                self.assertFalse(state.gf_failed)
                self.assertFalse(fn.gf_lookup_failed())
                self.assertFalse(fn.should_hold_group(False))

    def test_scope_off_state_unchanged(self) -> None:
        with fn_env("off"):
            self.assertEqual(fn.initialize(_Client()), fn.FnState())

    def test_no_hold_in_test_mode(self) -> None:
        """D2 (owner 2026-10-30): dry runs never upload, so never hold."""
        state = self.init_failed()
        self.assertTrue(state.gf_failed)
        with mock.patch.object(config, "TEST_MODE", True):
            self.assertFalse(fn.gf_lookup_failed())
            self.assertFalse(fn.should_hold_group(False))
        self.assertTrue(fn.gf_lookup_failed())
        self.assertTrue(fn.should_hold_group(False))

    def test_predicates_never_raise(self) -> None:
        with mock.patch.object(fn, "_STATE", None):
            self.assertFalse(fn.gf_lookup_failed())
            self.assertFalse(fn.should_hold_group(False))


# ---------------------------------------------------------------------------
# Task 1: the run-end hold event
# ---------------------------------------------------------------------------

_HELD = [(PILOT_WR, "081025", "primary")]
_FORCE = {
    "FORCE_GENERATION": False, "REGEN_WEEKS": True,
    "RESET_HASH_HISTORY": False, "RESET_WR_LIST": False,
}
_GH_ENV = {
    "GITHUB_SERVER_URL": "https://github.example",
    "GITHUB_REPOSITORY": "org/repo",
    "GITHUB_RUN_ID": "123",
}


class HoldEventTests(_Base):
    def _report(self, held: list) -> SentryCapture:
        self.init_failed()
        cap = SentryCapture(self)
        note = NOTE_SENTINEL  # noqa: F841 - frame-local leak bait
        gf_alias = "GF-1"  # noqa: F841 - frame-local leak bait
        with fn_env(), mock.patch.dict(os.environ, _GH_ENV):
            self.report = fn.report_run_end(
                held_groups=held, force_flags=_FORCE)
        return cap

    def test_one_hold_event_with_context(self) -> None:
        cap = self._report(list(_HELD))
        holds = cap.by_fingerprint("foreman-notes", "gf-hold")
        self.assertEqual(len(holds), 1)
        event = holds[0]
        self.assertEqual(event["level"], "error")  # D1
        self.assertEqual(event["fingerprint"], ["foreman-notes", "gf-hold"])
        self.assertEqual(event["tags"]["foreman_notes_scope"], "pilot")
        self.assertEqual(event["tags"]["foreman_notes_reason"], "exception")
        ctx = event["contexts"]["foreman_notes"]
        for key in ("reason", "exception_class", "exception_message",
                    "target_sheet_id", "wr_column_id", "gf_column_id",
                    "expected_titles", "held_groups", "held_total",
                    "force_flags_active", "remediation", "run_url"):
            self.assertIn(key, ctx, key)
        self.assertEqual(ctx["held_groups"], [
            {"wr": PILOT_WR, "week_ending": "081025", "variant": "primary"},
        ])
        self.assertEqual(ctx["held_total"], 1)
        self.assertEqual(ctx["run_url"],
                         "https://github.example/org/repo/actions/runs/123")
        self.assertIn(PILOT_WR, json.dumps(ctx))
        text = json.dumps(event, default=str)
        for secret in ("GF-1", "GF-2", "gf-1", "gf-2", NOTE_SENTINEL):
            self.assertNotIn(secret, text)
        # The message text names no WR.
        self.assertNotIn(PILOT_WR, event.get("message") or "")
        self.assertEqual(self.report["held_total"], 1)

    def test_hold_event_does_not_leak_onto_next_event(self) -> None:
        """F4: tags, context and fingerprint stay on the forked scope."""
        cap = self._report(list(_HELD))
        sentry_sdk.capture_message("probe")
        probe = cap.events[-1]
        self.assertEqual(probe.get("message"), "probe")
        self.assertNotIn("foreman_notes", probe.get("contexts") or {})
        tags = probe.get("tags") or {}
        for tag in ("foreman_notes_reason", "foreman_notes_scope"):
            self.assertNotIn(tag, tags)
        self.assertNotIn("fingerprint", probe)

    def test_reset_purge_skipped_in_hold_context(self) -> None:
        """F1: the hold event says the RESET_* purge was skipped."""
        self.init_failed()
        cap = SentryCapture(self)
        with fn_env():
            report = fn.report_run_end(
                held_groups=list(_HELD), force_flags=_FORCE,
                reset_purge_skipped=True)
        (event,) = cap.by_fingerprint("foreman-notes", "gf-hold")
        ctx = event["contexts"]["foreman_notes"]
        self.assertIs(ctx["reset_purge_skipped"], True)
        self.assertIs(report["reset_purge_skipped"], True)

    def test_no_hold_event_when_nothing_held(self) -> None:
        cap = self._report([])
        self.assertEqual(cap.by_fingerprint("foreman-notes", "gf-hold"), [])

    def test_held_list_capped_at_200(self) -> None:
        held = [(str(90000 + i), "081025", "primary") for i in range(205)]
        cap = self._report(held)
        (event,) = cap.by_fingerprint("foreman-notes", "gf-hold")
        ctx = event["contexts"]["foreman_notes"]
        self.assertEqual(len(ctx["held_groups"]), 200)
        self.assertEqual(ctx["held_total"], 205)

    def test_scope_off_report_is_empty(self) -> None:
        with fn_env("off"):
            fn.initialize(_Client())
            self.assertEqual(
                fn.report_run_end(held_groups=[], force_flags=_FORCE), {})


# ---------------------------------------------------------------------------
# Task 1: placement of the hold inside main()
# ---------------------------------------------------------------------------

ORCH_SOURCE = ORCH_PATH.read_text(encoding="utf-8")
ORCH_TREE = ast.parse(ORCH_SOURCE)


def _main() -> ast.FunctionDef:
    return next(
        n for n in ORCH_TREE.body
        if isinstance(n, ast.FunctionDef) and n.name == "main")


def _dotted(call: ast.Call) -> str | None:
    f = call.func
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        return f"{f.value.id}.{f.attr}"
    if isinstance(f, ast.Name):
        return f.id
    return None


def _calls(node: ast.AST, dotted: str) -> list[ast.Call]:
    return [n for n in ast.walk(node)
            if isinstance(n, ast.Call) and _dotted(n) == dotted]


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


class HoldPlacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.main = _main()

    def _hold_if(self) -> ast.If:
        ifs = [n for n in ast.walk(self.main) if isinstance(n, ast.If)
               and _calls(n.test, "_fn.gf_lookup_failed")]
        self.assertEqual(len(ifs), 1)
        return ifs[0]

    def test_single_call_sites(self) -> None:
        for dotted in ("_fn.gf_lookup_failed", "_fn.should_hold_group",
                       "_fn.report_run_end"):
            self.assertEqual(len(_calls(self.main, dotted)), 1, dotted)

    def test_hold_sits_between_no_target_gate_and_freeze(self) -> None:
        hold = self._hold_if()
        (no_target,) = _calls(self.main, "should_skip_no_target_row")
        freeze = [n for n in ast.walk(self.main) if isinstance(n, ast.If)
                  and "_has_uncached_freeze_candidates" in _names(n.test)]
        self.assertEqual(len(freeze), 1)
        excel = _calls(self.main, "generate_excel")
        self.assertTrue(excel)
        self.assertGreater(hold.lineno, no_target.lineno)
        self.assertLess(hold.lineno, freeze[0].lineno)
        for call in excel:
            self.assertLess(hold.lineno, call.lineno)

    def test_hold_body_continues_without_bookkeeping(self) -> None:
        hold = self._hold_if()
        inner = [n for n in ast.walk(hold) if isinstance(n, ast.If)
                 and _calls(n.test, "_fn.should_hold_group")]
        self.assertEqual(len(inner), 1)
        self.assertIsInstance(inner[0].body[-1], ast.Continue)
        names = _names(hold)
        for forbidden in ("_mem_confirmed_skip_keys", "generated_filenames",
                          "groups"):
            self.assertNotIn(forbidden, names)


# ---------------------------------------------------------------------------
# Task 2: attachment cleanup tolerates a held group (approved item 3)
# ---------------------------------------------------------------------------

_HELD_NAME = "WR_90003_WeekEnding_081025_120000_User_Sample_aabbcc.xlsx"
_SKIP_NAME = "WR_90004_WeekEnding_081025_120000_User_Sample_ddeeff.xlsx"


class CleanupToleranceTests(unittest.TestCase):
    """A held group keeps its last good attachment, like an unchanged skip.

    Site 2 builds ``valid_wr_weeks`` from ``groups.items()``; the hold never
    removes a group from ``groups``, so the held identity is present.
    """

    def _run(self, dry_run: bool) -> list:
        build_group_identity = cd.build_group_identity
        deleted: list = []
        client = mock.MagicMock()
        client.Attachments.delete_attachment.side_effect = (
            lambda _sid, att_id: deleted.append(att_id))
        atts = []
        for att_id, name in ((10, _HELD_NAME), (20, _SKIP_NAME)):
            att = mock.MagicMock()
            att.name = name
            att.id = att_id
            atts.append(att)
        row = mock.MagicMock()
        row.id = 111
        sheet = mock.MagicMock()
        sheet.rows = [row]
        valid = {build_group_identity(_HELD_NAME),
                 build_group_identity(_SKIP_NAME)}
        self.assertNotIn(None, valid)
        gwp.cleanup_untracked_sheet_attachments(
            client=client, target_sheet_id=5723337641643908,
            valid_wr_weeks=valid, test_mode=False,
            attachment_cache={111: atts}, target_sheet=sheet,
            dry_run=dry_run,
        )
        return deleted

    def test_dry_run_deletes_nothing(self) -> None:
        self.assertEqual(self._run(dry_run=True), [])

    def test_live_cleanup_keeps_held_like_unchanged_skip(self) -> None:
        self.assertEqual(self._run(dry_run=False), [])

    def test_site2_builds_identities_from_groups(self) -> None:
        main = _main()
        loops = [
            n for n in ast.walk(main) if isinstance(n, ast.For)
            and isinstance(n.iter, ast.Call)
            and isinstance(n.iter.func, ast.Attribute)
            and n.iter.func.attr == "items"
            and isinstance(n.iter.func.value, ast.Name)
            and n.iter.func.value.id == "groups"
            and _calls(n, "valid_wr_weeks.add")
        ]
        self.assertTrue(loops)


if __name__ == "__main__":
    unittest.main()
