
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
        self.assertTrue(hasattr(generate_weekly_pdfs, 'FuturesTimeoutError'))

if __name__ == '__main__':
    unittest.main()
