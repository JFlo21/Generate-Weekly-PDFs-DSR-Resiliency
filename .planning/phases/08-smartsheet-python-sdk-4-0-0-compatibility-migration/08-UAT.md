---
status: complete
phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration
source: [08-01-SUMMARY.md, 08-02-SUMMARY.md, 08-HUMAN-UAT.md (carried-over test)]
started: 2026-07-22T20:57:58Z
updated: 2026-07-22T21:24:22Z
---

## Current Test

[testing complete]

## Tests

### 1. SDK 4.3.0 installed and exact-pinned
expected: `python -m pip show smartsheet-python-sdk` reports Version: 4.3.0, and `requirements.txt` contains the exact pin `smartsheet-python-sdk==4.3.0` (no `<4.0.0` ceiling remains).
result: pass

### 2. Engine imports cleanly without the 3.x re-export shim
expected: `python -m py_compile generate_weekly_pdfs.py` exits clean, and importing the engine raises no ModuleNotFoundError/AttributeError. The 27-line `smartsheet.smartsheet` re-export block is gone from the top of generate_weekly_pdfs.py (only `import smartsheet` + `import smartsheet.exceptions as ss_exc` remain).
result: pass

### 3. Full test suite green under 4.3.0
expected: With `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` set and SMARTSHEET_API_TOKEN unset (to avoid real reads), `pytest tests/ -v` passes — 1171 passed + 130 subtests, 0 failures.
result: pass

### 4. SKIP_UPLOAD zero-mutation gating in effect
expected: `pytest tests/test_skip_upload_delete_gating.py -v` passes all 7 tests — SKIP_UPLOAD=true now gates the DELETE half too (dry_run wired at all 5 mutating call sites in pipeline/orchestrate.py), so a SKIP_UPLOAD run performs zero Smartsheet mutations.
result: pass

### 5. No lingering production-attachment loss (WR 89881161 self-heal; WR 89708709 / WR 90093002 intact)
expected: On target sheet 5723337641643908 — WR 89881161 weeks 072025 and 081725 (deleted by the D-05 probe) have been regenerated and re-uploaded by a subsequent weekday cron run; WR 89708709 and WR 90093002 either have no matching attachments (no-op) or show no unexplained loss. No manual restore needed.
result: pass

### 6. Migration recorded for operators (Living Ledger + rollout/rollback runbooks)
expected: memory-bank/living-ledger.md contains the dated migration entry ([2026-07-22 02:31]) and the D-05 live-probe sign-off ([2026-07-22 10:20]); 08-02-SUMMARY.md captures the D-06 rollout runbook (weekday daytime merge + one watched canary dispatch) and the D-07 rollback runbook (revert PR, pip cache auto-busts).
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
