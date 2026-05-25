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
