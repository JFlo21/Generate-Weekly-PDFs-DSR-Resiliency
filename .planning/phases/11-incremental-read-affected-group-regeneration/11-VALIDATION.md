---
phase: 11
slug: incremental-read-affected-group-regeneration
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-26
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python 3.12 in CI, 3.11+ locally) |
| **Config file** | `pytest.ini` / `tests/conftest.py` (existing — no Wave 0 install) |
| **Quick run command** | `python -m pytest tests/test_pipeline_memory_shadow.py tests/test_mem04_formula_change.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` (baseline 1525 passed / 1 skipped / 135 subtests) |
| **Estimated runtime** | ~25 seconds (full suite); ~5 seconds (quick) |

Also gate every plan with `python -m py_compile generate_weekly_pdfs.py` and, before
`/gsd:verify-work`, `bash scripts/run_6_gates.sh` (Gate 6 pins the frozen 21-key
`tests/golden/run_summary_baseline.json`).

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_pipeline_memory_shadow.py tests/test_mem04_formula_change.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {N}-01-01 | 01 | 1 | REQ-{XX} | T-{N}-01 / — | {expected secure behavior or "N/A"} | unit | `{command}` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*(Populated from PLAN.md `<automated>` verify commands by `/gsd:validate-phase`; see
`11-RESEARCH.md` § Validation Architecture for the per-decision / per-success-criterion map.)*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_memory_incremental.py` — stubs for INC-01..INC-04 (delta read, watermark, FULL-read triggers, affected-set → sheet mapping, shadow parity verdict)
- [ ] `tests/test_pipeline_memory_shadow.py` — extend for WR-01 decorated-numeric payloads and WR-04 `sheets_changed`
- [ ] `tests/conftest.py` — shared fixtures (already present)

*Existing infrastructure covers the framework; new test modules above are created by the plans that need them.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `RUN_MEMORY_WRITE_ENABLED` flip merged and one real run populated `pipeline_memory` | INC-04 (D-10 precondition) | Protected GitHub Actions workflow edit + live production run | Juan approves/merges the flip PR; confirm a `run_ledger` row with `status='success'` and non-zero `row_state` count |
| Parity streak ≥5 consecutive `production_frequent` runs with `parity_verdict='pass'` | INC-04 | Requires real scheduled runs over ~1 business day | Query newest `run_ledger` rows (`notes.execution_type='production_frequent'`) backward to first non-pass |
| Weekly deep run detects a deleted row + formula-only change on live data | INC-03 (SC3) | One live verification alongside the fixture | Delete one row / edit one formula on the Sandbox rig before the Monday run; confirm `row_state.deleted_at` + `group_state` repair |
| Frequent-run wall clock before/after INC-05 retirement | INC-05 (SC4) | Measured on real runs (baseline 94 min, run 32743959053) | Compare run durations in the Actions log before and after the retirement PR |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
