---
phase: 08
slug: smartsheet-python-sdk-4-0-0-compatibility-migration
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-21
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing suite, ~1122 tests) + `scripts/run_6_gates.sh` behavior-neutrality oracle |
| **Config file** | none — repo-root `tests/` discovered by pytest defaults |
| **Quick run command** | `python -m py_compile generate_weekly_pdfs.py && pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Gate harness** | `bash scripts/run_6_gates.sh` |
| **Estimated runtime** | ~120 seconds (suite); ~150 seconds (six gates incl. TEST_MODE synthetic run) |

---

## Sampling Rate

- **After every task commit:** Run `python -m py_compile generate_weekly_pdfs.py && pytest tests/ -x -q`
- **After every plan wave:** Run `bash scripts/run_6_gates.sh` (six gates) then `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full six-gate + full suite must be green under SDK 4.3.0
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-T1 | 08-01 | 1 | SDK-01, SDK-03 | T-08-SC | Trusted first-party exact-pin install; every in-use SDK symbol resolves | smoke import | `python -c "import smartsheet.exceptions as e, smartsheet.smartsheet; from smartsheet.models.sheet import Sheet; from smartsheet.models.folder import Folder; [getattr(e,n) for n in ('RateLimitExceededError','UnexpectedErrorShouldRetryError','InternalServerError','ServerTimeoutExceededError')]; print('SDK_401_OK')"` | ✅ generate_weekly_pdfs.py | ⬜ pending |
| 08-01-T2 | 08-01 | 1 | SDK-02 | T-08-01, T-08-02 | Remove dead re-export without breaking retry lookup; baseline reflects ONLY the authorized `_exc_name` deletion | AST / unit | `python -m py_compile generate_weekly_pdfs.py && python scripts/check_api_equality.py` | ✅ tests/golden/baseline_names.json | ⬜ pending |
| 08-01-T3 | 08-01 | 1 | SDK-04, SDK-06 | T-08-01 | Full behavior-neutrality: six gates + full pytest green, zero test changes | full suite + gates | `bash scripts/run_6_gates.sh && pytest tests/ -v` | ✅ scripts/run_6_gates.sh | ⬜ pending |
| 08-02-T1 | 08-02 | 2 | SDK-05 | T-08-04 | Exact pin blocks unreviewed auto-bump into production | config assertion | `python -c "import re,sys; t=open('requirements.txt').read(); m=re.search(r'^smartsheet-python-sdk(.*)$',t,re.M); sys.exit(0 if (m and m.group(1).strip()=='==4.3.0') else 1)"` | ✅ requirements.txt | ⬜ pending |
| 08-02-T2 | 08-02 | 2 | SDK-05 | T-08-04 | Durable ledger record of the migration + exact-pin rule | docs assertion | `python -c "assert 'smartsheet-python-sdk==4.3.0' in open('memory-bank/living-ledger.md',encoding='utf-8').read(); print('LEDGER_OK')"` | ✅ memory-bank/living-ledger.md | ⬜ pending |
| 08-02-T3 | 08-02 | 2 | SDK-03, SDK-06 | T-08-03, T-08-05 | Live read-only probe validates real 4.3.0 transport + error shape; ZERO writes to Smartsheet | manual live probe | `SKIP_UPLOAD=true WR_FILTER=<WRs> MAX_GROUPS=5 python generate_weekly_pdfs.py` (operator-run) + `pip show smartsheet-python-sdk` | ✅ generate_weekly_pdfs.py | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all automated phase requirements — the
existing pytest suite (~1122 tests, including `tests/test_smartsheet_retry.py`
17 retry-path tests and the shadow-import tests) plus the calibrated
`scripts/run_6_gates.sh` behavior-neutrality oracle. **No new test files or
fixtures are required** (SDK-04 research finding: net test changes = zero).

One authorized golden-baseline edit is part of implementation, not a Wave 0
gap: `tests/golden/baseline_names.json` drops the transient `_exc_name`
(178 -> 177) to reflect the D-04 block deletion (task 08-01-T2).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live read-only Smartsheet probe on SDK 4.3.0 | SDK-03 (real path), SDK-06 | Mocked `ApiError.error.result` blind spot — `tests/test_smartsheet_retry.py` uses `mock.Mock()` and TEST_MODE never touches the wire; production-touch action is operator-gated | On branch `feat/phase-08-sdk-430-migration` with 4.3.0 installed, run `SKIP_UPLOAD=true WR_FILTER=<known WRs> MAX_GROUPS=5 python generate_weekly_pdfs.py`. Confirm exit 0, real rows fetched, Excel generated under `generated_docs/`, ZERO uploads/deletes, no SDK error-shape exception (08-02 task 3 / D-05) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (08-02-T3 pairs a `<human-check>` with a supporting automated `pip show` assertion)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra + one authorized baseline edit)
- [x] No watch-mode flags
- [x] Feedback latency < 180s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (planner) — ready for `/gsd:execute-phase 08`
