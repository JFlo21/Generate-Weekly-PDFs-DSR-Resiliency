---
status: diagnosed
phase: 12-ownership-last-known-foreman-as-of-the-week
source: 12-01-SUMMARY.md, 12-02-SUMMARY.md, 12-03-SUMMARY.md, 12-04-SUMMARY.md, 12-05-SUMMARY.md, 12-06-SUMMARY.md
started: 2026-09-03T23:31:58Z
updated: 2026-09-04T01:21:38Z
---

## Current Test

[testing complete]

## Tests

### 1. Live SQL apply of the OWN-03 backfill objects (12-03 Tasks 3-4)
expected: In production Supabase the four objects from billing_audit/own03_backfill_attribution.sql exist live: the dated backup table attribution_snapshot_backup_<YYYYMMDD>, the backfill_source / backfill_run_id provenance columns with their five-value CHECK, the is_sentinel_value predicate, and the backfill_attribution RPC. EXECUTE on the RPC is granted to service_role only. The STEP 6 no-op smoke call returns skipped_no_row with zero attribution_snapshot rows modified, and the exact backup table name is recorded in 12-03-SUMMARY.md.
context: 12-03 coverage D3 (human_judgment) — one-way DDL against a production, data-team-owned billing table; Task 3 was a blocking-human decision and Task 4 a hands-on apply by the owner. Never automatable.
result: pass
evidence: Juan asked for a live read-only check via the Supabase MCP (project poeyztlmsawfoqlanucc, 2026-09-03 UTC): billing_audit.attribution_snapshot (220,433 rows) and attribution_snapshot_backup_20260903 (220,010 rows) both exist; columns backfill_source / backfill_run_id present with CHECK attribution_snapshot_backfill_source_check over the five values (live, backfill_artifacts, backfill_hash_history, backfill_cell_history, operator); backfill_attribution(p_rows jsonb) is SECURITY INVOKER with ACL {postgres,service_role} only (anon/authenticated/PUBLIC EXECUTE = false); is_sentinel_value(p_value text) present (keeps default PUBLIC EXECUTE, matching the SQL file which revokes only the RPC); 0 rows carry backfill_run_id and every backfill_source is NULL, so zero rows were modified. Backup name recorded in 12-03-SUMMARY.md line 248. Live is now 423 rows past the backup; 12-06 re-creates it on apply day. RPC not invoked (write path); the STEP 6 skipped_no_row result stands as recorded in 12-03-SUMMARY.md.

### 2. cell-history-backfill.yml is isolated from the production run and never applies (12-04 Task 3)
expected: In GitHub Actions the cell-history-backfill workflow is workflow_dispatch-only (no schedule key — the owner re-decided dispatch-only on 2026-09-03), runs under its own concurrency group separate from weekly-excel-generation, has timeout-minutes greater than CELL_HISTORY_BACKFILL_MAX_MINUTES, binds every dispatch input through env: (no input interpolated into run: shell text), and no step passes --apply. A manual dispatch against an empty backlog exits early through the --check-backlog gate without calling Smartsheet.
context: 12-04 coverage D5 (human_judgment) — the workflow's existence and schedule shape are an owner authorization, not a testable fact; unit tests prove the authored file honours the decision's constraints.
result: pass
evidence: Juan asked the session to run the check (read-only, no dispatch). Static inspection of .github/workflows/cell-history-backfill.yml on master (merge 1f159bc): 0 schedule: keys, 1 workflow_dispatch:; concurrency group cell-history-backfill-${{ github.ref }} vs production weekly-excel-${{ github.ref }}; timeout-minutes 60 > CELL_HISTORY_BACKFILL_MAX_MINUTES 45; all three inputs (dry_run, wr_filter, max_requests) bound in env: at lines 118-120 and zero ${{ }} inside any run: block; --apply appears only in two comments; step backlog runs --check-backlog and writes backlog_rows to GITHUB_OUTPUT, the backfill step is gated if: steps.backlog.outputs.backlog_rows != '0'. pytest tests/test_backfill_cell_history_attribution.py: 48 passed, 19 subtests (incl. test_dispatch_only_no_schedule, test_concurrency_group_is_isolated_from_production, test_timeout_exceeds_max_minutes_budget, test_backfill_step_is_gated_and_never_applies, test_no_run_block_interpolates_expressions, test_no_run_block_passes_apply, test_every_dispatch_input_is_bound_to_env, test_gate_step_writes_backlog_rows_output). GitHub registry: 'OWN-03 Cell History Attribution Backfill' active, id 349679975, total runs 0 (no cron has fired). The empty-backlog early exit is verified by the gate wiring plus CheckBacklogTests, not by a live dispatch.

### 3. Live OWN-03 dry-run report reviewed and a written verdict recorded (12-06 Task 1)
expected: A scoped dry-run of scripts/backfill_claim_time_attribution.py against live Supabase data exits 0 and produces generated_docs/own03_backfill_report.{json,csv}. Every proposed value is a real claimer name — no sentinel and no filename-derived placeholder such as "Unknown Foreman.xlsx" — and source-3 (public.artifacts filename) candidates carry the extension-stripped real name. The known-good sample resolves through backfill_hash_history. Juan records APPROVE / APPROVE WITH SCOPE / REJECT in writing in 12-06-SUMMARY.md before any --apply.
context: 12-06 coverage D1 (human_judgment) — human review of proposed claimer names, live production counts and operator domain knowledge; no automated check can approve a production billing-attribution write. Tasks 2-4 (apply decision, live apply, post-apply scheduled-run check) are gated on this verdict.
result: issue
reported: "reject: source-3 filename parser defect" (Juan's verbatim 12-06 Task 1 verdict, recorded in 12-06-SUMMARY.md; Juan asked the session to re-run the check itself)
severity: blocker
evidence: (1) Juan's full-set report generated_docs/own03_backfill_report.json (2026-09-03 17:15, git-ignored) analysed in-sandbox, counts only: 5,829 rows; proposed 4,762 / conflict 1,066 / unresolved 1; sources backfill_artifacts 5,136 / live 692; 4,070 proposed values end in .xlsx and ALL are the single string 'Unknown Foreman.xlsx' (a sentinel once the extension is stripped); 0 rows for WR 19073866; 0 rows resolved via backfill_hash_history. (2) Scoped live re-run by the session, read-only dry-run, report written to the session scratchpad (Juan's report untouched): --wr 89732091 --weeks 071325,072025,072725,080325,081025,090725,091425 -> exit 0, 235 sentinel rows considered, 235/235 status=proposed source=backfill_artifacts fidelity=desanitized proposed_value='Unknown Foreman.xlsx' with current_value 'Unknown Foreman'; evidence field shape 'primary|Unknown_Foreman.xlsx|<ts>'. The expected outcome (real names only, extension-stripped source-3 candidates, known-good sample via backfill_hash_history, APPROVE) is not met; an --apply would freeze the placeholder as a real name.

### 4. 12-01 D1 — Dry-run for the WR 19073866 known-good sample resolves the primary claimer via source 4 (backfill_hash_history) across all four weeks with zero writes
expected: End-to-end dry-run for the WR 19073866 known-good sample resolves the primary claimer via source 4 (backfill_hash_history) across all four weeks
result: pass
source: automated
coverage_id: 12-01/D1

### 5. 12-01 D2 — Sources 1, 2 and 3 resolve under the total 1->2->3->4 precedence, week-scoped, no cross-week rung
expected: Sources 1 (row_event/row_state), 2 (same-row other role) and 3 (public.artifacts filenames) resolve under the total 1->2->3->4 precedence
result: pass
source: automated
coverage_id: 12-01/D2

### 6. 12-01 D3 — Two distinct real names for the same (wr, week_ending, role) in source 3 or 4 produce status=conflict with an empty proposed_value
expected: Two distinct real names for the same (wr, week_ending, role) in source 3 or source 4 produce status=conflict with an empty proposed_value
result: pass
source: automated
coverage_id: 12-01/D3

### 7. 12-01 D4 — --apply refused without --i-approved-this (exit 4, zero RPC calls) and without a readable dated backup table
expected: The --apply write path is refused without --i-approved-this (exit 4, zero RPC calls) and refuses to write when the dated backup table is missing
result: pass
source: automated
coverage_id: 12-01/D4

### 8. 12-01 D5 — generated_docs/own03_backfill_report.{json,csv} are git-ignored and no plan task performs a live Supabase write
expected: generated_docs/own03_backfill_report.{json,csv} are git-ignored (claimer PII never committed) and no task in this plan performs a live Supabase write
result: pass
source: automated
coverage_id: 12-01/D5

### 9. 12-02 D1 — CR-01: real names with leading punctuation are never classified as sentinels; every pinned sentinel spelling still is
expected: A real claimer name whose sanitized identifier begins with a leading underscore is never classified as a sentinel, while every previously-pinned sentinel spelling (including case variants) still classifies as one
result: pass
source: automated
coverage_id: 12-02/D1

### 10. 12-02 D2 — WR-01: pipeline/orchestrate.py imports AttachmentParentType function-locally and degrades to a string comparison when unavailable
expected: pipeline/orchestrate.py has no module-top-level AttachmentParentType import; _is_row_attachment imports it function-locally and degrades to a plain string comparison instead of raising
result: pass
source: automated
coverage_id: 12-02/D2

### 11. 12-02 D3 — The sentinel-superseded delete gate in pipeline/cleanup.py is unchanged apart from the predicate it calls
expected: The sentinel-superseded delete gate at pipeline/cleanup.py is unchanged apart from the predicate it calls (single hunk confined to _is_sentinel_identifier)
result: pass
source: automated
coverage_id: 12-02/D3

### 12. 12-03 D1 — billing_audit/own03_backfill_attribution.sql is a reviewable, owner-applied file with a structural contract test pinning its security-critical shape
expected: The SQL file is authored end-to-end (backup table, provenance columns + CHECK, sentinel predicate, sentinel-only RPC, service_role-only grant) with tests/test_own03_backfill_sql_contract.py pinning its shape
result: pass
source: automated
coverage_id: 12-03/D1

### 13. 12-03 D2 — billing_audit/schema.sql documents the backfill_attribution RPC contract and D-12-A without asserting attribution_snapshot DDL
expected: schema.sql documents the seven-field p_rows payload, three-value result, sentinel-or-NULL-only invariant, service_role-only grant, and D-12-A (no wr_week_ownership table)
result: pass
source: automated
coverage_id: 12-03/D2

### 14. 12-04 D1 — backfill_cell_history_attribution.py resolves a claimer from Smartsheet cell history under hard caps, never proposing a sentinel
expected: scripts/backfill_cell_history_attribution.py resolves a claimer from Smartsheet cell history under hard request/row/wall-clock caps, self-paced, never proposing a sentinel
result: pass
source: automated
coverage_id: 12-04/D1

### 15. 12-04 D2 — Every cell-history request is self-paced and the run stops at the request/row/minute cap, reporting remaining candidates unresolved
expected: Every cell-history request is self-paced and the run stops fetching at the request/row/minute cap, reporting remaining candidates unresolved with a reason naming the cap
result: pass
source: automated
coverage_id: 12-04/D2

### 16. 12-04 D3 — A per-candidate exception leaves that candidate unresolved without aborting; --check-backlog is a bounded zero-Smartsheet-call read
expected: A per-candidate exception is caught, logged, and leaves that candidate unresolved without aborting the run; --check-backlog performs a bounded, zero-Smartsheet-call read
result: pass
source: automated
coverage_id: 12-04/D3

### 17. 12-04 D4 — No production module calls get_cell_history or reads a CELL_HISTORY_BACKFILL_* variable
expected: No production module (generate_weekly_pdfs.py, pipeline/*.py, audit_billing_changes.py) calls get_cell_history or reads a CELL_HISTORY_BACKFILL_* variable
result: pass
source: automated
coverage_id: 12-04/D4

### 18. 12-05 D1 — website/docs/runbook/ownership-attribution.md exists, is in the Runbook sidebar, and documents the ladder as implemented
expected: The runbook page exists, is reachable from the Runbook sidebar, and documents the ladder with D-12-A / D-12-B, the five provenance tags, both backfill scripts, rollback, and component ownership
result: pass
source: automated
coverage_id: 12-05/D1

### 19. 12-05 D2 — scripts.md, workflows.md and environment.md rewritten coherently with no broken cross-links (Docusaurus build SUCCESS)
expected: scripts.md, workflows.md and environment.md give one coherent account; npm --prefix website run build reports [SUCCESS] with no broken link or anchor
result: pass
source: automated
coverage_id: 12-05/D2

### 20. 12-05 D3 — memory-bank/living-ledger.md ends with one dated [2026-09-03 13:55] entry recording the Phase 12 decisions; CLAUDE.md untouched
expected: The ledger ends with one dated entry recording D-12-A, D-12-B, the amended Foundation A contract, CR-01, WR-01 and source-5 isolation; no secrets; CLAUDE.md untouched
result: pass
source: automated
coverage_id: 12-05/D3

### 21. 12-05 D4 — Documentation tests pass and no real claimer name appears in any documentation file
expected: tests/test_own04_documentation.py passes and only fictional names (Avery Example, Pat Example, Sam Sample) and sentinel tokens appear in the documentation delta
result: pass
source: automated
coverage_id: 12-05/D4

## Summary

total: 21
passed: 20
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->
- gap_id: G-12-3
  truth: "Live OWN-03 dry-run proposes only real claimer names (no sentinel, no filename-derived placeholder), source-3 candidates carry the extension-stripped real name, the known-good sample resolves via backfill_hash_history, and Juan approves the report before any --apply"
  status: failed
  reason: "User reported: reject: source-3 filename parser defect (Juan's verbatim 12-06 Task 1 verdict; re-confirmed by the session 2026-09-04: full-set report 4,070 of 4,762 proposals = 'Unknown Foreman.xlsx'; scoped live re-run WR 89732091 x 7 weeks exit 0 with 235/235 rows proposing 'Unknown Foreman.xlsx'; WR 19073866 has 0 rows in Supabase; 0 rows resolve via backfill_hash_history)"
  severity: blocker
  test: 3
  root_cause: "scripts/backfill_claim_time_attribution.py::_extract_claimer_from_filename strips only a _<6hex>.xlsx hash tail, but public.artifacts.filename (written by scripts/publish_artifacts_to_supabase.py::_parse_stable) is the stable hash-less name WR_<wr>_WeekEnding_<mmddyy>_User_<name>.xlsx, so the remainder 'Unknown_Foreman.xlsx' survives, is desanitized to 'Unknown Foreman.xlsx' and passes is_sentinel_claimer because the extension defeats the sentinel match. The billing_audit.backfill_attribution RPC guard is_sentinel_value(s.frozen_<role>) checks only the CURRENT value, never the PROPOSED one, so an --apply would freeze the placeholder as a permanent real name in 4,070 rows / 69 WRs. The 12-01 source-3 fixtures were all hash-suffixed, so the live shape was never exercised. Secondary gaps surfaced by the same review: billing_audit.lookup_attribution_bulk returns NULL for '#'-prefixed values, hiding the 945 '#NO MATCH' rows from targeting; the documented known-good sample WR 19073866 has zero rows in every Supabase store, so ROADMAP SC3 'via backfill_hash_history' is not provable from Supabase (WR 89829163 is a partial substitute pending Juan)."
  artifacts:
    - path: "scripts/backfill_claim_time_attribution.py"
      issue: "_extract_claimer_from_filename strips only the hash suffix; no extension strip before the sentinel check; _build_apply_payload has no proposed-value sentinel guard"
    - path: "billing_audit/own03_backfill_attribution.sql"
      issue: "backfill_attribution RPC WHERE guard checks is_sentinel_value(current) only; the proposed value is unguarded server-side"
    - path: "tests/test_backfill_claim_time_attribution.py"
      issue: "source-3 fixtures are all hash-suffixed; the live hash-less filename shape and the 'Unknown_Foreman.xlsx' case are untested"
    - path: "billing_audit/schema.sql (lookup_attribution_bulk)"
      issue: "returns NULL for '#'-prefixed values, so #NO MATCH rows are invisible to targeting (owner scope decision needed)"
  missing:
    - "Strip the file extension from every filename-derived candidate BEFORE the sentinel check and reject any candidate that still carries an extension (source 3)"
    - "Add a proposed-value guard in _build_apply_payload and in the backfill_attribution RPC so a value is_sentinel_value would reject can never be written (owner-applied SQL; production-guardrails Supabase rule)"
    - "Rebuild the 12-01 source-3 fixtures from the real hash-less filename shape WR_<wr>_WeekEnding_<mmddyy>_User_<name>.xlsx and add a regression test for 'Unknown_Foreman.xlsx'"
    - "Owner scope decision plus targeting fix for the 945 '#NO MATCH' rows hidden by lookup_attribution_bulk"
    - "Owner decision: replace the absent known-good sample (WR 19073866) with a provable one or amend ROADMAP SC3; then re-run 12-06 Task 1 on a fresh same-UTC-day backup"
  debug_session: ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-06-SUMMARY.md § Halted at Designed Stop (root cause live-evidenced 2026-09-03 and re-reproduced by this session; no separate debug agent run — nothing to re-derive)"
