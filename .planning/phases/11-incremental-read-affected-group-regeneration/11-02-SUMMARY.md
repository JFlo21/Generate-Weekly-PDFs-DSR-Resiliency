---
phase: 11-incremental-read-affected-group-regeneration
plan: 02
subsystem: pipeline_memory
tags: [supabase, smartsheet, incremental-read, watermark, run-ledger, mypy, tdd]

# Dependency graph
requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "Plan 01's caller-parses-then-passes numeric contract and run_ledger.sheets_changed population — both preconditions for the write path this plan reads back"
provides:
  - "pipeline_memory/reader.py — the package's first Supabase READ surface: get_sheet_watermarks(sheet_ids) and get_last_run_ledger_status(), both fail-open to \"cannot confirm\" (never a partial/successful-looking result) on any failure"
  - "pipeline.fetch.fetch_sheet_delta / _is_abbreviated_response / compute_rows_modified_since — the INC-01 delta-read primitive (if_version_after probe, then a rows_modified_since fetch only when the probe shows change), NOT yet wired into PHASE 2"
  - "pipeline.orchestrate.resolve_run_mode — all seven CONTEXT.md D-02 full-read escalation triggers plus the RUN_MEMORY_INCREMENTAL_ENABLED flag gate, wired into main() between PHASE 1 discovery and run_ledger_start"
  - "Capture-time watermark persistence: pipeline_memory.writer.upsert_sheet_registry's new capture_times/full_read_sheets kwargs, so last_read_at is a caller-owned instant and last_full_read_at only moves on a full read"
  - "run_ledger.mode + notes.fallback_reason visibility on all three run_ledger write call sites (start, success-finish, failure-finish)"
affects: ["11-04 (restructures PHASE 2 against fetch_sheet_delta + resolve_run_mode's per-sheet map)", "11-05 (shadow parity harness re-runs the same delta reads this plan proved)"]

# Actuals (#2632)
actuals:
  tokens: 20261
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "Read-side fail-open mirrors the existing write-side contract: pipeline_memory/reader.py never raises and returns {} / None on any failure — the caller must read that as \"cannot confirm\", never as \"nothing changed\" or \"previous run was clean\" (T-11-07)."
    - "Standalone, directly-testable pure helpers for logic nested inside main() (resolve_run_mode, _build_registry_write_plan, _normalize_column_mapping) — mirrors the established _run_memory_write_phase / _build_group_state_flush pattern from Phase 10, so deep main()-internal logic stays unit-testable without a full session."
    - "Source-inspection (inspect.getsource) regression tests for call sites too deep inside main() to invoke directly — extends the existing AttachmentSideChannelTests / RunLedgerSheetsChangedCallSiteTests convention to the new resolve_run_mode wiring."
    - "A properly type-annotated top-level function surfaces real mypy findings an untyped nested closure was silently hiding (dict[int, int] vs the runtime-accurate dict[int, int | None]) — annotate for real checking, don't suppress."

key-files:
  created:
    - pipeline_memory/reader.py
    - tests/test_incremental_read.py
    - tests/fixtures/incremental/abbreviated_sheet_response.json
  modified:
    - pipeline/config.py
    - pipeline/fetch.py
    - pipeline/orchestrate.py
    - pipeline_memory/writer.py
    - tests/test_pipeline_memory_shadow.py
    - .github/prompts/configuration-environment.md

key-decisions:
  - "auth_error_sheet_ids (D-02 trigger 3) is a real, directly-testable resolve_run_mode parameter with NO live producer yet — PHASE 2 still performs today's single-call full fetch this plan, so there is no per-sheet moment before the registry write where a live 401/403 could be observed. The trigger's logic ships now (unit-tested with a synthetic set); plan 04's per-sheet delta wiring is what will populate it for real."
  - "RUN_MEMORY_INCREMENTAL_ENABLED is checked FIRST in resolve_run_mode, before triggers 4-7, so the flag dominates \"regardless of every other input\" per CONTEXT.md D-11 — no other trigger's reason can shadow the flag-off reason."
  - "run_ledger_start's call site moved from immediately-after-the-'weekly run started' log (before PHASE 1) to immediately-after resolve_run_mode (after PHASE 1 discovery, before PASS 1's sheet_registry write) — required because resolve_run_mode needs source_sheets from discovery, and D-02/D-10 both want run_ledger_start to carry the SAME resolved mode the finish calls carry, not a hard-coded \"full\"."
  - "sheet_registry's capture_time is captured ONCE (immediately before PASS 1, i.e. immediately before PHASE 2 issues its reads) and reused verbatim for BOTH the pre-fetch and post-fetch registry passes — PASS 2 no longer recomputes a fresh \"now\" after the read completed, which would have been the wrong instant for D-01's \"captured before the read\" contract."
  - "Every sheet_registry write this plan is marked full_read=True (via _build_registry_write_plan) because PHASE 2 genuinely still performs a full fetch of every sheet regardless of the resolved run mode — the mode is computed and recorded for visibility only; plan 04 is what makes it drive the actual fetch."
  - "Widened pipeline.fetch._LAST_SHEET_VERSIONS / get_last_sheet_versions() from dict[int, int] to dict[int, int | None] rather than suppressing the new mypy [assignment] finding — the loose annotation was always inaccurate (the cache legitimately stores None); the untyped nested closure that also writes it had simply never been checked."

requirements-completed: [INC-01]

coverage:
  - id: D1
    description: "An unchanged registered sheet costs exactly one Sheets.get_sheet call and yields zero rows through fetch_sheet_delta; a changed sheet costs two, the second carrying the overlap-adjusted rows_modified_since (INC-01)."
    requirement: "INC-01"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::FetchSheetDeltaTests"
        status: pass
      - kind: unit
        ref: "tests/test_incremental_read.py::RowsModifiedSinceTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "A version-less abbreviated response, a Supabase read failure, or an unexpected exception always escalates to a full read — never reported as \"unchanged\" (T-11-07 fail-open direction)."
    requirement: "INC-01"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::FetchSheetDeltaTests::test_abbreviated_without_version_escalates"
        status: pass
      - kind: unit
        ref: "tests/test_incremental_read.py::FetchSheetDeltaTests::test_exception_escalates_never_unchanged"
        status: pass
      - kind: unit
        ref: "tests/test_incremental_read.py::SheetWatermarksReadTests::test_supabase_failure_returns_empty_dict"
        status: pass
    human_judgment: false
  - id: D3
    description: "resolve_run_mode implements all seven D-02 full-read escalation triggers plus the RUN_MEMORY_INCREMENTAL_ENABLED flag gate, never raises, and always names a non-empty fallback_reason on every full-mode resolution."
    requirement: "INC-01"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::ModeResolutionTests (14 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Capture-time watermark persistence: last_read_at is the caller-supplied capture instant verbatim; last_full_read_at is omitted (never overwritten) on a delta read; a trigger-3-isolated sheet is excluded from the registry write entirely."
    requirement: "INC-01"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::WatermarkPersistenceTests (11 tests)"
        status: pass
      - kind: other
        ref: "python -m pytest tests/ -q -> 1574 passed, 139 subtests, 1 skipped (unchanged)"
        status: pass
    human_judgment: false
  - id: D5
    description: "run_ledger.mode + notes.fallback_reason are visible on all three run_ledger write call sites; run_summary.json's frozen 21-key contract and the .github/workflows/ + pipeline_memory/schema.sql protected areas are untouched; bash scripts/run_6_gates.sh passes all 6 gates."
    verification:
      - kind: other
        ref: "bash scripts/run_6_gates.sh -> ALL 6 GATES PASSED (mypy delta 65 -> 65, run_summary.json 21 keys, protected paths clean)"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-08-26
status: complete
---

# Phase 11 Plan 02: Incremental Read Delta-Fetch Primitive + Mode Resolution Summary

**INC-01's per-sheet delta-read probe (`if_version_after` + `rows_modified_since`), all seven D-02 full-read escalation triggers, and capture-time `sheet_registry` watermark persistence — wired for visibility into `run_ledger.mode`, with `PHASE 2` still performing today's full fetch.**

## Performance

- **Duration:** 21 min (Task 1 RED commit `6e34ede` to the Gate-4 fix-up commit `ab75dfa`)
- **Started:** 2026-08-26T13:27:44-05:00
- **Completed:** 2026-08-26T13:48:34-05:00
- **Tasks:** 3
- **Files modified:** 9 (3 created, 6 modified)

## Accomplishments

- Shipped `pipeline_memory/reader.py` — the `pipeline_memory` package's first Supabase READ surface (`get_sheet_watermarks`, `get_last_run_ledger_status`), sharing the existing independent circuit breaker/kill-switch from `pipeline_memory.client` and importing nothing from `pipeline.*` (AST boundary check: `READER_BOUNDARY_OK`).
- Shipped `pipeline.fetch.fetch_sheet_delta` (plus `_is_abbreviated_response` and `compute_rows_modified_since`): an unchanged sheet costs exactly one `Sheets.get_sheet` call and zero rows; a changed sheet costs two, with the second carrying the `SAFETY_WINDOW_MINUTES`-overlap-adjusted `rows_modified_since`. Every failure mode (version-less abbreviated response, a raised exception) escalates to "cannot confirm unchanged", never reports "unchanged" (T-11-07).
- Shipped `pipeline.orchestrate.resolve_run_mode`: all seven CONTEXT.md D-02 triggers (no watermark, `column_mapping` drift, 401/403 isolation, empty watermark map, operator reset/force flags, previous run not clean, `EXECUTION_TYPE != production_frequent`) plus the `RUN_MEMORY_INCREMENTAL_ENABLED` flag gate checked first. Never raises; every full-mode resolution names a non-empty `fallback_reason`.
- Wired capture-time watermark persistence: `pipeline_memory.writer.upsert_sheet_registry` now accepts caller-supplied `capture_times`/`full_read_sheets`, so `last_read_at` is a real capture-time instant (never recomputed inside the writer) and `last_full_read_at` is omitted entirely on a delta read rather than overwritten. `run_ledger.mode` + `notes.fallback_reason` now reach all three `run_ledger` write call sites.
- Closed a self-introduced 2-line mypy Gate 4 regression discovered by the plan's own `bash scripts/run_6_gates.sh` verification step, before declaring the plan complete.

## Task Commits

Each task was committed atomically, TDD RED then GREEN:

1. **Task 1: End-to-end delta read for one sheet — config, watermark read, probe, skip**
   - `6e34ede` (test, RED) — 15 failing tests against unimplemented `_is_abbreviated_response` / `fetch_sheet_delta` / `compute_rows_modified_since` / `get_sheet_watermarks`
   - `e51a652` (feat, GREEN) — `pipeline/config.py` (`RUN_MEMORY_INCREMENTAL_ENABLED`, `SAFETY_WINDOW_MINUTES`), `pipeline/fetch.py`, `pipeline_memory/reader.py` (new)
2. **Task 2: resolve_run_mode — the seven D-02 full-read escalation triggers**
   - `4f078f0` (test, RED) — 17 failing tests against unimplemented `resolve_run_mode` / `get_last_run_ledger_status`
   - `5dad014` (feat, GREEN) — `pipeline_memory/reader.py` (`get_last_run_ledger_status`), `pipeline/orchestrate.py` (`resolve_run_mode`, `_normalize_column_mapping`)
3. **Task 3: Capture-time watermark persistence, run_ledger.mode visibility, and env docs**
   - `b62a8dd` (test, RED) — 11 failing tests against `upsert_sheet_registry`'s unimplemented new kwargs and the unwired `resolve_run_mode` call site
   - `918cf5d` (feat, GREEN) — `pipeline_memory/writer.py`, `pipeline/orchestrate.py` (mode wiring, `_build_registry_write_plan`), `.github/prompts/configuration-environment.md`, plus a structural-test fix in `tests/test_pipeline_memory_shadow.py` (see Deviations)
   - `ab75dfa` (fix) — closed the mypy Gate 4 regression surfaced by the plan-level `run_6_gates.sh` verification (see Deviations)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

_All three tasks were `tdd="true"`: tests written and confirmed RED (via a temporary implementation revert/restore cycle, since the exact function contracts were derived directly from the plan spec) before each GREEN implementation commit._

## Files Created/Modified

- `pipeline_memory/reader.py` (new) — `get_sheet_watermarks(sheet_ids)`, `get_last_run_ledger_status()`. Both fail-open to an empty/`None` result on any failure; imports nothing from `pipeline.*`.
- `pipeline/fetch.py` — `_is_abbreviated_response`, `compute_rows_modified_since`, `fetch_sheet_delta` (NOT wired into `get_all_source_rows`/PHASE 2 this plan); widened `_LAST_SHEET_VERSIONS`/`get_last_sheet_versions()` to `dict[int, int | None]` (mypy fix).
- `pipeline/config.py` — `RUN_MEMORY_INCREMENTAL_ENABLED` (default OFF), `SAFETY_WINDOW_MINUTES` (default 15).
- `pipeline/orchestrate.py` — `resolve_run_mode`, `_normalize_column_mapping`, `_build_registry_write_plan`; moved `run_ledger_start`'s call site to after PHASE 1 discovery so it can carry the resolved mode; both `run_ledger_finish` call sites now build a `_finish_kwargs` dict carrying `mode=` and an optional `fallback_reason=`; both `sheet_registry` upsert passes now share one capture-time and exclude trigger-3-isolated sheets.
- `pipeline_memory/writer.py` — `upsert_sheet_registry` gains optional `capture_times` / `full_read_sheets` kwargs (default `None` preserves Phase 10's exact prior behavior at its two existing call sites); widened `sheet_versions` param type to match `dict[int, int | None]`.
- `tests/test_incremental_read.py` (new) — `AbbreviatedResponseDetectionTests`, `RowsModifiedSinceTests`, `FetchSheetDeltaTests`, `SheetWatermarksReadTests`, `LastRunLedgerStatusReadTests`, `ModeResolutionTests`, `WatermarkPersistenceTests` (69 test methods incl. subTests).
- `tests/fixtures/incremental/abbreviated_sheet_response.json` (new) — a REAL Smartsheet abbreviated `get_sheet` response, extracted verbatim from `tests/fixtures/mem04/mem04_edit_mapping.json`'s live-captured T2 probe (not fabricated).
- `tests/test_pipeline_memory_shadow.py` — updated `RunLedgerSheetsChangedCallSiteTests`' source-inspection regex to match the new `_finish_kwargs` dict-then-call shape (same WR-04 invariant, different call-site structure — see Deviations).
- `.github/prompts/configuration-environment.md` — documents `RUN_MEMORY_INCREMENTAL_ENABLED` / `SAFETY_WINDOW_MINUTES` and the two different "mode" meanings (`run_summary.json`'s `TEST`/`PRODUCTION` vs `run_ledger.mode`'s `incremental`/`full`).

## Decisions Made

See `key-decisions` in frontmatter. The `run_ledger_start` call-site reorder and the `auth_error_sheet_ids`-has-no-live-producer-yet decision are both load-bearing: the reorder is required by the plan's own instruction to pass the resolved mode into `run_ledger_start`, and the "no live producer" framing is honest about what this plan can and cannot exercise live (PHASE 2 is explicitly unchanged this plan) while still shipping trigger 3's real, unit-tested logic per CONTEXT.md D-02's "the seven triggers ship in the same change as D-01" requirement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a structural regression test broken by the Task 3 call-site refactor**
- **Found during:** Task 3
- **Issue:** Restructuring both `run_ledger_finish` call sites to build a `_finish_kwargs` dict (so `mode=`/optional `fallback_reason=` could be added) broke `tests/test_pipeline_memory_shadow.py::RunLedgerSheetsChangedCallSiteTests::test_both_finish_call_sites_pass_sheets_changed`, a Plan 01 source-inspection regression guard that expected `sheets_changed=_mem_sheets_written` directly inside the `run_ledger_finish(` call parentheses.
- **Fix:** Updated the test's regex to match the new `_finish_kwargs = dict(...)` construction followed by `run_ledger_finish(_mem_run_id, **_finish_kwargs)`, preserving the same WR-04 invariant (both call sites still populate `sheets_changed`) against the new (equivalent) call shape.
- **Files modified:** `tests/test_pipeline_memory_shadow.py`
- **Verification:** `python -m pytest tests/test_pipeline_memory_shadow.py -q` → 83 passed, 3 subtests passed
- **Committed in:** `918cf5d` (Task 3 GREEN commit)

**2. [Rule 1 - Bug] Closed a 2-line mypy Gate 4 regression surfaced by the plan's own verification step**
- **Found during:** Plan-level verification (`bash scripts/run_6_gates.sh`, run once before declaring the plan complete per the plan's `<verification>` note)
- **Issue:** Gate 4 (mypy delta, must not increase) failed: 65 → 67 lines. Root cause 1: `fetch_sheet_delta` is a properly type-annotated top-level function assigning `getattr(sheet, 'version', None)` (typed `Any | None`) into `_LAST_SHEET_VERSIONS: dict[int, int]` — a real `[assignment]` error mypy had never caught before because the only prior writer, `_fetch_and_process_sheet`, is an untyped nested closure inside the untyped `get_all_source_rows()`, so mypy silently skips its body. Root cause 2: two newly-added, explicitly-annotated local variables inside the (also untyped) `main()` each triggered a separate, gate-counted `[annotation-unchecked]` note.
- **Fix:** Widened `_LAST_SHEET_VERSIONS` / `get_last_sheet_versions()` / `upsert_sheet_registry`'s `sheet_versions` param from `dict[int, int]` to `dict[int, int | None]` (the cache genuinely stores `None` at runtime — a type-accuracy fix, not a suppression). Dropped the two unnecessary local-variable type annotations inside `main()` (which itself is never mypy-checked), matching the existing unannotated sibling style.
- **Files modified:** `pipeline/fetch.py`, `pipeline_memory/writer.py`, `pipeline/orchestrate.py`
- **Verification:** `bash scripts/check_mypy_delta.sh` → `PASS: mypy delta neutral or improved (65 -> 65)`; full `bash scripts/run_6_gates.sh` → `ALL 6 GATES PASSED`; `python -m pytest tests/ -q` → 1574 passed, 139 subtests, 1 skipped (unchanged)
- **Committed in:** `ab75dfa`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs surfaced by the plan's own gates, not scope changes)
**Impact on plan:** Both fixes were required for the plan's own stated verification gates to pass; neither changed the plan's scope, behavior, or the flagged assumptions.

## Issues Encountered

None beyond the two auto-fixed items above. The flagged Edge Coverage assumption from the plan's `<objective>` (INC-01 classified `unclassified` by the edge probe — no resolved adjacency/empty/ordering/concurrency category) remains unresolved by this plan; the empty-registry and first-run cases were exercised directly by `ModeResolutionTests` (trigger 1 and trigger 4), which is the closest this plan gets to addressing it without a live-Supabase run.

## User Setup Required

None — no external service configuration required. `RUN_MEMORY_INCREMENTAL_ENABLED` and the new `resolve_run_mode` wiring are dormant by default (flag OFF); nothing in this plan changes production behavior. The operator-gated `RUN_MEMORY_WRITE_ENABLED` flip (from Plan 01's checklist) remains a separate, not-yet-scheduled PR this plan does not touch.

## Next Phase Readiness

- `pipeline.fetch.fetch_sheet_delta` and `pipeline.orchestrate.resolve_run_mode` are both fully built and unit-tested, ready for Plan 04 to wire into a restructured PHASE 2 — this plan deliberately left `all_rows` coming from today's single `get_all_source_rows()` full fetch (11-02-PLAN.md `<objective>` success criterion 6, confirmed still true).
- `resolve_run_mode`'s `auth_error_sheet_ids` parameter (D-02 trigger 3) has no live producer yet — Plan 04's per-sheet delta wiring is what will populate it from real 401/403s.
- `run_ledger.mode` is now trustworthy (real resolved value on all three write call sites) — the CONTEXT.md D-11 precondition ("`run_ledger.mode` must be trustworthy before anything alerts on it") is satisfied for Plan 05's shadow parity harness.
- `pipeline_memory` still imports nothing from `pipeline.*` (AST boundary check passes for both `writer.py` and the new `reader.py`); `run_summary.json`'s frozen 21-key contract, `.github/workflows/`, and `pipeline_memory/schema.sql` are all untouched.
- No blockers. `bash scripts/run_6_gates.sh` passes ALL 6 gates on the final commit.

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-08-26*
