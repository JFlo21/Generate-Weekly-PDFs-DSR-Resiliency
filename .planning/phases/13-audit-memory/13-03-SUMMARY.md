---
phase: 13-audit-memory
plan: 03
subsystem: database
tags: [supabase, pipeline_memory, audit, python, hashing]

# Dependency graph
requires:
  - phase: 13-audit-memory
    provides: "13-01's proven vertical slice -- IDENTITY_RECIPES/compute_finding_key contract, rate_sanity_mismatch branch as the pattern to mirror, module counters surface"
provides:
  - "build_finding_payloads with all three MEMORY_BACKED_CHECKS branches implemented (rate_sanity_mismatch from 13-01, price_variance_anomaly + data_consistency_issue new this plan)"
  - "Recipe-coverage CI gate (set(IDENTITY_RECIPES) == MEMORY_BACKED_CHECKS) plus a production-safe no-recipe skip path"
  - "Collapse observability (examined vs distinct finding counts) for the D-01-accepted rate_sanity_mismatch row-ambiguity case"
  - "DATA_CONSISTENCY_ISSUE_LITERALS bidirectional contract test pinning _validate_data_consistency's 8 issue strings as durable identity"
affects: [13-04 (fixed/resurfaced/reopened transitions), 13-05 (RLS/GRANTs/DDL apply)]

# Actuals (#2632)
actuals:
  tokens: 7450
  tasks: 3
  commits: 3
  plan_head_before: 921f0b5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-check payload-builder branches share one shape (resolve identity -> resolve week_ending -> compute_finding_key -> emit payload with everything else in evidence), matching 13-01's rate_sanity_mismatch template exactly."
    - "Recipe-coverage gate: dispatch checks finding_type against IDENTITY_RECIPES before branching, so a future check added to MEMORY_BACKED_CHECKS without a matching recipe entry degrades to a counted skip in production and fails a dedicated set-equality test in CI."
    - "Collapse-by-finding_key: build_finding_payloads de-duplicates its output by finding_key (last-write-wins for evidence) and logs both the examined and distinct counts, making the D-01-accepted row-ambiguity collapse observable instead of silent."
    - "Bidirectional literal-string contract test: DATA_CONSISTENCY_ISSUE_LITERALS in the Python module mirrors audit_billing_changes.py's message strings verbatim, verified red-then-green by a live single-character mutation."

key-files:
  created: []
  modified:
    - pipeline_memory/audit_findings.py
    - audit_billing_changes.py
    - tests/test_audit_findings.py

key-decisions:
  - "price_variance_anomaly never drops a finding for an unresolvable week -- 0 distinct weeks (no match, or no parseable date) and >1 distinct weeks both persist week_ending=None, but only the >1 case bumps the findings_week_ambiguous counter (0 distinct weeks is not 'ambiguous', it's simply absent)."
  - "data_consistency_issue's row_index is used only to resolve the source row for week_ending and to carry provenance in evidence -- it never enters the value list passed to compute_finding_key, verified by a same-identity-different-row_index equal-key test and a grep acceptance check."
  - "The recipe-coverage 'no branch wired' else-arm in build_finding_payloads is a defensive fail-safe, not a reachable path today -- all three MEMORY_BACKED_CHECKS entries now have both a recipe and a branch; the reachable gap this plan closes is a MISSING recipe entry (findings_skipped_no_recipe), tested by monkeypatching MEMORY_BACKED_CHECKS with an unmapped check id."
  - "DATA_CONSISTENCY_ISSUE_LITERALS is declared in pipeline_memory/audit_findings.py (not audit_billing_changes.py) so the durable-identity contract lives next to compute_finding_key, with only comment-only markers added at the source per D-02."

patterns-established:
  - "A payload-builder branch that can never legitimately drop a finding (price_variance_anomaly) returns a plain dict, not dict | None -- only branches with a real 'this finding cannot be identified at all' case (data_consistency_issue's unresolved row_index, rate_sanity_mismatch's no-match) return Optional."

requirements-completed: [AUD-01]

coverage:
  - id: D1
    description: "price_variance_anomaly payload branch: week_ending resolved via D-CD-01's WR-wide row pool (single week used, 0 or >1 distinct weeks persist NULL, only >1 bumps the ambiguity counter), never dropped, evidence-only fields excluded from the key"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py -k key_derivation"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_price_variance_multi_week_yields_none_week_ending_and_bumps_counter"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_price_variance_no_parseable_week_yields_none_and_is_not_dropped"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_price_variance_no_matching_rows_yields_none_and_is_not_dropped"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_price_variance_same_wr_same_rows_is_idempotent"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_price_variance_evidence_only_fields_do_not_change_key"
        status: pass
    human_judgment: false
  - id: D2
    description: "data_consistency_issue payload branch: identity uses sorted issue strings (order-independent equal keys), row_index resolves week_ending but never enters the hash input, out-of-range row_index skips with a named counter and never raises"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py::test_data_consistency_sorted_issues_produce_equal_key_key_derivation"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_data_consistency_out_of_range_row_index_skips_and_bumps_counter"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_data_consistency_resolves_week_ending_from_its_own_row_index"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_data_consistency_row_index_never_enters_finding_key"
        status: pass
      - kind: other
        ref: "grep -n row_index pipeline_memory/audit_findings.py (row lookup + evidence only, never the compute_finding_key argument list)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Exhaustive recipe dispatch: a MEMORY_BACKED_CHECKS type absent from IDENTITY_RECIPES is skipped with a named counter and a check-id-only WARNING, never raises; a CI test pins set(IDENTITY_RECIPES) == MEMORY_BACKED_CHECKS; the recent_discussion passthrough stays membership-filtered, not an exclusion list"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py::test_recipe_coverage_identity_recipes_matches_memory_backed_checks"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_unmapped_check_type_in_memory_backed_checks_skips_and_bumps_no_recipe_counter"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_recent_discussion_finding_yields_no_payload_no_counter_no_raise"
        status: pass
      - kind: other
        ref: "grep -n recent_discussion pipeline_memory/audit_findings.py (comment lines only, no conditional branch)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Collapse observability: two rate_sanity_mismatch findings sharing (wr, cu, work_type, week_ending) collapse to one payload; examined-vs-distinct counts differ by exactly one and are logged"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py::test_two_identical_rate_sanity_findings_collapse_to_one_payload"
        status: pass
    human_judgment: false
  - id: D5
    description: "DATA_CONSISTENCY_ISSUE_LITERALS pins _validate_data_consistency's exact 8 issue strings as durable identity via a bidirectional contract test; audit_billing_changes.py gains comment-only markers naming the coupling, with zero behavior change"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py::test_data_consistency_issue_literals_match_validate_data_consistency"
        status: pass
      - kind: other
        ref: "git diff -- audit_billing_changes.py (every added line matches ^\\s*# ; live single-character mutation of one mirrored string produced AssertionError, then a clean pass on revert)"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py tests/test_price_variance_risk_demotion.py -q (audit engine's own behavior unchanged)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-09-11
status: complete
---

# Phase 13 Plan 03: Audit-Memory Full Check Coverage Summary

**All three memory-backed audit checks (`rate_sanity_mismatch`, `price_variance_anomaly`, `data_consistency_issue`) now derive a D-01-conformant `finding_key` from their real emitted fields, with an exhaustive recipe-coverage CI gate, collapse observability, and a bidirectional contract test protecting `data_consistency_issue`'s literal-string identity from a silent reword.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-09-11
- **Completed:** 2026-09-11
- **Tasks:** 3 (all `type="auto" tdd="true"`)
- **Files modified:** 3 (`pipeline_memory/audit_findings.py`, `audit_billing_changes.py`, `tests/test_audit_findings.py`)

## Accomplishments

- Added the `price_variance_anomaly` payload branch: `week_ending` is resolved from the WR's full (week-agnostic) row pool per D-CD-01 -- exactly one distinct week is used, zero distinct weeks silently persists `None`, more than one distinct week persists `None` AND bumps `findings_week_ambiguous`. The finding is never dropped, unlike `rate_sanity_mismatch`'s no-match case.
- Added the `data_consistency_issue` payload branch: identity is `wr | week_ending | sorted(issues)` (D-CD-02), `week_ending` is resolved unambiguously from the single row at `row_index`, and `row_index` never enters the hash input -- only row lookup and `evidence` provenance.
- Made `build_finding_payloads` dispatch exhaustive and observable: a `MEMORY_BACKED_CHECKS` type missing from `IDENTITY_RECIPES` is a counted, non-raising production skip (`findings_skipped_no_recipe`) with a CI test (`set(IDENTITY_RECIPES) == MEMORY_BACKED_CHECKS`) that would catch the gap before it ever reaches production. Output is now de-duplicated by `finding_key` (last-write-wins for `evidence`), with an INFO line reporting both the examined and distinct counts so the D-01-accepted `rate_sanity_mismatch` row-collapse case is visible.
- Declared `DATA_CONSISTENCY_ISSUE_LITERALS` in `pipeline_memory/audit_findings.py`, mirroring `_validate_data_consistency`'s exact 8 issue strings (4 static + the 4 the per-field "Missing {field}" loop builds), and added a bidirectional contract test that drives the real check function over fixture rows and asserts set equality both ways.
- Added comment-only markers in `audit_billing_changes.py` (verified via `git diff` -- every added line matches `^\s*#`, no other line touched): one above `_validate_data_consistency`'s issue-collection block naming the identity coupling, one above `_detect_price_anomalies` explaining why its persisted `week_ending` can be `NULL`.
- Ran a live red-then-green mutation proof: temporarily appending one character to a mirrored literal string failed the contract test with an explicit `AssertionError` (extra items on both sides), then reverting restored a clean pass with zero residual diff.

## Task Commits

Each task was committed atomically:

1. **Task 1: price_variance_anomaly and data_consistency_issue identity branches** - `69db42f` (feat)
2. **Task 2: Exhaustive recipe dispatch, passthrough, and collapse observability** - `0f4f0ff` (feat)
3. **Task 3: Pin the load-bearing issue strings and mark them at the source** - `cf4d4b4` (test)

**Plan metadata:** (this commit)

## Files Created/Modified

- `pipeline_memory/audit_findings.py` (modified) - `_build_price_variance_payload`, `_build_data_consistency_payload`, `DATA_CONSISTENCY_ISSUE_LITERALS`, recipe-coverage gate + collapse de-duplication in `build_finding_payloads`, three new counter keys
- `audit_billing_changes.py` (modified) - two comment-only markers (no behavior change, confirmed by `git diff`)
- `tests/test_audit_findings.py` (modified) - 24 new tests covering every Task 1-3 behavior bullet and the literal-string contract

## Decisions Made

See `key-decisions` in frontmatter for the full record. In short: price_variance_anomaly's "never drop" rule distinguishes "0 distinct weeks" (absent, uncounted) from "multi-week" (ambiguous, counted); the recipe-coverage else-arm is a documented fail-safe rather than a currently-reachable path; and the literal-string constant lives with the hashing logic, not the check function, per D-02's edit boundary.

## Deviations from Plan

None - plan executed exactly as written, including the owner-confirmed D-01 recipe from 13-01 and every must-have truth/prohibition in this plan's frontmatter.

## Issues Encountered

One pre-existing test from 13-01 (`test_build_finding_payloads_unimplemented_memory_backed_check_skips_and_counts`) asserted the old "unimplemented check" placeholder behavior for `price_variance_anomaly`, which this plan's Task 1 explicitly supersedes (that type now has a real payload branch). Renamed and repurposed the test to assert the new, correct behavior (a real payload is produced, with `week_ending=None` for the no-rows-supplied case) rather than leaving a stale assertion in the suite. Not a plan deviation -- a natural consequence of completing the branch the old test was pinning as "not yet done."

## User Setup Required

None - no external service configuration required. `AUDIT_MEMORY_ENABLED` still ships off by default (unchanged by this plan); no live Supabase DDL touched.

## Next Phase Readiness

- All three `MEMORY_BACKED_CHECKS` types now have complete, tested payload-building branches sharing one contract (`compute_finding_key` + the D-01 identity recipe).
- Full suite: 2384 passed / 1 skipped (>= 2366 baseline from 13-01), 6-gate harness ALL PASSED (mypy delta neutral 70->70, golden `run_summary.json` unchanged at 30 keys).
- `AUD-01` requirement stays unmarked in `REQUIREMENTS.md` -- `requirements.ready-ids` confirms 0/1 ready, shared with sibling Phase 13 plans (13-04, 13-05, 13-06) still in progress; the shared-ID gate will mark it complete once the last declaring plan finishes.
- Plan 13-04 can now implement the `fixed`/`resurfaced`/`reopened` transitions in `upsert_audit_findings` against a fully-populated `build_finding_payloads` covering all three check types.
- Plan 13-05 owns RLS policies, GRANTs/REVOKEs, and the live DDL apply for `audit_finding` / `audit_finding_event` -- untouched by this plan.
- No blockers.

## Self-Check: PASSED

- `pipeline_memory/audit_findings.py` exists on disk: FOUND
- `audit_billing_changes.py` exists on disk: FOUND
- `tests/test_audit_findings.py` exists on disk: FOUND
- Commit `69db42f` present: `git log --oneline --all | grep -q 69db42f` -> FOUND
- Commit `0f4f0ff` present: `git log --oneline --all | grep -q 0f4f0ff` -> FOUND
- Commit `cf4d4b4` present: `git log --oneline --all | grep -q cf4d4b4` -> FOUND
- All Task 1-3 acceptance criteria re-verified via grep/pytest -- all PASS (see Accomplishments and coverage block above)
- Full suite: 2384 passed, 1 skipped, 0 failed (baseline 2366) -- PASS
- 6-gate harness: ALL 6 GATES PASSED -- PASS
- `git diff -- audit_billing_changes.py` (against 13-01 baseline `921f0b5`): every added line matches `^\s*#` -- PASS

---
*Phase: 13-audit-memory*
*Completed: 2026-09-11*
