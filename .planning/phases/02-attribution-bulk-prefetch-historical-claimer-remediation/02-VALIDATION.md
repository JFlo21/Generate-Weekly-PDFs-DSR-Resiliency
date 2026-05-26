---
phase: 02
slug: attribution-bulk-prefetch-historical-claimer-remediation
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
validated: 2026-05-26
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
| 02-01-01 | 01 | 1 | SPEC-1 | T-02-01/02/03 | Parameterized jsonb RPC, service_role-only grant, op-isolated | structural | `python -c "assert 'lookup_attribution_bulk' in open('billing_audit/schema.sql').read()"` | ✅ | ✅ green |
| 02-01-02 | 01 | 1 | SPEC-1, SPEC-6 | T-02-03/04/05 | Fail-safe reader (distinct op id), no PII in logs, chunked payload; RESOLVER-LEVEL historical-claimer RED/GREEN + direct-HOLD-zero-Supabase-calls locked HERE (Wave 1, BLOCKER 1/3) | unit | `pytest tests/test_billing_audit_shadow.py::PrefetchAttributionTests tests/test_billing_audit_shadow.py::ResolveClaimerMapAwareTests -q` | ✅ | ✅ green |
| 02-02-01 | 02 | 2 | SPEC-2, SPEC-6 | T-02-07/09 | BEHAVIORAL keystone ONLY (group_source_rows-driven; resolver-level cases live in Plan 01 Wave 1); + B/C direct-HOLD-0-Supabase wiring (BLOCKER 1); RED-before/GREEN-after | behavioral | `pytest tests/test_primary_claim_attribution.py::TestHistoricalClaimerRegression -q` | ✅ | ✅ green |
| 02-02-02 | 02 | 2 | SPEC-1, SPEC-2, SPEC-3 | T-02-06/08/09/10 | Single bulk prefetch; no per-row RPC; scope removed; CR-01 preserved; D-04 fallback | behavioral + grep | `pytest tests/ -q` | ✅ | ✅ green |
| 02-02-03 | 02 | 2 | SPEC-6 | — | Obsolete scope test deleted; no orphan import | suite | `pytest tests/ -q` | ✅ | ✅ green |
| 02-03-01 | 03 | 3 | SPEC-4, SPEC-6 | T-02-11/13 | Dry-run-no-delete + live-identity exemption + pattern-only delete | unit | `pytest tests/test_claimer_remediation.py -q` | ✅ | ✅ green |
| 02-03-02 | 03 | 3 | SPEC-4 | T-02-11/12/13/14 | Isolated default-OFF sweep; parser-based identity; counts-only logs | unit + behavioral | `pytest tests/test_claimer_remediation.py -q` | ✅ | ✅ green |
| 02-03-03 | 03 | 3 | SPEC-4 | T-02-12/15 | Flags pinned default-OFF; AUTHORITATIVE not flipped here | suite + config | `pytest tests/test_claimer_remediation.py -q` | ✅ | ✅ green |
| 02-04-01 | 04 | 4 | SPEC-5, SPEC-4 | T-02-16/17 | Runbook documents validation gate + human-gated flip + dry-run-first | doc (inline string assert) | `python -c "src=open('website/docs/runbook/operations.md',encoding='utf-8').read(); req=['SUPABASE_HASH_STORE_AUTHORITATIVE','lookup_attribution_bulk','REMEDIATE_CLAIMERS','TIME_BUDGET_MINUTES','NOTIFY pgrst','46cd05d']; missing=[r for r in req if r not in src]; assert not missing, missing; print('ok')"` | ✅ | ✅ green |
| 02-04-02 | 04 | 4 | SPEC-5 | T-02-16 | Living Ledger records fix + rules + lineage; append-only | doc (inline string+count assert) | `python -c "import re; t=open('CLAUDE.md',encoding='utf-8').read(); req=['lookup_attribution_bulk','ATTRIBUTION_RESOLUTION_WEEKS','run_claimer_remediation','PrefetchAttributionTests']; assert all(r in t for r in req); assert len(re.findall(r'\[2026-05-26 \d\d:\d\d\]', t))>=2; print('ok')"` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Sampling continuity check: no run of 3 consecutive tasks lacks an automated verify
(every task above has an automated command; the two doc tasks use INLINE
`python -c` string assertions — no executor-created-script dependency, BLOCKER 2).

---

## Wave 0 Requirements

- [x] `tests/test_billing_audit_shadow.py` — add `PrefetchAttributionTests` (success / unavailable / global-kill-is-fetch-failure / with_retry-None-is-fetch_failure / unexpected-exception-is-fetch_failure / empty-pairs-no_row / chunking / no-per-row-RPC) + `ResolveClaimerMapAwareTests` (map-hit-frozen / map-miss-no_history / disabled / RESOLVER-LEVEL historical-row-resolves-real-claimer + historical-no-frozen-falls-back / direct-HOLD-zero-Supabase-calls). The resolver-level historical-claimer RED/GREEN assertions are locked at Wave 1 HERE (they do not depend on generate_weekly_pdfs.py) — BLOCKER 3. Plan 01. **VERIFIED**: 17 passed, 3 skipped (postgrest-gated).
- [x] `tests/test_primary_claim_attribution.py` — add `TestHistoricalClaimerRegression` (the BEHAVIORAL group_source_rows-driven keystone ONLY: historical group emits real claimer key, garbage absent — RED-before/GREEN-after; depends on Wave 2 code) — Plan 02. Resolver-level cases are NOT here (they are in Plan 01's ResolveClaimerMapAwareTests, Wave 1). **VERIFIED**: 2 passed.
- [x] `tests/test_subcontractor_primary_claim_attribution.py` + `tests/test_vac_crew_claim_attribution.py` — B/C direct-HOLD wiring tests (under `_attr_status=='fetch_failure'`, outcome is HOLD AND `_lookup_attribution_all.assert_not_called()` — 0 additional Supabase calls, BLOCKER 1); map hit → frozen — Plan 02. **VERIFIED**: `test_bulk_fetch_failure_bc_direct_hold_zero_supabase_calls` + `test_bulk_fetch_failure_c_direct_hold_zero_supabase_calls` both pass; `assert_not_called` present in both files.
- [x] `tests/test_claimer_remediation.py` — NEW module with INLINE `_ensure_smartsheet_mocked` def + import-guard (WARNING 5; the old defining module is deleted); dry-run-no-delete / execute-only-garbage / live-identity-exemption (valid_wr_weeks populated) / isolation-path (valid_wr_weeks=None, WARNING 6) / real-name-never-matches / window-filter / TARGET+PPP — Plan 03. **VERIFIED**: 14 passed (incl. Plan 02-06 `TestIsolatedPathUnknownForemanProtection` + `TestOutOfWindowCountsOnlyGarbage`).
- [x] DELETE `tests/test_attribution_resolution_scope.py` (D-05; replacement regression lives in test_primary_claim_attribution.py) — Plan 02. **VERIFIED**: file absent; `ATTRIBUTION_RESOLUTION_WEEKS` remains only in 3 explanatory comments (no live code).

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

**Approval:** validated (all tasks green post-execution)

---

## Validation Audit 2026-05-26

Post-execution retroactive audit (State A). All 6 plans executed; cross-referenced
the plan-time per-task verification map against the implemented test suite and ran
every automated command. No gaps — every requirement has passing automated coverage;
no `gsd-nyquist-auditor` spawn was required.

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated (manual-only) | 3 (pre-declared: live-RPC acceptance run, AUTHORITATIVE=1 flip, remediation execute) |

**Evidence (commands run 2026-05-26):**

| Check | Result |
|-------|--------|
| `pytest tests/ -q` (full suite) | 986 passed, 29 skipped, 69 subtests passed |
| `PrefetchAttributionTests` + `ResolveClaimerMapAwareTests` | 17 passed, 3 skipped |
| `TestHistoricalClaimerRegression` | 2 passed |
| `test_claimer_remediation.py` | 14 passed |
| B/C direct-HOLD-zero-Supabase wiring (BLOCKER 1) | 2 passed (`assert_not_called` verified) |
| Plan 02-05/06 gap-closure (`TestRpcMissingGracefulDegradation`, `TestIsolatedPathUnknownForemanProtection`, `TestOutOfWindowCountsOnlyGarbage`) | 11 passed |
| schema.sql `lookup_attribution_bulk` (02-01-01) | PASS |
| operations.md runbook doc assert (02-04-01) | PASS |
| CLAUDE.md Living Ledger doc assert (02-04-02) | PASS |
| Config pins: `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` (not flipped), remediation flags via `advanced_options`, `ATTRIBUTION_BULK_PREFETCH_FALLBACK: '1'` | PASS |
| `tests/test_attribution_resolution_scope.py` deleted (D-05) | PASS (absent; `ATTRIBUTION_RESOLUTION_WEEKS` only in comments) |

**Conclusion:** Phase 02 is Nyquist-compliant. The 3 manual-only verifications are
correctly deferred (they require a live Supabase RPC deploy + production-equivalent
run and a deliberately human-gated `AUTHORITATIVE=1` flip), not validation gaps.
