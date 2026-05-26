# Phase 2: Attribution Bulk-Prefetch + Historical Claimer Remediation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 02-attribution-bulk-prefetch-historical-claimer-remediation
**Areas discussed:** Bulk-loader design, Week-scope env-var, Remediation mechanism, E re-activation sequencing

---

## Bulk-loader design

### How should the bulk attribution_snapshot fetch be done?

| Option | Description | Selected |
|--------|-------------|----------|
| New bulk RPC | `lookup_attribution_bulk(p_wr_weeks jsonb)` in schema.sql + writer.py; server-side `#NO MATCH`→NULL normalization; fail-safe; operator deploys DDL | ✓ |
| Direct table SELECT | PostgREST `.in_()` filters on `attribution_snapshot`; needs table SELECT exposure + Python-side normalization (second source of truth) | |
| You decide | Planner picks; researcher confirms exposure | |

### What should the bulk query load?

| Option | Description | Selected |
|--------|-------------|----------|
| Exact run (wr, week) set | Load only the pairs this run discovered/grouped; cannot miss a generated group; O(distinct bulk queries) | ✓ |
| Bounded recent superset | `week_ending >= cutoff`; simpler shape but reintroduces a recency window (the bug class) | |
| You decide | Planner picks on payload vs query simplicity | |

### How should resolve_claimer consume the prefetched map?

| Option | Description | Selected |
|--------|-------------|----------|
| Map-aware, keep contract | `prefetch_attribution` builder + resolve_claimer reads preloaded map; preserves Foundation A decision table + ROLE_BY_VARIANT | ✓ |
| Sites read map directly | 4 pre-pass sites do map.get + inline decision; duplicates decision logic (drift risk) | |
| You decide | Minimum-diff, planner picks | |

**User's choice:** New bulk RPC + exact run (wr,week) set + map-aware resolver keeping the Foundation A contract.
**Notes:** Drove the derived bulk-failure-semantics decision (CONTEXT D-04): a total bulk-load failure marks affected keys `fetch_failure` and lets each variant apply its existing policy (D=use-current, B/C=HOLD) — no new HOLD-all semantics.

---

## Week-scope env-var

### What happens to ATTRIBUTION_RESOLUTION_WEEKS and the 4 _attribution_week_in_scope gates?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop entirely | Remove var, 4 gates, helpers, banner line, workflow pin, scope test file; exact-set load makes recency-gating obsolete and removes the incident footgun | ✓ |
| Keep, decoupled | Remove the 4 key-formation gates but keep var as a default-OFF payload-size escape hatch; risk: any non-zero value reintroduces the bug | |
| You decide | Planner picks; both remove the key-formation gating | |

**User's choice:** Drop entirely.
**Notes:** The recency window was the precise mechanism that gated group-KEY formation and caused the corruption; a vestigial knob on this code path is a re-incident risk.

---

## Remediation mechanism

### What mechanism should remediate the ~26-week window of corrupted files?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated remediation mode | Env-gated one-shot; own logging/counters/dry-run; isolated from cron path | ✓ |
| Reuse REGEN_WEEKS + cleanup | Regenerate via existing knobs, let generic cleanup delete orphans (broader blast radius, KEEP_HISTORICAL_WEEKS dependency) | |
| You decide | Planner picks on minimum-diff vs observability | |

### How should the orphaned garbage attachments be identified for deletion?

| Option | Description | Selected |
|--------|-------------|----------|
| Name-pattern sweep | Delete only `*_NO_MATCH*` / `*_Unknown_Foreman*` within the window (TARGET+PPP); narrowest blast radius | ✓ |
| Identity-orphan cleanup | Delete anything not in this run's valid identity set for the window; wider net | |
| You decide | Planner picks; both respect the live-identity exemption | |

### What safety/observability gate should the remediation run behind?

| Option | Description | Selected |
|--------|-------------|----------|
| Dry-run first + env window | Env-configurable window (default ~26wk); report-only first, then execute; default-OFF flag | ✓ |
| Hardcoded 26, direct execute | Fixed window, executes directly; no preview of the destructive op | |
| You decide | Planner picks; stays default-OFF on cron | |

**User's choice:** Dedicated remediation mode + name-pattern sweep + dry-run-first with an env-configurable window.
**Notes:** Highest-blast-radius area (deletes production Smartsheet attachments) — observability and reversibility prioritized.

---

## E re-activation sequencing

### In what order should the fix, E re-activation, and remediation happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Fix → validate → E on → remediate | Flip AUTHORITATIVE=1 after validation (its regen wave produces correct clean names), then sweep garbage; no token→clean double-churn | ✓ |
| Fix → validate → remediate → E on | Remediate while AUTH=0 (token-named), then E flip regenerates the window again (extra churn) | |
| You decide | Planner sequences; fix+validation is the hard prerequisite | |

### What concretely gates flipping AUTHORITATIVE=1?

| Option | Description | Selected |
|--------|-------------|----------|
| Acceptance-criteria run | Real run shows zero garbage names, O(bulk) HTTP not ~137k, ≤165min, pytest green | ✓ |
| Spot-check + tests | pytest green + manual spot-check of a few weeks; lighter, less evidence | |
| You decide | Planner defines the evidence-based checklist | |

### How is the AUTHORITATIVE=1 flip itself delivered?

| Option | Description | Selected |
|--------|-------------|----------|
| Operator follow-up, gated | Ship fix + remediation + runbook; the one-line flip is a separate explicit operator action after a green run; NOT in the fix PR | ✓ |
| Committed in-phase | Executor commits AUTHORITATIVE=1; goes live next cron; no human gate | |
| You decide | Planner decides; validation gate satisfied either way | |

**User's choice:** Fix → validate → E on → remediate; acceptance-criteria validation gate; operator-applied, gated flip.
**Notes:** Directly avoids repeating the premature-flip incident (`67539ec` → corruption → revert PR #234) by keeping a human gate between validation and going-live.

---

## Claude's Discretion

- Bulk-RPC payload chunking strategy if the run's (wr, week) set is large.
- Resolver wiring shape — `prefetched_map` param vs thin sibling resolver.
- Disposition of `tests/test_attribution_resolution_scope.py` — delete vs repurpose.
- Where in the run flow the prefetch map is built.
- Final names for the remediation flag + window env var.
- Living Ledger entry timestamp (executor sets at commit).

## Deferred Ideas

- Missing-`Helper Dept #` hard-gate relaxation (126 rows in run 26200546881) — separate Smartsheet-data/gate decision; out of scope, preserved.
- Deep-history (>~6 months) remediation — self-heals on natural edit; out of scope.
- Railway → Render migration + Artifact Explorer redesign — v1.1 milestone.
