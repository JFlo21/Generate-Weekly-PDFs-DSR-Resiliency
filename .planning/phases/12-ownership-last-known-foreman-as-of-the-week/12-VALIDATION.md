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
| 12-01-T1 | 12-01 | 1 | OWN-01, OWN-03 | T-12-02, T-12-05 | Tracer: dry-run for WR 19073866 WE 082425/083125/091425/092125 proposes `Avery Example` via `backfill_hash_history`; zero Supabase writes; report is git-ignored | integration (fixtures) | `python -m pytest tests/test_backfill_claim_time_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-01-T2 | 12-01 | 1 | OWN-01, OWN-03 | T-12-04 | Sources 1–4 resolve under a total deterministic precedence; two real names in one week ⇒ `conflict`; zero candidates ⇒ `unresolved` + exit 0; no source reads outside the row's own week | integration (fixtures) | `python -m pytest tests/test_backfill_claim_time_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-01-T3 | 12-01 | 1 | OWN-03 | T-12-01, T-12-06 | `p_rows` never contains a row whose current frozen value is a real name; `--apply` refused without `--i-approved-this` (exit 4) or without the backup table (exit 3) | unit | `python -m pytest tests/test_backfill_claim_time_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-02-T1 | 12-02 | 2 | OWN-02 (CR-01) | T-12-07, T-12-09 | A real claimer name with leading space/apostrophe/paren is NOT treated as a sentinel by `_is_sentinel_identifier`; every previously-pinned sentinel spelling still is | unit | `python -m pytest tests/test_sentinel_superseded_cleanup.py -q` | ✅ (extend) | ⬜ pending |
| 12-02-T2 | 12-02 | 2 | OWN-02 (WR-01) | T-12-08 | `pipeline/orchestrate.py` imports `AttachmentParentType` inside `_is_row_attachment`, guarded, mirroring `pipeline/discovery.py`; degrades to the string comparison instead of raising | structural + unit | `python -m pytest tests/test_lazy_smartsheet_imports.py -q` | ❌ W0 | ⬜ pending |
| 12-03-T1 | 12-03 | 2 | OWN-01, OWN-03 | T-12-10, T-12-11, T-12-12, T-12-15 | The owner-applied SQL uses typed `jsonb_to_recordset`, a server-side sentinel-only `WHERE`, `SET search_path = ''`, `service_role`-only grant; no `EXECUTE format`, no `TO anon` / `TO authenticated`; SQL and Python sentinel families agree | structural | `python -m pytest tests/test_own03_backfill_sql_contract.py -q` | ❌ W0 | ⬜ pending |
| 12-03-T2 | 12-03 | 2 | OWN-01, OWN-03 | — | `billing_audit/schema.sql` carries the `backfill_attribution` contract-as-comment block (jsonb `p_rows` I/O contract, sentinel-only `WHERE`, `updated` / `skipped_real_name` / `skipped_no_row` return statuses) matching the owner-deployed SQL file; the function body stays owner-deployed | structural | `python -m pytest tests/test_own03_backfill_sql_contract.py -q` | ❌ W0 | ⬜ pending |
| 12-03-T4 | 12-03 | 2 | OWN-03 | T-12-13 | Owner-applied DDL/RPC verified live: STEP 4 predicate spot check `true, true, false`; STEP 6 no-op call returns `skipped_no_row` with zero rows carrying `backfill_run_id` | manual (owner) | — (`checkpoint:human-verify`, `gate="blocking-human"`) | n/a | ⬜ pending |
| 12-04-T1 | 12-04 | 2 | OWN-03 | T-12-16 | Source 5 self-paces (no sleep before the first call), stops at the request / row / deadline cap and reports the capped rows `unresolved`; a per-row exception leaves that row unresolved; `--check-backlog` issues zero Smartsheet calls | unit | `python -m pytest tests/test_backfill_cell_history_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-04-T2 | 12-04 | 2 | OWN-03 | T-12-17 | No production module calls `get_cell_history` (allowlist = `pipeline/snapshot_drift.py` only) or reads `CELL_HISTORY_BACKFILL*`; `audit_billing_changes.py` stays a stub | structural | `python -m pytest tests/test_backfill_cell_history_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-04-T4 | 12-04 | 2 | OWN-03 | T-12-18, T-12-21 | Workflow has its own concurrency group, `timeout-minutes` > `CELL_HISTORY_BACKFILL_MAX_MINUTES`, `permissions: contents: read`, no `${{` in `run:` text, no `--apply`, and a `backlog_rows` gate | structural | `python -m pytest tests/test_backfill_cell_history_attribution.py -q` | ❌ W0 | ⬜ pending |
| 12-05-T1 | 12-05 | 3 | OWN-01, OWN-04 | T-12-23 | The runbook documents the ladder AS IMPLEMENTED (D-12-A, D-12-B) with zero occurrences of the dropped cross-week rung, `--hash-history`, `ATTACHMENT_PREFETCH_` or `DISCOVERY_CACHE_`; the sidebar reaches the page | structural | `python -m pytest tests/test_own04_documentation.py -q` | ❌ W0 | ⬜ pending |
| 12-05-T2 | 12-05 | 3 | OWN-04 | T-12-23 | The Docusaurus site builds with no broken links after the new page and the three rewritten pages | integration | `npm --prefix website run build` | ✅ | ⬜ pending |
| 12-05-T3 | 12-05 | 3 | OWN-04 | T-12-24 | One dated `[YYYY-MM-DD HH:MM]` Living Ledger entry records D-12-A, D-12-B, CR-01, WR-01 and the source-5 isolation rule; `CLAUDE.md` unmodified; no credential-shaped string | structural | `python -m pytest tests/test_own04_documentation.py -q` | ❌ W0 | ⬜ pending |
| 12-06-T1 | 12-06 | 4 | OWN-03 | T-12-28 | Dry-run over live data reviewed and approved by Juan; WR 19073866's four weeks resolve to `Avery Example` via `backfill_hash_history`; `public.artifacts` cross-check recorded | manual (owner) | — (`checkpoint:human-verify`, `gate="blocking-human"`) | n/a | ⬜ pending |
| 12-06-T3 | 12-06 | 4 | OWN-03 | T-12-25, T-12-30 | Apply exits 0; the four tallies recorded; comparison against the dated backup shows 0 differences for rows with a NULL `backfill_run_id`; provenance breakdown totals the `updated` tally | manual (owner) | — (`checkpoint:human-verify`, `gate="blocking-human"`) | n/a | ⬜ pending |
| 12-06-T4 | 12-06 | 4 | OWN-02, OWN-03 | T-12-26, T-12-27 | Post-apply scheduled run: `sentinel_claimers_ignored` drops, WR 19073866 carries `_User_Avery_Example` attachments, the stale placeholder attachments are gone, no PPP attachment and no real claimer's attachment deleted | manual (owner) | — (`checkpoint:human-verify`, `gate="blocking-human"`) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Phase-gate command (every wave merge):** `python -m pytest tests/ -q` and `bash scripts/run_6_gates.sh` (expect `ALL 6 GATES PASSED`).

---

## Wave 0 Requirements

- [ ] `tests/test_backfill_claim_time_attribution.py` — new file (plan 12-01): OWN-03 dry-run report generation, source precedence 1→4, no-cross-week-lookup, never-overwrite-a-real-name, determinism, `p_rows` key-set pin
- [ ] Module-level source fixtures inside that test file (fixtures-before-live-data rule): mock `pipeline_memory.row_event` / `row_state` rows, mock `attribution_snapshot` roles, mock `public.artifacts` filenames, mock `billing_audit.group_content_hash` + `pipeline_memory.group_state` rows for the WR 19073866 known-good sample. **No separate fixtures package and no `hash_history.json` fixture file** — D-12-B replaced source 4's JSON with the Supabase hash store.
- [ ] `tests/test_sentinel_superseded_cleanup.py` — EXTEND `SentinelIdentifierPredicateTests` with the CR-01 leading-punctuation regression. **Supersedes the seed's `tests/test_cleanup.py`**: that file was seeded before this session confirmed `tests/test_sentinel_superseded_cleanup.py` already owns `_is_sentinel_identifier` coverage (`grep -n class` → `SentinelIdentifierPredicateTests` at line 103). A second cleanup test surface would be a duplicate, not a gap.
- [ ] `tests/test_lazy_smartsheet_imports.py` — new file (plan 12-02): WR-01 structural + behavioral coverage, mirroring `tests/test_billing_audit_shadow.py:2617-2638`'s `_read_source` / `_collapse_ws` idiom
- [ ] `tests/test_own03_backfill_sql_contract.py` — new file (plan 12-03): structural gate over the owner-applied SQL's security-critical shape and the SQL/Python sentinel-family agreement
- [ ] `tests/test_backfill_cell_history_attribution.py` — new file (plan 12-04): paced/capped fetch, per-row never-raises, backlog check, the production-isolation allowlist, and the workflow structural checks
- [ ] `tests/test_own04_documentation.py` — new file (plan 12-05): runbook and Living Ledger content gates
- [ ] OWN-01's "no cross-week inheritance" is asserted as a **negative source gate** in `tests/test_backfill_claim_time_attribution.py` (zero non-comment occurrences of the dropped rung in the script) rather than as a `ResolveClaimerSentinelTests` behavioral case — per D-12-A the rung is never implemented, so there is no runtime behavior to exercise. `tests/test_sentinel_never_a_claimer.py` is unchanged by this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dry-run backfill report approved before live remediation | OWN-03 | Protected billing/attribution data; owner approval is a production guardrail | Run the script with `--dry-run`, review `generated_docs/` report for WR 19073866 and the 93-WR set, Juan approves, then `--apply` |
| Owner-deployed Supabase SQL (backup table, provenance columns, `backfill_attribution` RPC) | OWN-03 | Supabase DDL/RPC is data-team-owned and applied by Juan in the SQL editor, never by pipeline code | Juan pastes the shipped `.sql` file, confirms column names against the live `attribution_snapshot` schema |
| Runbook + Living Ledger document the amended Foundation A contract | OWN-04 | Documentation | `npm --prefix website run typecheck && npm --prefix website run build`; ledger entry dated `[YYYY-MM-DD HH:MM]` present |
| Owner authorizes the one-way Supabase DDL apply | OWN-03 | Production schema change on a data-team-owned billing table | 12-03 Task 3 `checkpoint:decision`, `gate="blocking-human"`; options `approve` / `approve-with-correction` / `hold` |
| Owner authorizes a new scheduled workflow on the shared Smartsheet token | OWN-03 | GitHub Actions schedule change consuming the production rate budget | 12-04 Task 3 `checkpoint:decision`, `gate="blocking-human"`; options `approve-cron` / `approve-dispatch-only` / `hold` |
| Owner authorizes the one-way live backfill write | OWN-03 | Bulk write to production billing attribution + downstream attachment replacement | 12-06 Task 2 `checkpoint:decision`, `gate="blocking-human"`; options `apply-full` / `apply-scoped` / `hold` |
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
