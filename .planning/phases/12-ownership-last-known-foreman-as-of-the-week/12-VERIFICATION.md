---
phase: 12-ownership-last-known-foreman-as-of-the-week
verified: 2026-09-03T19:09:46Z
status: human_needed
score: 49/62 must-haves verified
behavior_unverified: 0 # No truth is "present but untested"; every unverified truth is an owner-executed live step (12-03 T4, 12-06) or a backstop needing direct evidence (Docusaurus build)
overrides_applied: 6 # PASSED (override) items included in score — plan text superseded by SUMMARY addenda / owner re-decisions; listed for owner confirmation in human_verification item 7
overrides:
  - must_have: "The workflow's schedule is a single Sunday 05:00 UTC cron and its workflow_dispatch inputs are bound to env: entries, never interpolated into run: shell text."
    reason: "Owner re-decided 12-04 Task 3 to dispatch-only after Opus H1 (a cron would be a permanently green no-op on the production token). Shipped shape: no schedule: key, workflow_dispatch only, inputs bound to env: (mechanical scan: zero ${{ in any run: block). Cron returns in 12-06 with a real candidate source."
    accepted_by: "Juan (verbatim 'dispatch-only now (Recommended)', 12-04-SUMMARY § Re-decision); applied in 90d715b; orchestrator directive: verify against the addenda"
    accepted_at: "2026-09-03"
  - must_have: "scripts/backfill_cell_history_attribution.py resolves a claimer from the Smartsheet cell history of the role's name column at the timestamp its completion checkbox was checked, and tags every value it proposes with provenance 'operator'."
    reason: "Opus review: 'operator' means human-entered; a cell-history inference is machine-derived. Shipped tag is 'backfill_cell_history' (script line 656); 'operator' is reserved and unwritten. Resolution mechanism unchanged and tested (test_happy_path_uses_backfill_cell_history_provenance)."
    accepted_by: "orchestrator (12-04 pre-checkpoint review fix 101489d; vocabulary extended in 12-03 f3b6db3, presented at the 12-03 Task 3 checkpoint Juan approved)"
    accepted_at: "2026-09-03"
  - must_have: "attribution_snapshot.backfill_source carries a CHECK constraint restricted to 'live', 'backfill_artifacts', 'backfill_hash_history' and 'operator'; the file contains no cross-week provenance value and no occurrence of last_known_before_week (D-12-A)."
    reason: "Shipped CHECK and RPC guard accept five values — the four planned plus 'backfill_cell_history' (same reason as above). Still no cross-week value and zero occurrences of last_known_before_week; test_vocabulary_has_exactly_five_tags and test_check_and_guard_lists_match pin the set."
    accepted_by: "orchestrator (12-03 addendum 'Vocabulary extension for source 5', f3b6db3); Juan's 12-03 Task 3 'approve' recorded post-addendum"
    accepted_at: "2026-09-03"
  - must_have: "The sentinel-superseded delete gate at pipeline/cleanup.py:495-508 is unchanged apart from the predicate it calls."
    reason: "The gate hunk changed by exactly one line: the sibling-side check `and not _is_sentinel_identifier(_vw[3])` became `and _is_real_name_identifier(_vw[3])` (98b5ea3, Opus HIGH: narrowing the predicate had made every unlisted leading-underscore token a 'real name' by negation, so `_DATE_EXPECTED` could trigger deletion). The change is strictly safety-narrowing on the sibling side; the victim-side predicate and surrounding logic are otherwise byte-identical. Pinned by test_unlisted_underscore_sibling_never_triggers / test_underscore_real_name_sibling_is_neutral."
    accepted_by: "orchestrator (12-02 'Post-execution review fixes' addendum, Opus FIX-FIRST round)"
    accepted_at: "2026-09-03"
  - must_have: "Every cell-history request is self-paced by CELL_HISTORY_BACKFILL_PACE_SEC, never sleeping before the first call of the run, and the run stops fetching when either CELL_HISTORY_BACKFILL_MAX_REQUESTS (default 3000), CELL_HISTORY_BACKFILL_MAX_ROWS or the CELL_HISTORY_BACKFILL_MAX_MINUTES wall-clock deadline is reached; rows past any cap are reported unresolved, never silently dropped."
    reason: "Pacing, first-call-no-sleep and all three caps are implemented and tested. Deviation: when the request or wall-clock cap trips, the not-yet-attempted candidates are DEFERRED out of this run's report and counted in summary.cap_reached / summary.candidates_deferred (exit 0) rather than written as per-row 'unresolved' rows; the row cap still writes a per-row unresolved reason. Not silent — counted and logged; the rows stay unresolved in the sources 1-4 report and are retried next invocation."
    accepted_by: "orchestrator (12-04 pre-checkpoint review fix 101489d — caps re-checked before every request, cap trip defers)"
    accepted_at: "2026-09-03"
  - must_have: "A per-row exception is caught, logged as a WARNING, and leaves that row unresolved — one bad row never aborts the run."
    reason: "Opus HIGH 'laundered read failures': treating a Smartsheet/mapping read failure as 'unresolved' would silently produce a wrong report. Shipped: the failing candidate is marked status='error' (exception TYPE only in evidence), further Smartsheet calls stop, the report is still written with summary.read_failures / summary.aborted, and the process exits 7. Pinned by test_read_failure_aborts_run_with_error_status. This is the fail-closed direction for billing data."
    accepted_by: "orchestrator (12-04 pre-checkpoint review fix 101489d)"
    accepted_at: "2026-09-03"
human_verification:
  - test: "12-03 Task 4 (blocking-human): Juan applies billing_audit/own03_backfill_attribution.sql STEP 0-5 in the Supabase SQL editor and reports the seven answers (STEP 0 write-side column names; exact backup table name attribution_snapshot_backup_<YYYYMMDD> and row count; count equals live attribution_snapshot count; backfill_source / backfill_run_id visible; STEP 3 spot check true,true,false; STEP 4/5 applied + NOTIFY pgrst reload; STEP 6 no-op RPC returns skipped_no_row with zero rows carrying backfill_run_id). Pre-apply: confirm the applying role holds UPDATE on billing_audit.attribution_snapshot (RPC is SECURITY INVOKER; file grants EXECUTE only) and confirm the five-value backfill_source vocabulary."
    expected: "All four live objects exist; backup readable by service_role; zero rows of attribution_snapshot modified. Record the exact backup table name in 12-03-SUMMARY.md — the 12-01 --apply probe looks for attribution_snapshot_backup_<today UTC>, so STEP 1 and the 12-06 apply must happen on the same UTC day."
    why_human: "Owner-applied DDL against a production, data-team-owned billing table; no repo code may execute it (production-guardrails Supabase rule, plan precondition). Covers 12-03 backstop truth #10."
  - test: "12-06 Task 1 (blocking-human): after 12-03 T4 and merge to master, run `python scripts/backfill_claim_time_attribution.py --wr 19073866 --weeks 082425,083125,091425,092125` (dry-run default) against live data; review generated_docs/own03_backfill_report.csv; run the public.artifacts filename cross-check; run the read-only count of NULL / stale-week row_event / row_state rows for the target row_ids (Opus MEDIUM carried from PR #387). Then state APPROVE / APPROVE WITH SCOPE / REJECT in writing."
    expected: "Exit 0; the four WR 19073866 primary rows propose 'Avery Example' with source backfill_hash_history and name_fidelity desanitized; summary counts recorded in 12-06-SUMMARY.md with only counts, WR numbers and the fictional sample name."
    why_human: "Roadmap SC2 requires Juan's approval on the live report before any remediation; live Supabase reads are outside this verifier's remit (no network). The fixture-level equivalent (test_resolves_all_four_weeks_via_source_4) passed."
  - test: "12-06 Task 2 (blocking-human decision): choose apply-full / apply-scoped / hold and record the exact command scope in 12-06-SUMMARY.md."
    expected: "Decision recorded in writing before any --apply --i-approved-this invocation."
    why_human: "One-way production write authorization; never auto-approvable."
  - test: "12-06 Task 3 (blocking-human): run `--apply --i-approved-this` on the same UTC day as the STEP 1 backup; capture the updated / skipped_real_name / skipped_no_row tallies; compare attribution_snapshot against attribution_snapshot_backup_<YYYYMMDD> for rows with NULL backfill_run_id; sum the provenance breakdown."
    expected: "Exit 0; zero differences for rows with NULL backfill_run_id (no real name touched); provenance breakdown totals the updated tally; count of skipped_real_name recorded."
    why_human: "Live production mutation; the never-overwrite guarantee has two independent guards (Python _build_apply_payload filter + SQL WHERE is_sentinel_value) proven by unit/contract tests, but the live proof is the backup comparison."
  - test: "12-06 Task 4 (blocking-human): after the next scheduled weekly-excel-generation.yml run, check the run summary's sentinel_claimers_ignored for the backfilled WRs, confirm WR 19073866 WE 082425/083125/091425/092125 now carry _User_Avery_Example attachments and the stale _User_Unknown_Foreman / _User__NO_MATCH files were removed by the sentinel-superseded cleanup gate; spot-check three other remediated WRs; confirm no PPP attachment was deleted and no real-name attachment was lost; record run duration vs TIME_BUDGET_MINUTES (165)."
    expected: "Roadmap SC3 observed live: files regenerate under real names, no _User__NO_MATCH / _User_Unknown_Foreman churn remains (today ~154 regenerations per run), run finishes inside the time budget. Do not drop the backup table before this check passes. Also decide whether to restore the Sunday cron in cell-history-backfill.yml together with a candidate source and the M4 dispatch-time guard."
    why_human: "Requires a live scheduled run after the live apply; the code path (resolve_claimer reading frozen real names, cleanup gate with the CR-01 fail-safe) is present and unit-tested but its end-to-end effect on the 93 WRs cannot be produced in this branch."
  - test: "Run `npm --prefix website run build` and grep the output for 'Broken link' / 'broken anchors'."
    expected: "[SUCCESS] Generated static files; zero broken-link or broken-anchor lines (docusaurus.config.ts uses onBrokenLinks: 'warn', so the build will not fail on its own)."
    why_human: "12-05 backstop truth. This verifier ran `npm run typecheck` (tsc, exit 0) but did not run the full build because it writes website/build (git-ignored) and the instruction was to modify no file other than this report; no build output existed in the working tree to inspect."
  - test: "Confirm the six plan-text deviations recorded under `overrides:` above (dispatch-only workflow; backfill_cell_history provenance tag; five-value backfill_source CHECK; _is_real_name_identifier on the cleanup gate's sibling side; cap trip defers candidates; read failure marks status='error' and exits 7)."
    expected: "Juan either accepts them as recorded (they then stand as the phase contract) or asks for a change before 12-06."
    why_human: "Four of the six were orchestrator-decided Opus review fixes recorded in SUMMARY addenda; only dispatch-only and the five-tag vocabulary carry a recorded owner decision. Overrides count toward the score above and must not be accepted silently."
  - test: "unverified-prohibition — human review recommended: review the 22 unique judgment-tier prohibitions in § Prohibitions below. Each carries a NON-AUTHORITATIVE LLM-judge verdict with code/test evidence; the seven 12-06 prohibitions are not yet exercisable."
    expected: "No prohibition is contradicted by the shipped code. Flagged items: the source-5 script performs a bounded raw `.table('attribution_snapshot').limit(...)` scan for --check-backlog (not prohibited for that script; noted for awareness)."
    why_human: "ADR-550 D4: judgment-tier prohibitions in autonomous verify are recorded non-authoritatively and flagged, never silently passed."
---

# Phase 12: Ownership — last known foreman as of the week — Verification Report

**Phase Goal:** Each (WR, week) file is named for — and partitioned by — the foreman/helper/VAC who owned the job at that time, derived from observed history, never from a sentinel. Repairs the 2026-08-24 `_User_Unknown_Foreman` defect and the 93 affected WRs.
**Verified:** 2026-09-03T19:09:46Z (branch `feat/phase-12-wave-2`, HEAD `1b997af`; verified against this branch's working tree, not master)
**Status:** human_needed
**Re-verification:** No — initial verification

## Verification scope and method

- Plans 12-01, 12-02, 12-04, 12-05 complete; 12-03 complete through Task 3 (Juan approved the DDL apply) and paused at Task 4 (owner applies the SQL by hand); 12-06 not started (four blocking-human checkpoints, requires 12-03 T4 and merge to master). Per the orchestrator's instruction the live Supabase objects and the live remediation are classified as pending owner steps, not automated gaps.
- SUMMARY addenda ("Post-merge review fixes", "Pre-checkpoint review fixes", "Post-checkpoint review fixes", "Re-decision", "Vocabulary extension") were treated as superseding plan text; each resulting plan-text deviation is recorded as an explicit override (frontmatter) rather than absorbed silently.
- No network access was used: no Supabase or Smartsheet call. The six phase test files and `tests/test_sentinel_never_a_claimer.py` were run with `SMARTSHEET_API_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_KEY`, `SENTRY_DSN` unset (all tests use in-process fakes).
- `gsd-tools query verify.artifacts` / `verify.key-links` returned 0 items for every plan — the PLAN frontmatter lists artifacts and key_links as flat strings, which the tool does not parse. All artifact/link verification below is manual (grep, diff, targeted test runs).
- The gsd runtime identity check printed a WARNING (older gsd-tools without the `runtime-identity` verb); the tool was used only for the two query verbs above.

## Goal Achievement

### Observable Truths

Status key: ✓ VERIFIED · ✓ (override) PASSED via recorded override · ? HUMAN pending owner step / needs direct evidence.

#### Roadmap success criteria (the contract)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| SC1 | `resolve_claimer`/`freeze_row` never store or honor `Unknown Foreman` / `#…` as a claimer (TDD) | ✓ VERIFIED | `billing_audit/writer.py`: `is_sentinel_claimer` (105-115: None/blank/`#`-prefix/family after strip→underscore-to-space→collapse→casefold); `_null_if_named_sentinel` (118-124) applied to helper/vac_crew in `freeze_row` and `sentinel_freezes_deferred` when all roles sentinel (630-636); `resolve_claimer` reads a frozen sentinel as no-history and bumps `sentinel_claimers_ignored` (1141-1143). Behavioral: `tests/test_sentinel_never_a_claimer.py` 14 passed / 23 subtests (ResolveClaimerSentinelTests, FreezeRowSentinelTests). Note: the roadmap names `tests/test_billing_audit_shadow.py`; the sentinel TDD actually lives in `test_sentinel_never_a_claimer.py` (shadow file has 2 incidental mentions). |
| SC2 | Dry-run backfill report lists, per affected (WR, week), the proposed owner and its source; Juan approves before the live remediation | ? HUMAN | Mechanism verified: report columns include wr, week_ending, row_id, role, status, proposed_value, source, name_fidelity, evidence (test_csv_report_has_expected_columns); known-good sample resolves in fixtures (test_resolves_all_four_weeks_via_source_4). Juan's approval on live data is 12-06 Task 1 (not started) → human item 2. |
| SC3 | WR 19073866 WE 082425/083125/091425/092125 regenerate as `_User_Avery_Example` from `backfill_hash_history`; no `_User__NO_MATCH` / `_User_Unknown_Foreman` churn remains in the scheduled run | ? HUMAN | Code path present and unit-tested: resolver source 4 (script 590-720), `resolve_claimer` honors backfilled real frozen names (writer.py 1144), sentinel-superseded cleanup gate with CR-01 fix (cleanup.py 577-583; SentinelSupersededCleanupTests pass). Live effect requires 12-03 T4 + 12-06 T3/T4 → human items 1, 4, 5. |
| SC4 | Living Ledger + runbook document the amended Foundation A contract | ✓ VERIFIED | `memory-bank/living-ledger.md` `## [2026-09-03 13:55]` (line 9146, last entry in file, 78 lines) — "Amended Foundation A contract. First-write-wins still protects a real name…"; `website/docs/runbook/ownership-attribution.md` § "The amended Foundation A contract" (99-126) with the three enforcement points table. |

#### Plan 12-01 — OWN-03 claim-time backfill script

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Dry-run for WR 19073866 × 082425/083125/091425/092125 proposes 'Avery Example' via `backfill_hash_history`, zero Supabase writes | ✓ VERIFIED (fixture) | `test_resolves_all_four_weeks_via_source_4`; every fake table's write raises (`_RaisingWrite`). Live counterpart = 12-06 T1 (human item 2). |
| 2 | Ladder 1 (row_event/row_state) → 2 (same-row other role) → 3 (artifacts) → 4 (hash history) → sentinel; no cross-week rung | ✓ VERIFIED | `_SOURCE_RESOLVERS` registry (1077-1096); `_in_target_week` (877) applied in both source-1 loops (906, 922); `test_no_last_known_before_week_literal_in_non_comment_lines`, `test_no_source_ever_reads_an_adjacent_week`, 4 in-week guard tests (931-1013); grep: zero non-comment `last_known_before_week`. |
| 3 | Two distinct real names in source 3/4 → status 'conflict' listing both | ✓ VERIFIED | `_resolve_single_name` returns `_Conflict(names=sorted…)` (539-545); `test_source_3_two_names_conflict`, `test_two_names_in_source_4_is_a_conflict`. |
| 4 | No source names the row → 'unresolved' + reason, exit 0 | ✓ VERIFIED | `test_zero_candidates_across_all_sources_is_unresolved`, `test_unresolvable_row_reports_unresolved_and_exits_zero`. |
| 5 | Sentinel classification uses only `billing_audit.writer.is_sentinel_claimer`; no second sanitizer | ✓ VERIFIED | Lazy imports at 424, 508, 900, 950, 1256, 1442; `test_imports_is_sentinel_claimer_and_does_not_redefine_it`. |
| 6 | Precedence total/deterministic; tie-breaks by earliest observed_at / updated_at / filename; report sorted by (wr, week_ending, row_id, role) | ✓ VERIFIED | `.order("observed_at")` 791, `.order("row_modified_at")` 826, `.order("identifier")` 610/669, `.order("filename")` 1020; input rows sorted before grouping (513-523); `test_source_1_wins_over_3_and_4_when_all_present`, `DeterminismTests::test_shuffled_tied_rows_produce_identical_report`, `test_report_is_deterministic_across_two_runs`. Refinement: `_pick_best_entry` (555-573) prefers a pre-2026-08-24 `updated_at` then earliest — it selects the evidence string among entries for the SAME name, so the proposed value is unaffected. |
| 7 | Filename/identifier-derived values carry `name_fidelity` 'desanitized'; observed-name values 'exact' | ✓ VERIFIED | Sources 1/2 `fidelity="exact"` (917, 932, 966); sources 3/4 `name_fidelity="desanitized"` (713, 1074). |
| 8 | `--apply` never includes a p_rows entry whose current frozen value is a real name | ✓ VERIFIED | `_build_apply_payload` gates on `_is_named_sentinel(current_value)` (1266); `test_build_apply_payload_excludes_real_current_value`. |
| 9 | `--dry-run` default; `--apply` refused without `--i-approved-this` and a readable dated backup table | ✓ VERIFIED | exit 4 (1564), exit 3 (1689), exit 7 connectivity (1699); `test_apply_without_approval_returns_4_and_no_rpc_calls`, `test_apply_missing_backup_table_returns_3`, `test_apply_backup_probe_connectivity_error_returns_7`. |
| 10 | (backstop) report .json/.csv git-ignored | ✓ VERIFIED (observed) | `git check-ignore -v` → `.gitignore:87 generated_docs/own03_*.json`, `:88 generated_docs/own03_*.csv` for both report stems. |

#### Plan 12-02 — OWN-02 residuals CR-01 / WR-01

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `_is_sentinel_identifier` False for leading-underscore sanitized real names | ✓ VERIFIED | cleanup.py 157-167 (allowlist match only, else lazy `is_sentinel_claimer`); `test_real_names_with_leading_punctuation_are_not_sentinels`. |
| 2 | True for `_NO_MATCH`, `_REF_`, `_INVALID` and Unknown_Foreman/Helper/VAC_Crew family | ✓ VERIFIED | `_SANITIZED_ERROR_IDENTIFIERS` frozenset (98); `test_placeholders_and_bare_primary` incl. case variants. |
| 3 | Fail-safe direction: unrecognised leading-underscore token treated as not-a-sentinel, gate declines | ✓ VERIFIED | `_is_real_name_identifier` (170-195) keeps underscore tokens neutral on the sibling side too; `test_unlisted_underscore_sibling_never_triggers`, `test_underscore_real_name_sibling_is_neutral`. |
| 4 | Same normalization as `is_sentinel_claimer` | ✓ VERIFIED | cleanup.py 157 `" ".join(token.replace('_',' ').split()).casefold()` ≡ writer.py 114. |
| 5 | No module-level `AttachmentParentType` import; function-local in `_is_row_attachment` | ✓ VERIFIED | Only occurrences at orchestrate.py 1279-1328 (inside the helper/its warn function); guarded import 1321-1327; `StructuralImportPlacementTests` (2). |
| 6 | `_is_row_attachment` ROW→True, SHEET/COMMENT→False, string fallback | ✓ VERIFIED | `IsRowAttachmentBehaviorTests` (7 incl. simulated ImportError degrade + warns-once). |
| 7 | (backstop) delete gate unchanged apart from the predicate it calls | ✓ (override) | Diff master..HEAD gate hunk = one line: `- and not _is_sentinel_identifier(_vw[3])` / `+ and _is_real_name_identifier(_vw[3])` (98b5ea3, Opus HIGH). See override #4. |

#### Plan 12-03 — owner-deployed SQL (Tasks 1-3 done; Task 4 pending owner)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | SQL file is owner-applied; no repo code executes it | ✓ VERIFIED | Only references: script user-facing messages (49, 1686; cell-history 1055) and the contract test reading it as text (`_SQL_RELPATH`). |
| 2 | RPC updates a role column only where NULL/blank/`#`/sentinel family; enforced in SQL WHERE | ✓ VERIFIED | `is_sentinel_value` (211-233: NULL, btrim all whitespace, `LIKE '#%'`, normalized family); WHERE guards at 288/304/320. |
| 3 | One result row per input with `updated` / `skipped_real_name` / `skipped_no_row` | ✓ VERIFIED | CASE at 351-353; `test_apply_result_keys_appear_in_sql_case_vocabulary`. |
| 4 | Typed `jsonb_to_recordset` list is exactly the seven p_rows keys | ✓ VERIFIED | 234-242 (wr TEXT, week_ending DATE, smartsheet_row_id BIGINT, role, value, backfill_source, backfill_run_id TEXT); `test_build_apply_payload_keys_match_sql_column_list`, `test_apply_payload_key_set_is_exact_seven_keys`. |
| 5 | Three static per-role UPDATEs; raises on any other role; no dynamic SQL | ✓ VERIFIED | `RAISE EXCEPTION 'backfill_attribution: invalid role %'` (245); three CTEs 280-320; `test_no_execute_format` (zero `EXECUTE format`). |
| 6 | plpgsql, `SET search_path = ''`, schema-qualified, EXECUTE to service_role only | ✓ VERIFIED | 212-216, `#variable_conflict use_column`; `GRANT EXECUTE … TO service_role` (378); zero `TO anon` / `TO authenticated` (contract tests). |
| 7 | CHECK constraint restricted to four values; no cross-week value; no `last_known_before_week` | ✓ (override) | Five values shipped (137-141, RPC guard 254-255); zero `last_known_before_week`; see override #3. |
| 8 | STEP 0 information_schema query + one ADJUST HERE region | ✓ VERIFIED | 40 (`information_schema.columns`), 218 (`ADJUST HERE`); `Step0Tests`. |
| 9 | schema.sql gains a `backfill_attribution` contract-as-comment block in the freeze_attribution style | ✓ VERIFIED | schema.sql 222-283 (I/O contract, provenance vocabulary, D-12-A scope, operator note); +66 lines in diff. |
| 10 | (backstop) after apply, `attribution_snapshot_backup_<YYYYMMDD>` readable by service_role | ? HUMAN | `GRANT SELECT … TO service_role` present (83), but the object does not exist yet — 12-03 Task 4 pending (human item 1). |

#### Plan 12-04 — source 5 cell-history script + isolated workflow

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Resolves from checkbox-time cell history; tags 'operator' | ✓ (override) | Checkbox-first, in-window (`week_ending - 6 days`, 722) claim logic; tag `backfill_cell_history` (656). See override #2; `test_happy_path_uses_backfill_cell_history_provenance`. |
| 2 | Considers only rows sources 1-4 left 'unresolved'/'conflict' | ✓ VERIFIED | Candidates read from `own03_backfill_report.json`; `test_report_present_counts_unresolved_and_conflict_only`, `test_proposed_status_row_is_never_a_candidate`. |
| 3 | Self-paced; never sleeps before first call; stops at request/row/minute cap; capped rows never silently dropped | ✓ (override) | 875-984; `test_sleep_pacing_zero_before_first_one_before_subsequent`, `test_request_cap_defers_remaining_candidates`, `test_row_cap_env_var_stops_remaining_candidates`, `test_wall_clock_deadline_defers_before_any_fetch`. Cap trip defers (counted) — see override #5. |
| 4 | Per-row exception caught, WARNING, row unresolved, run continues | ✓ (override) | Shipped fail-closed: status='error', stop fetching, report written, exit 7 (`test_read_failure_aborts_run_with_error_status`). See override #6. |
| 5 | `--dry-run` default; `--check-backlog` bounded read prints `backlog_rows=<N>`, exit 0 | ✓ VERIFIED | 223, 340-400 (`.limit(_BACKLOG_FALLBACK_SCAN_LIMIT)`); `CheckBacklogTests` (3); broken backend now exits 7 instead of reporting 0. |
| 6 | No production module calls `get_cell_history` for this feature or reads `CELL_HISTORY_BACKFILL_*` | ✓ VERIFIED | grep: `get_cell_history` only at `pipeline/snapshot_drift.py:410` (pre-existing allowlisted caller) and the script; zero `CELL_HISTORY_BACKFILL` in `generate_weekly_pdfs.py`, `pipeline/`, `audit_billing_changes.py`; `CellHistoryProductionIsolationTests` (3). |
| 7 | Own concurrency group; `timeout-minutes` > `CELL_HISTORY_BACKFILL_MAX_MINUTES` | ✓ VERIFIED | `cell-history-backfill-${{ github.ref }}` (queue mode); `timeout-minutes: 60` vs env 45; `test_concurrency_group_is_isolated_from_production`, `test_timeout_exceeds_max_minutes_budget`. |
| 8 | Single Sunday 05:00 UTC cron; dispatch inputs bound to `env:` never interpolated into `run:` | ✓ (override) | Dispatch-only (no `schedule:` key, no `- cron:` line — mechanical scan); every `${{` lives in `env:`/`if:`/`with:`; zero `${{` inside any `run:` block (mechanical scan + `test_no_run_block_interpolates_expressions`). See override #1. |
| 9 | Backfill steps skipped when backlog reports 0 | ✓ VERIFIED | `if: steps.backlog.outputs.backlog_rows != '0'`; `test_backfill_step_is_gated_and_never_applies`. Caveat (documented, Opus H1): on a fresh runner the gate counts via Supabase while the backfill step consumes only the absent report file, so a dispatch today is a bounded no-op — the reason the cron was removed. |
| 10 | (backstop) never more than `MAX_REQUESTS` Smartsheet calls per run | ✓ VERIFIED (wired test) | Cap re-checked before every request (940-949); `test_request_cap_defers_remaining_candidates`, `test_cap_trips_between_a_single_candidates_own_two_requests`. |

#### Plan 12-05 — OWN-04 documentation

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Runbook documents the ladder AS IMPLEMENTED, no cross-week rung | ✓ VERIFIED | ownership-attribution.md 56-81 (six rungs incl. same-row other role and cell history); `last_known_before_week` count 0; `test_forbidden_literal_absent`. |
| 2 | Records D-12-A (no `wr_week_ownership`; deferred to Phase 13) | ✓ VERIFIED | 83-97 admonition; `test_wr_week_ownership_only_as_phase_13_deferral`. |
| 3 | Records D-12-B (Supabase hash store, no file flag, 2026-05-25 fall-through) | ✓ VERIFIED | 138-146 admonition + sources table row 4. |
| 4 | Records the amended Foundation A contract | ✓ VERIFIED | 99-126. |
| 5 | Distinguishes `backfill_attribution_snapshot.py` from `backfill_claim_time_attribution.py` with the do-not-run warning | ✓ VERIFIED | § "Two scripts, opposite semantics" (329-349, `:::danger Pitfall 4`). |
| 6 | Names the owning component for each flow | ✓ VERIFIED | § "Who owns what" table (399-407). |
| 7 | Documents rollback from `attribution_snapshot_backup_<YYYYMMDD>` | ✓ VERIFIED | § Rollback (382-397). |
| 8 | `sidebars.ts` lists the page under Runbook; nothing removed | ✓ VERIFIED | line 23 after `runbook/operations`; diff is +1/-0; `test_sidebar_lists_the_page`. |
| 9 | environment.md documents the four `CELL_HISTORY_BACKFILL_*` vars with defaults, never read by production | ✓ VERIFIED | 864-867 (3000 / 1200 / 0.5 / 45, each "never by the production run"). |
| 10 | Ledger gains one dated entry at the BOTTOM recording D-12-A, D-12-B, CR-01, Foundation A; CLAUDE.md untouched | ✓ VERIFIED | `## [2026-09-03 13:55]` is the last header (9146 of 9223); 10 hits for D-12-A/D-12-B/CR-01/WR-01/Foundation A/backfill_source/dispatch; `git diff --name-only master..HEAD -- CLAUDE.md` empty. |
| 11 | No real claimer name in any documentation file | ✓ VERIFIED | Added lines across website/ + ledger contain only Avery Example / Pat Example / Sam Sample and sentinel filename tokens (`_User_Unknown_Foreman`, `_User__NO_MATCH`, `_Helper_Unknown_Helper`, `_VacCrew_Unknown_VAC_Crew`, `_User_Avery_Example`). |
| 12 | (backstop) Docusaurus site still builds with no broken cross-links | ? HUMAN | `npm --prefix website run typecheck` (tsc) exit 0 this run; full build not executed (writes website/build; none present to inspect). Human item 6. |

#### Plan 12-06 — live rollout (not started; owner-executed)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Live dry-run: WR 19073866 four weeks → Avery Example via backfill_hash_history | ? HUMAN | Human item 2. |
| 2 | Juan approves the report before any --apply; recorded in 12-06-SUMMARY | ? HUMAN | Human item 2. |
| 3 | public.artifacts cross-check agrees or row flagged and not applied | ? HUMAN | Human item 2. |
| 4 | --apply reports updated / skipped_real_name / skipped_no_row tallies | ? HUMAN | Human item 4 (tally code path: script 1341-1400, `test_apply_updated_result_returns_0_and_report_gets_rpc_result`). |
| 5 | Zero real-name rows modified (backup comparison, NULL backfill_run_id) | ? HUMAN | Human item 4. |
| 6 | Post-apply scheduled run regenerates under real names, sentinel_claimers_ignored drops, stale attachments removed | ? HUMAN | Human item 5 (= roadmap SC3). |
| 7 | No PPP attachment deleted by the post-apply run | ? HUMAN | Human item 5. |
| 8 | No real claimer name copied into any committed file | ? HUMAN | Human items 2/4 (none present in the branch today — see 12-05 #11). |
| 9 | (backstop) post-apply run stays within TIME_BUDGET_MINUTES | ? HUMAN | Human item 5. |

**Score:** 49/62 truths verified (43 ✓ VERIFIED + 6 PASSED via override); 0 FAILED; 13 pending human (0 present-behavior-unverified).

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `scripts/backfill_claim_time_attribution.py` | OWN-03 sources 1-4 CLI + gated --apply | ✓ VERIFIED | 1747 lines; wired to `billing_audit.writer` (`is_sentinel_claimer`, `prefetch_attribution`) and `pipeline_memory` reads; imported by the source-5 script. |
| `tests/test_backfill_claim_time_attribution.py` | fixture-driven suite | ✓ VERIFIED | 1742 lines; 61 tests incl. ApplyPathTests, DeterminismTests, in-week guard tests. |
| `generated_docs/own03_backfill_report.{json,csv}` / `own03_cell_history_report.json` | dry-run outputs | N/A (by design) | Run outputs produced by a live dry-run (12-06 T1); git-ignored (PII); correctly absent from the tree. |
| `pipeline/cleanup.py` | CR-01 narrowed predicate + `_is_real_name_identifier` | ✓ VERIFIED | Diff +101 lines confined to the predicate region and one gate line; gate wired at 577/583. |
| `pipeline/orchestrate.py` | WR-01 function-local guarded import | ✓ VERIFIED | Import at 1321-1327 inside `_is_row_attachment`; warn-once helper. |
| `tests/test_lazy_smartsheet_imports.py` | structural + behavioral WR-01 suite | ✓ VERIFIED | 9 tests. |
| `tests/test_sentinel_superseded_cleanup.py` | extended CR-01 tests | ✓ VERIFIED | +60 lines; 3 predicate tests + sibling-side tests. |
| `billing_audit/own03_backfill_attribution.sql` | STEP 0-5 owner-applied file | ✓ VERIFIED (authored; NOT applied live) | 384 lines; all security-critical shapes present. |
| `billing_audit/schema.sql` | contract-as-comment block | ✓ VERIFIED | 222-283. |
| `tests/test_own03_backfill_sql_contract.py` | structural contract test | ✓ VERIFIED | 20 tests incl. Python↔SQL payload parity and five-tag vocabulary parity. |
| `scripts/backfill_cell_history_attribution.py` | source-5 paced/capped resolver | ✓ VERIFIED | 1113 lines; imports `bca` (12-01) for `_write_reports`, apply helpers, `_is_named_sentinel`, `with_retry` from `pipeline_memory.client`; no `pipeline.*` import. |
| `tests/test_backfill_cell_history_attribution.py` | resolver + isolation + workflow structure tests | ✓ VERIFIED | 45 tests (structural 4, backlog 3, resolution 15, isolation 3, workflow 14 — plus helpers). |
| `.github/workflows/cell-history-backfill.yml` | isolated dispatch-only runner | ✓ VERIFIED | 156 lines; `permissions: contents: read`; own concurrency group; timeout 60; caps pinned; gate step; never `--apply`; `dry_run=false` fails loudly; artifact upload keyed on `hashFiles`. |
| `website/docs/runbook/ownership-attribution.md` | runbook page | ✓ VERIFIED | 411 lines, 10 sections, reachable via sidebar. |
| `tests/test_own04_documentation.py` | docs structural gate | ✓ VERIFIED | 20 tests. |
| `website/sidebars.ts`, `scripts.md`, `workflows.md`, `reference/environment.md` | wiring/cross-links | ✓ VERIFIED | Links resolve to `ownership-attribution.md` (+anchors); env table 864-867. |
| `memory-bank/living-ledger.md` | dated bottom entry | ✓ VERIFIED | `[2026-09-03 13:55]`, 78 lines. |
| `.gitignore` | own03 report ignore | ✓ VERIFIED | lines 87-88. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `scripts/backfill_claim_time_attribution.py` | `billing_audit.writer.is_sentinel_claimer` | lazy import, no redefinition | ✓ WIRED | 6 import sites; structural test. |
| `scripts/backfill_claim_time_attribution.py` | `billing_audit.writer.prefetch_attribution` | sentinel discovery | ✓ WIRED | 1442-1449; zero raw `table("attribution_snapshot")` (structural test). |
| `scripts/backfill_claim_time_attribution.py` | `billing_audit.backfill_attribution(p_rows)` RPC | `.schema("billing_audit").rpc("backfill_attribution", {"p_rows": chunk})` | ✓ WIRED (contract) | 1341; payload keys == SQL typed list (parity tests). Live RPC does not exist yet (12-03 T4). |
| SQL typed column list | `_build_apply_payload` key set | seven keys | ✓ WIRED | `ApplyPayloadSqlParityTests`. |
| `billing_audit.is_sentinel_value` | `billing_audit.writer.is_sentinel_claimer` | SQL twin | ✓ WIRED | `SentinelVocabularyParityTests::test_every_sentinel_claimer_appears_in_sql`; same normalization steps. |
| `pipeline/cleanup.py::_is_sentinel_identifier` | `billing_audit.writer.is_sentinel_claimer` | lazy import | ✓ WIRED | 164-167. |
| `pipeline/orchestrate.py::_is_row_attachment` | `AttachmentParentType` | sole consumer, function-local | ✓ WIRED | 1321-1328. |
| `scripts/backfill_cell_history_attribution.py` | `scripts/backfill_claim_time_attribution.py` | `_write_reports(filename_stem=…)`, apply helpers, `_is_named_sentinel` | ✓ WIRED | 136, 866, 1013; `test_imports_report_writer_and_rpc_caller_no_duplicate_rpc_site`. |
| source-5 candidate set | sources 1-4 report | reads `own03_backfill_report.json`, filters unresolved/conflict | ✓ WIRED | one shared definition of 'unresolved'. |
| `cell-history-backfill.yml` | source-5 script | only scheduled/dispatch surface; `weekly-excel-generation.yml` untouched | ✓ WIRED | production workflow absent from `git diff --stat master..HEAD`. |
| `website/sidebars.ts` | `runbook/ownership-attribution` | Runbook category | ✓ WIRED | line 23. |
| `scripts.md` / `workflows.md` / `environment.md` | ownership page | Docusaurus file links | ✓ WIRED | 5 link sites. |
| `memory-bank/living-ledger.md` | durable record; CLAUDE.md untouched | — | ✓ WIRED | CLAUDE.md not in diff. |
| 12-06 `--apply` probe | backup table name from 12-03-SUMMARY | `attribution_snapshot_backup_<today UTC>` | ? PENDING | Name not yet recorded (12-03 T4); exit 3 on mismatch is implemented (1689). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| backfill report `proposed_value`/`source` | resolver `_Candidate` | Supabase `row_event`/`row_state` (chunked `.in_()`), `attribution_snapshot` via `prefetch_attribution`, `public.artifacts`, `group_content_hash`, `group_state` | Yes — no static/hardcoded return; `with_retry` `None` → connectivity error (exit 7), never a fake zero-row | ✓ FLOWING (fixture-proven; live = 12-06) |
| cell-history report | `client.Cells.get_cell_history` entries | Smartsheet (single call site 962) + `pipeline_memory.row_state`/`sheet_registry` for ids | Yes; documented live limitation: `pipeline_memory` surfaces are empty until `RUN_MEMORY_WRITE_ENABLED` is on | ✓ FLOWING (fixture-proven) |
| workflow `backlog_rows` output | `--check-backlog` stdout | report count or LIMIT-capped Supabase scan | Yes | ✓ FLOWING |
| Docs pages | static | — | N/A | — |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| All six phase test files pass with no network env | `python -m pytest tests/test_backfill_claim_time_attribution.py tests/test_backfill_cell_history_attribution.py tests/test_own03_backfill_sql_contract.py tests/test_lazy_smartsheet_imports.py tests/test_sentinel_superseded_cleanup.py tests/test_own04_documentation.py -q` (SMARTSHEET/SUPABASE/SENTRY vars unset) | `159 passed, 62 subtests passed in 6.83s` | ✓ PASS |
| SC1 sentinel-never-a-claimer TDD | `python -m pytest tests/test_sentinel_never_a_claimer.py -q` | `14 passed, 23 subtests passed` | ✓ PASS |
| Docs TypeScript | `npm --prefix website run typecheck` (tsc) | exit 0 | ✓ PASS |
| Docusaurus full build + link check | not run (writes website/build) | — | ? SKIP → human item 6 |
| Report files ignored | `git check-ignore -v generated_docs/own03_*` | `.gitignore:87/88` | ✓ PASS |
| Workflow injection / schedule / apply scan | python line scan of `cell-history-backfill.yml` | `run-block ${{ hits: []`, `schedule key: False`, `cron lines: []`, `--apply` only in an input description | ✓ PASS |
| Production isolation | `grep -rn get_cell_history / CELL_HISTORY_BACKFILL` over prod modules | only `pipeline/snapshot_drift.py:410` (pre-existing); zero env reads | ✓ PASS |
| All 26 SUMMARY-cited commits exist | `git cat-file -e` | 26/26 OK | ✓ PASS |
| Branch scope | `git diff --stat master..HEAD` | 22 files; no `weekly-excel-generation.yml`, no `CLAUDE.md`, no `requirements.txt` | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| --- | --- | --- | --- |
| — | `find scripts -path '*/tests/probe-*.sh'`; grep PLAN/SUMMARY for `probe-*.sh` | none found, none declared | SKIPPED (no probes for this phase) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| OWN-01 | 12-01, 12-03, 12-05 | Ladder decides each (WR, week, variant, role) owner; sentinels never stored as names | ✓ SATISFIED (code, as re-scoped by D-12-A) / ? live DDL pending | REQUIREMENTS.md wording is stale (names `wr_week_ownership` and `last_known_before_week`; ROADMAP D-12-A and the runbook say so). As implemented: `attribution_snapshot` + `resolve_claimer` + script ladder + `backfill_source`/`backfill_run_id` (SQL authored, not yet applied — human item 1). Sentinels never stored: `freeze_row` nulls, RPC WHERE. |
| OWN-02 | 12-02, 12-06 | `freeze_row`/`resolve_claimer` treat sentinel as no-claimer; partition | ✓ SATISFIED | SC1 evidence; CR-01/WR-01 residuals closed with tests. "partition by `wr_week_ownership`" clause stale per D-12-A (partition is by `attribution_snapshot`). 12-06's live confirmation pending (human item 5). |
| OWN-03 | 12-01, 12-03, 12-04, 12-06 | Dry-run-first backfill; 93 WRs / 5,824 rows remediated; attachments replaced; validated on WR 19073866 | ? NEEDS HUMAN (tooling complete; remediation not performed) | Sources 1-5, SQL, workflow all present and tested; known-good sample validated at fixture level only. Live remediation = 12-03 T4 + 12-06 (human items 1-5). Wording stale: source 4 reads the Supabase hash store, not `hash_history.json` (D-12-B). |
| OWN-04 | 12-05 | Foundation A amendment documented in ledger + runbook; helper/VAC follow the same ladder | ✓ SATISFIED | SC4 evidence; script `--roles primary,helper,vac_crew` default; RPC has three per-role statements; runbook § Who owns a (WR, week) file covers all three roles. |

Orphaned requirements: none — REQUIREMENTS.md maps exactly OWN-01..04 to Phase 12 and all four appear in plan frontmatter. REQUIREMENTS.md still shows all four as "Pending" (orchestrator-owned tracking).

### Prohibitions (judgment-tier; NON-AUTHORITATIVE LLM-judge verdicts — human review recommended)

| # | Prohibition (deduplicated; plans) | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | Never store or honor a sentinel as a claimer, any role/source (12-01, 12-02) | not violated | `is_sentinel_claimer` filter at every source (913/928/962), RPC guard raises on a sentinel value (247), WHERE gates. |
| 2 | Never overwrite a real (non-sentinel) frozen name (12-01, 12-03, 12-04, 12-06) | not violated (code); live proof pending | `_build_apply_payload` filter + `is_sentinel_value` WHERE; `test_build_apply_payload_excludes_real_current_value`. |
| 3 | Never infer ownership across weeks (12-01) | not violated | `_in_target_week`, zero cross-week literal, adjacent-week tests. |
| 4 | Never apply Supabase DDL/RPC definitions from script or pipeline code (12-01, 12-03) | not violated | No code reads/executes the .sql file. |
| 5 | Never commit claimer PII from the dry-run report (12-01, 12-06) | not violated | git-ignore rules; no report in tree. |
| 6 | Never read current Smartsheet row state as a backfill source (12-01) | not violated | 12-01 script has no `smartsheet` import (only prose mentions). |
| 7 | Never delete an attachment of a real claimer (12-02) | not violated | Fail-safe direction on both gate sides; sibling tests. |
| 8 | Never change the surrounding delete gate logic while fixing the predicate (12-02) | deviation, accepted (override #4) | One sibling-side line changed to `_is_real_name_identifier`. |
| 9 | Never re-implement sentinel matching outside `billing_audit/writer.py` (12-02) | not violated | cleanup.py allowlist covers sanitized error TOKENS only; the named family stays in writer.py via lazy import. |
| 10 | Never grant EXECUTE on the RPC to anon/authenticated (12-03) | not violated | `test_no_grant_to_anon`, `test_no_grant_to_authenticated`. |
| 11 | Never build the UPDATE target by interpolation / `EXECUTE format` (12-03) | not violated | `test_no_execute_format`; three static statements. |
| 12 | Never add a cross-week provenance value to the CHECK (12-03) | not violated | five values, none cross-week. |
| 13 | Never call `Cells.get_cell_history` from `generate_weekly_pdfs.py` or any pipeline module for this feature (12-04) | not violated | allowlist = `pipeline/snapshot_drift.py` (pre-existing); structural test. |
| 14 | Never gate source 5 behind an env flag read in the production run (12-04) | not violated | zero `CELL_HISTORY_BACKFILL` in prod modules. |
| 15 | Never share the production workflow's concurrency group (12-04) | not violated | `cell-history-backfill-…` group. |
| 16 | Never interpolate a dispatch input into `run:` text (12-04) | not violated | mechanical scan + test. |
| 17 | Never add a custom Smartsheet retry loop (12-04) | not violated | only `pipeline_memory.client.with_retry` for Supabase reads; SDK 429 handling relied on. |
| 18 | Never raise PARALLEL_WORKERS above 8 / widen the shared budget (12-04) | not violated | no `PARALLEL_WORKERS` reference; pace 0.5 s = 40% of budget. |
| 19 | Never document a cross-week rung / real name / secret / ledger-in-CLAUDE.md / stale retired vars (12-05) | not violated | forbidden-literal tests; PII scan; CLAUDE.md untouched; retired vars already marked no-op. |
| 20 | Never append a contradicting stale paragraph (12-05) | not violated (judgment) | `environment.md` REMEDIATE_CLAIMERS passage rewritten rather than appended (12-05 deviation 4). |
| 21 | 12-06: never `--apply` before written approval / without the backup / never run `backfill_attribution_snapshot.py` on remediated WRs / never purge PPP / never drop the backup before post-run verification | not yet exercisable | 12-06 not started; the runbook and script gates encode each rule (exit 4, exit 3, Pitfall 4 warning). |
| 22 | Awareness (not a declared prohibition): the source-5 script performs a bounded raw `.table("attribution_snapshot").limit(…)` scan for `--check-backlog` fallback | flagged for awareness | 12-01's raw-read prohibition is scoped to the 12-01 script (its structural test passes); the 12-04 read is read-only and LIMIT-capped. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `scripts/backfill_claim_time_attribution.py` | 1572 | `except ImportError: pass` (optional `python-dotenv`) | ℹ️ Info | Benign; mirrors `backfill_attribution_snapshot.py`. |
| `scripts/backfill_cell_history_attribution.py` | 850 | same | ℹ️ Info | Benign. |
| `.planning/ROADMAP.md` | 736 | 12-03 marked `[x]` while `12-03-SUMMARY.md` has `status: halted` (Task 4 pending) and `requirements-completed: []` | ℹ️ Info | Tracking drift (orchestrator-owned); "Plans: 5/6 executed" counts a paused plan. |
| `.planning/STATE.md` | 40 | "Plan: 4 of 6" vs ROADMAP "5/6" | ℹ️ Info | Tracking drift. |
| `.planning/REQUIREMENTS.md` | 272-283 | OWN-01/02/03 wording names `wr_week_ownership`, `last_known_before_week`, `hash_history.json` — superseded by D-12-A / D-12-B | ℹ️ Info | Already flagged as stale in ROADMAP and the runbook; not a code gap. |
| `.planning/ROADMAP.md` | SC1 | cites `tests/test_billing_audit_shadow.py`; the sentinel TDD is `tests/test_sentinel_never_a_claimer.py` | ℹ️ Info | Wrong file name in the roadmap contract text. |

No `TBD` / `FIXME` / `XXX` / `TODO` / `HACK` / placeholder markers in any phase-modified file (grep hits are prose uses of "placeholder" describing sentinel names). No stub returns, no hardcoded empty data, no `NotImplementedError`.

### Human Verification Required

See the `human_verification` frontmatter list (8 items): (1) 12-03 Task 4 owner SQL apply + seven answers; (2) 12-06 Task 1 live dry-run review and approval (roadmap SC2) incl. the carried-over NULL/stale-week row_event/row_state count; (3) 12-06 Task 2 apply decision; (4) 12-06 Task 3 live apply + backup comparison; (5) 12-06 Task 4 post-run verification (roadmap SC3) and the cron-restore decision; (6) Docusaurus full build link check; (7) confirmation of the six recorded overrides; (8) review of the judgment-tier prohibition verdicts.

Sequencing constraint (from plan and review carry-overs): (1) must precede (2)-(4); the branch must be merged to master first; STEP 1 backup and the `--apply` must happen on the same UTC day; the applying role needs UPDATE on `billing_audit.attribution_snapshot`.

### Gaps Summary

No automated gaps. Every artifact exists, is substantive and wired; every roadmap success criterion is either verified in code (SC1, SC4) or blocked only on owner-executed live steps that the phase deliberately gates behind blocking-human checkpoints (SC2, SC3). Zero truths FAILED. Six plan-text deviations are carried as explicit overrides for owner confirmation. The phase goal — files partitioned by the claim-time owner, never a sentinel — is achieved in code and tests; its production effect on the 93 WRs is pending 12-03 Task 4 and plan 12-06.

---

_Verified: 2026-09-03T19:09:46Z_
_Verifier: Claude (gsd-verifier)_
