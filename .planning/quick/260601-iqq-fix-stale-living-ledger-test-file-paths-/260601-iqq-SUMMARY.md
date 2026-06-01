---
phase: quick-260601-iqq
plan: "01"
subsystem: tests
tags: [test-fix, living-ledger, sub-project-e]
dependency_graph:
  requires: []
  provides: [green-pre-push-gate]
  affects: []
tech_stack:
  added: []
  patterns: []
key_files:
  modified:
    - tests/test_subcontractor_pricing.py
    - tests/test_subproject_e_hash_store.py
decisions:
  - "_read_ledger() now reads memory-bank/living-ledger.md (not CLAUDE.md) — matches the 2026-05-28 relocation"
  - "TestWorkflowPinned asserts SUPABASE_HASH_STORE_AUTHORITATIVE: '1' — E is active"
metrics:
  duration: "~3 minutes"
  completed: "2026-06-01"
  tasks_completed: 2
  files_changed: 2
---

# Phase quick-260601-iqq Plan 01: Fix Stale Living Ledger Test File Paths Summary

**One-liner:** Repointed two stale test fixtures — `_read_ledger()` to `memory-bank/living-ledger.md` and E-flag assertion to `'1'` — to restore 1020-test green suite.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Repoint TestPhase1GapClosureLedgerEntryPresent to relocated Living Ledger | eed82a1 | tests/test_subcontractor_pricing.py |
| 2 | Update stale E-flag assertion in TestWorkflowPinned | eed82a1 | tests/test_subproject_e_hash_store.py |

## Verification Results

Targeted check:
```
python -m pytest tests/test_subcontractor_pricing.py::TestPhase1GapClosureLedgerEntryPresent tests/test_subproject_e_hash_store.py::TestWorkflowPinned -q
8 passed, 12 subtests passed in 1.14s
```

Full suite:
```
python -m pytest tests/ -q
1020 passed, 29 skipped, 76 subtests passed in 6.67s
```

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — changes are mechanical path/string corrections in test code only; no production logic touched.

## Self-Check: PASSED

- tests/test_subcontractor_pricing.py: modified (contains `memory-bank/living-ledger.md`)
- tests/test_subproject_e_hash_store.py: modified (contains `test_authoritative_flag_pinned_on` asserting `'1'`)
- Commit eed82a1: exists
- Full suite: 1020 passed, 0 failures
