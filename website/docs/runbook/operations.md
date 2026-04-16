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
