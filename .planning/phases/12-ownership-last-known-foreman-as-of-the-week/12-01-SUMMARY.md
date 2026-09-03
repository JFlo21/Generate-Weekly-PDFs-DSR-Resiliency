---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 01
subsystem: billing-attribution
tags: [supabase, postgrest, billing_audit, pipeline_memory, attribution, backfill, cli, pytest, tdd]

# Dependency graph
requires: []
provides:
  - "scripts/backfill_claim_time_attribution.py — the OWN-03 claim-time attribution backfill CLI, dry-run by default"
  - "A total, deterministic 1->2->3->4 source-precedence resolver ladder with explicit proposed/conflict/unresolved outcomes"
  - "The --apply write path (backup precondition, chunked RPC caller, never-overwrite-a-real-name guarantee) — gated behind --i-approved-this, never invoked by this plan"
  - "A fixture-driven, filter-aware fake-Supabase-client test harness reusable by plans 12-02..12-06 for similar Supabase-backed script testing"
affects: [12-02, 12-03, 12-04, 12-05, 12-06]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 26800
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bounded with_retry-then-single-reprobe pattern to distinguish a definitively-missing PostgREST relation/RPC (permanent PGRST1xx/2xx/3xx code) from a transient connectivity failure, reused from billing_audit.writer.prefetch_attribution's PGRST202 handling and applied here to PGRST205 (missing backup table)"
    - "Filter-aware fake Supabase client test infra (_FakeQuery/_FakeTable/_FakeSchema/_FakeClient) that actually honors .eq()/.in_()/.order() against fixture rows, so negative/scoping tests (no cross-week reads) are meaningful instead of rubber-stamped by an unconditional mock"
    - "Source-precedence resolver registry: a dict of resolver callables keyed by source id, walked in a fixed order, first non-None (Candidate or Conflict) wins — new sources register without touching the loop"

key-files:
  created:
    - scripts/backfill_claim_time_attribution.py
    - tests/test_backfill_claim_time_attribution.py
  modified:
    - .gitignore

key-decisions:
  - "Sentinel discovery uses billing_audit.writer.prefetch_attribution (bulk, keyed by (wr, week_ending) pairs, no pre-known row_id needed) instead of the plan's literally-named _lookup_attribution_all (which requires a row_id up front) — RESEARCH.md Pattern 1 sanctions either function, and prefetch_attribution is the only one that can enumerate rows without a raw attribution_snapshot scan."
  - "--wr and --weeks are both effectively required (new exit code 8) rather than defaulting to 'every WR with a sentinel role' as the plan's CLI-surface text describes — no source available to this script can enumerate that scope without a prohibited raw table scan. Documented as an intentional, safe limitation, not a silent no-op."
  - "Source 3's filename-token mapping covers the full 7 pipeline variants (including reduced_sub_helper/aep_billable_helper) rather than the plan's bare _User_/_Helper_/_VacCrew_ enumeration — omitting the subcontractor helper tokens would silently under-cover those sheets, the exact class of coverage gap OWN-03 exists to close."
  - "public.artifacts rows already carry their own `variant` column, so source 3 looks up the ONE filename token for a row's own variant rather than sniffing the filename to classify it — sidesteps the _User_/_ReducedSub_User_ substring-ambiguity problem entirely."
  - "Backup-table probe results in status vocabulary {'ok','missing','connectivity_error'} rather than a plain boolean, mirroring prefetch_attribution's own status vocabulary discipline so callers cannot conflate 'table absent' with 'transient outage'."
  - "_write_reports gained optional csv_columns/extra_summary parameters (both default to the Task 1/2 shape) instead of a second report-writer function, so the apply-mode rewrite (rpc_result column + apply tallies) reuses the exact same sort/serialize logic and cannot drift from the dry-run report's byte-for-byte determinism guarantee."
  - "The RPC per-row result vocabulary is treated defensively: any result string outside {updated, skipped_real_name, skipped_no_row} is counted as 'error' and logged, so a future RPC contract change that adds or renames an outcome fails loudly (exit 6) instead of being silently miscounted as success."

patterns-established:
  - "Two independent never-overwrite-a-real-name guards (T-12-01): the Python-side is_sentinel_claimer filter on current_value in _build_apply_payload, and the server-side sentinel-only WHERE clause the plan 12-03 RPC must implement — proven independently by a unit test that constructs a malformed report_rows entry directly, bypassing discovery."
  - "A run-date function (_run_date()) is a standalone, mockable indirection rather than an inline datetime.now() call whenever a date value determines a resource name (here: the dated backup table) — keeps date-dependent code testable without freezing wall-clock time."

requirements-completed: [OWN-01, OWN-03]

coverage:
  - id: D1
    description: "End-to-end dry-run for the WR 19073866 known-good sample resolves the primary claimer via source 4 (backfill_hash_history) across all four week_ending_fmt tokens, with zero Supabase write calls"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::KnownGoodSampleDryRunTests::test_resolves_all_four_weeks_via_source_4"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::KnownGoodSampleDryRunTests::test_report_is_deterministic_across_two_runs"
        status: pass
    human_judgment: false
  - id: D2
    description: "Sources 1 (row_event/row_state), 2 (same-row other role) and 3 (public.artifacts filenames) resolve under the total 1->2->3->4 precedence, with source 1 winning over 3/4 when multiple sources have candidates, and no source ever reads outside its row's own week"
    requirement: "OWN-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::SourcesOneTwoThreeTests::test_source_1_wins_over_3_and_4_when_all_present"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::SourcesOneTwoThreeTests::test_no_source_ever_reads_an_adjacent_week"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::StructuralContractTests::test_no_last_known_before_week_literal_in_non_comment_lines"
        status: pass
    human_judgment: false
  - id: D3
    description: "Two distinct real names for the same (wr, week_ending, role) in source 3 or source 4 produce status='conflict' with an empty proposed_value and no source can name a row produces status='unresolved' with a non-empty reason, process still exits 0"
    requirement: "OWN-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::SourcesOneTwoThreeTests::test_source_3_two_names_conflict"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::KnownGoodSampleDryRunTests::test_two_names_in_source_4_is_a_conflict"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::SourcesOneTwoThreeTests::test_zero_candidates_across_all_sources_is_unresolved"
        status: pass
    human_judgment: false
  - id: D4
    description: "The --apply write path: refused without --i-approved-this (exit 4, zero RPC calls); refuses to write when the dated backup table is missing (exit 3) vs a connectivity error on the same probe (exit 7); never includes a p_rows entry for a row whose current frozen value is a real name; the payload key set is exactly the 7-key contract; a raised RPC exception or unrecognized per-row result returns exit 6"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::ApplyPathTests::test_apply_without_approval_returns_4_and_no_rpc_calls"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::ApplyPathTests::test_apply_missing_backup_table_returns_3"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::ApplyPathTests::test_apply_backup_probe_connectivity_error_returns_7"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::ApplyPathTests::test_build_apply_payload_excludes_real_current_value"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::ApplyPathTests::test_apply_payload_key_set_is_exact_seven_keys"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py::ApplyPathTests::test_apply_raised_rpc_exception_returns_6"
        status: pass
    human_judgment: false
  - id: D5
    description: "generated_docs/own03_backfill_report.{json,csv} are git-ignored (claimer PII never committed) and no task in this plan performs a live Supabase write"
    verification:
      - kind: other
        ref: "git check-ignore generated_docs/own03_backfill_report.csv && git check-ignore generated_docs/own03_backfill_report.json"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py (every fake table's insert/update/upsert/delete raises AssertionError if called — _RaisingWrite)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-09-03
status: complete
---

# Phase 12 Plan 01: OWN-03 Claim-Time Attribution Backfill Summary

**A fixture-driven, dry-run-first CLI that resolves the historically-correct claimer for sentinel-frozen billing rows through a deterministic four-source ladder (row_event/row_state, same-row cross-role, artifact filenames, hash-history), with a fully-gated --apply write path never invoked by this plan.**

## Performance

- **Duration:** ~35 min (git commit span 00:53:54–01:22:13 CDT plus research/design time)
- **Tasks:** 3 completed (1 tracer + 2 TDD auto)
- **Files modified:** 3 (`scripts/backfill_claim_time_attribution.py`, `tests/test_backfill_claim_time_attribution.py`, `.gitignore`)

## Accomplishments

- Built `scripts/backfill_claim_time_attribution.py` end to end: argparse CLI → Supabase client → sentinel-row discovery (via `billing_audit.writer.prefetch_attribution`, never a raw `attribution_snapshot` scan) → a total 1→2→3→4 source-precedence resolver ladder → JSON/CSV dry-run report writer → the fully-gated `--apply` write path.
- All four sources resolve under a deterministic precedence with explicit `proposed` / `conflict` / `unresolved` outcomes, and none of the four ever reads outside a row's own `week_ending` — the dropped cross-week (`last_known_before_week`) rung is verified absent by a structural test.
- The `--apply` path never overwrites a real name (two independent guards: Python-side `is_sentinel_claimer` filter + the server-side RPC contract it will call), is refused without `--i-approved-this`, and refuses to write when the dated backup table is unreadable — distinguishing a definitively-missing table from a connectivity blip via a bounded PostgREST-error reprobe.
- 40 tests in `tests/test_backfill_claim_time_attribution.py`; full repo suite 1986 passed / 1 skipped; `bash scripts/run_6_gates.sh` prints `ALL 6 GATES PASSED`.

## Task Commits

Each task was committed atomically (Tasks 2 and 3 followed the RED → GREEN TDD cycle):

1. **Task 1: End-to-end dry-run for one WR — CLI to report, source 4 only** — `d49be6b` (feat, tracer)
2. **Task 2: Fill in sources 1, 2 and 3 and the conflict/unresolved/ordering rules** — `2b9f3b3` (test, RED) → `7912fd2` (feat, GREEN)
3. **Task 3: The --apply write path — backup precondition, RPC caller, never-overwrite guarantee** — `c1020c7` (test, RED) → `e047c02` (feat, GREEN)

**Plan metadata:** commit for this SUMMARY.md follows.

## Files Created/Modified

- `scripts/backfill_claim_time_attribution.py` — the OWN-03 CLI: CLI parsing, sentinel discovery, `resolve_source_1..4`, the `--apply` write path, JSON/CSV report writer.
- `tests/test_backfill_claim_time_attribution.py` — fixture-driven test suite with a dedicated filter-aware fake Supabase client (no live Smartsheet/Supabase access anywhere).
- `.gitignore` — `generated_docs/own03_*.json` / `.csv` added under the existing `generated_docs/` block (claimer PII, never committed).

## Decisions Made

See `key-decisions` in frontmatter — summarized: (1) sentinel discovery uses `prefetch_attribution` over `_lookup_attribution_all`; (2) `--wr`/`--weeks` are effectively required rather than defaulting to "every WR with a sentinel role"; (3) source 3's filename-token map covers all 7 pipeline variants, not just the plan's 3 named examples; (4) `public.artifacts.variant` is used directly rather than sniffing filenames to classify rows; (5) the backup-table probe returns a 3-way status vocabulary, not a boolean; (6) `_write_reports` gained optional parameters instead of a second writer function; (7) unrecognized RPC per-row results are treated as errors defensively.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `--roles` default (all three) inflated expected row counts in early tests**
- **Found during:** Task 1, while writing `KnownGoodSampleDryRunTests`
- **Issue:** `is_sentinel_claimer(None) == True`, so the default `--roles primary,helper,vac_crew` produced 3x the expected sentinel-target count in fixtures whose `helper`/`vac_crew` columns were `None` (correctly flagged as sentinel, but not what those early tests expected).
- **Fix:** Added a `roles` parameter to the test helper, scoped existing known-good-sample assertions to `roles="primary"`, and added a dedicated `test_default_roles_scope_covers_all_three_roles` test proving the all-three-roles-by-default behavior explicitly (primary resolves via source 4, helper/vac_crew report `unresolved`).
- **Files modified:** `tests/test_backfill_claim_time_attribution.py`
- **Committed in:** `d49be6b` (Task 1 commit)

**2. [Rule 1 - Bug] `sentry_sdk.start_span(description=...)` deprecation**
- **Found during:** Task 1
- **Issue:** sentry-sdk 2.63.0 deprecates the `description` kwarg in favor of `name`; the rest of the codebase (`pipeline/discovery.py`, `pipeline/fetch.py`, `pipeline/orchestrate.py`, `pipeline/upload.py`) already uses `name=`.
- **Fix:** Used `name=` throughout this script's `sentry_sdk.start_span(...)` calls, matching the established codebase convention.
- **Files modified:** `scripts/backfill_claim_time_attribution.py`
- **Committed in:** `d49be6b` (Task 1 commit)

**3. [Rule 2 - Missing Critical] Full 7-token filename map for source 3**
- **Found during:** Task 2
- **Issue:** The plan's own source-3 enumeration named only `_User_`, `_Helper_`, `_VacCrew_` — omitting the subcontractor helper filename tokens (`_ReducedSub_Helper_`, `_AEPBillable_Helper_`) and the subcontractor primary tokens (`_ReducedSub_User_`, `_AEPBillable_User_`). Filenames for those variants would have silently never resolved via source 3.
- **Fix:** Implemented the full 7-variant `_VARIANT_FILENAME_TOKENS` map, keyed off each `public.artifacts` row's own `variant` column (no filename sniffing needed to classify a row, sidestepping the `_User_`-is-a-substring-of-`_ReducedSub_User_` ambiguity).
- **Files modified:** `scripts/backfill_claim_time_attribution.py`
- **Committed in:** `7912fd2` (Task 2 commit)

**4. [Rule 1 - Bug] Docstring literal false-positive on the structural test**
- **Found during:** Task 1
- **Issue:** `_discover_sentinel_targets`'s docstring contained the literal substring `` `supabase.table("attribution_snapshot")` `` in explanatory prose (describing what the function does NOT do), which false-positive-tripped this script's own structural contract test.
- **Fix:** Reworded to "never a raw Supabase table-select on the attribution_snapshot table", preserving meaning while avoiding the exact literal.
- **Files modified:** `scripts/backfill_claim_time_attribution.py`
- **Committed in:** `d49be6b` (Task 1 commit)

---

**Total deviations:** 4 auto-fixed (2 bugs, 1 missing-critical-functionality, 1 self-inflicted test false-positive)
**Impact on plan:** All auto-fixes necessary for correctness or coverage completeness. No scope creep — no architectural changes, no new dependencies, no behavior outside this plan's `<threat_model>` and `<must_haves>`.

## Issues Encountered

None beyond the auto-fixed deviations above. `python -m pytest`, `py_compile`, `--help`, `git check-ignore`, and the full suite all passed on first or second attempt after each fix.

## User Setup Required

None — no external service configuration required. `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` are read from the existing environment contract every `billing_audit` / `pipeline_memory` script already uses; this plan never calls `--apply`.

## Next Phase Readiness

- `scripts/backfill_claim_time_attribution.py` is ready for plans 12-02 through 12-06 to build on: the sentinel-cleanup predicate work (12-02), the owner-deployed SQL/RPC/backup-table contract (12-03) this script's `--apply` path already calls by name, the cell-history source 5 job (12-04), the runbook page (12-05), and the human-checkpoint live-apply run (12-06).
- Blocker for 12-03: the `billing_audit.backfill_attribution(p_rows jsonb)` RPC and `attribution_snapshot_backup_<YYYYMMDD>` table do not exist yet (owner-deployed) — `--apply` will return exit 3 (backup absent) against any real environment until that plan lands. This is expected and by design; no code in this plan can create Supabase DDL/RPCs.
- No known stubs. No skipped tests. No unrun `<verify>` commands — every plan-level verification command listed in `12-01-PLAN.md` was executed and passed in this session.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-03*

## Self-Check: PASSED

- FOUND: `scripts/backfill_claim_time_attribution.py`
- FOUND: `tests/test_backfill_claim_time_attribution.py`
- FOUND: `.planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-01-SUMMARY.md`
- FOUND commit: `d49be6b` (Task 1)
- FOUND commit: `2b9f3b3` (Task 2 RED)
- FOUND commit: `7912fd2` (Task 2 GREEN)
- FOUND commit: `c1020c7` (Task 3 RED)
- FOUND commit: `e047c02` (Task 3 GREEN)

## Post-merge review fixes

An independent production-risk review of `scripts/backfill_claim_time_attribution.py`
(commit `d922d29`) found seven issues, all fixed in the same commit:

- **Targeting (HIGH):** `_discover_sentinel_targets` treated a role whose current
  frozen value was `None`/blank as a sentinel target (`is_sentinel_claimer(None)`
  is `True`), so source 2 could propose the primary claimer's name into a
  `helper`/`vac_crew` role that never had one. Default targeting now requires a
  NAMED sentinel (non-blank string classified by `is_sentinel_claimer`); the
  opt-in `--include-blank-roles` flag restores the prior behavior and is recorded
  in the report `summary`. The same rule was applied inside `_build_apply_payload`.
- **Batched reads (HIGH):** source 1 (`row_event`/`row_state`) queried once per
  `row_id`. Rewritten as `_prefetch_row_events_and_states`, which issues chunked
  `.in_()` reads over every in-scope `row_id` (chunk size 500, mirroring
  `pipeline_memory/reader.py`) and groups results in Python — never one query
  per row.
- **Silent read failure (HIGH):** `with_retry` returning `None` on failure was
  treated as a genuine zero-row read by every source fetcher. All five read
  sites now raise `_SourceReadConnectivityError` on a `None` result, which
  propagates to `main()`'s existing connectivity `try`/`except` (exit 7) instead
  of producing an incorrect `unresolved` report row.
- **Discovery status (MED):** `main()` only treated `prefetch_attribution`'s
  `'fetch_failure'` status as fatal; `'unavailable'` / `'rpc_missing'` fell
  through silently to zero targets and exit 0. `main()` now fails (exit 7) on
  any status outside `{'success', 'no_row'}`.
- **Determinism (MED, plan must_have):** added explicit `.order()` clauses to
  the `group_content_hash`, `group_state`, `artifacts` and `row_state` reads,
  and sort candidate rows in Python before `_resolve_single_name` builds
  conflict evidence and before `_pick_best_entry` breaks ties, so two runs over
  the same rows produce byte-identical reports regardless of server row order.
- **Apply reconciliation (MED):** each RPC chunk's response is now checked for
  `len(results) == len(chunk)`; a mismatch logs an ERROR and folds into
  `local_exceptions` so `main()` returns 6 instead of trusting a
  partial/over-long response.
- **Report dir (LOW):** a `--report-dir` that resolves outside `generated_docs/`
  now logs a WARNING that its files will not be git-ignored — the run is never
  refused.

Tests added/updated in `tests/test_backfill_claim_time_attribution.py`:
`BlankRoleTargetingTests`, `BatchedReadsTests`, `SourceReadFailureTests`,
`DeterminismTests`, `DiscoveryStatusTests`,
`ApplyPathTests::test_apply_rpc_result_count_mismatch_returns_6`,
`KnownGoodSampleDryRunTests::test_report_dir_outside_generated_docs_warns_not_refuses`;
`test_default_roles_scope_covers_all_three_roles` and the two subcontractor/bare
`_Helper_` source-3 tests were updated to use `--include-blank-roles` / a named
sentinel so they still exercise the intended behavior under the new default
targeting rule. Full suite: 1994 passed, 1 skipped, 365 subtests passed.

### Greptile review fix (PR #387) — source-1 in-week guard

Greptile's review of PR #387 found that source 1 never compared a
`row_event` / `row_state` row's own `week_ending` to `target.week_ending`:
the bulk query selected `row_id,observed_at,after_image` only and
`resolve_source_1` returned the first qualifying event chronologically, so a
row re-dated after a data correction could have an EARLIER week's owner
written for a later target week — a D-12-A violation that the GSD gates and
the Opus round both missed. Fix: the query now also selects `week_ending`;
`_in_target_week()` requires the row's own week to equal the target week in
both loops; a NULL/missing week is never in-week evidence (the row stays
unresolved — the safe direction). Fixture helpers `_row_event` / `_row_state`
now carry a `week_ending` column defaulting to the row's own week. Four tests
added in `SourcesOneTwoThreeTests`: `test_source_1_ignores_row_event_from_
another_week`, `..._ignores_row_state_from_another_week`,
`..._stays_unresolved_with_only_other_week_evidence`,
`..._skips_event_whose_week_is_unknown`. Full suite: 1998 passed.

The mandatory Opus production-risk review of the fix returned SHIP with one
HIGH follow-up, closed in the same round: the fake client ignores column
projections, so the batching test now pins `week_ending` in the row_event
select (`_FakeTable.last_select_args`), and the resolver tallies skipped
out-of-week rows into `summary.source_1_out_of_week_rows` plus one INFO log
line, so an all-unresolved run caused by a missing week column is visible.
Opus MEDIUM carried to 12-06: `week_ending` is nullable on both tables and
`row_state.week_ending` refreshes only when `content_hash` changes, so before
`--apply` is unblocked run a read-only count of NULL / stale-week
`row_event` / `row_state` rows for the target `row_id`s and record it.
