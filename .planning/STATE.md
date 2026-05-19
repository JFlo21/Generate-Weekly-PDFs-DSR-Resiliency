---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Subcontractor Rate Logic
status: executing
stopped_at: Phase 1.1 context gathered
last_updated: "2026-05-19T22:51:36.947Z"
last_activity: 2026-05-19 -- Phase 01.1 planning complete
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 14
  completed_plans: 14
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** The production Smartsheet → Excel → Smartsheet
attachment pipeline runs every 2 hours on weekdays and ships
billing-grade Excel reports without regression.
**Current focus:** Phase 1.1 — Subcontractor Helper-Shadow Rescue + Variant Partition + Claim-History Attribution (urgent hotfix; Phase 01 remains complete and merged)

## Current Position

Phase: 1.1 (Subcontractor Helper-Shadow Rescue + Variant Partition + Claim-History Attribution) — INSERTED, awaiting /gsd-discuss-phase
Plan: 0 of TBD plans implemented (decomposition pending)
Status: Ready to execute
Last activity: 2026-05-19 -- Phase 01.1 planning complete
Prior phase: Phase 01 (Subcontractor Rate Logic Modification) — COMPLETE, 14 of 14 plans shipped

Progress: [█░░░░░░░░░] 50% across v1.0 milestone (Phase 01 ✅; Phase 1.1 ⏳; Phase 2 DEFERRED)

## Performance Metrics

**Velocity:**

- Total plans completed: 14
- Average duration: ~15 min (estimated for gap-closure plans 01-07..01-14)
- Total execution time: ~3.9 hours (6 original plans ~114 min + 8 gap-closure plans ~120 min)

**By Phase:**

| Phase                         | Plans | Total    | Avg/Plan |
|-------------------------------|-------|----------|----------|
| 01 — Subcontractor Rate Logic |    14 | ~234 min | ~17 min  |

**Recent Trend:**

- All 14 plans complete (6 original + 8 gap-closure)
- Trend: ✅ Phase 01 gap closure complete; all 12 actionable findings addressed; CLAUDE.md Living Ledger entry committed

*Updated after each plan completion*

## Accumulated Context

### Roadmap Evolution

- Phase 1.1 inserted after Phase 1: Subcontractor Helper-Shadow Rescue + Variant Partition + Claim-History Attribution — urgent hotfix for three post-Phase-1 production bugs diagnosed via 2-cycle /gsd-debug session (URGENT)

### Decisions

Decisions are logged in PROJECT.md `<decisions>` table. Bootstrapped
from `.planning/intel/decisions.md`, which contains ~30 dated
ADR-equivalent rules from `CLAUDE.md` Living Ledger plus 8 SPEC-level
decisions. All are operative-locked per the
`.planning/INGEST-CONFLICTS.md` WARNING gate (user confirmed
default-yes).

Recent decisions affecting Phase 1:

- [2026-04-25 14:00] `freeze_row` parallelization contract — new
  variants must extend the same `ThreadPoolExecutor` pattern in the
  main group loop.

- [2026-04-25 12:00] `billing_audit/schema.sql` DDL must ship in the
  same PR — SUB-07 `variant` column in `pipeline_run` is bound by
  this rule.

- [2026-04-24 14:30] CSV-side rate recalc retired at workflow layer
  — Phase 1 must NOT re-introduce `RATE_CUTOFF_DATE` / `NEW_RATES_CSV`
  / `OLD_RATES_CSV`; new subcontractor rates load from
  `data/subcontractor_rates.csv` instead.

- [2026-04-24 11:30] `RATE_RECALC_SKIP_ORIGINAL_CONTRACT` guard —
  pattern for SUB-06's "no subcontractor logic on ORIG sheets"
  requirement.

- [2026-04-23 21:00 round-9] Source-side WR collision quarantine key
  is the sanitized WR alone — Phase 1 must extend (not replace) the
  existing pre-scan to cover `_AEPBillable` and `_ReducedSub`.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- `.planning/INGEST-CONFLICTS.md` INFO #8: pre-migration ADR for
  Railway → Render is missing under `memory-bank/adr/`. **Addressed
  by Phase 2** (MIG-01). Phase 2 is DEFERRED (out of v1.0 scope).

- `data/subcontractor_rates.csv` was authored as part of Plan 01-01
  (17 columns, 3691 priced CUs, currency-formatted, fingerprint
  `e4941a5e86c4f8ce`). ✅ Resolved.

- **Operator action required at merge time:** apply
  `billing_audit/schema.sql` to the deployed Supabase project so
  `billing_audit.pipeline_run.variant TEXT` lands before the first
  scheduled production run after Phase 1 ships. Statement is
  `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT;`
  (idempotent). Documented in the new runbook section under
  "How it impacts operators → One-time setup".

- **Step B real-data SKIP_UPLOAD price-write gate deferred** to the
  next scheduled GitHub Actions production run (per Warning 10's
  documented fallback verification surface). Local operator env
  lacked `SMARTSHEET_API_TOKEN`. Risk envelope bounded by the
  kill-switch default-ON + Plan 3's unit + integration tests.

## Deferred Items

Items acknowledged and carried forward to v1.1+:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Backend migration | REQ-railway-render-migration | Deferred to v1.1 | 2026-05-14 (planning bootstrap) |
| Backend migration | REQ-migration-staging-verification | Deferred to v1.1 | 2026-05-14 |
| Backend migration | REQ-migration-decommission | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-artifact-explorer-v1 | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-excel-styled-renderer | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-cross-artifact-search | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-backend-routes-for-explorer | Deferred to v1.1 | 2026-05-14 |

## Session Continuity

Last session: 2026-05-19T21:22:16.678Z
Stopped at: Phase 1.1 context gathered

Next step: `/gsd-discuss-phase 1.1` to gather full context and formalize SUB-08..SUB-12 requirements, then `/gsd-plan-phase 1.1` to decompose into atomic plans.

Operator items still pending (carried forward from Phase 01):

- Apply `billing_audit/schema.sql` to Supabase before the first scheduled production run after merge of Phase 01 (PR #203) — still required.
- Step B real-data SKIP_UPLOAD price-write spot-check (deferred to scheduled GHA run OR local re-run with rotated token).
- Watch p01-hotfix-followups.md thread for AEP/ReducedSub byte-divergence confirmation on next 2-3 post-PR-#206 cron runs (independent of Phase 1.1).

Phase 1.1 inputs ready:

- Debug session artifact: `.planning/debug/sub-helper-shadow-missing.md` (2-cycle Root Cause Report)
- Hotfix thread: `.planning/threads/p01-hotfix-followups.md`
- Routing matrix decision: Statement #1 (codified in ROADMAP Phase 1.1 success criterion 1)
- Plan 01-03 Test 1 override decision: subcontractor rows partition (not additive); primary rows unchanged
- Bug C scope: billing_audit claim-history attribution on subcontractor workflow only

Resume file: .planning/phases/01.1-subcontractor-helper-shadow-rescue/01.1-CONTEXT.md
