---
phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration
plan: 01
subsystem: infra
tags: [smartsheet-python-sdk, pip, dependency-migration, mypy, pytest, billing-engine]

# Dependency graph
requires:
  - phase: 09 (engine modularization)
    provides: pipeline/ package + 709-line facade (generate_weekly_pdfs.py) that this plan's SDK surface targets
provides:
  - smartsheet-python-sdk 4.3.0 installed and smoke-verified against every in-use SDK symbol
  - Dead 3.x re-export workaround removed from generate_weekly_pdfs.py (D-04)
  - Gate 1 baseline updated to 177 names (authorized _exc_name removal)
  - Green six-gate harness + full pytest suite proof under 4.3.0
affects: [08-02 (requirements.txt pin lift + live-probe + rollout)]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - generate_weekly_pdfs.py
    - tests/golden/baseline_names.json

key-decisions:
  - "Installed smartsheet-python-sdk==4.3.0 directly via pip (not via requirements.txt, which still pins <4.0.0 until 08-02)"
  - "Removed generate_weekly_pdfs.py lines 20-46 (the 3.x smartsheet.smartsheet re-export shim) per D-04; kept line 18 (import smartsheet.exceptions as ss_exc) and pipeline/retry.py untouched"
  - "Updated tests/golden/baseline_names.json 178 -> 177 entries, removing exactly _exc_name (an import-time temp, never public API)"

patterns-established: []

requirements-completed: [SDK-01, SDK-02, SDK-03, SDK-04, SDK-06]

# Metrics
duration: 12min
completed: 2026-07-22
---

# Phase 08 Plan 01: SDK 4.3.0 Install + Dead Re-export Removal Summary

**smartsheet-python-sdk upgraded 3.9.0 -> 4.3.0 in the environment; dead 3.x `smartsheet.smartsheet` re-export shim deleted from the production billing engine; six-gate harness and full 1164-test pytest suite green with zero test/fixture changes.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-22T01:26:27Z
- **Completed:** 2026-07-22T01:37:41Z (execution) — SUMMARY finalized shortly after
- **Tasks:** 3 completed
- **Files modified:** 2 (`generate_weekly_pdfs.py`, `tests/golden/baseline_names.json`)

## Accomplishments

- `smartsheet-python-sdk==4.3.0` installed directly (`pip install`, not via `requirements.txt`); resolved version confirmed `4.3.0`; smoke-verified all four retryable exception classes (`RateLimitExceededError`, `UnexpectedErrorShouldRetryError`, `InternalServerError`, `ServerTimeoutExceededError`), the `smartsheet.smartsheet` submodule, and `smartsheet.models.sheet.Sheet` / `smartsheet.models.folder.Folder` resolve cleanly under 4.3.0.
- Removed the dead 3.x re-export workaround block (14-line comment + `import smartsheet.smartsheet as _ss_smartsheet_module` + `_exc_name` re-export loop + both `del` statements — 27 lines total) from `generate_weekly_pdfs.py`. Lines 17-18 (`import smartsheet`, `import smartsheet.exceptions as ss_exc`) and `pipeline/retry.py` are untouched.
- Updated `tests/golden/baseline_names.json` from 178 to 177 entries, removing exactly `_exc_name` (the authorized Gate 1 adjustment per D-04/T-08-02).
- Ran the full six-gate behavior-neutrality harness (`bash scripts/run_6_gates.sh`) under 4.3.0: **`=== ALL 6 GATES PASSED ===`**.
- Ran the full verbose pytest suite (`pytest tests/ -v`) under 4.3.0: **1164 passed, 130 subtests passed, 0 failed** — with zero test/fixture edits (only the golden baseline count file, as authorized).
- `requirements.txt` intentionally left unchanged (still `>=3.1.0,<4.0.0`) per the plan's ordering constraint — the pin lift is Plan 08-02.

## Task Commits

Each task was committed atomically:

1. **Task 1: Install SDK 4.3.0 into the env and smoke-verify every in-use symbol** — no commit (environment-only change; no repo files modified, confirmed via `git status --short`)
2. **Task 2: Remove the dead 3.x re-export block and update the Gate 1 baseline** - `b2e76bf` (fix)
3. **Task 3: Run the full six-gate harness and complete pytest suite under 4.3.0** — no commit (verification-only; `git status --short` clean after)

_Note: This plan has no separate plan-metadata commit — SUMMARY.md is committed as the final worktree commit per parallel-executor convention (STATE.md/ROADMAP.md excluded, owned by the orchestrator)._

## Six-Gate Harness Result (full output line)

```
=== Gate 1: AST import equality ===
PASS: all 177 baseline names present
=== Gate 2: Facade completeness ===
PASS: all 108 allowlist names resolve
=== Gate 3: pytest ===
1164 passed, 130 subtests passed in 12.85s
=== Gate 4: mypy delta ===
PASS: mypy delta neutral or improved (56 -> 58)
=== Gate 5: py_compile ===
PASS: py_compile clean
=== Gate 6: golden run_summary ===
PASS: run_summary.json structure matches baseline (21 keys)
=== ALL 6 GATES PASSED ===
```

## Full Pytest Result

```
1164 passed, 130 subtests passed in 10.45s
```
(run with `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` — same encoding posture `run_6_gates.sh` forces; see Issues Encountered below)

## Removed Block (exact diff)

```diff
 import smartsheet
 import smartsheet.exceptions as ss_exc
 
-# Upstream SDK workaround: smartsheet-python-sdk 3.8.0 raises an
-# AttributeError from smartsheet.smartsheet.Smartsheet._request_with_retry
-# whenever the API returns a retryable error (429, 5xx). At
-# smartsheet/smartsheet.py:303 it does
-# ``getattr(sys.modules[__name__], native.result.name)`` to look up the
-# exception class to raise, but that module's top-level imports only
-# expose ApiError / HttpError / UnexpectedRequestError. The retryable
-# exception classes (RateLimitExceededError, UnexpectedErrorShouldRetry-
-# Error, InternalServerError, ServerTimeoutExceededError, SystemMainte-
-# nanceError) live in smartsheet.exceptions and were never re-exported
-# into smartsheet.smartsheet, so the getattr fails and our retry
-# wrapper never gets the real exception. Re-export the missing names
-# here so the SDK's internal lookup succeeds. The ``if not hasattr``
-# guard makes this a no-op if the upstream SDK ever re-exports them.
-import smartsheet.smartsheet as _ss_smartsheet_module
-_exc_name = None
-for _exc_name in (
-    'RateLimitExceededError',
-    'UnexpectedErrorShouldRetryError',
-    'InternalServerError',
-    'ServerTimeoutExceededError',
-    'SystemMaintenanceError',
-):
-    if not hasattr(_ss_smartsheet_module, _exc_name) and hasattr(ss_exc, _exc_name):
-        setattr(_ss_smartsheet_module, _exc_name, getattr(ss_exc, _exc_name))
-del _ss_smartsheet_module
-del _exc_name
 from dotenv import load_dotenv
```

## Files Created/Modified

- `generate_weekly_pdfs.py` - removed the dead 3.x SDK re-export shim (27 lines); import surface now just `import smartsheet` + `import smartsheet.exceptions as ss_exc`
- `tests/golden/baseline_names.json` - dropped `_exc_name` (178 -> 177 entries), the Gate 1 frozen name-set adjustment authorized by D-04

## Decisions Made

- Installed 4.3.0 directly via `pip install "smartsheet-python-sdk==4.3.0"` rather than touching `requirements.txt`, exactly as the plan's critical ordering constraint requires (the `<4.0.0` pin stays until 08-02).
- No new dependency was introduced (first-party SDK already in production use), so no package-legitimacy checkpoint was required per the plan's threat model (T-08-SC).

## Deviations from Plan

None - plan executed exactly as written. Both authorized deletions (the 27-line re-export block, the single `_exc_name` baseline entry) match the plan's `<interfaces>` section byte-for-byte.

## Issues Encountered

- **Gate 4 (`scripts/check_mypy_delta.sh`) raw count moved 56 -> 58, masked by a pre-existing CRLF bug in `tests/golden/mypy_baseline_count.txt`.** Investigated by running `mypy` directly and diffing against `tests/golden/mypy_baseline.txt` with line numbers stripped: the actual type-error set is byte-identical (22 errors in 5 files, same messages) before and after this plan's changes. The +2 raw-line delta is exclusively 2 extra "annotation-unchecked" NOTE-level lines for `pipeline/orchestrate.py` (a file this plan never touched — confirmed via `git diff --stat`) plus a "checked 21 -> 22 source files" summary artifact, most likely because SDK 4.3.0 changes what mypy's import graph pulls in. Zero new type ERRORS. The CRLF byte in the checked-in baseline count file (pre-dating this plan) causes bash's `-gt` integer comparison to silently no-op inside an `if` condition (exempt from `set -e`), so Gate 4 always prints PASS on this Windows/Git-Bash environment regardless of the true comparison. This is a pre-existing tooling bug unrelated to the SDK migration — logged to `.planning/phases/08-smartsheet-python-sdk-4-0-0-compatibility-migration/deferred-items.md` per the executor SCOPE BOUNDARY rule (not fixed; out of this plan's authorized file list).
- **One full-suite pytest run failed transiently on `test_startup_banner_printed_once`** when run without first exporting `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` in the shell (a `UnicodeDecodeError` in the subprocess reader thread decoding the engine's emoji startup banner under Windows cp1252). Re-running with those two env vars set — exactly the posture `scripts/run_6_gates.sh` already forces for this documented reason (see CLAUDE.md / Living Ledger note on Windows cp1252 emoji banners) — reproduced a clean `1164 passed, 130 subtests passed, 0 failed`. Not a regression from this plan; a pre-existing Windows console-encoding environment condition.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SDK 4.3.0 is installed and proven behavior-neutral (six gates + full suite green); the dead 3.x facade shim is gone.
- `requirements.txt` still pins `>=3.1.0,<4.0.0` by design — Plan 08-02 lifts the pin to `==4.3.0`, adds the live read-only probe (D-05), and executes the D-06 rollout sequence.
- No blockers for 08-02.

---
*Phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration*
*Completed: 2026-07-22*
