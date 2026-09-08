---
phase: 14-foreman-helper-2
plan: 09
subsystem: billing-pipeline
tags: [python, supabase, postgres, sql, migration, attribution, rpc, billing-audit]

# Dependency graph
requires:
  - phase: 14-03
    provides: "billing_audit/writer.py freeze_attribution() parameter names and the frozen_helper2/frozen_helper2_dept role-column read path this migration's SQL and contract test pin against"
  - phase: 14-08
    provides: "O-14-A helper2-wins conflict rule and the run-summary counters that make this migration's post-merge observation (Task 3 check 4, the plan-14-03 degrade warning) meaningful once feat/phase-12-remediation merges"
provides:
  - "billing_audit/helper2_attribution.sql: the owner-deployed migration (5 numbered steps) adding frozen_helper2/frozen_helper2_dept to attribution_snapshot, appending two DEFAULT NULL parameters to freeze_attribution, and drop-then-recreating BOTH lookup functions with the new return columns"
  - "tests/test_helper2_attribution_sql_contract.py: 19-test FIXTURE PASS contract pinning drop-before-create for both lookups, parameter/column name equality against billing_audit/writer.py, and exclusion of the backfill function and provenance columns"
  - "billing_audit/schema.sql: corrected stale operator comment above the bulk lookup function (now names the drop-first requirement) plus the extended documented parameter/column contracts"
  - "The deployed production migration itself (Supabase migration 20260908165511_helper2_attribution_columns_and_rpcs on project poeyztlmsawfoqlanucc), applied under Juan's explicit chat delegation and read back with his co-sign"
provides_records:
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: D-14-07-APPLIED and D-14-07-VERIFIED (both written during this plan's Task 2/3 checkpoints; that file is NOT touched by this SUMMARY's own commit -- the orchestrator owns it concurrently for plan 14-11)"
affects: [14-10, 14-11]

# Actuals (#2632)
# NOTE ON SCOPE: plan_head_before/commits are scoped to plan 14-09's OWN commit
# range (0203e27..9d41b2e), not to current HEAD. HEAD moved past this range
# before this closeout ran because the orchestrator inserted and began
# executing plan 14-11 (O-14-C closure) concurrently on this same branch
# immediately after 14-09's Task 3 checkpoint resolved. No gsd-plan-head-before
# sentinel was ever written for 14-09 (Task 1 predates that convention landing
# in this session), so the base above was reconstructed as the parent of Task
# 1's first commit (66924c0^) and the end as the last commit whose message and
# diff are unambiguously 14-09's own (9d41b2e, the D-14-07 apply ledger sync,
# immediately before a34faa9 "docs(14-11): insert O-14-C closure plan").
# `tokens` is chars/4 over the diff of exactly this plan's declared
# files_modified across that same range.
actuals:
  tokens: 11665
  tasks: 3
  commits: 7
  plan_head_before: 0203e273ebe250524326930bc4111d94d6606054

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Owner-deployed SQL migration files follow the Phase 12 backfill precedent: a header naming who applies it/where/when/how to verify, then numbered steps a human runs in order in the Supabase SQL editor -- never executed from an agent session by default"
    - "A SQL contract test (tests/test_helper2_attribution_sql_contract.py) parses the migration file as TEXT and asserts shape/name-equality against the Python caller, because the deployed function bodies live in Supabase and cannot be inspected from the repository -- this is the only automated defense a migration like this has"
    - "Function-signature migrations that change RETURNS TABLE columns must drop before create (Postgres cannot alter a function's return columns via CREATE OR REPLACE); the contract test pins a drop statement at a lower line number than each function's create statement"
    - "New RPC parameters that must stay compatible with an already-deployed caller are declared DEFAULT NULL, not bare TEXT -- PostgREST needs every non-default named parameter present in the call, so a bare-typed new parameter would break the currently-deployed 12-parameter writer the moment the migration lands"

key-files:
  created:
    - billing_audit/helper2_attribution.sql
    - tests/test_helper2_attribution_sql_contract.py
  modified:
    - billing_audit/schema.sql
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md

key-decisions:
  - "Deployment order: sql-first (Juan's decision, chat, 2026-09-08 ~16:10Z) -- the migration landed before the feat/phase-12-remediation code merge, so the first post-merge run writes Helper #2 attribution immediately with no capability-degrade warning."
  - "Owner-authorized deviation from the plan's own prohibition ('Never apply this SQL from an agent session', threat T-14-09-05): Juan explicitly delegated the apply to the orchestrating Claude session over the Supabase MCP connection ('do sql first but apply it yourself through the supabase connection'). Authority stayed with Juan; the hands were the session's. Recorded as D-14-07-APPLIED."
  - "Three preserve-live-definition deviations from the repo template, applied at migration time and back-ported into billing_audit/helper2_attribution.sql + schema.sql in the same session so the contract test still passes: (a) the two new freeze parameters are appended LAST, not mid-list, because Postgres rejects a non-defaulted parameter after a defaulted one; (b) both lookup functions keep their deployed pinned search_path (billing_audit, public, extensions, pg_temp), which the repo's CREATE statements had omitted; (c) the deployed freeze_attribution body stays per-ROW first-write-wins (ON CONFLICT ... DO NOTHING), not per-ROLE as the file's D-12-A note assumed."
  - "Deviation (c) means every row frozen before the merge (222,260 as of 16:10Z) keeps frozen_helper2 NULL forever -- tracked as O-14-C, and NOT resolved by this plan. Plan 14-11 (inserted 2026-09-08, Wave 6) closes it with a per-role fill; its Tasks 1-2 landed during this same session (57144a9, c30d8ed, 0bb018b) and its Task 3 apply is in progress in the orchestrating session as this SUMMARY is written."
  - "[Rule 1 - Bug] The two new freeze_attribution parameters needed TEXT DEFAULT NULL, not bare TEXT -- PostgREST requires every non-default named parameter to be present in the call, so a bare-typed new parameter would have broken the currently-deployed 12-parameter writer the instant the migration landed. This default is what makes the sql-first order safe against the not-yet-merged code."

patterns-established:
  - "A migration whose documented failure mode produces no error at apply time (drop-then-create silently non-deploying) is never reported complete on 'the SQL ran without complaint' alone -- only on a recorded, timestamped, labelled read-back of the live function/table shape."

requirements-completed: [HLP-06]
# HLP-06's own text ("recorded for the Helper #2 role without overwriting other
# roles ... repeated runs are idempotent") is met at the SCHEMA/RPC-CONTRACT
# level by this plan: the deployed freeze_attribution and both lookups exist,
# return the new columns, and a Helper #2 freeze on a NEW row leaves the other
# three role columns byte-identical (Task 3 check 3, OWNER-DELEGATED
# PRODUCTION READ-BACK). The narrower per-role EXISTING-ROW gap (O-14-C) is a
# separate, explicitly-tracked follow-up that plan 14-11 closes -- it does not
# block marking HLP-06 complete because HLP-06's contract is about a fresh
# freeze never clobbering another role, which is proven, not about backfilling
# rows frozen before this migration existed.

coverage:
  - id: D1
    description: "billing_audit/helper2_attribution.sql exists with a drop-before-create sequence for both lookup functions, and a contract test pins parameter/column name equality against billing_audit/writer.py plus exclusion of the backfill function and provenance columns"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_helper2_attribution_sql_contract.py -- FIXTURE PASS (19 passed)"
        status: pass
      - kind: unit
        ref: "tests/test_billing_audit_shadow.py -q"
        status: pass
      - kind: other
        ref: "python -m pytest tests/ -q -- full suite 2249 passed / 1 skipped / 550 subtests at the Task 2 checkpoint"
        status: pass
    human_judgment: false
  - id: D2
    description: "The migration is applied to the production Supabase project (poeyztlmsawfoqlanucc) as a single transaction, in an owner-chosen deployment order, with the pre-state and rollback recorded before the change"
    requirement: "HLP-06"
    verification:
      - kind: other
        ref: "14-DECISIONS.md D-14-07-APPLIED -- OWNER-DELEGATED LIVE STATE, applied 2026-09-08T16:55:11Z as migration 20260908165511_helper2_attribution_columns_and_rpcs"
        status: pass
    human_judgment: true
    rationale: "Applying DDL to the production billing database is a protected-area, one-way action (dropping and recreating live functions) that the plan's own threat model (T-14-09-01, T-14-09-05) requires an explicit owner decision and owner authorization for -- no automated check can substitute for Juan's review and delegation of the apply."
  - id: D3
    description: "The deployed contract is confirmed by reading it back: both lookups return the two new columns, the table has both columns, a Helper #2 freeze leaves frozen_primary/frozen_helper/frozen_vac_crew byte-identical on a real observed row, and the first post-apply production run shows zero PGRST errors against the migrated functions"
    requirement: "HLP-06"
    verification:
      - kind: other
        ref: "14-DECISIONS.md D-14-07-VERIFIED -- OWNER-DELEGATED PRODUCTION READ-BACK (co-signed 'approved' by Juan), four dated observations 16:56-17:55Z on run 34253845749"
        status: pass
    human_judgment: true
    rationale: "This migration's documented failure mode (a plain replace that cannot change a function's return columns) succeeds with no error and deploys nothing -- exactly what happened here on 2026-05-27. The deployed function bodies live in Supabase and cannot be inspected from the repository, so the only possible evidence is a human (or owner-delegated session, co-signed by the human) reading the live state back."

# Metrics
duration: ~2h10m of active work across three checkpoint-gated stretches on 2026-09-08 (Task 1 SQL authoring + the DEFAULT NULL fix ~10:15-11:15Z; Task 2/3 owner-delegated apply + read-back ~16:10-17:55Z, co-signed by Juan; this closeout ~10min) -- two blocking-human gate waits separate the stretches and are not counted as active work
completed: 2026-09-08
status: complete
---

# Phase 14 Plan 09: Helper #2 Attribution Migration (D-14-07) Summary

**Owner-deployed Supabase migration gives Helper #2 its own frozen attribution role -- two additive columns, two DEFAULT-NULL freeze parameters, and both lookup functions drop-then-recreated -- pinned by a 19-test SQL contract and confirmed live by an owner-delegated, owner-co-signed production read-back.**

## Performance

- **Duration:** ~2h10m active work across three checkpoint-gated stretches on 2026-09-08 (see Metrics above); two `gate="blocking-human"` waits in between are not counted as active work
- **Tasks:** 3 (1 auto, 2 blocking-human checkpoints)
- **Files modified:** 4 (3 code/test files this SUMMARY's commit touches; `14-DECISIONS.md` was written during Tasks 2-3 but is not part of this closeout commit)
- **Commits (this plan's own scope):** 7

## Accomplishments

- **Task 1 -- the migration file and its contract test (`66924c0`, fix `c786ec3`).** `billing_audit/helper2_attribution.sql` authored on the Phase 12 backfill precedent: a header naming the applier/project/verification, then 5 numbered steps -- add the two columns, extend `freeze_attribution` with `p_helper2`/`p_helper2_dept` (both `TEXT DEFAULT NULL`, the Rule-1 fix that keeps the deployed 12-parameter writer working after the migration), drop-then-recreate `lookup_attribution`, drop-then-recreate `lookup_attribution_bulk`, reload the schema cache. `billing_audit/schema.sql`'s stale operator comment above the bulk lookup (which told the next reader to use a plain replace -- the exact 2026-05-27 failure mode) is corrected. `tests/test_helper2_attribution_sql_contract.py` asserts drop-before-create for both lookups, parameter/column name equality against `billing_audit/writer.py`, and zero references to the backfill function or provenance columns -- 19 tests, FIXTURE PASS.
- **Task 2 -- owner review and apply (`D-14-07-APPLIED`, `3d6263a`).** Juan selected **sql-first** and explicitly delegated the apply itself to this session over the Supabase MCP connection -- an owner-authorized deviation from the plan's own acceptance criterion ("No SQL was executed from an agent session") and from threat T-14-09-05, with authority staying with Juan throughout. Applied 2026-09-08T16:55:11Z on project `poeyztlmsawfoqlanucc` as a single-transaction migration, with three deviations from the repo template that preserve the LIVE definitions read back beforehand (parameter order, pinned `search_path`, per-row first-write-wins) -- all three were back-ported into the repo file and `schema.sql` in the same commit, and the contract test still passes. OWNER-DELEGATED LIVE STATE.
- **Task 3 -- the read-back (`D-14-07-VERIFIED`, same commit `3d6263a`).** Four checks, all OWNER-DELEGATED PRODUCTION READ-BACK, co-signed "approved" by Juan: both lookups return the new columns present (not absent) even when null; the table carries both new columns; a Helper #2 freeze on a real/synthetic row leaves `frozen_primary`/`frozen_helper`/`frozen_vac_crew` byte-identical; and the first real production run after the apply (34253845749) shows 74 freeze calls and 6 bulk-lookup calls, all HTTP 200, zero PGRST errors. Assumption A4 (14-RESEARCH.md) is CLOSED by observation for the contract this plan asked about. The plan-14-03 degrade-warning half of check 4 stays PENDING-UNTIL-MERGE (the deployed writer predates Phase 14's code entirely) and must be confirmed on the first run after `feat/phase-12-remediation` merges.

## Task Commits

This plan's own commit range (`0203e27`..`9d41b2e` -- see the `actuals` note in frontmatter for why this scope excludes later HEAD movement from the concurrently-inserted plan 14-11):

1. **Task 1: author the SQL + contract test** - `66924c0` (feat)
2. **Task 1 checkpoint pause: record the blocker at Task 2** - `a64f761` (docs)
3. **Task 1 follow-up fix: DEFAULT NULL on the two freeze params** - `c786ec3` (fix)
4. **Ledger sync: 14-08 close + 14-09 checkpoint** - `1f25ea0` (docs)
5. **Ledger sync: final gate counts for the 14-09 checkpoint** - `811782a` (docs)
6. **Task 2 + Task 3: record D-14-07-APPLIED and D-14-07-VERIFIED, align SQL/schema.sql** - `3d6263a` (docs)
7. **Ledger sync: the D-14-07 production apply** - `9d41b2e` (docs)

**Plan metadata:** captured in this SUMMARY commit (`docs(14-09): complete plan`).

## Files Created/Modified

- `billing_audit/helper2_attribution.sql` - the owner-deployed migration: 2 new columns, 2 new DEFAULT-NULL freeze parameters, both lookup functions drop-then-recreated
- `billing_audit/schema.sql` - corrected the stale operator comment above the bulk lookup; extended the documented parameter/column contracts
- `tests/test_helper2_attribution_sql_contract.py` - 19-test SQL shape and name-equality contract
- `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` - `D-14-07-APPLIED` and `D-14-07-VERIFIED` (written during Tasks 2-3; **not** part of this SUMMARY's own commit -- the orchestrating session owns this file concurrently for plan 14-11)

## Decisions Made

See `key-decisions` in the frontmatter: the sql-first deployment order, the owner-authorized deviation from "never apply from an agent session," the three preserve-live-definition deviations (parameter order / search_path / per-row first-write-wins), the resulting O-14-C follow-up now being closed by plan 14-11, and the Rule-1 DEFAULT-NULL fix that made the sql-first order safe.

## Deviations from Plan

### Owner-Authorized Deviations (not Rule 1-3 auto-fixes -- explicit owner decisions)

**1. Applying the SQL from this session, not from the Supabase SQL editor by Juan's own hand**
- **Found during:** Task 2 checkpoint
- **Plan text:** "Never apply this SQL from an agent session; the owner applies it in the Supabase SQL editor" (a stated prohibition, and threat T-14-09-05's stated mitigation)
- **What happened:** Juan explicitly instructed, in chat: "do sql first but apply it yourself through the supabase connection." The orchestrating session applied the migration via the Supabase MCP connection under that live delegation. Authority stayed with Juan; the hands were the session's.
- **Recorded:** `14-DECISIONS.md` `D-14-07-APPLIED`
- **Committed in:** `3d6263a`

**2. The deployed migration text diverges from the repo template in three ways, to preserve the live definitions**
- **Found during:** Task 2 apply, reading back the pre-state before writing the transaction
- **Issue:** (a) the repo template placed the two new freeze parameters mid-list, which cannot compile after the deployed function's existing defaulted parameters; (b) the repo's `CREATE` statements omitted the deployed pinned `search_path`; (c) the repo file's D-12-A note assumed a per-ROLE upsert, but the deployed `freeze_attribution` is per-ROW first-write-wins.
- **Fix:** The applied SQL kept the live shape for (a) and (b); (c) was left as-is (a business-logic change to the owner-maintained function body was out of this plan's scope) and tracked as O-14-C. The repo file and `schema.sql` were aligned to (a) and (b) in the same commit; the contract test still passes.
- **Files modified:** `billing_audit/helper2_attribution.sql`, `billing_audit/schema.sql`
- **Committed in:** `3d6263a`
- **Consequence:** O-14-C (existing rows never gain Helper #2) is open at the end of this plan; plan 14-11 (inserted the same day) closes it.

### Auto-fixed Issues

**1. [Rule 1 - Bug] `freeze_attribution`'s two new parameters needed `DEFAULT NULL`**
- **Found during:** Task 1, reviewing the currently-deployed writer's call shape before finalizing the SQL
- **Issue:** PostgREST requires every non-default named parameter to be present in an RPC call; a bare-typed new parameter on `freeze_attribution` would have broken the currently-deployed 12-parameter writer the instant the migration landed, forcing a code-first order regardless of Juan's choice.
- **Fix:** Declared `p_helper2 TEXT DEFAULT NULL` and `p_helper2_dept TEXT DEFAULT NULL`; updated `schema.sql`'s documented contract; added a contract-test assertion pinning both defaults.
- **Files modified:** `billing_audit/helper2_attribution.sql`, `billing_audit/schema.sql`, `tests/test_helper2_attribution_sql_contract.py`
- **Verification:** contract test + full suite green after the fix (2249 passed / 1 skipped / 550 subtests)
- **Committed in:** `c786ec3`

---

**Total deviations:** 2 owner-authorized (both explicit Juan decisions, not auto-fixes) + 1 auto-fixed (Rule 1, a genuine compatibility bug caught before apply)
**Impact on plan:** The owner-authorized deviations are the plan's most consequential outcome -- they trade the plan's stated "no agent applies SQL" acceptance criterion for Juan's explicit, in-session delegation, and they leave O-14-C open pending plan 14-11. Both are fully recorded with timestamps and rationale in `14-DECISIONS.md`. The Rule-1 fix is a pure compatibility correction with no scope creep.

## Issues Encountered

None beyond the deviations above. The intended run-free apply window (after run 34243784963, before the next scheduled run) was missed by about 75 seconds -- the transaction landed during run 34253845749's job checkout/setup phase, before the pipeline reaches any `billing_audit` call, so no scheduled run was affected. Recorded as-is in `D-14-07-APPLIED`.

## User Setup Required

None for this closeout. Juan already performed the required actions himself (owner-delegated) during Tasks 2 and 3: reviewing and choosing the deployment order, applying the migration, and confirming all four read-back checks. No further manual action is needed to close this plan.

## Next Phase Readiness

- **HLP-06 is complete.** The schema/RPC contract this requirement names (a later Helper #2 completion recorded for its own role, without overwriting other roles, on a fresh freeze) is proven by the Task 3 read-back.
- **O-14-C stays open at the data level**, not blocking this plan: rows frozen before the 16:55:11Z apply (222,260 of them) will never gain `frozen_helper2` under the deployed per-row first-write-wins body. Plan 14-11 (inserted 2026-09-08, Wave 6) closes this with a per-role fill; its Tasks 1-2 landed this session (`57144a9`, `c30d8ed`, `0bb018b`) and its Task 3 apply is in progress in the orchestrating session as this SUMMARY is written. Do not claim pre-merge rows carry Helper #2 attribution until 14-11's own SUMMARY confirms it.
- **The plan-14-03 degrade-warning check stays PENDING-UNTIL-MERGE.** The deployed writer that ran during Task 3's observation predates Phase 14's code entirely; the "no capability-degrade warning" half of check 4 can only be confirmed on the first scheduled run after `feat/phase-12-remediation` merges. Plan 14-10's rollout must confirm this before claiming the sql-first order paid off cleanly.
- Plan 14-10 (rollout: runbook, pilot, flag default, workflow wiring) remains blocked on Wave 6 (14-11) per the roadmap's wave ordering, not on this plan.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-08*

## Self-Check: PASSED

**Files verified:**
- FOUND: `billing_audit/helper2_attribution.sql`
- FOUND: `billing_audit/schema.sql`
- FOUND: `tests/test_helper2_attribution_sql_contract.py`
- FOUND: `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`
- FOUND: `.planning/phases/14-foreman-helper-2/14-09-SUMMARY.md`

**Commits verified:**
- FOUND: `66924c0` (Task 1: SQL + contract test)
- FOUND: `a64f761` (Task 1 checkpoint pause)
- FOUND: `c786ec3` (Rule 1 fix: DEFAULT NULL)
- FOUND: `1f25ea0` (ledger sync)
- FOUND: `811782a` (ledger sync)
- FOUND: `3d6263a` (Task 2 + Task 3: D-14-07-APPLIED / D-14-07-VERIFIED)
- FOUND: `9d41b2e` (ledger sync)
