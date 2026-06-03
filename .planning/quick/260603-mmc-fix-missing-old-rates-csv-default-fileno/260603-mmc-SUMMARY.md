---
phase: quick-260603-mmc
plan: 01
subsystem: python-billing-pipeline
tags: [sentry, rate-csv, pii, tdd, benign-skip, monitor-config]
dependency_graph:
  requires: []
  provides: [optional-rate-csv-skip, sentry-monitor-corrected, pii-safe-run-tags]
  affects: [generate_weekly_pdfs.py, tests/test_subcontractor_pricing.py, memory-bank/living-ledger.md]
tech_stack:
  added: []
  patterns: [os.path.isfile guard, sentry fingerprinted except, assertNoLogs TDD]
key_files:
  created: []
  modified:
    - generate_weekly_pdfs.py
    - tests/test_subcontractor_pricing.py
    - .planning/quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/verify_sentry_mods.py
    - memory-bank/living-ledger.md
decisions:
  - "Existence guard goes in loaders only (not _sanitize_csv_path) to preserve CodeQL taint pattern and the one-line revert path"
  - "Comment-aware check in verifier: old wr_filter key documented in a comment is not a leak; grep non-comment lines only"
metrics:
  duration: ~12 minutes
  completed: 2026-06-03
---

# Quick Task 260603-mmc Summary

**One-liner:** Benign `os.path.isfile()` skip replaces recurring Sentry ERROR for missing optional rate CSV; stale cron monitor_config corrected and WR list PII leak closed.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | TDD - make missing rate CSV a benign skip | `094a5b0` | generate_weekly_pdfs.py, tests/test_subcontractor_pricing.py |
| 2 | Correct stale cron monitor_config + PII-safe run-mode tags | `f5c2948` | generate_weekly_pdfs.py, verify_sentry_mods.py |
| 3 | Append dated Living Ledger entry | `d10aded` | memory-bank/living-ledger.md |

## What Changed Per File

### `generate_weekly_pdfs.py`

**`load_contract_rates` (was :1432):**
- Added `os.path.isfile(filepath)` guard before `try:/open()`. When the file is absent: `logging.info("Rate CSV not present, skipping load: ...")` + `sentry_add_breadcrumb(level="info", data={"path_present": False})` + `return rates`. No `logging.error`, no Sentry event.
- Added `sentry_capture_with_context(e, ..., fingerprint=["rate-csv-load-failure", "load_contract_rates"])` with `_redact_exception_message(e)` in `context_data` inside the existing `except Exception` block for genuinely malformed files.

**`build_cu_to_group_mapping` (was :1493):**
- Symmetric `os.path.isfile(old_csv_path)` guard with identical INFO/breadcrumb/return pattern.
- Fingerprinted except: `fingerprint=["rate-csv-load-failure", "build_cu_to_group_mapping"]`.

**`_sentry_cron_checkin_start` (was :7890):**
- Corrected stale `monitor_config`: `"30 17 * * 1"` / `America/Phoenix` / `max_runtime 120` replaced with `"0 13,15,17,19,21,23,1 * * 1-5"` / `America/Chicago` / `max_runtime 180` (matches real production weekday schedule and workflow `timeout-minutes: 180`).

**Sentry init tag block (was :1391):**
- Added 3 PII-safe run-mode tags: `res_grouping_mode` (fixed enum), `wr_filter_active` (`str(bool(WR_FILTER))` — True/False string, never the WR list), `force_generation` (bool).

**`set_context("configuration")` (was :1397):**
- Replaced `"wr_filter": WR_FILTER` (raw WR list — row-PII) with `"wr_filter_active": bool(WR_FILTER)` + `"wr_filter_count": len(WR_FILTER)`. Explanatory comment preserved inline. All other keys unchanged.

### `tests/test_subcontractor_pricing.py`

- Added `TestLoadContractRates.test_missing_file_is_benign_not_error`: `assertNoLogs(level="ERROR")` confirms absent CSV emits no ERROR log and returns `{}`.
- Added `TestBuildCuToGroupMapping.test_missing_file_is_benign_not_error`: same pattern for `build_cu_to_group_mapping`.
- Existing `:43` and `:759` `test_missing_file_returns_empty` tests unchanged and still passing.

### `verify_sentry_mods.py`

- Extended with 3 PART D assertions: raw WR list gone from `set_context` (comment-aware line check), `wr_filter_active bool(WR_FILTER)` present, `wr_filter_count len(WR_FILTER)` present.

### `memory-bank/living-ledger.md`

- Appended `[2026-06-03 16:48]` entry documenting: optional rate CSV, root cause, blast radius, fingerprinted except, corrected monitor_config, PII-safe tags, WR leak closure, preserved guardrails.

## TDD RED -> GREEN Evidence

**RED run (before implementation):**
```
FAILED tests/test_subcontractor_pricing.py::TestLoadContractRates::test_missing_file_is_benign_not_error
  AssertionError: Unexpected logs found: ["ERROR:root:Failed to load rates from /nonexistent/path.csv: [Errno 2] No such file or directory: '/nonexistent/path.csv'"]
FAILED tests/test_subcontractor_pricing.py::TestBuildCuToGroupMapping::test_missing_file_is_benign_not_error
  AssertionError: Unexpected logs found: ["ERROR:root:Failed to build CU-to-group mapping from /nonexistent/old.csv: [Errno 2] No such file or directory: '/nonexistent/old.csv'"]
2 failed, 217 deselected in 1.61s
```

**GREEN run (after existence guard):**
```
tests/test_subcontractor_pricing.py::TestLoadContractRates::test_missing_file_is_benign_not_error PASSED
tests/test_subcontractor_pricing.py::TestLoadContractRates::test_missing_file_returns_empty PASSED
tests/test_subcontractor_pricing.py::TestBuildCuToGroupMapping::test_missing_file_is_benign_not_error PASSED
tests/test_subcontractor_pricing.py::TestBuildCuToGroupMapping::test_missing_file_returns_empty PASSED
5 passed, 214 deselected in 0.74s
```

## Full pytest Result

```
1027 passed, 29 skipped in 6.03s
```
(0 failures — pre-push gate passes)

## py_compile Result

```
python -m py_compile generate_weekly_pdfs.py  -> SYNTAX OK
```

## verify_sentry_mods.py --with-ledger Result

```
PASS - corrected cron schedule present
PASS - corrected timezone present
PASS - stale timezone removed
PASS - stale Monday-only schedule removed
PASS - run-mode tag res_grouping_mode added
PASS - wr_filter_active is a BOOL (no raw WR list leak)
PASS - force_generation tag added
PASS - existing run-summary set_context preserved (not re-added)
PASS - existence guard added to loaders
PASS - benign skip path uses INFO, not error, for absent CSV
PASS - fingerprinted rate-load failure
PASS - redaction used for exception text in context
PASS - sentry-sdk floor NOT bumped / no banned APIs
PASS - raw WR list no longer in set_context configuration (PII leak closed)
PASS - wr_filter_active bool present in configuration context
PASS - wr_filter_count int present in configuration context
PASS - Living Ledger has a dated entry mentioning the rate CSV change

ALL PASS (17/17)
```

## Deviations from Plan

**1. [Rule 1 - Bug] Verifier comment-detection edge case**
- **Found during:** Task 2 PART D verification
- **Issue:** The explanatory comment `# was: "wr_filter": WR_FILTER` left in the source as documentation caused the verifier's literal string check `'"wr_filter": WR_FILTER' not in s` to falsely report FAIL even though the actual dict key was removed. The comment is correct and intentional per the plan's intent to document the change.
- **Fix:** Replaced the literal string check with a comment-aware line scan: `not any(line that is not a comment contains '"wr_filter": WR_FILTER')`.
- **Files modified:** `verify_sentry_mods.py`
- **Commit:** `f5c2948`

## Known Stubs

None — no placeholder values, no hardcoded empty arrays flowing to UI, no TODO/FIXME introduced.

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced. The `set_context` / `set_tag` trust boundary is the only Sentry-facing surface, and the T-mmc-01 through T-mmc-05 mitigations in the plan's threat model are all applied.

## Self-Check: PASSED

- `094a5b0` exists in git log: confirmed
- `f5c2948` exists in git log: confirmed
- `d10aded` exists in git log: confirmed
- `generate_weekly_pdfs.py` modified: confirmed (os.path.isfile guard in both loaders, fingerprinted except, corrected monitor_config, new tags, wr_filter redaction)
- `tests/test_subcontractor_pricing.py` modified: confirmed (2 new assertNoLogs tests)
- `memory-bank/living-ledger.md` modified: confirmed (new bottom entry with [2026-06-03 16:48])
- All 17 verifier checks: PASS
- Full pytest: 1027 passed, 0 failed

---

## Plan 02

**One-liner:** TDD-enforced PII-safe Sentry telemetry: run-level KPIs on root transaction, counts-only failure attachment, guarded structured-log milestone calls; sentry-sdk floor raised to 2.54.0.

### Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD - pure PII-safe helpers (KPIs, snapshot, log wrapper) | `941021f` | `generate_weekly_pdfs.py`, `tests/test_subcontractor_pricing.py` |
| 2 | Wire helpers into main() - root-txn KPIs (#6), failure attachment (#5), milestone logs (#7) | `1a33e14` | `generate_weekly_pdfs.py`, `requirements.txt` |
| 3 | Living Ledger entry | `d8a1121` | `memory-bank/living-ledger.md` |

### What Was Built

**Helper A - `_build_run_kpis`** (pure, after `sentry_capture_message_with_context`): Returns a flat `dict[str, int | float]` with 10 KPI fields plus a derived `groups_per_minute` throughput (`0.0` on zero duration — no `ZeroDivisionError`). All values are `int | float`; no strings possible, guaranteeing no PII leakage via `set_data`.

**Helper B - `_build_run_context_snapshot`** (pure): Returns counts/booleans/`error_type` class name only. Designed for `scope.add_attachment` which bypasses `before_send_log`. Tests assert no WR token, no `$`, no foreman name in serialised JSON.

**Helper C - `_sentry_log_event`** (guarded): Wraps `sentry_sdk.logger` with three no-op gates (no DSN, no `logger` attribute on older SDK, internal `try/except` swallow) and a module-level comment: "ONLY pass non-PII scalars — this path BYPASSES before_send_log".

**Wired into main():**
- `#6` SUCCESS path: `_build_run_kpis` loop → `_txn.set_data` for each KPI, guarded by `if _txn:`, placed immediately before `_txn.set_status("ok")`.
- `#7` Milestone logs: `_sentry_log_event` at run-start (after `_txn` init, `test_mode`/`github_actions` booleans) and run-complete (after #6 KPI loop, aggregate counts). Zero calls in per-group loops.
- `#5` FAILURE path: `_build_run_context_snapshot` → `scope.add_attachment(bytes=json.dumps(...), filename="run-context.json")` before `sentry_capture_with_context`, wrapped in `try/except: pass` — can never mask the real exception.

**`requirements.txt`:** `sentry-sdk>=2.35.0` → `sentry-sdk>=2.54.0` (structured logger API floor; 2.x only, no 3.x OTel APIs).

### Deviations from Plan

None — plan executed exactly as written.

### PII-Safety Test Gate

16 new assertions in `TestSentryTelemetryHelpers`:
- KPI: returns expected keys; throughput computed; zero-duration → `0.0`; every value is `int | float`.
- Snapshot: success/failure shapes; values are `int|float|bool|None|str`; no WR token; no `$`; no foreman name in JSON.
- Log event: no-op without DSN; no-op without `sentry_sdk.logger` attr; no raise on bad level; swallows broken logger.

### Verification

- `python -m py_compile generate_weekly_pdfs.py`: CLEAN
- `python -m pytest tests/ -q`: **1043 passed, 29 skipped, 76 subtests passed**
- No `set_measurement` added. `SENTRY_ENABLE_LOGS` default unchanged (stays `false`). Billing path untouched. Plan-01 edits untouched.
