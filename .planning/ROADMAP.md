# Roadmap: Generate-Weekly-PDFs-DSR-Resiliency

## Overview

v1.0 milestone delivers the **Subcontractor Rate Logic Modification** —
an additive change to `generate_weekly_pdfs.py` that introduces two new
Excel variants (`_AEPBillable` priced at the 3%-increase AEP contract
awarded 2026-04-12, and `_ReducedSub` priced at the 13%-reduced
subcontractor rate Linetec pays its subs) for subcontractor-folder
work-request groups, with full shadow-foreman/helper support. Scope is
strictly subcontractor-folder sheets; ORIG-folder and VAC-crew flows
remain untouched. A second focused phase delivers the missing
Railway → Render pre-migration ADR so the migration milestone has its
foundational decision record on file before execution begins. The
migration itself, the Artifact Explorer redesign, and the five new
Express explorer routes are tracked as v1.1+ scope.

## Milestones

- 🚧 **v1.0 Subcontractor Rate Logic** — Phase 1 (active, gating).
  Phase 2 (MIG-01) is DEFERRED — captured for traceability but does
  NOT gate v1.0 completion.
- 📋 **v1.1 Backend Migration + Artifact Explorer** — Phases 3-N
  (planned, scope in `REQUIREMENTS.md` v2 section). The Phase 2
  pre-migration ADR deliverable, if completed during v1.0, becomes
  this milestone's prerequisite.

## Phases

**Phase Numbering:**
- Integer phases (1, 2): Planned milestone work
- Decimal phases (e.g., 1.1, 2.1): Urgent insertions inserted via
  `/gsd-insert-phase` (none yet)

- [ ] **Phase 1: Subcontractor Rate Logic Modification** — Two new Excel
  variants (`_AEPBillable`, `_ReducedSub`) for subcontractor WR groups,
  routed to original-PPP and new-subcontractor-PPP target sheets, with
  shadow-foreman/helper support
- [ ] **Phase 2 (DEFERRED): Railway → Render Pre-Migration ADR** — File the
  missing `memory-bank/adr/` record locking Render Starter, in-memory
  LRU search, and v1 download = original `.xlsx`. **Does not gate v1.0 completion** — preserved here so MIG-01 stays mapped, but the full Railway → Render execution lives in REQUIREMENTS.md v2 section.

## Phase Details

### Phase 1: Subcontractor Rate Logic Modification
**Goal**: An operator runs the weekly workflow on a Smartsheet
subcontractor folder and sees two new Excel variants per qualifying WR
group landing on the correct target sheets, with shadow-foreman events
producing both variant-tagged helper files — and zero impact to
existing primary, helper, VAC-crew, or ORIG-folder outputs.
**Depends on**: Nothing (first phase). Foundational constraints come
from existing pre-locked decisions in PROJECT.md and the production
pipeline as-is.
**Requirements**: SUB-01, SUB-02, SUB-03, SUB-04, SUB-05, SUB-06,
SUB-07
**Success Criteria** (what must be TRUE):
  1. For every subcontractor-folder WR group with
     `Snapshot Date >= 2026-04-12`, the workflow produces an
     `_AEPBillable` Excel file whose row totals match the
     `new_*_price` columns of `data/subcontractor_rates.csv` for that
     row's CU code + work type, and the file lands as an attachment
     on `TARGET_SHEET_ID=5723337641643908` (observable in Smartsheet's
     row attachment panel).
  2. For every subcontractor-folder WR group (regardless of snapshot
     date), the workflow produces a `_ReducedSub` Excel file priced
     via the `reduced_*_price` CSV columns, attached to BOTH
     `5723337641643908` AND `SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908`
     (two attachment uploads per `_ReducedSub` file, observable).
  3. When a foreman change is detected on a subcontractor WR (the
     existing helper-foreman rule fires), TWO shadow files appear in
     `generated_docs/<week>/` named `_AEPBillable_Helper_<name>` and
     `_ReducedSub_Helper_<name>`, each routed to its variant's target
     sheet (observable as two new attachments).
  4. `pytest tests/` passes including: new tests covering
     subcontractor variant generation, CSV rate loader schema
     validation, hash-key extension with the new variant strings,
     `build_group_identity` round-trip for `_AEPBillable` and
     `_ReducedSub` (and their `_Helper_<name>` forms),
     `target_map` collision quarantine across new variants, and
     `freeze_row` `variant` attribution captured in
     `pipeline_run`. No existing test regresses.
  5. A scheduled weekly workflow run completes inside
     `timeout-minutes: 195` and emits zero Sentry events tagged with
     the new variant scope; existing VAC-crew, ORIG-folder, and
     primary outputs are byte-identical to the run immediately before
     the change (verified via hash-history diff on a TEST_MODE run).
**Plans**: 6 plans

Plans:
- [ ] 01-01-PLAN.md — CSV move to canonical path + subcontractor rate loader + env-var scaffolding + fingerprint
- [ ] 01-02-PLAN.md — Extend build_group_identity + calculate_data_hash for the 4 new variants; PII markers + collision-quarantine regression coverage
- [ ] 01-03-PLAN.md — Variant tagging in group_source_rows + Excel generation with CSV-driven prices + missing-CU WARNING + kill-switch
- [ ] 01-04-PLAN.md — Dual-target routing for _ReducedSub via SUBCONTRACTOR_PPP_SHEET_ID; independent collision quarantine on second target_map
- [ ] 01-05-PLAN.md — billing_audit pipeline_run.variant column DDL + freeze_row/emit_run_fingerprint variant kwarg
- [ ] 01-06-PLAN.md — Byte-identical regression test, production-safety validator pin, Docusaurus runbook update, human-verify checkpoint

### Phase 2: Railway → Render Pre-Migration ADR (DEFERRED — out of v1.0 scope)
**Status**: DEFERRED. Does not gate v1.0 milestone completion. The seven REQ-* requirements that drive the actual Railway → Render execution + Artifact Explorer redesign live in REQUIREMENTS.md "v2 Requirements" section and will be promoted by a future `/gsd-new-project` cycle. Phase 2 here exists to lock in the one small documentation deliverable (`MIG-01`) that should land before any of that v2 work begins.
**Goal**: A reviewer can open `memory-bank/adr/` and read a single
document that authoritatively records the locked Railway → Render
decisions, so the future migration milestone executes against an ADR
that exists in the codebase rather than a transition-plan SPEC alone.
**Depends on**: Nothing structural — independent of Phase 1. Can run
in parallel if desired.
**Requirements**: MIG-01
**Success Criteria** (what must be TRUE):
  1. `memory-bank/adr/0001-railway-to-render.md` exists in the repo
     and follows a standard ADR template (Status / Context /
     Decision / Consequences) covering: Render Web Service Starter
     plan ($7/mo, Oregon, root `portal`, build `npm ci`, start
     `node server.js`, health `/health`, Node `>=20 <23`), in-memory
     LRU search index (`artifactCache max:50 TTL 15min`,
     `searchIndex max:200 TTL 60min`), and v1 download surface =
     original `.xlsx` passthrough only.
  2. The ADR explicitly cross-references
     `docs/railway-to-render-transition-plan.md` (the operative SPEC),
     `.planning/decisions.md` (synthesized rules), and the `decisions
     .md` 2026-04-24 14:30 retention policy for the retired CSV-side
     rate recalc env vars.
  3. `website/` Docusaurus build (`npm run typecheck && npm run build`
     in `website/`) succeeds with the new ADR referenced from the
     runbook (or explicitly NOT referenced, with a noted rationale)
     so cross-link integrity is preserved.
  4. `.planning/INGEST-CONFLICTS.md` INFO #8 (missing pre-migration
     ADR deliverable) is resolvable — a subsequent re-ingest would
     classify the new ADR as `type: ADR, locked: true` and close the
     gap.
**Plans**: TBD

Plans:
- [ ] 02-01: TBD (to be decomposed via `/gsd-plan-phase 2`)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Subcontractor Rate Logic Modification | 0/6 | Not started | - |
| 2. Railway → Render Pre-Migration ADR (DEFERRED) | 0/TBD | Deferred — out of v1.0 scope | - |
