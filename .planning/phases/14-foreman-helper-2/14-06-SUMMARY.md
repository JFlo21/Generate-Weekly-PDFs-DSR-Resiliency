---
phase: 14-foreman-helper-2
plan: 06
subsystem: billing-pipeline
tags: [python, smartsheet, foreman-helper, subcontractor, change-detection, tdd]

# Dependency graph
requires:
  - phase: 14-01
    provides: "HELPER2_ENABLED flag, the six Helper #2 column titles, __helper2_foreman row key, the helper2 / aep_billable_helper2 / reduced_sub_helper2 tokens, the '_Helper2_' filename token, HELPER2= hash meta, and the plain helper2 emission path in pipeline/grouping.py"
  - phase: 14-03
    provides: "billing_audit/writer.py ROLE_BY_VARIANT['helper2'] and resolve_claimer's Helper #2 role resolution"
  - phase: 14-05
    provides: "pipeline/cleanup.py orphan-gate coverage and the publisher/portal-label extensions for the Helper #2 family"
provides:
  - "pipeline/grouping.py: _sub_is_valid_helper2_row gate excluding a Helper #2-completed subcontractor row from the primary reduced_sub/aep_billable emission, and the reduced_sub_helper2 / aep_billable_helper2 shadow leg partitioned via resolve_claimer('helper2', ...)"
  - "pipeline/excel.py: aep_billable_helper2 / reduced_sub_helper2 filename elif branches (defensive raise on empty foreman) and a header-dispatch branch showing the attributed claimer with Helper #2 dept/job"
  - "pipeline/change_detection.py: nested Helper2 checks inside the AEPBillable/ReducedSub reserved-token filename branches, and helper2 sub-bucketing in the aggregated content hash"
  - "pipeline/upload.py: reduced_sub_helper2 joins the second-leg PPP routing tuple"
  - "tests/test_helper2_family_parity.py: pinned table now covers pipeline/upload.py and pipeline/grouping.py in addition to the entries from plans 14-01 and 14-05; the pipeline/excel.py KNOWN_DEFERRED entries are cleared"
affects: [14-08, 14-09, 14-10]

# Actuals (#2632)
actuals:
  tokens: 12988
  tasks: 3
  commits: 3
  plan_head_before: dcf240693f07181c01d9246931f779957fd74cb4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Subcontractor shadow-leg cloning: every Helper #2 shadow emission site (grouping key, filename suffix, header dispatch, filename parse, aggregated hash sub-bucket, PPP routing) is a sibling elif/branch copied character-for-character from the adjacent Helper #1 site, never a widened tuple -- preserves the D-14-11 vocabulary lock and avoids the 2026-05-19/2026-05-21 incident shapes"
    - "mypy Gate 4 hygiene inside an unchecked function: a bare (unannotated) local variable, not a PEP 526 `name: T = value` annotation, avoids a new annotation-unchecked note when adding code to a function mypy already skips body-checking for"

key-files:
  created: []
  modified:
    - pipeline/grouping.py
    - pipeline/excel.py
    - pipeline/change_detection.py
    - pipeline/upload.py
    - tests/test_subcontractor_helper_shadow_rescue.py
    - tests/test_helper2_family_parity.py

key-decisions:
  - "The primary reduced_sub/aep_billable emission gate (`if not _sub_is_valid_helper_row:`) now also checks `not _sub_is_valid_helper2_row` in the SAME edit that adds the new variable -- a Helper #2-completed subcontractor row must never leak into the primary variant, mirroring the existing Helper #1 exclusion exactly."
  - "The both-slots-valid case (a row with BOTH a valid Helper #1 AND a valid Helper #2 completion) takes NO position: neither shadow-leg gate excludes the other, so today's behavior is additive -- both families' shadow keys emit. This is documented and pinned by a test, not silently resolved; O-14-A remains owner-blocked and plan 14-08 owns the eventual rule."
  - "Dropped the local PEP 526 annotation on the new `_attribution_reason2` variable in pipeline/grouping.py (Rule 1 fix) -- an annotated assignment inside the unchecked `group_source_rows` function body adds a new mypy 'annotation-unchecked' note, tripping Gate 4's strict delta check (71 -> 72) even though there is no real type error. The Helper #1 sibling variable is not annotated at that scope either."
  - "Sub-bucketing in the aggregated content hash's 'helper2' branch excludes the shadow variants (reduced_sub_helper2 / aep_billable_helper2), exactly matching the pre-existing Helper #1 scope -- 14-RESEARCH.md classifies the shadow-variant gap as unrelated and pre-existing, not introduced by this phase."

patterns-established:
  - "A sibling-branch clone plan (D-14-03 'same stages, same modules') should copy control-flow shape character-for-character from its analog, including subcontractor guards and cutoff comparisons, rather than re-deriving logic that has a documented incident history."

requirements-completed: [HLP-01, HLP-02, HLP-05]

coverage:
  - id: D1
    description: "A subcontractor row with a valid Helper #2 completion emits exactly the reduced_sub_helper2 key (always) and the aep_billable_helper2 key (post-cutoff snapshot only) -- never a plain helper2 key and never the subcontractor primary key"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestSubcontractorHelper2ShadowRescue::test_subcontractor_helper2_row_emits_shadow_keys_only"
        status: pass
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestSubcontractorHelper2ShadowRescue::test_subcontractor_helper2_row_pre_cutoff_emits_only_reducedsub_helper2"
        status: pass
    human_judgment: false
  - id: D2
    description: "The VAC-crew short-circuit wins over a Helper #2 completion, exactly as it wins over Helper #1"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestSubcontractorHelper2ShadowRescue::test_vac_crew_row_with_helper2_takes_vac_path"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Helper #2 shadow claimant is resolved through billing_audit's Helper #2 role (resolve_claimer('helper2', ...)), not the primary or Helper #1 role"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestSubcontractorHelper2ShadowRescue::test_helper2_shadow_claimant_resolves_through_helper2_role"
        status: pass
    human_judgment: false
  - id: D4
    description: "Helper #2 shadow filenames (_AEPBillable_Helper2_<name> / _ReducedSub_Helper2_<name>) render correctly, raise on empty foreman, show the attributed claimer with Helper #2 dept/job in the header, and parse back to their own variant; a bare _AEPBillable_User_ filename and the Helper #1 shadow parse path are unchanged"
    requirement: "HLP-02"
    verification:
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2ShadowExcelRendering::test_aep_billable_helper2_filename_includes_sanitized_name"
        status: pass
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2ShadowExcelRendering::test_reduced_sub_helper2_shows_helper2_dept_and_job"
        status: pass
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2FilenameParsingAndAggregatedHash::test_aep_billable_helper2_filename_parses_to_shadow_variant"
        status: pass
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2FilenameParsingAndAggregatedHash::test_bare_reduced_sub_helper_filename_still_parses_unchanged"
        status: pass
      - kind: unit
        ref: "tests/test_change_detection_tiebreak.py"
        status: pass
      - kind: unit
        ref: "tests/test_group_identity_and_header_foreman.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "An aggregated content hash covering two or more distinct Helper #2 foremen changes when any one of them changes, not only the first-sorted one"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2FilenameParsingAndAggregatedHash::test_two_foreman_helper2_bucket_hash_changes_when_second_foreman_changes"
        status: pass
    human_judgment: false
  - id: D6
    description: "A reduced-sub Helper #2 group's upload task list includes both the target sheet and the subcontractor PPP sheet; an AEP-billable or plain Helper #2 group routes to the target sheet only; a missing PPP target row degrades gracefully with no new failure mode"
    requirement: "HLP-02"
    verification:
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2UploadRouting::test_reduced_sub_helper2_routes_to_both_sheets"
        status: pass
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2UploadRouting::test_aep_billable_helper2_routes_to_target_only"
        status: pass
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestHelper2UploadRouting::test_reduced_sub_helper2_without_ppp_target_row_skips_second_leg"
        status: pass
    human_judgment: false
  - id: D7
    description: "Every independent helper-family enumeration this phase's research found (excel.py, change_detection.py, cleanup.py, orchestrate.py, publish_artifacts_to_supabase.py, upload.py, grouping.py) is pinned by a test that fails if the next variant misses one"
    requirement: "HLP-05"
    verification:
      - kind: unit
        ref: "tests/test_helper2_family_parity.py"
        status: pass
    human_judgment: false
  - id: D8
    description: "No Helper #1 shadow behavior, key, filename, or hash changed; no widened Helper #1 tuple; no pricing or AEP-billable-cutoff change; HELPER2_ENABLED-unset legacy byte-identity fixture still passes"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py (15 passed, 26 subtests)"
        status: pass
      - kind: unit
        ref: "tests/ full suite (2196 passed, 1 skipped, 541 subtests)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh (ALL 6 GATES PASSED)"
        status: pass
    human_judgment: false

# Metrics
duration: ~40min
completed: 2026-09-06
status: complete
---

# Phase 14 Plan 06: Subcontractor Helper #2 Shadow Variants Summary

**Subcontractor Helper #2 completions now produce reduced_sub_helper2 / aep_billable_helper2 shadow files that route, render, and hash exactly like their Helper #1 siblings — no duplicate billing, no header defect, no sort-order hash blind spot.**

## Performance

- **Duration:** ~40 min
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `pipeline/grouping.py`: added `_sub_is_valid_helper2_row` and the Helper #2 shadow leg (`reduced_sub_helper2` / `aep_billable_helper2` keys), gated the primary reduced_sub/aep_billable emission to also exclude a Helper #2-completed subcontractor row, and preserved VAC-crew precedence
- `pipeline/excel.py`: added the two shadow filename branches (with the D-14-05 defensive raise on empty `__helper2_foreman`) and the header-dispatch branch showing the attributed claimer with Helper #2 dept/job — the same asymmetry the Helper #1 shadow variants deliberately carry
- `pipeline/change_detection.py`: nested Helper #2 checks ahead of the Helper #1 checks inside the AEPBillable/ReducedSub filename branches, and added Helper #2 sub-bucketing to the aggregated content hash so a multi-foreman bucket can no longer hide a change behind row sort order
- `pipeline/upload.py`: added `reduced_sub_helper2` to the PPP second-leg routing tuple so a subcontractor Helper #2 shadow file reaches the subcontractor PPP sheet
- Extended `tests/test_helper2_family_parity.py`'s pinned table to cover every file this phase's research identified (upload.py, grouping.py joined excel.py, change_detection.py, cleanup.py, orchestrate.py, publish_artifacts_to_supabase.py), clearing the excel.py `KNOWN_DEFERRED` entries plan 14-01 left for this plan to close

## Task Commits

Each task was committed atomically:

1. **Task 1: The subcontractor Helper #2 shadow partition in grouping** - `b320e6b` (feat)
2. **Task 2: Shadow workbook rendering, nested filename parsing, and multi-foreman aggregated hashing** - `321d503` (feat)
3. **Task 3: The PPP dual-route gate and the extended family-parity invariant** - `fbaf085` (feat, includes a Rule 1 mypy-annotation fix in `pipeline/grouping.py`)

_No plan-metadata commit yet — SUMMARY/STATE/ROADMAP/REQUIREMENTS docs commit follows this file._

## Files Created/Modified

- `pipeline/grouping.py` — `_sub_is_valid_helper2_row`, the primary-leg exclusion, and the reduced_sub_helper2/aep_billable_helper2 shadow emission block
- `pipeline/excel.py` — `_AEPBillable_Helper2_<name>` / `_ReducedSub_Helper2_<name>` filename branches and their header-dispatch counterpart
- `pipeline/change_detection.py` — nested Helper2 filename-parse checks and the `helper2` aggregated-hash sub-bucket
- `pipeline/upload.py` — `reduced_sub_helper2` in the second-leg PPP routing tuple
- `tests/test_subcontractor_helper_shadow_rescue.py` — new test classes: `TestSubcontractorHelper2ShadowRescue`, `TestHelper2ShadowExcelRendering`, `TestHelper2FilenameParsingAndAggregatedHash`, `TestHelper2UploadRouting`, plus a grep-guard test in `TestProductionCodeSiteInvariants`
- `tests/test_helper2_family_parity.py` — `PARITY_TABLE` extended with `pipeline/upload.py` and `pipeline/grouping.py`; `KNOWN_DEFERRED` emptied

## Decisions Made

- The primary subcontractor-variant gate now excludes Helper #2-completed rows in the same way it already excludes Helper #1-completed rows (`_sub_is_valid_helper_row` and `_sub_is_valid_helper2_row` both checked before emitting the primary `_USER_` key).
- The both-slots-valid case is deliberately left unresolved: a row with both a valid Helper #1 and a valid Helper #2 completion emits both families' shadow keys today (additive, not a chosen winner). This is proven by `test_both_helper_slots_valid_takes_no_position` and documented as O-14-A, owner-blocked, owned by plan 14-08.
- Aggregated-hash sub-bucketing for `helper2` is scoped to the plain variant only, matching the pre-existing Helper #1 scope; the shadow variants fall to the generic hashing branch (a documented pre-existing gap per 14-RESEARCH.md, not introduced here).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed a local type annotation that regressed the mypy Gate 4 baseline**
- **Found during:** Task 3 (running `bash scripts/run_6_gates.sh` as part of overall plan verification)
- **Issue:** The new `_attribution_reason2: str | None = None` declaration in `pipeline/grouping.py`'s Helper #2 shadow block is a PEP 526 annotated assignment inside the (already-untyped) `group_source_rows` function. mypy emits an informational "annotation-unchecked" note for every such annotation inside an unchecked function body, so the new line added a note that was not in the pinned baseline, moving the count from 71 to 72 and failing Gate 4's strict delta check — even though there is no real type error.
- **Fix:** Changed the declaration to a bare (unannotated) assignment (`_attribution_reason2 = None`), matching the sibling Helper #1 variable's scope, and added a comment explaining why the annotation was dropped.
- **Files modified:** `pipeline/grouping.py`
- **Verification:** `bash scripts/check_mypy_delta.sh` reports "PASS: mypy delta neutral or improved (71 -> 71)"; full `bash scripts/run_6_gates.sh` reports ALL 6 GATES PASSED.
- **Committed in:** `fbaf085` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug fix, mypy hygiene, zero behavior change)
**Impact on plan:** No scope creep; the fix touches only the annotation style of a single new variable, not any billing-visible behavior.

## Issues Encountered

An early version of the aggregated-hash regression test (`test_two_foreman_helper2_bucket_hash_changes_when_second_foreman_changes`) had a copy-paste bug in its own `_row(foreman, price)` fixture helper — the `price` parameter was accepted but the dict literal hardcoded `'Units Total Price': '$100.00'` instead of using it, so both the baseline and "changed" fixtures always hashed identically regardless of the production code. Traced by comparing a standalone debug script (which used the SAME helper shape but happened to pass the literal correctly at the call site in one variant) against the actual test file, diffing the two, and finding the hardcoded literal. Fixed by wiring the parameter through; the corrected test then failed against a version of the code without the sub-bucketing fix and passed with it, confirming the test actually exercises the production branch (not a self-fulfilling mirror).

## User Setup Required

None — no external service configuration required. No live upload was performed and no Smartsheet attachment was created; all evidence in this SUMMARY is FIXTURE PASS from the local test suite.

## Next Phase Readiness

- The Helper #2 shadow-variant family (`helper2`, `aep_billable_helper2`, `reduced_sub_helper2`) is now fully wired through grouping, Excel rendering, filename parsing, aggregated hashing, and upload routing — matching the Helper #1 family site-for-site.
- Remaining Phase 14 work: plan 14-08 (O-14-A both-slots-valid business decision, owner-blocked), plan 14-09 (the `billing_audit.freeze_attribution` / `lookup_attribution` Supabase RPC migration adding `p_helper2` support, PROTECTED / `checkpoint:decision`), and plan 14-10 (the fixture-only pilot per the 2026-09-06 read-only Smartsheet probe finding Resource Analyst Foreman Helper #2 blank on all 576 rows).
- No blockers introduced by this plan; `HELPER2_ENABLED` stays default OFF (`'0'`) in production, so none of this plan's new code paths are reachable in production until a future plan flips the flag.

## Self-Check: PASSED

All 6 modified files confirmed present on disk; all 3 task commits
(`b320e6b`, `321d503`, `fbaf085`) confirmed present in `git log`.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-06*
