---
phase: 10-run-memory-foundation-shadow-writes
plan: 05
subsystem: testing
tags: [smartsheet-sdk, mem04, cassette-replay, formula-change-detection, living-ledger, d-09-gate]

# Dependency graph
requires:
  - phase: 10-run-memory-foundation-shadow-writes
    provides: "10-04's mem04_experiment.py probe CLI, derive_verdict()/safety_window_sensitivity_note(), and the build_sheet_from_dict/replay_probe_call_shapes replay helpers this plan points at real evidence"
provides:
  - "tests/fixtures/mem04/mem04_blank_lookup.json, tests/fixtures/mem04/mem04_edit_mapping.json -- real captured MEM-04 cassettes against Juan's hand-built sandbox rig (both D-08 scenarios, with/without SAFETY_WINDOW overlap)"
  - "RealCassetteCompletenessTests, RealCassetteReplayTests, RealCassetteVerdictTests in tests/test_mem04_formula_change.py -- regression coverage binding the 10-04 replay helper to the real cassettes and pinning the combined PASS verdict"
  - "the dated [2026-08-25 12:50] MEM-04 Living Ledger entry -- D-09 gate OPEN, Phase 11 cleared to enable incremental reads for formula-only recalculation changes"
affects: [11-incremental-reads]

# Actuals (#2632)
actuals:
  tokens: 32811
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Merge-then-derive: each committed cassette is a SEPARATE single-scenario file (one --out per scenario invocation); the combined PASS/FAIL verdict is computed by merging both cassettes' `scenarios` dicts and calling the unmodified plan-10-04 derive_verdict() -- never by hand-writing a verdict or trusting either file's own per-invocation 'undetermined' report in isolation"
    - "Double-timezone-suffix sanitizer in build_sheet_from_dict: smartsheet-python-sdk==4.3.0's own serialize() appends 'Z' onto an already-offset isoformat() string, producing e.g. '...+00:00Z' that dateutil.parser.parse rejects -- fixed with a recursive regex sanitizer applied before Sheet() reconstruction, a no-op for the 10-04 synthetic fixtures (clean 'Z'-only strings) and required for any real captured cassette"
    - "Corrected (not literal) cassette-completeness and ledger-tail verify checks: the plan's own <verify> one-liners assumed a flat top-level schema and a 6000-char tail window that don't match the real cassette schema (nested under scenarios[name]) or the entry size 12 evidence items actually require -- ran corrected equivalents that preserve the checks' intent (CASSETTES_COMPLETE_OK, DATED_ENTRIES_IN_TAIL=1) rather than skip verification"

key-files:
  created:
    - tests/fixtures/mem04/mem04_blank_lookup.json
    - tests/fixtures/mem04/mem04_edit_mapping.json
  modified:
    - tests/test_mem04_formula_change.py
    - memory-bank/living-ledger.md

key-decisions:
  - "Combined verdict is PASS: merging both real cassettes through derive_verdict() (unmodified from 10-04) yields 'rows_modified_since surfaced the formula-only change in both scenarios' -- both blank_lookup and edit_mapping showed the affected DEPENDENT row present in rows_modified_since WITH and WITHOUT the 15-minute SAFETY_WINDOW overlap"
  - "D-09 gate is OPEN: Phase 11 is cleared to enable incremental reads for formula-only recalculation changes. The weekly deep run stays the full-reconciliation safety net (D-07) regardless. The PASSIVE half of D-08's hybrid proof (mem04_passive_compare.py against two consecutive production shadow-run observations) is a non-blocking follow-up -- it has no production data yet since shadow writes haven't accumulated two runs -- and D-09 only required this fixture-proven verdict"
  - "Edit method recorded honestly in the Ledger: Juan authorized Claude to act as operator for Task 1 ('you run this for me'); the two triggering edits were Smartsheet MCP API cell updates Claude made on Juan's explicit instruction, not literal UI clicks. D-08's 'zero writes in the plan's tooling' still holds -- scripts/mem04_experiment.py itself made zero write calls (AST-scan-verified in 10-04); the rig build and edits used the Smartsheet MCP tools plus a one-off SDK snippet run from the shell, not any repo script"
  - "Discovered and fixed (test-only) a real smartsheet-python-sdk==4.3.0 to_dict() quirk: smartsheet.util.serialize() unconditionally appends 'Z' onto ANY datetime.isoformat() output, even an already-offset one, producing an invalid double-suffixed timestamp that broke naive replay of the real captured cassette. Fixed with a sanitizer in build_sheet_from_dict (test file only -- scripts/mem04_experiment.py never re-parses a captured response, so production capture is unaffected)"

requirements-completed: [MEM-04]

coverage:
  - id: D1
    description: "Both real MEM-04 cassettes (blank_lookup, edit_mapping) are committed as replayable test fixtures, scrub-checked for production sheet ids, WR-number patterns, and personnel names before commit"
    requirement: MEM-04
    verification:
      - kind: unit
        ref: "tests/test_mem04_formula_change.py::RealCassetteCompletenessTests"
        status: pass
      - kind: other
        ref: "scrub-check script (production ids, WR patterns, sensitive-key names) -- zero hits in either cassette"
        status: pass
    human_judgment: false
  - id: D2
    description: "The plan-10-04 replay helper reconstructs real SDK Sheet objects from both real cassettes and reproduces the exact recorded T2/if_version_after and T3a/T3b rows_modified_since keyword-argument shapes and the derived probe fields (affected_row_id, overlap/no-overlap presence, attempts_used)"
    requirement: MEM-04
    verification:
      - kind: unit
        ref: "tests/test_mem04_formula_change.py::RealCassetteReplayTests::test_replay_reproduces_recorded_t2_t3a_t3b_kwargs_and_probe_fields"
        status: pass
    human_judgment: false
  - id: D3
    description: "The combined verdict, derived deterministically by merging both real cassettes through the unmodified plan-10-04 derive_verdict(), is one explicit PASS sentence (each cassette alone is 'undetermined', matching what Juan saw live per invocation)"
    requirement: MEM-04
    verification:
      - kind: unit
        ref: "tests/test_mem04_formula_change.py::RealCassetteVerdictTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "The dated [2026-08-25 12:50] Living Ledger entry carries all twelve D-08 evidence items, the one explicit PASS verdict sentence, and an explicit D-09 line stating Phase 11 is cleared -- appended at the bottom with no existing entry modified and CLAUDE.md untouched"
    requirement: MEM-04
    verification:
      - kind: manual_procedural
        ref: "memory-bank/living-ledger.md, entry at line 6365 ([2026-08-25 12:50] MEM-04 answered)"
        status: pass
    human_judgment: true
    rationale: "The plan's own <verify><human-check> requires Juan to confirm the verdict sentence and edit details match what he observed live in the Smartsheet UI/API responses -- this is exactly the kind of confirmation an automated check cannot substitute for."

duration: ~40min
completed: 2026-08-25
status: complete
---

# Phase 10 Plan 05: MEM-04 Real-Rig Verdict Summary

**Real MEM-04 cassettes captured against Juan's hand-built sandbox rig, replayed and merged into a deterministic PASS verdict (`rows_modified_since` surfaces formula-only recalculation in both scenarios, with and without the SAFETY_WINDOW overlap), recorded in the Living Ledger with the D-09 gate now OPEN for Phase 11.**

## Performance

- **Duration:** ~40 min (this continuation session; Task 1 checkpoint spanned a prior session)
- **Started:** 2026-08-25 (continuation resume)
- **Completed:** 2026-08-25T17:53:13Z
- **Tasks:** 3 (Task 1 by operator in a prior session; Tasks 2-3 this session)
- **Files modified:** 4 (2 new cassette fixtures, 1 test file extended, 1 Ledger append)

## Accomplishments
- Committed Juan's two real captured cassettes (`tests/fixtures/mem04/mem04_blank_lookup.json`, `tests/fixtures/mem04/mem04_edit_mapping.json`) as replayable test fixtures against his hand-built Smartsheet sandbox rig (workspace `Sandbox` id `4902858211518340`; LOOKUP sheet id `6295051624730500`; DEPENDENT sheet id `4909062725521284` with a cross-sheet INDEX/MATCH column formula mirroring the real `Foreman`/`Helper Dept #` lookups) -- scrub-checked clean (no production sheet ids, WR-number patterns, or sensitive-key mentions) before commit
- Bound the plan-10-04 replay helper (`build_sheet_from_dict` / `replay_probe_call_shapes`) to both real cassettes: `RealCassetteCompletenessTests` (schema completeness against the actual nested `scenarios[name]` shape), `RealCassetteReplayTests` (reproduces the exact recorded T2/T3a/T3b keyword-argument shapes and derived probe fields from raw responses), `RealCassetteVerdictTests` (each cassette alone is `undetermined`, the merged pair is deterministic `PASS`) -- 6 new tests, 32 total in the file
- Discovered and fixed a real `smartsheet-python-sdk==4.3.0` `to_dict()` serialization quirk while binding the replay helper to real data: `smartsheet.util.serialize()` unconditionally appends `"Z"` onto any `datetime.isoformat()` output, even an already-offset one, producing an invalid double-suffixed timestamp (`"...+00:00Z"`) that `dateutil.parser.parse` rejects on reconstruction -- fixed with a sanitizer in `build_sheet_from_dict` (test-only; `scripts/mem04_experiment.py` itself never re-parses a captured response, so this never affected production capture)
- Derived the combined MEM-04 verdict deterministically by merging both cassettes' `scenarios` dicts through the unmodified 10-04 `derive_verdict()`: **PASS -- `rows_modified_since` surfaced the formula-only change in both scenarios**, with `row_present_in_rows_modified_since_overlap=True` AND `..._no_overlap=True` in both
- Appended the dated `[2026-08-25 12:50]` MEM-04 entry to `memory-bank/living-ledger.md` (bottom, no existing entry modified, `CLAUDE.md` untouched) carrying all twelve D-08 evidence items, the honest edit-method note (Claude as operator via Smartsheet MCP on Juan's instruction, not UI clicks), the discovered SDK serialization quirk, and an explicit **D-09 gate: OPEN** line clearing Phase 11 to enable incremental reads for this change class

## Task Commits

Each task was committed atomically:

1. **Task 1: Operator builds the sandbox formula rig and makes the two triggering edits** - `8bd75f3` (docs: checkpoint state record; no code commit -- operator work was Smartsheet MCP calls, not a repo change)
2. **Task 2: Ingest the captures, replay them, and derive the verdict** - `aa103f6` (feat)
3. **Task 3: Record the dated MEM-04 entry in the Living Ledger** - `1dc5aa3` (docs)

**Plan metadata:** commit pending (docs: complete plan)

## Files Created/Modified
- `tests/fixtures/mem04/mem04_blank_lookup.json` - real captured cassette, scenario (a) blank/archive the lookup value
- `tests/fixtures/mem04/mem04_edit_mapping.json` - real captured cassette, scenario (b) edit a mapping value in place
- `tests/test_mem04_formula_change.py` - added `RealCassetteCompletenessTests`, `RealCassetteReplayTests`, `RealCassetteVerdictTests`; fixed `build_sheet_from_dict` to sanitize the SDK double-timezone-suffix quirk (6 new tests, 32 total in file)
- `memory-bank/living-ledger.md` - appended the dated `[2026-08-25 12:50]` MEM-04 entry (124 lines)

## Decisions Made
See `key-decisions` in frontmatter. All four are load-bearing: the combined-verdict derivation method, the D-09 gate outcome, the honest edit-method record, and the SDK quirk fix are each either correctness-critical or directly determine what the Ledger entry is permitted to claim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `build_sheet_from_dict` could not reconstruct a real captured cassette due to a genuine smartsheet-python-sdk==4.3.0 serialization quirk**
- **Found during:** Task 2, first attempt to replay the real cassette through the mocked client
- **Issue:** `smartsheet.util.serialize()` in this exact pinned SDK version unconditionally appends `"Z"` onto any `datetime.isoformat()` output -- including an already-timezone-aware datetime whose `isoformat()` already carries a `"+00:00"` offset -- producing an invalid double-suffixed string (e.g. `"2026-08-25T17:36:36+00:00Z"`). `smartsheet.types.Timestamp`'s value setter parses incoming strings with `dateutil.parser.parse`, which raises `ParserError` on that malformed shape. Every timestamp field in the real captured `raw_response` (sheet-level and row-level `createdAt`/`modifiedAt`) carries this quirk; the 10-04 synthetic fixtures never exhibited it because they were hand-authored with clean `"Z"`-only strings.
- **Fix:** Added a recursive regex sanitizer (`_sanitize_double_tz_suffix`) applied inside `build_sheet_from_dict` before `Sheet(raw)` construction. No-op for any string not matching the malformed pattern (verified against the 10-04 synthetic fixtures, still 26 passing).
- **Files modified:** `tests/test_mem04_formula_change.py`
- **Verification:** Manually replayed both real cassettes end-to-end before and after the fix -- confirmed `ParserError` before, exact kwargs + probe-field reproduction after; `RealCassetteReplayTests` pins this as a regression.
- **Committed in:** `aa103f6` (Task 2 commit)

**2. [Rule 1 - Bug] The plan's own `<verify>` one-liners assumed a cassette schema and Ledger-tail window that don't match reality**
- **Found during:** Task 2 (cassette completeness check) and Task 3 (ledger tail check)
- **Issue:** (a) Task 2's literal completeness check tested `k not in json.load(open(p))` for `['baseline','probe','sdk_version','sheet_ids','disposable_test_rig']` against the TOP-LEVEL cassette dict -- but the actual schema `scripts/mem04_experiment.py` (built in 10-04) writes nests `baseline`/`probe`/`sheet_ids` one level down inside `scenarios[<scenario_name>]`. Run literally, the check always reports `INCOMPLETE` regardless of cassette content. (b) Task 3's ledger-tail check greps the LAST 6000 characters of the file for a dated-entry pattern -- but an entry faithfully carrying all twelve required D-08 evidence items, the edit-method note, the SDK quirk, and the D-09 line is necessarily ~10.5K characters (roughly 3.5x the previous longest entry in the file), so the entry's own header falls outside that fixed window.
- **Fix:** Ran corrected equivalents that preserve each check's actual intent rather than skip verification: (a) a schema-aware completeness check validating the real nested structure, which printed `CASSETTES_COMPLETE_OK` / exit 0; (b) a tail check sized to the entry's actual length (11000 chars), which found exactly 1 dated entry (`DATED_ENTRIES_IN_TAIL=1`). Neither the cassette schema nor the entry's required content was altered to fit a stale check -- the checks were corrected to match content the plan's own acceptance criteria mandates. Note: neither of the plan's literal `<verify>` command outputs is separately required by the `<acceptance_criteria>` block, which only requires `CASSETTES_COMPLETE_OK` (met by the corrected check) and the `LEDGER_OK` string-presence check (met, unmodified, verbatim).
- **Files modified:** none -- verification-only; no cassette or Ledger content was shaped around either stale check.
- **Verification:** Corrected checks run and passing (see above); the plan's own `LEDGER_OK` check and `git diff --exit-code -- requirements.txt` both ran verbatim and passed.
- **Committed in:** n/a (verification-only; no separate commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bugs discovered while exercising 10-04's tooling against real, rather than synthetic, evidence)
**Impact on plan:** No scope creep. Both fixes are test-infrastructure corrections required to honestly bind the replay helper and verify checks to REAL captured data -- exactly what plan 10-05 exists to do. Neither touches `scripts/mem04_experiment.py` (the read-only production probe) or any pipeline/billing code.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required

None for this plan. Task 1's `user_setup` (sandbox rig creation, the two triggering edits) was completed in a prior session -- see the `[2026-08-25 12:50]` Ledger entry's edit-method note for the honest record of how those edits were made (Smartsheet MCP API calls Claude ran on Juan's explicit instruction, not literal UI clicks).

## Next Phase Readiness
- MEM-04 is answered with a fixture-proven **PASS** verdict; the D-09 gate is **OPEN** -- Phase 11 (incremental reads) is cleared to enable `rows_modified_since` for formula-only recalculation changes.
- The weekly deep run (`0 5 * * 1`) remains the full-reconciliation safety net regardless (D-07, unchanged).
- Non-blocking follow-up: `scripts/mem04_passive_compare.py` (built in 10-04, credential-free-tested) can corroborate the causal answer at production scale once Phase 10's shadow writer has run in production at least twice -- it has no data to compare yet and does not gate D-09.
- Both real sandbox sheets (`6295051624730500` LOOKUP, `4909062725521284` DEPENDENT) remain in place in the Smartsheet `Sandbox` workspace for a future rerun if the SDK version pin ever changes.
- No blockers for `10-06-apply-schema-and-control-run` or Phase 11.

## Self-Check: PASSED

All created/modified files found on disk (`tests/fixtures/mem04/mem04_blank_lookup.json`,
`tests/fixtures/mem04/mem04_edit_mapping.json`, `tests/test_mem04_formula_change.py`,
`memory-bank/living-ledger.md`, this SUMMARY.md). Both task commits (`aa103f6`, `1dc5aa3`) found
in `git log`. Full suite: `1459 passed, 1 skipped, 132 subtests passed` (baseline before this plan's
work was `1453 passed, 1 skipped, 132 subtests` -- net +6, matching the 6 new tests exactly).
`git diff --exit-code -- requirements.txt` exits 0 (no dependency added). `git diff --exit-code --
CLAUDE.md` exits 0 (untouched). Ledger diff is pure addition (`git diff -- memory-bank/living-ledger.md`
shows zero removed lines from any existing entry).

---
*Phase: 10-run-memory-foundation-shadow-writes*
*Completed: 2026-08-25*
