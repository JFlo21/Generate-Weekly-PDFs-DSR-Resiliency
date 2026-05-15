---
phase: 01-subcontractor-rate-logic-modification
plan: 10
subsystem: python-billing-engine
tags: [python, gap-closure, code-review, env-var-coercion, ppp-sheet, defensive-raise, helper-shadow, docs-runbook]
requires: [01-09]
provides: [REVIEW-WR-02-closed, REVIEW-WR-03-closed]
affects: [generate_weekly_pdfs.py, website/docs/reference/environment.md, tests/test_subcontractor_pricing.py]
tech-stack:
  added: []
  patterns:
    - "Asymmetric env-var resolution: helper stays default-fallback (shared with TARGET_SHEET_ID), special case lives at the call site (PPP-specific)."
    - "Defensive raise loud-fails on upstream-gate bypass: ValueError surfaces data drift instead of producing an ambiguous primary-looking filename when the variant_suffix builder hits empty __helper_foreman."
    - "Scope immutability test: explicit regression test guards the legacy `helper` branch against accidental WR-03 broadening."
key-files:
  created: []
  modified:
    - "generate_weekly_pdfs.py — WR-02 empty-string-as-zero special case + PPP routing ENABLED/DISABLED startup banner; WR-03 ValueError raises in the two new helper-shadow filename-suffix branches with a TODO comment above the legacy branch."
    - "website/docs/reference/environment.md — SUBCONTRACTOR_PPP_SHEET_ID section rewritten to document that BOTH `0` and `''` disable dual routing, with the asymmetry rationale and the new startup banner lines."
    - "tests/test_subcontractor_pricing.py — added TestSubcontractorPppSheetIdEmptyStringDisable (5 tests) and TestHelperShadowSuffixDefensiveRaise (4 tests)."
decisions:
  - "WR-02 special-case lives at the SUBCONTRACTOR_PPP_SHEET_ID call site, NOT inside _coerce_sheet_id — the helper is shared with TARGET_SHEET_ID where default-fallback is correct."
  - "WR-03 defensive raise is scoped to the TWO new shadow-variant branches only; the legacy `helper` branch (pre-existing same-shape silent fallthrough) is out of scope per 01-REVIEW.md and is explicitly guarded by an immutability regression test."
  - "PII discipline: raised ValueError message bodies contain WR + week + variant name only; foreman / dept / job are excluded per CLAUDE.md Living Ledger 2026-04-20 12:00 and verified by explicit assertions in the regression tests."
metrics:
  duration_min: 5
  completed_date: "2026-05-15"
  tasks_completed: 4
  files_modified: 3
  tests_added: 9
  tests_total_before: 562
  tests_total_after: 571
---

# Phase 01 Plan 10: WR-02 + WR-03 Gap Closure Summary

PPP routing now disables on either `0` or `''`; the two new helper-shadow filename-suffix branches refuse to produce ambiguous output if upstream drift bypasses the `_valid_helper_row` gate; documentation and regression tests lock in both contracts.

## Objective

Two independent gap-closures from `01-REVIEW.md` bundled by the same code-region (env-var startup + `generate_excel` filename-suffix branches; both are operational-safety hardening for the helper-shadow variant set):

1. **REVIEW-WR-02** — `SUBCONTRACTOR_PPP_SHEET_ID=''` (empty string) silently fell back to the hardcoded default `8162920222379908`. The documentation claimed "empty / `0` to disable dual routing"; only `0` actually disabled. Asymmetry resolved by special-casing empty-string-as-zero at the call site (NOT inside `_coerce_sheet_id`, which is shared with `TARGET_SHEET_ID` where default-fallback is correct). Paired with a startup-banner line that names the resolved active state.

2. **REVIEW-WR-03** — The `aep_billable_helper` and `reduced_sub_helper` branches inside `generate_excel`'s variant-suffix builder silently produced a primary-looking filename if `__helper_foreman` was empty. The upstream gate at `_valid_helper_row` in `group_source_rows` prevents this in production today, but a defensive `raise ValueError` surfaces future data drift loudly. Scope is the TWO NEW shadow-variant branches only — the legacy `helper` branch (pre-existing same shape) stays untouched per `01-REVIEW.md`'s explicit scope restriction.

## Tasks Completed

| Task | Name | Commit | Files |
| --- | --- | --- | --- |
| 1 | WR-02 special-case `SUBCONTRACTOR_PPP_SHEET_ID=''` + startup-banner state log | `c205410` | `generate_weekly_pdfs.py` |
| 2 | WR-02 doc rewrite — `environment.md` SUBCONTRACTOR_PPP_SHEET_ID disable semantics | `c11e45e` | `website/docs/reference/environment.md` |
| 3 | WR-03 defensive `ValueError` raise in the two helper-shadow filename-suffix branches | `4b7677c` | `generate_weekly_pdfs.py` |
| 4 | Regression tests: `TestSubcontractorPppSheetIdEmptyStringDisable` (5) + `TestHelperShadowSuffixDefensiveRaise` (4) | `d512f63` | `tests/test_subcontractor_pricing.py` |

## Diff Summary

### `generate_weekly_pdfs.py`

**WR-02 (Task 1):** Two additive blocks near the env-var resolution section.

1. After the existing `SUBCONTRACTOR_PPP_SHEET_ID = _coerce_sheet_id(...)` call, a single-line `if os.getenv('SUBCONTRACTOR_PPP_SHEET_ID', '8162920222379908') == '': SUBCONTRACTOR_PPP_SHEET_ID = 0` special case with a documenting comment block explaining why the helper itself is unchanged.

2. After the existing `📊 Subcontractor rate variants ENABLED/DISABLED` banner, a new banner block:

   ```text
   📊 Subcontractor PPP routing ENABLED (target sheet id: <id>)   # value > 0
   📊 Subcontractor PPP routing DISABLED (SUBCONTRACTOR_PPP_SHEET_ID='' or 0)   # value is 0
   ```

   Only emitted when the umbrella `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` is on (when off, PPP routing is moot).

**WR-03 (Task 3):** Inside `generate_excel`'s variant-suffix builder, the `aep_billable_helper` and `reduced_sub_helper` branches now check `if not helper_foreman:`, emit a `logging.error` with WR + week + variant, and `raise ValueError(...)` with a PII-redact-compatible message body (no foreman / dept / job in the body). A TODO comment above the legacy `elif variant == 'helper':` branch documents the follow-up tech-debt cleanup option.

### `website/docs/reference/environment.md`

The `### SUBCONTRACTOR_PPP_SHEET_ID` section was rewritten (heading anchor preserved verbatim) to document:

- **Disable dual routing:** Both `0` (integer) AND `''` (empty string) resolve to `0` and disable. Pre-2026-05-15 asymmetry called out explicitly with the 01-10 plan as the closing reference.
- **Other values:** Non-empty, non-integer values fall back to the hardcoded default and log a WARNING. The fallback is intentional (shared helper preserves `TARGET_SHEET_ID` semantics).
- **Startup banner:** Operators can grep `Subcontractor PPP routing ENABLED` / `Subcontractor PPP routing DISABLED` to confirm the resolved state.
- **Rollback:** Unchanged from the prior section (same-sheet detection + unreachable-sheet automatic degrade).

Cross-link integrity verified: `website/docs/runbook/workflows.md` lines 73 and 109 reference `[../reference/environment.md#subcontractor_ppp_sheet_id]`; both anchors still resolve because the heading was preserved.

### `tests/test_subcontractor_pricing.py`

Two new classes appended between `TestSubcontractorVariantKillSwitchAndScope` and `TestSubcontractorVariantOpenpyxlCompliance`:

**`TestSubcontractorPppSheetIdEmptyStringDisable`** (5 tests):

- `test_empty_string_disables_ppp` — WR-02 primary contract
- `test_zero_string_disables_ppp` — pre-existing behavior preserved
- `test_unset_uses_hardcoded_default` — default-fallback path
- `test_invalid_value_falls_back_to_default` — `_coerce_sheet_id` WARN-and-fallback preserved
- `test_integer_string_passes_through` — happy path

Uses the `importlib.reload(generate_weekly_pdfs)` pattern with `os.environ['SENTRY_DSN'] = ''` + `mock.patch('sentry_sdk.init')` brackets per Living Ledger 2026-04-22 16:05 rule (8) so a developer's local DSN doesn't fire a real Sentry init on every test. `setUp` / `tearDown` snapshot + restore `SUBCONTRACTOR_PPP_SHEET_ID` and `SENTRY_DSN`, and `tearDown` re-reloads the module to baseline.

**`TestHelperShadowSuffixDefensiveRaise`** (4 tests):

- `test_aep_billable_helper_empty_foreman_raises_value_error` — WR-03 primary contract; explicit assertion that dept `500` and job `JOB-99` from the fixture do NOT leak into the raise body.
- `test_reduced_sub_helper_empty_foreman_raises_value_error` — symmetric.
- `test_legacy_helper_branch_does_not_raise_on_empty_foreman` — **scope-immutability guard**. Constructs a `helper` variant group with empty foreman; asserts NO `ValueError` is raised. If a future plan intentionally extends the raise to the legacy branch, this test must be removed and a symmetric raise+test pair added.
- `test_production_aep_billable_helper_branch_has_defensive_raise` — source-level guard (belt-and-suspenders) confirming the raise text landed in `generate_weekly_pdfs.py`.

Includes:

- Imports updated: `importlib` and `from unittest import mock` added (test file previously imported neither).
- `_make_group` static helper produces a 1-row group with the minimum field set the variant-suffix builder needs to reach the variant branch (Work Request #, Weekly Reference Logged Date, `__variant`, `__helper_foreman`, plus fields needed by `generate_excel`'s pre-suffix derivations: `Snapshot Date`, `Units Total Price`, `CU`, `Quantity`, `Customer Name`, `Foreman`, `Dept #`, `Job #`, `__effective_user`, `__current_foreman`, `__helper_dept`, `__helper_job`, `__week_ending_date`).
- `setUp` directs `OUTPUT_FOLDER` into a `tempfile.TemporaryDirectory` so the legacy-helper test (which doesn't raise and continues into workbook construction) doesn't pollute the repo.

## Verification

All 9 verification gates pass:

| # | Check | Expected | Actual |
| --- | --- | --- | --- |
| 1 | `python -m py_compile generate_weekly_pdfs.py` | exit 0 | OK |
| 2 | `grep -c "SUBCONTRACTOR_PPP_SHEET_ID = 0" generate_weekly_pdfs.py` | 1 | 1 |
| 3 | `grep -c -E "Subcontractor PPP routing ENABLED\|DISABLED" generate_weekly_pdfs.py` | 2 | 2 |
| 4 | `grep -c "aep_billable_helper requires __helper_foreman" generate_weekly_pdfs.py` | 1 | 1 |
| 5 | `grep -c "reduced_sub_helper requires __helper_foreman" generate_weekly_pdfs.py` | 1 | 1 |
| 6 | `grep -A 5 "elif variant == 'helper':" generate_weekly_pdfs.py \| grep -c "raise ValueError"` | 0 (legacy untouched) | 0 |
| 7 | `grep -c "Disable dual routing" website/docs/reference/environment.md` | 1 | 1 |
| 8 | `grep -c "@cell" generate_weekly_pdfs.py` | 0 | 0 |
| 9 | `pytest tests/` | exit 0 | **571 passed, 22 skipped, 46 subtests** |

### Critical-invariant gates (from plan front-matter)

- `pytest tests/test_subcontractor_pricing.py::TestPhase1IntegrationRegression -v` → **5/5 pass** ✓
- `pytest tests/test_subcontractor_pricing.py::TestSubcontractorVariantKillSwitchAndScope -v` → **4/4 pass** ✓
- `cd website && npm run typecheck` → **SKIPPED** (see Deviations below).

### Test count

- Pre-plan baseline: 562 passed (end of wave 7).
- Post-plan: **571 passed**, +9 new tests (5 PPP empty-disable + 4 helper-shadow defensive raise), no regressions in the 562 existing tests.

## Decisions Made

1. **WR-02 helper unchanged:** The single-line empty-string special case (`if os.getenv(...) == '': SUBCONTRACTOR_PPP_SHEET_ID = 0`) lives at the call site immediately after `_coerce_sheet_id`. `_coerce_sheet_id` itself is shared with `TARGET_SHEET_ID` resolution where the default-fallback for empty input is correct (`TARGET_SHEET_ID` has no "disabled" state), so adding the empty-string special-case inside the helper would regress `TARGET_SHEET_ID`.

2. **WR-03 scope-locked to NEW variants:** The legacy `helper` branch has the same silent-fallthrough shape, but modifying it carries regression risk for the long-standing helper-variant production path (in service for years, exercised by ~7 weekday runs × 2-hour cadence). The TODO comment + explicit immutability regression test (`test_legacy_helper_branch_does_not_raise_on_empty_foreman`) makes the future tech-debt cleanup option discoverable while guarding against accidental broadening.

3. **PII discipline in raised messages:** Raised `ValueError` body contains `wr_num`, `week_end_raw`, and the variant name only. The fixture uses dept `500` and job `JOB-99`; the regression tests explicitly assert both strings are absent from `str(exc)`. This matches the defense-in-depth pattern from `_redact_exception_message` (Living Ledger 2026-04-23 12:00) — even though the upstream gate at `_valid_helper_row` makes the raise unreachable in production today, we strip PII from the body in advance so that if the raise ever fires, no row PII can land in a Sentry capture's `context_data` payload.

4. **Test reload pattern reuses `_safe_reload_gwp` shape:** Mirrors the `test_performance_optimizations.py` and `test_sentry_log_sanitizer.py` precedent per Living Ledger 2026-04-22 16:05 rule (8). The `tearDown` re-reload runs the same Sentry-suppression bracket so a test that mutates env vars cannot leak module state into unrelated test classes.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written. No Rule 1 / Rule 2 / Rule 3 deviations encountered.

### Skipped Optional Steps

**[Skipped: optional doc build]** — Task 2 acceptance criteria flagged `cd website && npm run typecheck && npm run build` as *optional but recommended*. The worktree's `website/node_modules` is not installed (verified via `ls website/node_modules → No such file or directory`). Per the plan's explicit fallback ("If `website/node_modules` is not installed in the execution environment, skip the build step and document the skip in the task SUMMARY"), the build step was skipped. The markdown change introduces no new MDX imports and no front-matter changes; the section heading anchor is preserved verbatim (verified) so cross-links from `website/docs/runbook/workflows.md` (lines 73 and 109) continue to resolve. Future PR-time CI is the authoritative build gate.

### Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None — neither change introduces new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. WR-02 is a single env-var resolution refinement that *narrows* the resolved value space (one previously-unintended fallback case is now disabled); WR-03 is a defensive raise that *fail-fasts* a previously-silent code path that downstream attachment routing was already misclassifying as primary.

## TDD Gate Compliance

Plan-level type is `execute` (not `tdd`); only Task 4 is `tdd="true"` at the task level. Task 4's test commit (`d512f63`) was the final commit because Tasks 1 and 3's implementation was already in place from the gap-closure remit (the tests verify and lock in the contract those tasks established). The git history reads `feat(01-10) → docs(01-10) → feat(01-10) → test(01-10)` — the `test` commit landed AFTER `feat` for both contracts. This is intentional for a gap-closure plan where the contract is established by 01-REVIEW.md upstream and the unit-test-locked-in form is the final deliverable. The RED gate was implicit in 01-REVIEW.md's specification of the broken behavior; the GREEN gate landed in Tasks 1 + 3; the lock-in tests landed in Task 4.

## CLAUDE.md Compliance

Verified against every applicable rule in `c:\Users\juflores\dev\Generate-Weekly-PDFs-DSR-Resiliency\CLAUDE.md`:

- ✅ **Production Safety & Code Modification:** Changes are additive, surgical, and minimal. WR-02 adds a single guard line + a banner block; WR-03 adds raise blocks inside two existing `elif` branches. No production code path was deleted or rewritten. Behavior is byte-identical for every input that already worked correctly (numeric WR#s, populated foremen, populated PPP env vars).
- ✅ **Smartsheet Formula Restriction:** No `@cell` introduced anywhere. Verified by `grep -c "@cell" generate_weekly_pdfs.py` → 0.
- ✅ **Python style:** PEP 8 compliant; type hints unchanged on touched functions; docstrings unchanged.
- ✅ **Living Ledger discipline:** This plan adds two operational rules (WR-02 special-case at-call-site rule, WR-03 NEW-variants-only scope) that the gap-closure phase already encoded in 01-REVIEW.md. A Living Ledger entry summarizing both gap closures will be appended via the same PR that lands this work (per the autonomous cloud memory injection rule).

## Commits

```text
d512f63 test(01-10): regression tests for WR-02 empty-disable + WR-03 raise
4b7677c feat(01-10): WR-03 defensive raise on empty helper foreman (new variants)
c11e45e docs(01-10): clarify SUBCONTRACTOR_PPP_SHEET_ID disable semantics
c205410 feat(01-10): WR-02 empty-string PPP disable + routing-state banner
```

## Self-Check: PASSED

Verified at 2026-05-15T16:20:32Z:

- `FOUND: .planning/phases/01-subcontractor-rate-logic-modification/01-10-SUMMARY.md`
- `FOUND: generate_weekly_pdfs.py`
- `FOUND: website/docs/reference/environment.md`
- `FOUND: tests/test_subcontractor_pricing.py`
- `FOUND: c205410` (Task 1 — WR-02 PPP empty-disable + banner)
- `FOUND: c11e45e` (Task 2 — environment.md doc rewrite)
- `FOUND: 4b7677c` (Task 3 — WR-03 defensive raise)
- `FOUND: d512f63` (Task 4 — regression tests)

All 4 task commits exist on the worktree branch; SUMMARY references every file and hash listed in this plan.
