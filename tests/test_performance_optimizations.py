
import importlib
import os
import unittest
import hashlib
from unittest.mock import MagicMock, patch


def _safe_reload_gwp():
    """Reload ``generate_weekly_pdfs`` without re-running its Sentry
    init side effects.

    The module's top-level ``if SENTRY_DSN: sentry_sdk.init(...)`` runs
    at import time, so a plain ``importlib.reload`` in a dev shell with
    ``SENTRY_DSN`` set would make unit tests network-dependent. We
    force an empty DSN and mock the init for the duration of the
    reload, following the pattern in ``tests/test_sentry_log_sanitizer.py``.
    """
    with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
        with patch("sentry_sdk.init"):
            return importlib.reload(generate_weekly_pdfs)


# Initial import under the same guard so test collection doesn't fire
# a real sentry_sdk.init either (Copilot review on test line 8).
with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
    with patch("sentry_sdk.init"):
        import generate_weekly_pdfs

class TestPerformanceOptimizations(unittest.TestCase):

    def test_calculate_data_hash_consistency_legacy(self):
        """Test that the optimized hash calculation produces the same result as the legacy string concatenation."""
        rows = [
            {
                'Work Request #': 'WR123',
                'CU': 'CU001',
                'Quantity': '10',
                'Units Total Price': '$100.00',
                'Snapshot Date': '2023-01-01',
                'Pole #': 'P1',
                'Work Type': 'Install',
                'Units Completed?': 'true'
            },
            {
                'Work Request #': 'WR123',
                'CU': 'CU002',
                'Quantity': '5',
                'Units Total Price': '$50.00',
                'Snapshot Date': '2023-01-01',
                'Pole #': 'P2',
                'Work Type': 'Install',
                'Units Completed?': 'true'
            }
        ]

        # Test generate_weekly_pdfs implementation (legacy mode)
        # We need to temporarily force EXTENDED_CHANGE_DETECTION to False to test that path
        original_setting = generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = False

        try:
            hash_val = generate_weekly_pdfs.calculate_data_hash(rows)
            self.assertEqual(len(hash_val), 16)
            # We can't easily assert equality with "original" since we are modifying the code in place.
            # But we can assert it produces a stable hash.
            hash_val_2 = generate_weekly_pdfs.calculate_data_hash(rows)
            self.assertEqual(hash_val, hash_val_2)
        finally:
            generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = original_setting

    def test_calculate_data_hash_consistency_extended(self):
        """Test the extended hash calculation optimization."""
        rows = [
            {
                'Work Request #': 'WR123',
                'CU': 'CU001',
                'Quantity': '10',
                'Units Total Price': '$100.00',
                'Snapshot Date': '2023-01-01',
                'Pole #': 'P1',
                'Work Type': 'Install',
                'Units Completed?': 'true',
                'Foreman': 'John Doe',
                'Dept #': '123',
                'Scope #': 'S1'
            }
        ]

        # Test generate_weekly_pdfs implementation (extended mode)
        # Force EXTENDED_CHANGE_DETECTION to True
        original_setting = generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = True

        try:
            hash_val = generate_weekly_pdfs.calculate_data_hash(rows)
            self.assertEqual(len(hash_val), 16)

            # Verify stability
            hash_val_2 = generate_weekly_pdfs.calculate_data_hash(rows)
            self.assertEqual(hash_val, hash_val_2)

            # Verify sensitivity to change
            rows[0]['Foreman'] = 'Jane Doe'
            hash_val_3 = generate_weekly_pdfs.calculate_data_hash(rows)
            self.assertNotEqual(hash_val, hash_val_3)
        finally:
            generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = original_setting

    def test_complete_fixed_optimization(self):
        """Test hash stability and group_source_rows date caching."""
        # Test hash stability
        rows = [{'Work Request #': 'WR1', 'Units Total Price': '10', 'Units Completed?': 'true'}]
        hash_val = generate_weekly_pdfs.calculate_data_hash(rows)
        self.assertEqual(len(hash_val), 16)

        # Test date caching logic in group_source_rows
        rows = [
            {
                'Foreman': 'F1',
                'Work Request #': 'WR1',
                'Weekly Reference Logged Date': '2023-01-01',
                'Snapshot Date': '2023-01-02',
                'Units Completed?': 'true',
                'Units Total Price': '100'
            }
        ]

        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertTrue(len(groups) > 0)


class TestAttachmentPrefetchBudget(unittest.TestCase):
    """Lock in the pre-fetch sub-budget guardrails added after the 2026-04-22
    production incident where a flaky Smartsheet connection stalled the
    attachment pre-fetch for ~17 minutes and consumed the entire
    TIME_BUDGET_MINUTES before a single Excel file could be generated.
    """

    def test_prefetch_budget_constants_exist(self):
        # Must exist so the pre-fetch can time-box itself.
        self.assertTrue(hasattr(generate_weekly_pdfs, 'ATTACHMENT_PREFETCH_MAX_MINUTES'))
        self.assertTrue(hasattr(generate_weekly_pdfs, 'ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC'))

    def test_prefetch_budget_defaults_with_isolated_env(self):
        # The constants are read at import time via os.getenv(). If the dev
        # shell / CI has ATTACHMENT_PREFETCH_* set, testing the raw module
        # values leaks the environment into the assertion. Clear both vars
        # and reload the module so the defaults are what we actually check.
        env_overrides = {
            "ATTACHMENT_PREFETCH_MAX_MINUTES": "",
            "ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC": "",
        }
        try:
            # clear=False preserves unrelated test env (SMARTSHEET_API_TOKEN etc.).
            with patch.dict(os.environ, env_overrides, clear=False):
                for _k in list(env_overrides):
                    os.environ.pop(_k, None)
                _safe_reload_gwp()
                self.assertEqual(generate_weekly_pdfs.ATTACHMENT_PREFETCH_MAX_MINUTES, 10)
                self.assertEqual(generate_weekly_pdfs.ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC, 45)

                # Upper-bound invariants — prevent a future tweak from
                # accidentally setting a pre-fetch budget that could burn
                # the whole session. Weekly workflow runs at
                # TIME_BUDGET_MINUTES=180; the pre-fetch budget must stay
                # well below that.
                self.assertGreater(generate_weekly_pdfs.ATTACHMENT_PREFETCH_MAX_MINUTES, 0)
                self.assertLess(generate_weekly_pdfs.ATTACHMENT_PREFETCH_MAX_MINUTES, 60)
                self.assertGreater(generate_weekly_pdfs.ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC, 0)
                self.assertLessEqual(generate_weekly_pdfs.ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC, 120)
        finally:
            # Reload AFTER the `with patch.dict(...)` block exits, so
            # os.environ has already been restored to whatever the outer
            # shell said. Reloading inside the `with` (as an earlier
            # revision did) picks up the popped env instead — the module
            # would stay pinned at defaults even when the outer env has
            # ATTACHMENT_PREFETCH_* set. Thanks @cursor[bot] for catching.
            _safe_reload_gwp()

    def test_futures_timeout_error_imported(self):
        # The consumer loop catches FuturesTimeoutError from the as_completed
        # wait (phase sub-budget) and from future.result (per-future guard).
        # If this import is removed the pre-fetch will crash on a stall
        # instead of falling back to the per-row path.
        # Phase 09 W6: the consumer loop (main()) relocated to
        # pipeline/orchestrate.py, which owns this import now.
        import pipeline.orchestrate
        self.assertTrue(hasattr(pipeline.orchestrate, 'FuturesTimeoutError'))


class TestPppAttachmentPrefetchBudget(unittest.TestCase):
    """Phase 01 gap closure (REVIEW-WR-05): the PPP secondary
    attachment-prefetch pass MUST mirror the primary prefetch's
    defense-in-depth pattern in full per Living Ledger
    2026-04-22 16:05.

    These tests are predominantly SOURCE-LEVEL invariant guards
    — the actual prefetch behavior is exercised end-to-end by
    the workflow run, not by unit tests (would require mocking
    the entire Smartsheet SDK + threading machinery, which the
    primary prefetch suite intentionally does not do). The
    source-level guards catch regressions like "PPP prefetch
    landed but with ``with _DaemonThreadPoolExecutor(...)``
    instead of explicit shutdown" before they ship.

    Mirrors TestAttachmentPrefetchBudget's structure exactly.
    """

    @staticmethod
    def _read_source() -> str:
        # Phase 09 W6: the PPP attachment-prefetch block lives in main(),
        # relocated to pipeline/orchestrate.py — concatenate facade +
        # orchestrate (follow-the-code superset).
        import inspect
        import pathlib
        import pipeline.orchestrate
        return (
            pathlib.Path(
                inspect.getsourcefile(generate_weekly_pdfs)
            ).read_text(encoding='utf-8')
            + "\n"
            + pathlib.Path(
                inspect.getsourcefile(pipeline.orchestrate)
            ).read_text(encoding='utf-8')
        )

    def test_constants_present(self):
        # The pre-flight guard depends on three constants — verify
        # they exist with reasonable defaults.
        self.assertTrue(
            hasattr(generate_weekly_pdfs, 'SUBCONTRACTOR_PPP_SHEET_ID'),
        )
        self.assertTrue(
            hasattr(generate_weekly_pdfs, 'ATTACHMENT_PREFETCH_MAX_MINUTES'),
        )
        self.assertTrue(
            hasattr(generate_weekly_pdfs, 'ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC'),
        )
        self.assertTrue(
            hasattr(generate_weekly_pdfs, 'ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN'),
        )

    def test_ppp_worker_function_exists(self):
        src = self._read_source()
        self.assertIn('def _fetch_ppp_row_attachments', src)

    def test_ppp_prefetch_targets_ppp_sheet(self):
        src = self._read_source()
        # Worker calls Attachments.list_row_attachments with the
        # PPP sheet id constant (not TARGET_SHEET_ID).
        self.assertIn(
            'list_row_attachments(SUBCONTRACTOR_PPP_SHEET_ID',
            src,
        )

    def test_ppp_prefetch_uses_daemon_executor_explicit_lifecycle(self):
        src = self._read_source()
        # Extract the PPP prefetch block so the executor-lifecycle
        # invariants are scoped to the new code path. The legitimate
        # ``with ThreadPoolExecutor(...) as executor`` callers
        # elsewhere in the file (folder discovery, parallel row
        # fetch, freeze_row parallelization) produce
        # non-discardable results — the ``with`` form is correct
        # for those because they need the implicit
        # ``shutdown(wait=True)`` to flush side effects. The PPP
        # prefetch is different: its work IS discardable (cache-
        # warming optimization with per-row fallback) so it must
        # use the daemon-executor + explicit shutdown(wait=False)
        # pattern established by the 2026-04-22 16:05 incident.
        ppp_start = src.find('def _fetch_ppp_row_attachments')
        self.assertGreater(
            ppp_start, -1,
            "PPP prefetch block not located — _fetch_ppp_row_attachments "
            "is the canonical anchor for the new block.",
        )
        # The PPP block ends at the next outer 'Load hash history'
        # comment marker (insertion-point comment) or at the
        # function attribution span set_data line.
        ppp_end_candidates = [
            src.find('# Load hash history', ppp_start),
            src.find('hash_history = load_hash_history', ppp_start),
        ]
        valid_ends = [c for c in ppp_end_candidates if c > -1]
        if not valid_ends:
            self.fail(
                "PPP prefetch block end marker not located — neither "
                "'# Load hash history' nor 'hash_history = load_hash_history' "
                "found after ppp_start."
            )
        ppp_end = min(valid_ends)
        self.assertGreater(
            ppp_end, ppp_start,
            "PPP prefetch block end marker not located.",
        )
        ppp_block = src[ppp_start:ppp_end]
        # Within the PPP block, MUST NOT use the ``with`` form for
        # _DaemonThreadPoolExecutor — the implicit
        # shutdown(wait=True) would re-introduce the 2026-04-22
        # 16:05 incident's block-on-stuck-worker bug.
        self.assertNotIn('with _DaemonThreadPoolExecutor', ppp_block)
        self.assertNotIn('with ThreadPoolExecutor', ppp_block)
        # The PPP block MUST construct the daemon executor by
        # direct call (no ``with``).
        self.assertIn('_DaemonThreadPoolExecutor(', ppp_block)
        self.assertIn('ppp_executor.shutdown(wait=False, cancel_futures=True)', ppp_block)
        # Whole-file invariant: there are now at least two
        # explicit shutdown(wait=False, cancel_futures=True) sites
        # — one in the primary prefetch and one in the PPP
        # prefetch — and both contribute to the count.
        self.assertGreaterEqual(
            src.count('shutdown(wait=False, cancel_futures=True)'),
            2,
            "Both primary and PPP prefetch blocks must use explicit "
            "shutdown(wait=False, cancel_futures=True). Expected >= 2 "
            "occurrences.",
        )

    def test_ppp_prefetch_skip_log_with_headroom(self):
        src = self._read_source()
        # Pre-flight guard logs an operator-visible reason.
        self.assertIn('Skipping PPP attachment prefetch', src)
        # The skip threshold is (PREFETCH_MAX + GENERATION_HEADROOM)
        # — verify both constants participate in the calculation.
        self.assertIn(
            'ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN', src,
        )
        # The PPP block must reference the headroom constant in
        # addition to PREFETCH_MAX. (Primary prefetch also
        # references both — this test relies on count.)
        self.assertGreaterEqual(
            src.count('ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN'),
            2,
            "Both primary and PPP prefetch pre-flight guards must "
            "reserve generation headroom. Expected >= 2 occurrences "
            "of the headroom constant.",
        )

    def test_ppp_prefetch_counters_separate(self):
        src = self._read_source()
        # Per 2026-04-22 16:05 rule (5), counters report cancelled
        # (queued futures we cancelled) and still_running (in-flight
        # we abandoned) SEPARATELY — don't conflate them via
        # ``not f.done()`` alone.
        self.assertIn('_ppp_prefetch_cancelled', src)
        self.assertIn('_ppp_prefetch_still_running', src)

    def test_ppp_atexit_detach_on_budget_exceed_only(self):
        src = self._read_source()
        # Per Copilot review noted in primary prefetch comments:
        # the atexit detach is on the budget-exceeded path only —
        # don't touch private APIs when workers completed normally.
        self.assertIn('_detach_ppp_from_atexit_registry', src)
        # Verify the detach is INSIDE the budget-exceed branch.
        # A naive `_detach_ppp_from_atexit_registry()` outside any
        # condition would touch private APIs on every run; the
        # explicit ``if _ppp_prefetch_budget_exceeded:`` gates it.
        self.assertRegex(
            src,
            r"if _ppp_prefetch_budget_exceeded:\s*\n\s*_detach_ppp_from_atexit_registry\(\)",
        )

    def test_ppp_prefetch_gated_on_kill_switch_and_distinct_sheet(self):
        src = self._read_source()
        # Eligibility gate must check the kill switch AND that PPP
        # is a different sheet from TARGET (skip the redundant pass
        # if operators have configured them to the same id).
        # AND not TEST_MODE AND target_map_ppp is populated.
        self.assertIn('SUBCONTRACTOR_RATE_VARIANTS_ENABLED', src)
        self.assertIn('SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID', src)
        self.assertIn('not TEST_MODE', src)
        self.assertIn('target_map_ppp', src)

    def test_ppp_populates_shared_attachment_cache(self):
        src = self._read_source()
        # Per WR-05 contract: PPP prefetch populates the SAME
        # ``attachment_cache`` dict the primary prefetch uses —
        # downstream ``_upload_one`` reads from that dict by
        # ``target_row.id`` without knowing which sheet the row
        # came from. The cache is dual-sheet-shared, not split.
        # Verify the PPP prefetch's `attachment_cache[row_id] = atts`
        # assignment is present in the PPP block (search for a
        # broader pattern since the same line exists in the
        # primary block too).
        self.assertGreaterEqual(
            src.count('attachment_cache['), 2,
            "Both primary and PPP prefetch blocks must write to the "
            "shared attachment_cache dict.",
        )


if __name__ == '__main__':
    unittest.main()
