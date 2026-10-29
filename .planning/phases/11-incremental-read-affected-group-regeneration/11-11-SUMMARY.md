---
phase: 11-incremental-read-affected-group-regeneration
plan: 11
subsystem: pipeline-memory
tags: [gap-closure, G-11-37, row_state, content_hash, change-detection, fingerprint, tdd]
status: complete

requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "11-09 candidate-divergence diagnosis; D-04 affected-set derived from row_state.content_hash deltas"
provides:
  - "pipeline/memory_candidate.py: row_group_hash_fingerprint(row), GROUP_DERIVATION_KEYS, DERIVED_KEY_SOURCES"
  - "pipeline_memory/writer.py: HASH_ONLY_FIELDS = ('group_hash_fp',) folded into compute_content_hash, stripped from the sent payload"
  - "orchestrate stamps __mem_group_fp; a Job #/Dept #/Customer Name/Work Order #/CU Description/UoM/Area/Scope/raw Quantity-Snapshot/Foreman Assigned?/helper/VAC edit now moves row_state.content_hash"
  - "AST key-coverage drift detector (T-11-48) and skip-gate independence static gate"
affects: [11-12, 11-13, 11-15]

tech-stack:
  added: []
  patterns:
    - "Hash-only member: caller-computed value enters content_hash via HASH_ONLY_FIELDS and is deleted from the payload (zero DDL, RPC key set unchanged)"
    - "Mode-invariant fingerprint: derived double-underscore keys excluded, covered through their raw source columns"

key-files:
  created:
    - pipeline/memory_candidate.py
    - tests/test_row_state_group_hash_domain.py
  modified:
    - pipeline_memory/writer.py
    - pipeline/orchestrate.py
    - tests/test_deep_run_reconciliation.py
    - tests/fixtures/incremental/formula_only_change.json
    - docs/ai/architecture.md

key-decisions:
  - "No DDL: HASH_FIELDS (20 members, pinned to the RPC column lists) untouched; fingerprint enters content_hash through the separate HASH_ONLY_FIELDS tuple"
  - "Derived keys (__effective_user, __helper*, __helper2*, __vac_crew*, __is_*) are NOT fingerprinted; their raw source columns are (mode invariance wins, per plan Task 2)"

duration: ~45min
completed: 2026-10-29

actuals:
  tokens: 11300
  tasks: 3
  commits: 4
  plan_head_before: b3fbcedf37b4b5364ba6d696bf56fd0477174b8a
  plan_head_after: d6516eec7c5b0dd0c5dabe1a459dce842e601fc3
---

# Phase 11 Plan 11: Row-state hash-domain fingerprint (G-11-37 mechanism A) Summary

**`row_state.content_hash` now moves on any edit to a field the group hash or group key reads (Job #, Dept #, Customer Name, `Foreman Assigned?`, ...), via a hash-only SHA-256 fingerprint built from `_extended_row_fields` plus raw group-derivation columns -- no DDL, RPC payload unchanged.**

`plan_head_before` (pre-edit base SHA): `b3fbcedf37b4b5364ba6d696bf56fd0477174b8a`; `commits:` is measured (`git rev-list --count`), 4.

## Commits

| Commit | Type | What |
|---|---|---|
| e439a74 | test (RED) | Tests A-E: Job #/Dept #/Foreman Assigned? edits leave content_hash unchanged (5 failing for the right reason), payload-key and HASH_FIELDS pins |
| a086bb5 | feat (GREEN) | `memory_candidate.py`, writer `HASH_ONLY_FIELDS`, orchestrate stamp |
| f98f8b6 | test | Perturbation, determinism, key-order, mode invariance, failure path, AST key-coverage drift detector; writer-level Customer Name test scoped + stamped sibling; new fixture case |
| d6516ee | test/docs | Skip-gate independence static gate; `docs/ai/architecture.md` row |

(The plan-checker advisory about splitting the AST drift test into its own commit was not needed; it landed with the Task 2 test batch, not dropped.)

## Verification evidence

- `pytest tests/ -q`: **2446 passed, 1 skipped**, 656 subtests (full suite, run after Task 3).
- `tests/test_row_state_group_hash_domain.py`: 18 tests (+46 subtests); with `test_deep_run_reconciliation.py`, `test_mem04_formula_change.py`, `test_group_identity_and_header_foreman.py`: 120 passed (golden group-hash digests unchanged).
- RPC contract + writer-boundary: `test_upsert_rows_bulk_helper2_contract.py`, `test_pipeline_memory_shadow.py` pass unchanged.
- `python -m py_compile generate_weekly_pdfs.py pipeline/memory_candidate.py`: OK.
- `SMARTSHEET_API_TOKEN= bash scripts/run_6_gates.sh`: **ALL 6 GATES PASSED** (synthetic TEST_MODE, no live read).
- `git diff --exit-code <merge-base> -- change_detection grouping pricing attribution excel upload .github/workflows/`: clean (byte-identical). `git diff HEAD -- pipeline_memory/schema.sql`: clean.
- Drift detector proven live: removing two exclusions made the test fail naming exactly `['User', '__variant']`.

## Deviations from Plan

### Plan-sanctioned adjustment (mode-invariance finding)

**1. [Plan Task 2 branch] Delta and full read paths do NOT attach identical derived keys.** `fetch.map_delta_sheet_rows` sets no `__effective_user`, `__helper*`, `__helper2*`, `__vac_crew*`, `__is_*` keys; only `get_all_source_rows` does. Per the plan's instruction, derived keys are excluded from the fingerprint (it strips them before calling `_extended_row_fields`, so `__vac_crew_*` read as constant `''` in both modes) and covered through raw sources. Consequences, all intentional:
- `GROUP_DERIVATION_KEYS` is raw-columns only (13 entries; adds `VAC Crew Dept #` / `Vac Crew Job #` raw names read from fetch.py). A separate `DERIVED_KEY_SOURCES` map (derived key -> raw sources) records the coverage; a test asserts every source is fingerprinted and no derived key is in `GROUP_DERIVATION_KEYS`. The plan's artifact line "incl. ... `__effective_user`" is therefore satisfied via `DERIVED_KEY_SOURCES`, not the tuple.
- The plan's perturbation list included derived keys (`__vac_crew_dept`, `__helper_dept`, `__effective_user`) perturbed directly. Those are instead perturbed through their raw source via the real full-read derivation, asserting the derived key flips AND `content_hash` flips (`test_group_key_inputs_flip_derived_key_and_content_hash`).
- Mode invariance is asserted for Foreman Assigned?-set, Foreman-only, and helper+VAC rows (delta row verifiably lacks the derived keys).

### Auto-fixed / judgement items

**2. [Rule 3 - fixture] "Pick a column already present on the cassette rows" was not satisfiable.** The only non-HASH_FIELDS column on the cassette is `Customer Name`, now in the group-hash domain. New case `non_group_hash_field_change` edits `Vac Crew Email Address` (display/notification only; `__vac_crew_email` is never hashed). The test asserts the column is outside `_extended_row_fields`, outside `GROUP_DERIVATION_KEYS`, and outside `HASH_FIELDS` before asserting hash equality.
**3.** The existing writer-level test body/assertion in `test_deep_run_reconciliation.py` is unchanged; only its docstring was corrected, as specified.

## Findings (not fixed, out of scope)

- `Units Total Price` is mutated in place by rate recalculation on the full-read path only; the delta path carries the raw sheet price. This already affects `HASH_FIELDS.units_total_price` today and is not widened by the fingerprint (the same cell feeds both). Worth noting for 11-12/11-15 when incremental mode alternates with full runs.
- `User` (identity-only sort tiebreaker) and `Weekly Reference Logged Date` are documented exclusions in `_FINGERPRINT_EXCLUSIONS`, each with a reason.

## Residual class (honest statement)

A group re-keyed purely by a `billing_audit` claim-attribution change with no row edit (operator backfill/repair) is outside the row domain and is NOT covered by any row fingerprint; it would surface as `only_in_actual`. To be listed in 11-13's ledger entry and 11-15 as a class that can still reset the parity streak.

## Expected one-time side effects (document, do not "fix")

On the first post-deploy run every live `row_state.content_hash` re-keys once (`rows_changed` ~ live row count; one `row_event` burst). It causes no Excel regeneration or upload: the skip/regenerate gate never reads `row_state` (pinned by `SkipGateIndependenceTests.test_skip_gate_never_reads_row_state`; live confirmation is plan 11-15's owner checkpoint). The D-08 read-side verdict fails once on that run (streak already 0). If the burst exceeds `RUN_MEMORY_WRITE_MAX_MINUTES`, remaining sheets re-key on subsequent runs with the same harmless effect.

**Burst size (optional Supabase read-only count): NOT run** -- the Supabase MCP was not loaded in this executor; for 11-15, run `SELECT count(*) FROM pipeline_memory.row_state WHERE deleted_at IS NULL` (project poeyztlmsawfoqlanucc, SELECT only).

## Known Stubs

None.

## Threat Flags

None (no new endpoints or trust-boundary surface). T-11-45 (payload keys, Test C + RPC contract), T-11-46 (skip-gate static test), T-11-48 (AST drift detector) mitigated as planned.

## Not done / flags for follow-ups

- `memory-bank/living-ledger.md` entry deferred to plan 11-13 (per plan text); `RUN_MEMORY_INCREMENTAL_ENABLED` still OFF; no workflow/schedule/env change.

## Self-Check: PASSED

- Files exist: `pipeline/memory_candidate.py`, `tests/test_row_state_group_hash_domain.py`, SUMMARY.
- Commits e439a74, a086bb5, f98f8b6, d6516ee are ancestors of HEAD.
