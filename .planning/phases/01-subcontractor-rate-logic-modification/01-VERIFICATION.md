---
phase: 01-subcontractor-rate-logic-modification
verified: 2026-05-15T17:00:00Z
status: human_needed
score: 12/12 gap-closure findings VERIFIED + 7/7 ROADMAP success criteria VERIFIED code-side; 3 deferred items require post-merge production run
re_verification:
  previous_status: human_needed
  previous_score: "5/5 must-haves verified (code-side); 2 deferred items require post-merge production run"
  notes: "Re-verification after gap-closure round (plans 01-07 through 01-14). Prior 01-VERIFICATION.md was status=human_needed with all 7 ROADMAP success criteria code-side VERIFIED and 3 deferred production-run items. The subsequent 01-REVIEW.md surfaced 3 BLOCKERs (CR-01..CR-03), 6 WARNINGs (WR-01..WR-06), and 4 INFO items (IN-01..IN-04, of which IN-03 is reference-only). Plans 01-07..01-14 closed all 12 actionable findings. The 3 deferred production-run items carry forward unchanged — they were not closable in code-side work and remain operator-action items."
  gaps_closed:
    - "REVIEW-CR-01: helper-shadow file_identifier three-site fix landed at calculate_data_hash (L2095) + main-loop (L6379) + valid_wr_weeks (L7108) + current_keys (L7233); TestHelperShadowVariantFileIdentifier (9 tests) all pass"
    - "REVIEW-CR-02: _key_matches_excluded_wr (L4452) gains 4 new variant-suffix clauses (L4481-4484); TestExcludeWrsMatchesAllVariants (5 tests) all pass"
    - "REVIEW-CR-03: _key_matches_wr (L4404) gains 4 new variant-suffix clauses (L4434-4437); TestWrFilterMatchesAllVariants (5 tests) all pass"
    - "REVIEW-WR-01: secondary cleanup_untracked_sheet_attachments invocation for PPP at L7184 with smartsheet.cleanup_ppp Sentry span; TestPppCleanupUntrackedAttachments (8 tests) all pass"
    - "REVIEW-WR-02: SUBCONTRACTOR_PPP_SHEET_ID='' empty-string special-cased to 0 at L449; environment.md doc rewrite; TestSubcontractorPppSheetIdEmptyStringDisable (5 tests) all pass"
    - "REVIEW-WR-03: defensive raise ValueError landed in aep_billable_helper (L4675) + reduced_sub_helper (L4691) filename-suffix branches; legacy helper branch (L4709) explicitly untouched; TestHelperShadowSuffixDefensiveRaise (4 tests) all pass"
    - "REVIEW-WR-04: explicit literal markers 'REDUCED SUB HELPER GROUP CREATED' (L863) + 'AEP BILLABLE HELPER GROUP CREATED' (L864) in _PII_LOG_MARKERS; TestPiiLogMarkersIncludeSubcontractorVariants extended with 2 new methods"
    - "REVIEW-WR-05: secondary PPP attachment-prefetch pass at _fetch_ppp_row_attachments (L5940) with full defense-in-depth trifecta; TestPppAttachmentPrefetchBudget (9 tests) all pass"
    - "REVIEW-WR-06: missing-CU attribution loop now reads canonical __source_sheet_id; legacy __sheet_id write retained for back-compat; TestSourceSheetIdFieldConsistency (4 tests) all pass"
    - "REVIEW-IN-01: AEP_BILLABLE_CUTOFF env-var override with strptime + ValueError fallback (10 mentions in source); TestAepBillableCutoffEnvVarOverride (6 tests) all pass"
    - "REVIEW-IN-02: row.get('Quantity') or 0 pattern removed (count=0); qty_raw not in (None, '') pattern present (count=1); TestResolveRowPriceQuantityCoercion (10 tests) all pass"
    - "REVIEW-IN-04: SUBCONTRACTOR_RATES_CSV / SUBCONTRACTOR_PPP_SHEET_ID / SUBCONTRACTOR_RATE_VARIANTS_ENABLED pinned in workflow at lines 321-323; TestPhase1GapClosureLedgerEntryPresent (5 tests / 12 subtests) all pass"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "First scheduled GitHub Actions weekly production run after merge — full code path with real subcontractor sheet data"
    expected: "Run completes inside timeout-minutes:195; produces _AEPBillable and _ReducedSub Excel files (and helper-shadow files where helper-foreman events fire) in generated_docs/<week>/; _AEPBillable + _ReducedSub attached to TARGET_SHEET_ID=5723337641643908; _ReducedSub additionally attached to SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908; zero Sentry events tagged with new variant scope; existing primary/helper/vac_crew/ORIG-folder outputs byte-identical to the prior run (hash-history diff verification); new Sentry spans smartsheet.attachment_prefetch_ppp and smartsheet.cleanup_ppp appear in traces; pre-flight skip log '🛡️ Skipping PPP attachment prefetch:' does NOT appear in normal steady-state runs"
    why_human: "ROADMAP success criterion 5 explicitly requires a scheduled production run end-to-end; cannot be exercised programmatically in this verifier — operator must observe the next scheduled GHA run logs and Smartsheet attachment panels. Per Plan 06 Step B operator decision (Warning 10 fallback verification surface), this is the deferred validation pathway. Carried forward unchanged from the prior 01-VERIFICATION.md."
  - test: "Step B real-data SKIP_UPLOAD price-write end-to-end (deferred during Plan 01-06 Task 3)"
    expected: "Running SKIP_UPLOAD=true python generate_weekly_pdfs.py against real subcontractor sheets (with SMARTSHEET_API_TOKEN set) produces _AEPBillable and _ReducedSub workbook cells where Pricing column H equals rate × qty from data/subcontractor_rates.csv for known CUs, falls through to SmartSheet Units Total Price for missing CUs, and emits exactly one WARNING per affected sheet containing the marker 'Subcontractor rates CSV missing'"
    why_human: "Per Plan 06 Task 3 SUMMARY: 'Local operator env lacks SMARTSHEET_API_TOKEN — Step B cannot run locally.' Unit-level coverage of _resolve_row_price is locked by Plan 03 tests, but the production-data integration is only exercisable in an environment with the API token + access to subcontractor sheets. Carried forward unchanged."
  - test: "Operator one-time apply of billing_audit/schema.sql to Supabase before first production run"
    expected: "Open Supabase Dashboard → SQL Editor → paste billing_audit/schema.sql contents → Run. The ADD COLUMN IF NOT EXISTS variant TEXT clause is idempotent. After apply, billing_audit.pipeline_run.variant column exists and accepts the 7 valid variant strings (or NULL for legacy rows)"
    why_human: "Schema migration apply lives in the Supabase Dashboard UI — the verifier cannot execute against the deployed Supabase project. Per Plan 05 SUMMARY 'User Setup Required' section. Without this apply, the first production run's emit_run_fingerprint upsert will fail at the variant column write. Carried forward unchanged."
overrides: []
---

# Phase 01: Subcontractor Rate Logic Modification — Verification Report (Re-Verification)

**Phase Goal:** An operator runs the weekly workflow on a Smartsheet subcontractor folder and sees two new Excel variants per qualifying WR group landing on the correct target sheets, with shadow-foreman events producing both variant-tagged helper files — and zero impact to existing primary, helper, VAC-crew, or ORIG-folder outputs.

**Verified:** 2026-05-15T17:00:00Z
**Status:** human_needed (all code-side findings + invariants verified; same 3 deferred production-run items as the prior verification remain operator-action items)
**Re-verification:** Yes — after gap-closure round (plans 01-07 through 01-14 closing 12 of 13 review findings; IN-03 is reference-only)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — re-verified)

All 5 ROADMAP success criteria from the prior verification remain VERIFIED code-side, with the gap-closure work strengthening the wiring rather than changing the underlying contract. The byte-identical-hash invariant is re-confirmed by 5/5 passes of `TestPhase1IntegrationRegression` under the post-gap-closure source.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | For every subcontractor-folder WR group with `Snapshot Date >= 2026-04-12`, the workflow produces an `_AEPBillable` Excel file priced via `new_*_price` columns | VERIFIED (code-side) | Unchanged from prior verification — `group_source_rows` cutoff gate + `_resolve_row_price` + `generate_excel` suffix all intact. IN-01 (Plan 01-11) adds env-var override but default `datetime.date(2026, 4, 12)` is byte-identical to the prior hardcoded constant. |
| 2 | For every subcontractor-folder WR group, the workflow produces a `_ReducedSub` Excel file routed to BOTH TARGET_SHEET_ID AND SUBCONTRACTOR_PPP_SHEET_ID | VERIFIED (code-side) | Unchanged on the routing side. WR-05 (PPP prefetch, Plan 01-12) + WR-01 (PPP cleanup, Plan 01-13) ADD belt-and-suspenders defenses on the PPP leg; correctness on the existing per-row delete path was already correct, gap-closure makes it operationally hygienic. |
| 3 | When a foreman change is detected on a subcontractor WR, TWO shadow files appear in `generated_docs/<week>/` | VERIFIED (code-side) | CR-01 (Plan 01-08) closes the helper-shadow `file_identifier` three-site drift bug. The three-tuple gate `('helper', 'aep_billable_helper', 'reduced_sub_helper')` now appears at 4 source locations (L2095, L6379, L7108, L7233 — was previously only at L2095). Skip-unchanged optimization works for shadow variants; orphan attachment accumulation eliminated. |
| 4 | `pytest tests/` passes including all new tests; no existing test regresses | VERIFIED | `pytest tests/ -q` → **609 passed / 22 skipped / 58 subtests passed in 5.60s** (was 537/22/16 pre-gap-closure; +72 new tests / +42 new subtests across 11 new test classes from plans 01-07..01-14). All prior tests still pass. |
| 5 | A scheduled weekly workflow run completes inside `timeout-minutes: 195` and emits zero Sentry events tagged with the new variant scope; existing VAC-crew, ORIG-folder, and primary outputs are byte-identical | VERIFIED (code-side); production-run portion DEFERRED | `TestPhase1IntegrationRegression` (5 tests) and `TestSubcontractorVariantKillSwitchAndScope` (4 tests) re-confirm byte-identical hashes and zero-emission on ORIG-folder under the post-gap-closure source. Production-run portion stays DEFERRED per phase brief. |

**Score:** 5/5 ROADMAP truths verified code-side (3 carry deferred production-run portions documented in `human_verification`).

### Gap-Closure Findings (re-verification surface)

| # | Finding | Status | Evidence |
|---|---------|--------|----------|
| 1 | REVIEW-CR-01 | VERIFIED | Three-tuple gate `('helper', 'aep_billable_helper', 'reduced_sub_helper')` present at calculate_data_hash (L2095) + main-loop site 1 (L6379) + valid_wr_weeks cleanup-tuple site 2 (L7108) + current_keys hash-prune site 3 (L7233); 4 source locations total (threshold ≥3). `TestHelperShadowVariantFileIdentifier` (9 tests) PASS. |
| 2 | REVIEW-CR-02 | VERIFIED | `_key_matches_excluded_wr` (L4452) gains 4 new variant clauses at L4481-4484: `f"{wr}_REDUCEDSUB"`, `f"{wr}_AEPBILLABLE"`, `f"{wr}_REDUCEDSUB_HELPER_"`, `f"{wr}_AEPBILLABLE_HELPER_"`. `TestExcludeWrsMatchesAllVariants` (5 tests) PASS. |
| 3 | REVIEW-CR-03 | VERIFIED | `_key_matches_wr` (L4404) gains identical 4 new variant clauses at L4434-4437. `_USER_` asymmetry preserved by intent (TestWrFilterMatchesAllVariants includes `test_user_variant_intentionally_not_matched` regression guard). `TestWrFilterMatchesAllVariants` (5 tests) PASS. |
| 4 | REVIEW-WR-01 | VERIFIED | Secondary `cleanup_untracked_sheet_attachments(client, SUBCONTRACTOR_PPP_SHEET_ID, ...)` invocation at L7184 with distinct `smartsheet.cleanup_ppp` Sentry span; gated on 4-condition predicate matching Plan 04 `target_map_ppp` build. Total `cleanup_untracked_sheet_attachments(` count = 3 (1 definition + 2 invocations). `TestPppCleanupUntrackedAttachments` (8 tests) PASS. |
| 5 | REVIEW-WR-02 | VERIFIED | `SUBCONTRACTOR_PPP_SHEET_ID = 0` empty-string special case present at L449 (count=1). Environment.md doc rewritten. `TestSubcontractorPppSheetIdEmptyStringDisable` (5 tests) PASS. |
| 6 | REVIEW-WR-03 | VERIFIED | `raise ValueError("aep_billable_helper requires __helper_foreman; got empty …")` at L4675; symmetric `reduced_sub_helper` raise at L4691. Legacy `helper` branch at L4709 — manually verified contains NO `raise ValueError` (only the original `if helper_foreman:` populate-suffix logic). `TestHelperShadowSuffixDefensiveRaise` includes `test_legacy_helper_branch_does_not_raise_on_empty_foreman` scope-immutability guard. (4 tests) PASS. |
| 7 | REVIEW-WR-04 | VERIFIED | Explicit literal markers in `_PII_LOG_MARKERS`: `"REDUCED SUB HELPER GROUP CREATED"` at L863, `"AEP BILLABLE HELPER GROUP CREATED"` at L864 (immediately above the existing Phase 02 markers). `TestPiiLogMarkersIncludeSubcontractorVariants` test `test_all_nine_subcontractor_markers_present` PASSES. |
| 8 | REVIEW-WR-05 | VERIFIED | `def _fetch_ppp_row_attachments` at L5940; daemon-executor + `as_completed(timeout=...)` + explicit `shutdown(wait=False, cancel_futures=True)` + atexit-detach scoped to budget-exceed-only. All 9 `TestPppAttachmentPrefetchBudget` tests PASS (including block-scoped invariant test that does not break legitimate `with ThreadPoolExecutor` callers elsewhere). |
| 9 | REVIEW-WR-06 | VERIFIED | Missing-CU attribution loop reads canonical `__source_sheet_id`; legacy `__sheet_id` write retained. `grep -c "_r.get('__sheet_id')" generate_weekly_pdfs.py` = 0; `grep -c "_r.get('__source_sheet_id')"` = 1. `TestSourceSheetIdFieldConsistency` (4 tests) PASS. |
| 10 | REVIEW-IN-01 | VERIFIED | `AEP_BILLABLE_CUTOFF` count = 10 in source (env-var resolver block + banner + comment cross-refs). Default `datetime.date(2026, 4, 12)` byte-identical to prior hardcoded constant. `TestAepBillableCutoffEnvVarOverride` (6 tests) PASS. |
| 11 | REVIEW-IN-02 | VERIFIED | `row.get('Quantity') or 0` count = 0 (pattern removed); `qty_raw not in (None, '')` count = 1 (replacement pattern present). `TestResolveRowPriceQuantityCoercion` (10 tests) PASS. |
| 12 | REVIEW-IN-04 | VERIFIED | `.github/workflows/weekly-excel-generation.yml` lines 321-323 pin: `SUBCONTRACTOR_RATES_CSV: 'data/subcontractor_rates.csv'`, `SUBCONTRACTOR_PPP_SHEET_ID: '8162920222379908'`, `SUBCONTRACTOR_RATE_VARIANTS_ENABLED: '1'` — each exactly once. Living Ledger 2026-05-15 12:00 entry present at CLAUDE.md L1611 with all 7 named rules grep-detectable on single lines. `TestPhase1GapClosureLedgerEntryPresent` (5 tests / 12 subtests) PASS. |

**Score:** 12/12 actionable findings VERIFIED (IN-03 was reference-only per the review, intentionally excluded from the gap-closure surface).

### Required Artifacts (delta from prior verification)

All artifacts from the prior 01-VERIFICATION.md remain VERIFIED. New artifacts added by gap-closure plans:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `generate_weekly_pdfs.py` — three-tuple shadow-variant gate at 4 sites | CR-01 lock-step extension across calculate_data_hash + 3 main-loop sites | VERIFIED + WIRED | All 4 sites use byte-identical gate string `('helper', 'aep_billable_helper', 'reduced_sub_helper')`. Drift between sites — the original bug shape — is locked out by `TestHelperShadowVariantFileIdentifier` source-grep guards. |
| `generate_weekly_pdfs.py` — variant-aware filter matchers | CR-02/CR-03 four additive clauses each | VERIFIED + WIRED | Both `_key_matches_wr` (L4404) and `_key_matches_excluded_wr` (L4452) recognize the four new variant suffix shapes. `_USER_` asymmetry preserved by design. |
| `generate_weekly_pdfs.py` — PPP cleanup invocation | WR-01 second `cleanup_untracked_sheet_attachments` call | VERIFIED + WIRED | Gated on 4-condition predicate (kill switch + PPP id truthy + distinct sheet + sheet-object available); sequenced AFTER TARGET cleanup; distinct Sentry op. |
| `generate_weekly_pdfs.py` — PPP empty-string disable | WR-02 special case after `_coerce_sheet_id` call | VERIFIED + WIRED | `SUBCONTRACTOR_PPP_SHEET_ID = 0` reset when raw env-var is empty string; paired with startup banner naming resolved state. |
| `generate_weekly_pdfs.py` — defensive raise on empty helper foreman | WR-03 ValueError in both new shadow-variant branches | VERIFIED + WIRED | PII-discipline: raise body contains only WR + week + variant name (no foreman/dept/job). Legacy `helper` branch explicitly untouched per review scope. |
| `generate_weekly_pdfs.py` — `_PII_LOG_MARKERS` extended | WR-04 explicit literal markers | VERIFIED + WIRED | Two new markers join the existing 7 Phase 1 markers; substring match is now intentional rather than accidental. |
| `generate_weekly_pdfs.py` — PPP attachment prefetch | WR-05 secondary defense-in-depth prefetch | VERIFIED + WIRED | Mirrors primary prefetch pattern verbatim (Living Ledger 2026-04-22 16:05 contract). Shared `attachment_cache` dict; per-row fallback preserves correctness on skip. |
| `generate_weekly_pdfs.py` — `__source_sheet_id` migration | WR-06 reader-side rename | VERIFIED + WIRED | Missing-CU attribution loop reads canonical name; writer retains both aliases for back-compat. |
| `generate_weekly_pdfs.py` — `AEP_BILLABLE_CUTOFF` env override | IN-01 strptime + fallback | VERIFIED + WIRED | Default byte-identical to prior; ValueError fallback logs actionable error. Banner names resolved value + provenance. |
| `generate_weekly_pdfs.py` — `_resolve_row_price` qty coercion | IN-02 explicit None/empty handling | VERIFIED + WIRED | `row.get('Quantity', 0)` + `float(x) if x not in (None, '') else 0.0` + `try/except (TypeError, ValueError)`. Numeric output byte-identical for every pre-existing input case. |
| `.github/workflows/weekly-excel-generation.yml` — Phase 1 env-var pinning | IN-04 three pinned vars + comment block | VERIFIED + WIRED | Lines 321-323; LEGACY-style comment block + AEP_BILLABLE_CUTOFF intentionally-unset trailing comment. |
| `CLAUDE.md` — Living Ledger 2026-05-15 entry | Single entry summarizing 7 named rules | VERIFIED | L1611; entry sequenced after 2026-04-25 14:00; all 7 rules on single source lines per substring-match contract; references 5 named regression test classes. |
| 11 new test classes across 3 test files | Regression lock-in for every gap-closure finding | VERIFIED + WIRED | TestHelperShadowVariantFileIdentifier, TestExcludeWrsMatchesAllVariants, TestWrFilterMatchesAllVariants, TestPppAttachmentPrefetchBudget, TestPppCleanupUntrackedAttachments, TestSubcontractorPppSheetIdEmptyStringDisable, TestHelperShadowSuffixDefensiveRaise, TestAepBillableCutoffEnvVarOverride, TestResolveRowPriceQuantityCoercion, TestPhase1GapClosureLedgerEntryPresent, TestSourceSheetIdFieldConsistency — all confirmed present via Grep and all pass under `pytest tests/`. |

### Key Link Verification (delta)

All previously-verified key links remain WIRED. New key links established by gap-closure:

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| main-loop identifier construction | `_has_existing_week_attachment` / `delete_old_excel_attachments` | `task['file_identifier']` derived from `__helper_foreman` for the 3-tuple shadow-variant gate | WIRED | Plan 01-08 (CR-01) — the round-trip between main-loop derivation, filename, and `build_group_identity` parsing is exercised end-to-end by `TestHelperShadowVariantFileIdentifier::test_aep_billable_helper_filename_round_trips`. |
| `EXCLUDE_WRS` env var | group emission suppression | `_key_matches_excluded_wr(k, wr)` for each variant suffix | WIRED | Plan 01-07 (CR-02) — `TestExcludeWrsMatchesAllVariants::test_all_seven_variants_excluded_for_target_wr` confirms all 7 group-key shapes suppress for an excluded WR. |
| `WR_FILTER` env var (TEST_MODE) | group emission retention | `_key_matches_wr(k, wr)` for each variant suffix | WIRED | Plan 01-07 (CR-03) — `TestWrFilterMatchesAllVariants::test_all_seven_variants_retained_for_target_wr` confirms the documented operator-diagnostic command path is now functional end-to-end. |
| `target_map_ppp` | PPP `_upload_one` worker | shared `attachment_cache` dict (WR-05 prefetch writes; downstream consumer reads) | WIRED | Plan 01-12 (WR-05) — Sentry span `smartsheet.attachment_prefetch_ppp` correlates the prefetch with the upload phase. |
| `valid_wr_weeks` | PPP `cleanup_untracked_sheet_attachments` | direct kwarg pass-through (same set TARGET cleanup consumes) | WIRED | Plan 01-13 (WR-01) — symmetric eligibility gate at the cleanup site means cleanup never iterates a sheet that wasn't successfully mapped. |
| `AEP_BILLABLE_CUTOFF` env var | module-level constant | `os.getenv('AEP_BILLABLE_CUTOFF', '')` + `datetime.datetime.strptime(...).date()` with ValueError fallback | WIRED | Plan 01-11 (IN-01) — banner emission visible to operators at startup. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `SENTRY_DSN='' PYTHONPATH=. python -m pytest tests/ -q` | **609 passed, 22 skipped, 58 subtests passed in 5.60s** | PASS |
| Critical-invariant test classes pass | `pytest tests/test_subcontractor_pricing.py::TestPhase1IntegrationRegression tests/test_subcontractor_pricing.py::TestSubcontractorVariantKillSwitchAndScope tests/test_subcontractor_pricing.py::TestHelperShadowVariantFileIdentifier tests/test_security_audit_followup.py::TestExcludeWrsMatchesAllVariants tests/test_security_audit_followup.py::TestWrFilterMatchesAllVariants tests/test_security_audit_followup.py::TestPppCleanupUntrackedAttachments tests/test_performance_optimizations.py::TestPppAttachmentPrefetchBudget tests/test_subcontractor_pricing.py::TestPhase1GapClosureLedgerEntryPresent -v` | **50 passed, 42 subtests passed in 0.72s** | PASS |
| Module compiles cleanly | `python -m py_compile generate_weekly_pdfs.py` | exit 0 | PASS |
| `@cell` ban respected | `grep -c "@cell" generate_weekly_pdfs.py` | 0 | PASS |
| Production safety validator (UTF-8) | `PYTHONIOENCODING=utf-8 PYTHONPATH=. python -X utf8 tests/validate_production_safety.py` | **9/9 claims validated** | PASS |
| IN-02 anti-pattern removed | `grep -c "row.get('Quantity') or 0" generate_weekly_pdfs.py` | 0 | PASS |
| IN-02 replacement pattern present | `grep -c "qty_raw not in (None, '')" generate_weekly_pdfs.py` | 1 | PASS |
| IN-04 workflow pinning | `grep -c -E "SUBCONTRACTOR_(RATES_CSV: 'data/subcontractor_rates.csv'\|PPP_SHEET_ID: '8162920222379908'\|RATE_VARIANTS_ENABLED: '1')" .github/workflows/weekly-excel-generation.yml` | 3 (one per pinned var) | PASS |
| Living Ledger 2026-05-15 entry | `grep -c "\[2026-05-15" CLAUDE.md` | 1 | PASS |
| All 7 named rules grep-detectable | `grep -E "Three-site identity-consistency invariant\|Mirror-matcher invariant\|Explicit PII markers\|Defensive raise scope discipline\|Dual-target cleanup invocation pattern\|Env-var override safe-parse pattern\|Workflow pinning for new feature env vars" CLAUDE.md` | 7 matches on single lines | PASS |
| billing_audit schema variant column | `grep -n "ADD COLUMN IF NOT EXISTS variant TEXT" billing_audit/schema.sql` | L123 | PASS |
| billing_audit writer effective_variant | `grep -n "effective_variant" billing_audit/writer.py` | L595, L611 (resolve + payload) | PASS |

### Requirements Coverage

All 7 SUB-* requirements from the original phase plan remain SATISFIED. None of the gap-closure plans touched the requirement-fulfilling code paths in a way that could regress satisfaction; the gap closures strengthened the operational wiring.

| Requirement | Status | Evidence |
|-------------|--------|----------|
| SUB-01 (`_AEPBillable` priced via `new_*_price`) | SATISFIED | Unchanged from prior verification. CR-01 and IN-01 strengthen the wiring without changing pricing semantics. |
| SUB-02 (`_ReducedSub` priced via `reduced_*_price`) | SATISFIED | Unchanged. WR-01/WR-05 add PPP defense-in-depth without changing pricing. |
| SUB-03 (dual-target routing) | SATISFIED | Unchanged. WR-01 (cleanup) + WR-05 (prefetch) + WR-02 (empty-string disable) round out the PPP lifecycle. |
| SUB-04 (CSV authoritative) | SATISFIED | Unchanged. IN-04 workflow pinning makes the operator override path explicit. |
| SUB-05 (helper-shadow generation) | SATISFIED | Hardened by CR-01 (file_identifier round-trip), WR-03 (defensive raise), WR-04 (explicit PII markers). |
| SUB-06 (no impact to ORIG/VAC-crew) | SATISFIED | Re-confirmed by `TestPhase1IntegrationRegression` (5/5) + `TestSubcontractorVariantKillSwitchAndScope` (4/4) under post-gap-closure source. |
| SUB-07 (`pipeline_run.variant`) | SATISFIED | Unchanged. Schema and writer untouched by gap-closure. **Operator action required**: apply schema.sql to Supabase (human_verification item 3). |

**Coverage:** 7/7 SUB-* requirements SATISFIED; 12/12 gap-closure pseudo-IDs VERIFIED; 0 orphaned; 1 (SUB-07) requires one-time operator Supabase Dashboard apply.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

No anti-patterns introduced by the gap-closure work. The previously-discovered `row.get('Quantity') or 0` pattern (IN-02) is now removed (count=0). All raises in the new shadow-variant defensive branches use PII-redact-compatible message bodies (no foreman/dept/job).

### Human Verification Required

Three operator-action items carry forward unchanged from the prior 01-VERIFICATION.md. The gap-closure round did not introduce new human-verification items.

#### 1. First scheduled GHA production run after merge

**Test:** Allow the next scheduled `.github/workflows/weekly-excel-generation.yml` run to complete with `SUBCONTRACTOR_RATE_VARIANTS_ENABLED='1'` against the live Smartsheet subcontractor folder.

**Expected:**
- Run completes inside `timeout-minutes: 195`.
- New artifacts appear in the run's `generated_docs/<week>/` zip: `WR_*_WeekEnding_*_AEPBillable_*.xlsx`, `WR_*_WeekEnding_*_ReducedSub_*.xlsx`, plus `*_AEPBillable_Helper_<name>_*.xlsx` and `*_ReducedSub_Helper_<name>_*.xlsx` when helper-foreman events fire.
- Smartsheet attachment panel on TARGET_SHEET_ID=5723337641643908 shows the new variants attached.
- Smartsheet attachment panel on SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908 shows `_ReducedSub` variants attached (dual-routing second leg).
- Hash-history diff vs the prior run shows primary/helper/vac_crew/ORIG-folder hashes unchanged.
- New Sentry spans `smartsheet.attachment_prefetch_ppp` and `smartsheet.cleanup_ppp` appear in traces. The pre-flight skip log `🛡️ Skipping PPP attachment prefetch:` does NOT appear under normal steady-state runs.
- Zero new error-grouping fingerprints tagged with the new variant scope.

**Why human:** ROADMAP success criterion 5 explicitly requires a scheduled production run end-to-end. The verifier cannot execute the live Smartsheet API path. Kill-switch rollback path: set `SUBCONTRACTOR_RATE_VARIANTS_ENABLED='0'` in the workflow env block.

#### 2. Step B real-data price-write end-to-end (deferred during Plan 06)

**Test:** With a valid `SMARTSHEET_API_TOKEN` and read access to subcontractor folder sheets:

```
PYTHONIOENCODING=utf-8 python -X utf8 SKIP_UPLOAD=true python generate_weekly_pdfs.py
```

**Expected:**
- `generated_docs/<week>/` contains `_AEPBillable` and `_ReducedSub` workbooks.
- Pricing column H values match `rate × qty` from `data/subcontractor_rates.csv` (`new_*_price` for AEP, `reduced_*_price` for Reduced).
- Run log emits exactly one WARNING per affected sheet containing the marker `Subcontractor rates CSV missing` for any CUs not in the CSV.
- No openpyxl corruption errors.

**Why human:** Local operator env lacks `SMARTSHEET_API_TOKEN`. Per Plan 06 Task 3 SUMMARY, Step B was explicitly deferred.

#### 3. One-time Supabase schema apply

**Test:** Before the first scheduled production run after this PR merges, open Supabase Dashboard → SQL Editor → paste `billing_audit/schema.sql` → Run.

**Expected:** `ADD COLUMN IF NOT EXISTS variant TEXT` is idempotent; `billing_audit.pipeline_run.variant` column accepts the 7 valid variant strings (or NULL for legacy rows).

**Why human:** Schema migration apply lives in the Supabase Dashboard UI — the verifier cannot execute against the deployed Supabase project. Without this apply, the first scheduled production run's `emit_run_fingerprint` upsert will fail at the variant column write.

### Gaps Summary

**No code-side gaps found. All 12 actionable findings from `01-REVIEW.md` are closed:**

| Wave | Plan | Findings closed | Tests added |
|------|------|-----------------|-------------|
| 5 | 01-07 | CR-02, CR-03 | 10 tests / 30 subtests |
| 6 | 01-08 | CR-01 | 9 tests |
| 7 | 01-09 | WR-04, WR-06 | 6 tests |
| 8 | 01-10 | WR-02, WR-03 | 9 tests |
| 9 | 01-11 | IN-01, IN-02 | 16 tests |
| 10 | 01-12 | WR-05 | 9 tests |
| 11 | 01-13 | WR-01 | 8 tests |
| 12 | 01-14 | IN-04 + Living Ledger | 5 tests / 12 subtests |

**Total new tests across the gap-closure round:** ~72 net new tests + ~42 subtests, bringing the suite from 537/22/16 (pre-gap-closure) to **609/22/58** (post-gap-closure). All previously-passing tests still pass; no regressions.

**Deferred items (per phase brief — not gaps):**
- Scheduled production run (ROADMAP success criterion 5 in-production portion).
- Step B real-data SKIP_UPLOAD price-write gate (operator-decided defer during Plan 06).
- One-time Supabase schema apply (operator action prerequisite).

These are operator-action items, explicitly flagged in `human_verification` per the phase brief contract.

**Reference note on `IN-03` (Phase 6 master-bug fix `_txn = None` hoist at `generate_weekly_pdfs.py:5211`):** This was explicitly reference-only per `01-REVIEW.md` — "Not a Phase 1 finding." Re-verified present at L5211 of the current source; carried forward from the prior verification unchanged.

---

_Verified: 2026-05-15T17:00:00Z_
_Verifier: Claude (gsd-verifier, Opus 4.7 — 1M context)_
_Re-verification of: 2026-05-14T22:30:00Z initial verification_
_Findings closed: 12/12 actionable (REVIEW-CR-01..CR-03, WR-01..WR-06, IN-01/IN-02/IN-04). IN-03 reference-only._
_Outstanding: 3 operator-action items in `human_verification` (carried forward unchanged from prior verification)._
