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

## Verification

- `verify-azure-setup.sh` — shell script that validates the Azure DevOps
  mirror prerequisites before you run the Azure pipeline for the first
  time.

## Development utilities

- `cleanup_excels.py` — prunes `generated_docs/*.xlsx`. Handy before a
  clean local run.
- `test_production_reload.py` — re-runs the production reload path
  against fixture data.
