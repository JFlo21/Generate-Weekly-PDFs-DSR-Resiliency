---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 03
subsystem: billing-attribution
tags: [supabase, postgrest, billing_audit, sql, ddl, rpc, backfill, checkpoint]

# Dependency graph
requires:
  - phase: 12-01
    provides: "scripts/backfill_claim_time_attribution.py — the --apply write path this RPC's contract must match verbatim"
provides:
  - "billing_audit/own03_backfill_attribution.sql — reviewable, owner-applied SQL: dated backup table, backfill_source/backfill_run_id provenance columns, billing_audit.is_sentinel_value, billing_audit.backfill_attribution(p_rows jsonb) RPC"
  - "billing_audit/schema.sql backfill_attribution (RPC) contract-as-comment block"
  - "tests/test_own03_backfill_sql_contract.py — structural contract test pinning the RPC's security-critical shape"
affects: [12-06]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 21000
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three explicit static per-role UPDATE statements inside one WITH-clause RETURN QUERY (no dynamic SQL, no EXECUTE format), each RETURNING the keys it actually touched so downstream classification reflects the pre-update sentinel predicate rather than a post-hoc value comparison"

key-files:
  created:
    - billing_audit/own03_backfill_attribution.sql
    - tests/test_own03_backfill_sql_contract.py
  modified:
    - billing_audit/schema.sql

key-decisions:
  - "backfill_attribution's three per-role UPDATEs are expressed as data-modifying CTEs inside one WITH ... RETURN QUERY statement (each with its own RETURNING) rather than three standalone UPDATEs followed by a separate classification query — this makes the updated/skipped_real_name/skipped_no_row classification derive from the PRE-update sentinel predicate (what the plan's English description asks for: 'skipped_real_name for payload rows whose PK exists but whose role column failed the sentinel predicate') instead of a POST-update value comparison, which would misclassify an idempotent re-run of an already-correct row as 'updated'."
  - "The RPC's per-row validation loop (role/value/backfill_source) raises immediately (RAISE EXCEPTION) on any offending row, aborting the whole call so a malformed p_rows chunk fails loudly (surfaces as the Python caller's exit 6) rather than partially applying — matches the plan's 'never coerce and never fall through' instruction."

requirements-completed: []  # Plan halted at Task 3 (blocking-human decision) before the live apply (Task 4) — OWN-01/OWN-03 are NOT marked complete by this partial run. Tasks 1-2 (SQL authored + documented) are done; the live Supabase objects do not exist yet.

coverage:
  - id: D1
    description: "billing_audit/own03_backfill_attribution.sql is a reviewable, owner-applied file authored end-to-end (backup table, provenance columns + CHECK, sentinel predicate, sentinel-only RPC, service_role-only grant) with a structural contract test pinning its security-critical shape"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_own03_backfill_sql_contract.py (14 tests, 12 subtests, all pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "billing_audit/schema.sql documents the backfill_attribution RPC's full contract (seven-field p_rows payload, three-value result, sentinel-or-NULL-only server-side invariant, service_role-only grant) and D-12-A (no wr_week_ownership table) without asserting the opaque attribution_snapshot table's DDL"
    requirement: "OWN-01"
    verification:
      - kind: unit
        ref: "python -m pytest tests/ -q (2012 passed, 1 skipped, 377 subtests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The one-way Supabase DDL apply (Task 3 decision, Task 4 live apply) requires Juan's explicit authorization and hands-on execution — this plan halts here by design"
    human_judgment: true
    rationale: "Task 3 is a checkpoint:decision with gate=\"blocking-human\" authorizing an ADD COLUMN against a production, data-team-owned billing table; Task 4 is a checkpoint:human-verify with gate=\"blocking-human\" where Juan runs the SQL himself in the Supabase SQL editor. Neither step is automatable or auto-approvable in any mode, including auto-mode (checkpoints.md golden rule 6)."

duration: ~18min (Tasks 1-2 only; halted before Tasks 3-4)
completed: 2026-09-03
status: halted
---

# Phase 12 Plan 03: Owner-Deployed OWN-03 Backfill SQL (HALTED at Task 3 decision checkpoint) Summary

**Authored the reviewable, owner-applied `backfill_attribution` RPC SQL file (backup table, provenance columns, sentinel-only server-side guard) and its `schema.sql` contract documentation; halted before the live Supabase apply pending Juan's explicit authorization.**

## Performance

- **Duration:** ~18 min (Tasks 1-2; Tasks 3-4 not started — this plan is PAUSED, not complete)
- **Started:** 2026-09-03 (session start)
- **Halted at:** 2026-09-03T17:26:08Z
- **Tasks:** 2 of 4 completed (Task 3 is the current blocking checkpoint)
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- `billing_audit/own03_backfill_attribution.sql`: a six-step (STEP 0-5), idempotent, top-to-bottom-runnable SQL file for Juan. STEP 0 gives an `information_schema.columns` query plus a single `ADJUST HERE` correction region (in STEP 4) for if the live write-side role column names differ from the assumed `frozen_primary`/`frozen_helper`/`frozen_vac_crew`. STEP 1 creates the dated `attribution_snapshot_backup_<YYYYMMDD>` table (backup-before-write). STEP 2 adds `backfill_source`/`backfill_run_id` with a four-value CHECK matching the vocabulary `pipeline_memory.row_event.source`/`group_state.source` already use. STEP 3 defines `billing_audit.is_sentinel_value` as the exact SQL twin of `billing_audit.writer.is_sentinel_claimer`. STEP 4 defines the sentinel-only `billing_audit.backfill_attribution(p_rows jsonb)` RPC: three explicit static per-role UPDATE statements (no dynamic SQL, no `EXECUTE`-format pattern), each gated by `is_sentinel_value` in its `WHERE` so a real name can never be overwritten server-side, classified via `RETURNING`-captured keys rather than a post-hoc value comparison. STEP 5 grants `EXECUTE` to `service_role` only and reminds the operator to reload the PostgREST schema cache.
- `billing_audit/schema.sql`: new `backfill_attribution (RPC)` contract-as-comment block, in the same voice/restraint as the existing `freeze_attribution` block, documenting the RPC's I/O contract, the two new provenance columns, and D-12-A — without asserting the opaque `attribution_snapshot` table's DDL.
- `tests/test_own03_backfill_sql_contract.py`: 14 tests / 12 subtests pinning the SQL's security-critical shape — required content (typed column list, `is_sentinel_value`, `SET search_path`, `service_role` grant, `DROP FUNCTION IF EXISTS`), prohibited content (zero `EXECUTE format`, `TO anon`, `TO authenticated`, `last_known_before_week`), the STEP 0 confirmation query + `ADJUST HERE` marker, and sentinel-vocabulary parity with `billing_audit.writer._SENTINEL_CLAIMERS`.
- Full repo suite: 2012 passed, 1 skipped, 377 subtests — no regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author the owner-deployed backfill_attribution SQL file** - `3fbd7bf` (feat)
2. **Task 2: Add the backfill_attribution contract-as-comment block to billing_audit/schema.sql** - `f1a1099` (docs)
3. **Task 3: DECISION — authorize the one-way Supabase DDL apply** - `gate="blocking-human"` — **AWAITING JUAN'S DECISION**, halted here.
4. **Task 4: Juan applies the SQL and confirms the live schema** - not started (blocked by Task 3).

**Plan metadata:** this SUMMARY.md commit follows.

## Files Created/Modified

- `billing_audit/own03_backfill_attribution.sql` - owner-applied SQL: backup table, provenance columns, sentinel predicate, sentinel-only RPC.
- `billing_audit/schema.sql` - new `backfill_attribution (RPC)` contract-as-comment block.
- `tests/test_own03_backfill_sql_contract.py` - structural contract test over the SQL file's text.

## Decisions Made

See `key-decisions` in frontmatter: (1) the RPC's three per-role UPDATEs are data-modifying CTEs inside one `WITH ... RETURN QUERY` statement (each with its own `RETURNING`) so classification derives from the pre-update sentinel predicate, not a post-hoc value comparison that would misclassify an idempotent re-run; (2) the validation loop raises immediately on any offending row, aborting the whole call.

## Deviations from Plan

None - plan Tasks 1-2 executed exactly as written. No Rule 1-3 auto-fixes were needed.

## Issues Encountered

None. Both automated `<verify>` commands (`python -m pytest tests/test_own03_backfill_sql_contract.py -q` and `python -m pytest tests/ -q`) passed on the first attempt.

## Checkpoint: Task 3 — DECISION Awaiting Juan

**Decision:** Apply `billing_audit/own03_backfill_attribution.sql` to the production Supabase project, adding two columns to the data-team-owned `billing_audit.attribution_snapshot` table.

**Gate:** `blocking-human` — never auto-approved, in any mode (checkpoints.md golden rule 6). This executor did NOT proceed to Task 4 and made zero Supabase calls.

**Context:** The file creates four live objects: `attribution_snapshot_backup_<YYYYMMDD>`, the two provenance columns `backfill_source`/`backfill_run_id`, the predicate `billing_audit.is_sentinel_value`, and the RPC `billing_audit.backfill_attribution`. The two `ADD COLUMN IF NOT EXISTS` statements and the `CREATE TABLE ... AS SELECT` are the one-way parts: a column add on a data-team-owned production billing table is not cleanly revertible without a coordinated `ALTER TABLE ... DROP COLUMN`. The RPC and the predicate are freely droppable. No row of `attribution_snapshot` is modified by this file — the write happens later, in plan 12-06, behind its own decision checkpoint. Open risk (RESEARCH.md Pitfall 1 / Open Question 2): `attribution_snapshot`'s write-side column names are not verifiable from this repo; STEP 0 of the file resolves that before anything is applied.

**Options:**
1. **approve** — apply as written after running STEP 0. Pros: unblocks the OWN-03 write path; backup table and provenance columns exist before any row is touched. Cons: adds two columns to a production billing table; dropping them later is a second coordinated change.
2. **approve-with-correction** — Juan supplies the real write-side column names (if STEP 0 disagrees with the `frozen_primary`/`frozen_helper`/`frozen_vac_crew` assumption) and the executor edits only the `ADJUST HERE` region before he applies. Pros: handles the column-name-mismatch case cleanly. Cons: requires one extra round trip between STEP 0 and STEP 4.
3. **hold** — do not apply. Pros: zero production change; plans 12-04 and 12-05 still ship the source-5 job and documentation. Cons: Phase 12 closes with the 93 WRs unremediated; plan 12-06 is blocked.

**Resume signal:** Reply `approve`, `approve-with-correction` (and paste the three real column names), or `hold`.

**Status:** No response received yet in this execution. `12-03-SUMMARY.md` is being committed now (per the atomic-close-out invariant for a designed checkpoint stop) so a continuation agent has the completed-tasks state on resume. Task 4 (`gate="blocking-human"`, the live Supabase apply + confirmation) is blocked on this decision and has not started.

## User Setup Required

None yet — Task 4 (when unblocked) requires Juan to run the SQL by hand in the Supabase SQL editor; this executor performs none of those steps itself (per the plan's precondition and the production-guardrails Supabase rule).

## Next Phase Readiness

- Tasks 1-2 are complete and merge-ready: the SQL file and its schema.sql documentation exist, are tested, and do not touch production.
- Task 3 (decision) and Task 4 (live apply + confirmation) remain blocked pending Juan's explicit reply.
- Plan 12-06 (the human-checkpoint live-apply run against real sentinel rows) depends on Task 4 completing first — this backup table and RPC must exist in Supabase before 12-06's `--apply` precondition probe can succeed.
- No known stubs. No skipped tests introduced by this plan. No unrun automated `<verify>` commands — both were executed and passed.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Halted: 2026-09-03 (awaiting Task 3 decision)*

## Self-Check: PASSED

- FOUND: `billing_audit/own03_backfill_attribution.sql`
- FOUND: `tests/test_own03_backfill_sql_contract.py`
- FOUND: `billing_audit/schema.sql` (modified, contains `backfill_attribution (RPC)` banner)
- FOUND commit: `3fbd7bf` (Task 1)
- FOUND commit: `f1a1099` (Task 2)
- VERIFIED: `python -m pytest tests/test_own03_backfill_sql_contract.py -q` — 14 passed, 12 subtests passed
- VERIFIED: `python -m pytest tests/ -q` — 2012 passed, 1 skipped, 377 subtests passed

## Pre-checkpoint review fixes

An independent Opus production-risk review of Tasks 1-2 (before merge and before
the Task 3 decision) returned FIX-FIRST; one fix round, commit `1e1c28d`:

- **HIGH — PII in RAISE:** the sentinel-refusal exception interpolated the proposed
  name; the message now carries role / wr / week_ending / smartsheet_row_id only.
- **MEDIUM — whitespace drift:** `is_sentinel_value` trimmed spaces only (`btrim`)
  while `is_sentinel_claimer` strips all whitespace; the predicate now trims
  `E' 	
'` before every blank / `#`-prefix / vocabulary check.
- **LOW — OUT-param shadowing:** `#variable_conflict use_column` added as the first
  line of the RPC body.
- **Test gap:** `ApplyPayloadSqlParityTests` parses the seven `jsonb_to_recordset`
  columns and the CASE result vocabulary from the SQL text and pins them against
  `_build_apply_payload` output keys and `_APPLY_RESULT_KEYS`. Suite: 2014 passed.

Carried to the Task 3 decision / plan 12-06 (not code changes in this plan):
the RPC is SECURITY INVOKER and the file grants EXECUTE only — confirm the applying
role holds UPDATE on `billing_audit.attribution_snapshot`; the script's backup-table
probe is same-UTC-day only (`attribution_snapshot_backup_<today>`), so apply STEP 1
and run `--apply` on the same UTC day or add a `--backup-table` override in 12-06;
STEP 0 column-name verification does not fail closed — run it first, by hand.
