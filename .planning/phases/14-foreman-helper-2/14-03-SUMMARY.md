---
phase: 14-foreman-helper-2
plan: 03
subsystem: billing-audit
tags: [python, supabase-rpc, attribution, postgrest, tdd]

# Dependency graph
requires:
  - phase: 14-foreman-helper-2
    provides: "plan 14-01's `__helper2_foreman` / `__helper2_dept` row keys written by the pipeline tracer"
provides:
  - "`p_helper2` in the freeze_attribution RPC payload, joined to the all-sentinel gate in the same edit"
  - "Per-process Helper #2 RPC capability flag with one-time PGRST202 probe-and-degrade (D-14-07a)"
  - "`helper2_attribution_degraded` run_summary counter, golden-pinned at 25 keys"
  - "Three ROLE_BY_VARIANT entries (helper2, reduced_sub_helper2, aep_billable_helper2) resolving to the `helper2` role"
affects: [14-06, 14-09]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 9962
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Separate frozenset for a new sentinel value (`_HELPER2_SENTINEL_CLAIMERS`) instead of widening a pinned literal set that a SQL-twin parity test asserts against"
    - "Reuse an already-typed module-level exception/classifier (`billing_audit.client._PGAPIError`, `_classify_postgrest_error`) instead of re-declaring a local `try/except ImportError` type-reassignment idiom, to avoid a new mypy finding"
    - "Per-process capability flag + one-time bounded probe to detect a not-yet-migrated Supabase RPC signature (PGRST202) and degrade gracefully, mirroring the existing `prefetch_attribution` `rpc_missing` probe idiom"

key-files:
  created: []
  modified:
    - billing_audit/writer.py
    - tests/test_billing_audit_shadow.py
    - tests/golden/run_summary_baseline.json
    - pipeline/orchestrate.py
    - tests/test_parity_shadow.py
    - tests/test_incremental_read.py

key-decisions:
  - "Added `_HELPER2_SENTINEL_CLAIMERS` as a separate frozenset ORed into `is_sentinel_claimer`, rather than adding `unknown helper 2` directly to `_SENTINEL_CLAIMERS`, because a SQL-twin parity test (`test_own03_backfill_sql_contract.py`) asserts every value in `_SENTINEL_CLAIMERS` appears in `own03_backfill_attribution.sql`, which this plan prohibits touching."
  - "Reused `billing_audit.client`'s existing `_PGAPIError` / `_classify_postgrest_error` for the PGRST202 capability probe instead of a local `try: from postgrest import APIError ... except: _APIError = ()` fallback, which introduced an extra unsuppressed mypy `[misc]` finding at that call site."
  - "Updated 3 pre-existing pinned golden key-count assertions (test_parity_shadow.py, test_incremental_read.py x2) from 24 to 25 — direct, foreseeable consequence of the new `helper2_attribution_degraded` counter key."
  - "Added the new counter key to both of `pipeline/orchestrate.py`'s pre-seed dicts (TEST_MODE synthetic path and the production path) after Gate 6 proved the synthetic path builds its own summary dict independent of `get_counters()` and was missing the key."

requirements-completed: [HLP-02, HLP-05, HLP-06]

coverage:
  - id: D1
    description: "A Helper #2-only real claim (primary/helper/vac_crew blank or sentinel) still invokes freeze_attribution instead of being silently classified as fully sentinel"
    requirement: "HLP-05"
    verification:
      - kind: unit
        ref: "tests/test_billing_audit_shadow.py#FreezeRowHelper2Tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Graceful degrade when the deployed RPC does not yet accept Helper #2 parameters: one warning, one retry without those parameters, no crash, no lost primary/helper freeze"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_billing_audit_shadow.py#FreezeRowHelper2DegradeTests"
        status: pass
    human_judgment: false
  - id: D3
    description: "resolve_claimer reads the helper2 role for the three Helper #2 variants, never primary_foreman, and the pre-migration RPC shape (no helper2 key) lands on no_history, not a KeyError or fall-through"
    requirement: "HLP-02"
    verification:
      - kind: unit
        ref: "tests/test_billing_audit_shadow.py#TestResolveClaimerHelper2"
        status: pass
    human_judgment: false
  - id: D4
    description: "Deployed function BODY behavior (does the migrated RPC actually persist and never overwrite frozen_helper) is NOT verified here — repository-side proof only"
    verification: []
    human_judgment: true
    rationale: "14-RESEARCH.md Assumption A4: the freeze_attribution function body lives in Supabase, not this repo, and cannot be proven from a repository read. This plan proves the Python side sends correct parameters and never suppresses a Helper #2-only freeze; the post-migration read-back check is plan 14-09's owner-verified step."

duration: 40min
completed: 2026-09-07
status: complete
---

# Phase 14 Plan 03: Helper #2 Attribution Wiring Summary

**`p_helper2` closes the all-sentinel silent-drop gate, degrades gracefully against the un-migrated Supabase RPC via a PGRST202 capability probe, and gives Helper #2 its own resolve_claimer role — all proven by 16 new fixture-only tests.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-09-06T18:32:00-05:00 (approx, per session continuity log)
- **Completed:** 2026-09-06T19:10:00-05:00
- **Tasks:** 3
- **Files modified:** 6 (3 in plan scope, 3 deviation)

## Accomplishments
- `p_helper2` computed via `_null_if_named_sentinel(row.get("__helper2_foreman"))` and joined to the all-sentinel `all(is_sentinel_claimer(v) for v in (...))` gate in the SAME edit, closing the single most dangerous silent-drop this phase could create
- `_HELPER2_SENTINEL_CLAIMERS` frozenset recognizes `unknown helper 2` as a placeholder without touching the SQL-twin-pinned `_SENTINEL_CLAIMERS`
- Per-process `_helper2_rpc_unsupported` capability flag: on first PGRST202 rejection, logs once, retries without Helper #2 parameters, bumps `helper2_attribution_degraded`; every subsequent freeze in the run skips the parameters without re-probing or re-logging
- Three `ROLE_BY_VARIANT` entries (`helper2`, `reduced_sub_helper2`, `aep_billable_helper2`) resolve to the `helper2` role; the pre-migration RPC shape (no `helper2` key) correctly lands on `resolve_claimer`'s `no_history` branch, never a `KeyError` and never a silent `primary_foreman` fall-through
- 16 new test methods across 3 test classes (`FreezeRowHelper2Tests`, `FreezeRowHelper2DegradeTests`, `TestResolveClaimerHelper2`); full suite grew from 2140 to 2156 passed (1 skipped), all 6 gates pass

## Task Commits

Each task was committed atomically:

1. **Task 1: p_helper2 joins the freeze payload AND the all-sentinel gate** - `7509709` (feat)
2. **Task 2: Degrade cleanly while the Supabase migration has not landed** - `5c44d49` (feat)
3. **Task 3: The Helper #2 role in ROLE_BY_VARIANT and resolve_claimer** - `58d73d2` (feat)

**Plan metadata:** (pending final commit)

_Note: All 3 tasks were `tdd="true"` — tests were written first per the `<behavior>` list in each task, then the implementation edit made them pass, all within a single commit per task._

## Files Created/Modified
- `billing_audit/writer.py` - `p_helper2`/`p_helper2_dept`, `_HELPER2_SENTINEL_CLAIMERS`, capability flag + PGRST202 probe/degrade, `helper2_attribution_degraded` counter, 3 new `ROLE_BY_VARIANT` entries
- `tests/test_billing_audit_shadow.py` - `FreezeRowHelper2Tests` (6 tests), `FreezeRowHelper2DegradeTests` (4 tests), `TestResolveClaimerHelper2` (6 tests), `CountersTests` dict update
- `tests/golden/run_summary_baseline.json` - added `helper2_attribution_degraded: 0` (24 -> 25 keys)
- `pipeline/orchestrate.py` - mirrored the new counter key in both the TEST_MODE synthetic pre-seed dict and the production pre-seed dict (deviation, see below)
- `tests/test_parity_shadow.py` - updated pinned golden key-count assertion 24 -> 25 (deviation, see below)
- `tests/test_incremental_read.py` - updated 2 pinned golden key-count assertions 24 -> 25 (deviation, see below)

## Decisions Made
- Kept `_HELPER2_SENTINEL_CLAIMERS` separate from `_SENTINEL_CLAIMERS` to avoid breaking the SQL-twin parity test while still recognizing the new sentinel value, mirroring the 14-01 `_NON_CLAIM_LITERALS` precedent.
- Reused `billing_audit.client`'s typed `_PGAPIError`/`_classify_postgrest_error` for the capability probe rather than a locally re-declared exception-type fallback, avoiding a new mypy Gate 4 finding.
- Bounded the capability probe to at most one extra RPC call on an already-failed path only (never a per-row storm), matching T-14-03-04's disposition.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy Gate 4 regression from local exception-type re-declaration**
- **Found during:** Task 2 (degrade path implementation)
- **Issue:** A local `try: from postgrest import APIError as _APIError; except: _APIError = ()` idiom introduced a new unsuppressed mypy `[misc]` finding, moving Gate 4's error count from a neutral/improved delta to a regression (28 -> 29 lines in `wc -l` terms).
- **Fix:** Replaced with imports of `billing_audit.client`'s already-typed `_PGAPIError` and `_classify_postgrest_error` module-level names.
- **Files modified:** billing_audit/writer.py
- **Verification:** `bash scripts/check_mypy_delta.sh` -> "PASS: mypy delta neutral or improved (71 -> 71)"
- **Committed in:** `5c44d49` (Task 2 commit)

**2. [Rule 1 - Bug] 3 pinned golden key-count assertions broke on the new counter**
- **Found during:** Task 2, full-suite verification pass
- **Issue:** `tests/test_parity_shadow.py::GoldenContractTests.test_run_summary_baseline_key_count` and two assertions in `tests/test_incremental_read.py` (`WatermarkPersistenceTests`, `ScopedCounterTests`) hard-pin the golden baseline key count to exactly 24, a direct and foreseeable consequence of adding the 25th key.
- **Fix:** Updated all three assertions from 24 to 25 with corresponding comment updates.
- **Files modified:** tests/test_parity_shadow.py, tests/test_incremental_read.py
- **Verification:** `python -m pytest tests/ -q` — full suite green
- **Committed in:** `5c44d49` (Task 2 commit)

**3. [Rule 1/2 - Bug/Missing Critical] Gate 6 failure: synthetic run_summary.json missing the new counter key**
- **Found during:** Task 2, `bash scripts/run_6_gates.sh` Gate 6 run
- **Issue:** `_run_synthetic_test_mode()` in `pipeline/orchestrate.py` hand-builds its own `_synth_summary` dict independent of `get_counters()`, so the TEST_MODE-generated `run_summary.json` was missing `helper2_attribution_degraded` entirely — an actual observed Gate 6 failure ("missing keys"), not a speculative fix.
- **Fix:** Added `"helper2_attribution_degraded": 0` to both the synthetic pre-seed dict (required) and the production pre-seed dict (defensive parity, matching the existing "mirrors" invariant comment already in that code).
- **Files modified:** pipeline/orchestrate.py
- **Verification:** `bash scripts/run_6_gates.sh` -> "PASS: run_summary.json structure matches baseline (25 keys)" and "=== ALL 6 GATES PASSED ==="
- **Committed in:** `5c44d49` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 bug/mypy, 1 bug/pinned-test-update, 1 bug-and-missing-critical/Gate-6)
**Impact on plan:** All three were direct, foreseeable, or actually-observed consequences of the new counter key and probe implementation — no scope creep, no architectural change, no file outside this tight blast radius touched.

## Issues Encountered
None beyond the auto-fixed deviations above — all resolved within the same task's commit.

## Evidence Label

FIXTURE PASS only. No live Supabase RPC was called, and the deployed `freeze_attribution` function body was not observed. All 20 Helper #2-specific tests (and the full 2156-test suite) run against mocked/fake Supabase clients (`_make_fake_supabase_client`); the PGRST202 detection path is proven against a fabricated `postgrest.APIError`, not a live schema-cache rejection from an actual un-migrated deployment.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 14-06's subcontractor shadow partition is unblocked: `ROLE_BY_VARIANT` now has the three Helper #2 entries it depends on.
- Plan 14-09's Supabase migration can land in either deployment order relative to this plan — the degrade path tolerates the pre-migration RPC shape on both the freeze side (capability probe) and the read side (`resolve_claimer` no_history fallback).
- Plan 14-09 still owns the one unresolved item from 14-RESEARCH.md Assumption A4: proving the deployed function body does not overwrite `frozen_helper` — that is a post-migration owner-verified read-back check, not assumed here.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-07*

## Self-Check: PASSED

- FOUND: `.planning/phases/14-foreman-helper-2/14-03-SUMMARY.md`
- FOUND: `7509709` (Task 1 commit)
- FOUND: `5c44d49` (Task 2 commit)
- FOUND: `58d73d2` (Task 3 commit)
- FOUND: `4ecb76a` (SUMMARY.md commit)
