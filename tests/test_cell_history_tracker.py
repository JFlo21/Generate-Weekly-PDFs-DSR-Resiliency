#!/usr/bin/env python3
"""
Tests for Cell History Tracker Module
"""

import os
import json
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
import pytest
import sys

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cell_history_tracker import CellHistoryTracker


class TestCellHistoryTracker:
    """Test suite for CellHistoryTracker class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test output."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock Smartsheet client."""
        client = Mock()
        client.Cells = Mock()
        return client
    
    def test_initialization(self, mock_client, temp_dir):
        """Test that CellHistoryTracker initializes correctly."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        assert tracker.client == mock_client
        assert tracker.output_folder == temp_dir
        assert tracker.history_file == os.path.join(temp_dir, "cell_history.json")
        assert "sheets" in tracker.history_data
        assert "summary" in tracker.history_data
    
    def test_load_empty_history(self, mock_client, temp_dir):
        """Test loading history when no file exists."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        assert tracker.history_data["last_updated"] is None
        assert tracker.history_data["sheets"] == {}
        assert tracker.history_data["summary"]["total_sheets_tracked"] == 0
    
    def test_save_and_load_history(self, mock_client, temp_dir):
        """Test saving and loading history data."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        # Add some test data
        tracker.history_data["sheets"]["123"] = {
            "sheet_id": 123,
            "sheet_name": "Test Sheet",
            "rows": {
                "456": {
                    "row_id": 456,
                    "work_request": "WR-001",
                    "history": [
                        {
                            "modified_at": "2024-01-01T00:00:00Z",
                            "modified_by": "test_user",
                            "value": "Test Value"
                        }
                    ]
                }
            }
        }
        
        # Save the history
        tracker._save_history()
        
        # Create a new tracker instance to load the saved data
        tracker2 = CellHistoryTracker(mock_client, temp_dir)
        
        assert "123" in tracker2.history_data["sheets"]
        assert tracker2.history_data["sheets"]["123"]["sheet_name"] == "Test Sheet"
        assert "456" in tracker2.history_data["sheets"]["123"]["rows"]
    
    def test_track_no_modified_by_column(self, mock_client, temp_dir):
        """Test tracking when no sheets have Modified By column."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        source_sheets = [
            {
                "id": 123,
                "name": "Test Sheet",
                "column_mapping": {
                    "Work Request #": 789,
                    "Snapshot Date": 790
                }
            }
        ]
        
        rows = [
            {
                "__sheet_id": 123,
                "__row_id": 456,
                "Work Request #": "WR-001"
            }
        ]
        
        results = tracker.track_modified_by_column(source_sheets, rows)
        
        assert results["sheets_processed"] == 0
        assert results["rows_processed"] == 0
    
    def test_track_with_modified_by_column(self, mock_client, temp_dir):
        """Test tracking when sheets have Modified By column."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        # Mock cell history response
        mock_history_item = Mock()
        mock_history_item.modified_at = "2024-01-01T00:00:00Z"
        mock_history_item.modified_by = Mock(name="Test User")
        mock_history_item.display_value = "Test Value"
        mock_history_item.value = None
        
        mock_response = Mock()
        mock_response.data = [mock_history_item]
        
        mock_client.Cells.get_cell_history.return_value = mock_response
        
        source_sheets = [
            {
                "id": 123,
                "name": "Test Sheet",
                "column_mapping": {
                    "Work Request #": 789,
                    "Modified By": 791
                }
            }
        ]
        
        rows = [
            {
                "__sheet_id": 123,
                "__row_id": 456,
                "Work Request #": "WR-001"
            }
        ]
        
        results = tracker.track_modified_by_column(source_sheets, rows)
        
        assert results["sheets_processed"] == 1
        assert results["rows_processed"] == 1
        assert results["history_entries_added"] == 1
        
        # Verify the cell history API was called
        mock_client.Cells.get_cell_history.assert_called_once_with(
            sheet_id=123,
            row_id=456,
            column_id=791,
            include_all=True
        )
    
    def test_fetch_cell_history_error_handling(self, mock_client, temp_dir):
        """Test error handling when fetching cell history fails."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        # Make the API call raise an exception
        mock_client.Cells.get_cell_history.side_effect = Exception("API Error")
        
        history = tracker._fetch_cell_history(123, 456, 789)
        
        # Should return empty list on error
        assert history == []
    
    def test_extract_modified_by_with_name(self, mock_client, temp_dir):
        """Test extracting modified_by when it has a name attribute."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        mock_item = Mock()
        mock_modified_by = Mock()
        mock_modified_by.name = "John Doe"
        mock_item.modified_by = mock_modified_by
        
        result = tracker._extract_modified_by(mock_item)
        
        assert result == "John Doe"
    
    def test_extract_modified_by_with_email(self, mock_client, temp_dir):
        """Test extracting modified_by when it has an email attribute."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        mock_item = Mock()
        mock_item.modified_by = Mock(spec=['email'])
        mock_item.modified_by.email = "john@example.com"
        # Remove name attribute to test email fallback
        del mock_item.modified_by.name
        
        result = tracker._extract_modified_by(mock_item)
        
        assert result == "john@example.com"
    
    def test_extract_modified_by_string(self, mock_client, temp_dir):
        """Test extracting modified_by when it's a string."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        mock_item = Mock()
        mock_item.modified_by = "User Name"
        
        result = tracker._extract_modified_by(mock_item)
        
        assert result == "User Name"
    
    def test_get_history_summary(self, mock_client, temp_dir):
        """Test getting history summary."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        tracker.history_data["sheets"]["123"] = {"sheet_id": 123}
        tracker.history_data["sheets"]["456"] = {"sheet_id": 456}
        tracker.history_data["summary"] = {
            "total_sheets_tracked": 2,
            "total_rows_tracked": 10
        }
        
        summary = tracker.get_history_summary()
        
        assert "summary" in summary
        assert "sheets_tracked" in summary
        assert len(summary["sheets_tracked"]) == 2
        assert "123" in summary["sheets_tracked"]
    
    def test_get_row_history_exists(self, mock_client, temp_dir):
        """Test getting history for a specific row that exists."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        test_history = {
            "row_id": 456,
            "work_request": "WR-001",
            "history": []
        }
        
        tracker.history_data["sheets"]["123"] = {
            "rows": {
                "456": test_history
            }
        }
        
        result = tracker.get_row_history(123, 456)
        
        assert result == test_history
    
    def test_get_row_history_not_exists(self, mock_client, temp_dir):
        """Test getting history for a row that doesn't exist."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        result = tracker.get_row_history(123, 456)
        
        assert result is None
    
    def test_track_multiple_sheets(self, mock_client, temp_dir):
        """Test tracking multiple sheets simultaneously."""
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        # Mock cell history response
        mock_history_item = Mock()
        mock_history_item.modified_at = "2024-01-01T00:00:00Z"
        mock_history_item.modified_by = Mock(name="Test User")
        mock_history_item.display_value = "Value"
        mock_history_item.value = None
        
        mock_response = Mock()
        mock_response.data = [mock_history_item]
        
        mock_client.Cells.get_cell_history.return_value = mock_response
        
        source_sheets = [
            {
                "id": 123,
                "name": "Sheet 1",
                "column_mapping": {"Modified By": 701, "Work Request #": 702}
            },
            {
                "id": 456,
                "name": "Sheet 2",
                "column_mapping": {"Modified By": 801, "Work Request #": 802}
            }
        ]
        
        rows = [
            {"__sheet_id": 123, "__row_id": 1001, "Work Request #": "WR-001"},
            {"__sheet_id": 456, "__row_id": 2001, "Work Request #": "WR-002"}
        ]
        
        results = tracker.track_modified_by_column(source_sheets, rows)
        
        assert results["sheets_processed"] == 2
        assert results["rows_processed"] == 2
        assert mock_client.Cells.get_cell_history.call_count == 2


def test_cell_history_tracker_import():
    """Test that cell history tracker can be imported."""
    from cell_history_tracker import CellHistoryTracker
    assert CellHistoryTracker is not None


def test_basic_functionality():
    """Basic smoke test for cell history tracker."""
    mock_client = Mock()
    mock_client.Cells = Mock()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        tracker = CellHistoryTracker(mock_client, temp_dir)
        
        # Should initialize without errors
        assert tracker is not None
        assert tracker.history_data is not None
