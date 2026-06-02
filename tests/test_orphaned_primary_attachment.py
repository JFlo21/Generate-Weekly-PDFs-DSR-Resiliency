"""Regression test: orphaned primary attachment on helper attribution correction.

Bug scenario (orphaned-primary-attachment):
  Run 1: dual-checkbox helper row has helper_dept BLANK. Row fails helper
  qualification (needs both helper_dept AND helper_foreman), falls back to
  primary foreman group, primary Excel uploaded to TARGET Smartsheet row.

  Run 2: operator adds helper_dept. Row now qualifies as a helper row.
  Correct helper Excel generated + uploaded.

  BUG: The primary fallback attachment from Run 1 is NEVER deleted on Run 2.
  cleanup_untracked_sheet_attachments only removes attachments whose
  identity is still present in valid_wr_weeks (generated or processed
  this run). The primary group disappears from groups entirely when the
  row migrates to helper — so its identity is never added to
  valid_wr_weeks, and the variant-pruning loop keeps exactly one
  attachment per identity (the newest), meaning a lone orphaned primary
  attachment survives every subsequent run.

Fix target: cleanup_untracked_sheet_attachments (or its caller) must detect
  (wr, week, 'primary', identifier) identities that appear on Smartsheet
  but have NO corresponding group in the current run AND have a live helper
  attachment for the same (wr, week) — and delete the stale primary.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked, _reset_all  # noqa: E402

_ensure_smartsheet_mocked()

import generate_weekly_pdfs as gwp  # noqa: E402


def _make_attachment(name: str, att_id: int = 1):
    """Return a minimal mock Smartsheet attachment object."""
    att = mock.MagicMock()
    att.name = name
    att.id = att_id
    return att


def _make_sheet_row(row_id: int, attachments: list):
    """Return a minimal mock Smartsheet row."""
    row = mock.MagicMock()
    row.id = row_id
    return row


class TestOrphanedPrimaryAttachmentOnHelperMigration(unittest.TestCase):
    """cleanup_untracked_sheet_attachments must delete a primary attachment
    that became orphaned when its row migrated to a helper variant.

    Scenario:
      - TARGET row 111 holds two attachments on Run 2:
          (a) stale primary from Run 1:
              WR_90001_WeekEnding_041926_120000_User_Bob_aabbcc.xlsx
          (b) fresh helper from Run 2 (just uploaded):
              WR_90001_WeekEnding_041926_120001_Helper_HelpFM_ddeeff.xlsx
      - valid_wr_weeks for Run 2 contains ONLY the helper identity
        (wr=90001, week=041926, variant='helper', identifier='HelpFM').
      - The primary group no longer exists in groups (it vanished because
        the row migrated to helper).
      - Expected: cleanup deletes the stale primary attachment.
      - Pre-fix actual: cleanup keeps the stale primary (no duplicates to
        remove; identity not in valid_wr_weeks causes the loop to keep it).
    """

    WR = '90001'
    WEEK = '041926'
    SHEET_ID = 5723337641643908

    # Attachment filenames
    STALE_PRIMARY_NAME = (
        'WR_90001_WeekEnding_041926_120000_User_Bob_aabbcc.xlsx'
    )
    FRESH_HELPER_NAME = (
        'WR_90001_WeekEnding_041926_120001_Helper_HelpFM_ddeeff.xlsx'
    )

    def _make_client(self, deleted_ids: list):
        """Return a mock Smartsheet client; appends deleted attachment IDs
        to deleted_ids so the test can assert which were removed."""
        client = mock.MagicMock()

        def _delete_attachment(sheet_id, att_id):
            deleted_ids.append(att_id)
            return mock.MagicMock()

        client.Attachments.delete_attachment.side_effect = _delete_attachment
        return client

    def _make_sheet_with_row_and_attachments(self, attachments: list):
        """Return a mock sheet object with a single row carrying the given
        attachment list in the attachment_cache style."""
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 111
        sheet.rows = [row]
        return sheet, {111: attachments}

    def test_stale_primary_deleted_when_helper_exists_for_same_wr_week(self):
        """After a row migrates from primary to helper, the now-orphaned
        primary attachment must be deleted by cleanup."""
        stale_primary = _make_attachment(self.STALE_PRIMARY_NAME, att_id=10)
        fresh_helper = _make_attachment(self.FRESH_HELPER_NAME, att_id=20)

        sheet, cache = self._make_sheet_with_row_and_attachments(
            [stale_primary, fresh_helper]
        )

        # valid_wr_weeks: only the helper is live this run
        valid_wr_weeks = {
            (self.WR, self.WEEK, 'helper', 'HelpFM'),
        }

        deleted_ids: list[int] = []
        client = self._make_client(deleted_ids)

        gwp.cleanup_untracked_sheet_attachments(
            client=client,
            target_sheet_id=self.SHEET_ID,
            valid_wr_weeks=valid_wr_weeks,
            test_mode=False,
            attachment_cache=cache,
            target_sheet=sheet,
        )

        self.assertIn(
            10,
            deleted_ids,
            msg=(
                "Expected stale primary attachment (id=10, "
                f"{self.STALE_PRIMARY_NAME!r}) to be deleted when its "
                "identity is absent from valid_wr_weeks and a helper "
                "attachment for the same (WR, week) is live. "
                f"Actually deleted IDs: {deleted_ids}"
            ),
        )

    def test_live_primary_not_deleted_when_no_helper_for_same_wr_week(self):
        """A primary attachment must NOT be deleted when it IS in
        valid_wr_weeks (no migration occurred — it is still the live file)."""
        live_primary = _make_attachment(self.STALE_PRIMARY_NAME, att_id=10)

        sheet, cache = self._make_sheet_with_row_and_attachments(
            [live_primary]
        )

        # valid_wr_weeks: primary is live this run
        valid_wr_weeks = {
            (self.WR, self.WEEK, 'primary', 'Bob'),
        }

        deleted_ids: list[int] = []
        client = self._make_client(deleted_ids)

        gwp.cleanup_untracked_sheet_attachments(
            client=client,
            target_sheet_id=self.SHEET_ID,
            valid_wr_weeks=valid_wr_weeks,
            test_mode=False,
            attachment_cache=cache,
            target_sheet=sheet,
        )

        self.assertNotIn(
            10,
            deleted_ids,
            msg=(
                "Live primary attachment (id=10) must NOT be deleted "
                "when its identity IS in valid_wr_weeks."
            ),
        )

    def test_helper_not_deleted_when_primary_migrates_away(self):
        """The fresh helper attachment must survive cleanup even when the
        primary for the same (WR, week) is deleted as an orphan."""
        stale_primary = _make_attachment(self.STALE_PRIMARY_NAME, att_id=10)
        fresh_helper = _make_attachment(self.FRESH_HELPER_NAME, att_id=20)

        sheet, cache = self._make_sheet_with_row_and_attachments(
            [stale_primary, fresh_helper]
        )

        valid_wr_weeks = {
            (self.WR, self.WEEK, 'helper', 'HelpFM'),
        }

        deleted_ids: list[int] = []
        client = self._make_client(deleted_ids)

        gwp.cleanup_untracked_sheet_attachments(
            client=client,
            target_sheet_id=self.SHEET_ID,
            valid_wr_weeks=valid_wr_weeks,
            test_mode=False,
            attachment_cache=cache,
            target_sheet=sheet,
        )

        self.assertNotIn(
            20,
            deleted_ids,
            msg=(
                "Fresh helper attachment (id=20) must NOT be deleted; "
                "only the orphaned primary should be removed."
            ),
        )

    def test_build_group_identity_parses_stale_primary_correctly(self):
        """build_group_identity must parse the stale primary filename to
        (wr='90001', week='041926', variant='primary', identifier='Bob')."""
        result = gwp.build_group_identity(self.STALE_PRIMARY_NAME)
        self.assertIsNotNone(result, "build_group_identity must not return None")
        wr, week, variant, identifier = result  # type: ignore[misc]
        self.assertEqual(wr, self.WR)
        self.assertEqual(week, self.WEEK)
        self.assertEqual(variant, 'primary')
        self.assertEqual(identifier, 'Bob')

    def test_build_group_identity_parses_helper_correctly(self):
        """build_group_identity must parse the helper filename to
        (wr='90001', week='041926', variant='helper', identifier='HelpFM')."""
        result = gwp.build_group_identity(self.FRESH_HELPER_NAME)
        self.assertIsNotNone(result, "build_group_identity must not return None")
        wr, week, variant, identifier = result  # type: ignore[misc]
        self.assertEqual(wr, self.WR)
        self.assertEqual(week, self.WEEK)
        self.assertEqual(variant, 'helper')
        self.assertEqual(identifier, 'HelpFM')


if __name__ == '__main__':
    unittest.main()
