---
quick_id: 260605-tgi
slug: fix-3-pylance-type-errors-in-generate-we
type: quick
created: 2026-06-06
---

# Quick Task 260605-tgi: Fix 3 Pylance type errors in generate_weekly_pdfs.py

## Task Boundary

Resolve the **3 `Error`-severity Pylance/Pyright diagnostics** in
`generate_weekly_pdfs.py` (confirmed via IDE `getDiagnostics`: exactly 3 Error,
369 Hint — the Hints are OUT OF SCOPE). All three are **static-analysis errors,
not runtime bugs** — the code is `hasattr`-guarded, covered by tests, CI-passed,
merged to master, and running in production. Fixes are **type-only** (zero
runtime behavior change).

## Errors → Fixes

| # | Site | Pylance error | Fix |
|---|------|---------------|-----|
| 1·2 | `_sentry_log_event` (~L1129) | `"logger" is not a known attribute of module "sentry_sdk"` (×2) | Resolve `logger` via `getattr(sentry_sdk, "logger")` into a local (already `hasattr`-guarded on L1126), then `getattr(_logger, level, _logger.info)` |
| 3 | `_build_cron_monitor_config` → `capture_checkin` (~L8063) | `dict[str, Unknown]` not assignable to `monitor_config: MonitorConfig \| None` | Add `from sentry_sdk._types import MonitorConfig` under `if TYPE_CHECKING:` and annotate `def _build_cron_monitor_config() -> "MonitorConfig":` |

## Tasks

1. **Add `TYPE_CHECKING` import of `MonitorConfig`** — extend `from typing import Any, cast` → `..., TYPE_CHECKING`; add an `if TYPE_CHECKING:` block importing `MonitorConfig` from `sentry_sdk._types` (type-checker-only; never imported at runtime).
   - files: `generate_weekly_pdfs.py`
   - verify: `grep -n "TYPE_CHECKING" generate_weekly_pdfs.py`
2. **Fix `_sentry_log_event` logger access** — resolve `sentry_sdk.logger` via `getattr`.
   - files: `generate_weekly_pdfs.py`
   - verify: behavior identical; `test_sentry_log_sanitizer.py` green
3. **Annotate `_build_cron_monitor_config` return** — `-> "MonitorConfig"`.
   - files: `generate_weekly_pdfs.py`
   - verify: IDE `getDiagnostics` → 0 Error-severity

## Verification (done = all pass)

- `python -m py_compile generate_weekly_pdfs.py` → clean
- `pytest tests/` → green (~1048 passed, incl. cron + sentry-log tests)
- IDE `getDiagnostics` on the file → **0 Error-severity** (369 Hints untouched)

## Constraints

- Production billing file: additive/surgical; do NOT touch billing/grouping/
  upload/cron-schedule logic. No runtime behavior change.
- Branch + atomic commit + PR to master (never push to main directly).
- Do NOT attempt to clear the 369 Hint-level diagnostics.
