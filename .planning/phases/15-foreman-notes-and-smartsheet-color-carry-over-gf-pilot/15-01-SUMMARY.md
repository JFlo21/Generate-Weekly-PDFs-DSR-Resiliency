---
phase: 15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot
plan: 01
subsystem: testing
tags: [golden-record, regression-fence, openpyxl, change-detection, requirements]
requires: []
provides:
  - "BASE golden record (workbook dump + group hash + per-row Phase 11 fingerprints) for all 10 Excel variant families"
  - "tests/test_foreman_notes_baseline.py regression fence every later Phase 15 plan must keep green"
  - "15-BASE_SHA: the BASE commit every Phase 15 diff check is relative to"
  - "FN-01..FN-13 registered in REQUIREMENTS.md with traceability rows"
affects: [15-02, 15-03, 15-04, 15-05, 15-06, 15-07]
tech-stack:
  added: []
  patterns:
    - "golden capture under pinned_env(): each env-derived input patched on the module that consumes it"
    - "subprocess env-independence test: perturbed environment must reproduce the fixture"
key-files:
  created:
    - tests/_foreman_notes_golden.py
    - tests/fixtures/foreman_notes/golden_off.json
    - tests/test_foreman_notes_baseline.py
    - .planning/phases/15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot/15-BASE_SHA
  modified:
    - .planning/REQUIREMENTS.md
key-decisions:
  - "Golden uses a fixed WR 90311 / invented names (Pat Example, Sam Sample, Robin Sample, Vic Crewman); public-repo safe"
  - "Report Generated On wall-clock cell replaced by <generated-at>; output filename timestamp replaced by <ts>"
  - "Logo path pinned to a nonexistent file so the golden is the text-title branch on every host"
metrics:
  duration: "~25m"
  completed: 2026-10-29
status: complete
commits: 3
plan_head_before: 3b14a1eee7cee09d6f4b8054c47e28eed7e11185
plan_head_after: 928185c779dba5b1d486597b9176d1d78e97532b
actuals:
  tokens: 100000
  tasks: 3
  commits: 3
---

# Phase 15 Plan 01: Golden baseline and FN requirements Summary

Frozen BASE golden record of workbook cells, group hash and per-row fingerprints for all ten variant families (`generate_excel` is the single path), plus FN-01..FN-13 registered in REQUIREMENTS.md; zero production files touched.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Tracer: golden capture + baseline assert (primary group), 15-BASE_SHA | c122e01 |
| 2 | Extend golden to every variant family (FN-12), env-independence test | 4601549 |
| 3 | Register FN-01..FN-13 in REQUIREMENTS.md | 928185c |

## What was built

- `tests/_foreman_notes_golden.py`: `build_fixture_groups()` (10 groups: primary, helper, helper2, vac_crew, aep_billable, reduced_sub, aep_billable_helper, reduced_sub_helper, aep_billable_helper2, reduced_sub_helper2), `dump_workbook()` (cell value/type/number format/font/fill/alignment, merged ranges, widths A..J, page setup, margins, fit-to-page, print props, footer, image count), `hash_digests()`, `pinned_env()`, `capture()`, and `--write` / `--print` entry points.
- Every group carries non-blank `Foreman Notes` text and one `=`-prefixed note; a test proves none of it appears in any workbook today.
- Fixture `meta.pinned` lists the 13 pinned inputs (module, name, value); `meta.skipped_variants` is empty (all 10 render offline); `meta.base_sha` equals `15-BASE_SHA`.
- Returned tuple data (filename with `<ts>`, wr_numbers, customer name, missing_cus) is part of the record, so filename/suffix drift is caught too.

## Verification

- `python -m pytest tests/test_foreman_notes_baseline.py -q`: 9 passed, 50 subtests passed.
- Env-independence: subprocess (`python -I ... --print`) with `EXTENDED_CHANGE_DETECTION=0`, `RATE_CUTOFF_DATE=2030-01-01`, `TEST_MODE=true`, `RES_GROUPING_MODE=primary`, `HELPER2_ENABLED=0`, `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=0`, `SKIP_UPLOAD=true` reproduces the fixture (excluding `meta.base_sha`); confirmed the perturbation really takes effect on an unpinned facade import.
- Full suite: `python -m pytest tests/ -q`: 2615 passed, 1 skipped, 714 subtests passed.
- `git status --porcelain -- pipeline/ generate_weekly_pdfs.py` empty; `git diff --stat 3b14a1e..HEAD -- pipeline/ generate_weekly_pdfs.py` empty.
- REQUIREMENTS.md diff: 63 additions, 0 removals; regex check reports no missing FN ids.

## Deviations from Plan

- [Rule 3 - Blocking] The facade prints emoji at import time and crashes on a cp1252 console when run as a script; `main()` now reconfigures stdout/stderr to UTF-8. Test-side only.
- `pinned_env()` also pins `pipeline.pricing.SUBCONTRACTOR_RATE_VARIANTS_ENABLED` as the plan specified, although `_resolve_row_price` does not read it (it is used only by the admission helper); pinned for safety, harmless.
- `HELPER2_ENABLED` is consumed only by `pipeline/fetch.py` and `pipeline/attribution.py`, outside the capture path, so it is not pinned; the perturbed-env test sets it to `0` and passes.

Fixture size is large (about 373 KB, 10 full workbook dumps) versus the plan estimate; actuals.tokens reflects that.

## Known Stubs

None.

## Threat Flags

None. Fixture data is synthetic; no network, token, or `.env` access.

## Self-Check: PASSED

- tests/_foreman_notes_golden.py, tests/test_foreman_notes_baseline.py, tests/fixtures/foreman_notes/golden_off.json, 15-BASE_SHA: FOUND
- Commits c122e01, 4601549, 928185c: FOUND (ancestors of HEAD)
