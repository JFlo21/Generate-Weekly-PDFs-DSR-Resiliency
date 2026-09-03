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

requirements-completed: [OWN-01, OWN-03]  # This plan's contribution: the live Supabase objects exist as of 2026-09-03 (Juan applied the SQL by hand and replied `approved`); OWN-03's live remediation itself finishes in 12-06.

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
status: complete
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
3. **Task 3: DECISION — authorize the one-way Supabase DDL apply** - `gate="blocking-human"` — **DECIDED 2026-09-03: `approve`** (see Checkpoint below).
4. **Task 4: Juan applies the SQL and confirms the live schema** - `gate="blocking-human"` — **APPROVED 2026-09-03** (see "Task 4 — APPROVED" below).

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

**Status (superseded):** No response was received in the original execution; the SUMMARY was committed at the checkpoint stop.

**Decision recorded 2026-09-03 (post wave-2 merge, orchestrator session):** Juan selected option **`approve`** — verbatim
selection from the structured checkpoint prompt: `approve (Recommended)` ("Apply as written after you run STEP 0 and
confirm the three frozen_* column names and the UPDATE grant"). No column-name correction supplied, so the `ADJUST HERE`
region of `billing_audit/own03_backfill_attribution.sql` is unchanged. Task 3 acceptance criteria met; the SQL file is
not edited by this decision.

## Checkpoint: Task 4 — human-verify awaiting Juan's apply

**Gate:** `blocking-human`. Nothing in this repo executes the SQL; Juan runs
`billing_audit/own03_backfill_attribution.sql` step by step in the Supabase SQL editor and reports the seven answers
from the plan's `<how-to-verify>` step 7: (1) the STEP 0 write-side role column names, (2) the exact backup table name
`attribution_snapshot_backup_<YYYYMMDD>` and its row count, (3) that the count equals the live `attribution_snapshot`
count, (4) STEP 2 shows `backfill_source` / `backfill_run_id` in the STEP 0 output, (5) the STEP 3 spot check
`true, true, false`, (6) STEP 4/5 applied + `NOTIFY pgrst, 'reload schema';`, (7) the STEP 6 no-op RPC call returned
`skipped_no_row` with zero rows carrying a non-null `backfill_run_id`.

**Pre-apply reminders (Opus review carry-overs):** the RPC is SECURITY INVOKER and the file grants EXECUTE only — confirm
the applying role also holds UPDATE on `billing_audit.attribution_snapshot`; the 12-01 `--apply` backup-table probe is
same-UTC-day only, so create the backup and run the 12-06 apply on the same UTC day; STEP 0 does not fail closed on
column names — read its output before STEP 4.

**Resume signal:** the seven answers, then `approved` — or the failing STEP. The continuation transcribes them here
verbatim; the recorded backup table name is the exact string plan 12-06's precondition probe looks for.

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


### Vocabulary extension for source 5 (`f3b6db3`)

The Opus review of plan 12-04 flagged that source 5 tagged its proposals `operator`
(human-entered) although they are a machine inference from Smartsheet cell history.
Orchestrator decision: add a fifth provenance tag, `backfill_cell_history`, to BOTH
accepted-value lists in this file (the STEP 2 CHECK constraint and the RPC guard) and
to the schema.sql contract comment; the contract test now parses both lists and pins
the five-tag set. A commented re-apply snippet (DROP CONSTRAINT IF EXISTS + ADD)
covers an environment where STEP 2 already ran with the four-value list. This is a
vocabulary decision for the owner to confirm at the Task 3 checkpoint before applying.

## Integration review fixes (Opus, whole-branch pass, 2026-09-03)

The pre-PR Opus integration review of the merged branch returned **SHIP** with two MEDIUM items in this
plan's SQL, both fixed before Juan's Task 4 apply (the SQL is idempotent; if STEP 0/2/4 were already run from
the earlier file version, re-run STEP 0b, the STEP 2 VERIFY query and STEP 4 — `CREATE OR REPLACE`):

- **MEDIUM-1** `attribution_snapshot` uniqueness on `(wr, week_ending, smartsheet_row_id)` was never checked;
  duplicate key rows would make the RPC's `UNION ALL`ed `RETURNING` sets fan the result out past `p_rows`, and
  the 12-01 CLI would count the chunk as failed (exit 6) after the UPDATEs committed. Fix: `updated_keys` now
  uses `UNION` (dedup), and a mandatory **STEP 0b** duplicate-key probe must return zero rows before STEP 4.
- **MEDIUM-2** STEP 2's `DO` block is a no-op when the CHECK constraint already exists and cannot widen an
  older four-value version. Fix: a mandatory **STEP 2 VERIFY** `pg_get_constraintdef` query follows the block;
  the operator confirms all five tags are accepted or runs the commented drop/re-add snippet.

Task 4 checklist therefore gains two answers: STEP 0b returned zero rows, and STEP 2 VERIFY shows the
five-tag definition. Seams confirmed OK by the same review: p_rows keys/types, five-tag CHECK vs emitted tags,
`is_sentinel_value` vs `is_sentinel_claimer`, backup-table name + SELECT grant, exit codes vs runbook.

**Apply-time fix (2026-09-03, during Juan's Task 4 run):** STEP 1 failed with 42P01 because the `YYYYMMDD`
placeholder must be substituted in BOTH the `CREATE TABLE` and the `GRANT` (the comment said "this statement").
The comment now says so, and a **STEP 1 VERIFY** query lists the existing backup tables so a stray
`attribution_snapshot_backup_yyyymmdd` (placeholder unreplaced in the CREATE) is visible and can be dropped.

## Task 4 — APPROVED (2026-09-03, owner apply in the Supabase SQL editor)

**Verbatim resume signal:** `approved` (after "everything in the sql was applied").

**Answers recorded verbatim from Juan's replies:**

- STEP 1 VERIFY returned one row: `attribution_snapshot_backup_20260903` — this exact string is the name plan
  12-06's `--apply` precondition probe looks for (same UTC day as the apply, or re-create the backup that day).
- STEP 2 VERIFY returned `attribution_snapshot_backfill_source_check` =
  `CHECK (((backfill_source IS NULL) OR (backfill_source = ANY (ARRAY['live'::text, 'backfill_artifacts'::text,
  'backfill_hash_history'::text, 'backfill_cell_history'::text, 'operator'::text]))))` — all five tags accepted.
- STEP 3 `CREATE FUNCTION` returned no rows (expected).
- STEP 4 failed twice with 42601 (run-under-cursor split the dollar-quoted body; a stray `;` after `AS $$` was
  reverted) and succeeded once the whole block between the new SELECTION markers was run as one statement.

**Answers NOT reported at approval (carried to 12-06 Task 1/3 preconditions, re-verifiable read-only):**

- STEP 0 write-side role column names (the file's `frozen_primary` / `frozen_helper` / `frozen_vac_crew` assumption
  was not corrected, so STEP 4 compiled against those names — a mismatch would have failed STEP 4).
- STEP 0b duplicate-key probe result (must be zero rows before `--apply`).
- Backup table row count vs live `attribution_snapshot` count.
- STEP 3 spot check triple (`true, true, false`), the STEP 6 smoke-test row (`skipped_no_row`), the
  `backfill_run_id IS NOT NULL` count (must be 0), and the `service_role` grant list on `attribution_snapshot`
  (must include UPDATE — the RPC is SECURITY INVOKER).

12-06 Task 1 re-runs the read-only checks above and records the numbers before any apply decision.

## Greptile review fix (PR #388, issue 1) — per-role provenance

Valid: the RPC updates one ROLE column per payload row but wrote the ROW-level `backfill_source` /
`backfill_run_id`, so a row whose primary and helper were filled by different sources (or runs — sources 1-4
today, source 5 later, which is exactly Phase 12's shape) lost the earlier role's provenance. Fix: STEP 2 adds
`backfill_provenance JSONB`; every role UPDATE merges `{"<role>": {"source", "run_id"}}` into it while the
two row-level columns keep meaning "most recent backfill write". Contract test pins the column and the three
merges; `schema.sql` and the runbook describe the three columns. **Owner re-apply required (idempotent):**
STEP 2 (adds the third column), STEP 4 (DROP + CREATE), then STEP 0 must list `backfill_provenance`.
