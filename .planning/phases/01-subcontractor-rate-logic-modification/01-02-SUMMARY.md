---
phase: 01-subcontractor-rate-logic-modification
plan: 02
subsystem: python-billing-engine
tags: [python, parser, hash-key, variants, subcontractor, change-detection, sentry-sanitizer]

# Dependency graph
requires:
  - "Plan 01: _SUBCONTRACTOR_RATES_FINGERPRINT module-level constant + _AEP_BILLABLE_CUTOFF available"
provides:
  - "build_group_identity() recognises _AEPBillable / _ReducedSub / _AEPBillable_Helper_<name> / _ReducedSub_Helper_<name> filenames"
  - "calculate_data_hash() mixes _SUBCONTRACTOR_RATES_FINGERPRINT into the hash for the 4 new variants ONLY (D-20)"
  - "calculate_data_hash() helper meta block now triggers on aep_billable_helper / reduced_sub_helper in addition to helper (Plan 3 wiring foundation)"
  - "_PII_LOG_MARKERS contains 7 new subcontractor variant tokens so Plan 3's INFO logs are sanitised before reaching Sentry"
  - "Regression locks: source-side WR collision pre-scan (round-9, sanitized WR alone) proven compatible with the 4 new variants via 3 new tests"
affects:
  - "01-03-PLAN.md (variant generation) — emitted filenames now round-trip through build_group_identity correctly; hash invalidates when CSV changes"
  - "01-04-PLAN.md (dual routing) — attachment-identity routing for _ReducedSub/_AEPBillable uses the variant tuple cleanly"
  - "01-05-PLAN.md (shadow helper) — _AEPBillable_Helper_<name> / _ReducedSub_Helper_<name> filenames parse and hash with HELPER meta block"
  - "01-06-PLAN.md (billing_audit attribution) — variant string from parser feeds freeze_row(variant=...) without ambiguity"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Variant-first / helper-second ordering inside build_group_identity (D-09): subcontractor variants checked BEFORE Helper/VacCrew/User so _AEPBillable_Helper_<name> resolves to aep_billable_helper rather than plain helper"
    - "Tail-scoped variant marker detection (D-10): the marker search operates on parts[we_idx + 2:] only — a sanitized WR# containing the literal AEPBillable / ReducedSub token cannot false-positive the variant"
    - "Conditional fingerprint mix-in scoped to the 4 new variants (D-20): the existing `if RATE_CUTOFF_DATE: ... RATES_FP=` legacy block is mirrored by a parallel `if variant in (...): ... SUB_RATES_FP=` block, preserving byte-identical hashes for primary/helper/vac_crew"
    - "Span-join discipline (round-7 contract): identifier extraction uses `'_'.join(post_xxx[idx + 1:-1])` so underscored helper names like `Jane_Smith` survive intact"
    - "Pre-emptive PII marker addition: tokens land in `_PII_LOG_MARKERS` in Plan 02 BEFORE Plan 03 emits the corresponding log calls — defense in depth per Living Ledger 2026-04-20 12:00"

key-files:
  created: []
  modified:
    - "generate_weekly_pdfs.py:
       (a) build_group_identity (~L2118-2231): 2 new variant branches BEFORE Helper/VacCrew/User; docstring extended with 8 supported filename formats;
       (b) calculate_data_hash (~L1889-1948): helper meta-block trigger extended to tuple ('helper', 'aep_billable_helper', 'reduced_sub_helper'); new D-20 SUB_RATES_FP mix-in block AFTER the legacy RATES_FP block;
       (c) _PII_LOG_MARKERS (~L760-783): 7 new tokens appended at end of tuple"
    - "tests/test_vac_crew.py: 2 new test classes (TestSubcontractorVariantGroupIdentityParsing 7 tests + TestSubcontractorVariantHashAggregation 10 tests)"
    - "tests/test_security_audit_followup.py: 5 new tests inside TestBuildGroupIdentityWithUnderscoresInWr + 3 new tests inside TestSourceWrCollisionQuarantine + new TestPiiLogMarkersIncludeSubcontractorVariants class (8 tests)"

key-decisions:
  - "Variant-first ordering (D-09): the new `'AEPBillable' in tail` and `'ReducedSub' in tail` branches MUST run before `'Helper' in tail` so the helper-variant of a subcontractor file parses with both the subcontractor classification AND the helper identifier intact. The existing Helper/VacCrew/User branches drop into elif positions after the two new branches — no behavior change for tails without AEPBillable/ReducedSub markers."
  - "Conditional fingerprint mix-in scoped exactly to the 4 new variants (D-20): preserves ROADMAP success criterion 5 (existing outputs byte-identical to pre-change). Locked with 3 negative tests — primary/helper/vac_crew hashes MUST stay byte-identical under SUB_RATES_FP mutation."
  - "Helper meta-block trigger extended via tuple membership (`variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper')`) rather than a parallel block: keeps the helper-validation / log-warning / meta_parts.append logic in ONE place so a future change to helper validation cannot accidentally diverge between the legacy and new helper variants."
  - "Source-side WR collision pre-scan (round-9, sanitized WR alone) NOT modified: the existing key contract already covers cross-variant and cross-week collisions for the new variants. Locked with 3 new regression tests so a future refactor cannot silently re-narrow the key to a tuple."
  - "PII markers added in Plan 02 even though Plan 03 will emit the corresponding INFO logs: the sanitizer must lead the call sites by at least one plan — defense in depth per Living Ledger 2026-04-20 12:00. Marker list is also locked by an all-7-at-once regression test (test_all_seven_subcontractor_markers_present) so a future PR that removes any one of them is caught immediately."

patterns-established:
  - "Variant-first variant detection: when adding a new variant whose name composes with an existing variant (here: `_AEPBillable_Helper_<name>` composes AEPBillable + Helper), the new variant's branch MUST run before the composition components' branches so the composition is recognised as a unit, not as the inner component with the outer token silently dropped."
  - "Tail-scoped marker detection: every variant marker check in build_group_identity operates on the `parts[we_idx + 2:]` tail slice. This is what makes the parser robust against sanitized WR#s that incidentally contain variant tokens — pattern to follow for any future variant additions."
  - "Fingerprint mix-in conditional on variant set membership: a tuple of variant names + an inner `if _FINGERPRINT:` guard, mirroring the existing legacy RATES_FP block. Future variant additions should use the same shape — never broaden an existing fingerprint to a wider variant set, always add a parallel block scoped to the new variants."
  - "PII marker pre-emptive addition: extend `_PII_LOG_MARKERS` in the plan BEFORE the plan that emits the corresponding log calls — locks the defense-in-depth layer ahead of the call sites."

requirements-completed: [SUB-01, SUB-02, SUB-05, SUB-06]

# Metrics
duration: ~30min
completed: 2026-05-14
---

# Phase 01 Plan 02: Parser + Hash Extension Summary

**`build_group_identity()` now recognises four new subcontractor variant filenames (`_AEPBillable`, `_ReducedSub`, `_AEPBillable_Helper_<name>`, `_ReducedSub_Helper_<name>`) with tail-scoped variant-first ordering, and `calculate_data_hash()` mixes `_SUBCONTRACTOR_RATES_FINGERPRINT` into the hash for those four variants only — preserving byte-identical hashes for `primary` / `helper` / `vac_crew` so the ROADMAP success criterion 5 stays intact. `_PII_LOG_MARKERS` gains 7 tokens so Plan 3's group-creation INFO logs and missing-CU WARNINGs are sanitised before reaching Sentry.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 3 (all autonomous, TDD discipline applied — RED commit before GREEN for every task)
- **Files modified:** 3 (`generate_weekly_pdfs.py`, `tests/test_vac_crew.py`, `tests/test_security_audit_followup.py`)
- **Tests added:** 33 net new (full suite: 459 passed / 22 skipped, was 426 / 22)

## Accomplishments

### Task 1 — `build_group_identity()` extended (commits `2c45fc8` RED + `bac4895` GREEN)

Inserted two new variant branches inside the variant marker detection block of `build_group_identity`, placed BEFORE the existing `Helper` / `VacCrew` / `User` branches so the variant-first / helper-second ordering (D-09) is preserved:

```python
if 'AEPBillable' in tail:
    aep_idx_rel = tail.index('AEPBillable')
    post_aep = tail[aep_idx_rel + 1:]
    if 'Helper' in post_aep:
        variant = 'aep_billable_helper'
        helper_idx_rel = post_aep.index('Helper')
        if helper_idx_rel + 1 < len(post_aep):
            identifier = '_'.join(post_aep[helper_idx_rel + 1:-1])
    else:
        variant = 'aep_billable'
        identifier = ''
elif 'ReducedSub' in tail:
    rs_idx_rel = tail.index('ReducedSub')
    post_rs = tail[rs_idx_rel + 1:]
    if 'Helper' in post_rs:
        variant = 'reduced_sub_helper'
        helper_idx_rel = post_rs.index('Helper')
        if helper_idx_rel + 1 < len(post_rs):
            identifier = '_'.join(post_rs[helper_idx_rel + 1:-1])
    else:
        variant = 'reduced_sub'
        identifier = ''
elif 'Helper' in tail:    # ← existing branch, unchanged
    variant = 'helper'
    ...
elif 'VacCrew' in tail:   # ← existing branch, unchanged
    variant = 'vac_crew'
    identifier = ''
elif 'User' in tail:      # ← existing branch, unchanged
    variant = 'primary'
    ...
```

Line ranges in `generate_weekly_pdfs.py`:
- AEPBillable branch: L2191-2204
- ReducedSub branch: L2205-2215
- Helper branch (unchanged): L2216-2221
- VacCrew branch (unchanged): L2222-2224
- User branch (unchanged): L2225-2229

Docstring extended with 8 supported filename formats (4 legacy + 4 new).

**Test coverage:**
- `TestSubcontractorVariantGroupIdentityParsing` (`tests/test_vac_crew.py`) — 7 tests cover the 4 positive round-trip cases + identity-tuple distinctness from primary and from each other + plain helper variant unaffected.
- 5 new tests inside `TestBuildGroupIdentityWithUnderscoresInWr` (`tests/test_security_audit_followup.py`) — lock the tail-scoped negative cases (`WR_AEPBillable_WeekEnding_...` → variant='primary' not 'aep_billable') and the underscored-WR round-trip for both helper variants.

### Task 2 — `calculate_data_hash()` D-20 fingerprint mix-in (commits `4295c0c` RED + `16f3ca4` GREEN)

Two parallel changes inside `calculate_data_hash()`:

**Change 1 — Helper meta block trigger extended (L1889 in `generate_weekly_pdfs.py`):**
```python
# Before:
if variant == 'helper':
    ...
# After:
if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
    ...
```

The new shadow-helper variants reuse the existing helper validation + meta_parts assembly. Plan 3 will emit `_AEPBILLABLE_HELPER_{name}` / `_REDUCEDSUB_HELPER_{name}` group keys that partition per foreman the same way `_HELPER_{name}` does today, so reading `sorted_rows[0]` for HELPER/HELPER_DEPT/HELPER_JOB is safe.

**Change 2 — D-20 fingerprint mix-in block (L1933-1947 in `generate_weekly_pdfs.py`):**
```python
# Per Phase 01 Plan 02 D-20: mix the subcontractor rates
# fingerprint into the hash ONLY for the four new variants
# that actually consume the subcontractor rates CSV.
if variant in (
    'aep_billable',
    'reduced_sub',
    'aep_billable_helper',
    'reduced_sub_helper',
):
    if _SUBCONTRACTOR_RATES_FINGERPRINT:
        meta_parts.append(
            f"SUB_RATES_FP={_SUBCONTRACTOR_RATES_FINGERPRINT}"
        )
```

This block sits AFTER the legacy `if RATE_CUTOFF_DATE: ... RATES_FP=` block. The two blocks are parallel — one keys on the retired-but-retained legacy recalc gate, the other keys on the variant set that consumes the new rates table.

**Final `meta_parts` shape for each variant:**

| Variant | meta_parts entries (order) |
|---------|----------------------------|
| `primary` | FOREMAN, VARIANT, DEPTS, TOTAL, ROWCOUNT |
| `helper` | FOREMAN, VARIANT, HELPER, HELPER_DEPT, HELPER_JOB, DEPTS, TOTAL, ROWCOUNT |
| `vac_crew` | FOREMAN, VARIANT, DEPTS, TOTAL, ROWCOUNT (per-row __vac_crew_* in row_str loop) |
| `aep_billable` | FOREMAN, VARIANT, DEPTS, TOTAL, ROWCOUNT, **SUB_RATES_FP** |
| `reduced_sub` | FOREMAN, VARIANT, DEPTS, TOTAL, ROWCOUNT, **SUB_RATES_FP** |
| `aep_billable_helper` | FOREMAN, VARIANT, HELPER, HELPER_DEPT, HELPER_JOB, DEPTS, TOTAL, ROWCOUNT, **SUB_RATES_FP** |
| `reduced_sub_helper` | FOREMAN, VARIANT, HELPER, HELPER_DEPT, HELPER_JOB, DEPTS, TOTAL, ROWCOUNT, **SUB_RATES_FP** |

If `RATE_CUTOFF_DATE` is set (retired but possible), `RATE_CUTOFF` + (if `_RATES_FINGERPRINT` is set) `RATES_FP` appear between ROWCOUNT and SUB_RATES_FP for every variant.

**Test coverage:**
- `TestSubcontractorVariantHashAggregation` (`tests/test_vac_crew.py`) — 10 tests:
  - 1 test confirms VARIANT-token discrimination (existing meta-part) distinguishes primary from aep_billable.
  - 4 tests confirm SUB_RATES_FP mutation changes hash for each of the 4 new variants.
  - 3 tests confirm SUB_RATES_FP mutation does NOT change hash for primary / helper / vac_crew.
  - 2 tests confirm the helper meta block fires for both new shadow-helper variants (HELPER_DEPT edit + HELPER name edit propagate to hash).
- Existing `TestVacCrewHashAggregation` (7 tests) — confirmed no regression.

### Task 3 — `_PII_LOG_MARKERS` + collision regression locks (commits `e011a9f` RED + `25cd303` GREEN)

**`_PII_LOG_MARKERS` extension** (L778-783 in `generate_weekly_pdfs.py`, appended at end of tuple):

```python
"_AEPBILLABLE",
"_REDUCEDSUB",
"_AEPBILLABLE_HELPER_",
"_REDUCEDSUB_HELPER_",
"AEP BILLABLE GROUP CREATED",
"REDUCED SUB GROUP CREATED",
"Subcontractor rates CSV missing",
```

Group-key prefix markers (the 4 with leading underscores) match log bodies that embed any of Plan 3's group keys — equivalent to the existing `_HELPER_` / `_VACCREW` markers for the legacy variant set. The "AEP BILLABLE GROUP CREATED" / "REDUCED SUB GROUP CREATED" tokens cover Plan 3's INFO-level group-creation logs. The "Subcontractor rates CSV missing" token covers the missing-CU WARNING that will embed the literal CU code (row-level data).

**Source-side WR collision pre-scan** — NO code change required. The existing round-9 contract (sanitized WR alone, not a tuple) already covers cross-variant and cross-week collisions for the four new variants. Locked with 3 new regression tests in `TestSourceWrCollisionQuarantine`:
- `test_pre_scan_catches_aep_billable_cross_variant_collision` — sanitization-colliding aep_billable + reduced_sub pair quarantined.
- `test_pre_scan_catches_aep_billable_cross_week_collision` — sanitization-colliding aep_billable + aep_billable across weeks quarantined.
- `test_pre_scan_does_not_false_positive_distinct_subcontractor_variants` — realistic numeric WR#s do NOT trigger false-positive (noise-free on production data).

**Test coverage:**
- `TestPiiLogMarkersIncludeSubcontractorVariants` — 8 tests (one per marker + one all-7-at-once assertion). The all-7 test mirrors the plan's verification command exactly.

## Task Commits

Six commits in TDD order (RED test commit → GREEN feature commit per task):

1. **Task 1 RED — failing parser tests** — `2c45fc8` (test)
2. **Task 1 GREEN — parser extension** — `bac4895` (feat)
3. **Task 2 RED — failing hash tests** — `4295c0c` (test)
4. **Task 2 GREEN — hash extension** — `16f3ca4` (feat)
5. **Task 3 RED — failing markers + new collision regression tests** — `e011a9f` (test)
6. **Task 3 GREEN — markers extension** — `25cd303` (feat)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- `generate_weekly_pdfs.py`:
  - **`_PII_LOG_MARKERS` tuple (~L760-783):** 7 new markers appended at end. Documented with an inline block comment pointing at Living Ledger 2026-04-20 12:00.
  - **`calculate_data_hash` (~L1889-1947):** helper meta block trigger extended to tuple membership; new SUB_RATES_FP mix-in block added after the legacy RATES_FP block.
  - **`build_group_identity` (~L2118-2231):** docstring extended with 8 supported filename formats; 2 new variant branches inserted before Helper/VacCrew/User branches.
- `tests/test_vac_crew.py`:
  - **`TestSubcontractorVariantGroupIdentityParsing` (new class, ~L136-232):** 7 tests for the 4 new variant filename formats + identity-tuple distinctness.
  - **`TestSubcontractorVariantHashAggregation` (new class, ~L518-741):** 10 tests for VARIANT-token discrimination, SUB_RATES_FP mix-in (positive + 3 negative), and helper meta-block reuse for shadow-helper variants.
- `tests/test_security_audit_followup.py`:
  - **5 new tests inside `TestBuildGroupIdentityWithUnderscoresInWr`** — tail-scoping negatives (WR# containing AEPBillable / ReducedSub literal token → variant='primary'), no-regression on plain helper, and underscored-WR round-trip for both new helper variants.
  - **3 new tests inside `TestSourceWrCollisionQuarantine`** — cross-variant / cross-week / no-false-positive coverage for the 4 new variants.
  - **`TestPiiLogMarkersIncludeSubcontractorVariants` (new class, ~L1402-1469):** 8 tests asserting all 7 new markers are present.

## Decisions Made

- **Variant-first ordering (D-09).** The `'AEPBillable' in tail` and `'ReducedSub' in tail` checks MUST run BEFORE the existing `'Helper' in tail` check so a `..._AEPBillable_Helper_<name>_<hash>` filename parses as `aep_billable_helper`, not as plain `helper` with the AEPBillable token silently dropped. Inserted as the first two branches in the if/elif cascade; existing branches drop into elif positions verbatim.
- **Tail-scoped detection (D-10).** Both new branches operate on the `parts[we_idx + 2:]` tail slice. A sanitized WR# that happens to contain the literal `AEPBillable` / `ReducedSub` token does not false-positive the variant — covered by `test_wr_containing_literal_aep_billable_token_no_false_variant` / `test_wr_containing_literal_reduced_sub_token_no_false_variant`.
- **Conditional fingerprint mix-in scoped exactly to the 4 new variants (D-20).** A tuple membership check (`variant in ('aep_billable', 'reduced_sub', 'aep_billable_helper', 'reduced_sub_helper')`) wraps the SUB_RATES_FP meta_parts.append. ROADMAP success criterion 5 (existing outputs byte-identical) is locked by 3 negative tests covering primary/helper/vac_crew.
- **Helper meta-block trigger extended via tuple membership** rather than a parallel block: keeps validation / WARNING / meta_parts logic in ONE place. Plan 3 will emit `_AEPBILLABLE_HELPER_{name}` / `_REDUCEDSUB_HELPER_{name}` group keys that partition per foreman the same way `_HELPER_{name}` does, so reading `sorted_rows[0]` is safe.
- **Source-side WR collision pre-scan NOT modified.** The existing round-9 contract (sanitized WR alone) already covers the new variants. Adding a code change would have been gratuitous; instead, locked the existing behaviour with 3 new regression tests so a future refactor cannot silently re-narrow the key.
- **PII markers added in Plan 02 even though Plan 03 will emit the corresponding INFO logs.** The sanitizer must lead the call sites by at least one plan — defense in depth per Living Ledger 2026-04-20 12:00. The all-7-at-once regression test catches removal of any one marker immediately.

## Deviations from Plan

None — plan executed exactly as written. Every acceptance criterion grep returns its expected matches, every verification command exits 0, every test passes.

## Issues Encountered

- **Worktree path resolution issue.** Early in Task 1, the Edit tool's view of the test files showed my added test class, but pytest in the worktree reported only the pre-existing 37 tests. Root cause: my first set of Edit calls used the canonical absolute path (`c:\Users\juflores\dev\Generate-Weekly-PDFs-DSR-Resiliency\tests\test_vac_crew.py`) instead of the worktree path (`c:\Users\juflores\dev\Generate-Weekly-PDFs-DSR-Resiliency\.claude\worktrees\agent-a0fc38b93ae5077ba\tests\test_vac_crew.py`). The edits landed in the canonical tree, which the worktree's pytest run did NOT see. Reverted via `git checkout --` in canonical, then re-applied using the worktree absolute path. Going forward, used the worktree path explicitly for every Edit / Read / Write call.
- **Windows console encoding.** PowerShell's default cp1252 codec rejected the emoji glyph in `print("\U0001f50d ...")` at module load on stderr/stdout. Worked around by passing `PYTHONUTF8=1 python -X utf8` to every pytest invocation. No source change required — the env-var pattern is the documented escape hatch.

## User Setup Required

None — Plan 2 changes are entirely internal to `generate_weekly_pdfs.py` and the test suite. No env vars added, no operator action required.

## Known Stubs

None — every change in this plan is wired up and exercised by tests. The new variant strings (`aep_billable`, `reduced_sub`, `aep_billable_helper`, `reduced_sub_helper`) do not yet appear as `__variant` values in production output because Plan 3 (variant emission via `group_source_rows`) is the next plan on this wave. That's not a stub — it's expected sequencing.

## Threat Surface Notes

No new threat surface introduced beyond what the plan's `<threat_model>` already enumerated. The 5 STRIDE entries (T-02-01 through T-02-05) are all mitigated:

- **T-02-01 (Tampering, filename → variant detection):** Tail-scoping locks the invariant. Covered by `test_wr_containing_literal_aep_billable_token_no_false_variant` + `test_wr_containing_literal_reduced_sub_token_no_false_variant`.
- **T-02-02 (Information Disclosure, group-creation INFO logs):** 7 new markers in `_PII_LOG_MARKERS`. Locked by `TestPiiLogMarkersIncludeSubcontractorVariants`.
- **T-02-03 (Tampering, hash key for new variants):** Internal-only; no external surface. Accepted as planned.
- **T-02-04 (Repudiation, variant attribution loss):** Round-trip filename ↔ tuple conversion proven for all 4 new variants via `TestSubcontractorVariantGroupIdentityParsing`.
- **T-02-05 (Denial of Service, hash byte-identical regression):** D-20 fingerprint scoping locked by 3 negative tests (primary/helper/vac_crew hashes byte-identical under SUB_RATES_FP mutation).

## Next Phase Readiness

- **Plan 01-03 (variant emission) is unblocked.** It can now emit `_AEPBillable` / `_ReducedSub` / `_AEPBillable_Helper_<name>` / `_ReducedSub_Helper_<name>` filenames into `generated_docs/`, knowing:
  - The parser will round-trip them correctly (Task 1).
  - The hash will invalidate them when the subcontractor CSV changes (Task 2).
  - The PII sanitizer will drop any INFO logs that embed their group keys (Task 3).
- **Plan 01-04 (dual routing)** depends on the parser's `(wr, week, variant, identifier)` tuple for attachment-identity routing — also unblocked.
- **Plan 01-05 (shadow helper)** depends on the helper meta-block tuple-membership extension landed in Task 2 — also unblocked.
- **No blockers.** All four downstream plans now have the parser + hash + sanitiser foundation they need.

## Self-Check

Performed inline before writing this section:

- `git log --oneline worktree-agent-a0fc38b93ae5077ba ^e8e02a9` shows 6 commits in TDD order: **FOUND** (`2c45fc8`, `bac4895`, `4295c0c`, `16f3ca4`, `e011a9f`, `25cd303`)
- `grep -nE "if 'AEPBillable' in tail" generate_weekly_pdfs.py` → L2191: **FOUND**
- `grep -nE "elif 'ReducedSub' in tail" generate_weekly_pdfs.py` → L2205: **FOUND**
- AEPBillable (L2191) + ReducedSub (L2205) + Helper (L2216) ordering: **CONFIRMED** (variant-first)
- `grep -nE "variant in \('helper', 'aep_billable_helper', 'reduced_sub_helper'\)" generate_weekly_pdfs.py` → L1889: **FOUND**
- `grep -nE "SUB_RATES_FP=" generate_weekly_pdfs.py` → L1944: **FOUND**
- `grep -nE "RATES_FP=" generate_weekly_pdfs.py` → L1921 (legacy) + L1944 (new): **BOTH PRESENT, DISTINCT STRINGS**
- `grep -nE '"_AEPBILLABLE"' generate_weekly_pdfs.py` → L778: **FOUND**
- `grep -nE '"_REDUCEDSUB"' generate_weekly_pdfs.py` → L779: **FOUND**
- `grep -nE '"Subcontractor rates CSV missing"' generate_weekly_pdfs.py` → L784: **FOUND**
- `python -c "import generate_weekly_pdfs as g; r=g.build_group_identity('WR_91467680_WeekEnding_041926_123456_AEPBillable_ab12cd34ef.xlsx'); assert r is not None and r[2]=='aep_billable' and r[3]==''"` → exit 0: **CONFIRMED**
- `python -c "import generate_weekly_pdfs as g; r=g.build_group_identity('WR_91467680_WeekEnding_041926_123456_ReducedSub_Helper_Jane_Smith_ab12cd34ef.xlsx'); assert r is not None and r[2]=='reduced_sub_helper' and r[3]=='Jane_Smith'"` → exit 0: **CONFIRMED**
- `python -c "import generate_weekly_pdfs as g; r=g.build_group_identity('WR_AEPBillable_WeekEnding_041926_123456_ab12cd34ef.xlsx'); assert r is not None and r[0]=='AEPBillable' and r[2]=='primary'"` → exit 0: **CONFIRMED (tail-scoping)**
- Inline D-20 byte-identical guarantee: `g._SUBCONTRACTOR_RATES_FINGERPRINT='A'; h1=...; g._SUBCONTRACTOR_RATES_FINGERPRINT='B'; h2=...; assert h1==h2` for `__variant='primary'` → exit 0: **CONFIRMED**
- `python -m py_compile generate_weekly_pdfs.py` → exit 0: **CONFIRMED**
- `pytest tests/test_vac_crew.py::TestSubcontractorVariantGroupIdentityParsing` → 7 passed: **CONFIRMED**
- `pytest tests/test_vac_crew.py::TestSubcontractorVariantHashAggregation` → 10 passed: **CONFIRMED**
- `pytest tests/test_vac_crew.py::TestVacCrewHashAggregation` → 7 passed (no regression): **CONFIRMED**
- `pytest tests/test_security_audit_followup.py::TestSourceWrCollisionQuarantine` → 7 passed (4 existing + 3 new): **CONFIRMED**
- `pytest tests/test_security_audit_followup.py::TestPiiLogMarkersIncludeSubcontractorVariants` → 8 passed: **CONFIRMED**
- `pytest tests/` full suite → 459 passed / 22 skipped / 0 failed: **CONFIRMED**
- All 6 variant suffixes (AEPBillable, ReducedSub, AEPBillable_Helper_Foo, ReducedSub_Helper_Bar, Helper_Baz, VacCrew) produce non-None tuples with the correct variant string: **CONFIRMED**

## Self-Check: PASSED

## TDD Gate Compliance

All three tasks followed the RED/GREEN cycle with separate commits:

| Task | RED commit (test) | GREEN commit (feat) |
|------|-------------------|---------------------|
| 1 (parser) | `2c45fc8 test(01-02): add failing tests for new subcontractor variants` | `bac4895 feat(01-02): parse _AEPBillable and _ReducedSub variant filenames` |
| 2 (hash) | `4295c0c test(01-02): add failing hash tests for D-20 fingerprint mix-in` | `16f3ca4 feat(01-02): mix subcontractor fingerprint into hash for new variants` |
| 3 (markers + collision locks) | `e011a9f test(01-02): add markers/collision tests for subcontractor variants` | `25cd303 feat(01-02): extend _PII_LOG_MARKERS with subcontractor variant tokens` |

Each RED commit was verified to FAIL the new tests (8 / 6 / 8 failures respectively) before the corresponding GREEN commit was made.

---

*Phase: 01-subcontractor-rate-logic-modification*
*Plan: 02*
*Completed: 2026-05-14*
