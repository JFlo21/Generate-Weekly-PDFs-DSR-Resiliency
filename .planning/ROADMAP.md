# Roadmap: Generate-Weekly-PDFs-DSR-Resiliency

## Milestones

- ✅ **v1.0 Subcontractor Rate Logic** — Phases 01 + 01.1 (shipped 2026-05-20).
  Full detail archived in [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).
- 📋 **v1.1 Backend Migration + Artifact Explorer** — Phase 2 (pre-migration
  ADR / MIG-01) + the Railway → Render execution and Artifact Explorer
  redesign. Scope tracked in `milestones/v1.0-REQUIREMENTS.md` (v1.1-deferred
  section). Promote via `/gsd-new-milestone`.

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

- [ ] **Phase 2: Railway → Render Pre-Migration ADR** (MIG-01) — file
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
| 01.1. Helper-Shadow Rescue (INSERTED)            | v1.0      | 5/5   | ✅ Shipped (pending live UAT) | 2026-05-20 |
| 2. Railway → Render Pre-Migration ADR            | v1.1      | 0/TBD | 📋 Planned (deferred)         | -          |
| —. Migration execution + Artifact Explorer       | v1.1      | 0/TBD | 📋 Planned (deferred)         | -          |
