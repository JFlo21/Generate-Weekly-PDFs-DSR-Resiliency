---
phase: 10-run-memory-foundation-shadow-writes
plan: 01
subsystem: database
tags: [supabase, postgres, pipeline_memory, shadow-write, fail-open, run_ledger, billing-pipeline]

# Dependency graph
requires:
  - phase: 09-engine-modularization-pipeline-package-split
    provides: the pipeline/ package (config.py, orchestrate.py) this plan additively wires into
provides:
  - pipeline_memory/ package (client, writer, schema.sql) with an independent Supabase client, kill switch, and circuit breaker
  - run_ledger wired end-to-end from pipeline/orchestrate.py::main(), off by default, fail-open
  - Complete versioned DDL for all five MEM-01 tables, service-role-only RLS, upsert_rows_bulk RPC, pg_cron retention
  - HASH_FIELDS / compute_content_hash() / build_row_payload() / upsert_rows_bulk() Python contract for row-level writes
affects: [10-02-per-row-write-path, 10-03-group-state-and-sheet-registry, 10-06-apply-schema-and-control-run]

# Actuals (#2632)
actuals:
  tokens: 25415
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Independent shadow-write package mirroring billing_audit/ shape (client.py/writer.py/schema.sql) with its OWN client cache, kill switch, and circuit breaker -- zero import from the sibling package"
    - "Fail-open write contract: client-none guard -> flag guard -> build payload -> with_retry-wrapped call -> counter bump -> typed return, NEVER raises"
    - "Defence-in-depth double gate: pipeline.config.RUN_MEMORY_WRITE_ENABLED (orchestrator's gate, read once) + pipeline_memory.client._write_enabled() (writer's own gate, re-read live) -- both must be true for a write"

key-files:
  created:
    - pipeline_memory/__init__.py
    - pipeline_memory/client.py
    - pipeline_memory/writer.py
    - pipeline_memory/schema.sql
    - tests/test_pipeline_memory_shadow.py
  modified:
    - pipeline/config.py
    - pipeline/orchestrate.py

key-decisions:
  - "pipeline_memory/client.py imports nothing from billing_audit -- own module-level _client_cache/_global_disable_reason/_open_circuits so a pipeline_memory-only PostgREST misconfiguration can never disable the shipped attribution/hash-store writer (10-RESEARCH.md Pitfall 5)"
  - "row_state.foreman_observed (and the whole HASH_FIELDS contract) reads the RAW Foreman column, never __effective_user -- the exact historical defect that corrupted 93 WRs / 5,824 rows in billing_audit.attribution_snapshot"
  - "EXECUTION_TYPE env var (already computed by the workflow's 'Determine execution type' step and consumed by scripts/notion_sync.py) is read directly for run_ledger.notes.execution_type instead of re-deriving the manual/production_frequent/weekend_maintenance/weekly_comprehensive classification in Python"
  - "group_state PRIMARY KEY promoted to include target_sheet_id (assumption_delta_decision) so a reduced_sub fan-out's two upload legs each get their own row instead of the second overwriting the first's attachment_id"
  - "sheet_registry.kind CHECK drops the design draft's 'vac_crew' value -- VAC-crew rows are a row-level, column-presence-driven flag on primary/subcontractor sheets, not a discovered sheet-id bucket, so that value could never be written"
  - "pipeline_memory/client.py's postgrest/httpx missing-dependency fallback uses a bare '# type: ignore' instead of billing_audit/client.py's '# type: ignore[assignment]' -- the narrower code doesn't actually cover mypy's real [misc] finding (already-accepted debt in the frozen baseline); new code should not reproduce that debt"

requirements-completed: [MEM-01, MEM-03]

coverage:
  - id: D1
    description: "pipeline_memory package (client.py, writer.py, __init__.py) with an independent Supabase client, retry/circuit-breaker, and run-global kill switch, isolated from billing_audit"
    requirement: MEM-03
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::RunLedgerTracerTests, ClientTestModeTests, FailOpenAndIsolationTests"
        status: pass
      - kind: other
        ref: "python -c AST import-isolation check on pipeline_memory/client.py -> CLIENT_ISOLATED_OK"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_ledger wired end-to-end from pipeline/orchestrate.py::main() (start hook after run-start log event, finish hook before run_summary.json write), off by default, fail-open, adds no key to the frozen 21-key run_summary.json"
    requirement: MEM-03
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::RunLedgerTracerTests::test_start_then_finish_produce_exactly_two_run_ledger_upserts"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- generate_weekly_pdfs.py tests/golden/run_summary_baseline.json .github/workflows/"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh"
        status: pass
    human_judgment: false
  - id: D3
    description: "pipeline_memory/schema.sql: complete, reapply-safe, versioned DDL for all five MEM-01 tables with service-role-only RLS, the upsert_rows_bulk RPC, and a bounded pg_cron 24-month retention job"
    requirement: MEM-01
    verification:
      - kind: other
        ref: "structural greps: DDL_STRUCTURE_OK, SCOPE_OK, RLS_POLICIES=5, RLS_ENABLED=5 (see plan 10-01 Task 2 <verify>)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Python<->SQL column contract mechanically locked (run_ledger payload keys are a subset of schema.sql's column set) and MEM-02 row-level edge invariants (empty input, single-element input, blank-Foreman never a placeholder, hash order-stability, row_id adjacency, counter isolation, no PII in writer logs) proven against a real HASH_FIELDS/build_row_payload/upsert_rows_bulk contract"
    requirement: MEM-01
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::SchemaColumnContractTests, BulkPayloadContractTests, CounterAndPiiDisciplineTests"
        status: pass
    human_judgment: false

duration: ~50min
completed: 2026-08-25
status: complete
---

# Phase 10 Plan 01: Run-Memory Foundation (shadow writes) Summary

**New `pipeline_memory` Supabase package with its own client/kill-switch/circuit-breaker, `run_ledger` wired end-to-end from `pipeline/orchestrate.py` behind a default-OFF flag, and the complete versioned DDL for all five MEM-01 tables plus the `upsert_rows_bulk` RPC and row-payload/content-hash Python contract.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-08-25T15:41Z (approx.)
- **Completed:** 2026-08-25T15:59Z
- **Tasks:** 3
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments
- `pipeline_memory/client.py` -- independent Supabase client construction, PostgREST error classification, per-run kill switch, and per-op circuit breaker, with zero import from `billing_audit` (proven via an AST-based isolation gate)
- `pipeline_memory/writer.py` -- fail-open `run_ledger_start`/`run_ledger_finish` writer, `resolve_run_id()`, plus the row-level `HASH_FIELDS`/`compute_content_hash`/`build_row_payload`/`upsert_rows_bulk` contract plan 10-02 builds its per-sheet loop on top of
- `pipeline/config.py` -- `RUN_MEMORY_WRITE_ENABLED`/`RUN_MEMORY_WRITE_MAX_MINUTES`/`RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC`/`RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN` flag family, default OFF
- `pipeline/orchestrate.py` -- two additive, guarded, try/except-wrapped hooks into `main()` (post run-start log event; pre `run_summary.json` write) that never touch the frozen 21-key contract
- `pipeline_memory/schema.sql` -- the complete, reapply-safe DDL for `sheet_registry`, `row_state`, `row_event`, `group_state`, `run_ledger`, the `upsert_rows_bulk` RPC (typed `jsonb_to_recordset`, server-side hash diff, `SET search_path = ''`), service-role-only RLS with explicit anon/authenticated REVOKE, and a bounded `pg_cron` 24-month retention job
- `tests/test_pipeline_memory_shadow.py` -- 19 tests: the six required Task 1 behavior tests (tracer, flag-off no-op, TEST_MODE no-op, PGRST106 fail-open, cross-feature isolation, `resolve_run_id()`), plus Task 3's schema-column contract test and five MEM-02 edge invariants

## Task Commits

Each task was committed atomically (Task 1 is `tdd="true"`, so it has a RED test commit followed by a GREEN feat commit):

1. **Task 1: End-to-end `run_ledger` write** - `3d416d6` (test, RED) + `f1cd223` (feat, GREEN)
2. **Task 2: Author the complete versioned `pipeline_memory` DDL** - `6f45e47` (feat)
3. **Task 3: Lock the Python-to-SQL column contract and edge invariants** - `1131edc` (test)

## TDD Gate Compliance

Task 1 (`tdd="true"`) followed RED -> GREEN:
- RED gate: `3d416d6` (`test(10-01): add failing test for run_ledger shadow-write path`). Verified by temporarily moving the `pipeline_memory/` package aside and confirming all 8 tests failed with `ModuleNotFoundError` before writing any implementation (see Issues Encountered).
- GREEN gate: `f1cd223` (`feat(10-01): wire run_ledger shadow-write path end-to-end`), after which all 8 tests passed.
- No REFACTOR commit was needed (no post-GREEN cleanup changed behavior).

## Files Created/Modified
- `pipeline_memory/__init__.py` - package docstring pointing at `schema.sql` as the DDL source of truth; writer re-export
- `pipeline_memory/client.py` - independent Supabase client, retry/classification/kill-switch/circuit-breaker, `_write_enabled()` live-read gate
- `pipeline_memory/writer.py` - `run_ledger_start`/`run_ledger_finish`/`resolve_run_id`/`get_counters`; `HASH_FIELDS`/`compute_content_hash`/`build_row_payload`/`upsert_rows_bulk`
- `pipeline_memory/schema.sql` - the five MEM-01 tables, RLS, `upsert_rows_bulk` RPC, pg_cron retention
- `pipeline/config.py` - `RUN_MEMORY_WRITE_*` flag family (default OFF)
- `pipeline/orchestrate.py` - `_mem_writer` import, hoisted memory counters + `_mem_run_id`, two guarded hook calls
- `tests/test_pipeline_memory_shadow.py` - 19 self-contained shadow-layer characterization tests

## Decisions Made
- See `key-decisions` in frontmatter. All five are load-bearing for correctness/security and are documented inline in the code they govern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong mypy `type: ignore` code in `pipeline_memory/client.py`**
- **Found during:** Task 1, running `bash scripts/run_6_gates.sh` Gate 4
- **Issue:** Copying `billing_audit/client.py`'s `_PGAPIError = None  # type: ignore[assignment]` pattern verbatim produced a NEW, uncovered mypy `[misc]` ("Cannot assign to a type") finding at two lines not present in `tests/golden/mypy_baseline.txt` (65 -> 67 error lines), failing Gate 4's "no increase vs. baseline" check. The identical pattern in `billing_audit/client.py` is already-accepted debt (present in the frozen baseline) -- new code should not reproduce it.
- **Fix:** Changed both `# type: ignore[assignment]` comments to a bare `# type: ignore` (which mypy's actual `[misc]` code needs), with a comment explaining why.
- **Files modified:** `pipeline_memory/client.py`
- **Verification:** `python -m mypy generate_weekly_pdfs.py audit_billing_changes.py billing_audit pipeline` -> 65 lines, matching `tests/golden/mypy_baseline_count.txt` exactly; `bash scripts/run_6_gates.sh` Gate 4 passes.
- **Committed in:** `f1cd223` (Task 1 GREEN commit)

**2. [Rule 2 - Missing critical functionality] Added the row-payload/content-hash Python contract in Task 3**
- **Found during:** Task 3, writing the plan's own required edge-invariant tests
- **Issue:** Task 3's `<action>` text requires tests against "the writer's bulk entry point" (empty-input zero-calls, single-element one-call, blank-Foreman placeholder-free, hash order-stability, row_id adjacency) and a payload with a stable `content_hash` -- but neither Task 1 nor Task 2 (nor this plan's own `<artifacts_produced>` manifest) ships any row-level Python symbol; that work is explicitly assigned to plan 10-02 in this plan's `source_coverage_audit` table ("MEM-02 per-row upsert... | 10-02"; "Pitfall 4 chunking... | 10-02 Task 2"). Writing these tests against nothing would leave Task 3's own stated acceptance criteria ("Tests exist and pass for: empty input...") unsatisfiable.
- **Fix:** Added a MINIMAL, real (not test-local-mock) `HASH_FIELDS` tuple, `compute_content_hash()`, `build_row_payload()`, and an unchunked `upsert_rows_bulk()` bulk entry point to `pipeline_memory/writer.py` -- explicitly scoped via docstring as "the payload-builder + single-call RPC wrapper only"; per-sheet chunking for the largest sheets (10-RESEARCH.md Pitfall 4), the per-sheet loop, its own time sub-budget, and the `pipeline/orchestrate.py` wiring remain plan 10-02's job and are NOT added here. This satisfies Task 3's literal test requirements (which explicitly test call-count behavior against a fake Supabase client, requiring real client-interaction semantics) while avoiding preempting plan 10-02's chunking/orchestration design decisions.
- **Files modified:** `pipeline_memory/writer.py`, `tests/test_pipeline_memory_shadow.py`
- **Verification:** `python -m pytest tests/test_pipeline_memory_shadow.py -q` -> 19 passed; `python -m pytest tests/ -q` -> 1407 passed, 1 skipped, 132 subtests; `bash scripts/run_6_gates.sh` -> all 6 gates pass.
- **Committed in:** `1131edc` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical functionality)
**Impact on plan:** Both were necessary for the plan's own `<verify>`/`<acceptance_criteria>` blocks to pass. No scope creep beyond what Task 3's action text and acceptance criteria explicitly require; plan 10-02 should REUSE (not reimplement) `HASH_FIELDS`/`compute_content_hash`/`build_row_payload`/`upsert_rows_bulk` from `pipeline_memory/writer.py` rather than duplicating the contract.

## Issues Encountered

**RED-phase verification for Task 1's TDD gate.** Because the plan's `<execution_context>` gave a fully-specified `<interfaces>`/`<action>` contract, the test file and the implementation were designed together rather than strictly test-first. To honor the RED gate honestly rather than fabricate it, the `pipeline_memory/` package was temporarily moved aside (`mv pipeline_memory pipeline_memory.__red_hidden`, plain filesystem move, no git operation) immediately after writing `tests/test_pipeline_memory_shadow.py`; `pytest` confirmed all 8 tests failed with `ModuleNotFoundError`; the package was restored and the suite re-run to confirm GREEN, before either commit was made. Resolved cleanly -- no lasting effect.

**`resolve_run_id()`'s "local-" fallback test was initially too strict.** The first version of `test_neither_set_returns_unique_local_prefixed_value` asserted two back-to-back calls produce different values, which collided on a fast host (both landed in the same microsecond). The mirrored derivation (`pipeline/orchestrate.py`'s exact fallback formula) is only ever called once per real run, so cross-call uniqueness isn't an actual guarantee worth enforcing; the test was corrected to assert the derivation's FORMAT (regex + calendar-date check) instead of forcing artificial collision-avoidance logic into production code that must otherwise mirror the original exactly. Resolved before the first commit.

## User Setup Required

None - no external service configuration required this plan. `pipeline_memory/schema.sql` is authored and version-controlled but **not applied** to any Supabase project; applying it (plus the PostgREST "Exposed schemas" + "Reload schema cache" steps) is an explicit operator checkpoint in plan 10-06 Task 2, not this plan.

## Next Phase Readiness

- `pipeline_memory/client.py` and `pipeline_memory/writer.py` give plan 10-02 a proven, independently-tested fail-open write path to extend (per-sheet loop, chunking for the largest sheets, its own time sub-budget, `pipeline/orchestrate.py` wiring for the row-level path).
- `pipeline_memory/schema.sql` is complete for all five MEM-01 tables; plan 10-06 Task 2 still needs to apply it to the live Supabase project and perform the PostgREST exposure step before any shadow write can actually reach the database.
- `RUN_MEMORY_WRITE_ENABLED` stays OFF in code; no `.github/workflows/*` file was touched this plan, so production behavior is provably unchanged (`git diff --exit-code -- generate_weekly_pdfs.py .github/workflows/ requirements.txt tests/golden/run_summary_baseline.json billing_audit/` is clean, and all 6 gates + the full 1407-test suite pass).
- No blockers for plan 10-02.

## Self-Check: PASSED

All created files found on disk (`pipeline_memory/__init__.py`, `pipeline_memory/client.py`,
`pipeline_memory/writer.py`, `pipeline_memory/schema.sql`, `tests/test_pipeline_memory_shadow.py`,
`pipeline/config.py`, `pipeline/orchestrate.py`, this SUMMARY.md). All four task commits
(`3d416d6`, `f1cd223`, `6f45e47`, `1131edc`) found in git log.

---
*Phase: 10-run-memory-foundation-shadow-writes*
*Completed: 2026-08-25*
