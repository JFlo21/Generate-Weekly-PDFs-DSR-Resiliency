"""
Test suite for Work Request exemption list functionality.
"""

import json
import os
import tempfile
import pytest

# Import the functions we need to test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_weekly_pdfs import load_exemption_list, group_source_rows


class TestLoadExemptionList:
    """Test cases for loading exemption list from JSON file."""
    
    def test_load_empty_exemption_list(self):
        """Test loading an exemption list with no entries."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"exempted_work_requests": []}, f)
            temp_path = f.name
        
        try:
            result = load_exemption_list(temp_path)
            assert isinstance(result, set)
            assert len(result) == 0
        finally:
            os.unlink(temp_path)
    
    def test_load_exemption_list_with_entries(self):
        """Test loading an exemption list with multiple entries."""
        test_wrs = ["12345678", "87654321", "11111111"]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"exempted_work_requests": test_wrs}, f)
            temp_path = f.name
        
        try:
            result = load_exemption_list(temp_path)
            assert isinstance(result, set)
            assert len(result) == 3
            assert "12345678" in result
            assert "87654321" in result
            assert "11111111" in result
        finally:
            os.unlink(temp_path)
    
    def test_load_exemption_list_with_decimals(self):
        """Test that decimal work request numbers are normalized."""
        # Smartsheet sometimes returns WR numbers as floats (e.g., 12345678.0)
        test_wrs = ["12345678.0", 87654321.0, "11111111"]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"exempted_work_requests": test_wrs}, f)
            temp_path = f.name
        
        try:
            result = load_exemption_list(temp_path)
            assert isinstance(result, set)
            assert len(result) == 3
            assert "12345678" in result  # Should remove .0
            assert "87654321" in result  # Should convert to string
            assert "11111111" in result
        finally:
            os.unlink(temp_path)
    
    def test_load_exemption_list_nonexistent_file(self):
        """Test behavior when file doesn't exist."""
        result = load_exemption_list("/nonexistent/path/to/file.json")
        assert isinstance(result, set)
        assert len(result) == 0
    
    def test_load_exemption_list_invalid_json(self):
        """Test behavior with malformed JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json content")
            temp_path = f.name
        
        try:
            result = load_exemption_list(temp_path)
            assert isinstance(result, set)
            assert len(result) == 0  # Should return empty set on error
        finally:
            os.unlink(temp_path)
    
    def test_load_exemption_list_wrong_structure(self):
        """Test behavior with valid JSON but wrong structure."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"wrong_key": ["12345678"]}, f)
            temp_path = f.name
        
        try:
            result = load_exemption_list(temp_path)
            assert isinstance(result, set)
            assert len(result) == 0  # Should return empty set if key missing
        finally:
            os.unlink(temp_path)
    
    def test_load_exemption_list_with_whitespace(self):
        """Test that whitespace is properly stripped."""
        test_wrs = ["  12345678  ", "87654321\n", "\t11111111"]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"exempted_work_requests": test_wrs}, f)
            temp_path = f.name
        
        try:
            result = load_exemption_list(temp_path)
            assert isinstance(result, set)
            assert len(result) == 3
            assert "12345678" in result
            assert "87654321" in result
            assert "11111111" in result
        finally:
            os.unlink(temp_path)
    
    def test_load_exemption_list_with_empty_values(self):
        """Test that empty values are filtered out."""
        test_wrs = ["12345678", "", None, "87654321", "  ", "11111111"]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"exempted_work_requests": test_wrs}, f)
            temp_path = f.name
        
        try:
            result = load_exemption_list(temp_path)
            assert isinstance(result, set)
            assert len(result) == 3  # Only non-empty values
            assert "12345678" in result
            assert "87654321" in result
            assert "11111111" in result
        finally:
            os.unlink(temp_path)


class TestGroupSourceRowsWithExemption:
    """Test cases for group_source_rows with exemption list."""
    
    def create_test_row(self, wr_num, week_date="2024-01-07", price="100.00"):
        """Helper to create a test row."""
        return {
            'Work Request #': wr_num,
            'Weekly Reference Logged Date': week_date,
            'Snapshot Date': week_date,
            'Units Total Price': price,
            'Quantity': "1",
            'Units Completed?': True,
            'Foreman': 'Test Foreman',
            'CU': 'CU100',
            '__effective_user': 'Test User',
            '__assignment_method': 'TEST',
            '__is_helper_row': False,
        }
    
    def test_grouping_without_exemption(self):
        """Test that grouping works normally when no exemption list provided."""
        rows = [
            self.create_test_row("12345678"),
            self.create_test_row("12345678"),
            self.create_test_row("87654321"),
        ]
        
        groups = group_source_rows(rows, exemption_list=None)
        
        # Should have 2 groups (one for each WR)
        assert len(groups) == 2
        
        # Check that both WRs are present
        wr_numbers = set()
        for group_rows in groups.values():
            wr_numbers.add(str(group_rows[0].get('Work Request #')).split('.')[0])
        
        assert "12345678" in wr_numbers
        assert "87654321" in wr_numbers
    
    def test_grouping_with_empty_exemption_list(self):
        """Test that empty exemption list doesn't affect grouping."""
        rows = [
            self.create_test_row("12345678"),
            self.create_test_row("87654321"),
        ]
        
        groups = group_source_rows(rows, exemption_list=set())
        
        # Should have 2 groups
        assert len(groups) == 2
    
    def test_grouping_exempts_single_wr(self):
        """Test that a single WR can be exempted."""
        rows = [
            self.create_test_row("12345678"),
            self.create_test_row("87654321"),
            self.create_test_row("11111111"),
        ]
        
        exemption_list = {"87654321"}  # Exempt only this one
        groups = group_source_rows(rows, exemption_list=exemption_list)
        
        # Should have 2 groups (87654321 exempted)
        assert len(groups) == 2
        
        # Verify exempted WR is not present
        wr_numbers = set()
        for group_rows in groups.values():
            wr_numbers.add(str(group_rows[0].get('Work Request #')).split('.')[0])
        
        assert "12345678" in wr_numbers
        assert "87654321" not in wr_numbers  # This one was exempted
        assert "11111111" in wr_numbers
    
    def test_grouping_exempts_multiple_wrs(self):
        """Test that multiple WRs can be exempted."""
        rows = [
            self.create_test_row("12345678"),
            self.create_test_row("87654321"),
            self.create_test_row("11111111"),
            self.create_test_row("22222222"),
        ]
        
        exemption_list = {"87654321", "22222222"}  # Exempt these two
        groups = group_source_rows(rows, exemption_list=exemption_list)
        
        # Should have 2 groups (2 exempted)
        assert len(groups) == 2
        
        # Verify only non-exempted WRs are present
        wr_numbers = set()
        for group_rows in groups.values():
            wr_numbers.add(str(group_rows[0].get('Work Request #')).split('.')[0])
        
        assert "12345678" in wr_numbers
        assert "87654321" not in wr_numbers  # Exempted
        assert "11111111" in wr_numbers
        assert "22222222" not in wr_numbers  # Exempted
    
    def test_grouping_exempts_all_wrs(self):
        """Test that all WRs can be exempted."""
        rows = [
            self.create_test_row("12345678"),
            self.create_test_row("87654321"),
        ]
        
        exemption_list = {"12345678", "87654321"}  # Exempt all
        groups = group_source_rows(rows, exemption_list=exemption_list)
        
        # Should have 0 groups (all exempted)
        assert len(groups) == 0
    
    def test_grouping_with_decimal_wr_numbers(self):
        """Test that WR numbers with decimals are properly matched."""
        # Smartsheet sometimes returns WR numbers as "12345678.0"
        rows = [
            self.create_test_row("12345678.0"),  # With decimal
            self.create_test_row("87654321"),    # Without decimal
        ]
        
        exemption_list = {"12345678"}  # Exempt without decimal
        groups = group_source_rows(rows, exemption_list=exemption_list)
        
        # Should have 1 group (12345678.0 matched and exempted)
        assert len(groups) == 1
        
        # Verify only 87654321 is present
        wr_numbers = set()
        for group_rows in groups.values():
            wr_numbers.add(str(group_rows[0].get('Work Request #')).split('.')[0])
        
        assert "12345678" not in wr_numbers  # Exempted
        assert "87654321" in wr_numbers
    
    def test_grouping_preserves_multiple_rows_per_wr(self):
        """Test that exemption works correctly when WR has multiple rows."""
        rows = [
            self.create_test_row("12345678"),
            self.create_test_row("12345678"),  # Same WR, different row
            self.create_test_row("12345678"),  # Same WR, another row
            self.create_test_row("87654321"),
            self.create_test_row("87654321"),  # Same WR, different row
        ]
        
        exemption_list = {"12345678"}  # Exempt only first WR
        groups = group_source_rows(rows, exemption_list=exemption_list)
        
        # Should have 1 group (all 12345678 rows exempted)
        assert len(groups) == 1
        
        # Verify 87654321 has 2 rows
        for group_rows in groups.values():
            wr = str(group_rows[0].get('Work Request #')).split('.')[0]
            if wr == "87654321":
                assert len(group_rows) == 2


class TestExemptionIntegration:
    """Integration tests for exemption feature."""
    
    def test_exemption_file_creation(self):
        """Test that the default exemption file can be created and used."""
        test_wrs = ["99999999", "88888888"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "_comment": "Test exemption list",
                "exempted_work_requests": test_wrs
            }, f)
            temp_path = f.name
        
        try:
            # Load the list
            exemption_list = load_exemption_list(temp_path)
            
            # Verify it loaded correctly
            assert len(exemption_list) == 2
            assert "99999999" in exemption_list
            assert "88888888" in exemption_list
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
