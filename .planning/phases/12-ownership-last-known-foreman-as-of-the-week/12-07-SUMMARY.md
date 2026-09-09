---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 07
subsystem: billing-attribution-backfill
tags: [own-03, backfill, sentinel, regex, tdd]

# Dependency graph
requires:
  - phase: 12-ownership-last-known-foreman-as-of-the-week (12-06)
    provides: the live OWN-03 dry-run run that surfaced gap G-12-3 (Juan REJECT verdict)
provides:
  - "_extract_claimer_from_filename correctly handles the live hash-less public.artifacts filename shape, not just the legacy hash-suffixed shape"
  - "_build_apply_payload defensive client-side guard on proposed_value, mirroring the existing current_value guard"
affects: [12-06 (owner re-run), 12-08, 12-09, 12-10]

# Actuals (#2632)
actuals:
  tokens: 5984
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-branch filename suffix strip: hash-suffix match keeps legacy slicing behavior, else strip one trailing document extension via a closed extension-set regex, then reject any candidate still ending in one"
    - "Defensive client-side guard duplicated at the payload-build boundary (not just the discovery boundary) so a downstream bug in any source can never reach the RPC"

key-files:
  created: []
  modified:
    - scripts/backfill_claim_time_attribution.py
    - tests/test_backfill_claim_time_attribution.py

key-decisions:
  - "Extension-stripping regex restricted to a closed document-extension set (xlsx/xlsm/xls/csv/pdf/json) rather than a generic trailing-suffix pattern, so an initialled human name is never truncated"
  - "The sentinel check itself is NOT duplicated in _extract_claimer_from_filename -- it only strips the extension and rejects residual-extension candidates; billing_audit.writer.is_sentinel_claimer (called downstream in _resolve_single_name) remains the single sentinel classifier"
  - "Task 2 required no production code change -- Task 1's extraction fix already made every parameterized source-3 case pass on the hash-less shape; Task 2 is a pure test-coverage rebuild that pins the behavior structurally"

requirements-completed: [OWN-03]

coverage:
  - id: D1
    description: "A live hash-less sentinel filename (WR_<wr>_WeekEnding_<mmddyy>_User_Unknown_Foreman.xlsx) never produces a source-3 proposal"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#test_source_3_hashless_sentinel_filename_yields_no_proposal"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#test_extract_claimer_rejects_residual_extension"
        status: pass
    human_judgment: false
  - id: D2
    description: "A live hash-less filename carrying a real name still resolves to the desanitized name (source backfill_artifacts, name_fidelity desanitized)"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#test_source_3_hashless_real_name_resolves"
        status: pass
    human_judgment: false
  - id: D3
    description: "The pre-existing hash-suffixed filename shape behaves exactly as before (no regression)"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#test_extract_claimer_preserves_hash_suffix_behavior"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#SourcesOneTwoThreeTests (subTest shape=hash_suffixed, all 4 parameterized cases)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both filename shapes are exercised by every source-3 case (single-name, conflict, subcontractor helper token, helper-vs-reduced-sub-helper), plus a hash-less two-sentinel-names case resolving to silence not conflict"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#SourcesOneTwoThreeTests (7 tests, 8 subtests, -k source_3)"
        status: pass
    human_judgment: false
  - id: D5
    description: "_build_apply_payload refuses a sentinel or extension-bearing proposed_value, so --apply cannot send such a value to the RPC even if the report contains one"
    requirement: "OWN-03"
    verification:
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#test_apply_payload_drops_sentinel_proposed_value"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#test_apply_payload_drops_extension_bearing_proposed_value"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_claim_time_attribution.py#test_apply_payload_keeps_real_proposed_value"
        status: pass
      - kind: unit
        ref: "tests/test_own03_backfill_sql_contract.py#test_build_apply_payload_keys_match_sql_column_list"
        status: pass
    human_judgment: false

# Metrics
duration: ~15min
completed: 2026-09-04
status: complete
---

# Phase 12 Plan 07: Fix hash-less filename extraction and add apply-payload guard (G-12-3) Summary

**Fixed `_extract_claimer_from_filename` to strip a trailing document extension (not just a hash suffix) before the sentinel check runs, and added a defensive `proposed_value` guard to `_build_apply_payload` — closing the source-3 half of gap G-12-3.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-09-04T04:33:57Z
- **Tasks:** 3 completed
- **Files modified:** 2

## Accomplishments

- `_extract_claimer_from_filename` now branches on whether the pipeline's
  `_<6hex>.xlsx` hash suffix is present: when present, behavior is byte-for-byte
  unchanged; when absent — the live shape written by
  `scripts/publish_artifacts_to_supabase.py::_parse_stable` — it strips one
  trailing document extension (`xlsx|xlsm|xls|csv|pdf|json`, case-insensitive)
  instead, then rejects any candidate that still ends in one after that strip.
- Before the fix: `_extract_claimer_from_filename("...User_Unknown_Foreman.xlsx", "_User_")`
  returned `"Unknown_Foreman.xlsx"` — the un-stripped extension defeated
  `is_sentinel_claimer`'s normalization, so the literal placeholder string was
  proposed as a real name. This is the defect that produced 4,070 of 4,762 live
  proposals as the placeholder in the 12-06 dry-run Juan rejected.
- After the fix: the same input returns `"Unknown_Foreman"`, which
  `is_sentinel_claimer` correctly classifies as a sentinel once desanitized
  (`"unknown foreman"`), so `_resolve_single_name` skips it and the row falls
  through to unresolved/blank — never `status="proposed"`.
- A hash-less filename carrying a real name (`..._User_Avery_Example.xlsx`)
  still resolves to `"Avery Example"` (`source=backfill_artifacts`,
  `name_fidelity=desanitized`), and the pre-existing hash-suffixed shape
  (`..._User_Avery_Example_aabbcc.xlsx`) is completely unaffected.
- All four pre-existing source-3 tests (single-name resolve, two-name conflict,
  subcontractor helper token, helper-vs-reduced-sub-helper) now run via
  `subTest` against BOTH filename shapes, so the live shape can never again go
  untested. A new test pins that two hash-less sentinel filenames resolve to
  silence rather than a two-placeholder conflict — the 1,066-row conflict class
  the live report actually produced.
- `_build_apply_payload` now also drops any `proposed`-status row whose
  `proposed_value` is a sentinel or still carries a document extension, in
  addition to the existing `current_value` guard — defense in depth so the
  `--apply` write path can never send a placeholder-shaped value to the RPC
  even if some future source leaks one. Skipped rows are counted, never
  logged individually (report values are claimer PII).

## Task Commits

Each task was committed atomically (TDD RED → GREEN per task):

1. **Task 1: End-to-end — a live hash-less sentinel filename must produce no proposal**
   - `8d27e36` (test) — 4 new tests added; confirmed RED (3/4 failed; the 4th pins
     unchanged pre-existing behavior).
   - `8dba6b6` (fix) — `_FILENAME_DOC_EXTENSION_RE` constant + rewritten
     `_extract_claimer_from_filename` body; confirmed GREEN (all 4 pass, full
     file suite 56/56 pass).
2. **Task 2: Rebuild the source-3 fixtures on the shape production actually stores**
   - `d4e05eb` (test) — parameterized the 4 existing source-3 tests over both
     filename shapes via `subTest`; added
     `test_source_3_hashless_two_sentinel_names_are_not_a_conflict`. No
     production code change required — Task 1's fix already covered every
     case (57/57 file tests pass, 10 subtests).
3. **Task 3: Client-side proposed-value guard in the apply payload builder**
   - `5ec9757` (test) — 3 new tests added to `ApplyPathTests`; confirmed RED
     (2/3 failed on the drop-cases, the keep-case already passed).
   - `4bdd3ce` (fix) — proposed-value guard added to `_build_apply_payload`
     with aggregate-only WARNING logging; confirmed GREEN (5/5 pass), SQL
     contract test still passes (20/20), full suite green (2107 passed, 1
     pre-existing skip, 416 subtests).

## Files Created/Modified

- `scripts/backfill_claim_time_attribution.py` — added `_FILENAME_DOC_EXTENSION_RE`;
  rewrote `_extract_claimer_from_filename` to branch on hash-suffix presence
  and reject residual-extension candidates; added the `proposed_value` guard
  (with aggregate WARNING) to `_build_apply_payload`. `git diff` confirms the
  script's hunks are confined to those three symbols — no other function body
  touched.
- `tests/test_backfill_claim_time_attribution.py` — 4 new Task 1 tests, 2 new
  shape-builder helpers + 4 parameterized existing tests + 1 new test (Task 2),
  3 new Task 3 tests. 60 tests / 10 subtests in this file, all passing.

## Decisions Made

- Extension-stripping regex is a closed document-extension set, not a generic
  trailing-suffix pattern — avoids truncating an initialled human name (e.g.
  "Avery Jr").
- The sentinel classification stays entirely inside
  `billing_audit.writer.is_sentinel_claimer`; this plan only removes the
  extension that was defeating that existing check, and adds one more call
  site to it (the new `proposed_value` guard) — no second sentinel list or
  sanitizer was introduced anywhere.
- Task 2 needed zero production code changes because Task 1's fix operates
  per-row inside `_extract_claimer_from_filename`, independent of variant/role
  — every parameterized case (including the new hash-less two-sentinel-names
  case) already passed once Task 1 landed. Verified explicitly by running the
  Task 2 tests before writing any additional script code.

## Deviations from Plan

None - plan executed exactly as written. (One process note: the module
constant was briefly added to the script before the RED tests were written;
this was caught and reverted before any test was run, so the four Task 1
tests were confirmed genuinely RED — 3/4 failing, the residual-extension
rejection and hash-less proposals both still broken — before the real fix
landed.)

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The source-3 half of gap G-12-3 is closed: a live hash-less sentinel
  filename can no longer produce a proposed value, and the apply-payload
  builder has a second, independent guard against ever writing one.
- No `--apply` run and no live Supabase write occurred in this plan (all
  tests run against the fixture-driven fake Supabase client per the plan's
  hard prohibitions).
- `billing_audit/writer.py`, `generate_weekly_pdfs.py`, and `pipeline/*` were
  not touched, per the plan's file-scope prohibitions.
- 12-06's re-run (owner-gated) can now proceed once the remaining gap plans
  (12-08, 12-09, 12-10) are also closed, per STATE.md's recorded next step.

## Self-Check: PASSED

- `scripts/backfill_claim_time_attribution.py` exists on disk.
- `tests/test_backfill_claim_time_attribution.py` exists on disk.
- All 5 task commits (`8d27e36`, `8dba6b6`, `d4e05eb`, `5ec9757`, `4bdd3ce`)
  found via `git log --oneline --all`.
- All plan-level `<verification>` commands re-run and passing: file suite
  60/60 (10 subtests), `tests/` full suite 2107 passed / 1 pre-existing skip
  / 416 subtests, `py_compile` clean, `git diff --stat` shows exactly the
  two files named in `files_modified`, script diff hunks confined to
  `_FILENAME_DOC_EXTENSION_RE`, `_extract_claimer_from_filename`, and
  `_build_apply_payload`.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-04*
