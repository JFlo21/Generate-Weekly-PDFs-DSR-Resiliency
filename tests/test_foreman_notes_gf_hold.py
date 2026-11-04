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
import tempfile
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


class ApiLikeError(Exception):
    """An exception shaped like a Smartsheet ``ApiError``: free text in
    ``str()`` plus ``error.result.code`` / ``status_code``."""

    def __init__(self, msg: str, code: int, status: int) -> None:
        super().__init__(msg)
        self.error = NS(result=NS(code=code, status_code=status))


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
                "foreman_notes_held",
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

    def test_failure_fields_are_structured(self) -> None:
        """R4: no free-text exception message is kept, only the class,
        the Smartsheet API error code and the HTTP status."""
        self.assertFalse(hasattr(fn.FnState(), "gf_fail_msg"))
        state = self.init_failed(exc=ApiLikeError(
            "GF-1 Example Name note text sample", code=4003, status=403))
        self.assertEqual(state.gf_fail_exc, "ApiLikeError")
        self.assertEqual(state.gf_fail_code, 4003)
        self.assertEqual(state.gf_fail_status, 403)
        plain = self.init_failed(exc=RuntimeError("WR 90003 broke"))
        self.assertIsNone(plain.gf_fail_code)
        self.assertIsNone(plain.gf_fail_status)

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
        for key in ("reason", "exception_class", "api_error_code",
                    "http_status",
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
        for dotted in ("_fn.should_hold_group", "_fn.report_run_end"):
            self.assertEqual(len(_calls(self.main, dotted)), 1, dotted)
        # Two by design: the hold branch and the RESET_* purge gate (F1).
        self.assertEqual(
            len(_calls(self.main, "_fn.gf_lookup_failed")), 2)

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
# Fix round: orchestrate wiring (F1, F2, F3, F5, F8, D1 cron)
# ---------------------------------------------------------------------------

def _orch() -> Any:
    from pipeline import orchestrate

    return orchestrate


def _first_assign_line(node: ast.AST, name: str) -> int:
    lines = [
        n.lineno for n in ast.walk(node) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
    ]
    return min(lines) if lines else 10 ** 9


class ResetPurgeTests(unittest.TestCase):
    """F1: the RESET_* purge never runs while groups would be held."""

    def _run(
        self, hold_active: bool, wr_list: set[str], reset_all: bool
    ) -> tuple[bool, mock.MagicMock]:
        orch = _orch()
        with mock.patch.object(orch, "RESET_WR_LIST", wr_list), \
                mock.patch.object(orch, "RESET_HASH_HISTORY", reset_all), \
                mock.patch.object(
                    orch, "purge_existing_hashed_outputs") as purge:
            skipped = orch._run_reset_purge(
                object(), hold_active, test_mode=False)
        return skipped, purge

    def test_failed_lookup_skips_purge(self) -> None:
        with self.assertLogs(level="WARNING") as cm:
            skipped, purge = self._run(True, {PILOT_WR}, False)
        purge.assert_not_called()
        self.assertTrue(skipped)
        self.assertEqual(len(cm.records), 1)
        self.assertNotIn(PILOT_WR, cm.records[0].getMessage())
        skipped, purge = self._run(True, set(), True)
        purge.assert_not_called()
        self.assertTrue(skipped)

    def test_good_lookup_purges_as_before(self) -> None:
        orch = _orch()
        skipped, purge = self._run(False, {PILOT_WR}, False)
        self.assertFalse(skipped)
        purge.assert_called_once()
        args, kwargs = purge.call_args
        self.assertEqual(
            args[1:4], (orch.TARGET_SHEET_ID, {PILOT_WR}, False))
        self.assertEqual(kwargs, {"dry_run": orch.SKIP_UPLOAD})
        skipped, purge = self._run(False, set(), True)
        self.assertEqual(purge.call_args[0][2], None)

    def test_no_reset_requested_no_purge(self) -> None:
        for hold in (True, False):
            skipped, purge = self._run(hold, set(), False)
            purge.assert_not_called()
            self.assertFalse(skipped)

    def test_helper_annotates_client_like_neighbours(self) -> None:
        """R3: ``client: Any`` like the other orchestrate helpers."""
        tree = ast.parse(ORCH_SOURCE)
        (func,) = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == "_run_reset_purge"]
        ann = func.args.args[0].annotation
        self.assertEqual(getattr(ann, "id", None), "Any")
        self.assertIsNotNone(func.returns)

    def test_main_gates_purge_on_failed_lookup(self) -> None:
        main = _main()
        self.assertEqual(_calls(main, "purge_existing_hashed_outputs"), [])
        (call,) = _calls(main, "_run_reset_purge")
        self.assertEqual(len(call.args), 2)
        self.assertEqual(_dotted(call.args[1]), "_fn.gf_lookup_failed")
        kws = {k.arg: k.value for k in call.keywords}
        self.assertEqual(getattr(kws.get("test_mode"), "id", None),
                         "TEST_MODE")
        (report,) = _calls(main, "_fn.report_run_end")
        kw = {k.arg for k in report.keywords}
        self.assertIn("reset_purge_skipped", kw)


class StoredHashMatchTests(_Base):
    """F3: the stored-hash comparison ignores force flags (approved)."""

    def test_helper_contract(self) -> None:
        calls: list = []

        def resolve() -> bool:
            calls.append(1)
            return True

        self.assertTrue(fn.stored_hash_matches(True, True, resolve))
        self.assertFalse(fn.stored_hash_matches(True, False, resolve))
        self.assertEqual(calls, [])
        self.assertTrue(fn.stored_hash_matches(False, False, resolve))
        self.assertEqual(calls, [1])

        def boom() -> bool:
            raise RuntimeError("store down")

        self.assertFalse(fn.stored_hash_matches(False, False, boom))

    def test_forced_run_holds_only_mismatched_groups(self) -> None:
        self.init_good()
        stored = {
            _history_key(wr): {"hash": _hash(_group(wr))}
            for wr in (PILOT_WR, OTHER_WR)
        }
        self.init_failed()
        held = []
        for wr in (PILOT_WR, OTHER_WR):
            data_hash = _hash(_group(wr))
            # A forced run: history skip is not eligible, so main()'s
            # _hash_unchanged is False for every group.
            match = fn.stored_hash_matches(
                False, False,
                lambda wr=wr, h=data_hash: _unchanged(wr, h, stored))
            if fn.should_hold_group(match):
                held.append(wr)
        self.assertEqual(held, [PILOT_WR])

    def test_main_passes_stored_comparison_not_hash_unchanged(self) -> None:
        main = _main()
        (call,) = _calls(main, "_fn.stored_hash_matches")
        a0, a1, a2 = call.args
        self.assertEqual(
            getattr(a0, "id", None), "_history_eligible_for_skip")
        self.assertEqual(getattr(a1, "id", None), "_hash_unchanged")
        self.assertIsInstance(a2, ast.Lambda)
        self.assertTrue(_calls(a2, "_resolve_unchanged_for_skip"))
        (hold,) = _calls(main, "_fn.should_hold_group")
        self.assertEqual(
            getattr(hold.args[0], "id", None), "_fn_hash_match")


class RunEndOrderingTests(_Base):
    """F2: the run-end report follows the last notes-digest call."""

    def test_report_after_globals_fingerprint(self) -> None:
        main = _main()
        (report,) = _calls(main, "_fn.report_run_end")
        fps = _calls(
            main, "_memory_candidate.group_hash_globals_fingerprint")
        self.assertTrue(fps)
        for call in fps:
            self.assertGreater(report.lineno, call.lineno)

    def test_globals_component_failure_counted_in_event(self) -> None:
        from pipeline import memory_candidate as mc

        self.init_good()
        saved = fn.get_state()
        fn.set_state(fn.FnState(scope="pilot", allowlist=None))
        with fn_env():
            mc.group_hash_globals_fingerprint()
        fn.set_state(saved)
        cap = SentryCapture(self)
        with fn_env():
            report = fn.report_run_end(held_groups=[], force_flags={})
        (event,) = cap.by_fingerprint("foreman-notes", "notes-digest-failed")
        failures = event["contexts"]["foreman_notes"]["failures"]
        self.assertEqual(failures.get("globals_component"), 1)
        self.assertEqual(report["digest_failures"], 1)


class ParityAndVisibilityTests(_Base):
    """F5 parity, F8 operator visibility, D1 cron status."""

    def test_held_groups_unobservable_for_shadow_parity(self) -> None:
        """Candidate-only groups are not a D-07 divergence, so a held
        group cannot turn the verdict to ``fail``; it was reported as
        ``only_in_candidate`` noise. Marked unobservable, it is dropped
        and counted in ``withheld_excluded`` instead."""
        from pipeline import parity

        orch = _orch()
        held_key = f"081025_{PILOT_WR}"
        other_key = f"081025_{OTHER_WR}"
        candidate = {held_key: "h1", other_key: "h2"}
        deferred = [{"group_key": other_key, "data_hash": "h2"}]
        uploads = [{"group_key": other_key}]
        cand, actual, _ = orch._shadow_parity_input_sets(
            candidate, deferred, uploads)
        noisy = parity.compare_shadow_parity(cand, actual)
        self.assertIn(held_key, noisy["only_in_candidate"])
        cand, actual, excluded = orch._shadow_parity_input_sets(
            candidate, deferred, uploads, unobservable={held_key})
        self.assertEqual(cand, {other_key: "h2"})
        self.assertEqual(excluded, 1)
        clean = parity.compare_shadow_parity(cand, actual)
        self.assertEqual(clean["verdict"], "pass")
        self.assertEqual(clean["only_in_candidate"], [])

    def test_main_marks_held_groups_unobservable(self) -> None:
        main = _main()
        calls = _calls(main, "_shadow_parity_input_sets")
        self.assertTrue(calls)
        for call in calls:
            unobs = [k.value for k in call.keywords
                     if k.arg == "unobservable"]
            self.assertEqual(len(unobs), 1)
            names = _names(unobs[0])
            self.assertIn("_fn_held_groups", names)
            self.assertIn("_no_target_row_groups", names)

    def test_group_phase_log_names_held_count(self) -> None:
        main = _main()
        logs = [
            c for c in _calls(main, "logging.info")
            if "Group processing phase" in ast.unparse(c)
        ]
        self.assertEqual(len(logs), 1)
        self.assertIn("_fn_held_groups", _names(logs[0]))

    def test_held_count_run_tag(self) -> None:
        self.init_failed()
        cap = SentryCapture(self)
        with fn_env():
            fn.report_run_end(held_groups=list(_HELD), force_flags={})
        sentry_sdk.capture_message("probe")
        self.assertEqual(
            cap.events[-1]["tags"]["foreman_notes_held"], "1")

    def test_cron_checks_in_error_when_groups_held(self) -> None:
        main = _main()
        cron = [
            n for n in ast.walk(main) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_cron_ok"
                    for t in n.targets)
        ]
        self.assertEqual(len(cron), 1)
        self.assertIn("_fn_held_groups", _names(cron[0].value))
        # Hoisted above the main try so the finally block can read it.
        (init,) = _calls(main, "_fn.initialize")
        self.assertLess(
            _first_assign_line(main, "_fn_held_groups"), init.lineno)
        self.assertLess(
            _first_assign_line(main, "_fn_run_report"), init.lineno)


# ---------------------------------------------------------------------------
# Task 2: attachment cleanup tolerates a held group (approved item 3)
# ---------------------------------------------------------------------------

_LEGACY_SUFFIX = "000002_abcdef0123456789.xlsx"


class CleanupToleranceTests(_Base):
    """A held group keeps its last good attachment (approved item 3).

    F6: the held identity is derived from the held group's ROWS exactly as
    Site 2 does (``groups.items()`` -> canonical first row ->
    ``derive_group_identity``), the attachment name comes from a real
    ``generate_excel`` call in the good run, and cleanup runs live
    (``dry_run=False``) against a client that records deletes.
    """

    def setUp(self) -> None:
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.init_good()
        self.key = f"{golden.WEEK_RAW}_{PILOT_WR}"
        self.rows = _group(PILOT_WR)
        with golden.pinned_env(output_folder=tmp.name):
            data_hash = cd.calculate_data_hash(self.rows)
            path, *_rest = gwp.generate_excel(
                self.key, self.rows, golden.SNAPSHOT_DATE,
                data_hash=data_hash)
        self.held_name = Path(path).name
        self.init_failed()  # the held run

    def _site2_identity(self) -> tuple:
        """Mirror of orchestrate.main() Site 2 for one group."""
        from pipeline import orchestrate as orch

        week_raw = self.key.split("_", 1)[0]
        first = cd.canonical_first_row(self.rows)
        wr = fn.norm_wr(first.get("Work Request #"))
        variant = first.get("__variant", "primary")
        with golden.pinned_env():
            _, file_id = orch.derive_group_identity(
                first, primary_claim_enabled=True,
                vac_crew_claim_enabled=True, res_grouping_mode="both")
        return (wr, week_raw, variant, file_id)

    def _older(self, name: str) -> str:
        parts = name.split("_")
        parts[parts.index("WeekEnding") + 2] = "000001"
        return "_".join(parts)

    def _cleanup(
        self, names: list[str], valid: set[tuple[str, ...]],
        dry_run: bool = False, **kwargs: Any,
    ) -> list[str]:
        deleted: list[int] = []
        client = mock.MagicMock()
        client.Attachments.delete_attachment.side_effect = (
            lambda _sid, att_id: deleted.append(att_id))
        atts = []
        for att_id, name in enumerate(names, start=10):
            att = mock.MagicMock()
            att.name = name
            att.id = att_id
            atts.append(att)
        row = mock.MagicMock()
        row.id = 111
        sheet = mock.MagicMock()
        sheet.rows = [row]
        with golden.pinned_env():
            gwp.cleanup_untracked_sheet_attachments(
                client=client, target_sheet_id=5723337641643908,
                valid_wr_weeks=valid, test_mode=False,
                attachment_cache={111: atts}, target_sheet=sheet,
                dry_run=dry_run, **kwargs,
            )
        return [names[i - 10] for i in deleted]

    def test_site2_identity_matches_uploaded_name(self) -> None:
        self.assertEqual(
            self._site2_identity(), cd.build_group_identity(self.held_name))

    def test_dry_run_deletes_nothing(self) -> None:
        names = [self.held_name, self._older(self.held_name)]
        self.assertEqual(
            self._cleanup(names, {self._site2_identity()}, dry_run=True),
            [])

    def test_live_cleanup_keeps_held_newest(self) -> None:
        older = self._older(self.held_name)
        deleted = self._cleanup(
            [self.held_name, older], {self._site2_identity()})
        self.assertEqual(deleted, [older])  # live: prunes, keeps newest

    def _legacy_primary(self) -> str:
        name = f"WR_{PILOT_WR}_WeekEnding_{golden.WEEK_RAW}_{_LEGACY_SUFFIX}"
        wr, week, variant, ident = cd.build_group_identity(name)
        self.assertEqual((wr, variant), (PILOT_WR, "primary"))
        self.assertFalse(ident)
        return name

    def test_f7_legacy_scope_cannot_delete_held_wr_file(self) -> None:
        legacy = self._legacy_primary()
        valid = {self._site2_identity()}
        risky = self._cleanup([legacy], valid, primary_wr_scope={PILOT_WR})
        self.assertEqual(risky, [legacy])  # the pre-fix risk
        held = {(PILOT_WR, golden.WEEK_RAW)}
        kept = self._cleanup([legacy], valid, primary_wr_scope={PILOT_WR},
                             held_wr_weeks=held)
        self.assertEqual(kept, [])

    def test_f7_held_helper_cannot_orphan_primary(self) -> None:
        helper = (PILOT_WR, golden.WEEK_RAW, "helper", "Sam_Sample")
        risky = self._cleanup([self.held_name], {helper})
        self.assertEqual(risky, [self.held_name])  # the pre-fix risk
        kept = self._cleanup(
            [self.held_name], {helper},
            held_wr_weeks={(PILOT_WR, golden.WEEK_RAW)})
        self.assertEqual(kept, [])

    def test_f7_ppp_whitelist_cannot_delete_held_file(self) -> None:
        # PPP cleanup passes a variant whitelist; a held pair's file must
        # survive it the same as every other prune rule.
        ppp = {"variant_whitelist": {"reduced_sub", "reduced_sub_helper"}}
        valid = {self._site2_identity()}
        risky = self._cleanup([self.held_name], valid, **ppp)
        self.assertEqual(risky, [self.held_name])  # the pre-fix risk
        kept = self._cleanup(
            [self.held_name], valid,
            held_wr_weeks={(PILOT_WR, golden.WEEK_RAW)}, **ppp)
        self.assertEqual(kept, [])

    def test_f7_main_passes_held_pairs_to_every_cleanup(self) -> None:
        main = _main()
        calls = _calls(main, "cleanup_untracked_sheet_attachments")
        self.assertEqual(len(calls), 2)
        for call in calls:
            kw = {k.arg: k.value for k in call.keywords}
            self.assertIn("held_wr_weeks", kw)
            self.assertIn("_fn_held_wr_weeks", _names(kw["held_wr_weeks"]))
        sources = [
            n.value for n in ast.walk(main) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_fn_held_wr_weeks"
                    for t in n.targets)
        ]
        self.assertEqual(len(sources), 1)
        self.assertIn("_fn_held_groups", _names(sources[0]))

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


# ---------------------------------------------------------------------------
# Fail-closed 2026-11-03: hold a pilot group whose notes token raised
# ---------------------------------------------------------------------------

# Hashes pinned from master 13a1dcb1 (pre-fix) for the fixture groups
# under ``golden.pinned_env``. Happy paths must stay byte-identical: any
# drift would regenerate every group on the next production run.
_PINNED = {
    # (extended, wr, token raises): hash
    (True, PILOT_WR, False): "af96c8e2057a46b7",
    (True, OTHER_WR, False): "30ff59324721bf11",
    (False, PILOT_WR, False): "d97f4e96575c1df7",
    (False, OTHER_WR, False): "2e8b88983c3d4fae",
    # Failure path: change_detection is untouched, so a raising token
    # still hashes WITHOUT NOTES_FP exactly as before the fix.
    (True, PILOT_WR, True): "d376950ecac3977e",
    (True, OTHER_WR, True): "30ff59324721bf11",
    (False, PILOT_WR, True): "542b63538e57949c",
    (False, OTHER_WR, True): "2e8b88983c3d4fae",
}
_TOKEN_HELD = (PILOT_WR, "081025", "primary", "notes_token_failed")


def _hash_mode(
    rows: list[dict[str, Any]], extended: bool = True, boom: bool = False
) -> str:
    """Group hash in either mode; ``boom`` makes the notes token raise."""
    with contextlib.ExitStack() as stack:
        stack.enter_context(golden.pinned_env())
        stack.enter_context(mock.patch.object(
            gwp, "EXTENDED_CHANGE_DETECTION", extended))
        if boom:
            stack.enter_context(mock.patch.object(
                fn, "norm_note", side_effect=RuntimeError("token broke")))
        return cd.calculate_data_hash(rows)


class TokenFailureHoldTests(_Base):
    """RED on master: the token failure dropped NOTES_FP silently and
    nothing could tell the group apart, so it was never held."""

    def test_failed_token_drops_notes_fp_and_is_held(self) -> None:
        self.init_good()
        rows = _group(PILOT_WR)
        failed = _hash_mode(rows, boom=True)
        self.assertNotEqual(failed, _hash_mode(rows))
        with fn_env("off"):
            fn.set_state(fn.FnState())
            no_notes_fp = _hash_mode(rows)
        self.assertEqual(failed, no_notes_fp)  # the silent drop
        self.init_good()
        _hash_mode(rows, boom=True)
        self.assertTrue(fn.token_failure_recorded(rows))
        self.assertTrue(fn.notes_token_failed(list(reversed(rows))))
        self.assertEqual(fn.get_state().scope, "pilot")

    def test_failure_registered_per_variant(self) -> None:
        self.init_good()
        rows = _group(PILOT_WR)
        for row in rows:
            row["__variant"] = "primary"
        _hash_mode(rows, boom=True)
        helper = copy.deepcopy(rows)
        for row in helper:
            row["__variant"] = "helper"
        self.assertTrue(fn.notes_token_failed(rows))
        self.assertFalse(fn.notes_token_failed(helper))

    def test_happy_path_records_nothing(self) -> None:
        self.init_good()
        for extended in (True, False):
            for wr in (PILOT_WR, OTHER_WR):
                _hash_mode(_group(wr), extended)
        self.assertEqual(fn._RUN_FAILURES["token_failed_groups"], set())
        self.assertFalse(fn.notes_token_failed(_group(PILOT_WR)))

    def test_hashes_byte_identical_to_master(self) -> None:
        for (extended, wr, boom), expected in _PINNED.items():
            with self.subTest(extended=extended, wr=wr, boom=boom):
                self.init_good()
                self.assertEqual(
                    _hash_mode(_group(wr), extended, boom), expected)

    def test_non_pilot_raising_helper_not_held(self) -> None:
        self.init_good()
        for extended in (True, False):
            rows = _group(OTHER_WR)
            self.assertEqual(
                _hash_mode(rows, extended, boom=True),
                _PINNED[(extended, OTHER_WR, False)],
            )
            self.assertFalse(fn.token_failure_recorded(rows))
            self.assertFalse(fn.notes_token_failed(rows))
        self.assertEqual(fn._RUN_FAILURES["digest"], {})

    def test_never_holds_in_test_mode(self) -> None:
        """D2: a dry run never uploads, so never holds; the failure is
        still recorded and counted."""
        self.init_good()
        rows = _group(PILOT_WR)
        with mock.patch.object(config, "TEST_MODE", True):
            _hash_mode(rows, boom=True)
            self.assertTrue(fn.token_failure_recorded(rows))
            self.assertFalse(fn.notes_token_failed(rows))
        self.assertEqual(
            fn._RUN_FAILURES["digest"], {"group_notes_token": 1})

    def test_scope_off_token_is_empty_and_never_held(self) -> None:
        with fn_env("off"):
            fn.initialize(_Client())
            rows = _group(PILOT_WR)
            with mock.patch.object(
                    fn, "norm_note", side_effect=RuntimeError("x")):
                self.assertEqual(
                    fn.group_notes_token(rows, lambda r: ""), "")
            self.assertFalse(fn.notes_token_failed(rows))

    def test_registry_cleared_by_reset_state(self) -> None:
        self.init_good()
        rows = _group(PILOT_WR)
        _hash_mode(rows, boom=True)
        fn.reset_state()
        self.assertFalse(fn.token_failure_recorded(rows))

    def test_predicates_never_raise(self) -> None:
        self.assertIsNone(fn._token_group_key(None))
        self.assertFalse(fn.notes_token_failed(None))
        self.assertFalse(fn.notes_token_failed([object()]))
        with mock.patch.object(fn, "_RUN_FAILURES", {}):
            self.assertFalse(fn.notes_token_failed(_group(PILOT_WR)))
            fn._record_token_failure(_group(PILOT_WR))
        self.assertEqual(fn.held_reason_label(None), "GF lookup failed")


class TokenHoldReportTests(_Base):
    def _report(self, held: list) -> SentryCapture:
        self.init_good()
        _hash_mode(_group(PILOT_WR), boom=True)
        cap = SentryCapture(self)
        with fn_env(), mock.patch.dict(os.environ, _GH_ENV):
            self.report = fn.report_run_end(
                held_groups=held, force_flags=_FORCE)
        return cap

    def test_report_counts_token_held_groups(self) -> None:
        self._report([_TOKEN_HELD])
        report = self.report
        self.assertEqual(report["held_total"], 1)
        self.assertEqual(report["held_by_reason"], {
            "gf_lookup_failed": 0, "notes_token_failed": 1})
        self.assertEqual(report["token_failed_total"], 1)
        self.assertEqual(report["token_failures_recorded"], 1)
        self.assertEqual(report["digest_failures"], 1)
        # The report rides the shared session_summary context: counts
        # only, no WR (DECISIONS 2026-10-30).
        self.assertNotIn(PILOT_WR, json.dumps(report))

    def test_digest_event_lists_token_held_groups(self) -> None:
        cap = self._report([_TOKEN_HELD])
        # No new channel: no gf-hold event; the digest event fires once.
        self.assertEqual(cap.by_fingerprint("foreman-notes", "gf-hold"), [])
        (event,) = cap.by_fingerprint(
            "foreman-notes", "notes-digest-failed")
        ctx = event["contexts"]["foreman_notes"]
        self.assertEqual(ctx["held_reason"], "notes_token_failed")
        self.assertEqual(ctx["token_failed_groups"], [
            {"wr": PILOT_WR, "week_ending": "081025", "variant": "primary"},
        ])
        self.assertEqual(ctx["token_failed_total"], 1)
        self.assertEqual(ctx["failures"], {"group_notes_token": 1})
        self.assertNotIn(PILOT_WR, event.get("message") or "")
        for text in cap.texts():
            for secret in ("GF-1", "GF-2", NOTE_SENTINEL):
                self.assertNotIn(secret, text)

    def test_digest_event_unchanged_without_token_holds(self) -> None:
        cap = self._report([])
        (event,) = cap.by_fingerprint(
            "foreman-notes", "notes-digest-failed")
        ctx = event["contexts"]["foreman_notes"]
        for key in ("held_reason", "token_failed_groups",
                    "token_failed_total"):
            self.assertNotIn(key, ctx)

    def test_token_held_list_capped_at_200(self) -> None:
        held = [(str(90000 + i), "081025", "primary", "notes_token_failed")
                for i in range(205)]
        cap = self._report(held)
        (event,) = cap.by_fingerprint(
            "foreman-notes", "notes-digest-failed")
        ctx = event["contexts"]["foreman_notes"]
        self.assertEqual(len(ctx["token_failed_groups"]), 200)
        self.assertEqual(ctx["token_failed_total"], 205)
        self.assertEqual(self.report["token_failed_total"], 205)

    def test_gf_hold_event_counts_only_gf_holds(self) -> None:
        self.init_failed()
        cap = SentryCapture(self)
        with fn_env():
            report = fn.report_run_end(
                held_groups=list(_HELD) + [_TOKEN_HELD], force_flags=_FORCE)
        (event,) = cap.by_fingerprint("foreman-notes", "gf-hold")
        ctx = event["contexts"]["foreman_notes"]
        self.assertEqual(ctx["held_total"], 1)
        self.assertEqual(len(ctx["held_groups"]), 1)
        self.assertEqual(report["held_total"], 2)
        self.assertEqual(report["held_by_reason"], {
            "gf_lookup_failed": 1, "notes_token_failed": 1})

    def test_gf_only_report_lists_no_token_groups(self) -> None:
        self.init_failed()
        with fn_env():
            report = fn.report_run_end(
                held_groups=list(_HELD), force_flags=_FORCE)
        self.assertEqual(report["token_failed_total"], 0)
        self.assertEqual(report["held_by_reason"], {
            "gf_lookup_failed": 1, "notes_token_failed": 0})

    def test_held_reason_label(self) -> None:
        self.assertEqual(
            fn.held_reason_label([_HELD[0]]), "GF lookup failed")
        self.assertEqual(
            fn.held_reason_label([_TOKEN_HELD]), "notes token failed")
        self.assertEqual(
            fn.held_reason_label([_HELD[0], _TOKEN_HELD]),
            "GF lookup failed / notes token failed")


class TokenHoldPlacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.main = _main()

    def _token_if(self) -> ast.If:
        ifs = [n for n in ast.walk(self.main) if isinstance(n, ast.If)
               and _calls(n.test, "_fn.notes_token_failed")]
        self.assertEqual(len(ifs), 1)
        return ifs[0]

    def test_checks_the_hashed_group_rows(self) -> None:
        (call,) = _calls(self._token_if().test, "_fn.notes_token_failed")
        self.assertEqual([a.id for a in call.args], ["group_rows"])

    def test_after_gf_hold_before_freeze_and_excel(self) -> None:
        hold = self._token_if()
        gf = [n for n in ast.walk(self.main) if isinstance(n, ast.If)
              and _calls(n.test, "_fn.gf_lookup_failed")
              and _calls(n, "_fn.should_hold_group")]
        self.assertEqual(len(gf), 1)
        freeze = [n for n in ast.walk(self.main) if isinstance(n, ast.If)
                  and "_has_uncached_freeze_candidates" in _names(n.test)]
        self.assertGreater(hold.lineno, gf[0].lineno)
        self.assertLess(hold.lineno, freeze[0].lineno)
        for call in _calls(self.main, "generate_excel"):
            self.assertLess(hold.lineno, call.lineno)

    def test_holds_regardless_of_hash_and_continues(self) -> None:
        hold = self._token_if()
        self.assertIsInstance(hold.body[-1], ast.Continue)
        names = _names(hold)
        self.assertIn("_fn_held_groups", names)
        for forbidden in ("_hash_unchanged", "_mem_confirmed_skip_keys",
                          "generated_filenames", "data_hash"):
            self.assertNotIn(forbidden, names)
        attrs = {n.attr for n in ast.walk(hold)
                 if isinstance(n, ast.Attribute)}
        self.assertIn("HOLD_NOTES_TOKEN", attrs)
        self.assertEqual(fn.HOLD_NOTES_TOKEN, "notes_token_failed")


class RunReportContractTests(_Base):
    """The dict main() puts on ``session_summary.foreman_notes``: its key
    set is a deliberate contract (counts only, no WR)."""

    _KEYS = [
        "digest_failures", "digest_failures_by_function", "gf_lookup",
        "held_by_reason", "held_total", "reset_purge_skipped", "scope",
        "style_attach_failures", "style_failed_chunks",
        "style_rows_affected", "style_rows_missing", "token_failed_total",
        "token_failures_recorded",
    ]

    def test_pilot_run_without_holds_key_set(self) -> None:
        self.init_good()
        with fn_env():
            report = fn.report_run_end(held_groups=[], force_flags=_FORCE)
        self.assertEqual(sorted(report), self._KEYS)
        self.assertEqual(report["held_by_reason"], {
            "gf_lookup_failed": 0, "notes_token_failed": 0})
        self.assertEqual(report["token_failed_total"], 0)
        self.assertEqual(report["token_failures_recorded"], 0)


_BOOM_NOTE = "zz-token-boom-zz"


class TokenHoldMainLoopTests(_Base):
    """Behavioural: drive the real ``orchestrate.main()`` group loop over
    one pilot and one non-pilot group, recording which groups reach the
    billing-audit freeze, ``generate_excel``, the upload worker and the
    deferred ``group_state`` flush. Offline: fake Smartsheet client,
    mocked billing-audit and memory writers, ``SKIP_UPLOAD`` so nothing
    is published, and a forked Sentry isolation scope."""

    def _drive(self, boom: bool) -> dict[str, list[str]]:
        import concurrent.futures
        from pipeline import orchestrate as orch

        seen: dict[str, list[str]] = {
            "freeze": [], "excel": [], "upload": [], "group_state": []}
        rows = _group(PILOT_WR) + _group(OTHER_WR)
        for n, row in enumerate(rows):
            row["__row_id"] = 5000 + n
        if boom:
            rows[0][fn.NOTES_KEY] = _BOOM_NOTE
        real_norm, real_init = fn.norm_note, fn.initialize

        def norm(value: Any) -> str:
            if value == _BOOM_NOTE:
                raise RuntimeError("token broke")
            return real_norm(value)

        def init(client: Any) -> fn.FnState:
            with fn_env():
                return real_init(_Client())

        def excel(group_key: str, group_rows: list, *a: Any,
                  **k: Any) -> tuple:
            seen["excel"].append(str(group_rows[0]["Work Request #"]))
            return ("x.xlsx", "x.xlsx", [], "", [])

        def tasks(**k: Any) -> list[dict[str, Any]]:
            return [{
                "group_key": k["group_key"], "target_row": NS(id=1),
                "target_sheet_id": 1, "wr_num": k["wr_num"],
                "week_raw": k["week_raw"], "data_hash": k["data_hash"],
                "variant": k["variant"], "identifier": "",
                "file_identifier": "", "filename": "x.xlsx",
                "excel_path": "x.xlsx",
            }]

        def delete(client: Any, sid: Any, row: Any, wr: Any,
                   *a: Any, **k: Any) -> tuple:
            seen["upload"].append(str(wr))
            return 0, False

        def flush(deferred: list, *a: Any, **k: Any) -> tuple:
            seen["group_state"].extend(str(d["wr_num"]) for d in deferred)
            return [], 0

        def freeze(row: dict, **k: Any) -> bool:
            seen["freeze"].append(str(row.get("Work Request #")))
            return False

        executor = concurrent.futures.ThreadPoolExecutor(2)
        self.addCleanup(executor.shutdown)
        writer = mock.MagicMock()
        writer.any_flag_enabled.return_value = True
        writer.freeze_row.side_effect = freeze
        writer.get_freeze_row_executor.return_value = executor
        values = (
            (orch, "API_TOKEN", "fake-token"), (gwp, "TEST_MODE", False),
            (gwp, "SENTRY_DSN", None), (gwp, "BILLING_AUDIT_AVAILABLE", True),
            (gwp, "_billing_audit_writer", writer),
            (orch, "RUN_MEMORY_WRITE_ENABLED", True),
            (orch, "SKIP_UPLOAD", True),
            (orch, "_mem_writer", mock.MagicMock()),
            (fn, "EFFECTIVE_SCOPE", "pilot"),
        )
        fakes = (
            (orch, "_sentry_cron_checkin_start", {"return_value": None}),
            (orch.smartsheet, "Smartsheet", {}),
            (orch, "discover_source_sheets", {"return_value": [
                {"id": SOURCE_SHEET, "name": "S", "column_mapping": {}}]}),
            (orch, "get_all_source_rows", {"return_value": rows}),
            (orch, "generate_excel", {"side_effect": excel}),
            (orch, "_build_upload_tasks_for_group", {"side_effect": tasks}),
            (orch, "delete_old_excel_attachments", {"side_effect": delete}),
            (orch, "_build_group_state_flush", {"side_effect": flush}),
            (fn, "initialize", {"side_effect": init}),
            (fn, "norm_note", {"side_effect": norm}),
        )
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            stack.enter_context(golden.pinned_env(output_folder=tmp))
            for module, name, value in values:
                stack.enter_context(mock.patch.object(module, name, value))
            for module, name, kw in fakes:
                stack.enter_context(mock.patch.object(module, name, **kw))
            stack.enter_context(sentry_sdk.isolation_scope())
            orch.main()
        return seen

    def test_token_held_group_reaches_nothing_downstream(self) -> None:
        seen = self._drive(boom=True)
        for stage, wrs in seen.items():
            with self.subTest(stage=stage):
                self.assertNotIn(PILOT_WR, wrs)
                self.assertIn(OTHER_WR, wrs)

    def test_same_group_without_token_failure_is_generated(self) -> None:
        seen = self._drive(boom=False)
        for stage, wrs in seen.items():
            with self.subTest(stage=stage):
                self.assertIn(PILOT_WR, wrs)
                self.assertIn(OTHER_WR, wrs)


if __name__ == "__main__":
    unittest.main()
