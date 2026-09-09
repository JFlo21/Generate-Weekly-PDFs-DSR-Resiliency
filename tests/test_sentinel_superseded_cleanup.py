"""Phase 12 / OWN-02 follow-up (owner-approved 2026-09-01):

1. ``cleanup_untracked_sheet_attachments`` deletes a stale placeholder
   identity (``_User_Unknown_Foreman``, ``_Helper_Unknown_Helper``,
   ``_VacCrew_Unknown_VAC_Crew``, ``_User__NO_MATCH``) once a REAL-name
   identity for the SAME (wr, week, variant) is live this run — and never
   otherwise (same week only, same variant only, never when the sentinel
   is itself still produced, never on a bare primary).
2. ``RESET_WR_LIST`` scopes the unchanged-group skip gate to the listed
   WRs (``_reset_list_forces_regeneration``) instead of disabling it for
   the whole run, and its tokens are normalized to bare WR numbers
   (``_normalize_reset_wr``).

CR-01 (2026-09, Phase 12 plan 02): ``_is_sentinel_identifier`` no longer
treats every leading underscore as a sentinel. A real claimer name whose
raw form began with a space, apostrophe or parenthesis (``" O'Brien"``,
``"(Contractor) Smith"``, ``"'Ana Ruiz"``) sanitizes to a leading
underscore too (``pipeline/excel.py`` never ``.strip()``s before
sanitizing), and the old bare ``startswith('_')`` check could not tell
that apart from a sanitized Smartsheet error token — a false positive
that could delete a real person's billing attachment through the
sentinel-superseded gate below. The fix narrows the leading-underscore
branch to an explicit allowlist of sanitized error spellings.

Fixture style mirrors ``tests/test_orphaned_primary_attachment.py``. All
names are fictional (public-repo rule).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked  # noqa: E402

_ensure_smartsheet_mocked()

import generate_weekly_pdfs as gwp  # noqa: E402
from pipeline.cleanup import _is_sentinel_identifier  # noqa: E402
from pipeline.config import _normalize_reset_wr  # noqa: E402
from pipeline.orchestrate import _reset_list_forces_regeneration  # noqa: E402

_WR = '90001'
_WEEK = '041926'
_OTHER_WEEK = '042626'
_SHEET_ID = 5723337641643908

_STALE_UNKNOWN_PRIMARY = (
    'WR_90001_WeekEnding_041926_120000_User_Unknown_Foreman_aabbcc.xlsx'
)
_LIVE_REAL_PRIMARY = (
    'WR_90001_WeekEnding_041926_120001_User_Pat_Example_ddeeff.xlsx'
)
_STALE_UNKNOWN_HELPER = (
    'WR_90001_WeekEnding_041926_120000_Helper_Unknown_Helper_aabbcc.xlsx'
)
_LIVE_REAL_HELPER = (
    'WR_90001_WeekEnding_041926_120001_Helper_Sam_Sample_ddeeff.xlsx'
)
_STALE_UNKNOWN_VAC = (
    'WR_90001_WeekEnding_041926_120000_VacCrew_Unknown_VAC_Crew_aabbcc.xlsx'
)
_STALE_NO_MATCH_PRIMARY = (
    'WR_90001_WeekEnding_041926_120000_User__NO_MATCH_aabbcc.xlsx'
)
_LIVE_BARE_PRIMARY = 'WR_90001_WeekEnding_041926_120001_ddeeff.xlsx'


def _att(name: str, att_id: int) -> mock.MagicMock:
    att = mock.MagicMock()
    att.name = name
    att.id = att_id
    return att


def _client(deleted_ids: list[int]) -> mock.MagicMock:
    client = mock.MagicMock()

    def _delete(sheet_id, att_id):
        deleted_ids.append(att_id)
        return mock.MagicMock()

    client.Attachments.delete_attachment.side_effect = _delete
    return client


def _sheet(attachments: list) -> tuple[mock.MagicMock, dict]:
    sheet = mock.MagicMock()
    row = mock.MagicMock()
    row.id = 111
    sheet.rows = [row]
    return sheet, {111: attachments}


def _run_cleanup(attachments: list, valid_wr_weeks: set) -> list[int]:
    deleted: list[int] = []
    sheet, cache = _sheet(attachments)
    gwp.cleanup_untracked_sheet_attachments(
        client=_client(deleted),
        target_sheet_id=_SHEET_ID,
        valid_wr_weeks=valid_wr_weeks,
        test_mode=False,
        attachment_cache=cache,
        target_sheet=sheet,
    )
    return deleted


class SentinelIdentifierPredicateTests(unittest.TestCase):
    def test_placeholders_and_bare_primary(self) -> None:
        for token, expected in (
            ('Unknown_Foreman', True),
            ('Unknown_Helper', True),
            ('Unknown_VAC_Crew', True),
            ('_NO_MATCH', True),
            ('_REF_', True),        # sanitized '#REF!' (Codex, PR #377)
            ('_INVALID', True),     # sanitized '#INVALID'
            ('_ref_', True),        # case-insensitive (CR-01)
            ('_No_Match', True),    # case-insensitive (CR-01)
            ('Pat_Example', False),
            ('Sam_Sample', False),
            (None, False),
            ('', False),
        ):
            with self.subTest(token=token):
                self.assertIs(_is_sentinel_identifier(token), expected)

    def test_real_names_with_leading_punctuation_are_not_sentinels(self) -> None:
        """CR-01: a real name sanitized from a raw leading space,
        apostrophe or parenthesis must never classify as a sentinel."""
        for token in (
            '_O_Brien',              # sanitized " O'Brien"
            '_Contractor__Smith',    # sanitized "(Contractor) Smith"
            '_Ana_Ruiz',              # sanitized "'Ana Ruiz"
            '_Zorblatt',              # unrecognised leading-underscore token
        ):
            with self.subTest(token=token):
                self.assertIs(_is_sentinel_identifier(token), False)

    def test_non_string_and_whitespace_prefixed_tokens(self) -> None:
        """Review fix: a non-str token must not raise, and a
        whitespace-prefixed allowlisted spelling is still a sentinel."""
        self.assertIs(
            _is_sentinel_identifier(123),  # type: ignore[arg-type]
            False,
        )
        self.assertIs(_is_sentinel_identifier(' _REF_'), True)
        self.assertIs(_is_sentinel_identifier('_REF_'), True)


class SentinelSupersededCleanupTests(unittest.TestCase):
    """The gate fires only on: sentinel identity NOT live + real-name
    identity for the same (wr, week, variant) live."""

    def test_stale_unknown_primary_deleted_when_real_primary_live(self) -> None:
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_PRIMARY, 10), _att(_LIVE_REAL_PRIMARY, 20)],
            {(_WR, _WEEK, 'primary', 'Pat_Example')},
        )
        self.assertIn(10, deleted)
        self.assertNotIn(20, deleted)

    def test_stale_no_match_primary_deleted_when_real_primary_live(self) -> None:
        deleted = _run_cleanup(
            [_att(_STALE_NO_MATCH_PRIMARY, 10), _att(_LIVE_REAL_PRIMARY, 20)],
            {(_WR, _WEEK, 'primary', 'Pat_Example')},
        )
        self.assertIn(10, deleted)

    def test_stale_unknown_helper_deleted_when_real_helper_live(self) -> None:
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_HELPER, 10), _att(_LIVE_REAL_HELPER, 20)],
            {(_WR, _WEEK, 'helper', 'Sam_Sample')},
        )
        self.assertIn(10, deleted)
        self.assertNotIn(20, deleted)

    def test_unknown_still_produced_this_run_is_kept(self) -> None:
        # WR still unassigned: the sentinel identity is itself live.
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_PRIMARY, 10)],
            {(_WR, _WEEK, 'primary', 'Unknown_Foreman')},
        )
        self.assertNotIn(10, deleted)

    def test_unknown_kept_when_no_real_name_live_for_that_week(self) -> None:
        # Nothing about this WR/week processed this run -> untouched.
        deleted = _run_cleanup([_att(_STALE_UNKNOWN_PRIMARY, 10)], set())
        self.assertNotIn(10, deleted)

    def test_real_name_on_another_week_never_triggers(self) -> None:
        # Owner decision: ownership is never inherited across weeks.
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_PRIMARY, 10)],
            {(_WR, _OTHER_WEEK, 'primary', 'Pat_Example')},
        )
        self.assertNotIn(10, deleted)

    def test_real_name_on_another_variant_never_triggers(self) -> None:
        # A live real helper does not make an unknown PRIMARY stale
        # (that case belongs to the variant-migration orphan gate, which
        # requires a primary->helper migration, not a sentinel).
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_VAC, 10)],
            {(_WR, _WEEK, 'helper', 'Sam_Sample')},
        )
        self.assertNotIn(10, deleted)

    def test_live_sanitized_error_sibling_is_not_a_real_name(self) -> None:
        # A live '#REF!' claimer sanitizes to '_REF_' in the filename;
        # it must not count as the real-name replacement (Codex, PR #377).
        stale = _STALE_UNKNOWN_PRIMARY
        error_sib = 'WR_90001_WeekEnding_041926_120001_User__REF__ddeeff.xlsx'
        deleted = _run_cleanup(
            [_att(stale, 10), _att(error_sib, 20)],
            {(_WR, _WEEK, 'primary', '_REF_')},
        )
        self.assertNotIn(10, deleted)

    def test_unlisted_underscore_sibling_never_triggers(self) -> None:
        """Review fix (Phase 12 plan 02): an unlisted sanitized error
        spelling ('#DATE EXPECTED' -> '_DATE_EXPECTED') is neither a
        sentinel victim nor a real-name replacement -- nothing fires."""
        sib = (
            'WR_90001_WeekEnding_041926_120001_User__DATE_EXPECTED'
            '_ddeeff.xlsx'
        )
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_PRIMARY, 10), _att(sib, 20)],
            {(_WR, _WEEK, 'primary', '_DATE_EXPECTED')},
        )
        self.assertEqual(deleted, [])

    def test_underscore_real_name_sibling_is_neutral(self) -> None:
        """A real name that sanitized to a leading underscore (CR-01)
        is never deleted as a sentinel AND never acts as the replacement
        that deletes a stale sentinel file (fail-safe on both sides)."""
        sib = 'WR_90001_WeekEnding_041926_120001_User__O_Brien_ddeeff.xlsx'
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_PRIMARY, 10), _att(sib, 20)],
            {(_WR, _WEEK, 'primary', '_O_Brien')},
        )
        self.assertEqual(deleted, [])

    def test_live_bare_primary_is_not_a_real_name(self) -> None:
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_PRIMARY, 10), _att(_LIVE_BARE_PRIMARY, 20)],
            {(_WR, _WEEK, 'primary', None)},
        )
        self.assertNotIn(10, deleted)

    def test_live_sentinel_sibling_is_not_a_real_name(self) -> None:
        # Two placeholder spellings, neither real -> nothing fires.
        deleted = _run_cleanup(
            [_att(_STALE_NO_MATCH_PRIMARY, 10)],
            {(_WR, _WEEK, 'primary', 'Unknown_Foreman')},
        )
        self.assertNotIn(10, deleted)

    def test_real_name_generated_but_not_attached_keeps_sentinel(self) -> None:
        # Greptile (PR #377): the replacement was generated (so it is in
        # valid_wr_weeks) but its upload failed — it is NOT on the row.
        # The placeholder is still the only current report: keep it.
        deleted = _run_cleanup(
            [_att(_STALE_UNKNOWN_PRIMARY, 10)],
            {(_WR, _WEEK, 'primary', 'Pat_Example')},
        )
        self.assertNotIn(10, deleted)


class VariantMigrationOrphanHelper2Tests(unittest.TestCase):
    """Phase 14 plan 05: the orphan-supersede gate must treat a live
    Helper #2 claim (plain, AEP-billable shadow, reduced-sub shadow) the
    same way it already treats a Helper #1 claim -- a primary attachment
    superseded ONLY by one of these is a variant-migration orphan."""

    _STALE_PRIMARY_FOR_MIGRATION = (
        'WR_90001_WeekEnding_041926_120000_User_Bob_aabbcc.xlsx'
    )

    def test_primary_superseded_by_helper2_is_queued_for_deletion(self) -> None:
        deleted = _run_cleanup(
            [_att(self._STALE_PRIMARY_FOR_MIGRATION, 10)],
            {(_WR, _WEEK, 'helper2', 'Sam_Sample')},
        )
        self.assertIn(10, deleted)

    def test_primary_superseded_by_aep_billable_helper2_is_queued_for_deletion(
        self,
    ) -> None:
        deleted = _run_cleanup(
            [_att(self._STALE_PRIMARY_FOR_MIGRATION, 10)],
            {(_WR, _WEEK, 'aep_billable_helper2', 'Sam_Sample')},
        )
        self.assertIn(10, deleted)

    def test_primary_superseded_by_reduced_sub_helper2_is_queued_for_deletion(
        self,
    ) -> None:
        deleted = _run_cleanup(
            [_att(self._STALE_PRIMARY_FOR_MIGRATION, 10)],
            {(_WR, _WEEK, 'reduced_sub_helper2', 'Sam_Sample')},
        )
        self.assertIn(10, deleted)

    def test_primary_with_no_helper_sibling_of_any_kind_is_untouched(
        self,
    ) -> None:
        """A primary with no live helper-family sibling (Helper #1 or
        Helper #2) for the same WR/week is left alone, exactly as
        today."""
        deleted = _run_cleanup(
            [_att(self._STALE_PRIMARY_FOR_MIGRATION, 10)],
            set(),
        )
        self.assertNotIn(10, deleted)

    def test_helper2_attachment_never_matched_by_legacy_sub_offcontract_gate(
        self,
    ) -> None:
        """The one-time legacy migration gate for subcontractor off-contract
        variants (production value ``{'helper', 'primary'}``, per this
        function's own docstring) must never widen to catch a Helper #2
        identity -- Helper #2 is a brand-new identity, never a legacy
        off-contract leftover, and this plan makes zero changes to that
        gate's matching logic."""
        helper2_att = _att(
            'WR_90001_WeekEnding_041926_120000_Helper2_Sam_Sample_aabbcc.xlsx',
            10,
        )
        deleted: list[int] = []
        sheet, cache = _sheet([helper2_att])
        gwp.cleanup_untracked_sheet_attachments(
            client=_client(deleted),
            target_sheet_id=_SHEET_ID,
            valid_wr_weeks=set(),
            test_mode=False,
            attachment_cache=cache,
            target_sheet=sheet,
            sub_wr_scope={_WR},
            sub_offcontract_variants={'helper', 'primary'},
        )
        self.assertNotIn(10, deleted)

    def test_helper2_attachment_produced_this_run_is_never_swept(self) -> None:
        """An older Helper #2 attachment for the same identity is pruned
        by the ordinary newest-wins dedup (unrelated to this plan), but
        the fresh one produced this run survives."""
        stale = _att(
            'WR_90001_WeekEnding_041926_120000_Helper2_Sam_Sample_aabbcc.xlsx',
            10,
        )
        fresh = _att(
            'WR_90001_WeekEnding_041926_120001_Helper2_Sam_Sample_ddeeff.xlsx',
            20,
        )
        deleted = _run_cleanup(
            [stale, fresh],
            {(_WR, _WEEK, 'helper2', 'Sam_Sample')},
        )
        self.assertNotIn(20, deleted)

    def test_placeholder_helper2_swept_by_existing_sentinel_gate(self) -> None:
        """A placeholder Helper #2 identity not produced this run is swept
        by the pre-existing, variant-agnostic sentinel-superseded gate
        (``_is_sentinel_identifier`` -> ``billing_audit.writer.
        is_sentinel_claimer``, which already recognizes 'unknown helper 2'
        per plan 14-01/14-03) once a real-name Helper #2 sibling is live
        this run -- no new detection function required."""
        stale_placeholder = _att(
            'WR_90001_WeekEnding_041926_120000_Helper2_Unknown_Helper_2'
            '_aabbcc.xlsx',
            10,
        )
        live_real_helper2 = _att(
            'WR_90001_WeekEnding_041926_120001_Helper2_Sam_Sample_ddeeff.xlsx',
            20,
        )
        deleted = _run_cleanup(
            [stale_placeholder, live_real_helper2],
            {(_WR, _WEEK, 'helper2', 'Sam_Sample')},
        )
        self.assertIn(10, deleted)
        self.assertNotIn(20, deleted)


class Helper2RollbackProtectionTests(unittest.TestCase):
    """D-14-12 (rollback preserves Helper #2 evidence): a cleanup pass
    must never queue an existing Helper #2 attachment for deletion just
    because ``HELPER2_ENABLED`` is off and it was therefore not
    regenerated this run. ``pipeline/cleanup.py`` has zero coupling to
    the flag -- these tests prove that lack of coupling holds in
    practice for both flag values, not merely by code inspection."""

    _ROLLBACK_HELPER2 = (
        'WR_90001_WeekEnding_041926_120000_Helper2_Sam_Sample_aabbcc.xlsx'
    )

    def test_helper2_attachment_survives_cleanup_with_flag_off(self) -> None:
        from pipeline.config import HELPER2_ENABLED as _flag

        self.assertIs(
            _flag,
            False,
            'Precondition: HELPER2_ENABLED must be at its documented '
            'default-off value for this rollback test to be meaningful.',
        )
        deleted = _run_cleanup([_att(self._ROLLBACK_HELPER2, 10)], set())
        self.assertNotIn(10, deleted)

    def test_helper2_attachment_survives_cleanup_with_flag_on(self) -> None:
        """Symmetry check: survival is not an artifact of the flag's
        current value -- a Helper #2 attachment produced under a prior
        flag=on run that simply is not in THIS run's ``valid_wr_weeks``
        survives identically regardless of the flag's live value."""
        with mock.patch('pipeline.config.HELPER2_ENABLED', True):
            deleted = _run_cleanup([_att(self._ROLLBACK_HELPER2, 10)], set())
        self.assertNotIn(10, deleted)


class ResetListScopeTests(unittest.TestCase):
    def test_normalize_strips_optional_wr_prefix(self) -> None:
        for token, expected in (
            ('91390001', '91390001'),
            (' 91390001 ', '91390001'),
            ('WR_91390001', '91390001'),
            ('wr_91390001', '91390001'),
            ('WR91390001', '91390001'),
            ('wr91390001', '91390001'),
            ('WRX', 'WRX'),          # not a WR-number prefix -> untouched
            ('12/34', '12_34'),      # same sanitizer as wr_num / filenames
            ('WR_12 34', '12_34'),   # (Codex, PR #377)
            ('', ''),
        ):
            with self.subTest(token=token):
                self.assertEqual(_normalize_reset_wr(token), expected)

    def test_only_listed_wr_forces_regeneration(self) -> None:
        reset = {'91390001'}
        self.assertTrue(_reset_list_forces_regeneration('91390001', reset))
        self.assertFalse(_reset_list_forces_regeneration('91390002', reset))

    def test_empty_or_missing_list_never_forces(self) -> None:
        self.assertFalse(_reset_list_forces_regeneration('91390001', set()))
        self.assertFalse(_reset_list_forces_regeneration('91390001', None))


if __name__ == '__main__':
    unittest.main()
