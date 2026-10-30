"""Phase 11 Plan 12 (G-11-37 mechanism B): regeneration debt is carried
across run boundaries so the D-04 candidate set stays a SUPERSET of what
the next full run regenerates.

``row_state`` advances during the memory write, before any upload, and the
affected set is "changed this run" only. A run that is cancelled, times
out, or fails an upload strands groups whose durable group hash never
advanced; the next run's row diff no longer contains them, yet the full
run regenerates them (live: cancelled 40751825583 then manual 40757294483
regenerated ~12 groups vs 4 affected pairs).

Debt is carried with NO DDL in ``pipeline_memory.run_ledger.notes``.

Class layout:
  - ReducerTests / PairsToJsonTests / ShadowCandidatePairsTests -- the
    pure functions in ``pipeline.memory_candidate`` (Task 1).
  - ReaderTests / WriterNotePendingTests -- the bounded SELECT and the
    UPDATE-only mid-run note (Task 1).
  - KilledRunReplayTests -- the 40751825583 -> 40757294483 shape end to
    end through the real ``_filter_groups_to_affected`` and
    ``compare_shadow_parity`` (Task 1).
  - UnconfirmedPairsTests / FinishWiringTests -- Task 2.
  - IncrementalPathTests -- Task 3.

Self-contained (no tests/conftest.py); no live Supabase / Smartsheet call.
"""

from __future__ import annotations

import inspect
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import memory_candidate as mc  # noqa: E402
from pipeline import parity  # noqa: E402
import pipeline.orchestrate as orch  # noqa: E402


def _row(started="2026-11-01T10:00:00+00:00", status="success",
         finished="2026-11-01T11:00:00+00:00", notes=None):
    return {
        "run_id": "r", "started_at": started, "finished_at": finished,
        "status": status, "notes": notes,
    }


# ── Pure reducer ────────────────────────────────────────────────────────

class ReducerTests(unittest.TestCase):
    def test_killed_run_pending_pairs_are_carried(self):
        rows = [
            _row(status="running", finished=None, notes={
                "regen_pending_pairs": [["91427660", "2026-11-01"]],
                "regen_pending_overflow": False,
            }),
            _row(notes={"regen_debt_pairs": []}),
        ]
        self.assertEqual(
            mc.regen_debt_from_ledger_rows(rows),
            {("91427660", "2026-11-01")},
        )

    def test_success_row_debt_is_carried(self):
        rows = [_row(notes={"regen_debt_pairs": [["1", "2026-11-08"]]})]
        self.assertEqual(
            mc.regen_debt_from_ledger_rows(rows), {("1", "2026-11-08")},
        )

    def test_clean_success_chain_is_empty_debt_not_unknown(self):
        rows = [_row(notes={"regen_debt_pairs": []})]
        self.assertEqual(mc.regen_debt_from_ledger_rows(rows), set())

    def test_failed_row_debt_and_killed_row_union(self):
        rows = [
            _row(status="failed", notes={"regen_debt_pairs": [["a", "w1"]]}),
            _row(status="running", finished=None,
                 notes={"regen_pending_pairs": [["b", "w2"]]}),
            _row(notes={"regen_debt_pairs": [["c", "w3"]]}),
        ]
        self.assertEqual(
            mc.regen_debt_from_ledger_rows(rows),
            {("a", "w1"), ("b", "w2"), ("c", "w3")},
        )

    def test_stops_at_first_success_row(self):
        rows = [
            _row(notes={"regen_debt_pairs": [["new", "w"]]}),
            # Older than the first success: must be ignored, even legacy.
            _row(status="running", finished=None, notes=None),
        ]
        self.assertEqual(
            mc.regen_debt_from_ledger_rows(rows), {("new", "w")},
        )

    def test_unknown_when_newest_success_row_is_legacy(self):
        rows = [_row(notes={"execution_type": "manual"})]
        self.assertIsNone(mc.regen_debt_from_ledger_rows(rows))

    def test_unknown_when_killed_row_has_no_note(self):
        rows = [
            _row(status="running", finished=None, notes={}),
            _row(notes={"regen_debt_pairs": []}),
        ]
        self.assertIsNone(mc.regen_debt_from_ledger_rows(rows))

    def test_unknown_when_killed_row_notes_null(self):
        rows = [
            _row(status="running", finished=None, notes=None),
            _row(notes={"regen_debt_pairs": []}),
        ]
        self.assertIsNone(mc.regen_debt_from_ledger_rows(rows))

    def test_unknown_on_any_overflow_or_unknown_flag(self):
        for flag_notes in (
            {"regen_pending_pairs": [], "regen_pending_overflow": True},
            {"regen_debt_pairs": [], "regen_debt_overflow": True},
            {"regen_debt_pairs": [], "regen_debt_unknown": True},
        ):
            with self.subTest(flag_notes=flag_notes):
                status = "running" if "regen_pending_pairs" in flag_notes \
                    else "success"
                rows = [
                    _row(status=status,
                         finished=None if status == "running" else "x",
                         notes=flag_notes),
                    _row(notes={"regen_debt_pairs": []}),
                ]
                self.assertIsNone(mc.regen_debt_from_ledger_rows(rows))

    def test_unknown_when_rows_none_or_not_a_list(self):
        self.assertIsNone(mc.regen_debt_from_ledger_rows(None))
        self.assertIsNone(mc.regen_debt_from_ledger_rows("nope"))

    def test_unknown_when_no_success_row_in_scan(self):
        rows = [
            _row(status="failed", notes={"regen_debt_pairs": []}),
            _row(status="running", finished=None,
                 notes={"regen_pending_pairs": []}),
        ]
        self.assertIsNone(mc.regen_debt_from_ledger_rows(rows))
        self.assertIsNone(mc.regen_debt_from_ledger_rows([]))

    def test_unknown_on_malformed_pair_elements(self):
        for bad in ([["only-one"]], ["notalist"], [["a", "b", "c"]], "str",
                    [None]):
            with self.subTest(bad=bad):
                rows = [_row(notes={"regen_debt_pairs": bad})]
                self.assertIsNone(mc.regen_debt_from_ledger_rows(rows))

    def test_null_started_at_row_is_skipped_never_the_newest(self):
        rows = [
            # A NULL started_at row must not be treated as the newest run.
            _row(started=None, status="running", finished=None, notes=None),
            _row(notes={"regen_debt_pairs": [["x", "w"]]}),
        ]
        self.assertEqual(
            mc.regen_debt_from_ledger_rows(rows), {("x", "w")},
        )

    def test_non_dict_row_is_unknown_never_raises(self):
        self.assertIsNone(mc.regen_debt_from_ledger_rows([object()]))

    def test_week_none_round_trips(self):
        rows = [_row(notes={"regen_debt_pairs": [["wr", None]]})]
        self.assertEqual(
            mc.regen_debt_from_ledger_rows(rows), {("wr", None)},
        )


class PairsToJsonTests(unittest.TestCase):
    def test_sorted_lists_and_no_overflow_at_cap(self):
        pairs = {("b", "2026-11-08"), ("a", "2026-11-01")}
        out, overflow = mc.pairs_to_json(pairs)
        self.assertEqual(
            out, [["a", "2026-11-01"], ["b", "2026-11-08"]],
        )
        self.assertFalse(overflow)

    def test_exactly_cap_is_not_overflow(self):
        pairs = {(str(i), "w") for i in range(mc.REGEN_DEBT_MAX_PAIRS)}
        out, overflow = mc.pairs_to_json(pairs)
        self.assertEqual(len(out), mc.REGEN_DEBT_MAX_PAIRS)
        self.assertFalse(overflow)

    def test_cap_plus_one_overflows_to_empty(self):
        pairs = {(str(i), "w") for i in range(mc.REGEN_DEBT_MAX_PAIRS + 1)}
        self.assertEqual(mc.pairs_to_json(pairs), ([], True))

    def test_none_week_sorts_without_raising(self):
        out, overflow = mc.pairs_to_json({("a", None), ("a", "2026-11-01")})
        self.assertEqual(len(out), 2)
        self.assertFalse(overflow)

    def test_constants(self):
        self.assertEqual(mc.REGEN_DEBT_MAX_PAIRS, 5000)
        self.assertEqual(mc.REGEN_DEBT_SCAN_LIMIT, 20)


class ShadowCandidatePairsTests(unittest.TestCase):
    def test_union(self):
        self.assertEqual(
            mc.shadow_candidate_pairs({("a", "w")}, {("b", "w")}),
            {("a", "w"), ("b", "w")},
        )

    def test_empty_debt_is_affected(self):
        self.assertEqual(
            mc.shadow_candidate_pairs({("a", "w")}, set()), {("a", "w")},
        )

    def test_never_raises_on_none_inputs(self):
        self.assertEqual(mc.shadow_candidate_pairs(None, None), set())


# ── Reader ──────────────────────────────────────────────────────────────

class ReaderTests(unittest.TestCase):
    def setUp(self):
        from pipeline_memory import client as mem_client
        mem_client.reset_cache_for_tests()

    def tearDown(self):
        from pipeline_memory import client as mem_client
        mem_client.reset_cache_for_tests()

    def _chain(self, client):
        return (
            client.schema.return_value.table.return_value
            .select.return_value.order.return_value.limit.return_value
        )

    def test_selects_orders_nulls_last_and_limits(self):
        from pipeline_memory import reader as mem_reader

        client = mock.Mock()
        data = [_row(), _row()]
        self._chain(client).execute.return_value = SimpleNamespace(data=data)
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client,
        ):
            out = mem_reader.get_recent_run_ledger_rows(7)
        self.assertEqual(out, data)
        client.schema.assert_called_with("pipeline_memory")
        client.schema.return_value.table.assert_called_with("run_ledger")
        select = client.schema.return_value.table.return_value.select
        select.assert_called_once_with(
            "run_id,started_at,finished_at,status,notes",
        )
        select.return_value.order.assert_called_once_with(
            "started_at", desc=True, nullsfirst=False,
        )
        select.return_value.order.return_value.limit.assert_called_once_with(7)

    def test_none_client_returns_none(self):
        from pipeline_memory import reader as mem_reader
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=None,
        ):
            self.assertIsNone(mem_reader.get_recent_run_ledger_rows())

    def test_failure_returns_none(self):
        from pipeline_memory import reader as mem_reader
        client = mock.Mock()
        self._chain(client).execute.side_effect = Exception("boom")
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client,
        ):
            self.assertIsNone(mem_reader.get_recent_run_ledger_rows())

    def test_empty_result_is_empty_list_not_none(self):
        from pipeline_memory import reader as mem_reader
        client = mock.Mock()
        self._chain(client).execute.return_value = SimpleNamespace(data=[])
        with mock.patch(
            "pipeline_memory.reader.get_client", return_value=client,
        ):
            self.assertEqual(mem_reader.get_recent_run_ledger_rows(), [])


# ── Writer ──────────────────────────────────────────────────────────────

class WriterNotePendingTests(unittest.TestCase):
    def setUp(self):
        from pipeline_memory import client as mem_client
        mem_client.reset_cache_for_tests()
        self._env = mock.patch.dict(os.environ, {
            "RUN_MEMORY_WRITE_ENABLED": "1",
        })
        self._env.start()
        self.addCleanup(self._env.stop)

    def tearDown(self):
        from pipeline_memory import client as mem_client
        mem_client.reset_cache_for_tests()

    def test_issues_update_by_run_id_never_upsert_or_insert(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        table = client.schema.return_value.table.return_value
        table.update.return_value.eq.return_value.execute.return_value = (
            SimpleNamespace(data=[{"run_id": "run-9"}])
        )
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            mem_writer.run_ledger_note_pending(
                "run-9", [["a", "2026-11-01"]], False,
            )

        client.schema.assert_called_with("pipeline_memory")
        client.schema.return_value.table.assert_called_with("run_ledger")
        table.update.assert_called_once()
        table.upsert.assert_not_called()
        table.insert.assert_not_called()
        payload = table.update.call_args.args[0]
        self.assertEqual(set(payload), {"notes"})
        self.assertEqual(
            set(payload["notes"]),
            {"regen_pending_pairs", "regen_pending_overflow"},
        )
        self.assertEqual(
            payload["notes"]["regen_pending_pairs"], [["a", "2026-11-01"]],
        )
        self.assertFalse(payload["notes"]["regen_pending_overflow"])
        table.update.return_value.eq.assert_called_once_with(
            "run_id", "run-9",
        )

    def test_zero_row_match_creates_nothing_and_does_not_raise(self):
        # run_ledger_start failed -> no row. The UPDATE matches zero rows;
        # nothing may be created (an inserted NULL started_at row would
        # sort first under DESC and falsely trip D-02 trigger 6).
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        table = client.schema.return_value.table.return_value
        table.update.return_value.eq.return_value.execute.return_value = (
            SimpleNamespace(data=[])
        )
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            mem_writer.run_ledger_note_pending("ghost", [], False)
        table.upsert.assert_not_called()
        table.insert.assert_not_called()

    def test_never_raises_when_client_raises(self):
        from pipeline_memory import writer as mem_writer

        client = mock.Mock()
        (
            client.schema.return_value.table.return_value
            .update.return_value.eq.return_value.execute.side_effect
        ) = Exception("boom")
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            mem_writer.run_ledger_note_pending("r", [["a", "w"]], False)

    def test_none_client_and_disabled_flag_are_noops(self):
        from pipeline_memory import writer as mem_writer

        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=None,
        ):
            mem_writer.run_ledger_note_pending("r", [], False)

        client = mock.Mock()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ), mock.patch(
            "pipeline_memory.writer._client_write_enabled",
            return_value=False,
        ):
            mem_writer.run_ledger_note_pending("r", [], False)
        client.schema.assert_not_called()


# ── End to end: 40751825583 (cancelled) -> 40757294483 (manual) ─────────

def _group(wr, week):
    return [{
        "Work Request #": wr,
        "Weekly Reference Logged Date": week,
    }]


class KilledRunReplayTests(unittest.TestCase):
    """4 affected pairs; 12 actual groups, 8 of which belong to 3 pairs
    present ONLY in the killed run's pending note."""

    def setUp(self):
        self.affected = {
            ("100", "2026-11-01"), ("101", "2026-11-01"),
            ("102", "2026-11-01"), ("103", "2026-11-01"),
        }
        self.stranded = {
            ("200", "2026-11-01"), ("201", "2026-11-01"),
            ("202", "2026-11-08"),
        }
        self.groups = {}
        # 4 groups for the affected pairs (1 each).
        for wr, week in sorted(self.affected):
            self.groups[f"{wr}|{week}|a"] = _group(wr, week)
        # 8 groups for the 3 stranded pairs (3 + 3 + 2).
        for (wr, week), n in zip(sorted(self.stranded), (3, 3, 2)):
            for i in range(n):
                self.groups[f"{wr}|{week}|s{i}"] = _group(wr, week)
        self.assertEqual(len(self.groups), 12)
        self.hashes = {gk: f"h-{gk}" for gk in self.groups}
        # The killed run advanced row_state for its pairs (the stranded
        # ones included) before dying; its pending note recorded them.
        self.ledger_rows = [
            _row(status="running", finished=None, notes={
                "regen_pending_pairs": [list(p) for p in sorted(
                    self.stranded | {("100", "2026-11-01")},
                )],
                "regen_pending_overflow": False,
            }),
            _row(notes={"regen_debt_pairs": []}),
        ]

    def _verdict(self, candidate_pairs):
        cand_groups = orch._filter_groups_to_affected(
            self.groups, candidate_pairs,
        )
        cand_hashes = {gk: self.hashes[gk] for gk in cand_groups}
        deferred = [
            {"group_key": gk, "data_hash": self.hashes[gk]}
            for gk in self.groups
        ]
        uploads = [{"group_key": gk} for gk in self.groups]
        cand, actual, _w = orch._shadow_parity_input_sets(
            cand_hashes, deferred, uploads, unobservable=set(),
        )
        return parity.compare_shadow_parity(cand, actual)

    def test_without_debt_the_stranded_groups_are_only_in_actual(self):
        result = self._verdict(self.affected)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(len(result["only_in_actual"]), 8)

    def test_with_debt_the_verdict_passes(self):
        debt = mc.regen_debt_from_ledger_rows(self.ledger_rows)
        self.assertIsNotNone(debt)
        candidate = mc.shadow_candidate_pairs(self.affected, debt)
        result = self._verdict(candidate)
        self.assertEqual(result["verdict"], "pass", result)

    def test_replay_names_the_live_run_ids(self):
        # Provenance marker for the fixture shape (live runs).
        self.assertIn("40757294483", inspect.getsource(type(self)))
        self.assertIn("40751825583", inspect.getsource(type(self)))



class MainWiringTests(unittest.TestCase):
    """Source-inspection pins for the main() wiring (the convention
    tests/test_incremental_read.py uses for logic too deep in main())."""

    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(orch.main)

    def test_debt_is_read_before_run_ledger_start(self):
        src = self.src
        self.assertEqual(src.count("get_recent_run_ledger_rows("), 1)
        self.assertLess(
            src.index("get_recent_run_ledger_rows("),
            src.index("run_ledger_start("),
        )
        self.assertIn("_mem_ledger_rows = _mem_reader", src)

    def test_pending_note_follows_the_memory_write(self):
        src = self.src
        self.assertEqual(src.count("_note_pending_regen_pairs("), 2)
        self.assertGreater(
            src.index("_note_pending_regen_pairs("),
            src.index("_mem_regen_unknown = True"),
        )

    def test_deletion_pairs_are_renoted_right_after_reconciliation(self):
        """PR #435 (Copilot): mark_rows_deleted commits before the finish,
        so the reconcile pairs are noted before the audit / upload kill
        points, or a killed deep run loses them for good."""
        src = self.src
        second = src.index(
            "_note_pending_regen_pairs(", src.index("_reconcile_result = "),
        )
        self.assertLess(second, src.index("audit_system = BillingAudit("))
        self.assertIn(
            "_mem_candidate_pairs | _reconcile_affected_pairs,",
            src[second:second + 300],
        )

    def test_shadow_filters_by_candidate_pairs_and_skips_on_unknown(self):
        src = self.src
        self.assertIn("groups, _mem_candidate_pairs,", src)
        self.assertIn('"reason": "regen_debt_unknown"', src)
        self.assertIn('"regen_debt_carried"', src)



# ── Task 2: confirm or carry each pending pair at finish ────────────────

class UnconfirmedPairsTests(unittest.TestCase):
    def test_pair_with_all_groups_confirmed_is_cleared(self):
        pending = {("1", "w")}
        group_pairs = {"g1": ("1", "w"), "g2": ("1", "w")}
        self.assertEqual(
            mc.unconfirmed_pairs(pending, group_pairs, {"g1", "g2"}, False),
            set(),
        )

    def test_pair_with_one_unconfirmed_group_is_carried(self):
        pending = {("1", "w")}
        group_pairs = {"g1": ("1", "w"), "g2": ("1", "w")}
        self.assertEqual(
            mc.unconfirmed_pairs(pending, group_pairs, {"g1"}, False),
            {("1", "w")},
        )

    def test_zero_group_pair_cleared_unscoped_carried_scoped(self):
        pending = {("9", "w")}
        self.assertEqual(
            mc.unconfirmed_pairs(pending, {}, set(), scoped=False), set(),
        )
        self.assertEqual(
            mc.unconfirmed_pairs(pending, {}, set(), scoped=True),
            {("9", "w")},
        )

    def test_groups_of_non_pending_pairs_are_ignored(self):
        pending = {("1", "w")}
        group_pairs = {"g1": ("1", "w"), "other": ("2", "w")}
        self.assertEqual(
            mc.unconfirmed_pairs(pending, group_pairs, {"g1"}, False),
            set(),
        )

    def test_internal_error_returns_full_pending(self):
        pending = {("1", "w")}
        self.assertEqual(
            mc.unconfirmed_pairs(pending, None, None, False), pending,
        )


class FinishKwargsTests(unittest.TestCase):
    """``_regen_debt_finish_kwargs`` / ``_regen_debt_failure_kwargs``: the
    pure builders behind the two run_ledger_finish call sites."""

    def _kw(self, **over):
        base = dict(
            candidate_pairs={("1", "2026-11-01")},
            groups={"g1": _group("1", "2026-11-01")},
            skip_keys=set(),
            upload_ok={},
            deferred_records=[],
            upload_tasks=[],
            no_target_groups=set(),
            scoped=False,
            debt_unknown=False,
        )
        base.update(over)
        return orch._regen_debt_finish_kwargs(**base)

    def test_upload_failure_in_success_run_carries_the_pair(self):
        out = self._kw(
            upload_ok={"g1": False},
            deferred_records=[{"group_key": "g1"}],
            upload_tasks=[{"group_key": "g1"}],
        )
        self.assertEqual(out["regen_debt_pairs"], [["1", "2026-11-01"]])
        self.assertFalse(out["regen_debt_unknown"])

    def test_time_budget_stop_carries_the_pair(self):
        # g1 in groups, neither skipped nor uploaded nor generated.
        out = self._kw()
        self.assertEqual(out["regen_debt_pairs"], [["1", "2026-11-01"]])

    def test_hash_skip_clears_the_pair(self):
        out = self._kw(skip_keys={"g1"})
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_successful_upload_clears_the_pair(self):
        out = self._kw(
            upload_ok={"g1": True},
            deferred_records=[{"group_key": "g1"}],
            upload_tasks=[{"group_key": "g1"}],
        )
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_withheld_generated_group_counts_as_confirmed(self):
        # Generated but no upload task: never observable.
        out = self._kw(deferred_records=[{"group_key": "g1"}])
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_no_target_row_group_counts_as_confirmed(self):
        out = self._kw(no_target_groups={"g1"})
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_scoped_run_carries_zero_group_pair_unscoped_clears(self):
        pending = {("9", "2026-11-01")}
        self.assertEqual(
            self._kw(candidate_pairs=pending, groups={}, scoped=True)[
                "regen_debt_pairs"], [["9", "2026-11-01"]],
        )
        self.assertEqual(
            self._kw(candidate_pairs=pending, groups={}, scoped=False)[
                "regen_debt_pairs"], [],
        )

    def test_unknown_flag_passes_through(self):
        self.assertTrue(self._kw(debt_unknown=True)["regen_debt_unknown"])

    def test_inherited_unknown_widens_pending_to_every_group_pair(self):
        # Inherited debt was unknowable: a stranded group outside this
        # run's candidate must still be carried if it is not confirmed.
        out = self._kw(
            candidate_pairs=set(),
            groups={"g1": _group("7", "2026-11-01")},
            inherited_unknown=True,
        )
        self.assertEqual(out["regen_debt_pairs"], [["7", "2026-11-01"]])

    def test_overflow_reports_empty_list_and_flag(self):
        many = {(str(i), "2026-11-01") for i in range(mc.REGEN_DEBT_MAX_PAIRS + 1)}
        out = self._kw(candidate_pairs=many, groups={}, scoped=True)
        self.assertEqual(out["regen_debt_pairs"], [])
        self.assertTrue(out["regen_debt_overflow"])

    def test_internal_error_marks_unknown(self):
        out = orch._regen_debt_finish_kwargs(
            candidate_pairs=None, groups=object(), skip_keys=None,
            upload_ok=None, deferred_records=None, upload_tasks=None,
            no_target_groups=None, scoped=False, debt_unknown=False,
        )
        self.assertTrue(out["regen_debt_unknown"])

    def test_failure_path_carries_full_pending_without_confirmation(self):
        out = orch._regen_debt_failure_kwargs(
            {("1", "2026-11-01"), ("2", "2026-11-01")}, debt_unknown=False,
        )
        self.assertEqual(
            out["regen_debt_pairs"], [["1", "2026-11-01"], ["2", "2026-11-01"]],
        )
        self.assertFalse(out["regen_debt_unknown"])
        self.assertTrue(
            orch._regen_debt_failure_kwargs(set(), debt_unknown=True)[
                "regen_debt_unknown"]
        )


class UnknownFlagRuleTests(unittest.TestCase):
    def test_unknown_iff_unconfirmed_sheets_with_rows_sent(self):
        f = orch._memory_write_may_have_advanced_unseen
        self.assertTrue(f({"sheets_unconfirmed": 1, "rows_sent": 5}))
        self.assertFalse(f({"sheets_unconfirmed": 1, "rows_sent": 0}))
        self.assertFalse(f({"sheets_unconfirmed": 0, "rows_sent": 5}))
        self.assertFalse(f({}))


class AttachmentRepairTagTests(unittest.TestCase):
    def test_tags_only_in_actual_groups_that_hit_the_repair_site(self):
        out = orch._attachment_repair_only_in_actual(
            actual_hashes={"a": "1", "b": "2", "c": "3"},
            candidate_hashes={"c": "3"},
            repair_keys={"a", "c", "zzz"},
        )
        self.assertEqual(out, ["a"])

    def test_capped_at_ten_and_stringified(self):
        actual = {(i, "x"): "h" for i in range(25)}
        out = orch._attachment_repair_only_in_actual(
            actual, {}, set(actual),
        )
        self.assertEqual(len(out), 10)
        self.assertTrue(all(isinstance(x, str) for x in out))

    def test_verdict_inputs_unchanged(self):
        actual = {"a": "1"}
        cand = {}
        orch._attachment_repair_only_in_actual(actual, cand, {"a"})
        self.assertEqual(
            parity.compare_shadow_parity(cand, actual)["verdict"], "fail",
        )


class FinishWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(orch.main)

    def test_both_finish_sites_carry_debt_kwargs(self):
        self.assertIn("_regen_debt_finish_kwargs(", self.src)
        self.assertIn("_regen_debt_failure_kwargs(", self.src)

    def test_skip_and_repair_sites_record_membership(self):
        src = self.src
        skip_i = src.index("Skip (unchanged + attachment exists)")
        rep_i = src.index(
            "Regenerating despite same hash (attachment missing)"
        )
        self.assertIn(
            "_mem_confirmed_skip_keys.add(group_key)",
            src[skip_i - 400:skip_i + 600],
        )
        self.assertIn(
            "_mem_attachment_repair_keys.add(group_key)",
            src[rep_i - 700:rep_i + 400],
        )

    def test_shadow_reports_attachment_repair_tag(self):
        self.assertIn("only_in_actual_attachment_repair", self.src)



# ── Task 3: the incremental path consumes the same candidate ────────────

class IncrementalPathTests(unittest.TestCase):
    """``_run_phase2_incremental(regen_debt=...)``: D-04 candidate =
    affected | carried debt (flag OFF in production)."""

    def _run(self, regen_debt, **kw):
        from tests.test_incremental_read import (
            _delta_row, _delta_sheet, _delta_source,
        )
        import datetime

        source = _delta_source(sheet_id=111222)
        sheet = _delta_sheet([_delta_row(1, "90001", "2026-08-30")])
        write = mock.Mock(return_value={
            "sheets_written": 1, "sheets_errored": 0,
            "rows_sent": 1, "rows_changed": 1,
            "affected": {("90001", "2026-08-30")},
            "memory_confirmed": True,
        })
        mapping = mock.Mock(return_value={111222})
        with mock.patch.object(
            orch._fetch, "fetch_sheet_delta",
            return_value={
                "escalate": False, "sheet": sheet, "version": 9, "calls": 2,
            },
        ), mock.patch.object(
            orch, "_run_memory_write_phase", write,
        ), mock.patch.object(
            orch._mem_reader, "map_affected_to_sheets", mapping,
        ), mock.patch.object(
            orch, "get_all_source_rows", return_value=[],
        ):
            args = dict(
                client=mock.Mock(),
                source_sheets=[source],
                watermarks={111222: {
                    "last_sheet_version": 8,
                    "last_read_at": "2026-08-26T18:00:00+00:00",
                }},
                per_sheet_reasons={},
                mem_run_id="run-1",
                session_start=datetime.datetime.now(),
            )
            if regen_debt != "OMIT":
                args["regen_debt"] = regen_debt
            args.update(kw)
            result = orch._run_phase2_incremental(**args)
        return result, write, mapping

    def test_default_debt_is_empty_and_behaviour_unchanged(self):
        result, _w, mapping = self._run("OMIT")
        self.assertTrue(result["ok"])
        mapping.assert_called_once_with({("90001", "2026-08-30")})
        self.assertEqual(result["candidate_pairs"], result["affected"])
        sig = inspect.signature(orch._run_phase2_incremental)
        self.assertEqual(
            sig.parameters["regen_debt"].default, frozenset(),
        )
        self.assertEqual(
            sig.parameters["regen_debt"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )

    def test_debt_pair_widens_the_sheet_mapping_and_candidate(self):
        debt = {("80001", "2026-08-23")}
        result, _w, mapping = self._run(debt)
        self.assertTrue(result["ok"])
        mapping.assert_called_once_with(
            {("90001", "2026-08-30"), ("80001", "2026-08-23")},
        )
        self.assertIn(("80001", "2026-08-23"), result["candidate_pairs"])
        # The memory affected set (counters) is NOT widened.
        self.assertEqual(result["affected"], {("90001", "2026-08-30")})

    def test_unknown_debt_forces_full_before_any_write(self):
        result, write, mapping = self._run(None)
        self.assertFalse(result["ok"])
        self.assertTrue(
            result["fallback_reason"].startswith("trigger_regen_debt_unknown")
        )
        write.assert_not_called()
        mapping.assert_not_called()


class IncrementalMainWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(orch.main)

    def test_main_passes_debt_and_consumes_candidate_pairs(self):
        src = self.src
        self.assertIn("regen_debt=_mem_regen_debt", src)
        self.assertIn(
            "groups = _filter_groups_to_affected(groups, _mem_candidate_pairs)",
            src,
        )
        self.assertIn(
            "_incremental_empty_affected_run = not _mem_candidate_pairs", src,
        )
        self.assertNotIn(
            "_incremental_empty_affected_run = not _mem_affected", src,
        )


# ── PR #435 feedback: coverage, ledger-start confirmation ───────────────

class CoverageIncompleteTests(unittest.TestCase):
    """Issue 1: debt is cleared only from a COMPLETE groups map. MAX_GROUPS
    truncation, a failed source-sheet read or a non-'both' grouping mode
    can hide some of a pair's groups, so every pending pair is carried."""

    def test_incomplete_coverage_carries_pair_with_confirmed_groups(self):
        pending = {("1", "w")}
        group_pairs = {"g1": ("1", "w")}
        self.assertEqual(
            mc.unconfirmed_pairs(
                pending, group_pairs, {"g1"}, False,
                coverage_complete=False,
            ),
            {("1", "w")},
        )

    def test_incomplete_coverage_carries_zero_group_pair_unscoped(self):
        pending = {("9", "w")}
        self.assertEqual(
            mc.unconfirmed_pairs(
                pending, {}, set(), False, coverage_complete=False,
            ),
            {("9", "w")},
        )

    def test_complete_coverage_is_the_default(self):
        sig = inspect.signature(mc.unconfirmed_pairs)
        self.assertIs(sig.parameters["coverage_complete"].default, True)
        self.assertEqual(
            mc.unconfirmed_pairs({("1", "w")}, {"g1": ("1", "w")}, {"g1"},
                                 False),
            set(),
        )

    def test_finish_kwargs_carry_uploaded_pair_when_incomplete(self):
        base = dict(
            candidate_pairs={("1", "2026-11-01")},
            groups={"g1": _group("1", "2026-11-01")},
            skip_keys=set(),
            upload_ok={"g1": True},
            deferred_records=[{"group_key": "g1"}],
            upload_tasks=[{"group_key": "g1"}],
            no_target_groups=set(),
            scoped=False,
            debt_unknown=False,
        )
        self.assertEqual(
            orch._regen_debt_finish_kwargs(**base)["regen_debt_pairs"], [],
        )
        self.assertEqual(
            orch._regen_debt_finish_kwargs(
                **base, coverage_complete=False,
            )["regen_debt_pairs"],
            [["1", "2026-11-01"]],
        )

    def test_coverage_complete_rule(self):
        f = orch._regen_debt_coverage_complete
        self.assertTrue(f(False, set(), "both"))
        self.assertFalse(f(True, set(), "both"))
        self.assertFalse(f(False, {123}, "both"))
        self.assertFalse(f(False, set(), "primary"))
        self.assertFalse(f(False, set(), "helper"))
        self.assertFalse(f(False, None, "both"))

    def test_main_tracks_truncation_and_passes_coverage(self):
        src = inspect.getsource(orch.main)
        cut = src.index("Limiting processing to first")
        self.assertIn(
            "_mem_groups_truncated = True", src[cut:cut + 400],
        )
        self.assertIn("_mem_groups_truncated = False", src[:cut])
        self.assertIn("coverage_complete=_regen_debt_coverage_complete(",
                      src)
        self.assertIn("get_last_full_read_failed_sheet_ids()", src)


class LedgerStartConfirmationWriterTests(unittest.TestCase):
    """Issues 2 + 3, writer side: start / note report success, and the
    finish upsert can carry a fallback ``started_at``."""

    def setUp(self):
        from pipeline_memory import client as mem_client
        mem_client.reset_cache_for_tests()
        self._env = mock.patch.dict(os.environ, {
            "RUN_MEMORY_WRITE_ENABLED": "1",
        })
        self._env.start()
        self.addCleanup(self._env.stop)

    def tearDown(self):
        from pipeline_memory import client as mem_client
        mem_client.reset_cache_for_tests()

    def _client(self, upsert_exc=None, update_data=None, update_exc=None):
        client = mock.Mock()
        table = client.schema.return_value.table.return_value
        if upsert_exc is not None:
            table.upsert.return_value.execute.side_effect = upsert_exc
        else:
            table.upsert.return_value.execute.return_value = (
                SimpleNamespace(data=[])
            )
        upd = table.update.return_value.eq.return_value.execute
        if update_exc is not None:
            upd.side_effect = update_exc
        else:
            upd.return_value = SimpleNamespace(data=update_data)
        return client, table

    def test_run_ledger_start_returns_true_on_write(self):
        from pipeline_memory import writer as mem_writer
        client, _t = self._client()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            self.assertIs(
                mem_writer.run_ledger_start("r", mode="full"), True,
            )

    def test_run_ledger_start_returns_false_when_not_written(self):
        from pipeline_memory import writer as mem_writer
        client, _t = self._client(upsert_exc=Exception("boom"))
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            self.assertIs(
                mem_writer.run_ledger_start("r", mode="full"), False,
            )
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=None,
        ):
            self.assertIs(
                mem_writer.run_ledger_start("r", mode="full"), False,
            )

    def test_note_pending_true_only_when_a_row_matched(self):
        from pipeline_memory import writer as mem_writer
        client, _t = self._client(update_data=[{"run_id": "r"}])
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            self.assertIs(
                mem_writer.run_ledger_note_pending("r", [], False), True,
            )
        client, table = self._client(update_data=[])
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            self.assertIs(
                mem_writer.run_ledger_note_pending("ghost", [], False),
                False,
            )
        table.upsert.assert_not_called()
        table.insert.assert_not_called()

    def test_note_pending_false_on_failure_or_no_client(self):
        from pipeline_memory import writer as mem_writer
        client, _t = self._client(update_exc=Exception("boom"))
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            self.assertIs(
                mem_writer.run_ledger_note_pending("r", [], False), False,
            )
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=None,
        ):
            self.assertIs(
                mem_writer.run_ledger_note_pending("r", [], False), False,
            )

    def test_finish_carries_fallback_started_at_as_a_column(self):
        from pipeline_memory import writer as mem_writer
        client, table = self._client()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            mem_writer.run_ledger_finish(
                "r", started_at="2026-11-01T10:00:00+00:00",
                regen_debt_pairs=[["1", "w"]],
            )
        payload = table.upsert.call_args.args[0]
        self.assertEqual(payload["started_at"], "2026-11-01T10:00:00+00:00")
        self.assertNotIn("started_at", payload["notes"])
        self.assertEqual(payload["notes"]["regen_debt_pairs"], [["1", "w"]])

    def test_finish_without_started_at_never_sends_the_column(self):
        from pipeline_memory import writer as mem_writer
        client, table = self._client()
        with mock.patch(
            "pipeline_memory.writer.get_client", return_value=client,
        ):
            mem_writer.run_ledger_finish("r")
            mem_writer.run_ledger_finish("r", started_at=None)
        self.assertEqual(table.upsert.call_count, 2)
        for call in table.upsert.call_args_list:
            payload = call.args[0]
            self.assertNotIn("started_at", payload)
            self.assertNotIn("started_at", payload["notes"])


class LedgerStartConfirmationOrchestrateTests(unittest.TestCase):
    """Issues 2 + 3, orchestrate side."""

    def test_note_helper_returns_the_writer_result(self):
        for ret in (True, False):
            with mock.patch.object(
                orch._mem_writer, "run_ledger_note_pending",
                return_value=ret,
            ):
                self.assertIs(
                    orch._note_pending_regen_pairs("r", {("1", "w")}, False),
                    ret,
                )

    def test_note_helper_false_when_writer_raises(self):
        with mock.patch.object(
            orch._mem_writer, "run_ledger_note_pending",
            side_effect=RuntimeError("x"),
        ):
            self.assertIs(
                orch._note_pending_regen_pairs("r", set(), False), False,
            )

    def test_unconfirmed_ledger_rule(self):
        f = orch._ledger_debt_unconfirmed
        # start not confirmed -> unknown, whatever else happened
        self.assertTrue(f(False, True, True))
        self.assertTrue(f(False, False, False))
        # start ok, note attempted but not confirmed -> unknown
        self.assertTrue(f(True, True, False))
        # start ok and note confirmed / never needed -> trusted
        self.assertFalse(f(True, True, True))
        self.assertFalse(f(True, False, False))

    def test_start_fallback_kwargs(self):
        f = orch._ledger_start_fallback_kwargs
        self.assertEqual(
            f(True, "2026-11-01T10:00:00+00:00"),
            {"run_ledger_start_confirmed": True},
        )
        self.assertEqual(
            f(False, "2026-11-01T10:00:00+00:00"),
            {
                "run_ledger_start_confirmed": False,
                "started_at": "2026-11-01T10:00:00+00:00",
            },
        )
        out = f(False, None)
        self.assertFalse(out["run_ledger_start_confirmed"])
        self.assertTrue(isinstance(out["started_at"], str)
                        and out["started_at"])

    def test_fallback_row_is_newest_and_its_debt_is_carried(self):
        # Start failed; finish wrote a row WITH the fallback started_at, so
        # the reducer sees its failed-upload debt instead of an older
        # clean success row.
        rows = [
            _row(started="2026-11-02T10:00:00+00:00", notes={
                "regen_debt_pairs": [["1", "w"]],
                "regen_debt_unknown": False,
            }),
            _row(started="2026-11-01T10:00:00+00:00", notes={
                "regen_debt_pairs": [],
            }),
        ]
        self.assertEqual(
            mc.regen_debt_from_ledger_rows(rows), {("1", "w")},
        )

    def test_main_wiring(self):
        src = inspect.getsource(orch.main)
        self.assertIn("_mem_ledger_started = False", src)
        self.assertIn("_mem_ledger_noted = False", src)
        self.assertIn(
            "_mem_ledger_started = _mem_writer.run_ledger_start(", src,
        )
        note_i = src.index("_note_pending_regen_pairs(")
        self.assertIn(
            "_mem_ledger_noted = _note_pending_regen_pairs(",
            src[note_i - 60:note_i + 30],
        )
        # A failed start is retried once before the pending note.
        retry_i = src.rindex(
            "_mem_ledger_started = _mem_writer.run_ledger_start(",
        )
        self.assertLess(src.index("PHASE 2: Fetching source data"), retry_i)
        self.assertLess(retry_i, note_i)
        # Both finish sites mark the debt unknown and carry started_at.
        self.assertEqual(src.count("_ledger_debt_unconfirmed("), 2)
        self.assertEqual(src.count("_ledger_start_fallback_kwargs("), 2)



class PR435BotFollowupTests(unittest.TestCase):
    """PR #435 bot-thread follow-ups: inherited unknown debt survives an
    incomplete run, and deep-run deletion pairs join the carried debt."""

    def _kw(self, **over):
        base = dict(
            candidate_pairs={("1", "2026-11-01")},
            groups={"g1": _group("1", "2026-11-01")},
            skip_keys={"g1"},
            upload_ok={},
            deferred_records=[],
            upload_tasks=[],
            no_target_groups=set(),
            scoped=False,
            debt_unknown=False,
        )
        base.update(over)
        return orch._regen_debt_finish_kwargs(**base)

    def test_inherited_unknown_with_incomplete_coverage_stays_unknown(self):
        out = self._kw(inherited_unknown=True, coverage_complete=False)
        self.assertTrue(out["regen_debt_unknown"])

    def test_inherited_unknown_with_complete_coverage_becomes_known(self):
        out = self._kw(inherited_unknown=True, coverage_complete=True)
        self.assertFalse(out["regen_debt_unknown"])

    def test_known_debt_with_incomplete_coverage_stays_known(self):
        out = self._kw(inherited_unknown=False, coverage_complete=False)
        self.assertFalse(out["regen_debt_unknown"])

    def test_reconcile_pair_with_failed_upload_is_carried(self):
        out = self._kw(
            candidate_pairs={("1", "2026-11-01"), ("2", "2026-11-08")},
            groups={
                "g1": _group("1", "2026-11-01"),
                "g2": _group("2", "2026-11-08"),
            },
            skip_keys={"g1"},
            upload_ok={"g2": False},
        )
        self.assertEqual(
            [tuple(p) for p in out["regen_debt_pairs"]],
            [("2", "2026-11-08")],
        )

    def test_failed_upload_outside_candidate_is_carried(self):
        """PR #435 (Codex P2): an attachment-repair group outside the
        candidate set whose upload failed stays debt even when the
        inherited debt was known."""
        out = self._kw(
            candidate_pairs=set(),
            groups={"g9": _group("9", "2026-11-08")},
            skip_keys=set(),
            upload_tasks=[{"group_key": "g9"}],
            upload_ok={"g9": False},
        )
        self.assertEqual(
            [tuple(p) for p in out["regen_debt_pairs"]],
            [("9", "2026-11-08")],
        )
        self.assertFalse(out["regen_debt_unknown"])

    def test_successful_upload_outside_candidate_is_not_carried(self):
        out = self._kw(
            candidate_pairs=set(),
            groups={"g9": _group("9", "2026-11-08")},
            skip_keys=set(),
            upload_tasks=[{"group_key": "g9"}],
            upload_ok={"g9": True},
        )
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_generation_error_outside_candidate_is_carried(self):
        """Codex P2 follow-up: a group outside the candidate set that
        failed in generation has no upload task and no skip; it is still
        owed a regeneration."""
        out = self._kw(
            candidate_pairs=set(),
            groups={"g9": _group("9", "2026-11-08")},
            skip_keys=set(),
        )
        self.assertEqual(
            [tuple(p) for p in out["regen_debt_pairs"]],
            [("9", "2026-11-08")],
        )
        self.assertFalse(out["regen_debt_unknown"])

    def test_group_never_reached_is_carried_unchanged_is_not(self):
        out = self._kw(
            candidate_pairs=set(),
            groups={
                "reached": _group("1", "2026-11-01"),
                "unreached": _group("2", "2026-11-08"),
            },
            skip_keys={"reached"},
        )
        self.assertEqual(
            [tuple(p) for p in out["regen_debt_pairs"]],
            [("2", "2026-11-08")],
        )

    def test_quarantined_group_is_not_carried(self):
        out = self._kw(
            candidate_pairs=set(),
            groups={"q": _group("7", "2026-11-08")},
            skip_keys=set(),
            excluded_groups={"q"},
        )
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_quarantined_candidate_pair_is_not_carried(self):
        # PR #439 (Copilot): a quarantined group already in the candidate
        # set must clear too, not only one outside it.
        out = self._kw(
            candidate_pairs={("7", "2026-11-08")},
            groups={"q": _group("7", "2026-11-08")},
            skip_keys=set(),
            excluded_groups={"q"},
        )
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_quarantined_group_with_inherited_unknown_is_not_carried(self):
        out = self._kw(
            candidate_pairs=set(),
            groups={"q": _group("7", "2026-11-08")},
            skip_keys=set(),
            excluded_groups={"q"},
            inherited_unknown=True,
        )
        self.assertEqual(out["regen_debt_pairs"], [])

    def test_unconfirmed_sibling_of_quarantined_group_is_carried(self):
        out = self._kw(
            candidate_pairs={("7", "2026-11-08")},
            groups={
                "q": _group("7", "2026-11-08"),
                "sibling": _group("7", "2026-11-08"),
            },
            skip_keys=set(),
            excluded_groups={"q"},
        )
        self.assertEqual(
            [tuple(p) for p in out["regen_debt_pairs"]],
            [("7", "2026-11-08")],
        )

    def test_quarantined_candidate_stays_carried_on_partial_coverage(self):
        out = self._kw(
            candidate_pairs={("7", "2026-11-08")},
            groups={"q": _group("7", "2026-11-08")},
            skip_keys=set(),
            excluded_groups={"q"},
            coverage_complete=False,
        )
        self.assertEqual(
            [tuple(p) for p in out["regen_debt_pairs"]],
            [("7", "2026-11-08")],
        )

    def test_quarantined_group_keys_covers_every_matching_group(self):
        # PR #439 (Greptile): no dependence on the main loop reaching a
        # group, so one past the time-budget break is still listed.
        groups = {
            "a": [{"Work Request #": "1/2"}],
            "b": [{"Work Request #": "1:2.0"}],
            "ok": [{"Work Request #": "99"}],
            "blank": [{"Work Request #": ""}],
            "empty": [],
        }
        self.assertEqual(
            orch._quarantined_group_keys(groups, {"1_2"}), {"a", "b"},
        )

    def test_main_records_quarantined_groups_before_the_loop(self):
        src = inspect.getsource(orch.main)
        self.assertNotIn("_mem_quarantined_group_keys.add(", src)
        recorded = src.index(
            "_mem_quarantined_group_keys.update(_quarantined_group_keys("
        )
        loop = src.index("for group_idx, (group_key, group_rows)")
        self.assertLess(recorded, loop)
        self.assertIn(
            "excluded_groups=_mem_quarantined_group_keys", src,
        )

    def test_both_finish_sites_union_reconcile_pairs(self):
        # Two finish sites plus the post-reconciliation pending note.
        src = inspect.getsource(orch.main)
        self.assertEqual(
            src.count("_mem_candidate_pairs | _reconcile_affected_pairs"), 3,
        )

if __name__ == "__main__":
    unittest.main()
