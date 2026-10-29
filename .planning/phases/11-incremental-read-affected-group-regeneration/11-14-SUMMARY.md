---
phase: 11-incremental-read-affected-group-regeneration
plan: 14
subsystem: pipeline-memory
tags: [gap-closure, G-11-37, mechanism-C, upsert_rows_bulk, additive-ddl, owner-gated-apply, tdd]
status: complete

requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "11-13 shadow fallback modelling (serialized wave 4; shares ledger and 11-CONTEXT.md)"
provides:
  - "pipeline_memory/schema.sql: upsert_rows_bulk returns the PRIOR (wr, week_ending) pair when a row's Work Request # changed (additive third UNION branch)"
  - "pipeline_memory/upsert_rows_bulk_prior_pair_migration.sql: FORWARD block == schema.sql, ROLLBACK == verbatim pre-change body; header records APPLIED 20261029205414"
  - "tests/test_upsert_rows_bulk_prior_pair_contract.py + tests/fixtures/incremental/upsert_rows_bulk_pre_g1137.sql"
affects: [11-15]

tech-stack:
  added: []
  patterns:
    - "Protected RPC change: snapshot fixture + RED contract test before the edit, insert-only schema.sql diff, rollback pinned equal to the snapshot, live apply gated on showing the owner the exact SQL"

key-files:
  created:
    - tests/fixtures/incremental/upsert_rows_bulk_pre_g1137.sql
    - tests/test_upsert_rows_bulk_prior_pair_contract.py
    - pipeline_memory/upsert_rows_bulk_prior_pair_migration.sql
  modified:
    - pipeline_memory/schema.sql
    - .planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md
    - memory-bank/living-ledger.md

key-decisions:
  - "Owner (Juan) approved the additive change 2026-10-29 and replied apply-now to the pre-apply SQL checkpoint the same day; D-04 amended in 11-CONTEXT.md (D-04 bullet plus one Protected-areas line)"
  - "Kept the existing second return branch so no previously returned pair disappears; new branch is a strict superset"
  - "tests/test_upsert_rows_bulk_helper2_contract.py not edited: test_rpc_body_lives_only_in_schema_sql asserts only on the helper2 migration file, so no allow-list widening was needed"

duration: ~40min
completed: 2026-10-29

commits: 3
plan_head_before: 7f6317aa663a405eee6fc03a303eec92aa336f39
plan_head_after: c324a3749ef25728cf306e9330a07a886daf10ee
actuals:
  tokens: 14500
  tasks: 3
  commits: 3
---

# Phase 11 Plan 14: upsert_rows_bulk prior-WR pair (G-11-37 mechanism C) Summary

`upsert_rows_bulk` now also returns `(prior wr, prior week_ending)` when a changed row's stored Work Request # differs from its new one, so the old WR's group enters the D-04 candidate; the change is one additive UNION branch and is APPLIED live (migration 20261029205414) after the owner reviewed the exact SQL.

## What was done

- **Task 1 (tracer, TDD):** Snapshotted the verbatim pre-change function block to the fixture, wrote the contract test and saw it fail, then made an insert-only edit to `schema.sql` (8 SQL lines plus a dated comment block: `, rs.wr AS prior_wr` in `prior`, `p.prior_wr,` in `changed`, a new UNION branch gated on `prior_wr IS NOT NULL AND prior_week_ending IS NOT NULL AND prior_wr IS DISTINCT FROM wr`). Created the standalone migration with FORWARD (equal to the schema.sql block) and a commented ROLLBACK (equal to the snapshot). Appended the dated D-04 amendment. Commits: 71c7b4e (RED), a877685 (GREEN).
- **Task 2 (blocking-human checkpoint):** the exact FORWARD SQL and rollback were shown to Juan; answer `apply-now`, recorded 2026-10-29. Applied by the orchestrator via Supabase `apply_migration` (name `upsert_rows_bulk_prior_pair`, project poeyztlmsawfoqlanucc), version 20261029205414 (2026-10-29 20:54:14Z). This executor had no live access and did not call it.
- **Task 3:** recorded the applied status in the migration header, appended the living-ledger entry, ran the full gates. Commit c324a37.

## Evidence

- **RED (before the schema.sql edit):** 7 of 9 new contract tests failed (prior-WR branch, CTE columns, insert-only check, and the 4 migration-file tests); the legacy-branch and signature/search_path/grant tests passed.
- **GREEN:** both contract files 21 passed; `tests/test_incremental_read.py -k additive_only` passed (schema.sql diff is 18 insertions, 0 deletions).
- **Full suite:** `pytest tests/ -q` 2556 passed, 1 skipped, 664 subtests. `SMARTSHEET_API_TOKEN= bash scripts/run_6_gates.sh`: ALL 6 GATES PASSED.
- **Scope guards:** `git diff HEAD -- pipeline/ pipeline_memory/{writer,reader,client}.py generate_weekly_pdfs.py` empty; `git diff <merge-base origin/master> -- generate_weekly_pdfs.py .github/workflows/` empty.
- **Live post-apply verification (read-only, by the orchestrator):** `pg_get_functiondef` contains `prior_wr`; live prosrc md5 (comments and whitespace stripped) b96af4f7de8fc75592e86e09be54caec equals the same normalization of the local FORWARD block (pre-apply live md5 f052e3edda479c3a6b0271d1e1c01d6e equalled the rollback snapshot); `service_role` EXECUTE true; `search_path=""` pinned; `get_advisors(security)` shows no finding on `pipeline_memory`.

## Deviations from Plan

None - plan executed as written. One note: the plan said "a new UNION branch"; the branch is 6 inserted lines (including its leading `UNION`), so the insert-only diff is 8 SQL lines in total, which the contract test pins exactly.

## Auth gates

None. Task 2 was a planned decision checkpoint, not an auth gate.

## Known Stubs

None.

## Threat Flags

None. The only trust-boundary change (repo DDL to live project) is the one the threat model covers (T-11-56, T-11-57), mitigated as planned.

## Self-Check: PASSED

- Files exist: fixture, contract test, migration, SUMMARY target directory.
- Commits 71c7b4e, a877685, c324a37 are ancestors of HEAD.
