"""Phase 08 security follow-up (T-08-03) — SKIP_UPLOAD must gate deletes.

The D-05 live probe (SKIP_UPLOAD=true) deleted prior production
attachments because ``delete_old_excel_attachments`` ran
unconditionally in the upload worker while ``SKIP_UPLOAD`` gated only
the subsequent upload. These tests pin the fix: a ``dry_run`` flag on
``delete_old_excel_attachments`` that preserves the read-only skip
decision but never calls ``delete_attachment``, wired from the upload
worker as ``dry_run=SKIP_UPLOAD``.
"""
import inspect
import unittest
from unittest import mock

from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked

_ensure_smartsheet_mocked()

import generate_weekly_pdfs as gwp  # noqa: E402


class _FakeAtt:
    def __init__(self, name, id_):
        self.name = name
        self.id = id_


class TestDeleteOldDryRun(unittest.TestCase):
    """``dry_run=True`` must never mutate Smartsheet."""

    def setUp(self):
        self._saved_auth = gwp.SUPABASE_HASH_STORE_AUTHORITATIVE

    def tearDown(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = self._saved_auth

    def _client(self):
        c = mock.Mock()
        c.Attachments.delete_attachment.return_value = None
        return c

    def _row(self):
        r = mock.Mock()
        r.id = 99
        return r

    def test_dry_run_preserves_matching_prior_attachment(self):
        # Authoritative mode (production): a changed group would
        # normally delete the prior same-identity attachment. Under
        # dry_run the candidate must survive untouched.
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        att = _FakeAtt(
            "WR_90001_WeekEnding_041926_120000_deadbeefcafe0001.xlsx", 1)
        client = self._client()
        deleted, skipped = gwp.delete_old_excel_attachments(
            client, 123, self._row(), "90001", "041926",
            "newhash0000000000", variant="primary", identifier=None,
            cached_attachments=[att], dry_run=True)
        self.assertEqual((deleted, skipped), (0, False))
        client.Attachments.delete_attachment.assert_not_called()

    def test_dry_run_keeps_legacy_hash_skip_decision(self):
        # Legacy (non-authoritative) mode: the same-hash short-circuit
        # is a read-only decision and must still fire under dry_run.
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = False
        att = _FakeAtt(
            "WR_90001_WeekEnding_041926_120000_deadbeefcafe0001.xlsx", 1)
        client = self._client()
        deleted, skipped = gwp.delete_old_excel_attachments(
            client, 123, self._row(), "90001", "041926",
            "deadbeefcafe0001", variant="primary", identifier=None,
            cached_attachments=[att], dry_run=True)
        self.assertEqual((deleted, skipped), (0, True))
        client.Attachments.delete_attachment.assert_not_called()

    def test_dry_run_default_false_preserves_delete_behavior(self):
        # Callers that do not pass dry_run keep today's behavior.
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        att = _FakeAtt(
            "WR_90001_WeekEnding_041926_120000_deadbeefcafe0001.xlsx", 1)
        client = self._client()
        deleted, skipped = gwp.delete_old_excel_attachments(
            client, 123, self._row(), "90001", "041926",
            "newhash0000000000", variant="primary", identifier=None,
            cached_attachments=[att])
        self.assertEqual((deleted, skipped), (1, False))
        client.Attachments.delete_attachment.assert_called_once()


class TestCleanupUntrackedDryRun(unittest.TestCase):
    """``dry_run=True`` must short-circuit untracked-attachment pruning."""

    def test_dry_run_returns_before_any_sheet_mutation(self):
        client = mock.Mock()
        gwp.cleanup_untracked_sheet_attachments(
            client, 123, set(), False, dry_run=True)
        client.Attachments.delete_attachment.assert_not_called()
        client.Sheets.get_sheet.assert_not_called()


class TestPurgeDryRun(unittest.TestCase):
    """``dry_run=True`` must skip the remote purge (local reset only)."""

    def test_dry_run_skips_remote_attachment_purge(self):
        client = mock.Mock()
        gwp.purge_existing_hashed_outputs(
            client, 123, None, False, dry_run=True)
        client.Attachments.delete_attachment.assert_not_called()
        client.Sheets.get_sheet.assert_not_called()


class TestUploadWorkerWiresSkipUpload(unittest.TestCase):
    """Every Smartsheet-mutating cleanup path must receive
    dry_run=SKIP_UPLOAD from orchestrate."""

    def test_orchestrate_gates_delete_on_skip_upload(self):
        import pipeline.orchestrate as orch
        src = inspect.getsource(orch)
        call_start = src.index("delete_old_excel_attachments(",
                               src.index("def _upload_one"))
        call_src = src[call_start:call_start + 600]
        self.assertIn("dry_run=SKIP_UPLOAD", call_src)

    def test_orchestrate_gates_untracked_cleanup_and_purge(self):
        import pipeline.orchestrate as orch
        src = inspect.getsource(orch)
        # Two cleanup_untracked_sheet_attachments call sites (TARGET +
        # PPP) and two purge_existing_hashed_outputs call sites must
        # all pass dry_run=SKIP_UPLOAD.
        self.assertGreaterEqual(src.count("dry_run=SKIP_UPLOAD"), 5)


class TestRemediationGatesOnSkipUpload(unittest.TestCase):
    """PR #286 follow-up: the 6th mutating call site.

    The isolated REMEDIATE_CLAIMERS sweep calls
    ``run_claimer_remediation(..., dry_run=REMEDIATION_DRY_RUN)``
    without folding in SKIP_UPLOAD, so SKIP_UPLOAD=true +
    REMEDIATION_DRY_RUN=0 could still issue delete_attachment calls
    against production. This pins the fix: the effective dry_run must
    be ``REMEDIATION_DRY_RUN or SKIP_UPLOAD``.
    """

    def test_remediation_call_ors_in_skip_upload(self):
        import pipeline.orchestrate as orch
        src = inspect.getsource(orch)
        branch_start = src.index("if REMEDIATE_CLAIMERS:")
        branch_end = src.index("return", branch_start)
        branch_src = src[branch_start:branch_end]
        self.assertIn("REMEDIATION_DRY_RUN or SKIP_UPLOAD", branch_src)


if __name__ == "__main__":
    unittest.main()
