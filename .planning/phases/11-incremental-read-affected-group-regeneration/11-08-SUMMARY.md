---
phase: 11-incremental-read-affected-group-regeneration
plan: 08
subsystem: pipeline, pipeline_memory, ci-workflow
tags: [inc-05, retirement, group_state, sheet_registry, mypy-baseline, living-ledger, tdd]

# Dependency graph
requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "11-07's get_parity_streak(limit) and the retire-now decision re-opened 2026-08-31 with a real 5/5 streak reading (11-07-SUMMARY.md 'Task 2 -- DECISION RE-OPENED')"
provides:
  - "group_state.content_hash as the sole change-detection skip gate (pipeline/change_detection.py::_resolve_unchanged_for_skip, pipeline_memory/reader.py::get_group_state_content_hashes_by_wr)"
  - "discover_source_sheets() validating every candidate sheet in full every run, with sheet_registry as the only cross-run sheet-identity store (pipeline/discovery.py)"
  - "Zero GitHub Actions cache steps for the three retired local JSON caches (.github/workflows/weekly-excel-generation.yml)"
  - "The dated Phase 11 closing entry in memory-bank/living-ledger.md"
affects: ["Phase 12/13 planning -- Phase 11 is now fully shipped; no further INC-05 follow-up plan is open"]

# Actuals (#2632)
actuals:
  tokens: 70500
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Batch pre-fetch pattern (established 11-08 Task 2, reused Task 3): query pipeline_memory once before the group loop, build a local dict, zero-I/O in-memory lookups per iteration -- get_group_state_content_hashes_by_wr mirrors get_group_state_attachments_by_wr exactly."
    - "history_key format changed from MMDDYY (week_raw) to ISO date (week_iso) to match group_state.week_ending's DATE column type -- required reordering history_key construction to after week_iso is computed."
    - "Always-full discovery: no incremental/cached fast path in discover_source_sheets(); sheet_registry (already written by pre-existing get_sheet_watermarks/upsert_sheet_registry calls) is the only place sheet identity persists across runs."
    - "Stale mypy baselines are refrozen, not chased line-by-line, once the underlying error SET is confirmed unchanged (28 errors, same files) and the only drift is untyped-function annotation notes shifting with unrelated file growth -- confirmed via a disposable git worktree diff against the pre-Task-3 commit."

key-files:
  created: []
  modified:
    - pipeline/orchestrate.py
    - pipeline/config.py
    - pipeline/discovery.py
    - pipeline/change_detection.py
    - pipeline/attribution.py
    - pipeline/observability.py
    - pipeline_memory/reader.py
    - generate_weekly_pdfs.py
    - billing_audit/schema.sql
    - .github/workflows/weekly-excel-generation.yml
    - .github/prompts/configuration-environment.md
    - CLAUDE.md
    - memory-bank/living-ledger.md
    - tests/test_incremental_read.py
    - tests/golden/baseline_names.json
    - tests/golden/facade_allowlist.json
    - tests/golden/mypy_baseline.txt
    - tests/golden/mypy_baseline_count.txt
    - "10 additional test files (see Test Rewrite Accounting below)"

key-decisions:
  - "Task 1's gate was satisfied by citation, not re-derivation: 11-07-SUMMARY.md's 'Task 2 -- DECISION RE-OPENED (2026-08-31)' section already records option id retire-now with a real get_parity_streak() = 5/5 reading (contributing runs 33449808275.1, 33429256710.1, 33418485870.1, 33407578625.1, 33396264753.1) and the before wall-clock figures. This plan executed strictly against that recorded authorisation, on its own branch feat/11-08-inc05-retirement cut after #371/#372 merged."
  - "discover_source_sheets() gets no sheet_registry-based fast path -- sheet_registry has no name column, so _validate_single_sheet()'s mandatory get_sheet(sid, include='columns') call is needed regardless. Any registry-based skip could only ever bypass the secondary sample-row fuzzy-matching cost, not the primary API call -- not worth the added complexity to a heavily-tested VAC-crew matching function. Always-full validation satisfies the plan's key_link ('sheet discovery reads sheet_registry instead of discovery_cache.json') at the system level via the pre-existing get_sheet_watermarks/upsert_sheet_registry calls, unmodified by this plan."
  - "The four one-time hash-history migration-prune functions (_run_phase_1_1_hash_prune, _run_subproject_b_hash_prune, _run_vac_crew_hash_prune, _run_subproject_d_hash_prune) stay DEFINED in pipeline/attribution.py (harmless, still fixture-tested) with their call sites removed from orchestrate.py's main() -- one-time migrations almost certainly already completed in production."
  - "billing_audit_row_cache becomes a purely in-memory, never-persisted-across-runs set (file load/save removed, in-loop .add()/in usage untouched) -- freeze_row/freeze_attribution's server-side first-write-wins idempotency makes the worst case a few redundant-but-safe RPC calls per run, never a correctness issue."
  - "history_updates (part of the frozen run_summary.json 21+1-key contract) keeps its old semantics via two new increment sites: history_updates += 1 inside the TEST_MODE branch at emission time (mirrors the old immediate-write path), and history_updates += len(_mem_group_records) in production, sourced from _build_group_state_flush's already-computed record count."
  - "Operator escalation flags (RESET_HASH_HISTORY, REGEN_WEEKS, RESET_WR_LIST, FORCE_GENERATION) are re-verified, not re-tested: they were already covered end-to-end by tests/test_incremental_read.py::test_trigger5_operator_flags_force_full against resolve_run_mode's D-02 trigger 5, which is boolean/env-var based and structurally independent of hash_history.json's existence. That test's logic and passing status are unchanged by this plan's edits. The plan's own per-group _history_eligible_for_skip gate (a separate, unchanged inline check) is covered only by its unchanged source text matching the unchanged test at the run-level trigger; no new dedicated test was added for the per-group gate specifically, since its logic was not touched."
  - "Two out-of-scope documentation staleness findings (.github/instructions/copilot-setup.instructions.md, scripts/notion_sync.py's DISCOVERY_CACHE_VERSION regex, tests/test_security_audit_followup.py's obsolete-but-still-green TestDiscoveryCacheFastPathSkipsOnPartialCorruption truth-table) were logged to deferred-items.md rather than fixed -- none are in this plan's files_modified and none block any acceptance criterion or currently-passing test."
  - "The pre-existing mypy Gate 4 baseline (tests/golden/mypy_baseline.txt) was refrozen. It was last regenerated 2026-08-24 (Phase 09), before Phase 10 and Phase 11's growth of orchestrate.py; a disposable git worktree at commit a0b0432 (Task 2, before any Task 3 edit) proved the drift (67 -> 68 lines, 25 files checked vs the frozen 24) was already present before Task 3 touched anything. The distinct error SET is unchanged (28 errors, same files) both before and after -- only untyped-function annotation notes shifted line numbers. Refrozen to 68, LF-only per the repo's tests/golden/*.txt convention."

requirements-completed: [INC-05]

coverage:
  - id: T-11-38
    description: "Task 3 removes exactly six cache steps and nothing else; the schedule, timeout-minutes: 180, TIME_BUDGET_MINUTES, and the advanced_options parser all survive."
    requirement: "INC-05"
    verification:
      - kind: unit
        ref: "python one-liner verify command (WORKFLOW_OK); git diff shows exactly 48 deletions across two hunks, both restore/save step pairs, nothing else"
        status: pass
    human_judgment: false
  - id: T-11-39
    description: "TIME_BUDGET_MINUTES stays 165 and timeout-minutes stays 180 across both tasks."
    requirement: "INC-05"
    verification:
      - kind: unit
        ref: "workflow diff (below) touches no schedule/budget line"
        status: pass
    human_judgment: false
  - id: T-11-40
    description: "Operator escalation flags still force full regeneration against group_state."
    requirement: "INC-05"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::test_trigger5_operator_flags_force_full (unchanged, still passing)"
        status: pass
    human_judgment: false
  - id: T-11-41
    description: "Attachment identity is not lost with the pre-fetch cache -- group_state supplies it, with the existing per-row fallback intact (Task 2, this plan)."
    requirement: "INC-05"
    verification:
      - kind: unit
        ref: "pipeline/cleanup.py consumers unmodified by Task 3; verified by the full pytest suite"
        status: pass
    human_judgment: false
  - id: T-11-43
    description: "The streak authorisation is re-confirmed at execution time, not just cited from a stale record."
    requirement: "INC-05"
    verification:
      - kind: manual
        ref: "11-07-SUMMARY.md 'Task 2 -- DECISION RE-OPENED (2026-08-31)' -- real get_parity_streak() = 5/5 read on merged master #372 = d9bd2b2, before this branch's first commit"
        status: pass
    human_judgment: true
    rationale: "Owner-only re-authorisation citation per the plan's precondition; this executor did not and could not independently re-run a live Supabase scan."
  - id: T-11-44
    description: "No secrets or row-level billing data in the Living Ledger entry."
    requirement: "INC-05"
    verification:
      - kind: unit
        ref: "memory-bank/living-ledger.md Task 4 entry -- rule names, env-var names, and run ids only"
        status: pass
    human_judgment: false

duration: ~2h (continuation agent: Tasks 2-4 plus plan-level gate remediation; Task 1 pre-resolved by owner citation)
completed: 2026-08-31
status: complete
---

# Phase 11 Plan 08: INC-05 Retirement Summary

**Retired the three local JSON caches, their two attachment pre-fetch phases, and six GitHub Actions cache steps -- `group_state.content_hash` and `sheet_registry` are now the sole cross-run stores, closing Phase 11.**

## Performance

- **Duration:** ~2h (continuation agent picking up mid-Task-3; Task 1's gate was a citation of 11-07's already-recorded `retire-now` decision, not re-executed)
- **Tasks:** 3 of 4 executed by this agent (Task 1 pre-resolved by owner; Task 2 was completed by a prior segment of this same continuation before compaction)
- **Commits:** 5 (`a0b0432` Task 2, `3f25082` Task 3, `f280ee9` Task 4, `7279448` plan-level gate fix, plus this metadata commit)
- **Files touched (whole plan vs. `origin/master` merge-base):** 35 files, +1890/-1823 lines (~70.5K estimateTokens)

## Checkpoint / Decisions

### Task 1 — GATE (satisfied by citation)

Per this plan's execution instructions, Task 1 was pre-resolved by the owner:
option id **`retire-now`**, backed by a real `get_parity_streak()` reading of
**5/5** with no intervening `fail`, recorded in `11-07-SUMMARY.md`'s "Task 2
— DECISION RE-OPENED (2026-08-31)" section (contributing run ids
`33449808275.1`, `33429256710.1`, `33418485870.1`, `33407578625.1`,
`33396264753.1`). This plan executed strictly against that citation, on its
own branch `feat/11-08-inc05-retirement`, cut from `origin/master` after
#371/#372 merged. No plan 01-07 work rides on this branch.

## Accomplishments

### Task 2 — Retire the two attachment pre-fetch phases

Completed in an earlier segment of this continuation (commit `a0b0432`).
Both attachment pre-fetch phases and `ATTACHMENT_PREFETCH_MAX_MINUTES` /
`ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` removed; `group_state` supplies
attachment identity with the existing per-row on-demand fallback in
`pipeline/cleanup.py` untouched; `CLAUDE.md` and
`docs/run-memory-write-flip-checklist.md`'s before-figure section updated.

### Task 3 — Retire the three local JSON caches and their workflow cache steps

- `group_state.content_hash` is now the sole change-detection skip gate.
  `pipeline/change_detection.py::_resolve_unchanged_for_skip` takes a
  caller-supplied `group_state_hashes` dict (renamed from `hash_history`);
  `pipeline_memory/reader.py::get_group_state_content_hashes_by_wr` builds it
  once per run (batch pre-fetch, mirrors the Task 2 attachment pattern).
  `history_key` moved from MMDDYY (`week_raw`) to ISO (`week_iso`) to match
  `group_state.week_ending`'s DATE column type.
- `discover_source_sheets()` validates every candidate sheet in full every
  run; the ~110-line cache-load/TTL/incremental-vs-full dichotomy in
  `pipeline/discovery.py` is gone. `sheet_registry` (via the pre-existing,
  unmodified `get_sheet_watermarks`/`upsert_sheet_registry` calls in
  `pipeline/orchestrate.py`) is now the only place sheet identity persists
  across runs. `FORCE_REDISCOVERY` stays on the facade for runbook/back-compat
  reasons but is a no-op.
- `billing_audit_row_cache` (dedupe set for `freeze_row`/`freeze_attribution`
  RPC calls) is now purely in-memory per run; its JSON persistence removed.
- Six GitHub Actions cache steps removed from
  `.github/workflows/weekly-excel-generation.yml` -- full diff below.
- Operator escalation flags (`RESET_HASH_HISTORY`, `REGEN_WEEKS`,
  `RESET_WR_LIST`, `FORCE_GENERATION`) unchanged in behavior: they still
  force full regeneration via `resolve_run_mode`'s D-02 trigger 5, which was
  never touched and is structurally independent of `hash_history.json`'s
  existence. `tests/test_incremental_read.py::test_trigger5_operator_flags_force_full`
  already covers all four flags and continues to pass.
- `CLAUDE.md` (Data Pipeline Architecture, Configuration section, Critical
  Pitfalls) and `.github/prompts/configuration-environment.md` updated so no
  documentation describes a cache that no longer exists.
- `docs/run-memory-write-flip-checklist.md`'s "after" wall-clock figure was
  already recorded as PENDING (with the before figures and the baseline) by
  an earlier segment of this continuation -- confirmed present, not
  re-written.

### Task 4 — Living Ledger closing entry

Appended a dated `## [2026-08-31 20:44] Phase 11 shipped` entry to the
bottom of `memory-bank/living-ledger.md` (89 additions, 0 deletions),
recording: the seven D-02 escalation triggers; capture-time watermark
persistence (`SAFETY_WINDOW_MINUTES` subtracted only at query-build time);
that frequent runs never detect deletions; D-06's zero-deletion-in-
incremental-mode rule; the shadow-parity comparator; D-09 streak semantics
(`get_parity_streak`); the INC-05 retirement summary (`group_state`, the
94-minute baseline, run `32743959053`); and the rollout-ordering rule this
phase proves out. No secrets, no row-level data, nothing inlined into
`CLAUDE.md`.

## Task Commits

1. **Task 2:** `a0b0432` — `feat(11-08): retire attachment pre-fetch for group_state`
2. **Task 3:** `3f25082` — `feat(11-08): retire local JSON caches (INC-05)`
3. **Task 4:** `f280ee9` — `docs(11-08): Phase 11 Living Ledger closing entry`
4. **Plan-level gate fix:** `7279448` — `fix(11-08): drop retired USE_DISCOVERY_CACHE, refresh mypy baseline`

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

## Workflow Diff (Task 3, full and verbatim)

```diff
diff --git a/.github/workflows/weekly-excel-generation.yml b/.github/workflows/weekly-excel-generation.yml
index bbbe766..fb0f863 100644
--- a/.github/workflows/weekly-excel-generation.yml
+++ b/.github/workflows/weekly-excel-generation.yml
@@ -162,31 +162,6 @@ jobs:
           key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
           restore-keys: |
             ${{ runner.os }}-pip-
-      # Use restore/save split so caches persist even when the job times out or fails
-      - name: Restore hash history cache
-        uses: actions/cache/restore@v4
-        with:
-          path: generated_docs/hash_history.json
-          key: hash-history-${{ github.ref_name }}-${{ github.run_id }}
-          restore-keys: |
-            hash-history-${{ github.ref_name }}-
-            hash-history-
-      - name: Restore discovery cache
-        uses: actions/cache/restore@v4
-        with:
-          path: generated_docs/discovery_cache.json
-          key: discovery-cache-${{ github.ref_name }}-${{ github.run_id }}
-          restore-keys: |
-            discovery-cache-${{ github.ref_name }}-
-            discovery-cache-
-      - name: Restore billing-audit row cache
-        uses: actions/cache/restore@v4
-        with:
-          path: generated_docs/billing_audit_frozen_rows.json
-          key: billing-audit-rows-${{ github.ref_name }}-${{ github.run_id }}
-          restore-keys: |
-            billing-audit-rows-${{ github.ref_name }}-
-            billing-audit-rows-
       - name: Install dependencies
         run: |
           python -m pip install --upgrade pip
@@ -786,29 +761,6 @@ jobs:
           echo "3. **By Week Ending** - Weekly billing periods" >> $GITHUB_STEP_SUMMARY
           echo "4. **Manifest** - JSON index with file metadata" >> $GITHUB_STEP_SUMMARY
       
-      # ==================== CACHE SAVE (runs even on timeout/failure) ====================
-      - name: Save hash history cache
-        if: always()
-        uses: actions/cache/save@v4
-        with:
-          path: generated_docs/hash_history.json
-          key: hash-history-${{ github.ref_name }}-${{ github.run_id }}
-      
-      - name: Save discovery cache
-        if: always()
-        uses: actions/cache/save@v4
-        with:
-          path: generated_docs/discovery_cache.json
-          key: discovery-cache-${{ github.ref_name }}-${{ github.run_id }}
-
-      - name: Save billing-audit row cache
-        if: always()
-        continue-on-error: true
-        uses: actions/cache/save@v4
-        with:
-          path: generated_docs/billing_audit_frozen_rows.json
-          key: billing-audit-rows-${{ github.ref_name }}-${{ github.run_id }}
-      
       - name: Summary
         if: always()
         run: |
```

48 lines removed across two hunks, both cache restore/save step pairs, and
nothing else. The cron schedule, `timeout-minutes: 180`,
`TIME_BUDGET_MINUTES: '165'`, the execution-type step, the env block, and
the `advanced_options` key:value parser are all byte-identical.

## Test Rewrite Accounting (Task 3)

Ground truth from `git diff` on the Task 3 commit (`3f25082`), matched by
exact `def test_...` method signature (a name-preserving in-place edit --
kwarg rename, assertion string change, count assertion 3→2 -- does not
appear in this list; it is a body-only edit inside an unchanged method):

**15 test methods removed** (all replaced by an equivalent or explicit
"retired" assertion, never silently deleted):
`test_discovery_cache_version_bumped_to_4`,
`test_error_legs_invalidate_both_hash_layers`,
`test_full_mode_not_exceeded_prunes_stale_keys_as_today`,
`test_full_mode_time_budget_exceeded_skips_as_today`,
`test_gate_condition_matches_source_byte_for_byte`,
`test_history_updates_write_stays_outside_the_gate`,
`test_incremental_mode_preserves_every_key_regardless_of_time_budget`,
`test_incremental_skip_is_logged_with_preserved_key_count`,
`test_json_flush_consults_upload_results`,
`test_json_flush_not_gated_on_supabase_flag`,
`test_json_hash_history_deferred_in_production`,
`test_phase_prune_version_survives_round_trip`,
`test_save_handles_int_sentinel_in_retention_sort`,
`test_workflow_and_schema_untouched`,
`test_zero_keys_removed_for_strict_subset_groups_in_incremental_mode`.

**11 test methods added:**
`test_discovery_cache_constants_removed`,
`test_error_legs_invalidate_durable_hash_layer`,
`test_group_state_flush_consults_upload_results`,
`test_group_state_flush_has_no_stale_key_prune_equivalent`,
`test_group_state_flush_not_gated_on_supabase_flag`,
`test_hash_history_persistence_helpers_removed`,
`test_history_updates_advances_immediately_only_in_test_mode`,
`test_schema_untouched`,
`test_site_3_stale_key_prune_is_retired`,
`test_stale_key_prune_gate_removed_from_source`,
`test_workflow_caches_retired_but_schedule_and_budget_survive`.

The last pair (`test_schema_untouched` /
`test_workflow_caches_retired_but_schedule_and_budget_survive`) replaces
`test_workflow_and_schema_untouched`, discovered failing during this plan's
own `bash scripts/run_6_gates.sh` run because it asserted `git diff
--exit-code` was clean across `.github/workflows/` -- an assumption this
task's own authorised workflow edit invalidates. Split into a permanent
`pipeline_memory/schema.sql`-only zero-diff guard plus a positive
post-retirement invariant guard (zero `actions/cache/` steps; schedule/
budget/parser anchors present) so a future change cannot silently
reintroduce a cache step.

Additional in-place edits (unchanged method name, modified body/assertions,
not counted above): `tests/test_group_identity_and_header_foreman.py`,
`tests/test_primary_claim_attribution.py` (`TestSitesBCIdentity`),
`tests/test_subcontractor_primary_claim_attribution.py`
(`TestThreeIdentitySitesCarryClaimer`),
`tests/test_vac_crew_claim_attribution.py`,
`tests/test_subcontractor_pricing.py`, and multiple keyword-argument
renames (`hash_history=` → `group_state_hashes=`) across
`tests/test_subproject_e_hash_store.py::TestAuthoritativeSkipGate`.

None were silently deleted. Every removed test's coverage intent is either
preserved (rewritten against the new `group_state`/`sheet_registry`
surface) or replaced with an explicit "this gate/path is retired" assertion.

## Gate Results

- `python -m pytest tests/test_incremental_read.py -q` — 141 passed, 16
  subtests passed.
- `python -m pytest tests/ -q` — **1845 passed, 1 skipped, 306 subtests
  passed** (0 failed).
- `python -m py_compile generate_weekly_pdfs.py` — clean.
- Workflow verify one-liner — `WORKFLOW_OK` (zero `actions/cache/` steps;
  `timeout-minutes: 180` / `TIME_BUDGET_MINUTES` / `advanced_options` all
  present).
- Literal-filename `git grep` verify one-liner (`hash_history.json`,
  `discovery_cache.json`, `billing_audit_frozen_rows.json` across
  `pipeline/`, `billing_audit/`, `generate_weekly_pdfs.py`) — `CACHE_REFS:
  (none)`, exit 1 (grep's no-match code) as required.
- `git diff --exit-code -- pipeline_memory/schema.sql` — clean, zero schema
  change across the whole phase (this rule applies only to
  `pipeline_memory/schema.sql`, not `billing_audit/schema.sql`, whose
  comment-only edit is unrelated and safe).
- `bash scripts/run_6_gates.sh` — **ALL 6 GATES PASSED** (run once at the
  plan level, after the fix below):
  - Gate 1 (AST import equality): PASS, 164 baseline names present.
  - Gate 2 (facade completeness): PASS, 101 allowlist names resolve.
  - Gate 3 (pytest): PASS, full suite as above.
  - Gate 4 (mypy delta): PASS, `68 -> 68` (see "Plan-Level Gate Remediation"
    below for the fix and the baseline refresh).
  - Gate 5 (py_compile): PASS.
  - Gate 6 (golden run_summary): PASS, 22-key structural match.

## Plan-Level Gate Remediation (Rule 1 + Rule 3 auto-fixes)

Running `bash scripts/run_6_gates.sh` at the plan level (as required once
before declaring the plan complete) surfaced two issues, both fixed and
committed as `7279448` before re-running the full gate suite to green:

1. **Rule 1 (auto-fix bug):** `pipeline/observability.py`'s Sentry init
   context still read `_cfg.USE_DISCOVERY_CACHE` after Task 3 removed that
   constant from `pipeline/config.py` -- a live `AttributeError` the moment
   Sentry actually initializes with a configured DSN. Mypy's `attr-defined`
   check caught it (`Module has no attribute "USE_DISCOVERY_CACHE"`); the
   stale key was dropped from the `set_context("configuration", {...})` dict.
2. **Rule 3 (auto-fix blocking issue):** Gate 4's mypy delta check failed
   (`65 -> 69`, then `65 -> 68` after fix 1) against a baseline
   (`tests/golden/mypy_baseline.txt`) last regenerated 2026-08-24 (Phase 09)
   -- weeks before Phase 10 and Phase 11 (plans 01-07) grew
   `pipeline/orchestrate.py` substantially. A disposable `git worktree add
   --detach` at commit `a0b0432` (this plan's Task 2, before any Task 3 edit)
   proved the drift was **already present** before Task 3 touched anything
   (67 lines, 25 files checked, vs. the frozen 65/24) -- this plan's Task 3
   only added 1 more line on top of that pre-existing drift. The distinct
   *error set* is unchanged both before and after (28 errors, same 7 files);
   the only difference is `annotation-unchecked` informational notes whose
   line numbers shifted with the file's unrelated growth, plus one more file
   entering the checked set. Refroze `tests/golden/mypy_baseline.txt` /
   `mypy_baseline_count.txt` against current state (68, LF-only, matching the
   repo's `tests/golden/*.txt` convention) rather than chasing individual
   note line numbers across a 5000+ line file.

## Files Created/Modified

See `key-files.modified` in the frontmatter for the full list (18 named
files plus 10 test files under "Test Rewrite Accounting" above).

## Decisions Made

See `key-decisions` in the frontmatter for the full list. Most
consequential: `discover_source_sheets()` gets no sheet_registry-based fast
path (always-full validation instead), and the mypy baseline was refrozen
rather than chased line-by-line once the error set was confirmed unchanged.

## Deviations from Plan

### Rule 1 — Auto-fixed bugs

**1. [Rule 1 - Bug] `pipeline/observability.py` referenced the retired
`USE_DISCOVERY_CACHE` constant**
- **Found during:** Plan-level `bash scripts/run_6_gates.sh` run (Gate 4,
  mypy `attr-defined`).
- **Issue:** Sentry init's `set_context("configuration", {...})` read
  `_cfg.USE_DISCOVERY_CACHE`, which Task 3 removed from `pipeline/config.py`.
  A live `AttributeError` the next time Sentry actually initializes.
- **Fix:** Dropped the key from the context dict, with a retirement comment.
- **Files modified:** `pipeline/observability.py`
- **Commit:** `7279448`

### Rule 3 — Auto-fixed blocking issues

**2. [Rule 3 - Blocking] Stale mypy Gate 4 baseline blocked the plan-level
gate requirement**
- **Found during:** Same gate run.
- **Issue:** `tests/golden/mypy_baseline.txt` was frozen 2026-08-24 (Phase
  09), predating Phase 10/11's growth of `orchestrate.py`; the drift
  (25 files checked vs. the frozen 24, note line numbers shifted) was
  confirmed pre-existing (present at commit `a0b0432`, before Task 3) via a
  disposable comparison worktree, not introduced by this plan.
- **Fix:** Refroze both baseline files against current state after fixing
  issue 1. Error set unchanged (28 errors, same files).
- **Files modified:** `tests/golden/mypy_baseline.txt`,
  `tests/golden/mypy_baseline_count.txt`
- **Commit:** `7279448`

### Rule-neutral (plan-mandated, not a deviation)

The 15-removed/11-added test rewrite in Task 3 is explicitly required by the
plan's own action text ("Rewrite, do not silently delete... Record in the
plan SUMMARY how many tests were rewritten and how many removed as genuinely
obsolete") -- documented under "Test Rewrite Accounting" above, not listed
here as a deviation.

### Logged, not fixed (out of scope — SCOPE BOUNDARY)

Two stale-documentation findings and one stale-but-still-green test class
were discovered but are not in this plan's `files_modified` and do not block
any acceptance criterion; logged to
`.planning/phases/11-incremental-read-affected-group-regeneration/deferred-items.md`:
`.github/instructions/copilot-setup.instructions.md` (stale env-var/cache
docs), `scripts/notion_sync.py:507` (a `DISCOVERY_CACHE_VERSION` regex that
now silently never matches, no crash), and
`tests/test_security_audit_followup.py::TestDiscoveryCacheFastPathSkipsOnPartialCorruption`
(a self-contained truth-table test for a gate Task 3 retired; still green,
not currently failing).

## Issues Encountered

None beyond the two Rule 1/Rule 3 auto-fixes documented above, both resolved
before the plan-level gate was declared green.

## Known Stubs

None.

## User Setup Required

None. This plan makes no new external-service or manual-step requirement.

## Next Phase Readiness

- Phase 11 is now fully shipped: all 8 plans have a SUMMARY.md, INC-01
  through INC-05 are complete, and `memory-bank/living-ledger.md` carries
  the phase's dated closing entry.
- The "after" frequent-run wall-clock figure in
  `docs/run-memory-write-flip-checklist.md` remains PENDING by design --
  it cannot exist until the first scheduled `production_frequent` run
  executes against this plan's merged retirement. This is a manual item for
  `11-VALIDATION.md`, not a gap in this plan's completion.
- No blockers introduced. `pipeline_memory/schema.sql` is byte-identical to
  before this plan (confirmed via `git diff --exit-code`).

## Threat Flags

The plan's own STRIDE threat register (T-11-38 through T-11-44) is fully
dispositioned in `coverage` above via automated verification, except
T-11-43 (owner-only re-authorisation citation, `human_judgment: true`). No
new threat surface was introduced by this plan -- it is a pure retirement
(removes cache read/write paths and workflow steps; adds one new read-only
`pipeline_memory` reader function with the same fail-open contract every
other reader function in that module already carries).

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-08-31*

## Self-Check: PASSED

Verified on disk: `pipeline_memory/reader.py` contains
`get_group_state_content_hashes_by_wr`; `.github/workflows/weekly-excel-generation.yml`
contains zero `actions/cache/` occurrences; `memory-bank/living-ledger.md`'s
last `## [` heading contains "Phase 11" and the required strings
`SAFETY_WINDOW_MINUTES`, `get_parity_streak`, `group_state`, `32743959053`
are all present; `tests/golden/mypy_baseline_count.txt` reads `68`.
Commits `a0b0432`, `3f25082`, `f280ee9`, `7279448` all confirmed present via
`git log --oneline --all`. Full suite confirmed green: 1845 passed, 1
skipped, 306 subtests. `bash scripts/run_6_gates.sh` confirmed
`ALL 6 GATES PASSED` on the final run.
