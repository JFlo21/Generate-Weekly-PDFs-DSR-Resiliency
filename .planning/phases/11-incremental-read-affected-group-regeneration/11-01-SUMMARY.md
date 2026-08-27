---
phase: 11-incremental-read-affected-group-regeneration
plan: 01
subsystem: pipeline_memory
tags: [supabase, postgrest, pipeline_memory, run_ledger, decorated-numerics, tdd]

# Dependency graph
requires:
  - phase: 10-run-memory-foundation-shadow-writes
    provides: "pipeline_memory shadow-write package (writer.py, client.py), run_ledger schema, upsert_rows_bulk/upsert_group_state/run_ledger_finish"
provides:
  - "Caller-parses-then-passes numeric contract: pipeline/orchestrate.py pre-parses decorated Quantity/Units Total Price cells and passes them via __mem_quantity/__mem_units_total_price row keys; pipeline_memory/writer.py never re-parses or falls back to raw cell values"
  - "run_ledger.sheets_changed populated on both the success-path and failure-path run_ledger_finish calls"
  - "docs/run-memory-write-flip-checklist.md — the operator checklist gating the separate, owner-approved RUN_MEMORY_WRITE_ENABLED flip PR"
  - "Dated WR-01 Living Ledger entry recording the silent-data-loss defect class and the caller-parses contract"
affects: ["11-02 (incremental read / capture-time watermark)", "the future owner-gated RUN_MEMORY_WRITE_ENABLED flip PR"]

# Actuals (#2632)
actuals:
  tokens: 7166
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Caller-parses-then-passes: any pipeline_memory write field sourced from a decorated Smartsheet cell must be pre-parsed by the caller (pipeline/orchestrate.py) using the engine's own pipeline.pricing parsers and handed to pipeline_memory via a __mem_* row key; pipeline_memory itself parses nothing and never falls back to a raw cell value, preserving the pipeline_memory-imports-nothing-from-pipeline.* boundary."
    - "Source-inspection regression tests (inspect.getsource(orch) + string/regex anchors) for logic nested deep inside main() that cannot be exercised without a full production session — mirrors the existing AttachmentSideChannelTests pattern rather than inventing a new one."

key-files:
  created:
    - docs/run-memory-write-flip-checklist.md
  modified:
    - pipeline/orchestrate.py
    - pipeline_memory/writer.py
    - tests/test_pipeline_memory_shadow.py
    - memory-bank/living-ledger.md
    - .planning/todos/pending/2026-08-25-run-memory-review-followups.md

key-decisions:
  - "quantity/units_total_price are pre-parsed once by the caller (_run_memory_write_phase) and stashed on __mem_quantity/__mem_units_total_price row-dict keys; _row_to_payload reads only those keys and yields None (clean nullable NUMERIC) rather than falling back to the raw decorated cell, which is exactly the value that fails the Postgres cast and drops a 500-row chunk under fail-open."
  - "sheets_changed is wired as a real run_ledger column (already accepted by _RUN_LEDGER_FINISH_COLUMNS) on BOTH the success-path and the finally-block failure-path run_ledger_finish calls; mem_sheets_written stays untouched as its existing notes-JSON counter — this adds a column, it does not migrate a key."
  - "The success-path run_ledger_finish call site is unreachable in a unit test without running a full production session, so its sheets_changed= wiring is proven structurally via inspect.getsource(orch), mirroring the established AttachmentSideChannelTests pattern in this file; the failure-path call site IS behaviorally exercised end-to-end through the real finally block via the existing RunLedgerFailurePathTests harness."
  - "RUN_MEMORY_WRITE_ENABLED is currently ABSENT from weekly-excel-generation.yml (code default '0' in pipeline/config.py) — the flip checklist documents the change as adding one env-var line to both Generate-reports env: blocks, not toggling an existing '0' to '1'."
  - "IN-01 (upsert_group_state's attachment-preservation COALESCE) is genuinely untestable under SKIP_UPLOAD, so it is deferred to checklist item 2 of the flip document rather than forced into a mock-based unit test that wouldn't prove the real behavior."

requirements-completed: [INC-04]

coverage:
  - id: D1
    description: "A decorated Quantity/Units Total Price cell (e.g. \"12 ea\", \"$1,234.50\") reaches upsert_rows_bulk as a parsed float via __mem_* row keys; a missing pre-parse yields NULL, never a raw string that drops the chunk (WR-01)."
    requirement: "INC-04"
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests"
        status: pass
      - kind: other
        ref: "AST import-boundary check on pipeline_memory/writer.py -> WRITER_BOUNDARY_OK"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_ledger.sheets_changed is populated on both the success-path and failure-path run_ledger_finish calls (WR-04)."
    requirement: "INC-04"
    verification:
      - kind: e2e
        ref: "tests/test_pipeline_memory_shadow.py::RunLedgerFailurePathTests::test_failure_path_finish_includes_sheets_changed"
        status: pass
      - kind: other
        ref: "tests/test_pipeline_memory_shadow.py::RunLedgerSheetsChangedCallSiteTests::test_both_finish_call_sites_pass_sheets_changed (source-inspection proof of the success-path call site)"
        status: pass
    human_judgment: false
  - id: D3
    description: "docs/run-memory-write-flip-checklist.md gates the flip PR on preconditions, the IN-01 upload-enabled control run, the group_state attachment-id proof, and the low-activity comparator rerun; memory-bank/living-ledger.md carries the dated WR-01 entry (append-only, no secrets); the folded todo records resolution; .github/workflows/ is untouched."
    verification:
      - kind: other
        ref: "python content/string checks (CHECKLIST_OK, LEDGER_OK, APPEND_ONLY_OK) run during execution; git diff --exit-code -- .github/workflows/"
        status: pass
    human_judgment: true
    rationale: "The checklist's own content (which env-var line to add, which queries to run) is a judgment call about operational safety on a protected production workflow — Juan reviews the document itself before it governs the real flip PR, even though every mechanical acceptance check (string presence, append-only diff, workflow untouched) passed."

duration: 48min
completed: 2026-08-26
status: complete
---

# Phase 11 Plan 01: Run-Memory Write-Path Preconditions Summary

**Fixed a silent-data-loss defect in the pipeline_memory write path (decorated numerics dropping 500-row chunks), populated `run_ledger.sheets_changed` on both finish paths, and wrote the operator checklist that gates the future `RUN_MEMORY_WRITE_ENABLED` flip PR.**

## Performance

- **Duration:** 48 min (task-1 commit `4323cec` to task-3 commit `a67cb39`; includes a paused tracer human-verify checkpoint between sessions)
- **Started:** 2026-08-26T12:25:14-05:00
- **Completed:** 2026-08-26T13:13:39-05:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Closed WR-01: a decorated `Quantity`/`Units Total Price` cell (`"12 ea"`, `"$1,234.50"`) now reaches `upsert_rows_bulk` as a real parsed float via the caller-parses-then-passes `__mem_quantity`/`__mem_units_total_price` contract, instead of silently dropping the entire 500-row chunk on a Postgres NUMERIC cast failure under the fail-open contract.
- Closed WR-04: `run_ledger.sheets_changed` is now populated on both the success-path and the failure-path `run_ledger_finish` calls in `pipeline/orchestrate.py`, so a run's own record of how much it saw is complete even when it dies mid-session.
- Delivered `docs/run-memory-write-flip-checklist.md`: the six-gate operator checklist Juan works through on the separate, owner-approved PR that flips `RUN_MEMORY_WRITE_ENABLED` on — including the IN-01 upload-enabled control run, the `group_state` attachment-id proof, and the low-activity comparator rerun.
- Appended a dated `[2026-08-26 18:10]` WR-01 entry to `memory-bank/living-ledger.md` recording the silent-data-loss defect class, the caller-parses contract, the `HASH_FIELDS` side effect, and a forward-flag repeating the capture-time watermark rule for plan 11-02.
- Closed the folded todo `.planning/todos/pending/2026-08-25-run-memory-review-followups.md` with a `## Resolution` section covering WR-01, WR-04, and IN-01 (WR-02/WR-03 were already closed).

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end decorated-numeric write — one row, caller to RPC payload (WR-01)** - `4323cec` (fix) — completed in a prior session; NOT re-executed this session, only verified present.
2. **Task 2: Populate run_ledger.sheets_changed on both finish paths (WR-04)** - `0d63073` (test, RED) then `7ffa57a` (feat, GREEN)
3. **Task 3: RUN_MEMORY_WRITE_ENABLED flip checklist, Living Ledger entry, folded-todo resolution (IN-01)** - `a67cb39` (docs)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

_Note: Task 2 (`tdd="true"`) followed RED → GREEN: two failing tests committed first (`0d63073`), confirmed failing via `pytest -k sheets_changed`, then the minimal caller-side fix committed (`7ffa57a`)._

## Files Created/Modified

- `pipeline/orchestrate.py` - Task 1: stashes `__mem_quantity`/`__mem_units_total_price` per row via `pipeline.pricing`'s own parsers. Task 2: both `run_ledger_finish` call sites (success path, failure-path `finally` block) now pass `sheets_changed=_mem_sheets_written` with a comment distinguishing it from the `mem_sheets_written` notes counter.
- `pipeline_memory/writer.py` - Task 1: `_row_to_payload` reads only `__mem_quantity`/`__mem_units_total_price`, never the raw cell; docstring documents the caller-owns-parsing contract and the `HASH_FIELDS` side effect.
- `tests/test_pipeline_memory_shadow.py` - Task 1: 4 new cases in `BulkPayloadContractTests`. Task 2: `RunLedgerFailurePathTests.test_failure_path_finish_includes_sheets_changed` (behavioral, via the real failure-path `finally` block) and the new `RunLedgerSheetsChangedCallSiteTests` class (structural, source-inspection proof both call sites pass `sheets_changed=`).
- `docs/run-memory-write-flip-checklist.md` (new) - Task 3: the 6-item operator checklist gating the `RUN_MEMORY_WRITE_ENABLED` flip PR.
- `memory-bank/living-ledger.md` - Task 3: dated `[2026-08-26 18:10]` WR-01 entry appended at the bottom (append-only, verified via `git diff --numstat`).
- `.planning/todos/pending/2026-08-25-run-memory-review-followups.md` - Task 3: `## Resolution` section added.

## Decisions Made

See `key-decisions` in frontmatter. All five are load-bearing: the caller-parses contract and the `sheets_changed`-is-a-real-column decision are both defect fixes with an explicit rationale for why the "obvious" alternative (parse inside `pipeline_memory`, or fold `sheets_changed` into `notes` like the other counters) was rejected; the source-inspection test decision follows precedent already established in this test file rather than inventing a new pattern; the "flip is an add, not a toggle" and "IN-01 is checklist-gated, not unit-tested" decisions are both honest documentation of real repository state discovered during Task 3, not scope changes.

## Deviations from Plan

None - plan executed exactly as written across all three tasks. Task 1 was completed and committed in a prior session; this session verified `4323cec` was present and did not re-execute it, per the continuation instructions.

## Issues Encountered

None. The one design decision requiring investigation (how to test the success-path `run_ledger_finish` call site, which sits deep inside `main()` and is not reachable without running a full production session) was resolved by discovering and reusing the codebase's own existing convention (`AttachmentSideChannelTests`' `inspect.getsource(orch)` pattern) rather than attempting a costly full-session mock or leaving the success path unverified.

## User Setup Required

None - no external service configuration required. `docs/run-memory-write-flip-checklist.md` documents manual steps for the FUTURE flip PR, which is explicitly out of scope for this plan and requires Juan's separate approval.

## Next Phase Readiness

- All three `RUN_MEMORY_WRITE_ENABLED` flip preconditions from `10-REVIEW.md` (WR-01, WR-02, WR-03, WR-04) are now closed; IN-01 is checklist-gated pending a real upload-enabled control run.
- `pipeline_memory` still imports nothing from `pipeline.*` (AST boundary check passes); `run_summary.json`'s frozen 21-key contract and `.github/workflows/` are untouched.
- Plan 11-02 (incremental read) can proceed; its capture-time watermark rule is already locked in the Phase 11 discuss-phase Living Ledger entry and repeated in this plan's WR-01 entry as a forward-flag.
- No blockers. The `RUN_MEMORY_WRITE_ENABLED` flip itself remains a separate, owner-approved PR — not scheduled by this plan.

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-08-26*

## Self-Check: PASSED

All 6 created/modified files confirmed present on disk; all 5 commits
(`4323cec`, `0d63073`, `7ffa57a`, `a67cb39`, `f2ce4a4`) confirmed present
in `git log --oneline --all`.
