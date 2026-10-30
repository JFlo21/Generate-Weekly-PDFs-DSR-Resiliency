---
phase: "11"
slug: "incremental-read-affected-group-regeneration"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: "2026-09-12"
verified: "2026-09-12"
---
# Phase 11 — Security
> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register source: the `<threat_model>` blocks of all eight PLAN files (11-01..11-08) plus the
> `## Threat Flags` sections of SUMMARY 11-04..11-08. Verification depth: ASVS L1 (grep-level
> evidence that each mitigation exists in the implementation, plus the pinned test names).
> Note: the ID `T-11-06` was assigned twice at plan time (plan 01 ledger-append threat and plan 02
> watermark-integrity threat). Both are retained below, disambiguated by plan.
---
## Trust Boundaries
| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Smartsheet cell content → `pipeline_memory` NUMERIC columns | Operator-authored cell text crosses into typed Postgres columns via PostgREST | Quantity / price text (untrusted) |
| Smartsheet cell content → Supabase query predicate | WR and week-ending values flow into `row_state` filters | WR identifiers, dates |
| Smartsheet API → pipeline | Untrusted response shapes (abbreviated vs full `Sheet`, 401/403) cross the fetch layer | Sheet metadata, rows |
| Python process → Supabase `service_role` client | Every `pipeline_memory` read/write crosses this boundary | Row state, watermarks, run ledger |
| `pipeline_memory` → run-mode / regeneration-scope decision | Stored watermarks, prior run status and `row_state` membership decide how much source data the run reads and regenerates | Billing-adjacent scope decision |
| Run-scoped `groups` dict → destructive maintenance | The run's in-memory "live groups" decides what is deleted from Smartsheet and local state | Attachment delete, hash-history prune |
| Pipeline → Smartsheet attachment delete API | Delete calls against production billing artifacts, no undo | Excel attachments |
| Smartsheet full-read result → deletion inference | Row absence used as evidence of deletion | `row_state.deleted_at` |
| Deep run → `row_state.deleted_at` / `group_state` | Reconciliation writes to the store that later narrows regeneration scope | Deletion marks, attachment ids |
| Shadow block → session budget / run behaviour / flip decision | Parity shadow runs inside the production process; its verdict gates a production flag flip | Extra Smartsheet calls, verdict |
| Parity streak evidence → INC-05 retirement | A wrong streak reading authorises removing the rollback path | `run_ledger.notes` verdicts |
| Editor → protected workflow file | `weekly-excel-generation.yml` carries schedule, runner timeout and session budget | GitHub Actions config |
| Docs / Living Ledger | Operator docs must name env-var names and rules only | Never tokens, keys, row data |
---
## Threat Register
| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-11-01 | Tampering | `_row_to_payload` → NUMERIC cast | high | mitigate | `pipeline/orchestrate.py:816,821` parses Quantity / Units Total Price via `_pricing._parse_quantity` / `parse_price` before the writer; unparseable → NULL (writer docstring `pipeline_memory/writer.py:805`) | closed |
| T-11-02 | Repudiation | `run_ledger` finish row `sheets_changed` | medium | mitigate | Populated on both success (`orchestrate.py:5372`) and failure (`orchestrate.py:5727`) finish paths | closed |
| T-11-03 | Information disclosure | `run_ledger.notes` JSONB | low | mitigate | Only integer counters added (`delta_sheets_changed`, `delta_rows_count`, `mapped_sheet_count`; `orchestrate.py:1926`) | closed |
| T-11-04 | Elevation of privilege | `pipeline_memory` service-role client | low | accept | No new grant/table/schema; Phase 10 RLS + REVOKE posture unchanged (`pipeline_memory/schema.sql:585-592`) | closed |
| T-11-05 | Information disclosure | `docs/run-memory-write-flip-checklist.md`, living ledger | medium | mitigate | Secret-pattern scan (JWT, connection string, populated token/key assignments) → 0 hits in the checklist; ledger hits are blank-value `SUPABASE_SERVICE_ROLE_KEY=` recipe lines only | closed |
| T-11-06 (P01) | Tampering | `memory-bank/living-ledger.md` history | low | mitigate | Append-only, verified via `git diff --numstat` zero deletions (11-01-SUMMARY line 124) | closed |
| T-11-06 (P02) | Tampering | Watermark integrity (`sheet_registry.last_read_at`) | critical | mitigate | Capture-time instant persisted; `SAFETY_WINDOW_MINUTES` subtracted only at filter build (`orchestrate.py:1770`, `fetch.py:174`). Pinned: `test_subtracts_safety_window_from_capture_time`, `test_persists_caller_supplied_capture_time_verbatim`, `test_full_read_writes_last_full_read_at_equal_to_capture_time` | closed |
| T-11-07 | Denial of service (billing data) | Delta-read failure misread as "unchanged" | critical | mitigate | Every unconfirmed condition resolves to full mode with a non-empty `fallback_reason` (`orchestrate.py:978-987`). Pinned: `test_delta_probe_escalation_falls_back_to_full_mode` | closed |
| T-11-08 | Tampering | Stale `sheet_registry.column_mapping` | high | mitigate | Trigger 2 dict-equality drift → per-sheet full read (`orchestrate.py:1042-1046`); `_log_column_mapping_drift` | closed |
| T-11-09 | Elevation of privilege | New `pipeline_memory` SELECT queries | low | accept | Same `service_role` client; Phase 10 RLS + REVOKE unchanged; no schema change | closed |
| T-11-10 | Information disclosure | Smartsheet token in retry/Sentry paths | medium | mitigate | Delta read routes through existing `smartsheet_call_with_retry` (`pipeline/retry.py`, used by `fetch.py`, `discovery.py`, `orchestrate.py`); no new header/credential logging | closed |
| T-11-11 | Repudiation | Silent mode fallback | high | mitigate | `run_ledger.mode` + `notes.fallback_reason` recorded on every full-mode resolution (`orchestrate.py:980`) | closed |
| T-11-12 | Tampering / data loss | `cleanup_untracked_sheet_attachments` via `valid_wr_weeks` | critical | mitigate | `keep_historical=True` when `_resolved_mode == 'incremental'` at both call sites (`orchestrate.py:5225,5309`). Pinned: `test_strict_subset_groups_issues_zero_deletes_for_untouched_identities` | closed |
| T-11-13 | Tampering / data loss | Hash-history stale-key prune | critical | mitigate | Full-mode gate added in plan 03; the prune and the hash-history dict were then retired outright by plan 08 (INC-05). Pinned: `test_stale_key_prune_gate_removed_from_source` — surface no longer exists | closed |
| T-11-14 | Tampering | Seven off-contract / legacy-migration gates | medium | mitigate | No code change to gates; pinned: `test_absent_wr_excluded_from_all_three_scope_sets`, `test_zero_offcontract_deletions_for_wr_absent_from_groups`, `test_pipeline_cleanup_offcontract_gates_diff_is_untouched` | closed |
| T-11-15 | Repudiation | Scoped counters read as full-run counters | medium | mitigate | Counters documented as interpretable only next to `run_ledger.mode` (`orchestrate.py:5356`); `run_summary.json` not overloaded | closed |
| T-11-16 | Denial of service | Global `KEEP_HISTORICAL_WEEKS` flipped process-wide | high | mitigate | Override is a call-boundary keyword; env constant untouched (`pipeline/cleanup.py:212,323-324`) | closed |
| T-11-17 | Tampering | `map_affected_to_sheets` query construction | high | mitigate | Typed `.in_()` builder, no interpolation (`pipeline_memory/reader.py:282-301`). Pinned: `test_wr_metacharacters_carried_as_bound_value_not_interpolated` | closed |
| T-11-18 | Denial of service (silent omission) | Narrowed scope from partial/failed mapping | critical | mitigate | Empty/cannot-confirm mapping → full mode with `fallback_reason` (`orchestrate.py:1684-1686`); partial chunk union discarded. Pinned: `test_writer_one_failed_chunk_is_partial_and_keeps_good_chunk` | closed |
| T-11-19 | Tampering | Incomplete group content after scoped re-fetch | critical | mitigate | Mapping widens to every sheet holding an affected pair; PHASE 2b re-fetches those sheets in full (`orchestrate.py:1643,1678`). Pinned: `test_sheets_written_reflects_delta_change_not_phase2b_refetch_count`, `test_moved_week_keeps_both_new_and_prior_pair_groups` | closed |
| T-11-20 | Repudiation | Scoped counters vs full-run counters | medium | mitigate | Delta-read and re-fetch scope reported as distinct keys; `rows_seen` documented as comparable only against another incremental run (`orchestrate.py:5387`) | closed |
| T-11-21 | Information disclosure | `run_ledger.notes` counters | low | accept | Integer counts only; no WR identifiers or row content beyond Phase 10 | closed |
| T-11-22 | Elevation of privilege | New `row_state` SELECT | low | accept | Same client, same RLS/REVOKE posture, existing SELECT grant | closed |
| T-11-23 | Repudiation | Vacuous parity pass | critical | mitigate | `pass` requires `groups_compared > 0` and both inputs valid (`pipeline/parity.py:122,142,161`); otherwise `skipped` with reason | closed |
| T-11-24 | Denial of service | Shadow consuming session budget | high | mitigate | `RUN_MEMORY_SHADOW_MAX_MINUTES` (10) sub-budget + `RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC` (45) per-call timeout + pre-flight guard (`orchestrate.py:4560-4663`); `PARALLEL_WORKERS` not raised | closed |
| T-11-25 | Tampering | Shadow mutating watermarks | high | mitigate | Read-only contract; pinned: `test_never_calls_registry_write` (`tests/test_parity_shadow.py`) | closed |
| T-11-26 | Tampering | Shadow altering run behaviour on fail | critical | mitigate | Compute-and-compare only; pinned: `test_fail_verdict_never_touches_generation_upload_cleanup`, `test_never_touches_generation_upload_cleanup` | closed |
| T-11-27 | Information disclosure | `parity_details` in `run_ledger.notes` | medium | mitigate | Carries group keys, hashes, counts, sheet/row ids only (`orchestrate.py:~4676`) | closed |
| T-11-28 | Information disclosure | Sentry event on parity fail | medium | mitigate | Message carries `groups_compared`, verdict and `run_id` only via `sentry_capture_message_with_context` (`orchestrate.py:~4684-4694`) | closed |
| T-11-29 | Denial of service | Extra Smartsheet calls vs 300 req/min | medium | mitigate | Existing retry wrapper; `PARALLEL_WORKERS` cap unchanged; one probe call per unchanged sheet | closed |
| T-11-30 | Tampering / data loss | Deletion inference from zero-row/partial read | critical | mitigate | Zero-row or unread sheet skipped with warning + breadcrumb (`orchestrate.py:~2025-2050`). Pinned: `test_zero_row_full_read_marks_zero_deleted_and_skips`, `test_sheet_absent_from_live_map_is_treated_as_zero_row` | closed |
| T-11-31 | Tampering | Wrong deletions narrowing future scope | high | mitigate | `deleted_at` only on `weekly_comprehensive` after successful full read; `mark_rows_deleted` fail-open. Pinned: `test_failure_returns_zero_count_empty_pairs` | closed |
| T-11-32 | Tampering | `group_state` repair nulling attachment ids | high | mitigate | Repair rides existing `upsert_group_state` COALESCE path. Pinned: `test_repaired_records_never_carry_attachment_keys` | closed |
| T-11-33 | Tampering | Drifted `column_mapping` adopted on frequent run | high | mitigate | Only deep run refreshes mapping; frequent run escalates to full read. Pinned: `test_production_frequent_run_issues_zero_refresh_writes_when_all_registered` | closed |
| T-11-34 | Elevation of privilege | New `row_state` UPDATE from writer | low | accept | Same client; existing schema-wide UPDATE grant; no schema change | closed |
| T-11-35 | Information disclosure | Deletion logs / breadcrumbs | low | mitigate | Reconciliation `logging.warning` / `sentry_add_breadcrumb` calls carry sheet ids, row ids, counts only (`orchestrate.py:~2025-2051`) | closed |
| T-11-36 | Repudiation | Falsely satisfied parity streak | critical | mitigate | `get_parity_streak` derived on demand from `run_ledger`, returns `contributing_run_ids`, returns `None` when it cannot confirm (`pipeline_memory/reader.py:691-750`) | closed |
| T-11-37 | Denial of service | Rollback path removed while latent defect remains | high | mitigate | Blocking owner checkpoint: plan 07 recorded `defer` (2026-08-26); decision re-opened 2026-08-31 as `retire-now` on a real 5/5 streak reading; removals landed in a separate plan (11-08) and separate PR | closed |
| T-11-38 | Tampering | Collateral edit to protected workflow | critical | mitigate | Only state-cache steps removed; schedule (`cron` lines 20-22), `timeout-minutes: 180` (line 130), `advanced_options` parser (line 100) survive; only the pip cache (`actions/cache@v4`, `~/.cache/pip`) remains | closed |
| T-11-39 | Denial of service | Budget/timeout mismatch hard-kill | high | mitigate | `TIME_BUDGET_MINUTES: '165'` (line 545) < `timeout-minutes: 180` (line 130); 15-minute gap intact | closed |
| T-11-40 | Tampering | Escalation flags broken by hash-history removal | high | mitigate | Flags asserted against `group_state` in `tests/test_incremental_read.py` (references `RESET_HASH_HISTORY` et al.) and `test_reset_hash_history_followed_by_prune_is_noop` | closed |
| T-11-41 | Tampering | Attachment identity lost with pre-fetch cache | high | mitigate | `pipeline/cleanup.py:342-343` per-row on-demand fallback when `attachment_cache` lacks the row; `group_state` ids preferred (Phase 11 Plan 08, INC-05) | closed |
| T-11-42 | Tampering | Counter column / cached streak drifting from evidence | medium | mitigate | No `streak`/counter column in `pipeline_memory/schema.sql` (grep 0 hits); `git diff --exit-code -- pipeline_memory/schema.sql` verify in plan 07 | closed |
| T-11-43 | Repudiation | Stale authorisation between 11-07 decision and 11-08 PR | high | mitigate | Owner-only re-authorisation recorded in 11-07-SUMMARY "Task 2 — DECISION RE-OPENED (2026-08-31)" with a real `get_parity_streak()` = 5/5 reading on master `d9bd2b2`; 11-08 gate satisfied by citation (`human_judgment: true`) | closed |
| T-11-44 | Information disclosure | Secrets / row data in Living Ledger | medium | mitigate | Secret-pattern scan of `memory-bank/living-ledger.md`: only blank-value env recipe lines; no tokens, keys, connection strings or row data | closed |
*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*
---
## Accepted Risks Log
| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-11-01 | T-11-04 | Writer reuses the existing `service_role` client; no new grant, table or schema exposure. Phase 10 RLS + `REVOKE ALL FROM anon, authenticated` unchanged. | Juan Flores (owner, plan-time disposition) | 2026-09-12 |
| AR-11-02 | T-11-09 | New `pipeline_memory` SELECTs reuse the existing client and grant; no schema change. | Juan Flores (owner, plan-time disposition) | 2026-09-12 |
| AR-11-03 | T-11-21 | `run_ledger.notes` gains integer counts only; no identifiers or row content beyond Phase 10. | Juan Flores (owner, plan-time disposition) | 2026-09-12 |
| AR-11-04 | T-11-22 | New `row_state` SELECT: same client, same RLS/REVOKE posture, existing grant. | Juan Flores (owner, plan-time disposition) | 2026-09-12 |
| AR-11-05 | T-11-34 | New `row_state` UPDATE: same client, existing schema-wide UPDATE grant from Phase 10; confirmed against `pipeline_memory/schema.sql`. | Juan Flores (owner, plan-time disposition) | 2026-09-12 |
*Accepted risks do not resurface in future audit runs.*
---
## Security Audit Trail
| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-12 | 45 | 45 | 0 | /gsd:secure-phase 11 (orchestrator, ASVS L1 grep-level; short-circuit rule — register authored at plan time, no open threats, no auditor subagent required) |

### Audit notes (2026-09-12)
- Verification depth is L1: mitigation presence confirmed by grep against `pipeline/`, `pipeline_memory/`, `tests/`, `.github/workflows/`, docs and the phase SUMMARY files. No end-to-end trace (L3) was performed; not required at `security_asvs_level: 1`.
- T-11-43's closure rests on the owner's documented re-authorisation citation, not on a live streak re-derivation (the 11-08 executor recorded `human_judgment: true`). Any future re-run of the INC-05 retirement decision must re-derive `get_parity_streak()` live.
- Manual-only items still open outside this gate (tracked in 11-VALIDATION.md, not security threats): `RUN_MEMORY_WRITE_ENABLED` flip approval, ≥5 production parity runs for INC-02 final acceptance, live deletion/formula detection on Sandbox.
---
## Sign-Off
- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
**Approval:** verified 2026-09-12
