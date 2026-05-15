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

## Subcontractor rate variants

*(Added 2026-05-14, Phase 1 — see also
[Subcontractor rate variants](../runbook/workflows.md#subcontractor-rate-variants)
in the runbook for operator-facing context.)*

**Component owner:** Python billing pipeline
(`generate_weekly_pdfs.py`) — the variant emission code path, the
CSV loader, the dual-routing target-map build, and the missing-CU
WARNING all live in this module. Notion sync and the `portal-v2`
Supabase tier are not involved.

### `SUBCONTRACTOR_RATES_CSV`

**Default:** `data/subcontractor_rates.csv`
**Purpose:** Path to the operator-managed subcontractor rate matrix
CSV (17 columns: `CU`, `Description`, `Work Type`, and the six
priced columns `reduced_install_price` / `reduced_remove_price` /
`reduced_transfer_price` / `new_install_price` / `new_remove_price`
/ `new_transfer_price`, plus identifying metadata). Consumed by the
`_AEPBillable` and `_ReducedSub` variants to compute
`rate × qty` per row's CU code and work type. Loaded once at module
import (3691 priced CUs in the shipped file). Currency cells
(`$45.95`) and BOM-prefixed files are tolerated; rows where all six
priced columns are zero are skipped.
**Valid values:** Any filesystem path resolvable from the repo root
or an absolute path. Resolved via `_sanitize_csv_path` — path
traversal attempts are normalised away.
**Rollback:** Setting to a path that does not exist causes the
loader to log an ERROR and return an empty dict. New-variant
generation then silently falls through to the SmartSheet
`Units Total Price` for every row (safe no-op per D-16 fail-safe
contract — never zero-out, never error). To intentionally retire
the feature, prefer flipping
[`SUBCONTRACTOR_RATE_VARIANTS_ENABLED`](#subcontractor_rate_variants_enabled)
to `0` so the kill switch is the visible signal.

### `SUBCONTRACTOR_PPP_SHEET_ID`

**Default:** `8162920222379908`
**Purpose:** Smartsheet sheet id for the secondary attachment
target used by `_ReducedSub` and `_ReducedSub_Helper_<name>` files.
Files of those two variants attach to **both**
[`TARGET_SHEET_ID`](#smartsheet-targets) (`5723337641643908`)
**and** this sheet — operators see the same `_ReducedSub_*.xlsx`
file appear as an attachment on two rows (one on each target
sheet). `_AEPBillable` variants and every legacy variant
(primary / helper / vac_crew) continue to route to
`TARGET_SHEET_ID` only.

**Disable dual routing:** Set to `0` (integer) OR `''` (empty
string). Both values resolve to `0` at import time and the
downstream gate
(`if SUBCONTRACTOR_RATE_VARIANTS_ENABLED and SUBCONTRACTOR_PPP_SHEET_ID:`)
skips the second `target_map` build, the PPP prefetch (when WR-05
lands), the PPP upload-task emission, and (when WR-01 lands) the
PPP end-of-run cleanup pass. Pre-2026-05-15 this asymmetry was
undocumented — `''` silently fell back to the hardcoded default,
while `0` correctly disabled. The 01-10 gap-closure plan
special-cased empty-string-as-zero at the call site so both forms
now behave consistently with the operator's intent.

**Other values:** Any non-empty, non-integer value falls back to
the hardcoded default `8162920222379908` and logs a WARNING
(`Invalid sheet id value provided`). The fallback is intentional —
the shared `_coerce_sheet_id` helper preserves default-fallback
for `TARGET_SHEET_ID` where "disabled" is not a state.

**Startup banner:** The resolved state is logged at startup:

- `📊 Subcontractor PPP routing ENABLED (target sheet id: <id>)` — value > 0
- `📊 Subcontractor PPP routing DISABLED (SUBCONTRACTOR_PPP_SHEET_ID='' or 0)` — value is 0

Operators can grep the startup banner to confirm the resolved
routing state without inspecting individual env-var values.

**Rollback:** If the value equals `TARGET_SHEET_ID`, the dual
routing detects same-sheet config and skips the second upload (no
duplicate attachments). If the sheet is unreachable, the pipeline
logs an ERROR via `_redact_exception_message` and degrades
automatically to single-sheet routing for the rest of the run — no
operator intervention required.

### `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`

**Default:** `'1'` — truthy values are `1` / `true` / `yes` / `on`
(case-insensitive). Any other value (including empty string,
`0`, `false`) disables the feature.
**Purpose:** Default-on kill switch covering the entire
new-variant code path. When disabled, no `_AEPBillable` or
`_ReducedSub` files generate, no dual-target routing fires, the
subcontractor CSV is not loaded, and the
`billing_audit.pipeline_run.variant` column records every group
as `'primary'`. Existing primary / helper / vac_crew flows are
byte-identical to the pre-Phase-1 baseline. Pattern mirrors
`RATE_RECALC_SKIP_ORIGINAL_CONTRACT` and
`RATE_RECALC_WEEKLY_FALLBACK`.
**Rollback:** Set to `0` or `false` in the GitHub Actions workflow
`env:` block (or in `.env` for local runs). The next run skips all
new-variant generation immediately — **no code revert required**.
The kill-switch state is logged in the startup banner (e.g.
`📊 Subcontractor rate variants ENABLED ...`), so operators
grepping the run header can confirm the active state at a glance.

### `AEP_BILLABLE_CUTOFF`

**Default:** `2026-04-12` (AEP rate-increase contract awarded to Linetec)
**Format:** `YYYY-MM-DD` (e.g., `2026-04-12`).
**Purpose:** Snapshot-date cutoff for the `_AEPBillable` variant. Phase 1 emits
`_AEPBillable` and `_AEPBillable_Helper_<name>` files ONLY for rows whose
`Snapshot Date` is on or after this date. `_ReducedSub` variants have no cutoff
(they generate unconditionally for subcontractor-folder WR groups).

**When to override:** Operators may need to roll the cutoff forward (delayed contract
amendment) or back (retroactive billing decision) without redeploying the Python
engine. Set this env var at the workflow level. The default tracks the original
contract award; changing it is an operator decision, not a developer decision.

**Invalid format behavior:** If the env-var value is set but does not parse as
`YYYY-MM-DD`, the loader logs `⚠️ Invalid AEP_BILLABLE_CUTOFF format: <value>;
expected YYYY-MM-DD. Falling back to default 2026-04-12.` and continues with the
hardcoded default. This is fail-safe — a misconfigured env var never silently
suppresses `_AEPBillable` generation entirely.

**Startup banner:** The resolved cutoff is logged at startup:

- `📊 AEP Billable cutoff: 2026-04-12 (default)` — env var unset
- `📊 AEP Billable cutoff: 2026-05-01 (env override)` — env var set
- (If invalid format) the error log fires first; the banner still names the
  fallback default.

**Related:** `RATE_CUTOFF_DATE` is retired (see Living Ledger 2026-04-24 14:30);
it must NOT be re-used as the AEP-billable cutoff. `AEP_BILLABLE_CUTOFF` is the
Phase 1 successor with explicit subcontractor-variant scope.

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
