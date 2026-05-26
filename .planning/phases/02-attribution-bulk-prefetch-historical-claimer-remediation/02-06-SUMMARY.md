---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
plan: 06
subsystem: api
tags: [remediation, workflow, documentation, safety, billing]

# Dependency graph
requires:
  - phase: 02-attribution-bulk-prefetch-historical-claimer-remediation (Plan 05)
    provides: rpc_missing/ATTRIBUTION_BULK_PREFETCH_FALLBACK; WR-01/WR-03/WR-05/IN-01 closed
provides:
  - WR-02: remediation reachable via advanced_options parser (literal pins removed)
  - WR-04: isolated EXECUTE sweep restricted to _ALWAYS_GARBAGE_PATTERNS (_NO_MATCH only)
  - IN-02: out_of_window counts only garbage files (garbage check reordered before window filter)
  - IN-03: operations.md dry-run quote aligned to real summary-line format
  - IN-04: shadowing local import datetime as _dt removed from run_claimer_remediation
  - Living Ledger entry for full Phase 2 gap-closure round (AUTONOMOUS CLOUD MEMORY rule)
affects: [remediation-activation, blast-radius-observability, docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "advanced_options parser extension: rarely-used destructive controls go through key:value parser, never new top-level inputs"
    - "Always-garbage vs context-garbage pattern sets: _ALWAYS_GARBAGE_PATTERNS for isolated sweep path, _GARBAGE_PATTERNS for exemption-protected path"
    - "IN-02 reorder: garbage check before window filter so scope counter is unambiguous"

key-files:
  created: []
  modified:
    - .github/workflows/weekly-excel-generation.yml
    - website/docs/runbook/operations.md
    - website/docs/reference/environment.md
    - generate_weekly_pdfs.py
    - tests/test_claimer_remediation.py
    - CLAUDE.md

key-decisions:
  - "Delete literal REMEDIATE_CLAIMERS/REMEDIATION_DRY_RUN/REMEDIATION_WINDOW_WEEKS step-env pins (they masked $GITHUB_ENV); Python module defaults supply safe values for cron runs"
  - "_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',) only — _Unknown_Foreman preserved in isolated path because it is a legitimate current sentinel with no live-identity exemption to protect it"
  - "Garbage check runs BEFORE window filter so out_of_window counts only garbage files (IN-02 reorder — not a rename)"
  - "Reconcile TestExecuteDeletesOnlyGarbage + TestBothSheetsSwepped to non-isolated path (valid_wr_weeks=set()) to preserve the both-tokens-eligible contract"

requirements-completed: [SPEC-4, SPEC-5, SPEC-6]

# Metrics
duration: ~60min
completed: 2026-05-26
---

# Phase 02 Plan 06: Remediation Mode Safety + Activation + Ledger Summary

**Isolated EXECUTE sweep now deletes only the always-garbage `_NO_MATCH` token (preserving valid `_Unknown_Foreman` files); remediation is operator-reachable via the `advanced_options` parser; `out_of_window` counts only garbage; runbook quote aligned; shadowing datetime alias removed; date-stamped Living Ledger entry committed.**

## Performance

- **Duration:** ~60 min
- **Started:** 2026-05-26T22:00Z (first task commit)
- **Completed:** 2026-05-26T23:45Z
- **Tasks:** 4 (1 workflow/docs, 1 TDD fix, 1 doc alignment, 1 ledger + suite gate)
- **Files modified:** 6

## Accomplishments

- **WR-02:** Three new `case` branches in the `advanced_options` parser (`remediate_claimers`, `remediation_dry_run`, `remediation_window_weeks`) export to `$GITHUB_ENV`. The three literal step-`env:` pins that silently masked the parser were removed. Python module defaults (OFF/dry-run/26wk) supply safe cron-run values. The real activation path is now documented in operations.md and environment.md.
- **WR-04:** Added `_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',)`. `run_claimer_remediation` selects the active pattern set based on `valid_wr_weeks is not None`. The isolated path (`valid_wr_weeks=None`) now only deletes `_NO_MATCH` (a pure Smartsheet `#NO MATCH` error token); `_Unknown_Foreman` is preserved as a legitimate current sentinel. The non-isolated path is unchanged (both tokens eligible, live-identity exemption active).
- **IN-02:** Reordered the per-attachment loop so the garbage-pattern check runs before the window filter. `out_of_window` now counts only garbage files too old to sweep — unambiguous blast-radius metric in the summary line.
- **IN-03:** Rewrote operations.md Step 4 to quote the real summary-line format (`✅ run_claimer_remediation [DRY-RUN] complete: scanned=N garbage=N deleted=0 exempted=N out_of_window=N`) and the per-attachment grep pattern. Removed the misleading dedicated-input YAML snippets.
- **IN-04:** Removed the shadowing `import datetime as _dt` from inside `run_claimer_remediation`; all three references changed to the module-level `datetime.*`.
- **Living Ledger:** Date-stamped `[2026-05-26 22:45]` entry summarizing all 10 Phase 2 gap-closure findings (Plans 02-05 + 02-06) committed to CLAUDE.md per the AUTONOMOUS CLOUD MEMORY INJECTION rule.
- **Full suite:** 986 passed / 29 skipped / 69 subtests (strictly > 981 baseline from Plan 02-05).

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | WR-02 advanced_options parser + docs | `d97514b` | weekly-excel-generation.yml, operations.md, environment.md |
| 2 | WR-04/IN-02/IN-04 code fixes + TDD | `2edacc8` | generate_weekly_pdfs.py, tests/test_claimer_remediation.py |
| 3 | IN-03 doc alignment | (included in Task 1 commit — operations.md was rewritten in one pass covering both WR-02 and IN-03) | — |
| 4 | Living Ledger + full-suite gate | `1f4669f` | CLAUDE.md |

## Files Created/Modified

- `.github/workflows/weekly-excel-generation.yml` — three new `advanced_options` case branches; three literal env pins removed; `advanced_options` input description updated.
- `website/docs/runbook/operations.md` — Step 4 rewritten: real `advanced_options` activation syntax; real dry-run summary-line quote; per-attachment grep pattern.
- `website/docs/reference/environment.md` — REMEDIATE_CLAIMERS / REMEDIATION_DRY_RUN / REMEDIATION_WINDOW_WEEKS sections updated to reference `advanced_options`.
- `generate_weekly_pdfs.py` — `_ALWAYS_GARBAGE_PATTERNS` constant added; `run_claimer_remediation` selects pattern set by path; garbage check reordered before window filter (IN-02); local `import datetime as _dt` removed (IN-04).
- `tests/test_claimer_remediation.py` — `TestIsolatedPathUnknownForemanProtection` (3 new tests: deletes NO_MATCH, preserves Unknown_Foreman, non-isolated path both eligible); `TestOutOfWindowCountsOnlyGarbage` (2 new tests: clean file does not inflate counter, garbage file does increment counter); `TestExecuteDeletesOnlyGarbage` and `TestBothSheetsSwepped` reconciled to post-WR-04 non-isolated contract.
- `CLAUDE.md` — Living Ledger entry `[2026-05-26 22:45]` appended.

## Decisions Made

- **Delete literal pins, not replace with ${{ ... }}:** The remediation vars have no dedicated `workflow_dispatch` input (10-input limit), so the `${{ github.event.inputs.X || default }}` pattern doesn't apply. Deleting the pins and relying on Python module defaults is the cleanest approach — mirrors how `MAX_GROUPS`/`REGEN_WEEKS`/`RESET_WR_LIST` work (no step-env literal, parser-only).
- **Reorder garbage-before-window (not rename):** A label-only rename of `out_of_window` would still mis-count clean out-of-window files. The reorder is the correct fix for IN-02 — the counter now means what operators expect.
- **Reconcile (not weaken) existing tests:** `TestExecuteDeletesOnlyGarbage` and `TestBothSheetsSwepped` both passed `valid_wr_weeks=None` (isolated path) and expected `_Unknown_Foreman` to be deleted. Post-WR-04 that is wrong. Reconciled to `valid_wr_weeks=set()` (non-isolated, no exemptions) — preserves the "both tokens eligible in non-isolated path" contract exactly; the isolated-path contract is covered by the new `TestIsolatedPathUnknownForemanProtection` class.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test-contract reconciliation] Reconciled TestExecuteDeletesOnlyGarbage and TestBothSheetsSwepped to post-WR-04 contract**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Both existing tests passed `valid_wr_weeks=None` (isolated path) and asserted `_Unknown_Foreman` IS deleted — exactly the behavior WR-04 reverses.
- **Fix:** Changed both to `valid_wr_weeks=set()` (non-isolated path, no exemptions active) so both garbage tokens remain eligible there. The isolated-path behaviour is covered by the new `TestIsolatedPathUnknownForemanProtection` test class. Per the [2026-05-20 00:26] rule 2: reconciled in-place with docstring citing the plan.
- **Files modified:** tests/test_claimer_remediation.py
- **Committed in:** `2edacc8`

**2. [Rule 1 - Test fixture] Fixed test_out_of_window_counts_garbage_older_than_window double-count**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** `_BaseRemediationTest` patches both TARGET and PPP sheet IDs; when both sheets return the same mock attachment, `out_of_window=2` not `1`. The test expected `1`.
- **Fix:** Added `mock.patch('generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID', 0)` in that test to disable PPP, giving exactly one attachment scanned — `out_of_window=1` as expected.
- **Files modified:** tests/test_claimer_remediation.py
- **Committed in:** `2edacc8`

**3. [Rule 1 - Doc task merged into Task 1] IN-03 doc changes included in Task 1 commit**
- **Found during:** Task 1 execution
- **Issue:** The plan specified Task 3 as a separate commit for the operations.md dry-run quote fix, but the quote change was part of the same Step 4 rewrite that Task 1 required (WR-02 activation syntax). Doing them separately would require two edits to the same paragraph.
- **Fix:** Applied both WR-02 and IN-03 doc changes in one coherent Step 4 rewrite in Task 1 commit `d97514b`. No separate Task 3 commit needed (no further doc change was required).

---

**Total deviations:** 3 auto-fixed (2 test-contract reconciliations, 1 doc-task merge)
**Impact on plan:** All plan must-haves satisfied; no scope creep; additive/surgical constraint held.

## Known Stubs

None — all plan deliverables are fully wired.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes were introduced. The changes are:
- Workflow YAML: parser extension (no new secrets or endpoints)
- Python: pattern-set selection + loop reorder (no new I/O)
- Docs: content updates only

No new threat flags.

## Self-Check: PASSED

**Files present:**
- `.github/workflows/weekly-excel-generation.yml` — contains `remediate_claimers)` case branch
- `generate_weekly_pdfs.py` — contains `_ALWAYS_GARBAGE_PATTERNS`; no `import datetime as _dt`
- `tests/test_claimer_remediation.py` — 14 tests passing
- `website/docs/runbook/operations.md` — contains `run_claimer_remediation [DRY-RUN] complete`
- `CLAUDE.md` — contains `[2026-05-26 22:45]` Living Ledger entry

**Commits present:** `d97514b`, `2edacc8`, `1f4669f` — verified via git log

**Suite:** 986 passed / 29 skipped / 69 subtests (strictly > 981 baseline)

---
*Phase: 02-attribution-bulk-prefetch-historical-claimer-remediation*
*Completed: 2026-05-26*
