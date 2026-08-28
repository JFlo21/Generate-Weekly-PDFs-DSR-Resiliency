---
phase: 260812-isx
plan: 01
subsystem: billing-audit
tags: [python, unittest, smartsheet, billing, audit, rate-sanity]

# Dependency graph
requires:
  - phase: production (pipeline/pricing.py, data/subcontractor_rates.csv)
    provides: _SUBCONTRACTOR_RATES table, parse_price, _parse_quantity,
      the shortest-prefix Work Type matcher
provides:
  - Report-only rate-sanity detector on BillingAudit
    (_detect_rate_sanity_mismatches) flagging rows whose Units Total
    Price disagrees with New-Rates rate x Quantity
  - RATE_SANITY_AUDIT_ENABLED kill-switch
  - rate_sanity_mismatches / total_rate_sanity_mismatches /
    rate_sanity_skipped keys in the audit results and summary
affects: [billing-audit, investigate-price-anomaly skill, future audit-layer work]

# Actuals (#2632)
actuals:
  tokens: 8227
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Function-local lazy import of pipeline submodules from
       audit_billing_changes.py to avoid the generate_weekly_pdfs.py
       import-order hazard (audit_billing_changes is imported before
       pipeline.pricing)."
    - "Report-only audit detector shape: whole body wrapped in
       try/except, returns partial results on error, mirrors
       _detect_price_anomalies."

key-files:
  created:
    - tests/test_rate_sanity_audit.py
  modified:
    - audit_billing_changes.py
    - memory-bank/living-ledger.md

key-decisions:
  - "Imported _parse_quantity directly from pipeline.pricing (not via
     the generate_weekly_pdfs facade) because the facade does not
     re-export it (verified: hasattr is False) — kept the same
     function-local lazy-import pattern to avoid the import-order
     hazard."
  - "Combined Task 1 (tracer) and Task 2 (skip semantics / tolerance /
     kill-switch / summary) into one RED test commit and one GREEN
     implementation commit — the detector, tolerance check, and skip
     logic are one cohesive unit with no natural seam for a separately
     committable intermediate state."

patterns-established:
  - "Rate-sanity tolerance formula: max($0.02 flat, 0.5% of expected)
     — reusable for any future expected-vs-actual price sanity check."

requirements-completed: [QUICK-260812-ISX]

coverage:
  - id: D1
    description: "Detector flags the SAA-DE-20 incident row (qty 3,
      $341.04) with expected_price 170.52 and delta 170.52"
    requirement: "QUICK-260812-ISX"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityIncidentRegression::test_incident_row_is_flagged"
        status: pass
    human_judgment: false
  - id: D2
    description: "Clean row (qty 1, $56.84) is not flagged"
    requirement: "QUICK-260812-ISX"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityIncidentRegression::test_clean_row_is_not_flagged"
        status: pass
    human_judgment: false
  - id: D3
    description: "Missing CU, zero/missing/unparseable quantity,
      unparseable/empty price, and unknown work type are skipped and
      counted, never flagged"
    requirement: "QUICK-260812-ISX"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanitySkipsAndTolerance (10 skip-class tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tolerance is max($0.02, 0.5% of expected)"
    requirement: "QUICK-260812-ISX"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanitySkipsAndTolerance (3 tolerance-boundary tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "audit_financial_data wires the detector end-to-end
      and never mutates rows/pricing/grouping/hashing/upload"
    requirement: "QUICK-260812-ISX"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityEndToEndWiring::test_audit_financial_data_surfaces_mismatch"
        status: pass
      - kind: unit
        ref: "pytest tests/ -v (full suite, 1228 passed, 130 subtests passed, no regressions)"
        status: pass
    human_judgment: false
  - id: D6
    description: "RATE_SANITY_AUDIT_ENABLED=false restores pre-change
      audit summary shape"
    requirement: "QUICK-260812-ISX"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanitySkipsAndTolerance::test_kill_switch_disables_detector"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanitySummary::test_kill_switch_zeroes_summary_counter"
        status: pass
    human_judgment: false
  - id: D7
    description: "Living Ledger carries a new dated entry documenting
      the detector"
    requirement: "QUICK-260812-ISX"
    verification: []
    human_judgment: true
    rationale: "Prose-quality ledger entry — content correctness
      judged by review, not an automated test."

# Metrics
duration: ~35min
completed: 2026-08-12
status: complete
---

# Quick Task 260812-isx: Report-Only Rate-Sanity Audit Check Summary

**Report-only rate-sanity detector in `audit_billing_changes.py` flags Smartsheet `Units Total Price` vs `New Rates rate x Quantity` mismatches (keyed by CU + Work Type, `max($0.02, 0.5%)` tolerance) — catches the SAA-DE-20 stale-quantity-formula overbill class automatically without touching any pricing path.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-08-12T18:20:00Z (approx.)
- **Completed:** 2026-08-12T18:54:49Z
- **Tasks:** 3/3 completed
- **Files modified:** 3 (`audit_billing_changes.py`, `tests/test_rate_sanity_audit.py`, `memory-bank/living-ledger.md`)

## Accomplishments

- New `_detect_rate_sanity_mismatches()` method on `BillingAudit`, wired into `audit_financial_data()` as a report-only step, flags rows whose `Units Total Price` disagrees with `(New Rates rate x Quantity)` by more than `max($0.02, 0.5% of expected)`.
- Reproduces the SAA-DE-20 incident exactly: qty 3 / $341.04 -> `expected_price` 170.52, `actual_price` 341.04, `delta` 170.52.
- Skip classes (missing CU, unknown work type, non-positive/unparseable quantity, empty/unparseable price) are silently counted (`_rate_sanity_skipped`) and logged once per run as an aggregate count — never per-row, never with price/quantity/foreman detail (T-ISX-01).
- `RATE_SANITY_AUDIT_ENABLED` kill-switch (default `true`), read per-call.
- Summary gains `total_rate_sanity_mismatches` and `rate_sanity_skipped`, folded into the existing `total_issues` -> `risk_level` escalation.
- Zero changes to `pipeline/`, `generate_weekly_pdfs.py`, pricing, grouping, hashing, filenames, or upload behavior (diff guard confirmed — see Verification below).
- Dated Living Ledger entry `[2026-08-12 14:05]` documents the rule.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1 + Task 2 combined (tracer + skip/tolerance/kill-switch/summary):**
   - `a7f5d77` (test) — RED: 20 failing tests covering the incident regression, clean case, end-to-end wiring, all skip classes, tolerance boundaries, decorated-quantity parsing, kill-switch, and summary counters.
   - `2cb9897` (feat) — GREEN: full detector implementation; all 20 tests pass.
2. **Task 3: Full-suite regression gate and Living Ledger entry:**
   - `ad3fa19` (docs) — dated `[2026-08-12 14:05]` Living Ledger entry, appended below the pre-existing `[2026-08-12 13:40]` incident entry.

_Note: Task 1 (`tracer`, tdd) and Task 2 (`auto`, tdd) were implemented together in one RED/GREEN pair — see Deviations below._

## Files Created/Modified

- `audit_billing_changes.py` — module-level `RATE_SANITY_ABS_TOLERANCE`/`RATE_SANITY_PCT_TOLERANCE` constants, `_rate_sanity_expected_price()`, `_rate_sanity_is_mismatch()`, `_rate_sanity_looks_like_zero()` helpers, `BillingAudit._detect_rate_sanity_mismatches()` method, wiring into `audit_financial_data()`, `_generate_audit_summary()`, and `_log_audit_results()`.
- `tests/test_rate_sanity_audit.py` — new file, 20 unittest cases across 5 test classes (incident regression, end-to-end wiring, skips/tolerance/kill-switch, summary).
- `memory-bank/living-ledger.md` — new dated entry `[2026-08-12 14:05]` documenting the detector (appended below the orchestrator's pre-existing `[2026-08-12 13:40]` incident entry, per instructions, without duplicating that narrative).

## Decisions Made

- **Imported `_parse_quantity` directly from `pipeline.pricing`, not via `_gwp._parse_quantity`.** The plan's design_facts specified reading it off the `generate_weekly_pdfs` facade, but verification (`hasattr(generate_weekly_pdfs, '_parse_quantity')`) showed it is `False` — the facade's static re-export block only carries `_SUBCONTRACTOR_RATES` and `parse_price` from `pipeline.pricing`, and `_parse_quantity` is not one of the 4 PEP-562 live-proxy names either. Fixed by importing it directly from `pipeline.pricing` inside the same function-local lazy-import block, which is safe: the import only executes when the detector runs (well after `generate_weekly_pdfs.py` has already imported `pipeline.pricing` at L196-210), so the import-order hazard the plan's design_facts #4 warns about does not apply to a call-time import regardless of which module it targets.
- **Combined Task 1 and Task 2 into a single TDD pass.** Both tasks operate on the same method/helpers with no natural intermediate "working but incomplete" state to commit separately — writing all 20 tests up front (RED) and then implementing the full detector (GREEN) in one pass was more honest than fabricating an artificial split. Task 3's ledger entry stayed a separate commit as planned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_gwp._parse_quantity` does not exist on the facade**
- **Found during:** Task 1 (writing the `_rate_sanity_expected_price` helper)
- **Issue:** design_facts and the task action text both specified `_gwp._parse_quantity(row.get('Quantity'))`, but `generate_weekly_pdfs.py`'s static `from pipeline.pricing import (...)` block (L189-213) only re-exports `parse_price`, not `_parse_quantity`; nor is it one of the 4 PEP-562 live-proxy names (`SUBCONTRACTOR_SHEET_IDS`, `_FOLDER_DISCOVERED_SUB_IDS`, `_FOLDER_DISCOVERED_ORIG_IDS`, `_RATES_FINGERPRINT`). Calling `_gwp._parse_quantity` would raise `AttributeError` at runtime.
- **Fix:** Function-local `from pipeline.pricing import _parse_quantity` alongside the existing `import generate_weekly_pdfs as _gwp` lazy import, in both `_rate_sanity_expected_price()` and `_detect_rate_sanity_mismatches()`. Verified safe (no import-cycle reintroduction) because it executes only at call time.
- **Files modified:** `audit_billing_changes.py`
- **Verification:** `python -c "import generate_weekly_pdfs as g; hasattr(g, '_parse_quantity')"` -> `False` (confirms the gap); all 20 new tests pass with the fix; full suite (1228 tests) passes.
- **Committed in:** `2cb9897` (Task 1+2 feat commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — Rule 3)
**Impact on plan:** Necessary correctness fix; the plan's intended behavior (parse quantity via the shared helper) is preserved exactly, only the import path changed. No scope creep — `git diff --stat` still shows exactly the three planned files.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None — no external service configuration required.

## Verification

- `pytest tests/test_rate_sanity_audit.py -v` — 20/20 passed.
- `pytest tests/ -v` (full suite) — **1228 passed, 130 subtests passed** in 13.80s. No regressions in `tests/test_billing_audit_shadow.py` or `tests/test_subcontractor_pricing.py` (neither file references `audit_billing_changes.py`/`BillingAudit` directly, and neither broke).
- `python -m py_compile audit_billing_changes.py` — exits 0.
- `git diff --stat a5cf378..HEAD -- . ':!.claude' ':!.serena' ':!.planning'` — confirms exactly 3 files changed: `audit_billing_changes.py`, `tests/test_rate_sanity_audit.py`, `memory-bank/living-ledger.md`. No hunks in `pipeline/` or `generate_weekly_pdfs.py`.

### pytest tail (full suite)

```
================= 1228 passed, 130 subtests passed in 13.80s ==================
```

## Next Phase Readiness

- The detector is live and default-on (`RATE_SANITY_AUDIT_ENABLED=true` by default); no further action required to activate it in production.
- Optional local smoke test (not run in this session, per the plan's "Optional" verification item):
  `SKIP_UPLOAD=true WR_FILTER=16881353 python generate_weekly_pdfs.py` — would confirm the live audit section reports the (now-corrected, per the 13:40 incident entry) WR 16881353 row without changing any generated price. Left for an operator/next session to run against live Smartsheet data if desired.
- No blockers.

---
*Phase: 260812-isx*
*Completed: 2026-08-12*
