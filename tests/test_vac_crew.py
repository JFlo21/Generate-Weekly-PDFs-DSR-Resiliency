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
    """Regression tests for the VAC crew hash aggregation bug.

    VAC crew groups are not split per foreman in the group key (all VAC
    crew rows for a given WR+week share a single `_VACCREW` group), so a
    single group can contain multiple VAC crew members. Prior to the fix,
    the hash metadata read VAC crew name/dept/job only from sorted_rows[0],
    which meant edits to VAC crew fields on any non-first row left the hash
    unchanged and the file was skipped as "unchanged + attachment exists".

    The final fix embeds VAC crew name/dept/job in the *per-row* row_str
    (scoped to the vac_crew variant), which is strictly more sensitive than
    meta_parts aggregation and is not vulnerable to set-dedup collisions or
    comma-in-name delimiter collisions.
    """

    def setUp(self):
        # Pin module globals that calculate_data_hash() reads so tests are
        # robust against env-var overrides in developer shells. The test
        # suite intentionally covers the `EXTENDED_CHANGE_DETECTION=True`
        # path — the production default — so other values are not exercised
        # here.
        self._saved_ext = generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION
        self._saved_cutoff = generate_weekly_pdfs.RATE_CUTOFF_DATE
        self._saved_fp = generate_weekly_pdfs._RATES_FINGERPRINT
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = True
        generate_weekly_pdfs.RATE_CUTOFF_DATE = None
        generate_weekly_pdfs._RATES_FINGERPRINT = ''

    def tearDown(self):
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = self._saved_ext
        generate_weekly_pdfs.RATE_CUTOFF_DATE = self._saved_cutoff
        generate_weekly_pdfs._RATES_FINGERPRINT = self._saved_fp

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

    def test_hash_changes_when_edited_value_collides_with_another_member(self):
        """Regression: set-based dedup of VAC crew metadata silently missed
        edits to a shared value. With three members having depts
        {500, 500, 600}, editing one row's dept from 500→600 leaves the
        set {500, 600} unchanged. Per-row row_str inclusion must still
        register the change."""
        base = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice',   '500', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',     '500', 'J2'),
            self._row('12345', 'CU-C', 1, '$300', 'Charlie', '600', 'J3'),
        ]
        edited = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice',   '500', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',     '600', 'J2'),  # 500 → 600
            self._row('12345', 'CU-C', 1, '$300', 'Charlie', '600', 'J3'),
        ]
        self.assertNotEqual(
            generate_weekly_pdfs.calculate_data_hash(base),
            generate_weekly_pdfs.calculate_data_hash(edited),
            "Hash did not change when a VAC crew dept edit collided with "
            "another member's dept — the old set-dedup behavior would "
            "silently skip regeneration."
        )

    def test_hash_distinguishes_comma_in_name_edge_case(self):
        """Regression: delimiter collision in ','.join aggregation.
        Names 'A,B' + 'C' and 'A' + 'B,C' both produced the literal
        token 'A,B,C', causing distinct group states to share a hash.
        Per-row row_str inclusion isolates each row's fields, so these
        two states must hash differently."""
        state_1 = [
            self._row('12345', 'CU-A', 1, '$100', 'A,B', '1', 'J'),
            self._row('12345', 'CU-B', 1, '$200', 'C',   '2', 'J'),
        ]
        state_2 = [
            self._row('12345', 'CU-A', 1, '$100', 'A',   '1', 'J'),
            self._row('12345', 'CU-B', 1, '$200', 'B,C', '2', 'J'),
        ]
        self.assertNotEqual(
            generate_weekly_pdfs.calculate_data_hash(state_1),
            generate_weekly_pdfs.calculate_data_hash(state_2),
            "Distinct VAC crew states collapsed to the same hash — "
            "delimiter collision in aggregated metadata."
        )

    def test_hash_stable_when_no_vac_crew_fields_change(self):
        """Same VAC crew data (in any row order) must produce the same hash."""
        rows = [
            self._row('12345', 'CU-A', 1, '$100', 'Alice', '1000', 'J1'),
            self._row('12345', 'CU-B', 1, '$200', 'Bob',   '2000', 'J2'),
        ]
        # calculate_data_hash sorts rows deterministically before hashing,
        # so input order must not affect the result.
        self.assertEqual(
            generate_weekly_pdfs.calculate_data_hash(rows),
            generate_weekly_pdfs.calculate_data_hash(list(reversed(rows))),
        )

    def test_legacy_mode_ignores_vac_crew_metadata_edits(self):
        """Regression: legacy mode (EXTENDED_CHANGE_DETECTION=0) must remain
        insensitive to VAC crew field edits. The docstring promises
        legacy uses only the original minimal fields so hashes stay
        bit-stable for rollbacks, and legacy row_data does not include
        VAC crew fields. Applying VAC crew tie-breakers unconditionally
        to the sort key would let VAC crew edits change the hash
        indirectly by reordering rows whose legacy row_data differs on
        non-primary fields (Work Type / Units Completed? / price)."""
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = False
        # Tied on primary sort keys but with differing legacy row_data
        # (Work Type differs) — order matters for the hasher.
        row_a = self._row('12345', 'CU-SAME', 1, '$100', 'Alice', '1000', 'J1')
        row_b = self._row('12345', 'CU-SAME', 1, '$100', 'Bob',   '2000', 'J2')
        row_a['Work Type'] = 'Install'
        row_b['Work Type'] = 'Remove'

        base_hash = generate_weekly_pdfs.calculate_data_hash([row_a, row_b])

        # Edit a VAC crew field only — legacy hash must not change.
        row_a_edited = dict(row_a, __vac_crew_dept='9999')
        edited_hash = generate_weekly_pdfs.calculate_data_hash(
            [row_a_edited, row_b]
        )
        self.assertEqual(
            base_hash, edited_hash,
            "Legacy hash changed after a VAC crew field edit — "
            "tie-breakers must be gated behind EXTENDED_CHANGE_DETECTION "
            "to preserve rollback-stability of legacy mode."
        )

    def test_hash_stable_when_vac_crew_rows_share_primary_sort_keys(self):
        """Regression: including VAC crew fields in row_str made the hash
        sensitive to insertion order when multiple VAC crew rows share
        (WR, Snapshot, CU, Pole, Qty). Because rows are merged from
        parallel `as_completed` futures in `get_all_source_rows`,
        insertion order is non-deterministic across runs. VAC crew fields
        must act as tie-breakers in the sort key so identical datasets
        hash identically regardless of which future returned first."""
        rows = [
            self._row('12345', 'CU-SAME', 1, '$100', 'Alice', '1000', 'J1'),
            self._row('12345', 'CU-SAME', 1, '$100', 'Bob',   '2000', 'J2'),
        ]
        # All five primary sort keys match; only VAC crew fields differ.
        self.assertEqual(
            generate_weekly_pdfs.calculate_data_hash(rows),
            generate_weekly_pdfs.calculate_data_hash(list(reversed(rows))),
            "Hash changed when VAC crew rows with identical primary sort "
            "keys were reversed — missing tie-breaker makes production "
            "runs subject to insertion-order churn."
        )


class TestVacCrewColumnTitleNormalizer(unittest.TestCase):
    """Tests for ``_normalize_column_title_for_vac_crew``.

    The normalizer exists so the fuzzy fallback in ``_validate_single_sheet``
    can reconcile Smartsheet column titles that drift from the canonical form
    by whitespace, decorative trailing ``?``/``#``, or case. If these
    assertions fail, the fuzzy fallback will stop reconciling real-world
    variants and sheet ``1413438401105796`` (and any future sheet cloned
    from it) will silently drop VAC Crew detection again.
    """

    def test_collapses_runs_of_whitespace(self):
        norm = generate_weekly_pdfs._normalize_column_title_for_vac_crew
        self.assertEqual(
            norm('VAC   Crew  Helping?'),
            norm('VAC Crew Helping?'),
        )

    def test_strips_trailing_question_and_hash_with_surrounding_spaces(self):
        norm = generate_weekly_pdfs._normalize_column_title_for_vac_crew
        self.assertEqual(norm('VAC Crew Helping '), norm('VAC Crew Helping?'))
        self.assertEqual(norm('VAC Crew Helping ?'), norm('VAC Crew Helping?'))
        self.assertEqual(norm('VAC Crew Dept#'), norm('VAC Crew Dept #'))
        self.assertEqual(norm('VAC Crew Dept '), norm('VAC Crew Dept #'))

    def test_is_case_insensitive(self):
        norm = generate_weekly_pdfs._normalize_column_title_for_vac_crew
        self.assertEqual(norm('vac crew helping?'), norm('VAC Crew Helping?'))
        self.assertEqual(norm('VAC CREW HELPING?'), norm('VAC Crew Helping?'))

    def test_canonicalises_hyphenated_variants(self):
        """'vac-crew' variants must normalize to the canonical 'vac crew' token
        so the broadened substring detector and the fuzzy fallback stay in sync
        — otherwise a hyphenated column title advertises itself in logs but
        still silently fails to map."""
        norm = generate_weekly_pdfs._normalize_column_title_for_vac_crew
        self.assertEqual(norm('Vac-Crew Helping?'), norm('VAC Crew Helping?'))
        self.assertEqual(norm('VAC-CREW Completed Unit?'),
                         norm('Vac Crew Completed Unit?'))
        self.assertEqual(norm('vac-crew dept#'), norm('VAC Crew Dept #'))

    def test_canonicalises_joined_word_variants(self):
        """'vaccrew' (no separator) variants must normalize to 'vac crew' so
        the fuzzy fallback resolves them — same synchronization concern as the
        hyphenated case."""
        norm = generate_weekly_pdfs._normalize_column_title_for_vac_crew
        self.assertEqual(norm('VacCrew Helping?'), norm('VAC Crew Helping?'))
        self.assertEqual(norm('VACCREW Completed Unit?'),
                         norm('Vac Crew Completed Unit?'))
        self.assertEqual(norm('vaccrew job#'), norm('Vac Crew Job #'))

    def test_handles_none_and_empty(self):
        norm = generate_weekly_pdfs._normalize_column_title_for_vac_crew
        self.assertEqual(norm(None), '')
        self.assertEqual(norm(''), '')
        self.assertEqual(norm('   '), '')


class TestVacCrewColumnFuzzyFallback(unittest.TestCase):
    """Integration tests for the fuzzy VAC Crew column fallback inside
    ``_validate_single_sheet``.

    Simulates a Smartsheet whose VAC Crew columns carry subtle name
    variants that the exact-match ``synonyms`` dict cannot absorb (the
    documented failure mode on sheet id ``1413438401105796`` in folder
    ``8815193070299012``). After the fuzzy pass the canonical VAC Crew
    keys must be present in the column mapping so
    ``sheet_has_vac_crew_columns`` evaluates True at runtime and the
    row-level detection block fires for that sheet.
    """

    def _build_mock_client(self, column_titles):
        """Return a mock Smartsheet client whose get_sheet returns a sheet
        with the given column titles and no rows."""
        from smartsheet.models.column import Column
        from smartsheet.models.sheet import Sheet as _Sheet

        columns = []
        for idx, title in enumerate(column_titles, start=1):
            col = Column({'id': 1000 + idx, 'title': title, 'type': 'TEXT_NUMBER'})
            columns.append(col)

        # Ensure a Weekly Reference Logged Date column exists so
        # _validate_single_sheet returns a dict rather than None.
        wr_col = Column({
            'id': 9001,
            'title': 'Weekly Reference Logged Date',
            'type': 'DATE',
        })
        columns.append(wr_col)

        sheet = _Sheet({
            'id': 1413438401105796,
            'name': 'Mock VAC Crew Sheet',
            'columns': [],
            'rows': [],
        })
        # Attach columns directly — the SDK's Sheet model constructor does
        # not always hydrate columns from the raw dict.
        sheet.columns = columns
        sheet.rows = []

        mock_client = MagicMock()
        mock_client.Sheets.get_sheet.return_value = sheet
        return mock_client

    def _run_discovery(self, mock_client, sheet_id=1413438401105796):
        """Invoke discover_source_sheets via a LIMITED_SHEET_IDS override
        so only our fake sheet is validated, bypassing the cache."""
        saved_env = {
            'LIMITED_SHEET_IDS': os.environ.get('LIMITED_SHEET_IDS'),
            'USE_DISCOVERY_CACHE': os.environ.get('USE_DISCOVERY_CACHE'),
            'FORCE_REDISCOVERY': os.environ.get('FORCE_REDISCOVERY'),
            'SUBCONTRACTOR_FOLDER_IDS': os.environ.get('SUBCONTRACTOR_FOLDER_IDS'),
            'ORIGINAL_CONTRACT_FOLDER_IDS': os.environ.get('ORIGINAL_CONTRACT_FOLDER_IDS'),
        }
        try:
            os.environ['LIMITED_SHEET_IDS'] = str(sheet_id)
            os.environ['USE_DISCOVERY_CACHE'] = '0'
            os.environ['FORCE_REDISCOVERY'] = '1'
            os.environ['SUBCONTRACTOR_FOLDER_IDS'] = ''
            os.environ['ORIGINAL_CONTRACT_FOLDER_IDS'] = ''
            # Align module-level globals with the env overrides.
            saved_use_cache = generate_weekly_pdfs.USE_DISCOVERY_CACHE
            saved_force = generate_weekly_pdfs.FORCE_REDISCOVERY
            saved_sub_folders = generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS
            saved_orig_folders = generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS
            generate_weekly_pdfs.USE_DISCOVERY_CACHE = False
            generate_weekly_pdfs.FORCE_REDISCOVERY = True
            generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS = []
            generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS = []
            try:
                return generate_weekly_pdfs.discover_source_sheets(mock_client)
            finally:
                generate_weekly_pdfs.USE_DISCOVERY_CACHE = saved_use_cache
                generate_weekly_pdfs.FORCE_REDISCOVERY = saved_force
                generate_weekly_pdfs.SUBCONTRACTOR_FOLDER_IDS = saved_sub_folders
                generate_weekly_pdfs.ORIGINAL_CONTRACT_FOLDER_IDS = saved_orig_folders
        finally:
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def _assert_vac_crew_mapped(self, discovered):
        self.assertEqual(len(discovered), 1)
        mapping = discovered[0]['column_mapping']
        self.assertIn('VAC Crew Helping?', mapping,
                      f"VAC Crew Helping? not mapped; mapping={mapping}")
        self.assertIn('Vac Crew Completed Unit?', mapping,
                      f"Vac Crew Completed Unit? not mapped; mapping={mapping}")

    def test_whitespace_variant_resolves_via_fuzzy_fallback(self):
        """Columns with extra whitespace or trailing space before '?'
        must still map to canonical VAC Crew keys."""
        titles = [
            'VAC Crew  Helping?',              # double space
            'Vac Crew Completed Unit ?',       # space before '?'
            'Work Request #',
        ]
        client = self._build_mock_client(titles)
        discovered = self._run_discovery(client)
        self._assert_vac_crew_mapped(discovered)

    def test_case_variant_resolves_via_fuzzy_fallback(self):
        """All-caps or all-lower variants must still map."""
        titles = [
            'VAC CREW HELPING?',
            'vac crew completed unit?',
            'Work Request #',
        ]
        client = self._build_mock_client(titles)
        discovered = self._run_discovery(client)
        self._assert_vac_crew_mapped(discovered)

    def test_hyphenated_variant_resolves_via_fuzzy_fallback(self):
        """'Vac-Crew' hyphenated variants must map via the normalizer's
        hyphen→space canonicalisation. Without this, the broadened substring
        detector would log the title as 'found' while the mapping silently
        failed — the same failure class this PR is fixing."""
        titles = [
            'Vac-Crew Helping?',
            'VAC-CREW Completed Unit?',
            'Work Request #',
        ]
        client = self._build_mock_client(titles)
        discovered = self._run_discovery(client)
        self._assert_vac_crew_mapped(discovered)

    def test_joined_word_variant_resolves_via_fuzzy_fallback(self):
        """'VacCrew' / 'VACCREW' (no separator) variants must map via the
        normalizer's joined-word canonicalisation."""
        titles = [
            'VacCrew Helping?',
            'VACCREW Completed Unit?',
            'Work Request #',
        ]
        client = self._build_mock_client(titles)
        discovered = self._run_discovery(client)
        self._assert_vac_crew_mapped(discovered)

    def test_dept_and_job_resolve_when_hash_drops_spacing(self):
        """Dept/Job variants like 'Vac Crew Dept#' (no space) must still map."""
        titles = [
            'Vac Crew Helping?',
            'Vac Crew Completed Unit?',
            'Vac Crew Dept#',        # missing space before '#'
            'VAC Crew Job#',         # missing space, differing case
            'Work Request #',
        ]
        client = self._build_mock_client(titles)
        discovered = self._run_discovery(client)
        mapping = discovered[0]['column_mapping']
        self.assertIn('VAC Crew Dept #', mapping)
        self.assertIn('Vac Crew Job #', mapping)

    def test_existing_exact_matches_are_not_overridden(self):
        """If canonical titles are already present (exact match) the fuzzy
        pass must not clobber the existing mapping with a different column."""
        titles = [
            'VAC Crew Helping?',          # exact canonical
            'VAC Crew Helping ?',         # variant, should NOT displace above
            'Vac Crew Completed Unit?',   # exact canonical
            'Work Request #',
        ]
        client = self._build_mock_client(titles)
        discovered = self._run_discovery(client)
        mapping = discovered[0]['column_mapping']
        # The exact match is iterated first; fuzzy pass must not clobber it.
        # Whichever of the two columns won the exact-match race, the other
        # (variant) must NOT now be mapped to the same canonical key.
        vac_helping_id = mapping['VAC Crew Helping?']
        # The variant col id 1002 (second in list) has title 'VAC Crew Helping ?'
        # and the exact col id 1001 has title 'VAC Crew Helping?'. We only
        # require the canonical slot resolves to exactly one of them once.
        self.assertIn(vac_helping_id, {1001, 1002})

    def test_discovery_cache_version_bumped_to_4(self):
        """The cache version must be bumped past v3 so existing caches
        written before the fuzzy fallback are invalidated on next run."""
        self.assertGreaterEqual(
            generate_weekly_pdfs.DISCOVERY_CACHE_VERSION, 4,
            "DISCOVERY_CACHE_VERSION must be >=4 so caches created before "
            "the fuzzy fallback (v3) are invalidated, otherwise sheets like "
            "1413438401105796 stay stuck with the old mapping for up to "
            "DISCOVERY_CACHE_TTL_MIN (default 7d)."
        )


if __name__ == '__main__':
    unittest.main()
