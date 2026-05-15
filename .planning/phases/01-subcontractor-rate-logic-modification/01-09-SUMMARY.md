---
phase: 01-subcontractor-rate-logic-modification
plan: 09
subsystem: billing-pipeline-python
tags: [python, gap-closure, code-review, pii-markers, sentry, source-sheet-id, log-sanitizer]
requirements: [REVIEW-WR-04, REVIEW-WR-06]
dependency-graph:
  requires:
    - "Phase 01 Plan 02 (subcontractor PII markers + group-key tokens)"
    - "Phase 01 Plan 03 (helper-shadow GROUP CREATED log emission)"
    - "Phase 01 Plan 03 (__source_sheet_id writer alias)"
  provides:
    - "Defense-in-depth PII coverage for helper-shadow GROUP CREATED logs"
    - "Canonical __source_sheet_id reader in missing-CU attribution loop"
  affects:
    - generate_weekly_pdfs.py
    - tests/test_security_audit_followup.py
tech-stack:
  added: []
  patterns:
    - "Explicit PII marker entries (vs accidental substring containment)"
    - "Source-level grep regression assertions for field-naming consistency"
key-files:
  created: []
  modified:
    - "generate_weekly_pdfs.py — _PII_LOG_MARKERS extended + missing-CU loop reads canonical name"
    - "tests/test_security_audit_followup.py — TestPiiLogMarkersIncludeSubcontractorVariants extended + new TestSourceSheetIdFieldConsistency"
decisions:
  - "Retain legacy __sheet_id WRITE at populate site (back-compat for any future reader); migrate READERS only — matches WR-06 REVIEW recommendation."
  - "Use source-level grep assertions (not behavioral mocks) for WR-06 lock-in — the contract is a per-line invariant, not a runtime behavior."
  - "Rename test_all_seven_subcontractor_markers_present to test_all_nine_subcontractor_markers_present (vs adding a sibling) — single source-of-truth for the whole-set assertion."
metrics:
  duration: "00:02:35"
  completed: "2026-05-15T11:08:06-05:00"
  tasks_completed: 3
  files_modified: 2
  tests_added: 6
  pytest_before: "556 passed / 22 skipped"
  pytest_after: "562 passed / 22 skipped"
---

# Phase 1 Plan 09: Code-Review WR-04 + WR-06 Gap Closure Summary

Closed two operational-hygiene findings from the Phase 1 code review (`01-REVIEW.md`):
explicit PII markers for the helper-shadow `GROUP CREATED` log lines (WR-04), and
canonical-field-name standardization in the missing-CU attribution loop (WR-06). Both
fixes are purely additive and carry zero runtime behavior change.

## Tasks Completed

| Task | Name                                                  | Commit  | Files                              |
| ---- | ----------------------------------------------------- | ------- | ---------------------------------- |
| 1    | WR-04 — Add explicit helper-shadow PII markers        | 3c59fff | generate_weekly_pdfs.py            |
| 2    | WR-06 — Migrate missing-CU attribution to canonical   | d1a606e | generate_weekly_pdfs.py            |
| 3    | Regression tests (PII markers + field consistency)    | 040793e | tests/test_security_audit_followup.py |

## What Changed

### WR-04 — `_PII_LOG_MARKERS` extended (`generate_weekly_pdfs.py` lines 781-797)

Added two explicit string entries to the tuple immediately after the existing Phase 01
Plan 02 markers:

```python
"REDUCED SUB HELPER GROUP CREATED",
"AEP BILLABLE HELPER GROUP CREATED",
```

Inline comment cites Living Ledger 2026-04-20 12:00 (Sentry Logs sanitizer rule) and
spells out the failure mode the explicit markers protect against — a future wording
rewording (e.g. `"REDUCED SUB HELPER GRP CREATED"` or `"...REGISTERED"`) that breaks
the accidental substring containment of `"HELPER GROUP CREATED"` and silently leaks
helper foreman names to Sentry Logs.

**No log-emission code path changed.** Same INFO logs that fired before this commit
fire after; the sanitizer simply gates them by intentional contract instead of
accident-of-string-containment.

### WR-06 — Missing-CU attribution canonical-field migration

**Reader site** (inside `main()`, in the per-group missing-CU attribution block):

```diff
-                    for _r in group_rows:
-                        _sid = _r.get('__sheet_id')
+                    for _r in group_rows:
+                        _sid = _r.get('__source_sheet_id')
```

**Writer site** (inside `_fetch_and_process_sheet`): both `row_data['__sheet_id']`
and `row_data['__source_sheet_id']` writes are PRESERVED. Both still alias to the
same `source['id']` value so any future reader of the legacy field name does not
regress. The writer's comment block now references the WR-06 migration so future
maintainers see the back-compat rationale.

**No runtime behavior change.** The two fields are written together at populate time;
the loop sees identical sheet ids whether it reads the legacy name or the canonical
one. The migration removes the silent-divergence-risk surface — a future refactor
that splits the two field names would have silently routed every missing-CU WARNING
to sheet `-1` (the fallback bucket) without changing any pytest output. The new
regression tests trip that scenario at the source-grep level.

### Regression tests (`tests/test_security_audit_followup.py`)

Extended class `TestPiiLogMarkersIncludeSubcontractorVariants` with 2 new methods:

- `test_aep_billable_helper_group_created_log_text_in_markers`
- `test_reduced_sub_helper_group_created_log_text_in_markers`

Renamed the whole-set assertion `test_all_seven_subcontractor_markers_present`
to `test_all_nine_subcontractor_markers_present` and grew the expected set from
7 to 9 (preserves single-source-of-truth — no parallel sibling method).

New class `TestSourceSheetIdFieldConsistency` (4 tests) uses source-level grep on
`generate_weekly_pdfs.py` to lock in:

| Test                                                | Asserts                                                          |
| --------------------------------------------------- | ---------------------------------------------------------------- |
| `test_populate_site_writes_both_aliases`            | Both `row_data['__sheet_id']` and `row_data['__source_sheet_id']` writes exist |
| `test_missing_cu_attribution_reads_source_sheet_id` | Loop body contains `_r.get('__source_sheet_id')`                 |
| `test_missing_cu_attribution_does_not_read_legacy_alias` | Source has NO `_r.get('__sheet_id')` call                   |
| `test_writer_comment_references_wr_06_migration`    | `'WR-06'` appears in source (writer / loop comment blocks)       |

## Verification

```
SENTRY_DSN="" python -m pytest tests/
562 passed, 22 skipped in 4.68s

python -m py_compile generate_weekly_pdfs.py
exit 0

grep -c "@cell" generate_weekly_pdfs.py
0

grep -c "_r.get('__sheet_id')" generate_weekly_pdfs.py
0

grep -c "_r.get('__source_sheet_id')" generate_weekly_pdfs.py
1
```

## Deviations from Plan

### Minor: literal-string grep acceptance criteria

The plan's acceptance criteria for Task 1 specify:

```
grep -c "\"REDUCED SUB HELPER GROUP CREATED\"" generate_weekly_pdfs.py returns 1
```

The actual count is `2` because the inline comment immediately above the new tuple
entry references the literal token string by name (Living Ledger style — quotes the
new markers verbatim so a reader scanning the comment block sees the full token
list). This is the intended documentation pattern but technically diverges from the
"returns 1" wording.

**Resolution:** the spirit of the test (marker exists as a tuple entry exactly once)
is verified by a stricter regex: `grep -nE '^\s*"REDUCED SUB HELPER GROUP CREATED",\s*$' generate_weekly_pdfs.py`
returns exactly one match (line 795). The same stricter check holds for the AEP
BILLABLE HELPER marker (line 796) and for the four sibling markers from Plan 02.
The plan-level test (`test_all_nine_subcontractor_markers_present`) and the two new
individual marker tests both pass — the only artifact of this deviation is the
grep-count number, which is benign given the source verification by alternative
greps and by the pytest contract.

No code change made — the inline comment is intentional documentation per the
Living Ledger pattern.

### Other deviations

None. No Rule 1-3 auto-fixes were triggered. Both fixes are pure tightening of
existing safety nets with zero impact on production logic.

## Threat Model

No new attack surface introduced:

- WR-04 strengthens the existing Sentry Logs PII sanitizer's coverage by making
  scrubbing intentional rather than accidental. The marker tuple is a Python module-
  level constant; mutating it requires a code change.
- WR-06 substitutes one local-variable read with another that aliases to the same
  value at populate time. No new I/O, no new code paths.

No `threat_flags` raised.

## Known Stubs

None.

## Self-Check: PASSED

- [x] `.planning/phases/01-subcontractor-rate-logic-modification/01-09-SUMMARY.md` written
- [x] Task 1 commit `3c59fff` exists in `git log`
- [x] Task 2 commit `d1a606e` exists in `git log`
- [x] Task 3 commit `040793e` exists in `git log`
- [x] `pytest tests/` exits 0 (562 passed / 22 skipped)
- [x] `python -m py_compile generate_weekly_pdfs.py` exits 0
- [x] `grep -c "@cell" generate_weekly_pdfs.py` returns 0
- [x] No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md`
- [x] No file deletions in any of the three commits
