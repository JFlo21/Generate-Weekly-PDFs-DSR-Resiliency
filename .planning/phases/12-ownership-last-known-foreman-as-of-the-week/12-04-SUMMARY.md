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
  - ".github/workflows/cell-history-backfill.yml -- the isolated, budget-capped, self-disabling Sunday 05:00 UTC cron + workflow_dispatch runner for source 5 (dry-run only; never --apply)"
affects: [12-05, 12-06]

# Actuals (#2632) -- pairs with the plan's estimate to calibrate future estimates.
# estimateTokens scale (chars/4 over the realized diff of every file this
# plan touched, master..HEAD, including the pre-checkpoint review hardening).
actuals:
  tokens: 24285
  tasks: 4
  commits: 5

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
    - .github/workflows/cell-history-backfill.yml
  modified:
    - scripts/backfill_claim_time_attribution.py

key-decisions:
  - "Primary role's name column resolution tries 'Foreman Assigned?' then falls back to 'Foreman' via column_mapping.get(...) in order -- matching spec §2's literal fallback chain -- even though pipeline/discovery.py's canonical column_mapping synonym set does not currently include 'Foreman Assigned?' (verified via grep: absent from discovery.py entirely). Today this resolves via 'Foreman' only; if a future pipeline/discovery.py change adds 'Foreman Assigned?' to the canonical mapping, this script picks it up automatically with zero further changes -- documented as a known current-state gap, not a bug in this plan's scope."
  - "Sheet id / column id resolution reuses pipeline_memory.row_state + sheet_registry rather than inventing new Supabase schema or performing a live full-sheet Smartsheet discovery read. IMPORTANT CAVEAT recorded here because it materially affects source 5's real-world effectiveness today: per STATE.md, RUN_MEMORY_WRITE_ENABLED is currently OFF in production, so pipeline_memory.row_state/sheet_registry are effectively EMPTY on the live Supabase project outside isolated shadow/experiment runs. Until that flag flips on (a documented upcoming milestone precondition, unrelated to this plan), every real candidate this script considers will resolve to unresolved with reason 'sheet id or column mapping unavailable for this row' -- a truthful, non-silent degradation, never a crash or a wrong answer. Once RUN_MEMORY_WRITE_ENABLED is on and at least one full production run has populated the registry, source 5 will begin resolving real candidates with zero code changes to this script."
  - "The --check-backlog Supabase-fallback scan (used only when the sources-1-4 report file is absent) counts a row via the NAMED-sentinel check (scripts.backfill_claim_time_attribution._is_named_sentinel, reused not duplicated) rather than the raw is_sentinel_claimer, so a blank/never-populated helper or vac_crew column is not over-counted as backlog -- matches sources 1-4's own default targeting rule (12-01's post-merge review fix)."
  - "Task 2's isolation test is a test-only commit (no implementation half) -- Task 1's script already satisfies the invariant by construction (it imports nothing from pipeline.*, per its own module docstring), so there is no production code to change to make the guard pass. Verified locally (not committed) that the guard fails when get_cell_history is temporarily added to pipeline/orchestrate.py, then reverted."
  - "Task 3 checkpoint: Juan selected `approve-cron` (2026-09-03) -- the workflow ships with the single Sunday 05:00 UTC cron plus workflow_dispatch, as agreed in the 2026-09-01 design spec."
  - "Workflow structural test parses the YAML with validate_system_health.py's comment-stripped line reader (_strip_comment / _find_key_value / _find_timeout_minutes) instead of PyYAML: PyYAML is not declared in requirements.txt (the only file ci-checks.yml installs) and is importable locally only via an unrelated venv on PATH, so a top-level `import yaml` would have failed collection of the whole test module in CI."
  - "The --check-backlog gate step binds SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (never SMARTSHEET_API_TOKEN): on a fresh runner generated_docs/own03_backfill_report.json is git-ignored and absent, so the gate always takes the bounded Supabase fallback scan and would exit 7 every Sunday without them. The Smartsheet token is bound only in the backfill step, and no secret is bound at job level."

requirements-completed: [OWN-03]

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
    description: ".github/workflows/cell-history-backfill.yml is isolated from the production run (own concurrency group, timeout-minutes > CELL_HISTORY_BACKFILL_MAX_MINUTES), self-disables on an empty backlog, binds every dispatch input to env:, and never passes --apply"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryWorkflowStructureTests::test_concurrency_group_is_isolated_from_production"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryWorkflowStructureTests::test_timeout_exceeds_max_minutes_budget"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryWorkflowStructureTests::test_backfill_step_is_gated_and_never_applies"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryWorkflowStructureTests::test_every_dispatch_input_is_bound_to_env"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_cell_history_attribution.py::CellHistoryWorkflowStructureTests::test_single_sunday_cron"
        status: pass
    human_judgment: true
    rationale: "Task 3 (gate=blocking-human) was decided by Juan on 2026-09-03: approve-cron. The schedule's existence is a human authorization, not a testable fact; the tests above prove the authored file honours the decision's constraints."

duration: ~35min (Tasks 1-2) + ~40min (Task 4 continuation)
completed: 2026-09-03
status: complete
---

# Phase 12 Plan 04: OWN-03 Cell-History Attribution Backfill (Source 5) Summary

**Paced, capped Smartsheet cell-history resolver for the rows sources 1-4 could not name, fully isolated from the production billing run, plus its own budget-capped, self-disabling Sunday 05:00 UTC GitHub Actions workflow (dry-run only) -- all 4 tasks shipped; Task 3's blocking-human gate was decided by Juan (`approve-cron`).**

## Performance

- **Duration:** ~35 min for Tasks 1-2, a pause at Task 3 (blocking-human decision), then ~40 min for the Task 4 continuation
- **Started:** 2026-09-03 (session start)
- **Tasks:** 4 of 4 completed (Task 3 decided by Juan: `approve-cron`)
- **Files modified:** 4 (`scripts/backfill_cell_history_attribution.py`, `tests/test_backfill_cell_history_attribution.py`, `scripts/backfill_claim_time_attribution.py`, `.github/workflows/cell-history-backfill.yml`)

## Accomplishments

- Built `scripts/backfill_cell_history_attribution.py` end to end: CLI (`--check-backlog`, `--wr`, `--weeks`, `--roles`, `--report`, `--report-dir`, `--max-requests`, `--dry-run`, `--apply`, `--i-approved-this`) → sources-1-4 candidate selection (only `unresolved`/`conflict` rows, deterministic ordering) → Supabase-only sheet/column resolution (`pipeline_memory.row_state` + `sheet_registry`, batched reads, zero Smartsheet calls) → the paced, capped `client.Cells.get_cell_history` resolver → `generated_docs/own03_cell_history_report.{json,csv}` via the reused report writer → the fully-gated `--apply` path reusing 12-01's backup probe / RPC caller / exit codes verbatim.
- The resolver reads the completion checkbox's cell history first; when it never becomes checked, the candidate resolves to unresolved WITHOUT a second Smartsheet call (efficiency short-circuit, halves cost for never-completed rows). Every proposed value is tagged `source="operator"`, `name_fidelity="exact"`, and discarded via `is_sentinel_claimer` if it resolves to a sentinel.
- Pacing/caps: `CELL_HISTORY_BACKFILL_MAX_REQUESTS` (3000), `CELL_HISTORY_BACKFILL_MAX_ROWS` (1200), `CELL_HISTORY_BACKFILL_PACE_SEC` (0.25), `CELL_HISTORY_BACKFILL_MAX_MINUTES` (45) all enforced with the first fetch of a run never sleeping and every subsequent fetch sleeping `PACE_SEC`; remaining candidates past any cap are reported unresolved with a reason naming the cap. A `TIME_BUDGET_MINUTES`/`GITHUB_ACTIONS` pre-flight guard degrades the whole run to all-unresolved rather than stalling a tight session.
- `--check-backlog` performs a bounded read (report-file count, or a `.limit()`-capped `attribution_snapshot` scan fallback when the report is absent) and issues zero Smartsheet calls.
- Task 2 added a permanent structural test proving `get_cell_history` appears in exactly one production file (`pipeline/snapshot_drift.py`, the pre-existing legitimate caller) and no production module reads `CELL_HISTORY_BACKFILL_*` -- verified live by temporarily adding a call to `pipeline/orchestrate.py` and confirming the guard fires, then reverting.
- 19 tests in `tests/test_backfill_cell_history_attribution.py`; full repo suite 2017 passed / 1 skipped / 365 subtests (up from 2014 passed / 365 subtests before this plan's Tasks 1-2).
- Task 4 authored `.github/workflows/cell-history-backfill.yml` per the `approve-cron` decision: `permissions: contents: read`; its own `cell-history-backfill-${{ github.ref }}` concurrency group (queue mode) so it can neither queue behind nor block `weekly-excel-*`; a single `'0 5 * * 0'` cron (Sunday 05:00 UTC, no overlap with the 15:00/19:00/23:00 UTC weekend billing crons) plus `workflow_dispatch` inputs `dry_run` / `wr_filter` / `max_requests`; `timeout-minutes: 60` strictly above the 45-minute script cap; job env pins the request/row/pace/minute caps; a `--check-backlog` gate step (Supabase only, zero Smartsheet calls) writes `backlog_rows=<N>` to `$GITHUB_OUTPUT` and the backfill step is skipped when it is `0`; every dispatch input is bound to `env:` and read as a shell variable (no `${{` inside any `run:`); the backfill step never passes `--apply` and is the only place `SMARTSHEET_API_TOKEN` is bound; the report is uploaded with `actions/upload-artifact@v4` and never enters git.
- 9 structural tests (`CellHistoryWorkflowStructureTests`) grade the workflow with `validate_system_health.py`'s comment-stripped line reader; each guard was proven to fire under mutation (injected `${{` in `run:`, `--apply`, `timeout-minutes: 45`, a `weekly-excel-` group). File total: 36 tests; full repo suite 2065 passed / 1 skipped / 395 subtests.

## Task Commits

1. **Task 1 RED: add failing test for cell-history resolver** — `e3d3208` (test)
2. **Task 1 GREEN: implement paced/capped cell-history resolver** — `2a4b45e` (feat)
3. **Task 2: guard production isolation of source 5** — `4bfa0d9` (test)
4. **Pre-checkpoint review hardening** — `101489d` (fix; see "Pre-checkpoint review fixes" below)
5. **Task 3: decision checkpoint** — no commit (decided by Juan: `approve-cron`, 2026-09-03)
6. **Task 4: add cell-history backfill workflow** — `43f52ce` (feat)

**Plan metadata:** this SUMMARY.md's own commit follows separately (`docs(12-04): record Task 4 and checkpoint decision`); STATE.md/ROADMAP.md/REQUIREMENTS.md are owned centrally by the orchestrator after the wave.

## Files Created/Modified

- `scripts/backfill_cell_history_attribution.py` — OWN-03 source 5 CLI: paced/capped cell-history resolver, `--check-backlog`, the `--apply` write path (reused, not duplicated).
- `tests/test_backfill_cell_history_attribution.py` — 36 tests: pacing/caps, checkbox-first efficiency, sentinel discard, exception isolation, `--check-backlog` (both paths), structural import/single-call-site contracts, and the Task 2 production-isolation guard, plus the Task 4 `CellHistoryWorkflowStructureTests` workflow contract (9 tests).
- `scripts/backfill_claim_time_attribution.py` — `_write_reports` gained an optional `filename_stem` parameter (default `"own03_backfill_report"`, byte-for-byte preserving every pre-existing call site) so this sibling script can reuse it under `own03_cell_history_report` instead of duplicating the sort/serialize/summary logic.
- `.github/workflows/cell-history-backfill.yml` — the isolated OWN-03 source 5 runner (Task 4): Sunday 05:00 UTC cron + `workflow_dispatch`, own concurrency group, backlog gate, dry-run only, artifact upload.

## Decisions Made

See `key-decisions` in frontmatter — summarized: (1) primary role's name-column resolution tries `Foreman Assigned?` then `Foreman`, matching spec §2 even though `Foreman Assigned?` is not in today's stored `column_mapping` (forward-compatible, documented gap); (2) sheet/column resolution reuses `pipeline_memory.row_state`/`sheet_registry` rather than inventing new schema or live full-sheet discovery, with an important caveat that this surface is empty in production until `RUN_MEMORY_WRITE_ENABLED` flips on; (3) the `--check-backlog` fallback scan uses the NAMED-sentinel check (reused from 12-01), not the raw `is_sentinel_claimer`, to avoid over-counting blank roles; (4) Task 2 is a test-only commit since Task 1's script already satisfies the isolation invariant by construction; (5) Task 3: Juan chose `approve-cron`; (6) the workflow structural test uses `validate_system_health.py`'s line reader, not PyYAML (an undeclared dependency); (7) the backlog gate step binds the Supabase secrets (required for its fallback scan on a fresh runner) while the Smartsheet token stays bound only in the backfill step.

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

**4. [Approved deviation] `CELL_HISTORY_BACKFILL_PACE_SEC: '0.5'` in the workflow job env (plan text said `'0.25'`)**
- **Found during:** Task 4
- **Issue:** The pre-checkpoint review hardening (`101489d`) raised the script's default pace from 0.25 s to 0.5 s (120 req/min, 40% of the shared 300 req/min budget instead of 80%). A workflow pinning `'0.25'` would have silently undercut the script's own default.
- **Fix:** The job env pins `'0.5'` with a comment saying never to set it lower than the script default. Approved by the orchestrator in the continuation brief.
- **Files modified:** `.github/workflows/cell-history-backfill.yml`
- **Commit:** `43f52ce`

**5. [Rule 3 - Blocking] Workflow structural test uses the repo's line reader, not PyYAML**
- **Found during:** Task 4, before writing the test
- **Issue:** The plan/brief assumed PyYAML was available because `tests/test_validate_system_health.py` "uses it". It does not: no file in the repo imports `yaml`, PyYAML is absent from `requirements.txt` (the only file `ci-checks.yml` installs) and from `requirements-dev.txt`, and `import yaml` works locally only because an unrelated venv (`hermes-agent`) is first on PATH. A top-level `import yaml` would have errored the whole 36-test module at collection in CI.
- **Fix:** The test reuses `validate_system_health._strip_comment` / `_find_key_value` / `_find_timeout_minutes` (exactly "the config-parsing approach already used by ... production workflow checks" the plan asks for) plus three small local helpers (`_step_blocks`, `_run_block`, `_dispatch_input_names`). Adding PyYAML to `requirements.txt` was rejected: it would install a new package into the production cron runner to satisfy a test. Corollary: the plan's `sorted(d)` verify one-liner raises `TypeError` under PyYAML 6 because the bare `on:` key parses as boolean `True` (same as the production workflow); it was run as `sorted(map(str, d))` and the key list includes `jobs`.
- **Files modified:** `tests/test_backfill_cell_history_attribution.py`
- **Commit:** `43f52ce`

**6. [Rule 2 - Missing critical functionality] Supabase secrets bound in the `--check-backlog` gate step**
- **Found during:** Task 4, tracing `_check_backlog` on a fresh runner
- **Issue:** The plan binds all three secrets only in the backfill step. But `generated_docs/own03_backfill_report.json` is git-ignored and never present on a fresh runner, so `_check_backlog` always takes `_check_backlog_via_bounded_supabase_scan`, which returns -1 without a Supabase client -> exit 7 -> the job fails every Sunday and the gate never runs.
- **Fix:** The gate step binds `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` only (still zero Smartsheet calls); `SMARTSHEET_API_TOKEN` is bound solely in the backfill step, and no secret is bound at job level -- `test_gate_step_writes_backlog_rows_output` and `test_smartsheet_token_bound_only_in_backfill_step` pin both facts (T-12-19 intent preserved).
- **Files modified:** `.github/workflows/cell-history-backfill.yml`
- **Commit:** `43f52ce`

---

**Total deviations:** 6 (3 auto-fixed in Tasks 1-2; 1 approved, 1 blocking, 1 missing-functionality in Task 4)
**Impact on plan:** All necessary for correctness or to fulfill the plan's own instructions. No architectural changes, no new dependencies, no behavior outside this plan's `<threat_model>` and `<must_haves>`.

## Issues Encountered

None beyond the auto-fixed deviations above. `python -m pytest tests/test_backfill_cell_history_attribution.py -q`, `python -m py_compile`, `--help`, and the full suite all passed after the fixes described above.

## Known Stubs

None. Every function in `scripts/backfill_cell_history_attribution.py` has a real implementation; nothing is hardcoded to a placeholder value.

## Checkpoint: Task 3 decision (blocking-human) -- RECORDED

Task 3 is `type="checkpoint:decision" gate="blocking-human"`; it was never auto-approved. Execution paused after Tasks 1-2 (plus the pre-checkpoint review hardening) and resumed only after Juan answered.

- **Selected option id:** `approve-cron`
- **Decided by / on:** Juan, 2026-09-03
- **Verbatim selection from the structured checkpoint prompt:** `approve-cron (Recommended)` ("Sunday 05:00 UTC schedule plus workflow_dispatch, as agreed in the 2026-09-01 design spec")
- **Consequence:** Task 4 authored `.github/workflows/cell-history-backfill.yml` with the single `'0 5 * * 0'` cron plus `workflow_dispatch` (commit `43f52ce`). The `approve-dispatch-only` and `hold` variants were not built.

## Known limitations (operator-visible, not defects of this plan)

- **The cron cannot self-produce its candidate list.** The cell-history script reads candidates only from the sources 1-4 report (`generated_docs/own03_backfill_report.json`), which is git-ignored and absent on a fresh runner, and `scripts/backfill_claim_time_attribution.py` refuses to enumerate candidates without explicit `--wr` and `--weeks` scoping (exit 8, a 12-01 design constraint). So a Sunday run today gates on the Supabase fallback count, then the backfill step finds zero in-scope candidates, writes an empty report, emits a `::warning::` annotation naming this precondition, and exits 0 -- safe and cheap (Supabase reads only, zero Smartsheet calls), but not yet useful. Producing that report on the runner (a scoped sources-1-4 step, or plan 12-05/12-06 supplying it) is a scope decision for Juan, not something this plan may add unilaterally (Rule 4).
- **`RUN_MEMORY_WRITE_ENABLED` is still off in production**, so even with a report present every candidate resolves to `unresolved` ("sheet id or column mapping unavailable") until `pipeline_memory.row_state` / `sheet_registry` are populated (unchanged from the Tasks 1-2 caveat).
- **`dry_run=false` does not apply anything.** The workflow never passes `--apply`; the input only produces a `::warning::` and still runs dry. The live write stays plan 12-06's human checkpoint.

## User Setup Required

- Repository secrets `SMARTSHEET_API_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` must exist (they already do for `weekly-excel-generation.yml`; no new secret is introduced).
- The Sunday 05:00 UTC cron starts on merge to the default branch. Deleting or disabling the workflow stops it; nothing else needs configuring.

## Next Phase Readiness

- Ready for plans 12-05/12-06: OWN-03's source 5 resolver and its isolated workflow both exist, are dry-run only, and are pinned by 36 tests.
- Open decision for Juan (see Known limitations): how the Sunday run obtains the sources 1-4 candidate report on a fresh runner. Until then the cron is a safe no-op that reports its own precondition.
- Operational caveat carried forward: `RUN_MEMORY_WRITE_ENABLED` must be on (and one full production run completed) before source 5 can resolve real candidates.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-03 (all 4 tasks; Task 3 decided by Juan: approve-cron)*

## Self-Check: PASSED

- FOUND: `scripts/backfill_cell_history_attribution.py`
- FOUND: `tests/test_backfill_cell_history_attribution.py`
- FOUND: `.github/workflows/cell-history-backfill.yml`
- FOUND commit: `e3d3208` (Task 1 RED)
- FOUND commit: `2a4b45e` (Task 1 GREEN)
- FOUND commit: `4bfa0d9` (Task 2)
- FOUND commit: `101489d` (pre-checkpoint review hardening)
- FOUND commit: `43f52ce` (Task 4)
- VERIFIED: `python -m pytest tests/test_backfill_cell_history_attribution.py -q` — 36 passed, 9 subtests passed
- VERIFIED: `python -m pytest tests/test_backfill_cell_history_attribution.py -q -k CellHistoryWorkflowStructureTests` — 9 passed
- VERIFIED: `python -m pytest tests/ -q` — 2065 passed, 1 skipped, 395 subtests passed
- VERIFIED: PyYAML `safe_load` of the workflow (local env only) — keys `concurrency, jobs, name, permissions, on`; inputs `dry_run, max_requests, wr_filter`; cron `0 5 * * 0`; `timeout-minutes` 60; steps `Checkout, Setup Python, Install dependencies, backlog, run_backfill, Upload cell-history report`
- VERIFIED: `git diff --name-only master..HEAD | grep weekly-excel-generation` — empty (production workflow untouched)
- VERIFIED: mutation checks — injected `${{` in `run:`, `--apply`, `timeout-minutes: 45`, and a `weekly-excel-` group are each caught by the structural helpers

## Pre-checkpoint review fixes

An independent Opus production-risk review of Tasks 1-2 (before merge and before the
Task 3 decision) returned FIX-FIRST (4 HIGH / 4 MEDIUM); one fix round, commit
`101489d`, orchestrator-decided rules:

- **HIGH — laundered read failures:** any cell-history / mapping read failure now
  marks the candidate `status="error"` (evidence carries the exception TYPE only),
  stops further Smartsheet calls, still writes the report with
  `summary.read_failures` / `summary.aborted`, and exits 7 — never `unresolved`.
- **HIGH — name column read `value`:** `_entry_name_value` prefers `display_value`
  (a CONTACT_LIST `value` is an email) for the name column only.
- **HIGH — no week guard:** rule decided: a checkbox falsy→truthy transition counts
  only when its timestamp is on/after `week_ending - 6 days` (earlier ticks belong to
  a prior week's claim on a re-dated row); no upper bound (late ticks are still this
  row's week). One distinct in-window name → proposed (`claims=<n>`); differing names
  → `conflict` (timestamps only in evidence); none → unresolved.
- **HIGH — pacing 80% of the shared budget:** default pace 0.25s → 0.5s (120 req/min);
  request/deadline caps now checked inside the fetch before every request; a trip
  defers the remaining candidates (`cap_reached`, `candidates_deferred`), exit 0.
- **MEDIUM:** dead `TIME_BUDGET_MINUTES` pre-flight removed; provenance tag
  `operator` → `backfill_cell_history` (12-03's RPC vocabulary extended in `f3b6db3`);
  `--check-backlog` exits 7 on a broken backend instead of reporting 0.
- **LOW:** non-canonical `Foreman Assigned?` synonym dropped.
- Tests: +11 (ordering, recheck cycles, conflict, name-after-check, week window,
  display_value, failure exit, cap deferral, backlog failure). Full suite: 2025 passed.

## Post-checkpoint review fixes (Opus production-risk review, 2026-09-03)

The mandatory read-only Opus review of Task 4 (`43f52ce`) returned **FIX-FIRST**. Applied in the same
fix round by the orchestrator:

- **M2** `dry_run=false` no longer warns-and-continues: the backfill step exits 1 with a `::error::`
  before any call, so an operator can never mistake a green run for a live write.
- **M3** Test gaps closed by mutation: `--apply` is asserted absent from EVERY `run:` block (a mutation
  adding it to the gate step passed before); exactly one `contents:` key and zero `*: write` scopes
  (a job-level `contents: write` slipped past `_find_key_value`'s first-match); the four cap env values
  (3000 / 1200 / 0.5 / 45) are pinned so a quiet `PACE_SEC` regression fails CI.
- **L6** The artifact upload keys on `hashFiles()` of the report instead of `steps.run_backfill.outcome`,
  which is `''` (not `'skipped'`) for a step never reached after a gate failure.
- **L5** accepted as-is: the gate step needs `SUPABASE_*` for its bounded fallback scan; step-scoped,
  never echoed, mirrors the production workflow.
- **M4** carried to 12-06: a manual dispatch during a billing run would share the 300 req/min token;
  nil exposure today (zero Smartsheet calls without a candidate report), real once 12-06 supplies one.

**Open (Opus H1, owner decision, NOT applied):** the backlog gate counts sentinel rows via the bounded
Supabase fallback while the backfill step consumes candidates only from
`generated_docs/own03_backfill_report.json`, which never exists on a fresh runner — so the approved
Sunday cron is a permanently green no-op (zero Smartsheet calls) until a candidate source exists, and the
"self-disables when empty" property does not hold. Opus recommends dropping the `schedule:` block until
12-06 lands a real candidate source (option b) and rejects a checked-in WR scope (option c). Juan chose
`approve-cron` before this gap was known; the schedule stays in the file pending his re-decision.
