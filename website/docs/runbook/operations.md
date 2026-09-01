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
   `wr_filter=13792260,16975895` for a targeted reprocess.
4. Submit.

## Common knobs

| Input / var | Purpose |
| --- | --- |
| `test_mode` | Skip uploads, shorten retention to 30 days. |
| `force_generation` | Bypass the "no eligible data" short-circuit. |
| `reset_hash_history` | Force every group to regenerate this run (escalates via Supabase `pipeline_memory.group_state`, D-02 trigger 5) — there is no local `hash_history.json` to invalidate since PR #373. |
| `force_rediscovery` | No-op. Discovery validates every candidate sheet in full every run since PR #373 retired the local discovery cache; kept for backward compatibility. |
| `wr_filter` / `exclude_wrs` | Narrow the run to specific work requests. |
| `advanced_options` | Composite knob parsed by the workflow into env vars. |

## Interpreting a failed run

1. Open the failed workflow run in the Actions tab.
2. Check the "Run system health check" / "Generate reports" step logs.
3. Download the `Manifest-…` artifact — the JSON summary tells you how
   many WRs and weeks were processed before the failure.
4. If Sentry is configured, open the release matching the run's SHA to
   see exceptions and log breadcrumbs.
5. Discovery is never stale — every candidate sheet is validated in full
   every run (the local discovery cache was retired in PR #373). If a
   sheet still isn't found, check the folder membership and column
   mapping instead.

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
| Turn off run-memory writes (Phase 11) | Delete the `RUN_MEMORY_WRITE_ENABLED: '1'` line from the `Generate reports` step (or set it to `'0'`). No code change; rows already in `pipeline_memory` are harmless. See the section below. |
| Revert the local-cache retirement (PR #373, Phase 11 Plan 08 / INC-05) | Revert PR #373. There is no local JSON cache to restore or reset — the retirement removed the cache files and their GitHub Actions restore/save steps outright, so rollback is a code revert, not a cache operation. |

## Run-memory writes and the incremental-read rollout (Phase 11)

**Owned by:** Python billing pipeline (`generate_weekly_pdfs.py` →
`pipeline/orchestrate.py`, on the GitHub Actions weekly workflow). The
Supabase project is the same one `billing_audit` uses; the `portal-v2`
web app is not involved.

Phase 11 teaches the pipeline to remember what it read. Every scheduled
run writes a Supabase `pipeline_memory` ledger — one `run_ledger` row per
run, a per-sheet `sheet_registry` watermark, and the observed `row_state`
/ `group_state` for every accepted billing row and generated group — so a
future run can read only the rows that changed. That future behaviour is
rolled out in two separately gated steps:

| Flag | Where | State | What it turns on |
|---|---|---|---|
| `RUN_MEMORY_WRITE_ENABLED` | `Generate reports` step env | **`'1'` since PR #353** | The memory writes above, the in-process shadow-parity comparator (`parity_verdict` in `run_ledger.notes`), and the Monday deep run's deletion reconciliation. Excel generation, uploads and cleanup are unchanged. |
| `RUN_MEMORY_INCREMENTAL_ENABLED` | not set (code default `'0'`) | **OFF** | The incremental read itself (delta reads + regenerating only affected groups). Do not set it until the five-run parity streak is recorded and the 11-07 decision is re-opened (`docs/run-memory-write-flip-checklist.md`). |
| `RUN_MEMORY_SHADOW_MAX_MINUTES` | `Generate reports` step env | **`'25'`** (code default `10`) | Sub-budget for the shadow read-side probes. Sized from run #2801 (~11 s/sheet × 121 sheets); at the default only 56 sheets were probed, so the read verdict was `skipped` — and any `skipped` side blocks an overall `pass`. |

### What you will see on a normal run

- A `🧭 Run-memory mode resolved: full` line, then `⚡ Run-memory row
  writes: N sheet(s) written, 0 errored … confirmed=True`.
- A shadow-parity line and a `parity_verdict` of `pass`, `fail` or
  `skipped` in that run's `run_ledger.notes`. `skipped` on a quiet run
  (nothing changed, nothing to compare) is normal and does not count
  toward or against the streak.
- On Monday's `weekly_comprehensive` run only: a `🗑️ Deep-run
  reconciliation` line when rows deleted in Smartsheet were marked
  `deleted_at`.

### What needs attention

| Symptom | Meaning | Action |
|---|---|---|
| `mem_sheets_errored > 0` / `mem_confirmed=false` in `run_ledger.notes`, or `⚠️ pipeline_memory …` warnings | Supabase was unreachable or a write was partial. The run still completes — the path is fail-open — but that run's memory is incomplete and its parity verdict is `skipped`. | Check Supabase status / the service-role secret. No billing impact; the next run rewrites. |
| `⚠️ Supabase client init … failed (<Exception>: …)` right after `Phase 1 complete`, then `0 sheet(s) written, N errored` and **no** `run_ledger` row | The `pipeline_memory` client could not be built at all — usually an SDK/options drift (the first post-flip run, 33090659647, hit `AttributeError: 'ClientOptions' object has no attribute 'storage'` on `supabase==2.31.0`). `billing_audit` builds its own client and is unaffected. | The log line names the exception. The client now retries without the PostgREST timeout before giving up; if it still fails, treat it as a code defect (not an outage) and open an issue. |
| Sentry error `parity fail` (message carries counts, group keys and the run id) | The incremental selector would have regenerated a different set of groups than the full run did. **Blocking defect for the rollout, inert for the run** — nothing was generated differently. | Do not flip `RUN_MEMORY_INCREMENTAL_ENABLED`. Read `parity_details` in `run_ledger.notes` and open an issue. "Actual" is the set of generated groups that had an upload task; `actual_withheld_excluded` counts the generated-but-never-uploaded groups (quarantined `_NO_MATCH` / `Unknown_Foreman` names) dropped from both sides — a large number there is normal, not a finding. `only_in_candidate` (groups the incremental path would have *considered* but the full run skipped as unchanged — e.g. a helper variant of a WR whose primary changed) is informational too. A `fail` means `actual_not_in_candidate` — the full run regenerated a group the incremental selector would have missed — or a hash mismatch on a shared group. |
| `⏩ Skipping run-memory row writes` / `Skipping shadow parity check` | The session budget guard fired (`RUN_MEMORY_WRITE_MAX_MINUTES` / `RUN_MEMORY_SHADOW_MAX_MINUTES` + headroom). | Expected on a slow run; investigate only if it repeats. |
| `Deep-run reconciliation skipped sheet …: failed/partial full read` | A sheet did not read cleanly, so its stored rows were left untouched rather than risk a false deletion. | Nothing; the next Monday run retries. |

### Confirming the flip (first scheduled run after #353)

```sql
select run_id, status, finished_at, sheets_changed,
       notes->>'mem_sheets_errored' as mem_err,
       notes->>'execution_type' as exec, notes->>'parity_verdict' as parity,
       notes->>'mem_confirmed' as confirmed
from pipeline_memory.run_ledger order by started_at desc limit 3;
```

Pass = `status='success'`, `sheets_changed` populated, `mem_err='0'`,
`confirmed=true`, a `parity` value present. (`run_ledger` has no
`sheets_errored` column — the per-run error count lives in `notes`.) The streak that authorises the
incremental read is derived on demand by
`pipeline_memory.reader.get_parity_streak()` — five consecutive `pass`
verdicts on `production_frequent` runs with no intervening `fail`.

### Rollback

Delete the `RUN_MEMORY_WRITE_ENABLED: '1'` line from the `Generate
reports` step (or set it to `'0'`). Every call site is fail-open and
self-gates on this flag plus `TEST_MODE`, so no code change is needed.
Data already written to `pipeline_memory` stays and is harmless. Full
operator checklist: `docs/run-memory-write-flip-checklist.md` in the
repository.
