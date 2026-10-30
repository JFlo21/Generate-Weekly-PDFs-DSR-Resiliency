---
phase: 15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot
plan: 05
subsystem: pipeline
tags: [foreman-notes, orchestrate, dry-run-guard, seams, pipeline-memory]
requires: [15-02, 15-03, 15-04]
provides:
  - "pipeline/orchestrate.py: _fn.initialize(client) before PHASE 1; _fn.build_sheet_column_maps after discovery; _fn.attach_group_styles immediately before generate_excel"
  - "memory_write_blocked(kind) guard inside the existing gate of every pipeline_memory / hash-store / billing-audit-hash write site"
  - "tests/test_foreman_notes_pipeline.py: tracer, seam-order AST, zero-impact, write-guard drift, guard behaviour, synthetic-run tests"
affects: [15-06, 15-07]
tech-stack:
  added: []
  patterns:
    - "guard inner, gate outer: the existing write-gate conditions are untouched; the guard is evaluated (and may log) only when the write would have run"
key-files:
  created:
    - tests/test_foreman_notes_pipeline.py
  modified:
    - pipeline/orchestrate.py
    - pipeline/foreman_notes.py
key-decisions:
  - "memory_writes_possible() now also reads AUDIT_MEMORY_ENABLED: the audit-findings upsert is gated on that flag alone and is NOT TEST_MODE-gated, so a dry run with it on could persist state; such a run now resolves to effective scope off (fail-safe)"
  - "Helpers without their own gate (_note_pending_regen_pairs, _reconcile_deep_run_deletions) carry a function-entry guard; their single call sites in main() are inside the existing gates and a test asserts that"
  - "client and source_sheets are plain main() locals in the group loop; no threading was needed"
requirements-completed: [FN-03, FN-11, FN-12, FN-01]
status: complete
commits: 3
plan_head_before: 70d183e6f5c2b0a175d40ca4c7c71399236ac166
plan_head_after: 7cb119079c683e87d7456fe80dc04b8bb55b28d1
metrics:
  duration: "~50m"
  completed: 2026-10-29
actuals:
  tokens: 26000
  tasks: 3
  commits: 3
---

# Phase 15 Plan 05: Pipeline wiring Summary

The GF pilot set is now read once per run right after the Smartsheet client is created (before PHASE 1 and every memory write), pilot groups get their Smartsheet colours attached just before `generate_excel`, and a code-level guard plus AST drift test stops a dry-run pilot from persisting pilot-flavoured state; production (scope off) makes no new call and produces identical output.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Tracer: run-start GF load and pre-render style attach on fakes | 48c7016 |
| 2 | Dry-run persistence guard, seam-order and zero-impact guards | 2de9332 |
| 3 | Synthetic run check (+ full suite and 6 gates) | 7cb1190 |

## Seams (orchestrate.py)

- `_fn.initialize(client)`: after `client.errors_as_exceptions(True)` and the REMEDIATE_CLAIMERS early return, before the Sentry session transaction and the `PHASE 1` log.
- `_fn_sheet_maps = _fn.build_sheet_column_maps(source_sheets)`: right after the "No valid source sheets" check.
- `_fn.attach_group_styles(client, group_rows, _fn_sheet_maps)`: directly before the `with ... Generate Excel` block, after the hash and every skip decision. `_upload_one`, `_run_synthetic_test_mode`, `create_target_sheet_map_with_quarantine` and `.github/workflows/*` are untouched (diff vs BASE_SHA confirmed). No `run_summary.json` key, span data or log carries notes/GF names.

## Write-site inventory (15 raw write references; drift test pins the count at 15)

| # | Call site | Kind | Existing gate (unchanged) |
|---|-----------|------|---------------------------|
| 1 | `_run_memory_write_phase` -> `upsert_rows_bulk_result` (called from main and `_run_phase2_incremental`) | row_state | function-entry `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE` early return; guard follows it |
| 2 | main `run_ledger_start` (start hook) | run_ledger | `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE` |
| 3 | main `upsert_sheet_registry` pass 1 | sheet_registry | same |
| 4 | main `run_ledger_start` retry before pending note | run_ledger | same |
| 5 | `_note_pending_regen_pairs` -> `run_ledger_note_pending` | run_ledger | caller gate `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE`; function-entry guard |
| 6 | main `upsert_sheet_registry` pass 2 | sheet_registry | `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE` |
| 7 | `_reconcile_deep_run_deletions` -> `mark_rows_deleted_fn(...)` | row_state | caller gate `_is_deep_run and full and RUN_MEMORY_WRITE_ENABLED and not TEST_MODE`; function-entry guard |
| 8 | main `emit_run_fingerprint` | billing_audit_hash | `BILLING_AUDIT_AVAILABLE and not TEST_MODE and any_flag_enabled()` |
| 9, 10 | main durable hash flush `upsert_group_hash` x2 (withheld + advance) | hash_store | `SUPABASE_HASH_STORE_WRITE_ENABLED and _deferred_hash_upserts` (deferral also `not TEST_MODE`) |
| 11, 12 | main group_state flush `bump_group_state_withheld` + `upsert_group_state` | group_state | `RUN_MEMORY_WRITE_ENABLED and _deferred_group_state` (deferral also `not TEST_MODE`) |
| 13 | main `run_ledger_finish` (success) | run_ledger | `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE` |
| 14 | main `run_ledger_finish` (failure path) | run_ledger | `_session_failed and RUN_MEMORY_WRITE_ENABLED and not TEST_MODE` |
| 15 | `_run_audit_memory_phase` -> `upsert_audit_findings` | audit_findings (new kind) | `AUDIT_MEMORY_ENABLED and audit_results` (NOT TEST_MODE-gated); guard follows the gate |

Not guarded, by inspection: `billing_audit` `freeze_row` and `snapshot_drift` provenance/event writes. They are Supabase writes through the `billing_audit` client, which returns no client under TEST_MODE (`_is_test_mode`), and neither carries notes/colour/pilot data or a content hash. Read paths (`lookup_group_hash`, `_mem_reader.*`, `fetch_snapshot_provenance`) are unaffected.

## Verification

- Task 1 verify: `pytest tests/test_foreman_notes_pipeline.py -q` -> 1 passed.
- Task 2 verify: same file -> 17 passed. Full suite at that point 2746 passed, 3 skipped, 821 subtests.
- Task 3 verify: same file -> 18 passed (synthetic-run test ~1s; leaves no files in `generated_docs/`; `git status --porcelain generated_docs/` empty).
- Full suite: `pytest tests/ -q` -> **2747 passed, 3 skipped, 821 subtests passed, 0 failed** (15-04 baseline 2729; +18 tests). `tests/test_audit_findings.py` collected without error in this environment (no pre-existing collection ImportError observed).
- 6-gate harness (`bash scripts/run_6_gates.sh`): Gate 1 (AST import equality) PASS, Gate 2 (facade completeness) PASS, Gate 3 (pytest) PASS, **Gate 4 (mypy delta) FAIL: "mypy error lines increased (70 -> 74)"**, which aborts the script under `set -e`. Gates 5 and 6 run manually afterwards: Gate 5 `py_compile` PASS; Gate 6 synthetic run exit 0 and `check_run_summary_structure.py` "PASS: run_summary.json structure matches baseline (30 keys)".
- Gate 4 is PRE-EXISTING and not caused by this plan: the same mypy command yields 74 lines at 70d183e (before 15-05) and 74 at HEAD (delta 0 from this plan); at the 15-BASE_SHA it yields 73. The frozen `tests/golden/mypy_baseline_count.txt` (70) is stale against unrelated files (audit_billing_changes.py, pipeline_memory/audit_findings.py, billing_audit/*). Left unfixed (out of scope); see Deferred Issues.
- Acceptance greps: `_fn.initialize(` count 1, `_fn.attach_group_styles(` count 1; workflows diff vs BASE_SHA empty; no `_upload_one` / `_run_synthetic_test_mode` lines in the orchestrate diff.
- Seam-order tests would fail if `_fn.initialize(` moved after the PHASE 1 literal / `discover_source_sheets` / any `_run_memory_write_phase` or `_run_phase2_incremental` call (asserted by line number from the AST), or into the REMEDIATE_CLAIMERS branch; they would fail if anything but `generate_excel` followed the attach statement or a second `calculate_data_hash` appeared in main. No broken order was committed.
- Drift test mutation reasoning: removing a guard leaves no `memory_write_blocked` ancestor or function-level early return -> "unguarded write site"; moving a guard outside its gate removes the gate ancestor -> "guard not nested inside an existing gate"; a new write reference changes the count of 15.

## Deviations from Plan

- [Rule 2 - missing critical functionality] The inventory found `AUDIT_MEMORY_ENABLED` (audit-findings upsert) as a pipeline_memory write gated only on its own flag, not TEST_MODE. Added it to `memory_writes_possible()` (so a dry run with it on resolves to scope off) and added an `audit_findings` guard kind inside its gate. Test: `test_memory_writes_possible_covers_audit_memory_flag`.
- [Interpretation] Guards that cannot be wrapped lexically (helpers with no own gate) use a function-entry early return plus a test that every call site sits inside a gate, instead of wrapping each call.
- [Interpretation] Since every existing write gate already includes `not TEST_MODE` (or a TEST_MODE-gated deferral), the guards are defence in depth: in a real dry run they are never evaluated, which is what "zero guard ERRORs" asserts. Behaviour tests open the gate artificially to prove the guard blocks and logs once per kind.
- The plan's "slow marker" has no suite convention; the synthetic-run test (about 1 s) runs in the normal suite.

## Known Stubs

None.

## Deferred Issues

- Gate 4 mypy baseline (`tests/golden/mypy_baseline_count.txt` = 70) is stale versus the repo (73 at BASE, 74 now) so `scripts/run_6_gates.sh` exits at Gate 4. Needs a deliberate baseline refresh by the owner; not changed here.

## Threat Flags

None. The seams call read-only functions; `_upload_one` is unchanged (T-15-21); no span/summary/log carries notes or GF names (T-15-19).

## Requirements

Marked Complete: FN-03 (GF map read once, drives the whole run), FN-11 (effective scope off in production and synthetic run; dry-run write guard), FN-12 (pilot path wired through the single `generate_excel`), FN-01 (zero-call, byte-identical production path now proven through the real seams).

## Self-Check: PASSED

- tests/test_foreman_notes_pipeline.py, pipeline/orchestrate.py, pipeline/foreman_notes.py: FOUND
- Commits 48c7016, 2de9332, 7cb1190: ancestors of HEAD
