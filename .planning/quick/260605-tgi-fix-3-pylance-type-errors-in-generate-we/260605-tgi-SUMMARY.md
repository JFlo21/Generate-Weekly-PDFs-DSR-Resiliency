---
quick_id: 260605-tgi
slug: fix-3-pylance-type-errors-in-generate-we
status: complete
completed: 2026-06-06
commit: 1c5caf9
pr: 266
---

# Quick Task 260605-tgi: Fix 3 Pylance type errors — Summary

**Cleared the 3 `Error`-severity Pylance/Pyright diagnostics in
`generate_weekly_pdfs.py` with type-only changes (zero runtime behavior change).
IDE `getDiagnostics`: Error-severity 3 → 0; the 369 `Hint`-level diagnostics
were intentionally left untouched.**

## What changed (`generate_weekly_pdfs.py`, commit `1c5caf9`, PR #266)

| Error | Fix |
|-------|-----|
| `_sentry_log_event`: `"logger" is not a known attribute of module "sentry_sdk"` (×2) | `_logger = getattr(sentry_sdk, "logger")` then `getattr(_logger, level, _logger.info)` — presence already asserted by the `hasattr` guard above |
| `_build_cron_monitor_config` → `capture_checkin`: `dict[str, Unknown]` not assignable to `MonitorConfig \| None` | Added `from sentry_sdk._types import MonitorConfig` under `if TYPE_CHECKING:`; annotated `def _build_cron_monitor_config() -> "MonitorConfig":` |

## Why they were "actually errors" but safe

All three were **legitimate static-analysis errors** (red in the Problems panel)
but **NOT runtime bugs**: `sentry_sdk.logger` is `hasattr`-guarded and real in
sentry-sdk ≥ 2.54.0; the monitor_config dict is structurally valid and the code
is tested, CI-passed, merged, and running in production. The fixes change only
how the type checker sees the code.

## Verification

- `python -m py_compile generate_weekly_pdfs.py` → clean
- `pytest tests/` → **1048 passed, 29 skipped** (identical to pre-change — no regression)
- `tests/test_cron_monitor_config.py` + `tests/test_sentry_log_sanitizer.py` → 66 passed
- IDE `getDiagnostics` (parsed): `{"Error":0,"Hint":369}` — was `{"Error":3,"Hint":369}`

## Deviations from plan

None. Executed inline by the orchestrator (rather than spawning planner/executor
subagents) given the task was a 2-site, fully-specified type-annotation fix — all
GSD gates preserved (quick-task dir, PLAN, atomic code commit, SUMMARY, STATE
tracking, branch + PR).

## Scope discipline

Only the 3 Error-severity diagnostics were addressed. The 369 Hint-level
diagnostics (unused imports / unaccessed names) were explicitly out of scope and
left untouched.
