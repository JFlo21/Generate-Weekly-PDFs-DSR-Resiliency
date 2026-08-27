---
phase: 11-incremental-read-affected-group-regeneration
plan: 06
subsystem: pipeline_memory
tags: [smartsheet, supabase, incremental-read, deletion-reconciliation, column-mapping, tdd]

# Dependency graph
requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "Plan 05's orchestrate.py shadow hook and run_ledger_finish _finish_kwargs plumbing (this plan's reconciliation phase and its own _finish_kwargs additions coexist with it); plan 02's _normalize_column_mapping and resolve_run_mode trigger 2 (reused verbatim, never duplicated); plan 04's reader/writer boundary and fail-open conventions"
provides:
  - "pipeline_memory.reader.get_row_state_row_ids -- the stored row-id set for a sheet, paginated, fail-open empty set"
  - "pipeline_memory.writer.mark_rows_deleted -- chunked row_state.deleted_at UPDATE, returns {count, affected_pairs} read back from the UPDATE's own response rows"
  - "pipeline_memory.writer.upsert_sheet_registry's new column_mapping_sheets kwarg -- None (default, unchanged) refreshes every sheet; a set restricts the refresh"
  - "pipeline.orchestrate._reconcile_deep_run_deletions / _repair_group_state_for_affected_pairs / _compute_registry_mapping_sheets / _log_column_mapping_drift -- standalone, directly-testable helpers wired into main()'s deep-run path"
  - "The weekly deep run (EXECUTION_TYPE weekly_comprehensive) now marks deleted rows, repairs/confirms group_state, and is the sole refresher of sheet_registry.column_mapping"
affects: ["11-07 (get_parity_streak scans run_ledger.notes.parity_verdict, unaffected by this plan's separate mem_deep_run_rows_deleted notes key)"]

# Actuals (#2632)
actuals:
  tokens: 18891
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Ambiguity-safe guard collapse: pipeline/fetch.py's get_all_source_rows exposes no per-sheet read-success signal to the caller (out of this plan's declared files_modified), so a genuinely-empty sheet and a failed/partial read of that sheet are indistinguishable from orchestrate.py. Rather than build new per-sheet tracking, _reconcile_deep_run_deletions treats both identically (skip + warn) -- the safe superset of the plan's two stated guards, documented explicitly in the function's own docstring rather than silently narrowed."
    - "Read-back-from-write instead of a second read: mark_rows_deleted derives its returned affected_pairs from the UPDATE call's own response rows (PostgREST returns full row representation for an .update() by default) rather than adding a third pipeline_memory read function -- keeps the plan's declared files_modified exact (reader.py gained exactly one function: get_row_state_row_ids)."
    - "Group-state repair as observability, not a second write: _repair_group_state_for_affected_pairs does not call upsert_group_state itself. Because the deep run is always full mode, group_source_rows(all_rows) already excludes a deleted row, so the ordinary per-run group loop already recomputes and the existing post-upload flush already upserts a CORRECT content_hash for every group that still has >=1 row. The new function only identifies which of those already-scheduled writes belong to an affected pair, for logging/counting -- avoiding a second, redundant write path."
    - "NOT NULL-safe conditional column refresh: upsert_sheet_registry's new column_mapping_sheets is a per-call set (None = every sheet), computed by _compute_registry_mapping_sheets as 'every sheet id absent from this run's watermark read' on a non-deep run -- so a genuinely new sheet's first-ever INSERT still carries a mapping (the column is NOT NULL with no default) even when the whole-call refresh is otherwise suppressed."

key-files:
  created:
    - tests/test_deep_run_reconciliation.py
    - tests/fixtures/incremental/deleted_row.json
    - tests/fixtures/incremental/formula_only_change.json
  modified:
    - pipeline_memory/reader.py
    - pipeline_memory/writer.py
    - pipeline/orchestrate.py
    - docs/run-memory-write-flip-checklist.md

key-decisions:
  - "A sheet with zero observed rows in this run's live read AND a sheet not successfully read in full are treated as the SAME guard case (skip + warn), because pipeline/fetch.py (out of this plan's declared files_modified) exposes no per-sheet read-success signal to orchestrate.py. Documented explicitly in _reconcile_deep_run_deletions' docstring as the safe superset of the plan's two stated behaviors, not a silent narrowing."
  - "mark_rows_deleted returns {\"count\": int, \"affected_pairs\": set} rather than a bare count -- the plan's action text says both 'returns a zero count' AND 'collect the affected (wr, week_ending) pairs from the deleted rows'; deriving the pairs from the UPDATE's own response rows (no second read) satisfies both without adding a third reader/writer function outside this plan's declared files_modified."
  - "group_state repair for a deletion is implemented as OBSERVABILITY over the existing post-upload flush, not a second write path -- the deep run's ordinary full-mode group loop already recomputes every surviving group's content_hash over the post-deletion row set every run; _repair_group_state_for_affected_pairs only identifies which already-scheduled writes are attributable to a deletion, for logging."
  - "A (wr, week_ending) pair whose LAST remaining row is deleted this run produces no group_state repair at all -- documented as a known, out-of-scope limitation (recorded in .planning/WINDOWS.md as a deviation) rather than built speculatively, since cleaning it up needs a stored target_sheet_id reader this plan does not add."
  - "column_mapping refresh is gated by a per-sheet SET (column_mapping_sheets), not a single whole-call boolean, because sheet_registry.column_mapping is NOT NULL with no default -- a genuinely new sheet discovered on a frequent (non-deep) run still needs its first-ever mapping written on INSERT, even though every ALREADY-registered sheet's mapping stays untouched that run."
  - "_normalize_column_mapping (already a standalone function from plan 02's resolve_run_mode trigger 2) is reused verbatim by _log_column_mapping_drift -- Task 2's action text asked to extract a shared helper only if one did not already exist; plan 02 had already extracted it, so Task 2 adds zero duplicate normalisation logic."

requirements-completed: [INC-03]

coverage:
  - id: D1
    description: "The weekly deep run diffs stored row_state row ids against its own full read's row ids per sheet and marks the difference deleted (row_state.deleted_at), never rewriting an already-deleted row."
    requirement: "INC-03"
    verification:
      - kind: unit
        ref: "tests/test_deep_run_reconciliation.py::RowStateRowIdsReadTests, MarkRowsDeletedTests, DeepRunDeletionReconciliationTests (23 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A zero-row or partial full read never produces a deletion -- a sheet with no observed live rows this run (indistinguishable, by design, from an unsuccessfully-read sheet given available signals) is skipped entirely with a warning + Sentry breadcrumb, never inferred as 'every row deleted'."
    requirement: "INC-03"
    verification:
      - kind: unit
        ref: "tests/test_deep_run_reconciliation.py::DeepRunDeletionReconciliationTests::test_zero_row_full_read_marks_zero_deleted_and_skips, test_sheet_absent_from_live_map_is_treated_as_zero_row, test_fixture_deleted_row_drives_expected_diff"
        status: pass
    human_judgment: false
  - id: D3
    description: "group_state rows for a deletion-affected (wr, week_ending) pair are confirmed repaired via the existing post-upload flush (attachment ids preserved by the pre-existing COALESCE-by-omission); a pair whose group is now fully empty is identified and logged as a documented limitation, never silently mis-repaired."
    requirement: "INC-03"
    verification:
      - kind: unit
        ref: "tests/test_deep_run_reconciliation.py::GroupStateRepairTests (4 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "sheet_registry.column_mapping is refreshed only on the weekly_comprehensive execution type; a frequent run never silently adopts a drifted mapping for an already-registered sheet (D-02 trigger 2 escalates instead), while a genuinely new sheet still gets its first mapping written regardless of execution type."
    requirement: "INC-03"
    verification:
      - kind: unit
        ref: "tests/test_deep_run_reconciliation.py::ColumnMappingRefreshTests (10 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A formula-only change to a HASH_FIELDS-mapped column reconciles through the ordinary content-hash path (different compute_content_hash() value); a formula-only change to a field outside HASH_FIELDS produces the identical hash and no repair -- correct, not a miss. Fixture is derived from, and its provenance names, the MEM-04 cassettes rather than re-probing the Smartsheet API."
    requirement: "INC-03"
    verification:
      - kind: unit
        ref: "tests/test_deep_run_reconciliation.py::FormulaOnlyReconciliationTests (5 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "docs/run-memory-write-flip-checklist.md carries the single live-verification section ROADMAP.md success criterion 3 requires (delete one row + one formula-only edit on the sandbox rig before a Monday weekly_comprehensive run, then confirm row_state/group_state/column_mapping)."
    requirement: "INC-03"
    verification:
      - kind: other
        ref: "tests/test_deep_run_reconciliation.py::FormulaOnlyReconciliationTests::test_checklist_names_weekly_comprehensive_deep_run_verification; the plan's own SC3 <verify> one-liner"
        status: pass
    human_judgment: true
    rationale: "The checklist SECTION is proven present and correctly worded by test + the plan's own verify command, but the live run it describes has not happened -- it requires the RUN_MEMORY_WRITE_ENABLED flip PR to merge first (still unmerged per this plan's own precondition-resolution evidence below) and a real Monday weekly_comprehensive run against the sandbox rig after that. A human (Juan) must perform and confirm that run before ROADMAP success criterion 3 is fully closed."

duration: ~50min (no PLAN_START_TIME epoch captured at kickoff; estimated from session activity -- required reading, design analysis of the existing orchestrate.py group loop / registry passes, TDD RED/GREEN, one mypy-delta fix-up, full 6-gate verification)
completed: 2026-08-26
status: complete
---

# Phase 11 Plan 06: Weekly Deep Run Deletion + Column-Mapping Reconciliation Summary

**`mark_rows_deleted` / `get_row_state_row_ids` close the frequent path's structural blind spot (`rowsModifiedSince` never surfaces a deleted row) on the weekly deep run only, with `sheet_registry.column_mapping` refresh gated to the same `weekly_comprehensive` execution type and formula-only changes proven to reconcile through the pre-existing content-hash path.**

## Performance

- **Duration:** ~50 min (estimated; no epoch timer captured at kickoff)
- **Tasks:** 3
- **Files modified:** 7 (3 created, 4 modified)
- **Commits:** 3

## Checkpoint / Decisions

Task 1 declares a `<precondition>`: `pipeline_memory.row_state` holds rows for
at least one registered sheet, written by a real run after the
`RUN_MEMORY_WRITE_ENABLED` flip. Per the orchestrator's explicit continuation
instruction, this was **not** treated as `blocking-human` for this plan — the
owner (Juan) already ruled on this exact fact for plan 11-05 earlier the same
day (2026-08-26), and that decision carries forward. Recording the
orchestrator-verified evidence at approval time verbatim, since it documents
a real, transparent gap between this plan's precondition and what was
actually true:

- The `RUN_MEMORY_WRITE_ENABLED` flip PR has **NOT** merged: no
  `RUN_MEMORY_*` key exists in `.github/workflows/weekly-excel-generation.yml`
  on `origin/master` or on this branch.
- Supabase `pipeline_memory` (project `poeyztlmsawfoqlanucc`) **IS**
  populated from Phase 10's manual rollout, not a scheduled post-flip run:
  `row_state` 209,464 rows; `sheet_registry` 120/120 sheets watermarked;
  `run_ledger` 1 real successful manual run; `group_state` 0 rows.
- Juan approved proceeding with the code + unit-test work on that basis. All
  three tasks in this plan are code + fixtures + unit tests with mocked
  Smartsheet and Supabase clients — no live Supabase or Smartsheet calls were
  made, and no `RUN_MEMORY_*` env var was set in any workflow file.
- **This plan's live verification (success criterion 3 — the sandbox-rig
  deletion + formula edit before a Monday `weekly_comprehensive` run) remains
  an open post-merge dependency.** The checklist section this plan adds
  (`docs/run-memory-write-flip-checklist.md`) is the artifact that makes that
  verification actionable once the flip PR lands; the run itself has not
  happened.

## Accomplishments

- Shipped `pipeline_memory.reader.get_row_state_row_ids(sheet_id)` — the
  stored `row_state` row-id set for a sheet (paginated at 1,000 rows/page,
  filtered to `deleted_at IS NULL`), fail-open to an empty set on any
  failure, mirroring `get_sheet_watermarks`/`map_affected_to_sheets`'
  established conventions.
- Shipped `pipeline_memory.writer.mark_rows_deleted(sheet_id, row_ids,
  run_id)` — chunked `row_state.deleted_at` UPDATE (never rewrites an
  already-deleted row), returning `{"count", "affected_pairs"}` derived from
  the UPDATE's own response rows (no second read). Zero schema change —
  `deleted_at` was already reserved (Phase 10 `COVERAGE.md` line-33 OPT-OUT
  lifted here).
- Shipped `pipeline.orchestrate._reconcile_deep_run_deletions` — the
  detection loop wired into `main()` right after the full read and the
  memory write complete, gated on `EXECUTION_TYPE == 'weekly_comprehensive'`
  plus the standard `RUN_MEMORY_WRITE_ENABLED`/`TEST_MODE` double gate. A
  sheet with zero observed live rows this run is skipped with a warning +
  Sentry breadcrumb (T-11-30) rather than risking a false mass-deletion.
- Shipped `pipeline.orchestrate._repair_group_state_for_affected_pairs` — an
  observability-only confirmation that the existing post-upload `group_state`
  flush (unchanged, still upserts every surviving group's fresh content hash
  each full run with attachment ids preserved by its pre-existing COALESCE)
  already covers a deletion-affected group; a pair whose group is now fully
  empty is identified as a documented, out-of-scope limitation.
- Shipped `pipeline.orchestrate._compute_registry_mapping_sheets` /
  `_log_column_mapping_drift` and `upsert_sheet_registry`'s new
  `column_mapping_sheets` kwarg — the deep run refreshes every sheet's
  mapping; a frequent run refreshes only a genuinely new sheet's first-ever
  mapping (`NOT NULL` safety), leaving every already-registered sheet's
  stored mapping untouched so D-02 trigger 2 keeps being the escalation
  mechanism, never a silent adoption. Reuses `_normalize_column_mapping`
  (already a standalone function from plan 02) rather than duplicating it.
- Added the "Deep-run live verification (INC-03 / success criterion 3)"
  section to `docs/run-memory-write-flip-checklist.md`.
- `tests/test_deep_run_reconciliation.py`: 44 tests across
  `RowStateRowIdsReadTests` (7), `MarkRowsDeletedTests` (7),
  `DeepRunDeletionReconciliationTests` (8), `GroupStateRepairTests` (4),
  `MainWiringStructuralTests` (2), `ColumnMappingRefreshTests` (10),
  `FormulaOnlyReconciliationTests` (5) — above the plan's 7/6/17-test floors.

## Task Commits

Each task was committed atomically, TDD RED then GREEN, with a separate docs
commit for Task 3's literal checklist deliverable:

1. **Tasks 1-3 (RED): failing tests + fixtures** — `94ccb2e` (test)
2. **Tasks 1-2 (GREEN): reader/writer/orchestrate implementation** —
   `5fb64d1` (feat)
3. **Task 3: checklist live-verification section** — `db7592a` (docs)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

_Deviation from the plan's literal per-task commit shape: all three tasks'
tests were written in one RED commit, and Tasks 1 and 2's production code
landed in one GREEN commit, because Task 2's `column_mapping` refresh sits
inside the SAME `main()` call sites (PASS 1 / PASS 2 `upsert_sheet_registry`)
Task 1's deletion-reconciliation phase is wired next to, and Task 3 needed
Task 1's `_repair_group_state_for_affected_pairs` for its own integration
test. This mirrors the documented "coherent commit over an artificial
function-boundary split" precedent from plans 04/05. Every task's own
acceptance criteria were independently re-verified against the final state
(full `pytest tests/ -q` green, `bash scripts/run_6_gates.sh` ALL 6 GATES
PASSED) before this SUMMARY was written._

## Files Created/Modified

- `pipeline_memory/reader.py` — `get_row_state_row_ids`,
  `_ROW_STATE_PAGE_SIZE` constant.
- `pipeline_memory/writer.py` — `mark_rows_deleted`;
  `upsert_sheet_registry` gains `column_mapping_sheets` (default `None`,
  every existing call site byte-for-byte unchanged).
- `pipeline/orchestrate.py` — `_reconcile_deep_run_deletions`,
  `_repair_group_state_for_affected_pairs`,
  `_compute_registry_mapping_sheets`, `_log_column_mapping_drift` (new
  standalone functions); `_is_deep_run` / `_registry_mapping_sheets`
  computed before PASS 1; both `upsert_sheet_registry` call sites pass
  `column_mapping_sheets=`; the deletion-reconciliation call site after PASS
  2; the group-state repair confirmation after the shadow-parity hook; both
  `run_ledger_finish` call sites gain a conditional
  `mem_deep_run_rows_deleted` notes key; `_reconcile_ran` /
  `_reconcile_rows_marked_deleted` / `_reconcile_affected_pairs` hoisted
  defaults.
- `tests/test_deep_run_reconciliation.py` (new, 44 tests).
- `tests/fixtures/incremental/deleted_row.json`,
  `formula_only_change.json` (new).
- `docs/run-memory-write-flip-checklist.md` — new live-verification section.

## Decisions Made

See `key-decisions` in frontmatter. The most consequential: collapsing the
plan's two stated guards ("zero-row full read" and "sheet not successfully
read in full") into one code path, because `pipeline/fetch.py` — outside
this plan's declared `files_modified` — exposes no per-sheet read-success
signal to `orchestrate.py`'s caller. Documented transparently in the
function's own docstring as the safe superset rather than silently choosing
one interpretation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed two unnecessary type annotations on `main()`-local variables to keep the mypy delta gate neutral**
- **Found during:** Plan-level verification (`bash scripts/run_6_gates.sh`,
  run once before declaring the plan complete per the plan's own
  `<verification>` note)
- **Issue:** Gate 4 (mypy delta, must not increase) failed: 65 -> 67.
  `main()` itself is untyped/unchecked by default; two newly-hoisted,
  explicitly-annotated locals (`_reconcile_affected_pairs: set = set()`,
  `_reconcile_live_ids_by_sheet: dict[Any, set] = {}`) each triggered one
  gate-counted `[annotation-unchecked]` mypy note — the identical
  regression class 11-02-SUMMARY / 11-04-SUMMARY already documented and
  fixed the same way.
- **Fix:** Dropped both explicit annotations, matching the unannotated style
  of every neighboring hoisted default in the same block.
- **Files modified:** `pipeline/orchestrate.py`
- **Verification:** `bash scripts/check_mypy_delta.sh` ->
  `PASS: mypy delta neutral or improved (65 -> 65)`; full
  `bash scripts/run_6_gates.sh` -> `ALL 6 GATES PASSED`.
- **Committed in:** `5fb64d1` (production-code commit; fixed before commit,
  so no separate fix-up commit was needed).

---

**Total deviations:** 1 auto-fixed (Rule 1 — a real mypy regression
surfaced by the plan's own gate, not a scope change), plus the documented
commit-shape deviation above (task-boundary consolidation, not a behavior or
scope change), plus one documented out-of-scope limitation (see Known
Limitations below).
**Impact on plan:** No production behavior beyond what the plan specified.
The mypy fix was required for the plan's own stated verification gate to
pass; the commit-shape deviation only changes which commit hash a given
task's diff lands under, not what landed.

## Known Limitations

**A `(wr, week_ending)` pair whose LAST remaining row is deleted by the deep
run produces no `group_state` repair.** Once every row for that pair is
gone, `group_source_rows()` never assigns it to a group this run, so it
never appears in `_deferred_group_state` for `_repair_group_state_for_affected_pairs`
to find. Its `group_state` row is left with its last-known `content_hash` /
`row_count` rather than being actively cleared. Cleaning this up needs the
stored `target_sheet_id`(s) for that pair, which this plan does not add a
reader for (out of the plan's declared `files_modified`). Documented in code
(`_repair_group_state_for_affected_pairs`'s docstring) and recorded in
`.planning/WINDOWS.md` (kind: `deviation`, id 2) for cross-phase visibility.
This is a data-hygiene nicety, not a billing-integrity risk this phase's
threat model registers — nothing in the current pipeline reads `group_state`
as a live billing input.

## Issues Encountered

None beyond the mypy fix above and the documented group_state limitation.
The plan's own flagged assumption (Edge Coverage: INC-03 classified
`unclassified` by the edge probe) is addressed by this plan's explicit
zero-row/unread-sheet guard and its test coverage
(`DeepRunDeletionReconciliationTests`), but — per the plan's objective —
remains unproven against a real Smartsheet full-sheet-emptied event; only
the live verification (checklist, D6 above) can close that gap.

## User Setup Required

None — no external service configuration required by this plan's own code.
The `RUN_MEMORY_WRITE_ENABLED` flip PR (a precondition for the deep-run
reconciliation phase ever actually running in production) remains a
separate, owner-gated PR per D-10, unchanged by this plan. The one live
verification this plan's checklist section describes must be performed by
Juan after that flip merges, on a Monday `weekly_comprehensive` run against
the sandbox rig — see `docs/run-memory-write-flip-checklist.md`'s new
"Deep-run live verification" section.

## Threat Flags

None new. All six of this plan's own STRIDE threat-register entries
(T-11-30..T-11-35) were dispositioned and mitigated/accepted within the
plan's own scope:
- T-11-30 (critical, deletion inference from a zero-row/partial read) —
  mitigated by the collapsed zero-row/unread-sheet guard, pinned by
  `test_zero_row_full_read_marks_zero_deleted_and_skips` and
  `test_sheet_absent_from_live_map_is_treated_as_zero_row`.
- T-11-31 (wrongly-marked deletions narrowing future scope) — mitigated:
  `deleted_at` is written only on `weekly_comprehensive` after a successful
  full read, and `mark_rows_deleted` is fail-open (a failure leaves rows
  unmarked for the next deep run to retry), pinned by
  `test_failure_returns_zero_count_empty_pairs`.
- T-11-32 (`group_state` repair nulling attachment ids) — mitigated: the
  repair is pure observability over the existing `upsert_group_state`
  COALESCE-by-omission path, never a second write with attachment fields;
  pinned by `test_repaired_records_never_carry_attachment_keys`.
- T-11-33 (silently adopting a drifted `column_mapping` on a frequent run) —
  mitigated: only the deep run refreshes an already-registered sheet's
  mapping; pinned by
  `test_production_frequent_run_issues_zero_refresh_writes_when_all_registered`.
- T-11-34 (new `row_state` UPDATE from the writer, accepted) — same
  `service_role` client and existing schema-wide `GRANT ... UPDATE` from
  Phase 10; confirmed against `pipeline_memory/schema.sql` (no schema
  change, no new grant).
- T-11-35 (deletion logs/breadcrumbs information disclosure) — mitigated:
  every log line and breadcrumb this plan adds carries sheet ids, row ids,
  and counts only — no cell content, no price values.

## Next Phase Readiness

- `pipeline_memory.reader.get_row_state_row_ids` and
  `pipeline_memory.writer.mark_rows_deleted` are production-shaped
  (paginated/chunked, fail-open, never-rewrite-already-deleted) and ready
  for the flip PR's first real `weekly_comprehensive` run to exercise live.
- `upsert_sheet_registry`'s new `column_mapping_sheets` kwarg defaults to
  `None`, so every existing call site (Phase 10, plan 02) is byte-for-byte
  unchanged; only this plan's two `main()` call sites pass a computed value.
- `tests/golden/run_summary_baseline.json` (21 keys), `.github/workflows/`,
  and `pipeline_memory/schema.sql` are all untouched (verified via
  `git diff --exit-code`).
- No blockers. `bash scripts/run_6_gates.sh` passes ALL 6 gates on the final
  commit (`db7592a`); full suite 1694 passed / 1 skipped / 141 subtests.
- Open dependency, unchanged by this plan: the `RUN_MEMORY_WRITE_ENABLED`
  flip PR must merge and a real Monday `weekly_comprehensive` run must
  execute against the sandbox rig before ROADMAP success criterion 3's live
  verification is closed (checklist item added by this plan; the run itself
  happens after merge, per D-10).
- Phase 11's remaining plan (07 — parity streak) is unaffected by this
  plan's `mem_deep_run_rows_deleted` notes key (a separate `run_ledger.notes`
  field from `parity_verdict`/`parity_details`).

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-08-26*

## Self-Check: PASSED

All 3 created files (`tests/test_deep_run_reconciliation.py`,
`tests/fixtures/incremental/deleted_row.json`,
`tests/fixtures/incremental/formula_only_change.json`) and all 4
modified files (`pipeline_memory/reader.py`, `pipeline_memory/writer.py`,
`pipeline/orchestrate.py`, `docs/run-memory-write-flip-checklist.md`)
confirmed present on disk; all 3 commits (`94ccb2e`, `5fb64d1`, `db7592a`)
confirmed present in `git log --oneline --all`; `bash scripts/run_6_gates.sh`
re-run and confirmed `ALL 6 GATES PASSED` before this SUMMARY was
finalized.
