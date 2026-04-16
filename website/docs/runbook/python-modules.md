---
id: python-modules
title: Python modules
sidebar_position: 2
---

# Python modules

Every top-level Python file in the repo and what it owns.

## Production entry points

### `generate_weekly_pdfs.py`
The primary script. Responsibilities:

- Loads config via `python-dotenv`.
- Calls Smartsheet via `smartsheet-python-sdk`, using `ThreadPoolExecutor`
  for parallel sheet discovery and attachment pre-fetch.
- Groups rows by `(work_request, week_ending)` and computes a content hash
  per group. Groups whose hash matches `generated_docs/hash_history.json`
  are skipped (the `HISTORY_SKIP_ENABLED` gate).
- Writes each group to `generated_docs/WR_{wr}_WeekEnding_{date}_*.xlsx`
  via `openpyxl`, styling headers, totals, and embedding the
  `LinetecServices_Logo.png`.
- Re-uploads the resulting files as Smartsheet attachments, unless
  `SKIP_UPLOAD=true`.
- Emits `generated_docs/run_summary.json` (consumed downstream by Notion).
- Wires Sentry for exception, threading, and logging integrations, and
  emits cron check-ins so missed runs page.

### `audit_billing_changes.py`
The `BillingAudit` class. When the generator runs, it imports this module
and checks for unauthorized edits (cell history diff) against
`generated_docs/audit_state.json`. Also runnable standalone for a
one-shot audit sweep.

### `run_info.py`
Convenience CLI that prints the available scripts and their flags — what
the Replit "Run" button invokes.

## Diagnostics

| File | Purpose |
| --- | --- |
| `analyze_excel_totals.py` | Reconciles totals across generated Excel files; useful when a week's numbers look wrong. |
| `analyze_specific_excel.py` | Inspects one Excel file in detail (cell dump + formula trace). |
| `diagnose_pricing_issues.py` | Surfaces work items excluded due to missing/invalid pricing. |
| `cleanup_excels.py` | Deletes stale Excel output. Used by CI cleanup steps. |
| `test_production_reload.py` | Reproduces the production reload path locally; smoke test. |

## Scheduled scripts

| File | Purpose |
| --- | --- |
| `scripts/notion_sync.py` | Called at the end of a workflow run with `--mode run`; upserts metrics rows. |
| `scripts/notion_setup.py` | Bootstraps Notion databases the first time. |
| `scripts/notion_dashboard.py` | Builds/refreshes dashboard pages. |
| `scripts/generate_artifact_manifest.py` | Produces `artifact_manifest.json` (SHA256 + summary) after each run for the workflow's upload step. |

## Dependencies

See `requirements.txt`. Core: `smartsheet-python-sdk`, `openpyxl`, `pandas`,
`sentry-sdk`, `pandera`, `psutil`, `notion-client`. Python `3.11`+ (the
weekly workflow uses `3.12`).
