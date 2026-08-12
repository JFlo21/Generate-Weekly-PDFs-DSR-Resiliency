---
phase: quick-260812-jqx
plan: 01
subsystem: billing-pipeline
tags: [smartsheet, supabase, billing-audit, snapshot-date, defence-in-depth]

# Dependency graph
requires:
  - phase: quick-260812-isx
    provides: report-only rate-sanity audit pattern (RED-first tests, per-call kill-switch reads, audit_results summary wiring) reused here
provides:
  - Snapshot-date drift detection with zero extra Smartsheet API calls (billed-week baseline in a new Supabase shadow table)
  - Cell-history classifier distinguishing automation self-fires from manual edits, capped/paced/budget-aware
  - Hold-prior-week override for automation self-fires only, rewriting both Weekly Reference Logged Date and Snapshot Date
  - Post-hoc audit risk_level escalation wired to automation self-fire hold counts only
affects: [billing-audit, smartsheet-automation-fixes, audit-sheet-write-followup]

# Actuals (#2632)
actuals:
  tokens: 21612
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pre-grouping seam in pipeline/orchestrate.py for row-transform passes that must run upstream of grouping.py without editing it"
    - "Bulk Supabase read/write via billing_audit.snapshot_store, mirroring lookup_group_hash/upsert_group_hash's fail-safe contract"
    - "Per-call os.getenv reads for kill-switches (not frozen pipeline.config constants) so tests can toggle without reloading a module"
    - "Fail-open classification / fail-closed logging: every candidate is recorded even when gating declines to act"

key-files:
  created:
    - pipeline/snapshot_drift.py
    - billing_audit/snapshot_store.py
    - tests/test_snapshot_drift_audit.py
  modified:
    - billing_audit/schema.sql
    - pipeline/config.py
    - pipeline/orchestrate.py
    - audit_billing_changes.py
    - memory-bank/living-ledger.md

key-decisions:
  - "Hold-prior-week gate ships default OFF (SNAPSHOT_DRIFT_HOLD_ENABLED); only automation self-fires on an already-billed row are eligible for a hold; manual edits are NEVER held"
  - "Fail-open gating (unclassifiable drift is flagged, never held), fail-closed logging (every candidate — held, manual, or unclassified — is written to the Supabase event table)"
  - "Cell-history spend is capped at ~40 rows/run, self-paced ~2s between calls, and gated by a session sub-budget with a pre-flight guard"
  - "New additive Supabase tables (snapshot_provenance, snapshot_drift) appended to billing_audit/schema.sql for manual apply by Juan — the pipeline never runs DDL"
  - "No new mutating AUDIT_SHEET_ID write in v1 — _log_to_audit_sheet stays the pre-existing no-op placeholder; the durable flag surface is the Supabase shadow layer plus the run log"
  - "Added a post-seam Sentry warning capture when any hold is applied (plan-check follow-up, not in the original task text)"

patterns-established:
  - "Row-transform seam pattern: insert a self-contained pass between the audit block and grouping in orchestrate.py, own try/except, zero edits to grouping.py/excel.py"
  - "Hold overrides that affect billing week MUST rewrite every field that downstream code keys off — Weekly Reference Logged Date (grouping) AND Snapshot Date (Excel day-table filter, content hash, sort key) together, never just one"

requirements-completed: [QT-260812-jqx]

coverage:
  - id: D1
    description: "Detect rows whose computed billing week differs from their recorded prior billed week, using zero extra Smartsheet API calls"
    requirement: "QT-260812-jqx"
    verification:
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask1WeekDriftIsACandidate#test_drifted_week_emits_candidate_without_mutation"
        status: pass
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask1WeekUnchangedCostsNothing#test_unchanged_week_costs_zero_api_calls"
        status: pass
    human_judgment: false
  - id: D2
    description: "Classify each drift candidate as automation self-fire vs manual via targeted cell-history lookups, capped/paced/budget-aware, fail-open on any error"
    requirement: "QT-260812-jqx"
    verification:
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask2AutomationSelfFire#test_automation_write_no_nearby_units_change_is_self_fire"
        status: pass
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask2ApiErrorIsUnclassified#test_get_cell_history_raises_is_unclassified"
        status: pass
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask2BudgetGuardSkipsAll#test_low_remaining_budget_skips_classification_entirely"
        status: pass
    human_judgment: false
  - id: D3
    description: "Hold automation self-fires at their prior billed week (both Weekly Reference Logged Date and Snapshot Date), never manual/unclassified; row survives the Excel Monday-Sunday filter and the prior week's content hash is stable"
    requirement: "QT-260812-jqx"
    verification:
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask3HoldRewritesBothFields#test_hold_rewrites_both_fields_and_preserves_originals"
        status: pass
      - kind: integration
        ref: "tests/test_snapshot_drift_audit.py::TestTask3HeldRowSurvivesExcelFilter#test_held_row_appears_in_generated_workbook"
        status: pass
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask3PriorWeekHashStability#test_hash_stable_across_drift_and_hold_both_modes"
        status: pass
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask3ManualNeverMutated#test_manual_candidate_never_mutated_even_with_hold_enabled"
        status: pass
    human_judgment: false
  - id: D4
    description: "Only automation self-fire holds escalate audit risk_level; manual/unclassified drift is recorded but never inflates risk"
    requirement: "QT-260812-jqx"
    verification:
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask3RiskEscalation#test_four_holds_escalate_to_high"
        status: pass
      - kind: unit
        ref: "tests/test_snapshot_drift_audit.py::TestTask3RiskEscalation#test_zero_holds_leaves_risk_level_unchanged"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live operator verification of assumptions A1 (cell-history entry ordering) and A4 (automation modified_by email) against one known-drifted Smartsheet row, before enabling SNAPSHOT_DRIFT_HOLD_ENABLED in the workflow"
    verification: []
    human_judgment: true
    rationale: "Requires a live SMARTSHEET_API_TOKEN and a real known-drifted row in production Smartsheet data — unavailable in this execution environment. Recorded as an open item in .planning/WINDOWS.md (kind unrun-verify)."

# Metrics
duration: 38min
completed: 2026-08-12
status: complete
---

# Quick Task 260812-jqx: Snapshot-Date Drift Audit Summary

**Defence-in-depth Smartsheet snapshot-date drift detector that classifies automation self-fires vs manual edits via targeted cell-history lookups and holds only the automation self-fires at their prior billed week, with zero grouping.py/excel.py edits and both kill-switches defaulting to safe values.**

## Performance

- **Duration:** 38 min (planning-doc commit to final code commit)
- **Started:** 2026-08-12T15:48:58-05:00
- **Completed:** 2026-08-12T16:26:10-05:00
- **Tasks:** 3
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments

- Detects rows whose computed billing week differs from a durable per-row baseline in a new additive Supabase table, at zero extra Smartsheet API cost for non-drifted rows, seeding silently on first sight
- Classifies week-movers ONLY via targeted `Cells.get_cell_history` lookups (Snapshot Date + Units Completed?, ≤40 rows/run, ~2s self-paced, session-budget-aware), fail-open to `unclassified` on any error
- Holds automation self-fires at their prior billed week by rewriting BOTH `Weekly Reference Logged Date` and `Snapshot Date` — verified the held row survives `generate_excel`'s Monday-Sunday day-table filter and the prior week's content hash stays byte-stable in both legacy and extended change-detection modes
- Manual edits and unclassifiable drift are recorded but NEVER held, even with the hold gate enabled
- Only automation self-fire holds escalate the audit `risk_level`; four holds trip HIGH, four manual + four unclassified drifts leave it unchanged
- Added a post-seam Sentry warning capture when any hold is applied (plan-check follow-up)

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end drift detection — one path, zero Smartsheet API calls** - `55329a1` (feat)
2. **Task 2: Cell-history classifier with pacing, cap, and sub-budget** - `c58a9bd` (feat)
3. **Task 3: Hold-prior-week override (both fields) + audit risk wiring** - `0a68aeb` (feat)

**Plan metadata:** (this commit, below)

_Note: TDD-per-task — each task's tests were written first and run RED before implementation, then re-run GREEN before commit._

## Files Created/Modified

- `pipeline/snapshot_drift.py` - `apply_snapshot_drift_holds()`: detection, classification, and the hold override — the single place drift logic lives
- `billing_audit/snapshot_store.py` - Bulk provenance read/upsert + batched drift-event insert, fail-safe (never raises)
- `billing_audit/schema.sql` - Appended `billing_audit.snapshot_provenance` + `billing_audit.snapshot_drift` DDL (manual apply by Juan)
- `pipeline/config.py` - Six `SNAPSHOT_DRIFT_*` env-var switches declared next to the `TIME_BUDGET_MINUTES` family
- `pipeline/orchestrate.py` - One call site at the pre-grouping seam, plus the post-classification summary merge and Sentry capture
- `audit_billing_changes.py` - `total_snapshot_drift_holds` placeholder + `escalate_risk_for_snapshot_drift()`
- `tests/test_snapshot_drift_audit.py` - 27 tests across all three tasks, all RED-first
- `memory-bank/living-ledger.md` - Dated `[2026-08-12 15:30]` entry

## Decisions Made

- **Hold gate ships default OFF.** `SNAPSHOT_DRIFT_HOLD_ENABLED` defaults `false`; only detection + Supabase shadow-logging (`SNAPSHOT_DRIFT_AUDIT_ENABLED`, default `true`) is live by default. Flipping the hold gate on in the workflow is a deliberate follow-up operator action after live verification (see D5 above).
- **Fail-open on gating, fail-closed on logging.** Any classification failure (API error, missing column id, cap exhausted, budget short) becomes `unclassified` — flagged, never held. Every candidate, regardless of outcome, is still written to the append-only `billing_audit.snapshot_drift` table.
- **Both-fields hold rewrite is non-negotiable.** `Weekly Reference Logged Date` alone controls grouping, but `Snapshot Date` alone controls `generate_excel`'s Monday-Sunday day-table bucket AND the content hash / sort key in `change_detection.py`. Rewriting only one silently excludes the row from the workbook body — verified via a real `generate_excel` integration test and a hash-stability test in both change-detection modes.
- **Only self-fire holds feed `risk_level`.** `escalate_risk_for_snapshot_drift(summary, self_fire_holds)` takes ONLY the hold count as input by construction — manual/unclassified drift can never reach risk escalation, correct-by-construction rather than by a filtering condition that could be edited away.
- **Per-call env reads, not frozen config constants.** All six switches are read via `os.getenv(...)` inside `pipeline/snapshot_drift.py` at call time (mirroring the `RATE_SANITY_AUDIT_ENABLED` pattern from 260812-isx) so tests can toggle any switch without reloading a module. The matching `pipeline/config.py` constants exist for documentation/discoverability but are not the values actually consulted at runtime by this module.
- **Added Sentry capture for holds (plan-check follow-up).** The task text did not explicitly specify this, but the plan-check warning provided at kickoff called for a post-seam Sentry capture when holds occur — implemented via `sentry_capture_message_with_context` with `context_name="snapshot_drift"` and `tags={"subsystem": "snapshot_drift"}`, matching the aggregate-only, PII-safe logging discipline used elsewhere in this repo.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a boundary-precision test flake in the budget-guard test**
- **Found during:** Task 3 (running the full `test_snapshot_drift_audit.py` file after adding Task 3 tests)
- **Issue:** `TestTask2BudgetGuardSkipsAll` set `stale_session_start` exactly 160 minutes before `TIME_BUDGET_MINUTES=165`, leaving remaining budget at exactly the `SNAPSHOT_DRIFT_MAX_MINUTES=5` threshold. Under the slower wall-clock scheduling of the full test file (openpyxl-heavy tests included), the tiny execution delta between capturing `stale_session_start` and the guard's own `datetime.now()` call occasionally left `remaining_min` at or just above 5.0, so the pre-flight skip did not fire and the test flaked.
- **Fix:** Widened the margin to 163 minutes elapsed (2 minutes remaining, well under the 5-minute threshold) so ordinary test-execution latency cannot flip the outcome.
- **Files modified:** `tests/test_snapshot_drift_audit.py`
- **Verification:** Full file re-run 27/27 green, twice, including combined with the slower Task 3 integration tests.
- **Committed in:** `0a68aeb` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test flakiness, not production code)
**Impact on plan:** Test-only fix; no production behavior changed. No scope creep.

## Issues Encountered

None beyond the test-flakiness item above.

## User Setup Required

**External Supabase configuration required — see the plan's `user_setup` block** (`.planning/quick/260812-jqx-snapshot-date-drift-audit-detect-snapsho/260812-jqx-PLAN.md` frontmatter):

1. Apply the two appended `CREATE TABLE IF NOT EXISTS` blocks from `billing_audit/schema.sql` (project `poeyztlmsawfoqlanucc` → SQL Editor). Until applied, the pipeline degrades safely — every read surfaces as a fetch failure, falls back to the no-baseline seed-only path, and never produces a false drift flag.
2. Confirm `billing_audit` is still listed under Project Settings → API → Exposed schemas, then reload the PostgREST schema cache.
3. **Verify assumptions A1/A4 against ONE known-drifted row** (Smartsheet UI → a row from the 2026-08-12 drift incident → Snapshot Date cell history): confirm cell-history entry ordering and the literal `modified_by` email for automation writes. If the email is not `automation@smartsheet.com`, set `SNAPSHOT_DRIFT_AUTOMATION_EMAIL` rather than editing code. This is recorded as an open item in `.planning/WINDOWS.md` (kind `unrun-verify`) — no `SMARTSHEET_API_TOKEN` was available in this execution environment to run it directly.
4. No GitHub Actions workflow change is required to land this — `SNAPSHOT_DRIFT_HOLD_ENABLED` stays unset (defaults `false`) until step 3 is confirmed. Setting it to `'true'` in `.github/workflows/weekly-excel-generation.yml` is a deliberate follow-up operator action.

## Known Stubs

None introduced by this plan. `_log_to_audit_sheet` in `audit_billing_changes.py` remains the pre-existing no-op placeholder (documented in RESEARCH.md and explicitly out of scope for v1) — this was already true before this plan and is not a regression; a real `AUDIT_SHEET_ID` write is a separate, protected-area follow-up task.

## Next Phase Readiness

- Detection + Supabase shadow logging is live by default (`SNAPSHOT_DRIFT_AUDIT_ENABLED=true`); the hold gate is off and ready for a deliberate operator-driven enable once Juan completes the `user_setup` verification steps above.
- Follow-up (deferred, separate task per RESEARCH.md): a real mutating `AUDIT_SHEET_ID` write for "flag on the billing audit sheet" — requires Juan's approval, `SKIP_UPLOAD` gating, and audit-sheet column-id discovery.
- No blockers for merging this branch; the DDL apply + live-row verification are operator actions independent of the code landing.

## Self-Check: PASSED

All 9 created/modified files confirmed present on disk; all 3 task commit hashes (`55329a1`, `c58a9bd`, `0a68aeb`) confirmed in `git log`.

---
*Phase: quick-260812-jqx*
*Completed: 2026-08-12*
