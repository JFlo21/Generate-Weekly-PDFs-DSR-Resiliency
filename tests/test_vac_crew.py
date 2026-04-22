"""
Tests for VAC Crew Promax sheet support.
Validates VAC_CREW_SHEET_IDS configuration, folder discovery, grouping, and
filename identity parsing for the vac_crew variant.
"""

import os
import unittest
from unittest.mock import MagicMock
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


def _make_children_page(sheet_ids=(), subfolder_ids=(), last_key=None):
    """Build a MagicMock paginated children result containing real Sheet/Folder instances."""
    from smartsheet.models.sheet import Sheet
    from smartsheet.models.folder import Folder
    data = [Sheet({'id': sid, 'name': f'sheet-{sid}'}) for sid in sheet_ids]
    data += [Folder({'id': fid, 'name': f'folder-{fid}'}) for fid in subfolder_ids]
    page = MagicMock()
    page.data = data
    page.last_key = last_key
    return page


class TestVacCrewFolderDiscovery(unittest.TestCase):
    """Tests for VAC Crew folder-based sheet discovery using discover_folder_sheets."""

    def test_vac_crew_folder_discovery_returns_ids(self):
        """discover_folder_sheets returns correct sheet IDs for vac_crew label."""
        mock_client = MagicMock()
        mock_client.Folders.get_folder_children.return_value = _make_children_page(sheet_ids=[5001, 5002])

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [8888], 'vac crew')
        self.assertEqual(result, {5001, 5002})
        mock_client.Folders.get_folder_children.assert_called_once()
        self.assertEqual(mock_client.Folders.get_folder_children.call_args.args[0], 8888)

    def test_vac_crew_folder_discovery_multiple_folders(self):
        """discover_folder_sheets merges IDs across multiple VAC Crew folder IDs."""
        mock_client = MagicMock()

        def _children(fid, **kwargs):
            if fid == 1111:
                return _make_children_page(sheet_ids=[5001])
            return _make_children_page(sheet_ids=[5002])

        mock_client.Folders.get_folder_children.side_effect = _children

        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [1111, 2222], 'vac crew')
        self.assertEqual(result, {5001, 5002})

    def test_vac_crew_folder_discovery_empty_folder_list(self):
        """discover_folder_sheets returns empty set when no folder IDs provided."""
        mock_client = MagicMock()
        result = generate_weekly_pdfs.discover_folder_sheets(mock_client, [], 'vac crew')
        self.assertEqual(result, set())
        mock_client.Folders.get_folder_children.assert_not_called()

    def test_vac_crew_folder_discovery_api_error_graceful(self):
        """discover_folder_sheets handles API errors gracefully for vac_crew folders."""
        mock_client = MagicMock()
        mock_client.Folders.get_folder_children.side_effect = Exception("Smartsheet API error")

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


class TestVacCrewHashAggregation(unittest.TestCase):
    """Regression tests for the VAC crew hash metadata aggregation bug.

    VAC crew groups are not split per foreman in the group key (all VAC crew
    rows for a given WR+week share a single `_VACCREW` group), so a single
    group can contain multiple VAC crew members. Prior to the fix, the hash
    metadata read VAC crew name/dept/job only from sorted_rows[0], which meant
    edits to VAC crew fields on any non-first row left the hash unchanged and
    the file was skipped as "unchanged + attachment exists".
    """

    def _row(self, wr, cu, qty, price, name, dept, job, snapshot='2026-04-19'):
        return {
            'Work Request #': wr,
            'Snapshot Date': snapshot,
            'CU': cu,
            'Quantity': qty,
            'Units Total Price': price,
            'Units Completed?': True,
            '__variant': 'vac_crew',
            '__is_vac_crew': True,
            '__vac_crew_name': name,
            '__vac_crew_dept': dept,
            '__vac_crew_job': job,
        }

    def test_hash_changes_when_non_first_row_vac_crew_dept_edited(self):
        """Editing VAC crew dept on a non-first sorted row must change the hash."""
        base = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice', '1000', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',   '2000', 'J2'),
        ]
        edited = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice', '1000', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',   '2099', 'J2'),
        ]
        self.assertNotEqual(
            generate_weekly_pdfs.calculate_data_hash(base),
            generate_weekly_pdfs.calculate_data_hash(edited),
            "Hash did not change after editing a non-first row's VAC crew "
            "dept — regression: multi-member VAC crew groups will silently "
            "skip regeneration."
        )

    def test_hash_changes_when_non_first_row_vac_crew_name_edited(self):
        """Editing VAC crew name on a non-first sorted row must change the hash."""
        base = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice', '1000', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',   '2000', 'J2'),
        ]
        edited = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice',   '1000', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob Jr.', '2000', 'J2'),
        ]
        self.assertNotEqual(
            generate_weekly_pdfs.calculate_data_hash(base),
            generate_weekly_pdfs.calculate_data_hash(edited),
        )

    def test_hash_stable_when_no_vac_crew_fields_change(self):
        """Same VAC crew data (in any row order) must produce the same hash."""
        rows = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice', '1000', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',   '2000', 'J2'),
        ]
        # Shuffled input order must not change hash — calculate_data_hash
        # already sorts deterministically, and VAC crew fields are per-row
        # in the row hash.
        self.assertEqual(
            generate_weekly_pdfs.calculate_data_hash(rows),
            generate_weekly_pdfs.calculate_data_hash(list(reversed(rows))),
        )

    def test_hash_changes_when_dept_edited_to_existing_member_value(self):
        """A dept edit that only duplicates another member's dept must change
        the hash (set-only aggregation would miss this)."""
        base = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice', '500',  'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',   '600',  'J2'),
            self._row('12345', 'CU-C', 1, '$300', 'Carol', '500',  'J3'),
        ]
        edited = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice', '600',  'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',   '600',  'J2'),
            self._row('12345', 'CU-C', 1, '$300', 'Carol', '500',  'J3'),
        ]
        self.assertNotEqual(
            generate_weekly_pdfs.calculate_data_hash(base),
            generate_weekly_pdfs.calculate_data_hash(edited),
        )


if __name__ == '__main__':
    unittest.main()
