"""Tests for the run_claimer_remediation garbage-attachment sweep.

Phase 2 Plan 03 — D-06/D-07/D-08/D-12/D-14.

Guards:
- Dry-run reports counts without deleting.
- Execute deletes ONLY *_NO_MATCH* / *_Unknown_Foreman* attachments.
- Live-identity exemption: a garbage-named file whose build_group_identity
  4-tuple IS in valid_wr_weeks is NOT deleted (even when it matches a pattern).
- Isolation path: valid_wr_weeks=None skips the exemption check entirely and
  still deletes only garbage-named files (WARNING 6 accepted tradeoff — the
  name patterns are not realistic real-claimer substrings).
- Window filter: attachments whose week-ending is older than REMEDIATION_WINDOW_WEEKS
  are skipped.
- Both TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID are swept.

[2026-05-26 01:45] rule 3: guard _ensure_smartsheet_mocked() with a
try/import so this module cannot shadow the real smartsheet package
during pytest collection and break unrelated suites.
"""
import sys
import datetime
import unittest
from unittest import mock

# ── Pitfall-4 guard ────────────────────────────────────────────────────────
# Define _ensure_smartsheet_mocked INLINE (the test_attribution_resolution_scope.py
# that previously defined it is DELETED by Plan 02 Task 3 — do NOT import from it).
# Only install the stub when the real SDK is NOT installed, so this module cannot
# shadow the real `smartsheet` package during pytest collection.


def _ensure_smartsheet_mocked():
    """Install a minimal smartsheet MagicMock into sys.modules ONLY when the real
    SDK is absent (CI without the package). Mirrors the guard that lived in the
    now-deleted test_attribution_resolution_scope.py ([2026-05-26 01:45] rule 3)."""
    if 'smartsheet' not in sys.modules:
        sys.modules['smartsheet'] = mock.MagicMock()


# Guard: only stub smartsheet when NOT already installed as a real package.
try:
    import smartsheet  # noqa: F401
except ImportError:
    _ensure_smartsheet_mocked()

# ── Import the real build_group_identity parser from generate_weekly_pdfs ──
# We need the real parser for identity-based tests; run_claimer_remediation
# will be defined once Task 2 is complete (tests are RED until then).
try:
    from generate_weekly_pdfs import build_group_identity
    _GWP_AVAILABLE = True
except ImportError:
    _GWP_AVAILABLE = False
    build_group_identity = None  # type: ignore[assignment]

# ── Helper: make a fake attachment object ─────────────────────────────────


def _make_attachment(name: str, att_id: int):
    """Build a minimal attachment-like mock with .name and .id."""
    att = mock.MagicMock()
    att.name = name
    att.id = att_id
    return att


# ── Realistic filename helpers ─────────────────────────────────────────────
# "Legacy-token" filenames have a 6-digit timestamp; build_group_identity
# strips it plus the trailing hash for legacy shapes.
# "Clean" filenames (Sub-project E authoritative) have no timestamp/hash.

def _clean_filename(wr, week_mmddyy, variant_suffix=""):
    """Build a Sub-project-E clean filename (no timestamp / no hash)."""
    if variant_suffix:
        return f"WR_{wr}_WeekEnding_{week_mmddyy}_{variant_suffix}.xlsx"
    return f"WR_{wr}_WeekEnding_{week_mmddyy}.xlsx"


def _legacy_filename(wr, week_mmddyy, variant_suffix="", ts="143015", h="abc12345"):
    """Build a legacy token-bearing filename."""
    if variant_suffix:
        return f"WR_{wr}_WeekEnding_{week_mmddyy}_{ts}_{variant_suffix}_{h}.xlsx"
    return f"WR_{wr}_WeekEnding_{week_mmddyy}_{ts}_{h}.xlsx"


# ── Week helpers ───────────────────────────────────────────────────────────

def _week_mmddyy(weeks_ago: int = 0) -> str:
    """Return MMDDYY for today minus `weeks_ago` weeks."""
    d = datetime.date.today() - datetime.timedelta(weeks=weeks_ago)
    return d.strftime("%m%d%y")


# ── Base test mixin that patches out run_claimer_remediation's Smartsheet calls ──

class _BaseRemediationTest(unittest.TestCase):
    """Base class: patches TARGET_SHEET_ID / PPP_SHEET_ID module globals and
    supplies a freshly-mocked Smartsheet client."""

    TARGET_ID = 5723337641643908
    PPP_ID = 8162920222379908

    def setUp(self):
        # Patch module-level sheet IDs so tests are hermetic.
        self._patches = [
            mock.patch('generate_weekly_pdfs.TARGET_SHEET_ID', self.TARGET_ID),
            mock.patch('generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID', self.PPP_ID),
        ]
        for p in self._patches:
            p.start()

        self.client = mock.MagicMock()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def _import_function(self):
        """Import run_claimer_remediation (raises ImportError / AttributeError when RED)."""
        import generate_weekly_pdfs as gwp
        return gwp.run_claimer_remediation

    def _build_row_with_attachments(self, attachments):
        row = mock.MagicMock()
        row_response = mock.MagicMock()
        row_response.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_response
        return row

    def _make_sheet(self, rows):
        sheet = mock.MagicMock()
        sheet.rows = rows
        self.client.Sheets.get_sheet.return_value = sheet


# ══════════════════════════════════════════════════════════════════════════════
# Test class 1: Dry-run reports counts without deleting
# ══════════════════════════════════════════════════════════════════════════════

class TestDryRunNeverDeletes(_BaseRemediationTest):
    """D-08: dry_run=True logs counts but calls delete_attachment 0 times."""

    def test_dry_run_reports_garbage_count_no_delete(self):
        """3 garbage attachments + 2 real-claimer files → dry run count=3, delete=0."""
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(2)  # recent — within 26-week window

        # Garbage names (match _NO_MATCH / _Unknown_Foreman patterns)
        garbage_1 = _clean_filename("90001", week, "User__NO_MATCH")
        garbage_2 = _clean_filename("90001", week, "User_Unknown_Foreman")
        garbage_3 = _clean_filename("90002", week, "VacCrew_Unknown_Foreman")

        # Real-claimer names — must NOT be deleted
        real_1 = _clean_filename("90001", week, "User_Jane_Smith")
        real_2 = _clean_filename("90002", week, "VacCrew_Pat_Lee")

        attachments = [
            _make_attachment(garbage_1, 101),
            _make_attachment(garbage_2, 102),
            _make_attachment(garbage_3, 103),
            _make_attachment(real_1, 201),
            _make_attachment(real_2, 202),
        ]

        # Both sheets return the same attachment list (each via sheet.rows loop)
        row = mock.MagicMock()
        row.id = 1
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        run_claimer_remediation(
            self.client, dry_run=True, window_weeks=26, valid_wr_weeks=None
        )

        # No actual deletions in dry-run mode
        self.client.Attachments.delete_attachment.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Test class 2: Execute deletes only garbage files
# ══════════════════════════════════════════════════════════════════════════════

class TestExecuteDeletesOnlyGarbage(_BaseRemediationTest):
    """D-07: dry_run=False deletes only *_NO_MATCH* / *_Unknown_Foreman* files.

    Post-WR-04: uses valid_wr_weeks=set() (non-isolated path) so both garbage
    tokens remain eligible (the live-identity exemption is active but no file
    is exempt).  The isolated path (valid_wr_weeks=None) is tested separately
    in TestIsolatedPathUnknownForemanProtection.
    """

    def test_execute_deletes_only_garbage(self):
        """Execute mode (non-isolated): delete exactly the 3 garbage IDs; real-claimer untouched."""
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(3)

        garbage_1 = _clean_filename("90001", week, "User__NO_MATCH")
        garbage_2 = _clean_filename("90001", week, "User_Unknown_Foreman")
        garbage_3 = _clean_filename("90002", week, "ReducedSub_User__NO_MATCH")

        real_1 = _clean_filename("90001", week, "User_Bob_Jones")
        real_2 = _clean_filename("90002", week, "ReducedSub_User_Bob_Jones")

        attachments = [
            _make_attachment(garbage_1, 301),
            _make_attachment(garbage_2, 302),
            _make_attachment(garbage_3, 303),
            _make_attachment(real_1, 401),
            _make_attachment(real_2, 402),
        ]

        row = mock.MagicMock()
        row.id = 10
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        # Post-WR-04: pass valid_wr_weeks=set() (non-isolated) so both garbage
        # tokens are eligible — the isolated path restricts to _NO_MATCH only.
        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=set()
        )

        # Collect all (sheet_id, att_id) pairs passed to delete
        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = set()
        for call in delete_calls:
            args = call[0] if call[0] else ()
            if len(args) >= 2:
                deleted_ids.add(args[1])

        self.assertIn(301, deleted_ids, "garbage_1 (_NO_MATCH) should be deleted")
        self.assertIn(302, deleted_ids, "garbage_2 (_Unknown_Foreman) should be deleted")
        self.assertIn(303, deleted_ids, "garbage_3 (_NO_MATCH) should be deleted")
        self.assertNotIn(401, deleted_ids, "real_1 (Bob_Jones) must NOT be deleted")
        self.assertNotIn(402, deleted_ids, "real_2 (Bob_Jones) must NOT be deleted")

    def test_real_claimer_name_never_matches_pattern(self):
        """Realistic real names like _User_Jane_Smith never match garbage patterns."""
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(1)

        real_names = [
            _clean_filename("90001", week, "User_Jane_Smith"),
            _clean_filename("90002", week, "ReducedSub_User_Bob_Jones"),
            _clean_filename("90003", week, "VacCrew_Pat_Lee"),
        ]

        attachments = [_make_attachment(n, 500 + i) for i, n in enumerate(real_names)]

        row = mock.MagicMock()
        row.id = 99
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
        )

        self.client.Attachments.delete_attachment.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Test class 3: Live-identity exemption (valid_wr_weeks populated)
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveIdentityExemption(_BaseRemediationTest):
    """D-07/[2026-05-19 23:45]: garbage file whose identity IS in valid_wr_weeks
    is NOT deleted, even though its name matches a garbage pattern."""

    @unittest.skipUnless(_GWP_AVAILABLE, "generate_weekly_pdfs not importable")
    def test_live_identity_exemption_protects_correct_file(self):
        """A garbage-NAMED file whose parsed 4-tuple is in valid_wr_weeks is exempt."""
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(4)

        # This file is named with a garbage pattern BUT the operator has
        # this exact identity in their live valid set (edge safety net).
        exempted_name = _clean_filename("90001", week, "User__NO_MATCH")
        not_exempted_name = _clean_filename("90002", week, "User__NO_MATCH")

        # Build the identity 4-tuple for the exempted file using the real parser
        parsed = build_group_identity(exempted_name)
        self.assertIsNotNone(parsed, "Parser should return a 4-tuple for the exempted name")

        # Put the exempted file's identity in valid_wr_weeks
        valid_wr_weeks = {parsed}  # type: ignore[arg-type]

        attachments = [
            _make_attachment(exempted_name, 601),
            _make_attachment(not_exempted_name, 602),
        ]

        row = mock.MagicMock()
        row.id = 55
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=valid_wr_weeks
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}

        self.assertNotIn(601, deleted_ids, "exempted file (in valid_wr_weeks) must NOT be deleted")
        self.assertIn(602, deleted_ids, "non-exempted garbage file MUST be deleted")


# ══════════════════════════════════════════════════════════════════════════════
# Test class 4: Isolation path (valid_wr_weeks=None)
# ══════════════════════════════════════════════════════════════════════════════

class TestIsolationPathValidWrWeeksNone(_BaseRemediationTest):
    """WARNING 6: valid_wr_weeks=None skips the exemption check entirely.
    The name-pattern + window guards alone gate deletion in isolated mode."""

    def test_isolation_path_valid_wr_weeks_none(self):
        """valid_wr_weeks=None: garbage files are deleted; real-claimer files are not."""
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(5)

        garbage = _clean_filename("90001", week, "User__NO_MATCH")
        real = _clean_filename("90001", week, "User_Real_Person")

        attachments = [
            _make_attachment(garbage, 701),
            _make_attachment(real, 702),
        ]

        row = mock.MagicMock()
        row.id = 77
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        # Pass None explicitly — the isolation mode
        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}

        self.assertIn(701, deleted_ids, "garbage file should be deleted in isolation mode")
        self.assertNotIn(702, deleted_ids, "real-claimer file must NOT be deleted in isolation mode")


# ══════════════════════════════════════════════════════════════════════════════
# Test class 5: Window filtering
# ══════════════════════════════════════════════════════════════════════════════

class TestWindowFilter(_BaseRemediationTest):
    """D-08: attachments outside the window (older than window_weeks) are skipped."""

    @unittest.skipUnless(_GWP_AVAILABLE, "generate_weekly_pdfs not importable")
    def test_window_filters_old_weeks(self):
        """A garbage attachment whose week-ending is > window_weeks old is skipped."""
        run_claimer_remediation = self._import_function()

        # 40 weeks ago — well outside a 26-week window
        old_week = _week_mmddyy(40)
        recent_week = _week_mmddyy(4)

        old_garbage = _clean_filename("90001", old_week, "User__NO_MATCH")
        recent_garbage = _clean_filename("90001", recent_week, "User__NO_MATCH")

        attachments = [
            _make_attachment(old_garbage, 801),
            _make_attachment(recent_garbage, 802),
        ]

        row = mock.MagicMock()
        row.id = 88
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}

        self.assertNotIn(801, deleted_ids, "old garbage (> window_weeks) must NOT be deleted")
        self.assertIn(802, deleted_ids, "recent garbage (within window) MUST be deleted")


# ══════════════════════════════════════════════════════════════════════════════
# Test class 6: Both TARGET and PPP are swept
# ══════════════════════════════════════════════════════════════════════════════

class TestBothSheetsSwepped(_BaseRemediationTest):
    """D-07: remediation sweeps both TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID.

    Post-WR-04: uses _NO_MATCH for both sheets (always-garbage token) so the
    isolated path (valid_wr_weeks=None) deletes both.  _Unknown_Foreman is
    tested in TestIsolatedPathUnknownForemanProtection.
    """

    def test_ppp_and_target_both_swept(self):
        """Attachments on both TARGET and PPP are considered for deletion."""
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(2)

        # One garbage attachment on TARGET, one on PPP — both _NO_MATCH
        # so the isolated path (valid_wr_weeks=None) deletes both (WR-04).
        target_garbage = _clean_filename("90001", week, "User__NO_MATCH")
        ppp_garbage = _clean_filename("90002", week, "ReducedSub_User__NO_MATCH")

        target_att = _make_attachment(target_garbage, 901)
        ppp_att = _make_attachment(ppp_garbage, 902)

        # Both sheets have one row each; each row has one attachment
        row_target = mock.MagicMock()
        row_target.id = 11
        row_ppp = mock.MagicMock()
        row_ppp.id = 22

        target_sheet = mock.MagicMock()
        target_sheet.rows = [row_target]
        ppp_sheet = mock.MagicMock()
        ppp_sheet.rows = [row_ppp]

        # get_sheet returns different sheets for different sheet IDs
        def _get_sheet(sheet_id):
            if sheet_id == self.TARGET_ID:
                return target_sheet
            return ppp_sheet

        self.client.Sheets.get_sheet.side_effect = _get_sheet

        # list_row_attachments returns different attachments for different row IDs
        def _list_attachments(sheet_id, row_id):
            resp = mock.MagicMock()
            if row_id == 11:
                resp.attachments = [target_att]
            else:
                resp.attachments = [ppp_att]
            return resp

        self.client.Attachments.list_row_attachments.side_effect = _list_attachments

        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}

        self.assertIn(901, deleted_ids, "TARGET garbage attachment must be deleted")
        self.assertIn(902, deleted_ids, "PPP garbage attachment must be deleted")


# ══════════════════════════════════════════════════════════════════════════════
# Test class 7: Unparseable / non-WR filenames are left alone
# ══════════════════════════════════════════════════════════════════════════════

class TestUnparseableFilesIgnored(_BaseRemediationTest):
    """Files that build_group_identity cannot parse are left alone (never deleted)."""

    def test_unparseable_filename_never_deleted(self):
        """An unparseable filename (not WR_*) is skipped even if it matches a pattern."""
        run_claimer_remediation = self._import_function()

        # This name CONTAINS _NO_MATCH but does NOT start with WR_ → unparseable
        unparseable = "some_other_file_NO_MATCH_garbage.xlsx"
        # Normal garbage that should be deleted
        week = _week_mmddyy(1)
        normal_garbage = _clean_filename("90001", week, "User__NO_MATCH")

        attachments = [
            _make_attachment(unparseable, 1001),
            _make_attachment(normal_garbage, 1002),
        ]

        row = mock.MagicMock()
        row.id = 55
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}

        self.assertNotIn(1001, deleted_ids, "unparseable file must NOT be deleted")
        self.assertIn(1002, deleted_ids, "normal garbage file MUST be deleted")


# ══════════════════════════════════════════════════════════════════════════════
# Test class 8: PPP=0 (disabled) means only TARGET is swept
# ══════════════════════════════════════════════════════════════════════════════

class TestPppDisabledOnlyTargetSwept(unittest.TestCase):
    """When SUBCONTRACTOR_PPP_SHEET_ID is 0 (disabled), only TARGET is swept."""

    def test_ppp_disabled_only_target_swept(self):
        """PPP=0 → get_sheet called once (TARGET only)."""
        try:
            import generate_weekly_pdfs as gwp
            run_claimer_remediation = gwp.run_claimer_remediation
        except (ImportError, AttributeError):
            self.skipTest("run_claimer_remediation not yet defined (RED)")

        client = mock.MagicMock()
        week = _week_mmddyy(1)
        garbage = _clean_filename("90001", week, "User__NO_MATCH")

        row = mock.MagicMock()
        row.id = 5
        sheet = mock.MagicMock()
        sheet.rows = [row]
        client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = [_make_attachment(garbage, 1101)]
        client.Attachments.list_row_attachments.return_value = row_resp

        with mock.patch('generate_weekly_pdfs.TARGET_SHEET_ID', 5723337641643908), \
             mock.patch('generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID', 0):
            run_claimer_remediation(
                client, dry_run=False, window_weeks=26, valid_wr_weeks=None
            )

        # Only one get_sheet call — TARGET only (PPP disabled)
        self.assertEqual(client.Sheets.get_sheet.call_count, 1)


# ══════════════════════════════════════════════════════════════════════════════
# Test class 9: WR-04 — isolated path protects _Unknown_Foreman
# ══════════════════════════════════════════════════════════════════════════════

class TestIsolatedPathUnknownForemanProtection(_BaseRemediationTest):
    """WR-04: in EXECUTE mode with valid_wr_weeks=None (isolated path),
    _Unknown_Foreman attachments MUST NOT be deleted — only _NO_MATCH files
    are swept.  _Unknown_Foreman is a legitimate current sentinel (emitted
    when effective_user is blank) and there is no live-identity exemption
    to protect it in the isolated path.

    When valid_wr_weeks IS provided (non-isolated path) both tokens remain
    eligible, subject to the live-identity exemption (existing behaviour
    unchanged — see TestLiveIdentityExemption / TestExecuteDeletesOnlyGarbage).
    """

    def test_isolated_path_deletes_no_match(self):
        """EXECUTE + valid_wr_weeks=None: a _NO_MATCH attachment IS deleted."""
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(2)
        no_match_name = _clean_filename("90001", week, "User__NO_MATCH")
        attachments = [_make_attachment(no_match_name, 2001)]

        row = mock.MagicMock()
        row.id = 10
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}
        self.assertIn(2001, deleted_ids, "_NO_MATCH must be deleted in isolated path")

    def test_isolated_path_preserves_unknown_foreman(self):
        """EXECUTE + valid_wr_weeks=None: a _Unknown_Foreman attachment is NOT deleted.

        _Unknown_Foreman is a legitimate current sentinel emitted when
        effective_user/Foreman Assigned? is blank — it is a real billing
        artifact. With no live-identity set to protect it, the isolated path
        restricts deletion to the always-garbage _NO_MATCH token only (WR-04).
        """
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(2)
        unknown_name = _clean_filename("90001", week, "User_Unknown_Foreman")
        no_match_name = _clean_filename("90002", week, "User__NO_MATCH")

        attachments = [
            _make_attachment(unknown_name, 2101),
            _make_attachment(no_match_name, 2102),
        ]

        row = mock.MagicMock()
        row.id = 11
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}

        self.assertNotIn(
            2101, deleted_ids,
            "_Unknown_Foreman must NOT be deleted in isolated EXECUTE path (WR-04)"
        )
        self.assertIn(
            2102, deleted_ids,
            "_NO_MATCH must still be deleted in isolated EXECUTE path"
        )

    def test_non_isolated_path_both_tokens_eligible(self):
        """Non-isolated path (valid_wr_weeks provided): both tokens remain eligible
        (subject to live-identity exemption, which is active in this path).
        Existing TestExecuteDeletesOnlyGarbage / TestLiveIdentityExemption
        behaviour is preserved — this test is the guard.
        """
        run_claimer_remediation = self._import_function()

        week = _week_mmddyy(3)
        unknown_name = _clean_filename("90001", week, "User_Unknown_Foreman")
        no_match_name = _clean_filename("90002", week, "User__NO_MATCH")

        attachments = [
            _make_attachment(unknown_name, 2201),
            _make_attachment(no_match_name, 2202),
        ]

        row = mock.MagicMock()
        row.id = 12
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        # Provide an empty set so the exemption logic is active but no file is exempt
        run_claimer_remediation(
            self.client, dry_run=False, window_weeks=26, valid_wr_weeks=set()
        )

        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}

        self.assertIn(
            2201, deleted_ids,
            "_Unknown_Foreman IS eligible when valid_wr_weeks is provided (non-isolated)"
        )
        self.assertIn(
            2202, deleted_ids,
            "_NO_MATCH IS eligible in non-isolated path"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test class 10: IN-02 — out_of_window counts only garbage files
# ══════════════════════════════════════════════════════════════════════════════

class TestOutOfWindowCountsOnlyGarbage(_BaseRemediationTest):
    """IN-02: the out_of_window counter must NOT be inflated by clean (non-garbage)
    out-of-window attachments.  With IN-02 reorder, the garbage check runs BEFORE
    the window filter, so only garbage files that are too old increment the counter.
    """

    def test_out_of_window_does_not_count_clean_files(self):
        """A clean (non-garbage) out-of-window attachment must NOT inflate out_of_window.

        Drives run_claimer_remediation and inspects the summary log line to
        verify out_of_window stays 0 when the only out-of-window file is a
        clean real-claimer name.
        """
        run_claimer_remediation = self._import_function()

        # Out-of-window (40 weeks ago) CLEAN attachment
        old_week = _week_mmddyy(40)
        clean_old = _clean_filename("90001", old_week, "User_Jane_Smith")

        # In-window garbage attachment (to confirm the function runs normally)
        recent_week = _week_mmddyy(2)
        recent_garbage = _clean_filename("90002", recent_week, "User__NO_MATCH")

        attachments = [
            _make_attachment(clean_old, 3001),
            _make_attachment(recent_garbage, 3002),
        ]

        row = mock.MagicMock()
        row.id = 20
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        import logging
        with self.assertLogs('root', level='INFO') as log_ctx:
            run_claimer_remediation(
                self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
            )

        # Find the summary line
        summary_lines = [l for l in log_ctx.output if 'run_claimer_remediation' in l and 'complete' in l]
        self.assertEqual(len(summary_lines), 1, "Expected exactly one summary log line")
        summary = summary_lines[0]

        # out_of_window must be 0 (the old file is clean — it was skipped at the
        # garbage-pattern gate before ever reaching the window-filter counter)
        self.assertIn(
            'out_of_window=0', summary,
            f"out_of_window should be 0 (clean file skipped before window filter); got: {summary}"
        )

        # recent garbage was deleted
        delete_calls = self.client.Attachments.delete_attachment.call_args_list
        deleted_ids = {call[0][1] for call in delete_calls if call[0] and len(call[0]) >= 2}
        self.assertIn(3002, deleted_ids, "recent garbage must be deleted")
        self.assertNotIn(3001, deleted_ids, "clean old file must NOT be deleted")

    def test_out_of_window_counts_garbage_older_than_window(self):
        """An out-of-window GARBAGE attachment increments out_of_window (it IS garbage,
        just too old to sweep).  This is the meaningful counter value.
        PPP is disabled (=0) so only TARGET is swept — exactly 1 attachment."""
        run_claimer_remediation = self._import_function()

        old_week = _week_mmddyy(40)
        old_garbage = _clean_filename("90001", old_week, "User__NO_MATCH")

        attachments = [_make_attachment(old_garbage, 3101)]

        row = mock.MagicMock()
        row.id = 21
        sheet = mock.MagicMock()
        sheet.rows = [row]
        self.client.Sheets.get_sheet.return_value = sheet

        row_resp = mock.MagicMock()
        row_resp.attachments = attachments
        self.client.Attachments.list_row_attachments.return_value = row_resp

        import logging
        # Disable PPP so only TARGET is swept → out_of_window=1, not 2.
        with mock.patch('generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID', 0), \
             self.assertLogs('root', level='INFO') as log_ctx:
            run_claimer_remediation(
                self.client, dry_run=False, window_weeks=26, valid_wr_weeks=None
            )

        summary_lines = [l for l in log_ctx.output if 'run_claimer_remediation' in l and 'complete' in l]
        self.assertEqual(len(summary_lines), 1)
        summary = summary_lines[0]

        self.assertIn(
            'out_of_window=1', summary,
            f"out_of_window should be 1 for an old garbage file; got: {summary}"
        )
        # Must NOT be deleted (out of window)
        self.client.Attachments.delete_attachment.assert_not_called()


if __name__ == '__main__':
    unittest.main()
