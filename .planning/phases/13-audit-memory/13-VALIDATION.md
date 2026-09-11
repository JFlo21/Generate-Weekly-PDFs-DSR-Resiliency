---
phase: "13"
slug: "audit-memory"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-11"
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, `tests/` directory) |
| **Config file** | none dedicated — `pytest tests/ -v` per CLAUDE.md Validation commands |
| **Quick run command** | `pytest tests/test_audit_findings.py -x` (Wave 0 creates it; until then `pytest tests/test_billing_audit_shadow.py -v`) |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~120 seconds (full suite, 2333+ tests) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_audit_findings.py -x` (or the closest new/modified test file)
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green; DDL apply + live read-back checkpoint (D-11) before declaring AUD-03 satisfied
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-xx-xx | — | — | AUD-01 | — | Finding created once, stable key, lifecycle transitions (open→fixed/resurfaced/acknowledged/suppressed) | unit (fake Supabase client) | `pytest tests/test_audit_findings.py -x` | ❌ W0 | ⬜ pending |
| 13-xx-xx | — | — | AUD-01 | — | Finding-key derivation matches D-01 recipe per check type, incl. price_variance_anomaly multi-week NULL path (D-CD-01) and data_consistency_issue literal-string pin | unit | `pytest tests/test_audit_findings.py -k key_derivation -x` | ❌ W0 | ⬜ pending |
| 13-xx-xx | — | — | AUD-02 | — | Only affected groups + open findings evaluated; non-reproduced finding transitions to `fixed` with fixing run id | unit + fixture-seed integration | `pytest tests/test_audit_findings.py -k lifecycle -x` | ❌ W0 | ⬜ pending |
| 13-xx-xx | — | — | AUD-03 | — | `open_findings` / `finding_history_by_wr` views return status IN ('open','resurfaced') and full per-WR history | manual SQL (post-DDL-apply checkpoint, D-11) | N/A — checkpoint:human-verify | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Planner fills Task ID / Plan / Wave columns from PLAN.md; rows above are the research-derived requirement map.*

---

## Wave 0 Requirements

- [ ] `tests/test_audit_findings.py` — new file, covers AUD-01/AUD-02 key derivation and lifecycle transitions against a fake Supabase client (mirror `_make_fake_supabase_client` / `_fake_rpc_response` from `tests/test_billing_audit_shadow.py`)
- [ ] No new shared fixtures needed — existing `tests/test_billing_audit_shadow.py` and Phase 10/11 shadow-test fixtures are directly reusable
- [ ] Framework install: none — pytest already installed and in use

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `open_findings` / `finding_history_by_wr` view content on live Supabase | AUD-03 | No automated harness for live Supabase view content exists in this repo; DDL apply is owner-executed (D-11) | After owner applies the appended `pipeline_memory/schema.sql` DDL: run `SELECT * FROM open_findings LIMIT 5;` and `SELECT * FROM finding_history_by_wr WHERE wr = '<seeded WR>';` in the SQL editor; confirm statuses are only open/resurfaced in the first and full history in the second |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
