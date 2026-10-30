---
phase: 11-incremental-read-affected-group-regeneration
plan: 12
subsystem: pipeline-memory
tags: [gap-closure, G-11-37, regen-debt, run_ledger, shadow-parity, tdd]
status: complete

requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "11-11 row_state hash-domain fingerprint (mechanism A); pipeline/memory_candidate.py"
provides:
  - "pipeline/memory_candidate.py: regen_debt_from_ledger_rows, pairs_to_json, shadow_candidate_pairs, unconfirmed_pairs, REGEN_DEBT_MAX_PAIRS=5000, REGEN_DEBT_SCAN_LIMIT=20"
  - "pipeline_memory/reader.py: get_recent_run_ledger_rows(limit) - one bounded newest-first SELECT, nulls last"
  - "pipeline_memory/writer.py: run_ledger_note_pending(run_id, pairs, overflow) - UPDATE-by-run_id of notes only"
  - "orchestrate: main()-scoped _mem_ledger_rows (reused by 11-13) and _mem_regen_debt; shadow candidate and incremental path = affected | carried debt"
affects: [11-13, 11-15]

tech-stack:
  added: []
  patterns:
    - "Non-DDL durable carrier: run_ledger.notes JSON (mid-run pending note, replaced wholesale by the finish note)"
    - "UNKNOWN (None) debt resolves to shadow 'skipped' / incremental-to-full: scope only widens (T-11-18)"

key-files:
  created:
    - tests/test_regen_debt_carry.py
  modified:
    - pipeline/memory_candidate.py
    - pipeline_memory/reader.py
    - pipeline_memory/writer.py
    - pipeline/orchestrate.py

key-decisions:
  - "No DDL: debt rides run_ledger.notes (regen_pending_pairs mid-run, regen_debt_pairs at finish)"
  - "Pending note is an UPDATE by run_id only - never upsert/insert, so a failed run_ledger_start cannot create a NULL started_at row"
  - "Unknown debt = shadow verdict skipped (reason regen_debt_unknown); incremental returns trigger_regen_debt_unknown BEFORE any read or write"
  - "Constants, not env vars: REGEN_DEBT_MAX_PAIRS=5000, REGEN_DEBT_SCAN_LIMIT=20"

patterns-established:
  - "Pure finish-kwargs builders (_regen_debt_finish_kwargs / _regen_debt_failure_kwargs) keep main() wiring testable"

duration: ~60min
completed: 2026-10-29

actuals:
  tokens: 17400
  tasks: 3
  commits: 6
  plan_head_before: 2f9238e92259f2293a33c047b7179bbddc1fa860
  plan_head_after: 00ceef083eff68a1953dfc579b73aa1759774b97
---

# Phase 11 Plan 12: Regeneration-debt carry (G-11-37 mechanism B) Summary

**Groups stranded by a cancelled / timed-out / partly-failed run now reach the next run's D-04 candidate through `run_ledger.notes` (no DDL): a mid-run `regen_pending_pairs` note, replaced at finish by `regen_debt_pairs`, reduced newest-first back to the last `success` row; unknowable debt makes the shadow verdict `skipped` and the incremental path fall back to full.**

`plan_head_before` (pre-edit base SHA): `2f9238e92259f2293a33c047b7179bbddc1fa860`; `commits:` is measured (`git rev-list --count`) = 6 task commits (the SUMMARY/metadata commit follows separately).

## Commits

| Commit | Type | What |
|---|---|---|
| 25f1555 | test (RED) | reducer, `pairs_to_json`, `shadow_candidate_pairs`, reader, writer, killed-run replay |
| 53af895 | feat (tracer) | pure debt functions, `get_recent_run_ledger_rows`, `run_ledger_note_pending`, orchestrate hoists + pending note + shadow candidate/skip branch |
| a49bb00 | test (RED) | `unconfirmed_pairs`, finish/failure kwargs builders, attachment-repair tag, unknown-flag rule |
| a377c9a | feat | `unconfirmed_pairs`, `_regen_debt_finish_kwargs` / `_regen_debt_failure_kwargs`, skip/repair membership records, upload-success record, shadow `only_in_actual_attachment_repair` |
| ed73c44 | test (RED) | `_run_phase2_incremental(regen_debt=...)` contracts + main wiring |
| 00ceef0 | feat | `regen_debt` keyword-only param (default `frozenset()`), `candidate_pairs` in the result, main() uses it for the filter and the empty-run sentinel |

Tracer feedback gate: the tracer `<verify>` is automated-only (no `gate="blocking-human"`); re-run end to end after the tracer commit (382 passed) before expanding.

## Verification evidence

- `pytest tests/ -q`: **2511 passed, 1 skipped**, 664 subtests (after Task 3).
- `tests/test_regen_debt_carry.py`: 65 tests (+8 subtests), written RED first for every task; with `test_parity_shadow.py`, `test_incremental_read.py`, `test_pipeline_memory_shadow.py` unchanged and green (406 passed).
- Killed-run replay (4 affected pairs, 12 actual groups, 8 in 3 stranded pairs): without debt `only_in_actual` has exactly 8 and verdict `fail`; with debt from the ledger rows the verdict is `pass`.
- `python -m py_compile generate_weekly_pdfs.py pipeline/memory_candidate.py`: OK.
- `SMARTSHEET_API_TOKEN= bash scripts/run_6_gates.sh`: **ALL 6 GATES PASSED** (synthetic TEST_MODE, no live read; run_summary.json 30 keys unchanged).
- `git diff --exit-code <merge-base> -- change_detection grouping pricing attribution excel upload parity .github/workflows/`: clean (byte-identical). `git diff HEAD -- pipeline_memory/schema.sql`: clean.
- Postgrest `order` signature confirmed from the installed package (2.31.0): `order(column, *, desc=False, nullsfirst=None, foreign_table=None)`.
- No Supabase or Smartsheet contact; nothing printed or written from env.

## Shadow ordering (plan Task 2 requirement)

The group loop (where the skip and attachment-repair sets are populated) runs BEFORE the shadow block, and the shadow block runs BEFORE the upload phase. So `_mem_attachment_repair_keys` is fully populated when `only_in_actual_attachment_repair` is computed. Confirmed by reading the block order in `main()`.

## Deviations from Plan

### Auto-added critical functionality

**1. [Rule 2 - Missing correctness] Inherited-unknown debt must not be silently dropped.** The plan only handled unknown debt by skipping the shadow verdict. Without more, a run that starts with unknown debt and is then itself killed (or has an upload fail) would write a pending/finish note covering only its own affected set, so groups stranded in the unknowable era would be lost from the chain. Added: (a) the mid-run pending note is flagged overflowed (so a killed run reads back as UNKNOWN) when inherited debt is None or the write may have advanced `row_state` unseen; (b) at finish, `_regen_debt_finish_kwargs(inherited_unknown=True)` widens pending to every group pair of the run so any unconfirmed group is carried; (c) `regen_debt_unknown` is set when inherited debt was unknown and the run was scoped. Scope can only widen. Files: `pipeline/orchestrate.py`. Commits 53af895, a377c9a.

**2. [Rule 2 - Missing correctness] Memory-write exception also means unknown debt.** The plan's flag rule (`sheets_unconfirmed > 0 and rows_sent > 0`) misses the case where `_run_memory_write_phase` raises (the fallback result dict reports `rows_sent: 0` though row_state may have advanced). That, and any incremental fallback that is not a pre-write one (anything other than `trigger_delta_probe_escalation` / `trigger_regen_debt_unknown`), now sets `_mem_regen_unknown`. Extracted the plan's rule as `_memory_write_may_have_advanced_unseen`. Commit 53af895 / a377c9a.

### Judgement items

**3.** Pure debt builders (`_regen_debt_finish_kwargs`, `_regen_debt_failure_kwargs`, `_attachment_repair_only_in_actual`, `_note_pending_regen_pairs`) live in `orchestrate.py` as module-level functions (they call `_resolve_row_wr_week`, which `memory_candidate` must not import); `unconfirmed_pairs` itself is in `memory_candidate.py` as the plan states.

**4.** The per-group upload-success record is a short loop right after `upload_results = list(...)` rather than reusing `_group_upload_ok`, which is only built when the hash-store or group-state flush is enabled. Record only; no control flow reads it.

**5.** A debt pair that maps to no `row_state` sheet (e.g. rows since deleted) makes `map_affected_to_sheets` return empty and the incremental path fall back to full (existing `trigger_affected_set_mapping_empty`): wider, never narrower; flag is OFF anyway.

**6.** Finish/pending state-machine (for the record): a `failed` row carries the FULL pending set; the reducer unions every non-success row back to the first `success` row, so a run that fails before the memory write does not lose older debt.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-11-49 (malformed / overflow / legacy notes -> UNKNOWN), T-11-50 (cap + scan limit + zero-group clearing on unscoped runs), T-11-51 (UPDATE-by-run_id only, payload `{notes}`, zero-row case pinned, nulls-last order + NULL `started_at` skipped by the reducer) are covered by tests. Pair lists in `notes` are (WR, week) identifiers already stored in `row_state`.

## Not done / flags for follow-ups

- `RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF; no workflow, schema or env change; `memory-bank/living-ledger.md` entry is deferred to plan 11-13 (per 11-11's note).
- REQUIREMENTS.md INC-02 / INC-04 not ticked (streak still pending), per orchestrator instruction.
- Carried from 11-11: `Units Total Price` is rewritten in place by rate recalculation on the full-read path only (affects `units_total_price` in `HASH_FIELDS`); not touched here, relevant if 11-13/11-15 compare hashes across read paths.
- 11-13 reuses the hoisted `_mem_ledger_rows` (no second SELECT).
- One-time effect on first post-deploy run: ledger rows predate this feature, so debt is UNKNOWN and that run's shadow verdict is `skipped` (`regen_debt_unknown`); the following run reads the new finish note and is known again (self-healing).

## Self-Check: PASSED

- Files exist: `tests/test_regen_debt_carry.py`, `pipeline/memory_candidate.py`, `pipeline_memory/reader.py`, `pipeline_memory/writer.py`, `pipeline/orchestrate.py`, SUMMARY.
- Commits 25f1555, 53af895, a49bb00, a377c9a, ed73c44, 00ceef0 are ancestors of HEAD.
