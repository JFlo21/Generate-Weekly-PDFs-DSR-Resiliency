"""
Tests for VAC Crew Promax sheet support.
Validates VAC_CREW_SHEET_IDS configuration, folder discovery, grouping, and
filename identity parsing for the vac_crew variant.
"""

import os
import unittest
from unittest.mock import MagicMock, patch
import generate_weekly_pdfs


class TestVacCrewSheetIdsConfig(unittest.TestCase):
    """Test VAC_CREW_SHEET_IDS module attribute and _parse_sheet_ids integration."""

    def test_vac_crew_sheet_ids_is_set(self):
        """Verify that VAC_CREW_SHEET_IDS is a set attribute on the module."""
        self.assertIsInstance(generate_weekly_pdfs.VAC_CREW_SHEET_IDS, set)

    def test_vac_crew_folder_ids_is_list(self):
        """Verify that VAC_CREW_FOLDER_IDS is a list attribute on the module."""
        self.assertIsInstance(generate_weekly_pdfs.VAC_CREW_FOLDER_IDS, list)

    def test_vac_crew_sheet_ids_default_empty(self):
        """Verify VAC_CREW_SHEET_IDS is empty by default (no env var set)."""
        # The module was imported without VAC_CREW_SHEET_IDS env var set
        # so it should be empty unless the env var was provided externally.
        env_val = os.getenv('VAC_CREW_SHEET_IDS', '')
        if not env_val.strip():
            self.assertEqual(len(generate_weekly_pdfs.VAC_CREW_SHEET_IDS), 0)

    def test_vac_crew_folder_ids_default_empty(self):
        """Verify VAC_CREW_FOLDER_IDS is empty by default (no env var set)."""
        env_val = os.getenv('VAC_CREW_FOLDER_IDS', '')
        if not env_val.strip():
            self.assertEqual(len(generate_weekly_pdfs.VAC_CREW_FOLDER_IDS), 0)


class TestVacCrewFolderDiscovery(unittest.TestCase):
    """Tests for VAC Crew folder-based sheet discovery using discover_folder_sheets."""

    def test_vac_crew_folder_discovery_returns_ids(self):
        """discover_folder_sheets returns correct sheet IDs for vac_crew label."""
        mock_client = MagicMock()
        sheet_a = MagicMock()
        sheet_a.id = 5001
        sheet_b = MagicMock()
        sheet_b.id = 5002
        folder = MagicMock()
        folder.sheets = [sheet_a, sheet_b]
        mock_client.Folders.get_folder.return_value = folder

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [8888], 'vac crew')
        self.assertEqual(result, {5001, 5002})
        mock_client.Folders.get_folder.assert_called_once_with(8888)

    def test_vac_crew_folder_discovery_multiple_folders(self):
        """discover_folder_sheets merges IDs across multiple VAC Crew folder IDs."""
        mock_client = MagicMock()

        def _get_folder(fid):
            folder = MagicMock()
            if fid == 1111:
                s = MagicMock()
                s.id = 5001
                folder.sheets = [s]
            else:
                s = MagicMock()
                s.id = 5002
                folder.sheets = [s]
            return folder

        mock_client.Folders.get_folder.side_effect = _get_folder

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [1111, 2222], 'vac crew')
        self.assertEqual(result, {5001, 5002})

    def test_vac_crew_folder_discovery_empty_folder_list(self):
        """discover_folder_sheets returns empty set when no folder IDs provided."""
        mock_client = MagicMock()
        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [], 'vac crew')
        self.assertEqual(result, set())
        mock_client.Folders.get_folder.assert_not_called()

    def test_vac_crew_folder_discovery_api_error_graceful(self):
        """discover_folder_sheets handles API errors gracefully for vac_crew folders."""
        mock_client = MagicMock()
        mock_client.Folders.get_folder.side_effect = Exception("Smartsheet API error")

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [9999], 'vac crew')
        self.assertEqual(result, set())


class TestVacCrewGroupIdentityParsing(unittest.TestCase):
    """Tests for build_group_identity() recognising the VacCrew filename marker."""

    def test_vac_crew_filename_parsed_as_vac_crew_variant(self):
        """build_group_identity returns vac_crew variant for VacCrew filenames."""
        fname = 'WR_90093002_WeekEnding_081725_163045_VacCrew_a4d1aae7ccf82b3e.xlsx'
        result = generate_weekly_pdfs.build_group_identity(fname)
        self.assertIsNotNone(result)
        wr, week, variant, identifier = result
        self.assertEqual(wr, '90093002')
        self.assertEqual(week, '081725')
        self.assertEqual(variant, 'vac_crew')
        self.assertEqual(identifier, '')

    def test_primary_filename_not_affected(self):
        """build_group_identity still returns primary for standard filenames."""
        fname = 'WR_90093002_WeekEnding_081725_163045_a4d1aae7ccf82b3e.xlsx'
        result = generate_weekly_pdfs.build_group_identity(fname)
        self.assertIsNotNone(result)
        wr, week, variant, identifier = result
        self.assertEqual(variant, 'primary')

    def test_helper_filename_not_affected(self):
        """build_group_identity still returns helper for Helper filenames."""
        fname = 'WR_90093002_WeekEnding_081725_163045_Helper_JohnSmith_a4d1aae7ccf82b3e.xlsx'
        result = generate_weekly_pdfs.build_group_identity(fname)
        self.assertIsNotNone(result)
        wr, week, variant, identifier = result
        self.assertEqual(variant, 'helper')
        self.assertEqual(identifier, 'JohnSmith')

    def test_vac_crew_identity_does_not_match_primary(self):
        """VAC Crew identity tuple is distinct from primary identity tuple for same WR/week."""
        fname_vac = 'WR_90093002_WeekEnding_081725_163045_VacCrew_aabbccdd11223344.xlsx'
        fname_primary = 'WR_90093002_WeekEnding_081725_163045_aabbccdd11223344.xlsx'
        ident_vac = generate_weekly_pdfs.build_group_identity(fname_vac)
        ident_primary = generate_weekly_pdfs.build_group_identity(fname_primary)
        self.assertIsNotNone(ident_vac)
        self.assertIsNotNone(ident_primary)
        self.assertNotEqual(ident_vac, ident_primary)


class TestVacCrewGroupingLogic(unittest.TestCase):
    """Tests for group_source_rows() VAC Crew variant grouping."""

    def _make_row(self, wr, date_str, price, is_vac_crew=False, is_helper=False):
        """Build a minimal valid source row for grouping tests."""
        row = {
            'Work Request #': wr,
            'Weekly Reference Logged Date': date_str,
            'Units Completed?': True,
            'Units Total Price': price,
            '__effective_user': 'TestForeman',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': is_helper,
            '__helper_foreman': '',
            '__is_vac_crew': is_vac_crew,
        }
        return row

    def test_vac_crew_rows_produce_vac_crew_variant(self):
        """Rows flagged __is_vac_crew=True produce groups with variant='vac_crew'."""
        rows = [self._make_row('12345678', '2025-08-17', '$100.00', is_vac_crew=True)]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertTrue(len(groups) > 0, "Expected at least one group")
        for key, group_rows in groups.items():
            variant = group_rows[0].get('__variant')
            self.assertEqual(variant, 'vac_crew', f"Expected vac_crew variant for key '{key}'")
            self.assertIn('_VACCREW', key)

    def test_vac_crew_key_format(self):
        """VAC Crew group key ends with _VACCREW."""
        rows = [self._make_row('99887766', '2025-08-17', '$200.00', is_vac_crew=True)]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        keys = list(groups.keys())
        self.assertTrue(any(k.endswith('_VACCREW') for k in keys),
                        f"Expected a key ending with _VACCREW; got: {keys}")

    def test_non_vac_crew_rows_produce_primary_variant(self):
        """Rows NOT flagged as VAC Crew produce primary groups, unaffected by VAC Crew logic."""
        rows = [self._make_row('11223344', '2025-08-17', '$150.00', is_vac_crew=False)]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertTrue(len(groups) > 0)
        for key, group_rows in groups.items():
            variant = group_rows[0].get('__variant')
            self.assertNotEqual(variant, 'vac_crew')
            self.assertNotIn('_VACCREW', key)

    def test_vac_crew_and_primary_rows_produce_separate_groups(self):
        """VAC Crew and primary rows for the same WR/week go into separate groups."""
        wr = '55667788'
        date = '2025-08-17'
        rows = [
            self._make_row(wr, date, '$100.00', is_vac_crew=True),
            self._make_row(wr, date, '$200.00', is_vac_crew=False),
        ]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertGreaterEqual(len(groups), 2, "Expected separate groups for vac_crew and primary")
        variants = {group_rows[0].get('__variant') for group_rows in groups.values()}
        self.assertIn('vac_crew', variants)
        self.assertIn('primary', variants)

    def test_vac_crew_group_created_log_fires_once_per_group(self):
        """'VAC CREW GROUP CREATED' should log info only on the first row of each group.

        Multiple VAC Crew rows sharing the same WR+week must not produce duplicate
        info-level log messages — only the first row creates the group; the rest
        add to an existing group and should log at debug level only.
        """
        wr = '11112222'
        date = '2025-08-17'
        rows = [
            self._make_row(wr, date, '$50.00', is_vac_crew=True),
            self._make_row(wr, date, '$75.00', is_vac_crew=True),
            self._make_row(wr, date, '$25.00', is_vac_crew=True),
        ]
        with self.assertLogs('root', level='INFO') as log_ctx:
            groups = generate_weekly_pdfs.group_source_rows(rows)

        vaccrew_created_msgs = [
            m for m in log_ctx.output
            if 'VAC CREW GROUP CREATED' in m and 'INFO' in m
        ]
        self.assertEqual(
            len(vaccrew_created_msgs), 1,
            f"Expected exactly 1 info-level 'VAC CREW GROUP CREATED' message for "
            f"3 rows in the same group; got {len(vaccrew_created_msgs)}: {vaccrew_created_msgs}"
        )
        vaccrew_key = [k for k in groups if '_VACCREW' in k]
        self.assertEqual(len(vaccrew_key), 1)
        self.assertEqual(len(groups[vaccrew_key[0]]), 3)

    def test_vac_crew_completed_unit_checkbox_flags_row_as_vac_crew(self):
        """A row with 'Vac Crew Completed Unit?' checked is grouped as vac_crew even when
        __is_vac_crew was not set by the sheet-ID check (simulates the column-based path)."""
        row = {
            'Work Request #': '77665544',
            'Weekly Reference Logged Date': '2025-08-17',
            'Units Completed?': True,
            'Vac Crew Completed Unit?': True,
            'Units Total Price': '$120.00',
            '__effective_user': 'VacCrewForeman',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            # __is_vac_crew set as True here (as get_all_source_rows would set it)
            '__is_vac_crew': True,
        }
        groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertTrue(len(groups) > 0)
        keys = list(groups.keys())
        self.assertTrue(any('_VACCREW' in k for k in keys),
                        f"Expected _VACCREW group key; got: {keys}")
        for key, group_rows in groups.items():
            self.assertEqual(group_rows[0].get('__variant'), 'vac_crew')

    def test_vac_crew_only_vac_crew_completed_unit_no_units_completed(self):
        """A row with only 'Vac Crew Completed Unit?' checked (Units Completed?=False)
        still passes grouping when __is_vac_crew=True (column-based acceptance path)."""
        row = {
            'Work Request #': '33445566',
            'Weekly Reference Logged Date': '2025-08-17',
            'Units Completed?': False,
            'Vac Crew Completed Unit?': True,
            'Units Total Price': '$80.00',
            '__effective_user': 'VacCrewForeman',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__is_vac_crew': True,
        }
        groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertTrue(len(groups) > 0,
                        "Expected VAC Crew row to pass grouping via Vac Crew Completed Unit?")
        keys = list(groups.keys())
        self.assertTrue(any('_VACCREW' in k for k in keys),
                        f"Expected _VACCREW group key; got: {keys}")

    def test_discover_source_sheets_maps_vac_crew_completed_unit_column(self):
        """discover_source_sheets() must include 'Vac Crew Completed Unit?' in the returned
        column_mapping when the Smartsheet sheet contains that column.

        This validates the real production synonyms dict inside discover_source_sheets()
        rather than a locally-recreated copy, so the test will fail if the entry is ever
        removed from the production code.
        """
        SHEET_ID = 88887777
        COL_DATE_ID = 200
        COL_VAC_ID = 201

        def _mock_col(title, col_type, col_id):
            c = MagicMock()
            c.title = title
            c.type = col_type
            c.id = col_id
            return c

        # Column metadata sheet (include='columns' call)
        cols_meta = [
            _mock_col('Weekly Reference Logged Date', 'DATE', COL_DATE_ID),
            _mock_col('Vac Crew Completed Unit?', 'CHECKBOX', COL_VAC_ID),
        ]
        meta_sheet = MagicMock()
        meta_sheet.name = 'Test VAC Crew Sheet'
        meta_sheet.columns = cols_meta

        # Sample-rows sheet (row_numbers=[1,2,3] call) — provides date sample for validation
        sample_cell = MagicMock()
        sample_cell.column_id = COL_DATE_ID
        sample_cell.value = '2025-08-17'
        sample_cell.display_value = '2025-08-17'
        sample_row = MagicMock()
        sample_row.cells = [sample_cell]
        sample_sheet = MagicMock()
        sample_sheet.rows = [sample_row]

        def _get_sheet(sid, **kwargs):
            if kwargs.get('include') == 'columns':
                return meta_sheet
            return sample_sheet

        mock_client = MagicMock()
        mock_client.Sheets.get_sheet.side_effect = _get_sheet

        # Temporarily override module-level state to isolate this test from real data
        orig_force = generate_weekly_pdfs.FORCE_REDISCOVERY
        orig_use_cache = generate_weekly_pdfs.USE_DISCOVERY_CACHE
        orig_sub = generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS
        orig_orig = generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS
        orig_vac = generate_weekly_pdfs.VAC_CREW_FOLDER_IDS
        try:
            generate_weekly_pdfs.FORCE_REDISCOVERY = True
            generate_weekly_pdfs.USE_DISCOVERY_CACHE = False
            generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS = []
            generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS = []
            generate_weekly_pdfs.VAC_CREW_FOLDER_IDS = []
            with patch.dict(os.environ, {'LIMITED_SHEET_IDS': str(SHEET_ID)}):
                discovered = generate_weekly_pdfs.discover_source_sheets(mock_client)
        finally:
            generate_weekly_pdfs.FORCE_REDISCOVERY = orig_force
            generate_weekly_pdfs.USE_DISCOVERY_CACHE = orig_use_cache
            generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS = orig_sub
            generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS = orig_orig
            generate_weekly_pdfs.VAC_CREW_FOLDER_IDS = orig_vac

        self.assertEqual(len(discovered), 1,
                         f"Expected exactly 1 discovered sheet; got: {discovered}")
        col_mapping = discovered[0]['column_mapping']
        self.assertIn(
            'Vac Crew Completed Unit?', col_mapping,
            "'Vac Crew Completed Unit?' must appear in the column_mapping returned by "
            "discover_source_sheets(). Its absence means the production synonyms dict "
            "is missing the entry and checkbox values will never be read from rows."
        )


class TestVacCrewRowIngest(unittest.TestCase):
    """Tests that get_all_source_rows() correctly accepts and tags VAC Crew rows.

    These tests exercise the actual row-ingest code path with a mocked Smartsheet
    client and verify that the acceptance filter and __is_vac_crew tagging work
    correctly based on the 'Vac Crew Completed Unit?' checkbox alone (without the
    sheet needing to be in VAC_CREW_SHEET_IDS).
    """

    def test_row_ingest_vac_crew_checkbox_accepted_and_flagged(self):
        """A row with Units Completed?=False and Vac Crew Completed Unit?=True is
        accepted by get_all_source_rows() and has __is_vac_crew=True.

        This verifies the column-based detection path that was added in the fix:
        rows on any sheet are accepted and flagged as VAC Crew when the
        'Vac Crew Completed Unit?' checkbox is checked, even when the sheet is
        not explicitly listed in VAC_CREW_SHEET_IDS.
        """
        COL_WR = 100
        COL_DATE = 101
        COL_PRICE = 102
        COL_UNITS_COMPLETED = 103
        COL_VAC_CREW_COMPLETED = 104
        SHEET_ID = 77778888  # not in VAC_CREW_SHEET_IDS — exercises column-based path

        # Build a source config as returned by discover_source_sheets()
        source = {
            'id': SHEET_ID,
            'name': 'Test VAC Crew Sheet',
            'column_mapping': {
                'Work Request #': COL_WR,
                'Weekly Reference Logged Date': COL_DATE,
                'Units Total Price': COL_PRICE,
                'Units Completed?': COL_UNITS_COMPLETED,
                'Vac Crew Completed Unit?': COL_VAC_CREW_COMPLETED,
            },
        }

        def _make_cell(col_id, value):
            cell = MagicMock()
            cell.column_id = col_id
            cell.value = value
            cell.display_value = str(value) if value is not None else None
            return cell

        mock_row = MagicMock()
        mock_row.id = 1
        mock_row.cells = [
            _make_cell(COL_WR, '12345678'),
            _make_cell(COL_DATE, '2025-08-17'),
            _make_cell(COL_PRICE, 100.0),
            _make_cell(COL_UNITS_COMPLETED, False),   # standard checkbox NOT checked
            _make_cell(COL_VAC_CREW_COMPLETED, True),  # VAC Crew checkbox IS checked
        ]

        mock_sheet = MagicMock()
        mock_sheet.rows = [mock_row]
        mock_client = MagicMock()
        mock_client.Sheets.get_sheet.return_value = mock_sheet

        result = generate_weekly_pdfs.get_all_source_rows(mock_client, [source])

        self.assertEqual(
            len(result), 1,
            "Expected exactly one row to be accepted when Vac Crew Completed Unit? "
            "is checked and Units Completed? is not"
        )
        self.assertTrue(
            result[0].get('__is_vac_crew'),
            "__is_vac_crew must be True when the 'Vac Crew Completed Unit?' checkbox "
            "is checked, even when the sheet is not in VAC_CREW_SHEET_IDS"
        )


if __name__ == '__main__':
    unittest.main()
