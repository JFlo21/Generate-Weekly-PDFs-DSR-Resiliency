"""RED regression for the WR 90922617 point-.11 VAC-crew leak.

Debug session: ``vac-crew-leak-foreman-sheet``.

Kept in a dedicated module (rather than appended to ``test_vac_crew.py``)
so the failing-test-first state is isolated and easy to run on its own:

    pytest tests/test_vac_crew_exclusion_leak.py -v

AUTHORITATIVE operator contract (session file, 2026-06-08):

  | Vac Crew Completed Unit? | Units Completed? | Helping Foreman Completed Unit? | Credited to        |
  |:------------------------:|:----------------:|:-------------------------------:|--------------------|
  | checked                  | (any)            | (any)                           | VAC crew ONLY      |
  | unchecked                | checked          | unchecked                       | Primary foreman    |
  | unchecked                | checked          | checked                         | Helper foreman     |
  | unchecked                | unchecked        | (any)                           | Nobody (not done)  |

  - ``Vac Crew Completed Unit?`` is the DOMINANT exclusion trigger and the
    VAC crew's OWN completion attestation. When checked (with a named VAC
    crew) the unit is credited to the VAC crew REGARDLESS of
    ``Units Completed?`` and REGARDLESS of any helper checkbox, and is
    EXCLUDED from BOTH the primary-foreman AND helping-foreman sheets
    (line items AND totals).
  - A VAC-claimed unit with ``Units Completed?`` UNchecked must STILL be
    credited to the VAC crew, so it must REACH the _VacCrew file. The intake
    (acceptance) gate must therefore admit a row when
    ``units_completed_checked OR <row carries a VAC claim>``. NARROW widening
    — admitted VAC-claimed rows route ONLY to the VacCrew variant, never to
    foreman/helper.

Fix contract under test:

  * A single pure row-level predicate
    ``generate_weekly_pdfs._is_vac_crew_excluded_row(row_data,
    sheet_has_vac_crew_columns)`` returning
    ``bool(vac_crew_name and vac_crew_completed_checked)`` — the
    ``units_completed_checked`` term is DROPPED. This is the ONE source of
    truth consumed by ``group_source_rows`` line-item routing AND
    ``validate_group_totals`` per-group totals (req #3).
  * The acceptance gate admits ``units_completed_checked OR vac_claim``.
  * Multi-page (req #4): the leaked User-sheet line item for point .11
    originates from a SEPARATE source row than the VacCrew row (one row ->
    one group at the clean if/else routing). The row-local predicate closes
    the case where that foreman-side row ITSELF carries the VAC signal
    (VAC box checked, Units Completed? unchecked). The remaining case — the
    foreman-side row does NOT carry the VAC signal at all — requires a
    point-level (WR + Pole #) reconciliation; that test is marked
    ``expectedFailure`` and documents the design pending operator sign-off.

The predicate does not exist yet, so every assertion that depends on it is
RED until the fix lands — the intended failing-test-first state.
"""

import unittest

import generate_weekly_pdfs


class TestVacCrewExclusionSingleSourceOfTruth(unittest.TestCase):
    """Predicate-level RED: exclusion ignores ``Units Completed?`` and the
    per-page VAC-columns gate, while preserving the inverse correct cases."""

    def _predicate(self):
        # Resolved lazily so the AttributeError (predicate not yet defined)
        # surfaces as a clear RED failure on the real fix contract rather
        # than an import-time collection error for the whole module.
        return getattr(
            generate_weekly_pdfs, '_is_vac_crew_excluded_row', None
        )

    def _vac_row(self, units_completed):
        """A point-.11-shaped row: VAC checkbox checked, VAC helper named."""
        return {
            'Work Request #': '90922617',
            'Weekly Reference Logged Date': '2026-06-07',
            'Pole #': '.11',
            'Units Total Price': '$1234.56',
            'Units Completed?': units_completed,
            'VAC Crew Helping?': 'Hugo Garcia',
            'Vac Crew Completed Unit?': True,
            'VAC Crew Dept #': '4100',
            'Vac Crew Job #': 'J-11',
            'Foreman': 'Chris Higginbotham',
            '__effective_user': 'Chris Higginbotham',
        }

    def test_predicate_exists(self):
        """The single-source-of-truth predicate must exist (fix contract)."""
        self.assertIsNotNone(
            self._predicate(),
            "generate_weekly_pdfs._is_vac_crew_excluded_row is not defined — "
            "requirement #3 needs ONE row-level exclusion flag shared by the "
            "line-item filter and the totals aggregation."
        )

    def test_vac_excluded_when_units_completed_true(self):
        """VAC checkbox true + Units Completed? true -> excluded (the .11 case)."""
        pred = self._predicate()
        self.assertIsNotNone(pred, "predicate missing — see test_predicate_exists")
        self.assertTrue(
            pred(self._vac_row(units_completed=True), True),
            "Point .11 (VAC checked, Units Completed checked) must be EXCLUDED "
            "from the foreman sheet."
        )

    def test_vac_excluded_when_units_completed_FALSE(self):
        """Contract row 1: exclusion holds even when ``Units Completed?`` is
        UNchecked. This is the Lead-1 detection-conjunction leak."""
        pred = self._predicate()
        self.assertIsNotNone(pred, "predicate missing — see test_predicate_exists")
        self.assertTrue(
            pred(self._vac_row(units_completed=False), True),
            "A VAC-flagged row with Units Completed? UNchecked must STILL be "
            "excluded from the foreman sheet (contract: VAC checked -> VAC crew "
            "ONLY, regardless of Units Completed?). Today the "
            "'and units_completed_checked' conjunction lets it leak to the "
            "primary/User group."
        )

    # --- Inverse (currently-correct) behavior that MUST be preserved ------

    def test_non_vac_row_not_excluded(self):
        """A normal foreman row (no VAC checkbox) must NOT be excluded."""
        pred = self._predicate()
        self.assertIsNotNone(pred, "predicate missing — see test_predicate_exists")
        row = self._vac_row(units_completed=True)
        row['Vac Crew Completed Unit?'] = False
        row['VAC Crew Helping?'] = ''
        self.assertFalse(
            pred(row, True),
            "A row without the VAC checkbox must remain on the foreman sheet — "
            "the fix must not over-exclude normal primary rows."
        )

    def test_vac_checkbox_without_helper_name_not_excluded(self):
        """VAC completed checkbox checked but no VAC helper named -> NOT a VAC
        claim (no crew to credit); must stay with the foreman. Preserves the
        name+checkbox conjunction on the VAC side."""
        pred = self._predicate()
        self.assertIsNotNone(pred, "predicate missing — see test_predicate_exists")
        row = self._vac_row(units_completed=True)
        row['VAC Crew Helping?'] = ''
        self.assertFalse(
            pred(row, True),
            "VAC completed checkbox with a blank 'VAC Crew Helping?' is not an "
            "attributable VAC claim; the unit must stay with the foreman."
        )

    # --- Page gate — exclusion is evaluable per-row regardless of gate ----

    def test_vac_row_on_page_without_vac_columns_still_excluded(self):
        """When the VAC signal is present on the ROW, the predicate must
        exclude regardless of the page-level ``sheet_has_vac_crew_columns``
        gate. (Covers the foreman-side row that itself carries the VAC box.)"""
        pred = self._predicate()
        self.assertIsNotNone(pred, "predicate missing — see test_predicate_exists")
        self.assertTrue(
            pred(self._vac_row(units_completed=True), False),
            "A VAC-flagged row must be excluded from the foreman sheet even "
            "when the page-level VAC-columns gate is False."
        )


class TestVacCrewAcceptanceGateWidening(unittest.TestCase):
    """RED for the narrow intake widening: a VAC-claimed, units-UNchecked row
    must be ADMITTED into the pipeline (so it can reach the _VacCrew file),
    not dropped at the acceptance gate.

    Exercised end-to-end through ``group_source_rows``: a row that the fixed
    upstream detection flags ``__is_vac_crew=True`` despite
    ``Units Completed?`` unchecked must produce a vac_crew group (proof it
    survived intake) and NO primary group."""

    def _vac_claim_units_incomplete_row(self):
        return {
            'Work Request #': '90922617',
            'Weekly Reference Logged Date': '2026-06-07',
            'Pole #': '.11',
            'Units Completed?': False,
            'Units Total Price': '$1234.56',
            '__effective_user': 'Chris Higginbotham',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__is_vac_crew': True,
            '__vac_crew_name': 'Hugo Garcia',
            '__vac_crew_dept': '4100',
            '__vac_crew_job': 'J-11',
        }

    def test_vac_claim_units_incomplete_admitted_to_vaccrew(self):
        rows = [self._vac_claim_units_incomplete_row()]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        vac_keys = [
            k for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'vac_crew'
        ]
        primary_keys = [
            k for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'primary'
        ]
        self.assertTrue(
            vac_keys,
            "A VAC-claimed unit with Units Completed? UNchecked was not routed "
            "to a _VacCrew group — intake widening missing or grouping did not "
            "consume the VAC flag; the VAC crew would never be credited."
        )
        self.assertEqual(
            primary_keys, [],
            "VAC-claimed unit leaked into a primary/User group."
        )


class TestVacCrewExclusionGroupingEndToEnd(unittest.TestCase):
    """End-to-end RED: a VAC-flagged row must never land in a primary/User
    group, exercised through the real ``group_source_rows`` routing. Locks in
    that the single source of truth is actually CONSUMED by the grouping
    path, not merely defined."""

    def _vac_flagged_unit_incomplete_row(self):
        return {
            'Work Request #': '90922617',
            'Weekly Reference Logged Date': '2026-06-07',
            'Pole #': '.11',
            'Units Completed?': False,
            'Units Total Price': '$1234.56',
            '__effective_user': 'Chris Higginbotham',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__is_vac_crew': True,
            '__vac_crew_name': 'Hugo Garcia',
            '__vac_crew_dept': '4100',
            '__vac_crew_job': 'J-11',
        }

    def test_vac_flagged_row_never_in_primary_group(self):
        rows = [self._vac_flagged_unit_incomplete_row()]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        primary_keys = [
            k for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'primary'
        ]
        self.assertEqual(
            primary_keys, [],
            "A VAC-flagged unit produced a primary/User group — it leaked to "
            "the foreman sheet. WR 90922617 point .11 must appear ONLY on the "
            "_VacCrew variant."
        )
        vac_keys = [
            k for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'vac_crew'
        ]
        self.assertTrue(
            vac_keys,
            "The VAC-flagged unit must still produce its own _VacCrew group."
        )


class TestVacCrewMixedPolePerUnit(unittest.TestCase):
    """Per-UNIT exclusion grain (operator decision 2026-06-08).

    Exclusion is at the UNIT/ROW grain, NOT the pole/point grain. When a
    single Pole # carries BOTH a VAC-claimed unit AND a separate unit the
    foreman genuinely completed (VAC box unchecked, Units Completed checked),
    ONLY the VAC-claimed unit moves to the VAC crew; the foreman's own unit on
    the same pole MUST remain on the foreman sheet.

    This supersedes the earlier (rejected) pole-level "step C" design, which
    would have stripped the foreman's legitimate unit just because it shares a
    pole with a VAC-claimed unit. This test guards against anyone
    reintroducing that over-exclusion.
    """

    def _vac_claimed_unit(self):
        return {
            'Work Request #': '90922617',
            'Weekly Reference Logged Date': '2026-06-07',
            'Pole #': '.11',
            'Units Completed?': True,
            'Units Total Price': '$1000.00',
            '__effective_user': 'Hugo Garcia',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__is_vac_crew': True,
            '__vac_crew_name': 'Hugo Garcia',
            '__vac_crew_dept': '4100',
            '__vac_crew_job': 'J-11',
        }

    def _foreman_own_unit_same_pole(self):
        # A DIFFERENT billable unit on the SAME pole that the foreman
        # genuinely completed; no VAC claim on this row. Per the per-unit
        # contract it MUST stay on the foreman sheet.
        return {
            'Work Request #': '90922617',
            'Weekly Reference Logged Date': '2026-06-07',
            'Pole #': '.11',
            'Units Completed?': True,
            'Units Total Price': '$250.00',
            '__effective_user': 'Chris Higginbotham',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__is_vac_crew': False,
        }

    def test_foreman_own_unit_on_vac_touched_pole_is_retained(self):
        rows = [self._vac_claimed_unit(), self._foreman_own_unit_same_pole()]
        groups = generate_weekly_pdfs.group_source_rows(rows)

        primary_groups = {
            k: gr for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'primary'
        }
        vac_groups = {
            k: gr for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'vac_crew'
        }

        # The foreman's own completed unit stays with the foreman — per-unit,
        # NOT pole-level exclusion.
        self.assertTrue(
            primary_groups,
            "The foreman's own completed unit on pole .11 was dropped — "
            "per-unit exclusion must NOT strip non-VAC units that merely share "
            "a pole with a VAC-claimed unit (rejected pole-level over-exclusion)."
        )
        foreman_rows = [r for gr in primary_groups.values() for r in gr]
        self.assertTrue(
            all(not r.get('__is_vac_crew') for r in foreman_rows),
            "A VAC-claimed unit leaked into the foreman group."
        )
        self.assertTrue(
            any(str(r.get('Pole #')) == '.11' for r in foreman_rows),
            "The foreman's legitimate .11 unit must remain on the foreman sheet."
        )

        # The VAC-claimed unit on the same pole is credited to the VAC crew.
        self.assertTrue(
            vac_groups,
            "The VAC-claimed unit on pole .11 must produce a _VacCrew group."
        )
        vac_rows = [r for gr in vac_groups.values() for r in gr]
        self.assertTrue(
            all(r.get('__is_vac_crew') for r in vac_rows),
            "A non-VAC unit leaked into the VAC crew group."
        )


class TestVacCrewCrossRowUnitReconciliation(unittest.TestCase):
    """The REAL WR 90922617 bug: multi-sheet duplication.

    A WR can span two source sheets — a foreman/original-contract sheet (no
    VAC columns) AND a VAC-crew sheet (VAC columns). The SAME physical unit
    then exists as TWO rows; only the VAC-sheet copy carries the VAC claim, so
    a purely row-local predicate cannot see the claim on the foreman's copy and
    the unit is duplicated onto BOTH the foreman sheet and the VacCrew sheet.

    Operator contract (2026-06-08): the same unit must appear on only one sheet
    (the VAC crew's). The exclusion is at the UNIT grain (WR + week + Point +
    CU), NOT the pole grain — so the foreman's OTHER units on the same pole are
    retained.

    Mirrors the observed data: Point 11 ``ANC-DSC-16-96-D1`` appeared on both
    Chris's User file and Hugo's VacCrew file, while Point 11
    ``ARM-8SF-GN-TL-C`` (genuinely Chris's) appeared only on Chris's.
    """

    def _vac_sheet_row(self, point, cu):
        return {
            'Work Request #': '90922617',
            'Weekly Reference Logged Date': '2026-06-07',
            'Snapshot Date': '2026-06-04',
            'Pole #': point,
            'CU': cu,
            'Units Completed?': True,
            'Units Total Price': '$1628.56',
            '__effective_user': 'Hugo Garcia',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__is_vac_crew': True,
            '__vac_crew_name': 'Hugo Garcia',
            '__vac_crew_dept': '455',
            '__vac_crew_job': '',
        }

    def _foreman_sheet_row(self, point, cu, price='$100.00'):
        # Foreman-sheet copy of a unit — carries NO VAC signal because it comes
        # from a source sheet without the VAC columns.
        return {
            'Work Request #': '90922617',
            'Weekly Reference Logged Date': '2026-06-07',
            'Snapshot Date': '2026-06-04',
            'Pole #': point,
            'CU': cu,
            'Units Completed?': True,
            'Units Total Price': price,
            '__effective_user': 'Chris Higginbotham',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__is_vac_crew': False,
        }

    def test_vac_claimed_unit_removed_from_foreman_other_units_kept(self):
        rows = [
            self._vac_sheet_row('Point 11', 'ANC-DSC-16-96-D1'),      # VAC claim
            self._foreman_sheet_row('Point 11', 'ANC-DSC-16-96-D1'),  # dup -> drop from foreman
            self._foreman_sheet_row('Point 11', 'ARM-8SF-GN-TL-C'),   # Chris's own -> keep
        ]
        groups = generate_weekly_pdfs.group_source_rows(rows)

        primary_cus = {
            str(r.get('CU'))
            for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'primary'
            for r in gr
        }
        vac_cus = {
            str(r.get('CU'))
            for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'vac_crew'
            for r in gr
        }

        self.assertNotIn(
            'ANC-DSC-16-96-D1', primary_cus,
            "The VAC-claimed unit (Point 11 ANC-DSC-16-96-D1) leaked onto the "
            "foreman sheet — it is duplicated from the VAC crew sheet and must "
            "be excluded from the foreman."
        )
        self.assertIn(
            'ARM-8SF-GN-TL-C', primary_cus,
            "The foreman's OWN unit on the same pole was wrongly dropped — "
            "exclusion must be per-UNIT (Point + CU), not per-pole."
        )
        self.assertIn(
            'ANC-DSC-16-96-D1', vac_cus,
            "The VAC-claimed unit must still appear on the VAC crew sheet."
        )

    def test_unit_not_vac_claimed_anywhere_stays_with_foreman(self):
        # No VAC row for this unit -> it must remain on the foreman sheet.
        rows = [self._foreman_sheet_row('Point 11', 'ARM-8SF-GN-TL-C')]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        primary_cus = {
            str(r.get('CU'))
            for k, gr in groups.items()
            if gr and gr[0].get('__variant') == 'primary'
            for r in gr
        }
        self.assertIn(
            'ARM-8SF-GN-TL-C', primary_cus,
            "A unit that is not VAC-claimed anywhere must stay with the foreman."
        )


if __name__ == '__main__':
    unittest.main()
