"""Phase 11 Plan 13 (G-11-37, owner decision 2026-10-29): the shadow models
the D-02 whole-run fallbacks the real incremental path would take.

A shadow verdict is only evidence for INC-04 when the incremental path
would actually have executed incrementally. When it would have fallen back
to a FULL run (D-02 triggers 4/5/6) or when an input of the group hash that
no row delta can see changed (EXTENDED_CHANGE_DETECTION, RATE_CUTOFF_DATE,
the contract / subcontractor rates fingerprints), the comparison is
``skipped`` with ``would_fallback_full:<reason>`` -- never ``pass``, never
``fail`` (D-07 / D-08). Trigger 7 (execution type) is NOT modelled, so
``manual`` runs with ``streak_eligible`` true keep counting (Q2).

Class layout:
  - SkipReasonTests / GlobalsFingerprintTests / PriorGlobalsTests -- pure
    functions in ``pipeline.memory_candidate``.
  - ShadowFallbackSkipTests -- ``pipeline.orchestrate._shadow_fallback_skip``
    through the REAL ``resolve_run_mode``.
  - MainWiringTests -- source pins for the main() wiring.
  - StreakQ2PinTests -- unchanged reader behaviour for manual passes.

Self-contained; no live Supabase / Smartsheet call.
"""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import memory_candidate as mc  # noqa: E402
import pipeline.orchestrate as orch  # noqa: E402

_CLEAN = {"status": "success", "finished_at": "2026-10-29T10:00:00+00:00"}


def _source(sheet_id=101):
    return {"id": sheet_id, "name": "S", "column_mapping": {"WR": 1}}


def _watermarks(sheet_id=101):
    return {
        sheet_id: {
            "sheet_id": sheet_id,
            "last_sheet_version": 8,
            "last_read_at": "2026-10-29T09:00:00+00:00",
            "last_full_read_at": "2026-10-28T09:00:00+00:00",
            "column_mapping": {"WR": 1},
        }
    }


def _ledger_row(fp, status="success"):
    notes = {} if fp is None else {"group_hash_globals_fp": fp}
    return {
        "run_id": "r", "started_at": "2026-10-29T10:00:00+00:00",
        "finished_at": "2026-10-29T10:30:00+00:00",
        "status": status, "notes": notes,
    }


class SkipReasonTests(unittest.TestCase):
    def test_trigger6_modelled(self):
        self.assertEqual(
            mc.shadow_fallback_skip_reason(
                "full", "trigger6_previous_run_not_clean: x", True,
            ),
            "would_fallback_full:trigger6",
        )

    def test_trigger6_not_modelled_when_policy_off(self):
        self.assertIsNone(
            mc.shadow_fallback_skip_reason(
                "full", "trigger6_previous_run_not_clean: x", False,
            )
        )

    def test_policy_constant_matches_owner_decision(self):
        self.assertIs(mc.SHADOW_MODELS_TRIGGER6, True)

    def test_trigger4_and_5_always_modelled(self):
        for reason, label in (
            ("trigger4_empty_watermark_map: x", "trigger4"),
            ("trigger5_operator_flag: REGEN_WEEKS set", "trigger5"),
        ):
            for model6 in (True, False):
                self.assertEqual(
                    mc.shadow_fallback_skip_reason("full", reason, model6),
                    f"would_fallback_full:{label}",
                )

    def test_incremental_is_not_a_fallback(self):
        self.assertIsNone(
            mc.shadow_fallback_skip_reason("incremental", None, True)
        )

    def test_trigger7_never_modelled(self):
        self.assertIsNone(
            mc.shadow_fallback_skip_reason(
                "full", "trigger7_execution_type: EXECUTION_TYPE='manual'",
                True,
            )
        )

    def test_flag_off_and_unknown_reasons_not_modelled(self):
        for reason in ("flag_off: x", "trigger_resolve_exception", None, ""):
            self.assertIsNone(
                mc.shadow_fallback_skip_reason("full", reason, True)
            )

    def test_never_raises_on_garbage(self):
        self.assertIsNone(mc.shadow_fallback_skip_reason(None, 5, True))


class GlobalsFingerprintTests(unittest.TestCase):
    """Each of the four group-hash globals moves the fingerprint."""

    def test_stable_when_nothing_changes(self):
        a = mc.group_hash_globals_fingerprint()
        b = mc.group_hash_globals_fingerprint()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)

    def _changes(self, target, attr, value):
        base = mc.group_hash_globals_fingerprint()
        with mock.patch(target + "." + attr, value, create=True):
            changed = mc.group_hash_globals_fingerprint()
        self.assertNotEqual(base, changed, attr)
        self.assertEqual(base, mc.group_hash_globals_fingerprint())

    def test_extended_change_detection(self):
        import generate_weekly_pdfs as gwp
        self._changes(
            "generate_weekly_pdfs", "EXTENDED_CHANGE_DETECTION",
            not gwp.EXTENDED_CHANGE_DETECTION,
        )

    def test_rate_cutoff_date(self):
        self._changes("generate_weekly_pdfs", "RATE_CUTOFF_DATE", "sentinel-A")

    def test_subcontractor_fingerprint(self):
        self._changes(
            "generate_weekly_pdfs", "_SUBCONTRACTOR_RATES_FINGERPRINT",
            "sentinel-B",
        )

    def test_contract_rates_fingerprint(self):
        self._changes("pipeline.fetch", "_RATES_FINGERPRINT", "sentinel-C")

    def test_never_raises(self):
        with mock.patch.dict(sys.modules, {"generate_weekly_pdfs": None}):
            self.assertEqual(mc.group_hash_globals_fingerprint(), "")


class PriorGlobalsTests(unittest.TestCase):
    def test_newest_success_row_wins(self):
        rows = [
            _ledger_row("bad", status="failed"),
            _ledger_row("good"),
            _ledger_row("older"),
        ]
        self.assertEqual(mc.prior_globals_fingerprint(rows), "good")

    def test_none_when_absent_or_legacy(self):
        self.assertIsNone(mc.prior_globals_fingerprint([_ledger_row(None)]))
        self.assertIsNone(mc.prior_globals_fingerprint([]))
        self.assertIsNone(mc.prior_globals_fingerprint(None))
        self.assertIsNone(
            mc.prior_globals_fingerprint([_ledger_row("x", status="failed")])
        )

    def test_malformed_rows_never_raise(self):
        self.assertIsNone(mc.prior_globals_fingerprint(["junk", 5, None]))
        self.assertIsNone(
            mc.prior_globals_fingerprint(
                [{"status": "success", "notes": "str"}]
            )
        )


class ShadowFallbackSkipTests(unittest.TestCase):
    """The orchestrate helper through the real resolve_run_mode."""

    def _call(self, **over):
        kw = dict(
            source_sheets=[_source()],
            watermarks=_watermarks(),
            last_run_status=_CLEAN,
            ledger_rows=[_ledger_row("fp-1")],
            current_fp="fp-1",
        )
        kw.update(over)
        return orch._shadow_fallback_skip(**kw)

    def test_clean_run_with_unchanged_globals_runs_comparison(self):
        self.assertIsNone(self._call())

    def test_trigger6_previous_run_unfinished(self):
        out = self._call(
            last_run_status={"status": "running", "finished_at": None}
        )
        self.assertEqual(out["reason"], "would_fallback_full:trigger6")
        self.assertTrue(
            out["would_fallback_reason"].startswith("trigger6")
        )

    def test_trigger6_previous_run_failed(self):
        out = self._call(
            last_run_status={"status": "failed", "finished_at": "x"}
        )
        self.assertEqual(out["reason"], "would_fallback_full:trigger6")

    def test_trigger6_unreadable_last_status(self):
        out = self._call(last_run_status=None)
        self.assertEqual(out["reason"], "would_fallback_full:trigger6")

    def test_trigger4_empty_watermarks(self):
        out = self._call(watermarks={})
        self.assertEqual(out["reason"], "would_fallback_full:trigger4")

    def test_trigger5_operator_flag(self):
        with mock.patch.object(orch, "RESET_HASH_HISTORY", True):
            out = self._call()
        self.assertEqual(out["reason"], "would_fallback_full:trigger5")

    def test_trigger7_not_modelled_for_manual_execution(self):
        # The helper always asks as production_frequent, whatever the
        # real EXECUTION_TYPE is, so a manual run is judged on merit.
        with mock.patch.dict("os.environ", {"EXECUTION_TYPE": "manual"}):
            self.assertIsNone(self._call())

    def test_globals_changed_is_skipped(self):
        out = self._call(current_fp="fp-2")
        self.assertEqual(
            out["reason"],
            "would_fallback_full:group_hash_globals_changed",
        )

    def test_globals_unknown_prior_missing(self):
        out = self._call(ledger_rows=[_ledger_row(None)])
        self.assertEqual(
            out["reason"],
            "would_fallback_full:group_hash_globals_unknown",
        )

    def test_globals_unknown_when_current_fingerprint_unavailable(self):
        out = self._call(current_fp="")
        self.assertEqual(
            out["reason"],
            "would_fallback_full:group_hash_globals_unknown",
        )

    def test_globals_checked_before_trigger_modelling(self):
        out = self._call(
            current_fp="fp-2",
            last_run_status={"status": "running", "finished_at": None},
        )
        self.assertEqual(
            out["reason"],
            "would_fallback_full:group_hash_globals_changed",
        )

    def test_resolve_run_mode_is_called_pure_with_incremental_enabled(self):
        calls = []
        real = orch.resolve_run_mode

        def spy(*a, **k):
            calls.append(k)
            return real(*a, **k)

        with mock.patch.object(orch, "resolve_run_mode", spy):
            self._call()
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0]["incremental_enabled"], True)
        self.assertEqual(calls[0]["execution_type"], "production_frequent")

    def test_never_raises(self):
        with mock.patch.object(
            orch, "resolve_run_mode", side_effect=RuntimeError("boom")
        ):
            out = self._call()
        # an internal error is unknowable -> skipped, never a vacuous pass
        self.assertIsNotNone(out)
        self.assertTrue(out["reason"].startswith("would_fallback_full:"))


class MainWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(orch.main)

    def test_last_run_status_hoisted(self):
        self.assertIn("_last_run_status = None", self.src)

    def test_shadow_block_calls_the_helper_after_debt_check(self):
        i_debt = self.src.index('"reason": "regen_debt_unknown"')
        i_fb = self.src.index("_shadow_fallback_skip(")
        i_cmp = self.src.index("compare_shadow_parity(")
        self.assertLess(i_debt, i_fb)
        self.assertLess(i_fb, i_cmp)

    def test_fingerprint_persisted_on_both_finish_paths(self):
        self.assertGreaterEqual(self.src.count('"group_hash_globals_fp"'), 2)

    def test_resolve_run_mode_unchanged_flag_gate_first(self):
        src = inspect.getsource(orch.resolve_run_mode)
        self.assertLess(src.index("flag_off"), src.index("trigger4_empty"))

    def test_owner_decision_cited(self):
        self.assertIn("2026-10-29", inspect.getsource(mc))
        self.assertIn("2026-10-29", inspect.getsource(orch._shadow_fallback_skip))


class StreakQ2PinTests(unittest.TestCase):
    """Q2 = keep: a streak_eligible manual pass still counts (reader
    unchanged), and a trigger-6 skipped row neither counts nor resets."""

    def _rows(self, rows):
        client = mock.Mock()
        query = (
            client.schema.return_value.table.return_value
            .select.return_value.order.return_value.limit.return_value
        )
        query.execute.return_value = SimpleNamespace(data=rows)
        return client

    def _row(self, rid, verdict, exec_type="production_frequent",
             eligible=None, details=None):
        notes = {"execution_type": exec_type, "parity_verdict": verdict}
        if eligible is not None:
            notes["streak_eligible"] = eligible
        return {"run_id": rid, "started_at": "2026-10-29T00:00:00+00:00",
                "status": "success", "notes": notes}

    def test_manual_pass_counts_and_skipped_neither_counts_nor_resets(self):
        from pipeline_memory import reader as mem_reader

        rows = [
            self._row("manual-pass", "pass", "manual", True),
            self._row("after-cancel", "skipped"),
            self._row("freq-pass", "pass"),
        ]
        with mock.patch(
            "pipeline_memory.reader.get_client",
            return_value=self._rows(rows),
        ):
            result = mem_reader.get_parity_streak(limit=10)
        self.assertEqual(result["streak"], 2)
        self.assertIn("manual-pass", result["contributing_run_ids"])
        self.assertNotIn("after-cancel", result["contributing_run_ids"])


if __name__ == "__main__":
    unittest.main()
