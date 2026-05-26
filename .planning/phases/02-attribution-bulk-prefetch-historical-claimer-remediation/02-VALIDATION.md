---
phase: 02
slug: attribution-bulk-prefetch-historical-claimer-remediation
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-26
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (unittest.TestCase classes) + coverage |
| **Config file** | none (pytest discovers `tests/`) |
| **Quick run command** | `pytest tests/test_billing_audit_shadow.py -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_billing_audit_shadow.py tests/test_primary_claim_attribution.py tests/test_claimer_remediation.py -q` (whichever exist)
- **After every plan wave:** `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SPEC-1 | T-02-01/02/03 | Parameterized jsonb RPC, service_role-only grant, op-isolated | structural | `python -c "assert 'lookup_attribution_bulk' in open('billing_audit/schema.sql').read()"` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | SPEC-1, SPEC-6 | T-02-03/04/05 | Fail-safe reader (distinct op id), no PII in logs, chunked payload | unit | `pytest tests/test_billing_audit_shadow.py::PrefetchAttributionTests tests/test_billing_audit_shadow.py::ResolveClaimerMapAwareTests -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | SPEC-2, SPEC-6 | T-02-07/10 | Historical group resolves real claimer; RED-before/GREEN-after | behavioral | `pytest tests/test_primary_claim_attribution.py::TestHistoricalClaimerRegression -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | SPEC-1, SPEC-2, SPEC-3 | T-02-06/08/09/10 | Single bulk prefetch; no per-row RPC; scope removed; CR-01 preserved; D-04 fallback | behavioral + grep | `pytest tests/ -q` | ⚠ extend | ⬜ pending |
| 02-02-03 | 02 | 2 | SPEC-6 | — | Obsolete scope test deleted; no orphan import | suite | `pytest tests/ -q` | ✅ | ⬜ pending |
| 02-03-01 | 03 | 3 | SPEC-4, SPEC-6 | T-02-11/13 | Dry-run-no-delete + live-identity exemption + pattern-only delete | unit | `pytest tests/test_claimer_remediation.py -q` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 3 | SPEC-4 | T-02-11/12/13/14 | Isolated default-OFF sweep; parser-based identity; counts-only logs | unit + behavioral | `pytest tests/test_claimer_remediation.py -q` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 3 | SPEC-4 | T-02-12/15 | Flags pinned default-OFF; AUTHORITATIVE not flipped here | suite + config | `pytest tests/test_claimer_remediation.py -q` | ✅ | ⬜ pending |
| 02-04-01 | 04 | 4 | SPEC-5, SPEC-4 | T-02-16/17 | Runbook documents validation gate + human-gated flip + dry-run-first | doc | `python tools/check_phase2_docs.py` (executor-created) | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 4 | SPEC-5 | T-02-16 | Living Ledger records fix + rules + lineage; append-only | doc | `python tools/check_phase2_ledger.py` (executor-created) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Sampling continuity check: no run of 3 consecutive tasks lacks an automated verify
(every task above has an automated command; the two doc tasks use small
executor-created assertion scripts or inline grep equivalents).

---

## Wave 0 Requirements

- [ ] `tests/test_billing_audit_shadow.py` — add `PrefetchAttributionTests` (success / unavailable / global-kill-is-fetch-failure / with_retry-None-is-fetch_failure / unexpected-exception-is-fetch_failure / empty-pairs-no_row / chunking / no-per-row-RPC) + `ResolveClaimerMapAwareTests` (map-hit-frozen / map-miss-no_history / fetch_failure-holds-B/C / fetch_failure-uses-current-D / disabled) — Plan 01.
- [ ] `tests/test_primary_claim_attribution.py` — add `TestHistoricalClaimerRegression` (RED-before/GREEN-after historical group → real claimer; no-frozen fallback) — Plan 02.
- [ ] `tests/test_subcontractor_primary_claim_attribution.py` + `tests/test_vac_crew_claim_attribution.py` — map-aware resolution assertions (B/C HOLD on fetch_failure; map hit → frozen) — Plan 02.
- [ ] `tests/test_claimer_remediation.py` — NEW module (Pitfall-4 import-guard; dry-run-no-delete / execute-only-garbage / live-identity-exemption / real-name-never-matches / window-filter / TARGET+PPP) — Plan 03.
- [ ] DELETE `tests/test_attribution_resolution_scope.py` (D-05; replacement regression lives in test_primary_claim_attribution.py) — Plan 02.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Acceptance run: 0 garbage names + O(chunks) HTTP + ≤165 min | SPEC-2/3 (D-10) | Requires the live `lookup_attribution_bulk` RPC deployed to Supabase + a production-equivalent run; HTTP count + runtime are run-log observations | After RPC deploy, run with `SUPABASE_HASH_STORE_AUTHORITATIVE=0`; grep run log for `*_NO_MATCH*`/`*_Unknown_Foreman*` (expect 0 for rows with a frozen claimer); count `POST /rpc/lookup_attribution_bulk` (expect chunk count, not ~137k); confirm runtime < 165 min |
| `SUPABASE_HASH_STORE_AUTHORITATIVE=1` flip + post-flip clean run | SPEC-5 (D-11) | Human-gated operator action (deliberately not auto-committed); requires the green D-10 gate first | Per the operations.md re-activation runbook: flip in workflow `env:` as a separate PR; confirm clean filenames + correct claimers + zero garbage |
| Recent-window remediation execute | SPEC-4 (D-08) | Destructive production-attachment deletion; dry-run review precedes execute | Run `REMEDIATE_CLAIMERS='1' REMEDIATION_DRY_RUN='1'` (review counts), then `REMEDIATION_DRY_RUN='0'` (execute); confirm garbage gone + correct files present |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned (pending execution)
