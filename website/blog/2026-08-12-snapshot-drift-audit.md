---
slug: snapshot-drift-audit
title: "feat: snapshot-date drift audit detects automation re-stamps (report-only)"
authors: [runbook-bot]
tags: [project, python, tests, workflows]
date: 2026-08-12T22:00:00+00:00
---

**Component:** Python billing pipeline (`pipeline/snapshot_drift.py`, seam in
`pipeline/orchestrate.py`, shadow log in `billing_audit/`) — runs inside every
scheduled `generate_weekly_pdfs.py` billing run.

<!-- truncate -->

## What changed

The pipeline gains a **snapshot-date drift audit**. Each run, every row's
current `Snapshot Date`-derived billing week is compared against a Supabase
provenance baseline (`snapshot_provenance`) recording the week each row was
first billed under. A row whose week *moved* is a drift candidate; candidates
are classified by reading the Smartsheet **cell history** of `Snapshot Date`
and `Units Completed?`:

- A `Snapshot Date` write by the automation identity
  (`automation@smartsheet.com`) with **no** `Units Completed?` change within
  the correlation window (default 15 minutes — the automation batches its
  stamps, so legitimate writes can land several minutes after the checkbox) is
  an **`automation_self_fire`** — the defect signature.
- Anything else classifies as **`manual`** (never held) or
  **`unclassified`** (never held) — every error path degrades away from
  holding.

Detection is **report-only by default**. A separate, default-OFF gate
(`SNAPSHOT_DRIFT_HOLD_ENABLED`) can additionally *hold* automation self-fires
at their previously-billed week (rewriting both `Snapshot Date` and
`Weekly Reference Logged Date` in memory only — the source sheet is never
written). Drift events are shadow-logged to Supabase (`snapshot_drift`) and
raise the audit `risk_level`; a Sentry warning fires whenever a hold applies.

## Why it changed

The per-sheet "record Snapshot Date" Smartsheet automation uses trigger "when
rows are changed" with condition "Units Completed? is checked" — conditions
filter rows, not fields, so ANY edit to a completed row (even a same-value
re-save) re-stamps `Snapshot Date` to today. Proven 2026-08-12 on WR 16881353
/ Point 27: a Quantity re-save at 18:11:24Z drew an automation re-stamp at
18:11:48Z (and a `Weekly Reference Logged Date` rewrite to the wrong Sunday)
while `Units Completed?` had been unchanged for six days. Every re-stamp moves
a unit into the current billing week — files regenerate, billing weeks shift,
audit deltas appear. The Smartsheet-side fix (field-scoped trigger + write-once
condition) is applied per sheet in the UI; this audit is the pipeline-side
detector that catches any sheet where the broken automation still lives.

## What operators need to know

- **Kill switches:** `SNAPSHOT_DRIFT_AUDIT_ENABLED=false` disables detection
  entirely (restores pre-change behavior). `SNAPSHOT_DRIFT_HOLD_ENABLED`
  (default `false`) gates holding; leave OFF until burn-in completes.
- **Tuning env vars:** `SNAPSHOT_DRIFT_MAX_ROWS` (default 40 cell-history
  classifications per run, week-movers only), `SNAPSHOT_DRIFT_PACE_SEC`
  (default 2.0s between history calls), `SNAPSHOT_DRIFT_MAX_MINUTES` (default
  5, phase sub-budget under `TIME_BUDGET_MINUTES`),
  `SNAPSHOT_DRIFT_AUTOMATION_EMAIL` (default `automation@smartsheet.com`),
  `SNAPSHOT_DRIFT_UNITS_WINDOW_MINUTES` (default 15 — widen if legitimate
  batched stamps ever classify as self-fires).
- **Manual rollout step (required once):** apply the two appended DDL blocks
  in `billing_audit/schema.sql` (`snapshot_provenance`, `snapshot_drift`) to
  Supabase and confirm the `billing_audit` schema stays PostgREST-exposed.
  Until applied, the feature safely no-ops (fetches degrade, nothing is
  logged, nothing is held).
- **Fail-open guarantee:** Supabase outages, classification errors, malformed
  history, and budget exhaustion all degrade to today's behavior — rows bill
  exactly as they do now. A hold can only apply to a row positively classified
  as an automation self-fire with a known prior week.
- **Owner:** Python billing pipeline. Stacked on the rate-sanity audit change
  (#329); the Supabase tables live in the same `billing_audit` schema as the
  billing audit shadow log.
