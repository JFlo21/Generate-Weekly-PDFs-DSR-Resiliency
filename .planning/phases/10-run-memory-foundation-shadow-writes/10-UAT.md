---
status: testing
phase: 10-run-memory-foundation-shadow-writes
source: [10-VERIFICATION.md]
started: 2026-08-25T20:05:00-05:00
updated: 2026-08-25T20:05:00-05:00
---

## Current Test

number: 1
name: SC4 byte-identical standard — accept canonicalized-content proof or require a maintenance-window rerun
expected: |
  Decision: either (a) the 10-06 evidence (100% canonicalized Excel-content equality across all 17
  overlapping identities; residual comparator diff mechanically explained by ~50 live Smartsheet
  row additions during the ~68-minute control→shadow gap) satisfies the ROADMAP's "byte-identical"
  wording, or (b) scripts/compare_control_run.py must exit 0 on a control/shadow pair captured in a
  low-activity window (or via a fetch-snapshot replay) before Phase 10 is closed.
awaiting: user response

## Tests

### 1. SC4 byte-identical standard — accept canonicalized-content proof or require a maintenance-window rerun
expected: Comparator exits 0 with zero content-hash mismatches and zero group-selection / run_summary drift — OR Juan accepts the canonicalized-content proof as satisfying SC4 given the live-data limitation (product/scope decision; not resolvable by more automated evidence within Phase 10's tooling).
result: [pending]

### 2. MEM-01 group_state attachment id/name after a real upload
expected: Run the pipeline once with RUN_MEMORY_WRITE_ENABLED=1 and SKIP_UPLOAD unset (a real, non-dry-run execution); pipeline_memory.group_state gains rows whose attachment_id / attachment_name match the Smartsheet attachment actually created, and a reduced_sub fan-out group yields two distinct rows (one per target sheet). Structurally untestable under SKIP_UPLOAD; deferred to the flag-flip PR's first real run or a dedicated mock-based integration test — Juan decides whether Phase 10 closes with this item carried to Phase 11.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
