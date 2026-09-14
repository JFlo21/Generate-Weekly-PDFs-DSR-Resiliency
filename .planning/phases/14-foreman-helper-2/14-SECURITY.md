---
phase: "14"
slug: "foreman-helper-2"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: "2026-09-13"
---

# Phase 14 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register source: the `<threat_model>` blocks of all fourteen PLAN files (14-01 .. 14-14). Plans
> 14-01 .. 14-11 carry STRIDE tables with explicit IDs; 14-12 carries four bulleted, numbered
> threats; 14-13 and 14-14 carry unnumbered bulleted threats, assigned IDs `T-14-13-0n` /
> `T-14-14-0n` here. Severities missing from the bulleted plans were assigned by the audit and are
> marked `(assigned)`. SUMMARY threat flags: 14-02 reports none; 14-09, 14-11, 14-12 record
> owner-delegated production applies against their own T-*-05 / T-*-03 prohibitions (see register).
> Verification depth: ASVS L1 grep-level — mitigation located in the implementation, pinned test
> named, or live read-back cited from the plan SUMMARY / 14-DECISIONS.md.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Smartsheet source sheets → `pipeline/fetch.py` Helper #2 detection | Raw "Foreman Helping 2" / dept / job cells become a billable claimant identity | Personnel names (PII), formula-error tokens, blanks |
| Helper #2 identity → group key / filename / Excel header (`pipeline/grouping.py`, `pipeline/excel.py`) | A raw cell value becomes a filesystem name and a customer-facing workbook header | Sanitized claimant identifier |
| `pipeline_memory.row_state` + `upsert_rows_bulk` RPC (owner-applied DDL) | Additive Helper #2 columns join the content hash and the frozen-row store | Row-level billing facts incl. `helper2_observed` (PII) |
| `billing_audit.attribution_snapshot` freeze / fill RPCs (owner-applied DDL) | Per-role frozen attribution; a Helper #2 write must never clear another role | Frozen claimant per role; provenance jsonb |
| Discovery skip-index (`pipeline/discovery.py` ↔ `pipeline_memory.sheet_registry`) | `helper2-v1` mapping marker gates cache admission; a wrong admission silently disables detection | Column mappings, sheet versions, marker |
| Cleanup / orphan gate (`pipeline/cleanup.py`) → Smartsheet attachments | Deletion of superseded workbooks; a Helper #2 workbook must never be treated as legacy | Attachment identity, variant tokens |
| Log / Sentry plane (`pipeline/observability.py`) | New Helper #2 log lines and breadcrumbs | Reason codes only; PII markers redacted |
| GitHub Actions cron (`weekly-excel-generation.yml`) | `HELPER2_ENABLED` repo variable; default `'0'` | Rollout flag |
| Agent session → live Supabase / Smartsheet | All production applies and probes are owner-run or owner-delegated at `blocking-human` gates | DDL, read-only probes |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation (evidence) | Status |
|-----------|----------|-----------|----------|-------------|------------------------|--------|
| T-14-01-01 | Tampering | `pipeline/excel.py` variant_suffix, `pipeline/grouping.py` helper2 key | high | mitigate | `_RE_SANITIZE_HELPER_NAME.sub('_', …)[:50]` applied to every helper2 identifier (`pipeline/attribution.py:156,185,225`); consumers read only `__helper2_*` (`pipeline/excel.py:334-385`); pinned by `tests/test_foreman_helper_2.py` | closed |
| T-14-01-02 | Spoofing | `pipeline/fetch.py` Helper #2 detection | high | mitigate | `normalize_helper_value` on name, dept, job (`pipeline/fetch.py:408,421,424`) rejects blank + all `FORMULA_ERROR_VALUES` (D-14-05) | closed |
| T-14-01-03 | Information Disclosure | new Helper #2 log lines | medium | mitigate | `_PII_LOG_MARKERS` registry incl. `"Foreman Helping?"` family (`pipeline/observability.py:357-373`) enforced at `:597,:648`; Helper #2 lines log reason codes (`helper2_capability_unavailable`, `pipeline/fetch.py:646`) | closed |
| T-14-01-04 | Denial of Service | `pipeline/discovery.py` synonyms | low | accept | Six additive dict entries; no network calls, no `PARALLEL_WORKERS` change (AR-14-01) | closed |
| T-14-01-05 | Repudiation | helper2 group identity | medium | mitigate | Round-trip test: `build_group_identity(output_filename)` resolves back to the claimant (`tests/test_foreman_helper_2.py:198-200`) | closed |
| T-14-01-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed; 14-RESEARCH.md § Package Legitimacy Audit = not applicable (AR-14-02) | closed |
| T-14-02-01 | Information Disclosure | 14-DECISIONS.md live-probe answers | medium | mitigate | LIVE-COLUMN-PROBE records column titles/ids/counts only (`14-DECISIONS.md:76,102-109`); no row values, names, or tokens in the file | closed |
| T-14-02-02 | Tampering | live Smartsheet during the probe | high | mitigate | Read-only attestation (`14-DECISIONS.md:4,11,76`); 14-02-SUMMARY Threat Flags: "zero writes were performed" | closed |
| T-14-02-03 | Repudiation | pending-resolution verdicts | low | mitigate | 14-02-SUMMARY: "every verdict cites file plus line range" | closed |
| T-14-02-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-03-01 | Spoofing | `freeze_row` Helper #2 claimant | high | mitigate | `_null_if_named_sentinel(row.get('__helper2_foreman'))` (`pipeline/attribution.py:886-887`, `pipeline/grouping.py:303`); `tests/test_billing_audit_shadow.py:761` asserts `p_helper2` is None for a sentinel | closed |
| T-14-03-02 | Repudiation | `freeze_row` all-sentinel short-circuit | high | mitigate | `p_helper2` joins the freeze payload AND the all-sentinel gate (`tests/test_billing_audit_shadow.py:624-625`) | closed |
| T-14-03-03 | Tampering | Helper #2 freeze overwriting another role | high | mitigate | Per-role named columns in `billing_audit/helper2_attribution.sql`; tests assert the other role params byte-identical (`tests/test_billing_audit_shadow.py:683-795`) | closed |
| T-14-03-04 | Denial of Service | pre-migration RPC parameter rejection | medium | mitigate | Degraded path drops `p_helper2` once per process (`tests/test_billing_audit_shadow.py:875`); `helper2_attribution_degraded` counter (`tests/golden/run_summary_baseline.json:27`) — no per-row error storm | closed |
| T-14-03-05 | Information Disclosure | RPC error text in logs | medium | mitigate | Routed through `_redact_exception_message` / `_PII_LOG_MARKERS` (`pipeline/observability.py:597,648`) | closed |
| T-14-03-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-04-01 | Tampering | `pipeline_memory.row_state` DDL | high | mitigate | `ADD COLUMN IF NOT EXISTS helper2_observed TEXT` etc., additive nullable (`pipeline_memory/helper2_columns_migration.sql:33-36`, `schema.sql:152`); owner-applied D-14-13-DDL-APPLIED (14-12-SUMMARY) | closed |
| T-14-04-02 | Repudiation | `content_hash` field-set change | medium | mitigate | One-time churn quantified from live read-only figures before apply (`14-DECISIONS.md:109`); HASH_FIELDS append-only (`pipeline_memory/schema.sql:321`) | closed |
| T-14-04-03 | Information Disclosure | `helper2_observed` raw personnel value | medium | accept | Same data class and same service-role RLS policy as existing `helper_observed`; no new surface (AR-14-03) | closed |
| T-14-04-04 | Denial of Service | first-run `row_event` burst | medium | mitigate | Bounded one event per row (`pipeline_memory/writer.py` row_event path); parity finding from 14-02 confirmed no new first-run suppression guard needed (14-02-SUMMARY § Next Phase Readiness) | closed |
| T-14-04-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-05-01 | Denial of Service | cleanup deletion of live Helper #2 attachments | high | mitigate | `test_helper2_attachment_survives_cleanup_with_flag_off` (`tests/test_sentinel_superseded_cleanup.py:404`); legacy-migration gates untouched | closed |
| T-14-05-02 | Repudiation | orphan-supersede gate blind to Helper #2 | medium | mitigate | `_HELPER_VARIANTS_FOR_ORPHAN_GATE` frozenset includes `helper2`, `aep_billable_helper2`, `reduced_sub_helper2` (`pipeline/cleanup.py:525-527`) | closed |
| T-14-05-03 | Tampering | `normalize_variant` misfiling a Helper #2 artifact | medium | mitigate | Parallel sibling family with precedence-ordered tokens (`pipeline/cleanup.py:520-527`); cross-match tests in `tests/test_helper2_family_parity.py` | closed |
| T-14-05-04 | Information Disclosure | portal label rendering a person's name | low | accept | Labels keyed on variant token; filename field unchanged (AR-14-04) | closed |
| T-14-05-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed; portal build uses existing lockfile (AR-14-02) | closed |
| T-14-06-01 | Tampering | `pipeline/grouping.py` Helper #2 key emission | critical | mitigate | Subcontractor shadow-key guard (`pipeline/grouping.py:1564-1575`, `_SUBCONTRACTOR_SCOPE_VARIANTS` `pipeline/attribution.py:119`); pinned by `tests/test_subcontractor_helper_shadow_rescue.py` and `tests/test_helper2_family_parity.py` (two shadow keys, zero plain) | closed |
| T-14-06-02 | Spoofing | `pipeline/excel.py` header dispatch | high | mitigate | Dedicated sibling `elif variant == 'aep_billable_helper2' / 'reduced_sub_helper2' / 'helper2'` branches (`pipeline/excel.py:326,347,381,611,618`) | closed |
| T-14-06-03 | Repudiation | `pipeline/upload.py` second-leg routing | high | mitigate | `reduced_sub_helper2` joins the routing tuple (`pipeline/upload.py:344-349`) | closed |
| T-14-06-04 | Tampering | aggregated content hash for multi-foreman buckets | medium | mitigate | Sibling sub-bucketing by Helper #2 identity (`pipeline/change_detection.py:563`) | closed |
| T-14-06-05 | Information Disclosure | new grouping and upload log lines | medium | mitigate | Reason-code style; `_PII_LOG_MARKERS` redaction (`pipeline/observability.py:597,648`) | closed |
| T-14-06-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-07-01 | Tampering | discovery skip-index admission | high | mitigate | `MAPPING_SCHEMA_MARKER = "helper2-v1"` is the additive sixth condition that can only reject (`pipeline/discovery.py:72,256,334`) | closed |
| T-14-07-02 | Repudiation | a not-yet-migrated marker column | high | mitigate | Degrade fails toward full validation, "never a silent cache admission" (`pipeline_memory/reader.py:151-208`) | closed |
| T-14-07-03 | Denial of Service | one-time full validation for every sheet | medium | mitigate | Cost quantified from live figures before apply (`14-DECISIONS.md:102-109`, D-14-10-APPLIED) | closed |
| T-14-07-04 | Spoofing | a read failure reported as a Helper #2 absence | high | mitigate | Distinct reason codes: `helper2_capability_unavailable` (`pipeline/fetch.py:646`) vs no-qualifying (`:1188`) vs failed-validation path in `pipeline/discovery.py` (untouched) | closed |
| T-14-07-05 | Information Disclosure | new per-sheet reason log lines | medium | mitigate | Reason code + sheet name only (`pipeline/fetch.py:646`); PII marker registry | closed |
| T-14-07-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-08-01 | Repudiation | conflicted-row handling | critical | mitigate | `_record_helper2_wins_conflict` cites the owner-decided O-14-A RESOLVED record in code (`pipeline/grouping.py:103-117`) | closed |
| T-14-08-02 | Tampering | double emission of one unit | critical | mitigate | "Call exactly once per conflicted row, at the single point per leg" (`pipeline/grouping.py:114`); conflict tests in `tests/test_foreman_helper_2.py` | closed |
| T-14-08-03 | Denial of Service | one bad row aborting the run | high | mitigate | No exception path; counter-only (`_HELPER2_CONFLICT_COUNT`, `pipeline/grouping.py:94-100`); other groups still generate per `tests/test_foreman_helper_2.py` | closed |
| T-14-08-04 | Information Disclosure | conflict log lines naming two people | medium | mitigate | Reason code `helper2_conflict_hold` and identifiers only (`pipeline/grouping.py:117`) | closed |
| T-14-08-05 | Repudiation | run summary key drift | medium | mitigate | Counters pre-seeded (`pipeline/orchestrate.py:637`) and golden baseline updated (`tests/golden/run_summary_baseline.json:21-31`) | closed |
| T-14-08-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-09-01 | Tampering | lookup function replacement | critical | mitigate | Drop-then-create for both functions in `billing_audit/helper2_attribution.sql`; contract test `tests/test_helper2_attribution_sql_contract.py` (19 tests); applied D-14-07-APPLIED `3d6263a` (14-09-SUMMARY:134) | closed |
| T-14-09-02 | Repudiation | silent non-deploy | critical | mitigate | D-14-07-VERIFIED production read-back, four checks, co-signed by owner (14-09-SUMMARY:135) | closed |
| T-14-09-03 | Tampering | a Helper #2 freeze clearing another role | critical | mitigate | Per-role write in SQL; read-back observed the other three columns unchanged (14-09-SUMMARY:135); `tests/test_billing_audit_shadow.py:683-795` | closed |
| T-14-09-04 | Denial of Service | a scheduled run during the drop window | high | mitigate | Quiet window chosen at the Task 2 owner checkpoint (14-09-SUMMARY:134) | closed |
| T-14-09-05 | Elevation of Privilege | applying production SQL from an agent session | high | mitigate | Both checkpoints `gate="blocking-human"`; the apply was an explicit, recorded owner delegation (Juan, 14-09-SUMMARY § deviations), not an auto-mode resolution | closed |
| T-14-09-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-10-01 | Tampering | pilot run side effects | high | mitigate | Pilot fixture-only (`14-DECISIONS.md:86`); Task 3 owner decision "documented-only, no controlled upload" (14-10-SUMMARY:79,128) | closed |
| T-14-10-02 | Denial of Service | enabling the flag on a scheduled run | high | mitigate | `HELPER2_ENABLED` default `'0'` (`pipeline/config.py:49-50`); workflow `vars.HELPER2_ENABLED \|\| '0'` (`.github/workflows/weekly-excel-generation.yml:247`) | closed |
| T-14-10-03 | Repudiation | mislabelled evidence | high | mitigate | Four distinct evidence labels used throughout 14-10-SUMMARY; fixture pass never reported as production | closed |
| T-14-10-04 | Tampering | rollback deleting Helper #2 evidence | high | mitigate | Flag-off + retention, pinned by `tests/test_sentinel_superseded_cleanup.py:404` | closed |
| T-14-10-05 | Elevation of Privilege | editing the CI workflow without approval | medium | mitigate | `git diff --quiet -- .github/workflows/weekly-excel-generation.yml` EXIT 0 during 14-10 (14-10-SUMMARY:135); later wiring landed via owner-merged PR #390 (`661d6d3`, plan 14-12) | closed |
| T-14-10-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed; docs build uses existing lockfile (AR-14-02) | closed |
| T-14-11-01 | Tampering | ON CONFLICT DO UPDATE touching a non-Helper-#2 column | critical | mitigate | SET list parsed and pinned by `tests/test_helper2_attribution_fill_sql_contract.py:80-83`; O-14-C-VERIFIED read-back: only two Helper #2 columns + provenance written (14-11-SUMMARY:125,129) | closed |
| T-14-11-02 | Tampering | a later run overwriting a real Helper #2 | high | mitigate | `is_sentinel_value(s.frozen_helper2)` WHERE gate in `billing_audit/helper2_attribution_fill.sql`; refusal proven in read-back (14-11-SUMMARY) | closed |
| T-14-11-03 | Denial of Service | admission rule re-sending every frozen row | high | mitigate | Admission = valid Helper #2 on row AND key in `_PREFETCHED_HELPER2_MISSING_KEYS` (`pipeline/grouping.py:66-84,202`, `pipeline/attribution.py:852-882`); count logged before loop | closed |
| T-14-11-04 | Repudiation | a fill nobody can trace | medium | mitigate | Provenance `{helper2: {source, run_id}}` in fill SQL; `snapshots_helper2_filled` counter (`tests/golden/run_summary_baseline.json:21`) | closed |
| T-14-11-05 | Elevation of Privilege | applying production SQL without the owner | high | mitigate | Task 3 `blocking-human`; owner-delegated apply recorded (O-14-C-APPLIED, 14-11-SUMMARY) | closed |
| T-14-11-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed (AR-14-02) | closed |
| T-14-12-01 | Tampering (integrity) | hashed field missing from `upsert_rows_bulk` RPC | high (assigned) | mitigate | Lockstep contract test `tests/test_upsert_rows_bulk_helper2_contract.py` (12 tests); HASH_FIELDS ⊆ RPC pinned (`pipeline_memory/schema.sql:317-321`) | closed |
| T-14-12-02 | Denial of Service (availability) | ALTER TABLE lock during a writing run | medium (assigned) | mitigate | Run-window check; DDL applied 2026-09-09 02:22-02:27Z outside cron (D-14-13-VERIFIED, 14-12-SUMMARY:75) | closed |
| T-14-12-03 | Elevation of Privilege | losing `service_role` EXECUTE on the RPC | high (assigned) | mitigate | Signature-preserving `CREATE OR REPLACE`; grants read back (`pipeline_memory/helper2_columns_migration.sql:51,67`; 14-12-SUMMARY:107) | closed |
| T-14-12-04 | Repudiation (rollback) | irreversible DDL | medium (assigned) | mitigate | Pre-state parked verbatim in vault raw; every DDL droppable (14-12-SUMMARY:81) | closed |
| T-14-13-01 | Tampering | marker stamped on an unvalidated or echoed mapping | high (assigned) | mitigate | Marker ⊆ column_mapping-written ∩ fully-validated set (`pipeline/discovery.py:79`); `tests/test_mapping_schema_marker_caller.py` (8 tests), `tests/test_foreman_helper_2.py:544-568` | closed |
| T-14-13-02 | Repudiation | getter reads a stale value from an earlier call | medium (assigned) | mitigate | `_discovery_skip_sids` reset at the top of `discover_source_sheets` (`pipeline/discovery.py:368`; 14-13-SUMMARY:14,93); getter defensive-copy test | closed |
| T-14-14-01 | Tampering | frequent run adopting a wrong mapping | high (assigned) | mitigate | Adoption only after this run's full validation; drift logged + breadcrumbed; `tests/test_frequent_run_mapping_adoption.py:196-240` | closed |
| T-14-14-02 | Spoofing | marker on a mapping lacking Helper #2 keys | medium (assigned) | mitigate | Correct by construction if the live sheet lacks them; a later column addition bumps sheet version and forces re-validation (`pipeline/discovery.py:230-354` version skip index) | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-14-01 | T-14-01-04 | Six additive discovery synonyms; no network calls, no worker-count change, time budget unaffected | Juan Flores (plan 14-01) | 2026-09-13 |
| AR-14-02 | T-14-01-SC .. T-14-11-SC (11 entries) | Phase installs no packages; 14-RESEARCH.md § Package Legitimacy Audit records not-applicable; portal/docs builds use existing lockfiles | Juan Flores (plans 14-01..14-11) | 2026-09-13 |
| AR-14-03 | T-14-04-03 | `helper2_observed` stores the same personnel-data class as `helper_observed` under the same service-role RLS policy; no new exposure surface | Juan Flores (plan 14-04) | 2026-09-13 |
| AR-14-04 | T-14-05-04 | Portal labels keyed on variant token; the name reaches the portal only via the pre-existing filename field | Juan Flores (plan 14-05) | 2026-09-13 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-13 | 70 | 70 (56 mitigated, 14 accepted) | 0 | Claude Fable 5.1 (`/gsd:secure-phase 14`, L1 short-circuit — plan-time register, ASVS 1) |

Severity mix: 7 critical · 27 high · 22 medium · 14 low (all closed).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-13
