---
phase: 09
slug: engine-modularization-pipeline-package-split
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: false
wave_0_complete: true
created: 2026-08-25
scope: gap-closure plans 09-07 / 09-08 (retroactive; Phase 09 proper was merged via PR #280 before GSD tracking)
---

# Phase 09 — Validation Strategy

> Per-phase validation contract. Reconstructed from artifacts (State B) on 2026-08-25
> after the G-09-MOD-06 gap-closure plans executed.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pyproject.toml) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/test_facade_harness.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Harness (all 6 gates)** | `bash scripts/run_6_gates.sh` (offline since 09-08; ~32 s) |
| **Estimated runtime** | ~11 s quick · ~25 s full · ~32 s harness |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_facade_harness.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite AND `bash scripts/run_6_gates.sh` must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-07-01 | 07 | 1 | MOD-06 | T-09-01 / T-09-03 | Gate 4 exits 1 on any non-integer or CRLF-tainted count; no new bypass flag | unit (real script bytes) | `python -m pytest tests/test_facade_harness.py -q -k gate4` | ✅ | ✅ green |
| 09-07-02 | 07 | 1 | MOD-06 | T-09-02 | `tests/golden/*.txt` check out LF on autocrlf clones | integration (bytes + `git check-attr`) | `python -m pytest tests/test_facade_harness.py -q -k "golden or crlf_scan"` | ✅ | ✅ green |
| 09-07-03 | 07 | 1 | MOD-06 | T-09-06 | Ledger entry carries no secrets | doc check | `bash -c 'tail -80 memory-bank/living-ledger.md \| grep -q G-09-MOD-06'` | ✅ | ✅ green |
| 09-08-01 | 08 | 2 | MOD-06 | T-09-07 / T-09-08 / T-09-13 | Gate 6 never reads production; hash_history untouched | integration (real script bytes) + harness run | `python -m pytest tests/test_facade_harness.py -q -k gate6` · `bash scripts/run_6_gates.sh` | ✅ | ✅ green |
| 09-08-02 | 08 | 2 | MOD-06 | T-09-11 | Every new mypy finding attributed before a decision is offered | artifact completeness (python multiset check, see 09-08-PLAN Task 2 verify) | plan verify #2 | ✅ | ✅ green |
| 09-08-03 | 08 | 2 | MOD-06 | T-09-09 | Re-baseline only by explicit human decision + attributed commit | manual (decision checkpoint) | — | n/a | ✅ decided `rebaseline` (`da7d73c`) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Nyquist audit 2026-08-25 added 8 pytest guards to `tests/test_facade_harness.py` (golden LF pin ×3, Gate-6 synthetic pin ×5 incl. fail-capability cases); no new framework or fixtures needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fix-types vs re-baseline decision for a Gate-4 delta | MOD-06 | Business/engineering judgment on accepted type debt; `gate="blocking-human"` by design (auto-choosing is the failure mode G-09-MOD-06 closed) | Read `.planning/debug/mypy-delta-*.md`, reply `fix-types` / `rebaseline` / `split`; re-baseline lands as a dedicated attributed commit |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (09-08-03 is a designed human gate)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 35s
- [ ] `nyquist_compliant: true` — intentionally false: one manual-only behavior (the human decision checkpoint) remains by design

**Approval:** validated 2026-08-25 (partial — 5 automated, 1 manual-only)

## Validation Audit 2026-08-25
| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |
