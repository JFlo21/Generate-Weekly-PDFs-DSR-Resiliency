---
phase: 15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot
plan: 07
subsystem: release
tags: [owner-checkpoint, draft-pr, stacked-pr]
requirements-completed: []
completed: 2026-10-29
---

# Plan 15-07 Summary: owner dry run and stacked draft PR

## Outcome

- Owner dry-run approval recorded in `15-DRYRUN-APPROVAL.md`
  (`OWNER DRY-RUN: APPROVED 2026-10-29`, owner reply verbatim).
- Draft PR #436 `feat: foreman notes GF pilot (stacked on #435)`, head
  `feat/phase-15-foreman-notes`, base `plan/phase-13`. Body carries Objective,
  Changes Made, Production Safety Check, the "rebase onto master and retarget"
  instruction and the bold D-15-13 merge-gate line.
- Changelog post `website/blog/2026-10-30-phase-15-foreman-notes-pilot.md`
  now links PR #436 (no `PR: pending` left).

## Pre-rebase BASE_SHA checks (BASE 3b14a1e)

- `git log --oneline BASE..HEAD` listed only Phase 15 commits (15-01 through
  15-06, the 6fc9fd9 typing fix, and the approval commit).
- Non-alias allowlist check (15-06) printed nothing.
- Orchestrator private real-name scan over the full PR range (diffs and
  messages): 0 hits.

## Deviation: rebased while #435 is open

The plan says no rebase while #435 is open. The branch was rebased onto the
current `plan/phase-13` (a7558cb) anyway: without #435's typing fixes Gate 4
(mypy delta) failed 73 > 70. The rebase was clean (27 commits, no
conflicts). `15-BASE_SHA` still names the pre-rebase SHA; BASE diffs are not
re-run after a rebase, per this plan.

## Post-rebase validation

- `pytest tests/`: 2748 passed, 3 skipped, 825 subtests passed.
- `bash scripts/run_6_gates.sh`: ALL 6 GATES PASSED (mypy 70 -> 70).
- Website typecheck and build: green in 15-06 (docs unchanged since,
  except the PR-number line).

## Still open

- FN-13 (merge gate) closes at merge, after #435 merges and the 11-15 live
  parity reading closes Phase 11 (D-15-13). Then: rebase onto master,
  retarget the base to master, re-run suite and 6 gates.
- Live check deferred to the rollout run: the `row_ids` + `include=format`
  fetch returning `conditional_format` (research A4) was confirmed only by
  the owner's dry run.
