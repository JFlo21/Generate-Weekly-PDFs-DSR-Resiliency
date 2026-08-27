---
phase: 11-incremental-read-affected-group-regeneration
plan: 04
subsystem: pipeline
tags: [smartsheet, supabase, incremental-read, affected-group-regeneration, tdd]

# Dependency graph
requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "Plan 02's resolve_run_mode (the resolved 'incremental'/'full' string, carried in main() as _resolved_mode), pipeline.fetch.fetch_sheet_delta/compute_rows_modified_since, and pipeline_memory/reader.py's fail-open read-surface conventions"
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "Plan 03's D-06 preservation gates (keep_historical call-boundary override, hash-history prune gated on mode=='full') -- the destructive-maintenance blocks were already safe by construction before this plan first produces a scoped `groups` dict"
provides:
  - "pipeline_memory.reader.map_affected_to_sheets -- the affected (wr, week_ending) set -> sheet_id mapping query, bound-parameterised, chunked, all-or-nothing fail-open"
  - "pipeline.fetch.map_delta_sheet_rows -- delta-probed Sheet rows -> the minimal raw-mapped-column + provenance-key row shape pipeline_memory needs"
  - "pipeline.orchestrate._run_phase2_incremental -- the PHASE 2a/2b dispatcher: delta read -> unmodified _run_memory_write_phase -> affected-set mapping -> unmodified get_all_source_rows scoped re-fetch, never-raise/fail-to-full contract"
  - "pipeline.orchestrate._filter_groups_to_affected / _resolve_row_wr_week -- the post-grouping affected-pair restriction applied AFTER the unmodified group_source_rows() call"
  - "main() PHASE 2 restructured mode-aware: full mode byte-for-byte unchanged; incremental mode dispatches through _run_phase2_incremental and falls back to full on any failure"
  - "run_ledger.notes keys mem_phase2a_delta_rows / mem_phase2b_sheets_refetched at both run_ledger_finish call sites"
  - ".planning/REQUIREMENTS.md INC-02 D-05 approved-partial note"
affects: ["11-05 (shadow parity harness re-runs the same delta reads and can now compare against this plan's real scoped regeneration)", "11-06/11-07 (deletion/formula-change and streak-query plans build on row_state now being genuinely queried for scope, not just written)"]

# Actuals (#2632)
actuals:
  tokens: 17688
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Standalone, directly-testable pure/near-pure helpers for logic nested inside main() (_run_phase2_incremental, _filter_groups_to_affected, _resolve_row_wr_week) -- mirrors the established _run_memory_write_phase / resolve_run_mode / _build_registry_write_plan pattern from plans 01-02, so PHASE 2a/2b's deep-in-main() logic stays unit-testable without a full production session."
    - "Fail-to-full, never fail-narrow: every failure surface in the incremental branch (delta-probe escalation, an unexpected _run_memory_write_phase exception, an empty sheet mapping for a non-empty affected set, or any other unhandled exception) returns ok=False with a non-empty fallback_reason and the caller re-runs today's single full get_all_source_rows call over every sheet -- the regeneration scope can only widen, never narrow (T-11-18)."
    - "Minimal essential-fields row mapper as a strict acceptance-gate superset: map_delta_sheet_rows requires only Work Request # + Weekly Reference Logged Date (the same minimum group_source_rows itself requires), deliberately skipping the full business acceptance gate (Units Completed? / non-zero price / CU-no-match / helper-VAC derivation) that PHASE 2b's real grouping phase applies -- so PHASE 2a can only over-include relative to what would actually group, never under-include."
    - "Chunk-size discipline mirrored, not imported: pipeline_memory/reader.py defines its own _MAPPING_CHUNK_SIZE = 500 constant (matching pipeline_memory/writer.py's _CHUNK_ROWS) rather than importing it, keeping reader.py's import surface minimal."
  discovered_apis: []

key-files:
  created: []
  modified:
    - pipeline/orchestrate.py
    - pipeline/fetch.py
    - pipeline_memory/reader.py
    - tests/test_incremental_read.py
    - .planning/REQUIREMENTS.md

key-decisions:
  - "map_delta_sheet_rows uses str(row['Work Request #']).split('.')[0] (grouping.py's own WR-key derivation) rather than pipeline_memory.writer._sanitized_wr's regex-sanitized form, per the plan's explicit instruction to derive the affected-pair prefix using the SAME resolution group_source_rows uses. For real-world numeric WR values this is a no-op divergence; documented here as the literal-instruction-over-inferred-consistency call this plan made."
  - "_run_phase2_incremental hardens map_affected_to_sheets (chunking, bound parameterisation, all-or-nothing fail-open) in the SAME implementation pass as the base PHASE 2a/2b slice, rather than as a separate follow-up edit -- Task 1's own acceptance criteria (an empty mapping must mean \"cannot confirm\", not \"nothing to fetch\") already require the fail-open contract Task 2 additionally proves with chunk/injection/partial-failure tests. Task 2's commit is therefore test-coverage-only against already-complete source, mirroring 11-03's precedent of iteratively-verified work landing as a coherent commit rather than a strict pre-implementation RED/GREEN split."
  - "Trigger 3 (auth-error isolation) sheets are defensively SKIPPED entirely in PHASE 2a's per-sheet dispatch, even though resolve_run_mode's auth_error_sheet_ids parameter still has no live producer (11-02-SUMMARY: unchanged by this plan) -- the branch is dead code today but matches D-02's isolation semantics exactly if a future plan wires a live producer, and is unit-tested via a synthetic per_sheet_reasons dict so the dispatch logic itself is proven now."
  - "The 'no valid data rows found' / 'no valid groups created' raise guards are relaxed with `and not _incremental_empty_affected_run` rather than removed -- a genuinely empty affected set (nothing changed) is a successful zero-group incremental run; a full-mode run (or an incremental run that fell back to full) with zero rows/groups still raises exactly as it does today, because the sentinel is only ever set True inside the successful-incremental branch."
  - "_watermarks / _per_sheet_reasons are hoisted WITHOUT explicit type annotations (plain `= {}`) rather than annotated dict[...] locals -- an explicitly-annotated local inside main() (itself untyped/unchecked by default) triggers a gate-counted mypy [annotation-unchecked] note per variable; this is the identical Gate-4 regression class 11-02 already hit and fixed the same way (drop the unnecessary annotation, matching the unannotated sibling style) rather than suppressing a real finding."

requirements-completed: []

coverage:
  - id: D1
    description: "In incremental mode, PHASE 2a issues a per-sheet delta read (full read for trigger1/trigger2-flagged sheets, skip for trigger3-isolated sheets), hands the collected rows to the unmodified _run_memory_write_phase, maps the returned affected set to every sheet holding a row_state row for it, and PHASE 2b re-fetches only those sheets via the unmodified get_all_source_rows; full mode is byte-for-byte the pre-plan single-call path."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::IncrementalScopeTests (14 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The affected-pair restriction is applied to `groups` AFTER the unmodified group_source_rows() call -- a group either survives in full or is dropped entirely, never partially reconstructed; a moved week keeps both the new pair's group and the prior pair's group."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::IncrementalScopeTests::test_filter_groups_restricts_to_affected_pairs, test_moved_week_keeps_both_new_and_prior_pair_groups"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- pipeline/grouping.py pipeline/pricing.py pipeline/attribution.py pipeline/excel.py -> clean (D-04's central promise, mechanically verified)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every failure in the delta read, the memory write, or the affected-set mapping resolves the run to full mode with a non-empty fallback_reason -- the scope can only ever be too wide, never too narrow. An empty affected set (nothing changed) is distinguished from a failed mapping and is recorded as a successful zero-group incremental run."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::IncrementalScopeTests (escalation/exception/empty-mapping fallback tests), AffectedSetMappingTests (10 tests: bound parameterisation, chunking, mid-chunk failure, three distinguishable empty outcomes)"
        status: pass
    human_judgment: false
  - id: D4
    description: "run_ledger.sheets_changed on an incremental run reflects the delta-read changed-sheet count, not the PHASE 2b re-fetch count; the two scopes are reported as distinct notes-only counters at both run_ledger_finish call sites; run_summary.json's frozen 21-key contract and the D-05 REQUIREMENTS.md note are both in place."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::ScopedCounterTests (4 tests)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh -> ALL 6 GATES PASSED (pytest 1620 passed / 1 skipped / 141 subtests; mypy delta 65 -> 65; run_summary.json 21 keys; protected paths clean)"
        status: pass
    human_judgment: false

duration: ~28min
completed: 2026-08-26
status: complete
---

# Phase 11 Plan 04: Incremental Read PHASE 2a/2b + Affected-Group Regeneration Summary

**CONTEXT.md D-04 Option C shipped: `row_state` decides regeneration membership via a widened affected-sheet mapping, a scoped full re-fetch supplies content, and `group_source_rows`/`pricing.py`/`attribution.py`/`excel.py` are byte-for-byte unmodified -- the plan that actually makes the frequent run read less.**

## Performance

- **Duration:** ~28 min
- **Started:** 2026-08-26T19:21:15Z (session continuation from 11-03)
- **Completed:** 2026-08-26T19:49:31Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Shipped `pipeline_memory.reader.map_affected_to_sheets` -- the affected `(wr, week_ending)` set -> `sheet_id` mapping query, using the Supabase client's bound `.in_()` builder (never string interpolation), chunked at 500 distinct WR values, and all-or-nothing on any chunk failure (a partial mapping is discarded and treated as "cannot confirm").
- Shipped `pipeline.fetch.map_delta_sheet_rows` -- maps a delta-probed `Sheet`'s raw rows to the raw-mapped-column + provenance-key shape `pipeline_memory._run_memory_write_phase` needs, gated only on the same minimum (`Work Request #` + `Weekly Reference Logged Date`) `group_source_rows` itself requires -- a strict superset of the full business acceptance gate, so the affected set this feeds can only be too wide, never too narrow.
- Shipped `pipeline.orchestrate._run_phase2_incremental` -- the PHASE 2a delta-read -> unmodified `_run_memory_write_phase` -> affected-set mapping -> PHASE 2b unmodified `get_all_source_rows` scoped re-fetch dispatcher, with per-sheet trigger1 (full read)/trigger3 (isolated skip) handling and a never-raise, fail-to-full-mode contract on any unexpected failure.
- Shipped `_filter_groups_to_affected` / `_resolve_row_wr_week` -- the post-grouping affected-pair restriction, applied strictly AFTER the unmodified `group_source_rows()` call so a group either survives whole or is dropped entirely (no second grouping/Excel codepath).
- Restructured `main()`'s PHASE 2 block mode-aware: full mode is byte-for-byte the pre-plan single-call path; incremental mode dispatches through `_run_phase2_incremental` and falls straight through to the SAME full-mode block on any failure. Relaxed the "no valid data rows/groups" raise guards so a legitimately empty incremental run (nothing changed) is recorded as a successful zero-group run, not an error.
- Wired `mem_phase2a_delta_rows` / `mem_phase2b_sheets_refetched` as distinct `run_ledger.notes` counters at both `run_ledger_finish` call sites, so the delta-read scope is never conflated with the PHASE 2b re-fetch scope; recorded the D-05 approved partial against INC-02 in `.planning/REQUIREMENTS.md`.

## Task Commits

Each task was committed atomically:

1. **Task 1 + Task 2 (production code): PHASE 2a/2b dispatcher, affected-set mapping (hardened), delta-row mapper** - `ec44ff6` (feat)
2. **Task 1 + Task 2 + Task 3 (tests): IncrementalScopeTests, AffectedSetMappingTests, ScopedCounterTests** - `d01efeb` (test)
3. **Task 3 (docs): D-05 approved-partial note in REQUIREMENTS.md** - `b3bd36c` (docs)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

_Deviation from the plan's literal 3-commit-per-task shape: `map_affected_to_sheets`'s hardening (chunking, bound parameterisation, all-or-nothing fail-open) was written in the SAME implementation pass as its Task 1 baseline, because Task 1's own acceptance criteria already require the "empty return means cannot confirm" fail-open contract Task 2 additionally proves with chunk/injection/partial-failure tests. Rather than force an artificial mid-function revert/restore cycle to produce a separate Task-2-only source diff, commit `ec44ff6` carries the complete, final source for Tasks 1-3 (Task 3's `run_ledger_finish` notes-counters are also threaded through the same restructured PHASE 2 block), and commit `d01efeb` carries all three tasks' test coverage together. This mirrors 11-03's documented precedent for tightly-coupled, iteratively-verified work. Every task's acceptance criteria were independently re-verified against the final state before this SUMMARY was written._

## Files Created/Modified

- `pipeline/orchestrate.py` -- `_resolve_row_wr_week`, `_filter_groups_to_affected`, `_run_phase2_incremental` (new standalone functions); PHASE 2 restructured mode-aware; the group-filter call site added after `group_source_rows()`; the "no valid rows/groups" raise guards relaxed for the empty-incremental-run case; both `run_ledger_finish` call sites gain the two new notes-only counters; `SAFETY_WINDOW_MINUTES` added to the `pipeline.config` import block; `_watermarks`/`_per_sheet_reasons` hoisted with safe defaults.
- `pipeline/fetch.py` -- `map_delta_sheet_rows` (new), placed alongside `fetch_sheet_delta`.
- `pipeline_memory/reader.py` -- `map_affected_to_sheets` (new), `_MAPPING_CHUNK_SIZE` constant, `logging` import.
- `tests/test_incremental_read.py` -- `IncrementalScopeTests` (14), `AffectedSetMappingTests` (10), `ScopedCounterTests` (4) -- 28 new test methods, 89 total in the file.
- `.planning/REQUIREMENTS.md` -- D-05 approved-partial note appended directly beneath the INC-02 entry.

## Decisions Made

See `key-decisions` in frontmatter. The most consequential: the WR-key derivation for the group filter deliberately follows the plan's literal instruction (grouping.py's own `str(wr).split('.')[0]`) rather than `pipeline_memory.writer._sanitized_wr`'s regex-sanitized form -- a divergence that is a no-op for real-world numeric WR values but is documented here as an explicit, reviewable choice rather than a silent inconsistency.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unnecessary type annotations on two `main()`-local variables to keep the mypy delta gate neutral**
- **Found during:** Task-level `bash scripts/run_6_gates.sh` verification (run once before declaring the plan complete, per the plan's own `<verification>` note)
- **Issue:** Gate 4 (mypy delta, must not increase) failed: 65 -> 67. `main()` itself is untyped/unchecked by default; an explicitly-annotated local variable inside its body still triggers one gate-counted `[annotation-unchecked]` mypy note per variable. The two newly-hoisted `_watermarks: dict[Any, dict[str, Any]] = {}` / `_per_sheet_reasons: dict[Any, str] = {}` lines each added one such note -- the identical regression class 11-02-SUMMARY already documented and fixed the same way.
- **Fix:** Dropped both explicit annotations (`_watermarks = {}` / `_per_sheet_reasons = {}`), matching the unannotated style of every neighboring hoisted default in the same block.
- **Files modified:** `pipeline/orchestrate.py`
- **Verification:** `bash scripts/check_mypy_delta.sh` -> `PASS: mypy delta neutral or improved (65 -> 65)`; full `bash scripts/run_6_gates.sh` -> `ALL 6 GATES PASSED`.
- **Committed in:** `ec44ff6` (production-code commit; fixed before commit, so no separate fix-up commit was needed).

---

**Total deviations:** 1 auto-fixed (Rule 1 -- a real mypy regression surfaced by the plan's own gate, not a scope change), plus the documented commit-shape deviation above (task-boundary consolidation, not a behavior or scope change).
**Impact on plan:** No production behavior beyond what the plan specified. The mypy fix was required for the plan's own stated verification gate to pass; the commit-shape deviation only changes which commit hash a given task's diff lands under, not what landed.

## Issues Encountered

None beyond the two items above. The plan's own flagged assumption ("the edge probe classified INC-02 as `unclassified`... the empty-affected-set and single-pair cases are derived from D-04, not from a resolved edge probe") remains a plan-level caveat this plan does not resolve further -- `test_empty_affected_set_yields_empty_groups_successful_run` exercises exactly that derived case and passes, but a live shadow-parity comparison (plan 05) is the harness that would actually validate the assumption against real production data.

## User Setup Required

None -- no external service configuration required. `RUN_MEMORY_INCREMENTAL_ENABLED` remains OFF by default (plan 02); with the flag off, `resolve_run_mode` always resolves `full`, so `_run_phase2_incremental` is never invoked in production today (per the structural test `test_full_mode_never_calls_delta_probe_or_mapping_query`, which proves the incremental branch is unreachable when `_resolved_mode != 'incremental'`).

## Threat Flags

None. All six of this plan's STRIDE threat-register entries (T-11-17..T-11-22) were dispositioned and mitigated/accepted within the plan's own scope (bound parameterisation, all-or-nothing chunk failure, the widen-never-narrow mapping contract, distinct notes-only counters, counts-only logging, no schema change) -- no new, un-dispositioned surface was introduced.

## Next Phase Readiness

- CONTEXT.md D-04's central promise -- `group_source_rows` / `pricing.py` / `attribution.py` / `excel.py` byte-for-byte unmodified -- holds, mechanically verified via `git diff --exit-code` on all four files.
- Every failure path in the incremental branch is proven (by test, not just by contract) to fall back to full mode with a non-empty `fallback_reason`; the only outcome that is NOT a fallback is a genuinely empty affected set, which is now correctly distinguished from a failed run.
- `pipeline_memory.reader.map_affected_to_sheets` is production-shaped (chunked, bound, fail-open) and ready for plan 05's shadow parity harness to reuse for its own candidate-set computation.
- `run_ledger.mode`, `sheets_changed`, `rows_seen`, `groups_affected`, `groups_generated`, and the two new PHASE-2a/2b notes counters are all trustworthy and mode-aware -- the D-11 precondition ("scoped counters are only interpretable next to `run_ledger.mode`") continues to hold, now with real scoped values behind it whenever the flag is eventually turned on.
- `tests/golden/run_summary_baseline.json` (21 keys), `.github/workflows/`, and `pipeline_memory/schema.sql` are all untouched (verified via `git diff --exit-code`).
- No blockers. `bash scripts/run_6_gates.sh` passes ALL 6 gates on the final commit (`b3bd36c`).

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-08-26*

## Self-Check: PASSED

All 5 created/modified files (`pipeline/orchestrate.py`, `pipeline/fetch.py`,
`pipeline_memory/reader.py`, `tests/test_incremental_read.py`,
`.planning/REQUIREMENTS.md`) plus this SUMMARY.md confirmed present on disk;
all 3 commits (`ec44ff6`, `d01efeb`, `b3bd36c`) confirmed present in
`git log --oneline --all`.
