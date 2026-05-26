# Roadmap: Generate-Weekly-PDFs-DSR-Resiliency

## Milestones

- ✅ **v1.0 Subcontractor Rate Logic** — Phases 01 + 01.1 (shipped 2026-05-20).
  Full detail archived in [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).
- 🔧 **v1.0 hotfix line** — Phase 2 (Attribution Bulk-Prefetch + Historical
  Claimer Remediation). Blocking fix for the claim-attribution week-scope /
  Sub-project E interaction shipped after v1.0.
- 📋 **v1.1 Backend Migration + Artifact Explorer** — the Railway → Render
  pre-migration ADR (MIG-01) + the Railway → Render execution and Artifact
  Explorer redesign. Scope tracked in `milestones/v1.0-REQUIREMENTS.md`
  (v1.1-deferred section). Promote via `/gsd-new-milestone` (phases numbered
  on formalization).

## Phases

<details>
<summary>✅ v1.0 Subcontractor Rate Logic (Phases 01 + 01.1) — SHIPPED 2026-05-20</summary>

- [x] **Phase 01: Subcontractor Rate Logic Modification** (14/14 plans) —
  two new Excel variants (`_AEPBillable`, `_ReducedSub`) for subcontractor
  WR groups, dual-target routing, shadow-foreman/helper support. Original
  6 plans + 8 gap-closure plans (CR/WR/IN review findings).
- [x] **Phase 01.1 (INSERTED): Subcontractor Helper-Shadow Rescue + Variant
  Partition + Claim-History Attribution** (5/5 plans) — hotfix for three
  post-Phase-1 production bugs (pre-acceptance rescue, variant partitioning,
  PPP cleanup whitelist) + per-row claim-history attribution.

Full phase details, success criteria, and plan lists:
[`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).

</details>

### 📋 v1.1 Backend Migration + Artifact Explorer (Planned)

Carried forward from v1.0's deferred scope (see
`milestones/v1.0-REQUIREMENTS.md`). To be formalized via
`/gsd-new-milestone`.

- [ ] **Railway → Render Pre-Migration ADR** (MIG-01, renumbered on v1.1
  formalization) — file
  `memory-bank/adr/0001-railway-to-render.md` locking Render Starter,
  in-memory LRU search, v1 download = original `.xlsx`. Closes
  `.planning/INGEST-CONFLICTS.md` INFO #8.
- [ ] Railway → Render backend migration execution (`REQ-railway-render-migration`,
  `REQ-migration-staging-verification`, `REQ-migration-decommission`).
- [ ] Artifact Explorer redesign (`REQ-artifact-explorer-v1`,
  `REQ-excel-styled-renderer`, `REQ-cross-artifact-search`,
  `REQ-backend-routes-for-explorer`).

## Progress

| Phase                                            | Milestone | Plans | Status                       | Completed  |
|--------------------------------------------------|-----------|-------|------------------------------|------------|
| 01. Subcontractor Rate Logic Modification        | v1.0      | 14/14 | ✅ Shipped (pending live UAT) | 2026-05-20 |
| 01.1. Helper-Shadow Rescue (INSERTED)            | v1.0      | 6/6 | Complete    | 2026-05-20 |
| 02. Attribution Bulk-Prefetch + Remediation      | v1.0 hotfix | 4/6 | Gap closure (02-05, 02-06)   | 2026-05-26 |
| —. Railway → Render Pre-Migration ADR            | v1.1      | 0/TBD | 📋 Planned (deferred, renumber on v1.1) | - |
| —. Migration execution + Artifact Explorer       | v1.1      | 0/TBD | 📋 Planned (deferred)         | -          |

### Phase 2: Attribution Bulk-Prefetch + Historical Claimer Remediation

**Goal:** Every generated Excel file is partitioned/named by the real frozen
claimer from `billing_audit.attribution_snapshot` (no `_NO_MATCH` /
`Unknown_Foreman` for rows that have a frozen claimer), with no time-budget
regression, so Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`, clean
filenames) can be safely re-activated.
**Requirements**: 6 locked in 02-SPEC.md (SPEC-1 bulk prefetch; SPEC-2 correct
claimer on every file; SPEC-3 no time-budget regression; SPEC-4 recent-window
remediation; SPEC-5 safe Sub-project E re-activation; SPEC-6 regression coverage).
**Depends on:** Phase 01.1 (and the shipped Foundation A / B / C / D / E
attribution work tracked in `docs/superpowers/`)
**Plans:** 6 plans (4 executed + 2 gap-closure from 02-REVIEW.md)

Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Bulk RPC (`lookup_attribution_bulk`) + fail-safe `prefetch_attribution` reader + map-aware `resolve_claimer` (Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md — Wire the 4 pre-pass sites to the bulk map + drop `ATTRIBUTION_RESOLUTION_WEEKS` + historical-claimer RED/GREEN regression (Wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-03-PLAN.md — Default-OFF, dry-run-first, isolated `run_claimer_remediation` garbage sweep (TARGET + PPP, live-identity exempt) (Wave 3)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 02-04-PLAN.md — E re-activation runbook (D-09/D-10/D-11 gated flip) + Living Ledger entry (Wave 4)

**Gap closure** *(from 02-REVIEW.md: 1 BLOCKER + 5 WARNING + 4 INFO)*
- [ ] 02-05-PLAN.md — CR-01 graceful degradation (`rpc_missing` + default-ON `ATTRIBUTION_BULK_PREFETCH_FALLBACK`) + WR-01 sanitization key + WR-03 comment + WR-05 sub-helper observability + IN-01 dead imports (Wave 1, gap-closure)
- [ ] 02-06-PLAN.md — WR-02 advanced_options activation path + WR-04 `_Unknown_Foreman` protection + IN-02 counter + IN-03 runbook quote + IN-04 datetime + Living Ledger entry (Wave 2, gap-closure; depends_on 02-05)
