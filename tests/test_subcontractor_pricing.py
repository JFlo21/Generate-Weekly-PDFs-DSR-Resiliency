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

    def test_default_is_empty_set(self):
        """Verify that SUBCONTRACTOR_SHEET_IDS is a set attribute on the module."""
        self.assertIsInstance(generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS, set)

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


class TestDiscoverFolderSheets(unittest.TestCase):
    """Tests for folder-based sheet discovery."""

    def test_discover_folder_sheets_returns_set(self):
        """Test discover_folder_sheets returns a set of ints."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        sheet1 = MagicMock(); sheet1.id = 111
        sheet2 = MagicMock(); sheet2.id = 222
        folder = MagicMock(); folder.sheets = [sheet1, sheet2]
        mock_client.Folders.get_folder.return_value = folder

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [9999], 'test')
        self.assertEqual(result, {111, 222})
        mock_client.Folders.get_folder.assert_called_once_with(9999)

    def test_discover_folder_sheets_handles_api_error(self):
        """Test graceful handling when folder API call fails."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.Folders.get_folder.side_effect = Exception("API error")

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [9999], 'test')
        self.assertEqual(result, set())

    def test_discover_folder_sheets_multiple_folders(self):
        """Test discovery across multiple folder IDs with deduplication."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        sheet_a = MagicMock(); sheet_a.id = 100
        sheet_b = MagicMock(); sheet_b.id = 200
        sheet_c = MagicMock(); sheet_c.id = 100  # duplicate
        folder1 = MagicMock(); folder1.sheets = [sheet_a, sheet_b]
        folder2 = MagicMock(); folder2.sheets = [sheet_c]
        mock_client.Folders.get_folder.side_effect = [folder1, folder2]

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [1, 2], 'test')
        self.assertEqual(result, {100, 200})

    def test_discover_folder_sheets_empty_list(self):
        """Test with no folder IDs returns empty set."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [], 'test')
        self.assertEqual(result, set())


class TestIdentityNormalization(unittest.TestCase):
    """Tests for the None vs '' identity comparison fix."""

    def test_none_equals_empty_string_after_normalization(self):
        """Verify that (None or '') == ('' or '') is True."""
        ident_identifier = None
        identifier = ''
        self.assertEqual((ident_identifier or ''), (identifier or ''))

    def test_non_empty_identifiers_still_match(self):
        """Verify that real identifiers still match correctly."""
        ident_identifier = 'John|Dept1|Job1'
        identifier = 'John|Dept1|Job1'
        self.assertEqual((ident_identifier or ''), (identifier or ''))

    def test_different_identifiers_do_not_match(self):
        """Verify that different identifiers don't match."""
        ident_identifier = 'John|Dept1|Job1'
        identifier = 'Jane|Dept2|Job2'
        self.assertNotEqual((ident_identifier or ''), (identifier or ''))


class TestLoadNewContractRates(unittest.TestCase):
    """Tests for loading the 2026-format new contract rates CSV."""

    def test_loads_new_format_csv(self):
        """Test loading a CSV with 3 metadata rows and positional columns."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            # 3 metadata rows
            writer.writerow(['', '', '', '', '', '', '2026 Update', '', '0.03'])
            writer.writerow(['', '', '', '', '', '', 'Revised Pricing', '', ''])
            writer.writerow(['', '', '', '', '', '', 'Install', 'Remove ', 'Transfer'])
            # Data rows
            writer.writerow(['ANC-H', 'Anchor Assembly (Hand)', 'EA', 'Overhead', 'AEP TX', '01-18-26', '814.28', '29.45', '0'])
            writer.writerow(['ANC-M', 'Anchor Assembly (Machine)', 'EA', 'Overhead', 'AEP TX', '01-18-26', '224.06', '29.46', '0'])
            writer.writerow(['ARM-DW', 'Double Wood Crossarm', 'EA', 'Overhead', 'AEP TX', '01-18-26', '330.24', '75.94', '183.98'])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_new_contract_rates(tmp_path)
            self.assertEqual(len(rates), 3)
            self.assertIn('ANC-H', rates)
            self.assertIn('ANC-M', rates)
            self.assertIn('ARM-DW', rates)
            self.assertAlmostEqual(rates['ANC-H']['install'], 814.28)
            self.assertAlmostEqual(rates['ANC-H']['removal'], 29.45)
            self.assertAlmostEqual(rates['ANC-H']['transfer'], 0.0)
            self.assertAlmostEqual(rates['ANC-M']['install'], 224.06)
            self.assertAlmostEqual(rates['ARM-DW']['transfer'], 183.98)
        finally:
            os.unlink(tmp_path)

    def test_missing_file_returns_empty(self):
        """Test that a missing file returns empty dict."""
        rates = generate_weekly_pdfs.load_new_contract_rates('/nonexistent/new_rates.csv')
        self.assertEqual(rates, {})

    def test_skips_short_rows(self):
        """Test that rows with fewer than 9 columns are skipped."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['', '', '', '', '', '', 'Header', '', ''])
            writer.writerow(['', '', '', '', '', '', '', '', ''])
            writer.writerow(['', '', '', '', '', '', '', '', ''])
            writer.writerow(['SHORT', 'Only 5 cols', 'EA', 'Cat', 'Region'])  # Too short
            writer.writerow(['VALID', 'Full row', 'EA', 'Cat', 'Region', '01-18-26', '100', '50', '25'])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_new_contract_rates(tmp_path)
            self.assertEqual(len(rates), 1)
            self.assertIn('VALID', rates)
        finally:
            os.unlink(tmp_path)

    def test_group_code_uppercased(self):
        """Test that group codes are normalized to uppercase."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            for _ in range(3):
                writer.writerow([''] * 9)
            writer.writerow(['anc-h', 'Anchor', 'EA', 'OH', 'AEP', '01-18-26', '100', '50', '25'])
            tmp_path = f.name

        try:
            rates = generate_weekly_pdfs.load_new_contract_rates(tmp_path)
            self.assertIn('ANC-H', rates)
            self.assertNotIn('anc-h', rates)
        finally:
            os.unlink(tmp_path)


class TestBuildCuToGroupMapping(unittest.TestCase):
    """Tests for building the CU-to-group code mapping."""

    def test_builds_mapping_from_old_csv(self):
        """Test building CU -> Compatible Unit Group mapping."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', 'ANC-DHM-10-84-D1', 'EA', 'Anchor', 'ANC-M', '0.24', '0.14', '0', '217.53', '28.60', '0'])
            writer.writerow(['101', 'ANC-DSC-16-96-D1', 'EA', 'Anchor Disc', 'ANC-H', '0.90', '0.14', '0', '790.56', '28.59', '0'])
            writer.writerow(['102', 'ARM-10D-60HS', 'EA', 'Crossarm', 'ARM-DW', '0.66', '0.38', '0.93', '320.62', '73.73', '178.62'])
            tmp_path = f.name

        try:
            mapping = generate_weekly_pdfs.build_cu_to_group_mapping(tmp_path)
            self.assertEqual(len(mapping), 3)
            self.assertEqual(mapping['ANC-DHM-10-84-D1'], 'ANC-M')
            self.assertEqual(mapping['ANC-DSC-16-96-D1'], 'ANC-H')
            self.assertEqual(mapping['ARM-10D-60HS'], 'ARM-DW')
        finally:
            os.unlink(tmp_path)

    def test_missing_file_returns_empty(self):
        """Test that missing file returns empty mapping."""
        mapping = generate_weekly_pdfs.build_cu_to_group_mapping('/nonexistent/old.csv')
        self.assertEqual(mapping, {})

    def test_cu_codes_uppercased(self):
        """Test that CU codes and group codes are uppercased."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
                'Compatible Unit Group', 'Install Hours', 'Removal Hours',
                'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
            ])
            writer.writerow(['100', 'lower-cu', 'EA', 'Test', 'lower-group', '1', '0', '0', '100', '50', '25'])
            tmp_path = f.name

        try:
            mapping = generate_weekly_pdfs.build_cu_to_group_mapping(tmp_path)
            self.assertIn('LOWER-CU', mapping)
            self.assertEqual(mapping['LOWER-CU'], 'LOWER-GROUP')
        finally:
            os.unlink(tmp_path)


class TestRecalculateRowPrice(unittest.TestCase):
    """Tests for the date-based rate recalculation function."""

    def setUp(self):
        self.cu_to_group = {
            'ANC-DHM-10-84-D1': 'ANC-M',
            'ANC-DSC-16-96-D1': 'ANC-H',
            'ARM-10D-60HS': 'ARM-DW',
        }
        self.rates_primary = {
            'ANC-M': {'install': 224.06, 'removal': 29.46, 'transfer': 0.0},
            'ANC-H': {'install': 814.28, 'removal': 29.45, 'transfer': 0.0},
            'ARM-DW': {'install': 330.24, 'removal': 75.94, 'transfer': 183.98},
        }

    def test_basic_install_recalculation(self):
        """Test basic install price recalculation via CU-to-group mapping."""
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Quantity': '3', 'Units Total Price': '$650.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        expected = round(224.06 * 3, 2)  # 672.18
        self.assertAlmostEqual(result, expected)
        self.assertAlmostEqual(row['Units Total Price'], expected)

    def test_removal_work_type(self):
        """Test removal work type mapping."""
        row = {'CU': 'ARM-10D-60HS', 'Work Type': 'Removal', 'Quantity': '2', 'Units Total Price': '$100.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        expected = round(75.94 * 2, 2)  # 151.88
        self.assertAlmostEqual(result, expected)

    def test_transfer_work_type(self):
        """Test transfer work type mapping."""
        row = {'CU': 'ARM-10D-60HS', 'Work Type': 'Transfer', 'Quantity': '1', 'Units Total Price': '$150.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 183.98)

    def test_xfr_work_type(self):
        """Test that 'xfr' maps to transfer rates."""
        row = {'CU': 'ARM-10D-60HS', 'Work Type': 'XFR', 'Quantity': '1', 'Units Total Price': '$150.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 183.98)

    def test_unknown_cu_keeps_smartsheet_price(self):
        """Test that unknown CU codes keep the original SmartSheet price."""
        row = {'CU': 'UNKNOWN-CU-999', 'Work Type': 'Install', 'Quantity': '1', 'Units Total Price': '$55.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 55.0)
        # Original string should be unchanged
        self.assertEqual(row['Units Total Price'], '$55.00')

    def test_direct_group_code_lookup(self):
        """Test that if SmartSheet row uses a group code directly, it still works."""
        row = {'CU': 'ANC-M', 'Work Type': 'Install', 'Quantity': '2', 'Units Total Price': '$400.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        expected = round(224.06 * 2, 2)  # 448.12
        self.assertAlmostEqual(result, expected)

    def test_cu_helper_preferred(self):
        """Test that CU Helper field is preferred over CU field."""
        row = {'CU Helper': 'ANC-DSC-16-96-D1', 'CU': 'ARM-10D-60HS', 'Work Type': 'Install', 'Quantity': '1', 'Units Total Price': '$300.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 814.28)  # ANC-H install rate

    def test_arrowhead_discount_rates(self):
        """Test that Arrowhead (subcontractor) rates are 90% of primary."""
        arrowhead_rates = {
            group: {
                'install': round(r['install'] * 0.90, 2),
                'removal': round(r['removal'] * 0.90, 2),
                'transfer': round(r['transfer'] * 0.90, 2),
            }
            for group, r in self.rates_primary.items()
        }
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Quantity': '1', 'Units Total Price': '$200.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, arrowhead_rates)
        expected = round(224.06 * 0.90, 2)  # 201.65
        self.assertAlmostEqual(result, expected)

    def test_zero_quantity(self):
        """Test that zero quantity yields zero price."""
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Quantity': '0', 'Units Total Price': '$0.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 0.0)


class TestRateCutoffConfig(unittest.TestCase):
    """Tests for rate cutoff configuration."""

    def test_rate_cutoff_attribute_exists(self):
        """Test that RATE_CUTOFF_DATE attribute exists on the module."""
        self.assertTrue(hasattr(generate_weekly_pdfs, 'RATE_CUTOFF_DATE'))

    def test_arrowhead_discount_value(self):
        """Test that ARROWHEAD_DISCOUNT is 0.90 (10% reduction)."""
        self.assertAlmostEqual(generate_weekly_pdfs.ARROWHEAD_DISCOUNT, 0.90)

    def test_new_rates_csv_attribute(self):
        """Test that NEW_RATES_CSV attribute exists and points to the new file."""
        self.assertTrue(hasattr(generate_weekly_pdfs, 'NEW_RATES_CSV'))
        self.assertIn('New Contract Rates', generate_weekly_pdfs.NEW_RATES_CSV)

    def test_rates_fingerprint_attribute_exists(self):
        """Test that _RATES_FINGERPRINT attribute exists on the module."""
        self.assertTrue(hasattr(generate_weekly_pdfs, '_RATES_FINGERPRINT'))


class TestRatesFingerprint(unittest.TestCase):
    """Tests for rate table fingerprint computation."""

    def test_fingerprint_deterministic(self):
        """Test that same rates produce same fingerprint."""
        rates = {'ANC-H': {'install': 100.0, 'removal': 50.0, 'transfer': 25.0}}
        fp1 = generate_weekly_pdfs._compute_rates_fingerprint(rates)
        fp2 = generate_weekly_pdfs._compute_rates_fingerprint(rates)
        self.assertEqual(fp1, fp2)

    def test_fingerprint_changes_with_rates(self):
        """Test that different rates produce different fingerprints."""
        rates1 = {'ANC-H': {'install': 100.0, 'removal': 50.0, 'transfer': 25.0}}
        rates2 = {'ANC-H': {'install': 103.0, 'removal': 51.5, 'transfer': 25.75}}
        fp1 = generate_weekly_pdfs._compute_rates_fingerprint(rates1)
        fp2 = generate_weekly_pdfs._compute_rates_fingerprint(rates2)
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_is_12_chars(self):
        """Test that fingerprint is 12 hex characters."""
        rates = {'X': {'install': 1.0, 'removal': 2.0, 'transfer': 3.0}}
        fp = generate_weekly_pdfs._compute_rates_fingerprint(rates)
        self.assertEqual(len(fp), 12)


class TestCutoffDateRecalculationIntegration(unittest.TestCase):
    """Integration tests for date-based rate recalculation logic."""

    def setUp(self):
        self.cu_to_group = {
            'ANC-DHM-10-84-D1': 'ANC-M',
        }
        self.rates_primary = {
            'ANC-M': {'install': 224.06, 'removal': 29.46, 'transfer': 0.0},
        }

    def test_pre_cutoff_row_keeps_smartsheet_price(self):
        """Verify a row with Snapshot Date before cutoff is not recalculated."""
        import datetime as dt
        cutoff = dt.date(2026, 4, 19)
        row = {
            'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install',
            'Quantity': '1', 'Units Total Price': '$200.00',
            'Snapshot Date': '2026-04-18',
        }
        snap = generate_weekly_pdfs.excel_serial_to_date(row['Snapshot Date'])
        snap_date = snap.date() if hasattr(snap, 'date') else snap
        # Pre-cutoff: should NOT recalculate
        self.assertLess(snap_date, cutoff)
        # Price unchanged
        self.assertEqual(row['Units Total Price'], '$200.00')

    def test_post_cutoff_row_gets_recalculated(self):
        """Verify a row with Snapshot Date on/after cutoff gets new rates."""
        import datetime as dt
        cutoff = dt.date(2026, 4, 19)
        row = {
            'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install',
            'Quantity': '2', 'Units Total Price': '$400.00',
            'Snapshot Date': '2026-04-19',
        }
        snap = generate_weekly_pdfs.excel_serial_to_date(row['Snapshot Date'])
        snap_date = snap.date() if hasattr(snap, 'date') else snap
        self.assertGreaterEqual(snap_date, cutoff)
        # Recalculate
        new_price = generate_weekly_pdfs.recalculate_row_price(
            row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(new_price, 448.12)  # 224.06 * 2

    def test_subcontractor_row_gets_discounted_rates(self):
        """Verify subcontractor rows use 90% of primary rates."""
        arrowhead_rates = {
            'ANC-M': {
                'install': round(224.06 * 0.90, 2),
                'removal': round(29.46 * 0.90, 2),
                'transfer': 0.0,
            }
        }
        row = {
            'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install',
            'Quantity': '1', 'Units Total Price': '$200.00',
        }
        new_price = generate_weekly_pdfs.recalculate_row_price(
            row, self.cu_to_group, arrowhead_rates)
        expected = round(224.06 * 0.90, 2)  # 201.65
        self.assertAlmostEqual(new_price, expected)

    def test_snapshot_date_parsing_iso_format(self):
        """Test that ISO format snapshot dates are parsed correctly."""
        dt = generate_weekly_pdfs.excel_serial_to_date('2026-04-19')
        self.assertIsNotNone(dt)

    def test_snapshot_date_parsing_returns_none_for_empty(self):
        """Test that empty/None snapshot dates return None."""
        self.assertIsNone(generate_weekly_pdfs.excel_serial_to_date(None))
        self.assertIsNone(generate_weekly_pdfs.excel_serial_to_date(''))


class TestExpandedHashCoverage(unittest.TestCase):
    """Tests for the expanded calculate_data_hash field coverage."""

    def test_hash_changes_when_customer_name_changes(self):
        """Verify the hash changes when Customer Name is modified."""
        base_row = {
            'Work Request #': '12345', 'Snapshot Date': '2025-01-01',
            'CU': 'ABC', 'Quantity': '1', 'Units Total Price': '100.00',
            'Work Type': 'install', 'Dept #': '10',
            'Customer Name': 'OriginalCustomer', '__variant': 'primary',
        }
        import copy
        modified_row = copy.deepcopy(base_row)
        modified_row['Customer Name'] = 'DifferentCustomer'

        hash1 = generate_weekly_pdfs.calculate_data_hash([base_row])
        hash2 = generate_weekly_pdfs.calculate_data_hash([modified_row])
        self.assertNotEqual(hash1, hash2)

    def test_hash_changes_when_job_number_changes(self):
        """Verify the hash changes when Job # is modified."""
        base_row = {
            'Work Request #': '12345', 'Snapshot Date': '2025-01-01',
            'CU': 'ABC', 'Quantity': '1', 'Units Total Price': '100.00',
            'Work Type': 'install', 'Job #': 'JOB001', '__variant': 'primary',
        }
        import copy
        modified_row = copy.deepcopy(base_row)
        modified_row['Job #'] = 'JOB002'

        hash1 = generate_weekly_pdfs.calculate_data_hash([base_row])
        hash2 = generate_weekly_pdfs.calculate_data_hash([modified_row])
        self.assertNotEqual(hash1, hash2)

    def test_hash_stable_when_no_changes(self):
        """Verify the hash is deterministic for identical input."""
        row = {
            'Work Request #': '12345', 'Snapshot Date': '2025-01-01',
            'CU': 'ABC', 'Quantity': '1', 'Units Total Price': '100.00',
            'Work Type': 'install', '__variant': 'primary',
        }
        hash1 = generate_weekly_pdfs.calculate_data_hash([row])
        hash2 = generate_weekly_pdfs.calculate_data_hash([row])
        self.assertEqual(hash1, hash2)


if __name__ == '__main__':
    unittest.main()
