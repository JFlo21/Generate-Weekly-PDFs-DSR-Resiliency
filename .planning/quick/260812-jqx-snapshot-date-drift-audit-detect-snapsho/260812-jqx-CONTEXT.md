# Quick Task 260812-jqx: Snapshot-date drift audit - Context

**Gathered:** 2026-08-12
**Status:** Ready for planning

<domain>
## Task Boundary

Snapshot-date drift audit: detect Snapshot Date changes on rows whose
week was already billed, classify automation self-fire vs legitimate
manual edit via targeted cell-history lookups, flag all drift on the
billing audit sheet plus a Supabase shadow layer, and gate
regeneration only for automation self-fires (never block manual
edits).

Background (proven 2026-08-12, living-ledger `[2026-08-12 13:40]`):
the per-sheet "record Snapshot Date" Smartsheet automation uses a
row-change trigger with "Units Completed? is checked" as a condition,
so ANY edit to a completed row (same-value saves, bulk API/DataTable
touches) re-stamps Snapshot Date to today. Because Weekly Reference
Logged Date = Snapshot Date snapped to Sunday, each re-stamp moves
the unit into the current billing week -> already-billed units drift
weeks -> audit chaos. The UI-side automation fix is being applied by
Juan, but the pipeline needs defense-in-depth.

</domain>

<decisions>
## Implementation Decisions

### Gate action (automation self-fire on an already-billed row)
- **Hold prior week + flag HIGH.** The pipeline keeps billing the
  row under its previously-billed week (ignores the drifted date for
  grouping), flags HIGH on the billing audit sheet + Supabase, and
  reports which row to repair upstream. Files stay correct; nothing
  silently moves weeks.
- Manual edits are NEVER blocked or held — they flow through
  normally and are shadow-logged.
- Unclassifiable drift (history unavailable, cap exhausted, API
  error) must NOT hold the row — flag it as `unclassified` and let
  it flow (fail-open on gating, fail-closed on logging).

### Cell-history budget (30 req/min hard limit)
- **Only week-movers, capped.** Spend history lookups ONLY on rows
  whose computed billing week differs from the previously-billed
  week for that row, with a per-run cap (~40 rows) and pacing
  (~2s between calls; ~2 calls per row: Snapshot Date +
  Units Completed?). Everything else costs zero extra API calls.
- Classifier signature: a Snapshot Date write by
  automation@smartsheet.com with NO Units Completed? change within
  +/-2 minutes = automation self-fire. Otherwise manual/legitimate.

### Provenance / Supabase shadow layer
- **New additive Supabase table** (e.g. `snapshot_drift` /
  provenance: sheet_id, row_id, WR, CU, prior snapshot date, new
  snapshot date, prior billed week, new week, changed_by,
  classification, run_id, detected_at). Written additively by the
  pipeline; the existing `billing_audit` tables stay untouched.
- Approved as a Supabase schema ADDITION only — no RLS/policy/
  schema changes to existing tables. Migration must be reviewed by
  Juan before apply (protected area).

### Claude's Discretion
- Exact table/column naming and index choices.
- Flag format on the billing audit sheet (reuse the existing
  `_log_to_audit_sheet` shape from audit_billing_changes.py).
- Env-var kill-switches and defaults (mirror RATE_SANITY pattern:
  default enabled for detection/logging; the HOLD gate gets its OWN
  kill-switch so gating can be disabled independently of detection).
- Whether v1 per-row provenance is seeded from the first run that
  sees a row (no history backfill required).

</decisions>

<specifics>
## Specific Ideas

- Reuse the 260812-isx patterns: function-local lazy imports,
  report-only hard rules, RED-first tests, shortest-prefix work-type
  tokens, `_parse_quantity`/`parse_price` helpers.
- Time-budget awareness: drift classification must respect
  TIME_BUDGET_MINUTES and degrade to `unclassified` (flag, no hold)
  when the budget is tight — never stall the session.
- The hold decision must be deterministic and visible: every held
  row logs WR / row id / prior week / drifted week / evidence
  timestamps to the run log, audit sheet, and Supabase.

</specifics>

<canonical_refs>
## Canonical References

- `memory-bank/living-ledger.md` `[2026-08-12 13:40]` — incident
  root causes + drift signature (automation@smartsheet.com write
  with no Units Completed? change within +/-2 min).
- `memory-bank/living-ledger.md` — `billing_audit` Supabase
  integration + Supabase hash-store migration entries (research
  phase must read these before proposing the new table).
- `.github/prompts/data-processing-business-logic.md` — domain
  rules (snapshot date vs weekly reference log date is a protected
  concept).

</canonical_refs>
