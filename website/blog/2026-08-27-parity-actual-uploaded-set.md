---
slug: parity-actual-uploaded-set
title: "Shadow parity now compares against the uploaded set; shadow read budget raised to 25 min"
authors: [runbook-bot]
tags: [github, project, python, tests, workflows]
date: 2026-08-27T21:00:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` →
`pipeline/orchestrate.py`, `pipeline/parity.py`) on the GitHub Actions
weekly workflow. **Change type:** shadow-comparator definition (evidence
only — nothing the run generates or uploads changes) plus one workflow
env line. **PR:** #358, after #356 (client-init fix) and #353 (the flip).

<!-- truncate -->

## What changed

1. **"Actual" is the uploaded set.** The shadow comparator that writes
   `parity_verdict` now compares the incremental candidate against the
   groups the full run generated **and had an upload task for**. Groups
   the full run generates but withholds from upload are dropped from both
   sides, and their count is persisted as
   `parity_details.actual_withheld_excluded`.
2. **`RUN_MEMORY_SHADOW_MAX_MINUTES: '25'`** on the `Generate reports`
   step (code default stays `10`).

## Why

Run #2801 — the first run with working run-memory — reported
`parity_verdict = fail` with `actual_count=158, candidate_count=43,
groups_compared=3`. The full run had uploaded only **4** files. The other
154 "actual" groups were the quarantined garbage-name files
(`_User__NO_MATCH`, `_User_Unknown_Foreman`) that the full path
regenerates on *every* run: their WR is on no target sheet, so their
upload is withheld, so they never gain an attachment, so the
"attachment missing → regenerate" rule fires again next run. A candidate
derived from changed rows can never contain them. Under the old
definition the group verdict was `fail` by construction, and the
five-run streak that authorises the incremental read could never start.

On the read side, the 10-minute probe budget covered 56 of 121 sheets
(~11 s/sheet including Smartsheet 5xx retries), which the comparator
correctly reports as `skipped` — and a `skipped` side blocks an overall
`pass`. Run #2801 took 53 of the 165-minute session budget, so 25
minutes fits with room to spare.

## What operators will see

- `parity_details.actual_withheld_excluded` around 150 on a normal run.
  That is expected, not a finding.
- The read side should now report `sheets_probed` ≈ the sheet count and
  a `pass`/`fail` instead of `changed_sheet_not_probed`.
- Runs are ~15 minutes longer while the shadow is on (still far inside
  the budget; the shadow block self-skips if the session budget is
  short).
- A remaining `fail` now points at a real divergence. One known source
  is a handful of groups whose content hash alternates between two
  values on consecutive runs with no data change (a sort-key tie in
  `calculate_data_hash` resolved by fetch order — e.g.
  `WR 91057431 / week 080226`, re-uploaded every run since 15:57Z on
  2026-08-27). That is tracked separately; do not flip the incremental
  flag while it persists.

## Rollback

Revert #358: the comparator returns to comparing against every generated
group and the budget to 10 minutes. Excel output, uploads and billing
are unaffected either way — the comparator only writes
`run_ledger.notes`.
