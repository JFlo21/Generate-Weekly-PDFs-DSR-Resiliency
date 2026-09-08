---
phase: 14-foreman-helper-2
plan: 07
subsystem: billing-pipeline
tags: [python, smartsheet, supabase, pipeline-memory, discovery, foreman-helper, tdd]

# Dependency graph
requires:
  - phase: 14-01
    provides: "HELPER2_ENABLED flag, the six Helper #2 column synonyms in pipeline/discovery.py, the sheet_has_helper2_columns capability gate and the helper2_capability_unavailable reason in pipeline/fetch.py, and the locked Helper #2 reason-string vocabulary"
  - phase: 14-02
    provides: "Live column-state confirmation (117 sheets surveyed, no partial Helper #2 column set observed; Intake ProMax 8 confirmed read-only), the A3 PII-safe logging finding, and the D-14-01 fixture-only verification rule"
  - phase: 14-04
    provides: "The first owner-applied Supabase DDL checkpoint pattern (D-14-08-APPLIED) that D-14-10-APPLIED mirrors"
provides:
  - "pipeline/discovery.py: MAPPING_SCHEMA_MARKER = 'helper2-v1' and a sixth, reject-only admission condition in _build_discovery_skip_index (marker must equal the current constant; null or stale marker -> full validation)"
  - "pipeline_memory/schema.sql: additive nullable sheet_registry.mapping_schema TEXT column (owner-applied; no DDL executed from any session)"
  - "pipeline_memory/reader.py: mapping_schema in the watermark select, plus a single-warning unknown-column degrade that returns every row with mapping_schema=None so no sheet is admitted from cache on a not-yet-migrated database"
  - "pipeline_memory/writer.py: mapping_schema_by_sheet parameter on upsert_sheet_registry; the marker is written only for sheets that just completed a full validation, never promoted for cache-admitted sheets"
  - "pipeline/fetch.py: helper2_no_qualifying_completion reason (capability present, nothing qualified) distinct from helper2_capability_unavailable (capability absent); the price-exclusion diagnostic's specialized-row recompute now covers the Helper #2 slot"
  - "tests/test_foreman_helper_2.py: MappingSchemaMarkerAdmissionTests, MappingSchemaColumnDegradeTests, MappingSchemaMarkerWriterTests, HelperTwoPartialColumnCapabilityTests, HelperTwoNoQualifyingCompletionTests, HelperTwoPriceExclusionDiagnosticTagTests, HelperTwoIntake8ShapedFixtureTests, HelperTwoDiscoveryFailedValidationUnchangedTests"
  - ".planning/phases/14-foreman-helper-2/14-DECISIONS.md: D-14-10-APPLIED (separate-column)"
affects: [14-08, 14-09, 14-10]

# Actuals (#2632)
actuals:
  tokens: 45000
  tasks: 3
  commits: 5
  plan_head_before: 5e0603c

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Schema-marker revalidation: a versioned string constant in the module that owns the synonym map is persisted beside the cached mapping and checked as one more reject-only admission gate; bumping the constant is the only mechanism needed to force exactly one revalidation per sheet after a synonym change"
    - "Not-yet-migrated degrade: the reader probes for the specific 'column does not exist' error signature, logs one warning per process, retries with the legacy select, and back-fills the new field as None so every downstream consumer sees 'unmarked' rather than raising -- slower but correct"
    - "RED-baseline honesty: when a plan's tests pin existing behavior as well as new behavior, the RED commit is expected to have some passing tests; only the tests for genuinely new behavior must fail (here 2 of 6 in Task 3)"

key-files:
  created:
    - .planning/phases/14-foreman-helper-2/14-07-SUMMARY.md
  modified:
    - pipeline/discovery.py
    - pipeline_memory/schema.sql
    - pipeline_memory/reader.py
    - pipeline_memory/writer.py
    - pipeline/fetch.py
    - tests/test_foreman_helper_2.py
    - tests/test_incremental_read.py
    - .planning/phases/14-foreman-helper-2/14-DECISIONS.md

key-decisions:
  - "D-14-10-APPLIED (owner, 2026-09-06): the marker is a separate nullable TEXT column `sheet_registry.mapping_schema`, not a reserved key inside `column_mapping`; marker value `helper2-v1`; degrade direction is 'slower but correct' -- a missing column means full validation for every sheet, never silent cache admission. One-time cost measured at ~0.3 s/sheet (121 sheets = 37.7 s of Phase 1 on canary run 33683979474), well inside the 165-min TIME_BUDGET_MINUTES."
  - "The five pre-existing skip-index admission conditions are byte-for-byte unchanged; the sixth is evaluated as one more `continue` gate, so evaluation order cannot loosen admission (T-14-07-01)."
  - "A cache-admitted sheet never has its marker promoted; only a full validation earns it (MappingSchemaMarkerWriterTests pins both directions)."
  - "The reader degrade warning names the plan in both 'Phase 14 Plan 07' and '14-07' forms after a GREEN-phase message-format mismatch surfaced in tests/test_incremental_read.py."
  - "A partial Helper #2 column set (one or two of the three key titles) is capability-unavailable, not partially capable -- a defensive shape, since 14-02's live probe found no partial set on any of the 117 sheets surveyed."
  - "Task 3 required NO change to pipeline/discovery.py: `git diff pipeline/discovery.py` was empty for the task, and HelperTwoDiscoveryFailedValidationUnchangedTests pins that a genuine read failure still aborts through the failed-validation path rather than being reported as a Helper #2 absence (T-14-07-04)."
  - "The price-exclusion diagnostic's Helper #2 recompute uses normalize_helper_value + is_checked (mirroring _detect_helper2_row's fabricated-claim guard) rather than a bare str().strip(), so a blank/NA/formula-error Helper #2 claim is never counted as 'specialized' even in a log tag."

patterns-established:
  - "Every owner-applied Supabase DDL in this phase follows the same shape: additive nullable column, code that tolerates its absence by degrading toward more work (never less correctness), a D-14-xx-APPLIED record before the code lands, and no DDL executed from an agent session."

requirements-completed: [HLP-03, HLP-04]
# Note: REQUIREMENTS.md keeps HLP-03 Pending until 14-08 (run-summary counters) and HLP-04
# Pending until 14-10 (rollout notes) land, matching the "keep pending until the last
# contributing plan lands" convention used for HLP-05 and HLP-06.

coverage:
  - id: D1
    description: "A sheet_registry row with a null, missing, or stale mapping_schema marker is NOT admitted from cache and takes one full validation; a row carrying the current marker is admitted; a current marker never overrides a live-version mismatch"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#MappingSchemaMarkerAdmissionTests (5 tests: null / missing key / stale / current / current-does-not-override-version-mismatch)"
        status: pass
    human_judgment: false
  - id: D2
    description: "On a database without the mapping_schema column, get_sheet_watermarks logs exactly one warning, retries with the legacy select, returns every row with mapping_schema=None (so nothing is admitted from cache), and never raises; any other error is not swallowed"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#MappingSchemaColumnDegradeTests (3 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_incremental_read.py (marker-aware fixtures; 5 previously-failing tests pass)"
        status: pass
    human_judgment: false
  - id: D3
    description: "upsert_sheet_registry writes the marker only for sheets that just completed a full validation; a cache-admitted sheet's marker is never promoted; the default call omits the marker for every sheet"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#MappingSchemaMarkerWriterTests (2 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A Helper #2-capable sheet with no qualifying completion logs helper2_no_qualifying_completion exactly once, distinct from helper2_capability_unavailable; a qualifying row suppresses it"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoNoQualifyingCompletionTests (2 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A sheet mapping only some of the three key Helper #2 columns is treated as capability-unavailable and logs that reason, never as partially capable"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoPartialColumnCapabilityTests::test_partial_helper2_column_set_is_capability_unavailable"
        status: pass
    human_judgment: false
  - id: D6
    description: "A price-excluded row whose only completion claim is the Helper #2 slot is tagged as a helper row in the price-missing diagnostic rather than falling through to the VAC-crew/plain tag"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoPriceExclusionDiagnosticTagTests::test_price_excluded_helper2_row_tagged_as_helper"
        status: pass
    human_judgment: false
  - id: D7
    description: "An Intake-ProMax-8-shaped source (full Helper #1 column set, none of the six Helper #2 titles) is accepted, generates its primary output normally, produces no Helper #2 group or file, and logs the capability-unavailable reason -- FIXTURE ONLY; sheet 2244739192541060 is never read, repaired, reconnected, or migrated"
    requirement: "HLP-04"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoIntake8ShapedFixtureTests::test_intake8_shaped_source_accepted_no_helper2_output"
        status: pass
    human_judgment: false
  - id: D8
    description: "A genuine sheet read failure still routes through discovery's failed-validation path and aborts the run; it is never reported as a Helper #2 absence; the strict-mode acceptance gate is untouched"
    requirement: "HLP-03"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py#HelperTwoDiscoveryFailedValidationUnchangedTests::test_genuine_read_failure_still_aborts_not_reported_as_helper2_absence"
        status: pass
      - kind: other
        ref: "git diff pipeline/discovery.py empty for Task 3 (discovery changes were confined to Task 2's marker gate)"
        status: pass
    human_judgment: false
  - id: D9
    description: "No regression across the pipeline: helper suite, full suite, and the 6-gate harness all pass; no local JSON cache reintroduced"
    verification:
      - kind: unit
        ref: "tests/test_foreman_helper_2.py (31 passed, 26 subtests)"
        status: pass
      - kind: unit
        ref: "tests/ full suite (2222 passed, 1 skipped, 541 subtests)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh (ALL 6 GATES PASSED; run_summary.json structure matches baseline, 25 keys)"
        status: pass
    human_judgment: false

# Metrics
duration: ~100min (spanned three sessions: Task 1 checkpoint 2026-09-06, Tasks 2-3 GREEN 2026-09-07, closeout 2026-09-08)
completed: 2026-09-08
status: complete
---

# Phase 14 Plan 07: Mapping-Schema Marker Revalidation and the Four Capability Reasons Summary

**Helper #2 now activates on sheets whose column mappings were cached before the synonyms existed — after exactly one bounded revalidation per sheet — and an operator reading the logs can tell "no Helper #2 columns", "columns present but nothing qualified", "partial column set", and "the read genuinely failed" apart.**

## Performance

- **Duration:** ~100 min across three sessions (token figure approximate)
- **Tasks:** 3 (1 owner checkpoint + 2 TDD tasks)
- **Files modified:** 8
- **Commits:** 5 (`0f2874f` docs, `50b630d` test, `2e98d3f` feat, `ac38699` test, `e7aa054` feat)

## Accomplishments

- **Task 1 — owner checkpoint (D-14-10-APPLIED, `0f2874f`).** Juan chose the separate-column shape: `sheet_registry.mapping_schema TEXT NULL`, marker value `helper2-v1`, degrade toward full validation ("slower but correct is correct"). The one-time cost was quantified from the Phase 11.1 canary (37.7 s for 121 sheets) rather than estimated. No DDL was executed from any session; the owner applies it by hand in the SQL Editor, recommended together with the 14-04 `row_state` DDL and the O-14-B RPC update.
- **Task 2 — the marker end to end (`50b630d` RED, `2e98d3f` GREEN).** `MAPPING_SCHEMA_MARKER` lives in `pipeline/discovery.py` beside the synonym map it versions; `_build_discovery_skip_index` gained a sixth reject-only `continue` gate and its docstring now enumerates six admission conditions. `pipeline_memory/reader.py` selects the marker and degrades with one warning (plus explicit `None` back-fill) when the column is missing; `pipeline_memory/writer.py` writes the marker only for freshly validated sheets. Five `tests/test_incremental_read.py` fixtures were extended with the marker so they keep exercising the cache-admitted path.
- **Task 3 — the four distinguishable conditions (`ac38699` RED, `e7aa054` GREEN).** `pipeline/fetch.py` tracks `sheet_helper2_qualified_seen` per sheet and logs `helper2_no_qualifying_completion` once when a Helper #2-capable sheet produced no qualifying row, distinct from the 14-01 `helper2_capability_unavailable` reason. The price-exclusion diagnostic's specialized-row recompute now covers the Helper #2 slot through the same fabricated-claim guard as detection. Partial column sets, the Intake-8-shaped fixture (HLP-04, fixture-only by docstring), and the untouched failed-validation path are each pinned by a named test.

## Evidence (labelled precisely)

- **FIXTURE PASS:** `python -m pytest tests/test_foreman_helper_2.py -q` → 31 passed, 26 subtests.
- **FIXTURE PASS:** `python -m pytest tests/ -q` → 2222 passed, 1 skipped, 541 subtests.
- **HARNESS PASS:** `bash scripts/run_6_gates.sh` → ALL 6 GATES PASSED (`run_summary.json` structure matches baseline, 25 keys).
- **RED baseline for Task 3:** with `pipeline/fetch.py` stashed, 2 of the 6 new tests failed (`HelperTwoNoQualifyingCompletionTests::test_capability_present_no_qualifying_row_logs_distinct_reason`, `HelperTwoPriceExclusionDiagnosticTagTests::test_price_excluded_helper2_row_tagged_as_helper`); the other 4 pin behavior that 14-01 already shipped, which is expected and stated here rather than presented as new coverage.
- **Not verified from this session:** whether the owner has applied the `mapping_schema` DDL to `poeyztlmsawfoqlanucc`. The code is correct in both states by construction (D2 above); the only observable difference is a one-time slower Phase 1 until the column exists.

## Deviations from plan

None. Task 3's "test-only obligation for discovery" held: no discovery code change was needed, so no finding was raised.

## Cross-plan notes

- **For 14-08:** the two fetch-side reason strings and the `sheet_has_helper2_columns` / `sheet_helper2_qualified_seen` signals are the inputs to Task 3's run-summary counters. The O-14-A owner decision (helper2-wins) is already recorded in `14-DECISIONS.md`, so 14-08 Task 1's blocking checkpoint is satisfied and Task 2 is unblocked.
- **For 14-09 / 14-10:** the marker column joins the owner's single SQL session; the rollout notes should state that the first run after the marker lands fully validates every sheet once (~40 s) and that a not-yet-migrated database logs one warning and behaves identically but slower.

## Self-Check: PASSED

- All acceptance criteria from Tasks 2 and 3 have a test assertion or a `git diff` check named above.
- The five pre-existing admission conditions were not weakened (T-14-07-01), absence never raises into failed validation (T-14-07-04), and the new log lines carry sheet names and reason codes only (T-14-07-05).
- No package installed (T-14-07-SC), no local JSON cache reintroduced, no live sheet touched.
