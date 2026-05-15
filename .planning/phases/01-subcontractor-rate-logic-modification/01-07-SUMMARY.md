---
phase: 01-subcontractor-rate-logic-modification
plan: 07
subsystem: python-billing-pipeline
tags: [python, gap-closure, code-review, filter-matchers, exclude-wrs, wr-filter, subcontractor-variants]
requirements: [REVIEW-CR-02, REVIEW-CR-03]
dependency_graph:
  requires:
    - "01-01..01-06 (Phase 1 subcontractor variant infrastructure: CSV loader, fingerprint, _resolve_row_price, variant emission, parser/round-trip, dual-target builder, writer kwarg threading, schema migration, PII markers)"
  provides:
    - "production-active EXCLUDE_WRS path that suppresses all 7 variants per WR (primary + helper + USER + vac_crew + reduced_sub + aep_billable + their two helper-shadow twins)"
    - "TEST_MODE WR_FILTER path that retains all 7 variant groups per WR (minus _USER_ by design)"
    - "regression coverage that documents the deliberate _USER_ asymmetry between the two matchers"
  affects:
    - "generate_weekly_pdfs.py: group_source_rows.{_key_matches_wr, _key_matches_excluded_wr}"
    - "tests/test_security_audit_followup.py: +2 test classes, +10 methods, +30 subtests"
tech-stack:
  added: []
  patterns:
    - "Sibling matchers MUST stay in sync — extending one without the other reopens the gap. Docstring on each matcher explicitly names the sibling."
    - "Source-level grep-guard tests defeat the 'test mirror passes but production matcher was reverted' failure mode by reading generate_weekly_pdfs.py and asserting the four characteristic f-string fragments are present (and present at least twice — once per matcher)."
    - "Anchored to function names (`def _key_matches_wr`, `def _key_matches_excluded_wr`) — not line numbers — per Living Ledger 2026-04-22 rule."
key-files:
  created: []
  modified:
    - generate_weekly_pdfs.py
    - tests/test_security_audit_followup.py
decisions:
  - "Preserve the _USER_ asymmetry. WR_FILTER has never carried the _USER_ clause; we did NOT speculatively add it. TestWrFilterMatchesAllVariants.test_user_variant_intentionally_not_matched guards against future drift."
  - "Additive boolean clauses only — pre-fix four-clause behavior is preserved verbatim in both matchers. Realistic operator data unaffected."
  - "Pair the production fix with both a behavioural-mirror test class AND a source-level grep test, because the matchers are nested helpers (cannot be imported / monkey-patched directly). The two layers are complementary, not redundant."
metrics:
  duration_minutes: ~10
  completed_date: "2026-05-15"
  tasks_completed: 3
  files_modified: 2
  tests_added: 10
  subtests_added: 30
  full_suite_passing: 547
  full_suite_skipped: 22
---

# Phase 01 Plan 07: Filter-matcher variant gap closure Summary

CR-02 + CR-03 closed: extend `_key_matches_excluded_wr` and `_key_matches_wr` (the two nested filter matchers inside `group_source_rows`) so all four Phase 1 subcontractor variant group-key suffixes (`_REDUCEDSUB`, `_AEPBILLABLE`, `_REDUCEDSUB_HELPER_<name>`, `_AEPBILLABLE_HELPER_<name>`) are recognized — closing both the production-active EXCLUDE_WRS hole and the TEST_MODE WR_FILTER mirror.

## Objective

Phase 1's subcontractor pipeline emits seven possible group-key shapes per WR. Before this plan, the two filter matchers inside `group_source_rows` only recognized four:

| Suffix shape                          | Source         | Pre-fix matched? |
| ------------------------------------- | -------------- | ---------------- |
| `MMDDYY_WR`                           | primary        | yes              |
| `MMDDYY_WR_HELPER_<name>`             | helper         | yes              |
| `MMDDYY_WR_USER_<name>`               | user (legacy)  | excluded only    |
| `MMDDYY_WR_VACCREW`                   | vac_crew       | yes              |
| `MMDDYY_WR_REDUCEDSUB`                | reduced_sub    | **no (CR-02/03)**|
| `MMDDYY_WR_AEPBILLABLE`               | aep_billable   | **no (CR-02/03)**|
| `MMDDYY_WR_REDUCEDSUB_HELPER_<name>`  | reduced_sub_h  | **no (CR-02/03)**|
| `MMDDYY_WR_AEPBILLABLE_HELPER_<name>` | aep_billable_h | **no (CR-02/03)**|

Critical sub-string observation that made these silent: `WR_REDUCEDSUB_HELPER_<name>` does NOT satisfy `suffix.startswith(f"{wr}_HELPER_")` — the actual prefix is `WR_REDUCEDSUB_HELPER_`, so the existing helper-shadow check missed entirely. Both matchers needed four additive boolean clauses.

## Matcher diff summary

Both matchers in `generate_weekly_pdfs.py:group_source_rows` got four new boolean clauses appended to their return expression. The pre-fix four clauses (primary, `_HELPER_`, `_USER_` (excluded only) / `_VACCREW`) are preserved verbatim.

### `_key_matches_excluded_wr` (CR-02, production-active path)

Pre-fix returned the boolean of four clauses; post-fix returns the boolean of eight. New clauses:
- `or suffix == f"{wr}_REDUCEDSUB"`
- `or suffix == f"{wr}_AEPBILLABLE"`
- `or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")`
- `or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")`

Commit: `ce2a0c0`

### `_key_matches_wr` (CR-03, TEST_MODE diagnostic mirror)

Same four additive clauses. The `_USER_` clause is deliberately NOT mirrored into this matcher — WR_FILTER has never carried it and that asymmetry is preserved by intent.

Commit: `7fd5b42`

### Regression tests

`TestExcludeWrsMatchesAllVariants` and `TestWrFilterMatchesAllVariants` appended at the end of `tests/test_security_audit_followup.py`. Two layers:
1. **Behavioural mirror** — a `_exclude_matches` / `_filter_matches` static helper inside each class re-implements the production matcher body, so the eight (or seven) variant suffixes can be exercised directly without monkey-patching nested functions.
2. **Source-level grep guard** (`test_production_function_body_contains_all_four_new_clauses` in each class) — reads `generate_weekly_pdfs.py` text and asserts the four characteristic f-string fragments (`f"{wr}_REDUCEDSUB"`, `f"{wr}_AEPBILLABLE"`, `f"{wr}_REDUCEDSUB_HELPER_"`, `f"{wr}_AEPBILLABLE_HELPER_"`) appear in the file. The `_key_matches_wr` variant additionally requires each fragment to appear AT LEAST twice (once per matcher), guarding against accidental reversion of one matcher while the other stays fixed.

Commit: `895ea18`

## Tasks executed

| Task | Name                                                                      | Commit  | Files modified                          |
| ---- | ------------------------------------------------------------------------- | ------- | --------------------------------------- |
| 1    | Extend `_key_matches_excluded_wr` (CR-02 — production EXCLUDE_WRS)        | ce2a0c0 | generate_weekly_pdfs.py                 |
| 2    | Extend `_key_matches_wr` (CR-03 — TEST_MODE WR_FILTER mirror)             | 7fd5b42 | generate_weekly_pdfs.py                 |
| 3    | Regression tests `TestExcludeWrsMatchesAllVariants` + `TestWrFilterMatchesAllVariants` | 895ea18 | tests/test_security_audit_followup.py   |

## Decisions Made

- **Preserve the `_USER_` asymmetry between the two matchers.** `_key_matches_wr` has never recognized `_USER_`; speculatively adding it would broaden TEST_MODE behaviour without a documented production incident. `TestWrFilterMatchesAllVariants.test_user_variant_intentionally_not_matched` is a regression guard so a future contributor who "sees the asymmetry and wants to make it consistent" gets a loud test failure with a comment explaining the asymmetry is by design.
- **Behavioural mirror + source-level grep, not just one.** The matchers are nested helpers inside `group_source_rows`; they cannot be imported or monkey-patched. The behavioural mirror tests document the *contract* (what each matcher must accept/reject). The source-level grep tests document the *production landing* (the file actually carries the eight clauses). Either layer alone has a known failure mode the other layer catches.
- **Anchor docs to function names, not line numbers.** Both matcher docstrings reference `_key_matches_wr` / `_key_matches_excluded_wr` by name, not by line. Mirrors the Living Ledger 2026-04-22 rule (line numbers drift; function names don't).

## Test counts (added / passed / total)

- Added: **10 test methods** (5 in `TestExcludeWrsMatchesAllVariants`, 5 in `TestWrFilterMatchesAllVariants`).
- New subtests: **30** (10 from the seven-variant assertion in CR-02, 7 from the seven-variant assertion in CR-03, plus the rest spread across substring / malformed / source-level grep tests).
- `pytest tests/test_security_audit_followup.py -k "TestExcludeWrsMatchesAllVariants or TestWrFilterMatchesAllVariants" -v` → `10 passed, 30 subtests passed`.
- `pytest tests/ -x --tb=short -q` → **547 passed, 22 skipped, 46 subtests passed** (up from 537 / 22 / 16 before this plan). Full suite still green.

## Verification commands run

| Command                                                                      | Result                                              |
| ---------------------------------------------------------------------------- | --------------------------------------------------- |
| `python -m py_compile generate_weekly_pdfs.py`                               | exits 0 (no syntax regression)                      |
| `python -m py_compile tests/test_security_audit_followup.py`                 | exits 0                                             |
| `pytest tests/ -x --tb=short -q`                                             | 547 passed, 22 skipped, 46 subtests (was 537/22/16) |
| `grep -c "@cell" generate_weekly_pdfs.py`                                    | 0 (CLAUDE.md absolute ban respected)                |
| `grep -c "class TestExcludeWrsMatchesAllVariants" tests/test_security_audit_followup.py` | 1                                       |
| `grep -c "class TestWrFilterMatchesAllVariants" tests/test_security_audit_followup.py`   | 1                                       |
| `grep -c "def _key_matches_excluded_wr" generate_weekly_pdfs.py`             | 1 (single-definition preserved)                     |
| `grep -c "def _key_matches_wr" generate_weekly_pdfs.py`                      | 1 (single-definition preserved)                     |

## Documented Step B diagnostic command — now functional

Per `01-VERIFICATION.md`, the operator diagnostic is:

```bash
TEST_MODE=true WR_FILTER=12345 SKIP_UPLOAD=true python generate_weekly_pdfs.py
```

Before this plan: the four new variant groups for WR `12345` were dropped before generation (`_key_matches_wr` did not recognize them), so the command silently produced zero `_AEPBillable` / `_ReducedSub` output. Operators ran the documented command and got no diagnostic signal.

After this plan: all seven variant groups for WR `12345` (minus `_USER_`, by design) survive the filter and reach generation. The documented operator-diagnostic path is exercisable end-to-end. `TestWrFilterMatchesAllVariants.test_all_seven_variants_retained_for_target_wr` locks this in via the seven-key subtest matrix.

## Deviations from Plan

None — plan executed exactly as written. Tasks 1, 2, 3 each produced the exact diff specified in the plan's `<action>` blocks. All acceptance criteria met (grep counts, py_compile, full suite green, no `@cell` regression, single-definition matchers).

The only non-deviation worth noting: the worktree's pytest 9.0.2 + Python 3.14.3 requires `PYTHONPATH=.` when running a single test file by path (e.g. `pytest tests/test_security_audit_followup.py -k ...`), but the bare `pytest tests/` invocation auto-resolves the module via test discovery. The plan's verification command `pytest tests/ -v` works as documented; the per-file targeted invocation needs `PYTHONPATH=.` in this environment. Not a behavior change in the test or production code.

## Threat Flags

None. The change is additive boolean clauses inside two existing helpers. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries.

## Self-Check: PASSED

- [x] `generate_weekly_pdfs.py` — modified at `def _key_matches_excluded_wr` (commit `ce2a0c0`) and `def _key_matches_wr` (commit `7fd5b42`). Confirmed via `Read` and `Grep`.
- [x] `tests/test_security_audit_followup.py` — appended two new test classes (commit `895ea18`). Confirmed via `pytest -k`.
- [x] Commit `ce2a0c0` exists in `git log --oneline -5`.
- [x] Commit `7fd5b42` exists in `git log --oneline -5`.
- [x] Commit `895ea18` exists in `git log --oneline -5`.
- [x] `pytest tests/` exits 0 with 547 passed (was 537, +10 new tests).
- [x] `python -m py_compile generate_weekly_pdfs.py` exits 0.
- [x] `grep -c "@cell" generate_weekly_pdfs.py` returns 0.
- [x] No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md` (orchestrator owns those).

_Phase 1 ROADMAP success criterion 5 (byte-identical primary / helper / vac_crew / ORIG-folder hashes) is preserved — the matchers ONLY affect which group keys survive filtering; they do NOT touch `calculate_data_hash`, `_resolve_row_price`, `group_source_rows` row-emission, or `generate_excel`._
