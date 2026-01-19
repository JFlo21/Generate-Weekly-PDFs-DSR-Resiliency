"""
Unit tests for get_all_source_rows optimization.
Verifies that the O(1) hash map lookup produces the same results as the original O(M) implementation.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, MagicMock
import pytest


def test_get_all_source_rows_with_empty_column_mapping():
    """Test that empty column mappings are handled gracefully."""
    from generate_weekly_pdfs_complete_fixed import get_all_source_rows
    
    # Mock client
    mock_client = Mock()
    
    # Create mock sheet with empty column mapping
    mock_sheet = Mock()
    mock_sheet.rows = []
    mock_client.Sheets.get_sheet.return_value = mock_sheet
    
    source_sheets = [{
        'id': 12345,
        'name': 'Test Sheet',
        'column_mapping': {}  # Empty mapping
    }]
    
    # Should handle empty mapping without errors
    result = get_all_source_rows(mock_client, source_sheets)
    assert result == []


def test_get_all_source_rows_with_valid_data():
    """Test that valid rows are correctly extracted using the optimized O(1) lookup."""
    from generate_weekly_pdfs_complete_fixed import get_all_source_rows
    
    # Mock client
    mock_client = Mock()
    
    # Create mock cells with different column IDs
    mock_cell_wr = Mock()
    mock_cell_wr.column_id = 1001
    mock_cell_wr.display_value = "WR12345"
    
    mock_cell_date = Mock()
    mock_cell_date.column_id = 1002
    mock_cell_date.display_value = "2026-01-15"
    
    mock_cell_completed = Mock()
    mock_cell_completed.column_id = 1003
    mock_cell_completed.display_value = "true"
    
    mock_cell_price = Mock()
    mock_cell_price.column_id = 1004
    mock_cell_price.display_value = "$100.50"
    
    # Create mock row
    mock_row = Mock()
    mock_row.cells = [mock_cell_wr, mock_cell_date, mock_cell_completed, mock_cell_price]
    
    # Create mock sheet
    mock_sheet = Mock()
    mock_sheet.rows = [mock_row]
    mock_client.Sheets.get_sheet.return_value = mock_sheet
    
    # Define source sheets with column mapping
    source_sheets = [{
        'id': 12345,
        'name': 'Test Sheet',
        'column_mapping': {
            'Work Request #': 1001,
            'Weekly Reference Logged Date': 1002,
            'Units Completed?': 1003,
            'Units Total Price': 1004
        }
    }]
    
    # Execute function
    result = get_all_source_rows(mock_client, source_sheets)
    
    # Verify results
    assert len(result) == 1
    assert result[0]['Work Request #'] == 'WR12345'
    assert result[0]['Weekly Reference Logged Date'] == '2026-01-15'
    assert result[0]['Units Completed?'] == 'true'
    assert result[0]['Units Total Price'] == '$100.50'


def test_get_all_source_rows_filters_invalid_rows():
    """Test that rows missing required data are filtered out."""
    from generate_weekly_pdfs_complete_fixed import get_all_source_rows
    
    # Mock client
    mock_client = Mock()
    
    # Create valid row
    mock_cell_wr_valid = Mock()
    mock_cell_wr_valid.column_id = 1001
    mock_cell_wr_valid.display_value = "WR12345"
    
    mock_cell_date_valid = Mock()
    mock_cell_date_valid.column_id = 1002
    mock_cell_date_valid.display_value = "2026-01-15"
    
    mock_cell_completed_valid = Mock()
    mock_cell_completed_valid.column_id = 1003
    mock_cell_completed_valid.display_value = "true"
    
    mock_cell_price_valid = Mock()
    mock_cell_price_valid.column_id = 1004
    mock_cell_price_valid.display_value = "$100.50"
    
    mock_row_valid = Mock()
    mock_row_valid.cells = [mock_cell_wr_valid, mock_cell_date_valid, mock_cell_completed_valid, mock_cell_price_valid]
    
    # Create invalid row (missing date)
    mock_cell_wr_invalid = Mock()
    mock_cell_wr_invalid.column_id = 1001
    mock_cell_wr_invalid.display_value = "WR67890"
    
    mock_cell_date_invalid = Mock()
    mock_cell_date_invalid.column_id = 1002
    mock_cell_date_invalid.display_value = None  # Missing date
    
    mock_cell_completed_invalid = Mock()
    mock_cell_completed_invalid.column_id = 1003
    mock_cell_completed_invalid.display_value = "false"  # Not completed
    
    mock_cell_price_invalid = Mock()
    mock_cell_price_invalid.column_id = 1004
    mock_cell_price_invalid.display_value = "$50.00"
    
    mock_row_invalid = Mock()
    mock_row_invalid.cells = [mock_cell_wr_invalid, mock_cell_date_invalid, mock_cell_completed_invalid, mock_cell_price_invalid]
    
    # Create mock sheet with both rows
    mock_sheet = Mock()
    mock_sheet.rows = [mock_row_valid, mock_row_invalid]
    mock_client.Sheets.get_sheet.return_value = mock_sheet
    
    # Define source sheets
    source_sheets = [{
        'id': 12345,
        'name': 'Test Sheet',
        'column_mapping': {
            'Work Request #': 1001,
            'Weekly Reference Logged Date': 1002,
            'Units Completed?': 1003,
            'Units Total Price': 1004
        }
    }]
    
    # Execute function
    result = get_all_source_rows(mock_client, source_sheets)
    
    # Only valid row should be returned
    assert len(result) == 1
    assert result[0]['Work Request #'] == 'WR12345'


def test_get_all_source_rows_with_many_columns():
    """Test performance optimization with many columns (edge case for O(1) vs O(M))."""
    from generate_weekly_pdfs_complete_fixed import get_all_source_rows
    
    # Mock client
    mock_client = Mock()
    
    # Create a column mapping with 50 columns
    column_mapping = {
        'Work Request #': 1001,
        'Weekly Reference Logged Date': 1002,
        'Units Completed?': 1003,
        'Units Total Price': 1004
    }
    
    # Add 46 more columns to simulate a large mapping
    for i in range(5, 51):
        column_mapping[f'Extra Column {i}'] = 1000 + i
    
    # Create mock cells - only required ones have values
    mock_cells = []
    
    mock_cell_wr = Mock()
    mock_cell_wr.column_id = 1001
    mock_cell_wr.display_value = "WR99999"
    mock_cells.append(mock_cell_wr)
    
    mock_cell_date = Mock()
    mock_cell_date.column_id = 1002
    mock_cell_date.display_value = "2026-01-20"
    mock_cells.append(mock_cell_date)
    
    mock_cell_completed = Mock()
    mock_cell_completed.column_id = 1003
    mock_cell_completed.display_value = "1"
    mock_cells.append(mock_cell_completed)
    
    mock_cell_price = Mock()
    mock_cell_price.column_id = 1004
    mock_cell_price.display_value = "250.75"
    mock_cells.append(mock_cell_price)
    
    # Add cells for all other columns (simulating a wide sheet)
    for i in range(5, 51):
        mock_cell = Mock()
        mock_cell.column_id = 1000 + i
        mock_cell.display_value = f"Value {i}"
        mock_cells.append(mock_cell)
    
    # Create mock row
    mock_row = Mock()
    mock_row.cells = mock_cells
    
    # Create mock sheet
    mock_sheet = Mock()
    mock_sheet.rows = [mock_row]
    mock_client.Sheets.get_sheet.return_value = mock_sheet
    
    # Define source sheets
    source_sheets = [{
        'id': 12345,
        'name': 'Test Sheet with Many Columns',
        'column_mapping': column_mapping
    }]
    
    # Execute function (this tests the O(1) optimization)
    result = get_all_source_rows(mock_client, source_sheets)
    
    # Verify results
    assert len(result) == 1
    assert result[0]['Work Request #'] == 'WR99999'
    assert result[0]['Weekly Reference Logged Date'] == '2026-01-20'
    assert result[0]['Units Completed?'] == '1'
    assert result[0]['Units Total Price'] == '250.75'
    
    # Verify all extra columns were captured
    for i in range(5, 51):
        assert result[0][f'Extra Column {i}'] == f'Value {i}'


def test_get_all_source_rows_handles_unmapped_columns():
    """Test that cells with column IDs not in the mapping are ignored."""
    from generate_weekly_pdfs_complete_fixed import get_all_source_rows
    
    # Mock client
    mock_client = Mock()
    
    # Create mock cells - some mapped, some unmapped
    mock_cell_wr = Mock()
    mock_cell_wr.column_id = 1001
    mock_cell_wr.display_value = "WR54321"
    
    mock_cell_unmapped = Mock()
    mock_cell_unmapped.column_id = 9999  # Not in mapping
    mock_cell_unmapped.display_value = "Should be ignored"
    
    mock_cell_date = Mock()
    mock_cell_date.column_id = 1002
    mock_cell_date.display_value = "2026-01-18"
    
    mock_cell_completed = Mock()
    mock_cell_completed.column_id = 1003
    mock_cell_completed.display_value = "checked"
    
    mock_cell_price = Mock()
    mock_cell_price.column_id = 1004
    mock_cell_price.display_value = "$75.25"
    
    # Create mock row with unmapped cell
    mock_row = Mock()
    mock_row.cells = [mock_cell_wr, mock_cell_unmapped, mock_cell_date, mock_cell_completed, mock_cell_price]
    
    # Create mock sheet
    mock_sheet = Mock()
    mock_sheet.rows = [mock_row]
    mock_client.Sheets.get_sheet.return_value = mock_sheet
    
    # Define source sheets
    source_sheets = [{
        'id': 12345,
        'name': 'Test Sheet',
        'column_mapping': {
            'Work Request #': 1001,
            'Weekly Reference Logged Date': 1002,
            'Units Completed?': 1003,
            'Units Total Price': 1004
        }
    }]
    
    # Execute function
    result = get_all_source_rows(mock_client, source_sheets)
    
    # Verify unmapped column is not in result
    assert len(result) == 1
    assert result[0]['Work Request #'] == 'WR54321'
    assert 9999 not in result[0]  # Column ID should not appear
    # No key for unmapped column should exist
    assert all(key in ['Work Request #', 'Weekly Reference Logged Date', 'Units Completed?', 'Units Total Price'] 
               for key in result[0].keys())


def test_get_all_source_rows_filters_zero_price():
    """Test that rows with zero or negative price are filtered out."""
    from generate_weekly_pdfs_complete_fixed import get_all_source_rows
    
    # Mock client
    mock_client = Mock()
    
    # Create row with zero price
    mock_cell_wr = Mock()
    mock_cell_wr.column_id = 1001
    mock_cell_wr.display_value = "WR00000"
    
    mock_cell_date = Mock()
    mock_cell_date.column_id = 1002
    mock_cell_date.display_value = "2026-01-15"
    
    mock_cell_completed = Mock()
    mock_cell_completed.column_id = 1003
    mock_cell_completed.display_value = "true"
    
    mock_cell_price = Mock()
    mock_cell_price.column_id = 1004
    mock_cell_price.display_value = "$0.00"  # Zero price
    
    mock_row = Mock()
    mock_row.cells = [mock_cell_wr, mock_cell_date, mock_cell_completed, mock_cell_price]
    
    # Create mock sheet
    mock_sheet = Mock()
    mock_sheet.rows = [mock_row]
    mock_client.Sheets.get_sheet.return_value = mock_sheet
    
    # Define source sheets
    source_sheets = [{
        'id': 12345,
        'name': 'Test Sheet',
        'column_mapping': {
            'Work Request #': 1001,
            'Weekly Reference Logged Date': 1002,
            'Units Completed?': 1003,
            'Units Total Price': 1004
        }
    }]
    
    # Execute function
    result = get_all_source_rows(mock_client, source_sheets)
    
    # Row with zero price should be filtered out
    assert len(result) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
