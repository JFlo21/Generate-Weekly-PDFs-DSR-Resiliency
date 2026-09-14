---
status: complete
phase: 11-incremental-read-affected-group-regeneration
source: 11-01-SUMMARY.md, 11-02-SUMMARY.md, 11-03-SUMMARY.md, 11-04-SUMMARY.md, 11-05-SUMMARY.md, 11-06-SUMMARY.md, 11-07-SUMMARY.md, 11-08-SUMMARY.md
started: 2026-09-14T01:45:56Z
updated: 2026-09-14T07:02:20Z
---

## Current Test

[testing complete]

## Tests

### 1. Flip checklist content is operationally safe
expected: docs/run-memory-write-flip-checklist.md reads as a safe gate for the RUN_MEMORY_WRITE_ENABLED flip PR: preconditions, the IN-01 upload-enabled control run, the group_state attachment-id proof, and the low-activity comparator rerun are all listed with the correct env-var line and queries. memory-bank/living-ledger.md carries the dated WR-01 entry (append-only, no secrets) and .github/workflows/ is untouched.
result: pass
coverage_id: 11-01/D3

### 2. First post-flip run writes a parity verdict
expected: The first real production_frequent run after the RUN_MEMORY_WRITE_ENABLED flip persists a non-null parity_verdict and parity_details in run_ledger.notes (pass, fail, or skipped-with-reason) on both success and failure finish paths. run_summary.json keeps its frozen 21-key contract. A fail verdict appears in Sentry at error level with counts and run id only, never row content.
result: pass
validated_by: agent (owner-delegated)
evidence: |
  workflow RUN_MEMORY_WRITE_ENABLED=1 (weekly-excel-generation.yml:239); live run_ledger (Supabase poeyztlmsawfoqlanucc) production_frequent rows 2026-09-10..09-11 carry parity_verdict pass/fail/skipped with parity_details (read+group sides); success-path finish proven live, failure-path finish proven by orchestrate.py:5747-5750 + RunLedgerFailurePathTests (no live failed run since 2026-09-01 to observe); GoldenContractTests 21-key baseline passes (14 passed); Sentry issue GENERATE-WEEKLY-EXCEL-AH "Shadow-incremental parity FAIL" level=error, 9 events, context_data = run_id + counts only (orchestrate.py:4688-4714).
coverage_id: 11-05/D5

### 3. Weekly deep run reconciles a deleted row and a formula-only edit
expected: On the sandbox rig, delete one row and make one formula-only edit before a Monday weekly_comprehensive run. After the run, row_state shows deleted_at on the deleted row, group_state for the affected (WR, week_ending) pair is repaired, and sheet_registry.column_mapping is refreshed, matching the live-verification section in docs/run-memory-write-flip-checklist.md.
result: pass
validated_by: agent (owner-delegated)
evidence: |
  Live (Supabase poeyztlmsawfoqlanucc): weekly_comprehensive runs 33359937884.1 (2026-08-31) and 34086148733.1 (2026-09-07) recorded mem_deep_run_rows_deleted=6 and 15; row_state holds 21 rows with deleted_at across 7 sheets, all timestamped inside those two run windows (05:38-05:50 UTC), none outside — production deletion reconciliation is exercised for real, not only on the sandbox rig. group_state repair for deletion-affected pairs and weekly-only column_mapping refresh were not re-queried live (owner declined the follow-up query); they rest on the pinned 11-06 coverage entries D3/D4 (tests/test_deep_run_reconciliation.py) and the checklist section test (FormulaOnlyReconciliationTests). The explicit sandbox-rig delete + formula-only edit procedure itself was not performed in this session.
coverage_id: 11-06/D6

### 4. INC-05 retirement decision was owner-selected and recorded
expected: 11-07-SUMMARY.md records Juan's explicit INC-05 decision at the blocking checkpoint with the streak reading pasted alongside (initial option id defer, re-opened 2026-08-31 with a 5/5 reading), and plan 11-08 read that recorded option back. The retirement was authorised by the owner, not inferred by an agent.
result: pass
validated_by: agent (owner-delegated)
evidence: |
  11-07-SUMMARY.md "Task 2 -- USER DECISION (2026-08-26)" records option id `defer` selected by Juan with rationale verbatim and the (empty) streak reading; "Task 2 -- DECISION RE-OPENED (2026-08-31)" supersedes it with `retire-now` backed by a real get_parity_streak() = 5/5 reading on merged master d9bd2b2 (#372), contributing runs 33449808275.1..33396264753.1. 11-08-SUMMARY.md (lines 10, 56, 139-144) reads that recorded option id back and executed on branch feat/11-08-inc05-retirement; retirement merged as abf905d (#373, 2026-08-31, authored by Juan Flores). Owner-authorised, not agent-inferred.
coverage_id: 11-07/D4

### 5. Streak authorisation re-confirmed at execution time
expected: The pre-fetch cache retirement in plan 11-08 was executed only after a fresh get_parity_streak() read of 5 consecutive clean production_frequent runs on merged master (d9bd2b2), taken at execution time rather than cited from a stale record. (Note: this SUMMARY coverage entry has a malformed verification kind and should be corrected.)
result: pass
validated_by: agent (owner-delegated)
evidence: |
  Re-derived from pipeline_memory.run_ledger (Supabase poeyztlmsawfoqlanucc) as of 2026-08-31 23:55Z under D-09-as-amended semantics: newest-first 33449808275.1 pass, 33440295024.1 skipped (excluded), 33429256710.1 pass, 33418485870.1 pass, 33407578625.1 pass, 33396264753.1 pass, then 33347828997.1 (weekend_maintenance) fail stops the scan -> streak 5, identical contributing ids to the recorded reading. Reading taken on merged master d9bd2b2 (#372, 15:58Z) and 54 min before 11-08 first commit a0b0432 (2026-09-01 00:49Z); merged as #373 abf905d. Nuance: the 11-08 executor cited the owner reading rather than re-running get_parity_streak itself and said so; the authorisation was fresh, not stale. Malformed coverage kind on T-11-43 corrected to `other` in 11-08-SUMMARY.md.
coverage_id: 11-08/T-11-43

### 6. A decorated Quantity/Units Total Price cell (e.g. "12 ea", "$1,234.50") reaches upsert_rows_bulk as a parsed float via __mem_* row keys; a missing pre-parse yields NULL, never a raw string that drops the chunk (WR-01).
expected: A decorated Quantity/Units Total Price cell (e.g. "12 ea", "$1,234.50") reaches upsert_rows_bulk as a parsed float via __mem_* row keys; a missing pre-parse yields NULL, never a raw string that drops the chunk (WR-01).
result: pass
source: automated
coverage_id: 11-01/D1

### 7. run_ledger.sheets_changed is populated on both the success-path and failure-path run_ledger_finish calls (WR-04).
expected: run_ledger.sheets_changed is populated on both the success-path and failure-path run_ledger_finish calls (WR-04).
result: pass
source: automated
coverage_id: 11-01/D2

### 8. An unchanged registered sheet costs exactly one Sheets.get_sheet call and yields zero rows through fetch_sheet_delta; a changed sheet costs two, the second carrying the overlap-adjusted rows_modified_since (INC-01).
expected: An unchanged registered sheet costs exactly one Sheets.get_sheet call and yields zero rows through fetch_sheet_delta; a changed sheet costs two, the second carrying the overlap-adjusted rows_modified_since (INC-01).
result: pass
source: automated
coverage_id: 11-02/D1

### 9. A version-less abbreviated response, a Supabase read failure, or an unexpected exception always escalates to a full read — never reported as "unchanged" (T-11-07 fail-open direction).
expected: A version-less abbreviated response, a Supabase read failure, or an unexpected exception always escalates to a full read — never reported as "unchanged" (T-11-07 fail-open direction).
result: pass
source: automated
coverage_id: 11-02/D2

### 10. resolve_run_mode implements all seven D-02 full-read escalation triggers plus the RUN_MEMORY_INCREMENTAL_ENABLED flag gate, never raises, and always names a non-empty fallback_reason on every full-mode resolution.
expected: resolve_run_mode implements all seven D-02 full-read escalation triggers plus the RUN_MEMORY_INCREMENTAL_ENABLED flag gate, never raises, and always names a non-empty fallback_reason on every full-mode resolution.
result: pass
source: automated
coverage_id: 11-02/D3

### 11. Capture-time watermark persistence: last_read_at is the caller-supplied capture instant verbatim; last_full_read_at is omitted (never overwritten) on a delta read; a trigger-3-isolated sheet is excluded from the registry write entirely.
expected: Capture-time watermark persistence: last_read_at is the caller-supplied capture instant verbatim; last_full_read_at is omitted (never overwritten) on a delta read; a trigger-3-isolated sheet is excluded from the registry write entirely.
result: pass
source: automated
coverage_id: 11-02/D4

### 12. run_ledger.mode + notes.fallback_reason are visible on all three run_ledger write call sites; run_summary.json's frozen 21-key contract and the .github/workflows/ + pipeline_memory/schema.sql protected areas are untouched; bash scripts/run_6_gates.sh passes all 6 gates.
expected: run_ledger.mode + notes.fallback_reason are visible on all three run_ledger write call sites; run_summary.json's frozen 21-key contract and the .github/workflows/ + pipeline_memory/schema.sql protected areas are untouched; bash scripts/run_6_gates.sh passes all 6 gates.
result: pass
source: automated
coverage_id: 11-02/D5

### 13. keep_historical call-boundary override on cleanup_untracked_sheet_attachments — None falls back to KEEP_HISTORICAL_WEEKS (byte-identical for every existing caller); True/False override it explicitly; a strict-subset valid_wr_weeks with keep_historical=True issues zero attachment deletes for identities outside it.
expected: keep_historical call-boundary override on cleanup_untracked_sheet_attachments — None falls back to KEEP_HISTORICAL_WEEKS (byte-identical for every existing caller); True/False override it explicitly; a strict-subset valid_wr_weeks with keep_historical=True issues zero attachment deletes for identities outside it.
result: pass
source: automated
coverage_id: 11-03/D1

### 14. The hash-history stale-key prune requires both the pre-existing time-budget guard and the resolved mode being 'full'; an incremental run preserves every hash_history key it did not reach and logs the suppression with the preserved-key count; full-mode behavior (both pruning and the time-budget-exceeded skip) is unchanged.
expected: The hash-history stale-key prune requires both the pre-existing time-budget guard and the resolved mode being 'full'; an incremental run preserves every hash_history key it did not reach and logs the suppression with the preserved-key count; full-mode behavior (both pruning and the time-budget-exceeded skip) is unchanged.
result: pass
source: automated
coverage_id: 11-03/D2

### 15. The seven off-contract / legacy-migration gates inside cleanup_untracked_sheet_attachments are unmodified and pinned as already-scoped: a WR absent from `groups` is absent from sub_wr_scope, vac_legacy_wr_scope, and primary_wr_scope, and zero off-contract deletions are issued for it. run_ledger_finish's scoped counters (groups_generated/groups_affected/rows_seen) are documented as interpretable only next to run_ledger.mode; run_summary.json's frozen 21-key contract is untouched.
expected: The seven off-contract / legacy-migration gates inside cleanup_untracked_sheet_attachments are unmodified and pinned as already-scoped: a WR absent from `groups` is absent from sub_wr_scope, vac_legacy_wr_scope, and primary_wr_scope, and zero off-contract deletions are issued for it. run_ledger_finish's scoped counters (groups_generated/groups_affected/rows_seen) are documented as interpretable only next to run_ledger.mode; run_summary.json's frozen 21-key contract is untouched.
result: pass
source: automated
coverage_id: 11-03/D3

### 16. In incremental mode, PHASE 2a issues a per-sheet delta read (full read for trigger1/trigger2-flagged sheets, skip for trigger3-isolated sheets), hands the collected rows to the unmodified _run_memory_write_phase, maps the returned affected set to every sheet holding a row_state row for it, and PHASE 2b re-fetches only those sheets via the unmodified get_all_source_rows; full mode is byte-for-byte the pre-plan single-call path.
expected: In incremental mode, PHASE 2a issues a per-sheet delta read (full read for trigger1/trigger2-flagged sheets, skip for trigger3-isolated sheets), hands the collected rows to the unmodified _run_memory_write_phase, maps the returned affected set to every sheet holding a row_state row for it, and PHASE 2b re-fetches only those sheets via the unmodified get_all_source_rows; full mode is byte-for-byte the pre-plan single-call path.
result: pass
source: automated
coverage_id: 11-04/D1

### 17. The affected-pair restriction is applied to `groups` AFTER the unmodified group_source_rows() call -- a group either survives in full or is dropped entirely, never partially reconstructed; a moved week keeps both the new pair's group and the prior pair's group.
expected: The affected-pair restriction is applied to `groups` AFTER the unmodified group_source_rows() call -- a group either survives in full or is dropped entirely, never partially reconstructed; a moved week keeps both the new pair's group and the prior pair's group.
result: pass
source: automated
coverage_id: 11-04/D2

### 18. Every failure in the delta read, the memory write, or the affected-set mapping resolves the run to full mode with a non-empty fallback_reason -- the scope can only ever be too wide, never too narrow. An empty affected set (nothing changed) is distinguished from a failed mapping and is recorded as a successful zero-group incremental run.
expected: Every failure in the delta read, the memory write, or the affected-set mapping resolves the run to full mode with a non-empty fallback_reason -- the scope can only ever be too wide, never too narrow. An empty affected set (nothing changed) is distinguished from a failed mapping and is recorded as a successful zero-group incremental run.
result: pass
source: automated
coverage_id: 11-04/D3

### 19. run_ledger.sheets_changed on an incremental run reflects the delta-read changed-sheet count, not the PHASE 2b re-fetch count; the two scopes are reported as distinct notes-only counters at both run_ledger_finish call sites; run_summary.json's frozen 21-key contract and the D-05 REQUIREMENTS.md note are both in place.
expected: run_ledger.sheets_changed on an incremental run reflects the delta-read changed-sheet count, not the PHASE 2b re-fetch count; the two scopes are reported as distinct notes-only counters at both run_ledger_finish call sites; run_summary.json's frozen 21-key contract and the D-05 REQUIREMENTS.md note are both in place.
result: pass
source: automated
coverage_id: 11-04/D4

### 20. Every full production_frequent run with RUN_MEMORY_WRITE_ENABLED on and RUN_MEMORY_INCREMENTAL_ENABLED off computes a two-sided group verdict (candidate set from _filter_groups_to_affected(groups, _mem_affected) vs actual set from _deferred_group_state) with order-independent set comparison and per-group hash equality over the intersection, using only already-computed calculate_data_hash() values.
expected: Every full production_frequent run with RUN_MEMORY_WRITE_ENABLED on and RUN_MEMORY_INCREMENTAL_ENABLED off computes a two-sided group verdict (candidate set from _filter_groups_to_affected(groups, _mem_affected) vs actual set from _deferred_group_state) with order-independent set comparison and per-group hash equality over the intersection, using only already-computed calculate_data_hash() values.
result: pass
source: automated
coverage_id: 11-05/D1

### 21. A comparison that could not fully execute (zero groups on both sides, None inputs, an unexpected exception, insufficient session budget, zero sheets probed) reports skipped with a reason and never pass; a fail on the group side or the read side is never silently dropped when combined into the overall parity_verdict.
expected: A comparison that could not fully execute (zero groups on both sides, None inputs, an unexpected exception, insufficient session budget, zero sheets probed) reports skipped with a reason and never pass; a fail on the group side or the read side is never silently dropped when combined into the overall parity_verdict.
result: pass
source: automated
coverage_id: 11-05/D2

### 22. The shadow issues real per-sheet D-01 delta probes (reusing pipeline.fetch.fetch_sheet_delta and the persisted watermarks) under a sub-budget with a pre-flight guard, a per-call timeout that marks a stuck sheet NOT COMPARED (never compared-and-clean), and a phase-level abandon; PARALLEL_WORKERS is not raised; it never calls upsert_sheet_registry or otherwise mutates a watermark.
expected: The shadow issues real per-sheet D-01 delta probes (reusing pipeline.fetch.fetch_sheet_delta and the persisted watermarks) under a sub-budget with a pre-flight guard, a per-call timeout that marks a stuck sheet NOT COMPARED (never compared-and-clean), and a phase-level abandon; PARALLEL_WORKERS is not raised; it never calls upsert_sheet_registry or otherwise mutates a watermark.
result: pass
source: automated
coverage_id: 11-05/D3

### 23. Every row whose content hash changed in this run's upsert_rows_bulk (read back from pipeline_memory.row_event) that is absent from the shadow delta read's row set is a read-side fail naming the sheet and row id; a sheet never successfully probed contributes neither a pass nor a fail for its changed rows.
expected: Every row whose content hash changed in this run's upsert_rows_bulk (read back from pipeline_memory.row_event) that is absent from the shadow delta read's row set is a read-side fail naming the sheet and row id; a sheet never successfully probed contributes neither a pass nor a fail for its changed rows.
result: pass
source: automated
coverage_id: 11-05/D4

### 24. The weekly deep run diffs stored row_state row ids against its own full read's row ids per sheet and marks the difference deleted (row_state.deleted_at), never rewriting an already-deleted row.
expected: The weekly deep run diffs stored row_state row ids against its own full read's row ids per sheet and marks the difference deleted (row_state.deleted_at), never rewriting an already-deleted row.
result: pass
source: automated
coverage_id: 11-06/D1

### 25. A zero-row or partial full read never produces a deletion -- a sheet with no observed live rows this run (indistinguishable, by design, from an unsuccessfully-read sheet given available signals) is skipped entirely with a warning + Sentry breadcrumb, never inferred as 'every row deleted'.
expected: A zero-row or partial full read never produces a deletion -- a sheet with no observed live rows this run (indistinguishable, by design, from an unsuccessfully-read sheet given available signals) is skipped entirely with a warning + Sentry breadcrumb, never inferred as 'every row deleted'.
result: pass
source: automated
coverage_id: 11-06/D2

### 26. group_state rows for a deletion-affected (wr, week_ending) pair are confirmed repaired via the existing post-upload flush (attachment ids preserved by the pre-existing COALESCE-by-omission); a pair whose group is now fully empty is identified and logged as a documented limitation, never silently mis-repaired.
expected: group_state rows for a deletion-affected (wr, week_ending) pair are confirmed repaired via the existing post-upload flush (attachment ids preserved by the pre-existing COALESCE-by-omission); a pair whose group is now fully empty is identified and logged as a documented limitation, never silently mis-repaired.
result: pass
source: automated
coverage_id: 11-06/D3

### 27. sheet_registry.column_mapping is refreshed only on the weekly_comprehensive execution type; a frequent run never silently adopts a drifted mapping for an already-registered sheet (D-02 trigger 2 escalates instead), while a genuinely new sheet still gets its first mapping written regardless of execution type.
expected: sheet_registry.column_mapping is refreshed only on the weekly_comprehensive execution type; a frequent run never silently adopts a drifted mapping for an already-registered sheet (D-02 trigger 2 escalates instead), while a genuinely new sheet still gets its first mapping written regardless of execution type.
result: pass
source: automated
coverage_id: 11-06/D4

### 28. A formula-only change to a HASH_FIELDS-mapped column reconciles through the ordinary content-hash path (different compute_content_hash() value); a formula-only change to a field outside HASH_FIELDS produces the identical hash and no repair -- correct, not a miss. Fixture is derived from, and its provenance names, the MEM-04 cassettes rather than re-probing the Smartsheet API.
expected: A formula-only change to a HASH_FIELDS-mapped column reconciles through the ordinary content-hash path (different compute_content_hash() value); a formula-only change to a field outside HASH_FIELDS produces the identical hash and no repair -- correct, not a miss. Fixture is derived from, and its provenance names, the MEM-04 cassettes rather than re-probing the Smartsheet API.
result: pass
source: automated
coverage_id: 11-06/D5

### 29. get_parity_streak scans newest-first over run_ledger rows whose notes.execution_type is production_frequent: pass increments, fail resets to zero and stops the scan, skipped is excluded from the sequence (neither counts nor resets), and rows outside production_frequent are ignored.
expected: get_parity_streak scans newest-first over run_ledger rows whose notes.execution_type is production_frequent: pass increments, fail resets to zero and stops the scan, skipped is excluded from the sequence (neither counts nor resets), and rows outside production_frequent are ignored.
result: pass
source: automated
coverage_id: 11-07/D1

### 30. No dedicated streak counter column is added to pipeline_memory/schema.sql -- the streak is derived on demand so it cannot drift from the evidence.
expected: No dedicated streak counter column is added to pipeline_memory/schema.sql -- the streak is derived on demand so it cannot drift from the evidence.
result: pass
source: automated
coverage_id: 11-07/D2

### 31. A Supabase failure returns None, read by the caller as 'cannot confirm', never as a satisfied streak.
expected: A Supabase failure returns None, read by the caller as 'cannot confirm', never as a satisfied streak.
result: pass
source: automated
coverage_id: 11-07/D3

### 32. Task 3 removes exactly six cache steps and nothing else; the schedule, timeout-minutes: 180, TIME_BUDGET_MINUTES, and the advanced_options parser all survive.
expected: Task 3 removes exactly six cache steps and nothing else; the schedule, timeout-minutes: 180, TIME_BUDGET_MINUTES, and the advanced_options parser all survive.
result: pass
source: automated
coverage_id: 11-08/T-11-38

### 33. TIME_BUDGET_MINUTES stays 165 and timeout-minutes stays 180 across both tasks.
expected: TIME_BUDGET_MINUTES stays 165 and timeout-minutes stays 180 across both tasks.
result: pass
source: automated
coverage_id: 11-08/T-11-39

### 34. Operator escalation flags still force full regeneration against group_state.
expected: Operator escalation flags still force full regeneration against group_state.
result: pass
source: automated
coverage_id: 11-08/T-11-40

### 35. Attachment identity is not lost with the pre-fetch cache -- group_state supplies it, with the existing per-row fallback intact (Task 2, this plan).
expected: Attachment identity is not lost with the pre-fetch cache -- group_state supplies it, with the existing per-row fallback intact (Task 2, this plan).
result: pass
source: automated
coverage_id: 11-08/T-11-41

### 36. No secrets or row-level billing data in the Living Ledger entry.
expected: No secrets or row-level billing data in the Living Ledger entry.
result: pass
source: automated
coverage_id: 11-08/T-11-44

## Summary

total: 36
passed: 36
issues: 0
pending: 0
skipped: 0
blocked: 0

## Notes

- Commit-claim reconciliation: all 8 SUMMARYs are pre-#3968 legacy (no commits:/plan_head_before: fields) — WARNING only, not a mismatch.
- Coverage errors: 11-08-SUMMARY.md T-11-43 has an invalid verification kind (malformed_block); treated as a human checkpoint (test 5), never dropped.
- Automated UI verification: ui_phase_active=true but no UI-SPEC.md, workflow.live_dom_uat=false, Python pipeline phase — 0 UI checkpoints.
- Cold-start smoke test: no startup/migration paths in SUMMARY files — not injected.

- Observation (not a test-2 defect): two recent fail verdicts (runs 34648318434.1, 34541106039.1) are group-side `actual_not_in_candidate` — the incremental candidate set missed USER-variant groups the full run produced. This is the shadow doing its job while INC-02 stays off; it resets the D-05 clean-run streak.

## Gaps

[none yet]
