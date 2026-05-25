"""Sub-project D — primary-workflow primary claim attribution tests."""
import datetime
import inspect
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
        self.assertRegex(
            src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf"
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
