# API Coverage Matrix — Phase 11.1 (post-INC-05 runtime remediation)

Scope: the external-service surface this phase touched while remediating the INC-05
runtime regression (Smartsheet SDK 4.3.0 + Supabase `pipeline_memory`). Decisions are
the phase's own D-11.1-01..05 (`11.1-CONTEXT.md`) restated per capability; nothing new
is decided here. Produced 2026-09-02 for the `api-coverage.verify-pre` seal gate.

| capability | decision | reason |
|---|---|---|
| Smartsheet Sheets.list_sheets bulk version probe (get_last_sheet_versions) | INTEGRATE | D-11.1-01 registry-version skip index; one call per run replaces per-sheet validation when versions match |
| Smartsheet Sheets.get_sheet full validation | INTEGRATE | D-11.1-01 fail-closed doubt branch; any registry mismatch or probe failure falls back to the full INC-05 validation |
| Supabase pipeline_memory.get_sheet_watermarks (sheet_registry read) | INTEGRATE | D-11.1-01 source of last_sheet_version, name, column_mapping for the skip index |
| Smartsheet Attachments.list_all_attachments bulk listing (include_all) | INTEGRATE | D-11.1-02 pre-seeds the live attachment memo for the target and PPP sheets before the group loop |
| Smartsheet Attachments total_count pre-flight before the bulk listing | INTEGRATE | D-11.1-05 ceiling check (BULK_ATTACHMENT_LISTING_MAX_TOTAL, default 25000) guards the bulk call |
| Smartsheet Attachments.list_row_attachments per-row fallback | INTEGRATE | INC-05 contract kept for rows absent from a failed or skipped bulk listing; never removed |
| Bulk attachment listing above the total_count ceiling | OPT-OUT | D-11.1-05 accepted residual: fall back to per-row lookups with an ERROR line rather than page an oversized listing |
| Local JSON caches or Actions cache steps for discovery/attachment state | OPT-OUT | D-11.1-03 prohibits re-introducing what INC-05 retired; cross-run state lives only in pipeline_memory |
| Sub-budget timeout constants for the pre-seed (*_MAX_MINUTES, *_TIMEOUT_SEC) | OPT-OUT | D-11.1-03: the pre-seed is a single never-raising call, not a budgeted phase like the retired pre-fetch |
| Smartsheet webhooks or event stream for change capture | OPT-OUT | Assessed as a future Phase 14 (ledger 2026-09-01 19:45); out of this remediation's scope |
