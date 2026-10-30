---
phase: 15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot
plan: 04
subsystem: pipeline
tags: [foreman-notes, excel, openpyxl, colour-carry-over, golden-identity]
requires: [15-01, 15-02]
provides:
  - "pipeline/excel.py: pilot-only branches (column I notes, A:I day header, red TOTAL I, fit-to-width, column I width 50, carried fill/font colours)"
  - "tests/test_foreman_notes_excel.py: pilot content, merges, print setup, footer, formula injection, colours, all variants, golden identity"
affects: [15-05, 15-06, 15-07]
tech-stack:
  added: []
  patterns:
    - "single pilot flag computed once per workbook (_fn.is_pilot_group), captured by the write_day_block closure"
    - "all pilot behaviour in `if fn_pilot` branches; non-pilot statements untouched"
key-files:
  created:
    - tests/test_foreman_notes_excel.py
  modified:
    - pipeline/excel.py
key-decisions:
  - "Colour application is per-cell fail-closed: fill and font are both built before either is applied, so a malformed value leaves the whole cell plain (TypeError/ValueError only)"
  - "Non-dict STYLE_KEY values are treated as no style"
requirements-completed: [FN-05, FN-06, FN-07, FN-12]
status: complete
commits: 3
plan_head_before: f6307c31251702040ac57d1800cac0bd88e3a611
plan_head_after: 35c16afc41124b8a4ae45bd956dca8bdd7c5c078
metrics:
  duration: "~30m"
  completed: 2026-10-29
actuals:
  tokens: 14000
  tasks: 3
  commits: 3
---

# Phase 15 Plan 04: Pilot Excel rendering Summary

Pilot workbooks now render a wrapped `Foreman Notes` column I (text-typed, width 50), A:I day headers, a red TOTAL I cell, fit-to-width landscape printing and carried Smartsheet fill/font colours on the Smartsheet-sourced CU cells; switch-off and non-pilot workbooks remain cell-identical to the BASE golden for all ten variant families.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Tracer: pilot primary workbook, note in I, one coloured row | d10bcec |
| 2 | Layout details, injection safety, print setup, colour fail-closed | 9f62f9c |
| 3 | Every variant: pilot renders column I; off/non-pilot golden-identical | 35c16af |

Task 2 needed no further `pipeline/excel.py` change beyond Task 1; the whole implementation landed in commit d10bcec.

## Verification

- `pytest tests/test_foreman_notes_excel.py tests/test_foreman_notes_baseline.py -q` -> 19 passed, 84 subtests passed.
- Task 2 verify (`test_foreman_notes_excel.py`) -> 9 passed, 4 subtests passed.
- Task 3 verify (`-k variants`) -> 1 passed, 30 subtests passed (10 groups x off / non-pilot / pilot; group count asserted equal to fixture group count).
- Full suite: `pytest tests/ -q` -> 2729 passed, 3 skipped, 821 subtests passed, zero failures (15-02 baseline: 2690 passed).
- `python -m py_compile pipeline/excel.py` clean; `grep -c "ws.merge_cells(" pipeline/excel.py` = 1 (inside `safe_merge_cells`); `oddFooter` appears only in pre-existing docstring/comment lines.
- 6-gate harness deferred to 15-05 as planned.

## Deviations from Plan

- [Interpretation] The plan says "one `A:I` per day header". The FIRST day's header row (row 14 in the fixture) lies inside the summary merge `G14:I14`, so `safe_merge_cells` skips it today (`A14:H14` is absent from the BASE golden) and equally skips `A14:I14` now. Only later day headers get the `A:I` merge. The exact merged-range test encodes this real behaviour (diff vs golden is exactly `A21:H21` -> `A21:I21`). This overlap is pre-existing and was not altered.
- [Rule 2 - hardening] Colour application guards malformed style values (non-dict STYLE_KEY, non-tuple entries, invalid hex): the cell stays plain instead of failing the workbook.
- Test file was committed in three stages (tracer, layout, variants) to honour per-task commits.

## Known Stubs

None.

## Threat Flags

None. T-15-13 (text-typed notes with `=`, `+`, `-`, `@` prefixes), T-15-14 (illegal chars stripped, 32767 cap), T-15-15 (all merges via `safe_merge_cells`, exact merged list, footers empty) and T-15-16 (golden identity for every variant, off and non-pilot with notes and colours present) are covered by tests.

## Requirements

Marked Complete: FN-05, FN-06, FN-07, FN-12 (layout, print setup, colour carry rendering, every variant via the single `generate_excel`). FN-01 was completed in 15-02; this plan only proves the switch-off workbook identity.

## Self-Check: PASSED

- pipeline/excel.py, tests/test_foreman_notes_excel.py: FOUND
- Commits d10bcec, 9f62f9c, 35c16af: ancestors of HEAD
