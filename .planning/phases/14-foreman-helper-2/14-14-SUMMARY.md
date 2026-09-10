---
phase: 14-foreman-helper-2
plan: 14
subsystem: run-memory
tags: [python, run-memory, discovery, sheet-registry, gap-closure, tdd, observability]

# Dependency graph
requires:
  - phase: 14-13
    provides: "_compute_registry_marker_sheets (marker = fully validated AND mapping written this call) and get_last_discovery_skip_sids -- widening the written set is the whole change"
  - phase: 11-06
    provides: "D-03 column_mapping_sheets contract on upsert_sheet_registry and _log_column_mapping_drift (the deep-run drift log this plan reuses with a label)"
provides:
  - "pipeline/orchestrate.py: _compute_registry_mapping_sheets(..., fully_validated_sids=None) -- on a frequent run the written set is new sheets UNION sheets fully validated this run; _log_column_mapping_drift(..., label=) -- label prefix; main derives _registry_fully_validated_sids once and logs adoption in pass 1 BEFORE the first registry write"
  - "pipeline_memory/writer.py: upsert_sheet_registry docstring records the widened frequent-run set -- NOT in 736141a: the branch commit bed436c was pushed after PR #396 had already merged at c04dc5b, so it landed as cherry-pick 607f5db in the closure PR #398"
  - "tests/test_frequent_run_mapping_adoption.py: 10 tests -- helper include/exclude/new-sheet/default/deep-run, drift label custom + default, source pin, ordering pin (frequent drift log index < first upsert index; fails on 9fad83c), writer-payload proof (fresh mapping + marker for a fully validated sheet, stored mapping + no marker for a skip-admitted one)"
provides_records:
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: O-14-E owner instruction, SQL-backfill rejection evidence, 14-14 record, RESOLVED block with the observed runs"
  - ".lattice/learnings.md: 'log before you persist'"
affects: []

# Actuals
# NOTE ON SCOPE: executed ad hoc in the owner's session (not by gsd-executor),
# so no plan-head sentinel exists. `commits` counts the squash-merge on master
# (PR #396 -> 736141a); the branch carried the RED/GREEN pair plus three bot
# review rounds (Copilot x3, Greptile x1); the docs-alignment follow-up
# landed separately as PR #397 -> 92c9ed6, and the writer.py docstring
# (bed436c, pushed after the merge) as cherry-pick 607f5db in PR #398.
actuals:
  tokens: 26000
  tasks: 2
  commits: 1
  plan_head_before: d079e81

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Observability before persistence: when a run adopts new state and an early-exit path exists between the first write and a later log, emit the drift log immediately before the first persistence call; an ordering pin on the orchestrator source (log index < first write index) locks it when a behavioral main() test is not feasible."
    - "A closing condition must be satisfiable by the documented capability split: marker on all rows, capability keys only on the sheets that physically carry them."

key-files:
  created:
    - tests/test_frequent_run_mapping_adoption.py
    - .planning/phases/14-foreman-helper-2/14-14-PLAN.md
  modified:
    - pipeline/orchestrate.py
    - pipeline_memory/writer.py
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md
    - .claude/project-state.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - docs/CHANGELOG_CONTEXT.md
    - memory-bank/living-ledger.md

key-decisions:
  - "Owner instruction (Juan, 2026-09-09): 'the 121 sheets do run and I cannot wait for that deep run so I need this to be cleared another way' -> code change chosen over a SQL marker backfill."
  - "SQL backfill REJECTED on evidence: 0 of 121 stored column_mapping values carried any Helper #2 key (last deep run 34086148733 ran 6696a46, pre-Helper-#2), so stamping helper2-v1 by SQL would have admitted every sheet from cache WITHOUT Helper #2 columns and silently disabled detection on the 114 capable sheets."
  - "Phase 11 D-03 kept in spirit: a frequent run adopts a mapping only for a sheet it fully validated this run, and the adoption is logged (label 'Frequent-run full-validation') before the first registry write; skip-admitted sheets still echo their stored mapping unmarked."
  - "O-14-E RESOLVED 2026-09-10 on the observed runs (see 14-DECISIONS.md): dispatch 34411958861 stamped all 121 rows (114 with Helper #2 keys, 7 capability-unavailable without); scheduled 34415980363 skipped 112 of 121 via sheet_registry."

patterns-established:
  - "Review-round hygiene on this repo: Copilot/Greptile findings are answered per thread with the fixing SHA; Codex bot comments are listed for the owner and never acted on (harness boundary)."

requirements-completed: [HLP-06]

coverage:
  - id: D1
    description: "A frequent run writes the freshly validated column_mapping (and the helper2-v1 marker) for every sheet it fully validated this run; skip-admitted sheets keep echoing unmarked; adoption is logged before the first registry write."
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_frequent_run_mapping_adoption.py -- RED then GREEN 10 passed (ordering pin verified RED against 9fad83c); full suite 2314 passed / 1 skipped; bash scripts/run_6_gates.sh ALL 6 GATES PASSED (mypy delta 71 -> 71); haiku-verifier PASS"
        status: pass
      - kind: other
        ref: "Task 2 observation -- dispatch run 34411958861 (JFlo21, head 97fe0c3 incl. 736141a, EXECUTION_TYPE manual, 22:23Z -> 23:23Z, success): split 121 / 0 skipped / 121 validated; 114 'Frequent-run full-validation column_mapping refresh' warnings all logged before the first sheet_registry POST; both POSTs carried mapping_schema and returned 200; counters 7 unavailable / 114 no-qualifying; 0 tracebacks; 6 files. Supabase 23:09Z: 121/121 marked, 114 with Helper #2 keys, 7 marked without keys = the capability-unavailable sheets (Arrowhead x4, Intake Promax, Intake Promax 8, Resiliency Promax Database Backup 2)."
        status: pass
      - kind: other
        ref: "Task 2 observation -- scheduled run 34415980363 (production_frequent, 23:23Z -> 00:12Z, success): split 121 candidates / 112 skipped via sheet_registry / 9 fully validated (version bumps); 0 refresh warnings; per pass one POST without mapping_schema (112 echoed) + one with (9 validated), all 200; counters 7/114; 0 tracebacks; 7 files. Supabase 00:21Z: still 121/114/7."
        status: pass
    human_judgment: false

# Metrics
duration: "~2h implementation + review rounds; ~2h production observation (two runs)"
completed: 2026-09-10
status: complete
---

# Phase 14 Plan 14: Frequent Runs Adopt the Validated Mapping -- O-14-E Cleared Without the Deep Run Summary

**A frequent run now writes the freshly validated `column_mapping` (and, through 14-13's marker helper,
the `helper2-v1` marker) for every sheet it fully validated this run, with the drift log fired before
the first registry write. The first run after the merge stamped all 121 sheets; the next scheduled run
skipped 112 of 121 via the registry. O-14-E is RESOLVED.**

## Performance

- **Duration:** ~2h implementation and three review rounds; ~2h observation across two production runs
- **Tasks:** 2 (1 TDD `auto`, 1 observation)
- **Files modified:** 2 production modules + 1 test file + records
- **Commits:** 1 on master (squash-merge `736141a`, PR #396); docs alignment PR #397 -> `92c9ed6`;
  writer docstring cherry-pick in PR #398

## Accomplishments

- **Task 1 -- adoption + drift log (TDD).** `_compute_registry_mapping_sheets` gains
  `fully_validated_sids`; `_log_column_mapping_drift` gains `label`; `main` derives the fully
  validated set once, logs adoption in pass 1 before the first upsert, and pass 2 keeps only the
  deep-run log. Ten tests including an ordering pin.
- **Task 2 -- observation.** Both halves of the closing condition observed the same night
  (details in `coverage.D1` above and in `14-DECISIONS.md` O-14-E RESOLVED).

## Task Commits

1. **Task 1 RED/GREEN + review rounds 1-3** -- squash-merged as `736141a` (PR #396, 2026-09-09 22:17Z)
2. **Docs alignment (ROADMAP checklist, STATE.md, CLAUDE.md, docs/ai, Lattice)** -- `92c9ed6` (PR #397)

## Files Created/Modified

- `pipeline/orchestrate.py` -- `fully_validated_sids` kwarg, `label` kwarg, pass-1 adoption log,
  docstrings for the widened written set.
- `pipeline_memory/writer.py` -- `upsert_sheet_registry` docstring (review round 3); not part of
  `736141a` (bed436c was pushed after the merge) -- landed via PR #398 cherry-pick `607f5db`.
- `tests/test_frequent_run_mapping_adoption.py` -- 10 tests.
- Records: `14-14-PLAN.md`, `14-DECISIONS.md`, `.claude/project-state.md`, `.planning/ROADMAP.md`,
  `.planning/STATE.md`, `docs/CHANGELOG_CONTEXT.md`, `memory-bank/living-ledger.md`,
  `.lattice/learnings.md`.

## Decisions Made

See `key-decisions`: owner instruction, SQL-backfill rejection, D-03 kept in spirit, O-14-E RESOLVED.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, review-driven] Drift log moved ahead of the pass-1 write (Copilot round 2)**
- **Found during:** PR #396 review on `9fad83c`
- **Issue:** pass 1 persisted the adopted mapping + marker before the pass-2 drift log, so an early
  no-data exit made adoption silent.
- **Fix:** frequent-run drift log moved into pass 1 before the first `upsert_sheet_registry`; ordering
  pin test added (round 3); marker/writer docstrings and the closing condition aligned.
- **Committed in:** `5ce3efc`, `c04dc5b` (branch, in squash `736141a`); `bed436c` (writer docstring)
  missed the merge and landed as `607f5db` in PR #398

**2. [Observation] Trigger substitution on Task 2 — first run was a manual dispatch, not a schedule**
- **Planned:** "the first scheduled run after merge" stamps the registry; "the following run" confirms
  the skips.
- **What happened:** Juan dispatched run `34411958861` (`workflow_dispatch`, `EXECUTION_TYPE=manual`) six
  minutes after the merge; the 23:00Z schedule `34415980363` queued behind it (workflow concurrency group)
  and became the confirming run.
- **Why it does not change the outcome:** both trigger types take the non-deep (frequent) path this plan
  changed — `_is_deep_run` is true only for the `weekly_comprehensive` cron — so the dispatch exercised
  exactly the adoption code and the schedule exercised exactly the registry-admitted path.

**Total deviations:** 2 (1 review-driven ordering fix, no change to which sheets are written; 1 trigger
substitution on the observation, same code path)
**Impact on plan:** None on scope; the plan text was updated to say "before the first registry write".

## Issues Encountered

None. The scheduled run's 9 full validations were sheets whose live version changed after the
dispatch run (normal churn), and their mappings were unchanged (0 refresh warnings).
