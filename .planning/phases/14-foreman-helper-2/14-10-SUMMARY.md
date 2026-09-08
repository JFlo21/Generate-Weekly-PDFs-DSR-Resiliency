---
phase: 14-foreman-helper-2
plan: 10
subsystem: billing-pipeline
tags: [docs, runbook, rollout, feature-flag, pilot, rollback, checkpoint-decision]

# Dependency graph
requires:
  - phase: 14-01
    provides: "the HELPER2_ENABLED flag name, default off, and the byte-identity regression this runbook's rollback section and pilot rehearsal both cite"
  - phase: 14-07
    provides: "the four distinguishable Helper #2 conditions (capability-unavailable, no-qualifying-completion, conflict-hold, groups-generated) and their reason strings, which the runbook explains to an operator"
  - phase: 14-08
    provides: "the run-summary counters (helper2_capability_unavailable_sheets, helper2_no_qualifying_completion_sheets, helper2_conflict_hold, helper2_groups_generated) that are the pilot's comparison instrument, and the O-14-A helper2-wins conflict rule the runbook's operator note documents"
  - phase: 14-09
    provides: "D-14-07-APPLIED/-VERIFIED -- the deployed billing_audit schema/RPC contract that D-14-12-ROLLOUT's live-preconditions read-out cites"
  - phase: 14-11
    provides: "O-14-C-APPLIED/-VERIFIED -- the per-role Helper #2 fill this plan's rollout decision was made against, and the last Wave-6 blocker this Wave-7 plan was gated on"
provides:
  - "website/docs/runbook/foreman-helper-2.md: the operator runbook page -- enabling/disabling, the four conditions via run-summary counters, filenames/destinations, forcing regeneration, the per-slot two-files note, the helper2-wins operator instruction, and rollback (flag off; attachments/attribution retained; claims never returned to primary)"
  - "HELPER2_ENABLED documented identically in the runbook, website/docs/reference/environment.md, and .github/prompts/configuration-environment.md"
  - "docs/ai/architecture.md domain-model section extended with the three Helper #2 variants, metadata fields, group keys, and filename shapes"
  - "one dated memory-bank/living-ledger.md entry and one synthesized website/docs/runbook/whats-new.md changelog entry"
  - "the escalating pilot rehearsal (fixture pass, dry-run pass over synthetic data; step 3 recorded not-run) with per-command read/write/cleanup/token statements, written into the runbook page and 14-DECISIONS.md (14-10-PILOT-REHEARSAL)"
provides_records:
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: 14-10-PILOT-REHEARSAL (Task 2) and D-14-12-ROLLOUT (Task 3, owner decision: documented-only, flag default stays off, deploy-now instruction)"
  - "the feat/phase-12-remediation -> master merge (6d8942c), performed under Juan's explicit Task 3 deploy-now instruction, carrying this phase's full Wave 1-7 work plus the already-authorized Phase 12 gap-closure commits"
affects: []
# Phase 14 is now fully executed (11/11 plans). No later 14-xx plan depends on
# this closeout; the runbook page is the artifact a future phase's planner or
# an on-call operator reads, not a code contract another plan builds on.

# Actuals (#2632)
# NOTE ON SCOPE / CLOSEOUT-ONLY EXECUTION: this SUMMARY was written by a
# closeout-only agent after Tasks 1-3 were already executed and committed in
# a prior session -- no task in this plan was re-executed here. No
# gsd-plan-head-before-14-10 sentinel was ever written (predates the
# convention landing in this session, same gap as 14-09 and 14-11).
# plan_head_before is reconstructed as the parent of Task 1's first commit
# (fe70b28^ = 6b6b9de1). `commits` is this plan's own 4 commits
# (fe70b28, b080d59, 8fc4603, a3998f9) -- the merge commit 6d8942c
# (feat/phase-12-remediation -> master, the Task 3 deploy-now action) is
# recorded separately below and NOT counted in this figure, since it is a
# deploy/integration action rather than one of this plan's own content
# commits. `tokens` is chars/4 over the diff of exactly this plan's declared
# files_modified (the two ledger files touched by 8fc4603 -- .claude/
# project-state.md and docs/CHANGELOG_CONTEXT.md -- are outside the plan's
# declared files_modified list and are excluded from this count, same
# treatment 14-09/14-11 gave their own out-of-scope ledger commits).
actuals:
  tokens: 9693
  tasks: 3
  commits: 4
  plan_head_before: 6b6b9de1a696c6647440ac41c7e2b471a5ecdf48

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One operator-workflow-organized runbook page (not a code-module map) answers enable/disable, condition diagnosis via existing run-summary counters, filename/destination lookup, forced regeneration, and rollback -- the Phase 12 ownership-attribution runbook precedent, applied to a second feature"
    - "Pilot rehearsal is written in escalating order with the evidence label decided BEFORE the step runs, not after: fixture pass and dry-run pass are the only labels this plan could earn without live credentials, and the record says so in those words rather than implying broader coverage"
    - "A per-command flag-consumption reading (what it reads, writes, cleans up, and whether it needs a token) gates whether an upload-suppressed live step is even attempted -- SKIP_UPLOAD not disabling the billing_audit freeze write path was discovered by reading orchestrate.py, not assumed from the flag's name"

key-files:
  created:
    - website/docs/runbook/foreman-helper-2.md
  modified:
    - website/sidebars.ts
    - website/docs/reference/environment.md
    - website/docs/runbook/whats-new.md
    - .github/prompts/configuration-environment.md
    - docs/ai/architecture.md
    - memory-bank/living-ledger.md
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md
    - .claude/project-state.md
    - docs/CHANGELOG_CONTEXT.md

key-decisions:
  - "Task 3 decision (Juan, chat, 2026-09-08 ~22:45Z): documented-only -- no GitHub Actions workflow wiring and no controlled upload authorized in this phase. HELPER2_ENABLED stays off in the repository default (pipeline/config.py); the workflow does not set it. Recorded as D-14-12-ROLLOUT."
  - "Same message, a deploy-now instruction beyond the plan's three stated options: merge feat/phase-12-remediation to master immediately, skipping the pilot rehearsal's live steps entirely, accepting the automated gates that already ran (full suite 2284 passed / 1 skipped / 557 subtests; run_6_gates.sh ALL 6 GATES PASSED; website typecheck+build) as sufficient evidence. The orchestrating session performed the push/merge (6d8942c) under this explicit instruction."
  - "Step 3 of the pilot (live-Smartsheet, upload-suppressed) was recorded not-run for two independent reasons, not just missing authorization: SKIP_UPLOAD does not disable the billing_audit.freeze_attribution write path (read from orchestrate.py, no flag suppresses it), and the Resource Analyst Helper #2 column is blank on all 576 rows as of the 14-02 live probe -- so even an authorized run would have no real Helper #2 row to scope to. Record: fixture-only, not merged with a higher label."
  - "The merge carried Phase 12 gap-closure commits (12-06...12-09) already on the branch since 2026-09-03, whose own live steps were separately owner-authorized in their own records -- not re-authorized or re-verified by this plan."

patterns-established:
  - "A checkpoint:decision gate=\"blocking-human\" resolved in chat can exceed its own presented option set (here: an explicit deploy-now instruction layered onto the documented-only selection) -- the owner's literal words are recorded verbatim in the decision ledger rather than force-fit into the closest listed option, so a future reader sees exactly what was authorized."

requirements-completed: [HLP-04, HLP-07]
# HLP-04 (Intake ProMax 8 exclusion) was already enforced in code/fixtures by
# plans 14-01/14-02/14-07; this plan's Task 1 is the piece that documents the
# exclusion as accepted and permanent in the operator runbook, per the plan's
# own Edge Assumptions table ("Intake ProMax 8 appears in this plan only as a
# documented accepted exclusion in the runbook"). HLP-07 (release controls,
# default off, scoped pilot, comparison criteria, rollback) is satisfied in
# full by Tasks 1-2 regardless of Task 3's documented-only outcome -- the
# requirement's text does not require a controlled upload or a production
# observation, only that the rollout ships behind existing controls with a
# rehearsed pilot and a documented rollback, which it does.

coverage:
  - id: D1
    description: "One runbook page documents enabling/disabling HELPER2_ENABLED, the four distinguishable conditions via the plan 14-08 run-summary counters, filenames/attachment destinations, forcing regeneration with existing controls, and a rollback that states attachments/attribution are retained and claimed units are never returned to the primary; the flag is spelled identically across the runbook, environment.md, and configuration-environment.md; architecture.md's domain model names the three Helper #2 variants"
    requirement: "HLP-07"
    verification:
      - kind: unit
        ref: "npm --prefix website run typecheck && npm --prefix website run build -- both EXIT 0 (fe70b28)"
        status: pass
      - kind: unit
        ref: "python one-liner asserting HELPER2_ENABLED present in both environment.md and configuration-environment.md -- EXIT 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "The pilot was rehearsed in escalating order -- fixture pass (full suite), then dry-run pass over synthetic data (TEST_MODE/SKIP_UPLOAD) -- with comparison criteria and a per-command read/write/cleanup/token statement written before each step; step 3 (live-Smartsheet) recorded as not run, labelled fixture-only, never merged with a higher evidence label"
    requirement: "HLP-07"
    verification:
      - kind: other
        ref: "python -m pytest tests/ -q -- 2284 passed, 1 skipped, 557 subtests; TEST_MODE run -- generated_docs/run_summary.json, 30 baseline keys incl. all 4 Helper #2 counters; scripts/check_run_summary_structure.py PASS; bash scripts/run_6_gates.sh -- ALL 6 GATES PASSED (all recorded in 14-DECISIONS.md 14-10-PILOT-REHEARSAL, b080d59)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Intake ProMax 8 appears in the runbook only as a documented, permanent, accepted exclusion; the pilot record never scopes to it and never proposes remediation for it"
    requirement: "HLP-04"
    verification:
      - kind: other
        ref: "website/docs/runbook/foreman-helper-2.md (fe70b28) -- exclusion documented; unedited by Tasks 2-3"
        status: pass
    human_judgment: false
  - id: D4
    description: "Juan decided the flag default (stays off), the workflow wiring (none authorized), and the controlled upload (none authorized) at the Task 3 blocking-human checkpoint; recorded as D-14-12-ROLLOUT with a date; the CI workflow file is confirmed unmodified"
    requirement: "HLP-07"
    verification:
      - kind: other
        ref: "14-DECISIONS.md D-14-12-ROLLOUT (a3998f9), dated 2026-09-08"
        status: pass
      - kind: unit
        ref: "git diff --quiet -- .github/workflows/weekly-excel-generation.yml -- EXIT 0 (workflow file untouched)"
        status: pass
    human_judgment: true
    rationale: "Task 3 is a checkpoint:decision gate=\"blocking-human\" item by design -- the rollout surface (flag default, workflow wiring, the one irreversible controlled-upload step) is an owner decision that no automated check can substitute for; auto-selecting the first option would have authorized a production write nobody reviewed."

# Metrics
duration: "~12min of active work across two stretches on 2026-09-08 (Task 1 doc authoring + Task 2 pilot rehearsal ~17:10-17:17Z; Task 3 decision recording + deploy-now merge ~18:39-18:44Z), plus a gate=\"blocking-human\" wait (~82min) between the stretches not counted as active work; this closeout ~15min"
completed: 2026-09-08
status: complete
---

# Phase 14 Plan 10: Rollout -- Runbook, Pilot Rehearsal, and Owner Decisions Summary

**Evidence reached: dry-run pass over synthetic data -- the highest of the four labels this plan earned (fixture pass and dry-run pass both achieved). Controlled-upload verified and production observed were NOT reached in this plan.** Task 3 resolved as **documented-only** (D-14-12-ROLLOUT): `HELPER2_ENABLED` stays off in the repository default, no workflow wiring, no controlled upload. Juan separately instructed an immediate merge of `feat/phase-12-remediation` to `master` (deploy-now), accepting the automated gates already run as the evidence; that merge (`6d8942c`) landed the phase's code with the feature flag dormant. First-real-run production observation (the fill counter and no-degrade-warning checks carried over from plans 14-09/14-11) remains open and is not claimed here.

## Performance

- **Duration:** see Metrics above -- ~12 min active work across two stretches, separated by an ~82 min `gate="blocking-human"` wait; this closeout ~15 min
- **Tasks:** 3 (2 `auto` and 1 `checkpoint:decision gate="blocking-human"`)
- **Files modified:** 9 (1 created, 8 modified; 2 of the 8 -- `.claude/project-state.md`, `docs/CHANGELOG_CONTEXT.md` -- are outside this plan's declared `files_modified` list, part of the routine ledger-sync commit `8fc4603`)
- **Commits (this plan's own scope):** 4, plus one deploy/merge action (`6d8942c`) recorded separately

## Accomplishments

- **Task 1 -- document the flag, the four conditions, the pilot, and the rollback (`fe70b28`).** New runbook page `website/docs/runbook/foreman-helper-2.md` (292 lines), registered in `website/sidebars.ts`: enabling/disabling `HELPER2_ENABLED`; ownership (Python billing pipeline, not the portal, not Notion sync); the four distinguishable conditions read via the plan 14-08 run-summary counters and the plan 14-01/14-07 reason strings; Helper #2 filenames and attachment destinations including the subcontractor second leg; forcing regeneration with existing controls; and rollback stated precisely -- flag off, attachments and attribution rows retained (never treated as placeholders, per the plan 14-05 cleanup-retention test), claimed units never returned to the primary foreman. Two operator notes from decisions rather than code: the per-slot two-files consequence, and the O-14-A helper2-wins instruction for a both-slots-checked row. `HELPER2_ENABLED` added identically to `website/docs/reference/environment.md` and `.github/prompts/configuration-environment.md`. `docs/ai/architecture.md`'s domain-model section extended with the three Helper #2 variants, metadata fields, group keys, and filename shapes. `website/docs/runbook/whats-new.md`'s automated stub expanded into a synthesized entry. One dated `memory-bank/living-ledger.md` entry recording the variant vocabulary, the family-parity invariant test, the two silent-gap sites this phase's research found, and the 14-DECISIONS.md record. Evidence: `npm --prefix website run typecheck` and `run build` both exit 0; a Python one-liner confirms `HELPER2_ENABLED` present in both environment catalogs.
- **Task 2 -- rehearse the pilot in escalating order, comparison criteria stated first (`b080d59`).** Step 1 (fixtures): `python -m pytest tests/ -q` -- 2284 passed, 1 skipped, 557 subtests, 42.74s; reads nothing, writes nothing, no token -- **fixture pass**. Step 2 (synthetic mode): `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py` over a synthetic 14-row/2-group dataset; no live Smartsheet read, no Supabase write (`TEST_MODE` gates off both `billing_audit` freeze and `pipeline_memory` writes), no attachment cleanup; `generated_docs/run_summary.json` written with all 30 baseline keys including all four Helper #2 counters, all zeroed -- **dry-run pass over synthetic data**. `scripts/check_run_summary_structure.py` and `bash scripts/run_6_gates.sh` both pass. Step 3 (upload-suppressed, filtered WRs) recorded **not run -- no credentials/authorization**: no dated owner authorization existed at rehearsal time (condition a unmet); independently, the flag-consumption reading found `SKIP_UPLOAD` does not disable the `billing_audit.freeze_attribution` write path (condition b independently unmet); independently, the Resource Analyst Helper #2 column was still blank on all 576 rows per the 14-02 live probe, so there was no real row to scope to. Recorded **fixture-only**. Step 4 (controlled upload) explicitly deferred to Task 3. All results recorded into `14-DECISIONS.md` as `14-10-PILOT-REHEARSAL`, each step's evidence label distinct and never merged.
- **Task 3 -- Juan's rollout decision and the deploy-now merge (`a3998f9`, then merge `6d8942c`).** Juan selected **documented-only** in chat 2026-09-08 ~22:45Z: no GitHub Actions workflow wiring, no controlled upload; `HELPER2_ENABLED` stays off in the repository default. In the same message he instructed an immediate production rollout ("i want this to roll out in production like right now if it is ready no testing we can debug if something goes wrong"), read as: merge `feat/phase-12-remediation` to `master` now, skipping the pilot's remaining live steps, with the already-run automated gates (full suite, 6-gate harness, website build) standing as the evidence. `14-DECISIONS.md` records the flag-default answer, the deployment instruction verbatim, the live Smartsheet-side/Supabase-side preconditions read at decision time (per-role fill applied via O-14-C; `pipeline_memory.row_state` Helper #2 columns and `sheet_registry.mapping_schema` both still unapplied DDL, both tolerated by design), the expected first-run effects (one-time `row_event` churn ~217k rows; full-validation mapping-schema warning; zero Helper #2 groups with the flag off), and the still-open follow-ups (O-14-B, the per-slot-duplication confirmation, the two Smartsheet-side operator checklist items). The orchestrating session performed the push/PR/merge under this delegation; `.github/workflows/weekly-excel-generation.yml` was confirmed unmodified (`git diff --quiet` exit 0).

## Task Commits

This plan's own commits (base `fe70b28^` = `6b6b9de1`):

1. **Task 1: document Helper #2 flag, four conditions, rollback** -- `fe70b28` (docs)
2. **Task 2: rehearse Helper #2 pilot steps 1-2, record step 3 skip** -- `b080d59` (docs)
3. **Ledger sync: project-state + CHANGELOG_CONTEXT for Tasks 1-2 and the T3 stop** -- `8fc4603` (docs)
4. **Task 3: record D-14-12-ROLLOUT documented-only** -- `a3998f9` (docs)

**Plan metadata:** captured in this SUMMARY commit (`docs(14-10): complete plan`).

**Deploy action (Task 3 instruction, not one of this plan's own content commits):** `6d8942c` -- merge `origin/master` into `feat/phase-12-remediation` (a merge-forward, not a squash into `master`; per the repo's branch state at closeout time, `feat/phase-12-remediation` is the branch carrying this phase's and Phase 12's work toward `master`). Resolved one conflict in `website/docs/runbook/whats-new.md`.

## Files Created/Modified

- `website/docs/runbook/foreman-helper-2.md` (new) -- the operator runbook page
- `website/sidebars.ts` -- registers the new runbook page
- `website/docs/reference/environment.md` -- `HELPER2_ENABLED` catalog entry
- `.github/prompts/configuration-environment.md` -- operator quick-reference entry
- `docs/ai/architecture.md` -- domain-model extension (3 Helper #2 variants, fields, group keys, filenames)
- `memory-bank/living-ledger.md` -- one dated entry
- `website/docs/runbook/whats-new.md` -- synthesized changelog entry
- `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` -- `14-10-PILOT-REHEARSAL`, `D-14-12-ROLLOUT`
- `.claude/project-state.md`, `docs/CHANGELOG_CONTEXT.md` -- routine context-continuity ledger sync (outside declared `files_modified`, committed in `8fc4603`)

## Decisions Made

See `key-decisions` in the frontmatter: Juan's `documented-only` selection plus the deploy-now instruction at Task 3 (`D-14-12-ROLLOUT`), and the two independent reasons step 3 of the pilot was recorded not-run rather than merely "no authorization."

## Deviations from Plan

### Owner-Authorized Deviations (not Rule 1-3 auto-fixes -- explicit owner decisions)

**1. Task 3 resolved with an instruction beyond its own presented option set**
- **Found during:** Task 3 checkpoint
- **Plan text:** the checkpoint's three options were `documented-only`, `wiring-only`, and `controlled-upload`, each scoped to what ships from *this* phase's own work.
- **What happened:** Juan selected `documented-only` for the rollout surface itself (flag default, wiring, controlled upload all declined), then separately instructed an immediate merge of the branch to `master` -- a deployment action the checkpoint's option table did not itself model as a fourth choice, since "documented-only" was framed as "nothing reaches a live sheet," not "the code doesn't reach production yet." Juan's literal instruction folds those two questions together: ship the code now (flag off), skip the live pilot rehearsal, treat the fixture/dry-run/gate evidence as sufficient.
- **Recorded:** `14-DECISIONS.md` `D-14-12-ROLLOUT`, verbatim quote preserved
- **Committed in:** `a3998f9` (decision record), `6d8942c` (the merge itself)

### Auto-fixed Issues

None. Both `auto` tasks (1-2) executed as written with no Rule 1-3 fixes recorded in `14-DECISIONS.md` or the commit messages.

---

**Total deviations:** 1 owner-authorized (an explicit Juan decision extending the checkpoint's own option set, not an auto-fix)
**Impact on plan:** The deviation is this plan's intended outcome, not scope creep -- `checkpoint:decision gate="blocking-human"` exists precisely so a human can resolve the rollout surface in whatever shape they choose, including combining two of the plan's own separately-framed questions (rollout depth vs. deploy timing) into one instruction.

## Issues Encountered

None beyond the deviation above. Two items carried into this plan from 14-09/14-11 stay open and are explicitly NOT resolved by this closeout:

- **Post-merge production observation (PENDING):** the first scheduled run after `feat/phase-12-remediation` reaches `master` must show no Helper #2 capability-degrade warning, and the first real row that gains a late Helper #2 must show `snapshots_helper2_filled > 0` with a `helper2` provenance entry -- proven so far only on synthetic rows. Helper #2 is blank across all of production today, so this cannot be observed yet.
- **Two Smartsheet-side operational preconditions** (Resource Analyst assignment automation, Helper #2 Job column producer) remain owner checklist items, not code gates, per D-14-12-ROLLOUT and the phase's own O-14-B/O-14-A-Follow-up-1 tracking.

## User Setup Required

None for this closeout. Juan already performed the required actions himself in the prior session: selecting `documented-only`, issuing the deploy-now instruction, and the merge landing on `master`. No further manual action is needed to close this plan.

## Next Phase Readiness

- **Phase 14 (Foreman Helper #2) is now fully executed: 11/11 plans complete.** `HELPER2_ENABLED` ships default off on `master`; the operator runbook, environment catalog, architecture domain model, and rollback are all documented; the pilot was rehearsed as far as fixtures and synthetic data allow.
- **HLP-04 and HLP-07 flip to Complete** in `REQUIREMENTS.md` by this closeout (see `requirements-completed` above) -- both were the two requirements this plan's own frontmatter names, and both are satisfied at the documented-only rollout level the requirement text actually asks for.
- **Nothing in this phase blocks a next phase.** The two open follow-ups (post-merge production observation, the two Smartsheet-side preconditions) are owner-tracked operational items, not phase-blocking code gaps -- a future phase or a direct operator action closes them independently of GSD phase sequencing.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-08*

## Self-Check: PASSED

**Files verified:**
- FOUND: `website/docs/runbook/foreman-helper-2.md`
- FOUND: `website/sidebars.ts`
- FOUND: `website/docs/reference/environment.md`
- FOUND: `website/docs/runbook/whats-new.md`
- FOUND: `.github/prompts/configuration-environment.md`
- FOUND: `docs/ai/architecture.md`
- FOUND: `memory-bank/living-ledger.md`
- FOUND: `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`

**Commits verified:**
- FOUND: `fe70b28` (Task 1)
- FOUND: `b080d59` (Task 2)
- FOUND: `8fc4603` (ledger sync)
- FOUND: `a3998f9` (Task 3: D-14-12-ROLLOUT)
- FOUND: `6d8942c` (deploy-now merge to master)
