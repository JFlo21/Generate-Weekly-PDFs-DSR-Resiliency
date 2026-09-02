---
phase: "12"
slug: "ownership-last-known-foreman-as-of-the-week"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-02"
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `12-RESEARCH.md` § Validation Architecture; the planner refines the
> per-task map and validate-phase sets `nyquist_compliant`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (unittest-style `TestCase` classes; `tests/test_sentinel_never_a_claimer.py`, `tests/test_billing_audit_shadow.py`) |
| **Config file** | none dedicated — defaults; suite runs via `pytest tests/ -v` (CLAUDE.md) |
| **Quick run command** | `python -m pytest tests/test_sentinel_never_a_claimer.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` (phase gate adds `bash scripts/run_6_gates.sh`) |
| **Estimated runtime** | ~60–120 seconds (full suite); ~5 seconds (quick) |

---

## Sampling Rate

- **After every task commit:** Run the targeted test file for the touched area (e.g. `python -m pytest tests/test_sentinel_never_a_claimer.py -q` after a `billing_audit/writer.py` change) plus `python -m py_compile generate_weekly_pdfs.py` after any pipeline-module change
- **After every plan wave:** Run `python -m pytest tests/ -q` and `bash scripts/run_6_gates.sh`
- **Before `/gsd:verify-work`:** Full suite must be green (`bash scripts/run_6_gates.sh`); OWN-03's dry-run report must be manually approved by Juan against the WR 19073866 known-good sample before any `--apply` run
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-TBD | TBD | TBD | OWN-01 | — | No cross-week inheritance: a row with no in-week observation stays sentinel even if a prior week had a real claimer | unit | `python -m pytest tests/test_sentinel_never_a_claimer.py -q` | ❌ W0 | ⬜ pending |
| 12-TBD | TBD | TBD | OWN-02 (CR-01) | — | A real claimer name with leading space/apostrophe/paren is NOT treated as a sentinel by `_is_sentinel_identifier` (attachment cleanup never deletes a real person's file) | unit | `python -m pytest tests/test_cleanup.py -q -k sentinel` | ❌ W0 | ⬜ pending |
| 12-TBD | TBD | TBD | OWN-02 (WR-01) | — | `orchestrate.py` imports `AttachmentParentType` lazily/guarded like `discovery.py` | structural | `python -m pytest tests/test_billing_audit_shadow.py -q -k import` | ❌ W0 | ⬜ pending |
| 12-TBD | TBD | TBD | OWN-03 | — | `--dry-run` report for WR 19073866 WE 082425/083125/091425/092125 resolves `_User_Avery_Example` via `backfill_hash_history`; no live Smartsheet/Supabase writes in dry-run | integration (fixtures) | `python -m pytest tests/test_backfill_claim_time_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-TBD | TBD | TBD | OWN-03 | — | Script never sends a `p_rows` entry for a row whose current `frozen_<role>` is a real (non-sentinel) name | unit | `python -m pytest tests/test_backfill_claim_time_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-TBD | TBD | TBD | OWN-04 | — | N/A (documentation) | manual | `cd website && npm run build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_backfill_claim_time_attribution.py` — new file: OWN-03 dry-run report generation, source precedence (1→5), no-cross-week-lookup, never-overwrite-a-real-name
- [ ] `tests/test_cleanup.py` (new, unless an existing cleanup test file is found) — CR-01 leading-punctuation regression for `_is_sentinel_identifier`
- [ ] Structural/grep-based test for WR-01's lazy import, mirroring `tests/test_billing_audit_shadow.py` `_read_source`/`_collapse_ws` pattern
- [ ] Fixtures for the backfill sources: mock `pipeline_memory.row_event` rows, mock `attribution_snapshot` rows, mock `public.artifacts` filenames, a small frozen `hash_history.json` fixture (fixtures-before-live-data rule)
- [ ] Extend `ResolveClaimerSentinelTests` in `tests/test_sentinel_never_a_claimer.py` with a no-cross-week-inheritance case (OWN-01)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dry-run backfill report approved before live remediation | OWN-03 | Protected billing/attribution data; owner approval is a production guardrail | Run the script with `--dry-run`, review `generated_docs/` report for WR 19073866 and the 93-WR set, Juan approves, then `--apply` |
| Owner-deployed Supabase SQL (backup table, provenance columns, `backfill_attribution` RPC) | OWN-03 | Supabase DDL/RPC is data-team-owned and applied by Juan in the SQL editor, never by pipeline code | Juan pastes the shipped `.sql` file, confirms column names against the live `attribution_snapshot` schema |
| Runbook + Living Ledger document the amended Foundation A contract | OWN-04 | Documentation | `cd website && npm run typecheck && npm run build`; ledger entry dated `[YYYY-MM-DD HH:MM]` present |
| Scheduled run shows no `_User_Unknown_Foreman` / `_User__NO_MATCH` churn | OWN-03 | Observed in the post-remediation GitHub Actions run, not a unit test | Inspect the next scheduled `weekly-excel-generation.yml` run summary |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
