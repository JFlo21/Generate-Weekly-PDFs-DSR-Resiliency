---
phase: 10
slug: run-memory-foundation-shadow-writes
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-25
scope: all six Phase 10 plans (threat registers authored at plan time); register reconstructed by the auditor from every PLAN <threat_model> block, which surfaced T-10-SC (present in all six plans, absent from the orchestrator's summary table)
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| `pipeline/orchestrate.py` → `pipeline_memory.writer` → PostgREST (`poeyztlmsawfoqlanucc`, schema `pipeline_memory`) | Shadow writes of run/sheet/row/group state with the service-role key; OFF by default, fail-open | Smartsheet row snapshots (WR, CU, quantities, raw observed personnel columns), run counters |
| PostgREST exposure of `pipeline_memory` → portal clients (`anon`, `authenticated`) | The schema is exposed to the Data API so the pipeline can write; portal users must not be able to read it | internal pipeline state (must be unreachable) |
| `pipeline/upload.py::_upload_one` → attachment side channel | Observational capture of the attachment id after a successful `attach_file_to_row` | attachment id/name per group |
| `scripts/mem04_*.py` → Smartsheet API | Read-only probes against a disposable sandbox rig; refuse production sheet ids | synthetic sandbox cells only |
| `pg_cron` (table owner `postgres`) → `pipeline_memory.row_event` | Daily bounded retention DELETE (5,000 rows/invocation, 24-month floor) | historical row events older than 24 months |
| Operator (Juan) → Supabase SQL Editor / dashboard | Manual DDL apply, schema exposure, cache reload, GRANTs | DDL from the versioned in-repo mirror `pipeline_memory/schema.sql` |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-10-01 | Information Disclosure | writer / orchestrator / flush / passive-compare log lines + Sentry breadcrumbs | high | mitigate | counts-and-ids-only logging (`pipeline_memory/writer.py:739-743`, `pipeline/orchestrate.py:451-458, 530-535, 2887-2890`); `assertLogs` PII-discipline tests (`tests/test_pipeline_memory_shadow.py:928, 1074`) | closed |
| T-10-02 | Elevation of Privilege | `pipeline_memory` schema once PostgREST-exposed | critical | mitigate | RLS on all 5 tables + `service_role_all` policies + REVOKE ALL from `anon`/`authenticated` incl. default privileges (`pipeline_memory/schema.sql`); live-verified 2026-08-25: `anon`/`authenticated` have no USAGE and no SELECT on any table; GRANT-gap fix `2df3b25` is service_role-only, DELETE withheld | closed |
| T-10-03 | Tampering | `upsert_rows_bulk(jsonb)` RPC payload | medium | mitigate | typed `jsonb_to_recordset` column list, no dynamic SQL, `SET search_path = ''` (`schema.sql:280-299`); explicit field map in `writer._row_to_payload` (`writer.py:614-635`) | closed |
| T-10-04 | Denial of Service (self-inflicted) | per-sheet memory write loop vs `TIME_BUDGET_MINUTES` | high | mitigate | pre-flight guard (`orchestrate.py:437-469`) + per-iteration elapsed check (`orchestrate.py:517-539`) + **per-RPC timeout now wired**: `pipeline_memory/client.py::_rpc_timeout_sec` / `_client_options` pass `ClientOptions(postgrest_client_timeout=RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC, default 45)` into `create_client` (commit `b48efd7`; `RpcTimeoutWiringTests`, 5 tests; haiku-verifier PASS 6/6) | closed |
| T-10-05 | Denial of Service (cross-feature) | shared PostgREST kill switch | high | mitigate | `pipeline_memory/client.py` imports nothing from `billing_audit` (grep: zero cross-refs); behavioural test `test_pgrst106_does_not_disable_billing_audit_client` (`test_pipeline_memory_shadow.py:290`) | closed |
| T-10-06 | Repudiation | `row_state.foreman_observed` / `helper_observed` / `vac_crew_observed` | high | mitigate | raw mapped columns only, never `__effective_user` (`writer.py:625-632`; `orchestrate.py:890` passes the raw fetch); regression tests `:624, :643` | closed |
| T-10-07 | Tampering | `pg_cron` retention DELETE on `row_event` | medium | mitigate | `purge_row_event_slice` bounded `ctid IN (... LIMIT 5000)`, 24-month floor (`schema.sql:570-590`), daily `cron.schedule` (`:597-601`); operator reviewed the retention block at the 10-06 checkpoint (`10-06-SUMMARY.md:109`) | closed |
| T-10-08 | Spoofing | reuse of `SUPABASE_SERVICE_ROLE_KEY` | medium | accept | see Accepted Risks Log AR-10-01 | closed (accepted) |
| T-10-09 | Tampering | `pipeline/fetch.py` additive edit vs the group content hash | high | mitigate | additive `__row_modified_at` capture only (`fetch.py:373, 376`); `test_calculate_data_hash_is_neutral_to_row_modified_at` (`test_pipeline_memory_shadow.py:400`) | closed |
| T-10-10 | Tampering | `_upload_one` side-channel capture inside delete-then-upload | high | mitigate | return-value read + one lock-guarded dict write after a successful `attach_file_to_row`, own swallow-all try/except (`orchestrate.py:2676-2690`); `pipeline/upload.py` untouched all phase | closed |
| T-10-11 | Denial of Service (self-inflicted) | third flush in the post-upload block | high | mitigate | group_state flush strictly after both production flushes (`orchestrate.py:2847-2894` vs `:2786`, `:2804`); source-order + try/except asserted by `test_flush_positioned_after_both_existing_flushes_and_writer_call_guarded` (`:1783`) | closed |
| T-10-12 | Tampering | concurrent side-channel writes from ≤ 8 upload workers | medium | mitigate | `threading.Lock` (`orchestrate.py:1563-1564`), unique key `(group_key, variant, file_identifier, target_sheet_id)` (`:2680-2688`) | closed |
| T-10-13 | Tampering | MEM-04 probe / hand edit against a production sheet | high | mitigate | startup guard refuses `TARGET_SHEET_ID` / `SUBCONTRACTOR_PPP_SHEET_ID` (`scripts/mem04_experiment.py:116-154`); AST `READ_ONLY_OK` scan; rig built in the `Sandbox` workspace with `DISPOSABLE TEST RIG — MEM-04` names | closed |
| T-10-14 | Information Disclosure | committed MEM-04 cassettes | medium | mitigate | synthetic sandbox data only; auditor + orchestrator scans: zero production sheet ids, zero WR-number patterns, zero token-like keys (`tests/test_mem04_formula_change.py:186-188`) | closed |
| T-10-15 | Repudiation | MEM-04 verdict beyond evidence | high | mitigate | `derive_verdict` → `undetermined` on any missing scenario/observation (`mem04_experiment.py:426-459`); dated ledger entry `[2026-08-25 12:50]` with evidence items and honest edit-method disclosure | closed |
| T-10-16 | Elevation of Privilege | passive script's service-role read of `pipeline_memory` | medium | accept | see Accepted Risks Log AR-10-02 | closed (accepted) |
| T-10-17 | Tampering | Living Ledger append rewriting history | medium | mitigate | commits `26cb11d`, `1dc5aa3` are insertion-only (0 deletions) | closed |
| T-10-18 | Tampering | `SKIP_UPLOAD` dry runs poisoning production change-detection state | high | mitigate | `hash_history.json` SHA-256 byte-identical across all four real runs (`10-06-SUMMARY.md:112`); the current dirty copy is the pre-existing local prune-marker diff (last real commit `14acf05`, pre-Phase 10) | closed |
| T-10-19 | Repudiation | neutrality declared on a vacuous comparison | high | mitigate | empty control/shadow set → explicit FAIL (`scripts/compare_control_run.py:228-247`); tests `:291, :326, :424` | closed |
| T-10-20 | Denial of Service | write path turned on in production without evidence | high | mitigate | `RUN_MEMORY_WRITE_ENABLED` absent from `.github/workflows/weekly-excel-generation.yml`; `git diff --exit-code -- .github/workflows/` clean; last workflow commit `724171b` predates Phase 10 | closed |
| T-10-SC | Tampering (supply chain) | `requirements.txt` | high | mitigate | `git log c409c32..HEAD -- requirements.txt` empty; `git diff --exit-code -- requirements.txt` exit 0 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-01 | T-10-08 | `pipeline_memory` reuses the same `SUPABASE_SERVICE_ROLE_KEY`, project and trust boundary as the already-shipped `billing_audit` writer; a separate key would add rotation surface without a new boundary (`10-01-PLAN.md:676`) | Juan (plan-time disposition, 10-01 CONTEXT/PLAN) | 2026-08-24 |
| AR-10-02 | T-10-16 | `scripts/mem04_passive_compare.py` reads `pipeline_memory` with the same secret, boundary and operator as the existing backfill scripts; read-only, counts-only output (`10-04-PLAN.md:389`) | Juan (plan-time disposition, 10-04 PLAN) | 2026-08-24 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-25 | 21 | 20 | 1 (T-10-04: per-RPC timeout declared in the plan's mitigation but never wired; residual = postgrest-py 120 s default) | gsd-security-auditor (Sonnet), ASVS L1, block_on high |
| 2026-08-25 | 21 | 21 | 0 — T-10-04 closed same session by `b48efd7` (`ClientOptions(postgrest_client_timeout=…)` wiring + 5 tests; suite 1514 passed, 6 gates green, haiku-verifier PASS) | orchestrator (Fable) re-verification |

Non-blocking observations recorded by the auditor: two harmless diagnostic `run_ledger` rows (`diag-test-mode-omit`, `diag-test-mode-fix`) remain in production from 10-06 root-cause work — `service_role` intentionally lacks DELETE, so they can only be removed by the operator; already disclosed in `10-06-SUMMARY.md:180`. No SUMMARY carries a `## Threat Flags` heading; deviations sections were reviewed directly and no undisclosed attack surface was found.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-25
