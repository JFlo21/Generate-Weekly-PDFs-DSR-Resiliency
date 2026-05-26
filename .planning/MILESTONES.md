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
  *(Closed 2026-05-26 during the v1.0.1 close: Phase 01 VALIDATION.md
  reconstructed (State B) and Phase 01.1 promoted to nyquist-compliant.)*

---

## v1.0.1 Attribution Bulk-Prefetch + Historical Claimer Remediation (Shipped: 2026-05-26)

**Hotfix line on top of v1.0** (post-`v1.0`-tag work on master). This Phase 02
is NOT the originally-planned MIG-01 ADR (that remains deferred to v1.1) — it is
a blocking production fix for the claim-attribution week-scope × Sub-project E
interaction.

**Phases completed:** 1 (Phase 02), 6 plans (4 executed + 2 gap-closure).

**Delivered:** A read-side fix making every generated Excel file
partitioned/named by the real frozen claimer from
`billing_audit.attribution_snapshot` — no `_NO_MATCH` / `_Unknown_Foreman` for
rows that have a frozen claimer — with no time-budget regression, so
Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`, clean filenames) can be
safely re-activated behind a human gate.

**Root cause:** the v1.0 `ATTRIBUTION_RESOLUTION_WEEKS=8` scope hotfix gated
group-KEY / filename formation (not just skip optimization); when Sub-project E
was flipped authoritative (`67539ec`), its `no_row → regenerate` wave resolved
claimers from the empty out-of-scope pre-pass → garbage names on 372 of 1,116
files. Mitigated by reverting E to dormant (`46cd05d`); fixed read-side here.

**Key accomplishments:**

- **Bulk attribution prefetch.** A single `lookup_attribution_bulk` RPC +
  fail-safe `prefetch_attribution` reader (chunked 500/call, distinct
  `with_retry` op id) replaces the four per-row pre-passes; consumers read O(1)
  from a shared `_attr_map`. Attribution HTTP drops from ~137k to O(chunks).
- **Footgun removed.** `ATTRIBUTION_RESOLUTION_WEEKS` and its scope gates fully
  excised (the gate-on-key-formation that caused the incident).
- **Graceful degradation.** `ATTRIBUTION_BULK_PREFETCH_FALLBACK` (default-ON)
  degrades a missing RPC (`rpc_missing` → per-row fallback) while a genuine
  outage (`fetch_failure`) still HOLDs B/C billing files (D-04 preserved).
- **Historical remediation.** Default-OFF, dry-run-first, isolated
  `run_claimer_remediation` garbage-attachment sweep (TARGET + PPP,
  live-identity exempt), operator-reachable via `advanced_options`.
- **Safe E re-activation.** Documented D-09/D-10/D-11 runbook;
  `SUPABASE_HASH_STORE_AUTHORITATIVE` stays dormant `'0'` — the flip is a
  separate, deliberately human-gated operator action.

**Stats:**

- Phases: 1 (Phase 02: 6 plans — 02-01..04 executed + 02-05/06 gap-closure)
- Requirements: 6/6 SPEC-1..6 satisfied code-side (02-SPEC.md)
- Tests: 986 passed / 29 skipped / 69 subtests (from 682 at v1.0 close)
- Audit: `tech_debt` (see `.planning/v1.0-MILESTONE-AUDIT.md`) — 18/18
  requirements satisfied code-side (SUB-01..12 + SPEC-1..6), 5/5 cross-phase
  integration seams wired, all 3 phases Nyquist-compliant.

**Known deferred items at close (operator-action production gates, not code defects):**

- Deploy `billing_audit.lookup_attribution_bulk` RPC to live Supabase +
  `NOTIFY pgrst, 'reload schema'`.
- Zero-garbage production run validation (O(chunks) attribution HTTP; no
  `_NO_MATCH` / `_Unknown_Foreman` for frozen-claimer rows).
- Remediation dry-run via `advanced_options`, then execute.
- **Human-gated D-11 flip** of `SUPABASE_HASH_STORE_AUTHORITATIVE=1` (currently
  dormant) after the above validate.
- Carried-forward v1.0 operator gates (live cron observation, Supabase
  `schema.sql` apply, data-team `lookup_attribution` RPC, Step B price-write).

---
