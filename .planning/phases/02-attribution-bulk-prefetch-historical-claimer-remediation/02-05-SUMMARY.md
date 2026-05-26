---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
plan: 05
subsystem: api
tags: [supabase, postgrest, attribution, prefetch, billing, claim-attribution, fail-safe]

# Dependency graph
requires:
  - phase: 02-attribution-bulk-prefetch-historical-claimer-remediation (Plan 01)
    provides: prefetch_attribution bulk reader + resolve_claimer(prefetched_map=) contract
  - phase: 02-attribution-bulk-prefetch-historical-claimer-remediation (Plan 02)
    provides: single shared _attr_map wiring across B/C/D/sub-helper consumers
provides:
  - rpc_missing status from prefetch_attribution distinguishing a not-yet-deployed bulk RPC (PGRST202) from a transient outage
  - ATTRIBUTION_BULK_PREFETCH_FALLBACK default-ON kill switch that degrades rpc_missing to the deployed per-row lookup_attribution path so B/C/sub-helper still generate billing files
  - WR-sanitized resolve_claimer prefetched-map lookup key (closes the WR-01 split-brain)
  - sub-helper fetch_failure WARNING observability restored (WR-05)
  - deploy-order-tolerant merge — the fix no longer depends on operators deploying lookup_attribution_bulk before the next production run
affects: [02-06, claim-attribution, supabase-rpc-deploy, E-reactivation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "rpc_missing vs fetch_failure: classify a permanent missing-RPC (PGRST202) distinctly from a transient outage so the caller can degrade vs HOLD"
    - "Bounded one-call classification probe on the already-failed with_retry path (cannot reintroduce the per-row storm)"
    - "Default-ON degrade kill switch protects a code-before-RPC deploy window automatically"

key-files:
  created: []
  modified:
    - billing_audit/writer.py
    - generate_weekly_pdfs.py
    - .github/workflows/weekly-excel-generation.yml
    - website/docs/reference/environment.md
    - tests/test_billing_audit_shadow.py
    - tests/test_subcontractor_helper_shadow_rescue.py

key-decisions:
  - "rpc_missing is detected at the prefetch_attribution layer via a bounded one-call probe because with_retry swallows the APIError and returns only None"
  - "Fail-safe default: any failure not provably PGRST202 stays fetch_failure (never falsely claim the RPC is missing)"
  - "ATTRIBUTION_BULK_PREFETCH_FALLBACK defaults ON so the merge does not depend on deploy ordering; transient outages still HOLD B/C (D-04 preserved)"
  - "resolve_claimer's prefetched-map lookup key is sanitized identically to the map key (WR-01); numeric WR#s are a no-op"

patterns-established:
  - "Permanent-vs-transient classification: when with_retry collapses an APIError to None, re-probe once on the failed path to recover the reason_code"
  - "Degrade-not-HOLD on a missing RPC; HOLD only on a genuine transient outage"

requirements-completed: [SPEC-1, SPEC-2, SPEC-3, SPEC-6]

# Metrics
duration: ~70min
completed: 2026-05-26
---

# Phase 02 Plan 05: Bulk-Prefetch rpc_missing Graceful Degradation Summary

**A missing lookup_attribution_bulk RPC (PGRST202) now degrades to the deployed per-row lookup_attribution path so B/C/sub-helper still generate billing files, while a genuine transient outage still HOLDs B/C (D-04) — the merge no longer depends on operators deploying the bulk RPC first.**

## Performance

- **Duration:** ~70 min
- **Started:** 2026-05-26T16:10:10-05:00 (first task commit)
- **Completed:** 2026-05-26T21:18Z
- **Tasks:** 4 (3 implementation + 1 full-suite gate)
- **Files modified:** 6

## Accomplishments
- `prefetch_attribution` returns a distinct `rpc_missing` status for a not-yet-deployed bulk RPC (PGRST202), separate from the transient `fetch_failure` — via a bounded one-call classification probe that cannot reintroduce the ~137k per-row RPC storm.
- New default-ON `ATTRIBUTION_BULK_PREFETCH_FALLBACK` kill switch wires the rpc_missing → per-row degrade across the B, C, D, and sub-helper consumers (`prefetched_map=None`), closing the CR-01 BLOCKER: a code-before-RPC deploy ordering no longer suppresses billing files.
- A transient `fetch_failure` still preserves the D-04 HOLD contract for B/C (no regression to the per-row storm).
- WR-01 closed: `resolve_claimer`'s prefetched-map lookup key is now sanitized identically to the map key, so a sanitization-sensitive WR# resolves its real frozen claimer instead of silently falling back to use-current.
- WR-05 closed: the sub-helper block threads `_attr_status` so a bulk failure surfaces the per-WR `reason=fetch_failure` WARNING again (Bug C observability).
- WR-03 (misleading D-consumer comment) and IN-01 (dead `_resolve_claimer_bulk` / `_ResolveOutcome` import aliases) closed.
- Full suite: **981 passed** / 29 skipped / 69 subtests (strictly > 973 baseline; SPEC-6 met).

## Task Commits

Each task was committed atomically:

1. **Task 1: prefetch_attribution distinguishes rpc_missing from fetch_failure** - `6254832` (feat, TDD)
2. **Task 2: WR-01 sanitize resolve_claimer prefetched-map lookup-key WR** - `2e0a91c` (fix, TDD)
3. **Task 3: CR-01 fallback env gate + degrade wiring; WR-05; WR-03; IN-01** - `0e79b0b` (feat, TDD)
4. **Task 4: full-suite green gate (count > 973)** - no code change (verification-only gate)

_Note: TDD tasks combine their RED test methods + GREEN implementation in a single atomic commit because the production environment lacks `postgrest` (the PGRST202-specific tests skip locally and run in CI); the writer-level GREEN was verified via the always-run tests + py_compile and the behavioral B/C/sub-helper tests in Task 3._

## Files Created/Modified
- `billing_audit/writer.py` - `prefetch_attribution` adds the `rpc_missing` PGRST202 classification probe; `resolve_claimer` sanitizes the prefetched-map lookup-key WR (WR-01).
- `generate_weekly_pdfs.py` - `ATTRIBUTION_BULK_PREFETCH_FALLBACK` env read + startup banner; `_attr_use_per_row_fallback` degrade decision; B/C HOLD gates + `prefetched_map=(None if fallback else _attr_map)` at B/C/D/sub-helper; WR-05 sub-helper status thread; WR-03 comment fix; IN-01 dead-import removal.
- `.github/workflows/weekly-excel-generation.yml` - `ATTRIBUTION_BULK_PREFETCH_FALLBACK: '1'` pinned default-ON.
- `website/docs/reference/environment.md` - new `### ATTRIBUTION_BULK_PREFETCH_FALLBACK` section.
- `tests/test_billing_audit_shadow.py` - `PrefetchAttributionTests` (rpc_missing / fetch_failure / distinctness) + `ResolveClaimerMapAwareTests` (WR-01 sanitization-sensitive + numeric-WR cases).
- `tests/test_subcontractor_helper_shadow_rescue.py` - new `TestRpcMissingGracefulDegradation` (6 behavioral tests driving `group_source_rows`); reconciled the sub-helper source guard to the gated `prefetched_map` form.

## Decisions Made
- Detect `rpc_missing` at the `prefetch_attribution` layer (not inside `with_retry`, which discards the reason_code) using a single bounded re-probe on the already-failed path.
- Fail-safe default: only a provably-PGRST202 probe exception yields `rpc_missing`; everything else stays `fetch_failure`.
- The degrade fallback fires ONLY on `rpc_missing` (permanent) — never on a transient `fetch_failure` — so the D-04 HOLD contract for B/C is preserved.
- The per-row fallback is bounded to rows the consumers actually process this run, so it cannot recreate the per-row storm.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test-contract reconciliation] Updated the sub-helper source-grep guard to the gated prefetched_map form**
- **Found during:** Task 3 (CR-01 wiring)
- **Issue:** The pre-existing guard `test_bug_c_reader_invocation_site_present_in_production` asserted the exact literal `prefetched_map=_attr_map`. The CR-01 change replaced the sub-helper call argument with the fallback-aware `prefetched_map=(None if _attr_use_per_row_fallback else _attr_map)`, so the bare literal no longer appears verbatim at that site and the guard failed.
- **Fix:** Reconciled the guard in place (per the project's [2026-05-20 00:26] rule 2) to assert the new gated expression + `_attr_use_per_row_fallback`, preserving the guard's intent ("the sub-helper site reads the shared prefetched map") and strengthening it rather than weakening it. A docstring note cites the Plan 05 CR-01 change.
- **Files modified:** tests/test_subcontractor_helper_shadow_rescue.py
- **Verification:** The reconciled guard + the full affected-suite (283 passed) + full suite (981 passed) all green.
- **Committed in:** `0e79b0b` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 test-contract reconciliation)
**Impact on plan:** The reconciliation was required by the CR-01 wiring change itself and was anticipated by the project's test-contract rules. No scope creep; the additive/surgical constraint held (no changes to the four-site identity lockstep, mirror matchers, variant grouping, or filename grammar).

## Issues Encountered
- The new `rpc_missing` / `fetch_failure` PGRST202 tests (Task 1) and the `lookup_attribution_bulk` APIError tests depend on the `postgrest` package, which is NOT installed in the local execution environment. They `skipTest(...)` locally (mirroring the established `PostgrestErrorClassificationTests` pattern) and run in CI where postgrest IS installed. This accounts for the skipped-count rising from 26 → 29. The non-postgrest GREEN behavior was still validated locally via the always-run WR-01 tests, the 6 behavioral B/C/sub-helper tests, and `py_compile`.

## User Setup Required
None - no external service configuration required by this plan. (Operator follow-up to actually deploy the `lookup_attribution_bulk` RPC and flip `SUPABASE_HASH_STORE_AUTHORITATIVE=1` remains a separate, human-gated step tracked by Plan 02-04's runbook — but this plan's whole point is that the merge is now safe REGARDLESS of that deploy ordering.)

## Next Phase Readiness
- CR-01 BLOCKER closed in-code; SPEC-2 is now fully achievable without depending on operator deploy ordering.
- WR-01 / WR-03 / WR-05 / IN-01 findings closed.
- Ready for the remaining gap-closure plan(s) in Phase 02 and for the orchestrator's post-wave shared-file updates.

## Self-Check: PASSED
- All modified files present (writer.py, generate_weekly_pdfs.py, weekly-excel-generation.yml, environment.md, both test files) — verified via filesystem check.
- All three task commits present: `6254832`, `2e0a91c`, `0e79b0b` — verified via git log.
- Full suite: 981 passed / 29 skipped (strictly > 973 baseline); no test files deleted.

---
*Phase: 02-attribution-bulk-prefetch-historical-claimer-remediation*
*Completed: 2026-05-26*
