---
status: testing
phase: subproject-b + helper-exclusion-hotfix (no GSD phase — superpowers plan)
source:
  - docs/superpowers/plans/2026-05-20-subproject-b-subcontractor-primary-claim-attribution.md
  - PR #216 (helper-completed exclusion hotfix, merged to master)
started: 2026-05-21
updated: 2026-05-21
---

## Current Test

number: 2
name: Subcontractor PRIMARY files partitioned by frozen claimer
status: blocked — requires a run of the Subproject B branch (PR #215)
note: |
  Test 1 PASSED in production (operator-confirmed 2026-05-21). Tests 2-4
  validate the _ReducedSub_User_<name> / _AEPBillable_User_<name>
  partitioning, which exists ONLY on the B branch (PR #215), not on master.
  They need the B branch to actually run and generate files first — i.e.
  merge PR #215 and wait for the next cron run, or run the branch in a
  local/test env.

## Tests

### 1. Helper-completed rows excluded from subcontractor PRIMARY files
scope: master / production (hotfix #216 is merged; runs on the 2h cron)
expected: |
  A helper-completed line item appears only in the _ReducedSub_Helper_<helper>
  / _AEPBillable_Helper_<helper> file, NOT in the primary _ReducedSub /
  _AEPBillable file. Primary totals exclude it. (This is the production bug
  you reported, now fixed on master.)
result: pass  # operator-confirmed in production 2026-05-21

### 2. Subcontractor PRIMARY files partitioned by frozen claimer
scope: Subproject B branch (PR #215, NOT yet on master)
expected: |
  Subcontractor primary files are named _ReducedSub_User_<foreman> /
  _AEPBillable_User_<foreman> (one file per claiming foreman) and each
  contains only that foreman's claimed (non-helper) line items.
result: pending

### 3. Two claimers on the same WR+week coexist
scope: Subproject B branch (PR #215)
expected: |
  If two foremen each claimed line items on the same WR + week, TWO separate
  primary files appear (one per foreman); neither overwrites/deletes the other.
result: pending

### 4. Helper-completed rows excluded from the _User_ primary files too
scope: Subproject B branch (PR #215)
expected: |
  Same exclusion as Test 1 but on the B branch: helper-completed rows do NOT
  appear in any _ReducedSub_User_* / _AEPBillable_User_* primary file — only
  in the _ReducedSub_Helper_* / _AEPBillable_Helper_* shadow files.
result: pending

## Summary

total: 4
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 3  # Tests 2-4 need the B branch (PR #215) to run and generate files

## Gaps

<!-- populated if a test reports an issue -->
