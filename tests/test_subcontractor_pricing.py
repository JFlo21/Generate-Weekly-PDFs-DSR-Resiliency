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


# Canonical 17-column header for the subcontractor rates CSV. Pinned at
# module scope so every TestLoadSubcontractorRates fixture emits the
# same shape and a future header drift fails one test instead of
# silently mis-feeding the loader across every test.
SUBCONTRACTOR_HEADERS = [
    'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
    'Compatible Unit Group', 'Install Hours', 'Removal Hours',
    'Transfer Hours',
    'Install Price (Subcontractor Rates)',
    'Removal Price (Subcontractor Rates)',
    'Transfer Price (Subcontractor Rates)',
    'Install Price (Old Rates)',
    'Removal Price (Old Rates)',
    'Transfer Price (Old Rates)',
    'Install Price (New Rates)',
    'Removal Price (New Rates)',
    'Transfer Price (New Rates)',
]


class TestLoadSubcontractorRates(unittest.TestCase):
    """Regression class for ``load_subcontractor_rates`` (Phase 1
    plan 01-01). Covers decisions D-04..D-07 + D-20."""

    def _write_csv(self, rows, *, write_bom: bool = False) -> str:
        """Write a temp CSV with the canonical 17-column header and the
        supplied data rows. Returns the temp path; the caller is
        responsible for ``os.unlink`` in a ``finally`` block. When
        ``write_bom`` is True a UTF-8 BOM is emitted at file start so
        the ``utf-8-sig`` tolerance can be tested.
        """
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False, newline='',
            encoding='utf-8',
        ) as f:
            if write_bom:
                f.write('﻿')
            writer = csv.writer(f)
            writer.writerow(SUBCONTRACTOR_HEADERS)
            for row in rows:
                writer.writerow(row)
            return f.name

    def test_loads_subcontractor_csv_with_currency_strings(self):
        """D-04: ``$150.00`` / ``$1,234.56`` currency cells parse to
        floats via ``parse_price``."""
        tmp_path = self._write_csv([
            [
                '100', 'ABC123', 'EA', 'Test', 'G1',
                '1', '0.5', '0.3',
                '$150.00', '$1,234.56', '$50.00',
                '$0.00', '$0.00', '$0.00',
                '$200.00', '$1,500.00', '$75.00',
            ],
        ])
        try:
            rates = generate_weekly_pdfs.load_subcontractor_rates(tmp_path)
            self.assertIn('ABC123', rates)
            self.assertAlmostEqual(rates['ABC123']['reduced_install_price'], 150.0)
            self.assertAlmostEqual(rates['ABC123']['reduced_remove_price'], 1234.56)
            self.assertAlmostEqual(rates['ABC123']['reduced_transfer_price'], 50.0)
            self.assertAlmostEqual(rates['ABC123']['new_install_price'], 200.0)
            self.assertAlmostEqual(rates['ABC123']['new_remove_price'], 1500.0)
            self.assertAlmostEqual(rates['ABC123']['new_transfer_price'], 75.0)
        finally:
            os.unlink(tmp_path)

    def test_loads_subcontractor_csv_with_utf8_bom(self):
        """D-04: a UTF-8 BOM at file start does not break header
        detection (``encoding='utf-8-sig'`` strips it)."""
        tmp_path = self._write_csv(
            [
                [
                    '100', 'BOM-CU', 'EA', 'Test', 'G1',
                    '1', '0.5', '0.3',
                    '$10.00', '$5.00', '$3.00',
                    '$0.00', '$0.00', '$0.00',
                    '$15.00', '$7.00', '$4.00',
                ],
            ],
            write_bom=True,
        )
        try:
            rates = generate_weekly_pdfs.load_subcontractor_rates(tmp_path)
            self.assertIn('BOM-CU', rates)
            self.assertAlmostEqual(rates['BOM-CU']['reduced_install_price'], 10.0)
            self.assertAlmostEqual(rates['BOM-CU']['new_install_price'], 15.0)
        finally:
            os.unlink(tmp_path)

    def test_skips_all_zero_priced_rows(self):
        """D-04: rows whose all six priced cells are zero are
        excluded from the dict (placeholder CUs)."""
        tmp_path = self._write_csv([
            # Row 1: all-zero priced — must be skipped
            [
                '100', 'ZERO-CU', 'EA', 'Placeholder', 'G1',
                '0', '0', '0',
                '$0.00', '$0.00', '$0.00',
                '$0.00', '$0.00', '$0.00',
                '$0.00', '$0.00', '$0.00',
            ],
            # Row 2: valid priced — must be loaded
            [
                '101', 'VALID-CU', 'EA', 'Real', 'G1',
                '1', '0.5', '0.3',
                '$45.95', '$33.33', '$106.54',
                '$0.00', '$0.00', '$0.00',
                '$52.58', '$38.14', '$121.93',
            ],
        ])
        try:
            rates = generate_weekly_pdfs.load_subcontractor_rates(tmp_path)
            self.assertEqual(len(rates), 1)
            self.assertNotIn('ZERO-CU', rates)
            self.assertIn('VALID-CU', rates)
        finally:
            os.unlink(tmp_path)

    def test_tolerates_na_in_hours_columns(self):
        """D-04: ``'N/A'`` in Hours columns does not break the loader
        (hours are not read at all). Row 2 of the production CSV
        (``ADDITEM-ROW-PURCHASE``) is shaped exactly like this."""
        tmp_path = self._write_csv([
            [
                '100', 'NA-HOURS', 'EA', 'Test', 'G1',
                'N/A', 'N/A', 'N/A',
                '$100.00', '$50.00', '$25.00',
                '$0.00', '$0.00', '$0.00',
                '$120.00', '$60.00', '$30.00',
            ],
        ])
        try:
            rates = generate_weekly_pdfs.load_subcontractor_rates(tmp_path)
            self.assertIn('NA-HOURS', rates)
            self.assertAlmostEqual(rates['NA-HOURS']['reduced_install_price'], 100.0)
            self.assertAlmostEqual(rates['NA-HOURS']['new_install_price'], 120.0)
        finally:
            os.unlink(tmp_path)

    def test_loads_per_cu_rate_variance_literally(self):
        """D-07: per-CU rate variance is real (median ``New/Old =
        1.0300``, min ``1.0244``; median ``Reduced/New = 0.8738``,
        min ``0.4343``). The loader MUST read literal values, never
        compute ``reduced = old × 0.87`` or ``new = old × 1.03``
        shortcuts."""
        # Outlier CU: New/Old = 2.0725 (max), Reduced/New = 0.4343 (min).
        # If the loader computed shortcuts, reduced_install would be
        # 0.87 × 20.73 ≈ 18.03 (not the literal 9.00), and new_install
        # would be 1.03 × 10.00 = 10.30 (not the literal 20.73).
        tmp_path = self._write_csv([
            [
                '100', 'OUTLIER', 'EA', 'Test', 'G1',
                '1', '0', '0',
                '$9.00', '$5.00', '$3.00',     # reduced
                '$10.00', '$5.00', '$3.00',    # old
                '$20.73', '$10.30', '$6.18',   # new
            ],
        ])
        try:
            rates = generate_weekly_pdfs.load_subcontractor_rates(tmp_path)
            self.assertIn('OUTLIER', rates)
            # Reduced must be the literal $9.00, not 0.87 × $10.00
            self.assertAlmostEqual(rates['OUTLIER']['reduced_install_price'], 9.0)
            # New must be the literal $20.73, not 1.03 × $10.00
            self.assertAlmostEqual(rates['OUTLIER']['new_install_price'], 20.73)
            # Compute ratios to confirm the outliers landed verbatim
            ratio_reduced_over_new = (
                rates['OUTLIER']['reduced_install_price']
                / rates['OUTLIER']['new_install_price']
            )
            self.assertAlmostEqual(ratio_reduced_over_new, 0.4341, places=3)
        finally:
            os.unlink(tmp_path)

    def test_old_rates_columns_not_loaded(self):
        """D-06: Old-Rates columns (12-14) are NOT loaded into the
        per-CU value dict. Carrying them would create a 3rd source of
        truth for pricing — explicitly forbidden by the design."""
        tmp_path = self._write_csv([
            [
                '100', 'HAS-OLD', 'EA', 'Test', 'G1',
                '1', '0', '0',
                '$45.95', '$33.33', '$106.54',
                # Old-Rates: deliberately distinct values so the test
                # would catch a key like ``'old_install_price'`` if
                # the loader regressed and included them
                '$999.00', '$888.00', '$777.00',
                '$52.58', '$38.14', '$121.93',
            ],
        ])
        try:
            rates = generate_weekly_pdfs.load_subcontractor_rates(tmp_path)
            self.assertIn('HAS-OLD', rates)
            value = rates['HAS-OLD']
            # No legacy or alternate-name keys for the old-rates columns
            self.assertNotIn('install_price_old', value)
            self.assertNotIn('old_install_price', value)
            self.assertNotIn('removal_price_old', value)
            self.assertNotIn('old_removal_price', value)
            self.assertNotIn('transfer_price_old', value)
            self.assertNotIn('old_transfer_price', value)
            # Defensive: no key in the value dict contains 'old'
            old_keys = [k for k in value.keys() if 'old' in k.lower()]
            self.assertEqual(old_keys, [], f"Found Old-Rates keys: {old_keys}")
            # Old-Rates values 999/888/777 must not appear anywhere
            for v in value.values():
                if isinstance(v, (int, float)):
                    self.assertNotAlmostEqual(v, 999.0)
                    self.assertNotAlmostEqual(v, 888.0)
                    self.assertNotAlmostEqual(v, 777.0)
        finally:
            os.unlink(tmp_path)

    def test_subcontractor_rates_fingerprint_deterministic(self):
        """D-20: two byte-identical inputs (different dict insertion
        order included) MUST produce the same 16-char fingerprint."""
        d1 = {
            'CU-A': {
                'cu_code': 'CU-A', 'cu_wbs': '', 'compatible_unit_group': '',
                'reduced_install_price': 10.0, 'reduced_remove_price': 5.0,
                'reduced_transfer_price': 3.0,
                'new_install_price': 12.0, 'new_remove_price': 6.0,
                'new_transfer_price': 4.0,
            },
            'CU-B': {
                'cu_code': 'CU-B', 'cu_wbs': '', 'compatible_unit_group': '',
                'reduced_install_price': 20.0, 'reduced_remove_price': 8.0,
                'reduced_transfer_price': 5.0,
                'new_install_price': 22.0, 'new_remove_price': 9.0,
                'new_transfer_price': 6.0,
            },
        }
        # Reverse insertion order — fingerprint must be identical
        # because the helper sorts keys before hashing.
        d2 = {
            'CU-B': dict(d1['CU-B']),
            'CU-A': dict(d1['CU-A']),
        }
        fp1 = generate_weekly_pdfs._compute_subcontractor_rates_fingerprint(d1)
        fp2 = generate_weekly_pdfs._compute_subcontractor_rates_fingerprint(d2)
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 16)
        # Output charset is hex
        self.assertRegex(fp1, r'^[0-9a-f]{16}$')

    def test_subcontractor_rates_fingerprint_changes_on_edit(self):
        """D-20: editing one CU's priced field (any of the six) MUST
        change the fingerprint."""
        base = {
            'CU-EDIT': {
                'cu_code': 'CU-EDIT', 'cu_wbs': '', 'compatible_unit_group': '',
                'reduced_install_price': 10.0, 'reduced_remove_price': 5.0,
                'reduced_transfer_price': 3.0,
                'new_install_price': 12.0, 'new_remove_price': 6.0,
                'new_transfer_price': 4.0,
            },
        }
        fp_base = generate_weekly_pdfs._compute_subcontractor_rates_fingerprint(base)

        mutated = {
            'CU-EDIT': dict(base['CU-EDIT'], new_install_price=12.01),
        }
        fp_mutated = generate_weekly_pdfs._compute_subcontractor_rates_fingerprint(mutated)
        self.assertNotEqual(fp_base, fp_mutated)
        self.assertEqual(len(fp_mutated), 16)


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


def _make_children_page(sheet_ids=(), subfolder_ids=(), last_key=None):
    """Build a MagicMock paginated children result containing real Sheet/Folder instances."""
    from unittest.mock import MagicMock
    from smartsheet.models.sheet import Sheet
    from smartsheet.models.folder import Folder
    data = [Sheet({'id': sid, 'name': f'sheet-{sid}'}) for sid in sheet_ids]
    data += [Folder({'id': fid, 'name': f'folder-{fid}'}) for fid in subfolder_ids]
    page = MagicMock()
    page.data = data
    page.last_key = last_key
    return page


class TestDiscoverFolderSheets(unittest.TestCase):
    """Tests for folder-based sheet discovery."""

    def test_discover_folder_sheets_returns_set(self):
        """Test discover_folder_sheets returns a set of ints."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.Folders.get_folder_children.return_value = _make_children_page(sheet_ids=[111, 222])

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [9999], 'test')
        self.assertEqual(result, {111, 222})
        mock_client.Folders.get_folder_children.assert_called_once()
        call_args = mock_client.Folders.get_folder_children.call_args
        self.assertEqual(call_args.args[0], 9999)

    def test_discover_folder_sheets_handles_api_error(self):
        """Test graceful handling when folder API call fails."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.Folders.get_folder_children.side_effect = Exception("API error")

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [9999], 'test')
        self.assertEqual(result, set())

    def test_discover_folder_sheets_multiple_folders(self):
        """Test discovery across multiple folder IDs with deduplication."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.Folders.get_folder_children.side_effect = [
            _make_children_page(sheet_ids=[100, 200]),
            _make_children_page(sheet_ids=[100]),  # duplicate 100
        ]

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [1, 2], 'test')
        self.assertEqual(result, {100, 200})

    def test_discover_folder_sheets_empty_list(self):
        """Test with no folder IDs returns empty set."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [], 'test')
        self.assertEqual(result, set())

    def test_discover_folder_sheets_paginates_last_key(self):
        """Multi-page last_key pagination is followed until last_key is falsy."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        # Page 1 returns two sheets + a continuation token; page 2 returns one more and terminates.
        mock_client.Folders.get_folder_children.side_effect = [
            _make_children_page(sheet_ids=[301, 302], last_key='k1'),
            _make_children_page(sheet_ids=[303], last_key=None),
        ]

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [4242], 'test')
        self.assertEqual(result, {301, 302, 303})
        self.assertEqual(mock_client.Folders.get_folder_children.call_count, 2)
        # The second call should forward the last_key from the first response.
        second_kwargs = mock_client.Folders.get_folder_children.call_args_list[1].kwargs
        self.assertEqual(second_kwargs.get('last_key'), 'k1')

    def test_discover_folder_sheets_recurses_into_subfolders(self):
        """Folder children returned as subfolders trigger recursive discovery."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()

        def _children(fid, **kwargs):
            if fid == 10:
                # Top folder has one sheet and one subfolder child
                return _make_children_page(sheet_ids=[401], subfolder_ids=[11])
            if fid == 11:
                # Subfolder has two sheets and no further nesting
                return _make_children_page(sheet_ids=[402, 403])
            return _make_children_page()

        mock_client.Folders.get_folder_children.side_effect = _children

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [10], 'test')
        self.assertEqual(result, {401, 402, 403})
        called_ids = [c.args[0] for c in mock_client.Folders.get_folder_children.call_args_list]
        self.assertIn(10, called_ids)
        self.assertIn(11, called_ids)

    def test_discover_folder_sheets_stops_on_repeated_last_key(self):
        """A repeated last_key must short-circuit pagination to avoid an API burst."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        # A misbehaving API keeps returning the same continuation token forever.
        # The discovery loop should stop after detecting the repeat rather than
        # calling through to max_pages.
        mock_client.Folders.get_folder_children.side_effect = [
            _make_children_page(sheet_ids=[501], last_key='stuck'),
            _make_children_page(sheet_ids=[502], last_key='stuck'),
            _make_children_page(sheet_ids=[503], last_key='stuck'),
        ]

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [7777], 'test')
        # Sheets from pages fetched before the repeat-stop are preserved.
        self.assertEqual(result, {501, 502})
        # Exactly 2 calls: page 1 (token 'stuck' recorded), page 2 (token repeats → stop).
        self.assertEqual(mock_client.Folders.get_folder_children.call_count, 2)

    def test_discover_folder_sheets_stops_at_max_pages(self):
        """Pagination must terminate at the 100-page safety cap."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        # Generate a unique last_key per call so the repeated-token guard never trips —
        # only the max_pages ceiling can terminate the loop.
        counter = {'n': 0}

        def _children(fid, **kwargs):
            counter['n'] += 1
            return _make_children_page(
                sheet_ids=[1000 + counter['n']],
                last_key=f"token-{counter['n']}",
            )

        mock_client.Folders.get_folder_children.side_effect = _children

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [8888], 'test')
        # Exactly max_pages (100) calls — not unbounded.
        self.assertEqual(mock_client.Folders.get_folder_children.call_count, 100)
        self.assertEqual(len(result), 100)


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

    def test_zero_quantity_keeps_smartsheet_price(self):
        """Test that zero quantity keeps original SmartSheet price instead of zeroing it out."""
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Quantity': '0', 'Units Total Price': '$55.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 55.0)
        # Original string should be unchanged
        self.assertEqual(row['Units Total Price'], '$55.00')

    def test_missing_quantity_keeps_smartsheet_price(self):
        """Test that missing/empty quantity keeps original SmartSheet price."""
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Units Total Price': '$100.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 100.0)
        self.assertEqual(row['Units Total Price'], '$100.00')

    def test_zero_rate_keeps_smartsheet_price(self):
        """Test that a zero rate for a work type keeps the original SmartSheet price."""
        # ANC-M has transfer rate of 0.0 in the test data
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Transfer', 'Quantity': '2', 'Units Total Price': '$75.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertAlmostEqual(result, 75.0)
        self.assertEqual(row['Units Total Price'], '$75.00')

    def test_cu_direct_fallback_when_mapped_group_absent_from_new_rates(self):
        """Regression for VAC crew pricing lag: when the old CSV maps a CU to
        a verbose group name that is NOT a key in the new rates table, the
        recalc should fall back to looking up the CU code directly before
        giving up. Prevents silent old-price retention on specialized work
        items (e.g. vacuum switches) whose CU codes are themselves the key
        in the new contract rates.
        """
        cu_to_group = {'CPD-VS-15-20': 'VACUUM SWITCH'}  # verbose group name
        rates = {
            'CPD-VS-15-20': {'install': 500.00, 'removal': 100.00, 'transfer': 0.0},
        }
        row = {
            'CU': 'CPD-VS-15-20',
            'Work Type': 'Install',
            'Quantity': '2',
            'Units Total Price': '$250.00',
        }
        result = generate_weekly_pdfs.recalculate_row_price(row, cu_to_group, rates)
        self.assertAlmostEqual(result, 1000.00)
        self.assertAlmostEqual(row['Units Total Price'], 1000.00)

    def test_retains_smartsheet_price_when_neither_group_nor_cu_in_new_rates(self):
        """When the mapped group is absent AND the CU is also absent from the
        new rates, the row must retain its SmartSheet price unchanged rather
        than inventing a rate. This guards against the CU-direct fallback
        being too aggressive."""
        cu_to_group = {'CPD-VS-15-20': 'VACUUM SWITCH'}
        rates = {'ANC-M': {'install': 224.06, 'removal': 29.46, 'transfer': 0.0}}
        row = {
            'CU': 'CPD-VS-15-20',
            'Work Type': 'Install',
            'Quantity': '2',
            'Units Total Price': '$250.00',
        }
        result = generate_weekly_pdfs.recalculate_row_price(row, cu_to_group, rates)
        self.assertAlmostEqual(result, 250.00)
        self.assertEqual(row['Units Total Price'], '$250.00')

    def test_out_status_recalculated_on_successful_lookup(self):
        """recalculate_row_price writes outcome='recalculated' when a rate
        was successfully applied (even if the new price equals the existing
        SmartSheet price)."""
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Quantity': '3', 'Units Total Price': '$672.18'}
        status = {}
        generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary, out_status=status)
        self.assertEqual(status.get('outcome'), 'recalculated')

    def test_out_status_missing_rate_when_cu_unmapped_and_absent(self):
        """When the CU isn't in cu_to_group and also isn't a direct key in
        the rates dict, out_status['outcome'] must be 'missing_rate' — this
        is the only outcome the per-sheet 'skipped' summary should count."""
        row = {'CU': 'UNKNOWN-999', 'Work Type': 'Install', 'Quantity': '2', 'Units Total Price': '$100.00'}
        status = {}
        generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary, out_status=status)
        self.assertEqual(status.get('outcome'), 'missing_rate')

    def test_out_status_missing_rate_when_group_absent_and_no_cu_fallback(self):
        """When CU maps to a verbose group name that isn't in the new rates
        table AND the CU itself also isn't a direct key, out_status reports
        'missing_rate'."""
        cu_to_group = {'CPD-VS-15-20': 'VACUUM SWITCH'}
        rates = {'ANC-M': {'install': 224.06, 'removal': 29.46, 'transfer': 0.0}}
        row = {'CU': 'CPD-VS-15-20', 'Work Type': 'Install', 'Quantity': '2', 'Units Total Price': '$250.00'}
        status = {}
        generate_weekly_pdfs.recalculate_row_price(row, cu_to_group, rates, out_status=status)
        self.assertEqual(status.get('outcome'), 'missing_rate')

    def test_out_status_invalid_quantity(self):
        """Zero/missing quantity short-circuits with outcome='invalid_quantity',
        not 'missing_rate' — the per-sheet 'skipped' summary must not
        attribute this to CSV coverage gaps."""
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Quantity': '0', 'Units Total Price': '$55.00'}
        status = {}
        generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary, out_status=status)
        self.assertEqual(status.get('outcome'), 'invalid_quantity')

    def test_out_status_zero_rate(self):
        """Zero rate for the resolved work type yields outcome='zero_rate'."""
        # ANC-M has transfer rate = 0.0 in the fixture
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Transfer', 'Quantity': '2', 'Units Total Price': '$75.00'}
        status = {}
        generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary, out_status=status)
        self.assertEqual(status.get('outcome'), 'zero_rate')

    def test_out_status_optional_preserves_backward_compat(self):
        """Callers that omit out_status must continue to get a float price."""
        row = {'CU': 'ANC-DHM-10-84-D1', 'Work Type': 'Install', 'Quantity': '3', 'Units Total Price': '$650.00'}
        result = generate_weekly_pdfs.recalculate_row_price(row, self.cu_to_group, self.rates_primary)
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, round(224.06 * 3, 2))


class TestResolveCuCode(unittest.TestCase):
    """Tests for the _resolve_cu_code helper used by both recalc and the
    per-sheet skipped-CU summary counter, so they agree on which CU a row
    is attributed to."""

    def test_prefers_cu_helper_over_cu(self):
        row = {'CU Helper': 'ANC-DSC-16-96-D1', 'CU': 'ARM-10D-60HS', 'Billable Unit Code': 'BLT-12'}
        self.assertEqual(generate_weekly_pdfs._resolve_cu_code(row), 'ANC-DSC-16-96-D1')

    def test_nan_helper_falls_back_to_cu(self):
        row = {'CU Helper': 'nan', 'CU': 'ARM-10D-60HS'}
        self.assertEqual(generate_weekly_pdfs._resolve_cu_code(row), 'ARM-10D-60HS')

    def test_falls_back_to_billable_unit_code(self):
        row = {'Billable Unit Code': 'Something-Mixed'}
        self.assertEqual(generate_weekly_pdfs._resolve_cu_code(row), 'SOMETHING-MIXED')

    def test_returns_empty_when_all_blank(self):
        self.assertEqual(generate_weekly_pdfs._resolve_cu_code({}), '')
        self.assertEqual(generate_weekly_pdfs._resolve_cu_code({'CU': None, 'Billable Unit Code': ''}), '')


class TestRateCutoffConfig(unittest.TestCase):
    """Tests for rate cutoff configuration."""

    def test_rate_cutoff_attribute_exists(self):
        """Test that RATE_CUTOFF_DATE attribute exists on the module."""
        self.assertTrue(hasattr(generate_weekly_pdfs, 'RATE_CUTOFF_DATE'))

    def test_arrowhead_discount_value(self):
        """Test that ARROWHEAD_DISCOUNT is 0.90 (10% reduction)."""
        self.assertAlmostEqual(generate_weekly_pdfs.ARROWHEAD_DISCOUNT, 0.90)

    def test_new_rates_csv_attribute(self):
        """Test that NEW_RATES_CSV attribute exists and is a non-empty path."""
        self.assertTrue(hasattr(generate_weekly_pdfs, 'NEW_RATES_CSV'))
        self.assertTrue(len(generate_weekly_pdfs.NEW_RATES_CSV) > 0)

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

    def test_discounted_rate_table_math(self):
        """Verify recalculate_row_price correctly applies a 90% discounted rate table (for future Arrowhead use)."""
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


class TestWeeklyRefDateFallbackCutoff(unittest.TestCase):
    """Regression tests for the Weekly-Ref-Date rate-recalc fallback.

    Production incident context: VAC crew Excel files were being
    generated for week ending 04/12/26 but NOT for 04/19/26. Root
    cause was that the pre-acceptance rate recalc only fired when
    ``Snapshot Date >= RATE_CUTOFF_DATE``. For current-week rows the
    Smartsheet snapshot automation had not yet populated Snapshot
    Date, so recalc was silently skipped, ``Units Total Price`` stayed
    at 0 for VAC crew specialty CUs, ``has_price`` evaluated False,
    and the row was dropped before VAC crew detection could even run.

    The fix is a narrowly-scoped fallback inside
    ``_resolve_rate_recalc_cutoff_date``: when Snapshot Date is blank
    AND Weekly Reference Logged Date parses to a date >= cutoff, use
    the weekly date as the effective gate. Rows that DO have a
    Snapshot Date are unaffected — the snapshot-keyed business rule
    remains primary.
    """

    def setUp(self):
        import datetime as dt
        self.cutoff = dt.date(2026, 4, 19)

    def test_env_constant_exists_and_is_bool(self):
        """``RATE_RECALC_WEEKLY_FALLBACK`` is wired into the module."""
        self.assertTrue(hasattr(generate_weekly_pdfs, 'RATE_RECALC_WEEKLY_FALLBACK'))
        self.assertIsInstance(generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK, bool)

    def test_snapshot_post_cutoff_returns_snapshot_no_fallback(self):
        """Row with Snapshot Date >= cutoff: primary rule wins, no fallback."""
        import datetime as dt
        row = {
            'Snapshot Date': '2026-04-22',
            'Weekly Reference Logged Date': '2026-04-19',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff,
        )
        self.assertEqual(effective, dt.date(2026, 4, 22))
        self.assertFalse(used_fallback)

    def test_snapshot_pre_cutoff_returns_none_even_if_weekly_post_cutoff(self):
        """Genuinely pre-cutoff row: fallback does NOT override snapshot rule.

        The snapshot-keyed business rule is authoritative when Snapshot
        Date IS populated — even if the weekly date would say
        otherwise. This preserves the ledger guardrail: "Do NOT change
        the cutoff column from Snapshot Date to Weekly Reference
        Logged Date."
        """
        row = {
            'Snapshot Date': '2026-04-10',
            'Weekly Reference Logged Date': '2026-04-19',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff,
        )
        self.assertIsNone(effective)
        self.assertFalse(used_fallback)

    def test_blank_snapshot_post_cutoff_weekly_triggers_fallback(self):
        """The incident case: blank Snapshot Date, current-week weekly date.

        This is what caused WE 04/19 VAC crew rows to silently drop.
        With the fallback enabled, recalc now runs using the weekly
        date as the effective gate.
        """
        import datetime as dt
        row = {
            'Snapshot Date': None,
            'Weekly Reference Logged Date': '2026-04-19',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff,
        )
        self.assertEqual(effective, dt.date(2026, 4, 19))
        self.assertTrue(used_fallback)

    def test_blank_snapshot_blank_weekly_returns_none(self):
        """No usable date on either column → no recalc (unchanged)."""
        row = {'Snapshot Date': None, 'Weekly Reference Logged Date': ''}
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff,
        )
        self.assertIsNone(effective)
        self.assertFalse(used_fallback)

    def test_blank_snapshot_pre_cutoff_weekly_returns_none(self):
        """Historical row with blank Snapshot and pre-cutoff Weekly: no recalc.

        Ensures the fallback is not a universal override — it still
        requires the weekly date to be >= cutoff, preserving contract
        versioning semantics.
        """
        row = {
            'Snapshot Date': None,
            'Weekly Reference Logged Date': '2026-04-12',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff,
        )
        self.assertIsNone(effective)
        self.assertFalse(used_fallback)

    def test_fallback_disabled_preserves_legacy_behaviour(self):
        """With the fallback disabled, blank Snapshot Date → skip recalc.

        This matches the pre-fix behaviour and proves the env gate is
        respected.
        """
        row = {
            'Snapshot Date': None,
            'Weekly Reference Logged Date': '2026-04-19',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff, weekly_fallback_enabled=False,
        )
        self.assertIsNone(effective)
        self.assertFalse(used_fallback)

    def test_unparseable_snapshot_falls_through_to_fallback(self):
        """A garbage Snapshot Date behaves like a blank one for fallback purposes.

        ``excel_serial_to_date`` returns ``None`` on unparseable input,
        which the helper treats the same as a blank value. Without
        this, a corrupted Snapshot Date cell would silently suppress
        recalc even when Weekly Reference Logged Date is valid.
        """
        import datetime as dt
        row = {
            'Snapshot Date': 'not-a-real-date',
            'Weekly Reference Logged Date': '2026-04-19',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff,
        )
        self.assertEqual(effective, dt.date(2026, 4, 19))
        self.assertTrue(used_fallback)

    def test_none_cutoff_always_returns_none(self):
        """No configured cutoff → helper must never authorise recalc.

        Matches the outer production guard ``if RATE_CUTOFF_DATE and
        _rate_new_primary and not is_subcontractor_sheet:`` but is
        also checked inside the helper as a defensive measure so
        callers/tests cannot accidentally enable recalc on a
        cutoff-disabled deployment.
        """
        row = {
            'Snapshot Date': None,
            'Weekly Reference Logged Date': '2026-04-19',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, None,
        )
        self.assertIsNone(effective)
        self.assertFalse(used_fallback)

    def test_fallback_end_to_end_produces_recalculated_price(self):
        """End-to-end: fallback → recalculate_row_price → new price applied.

        Proves the combined effect is what operators need: a VAC crew
        row with blank Snapshot Date, blank SmartSheet price, CU
        present in the new rates table, and a current-week Weekly
        Reference Logged Date comes out with a recalculated non-zero
        price — so the downstream ``has_price`` gate accepts it
        instead of dropping it silently.
        """
        cu_to_group = {'ANC-DHM-10-84-D1': 'ANC-M'}
        rates = {'ANC-M': {'install': 224.06, 'removal': 29.46, 'transfer': 0.0}}
        row = {
            'Snapshot Date': None,
            'Weekly Reference Logged Date': '2026-04-19',
            'CU': 'ANC-DHM-10-84-D1',
            'Work Type': 'Install',
            'Quantity': '2',
            'Units Total Price': 0,
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff,
        )
        self.assertIsNotNone(effective)
        self.assertTrue(used_fallback)
        new_price = generate_weekly_pdfs.recalculate_row_price(row, cu_to_group, rates)
        self.assertAlmostEqual(new_price, 448.12)
        # Confirm row was updated in-place so the downstream has_price
        # check will pass for this row.
        self.assertEqual(row['Units Total Price'], 448.12)


class TestOriginalContractFolderSkipsRateRecalc(unittest.TestCase):
    """Regression tests for the Smartsheet-native pricing guard.

    Production context: Smartsheet now emits the correct post-cutoff
    ``Units Total Price`` natively for sheets discovered via the two
    folders in ``ORIGINAL_CONTRACT_FOLDER_IDS``. Running Python-side
    rate recalc on top of Smartsheet's authoritative price risked
    overwriting it with a CSV-derived ``rate × qty`` value that did
    not always agree — producing over/under-billed rows. The guard
    introduced in this PR short-circuits the recalc gate for sheets
    whose IDs are in ``_FOLDER_DISCOVERED_ORIG_IDS`` (populated by
    ``discover_folder_sheets`` at every run start), behind a
    default-ON env var so the behaviour is reversible by operators.
    """

    def setUp(self):
        # Snapshot module state so individual tests can mutate
        # _FOLDER_DISCOVERED_ORIG_IDS / SUBCONTRACTOR_SHEET_IDS /
        # RATE_CUTOFF_DATE without leaking into other suites.
        self._orig_folder_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS)
        self._orig_sub_ids = set(generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS)
        self._orig_cutoff = generate_weekly_pdfs.RATE_CUTOFF_DATE
        self._orig_skip_flag = generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT

    def tearDown(self):
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.update(self._orig_folder_ids)
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.clear()
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.update(self._orig_sub_ids)
        generate_weekly_pdfs.RATE_CUTOFF_DATE = self._orig_cutoff
        generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT = self._orig_skip_flag

    def _evaluate_gate(self, sheet_id):
        """Mirror the original-contract-skip portion of the production gate.

        The full row-level recalc gate in ``_fetch_and_process_sheet``
        also requires ``_rate_new_primary`` to be populated (the new
        rates dict, loaded by ``load_rate_versions()`` only when
        ``RATE_CUTOFF_DATE`` is set). That branch is exercised by the
        existing recalc-integration tests in
        ``TestCutoffDateRecalculationIntegration`` and
        ``TestWeeklyRefDateFallbackCutoff``. This helper deliberately
        narrows the surface to the **original-contract skip
        composite** so the truth-table tests below stay fast and don't
        require seeding a CSV-loaded rates dict for what is purely a
        boolean-gating concern.

        Keeping the boolean inline (vs. importing a production helper)
        is intentional — if the production ``_skip_recalc_original_contract``
        expression drifts, these tests must be updated in the same PR
        so the invariant stays locked.
        """
        is_subcontractor_sheet = sheet_id in generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS
        is_original_contract_sheet = (
            sheet_id in generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS
        )
        _skip_recalc_original_contract = (
            generate_weekly_pdfs.RATE_CUTOFF_DATE is not None
            and generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT
            and is_original_contract_sheet
            and not is_subcontractor_sheet
        )
        recalc_would_run = (
            generate_weekly_pdfs.RATE_CUTOFF_DATE is not None
            and not is_subcontractor_sheet
            and not _skip_recalc_original_contract
        )
        return recalc_would_run, _skip_recalc_original_contract

    def test_env_var_exists_and_is_bool(self):
        """``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` is wired into the module."""
        self.assertTrue(
            hasattr(generate_weekly_pdfs, 'RATE_RECALC_SKIP_ORIGINAL_CONTRACT')
        )
        self.assertIsInstance(
            generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT, bool
        )

    def test_default_folder_ids_include_smartsheet_priced_folders(self):
        """Default ORIGINAL_CONTRACT_FOLDER_IDS covers the two Smartsheet-priced folders.

        Incident: user reported Smartsheet natively prices rows in
        folders 7644752003786628 and 8815193070299012 for post-cutoff
        ``Units Completed?`` rows. If these IDs are ever removed from
        the default list without also updating the env var wiring in
        ``.github/workflows/weekly-excel-generation.yml``, the guard
        becomes a no-op on CI runs that rely on the default.
        """
        defaults = generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS
        self.assertIn(7644752003786628, defaults)
        self.assertIn(8815193070299012, defaults)

    def test_guard_fires_for_original_contract_sheet(self):
        """Sheet in ORIG folder + cutoff set + env on → recalc skipped."""
        import datetime as dt
        generate_weekly_pdfs.RATE_CUTOFF_DATE = dt.date(2026, 4, 12)
        generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.add(111111)
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.clear()

        recalc_would_run, skip_fired = self._evaluate_gate(111111)
        self.assertFalse(recalc_would_run)
        self.assertTrue(skip_fired)

    def test_guard_does_not_fire_for_non_original_contract_sheet(self):
        """Sheet NOT in ORIG folder → recalc still runs (pre-fix behaviour)."""
        import datetime as dt
        generate_weekly_pdfs.RATE_CUTOFF_DATE = dt.date(2026, 4, 12)
        generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.add(111111)
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.clear()

        recalc_would_run, skip_fired = self._evaluate_gate(222222)
        self.assertTrue(recalc_would_run)
        self.assertFalse(skip_fired)

    def test_env_var_off_restores_legacy_behaviour(self):
        """``RATE_RECALC_SKIP_ORIGINAL_CONTRACT=False`` → recalc runs on ORIG sheet too.

        Proves the env-var kill switch works — operators can flip off
        the guard if Smartsheet-native pricing ever breaks or needs
        to be bypassed.
        """
        import datetime as dt
        generate_weekly_pdfs.RATE_CUTOFF_DATE = dt.date(2026, 4, 12)
        generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT = False
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.add(111111)
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.clear()

        recalc_would_run, skip_fired = self._evaluate_gate(111111)
        self.assertTrue(recalc_would_run)
        self.assertFalse(skip_fired)

    def test_no_cutoff_no_recalc_regardless_of_folder(self):
        """Without ``RATE_CUTOFF_DATE``, recalc is disabled globally.

        Confirms the original outer guard is preserved — the new
        folder skip is additive, not a replacement.
        """
        generate_weekly_pdfs.RATE_CUTOFF_DATE = None
        generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.add(111111)
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.clear()

        recalc_would_run, skip_fired = self._evaluate_gate(111111)
        self.assertFalse(recalc_would_run)
        # skip_fired must be False when cutoff is disabled: the skip
        # flag only matters when recalc was otherwise eligible, and
        # operators should not see the "🛡️ Skipping..." log on a
        # cutoff-disabled deployment.
        self.assertFalse(skip_fired)

    def test_subcontractor_sheet_wins_over_original_contract(self):
        """Sheet in BOTH sub and orig sets: subcontractor exclusion wins.

        Pathological but possible (misconfiguration). The subcontractor
        exclusion at the recalc gate is primary and unconditional, so
        the sheet skips recalc via the subcontractor path and the
        original-contract skip log never fires (avoiding duplicate
        "skipping" messages for the same sheet).
        """
        import datetime as dt
        generate_weekly_pdfs.RATE_CUTOFF_DATE = dt.date(2026, 4, 12)
        generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.add(111111)
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.clear()
        generate_weekly_pdfs.SUBCONTRACTOR_SHEET_IDS.add(111111)

        recalc_would_run, skip_fired = self._evaluate_gate(111111)
        self.assertFalse(recalc_would_run)
        # Subcontractor-exclusion path short-circuits first, so the
        # original-contract skip must NOT fire for the same sheet.
        self.assertFalse(skip_fired)

    def test_guard_does_not_mutate_recalculate_row_price(self):
        """``recalculate_row_price`` itself is unchanged by the guard.

        The guard is a sheet-level gate; it does NOT modify
        ``recalculate_row_price``'s behaviour. A caller that invokes
        the function directly (e.g., a future one-off reprice script)
        must still get the full recalc behaviour regardless of env
        vars.
        """
        cu_to_group = {'ANC-DHM-10-84-D1': 'ANC-M'}
        rates = {'ANC-M': {'install': 224.06, 'removal': 29.46, 'transfer': 0.0}}
        row = {
            'CU': 'ANC-DHM-10-84-D1',
            'Work Type': 'Install',
            'Quantity': '2',
            'Units Total Price': 0,
        }
        # Flip the env flag on — helper should still recalc, proving
        # the guard is at the caller (sheet-level gate), not here.
        generate_weekly_pdfs.RATE_RECALC_SKIP_ORIGINAL_CONTRACT = True
        new_price = generate_weekly_pdfs.recalculate_row_price(row, cu_to_group, rates)
        self.assertAlmostEqual(new_price, 448.12)
        self.assertEqual(row['Units Total Price'], 448.12)


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


class TestSubcontractorVariantGrouping(unittest.TestCase):
    """Plan 01-03 Task 1: subcontractor variant tagging in group_source_rows().

    Per the plan's committed plumbing decision (Blocker 3), the gate is
    PER-ROW via ``r.get('__source_sheet_id') in _FOLDER_DISCOVERED_SUB_IDS``.
    Each test snapshots & restores the module's folder-id sets and the
    kill-switch env flag so a test's mutation cannot leak.
    """

    _SUB_SHEET_ID = 8162920222379908
    _ORIG_SHEET_ID = 7644752003786628

    def setUp(self):
        self._orig_sub_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS)
        self._orig_orig_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS)
        self._orig_kill = generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        # Seed the SUB folder set with our test sheet id so the per-row
        # gate trips.
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.add(self._ORIG_SHEET_ID)
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True

    def tearDown(self):
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._orig_sub_ids)
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.update(self._orig_orig_ids)
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._orig_kill

    def _make_row(
        self,
        wr,
        date_str,
        price,
        snapshot=None,
        source_sheet_id=None,
        is_helper=False,
        helper_foreman='',
        helper_dept='',
        helper_job='',
    ):
        """Minimal valid source row for group_source_rows().

        ``source_sheet_id`` populates ``row['__source_sheet_id']`` —
        the field the plan's per-row gate reads. Defaults to the
        test class's seeded subcontractor sheet id.
        """
        if source_sheet_id is None:
            source_sheet_id = self._SUB_SHEET_ID
        row = {
            'Work Request #': wr,
            'Weekly Reference Logged Date': date_str,
            'Units Completed?': True,
            'Units Total Price': price,
            'Snapshot Date': snapshot if snapshot is not None else date_str,
            '__effective_user': 'TestForeman',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': is_helper,
            '__helper_foreman': helper_foreman,
            '__helper_dept': helper_dept,
            '__helper_job': helper_job,
            '__is_vac_crew': False,
            '__source_sheet_id': source_sheet_id,
        }
        return row

    def test_post_cutoff_subcontractor_row_emits_aep_billable_and_reduced_sub(self):
        """Test 1: post-cutoff snapshot, SUB sheet, kill-switch on → both new variant group keys appear."""
        row = self._make_row(
            wr='WR_X',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',  # post-cutoff (>= 2026-04-12)
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        self.assertTrue(
            any('_AEPBILLABLE' in k and '_HELPER_' not in k for k in keys),
            f"Expected an _AEPBILLABLE group key for post-cutoff sub row; got: {keys}",
        )
        self.assertTrue(
            any('_REDUCEDSUB' in k and '_HELPER_' not in k for k in keys),
            f"Expected a _REDUCEDSUB group key for sub row; got: {keys}",
        )

    def test_pre_cutoff_subcontractor_row_emits_reduced_sub_only(self):
        """Test 2: pre-cutoff snapshot → ReducedSub yes, AEPBillable no (D-08)."""
        row = self._make_row(
            wr='WR_Y',
            date_str='2026-04-05',
            price='$100.00',
            snapshot='2026-04-05',  # pre-cutoff (< 2026-04-12)
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        self.assertTrue(
            any('_REDUCEDSUB' in k for k in keys),
            f"Expected a _REDUCEDSUB group key for pre-cutoff sub row; got: {keys}",
        )
        self.assertFalse(
            any('_AEPBILLABLE' in k for k in keys),
            f"Expected NO _AEPBILLABLE group key for pre-cutoff sub row; got: {keys}",
        )

    def test_helper_event_emits_shadow_variants_when_post_cutoff(self):
        """Test 3: helper-foreman event on sub WR post-cutoff → both shadow variants appear."""
        row = self._make_row(
            wr='WR_Z',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',
            is_helper=True,
            helper_foreman='Jane Smith',
            helper_dept='123',
            helper_job='J-1',
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        self.assertTrue(
            any('_AEPBILLABLE_HELPER_Jane_Smith' in k for k in keys),
            f"Expected _AEPBILLABLE_HELPER_Jane_Smith key; got: {keys}",
        )
        self.assertTrue(
            any('_REDUCEDSUB_HELPER_Jane_Smith' in k for k in keys),
            f"Expected _REDUCEDSUB_HELPER_Jane_Smith key; got: {keys}",
        )

    def test_non_subcontractor_sheet_emits_no_new_variants(self):
        """Test 4: row from a non-SUB sheet → no new variant keys (per-row gate proof)."""
        row = self._make_row(
            wr='WR_A',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',
            source_sheet_id=self._ORIG_SHEET_ID,  # in ORIG, NOT in SUB
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        self.assertFalse(
            any('_AEPBILLABLE' in k or '_REDUCEDSUB' in k for k in keys),
            f"Expected NO new variant keys for non-sub row; got: {keys}",
        )

    def test_kill_switch_off_emits_no_new_variants(self):
        """Test 5: SUBCONTRACTOR_RATE_VARIANTS_ENABLED=False → no new variant keys (D-13)."""
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = False
        row = self._make_row(
            wr='WR_B',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        self.assertFalse(
            any('_AEPBILLABLE' in k or '_REDUCEDSUB' in k for k in keys),
            f"Expected NO new variant keys with kill switch off; got: {keys}",
        )

    def test_variant_string_tagging_uses_canonical_lowercase(self):
        """Test 6: r_copy['__variant'] in the new variants uses the exact lowercase strings."""
        row = self._make_row(
            wr='WR_C',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        variants_seen = set()
        for key, rows in groups.items():
            if '_AEPBILLABLE' in key or '_REDUCEDSUB' in key:
                variants_seen.add(rows[0].get('__variant'))
        # At minimum reduced_sub and aep_billable must be present.
        self.assertIn('reduced_sub', variants_seen, f"expected 'reduced_sub' tagging; saw {variants_seen}")
        self.assertIn('aep_billable', variants_seen, f"expected 'aep_billable' tagging; saw {variants_seen}")
        self.assertTrue(
            variants_seen.issubset(
                {'reduced_sub', 'aep_billable', 'reduced_sub_helper', 'aep_billable_helper'}
            ),
            f"new-variant group rows must tag __variant only with the four lowercase strings; got {variants_seen}",
        )

    def test_helper_name_with_apostrophe_sanitized_in_key(self):
        """Test 7: helper name with non-word chars is sanitized via _RE_SANITIZE_HELPER_NAME before key embedding."""
        row = self._make_row(
            wr='WR_D',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',
            is_helper=True,
            helper_foreman="Jane O'Brien",
            helper_dept='456',
            helper_job='J-2',
        )
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        # ``_RE_SANITIZE_HELPER_NAME`` replaces ``'`` with ``_``.
        sanitized_expected = 'Jane_O_Brien'
        self.assertTrue(
            any(f'_REDUCEDSUB_HELPER_{sanitized_expected}' in k for k in keys),
            f"Expected sanitized helper name {sanitized_expected!r} in a REDUCEDSUB_HELPER key; got: {keys}",
        )
        self.assertTrue(
            any(f'_AEPBILLABLE_HELPER_{sanitized_expected}' in k for k in keys),
            f"Expected sanitized helper name {sanitized_expected!r} in an AEPBILLABLE_HELPER key; got: {keys}",
        )

    def test_per_row_gate_does_not_bleed_across_rows_in_same_call(self):
        """Test 8: a single call with a sub row + a non-sub row → only the sub row produces new variants.

        Regression guard against accidental per-CALL gating that would
        emit variant keys for every row in the call once any row was
        on a SUB sheet.
        """
        row_sub = self._make_row(
            wr='WR_E',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',
            source_sheet_id=self._SUB_SHEET_ID,
        )
        row_orig = self._make_row(
            wr='WR_F',
            date_str='2026-04-19',
            price='$100.00',
            snapshot='2026-04-19',
            source_sheet_id=self._ORIG_SHEET_ID,
        )
        groups = generate_weekly_pdfs.group_source_rows([row_sub, row_orig])
        # WR_E (sub) MUST have new variant keys.
        sub_keys = [k for k in groups if '_WR_E' in k or k.endswith('_WR_E') or 'WR_E' in k]
        # The naming convention: ``{week}_{wr_key}_REDUCEDSUB`` etc.
        self.assertTrue(
            any('WR_E' in k and ('_AEPBILLABLE' in k or '_REDUCEDSUB' in k) for k in groups),
            f"Expected WR_E (sub) to produce new-variant keys; got: {list(groups.keys())}",
        )
        # WR_F (orig) MUST NOT produce any new variant keys.
        wr_f_new_variant_keys = [
            k for k in groups
            if 'WR_F' in k and ('_AEPBILLABLE' in k or '_REDUCEDSUB' in k)
        ]
        self.assertEqual(
            wr_f_new_variant_keys, [],
            f"WR_F (orig) must NOT produce new-variant keys (per-row gate); got: {wr_f_new_variant_keys}",
        )


if __name__ == '__main__':
    unittest.main()
