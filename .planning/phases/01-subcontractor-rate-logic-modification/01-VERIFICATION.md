---
phase: 01-subcontractor-rate-logic-modification
verified: 2026-05-14T22:30:00Z
status: human_needed
score: 5/5 must-haves verified (code-side); 2 deferred items require post-merge production run
re_verification:
  previous_status: none
  notes: "Initial verification — no prior 01-VERIFICATION.md existed"
human_verification:
  - test: "First scheduled GitHub Actions weekly production run after merge — full code path with real subcontractor sheet data"
    expected: "Run completes inside timeout-minutes:195; produces _AEPBillable and _ReducedSub Excel files (and helper-shadow files where helper-foreman events fire) in generated_docs/<week>/; _AEPBillable + _ReducedSub attached to TARGET_SHEET_ID=5723337641643908; _ReducedSub additionally attached to SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908; zero Sentry events tagged with new variant scope; existing primary/helper/vac_crew outputs byte-identical to the prior run (hash-history diff verification)"
    why_human: "ROADMAP success criterion 5 explicitly requires a scheduled production run end-to-end; cannot be exercised programmatically in this verifier — operator must observe the next scheduled GHA run logs and Smartsheet attachment panels. Per Plan 06 Step B operator decision (Warning 10 fallback verification surface), this is the deferred validation pathway."
  - test: "Step B real-data price-write end-to-end (deferred during Plan 01-06 Task 3)"
    expected: "Running SKIP_UPLOAD=true python generate_weekly_pdfs.py against real subcontractor sheets (with SMARTSHEET_API_TOKEN set) produces _AEPBillable and _ReducedSub workbook cells where Pricing column H equals rate × qty from data/subcontractor_rates.csv for known CUs, falls through to SmartSheet Units Total Price for missing CUs, and emits exactly one WARNING per affected sheet containing the marker 'Subcontractor rates CSV missing'"
    why_human: "Per Plan 06 Task 3 SUMMARY: 'Local operator env lacks SMARTSHEET_API_TOKEN — Step B cannot run locally.' Unit-level coverage of _resolve_row_price is locked by Plan 03 tests (TestResolveRowPriceCanonicalColumnNames + TestSubcontractorVariantPriceSubstitution write a real openpyxl workbook with rate×qty cells), but the production-data integration is only exercisable in an environment with the API token + access to subcontractor sheets."
  - test: "Operator one-time apply of billing_audit/schema.sql to Supabase before first production run"
    expected: "Open Supabase Dashboard → SQL Editor → paste billing_audit/schema.sql contents → Run. The ADD COLUMN IF NOT EXISTS variant TEXT clause is idempotent. After apply, billing_audit.pipeline_run.variant column exists and accepts the 7 valid variant strings (or NULL for legacy rows)"
    why_human: "Schema migration apply lives in the Supabase Dashboard UI — the verifier cannot execute against the deployed Supabase project. Per Plan 05 SUMMARY 'User Setup Required' section. Without this apply, the first production run's emit_run_fingerprint upsert will fail at the variant column write (the column needs to exist before the writer can populate it)."
overrides: []
---

# Phase 01: Subcontractor Rate Logic Modification — Verification Report

**Phase Goal:** An operator runs the weekly workflow on a Smartsheet subcontractor folder and sees two new Excel variants per qualifying WR group landing on the correct target sheets, with shadow-foreman events producing both variant-tagged helper files — and zero impact to existing primary, helper, VAC-crew, or ORIG-folder outputs.

**Verified:** 2026-05-14T22:30:00Z
**Status:** human_needed (all code-side artifacts verified; production-run validation deferred per phase brief)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | For every subcontractor-folder WR group with `Snapshot Date >= 2026-04-12`, the workflow produces an `_AEPBillable` Excel file whose row totals match the `new_*_price` columns of `data/subcontractor_rates.csv`, attached to `TARGET_SHEET_ID=5723337641643908` | VERIFIED (code-side) | `group_source_rows` L4161-4172 gates `aep_key = f"{week}_{wr}_AEPBILLABLE"` emission on `_snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF (2026-04-12)`. `generate_excel` L4506-4507 produces `_AEPBillable` variant_suffix. `_resolve_row_price` L1419 reads `new_{wt}_price` for `aep_billable` variant. `_build_upload_tasks_for_group` L5140-5153 routes to TARGET_SHEET_ID. End-to-end resolver test: sample CU `ALB-6-AUR1` (new_install_price=$52.58) × qty=5 returns 262.9. Production run with real data: DEFERRED to first scheduled GHA run. |
| 2 | For every subcontractor-folder WR group (regardless of snapshot date), the workflow produces a `_ReducedSub` Excel file priced via `reduced_*_price` CSV columns, attached to BOTH `5723337641643908` AND `SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908` | VERIFIED (code-side) | `group_source_rows` L4144-4150 emits `reduced_key = f"{week}_{wr}_REDUCEDSUB"` unconditionally on subcontractor rows. `generate_excel` L4508-4509 produces `_ReducedSub` variant_suffix. `_resolve_row_price` L1421-1422 reads `reduced_{wt}_price`. `_build_upload_tasks_for_group` L5140-5153 (primary leg) + L5167-5181 (PPP leg) emits 2 tasks for `reduced_sub`/`reduced_sub_helper` variants. End-to-end resolver test: CU `ALB-6-AUR1` (reduced_install_price=$45.95) × 5 = 229.75. Production run with real data: DEFERRED. |
| 3 | When a foreman change is detected on a subcontractor WR, TWO shadow files appear in `generated_docs/<week>/` named `_AEPBillable_Helper_<name>` and `_ReducedSub_Helper_<name>`, each routed to its variant's target sheet | VERIFIED (code-side) | `group_source_rows` L4199-4243 — helper-shadow gate piggybacks on `valid_helper_row + helper_mode_enabled`; emits `_REDUCEDSUB_HELPER_<sanitized>` unconditionally and `_AEPBILLABLE_HELPER_<sanitized>` when snapshot ≥ cutoff. `generate_excel` L4510-4519 produces `_AEPBillable_Helper_<name>` and `_ReducedSub_Helper_<name>` suffixes. Routing inherits from parent variant (PPP routes only `_ReducedSub*`). Round-trip parser confirmed for all 7 variants. Production run: DEFERRED. |
| 4 | `pytest tests/` passes including new tests covering subcontractor variant generation, CSV rate loader schema validation, hash-key extension with new variant strings, `build_group_identity` round-trip, `target_map` collision quarantine, and `freeze_row` variant attribution. No existing test regresses. | VERIFIED | `pytest tests/ -q` → **537 passed, 22 skipped, 16 subtests passed in 4.62s** on this verifier run. New classes present and exercised: `TestLoadSubcontractorRates`, `TestSubcontractorVariantGroupIdentityParsing`, `TestSubcontractorVariantHashAggregation`, `TestPiiLogMarkersIncludeSubcontractorVariants`, `TestSubcontractorVariantGrouping`, `TestResolveRowPriceCanonicalColumnNames`, `TestSubcontractorVariantFilenameSuffixes`, `TestSubcontractorVariantPriceSubstitution`, `TestGenerateExcelReturnTupleShape`, `TestSubcontractorMissingCUWarning`, `TestSubcontractorVariantOpenpyxlCompliance`, `TestSubcontractorVariantKillSwitchAndScope`, `TestDualTargetMapIndependentQuarantine`, `TestDualTargetSheetRouting`, `TestFreezeRowVariantAttribution`, `TestPipelineRunVariantColumnSchema`, `TestPhase1IntegrationRegression`, `TestPhase1FilenameRoundTripCoverage`. Existing classes (e.g., `TestVacCrewHashAggregation`, `TestSourceWrCollisionQuarantine`, `TestBuildGroupIdentityWithUnderscoresInWr`, `TestLoadContractRates`) unaffected. |
| 5 | A scheduled weekly workflow run completes inside `timeout-minutes: 195` and emits zero Sentry events tagged with the new variant scope; existing VAC-crew, ORIG-folder, and primary outputs are byte-identical to the run immediately before the change (verified via hash-history diff on a TEST_MODE run) | VERIFIED (code-side); production-run portion DEFERRED | Code-side byte-identical guarantee is locked by **`TestPhase1IntegrationRegression`** (5 tests, tests/test_subcontractor_pricing.py L2506): primary/helper/vac_crew hashes byte-identical across `_SUBCONTRACTOR_RATES_FINGERPRINT` mutation; positive companion confirms `aep_billable` hash changes under SUB_RATES_FP mutation (D-20 mix-in active). `_resolve_row_price` L1390-1394 short-circuits to `parse_price(row.get('Units Total Price'))` for legacy variants. `_AEP_BILLABLE_CUTOFF` and helper-shadow gates scoped via `_FOLDER_DISCOVERED_SUB_IDS` ⊆ subcontractor folders only — ORIG-folder + VAC-crew workflows untouched. **Scheduled run portion is per phase brief explicitly DEFERRED** to the first scheduled GHA production run after merge. |

**Score:** 5/5 truths verified code-side (3 carry deferred production-run portions documented in `human_verification`)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `data/subcontractor_rates.csv` | 17-column subcontractor rate matrix at canonical path with preserved git history | VERIFIED | File exists at 2,060,539 bytes, 4849 lines (header + 4848 data rows). `git log --follow --oneline` traces through `f3e3d2c (content seed) → d25fb07 (git mv) → d9e3603 (original add)`. Header confirmed: `CU WBS #, CU, ..., Install Price (Subcontractor Rates), Removal Price (Subcontractor Rates), Transfer Price (Subcontractor Rates), Install Price (Old Rates), Removal Price (Old Rates), Transfer Price (Old Rates), Install Price (New Rates), Removal Price (New Rates), Transfer Price (New Rates)`. Legacy `CU List - Corpus North & South.csv` confirmed removed from repo root. |
| `generate_weekly_pdfs.py` — Phase 1 helpers | `load_subcontractor_rates`, `_compute_subcontractor_rates_fingerprint`, `_resolve_row_price`, `_build_upload_tasks_for_group`, `create_target_sheet_map_for`, module-level `_SUBCONTRACTOR_RATES` + `_SUBCONTRACTOR_RATES_FINGERPRINT` + `_AEP_BILLABLE_CUTOFF`, env-var block | VERIFIED + WIRED | All 5 functions defined (lines 1116, 1254, 1324, 5070, 4898). Module-level constants populated at import: `_SUBCONTRACTOR_RATES` = 3691 CUs; `_SUBCONTRACTOR_RATES_FINGERPRINT` = `e4941a5e86c4f8ce` (matches Plan 01 SUMMARY claim exactly); `_AEP_BILLABLE_CUTOFF` = `2026-04-12`. Env vars resolve at import: `SUBCONTRACTOR_RATES_CSV` ends with `data/subcontractor_rates.csv`, `SUBCONTRACTOR_PPP_SHEET_ID = 8162920222379908`, `SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True`. |
| `generate_weekly_pdfs.py` — variant emission | `group_source_rows` emits 4 new group key prefixes; `generate_excel` produces 4 new variant_suffix branches | VERIFIED + WIRED | `_REDUCEDSUB` / `_AEPBILLABLE` / `_REDUCEDSUB_HELPER_` / `_AEPBILLABLE_HELPER_` group keys emitted at L4144 / L4166 / L4210 / L4227 gated per-row on `r.get('__source_sheet_id') in _FOLDER_DISCOVERED_SUB_IDS AND SUBCONTRACTOR_RATE_VARIANTS_ENABLED`. `generate_excel` L4506-4519 produces variant suffixes `_AEPBillable`, `_ReducedSub`, `_AEPBillable_Helper_<name>`, `_ReducedSub_Helper_<name>` BEFORE legacy branches (D-09 variant-first ordering). Operator-visible group-creation INFO logs fire (`🔻 REDUCED SUB GROUP CREATED`, `💲 AEP BILLABLE GROUP CREATED`). |
| `generate_weekly_pdfs.py` — parser / hash extensions | `build_group_identity` recognises 4 new filenames; `calculate_data_hash` mixes `_SUBCONTRACTOR_RATES_FINGERPRINT` for the 4 new variants only | VERIFIED + WIRED | `build_group_identity` L2306 (AEPBillable) + L2320 (ReducedSub) branches inserted BEFORE Helper/VacCrew/User (variant-first). Round-trip verified end-to-end for all 7 variants — see in-line check in verifier scratch run. `calculate_data_hash` L2051-2060 mixes `SUB_RATES_FP={_SUBCONTRACTOR_RATES_FINGERPRINT}` ONLY for variant ∈ {aep_billable, reduced_sub, aep_billable_helper, reduced_sub_helper}; legacy variants' meta_parts unchanged (byte-identical guarantee). Helper meta-block trigger extended at L2004 to tuple membership including new helper-shadow variants. |
| `generate_weekly_pdfs.py` — dual routing | `create_target_sheet_map_for(client, sheet_id)` extracted; `_build_upload_tasks_for_group` emits 1 or 2 tasks; `_upload_one` worker resolves `task['target_sheet_id']` | VERIFIED + WIRED | `create_target_sheet_map_for` at L4898 (parameterised helper); `create_target_sheet_map` at L5056 (back-compat wrapper delegating to TARGET_SHEET_ID). FUNCTION-LOCAL `_quarantined_keys` / `_seen_raw_for_key` confirmed inside helper body. `_build_upload_tasks_for_group` at L5070 emits 1 task for primary/helper/vac_crew/aep_billable/aep_billable_helper variants; 2 tasks for reduced_sub/reduced_sub_helper. PPP target_map built in main() at L5462-5489, gated by kill switch + same-sheet defense + fail-safe try/except via `_redact_exception_message`. |
| `billing_audit/schema.sql` — variant column | Idempotent `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT` migration positioned before CREATE INDEX | VERIFIED + WIRED | Schema migration at L122-123, positioned between existing column-add block (L89-95) and CREATE INDEX (L125-126). Inline comment block at L97-121 explains SUB-07 / D-18 / Blocker 1 Path B rationale. No `p_variant` substring in file (Path B lock-in). No `CHECK (variant ...)` constraint (D-18 forward-compat). |
| `billing_audit/writer.py` — variant kwarg | `freeze_row` + `emit_run_fingerprint` accept `variant: str \| None = None`; `freeze_row` body has `del variant`; `emit_run_fingerprint` upsert payload contains `'variant': effective_variant` | VERIFIED + WIRED | `freeze_row` L364 signature; L408 `del variant`; documented contract in docstring L385-407. `emit_run_fingerprint` L519 signature; L595 `effective_variant = variant if variant else 'primary'`; L611 `"variant": effective_variant` in payload. `on_conflict="wr,week_ending,run_id"` at L617 UNCHANGED (D-18: variant NOT in PK → first-variant-wins via existing dedup). |
| `generate_weekly_pdfs.py` — `_txn` hoist (orchestrator master-bug fix, commit 7e4777c) | `_txn = None` initialized at the top of `main()` so the `finally` block never sees it unbound after a synthetic-mode return or missing-token raise | VERIFIED | `_txn = None` at L5211 with the explanatory comment block at L5205-5210. Reference-only — not part of Phase 1 scope; documented separately in Plan 06 SUMMARY as a pre-existing master regression surfaced during Step A. |
| `tests/test_subcontractor_pricing.py` | New regression classes covering loader / variant emission / pricing / phase-1 integration | VERIFIED + WIRED | 11 new test classes present (lines 175, 1558, 1807, 2006, 2113, 2257, 2303, 2322, 2479, 2506, 2808). Full file invoked under `pytest tests/` → 0 failures. |
| `tests/test_vac_crew.py` | New parser + hash classes for subcontractor variants | VERIFIED + WIRED | `TestSubcontractorVariantGroupIdentityParsing` (L136), `TestSubcontractorVariantHashAggregation` (L519). |
| `tests/test_security_audit_followup.py` | Extensions + new classes for collision quarantine, PII markers, dual-target maps, dual-target routing | VERIFIED + WIRED | `TestBuildGroupIdentityWithUnderscoresInWr` (L907 — extended), `TestSourceWrCollisionQuarantine` (L1244 — extended), `TestPiiLogMarkersIncludeSubcontractorVariants` (L1415), `TestDualTargetMapIndependentQuarantine` (L1692), `TestDualTargetSheetRouting` (L1913). |
| `tests/test_billing_audit_shadow.py` | New writer + schema regression classes | VERIFIED + WIRED | `TestFreezeRowVariantAttribution` (L3685, 10 methods + 7 parametrized subtests), `TestPipelineRunVariantColumnSchema` (L4088, 7 methods). |
| `tests/validate_production_safety.py` | Inline comment pinning the 18 kB window cap with Phase 1 measurement + Warning 8 reconciliation | VERIFIED | L143-169 contains the Phase 1 measurement (17,738 chars), 262-char headroom rationale, Warning 8 reconciliation referencing Plan 05's 24 kB substring window. `python tests/validate_production_safety.py` reports **9/9 claims pass** under UTF-8 (the Windows-charmap Claim 5 failure is a pre-existing environment quirk documented in Plan 05 SUMMARY). |
| `website/docs/reference/environment.md` | "Subcontractor rate variants" section documenting the 3 env vars | VERIFIED | File contains "Subcontractor rate variants" section + all 3 env-var names. |
| `website/docs/runbook/workflows.md` | "Subcontractor rate variants" subsection synthesizing the what/why/how operator-impact narrative | VERIFIED | File contains "Subcontractor rate variants" section + `_AEPBillable` / `_ReducedSub` operator-impact narrative. `cd website && npm run typecheck` exits 0. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `generate_weekly_pdfs.py` module init | `data/subcontractor_rates.csv` | `load_subcontractor_rates(SUBCONTRACTOR_RATES_CSV)` at L1295-1299 | WIRED | Import produces `_SUBCONTRACTOR_RATES` = 3691-entry dict; fingerprint = `e4941a5e86c4f8ce`. Verified by direct import in this verifier run. |
| `group_source_rows` (variant emission) | `generate_excel` (filename suffix) | `__variant` row metadata field + group_key prefix matching | WIRED | `__variant` set at L4248-4249 in `group_source_rows`; consumed by `generate_excel` variant_suffix branches at L4506-4519 + `_resolve_row_price` at L1390-1394 (legacy short-circuit) + L1419-1422 (subcontractor branches). |
| `generate_excel` (5-tuple return) | main loop (upload-task builder + missing-CU WARNING) | `(excel_path, filename, wr_numbers, customer_name, missing_cus) = generate_excel(...)` parenthesised unpack at L6341-6350 (Plan 03 wiring) | WIRED | Verified by `TestGenerateExcelReturnTupleShape` (1 test) + `test_generate_excel_5tuple_unpacked_at_call_site` in `TestDualTargetSheetRouting`. The 5-tuple flows correctly to `_build_upload_tasks_for_group` and `_missing_cus_by_sheet`. |
| `_build_upload_tasks_for_group` | `_upload_one` worker | `task['target_sheet_id']` field on the task dict | WIRED | `task['target_sheet_id']` referenced ≥3 times inside the `_upload_one` closure body; 0 references to the global `TARGET_SHEET_ID` (verified by inspect-based test). |
| `row['__variant']` (per-row metadata) | `billing_audit.pipeline_run.variant` (Supabase) | `freeze_row(..., variant=_row.get('__variant', 'primary'))` at L6135 (single-row fast path) + L6173 (parallel worker) + `emit_run_fingerprint(..., variant=_group_variant)` at L6309 | WIRED | `freeze_row` accepts variant but explicitly drops it (Path B); `emit_run_fingerprint` writes it to the upsert payload. The schema column exists in `billing_audit/schema.sql` (must be applied to Supabase before first run — see `human_verification` item 3). |
| Operator startup banner | run log | `logging.info` lines at L1306-1311 (rate-table loaded) + earlier env-var banner | WIRED | Confirmed by import: `📊 Subcontractor rates loaded: 3691 CUs, fingerprint=e4941a5e86c4f8ce` (visible in the validator script output). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_SUBCONTRACTOR_RATES` module dict | dict of 3691 CU → 9 priced fields | `load_subcontractor_rates('data/subcontractor_rates.csv')` reads the operator-managed 17-column CSV with `skipinitialspace=True` + `_strip_csv_fieldnames` + `parse_price` coercion | Yes — sample CU `ALB-6-AUR1` resolves to `{new_install_price: 52.58, reduced_install_price: 45.95, …}` matching the raw CSV row | FLOWING |
| `_resolve_row_price(row, 'aep_billable', mc)` | float price | `_SUBCONTRACTOR_RATES[cu][new_{wt}_price] * qty` where wt is Work-Type-keyed | Yes — end-to-end test: CU=`ALB-6-AUR1`, Work Type='Install', Quantity=5 → 5 × 52.58 = 262.9 | FLOWING |
| `_resolve_row_price(row, 'reduced_sub', mc)` | float price | `_SUBCONTRACTOR_RATES[cu][reduced_{wt}_price] * qty` | Yes — same row → 5 × 45.95 = 229.75 | FLOWING |
| `_resolve_row_price(row, 'primary', mc)` | float price (legacy short-circuit) | `parse_price(row['Units Total Price'])` — byte-identical to pre-Phase-1 | Yes — test row `Units Total Price=100` returns 100.0 | FLOWING |
| `missing_cus` Counter | Counter[CU → count] | `_resolve_row_price` increments when CU not in `_SUBCONTRACTOR_RATES` | Yes — test row CU='NONEXISTENT_CU' → Counter records {'NONEXISTENT_CU': 1} and price falls through to SmartSheet `Units Total Price` | FLOWING |
| `target_map_ppp` | dict[sanitized_wr → row] | `create_target_sheet_map_for(client, SUBCONTRACTOR_PPP_SHEET_ID)` invocation in main() | Cannot verify without Smartsheet API; gated by TEST_MODE / kill-switch / distinct-sheet checks; fail-safe try/except degrades to `{}` | DEFERRED (production run validates; see `human_verification` item 1) |
| `billing_audit.pipeline_run.variant` | TEXT column on Supabase | `emit_run_fingerprint` upsert payload `{"variant": effective_variant}` | Cannot verify without Supabase access; schema column must be applied first | DEFERRED (see `human_verification` item 3) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `pytest tests/ -q` | 537 passed / 22 skipped / 16 subtests in 4.62s | PASS |
| Module imports cleanly | `python -c "import generate_weekly_pdfs as g; print(len(g._SUBCONTRACTOR_RATES), g._SUBCONTRACTOR_RATES_FINGERPRINT)"` | `3691 e4941a5e86c4f8ce` (matches Plan 01 SUMMARY) | PASS |
| `build_group_identity` round-trip for all 7 variants | Inline script | All 7 variants parse correctly (primary, helper, vac_crew, aep_billable, reduced_sub, aep_billable_helper, reduced_sub_helper); identifier substring `Jane_Smith` preserved for helper-shadow variants | PASS |
| `_resolve_row_price` returns rate × qty for known CU on subcontractor variants and 100.0 SmartSheet pass-through on primary | Inline script | aep_billable: 262.9, reduced_sub: 229.75, primary: 100.0, missing CU: 100.0 + Counter recorded | PASS |
| Docusaurus typecheck | `cd website && npm run typecheck` | exit 0 | PASS |
| Production safety validator | `PYTHONIOENCODING=utf-8 python -X utf8 tests/validate_production_safety.py` | 9/9 claims validated | PASS |
| _txn pre-existing master bug fixed | `grep "^    _txn = None$" generate_weekly_pdfs.py` | L5211 (hoisted to main() init block per commit 7e4777c) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SUB-01 | Plan 02, Plan 03 | `_AEPBillable` variant priced via `new_*_price` columns | SATISFIED | `_resolve_row_price` L1419-1420 reads `new_{wt}_price` for `aep_billable*` variants; `group_source_rows` L4161-4172 emits `_AEPBILLABLE` only when `Snapshot Date >= 2026-04-12`; `generate_excel` L4506-4507 produces `_AEPBillable` suffix. End-to-end resolver test verified. |
| SUB-02 | Plan 02, Plan 03 | `_ReducedSub` variant priced via `reduced_*_price` columns regardless of snapshot | SATISFIED | `_resolve_row_price` L1422 reads `reduced_{wt}_price` for `reduced_sub*` variants; `group_source_rows` L4144-4150 emits `_REDUCEDSUB` unconditionally on subcontractor rows; `generate_excel` L4508-4509 produces `_ReducedSub` suffix. End-to-end resolver test verified. |
| SUB-03 | Plan 04 | `_AEPBillable` + `_ReducedSub` route to TARGET_SHEET_ID; `_ReducedSub` additionally routes to SUBCONTRACTOR_PPP_SHEET_ID | SATISFIED | `_build_upload_tasks_for_group` L5140-5153 (primary leg) + L5167-5181 (PPP leg) emits 2 tasks for `reduced_sub*` variants; same-sheet defense at L5467 prevents accidental double-upload; fail-safe try/except at L5468-5489. 14 routing tests pass in `TestDualTargetSheetRouting`. |
| SUB-04 | Plan 01, Plan 03 | `data/subcontractor_rates.csv` is authoritative; load helper validates schema + logs missing CUs as WARNINGs | SATISFIED | CSV at canonical path (4848 data rows). `load_subcontractor_rates` validates 7 required headers, BOM-tolerant, currency-tolerant, zero-row skip. Missing-CU WARNING surface: per-sheet WARNING at end-of-group-processing with marker `Subcontractor rates CSV missing` (Plan 03). 8 loader tests + 1 missing-CU test pass. |
| SUB-05 | Plan 02, Plan 03, Plan 04 | When helper-foreman event fires on a subcontractor WR, BOTH `_AEPBillable_Helper_<name>` AND `_ReducedSub_Helper_<name>` shadow files generated | SATISFIED | `group_source_rows` L4199-4243 emits `_REDUCEDSUB_HELPER_<sanitized>` + `_AEPBILLABLE_HELPER_<sanitized>` (cutoff-gated) on `valid_helper_row + helper_mode_enabled`. `generate_excel` L4510-4519 produces the matching filename suffixes. Routing inherits parent variant (PPP route for `_ReducedSub_Helper_<name>` only). |
| SUB-06 | Plan 01, Plan 02, Plan 03, Plan 04 | No new subcontractor variant logic touches ORIG-folder sheets or VAC-crew detection | SATISFIED | Per-row gate `_row_sheet_id in _FOLDER_DISCOVERED_SUB_IDS` at L4134-4138 scopes ALL new variant emission to subcontractor folders only. D-20 fingerprint mix-in scoped exactly to the 4 new variants (3 negative tests in `TestSubcontractorVariantHashAggregation` lock byte-identical hashes for primary/helper/vac_crew). `TestSubcontractorVariantKillSwitchAndScope::test_orig_folder_sheet_emits_no_new_variants` + `TestPhase1IntegrationRegression` cover the invariant. |
| SUB-07 | Plan 05 | `billing_audit.pipeline_run` records variant; schema change in same PR as writer | SATISFIED | Schema migration at `billing_audit/schema.sql` L122-123 (`ADD COLUMN IF NOT EXISTS variant TEXT`); writer kwarg threading in `billing_audit/writer.py` L364, L519, L595, L611; per-row + per-group call-site wiring in `generate_weekly_pdfs.py` L6135, L6173, L6309. 17 new tests (7 schema + 10 writer with 7 parametrized subtests) pass. Path B lock-in: variant NOT injected into freeze_attribution RPC. **Operator action required**: apply schema.sql to Supabase before first production run (see `human_verification` item 3). |

**Coverage:** 7/7 SUB-* requirements satisfied (all code-side); 0 orphaned; 1 (SUB-07) requires one-time operator Supabase Dashboard apply.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none of operational concern) | — | — | — | — |

The legacy `oddFooter.right.text` comment at L5xxx is a forward-compatibility guardrail noting the corruption vector, NOT an actual assignment. The `Phase 1 SUB-07` / `# Phase 01 Plan 02` / `# Phase 01 Plan 03` comments throughout `generate_weekly_pdfs.py` are intentional cross-references to plan documentation. No TODO/FIXME/XXX/HACK markers introduced by Phase 1 changes.

### Human Verification Required

Code-side artifacts are all in place; the remaining validation is the in-production observation per ROADMAP success criterion 5 and Plan 06 Step B operator decision.

#### 1. First scheduled GHA production run after merge

**Test:** Allow the next scheduled `.github/workflows/weekly-excel-generation.yml` run to complete with `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=1` against the live Smartsheet subcontractor folder.

**Expected:**
- Run completes inside `timeout-minutes: 195`.
- New artifacts appear in the run's `generated_docs/<week>/` zip: `WR_*_WeekEnding_*_AEPBillable_*.xlsx`, `WR_*_WeekEnding_*_ReducedSub_*.xlsx`, plus `*_AEPBillable_Helper_<name>_*.xlsx` and `*_ReducedSub_Helper_<name>_*.xlsx` when helper-foreman events fire.
- Smartsheet attachment panel on `TARGET_SHEET_ID=5723337641643908` shows the new variants attached to qualifying WR rows.
- Smartsheet attachment panel on `SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908` shows `_ReducedSub` variants attached (dual-routing second leg).
- Hash-history diff vs the prior run shows primary/helper/vac_crew/ORIG-folder hashes unchanged (byte-identical guarantee per success criterion 5).
- Sentry dashboard shows zero new error-grouping fingerprints tagged with the new variant scope.

**Why human:** ROADMAP success criterion 5 explicitly requires a scheduled production run end-to-end. The verifier cannot execute the live Smartsheet API path. Per Plan 06 SUMMARY Task 3 Step B (Warning 10 fallback verification surface), this is the deferred validation pathway with the kill switch (`SUBCONTRACTOR_RATE_VARIANTS_ENABLED=0`) as the documented rollback path if behaviour regresses.

#### 2. Step B real-data price-write end-to-end (deferred during Plan 06)

**Test:** In an environment with a valid `SMARTSHEET_API_TOKEN` and read access to subcontractor folder sheets, run:

```
PYTHONIOENCODING=utf-8 python -X utf8 SKIP_UPLOAD=true python generate_weekly_pdfs.py
```

**Expected:**
- `generated_docs/<week>/` contains `_AEPBillable` and `_ReducedSub` workbooks for the current subcontractor sheet rows.
- Open any `_AEPBillable_*.xlsx` and confirm column H "Pricing" cells contain `rate × qty` derived from `data/subcontractor_rates.csv`'s `new_*_price` columns for known CUs.
- Open any `_ReducedSub_*.xlsx` and confirm Pricing cells use the `reduced_*_price` columns.
- Run log emits exactly one WARNING per affected sheet containing the marker text `Subcontractor rates CSV missing` for any CUs not in the CSV.
- No `oddFooter.right.text` assignment errors, no `MergedCell` errors, no openpyxl corruption errors.

**Why human:** Per Plan 06 Task 3 SUMMARY: "Local operator env lacks `SMARTSHEET_API_TOKEN` — Step B cannot run locally." Unit-level coverage in `TestSubcontractorVariantPriceSubstitution` writes a real openpyxl workbook and verifies the cell values, but the production-data integration (real CU codes, real Work Types, real Quantities) only exercises in an environment with the API token + access to subcontractor sheets. Step B was explicitly deferred to the first scheduled production run.

#### 3. One-time Supabase schema apply

**Test:** Before the first scheduled production run after this PR merges:

1. Open Supabase Dashboard for the project hosting `billing_audit` schema.
2. Navigate to **Project Settings → SQL Editor**.
3. Paste the entire contents of `billing_audit/schema.sql` into the editor.
4. Click **Run**.
5. Verify with `\d billing_audit.pipeline_run` (or the Dashboard table inspector) that the `variant TEXT` column is present.

**Expected:**
- `ADD COLUMN IF NOT EXISTS variant TEXT` clause is idempotent — safe to re-run if the column already exists.
- After apply, `billing_audit.pipeline_run.variant` accepts the 7 valid variant strings (or NULL for legacy rows).

**Why human:** Schema migration apply lives in the Supabase Dashboard UI — the verifier cannot execute against the deployed Supabase project. Without this apply, the first scheduled production run's `emit_run_fingerprint` upsert will fail at the variant column write (the column needs to exist before the writer can populate it). Per Plan 05 SUMMARY "User Setup Required" section.

### Gaps Summary

**No code-side gaps found.** Every Phase 1 deliverable across the six plans is wired up, exercised by tests, and produces correct output on direct invocation. The full pytest suite passes (537 passed / 22 skipped / 16 subtests) and the production-safety validator reports 9/9 claims pass.

**Deferred items (per phase brief — these are not gaps):**
- Scheduled production run (ROADMAP success criterion 5 — the "in-production observation" portion).
- Step B real-data SKIP_UPLOAD price-write gate (operator-decided defer during Plan 06 Task 3 due to local `SMARTSHEET_API_TOKEN` unavailability).
- One-time Supabase schema apply (operator action prerequisite to first production run).

These are explicitly flagged in `human_verification` per the workflow contract, and the phase brief stated: "Treat the per-criterion check as: Code-side artifacts and tests in place (verifiable now); Production run validation deferred to first scheduled run after merge (note in VERIFICATION.md `human_verification` section)."

**Reference note on commit 7e4777c (`fix(main): hoist _txn = None`):** This orchestrator-applied fix is a pre-existing master regression discovered during Phase 1 verification (synthetic-mode `return` and missing-token `raise` short-circuited past the in-place `_txn` init, causing `UnboundLocalError` in the `finally` block). Documented in Plan 06 SUMMARY for traceability. Reference-only — not penalized against Phase 1; the hoist is verified present at L5211 of `generate_weekly_pdfs.py`.

---

_Verified: 2026-05-14T22:30:00Z_
_Verifier: Claude (gsd-verifier, Opus 4.7)_
