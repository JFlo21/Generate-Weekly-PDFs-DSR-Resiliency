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

## 2026-11-04 — Corrections file fail-closed gate (stacked on PR #447)
- **Scope**: 2 pipeline files + 1 test file (orchestration + reporting-corrections module), runbook/config docs
- **Atoms**: clean-code, secure-coding, test-quality
- **Result**: 0 critical, 0 warning, 3 suggestion (unreachable `_txn` branch kept as defence; off-run test documents the regression rather than the gate; synthetic problem_count=1 for unexpected errors)
- **Key findings**: Opus production-risk round fixed wording (failure-path run_ledger row is still written), `del path` before raise (Sentry captures locals), denylist→allowlist AST test, opt-in `vars.REPORTING_CORRECTIONS_REQUIRED` guard
- **Strengths**: error surface is class + count only, no chained cause; gate placement proven by AST allowlist and a behavioural main() test
