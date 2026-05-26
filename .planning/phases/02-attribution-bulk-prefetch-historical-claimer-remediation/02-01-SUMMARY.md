---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
plan: "01"
subsystem: billing_audit
tags: [bulk-prefetch, attribution, supabase, performance, tdd]
dependency_graph:
  requires: []
  provides:
    - billing_audit.lookup_attribution_bulk RPC (schema.sql)
    - billing_audit.writer.prefetch_attribution (bulk reader)
    - billing_audit.writer.resolve_claimer(prefetched_map=) (O(1) map-aware)
  affects:
    - billing_audit/writer.py
    - billing_audit/schema.sql
    - tests/test_billing_audit_shadow.py
tech_stack:
  added:
    - lookup_attribution_bulk Supabase RPC (jsonb_to_recordset bulk join)
  patterns:
    - Chunked bulk RPC reader (500 pairs/chunk, fail-safe, op-isolated)
    - D-03 O(1) map-aware resolve_claimer (drop-in replacement for per-row RPC)
    - D-04 total-failure contract (caller constructs HOLD directly, zero re-invocation)
key_files:
  created: []
  modified:
    - billing_audit/schema.sql (lookup_attribution_bulk RPC + service_role grant)
    - billing_audit/writer.py (prefetch_attribution + map-aware resolve_claimer)
    - tests/test_billing_audit_shadow.py (PrefetchAttributionTests + ResolveClaimerMapAwareTests)
decisions:
  - "Empty pairs check moved before get_client() so prefetch_attribution({}) returns no_row regardless of credential state (not unavailable)"
  - "op=lookup_attribution_bulk is distinct from all existing ops (freeze_attribution, pipeline_run_select/upsert, feature_flag, lookup_attribution, lookup_group_hash) — D-13 op-isolation"
  - "D-04 contract: CALLER constructs HOLD directly on fetch_failure, never re-invokes resolver — zero additional Supabase calls on outage"
metrics:
  duration: "~20 minutes"
  completed_date: "2026-05-26"
  tasks_completed: 2
  files_changed: 3
---

# Phase 02 Plan 01: Bulk Attribution Prefetch Foundation Summary

Bulk read-side foundation for eliminating ~137k per-row `lookup_attribution` RPCs/run: `lookup_attribution_bulk` Supabase RPC, `prefetch_attribution` bulk reader, and map-aware `resolve_claimer(prefetched_map=)` that resolves O(1) from the preloaded map.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add lookup_attribution_bulk RPC to schema.sql (D-01) | 48e9e62 | billing_audit/schema.sql |
| 2 RED | Add PrefetchAttributionTests + ResolveClaimerMapAwareTests (failing) | 7077f2f | tests/test_billing_audit_shadow.py |
| 2 GREEN | Add prefetch_attribution + map-aware resolve_claimer | a581495 | billing_audit/writer.py |

## What Was Built

### Task 1: lookup_attribution_bulk RPC (D-01)

`billing_audit/schema.sql` now defines a bulk generalization of `lookup_attribution`. The new RPC:

- Accepts `p_wr_weeks jsonb` (array of `{wr, week_ending}` objects) and returns ALL matching `attribution_snapshot` rows in one round-trip
- Uses `jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)` joined to `attribution_snapshot` — no string concatenation, typed coercion (T-02-01)
- Copies the per-role `CASE WHEN s.frozen_primary LIKE '#%' OR btrim(...)` CASE blocks VERBATIM from `lookup_attribution` (D-01: one source of truth)
- `GRANT EXECUTE ... TO service_role` only, mirroring the existing grant (T-02-02)
- Includes operator-deploy comment block with `NOTIFY pgrst, 'reload schema';` instruction

### Task 2: prefetch_attribution + map-aware resolve_claimer (D-03, D-04, D-13)

**`prefetch_attribution(pairs)`** in `billing_audit/writer.py`:
- Chunks 500 pairs/RPC call (~45 bytes/pair, two orders of magnitude under the 1 MB limit)
- Builds `{(wr, week_ending, smartsheet_row_id) -> roles-dict}` map from bulk RPC results
- Never raises — all failure modes return `({}, status)` where status signals the degradation
- Uses `with_retry(op="lookup_attribution_bulk")` — DISTINCT op id from all existing ops (D-13 op-isolation)
- D-04 total-failure contract documented in docstring: caller applies variant policy directly on `fetch_failure`, zero re-invocation

**`resolve_claimer(prefetched_map=None)`** map-aware update:
- New keyword-only `prefetched_map: dict | None = None` parameter (D-03)
- When `prefetched_map is not None`: O(1) `(wr, week_ending, row_id)` key lookup yields same `(row, status)` shape as `_lookup_attribution_all` — decision table below is unchanged
- Key absent in non-empty map yields `(None, "no_row")` — use-current (no_history), not HOLD
- Default `None` path calls `_lookup_attribution_all` byte-identically to pre-edit behavior
- D-04 contract sentence in docstring: caller constructs HOLD directly, never re-invokes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Empty pairs check moved before get_client()**
- **Found during:** Task 2 GREEN phase (test_empty_pairs_returns_no_row failed)
- **Issue:** Original code called `get_client()` before checking `if not pairs`, so `prefetch_attribution(set())` returned `"unavailable"` (no credentials in test environment) instead of `"no_row"`
- **Fix:** Moved the `if not pairs: return {}, "no_row"` check to the top of `prefetch_attribution`, before the client acquisition
- **Files modified:** billing_audit/writer.py
- **Commit:** a581495

## TDD Gate Compliance

RED phase: `7077f2f` — test commit with 15 failing tests (`AttributeError: module has no attribute 'prefetch_attribution'`, `TypeError: resolve_claimer() got an unexpected keyword argument 'prefetched_map'`)

GREEN phase: `a581495` — implementation commit; all 15 tests pass

REFACTOR: not needed — implementation was clean after the one deviation fix.

## Test Results

- New test classes: `PrefetchAttributionTests` (8 tests), `ResolveClaimerMapAwareTests` (7 tests) = 15 new tests
- Full suite: **976 passed / 26 skipped / 69 subtests** (was 955 / 26 / 69 at phase start; +21 net)
- Historical claimer regression locked at Wave 1 (BLOCKER 3): `test_historical_row_resolves_real_claimer_from_map` and `test_historical_row_no_frozen_falls_back_to_current` both pass
- D-04 direct-HOLD zero-Supabase-call contract locked (BLOCKER 1): `test_fetch_failure_direct_hold_zero_supabase_calls` passes

## Threat Surface Scan

No new network endpoints or auth paths beyond what the plan's threat model documents. The `lookup_attribution_bulk` RPC is `GRANT`ed to `service_role` only (T-02-02). The `prefetch_attribution` reader logs only a generic warning with no row content (T-02-04). Chunking at 500 pairs keeps payload well under 1 MB (T-02-05 accepted).

## Operator Prerequisites (not code)

Before `prefetch_attribution` resolves real claimers at runtime, the operator must:
1. Apply the `CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(...)` DDL in the Supabase SQL Editor
2. Run `NOTIFY pgrst, 'reload schema';` (or use Project Settings -> API -> Reload schema cache)

Until then, `prefetch_attribution` returns `({}, "fetch_failure")` via the PGRST106/SQLSTATE 42P01 error path and `resolve_claimer` falls back to use-current for all variants — production behavior is unchanged.

## Self-Check: PASSED

Files exist:
- `billing_audit/schema.sql` contains `lookup_attribution_bulk`: YES
- `billing_audit/writer.py` contains `prefetch_attribution`: YES
- `tests/test_billing_audit_shadow.py` contains `PrefetchAttributionTests`: YES

Commits exist:
- `48e9e62` feat(02-01): schema.sql
- `7077f2f` test(02-01): RED tests
- `a581495` feat(02-01): writer.py implementation

`pytest tests/test_billing_audit_shadow.py -q` exits 0: YES (174 passed, 26 skipped)
`python -m py_compile billing_audit/writer.py` exits 0: YES
