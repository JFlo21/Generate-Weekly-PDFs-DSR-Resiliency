---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 04
subsystem: billing-attribution
tags: [supabase, smartsheet, cell-history, billing_audit, pipeline_memory, attribution, backfill, cli, pytest, tdd, github-actions]

# Dependency graph
requires:
  - phase: 12-01
    provides: "scripts/backfill_claim_time_attribution.py -- the sources 1-4 report shape, the --apply write path (backup precondition, chunked RPC caller, never-overwrite-a-real-name guarantee), and the fixture-driven fake-Supabase-client test harness"
provides:
  - "scripts/backfill_cell_history_attribution.py -- the OWN-03 source 5 cell-history attribution resolver CLI, dry-run by default"
  - "The paced/capped Smartsheet Cells.get_cell_history resolver (request/row/wall-clock caps, self-pacing, checkbox-first efficiency short-circuit)"
  - "--check-backlog: bounded, zero-Smartsheet-call backlog count (report-file count, or a LIMIT-capped Supabase scan fallback)"
  - "A permanent structural test proving no production module (generate_weekly_pdfs.py, pipeline/*.py, audit_billing_changes.py) calls get_cell_history or reads a CELL_HISTORY_BACKFILL_* env var"
  - "scripts/backfill_claim_time_attribution.py::_write_reports gained an optional filename_stem parameter (default unchanged) so a sibling script can reuse it under its own report name"
affects: [12-05, 12-06]

# Actuals (#2632) -- pairs with the plan's estimate to calibrate future estimates.
# estimateTokens scale (chars/4 over the realized diff) for Tasks 1-2 only;
# Tasks 3-4 have not run yet (checkpoint pause).
actuals:
  tokens: 15300
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Checkbox-first efficiency short-circuit: the completion checkbox's cell history is always fetched before the name column's; when the checkbox never becomes truthy, the candidate resolves to unresolved WITHOUT a second Smartsheet request -- halves the request cost for rows that were never actually completed for the role in question."
    - "Sheet id / column id resolution via a Supabase-only prefetch (pipeline_memory.row_state for row_id -> sheet_id, pipeline_memory.sheet_registry for sheet_id -> column_mapping), entirely OUTSIDE the Smartsheet request/row/wall-clock caps -- a client-unavailable or read-failure degrades the affected candidates to unresolved rather than aborting the run."
    - "Report-writer filename parameterization: scripts/backfill_claim_time_attribution.py::_write_reports gained a filename_stem parameter (default preserves every pre-existing call site byte-for-byte) so a sibling OWN-03 script reuses the exact same sort/serialize/summary logic under its own report name instead of duplicating it."

key-files:
  created:
    - scripts/backfill_cell_history_attribution.py
    - tests/test_backfill_cell_history_attribution.py
  modified:
    - scripts/backfill_claim_time_attribution.py

key-decisions:
  - "Primary role's name column resolution tries 'Foreman Assigned?' then falls back to 'Foreman' via column_mapping.get(...) in order -- matching spec §2's literal fallback chain -- even though pipeline/discovery.py's canonical column_mapping synonym set does not currently include 'Foreman Assigned?' (verified via grep: absent from discovery.py entirely). Today this resolves via 'Foreman' only; if a future pipeline/discovery.py change adds 'Foreman Assigned?' to the canonical mapping, this script picks it up automatically with zero further changes -- documented as a known current-state gap, not a bug in this plan's scope."
  - "Sheet id / column id resolution reuses pipeline_memory.row_state + sheet_registry rather than inventing new Supabase schema or performing a live full-sheet Smartsheet discovery read. IMPORTANT CAVEAT recorded here because it materially affects source 5's real-world effectiveness today: per STATE.md, RUN_MEMORY_WRITE_ENABLED is currently OFF in production, so pipeline_memory.row_state/sheet_registry are effectively EMPTY on the live Supabase project outside isolated shadow/experiment runs. Until that flag flips on (a documented upcoming milestone precondition, unrelated to this plan), every real candidate this script considers will resolve to unresolved with reason 'sheet id or column mapping unavailable for this row' -- a truthful, non-silent degradation, never a crash or a wrong answer. Once RUN_MEMORY_WRITE_ENABLED is on and at least one full production run has populated the registry, source 5 will begin resolving real candidates with zero code changes to this script."
  - "The --check-backlog Supabase-fallback scan (used only when the sources-1-4 report file is absent) counts a row via the NAMED-sentinel check (scripts.backfill_claim_time_attribution._is_named_sentinel, reused not duplicated) rather than the raw is_sentinel_claimer, so a blank/never-populated helper or vac_crew column is not over-counted as backlog -- matches sources 1-4's own default targeting rule (12-01's post-merge review fix)."
  - "Task 2's isolation test is a test-only commit (no implementation half) -- Task 1's script already satisfies the invariant by construction (it imports nothing from pipeline.*, per its own module docstring), so there is no production code to change to make the guard pass. Verified locally (not committed) that the guard fails when get_cell_history is temporarily added to pipeline/orchestrate.py, then reverted."

requirements-completed: []  # OWN-03 NOT yet marked complete -- Tasks 3-4 remain; see Checkpoint below.

coverage:
  - id: D1
    description: "scripts/backfill_cell_history_attribution.py resolves a claimer from Smartsheet cell history under hard request/row/wall-clock caps, self-paced, never proposing a sentinel"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_happy_path_resolves_real_name_with_operator_provenance"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_resolved_name_that_is_a_sentinel_stays_unresolved"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_checkbox_never_checked_stays_unresolved"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every cell-history request is self-paced and the run stops fetching at the request/row/minute cap, reporting remaining candidates unresolved with a reason naming the cap"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_request_cap_stops_third_candidate"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_sleep_pacing_zero_before_first_one_before_subsequent"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_row_cap_env_var_stops_remaining_candidates"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_wall_clock_deadline_stops_before_any_fetch"
        status: pass
    human_judgment: false
  - id: D3
    description: "A per-candidate exception is caught, logged, and leaves that candidate unresolved without aborting the run; --check-backlog performs a bounded, zero-Smartsheet-call read"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CandidateResolutionTests::test_exception_on_one_candidate_leaves_next_candidate_resolving"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CheckBacklogTests::test_report_present_counts_unresolved_and_conflict_only"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CheckBacklogTests::test_report_absent_falls_back_to_bounded_supabase_scan"
        status: pass
    human_judgment: false
  - id: D4
    description: "No production module (generate_weekly_pdfs.py, pipeline/*.py, audit_billing_changes.py) calls get_cell_history or reads a CELL_HISTORY_BACKFILL_* env var"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryProductionIsolationTests::test_get_cell_history_call_sites_are_exactly_the_allowlist"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryProductionIsolationTests::test_no_scanned_file_reads_cell_history_backfill_env_var"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryProductionIsolationTests::test_audit_billing_changes_stub_has_zero_get_cell_history_calls"
        status: pass
    human_judgment: false
  - id: D5
    description: "Task 3 (the GitHub Actions workflow authorization decision) and Task 4 (authoring the workflow) -- NOT YET DONE, paused at a mandatory human decision checkpoint"
    requirement: "OWN-03"
    verification: []
    human_judgment: true
    rationale: "gate=blocking-human on Task 3 requires Juan's explicit written decision before any workflow file is authored; this plan cannot proceed past this point without that answer."

duration: ~35min (Tasks 1-2 only; paused before Task 3)
completed: 2026-09-03
status: halted
---

# Phase 12 Plan 04: OWN-03 Cell-History Attribution Backfill (Source 5) Summary

**Paced, capped Smartsheet cell-history resolver for the rows sources 1-4 could not name, fully isolated from the production billing run -- Tasks 1-2 shipped and verified; PAUSED at Task 3's mandatory human decision gate before any GitHub Actions workflow is authored.**

## Performance

- **Duration:** ~35 min for Tasks 1-2 (Task 3 is a blocking-human checkpoint; Task 4 not started)
- **Started:** 2026-09-03 (session start)
- **Tasks:** 2 of 4 completed (Task 3 paused for human decision; Task 4 not started)
- **Files modified:** 3 (`scripts/backfill_cell_history_attribution.py`, `tests/test_backfill_cell_history_attribution.py`, `scripts/backfill_claim_time_attribution.py`)

## Accomplishments

- Built `scripts/backfill_cell_history_attribution.py` end to end: CLI (`--check-backlog`, `--wr`, `--weeks`, `--roles`, `--report`, `--report-dir`, `--max-requests`, `--dry-run`, `--apply`, `--i-approved-this`) → sources-1-4 candidate selection (only `unresolved`/`conflict` rows, deterministic ordering) → Supabase-only sheet/column resolution (`pipeline_memory.row_state` + `sheet_registry`, batched reads, zero Smartsheet calls) → the paced, capped `client.Cells.get_cell_history` resolver → `generated_docs/own03_cell_history_report.{json,csv}` via the reused report writer → the fully-gated `--apply` path reusing 12-01's backup probe / RPC caller / exit codes verbatim.
- The resolver reads the completion checkbox's cell history first; when it never becomes checked, the candidate resolves to unresolved WITHOUT a second Smartsheet call (efficiency short-circuit, halves cost for never-completed rows). Every proposed value is tagged `source="operator"`, `name_fidelity="exact"`, and discarded via `is_sentinel_claimer` if it resolves to a sentinel.
- Pacing/caps: `CELL_HISTORY_BACKFILL_MAX_REQUESTS` (3000), `CELL_HISTORY_BACKFILL_MAX_ROWS` (1200), `CELL_HISTORY_BACKFILL_PACE_SEC` (0.25), `CELL_HISTORY_BACKFILL_MAX_MINUTES` (45) all enforced with the first fetch of a run never sleeping and every subsequent fetch sleeping `PACE_SEC`; remaining candidates past any cap are reported unresolved with a reason naming the cap. A `TIME_BUDGET_MINUTES`/`GITHUB_ACTIONS` pre-flight guard degrades the whole run to all-unresolved rather than stalling a tight session.
- `--check-backlog` performs a bounded read (report-file count, or a `.limit()`-capped `attribution_snapshot` scan fallback when the report is absent) and issues zero Smartsheet calls.
- Task 2 added a permanent structural test proving `get_cell_history` appears in exactly one production file (`pipeline/snapshot_drift.py`, the pre-existing legitimate caller) and no production module reads `CELL_HISTORY_BACKFILL_*` -- verified live by temporarily adding a call to `pipeline/orchestrate.py` and confirming the guard fires, then reverting.
- 19 tests in `tests/test_backfill_cell_history_attribution.py`; full repo suite 2017 passed / 1 skipped / 365 subtests (up from 2014 passed / 365 subtests before this plan's Tasks 1-2).

## Task Commits

1. **Task 1 RED: add failing test for cell-history resolver** — `e3d3208` (test)
2. **Task 1 GREEN: implement paced/capped cell-history resolver** — `2a4b45e` (feat)
3. **Task 2: guard production isolation of source 5** — `4bfa0d9` (test)

**Plan metadata:** this SUMMARY.md's own commit follows (worktree mode -- STATE.md/ROADMAP.md/REQUIREMENTS.md are NOT touched by this executor; the orchestrator owns those centrally after the wave, and this plan is not complete regardless).

## Files Created/Modified

- `scripts/backfill_cell_history_attribution.py` — OWN-03 source 5 CLI: paced/capped cell-history resolver, `--check-backlog`, the `--apply` write path (reused, not duplicated).
- `tests/test_backfill_cell_history_attribution.py` — 19 tests: pacing/caps, checkbox-first efficiency, sentinel discard, exception isolation, `--check-backlog` (both paths), structural import/single-call-site contracts, and the Task 2 production-isolation guard.
- `scripts/backfill_claim_time_attribution.py` — `_write_reports` gained an optional `filename_stem` parameter (default `"own03_backfill_report"`, byte-for-byte preserving every pre-existing call site) so this sibling script can reuse it under `own03_cell_history_report` instead of duplicating the sort/serialize/summary logic.

## Decisions Made

See `key-decisions` in frontmatter — summarized: (1) primary role's name-column resolution tries `Foreman Assigned?` then `Foreman`, matching spec §2 even though `Foreman Assigned?` is not in today's stored `column_mapping` (forward-compatible, documented gap); (2) sheet/column resolution reuses `pipeline_memory.row_state`/`sheet_registry` rather than inventing new schema or live full-sheet discovery, with an important caveat that this surface is empty in production until `RUN_MEMORY_WRITE_ENABLED` flips on; (3) the `--check-backlog` fallback scan uses the NAMED-sentinel check (reused from 12-01), not the raw `is_sentinel_claimer`, to avoid over-counting blank roles; (4) Task 2 is a test-only commit since Task 1's script already satisfies the isolation invariant by construction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended `_write_reports`'s reusability with a `filename_stem` parameter**
- **Found during:** Task 1, while wiring the report writer per the plan's explicit "using the report writer imported from scripts/backfill_claim_time_attribution.py" instruction
- **Issue:** `_write_reports` hardcoded the output filename to `own03_backfill_report.{json,csv}` -- reusing it verbatim would have overwritten sources 1-4's own input report file instead of producing the required `own03_cell_history_report.{json,csv}` artifact.
- **Fix:** Added an optional `filename_stem` parameter (default `"own03_backfill_report"`, preserving every existing call site byte-for-byte) to `scripts/backfill_claim_time_attribution.py::_write_reports`.
- **Files modified:** `scripts/backfill_claim_time_attribution.py`
- **Verification:** Full repo suite (2017 passed / 1 skipped / 365 subtests) confirms zero regression to 12-01's existing behavior/tests.
- **Committed in:** `2a4b45e` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] `_prefetch_sheet_and_columns` cache-key membership bug**
- **Found during:** Task 1, first GREEN test run (8 of 16 tests failed with "sheet id or column mapping unavailable" despite a correctly-populated fake `pipeline_memory.row_state` fixture)
- **Issue:** The row_state result-processing loop checked `if rid in cache` (a bare integer row_id) instead of `if rid in pending_set`, but `cache`'s keys are `("row_sheet", rid)` tuples -- the bare integer was never a top-level key, so every resolved `sheet_id` was silently discarded and the candidate always fell through to "sheet id or column mapping unavailable."
- **Fix:** Introduced `pending_set = set(pending)` and check membership against that instead of the tuple-keyed `cache` dict.
- **Files modified:** `scripts/backfill_cell_history_attribution.py`
- **Verification:** Isolated a debug repro confirming the exact failure, applied the fix, reran the full test file (16/16 passed at that point).
- **Committed in:** `2a4b45e` (Task 1 GREEN commit)

**3. [Rule 1 - Bug] Backlog fallback scan over-counted blank roles as sentinel**
- **Found during:** Task 1, `test_report_absent_falls_back_to_bounded_supabase_scan` failing with `backlog_rows=3` instead of the expected `2`
- **Issue:** `_check_backlog_via_bounded_supabase_scan` used the raw `billing_audit.writer.is_sentinel_claimer`, which treats `None`/blank as a sentinel -- a row whose helper/vac_crew was simply never populated (not a NAMED sentinel like "Unknown Foreman") was incorrectly counted as backlog, inflating the count and diverging from sources 1-4's own default targeting rule.
- **Fix:** Switched to `scripts.backfill_claim_time_attribution._is_named_sentinel` (reused, not duplicated), which excludes blank/`None` and only counts a non-blank string classified as a sentinel.
- **Files modified:** `scripts/backfill_cell_history_attribution.py`
- **Verification:** Test now asserts the correct `backlog_rows=2`.
- **Committed in:** `2a4b45e` (Task 1 GREEN commit)

---

**Total deviations:** 3 auto-fixed (1 blocking/reuse gap, 2 bugs)
**Impact on plan:** All three necessary for correctness or to fulfill the plan's own explicit reuse instruction. No scope creep -- no architectural changes, no new dependencies, no behavior outside this plan's `<threat_model>` and `<must_haves>`.

## Issues Encountered

None beyond the auto-fixed deviations above. `python -m pytest tests/test_backfill_cell_history_attribution.py -q`, `python -m py_compile`, `--help`, and the full suite all passed after the fixes described above.

## Known Stubs

None. Every function in `scripts/backfill_cell_history_attribution.py` has a real implementation; nothing is hardcoded to a placeholder value.

## Checkpoint: Paused at Task 3 (blocking-human decision)

**This plan did NOT complete.** Task 3 is `type="checkpoint:decision" gate="blocking-human"` -- per the executor's checkpoint protocol, a `gate="blocking-human"` checkpoint is NEVER auto-approved, in any mode (auto-mode is not even active in this project's config: `workflow._auto_chain_active: false`). Execution stopped here; no `.github/workflows/cell-history-backfill.yml` has been created. Task 4 (authoring that workflow) is entirely unstarted and depends on Task 3's answer.

**Decision needed from Juan:** Add `.github/workflows/cell-history-backfill.yml` with a recurring cron (Sunday 05:00 UTC) that consumes the same `SMARTSHEET_API_TOKEN` and shared 300 req/min budget as the production billing pipeline, OR a `workflow_dispatch`-only variant with no schedule, OR hold and ship no workflow at all this plan. See the structured checkpoint returned alongside this SUMMARY for the full decision context and options (`approve-cron` / `approve-dispatch-only` / `hold`).

**Not yet recorded:** Juan's verbatim answer. This section will be updated (by the continuation executor) once he responds, per Task 3's own acceptance criteria ("12-04-SUMMARY.md records the selected option id and Juan's verbatim response").

## User Setup Required

None yet for Tasks 1-2 (no external service configuration required; `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`/`SMARTSHEET_API_TOKEN` are read from the existing environment contract every `billing_audit`/`pipeline_memory` script already uses). Task 3's decision and Task 4's workflow (once authored) may introduce new GitHub Actions secrets/schedule considerations -- not yet applicable.

## Next Phase Readiness

- NOT ready to proceed to plans 12-05/12-06 -- this plan is incomplete. A continuation executor must present Task 3's decision to Juan (or receive it if already communicated out-of-band), record the answer in this SUMMARY, then execute Task 4 accordingly (or skip it entirely if `hold` is selected).
- Tasks 1-2 are fully shippable on their own: `scripts/backfill_cell_history_attribution.py` works standalone today (dry-run, `--check-backlog`, and eventually `--apply` once plan 12-03's RPC/backup table exist) even with no GitHub Actions workflow -- Juan (or CI) can invoke it manually. The workflow (Task 4) only adds unattended, scheduled/dispatched automation on top.
- IMPORTANT operational caveat for whoever runs this script for real: `pipeline_memory.row_state`/`sheet_registry` are currently EMPTY in production (`RUN_MEMORY_WRITE_ENABLED` is OFF per STATE.md) -- every real candidate will resolve to `unresolved` with reason "sheet id or column mapping unavailable for this row" until that flag flips on and at least one full production run has populated the registry. This is a truthful, documented degradation, not a defect in this plan.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-03 (Tasks 1-2 only; plan halted at Task 3)*

## Self-Check: PASSED

- FOUND: `scripts/backfill_cell_history_attribution.py`
- FOUND: `tests/test_backfill_cell_history_attribution.py`
- FOUND commit: `e3d3208` (Task 1 RED)
- FOUND commit: `2a4b45e` (Task 1 GREEN)
- FOUND commit: `4bfa0d9` (Task 2)
- VERIFIED: `python -m pytest tests/test_backfill_cell_history_attribution.py -q` — 19 passed
- VERIFIED: `python -m pytest tests/ -q` — 2017 passed, 1 skipped, 365 subtests
- VERIFIED: `python -m py_compile scripts/backfill_cell_history_attribution.py` — no errors
- VERIFIED: `python scripts/backfill_cell_history_attribution.py --help` — contains both `--check-backlog` and `--max-requests`
