---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Subcontractor Rate Logic
status: executing
stopped_at: Phase 01 code review flagged 3 BLOCKERs (main-loop integration gaps not caught by unit tests). Implementation and tests are done across 6 plans; phase is NOT shippable until the BLOCKERs are addressed.
last_updated: "2026-05-15T03:21:40.846Z"
last_activity: 2026-05-15 -- Phase 01 planning complete
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 6
  completed_plans: 6
  percent: 90
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** The production Smartsheet → Excel → Smartsheet
attachment pipeline runs every 2 hours on weekdays and ships
billing-grade Excel reports without regression.
**Current focus:** Phase 01 — Subcontractor Rate Logic Modification

## Current Position

Phase: 01 (Subcontractor Rate Logic Modification) — GAPS FOUND (code review)
Plan: 6 of 6 plans implemented; 0 of N gap-closure plans (TBD)
Status: Ready to execute
Last activity: 2026-05-15 -- Phase 01 planning complete

Progress: [█████████░] 90% (implementation done; gap closure pending)

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: ~19 min
- Total execution time: ~1.9 hours (Plan 01 ~30m + Plan 02 ~30m + Plan 03 ~13m + Plan 04 ~9m + Plan 05 ~7m + Plan 06 ~25m)

**By Phase:**

| Phase                         | Plans | Total    | Avg/Plan |
|-------------------------------|-------|----------|----------|
| 01 — Subcontractor Rate Logic |     6 | ~114 min | ~19 min  |

**Recent Trend:**

- Last 5 plans: 30m → 30m → 13m → 9m → 7m → 25m (Plan 06 is regression-lock + docs, slightly slower due to human-verify checkpoint + Docusaurus build cycle)
- Trend: ✅ Phase 01 ships clean; kill switch default-ON for rollback safety; CLAUDE.md Living Ledger entry will append on merge

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

Last session: 2026-05-14T23:45:00.000Z
Stopped at: Phase 01 code review flagged 3 BLOCKERs (main-loop integration gaps not caught by unit tests). Implementation and tests are done across 6 plans; phase is NOT shippable until the BLOCKERs are addressed.

Next step: `/gsd-plan-phase 01 --gaps` — reads 01-VERIFICATION.md + 01-REVIEW.md and creates a focused gap-closure phase with the 3 BLOCKERs (and optionally the 6 WARNINGs) as plans.

Blocker summary (see 01-REVIEW.md for full detail):
  CR-01 — Helper-shadow variants' `file_identifier` falls through to User branch (attachment-skip optimization broken on `_AEPBillable_Helper_*` / `_ReducedSub_Helper_*` files; orphan accumulation on PPP sheet)
  CR-02 — `EXCLUDE_WRS` matcher doesn't recognize the 4 new variant group keys
  CR-03 — `WR_FILTER` mirror bug; Step B operator verification path silently broken

Operator items still pending (post-gap-closure):

- Apply `billing_audit/schema.sql` to Supabase before the first scheduled production run after merge
- Step B real-data SKIP_UPLOAD price-write spot-check (deferred to scheduled GHA run OR local re-run with rotated token)

Resume file: .planning/phases/01-subcontractor-rate-logic-modification/01-REVIEW.md
