---
phase: "13"
slug: "audit-memory"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-11"
planned: "2026-09-11"
plans: 6
waves: 5
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, `tests/` directory) |
| **Config file** | none dedicated — `pytest tests/ -v` per CLAUDE.md Validation commands |
| **Quick run command** | `python -m pytest tests/test_audit_findings.py -q` (created by plan 13-01 Task 2; until then `python -m pytest tests/test_billing_audit_shadow.py -q`) |
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
| 13-01-02 | 13-01 | 1 | AUD-01 | T-13-01, T-13-02, T-13-04 | Tracer: one check type travels flag gate → key derivation → breaker → shaped RPC call; flag-off path makes zero Supabase calls | unit (fake Supabase client) | `python -m pytest tests/test_audit_findings.py -q` | ✅ W0 created here | ⬜ pending |
| 13-01-03 | 13-01 | 1 | AUD-01 | T-13-04 | Orchestrate hook is dormant with the flag unset and non-fatal on any failure with it on | unit + dry run | `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py` | ✅ | ⬜ pending |
| 13-02-01 | 13-02 | 1 | AUD-01 | T-13-02-01 | Provenance-row key narrowing preserves the skip behavior for malformed rows | unit | `python -m pytest tests/test_snapshot_store.py -q` | ✅ | ⬜ pending |
| 13-02-02 | 13-02 | 1 | AUD-01 | T-13-02-02 | Gate-4 baseline drops by exactly one; six-gate harness stays green | harness | `bash scripts/run_6_gates.sh` | ✅ | ⬜ pending |
| 13-03-01 | 13-03 | 2 | AUD-01 | T-13-03-05 | Finding-key derivation matches the D-01 recipe per check type, incl. the price_variance_anomaly multi-week NULL path (D-CD-01) and the data_consistency_issue sorted-set rule (D-CD-02) | unit | `python -m pytest tests/test_audit_findings.py -k key_derivation -q` | ✅ | ⬜ pending |
| 13-03-02 | 13-03 | 2 | AUD-01 | T-13-03-02 | Recipe map is exhaustive; recent_discussion passes through silently; duplicate keys collapse and are counted | unit | `python -m pytest tests/test_audit_findings.py -q` | ✅ | ⬜ pending |
| 13-03-03 | 13-03 | 2 | AUD-01 | T-13-03-01, T-13-03-04 | The check's literal issue strings are pinned both ways; audit_billing_changes.py diff is comment-only | unit (contract) | `python -m pytest tests/test_audit_findings.py -q` | ✅ | ⬜ pending |
| 13-04-01 | 13-04 | 3 | AUD-01, AUD-02 | T-13-04-01, T-13-04-02, T-13-04-03 | Full D-08 transition table server-side; the fixed branch joins the re-audited set so an empty set closes nothing | structural (SQL text gates) | `grep -nE "EXECUTE +'\|EXECUTE +format\(\|\\\|\\\| *quote_" pipeline_memory/schema.sql` | ✅ | ⬜ pending |
| 13-04-02 | 13-04 | 3 | AUD-02 | T-13-04-03 | Re-audited pairs are per-check; a check disabled for the run closes nothing (Pitfall 5) | unit | `python -m pytest tests/test_audit_findings.py -q` | ✅ | ⬜ pending |
| 13-04-03 | 13-04 | 3 | AUD-01, AUD-02 | T-13-04-04 | Python payload keys, RPC params, and both CHECK value sets stay in lockstep; caller per-run payload contract pinned | unit (contract) + lifecycle | `python -m pytest tests/test_audit_findings_sql_contract.py -q` and `python -m pytest tests/test_audit_findings.py -k lifecycle -q` | ✅ | ⬜ pending |
| 13-05-01 | 13-05 | 4 | AUD-01, AUD-03 | T-13-05-01, T-13-05-02 | Views declare security_invoker and revoke anon/authenticated; open_findings filters to open+resurfaced with a total order; acknowledge_finding pins search_path | structural (SQL text gates) | `python -m pytest tests/test_audit_findings_sql_contract.py -q` | ✅ | ⬜ pending |
| 13-05-02 | 13-05 | 4 | AUD-03 | T-13-05-04, T-13-05-06 | Owner applies the DDL; schema cache reloaded; nothing enabled | manual (owner, protected area, D-11) | N/A — checkpoint:human-verify, gate blocking-human | n/a | ⬜ pending |
| 13-05-03 | 13-05 | 4 | AUD-03 | T-13-05-01, T-13-05-03 | `open_findings` returns open+resurfaced only; `finding_history_by_wr` returns full per-WR history incl. event-less findings; acknowledge_finding writes its event and rejects bad input | manual SQL read-back (owner) | N/A — checkpoint:human-verify | n/a | ⬜ pending |
| 13-06-02 | 13-06 | 5 | AUD-03 | T-13-06-01 | Operator docs for the flag and the SQL surface build cleanly with no broken links | build | `npm --prefix website run build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Planner fills Task ID / Plan / Wave columns from PLAN.md; rows above are the research-derived requirement map.*

---

## Wave 0 Requirements

- [ ] `tests/test_audit_findings.py` — created by plan **13-01 Task 2** (the tracer), the first code-producing task of the phase; covers AUD-01/AUD-02 key derivation and caller-contract behavior against a fake Supabase client (mirror `_make_fake_supabase_client` / `_fake_rpc_response` from `tests/test_billing_audit_shadow.py`)
- [ ] `tests/test_audit_findings_sql_contract.py` — created by plan **13-04 Task 3**; lockstep Python-to-SQL pin over the RPC parameters, the typed recordset column lists, and both CHECK value sets (mirror `tests/test_upsert_rows_bulk_helper2_contract.py`)
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
