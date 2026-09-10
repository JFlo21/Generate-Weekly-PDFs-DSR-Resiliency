---
slug: pr402-phase-14-review-fixes
title: "Helper #2 pricing, WR holds, cleanup scope and audit fallback fixes (PR #402)"
authors: [operators]
tags: [python, project]
date: 2026-09-10T18:30:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` → `pipeline/`, `billing_audit/`), GitHub Actions cron. **PR:** [#402](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/402) on `fix/phase-14-cr01-cr02-wr03`. This entry is the synthesized changelog for that PR; the auto-generated stub that `docs-changelog.yml` posts on merge is superseded by it.

<!-- truncate -->

## What changed

Phase 14 shipped Foreman Helper #2 (`HELPER2_ENABLED=1`, permanent). The Phase 14 code review found that four places still treated only the Helper #1 family as "the helper family". PR #402 closes them:

- **Subcontractor pricing (CR-01).** `_Helper2_` shadow workbooks for AEP Billable and ReducedSub rows now price from the subcontractor rate matrix (`rate × qty`, work-type column) exactly like their Helper #1 twins. Before, both Helper #2 shadow variants fell through the early gate in `pipeline/pricing.py` and carried the raw Smartsheet `Units Total Price` instead.
- **Work-request holds and filters (CR-02).** `EXCLUDE_WRS` now holds back Helper #2 group files, and `WR_FILTER` now selects them in a scoped run. Both matchers in `pipeline/grouping.py` recognise the three `_HELPER2_` key shapes; before, a held WR could still upload its Helper #2 file.
- **Legacy cleanup scope (WR-01).** A WR whose only completed subcontractor rows this run were Helper #2 claims is now classified subcontractor-active, so the SUB-09 legacy off-contract / legacy-primary cleanup on `TARGET_SHEET_ID` applies to it the same way it already did for Helper #1-only WRs.
- **Billing-audit fallback (WR-03).** The `freeze_attribution` capability probe (used when the deployed Supabase RPC does not yet accept the Helper #2 parameters) is now coordinated across the parallel workers: one probe at a time, `inconclusive` outcomes re-probe up to five times, and rows that already know the RPC is un-migrated send their degraded request under the `freeze_attribution_degraded` circuit-breaker label instead of the primary one, so a tripped primary breaker no longer fast-fails them.

Guard rails that grew with it: the Helper #1 / Helper #2 literal parity test now covers `pipeline/pricing.py` and `pipeline/attribution.py` and checks parity per owning function or block rather than per file.

## Why

CR-01 and CR-02 were the two Critical findings of `14-REVIEW.md`: under-priced Helper #2 subcontractor workbooks and a WR hold that silently leaked Helper #2 files. WR-01 and WR-03 were the matching Warning findings in cleanup scope and the audit fallback. The owner decision on 2026-09-10 was `--fix`, validated against Helper #1 parity as the known-good sample.

## How it affects you

- **No new commands, env vars or schedule changes.** `EXCLUDE_WRS` and `WR_FILTER` now recognise the Helper #2 group-key shapes (`_HELPER2_`, `_REDUCEDSUB_HELPER2_`, `_AEPBILLABLE_HELPER2_`), so a WR hold also holds the Helper #2 files and a WR filter no longer drops them. `HELPER2_ENABLED`, `REGEN_WEEKS` and `RESET_WR_LIST` are unchanged; they were already variant-independent.
- **Expect one regeneration wave** of `_AEPBillable_Helper2_*` / `_ReducedSub_Helper2_*` workbooks on the first scheduled run after merge. The change-detection hash covers the raw Smartsheet `Units Total Price`, not the priced total, so the corrected prices alone would not have moved it; the wave comes from the subcontractor rates fingerprint (`SUB_RATES_FP`) now being mixed into these two variants' hashes, as it already is for the Helper #1 subcontractor files. The same mix-in means a future edit to `data/subcontractor_rates.csv` regenerates the Helper #2 shadow files too. Helper #1, primary and VAC-crew hashes are byte-identical to before. Today no live `_Helper2_` file exists, so the wave is empty until the first Helper #2 claim.
- **If a Helper #2 subcontractor total looks different from last week**, that is the rate-matrix price replacing the raw Smartsheet value; compare it to the Helper #1 file for the same WR and week before treating it as an anomaly (`investigate-price-anomaly` skill).
- **New warning to recognise:** `billing_audit.freeze_row: deployed freeze_attribution RPC does not yet accept the Helper #2 parameters` fires once per run when the Supabase migration from plan 14-09 is not applied; the run then persists attribution without Helper #2 for the rest of that run (counter `helper2_attribution_degraded`). It is not a failure of the workbook upload.
- **Open owner follow-ups** (not in this PR): a half-open policy for the billing-audit circuit breaker after a successful probe, and honouring `keep_historical` inside the SUB-09 off-contract cleanup gate before incremental read mode (`RUN_MEMORY_INCREMENTAL_ENABLED`) is ever switched on. Both are tracked in `.planning/todos/pending/2026-09-10-pr402-review-followups.md`.
