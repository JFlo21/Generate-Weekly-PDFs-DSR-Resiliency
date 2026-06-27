---
name: investigate-price-anomaly
description: Use when a billing audit flags a price delta or risk level (LOW/MEDIUM/HIGH), or a Work Request's pricing looks wrong. Covers audit_billing_changes.py, diagnose_pricing_issues.py, optional cell-history enrichment, and the billing_audit risk model. Read-only diagnosis — never alters pricing logic.
---

# Investigate a price anomaly

Read-only triage for billing/pricing anomalies. Do **not** change pricing or billing
logic to "fix" a number — surface the root cause and the correct upstream data.

## Tools
```bash
python audit_billing_changes.py        # price anomaly / risk-level detection (LOW/MEDIUM/HIGH + deltas)
python diagnose_pricing_issues.py      # pricing-specific diagnostics
```
- `audit_billing_changes.py` is imported by the main engine and assigns risk levels
  with delta tracking; it can optionally enrich from Smartsheet cell history.
- `SKIP_CELL_HISTORY=true` skips the (slower) cell-history enrichment when you only
  need the delta/risk pass.

## Method
1. Reproduce read-only with `SKIP_UPLOAD=true WR_FILTER=<WR>` to regenerate the
   affected file without touching Smartsheet.
2. Run the audit; read the LOW/MEDIUM/HIGH classification and the delta vs. prior.
3. Distinguish a **data** problem (wrong rate/unit upstream in Smartsheet) from a
   **logic** path (subcontractor vs original-contract pricing, VAC-crew attribution).
   Check `memory-bank/living-ledger.md` for the established rule (rate recalc, claim
   attribution, WR sanitization) before concluding.
4. Report root cause + the upstream cell/source to correct. Recommend; do not patch.

## Related
- Agent `billing-audit-analyst` (read-only) for deeper audit-row analysis.
- Domain rules: `.github/prompts/data-processing-business-logic.md`.
- Supabase `billing_audit` integration: see `memory-bank/living-ledger.md`.
