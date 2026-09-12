---
phase: 13-audit-memory
verified: 2026-09-12T03:45:00Z
status: human_needed
score: 13/14 must-haves verified
covered_files: [".github/prompts/configuration-environment.md", ".planning/REQUIREMENTS.md", ".planning/ROADMAP.md", ".planning/phases/13-audit-memory/13-01-PLAN.md", ".planning/phases/13-audit-memory/13-01-SUMMARY.md", ".planning/phases/13-audit-memory/13-02-PLAN.md", ".planning/phases/13-audit-memory/13-02-SUMMARY.md", ".planning/phases/13-audit-memory/13-03-PLAN.md", ".planning/phases/13-audit-memory/13-03-SUMMARY.md", ".planning/phases/13-audit-memory/13-04-PLAN.md", ".planning/phases/13-audit-memory/13-04-SUMMARY.md", ".planning/phases/13-audit-memory/13-05-PLAN.md", ".planning/phases/13-audit-memory/13-05-SUMMARY.md", ".planning/phases/13-audit-memory/13-06-PLAN.md", ".planning/phases/13-audit-memory/13-06-SUMMARY.md", ".planning/phases/13-audit-memory/13-CONTEXT.md", ".planning/phases/13-audit-memory/13-DISCUSSION-LOG.md", ".planning/phases/13-audit-memory/13-PATTERNS.md", ".planning/phases/13-audit-memory/13-RESEARCH.md", ".planning/phases/13-audit-memory/13-VALIDATION.md", "billing_audit/snapshot_store.py", "docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md", "memory-bank/living-ledger.md", "pipeline/config.py", "pipeline/orchestrate.py", "pipeline_memory/audit_findings.py", "pipeline_memory/client.py", "pipeline_memory/schema.sql", "tests/golden/mypy_baseline.txt", "tests/golden/mypy_baseline_count.txt", "tests/test_audit_findings.py", "tests/test_audit_findings_sql_contract.py", "tests/test_snapshot_store.py", "website/docs/reference/environment.md", "website/docs/runbook/operations.md"]
covered_digest: "v1:sha256:c83bcff209e41f9001831d589abbaeaf50fe278164f4c0464ec81476ada37c71"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Observe several consecutive scheduled (frequent) production runs after AUDIT_MEMORY_ENABLED=1 is flipped on, and compare audit-memory wall-clock / row-count with the count of affected groups + currently-open findings (the INFO log lines 'Audit-memory findings: examined=N distinct=N' and 'Audit-memory upsert: findings_sent=N reaudited_pairs_sent=N ...' plus the existing incremental-read affected-set logging)."
    expected: "Audit-memory processing time/row-count scales with (affected groups + open findings), not with the full historical finding/row volume, across several consecutive runs."
    why_human: "Success criterion 2 is an operational/production performance property. No local Postgres or scheduled-run harness exists in this repo to execute upsert_audit_findings against real volume; the code path (SQL joins scoped to p_reaudited_pairs / incoming, Python iterating only audit_results emitted this run) is architecturally consistent with proportional cost, and the required observability logging is in place, but the actual wall-clock proportionality can only be confirmed by watching real scheduled runs (CONTEXT.md: 'measured, not asserted')."
---

# Phase 13: Audit Memory Verification Report

**Phase Goal:** Audit findings persist across runs like a task list: created once, carried
while unresolved, closed when the fixing run no longer reproduces them.
**Verified:** 2026-09-12
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | AUD-01: `audit_finding`/`audit_finding_event` persist every finding with a stable key and full lifecycle (`open → fixed \| resurfaced \| acknowledged \| suppressed`) | ✓ VERIFIED | `pipeline_memory/schema.sql:695-950` (tables + `upsert_audit_findings` RPC implementing the full D-08 transition table); `pipeline_memory/audit_findings.py` builds versioned sha256 `finding_key` per D-01 recipe for all three `MEMORY_BACKED_CHECKS`; 74/74 module+contract tests pass |
| 2 | Success criterion 1: a seeded finding survives 3 runs untouched, transitions to `fixed` on the run that stops reproducing it, and to `resurfaced` after being acknowledged and reappearing | ✓ VERIFIED | Python-side sequence pinned by `tests/test_audit_findings.py::test_lifecycle_success_criterion_1_sequence_sends_correct_payload_each_run`; server-side transition state machine live-verified via owner-run 7-step Supabase read-back recorded verbatim in 13-05-SUMMARY.md (opened→seen→fixed→reopened→acknowledged→resurfaced against migration `audit_memory_findings_lifecycle_views` v20260912023008) — treated as authoritative live-apply evidence per task instructions |
| 3 | AUD-02: each run evaluates only affected groups + open findings; a finding not reproduced on a re-audited group becomes `fixed` with the fixing run id; a finding whose group was not re-audited is left untouched | ✓ VERIFIED | `upsert_audit_findings`'s `to_fix` CTE joins `audit_finding` to `p_reaudited_pairs` (never a bare `NOT EXISTS` over the whole table); per-check scoping via `check_id` in the pair, mirroring `RATE_SANITY_AUDIT_ENABLED`; `build_reaudited_pairs`/`executed_checks` in `pipeline_memory/audit_findings.py`; 11 `test_lifecycle_*`/`test_build_reaudited_pairs_*` tests cover reproduced / re-audited-not-reproduced / group-absent / empty-set / disabled-check cases |
| 4 | An empty re-audited pair set transitions nothing to `fixed`; empty input is never read as "everything was fixed" | ✓ VERIFIED | SQL `to_fix` CTE is a JOIN against `jsonb_to_recordset(p_reaudited_pairs)` (empty array → empty join, structurally); `test_lifecycle_empty_audited_row_set_sends_empty_pairs`, `test_build_reaudited_pairs_empty_*` |
| 5 | Suppressed findings never change status on re-detection but still bump `last_seen_run`; acknowledged→resurfaced; fixed→open again with `reopened` event | ✓ VERIFIED | `upsert_audit_findings` ON CONFLICT CASE (acknowledged→resurfaced, fixed→open+fixed_run cleared, else unchanged) + transition-logging CASE; pinned by `tests/test_audit_findings_sql_contract.py::CheckValueSetContractTests`/structural asserts and the live read-back sequence |
| 6 | AUD-03 (re-scoped by D-07): `pipeline_memory.open_findings` (status IN open/resurfaced, deterministic order) and `pipeline_memory.finding_history_by_wr` (LEFT JOIN, never drops an event-less finding) ship; the Excel/portal visual surface is explicitly NOT built in Phase 13 | ✓ VERIFIED | `pipeline_memory/schema.sql:993-1059`; `tests/test_audit_findings_sql_contract.py::OpenFindingsViewContractTests`/`FindingHistoryByWrViewContractTests`; ROADMAP.md Phase 13 success-criterion-3 re-scope note + Backlog entry; `_log_to_audit_sheet` untouched placeholder confirmed (no Excel/portal file created) |
| 7 | `acknowledge_finding(finding_key, actor, transition, note)` applies the transition and writes its event row atomically, service-role only, rejecting bad transitions/unknown keys | ✓ VERIFIED | `pipeline_memory/schema.sql:1086-1130`; `REVOKE ALL ... FROM PUBLIC`; `tests/test_audit_findings_sql_contract.py::AcknowledgeFindingContractTests` |
| 8 | Both new tables + both views: RLS/service-role-only, `anon`/`authenticated` blocked on tables and views alike | ✓ VERIFIED | `schema.sql:965-974` (RLS + policy), `:1021`/`:1059` (view REVOKEs); `AuditTablesRlsContractTests`; live catalog read-back in 13-05-SUMMARY confirms RLS enabled and anon/authenticated denied (401/42501 PostgREST probe) |
| 9 | D-09: with `AUDIT_MEMORY_ENABLED` unset (default), zero audit-memory Supabase calls and byte-identical Excel/upload/`run_summary.json` output | ✓ VERIFIED | `pipeline/config.py:550-551` defaults `'0'`; `_run_audit_memory_phase` self-gates on the flag; `bash scripts/run_6_gates.sh` Gate 6 passed with `AUDIT_MEMORY_ENABLED` unset — "PASS: run_summary.json structure matches baseline (30 keys)" |
| 10 | A Supabase failure/breaker-open/exception in the audit-memory hook logs+Sentry-breadcrumbs and lets the run continue; dedicated `audit_finding_upsert` breaker op shared with no other `pipeline_memory` operation | ✓ VERIFIED | `pipeline/orchestrate.py:2995-3020` wraps the whole hook in its own try/except (outside the audit-engine block); `with_retry(_invoke, op="audit_finding_upsert")` is the only use of that op string in the codebase |
| 11 | D-06/D-13-A: `wr_week_ownership` is permanently dropped, not deferred — no table/view/rung built, and every document that said "deferred to Phase 13" is corrected | ✓ VERIFIED | `grep -c wr_week_ownership` schema.sql shows only the header-comment/prior-draft references, no `CREATE TABLE`/`CREATE VIEW`; `grep -rn "deferred to Phase 13"` across REQUIREMENTS.md/ROADMAP.md/design-spec returns zero matches; design spec §3 lines 190-191 annotated SUPERSEDED |
| 12 | Folded todos closed: `snapshot_store.py` narrowing guard + mypy baseline drop (71→70), `run_ledger.sheets_changed` populated & pinned, Gate-4 hardening todo deliberately deferred | ✓ VERIFIED | `billing_audit/snapshot_store.py` guard present; `tests/golden/mypy_baseline_count.txt` = 70, confirmed by Gate 4 "PASS: mypy delta neutral or improved (70 -> 70)"; `.planning/todos/done/2026-08-25-{run-memory-review-followups,fix-snapshot-store-int-arg-type}.md` archived; `.planning/todos/pending/2026-08-25-harden-check-mypy-delta-followups.md` remains with dated deferral note in ROADMAP backlog |
| 13 | Operator documentation: `AUDIT_MEMORY_ENABLED` documented in both catalogs; runbook covers reading open findings / per-WR history / acknowledging via SQL, names the owning component (Python pipeline + `pipeline_memory` schema, not portal/Notion) | ✓ VERIFIED | `website/docs/reference/environment.md:861-879`, `.github/prompts/configuration-environment.md:19`, `website/docs/runbook/operations.md:186,256-311` (`Audit-memory findings (Phase 13)` section) |
| 14 | Success criterion 2: audit wall clock on frequent runs is proportional to affected groups + open findings | ⚠️ Needs human verification | Architecturally consistent (SQL `to_fix`/upsert CTEs scoped to `p_reaudited_pairs`/incoming findings only; `build_finding_payloads` iterates only this run's emitted findings) and the required observability logging exists (`examined=/distinct=`, `findings_sent=/reaudited_pairs_sent=/opened=.../reopened=`), but the actual wall-clock proportionality is a production-observed property with no local harness — see Human Verification below |

**Score:** 13/14 truths verified (1 routed to human verification; 0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline_memory/audit_findings.py` | Key derivation, payload building, re-audit pairs, upsert wrapper | ✓ VERIFIED | 672 lines, substantive, imported/used by `pipeline/orchestrate.py` |
| `pipeline_memory/schema.sql` (audit-memory section) | Tables, RPC, views, RLS, `acknowledge_finding` | ✓ VERIFIED | Lines 681-1131; reapply-safe (`CREATE ... IF NOT EXISTS`/`CREATE OR REPLACE`); applied live as migration `audit_memory_findings_lifecycle_views` v20260912023008 (13-05-SUMMARY) |
| `pipeline/config.py` (`AUDIT_MEMORY_ENABLED`) | Default-off flag | ✓ VERIFIED | `os.getenv('AUDIT_MEMORY_ENABLED', '0')` |
| `pipeline_memory/client.py` (`_audit_write_enabled`) | Live re-read of the flag | ✓ VERIFIED | Lines 136-149 |
| `pipeline/orchestrate.py` (`_run_audit_memory_phase` + call site) | Wired hook, own try/except | ✓ VERIFIED | Lines 2084-2131 (function), 2995-3020 (call site) |
| `tests/test_audit_findings.py` | Unit test suite | ✓ VERIFIED | 1024 lines, 60+ tests, all passing |
| `tests/test_audit_findings_sql_contract.py` | Python↔SQL lockstep contract | ✓ VERIFIED | 329 lines, 14 test classes, all passing |
| `billing_audit/snapshot_store.py` | Narrowing guard (folded todo) | ✓ VERIFIED | Guard present; regression tests in `tests/test_snapshot_store.py` |
| `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, design spec, runbook docs | Documentation closure | ✓ VERIFIED | See truths #11, #13 above |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `pipeline/orchestrate.py` audit call site | `pipeline_memory.audit_findings.build_finding_payloads` | direct call, own try/except block | ✓ WIRED | Confirmed at lines 2124-2131, 2995-3020 |
| `pipeline_memory.audit_findings.upsert_audit_findings` | `pipeline_memory.upsert_audit_findings` RPC | `with_retry(op='audit_finding_upsert')` → `client.schema('pipeline_memory').rpc(...)` | ✓ WIRED | `audit_findings.py:650-657` |
| `pipeline.config.AUDIT_MEMORY_ENABLED` | `pipeline_memory.client._audit_write_enabled()` | live env re-read | ✓ WIRED | `client.py:136-149` |
| `audit_findings.IDENTITY_RECIPES` | `compute_finding_key` | ordered identity values → sha256 | ✓ WIRED | `audit_findings.py:64-68, 152-165` |
| `pipeline_memory.audit_finding.status` | `pipeline_memory.open_findings` WHERE clause | view definition | ✓ WIRED | `schema.sql:1018` |
| `pipeline_memory.acknowledge_finding` | `audit_finding` UPDATE + `audit_finding_event` INSERT | single plpgsql function, same transaction | ✓ WIRED | `schema.sql:1086-1127` |
| `pipeline_memory/schema.sql` (repo DDL) | live Supabase project `poeyztlmsawfoqlanucc` | owner-applied migration | ✓ WIRED | 13-05-SUMMARY.md Task 2/3 evidence (treated as authoritative per task instructions) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Module test suite for audit-memory | `pytest tests/test_audit_findings.py tests/test_audit_findings_sql_contract.py -q` | 74 passed | ✓ PASS |
| Full repo test suite | `pytest tests/ -q` | 2416 passed, 1 skipped, 595 subtests | ✓ PASS (matches expected) |
| 6-gate harness | `bash scripts/run_6_gates.sh` | mypy delta 70→70, py_compile clean, `run_summary.json` matches baseline (30 keys), `AUDIT_MEMORY_ENABLED` unset throughout | ✓ PASS |
| No `wr_week_ownership` object created | `grep -n "CREATE TABLE.*wr_week_ownership\|CREATE VIEW.*wr_week_ownership" pipeline_memory/schema.sql` | no match (exit 1) | ✓ PASS |
| No stale "deferred to Phase 13" wording remains | `grep -rn "deferred to Phase 13" REQUIREMENTS.md ROADMAP.md design-spec` | no match (exit 1) | ✓ PASS |
| Dedicated breaker op not shared | `grep -rn "audit_finding_upsert" pipeline_memory/*.py` | single use site in `audit_findings.py` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| AUD-01 | 13-01, 13-02, 13-03, 13-04, 13-05 | `audit_finding`/`audit_finding_event` persist findings with stable key + lifecycle | ✓ SATISFIED | Truths #1, #5, #9, #10 above |
| AUD-02 | 13-04 | Each run evaluates only affected groups + open findings; unreproduced findings on re-audited groups become `fixed` | ✓ SATISFIED | Truths #3, #4 above |
| AUD-03 | 13-05, 13-06 | SQL views for open + resurfaced findings and per-WR history (re-scoped by D-07 to SQL-only) | ✓ SATISFIED (SQL scope) | Truths #6, #7, #8 above; visual-surface half explicitly deferred to a named ROADMAP backlog item, not a gap |

No orphaned requirement IDs — AUD-01/02/03 are the phase's full requirement set and each is claimed by at least one plan's `requirements:` frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.planning/REQUIREMENTS.md` | AUD-01/02/03 checkbox lines | Marked `[x] Complete` by the automated `requirements.mark-complete` step during plan execution (commits `9165cb0`, `48e1d38`, `2c107dd`), even though `13-06-PLAN.md`'s own `prohibitions` block states "Do not mark AUD-01, AUD-02, or AUD-03 complete in REQUIREMENTS.md; requirement checkboxes are closed by verify-work, not by a plan." | ℹ️ Info | Process/governance inconsistency only — the framework's shared-ID completion gate ran ahead of this verification step. The resulting checkbox state happens to match this verification's own findings (all three are in fact satisfied), so there is no functional discrepancy, but the stated plan prohibition was not honored. Same pattern occurred for OWN-01..04 in Phase 12, so this appears to be standard (if under-documented) framework behavior in this repo rather than an isolated mistake. |
| `.planning/REQUIREMENTS.md` | AUD-03 line | The AUD-03 checkbox text ("Excel/portal audit surfaces open + resurfaced findings only") carries no re-scope blockquote annotation the way OWN-01/OWN-02 do for D-13-A, even though D-07 re-scoped it to SQL-only in Phase 13 | ℹ️ Info | Minor documentation-completeness gap. ROADMAP.md's Phase 13 success-criterion-3 and Backlog section already carry the explicit re-scope note and decision trigger, so the re-scope is discoverable and not silently lost — per this task's explicit instruction, the deferred visual surface is "a tracked backlog item, NOT a Phase 13 gap." Not treated as a gap here. |

No debt markers (`TODO`/`FIXME`/`XXX`/`TBD`) found in any Phase 13 code file (`pipeline_memory/audit_findings.py`, `pipeline_memory/schema.sql`, `pipeline/orchestrate.py`).

### Human Verification Required

### 1. Audit wall-clock proportionality (Success Criterion 2)

**Test:** After `AUDIT_MEMORY_ENABLED=1` is flipped on in a later owner decision, observe several consecutive frequent (2-hour cadence) scheduled production runs and compare the audit-memory phase's row/time cost against the count of affected `(wr, week_ending)` groups plus currently-open findings, using the `examined=/distinct=` and `findings_sent=/reaudited_pairs_sent=/opened=.../reopened=` INFO log lines this phase added.

**Expected:** Audit-memory processing cost scales with (affected groups + open findings) for a frequent run, not with the full historical finding or row volume — i.e., a frequent run touching a handful of groups should not become slower as the total finding backlog grows.

**Why human:** This is a live, production-observed performance property. No local Postgres instance, scheduled-run harness, or realistic finding-volume fixture exists in this repository to execute `upsert_audit_findings` at scale, and `AUDIT_MEMORY_ENABLED` ships default-off (D-09) so the write path has produced no production data yet. The code's structure (SQL `to_fix`/`ON CONFLICT` operate over CTEs scoped to the incoming `p_findings`/`p_reaudited_pairs` payloads rather than a full-table scan; Python's `build_finding_payloads` iterates only the findings `audit_financial_data` emitted this run) is consistent with the proportionality claim, and the logging needed to observe it is now in place — but the wall-clock claim itself, per CONTEXT.md, is explicitly "measured, not asserted," and can only be confirmed once flipped on in shadow.

### Gaps Summary

No blocking gaps. All AUD-01/AUD-02/AUD-03 must-haves that can be verified from the repository (schema, RPC transition logic, Python payload/key derivation, RLS/security posture, fail-open/default-off rollout contract, documentation and ledger closure, folded-todo cleanup) are present, substantively implemented, wired together, and covered by 74 passing unit/contract tests plus a full 2416-test regression pass and a green 6-gate harness run with byte-identical golden output. The single open item — success criterion 2's wall-clock proportionality — is an inherently production-observed property that this phase correctly instrumented (INFO log lines) but cannot itself prove offline; it is routed to human verification rather than treated as a functional gap. Two ℹ️ Info findings around `REQUIREMENTS.md` checkbox governance are noted for awareness but do not affect the phase's technical completeness.

---

*Verified: 2026-09-12*
*Verifier: Claude (gsd-verifier)*
