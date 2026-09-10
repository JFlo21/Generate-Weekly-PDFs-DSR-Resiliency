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

import ast
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
    # Plan 14-06: the remaining sites this phase touches -- the upload
    # module (PPP dual-route gate) and the grouping module (shadow
    # partition + main-loop emission). With these three additions the
    # table covers every independent enumeration of the helper-family
    # variant strings that 14-RESEARCH.md's Pitfall 3 identified.
    'pipeline/upload.py',
    'pipeline/grouping.py',
    # Code review CR-01/WR-01 gap closure: pricing.py's _resolve_row_price
    # (both the early-gate and rate-class-selection literal sites) and
    # attribution.py's _SUBCONTRACTOR_SCOPE_VARIANTS enumerate the Helper
    # #1 family literals the same way every other pinned site does, but
    # were absent from this table, so the parity net never covered them
    # -- exactly the class of gap this table exists to catch.
    'pipeline/pricing.py',
    'pipeline/attribution.py',
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
#
# pipeline/attribution.py's bare ``'helper'`` literal is NOT a Helper
# #1/#2 variant-dispatch site -- it is ``_run_phase_1_1_hash_prune``'s
# Phase 1.1 (SUB-12) one-time, VERSIONED orphan-key cleanup for the
# legacy 6-part hash-history key shape (``wr|week|helper|foreman|dept
# |job``) that predates Helper #2 entirely. The real parity gap in this
# file was ``_SUBCONTRACTOR_SCOPE_VARIANTS`` (code review WR-01, now
# fixed). There is no Helper #2 equivalent legacy key to prune, so this
# is a permanent, structural exception (not a later-plan-closes-it
# gap) -- do not add a ``'helper2'`` clause to the hash-prune matcher.
#
# Greptile (PR #402): the exception is scoped to the OWNING FUNCTION,
# not the whole file. Value shape is ``{helper2_literal: owner_fn}`` --
# every occurrence of the Helper #1 literal in that file must sit
# inside ``owner_fn``'s ``ast`` span (def line .. end line, docstring
# and comments included). A later, unrelated bare ``'helper'`` dispatch
# added anywhere else in the file is NOT covered and fails the parity
# check like any other pinned site would.
KNOWN_DEFERRED: dict[str, dict[str, str]] = {
    'pipeline/attribution.py': {'helper2': '_run_phase_1_1_hash_prune'},
}


def _function_span(src: str, fn_name: str) -> tuple[int, int] | None:
    """1-based inclusive ``(first_line, last_line)`` of top-level or
    nested ``def fn_name`` in ``src``; ``None`` when it does not exist."""
    for node in ast.walk(ast.parse(src)):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == fn_name
        ):
            return node.lineno, node.end_lineno or node.lineno
    return None


def _literal_lines_outside_owner(
    src: str, literal: str, owner_fn: str,
) -> list[int]:
    """Line numbers where the quoted ``literal`` appears OUTSIDE the
    ``owner_fn`` span. Every line is reported when ``owner_fn`` is
    missing, so a renamed/removed owner can never silently widen the
    exception back to file scope."""
    span = _function_span(src, owner_fn)
    forms = _quoted_forms(literal)
    return [
        lineno
        for lineno, line in enumerate(src.splitlines(), start=1)
        if any(form in line for form in forms)
        and (span is None or not (span[0] <= lineno <= span[1]))
    ]


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
            deferred = KNOWN_DEFERRED.get(rel, {})
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
                        owner = deferred[helper2_lit]
                        stray = _literal_lines_outside_owner(
                            src, helper1_lit, owner,
                        )
                        self.assertEqual(
                            stray, [],
                            f"{rel}: the KNOWN_DEFERRED exception for "
                            f"{helper2_lit!r} covers ONLY {owner}(); "
                            f"bare {helper1_lit!r} also appears outside "
                            f"it at line(s) {stray} with no "
                            f"{helper2_lit!r} sibling (Pitfall 3 -- a "
                            f"new Helper #1 site the file-wide "
                            f"deferral used to hide)",
                        )
                    else:
                        self.assertTrue(
                            _literal_present(helper2_lit, src),
                            f"{rel}: enumerates Helper #1 family literal "
                            f"{helper1_lit!r} but is missing its Helper #2 "
                            f"sibling {helper2_lit!r} (Pitfall 3 -- a "
                            f"Helper #1 site with no Helper #2 sibling)",
                        )

    def test_deferred_exception_is_scoped_to_owner_function(self):
        """Greptile (PR #402): the attribution.py deferral must NOT be
        file-wide. Reproduces the reviewer's scenario -- the real file
        plus one unrelated bare ``'helper'`` dispatch appended outside
        ``_run_phase_1_1_hash_prune`` -- and requires the scoped check
        to flag exactly that new line, while the unmodified file has
        zero stray occurrences."""
        rel = 'pipeline/attribution.py'
        owner = KNOWN_DEFERRED[rel]['helper2']
        src = self._sources[rel]
        self.assertIsNotNone(
            _function_span(src, owner),
            f"{rel}: KNOWN_DEFERRED names {owner}() but it no longer "
            f"exists -- re-scope or drop the exception",
        )
        self.assertEqual(
            _literal_lines_outside_owner(src, 'helper', owner), [],
        )

        appended = (
            src.rstrip('\n')
            + "\n\n\ndef _future_unrelated_dispatch():\n"
            + "    return 'helper'\n"
        )
        expected_line = appended.count('\n')  # the ``return`` line
        self.assertEqual(
            _literal_lines_outside_owner(appended, 'helper', owner),
            [expected_line],
        )
        # And a missing owner reports EVERY occurrence (never widens).
        self.assertGreater(
            len(_literal_lines_outside_owner(src, 'helper', '_nope')), 0,
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
