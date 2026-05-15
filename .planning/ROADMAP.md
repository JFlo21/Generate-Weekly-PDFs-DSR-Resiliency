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

- [x] **Phase 1: Subcontractor Rate Logic Modification** — Two new Excel
  variants (`_AEPBillable`, `_ReducedSub`) for subcontractor WR groups,
  routed to original-PPP and new-subcontractor-PPP target sheets, with
  shadow-foreman/helper support. Original 6 plans completed 2026-05-14;
  post-merge code review (`/gsd-code-review 01`) flagged 3 BLOCKER +
  6 WARNING + 4 INFO findings. Gap-closure plans 01-07 through 01-14
  completed 2026-05-15 to close all 12 actionable findings (IN-03 is
  reference-only). Kill switch (`SUBCONTRACTOR_RATE_VARIANTS_ENABLED`)
  default-ON with `0` as the documented rollback path; per IN-04 / plan
  01-14 now also pinned in the workflow `env:` block.
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
SUB-07 (covered by plans 01-01..01-06); gap-closure plans 01-07..01-14
address review findings REVIEW-CR-01, REVIEW-CR-02, REVIEW-CR-03,
REVIEW-WR-01..WR-06, REVIEW-IN-01, REVIEW-IN-02, REVIEW-IN-04, and
the Living Ledger documentation rule (IN-03 is reference-only — not
a tracked finding).
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
     sheet (observable as two new attachments). Helper-shadow
     attachment identity matches correctly through
     `_has_existing_week_attachment` and
     `delete_old_excel_attachments` per plan 01-08 / CR-01 (the
     three-site identity consistency fix). Orphan accumulation on
     `SUBCONTRACTOR_PPP_SHEET_ID` is eliminated by the combination
     of CR-01 + WR-05 (PPP prefetch, plan 01-12) + WR-01 (PPP
     end-of-run cleanup, plan 01-13).
  4. `pytest tests/` passes including: new tests covering
     subcontractor variant generation, CSV rate loader schema
     validation, hash-key extension with the new variant strings,
     `build_group_identity` round-trip for `_AEPBillable` and
     `_ReducedSub` (and their `_Helper_<name>` forms),
     `target_map` collision quarantine across new variants, and
     `freeze_row` `variant` attribution captured in
     `pipeline_run`. No existing test regresses. Gap-closure plans
     added ~55-65 new tests across `tests/test_subcontractor_pricing.py`,
     `tests/test_security_audit_followup.py`, and
     `tests/test_performance_optimizations.py`.
  5. A scheduled weekly workflow run completes inside
     `timeout-minutes: 110` (with `TIME_BUDGET_MINUTES: 95`) and emits
     zero Sentry events tagged with the new variant scope; existing
     VAC-crew, ORIG-folder, and primary outputs are byte-identical to
     the run immediately before the change (verified via hash-history
     diff on a TEST_MODE run). `TestPhase1IntegrationRegression`
     continues to pass after all gap-closure plans land.
  6. `EXCLUDE_WRS` correctly suppresses all 7 group-key variants per
     WR (primary + helper + USER + vac_crew + the 4 new variants)
     per plan 01-07 / CR-02; `WR_FILTER` correctly retains 6 of those
     7 variants in TEST_MODE per CR-03 (matcher asymmetry preserved
     — _USER_ legacy clause is excluded from `_key_matches_wr` per
     pre-fix surface).
  7. Operator-facing rollback path is workflow-pinned: setting
     `SUBCONTRACTOR_RATE_VARIANTS_ENABLED='0'` in the workflow `env:`
     block disables ALL Phase 1 variant generation, leaving primary
     / helper / vac_crew / ORIG-folder pipelines unaffected (per
     plan 01-14 / IN-04).
**Plans**: 14 plans (6 original + 8 gap-closure)

Plans:
- [x] 01-01-PLAN.md — CSV move to canonical path + subcontractor rate loader + env-var scaffolding + fingerprint
- [x] 01-02-PLAN.md — Extend build_group_identity + calculate_data_hash for the 4 new variants; PII markers + collision-quarantine regression coverage
- [x] 01-03-PLAN.md — Variant tagging in group_source_rows + Excel generation with CSV-driven prices + missing-CU WARNING + kill-switch
- [x] 01-04-PLAN.md — Dual-target routing for _ReducedSub via SUBCONTRACTOR_PPP_SHEET_ID; independent collision quarantine on second target_map
- [x] 01-05-PLAN.md — billing_audit pipeline_run.variant column DDL + freeze_row/emit_run_fingerprint variant kwarg
- [x] 01-06-PLAN.md — Byte-identical regression test, production-safety validator pin, Docusaurus runbook update, human-verify checkpoint
- [x] 01-07-PLAN.md — Gap closure: CR-02 + CR-03 (mirror filter matchers extend to 4 new variant suffixes) + regression tests
- [x] 01-08-PLAN.md — Gap closure: CR-01 (helper-shadow identifier derivation at 3 main-loop sites) + regression test
- [x] 01-09-PLAN.md — Gap closure: WR-04 (explicit helper-shadow PII markers) + WR-06 (`__source_sheet_id` migration) + regression tests
- [x] 01-10-PLAN.md — Gap closure: WR-02 (PPP empty-string disable) + WR-03 (helper-shadow filename-suffix defensive raise) + doc update + regression tests
- [x] 01-11-PLAN.md — Gap closure: IN-01 (`AEP_BILLABLE_CUTOFF` env var with safe parse) + IN-02 (`qty_raw` coercion cleanup) + doc update + regression tests
- [x] 01-12-PLAN.md — Gap closure: WR-05 (PPP attachment prefetch — same daemon-executor / sub-budget pattern as primary) + regression tests
- [x] 01-13-PLAN.md — Gap closure: WR-01 (PPP end-of-run cleanup pass) + regression tests
- [x] 01-14-PLAN.md — Gap closure: IN-04 (workflow env-var pinning) + Living Ledger entry documenting 7 new rules + regression test

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

| Phase                                            | Plans Complete | Status                       | Completed |
|--------------------------------------------------|----------------|------------------------------|-----------|
| 1. Subcontractor Rate Logic Modification         | 14/14          | ✅ Complete — ready to ship  | -         |
| 2. Railway → Render Pre-Migration ADR (DEFERRED) | 0/TBD          | Deferred — out of v1.0 scope | -         |
