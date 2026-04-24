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
| `TIME_BUDGET_MINUTES` | `0` (code) / `180` (workflow) | Graceful stop budget in minutes. `0` disables the early-exit. The weekly workflow sets `180` (3h) with a matching runner `timeout-minutes: 195` (15min cushion for cache/artifact save steps); local runs default to disabled. |
| `ATTACHMENT_PREFETCH_MAX_MINUTES` | `10` | Phase sub-budget for the target-row attachment pre-fetch (introduced 2026-04-22). Passed as `timeout=` to `as_completed(...)` so the iterator itself raises `FuturesTimeoutError` if stuck HTTP calls prevent progress. When it fires, the consumer loop exits, in-flight threads are abandoned via `executor.shutdown(wait=False, cancel_futures=True)`, and the remaining rows fall back to per-row on-demand lookups. Also used by the pre-flight guard: if less than this many minutes remain in the session budget, pre-fetch is skipped entirely. |
| `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` | `45` | Defensive per-future timeout passed to `future.result(timeout=...)` inside the pre-fetch consumer loop. In the current code path this is belt-and-suspenders — `as_completed` only yields already-done futures, so `.result()` returns immediately — but a future refactor that yielded not-yet-done futures would still degrade gracefully instead of raising. |

## Change detection & history

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXTENDED_CHANGE_DETECTION` | `true` | Include foreman/dept in the diff check. |
| `HISTORY_SKIP_ENABLED` | `true` | Skip groups with unchanged hash. |
| `ATTACHMENT_REQUIRED_FOR_SKIP` | `true` | Only skip when the Smartsheet attachment exists. |
| `RESET_HASH_HISTORY` | `false` | Wipe hash state and regenerate. |
| `KEEP_HISTORICAL_WEEKS` | `false` | Keep older week folders on disk. |

## Rate contract versioning

:::caution LEGACY — retired 2026-04-24
The Python CSV-side rate recalc was retired on 2026-04-24.
Smartsheet now emits the authoritative `Units Total Price`
natively on `ORIGINAL_CONTRACT_FOLDER_IDS` sheets for rows whose
`Snapshot Date >= 2026-04-12` and `Units Completed?` is checked.
Running the Python recalc on top of Smartsheet's authoritative
price was a silent-corruption trap. The production workflow
(`.github/workflows/weekly-excel-generation.yml`) now pins all
three variables below to empty strings; the env vars themselves
are retained so re-enablement is a one-line workflow revert if
ever needed. See the `[2026-04-24]` Living Ledger entry in
`CLAUDE.md` for the full incident context and revert path.
:::

| Variable | Purpose |
| --- | --- |
| `RATE_CUTOFF_DATE` (LEGACY) | `YYYY-MM-DD` switch date for new rates. Production workflow pins this to `''`. |
| `NEW_RATES_CSV` (LEGACY) | Path to the new rate CSV. Production workflow pins this to `''`. |
| `OLD_RATES_CSV` (LEGACY) | Path to the prior rate CSV. Production workflow pins this to `''`. |

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
