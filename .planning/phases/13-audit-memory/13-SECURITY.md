---
phase: "13"
slug: "audit-memory"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-12"
---

# Phase 13 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (all six PLAN.md files carry a `<threat_model>` block).
> Audit depth: ASVS L1 grep-level verification against the implementation on branch
> `plan/phase-13` at `e6c5b1c`. No SUMMARY.md carried a `## Threat Flags` section.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Smartsheet rows -> Python audit engine | Operator-edited cell values reach `audit_results` and then the finding payload | Prices, quantities, WR numbers, free text (billing-adjacent) |
| Python process -> Supabase PostgREST (`pipeline_memory`) | Client-shaped JSONB crosses into service-role plpgsql (`upsert_audit_findings`) | Finding payloads, re-audited pair set |
| Repo DDL -> live Supabase project | Owner applies `pipeline_memory/schema.sql` by hand; the agent never holds that privilege | Schema, RLS, grants |
| Environment -> process | `AUDIT_MEMORY_ENABLED`, `RATE_SANITY_AUDIT_ENABLED`, `SUPABASE_*` read from env/CI secrets | Flags, credentials |
| Supabase response rows -> Python key construction | Server JSON of unknown shape cast to `int` in `billing_audit/snapshot_store.py` | Sheet/row ids |
| Golden baseline files -> CI quality gate | `tests/golden/mypy_baseline*.txt` feed a numeric comparison in `scripts/check_mypy_delta.sh` | Baseline counts |
| Source message strings -> durable identity | Check wording participates in the finding-key hash | Identity contract |
| PostgREST roles (`anon`, `authenticated`) -> `pipeline_memory` objects | Billing-adjacent findings must not be reachable by public/end-user roles | Findings, events, views |
| Human SQL editor -> finding lifecycle | `acknowledge_finding` is the only manual transition path | Status, actor, note |
| Internal decisions -> published runbook | Docusaurus site is operator-facing | Env-var names, object names only |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-13-01 | Tampering | `upsert_audit_findings` RPC | high | mitigate | 9× `jsonb_to_recordset` typed column lists in `schema.sql`; zero `EXECUTE`/`format(`/`quote_` in function bodies (only hits are a `GRANT EXECUTE` and a comment) | closed |
| T-13-02 | Elevation of Privilege | new plpgsql function | high | mitigate | `SET search_path = ''` on `upsert_audit_findings` (schema.sql ~L820); `test_search_path_pin_present` | closed |
| T-13-03 | Information Disclosure | audit-memory logs / Sentry breadcrumbs | medium | mitigate | `audit_findings.py` log lines carry check_id + integer counts only; orchestrator breadcrumb carries `summarize_upsert_result` integers; `_redact_exception_message(e)` on `audit_memory_error` Sentry context | closed |
| T-13-04 | Denial of Service | Supabase outage during billing run | high | mitigate | `upsert_audit_findings()` documented NEVER raises, `with_retry(..., op="audit_finding_upsert")` dedicated breaker; orchestrator hook wrapped in own `try`/`except Exception`; `AUDIT_MEMORY_ENABLED` defaults `'0'` | closed |
| T-13-05 | Repudiation | which run opened/closed a finding | medium | mitigate | `first_seen_run`/`last_seen_run` columns; every transition inserts `audit_finding_event`; `first_seen_run` set on INSERT only | closed |
| T-13-06 | Spoofing | non-pipeline writes | medium | mitigate | RLS enabled on `audit_finding` + `audit_finding_event` with `service_role_all` policies (schema.sql L965–974); `REVOKE ALL ... FROM anon, authenticated` on both views | closed |
| T-13-07 | Tampering (integrity) | finding-key orphaning | medium | mitigate | `FINDING_KEY_RECIPE_VERSION = "v1"` is first hash segment; `DATA_CONSISTENCY_ISSUE_LITERALS` pinned by `test_audit_findings.py::…literals` contract | closed |
| T-13-SC | Tampering | package installs | high | accept | No install; `requirements.txt` has zero commits on `master..HEAD` | closed |
| T-13-02-01 | Denial of Service | `snapshot_store.py` provenance loop | low | mitigate | `except (TypeError, ValueError): continue` at L375 | closed |
| T-13-02-02 | Tampering | Gate-4 mypy baseline | medium | mitigate | `mypy_baseline_count.txt` = 70; 6-gate harness green (S1608 evidence) | closed |
| T-13-02-03 | Repudiation | closed follow-up todos | low | mitigate | Todos moved with `git mv` and dated closure notes (plan 13-02 summary) | closed |
| T-13-02-04 | Information Disclosure | ledger entry content | low | mitigate | Ledger names files/constructs/counts only; secrets scan of ledger + runbook found only empty-value `SUPABASE_*=` recipe lines | closed |
| T-13-02-SC | Tampering | package installs | high | accept | No install; `requirements.txt` untouched | closed |
| T-13-03-01 | Tampering (integrity) | `_validate_data_consistency` message strings | high | mitigate | Bidirectional set-equality test `observed_issues == DATA_CONSISTENCY_ISSUE_LITERALS` (`test_audit_findings.py` L534) | closed |
| T-13-03-02 | Tampering (integrity) | unmapped check type dispatch | high | mitigate | `set(IDENTITY_RECIPES) == MEMORY_BACKED_CHECKS` asserted (L429); runtime skip with `findings_skipped_no_recipe` counter | closed |
| T-13-03-03 | Information Disclosure | dispatch WARNING/INFO lines | medium | mitigate | Warning carries `check_id=%s` only; summary line `examined=%d distinct=%d` | closed |
| T-13-03-04 | Tampering | protected audit code edit | high | mitigate | Comment-only diff acceptance criterion; audit-engine tests green (2416 passed, S1608) | closed |
| T-13-03-05 | Denial of Service | malformed finding dict | medium | mitigate | `build_finding_payloads` skips with named counters; pure data-shaping, no raise | closed |
| T-13-03-SC | Tampering | package installs | high | accept | No install; `requirements.txt` untouched | closed |
| T-13-04-01 | Tampering | RPC input | high | mitigate | Same as T-13-01; grep gate over whole schema file clean | closed |
| T-13-04-02 | Elevation of Privilege | plpgsql body | high | mitigate | Same as T-13-02; 7 `SET search_path` pins across 4 functions | closed |
| T-13-04-03 | Tampering (integrity) | premature `fixed` transition | high | mitigate | `fixed` branch is a JOIN against `jsonb_to_recordset(p_reaudited_pairs)` (schema.sql L753–790); `test_fixed_branch_joins_against_pairs_recordset` | closed |
| T-13-04-04 | Tampering (integrity) | Python-to-SQL key drift | high | mitigate | `test_audit_findings_sql_contract.py` (15 tests: recordset columns, RPC param names, CHECK value sets) | closed |
| T-13-04-05 | Repudiation | which run performed which transition | medium | mitigate | `audit_finding_event(finding_key, run_id, transition, observed_at)`; `first_seen_run` never overwritten | closed |
| T-13-04-06 | Denial of Service | oversized RPC body | medium | mitigate | Fail-open writer + dedicated breaker + orchestrator `try`/`except` (see T-13-04) | closed |
| T-13-04-07 | Information Disclosure | RPC summary counts | medium | mitigate | `RETURNS TABLE (opened, seen, fixed, resurfaced, reopened INT)`; log + breadcrumb carry only those integers | closed |
| T-13-04-08 | Tampering | concurrent/retried RPC | medium | accept | One invocation = one transaction; `finding_key` PK makes duplicates impossible; call site single-threaded once per run | closed |
| T-13-04-SC | Tampering | package installs | high | accept | No install; `requirements.txt` untouched | closed |
| T-13-05-01 | Information Disclosure | new tables + views | high | mitigate | RLS + `service_role_all` on both tables; both views `WITH (security_invoker = true)` (L993, L1028) + `REVOKE ALL FROM anon, authenticated` (L1021, L1059); `test_no_grant_to_public_or_anon_or_authenticated`, `test_both_new_tables_have_rls_enabled_and_service_role_policy`; owner confirmed live posture (obs 12221) | closed |
| T-13-05-02 | Elevation of Privilege | `acknowledge_finding` | high | mitigate | `SET search_path = ''`; two `RAISE EXCEPTION` guards on invalid transition/state; `REVOKE ALL ON FUNCTION ... FROM PUBLIC` (L1129) | closed |
| T-13-05-03 | Repudiation | manual acknowledge/suppress | medium | mitigate | Helper inserts `audit_finding_event` with `run_id = 'manual:' || actor`, `actor`, `note` in same call | closed |
| T-13-05-04 | Tampering | DDL applied to production | high | mitigate | Owner-only checkpoint executed (obs 12192/12207); statements reapply-safe; write path stayed dormant (`AUDIT_MEMORY_ENABLED=0`) | closed |
| T-13-05-05 | Denial of Service | unbounded `finding_history_by_wr` scan | low | accept | Human SQL-editor read with WR filter; volume orders of magnitude below `row_state`; retention deferred until shadow volume observed (D-CD-05) | closed |
| T-13-05-06 | Tampering (integrity) | schema applied, write path silently dormant | medium | mitigate | Exposed-schemas + schema-cache reload restated in checkpoint; PostgREST reload performed (obs 12223/12227) | closed |
| T-13-05-SC | Tampering | package installs | high | accept | No install; `requirements.txt` untouched | closed |
| T-13-06-01 | Information Disclosure | published runbook + env reference | medium | mitigate | Secrets scan of `website/docs`, `configuration-environment.md`, ledger: no JWT, DSN, connection string, or key value present | closed |
| T-13-06-02 | Tampering | scoped ROADMAP/REQUIREMENTS edits | medium | mitigate | ROADMAP.md 1047 lines / 16 phase sections, REQUIREMENTS.md 472 lines — intact; D-13-A referenced 10× across ROADMAP/REQUIREMENTS/CONTEXT | closed |
| T-13-06-03 | Repudiation | cancelled/deferred scope | medium | mitigate | D-13-A closure recorded with id and date in three documents (obs 12238) | closed |
| T-13-06-04 | Tampering (integrity) | future reword of load-bearing message string | high | mitigate | Ledger entry states the coupling; CI contract test from 13-03 is the enforcement | closed |
| T-13-06-05 | Spoofing | operator misreading flag state | low | mitigate | Both catalogs and runbook state default `0`; runbook warns empty result set means flag off (obs 12249/12250) | closed |
| T-13-06-SC | Tampering | package installs | high | accept | No install; website build uses existing lockfile | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Residual notes (non-blocking, L1 observation)

- The orchestrator's failure path logs `f"⚠️ Audit-memory write failed: {e}"` with the raw
  exception text while the Sentry context uses `_redact_exception_message(e)`. This matches
  the existing audit-engine block's pattern and the planned mitigation (redaction on the Sentry
  side). PostgREST error bodies do not echo the request payload, so no finding data is
  expected in `e`; revisit if `SENTRY_ENABLE_LOGS` is ever turned on.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-13-01 | T-13-SC, T-13-02-SC, T-13-03-SC, T-13-04-SC, T-13-05-SC, T-13-06-SC | No package installed in any plan; `requirements.txt` has no commits on `master..HEAD`; website build uses existing lockfile. Any future install task must run the package-legitimacy gate first. | Juan Flores (plan-time disposition) | 2026-09-11 |
| AR-13-02 | T-13-04-08 | One plpgsql invocation is one transaction and `finding_key` is the PK, so retries are idempotent. `pipeline_memory/client.py` breaker lock fix (PR #407 precedent in `billing_audit/client.py`) is a tracked, separately-owned follow-up scoped out by CONTEXT.md. | Juan Flores (plan-time disposition) | 2026-09-11 |
| AR-13-03 | T-13-05-05 | `finding_history_by_wr` is a human SQL-editor read with a WR filter; finding volume is far below `row_state`. Retention is deliberately unmeasured until shadow-mode volume is observed (D-CD-05). | Juan Flores (plan-time disposition) | 2026-09-11 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-12 | 41 | 41 | 0 | /gsd:secure-phase (Claude Fable 5.1, L1 grep verification; auditor subagent skipped per ASVS-1 short-circuit) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-12
