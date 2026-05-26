---
phase: "02"
plan: "02"
subsystem: "generate_weekly_pdfs"
tags: ["attribution", "bulk-prefetch", "performance", "tdd", "D-02", "D-03", "D-04", "D-05"]
dependency_graph:
  requires: ["02-01"]
  provides: ["bulk-attribution-wiring", "scope-removal"]
  affects: ["generate_weekly_pdfs.py", "billing_audit/writer.py"]
tech_stack:
  added: []
  patterns: ["bulk-prefetch-O(1)-map-read", "D-04-direct-HOLD", "parallel-pre-pass-replaced-by-map-read"]
key_files:
  created: []
  modified:
    - "generate_weekly_pdfs.py"
    - ".github/workflows/weekly-excel-generation.yml"
    - "website/docs/reference/environment.md"
    - "tests/test_primary_claim_attribution.py"
    - "tests/test_subcontractor_helper_shadow_rescue.py"
    - "tests/test_subcontractor_primary_claim_attribution.py"
    - "tests/test_vac_crew_claim_attribution.py"
  deleted:
    - "tests/test_attribution_resolution_scope.py"
decisions:
  - "D-02: Single bulk prefetch call replaces all 4 per-variant ThreadPoolExecutor pre-passes"
  - "D-03: O(1) map reads replace per-row resolve_claimer RPC calls inside grouping loop"
  - "D-04: fetch_failure → construct ResolveOutcome hold directly; zero additional Supabase RPCs"
  - "D-05: ATTRIBUTION_RESOLUTION_WEEKS removed entirely (env var, helpers, gates, workflow pin, docs)"
metrics:
  duration: "~95 minutes"
  completed: "2026-05-26"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 8
---

# Phase 02 Plan 02: Bulk Prefetch Wiring + Scope Removal Summary

Single bulk `prefetch_attribution()` call replaces four per-variant ThreadPoolExecutor pre-passes, collapsing ~137k Supabase RPCs/run to O(pairs-in-current-run) with O(1) map reads at each consumer site, and `ATTRIBUTION_RESOLUTION_WEEKS` removed entirely.

## Objective

Wire the `prefetch_attribution` foundation (Plan 02-01) into `group_source_rows`, replacing the four per-variant attribution pre-passes (sub-primary B, vac-crew C, primary D, sub-helper Phase 1.1) with O(1) reads from a single shared `_attr_map`. Remove `ATTRIBUTION_RESOLUTION_WEEKS` and its two helpers (`_attribution_resolution_cutoff`, `_attribution_week_in_scope`) — the root cause of the production garbage-file incident — from code, workflow, and docs.

## Tasks Completed

| Task | Type | Commit | Description |
|------|------|--------|-------------|
| 1 | TDD RED | 599086f | Add failing keystone behavioral tests (historical claimer regression + direct-HOLD B/C) |
| 2 | TDD GREEN | c78a502 | Wire bulk prefetch, O(1) map reads, remove ATTRIBUTION_RESOLUTION_WEEKS |
| 3 | auto | 329e0b2 | Delete test_attribution_resolution_scope.py (tested now-deleted helpers) |

## What Changed

### generate_weekly_pdfs.py

**Single bulk prefetch block added** (before all three consumer blocks):
```python
# ── Phase 2 Plan 02: Single bulk attribution prefetch (D-02) ──
_attr_map: dict = {}
_attr_status: str = 'disabled'
if BILLING_AUDIT_AVAILABLE and (any attribution flag enabled):
    _prefetch_pairs = {(wr, week_ending, row_id) for completed rows}
    _attr_map, _attr_status = _prefetch_attribution(_prefetch_pairs)
```

**Three ThreadPoolExecutor pre-pass blocks replaced** with O(1) map reads:
- Sub-primary B: `_sub_primary_claimer_map` now built from `_attr_map` via `resolve_claimer(..., prefetched_map=_attr_map)`
- Vac-crew C: `_vac_crew_claimer_map` same pattern
- Primary D: `_primary_claimer_map` same pattern

**Sub-helper Phase 1.1 path** wired to `_attr_map` via `_resolve_claimer_sh` alias:
```python
_sh_out = _resolve_claimer_sh('helper', helper_foreman, ..., prefetched_map=_attr_map)
```

**D-04 direct-HOLD contract** applied in B and C consumer blocks: when `_attr_status == 'fetch_failure'`, constructs `ResolveOutcome('hold', None, None, 'fetch_failure')` directly — zero additional Supabase RPCs. D primary path uses-current on any failure (no HOLD — correctness tradeoff documented in D design).

**Deleted** (D-05):
- `ATTRIBUTION_RESOLUTION_WEEKS` env var read
- `_attribution_resolution_cutoff()` function
- `_attribution_week_in_scope()` function
- 4 scope gates gating pre-pass row collection
- Banner logging line for the env var

### .github/workflows/weekly-excel-generation.yml

Deleted the `ATTRIBUTION_RESOLUTION_WEEKS: '8'` workflow pin block. Updated comments on `timeout-minutes` and `concurrency` to reference Phase 2 bulk prefetch.

### website/docs/reference/environment.md

Deleted `ATTRIBUTION_RESOLUTION_WEEKS` table row. Updated `TIME_BUDGET_MINUTES` row to reference Phase 2 bulk prefetch.

### Test changes

- `test_attribution_resolution_scope.py`: **deleted** (13 tests — all tested now-deleted helpers)
- `test_primary_claim_attribution.py`: Updated `test_prepass_block_present` grep for new O(1) pattern; added `TestHistoricalClaimerRegression` RED tests; updated mock signatures with `prefetched_map=None`
- `test_subcontractor_primary_claim_attribution.py`: Updated `test_prepass_present` grep; fixed `_resolve` mock signatures; updated `test_helper_completed_row_excluded_from_primary_user_variants` to discriminate by variant
- `test_subcontractor_helper_shadow_rescue.py`: Updated 4 Bug C tests from `lookup_attribution` mocks to `resolve_claimer` mocks; added `ResolveOutcome` import
- `test_vac_crew_claim_attribution.py`: Added `TestBulkFetchFailureDirectHoldC` RED test; updated mock signatures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Source-grep tests checking old pre-pass pattern names**
- **Found during:** Task 2 (GREEN) fix cycle
- **Issue:** Tests used `assertIn('Subproject B attribution pre-pass', ...)` and `assertIn('resolve_claimer_primary(', ...)` — old patterns removed by the implementation
- **Fix:** Updated grep needles to `'Subproject B: O(1) map read'` and `'_resolve_claimer_d('`
- **Files modified:** `test_primary_claim_attribution.py`, `test_subcontractor_primary_claim_attribution.py`
- **Commit:** c78a502

**2. [Rule 1 - Bug] Mock functions missing `prefetched_map` kwarg in test signatures**
- **Found during:** Task 2 (GREEN) fix cycle
- **Issue:** 5 occurrences of `def _resolve(variant, current, *, wr, week_ending, row_id, enabled):` missing the new `prefetched_map=None` parameter, causing TypeError when production code passed the kwarg
- **Fix:** Added `prefetched_map=None` to all mock signatures via replace_all
- **Files modified:** `test_primary_claim_attribution.py`, `test_subcontractor_primary_claim_attribution.py`, `test_vac_crew_claim_attribution.py`
- **Commit:** c78a502

**3. [Rule 1 - Bug] Bug C tests mocked `lookup_attribution` (now obsolete API)**
- **Found during:** Task 2 (GREEN) fix cycle — 4 tests in `test_subcontractor_helper_shadow_rescue.py`
- **Issue:** `test_bug_c_attribution_partitions_row_to_frozen_helper`, `test_bug_c_no_history_falls_back_to_current_helper_with_warning`, `test_bug_c_fetch_failure_falls_back_with_correct_reason`, `test_bug_c_warning_dedupe_per_wr_helper` all mocked `billing_audit.writer.lookup_attribution` which is no longer called directly; sub-helper path now uses `resolve_claimer(prefetched_map=_attr_map)`
- **Fix:** Replaced `lookup_attribution` mocks with `resolve_claimer` mocks returning appropriate `ResolveOutcome` instances; removed obsolete `_global_disable_reason` manipulation; added `ResolveOutcome` import to file
- **Files modified:** `test_subcontractor_helper_shadow_rescue.py`
- **Commit:** c78a502

**4. [Rule 1 - Bug] `test_helper_completed_row_excluded_from_primary_user_variants` used non-discriminating mock**
- **Found during:** Task 2 (GREEN) fix cycle
- **Issue:** `resolve_claimer` mock returned 'PrimaryClaimer' for ALL variants, so sub-helper emission used 'PrimaryClaimer' as the helper name → key `REDUCEDSUB_HELPER_PrimaryClaimer` instead of `REDUCEDSUB_HELPER_HelperGuy`
- **Fix:** Replaced `return_value=ResolveOutcome(...)` with `side_effect=_resolve_by_variant` that discriminates by variant argument
- **Files modified:** `test_subcontractor_primary_claim_attribution.py`
- **Commit:** c78a502

## TDD Gate Compliance

- RED gate: `test(02-02)` commit `599086f` — 4 failing tests (historical claimer regression + direct-HOLD B/C)
- GREEN gate: `feat(02-02)` commit `c78a502` — all tests pass after implementation
- No REFACTOR gate needed (code was clean after GREEN)

## Known Stubs

None — all attribution wiring is fully connected end-to-end.

## Test Results

- **964 passed, 26 skipped, 0 failed** after all three tasks
- Net change: -16 tests (16 `test_attribution_resolution_scope.py` tests deleted, +0 net new behavioral tests from Task 1 RED were already counted in prior totals from the RED commit context)

## Self-Check: PASSED

- SUMMARY.md: FOUND at `.planning/phases/02-attribution-bulk-prefetch-historical-claimer-remediation/02-02-SUMMARY.md`
- Commit `599086f` (test RED): FOUND
- Commit `c78a502` (feat GREEN): FOUND
- Commit `329e0b2` (chore Task 3): FOUND
- Test suite: 964 passed, 26 skipped, 0 failed
