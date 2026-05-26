---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
verified: 2026-05-26T20:00:00Z
status: gaps_found
score: 5/6 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Correct claimer on every generated file — no garbage _NO_MATCH / _Unknown_Foreman names (SPEC-2)"
    status: partial
    reason: "Implementation is complete and correct, but the bulk prefetch wiring (B and C variants) relies unconditionally on the lookup_attribution_bulk RPC being deployed to Supabase before the next production run. There is no per-row fallback kill switch. If the operator runs the new code before deploying the RPC, resolve_claimer fetch_failure fires for every completed B/C row, the direct-HOLD contract (D-04) suppresses all reduced_sub and aep_billable billing files for that run, and no garbage names are generated — but no files are generated either. The deployment-ordering hazard is CR-01 from 02-REVIEW.md. Goal attainment is conditional on operator action that is outside the codebase."
    artifacts:
      - path: "billing_audit/schema.sql"
        issue: "lookup_attribution_bulk RPC is defined here but requires manual operator deployment to Supabase SQL Editor + NOTIFY pgrst reload — not applied automatically"
      - path: "generate_weekly_pdfs.py"
        issue: "No ATTRIBUTION_BULK_PREFETCH_FALLBACK or any per-row fallback kill switch; if RPC unavailable, B/C variants HOLD all rows (D-04 direct-HOLD contract)"
    missing:
      - "Operator must apply lookup_attribution_bulk DDL to Supabase before the next production run (documented in operations.md runbook — the step exists, it is a human-gate not a code gap)"
      - "Consider adding an env-var kill switch (e.g. ATTRIBUTION_BULK_PREFETCH_FALLBACK=1) that falls back to per-row lookup_attribution on RPC unavailability — this would degrade gracefully rather than HOLDing all B/C rows on first deploy"
deferred: []
human_verification:
  - test: "Validate lookup_attribution_bulk RPC is deployed to live Supabase project"
    expected: "SELECT billing_audit.lookup_attribution_bulk('[{\"wr\":\"WR_TEST\",\"week_ending\":\"2026-05-19\"}]') returns an empty array without PGRST106 error"
    why_human: "Cannot verify live Supabase schema state from codebase inspection alone"
  - test: "Verify remediation dry-run produces correct output for a WR with known garbage attachments"
    expected: "DRY-RUN log shows would-delete counts for *_NO_MATCH* / *_Unknown_Foreman* files; real claimer files (build_group_identity 4-tuple in valid_wr_weeks) are exempted"
    why_human: "Requires access to Smartsheet sheets with actual garbage attachments; cannot verify from static code inspection"
  - test: "Confirm SUPABASE_HASH_STORE_AUTHORITATIVE remains 0 after deploying new code"
    expected: "Workflow log shows SUPABASE_HASH_STORE_AUTHORITATIVE=0 in startup banner; no clean filenames generated; hash_history.json still in use"
    why_human: "Requires running the actual workflow and inspecting run logs"
---

# Phase 02: Attribution Bulk-Prefetch + Historical Claimer Remediation Verification Report

**Phase Goal:** Fix the claim-attribution week-scope / Sub-project E interaction that produced garbage claimer filenames (`_User__NO_MATCH` / `_User_Unknown_Foreman`). Replace the four per-row `lookup_attribution` RPC pre-pass sites with a single bulk prefetch + O(1) map reads; DELETE the `ATTRIBUTION_RESOLUTION_WEEKS` week-scope (root cause); add a default-OFF, dry-run-first, isolated remediation mode to sweep already-uploaded garbage attachments; and ship the safe E re-activation runbook + Living Ledger entry. Ships with `SUPABASE_HASH_STORE_AUTHORITATIVE=0` (dormant).
**Verified:** 2026-05-26T20:00:00Z
**Status:** gaps_found — 1 conditional gap (CR-01 deployment-ordering BLOCKER from 02-REVIEW.md; confirmed by codebase inspection)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SPEC-1: Single bulk `lookup_attribution_bulk` RPC call replaces four per-row ThreadPoolExecutor pre-passes (D-01, D-02, D-03) | ✓ VERIFIED | `billing_audit/schema.sql` defines `lookup_attribution_bulk` with `jsonb_to_recordset` join; `billing_audit/writer.py` has `prefetch_attribution` with `_CHUNK_SIZE=500`; `generate_weekly_pdfs.py` has single bulk prefetch block and `prefetched_map=_attr_map` passed at 4 consumer sites (B, C, D, sub-helper Phase 1.1). ThreadPoolExecutor pre-passes replaced with O(1) map reads. |
| 2 | SPEC-2: Correct claimer on every generated file — no garbage `_NO_MATCH` / `_Unknown_Foreman` names (D-03, D-04) | PARTIAL | Implementation is correct. Direct-HOLD contract (D-04) is in code: B sets `_sub_primary_claimer_map[_rid] = _ResolveOutcome_b('hold', None, None, 'fetch_failure')`, C mirrors for vac_crew. Tests `test_historical_row_resolves_real_claimer_from_map` and `test_fetch_failure_direct_hold_zero_supabase_calls` pass. However, the RPC must be operator-deployed before the code runs — no fallback kill switch exists (CR-01 BLOCKER). If deployed in wrong order, B/C generate ZERO files (HOLD), not garbage files. Goal is functionally achieved once RPC is deployed; the code itself produces no garbage names. |
| 3 | SPEC-3: No time-budget regression — `ATTRIBUTION_RESOLUTION_WEEKS` and its scope gates fully removed (D-05) | ✓ VERIFIED | `grep -c "ATTRIBUTION_RESOLUTION_WEEKS" generate_weekly_pdfs.py` = 3, ALL in comment text (lines 662, 5593, 6293); zero live code references. `_attribution_week_in_scope` = 0 occurrences. `_attribution_resolution_cutoff` = 0 occurrences. 4 scope gates removed. `tests/test_attribution_resolution_scope.py` deleted. Workflow pin removed. `environment.md` entry removed. |
| 4 | SPEC-4: Default-OFF, dry-run-first, isolated remediation mode sweeps garbage attachments within a window (D-06, D-07, D-08, D-12) | ✓ VERIFIED | `run_claimer_remediation` implemented in `generate_weekly_pdfs.py`. `REMEDIATE_CLAIMERS='0'` default, `REMEDIATION_DRY_RUN='1'` default, `REMEDIATION_WINDOW_WEEKS=26` default. All three pinned in workflow. `_GARBAGE_PATTERNS = ('_NO_MATCH', '_Unknown_Foreman')`. Isolated dispatch (`if REMEDIATE_CLAIMERS: run_claimer_remediation(...); return`). Live-identity exemption via `valid_wr_weeks`. 9 tests in `tests/test_claimer_remediation.py` pass. |
| 5 | SPEC-5: Safe E re-activation runbook documenting D-09/D-10/D-11 ordered procedure (D-09, D-10, D-11) | ✓ VERIFIED | `website/docs/runbook/operations.md` contains all 6 required strings: `SUPABASE_HASH_STORE_AUTHORITATIVE`, `lookup_attribution_bulk`, `REMEDIATE_CLAIMERS`, `TIME_BUDGET_MINUTES`, `NOTIFY pgrst`, `46cd05d`. 4-step ordered procedure documented. `SUPABASE_HASH_STORE_AUTHORITATIVE` remains `'0'` in workflow (dormant). |
| 6 | SPEC-6: Regression coverage — `PrefetchAttributionTests`, `ResolveClaimerMapAwareTests`, `TestHistoricalClaimerRegression`, `tests/test_claimer_remediation.py` all pass; pytest 973/26 | ✓ VERIFIED | `pytest tests/` = 973 passed / 26 skipped / 69 subtests. All named test classes present and passing. `test_historical_row_resolves_real_claimer_from_map` in `test_primary_claim_attribution.py` anchored to run 26439205107 evidence. `test_fetch_failure_direct_hold_zero_supabase_calls` in `test_billing_audit_shadow.py` locks D-04 contract. |

**Score:** 5/6 truths verified (SPEC-2 is PARTIAL — implementation correct but deployment-ordering creates a conditional gap)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `billing_audit/schema.sql` | `lookup_attribution_bulk` RPC + `GRANT EXECUTE TO service_role` | ✓ VERIFIED | Function defined with `jsonb_to_recordset(p_wr_weeks)` join; `CASE WHEN s.frozen_primary` CASE blocks present (verbatim from `lookup_attribution`); `NOTIFY pgrst` deploy comment; `GRANT EXECUTE` to `service_role` |
| `billing_audit/writer.py` | `prefetch_attribution` + `resolve_claimer(prefetched_map=)` + D-04 docstring | ✓ VERIFIED | `prefetch_attribution` chunked at `_CHUNK_SIZE=500`; `op="lookup_attribution_bulk"` distinct from all existing ops (D-13); `prefetched_map: dict | None = None` parameter; D-04 contract docstring present |
| `generate_weekly_pdfs.py` | Single bulk prefetch block + 4 O(1) consumer sites + ATTRIBUTION_RESOLUTION_WEEKS fully removed + `run_claimer_remediation` + 3 env vars | ✓ VERIFIED | Single `_attr_map, _attr_status = _prefetch_attribution(...)` block; `prefetched_map=_attr_map` at B/C/D/sub-helper sites; D-04 direct-HOLD for B and C; ATTRIBUTION_RESOLUTION_WEEKS in comments only (3 occurrences); `run_claimer_remediation` implemented; `REMEDIATE_CLAIMERS`/`REMEDIATION_DRY_RUN`/`REMEDIATION_WINDOW_WEEKS` env vars |
| `.github/workflows/weekly-excel-generation.yml` | `ATTRIBUTION_RESOLUTION_WEEKS` removed; 3 remediation vars pinned default-safe; `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` | ✓ VERIFIED | `ATTRIBUTION_RESOLUTION_WEEKS` absent; `REMEDIATE_CLAIMERS: '0'`, `REMEDIATION_DRY_RUN: '1'`, `REMEDIATION_WINDOW_WEEKS: '26'` all pinned; `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` (not flipped — D-11 correct) |
| `website/docs/reference/environment.md` | `ATTRIBUTION_RESOLUTION_WEEKS` removed; 3 remediation vars documented | ✓ VERIFIED | ATTRIBUTION_RESOLUTION_WEEKS absent; REMEDIATE_CLAIMERS/REMEDIATION_DRY_RUN/REMEDIATION_WINDOW_WEEKS sections present |
| `website/docs/runbook/operations.md` | E re-activation runbook section with D-09/D-10/D-11 | ✓ VERIFIED | All 6 required strings present; 4-step ordered procedure (deploy RPC → validate → flip → remediate) |
| `CLAUDE.md` | Phase 2 Living Ledger entry `[2026-05-26 14:55]` | ✓ VERIFIED | Entry present at byte offset 218840; 6999 chars; contains `lookup_attribution_bulk`, `run_claimer_remediation`, `PrefetchAttributionTests`, `TestHistoricalClaimerRegression`, `973 passed`, 3 new durable rules |
| `tests/test_billing_audit_shadow.py` | `PrefetchAttributionTests` (8 tests) + `ResolveClaimerMapAwareTests` (7 tests) | ✓ VERIFIED | Both classes present; `test_historical_row_resolves_real_claimer_from_map`, `test_historical_row_no_frozen_falls_back_to_current`, `test_fetch_failure_direct_hold_zero_supabase_calls` all present |
| `tests/test_primary_claim_attribution.py` | `TestHistoricalClaimerRegression` with run 26439205107 evidence anchor | ✓ VERIFIED | Class present; `26439205107` anchor present; `_NO_MATCH` absence assertions present |
| `tests/test_claimer_remediation.py` | 9 tests covering D-06/D-07/D-08/D-12/D-14 | ✓ VERIFIED | File created; 9 tests across 8 classes; `_ensure_smartsheet_mocked` defined inline (not imported from deleted file); `valid_wr_weeks=None` and populated branches tested |
| `tests/test_attribution_resolution_scope.py` | DELETED (D-05 — tested now-deleted helpers) | ✓ VERIFIED | File does not exist |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `generate_weekly_pdfs.py` bulk prefetch block | `billing_audit/writer.py:prefetch_attribution` | `_prefetch_attribution` alias | ✓ WIRED | `_prefetch_attribution = _billing_audit_writer.prefetch_attribution`; single call before grouping loop; `_attr_map, _attr_status = _prefetch_attribution(_prefetch_pairs)` |
| `generate_weekly_pdfs.py` B consumer | `resolve_claimer(prefetched_map=_attr_map)` | `_resolve_claimer_b(... prefetched_map=_attr_map)` | ✓ WIRED | O(1) map read at each B row; D-04 direct-HOLD when `_attr_status == 'fetch_failure'` |
| `generate_weekly_pdfs.py` C consumer | `resolve_claimer(prefetched_map=_attr_map)` | `_resolve_claimer_c(... prefetched_map=_attr_map)` | ✓ WIRED | Same pattern as B; `_vac_crew_claimer_map` populated via O(1) reads |
| `generate_weekly_pdfs.py` D consumer | `resolve_claimer(prefetched_map=_attr_map)` | `_resolve_claimer_d(... prefetched_map=_attr_map)` | ✓ WIRED | Primary path uses-current on failure (no HOLD — per design) |
| `generate_weekly_pdfs.py` sub-helper | `resolve_claimer(prefetched_map=_attr_map)` | `_resolve_claimer_sh(... prefetched_map=_attr_map)` | ✓ WIRED | Phase 1.1 path wired to shared `_attr_map` |
| `billing_audit/writer.py:prefetch_attribution` | `billing_audit.lookup_attribution_bulk` Supabase RPC | `with_retry(op="lookup_attribution_bulk")` | CONDITIONAL | Code wiring is correct (distinct op id D-13; chunked at 500); RPC not yet deployed to live Supabase (operator prerequisite) |
| `generate_weekly_pdfs.py:run_claimer_remediation` | Smartsheet attachment delete | `client.Attachments.delete_attachment(sheet_id, att_id)` | ✓ WIRED | Called in execute path (not dry-run); gated on `REMEDIATE_CLAIMERS`; isolated dispatch returns before Excel generation |
| `CLAUDE.md Phase 2 entry` | `operations.md` runbook | Cross-reference | ✓ WIRED | Entry references D-09/D-10/D-11 and cites `46cd05d` revert commit; runbook documents the same 4-step procedure |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `generate_weekly_pdfs.py` B consumer | `_sub_primary_claimer_map` | `_prefetch_attribution(_prefetch_pairs)` → `prefetch_attribution` → `billing_audit.lookup_attribution_bulk` RPC | Conditional on RPC deployment | CONDITIONAL — data flow correct; Supabase table must exist |
| `generate_weekly_pdfs.py` C consumer | `_vac_crew_claimer_map` | Same bulk prefetch | Conditional on RPC deployment | CONDITIONAL |
| `generate_weekly_pdfs.py` D consumer | `_primary_claimer_map` | Same bulk prefetch | Conditional on RPC deployment | CONDITIONAL |
| `run_claimer_remediation` | `attachment_list` | `client.Attachments.list_row_attachments(sheet_id, row.id)` | Yes (live Smartsheet API call) | ✓ FLOWING — reads from actual Smartsheet; gated on `REMEDIATE_CLAIMERS` default-OFF |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| pytest full suite passes | `pytest tests/ -q` | 973 passed / 26 skipped / 69 subtests | ✓ PASS |
| `ATTRIBUTION_RESOLUTION_WEEKS` fully removed from executable code | Python grep in generate_weekly_pdfs.py | 0 live code references (3 in comments only) | ✓ PASS |
| `_attribution_week_in_scope` fully removed | Python grep | 0 occurrences | ✓ PASS |
| `lookup_attribution_bulk` in schema.sql | Python grep | Function definition present with `jsonb_to_recordset` | ✓ PASS |
| D-04 direct-HOLD code in generate_weekly_pdfs.py | Python grep for `fetch_failure` in HOLD construction | 2 live HOLD constructions (B and C) | ✓ PASS |
| `REMEDIATE_CLAIMERS: '0'` pinned in workflow | Python grep | Present | ✓ PASS |
| `test_attribution_resolution_scope.py` deleted | File existence check | File does not exist | ✓ PASS |
| `SUPABASE_HASH_STORE_AUTHORITATIVE` not flipped in workflow | Python grep for `'1'` | Only `'0'` present (D-11 preserved) | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SPEC-1 / D-01/D-02/D-03 | 02-01-PLAN | `lookup_attribution_bulk` RPC + `prefetch_attribution` + O(1) `resolve_claimer` | ✓ SATISFIED | Schema function, writer function, 4 consumer sites in generate_weekly_pdfs.py |
| SPEC-2 / D-04 | 02-02-PLAN | Direct-HOLD contract on fetch_failure; no garbage names | CONDITIONAL | Code correct; deployment prerequisite exists (CR-01 BLOCKER) |
| SPEC-3 / D-05 | 02-02-PLAN | `ATTRIBUTION_RESOLUTION_WEEKS` + helpers + gates fully removed | ✓ SATISFIED | 0 live references; helpers deleted; workflow/docs updated; test file deleted |
| SPEC-4 / D-06/D-07/D-08 | 02-03-PLAN | Default-OFF remediation mode with dry-run, window filter, live-identity exemption | ✓ SATISFIED | `run_claimer_remediation` implemented; 9 tests pass; workflow pinned |
| SPEC-5 / D-09/D-10/D-11 | 02-04-PLAN | E re-activation runbook with evidence-based validation gate + human-gated flip | ✓ SATISFIED | operations.md section present with 4-step procedure; `SUPABASE_HASH_STORE_AUTHORITATIVE` remains `'0'` |
| SPEC-6 | All plans | Regression coverage — named test classes pass; 973/26 | ✓ SATISFIED | All named test classes verified; pytest count matches |
| D-12 (valid_wr_weeks=None accepted) | 02-03-PLAN | Isolation path accepts None; live-identity exemption when populated | ✓ SATISFIED | `TestIsolationPathValidWrWeeksNone` passes; `TestLiveIdentityExemption` passes |
| D-13 (op-isolation) | 02-01-PLAN | `lookup_attribution_bulk` uses distinct op id | ✓ SATISFIED | `op="lookup_attribution_bulk"` distinct from `freeze_attribution`/`pipeline_run_*`/`lookup_attribution`/`lookup_group_hash` |
| D-14 (build_group_identity reused for parsing) | 02-03-PLAN | `build_group_identity` parses each filename; unparseable skipped | ✓ SATISFIED | `TestUnparseableFilesIgnored` passes; `build_group_identity` call inside `run_claimer_remediation` |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.github/workflows/weekly-excel-generation.yml` | `REMEDIATE_CLAIMERS: '0'` block | No `workflow_dispatch` input binding for `REMEDIATE_CLAIMERS` — documented activation path doesn't exist (WR-02 from 02-REVIEW.md) | Warning | Operator must edit the workflow YAML directly to activate remediation; cannot trigger via `workflow_dispatch` UI as the runbook implies |
| `generate_weekly_pdfs.py` | bulk prefetch block | No `ATTRIBUTION_BULK_PREFETCH_FALLBACK` env var — on RPC unavailability, B/C HOLD all rows (D-04) rather than degrading to per-row lookup (CR-01 BLOCKER from 02-REVIEW.md) | Blocker | If operator deploys code before RPC, all reduced_sub + aep_billable + vac_crew billing files are suppressed for that run |
| `generate_weekly_pdfs.py` | `run_claimer_remediation` comment | Comment explains the `valid_wr_weeks=None` isolation path but uses wording "can delete valid `_Unknown_Foreman` files" — potentially misleading (WR-04 from 02-REVIEW.md) | Info | Docstring/comment alignment; no functional impact |

---

### Human Verification Required

#### 1. Supabase RPC Deployment Status

**Test:** In Supabase SQL Editor, run:
```sql
SELECT billing_audit.lookup_attribution_bulk('[{"wr":"WR_TEST","week_ending":"2026-05-19"}]');
```
**Expected:** Query executes and returns an empty array (no PGRST106 "schema not exposed" or 42P01 "relation does not exist" error)
**Why human:** Cannot verify live Supabase project schema state from codebase inspection alone. This is the prerequisite for SPEC-2 to be fully achieved.

#### 2. Remediation Dry-Run Against Known Garbage Attachments

**Test:** Set `REMEDIATE_CLAIMERS=1` and `REMEDIATION_DRY_RUN=1` in a test `workflow_dispatch` run (requires editing the workflow YAML — see WR-02 anti-pattern above). Review dry-run output.
**Expected:** Run logs show `DRY-RUN would delete` entries for `*_NO_MATCH*` and `*_Unknown_Foreman*` files from run 26439205107; files whose `build_group_identity` 4-tuple is in `valid_wr_weeks` are logged as EXEMPTED; script returns before any Excel generation
**Why human:** Requires access to Smartsheet sheets with actual garbage attachments from the incident; cannot simulate from static code inspection.

#### 3. Production Run Verification Under New Code (with RPC deployed)

**Test:** After deploying `lookup_attribution_bulk` RPC, trigger a production run and inspect the startup banner + run log.
**Expected:** Startup banner shows `ATTRIBUTION_RESOLUTION_WEEKS` is absent; new banner line for bulk prefetch status; all B/C/D pre-passes show `O(1) map read` pattern; no `_NO_MATCH` / `_Unknown_Foreman` in generated filenames; `SUPABASE_HASH_STORE_AUTHORITATIVE=0` confirmed
**Why human:** Requires a live production run with the operator-deployed RPC; static analysis cannot confirm runtime behavior.

---

### Gaps Summary

**One conditional gap blocks full goal achievement for SPEC-2.**

The bulk attribution prefetch wiring in `generate_weekly_pdfs.py` correctly implements D-04 (direct-HOLD on `fetch_failure`) — there are zero garbage filenames produced once the code runs with a deployed RPC. However, the code has no fallback path for the period between code deployment and RPC deployment. If a production run fires before the operator applies `billing_audit.lookup_attribution_bulk(...)` to the Supabase project:

- `prefetch_attribution` returns `({}, 'fetch_failure')`
- B consumer: all completed `reduced_sub`/`aep_billable` rows enter the `_attr_status == 'fetch_failure'` HOLD path → `_sub_primary_claimer_map[_rid]` set to HOLD outcome for every row
- C consumer: all completed `vac_crew` rows similarly HOLD
- D consumer: uses-current (per design, no HOLD) — primary billing files ARE generated
- Result: zero `_ReducedSub_User_*`, `_AEPBillable_User_*`, `_VacCrew_*` files for that run

This is the CR-01 BLOCKER from `02-REVIEW.md`, confirmed by codebase inspection (no `ATTRIBUTION_BULK_PREFETCH_FALLBACK` or equivalent exists anywhere in the codebase).

**The gap is an operator-action dependency, not a code defect.** The deployment sequence is documented in `website/docs/runbook/operations.md` (Step 1: deploy RPC; Step 2: validate; Step 3: flip AUTHORITATIVE). The code is architecturally correct. The gap manifests only if an operator skips or reorders steps.

**Recommendation:** Consider adding a `ATTRIBUTION_BULK_PREFETCH_FALLBACK=0` env var (default OFF — maintains current D-04 contract; set to `1` to degrade to per-row `lookup_attribution` calls instead of HOLD). This would protect the deployment window without changing the steady-state architecture.

The remaining five phase requirements (SPEC-1, SPEC-3, SPEC-4, SPEC-5, SPEC-6) are fully verified in code.

---

_Verified: 2026-05-26T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
