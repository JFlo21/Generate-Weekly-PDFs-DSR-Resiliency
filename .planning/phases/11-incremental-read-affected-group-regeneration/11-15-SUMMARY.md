---
phase: 11-incremental-read-affected-group-regeneration
plan: 15
subsystem: verification
tags: [owner-checkpoint, post-deploy, billing-impact]
requirements-completed: []
completed: 2026-10-30
---

# Plan 11-15 Summary: G-11-37 post-deploy check

## Outcome

- Task 1, billing-impact check: **PASS**. The first post-merge run, 41013512543, uploaded 8
  and generated 8 groups; the two prior runs had 7 and 10. Each generated group came from new
  rows (all 83 inserts on its 7 pairs). The one-time `row_state` re-key regenerated nothing.
- Task 2, the `get_parity_streak()` reading at 2026-10-30T07:16:29Z: streak 0, stopped at
  pre-fix run 40757294483.1 (`fail`). Recorded as-is; not a gate (D-09 as amended by PR #435).
- Recorded in `11-VERIFICATION.md` `#### G-11-37 Post-Deploy Observation`, with an INC-04
  note in `REQUIREMENTS.md`. Todo `2026-09-14-inc02-user-variant-candidate-divergence.md`
  moved to `todos/done/`.

## Not changed

No code, test, workflow, schema or UAT change. `11-VERIFICATION.md` `status:` / `score:`
and `11-UAT.md` are left for `/gsd:verify-work`. `RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF;
the globals-fallback todo is untouched.

## Observation

The ledger's `rows_changed` (6,378) is below the live row count that 11-11-SUMMARY
expected; `row_event` holds 256,001 update events for the run. It has no billing effect and
is recorded as-is.
