---
phase: 11-incremental-read-affected-group-regeneration
plan: 07
subsystem: pipeline_memory
tags: [supabase, run_ledger, parity, incremental-read, decision-gate, tdd]

# Dependency graph
requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "Plan 05's parity_verdict/parity_details vocabulary written into run_ledger.notes (pass/fail/skipped) and its execution_type tagging; plan 02/04/06's reader.py fail-open conventions"
provides:
  - "pipeline_memory.reader.get_parity_streak(limit) -- derives the D-09 consecutive-pass streak from run_ledger on demand, with pass-counts/fail-resets/skipped-excluded semantics, auditable contributing-run-ids + stopping-row detail, None on failure"
  - "The recorded INC-05 retirement decision: DEFERRED (option id `defer`), with the run_ledger streak reading pasted alongside it and a re-authorisation path for plan 11-08"
affects: ["11-08 (INC-05 retirement plan) -- reads this SUMMARY's recorded option id before touching any file; per this decision, 11-08 does NOT execute against this phase"]

# Actuals (#2632)
actuals:
  tokens: 9500
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Derived-on-demand evidence: get_parity_streak has no counter column and caches nothing -- every call re-scans run_ledger, so a streak claim can never drift from the underlying rows (D-09)."
    - "Auditable boolean-adjacent return: the function returns a dict (streak count, rows examined, contributing run ids, stopping run id/verdict) rather than a bare integer, so a claim of 'five' is falsifiable by a human reading the SUMMARY, not just trusted."

key-files:
  created: []
  modified:
    - pipeline_memory/reader.py
    - tests/test_incremental_read.py

key-decisions:
  - "Task 2's blocking-human decision was resolved by the owner (Juan) on 2026-08-26: option id `defer` selected. The INC-05 retirement (local JSON caches, attachment pre-fetch phases, workflow cache steps) is NOT executed this phase. Plan 11-08 does not run against this branch."
  - "Rationale for `defer` (recorded verbatim): D-12's authorisation condition -- five consecutive `pass` verdicts on scheduled production_frequent runs -- is structurally unsatisfiable today. It requires the RUN_MEMORY_WRITE_ENABLED flip PR to merge, the plan-05 shadow-parity hook to reach production, and at least five scheduled runs to record verdicts. None of that has happened: the flip PR is absent from .github/workflows/weekly-excel-generation.yml on both origin/master and this branch. Executing either retire option now would also bundle the removals with the incremental-read work, which this plan's own prohibition forbids (\"its own PR, cut strictly after the streak, never bundled\")."
  - "Task 1's `<precondition>` (a real run_ledger row with a parity_verdict written by a real run after plan 05 merged) was NOT met. Per the owner's prior ruling on this same class of fact for plans 11-05 and 11-06 (2026-08-26), Juan approved proceeding with the code + unit-test work on that basis. Task 1 used a mocked Supabase response only -- no live Supabase or Smartsheet calls were made."

requirements-completed: [INC-04]

coverage:
  - id: D1
    description: "get_parity_streak scans newest-first over run_ledger rows whose notes.execution_type is production_frequent: pass increments, fail resets to zero and stops the scan, skipped is excluded from the sequence (neither counts nor resets), and rows outside production_frequent are ignored."
    requirement: "INC-04"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::ParityStreakTests (11 tests, mocked Supabase response)"
        status: pass
    human_judgment: false
  - id: D2
    description: "No dedicated streak counter column is added to pipeline_memory/schema.sql -- the streak is derived on demand so it cannot drift from the evidence."
    requirement: "INC-04"
    verification:
      - kind: unit
        ref: "git diff --exit-code -- pipeline_memory/schema.sql"
        status: pass
    human_judgment: false
  - id: D3
    description: "A Supabase failure returns None, read by the caller as 'cannot confirm', never as a satisfied streak."
    requirement: "INC-04"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::ParityStreakTests (Supabase-failure case)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The INC-05 retirement decision is taken at this plan's blocking-human checkpoint with the streak reading pasted alongside it, and the selected option id is recorded for plan 11-08 to read back."
    verification: []
    human_judgment: true
    rationale: "This is an owner-only architectural/production-risk decision (D-12: costly-to-revert workflow-plus-code change) -- no automated check can substitute for Juan's explicit selection. Decision recorded below: option id `defer`."

duration: ~15min (continuation agent: recording an already-made owner decision, writing SUMMARY, updating STATE/ROADMAP -- no code changes)
completed: 2026-08-26
status: complete
---

# Phase 11 Plan 07: Parity Streak Evidence + INC-05 Retirement Decision Summary

**`get_parity_streak` derives a D-09 consecutive-pass streak from `run_ledger` on demand (no counter column, fully auditable), and the INC-05 retirement it authorizes was DEFERRED by the owner because the underlying evidence cannot exist yet -- the `RUN_MEMORY_WRITE_ENABLED` flip PR has not merged.**

## Performance

- **Duration:** ~15 min (continuation agent only; Task 1's implementation work was completed and committed by a prior executor)
- **Tasks:** 2
- **Files modified:** 2 (`pipeline_memory/reader.py`, `tests/test_incremental_read.py`)
- **Commits:** 2 (Task 1) + this plan-metadata commit

## Checkpoint / Decisions

### Task 1 precondition note

Task 1 declared a `<precondition>`: "`pipeline_memory.run_ledger` holds at least
one row whose `notes` carries a `parity_verdict`, written by a real run after
plan 05 merged." This was **not met**. The owner (Juan) had already ruled on
this exact class of fact for plans 11-05 and 11-06 earlier the same day
(2026-08-26) and approved proceeding with the code + unit-test work on that
basis. Task 1 used a mocked Supabase response only — no live Supabase or
Smartsheet calls were made, and `pipeline_memory/schema.sql` and
`.github/workflows/` remain byte-for-byte unchanged (`git diff --exit-code`
clean).

Task 1 verification (run by the prior executor, all green):
`ParityStreakTests` 11 passed; `tests/test_incremental_read.py` 100 passed;
full suite 1705 passed / 1 skipped / 141 subtests; `bash scripts/run_6_gates.sh`
ALL 6 GATES PASSED (mypy delta 65 → 65, no regression); `git diff --exit-code
-- pipeline_memory/schema.sql .github/workflows/` clean; `python -m py_compile
generate_weekly_pdfs.py` clean.

### Task 2 — USER DECISION (2026-08-26)

**Selected option id: `defer`** ("Defer the retirement to a later phase").

Per the plan's resume-signal: **plan 11-08 does NOT execute this phase.**
INC-05 stays open. The rollback path (three local JSON caches, two attachment
pre-fetch phases, six `.github/workflows/weekly-excel-generation.yml` cache
step pairs) remains fully intact.

**Streak reading pasted with the decision** (a read-only scan against live
`pipeline_memory.run_ledger` in Supabase project `poeyztlmsawfoqlanucc`,
newest-first, run 2026-08-26):

| run_id | status | execution_type | parity_verdict |
|---|---|---|---|
| local-20260825T215007120675Z | success | manual | (absent) |
| local-20260825T204825044699Z | running (stale) | (absent) | (absent) |
| diag-test-mode-fix | success | (absent) | (absent) |

**Streak = 0 of 5** · rows examined 3 · qualifying `production_frequent` rows
0 · contributing run ids none · stopping row none (window exhausted). This is
an **empty** streak, not a **failed** one: no scheduled run has ever written a
`parity_verdict` because nothing from Phase 11 has merged to production — the
`RUN_MEMORY_WRITE_ENABLED` flip PR is absent from
`.github/workflows/weekly-excel-generation.yml` on both `origin/master` and
this branch.

**Owner's stated rationale (verbatim):** D-12's authorisation condition (five
consecutive `pass` verdicts on scheduled `production_frequent` runs) is
structurally unsatisfiable today — it requires flip PR merge → the plan-05
shadow reaching production → at least five scheduled runs. Executing either
retire option on this branch would also bundle the removals with the
incremental-read work, which this plan's own prohibition forbids ("its own
PR, cut strictly after the streak, never bundled").

### Re-authorisation path

To run 11-08 later, the owner must:
1. Merge the `RUN_MEMORY_WRITE_ENABLED` flip PR (`docs/run-memory-write-flip-checklist.md`).
2. Let ≥5 counted runs (`production_frequent`, `weekend_maintenance`, or streak-eligible `manual` -- D-09 as amended 2026-08-29, PR #372) record `parity_verdict = pass` on `success` rows in `run_ledger`, with no intervening `fail`.
3. Confirm the `group_state` attachment-id proof (carried forward from Phase 10 UAT) and record the current frequent-run wall clock vs. the 94-minute baseline from run `32743959053`.
4. Re-open this Task 2 decision — update this SUMMARY's recorded option id to `retire-now` or `retire-code-keep-cache-steps`, with the real `get_parity_streak()` output pasted in place of the empty reading above.
5. Execute 11-08 as its own PR/branch, never bundled with any other change.

## Accomplishments

- Shipped `pipeline_memory.reader.get_parity_streak(limit)` (D-09): scans a
  bounded recent window of `run_ledger` newest-first, restricted to
  `notes.execution_type == "production_frequent"`; `pass` increments,
  `fail` resets to zero and stops the scan, `skipped` and an absent verdict
  are excluded (neither count nor reset). Returns a dict with the streak
  count, rows examined, contributing run ids, and the stopping run id/verdict
  — never a bare integer. Returns `None` on any Supabase failure, documented
  as "cannot confirm," never a satisfied streak. No schema column added; the
  streak is derived on demand every call.
- Added `ParityStreakTests` to `tests/test_incremental_read.py` — 11 tests
  covering all seven declared behaviors, including the load-bearing cases
  (a `skipped` row sandwiched between two `pass` rows yields a streak of two,
  not one and not a reset; a `fail` row yields a streak of zero; a Supabase
  failure returns `None`).
- Took the Task 2 blocking-human decision: **deferred** the INC-05 retirement.
  Plan 11-08 will not execute against this phase; the streak reading and
  rationale are recorded above for its opening gate to read back later.

## Task Commits

1. **Task 1 (RED): failing test for parity streak scan** — `f2fe486` (test)
2. **Task 1 (GREEN): implement get_parity_streak (D-09)** — `0575826` (feat)
3. **Task 2:** decision only, no code — recorded in this SUMMARY.

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

## Files Created/Modified

- `pipeline_memory/reader.py` — `get_parity_streak(limit)`.
- `tests/test_incremental_read.py` — `ParityStreakTests` (11 tests).

## Decisions Made

See "Checkpoint / Decisions" above. Most consequential: the INC-05 retirement
is **deferred**, not approved, because the streak evidence that would
authorise it cannot exist until the `RUN_MEMORY_WRITE_ENABLED` flip PR merges
and real scheduled runs accumulate. Phase 11 will not close ROADMAP success
criterion 4 (the wall-clock reduction from removing the rollback path) this
milestone.

## Deviations from Plan

None — plan executed exactly as written. Task 1 landed with the plan's
literal RED/GREEN commit shape; Task 2's checkpoint was resolved by the
owner exactly per its `<resume-signal>` contract (option id + pasted streak
reading).

## Issues Encountered

None. The empty streak reading pasted with the Task 2 decision is expected
given the flip PR's unmerged state — documented explicitly above rather than
treated as an anomaly.

## User Setup Required

None from this plan's own code (no files changed by Task 2; Task 1 changed
only `pipeline_memory/reader.py` and its test file). The `RUN_MEMORY_WRITE_ENABLED`
flip PR remains a separate, owner-gated action per D-10 — see the
re-authorisation path above and `docs/run-memory-write-flip-checklist.md`.

## Next Phase Readiness

- `get_parity_streak` is production-shaped (bounded window, fail-open to
  `None`, auditable detail) and ready to be called for real once the flip PR
  merges and scheduled runs begin recording `parity_verdict`.
- Plan 11-08 (INC-05 retirement) is **deferred**, not skipped: it remains
  open in the roadmap and must be re-planned or re-authorized once the
  re-authorisation path above is satisfied.
- No blockers introduced by this plan. `pipeline_memory/schema.sql` and
  `.github/workflows/` remain untouched (verified via `git diff --exit-code`).
- Phase 11's other six plans (01–06) are unaffected by this plan's read-only
  addition.

## Threat Flags

None new. This plan's two STRIDE threat-register entries were dispositioned
within scope:
- T-11-36 (a falsely satisfied parity streak authorising an irreversible-
  feeling production change) — mitigated: the streak is derived on demand
  with no cached counter, returns contributing run ids for audit, returns
  `None` rather than a number when it cannot confirm, and the decision
  checkpoint required the reading to be pasted alongside the decision (done
  above).
- T-11-37 (rollback path removed while a latent defect remains) — moot this
  plan: the owner selected `defer`, so no rollback path was removed.
- T-11-42 (a counter column or cached streak value drifting from the
  evidence) — mitigated: no schema column added, confirmed by
  `git diff --exit-code -- pipeline_memory/schema.sql`.

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-08-26*

## Self-Check: PASSED

`pipeline_memory/reader.py` and `tests/test_incremental_read.py` confirmed
present on disk with `get_parity_streak` / `ParityStreakTests` defined; both
commits (`f2fe486`, `0575826`) confirmed present in `git log --oneline --all`.
No code changes were made by this continuation agent — this SUMMARY records
Task 1's prior verification evidence and Task 2's owner decision.
