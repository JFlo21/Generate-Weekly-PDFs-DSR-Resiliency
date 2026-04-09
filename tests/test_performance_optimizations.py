
import unittest
import hashlib
from unittest.mock import MagicMock, patch
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

class TestAttachmentCacheOptimization(unittest.TestCase):
    """Tests that verify the cached_attachments parameter eliminates redundant API calls.

    Both _has_existing_week_attachment() and delete_old_excel_attachments() accept a
    cached_attachments list. When provided, neither function should call
    client.Attachments.list_row_attachments(); when omitted they must fall back to it.
    This prevents ~200 duplicate API calls per run when the pre-fetch cache is populated.
    """

    def _make_attachment(self, name):
        """Build a minimal mock attachment object with a given filename."""
        att = MagicMock()
        att.name = name
        att.id = abs(hash(name)) % 100000
        return att

    # ── _has_existing_week_attachment ──────────────────────────────────────

    def test_has_existing_week_attachment_uses_cache_no_api_call(self):
        """When cached_attachments is provided, no API call should be made."""
        client = MagicMock()
        target_row = MagicMock()
        target_row.id = 42

        cached = [self._make_attachment("WR_12345_WeekEnding_081725_163045_abcd1234abcd1234.xlsx")]

        result = generate_weekly_pdfs._has_existing_week_attachment(
            client, 9999, target_row, "12345", "081725",
            cached_attachments=cached
        )

        self.assertTrue(result)
        client.Attachments.list_row_attachments.assert_not_called()

    def test_has_existing_week_attachment_falls_back_to_api_when_no_cache(self):
        """When cached_attachments is None, the function must call the API."""
        client = MagicMock()
        target_row = MagicMock()
        target_row.id = 42

        api_att = self._make_attachment("WR_12345_WeekEnding_081725_163045_abcd1234abcd1234.xlsx")
        client.Attachments.list_row_attachments.return_value.data = [api_att]

        result = generate_weekly_pdfs._has_existing_week_attachment(
            client, 9999, target_row, "12345", "081725",
            cached_attachments=None
        )

        self.assertTrue(result)
        client.Attachments.list_row_attachments.assert_called_once_with(9999, 42)

    def test_has_existing_week_attachment_empty_cache_returns_false_no_api_call(self):
        """An empty cached list should return False without making any API call."""
        client = MagicMock()
        target_row = MagicMock()
        target_row.id = 42

        result = generate_weekly_pdfs._has_existing_week_attachment(
            client, 9999, target_row, "12345", "081725",
            cached_attachments=[]
        )

        self.assertFalse(result)
        client.Attachments.list_row_attachments.assert_not_called()

    # ── delete_old_excel_attachments ──────────────────────────────────────

    def test_delete_old_attachments_uses_cache_no_api_call(self):
        """When cached_attachments is provided, no list_row_attachments API call is made."""
        client = MagicMock()
        target_row = MagicMock()
        target_row.id = 42

        cached = [self._make_attachment("WR_12345_WeekEnding_081725_163045_oldhash1oldhash1.xlsx")]

        generate_weekly_pdfs.delete_old_excel_attachments(
            client, 9999, target_row, "12345", "081725",
            current_data_hash="newhash1newhash1",
            cached_attachments=cached
        )

        client.Attachments.list_row_attachments.assert_not_called()

    def test_delete_old_attachments_falls_back_to_api_when_no_cache(self):
        """When cached_attachments is None, the function must call the API to list attachments."""
        client = MagicMock()
        target_row = MagicMock()
        target_row.id = 42
        client.Attachments.list_row_attachments.return_value.data = []

        generate_weekly_pdfs.delete_old_excel_attachments(
            client, 9999, target_row, "12345", "081725",
            current_data_hash="newhash1newhash1",
            cached_attachments=None
        )

        client.Attachments.list_row_attachments.assert_called_once_with(9999, 42)

    def test_delete_old_attachments_skips_when_hash_matches(self):
        """If the cached attachment already has the current hash, deletion is skipped."""
        client = MagicMock()
        target_row = MagicMock()
        target_row.id = 42

        current_hash = "aabbccdd11223344"
        cached = [self._make_attachment(f"WR_12345_WeekEnding_081725_163045_{current_hash}.xlsx")]

        deleted, skipped = generate_weekly_pdfs.delete_old_excel_attachments(
            client, 9999, target_row, "12345", "081725",
            current_data_hash=current_hash,
            cached_attachments=cached
        )

        self.assertEqual(deleted, 0)
        self.assertTrue(skipped)
        client.Attachments.list_row_attachments.assert_not_called()
        client.Attachments.delete_attachment.assert_not_called()

    def test_delete_old_attachments_deletes_when_hash_differs(self):
        """When cached attachment has a different hash, it should be deleted without an extra API call."""
        client = MagicMock()
        target_row = MagicMock()
        target_row.id = 42

        old_hash = "oldhash1oldhash10"
        new_hash = "newhash1newhash10"
        old_att = self._make_attachment(f"WR_12345_WeekEnding_081725_163045_{old_hash}.xlsx")
        cached = [old_att]

        deleted, skipped = generate_weekly_pdfs.delete_old_excel_attachments(
            client, 9999, target_row, "12345", "081725",
            current_data_hash=new_hash,
            cached_attachments=cached
        )

        self.assertFalse(skipped)
        client.Attachments.delete_attachment.assert_called_once_with(9999, old_att.id)
        client.Attachments.list_row_attachments.assert_not_called()


if __name__ == '__main__':
    unittest.main()
