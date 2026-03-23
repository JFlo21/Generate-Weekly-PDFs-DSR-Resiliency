"""Tests for folder_sync_service — validates that contractor folders auto-sync.

The critical regression test is ``test_contractor_folder_not_skipped`` which
ensures that folders with ``folder_type='contractor'`` participate in
automatic sync runs (the original bug skipped them).
"""

import unittest
from unittest.mock import MagicMock, patch

import folder_sync_service
import smartsheet_client


class TestBuildCompositeKey(unittest.TestCase):
    """Tests for the composite key builder."""

    def test_basic_key(self):
        """Verify composite key format."""
        key = folder_sync_service.build_composite_key(123, 456)
        self.assertEqual(key, "123_456")

    def test_large_ids(self):
        """Verify composite key with realistic Smartsheet IDs."""
        key = folder_sync_service.build_composite_key(
            5099873842974596, 1234567890123456
        )
        self.assertEqual(key, "5099873842974596_1234567890123456")


class TestSyncFolder(unittest.TestCase):
    """Tests for sync_folder — the core fix entry point."""

    def _make_folder_config(self, folder_type='standard'):
        """Helper to create a folder config dict."""
        return {
            'folder_id': 4232010517505924,
            'folder_name': 'Test Folder',
            'folder_type': folder_type,
            'config_id': 3,
            'target_sheet_id': 5099873842974596,
        }

    @patch.object(smartsheet_client, 'list_folder_sheets', return_value=[])
    @patch.object(smartsheet_client, 'get_sheet')
    def test_standard_folder_processes(self, mock_get, mock_list):
        """Standard folders should complete sync without being skipped."""
        client = MagicMock()
        config = self._make_folder_config('standard')
        result = folder_sync_service.sync_folder(client, config)
        self.assertIn('synced', result)
        self.assertIn('failed', result)

    @patch.object(smartsheet_client, 'list_folder_sheets', return_value=[])
    @patch.object(smartsheet_client, 'get_sheet')
    def test_contractor_folder_not_skipped(self, mock_get, mock_list):
        """Contractor folders must NOT be skipped during auto-sync.

        Regression test for the fix that removed the contractor-type
        skip logic which previously prevented these folders from
        participating in automatic sync runs.
        """
        client = MagicMock()
        config = self._make_folder_config('contractor')
        result = folder_sync_service.sync_folder(client, config)
        # The function should have actually run (not short-circuited).
        # list_folder_sheets must have been called for the folder.
        mock_list.assert_called_once_with(client, 4232010517505924)
        self.assertIn('synced', result)
        self.assertIn('failed', result)

    @patch.object(smartsheet_client, 'list_folder_sheets', return_value=[])
    @patch.object(smartsheet_client, 'get_sheet')
    def test_contractor_folder_discovers_sheets(self, mock_get, mock_list):
        """Contractor folders should discover sheets just like others."""
        client = MagicMock()
        config = self._make_folder_config('contractor')
        folder_sync_service.sync_folder(client, config)
        mock_list.assert_called_once_with(client, config['folder_id'])

    @patch.object(smartsheet_client, 'add_rows_batched', return_value=(3, 0))
    @patch.object(smartsheet_client, 'list_folder_sheets')
    @patch.object(smartsheet_client, 'get_sheet')
    def test_contractor_folder_syncs_rows(
        self, mock_get, mock_list, mock_add
    ):
        """Contractor folders should sync new rows to the target sheet."""
        client = MagicMock()

        # Simulate a sheet with 3 rows
        mock_sheet = MagicMock()
        mock_row1 = MagicMock()
        mock_row1.id = 100
        mock_row2 = MagicMock()
        mock_row2.id = 200
        mock_row3 = MagicMock()
        mock_row3.id = 300
        mock_sheet.rows = [mock_row1, mock_row2, mock_row3]
        mock_sheet.columns = []

        sheet_info = {'id': 999, 'name': 'Test Sheet', 'row_count': 3}
        mock_list.return_value = [sheet_info]
        mock_get.return_value = mock_sheet

        config = self._make_folder_config('contractor')
        result = folder_sync_service.sync_folder(
            client, config, cached_keys=set()
        )
        self.assertEqual(result['synced'], 3)
        self.assertEqual(result['failed'], 0)
        mock_add.assert_called_once()


class TestSyncAllFolders(unittest.TestCase):
    """Tests for the multi-folder orchestrator."""

    @patch.object(folder_sync_service, 'sync_folder')
    def test_processes_all_folders(self, mock_sync):
        """All folders in the config list should be processed."""
        mock_sync.return_value = {'synced': 10, 'failed': 0}
        client = MagicMock()
        configs = [
            {
                'folder_id': 1,
                'folder_name': 'Folder A',
                'folder_type': 'standard',
                'config_id': 1,
            },
            {
                'folder_id': 2,
                'folder_name': 'Folder B',
                'folder_type': 'standard',
                'config_id': 2,
            },
            {
                'folder_id': 3,
                'folder_name': 'Subcontractor Folder',
                'folder_type': 'contractor',
                'config_id': 3,
            },
        ]
        result = folder_sync_service.sync_all_folders(client, configs)
        self.assertEqual(mock_sync.call_count, 3)
        self.assertEqual(result['total_synced'], 30)

    @patch.object(folder_sync_service, 'sync_folder')
    def test_contractor_folder_included_in_totals(self, mock_sync):
        """Contractor folder sync results should be included in totals."""
        mock_sync.side_effect = [
            {'synced': 500, 'failed': 0},
            {'synced': 500, 'failed': 0},
            {'synced': 200, 'failed': 0},
        ]
        client = MagicMock()
        configs = [
            {
                'folder_id': 1,
                'folder_name': 'Folder A',
                'folder_type': 'standard',
                'config_id': 1,
            },
            {
                'folder_id': 2,
                'folder_name': 'Folder B',
                'folder_type': 'standard',
                'config_id': 2,
            },
            {
                'folder_id': 3,
                'folder_name': 'Subcontractor Folder',
                'folder_type': 'contractor',
                'config_id': 3,
            },
        ]
        result = folder_sync_service.sync_all_folders(client, configs)
        self.assertEqual(result['total_synced'], 1200)
        self.assertEqual(
            result['per_folder']['Subcontractor Folder'], 200
        )


class TestSmartsheetClientHelpers(unittest.TestCase):
    """Tests for smartsheet_client helper functions."""

    def test_create_client_requires_token(self):
        """create_client should raise when no token is available."""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError):
                smartsheet_client.create_client(token=None)

    def test_get_column_map(self):
        """get_column_map should return lowercase name->id mapping."""
        mock_sheet = MagicMock()
        col1 = MagicMock()
        col1.title = 'Work Request #'
        col1.id = 111
        col2 = MagicMock()
        col2.title = 'CU Code'
        col2.id = 222
        mock_sheet.columns = [col1, col2]
        result = smartsheet_client.get_column_map(mock_sheet)
        self.assertEqual(result['work request #'], 111)
        self.assertEqual(result['cu code'], 222)


class TestSubcontractorFolderIds(unittest.TestCase):
    """Tests for subcontractor folder ID configuration."""

    def test_default_folder_ids(self):
        """Default subcontractor folder IDs should include both folders."""
        defaults = folder_sync_service._DEFAULT_SUBCONTRACTOR_FOLDER_IDS
        self.assertIn(4232010517505924, defaults)
        self.assertIn(2588197684307844, defaults)

    def test_get_subcontractor_folder_ids_defaults(self):
        """get_subcontractor_folder_ids returns defaults when env is empty."""
        with patch.dict('os.environ', {'SUBCONTRACTOR_FOLDER_IDS': ''}):
            ids = folder_sync_service.get_subcontractor_folder_ids()
            self.assertEqual(ids, [4232010517505924, 2588197684307844])

    def test_get_subcontractor_folder_ids_from_env(self):
        """get_subcontractor_folder_ids reads from env when set."""
        with patch.dict('os.environ', {'SUBCONTRACTOR_FOLDER_IDS': '111,222'}):
            ids = folder_sync_service.get_subcontractor_folder_ids()
            self.assertEqual(ids, [111, 222])

    def test_get_subcontractor_folder_ids_skips_invalid(self):
        """Invalid tokens in SUBCONTRACTOR_FOLDER_IDS are skipped."""
        with patch.dict('os.environ', {'SUBCONTRACTOR_FOLDER_IDS': '111,bad,222'}):
            ids = folder_sync_service.get_subcontractor_folder_ids()
            self.assertEqual(ids, [111, 222])


class TestSubcontractorFolderDiscovery(unittest.TestCase):
    """Tests for folder-based subcontractor sheet discovery."""

    def test_subcontractor_folder_ids_env_parsed(self):
        """SUBCONTRACTOR_FOLDER_IDS env var should be parsed in generate_weekly_pdfs."""
        import generate_weekly_pdfs
        self.assertIsInstance(generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS, list)

    def test_subcontractor_pricing_reversion_uses_original_rates(self):
        """Subcontractor sheets must have prices reverted to 100% Corpus rates.

        The reduced Arrowhead rates (×0.9) on subcontractor sheets
        must be converted back to original Corpus North & South rates
        when generating Excel files.
        """
        import generate_weekly_pdfs
        rates = {'CU-TEST': {'install': 100.0, 'removal': 50.0, 'transfer': 75.0}}
        row_data = {
            'CU': 'CU-TEST',
            'Work Type': 'Install',
            'Quantity': '2',
            'Units Total Price': '$180.00',
        }
        result = generate_weekly_pdfs.revert_subcontractor_price(row_data, rates)
        # Should be 100.0 × 2 = 200.0 (original rate), NOT 90.0 × 2 = 180.0 (reduced)
        self.assertAlmostEqual(result, 200.0)
        self.assertAlmostEqual(row_data['Units Total Price'], 200.0)

    def test_removal_pricing_reversion(self):
        """Removal work type should use removal rates for reversion."""
        import generate_weekly_pdfs
        rates = {'CU-TEST': {'install': 100.0, 'removal': 50.0, 'transfer': 75.0}}
        row_data = {
            'CU': 'CU-TEST',
            'Work Type': 'Removal',
            'Quantity': '3',
            'Units Total Price': '$135.00',
        }
        result = generate_weekly_pdfs.revert_subcontractor_price(row_data, rates)
        self.assertAlmostEqual(result, 150.0)

    def test_transfer_pricing_reversion(self):
        """Transfer work type should use transfer rates for reversion."""
        import generate_weekly_pdfs
        rates = {'CU-TEST': {'install': 100.0, 'removal': 50.0, 'transfer': 75.0}}
        row_data = {
            'CU': 'CU-TEST',
            'Work Type': 'Transfer',
            'Quantity': '1',
            'Units Total Price': '$67.50',
        }
        result = generate_weekly_pdfs.revert_subcontractor_price(row_data, rates)
        self.assertAlmostEqual(result, 75.0)


if __name__ == '__main__':
    unittest.main()
