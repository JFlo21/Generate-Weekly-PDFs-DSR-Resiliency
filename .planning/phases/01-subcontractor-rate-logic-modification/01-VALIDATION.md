---
phase: 01
slug: subcontractor-rate-logic-modification
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
validated: 2026-05-26
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Reconstructed retroactively (State B — no VALIDATION.md existed at execution
> time) from the 14 PLAN/SUMMARY artifacts + 01-VERIFICATION.md against the
> shipped test suite.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (unittest.TestCase classes) + pytest-subtests |
| **Config file** | none (pytest discovers `tests/`) |
| **Quick run command** | `pytest tests/test_subcontractor_pricing.py -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~3.3 s (3 Phase-01 files) / ~6 s (full suite) |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_subcontractor_pricing.py tests/test_security_audit_followup.py tests/test_performance_optimizations.py -q`
- **After every plan wave:** `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~6 seconds

---

## Per-Task Verification Map

Phase 01 shipped 7 functional requirements (SUB-01..07) across the original 6
plans, then 12 review-finding fixes (CR/WR/IN) across gap-closure plans 01-07..01-14.
Each row pins the requirement/finding to its covering automated test and the
delivering plan(s). No SECURITY.md exists for this phase → Threat Ref `—`.

### Functional requirements

| Task ID | Plan | Wave | Requirement | Threat Ref | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|----------|-----------|-------------------|-------------|--------|
| SUB-01 | 01-02, 01-03 | 1-2 | SUB-01 | — | `_AEPBillable` (Snapshot ≥ 2026-04-12) priced via `new_*_price` | unit | `pytest tests/test_subcontractor_pricing.py::TestSubcontractorVariantPriceSubstitution tests/test_subcontractor_pricing.py::TestResolveRowPriceCanonicalColumnNames tests/test_subcontractor_pricing.py::TestResolveRowPriceAbbreviatedWorkType -q` | ✅ | ✅ green |
| SUB-02 | 01-02, 01-03 | 1-2 | SUB-02 | — | `_ReducedSub` (every sub WR) priced via `reduced_*_price` | unit | `pytest tests/test_subcontractor_pricing.py::TestSubcontractorVariantFilenameSuffixes tests/test_subcontractor_pricing.py::TestSubcontractorVariantPriceSubstitution -q` | ✅ | ✅ green |
| SUB-03 | 01-04 | 2 | SUB-03 | — | Dual-target routing (`_AEPBillable`+`_ReducedSub`→TARGET; `_ReducedSub`→PPP) | unit | `pytest tests/test_security_audit_followup.py::TestPppCleanupUntrackedAttachments tests/test_performance_optimizations.py::TestPppAttachmentPrefetchBudget -q` | ✅ | ✅ green |
| SUB-04 | 01-01, 01-03 | 1-2 | SUB-04 | — | CSV authoritative rate source; missing-CU WARNING (`Subcontractor rates CSV missing`) | unit + grep | `pytest tests/test_subcontractor_pricing.py::TestResolveRowPriceQuantityCoercion -q` ; `grep -c "Subcontractor rates CSV missing" generate_weekly_pdfs.py` (=2) | ✅ | ✅ green |
| SUB-05 | 01-02, 01-03, 01-04 | 1-2 | SUB-05 | — | Foreman change → BOTH `_AEPBillable_Helper_<name>` AND `_ReducedSub_Helper_<name>` shadow files | unit | `pytest tests/test_subcontractor_pricing.py::TestHelperShadowVariantFileIdentifier tests/test_subcontractor_pricing.py::TestSubcontractorHelperVariantDeptJobDisplay -q` | ✅ | ✅ green |
| SUB-06 | 01-01..01-04 | 1-2 | SUB-06 | — | Zero impact to ORIG-folder / VAC-crew (byte-identical hashes, kill-switch scope) | regression | `pytest tests/test_subcontractor_pricing.py::TestPhase1IntegrationRegression tests/test_subcontractor_pricing.py::TestSubcontractorVariantKillSwitchAndScope tests/test_subcontractor_pricing.py::TestOriginalContractFolderSkipsRateRecalc -q` | ✅ | ✅ green |
| SUB-07 | 01-05 | 2 | SUB-07 | — | `billing_audit.pipeline_run.variant` column + writer `effective_variant` | structural | `python -c "import io; s=open('billing_audit/schema.sql',encoding='utf-8').read(); w=open('billing_audit/writer.py',encoding='utf-8').read(); assert 'ADD COLUMN IF NOT EXISTS variant TEXT' in s and 'effective_variant' in w; print('ok')"` | ✅ | ✅ green |

### Gap-closure findings (review fixes — plans 01-07..01-14)

| Task ID | Plan | Wave | Finding | Hardens | Test Type | Automated Command | File Exists | Status |
|---------|------|------|---------|---------|-----------|-------------------|-------------|--------|
| CR-01 | 01-08 | 6 | helper-shadow `file_identifier` 3-site lockstep | SUB-05 | unit | `pytest tests/test_subcontractor_pricing.py::TestHelperShadowVariantFileIdentifier -q` | ✅ | ✅ green |
| CR-02 | 01-07 | 5 | `_key_matches_excluded_wr` variant clauses | SUB-09-adjacent | unit | `pytest tests/test_security_audit_followup.py::TestExcludeWrsMatchesAllVariants -q` | ✅ | ✅ green |
| CR-03 | 01-07 | 5 | `_key_matches_wr` variant clauses | SUB-09-adjacent | unit | `pytest tests/test_security_audit_followup.py::TestWrFilterMatchesAllVariants -q` | ✅ | ✅ green |
| WR-01 | 01-13 | 11 | secondary PPP cleanup invocation | SUB-03 | unit | `pytest tests/test_security_audit_followup.py::TestPppCleanupUntrackedAttachments -q` | ✅ | ✅ green |
| WR-02 | 01-10 | 8 | `SUBCONTRACTOR_PPP_SHEET_ID=''` disable | SUB-03 | unit | `pytest tests/test_subcontractor_pricing.py::TestSubcontractorPppSheetIdEmptyStringDisable -q` | ✅ | ✅ green |
| WR-03 | 01-10 | 8 | defensive raise on empty helper foreman | SUB-05 | unit | `pytest tests/test_subcontractor_pricing.py::TestHelperShadowSuffixDefensiveRaise -q` | ✅ | ✅ green |
| WR-04 | 01-09 | 7 | explicit `_PII_LOG_MARKERS` for shadow groups | SUB-05 | unit | `pytest tests/test_security_audit_followup.py::TestPiiLogMarkersIncludeSubcontractorVariants -q` | ✅ | ✅ green |
| WR-05 | 01-12 | 10 | secondary PPP attachment prefetch | SUB-03 | unit | `pytest tests/test_performance_optimizations.py::TestPppAttachmentPrefetchBudget -q` | ✅ | ✅ green |
| WR-06 | 01-09 | 7 | `__source_sheet_id` canonical read | SUB-06 | unit | `pytest tests/test_security_audit_followup.py::TestSourceSheetIdFieldConsistency -q` | ✅ | ✅ green |
| IN-01 | 01-11 | 9 | `AEP_BILLABLE_CUTOFF` env override | SUB-01 | unit | `pytest tests/test_subcontractor_pricing.py::TestAepBillableCutoffEnvVarOverride -q` | ✅ | ✅ green |
| IN-02 | 01-11 | 9 | `_resolve_row_price` qty coercion | SUB-01/02 | unit | `pytest tests/test_subcontractor_pricing.py::TestResolveRowPriceQuantityCoercion -q` | ✅ | ✅ green |
| IN-04 | 01-14 | 12 | workflow env-var pinning + Living Ledger | SUB-03/04 | unit | `pytest tests/test_subcontractor_pricing.py::TestPhase1GapClosureLedgerEntryPresent -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Sampling continuity: every requirement and every gap-closure finding has a passing
automated command. No run of 3 consecutive items lacks an automated verify. The
SUB-07 structural check uses an INLINE `python -c` string assertion (no
executor-created-script dependency). IN-03 was reference-only per 01-REVIEW.md
(not a Phase 1 finding) — intentionally excluded.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Phase 01 added 11 new test
classes across 3 pre-existing pytest files (`tests/test_subcontractor_pricing.py`,
`tests/test_security_audit_followup.py`, `tests/test_performance_optimizations.py`)
during execution — no separate Wave 0 scaffolding was required, and none is
retroactively needed: all 7 functional requirements + 12 gap-closure findings
already have passing automated coverage (376 passed / 62 subtests across the 3
Phase-01 files; 0 gaps).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First scheduled GHA production run E2E | SUB-01..07 (ROADMAP SC-5 in-production) | Requires the live Smartsheet subcontractor folder + GHA cron; the verifier cannot execute the live API path | Allow the next `weekly-excel-generation.yml` run with `SUBCONTRACTOR_RATE_VARIANTS_ENABLED='1'`; confirm `_AEPBillable`/`_ReducedSub` (+ helper-shadow) files in `generated_docs/<week>/`, dual-target attachments, byte-identical ORIG/VAC/primary hashes, zero new variant-scope Sentry events |
| Step B real-data SKIP_UPLOAD price-write | SUB-01, SUB-02, SUB-04 | Local operator env lacks `SMARTSHEET_API_TOKEN`; needs subcontractor-sheet read access | `SKIP_UPLOAD=true python generate_weekly_pdfs.py`; assert Pricing col H = rate × qty from `data/subcontractor_rates.csv`, one WARNING per affected sheet for missing CUs |
| One-time Supabase `schema.sql` apply | SUB-07 | Schema apply lives in the Supabase Dashboard UI; verifier cannot execute against the deployed project | Supabase Dashboard → SQL Editor → paste `billing_audit/schema.sql` → Run; `ADD COLUMN IF NOT EXISTS variant TEXT` is idempotent |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra covers all)
- [x] No watch-mode flags
- [x] Feedback latency < ~6s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated (all tasks green; retroactive State-B reconstruction)

---

## Validation Audit 2026-05-26

Retroactive State-B reconstruction (no VALIDATION.md existed at execution time).
Built the requirement-to-test map from the 14 PLAN/SUMMARY artifacts +
01-VERIFICATION.md, confirmed every covering test class is present
(`grep ^class`), and ran every automated command. No gaps — every functional
requirement (SUB-01..07) and every gap-closure finding (CR-01..03, WR-01..06,
IN-01/02/04) has passing automated coverage, so no `gsd-nyquist-auditor` spawn
was required.

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated (manual-only) | 3 (pre-declared: prod cron run, Step B price-write, Supabase schema apply) |

**Evidence (commands run 2026-05-26):**

| Check | Result |
|-------|--------|
| `pytest tests/test_subcontractor_pricing.py tests/test_security_audit_followup.py tests/test_performance_optimizations.py -q` | 376 passed, 62 subtests passed |
| 16 Phase-01 test classes present (`grep ^class`) | all found across 3 files |
| SUB-07 structural assert (schema variant column + writer `effective_variant`) | PASS |
| SUB-04 missing-CU WARNING marker present | PASS (count=2) |

**Conclusion:** Phase 01 is Nyquist-compliant. The 3 manual-only verifications are
correctly deferred operator-action items (live Smartsheet/GHA run, token-gated
price-write, Supabase Dashboard apply), not validation gaps.
