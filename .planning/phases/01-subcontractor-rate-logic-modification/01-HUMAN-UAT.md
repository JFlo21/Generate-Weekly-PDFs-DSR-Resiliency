---
status: partial
phase: 01-subcontractor-rate-logic-modification
source: [01-VERIFICATION.md]
started: 2026-05-14T22:30:00Z
updated: 2026-05-14T22:30:00Z
---

## Current Test

[awaiting operator verification — none active]

## Tests

### 1. First scheduled GitHub Actions weekly production run after merge
expected: Run completes inside `timeout-minutes: 110` (with `TIME_BUDGET_MINUTES: 95`); produces `_AEPBillable` and `_ReducedSub` Excel files (and helper-shadow files where helper-foreman events fire) in `generated_docs/<week>/`; `_AEPBillable` + `_ReducedSub` attached to `TARGET_SHEET_ID=5723337641643908`; `_ReducedSub` additionally attached to `SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908`; zero Sentry events tagged with new variant scope; existing primary/helper/vac_crew outputs byte-identical to the prior run (hash-history diff verification).
result: [pending — fires on next scheduled GHA run after merge to master with the kill switch `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=1`]

### 2. Step B real-data price-write end-to-end (SKIP_UPLOAD)
expected: Running `SKIP_UPLOAD=true python generate_weekly_pdfs.py` against real subcontractor sheets (with `SMARTSHEET_API_TOKEN` set) produces `_AEPBillable` and `_ReducedSub` workbook cells where `Pricing` column H equals `rate × qty` from `data/subcontractor_rates.csv` for known CUs, falls through to SmartSheet `Units Total Price` for missing CUs, and emits exactly one WARNING per affected sheet containing the marker "Subcontractor rates CSV missing".
result: [pending — operator action; previously deferred during Plan 01-06 Task 3 because local env lacked `SMARTSHEET_API_TOKEN`. Now rotated. Can be completed locally before merge or deferred to first scheduled production run.]

### 3. Apply `billing_audit/schema.sql` to Supabase (one-time operator setup)
expected: Open Supabase Dashboard → SQL Editor → paste `billing_audit/schema.sql` contents → Run. The `ADD COLUMN IF NOT EXISTS variant TEXT` clause is idempotent. After apply, `billing_audit.pipeline_run.variant` column exists and accepts the 7 valid variant strings (or NULL for legacy rows).
result: [pending — operator must execute before the first production run after merge, otherwise `emit_run_fingerprint`'s upsert will fail at the variant column write.]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
