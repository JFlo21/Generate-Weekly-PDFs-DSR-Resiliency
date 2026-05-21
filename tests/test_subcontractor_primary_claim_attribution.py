"""Subproject B — subcontractor primary claim attribution tests.

Drives the real production code paths (parser, group_source_rows
pre-pass + emission, generate_excel filename builder, migration
cleanup, hash prune, HOLD wiring) per the [2026-05-20 00:26] rule 4:
row-flow changes require TRUE end-to-end tests, not static mirrors.
"""

from __future__ import annotations

import datetime
import importlib
import inspect
import os
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import (
    _reset_all,
    _ensure_smartsheet_mocked,
)

_ensure_smartsheet_mocked()
import generate_weekly_pdfs  # noqa: E402


class TestBuildGroupIdentityParsesPrimaryUserToken(unittest.TestCase):
    """Task 1: _User_ token parses for reduced_sub / aep_billable."""

    def test_reducedsub_user_token_parses_claimer(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_User_John_Doe_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', 'John_Doe'))

    def test_aepbillable_user_token_parses_claimer(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_User_John_Doe_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'aep_billable', 'John_Doe'))

    def test_legacy_reducedsub_parses_empty_identifier(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', ''))

    def test_legacy_aepbillable_parses_empty_identifier(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'aep_billable', ''))

    def test_reducedsub_helper_still_parses_helper(self):
        # Regression: the new User branch must not break helper-shadow parsing.
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_Helper_Jane_Smith_def456.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub_helper', 'Jane_Smith'))


if __name__ == '__main__':
    unittest.main()
