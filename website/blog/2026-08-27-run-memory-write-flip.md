---
slug: run-memory-write-flip
title: "Run-memory writes enabled in the weekly billing workflow (Phase 11 flip)"
authors: [runbook-bot]
tags: [github, project]
date: 2026-08-27T03:30:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` →
`pipeline/orchestrate.py`) on the GitHub Actions weekly workflow.
**Change type:** production flag flip (one workflow env line) plus the
controls it turns on. **PRs:** #353 (the flip), on top of #351 (Phase 11
plans 01–07, dormant) and #354 (review fixes).

<!-- truncate -->

## What changed

The `Generate reports` step of `weekly-excel-generation.yml` now sets
`RUN_MEMORY_WRITE_ENABLED: '1'`. That single line turns on three things
that shipped dormant in #351:

1. **Run memory.** Every scheduled run writes a Supabase `pipeline_memory`
   ledger — one `run_ledger` row per run, a per-sheet `sheet_registry`
   watermark, and the observed `row_state` / `group_state` for every
   accepted billing row and generated group.
2. **Shadow parity.** Each frequent run still does today's full read, and
   additionally computes what an *incremental* run would have regenerated
   from its own affected set, compares it with what the full run actually
   regenerated, and records `parity_verdict` (`pass` / `fail` / `skipped`)
   in `run_ledger.notes`. A `pass` requires real evidence — a comparison
   with nothing to compare reports `skipped`, never `pass`.
3. **Monday reconciliation.** The `weekly_comprehensive` run marks rows
   that disappeared from Smartsheet as `deleted_at` in `row_state` and
   refreshes each sheet's stored `column_mapping`. A sheet that did not read
   cleanly is left untouched rather than risk a false deletion.

The **incremental read itself stays OFF**: `RUN_MEMORY_INCREMENTAL_ENABLED`
is not set (code default `'0'`). Excel generation, attachment uploads and
cleanup are byte-for-byte the same as before this flip.

## Why

Phase 11's goal is for frequent runs to read only the rows that changed
and rebuild only the touched Work Request / week files. That is a
billing-visible behaviour change, so it is authorised by evidence, not by
review: five consecutive scheduled runs whose shadow comparison reports
`pass`. The evidence can only come from real scheduled runs writing real
memory — which is what this flip starts. The Phase 10 manual rollout
populated memory once, but a manual run is not a scheduled one.

## What operators will see

- New log lines: `🧭 Run-memory mode resolved: full`, `⚡ Run-memory row
  writes: … confirmed=True`, and a shadow-parity line per run.
- `run_ledger.notes` carries `parity_verdict`, `parity_details`,
  `mem_confirmed`, `mem_sheets_errored`.
- **Sentry:** a parity `fail` is sent at error level with counts, group
  keys and the run id. It is a blocking defect for the *rollout* and inert
  for the *run* — nothing was generated differently. Do not flip the
  incremental flag while any `fail` exists.
- **Failure modes are fail-open.** A Supabase outage or a partial write
  makes that run's memory incomplete (`mem_confirmed=false`, verdict
  `skipped`) and the run still completes normally. Each memory phase has
  its own sub-budget (`RUN_MEMORY_WRITE_MAX_MINUTES`,
  `RUN_MEMORY_SHADOW_MAX_MINUTES` plus generation headroom) so it can never
  threaten `TIME_BUDGET_MINUTES`.

## How to confirm

After the first scheduled `production_frequent` run:

```sql
select run_id, status, finished_at, sheets_changed, sheets_errored,
       notes->>'parity_verdict' as parity, notes->>'mem_confirmed' as confirmed
from pipeline_memory.run_ledger order by started_at desc limit 3;
```

Expect `status='success'`, `sheets_changed` populated, `sheets_errored=0`,
`confirmed=true`. The full owner checklist lives in
`docs/run-memory-write-flip-checklist.md`; the runbook's Operations page
has the symptom table.

## Rollback

Delete the `RUN_MEMORY_WRITE_ENABLED: '1'` line from the `Generate reports`
step (or set it to `'0'`). No code change is needed — every call site is
fail-open and self-gates on this flag plus `TEST_MODE`. Rows already
written to `pipeline_memory` stay and are harmless; nothing in production
reads them until the incremental flag flips.
