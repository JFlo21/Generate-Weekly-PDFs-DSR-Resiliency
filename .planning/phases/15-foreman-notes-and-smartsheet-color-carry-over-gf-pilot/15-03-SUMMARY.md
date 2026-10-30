---
phase: 15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot
plan: 03
subsystem: pipeline
tags: [foreman-notes, change-detection, hash-fingerprint, discovery-mapping]
requires: [15-01, 15-02]
provides:
  - "discovery maps 'Foreman Notes' (exact title) only when the effective scope is not off; MAPPING_SCHEMA_MARKER gains '+fn1' only then"
  - "calculate_data_hash: pilot-only NOTES_FP meta token after SUB_RATES_FP"
  - "row_group_hash_fingerprint: pilot-only third element; group_hash_globals_fingerprint: pilot-only globals component"
affects: [15-04, 15-05, 15-06, 15-07]
tech-stack:
  added: []
  patterns:
    - "one-line pilot-gated seams calling into pipeline/foreman_notes.py; off / non-pilot payloads byte-identical"
key-files:
  created:
    - tests/test_foreman_notes_hash.py
    - tests/test_foreman_notes_coverage.py
  modified:
    - pipeline/discovery.py
    - pipeline/change_detection.py
    - pipeline/memory_candidate.py
key-decisions:
  - "NOTES_FP is appended after the SUB_RATES_FP block and before the metadata update; _extended_row_fields, canonical_sorted_rows and the per-row loop are untouched (non-pilot byte identity, AST-safe)"
  - "Globals fingerprint list gets the foreman_notes component only when non-empty, so the off payload equals the legacy 4-element payload (asserted against an independently computed digest)"
  - "Coverage guards live in a new file; tests/test_row_state_group_hash_domain.py is unchanged"
requirements-completed: [FN-04, FN-08, FN-09, FN-10]
requirements-partial: []
status: complete
commits: 3
plan_head_before: ca511a919242edc3f3e4703030e5d8aedd05e5b4
plan_head_after: a6991d21c9438893306ab499aab46c46fb3f6668
metrics:
  duration: "~30m"
  completed: 2026-10-29
actuals:
  tokens: 21000
  tasks: 3
  commits: 3
---

# Phase 15 Plan 03: Notes data path (mapping, group hash, fingerprints) Summary

Foreman Notes now flows from discovery mapping into the pilot group hash (`NOTES_FP`), the Phase 11 row fingerprint and the globals fingerprint, all pilot-gated; off and non-pilot output is byte-identical to the BASE golden for all ten variant families.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Tracer: discovery mapping to group hash for one pilot row | 1dbaae0 |
| 2 | Golden identity matrix, NOTES_FP behaviour, full-vs-delta parity | 2d3b431 |
| 3 | AST coverage guards for the new hash inputs | a6991d2 |

## Verification

- Task 1 verify (hash + baseline + row_state domain): 28 passed, 96 subtests.
- Task 2 verify: `tests/test_foreman_notes_hash.py` 17 passed, 35 subtests.
- Task 3 verify (coverage + row_state domain): 30 passed, 74 subtests.
- Full suite before plan (15-02 baseline): 2690 passed, 3 skipped, 724 subtests.
- Full suite after plan: 2719 passed, 3 skipped, 787 subtests (+29 tests, zero new failures).
- `MAPPING_SCHEMA_MARKER`: default `helper2-v1`; `TEST_MODE=true` with both write flags 0 gives `helper2-v1+fn1`; `SKIP_UPLOAD=true` alone gives `helper2-v1`.
- Non-comment `NOTES_FP=` occurrences in change_detection.py: 1. `py_compile` of discovery, change_detection, memory_candidate and the facade is clean. 6-gate harness deferred to 15-05 as planned.

## Deviations from Plan

None - plan executed as written.

## Generic row-iteration scan (Task 3 record)

Scanned `pipeline/*.py` and `pipeline_memory/*.py` for loops/comprehensions over `.items()/.keys()/.values()` of a row-like receiver. Exactly two hits, both reviewed and allowlisted with reasons in the test:
- `memory_candidate.row_group_hash_fingerprint`: copies the row minus `DERIVED_KEY_SOURCES`, then reads only named fields through `_extended_row_fields`; the copy is never serialised.
- `excel.generate_excel` (line ~251): logs up to 15 non-dunder column NAMES (keys only, no values) in a "Job # not found" warning; no note or colour value reaches a log.
All other `.items()` hits iterate group, mapping or counter dicts, not source rows.

## Known Stubs

None.

## Threat Flags

None. No new endpoints, auth paths or schema; note text never reaches Supabase (only SHA-256 digests via the existing `group_hash_fp` slot; `HASH_FIELDS` unchanged and asserted).

## Requirements

Marked Complete: FN-04 (mapping behind marker bump; full/delta parity proven), FN-08 (NOTES_FP), FN-09 (row + globals fingerprint with coverage test and parity), FN-10 (colour excluded from every hash/fingerprint/payload, behaviour and AST guards). FN-07 and FN-11 remain Pending (Excel and pipeline_memory seams in later plans).

## Notes for later plans

- Enabling the pilot (and a later pilot to all flip) regenerates each affected group once (D-15-11, owner-settled).
- The delta-read path only maps notes when `map_delta_sheet_rows`'s source `column_mapping` carries them; this follows from discovery's `+fn1` marker forcing re-validation, so no separate fetch change was needed.

## Self-Check: PASSED

- tests/test_foreman_notes_hash.py, tests/test_foreman_notes_coverage.py: FOUND
- Commits 1dbaae0, 2d3b431, a6991d2: ancestors of HEAD
