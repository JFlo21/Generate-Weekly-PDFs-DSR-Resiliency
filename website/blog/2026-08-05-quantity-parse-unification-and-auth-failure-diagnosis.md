---
slug: quantity-parse-unification-and-auth-failure-diagnosis
title: "fix: decorated quantities now price correctly; all-sheets 403 runs diagnose themselves (#297)"
authors: [runbook-bot]
tags: [docs, project, workflows]
date: 2026-08-05T21:30:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` / `pipeline/`) — the
GitHub Actions cron engine that turns Smartsheet field data into weekly Excel reports.

<!-- truncate -->

## What changed

Three production fixes ship together in PR [#297](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/297):

1. **Decorated quantities now price correctly on subcontractor variants.** A
   Smartsheet `Quantity` cell containing unit decoration (for example `2 EA`
   instead of `2`) previously priced at the raw Smartsheet `Units Total Price`
   — often a single-unit price — while the workbook still displayed the
   quantity as `2`. The pricing parser now strips non-numeric characters
   exactly like the display parser does, so the row prices as rate × quantity.
   When pricing still has to fall back to the Smartsheet price (zero rate or
   zero quantity), the run log now carries a `⚠️ Subcontractor price
   fall-through` WARNING naming the CU, variant, rate, and raw quantity value.
2. **An all-sheets authorization failure names itself.** When every source
   sheet returns HTTP 401/403 and zero rows come back, the run now fails with
   `Smartsheet authorization failure: all N source sheets returned 401/403`
   instead of the generic `No valid data rows found`. A partial authorization
   failure logs a `🔐` ERROR with the affected sheet count.
3. **Early failures report cleanly.** A failure before the group-processing
   phase (such as the authorization failure above) previously crashed the
   error handler itself with `UnboundLocalError: _groups_errored`, hiding the
   real cause from both the log and Sentry. Session counters are now
   initialized before any work starts, so the true error always surfaces.

## Why it changed

On 2026-08-05 a production run failed with every one of its 113 source sheets
returning 403 (revoked/expired `SMARTSHEET_API_TOKEN` or removed sheet
sharing). The generic error plus the handler crash made the root cause
invisible without reading 113 per-sheet log lines. Separately, a billing
report for CU `BKT-IP8-F` showed quantity 2 priced as 1 unit — traced to the
pricing parser rejecting a decorated quantity value that the display parser
accepted.

## What operators need to know

- **If a run fails with `Smartsheet authorization failure`:** rotate the
  `SMARTSHEET_API_TOKEN` secret (GitHub → repository settings → Actions
  secrets) or restore sheet sharing for the token's account, then re-run the
  workflow. No code change is needed; the pipeline recovers on the next run.
- **If you see `⚠️ Subcontractor price fall-through` warnings:** the named
  row kept its Smartsheet price. Check the row's `Quantity` cell — a zero or
  truly non-numeric value is the usual cause. Decorated values like `2 EA` no
  longer trigger this.
- **After correcting quantity data for a past week**, force regeneration the
  usual way (`REGEN_WEEKS` / `RESET_HASH_HISTORY` via the workflow's
  `advanced_options`) so the corrected rate × quantity price reaches the
  attached workbook.
