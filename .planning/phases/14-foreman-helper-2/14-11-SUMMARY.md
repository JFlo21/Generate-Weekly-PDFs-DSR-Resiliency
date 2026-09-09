---
phase: 14-foreman-helper-2
plan: 11
subsystem: billing-pipeline
tags: [python, supabase, postgres, sql, migration, attribution, rpc, billing-audit, run-memory]

# Dependency graph
requires:
  - phase: 14-03
    provides: "billing_audit/writer.py freeze_attribution() parameter names, the 12-argument writer call shape, and the frozen_helper2/frozen_helper2_dept role-column read path this plan's admission rule and SQL contract test pin against"
  - phase: 14-08
    provides: "the run_summary counter pattern (add key -> golden baseline -> three key-count contracts) this plan repeats to add snapshots_helper2_filled, moving the baseline from 29 to 30 keys"
  - phase: 14-09
    provides: "the deployed billing_audit.freeze_attribution / lookup_attribution / lookup_attribution_bulk functions (D-14-07-APPLIED, D-14-07-VERIFIED) and the O-14-C gap this plan exists to close -- the deployed function was per-ROW first-write-wins, so a row frozen before the merge kept frozen_helper2 NULL forever"
provides:
  - "pipeline/grouping.py: get_prefetched_helper2_missing_keys() / _PREFETCHED_HELPER2_MISSING_KEYS, publishing the set of prefetched rows whose Helper #2 is still null/sentinel/absent"
  - "pipeline/attribution.py: billing_audit_cache_key() (factored out of warm_billing_audit_row_cache, byte-identical output), build_helper2_fill_keys(), and the pure admission predicate helper2_fill_admits()"
  - "pipeline/orchestrate.py: the freeze loop's already-frozen skip now admits a row exactly when helper2_fill_admits() returns True for it, so a frozen row that gained a valid Helper #2 is re-sent to the RPC at most once per run"
  - "billing_audit/writer.py: snapshots_helper2_filled counter, classified from the RPC's returned backfill_provenance.helper2.run_id only, never inferred from the outgoing request"
  - "tests/golden/run_summary_baseline.json: 30-key golden baseline (was 29 after 14-08)"
  - "billing_audit/helper2_attribution_fill.sql: the owner-approved per-role fill migration (CREATE OR REPLACE on the deployed 14-parameter freeze_attribution signature, ON CONFLICT DO UPDATE gated by is_sentinel_value, provenance-stamped) + tests/test_helper2_attribution_fill_sql_contract.py pinning its exact shape"
  - "The deployed production migration itself (Supabase migration 20260908201205_helper2_attribution_per_role_fill on project poeyztlmsawfoqlanucc), applied under Juan's explicit chat delegation (apply-delegated) and read back on synthetic rows"
provides_records:
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: O-14-C-APPLIED and O-14-C-VERIFIED (written by the orchestrating session during Task 3), and the O-14-C heading flipped from OPEN to RESOLVED"
affects: [14-10]

# Actuals (#2632)
# NOTE ON SCOPE: no gsd-plan-head-before-14-11 sentinel was ever written (this
# plan's Task 1 predates the sentinel convention landing in this session, same
# as 14-09). plan_head_before is reconstructed as the parent of Task 1's first
# commit (57144a9^ = a34faa9, the "insert 14-11 plan" commit -- itself excluded,
# same treatment 14-09 gave its own plan-insert predecessor). `commits` is an
# explicit list of this plan's OWN commits, not a raw `git rev-list --count`
# over the base..HEAD range: `a2de0de` ("docs(14-09): complete plan") lands
# chronologically inside that range because the orchestrating session
# interleaved 14-09's own closeout with this plan's Task 3 apply, and it is
# NOT one of this plan's commits. `tokens` is chars/4 summed per-commit (git
# diff <hash>^..<hash>) over exactly this plan's declared files_modified, for
# only the 5 commits below -- not a single diff across the contaminated range.
actuals:
  tokens: 16728
  tasks: 3
  commits: 5
  plan_head_before: a34faa90095f36b6e154d2bc92ba46d6849e6fea

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A prefetch-derived key set (get_prefetched_helper2_missing_keys) is published next to the existing frozen-row key set at the same three lifecycle points (reset / populate-on-success), so a new admission rule never needs its own prefetch pass"
    - "The freeze loop's admission predicate is a small pure function (helper2_fill_admits) taking the row, its cache key, and the fill-key set -- unit-testable without patching freeze_row or the network client"
    - "A per-role ON CONFLICT ... DO UPDATE fill mirrors the Phase 12 backfill_attribution precedent: gated by billing_audit.is_sentinel_value on both sides (existing value must be sentinel, incoming value must not be), and merges a per-role entry into backfill_provenance rather than touching the row-level backfill_source/backfill_run_id columns (those mean 'most recent backfill write', not 'a live fill')"
    - "A counter that claims a database-side effect happened must be classified from the RPC's returned row (backfill_provenance.helper2.run_id == this run's id), never from the shape of the outgoing request -- the same discipline snapshots_already_frozen already followed"

key-files:
  created:
    - billing_audit/helper2_attribution_fill.sql
    - tests/test_helper2_attribution_fill_sql_contract.py
  modified:
    - pipeline/grouping.py
    - pipeline/attribution.py
    - pipeline/orchestrate.py
    - billing_audit/writer.py
    - billing_audit/schema.sql
    - tests/test_foreman_helper_2.py
    - tests/golden/run_summary_baseline.json
    - tests/test_incremental_read.py
    - tests/test_parity_shadow.py
    - tests/test_billing_audit_shadow.py
    - tests/validate_production_safety.py
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md

key-decisions:
  - "Task 3 decision (Juan, chat, 2026-09-08 ~20:05Z): apply-delegated -- same pattern as D-14-07-APPLIED. The orchestrating Claude session applied the migration over the Supabase MCP connection under Juan's explicit delegation ('i approve the d-14-07-verified & apply-delegated'), not Juan applying it himself in the SQL Editor (apply-owner) and not deferring (defer)."
  - "Owner-authorized deviation from the plan's own phase-level wording ('no SQL from an agent session') and from this plan's own prohibition list item 5 ('Never apply the SQL without the owner's decision at Task 3') -- the owner's decision was obtained and is the deviation's basis, recorded plainly per the plan's own instruction. This is the SECOND occurrence of this exact deviation shape in Phase 14 (first: D-14-07-APPLIED, plan 14-09)."
  - "The per-role fill is scoped to Helper #2 ONLY -- primary, Helper #1, and vac_crew keep today's per-ROW first-write-wins (ON CONFLICT DO NOTHING). This was the plan's own design constraint (O-14-C option 2, scoped), not a decision made during execution."
  - "[Rule 1 - Bug] tests/test_billing_audit_shadow.py's counters-dict pin needed updating for the new snapshots_helper2_filled key, and tests/validate_production_safety.py's static-scan search window needed widening 18000->19000 to keep scanning far enough into orchestrate.py to see the new admission-rule lines -- both outside this plan's declared files_modified list, both required for the Task 1 GREEN commit to actually pass the full suite and the 6-gate harness."

patterns-established:
  - "A migration whose only correctness proof is a live read-back states so explicitly in its own header (STEP 1's read-only capture-and-compare-before-applying gate), mirroring 14-09's helper2_attribution.sql precedent for a second migration file in the same phase."

requirements-completed: [HLP-06]
# HLP-06 was already marked Complete in REQUIREMENTS.md by 14-09's closeout
# (a2de0de) -- HLP-06's text is satisfied at the schema/RPC-contract level by
# that plan's read-back. This plan closes the narrower O-14-C gap 14-09 left
# open (existing rows never gained Helper #2 under the deployed per-row
# first-write-wins body) and is HLP-06's own natural extension, but does NOT
# re-flip or re-run requirements.mark-complete -- there is no Pending row for
# this plan's requirement, so REQUIREMENTS.md is left untouched by this
# closeout.

coverage:
  - id: D1
    description: "The pipeline admits an already-frozen row to the freeze RPC exactly when it now carries a valid Helper #2 and the prefetched snapshot's Helper #2 is still null/sentinel/absent, and counts a fill only when the database's returned provenance confirms it"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py -- FIXTURE PASS (RED 57144a9 -> GREEN c30d8ed, TDD)"
        status: pass
      - kind: unit
        ref: "tests/test_incremental_read.py, tests/test_parity_shadow.py -- FIXTURE PASS (30-key contract)"
        status: pass
      - kind: other
        ref: "focused suite (test_foreman_helper_2.py + test_incremental_read.py + test_parity_shadow.py) -- 548 passed, re-verified by the orchestrator; bash scripts/run_6_gates.sh -- ALL 6 GATES PASSED; full suite -- 2284 passed / 1 skipped / 557 subtests"
        status: pass
    human_judgment: false
  - id: D2
    description: "A reviewable SQL file exists (billing_audit/helper2_attribution_fill.sql) whose only semantic change is a per-role Helper #2 fill gated by is_sentinel_value, with a provenance entry, and a contract test that fails the moment it touches any other column"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_helper2_attribution_fill_sql_contract.py -- FIXTURE PASS (38 passed, includes the pre-existing 14-09 contract test)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The fill migration is applied to the production Supabase project in an owner-chosen, owner-delegated apply, in a run-free window, with pre-state capture and rollback recorded"
    requirement: "HLP-06"
    verification:
      - kind: other
        ref: "14-DECISIONS.md O-14-C-APPLIED -- OWNER-DELEGATED LIVE STATE, applied 2026-09-08T20:12:05Z as migration 20260908201205_helper2_attribution_per_role_fill, run-free gap confirmed via gh run list at 20:10:59Z"
        status: pass
    human_judgment: true
    rationale: "Applying DDL that changes a live, owner-maintained billing function's conflict-resolution semantics is a protected-area, one-way action per the plan's own threat model (T-14-11-01, T-14-11-02, T-14-11-05) and Task 3's gate=\"blocking-human\" -- no automated check can substitute for Juan's review and delegation of the apply."
  - id: D4
    description: "The deployed fill is confirmed by a synthetic-row read-back: a fill writes only the two Helper #2 columns plus a provenance entry, every other column (including frozen_at and source_run_id) stays byte-identical, a second differing Helper #2 is refused, and a fresh insert carries no provenance"
    requirement: "HLP-06"
    verification:
      - kind: other
        ref: "14-DECISIONS.md O-14-C-VERIFIED -- PRODUCTION READ-BACK on synthetic key ZZ-HELPER2-VERIFY / 2000-01-01, 5 dated observations, rows deleted afterward (confirmed count 0)"
        status: pass
    human_judgment: true
    rationale: "This migration's documented failure mode (a WHERE clause that silently never matches, or a SET list that touches an unintended column) produces no error at apply time -- the only possible evidence is a read-back of the live function's behavior on rows before and after conflict, which per the plan's own <output> instruction must be labelled PRODUCTION READ-BACK, distinct from OWNER-DELEGATED LIVE STATE and FIXTURE PASS."

# Metrics
duration: ~40min of active work across two checkpoint-gated stretches on 2026-09-08 (Task 1 RED/GREEN + Task 2 SQL authoring ~19:27-19:46Z; Task 3 owner-delegated apply + synthetic-row read-back ~20:05-20:25Z, plus a final ledger-record commit at 21:53Z) -- the gate="blocking-human" wait between the Task 2 pause and Juan's ~20:05Z approval (~19 min) and a further gap before the O-14-C-APPLIED/VERIFIED ledger commit landed (the orchestrating session was concurrently closing out plan 14-09 in the same window) are not counted as active work; this closeout ~10min
completed: 2026-09-08
status: complete
---

# Phase 14 Plan 11: O-14-C Closure -- Per-Role Helper #2 Fill Summary

**Closes O-14-C: the freeze RPC now admits an already-frozen row exactly once when it gains a valid Helper #2, `freeze_attribution` fills only the two Helper #2 columns (plus provenance) on conflict via a per-role `is_sentinel_value`-gated `DO UPDATE`, the fill is counted from returned provenance only, and the migration is applied and read back live on synthetic rows.**

## Performance

- **Duration:** ~40 min active work across two checkpoint-gated stretches on 2026-09-08 (see Metrics above); a `gate="blocking-human"` wait and a concurrent-session gap between stretches are not counted as active work
- **Tasks:** 3 (2 auto -- one TDD -- and 1 `checkpoint:decision gate="blocking-human"`)
- **Files modified:** 12 (2 created, 10 modified; `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` was written during Task 3 and is not part of this closeout's own commit)
- **Commits (this plan's own scope):** 5

## Accomplishments

- **Task 1 -- admit late Helper #2 claims and count the fills (RED `57144a9`, GREEN `c30d8ed`).** `pipeline/grouping.py` gained `get_prefetched_helper2_missing_keys()` / `_PREFETCHED_HELPER2_MISSING_KEYS`, published at the same three lifecycle points as the existing frozen-row key set. `pipeline/attribution.py` factored `billing_audit_cache_key()` out of `warm_billing_audit_row_cache` (byte-identical output preserved) and added `build_helper2_fill_keys()` plus the pure admission predicate `helper2_fill_admits()`. `pipeline/orchestrate.py`'s freeze loop now skips an already-frozen row unless `helper2_fill_admits()` returns True for it, so a row is sent to the RPC at most once per run. `billing_audit/writer.py` gained the `snapshots_helper2_filled` counter, classified strictly from the RPC's returned `backfill_provenance.helper2.run_id` matching the current run -- never inferred from the outgoing request shape. `tests/golden/run_summary_baseline.json` moved from 29 to 30 keys, and the three run_summary key-count contracts (`tests/test_foreman_helper_2.py`, `tests/test_incremental_read.py`, `tests/test_parity_shadow.py`) were updated to match. Evidence: FIXTURE PASS -- focused suite (`test_foreman_helper_2.py` + `test_incremental_read.py` + `test_parity_shadow.py`) 548 passed; `bash scripts/run_6_gates.sh` ALL 6 GATES PASSED; full suite 2284 passed / 1 skipped / 557 subtests (re-verified by the orchestrator).
- **Task 2 -- author the per-role fill migration and its contract test (`0bb018b`).** `billing_audit/helper2_attribution_fill.sql` written on the 14-09 numbered-step pattern: STEP 1 is a read-only pre-apply capture-and-compare gate, STEP 2 is a single `CREATE OR REPLACE FUNCTION billing_audit.freeze_attribution` on the identical deployed 14-parameter signature whose only semantic change is the `ON CONFLICT ... DO NOTHING` becoming a `DO UPDATE` gated by `is_sentinel_value(s.frozen_helper2)` AND `NOT is_sentinel_value(EXCLUDED.frozen_helper2)`, setting only `frozen_helper2`, `frozen_helper2_dept`, and a merged `backfill_provenance.helper2 = {source: 'live', run_id}` entry, and STEP 3 is the read-only shape check plus the synthetic-row procedure. `billing_audit/schema.sql`'s freeze contract block was extended to name the fill file. `tests/test_helper2_attribution_fill_sql_contract.py` pins the SET list to exactly those three targets, the WHERE clause to both sentinel checks, the absence of `DROP FUNCTION`/`GRANT`/`backfill_source`/`backfill_run_id`/either lookup function, and the parameter-name/DEFAULT-NULL/ordering contract, importing the existing parser helpers from the 14-09 contract test rather than duplicating them. Evidence: FIXTURE PASS -- 38 passed (both contract test files together).
- **Task 3 -- Juan's decision, the delegated apply, and the production read-back (`O-14-C-APPLIED`, `O-14-C-VERIFIED`, orchestrator commit `c3df1a8`).** Juan selected **apply-delegated** in chat 2026-09-08 ~20:05Z ("i approve the d-14-07-verified & apply-delegated") -- the same shape as D-14-07-APPLIED, not `apply-owner` and not `defer`. The orchestrating Claude session captured the pre-state (post-14-09 per-row `DO NOTHING` body, identity args unchanged, `search_path=''`, grants intact, 222,465 snapshot rows, 0 synthetic rows -- parked verbatim in the vault), confirmed a run-free gap via `gh run list` at 20:10:59Z (no run in progress; next cron slot 21:00Z), and applied Supabase migration `20260908201205_helper2_attribution_per_role_fill` at 20:12:05Z -- OWNER-DELEGATED LIVE STATE. The synthetic-row PRODUCTION READ-BACK on key `ZZ-HELPER2-VERIFY` / 2000-01-01 (rows deleted afterward, count re-confirmed 0) showed: a 12-argument call (today's deployed writer shape) leaves `frozen_helper2` NULL; a 14-argument re-freeze with every OTHER value deliberately different fills only the two Helper #2 columns plus `backfill_provenance.helper2 = {source: live, run_id}`, with every other column -- including `frozen_at` and `source_run_id` -- byte-identical; a third call with a DIFFERENT Helper #2 is refused (first-write-wins per role holds); a fresh insert on a second row carries Helper #2 with no provenance entry (the insert path is untouched); and both lookup functions return the filled values. The O-14-C heading in `14-DECISIONS.md` was updated from OPEN to RESOLVED, pointing at both records.

## Task Commits

This plan's own commits (base `a34faa9`, the plan-insertion commit, excluded -- see the `actuals` note in frontmatter for why the range is not a straight `git rev-list --count`):

1. **Task 1 RED: failing tests for Helper #2 late-fill admission** - `57144a9` (test)
2. **Task 1 GREEN: admit late Helper #2 claims to freeze RPC, count fills** - `c30d8ed` (feat)
3. **Task 2: author per-role Helper #2 fill migration for review** - `0bb018b` (feat)
4. **Ledger sync: Tasks 1-2 landed, Task 3 checkpoint pause recorded** - `9367299` (docs)
5. **Task 3: record O-14-C-APPLIED and O-14-C-VERIFIED, O-14-C RESOLVED** - `c3df1a8` (docs)

**Plan metadata:** captured in this SUMMARY commit (`docs(14-11): complete plan`).

**Excluded from this list (interleaved, not this plan's own commit):** `a2de0de` ("docs(14-09): complete plan") lands chronologically between commits 4 and 5 above because the orchestrating session closed out plan 14-09 concurrently with this plan's Task 3 checkpoint wait and apply.

## Files Created/Modified

- `billing_audit/helper2_attribution_fill.sql` - the per-role Helper #2 fill migration: `CREATE OR REPLACE` on the deployed 14-parameter `freeze_attribution` signature, `ON CONFLICT ... DO UPDATE` gated by `is_sentinel_value`
- `tests/test_helper2_attribution_fill_sql_contract.py` - 38-assertion (combined with the 14-09 contract test) SQL shape and name-equality contract for the fill migration
- `billing_audit/schema.sql` - freeze contract block extended to name the fill file
- `pipeline/grouping.py` - `get_prefetched_helper2_missing_keys()` / `_PREFETCHED_HELPER2_MISSING_KEYS`
- `pipeline/attribution.py` - `billing_audit_cache_key()`, `build_helper2_fill_keys()`, `helper2_fill_admits()`
- `pipeline/orchestrate.py` - freeze loop's already-frozen skip now admits a qualifying row
- `billing_audit/writer.py` - `snapshots_helper2_filled` counter, classified from returned provenance
- `tests/test_foreman_helper_2.py` - new RED/GREEN test class for the admission rule and counter
- `tests/golden/run_summary_baseline.json` - 30-key baseline (was 29)
- `tests/test_incremental_read.py`, `tests/test_parity_shadow.py` - key-count contracts moved 29 -> 30
- `tests/test_billing_audit_shadow.py` - [Rule 1] counters-dict pin updated for `snapshots_helper2_filled`
- `tests/validate_production_safety.py` - [Rule 1] static-scan search window widened 18000 -> 19000
- `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` - `O-14-C-APPLIED`, `O-14-C-VERIFIED`, O-14-C heading flipped OPEN -> RESOLVED (written during Task 3; **not** part of this SUMMARY's own commit)

## Decisions Made

See `key-decisions` in the frontmatter: Juan's `apply-delegated` selection at Task 3, the resulting owner-authorized deviation from "no SQL from an agent session" (second occurrence in Phase 14, same shape as D-14-07-APPLIED), the plan's own design scoping of the fill to Helper #2 only, and the two Rule-1 auto-fixes needed to make Task 1's GREEN commit pass the full suite.

## Deviations from Plan

### Owner-Authorized Deviations (not Rule 1-3 auto-fixes -- explicit owner decisions)

**1. Applying the fill SQL from the orchestrating session, not from the Supabase SQL editor by Juan's own hand**
- **Found during:** Task 3 checkpoint
- **Plan text:** the phase's carried-forward instruction ("no SQL from an agent session") and this plan's own prohibition list item 5 ("Never apply the SQL without the owner's decision at Task 3")
- **What happened:** Juan explicitly selected the `apply-delegated` option in chat ("i approve the d-14-07-verified & apply-delegated"), the same shape Juan chose for D-14-07-APPLIED in plan 14-09. The orchestrating session applied the migration via the Supabase MCP connection under that live delegation. Authority stayed with Juan; the hands were the session's.
- **Recorded:** `14-DECISIONS.md` `O-14-C-APPLIED`
- **Committed in:** `c3df1a8`

### Auto-fixed Issues

**1. [Rule 1 - Bug] `tests/test_billing_audit_shadow.py`'s counters-dict pin needed the new key**
- **Found during:** Task 1 GREEN, running the full suite
- **Issue:** a test that pins the exact set of counter keys `freeze_row` can bump failed once `snapshots_helper2_filled` was added, because the pin predates this plan's new counter
- **Fix:** added `snapshots_helper2_filled` to the pinned counter set
- **Files modified:** `tests/test_billing_audit_shadow.py`
- **Verification:** full suite green after the fix (2284 passed / 1 skipped / 557 subtests)
- **Committed in:** `c30d8ed` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] `tests/validate_production_safety.py`'s static-scan search window was too short**
- **Found during:** Task 1 GREEN, running the full suite / 6-gate harness
- **Issue:** a static text-scan window into `pipeline/orchestrate.py` (bounded at character 18000) no longer reached far enough to see the new admission-rule lines added by this plan's freeze-loop change, so the scan's assertions were checked against a truncated view
- **Fix:** widened the window from 18000 to 19000 characters
- **Files modified:** `tests/validate_production_safety.py`
- **Verification:** `bash scripts/run_6_gates.sh` ALL 6 GATES PASSED after the fix
- **Committed in:** `c30d8ed` (Task 1 GREEN commit)

---

**Total deviations:** 1 owner-authorized (an explicit Juan decision, not an auto-fix) + 2 auto-fixed (both Rule 1, scope-boundary-adjacent test-file corrections needed for the Task 1 GREEN commit to actually pass)
**Impact on plan:** The owner-authorized deviation is this plan's most consequential outcome -- it trades the phase's stated "no agent applies SQL" convention for Juan's explicit, in-session delegation, for the second time in Phase 14. Both Rule-1 fixes are narrow test-file corrections outside this plan's declared `files_modified` list but directly caused by this plan's own new counter and new code lines; neither is scope creep.

## Issues Encountered

None beyond the deviations above.

**Post-merge checks still owed (PENDING, not verifiable from this closeout):**
- The first scheduled run after `feat/phase-12-remediation` merges must log no Helper #2 capability-degrade warning (carried over from D-14-07-VERIFIED check 4, still PENDING-UNTIL-MERGE).
- The first real production row that gains a late Helper #2 must show `snapshots_helper2_filled > 0` in that run's `run_summary` and a `helper2` entry in that row's `backfill_provenance` -- proven so far only on synthetic rows (O-14-C-VERIFIED), never yet on a real row, because Helper #2 is blank across all of production today (LIVE-COLUMN-PROBE, 2026-09-06: 0 of 576 rows on the Resource Analyst sheet carry a non-blank Helper #2).

## User Setup Required

None for this closeout. Juan already performed the required action himself during Task 3: choosing `apply-delegated` and confirming the delegation in chat. No further manual action is needed to close this plan.

## Next Phase Readiness

- **O-14-C is RESOLVED.** A foreman added as Helper #2 to a row after that row was first frozen will be credited in the attribution snapshot on the next run that sees it, with provenance, without any other column of that row changing, and without the pipeline re-sending rows that have nothing to fill -- proven end-to-end on synthetic rows in production; not yet observed on a real row because no real Helper #2 exists in production yet.
- **HLP-06 stays Complete** (marked by 14-09's closeout); this plan is HLP-06's natural extension and does not re-run `requirements.mark-complete`.
- **Two post-merge observations remain owed**, listed under Issues Encountered above -- 14-10's rollout notes must confirm both on the first real post-merge run before claiming the per-role fill "worked in production," not just "was applied and verified on synthetic data."
- **Plan 14-10 (rollout: runbook, pilot, flag default, workflow wiring) is now unblocked** on Wave 7 per the roadmap's wave ordering -- Wave 6 (this plan) is the last blocker.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-08*

## Self-Check: PASSED

**Files verified:**
- FOUND: `billing_audit/helper2_attribution_fill.sql`
- FOUND: `tests/test_helper2_attribution_fill_sql_contract.py`
- FOUND: `pipeline/grouping.py`
- FOUND: `pipeline/attribution.py`
- FOUND: `pipeline/orchestrate.py`
- FOUND: `billing_audit/writer.py`
- FOUND: `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`
- FOUND: `.planning/phases/14-foreman-helper-2/14-11-SUMMARY.md`

**Commits verified:**
- FOUND: `57144a9` (Task 1 RED)
- FOUND: `c30d8ed` (Task 1 GREEN)
- FOUND: `0bb018b` (Task 2)
- FOUND: `9367299` (ledger sync)
- FOUND: `c3df1a8` (Task 3: O-14-C-APPLIED / O-14-C-VERIFIED)

**Task 3 automated verify re-run:** `python -c "...O-14-C-APPLIED... and ...O-14-C-VERIFIED..."` -> EXIT 0 (both records present, O-14-C heading reads RESOLVED)
