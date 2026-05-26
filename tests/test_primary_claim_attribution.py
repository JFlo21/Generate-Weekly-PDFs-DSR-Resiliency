"""Sub-project D — primary-workflow primary claim attribution tests."""
import datetime
import inspect
import os
import tempfile
import unittest
from unittest import mock

import generate_weekly_pdfs  # noqa: E402
from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked, _reset_all  # noqa: E402

_ensure_smartsheet_mocked()

from billing_audit.writer import ResolveOutcome  # noqa: E402

gwp = generate_weekly_pdfs


class TestConfigConstants(unittest.TestCase):
    """Task 1: D config surface exists with the right defaults."""

    def test_hash_prune_version_constant(self):
        self.assertEqual(gwp.SUBPROJECT_D_HASH_PRUNE_VERSION, 1)

    def test_attribution_flag_is_bool(self):
        self.assertIsInstance(gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED, bool)

    def test_cleanup_flag_is_bool(self):
        self.assertIsInstance(
            gwp.LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED, bool
        )

    def test_banner_logs_attribution_flag(self):
        src = inspect.getsource(generate_weekly_pdfs)
        self.assertIn(
            "📋 PRIMARY_CLAIM_ATTRIBUTION_ENABLED=", src
        )
        self.assertIn(
            "📋 LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED=", src
        )


class TestPrimaryFilenameSuffix(unittest.TestCase):
    """Task 2: generate_excel emits _User_<claimer> for primary variant
    when attribution is enabled, bare otherwise."""

    def setUp(self):
        self._orig = gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._orig

    def test_primary_branch_builds_user_suffix_gated(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # The primary branch must build _User_<sanitized claimer> gated on
        # the kill switch + a non-empty __current_foreman.
        self.assertIn("_User_", src)
        # Confirm the gate wording is present in the primary suffix branch.
        # PR #223 Codex-P1 follow-up widened the gate to also require
        # RES_GROUPING_MODE in ('helper','both') (see TestPrimaryModeStaysBare),
        # so the kill switch and ``and _pf`` are no longer adjacent — tolerate
        # the interposed mode clause.
        self.assertRegex(
            src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED[\s\S]{0,120}and _pf"
            r"[\s\S]{0,200}_User_\{",
        )


def _make_primary_row(
    row_id,
    wr='90001',
    week_serial='2026-04-19',  # ISO date; excel_serial_to_date is STRICT (rejects numeric serials) -> week key 041926
    effective_user='CurrentForeman',
    source_sheet_id=99999,  # NOT in _FOLDER_DISCOVERED_SUB_IDS
):
    """Build a synthetic NON-subcontractor, completed, non-helper,
    non-vac primary row for group_source_rows."""
    return {
        '__row_id': row_id,
        '__source_sheet_id': source_sheet_id,
        '__effective_user': effective_user,
        '__is_helper_row': False,
        '__is_vac_crew': False,
        'Work Request #': wr,
        'Weekly Reference Logged Date': week_serial,
        'Units Completed?': True,
        'Units Total Price': 100.0,
        'Dept #': '500',
        'Job #': 'J-1',
    }


class TestPrimaryPrePass(unittest.TestCase):
    """Task 3: the pre-pass resolves frozen claimers for non-sub
    completed primary rows into _primary_claimer_map."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'mode': gwp.RES_GROUPING_MODE,
            'sub': set(gwp._FOLDER_DISCOVERED_SUB_IDS),
        }
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()  # row sheet 99999 is non-sub

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()
        gwp._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub'])

    def test_prepass_resolves_frozen_claimer_into_group_key(self):
        rows = [_make_primary_row(1001, effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        keys = list(groups.keys())
        self.assertTrue(
            any(k.endswith('_USER_FrozenFM') for k in keys),
            f"expected a _USER_FrozenFM primary group, got {keys}",
        )

    def _make_valid_helper_row(self, row_id, wr='90001'):
        # A completed helper row (both checkboxes) with helper_foreman +
        # helper_dept -> emitted to the _Helper_ shadow file, NOT the primary
        # _USER_ group. The pre-pass must skip it (no wasted resolve_claimer).
        r = _make_primary_row(row_id, wr=wr, effective_user='CurFM')
        r['__is_helper_row'] = True
        r['__helper_foreman'] = 'HelpFM'
        r['__helper_dept'] = '600'
        return r

    def test_prepass_skips_valid_helper_row(self):
        # PR #223 review follow-up: a valid helper row never emits a primary
        # _USER_ group, so the pre-pass must not call resolve_claimer for it.
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ) as _rc:
            gwp.group_source_rows([self._make_valid_helper_row(2001)])
        _rc.assert_not_called()

    def test_prepass_resolves_primary_only_skipping_helper(self):
        rows = [
            _make_primary_row(3001, wr='90002', effective_user='PFM'),
            self._make_valid_helper_row(3002, wr='90002'),
        ]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ) as _rc:
            gwp.group_source_rows(rows)
        # resolve_claimer called exactly once (the primary row); the valid
        # helper row was skipped by the pre-pass eligibility filter.
        self.assertEqual(_rc.call_count, 1)


class TestPrimaryPrePassSource(unittest.TestCase):
    """Task 3: the pre-pass exists with the right shape."""

    def test_prepass_block_present(self):
        src = inspect.getsource(generate_weekly_pdfs)
        self.assertIn("_primary_claimer_map", src)
        self.assertRegex(
            src,
            r"resolve_claimer_primary\(\s*'primary'",
        )
        # Pre-pass must exclude subcontractor + vac rows.
        self.assertRegex(
            src,
            r"_primary_claimer_map[\s\S]{0,600}_FOLDER_DISCOVERED_SUB_IDS",
        )


class TestPrimaryEmission(unittest.TestCase):
    """Task 4: production primary emission partitions by claimer when on,
    bare when off; never holds."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'mode': gwp.RES_GROUPING_MODE,
            'sub': set(gwp._FOLDER_DISCOVERED_SUB_IDS),
        }
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()
        gwp._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub'])

    def test_frozen_claimer_partitions_key(self):
        rows = [_make_primary_row(1, effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        self.assertTrue(any(k.endswith('_USER_FrozenFM') for k in groups))
        # The legacy bare primary key must NOT be present.
        self.assertFalse(
            any(k.split('_USER_')[0] == k and '_USER_' not in k
                and k.count('_') == 1 for k in groups),
        )

    def test_two_claimers_two_groups(self):
        rows = [
            _make_primary_row(1, wr='90001', effective_user='A'),
            _make_primary_row(2, wr='90001', effective_user='B'),
        ]

        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            return ResolveOutcome(
                'use', 'Alice' if row_id == 1 else 'Bob', 'frozen', 'success'
            )

        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = gwp.group_source_rows(rows)
        self.assertTrue(any(k.endswith('_USER_Alice') for k in groups))
        self.assertTrue(any(k.endswith('_USER_Bob') for k in groups))

    def test_no_history_falls_back_to_current(self):
        # Use distinct values for effective_user vs outcome.name so the
        # test can distinguish which branch the code took:
        #   outcome.name='ResolvedName'  → the ``use`` branch consumed .name
        #   effective_user='CurFM'       → the wrong/else branch fallback
        # The ``no_history`` → ``use`` path must consume outcome.name.
        rows = [_make_primary_row(1, effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'ResolvedName', 'current', 'no_history'),
        ):
            groups = gwp.group_source_rows(rows)
        # outcome.name was consumed: key must end with _USER_ResolvedName,
        # NOT with _USER_CurFM (which would mean effective_user was used).
        self.assertTrue(
            any(k.endswith('_USER_ResolvedName') for k in groups),
            f"expected _USER_ResolvedName key; got {list(groups)}",
        )
        self.assertFalse(
            any(k.endswith('_USER_CurFM') for k in groups),
            "effective_user leaked into key — code must use outcome.name on the 'use' branch",
        )

    def test_hold_outage_still_emits_under_current(self):
        rows = [_make_primary_row(1, effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('hold', None, None, 'fetch_failure'),
        ), mock.patch(
            'billing_audit.writer.record_attribution_hold'
        ) as _rec:
            groups = gwp.group_source_rows(rows)
        # D never holds: a primary group IS emitted under current foreman.
        self.assertTrue(any(k.endswith('_USER_CurFM') for k in groups))
        # And record_attribution_hold is NEVER called for the primary path.
        _rec.assert_not_called()

    def test_kill_switch_off_emits_bare_legacy_key(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        rows = [_make_primary_row(1, wr='90001', effective_user='CurFM')]
        # No mock needed — pre-pass is gated off, emission is legacy.
        groups = gwp.group_source_rows(rows)
        bare = [k for k in groups if '_USER_' not in k]
        self.assertTrue(bare, f"expected a bare primary key, got {list(groups)}")
        # bare key shape is {week}_{wr}
        self.assertTrue(any(k.endswith('_90001') for k in bare))


class TestPrimaryModeStaysBare(unittest.TestCase):
    """PR #223 Codex P1 follow-up — primary-mode consistency.

    In ``RES_GROUPING_MODE == 'primary'`` the emission deliberately stays
    bare (``{week}_{wr}``) and lumps every non-helper/non-sub foreman's rows
    into ONE workbook per WR/week — partitioning by ``primary_foreman`` there
    is documented as *semantically wrong* (design spec §Scope / Out of scope;
    Living Ledger). But pre-fix the ``generate_excel`` filename suffix and the
    three identity sites gated ONLY on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``
    (default on), so they derived ``_User_<first-row foreman>`` even in
    primary mode — mislabeling a multi-foreman workbook and letting row-order
    changes flip the attachment identity between runs.

    The fix gates all four surfaces on ``RES_GROUPING_MODE in ('helper',
    'both')`` too, so primary mode is *consistently* bare at every surface
    (matching the already-mode-gated pre-pass + emission). ``both`` / ``helper``
    production behaviour is unchanged.
    """

    def setUp(self):
        self._saved = {
            'mode': gwp.RES_GROUPING_MODE,
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'out': gwp.OUTPUT_FOLDER,
        }
        self._tmpdir = tempfile.TemporaryDirectory()
        gwp.OUTPUT_FOLDER = self._tmpdir.name
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.OUTPUT_FOLDER = self._saved['out']
        self._tmpdir.cleanup()

    def _make_row(self, foreman):
        return {
            'Work Request #': '90001',
            'Weekly Reference Logged Date': '2026-04-19',
            'Units Completed?': True,
            'Units Total Price': '$100.00',
            'CU': 'XYZ',
            'Work Type': 'Install',
            'Quantity': 1,
            'Customer Name': 'TestCustomer',
            'Foreman': foreman,
            'Dept #': '500',
            'Job #': 'J-1',
            '__effective_user': foreman,
            '__current_foreman': foreman,
            '__variant': 'primary',
            '__week_ending_date': datetime.datetime(2026, 4, 19),
        }

    def _gen_basename(self):
        rows = [self._make_row('PrimaryFM')]
        result = gwp.generate_excel(
            '041926_90001', rows, datetime.datetime(2026, 4, 19),
            data_hash='deadbeefcafe0001',
        )
        return os.path.basename(result[0])

    def test_primary_mode_filename_has_no_user_suffix(self):
        gwp.RES_GROUPING_MODE = 'primary'
        name = self._gen_basename()
        self.assertNotIn(
            '_User_', name,
            f"primary-mode workbook must be bare (no _User_), got {name!r}",
        )

    def test_both_mode_filename_keeps_user_suffix(self):
        # Positive control: the fix must NOT regress production ('both')
        # mode, which DOES partition by claimer.
        gwp.RES_GROUPING_MODE = 'both'
        name = self._gen_basename()
        self.assertIn(
            '_User_PrimaryFM', name,
            f"both-mode workbook must keep _User_<claimer>, got {name!r}",
        )

    def test_filename_suffix_gated_on_grouping_mode(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # The primary filename-suffix branch must require helper/both mode
        # in addition to the kill switch + non-empty __current_foreman.
        # (\s+ tolerates the multi-line ``if (`` continuation form.)
        self.assertRegex(
            src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED\s+and\s+"
            r"RES_GROUPING_MODE in \('helper', 'both'\)"
            r"[\s\S]{0,160}_User_\{",
        )

    def test_site_a_identity_gated_on_grouping_mode(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # Site 1 (main-loop history_key/file_identifier): gate must include
        # the grouping-mode check so primary mode produces the legacy
        # (User-field) identifier, NOT a __current_foreman _User_ identity.
        self.assertRegex(
            src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED\s+and\s+"
            r"RES_GROUPING_MODE in \('helper', 'both'\)"
            r"[\s\S]{0,520}__current_foreman"
            r"[\s\S]{0,520}first_row\.get\('User'\)",
        )

    def test_sites_bc_identity_gated_on_grouping_mode(self):
        import re as _re
        src = inspect.getsource(generate_weekly_pdfs)
        # Sites 2 & 3 (valid_wr_weeks / current_keys builders) plus the
        # filename suffix and Site 1 all gate the __current_foreman primary
        # partition on the grouping mode -> at least 4 occurrences.
        count = len(_re.findall(
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED\s+and\s+"
            r"RES_GROUPING_MODE in \('helper', 'both'\)",
            src,
        ))
        self.assertGreaterEqual(
            count, 4,
            f"expected >=4 mode-gated primary surfaces, found {count}",
        )


class TestPrimaryFilenameRoundTrip(unittest.TestCase):
    """Task 2+4: two claimers on one WR+week produce two distinct
    _User_ filenames that round-trip through build_group_identity as
    distinct primary identities (coexistence; no cross-delete)."""

    def test_distinct_identities_for_two_claimers(self):
        a = gwp.build_group_identity(
            "WR_90001_WeekEnding_041926_120000_User_Alice_abcdef0123456789.xlsx"
        )
        b = gwp.build_group_identity(
            "WR_90001_WeekEnding_041926_120000_User_Bob_abcdef0123456789.xlsx"
        )
        self.assertEqual(a, ('90001', '041926', 'primary', 'Alice'))
        self.assertEqual(b, ('90001', '041926', 'primary', 'Bob'))
        self.assertNotEqual(a, b)  # distinct -> cleanup keeps both


class TestPrimaryGroupCreatedPiiMarker(unittest.TestCase):
    """Task 4 review fix: the PRIMARY GROUP CREATED INFO log embeds WR=/Week=
    PII, so its marker must be registered in _PII_LOG_MARKERS (mirrors the
    five sibling GROUP CREATED markers; [2026-04-20 12:00] / [2026-05-15
    12:00] rules)."""

    def test_marker_registered(self):
        self.assertIn("PRIMARY GROUP CREATED", gwp._PII_LOG_MARKERS)


class TestSiteAMainLoopIdentity(unittest.TestCase):
    """Task 5: main-loop primary identity derives from __current_foreman
    when attribution is on (gated), legacy User field when off."""

    def test_site_a_gated_primary_identity(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # The primary identity branch must derive from __current_foreman
        # gated on PRIMARY_CLAIM_ATTRIBUTION_ENABLED, and keep the legacy
        # User-field path for the disabled case.
        # Note: span widened to 500 after Task 6 renamed the Site-1 local
        # variable to ``_pf``, adding comments that push the gap past 300
        # chars. The structural invariant (PRIMARY_CLAIM_ATTRIBUTION_ENABLED
        # → __current_foreman dict-key → first_row.get('User') fallback) is
        # preserved — only the window size changed.
        self.assertRegex(
            src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED[\s\S]{0,500}"
            r"__current_foreman[\s\S]{0,500}"
            r"first_row\.get\('User'\)",
        )


class TestSitesBCIdentity(unittest.TestCase):
    """Task 6: valid_wr_weeks (Site 2) and current_keys (Site 3) primary
    branches derive from __current_foreman gated on the kill switch."""

    def test_sites_b_and_c_gated_primary_identity(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # Site 2 (valid_wr_weeks builder): the else branch builds file_id
        # from __current_foreman gated on PRIMARY_CLAIM_ATTRIBUTION_ENABLED.
        self.assertRegex(
            src,
            r"file_id = \(\s*_RE_SANITIZE_IDENTIFIER\.sub\('_', _pf\)\[:50\]"
            r"\s*if \(PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf\)",
        )
        # Site 3 (current_keys builder): the else branch builds _ident
        # from __current_foreman gated on PRIMARY_CLAIM_ATTRIBUTION_ENABLED.
        self.assertRegex(
            src,
            r"_ident = \(\s*_RE_SANITIZE_IDENTIFIER\.sub\('_', _pf\)\[:50\]"
            r"\s*if \(PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf\)",
        )


class TestWrFilterMatchesUserVariant(unittest.TestCase):
    """Task 7: WR_FILTER (_key_matches_wr) retains _USER_ primary groups;
    EXCLUDE_WRS (_key_matches_excluded_wr) already does."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'mode': gwp.RES_GROUPING_MODE,
            'sub': set(gwp._FOLDER_DISCOVERED_SUB_IDS),
            'tm': gwp.TEST_MODE,
            'wf': list(gwp.WR_FILTER),
            'ex': list(gwp.EXCLUDE_WRS),
        }
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()
        gwp._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub'])
        gwp.TEST_MODE = self._saved['tm']
        gwp.WR_FILTER = self._saved['wf']
        gwp.EXCLUDE_WRS = self._saved['ex']

    def test_wr_filter_retains_user_primary_group(self):
        gwp.TEST_MODE = True
        gwp.WR_FILTER = ['90001']
        rows = [_make_primary_row(1, wr='90001', effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        self.assertTrue(
            any(k.endswith('_USER_FrozenFM') for k in groups),
            f"WR_FILTER dropped the _USER_ primary group: {list(groups)}",
        )

    def test_exclude_wrs_drops_user_primary_group(self):
        gwp.EXCLUDE_WRS = ['90001']
        rows = [_make_primary_row(1, wr='90001', effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        self.assertEqual(
            [k for k in groups if k.endswith('_USER_FrozenFM')], [],
            f"EXCLUDE_WRS failed to drop the _USER_ primary group: {list(groups)}",
        )


class TestBuildPrimaryWrScope(unittest.TestCase):
    """Task 8: scope helper returns sanitized WRs with a partitioned
    _USER_ primary group in this run."""

    def test_scope_collects_partitioned_primary_wrs(self):
        # __variant is the authoritative variant signal (set at emission);
        # the scope builder reads it, not a key substring.
        groups = {
            '041926_90001_USER_Alice': [{'Work Request #': '90001', '__variant': 'primary'}],
            '041926_90002_USER_Bob': [{'Work Request #': '90002', '__variant': 'primary'}],
            '041926_90003_HELPER_Carol': [{'Work Request #': '90003', '__variant': 'helper'}],
            '041926_90004_VACCREW_Dan': [{'Work Request #': '90004', '__variant': 'vac_crew'}],
            '041926_90005_REDUCEDSUB_USER_Eve': [{'Work Request #': '90005', '__variant': 'reduced_sub'}],
            '041926_90006': [{'Work Request #': '90006', '__variant': 'primary'}],  # bare primary (OFF/'primary' mode), no _USER_
        }
        scope = gwp._build_primary_wr_scope(groups)
        self.assertIn('90001', scope)
        self.assertIn('90002', scope)
        # Helper / vac / subcontractor / bare-primary groups are NOT in scope.
        self.assertNotIn('90003', scope)
        self.assertNotIn('90004', scope)
        self.assertNotIn('90005', scope)  # reduced_sub variant is B's, not D's
        self.assertNotIn('90006', scope)  # primary but bare (no _USER_)

    def test_empty_groups(self):
        self.assertEqual(gwp._build_primary_wr_scope({}), set())

    def test_helper_or_vac_only_wr_excluded_from_scope(self):
        # A WR that has ONLY a _HELPER_ or _VACCREW group (no _USER_
        # primary group) must NOT appear in D's scope — D only owns WRs
        # it actually partitioned this run.
        groups = {
            '041926_90010_HELPER_Carol': [{'Work Request #': '90010', '__variant': 'helper'}],
            '041926_90011_VACCREW_Dan': [{'Work Request #': '90011', '__variant': 'vac_crew'}],
        }
        scope = gwp._build_primary_wr_scope(groups)
        self.assertEqual(scope, set())

    def test_reserved_token_in_name_does_not_false_positive(self):
        # Codex PR #223 P1 regression guard. The scope builder must decide
        # variant from the authoritative ``__variant`` field, NOT a key
        # substring — otherwise a claimer / helper / vac name containing a
        # reserved word mis-buckets the WR (and the scope feeds the
        # DESTRUCTIVE bare-primary cleanup + the hash prune).
        groups = {
            # helper whose NAME contains the USER token -> key has _USER_
            # substring but __variant=='helper' -> must be EXCLUDED.
            '041926_90020_HELPER_USER_Smith': [
                {'Work Request #': '90020', '__variant': 'helper'}],
            # vac member named USER -> EXCLUDED.
            '041926_90021_VACCREW_USER_Jones': [
                {'Work Request #': '90021', '__variant': 'vac_crew'}],
            # genuine primary claimer whose NAME contains a reserved word
            # -> must be INCLUDED (the old substring exclusions wrongly
            # dropped these).
            '041926_90022_USER_ReducedSub_Bob': [
                {'Work Request #': '90022', '__variant': 'primary'}],
            '041926_90023_USER_AEPBillable_Sue': [
                {'Work Request #': '90023', '__variant': 'primary'}],
        }
        scope = gwp._build_primary_wr_scope(groups)
        self.assertNotIn('90020', scope)
        self.assertNotIn('90021', scope)
        self.assertIn('90022', scope)
        self.assertIn('90023', scope)


class TestSubprojectDHashPrune(unittest.TestCase):
    """Task 9: one-time prune of legacy bare-primary orphans, gated +
    idempotent + migration-dirty bool."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        self._attr = gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._attr

    def _groups(self):
        return {'041926_90001_USER_Alice': [
            {'Work Request #': '90001', '__variant': 'primary'}]}

    def test_drops_bare_primary_orphan_for_in_scope_wr(self):
        hist = {
            '90001|041926|primary|': {'hash': 'x'},   # legacy bare orphan
            '90001|041926|primary|Alice': {'hash': 'y'},  # new per-claimer (kept)
            '90002|041926|primary|': {'hash': 'z'},   # out-of-scope (kept)
        }
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertTrue(mutated)
        self.assertNotIn('90001|041926|primary|', hist)
        self.assertIn('90001|041926|primary|Alice', hist)
        self.assertIn('90002|041926|primary|', hist)
        self.assertEqual(
            hist['_subproject_d_prune_version'],
            gwp.SUBPROJECT_D_HASH_PRUNE_VERSION,
        )

    def test_idempotent_second_run_is_noop(self):
        hist = {'_subproject_d_prune_version': gwp.SUBPROJECT_D_HASH_PRUNE_VERSION}
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertFalse(mutated)

    def test_kill_switch_off_skips_and_no_sentinel_advance(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        hist = {'90001|041926|primary|': {'hash': 'x'}}
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertFalse(mutated)
        # OFF: the bare key is the ACTIVE legacy format — must NOT be dropped.
        self.assertIn('90001|041926|primary|', hist)
        self.assertNotIn('_subproject_d_prune_version', hist)

    def test_call_site_wired_into_migration_dirty(self):
        src = inspect.getsource(generate_weekly_pdfs)
        self.assertRegex(
            src,
            r"if _run_subproject_d_hash_prune\(hash_history, groups\):"
            r"\s*\n\s*_hash_history_migration_dirty = True",
        )

    def test_non_primary_variant_not_dropped_for_in_scope_wr(self):
        # A helper-variant (6-part) and a vac_crew-variant key for an
        # IN-SCOPE WR must NOT be dropped — the prune is scoped to
        # variant=='primary' + empty-identifier 4-part keys only.
        hist = {
            '90001|041926|primary|': {'hash': 'x'},          # dropped
            '90001|041926|helper|Bob|500|J1': {'hash': 'h'},  # kept
            '90001|041926|vac_crew|': {'hash': 'v'},          # kept
        }
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertTrue(mutated)
        self.assertNotIn('90001|041926|primary|', hist)
        self.assertIn('90001|041926|helper|Bob|500|J1', hist)
        self.assertIn('90001|041926|vac_crew|', hist)

    def test_empty_history_advances_sentinel(self):
        hist = {}
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertTrue(mutated)
        self.assertEqual(
            hist['_subproject_d_prune_version'],
            gwp.SUBPROJECT_D_HASH_PRUNE_VERSION,
        )


class TestBarePrimaryCleanup(unittest.TestCase):
    """Task 10: forced bare-primary attachment cleanup on TARGET, gated +
    valid_wr_weeks-exempt."""

    def setUp(self):
        _ensure_smartsheet_mocked()

    def _att(self, name):
        a = mock.MagicMock()
        a.name = name
        a.id = name
        return a

    def _run(self, attachments, valid_wr_weeks, primary_wr_scope):
        client = mock.MagicMock()
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 1
        sheet.rows = [row]
        client.Attachments.list_row_attachments.return_value.data = attachments
        deleted = []
        client.Attachments.delete_attachment.side_effect = (
            lambda sid, aid: deleted.append(aid)
        )
        gwp.cleanup_untracked_sheet_attachments(
            client, 12345, valid_wr_weeks, False,
            target_sheet=sheet,
            primary_wr_scope=primary_wr_scope,
        )
        return deleted

    def test_in_scope_bare_primary_deleted(self):
        bare = self._att("WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        deleted = self._run([bare], valid_wr_weeks=set(), primary_wr_scope={'90001'})
        self.assertIn(bare.id, deleted)

    def test_live_per_claimer_not_deleted(self):
        live = self._att("WR_90001_WeekEnding_041926_120000_User_Alice_aaaaaaaaaaaaaaaa.xlsx")
        # Per-claimer file is identity ('90001','041926','primary','Alice');
        # it's in valid_wr_weeks this run and has a non-empty identifier.
        vww = {('90001', '041926', 'primary', 'Alice')}
        deleted = self._run([live], valid_wr_weeks=vww, primary_wr_scope={'90001'})
        self.assertNotIn(live.id, deleted)

    def test_overlapping_live_bare_exempt_via_valid_wr_weeks(self):
        # A bare primary whose identity IS in valid_wr_weeks (e.g. OFF for
        # those rows) must be exempt.
        bare = self._att("WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        vww = {('90001', '041926', 'primary', None)}
        deleted = self._run([bare], valid_wr_weeks=vww, primary_wr_scope={'90001'})
        self.assertNotIn(bare.id, deleted)

    def test_out_of_scope_bare_primary_kept(self):
        bare = self._att("WR_90099_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        deleted = self._run([bare], valid_wr_weeks=set(), primary_wr_scope={'90001'})
        self.assertNotIn(bare.id, deleted)

    def test_none_scope_is_noop(self):
        bare = self._att("WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        deleted = self._run([bare], valid_wr_weeks=set(), primary_wr_scope=None)
        self.assertNotIn(bare.id, deleted)


class TestBuildGroupIdentityPrimaryUserRoundTrip(unittest.TestCase):
    """Task 11: parser round-trips D's _User_<claimer> primary filename."""

    def test_plain_claimer(self):
        self.assertEqual(
            gwp.build_group_identity(
                "WR_90001_WeekEnding_041926_120000_User_Alice_aaaaaaaaaaaaaaaa.xlsx"
            ),
            ('90001', '041926', 'primary', 'Alice'),
        )

    def test_underscored_claimer(self):
        self.assertEqual(
            gwp.build_group_identity(
                "WR_90001_WeekEnding_041926_120000_User_Jane_Smith_aaaaaaaaaaaaaaaa.xlsx"
            ),
            ('90001', '041926', 'primary', 'Jane_Smith'),
        )

    def test_bare_primary_still_parses(self):
        # OFF-mode legacy bare primary -> identifier None.
        self.assertEqual(
            gwp.build_group_identity(
                "WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx"
            ),
            ('90001', '041926', 'primary', None),
        )


class TestSubprojectDProductionInvariants(unittest.TestCase):
    """Task 11: source-grep guards for the four-site lockstep + matcher
    mirror + filename suffix + prune-kill-switch gate."""

    @classmethod
    def setUpClass(cls):
        with open(inspect.getsourcefile(generate_weekly_pdfs), encoding='utf-8') as f:
            cls.src = f.read()

    def test_filename_suffix_user_gated(self):
        # PR #223 Codex-P1 follow-up widened the primary suffix gate to also
        # require RES_GROUPING_MODE in ('helper','both') (TestPrimaryModeStaysBare),
        # so the kill switch and ``and _pf`` are no longer adjacent — tolerate
        # the interposed mode clause.
        self.assertRegex(
            self.src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED[\s\S]{0,120}and _pf"
            r"[\s\S]{0,200}_User_\{",
        )

    def test_wr_filter_matcher_has_user_clause(self):
        # Both matchers must carry the _USER_ prefix clause (count >= 2).
        self.assertGreaterEqual(
            self.src.count('startswith(f"{wr}_USER_")'), 2,
            "both _key_matches_wr and _key_matches_excluded_wr must match _USER_",
        )

    def test_prune_gated_on_kill_switch(self):
        # Window widened to 2000: Task 9 added a long docstring (~1824 chars)
        # between the def line and the kill-switch guard. The structural
        # invariant (kill-switch early-return) is present and correct in
        # production; only the scan window needed adjustment.
        self.assertRegex(
            self.src,
            r"def _run_subproject_d_hash_prune[\s\S]{0,2000}"
            r"if not PRIMARY_CLAIM_ATTRIBUTION_ENABLED:\s*\n\s*return False",
        )

    def test_prune_wired_into_call_site(self):
        self.assertIn("_run_subproject_d_hash_prune(hash_history, groups)", self.src)

    def test_cleanup_has_primary_wr_scope_param(self):
        self.assertIn("primary_wr_scope: set[str] | None = None", self.src)


class TestBuildGroupIdentityReservedTokenInClaimerName(unittest.TestCase):
    """Final-review Issue #1 fix: a bare _User_<claimer> primary file whose
    CLAIMER NAME contains a reserved token (Helper / VacCrew / ReducedSub /
    AEPBillable) must parse as 'primary' with the full claimer, not be
    misclassified by the variant scan. Generalizes the reserved-token-
    parse-order rule (ledger [2026-05-21 13:20]) to the bare _User_ shape.
    The parser now dispatches on the EARLIEST reserved-token position."""

    _H = 'aaaaaaaaaaaaaaaa'  # 16-char hash

    def _bgi(self, suffix):
        return gwp.build_group_identity(
            f"WR_90001_WeekEnding_041926_120000_{suffix}_{self._H}.xlsx"
        )

    # --- primary claimer NAME contains a reserved token (the bug) ---
    def test_primary_claimer_named_helper(self):
        self.assertEqual(self._bgi('User_Pat_Helper'),
                         ('90001', '041926', 'primary', 'Pat_Helper'))

    def test_primary_claimer_named_vaccrew(self):
        self.assertEqual(self._bgi('User_VacCrew_Joe'),
                         ('90001', '041926', 'primary', 'VacCrew_Joe'))

    def test_primary_claimer_named_reducedsub(self):
        self.assertEqual(self._bgi('User_ReducedSub_Bob'),
                         ('90001', '041926', 'primary', 'ReducedSub_Bob'))

    def test_primary_claimer_named_aepbillable(self):
        self.assertEqual(self._bgi('User_AEPBillable_Sue'),
                         ('90001', '041926', 'primary', 'AEPBillable_Sue'))

    # --- inverse guards: helper/vac/sub members NAMED 'User' still parse right ---
    def test_helper_named_user(self):
        self.assertEqual(self._bgi('Helper_User_Smith'),
                         ('90001', '041926', 'helper', 'User_Smith'))

    def test_vaccrew_named_user(self):
        self.assertEqual(self._bgi('VacCrew_User_Jones'),
                         ('90001', '041926', 'vac_crew', 'User_Jones'))

    # --- regression guards: B/C normal two-level shapes unchanged ---
    def test_reducedsub_user_normal(self):
        self.assertEqual(self._bgi('ReducedSub_User_Alice'),
                         ('90001', '041926', 'reduced_sub', 'Alice'))

    def test_aepbillable_helper_normal(self):
        self.assertEqual(self._bgi('AEPBillable_Helper_Jane'),
                         ('90001', '041926', 'aep_billable_helper', 'Jane'))

    def test_reducedsub_helper_normal(self):
        self.assertEqual(self._bgi('ReducedSub_Helper_Jane'),
                         ('90001', '041926', 'reduced_sub_helper', 'Jane'))

    def test_legacy_bare_vaccrew(self):
        self.assertEqual(self._bgi('VacCrew'),
                         ('90001', '041926', 'vac_crew', ''))

    def test_bare_primary_no_marker(self):
        # No reserved token at all -> bare primary, identifier None.
        self.assertEqual(
            gwp.build_group_identity(
                f"WR_90001_WeekEnding_041926_120000_{self._H}.xlsx"
            ),
            ('90001', '041926', 'primary', None),
        )


class TestHistoricalClaimerRegression(unittest.TestCase):
    """Phase 2 REQ-2/6b: historical (>8-week-old) group resolves REAL frozen
    claimer after the bulk-prefetch fix. RED before fix (ATTRIBUTION_RESOLUTION_WEEKS
    scope gate returned Unknown_Foreman / _NO_MATCH for out-of-scope weeks);
    GREEN after (bulk map covers exact run set, no recency gate).

    Evidence anchor: incident run 26439205107 — 372 garbage files
    (131 _User__NO_MATCH, 241 _User_Unknown_Foreman) concentrated in old
    weeks, because ATTRIBUTION_RESOLUTION_WEEKS=8 excluded those weeks from
    the per-row pre-pass. attribution_snapshot had the real names all along.

    Behavioral keystone: drives group_source_rows with a historical completed
    primary row + a mocked _attr_map carrying frozen primary_foreman='Real Name'
    and asserts the emitted primary group key contains _USER_Real_Name (not
    _USER__NO_MATCH / Unknown_Foreman). RED against pre-Task-2 code (the
    scope gate excluded the historical row's pair from the pre-pass map).
    GREEN after Task 2 removes ATTRIBUTION_RESOLUTION_WEEKS entirely.

    NOTE: resolver-level historical-claimer assertions
    (resolve_claimer(prefetched_map={...}) -> ('use','Real Name','frozen'))
    are owned by Plan 01's ResolveClaimerMapAwareTests (Wave 1). This class
    adds ONLY the behavioral group_source_rows-driven keystone.
    """

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'mode': gwp.RES_GROUPING_MODE,
            'sub': set(gwp._FOLDER_DISCOVERED_SUB_IDS),
        }
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()
        gwp._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub'])

    def _make_historical_primary_row(self, row_id=9999, wr='90001'):
        """Build a completed primary row with a week_ending >20 weeks in the past."""
        import datetime
        old_date = datetime.date.today() - datetime.timedelta(weeks=20)
        return {
            '__row_id': row_id,
            '__source_sheet_id': 99999,  # NOT in _FOLDER_DISCOVERED_SUB_IDS
            '__effective_user': 'Unknown Foreman',
            '__is_helper_row': False,
            '__is_vac_crew': False,
            'Work Request #': wr,
            'Weekly Reference Logged Date': old_date.isoformat(),
            'Units Completed?': True,
            'Units Total Price': 100.0,
            'Dept #': '500',
            'Job #': 'J-1',
        }

    def test_historical_group_emits_real_claimer_key(self):
        """GREEN after fix: a >20-week-old row gets the real frozen claimer.

        RED before fix: ATTRIBUTION_RESOLUTION_WEEKS=8 caused the pre-pass
        to skip historical rows, so _primary_claimer_map had no entry -> the
        emission fell back to 'Unknown Foreman', producing
        _USER_Unknown_Foreman garbage keys (incident run 26439205107).

        After Task 2 removes the scope gate, the bulk map is built from ALL
        completed rows (exact-set, no recency gate), so the historical row's
        pair IS in the map and the frozen claimer ('Real Name') is used.
        """
        import datetime
        row = self._make_historical_primary_row(row_id=9999, wr='90001')
        old_date = datetime.date.today() - datetime.timedelta(weeks=20)

        # Provide a frozen map as if prefetch_attribution returned real data.
        frozen_map = {('90001', old_date, 9999): {'primary_foreman': 'Real Name'}}

        with mock.patch(
            'billing_audit.writer.prefetch_attribution',
            return_value=(frozen_map, 'success'),
        ):
            groups = gwp.group_source_rows([row])

        keys = list(groups.keys())
        # The key must contain 'Real_Name' (sanitized from 'Real Name').
        self.assertTrue(
            any('Real_Name' in k for k in keys),
            f"expected a _USER_Real_Name primary group, got {keys} "
            f"(evidence anchor: incident run 26439205107)",
        )
        # Must NOT contain garbage claimer tokens (the bug being fixed).
        self.assertFalse(
            any('_NO_MATCH' in k for k in keys),
            f"found _NO_MATCH in group keys {keys} — scope gate still active?",
        )
        self.assertFalse(
            any('Unknown_Foreman' in k for k in keys),
            f"found Unknown_Foreman in group keys {keys} — scope gate still active?",
        )

    def test_d_use_current_on_fetch_failure_not_hold(self):
        """D (primary) must use-current on bulk fetch_failure, never HOLD.

        Counterpart to the B/C direct-HOLD wiring test in the other modules.
        When _attr_status == 'fetch_failure', the D emission path falls back
        to the current effective_user ('CurrentFM') and generates the file
        — it never defers (HOLDs) a primary billing file.
        """
        row = self._make_historical_primary_row(row_id=8888, wr='90002')
        row['__effective_user'] = 'CurrentFM'

        with mock.patch(
            'billing_audit.writer.prefetch_attribution',
            return_value=({}, 'fetch_failure'),
        ):
            groups = gwp.group_source_rows([row])

        keys = list(groups.keys())
        # D must emit a primary key (use-current = CurrentFM or fallback name).
        primary_keys = [k for k in keys if 'primary' in k.lower()
                        or 'USER' in k or 'CurrentFM' in k
                        or 'Unknown_Foreman' in k]
        # At minimum, something emitted — D never HOLDs.
        emitted = [k for k in keys if '_90002' in k or '90002' in k]
        self.assertTrue(
            len(emitted) > 0,
            f"D should emit a primary group on fetch_failure, got keys={keys}",
        )
