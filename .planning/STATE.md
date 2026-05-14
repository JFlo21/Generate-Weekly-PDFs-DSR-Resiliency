# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** The production Smartsheet → Excel → Smartsheet
attachment pipeline runs every 2 hours on weekdays and ships
billing-grade Excel reports without regression.
**Current focus:** Phase 1 — Subcontractor Rate Logic Modification

## Current Position

Phase: 1 of 2 (Subcontractor Rate Logic Modification)
Plan: 0 of TBD in current phase
Status: Ready to discuss (run `/gsd-discuss-phase 1`)
Last activity: 2026-05-14 — bootstrapped `.planning/` from ingested
intel (PROJECT.md, REQUIREMENTS.md, ROADMAP.md created;
INGEST-CONFLICTS.md WARNING acknowledged — Living Ledger treated as
ADR-equivalent locked).

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: — min
- Total execution time: — hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: — (no execution history yet)

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
  by Phase 2** (MIG-01). Not blocking Phase 1 execution.
- `data/subcontractor_rates.csv` mentioned in orchestrator prompt
  must be authored (or confirmed present) before Phase 1 plan-level
  decomposition — SUB-04 depends on the file existing with the 9
  expected columns. Flagged for `/gsd-discuss-phase 1`.

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

Last session: 2026-05-14 (planning bootstrap)
Stopped at: Created `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`,
`.planning/ROADMAP.md`, and this `STATE.md` from the ingested intel
set. Living Ledger treated as ADR-equivalent locked per the
INGEST-CONFLICTS WARNING (user-confirmed). Ready for
`/gsd-discuss-phase 1`.
Resume file: None
