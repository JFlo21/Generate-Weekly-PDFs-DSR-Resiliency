---
phase: 15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot
plan: 02
subsystem: pipeline
tags: [foreman-notes, pilot-scope, smartsheet-format, change-detection-inputs]
requires: [15-01]
provides:
  - "pipeline/foreman_notes.py: effective scope, immutable run state, GF map, pilot predicates, note normaliser, palette + descriptor parser, lazy style enrichment, notes digests, globals component, mapping marker helpers"
  - "FOREMAN_NOTES_SCOPE / _PILOT_GFS / _UPLOAD / _GF_WR_COLUMN_ID / _GF_COLUMN_ID in pipeline/config.py"
affects: [15-03, 15-04, 15-05, 15-06, 15-07]
tech-stack:
  added: []
  patterns:
    - "owning module with pure/never-raising functions; later plans add one-line pilot-gated seams"
    - "fail-closed everywhere: invalid scope, empty allowlist, GF read error, bad descriptor -> today's behaviour"
key-files:
  created:
    - pipeline/foreman_notes.py
    - tests/test_foreman_notes_state.py
    - tests/test_foreman_notes_styles.py
    - tests/test_foreman_notes_digest.py
  modified:
    - pipeline/config.py
key-decisions:
  - "Descriptor parser rejects ANY non-numeric part (not only slots 8/9), so a garbage short string fails the whole cell closed instead of falling through to a lower-precedence colour"
  - "norm_note exact rule (remove illegal chars, then strip, then cap) keeps inner spaces: '  hi \\x01there ' -> 'hi there' (the plan's 'hithere' example contradicts its own 'exact' rule)"
  - "reset_state() also clears the style cache and the memory_write_blocked dedupe set"
requirements-completed: [FN-01, FN-02, FN-03]
requirements-partial: [FN-07, FN-10, FN-11]
status: complete
commits: 3
plan_head_before: 5c175ba388238fda276bf1ff86c3298cd37bafdd
plan_head_after: c307ace0b85fc34343c3ca0165f595986f07bb03
metrics:
  duration: "~35m"
  completed: 2026-10-29
actuals:
  tokens: 28000
  tasks: 3
  commits: 3
---

# Phase 15 Plan 02: foreman_notes owning module Summary

`pipeline/foreman_notes.py` now holds all Phase 15 logic (effective scope that keeps production at `off`, allowlist-gated GF pilot WR set, probed colour precedence with whole-cell fail-closed, lazy pilot-only style fetch, single note normaliser and permutation-invariant digests); only `pipeline/config.py` changed among existing files.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Tracer: config flags, effective scope, GF map, pilot predicate | 4f43482 |
| 2 | Palette, descriptor precedence, lazy pilot-only style enrichment | 3f7d757 |
| 3 | Notes normaliser, digests, globals component | c307ace |

## Verification

- Task 1 verify: `pytest tests/test_foreman_notes_state.py tests/test_foreman_notes_baseline.py -q` -> 39 passed, 50 subtests passed.
- Task 2 verify: styles + state + baseline -> 67 passed, 2 skipped (live probe and palette drift, opt-in), 60 subtests passed.
- Task 3 verify: digest + styles + state + baseline -> 84 passed, 2 skipped, 60 subtests passed.
- Full suite before plan: 2615 passed, 1 skipped, 714 subtests passed.
- Full suite after plan: 2690 passed, 3 skipped, 724 subtests passed (+75 tests, +2 opt-in skips, zero new failures).
- Import-resolved effective scope (subprocess tests): default `off`; `SKIP_UPLOAD=true` `off`; `TEST_MODE=true` `off`; `TEST_MODE=true` with both write flags 0 `pilot`.
- AST import-rule check passes; `FOREMAN_NOTES_PILOT_GFS` getenv default is `''`; `py_compile` of config, foreman_notes and the facade is clean; module source contains none of `update_rows`, `add_rows`, `attach_file`, `delete_`.
- Golden baseline test still green.

## Deviations from Plan

- [Interpretation] `norm_note('  hi \x01there ')` returns `'hi there'`, not the plan's literal `'hithere'`; implemented the explicit rule (illegal chars removed, then strip). Test asserts the rule.
- [Rule 2 - hardening] `parse_descriptor` validates every part as empty-or-digits, so e.g. `'garbage'` is unparseable rather than silently "valid with no colour".
- `attach_group_styles` returns the count of group rows carrying a style (plan left the meaning of the int open).

## Known Stubs

None. Live tests are opt-in by design (`FN_LIVE_PROBE=1` with a token, `FN_PALETTE_LIVE=1`); they were NOT run here (no token in this environment), so research assumption A4 (row_ids form returns `conditional_format`) remains unverified live.

## Threat Flags

None. The module is read-only (`get_sheet` only) and logs counts and exception type names only.

## Requirements

Marked Complete: FN-01, FN-02, FN-03 (scope switch, allowlist, GF resolution fully delivered by the module). FN-07, FN-10 and FN-11 have their logic here (precedence parser, notes-only digests, effective scope + write guard) but stay Pending until the Excel, hash and pipeline_memory seams land in later plans.

## Notes for later plans

- `memory_writes_possible()` currently covers `SUPABASE_HASH_STORE_WRITE_ENABLED` and `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE`; 15-05 Task 2's call-site inventory must extend it if another write flag exists.
- `EFFECTIVE_SCOPE` is computed at import; `initialize(client)` reads it at call time.

## Self-Check: PASSED

- pipeline/foreman_notes.py, tests/test_foreman_notes_{state,styles,digest}.py: FOUND
- Commits 4f43482, 3f7d757, c307ace: ancestors of HEAD
