---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Subcontractor Rate Logic
status: Awaiting next milestone
stopped_at: v1.0 milestone completed and archived
last_updated: "2026-05-20T02:30:00.000Z"
last_activity: 2026-05-20 — Milestone v1.0 completed, archived, and tagged
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 19
  completed_plans: 19
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20 after v1.0 milestone)

**Core value:** The production Smartsheet → Excel → Smartsheet attachment
pipeline runs every 2 hours on weekdays and ships billing-grade Excel
reports without regression.
**Current focus:** Planning next milestone (v1.1 — Backend Migration +
Artifact Explorer).

## Current Position

Milestone: v1.0 Subcontractor Rate Logic — ✅ SHIPPED 2026-05-20 (archived + tagged)
Phase: —
Plan: —
Status: Awaiting next milestone
Last activity: 2026-05-20 — v1.0 completed and archived

Shipped: 2 gating phases (01 + inserted 01.1), 19 plans, 682 tests passing.
Audit: `tech_debt` (`milestones/v1.0-MILESTONE-AUDIT.md`). Full v1.0 detail in
`milestones/v1.0-ROADMAP.md` + `milestones/v1.0-REQUIREMENTS.md`.

## Performance Metrics

**Velocity:**

- Total plans completed (v1.0): 19 (Phase 01: 14, Phase 01.1: 5)
- Test suite at close: 682 passed / 26 skipped / 58 subtests (from 537 pre-milestone)

**By Phase:**

| Phase                                 | Plans | Status      |
|---------------------------------------|-------|-------------|
| 01 — Subcontractor Rate Logic         | 14/14 | ✅ Shipped   |
| 01.1 — Helper-Shadow Rescue (INSERTED)| 5/5   | ✅ Shipped   |

*Updated at milestone close.*

## Accumulated Context

### Decisions

Full decision log lives in PROJECT.md `<decisions>` table (~30 dated
ADR-equivalent rules from the CLAUDE.md Living Ledger + SPEC-level
decisions). All operative-locked. v1.0 added the Phase 1.1 partitioning
override (subcontractor rows partition, not additive), the Bug C D-12
fail-safe fall-back, and the pre-acceptance-rescue-generalization rule.

### Blockers/Concerns

[Open items affecting future work — resolved v1.0 blockers cleared at close]

- `.planning/INGEST-CONFLICTS.md` INFO #8: pre-migration ADR for
  Railway → Render still missing under `memory-bank/adr/`. Now tracked as
  MIG-01 in the v1.1 milestone (descoped from v1.0).

## Deferred Items

### v1.1 scope (carried forward from planning bootstrap)

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Migration pre-impl | MIG-01 (pre-migration ADR) | Deferred to v1.1 | 2026-05-20 (descoped from v1.0) |
| Backend migration | REQ-railway-render-migration | Deferred to v1.1 | 2026-05-14 |
| Backend migration | REQ-migration-staging-verification | Deferred to v1.1 | 2026-05-14 |
| Backend migration | REQ-migration-decommission | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-artifact-explorer-v1 | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-excel-styled-renderer | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-cross-artifact-search | Deferred to v1.1 | 2026-05-14 |
| Artifact Explorer | REQ-backend-routes-for-explorer | Deferred to v1.1 | 2026-05-14 |

### Open artifacts acknowledged at v1.0 close (2026-05-20)

Acknowledged and deferred per the milestone-close artifact audit (6 items).
All are deferred live-verification / watch-list items — none is failing code.

| Category | Item | Status |
|----------|------|--------|
| debug | sub-helper-shadow-missing | root_cause_found (fix shipped in Phase 01.1) |
| thread | p01-hotfix-followups | open (post-cron AEP/ReducedSub byte-divergence watch-list) |
| uat_gap | 01-HUMAN-UAT.md | partial (0 open scenarios; pending live cron) |
| uat_gap | 01.1-HUMAN-UAT.md | partial (0 open scenarios; pending live cron) |
| verification_gap | 01-VERIFICATION.md | human_needed (live-cron production observation) |
| verification_gap | 01.1-VERIFICATION.md | human_needed (live-cron production observation) |

**Operator actions still owed before flipping attribution on in prod:**
apply `billing_audit/schema.sql` to Supabase; data team deploys the
`lookup_attribution` RPC; Step B real-data SKIP_UPLOAD price-write spot-check.

## Operator Next Steps

- Start the next milestone with `/gsd-new-milestone` (v1.1 — Backend
  Migration + Artifact Explorer; fresh REQUIREMENTS.md will be created).
- Independently: review/commit the uncommitted `generate_weekly_pdfs.py`
  type-hint refinements (separate from this milestone close).
