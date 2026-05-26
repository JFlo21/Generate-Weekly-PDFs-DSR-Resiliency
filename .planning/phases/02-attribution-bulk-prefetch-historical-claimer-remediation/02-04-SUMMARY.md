---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
plan: "04"
subsystem: documentation
tags: [runbook, living-ledger, operator-procedure, documentation, D-09, D-10, D-11]
dependency_graph:
  requires: ["02-01", "02-02", "02-03"]
  provides:
    - E re-activation + remediation operator runbook (operations.md)
    - Phase 2 Living Ledger entry (CLAUDE.md)
  affects:
    - website/docs/runbook/operations.md
    - CLAUDE.md
tech_stack:
  added: []
  patterns:
    - Ordered-prerequisite operator runbook (deploy RPC -> validate -> flip -> remediate)
    - Evidence-based validation gate (D-10) before destructive go-live flip
    - Human-gated feature activation (D-11) separate from fix PR
key_files:
  created: []
  modified:
    - website/docs/runbook/operations.md (E re-activation runbook section with D-01/D-08/D-09/D-10/D-11)
    - CLAUDE.md (Phase 2 Living Ledger entry [2026-05-26 14:55])
decisions:
  - "D-11: AUTHORITATIVE=1 flip is a separate operator action with evidence-based validation gate, not bundled in fix PR"
  - "D-09 ordered procedure documented: RPC deploy -> validate -> flip -> remediate"
  - "D-10 validation gate: four evidence items (zero garbage names, O(chunks) HTTP, <=165 min, pytest green)"
  - "D-08 dry-run-first remediation documented in runbook with workflow_dispatch examples"
metrics:
  duration: "~20 minutes"
  completed_date: "2026-05-26"
  tasks_completed: 2
  files_changed: 2
---

# Phase 02 Plan 04: E Re-activation Runbook + Living Ledger Summary

Operator-facing documentation closing Phase 2: an ordered E re-activation + remediation procedure in `website/docs/runbook/operations.md` and a synthesized Phase 2 Living Ledger entry in `CLAUDE.md`. Documentation-only plan — no code or production-state changes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | E re-activation + remediation runbook (D-01/D-09/D-10/D-11/D-08) | 34593f2 | website/docs/runbook/operations.md |
| 2 | Phase 2 Living Ledger entry | 7103275 | CLAUDE.md |

## What Was Built

### Task 1: operations.md Runbook Section

Added a new operator-workflow section "Re-activate Sub-project E (clean filenames + durable hash store)" to `website/docs/runbook/operations.md`. The section:

- States up front that the flow is owned by the **Python billing pipeline** (`generate_weekly_pdfs.py` + GitHub Actions), per documentation-maintenance.md
- Cites the premature-flip incident (`67539ec` -> corruption -> `46cd05d` revert / PR #234) as the rationale for the human gate
- Documents the ordered four-step procedure (D-09):
  1. **Step 1 (D-01):** Deploy `lookup_attribution_bulk` RPC via Supabase SQL Editor + `NOTIFY pgrst, 'reload schema';`
  2. **Step 2 (D-10):** Evidence-based validation gate with `AUTHORITATIVE=0` still set — four criteria: zero garbage filenames, O(chunks) HTTP count, runtime <= `TIME_BUDGET_MINUTES=165`, pytest green
  3. **Step 3 (D-11):** Flip `SUPABASE_HASH_STORE_AUTHORITATIVE: '1'` as a **separate one-line commit/PR**, explicitly NOT bundled in the fix PR
  4. **Step 4 (D-08):** Dry-run-first `REMEDIATE_CLAIMERS` sweep (review would-delete counts, then execute), with workflow_dispatch YAML examples
- Includes roll-back notes for E revert and remediation disable
- Validated: Docusaurus `npm run build` exits `[SUCCESS]` with no errors

All six required strings asserted present: `SUPABASE_HASH_STORE_AUTHORITATIVE`, `lookup_attribution_bulk`, `REMEDIATE_CLAIMERS`, `TIME_BUDGET_MINUTES`, `NOTIFY pgrst`, `46cd05d`.

### Task 2: CLAUDE.md Living Ledger Entry

Appended a new `[2026-05-26 14:55]` entry (later than the existing `01:45` entry — four total `2026-05-26` entries now present) synthesizing Phase 2:

- **Context:** the `01:45` `ATTRIBUTION_RESOLUTION_WEEKS=8` hotfix gated group-KEY/filename formation; composed with E's `AUTHORITATIVE=1` activation (`67539ec`), it regenerated historical groups with garbage claimer names (372 of 1,116 files in run 26439205107); `attribution_snapshot` was ~99% populated with real names — the data existed, the read side never read it for out-of-scope weeks
- **Fix:** `lookup_attribution_bulk` RPC + `prefetch_attribution` bulk reader + map-aware `resolve_claimer(prefetched_map=)` replacing four per-variant ThreadPoolExecutor pre-passes; `ATTRIBUTION_RESOLUTION_WEEKS` removed entirely; D-04 direct-HOLD contract
- **Remediation:** `run_claimer_remediation` default-OFF, dry-run-first mode; window 26 weeks; live-identity exemption; isolated dispatch
- **Sequencing / gate:** D-09/D-10/D-11 ordered procedure; fix at `AUTHORITATIVE=0`; separate human-gated flip after evidence-based validation
- **Three new durable rules:** (1) no recency/scope gate on identity formation — only on skip optimizations; (2) distinct-op-id + bulk-load-eliminate-per-row + direct-HOLD-no-re-invocation; (3) dormant-feature go-live flip is a human-gated operator action, never bundled in the fix PR
- **Test classes named:** `PrefetchAttributionTests`, `ResolveClaimerMapAwareTests`, `TestHistoricalClaimerRegression`, `tests/test_claimer_remediation.py`; final `pytest tests/` count: **973 passed / 26 skipped / 69 subtests**

All four required strings asserted present; two distinct `[2026-05-26 HH:MM]` entries confirmed.

## Deviations from Plan

None — plan executed exactly as written. The MD060 table-pipe-spacing linting warnings in operations.md are cosmetic (linter style preference for "compact" mode), not build-breaking; Docusaurus build exits `[SUCCESS]` cleanly. The warnings are pre-existing in the page style and not introduced by this change.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. This is a documentation-only plan. The runbook section drives a human through a destructive flip + sweep, but the documentation itself introduces no new technical surface.

## Self-Check: PASSED

Files exist:
- `website/docs/runbook/operations.md` contains `SUPABASE_HASH_STORE_AUTHORITATIVE`: YES
- `website/docs/runbook/operations.md` contains `lookup_attribution_bulk`: YES
- `website/docs/runbook/operations.md` contains `REMEDIATE_CLAIMERS`: YES
- `website/docs/runbook/operations.md` contains `TIME_BUDGET_MINUTES`: YES
- `website/docs/runbook/operations.md` contains `NOTIFY pgrst`: YES
- `website/docs/runbook/operations.md` contains `46cd05d`: YES
- `CLAUDE.md` has second `[2026-05-26 HH:MM]` entry: YES (4 total)
- `CLAUDE.md` contains `lookup_attribution_bulk`: YES
- `CLAUDE.md` contains `ATTRIBUTION_RESOLUTION_WEEKS`: YES
- `CLAUDE.md` contains `run_claimer_remediation`: YES
- `CLAUDE.md` contains `PrefetchAttributionTests`: YES

Commits exist:
- `34593f2` docs(02-04): operations.md runbook: FOUND
- `7103275` docs(02-04): CLAUDE.md Living Ledger: FOUND

Docusaurus build: `[SUCCESS]` — clean
