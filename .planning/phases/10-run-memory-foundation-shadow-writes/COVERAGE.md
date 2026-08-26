# API Coverage — Phase 10 (Supabase PostgREST `pipeline_memory` + Smartsheet SDK 4.3.0)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Produced at plan time per the API Coverage Decision Checkpoint
> (`api-coverage.cjs` detected: true).

Two external surfaces are in scope this phase:

1. **Supabase PostgREST** against the new `pipeline_memory` schema in project
   `poeyztlmsawfoqlanucc` (D-01) — a NEW integration surface.
2. **Smartsheet API via `smartsheet-python-sdk==4.3.0`** — for the MEM-04
   read-only formula-change experiment ONLY. The production Smartsheet read/upload
   path is untouched this phase (MEM-03 shadow-mode).

---

## Surface 1 — Supabase PostgREST (`pipeline_memory`)

| capability | decision | reason |
|---|---|---|
| `rpc:upsert_rows_bulk` (bulk upsert + server hash diff + `row_event` append) | INTEGRATE | |
| `table:run_ledger` upsert (run start / run finish) | INTEGRATE | |
| `table:sheet_registry` upsert (per discovered source sheet) | INTEGRATE | |
| `table:group_state` upsert (per generated file, post-upload) | INTEGRATE | |
| `pg_cron` retention schedule for `row_event` | INTEGRATE | D-06: 24-month sliced DELETE ships in the same versioned SQL file |
| RLS policies + role GRANT/REVOKE on all five tables | INTEGRATE | D-01: service-role-only |
| PostgREST schema exposure + schema-cache reload | INTEGRATE | D-02: explicit, verifiable operator step (PGRST106 footgun) |
| `table:row_state`/`row_event` SELECT from `scripts/mem04_passive_compare.py` | INTEGRATE | D-08 passive half compares consecutive shadow-run observations. Operator-run diagnostic with a credential-free default source; never imported, scheduled, or reachable from the pipeline. |
| `table:row_state` SELECT **into the pipeline** (read memory back to drive a run) | OPT-OUT | Phase 10 is write-only shadow mode (MEM-03). Readers are Phase 11 INC-02; reading in Phase 10 would make memory an input to a billing decision, which MEM-03 forbids. |
| `table:row_event` SELECT **into the pipeline** | OPT-OUT | Same — Phase 12 ownership-history lookups (OWN-*) are the first in-pipeline reader. |
| `table:group_state` SELECT (skip-gate lookup) | OPT-OUT | The Phase-10 skip gate stays on `hash_history.json` + `billing_audit.group_content_hash` (spec §7 parity gate). Retiring those is explicitly Deferred to Phase 11+. |
| `table:sheet_registry` SELECT (drive discovery from memory) | OPT-OUT | Discovery stays on `discovery_cache.json` this phase; registry-driven discovery is Phase 11 INC-01. |
| Deletion reconciliation (`row_state.deleted_at` write on full read) | OPT-OUT | Phase 11 INC-03 owns full-read deletion reconciliation. The `deleted_at` column is reserved in the Phase-10 DDL but never written. |
| `wr_week_ownership` table + writes | OPT-OUT | Phase 12 (OWN-*), explicitly out of scope per CONTEXT.md `<domain>`. |
| `audit_finding` / `audit_finding_event` tables + writes | OPT-OUT | Phase 13 (AUD-*), explicitly out of scope per CONTEXT.md `<domain>`. |
| Remote feature-flag table (a `billing_audit.feature_flag`-style kill switch) | OPT-OUT | CONTEXT.md discretion locks an env flag (`RUN_MEMORY_WRITE_ENABLED`) for the shadow rollout; a second remote-flag round-trip per run adds latency inside the time budget for no Phase-10 benefit. |
| Supabase Auth / Storage / Realtime / Edge Functions | OPT-OUT | Not needed — this is a server-side service-role batch writer. No user-facing surface. |
| `billing_audit.group_content_hash` modification | OPT-OUT | Explicitly Deferred in CONTEXT.md (`<deferred>`): not modified in Phase 10. |

## Surface 2 — Smartsheet API (SDK 4.3.0), MEM-04 experiment only

| capability | decision | reason |
|---|---|---|
| `Sheets.get_sheet(sheet_id, level=2)` — T0/T1 baseline full read | INTEGRATE | |
| `Sheets.get_sheet(..., if_version_after=<T0 version>)` — T2 probe | INTEGRATE | |
| `Sheets.get_sheet(rows_modified_since, level=2)` — T3 probe ± SAFETY_WINDOW | INTEGRATE | |
| Raw request/response capture to a replayable JSON cassette | INTEGRATE | D-08 evidence items 3 and 12 |
| `Sheets.create_sheet` / `Sheets.copy_sheet` / `Folders.create_folder` | OPT-OUT | D-08: ZERO Smartsheet API writes. Juan hand-creates the sandbox lookup + dependent sheets. |
| `Rows.add_rows` / `Rows.update_rows` / `Cells` writes | OPT-OUT | D-08: the triggering edits (blank the lookup value; edit a mapping value in place) are made BY HAND by Juan, never by the script. |
| `Sheets.update_sheet` / column-formula writes | OPT-OUT | D-08: same — the cross-sheet INDEX/MATCH formula is authored by hand. |
| `Attachments.*` (attach / delete / list) | OPT-OUT | The production attachment path is unchanged this phase; the MEM-04 rig has no attachments. |
| `Cells.get_cell_history` | OPT-OUT | Not needed to answer MEM-04 (does `rowsModifiedSince` surface a formula-only change). The production pipeline's existing selective cell-history path is untouched. |
| `Sheets.list_sheets` / `Folders.list_folders` discovery | OPT-OUT | The rig's two sheet ids are supplied by Juan as CLI arguments; no discovery walk needed and none should be run against production folders. |
| Webhooks / Events API (change-tracking alternative) | OPT-OUT | Out of scope for the v1.4 milestone — the design (spec §4) is poll-based `ifVersionAfter` + `rowsModifiedSince`; an event-driven redesign is not on the roadmap. |
| Production pipeline read path (`get_all_source_rows`) behaviour change | OPT-OUT | MEM-03 shadow-mode + D-07: every Phase-10 run is still a full read. Changing it is Phase 11 (INC-01). |

---

**Second-integration note.** Surface 2 is a *second* integration against the same
Smartsheet API the production pipeline already uses. Per the checkpoint rule, its
opt-outs were re-decided from a full-coverage baseline rather than inherited from
the production integration's shape — the write-family opt-outs above are driven by
D-08 (zero API writes), not by "the pipeline doesn't do that either."
