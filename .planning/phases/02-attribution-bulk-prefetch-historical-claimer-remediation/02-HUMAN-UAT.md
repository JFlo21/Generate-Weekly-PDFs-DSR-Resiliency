---
status: partial
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
source: [02-VERIFICATION.md]
started: 2026-05-26T21:52:49Z
updated: 2026-05-26T21:52:49Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Supabase RPC deployment + production run validation
expected: After applying `billing_audit/schema.sql` to the live Supabase
project and reloading the PostgREST schema cache
(`NOTIFY pgrst, 'reload schema';`), the next scheduled/dispatched weekly run
produces ZERO `_User__NO_MATCH` / `_User_Unknown_Foreman` files for WRs that
have a frozen claimer in `billing_audit.attribution_snapshot`, and the
attribution HTTP call count is O(chunks) (a few `lookup_attribution_bulk`
POSTs), NOT the ~137k per-row `lookup_attribution` calls from the incident.
Total runtime stays under `TIME_BUDGET_MINUTES` (165) / `timeout-minutes`
(180). With the RPC absent, the run must still complete (degrades to per-row
`lookup_attribution` via the default-ON `ATTRIBUTION_BULK_PREFETCH_FALLBACK`).
result: [pending]

### 2. Remediation dry-run via advanced_options
expected: Trigger `workflow_dispatch` with
`advanced_options: remediate_claimers:1,remediation_dry_run:1,remediation_window_weeks:26`.
The run enters the isolated `run_claimer_remediation` dispatch and returns
BEFORE any Excel generation. The `[DRY-RUN]` summary lists only
`_NO_MATCH`-bearing attachments as deletion candidates (the legitimate
`_Unknown_Foreman` sentinel is NOT swept in the isolated `valid_wr_weeks=None`
path). No attachments are actually deleted in dry-run mode.
result: [pending]

### 3. Sub-project E re-activation (D-11 human gate)
expected: ONLY after items 1 and 2 pass, flip
`SUPABASE_HASH_STORE_AUTHORITATIVE: '1'` in a SEPARATE PR per the
`website/docs/runbook/operations.md` procedure. The first authoritative run
regenerates each group once on `no_row`, produces clean (token-less)
filenames partitioned by the correct frozen claimer, and the durable
`billing_audit.group_content_hash` store populates. This is the deliberate
human-gated activation that the premature `67539ec` flip skipped — it must
NOT be auto-committed.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
