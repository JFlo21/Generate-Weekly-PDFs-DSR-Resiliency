---
phase: 14-foreman-helper-2
plan: 13
subsystem: run-memory
tags: [python, run-memory, discovery, sheet-registry, gap-closure, tdd]

# Dependency graph
requires:
  - phase: 14-07
    provides: "MAPPING_SCHEMA_MARKER ('helper2-v1'), the sixth skip-index admission condition in pipeline/discovery.py, and upsert_sheet_registry(mapping_schema_by_sheet=) in pipeline_memory/writer.py -- the writer half of the marker contract"
  - phase: 14-12
    provides: "sheet_registry.mapping_schema column live in production (migration 20260909022129) and HELPER2_ENABLED=1 on the scheduled workflow"
provides:
  - "pipeline/discovery.py: _set_last_discovery_skip_sids / get_last_discovery_skip_sids -- the skip-admitted sheet ids of the last discover_source_sheets call, reset per call (mirrors fetch.get_last_sheet_versions)"
  - "pipeline/orchestrate.py: _compute_registry_marker_sheets(registry_sheets, skip_sids, column_mapping_sheets) -- marker = fully validated this run AND column_mapping written this call; passed as mapping_schema_by_sheet at BOTH upsert_sheet_registry call sites"
  - "tests/test_mapping_schema_marker_caller.py: 8 tests -- getter defensive copy, discovery source pin, 4 pure-helper cases, orchestrate source pin (both call sites), writer-payload proof"
provides_records:
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: O-14-E recorded (root cause, fix, close condition)"
  - ".lattice/learnings.md: 'test the caller, not only the callee, for opt-in kwargs'"
affects: [14-14]

# Actuals
# NOTE ON SCOPE: executed ad hoc in the owner's session (not by gsd-executor),
# so no plan-head sentinel exists. `commits` counts the squash-merge on master
# (PR #395 -> d079e81); the branch carried the RED/GREEN pair, two Greptile
# rounds (element-typed annotations) and a rebase onto the #394 docs merge.
actuals:
  tokens: 14000
  tasks: 2  # Task 1 executed; Task 2 (verify on the next deep run) superseded by plan 14-14
  commits: 1
  plan_head_before: 7ded60c

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A module-level 'last call' getter (get_last_discovery_skip_sids) next to the function that computes it, reset at the top of every call, is the repo's established way to hand per-run discovery facts to the orchestrator without widening return types."
    - "A cache-admission marker is stamped only for ids whose certified data is written in the SAME writer call (marker subset of column_mapping_sheets); an echoed stored value is never certified."

key-files:
  created:
    - tests/test_mapping_schema_marker_caller.py
    - .planning/phases/14-foreman-helper-2/14-13-PLAN.md
  modified:
    - pipeline/discovery.py
    - pipeline/orchestrate.py
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md
    - .lattice/learnings.md

key-decisions:
  - "O-14-E root cause (2026-09-09): plan 14-07 shipped the writer kwarg and the read-side admission condition but no production call site ever passed mapping_schema_by_sheet, so mapping_schema stayed NULL on all 121 rows and the registry skip was defeated (121 full validations, ~38 s per run, no billing impact). Fixed by wiring the caller (Juan: 'yes lets write up the fix')."
  - "Marker semantics: fully validated this run AND mapping written this call. On the 14-13 code alone the 121 existing sheets would earn the marker only on the next weekly_comprehensive run; plan 14-14 widened the frequent-run written set the same day."

patterns-established:
  - "Verification gate for any new opt-in writer kwarg: grep the production call sites for the kwarg name and pin them with inspect.getsource(orch.main)."

requirements-completed: [HLP-06]

coverage:
  - id: D1
    description: "(Task 1) Both sheet_registry upserts pass mapping_schema_by_sheet derived from the discovery skip index; the marker reaches the writer payload only for fully validated sheets whose mapping is written."
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_mapping_schema_marker_caller.py -- RED (caller pin absent) then GREEN 8 passed; full suite 2304 passed / 1 skipped; bash scripts/run_6_gates.sh ALL 6 GATES PASSED"
        status: pass
      - kind: other
        ref: "First scheduled run on the merge, 34393726548 (cbff797): both registry upserts 200, 0 skipped / 121 validated as expected, counters 114/7, no tracebacks"
        status: pass
    human_judgment: false

# Metrics
duration: "~3h wall clock across TDD, two Greptile rounds, rebase onto 7ded60c, merge"
completed: 2026-09-09
status: complete
---

# Phase 14 Plan 13: O-14-E Fix -- the mapping_schema Marker Reaches sheet_registry Summary

**Wires the caller half of plan 14-07's marker contract: `orchestrate.main` now derives the per-sheet
`helper2-v1` marker from the discovery skip index and passes it on both registry upserts, so a fully
validated sheet whose mapping is written this call is certified for cache admission on later runs.**

## Performance

- **Duration:** ~3h (TDD + review rounds); executed ad hoc in the owner's session
- **Tasks:** 2 planned — Task 1 (TDD `auto`) executed; Task 2 (record; verify on the next deep run) superseded by plan 14-14, see Deviations
- **Files modified:** 2 production modules + 1 test file + plan/decision records
- **Commits:** 1 on master (squash-merge `d079e81`, PR #395)

## Accomplishments

- **Discovery publishes the skip-admitted ids.** `_discovery_skip_sids` is reset at the top of
  `discover_source_sheets` and published after the "Discovery validation split" log through
  `get_last_discovery_skip_sids()` (defensive copy).
- **Orchestrate derives and passes the marker.** `_compute_registry_marker_sheets` is pure: a sheet
  gets `MAPPING_SCHEMA_MARKER` only if it is not skip-admitted AND its id is in the written mapping
  set (or the set is `None` on the deep run). Both `upsert_sheet_registry` calls pass
  `mapping_schema_by_sheet=_registry_marker_sheets`.
- **Tests pin the wiring.** Eight tests including a source pin that counts the kwarg at both call sites
  and a writer-payload proof.

## Task Commits

1. **Task 1 RED/GREEN + review rounds** -- squash-merged as `d079e81` (PR #395, 2026-09-09 18:50Z)

## Files Created/Modified

- `pipeline/discovery.py` -- skip-sid state + getter, `Iterable` import.
- `pipeline/orchestrate.py` -- `_compute_registry_marker_sheets`, marker kwarg at both upserts.
- `tests/test_mapping_schema_marker_caller.py` -- 8 tests.
- `.planning/phases/14-foreman-helper-2/14-13-PLAN.md`, `14-DECISIONS.md`, `.lattice/learnings.md`.

## Decisions Made

See `key-decisions`: O-14-E root cause and the marker semantics.

## Deviations from Plan

### Superseded task

**1. Task 2 "record; verify on the next deep run" — superseded by plan 14-14 (same day)**
- **Planned:** observe the marker on all 121 rows after the Monday 2026-09-14 `weekly_comprehensive` run,
  then close O-14-E.
- **What happened:** Juan could not wait for the deep run ("the 121 sheets do run and I cannot wait for
  that deep run"). Plan 14-14 was inserted the same afternoon so a frequent run adopts the freshly
  validated mapping (+ marker); the observation was performed as 14-14 Task 2 on runs `34411958861`
  (121/121 marked) and `34415980363` (112/121 registry skips). This plan's Task 2 was therefore never
  executed as written; O-14-E is RESOLVED in `14-DECISIONS.md` under 14-14's record.

### Review-driven

Two Greptile rounds (bare `set`/`list` annotations -> element-typed; stale STATE.md
lines) and one rebase onto the #394 docs merge (changelog conflict kept both sides).

## Issues Encountered

The first run on this fix still fully validated all 121 sheets by design (marker earned only on a
deep run for existing sheets). Juan could not wait for Monday's deep run, which produced plan 14-14.
