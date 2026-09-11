# Phase 13: Audit Memory - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-11
**Phase:** 13-audit-memory
**Areas discussed:** Finding identity + acknowledge (§8 #6), wr_week_ownership placement (D-12-A), Audit surface for open+resurfaced, Which checks get memory
**Mode:** advisor (USER-PROFILE.md present; vendor philosophy `conservative` → `full_maturity` tier; non-technical-owner = false). Three `gsd-advisor-researcher` (Sonnet) agents produced the comparison tables; the check-scope area was folded into the finding-identity agent because the key depends on it.

---

## Finding key (§8 #6a)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-check natural key | check_id + emitted identity fields + week_ending from the row; row_id in evidence only | ✓ |
| Spec draft uniform key | sha(check_id\|wr\|week\|cu\|pole); needs check-emission refactor; placeholders collapse findings | |
| Key includes evidence values | Changed number = new finding; breaks resurfaced semantics | |
| Key includes Smartsheet row_id (table only) | Finest grain but row ids churn under regeneration | |

**User's choice:** Per-check natural key (Recommended)
**Notes:** Research flagged that no check emits `week` or `pole` today; SARIF/CodeQL practice (hash identity, not content) cited.

---

## Check scope (§8 #6b)

| Option | Description | Selected |
|--------|-------------|----------|
| Three WR-scoped checks | price_variance_anomaly, data_consistency_issue, rate_sanity_mismatch; recent_discussion stays run-only | ✓ |
| All four incl. recent_discussion | Needs a bespoke fixed rule for sheet-level findings | |
| rate_sanity_mismatch only for v1 | Smallest shadow surface; AUD-01 partially delivered | |

**User's choice:** Three WR-scoped checks (Recommended)
**Notes:** Severity stays the check's own value; the run-level risk ladder is untouched.

---

## Acknowledge / suppress authority (§8 #6c)

| Option | Description | Selected |
|--------|-------------|----------|
| Owner-only via SQL, v1 | Service-role SQL; audit_finding_event records actor/time; no RLS/UI/workflow change | ✓ |
| SQL now + workflow_dispatch ack input | advanced_options key `ack_finding_keys`; protected Actions change | |
| portal-v2 page with RLS role | New page + RLS policy + role model | |
| Smartsheet audit-sheet checkbox (table only) | New sheet polled by the run; second source of truth | |

**User's choice:** Owner-only via SQL, v1 (Recommended)

---

## wr_week_ownership placement (D-12-A)

| Option | Description | Selected |
|--------|-------------|----------|
| Drop for good | OWN-01 satisfied by ladder + provenance; docs-only closure (D-13-A) | ✓ |
| Additive read-only view in Phase 13 | View over attribution_snapshot; only if a consumer is named | |
| Defer again with a named trigger | Keep reserved name with a concrete trigger | |
| Authoritative write-path table (table only) | Protected billing change; own phase | |

**User's choice:** Drop for good (Recommended)
**Notes:** Research confirmed no production consumer references `wr_week_ownership`.

---

## Audit surface (AUD-03)

| Option | Description | Selected |
|--------|-------------|----------|
| SQL views now, UI follow-up | open_findings + finding_history_by_wr; visual surface backlogged | ✓ |
| SQL views + generated audit workbook | openpyxl workbook each run in generated_docs/ | |
| SQL views + read-only portal-v2 page | Needs RLS policy for authenticated role | |
| SQL views + audit-sheet summary row | Implement _log_to_audit_sheet (Smartsheet write) | |

**User's choice:** SQL views now, UI follow-up (Recommended)

---

## Todos cross-referenced

All three keyword matches folded: run-memory review follow-ups (only WR-04 + IN-01 still open), snapshot_store int arg-type, Gate-4 mypy hardening (low priority).

## Claude's Discretion

- price_variance_anomaly week mapping when the pool spans weeks (D-CD-01)
- data_consistency_issue identity via sorted issue codes (D-CD-02)
- Server-side RPC vs client-side transitions (D-CD-03)
- `suppressed` = terminal-hidden (D-CD-04); no retention purge in Phase 13 (D-CD-05)

## Deferred Ideas

AUD-03 visual surface (workbook / portal page / audit-sheet row); workflow_dispatch acknowledge input; portal acknowledge page; recent_discussion in memory; wr_week_ownership derived view; pipeline_memory/client.py breaker lock (separate PR).
