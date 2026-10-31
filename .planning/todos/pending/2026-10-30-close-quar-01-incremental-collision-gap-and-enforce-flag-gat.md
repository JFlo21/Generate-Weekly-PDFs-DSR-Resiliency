---
created: 2026-10-30T17:28:16.807Z
title: Close QUAR-01 incremental collision gap and enforce the incremental flag gate in code
area: pipeline
severity: major
blocks: defaulting RUN_MEMORY_INCREMENTAL_ENABLED ON
depends_on: PR #439 merged (adds _source_wr_raws_by_key and the QUAR-01 row in docs/ai/known-bugs.md)
files:
  - pipeline/config.py:527
  - pipeline/orchestrate.py:_run_phase2_incremental
  - pipeline/orchestrate.py:5172
  - pipeline_memory/reader.py:map_affected_to_sheets
  - tests/test_incremental_read.py
  - tests/test_regen_debt_carry.py
  - docs/ai/known-bugs.md
---

## Problem

PR #439 narrowed QUAR-01 but left two gaps. Line numbers below are from
`origin/fix/regen-debt-unreached` at `52bbc61`; re-check them after #439 merges.

1. **Collision blind spot.** `map_affected_to_sheets` selects sheets by exact
   `(wr, week_ending)` pair. An incremental run therefore never reads a sheet
   holding the other raw WR when that raw WR is in a different week, so the source
   scan misses the collision and the in-scope group can upload against the shared
   `target_map` key.
2. **Unenforced gate.** Nothing in code stops someone setting
   `RUN_MEMORY_INCREMENTAL_ENABLED=1`. Every gate is written down only in docs and
   todos.

## Evidence (2026-10-30)

- **A raw-WR list and schema change are NOT needed.** This corrects the #439
  known-bugs text. A collision the scan can detect needs a key that holds `_` or is
  50 characters long, because the sanitizer only replaces characters with `_` and
  truncates at 50. `row_state.wr` can find the sheets to read, provided `row_state`
  is current (Task 2 adds that guard). An ad hoc check of 19,438 colliding keys found
  0 that failed this test.
- **Out of scope for the predicate:** `.split('.')[0]` also folds raws ("12.5" and
  "12.7" both become "12") before any scan sees them, on every run mode. Check source
  data for dotted WRs at execution time; if any exist, file that separately.
- **Exposure is tiny.** `row_state` has 818 distinct WRs: 1 contains `_`, 0 reach
  50 characters, 6 are non-numeric.
- **Pair mapping already covers same-week collisions.** Only cross-week collisions
  escape it.
- **Plain WR-wide widening is rejected.** It costs more than this needs: 2.6 sheets
  per WR on average, max 8, of 139, and up to about 156k rows for a 500-WR chunk.
- **The live `group_state` readers are not truncated today.** Run 41078401767
  resolved 2,182 attachment identities and 2,178 hashes through a chunk holding 2,153
  rows, so production's PostgREST row cap is above 2,153. The exact cap is unknown.
  That says nothing about `map_affected_to_sheets`, whose chunks can return far more
  rows (Task 2).
- **Independent review (2026-10-30)** found the gaps Task 2 now covers. Registry pass
  2 and `get_all_source_rows` failure handling were confirmed in code.
- Code paths were read, not exercised. Nothing here is reproduced yet.

## Solution

Route through `/gsd:quick` from a fresh branch off `master` after #439 merges. One
PR. Protected area: billing pipeline. No schema, workflow, or flag default change.
With the flag off, the run must stay byte-identical.

### Task 1: Enforce the gate (`pipeline/config.py`)

- Keep the env read as `RUN_MEMORY_INCREMENTAL_REQUESTED`.
- Add `RUN_MEMORY_INCREMENTAL_OPEN_GATES`, a tuple of gate ids.
- Set `RUN_MEMORY_INCREMENTAL_ENABLED = requested and not open_gates`.
- At run start, if requested and gated, log a WARNING and send a Sentry message
  naming the open gates. The run continues as full. No env bypass: removing a gate
  takes a reviewed code change.
- Gate at config, not in `resolve_run_mode`, so the shadow comparator
  (`orchestrate.py:5172`) keeps running and parity evidence keeps accruing. Tests
  that pass `incremental_enabled=True` are unaffected.
- Put the decision in a pure helper and test that. The flag is imported by value at
  `orchestrate.py:123`, so a reload-based test would mislead.
- Give the run ledger a distinct reason when the flag is set but gated. The current
  `flag_off: ... is not set` text (`orchestrate.py:1068`) would be false.

Initial gates, each to be confirmed open at execution time:

| Gate id | Source | Closes when |
| --- | --- | --- |
| `QUAR-01` | `docs/ai/known-bugs.md` | Task 2 ships |
| `INC-02-GLOBALS` | `2026-10-29-inc02-incremental-globals-fallback-trigger.md` | Its todo closes |
| `SUB-09-KEEP-HISTORICAL` | `.planning/STATE.md` (D-14-FOLLOWUPS) | `keep_historical` honoured, with fixture and dry run |
| `AUD-02-RECHECK` | `2026-10-29-audit-memory-open-findings-incremental-recheck.md` | Owner picks an option |
| `INC-04-STREAK` | `website/docs/runbook/operations.md:244` | The PR removing it records 5 passes from `get_parity_streak()` |

### Task 2: Close the blind spot (dormant path only)

- Add a pure predicate: `'_' in key or len(key) >= 50`. Use one shared 50 limit, not
  a new literal.
- Add a reader that maps WRs to sheet ids from `row_state` with no week filter,
  ordered and paged with `.range()`. Return `None` when it cannot confirm, and make
  no call for empty input.
- In `_run_phase2_incremental`, after the pair mapping, run that reader only for
  candidate WRs that pass the predicate and union the sheet ids into
  `mapped_sheet_ids`. `None` returns `ok=False` with a new
  `trigger_collision_scope_unconfirmed` reason, so the run goes full.
- Page `map_affected_to_sheets` too. It has no `.range()`, and a truncated response
  returns `ok=True` with too few sheets, so a group built from partial rows could
  replace a complete billing file. Keep its "cannot confirm returns empty" contract.
- Add a run-level trigger: if the previous run's `notes.mem_confirmed` is not true,
  resolve to full. Registry pass 2 advances the watermark even after a partial memory
  write (`orchestrate.py:3458-3470`), so a sheet can look unchanged while `row_state`
  is stale.
- Check read failures in `_run_phase2_incremental`. `get_all_source_rows` records a
  failed sheet and continues, and this path never checks. Capture failures from both
  reads, because the 2b call resets the tracker, then hold every collision-capable
  group for that run.
- Groups stay filtered to candidate pairs. Extra rows reach only the collision scan
  and other `all_rows` consumers. Review found these safe, but attribution prefetch
  and snapshot drift were not fully traced; finish that check here.

### Task 3: Docs

- Replace the known-bugs QUAR-01 row, including its wrong "needs a raw-WR source"
  sentence and its "covers every row the run read" overclaim (a raw removed by
  `EXCLUDE_WRS` is not scanned). Fix the matching comment in
  `pipeline/orchestrate.py`.
- Add a `memory-bank/living-ledger.md` entry.
- Update `.github/prompts/configuration-environment.md` and the website environment
  reference for the gate.

## Tests (write the failing test first)

- Cross-week collision on an unread sheet: fails today; after the fix the in-scope
  group is quarantined and nothing uploads. The twin is out of scope, so it is not
  in the quarantined group keys.
- Predicate against the real sanitizer: any two distinct raws with the same key pass.
- Numeric-only candidates make no extra query and read the same sheets as today.
- Both readers: paging across pages, empty input, and failure.
- Reader failure resolves the run to full.
- Previous run with `mem_confirmed` false or missing resolves to full.
- A failed sheet in either read holds collision-capable groups and leaves numeric
  groups alone.
- Env flag set: effective flag False, gated ledger reason, warning emitted, shadow
  condition still true.
- Every gate id appears in `docs/ai/known-bugs.md`. Add missing rows in Task 3.

Before Task 1, check that no test depends on the env-derived flag being True
(`tests/test_incremental_read.py` lists it in `_ENV_KEYS`).

## Validation

- `pytest tests/ -v`
- `bash scripts/run_6_gates.sh`
- `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py`
- Independent `production-risk-reviewer` pass before merge, then one Lattice `/review`.

## Separate finding: file as QUAR-02, do not fix in this PR

Read from code, not reproduced. Both cases can happen on full runs, so "unreachable
while every run is full" is too broad. Both need a `_` or 50-character key, so at
most 1 of 818 keys qualifies today.

- **Target side:** if the target sheet holds raw X and the source shows only raw Y
  with the same key, the scan sees one raw and Y routes to X's row. The upload path
  then calls `delete_old_excel_attachments` on that row, which can delete X's file
  when week, variant, and identifier match. The PPP map shares the builder, so it has
  the same gap. X can exist in source but be excluded or unaccepted.
- **Failed read:** a failed sheet on a full run hides the twin the same way.

`_build_target_sheet_map` already has the raw value and drops it. Add the comparison
as log-only first, limited to collision-capable keys: source reads `cell.value` first
while the target reads `display_value`, and a false quarantine would stop a billing
upload.

## Status

Open. Closing QUAR-01 removes one gate only; the flag stays off until all gates
close. The flag flip remains a separate operator PR.
