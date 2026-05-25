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
    week_serial=46100,  # arbitrary Excel serial -> a real date
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
