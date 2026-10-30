# Review Log

## 2026-10-30 — PR #439 quarantine and regen debt
- **Scope**: 2 code files, pipeline orchestration and its tests
- **Atoms**: clean-code, test-quality
- **Result**: 0 critical, 0 warning, 1 suggestion
- **Key findings**: `main()` wiring test is source-text only (repo pattern; `main()` is not unit-callable)
- **Strengths**: `_quarantined_group_keys` reuses `derive_row_wr`, so the pre-scan and the loop share one WR derivation

## 2026-10-30 — PR #437 Sentry frames and notes row binding
- **Scope**: 3 pipeline files and 1 test file
- **Atoms**: clean-code, secure-coding, test-quality
- **Result**: 0 critical, 0 warning, 2 suggestion
- **Key findings**: `_scrub_sheet_drop_frame_vars` now does more than its name says; `sheet_row_processing` is redundant while notes are mapped, kept so scope-off frames stay scrubbed
- **Strengths**: the scrub keys on whether notes can be in frames, not on a list of event locations, and fails closed

## 2026-10-30 — PR #443 mobile navbar colours
- **Scope**: 1 CSS file, docs site only
- **Atoms**: clean-code
- **Result**: 0 critical, 0 warning, 0 suggestion after one fix round
- **Key findings**: contrast for a chip-backed link must be measured on the chip, not the bar: the first active colour read 4.98:1 on the bar and 3.98:1 on the chip
- **Strengths**: scoping the overrides to `.navbar` left the desktop doc sidebar unchanged
