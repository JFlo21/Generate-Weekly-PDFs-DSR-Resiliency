---
phase: 11-incremental-read-affected-group-regeneration
plan: 03
subsystem: pipeline
tags: [smartsheet, attachment-cleanup, hash-history, incremental-read, keep-historical, tdd]

# Dependency graph
requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "Plan 02's resolve_run_mode (source of the resolved 'incremental'/'full' string, carried in main() as _resolved_mode) and run_ledger.mode visibility, which this plan's call sites and prune gate read"
provides:
  - "pipeline.cleanup.cleanup_untracked_sheet_attachments — a keep_historical call-boundary override (default None -> falls back to the module KEEP_HISTORICAL_WEEKS constant) so an incremental-mode run can force preservation of identities absent from valid_wr_weeks without touching the global env-driven constant"
  - "pipeline.orchestrate.main — both cleanup_untracked_sheet_attachments call sites (TARGET + PPP) now pass keep_historical=True if _resolved_mode == 'incremental' else None"
  - "pipeline.orchestrate.main — the hash-history stale-key prune's existing time-budget guard is widened to also require _resolved_mode == 'full', with a suppressed-path log line naming the preserved-key count"
  - "A regression pin (ScopeDerivationTests) proving the seven off-contract / legacy-migration gates in cleanup_untracked_sheet_attachments are already safe by construction because sub_wr_scope / vac_legacy_wr_scope / primary_wr_scope are all derived from this run's groups"
affects: ["11-04 (the plan that first produces a scoped `groups` dict in incremental mode — arrives to a codebase whose destructive maintenance blocks are already gated)", "11-05 (shadow parity harness re-runs these same gates in shadow mode)"]

# Actuals (#2632)
actuals:
  tokens: 8035
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Existing-gate extension over new-gate invention (RESEARCH.md Don't-Hand-Roll table): keep_historical reuses the pre-existing KEEP_HISTORICAL_WEEKS identity-loop gate; the hash-history prune's existing `if not _time_budget_exceeded:` guard is widened with `and _resolved_mode == 'full'` rather than adding a parallel conditional."
    - "Call-boundary override, never a global flip: both cleanup_untracked_sheet_attachments call sites pass keep_historical as a keyword argument computed inline (`True if _resolved_mode == 'incremental' else None`); the module-level KEEP_HISTORICAL_WEEKS constant and its facade rebind are never reassigned."
    - "Pin-with-a-test over re-gate: the seven off-contract / legacy-migration gates inside cleanup_untracked_sheet_attachments receive NO incremental-mode conditional (RESEARCH.md Pitfall 2 — they are already safe by construction); ScopeDerivationTests proves the safety argument with a regression test instead of adding risk-bearing conditionals to billing-critical code."
    - "Duplicate-attachment fixture pattern for identity-loop deletion tests: cleanup_untracked_sheet_attachments only ever deletes attachments BEYOND the single newest one per identity (`atts_sorted[1:]`) — a lone attachment is never deleted through this loop regardless of any gate, so every delete/preserve assertion needs 2+ attachments sharing an identity."

key-files:
  created: []
  modified:
    - pipeline/cleanup.py
    - pipeline/orchestrate.py
    - tests/test_incremental_read.py
    - tests/test_security_audit_followup.py

key-decisions:
  - "keep_historical positioned as the LAST parameter (after dry_run), not immediately after primary_wr_scope as PATTERNS.md's citation implied — tests/test_security_audit_followup.py::TestPppCleanupUntrackedAttachments::test_cleanup_function_signature_unchanged pins dry_run as the trailing kwarg from Phase 08 T-08-03; appending after it (and updating that pin test) preserves the established append-only signature-evolution convention with a smaller, more honest diff than reordering an existing pinned parameter."
  - "The literal source substring `keep_historical=True if _resolved_mode == 'incremental' else None` is written inline at both call sites (not via a precomputed `_keep_historical_override` variable) so the plan's Task 1 acceptance criterion — `pipeline/orchestrate.py` contains the substring `keep_historical=True` at two distinct call sites — is satisfied literally, and so a reader sees the incremental-mode condition directly at the call site rather than one indirection away."
  - "The hash-history suppressed-path log (`elif _resolved_mode != 'full':`) fires ONLY for incremental mode, not for the pre-existing time-budget-exceeded-in-full-mode case — that case's silent skip is unchanged (RESEARCH.md/PATTERNS.md: 'exactly as today'), so the new log line cannot be confused with the pre-existing, differently-caused silent skip."
  - "ScopeDerivationTests isolates the off-contract gates specifically by also passing keep_historical=True in its delete-call test — since the off-contract gates are unconditional (ignore KEEP_HISTORICAL_WEEKS/keep_historical entirely), forcing the base identity-loop gate to preserve means any observed delete_attachment call could only have come from an off-contract branch, making 'zero off-contract deletions for a WR absent from groups' a genuinely isolated assertion rather than one conflated with the base gate."

requirements-completed: [INC-02]

coverage:
  - id: D1
    description: "keep_historical call-boundary override on cleanup_untracked_sheet_attachments — None falls back to KEEP_HISTORICAL_WEEKS (byte-identical for every existing caller); True/False override it explicitly; a strict-subset valid_wr_weeks with keep_historical=True issues zero attachment deletes for identities outside it."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::CleanupPreservationTests (6 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_incremental_read.py::OrchestrateKeepHistoricalWiringTests (2 tests, source-inspection)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The hash-history stale-key prune requires both the pre-existing time-budget guard and the resolved mode being 'full'; an incremental run preserves every hash_history key it did not reach and logs the suppression with the preserved-key count; full-mode behavior (both pruning and the time-budget-exceeded skip) is unchanged."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::HashHistoryPruneTests (7 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The seven off-contract / legacy-migration gates inside cleanup_untracked_sheet_attachments are unmodified and pinned as already-scoped: a WR absent from `groups` is absent from sub_wr_scope, vac_legacy_wr_scope, and primary_wr_scope, and zero off-contract deletions are issued for it. run_ledger_finish's scoped counters (groups_generated/groups_affected/rows_seen) are documented as interpretable only next to run_ledger.mode; run_summary.json's frozen 21-key contract is untouched."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::ScopeDerivationTests (3 tests)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh -> ALL 6 GATES PASSED (pytest 1592 passed/1 skipped/141 subtests; mypy delta 65 -> 65; run_summary.json 21 keys; protected paths clean)"
        status: pass
    human_judgment: false

duration: 28min
completed: 2026-08-26
status: complete
---

# Phase 11 Plan 03: Attachment & Hash-History Preservation Gates (D-06) Summary

**`keep_historical` call-boundary override on `cleanup_untracked_sheet_attachments` plus a widened hash-history stale-key prune guard, both gated on `resolve_run_mode`'s resolved 'incremental'/'full' string — the phase's highest-severity risk closed before any plan produces a scoped `groups` dict.**

## Performance

- **Duration:** ~28 min
- **Started:** 2026-08-26T18:51:26Z (session continuation from 11-02)
- **Completed:** 2026-08-26T19:19:24Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Extended `pipeline.cleanup.cleanup_untracked_sheet_attachments` with a `keep_historical: bool | None = None` call-boundary override on the existing identity-loop `KEEP_HISTORICAL_WEEKS` gate — resolved once before the loop, with `None` (every pre-existing caller) falling back to the module constant unchanged.
- Wired `keep_historical=True if _resolved_mode == 'incremental' else None` at both `pipeline.orchestrate.main` call sites (TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID) — the global env-driven `KEEP_HISTORICAL_WEEKS` constant and its `pipeline/cleanup.py` facade rebind are never flipped, so full-mode cleanup decisions stay byte-for-byte unchanged.
- Widened the hash-history stale-key prune's existing time-budget guard (`if not _time_budget_exceeded:` -> `... and _resolved_mode == 'full':`) so an incremental run preserves every key it did not reach; added a single suppressed-path log line naming the preserved-key count so an operator can distinguish "suppressed because incremental" from "suppressed because time-budget-exceeded" from "nothing was stale."
- Pinned the seven off-contract / legacy-migration gates inside `cleanup_untracked_sheet_attachments` as already-scoped by `groups` — RESEARCH.md Pitfall 2 says re-gating them individually is risk-adding scope creep on billing-critical code; `ScopeDerivationTests` proves the safety argument with a regression test instead, and the region's diff is confirmed empty.
- Documented (comment only, no schema/contract change) that `run_ledger_finish`'s `groups_generated`/`groups_affected`/`rows_seen` counters are scoped to what an incremental run actually covered and are only interpretable next to `run_ledger.mode` (D-11); `run_summary.json`'s frozen 21-key contract is untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end attachment preservation — keep_historical from call site to gate** - `24ae124` (feat)
2. **Task 2: Gate the hash-history stale-key prune on full mode** - `80a54a7` (feat)
3. **Task 3: Pin the already-safe cleanup gates and report scoped counters honestly** - `64c2e93` (test)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

_All three tasks were `tdd="true"`. Tests and implementation were developed and iteratively corrected together against the real runtime behavior of `cleanup_untracked_sheet_attachments` and `pipeline.orchestrate.main` (see Deviations) rather than as a strict pre-implementation RED commit followed by a GREEN commit; each task's final commit nonetheless contains both the passing tests and the implementation for that task, verified atomically before commit._

## Files Created/Modified

- `pipeline/cleanup.py` — `cleanup_untracked_sheet_attachments` gains the `keep_historical` keyword parameter (trailing, after `dry_run`), resolved once (`_effective_keep_historical`) before the per-row loop.
- `pipeline/orchestrate.py` — both cleanup call sites pass the incremental-mode `keep_historical` override; the hash-history prune's guard is widened plus a suppressed-path log line; a documentation-only comment at the `run_ledger_finish` success-path call site records the scoped-counters interpretation rule (D-11).
- `tests/test_incremental_read.py` — `CleanupPreservationTests` (6), `OrchestrateKeepHistoricalWiringTests` (2), `HashHistoryPruneTests` (7), `ScopeDerivationTests` (3) — 18 new test methods, 61 total in the file.
- `tests/test_security_audit_followup.py` — `TestPppCleanupUntrackedAttachments::test_cleanup_function_signature_unchanged` updated to pin the new trailing `keep_historical` kwarg (v7 signature contract), consistent with how every prior addition to this signature was pinned.

## Decisions Made

See `key-decisions` in frontmatter. The most consequential: `keep_historical` was placed AFTER `dry_run` (not immediately after `primary_wr_scope` as PATTERNS.md's illustrative citation suggested), preserving the pre-existing signature-pin test's "dry_run is the trailing kwarg" contract with a smaller, more defensible diff (extend the pin test with one more trailing name, rather than reorder an already-pinned parameter).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated the pre-existing cleanup-signature pinning test for the new trailing kwarg**
- **Found during:** Task 1 (full-suite verification after adding `keep_historical`)
- **Issue:** `tests/test_security_audit_followup.py::TestPppCleanupUntrackedAttachments::test_cleanup_function_signature_unchanged` pins the exact parameter list of `cleanup_untracked_sheet_attachments`, including that `dry_run` is the trailing kwarg (Phase 08 T-08-03). Adding `keep_historical` broke that pin, as intended by the plan (a real signature change).
- **Fix:** Updated the pin to the v7 contract (`... , 'dry_run', 'keep_historical'`), added a `default is None` assertion for the new kwarg, and documented the Phase 11 Plan 03 / D-06 provenance inline, following the exact convention every prior parameter addition used in this same test.
- **Files modified:** `tests/test_security_audit_followup.py`
- **Verification:** `python -m pytest tests/test_security_audit_followup.py -q` passes; full suite green.
- **Committed in:** `24ae124` (Task 1 commit)

**2. [Rule 1 - Bug] Corrected two test-design assumptions against actual code mechanics (not a production bug)**
- **Found during:** Task 1 and Task 3 (first full test run after writing new test classes)
- **Issue:** (a) My first draft of `CleanupPreservationTests` used single-attachment fixtures per identity; `cleanup_untracked_sheet_attachments`'s identity-loop only ever deletes duplicate attachments BEYOND the single newest one per identity (`atts_sorted[1:]`) — a lone attachment can never be deleted through that loop regardless of any gate, so the drafted assertions failed. (b) `ScopeDerivationTests`'s first draft built a `primary`-variant group without the `_USER_` partition token that `_build_primary_wr_scope` additionally requires in the group KEY (not just `__variant`), so the in-scope WR was wrongly excluded from `primary_scope`.
- **Fix:** (a) Rewrote the fixtures to use duplicate-attachment pairs (distinct timestamps, same identity) so deletion vs. preservation is actually observable. (b) Added the `_USER_` token to the primary-variant group's key.
- **Files modified:** `tests/test_incremental_read.py`
- **Verification:** `python -m pytest tests/test_incremental_read.py -q` — 61 passed, 6 subtests; full suite 1592 passed / 1 skipped / 141 subtests.
- **Committed in:** `24ae124`, `64c2e93`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — one a required, plan-anticipated signature-pin update; one test-authoring corrections surfaced by running the tests against real code, not a production behavior change).
**Impact on plan:** No production behavior beyond what the plan specified. Both fixes were required for the plan's own stated verification gates to pass.

## Issues Encountered

None beyond the two auto-fixed items above.

## User Setup Required

None — no external service configuration required. `RUN_MEMORY_INCREMENTAL_ENABLED` remains OFF by default (Plan 02); with the flag off, `resolve_run_mode` always resolves `full`, so every gate added in this plan is inert today (per the plan's own manual reasoning check) and self-verified: `keep_historical` resolves to `None` at both call sites and the hash-history prune's added `_resolved_mode == 'full'` clause is always true.

## Next Phase Readiness

- Both of D-06's destructive-maintenance risks (attachment cleanup, hash-history prune) are closed and pinned with tests BEFORE any plan produces a scoped `groups` dict — Plan 04 (which restructures PHASE 2 against `fetch_sheet_delta`/`resolve_run_mode` and will be the first plan to actually narrow `groups`) arrives to a codebase that is already safe by construction.
- The seven off-contract / legacy-migration gates in `cleanup_untracked_sheet_attachments` remain byte-for-byte unmodified (confirmed by `ScopeDerivationTests::test_pipeline_cleanup_offcontract_gates_diff_is_untouched`), so no new risk surface was added to that billing-critical region.
- `tests/golden/run_summary_baseline.json` (21 keys), `.github/workflows/`, and `pipeline_memory/schema.sql` are all untouched (verified via `git diff --exit-code`).
- No blockers. `bash scripts/run_6_gates.sh` passes ALL 6 gates on the final commit (`64c2e93`).

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-08-26*

## Self-Check: PASSED
