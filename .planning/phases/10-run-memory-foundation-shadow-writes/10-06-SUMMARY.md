---
phase: 10-run-memory-foundation-shadow-writes
plan: 06
subsystem: database
tags: [supabase, postgres, pipeline_memory, shadow-write, fail-open, real-data-proof, run_ledger, row_event, idempotence, billing-pipeline]

# Dependency graph
requires:
  - phase: 10-run-memory-foundation-shadow-writes
    provides: "plan 10-01's pipeline_memory package + schema.sql, plan 10-02's row_state/row_event writer, plan 10-03's sheet_registry/group_state writer, plan 10-05's shadow-rollout groundwork -- this plan applies the schema live and proves the whole stack against real production data"
provides:
  - "scripts/compare_control_run.py + tests/test_compare_control_run.py -- a canonicalized (wall-clock-artifact-aware) control-vs-shadow Excel/run_summary comparison harness"
  - "The pipeline_memory schema LIVE on production project poeyztlmsawfoqlanucc: 5 tables, RLS, upsert_rows_bulk + purge_row_event_slice, pg_cron retention, exposed to PostgREST, locked down from anon/authenticated -- with the service_role GRANT gap found and fixed"
  - "Two real bugs found and fixed against real production data: run_ledger_finish's NOT-NULL mode omission (23502), and the comparator's raw-byte-hash false positive against openpyxl's wall-clock artifacts"
  - "Four real production runs' worth of rollout evidence (control, shadow, idempotence, fail-open) recorded in memory-bank/living-ledger.md, naming the flag-flip PR as a separate, later, reviewed follow-up"
affects: [11-incremental-reads-and-flag-flip, any-future-phase-reading-pipeline_memory]

# Actuals (#2632)
actuals:
  tokens: 13470
  tasks: 3
  commits: 8

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Canonicalized xlsx content hashing: exclude docProps/core.xml, normalize the 'Report Generated On' cell, hash the rest -- a raw file-byte hash can never prove two real (non-frozen-clock) pipeline runs are behaviorally identical, only a canonicalized one can"
    - "run_ledger_finish must always resend mode even though run_ledger_start already set it: PostgREST's merge-duplicates upsert validates the proposed row against NOT NULL constraints from ONLY the payload's own columns, before conflict resolution -- omitting any NOT-NULL-no-DEFAULT column always fails, even on an UPDATE-only path"
    - "SKIP_UPLOAD's crash-consistency withhold contract (which protects hash_history.json) also, as a side effect, withholds group_state's entire flush on every dry run -- a real assumption can only be resolved by a real (non-SKIP_UPLOAD) write, never by more dry runs"

key-files:
  created: []
  modified:
    - scripts/compare_control_run.py
    - tests/test_compare_control_run.py
    - pipeline_memory/writer.py
    - tests/test_pipeline_memory_shadow.py
    - pipeline_memory/schema.sql
    - memory-bank/living-ledger.md

key-decisions:
  - "compare_control_run.py hashes canonicalized xlsx content (excluding docProps/core.xml, normalizing the 'Report Generated On: <timestamp>' cell) instead of raw file bytes -- the original Task 1 design assumed content would be stable modulo the filename timestamp, but pipeline/excel.py embeds datetime.now() TWICE per save (openpyxl's own save metadata plus a footer cell), which would make ANY two real runs -- even two control-only runs -- compare unequal"
  - "run_ledger_finish now always includes mode (defaulting to 'full') in its upsert payload, matching run_ledger_start's hard-coded call-site value -- PostgREST's upsert validates NOT NULL constraints against the payload's own column list before conflict resolution, so a column omitted from an UPDATE-only upsert can still raise a fresh insert-shaped violation"
  - "Success criterion 4's 'byte-identical' claim is proven at the Excel-CONTENT level (100% match across all 17 directly-comparable identities after canonicalization), not at the group-SELECTION level -- a live 120-sheet/~209K-row production dataset cannot be held perfectly still across a ~50-90 minute control-to-shadow gap without a fetch-snapshot/replay capability this phase does not build; documented honestly rather than forced to a fabricated full-comparator PASS"
  - "group_state's attachment-preservation COALESCE behavior is explicitly left UNRESOLVED: SKIP_UPLOAD's per-task 'skip_upload' result is never in the ('uploaded','skipped') set the flush treats as OK, so EVERY group is withheld from group_state on EVERY dry run by the same crash-consistency contract that protects hash_history.json -- no amount of additional SKIP_UPLOAD runs can prove this assumption; it needs the flag-flip PR's own first real run or a dedicated mock-based integration test"

requirements-completed: [MEM-01, MEM-02, MEM-03]

coverage:
  - id: D1
    description: "Canonicalized control-vs-shadow Excel/run_summary comparison harness (Task 1), now proven against real production output"
    requirement: MEM-03
    verification:
      - kind: unit
        ref: "tests/test_compare_control_run.py (20 tests incl. TestRealXlsxWallClockCanonicalization)"
        status: pass
      - kind: other
        ref: "python scripts/compare_control_run.py over real runs 1+2 -- zero content-hash-mismatch errors across all 17 overlapping identities"
        status: pass
    human_judgment: false
  - id: D2
    description: "The pipeline_memory schema is live on poeyztlmsawfoqlanucc: 5 tables, RLS, RPCs, pg_cron retention, exposed to PostgREST, and locked down from anon/authenticated -- with the service_role GRANT gap found at the operator checkpoint and fixed in schema.sql"
    requirement: MEM-01
    verification:
      - kind: other
        ref: "Operator checkpoint (Task 2) live verification: 5 tables/RLS/policies/functions/indexes/pg_cron present; anon+authenticated have no USAGE/SELECT; service_role has schema USAGE + table SELECT/INSERT/UPDATE (no DELETE) after commit 2df3b25"
        status: pass
    human_judgment: true
    rationale: "Live production schema/permission state was verified once by the operator+orchestrator at the Task 2 checkpoint against the real Supabase dashboard/SQL editor -- not re-derivable from a test run in this repo."
  - id: D3
    description: "Real-data proof of shadow-write behavior neutrality (control vs shadow), idempotence (second run adds only genuinely-changed row_event rows), and fail-open (Supabase unreachable degrades to a WARNING with the full output set intact) -- against live production data on poeyztlmsawfoqlanucc"
    requirement: MEM-02
    verification:
      - kind: other
        ref: "Four real SKIP_UPLOAD=true production runs (control/shadow-A/shadow-B/fail-open), documented in memory-bank/living-ledger.md [2026-08-25 18:37] with exact row/event/run_ledger counts and query evidence"
        status: pass
    human_judgment: false
  - id: D4
    description: "Two real bugs found and fixed during real-data execution: run_ledger_finish's NOT-NULL mode omission (23502 on every finish upsert), and compare_control_run.py's raw-byte-hash false positive against openpyxl's wall-clock artifacts"
    requirement: MEM-03
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::RunLedgerTracerTests::test_start_then_finish_produce_exactly_two_run_ledger_upserts (mode assertion); tests/test_compare_control_run.py::TestRealXlsxWallClockCanonicalization"
        status: pass
      - kind: other
        ref: "Live reproduction + live re-verification against poeyztlmsawfoqlanucc (run_ledger_finish fix); forensic zip-member diff of a real control/shadow pair (comparator fix)"
        status: pass
    human_judgment: false

duration: ~4h10m (dominated by four real ~49-56min production Smartsheet fetch+audit runs, not by code changes)
completed: 2026-08-25
status: complete
---

# Phase 10 Plan 06: Run-Memory Foundation (real-data rollout evidence) Summary

**The `pipeline_memory` schema is live on production project `poeyztlmsawfoqlanucc` and proven behaviour-neutral, idempotent, and fail-open against real ~209K-row/120-sheet production data across four real `SKIP_UPLOAD=true` runs -- surfacing and fixing two real bugs (a `run_ledger_finish` NOT-NULL violation and a comparator false positive) that mocked tests alone could never have caught, while `RUN_MEMORY_WRITE_ENABLED` stays OFF in production.**

## Performance

- **Duration:** ~4h10m wall-clock, but only a small fraction is code/investigation time -- four real production pipeline runs (control 56.4min, shadow-A 54.5min, shadow-B 53.2min, fail-open 48.8min) dominate the total, each bounded by the existing Smartsheet fetch (~15-17min) and the pre-existing `billing_audit` rate-sanity audit (~30-33min), neither of which `MAX_GROUPS` reduces.
- **Started:** 2026-08-25T19:40:00Z (approx., Task 3 resume after the Task 2 checkpoint)
- **Completed:** 2026-08-25T23:41:37Z
- **Tasks:** 3 (Task 1 comparison script, Task 2 operator checkpoint -- both already complete on entry; Task 3 real-data runs -- this session)
- **Files modified:** 6

## Accomplishments
- **Task 2 checkpoint (completed by Juan + orchestrator verification before this session):** `pipeline_memory/schema.sql` applied to `poeyztlmsawfoqlanucc`; schema exposed to PostgREST and cache reloaded; a real GRANT gap found (the original file granted `service_role` only `EXECUTE` on the RPCs -- no schema `USAGE`, no table `SELECT`/`INSERT`/`UPDATE` -- every shadow write would have failed `42501` silently) and fixed in commit `2df3b25`.
- **Real bug 1 found and fixed:** `run_ledger_finish`'s upsert failed `400`/`23502` (`not_null_violation` on `mode`) on every real call -- PostgREST's merge-duplicates upsert validates `NOT NULL` constraints against the payload's own columns before conflict resolution, so omitting `mode` (already set by `run_ledger_start`) still raised a real violation on the UPDATE path. Confirmed live, fixed (`pipeline_memory/writer.py`, commit `514589a`), re-confirmed live.
- **Real bug 2 found and fixed:** `compare_control_run.py`'s raw file-byte SHA-256 reported "content hash mismatch" for every one of the first real control/shadow comparison's 17 overlapping identities -- `pipeline/excel.py` embeds `datetime.now()` twice per save (openpyxl's own `docProps/core.xml` timestamps, and a "Report Generated On" footer cell), so no two real runs could ever compare byte-equal. Fixed via a canonicalized hash that excludes/normalizes those two artifacts (commit `cf3568b`); re-run against the same real pair showed **zero** content differences across all 17 overlapping identities.
- **Four real production runs executed** (all `SKIP_UPLOAD=true`, zero Smartsheet writes, `generated_docs/hash_history.json` verified byte-identical before and after every run): CONTROL (flag off), SHADOW A (flag on, compared against control), SHADOW B (flag on again, idempotence), FAIL-OPEN (flag on, `SUPABASE_URL` pointed at an unreachable `.invalid` host).
- **Idempotence proven with direct query evidence:** a sampled `row_state` row unchanged since shadow-A shows `last_seen_run` advanced to shadow-B's run id while `last_changed_run` stayed at shadow-A's -- true for 209,286 of 209,464 rows (99.9%); the remaining 178 genuinely-new/changed rows (real Smartsheet edits during the ~48-minute gap) correctly got new `row_event` rows.
- **Fail-open proven clean:** with Supabase fully unreachable, the memory-write phase's circuit breaker opened after 3 consecutive exhausted retries and finished in 29.5s (not a 120-sheet retry storm); the run completed `success: true` with its full expected output, zero tracebacks, and `run_ledger` gained **zero** rows from that run (both start and finish failed cleanly -- fail-open held for the whole run, not just individual calls).
- **Living Ledger rollout-evidence entry** appended (`memory-bank/living-ledger.md` `[2026-08-25 18:37]`, commit `26cb11d`) with the full run table, both bugs, the honest scope-drift analysis, both open assumptions, and the flag-flip PR's explicit preconditions.

## Task Commits

Task 1 and Task 2 were completed in prior sessions (see `.planning/phases/10-run-memory-foundation-shadow-writes/10-06-PLAN.md` for their commits: `a13e47a`/`9aa220d` Task 1 RED/GREEN, `2df3b25` the Task-2-checkpoint GRANT fix). Task 3's commits, this session:

1. **Task 3 (real-data runs) -- Bug fix: run_ledger_finish mode omission** - `514589a` (fix)
2. **Task 3 (real-data runs) -- Bug fix: comparator wall-clock canonicalization** - `cf3568b` (fix)
3. **Task 3 (real-data runs) -- Living Ledger rollout evidence** - `26cb11d` (docs)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP/REQUIREMENTS update)

## Files Created/Modified
- `scripts/compare_control_run.py` - `_canonical_hash_of_xlsx()` excludes `docProps/core.xml` and normalizes the "Report Generated On" cell before hashing; falls back to a raw byte hash for non-zip input (existing test fixtures, or a genuinely corrupt xlsx)
- `tests/test_compare_control_run.py` - `_write_real_xlsx_zip()` fixture builder plus `TestRealXlsxWallClockCanonicalization` (2 new tests: identical-content-different-wall-clock PASSes, a genuine billing-cell difference still FAILs)
- `pipeline_memory/writer.py` - `run_ledger_finish()` pops an optional `mode` override (default `"full"`) and always includes it in the upsert payload
- `tests/test_pipeline_memory_shadow.py` - regression assertion locking `finish_payload["mode"] == "full"`
- `pipeline_memory/schema.sql` - (from the Task 2 checkpoint, `2df3b25`) new `GRANT` block: schema `USAGE`, table `SELECT`/`INSERT`/`UPDATE`, sequence `USAGE`, default privileges for `service_role` -- `DELETE` deliberately withheld
- `memory-bank/living-ledger.md` - `[2026-08-25 18:37]` dated rollout-evidence entry

## Decisions Made
See `key-decisions` in frontmatter. All four are load-bearing: two fix real defects that would otherwise make either the write path (`run_ledger_finish`) or the proof tool (`compare_control_run.py`) non-functional against real data; two are honest scope decisions (the canonicalized-content proof standard for success criterion 4, and leaving `group_state`'s COALESCE assumption explicitly open) documented rather than papered over.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `run_ledger_finish` upsert failed `400`/`23502` on every real call**
- **Found during:** Task 3, the first real SHADOW A run's finish hook
- **Issue:** `schema.sql`'s `run_ledger.mode` column is `NOT NULL` with no `DEFAULT`. PostgREST's merge-duplicates upsert builds `INSERT ... ON CONFLICT (run_id) DO UPDATE` scoped to only the payload's own columns; Postgres validates the proposed row against `NOT NULL` BEFORE conflict resolution, so omitting `mode` (only sent by `run_ledger_start`) raised `not_null_violation` on every finish call, even though the actual write is an UPDATE of an already-existing row.
- **Fix:** `run_ledger_finish()` now pops an optional `mode` override from `counters` (defaulting to `"full"`, matching `run_ledger_start`'s hard-coded call-site value) and always includes it in the payload.
- **Files modified:** `pipeline_memory/writer.py`, `tests/test_pipeline_memory_shadow.py`
- **Verification:** Direct live reproduction against `poeyztlmsawfoqlanucc` before the fix (`23502 not_null_violation`, confirmed no partial row inserted), then a direct live re-verification after the fix (`200 OK`, both start and finish rows persisted correctly); Run 3 (shadow-B) confirmed the fix in production with a full `status='success'`, `finished_at` populated `run_ledger` row.
- **Committed in:** `514589a`

**2. [Rule 1 - Bug] `compare_control_run.py`'s raw file-byte hash could never pass against real xlsx output**
- **Found during:** Task 3, the first real control-vs-shadow comparison (Run 1 vs Run 2)
- **Issue:** `pipeline/excel.py` embeds `datetime.datetime.now()` twice per saved workbook -- openpyxl's own `docProps/core.xml` created/modified timestamps, and a "Report Generated On: `<timestamp>`" footer cell (~line 477) -- both differing on every save regardless of row content. The first real comparison reported "content hash mismatch" for all 17 overlapping identities; a forensic zip-member diff of one such pair confirmed the byte differences were confined to EXACTLY those two members, zero billing-content bytes differing.
- **Fix:** `_canonical_hash_of_xlsx()` excludes `docProps/core.xml` entirely and normalizes the "Report Generated On" cell to a fixed placeholder before hashing worksheet XML; any other byte difference (real data or formatting) still changes the hash. Falls back to a raw byte hash for anything that isn't a valid zip.
- **Files modified:** `scripts/compare_control_run.py`, `tests/test_compare_control_run.py`
- **Verification:** Re-running the comparator against the SAME real control/shadow pair after the fix reported **zero** `content hash mismatch` errors (down from 17); two new regression tests using a minimal real xlsx-shaped zip fixture (identical content + differing wall-clock artifacts PASSes; a genuine billing-cell difference still FAILs).
- **Committed in:** `cf3568b`

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs, both discovered ONLY because this task ran against real production data instead of mocks -- exactly what Task 3 exists to catch)
**Impact on plan:** Both fixes were necessary for the plan's own stated purpose (a working, honest neutrality proof) to be achievable at all. No scope creep -- both are narrowly scoped to the exact defect found, with regression tests added in the same commit.

## Issues Encountered

**Success criterion 4's literal "byte-identical, full-comparator-PASS" claim is not achievable against this live dataset without further tooling.** After the canonicalization fix, Excel CONTENT is proven 100% identical across every directly-comparable (overlapping) group between control and shadow. `scripts/compare_control_run.py` still exits non-zero because the `MAX_GROUPS=30` order-stable truncation selected a different first-30 slice between the two runs (13 identities only-in-control, 13 only-in-shadow) and three `run_summary` fields drifted (`rows_fetched`, `fingerprint_changes_detected`, `snapshots_already_frozen`) -- all mechanically explained by `rows_fetched` genuinely growing (209,237 -> 209,287, +50 real rows) during the ~68-minute control-to-shadow gap on a live, continuously-edited 120-sheet/~209K-row production dataset. This is a genuine limitation the original plan's "~550 rows" cost assumption did not anticipate (actual production scale today is ~209,400 rows across 120 folder-discovered sheets, not ~550 rows across 13+ sheets -- `CLAUDE.md`'s Project Summary predates the folder-discovery expansion and should be corrected in a future docs-only pass). A byte-for-byte zero-drift comparator PASS would require either a maintenance-window run with zero concurrent Smartsheet edits, or a fetch-snapshot/replay capability neither this plan nor any prior Phase 10 plan builds. Recorded honestly in the Living Ledger rather than forced to a fabricated PASS, per this task's explicit instruction not to paper over a non-neutral diff.

**`group_state`'s COALESCE/attachment-preservation assumption could not be resolved by any of the four SKIP_UPLOAD runs.** `_group_upload_ok` treats a SKIP_UPLOAD dry-run's `'skip_upload'` task result as NOT ok, so `_build_group_state_flush` withholds every group on every dry run -- the same crash-consistency contract that protects `hash_history.json`. `group_state` stayed at 0 rows across all four real runs. This is expected, correct, by-design behavior, not a bug -- but it means the plan's own open assumption (a) genuinely cannot be resolved without either the flag-flip PR's first real (non-SKIP_UPLOAD) run, or a dedicated mock-based integration test. Documented as an explicit open item in the Living Ledger rather than asserted as confirmed.

**`Task 3`'s `<verify>` block's `scripts/compare_control_run.py --control-dir ... --shadow-dir ...` and the `bash scripts/run_6_gates.sh` automated check both still run as specified.** The comparator's non-zero exit for the reasons above is reported honestly here and in the Living Ledger rather than hidden; `run_6_gates.sh` (which does NOT include the comparator) passes cleanly with the full 1509-test suite.

## User Setup Required

None new. The Task 2 checkpoint (schema apply, PostgREST exposure, cache reload) was already completed by Juan before this session; the `SMARTSHEET_API_TOKEN`/`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` precondition for Task 3 was already present in the local `.env`.

## Next Phase Readiness

- `pipeline_memory` is live, locked down, and proven fail-open and (mostly-)neutral on real production data. Two real bugs that only real data could surface are fixed and regression-tested.
- The flag-flip PR (turning `RUN_MEMORY_WRITE_ENABLED` on in `.github/workflows/weekly-excel-generation.yml`) should, before merge: (1) resolve `group_state`'s open COALESCE assumption (mock-based test, or accept it will be proven on the flip PR's own first real run); (2) either re-run the control-vs-shadow comparison during a lower-activity window / with a fetch-snapshot capability for a byte-for-byte zero-drift PASS, or explicitly accept the canonicalized-content-only proof standard established here; (3) confirm this plan's two bug-fix commits (`514589a`, `cf3568b`) are on the branch it's cut from; (4) a short post-flip monitoring window watching `run_ledger.status`/`sheets_errored`/memory-phase timing headroom on the first few real production runs.
- `RUN_MEMORY_WRITE_ENABLED` remains OFF in `.github/workflows/weekly-excel-generation.yml`; `git diff --exit-code -- .github/workflows/ generate_weekly_pdfs.py requirements.txt tests/golden/run_summary_baseline.json billing_audit/` is clean (the `generated_docs/hash_history.json` line of that same check reports a PRE-EXISTING dirty state from before this session -- confirmed unchanged by SHA-256 across all four real runs, out of this plan's scope to fix); `bash scripts/run_6_gates.sh` passes all 6 gates; `python -m pytest tests/ -q` -> 1509 passed, 1 skipped, 132 subtests (up from 1507 at dispatch).
- Two harmless diagnostic `run_ledger` rows (`diag-test-mode-omit` -- never inserted; `diag-test-mode-fix` -- did insert) remain in production from this session's live root-cause reproduction; `service_role` has no `DELETE` grant by design, so they cannot be cleaned up from this repo. Noted for Juan's awareness; not blocking.
- No blockers for the next phase.

## Self-Check: PASSED

All modified files found on disk (`scripts/compare_control_run.py`, `tests/test_compare_control_run.py`, `pipeline_memory/writer.py`, `tests/test_pipeline_memory_shadow.py`, `pipeline_memory/schema.sql`, `memory-bank/living-ledger.md`, this SUMMARY.md). All three Task 3 commits (`514589a`, `cf3568b`, `26cb11d`) found in `git log`. `python -m pytest tests/ -q` -> 1509 passed, 1 skipped, 132 subtests. `bash scripts/run_6_gates.sh` -> ALL 6 GATES PASSED, mypy delta 65 -> 65 (neutral).

---
*Phase: 10-run-memory-foundation-shadow-writes*
*Completed: 2026-08-25*
