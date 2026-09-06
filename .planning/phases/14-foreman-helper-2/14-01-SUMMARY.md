---
phase: 14-foreman-helper-2
plan: 01
subsystem: billing-pipeline
tags: [python, smartsheet, openpyxl, foreman-helper, change-detection]

# Dependency graph
requires: []
provides:
  - "HELPER2_ENABLED default-off flag (pipeline/config.py) and FORMULA_ERROR_VALUES / normalize_helper_value (pipeline/types.py)"
  - "sheet_has_helper2_columns capability gate + _detect_helper2_row row detection (pipeline/fetch.py)"
  - "helper2 variant: group-key emission (pipeline/grouping.py), HELPER2= hash meta + 'Helper2' filename token (pipeline/change_detection.py), derive_group_identity branch (pipeline/orchestrate.py), _Helper2_<name> filename + REPORT DETAILS header (pipeline/excel.py)"
  - "tests/test_foreman_helper_2.py (new), tests/test_helper2_family_parity.py (new) -- reusable regression harness for later Phase 14 plans"
affects: [14-02, 14-03, 14-04, 14-05, 14-06, 14-07, 14-08, 14-09, 14-10]

# Actuals (#2632)
actuals:
  tokens: 14453
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sibling-branch cloning: every Helper #2 site is a parallel `if variant in ('helper2', ...)` block next to the Helper #1 block, never a widened tuple (D-14-11)"
    - "Fabricated-claim guard (D-14-05): normalize_helper_value() routes a raw Smartsheet cell through a formula-error + 'NA' + blank/whitespace filter BEFORE the truthiness check, unlike Helper #1's bare str().strip()"
    - "Extracted row-detection function (_detect_helper2_row in pipeline/fetch.py) instead of inlining, so the fetch-layer eligibility formula is directly unit-testable without a full Smartsheet client mock"
    - "Source-text family-parity guard (tests/test_helper2_family_parity.py): pinned file table + quoted-literal sibling pairs, with a KNOWN_DEFERRED allowlist for gaps a NAMED later plan closes"

key-files:
  created:
    - tests/test_foreman_helper_2.py
    - tests/test_helper2_family_parity.py
  modified:
    - pipeline/types.py
    - pipeline/config.py
    - pipeline/discovery.py
    - pipeline/fetch.py
    - pipeline/grouping.py
    - pipeline/change_detection.py
    - pipeline/orchestrate.py
    - pipeline/excel.py
    - tests/test_group_identity_and_header_foreman.py
    - tests/test_change_detection_tiebreak.py
    - tests/test_subcontractor_pricing.py
    - tests/test_subcontractor_helper_shadow_rescue.py

key-decisions:
  - "Extracted pipeline/fetch.py's Helper #2 row-detection formula into a standalone _detect_helper2_row() function (not inlined like Helper #1's block) so it is directly unit-testable without mocking a full Smartsheet Sheets.get_sheet() response -- Helper #1's own detection has no equivalent unit test in this repo."
  - "D-14-05's fabricated-claim guard was extended beyond the plan's literal 11-token FORMULA_ERROR_VALUES set to also reject the literal placeholder 'NA' (case-insensitive) inside normalize_helper_value() -- required by the plan's own must_haves truth and Task 3 <behavior> list, which name 'NA' as a required non-claim distinct from the eleven Smartsheet formula-error tokens."
  - "tests/test_helper2_family_parity.py uses a paired-literal design (SIBLING_PAIRS + a per-file KNOWN_DEFERRED allowlist) rather than requiring the full 3-member Helper #2 family in every pinned file immediately -- pipeline/excel.py's two subcontractor shadow branches are plan 14-06's work per this plan's own action items, so the parity test names that gap explicitly instead of failing or silently under-checking it."

patterns-established:
  - "Sibling-branch cloning for a second independently-identifiable role slot: never widen an existing variant tuple/frozenset; add a parallel block reading a distinct row-metadata prefix (__helper2_*)."
  - "Row-detection extraction for testability: a fetch-layer per-row eligibility formula lives in a standalone function taking the sheet-level capability booleans as keyword args, so it can be unit-tested without a Smartsheet client mock."

requirements-completed: [HLP-01, HLP-02, HLP-05, HLP-06, HLP-07]

coverage:
  - id: D1
    description: "One eligible Helper #2 completion travels discovery -> fetch -> grouping -> change-detection identity -> workbook -> filename -> filename round-trip, naming the same person at every hop, and is absent from the primary file for the same WR/week"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoTracerTests::test_single_helper2_row_travels_end_to_end"
        status: pass
    human_judgment: false
  - id: D2
    description: "A generated _Helper2_<name> filename round-trips through build_group_identity to variant 'helper2' and the identical sanitized identifier"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoTracerTests::test_single_helper2_row_travels_end_to_end"
        status: pass
    human_judgment: false
  - id: D3
    description: "Legacy primary / Helper #1 / VAC-crew group keys, content hashes, and filenames are unchanged by the presence of the new helper2 code path (D-14-09 byte-identity guarantee)"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_change_detection_tiebreak.py#HelperTwoHashMetaTests"
        status: pass
      - kind: unit
        ref: "tests/test_group_identity_and_header_foreman.py#DeriveGroupIdentityTests"
        status: pass
      - kind: unit
        ref: "tests/ -q (full suite, 2140 passed / 1 skipped, no golden hash constant changed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every non-claim input (blank, NA, each FORMULA_ERROR_VALUES token, whitespace-only, unchecked completion, unchecked units, missing dept, capability-absent sheet, HELPER2_ENABLED off) produces no __is_helper2_row flag, no helper2 group, and no helper2 workbook"
    requirement: "HLP-05"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoFabricatedClaimGuardTests"
        status: pass
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoMissingDeptExclusionTests::test_missing_dept_produces_no_helper2_group"
        status: pass
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoCapabilityAbsentDiscoveryTests::test_sheet_without_helper2_columns_is_not_rejected"
        status: pass
    human_judgment: false
  - id: D5
    description: "HELPER2_ENABLED defaults to off; the phase-wide vocabulary (variant strings, filename tokens, row-metadata keys, log reason codes) is locked for later Phase 14 plans"
    requirement: "HLP-07"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoFabricatedClaimGuardTests::test_helper2_enabled_off_disables_detection_for_an_otherwise_valid_row"
        status: pass
    human_judgment: false

duration: ~30min
completed: 2026-09-06
status: complete
---

# Phase 14 Plan 01: Helper #2 Tracer Summary

**One eligible `Foreman Helping? #2` completion travels the entire Smartsheet-to-Excel pipeline behind a default-off `HELPER2_ENABLED` flag, producing a correctly named `helper2` group, `_Helper2_<name>` workbook, and round-trippable filename, with every legacy identity pinned unchanged and every non-claim input proven inert.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 3/3 completed
- **Files modified:** 8 production modules + 4 test files (2 new)
- **Commits:** 3 task commits + this docs commit

## Accomplishments

- Wired the complete Helper #2 path — discovery synonyms, a hard per-sheet capability gate, fabricated-claim-guarded row detection, group-key emission, change-detection hash meta + filename token, `derive_group_identity` branch, and Excel filename/header rendering — as parallel sibling blocks to every existing Helper #1 site, never widening a Helper #1 tuple or frozenset.
- Implemented D-14-05's fabricated-claim guard (`pipeline/types.py`'s `FORMULA_ERROR_VALUES` + `normalize_helper_value`) so blank, whitespace-only, `NA`, and all eleven Smartsheet formula-error tokens are non-claims on the Helper #2 path from day one — the exact defect class Helper #1 still carries today (left untouched, out of scope).
- Proved the whole path end-to-end with a real production-code-driven test (`group_source_rows` → `calculate_data_hash` → `derive_group_identity` → `generate_excel` → `build_group_identity` round-trip → workbook header read-back), plus a fixture battery covering every documented non-claim input and a source-text parity guard for the Helper #1/#2 sibling literal sets.
- Fixed 3 pre-existing source-text invariant assertions (in `tests/test_subcontractor_pricing.py` and `tests/test_subcontractor_helper_shadow_rescue.py`) that pinned the exact literal text of the primary-emission partitioning gate, which this plan legitimately extended with `and not valid_helper2_row`.

## Task Commits

Each task was committed atomically:

1. **Task 1: One Helper #2 completion, end-to-end, one path only** — `3d6bcfb` (feat)
2. **Task 2: Legacy identities are unchanged when Helper #2 is absent** — `f7edb79` (test)
3. **Task 3: Nothing fabricates a Helper #2 claim** — `09017f8` (test)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified

- `pipeline/types.py` — `FORMULA_ERROR_VALUES` (11 Smartsheet error tokens) + `normalize_helper_value()` (D-14-05 fabricated-claim guard, also rejects the literal `NA`)
- `pipeline/config.py` — `HELPER2_ENABLED` flag, default `'0'` (D-14-12)
- `pipeline/discovery.py` — 6 additive Helper #2 column synonyms (bracket-form job title mirrors `Helper Job [#]`)
- `pipeline/fetch.py` — `sheet_has_helper2_columns` hard capability gate (mirrors `sheet_has_vac_crew_columns`) + `_detect_helper2_row()` (extracted, unit-testable row-detection function)
- `pipeline/grouping.py` — `valid_helper2_row` + `helper2` group-key emission, sibling to every Helper #1 exclusion/emission site (Pattern B subcontractor guard copied verbatim)
- `pipeline/change_detection.py` — `HELPER2=`/`HELPER2_DEPT=`/`HELPER2_JOB=` hash meta sibling block + `'Helper2'` reserved filename token
- `pipeline/orchestrate.py` — one new `derive_group_identity` branch for the helper2 family (main() still calls it from exactly 2 sites)
- `pipeline/excel.py` — `_Helper2_<name>` filename suffix branch + REPORT DETAILS header branch (`Unknown Helper 2` fallback)
- `tests/test_foreman_helper_2.py` (new) — tracer E2E test (Task 1) + fabricated-claim-guard fixture battery (Task 3)
- `tests/test_helper2_family_parity.py` (new) — source-text sibling-literal parity guard (Task 2)
- `tests/test_group_identity_and_header_foreman.py`, `tests/test_change_detection_tiebreak.py` — Task 2 regression cases pinning primary/Helper #1/VAC-crew identities and hashes unchanged
- `tests/test_subcontractor_pricing.py`, `tests/test_subcontractor_helper_shadow_rescue.py` — updated 3 source-text invariant literals to match the extended partitioning gate

## Decisions Made

- **Extracted `_detect_helper2_row()` as a standalone function** in `pipeline/fetch.py` rather than inlining the row-detection block like Helper #1's, so the fetch-layer eligibility formula (including the `normalize_helper_value` fabricated-claim guard) is directly unit-testable without mocking a full Smartsheet `Sheets.get_sheet()` response — the established test-suite convention has no such test for Helper #1's own inline block. This is a "same stages, same modules" sibling clone; the plan's D-14-04/D-14-05 behavior contract is unchanged, only the code's shape at this one site.
- **Extended the fabricated-claim guard to reject literal `NA`** (case-insensitive), beyond the plan's literally-enumerated 11-token `FORMULA_ERROR_VALUES` set. The plan's own `must_haves.truths` and Task 3 `<behavior>` list name `NA` as a required non-claim value distinct from "any other member of FORMULA_ERROR_VALUES" (D-14-05: "this is the case Helper #1 gets wrong today and Helper #2 must get right from day one"), but the prototype's literal `FORMULA_ERROR_VALUES` frozenset — which Task 1's action text names as the exact 11-item source — does not itself contain `NA`. Resolved by keeping `FORMULA_ERROR_VALUES` exactly as specified (11 members) and adding a separate `_NON_CLAIM_LITERALS` check inside `normalize_helper_value()` for the `NA` placeholder, so both the plan's literal spec and its behavioral requirement are satisfied without contradiction.
- **`tests/test_helper2_family_parity.py` uses a paired-literal design** with a per-file `KNOWN_DEFERRED` allowlist rather than requiring all three Helper #2 family members in every pinned file today. `pipeline/excel.py` currently has only the plain `'helper2'` sibling (its two subcontractor shadow branches are explicitly plan 14-06's work per this plan's Task 1 action item 8), so the parity test names that gap explicitly and will fail loudly if 14-06 lands without clearing the `KNOWN_DEFERRED` entry, or if the gap is accidentally introduced elsewhere.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 3 broken source-text invariant test assertions**
- **Found during:** Task 1 (full-suite verification run after committing the grouping.py change)
- **Issue:** `pipeline/grouping.py`'s primary-emission partitioning gate (`if not is_subcontractor_row and not valid_helper_row:`) and its diagnostic sibling (`elif is_subcontractor_row and not valid_helper_row:`) needed extending to `and not valid_helper2_row` per Task 1's own action item 5 ("exclude a valid Helper #2 row from primary emission the same way"). Two existing regression tests (`tests/test_subcontractor_helper_shadow_rescue.py::TestProductionCodeSiteInvariants::test_bug_b1_partitioning_gate_present_in_production` and `tests/test_subcontractor_pricing.py::TestSubcontractorB1PartitioningGate::test_source_level_grep_partitioning_gate_present`) pinned the exact pre-change literal text of these two gates via `assertIn`, so the legitimate extension broke 2 tests across 3 assertions.
- **Fix:** Updated the 3 pinned literal strings in both test files to the new exact gate text (`... and not valid_helper2_row:`), with a comment citing this plan.
- **Files modified:** `tests/test_subcontractor_helper_shadow_rescue.py`, `tests/test_subcontractor_pricing.py`
- **Verification:** `pytest tests/ -q` → 2118 passed / 1 skipped (post-fix, pre-Task-2)
- **Committed in:** `3d6bcfb` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — necessary test-literal update for a plan-mandated production change).
**Impact on plan:** No scope creep; both fixes are the direct, foreseeable consequence of Task 1's own action items. No behavior change to the fixed tests' actual intent (they still pin the gate's exact text, just the post-Phase-14 text).

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None — no external service configuration required. `HELPER2_ENABLED` defaults off; no Smartsheet column provisioning, Supabase migration, or GitHub Actions change occurred in this plan (all explicitly out of scope per the plan's prohibitions).

## Evidence Label

**FIXTURE PASS only** — every assertion in this plan runs against synthetic in-memory row dicts and mocked Smartsheet client objects. Not a dry-run, not a controlled upload, not a production observation. Live Smartsheet column verification, controlled-flag-on staging, and production rollout are later plans in this phase (14-07 through 14-10).

## Next Phase Readiness

- The `helper2` variant (plain, non-shadow) is fully wired and covered end-to-end; plan 14-06 can build the `aep_billable_helper2` / `reduced_sub_helper2` subcontractor shadow variants on top of this proven path (extending `pipeline/excel.py`'s two deferred branches and clearing the `KNOWN_DEFERRED` entries in `tests/test_helper2_family_parity.py`).
- Plan 14-05's cleanup/upload work (`pipeline/cleanup.py`'s `_HELPER_VARIANTS_FOR_ORPHAN_GATE`, `pipeline/upload.py`'s PPP dual-route gate) and plan 14-03's `billing_audit/writer.py` attribution freeze/resolve work both have a proven `__helper2_*` row-metadata contract to build against.
- No blockers. `HELPER2_ENABLED` stays off in every environment until an explicit later-plan checkpoint enables it for controlled testing.

## Self-Check: PASSED

All created/modified files found on disk; all 3 task commit hashes (`3d6bcfb`, `f7edb79`, `09017f8`) found in `git log --oneline --all`.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-06*
