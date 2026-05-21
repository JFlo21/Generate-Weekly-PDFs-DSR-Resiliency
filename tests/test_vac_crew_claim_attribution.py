"""Sub-project C — VAC Crew claim attribution tests.

Drives real production code paths (parser, group_source_rows pre-pass +
emission, generate_excel, migration cleanup, hash prune, HOLD wiring) per
the [2026-05-20 00:26] rule 4: row-flow changes require TRUE end-to-end
tests, not static mirrors.
"""
from __future__ import annotations

import inspect
import pathlib
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked, _reset_all

_ensure_smartsheet_mocked()
import generate_weekly_pdfs  # noqa: E402
from billing_audit.writer import ResolveOutcome  # noqa: E402


class TestVacCrewConfigFlags(unittest.TestCase):
    def test_attribution_flag_exists_and_is_bool(self):
        self.assertIsInstance(
            generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED, bool
        )

    def test_attribution_flag_default_on(self):
        # Env var unset in the test harness → default '1' → True.
        self.assertTrue(generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED)

    def test_legacy_cleanup_flag_exists_and_is_bool(self):
        self.assertIsInstance(
            generate_weekly_pdfs.VAC_CREW_LEGACY_CLEANUP_ENABLED, bool
        )

    def test_legacy_cleanup_flag_default_on(self):
        self.assertTrue(generate_weekly_pdfs.VAC_CREW_LEGACY_CLEANUP_ENABLED)

    def test_flags_pinned_in_workflow(self):
        wf = (_REPO_ROOT / ".github/workflows/weekly-excel-generation.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("VAC_CREW_CLAIM_ATTRIBUTION_ENABLED", wf)
        self.assertIn("VAC_CREW_LEGACY_CLEANUP_ENABLED", wf)


class TestVacCrewSuffixAndParser(unittest.TestCase):
    def test_suffix_embeds_name(self):
        self.assertEqual(
            generate_weekly_pdfs._vac_crew_variant_suffix('John Smith', '91467680', '041926'),
            '_VacCrew_John_Smith',
        )

    def test_suffix_empty_claimer_raises(self):
        with self.assertRaises(ValueError):
            generate_weekly_pdfs._vac_crew_variant_suffix('', '91467680', '041926')

    def test_parser_vaccrew_name_round_trips(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_John_Smith_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', 'John_Smith'),
        )

    def test_parser_name_containing_helper_token_stays_vac_crew(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_Pat_Helper_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', 'Pat_Helper'),
        )

    def test_parser_legacy_vaccrew_no_name(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', ''),
        )
