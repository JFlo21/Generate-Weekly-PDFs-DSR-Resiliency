---
phase: 13-audit-memory
plan: 02
subsystem: billing_audit
tags: [mypy, gate-4, snapshot_store, provenance, todos, technical-debt]

# Dependency graph
requires:
  - phase: 09-engine-modularization-pipeline-package-split
    provides: the frozen Gate-4 mypy baseline/count contract and the re-baseline hygiene rule this plan follows
  - phase: 10-run-memory-foundation-shadow-writes
    provides: run_ledger_finish and the WR-04 sheets_changed follow-up this plan verifies (already landed in Phase 11)
provides:
  - A narrowing guard in billing_audit/snapshot_store.py's fetch_snapshot_provenance that removes the Class-A mypy arg-type finding at snapshot_store.py:370, with 4 regression tests pinning behavior unchanged
  - Gate-4 mypy baseline lowered by exactly one line (71 -> 70), documented in the Living Ledger per the re-baseline hygiene rule
  - Two folded Phase 10/09 review todos closed with evidence; the Gate-4 hardening todo explicitly deferred with a dated note
affects: [13-audit-memory (remaining plans), any future Gate-4 re-baseline]

# Actuals (#2632)
actuals:
  tokens: 3644
  tasks: 3
  commits: 4
plan_head_before: 7a7adf095085780a52d8f579641f5c8a963c54b3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Narrow-before-cast guard: read dict.get() results into locals and skip on None BEFORE the int() cast, keeping the surrounding except (TypeError, ValueError) as the non-numeric backstop -- satisfies mypy without changing runtime behavior"
    - "Re-baseline hygiene: a Gate-4 baseline change is its own commit, removes exactly the accepted lines, and the ledger entry names them"

key-files:
  created: []
  modified:
    - billing_audit/snapshot_store.py
    - tests/test_snapshot_store.py
    - tests/golden/mypy_baseline.txt
    - tests/golden/mypy_baseline_count.txt
    - memory-bank/living-ledger.md
    - .planning/todos/pending/2026-08-25-run-memory-review-followups.md (moved to done/)
    - .planning/todos/pending/2026-08-25-fix-snapshot-store-int-arg-type.md (moved to done/)
    - .planning/todos/pending/2026-08-25-harden-check-mypy-delta-followups.md

key-decisions:
  - "The provenance-row key guard is a static-typing narrowing only, not a behavior fix -- the runtime skip for a missing/None/non-numeric sheet_id or row_id already held via the pre-existing except (TypeError, ValueError): continue"
  - "AUD-01 (this plan's declared requirement) is shared with sibling Phase 13 plans and is NOT marked complete here -- gsd-tools requirements.ready-ids confirmed 0/1 ready, so the shared-ID gate correctly withholds it until every declaring plan finishes"

patterns-established:
  - "Re-baseline hygiene rule applied exactly: one dedicated commit, exactly the accepted lines removed, ledger entry naming them"

requirements-completed: []

coverage:
  - id: D1
    description: "Narrowing guard added before the int() cast in billing_audit/snapshot_store.py's provenance key construction; behavior preserved and pinned by 4 new regression tests"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_snapshot_store.py#TestFetchSnapshotProvenanceKeyGuard"
        status: pass
      - kind: unit
        ref: "python -m pytest tests/ -q (2342 passed, 1 skipped)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Gate-4 mypy baseline re-baselined by exactly one line (71 -> 70) with a dated Living Ledger entry naming the removed line"
    verification:
      - kind: integration
        ref: "bash scripts/run_6_gates.sh (all 6 gates PASS, Gate 4: 70 -> 70)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Phase 10 review (WR-04/IN-01) and snapshot-store mypy todos closed with evidence; Gate-4 hardening todo explicitly deferred"
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::RunLedgerSheetsChangedCallSiteTests::test_both_finish_call_sites_pass_sheets_changed"
        status: pass
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::RunLedgerFailurePathTests::test_failure_path_finish_includes_sheets_changed"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-09-11
status: complete
---

# Phase 13 Plan 02: Snapshot-Store Mypy Fix and Folded Todo Closure Summary

**Narrowing guard removes the Class-A mypy arg-type finding in `billing_audit/snapshot_store.py`, Gate-4 baseline drops 71 -> 70 with a ledger entry, and two Phase 09/10 review todos close with evidence while the Gate-4 hardening todo is explicitly deferred.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-09-11T22:41:30Z
- **Completed:** 2026-09-11T22:55:06Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- Narrowed the provenance-row key construction in `fetch_snapshot_provenance` (`billing_audit/snapshot_store.py`) with an explicit `None` guard before the `int()` cast, removing the only Class-A mypy `arg-type` finding accepted into the 2026-08-25 Gate-4 re-baseline, with runtime behavior byte-for-byte preserved
- Added 4 regression tests (`TestFetchSnapshotProvenanceKeyGuard`) pinning the missing-key, `None` row_id, non-numeric, and well-formed-match cases
- Lowered `tests/golden/mypy_baseline.txt` / `tests/golden/mypy_baseline_count.txt` by exactly one line (71 -> 70) and recorded a dated Living Ledger entry naming the removed line, per the re-baseline hygiene rule
- Verified WR-04 (`run_ledger.sheets_changed`) was already landed in Phase 11 (both `run_ledger_finish` call sites, the `_RUN_LEDGER_FINISH_COLUMNS` contract, and existing test pins) and closed the Phase 10 review + snapshot-store todos to `done/` with dated evidence notes
- Left the Gate-4 hardening todo in `pending/` with a dated deferral note per the `13-CONTEXT.md` Folded Todos authorization

## Task Commits

Each task was committed atomically:

1. **Task 1: Narrow the provenance-row key before the int cast** - `5adebb0` (test) + `ac253c9` (fix)
2. **Task 2: Re-baseline mypy by exactly one line and record it in the ledger** - `b210481` (docs)
3. **Task 3: Close the Phase 10 review todo and record the Gate-4 deferral** - `fe33111` (docs)

_Note: Task 1 followed the TDD-style test-then-fix commit pattern even though the RED phase was unexpectedly green — see Deviations below._

## Files Created/Modified
- `billing_audit/snapshot_store.py` - Narrowing guard before the provenance key `int()` cast
- `tests/test_snapshot_store.py` - New `TestFetchSnapshotProvenanceKeyGuard` regression class (4 tests)
- `tests/golden/mypy_baseline.txt` - One `arg-type` line removed (71 -> 70 lines)
- `tests/golden/mypy_baseline_count.txt` - `71` -> `70`
- `memory-bank/living-ledger.md` - Dated entry naming the removed baseline line and count change
- `.planning/todos/done/2026-08-25-run-memory-review-followups.md` - Moved from `pending/`, dated closure note added
- `.planning/todos/done/2026-08-25-fix-snapshot-store-int-arg-type.md` - Moved from `pending/`, Resolution section added
- `.planning/todos/pending/2026-08-25-harden-check-mypy-delta-followups.md` - Dated deferral note added, stays in `pending/`

## Decisions Made
- The guard is a pure static-typing narrowing (mypy compliance), not a runtime behavior change — the `except (TypeError, ValueError): continue` already skipped the same rows today. Documented explicitly per the task's own "preserving behavior exactly" requirement.
- AUD-01 was **not** marked complete via `requirements.mark-complete` — `gsd-tools requirements.ready-ids` confirmed 0/1 ready (shared with sibling Phase 13 plans still in progress), so the shared-ID gate correctly withholds it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Investigation, not a defect] Unexpected GREEN in the RED phase for Task 1**
- **Found during:** Task 1 (narrowing guard)
- **Issue:** Per the TDD fail-fast rule ("Unexpected GREEN in RED phase: STOP and investigate"), the 4 new regression tests were run against the pre-guard file first and all 4 already passed. Investigation confirmed this is expected: the existing `except (TypeError, ValueError): continue` around the `int()` cast already produced the exact same runtime skip for a missing/`None`/non-numeric `sheet_id`/`row_id` — the guard only removes the static `Any | None` argument type mypy flags, it was never intended to change runtime behavior (explicitly stated in the plan's own `<action>` text). This is a legitimate mypy-only fix, not a functional bug, so RED-then-GREEN in the classic behavior-change sense does not apply; the test-then-fix commit split was kept for traceability regardless.
- **Fix:** None needed — proceeded with the guard exactly as specified in the plan, confirmed the diff stays scoped to the key-construction block, and confirmed all 42 scoped tests plus the full 2342-test suite pass after the change.
- **Files modified:** None beyond the plan's own scope.
- **Verification:** `python -m pytest tests/test_snapshot_store.py -q` — 38 passed pre-guard (baseline), 4 new tests also passed pre-guard (investigated, expected), 42 passed post-guard; `python -m pytest tests/ -q` — 2342 passed, 1 skipped, both before and after.
- **Committed in:** `5adebb0` (test), `ac253c9` (fix)

---

**Total deviations:** 1 investigated (no code change needed beyond the plan's own scope)
**Impact on plan:** None — the guard, tests, re-baseline, and todo closures all landed exactly as the plan specified. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Gate-4 mypy baseline is clean at 70 lines with the Class-A finding gone; `bash scripts/run_6_gates.sh` green.
- All three folded Phase 13 todos are resolved: two closed with evidence, one explicitly deferred and traceable.
- No blockers for the remaining Phase 13 plans (13-01, 13-03..13-06) building the `audit_finding` / `audit_finding_event` schema — this plan touched none of `pipeline_memory/`, `pipeline/`, or `audit_billing_changes.py`.

## Self-Check: PASSED

- `[ -f billing_audit/snapshot_store.py ]` — FOUND
- `[ -f tests/test_snapshot_store.py ]` — FOUND
- `[ -f tests/golden/mypy_baseline.txt ]` — FOUND
- `[ -f tests/golden/mypy_baseline_count.txt ]` — FOUND
- `[ -f memory-bank/living-ledger.md ]` — FOUND
- `[ -f .planning/todos/done/2026-08-25-run-memory-review-followups.md ]` — FOUND
- `[ -f .planning/todos/done/2026-08-25-fix-snapshot-store-int-arg-type.md ]` — FOUND
- `[ -f .planning/todos/pending/2026-08-25-harden-check-mypy-delta-followups.md ]` — FOUND
- `git log --oneline --all --grep="13-02"` returns 4 commits: `5adebb0`, `ac253c9`, `b210481`, `fe33111` — FOUND
- Re-ran all task `<acceptance_criteria>` — all PASS (see Task Commits / Accomplishments above)
- Re-ran plan-level `<verification>`: `python -m pytest tests/ -q` (2342 passed, 1 skipped), `bash scripts/run_6_gates.sh` (ALL 6 GATES PASSED), `cat tests/golden/mypy_baseline_count.txt` (70), both closed todos in `done/`, Gate-4 hardening todo in `pending/` with deferral note — all PASS

---
*Phase: 13-audit-memory*
*Completed: 2026-09-11*
