---
phase: 13-audit-memory
plan: 04
subsystem: database
tags: [supabase, plpgsql, audit, pipeline_memory, python]

# Dependency graph
requires:
  - phase: 13-audit-memory
    provides: "13-01's proven vertical slice (finding-key recipe, RPC skeleton) + 13-03's full three-check build_finding_payloads coverage"
provides:
  - "The complete D-08 transition table server-side in pipeline_memory.upsert_audit_findings: opened/seen/resurfaced/reopened/fixed, all atomic in one plpgsql invocation"
  - "executed_checks() + build_reaudited_pairs(rows, executed_checks) -- the per-check re-audited-pair computation (AUD-02, D-10), wired into pipeline/orchestrate.py's audit-memory hook"
  - "tests/test_audit_findings_sql_contract.py -- a bidirectional lockstep Python-to-SQL contract test (recordset columns, CHECK value sets, RPC parameter names, fixed-branch join structure)"
  - "5 lifecycle tests (-k lifecycle) pinning the CALLER's per-run payload contract across the success-criterion-1 sequence"
affects: [13-05 (RLS/GRANTs/DDL apply + owner read-back verification of the SQL transitions), 13-06]

# Actuals (#2632)
actuals:
  tokens: 12625
  tasks: 3
  commits: 3
  plan_head_before: 9cd8c8a

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two independent-but-disjoint writable CTEs on the same table in one plpgsql statement (upserted covers finding_keys IN incoming; to_fix/fixed_upd covers finding_keys NOT IN incoming) -- valid per Postgres semantics (all CTEs share one snapshot; only truly overlapping row writes are unspecified) and avoids a second round-trip statement."
    - "The 'fixed' branch is an explicit JOIN against the p_reaudited_pairs recordset (never a NOT EXISTS over the whole table), so an empty array structurally cannot close anything -- enforced by a grep-free structural regex test."
    - "RPC_PARAM_KEYS/FINDING_STATUS_VALUES/FINDING_EVENT_TRANSITIONS declared as Python module constants (not test-only literals) so a contract test has ONE name to grep on each side of the boundary; the params dict is built via dict(zip(RPC_PARAM_KEYS, ...)) so it structurally cannot drift from the constant."
    - "Per-check re-audited-pair scoping: build_reaudited_pairs emits one {check_id, wr, week_ending} triple PER EXECUTED CHECK per distinct (wr, week) pair, not one triple per pair -- so a disabled check (RATE_SANITY_AUDIT_ENABLED=false) never appears in any pair and can close nothing that run, even though the other two checks' pairs for the same (wr, week) are present."
    - "Lifecycle tests verify the CALLER's contract via a stateful fake RPC double, never the live plpgsql transitions -- documented explicitly in the test module's docstring, with plan 13-05's owner read-back named as the verification of record for the SQL."

key-files:
  created:
    - tests/test_audit_findings_sql_contract.py
  modified:
    - pipeline_memory/schema.sql
    - pipeline_memory/audit_findings.py
    - pipeline/orchestrate.py
    - tests/test_audit_findings.py

key-decisions:
  - "Two-writable-CTE design over a second sequential SQL statement: the 'opened/seen/resurfaced/reopened' CTE chain and the 'fixed' CTE chain both live inside ONE WITH query (one plpgsql function body executes as one transaction regardless), keeping the whole D-08 table in a single set-based statement rather than splitting the RPC into two round trips."
  - "week_ending IS NULL match rule implemented as (af.week_ending IS NULL OR p.week_ending = af.week_ending) inside the JOIN's ON clause, not as a separate UNION branch -- keeps the fixed-branch structural join assertion (T-13-04-03) a single regex-checkable block."
  - "Existing 13-01 test test_orchestrate_hook_flag_on_calls_build_and_upsert_once_with_run_id was renamed and rewritten (test_orchestrate_hook_flag_on_calls_build_pairs_and_upsert_once_with_run_id) to mock build_reaudited_pairs/executed_checks explicitly, since the real (previously-empty) reaudited_pairs argument it asserted against is now computed for real -- a natural consequence of Task 2 completing the placeholder from 13-01, not a plan deviation (mirrors 13-03's own precedent for this exact situation)."

patterns-established:
  - "A test that needs a Python-side name to compare against SQL declares that name as a module constant next to the logic it governs (RPC_PARAM_KEYS, FINDING_STATUS_VALUES, FINDING_EVENT_TRANSITIONS), never as a literal duplicated inside the test file."

requirements-completed: [AUD-01, AUD-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The complete D-08 transition table (opened/seen/resurfaced/reopened/fixed) is expressed server-side in one atomic upsert_audit_findings invocation; an empty or per-check-scoped-out p_reaudited_pairs array closes nothing"
    requirement: "AUD-02"
    verification:
      - kind: other
        ref: "grep -v '^--' pipeline_memory/schema.sql | grep -c \"SET search_path = ''\" (3, matches the 3 real functions -- the 4th grep hit is a comment line, not a function)"
        status: pass
      - kind: other
        ref: "grep -nE \"EXECUTE +'|EXECUTE +format\\(|\\|\\| *quote_\" pipeline_memory/schema.sql (no match, exit 1)"
        status: pass
      - kind: other
        ref: "grep -c \"jsonb_to_recordset(p_findings) AS q(\" pipeline_memory/schema.sql (1)"
        status: pass
      - kind: other
        ref: "grep -nc \"REFERENCES pipeline_memory.run_ledger\" pipeline_memory/schema.sql (0)"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings_sql_contract.py::FixedBranchStructuralContractTests::test_fixed_branch_joins_against_pairs_recordset"
        status: pass
    human_judgment: true
    rationale: "The plpgsql transition logic itself (opened/seen/resurfaced/reopened/fixed state machine correctness against real data) is not executable in this sandbox -- Task 1's grep/regex checks and the contract test prove structure and shape, not live transition behavior. Plan 13-05's owner read-back against the applied Supabase project is the verification of record for the SQL, per this plan's own scope boundary and the lifecycle test module's docstring."
  - id: D2
    description: "executed_checks() mirrors RATE_SANITY_AUDIT_ENABLED's gate character-for-character; build_reaudited_pairs(rows, executed_checks) computes one {check_id, wr, week_ending} triple per executed check per distinct (wr, week) pair, never dropping an unparseable week, and orchestrate.py's hook passes the real computation through (replacing 13-01's empty-list placeholder) with RPC summary counts flowing into the existing INFO line and the Sentry breadcrumb"
    requirement: "AUD-02"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py -k build_reaudited_pairs or -k executed_checks"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_orchestrate_hook_flag_on_calls_build_pairs_and_upsert_once_with_run_id"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_orchestrate_breadcrumb_carries_summary_counts_only"
        status: pass
      - kind: other
        ref: "git diff -- audit_billing_changes.py (empty for this plan's Task 2)"
        status: pass
      - kind: other
        ref: "git diff -- pipeline/orchestrate.py shows no change inside the AUDIT_SYSTEM_AVAILABLE/DISABLE_AUDIT_FOR_TESTING block"
        status: pass
      - kind: integration
        ref: "SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py (exit 0, 0 matches for audit_memory_error)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A bidirectional lockstep contract pins the p_findings/p_reaudited_pairs recordset column lists, the status/transition CHECK value sets, and the RPC parameter names against the Python module's own constants and emitted keys; a rename on either side fails CI -- proven red-then-green live"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings_sql_contract.py -q (6 passed)"
        status: pass
      - kind: other
        ref: "Live mutation proof: renaming build_finding_payloads' finding_key output key to finding_key_RENAMED_FOR_RED_PROOF made FindingsRecordsetContractTests fail (KeyError inside build_finding_payloads itself, still a legitimate RED); reverted via Edit tool (no git checkout), suite green again"
        status: pass
      - kind: other
        ref: "Live mutation proof: removing 'suppressed' from the status CHECK list in schema.sql made test_status_check_values_match_python_constant fail with an explicit set-mismatch AssertionError; reverted via Edit tool, suite green again"
        status: pass
    human_judgment: false
  - id: D4
    description: "5 lifecycle tests (-k lifecycle) drive a stateful fake RPC across the success-criterion-1 sequence (3 reproducing runs, 1 re-audited-without-reproduction run, 1 out-of-band acknowledge, 1 reproducing run again), pinning the caller's per-run payload contract; the test module's docstring states plainly this file never executes the plpgsql transitions"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py -k lifecycle -q (5 passed, 54 deselected)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Full regression suite and the 6-gate harness stay green with the completed RPC and the real re-audited-pair wiring in place"
    verification:
      - kind: other
        ref: "python -m pytest tests/ -q (2407 passed, 1 skipped -- baseline 2384 from 13-03)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh (ALL 6 GATES PASSED, mypy delta neutral 70->70, golden run_summary.json unchanged at 30 keys)"
        status: pass
    human_judgment: false

duration: ~50min
completed: 2026-09-11
status: complete
---

# Phase 13 Plan 04: Audit-Memory Finding Lifecycle (D-08) Summary

**The full D-08 finding-lifecycle transition table now runs atomically inside `pipeline_memory.upsert_audit_findings`, gated by a per-check `(check_id, wr, week_ending)` re-audited-pair set that the RPC joins against — so an empty or per-check-scoped-out pair array structurally cannot close a finding — with a bidirectional Python-to-SQL contract test and 5 caller-contract lifecycle tests pinning the boundary.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-09-11
- **Completed:** 2026-09-11
- **Tasks:** 3 (all `type="auto"`, Tasks 2-3 `tdd="true"`)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- Replaced the 13-01 skeleton body of `pipeline_memory.upsert_audit_findings` with the complete D-08 transition table: new key → `open` (+ `opened` event); existing key present in the payload → `acknowledged`→`resurfaced`, `fixed`→`open` (fixed_run cleared, + `reopened` event), `suppressed`/`open`/`resurfaced` → unchanged (+ `seen` event), with `last_seen_run`/`updated_at`/`severity`/`evidence` refreshed and `first_seen_run`/identity columns never overwritten; existing key absent from the payload, `open`/`resurfaced`, whose check ran this run AND whose group was re-audited → `fixed` (`fixed_run` set, `last_seen_run` deliberately NOT bumped, + `fixed` event). The `fixed` branch is an explicit `JOIN` against the `p_reaudited_pairs` recordset (never a `NOT EXISTS` over the whole table), with the D-CD-01 pooled-week exception (`af.week_ending IS NULL OR p.week_ending = af.week_ending`) inline in the join predicate.
- Added `pipeline_memory.audit_findings.executed_checks()` (mirrors `RATE_SANITY_AUDIT_ENABLED`'s gate character-for-character) and `build_reaudited_pairs(rows, executed_checks)` (one `{check_id, wr, week_ending}` triple per executed check per distinct `(wr, week)` pair, unparseable weeks persisted as `None` rather than dropped, deterministic sort order). Wired both into `pipeline/orchestrate.py`'s `_run_audit_memory_phase`, replacing 13-01's empty-list placeholder; the RPC's summary counts now flow into the existing `upsert_audit_findings` INFO log line and the Sentry breadcrumb (`summarize_upsert_result`, counts only, no identifiers).
- Created `tests/test_audit_findings_sql_contract.py`: a bidirectional lockstep contract pinning the `p_findings`/`p_reaudited_pairs` recordset column lists, the `status`/`transition` CHECK value sets, the RPC parameter names, and the `fixed` branch's join structure against three new Python module constants (`RPC_PARAM_KEYS`, `FINDING_STATUS_VALUES`, `FINDING_EVENT_TRANSITIONS`). Proved red-then-green live twice (a renamed payload key, a removed CHECK value) with reverts done via the Edit tool rather than any git command that discards uncommitted work.
- Added 5 lifecycle tests to `tests/test_audit_findings.py` (`-k lifecycle`) driving a stateful fake RPC across the CONTEXT.md success-criterion-1 sequence (3 reproducing runs, 1 re-audited-without-reproduction run, 1 out-of-band SQL acknowledge, 1 reproducing run again), asserting the CALLER's per-run `p_findings`/`p_reaudited_pairs` payload shape. The test module's docstring states explicitly that this file never executes the plpgsql transitions and names plan 13-05's owner read-back as the verification of record for the SQL.
- Full suite: 2407 passed / 1 skipped (baseline 2384 from 13-03); 6-gate harness ALL PASSED (mypy delta neutral 70→70, golden `run_summary.json` unchanged at 30 keys); production dry run with `AUDIT_MEMORY_ENABLED` unset confirms the whole path stays dormant (exit 0, zero `audit_memory_error` occurrences).

## Task Commits

Each task was committed atomically:

1. **Task 1: Complete the D-08 transition table in the RPC** - `995d1a9` (feat)
2. **Task 2: Compute the per-check re-audited pair set and pass it through** - `37d7a2c` (feat)
3. **Task 3: Lockstep Python-to-SQL contract test and lifecycle coverage** - `ab5ffaf` (test)

**Plan metadata:** (this commit)

_Note: Task 1's commit was amended once immediately after creation (`5964fec` → `995d1a9`) solely to add the session's required attribution trailers to the message; no content changed._

## Files Created/Modified

- `pipeline_memory/schema.sql` (modified) - Complete D-08 transition table in `upsert_audit_findings`; extended closing Python↔SQL contract comment block
- `pipeline_memory/audit_findings.py` (modified) - `executed_checks()`, `build_reaudited_pairs()`, `summarize_upsert_result()`, `RPC_PARAM_KEYS`/`FINDING_STATUS_VALUES`/`FINDING_EVENT_TRANSITIONS` constants, params dict built from `RPC_PARAM_KEYS`
- `pipeline/orchestrate.py` (modified) - `_run_audit_memory_phase` now computes real `reaudited_pairs`; breadcrumb carries RPC summary counts
- `tests/test_audit_findings.py` (modified) - executed_checks/build_reaudited_pairs/summarize_upsert_result tests, updated orchestrate-hook wiring tests, 5 new lifecycle tests, updated module docstring
- `tests/test_audit_findings_sql_contract.py` (created) - Bidirectional Python↔SQL contract test (6 tests)

## Decisions Made

See `key-decisions` in frontmatter. In short: the D-08 table is one atomic multi-CTE `WITH` statement (two disjoint writable CTE sets on `audit_finding`, valid per Postgres's documented same-snapshot semantics); the `week_ending IS NULL` pooled-week exception lives inline in the `fixed` branch's `JOIN` predicate rather than a separate branch, keeping the structural join assertion a single regex-checkable block; and the pre-existing 13-01 orchestrate-hook wiring test was renamed/rewritten (not a plan deviation) once its previously-empty `reaudited_pairs` assertion became real.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Own tooling error: `git checkout -- <file>` discarded uncommitted Task 3 edits mid-task**
- **Found during:** Task 3, while proving the red-then-green mutation evidence for the contract test
- **Issue:** After confirming RED with a temporary payload-key mutation, I ran `git checkout -- pipeline_memory/audit_findings.py` intending to revert only that mutation. Since Task 3's new module constants (`RPC_PARAM_KEYS`, `FINDING_STATUS_VALUES`, `FINDING_EVENT_TRANSITIONS`) and the `params` dict refactor were still uncommitted at that point, the checkout reverted the file all the way back to Task 2's commit, silently discarding those additions too.
- **Fix:** Re-applied the three constants and the `params = dict(zip(RPC_PARAM_KEYS, ...))` refactor via the Edit tool, then re-ran the full contract + audit-findings test files to confirm the state was fully restored (60 passed) before proceeding. All subsequent revert steps in this task used the Edit tool exclusively, never `git checkout`.
- **Files modified:** pipeline_memory/audit_findings.py
- **Verification:** `python -m pytest tests/test_audit_findings_sql_contract.py tests/test_audit_findings.py -q` → 60 passed, immediately after the re-apply
- **Committed in:** ab5ffaf (Task 3 commit — the recovered state, never separately committed broken)

---

**Total deviations:** 1 auto-fixed (1 self-inflicted tooling error, Rule 1)
**Impact on plan:** No scope creep and no lost work in the final committed state; the recovery was caught and fixed before any commit, entirely within Task 3's own working session.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required. `AUDIT_MEMORY_ENABLED` still ships off by default (unchanged by this plan); no live Supabase DDL was applied (per D-11, DDL application is an owner checkpoint in plan 13-05).

## Next Phase Readiness

- The complete `upsert_audit_findings` RPC and the real per-check re-audited-pair computation are both committed and test-covered; plan 13-05 can now own the RLS policies, GRANTs/REVOKEs, the live DDL apply to the Supabase project, and the owner read-back that verifies the SQL transitions actually behave as this plan's structural/caller-contract tests assume.
- `AUD-01`/`AUD-02` stay unmarked in `REQUIREMENTS.md` pending the shared-ID gate (sibling plans 13-05/13-06 still in progress); `requirements.ready-ids` will flip them once the last declaring plan finishes.
- No blockers.

## Self-Check: PASSED

- `pipeline_memory/schema.sql` exists on disk: FOUND
- `pipeline_memory/audit_findings.py` exists on disk: FOUND
- `pipeline/orchestrate.py` exists on disk: FOUND
- `tests/test_audit_findings.py` exists on disk: FOUND
- `tests/test_audit_findings_sql_contract.py` exists on disk: FOUND
- Commit `995d1a9` present: `git log --oneline --all | grep -q 995d1a9` → FOUND
- Commit `37d7a2c` present: `git log --oneline --all | grep -q 37d7a2c` → FOUND
- Commit `ab5ffaf` present: `git log --oneline --all | grep -q ab5ffaf` → FOUND
- All Task 1-3 acceptance criteria re-verified via grep/pytest — all PASS (see Accomplishments and coverage block above)
- Full suite: 2407 passed, 1 skipped, 0 failed (baseline 2384) — PASS
- 6-gate harness: ALL 6 GATES PASSED — PASS
- `git diff -- audit_billing_changes.py`: empty — PASS
- `git diff --diff-filter=D --name-only 9cd8c8a..HEAD`: empty (no unexpected deletions) — PASS

---
*Phase: 13-audit-memory*
*Completed: 2026-09-11*
