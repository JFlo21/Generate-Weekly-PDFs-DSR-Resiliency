---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 02
subsystem: billing-attribution
tags: [sentinel-classification, attachment-cleanup, smartsheet-sdk, lazy-import, pytest, tdd]

# Dependency graph
requires:
  - phase: 12-01
    provides: "OWN-02's core sentinel rule (is_sentinel_claimer, freeze_row, the cleanup gate), shipped in PRs #375/#376/#377 -- this plan narrows the one residual predicate defect on top of it"
provides:
  - "A narrowed pipeline.cleanup._is_sentinel_identifier that never classifies a real claimer name with leading punctuation as a sentinel (CR-01)"
  - "pipeline.cleanup._SANITIZED_ERROR_IDENTIFIERS -- the explicit allowlist of sanitized Smartsheet error-token spellings a leading underscore may match"
  - "A function-local, guarded AttachmentParentType import in pipeline.orchestrate._is_row_attachment that degrades to a string comparison instead of breaking module import on SDK relocation (WR-01)"
  - "tests/test_lazy_smartsheet_imports.py -- structural + behavioral regression suite pinning the import-placement fix"
affects: [12-06]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 3500
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sanitized-error-token allowlist: a leading-underscore filename token classifies as a sentinel only when its normalized remainder matches an explicit frozenset (_SANITIZED_ERROR_IDENTIFIERS), never via a bare startswith('_') check -- prevents a real name that happens to sanitize with a leading underscore from being misclassified"
    - "Function-local guarded SDK import (mirrors pipeline/discovery.py): a deep smartsheet.models.* import lives inside its sole consumer function, wrapped in try/except, so an SDK relocation degrades one helper instead of breaking module import"

key-files:
  created:
    - tests/test_lazy_smartsheet_imports.py
  modified:
    - pipeline/cleanup.py
    - pipeline/orchestrate.py
    - tests/test_sentinel_superseded_cleanup.py

key-decisions:
  - "_is_sentinel_identifier's leading-underscore allowlist normalizes with the exact same steps (strip, underscore-to-space, whitespace-collapse, casefold) as billing_audit.writer.is_sentinel_claimer, rather than importing pipeline/config.py's sanitization regex -- one normalization rule governs both predicates, per the plan's must_haves."
  - "pipeline/excel.py's six sanitization call sites were left untouched -- adding .strip() there would change generated filenames and therefore change-detection identity for existing groups, a billing-visible side effect out of scope for a predicate fix."
  - "The AttachmentParentType import degrades to a plain string ('ROW') comparison on ImportError rather than raising, preserving _is_row_attachment's existing fail-safe (no seeding) contract exactly as documented in its docstring."
  - "Both tasks followed strict RED-then-GREEN TDD: each fix was temporarily stashed to confirm the new test failed against the unmodified code before restoring the fix and confirming the pass, so the RED commit is a genuine failing-test artifact, not a post-hoc formality."

patterns-established:
  - "Sanitized Smartsheet error-token allowlist pattern (pipeline/cleanup.py): a leading underscore is sentinel-classified only against an explicit, dated allowlist -- never inferred structurally."

requirements-completed: [OWN-02]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "CR-01: a real claimer name whose sanitized identifier begins with a leading underscore (raw leading space/apostrophe/parenthesis) is never classified as a sentinel, while every previously-pinned sentinel spelling -- including case-variants -- still classifies as one"
    requirement: "OWN-02"
    verification:
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py::SentinelIdentifierPredicateTests::test_real_names_with_leading_punctuation_are_not_sentinels"
        status: pass
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py::SentinelIdentifierPredicateTests::test_placeholders_and_bare_primary"
        status: pass
    human_judgment: false
  - id: D2
    description: "WR-01: pipeline/orchestrate.py has no module-top-level AttachmentParentType import; _is_row_attachment imports it function-locally and degrades to a plain string comparison instead of raising when the deep SDK path is unavailable"
    requirement: "OWN-02"
    verification:
      - kind: unit
        ref: "tests/test_lazy_smartsheet_imports.py::StructuralImportPlacementTests::test_preamble_has_no_module_level_attachment_parent_type_import"
        status: pass
      - kind: unit
        ref: "tests/test_lazy_smartsheet_imports.py::StructuralImportPlacementTests::test_is_row_attachment_body_imports_attachment_parent_type_locally"
        status: pass
      - kind: unit
        ref: "tests/test_lazy_smartsheet_imports.py::IsRowAttachmentBehaviorTests::test_degrades_to_string_comparison_when_import_unavailable"
        status: pass
    human_judgment: false
  - id: D3
    description: "The sentinel-superseded delete gate at pipeline/cleanup.py (around the former lines 495-508) is unchanged apart from the predicate it calls"
    verification:
      - kind: other
        ref: "git diff 77a675b HEAD -- pipeline/cleanup.py (single hunk, confined to _is_sentinel_identifier and its new module-level constant; the delete gate below it has zero diff lines)"
        status: pass
    human_judgment: false

# Metrics
duration: ~15min
completed: 2026-09-03
status: complete
---

# Phase 12 Plan 02: CR-01 / WR-01 Ownership Code Review Fixes Summary

**Narrowed the sentinel-identifier false-positive that could delete a real person's billing attachment (CR-01), and moved a fragile module-top-level Smartsheet SDK enum import into its sole consumer function so an SDK relocation degrades instead of breaking the production entry module (WR-01) — both closed via strict RED-GREEN TDD.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-09-03T17:20:03Z (first RED commit)
- **Completed:** 2026-09-03T17:26:19Z
- **Tasks:** 2 completed (both `type="auto" tdd="true"`)
- **Files modified:** 4 (2 production, 1 new test file, 1 existing test file extended)

## Accomplishments

- `pipeline.cleanup._is_sentinel_identifier` no longer treats every leading underscore as a sentinel. A new `_SANITIZED_ERROR_IDENTIFIERS` frozenset (normalized: strip, underscore-to-space, whitespace-collapse, casefold — matching `billing_audit.writer.is_sentinel_claimer` exactly) is the only thing a leading underscore may match. Any other leading-underscore token — including real names sanitized from a raw leading space, apostrophe, or parenthesis (`_O_Brien`, `_Contractor__Smith`, `_Ana_Ruiz`) — now falls through to the existing lazy `is_sentinel_claimer` call, which correctly returns False.
- Every previously-pinned sentinel spelling (`Unknown_Foreman`, `Unknown_Helper`, `Unknown_VAC_Crew`, `_NO_MATCH`, `_REF_`, `_INVALID`) still classifies as a sentinel, plus two new case-variant rows (`_ref_`, `_No_Match`) proving the normalization is case-insensitive.
- The sentinel-superseded delete gate itself (`pipeline/cleanup.py`, around the former lines 495-508) is byte-for-byte unchanged — confirmed by inspecting the diff hunk, which is confined entirely to `_is_sentinel_identifier` and the new constant above it.
- `pipeline.orchestrate` no longer imports `smartsheet.models.enums.attachment_parent_type` at module scope. The import now lives inside `_is_row_attachment`'s own body, guarded in `try`/`except Exception` with a `# noqa: PLC0415` marker (matching `pipeline/cleanup.py`'s lazy-import house style), mirroring `pipeline/discovery.py`'s guarded function-local `smartsheet.models.*` pattern.
- On `ImportError`, `_is_row_attachment` degrades to the plain string comparison (`parent_type == 'ROW'`) instead of raising — preserving the function's existing fail-safe ("not a row attachment unless the string spelling matches") contract, proven by a test that monkeypatches `builtins.__import__` to simulate an SDK relocation.
- New `tests/test_lazy_smartsheet_imports.py` (8 tests): 2 structural tests (preamble has zero occurrences of the import; the function body has exactly one) and 6 behavioral tests (`AttachmentParentType.ROW`, the plain string `'ROW'`, `None`, `'SHEET'`, `'COMMENT'`, and the simulated-ImportError degrade path).
- Full repo suite: 2007 passed, 1 skipped, 371 subtests passed. `bash scripts/run_6_gates.sh` prints `ALL 6 GATES PASSED` (Gate 4 mypy delta neutral 71 -> 71).

## Task Commits

Each task followed the RED → GREEN TDD cycle (both fixes were temporarily stashed and re-tested to confirm a genuine RED before restoring GREEN):

1. **Task 1: CR-01 — narrow the sentinel-identifier heuristic** — `6273f93` (test, RED) → `289ed04` (feat, GREEN)
2. **Task 2: WR-01 — make the AttachmentParentType import function-local** — `48e03c1` (test, RED) → `41f0cb8` (feat, GREEN)

**Plan metadata:** commit for this SUMMARY.md follows.

## Files Created/Modified

- `pipeline/cleanup.py` — `_is_sentinel_identifier` narrowed; new module-level `_SANITIZED_ERROR_IDENTIFIERS` constant; docstring rewritten to state the corrected CR-01 reasoning.
- `pipeline/orchestrate.py` — module-top-level `AttachmentParentType` import removed; moved function-local into `_is_row_attachment`, guarded in `try`/`except`.
- `tests/test_sentinel_superseded_cleanup.py` — new `test_real_names_with_leading_punctuation_are_not_sentinels` subTest table; two case-variant rows added to the existing True table; module docstring extended with a dated CR-01 note.
- `tests/test_lazy_smartsheet_imports.py` (new) — structural + behavioral regression suite for the WR-01 import-placement fix.

## Decisions Made

See `key-decisions` in frontmatter — summarized: (1) the leading-underscore allowlist reuses `is_sentinel_claimer`'s exact normalization steps rather than a second regex-based rule; (2) `pipeline/excel.py`'s no-strip sanitization call sites were deliberately left untouched (billing-visible filename identity risk out of scope); (3) the SDK import degrades to a string comparison on failure rather than raising, matching the function's pre-existing fail-safe contract; (4) both tasks proved RED before GREEN by stashing the implementation change and re-running the new tests against the unmodified code.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' `<action>` instructions were followed verbatim: the allowlist token list, the normalization steps, the `pipeline/excel.py` non-modification constraint, the `# noqa: PLC0415` marker, the `try`/`except Exception` wrapper, and the `_read_source`/`_collapse_ws` structural-test idiom borrowed from `tests/test_billing_audit_shadow.py` were all implemented as specified.

## Issues Encountered

None. All verification commands (scoped pytest, full suite, py_compile, `bash scripts/run_6_gates.sh`) passed on the first run after each GREEN commit.

## User Setup Required

None — no external service configuration required. Both fixes are pure in-repo Python changes; no new dependencies, no Supabase DDL, no Smartsheet write behavior.

## Next Phase Readiness

- Both Phase 11.1 review findings (CR-01, WR-01) that Phase 12 owned are closed. `pipeline/cleanup.py`'s sentinel-superseded attachment-delete gate can now be trusted for the volume plan 12-06's remediation run without the false-positive real-name-deletion risk.
- No known stubs. No skipped tests. No unrun `<verify>` commands — every plan-level verification command listed in `12-02-PLAN.md` was executed and passed in this session.
- Ready for the next plan in Phase 12's wave sequence.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-03*

## Self-Check: PASSED

- FOUND: `pipeline/cleanup.py` (contains `_SANITIZED_ERROR_IDENTIFIERS`)
- FOUND: `pipeline/orchestrate.py` (no module-top-level `AttachmentParentType` import)
- FOUND: `tests/test_lazy_smartsheet_imports.py`
- FOUND: `tests/test_sentinel_superseded_cleanup.py` (extended)
- FOUND commit: `6273f93` (Task 1 RED)
- FOUND commit: `289ed04` (Task 1 GREEN)
- FOUND commit: `48e03c1` (Task 2 RED)
- FOUND commit: `41f0cb8` (Task 2 GREEN)
- CONFIRMED: `git diff --name-only 77a675b HEAD` lists exactly `pipeline/cleanup.py`, `pipeline/orchestrate.py`, `tests/test_lazy_smartsheet_imports.py`, `tests/test_sentinel_superseded_cleanup.py`
- CONFIRMED: full suite 2007 passed / 1 skipped / 371 subtests; `bash scripts/run_6_gates.sh` = ALL 6 GATES PASSED
