# Milestones

## v1.0 Subcontractor Rate Logic (Shipped: 2026-05-20)

**Phases completed:** 2 gating phases (Phase 01 + inserted Phase 01.1),
19 plans. Phase 02 (pre-migration ADR / MIG-01) deferred to v1.1.

**Delivered:** An additive Subcontractor Rate Logic Modification to the
production `generate_weekly_pdfs.py` billing pipeline — two new
subcontractor-scoped Excel variants with full shadow-foreman/helper
support and per-row claim-history attribution — with zero impact to the
existing primary, helper, VAC-crew, or ORIG-folder outputs.

**Key accomplishments:**

- **Two new subcontractor Excel variants.** `_AEPBillable` (3%-increase
  AEP contract rates, gated by `Snapshot Date >= 2026-04-12`) and
  `_ReducedSub` (13%-reduced rates), priced from the new
  `data/subcontractor_rates.csv` (3,691 priced CUs, fingerprinted),
  scoped strictly to `SUBCONTRACTOR_FOLDER_IDS`-discovered sheets.
- **Dual-target attachment routing.** `_ReducedSub` lands on both
  `TARGET_SHEET_ID` and the new `SUBCONTRACTOR_PPP_SHEET_ID`, with an
  independent `target_map` collision quarantine, a daemon-executor PPP
  attachment prefetch (sub-budgeted), and a symmetric end-of-run PPP
  cleanup pass.
- **Shadow-foreman/helper variants made production-functional.**
  `_AEPBillable_Helper_<name>` / `_ReducedSub_Helper_<name>` with
  three-site attachment-identity consistency (CR-01), unblocked by the
  Phase 01.1 pre-acceptance price rescue (Bug A) so blank-priced helper
  rows survive the row-acceptance gate.
- **Variant partitioning + off-contract cleanup.** Subcontractor
  non-helper rows emit ONLY variant keys (Bug B1 — eliminates the
  duplicate-no-suffix Excel), and a per-sheet PPP cleanup whitelist
  (`{'reduced_sub','reduced_sub_helper'}`, Bug B2) unconditionally prunes
  off-contract attachments.
- **Per-row claim-history attribution (Bug C).** Helper files contain
  only each foreman's pre-shift-change line items via the
  `lookup_attribution` reader against `billing_audit.attribution_snapshot`,
  with a fail-safe fall-back to the current helper; `pipeline_run.variant`
  schema column added (SUB-07).
- **Quality bar held.** `pytest tests/` → **682 passed / 26 skipped /
  58 subtests** (from 537 pre-milestone). Cross-phase integration
  verified (all 12 SUB-IDs wired); byte-identical primary/helper/
  VAC-crew/ORIG-folder outputs preserved; entire feature behind
  default-ON kill switches with workflow-pinned env vars. ~30+ post-merge
  review findings closed across two gap-closure rounds.

**Stats:**

- Phases: 2 gating (Phase 01: 14 plans; Phase 01.1: 5 plans) + Phase 02 deferred
- Requirements: 12/12 v1 requirements mapped (SUB-01..07 → Phase 1;
  SUB-08..12 → Phase 1.1); MIG-01 descoped to v1.1
- Tests: 682 passed / 26 skipped / 58 subtests
- Execution window: 2026-05-14 → 2026-05-20
- Audit: `tech_debt` (see archived `milestones/v1.0-MILESTONE-AUDIT.md`)

**Known deferred items at close: 6** (acknowledged — see STATE.md
"Deferred Items"). The v1 requirements shipped **code-complete and
integration-verified**, with production-observable acceptance criteria
deferred to the next scheduled GitHub Actions cron run:

- 4 HUMAN-UAT items (live-cron observable: shadow-variant emission;
  Bug C frozen-helper after a mid-week swap; PPP off-contract cleanup;
  hash-prune fires-once-idempotent) + 2 phase VERIFICATION `human_needed`.
- Operator actions before flipping attribution on in prod: apply
  `billing_audit/schema.sql`; data team deploys the `lookup_attribution`
  RPC; Step B real-data SKIP_UPLOAD price-write spot-check.
- Open debug session `sub-helper-shadow-missing` (root_cause_found, fix
  shipped) and open thread `p01-hotfix-followups` (post-cron
  byte-divergence watch-list).
- Nyquist VALIDATION docs incomplete (Phase 01 missing; Phase 01.1 draft)
  — 682 passing tests provide de-facto coverage.

---
