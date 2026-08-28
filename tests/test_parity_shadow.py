"""Shadow-incremental parity proof tests (Phase 11 Plan 05, INC-04).

CONTEXT.md D-07/D-08: while ``RUN_MEMORY_INCREMENTAL_ENABLED`` is OFF and
``RUN_MEMORY_WRITE_ENABLED`` is ON, every ``production_frequent`` run keeps
its full read and additionally computes what the incremental path *would*
have regenerated from this run's own affected set, then compares it
against what the full path *actually* regenerated (group-key set equality
plus per-group hash equality -- ``CompareShadowParityTests`` /
``CombineVerdictsTests``), and separately issues the real D-01 delta reads
so the watermark + escalation logic is exercised end-to-end before the
flag flips, asserting every row whose content hash changed this run
appears in the delta read's row set (``ShadowDeltaReadTests``).

Discipline pinned throughout (mirrors ``scripts/compare_control_run.py``
and ``tests/test_pipeline_memory_shadow.py``): a verdict of ``pass``
requires proof the comparison actually executed. A comparison that could
not execute -- zero groups, zero sheets probed, insufficient budget, an
unexpected exception -- reports ``skipped`` with a reason and NEVER
``pass``. Every function under test here computes and compares only; none
of them may call (or need to call) ``generate_excel`` / the upload path /
the cleanup path / ``upsert_sheet_registry`` -- pinned directly below.
"""

from __future__ import annotations

import datetime
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import parity  # noqa: E402


def _source(sheet_id):
    return {"id": sheet_id, "name": f"sheet-{sheet_id}", "column_mapping": {}}


class _FakeRow:
    def __init__(self, row_id):
        self.id = row_id


class _FakeSheet:
    def __init__(self, row_ids):
        self.rows = [_FakeRow(rid) for rid in row_ids]


# ── Task 2 (D-07): group-key set + per-group hash equality ────────────────

class CompareShadowParityTests(unittest.TestCase):
    """`compare_shadow_parity` -- the group-side two-sided verdict."""

    def test_equal_sets_equal_hashes_yields_pass(self):
        candidate = {"g1": "hashA", "g2": "hashB"}
        actual = {"g1": "hashA", "g2": "hashB"}
        result = parity.compare_shadow_parity(candidate, actual)
        self.assertEqual(result["verdict"], "pass")
        self.assertGreater(result["groups_compared"], 0)

    def test_reordered_members_still_yield_pass(self):
        # dict insertion order differs; set-based comparison must be
        # order-independent (CONTEXT.md D-07 / plan behavior list).
        candidate = {"g2": "hashB", "g1": "hashA"}
        actual = {"g1": "hashA", "g2": "hashB"}
        result = parity.compare_shadow_parity(candidate, actual)
        self.assertEqual(result["verdict"], "pass")

    def test_intersecting_but_unequal_sets_yield_fail_with_divergences(self):
        candidate = {"g1": "hashA", "g2": "hashB"}
        actual = {"g1": "hashA", "g3": "hashC"}
        result = parity.compare_shadow_parity(candidate, actual)
        self.assertEqual(result["verdict"], "fail")
        self.assertIn("g2", result["only_in_candidate"])
        self.assertIn("g3", result["only_in_actual"])

    def test_candidate_superset_yields_pass_and_records_candidate_only(self):
        # D-07 refinement #2 (run #2802, 33113384941.1): the D-04 candidate
        # is every group of an affected (WR, week) pair; the unmodified
        # hash-skip gate then skips the unchanged ones exactly as the full
        # run did. A candidate-only group is informational, not a divergence.
        candidate = {"083026_13242113_USER_John_Bishop": "hA",
                     "083026_13242113_HELPER_Walker_David_Moody": "hB"}
        actual = {"083026_13242113_USER_John_Bishop": "hA"}
        result = parity.compare_shadow_parity(candidate, actual)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["groups_compared"], 1)
        self.assertEqual(result["only_in_candidate"],
                         ["083026_13242113_HELPER_Walker_David_Moody"])
        self.assertEqual(result["only_in_actual"], [])

    def test_actual_not_in_candidate_is_the_real_divergence(self):
        candidate = {"g1": "hA"}
        actual = {"g1": "hA", "g9": "hZ"}
        result = parity.compare_shadow_parity(candidate, actual)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(result["reason"], "actual_not_in_candidate")
        self.assertEqual(result["only_in_actual"], ["g9"])

    def test_candidate_only_with_nothing_regenerated_is_skipped_not_pass(self):
        result = parity.compare_shadow_parity({"g2": "hB"}, {})
        self.assertEqual(result["verdict"], "skipped")
        self.assertEqual(result["groups_compared"], 0)

    def test_equal_sets_hash_mismatch_yields_fail(self):
        candidate = {"g1": "hashA"}
        actual = {"g1": "hashDIFFERENT"}
        result = parity.compare_shadow_parity(candidate, actual)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(len(result["hash_mismatches"]), 1)
        entry = result["hash_mismatches"][0]
        self.assertEqual(entry["group_key"], "g1")
        self.assertEqual(entry["candidate_hash"], "hashA")
        self.assertEqual(entry["actual_hash"], "hashDIFFERENT")

    def test_zero_groups_both_empty_yields_skipped_never_pass(self):
        result = parity.compare_shadow_parity({}, {})
        self.assertEqual(result["verdict"], "skipped")
        self.assertEqual(result["groups_compared"], 0)
        self.assertNotEqual(result["verdict"], "pass")
        self.assertTrue(result["reason"])

    def test_candidate_empty_actual_nonempty_yields_fail_not_skipped(self):
        # Zero groups is only "skipped" when BOTH sides are empty -- one
        # side non-empty is a real divergence (the full path regenerated
        # something the affected-set filter did not select).
        result = parity.compare_shadow_parity({}, {"g1": "h"})
        self.assertEqual(result["verdict"], "fail")

    def test_none_inputs_yield_skipped_never_pass(self):
        result = parity.compare_shadow_parity(None, {"g1": "h"})
        self.assertEqual(result["verdict"], "skipped")

    def test_never_raises_on_unexpected_input_shape(self):
        class Weird:
            def keys(self):
                raise RuntimeError("boom")

        try:
            result = parity.compare_shadow_parity(Weird(), {})
        except Exception as exc:  # pragma: no cover - defensive
            self.fail(f"compare_shadow_parity raised: {exc!r}")
        self.assertEqual(result["verdict"], "skipped")

    def test_fail_verdict_never_touches_generation_upload_cleanup(self):
        """T-11-26: the comparator computes and compares only."""
        with mock.patch("pipeline.excel.generate_excel") as gen_mock, \
                mock.patch(
                    "pipeline.upload.create_target_sheet_map"
                ) as up_mock, \
                mock.patch(
                    "pipeline.cleanup.cleanup_stale_excels"
                ) as cleanup_mock, \
                mock.patch(
                    "pipeline_memory.writer.upsert_sheet_registry"
                ) as reg_mock:
            candidate = {"g1": "hashA"}
            actual = {"g1": "hashDIFFERENT"}
            result = parity.compare_shadow_parity(candidate, actual)
            self.assertEqual(result["verdict"], "fail")
            gen_mock.assert_not_called()
            up_mock.assert_not_called()
            cleanup_mock.assert_not_called()
            reg_mock.assert_not_called()

    def test_elapsed_seconds_present_and_non_negative(self):
        result = parity.compare_shadow_parity({"g1": "h"}, {"g1": "h"})
        self.assertIn("elapsed_seconds", result)
        self.assertGreaterEqual(result["elapsed_seconds"], 0)


class CombineVerdictsTests(unittest.TestCase):
    """`combine_verdicts` -- folds the group-side and read-side verdicts
    into the single overall `parity_verdict` persisted to `run_ledger.notes`.
    """

    def test_pass_and_pass_is_pass(self):
        self.assertEqual(parity.combine_verdicts("pass", "pass"), "pass")

    def test_fail_dominates_pass(self):
        self.assertEqual(parity.combine_verdicts("fail", "pass"), "fail")
        self.assertEqual(parity.combine_verdicts("pass", "fail"), "fail")

    def test_skipped_with_pass_is_skipped(self):
        self.assertEqual(parity.combine_verdicts("skipped", "pass"), "skipped")
        self.assertEqual(parity.combine_verdicts("pass", "skipped"), "skipped")

    def test_fail_beats_skipped(self):
        self.assertEqual(parity.combine_verdicts("fail", "skipped"), "fail")
        self.assertEqual(parity.combine_verdicts("skipped", "fail"), "fail")


class GoldenContractTests(unittest.TestCase):
    """Plan-level guardrail: this plan touches no frozen contract."""

    def test_run_summary_baseline_key_count(self):
        import json

        baseline_path = _REPO_ROOT / "tests" / "golden" / "run_summary_baseline.json"
        with open(baseline_path, encoding="utf-8") as fh:
            baseline = json.load(fh)
        self.assertEqual(len(baseline), 22)  # 21 + PR #365's counter


# ── Task 3 (D-08): shadow delta reads + the read-side assertion ───────────

class ShadowDeltaReadTests(unittest.TestCase):
    """`run_shadow_delta_reads` -- sub-budgeted D-01 delta probes plus the
    read-side assertion (every row whose content hash changed this run
    must appear in the delta read's row set).
    """

    def test_changed_row_absent_from_delta_read_is_read_side_fail(self):
        sources = [_source(1)]
        watermarks = {
            1: {
                "last_sheet_version": 5,
                "last_read_at": "2026-08-01T00:00:00+00:00",
            }
        }
        changed = {1: {100, 200}}

        def fake_fetch(client, source, last_version, rows_modified_since):
            return {
                "escalate": False, "sheet": _FakeSheet([100]),
                "version": 6, "calls": 2,
            }

        result = parity.run_shadow_delta_reads(
            client=object(), source_sheets=sources, watermarks=watermarks,
            changed_row_ids_by_sheet=changed,
            session_start=datetime.datetime.now(),
            fetch_sheet_delta_fn=fake_fetch,
            compute_rows_modified_since_fn=lambda *a, **k: "x",
            safety_window_minutes=15, max_minutes=10, rpc_timeout_sec=45,
            generation_headroom_min=2, time_budget_minutes=0,
            github_actions_mode=False, parallel_workers=2,
        )
        self.assertEqual(result["read_verdict"], "fail")
        self.assertEqual(len(result["read_mismatches"]), 1)
        self.assertEqual(
            result["read_mismatches"][0], {"sheet_id": 1, "row_id": 200},
        )

    def test_all_changed_rows_present_yields_pass(self):
        sources = [_source(1), _source(2)]
        watermarks = {
            1: {
                "last_sheet_version": 5,
                "last_read_at": "2026-08-01T00:00:00+00:00",
            },
            2: {"last_sheet_version": 3, "last_read_at": None},
        }
        changed = {1: {100}, 2: set()}

        def fake_fetch(client, source, last_version, rows_modified_since):
            if source["id"] == 1:
                return {
                    "escalate": False, "sheet": _FakeSheet([100, 101]),
                    "version": 6, "calls": 2,
                }
            return {
                "escalate": False, "sheet": None, "version": 3, "calls": 1,
            }

        result = parity.run_shadow_delta_reads(
            client=object(), source_sheets=sources, watermarks=watermarks,
            changed_row_ids_by_sheet=changed,
            session_start=datetime.datetime.now(),
            fetch_sheet_delta_fn=fake_fetch,
            compute_rows_modified_since_fn=lambda last, win: "computed",
            safety_window_minutes=15, max_minutes=10, rpc_timeout_sec=45,
            generation_headroom_min=2, time_budget_minutes=0,
            github_actions_mode=False, parallel_workers=2,
        )
        self.assertEqual(result["read_verdict"], "pass")
        self.assertEqual(result["sheets_probed"], 2)
        self.assertEqual(result["sheets_abandoned"], 0)

    def test_per_call_timeout_marks_sheet_not_compared(self):
        sources = [_source(1), _source(2)]
        changed = {1: {100}, 2: {200}}

        def fake_fetch(client, source, last_version, rows_modified_since):
            if source["id"] == 1:
                time.sleep(0.3)
                return {
                    "escalate": False, "sheet": _FakeSheet([100]),
                    "version": 1, "calls": 2,
                }
            return {
                "escalate": False, "sheet": _FakeSheet([200]),
                "version": 1, "calls": 2,
            }

        result = parity.run_shadow_delta_reads(
            client=object(), source_sheets=sources, watermarks={},
            changed_row_ids_by_sheet=changed,
            session_start=datetime.datetime.now(),
            fetch_sheet_delta_fn=fake_fetch,
            compute_rows_modified_since_fn=lambda *a, **k: None,
            safety_window_minutes=15, max_minutes=10, rpc_timeout_sec=0.05,
            generation_headroom_min=2, time_budget_minutes=0,
            github_actions_mode=False, parallel_workers=2,
        )
        # Sheet 1's stuck call is abandoned -- NOT reported as "compared
        # and clean": its changed row (100) must not surface as either a
        # pass contributor or a mismatch, because we never actually looked.
        self.assertEqual(result["sheets_abandoned"], 1)
        self.assertEqual(result["sheets_probed"], 1)
        mismatched_sheet_ids = {m["sheet_id"] for m in result["read_mismatches"]}
        self.assertNotIn(1, mismatched_sheet_ids)

    def test_never_calls_registry_write(self):
        with mock.patch(
            "pipeline_memory.writer.upsert_sheet_registry"
        ) as reg_mock:
            def fake_fetch(client, source, last_version, rows_modified_since):
                return {
                    "escalate": False, "sheet": None, "version": 1,
                    "calls": 1,
                }

            parity.run_shadow_delta_reads(
                client=object(), source_sheets=[_source(1)], watermarks={},
                changed_row_ids_by_sheet={},
                session_start=datetime.datetime.now(),
                fetch_sheet_delta_fn=fake_fetch,
                compute_rows_modified_since_fn=lambda *a, **k: None,
                safety_window_minutes=15, max_minutes=10,
                rpc_timeout_sec=45, generation_headroom_min=2,
                time_budget_minutes=0, github_actions_mode=False,
                parallel_workers=2,
            )
            reg_mock.assert_not_called()

    def test_insufficient_budget_yields_skipped_and_zero_probe_calls(self):
        calls = []

        def fake_fetch(client, source, last_version, rows_modified_since):
            calls.append(source)
            return {
                "escalate": False, "sheet": None, "version": 1, "calls": 1,
            }

        session_start = (
            datetime.datetime.now() - datetime.timedelta(minutes=160)
        )
        result = parity.run_shadow_delta_reads(
            client=object(), source_sheets=[_source(1)], watermarks={},
            changed_row_ids_by_sheet={}, session_start=session_start,
            fetch_sheet_delta_fn=fake_fetch,
            compute_rows_modified_since_fn=lambda *a, **k: None,
            safety_window_minutes=15, max_minutes=10, rpc_timeout_sec=45,
            generation_headroom_min=2, time_budget_minutes=165,
            github_actions_mode=True, parallel_workers=2,
        )
        self.assertEqual(result["read_verdict"], "skipped")
        self.assertEqual(calls, [])
        self.assertEqual(result["sheets_probed"], 0)

    def test_no_source_sheets_yields_skipped(self):
        result = parity.run_shadow_delta_reads(
            client=object(), source_sheets=[], watermarks={},
            changed_row_ids_by_sheet={},
            session_start=datetime.datetime.now(),
            fetch_sheet_delta_fn=lambda *a, **k: {},
            compute_rows_modified_since_fn=lambda *a, **k: None,
            safety_window_minutes=15, max_minutes=10, rpc_timeout_sec=45,
            generation_headroom_min=2, time_budget_minutes=0,
            github_actions_mode=False, parallel_workers=2,
        )
        self.assertEqual(result["read_verdict"], "skipped")

    def test_escalation_marks_sheet_abandoned_and_never_pass(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            return {"escalate": True, "reason": "abbreviated with no version"}

        result = parity.run_shadow_delta_reads(
            client=object(), source_sheets=[_source(1)], watermarks={},
            changed_row_ids_by_sheet={1: {100}},
            session_start=datetime.datetime.now(),
            fetch_sheet_delta_fn=fake_fetch,
            compute_rows_modified_since_fn=lambda *a, **k: None,
            safety_window_minutes=15, max_minutes=10, rpc_timeout_sec=45,
            generation_headroom_min=2, time_budget_minutes=0,
            github_actions_mode=False, parallel_workers=2,
        )
        self.assertEqual(result["sheets_abandoned"], 1)
        self.assertEqual(result["sheets_probed"], 0)
        self.assertNotEqual(result["read_verdict"], "pass")

    def test_exception_in_probe_marks_sheet_abandoned_never_raises(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            raise RuntimeError("network blew up")

        try:
            result = parity.run_shadow_delta_reads(
                client=object(),
                source_sheets=[_source(1), _source(2)], watermarks={},
                changed_row_ids_by_sheet={},
                session_start=datetime.datetime.now(),
                fetch_sheet_delta_fn=fake_fetch,
                compute_rows_modified_since_fn=lambda *a, **k: None,
                safety_window_minutes=15, max_minutes=10,
                rpc_timeout_sec=45, generation_headroom_min=2,
                time_budget_minutes=0, github_actions_mode=False,
                parallel_workers=2,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.fail(f"run_shadow_delta_reads raised: {exc!r}")
        self.assertEqual(result["sheets_abandoned"], 2)
        self.assertNotEqual(result["read_verdict"], "pass")

    def test_never_raises_on_malformed_watermarks(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            raise AssertionError("should not be reached")

        try:
            result = parity.run_shadow_delta_reads(
                client=object(), source_sheets=[_source(1)],
                watermarks=None, changed_row_ids_by_sheet=None,
                session_start=datetime.datetime.now(),
                fetch_sheet_delta_fn=fake_fetch,
                compute_rows_modified_since_fn=lambda *a, **k: None,
                safety_window_minutes=15, max_minutes=10,
                rpc_timeout_sec=45, generation_headroom_min=2,
                time_budget_minutes=0, github_actions_mode=False,
                parallel_workers=2,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.fail(f"run_shadow_delta_reads raised: {exc!r}")
        self.assertIn(result["read_verdict"], ("skipped", "fail"))

    def test_parallel_workers_cap_respected(self):
        import concurrent.futures as cf

        captured = {}
        real_cls = cf.ThreadPoolExecutor

        class _Spy(real_cls):
            def __init__(self, max_workers=None, *a, **k):
                captured["max_workers"] = max_workers
                super().__init__(max_workers=max_workers, *a, **k)

        def fake_fetch(client, source, last_version, rows_modified_since):
            return {
                "escalate": False, "sheet": None, "version": 1, "calls": 1,
            }

        with mock.patch("pipeline.parity._DaemonThreadPoolExecutor", _Spy):
            parity.run_shadow_delta_reads(
                client=object(), source_sheets=[_source(1)], watermarks={},
                changed_row_ids_by_sheet={},
                session_start=datetime.datetime.now(),
                fetch_sheet_delta_fn=fake_fetch,
                compute_rows_modified_since_fn=lambda *a, **k: None,
                safety_window_minutes=15, max_minutes=10,
                rpc_timeout_sec=45, generation_headroom_min=2,
                time_budget_minutes=0, github_actions_mode=False,
                parallel_workers=3,
            )
        self.assertEqual(captured["max_workers"], 3)

    def test_never_touches_generation_upload_cleanup(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            return {
                "escalate": False, "sheet": _FakeSheet([1]),
                "version": 1, "calls": 2,
            }

        with mock.patch("pipeline.excel.generate_excel") as gen_mock, \
                mock.patch(
                    "pipeline.upload.create_target_sheet_map"
                ) as up_mock, \
                mock.patch(
                    "pipeline.cleanup.cleanup_stale_excels"
                ) as cleanup_mock:
            parity.run_shadow_delta_reads(
                client=object(), source_sheets=[_source(1)], watermarks={},
                changed_row_ids_by_sheet={1: {999}},
                session_start=datetime.datetime.now(),
                fetch_sheet_delta_fn=fake_fetch,
                compute_rows_modified_since_fn=lambda *a, **k: None,
                safety_window_minutes=15, max_minutes=10,
                rpc_timeout_sec=45, generation_headroom_min=2,
                time_budget_minutes=0, github_actions_mode=False,
                parallel_workers=2,
            )
            gen_mock.assert_not_called()
            up_mock.assert_not_called()
            cleanup_mock.assert_not_called()


class GetChangedRowIdsBySheetTests(unittest.TestCase):
    """`get_changed_row_ids_by_sheet` -- best-effort `row_event` read that
    supplies the read-side assertion's "what changed this run" input.
    Never raises. Greptile P1 (PR #353): a failed lookup returns ``None``
    ("cannot confirm") and is DISTINCT from a successful lookup that
    found zero changed rows (``{}``) -- the two used to collapse into
    the same empty dict and let the read side report a vacuous ``pass``.
    """

    def test_no_client_returns_none_not_empty_dict(self):
        with mock.patch(
            "pipeline_memory.client.get_client", return_value=None,
        ):
            result = parity.get_changed_row_ids_by_sheet("run-1")
        self.assertIsNone(result)

    def test_successful_empty_payload_returns_empty_dict(self):
        fake_client = mock.Mock()
        fake_result = mock.Mock()
        fake_result.data = []
        with mock.patch(
            "pipeline_memory.client.get_client", return_value=fake_client,
        ), mock.patch(
            "pipeline_memory.client.with_retry", return_value=fake_result,
        ):
            result = parity.get_changed_row_ids_by_sheet("run-1")
        self.assertEqual(result, {})

    def test_groups_rows_by_sheet_id(self):
        fake_client = mock.Mock()
        fake_result = mock.Mock()
        fake_result.data = [
            {"sheet_id": 1, "row_id": 100},
            {"sheet_id": 1, "row_id": 101},
            {"sheet_id": 2, "row_id": 200},
        ]
        with mock.patch(
            "pipeline_memory.client.get_client", return_value=fake_client,
        ), mock.patch(
            "pipeline_memory.client.with_retry", return_value=fake_result,
        ):
            result = parity.get_changed_row_ids_by_sheet("run-1")
        self.assertEqual(result, {1: {100, 101}, 2: {200}})

    def test_none_result_returns_none_not_empty_dict(self):
        fake_client = mock.Mock()
        with mock.patch(
            "pipeline_memory.client.get_client", return_value=fake_client,
        ), mock.patch(
            "pipeline_memory.client.with_retry", return_value=None,
        ):
            result = parity.get_changed_row_ids_by_sheet("run-1")
        self.assertIsNone(result)

    def test_none_payload_returns_none_not_empty_dict(self):
        fake_client = mock.Mock()
        fake_result = mock.Mock()
        fake_result.data = None
        with mock.patch(
            "pipeline_memory.client.get_client", return_value=fake_client,
        ), mock.patch(
            "pipeline_memory.client.with_retry", return_value=fake_result,
        ):
            result = parity.get_changed_row_ids_by_sheet("run-1")
        self.assertIsNone(result)

    def test_failure_returns_none_never_raises(self):
        with mock.patch(
            "pipeline_memory.client.get_client",
            side_effect=RuntimeError("boom"),
        ):
            try:
                result = parity.get_changed_row_ids_by_sheet("run-1")
            except Exception as exc:  # pragma: no cover - defensive
                self.fail(f"get_changed_row_ids_by_sheet raised: {exc!r}")
        self.assertIsNone(result)


class ReadSideEvidenceTests(unittest.TestCase):
    """Greptile P1 on PR #353 (``pipeline/parity.py`` read verdict): a
    read-side ``pass`` must be backed by evidence. Empty evidence -- a
    failed ``row_event`` lookup (``None``), a lookup that found nothing
    to assert (``{}``), or a changed sheet the probe never reached --
    can never count toward the five-run streak as ``pass``.
    """

    _KW = dict(
        session_start=None,
        compute_rows_modified_since_fn=lambda *a, **k: "x",
        safety_window_minutes=15, max_minutes=10, rpc_timeout_sec=45,
        generation_headroom_min=2, time_budget_minutes=0,
        github_actions_mode=False, parallel_workers=2,
    )

    def _run(self, changed, fetch_fn, sources, watermarks=None):
        kw = dict(self._KW)
        kw["session_start"] = datetime.datetime.now()
        return parity.run_shadow_delta_reads(
            client=object(), source_sheets=sources,
            watermarks=watermarks or {
                s["id"]: {
                    "last_sheet_version": 5,
                    "last_read_at": "2026-08-01T00:00:00+00:00",
                }
                for s in sources
            },
            changed_row_ids_by_sheet=changed,
            fetch_sheet_delta_fn=fetch_fn,
            **kw,
        )

    def test_none_evidence_is_skipped_lookup_failed_with_zero_probes(self):
        fetch = mock.Mock()

        result = self._run(None, fetch, [_source(1)])

        self.assertEqual(result["read_verdict"], "skipped")
        self.assertTrue(result["reason"].startswith("row_event_lookup_failed"))
        fetch.assert_not_called()
        self.assertEqual(result["rows_asserted"], 0)

    def test_empty_evidence_is_skipped_never_pass_but_probes_still_run(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            return {
                "escalate": False, "sheet": None, "version": 6, "calls": 1,
            }

        result = self._run({}, fake_fetch, [_source(1)])

        self.assertEqual(result["read_verdict"], "skipped")
        self.assertTrue(
            result["reason"].startswith("zero_changed_rows_to_assert"),
        )
        self.assertEqual(result["sheets_probed"], 1)  # watermark exercised
        self.assertEqual(result["rows_asserted"], 0)

    def test_all_empty_change_sets_is_skipped_never_pass(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            return {
                "escalate": False, "sheet": None, "version": 6, "calls": 1,
            }

        result = self._run({1: set(), 2: set()}, fake_fetch,
                           [_source(1), _source(2)])

        self.assertEqual(result["read_verdict"], "skipped")
        self.assertEqual(result["rows_asserted"], 0)

    def test_changed_sheet_never_probed_is_skipped_not_pass(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            if source["id"] == 2:
                return {"escalate": True, "reason": "abbreviated"}
            return {
                "escalate": False, "sheet": _FakeSheet([100]),
                "version": 6, "calls": 2,
            }

        result = self._run({1: {100}, 2: {200}}, fake_fetch,
                           [_source(1), _source(2)])

        self.assertEqual(result["read_verdict"], "skipped")
        self.assertTrue(
            result["reason"].startswith("changed_sheet_not_probed"),
        )
        self.assertEqual(result["changed_sheets_unprobed"], 1)
        self.assertEqual(result["rows_asserted"], 1)

    def test_mismatch_on_probed_sheet_fails_even_when_another_unprobed(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            if source["id"] == 2:
                return {"escalate": True, "reason": "abbreviated"}
            return {
                "escalate": False, "sheet": _FakeSheet([100]),
                "version": 6, "calls": 2,
            }

        result = self._run({1: {100, 200}, 2: {300}}, fake_fetch,
                           [_source(1), _source(2)])

        self.assertEqual(result["read_verdict"], "fail")
        self.assertEqual(
            result["read_mismatches"], [{"sheet_id": 1, "row_id": 200}],
        )

    def test_pass_requires_and_reports_asserted_rows(self):
        def fake_fetch(client, source, last_version, rows_modified_since):
            return {
                "escalate": False, "sheet": _FakeSheet([100, 101, 102]),
                "version": 6, "calls": 2,
            }

        result = self._run({1: {100, 101}}, fake_fetch, [_source(1)])

        self.assertEqual(result["read_verdict"], "pass")
        self.assertEqual(result["rows_asserted"], 2)
        self.assertEqual(result["changed_sheets_unprobed"], 0)

    def test_skipped_result_carries_evidence_counters(self):
        result = self._run({1: {100}}, mock.Mock(), [])
        self.assertEqual(result["read_verdict"], "skipped")
        self.assertIn("rows_asserted", result)
        self.assertIn("changed_sheets_unprobed", result)


if __name__ == "__main__":
    unittest.main()
