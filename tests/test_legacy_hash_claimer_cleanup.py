"""End-to-end regression tests for the one-time legacy-hash cross-claimer
attachment cleanup migration (2026-05-27).

ROOT CAUSE (debug session ``legacy-attachment-cleanup``):
``cleanup_untracked_sheet_attachments`` dedups ONLY within a single identity
tuple ``(wr, week, variant, claimer)`` — it keeps the newest copy per identity
and never cross-deletes between different claimers (the Foundation A
"claimer-file coexistence / no-cross-delete" invariant). When the 2026-05-27
attribution fix corrected historical claimers (e.g. Wade Watson -> Mark Diaz),
the run ADDED the correct ``_User_Mark_Diaz`` file but the old
``_User_Wade_Watson_<ts>_<hash>`` file is a DIFFERENT identity -> kept forever
as a duplicate.

FIX: a one-time, kill-switch-gated cleanup (``LEGACY_HASH_CLAIMER_CLEANUP_ENABLED``,
default OFF) that — for each ``(wr, week, variant)`` for which a CLEAN-named
current file exists on the row — deletes the LEGACY HASH-NAMED attachments for
that same ``(wr, week, variant)`` REGARDLESS of claimer.

INVARIANTS the tests lock in:
- Two CLEAN-named claimers for the same (wr, week, variant) BOTH survive
  (no-cross-delete is intact — only HASH-named files are deletion-eligible).
- A hash-named file is deleted ONLY when a clean-named file exists for the
  same (wr, week, variant). A hash-named file with NO clean sibling is kept
  (the per-identity dedup still handles within-identity supersession).
- Gated on the dedicated kill switch (default OFF) -> byte-identical legacy
  behaviour when the flag is off.
- Applies to BOTH TARGET and PPP (PPP off-contract variants are pruned earlier
  by the variant whitelist, so this gate only ever sees in-whitelist variants).

[2026-05-26 01:45] rule 3: guard the smartsheet stub behind a try/import so
this module never shadows the real SDK during pytest collection.
"""
import sys
import unittest
from unittest import mock


def _ensure_smartsheet_mocked():
    if 'smartsheet' not in sys.modules:
        sys.modules['smartsheet'] = mock.MagicMock()


try:
    import smartsheet  # noqa: F401
except ImportError:
    _ensure_smartsheet_mocked()

import generate_weekly_pdfs as gwp  # noqa: E402
from generate_weekly_pdfs import build_group_identity  # noqa: E402


def _make_attachment(name: str, att_id: int):
    att = mock.MagicMock()
    att.name = name
    att.id = att_id
    return att


def _clean(wr, week, variant_suffix=""):
    """Sub-project-E clean filename: no timestamp / no hash."""
    if variant_suffix:
        return f"WR_{wr}_WeekEnding_{week}_{variant_suffix}.xlsx"
    return f"WR_{wr}_WeekEnding_{week}.xlsx"


def _legacy(wr, week, variant_suffix="", ts="143015", h="ab12cd34ef56ab78"):
    """Legacy token-bearing (hash-named) filename: 6-digit ts + trailing hash."""
    if variant_suffix:
        return f"WR_{wr}_WeekEnding_{week}_{ts}_{variant_suffix}_{h}.xlsx"
    return f"WR_{wr}_WeekEnding_{week}_{ts}_{h}.xlsx"


class _BaseCleanup(unittest.TestCase):
    """Drives the REAL cleanup_untracked_sheet_attachments against a single
    Smartsheet row holding a list of attachments."""

    def setUp(self):
        self.client = mock.MagicMock()
        # KEEP_HISTORICAL_WEEKS must be False so the dedup loop processes every
        # identity (production workflow pins it to 'false').
        self._kh = mock.patch.object(gwp, 'KEEP_HISTORICAL_WEEKS', False)
        self._kh.start()

    def tearDown(self):
        self._kh.stop()

    def _run(self, attachments, *, sheet_id=5723337641643908,
             legacy_hash_cleanup=True, valid_wr_weeks=None,
             variant_whitelist=None):
        if valid_wr_weeks is None:
            # By default, mark every clean-named file as a live identity (mirrors
            # production: the current run generated the clean file this session).
            valid_wr_weeks = set()
            for att in attachments:
                if not gwp._is_legacy_hash_named(att.name):
                    ident = build_group_identity(att.name)
                    if ident:
                        valid_wr_weeks.add(ident)

        row = mock.MagicMock()
        row.id = 1
        sheet = mock.MagicMock()
        sheet.rows = [row]

        resp = mock.MagicMock()
        resp.data = attachments
        self.client.Attachments.list_row_attachments.return_value = resp

        gwp.cleanup_untracked_sheet_attachments(
            self.client,
            sheet_id,
            valid_wr_weeks,
            False,  # test_mode
            target_sheet=sheet,
            variant_whitelist=variant_whitelist,
            legacy_hash_cleanup=legacy_hash_cleanup,
        )

        calls = self.client.Attachments.delete_attachment.call_args_list
        return {c[0][1] for c in calls if c[0] and len(c[0]) >= 2}


class TestLegacyHashNamedDetector(unittest.TestCase):
    """_is_legacy_hash_named: the 6-digit-timestamp-after-week discriminator."""

    def test_clean_name_is_not_legacy(self):
        self.assertFalse(
            gwp._is_legacy_hash_named(_clean("90727774", "030126",
                                             "ReducedSub_User_Mark_Diaz")))

    def test_legacy_name_is_legacy(self):
        self.assertTrue(
            gwp._is_legacy_hash_named(_legacy("90727774", "030126",
                                              "ReducedSub_User_Wade_Watson")))

    def test_clean_bare_primary_is_not_legacy(self):
        self.assertFalse(gwp._is_legacy_hash_named(_clean("90001", "041926")))

    def test_legacy_bare_primary_is_legacy(self):
        self.assertTrue(gwp._is_legacy_hash_named(_legacy("90001", "041926")))

    def test_non_wr_filename_is_not_legacy(self):
        self.assertFalse(gwp._is_legacy_hash_named("random_143015_file.xlsx"))


class TestLegacyHashCrossClaimerCleanup(_BaseCleanup):
    """The CORE fix: a legacy hash-named wrong-claimer file is deleted when a
    clean-named current file exists for the same (wr, week, variant)."""

    def test_legacy_wrong_claimer_deleted_when_clean_sibling_exists(self):
        clean = _clean("90727774", "030126", "ReducedSub_User_Mark_Diaz")
        legacy = _legacy("90727774", "030126", "ReducedSub_User_Wade_Watson")
        deleted = self._run([
            _make_attachment(clean, 1),
            _make_attachment(legacy, 2),
        ])
        self.assertNotIn(1, deleted, "clean current file must survive")
        self.assertIn(2, deleted, "legacy wrong-claimer hash file must be deleted")

    def test_legacy_primary_user_cross_claimer_deleted(self):
        clean = _clean("90001", "041926", "User_Mark_Diaz")
        legacy = _legacy("90001", "041926", "User_Wade_Watson")
        deleted = self._run([
            _make_attachment(clean, 10),
            _make_attachment(legacy, 11),
        ])
        self.assertNotIn(10, deleted)
        self.assertIn(11, deleted)


class TestNoCrossDeleteInvariantPreserved(_BaseCleanup):
    """Two CLEAN-named claimers for the same (wr, week, variant) must BOTH
    survive — the Foundation A no-cross-delete invariant is untouched."""

    def test_two_clean_claimers_both_survive(self):
        a = _clean("90001", "041926", "User_Alice_Smith")
        b = _clean("90001", "041926", "User_Bob_Jones")
        deleted = self._run([
            _make_attachment(a, 20),
            _make_attachment(b, 21),
        ])
        self.assertEqual(deleted, set(),
                         "neither clean claimer is hash-named -> both survive")

    def test_legacy_with_no_clean_sibling_is_kept(self):
        """A legacy hash file with NO clean sibling for its (wr, week, variant)
        is NOT cross-deleted — only within-identity dedup applies (one file)."""
        legacy = _legacy("90002", "041926", "User_Wade_Watson")
        deleted = self._run([_make_attachment(legacy, 30)])
        self.assertEqual(deleted, set(),
                         "no clean sibling -> legacy file is kept")


class TestKillSwitchOff(_BaseCleanup):
    """legacy_hash_cleanup=False -> byte-identical legacy behaviour (the legacy
    wrong-claimer file persists; only within-identity dedup runs)."""

    def test_off_preserves_legacy_wrong_claimer(self):
        clean = _clean("90727774", "030126", "ReducedSub_User_Mark_Diaz")
        legacy = _legacy("90727774", "030126", "ReducedSub_User_Wade_Watson")
        deleted = self._run(
            [_make_attachment(clean, 40), _make_attachment(legacy, 41)],
            legacy_hash_cleanup=False,
        )
        self.assertEqual(deleted, set(),
                         "flag off -> no cross-claimer deletion")


class TestWithinIdentityDedupStillWorks(_BaseCleanup):
    """Two legacy hash files for the SAME identity (same claimer) -> the older
    is still pruned by the existing within-identity dedup, independent of the
    new cross-claimer cleanup."""

    def test_same_claimer_older_legacy_pruned(self):
        newer = _legacy("90003", "041926", "User_Wade_Watson", ts="150000")
        older = _legacy("90003", "041926", "User_Wade_Watson", ts="090000")
        # No clean sibling -> cross-claimer cleanup does nothing; within-identity
        # dedup keeps newest (150000), removes older (090000).
        deleted = self._run([
            _make_attachment(newer, 50),
            _make_attachment(older, 51),
        ], valid_wr_weeks=set())
        self.assertNotIn(50, deleted)
        self.assertIn(51, deleted, "older same-identity legacy file pruned")


class TestPppRespectsWhitelist(_BaseCleanup):
    """On PPP (variant_whitelist={'reduced_sub', 'reduced_sub_helper'}), the
    cross-claimer cleanup deletes legacy reduced_sub wrong-claimer files when a
    clean sibling exists, and off-contract variants are pruned earlier by the
    whitelist (never reach the cross-claimer gate)."""

    def test_ppp_reduced_sub_cross_claimer_deleted(self):
        clean = _clean("90004", "041926", "ReducedSub_User_Mark_Diaz")
        legacy = _legacy("90004", "041926", "ReducedSub_User_Wade_Watson")
        deleted = self._run(
            [_make_attachment(clean, 60), _make_attachment(legacy, 61)],
            sheet_id=8162920222379908,
            variant_whitelist={'reduced_sub', 'reduced_sub_helper'},
        )
        self.assertNotIn(60, deleted)
        self.assertIn(61, deleted)


class TestEnvFlagWired(unittest.TestCase):
    """The kill switch exists, is a bool, and defaults OFF; workflow-pinned."""

    def test_flag_exists_and_is_bool(self):
        self.assertTrue(hasattr(gwp, 'LEGACY_HASH_CLAIMER_CLEANUP_ENABLED'))
        self.assertIsInstance(gwp.LEGACY_HASH_CLAIMER_CLEANUP_ENABLED, bool)

    def test_pii_marker_registered(self):
        self.assertIn(
            "Removed legacy hash-named cross-claimer attachment",
            gwp._PII_LOG_MARKERS,
        )


if __name__ == '__main__':
    unittest.main()
