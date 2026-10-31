---
phase: "15"
slug: "foreman-notes-and-smartsheet-color-carry-over-gf-pilot"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-29"
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (unittest-style classes common) |
| **Config file** | none (repo root `tests/`); 6-gate harness `scripts/run_6_gates.sh` |
| **Quick run command** | `python -m pytest tests/test_foreman_notes_*.py -q -x` |
| **Full suite command** | `python -m pytest tests/ -q` then `bash scripts/run_6_gates.sh` |
| **Estimated runtime** | ~45 seconds (suite); harness longer |

---

## Sampling Rate

- **After every task commit:** quick run command
- **After every plan wave:** full suite command
- **Before `/gsd:verify-work`:** full suite + 6 gates green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled by the planner per task (`<automated>` blocks). Requirement → test map (from RESEARCH.md):

| Requirement | Behavior | Test Type | Automated Command | File Exists |
|-------------|----------|-----------|-------------------|-------------|
| FN-01 | switch off / non-pilot: cell + hash identity vs golden | unit | `pytest tests/test_foreman_notes_excel.py tests/test_foreman_notes_hash.py -x` | ❌ W0 |
| FN-02/03 | allowlist + GF normalisation, fail-closed | unit | `pytest tests/test_foreman_notes_state.py -x` | ❌ W0 |
| FN-04 | notes identical full vs delta read | unit | `pytest tests/test_foreman_notes_hash.py -k full_vs_delta -x` | ❌ W0 |
| FN-05/06 | column I, merges, TOTAL, print setup, footer untouched | unit | `pytest tests/test_foreman_notes_excel.py -x` | ❌ W0 |
| FN-07/10 | descriptor parse (row + cell precedence), fail-closed, no colour-triggered regen | unit | `pytest tests/test_foreman_notes_styles.py -x` | ❌ W0 |
| FN-08/09 | NOTES_FP, fingerprint, globals fp, AST coverage | unit | `pytest tests/test_foreman_notes_hash.py tests/test_row_state_group_hash_domain.py -x` | ❌ W0 / ✅ |
| FN-11 | effective-scope matrix incl. SKIP_UPLOAD / TEST_MODE / upload switch | unit | `pytest tests/test_foreman_notes_state.py -x` | ❌ W0 |
| FN-12 | every variant renders column I in pilot | unit | `pytest tests/test_foreman_notes_excel.py -k variants -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/foreman_notes/` golden cell dumps + golden hash digests captured from the BASE commit before any production edit
- [ ] `tests/test_foreman_notes_{state,styles,hash,excel}.py`
- [ ] coverage-test additions alongside `tests/test_row_state_group_hash_domain.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live row-level `conditionalFormat` returned | FN-07 | needs live token | DONE 2026-10-29 (RESEARCH.md § Live Probe Result) |
| Owner dry-run review of pilot workbooks | FN-11 | business judgment | `SKIP_UPLOAD=true` local run scoped to a pilot WR; open the xlsx, confirm notes + colours |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
