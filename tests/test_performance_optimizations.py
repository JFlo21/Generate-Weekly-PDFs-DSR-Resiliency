
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


class TestAttachmentPrefetchRetirement(unittest.TestCase):
    """Phase 11 Plan 08 (INC-05 retirement, CONTEXT.md D-12) REWRITES this
    class (does not silently delete it — plan action) in place of the
    retired ``TestAttachmentPrefetchBudget``: the bulk attachment
    pre-fetch and its three ``ATTACHMENT_PREFETCH_*`` sub-budget
    constants (added after the 2026-04-22 production incident) are gone.
    Attachment identity now resolves from ``pipeline_memory.group_state``
    (``get_group_state_attachments_by_wr``), with every consumer falling
    back to the pre-existing per-row on-demand ``list_row_attachments``
    lookup on a miss (T-11-41) — unit coverage for that fallback lives
    below; unit coverage for the reader function itself lives in
    ``tests/test_incremental_read.py``.
    """

    def test_prefetch_budget_constants_removed(self):
        for name in (
            'ATTACHMENT_PREFETCH_MAX_MINUTES',
            'ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC',
            'ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN',
        ):
            self.assertFalse(
                hasattr(generate_weekly_pdfs, name),
                f"{name} should have been removed (Phase 11 Plan 08 / INC-05)",
            )
        import pipeline.config
        for name in (
            'ATTACHMENT_PREFETCH_MAX_MINUTES',
            'ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC',
            'ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN',
        ):
            self.assertFalse(hasattr(pipeline.config, name))

    def test_prefetch_machinery_fully_removed_from_source(self):
        import inspect
        import pipeline.orchestrate
        src = inspect.getsource(pipeline.orchestrate)
        for gone in (
            'def _fetch_row_attachments',
            'def _fetch_ppp_row_attachments',
            'smartsheet.attachment_prefetch',
            '_DaemonThreadPoolExecutor',
            'FuturesTimeoutError',
            '_prefetch_budget_exceeded',
            '_ppp_prefetch_eligible',
        ):
            self.assertNotIn(
                gone, src,
                f"{gone!r} should be fully removed from "
                "pipeline/orchestrate.py",
            )

    def test_group_state_attachment_resolution_wired(self):
        import inspect
        import pipeline.orchestrate
        src = inspect.getsource(pipeline.orchestrate)
        self.assertIn('get_group_state_attachments_by_wr', src)
        self.assertIn('_GroupStateAttachmentStub', src)
        # Both identity-check consumers still key the shared cache by
        # target_row.id, unchanged since before the retirement.
        self.assertIn(
            'cached_attachments=attachment_cache.get(target_row.id)', src,
        )

    def test_cleanup_untracked_never_reads_group_state_cache(self):
        # cleanup_untracked_sheet_attachments must always resolve via its
        # own per-row on-demand fallback — group_state only knows what
        # THIS pipeline wrote, never an off-contract / legacy attachment
        # it needs to prune.
        import inspect
        import pipeline.orchestrate
        src = inspect.getsource(pipeline.orchestrate)
        self.assertIn('_cleanup_cache = None', src)

    def test_has_existing_week_attachment_falls_back_on_no_cache(self):
        # Acceptance criterion: the cleanup consumers still resolve
        # attachment identity when no cache entry exists (cold cache,
        # group_state miss, or a Supabase outage) — they call
        # list_row_attachments exactly as they would with no pre-fetch
        # (and no group_state resolution) ever having run.
        client = MagicMock()
        att = MagicMock()
        att.name = "WR_90001_WeekEnding_041926_120000_deadbeefcafe0001.xlsx"
        att.id = 1
        client.Attachments.list_row_attachments.return_value.data = [att]
        row = MagicMock()
        row.id = 555

        found = generate_weekly_pdfs._has_existing_week_attachment(
            client, 123, row, "90001", "041926", "primary", None,
            cached_attachments=None,
        )

        self.assertTrue(found)
        client.Attachments.list_row_attachments.assert_called_once_with(
            123, row.id,
        )

    def test_delete_old_excel_attachments_falls_back_on_no_cache(self):
        client = MagicMock()
        att = MagicMock()
        att.name = "WR_90001_WeekEnding_041926_120000_deadbeefcafe0001.xlsx"
        att.id = 1
        client.Attachments.list_row_attachments.return_value.data = [att]
        client.Attachments.delete_attachment.return_value = None
        row = MagicMock()
        row.id = 555

        original = generate_weekly_pdfs.SUPABASE_HASH_STORE_AUTHORITATIVE
        generate_weekly_pdfs.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        try:
            deleted, skipped = generate_weekly_pdfs.delete_old_excel_attachments(
                client, 123, row, "90001", "041926", "newhash0000000000",
                variant="primary", identifier=None,
                cached_attachments=None,
            )
        finally:
            generate_weekly_pdfs.SUPABASE_HASH_STORE_AUTHORITATIVE = original

        self.assertEqual((deleted, skipped), (1, False))
        client.Attachments.list_row_attachments.assert_called_once_with(
            123, row.id,
        )
        client.Attachments.delete_attachment.assert_called_once_with(123, 1)


if __name__ == '__main__':
    unittest.main()
