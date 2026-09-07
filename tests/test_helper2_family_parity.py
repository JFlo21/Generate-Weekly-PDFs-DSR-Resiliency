"""Helper #1 / Helper #2 family literal parity (Phase 14, 14-01 Task 2).

There is no single shared constant for "the helper-family variant
strings" anywhere in this codebase (14-PATTERNS.md Pattern A, Pitfall 3)
-- at least four independent call sites enumerate the Helper #1 family
(``helper``, ``aep_billable_helper``, ``reduced_sub_helper``) as an
inline literal, and Phase 14 adds a parallel Helper #2 sibling family
(``helper2``, ``aep_billable_helper2``, ``reduced_sub_helper2``) that
must never be merged into the Helper #1 tuple (D-14-11) but DOES need
its own literal at every site the Helper #1 family appears.

This module is the enforcement mechanism: it reads a PINNED table of
production files and asserts that a Helper #1 family literal's Helper #2
sibling is present too -- catching a future plan that adds a Helper #1
site (or extends one) but forgets its Helper #2 counterpart.

Literals are matched WITH their closing quote (e.g. ``'reduced_sub_helper'``
rather than the bare word) so the Helper #2 spelling is never miscounted
as a Helper #1 hit -- ``'reduced_sub_helper2'`` does not contain the
substring ``'reduced_sub_helper'`` followed by a closing quote.

Extension point: plan 14-05 adds ``pipeline/cleanup.py``
(``_HELPER_VARIANTS_FOR_ORPHAN_GATE``) and
``scripts/publish_artifacts_to_supabase.py`` (``_CANONICAL_VARIANTS`` /
``normalize_variant``) to ``PARITY_TABLE`` below -- the two silent-gap
sites this phase's research discovered that were NOT in the original
audit-scope anchor list. The publisher script quotes these literals with
double quotes exclusively (verified by grep), unlike every other pinned
file which uses single quotes exclusively for the SAME literal, so the
match helper below checks both quote styles rather than widening
``SIBLING_PAIRS`` itself to carry quote characters. Plan 14-06 adds the
subcontractor Helper #2 shadow variants to ``pipeline/excel.py`` and
``pipeline/change_detection.py``'s nested AEPBillable/ReducedSub filename
branches, and to ``billing_audit/writer.py`` (``ROLE_BY_VARIANT`` /
``resolve_claimer``) -- when it does, remove the corresponding entries
from ``KNOWN_DEFERRED`` below in the SAME change (the "the extension
point 14-06 must clear" this comment refers to).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# (Helper #1 literal, Helper #2 sibling literal) -- BARE words, quoted at
# match time by ``_literal_present`` (see below) with whichever quote
# character the pinned file actually uses.
SIBLING_PAIRS = (
    ("helper", "helper2"),
    ("aep_billable_helper", "aep_billable_helper2"),
    ("reduced_sub_helper", "reduced_sub_helper2"),
)

# Pinned file table (relative to repo root). This IS "the definitive
# checklist" RESEARCH.md's Pitfall 3 asks for -- seeded with the three
# files Plan 14-01 touches, extended by plan 14-05 with the two
# not-in-original-audit-scope sites its research discovered.
PARITY_TABLE = (
    'pipeline/change_detection.py',
    'pipeline/orchestrate.py',
    'pipeline/excel.py',
    'pipeline/cleanup.py',
    'scripts/publish_artifacts_to_supabase.py',
)

# Per-file (Helper #2 literal) pairs that are KNOWN, NAMED, TEMPORARY
# gaps -- a Helper #1 literal is present without its Helper #2 sibling
# on purpose, because a specific later plan in this phase adds it.
# Plan 14-01 deliberately left excel.py's two subcontractor Helper #2
# shadow branches (_AEPBillable_Helper2_<name> / _ReducedSub_Helper2_<name>)
# to plan 14-06, which has now implemented both branches (see
# 14-06-PLAN.md Task 2) -- there are no remaining known-deferred gaps.
# Any entry added here MUST cite the plan that closes it. Values are
# bare literals (matching SIBLING_PAIRS' bare form above), not quoted
# strings.
KNOWN_DEFERRED: dict[str, set[str]] = {}


def _quoted_forms(literal: str) -> tuple[str, str]:
    """Both quote styles used anywhere across ``PARITY_TABLE`` for these
    literals, each WITH both flanking quote characters, so a check never
    matches a bare substring (e.g. ``reduced_sub_helper`` inside
    ``reduced_sub_helper2``) regardless of which quote character a given
    pinned file prefers.

    ``scripts/publish_artifacts_to_supabase.py`` (plan 14-05) is
    double-quote-only for these tokens; every other pinned file is
    single-quote-only for the SAME literal -- verified by grep, no pinned
    file mixes both quote styles for one literal, so "either form
    present" cannot accidentally match a file that has neither.
    """
    return (f"'{literal}'", f'"{literal}"')


def _literal_present(literal: str, src: str) -> bool:
    return any(form in src for form in _quoted_forms(literal))


class HelperFamilyParityTests(unittest.TestCase):
    """Every Helper #1 family literal in the pinned table either has its
    Helper #2 sibling present, or the gap is a named, deferred one."""

    @classmethod
    def setUpClass(cls):
        cls._sources = {
            rel: (_REPO_ROOT / rel).read_text(encoding='utf-8')
            for rel in PARITY_TABLE
        }

    def test_helper1_literal_still_present(self):
        """Direction 1: the Helper #1 literal a file already carries must
        still be there -- this phase is additive-only to that family
        (D-14-11 vocabulary lock; never widen or touch the Helper #1
        tuple)."""
        for rel, src in self._sources.items():
            for helper1_lit, _helper2_lit in SIBLING_PAIRS:
                if _literal_present(helper1_lit, src):
                    with self.subTest(file=rel, literal=helper1_lit):
                        self.assertTrue(_literal_present(helper1_lit, src))

    def test_helper2_sibling_present_or_named_deferred(self):
        """Direction 2: a Helper #1 literal's Helper #2 sibling must be
        present, unless the gap is explicitly named in KNOWN_DEFERRED."""
        for rel, src in self._sources.items():
            deferred = KNOWN_DEFERRED.get(rel, frozenset())
            for helper1_lit, helper2_lit in SIBLING_PAIRS:
                if not _literal_present(helper1_lit, src):
                    continue  # this file never carries this family member
                with self.subTest(file=rel, pair=(helper1_lit, helper2_lit)):
                    if helper2_lit in deferred:
                        self.assertFalse(
                            _literal_present(helper2_lit, src),
                            f"{rel}: {helper2_lit!r} is listed in "
                            f"KNOWN_DEFERRED but is now present in the "
                            f"source -- remove it from KNOWN_DEFERRED "
                            f"for this file (the deferring plan landed)",
                        )
                    else:
                        self.assertTrue(
                            _literal_present(helper2_lit, src),
                            f"{rel}: enumerates Helper #1 family literal "
                            f"{helper1_lit!r} but is missing its Helper #2 "
                            f"sibling {helper2_lit!r} (Pitfall 3 -- a "
                            f"Helper #1 site with no Helper #2 sibling)",
                        )

    def test_helper2_spelling_is_not_miscounted_as_helper1(self):
        """Guard the guard: the quoted-literal technique actually
        discriminates 'reduced_sub_helper' from 'reduced_sub_helper2'
        (etc.) so a future edit to this test cannot silently regress into
        a substring false-positive -- checked for both quote styles used
        across PARITY_TABLE."""
        samples = (
            "variant in ('helper2', 'aep_billable_helper2', "
            "'reduced_sub_helper2')",
            'variant in ("helper2", "aep_billable_helper2", '
            '"reduced_sub_helper2")',
        )
        for sample in samples:
            for helper1_lit, helper2_lit in SIBLING_PAIRS:
                with self.subTest(sample=sample, literal=helper1_lit):
                    self.assertFalse(_literal_present(helper1_lit, sample))
                with self.subTest(sample=sample, literal=helper2_lit):
                    self.assertTrue(_literal_present(helper2_lit, sample))


if __name__ == "__main__":
    unittest.main()
