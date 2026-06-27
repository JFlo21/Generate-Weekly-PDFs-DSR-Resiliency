"""Regression tests for the WR 90922617 VAC-crew duplication fix.

Debug session: ``vac-crew-leak-foreman-sheet``.

Operator contract (2026-06-08, final):

  * A unit is credited to the VAC crew when ``Vac Crew Completed Unit?`` is
    checked (with a named ``VAC Crew Helping?`` crew) AND ``Units Completed?``
    is checked -- matching how the data is entered in practice.
  * Such a unit is excluded from BOTH the primary-foreman (``_User_``) AND the
    helping-foreman (``_Helper_``) sheets, with NO duplication -- the same
    dominance the dual-checkbox helper rule has over the primary.
  * Exclusion is PER-UNIT (WR + week + Point + CU), NOT per-pole: the
    foreman's OTHER units on the same pole are retained.

Real reproduction: WR 90922617 (week 060726). The WR spans two source sheets
(a foreman sheet WITHOUT the VAC columns and a VAC-crew sheet WITH them), so a
VAC-completed unit (e.g. Point 11 ``ANC-DSC-16-96-D1``) existed as two rows and
was duplicated onto both Chris Higginbotham's ``_User_`` file and Hugo Garcia's
``_VacCrew_`` file. The cross-row reconciliation in ``group_source_rows`` drops
the duplicate foreman/helper copy of any unit VAC-claimed on another row,
keyed at the UNIT grain (WR + week + Pole # + CU).
"""

import unittest

import generate_weekly_pdfs


def _base_row(**over):
    row = {
        'Work Request #': '90922617',
        'Weekly Reference Logged Date': '2026-06-07',
        'Snapshot Date': '2026-06-04',
        'Units Completed?': True,
        'Units Total Price': '$100.00',
        '__is_helper_row': False,
        '__helper_foreman': '',
        '__is_vac_crew': False,
    }
    row.update(over)
    return row


def _vac_row(point, cu, price='$1628.56'):
    return _base_row(**{
        'Pole #': point,
        'CU': cu,
        'Units Total Price': price,
        '__effective_user': 'Hugo Garcia',
        '__assignment_method': 'FOREMAN_COLUMN',
        '__is_vac_crew': True,
        '__vac_crew_name': 'Hugo Garcia',
        '__vac_crew_dept': '455',
        '__vac_crew_job': '',
    })


def _foreman_row(point, cu, price='$100.00'):
    return _base_row(**{
        'Pole #': point,
        'CU': cu,
        'Units Total Price': price,
        '__effective_user': 'Chris Higginbotham',
        '__assignment_method': 'FOREMAN_COLUMN',
    })


def _helper_row(point, cu, price='$100.00'):
    return _base_row(**{
        'Pole #': point,
        'CU': cu,
        'Units Total Price': price,
        '__effective_user': 'Chris Higginbotham',
        '__assignment_method': 'FOREMAN_COLUMN',
        '__is_helper_row': True,
        '__helper_foreman': 'David Doyle',
        '__helper_dept': '200',
        '__helper_job': '',
    })


def _cus_for_variant(groups, variant):
    return {
        str(r.get('CU'))
        for _k, gr in groups.items()
        if gr and gr[0].get('__variant') == variant
        for r in gr
    }


class TestVacCrewCrossRowDuplication(unittest.TestCase):
    """The same unit must never appear on both a foreman/helper sheet and the
    VacCrew sheet (the real cross-sheet duplication)."""

    def test_vac_claimed_unit_removed_from_foreman_other_units_kept(self):
        rows = [
            _vac_row('Point 11', 'ANC-DSC-16-96-D1'),
            _foreman_row('Point 11', 'ANC-DSC-16-96-D1'),  # dup -> drop
            _foreman_row('Point 11', 'ARM-8SF-GN-TL-C'),   # Chris's own -> keep
        ]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        primary = _cus_for_variant(groups, 'primary')
        vac = _cus_for_variant(groups, 'vac_crew')
        self.assertNotIn(
            'ANC-DSC-16-96-D1', primary,
            "VAC-claimed unit leaked onto the foreman sheet (duplicated with "
            "the VacCrew sheet)."
        )
        self.assertIn(
            'ARM-8SF-GN-TL-C', primary,
            "The foreman's own unit on the same pole was wrongly dropped -- "
            "exclusion must be per-UNIT (Point + CU), not per-pole."
        )
        self.assertIn(
            'ANC-DSC-16-96-D1', vac,
            "VAC-claimed unit missing from the VAC crew sheet."
        )

    def test_vac_claimed_unit_removed_from_helper(self):
        # Same dominance over the helper foreman as over the primary.
        rows = [
            _vac_row('Point 11', 'ANC-DSC-16-96-D1'),
            _helper_row('Point 11', 'ANC-DSC-16-96-D1'),  # dup -> drop from helper
            _helper_row('Point 11', 'ARM-8SF-GN-TL-C'),   # helper's own -> keep
        ]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        helper = _cus_for_variant(groups, 'helper')
        vac = _cus_for_variant(groups, 'vac_crew')
        self.assertNotIn(
            'ANC-DSC-16-96-D1', helper,
            "VAC-claimed unit leaked onto the helper sheet."
        )
        self.assertIn(
            'ARM-8SF-GN-TL-C', helper,
            "The helper's own unit on the same pole was wrongly dropped."
        )
        self.assertIn('ANC-DSC-16-96-D1', vac)

    def test_unit_not_vac_claimed_stays_with_foreman(self):
        rows = [_foreman_row('Point 11', 'ARM-8SF-GN-TL-C')]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertIn(
            'ARM-8SF-GN-TL-C', _cus_for_variant(groups, 'primary'),
            "A unit not VAC-claimed anywhere must remain with the foreman."
        )

    def test_vac_unchecked_does_not_suppress_foreman_copy(self):
        # LOW-01 hardening: the cross-row suppression pre-pass must mirror the
        # consumer emission gate's Units Completed? rule. A VAC row whose unit
        # is NOT billed (Units Completed? unchecked -> dropped downstream) must
        # NOT suppress the foreman's COMPLETED copy of that same unit, or the
        # unit is billed to nobody (silent data loss / under-billing).
        vac = _vac_row('Point 11', 'ANC-DSC-16-96-D1')
        vac['Units Completed?'] = False  # VAC crew did NOT complete it
        rows = [
            vac,
            _foreman_row('Point 11', 'ANC-DSC-16-96-D1'),  # foreman DID
        ]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertIn(
            'ANC-DSC-16-96-D1', _cus_for_variant(groups, 'primary'),
            "A VAC row with Units Completed? unchecked is not billed to the "
            "VAC crew, so it must not suppress the foreman's completed copy -- "
            "otherwise the unit is billed to nobody."
        )
        self.assertNotIn(
            'ANC-DSC-16-96-D1', _cus_for_variant(groups, 'vac_crew'),
            "An unchecked VAC row must not be billed to the VAC crew either."
        )


class TestVacCrewSingleRowRouting(unittest.TestCase):
    """A single VAC row routes ONLY to the VacCrew variant, never primary."""

    def test_vac_row_routes_to_vaccrew_not_primary(self):
        rows = [_vac_row('Point 11', 'ANC-DSC-16-96-D1')]
        groups = generate_weekly_pdfs.group_source_rows(rows)
        self.assertEqual(
            _cus_for_variant(groups, 'primary'), set(),
            "A VAC row must not produce a primary/foreman group."
        )
        self.assertIn(
            'ANC-DSC-16-96-D1', _cus_for_variant(groups, 'vac_crew'),
            "A VAC row must produce its own VacCrew group."
        )


class TestVacCrewRequiresUnitsCompleted(unittest.TestCase):
    """Operator decision (2026-06-08): VAC billing requires Units Completed?
    checked (matches real data). An unchecked row is dropped at the grouping
    gate and credited to nobody."""

    def test_vac_row_without_units_completed_is_not_billed(self):
        row = _vac_row('Point 11', 'ANC-DSC-16-96-D1')
        row['Units Completed?'] = False
        groups = generate_weekly_pdfs.group_source_rows([row])
        billed = (
            _cus_for_variant(groups, 'vac_crew')
            | _cus_for_variant(groups, 'primary')
            | _cus_for_variant(groups, 'helper')
        )
        self.assertNotIn(
            'ANC-DSC-16-96-D1', billed,
            "A VAC row with Units Completed? unchecked must not be billed to "
            "any variant."
        )


if __name__ == '__main__':
    unittest.main()
