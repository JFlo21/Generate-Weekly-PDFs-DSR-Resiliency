---
phase: 03-supabase-data-layer-foundation
plan: "02"
subsystem: supabase-publish
tags: [tdd, supabase, publish, artifacts, ci, python, fail-isolated]
dependency_graph:
  requires:
    - 03-01 (portal_schema.sql with public.artifacts UNIQUE sha256 constraint live)
    - billing_audit/client.py (get_client / with_retry / _classify_postgrest_error)
    - scripts/generate_artifact_manifest.py (calculate_file_hash / parse_excel_filename)
  provides:
    - scripts/publish_artifacts_to_supabase.py (additive CI publish step)
    - tests/test_publish_artifacts_to_supabase.py (34 mocked unit tests)
  affects:
    - 03-03 (workflow step that invokes this script)
    - Phase 05 (read path depends on artifacts rows being present)
tech_stack:
  added:
    - scripts/publish_artifacts_to_supabase.py (new Python script, supabase==2.9.1)
  patterns:
    - TDD: RED (test(03-02) commit) -> GREEN (feat(03-02) commit)
    - Reuse: get_client/with_retry (billing_audit.client) + calculate_file_hash/parse_excel_filename (scripts.generate_artifact_manifest)
    - Fail-isolated: try/except per file -> Sentry capture -> WARNING log -> GITHUB_STEP_SUMMARY -> exit 0 (D-06)
    - Idempotent upsert: on_conflict="sha256" (D-08)
    - PII discipline: WARNING contains only type(exc).__name__ + count, never raw filename
key_files:
  created:
    - scripts/publish_artifacts_to_supabase.py
    - tests/test_publish_artifacts_to_supabase.py
  modified: []
decisions:
  - "Separate normalize_variant() kept in publish script (not extending parse_excel_filename) per plan: lower blast-radius, zero change to shared manifest module"
  - "supabase==2.9.1 used as-is (already installed/proven in billing_audit); storage upload uses file_options={'upsert': 'true'} string form confirmed for 2.9.x"
  - "_parse_stable() wrapper delegates to parse_excel_filename for positions 1/3 only, discarding fragile tail positions (timestamp/data_hash break for variant-suffixed filenames)"
  - "on_conflict='sha256' for idempotent upsert; variant TEXT (no DB CHECK) mirrors billing_audit.schema.sql L97-104 precedent"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-29"
  tasks_completed: 2
  files_created: 2
---

# Phase 03 Plan 02: publish_artifacts_to_supabase — Fail-Isolated CI Publish Script Summary

**One-liner:** Mocked TDD test suite + additive CI publish script that scans generated_docs, uploads WR_*.xlsx to Supabase Storage bucket `excel-artifacts`, and upserts idempotent `public.artifacts` metadata rows on `sha256`, wrapped in loud-but-non-fatal failure isolation (D-06).

## What Was Built

`scripts/publish_artifacts_to_supabase.py` (434 lines) and `tests/test_publish_artifacts_to_supabase.py` (634 lines, 34 tests, all GREEN) implement the write path for DATA-02/DATA-03.

The script is a standalone additive step that runs after the billing pipeline exits. It scans `generated_docs/` (root + `YYYY-MM-DD` week subfolders) for `WR_*.xlsx` files, uploads each to the private `excel-artifacts` Storage bucket, and upserts a metadata row into `public.artifacts` keyed on `sha256` for idempotent re-runs.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (failing tests) | `6bb9793` | test(03-02): 34 tests fail, implementation absent |
| GREEN (passing tests) | `a67c1f7` | feat(03-02): 34 tests pass, full suite not regressed |
| REFACTOR | N/A | No refactor needed; implementation clean on first pass |

## Tasks

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | RED: write mocked failing tests | `6bb9793` | tests/test_publish_artifacts_to_supabase.py |
| 2 | GREEN: implement script + fix test date expectation | `a67c1f7` | scripts/publish_artifacts_to_supabase.py, tests/test_publish_artifacts_to_supabase.py |

## Key Design Decisions

### normalize_variant (7-way precedence chain)
Mirrors `generate_weekly_pdfs.py` L2834 precedence: most-specific token checked first. The two hybrid forms (`_AEPBillable_Helper_`, `_ReducedSub_Helper_`) are checked before their component forms to prevent the `_Helper_` check from matching a hybrid filename.

### parse_excel_filename reuse strategy
The existing `parse_excel_filename()` is only used for positions 1 (WR) and 3 (MMDDYY), which are stable across all 7 variant filename forms. A `_parse_stable()` wrapper discards the fragile `timestamp`/`data_hash` tail positions. `variant` is derived via `normalize_variant()` and `sha256` is computed from file bytes via `calculate_file_hash()` — never from the filename's embedded hash token (which is absent in clean-filename mode).

### supabase==2.9.1 call shapes (Wave 0 verify)
Confirmed against the installed version:
- Storage upload: `client.storage.from_("excel-artifacts").upload(path, file, file_options={"upsert": "true"})` — `"true"` as a string is the 2.9.x `file_options` keyword.
- Metadata upsert: `client.table("artifacts").upsert(row, on_conflict="sha256").execute()` — `on_conflict` as a keyword argument is valid in 2.9.1 via postgrest-py.

### Failure isolation (D-06)
`main()` is exception-safe end-to-end:
1. `get_client()` returns `None` → `_emit_summary(WARNING)` + return (no raise).
2. Per-file exception in `publish_file()` → Sentry `capture_exception` + `logging.warning` with only `type(exc).__name__` + count (no PII filename in message body, Pitfall D / T-03-pii-sentry).
3. Final `_emit_summary` writes `published=N failed=M` to both `$GITHUB_STEP_SUMMARY` and the log.
4. Process exits 0 regardless of outcome (defense-in-depth atop the workflow's `continue-on-error: true`).

## Test Coverage

34 tests across 7 test classes:

| Class | Tests | What it covers |
|-------|-------|----------------|
| TestNormalizeVariant | 11 | All 9 filename forms + 2 precedence cases + all 7 values reachable |
| TestParsePositional | 4 | Positions 1/3 stable for AEPBillable_Helper names; non-WR/short returns None |
| TestSha256FromBytes | 2 | sha256 matches hashlib.sha256(bytes); differs from filename token |
| TestWeekEndingIso | 4 | Known conversions; malformed input raises/returns None |
| TestUpsertPayloadIdempotent | 3 | 9 D-09 keys present; on_conflict='sha256'; storage_path format |
| TestSecretNotLogged | 1 | SUPABASE_SERVICE_ROLE_KEY never in log output (T-03-secret) |
| TestFailureIsolation | 5 | None client no-raise; WARNING emitted; GITHUB_STEP_SUMMARY written; upload exception caught; Sentry called |
| TestNoPiiInSentryBody | 1 | RuntimeError type name in log; raw filename absent (T-03-pii-sentry) |
| TestCollectXlsxFiles | 3 | Root scan; YYYY-MM-DD subfolder scan; nonexistent folder -> empty |

All 34 pass. Full suite: 1016 passed, 16 pre-existing failures (unchanged from before this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_another_date expected ISO date**
- **Found during:** GREEN phase (1 test failed after initial run)
- **Issue:** `"082425"` with `strptime("%m%d%y")` yields `"2025-08-24"` (year `25` = 2025), not `"2024-08-24"`. The test had the wrong expected year.
- **Fix:** Updated the expected value to `"2025-08-24"` and added a comment explaining Python's `%y` interpretation rule (00-68 → 2000-2068).
- **Files modified:** `tests/test_publish_artifacts_to_supabase.py`
- **Commit:** `a67c1f7` (bundled in GREEN commit)

## Grep Acceptance Criteria

All gates verified:

| Grep | Result |
|------|--------|
| `from billing_audit.client import` in script | Line 56 |
| `calculate_file_hash` in script | Lines 58, 281 |
| `def normalize_variant` in script | Line 114 |
| `on_conflict="sha256"` in script | Line 336 |
| No `CHECK` constraint code in script | Correct (only comments) |
| `class TestNormalizeVariant` in tests | Present |
| min_lines >= 120 for both files | 434 (script), 634 (tests) |

## Stub Tracking

No stubs. The script reads real files from disk (or skips gracefully), calls real Supabase client methods (mocked in tests), and computes real sha256 hashes. No hardcoded empty values flow to UI rendering.

## Threat Flags

No new threat surface introduced beyond what is already in the plan's `<threat_model>`. All four T-03-* mitigations implemented:

| Threat | Mitigation | Test |
|--------|-----------|------|
| T-03-secret | Key read inside `get_client()`; never in log output | `test_secret_not_logged` |
| T-03-pii-sentry | WARNING contains only `type(exc).__name__` + count | `test_no_pii_in_warning_log` |
| T-03-publish-dos | Internal try/except -> Sentry -> summary -> exit 0 | `test_failure_isolation` (5 tests) |
| T-03-sqli | supabase-py parameterizes upsert dict; no string-built SQL | structural (no string interpolation in upsert) |
| T-03-variant-coerce | Unknown token -> Sentry capture + still insert (no hard DB CHECK drop) | structural (guard in publish_file) |

## Self-Check: PASSED

### Created files exist:
- `scripts/publish_artifacts_to_supabase.py`: FOUND
- `tests/test_publish_artifacts_to_supabase.py`: FOUND

### Commits exist:
- `6bb9793` (RED): FOUND
- `a67c1f7` (GREEN): FOUND

### Tests pass:
- `pytest tests/test_publish_artifacts_to_supabase.py -v`: 34 passed
- `pytest tests/ -q`: 1016 passed, 16 pre-existing failures (unchanged)
