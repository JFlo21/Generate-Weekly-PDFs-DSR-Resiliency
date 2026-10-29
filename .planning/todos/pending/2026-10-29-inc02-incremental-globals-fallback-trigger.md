---
created: 2026-10-29T00:00:00-05:00
title: INC-02 incremental path needs a whole-run full fallback when group-hash globals change (BLOCKS flag flip)
area: pipeline
severity: major
blocks: defaulting RUN_MEMORY_INCREMENTAL_ENABLED ON
files:
  - pipeline/orchestrate.py:resolve_run_mode
  - pipeline/memory_candidate.py:group_hash_globals_fingerprint
  - pipeline/fetch.py:get_all_source_rows
  - pipeline/change_detection.py:calculate_data_hash
---

## Problem

The group hash (`calculate_data_hash`) reads four GLOBAL inputs that no row
delta can see: `EXTENDED_CHANGE_DETECTION`, `RATE_CUTOFF_DATE`, the contract-rates
fingerprint (`pipeline.fetch._RATES_FINGERPRINT`) and the subcontractor-rates
fingerprint. When any of them changes, a full run regenerates EVERY affected group
without a single row edit, so the real incremental path (which scopes to the D-04
row-delta candidate) would silently under-regenerate.

Plan 11-13 (G-11-37) models this in the SHADOW only: the verdict is `skipped`
(`would_fallback_full:group_hash_globals_changed`) when the current fingerprint
differs from the previous successful run's `run_ledger.notes.group_hash_globals_fp`.
The REAL incremental path has no such trigger.

## Required work (BLOCKS defaulting `RUN_MEMORY_INCREMENTAL_ENABLED` ON)

The real incremental path needs a whole-run full fallback (a new D-02-style
trigger) when the group-hash globals fingerprint differs from the previous
successful run's `notes.group_hash_globals_fp` (unknown prior -> full).

Why it was not done in 11-13: the rates fingerprint is only final after
`get_all_source_rows` rebinds `_RATES_FINGERPRINT` (PHASE 2), while
`resolve_run_mode` runs before PHASE 2. A pre-PHASE-2 trigger therefore needs a
change to WHEN rate versions load -- pricing / fetch territory under the
byte-identical constraint. That change needs explicit owner approval and its own
plan.

## Status

Open. `RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF (D-11); the flag default flip
is a separate operator-gated PR and MUST NOT happen while this is open.

Links: G-11-37, plan 11-13 (`11-13-PLAN.md`), threat T-11-55.
