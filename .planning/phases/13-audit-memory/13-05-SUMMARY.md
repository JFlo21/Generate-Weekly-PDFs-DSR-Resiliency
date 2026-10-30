---
phase: 13-audit-memory
plan: 05
subsystem: database
tags: [supabase, plpgsql, rls, audit, pipeline_memory]

# Dependency graph
requires:
  - phase: 13-audit-memory
    provides: "13-04's complete D-08 transition table in pipeline_memory.upsert_audit_findings"
provides:
  - "pipeline_memory.open_findings and pipeline_memory.finding_history_by_wr views, security_invoker, RLS-safe"
  - "pipeline_memory.acknowledge_finding(p_finding_key, p_actor, p_transition, p_note) owner-only manual transition helper"
  - "RLS + revoke coverage for audit_finding / audit_finding_event and the two new views"
  - "The complete, reapply-safe audit-memory DDL applied live to project poeyztlmsawfoqlanucc and read back by the owner"
affects: [13-06]

# Actuals (#2632)
actuals:
  tokens: 9500
  tasks: 3
  commits: 2
  plan_head_before: 9165cb016ed60f4a30087f861b550cc8adb34427

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Views declared WITH (security_invoker = true) plus an explicit REVOKE ALL FROM anon, authenticated stated per-view, since the schema-wide ALTER DEFAULT PRIVILEGES ... ON TABLES statement does not cover views created before it was re-run."
    - "acknowledge_finding validates the transition value and the finding_key existence explicitly and RAISEs on either miss, rather than silently no-op'ing -- the only manual transition path in the system, so silent failure would be indistinguishable from success."
    - "Owner-delegated live apply via the Supabase MCP connector, tracked as one named migration (audit_memory_findings_lifecycle_views) rather than raw ad hoc SQL execution, mirroring the precedent set in Phase 12 (D-12-E) and Phase 14 (D-14-07-APPLIED) for owner-authorized apply-delegated DDL."

key-files:
  created: []
  modified:
    - pipeline_memory/schema.sql
    - tests/test_audit_findings_sql_contract.py

key-decisions:
  - "Owner instruction 2026-09-11 (verbatim): \"apply the supabase edits yourself using our supbase connector and do this for me\" -- Task 2 and Task 3's checkpoints (both scoped by the plan as owner-only, protected-area actions per D-11) were resolved by the owner directing the orchestrating session to apply and read back the DDL via the Supabase MCP connector, mirroring the established apply-delegated pattern from Phase 12 (D-12-E) and Phase 14 (D-14-07-APPLIED, O-14-C-APPLIED, D-14-13-DDL-APPLIED)."
  - "DDL applied as one tracked migration (name audit_memory_findings_lifecycle_views, version 20260912023008) rather than pasted ad hoc into the SQL editor -- gives the live project a durable, inspectable migration record matching the file's own statement boundaries."
  - "AUDIT_MEMORY_ENABLED confirmed still unset everywhere post-apply -- applying the DDL does not open the write path; that remains a separate, later owner decision per the plan's explicit prohibition."

patterns-established:
  - "Live Supabase view-content read-back, run once by the owner via the connector against synthetic-only rows with a full before/after cleanup check (residual row count = 0), is the verification of record for SQL surfaces this repository has no automated harness for -- named explicitly in both this plan and 13-04's SUMMARY."

requirements-completed: [AUD-01]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "pipeline_memory.open_findings and pipeline_memory.finding_history_by_wr views, the acknowledge_finding helper, RLS/revoke coverage for audit_finding and audit_finding_event, and the D-13-A header closure are all present in the repo's schema.sql and pass the structural contract test"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings_sql_contract.py -q (15 passed)"
        status: pass
      - kind: other
        ref: "grep -nE \"EXECUTE +'|EXECUTE +format\\(|\\|\\| *quote_\" pipeline_memory/schema.sql (no match, exit 1)"
        status: pass
      - kind: other
        ref: "grep -c \"security_invoker = true\" pipeline_memory/schema.sql (2)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The audit-memory DDL was applied to the live Supabase project (poeyztlmsawfoqlanucc) without error, pipeline_memory remains an exposed schema, and the schema cache was reloaded -- owner-authorized apply via the Supabase connector, Task 2's checkpoint"
    requirement: "AUD-01"
    verification:
      - kind: manual_procedural
        ref: "Owner instruction 2026-09-11 delegating the apply; migration audit_memory_findings_lifecycle_views (20260912023008) applied, 18 statements, 0 errors; catalog read-back confirms RLS enabled, policies present, anon/authenticated blocked on all 4 objects; PostgREST probe returns 401/42501 for anon (schema exposed, access correctly denied) -- see Checkpoint Resolutions below"
        status: pass
    human_judgment: true
    rationale: "DDL application to the live production Supabase project is a protected-area action (D-11); no agent session holds that privilege independently. The owner's explicit delegation and the resulting catalog/PostgREST evidence are the verification of record."
  - id: D3
    description: "The two views and acknowledge_finding behave correctly against live synthetic data: open_findings returns only open/resurfaced rows, finding_history_by_wr returns full per-WR history via a left join that does not drop event-less findings, and acknowledge_finding both records a manual transition with its event row and rejects invalid input -- AUD-03's live verification of record"
    requirement: "AUD-03"
    verification:
      - kind: manual_procedural
        ref: "Owner-delegated 7-run synthetic lifecycle read-back (wr SMOKE-13-05) exercising opened/seen/fixed/reopened/acknowledged/resurfaced plus two Pitfall-5 no-op probes (empty pairs, wrong check_id); residual row count 0 after cleanup -- see Checkpoint Resolutions below"
        status: pass
    human_judgment: true
    rationale: "No automated harness exists in this repository for live Supabase view content (the plan's own Flagged Assumption); the owner's SQL-editor read-back, delegated to the orchestrating session's Supabase connector at the owner's explicit instruction, is this repository's stated verification of record for AUD-03's SQL half."

duration: ~10min (continuation session; Task 1 executed in a prior session)
completed: 2026-09-11
status: complete
---

# Phase 13 Plan 05: Audit-Memory Views, Acknowledge Helper, RLS, and Live Apply Summary

**The audit-memory read surface (`open_findings`, `finding_history_by_wr`), the owner-only `acknowledge_finding` manual-transition helper, and full RLS/revoke coverage are now live in Supabase project `poeyztlmsawfoqlanucc`, applied and read back by the owner via the Supabase connector under an explicit delegation instruction.**

## Performance

- **Duration:** ~10 min (this continuation session recorded the owner's resolution evidence and closed out state; Task 1's implementation work ran in a prior session and is already committed as `50a8a5e`)
- **Started:** 2026-09-11
- **Completed:** 2026-09-11
- **Tasks:** 3 (Task 1 `type="auto"`; Tasks 2-3 `type="checkpoint:human-verify"`, both resolved)
- **Files modified:** 2 (Task 1 only; Tasks 2-3 produced no repo changes)

## Accomplishments

- Task 1 (prior session, commit `50a8a5e`): appended the `open_findings` and `finding_history_by_wr` views (both `WITH (security_invoker = true)`, both with an explicit `REVOKE ALL ... FROM anon, authenticated`), the `acknowledge_finding(p_finding_key, p_actor, p_transition, p_note)` helper (`SET search_path = ''`, schema-qualified, no dynamic SQL, validates transition and key existence and RAISEs on either miss), RLS enable + `service_role_all` policies for `audit_finding`/`audit_finding_event`, and the D-13-A header-comment closure to `pipeline_memory/schema.sql`; extended `tests/test_audit_findings_sql_contract.py` with the matching structural assertions (15 passed).
- Task 2 (this session, owner-resolved): the owner instructed the orchestrating session to apply the audit-memory DDL to the live project via the Supabase connector. Applied as one tracked migration (`audit_memory_findings_lifecycle_views`, version `20260912023008`, 18 statements, 0 errors). Post-apply catalog read-back confirmed RLS enabled and `service_role_all` policies present on both tables, both views carry `security_invoker = true`, `anon`/`authenticated` have no table/schema privileges on any of the 4 new objects, and `acknowledge_finding`'s `EXECUTE` is correctly not granted to `PUBLIC`. Schema cache reloaded; a live PostgREST probe with the anon key returned `401 / 42501` (schema exposed, access correctly denied — not the PGRST106 footgun the checkpoint warned about). `upsert_audit_findings` keeps the same PUBLIC-executable convention as the two pre-existing bulk RPCs, which remains safe because `anon`/`authenticated` lack schema `USAGE` on `pipeline_memory`.
- Task 3 (this session, owner-resolved): the owner ran the full 7-step synthetic lifecycle read-back (fake WR `SMOKE-13-05`) against the live views and helper: opened → seen → two Pitfall-5 no-op probes (empty pairs; wrong `check_id`, confirming a mismatched check cannot close a finding) → fixed → reopened → acknowledged (row disappears from `open_findings`) → resurfaced. `finding_history_by_wr` showed the full ordered transition history (`opened, seen, fixed, reopened, acknowledged, resurfaced`) with the manual event's `run_id` correctly tagged `manual:smoke-test`, `first_seen_run` preserved across the whole sequence, and `severity_rank` correctly derived. All synthetic rows deleted; residual count confirmed 0. `AUDIT_MEMORY_ENABLED` confirmed still unset everywhere — no write path was enabled by this apply.

## Task Commits

Each task was committed atomically:

1. **Task 1: Views, the acknowledge helper, RLS, and the D-13-A header closure** - `50a8a5e` (feat)
2. **Task 2: [BLOCKING] Owner applies the audit-memory DDL to the live project** - RESOLVED, no repo commit (live Supabase DDL apply only; see Checkpoint Resolutions)
3. **Task 3: Owner reads back the two views and the acknowledge helper (AUD-03)** - RESOLVED, no repo commit (live read-back only; see Checkpoint Resolutions)

**Plan metadata:** (this commit)

## Checkpoint Resolutions

Both checkpoints in this plan are owner-only, protected-area actions per decision D-11 ("Do not apply any DDL to the live Supabase project from an agent session; the owner applies it"). The owner explicitly delegated the apply and read-back to the orchestrating session's Supabase connector rather than performing them manually — the same apply-delegated pattern already established in Phase 12 (D-12-E) and Phase 14 (D-14-07-APPLIED, O-14-C-APPLIED, D-14-13-DDL-APPLIED).

**Owner instruction (verbatim, 2026-09-11):** "apply the supabase edits yourself using our supbase connector and do this for me"

### Task 2 evidence — DDL applied to live project `poeyztlmsawfoqlanucc` (Smarthsheet-Resiliency-Offloaded-Data)

- **Pre-state:** `pipeline_memory` schema existed with `group_state`, `row_event`, `row_state`, `run_ledger`, `sheet_registry`, `upsert_rows_bulk`, `purge_row_event_slice`; no `audit_finding*` objects.
- **Applied** via Supabase MCP `apply_migration` as ONE tracked migration: name `audit_memory_findings_lifecycle_views`, version `20260912023008`, body = `pipeline_memory/schema.sql` lines 681-1131 at commit `50a8a5e`, verbatim. Statement count: 18 top-level DDL statements (2 `CREATE TABLE IF NOT EXISTS`, 3 `CREATE INDEX IF NOT EXISTS`, 2 `CREATE OR REPLACE FUNCTION`, 2 `ALTER TABLE ENABLE RLS`, 2 `DROP POLICY IF EXISTS`, 2 `CREATE POLICY`, 2 `CREATE OR REPLACE VIEW`, 3 `REVOKE`). Result: success, no errors.
- **Post-apply catalog read-back:** tables `audit_finding` + `audit_finding_event` with `rowsecurity=true`; policies `service_role_all` on both, roles={service_role}; indexes `idx_audit_finding_status`, `idx_audit_finding_wr_week`, `idx_audit_finding_event_key_observed`; views `open_findings` + `finding_history_by_wr` with `reloptions security_invoker=true`; functions `upsert_audit_findings` + `acknowledge_finding` with `proconfig search_path=""`. `has_table_privilege` SELECT: anon=false, authenticated=false, service_role=true on all four relations. `has_function_privilege` EXECUTE on `acknowledge_finding`: anon=false, authenticated=false, service_role=false (PUBLIC revoked as designed; owner calls it from the SQL editor). `upsert_audit_findings` EXECUTE: PUBLIC default (true for all three) — identical to the pre-existing `upsert_rows_bulk` and `purge_row_event_slice` convention; anon/authenticated have NO `USAGE` on schema `pipeline_memory` (`has_schema_privilege` false), so it is unreachable to them.
- **Schema cache:** `NOTIFY pgrst, 'reload schema'` sent. PostgREST probe with the public anon key: `GET /rest/v1/open_findings` (`Accept-Profile: pipeline_memory`) → HTTP 401 code 42501 "permission denied for schema pipeline_memory" (schema IS exposed; anon correctly blocked — NOT PGRST106). `POST rpc/acknowledge_finding` and `rpc/upsert_audit_findings` with `{}` → PGRST202 (no-args signature mismatch, i.e. functions present in the cache).

### Task 3 evidence — live lifecycle read-back (single implicit transaction, synthetic wr `SMOKE-13-05`, finding_key `smoke-13-05-key`, all rows deleted at the end; residual count 0)

- run1 findings=[F], pairs=[] → opened=1
- run2 findings=[F], pairs=[(rate_sanity_mismatch,SMOKE-13-05,2026-09-06)] → seen=1
- run3 findings=[], pairs=[] → all zero (empty pairs closes nothing)
- run4 findings=[], pairs=[(price_variance_anomaly, same wr/week)] → all zero (wrong check_id closes nothing, Pitfall 5)
- run5 findings=[], pairs=[(rate_sanity_mismatch, same wr/week)] → fixed=1
- run6 findings=[F], pairs=[same] → reopened=1
- `acknowledge_finding('smoke-13-05-key','smoke-test','acknowledged','smoke')` → `open_findings` rows for wr = 0
- run7 findings=[F], pairs=[] → resurfaced=1
- `open_findings` row: status=resurfaced, severity_rank=2 (severity medium), first_seen_run=smoke:13-05:run1 (preserved), last_seen_run=smoke:13-05:run7
- `finding_history_by_wr` transitions in event_id order: [opened, seen, fixed, reopened, acknowledged, resurfaced]; the acknowledged event's `event_run_id` = 'manual:smoke-test'
- cleanup: residual rows in `audit_finding` + `audit_finding_event` for the smoke key = 0
- `AUDIT_MEMORY_ENABLED` remains unset everywhere; no write path enabled by this apply.

## Files Created/Modified

- `pipeline_memory/schema.sql` (modified, Task 1, commit `50a8a5e`) - `open_findings`/`finding_history_by_wr` views, `acknowledge_finding` function, RLS/revoke coverage for the two new tables, D-13-A header closure
- `tests/test_audit_findings_sql_contract.py` (modified, Task 1, commit `50a8a5e`) - structural assertions for the views, `acknowledge_finding`, RLS coverage, and the D-13-A header note

No files were modified by Tasks 2 or 3 — both are live-Supabase-only actions per D-11.

## Decisions Made

See `key-decisions` in frontmatter. In short: the owner explicitly delegated both protected-area checkpoints to the orchestrating session's Supabase connector rather than performing them manually from the dashboard; the apply was tracked as one named migration rather than raw ad hoc SQL; and `AUDIT_MEMORY_ENABLED` was confirmed to remain unset before and after the apply, so the write path stays dormant per the plan's explicit prohibition.

## Deviations from Plan

**1. [Owner-authorized deviation, not a Rule 1-4 auto-fix] Checkpoint execution delegated to the Supabase connector instead of the owner's own dashboard session**

- **Found during:** Tasks 2 and 3
- **Context:** The plan scopes both checkpoints as strictly owner-only (D-11: "an agent session never holds that privilege") and instructs the executor to *present* the SQL and *wait* for the owner to run it manually.
- **What happened instead:** The owner, via the orchestrator, gave the explicit verbatim instruction "apply the supabase edits yourself using our supbase connector and do this for me," directing the orchestrating session to perform the apply and read-back itself using the Supabase MCP connector.
- **Why this is not a plan violation:** This is the same apply-delegated pattern already precedented and recorded in this project's own decision log for prior protected-area DDL applies (D-12-E, D-14-07-APPLIED, O-14-C-APPLIED, D-14-13-DDL-APPLIED) — an explicit, in-the-moment owner authorization overriding the plan's default "owner does it by hand" assumption, not an agent unilaterally bypassing D-11.
- **Verification:** Full statement-count and catalog read-back evidence recorded above; nothing was executed without the owner's direct instruction.
- **Committed in:** No commit — live Supabase DDL apply and read-back produce no repo diff.

---

**Total deviations:** 1 (owner-authorized checkpoint delegation, not an auto-fix under Rules 1-4)
**Impact on plan:** None on repo state. The live database now matches the plan's intended end state exactly, with full evidence recorded for both checkpoints.

## Issues Encountered

None. Both checkpoints resolved cleanly on the first attempt; no statement errored, no PGRST106, no unexpected privilege grant, and no read-back result diverged from the plan's stated expectation.

## User Setup Required

None remaining. The one external service configuration this plan required (applying the DDL to the live Supabase project) is complete — see Checkpoint Resolutions above. `AUDIT_MEMORY_ENABLED` stays unset; flipping the write path on is a separate, later owner decision per the plan's explicit prohibition.

## Next Phase Readiness

- AUD-01 is now complete (shared-ID gate cleared: this plan is the only remaining declaring plan for AUD-01 that had not yet finished). AUD-03 stays `Pending` in `REQUIREMENTS.md` — `requirements.ready-ids` reports it `blocked`, i.e. plan 13-06 also declares AUD-03 and has not yet completed; it will flip once 13-06's SUMMARY lands.
- The live `pipeline_memory` schema now carries the complete Phase 13 audit-memory surface: both tables, `upsert_audit_findings`, `acknowledge_finding`, and both views, all RLS-protected and read-back-verified. Plan 13-06 can build on a fully live, fully verified schema.
- No blockers.

## Self-Check: PASSED

- `pipeline_memory/schema.sql` exists on disk: FOUND
- `tests/test_audit_findings_sql_contract.py` exists on disk: FOUND
- Commit `50a8a5e` present: `git log --oneline --all | grep -q 50a8a5e` → FOUND
- `python -m pytest tests/test_audit_findings_sql_contract.py -q` re-run this session: 15 passed → PASS
- Owner checkpoint evidence (Task 2 and Task 3) recorded verbatim above, matching the resolution supplied by the orchestrator → PASS

---
*Phase: 13-audit-memory*
*Completed: 2026-09-11*
