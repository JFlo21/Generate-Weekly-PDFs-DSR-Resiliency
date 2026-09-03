---
id: scripts
title: Helper scripts
sidebar_position: 5
---

# Helper scripts

Utilities that live under `scripts/` or at the repo root.

## Notion integration

- `scripts/notion_sync.py` — upserts a row into the Notion pipeline/metric
  DBs after each workflow run. Consumes `generated_docs/run_summary.json`
  via env vars set by the workflow.
- `scripts/notion_setup.py` — one-time provisioning of the Notion
  databases. Run manually with a Notion token.
- `scripts/notion_dashboard.py` — generates dashboard pages that embed
  rollups from the sync databases.

## Artifact preservation

- `scripts/generate_artifact_manifest.py` — walks `generated_docs/`,
  produces a SHA256-stamped JSON index summarizing files, WRs, and weeks.
  Called by the weekly workflow's "Generate artifact manifest" step.

## Ownership attribution backfill

Three scripts write to `billing_audit.attribution_snapshot`, and two of them
have similar names with opposite semantics. The ladder, the procedure, the exit
codes and the rollback live on
[Ownership and claim-time attribution](ownership-attribution.md) — this section
only tells the scripts apart.

- `scripts/backfill_claim_time_attribution.py` — OWN-03 sources 1-4. Derives
  the historically correct claimer for sentinel-frozen rows from run memory,
  the same row's other roles, artifact filenames and the Supabase hash store —
  never from current Smartsheet state. Dry-run by default; `--wr` and
  `--weeks` are both required; `--apply` needs `--i-approved-this` and a
  same-UTC-day backup table. One-time / off-hours operator remediation, run by
  hand.
- `scripts/backfill_cell_history_attribution.py` — OWN-03 source 5. Reads the
  first script's report and resolves what is still `unresolved` or `conflict`
  from Smartsheet cell history, paced and capped. Runs only from the
  manual-dispatch [`cell-history-backfill.yml`](workflows.md#cell-history-backfillyml)
  workflow, never inside the billing run.
- `scripts/backfill_attribution_snapshot.py` — the older one-shot backfill. It
  freezes whatever Smartsheet shows **today** for a target week ("current
  always wins", a policy rejected on 2026-09-01). Do **not** run it against WRs
  the claim-time script has remediated: it freezes the current name into any
  role that is still NULL, which may be the role the claim-time ladder is still
  trying to name.

## Verification

- `verify-azure-setup.sh` — shell script that validates the Azure DevOps
  mirror prerequisites before you run the Azure pipeline for the first
  time.

## Development utilities

- `cleanup_excels.py` — prunes `generated_docs/*.xlsx`. Handy before a
  clean local run.
- `test_production_reload.py` — re-runs the production reload path
  against fixture data.
