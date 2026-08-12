---
slug: rate-sanity-audit-check
title: "feat: report-only rate-sanity audit flags stale-formula overbills (#329)"
authors: [runbook-bot]
tags: [project, python, tests, workflows]
date: 2026-08-12T15:30:00+00:00
---

**Component:** Python billing pipeline (`audit_billing_changes.py`) — the audit
system that runs alongside `generate_weekly_pdfs.py` on every scheduled billing run.

<!-- truncate -->

## What changed

The billing audit gains a new **report-only rate-sanity check**. On every audit
pass, each row's Smartsheet `Units Total Price` is compared against an expected
price computed as `New Rates rate × Quantity` (rates come from
`data/subcontractor_rates.csv`, keyed by CU + Work Type — the same table the
pricing engine already loads). A row is flagged when the two diverge by more
than the larger of a flat $0.02 rounding allowance or 0.5% of the expected
price.

This check is diagnostic only: it never mutates row price, quantity, grouping,
filenames, hashes, or upload behavior. It only adds entries to the audit
summary and, when applicable, raises the audit's `risk_level`.

The same PR also fixes an inconsistency in how the audit counts issues:
`total_issues` is computed in three separate places (the persisted local
history in `generated_docs/risk_trend.json`, the audit-sheet payload, and the
run-over-run trend delta), and only one of the three originally included the
new rate-sanity mismatch count. A mismatch-only run — no price anomalies, no
unauthorized changes, no data-consistency issues — could raise `risk_level`
correctly while still recording `total_issues: 0` in history and a zero trend
delta. All three aggregates now use the same definition.

## Why it changed

On 2026-08-12, WR 91916464 / Point 27 (CU `SAA-DE-20`) billed 3 EA at $341.04
($113.68/EA) instead of the correct 3 × $56.84 = $170.52. Root cause: the
source Smartsheet row's `Quantity` was corrected 6 → 3 by the foreman, but the
sheet's `Install Quantity` formula cell never recalculated and stayed at 6, so
the stale `56.84 × 6 = 341.04` flowed straight into `Units Total Price`. The
Python pricing engine was behaving correctly per contract — the primary/`_User_`
variant is a deliberate pass-through of Smartsheet's `Units Total Price` — so
there was no rate table for that path to compare against, and the stale
upstream cell was invisible to the pipeline. The only reason the overbill
surfaced at all was a foreman email. This audit check closes that detection
gap without touching the pricing path itself.

## What operators need to know

- **A rate-sanity mismatch shows up as a normal audit finding.** It raises
  `total_issues` (now consistently, across history/trend/audit-sheet) and can
  push `risk_level` from LOW to MEDIUM or HIGH, the same way a price anomaly or
  data-integrity issue does today.
- **When a mismatch is flagged**, compare the row's Smartsheet `Quantity`
  against its `Install/Removal/Transfer Quantity` formula cell on the source
  sheet. A mismatch between the two is the signature of this defect class —
  fix it by re-saving the row upstream (forces the formula to recalculate),
  never in the Python pricing path.
- **Emergency disable, no deploy needed:** set the environment variable
  `RATE_SANITY_AUDIT_ENABLED=false` to turn the check off. This restores the
  pre-change audit summary shape exactly (empty `rate_sanity_mismatches`,
  `total_rate_sanity_mismatches` 0) if the check ever produces noisy or
  incorrect findings in production.
- **Owner:** Python billing pipeline (`audit_billing_changes.py`). This check
  does not touch Supabase, `portal/`, or `portal-v2/`.
