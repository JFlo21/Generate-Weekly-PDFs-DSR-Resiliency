---
phase: "02"
plan: "03"
subsystem: "generate_weekly_pdfs"
tags: ["remediation", "garbage-cleanup", "tdd", "D-06", "D-07", "D-08", "D-12", "D-14"]
dependency_graph:
  requires: ["02-02"]
  provides: ["claimer-remediation-mode"]
  affects: ["generate_weekly_pdfs.py", ".github/workflows/weekly-excel-generation.yml", "website/docs/reference/environment.md"]
tech_stack:
  added: []
  patterns: ["default-OFF-isolated-mode", "dry-run-first", "live-identity-exemption", "window-filter"]
key_files:
  created:
    - "tests/test_claimer_remediation.py"
  modified:
    - "generate_weekly_pdfs.py"
    - ".github/workflows/weekly-excel-generation.yml"
    - "website/docs/reference/environment.md"
decisions:
  - "D-06: REMEDIATE_CLAIMERS default OFF — never fires on cron; isolated dispatch returns before Excel generation"
  - "D-07: _GARBAGE_PATTERNS = ('_NO_MATCH', '_Unknown_Foreman'); build_group_identity parses each filename; unparseable files skipped"
  - "D-08: REMEDIATION_DRY_RUN default ON; REMEDIATION_WINDOW_WEEKS default 26 weeks"
  - "D-12: valid_wr_weeks=None accepted (isolation path); live-identity exemption when set populated"
  - "D-14: build_group_identity() reused for filename parsing (battle-hardened, not new regex)"
metrics:
  duration: "~35 minutes"
  completed: "2026-05-26"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 4
---

# Phase 02 Plan 03: Claimer Remediation Mode Summary

New default-OFF, dry-run-first isolated remediation mode that sweeps `*_NO_MATCH*` / `*_Unknown_Foreman*` garbage attachments from TARGET and PPP Smartsheet sheets within a configurable window (default 26 weeks), with live-identity exemption protecting correct files and isolated dispatch returning before any Excel generation.

## Objective

Add a `REMEDIATE_CLAIMERS`-gated isolated mode to `generate_weekly_pdfs.py` that sweeps garbage claimer attachments produced by the pre-Phase-2 `SUPABASE_HASH_STORE_AUTHORITATIVE=1` incident. The mode is default OFF (never fires on cron), dry-run-first (D-08), and isolated (returns immediately — no Excel generation in the same session, D-06). Three env vars are workflow-pinned to safe defaults.

## Tasks Completed

| Task | Type | Commit | Description |
|------|------|--------|-------------|
| 1 | TDD RED | 7104791 | Add failing test module with 9 tests covering all D-06/D-07/D-08/D-12/D-14 behaviors |
| 2 | TDD GREEN | a822e8a | Implement run_claimer_remediation() + env vars + banner + isolated dispatch in main() |
| 3 | auto | 10ae102 | Pin remediation flags default-OFF in workflow + document 3 env vars in environment.md |

## What Changed

### generate_weekly_pdfs.py

**Three new env vars** added after `SUPABASE_HASH_STORE_AUTHORITATIVE` block:
- `REMEDIATE_CLAIMERS` (default `'0'`): master OFF switch — never fires on scheduled cron
- `REMEDIATION_DRY_RUN` (default `'1'`): dry-run-first guard; first run reports counts only
- `REMEDIATION_WINDOW_WEEKS` (default `26`): safe-parsed int; `0` = unbounded sweep

**Banner logging** added for all 3 flags at startup (after the E-store banner lines).

**`_GARBAGE_PATTERNS` module constant** `('_NO_MATCH', '_Unknown_Foreman')` — the exact tokens `resolve_claimer` emits for unresolved historical rows.

**`run_claimer_remediation(client, dry_run, window_weeks, valid_wr_weeks=None)` implemented:**
- Sweeps `TARGET_SHEET_ID` and `SUBCONTRACTOR_PPP_SHEET_ID` (skips PPP when `= 0`)
- Calls `client.Sheets.get_sheet(sheet_id)` per sheet, `client.Attachments.list_row_attachments(sheet_id, row.id)` per row
- Step 1: `build_group_identity(name)` parses each attachment filename; `None` return → skip (unparseable)
- Step 2: window filter — converts MMDDYY week token to `datetime.date`, skips when older than cutoff
- Step 3: `_GARBAGE_PATTERNS` substring check — skip if no match
- Step 4: live-identity exemption — when `valid_wr_weeks` is not `None` and the parsed 4-tuple is in the set, skip (protects live files per [2026-05-19 23:45])
- Step 5: dry-run logs `🔍 [DRY-RUN] would delete...`; execute calls `client.Attachments.delete_attachment(sheet_id, att_id)`
- PII-safe aggregate summary at end: counts only (scanned/garbage/deleted/exempted/out_of_window)

**Isolated dispatch in `main()`** added immediately after `client.errors_as_exceptions(True)`:
```python
if REMEDIATE_CLAIMERS:
    run_claimer_remediation(client, dry_run=REMEDIATION_DRY_RUN,
                            window_weeks=REMEDIATION_WINDOW_WEEKS,
                            valid_wr_weeks=None)
    return
```

### .github/workflows/weekly-excel-generation.yml

Three pins added after `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'`:
```yaml
REMEDIATE_CLAIMERS: '0'
REMEDIATION_DRY_RUN: '1'
REMEDIATION_WINDOW_WEEKS: '26'
```

### website/docs/reference/environment.md

Three new sections added before `### AEP_BILLABLE_CUTOFF`:
- `REMEDIATE_CLAIMERS` — with full operator workflow (dry-run first, then execute, then restore to 0)
- `REMEDIATION_DRY_RUN` — safety gate description
- `REMEDIATION_WINDOW_WEEKS` — blast-radius guard description

### tests/test_claimer_remediation.py

New test module (9 tests across 8 classes):
- `TestDryRunNeverDeletes` — dry_run=True → zero `delete_attachment` calls
- `TestExecuteDeletesOnlyGarbage` — 2 methods: garbage deleted, real-claimer untouched; realistic names never match
- `TestLiveIdentityExemption` — populated `valid_wr_weeks` exempts a garbage-named file
- `TestIsolationPathValidWrWeeksNone` — `None` path: garbage deleted, real-claimer untouched
- `TestWindowFilter` — 40-week-old file skipped; 4-week-old deleted
- `TestBothSheetsSwepped` — TARGET and PPP both swept
- `TestUnparseableFilesIgnored` — non-WR filenames skipped even if they contain `_NO_MATCH`
- `TestPppDisabledOnlyTargetSwept` — PPP=0 → `get_sheet` called once

## Deviations from Plan

None — plan executed exactly as written. The `_identifier` pyright hint on the tuple unpack is benign (the full `_identity` tuple is used for exemption lookup). A MD032 markdown lint warning was auto-fixed (blank line before list in `REMEDIATE_CLAIMERS` section).

## TDD Gate Compliance

- RED gate: `test(02-03)` commit `7104791` — 8 failing tests (AttributeError: `run_claimer_remediation` not defined)
- GREEN gate: `feat(02-03)` commit `a822e8a` — 9/9 tests pass after implementation
- No REFACTOR gate needed (code was clean after GREEN)

## Known Stubs

None — the remediation sweep is fully implemented and end-to-end tested.

## Test Results

- **973 passed, 26 skipped, 69 subtests** after all three tasks
- Net change: +9 tests (9 new in `test_claimer_remediation.py`)
- Prior baseline after Plan 02-02: 964 passed, 26 skipped

## Self-Check: PASSED

- SUMMARY.md: FOUND at `.planning/phases/02-attribution-bulk-prefetch-historical-claimer-remediation/02-03-SUMMARY.md`
- Commit `7104791` (test RED): verified
- Commit `a822e8a` (feat GREEN): verified
- Commit `10ae102` (chore Task 3): verified
- Test suite: 973 passed, 26 skipped, 69 subtests, 0 failed
