---
phase: 11-incremental-read-affected-group-regeneration
plan: 13
subsystem: pipeline-memory
tags: [gap-closure, G-11-37, shadow-parity, d-02-fallback, owner-decision, tdd]
status: complete

requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "11-12 main()-scoped _mem_ledger_rows, regen debt, shadow regen_debt_unknown branch"
provides:
  - "pipeline/memory_candidate.py: SHADOW_MODELS_TRIGGER6, shadow_fallback_skip_reason, group_hash_globals_fingerprint, prior_globals_fingerprint"
  - "pipeline/orchestrate.py: _shadow_fallback_skip (pure, calls resolve_run_mode with flag ON), shadow elif branch, group_hash_globals_fp persisted in run_ledger.notes on both finish paths"
  - "Blocking pre-flip todo for the real incremental path's globals-change full fallback"
affects: [11-14, 11-15]

tech-stack:
  added: []
  patterns:
    - "Shadow asks the pure resolve_run_mode what the real path would do; a would-be full run is skipped, never pass/fail"
    - "Globals fingerprint rides run_ledger.notes (no DDL)"

key-files:
  created:
    - tests/test_parity_shadow_fallback_model.py
    - .planning/todos/pending/2026-10-29-inc02-incremental-globals-fallback-trigger.md
  modified:
    - pipeline/memory_candidate.py
    - pipeline/orchestrate.py
    - .planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md
    - memory-bank/living-ledger.md

key-decisions:
  - "Owner decision (Juan, 2026-10-29): Q1 YES - run after unfinished/failed run (D-02 trigger 6) is skipped; Q2 - manual runs with streak_eligible keep counting"
  - "Trigger 7 is never modelled; shadow asks resolve_run_mode as production_frequent"
  - "Globals check runs before trigger modelling; unknown prior or current fingerprint -> skipped"

patterns-established:
  - "Never-raise helper returns a skip dict on internal error (unknowable -> skipped)"

duration: ~35min
completed: 2026-10-29

actuals:
  tokens: 9500
  tasks: 3
  commits: 4
  plan_head_before: 270c8bfb536b86bc933a293d3bdd63fb40ab1a49
  plan_head_after: 9a84d4139b773d1b1e6474630d301ef019c8e34f
---

# Phase 11 Plan 13: Shadow fallback modelling (G-11-37 close-out) Summary

**The shadow parity verdict is now `skipped` (`would_fallback_full:<why>`) whenever the real incremental path would not have run incrementally (D-02 triggers 4/5/6) or a group-hash global (extended mode, rate cutoff, contract / subcontractor rates fingerprint) changed since the previous successful run; the real path's matching trigger is filed as a blocking pre-flip todo.**

## Owner decisions

Juan (owner), given directly on 2026-10-29, recorded as a dated D-09 amendment in `11-CONTEXT.md` (commit 2b49376); not re-asked:

- **Q1 YES:** a run whose previous `run_ledger` row is unfinished or not `success` (D-02 trigger 6) gets `skipped` (`would_fallback_full:trigger6`) and neither counts nor resets the streak. Policy is the single constant `SHADOW_MODELS_TRIGGER6 = True`.
- **Q2 KEEP:** `manual` runs with `streak_eligible` true keep counting (2026-08-29 amendment stands). `pipeline_memory/reader.py` is unchanged; pinned by `StreakQ2PinTests`.

## Commits

| Commit | Type | What |
|---|---|---|
| 2b49376 | docs | Task 1: D-09 amendment (2026-10-29) in 11-CONTEXT.md |
| 0429559 | test (RED) | 34 of 36 tests failing for the right reason |
| e1e7e23 | feat (tracer) | memory_candidate functions, `_shadow_fallback_skip`, shadow branch, `group_hash_globals_fp` on both finish paths |
| 9a84d41 | docs | Task 3: blocking todo + consolidated Living Ledger entry |

`commits: 4` is measured (`git rev-list --count 270c8bf..HEAD`), before the metadata commit. Tracer feedback gate: `<verify>` is automated-only, re-run end to end after the tracer commit (148 passed) before Task 3.

## Verification evidence

- `pytest tests/ -q`: **2547 passed, 1 skipped**, 664 subtests (new file: 36 tests).
- `python -m py_compile generate_weekly_pdfs.py pipeline/memory_candidate.py pipeline/orchestrate.py`: OK.
- `SMARTSHEET_API_TOKEN= bash scripts/run_6_gates.sh`: ALL 6 GATES PASSED (synthetic TEST_MODE, no live read; run_summary.json 30 keys).
- `git diff --exit-code <merge-base> -- change_detection grouping pricing attribution excel upload parity fetch .github/workflows/`: clean. `git diff HEAD -- pipeline_memory/schema.sql pipeline_memory/reader.py`: clean. `resolve_run_mode` untouched.
- No Supabase / Smartsheet contact; no env values printed or written.

## Behaviour notes

- Order in the shadow block: memory unconfirmed -> regen debt unknown (11-12) -> **fallback/globals skip (new)** -> comparison. Inside `_shadow_fallback_skip` the globals check runs first, then the modelled triggers.
- `_last_run_status` is now hoisted to `None` (== trigger 6, matching `resolve_run_mode`'s reading of an unreadable status); `_mem_ledger_rows` is reused, no second SELECT.
- The current fingerprint is computed once after PHASE 2 (rates fingerprint final) and persisted on both the success and failure finish paths; only `success` rows are read back.
- **Expected one-time skips on the first post-deploy run:** (1) `regen_debt_unknown` (11-12: ledger rows predate debt notes); (2) no prior `group_hash_globals_fp`, so `group_hash_globals_unknown` would apply as well. The following run is known again (self-healing).

## Deviations from Plan

### Auto-added critical functionality

**1. [Rule 2 - Missing correctness] Unknown current fingerprint and internal errors map to `skipped`.** Plan specified unknown only for a missing prior fingerprint. An empty current fingerprint (`''`, error path) or an exception inside the helper could otherwise let a comparison against an unmodelled state proceed; both now return a `would_fallback_full:*` skip (`group_hash_globals_unknown`, `shadow_model_error`). Scope of evidence only narrows; matches T-11-54. File: `pipeline/orchestrate.py`.

### Judgement items

**2.** The decision logic lives in a module-level pure function `_shadow_fallback_skip` in `orchestrate.py` (it needs `resolve_run_mode` and the operator-flag globals) rather than inline in `main()`, so it is unit-tested through the real `resolve_run_mode`; main() has source-pin wiring tests like 11-12.

**3.** Breadcrumb for a fallback skip uses `level="info"` (an expected operating condition, not a warning).

## Known Stubs

None.

## Threat Flags

None beyond the plan register. T-11-53 (decision recorded), T-11-54 (would-fallback runs skipped, unknown globals skipped) and T-11-55 (blocking todo; flag stays OFF) are covered.

## Not done / flags for follow-ups

- **Blocking pre-flip todo** `.planning/todos/pending/2026-10-29-inc02-incremental-globals-fallback-trigger.md`: the real incremental path still has no globals-change full fallback (needs owner-approved change to rate-load timing). Filed only; not implemented. `RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF.
- Classes that can still produce a `fail` (carried into the Living Ledger entry): externally deleted attachment (tagged `only_in_actual_attachment_repair`, verdict unchanged); claim-attribution re-key with no row edit; WR move until 11-14 is applied live.
- REQUIREMENTS.md INC-02 / INC-04 not ticked (streak still pending), per orchestrator instruction.

## Self-Check: PASSED

- Files exist: `tests/test_parity_shadow_fallback_model.py`, the todo, `pipeline/memory_candidate.py`, `pipeline/orchestrate.py`, SUMMARY.
- Commits 2b49376, 0429559, e1e7e23, 9a84d41 are ancestors of HEAD.
