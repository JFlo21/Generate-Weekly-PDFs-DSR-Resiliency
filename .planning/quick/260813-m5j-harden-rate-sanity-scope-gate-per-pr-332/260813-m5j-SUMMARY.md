---
phase: quick/260813-m5j
plan: 01
subsystem: billing-audit
tags: [audit, rate-sanity, scope-gate, tdd, python]

# Dependency graph
requires:
  - phase: quick/260812-isx
    provides: report-only rate-sanity mismatch detector (audit_billing_changes.py)
  - phase: PR #332
    provides: current-cycle scope gate (_rate_sanity_in_scope, out-of-scope counter)
provides:
  - Corrected-polarity subcontractor exclusion (F2) in the rate-sanity scope gate
  - Sheet-gated Weekly-Ref-Date fallback (F1), fail-closed on unknown sheets
  - _rate_sanity_snapshot_column_index() helper (built once per call)
  - Per-reason out-of-scope breakdown (_rate_sanity_out_of_scope_by_reason)
  - 10 new regression tests (R1-R10) pinning both fixes and the VAC decision
affects: [billing-audit, rate-sanity-detector, incident-guardrails]

# Actuals (#2632)
actuals:
  tokens: 7111
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scope gate returns (bool, reason) tuple instead of bare bool so out-of-scope reasons are traceable without a second lookup"
    - "Column-presence index built once per detector call (O(sheets)), not per row (O(rows))"

key-files:
  created: []
  modified:
    - audit_billing_changes.py
    - tests/test_rate_sanity_audit.py
    - memory-bank/living-ledger.md

key-decisions:
  - "F2 literal finding (restrict scope TO subcontractor rows) REJECTED after research -- the SAA-DE-20 incident sheet is one of 110 non-subcontractor ProMax sheets; the corrected polarity excludes subcontractor rows instead"
  - "VAC-crew rows on non-subcontractor sheets stay IN scope (pass-through New-Rates basis, same as primary rows) -- pinned by test R4, not defaulted"
  - "out_of_scope reason breakdown is additive only -- the rate_sanity_out_of_scope summary key and running total keep their original name/semantics"

patterns-established:
  - "Sheet-metadata scope gates should be built as a single O(sheets) index per call, keyed by sheet id, rather than looked up per row"

requirements-completed: [F1, F2]

coverage:
  - id: D1
    description: "F1 closed: Weekly Reference Logged Date fallback only applies when the row's own sheet maps a Snapshot Date column; unknown sheet or absent metadata falls closed to snapshot-only"
    requirement: "F1"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r6_fallback_disabled_without_snapshot_column_mapping"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r7_fallback_enabled_when_sheet_maps_snapshot_column"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r8_unknown_sheet_fails_closed"
        status: pass
    human_judgment: false
  - id: D2
    description: "F2 closed with corrected polarity: __is_subcontractor rows excluded (reason subcontractor_basis); non-subcontractor rows, including the SAA-DE-20 incident row, remain in scope"
    requirement: "F2"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r1_incident_row_survives_f2_fix"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r2_subcontractor_row_at_sub_rate_is_out_of_scope"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r3_subcontractor_row_that_would_mismatch_is_excluded"
        status: pass
    human_judgment: false
  - id: D3
    description: "VAC-crew rows on non-subcontractor sheets remain in scope (Q5 decision), VAC rows on subcontractor sheets excluded automatically"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r4_vac_row_on_non_subcontractor_sheet_stays_in_scope"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r5_vac_row_on_subcontractor_sheet_is_out_of_scope"
        status: pass
    human_judgment: false
  - id: D4
    description: "rate_sanity_out_of_scope summary key and running total unchanged; per-reason breakdown added and sums correctly; legacy no-source_sheets call shape still works"
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r10_out_of_scope_counter_equals_reason_breakdown_sum"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py::TestRateSanityScopeHardening::test_r9_legacy_call_shape_without_source_sheets"
        status: pass
      - kind: unit
        ref: "python -m pytest tests/ -q"
        status: pass
    human_judgment: false

# Metrics
duration: 6min
completed: 2026-08-13
status: complete
---

# Quick Task 260813-m5j: Harden rate-sanity scope gate (PR #332 review) Summary

**Corrected the rate-sanity scope gate's F2 exclusion polarity (subcontractor rows OUT, not IN) and sheet-gated the F1 Weekly-Ref-Date fallback on Snapshot Date column presence, keeping the SAA-DE-20 incident class in scope.**

## Performance

- **Duration:** ~6 min (commit span 16:18:24 -> 16:23:28)
- **Tasks:** 3
- **Files modified:** 3 (`audit_billing_changes.py`, `tests/test_rate_sanity_audit.py`, `memory-bank/living-ledger.md`)

## Accomplishments
- Fixed F1 (Codex P1): `_rate_sanity_in_scope` now gates the Weekly Reference
  Logged Date fallback on whether the row's own sheet maps a Snapshot Date
  column (new `_rate_sanity_snapshot_column_index()` helper, built once per
  call from `source_sheets['column_mapping']`), mirroring
  `pipeline/fetch.py:276` exactly. Unknown sheet / absent metadata now fails
  closed to snapshot-only scoring.
- Fixed F2 with corrected polarity (research rejected the literal PR #332
  finding): `__is_subcontractor` rows are now excluded (reason
  `subcontractor_basis`) because their `Units Total Price` sits at the
  Subcontractor-Rates basis, not the New-Rates basis the detector compares
  against. The gate deliberately does NOT restrict scope TO subcontractor
  rows -- the SAA-DE-20 incident sheet ("Resiliency Promax Database Backup
  86") is one of 110 non-subcontractor ProMax sheets in the 115-sheet
  discovery cache, so that restriction would have blinded the detector to
  the exact defect class it exists for.
- Extended (never replaced) the out-of-scope counters:
  `_rate_sanity_out_of_scope_by_reason: Dict[str, int]` breaks the existing
  `_rate_sanity_out_of_scope` total down into `subcontractor_basis` and
  `pre_cutoff_or_undated`; the aggregate INFO log line now reports both
  reason counts (counts only, per the T-ISX-01 PII rule).
- Wired the production call site (`audit_financial_data`) to pass
  `source_sheets` into `_detect_rate_sanity_mismatches`, so the fallback
  gate is populated in real runs, not just in tests.
- Added 10 new regression tests (`TestRateSanityScopeHardening`, R1-R10)
  driving the public `_detect_rate_sanity_mismatches(rows,
  source_sheets=...)` entry point, plus updated the 2 pre-existing scope
  tests that relied on the old default-`True` fallback to use explicit
  `source_sheets` metadata instead.
- Appended a dated Living Ledger entry recording all four durable rules for
  future engineers (subcontractor-exclusion polarity, sheet-gated fallback,
  VAC-in-scope decision, frozen summary key contract).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED -- regression tests for the corrected scope gate** - `4245450` (test)
2. **Task 2: GREEN -- snapshot-column index + corrected scope gate + counter extension** - `a7c27b2` (feat)
3. **Task 3: Full-suite validation + Living Ledger entry** - `63c38c7` (docs)

**Plan metadata:** committed separately by the orchestrator (docs artifacts excluded from this executor's commits per task instructions).

_TDD gate sequence verified: `test(...)` -> `feat(...)` -> `docs(...)` in git log, in that order._

## Files Created/Modified
- `audit_billing_changes.py` - Added `_rate_sanity_snapshot_column_index()`; changed `_rate_sanity_in_scope()` to return `Tuple[bool, str]` with the corrected F2 polarity checked first and F1's sheet-gated fallback second; extended `_detect_rate_sanity_mismatches()` with an optional `source_sheets` kwarg and the per-reason counter; wired the production call site; extended the aggregate INFO log line
- `tests/test_rate_sanity_audit.py` - Added `TestRateSanityScopeHardening` (10 new tests, R1-R10); updated `test_blank_snapshot_with_post_cutoff_weekly_is_in_scope` and `test_pre_cutoff_snapshot_does_not_fall_back_to_weekly` to supply explicit `source_sheets` metadata instead of relying on the old default-enabled fallback
- `memory-bank/living-ledger.md` - Appended `[2026-08-13 16:45]` entry documenting the corrected polarity, the sheet-gated fallback, the VAC-in-scope decision, and the frozen summary-key contract

## Decisions Made
- **F2 polarity correction locked in:** subcontractor rows are excluded from
  the detector; scope is never restricted TO subcontractor rows. Re-flipping
  this without re-verifying the incident sheet's folder family against
  `generated_docs/discovery_cache.json` would silently regress detector
  coverage to zero for the defect class it exists for.
- **VAC-crew rows on non-subcontractor sheets stay in scope** (pinned by
  test R4) because they bill via the same pass-through New-Rates basis as
  primary rows -- there is no basis mismatch to justify excluding them.
- **`rate_sanity_out_of_scope` stays a frozen summary key.** The per-reason
  breakdown is purely additive (new instance attribute + log line detail),
  never a rename or replacement of the existing counter.

## Deviations from Plan

None - plan executed exactly as written. The recommended design from
`260813-m5j-RESEARCH.md` ("Recommended design (ONE gate, no new plumbing)")
was implemented essentially verbatim, including the exact function
signatures, docstring citations, and wiring points it specified.

## Issues Encountered

None. The RED phase (Task 1) produced the expected failure set: 8 of the
10 new R-tests failed with either `TypeError` (unsupported `source_sheets`
kwarg) or `AssertionError` (F2 not yet implemented); R4 and R9 passed
immediately because they pin behavior that was already correct before this
change (VAC rows were already in scope; the legacy no-`source_sheets` call
shape already worked). This matched the plan's documented RED expectations
exactly.

## User Setup Required

None - no external service configuration required. Report-only audit
change; no new env var, no `pipeline/` edit, `RATE_SANITY_AUDIT_ENABLED`
kill switch untouched.

## Next Phase Readiness

- The rate-sanity detector's scope gate is now hardened against both PR
  #332 review findings while preserving full incident-class coverage.
- Full pytest suite green (1284 passed, 132 subtests) after the change.
- Blast radius confirmed limited to `audit_billing_changes.py`,
  `tests/test_rate_sanity_audit.py`, and `memory-bank/living-ledger.md`
  (`git diff --name-only master..HEAD`).
- No blockers. Ready for PR review / merge to `master`.

---
*Phase: quick/260813-m5j*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 3 modified files confirmed present on disk; all 3 task commits
(`4245450`, `a7c27b2`, `63c38c7`) confirmed present in `git log --oneline
--all`.
