---
id: workflows
title: GitHub Actions workflows
sidebar_position: 3
---

# GitHub Actions workflows

All workflows live under `.github/workflows/`.

## `weekly-excel-generation.yml`

The production workhorse. Runs on schedule (weekday business-hour cadence +
weekend maintenance + Monday-morning comprehensive) and on
`workflow_dispatch` with a wide set of inputs for debugging and manual
reruns.

Key behaviors:

- Python `3.12`, `pip` cached by `requirements.txt` hash.
- Restores `hash_history.json` and `discovery_cache.json` via `cache/restore`,
  and saves them back in an `if: always()` step so caches survive timeouts.
- Derives an `execution_type` (`production_frequent`, `weekend_maintenance`,
  `weekly_comprehensive`, `manual`, `scheduled`) used in artifact names and
  the Notion sync.
- Parses the `advanced_options` input (`max_groups:X,regen_weeks:...`) into
  env vars before invoking `generate_weekly_pdfs.py`.
- Optionally tags a Sentry release when `SENTRY_AUTH_TOKEN` is set.
- Runs `scripts/generate_artifact_manifest.py`, organizes Excel files
  `by_wr/` and `by_week/` in `artifact_staging/`, and uploads multiple
  named artifacts (Complete, By-WorkRequest, By-WeekEnding, Manifest).
- Calls `scripts/notion_sync.py --mode run` when `vars.NOTION_ENABLED == 'true'`.

## `system-health-check.yml`

Daily 02:00 UTC smoke test. Installs deps, verifies
`SMARTSHEET_API_TOKEN` is present, runs `validate_system_health.py`, and
fails the job if the report is `CRITICAL`. Uploads
`generated_docs/system_health.json` as an artifact for 30 days.

## `notion-sync.yml`

Dedicated path for syncing existing run data into Notion (outside of the
generator job).

## `snyk-security.yml`

Security scanning for vulnerable dependencies.

## `codecov.yml`

Test coverage upload for PRs.

## `azure-pipelines.yml`

Mirror pipeline for Azure DevOps. See `AZURE_*` docs in the repo root for
setup.

## `docs-changelog.yml` *(new)*

Triggers on push to `master`. Runs `scripts/generate_runbook_entry.py`
which inspects the diff between the previous and current commit, groups
changed files into buckets (Python scripts, workflows, portals, docs),
and writes a new blog post under `website/blog/`. The post is committed
back with `[skip ci]`. See
[How this site updates](../reference/how-this-site-updates.md).
