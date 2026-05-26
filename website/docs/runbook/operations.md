---
id: operations
title: Operations
sidebar_position: 6
---

# Operations

## Running the generator by hand

```bash
# Local, no uploads to Smartsheet
SKIP_UPLOAD=true python generate_weekly_pdfs.py

# Full production path
python generate_weekly_pdfs.py
```

## Triggering the scheduled workflow on demand

1. Open **Actions → Weekly Excel Generation → Run workflow**.
2. Pick the branch (`master` for production).
3. Set inputs as needed — `test_mode=true` for dry runs,
   `wr_filter=90093002,89954686` for a targeted reprocess.
4. Submit.

## Common knobs

| Input / var | Purpose |
| --- | --- |
| `test_mode` | Skip uploads, shorten retention to 30 days. |
| `force_generation` | Bypass the "no eligible data" short-circuit. |
| `reset_hash_history` | Invalidate `hash_history.json` — regenerates everything. |
| `force_rediscovery` | Ignore `discovery_cache.json` — slow but correct. |
| `wr_filter` / `exclude_wrs` | Narrow the run to specific work requests. |
| `advanced_options` | Composite knob parsed by the workflow into env vars. |

## Interpreting a failed run

1. Open the failed workflow run in the Actions tab.
2. Check the "Run system health check" / "Generate reports" step logs.
3. Download the `Manifest-…` artifact — the JSON summary tells you how
   many WRs and weeks were processed before the failure.
4. If Sentry is configured, open the release matching the run's SHA to
   see exceptions and log breadcrumbs.
5. When the pipeline cache is suspected (stale discovery), re-run with
   `force_rediscovery=true`.

## Restoring from a bad run

- Use `reset_hash_history=true` to regenerate all files.
- If only some WRs are bad, pass `advanced_options=reset_wr_list:WR1;WR2`.
- The `By-WorkRequest-…` artifact from the previous good run can be
  downloaded and re-attached manually via Smartsheet if a rollback is
  required.

---

## Re-activate Sub-project E (clean filenames + durable hash store)

**Owned by:** Python billing pipeline (`generate_weekly_pdfs.py` + GitHub
Actions). No portal or Supabase web-app changes are involved.

Sub-project E ships `SUPABASE_HASH_STORE_AUTHORITATIVE=0` by design —
the flip to `1` is a deliberate, human-gated operator action. This section
documents the ordered procedure you must follow. Skipping the validation
gate in Step 2 can produce garbage-named files over real historical
attachments (see the `46cd05d` revert / PR #234 incident, where a premature
flip with `67539ec` produced 372 `_User__NO_MATCH` / `_User_Unknown_Foreman`
files over correct historical attachments).

### Step 1 — Prerequisite: deploy the `lookup_attribution_bulk` RPC (D-01)

The data team applies the `CREATE OR REPLACE FUNCTION
billing_audit.lookup_attribution_bulk(...)` DDL from `billing_audit/schema.sql`
in the **Supabase SQL Editor**, then reloads the PostgREST schema cache:

```sql
NOTIFY pgrst, 'reload schema';
```

Or use **Project Settings → API → Data API Settings → Reload schema cache**.

Until this is live, `prefetch_attribution` returns `({}, "fetch_failure")` via
the `PGRST106`/`SQLSTATE 42P01` error path and all attribution resolvers fall
back to use-current — the pipeline behaves exactly as before this fix, and no
claimer is corrected. Validation **must run after** this RPC is deployed.

### Step 2 — Validation gate (D-10, `AUTHORITATIVE=0` still set)

Run a real / production-equivalent workflow dispatch with
`SUPABASE_HASH_STORE_AUTHORITATIVE` still at `'0'` in the workflow env.
**Capture evidence for all four criteria before proceeding** — this is a
gate, not a spot-check.

| Evidence item | Expected result | How to verify |
|---|---|---|
| Zero garbage filenames | No generated file named `*_NO_MATCH*` or `*_Unknown_Foreman*` for any WR+week+row that has a frozen claimer in `attribution_snapshot` | Inspect the `By-WorkRequest-…` artifact filenames |
| O(chunks) Supabase HTTP calls | Single-digit or low double-digit `POST /rpc/lookup_attribution_bulk` count (one per 500-pair chunk); **not** the ~137k `POST /rpc/lookup_attribution` baseline | `grep -c 'lookup_attribution' <run-log>` |
| Runtime within budget | Run completes without a premature graceful-stop / "budget exceeded" before generation; total time ≤ `TIME_BUDGET_MINUTES=165` | Actions run duration |
| Tests green | `pytest tests/` passes, including `TestHistoricalClaimerRegression` | CI test step |

If any criterion fails, investigate and fix before proceeding to Step 3.

### Step 3 — Flip `AUTHORITATIVE=1` (D-11, separate gated operator action)

After Step 2 is fully green: set `SUPABASE_HASH_STORE_AUTHORITATIVE: '1'`
in `.github/workflows/weekly-excel-generation.yml` `env:` as a **one-line
change in its own commit and PR**.

```yaml
# .github/workflows/weekly-excel-generation.yml
env:
  SUPABASE_HASH_STORE_AUTHORITATIVE: '1'   # was '0'
```

This flip was **deliberately not bundled** into the Phase 2 fix PR —
the human gate between validation and going-live is the whole point
(lesson: `67539ec` premature flip → `46cd05d` revert / PR #234 incident).

After this PR merges, the `no_row → regenerate` wave now resolves real frozen
claimers from the bulk-loaded `attribution_snapshot`. Generated files use
clean names (no `_<timestamp>_<hash>` tokens) and are partitioned by real
claimer names.

### Step 4 — Remediate the recent window (D-08, after Step 3)

Once Sub-project E is live, sweep the garbage-named attachments from the
active billing window using the remediation mode. The default window is
26 weeks (`REMEDIATION_WINDOW_WEEKS`). See
[environment.md](/docs/reference/environment) for flag details.

**Always run dry-run first** — the dry-run logs what it would delete without
touching Smartsheet.

Trigger via the **Actions → "Run workflow"** button, setting the
`advanced_options` field:

```text
advanced_options: remediate_claimers:1,remediation_dry_run:1,remediation_window_weeks:26
```

Review the dry-run summary in the job log:

```text
✅ run_claimer_remediation [DRY-RUN] complete: scanned=N garbage=N deleted=0 exempted=N out_of_window=N
```

Also grep for the per-attachment lines to inspect scope:

```text
🔍 [DRY-RUN] would delete garbage attachment att=... sheet=... wr=... week=... variant=...
```

If the counts look reasonable, re-run with dry-run off:

```text
advanced_options: remediate_claimers:1,remediation_dry_run:0,remediation_window_weeks:26
```

The remediation mode returns immediately (no Excel generation in the same
session). Normal cron runs are unaffected — `REMEDIATE_CLAIMERS` Python
default is `'0'` so the sweep never fires unless explicitly activated
through `advanced_options`.

Remediating **after** E activation means each regenerated file uses the
clean-name format (no `_<timestamp>_<hash>` token churn). History deeper
than ~26 weeks self-heals on the next natural edit; no action needed.

### Roll-back notes

| Scenario | Action |
|---|---|
| Revert E activation | Set `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` in the workflow (mirrors the `46cd05d` mitigation). Token-named filenames resume; the `group_content_hash` store continues shadow-writing. |
| Disable remediation | Leave `REMEDIATE_CLAIMERS: '0'` (workflow default). No garbage attachments are deleted. |
| Revert bulk-prefetch wiring | Set `BILLING_AUDIT_AVAILABLE=false` to disable all attribution; pipeline falls back to current-foreman for all variants. |
