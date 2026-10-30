---
created: 2026-10-29T00:00:00-05:00
title: AUD-02 incremental runs never re-check open findings outside the re-fetched scope
area: pipeline_memory
severity: minor
blocks: claiming AUD-02's "affected groups + open findings" scope under RUN_MEMORY_INCREMENTAL_ENABLED
files:
  - pipeline/orchestrate.py:_run_audit_memory_phase
  - pipeline/orchestrate.py:_run_phase2_incremental
  - pipeline_memory/audit_findings.py:closing_row_indices
  - pipeline_memory/reader.py:map_affected_to_sheets
---

## Problem

AUD-02 says every audit run evaluates "affected groups + open findings". With
`AUDIT_MEMORY_ENABLED` and an incremental run (`RUN_MEMORY_INCREMENTAL_ENABLED`),
`audit_financial_data` only sees PHASE 2b's rows: the sheets that hold a row for a
candidate `(wr, week)` pair. A group with a stored `open`/`resurfaced` finding whose
rows sit only on unchanged sheets is not re-fetched, so it is never re-checked this
run and its `last_seen_run` is not bumped.

## Current safe behaviour (PR #435)

Such findings are left untouched and are never closed:

- Closing pairs come only from rows of the run's candidate pairs
  (`_run_audit_memory_phase(..., scope_pairs=...)`), and the WR-pooled
  `price_variance_anomaly` check closes nothing on a scoped run.
- The RPC's `fixed` branch is a JOIN against `p_reaudited_pairs`, so a group with
  no pair cannot be closed.
- A full run (every sheet re-fetched, `scope_pairs=None`) re-checks them, and full
  mode is still the production default.

Pinned by `tests/test_audit_memory_closure_safety.py::
test_open_finding_outside_changed_sheets_is_never_closed`.

They are re-checked on the next full run. Trigger 7 resolves every execution type
except `production_frequent` to full (the Monday `weekly_comprehensive` deep run,
weekend and manual runs), so each open finding is re-checked at least weekly. Pinned
by `tests/test_incremental_read.py::
test_every_non_frequent_execution_type_resolves_full`.

## Why it was not implemented in PR #435

Re-checking those groups means reading open-finding pairs from
`pipeline_memory.audit_finding` (no reader exists yet), mapping them to sheets
(`map_affected_to_sheets`) and adding those sheets to the PHASE 2b re-fetch. That
widens the production fetch path and `all_rows` (the grouping input), costs time
budget (`TIME_BUDGET_MINUTES`), and edits Phase 11 run-memory code
(`_run_phase2_incremental`) that another worker owns. A price-variance re-check also
needs every row of the WR (all weeks), which no per-pair re-fetch guarantees.

## Options for the follow-up

1. Fetch the open-finding groups' sheets in a separate read used only by the audit,
   never by grouping, bounded by a sheet cap and the time budget; or
2. Run a weekly full audit-memory pass (the deep run already reads every sheet) and
   document that incremental runs refresh only affected groups; or
3. Amend AUD-02's wording to "affected groups; open findings refresh on full runs".

Owner decision needed before `RUN_MEMORY_INCREMENTAL_ENABLED` and
`AUDIT_MEMORY_ENABLED` are both on in production.
