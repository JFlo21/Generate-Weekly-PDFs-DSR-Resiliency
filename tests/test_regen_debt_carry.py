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


if __name__ == "__main__":
    unittest.main()
