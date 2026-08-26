---
phase: 10-run-memory-foundation-shadow-writes
plan: 02
subsystem: database
tags: [supabase, postgres, pipeline_memory, shadow-write, fail-open, row_state, row_event, chunking, billing-pipeline]

# Dependency graph
requires:
  - phase: 10-run-memory-foundation-shadow-writes
    provides: "plan 10-01's pipeline_memory package (client.py, schema.sql, the initial HASH_FIELDS/compute_content_hash/upsert_rows_bulk stub) this plan extends"
provides:
  - "pipeline/fetch.py::__row_modified_at -- additive, hash-neutral capture of the Smartsheet row's own modified-at timestamp"
  - "pipeline_memory/writer.py::_row_to_payload -- the authoritative row_state payload builder: raw mapped columns for foreman/helper/vac_crew observed, WR sanitization, CU/Pole synonym fallback, caller-resolved dates, bad-row_id skip"
  - "pipeline_memory/writer.py::upsert_rows_bulk -- chunked (_CHUNK_ROWS=500) fail-open bulk upsert with per-call aggregate counters and one aggregate WARNING per call"
  - "pipeline/orchestrate.py::_run_memory_write_phase -- the budgeted, sequential, per-sheet shadow-write loop wired into main() right after Phase 2 completes"
affects: [10-03-group-state-and-sheet-registry, 10-05-shadow-rollout, 10-06-apply-schema-and-control-run]

# Actuals (#2632)
actuals:
  tokens: 14731
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Row-payload builder returns None (never fabricates) on a missing/non-int row_id; the caller (upsert_rows_bulk) owns the counter bump so the builder stays a pure, directly-testable mapper"
    - "Per-sheet loop extracted into a standalone, fully-typed module function (_run_memory_write_phase) rather than inlined in main() -- self-gated on the same RUN_MEMORY_WRITE_ENABLED/TEST_MODE constants main() checks, directly unit-testable via mock.patch.object on the imported module constants"
    - "Two-tier sub-budget guard mirrored verbatim from existing orchestrate.py patterns: pre-flight elapsed/remaining/required (attachment pre-fetch shape) plus a per-iteration check AFTER each sheet (main group loop shape) -- not the attachment pre-fetch's single collective as_completed(timeout=) shape"

key-files:
  created: []
  modified:
    - pipeline/fetch.py
    - pipeline_memory/writer.py
    - pipeline/orchestrate.py
    - tests/test_pipeline_memory_shadow.py

key-decisions:
  - "helper_observed/vac_crew_observed read the RAW mapped columns ('Foreman Helping?', 'VAC Crew Helping?'), never the pipeline's completion-gated __helper_foreman/__vac_crew_name keys -- those are ABSENT whenever the row's completion checkbox is unchecked, which would silently drop a real observed name; memory records what was literally on the row"
  - "week_ending/snapshot_date are resolved by the CALLER (pipeline/orchestrate.py, via pipeline.utils.excel_serial_to_date -- the same parser grouping uses) and passed into upsert_rows_bulk via new __mem_week_ending/__mem_snapshot_date keys stashed onto each row dict; pipeline_memory/writer.py keeps importing nothing from pipeline.* (_coerce_date explicitly refuses a raw string, mirroring billing_audit's _coerce_week_ending)"
  - "upsert_rows_bulk's per-sheet payload is chunked at _CHUNK_ROWS=500 (mirrors billing_audit's prefetch_attribution precedent); a chunk failure bumps rows_upsert_errored by that chunk's row count and continues to the remaining chunks, with exactly one aggregate WARNING per call rather than one per chunk"
  - "Counter rename from 10-01's rows_upsert_written to rows_upsert_sent/rows_upsert_changed: 'sent' tracks every row handed to the bulk upsert regardless of RPC outcome (MEM-02's 'every accepted row is sent exactly once'), 'changed' tracks the size of the returned affected set -- clearer separation than a single written/errored pair once chunking means partial success is possible per call"
  - "_run_memory_write_phase is a standalone, fully-typed module function (not inlined directly in main()'s body) so the 5 required loop-behavior tests (flag off, per-sheet bucketing, failure isolation, pre-flight skip, mid-loop break) can call it directly with mock.patch.object on pipeline.orchestrate's module-level config constants, instead of invoking all of main()'s Smartsheet/Sentry/audit machinery"
  - "The pre-existing pipeline_memory/writer.py::build_row_payload from plan 10-01's Task-3 deviation is fully superseded and renamed to _row_to_payload with a 4-arg signature (row_data, run_id, week_ending, snapshot_date) -- 10-01's SUMMARY explicitly flagged this contract as a minimal placeholder for plan 10-02 to complete, not a frozen API"

requirements-completed: [MEM-02, MEM-03]

coverage:
  - id: D1
    description: "pipeline/fetch.py additively captures the Smartsheet row's own modified-at timestamp onto row_data['__row_modified_at'], proven hash-neutral for the existing group-level calculate_data_hash and correctly mapped (including tolerating absence) through the row-payload builder"
    requirement: MEM-02
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::RowModifiedAtHashNeutralityTests"
        status: pass
      - kind: other
        ref: "git diff --numstat -- pipeline/fetch.py (10 added, 0 removed; bounded gate <=12/<=2)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh"
        status: pass
    human_judgment: false
  - id: D2
    description: "pipeline_memory/writer.py's content-hash, row-payload, and chunked fail-open bulk-upsert contract: HASH_FIELDS excludes run-varying fields, foreman/helper/vac_crew observed read the RAW mapped columns never the resolved/gated derivatives, WR sanitization + CU/Pole synonym fallback mirror billing_audit, and upsert_rows_bulk chunks at 500 rows with per-call fail-open semantics"
    requirement: MEM-02
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests, ChunkingAndPayloadSizeTests, ChunkFailOpenTests, AffectedSetParsingTests, CounterAndPiiDisciplineTests"
        status: pass
      - kind: other
        ref: "python -m ast import-isolation check on pipeline_memory/writer.py -> WRITER_BOUNDARY_OK"
        status: pass
    human_judgment: false
  - id: D3
    description: "pipeline/orchestrate.py::_run_memory_write_phase wires the per-sheet upsert_rows_bulk loop into main() right after Phase 2 completes: pre-flight + per-iteration sub-budget guards, sequential (no re-fetch, no ThreadPoolExecutor), per-sheet exception isolation, zero change to the frozen run_summary.json contract"
    requirement: MEM-03
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::MemoryWritePhaseTests (flag-off, per-sheet bucketing, failure isolation, pre-flight skip, mid-loop break)"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- generate_weekly_pdfs.py tests/golden/run_summary_baseline.json .github/workflows/ requirements.txt"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh"
        status: pass
    human_judgment: false

duration: ~40min
completed: 2026-08-25
status: complete
---

# Phase 10 Plan 02: Run-Memory Foundation (shadow writes) Summary

**The pipeline's per-row content hash, raw-observed row-payload builder, and chunked fail-open `upsert_rows_bulk` are now wired end-to-end from `pipeline/orchestrate.py`'s per-sheet shadow-write loop, still off by default behind `RUN_MEMORY_WRITE_ENABLED`.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-08-25T16:44:00Z (approx.)
- **Completed:** 2026-08-25T17:02:20Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `pipeline/fetch.py` additively captures the Smartsheet row's own modified-at timestamp onto `row_data['__row_modified_at']` — read defensively via `getattr`, ISO-serialised, proven hash-neutral for the existing group hash (10 lines added, 0 removed)
- `pipeline_memory/writer.py`'s row-payload builder (`_row_to_payload`) is now the authoritative MEM-02 contract: `foreman_observed`/`helper_observed`/`vac_crew_observed` read the RAW mapped Smartsheet columns (`Foreman`, `Foreman Helping?`, `VAC Crew Helping?`) — never `__effective_user`'s resolved sentinel, never the completion-gated `__helper_foreman`/`__vac_crew_name` derivatives — pinned by two regression tests encoding the 93-WR/5,824-row historical defect directly
- `upsert_rows_bulk` chunks at `_CHUNK_ROWS=500` (13 RPC calls for a 6,054-row sheet; ~497 bytes/row, well under the 1 MB PostgREST body limit), is fail-open per chunk (a middle-chunk failure keeps the successful chunks' affected set, bumps `rows_upsert_errored`, logs exactly one aggregate WARNING, never raises), and never returns `None`
- `pipeline/orchestrate.py::_run_memory_write_phase` buckets already-fetched rows by `__source_sheet_id` and shadow-writes each sheet in its own bulk call, sequential by design, with a pre-flight sub-budget guard (mirrors the attachment pre-fetch's elapsed/remaining/required shape) plus a per-iteration check after every sheet (mirrors the main group loop's shape, not the attachment pre-fetch's collective timeout) — wired into `main()` immediately after Phase 2 completes, before the audit system initializes
- 34 -> 39 tests added to `tests/test_pipeline_memory_shadow.py` (21 -> 39 total across this plan's three tasks) covering the raw-not-resolved regression, hash scope, chunking, payload size, fail-open chunk failure, affected-set parsing tolerance, and all five required loop behaviors (flag off, per-sheet bucketing, failure isolation, pre-flight skip, mid-loop break)

## Task Commits

Each task was committed atomically (Tasks 1 and 2 are `tdd="true"`, so each has a RED test commit followed by a GREEN feat commit):

1. **Task 1: Capture the Smartsheet row modified timestamp onto row_data** - `7ab0158` (test, RED) + `98b5ee1` (feat, GREEN)
2. **Task 2: Content hash, row payload, and the chunked fail-open bulk upsert** - `32d2b46` (test, RED) + `4a81c69` (feat, GREEN)
3. **Task 3: Wire the budgeted per-sheet memory write loop into main()** - `bce27c5` (feat)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

## TDD Gate Compliance

**Task 1** (`tdd="true"`) followed RED -> GREEN:
- RED gate: `7ab0158` (`test(10-02): add row_modified_at hash-neutrality + payload mapping tests`). Both tests already held true before this task's implementation (hash-neutrality is a property of the EXISTING `calculate_data_hash`'s named-field-only reads; the payload builder's `.get()` already tolerated a missing key) — see Issues Encountered for the honest accounting of this.
- GREEN gate: `98b5ee1` (`feat(10-02): capture Smartsheet row-modified timestamp onto row_data`).
- No REFACTOR commit needed.

**Task 2** (`tdd="true"`) followed RED -> GREEN, verified literally: the Task 2 GREEN implementation was temporarily reverted to plan 10-01's committed state and the full targeted test file was re-run, confirming 14 of the new/updated tests failed with `AttributeError` (missing `_CHUNK_ROWS`, `_row_to_payload`, etc.) before the implementation was restored and re-verified GREEN (34/34 passing).
- RED gate: `32d2b46` (`test(10-02): add MEM-02 row-payload contract tests for Task 2`).
- GREEN gate: `4a81c69` (`feat(10-02): content hash, row payload, and chunked fail-open bulk upsert`).
- No REFACTOR commit needed.

**Task 3** is `type="auto"` (not TDD) — a single `feat` commit, `bce27c5`.

## Files Created/Modified
- `pipeline/fetch.py` - additive `__row_modified_at` capture inside the existing provenance-metadata block (10 lines)
- `pipeline_memory/writer.py` - `_CHUNK_ROWS`, `_WR_SANITIZE`, `_sanitized_wr`, `_is_checked`, `_coerce_date`, `_row_to_payload` (supersedes 10-01's `build_row_payload`), chunked `upsert_rows_bulk`, `_bump_counter_by`; `HASH_FIELDS`/`compute_content_hash` unchanged (already correct from 10-01)
- `pipeline/orchestrate.py` - new module function `_run_memory_write_phase`; call site wired into `main()` right after Phase 2 completes; `run_ledger_finish` now feeds `groups_affected`; hoisted `_mem_affected` counter; stale "(not-yet-wired)" comment corrected
- `tests/test_pipeline_memory_shadow.py` - 21 -> 39 tests: 2 new (Task 1), 14 new/updated (Task 2), 5 new (Task 3), plus renamed references to the old `build_row_payload`/`rows_upsert_written` names

## Decisions Made
See `key-decisions` in frontmatter. All are load-bearing for correctness (raw-not-resolved provenance), the package-boundary contract (writer imports nothing from `pipeline.*`), or testability (the standalone phase function), and are documented inline in the code they govern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed a redundant type annotation that broke Gate 4 (mypy delta)**
- **Found during:** Task 3, running `bash scripts/run_6_gates.sh` Gate 4
- **Issue:** `_mem_affected: set = set()` (an annotated local inside the untyped `main()` function) produced a NEW `annotation-unchecked` note at that line, incrementing the frozen mypy baseline from 65 to 66 lines and failing Gate 4's "no increase vs. baseline" check.
- **Fix:** Dropped the redundant type annotation (`_mem_affected = set()`), matching the unannotated style of every other hoisted `_mem_*`/`_groups_*` counter in the same block.
- **Files modified:** `pipeline/orchestrate.py`
- **Verification:** `bash scripts/check_mypy_delta.sh` -> `PASS: mypy delta neutral or improved (65 -> 65)`; `bash scripts/run_6_gates.sh` -> all 6 gates pass.
- **Committed in:** `bce27c5` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for Task 3's own `<verify>` block to pass. No scope creep — a one-line style fix inside the file this task already edits.

## Issues Encountered

**Task 1's RED-phase tests are implementation-invariant, by design of the plan's own `<behavior>` block.** Both required tests (hash-neutrality of `calculate_data_hash`, and the payload builder's tolerance of a missing `__row_modified_at` key) construct plain dicts directly rather than exercising `pipeline/fetch.py`'s row-scraping loop — they were TRUE before this task's `pipeline/fetch.py` change and remain true after it, because `calculate_data_hash` already reads only explicitly named fields and the payload builder's `dict.get(key)` already returns `None` for an absent key. Investigated per the TDD fail-fast rule: this is a deliberate test design (proving the CONTRACT the new fetch.py line depends on, not the fetch.py line itself) rather than a mistake — unit-testing the actual Smartsheet SDK `Row.modified_at` -> `row_data['__row_modified_at']` capture would require a full mocked `Sheet`/`Row` success-path fixture that does not exist anywhere in this test file's precedent (`tests/test_fetch_auth_errors.py` only mocks the failure path). That capture line is instead proven correct via: (1) live SDK introspection this session confirming `Row.modified_at` exists as a safe `getattr` target, (2) the bounded `git diff --numstat` gate, (3) the full 1453-test suite, and (4) `bash scripts/run_6_gates.sh`. Resolved — no lasting effect; documented here per the TDD "investigate, don't fabricate" rule.

**Task 2's RED verification required a temporary revert** (not a `git stash` — a plain filesystem copy-then-restore, per the destructive-git-operations prohibition) of `pipeline_memory/writer.py` back to its plan-10-01-committed state to confirm the 14 new/updated tests genuinely fail (`AttributeError` on `_CHUNK_ROWS`, `_row_to_payload`, etc.) before the Task 2 implementation exists. Resolved cleanly — the backup was restored and the full suite re-verified GREEN before either commit was made.

## User Setup Required

None - no external service configuration required this plan. `RUN_MEMORY_WRITE_ENABLED` stays default OFF in code; `pipeline_memory/schema.sql` is still not applied to any live Supabase project (plan 10-06's operator checkpoint), so the new row-payload/chunking code paths this plan ships have never made a live network call.

## Next Phase Readiness

- `pipeline_memory/writer.py::_row_to_payload` / `upsert_rows_bulk` and `pipeline/orchestrate.py::_run_memory_write_phase` give plan 10-03 a proven pattern to extend for `sheet_registry` and `group_state` (the two remaining shadow-write integration points from the design spec's system diagram).
- `RUN_MEMORY_WRITE_ENABLED` stays OFF in code; no `.github/workflows/*` file was touched this plan; `git diff --exit-code -- generate_weekly_pdfs.py .github/workflows/ requirements.txt tests/golden/run_summary_baseline.json billing_audit/` is clean, and all 6 gates + the full 1453-test suite pass (up from the 1433-test baseline recorded at Wave 1 completion).
- No blockers for plan 10-03.

## Self-Check: PASSED

All modified files found on disk (`pipeline/fetch.py`, `pipeline_memory/writer.py`, `pipeline/orchestrate.py`, `tests/test_pipeline_memory_shadow.py`, this SUMMARY.md). All five task commits (`7ab0158`, `98b5ee1`, `32d2b46`, `4a81c69`, `bce27c5`) found in git log. `python -m pytest tests/ -q` -> 1453 passed, 1 skipped, 132 subtests. `bash scripts/run_6_gates.sh` -> ALL 6 GATES PASSED.

---
*Phase: 10-run-memory-foundation-shadow-writes*
*Completed: 2026-08-25*
