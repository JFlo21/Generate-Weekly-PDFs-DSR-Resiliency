---
phase: "12"
slug: "ownership-last-known-foreman-as-of-the-week"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: "2026-09-12"
---

# Phase 12 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register source: the `<threat_model>` blocks of all ten PLAN files (12-01 .. 12-10). Threat IDs
> were reused across plans (T-12-20..28, T-12-30), so every ID below carries a `(Pnn)` plan suffix.
> Verification depth: ASVS L1 grep-level — mitigation located in the implementation, pinned test
> named, or live confirmation cited from the plan SUMMARY.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| `scripts/backfill_claim_time_attribution.py` → Supabase (`billing_audit`, `pipeline_memory`, `public`) | Service-role reads plus the single write RPC `billing_audit.backfill_attribution(jsonb)` | Billing attribution rows (claimer names, PII); service-role credential |
| `p_rows` jsonb payload → `billing_audit.attribution_snapshot` | Last checkpoint before a value becomes permanent billing attribution | Caller-shaped role / value / provenance tuples |
| Supabase role grants → the RPC | An over-broad grant would expose an attribution rewrite to a browser-reachable role | EXECUTE privilege |
| Repo `.sql` file → live production schema | Owner-applied, one-way DDL with no automated rollback | Backup table, provenance columns, function bodies |
| Filename identity → attachment-delete decision (`pipeline/cleanup.py`) | A lossily-sanitized string decides whether a billing attachment is deleted from `TARGET_SHEET_ID` | Sanitized claimer identifiers |
| `pipeline/orchestrate.py` → Smartsheet SDK internals | Deep third-party enum path import | Availability of the production entry module |
| `public.artifacts.filename` → backfill script (source 3) | Pipeline-authored but shape-drifting filenames parsed as untrusted structure | Claimer name fragments, document extensions |
| Backfill job → Smartsheet API (source 5) | Second consumer of the shared 300 req/min token | `get_cell_history` requests |
| `workflow_dispatch` inputs → runner shell | Operator free text reaches a `run:` block | WR filter, max-requests override |
| GitHub Actions secrets → job environment | `SMARTSHEET_API_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` enter the runner | Credentials |
| Report files / run artifacts → git working tree, Actions artifacts, reviewers | Dry-run and cell-history reports carry real claimer names | PII |
| Private billing data → committed documentation (runbook, Living Ledger, ROADMAP) | A committed markdown file could leak names or Supabase identifiers | PII, decision records |
| Operator command line → production billing attribution (`--apply`) | One CLI invocation rewrites thousands of attribution rows; the next scheduled run deletes and replaces real billing artifacts | Live billing rows, Smartsheet attachments |
| Owner decision → production write scope (12-08) | The answer sets how many rows 12-10/12-06 may rewrite | Scope decision |
| Authoring agent → review verdict (12-10) | Verdict must come from fresh context to be independent | Review evidence |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-12-01 (P01) | Tampering | `--apply` payload builder | critical | mitigate | `_build_apply_payload` filters `current_value` through `billing_audit.writer.is_sentinel_claimer` (`scripts/backfill_claim_time_attribution.py:1289-1298`); server-side `is_sentinel_value` WHERE in every UPDATE (see T-12-10). Pinned by the real-name-absent-from-payload assertions in `tests/test_backfill_claim_time_attribution.py`. | closed |
| T-12-02 (P01) | Information Disclosure | `generated_docs/own03_backfill_report.{json,csv}` | high | mitigate | `.gitignore:87-88` (`generated_docs/own03_*.json`, `generated_docs/own03_*.csv`); `git check-ignore -v` confirms both report names and the cell-history report resolve to those rules. | closed |
| T-12-03 (P01) | Information Disclosure | `SUPABASE_SERVICE_ROLE_KEY` in the new script | high | mitigate | Credential read only through `billing_audit.client.get_client` / `pipeline_memory.client.get_client` (`:600`, `:661`, `:780`); no log line formats a credential. | closed |
| T-12-04 (P01) | Denial of Service | Unbounded per-row Supabase reads | medium | mitigate | `_ROW_ID_CHUNK_SIZE = 500` with chunked `.in_("row_id", ...)` reads (`:748-837`); RPC called in chunks of ≤ 500 (`:1334-1335`). | closed |
| T-12-05 (P01) | Repudiation | Backfilled value indistinguishable from live | high | mitigate | Every payload row carries `backfill_source` and `backfill_run_id` (`:1316-1317`); run id appends `GITHUB_RUN_ATTEMPT` to `GITHUB_RUN_ID` when present (`:501-506`). | closed |
| T-12-06 (P01) | Tampering | Apply run with no rollback path | critical | mitigate | `_probe_backup_table_readable` (`:1202`) gates `--apply`; exit code 3 when `attribution_snapshot_backup_<YYYYMMDD>` is unreadable (`:46`, `:1727`). | closed |
| T-12-07 (P02) | Tampering | `pipeline/cleanup.py::_is_sentinel_identifier` delete gate | critical | mitigate | Leading-underscore branch narrowed to the `_SANITIZED_ERROR_IDENTIFIERS` allowlist (`pipeline/cleanup.py:98-167`); fail-safe direction is "real name, decline to delete". Pinned by the `_O_Brien` / `_Contractor__Smith` regression table in `tests/test_sentinel_superseded_cleanup.py:137-138,243-246`. | closed |
| T-12-08 (P02) | Denial of Service | `pipeline/orchestrate.py` module import | medium | mitigate | `smartsheet.models.enums.attachment_parent_type` imported lazily inside `_is_row_attachment` under `try`/`except` (`pipeline/orchestrate.py:1332-1362`); no module-scope enums import. Pinned by `tests/test_lazy_smartsheet_imports.py`. | closed |
| T-12-09 (P02) | Tampering | Second, drifting sentinel implementation | high | mitigate | `pipeline/cleanup.py:164-167` lazily imports and reuses `is_sentinel_claimer`; no sentinel regex exists in `pipeline/config.py`. | closed |
| T-12-10 (P03) | Tampering | `backfill_attribution` UPDATE statements | critical | mitigate | `AND billing_audit.is_sentinel_value(s.frozen_<role>)` in all three UPDATE WHERE clauses (`billing_audit/own03_backfill_attribution.sql:385,403,421`). Pinned by `tests/test_own03_backfill_sql_contract.py::test_contains_is_sentinel_value`. | closed |
| T-12-11 (P03) | Tampering | `p_rows` jsonb payload | high | mitigate | Typed `pg_catalog.jsonb_to_recordset(p_rows) AS q(...)` column list (`:314-321`); `RAISE EXCEPTION` on invalid role / sentinel value / invalid `backfill_source` (`:325-353`); zero `EXECUTE format`. Pinned by `test_typed_column_list_has_all_seven_names`, `test_no_execute_format`. | closed |
| T-12-12 (P03) | Elevation of Privilege | RPC grants | high | mitigate | `REVOKE ALL ... FROM PUBLIC, anon, authenticated` + `GRANT EXECUTE ... TO service_role` (`:487-488`); `SET search_path = ''` (`:238,294`). Pinned by `test_revokes_execute_from_public_and_client_roles`, `test_grants_execute_to_service_role`, `test_no_grant_to_anon`, `test_no_grant_to_authenticated`, `test_contains_set_search_path`. | closed |
| T-12-13 (P03) | Tampering | Irreversible bulk write, no rollback | critical | mitigate | STEP 1 `CREATE TABLE ... attribution_snapshot_backup_YYYYMMDD AS` (`:103-111`) precedes any write path; CLI exit-3 precondition (T-12-06); 12-03 Task 3 `checkpoint:decision` and Task 4 human checkpoint recorded in `12-03-SUMMARY.md`. | closed |
| T-12-14 (P03) | Repudiation | Backfilled values indistinguishable from live | high | mitigate | `backfill_source` / `backfill_run_id` provenance columns with `attribution_snapshot_backfill_source_check` constraint (`:192-216`). Pinned by `test_vocabulary_has_exactly_five_tags`, `test_no_cross_week_ladder_rung`. | closed |
| T-12-15 (P03) | Tampering | SQL and Python sentinel predicates drifting | high | mitigate | `test_every_sentinel_claimer_appears_in_sql` iterates `billing_audit.writer._SENTINEL_CLAIMERS` against the SQL body (`tests/test_own03_backfill_sql_contract.py:179-183`). | closed |
| T-12-16 (P04) | Denial of Service | Shared Smartsheet 300 req/min budget | high | mitigate | `CELL_HISTORY_BACKFILL_MAX_REQUESTS: '3000'` (`.github/workflows/cell-history-backfill.yml:63`), isolated concurrency group (`:13-14`), dispatch-only trigger. Pinned by `test_request_cap_defers_remaining_candidates`, `test_row_cap_env_var_stops_remaining_candidates`, `test_wall_clock_deadline_defers_before_any_fetch`, `test_budget_caps_are_pinned`, `test_concurrency_group_is_isolated_from_production`, `test_timeout_exceeds_max_minutes_budget`. | closed |
| T-12-17 (P04) | Tampering | Source 5 wired into the production run | high | mitigate | `test_get_cell_history_call_sites_are_exactly_the_allowlist`, `test_no_scanned_file_reads_cell_history_backfill_env_var`, `test_audit_billing_changes_stub_has_zero_get_cell_history_calls` (`tests/test_backfill_cell_history_attribution.py:934-971`). | closed |
| T-12-18 (P04) | Tampering | Workflow command injection via `workflow_dispatch` | high | mitigate | Every dispatch input bound to `env:` (`:114-120`) and read as a shell variable; positive-integer validation on `max_requests` (`:134-144`). Direct scan: zero `${{` inside any `run:` block. Pinned by `test_no_run_block_interpolates_expressions`, `test_every_dispatch_input_is_bound_to_env`, `test_zero_max_requests_is_rejected_by_the_workflow`. | closed |
| T-12-19 (P04) | Information Disclosure | Secrets in job logs | high | mitigate | Secrets bound only in step `env:` (`:92-94`, `:114-117`), never passed as CLI args; script logs counts only. | closed |
| T-12-20 (P04) | Information Disclosure | Uploaded report artifact carrying claimer names | medium | accept | Accepted risk AR-12-01 (below `high` block threshold). `retention-days: 30` (`:158`); report never committed (T-12-02). | closed |
| T-12-21 (P04) | Elevation of Privilege | Over-broad workflow token | medium | mitigate | `permissions: contents: read` at workflow level (`:3-4`). Pinned by `test_permissions_declare_a_single_read_only_scope`, `test_workflow_declares_jobs_and_read_only_token`. | closed |
| T-12-22 (P05) | Information Disclosure | Runbook page and Living Ledger entry | high | mitigate | `website/docs/runbook/ownership-attribution.md` uses fictional names only; `tests/test_own04_documentation.py::test_forbidden_literal_absent` asserts forbidden literals are absent. | closed |
| T-12-23 (P05) | Tampering | Stale documentation → wrong production action | high | mitigate | `test_both_backfill_scripts_are_named`, `test_sentinel_outcome_is_named`, `test_all_five_provenance_tags_named`, `test_forbidden_literal_absent` (`--hash-history`, dropped ladder rung) in `tests/test_own04_documentation.py`. | closed |
| T-12-24 (P05) | Repudiation | Decisions with no durable record | medium | mitigate | Living Ledger `[2026-09-03 13:55]` entry records D-12-A, D-12-B, amended Foundation A, CR-01, WR-01, source-5 isolation (`memory-bank/living-ledger.md:9182`). | closed |
| T-12-25 (P06) | Tampering | The live `--apply` write | critical | mitigate | Four controls confirmed in `12-06-SUMMARY.md:37-41`: Juan's verbatim `I approve`, `apply-full` decision, same-UTC-day backup `attribution_snapshot_backup_20260905` (221,276 rows), server-side sentinel WHERE; post-apply diff: 1,758 updated / 0 skipped / 0 errors / 0 differences on 219,518 untouched rows. | closed |
| T-12-26 (P06) | Tampering | Attachment deletion during post-apply regeneration | critical | mitigate | CR-01 fix (T-12-07) merged before apply; Task 4 spot-checks (`12-06-SUMMARY.md:187-193`) show real `_User_<name>` files regenerated and only the matching `_User_Unknown_Foreman` files removed. | closed |
| T-12-27 (P06) | Tampering | PPP attachments purged by a reset | high | mitigate | `RESET_WR_LIST` scoped to `TARGET_SHEET_ID` only (shipped, `pipeline/orchestrate.py`); ledger `[2026-09-02 00:35]` "PPP attachments are NEVER purged by a reset"; Task 4 observation recorded. | closed |
| T-12-28 (P06) | Information Disclosure | Real claimer names in dry-run report / summary | high | mitigate | Report git-ignored (T-12-02); `12-06-SUMMARY.md` records counts, WR numbers and fictional sample only. | closed |
| T-12-29 (P06) | Denial of Service | Regeneration burst overrunning the time budget | medium | accept | Accepted risk AR-12-02 (below `high` block threshold). Bounded by `TIME_BUDGET_MINUTES=165` graceful stop under `timeout-minutes: 180`. | closed |
| T-12-30 (P06) | Repudiation | Apply with no record of what was written | high | mitigate | `backfill_run_id` on every touched row; tallies and provenance breakdown recorded in `12-06-SUMMARY.md:41`. | closed |
| T-12-20 (P07) | Tampering | `_extract_claimer_from_filename` | critical | mitigate | Extension stripped via `_FILENAME_DOC_EXTENSION_RE` before the sentinel check; residual-extension candidates rejected (`scripts/backfill_claim_time_attribution.py:992-1014`). | closed |
| T-12-21 (P07) | Tampering | `_build_apply_payload` | high | mitigate | Second guard rejects a sentinel or extension-bearing `proposed_value` (`:1304`). | closed |
| T-12-22 (P07) | Information Disclosure | Skip-guard logging | medium | mitigate | Skip counters logged as counts; no `proposed_value` / `current_value` formatted into log lines (grep: zero matches). | closed |
| T-12-23 (P07) | Tampering | Test fixtures | medium | mitigate | Source-3 tests parameterized over both production filename shapes (`tests/test_backfill_claim_time_attribution.py:182-212,1253`). | closed |
| T-12-24 (P07) | Elevation of Privilege | Live Supabase write | high | mitigate | `12-07-SUMMARY.md` confirms no task ran `--apply`; apply stayed gated behind 12-06's checkpoint. | closed |
| T-12-25 (P08) | Elevation of Privilege | Scope decision | high | mitigate | Both decisions `gate="blocking-human"`; Juan's verbatim wording recorded (`12-08-SUMMARY.md:63-69`). | closed |
| T-12-26 (P08) | Tampering | `lookup_attribution_bulk` | high | mitigate | Option `defer` chosen (D-12-C); the shared production read surface was not edited by 12-08. | closed |
| T-12-27 (P08) | Information Disclosure | Ledger / runbook / ROADMAP | high | mitigate | Counts, WR numbers and option ids only; `test_forbidden_literal_absent`, `test_own03_remediation_scope_section_names_both_populations`. | closed |
| T-12-28 (P08) | Repudiation | Decision record | medium | mitigate | D-12-C / D-12-D mirrored as dated bullets in `.planning/ROADMAP.md:802` and `test_records_phase_12_gap_closure_decisions`. | closed |
| T-12-30 (P09) | Tampering | `backfill_attribution` validation loop | critical | mitigate | Extension guard `IF v_row.value ~* '\.(xlsx|xlsm|xls|csv|pdf|json)$' THEN RAISE EXCEPTION` runs before any UPDATE (`own03_backfill_attribution.sql:342-343`). Pinned by `test_rpc_raises_on_extension_bearing_proposed_value`. | closed |
| T-12-31 (P09) | Tampering | `is_sentinel_value` targeting semantics | high | mitigate | Predicate body pinned by `test_is_sentinel_value_body_unchanged` (`tests/test_own03_backfill_sql_contract.py:415`). | closed |
| T-12-32 (P09) | Elevation of Privilege | RPC EXECUTE grant | critical | mitigate | STEP 5 REVOKE/GRANT re-run after STEP 4; live ACL confirmed `{postgres, service_role}` (`12-09-SUMMARY.md:22,99`). | closed |
| T-12-33 (P09) | Information Disclosure | `RAISE EXCEPTION` message | medium | mitigate | Extension-guard message names role / wr / week / row_id only, never the offending value (`own03_backfill_attribution.sql:343-350`). | closed |
| T-12-34 (P09) | Elevation of Privilege | Agent-executed DDL | high | mitigate | DDL applied only at Juan's explicit real-time instruction through the interactive Supabase MCP; `12-09-SUMMARY.md` Threat Flags records the deviation and its acceptance. | closed |
| T-12-35 (P09) | Tampering | Python/SQL guard drift | medium | mitigate | `test_sql_extension_list_matches_python_constant` compares the SQL list to `_FILENAME_DOC_EXTENSION_RE` (`:373-397`); `test_check_and_guard_lists_match`. | closed |
| T-12-40 (P10) | Information Disclosure | Dry-run report | high | mitigate | `--report-dir` outside the working tree with an outside-tree warning (`scripts/backfill_claim_time_attribution.py:444-457`); `git status --porcelain` asserted clean (`12-10-SUMMARY.md:87`). | closed |
| T-12-41 (P10) | Repudiation | Fix verification | high | mitigate | Independent fresh-context Opus reviewer, 8-point rubric, verdict `pass`, zero fix round (`12-10-SUMMARY.md:16,44,107`). | closed |
| T-12-42 (P10) | Denial of Service | Missing backup | critical | mitigate | Same-UTC-day `attribution_snapshot_backup_20260904` created, service_role-readable, prior-day table preserved (`12-10-SUMMARY.md:17,71`). | closed |
| T-12-43 (P10) | Tampering | Premature apply | critical | mitigate | No 12-10 task passed `--apply` / `--i-approved-this`; apply remained gated behind 12-06 Task 2 (`12-10-SUMMARY.md`). | closed |
| T-12-44 (P10) | Spoofing | Scope drift | medium | mitigate | Verification run reproduced the diagnosing session's `--wr` / `--weeks` scope: 235-of-235 → 0-of-0 extension-bearing proposals (`12-10-SUMMARY.md:107`). | closed |
| T-12-45 (P10) | Elevation of Privilege | Agent-executed DDL | high | mitigate | STEP 1 backup created at Juan's direction; no unattended agent DDL (`12-10-SUMMARY.md:107`). | closed |
| T-12-SC (P01–P10) | Tampering | npm/pip/cargo installs | high | mitigate | Zero new third-party dependencies in the phase (`12-RESEARCH.md` § Package Legitimacy Audit); `requirements.txt` untouched; `website` build uses the existing lockfile. Ten identical plan-level entries collapsed into this row. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-12-01 | T-12-20 (P04) | The cell-history report artifact carries claimer names, but it is scoped to repository Actions retention (30 days), reviewers already see the same names in Smartsheet, and the report is never committed (`generated_docs/own03_*` git-ignored). | Juan Flores (plan 12-04 disposition `accept`) | 2026-09-02 |
| AR-12-02 | T-12-29 (P06) | The post-apply regeneration burst is bounded by the number of backfilled WRs and the `TIME_BUDGET_MINUTES=165` graceful stop under `timeout-minutes: 180`; a budget hit defers remaining WRs to the next run rather than failing. Observed in run 33974128574 (12-06 Task 4). | Juan Flores (plan 12-06 disposition `accept`; Task 4 `Approved` 2026-09-10) | 2026-09-10 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-12 | 61 (52 unique + 10× T-12-SC → 1 row) | 61 | 0 | /gsd:secure-phase 12 (Claude Fable 5.1, L1 grep-depth short-circuit) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-12
