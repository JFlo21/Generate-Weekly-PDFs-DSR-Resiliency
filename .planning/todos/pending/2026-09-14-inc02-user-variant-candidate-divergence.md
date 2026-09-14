---
created: 2026-09-14T00:00:00-05:00
title: INC-02 D-04 candidate-set USER-variant divergence (live production_frequent FAIL)
area: pipeline
severity: major
files:
  - pipeline/orchestrate.py:_resolve_row_wr_week
  - pipeline/orchestrate.py:_filter_groups_to_affected
  - pipeline_memory/reader.py:map_affected_to_sheets
---

## Problem

Two recent live `production_frequent` runs (34648318434.1, 34541106039.1) produced
group-side `actual_not_in_candidate` parity FAIL verdicts from the phase's own
shadow-parity safety net: the D-04 incremental candidate selector missed
USER-variant groups that the full run actually produced and uploaded. The phase's
synthetic unit tests never exercised this class before this UAT session surfaced it,
and it was recorded only as an `11-UAT.md` "Observation (not a test-2 defect)" with
nothing filed anywhere in `.planning/` to drive it toward a fix — exactly the gap
`11-VERIFICATION.md` Gap 2 called out.

## Status

**Closed by plan 11-09 (2026-09-14):**

- Reproduced end-to-end with a fixture-backed test
  (`tests/fixtures/incremental/user_variant_candidate_miss.json`,
  `tests/test_parity_shadow.py::UserVariantCandidateParityTests`) that failed before
  the fix with the exact live symptom (`verdict: fail`, `reason:
  actual_not_in_candidate`) and passes after it.
- Confirmed cause: `_resolve_row_wr_week` (`pipeline/orchestrate.py`) derived its WR
  component as `str(wr).split('.')[0]` with no `_WR_SANITIZE` substitution and no
  50-character truncation, while `pipeline_memory.writer._sanitized_wr` applies both
  before a value reaches `row_state.wr` — the affected set this pair is compared
  against. A raw WR containing a sanitizer-affected character (the live class: an
  embedded space) resolved to two different strings on the two sides, so the pair
  never matched and the group was dropped from the candidate. A secondary
  falsy-WR mismatch (any falsy raw value vs. only a missing one) was fixed the same
  way.
- Fix: `_resolve_row_wr_week` now delegates its WR component to
  `pipeline_memory.writer._sanitized_wr` directly — one shared derivation instead of
  two parallel re-implementations. Pinned by a bidirectional contract test
  (`tests/test_incremental_read.py::AffectedPairKeyContractTests`, 8 WR shapes + 4
  week shapes).
- `RUN_MEMORY_INCREMENTAL_ENABLED` was NOT changed by this closure — it stays OFF
  (D-11). No workflow, schedule, schema, or billing-formula change.

**Remains owner-gated:**

- A fresh, currently-held ≥5 consecutive-pass `production_frequent` streak (via
  `pipeline_memory.reader.get_parity_streak()`), owned by plan 11-10 Task 3 under
  D-09 — this run's fix resets the clean-run count to zero; the streak must be
  re-established live before the INC-04 gate is considered held again.
- The flag flip itself (`RUN_MEMORY_INCREMENTAL_ENABLED` to `'1'` in
  `.github/workflows/weekly-excel-generation.yml`) remains a separate operator PR
  under D-11, and is NOT authorized by this closure.

This file stays in `pending/` — it is not done until plan 11-10 Task 3's live
observation lands.
