# Phase 12 — API Coverage Declaration

No external API integration: Phase 12 adds no new external API, SDK, or service surface —
`smartsheet-python-sdk`'s `Cells.get_cell_history` (plan 12-04) and the `supabase` Python
client's `.rpc()` / `.table()` calls (plans 12-01, 12-03) are already-integrated
capabilities used identically today by `pipeline/snapshot_drift.py:404-438` and
`billing_audit/writer.py` / `pipeline_memory/client.py`, against packages already pinned in
`requirements.txt` with no version change.

## Why the detector fired

The deterministic scan matched three prose phrases in the plan bodies — "Smartsheet SDK
internals", "Smartsheet API token", and "consumes the same `SMARTSHEET_API_TOKEN`" — all of
which appear in threat-model and isolation rationale that explains why the *existing*
Smartsheet integration's shared 300 req/min budget must not be spent by the new off-hours
job. They describe a constraint on an existing integration, not the adoption of a new one.

## Existing-integration inventory (for the record)

| Capability | Already integrated at | Used by Phase 12 |
|---|---|---|
| `smartsheet.Cells.get_cell_history(sheet_id, row_id, column_id, include_all=True)` | `pipeline/snapshot_drift.py:404-412` | plan 12-04 (`scripts/backfill_cell_history_attribution.py`), same call shape, same SDK 429 handling, new caps |
| `supabase` client `.schema(...).rpc(name, params).execute()` | `billing_audit/writer.py:520-600` (`freeze_row`), `pipeline_memory/schema.sql` `upsert_rows_bulk` callers | plans 12-01 / 12-03, new RPC name `backfill_attribution` on the existing client |
| `supabase` client `.table(...).select(...).in_(...)` | `pipeline_memory/reader.py` | plan 12-01 sources 1, 3 and 4 reads |
| `smartsheet.Attachments` list / delete / attach | `pipeline/cleanup.py`, `pipeline/upload.py` | unchanged; plan 12-02 fixes a predicate that gates the existing delete, adds no call |

New third-party dependencies: **none**. `requirements.txt` is not modified by any plan in
this phase (see `12-RESEARCH.md` § Package Legitimacy Audit — not applicable, zero new
dependencies).
