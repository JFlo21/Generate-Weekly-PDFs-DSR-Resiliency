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

This inventory is deliberately NOT a coverage matrix (no `capability | decision | reason`
rows): the seal-time gate treats any such table alongside the declaration above as
contradictory, and these are existing integrations, not new capability decisions.

- `smartsheet.Cells.get_cell_history(sheet_id, row_id, column_id, include_all=True)` —
  already integrated at `pipeline/snapshot_drift.py:404-412`; used by plan 12-04
  (`scripts/backfill_cell_history_attribution.py`), same call shape, same SDK 429 handling,
  new caps.
- `supabase` client `.schema(...).rpc(name, params).execute()` — already integrated at
  `billing_audit/writer.py:520-600` (`freeze_row`) and the `pipeline_memory/schema.sql`
  `upsert_rows_bulk` callers; used by plans 12-01 / 12-03 with the new RPC name
  `backfill_attribution` on the existing client.
- `supabase` client `.table(...).select(...).in_(...)` — already integrated at
  `pipeline_memory/reader.py`; used by plan 12-01 sources 1, 3 and 4 reads.
- `smartsheet.Attachments` list / delete / attach — already integrated at
  `pipeline/cleanup.py` and `pipeline/upload.py`; unchanged, plan 12-02 fixes a predicate
  that gates the existing delete and adds no call.

New third-party dependencies: **none**. `requirements.txt` is not modified by any plan in
this phase (see `12-RESEARCH.md` § Package Legitimacy Audit — not applicable, zero new
dependencies).
