---
phase: 11
slug: incremental-read-affected-group-regeneration
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-26
validated: 2026-09-12
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python 3.12 in CI, 3.11+ locally) |
| **Config file** | `pytest.ini` / `tests/conftest.py` (existing — no Wave 0 install) |
| **Quick run command** | `python -m pytest tests/test_incremental_read.py tests/test_parity_shadow.py tests/test_deep_run_reconciliation.py tests/test_pipeline_memory_shadow.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` (2026-09-12: 2416 passed / 1 skipped / 595 subtests) |
| **Estimated runtime** | ~45 seconds (full suite); ~3 seconds (quick, 383 tests) |

Also gate every plan with `python -m py_compile generate_weekly_pdfs.py` and, before
`/gsd:verify-work`, `bash scripts/run_6_gates.sh` (Gate 6 pins the frozen 21-key
`tests/golden/run_summary_baseline.json`).

---

## Sampling Rate

- **After every task commit:** Run the quick command above
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds
- **`bash scripts/run_6_gates.sh` is a PLAN-level gate, never a per-task `<automated>` verify.**
  It runs the full pytest suite, the mypy delta and a `TEST_MODE` run, which exceeds the
  30-second per-task latency above. Every plan runs it once before being declared complete;
  it lives in each PLAN.md's `<verification>` block, not in a `<task><verify>`.

---

## Per-Task Verification Map

Rows are keyed by the SUMMARY.md `coverage` ids (D1..D6 per plan; T-11-xx for plan 08).
Status reflects the 2026-09-12 retroactive audit run.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-D1 | 01 | 1 | INC-04 | — | Decorated numerics pre-parsed by caller; NULL never raw string (WR-01) | unit | `pytest tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests -q` | ✅ | ✅ green |
| 11-01-D2 | 01 | 1 | INC-04 | — | `sheets_changed` on both `run_ledger_finish` call sites | e2e + source | `pytest tests/test_pipeline_memory_shadow.py::RunLedgerFailurePathTests tests/test_pipeline_memory_shadow.py::RunLedgerSheetsChangedCallSiteTests -q` | ✅ | ✅ green |
| 11-01-D3 | 01 | 1 | INC-04 (doc) | — | Flip checklist + ledger entry; workflow untouched | content check | `git diff --exit-code -- .github/workflows/` | ✅ | ✅ green (checklist reviewed by hand) |
| 11-02-D1 | 02 | 2 | INC-01 | — | `if_version_after` probe, then `rows_modified_since` only on change | unit | `pytest tests/test_incremental_read.py::FetchSheetDeltaTests tests/test_incremental_read.py::RowsModifiedSinceTests -q` | ✅ | ✅ green |
| 11-02-D2 | 02 | 2 | INC-01 | — | Any delta/watermark failure escalates to full read, never "unchanged" | unit | `pytest tests/test_incremental_read.py::FetchSheetDeltaTests tests/test_incremental_read.py::SheetWatermarksReadTests -q` | ✅ | ✅ green |
| 11-02-D3 | 02 | 2 | INC-01 | — | All seven D-02 full-read escalation triggers + flag gate | unit | `pytest tests/test_incremental_read.py::ModeResolutionTests -q` | ✅ | ✅ green |
| 11-02-D4 | 02 | 2 | INC-01 | — | Capture-time watermark; `last_full_read_at` moves only on a full read | unit | `pytest tests/test_incremental_read.py::WatermarkPersistenceTests -q` | ✅ | ✅ green |
| 11-03-D1 | 03 | 3 | INC-02 | — | D-06 cleanup preservation + `KEEP_HISTORICAL_WEEKS` wiring | unit | `pytest tests/test_incremental_read.py::CleanupPreservationTests tests/test_incremental_read.py::OrchestrateKeepHistoricalWiringTests -q` | ✅ | ✅ green |
| 11-03-D2 | 03 | 3 | INC-02 | — | Hash-history prune bounded | unit | `pytest tests/test_incremental_read.py::HashHistoryPruneTests -q` | ✅ | ✅ green |
| 11-03-D3 | 03 | 3 | INC-02 | — | Scope derivation | unit | `pytest tests/test_incremental_read.py::ScopeDerivationTests -q` | ✅ | ✅ green |
| 11-04-D1 | 04 | 4 | INC-02 | — | Incremental scope restricted to affected (WR, week) pairs | unit | `pytest tests/test_incremental_read.py::IncrementalScopeTests -q` | ✅ | ✅ green |
| 11-04-D2 | 04 | 4 | INC-02 | — | Moved week keeps both new and prior pair; grouping/pricing/attribution/excel untouched | unit + diff | `git diff --exit-code -- pipeline/grouping.py pipeline/pricing.py pipeline/attribution.py pipeline/excel.py` | ✅ | ✅ green |
| 11-04-D3 | 04 | 4 | INC-02 | — | Affected-set mapping: chunking, mid-chunk failure, three empty outcomes fall back to full | unit | `pytest tests/test_incremental_read.py::AffectedSetMappingTests -q` | ✅ | ✅ green |
| 11-04-D4 | 04 | 4 | INC-02 | — | Scoped counters | unit | `pytest tests/test_incremental_read.py::ScopedCounterTests -q` | ✅ | ✅ green |
| 11-05-D1 | 05 | 5 | INC-04 | — | Shadow parity comparator verdicts | unit | `pytest tests/test_parity_shadow.py::CompareShadowParityTests -q` | ✅ | ✅ green |
| 11-05-D2 | 05 | 5 | INC-04 | — | Empty/None/unexpected inputs yield `skipped`, never `pass`; never raises | unit | `pytest tests/test_parity_shadow.py::CompareShadowParityTests tests/test_parity_shadow.py::CombineVerdictsTests -q` | ✅ | ✅ green |
| 11-05-D3 | 05 | 5 | INC-04 | — | Shadow delta read: budget, per-call timeout, no registry write, worker cap | unit | `pytest tests/test_parity_shadow.py::ShadowDeltaReadTests -q` | ✅ | ✅ green |
| 11-05-D4 | 05 | 5 | INC-04 | — | Changed row absent from delta read = read-side fail | unit | `pytest tests/test_parity_shadow.py::GetChangedRowIdsBySheetTests -q` | ✅ | ✅ green |
| 11-05-D5 | 05 | 5 | INC-04 | — | Golden `run_summary_baseline.json` unchanged (21 keys) | unit | `pytest tests/test_parity_shadow.py::GoldenContractTests -q` | ✅ | ✅ green |
| 11-06-D1 | 06 | 6 | INC-03 | — | Deep-run deletion detection + `mark_rows_deleted` | unit | `pytest tests/test_deep_run_reconciliation.py::RowStateRowIdsReadTests tests/test_deep_run_reconciliation.py::MarkRowsDeletedTests tests/test_deep_run_reconciliation.py::DeepRunDeletionReconciliationTests -q` | ✅ | ✅ green |
| 11-06-D2 | 06 | 6 | INC-03 | — | Zero-row full read marks zero deleted and skips (never mass-deletes) | unit | `pytest tests/test_deep_run_reconciliation.py::DeepRunDeletionReconciliationTests -q` | ✅ | ✅ green |
| 11-06-D3 | 06 | 6 | INC-03 | — | `group_state` repair | unit | `pytest tests/test_deep_run_reconciliation.py::GroupStateRepairTests -q` | ✅ | ✅ green |
| 11-06-D4 | 06 | 6 | INC-03 | — | `column_mapping` refresh | unit | `pytest tests/test_deep_run_reconciliation.py::ColumnMappingRefreshTests -q` | ✅ | ✅ green |
| 11-06-D5 | 06 | 6 | INC-03 | — | Formula-only reconciliation (fixture `formula_only_change.json`) | unit | `pytest tests/test_deep_run_reconciliation.py::FormulaOnlyReconciliationTests -q` | ✅ | ✅ green |
| 11-07-D1 | 07 | 7 | INC-04 | — | Parity streak read (mocked Supabase) | unit | `pytest tests/test_incremental_read.py::ParityStreakTests -q` | ✅ | ✅ green |
| 11-07-D2 | 07 | 7 | INC-04 | — | `schema.sql` untouched | diff | `git diff --exit-code -- pipeline_memory/schema.sql` | ✅ | ✅ green |
| 11-07-D3 | 07 | 7 | INC-04 | — | Streak read fails closed on Supabase failure | unit | `pytest tests/test_incremental_read.py::ParityStreakTests -q` | ✅ | ✅ green |
| 11-08-T38/39 | 08 | 8 | INC-05 | — | Six workflow cache steps removed; no schedule/budget line touched | content check | plan 08 python one-liner (WORKFLOW_OK) | ✅ | ✅ green |
| 11-08-T40 | 08 | 8 | INC-05 | — | Operator flags still force a full read after cache retirement | unit | `pytest tests/test_incremental_read.py -k test_trigger5_operator_flags_force_full -q` | ✅ | ✅ green |
| 11-08-T41 | 08 | 8 | INC-05 | — | `pipeline/cleanup.py` consumers unmodified | full suite | `python -m pytest tests/ -q` | ✅ | ✅ green |
| 11-08-T44 | 08 | 8 | INC-05 | — | Ledger entry holds rule/env names only, no secrets | content check | plan 08 python one-liner | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Evidence (2026-09-12, branch `plan/phase-13`): quick command → 383 passed / 25 subtests;
full suite → 2416 passed / 1 skipped / 595 subtests in 43.5 s; `py_compile` clean.

---

## Wave 0 Requirements

- [x] `tests/test_pipeline_memory_shadow.py` — extended for WR-01 decorated-numeric payloads and WR-04 `sheets_changed` (plan 01)
- [x] `tests/test_incremental_read.py` — delta read, mode resolution, watermark persistence, D-06 preservation, incremental scope, affected-set mapping, scoped counters, parity streak, operator-escalation-flag regressions (plans 02, 03, 04, 07, 08)
- [x] `tests/fixtures/incremental/abbreviated_sheet_response.json` — cassette pinning the abbreviated `Sheet` response shape (plan 02)
- [x] `tests/test_parity_shadow.py` — shadow comparator verdicts and shadow delta reads (plan 05)
- [x] `tests/test_deep_run_reconciliation.py` — deletion detection, `column_mapping` refresh, formula-only reconciliation (plan 06)
- [x] `tests/fixtures/incremental/deleted_row.json`, `tests/fixtures/incremental/formula_only_change.json` — cassettes (plan 06)
- [x] `tests/conftest.py` — shared fixtures (already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `RUN_MEMORY_WRITE_ENABLED` flip merged and one real run populated `pipeline_memory` | INC-04 (D-10 precondition) | Protected GitHub Actions workflow edit + live production run | Juan approves/merges the flip PR; confirm a `run_ledger` row with `status='success'` and non-zero `row_state` count |
| Parity streak ≥5 consecutive `production_frequent` runs with `parity_verdict='pass'` | INC-04 | Requires real scheduled runs over ~1 business day | Recorded as 5/5 on merged master #372 (`d9bd2b2`) per 11-07-SUMMARY "DECISION RE-OPENED (2026-08-31)" |
| INC-02 full acceptance ("only touched groups regenerate") | INC-02 (D-05 owner-approved partial) | Automated tests prove the scope selector; the requirement stays Pending in REQUIREMENTS.md until ≥5 production incremental runs are observed | Observe `run_ledger.mode='incremental'` rows post-deploy; compare regenerated group count vs affected-set size |
| Weekly deep run detects a deleted row + formula-only change on live data | INC-03 (SC3) | One live verification alongside the fixture | Delete one row / edit one formula on the Sandbox rig before the Monday run; confirm `row_state.deleted_at` + `group_state` repair |
| Frequent-run wall clock before/after INC-05 retirement | INC-05 (SC4) | Measured on real runs (baseline 94 min, run 32743959053) | Compare run durations in the Actions log before and after the retirement PR (plan 08) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (quick command ~3 s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-09-12 by `/gsd:validate-phase 11` (retroactive audit). No
VERIFICATION.md exists for this phase; the milestone audit's Phase 11 verification gap is
closed at the Nyquist layer by this document, not by a goal-backward VERIFICATION.md.

---

## Validation Audit 2026-09-12

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

All five requirements (INC-01..05) classified COVERED: every SUMMARY `coverage` ref resolves
to an existing test class or mechanical check, and the four Phase 11 test modules run green.
No `gsd-nyquist-auditor` spawn was required.
