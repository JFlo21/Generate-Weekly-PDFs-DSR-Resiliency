---
phase: 14-foreman-helper-2
plan: 12
subsystem: run-memory
tags: [python, sql, supabase, postgres, rpc, run-memory, github-actions, gap-closure]

# Dependency graph
requires:
  - phase: 14-04
    provides: "pipeline_memory/writer.py::_row_to_payload already emitting the four helper2_* keys and HASH_FIELDS already hashing them (2026-09-06) -- this plan's own Task 1 makes the RPC actually keep what the writer already sends"
  - phase: 14-07
    provides: "pipeline/discovery.py's MAPPING_SCHEMA_MARKER ('helper2-v1') read path, which stops degrading to full validation on every sheet the moment sheet_registry.mapping_schema exists as a real column"
  - phase: 14-10
    provides: "the proposed HELPER2_ENABLED workflow env line and rollout runbook this plan applies and enables"
provides:
  - "pipeline_memory/schema.sql: upsert_rows_bulk's typed jsonb_to_recordset list, incoming projection, row_event after_image, row_state INSERT list, and ON CONFLICT set list all name helper2_observed/helper2_completed/helper2_dept/helper2_job -- the RPC now keeps every HASH_FIELDS member instead of Postgres silently dropping the four extra JSON keys"
  - "pipeline_memory/helper2_columns_migration.sql: the additive, idempotent DDL (4 row_state columns + sheet_registry.mapping_schema) applied and read back in production"
  - "tests/test_upsert_rows_bulk_helper2_contract.py: a lockstep source-pin test (12 assertions) that fails the suite the moment a future HASH_FIELDS member is missing from any RPC list, instead of failing silently in production"
  - "The deployed production migration itself (Supabase migration 20260909022129_helper2_row_state_columns_marker_and_rpc on project poeyztlmsawfoqlanucc), owner-delegated apply, read back on synthetic rows on sheet_id -14012"
  - ".github/workflows/weekly-excel-generation.yml: HELPER2_ENABLED wired as `${{ vars.HELPER2_ENABLED || '0' }}` next to RUN_MEMORY_WRITE_ENABLED -- enabling/disabling Helper #2 is now a repo-variable flip, no further code change"
provides_records:
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: D-14-13-DDL-APPLIED, D-14-13-VERIFIED, O-14-A-FOLLOWUP-1 CONFIRMED, D-14-14-ENABLE (all written during this plan's own execution, not by this closeout)"
  - ".planning/REQUIREMENTS.md: HLP-06 flipped to Complete (7/7), citing D-14-13-VERIFIED"
  - ".planning/phases/14-foreman-helper-2/14-VERIFICATION.md: Addendum 2026-09-09 marking the HLP-06 gap (row 6b, O-14-B) closed, score 6/7 -> 7/7"
affects: []

# Actuals (#2632)
# NOTE ON SCOPE: this closeout runs AFTER all three plan tasks were already
# executed and committed by a prior session on this same branch
# (chore/phase-14-post-merge, PR #390) -- this SUMMARY, STATE.md, and
# ROADMAP.md are the only artifacts this closeout itself produces. No
# gsd-plan-head-before-14-12 sentinel was written by that prior session (the
# convention runs through 14-08's ledger files only), so plan_head_before is
# reconstructed as bc37103 ("docs(14): verify phase goal -- gaps_found 6/7,
# HLP-06 partial"), the commit immediately preceding Task 1's first commit.
# `commits` is the measured `git rev-list --count bc37103..HEAD` at closeout
# time (6), which is ONE MORE than the 5 commits named in this closeout's own
# task facts -- `365e76d` ("docs: second review pass on #390") landed after
# those facts were written, touching 14-VERIFICATION.md, both migration/RPC
# files, and the runbook with further review-driven wording fixes. It is
# this plan's own commit (same files, same PR, same review cycle) and is
# included below. `tokens` is chars/4 over the sum of per-commit diffs
# (git diff <hash>^..<hash>) across all 6 commits, restricted to this plan's
# declared files_modified plus the two migration/RPC files.
actuals:
  tokens: 21400
  tasks: 3
  commits: 6
  plan_head_before: bc37103

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A source-pinned lockstep test (test_upsert_rows_bulk_helper2_contract.py) parses the RPC block out of schema.sql text and asserts every HASH_FIELDS member appears in all five of its column lists -- the same 'parse the SQL file as text, assert membership' idiom test_helper2_attribution_sql_contract.py established in 14-09, applied to a second RPC"
    - "A migration file documents its own apply order, rollback order, and pre-state parking location in its own header comment (STEP 1/STEP 2/STEP 3-pointer-to-schema.sql), mirroring the helper2_attribution.sql and helper2_attribution_fill.sql precedents from 14-09/14-11 -- three additive Phase 14 migrations now share this exact documentation shape"
    - "HELPER2_ENABLED follows the RUN_MEMORY_WRITE_ENABLED precedent exactly: `${{ vars.NAME || '0' }}` in the workflow env block, a matching '0' default in pipeline/config.py, so enabling a capability in production is a repo-variable flip with zero code change and instant rollback"

key-files:
  created:
    - tests/test_upsert_rows_bulk_helper2_contract.py
  modified:
    - pipeline_memory/schema.sql
    - pipeline_memory/helper2_columns_migration.sql
    - .github/workflows/weekly-excel-generation.yml
    - website/docs/runbook/foreman-helper-2.md
    - website/docs/reference/environment.md
    - .github/prompts/configuration-environment.md
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md
    - .planning/phases/14-foreman-helper-2/14-VERIFICATION.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "D-14-13-DDL-APPLIED (Task 2, 2026-09-08 evening CDT -> applied 2026-09-09T02:21:29Z): Juan approved applying both pending additive DDLs (D-14-08-APPLIED row_state helper2_* x4; D-14-10-APPLIED sheet_registry.mapping_schema) and closing O-14-B in one message ('do this and then enable the helper 2 once these issues are fixed'), apply delegated to the orchestrating session -- the same apply-delegated shape as D-14-07-APPLIED (14-09) and O-14-C-APPLIED (14-11), the third occurrence of this pattern in Phase 14."
  - "D-14-13-VERIFIED (Task 2, production read-back 2026-09-09 02:22-02:27Z): four helper2 columns + mapping_schema confirmed present; upsert_rows_bulk def md5 changed 5987e5ed...->378b3353... with 36 helper2_ mentions, search_path pin and grants (service_role/postgres/PUBLIC EXECUTE) unchanged; synthetic round-trip on sheet_id -14012 proved insert-then-identical-resend adds 0 events, and a changed Helper #2 value on the same key produces exactly 1 update event; synthetic rows deleted, 0 remain. O-14-B RESOLVED."
  - "O-14-A-FOLLOWUP-1 CONFIRMED (2026-09-08): Juan's same instruction doubled as written confirmation of the per-slot-file-duplication follow-up left open by O-14-A; D-14-06's accepted consequence stands."
  - "D-14-14-ENABLE (Task 3, 2026-09-08): enable HELPER2_ENABLED for the scheduled workflow once the DDLs and O-14-B are fixed, overriding 14-10's runbook caution to wait for a real-data pilot -- the Resource Analyst Helper #2 column is blank on every live row today, so flipping the variable changes zero workbooks until a crew records a second helper. Mechanism: the workflow env line plus a post-merge `gh variable set HELPER2_ENABLED --body 1`, left PENDING by this closeout because PR #390 has not yet merged."
  - "[Rule 1 - Bug, review-driven] A second review pass on PR #390 (365e76d, not itemized in this closeout's original task facts) made small wording/date corrections to 14-VERIFICATION.md, both migration/RPC files, and the runbook -- no semantic change to the RPC lists, the migration DDL, or the enable decision; included here for an accurate commit count."

patterns-established:
  - "Three Phase 14 owner-delegated production applies (D-14-07-APPLIED/14-09, O-14-C-APPLIED/14-11, D-14-13-DDL-APPLIED/14-12) all follow the identical shape: pre-state parked verbatim in the owner's vault raw folder, apply as one migration outside a run window confirmed via `gh run list`, four-point read-back (schema shape, function definition text, grants/search_path, synthetic round-trip with a delete-and-recount), decision + verified records written in the same session."

requirements-completed: [HLP-06]

coverage:
  - id: D1
    description: "pipeline_memory.upsert_rows_bulk's typed recordset, incoming projection, after_image, row_state INSERT list, and ON CONFLICT set list all name the four helper2_* fields, so a run that observes a Helper #2 persists it instead of the RPC silently dropping the four keys (O-14-B)"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_upsert_rows_bulk_helper2_contract.py -- FIXTURE PASS (RED 11 of 12 failing before the fix, GREEN 12 passed after)"
        status: pass
      - kind: other
        ref: "full suite 2296 passed / 1 skipped / 557 subtests; bash scripts/run_6_gates.sh -- ALL 6 GATES PASSED; website typecheck + build green"
        status: pass
    human_judgment: false
  - id: D2
    description: "The five additive columns (row_state helper2_* x4, sheet_registry.mapping_schema) exist in production, applied together with the RPC in one owner-delegated session outside a run window, with the pre-state parked for rollback"
    requirement: "HLP-06"
    verification:
      - kind: other
        ref: "14-DECISIONS.md D-14-13-DDL-APPLIED -- OWNER-DELEGATED LIVE STATE, applied 2026-09-09T02:21:29Z as migration 20260909022129_helper2_row_state_columns_marker_and_rpc, run-free gap confirmed (run 34299267004 at the 01:00Z slot had completed; next slot 13:00Z)"
        status: pass
    human_judgment: true
    rationale: "Applying DDL plus a CREATE OR REPLACE on a live, service_role-granted RPC is a protected-area, one-way action per the plan's own threat model (T-14-12-02, T-14-12-03) and Task 2's gate=\"blocking-human\" -- no automated check substitutes for Juan's review and delegation of the apply."
  - id: D3
    description: "The apply is proven by a read-back: columns exist, the live function text carries the helper2 fields, service_role's EXECUTE and the search_path pin survived, and a synthetic round-trip stores Helper #2 values, carries them in after_image, and adds zero row_event rows on an identical second call"
    requirement: "HLP-06"
    verification:
      - kind: other
        ref: "14-DECISIONS.md D-14-13-VERIFIED -- PRODUCTION READ-BACK on sheet_id -14012, 2026-09-09 02:22-02:27Z; synthetic rows deleted afterward (3 events + 2 state rows, 0 remain)"
        status: pass
    human_judgment: true
    rationale: "The RPC's only failure mode (a column silently dropped from one of five lists) produces no error at apply time -- the sole evidence is a live read-back of before/after behavior, per the plan's own <output> instruction distinguishing PRODUCTION READ-BACK from OWNER-DELEGATED LIVE STATE."
  - id: D4
    description: "HELPER2_ENABLED is wired into the scheduled workflow exactly as the runbook proposed (a repo variable with a '0' fallback); the requirement ledger tells the truth -- HLP-06 becomes Complete only after the read-back, and O-14-A Follow-up 1 carries the owner's written confirmation"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "workflow structural tests in tests/ -- FIXTURE PASS (38 workflow structural tests pass, per the closeout facts); REQUIREMENTS.md HLP-06 row cites D-14-13-VERIFIED"
        status: pass
      - kind: other
        ref: "14-VERIFICATION.md Addendum 2026-09-09 -- score 6/7 -> 7/7 (row 6b closed)"
        status: pass
    human_judgment: false

# Metrics
duration: "unmeasured by this closeout -- the three tasks (RED/GREEN, the owner-delegated apply + read-back, and the workflow wiring + ledger writes) were executed and committed by a prior session on 2026-09-08 evening CDT / 2026-09-09 early UTC, before this closeout began; this closeout itself (SUMMARY + STATE.md + ROADMAP.md) is ~10min"
completed: 2026-09-09
status: complete
---

# Phase 14 Plan 12: O-14-B Closure -- RPC Carries Helper #2, DDL Applied, Flag Wired Summary

**Closes O-14-B: `pipeline_memory.upsert_rows_bulk` now carries all four Helper #2 fields through every one of its five column lists, the two pending additive DDLs (row_state helper2_* x4, sheet_registry.mapping_schema) are applied to production alongside the RPC and proven by a synthetic-row read-back, `HELPER2_ENABLED` is wired into the scheduled workflow as a repo-variable flip, and HLP-06 is honestly Complete (7/7) in both REQUIREMENTS.md and the 14-VERIFICATION.md addendum. The post-merge `gh variable set HELPER2_ENABLED --body 1` step remains PENDING until PR #390 merges.**

## Performance

- **Duration:** executed by a prior session (see Metrics above); this closeout ~10min
- **Tasks:** 3 (1 TDD `auto`, 1 `checkpoint:decision gate="blocking-human"`, 1 `auto`)
- **Files modified:** 9 declared in the plan + 1 test file created (10 total across this plan's commits)
- **Commits (this plan's own scope):** 6 (`bc37103` reconstructed as `plan_head_before`; see the `actuals` note in frontmatter for why this is 6, not the 5 named in this closeout's original task facts)

## Accomplishments

- **Task 1 -- RPC carries every HASH_FIELDS member; additive migration file (RED `1563199`, GREEN `cf556d8`).** `tests/test_upsert_rows_bulk_helper2_contract.py` (12 test functions) parses the `upsert_rows_bulk` block out of `pipeline_memory/schema.sql` and asserts every `HASH_FIELDS` member -- including the four `helper2_*` fields -- is present in the typed `jsonb_to_recordset` list, the incoming projection, the `row_event` after-image, the `row_state` INSERT list and its SELECT, and the `ON CONFLICT` set list; it also pins the signature, return type, and `search_path` pin as unchanged, and pins the shape of `pipeline_memory/helper2_columns_migration.sql` (header naming the project and OWNER-APPLIED, five idempotent `ADD COLUMN IF NOT EXISTS` statements, no `DROP`/`DELETE`/`TRUNCATE`/`DEFAULT`/`NOT NULL`/index, no duplicated RPC body). 11 of 12 assertions failed before the fix (RED). GREEN added the four helper2 fields to each of `schema.sql`'s RPC lists (after `vac_completed` everywhere, in `HASH_FIELDS` order) with a comment block explaining the lockstep pin and apply order, and wrote `pipeline_memory/helper2_columns_migration.sql` with STEP 1 (four `row_state` columns), STEP 2 (`mapping_schema`), a STEP 3 pointer to the `schema.sql` RPC block, and the read-back queries. Evidence: contract test 12 passed; full suite 2296 passed / 1 skipped / 557 subtests; `bash scripts/run_6_gates.sh` ALL 6 GATES PASSED; website typecheck + build green.
- **Task 2 -- apply the five columns and the RPC in one session, read back, record (`checkpoint:decision gate="blocking-human"`, resolved by Juan 2026-09-08 evening CDT; applied 2026-09-09T02:21:29Z; records in `3b60127`).** Juan selected **apply-delegated** ("do this and then enable the helper 2 once these issues are fixed") -- the third occurrence of this exact pattern in Phase 14 (after D-14-07-APPLIED/14-09 and O-14-C-APPLIED/14-11). The orchestrating session confirmed a run-free gap (run 34299267004 at the 01:00Z slot had completed; next slot 13:00Z), then applied Supabase migration `20260909022129_helper2_row_state_columns_marker_and_rpc` in one transaction: the five `ADD COLUMN IF NOT EXISTS` statements, then the `upsert_rows_bulk` block of `schema.sql` at `cf556d8` verbatim (`CREATE OR REPLACE` on the unchanged signature), then the GRANT line. The pre-state (def md5 `5987e5ed...`, grants `service_role`/`postgres`/`PUBLIC` EXECUTE, `proconfig search_path=""`) was parked in the owner's vault raw folder before applying. Read-back 02:22-02:27Z: (a) all five columns present, nullable, no default; (b) function def md5 changed to `378b3353...`, length 12035, 36 `helper2_` mentions, `SET search_path TO ''` kept, grants/proconfig unchanged; (c) a synthetic round-trip on `sheet_id = -14012` -- call 1 (two rows, one with Helper #2 values) stored `Helper Two Test / true / 42 / J-99` and NULLs respectively, both `row_event.after_image`s carried the four keys; call 2 (identical payload) returned 0 pairs / added 0 events; call 3 (new Helper #2 dept/job, new hash) returned 1 pair, updated `row_state` through the `ON CONFLICT` set list, and produced one `update` event -- then the synthetic rows were deleted (3 events + 2 state rows, 0 remain). `D-14-13-DDL-APPLIED`, `D-14-13-VERIFIED`, and `O-14-A-FOLLOWUP-1 -- CONFIRMED` were recorded in `14-DECISIONS.md`; O-14-B flipped OPEN -> RESOLVED.
- **Task 3 -- wire and enable HELPER2_ENABLED; make the ledgers truthful (`3b60127`, `8f94b50`, `365e76d`).** `.github/workflows/weekly-excel-generation.yml`'s "Generate reports" step gained `HELPER2_ENABLED: ${{ vars.HELPER2_ENABLED || '0' }}` next to `RUN_MEMORY_WRITE_ENABLED`, with a comment naming the owner decision, the rollback (`gh variable set HELPER2_ENABLED --body 0`), and where the variable lives; 38 workflow structural tests pass unchanged. The runbook (`website/docs/runbook/foreman-helper-2.md`), `environment.md`, and `configuration-environment.md` were updated from "not yet applied" to "applied," stating the variable flip as the on/off switch and that the 14-10 pilot caution was overridden by Juan on 2026-09-08. `14-DECISIONS.md` gained `D-14-14-ENABLE` (Juan's quoted instruction, the variable mechanism, expected first-enabled-run behavior). `REQUIREMENTS.md` flipped HLP-06 to Complete (7/7), citing `D-14-13-VERIFIED`; `14-VERIFICATION.md` gained an Addendum (2026-09-09) closing the HLP-06 gap (row 6b) and moving the score from 6/7 to **7/7**. `.claude/project-state.md` was separately condensed 565 -> 94 lines in the same commit window after a Greptile note, and a second review pass (`365e76d`) made small wording/date corrections to `14-VERIFICATION.md`, both migration/RPC files, and the runbook with no semantic change.

## Task Commits

This plan's own commits (base `bc37103`, reconstructed as `plan_head_before` -- see the `actuals` note in frontmatter for why the count is 6, not the 5 named in this closeout's original task facts):

1. **Task 1 RED: pin upsert_rows_bulk lists to HASH_FIELDS** - `1563199` (test)
2. **Task 1 GREEN: carry Helper #2 fields in upsert_rows_bulk** - `cf556d8` (feat)
3. **Task 2 + Task 3: Helper #2 run-memory live, flag wired** - `3b60127` (feat) -- bundles the DDL-apply decision records (D-14-13-DDL-APPLIED, D-14-13-VERIFIED, O-14-A-FOLLOWUP-1) with the workflow env line, docs, and ledger updates
4. **Ledger housekeeping: condense project-state, 14-12 ledger entries** - `b6cdd41` (docs)
5. **PR #390 review fixes (weekday, dates, YAML)** - `8f94b50` (docs)
6. **PR #390 second review pass** - `365e76d` (docs)

**Plan metadata:** captured in this SUMMARY commit (`docs(14-12): complete plan`).

## Files Created/Modified

- `tests/test_upsert_rows_bulk_helper2_contract.py` - 12-assertion lockstep contract test pinning the RPC's five column lists to `HASH_FIELDS`
- `pipeline_memory/schema.sql` - `upsert_rows_bulk` RPC's five column lists extended with the four helper2 fields; APPLIED comment added after Task 2
- `pipeline_memory/helper2_columns_migration.sql` - the additive DDL file (4 `row_state` columns + `sheet_registry.mapping_schema`); APPLIED header note added after Task 2
- `.github/workflows/weekly-excel-generation.yml` - `HELPER2_ENABLED: ${{ vars.HELPER2_ENABLED || '0' }}` added to the "Generate reports" env block
- `website/docs/runbook/foreman-helper-2.md`, `website/docs/reference/environment.md`, `.github/prompts/configuration-environment.md` - workflow wiring status flipped from "not yet applied" to "applied"
- `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` - `D-14-13-DDL-APPLIED`, `D-14-13-VERIFIED`, `O-14-A-FOLLOWUP-1 -- CONFIRMED`, `D-14-14-ENABLE`; O-14-B heading flipped OPEN -> RESOLVED (written during Task 2/3, not part of this closeout's own commit)
- `.planning/phases/14-foreman-helper-2/14-VERIFICATION.md` - Addendum 2026-09-09 closing the HLP-06 gap, score 6/7 -> 7/7 (written during Task 3, not part of this closeout's own commit)
- `.planning/REQUIREMENTS.md` - HLP-06 flipped to Complete (7/7) (written during Task 3, not part of this closeout's own commit)

## Decisions Made

See `key-decisions` in the frontmatter: `D-14-13-DDL-APPLIED` (Juan's apply-delegated selection, the third occurrence of this pattern in Phase 14), `D-14-13-VERIFIED` (the four-point production read-back), `O-14-A-FOLLOWUP-1 -- CONFIRMED`, and `D-14-14-ENABLE` (the owner's enable instruction, mechanism, and expected first-run behavior).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, review-driven] Second review pass on PR #390 (`365e76d`)**
- **Found during:** post-Task-3 PR review (after this closeout's task facts were assembled)
- **Issue:** small wording/date inconsistencies in `14-VERIFICATION.md`, both migration/RPC files, and the runbook, flagged by a review pass on PR #390
- **Fix:** wording and date corrections; no semantic change to the RPC column lists, the migration DDL, or the D-14-14-ENABLE decision
- **Files modified:** `.planning/phases/14-foreman-helper-2/14-VERIFICATION.md`, `pipeline_memory/helper2_columns_migration.sql`, `pipeline_memory/schema.sql`, `website/docs/runbook/foreman-helper-2.md`
- **Committed in:** `365e76d`

No other deviations. The plan's own reversibility ratings, prohibitions, and threat-model mitigations (T-14-12-01 lockstep test, T-14-12-02 run-window check, T-14-12-03 signature-preserving `CREATE OR REPLACE`, T-14-12-04 parked pre-state) all held exactly as scoped.

---

**Total deviations:** 1 auto-fixed (Rule 1, review-driven wording/date corrections, no semantic change)
**Impact on plan:** None on scope or correctness -- the extra commit is the same PR's own review cycle, folded into this plan's commit count for an honest `actuals.commits`.

## Issues Encountered

None beyond the deviation above.

**Post-merge step still owed (PENDING, not performable from this closeout):**
- `gh variable set HELPER2_ENABLED --body 1 --repo JFlo21/Generate-Weekly-PDFs-DSR-Resiliency` is an owner-delegated post-merge action, to run immediately after PR #390 merges to `master`. This closeout does not run it (no push, no merge, in scope for this session) and records it here as an addendum to `D-14-14-ENABLE`, to be confirmed once performed.
- The first scheduled run on the merged code (the Wed 2026-09-09 13:00Z slot, or the first slot after merge if later) must be observed for: the four Helper #2 counters present in `run_summary`, no `helper2_capability_unavailable`-style degrade warning where the columns are now present, and zero `_Helper2_` workbooks until a real Helper #2 name appears in production (Resource Analyst Helper #2 remains blank on every live row today).

## User Setup Required

**One action remains, to be performed by Juan (or the orchestrating session under his explicit delegation) immediately after PR #390 merges:**

```bash
gh variable set HELPER2_ENABLED --body 1 --repo JFlo21/Generate-Weekly-PDFs-DSR-Resiliency
```

Then confirm the next scheduled run's log shows the Helper #2 counters and no degrade warning. Rollback if needed: `gh variable set HELPER2_ENABLED --body 0` (no code change; the workflow's `|| '0'` fallback covers an unset variable too).

## Next Phase Readiness

- **O-14-B is RESOLVED.** `pipeline_memory.upsert_rows_bulk` now persists all four Helper #2 fields to `row_state`, proven end-to-end on synthetic rows in production; not yet observed on a real row because Helper #2 remains blank across production today.
- **HLP-06 is honestly Complete (7/7)** in both `REQUIREMENTS.md` and the `14-VERIFICATION.md` addendum -- both the "frozen" half (billing_audit, via O-14-C) and the "cached" half (pipeline_memory, via this plan's O-14-B closure) are now live-verified.
- **Phase 14 (Foreman Helper #2) is fully executed: 12/12 plans.** The only remaining action is the post-merge variable flip and its first-run observation, both owner-delegated operational steps outside any further planned work.
- **PR #390** carries this plan's full diff (Tasks 1-3 plus two review-fix commits) on branch `chore/phase-14-post-merge`, awaiting merge to `master`.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-09*

## Self-Check: PASSED

**Files verified:**
- FOUND: `tests/test_upsert_rows_bulk_helper2_contract.py`
- FOUND: `pipeline_memory/schema.sql`
- FOUND: `pipeline_memory/helper2_columns_migration.sql`
- FOUND: `.github/workflows/weekly-excel-generation.yml`
- FOUND: `website/docs/runbook/foreman-helper-2.md`
- FOUND: `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`
- FOUND: `.planning/phases/14-foreman-helper-2/14-VERIFICATION.md`
- FOUND: `.planning/REQUIREMENTS.md`

**Commits verified:**
- FOUND: `1563199` (Task 1 RED)
- FOUND: `cf556d8` (Task 1 GREEN)
- FOUND: `3b60127` (Task 2 + Task 3 records and wiring)
- FOUND: `b6cdd41` (ledger housekeeping)
- FOUND: `8f94b50` (PR #390 review fixes)
- FOUND: `365e76d` (PR #390 second review pass)

**Requirements verified:** `.planning/REQUIREMENTS.md` line 326 reads `[x] **HLP-06**` citing `D-14-13-VERIFIED`; line 443 reads `Complete (14-12 closed O-14-B; D-14-13-VERIFIED 2026-09-09)`.
