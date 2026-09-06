---
phase: 14-foreman-helper-2
plan: 02
subsystem: pipeline
tags: [smartsheet, change-detection, pricing, observability, planning-only]

# Dependency graph
requires:
  - phase: 14-foreman-helper-2 (plan 01)
    provides: Helper #2 tracer slice (fetch/grouping/change_detection wiring) that this plan's gap answers depend on being readable
provides:
  - Evidence-backed closure of A1/A2 (first-run suppression risk) — CONFIRMED SAFE, no guard needed
  - Evidence-backed closure of the parity sub-finding — not a live concern, plan 14-04 unaffected
  - Evidence-backed closure of A3 across attribution.py (no change), pricing.py (change assigned to 14-06), observability.py (change assigned to 14-07/14-08)
  - Owner-observed live Smartsheet column state for all four Task 3 questions, dated 2026-09-06
  - Pilot-mode determination for plan 14-10: FIXTURE-ONLY (Resource Analyst Helper #2 column blank on all 576 rows)
affects: [14-04, 14-06, 14-07, 14-08, 14-10]

# Actuals (#2632)
actuals:
  tokens: 5616
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Evidence citation contract: every verdict in 14-PENDING-RESOLUTIONS.md cites file + line range read, never a documented-contract assumption"
    - "OWNER-OBSERVED LIVE STATE labeling: 14-DECISIONS.md separates repository-derived evidence from owner-delegated read-only Smartsheet observations"

key-files:
  created:
    - .planning/phases/14-foreman-helper-2/14-PENDING-RESOLUTIONS.md
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md
  modified: []

key-decisions:
  - "A1/A2: pipeline_memory.group_state skip and the _live_row_attachments pre-seed are both structurally unable to suppress a first Helper #2 generation — no guard needed in plan 14-06"
  - "Parity sub-finding: pipeline/parity.py never reads a prior run's stored content_hash and the shadow-parity block is dormant (RUN_MEMORY_WRITE_ENABLED=0) — plan 14-04's HASH_FIELDS decision is unaffected"
  - "pipeline/pricing.py is variant-agnostic for plain helper2 (confirms D-14-03 by code, not assumption), but plan 14-06 MUST extend two branches (exclusion tuple + rate-column selector) for the future aep_billable_helper2/reduced_sub_helper2 shadow variants or they will silently mis-price"
  - "pipeline/observability.py._PII_LOG_MARKERS does not yet cover the new HELPER2 GROUP CREATED / _HELPER2_ log literals grouping.py already emits — assigned to plans 14-07 and 14-08"
  - "Owner-delegated read-only Smartsheet probe (2026-09-06) confirms Resource Analyst Foreman Helper #2 is blank on all 576 rows — plan 14-10's pilot is FIXTURE-ONLY, not a dry-run over real Helper #2 data"
  - "No PARTIAL Helper #2 column set exists anywhere in the live 117-sheet sweep — plan 14-07's capability-unavailable fixture stays synthetic; a partial-set fixture would be defensive, not observed"

patterns-established:
  - "Verdict vocabulary (CONFIRMED SAFE / REQUIRES GUARD / STILL UNKNOWN / NO CHANGE NEEDED / CHANGE NEEDED / LIVE-COLUMN-PROBE: ANSWERED) reused verbatim across 14-PENDING-RESOLUTIONS.md and 14-DECISIONS.md so later plans can grep for a single token"

requirements-completed: [HLP-04, HLP-06, HLP-07]

coverage:
  - id: D1
    description: "A1/A2 first-run suppression risk answered from pipeline_memory/reader.py, pipeline/change_detection.py, pipeline/orchestrate.py, and pipeline/parity.py read paths"
    requirement: "HLP-06"
    verification:
      - kind: other
        ref: "python -c automated check: '## A1' and '## A2' and 'parity' present in 14-PENDING-RESOLUTIONS.md (Task 1 <verify>)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A3 module-scope answers for pipeline/attribution.py, pipeline/pricing.py, pipeline/observability.py, plus prototype fixture-shape review"
    requirement: "HLP-04"
    verification:
      - kind: other
        ref: "python -c automated check: '## A3' and all three module paths present in 14-PENDING-RESOLUTIONS.md (Task 2 <verify>)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Owner confirms live Helper #2 column state and the Resource Analyst pilot-data precondition, dated and read-only"
    requirement: "HLP-07"
    verification:
      - kind: manual_procedural
        ref: "14-DECISIONS.md LIVE-COLUMN-PROBE: ANSWERED marker, observed 2026-09-06, commit 41f14b1"
        status: pass
    human_judgment: true
    rationale: "Live production Smartsheet state can only be confirmed by the owner via a delegated read-only connector probe; no repository read or automated check can observe production column state, and the plan's own gate (gate=\"blocking-human\") requires explicit owner confirmation rather than automated inference."

duration: ~15min (Task 3 continuation only; Tasks 1-2 completed in a prior session)
completed: 2026-09-06
status: complete
---

# Phase 14 Plan 02: Pending Resolutions Summary

**Closed all four 14-RESEARCH.md "pending" gaps: two code-path suppression risks confirmed safe, three module scopes assigned or cleared, and the owner-confirmed live Smartsheet state marks plan 14-10's pilot as fixture-only.**

## Performance

- **Duration:** ~15 min for this continuation (Task 3 only); full plan duration spans two sessions
- **Completed:** 2026-09-06
- **Tasks:** 3 (all complete)
- **Files modified:** 2 (both created: 14-PENDING-RESOLUTIONS.md, 14-DECISIONS.md)

## Accomplishments

- **Task 1 (A1/A2 + parity):** Read `pipeline_memory/reader.py`, `pipeline/change_detection.py:815-880` (and the full `_resolve_unchanged_for_skip` function through line 915), `pipeline/orchestrate.py:1190-1260` and `:3148-3184`, and `pipeline/parity.py:85-204`. Both the `group_state` hash-skip and the `_live_row_attachments` pre-seed are keyed such that a brand-new `helper2` variant cannot be mistaken for an existing attachment — CONFIRMED SAFE, no guard required. The parity mechanism is dormant in production and structurally insensitive to which fields compose a hash.
- **Task 2 (A3):** Read `pipeline/attribution.py`, `pipeline/pricing.py`, `pipeline/observability.py`, and skimmed the two renamed prototype test files for fixture shapes only. `attribution.py` needs no change. `pricing.py` is variant-agnostic today (confirms D-14-03 by code) but needs two branch extensions assigned to plan 14-06 for the future subcontractor shadow variants. `observability.py._PII_LOG_MARKERS` needs new Helper #2 literals, assigned to plans 14-07 and 14-08.
- **Task 3 (live column confirmation — this continuation):** Owner authorized and the session ran a read-only, owner-delegated Smartsheet connector probe on 2026-09-06. All four questions answered: Main ProMax still 6/6; a full 117-sheet sweep found 114 FULL / 3 NONE / 0 PARTIAL (no partial-set fixture is required by live evidence); Intake ProMax 8 and Backup 2 confirmed still 0/6 (accepted state, D-14-01); Resource Analyst `Foreman Helper #2` confirmed blank on all 576 rows. Marker `LIVE-COLUMN-PROBE: ANSWERED` and pilot-mode consequence (FIXTURE-ONLY) recorded in `14-DECISIONS.md`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Answer A1 and A2 — can a FIRST Helper #2 generation be suppressed?** - `8dfea37` (docs)
2. **Task 2: Answer A3 — what Helper #2 needs from attribution.py, pricing.py, and observability.py** - `55e3428` (docs)
3. **Task 3: Juan confirms the live Helper #2 column state and the pilot data precondition** - `41f14b1` (docs)

_Note: Tasks 1-2 were executed and committed in a prior session; this SUMMARY is written at the close of the Task 3 continuation, after the checkpoint's `gate="blocking-human"` was resolved with owner approval._

## Evidence Labeling (per plan `<output>` contract)

- **Tasks 1-2 (`14-PENDING-RESOLUTIONS.md`):** DOCUMENTED EVIDENCE — repository reads against current `HEAD`, each verdict citing a file plus line range. Not a dry-run pass, not a production observation of Helper #2 behavior.
- **Task 3 (`14-DECISIONS.md`):** OWNER-OBSERVED LIVE STATE — the owner explicitly authorized the four-question probe to be run read-only on his behalf through the Smartsheet connector ("Run the probe read only") rather than running it by his own hand. The probe executed zero writes: no column provisioning, no formula repair, no sheet reconnection, no row values or names recorded — only column titles, column ids, sheet counts, and one filtered row-count result (`rowsInFilter = 0`). This is neither a dry-run pass nor a production observation of Helper #2 *behavior* (no Helper #2 row has ever been generated); it is strictly a column-existence and column-blankness observation.

## Files Created/Modified

- `.planning/phases/14-foreman-helper-2/14-PENDING-RESOLUTIONS.md` - A1/A2/parity verdicts (Task 1) and A3 module verdicts + prototype fixture review (Task 2), all evidence-cited
- `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` - phase's running owner-decision ledger, seeded by Task 3's live-column-probe answers, dated 2026-09-06

## Decisions Made

- A1/A2: no first-run suppression guard needed anywhere in the pipeline; plans 14-04 and 14-06 inherit safe behavior with no additional code.
- Parity mechanism confirmed dormant and hash-agnostic; plan 14-04's HASH_FIELDS decision proceeds unaffected by mass Helper #2 hash volume.
- pricing.py: two specific line-ranged branches (`:636-639` exclusion tuple, `:678-681` rate-column selector) are REQUIRED tasks for plan 14-06, not discretionary — omitting them is a latent billing-pricing bug for the two future subcontractor shadow variants only (plain `helper2` is unaffected today).
- observability.py: `_PII_LOG_MARKERS` extension (`"HELPER2 GROUP CREATED"`, `"_HELPER2_"`, a `"Helper2="` token) assigned to plans 14-07 and 14-08; today's risk is dormant because `SENTRY_ENABLE_LOGS` defaults `false`, but the second defense-in-depth layer has a real gap that must close before that flag could ever flip.
- Pilot mode for plan 14-10 is FIXTURE-ONLY, not a dry-run over real Helper #2 rows — recorded explicitly rather than silently assumed, per the plan's own HLP-07 must-have.
- No partial Helper #2 column set exists live anywhere (0 of 117 sheets); plan 14-07 keeps its capability-unavailable fixture synthetic rather than deriving it from an observed partial sheet.

## Deviations from Plan

### Auto-fixed Issues

None — Tasks 1 and 2 executed exactly as written (no bugs, no missing functionality, no blocking issues encountered during the repository reads).

### Process Deviation (documented, not a Rule 1-4 code fix)

**1. Task 3 probe execution method**
- **Found during:** Task 3 (checkpoint resolution)
- **What happened:** The plan's checkpoint (`gate="blocking-human"`) specifies "Juan runs a read-only look at the live sheets." In this session, the owner explicitly authorized the four-question probe to be executed read-only through the Smartsheet MCP connector on his behalf ("Run the probe read only"), rather than running the lookups by his own hand in the Smartsheet UI.
- **Why this is not a scope violation:** The plan's underlying intent — a read-only, owner-authorized confirmation of live column state, with zero writes and zero automated approval of the checkpoint itself — was preserved. The checkpoint still required and received explicit owner sign-off ("approved") before this plan proceeded; no agent auto-approved a `gate="blocking-human"` checkpoint (per the standing rule, precondition/blocking-human checkpoints are never auto-approved even under auto mode).
- **Verification:** Zero writes performed (confirmed by the probe's own method notes in `14-DECISIONS.md`: "column-metadata reads... Zero writes. No column provisioning, no formula repair, no sheet reconnection, no row values read, no person's name recorded"). All four questions answered and dated. Automated verify (`LIVE-COLUMN-PROBE: ANSWERED` + `read-only` present) exits 0.
- **Files modified:** `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`
- **Committed in:** `41f14b1` (Task 3 commit)

---

**Total deviations:** 0 auto-fixed (Rules 1-4); 1 documented process deviation (delegated probe execution method, owner-authorized, zero writes, checkpoint still required explicit human sign-off).
**Impact on plan:** No scope creep, no code change, no production write. The deviation is procedural (who ran the read query) and does not weaken the plan's read-only guarantee or its blocking-human gate.

## Issues Encountered

None.

## Known Stubs

None — this is a documentation-only plan producing two planning artifacts; no application code or UI was written.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes were introduced. The plan's own threat register (T-14-02-01 through T-14-02-SC) already covers this plan's actual surface (live-probe information disclosure, live-probe tampering, verdict repudiation), and Task 3's execution matches the register's mitigations: only column titles, column ids, and counts were recorded; zero writes were performed; every verdict cites file plus line range.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 14-04 (HASH_FIELDS decision) can proceed without a new first-run suppression guard and without concern about parity-streak disturbance.
- Plan 14-06 has two REQUIRED tasks assigned from this plan: (1) no group_state/pre-seed guard needed, but (2) two specific pricing.py branch extensions ARE required for the two subcontractor Helper #2 shadow variants, plus the sibling-branch `_SUBCONTRACTOR_SCOPE_VARIANTS` cloning pattern for attribution.py (already the established pattern, confirmed unaffected).
- Plan 14-07 has two items assigned: extend `_PII_LOG_MARKERS` in observability.py, and keep its capability-unavailable fixture synthetic (no live partial-set sheet exists to derive it from). It also inherits reusable fixture shapes (`_row(**overrides)` base dict, the `_Helper2_<name>` filename token) and one stale-assertion warning (unified `__helper_role` shape is NOT how 14-01 shipped; must use the sibling-key `__helper2_foreman` shape instead) from the prototype fixture-shape review.
- Plan 14-08 has one item assigned: the same `_PII_LOG_MARKERS` extension, per this plan's own cross-reference.
- Plan 14-10's pilot scope must state FIXTURE-ONLY explicitly (owner-confirmed 2026-09-06); it must re-run this read-only probe before ever claiming a dry-run over real Helper #2 data.
- No blockers. No Smartsheet write occurred at any point in this plan. O-14-A remains open, untouched, and owned by plan 14-08 and Juan, exactly as this plan's guardrails required.

---
*Phase: 14-foreman-helper-2*
*Completed: 2026-09-06*

## Self-Check: PASSED

- FOUND: `.planning/phases/14-foreman-helper-2/14-PENDING-RESOLUTIONS.md`
- FOUND: `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`
- FOUND: `.planning/phases/14-foreman-helper-2/14-02-SUMMARY.md`
- FOUND commit `8dfea37` (Task 1)
- FOUND commit `55e3428` (Task 2)
- FOUND commit `41f14b1` (Task 3)

No missing items.
