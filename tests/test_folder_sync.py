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
        """Contractor folders must NOT be skipped — this is the core fix.

        Previously the code contained::

            if folder_config.get('folder_type') == 'contractor':
                logger.info("Contractor folder — skipping auto-sync "
                            "(manual push only)")
                return {'synced': 0, 'failed': 0}

        After the fix, contractor folders should be processed identically
        to standard folders.
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


if __name__ == '__main__':
    unittest.main()
