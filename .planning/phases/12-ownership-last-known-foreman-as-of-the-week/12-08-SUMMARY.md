---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 08
subsystem: billing-attribution-backfill
tags: [own-03, own-04, gap-closure, decision-record, roadmap, runbook, living-ledger]

# Dependency graph
requires:
  - phase: 12-ownership-last-known-foreman-as-of-the-week (12-07)
    provides: the source-3 filename-extraction fix that closed the G-12-3 root cause
provides:
  - "D-12-C: the #NO MATCH scope for OWN-03 is option `defer` -- the 945 #NO MATCH rows stay out of live remediation"
  - "D-12-D: ROADMAP success criterion 3's known-good sample is option `substitute-89829163` -- WR 89829163 / backfill_artifacts"
  - "Unambiguous plan 12-10 re-run invocation posture: no --include-blank-roles, sample WR 89829163 WE 082425/083125/091425/092125"
affects: [12-09, 12-10, 12-06]

# Actuals (#2632)
actuals:
  tokens: 3241
  tasks: 3
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Option-id anchoring in planning docs: a decision bullet must contain the literal phrase 'is option `<id>`' so a structural pytest test can read the choice back deterministically, instead of trusting free prose"

key-files:
  created: []
  modified:
    - .planning/ROADMAP.md
    - website/docs/runbook/ownership-attribution.md
    - memory-bank/living-ledger.md
    - tests/test_own04_documentation.py

key-decisions:
  - "D-12-C (2026-09-04): the #NO MATCH scope for OWN-03 is option `defer`"
  - "D-12-D (2026-09-04): ROADMAP success criterion 3's known-good sample is option `substitute-89829163`"
  - "requirements.mark-complete NOT run for OWN-03 / OWN-04 in this plan -- see Requirements note below"

# Metrics
duration: ~25min
completed: 2026-09-04
status: complete
---

# Phase 12 Plan 08: Owner scope decisions for gap G-12-3 (D-12-C, D-12-D) Summary

**Juan resolved both owner-only scope questions gap G-12-3 surfaced -- the #NO MATCH remediation
scope and ROADMAP success criterion 3's unprovable sample -- and this plan recorded both
decisions verbatim, amended the ROADMAP, added a runbook scope section, and appended one Living
Ledger entry, closing the ambiguity that was blocking plan 12-10's re-run scope.**

## Performance

- **Duration:** ~25 min (continuation agent; a prior executor stopped at Task 1's checkpoint and
  returned without writing any files or commits)
- **Completed:** 2026-09-04
- **Tasks:** 3/3 completed (2 decision checkpoints + 1 auto task)
- **Files modified:** 4

## Decisions Recorded (verbatim)

### Task 1 -- the #NO MATCH scope for OWN-03

**Option id:** `defer`

**Juan's verbatim wording (via the orchestrator's decision prompt, 2026-09-03):**

> `defer` -- leave the 945 `#NO MATCH` rows (935 primary + 10 helper) out of OWN-03 entirely;
> zero extra writes; those (WR, week) pairs keep regenerating under a sentinel filename until a
> later phase. Rationale accepted: OWN-03's scope is the `Unknown Foreman` defect, not roles that
> never existed; `--include-blank-roles` widens targeting beyond `#NO MATCH`; `raw-read-rpc`
> would require a new plan and delay the phase.

**12-10 invocation posture:** the re-run must NOT carry `--include-blank-roles`.

### Task 2 -- ROADMAP success criterion 3's known-good sample

**Option id:** `substitute-89829163`

**Juan's verbatim wording (via the orchestrator's decision prompt, 2026-09-03):**

> `substitute-89829163` -- adopt WR 89829163 (live-verified sentinel rows on week endings
> 082425 / 083125 / 091425 / 092125) and rewrite SC3 to name `backfill_artifacts` (source 3, the
> path 12-07 just fixed); source 4 (`backfill_hash_history`) stays unit-test-only coverage.

**SC3 replacement wording applied to ROADMAP.md** (Phase 12 § Success criteria, item 3):

> WR 89829163 WE 082425/083125/091425/092125 regenerate under a real resolved name from the
> `backfill_artifacts` source; no `_User__NO_MATCH` / `_User_Unknown_Foreman` churn remains in
> the scheduled run. (Amended 2026-09-04 per D-12-D; see 12-08-SUMMARY.md.)

Neither decision was auto-selected. Both checkpoints halted for Juan's explicit written answer,
per the plan's `gate="blocking-human"` on both tasks and the must-have "No option is auto-selected."

## Task Commits

1. **Task 1 & Task 2: DECISION checkpoints** -- no file changes; Juan's answers recorded above
   and reflected in the Task 3 commit's edits. No commit (decision-only tasks produce no diff).
2. **Task 3: Record both decisions in the ROADMAP, the runbook and the Living Ledger**
   - `cf13670` (docs) -- amended ROADMAP.md SC3 wording, appended D-12-C / D-12-D bullets to
     Planning decisions; added `## OWN-03 remediation scope` section to the ownership runbook;
     appended one dated Living Ledger entry; extended
     `tests/test_own04_documentation.py` with four new structural tests
     (`test_records_phase_12_gap_closure_decisions`,
     `test_own03_remediation_scope_section_names_both_populations`,
     `test_success_criterion_3_matches_recorded_decision`,
     `test_success_criterion_3_drops_the_unprovable_sample`).

## Files Created/Modified

- `.planning/ROADMAP.md` -- Phase 12 success criterion 3 rewritten to name WR 89829163 /
  `backfill_artifacts` instead of the unprovable WR 19073866 / `backfill_hash_history` sample;
  two new dated bullets `D-12-C` and `D-12-D` appended to Planning decisions. The Phase 12 §
  Plans list was left untouched, as required.
- `website/docs/runbook/ownership-attribution.md` -- new `## OWN-03 remediation scope` section
  inserted before `## Running the backfill`, naming both sentinel populations (`Unknown Foreman`,
  `#NO MATCH`) verbatim, explaining the `no-history` safety of a left-alone `#NO MATCH` row, and
  citing both `D-12-C` and `D-12-D`. No existing paragraph was made stale by the amendment, so
  none was removed.
- `memory-bank/living-ledger.md` -- one new dated entry
  (`## [2026-09-04 10:05] Gap G-12-3 root cause and owner scope decisions D-12-C / D-12-D (12-08)`)
  at the bottom, recording the G-12-3 root cause in one sentence and both decisions by label and
  option id. No claimer names, no secrets.
- `tests/test_own04_documentation.py` -- added `## OWN-03 remediation scope` to
  `_REQUIRED_HEADINGS`; added module constants/helpers (`_ROADMAP`, `_LEDGER`,
  `_phase_12_section`, `_newest_ledger_entry`, `_slice_bullet`, `_option_from_bullet`,
  `_success_criterion_3`, `_own03_remediation_scope_section`); added the four gate tests listed
  above. 25/25 tests pass in this file (up from the pre-plan baseline of 20).

## Verification Evidence

- `python -m pytest tests/test_own04_documentation.py -q` -- 25 passed (baseline before this
  plan's edits: 20 passed; the 5 new/parametrized cases all exercise content this plan's edits
  introduced).
- `python -m pytest tests/ -q` -- 2112 passed, 1 pre-existing skip, 416 subtests, no new failure
  against the pre-plan baseline.
- `npm --prefix website run typecheck` -- clean, no `error TS` line.
- `npm --prefix website run build` -- `[SUCCESS] Generated static files in "build".`, no broken
  link or anchor reported.
- File gate (`git diff HEAD --name-only` against the four declared files) -- `required_files_unmodified=[]`,
  i.e. every declared file was actually modified.
- `git diff --diff-filter=D --name-only HEAD~1 HEAD` -- empty; no unexpected deletions in the
  Task 3 commit.

## Deviations from Plan

None from the plan's own tasks -- both decisions were recorded exactly as Juan stated them, and
Task 3's five sub-steps were implemented as specified, with every new test failing to compile
against the pre-edit file state (each new test's assertions target strings -- `D-12-C`, `D-12-D`,
`## OWN-03 remediation scope`, the amended SC3 wording -- that did not exist before this plan's
edits, so none of the four new tests could have passed beforehand).

One process note, not a plan deviation: this plan's frontmatter lists `requirements: [OWN-03,
OWN-04]`, but this plan only records scope decisions -- it does not perform or complete the
OWN-03 live backfill (still pending 12-09's owner-applied SQL and 12-10's re-run) nor finish
OWN-04's documentation arc end-to-end. `requirements.mark-complete` was deliberately NOT run for
either id in this plan's state-update step, so `REQUIREMENTS.md` continues to show both as
Pending until the plans that actually complete them (12-05 already covers most of OWN-04; 12-10
completes OWN-03) do so. Marking either complete here would misrepresent what shipped.

## Issues Encountered

None.

## User Setup Required

None -- no external service configuration required. Both decisions were supplied in writing by
Juan via the orchestrator before this continuation agent was spawned.

## Next Phase Readiness

- Plan 12-09 (owner-applied SQL: extension guard, Python/SQL list pin, Juan's STEP 4 + STEP 5
  re-apply) can proceed -- it does not depend on either decision recorded here beyond knowing the
  #NO MATCH rows are out of scope (no widened targeting to guard against on the SQL side).
- Plan 12-10's re-run invocation is now unambiguous: scope excludes `--include-blank-roles`, and
  its independent production-risk review / verification dry-run can cite WR 89829163 WE
  082425/083125/091425/092125 as the provable sample instead of the dead WR 19073866.
- No file under `billing_audit/` or `scripts/` was touched by this plan, per its hard
  prohibitions. No RPC, no `generate_weekly_pdfs.py`, no `pipeline/*` change. No backfill script
  was run against live credentials.
- No real claimer name was written into ROADMAP.md, the runbook, the ledger, or this summary.

## Self-Check: PASSED

- `.planning/ROADMAP.md`, `website/docs/runbook/ownership-attribution.md`,
  `memory-bank/living-ledger.md`, `tests/test_own04_documentation.py` all exist on disk with the
  edits described above.
- Commit `cf13670` found via `git log --oneline --all`.
- `python -m pytest tests/test_own04_documentation.py -q` re-run: 25 passed.
- `python -m pytest tests/ -q` re-run: 2112 passed, 1 skipped, 416 subtests.
- `npm --prefix website run typecheck` and `npm --prefix website run build` re-run clean.
- File gate re-run: `required_files_unmodified=[]`.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-04*
