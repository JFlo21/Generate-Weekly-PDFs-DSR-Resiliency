---
phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration
plan: 02
subsystem: infra
tags: [smartsheet-python-sdk, pip, dependency-migration, living-ledger, live-probe]

# Dependency graph
requires:
  - phase: 08-01
    provides: smartsheet-python-sdk 4.3.0 installed, dead 3.x re-export shim removed, green six-gate + full pytest proof
provides:
  - Exact pin smartsheet-python-sdk==4.3.0 in requirements.txt (emergency <4.0.0 ceiling lifted)
  - Living Ledger entries recording the migration and the D-05 live-probe sign-off
  - Operator-run live read-only probe proving real 4.3.0 transport + error shapes
  - D-06 rollout runbook and D-07 rollback runbook captured for the operator
  - Deferred-item record of a pre-existing (non-SDK) SKIP_UPLOAD delete-before-skip defect
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/08-smartsheet-python-sdk-4-0-0-compatibility-migration/08-02-SUMMARY.md
  modified:
    - requirements.txt
    - memory-bank/living-ledger.md
    - .planning/phases/08-smartsheet-python-sdk-4-0-0-compatibility-migration/deferred-items.md

key-decisions:
  - "Exact pin smartsheet-python-sdk==4.3.0 (no range), per D-01, lifting the >=3.1.0,<4.0.0 emergency ceiling"
  - "CLAUDE.md left unchanged — grep confirmed zero stale smartsheet-python-sdk references (D-08 discretion, no-op)"
  - "SKIP_UPLOAD delete-before-skip defect deferred, not fixed inline — pre-existing on 3.x, out of this plan's compat-only file list; self-healing withheld-hash behavior means no data loss"
  - "Operator approved the live probe with the finding recorded, not treated as SDK regression"

patterns-established: []

requirements-completed: [SDK-03, SDK-05, SDK-06]

# Metrics
duration: ~20min active (across two sessions, separated by an operator-run checkpoint pause)
completed: 2026-07-22
---

# Phase 08 Plan 02: SDK Pin Lift + Living Ledger + Live Probe Summary

**Emergency `<4.0.0` pin lifted to the exact `smartsheet-python-sdk==4.3.0`; migration recorded in the Living Ledger; operator-run live read-only probe confirms real 4.3.0 transport is green against production Smartsheet, with one pre-existing (non-SDK) SKIP_UPLOAD finding captured and deferred.**

## Performance

- **Duration:** ~20 min of active executor work, split across two sessions separated by the Task 3 `checkpoint:human-verify` pause (operator ran the live probe independently)
- **Started:** 2026-07-21T21:31:11-05:00 (first commit, Task 1)
- **Completed:** 2026-07-22T10:26:39-05:00 (last commit, ledger sign-off)
- **Tasks:** 3 completed (2 auto + 1 checkpoint:human-verify)
- **Files modified:** 3 (`requirements.txt`, `memory-bank/living-ledger.md`, `deferred-items.md`)

## Accomplishments

- Replaced `smartsheet-python-sdk>=3.1.0,<4.0.0` with the exact `smartsheet-python-sdk==4.3.0` in `requirements.txt`, with a comment recording the exact-pin rule, the changelog review date, and a pointer to the Living Ledger.
- Appended a dated Living Ledger entry recording the migration: exact pin landed, dead re-export block removed (08-01), Gate 1 baseline delta (178→177), and the six-gate/pytest evidence.
- Confirmed `CLAUDE.md` needed no change (`grep -rn "smartsheet-python-sdk" CLAUDE.md` returned zero matches both before and after) — correctly left untouched per D-08 discretion.
- Operator (Juan) ran the D-05 bounded read-only live probe against real production Smartsheet on 4.3.0 and it came back **green** for every SDK-facing criterion.
- Captured a pre-existing (not SDK-caused) `SKIP_UPLOAD` defect discovered by the probe in `deferred-items.md`, and recorded a second Living Ledger entry signing off the probe result plus the finding.

## Task Commits

Each task was committed atomically:

1. **Task 1: Lift the emergency pin to the exact ==4.3.0** — `76e2471` (fix)
2. **Task 2: Append the Living Ledger migration entry (CLAUDE.md checked, no change needed)** — `038816c` (docs)
3. **Task 3: Live read-only Smartsheet probe on 4.3.0 + rollout/rollback runbook** — operator-run probe (no repo edits per plan's `<files>` spec for this task); follow-up documentation commits: `a31121d` (deferred-items.md finding) and `aa55b6b` (Living Ledger sign-off)

**Plan metadata:** this SUMMARY commit (parallel-executor convention — STATE.md/ROADMAP.md excluded, owned by the orchestrator)

## Files Created/Modified

- `requirements.txt` — exact pin `smartsheet-python-sdk==4.3.0` replaces the `>=3.1.0,<4.0.0` emergency ceiling; comment records the exact-pin rule + changelog review date + ledger pointer
- `memory-bank/living-ledger.md` — two new dated entries: `[2026-07-22 02:31]` (migration landed) and `[2026-07-22 10:20]` (D-05 live-probe sign-off + SKIP_UPLOAD finding)
- `.planning/phases/08-smartsheet-python-sdk-4-0-0-compatibility-migration/deferred-items.md` — new section documenting the pre-existing SKIP_UPLOAD delete-before-skip defect, self-healing behavior, and suggested future fix

## D-05 Live Probe Result (operator-run 2026-07-22 ~10:07 CDT)

**Command:** `SKIP_UPLOAD=true WR_FILTER=84157414,89881161 MAX_GROUPS=5 python generate_weekly_pdfs.py` (SDK version confirmed `4.3.0` via `python -m pip show smartsheet-python-sdk`)

**Result: PASSED** for all SDK-facing criteria:
- Real transport green end-to-end: all source sheets fetched, "Grouping validation passed: 2771 groups", target-sheet map 676 WRs (sheet `5723337641643908`), PPP map 545 WRs (sheet `8162920222379908`).
- 676 target-row + 545 PPP attachment-list calls completed via the retry wrapper in 12.8s/9.5s (8 workers), 0 cancelled.
- 5 Excel files generated locally under `generated_docs/` (WR 84157414 ×3 weeks, WR 89881161 ×2 weeks); totals validation printed; "Session complete!".
- Zero `ModuleNotFoundError` / `AttributeError` / retry-path exceptions. No SDK error-shape drift observed — `pipeline/retry.py`'s `ApiError.error.result` introspection matches the real 4.3.0 response shape.

**Approved-with-finding (recorded, not treated as SDK drift):**
- `SKIP_UPLOAD=true` gates only the UPLOAD half of the delete-then-upload sequence, not the DELETE half. The run deleted 2 prior primary attachments on the production target sheet (WR 89881161, weeks 072025 and 081725) and then correctly skipped the re-upload. This is pre-existing engine behavior, identical on 3.x — unrelated to the 4.3.0 migration.
- Self-healing confirmed in the log: the hash-history write was withheld for all 5 groups ("upload did not complete — they will regenerate next run"), so the next scheduled weekday cron run will regenerate and re-upload both files. Operator decision: wait for cron, no manual restore performed.
- Full detail and suggested fix logged in `deferred-items.md` (see "08-02: SKIP_UPLOAD deletes prior attachments before skipping upload").

## D-06 Rollout Runbook (recorded for the operator, not executed this plan)

1. This plan's `SKIP_UPLOAD=true` dry-run (above) already serves as rollout step 1 (reads prod, writes nothing) — complete.
2. Merge in a weekday **daytime** window immediately after a green scheduled run. Do **not** merge in the Sunday-night window before the Monday 05:00 UTC weekly deep run.
3. Fire **one** manual `workflow_dispatch` canary and watch it go green before walking away. The canary is a normal idempotent production run — no special flags needed.

## D-07 Rollback Runbook (recorded for the operator, not executed this plan)

1. Revert the PR. This restores the `>=3.1.0,<4.0.0` pin; the pip cache auto-busts on the `requirements.txt` hash, so no manual cache-clear is needed.
2. Optionally fire one confirm `workflow_dispatch` dispatch to verify the reverted state is green.
3. No other rollback machinery is required — this migration made zero workflow-file or retry-logic changes (D-03/D-04).

## Decisions Made

- **Exact pin, not a range** (D-01): `smartsheet-python-sdk==4.3.0` makes any future SDK bump a deliberate, changelog-reviewed PR — extends the 260608-gwm "upper-bound transport-critical deps" rule to its strongest form.
- **CLAUDE.md untouched**: grep confirmed no stale SDK reference existed before or after this plan; the D-08 discretionary refresh was correctly a no-op.
- **SKIP_UPLOAD finding deferred, not fixed inline**: fixing the delete/upload gate coupling is a real behavior change to `pipeline/upload.py`, outside this plan's compat-only, zero-behavior-change scope, and it's a pre-existing defect (identical on 3.x) rather than something this migration introduced. The self-healing withheld-hash mechanism means no attachment is permanently lost — the next cron run regenerates and re-uploads.
- **Operator approved with finding**: the checkpoint was resolved "approved" with the finding explicitly recorded (not silently ignored, not treated as an SDK regression).

## Deviations from Plan

### Auto-fixed Issues

None — no Rule 1/2/3 auto-fixes were needed. The one unplanned discovery (the SKIP_UPLOAD delete-before-skip behavior) was surfaced by the operator during the plan's own designed verification step (D-05 live probe) and was explicitly out-of-scope to fix per the plan's compat-only, zero-behavior-change mandate and the executor SCOPE BOUNDARY rule (pre-existing behavior unrelated to this plan's authorized changes) — it was documented in `deferred-items.md` and the Living Ledger instead, exactly as the coordinator instructed.

---

**Total deviations:** 0 auto-fixed. One pre-existing defect discovered and deferred per plan design (the D-05 probe's entire purpose is to surface exactly this class of finding).
**Impact on plan:** None on scope. The SDK migration itself is fully proven behavior-neutral (six gates + full pytest + real-transport live probe, all green). The deferred SKIP_UPLOAD finding is a separate, pre-existing issue for a future plan.

## Issues Encountered

None beyond the documented deferred item above. The checkpoint pause between Task 2 and Task 3 (operator running the live probe independently) was expected, designed behavior — not an issue.

## User Setup Required

None further. The `SMARTSHEET_API_TOKEN` env var referenced in this plan's `user_setup` frontmatter was the operator's existing production token, reused (not created) for the live probe, which the operator has already run successfully.

## Next Phase Readiness

- Phase 08 (smartsheet-python-sdk 4.0.0 Compatibility Migration) is functionally complete: SDK 4.3.0 installed, dead 3.x shim removed, exact pin lifted, six-gate + full pytest green, real-transport live probe green, Living Ledger fully records the migration.
- **Operator action still pending (D-06, not part of this plan's scope):** merge this branch in a weekday daytime window after a green scheduled run, then fire one watched `workflow_dispatch` canary. This is the actual production rollout — deliberately not executed as part of plan 08-02.
- **Tracked for a future plan (not blocking):** the SKIP_UPLOAD delete-before-skip defect in `pipeline/upload.py` (see `deferred-items.md`). Low/medium priority — self-healing prevents data loss, but the flag's name currently overpromises "read-only."
- No blockers for closing Phase 08.

---
*Phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration*
*Completed: 2026-07-22*

## Self-Check: PASSED

- FOUND: requirements.txt (contains `smartsheet-python-sdk==4.3.0`)
- FOUND: memory-bank/living-ledger.md (contains both new dated entries)
- FOUND: .planning/phases/08-smartsheet-python-sdk-4-0-0-compatibility-migration/deferred-items.md (SKIP_UPLOAD section present)
- FOUND: commit 76e2471 (fix(08-02): lift emergency SDK pin to exact ==4.3.0)
- FOUND: commit 038816c (docs(08-02): record SDK 4.3.0 migration in Living Ledger)
- FOUND: commit a31121d (docs(08-02): log SKIP_UPLOAD delete-before-skip defect)
- FOUND: commit aa55b6b (docs(08-02): record D-05 live-probe sign-off in Living Ledger)
