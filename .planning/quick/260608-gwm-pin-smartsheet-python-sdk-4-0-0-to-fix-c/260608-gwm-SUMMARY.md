---
phase: quick-260608-gwm
plan: "01"
subsystem: python-billing-pipeline
tags: [hotfix, dependency-pin, smartsheet-sdk, ci-crash]
dependency_graph:
  requires: []
  provides: [stable-ci-smartsheet-sdk-resolution]
  affects: [requirements.txt, memory-bank/living-ledger.md]
tech_stack:
  added: []
  patterns: [upper-bound-pin-for-transport-critical-deps]
key_files:
  created: []
  modified:
    - requirements.txt
    - memory-bank/living-ledger.md
decisions:
  - "Pin smartsheet-python-sdk to >=3.1.0,<4.0.0; deliberate 4.x migration is a separate planned effort"
  - "Used pip --dry-run to confirm 3.7.2 resolves without mutating local environment"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase quick-260608-gwm Plan 01: Pin smartsheet-python-sdk <4.0.0 to fix CI import crash Summary

**One-liner:** Pinned `smartsheet-python-sdk>=3.1.0,<4.0.0` to block 4.0.0's breaking removal of `smartsheet.exceptions` that crashed CI at import on 2026-06-08.

## What Was Built

A single-line dependency pin in `requirements.txt` that prevents the GitHub Actions billing
workflow from auto-pulling `smartsheet-python-sdk 4.0.0`, which removed `smartsheet.exceptions`
(crashing `generate_weekly_pdfs.py` line 28 at import), `Folders.get_folder/list_folders`,
`Templates`, and changed pagination. Zero changes to billing logic, `ss_exc` usage, or the
retry re-export workaround. Fully reversible by deleting `,<4.0.0`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pin smartsheet-python-sdk to exclude 4.0.0 | d89769c | requirements.txt |
| 2 | Non-mutating dry-run + Living Ledger entry | 2626142 | memory-bank/living-ledger.md |

## Verification Results

- `python -m py_compile generate_weekly_pdfs.py` — PASSED (no change to logic)
- Spec check `>=3.1.0,<4.0.0` present in requirements.txt — PASSED
- `pip install --dry-run -r requirements.txt` — resolves `smartsheet-python-sdk 3.7.2`, not 4.0.0 — PASSED
- Living Ledger check (date `2026-06-08` + pin spec present) — PASSED

## Decisions Made

1. **Upper-bound pin, not exact pin** — `>=3.1.0,<4.0.0` (not `==3.7.2`) allows patch/minor
   3.x updates to flow through. The 4.x line is blocked until a deliberate migration.
2. **Non-mutating verification** — used `pip install --dry-run` so the local Python environment
   was not modified. The dry-run output confirmed `3.7.2` is the newest allowed release.
3. **Zero logic change** — `generate_weekly_pdfs.py`, `ss_exc` usage, and the retry re-export
   workaround are untouched. The fix is fully reversible.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — this change narrows the dependency surface (removes a breaking major from the resolution
set). No new network endpoints, auth paths, or schema changes introduced.

## Rollback Notes

Remove `,<4.0.0` from `requirements.txt` line 8 to re-open the ceiling. Impact: next
`pip install` could resolve 4.0.0+, which will crash line 28 again. Do not revert unless
a tested 4.x migration branch is ready.

## Self-Check: PASSED

- requirements.txt modified: confirmed (d89769c)
- memory-bank/living-ledger.md modified: confirmed (2626142)
- Both commits exist on branch `worktree-agent-a75095df648f5262f`
