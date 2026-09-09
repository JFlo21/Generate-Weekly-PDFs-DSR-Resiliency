---
phase: 14-foreman-helper-2
plan: 04
subsystem: database
tags: [supabase, postgres, pipeline_memory, content-hash, run-memory, helper2]

# Dependency graph
requires:
  - phase: 14-foreman-helper-2
    provides: "14-01's six Helper #2 column titles and the __helper2_foreman row key that fetch.py's payload-reading idiom depends on"
provides:
  - "pipeline_memory.row_state DDL text for four additive nullable Helper #2 columns (helper2_observed/completed/dept/job), owner-applies-later"
  - "pipeline_memory/writer.py payload builder and HASH_FIELDS extended for Helper #2, append-only"
  - "scripts/mem04_passive_compare.py mirrored field split kept in lockstep with HASH_FIELDS via a drift-guard test"
  - "D-14-08-APPLIED decision record: include-now, with the real ~217k one-time production row_event churn quantified"
affects: [14-foreman-helper-2 rollout plans (14-09/14-10), any future HASH_FIELDS change]

# Actuals (#2632)
actuals:
  tokens: 6260
  tasks: 3
  commits: 3
plan_head_before: 6ded22b389b8ae6b5d2d058f80110d600fcc2a92

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive-only schema.sql invariant test (git diff --unified=0, zero removed lines) replacing a phase-scoped blanket freeze once a later phase is explicitly authorised to extend the same table"
    - "Simulated PostgREST SQLSTATE error (42703 column-does-not-exist) as a first-class fail-open test input, not just PGRST* global-kill codes"

key-files:
  created: []
  modified:
    - pipeline_memory/schema.sql
    - pipeline_memory/writer.py
    - scripts/mem04_passive_compare.py
    - tests/test_pipeline_memory_shadow.py
    - tests/test_incremental_read.py
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md

key-decisions:
  - "D-14-08-APPLIED: include-now — the four Helper #2 fields join HASH_FIELDS in the same change as the columns, per D-14-08's recommended option."
  - "The upsert_rows_bulk RPC's jsonb_to_recordset/INSERT column list is deliberately NOT touched in this plan — only row_state's own DDL gains the four columns. The RPC update (making helper2_* actually persist) is deferred to the rollout plans (14-09/14-10), matching the plan's own read_first scope."
  - "The existing with_retry/_error_summary fail-open contract already surfaces a 42703 (column does not exist) SQLSTATE's structural message — no new error-handling code was needed, only a test proving it (per the plan's explicit instruction not to add a new error path)."

patterns-established:
  - "Additive-only schema.sql guard: assert git diff --unified=0 has zero removed lines, instead of a blanket zero-diff freeze, once a phase is explicitly authorised to extend the file."

requirements-completed: [HLP-06]

coverage:
  - id: D1
    description: "row_state carries four additive nullable Helper #2 columns, and a run against a database where those columns do not yet exist still writes every other row_state field without crashing"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests::test_row_without_helper2_columns_yields_nulls_and_still_upserts"
        status: pass
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::MissingHelper2ColumnFailOpenTests::test_undefined_column_does_not_crash_and_other_chunk_still_writes"
        status: pass
    human_judgment: false
  - id: D2
    description: "The Helper #2 fields are members of HASH_FIELDS, appended after the original sixteen with no reordering, so a Helper #2-only change is visible to content_hash"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests::test_changing_only_helper2_observed_changes_content_hash"
        status: pass
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests::test_hash_fields_appended_only_original_sixteen_unmoved"
        status: pass
    human_judgment: false
  - id: D3
    description: "The HASH_FIELDS mirror in scripts/mem04_passive_compare.py lists the same four fields, split personnel/non-personnel the same way Helper #1's fields are split, with a drift guard"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::Mem04FieldMirrorDriftGuardTests::test_union_of_personnel_and_non_personnel_equals_hash_fields"
        status: pass
    human_judgment: false
  - id: D4
    description: "helper2_observed stores the RAW observed Foreman Helping? #2 value, never a resolved or sentinel-substituted value"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests::test_helper2_observed_is_raw_not_the_gated_derivative"
        status: pass
    human_judgment: false
  - id: D5
    description: "The additive DDL is applied by Juan, not by an agent, and the plan records his approval before any writer change assumes the columns exist"
    verification: []
    human_judgment: true
    rationale: "DDL application against the live poeyztlmsawfoqlanucc Supabase project is an owner-only action outside agent scope by hard rule. Not yet applied as of 2026-09-06 (0 helper2_* columns observed live). This SUMMARY only records the approval and the code that tolerates either order; Juan applying the DDL is a separate, unverifiable-by-agent step."

# Metrics
duration: ~9min (continuation from Task 1 checkpoint; Task 1 commit 21:51:32 to Task 3 commit 22:00:10)
completed: 2026-09-06
status: complete
---

# Phase 14 Plan 04: Run Memory Helper #2 Shape Summary

**Four additive nullable Helper #2 columns on `pipeline_memory.row_state`, `HASH_FIELDS` appended (include-now per D-14-08-APPLIED), and the passive-compare script's mirrored field list kept in lockstep by a drift-guard test.**

## Performance

- **Duration:** ~9 min (continuation agent; Task 1's checkpoint decision was answered before this run started)
- **Started:** 2026-09-06T21:51:32-05:00 (Task 1 commit)
- **Completed:** 2026-09-06T22:00:10-05:00 (Task 3 commit)
- **Tasks:** 3/3
- **Files modified:** 6

## Accomplishments

- Recorded and committed `D-14-08-APPLIED`: Juan approved include-now — the DDL is owner-applied (not yet applied as of 2026-09-06) and the hash decision is include-now, with the real one-time production write volume quantified (see Production Impact below).
- Added `helper2_observed TEXT`, `helper2_completed BOOLEAN`, `helper2_dept TEXT`, `helper2_job TEXT` to the `row_state` DDL (additive, nullable, no PK/index/constraint change) and extended the content_hash scoping comment to state they are in-scope business-content columns.
- Extended `pipeline_memory/writer.py`'s `_row_to_payload` to read the four canonical Helper #2 titles using the same raw-not-resolved idiom as Helper #1, and appended the four fields to `HASH_FIELDS` with the original sixteen members' order untouched.
- Proved, with a test that simulates the real PostgREST SQLSTATE `42703` ("column does not exist") response shape rather than assuming, that a database not yet carrying the new columns does not crash the writer and that rows in an unaffected chunk still get written — using the writer's existing `with_retry` fail-open contract with no new error-handling code.
- Mirrored `helper2_observed`/`helper2_dept`/`helper2_job` into `scripts/mem04_passive_compare.py`'s personnel tuple and `helper2_completed` into its non-personnel tuple, and added a drift-guard test asserting the union of the two tuples equals `HASH_FIELDS`.

## Production Impact (per D-14-08-APPLIED — read before enabling the write path further)

- The weekly workflow has carried `RUN_MEMORY_WRITE_ENABLED: '1'` since PR #353 (2026-08-26). Because this plan lands `helper2_*` in `HASH_FIELDS`, the **first scheduled run after this merge reaches production** will change `content_hash` for essentially every observed `row_state` row once. Live read-only figures from the 2026-09-06 probe: `row_state` = 217,491 rows, `row_event` = 218,931 rows, 58 runs in `run_ledger`. Expect roughly one `row_event` per observed row (~217k) on that first run — **real production writes, not shadow-only**, because the write path is already live in production.
- `RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF, so this burst changes no Excel output and triggers no regeneration — it is a write-volume and run-time cost only, not a billing-behavior change.
- The 14-02 parity finding still holds: the shadow comparator hashes within a single run and never reads stored hashes, so this burst cannot disturb a parity streak.
- The additive DDL itself is **owner-applied, by Juan, by hand, in Supabase project `poeyztlmsawfoqlanucc` via the SQL Editor — not yet applied as of 2026-09-06** (0 `helper2_*` columns observed live). No DDL was executed from any agent session, this one included.
- Note also: the `upsert_rows_bulk` RPC's own `jsonb_to_recordset`/`INSERT` column list was deliberately NOT touched in this plan (out of Task 2's read_first scope) — so even once the DDL is applied, the four new `row_state` columns will stay NULL until a later rollout plan (14-09/14-10) updates the RPC to actually persist them. This plan only prepares the column shape, the Python payload/hash contract, and the mirrored field list.

## Task Commits

Each task was committed atomically:

1. **Task 1: Juan approves the additive row_state DDL and the hash-inclusion decision** - `c452f72` (docs) — decision record only; answered before this continuation started
2. **Task 2: row_state Helper #2 columns, payload fields, and the hash decision** - `72dcd8d` (feat, TDD) — schema.sql + writer.py + tests/test_pipeline_memory_shadow.py (Task 2 hunk) + tests/test_incremental_read.py (deviation)
3. **Task 3: Keep the mirrored field list in the passive-compare script in lockstep** - `c9739d7` (feat) — scripts/mem04_passive_compare.py + tests/test_pipeline_memory_shadow.py (Task 3 hunk)

_Task 2 was TDD: the RED tests were written and confirmed failing (`KeyError: 'helper2_observed'`) before the schema.sql/writer.py implementation landed in the same commit; the plan requested no separate RED-only commit._

## Files Created/Modified

- `pipeline_memory/schema.sql` - four additive nullable Helper #2 columns on `row_state`; extended content_hash scoping comment
- `pipeline_memory/writer.py` - `_row_to_payload` reads the four Helper #2 titles raw; `HASH_FIELDS` appended-only with the four new members; docstring extended
- `scripts/mem04_passive_compare.py` - `_PERSONNEL_COLUMNS`/`_NON_PERSONNEL_COLUMNS` extended with the four Helper #2 fields, split the same way Helper #1's are
- `tests/test_pipeline_memory_shadow.py` - Helper #2 hash-sensitivity, raw-not-resolved, no-Helper2-columns, HASH_FIELDS append-only, simulated-42703 fail-open, and mem04 mirror drift-guard tests
- `tests/test_incremental_read.py` - `test_schema_untouched` (Phase 11's blanket freeze) replaced with `test_schema_changes_are_additive_only` (git diff has zero removed lines)
- `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` - `D-14-08-APPLIED` record (Task 1, committed at the start of this continuation)

## Decisions Made

- **D-14-08-APPLIED (include-now):** the four Helper #2 fields join `HASH_FIELDS` in the same change as the columns. Recorded by the owner before Task 2 started; see `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`.
- **RPC update deferred:** `pipeline_memory.upsert_rows_bulk`'s `jsonb_to_recordset`/`INSERT` column list is left untouched in this plan — the columns exist on `row_state` and the Python payload/hash carry the four fields, but nothing persists them into the table until a later rollout plan updates the RPC. This matches Task 2's explicit `read_first` scope (schema.sql lines 82-130 only, never the RPC body) and keeps this plan's blast radius to "prepare the shape," not "flip the switch."
- **No new error-handling code for the missing-column case:** per the plan's explicit instruction, the existing `with_retry`/`_error_summary` contract already classifies SQLSTATE `42703` as a structural, safely-loggable, non-transient, non-global-kill error. Task 2 added a test proving this (`MissingHelper2ColumnFailOpenTests`) rather than adding a new code path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated a stale Phase-11 schema-freeze test to permit this plan's sanctioned schema change**
- **Found during:** Task 2 (running `python -m pytest tests/ -q` after the schema.sql edit)
- **Issue:** `tests/test_incremental_read.py::WatermarkPersistenceTests::test_schema_untouched` ran `git diff --exit-code -- pipeline_memory/schema.sql` and failed on any diff at all — a blanket freeze written during Phase 11 Plan 08 ("Zero schema drift is a hard requirement across the whole phase"), scoped to that phase's own duration, not an eternal law. It blocked the plan's own `<verification>` requirement that the full suite exit 0.
- **Fix:** Replaced the blanket zero-diff check with `test_schema_changes_are_additive_only`, mirroring the exact precedent already established in the same file (`test_workflow_caches_retired_but_schedule_and_budget_survive`, which retired an analogous blanket "workflow untouched" guard once a later phase was explicitly authorised to edit it). The new test asserts `git diff --unified=0 -- pipeline_memory/schema.sql` contains zero removed/modified lines — so a future accidental edit to an existing column, RPC body, or comment is still caught, while this plan's owner-approved, purely-additive four-column insertion is not.
- **Files modified:** `tests/test_incremental_read.py`
- **Verification:** `python -m pytest tests/ -q` — 2206 passed, 1 skipped (up from the 2196/1 baseline)
- **Committed in:** `72dcd8d` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix only relaxed an obsolete phase-scoped assertion to match this plan's own sanctioned change; it added no new behavior and touched no file outside the test suite. No scope creep.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

**A Supabase DDL application requires manual action from Juan.** Per D-14-08-APPLIED:
1. Apply the four additive nullable columns to `pipeline_memory.row_state` in Supabase project `poeyztlmsawfoqlanucc` via the SQL Editor: `helper2_observed TEXT`, `helper2_completed BOOLEAN`, `helper2_dept TEXT`, `helper2_job TEXT` (see `pipeline_memory/schema.sql` for the exact DDL text in context).
2. No urgency either way — both orders (DDL before or after this code merges) are safe by design and proven by this plan's tests. The RPC does not yet reference these columns (deferred to a later rollout plan), so applying the DDL now has zero behavioral effect until that RPC update lands.
3. Be aware: once `HASH_FIELDS` reaches production (already true after this plan merges, since `RUN_MEMORY_WRITE_ENABLED` is live), the next scheduled run will emit a one-time burst of roughly 217k `row_event` rows. This is expected, bounded, and does not affect Excel output or trigger regeneration (`RUN_MEMORY_INCREMENTAL_ENABLED` is OFF) — noted here so it isn't mistaken for an anomaly.

## Next Phase Readiness

- `pipeline_memory.row_state`'s Helper #2 column shape, the Python payload/hash contract, and the mem04 mirror are all in place and tested.
- The `upsert_rows_bulk` RPC still needs updating (jsonb_to_recordset + INSERT + ON CONFLICT column lists) before Helper #2 values actually persist into `row_state` — this is explicitly deferred to the rollout plans (14-09/14-10) per the decision record, not a gap in this plan's own scope.
- No blockers for continuing Phase 14.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-06*

## Self-Check: PASSED

All files created/modified confirmed present on disk; all three task commit
hashes (`c452f72`, `72dcd8d`, `c9739d7`) confirmed in `git log --oneline --all`.
