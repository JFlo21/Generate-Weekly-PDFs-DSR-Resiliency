---
phase: quick-260709-oa7
plan: 01
subsystem: infra
tags: [smartsheet, retry, sentry, cron, observability, resiliency]

requires: []
provides:
  - "smartsheet_call_with_retry() retries transient HTTP 5xx wrapped as a generic code-0 ApiError"
  - "Sentry cron monitor checkin_margin raised from 5 to 60 minutes"
affects: [pipeline-discovery, pipeline-fetch, sentry-cron-monitoring]

tech-stack:
  added: []
  patterns:
    - "ApiError retry guard widened to check BOTH result.code (_RETRYABLE_API_CODES) and result.status_code (_RETRYABLE_HTTP_STATUS) before fail-fast"

key-files:
  created: []
  modified:
    - pipeline/retry.py
    - tests/test_smartsheet_retry.py
    - pipeline/observability.py
    - tests/test_cron_monitor_config.py

key-decisions:
  - "Retryable HTTP statuses fixed at {500, 502, 503, 504} per locked diagnosis — no new env var, additive frozenset constant mirroring _RETRYABLE_API_CODES"
  - "checkin_margin raised to 60 (not a smaller value) to absorb the full observed 25-57 min GitHub Actions scheduling delay while staying under the 2h run interval"

requirements-completed: [GENERATE-WEEKLY-EXCEL-89, GENERATE-WEEKLY-EXCEL-6V]

duration: 12min
completed: 2026-07-09
---

# Quick Task 260709-oa7: Sentry 503 Retry Gap + Cron Margin Summary

**Widened `smartsheet_call_with_retry()`'s generic-ApiError branch to also retry transient HTTP 5xx (500/502/503/504) wrapped as a code-0 ApiError, and raised the Sentry cron `checkin_margin` from 5 to 60 minutes to match GitHub Actions' observed scheduling delay.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- `pipeline/retry.py`: added `_RETRYABLE_HTTP_STATUS` frozenset `{500, 502, 503, 504}` and `_http_status_code()` extractor; the `except ss_exc.ApiError` branch now re-raises only when the error is neither a retryable result code NOR a retryable HTTP status — fixing the gap that dropped source sheet "Resiliency Promax Database Backup 59" with 0 rows on a transient 503.
- `pipeline/observability.py`: `_build_cron_monitor_config()["checkin_margin"]` raised 5 → 60, ending the 78 false missed-check-in Sentry events / 14 days caused by GitHub Actions' 25-57 min scheduling jitter.
- Fail-fast preserved: a permanent code (1006) with a 4xx status (404) still raises on attempt 1 with zero backoff and zero sleep; `max_total_sleep` ceiling and exhaustion re-raise untouched.

## Task Commits

Each task was committed atomically, TDD RED confirmed before each GREEN implementation:

1. **Task 1: Retry Smartsheet HTTP 5xx wrapped as generic ApiError (GENERATE-WEEKLY-EXCEL-89)** - `1791246` (fix)
2. **Task 2: Raise Sentry cron checkin_margin 5 to 60 (GENERATE-WEEKLY-EXCEL-6V)** - `7469204` (fix)

_No separate `test:`/`feat:` split commits — each task's test additions and source fix were committed together per the plan's TDD instruction (write RED, confirm failure, then implement GREEN, then commit once as a single `fix:` per task)._

## Files Created/Modified
- `pipeline/retry.py` - `_RETRYABLE_HTTP_STATUS` constant, `_http_status_code()` extractor, widened `ApiError` guard, updated design-contract docstring
- `tests/test_smartsheet_retry.py` - `_api_error_with_status()` helper + 5 new tests (503 retry, 500/502/504 parametrized retry, permanent-code+4xx fail-fast, exhaustion re-raise)
- `pipeline/observability.py` - `checkin_margin: 5` → `60` with inline evidence comment
- `tests/test_cron_monitor_config.py` - `test_runtime_and_threshold_fields` assertion updated to `checkin_margin == 60`

## Decisions Made
- Kept the retryable-status set exactly as specified in the plan (`{500, 502, 503, 504}`) — no attempt to widen further (e.g. 429 is already handled by the separate `RateLimitExceededError` branch with its own long backoff schedule, so it was correctly left out).
- Log `kind` tag changed from `f"ApiError {code}"` to `f"ApiError code={code} http={status}"` so retry log lines identify a 5xx distinctly from a 4000 code retry — purely additive to the log string, no behavior change.

## Deviations from Plan

None - plan executed exactly as written. Both tasks followed the RED→GREEN TDD sequence specified: new tests were added and confirmed failing before the source change, then the minimal additive fix was made and tests re-run green.

## Issues Encountered

**Full-suite gate — one pre-existing, out-of-scope failure (not fixed, per file-scope restriction):**
`tests/test_entrypoint_no_double_import.py::TestEntrypointNoDoubleImport::test_startup_banner_printed_once` fails with `TypeError: unsupported operand type(s) for +: 'NoneType' and 'NoneType'` when run on this Windows host. Root cause: the test spawns `generate_weekly_pdfs.py` as a subprocess and captures output in text mode; a `subprocess.py` reader thread hits `UnicodeDecodeError: 'charmap' codec can't decode byte ...` because the parent's `subprocess.run(text=True)` decodes the child's UTF-8 emoji-banner bytes using the Windows cp1252 locale default (the test's `PYTHONIOENCODING=utf-8` only affects the child's own stdout encoding, not the parent's decode). This is a documented pre-existing Windows-only console-encoding quirk (`memory-bank/living-ledger.md` "Oracle carry-forward" note, line ~4062, already flags `PYTHONUTF8` forcing for the same cp1252-vs-emoji-banner class of issue) — unrelated to `pipeline/retry.py`, `pipeline/observability.py`, or either targeted test file, and outside this plan's explicit file-scope restriction (`pipeline/retry.py`, `pipeline/observability.py`, `tests/test_smartsheet_retry.py`, `tests/test_cron_monitor_config.py`). Not auto-fixed per the deviation-rules scope boundary. `tests/test_smartsheet_retry.py` (17/17) and `tests/test_cron_monitor_config.py` (5/5) — the two targeted files — are fully green; the broader suite is 1163 passed / 1 pre-existing environmental failure.

## User Setup Required

None - no external service configuration required. Both fixes are pure code changes; no new env vars, no dashboard steps.

## Next Phase Readiness
- Both Sentry issues (GENERATE-WEEKLY-EXCEL-89, GENERATE-WEEKLY-EXCEL-6V) have a corresponding `Fixes` reference in their commit body for auto-resolve on merge to `master`.
- Recommend a maintainer separately investigate the pre-existing `test_entrypoint_no_double_import.py` Windows cp1252/UTF-8 subprocess-decode failure (unrelated to this task) — likely fix is `errors="replace"` or explicit `encoding="utf-8"` on `subprocess.run()` in that test, but that is out of scope here.

---
*Phase: quick-260709-oa7*
*Completed: 2026-07-09*

## Self-Check: PASSED

All 5 claimed artifacts found on disk (`pipeline/retry.py`, `tests/test_smartsheet_retry.py`,
`pipeline/observability.py`, `tests/test_cron_monitor_config.py`, this SUMMARY.md) and both
commit hashes (`1791246`, `7469204`) verified present in `git log`.
