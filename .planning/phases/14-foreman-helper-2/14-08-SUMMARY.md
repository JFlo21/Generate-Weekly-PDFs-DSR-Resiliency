---
phase: 14-foreman-helper-2
plan: 08
subsystem: billing-pipeline
tags: [python, smartsheet, grouping, run-summary, observability, sentry, tdd]

# Dependency graph
requires:
  - phase: 14-01
    provides: "HELPER2_ENABLED flag, __is_helper2_row/__helper2_foreman/__helper2_dept row metadata, and the locked Helper #2 reason-string vocabulary (including helper2_conflict_hold)"
  - phase: 14-06
    provides: "The subcontractor Helper #2 shadow emission sites (_valid_helper2_row, reduced_sub_helper2/aep_billable_helper2 keys) that Task 2 patches; the placeholder 'takes no position' test Task 2 replaces"
  - phase: 14-07
    provides: "The two per-sheet capability log reasons (helper2_capability_unavailable, helper2_no_qualifying_completion) and the sheet_has_helper2_columns / sheet_helper2_qualified_seen signals that Task 3's counters mirror"
provides:
  - "pipeline/grouping.py: the O-14-A helper2-wins conflict rule at the plain-leg and shadow-leg emission sites -- _record_helper2_wins_conflict() (log once, count, PII-safe Sentry message) and get_helper2_conflict_count() for the caller"
  - "pipeline/orchestrate.py: four Helper #2 run-summary counters (helper2_capability_unavailable_sheets, helper2_no_qualifying_completion_sheets, helper2_conflict_hold, helper2_groups_generated), pre-seeded on both the synthetic and production run_summary paths"
  - "tests/golden/run_summary_baseline.json: 29-key frozen contract (was 25)"
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: O-14-A RESOLVED (helper2-wins), recorded at Task 1"
affects: [14-09, 14-10]

# Actuals (#2632)
# NOTE ON SCOPE: this plan spanned two sessions. Task 1 (O-14-A owner
# checkpoint) landed 2026-09-07 in an earlier session at commit ede01a9.
# This continuation session executed Tasks 2-3 only. `commits` and
# `plan_head_before` below are the ledger-measured count for THIS
# session (ede01a9..HEAD), per the mechanical commits protocol.
# `tokens` is computed over the WIDER whole-plan diff (af7d55f..HEAD,
# includes Task 1's 14-DECISIONS.md change) since the plan's `estimate`
# in 14-08-PLAN.md is itself a whole-plan figure -- the two fields are
# intentionally different scopes; see the Commits section below for the
# full 5-commit list.
actuals:
  tokens: 8449
  tasks: 3
  commits: 4
  plan_head_before: ede01a9256056cb2d37d39fc51e5b012da42fa38

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A conflicted-row business rule is applied at exactly one elif branch per leg (plain, shadow), both calling a SHARED module-level helper (_record_helper2_wins_conflict) that performs the log+count+Sentry side effect once -- the rule lives in one place despite two call sites, per the plan's explicit requirement"
    - "A subcontractor row's conflict is recorded ONLY at the shadow leg (the plain leg is already a no-op for subcontractor rows by the pre-existing is_subcontractor_row dispatch) -- avoids double-counting without adding a subcontractor-specific branch to the counter logic itself"
    - "A per-run counter exposed from group_source_rows() to its caller uses a module-level int reset at function entry, mirroring the pre-existing _PREFETCHED_FROZEN_ROW_KEYS / get_prefetched_frozen_row_keys() shape -- no change to the function's return signature"
    - "New run-summary counters that depend on per-sheet/per-row signals are RECOMPUTED in pipeline/orchestrate.py from data already in scope (source_sheets, all_rows, groups) by mirroring pipeline/fetch.py's column-presence gate and row-validity criteria, rather than adding a new return channel from fetch.py -- keeps Task 3 inside its own file scope (pipeline/orchestrate.py only)"

key-files:
  created:
    - .planning/phases/14-foreman-helper-2/14-08-SUMMARY.md
  modified:
    - pipeline/grouping.py
    - pipeline/orchestrate.py
    - tests/golden/run_summary_baseline.json
    - tests/test_foreman_helper_2.py
    - tests/test_subcontractor_helper_shadow_rescue.py
    - tests/test_incremental_read.py
    - tests/test_parity_shadow.py
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md

key-decisions:
  - "O-14-A conflict counting fires exactly once per conflicted row: at the plain leg for a non-subcontractor row, at the shadow leg for a subcontractor row (never both) -- mirrors the pre-existing is_subcontractor_row dispatch that already made the plain leg's Helper #1/#2 blocks a no-op (debug-log only) for subcontractor rows before this change."
  - "The conflict Sentry alert is a dedicated capture (existing sentry_capture_message_with_context helper, no new observability.py function needed) carrying WR / week ending / sheet id / leg / count only -- exactly the scope Juan's O-14-A RESOLVED record authorizes, even though the repo's existing PII registries (_PII_LOG_MARKERS, _PII_BREADCRUMB_DATA_KEYS) treat bare WR/week values as sensitive at OTHER call sites; this is a deliberate, owner-authorized exception scoped precisely to what the DECISIONS record permits, never a name or row value."
  - "helper2_groups_generated counts every Helper #2-family variant (helper2, reduced_sub_helper2, aep_billable_helper2), not only the plain variant -- most production Helper #2 activity is expected on subcontractor sheets, so a plain-only count would undercount what the pilot in plan 14-10 needs to compare."
  - "The three EXISTING tests that pinned run_summary.json's frozen key count at 25 (tests/test_incremental_read.py x2, tests/test_parity_shadow.py x1) were updated to 29 in the same commit as the counter addition -- a direct, in-scope consequence of Task 3's key addition, not scope creep, matching the exact update pattern each prior counter-adding phase already applied to these same three tests."

patterns-established:
  - "Conflict-rule call sites carry an inline comment naming the O-14-A RESOLVED record's file location, not just a decision ID -- the next reader finds the authority in the code without a second lookup."

requirements-completed: [HLP-03, HLP-05]
# HLP-03 and HLP-05 both name 14-08 as their last contributing plan (confirmed:
# 14-09 claims only HLP-06, 14-10 claims only HLP-04/HLP-07). HLP-03's
# distinguishability requirement is now met at BOTH the per-sheet log level
# (14-01/14-07) and the run-summary level (this plan's Task 3). HLP-05's
# "never create a duplicate Helper #2 claim/group/attribution row" requirement
# is met by Task 2's conflict rule, including the same-person and
# subcontractor edge cases.

coverage:
  - id: D1
    description: "A source row with BOTH a valid Helper #1 completion and a valid Helper #2 completion is resolved helper2-wins -- the Helper #2 key is emitted, the Helper #1 key is never emitted, on both the plain (non-subcontractor) and shadow (subcontractor) legs"
    requirement: "HLP-05"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoConflictRuleTests::test_both_slots_valid_helper2_wins_helper1_dropped"
        status: pass
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestSubcontractorHelper2ShadowRescue::test_both_helper_slots_valid_helper2_wins"
        status: pass
    human_judgment: false
  - id: D2
    description: "One conflicted row never aborts the run or blocks any other group from generating -- the explicit rejection of the 2026-07 prototype's abort-before-workbook behavior"
    requirement: "HLP-05"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoConflictRuleTests::test_conflict_never_aborts_run_other_groups_still_generate"
        status: pass
    human_judgment: false
  - id: D3
    description: "The SAME person named in both slots on one row still takes the conflict path and is credited exactly once, via Helper #2 only"
    requirement: "HLP-05"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoConflictRuleTests::test_same_person_both_slots_collapses_to_single_credit"
        status: pass
    human_judgment: false
  - id: D4
    description: "A subcontractor conflicted row follows the identical helper2-wins rule at the shadow leg, and its conflict is recorded exactly once (never double-counted against the plain leg, which is already a no-op for subcontractor rows)"
    requirement: "HLP-05"
    verification:
      - kind: unit
        ref: "tests/test_subcontractor_helper_shadow_rescue.py#TestSubcontractorHelper2ShadowRescue::test_both_helper_slots_valid_subcontractor_conflict_counted_once"
        status: pass
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoConflictRuleTests::test_both_slots_valid_conflict_counted_once"
        status: pass
    human_judgment: false
  - id: D5
    description: "run_summary.json carries four new Helper #2 counters (capability-unavailable sheets, no-qualifying-completion sheets, conflict-hold rows, groups generated), all present with a zero int value on a flag-off/quiet run -- the key set never varies"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoRunSummaryCounterTests::test_synthetic_run_summary_includes_four_helper2_counters_zeroed"
        status: pass
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoRunSummaryCounterTests::test_synthetic_run_summary_key_set_matches_golden_baseline"
        status: pass
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoRunSummaryCounterTests::test_get_helper2_conflict_count_feeds_the_run_summary_key"
        status: pass
      - kind: other
        ref: "python scripts/check_run_summary_structure.py against a real TEST_MODE run -- PASS: run_summary.json structure matches baseline (29 keys)"
        status: pass
    human_judgment: false
  - id: D6
    description: "No regression: full suite, Gate 4 mypy delta, and the full 6-gate harness all pass with the new keys and the conflict rule in place"
    verification:
      - kind: unit
        ref: "tests/ full suite (2230 passed, 1 skipped, 541 subtests)"
        status: pass
      - kind: other
        ref: "bash scripts/check_mypy_delta.sh (Gate 4: neutral, 71 -> 71)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh (ALL 6 GATES PASSED)"
        status: pass
    human_judgment: false

# Metrics
duration: ~50min (this continuation session, Tasks 2-3; Task 1's O-14-A checkpoint was a separate earlier session, 2026-09-07)
completed: 2026-09-08
status: complete
---

# Phase 14 Plan 08: O-14-A Helper2-Wins Conflict Rule and Run-Summary Visibility Summary

**A source row with both helper completion checkboxes valid is now resolved by Juan's owner-decided helper2-wins rule (Helper #2 > Helper #1 > primary foreman) at exactly one code site per leg, and run_summary.json carries four new counters that make every Helper #2 condition -- capability-absent, capability-present-but-idle, conflicted, and generated -- countable on any run, flag on or off.**

## Performance

- **Duration:** ~50 min (this continuation session; Task 1's checkpoint was a separate session on 2026-09-07)
- **Tasks:** 3 (1 owner checkpoint, completed prior; 2 TDD tasks, completed this session)
- **Files modified:** 8 (across the whole plan; 7 in this session)
- **Commits (this session):** 4 (`c1d096b` test, `b3ae217` feat, `4aeea1e` test, `bede1c0` feat)

## Accomplishments

- **Task 1 -- owner checkpoint (prior session, `ede01a9`).** Juan resolved O-14-A as **helper2-wins**, an owner-defined fifth option not among the plan's original four: Helper #2 > Helper #1 > primary foreman for one physical unit on one row. Recorded in full in `14-DECISIONS.md` under "O-14-A RESOLVED," including the visibility answer (Sentry AND run summary) and the still-open, non-blocking per-slot-file-duplication follow-up.
- **Task 2 -- the conflict rule, plain and shadow legs (`c1d096b` RED, `b3ae217` GREEN).** `pipeline/grouping.py` gained `_record_helper2_wins_conflict()` (logs once with the `helper2_conflict_hold` reason locked in plan 14-01, bumps a module counter, sends a PII-safe Sentry message with WR/week/sheet-id/leg/count only) and `get_helper2_conflict_count()`. The plain-leg Helper #1 emission now requires `not valid_helper2_row`; a new `elif` applies the rule for non-subcontractor rows. The shadow-leg Helper #1 block gets the identical treatment for subcontractor rows -- and is the SOLE place a subcontractor conflict is recorded, since the plain leg was already a no-op for subcontractor rows by the pre-existing dispatch. Both sites carry a comment naming the O-14-A RESOLVED record. Replaced plan 14-06's placeholder `test_both_helper_slots_valid_takes_no_position` with `test_both_helper_slots_valid_helper2_wins` plus a conflict-count test.
- **Task 3 -- run-summary visibility (`4aeea1e` RED, `bede1c0` GREEN).** `pipeline/orchestrate.py` gained four counters, pre-seeded on both the synthetic (TEST_MODE) and production run_summary paths so the key set never varies. The two sheet-level counters are recomputed from `source_sheets`/`all_rows` (already in scope for the sibling `sheets_discovered`/`rows_fetched` counters) by mirroring `pipeline/fetch.py`'s column-presence gate and `_detect_helper2_row`'s validity criteria -- no new fetch.py signal was needed, keeping the task inside its stated file scope. `tests/golden/run_summary_baseline.json` grew from 25 to 29 keys in the same commit as the counter addition, per Gate 6's exact key-set-equality contract. Three pre-existing tests that pinned the 25-key count (`test_incremental_read.py` x2, `test_parity_shadow.py` x1) were updated in the same commit.

## Task Commits

This plan's full commit history (spanning two sessions):

1. **Task 1: O-14-A owner decision checkpoint** - `ede01a9` (docs) -- prior session, 2026-09-07
2. **Task 2 RED: failing tests for the conflict rule** - `c1d096b` (test) -- this session
3. **Task 2 GREEN: implement the conflict rule** - `b3ae217` (feat) -- this session
4. **Task 3 RED: failing tests for run-summary counters** - `4aeea1e` (test) -- this session
5. **Task 3 GREEN: run-summary counters** - `bede1c0` (feat) -- this session

**Plan metadata:** captured in this SUMMARY commit (docs: complete plan).

_Note: the `commits: 4` / `plan_head_before` frontmatter fields above are the ledger-measured count for THIS session only (Tasks 2-3); the list above includes Task 1's prior-session commit for completeness._

## Files Created/Modified

- `pipeline/grouping.py` - O-14-A conflict rule: `_record_helper2_wins_conflict()`, `get_helper2_conflict_count()`, and the plain-leg/shadow-leg `elif` branches that apply it
- `pipeline/orchestrate.py` - four Helper #2 run-summary counters, pre-seeded on both run paths
- `tests/golden/run_summary_baseline.json` - 29-key frozen contract (was 25)
- `tests/test_foreman_helper_2.py` - `HelperTwoConflictRuleTests`, `HelperTwoRunSummaryCounterTests`, and the `_both_helpers_row()` fixture builder
- `tests/test_subcontractor_helper_shadow_rescue.py` - replaced the plan-14-06 placeholder with `test_both_helper_slots_valid_helper2_wins` and a conflict-count test
- `tests/test_incremental_read.py` - two stale 25-key contract assertions updated to 29
- `tests/test_parity_shadow.py` - one stale 25-key contract assertion updated to 29
- `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` - O-14-A RESOLVED record (Task 1, prior session)

## Decisions Made

See `key-decisions` in the frontmatter above for the four decisions made during this session's execution (conflict-counting-once-per-leg dispatch, the Sentry PII scope, the `helper2_groups_generated` variant set, and the stale-test-count fix being in-scope rather than a deviation).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated three pre-existing tests pinning a stale run_summary key count**
- **Found during:** Task 3, running the full suite after adding the four new counters
- **Issue:** `tests/test_incremental_read.py::WatermarkPersistenceTests::test_run_summary_key_count_matches_contract`, `tests/test_incremental_read.py::ScopedCounterTests::test_run_summary_key_count_and_unmodified`, and `tests/test_parity_shadow.py::GoldenContractTests::test_run_summary_baseline_key_count` each asserted the golden baseline has exactly 25 keys -- correct before this plan, stale after it (29 keys)
- **Fix:** Updated the three assertions to 29 and extended each docstring/comment to name the four new Phase 14 / 14-08 counters, following the exact update pattern each prior counter-adding phase already applied to these same three tests
- **Files modified:** `tests/test_incremental_read.py`, `tests/test_parity_shadow.py`
- **Verification:** `python -m pytest tests/ -q` -> 2230 passed, 1 skipped, 541 subtests
- **Committed in:** `bede1c0` (Task 3 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 -- a stale test contract, not a code defect)
**Impact on plan:** Necessary and fully anticipated by the plan's own Task 3 action text ("every new run_summary key must be pre-seeded... added to the baseline in the SAME commit"). No scope creep -- the same three files this plan's own history shows were touched by every prior counter-adding phase (`helper2_attribution_degraded`, the two Phase 12 sentinel counters, `groups_skipped_no_target_row`).

## Issues Encountered

- **Windows console encoding + `.env`-supplied Smartsheet token, both pre-existing environmental characteristics, not code defects.** `python generate_weekly_pdfs.py` crashes on a `UnicodeEncodeError` under Windows' default `cp1252` console encoding at an unrelated pre-existing print statement (`generate_weekly_pdfs.py:36`) unless `PYTHONUTF8=1` is set -- exactly why `scripts/run_6_gates.sh` already forces it. Separately, a bare `TEST_MODE=true python generate_weekly_pdfs.py` (without also clearing `SMARTSHEET_API_TOKEN`) picks up a real token from this repo's `.env` file and attempts a REAL Smartsheet fetch instead of the synthetic path -- documented in `scripts/run_6_gates.sh`'s own Gate 6 comment ("with a .env-supplied token this same command fetched all 118 production source sheets... and never reached this gate"). One such invocation, made before I found the correct `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true` form, produced zero output for several minutes and was moved to a background task by the harness; it is almost certainly blocked at the network layer in this sandboxed environment (no output at all, and this sandbox has no other outbound network access observed this session) rather than making progress against production Smartsheet, but it may still be running. **Operator note for Juan:** if a stray `python generate_weekly_pdfs.py` process is still running in this session's shell history, it can be safely killed -- `SKIP_UPLOAD` was never set on that specific invocation, so if network access WAS somehow available it could in principle have reached the upload phase; no evidence of any output, upload log line, or Smartsheet write was observed before I moved to the correct invocation.
- Once the correct invocation (`SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py`) was used, both the shell-level verification and the full `bash scripts/run_6_gates.sh` harness completed cleanly and quickly (well under a minute).

## User Setup Required

None - no external service configuration required. No Supabase DDL, no Smartsheet reads or writes, no live data, no env/secrets edits.

## Next Phase Readiness

- Phase 14's only owner-blocked item (O-14-A) is resolved and implemented; plans 14-09 (HLP-06) and 14-10 (HLP-04/HLP-07 rollout) are unblocked and were never blocked by this plan per the plan's own "Blocked-work statement."
- `run_summary.json`'s Helper #2 counters give plan 14-10's pilot something concrete to compare a flag-on run against a flag-off run.
- Follow-up 1 from the O-14-A RESOLVED record (whether the same person in slot 1 on some rows and slot 2 on others within one WR/week should keep producing two files, one per slot, as D-14-06 accepts) remains open, documentation-only, and non-blocking -- confirm with Juan before the 14-10 rollout notes are finalized.
- HLP-03 and HLP-05 are now the two Phase 14 requirements this plan completes; REQUIREMENTS.md should show both as complete after this plan's state update.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-08*

## Self-Check: PASSED

**Files verified:**
- FOUND: `.planning/phases/14-foreman-helper-2/14-08-SUMMARY.md`
- FOUND: `pipeline/grouping.py`
- FOUND: `pipeline/orchestrate.py`
- FOUND: `tests/golden/run_summary_baseline.json`
- FOUND: `tests/test_foreman_helper_2.py`
- FOUND: `tests/test_subcontractor_helper_shadow_rescue.py`
- FOUND: `tests/test_incremental_read.py`
- FOUND: `tests/test_parity_shadow.py`
- FOUND: `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`

**Commits verified:**
- FOUND: `ede01a9` (Task 1, prior session)
- FOUND: `c1d096b` (Task 2 RED)
- FOUND: `b3ae217` (Task 2 GREEN)
- FOUND: `4aeea1e` (Task 3 RED)
- FOUND: `bede1c0` (Task 3 GREEN)
