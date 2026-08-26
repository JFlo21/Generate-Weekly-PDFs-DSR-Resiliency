# API Coverage — Phase 11 (Supabase PostgREST `pipeline_memory` + Smartsheet SDK 4.3.0)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Produced at plan time per the API Coverage Decision Checkpoint
> (`api-coverage.cjs` over the eight PLAN.md bodies returned `detected: true`).

Two external surfaces are in scope this phase. Both start from the same full-coverage
baseline as Phase 10 did — Phase 10's opt-outs are **re-decided here**, not carried over
silently, which is why several of them flip to INTEGRATE.

1. **Supabase PostgREST** against `pipeline_memory` in project `poeyztlmsawfoqlanucc`.
   Phase 10 was write-only; Phase 11 opens the read surface (INC-01, INC-02, INC-04).
2. **Smartsheet API via `smartsheet-python-sdk==4.3.0`** — the production read path gains
   `ifVersionAfter` / `rowsModifiedSince` (INC-01). No version bump.

---

## Surface 1 — Supabase PostgREST (`pipeline_memory`)

| capability | decision | reason |
|---|---|---|
| `rpc:upsert_rows_bulk` (bulk upsert, server hash diff, affected-set UNION) | INTEGRATE | D-04 promotes the returned affected set from observability to the regeneration scope selector |
| `table:run_ledger` upsert — start / finish, `mode`, `sheets_changed` | INTEGRATE | WR-04 populates `sheets_changed`; D-11 makes `mode` the incremental-vs-full channel |
| `table:sheet_registry` upsert — capture-time watermarks | INTEGRATE | D-01 `last_read_at` / `last_sheet_version` / `last_full_read_at` |
| `table:sheet_registry` upsert — `column_mapping` refresh | INTEGRATE | D-03: the weekly deep run is the sole writer of the mapping |
| `table:group_state` upsert — repair after membership change | INTEGRATE | D-03; the existing COALESCE preserves stored attachment ids |
| `table:row_state` UPDATE — set `deleted_at` | INTEGRATE | INC-03 / D-03. Lifts the Phase 10 COVERAGE.md OPT-OUT; the column was already reserved |
| `table:sheet_registry` SELECT — watermarks + stored `column_mapping` | INTEGRATE | INC-01 / D-01, D-02 trigger 2. Lifts the Phase 10 discovery OPT-OUT |
| `table:row_state` SELECT — affected `(wr, week)` pairs to sheet ids | INTEGRATE | INC-02 / D-04. Uses the existing `idx_row_state_wr_week` index |
| `table:row_state` SELECT — stored row-id set per sheet | INTEGRATE | INC-03: the left side of the deep run's deletion diff |
| `table:run_ledger` SELECT — previous run status / `finished_at` | INTEGRATE | D-02 trigger 6: a crashed run's partial watermarks are not a clean baseline |
| `table:run_ledger` SELECT — parity streak scan over `notes` | INTEGRATE | D-09: the streak is derived on demand, with no counter column (plan 07) |
| `table:group_state` SELECT — content-hash skip gate | INTEGRATE | INC-05 / D-12: becomes the sole skip gate once `hash_history.json` retires (plan 08) |
| `table:row_state` SELECT as the row CONTENT source for regeneration | OPT-OUT | D-05 approved partial: `row_state` stays membership-only. Deferred to a later slice, gated on D-04 running clean for 5 runs |
| `table:row_event` SELECT into the pipeline | OPT-OUT | Phase 12 ownership-history lookups (OWN-*) are the first in-pipeline consumer |
| Schema / DDL change — new column, index, RPC, or table | OPT-OUT | D-04 mandates zero schema change this phase; `pipeline_memory/schema.sql` is a protected area |
| `wr_week_ownership` table + reads/writes | OPT-OUT | Phase 12 (OWN-*), explicitly out of scope per CONTEXT.md `<domain>` |
| `audit_finding` / `audit_finding_event` tables | OPT-OUT | Phase 13 (AUD-*), explicitly out of scope per CONTEXT.md `<domain>` |
| `pg_cron` retention schedule for `row_event` | OPT-OUT | Shipped in Phase 10 and runs independently of the read/regeneration path |
| Remote feature-flag table as the incremental kill switch | OPT-OUT | D-11 locks the env-flag family; a per-run remote round-trip adds latency inside the time budget for no benefit |
| Supabase Auth / Storage / Realtime / Edge Functions | OPT-OUT | Server-side service-role batch job; no user-facing surface |
| Changing RLS policies or role GRANT/REVOKE | OPT-OUT | The Phase 10 service-role-only posture already covers every new SELECT; no new grant is needed |

## Surface 2 — Smartsheet API (SDK 4.3.0)

| capability | decision | reason |
|---|---|---|
| `Sheets.get_sheet(sheet_id, column_ids=...)` — full read | INTEGRATE | Unchanged full-mode path and the PHASE 2b scoped re-fetch (D-04) |
| `Sheets.get_sheet(..., if_version_after=...)` — version probe | INTEGRATE | INC-01 / D-01: an unchanged sheet costs one call and zero rows |
| `Sheets.get_sheet(..., rows_modified_since=...)` — delta read | INTEGRATE | INC-01 / D-01, with the fixed `SAFETY_WINDOW_MINUTES` overlap applied at filter time |
| Abbreviated-response detection on the version probe | INTEGRATE | INC-01. New production logic; only the MEM-04 experiment had it before |
| 401 / 403 classification for per-sheet isolation | INTEGRATE | D-02 trigger 3: isolate the sheet, do not retry-as-full in a loop |
| `Attachments` upload / delete on the target sheet | INTEGRATE | Existing upload path, now scoped by D-06 so nothing outside the affected scope is deleted |
| `Cells.get_cell_history` — selective audit enrichment | INTEGRATE | Existing behaviour behind `SKIP_CELL_HISTORY`; unchanged this phase |
| Folder-based sheet discovery (`Folders` / `Sheets` listing) | INTEGRATE | Existing discovery; its local cache retires to `sheet_registry` in plan 08 (INC-05) |
| Deleted-row detection via `rowsModifiedSince` | OPT-OUT | Structurally impossible — verified against SDK 4.3.0 and Smartsheet docs (D-03). The deep run's full-read diff covers it |
| Smartsheet webhooks / `Events` stream for push-based change notice | OPT-OUT | Would need a publicly reachable endpoint and a schedule change; 10-CONTEXT D-07 locks cron-driven polling |
| A separate sheet-version call before the delta read | OPT-OUT | `if_version_after` already returns the version on the abbreviated response; a second call doubles the request count |
| `Rows.get_row` per-row fetch | OPT-OUT | Bulk sheet read is the project standard; per-row fetching would breach the 300 req/min budget |
| Search / Reports / Sights / cross-sheet-reference APIs | OPT-OUT | Not needed by the billing pipeline; no requirement in INC-01..INC-05 references them |
| Raising `PARALLEL_WORKERS` above 8 | OPT-OUT | Hard project guardrail against the 300 req/min limit; the shadow adds calls to a run already at its ceiling |
| Any write to a source sheet (rows, cells, columns) | OPT-OUT | The pipeline reads source sheets and writes only attachments to the target sheet; unchanged |
