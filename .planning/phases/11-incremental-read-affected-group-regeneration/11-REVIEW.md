---
phase: 11-incremental-read-affected-group-regeneration
reviewed: 2026-09-14T18:14:23Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - pipeline/orchestrate.py
  - tests/test_parity_shadow.py
  - tests/test_incremental_read.py
  - tests/test_own04_documentation.py
  - tests/fixtures/incremental/user_variant_candidate_miss.json
  - memory-bank/living-ledger.md
  - .claude/project-state.md
  - docs/CHANGELOG_CONTEXT.md
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-09-14T18:14:23Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This is an **incremental** review scoped to the diff between `697eda9` (the prior
`11-REVIEW.md` commit) and `HEAD`: the Plan 11-09 gap-closure fix for
`11-VERIFICATION.md` Gap 2 (INC-02 USER-variant candidate-set divergence) and its
supporting tests/fixture/docs.

**The fix itself is correct and surgical.** `pipeline/orchestrate.py::_resolve_row_wr_week`
now derives its WR component by calling `pipeline_memory.writer._sanitized_wr(row)`
directly instead of re-implementing a parallel (and divergent) `str(wr).split('.')[0]`
rule. I traced `_sanitized_wr` (`pipeline_memory/writer.py:706-719`) and confirmed:
(1) it is byte-identical to what populates `row_state.wr`, so the affected-pair
comparison in `_filter_groups_to_affected` is now a true equality check against the
same key space `row_state` uses; (2) it is a pre-existing private helper already
called from this exact call site for the week component (`_coerce_date`), so this is
not a new cross-module private-access pattern, just an extension of one already in
place; (3) the one behavior change flagged in the docstring (a falsy-but-not-`None`
raw WR, e.g. `0`, now sanitizes to `"0"` instead of `''`) is the intended fix, not a
regression — it makes the falsy-value rule match `_sanitized_wr`'s contract instead of
diverging from it. `_mem_writer` was already imported at module scope; no new import
cycle. The WR-normalization non-injectivity risk (two raw values collapsing to one
sanitized key) is explicitly analyzed in the docstring and is the safe direction under
the codebase's T-11-18 "widen never narrow" invariant.

The new tests (`AffectedPairKeyContractTests` in `tests/test_incremental_read.py`,
`UserVariantCandidateParityTests` in `tests/test_parity_shadow.py`) and the new fixture
(`tests/fixtures/incremental/user_variant_candidate_miss.json`) were read in full and
independently executed: `pytest tests/test_parity_shadow.py tests/test_incremental_read.py
tests/test_own04_documentation.py -q` → 269 passed, 37 subtests passed, 0 failures.
The `test_own04_documentation.py` change (locating the Phase 12 ledger entry by the
`D-12-C` content marker instead of "last heading in the file") is a genuine robustness
fix — I confirmed the marker occurs exactly once in `living-ledger.md`, so the new loop
resolves unambiguously, and it correctly prevents the test from silently drifting onto
a later, unrelated ledger entry as the append-only ledger grows (which is precisely
what would have happened to the old position-based lookup once this same review's
gap-closure entry was appended below the Phase 12 one).

One caveat on the new test suite: `AffectedPairKeyContractTests`'s two "contract" tests
(`test_wr_component_matches_sanitized_wr_across_shapes`,
`test_week_component_matches_coerce_date_across_shapes`) compare
`orch._resolve_row_wr_week`'s output against calling the exact same underlying
functions a second time — since the fix makes `_resolve_row_wr_week` literally delegate
to `_sanitized_wr`/`_coerce_date`, the comparison is tautological today and cannot by
itself detect a bug *inside* `_sanitized_wr`/`_coerce_date`. This is intentional per
the docstring ("a future edit to either derivation fails this test instead of drifting
silently") — it is a wiring/regression-pin test, not a correctness proof — but it means
the actual correctness proof for the WR-sanitizer behavior rests on
`UserVariantCandidateParityTests`'s end-to-end reproduction (which does exercise real
`group_source_rows` output and a real parity verdict) rather than on the contract test.
Not a defect; noted for reviewer context only.

Two new findings resulted, both Warning-level and both in the documentation/ledger
files rather than the code fix. No Critical issues.

## Prior Review Findings — Status

The prior `11-REVIEW.md` (committed at `697eda9`, standard depth, 29 files) reported
0 Critical / 1 Warning / 2 Info. None of the three are touched by this diff (the diff
does not modify `pipeline/fetch.py` or `pipeline/attribution.py`) — I spot-checked all
three against current `HEAD` and confirm they remain **OPEN**, unchanged:

- **WR-01** (`pipeline/fetch.py:154-165`, `_is_abbreviated_response` cannot
  distinguish a whole-sheet-deleted full response from a genuinely abbreviated/
  unchanged probe response) — still present verbatim at `HEAD`. **Still open.**
- **IN-01** (`pipeline/orchestrate.py:257-276`, 11 dead names imported from
  `pipeline.attribution`) — the import block is byte-identical to the version
  reviewed at `697eda9`; none of the 11 names were touched by this diff. **Still open.**
- **IN-02** (`pipeline/attribution.py:231-605`, ~375 lines of hash-prune functions
  with no production caller) — confirmed the four functions and their
  `*_HASH_PRUNE_VERSION` constants are all still present, unarchived. **Still open.**

## Warnings

### WR-02: `.claude/project-state.md` exceeds its own documented 120-line cap and grew further in this diff

**File:** `.claude/project-state.md:2`

**Issue:** The file's own header states the hard constraint enforced by the
`align-instruction-files` skill:

> Cap ≤ 120 lines (`align-instruction-files` skill); history goes to
> `memory-bank/living-ledger.md`, never here.

At `diff_base` (`697eda9`) the file was already over cap at 178 lines. This diff adds
a new bullet ("Phase 11 verification gate run…") that pushes it to **196 lines** — an
18-line net increase in the wrong direction relative to the file's stated policy. The
new content (regeneration-gate detail, gap descriptions, tooling notes) largely
duplicates what the same diff already appended to `docs/CHANGELOG_CONTEXT.md` and
`memory-bank/living-ledger.md` in more detail, which is exactly the kind of content
the header says belongs in the ledger, "never here."

**Fix:** Trim `.claude/project-state.md` back under 120 lines by summarizing the new
bullet to a one-line pointer (e.g. "Gap-closure plan 11-09 fixed INC-02 candidate-set
divergence, see `living-ledger.md` 2026-09-14 18:00 entry") and moving the narrative
detail (which is already duplicated in `CHANGELOG_CONTEXT.md`/`living-ledger.md`) out
of this file, per the project's own `align-instruction-files` convention.

### WR-03: `_resolve_row_wr_week`'s new WR contract test is tautological, not a correctness proof

**File:** `tests/test_incremental_read.py:2048-2064` (`test_wr_component_matches_sanitized_wr_across_shapes`)

**Issue:** The test calls `orch._resolve_row_wr_week(row)` and compares its WR output
against `mem_writer._sanitized_wr(row)` called a second time on the same `row`. Because
the fixed implementation is `wr_key = _mem_writer._sanitized_wr(row)` (a direct
delegation, no transformation of its own), this assertion is `_sanitized_wr(row) ==
_sanitized_wr(row)` — always true regardless of whether `_sanitized_wr` itself is
correct. It protects against `_resolve_row_wr_week` regressing to a *different*
derivation (its stated purpose, and a real regression it would catch), but it provides
zero coverage of `_sanitized_wr`'s actual sanitization behavior (the truncation,
substitution, and falsy-value rules the docstring describes across the eight WR
shapes) — a bug introduced directly inside `_sanitized_wr` would pass this test.
Correctness coverage for those shapes currently depends entirely on
`pipeline_memory`'s own test suite (not reviewed in this pass) and on
`UserVariantCandidateParityTests`'s single end-to-end fixture case.

**Fix:** Either (a) accept this test as a wiring/regression pin only (its documented
intent) and rely on `pipeline_memory`'s own `_sanitized_wr` unit tests for behavioral
coverage — in which case a one-line docstring note ("this is a wiring pin, not a
sanitizer behavior proof; see `tests/test_pipeline_memory_shadow.py` for
`_sanitized_wr` behavior coverage") would prevent a future reader from mistaking it for
one — or (b) add expected-value assertions for at least the space/truncation/falsy
cases directly in this test (e.g. `self.assertEqual(group_side, "90001_REV2")` for the
space-containing shape) so a regression inside `_sanitized_wr` itself is also caught
here.

## Info

### IN-03: `_resolve_row_wr_week`'s week-component contract test is likewise tautological

**File:** `tests/test_incremental_read.py:2066-2084` (`test_week_component_matches_coerce_date_across_shapes`)

**Issue:** Same pattern as WR-03 but for the week component: `orch._resolve_row_wr_week`
internally computes `_mem_writer._coerce_date(_utils.excel_serial_to_date(...))`, and
the test recomputes the identical two-call chain and asserts equality — a tautology
with respect to `_coerce_date`/`excel_serial_to_date` correctness, useful only as a
wiring pin against `_resolve_row_wr_week` reintroducing its own date-stringification
logic.

**Fix:** Same as WR-03(a)/(b) — either document it as a wiring pin, or assert concrete
expected ISO strings for the four shapes (serial number, date string, `datetime.date`,
unparseable) to also guard the underlying stringifiers.

### IN-04: `UserVariantCandidateParityTests` skips the RED-before-fix step is unverifiable from the diff alone

**File:** `tests/test_parity_shadow.py:762-843`

**Issue:** The test's own comment states "Test 1 (the reproduction, must be RED before
the Task 2 fix)" and the ledger entry states the fix and its test landed together in
plan 11-09. Since this review only has the post-fix `HEAD` state, I can confirm the
test currently passes against the fixed code (verified via `pytest`, see Summary) but
cannot independently confirm it was ever actually red against the pre-fix
`_resolve_row_wr_week` (i.e., that it truly reproduces the Gap 2 defect rather than
passing vacuously for an unrelated reason). This is a process/evidence gap rather than
a code defect — the fixture's `sheet_id`/`Work Request #` values are plausible for
triggering the divergence (the fix's own diff shows the exact `str(wr).split('.')[0]`
vs `_sanitized_wr` mismatch this row would trigger: `"90201 REV2"` sanitizes to
`"90201_REV2"` under `_sanitized_wr` but to `"90201 REV2"` under the old
`str().split('.')[0]` rule), so the reproduction logic checks out by inspection.

**Fix:** No code change needed. For future gap-closure plans, consider having the
plan's SUMMARY record the actual pre-fix RED test output (or a `git stash`-based
verification step) as part of its evidence trail, so a later reviewer without access
to the plan's execution transcript can confirm the red/green claim rather than
inferring it by inspection.

---

_Reviewed: 2026-09-14T18:14:23Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
