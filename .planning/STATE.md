---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Subcontractor Rate Logic
status: ready_to_ship
stopped_at: Phase 01 complete — 14 plans shipped (6 original + 8 gap-closure); all BLOCKER/WARNING/INFO findings addressed; byte-identical regression tests pass; operator pre-merge actions documented.
last_updated: "2026-05-15T18:00:00.000Z"
last_activity: 2026-05-15 -- Phase 01 gap closure complete
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 14
  completed_plans: 14
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** The production Smartsheet → Excel → Smartsheet
attachment pipeline runs every 2 hours on weekdays and ships
billing-grade Excel reports without regression.
**Current focus:** Phase 01 — Subcontractor Rate Logic Modification

## Current Position

Phase: 01 (Subcontractor Rate Logic Modification) — COMPLETE
Plan: 14 of 14 plans implemented (6 original + 8 gap-closure)
Status: Ready to ship
Last activity: 2026-05-15 -- Phase 01 gap closure complete

Progress: [██████████] 100% (ready for PR merge)

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

Last session: 2026-05-15T18:00:00.000Z
Stopped at: Phase 01 gap closure complete — all 14 plans (6 original + 8 gap-closure) shipped. PR is ready for merge.

Next step: Merge PR, then operator applies `billing_audit/schema.sql` to Supabase before the first scheduled production run.

Operator items still pending (post-merge):

- Apply `billing_audit/schema.sql` to Supabase before the first scheduled production run after merge
- Step B real-data SKIP_UPLOAD price-write spot-check (deferred to scheduled GHA run OR local re-run with rotated token)

Resume file: None (Phase 01 complete)
