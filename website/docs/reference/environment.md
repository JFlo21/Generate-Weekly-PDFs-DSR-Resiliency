---
id: environment
title: Environment reference
sidebar_position: 1
---

# Environment reference

Canonical list of environment variables consumed by the generator and the
workflow. Copy `.env.example` to `.env` for local dev.

## Required

| Variable | Purpose |
| --- | --- |
| `SMARTSHEET_API_TOKEN` | Token used by `smartsheet-python-sdk` to authenticate. |

## Smartsheet targets

| Variable | Default | Purpose |
| --- | --- | --- |
| `TARGET_SHEET_ID` | `5723337641643908` | Sheet the Excel attachments land on. |
| `AUDIT_SHEET_ID` | — | Where audit rows/stats are written. |
| `SUBCONTRACTOR_FOLDER_IDS` | `4232010517505924,2588197684307844` | Folders scanned for subcontractor sheets. |
| `ORIGINAL_CONTRACT_FOLDER_IDS` | `7644752003786628,8815193070299012` | Folders scanned for original-contract sheets. |

## Execution controls

| Variable | Default | Purpose |
| --- | --- | --- |
| `SKIP_UPLOAD` | `false` | Skip Smartsheet uploads (local testing). |
| `SKIP_CELL_HISTORY` | `false` | Skip cell history lookups for speed. |
| `TEST_MODE` | `false` | Dry-run mode. |
| `FORCE_GENERATION` | `false` | Generate even with no eligible data. |
| `RES_GROUPING_MODE` | `both` | `primary`, `helper`, or `both`. |
| `WR_FILTER` | — | Comma-separated WR allowlist. |
| `EXCLUDE_WRS` | — | Comma-separated WR denylist. |

## Performance

| Variable | Default | Purpose |
| --- | --- | --- |
| `USE_DISCOVERY_CACHE` | `true` | Honor `generated_docs/discovery_cache.json`. |
| `FORCE_REDISCOVERY` | `false` | Ignore the discovery cache. |
| `DISCOVERY_CACHE_TTL_MIN` | `10080` | Cache age ceiling, minutes. |
| `PARALLEL_WORKERS` | `8` | Threads for data fetch + attachment pre-fetch. |
| `PARALLEL_WORKERS_DISCOVERY` | `8` | Threads for sheet discovery. |
| `TIME_BUDGET_MINUTES` | `80` | Graceful stop before Actions hard-kill. |

## Change detection & history

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXTENDED_CHANGE_DETECTION` | `true` | Include foreman/dept in the diff check. |
| `HISTORY_SKIP_ENABLED` | `true` | Skip groups with unchanged hash. |
| `ATTACHMENT_REQUIRED_FOR_SKIP` | `true` | Only skip when the Smartsheet attachment exists. |
| `RESET_HASH_HISTORY` | `false` | Wipe hash state and regenerate. |
| `KEEP_HISTORICAL_WEEKS` | `false` | Keep older week folders on disk. |

## Rate contract versioning

| Variable | Purpose |
| --- | --- |
| `RATE_CUTOFF_DATE` | `YYYY-MM-DD` switch date for new rates. |
| `NEW_RATES_CSV` | Path to the new rate CSV. |
| `OLD_RATES_CSV` | Path to the prior rate CSV. |

## Observability

| Variable | Purpose |
| --- | --- |
| `SENTRY_DSN` | Sentry DSN. Optional. |
| `SENTRY_AUTH_TOKEN` | Enables the "Create Sentry release" workflow step. |
| `SENTRY_ORG` / `SENTRY_PROJECT_WORKFLOW` | Targets for the release tag. |
| `ENVIRONMENT` / `RELEASE` / `SENTRY_RELEASE` | Populated by the workflow. |

## Notion sync

| Variable | Purpose |
| --- | --- |
| `NOTION_TOKEN` | Notion integration secret. |
| `NOTION_PIPELINE_DB` | Pipeline runs DB. |
| `NOTION_CHANGELOG_DB` | Changelog DB. |
| `NOTION_METRICS_DB` | Metrics DB. |
| `NOTION_INCIDENTS_DB` | Incidents DB. |
| `NOTION_ENABLED` | Repository variable toggle — the workflow short-circuits when this isn't `true`. |
