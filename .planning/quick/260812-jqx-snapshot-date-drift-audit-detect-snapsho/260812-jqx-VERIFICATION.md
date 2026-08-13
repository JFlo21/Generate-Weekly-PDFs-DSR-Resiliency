---
phase: quick-260812-jqx
verified: 2026-08-12T22:05:00Z
status: human_needed
score: 8/8 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: >
      Run SKIP_UPLOAD=true WR_FILTER=<one known-drifted WR>
      SNAPSHOT_DRIFT_HOLD_ENABLED=true python generate_weekly_pdfs.py
      against real Smartsheet data (Task 3 human-check, recorded open in
      .planning/WINDOWS.md).
    expected: >
      Run log shows the drifted row classified as automation_self_fire,
      held to its prior week, and present in the generated workbook's
      day-table for that week. If it comes back unclassified, correct
      SNAPSHOT_DRIFT_AUTOMATION_EMAIL (assumption A4) rather than the
      classifier.
    why_human: >
      Assumptions A1 (cell-history entry ordering) and A4 (literal
      automation modified_by email) can only be confirmed against live
      Smartsheet data; the suite proves the mechanism with mocked
      history payloads. Requires SMARTSHEET_API_TOKEN, unavailable in
      the verification sandbox.
  - test: >
      Apply the two appended CREATE TABLE IF NOT EXISTS blocks from
      billing_audit/schema.sql in the Supabase SQL Editor (project
      poeyztlmsawfoqlanucc); confirm billing_audit is in Exposed
      schemas and reload the PostgREST cache (user_setup).
    expected: >
      billing_audit.snapshot_provenance and billing_audit.snapshot_drift
      exist; the next run seeds provenance instead of degrading to
      fetch_failure.
    why_human: >
      The pipeline never runs DDL (D-07); schema.sql is
      documentation-grade and applied manually by Juan. Until applied,
      the feature safely no-ops (verified), but the audit produces no
      durable evidence.
---

# Quick Task 260812-jqx: Snapshot-Date Drift Audit — Verification Report

**Goal:** Detect rows whose billing week drifted from the week they were
last billed under, classify via targeted cell-history lookups, record
every drift durably in Supabase, and — for automation self-fires only,
behind a default-off gate — hold the row at its previously-billed week.
**Verified:** 2026-08-12 (branch feat/260812-jqx-snapshot-drift-audit,
commits 55329a1, c58a9bd, 0a68aeb, 0b5051a; diff base 3f7be82)
**Status:** human_needed (all automated must-haves verified; live A1/A4
operator check + manual DDL apply outstanding, both by design)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (PLAN must_haves.truths)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Drift detected with ZERO extra Smartsheet API calls (D-04) | ✓ VERIFIED | Detection uses one bulk Supabase provenance fetch only (`snapshot_store.fetch_snapshot_provenance`); tests `test_unchanged_week_costs_zero_api_calls`, `test_drifted_week_emits_candidate_without_mutation` pass — mock SDK client records zero calls |
| 2 | First sight seeds provenance silently — no flag, no history call, no hold (D-09) | ✓ VERIFIED | `apply_snapshot_drift_holds` lines 530-538 (seed path, `continue` before candidate emit); `test_no_baseline_seeds_silently` passes |
| 3 | Self-fire held to BOTH prior Weekly Reference Logged Date AND prior Snapshot Date; row survives day-tables; prior week hash unchanged (D-01) | ✓ VERIFIED | `_apply_holds` rewrites both fields + stashes originals under `__drifted_*` keys (snapshot_drift.py:448-461); `test_hold_rewrites_both_fields_and_preserves_originals`, `test_held_row_appears_in_generated_workbook` (real `generate_excel` Monday-Sunday filter), `test_hash_stable_across_drift_and_hold_both_modes` (2 subtests, legacy + extended) all pass. Live classifier accuracy is the human item |
| 4 | Manual edit shadow-logged, NEVER held (D-02) | ✓ VERIFIED | `_apply_holds` skips non-self-fire classifications; `test_manual_candidate_never_mutated_even_with_hold_enabled` passes; every candidate written to `snapshot_drift` events regardless (`test_events_carry_classification_and_held_for_all_outcomes`) |
| 5 | Any classification failure → 'unclassified': flagged, never held (D-03, D-10) | ✓ VERIFIED | Tests pass for: API exception, missing column id (zero calls), cap exhaustion (cap=1, exactly 2 calls), budget guard (zero calls), plus `test_unclassified_candidate_never_mutated_even_with_hold_enabled` |
| 6 | Both switches false → behaviour identical to today (D-08) | ✓ VERIFIED | `test_disabled_is_a_pure_noop` (zeroed summary, no Supabase touch, rows value-identical) + `test_both_switches_off_reproduces_baseline` (risk_level baseline) pass; orchestrate seam only touches `audit_results['summary']` when `enabled`; run_summary.json reads only `audit_risk_level` from the audit summary so its key set is unchanged. Info note below on the placeholder key |
| 7 | Only self-fire holds inflate total_issues / risk_level (D-01, caveat 5) | ✓ VERIFIED | `escalate_risk_for_snapshot_drift` early-returns at holds ≤ 0 and adds only `self_fire_holds` to the existing 4-term sum with the identical 0 / ≤3 / else thresholds; `test_four_holds_escalate_to_high`, `test_zero_holds_leaves_risk_level_unchanged` pass |
| 8 | Missing client / unapplied migration / fetch failure → whole feature no-ops, never breaks the run (D-07) | ✓ VERIFIED | Store functions inherit the `get_client()`-None never-raise contract (snapshot_store.py:73-77, 135-137, 166-168); absent table surfaces as `fetch_failure` → seed-only degrade; belt-and-suspenders `except` wraps the whole pass (snapshot_drift.py:623-631); orchestrate seam has its own try/except; `test_unavailable_client_flags_summary_and_does_not_raise`, `test_fetch_exception_is_swallowed` pass |

**Score:** 8/8 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `pipeline/snapshot_drift.py` | apply_snapshot_drift_holds() + classifier, only home of drift logic | ✓ VERIFIED | 631 lines; kill-switches read per call via os.getenv; lazy `billing_audit.snapshot_store` import; wired from orchestrate |
| `billing_audit/snapshot_store.py` | bulk read, bulk upsert, append-only insert | ✓ VERIFIED | 184 lines; 3 public fns, all bulk (one call/run), all never-raise, `lookup_group_hash` status vocabulary |
| `billing_audit/schema.sql` | appended provenance + drift DDL, manual apply | ✓ VERIFIED | +68/-0, single hunk after line 330; two CREATE TABLE IF NOT EXISTS, PKs (sheet_id,row_id) / (sheet_id,row_id,detected_at), wr+detected_at index, service_role grants; nothing above touched |
| `pipeline/config.py` | six SNAPSHOT_DRIFT_* switches | ✓ VERIFIED | All six present next to the TIME_BUDGET family with plan defaults: AUDIT_ENABLED=true, HOLD_ENABLED=false, MAX_ROWS=40, PACE_SEC=2.0, MAX_MINUTES=5, AUTOMATION_EMAIL=automation@smartsheet.com |
| `pipeline/orchestrate.py` | ONE call site at the pre-grouping seam | ✓ VERIFIED | Exactly 2 hunks (import + seam); seam sits between the audit else-branch and "📂 Grouping data...", own try/except; escalation + Sentry hold-warning inside the same seam |
| `audit_billing_changes.py` | drift counters + escalate_risk_for_snapshot_drift() | ✓ VERIFIED | +56/-0; `total_snapshot_drift_holds` counter + module-level escalation fn reusing existing thresholds |
| `tests/test_snapshot_drift_audit.py` | RED-first suite covering the 9 research cases | ✓ VERIFIED | 888 lines, 27 tests + 2 subtests, all pass in 31.7s, no live Smartsheet/Supabase calls |
| `memory-bank/living-ledger.md` | dated entry | ✓ VERIFIED | `## [2026-08-12 15:30] Snapshot-date drift audit + hold-prior-week gate added (260812-jqx)` at line 5336 (bottom of file) |

### Key Link Verification

| From | To | Via | Status |
| --- | --- | --- | --- |
| orchestrate.py pre-grouping seam | apply_snapshot_drift_holds(all_rows, source_sheets, client, session_start) | after audit else-branch, before grouping span — upstream of all grouping.py week readers | ✓ WIRED |
| Held row | grouping week key + excel Monday-Sunday filter + change-detection hashes | BOTH fields rewritten in `_apply_holds`; pinned by the excel-filter and dual-mode hash-stability tests | ✓ WIRED |
| `__source_sheet_id`/`__row_id` | `column_mapping['Snapshot Date']`/`['Units Completed?']` → `client.Cells.get_cell_history(..., include_all=True)` | `_collect_candidate_rows` + `_classify_candidates` | ✓ WIRED |
| `get_client()` returns None | whole feature no-ops | store neutral returns + `unavailable`/`fetch_failure` status | ✓ WIRED |
| `drift_summary['automation_self_fire_holds']` | `escalate_risk_for_snapshot_drift` → `summary['risk_level']` | orchestrate seam, gated on `enabled` + summary-is-dict | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| New suite green | `pytest tests/test_snapshot_drift_audit.py -v` | 27 passed, 2 subtests, 31.68s | ✓ PASS |
| Full-suite regression (run once) | `pytest tests/ -q` | 1257 passed, 132 subtests, 42.69s — independently confirms executor claim | ✓ PASS |
| Syntax | `py_compile` on generate_weekly_pdfs.py, snapshot_drift.py, snapshot_store.py, audit_billing_changes.py | clean | ✓ PASS |
| Diff guard: grouping/excel | `git diff --name-only 3f7be82..HEAD -- pipeline/grouping.py pipeline/excel.py` | 0 files | ✓ PASS |
| Seam guard | `git diff -U0 3f7be82..HEAD -- pipeline/orchestrate.py \| grep -c '^@@'` | 2 (≤ 3 allowed) | ✓ PASS |
| Schema append-only | `git diff --stat` + deleted-line count | +68/-0, single hunk at EOF | ✓ PASS |
| Off-switch run_summary key set | run_summary composition reads only `audit_risk_level` from audit summary | unchanged key set | ✓ PASS |

### Prohibitions / Negative Checks

| Prohibition | Status | Evidence |
| --- | --- | --- |
| Pipeline never runs DDL | ✓ HELD | snapshot_store issues only select/upsert/insert; schema.sql is documentation-grade with an operator apply banner |
| No new mutating Smartsheet write | ✓ HELD | Only read-only `get_cell_history`; no AUDIT_SHEET_ID write added (RESEARCH caveat 4 respected) |
| Change-detection key unshortened | ✓ HELD | change_detection.py and grouping.py untouched |
| No per-row Supabase reads/writes | ✓ HELD | One bulk fetch, one batched upsert, one batched insert per run; `test_upsert_called_once_with_batched_payload` pins it |

### Anti-Patterns Found

None. No TBD/FIXME/XXX/placeholder markers in the new or changed files.

### Deviations (accepted, documented)

- Post-seam Sentry `sentry_capture_message_with_context` warning when holds > 0 — additive, inside the seam hunk, addresses the plan-check observability warning. ℹ️
- Test-only budget-boundary flake fix — test file only. ℹ️
- `total_snapshot_drift_holds: 0` placeholder added unconditionally to `_generate_audit_summary` for key-set stability across enabled/disabled runs. Additive in-memory key; does not reach run_summary.json (which reads only `audit_risk_level`) or any billing artifact. ℹ️

### Human Verification Required

1. **Live A1/A4 classifier check (Task 3 human-check, open in .planning/WINDOWS.md)** — `SKIP_UPLOAD=true WR_FILTER=<known-drifted WR> SNAPSHOT_DRIFT_HOLD_ENABLED=true python generate_weekly_pdfs.py`; expect automation_self_fire classification, hold to prior week, row present in the workbook day-table. Must pass BEFORE setting `SNAPSHOT_DRIFT_HOLD_ENABLED=true` in the workflow. If unclassified, set `SNAPSHOT_DRIFT_AUTOMATION_EMAIL` — do not edit the classifier.
2. **Supabase DDL apply (user_setup)** — apply the two appended schema.sql blocks in the SQL Editor, confirm `billing_audit` in Exposed schemas, reload the PostgREST cache. Until then the feature safely no-ops (verified) but records no durable evidence.

### Gaps Summary

No gaps. Every automated must-have — all 8 truths, all 8 artifacts, all 5
key links, and every negative check — is verified against the codebase
with passing behavioral tests, not just symbol presence. The two open
items are the plan's own deliberately deferred operator actions (live
assumption check and manual DDL apply), both safe-by-default: the hold
gate ships OFF and the Supabase layer no-ops until applied.

---

_Verified: 2026-08-12T22:05:00Z_
_Verifier: Claude (gsd-verifier)_
