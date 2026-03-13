"""
Tests for subcontractor pricing helpers.
Validates load_contract_rates() behavior and SUBCONTRACTOR_SHEET_IDS configuration.
"""

import os
import csv
import tempfile
import unittest
import generate_weekly_pdfs


class TestLoadContractRates(unittest.TestCase):
    """Tests for the load_contract_rates helper function."""

    def test_loads_valid_csv(self):
        """Test loading a well-formed CSV returns correct rate dictionary."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', 'ABC123', 'EA', 'Test Unit', 'Group1', '1', '0.5', '0.3', '$150.00', '$75.00', '$50.00'])
            writer.writerow(['101', 'DEF456', 'LF', 'Another Unit', 'Group2', '2', '1', '0.5', '200', '100', '60'])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_contract_rates(tmp_path)
            self.assertEqual(len(rates), 2)
            self.assertIn('ABC123', rates)
            self.assertIn('DEF456', rates)
            self.assertAlmostEqual(rates['ABC123']['install'], 150.0)
            self.assertAlmostEqual(rates['ABC123']['removal'], 75.0)
            self.assertAlmostEqual(rates['ABC123']['transfer'], 50.0)
            self.assertAlmostEqual(rates['DEF456']['install'], 200.0)
        finally:
            os.unlink(tmp_path)

    def test_missing_file_returns_empty(self):
        """Test that a missing CSV file returns an empty dict gracefully."""
        rates = generate_weekly_pdfs.load_contract_rates('/nonexistent/path.csv')
        self.assertEqual(rates, {})

    def test_empty_csv_returns_empty(self):
        """Test that a CSV with only headers returns an empty dict."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_contract_rates(tmp_path)
            self.assertEqual(len(rates), 0)
        finally:
            os.unlink(tmp_path)

    def test_cu_uppercased(self):
        """Test that CU codes are normalized to uppercase."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', 'abc123', 'EA', 'Test', 'G1', '1', '0', '0', '100', '50', '25'])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_contract_rates(tmp_path)
            self.assertIn('ABC123', rates)
            self.assertNotIn('abc123', rates)
        finally:
            os.unlink(tmp_path)

    def test_handles_invalid_price_values(self):
        """Test that non-numeric price values default to 0.0."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', 'BAD1', 'EA', 'Test', 'G1', '1', '0', '0', 'N/A', '', 'error'])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_contract_rates(tmp_path)
            self.assertIn('BAD1', rates)
            self.assertAlmostEqual(rates['BAD1']['install'], 0.0)
            self.assertAlmostEqual(rates['BAD1']['removal'], 0.0)
            self.assertAlmostEqual(rates['BAD1']['transfer'], 0.0)
        finally:
            os.unlink(tmp_path)

    def test_skips_blank_cu_rows(self):
        """Test that rows with empty CU field are skipped."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', '', 'EA', 'Blank CU', 'G1', '1', '0', '0', '100', '50', '25'])
            writer.writerow(['101', 'VALID', 'EA', 'Valid CU', 'G1', '1', '0', '0', '200', '100', '50'])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_contract_rates(tmp_path)
            self.assertEqual(len(rates), 1)
            self.assertIn('VALID', rates)
        finally:
            os.unlink(tmp_path)

    def test_loads_both_contract_files(self):
        """Test that two separate CSVs load independently with different rates."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f1:
            writer = csv.writer(f1)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', 'CU001', 'EA', 'Original', 'G1', '1', '0', '0', '100.00', '50.00', '25.00'])
            path1 = f1.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f2:
            writer = csv.writer(f2)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', 'CU001', 'EA', 'Reduced', 'G1', '1', '0', '0', '90.00', '45.00', '22.50'])
            path2 = f2.name

        try:
            original = generate_weekly_pdfs.load_contract_rates(path1)
            contractor = generate_weekly_pdfs.load_contract_rates(path2)
            self.assertAlmostEqual(original['CU001']['install'], 100.0)
            self.assertAlmostEqual(contractor['CU001']['install'], 90.0)
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestSubcontractorSheetIdsConfig(unittest.TestCase):
    """Test SUBCONTRACTOR_SHEET_IDS configuration parsing."""

    def test_default_is_empty_list(self):
        """Verify that SUBCONTRACTOR_SHEET_IDS is a list attribute on the module."""
        self.assertIsInstance(generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS, list)

    def test_parse_sheet_ids_skips_invalid(self):
        """Verify _parse_sheet_ids gracefully skips non-integer tokens."""
        result = generate_weekly_pdfs._parse_sheet_ids('123,abc,456,,  789  ')
        self.assertEqual(result, [123, 456, 789])

    def test_parse_sheet_ids_empty_string(self):
        """Verify _parse_sheet_ids returns empty list for empty string."""
        result = generate_weekly_pdfs._parse_sheet_ids('')
        self.assertEqual(result, [])


class TestRevertSubcontractorPrice(unittest.TestCase):
    """Tests for the revert_subcontractor_price helper function."""

    def setUp(self):
        self.rates = {
            'CU-INSTALL': {'install': 100.0, 'removal': 50.0, 'transfer': 30.0},
            'CU-MULTI': {'install': 200.0, 'removal': 80.0, 'transfer': 60.0},
        }

    def test_basic_install_reversion(self):
        """Test that install price is recalculated from original rate × quantity."""
        row = {'CU': 'CU-INSTALL', 'Work Type': 'Install', 'Quantity': '3', 'Units Total Price': '$270.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 300.0)
        self.assertAlmostEqual(row['Units Total Price'], 300.0)

    def test_removal_work_type(self):
        """Test that 'Removal' work type maps to removal rates."""
        row = {'CU': 'CU-INSTALL', 'Work Type': 'Removal', 'Quantity': '2', 'Units Total Price': '$90.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 100.0)

    def test_transfer_work_type(self):
        """Test that 'Transfer' work type maps to transfer rates."""
        row = {'CU': 'CU-INSTALL', 'Work Type': 'Transfer', 'Quantity': '4', 'Units Total Price': '$108.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 120.0)

    def test_xfr_work_type(self):
        """Test that 'xfr' in work type maps to transfer rates."""
        row = {'CU': 'CU-INSTALL', 'Work Type': 'XFR', 'Quantity': '1', 'Units Total Price': '$27.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 30.0)

    def test_cu_helper_preferred_over_cu(self):
        """Test that CU Helper field is preferred over CU field."""
        row = {'CU Helper': 'CU-MULTI', 'CU': 'CU-INSTALL', 'Work Type': 'Install', 'Quantity': '1', 'Units Total Price': '$90.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 200.0)

    def test_nan_cu_helper_falls_back_to_cu(self):
        """Test that NaN CU Helper falls back to CU field."""
        row = {'CU Helper': 'nan', 'CU': 'CU-INSTALL', 'Work Type': 'Install', 'Quantity': '2', 'Units Total Price': '$180.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 200.0)

    def test_unknown_cu_returns_parsed_price(self):
        """Test that unknown CU code returns the original parsed price unchanged."""
        row = {'CU': 'UNKNOWN-CU', 'Work Type': 'Install', 'Quantity': '1', 'Units Total Price': '$55.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 55.0)
        self.assertEqual(row['Units Total Price'], '$55.00')

    def test_zero_quantity(self):
        """Test that zero quantity yields zero price."""
        row = {'CU': 'CU-INSTALL', 'Work Type': 'Install', 'Quantity': '0', 'Units Total Price': '$0.00'}
        result = generate_weekly_pdfs.revert_subcontractor_price(row, self.rates)
        self.assertAlmostEqual(result, 0.0)


if __name__ == '__main__':
    unittest.main()
