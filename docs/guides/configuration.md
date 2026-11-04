<!-- generated-by: gsd-doc-writer -->
# Configuration

How the billing pipeline is configured, which settings are required, which have defaults, and how
values differ between a local run and the GitHub Actions cron.

This page is a map. The full operator catalog (every flag, with business context) is
[`.github/prompts/configuration-environment.md`](../../.github/prompts/configuration-environment.md)
(see its "Operator quick reference" section). The code that parses each variable is
[`pipeline/config.py`](../../pipeline/config.py). When this page and the code disagree, the code wins.

## Overview

- Configuration is environment variables only. There is no YAML, JSON or TOML settings file for the
  pipeline itself (the one JSON file in play is the opt-in corrections file described below).
- Every variable is read with `os.getenv()` and a default in `pipeline/config.py`, which the
  `generate_weekly_pdfs.py` facade re-exports.
- `python-dotenv` loads a local `.env` through `load_dotenv()` in the facade before `pipeline/config.py`
  is parsed, so a `.env` in the project root populates the same variables for local runs.
- Never commit a real `.env`, and never write token, key, sheet-id or personal-name values into docs,
  commits, issues or logs. This page lists variable names only.

## Environment variables

Grouped by purpose. "Required" means the pipeline cannot do its job without it. Defaults are the code
defaults in `pipeline/config.py` unless noted.

### Required and integration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMARTSHEET_API_TOKEN` | Yes | none | Smartsheet API token. Supply via the environment only (local `.env` or the GitHub Actions secret of the same name). |
| `TARGET_SHEET_ID` | No | built-in sheet id | Destination sheet whose rows receive the generated Excel attachments. A non-numeric value logs a warning and falls back to the default. |
| `AUDIT_SHEET_ID` | No | unset | Destination for audit rows and stats only. `BILLING_AUDIT_SHEET_ID` is accepted as a legacy alias. |
| `SENTRY_DSN` | No | unset | Enables Sentry error reporting. |
| `SENTRY_ENVIRONMENT` / `ENVIRONMENT` | No | `ENVIRONMENT` falls back to `production` | Sentry `environment` tag. `SENTRY_*` variables take priority over the legacy names. |
| `SENTRY_RELEASE` / `RELEASE` | No | `RELEASE` falls back to `weekly-excel-generator@1.0.0` | Sentry `release` tag. |
| `SENTRY_ENABLE_LOGS` | No | `false` | Sentry Logs gate. Leave off: INFO-path logs can embed row PII (`before_send_log` in `pipeline/observability.py` is only a backstop). |
| `SENTRY_CRON_MONITOR_SLUG` | No | `weekly-excel-generation` | Sentry cron monitor slug. |
| `EXECUTION_TYPE` | No | `manual` | Run context (`manual`, `production_frequent`, `weekend_maintenance`, `weekly_comprehensive`, ...). Set by the workflow; it also gates incremental reads. |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Only when a Supabase write path is on | unset | Used by the `pipeline_memory` and `billing_audit` layers. The service-role key is a secret and must never be exposed to the browser app. |

### Run control (commonly touched)

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_MODE` | `false` | Use synthetic data instead of Smartsheet. With a real token still present, a run reads every sheet live, so blank the token for a truly synthetic run. |
| `SKIP_UPLOAD` | `false` | Generate files into `generated_docs/` but do not upload or delete attachments. |
| `SKIP_CELL_HISTORY` | `false` | Skip the cell-history lookup used by the audit (performance). |
| `FORCE_GENERATION` | `0` | Ignore hash short-circuiting and regenerate. |
| `WR_FILTER` | empty | Comma list of Work Requests to process. |
| `EXCLUDE_WRS` | empty | Comma list of Work Requests to exclude. |
| `MAX_GROUPS` | `0` (no limit) | Cap the number of groups processed. |
| `RES_GROUPING_MODE` | `both` | `primary`, `helper` or `both`. An invalid value logs a warning and becomes `both`. |
| `EXTENDED_CHANGE_DETECTION` | `1` | Include foreman, dept and scope in the change-detection hash. |
| `PARALLEL_WORKERS` / `PARALLEL_WORKERS_DISCOVERY` | `8` / `8` | Worker pools. Keep at 8 or below (Smartsheet allows 300 requests per minute). |
| `TIME_BUDGET_MINUTES` | `0` (disabled) | Graceful stop budget. The weekly workflow sets `165`; it must stay strictly below the job `timeout-minutes` (`180`). Raise both together. |

Boolean parsing: most flags accept `1`, `true` or `yes` (case-insensitive). The newer feature switches
(`HELPER2_ENABLED`, `FOREMAN_NOTES_UPLOAD`, the `RUN_MEMORY_*` and `AUDIT_MEMORY_ENABLED` family) also
accept `on`. A few legacy flags (`SKIP_UPLOAD`, `SKIP_CELL_HISTORY`, `SNAPSHOT_DRIFT_*`) compare to the
literal string `true` only, so use exactly `true` for those.

### Regeneration and reset

| Variable | Default | Description |
|----------|---------|-------------|
| `RESET_HASH_HISTORY` | `0` | Treat every group as changed (full regeneration). Change detection is backed by `pipeline_memory.group_state`, not a local file. |
| `REGEN_WEEKS` | empty | Comma list of `MMDDYY` week-ending codes to force-regenerate. |
| `RESET_WR_LIST` | empty | Comma list of WRs to purge; overrides a full reset. |
| `KEEP_HISTORICAL_WEEKS` | `0` | Preserve attachments for weeks not processed this run. |
| `HISTORY_SKIP_ENABLED` | `1` | Allow skipping a group when its hash is unchanged. |
| `ATTACHMENT_REQUIRED_FOR_SKIP` | `1` | Require an existing attachment before a skip is allowed. |

In GitHub Actions, the manual-dispatch `advanced_options` input carries several of these as
`key:value,key:value` pairs. Keep that exact format; operational runbooks depend on it. See
[`force-week-regeneration`](../../.claude/skills/force-week-regeneration) for the procedure.

### Discovery folders and rate tables

| Variable | Description |
|----------|-------------|
| `SUBCONTRACTOR_FOLDER_IDS`, `ORIGINAL_CONTRACT_FOLDER_IDS`, `VAC_CREW_FOLDER_IDS` | Comma lists of Smartsheet folder ids searched for source sheets. The first two have built-in defaults (overridable by workflow repository variables); `VAC_CREW_FOLDER_IDS` defaults to empty. `VAC_CREW_SHEET_IDS` adds individual sheets. |
| `NEW_RATES_CSV`, `OLD_RATES_CSV`, `SUBCONTRACTOR_RATES_CSV` | Rate table files (read in `pipeline/pricing.py`). |
| `RATE_CUTOFF_DATE` | Date separating old and new rate tables. |

### Feature switches (default-safe)

These ship dormant or scoped. Their full semantics are in the catalog.

| Variable | Default | Description |
|----------|---------|-------------|
| `HELPER2_ENABLED` | `0` | Second helping-foreman slot. Off is a complete no-op. In the workflow it is `${{ vars.HELPER2_ENABLED \|\| '0' }}`, so the repository variable is the on/off switch. Runbook: `website/docs/runbook/foreman-helper-2.md`. |
| `FOREMAN_NOTES_SCOPE` | `pilot` | `off`, `pilot` or `all`; anything else is treated as `off` with a warning. This is the configured scope; the effective scope also depends on `FOREMAN_NOTES_UPLOAD` and `TEST_MODE`. |
| `FOREMAN_NOTES_PILOT_GFS` | empty (zero pilot groups) | General Foreman allowlist. Set only in a local `.env` or the repository secret of the same name, never in the repository. |
| `FOREMAN_NOTES_UPLOAD` | `0` | Rollout switch for pilot output reaching the target sheet. Runbook: `website/docs/runbook/foreman-notes-pilot.md`. |
| `FOREMAN_NOTES_GF_WR_COLUMN_ID`, `FOREMAN_NOTES_GF_COLUMN_ID` | built-in column ids | Target-sheet columns for the General Foreman lookup. Titles are verified at runtime; a mismatch fails closed. |
| `AUDIT_MEMORY_ENABLED` | `0` | Persist the audit findings into `pipeline_memory`. Independent of the two flags below. |
| `RUN_MEMORY_WRITE_ENABLED` | `0` | Master switch for run-memory writes; sub-budgets `RUN_MEMORY_WRITE_MAX_MINUTES` (10), `RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC` (45) and `RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN` (2). |
| `RUN_MEMORY_INCREMENTAL_ENABLED` | `0` | Delta reads; only reachable when `EXECUTION_TYPE=production_frequent`. Fixed overlap `SAFETY_WINDOW_MINUTES` (15). |
| `RUN_MEMORY_SHADOW_*` | see catalog | Shadow-parity sub-budgets (`MAX_MINUTES`, `RPC_TIMEOUT_SEC`, `GENERATION_HEADROOM_MIN`). |
| `SUPABASE_HASH_STORE_WRITE_ENABLED` | `1` | Supabase hash store writes. |
| `SUPABASE_HASH_STORE_AUTHORITATIVE` | `0` | When on, the Supabase hash drives skip decisions and filenames drop timestamp and hash tokens. Master revert is to leave it off. |
| `SNAPSHOT_DRIFT_AUDIT_ENABLED` | `true` | Report-only drift detection. |
| `SNAPSHOT_DRIFT_HOLD_ENABLED` | `false` | Hold-prior-week gating; opt-in. |
| `PRICE_VARIANCE_IN_RISK` | `false` | Count legacy price-variance anomalies toward audit `risk_level` (read in `audit_billing_changes.py`). |
| `REPORTING_CORRECTIONS_FILE` | unset (feature off) | Opt-in path to a private corrections JSON. See the next section. |

Further `SUBCONTRACTOR_*`, `VAC_CREW_*`, `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`, `LEGACY_PRIMARY_*`,
`REMEDIATE_CLAIMERS` and `REMEDIATION_*` switches are attribution and cleanup toggles; read the comment
block above each in `pipeline/config.py` before changing one.

### Debug flags

`QUIET_LOGGING` (`0`), `PER_CELL_DEBUG_ENABLED` (`1`), `LOG_UNKNOWN_COLUMNS` (`1`),
`UNMAPPED_COLUMN_SAMPLE_LIMIT` (`5`), `DEBUG_SAMPLE_ROWS` (`3`), `DEBUG_ESSENTIAL_ROWS` (`5`),
`FILTER_DIAGNOSTICS` (`0`), `FOREMAN_DIAGNOSTICS` (`0`).

### Retired and unconsumed names

Setting these has no effect: `USE_DISCOVERY_CACHE`, `DISCOVERY_CACHE_TTL_MIN`, `HASH_HISTORY_PATH`,
`ATTACHMENT_PREFETCH_MAX_MINUTES`, `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC`, and `FORCE_REDISCOVERY`
(kept for back-compat; a no-op). The catalog also lists names that appear in older prompts but are not
read by the pipeline (for example `SKIP_FILE_OPERATIONS`, `DRY_RUN_UPLOADS`, `MOCK_SMARTSHEET_UPLOAD`,
`DEBUG_MODE`, `CLEANUP_ONLY`, `SYNTHETIC_WR_COUNT`, `SYNTHETIC_ROW_VARIANCE`, `ENABLE_AUDIT_ANOMALIES`).
Do not rely on them.

## Reporting corrections (opt-in)

`REPORTING_CORRECTIONS_FILE` is the switch for owner-approved reporting corrections: re-crediting
specific, already-billed source rows to an approved owner and workday without touching any raw
Smartsheet cell. Logic lives in `pipeline/reporting_corrections.py`; the operator page is
[`website/docs/runbook/reporting-corrections.md`](../../website/docs/runbook/reporting-corrections.md).

| Aspect | Behavior |
|--------|----------|
| Type | Filesystem path to a JSON file (parsed in `pipeline/config.py`; leading and trailing whitespace stripped). |
| Default | Unset or blank: feature off. Every hook is an identity no-op and output is byte-identical to a run without the module. |
| Valid file | Each correction case `(WR, week ending)` is validated row by row against the admitted rows; a mismatch blocks that case only. |
| Set but unloadable file | `main()` stops the run before any read or write (ERROR check-in, exit 1; fail-closed rule below). Only the `validate` / `preview` CLI treats an invalid file as "nothing applied". |
| Failure inside the run | A failure while preparing corrections is non-fatal: the stamps are cleared and no correction is applied that run. |
| Side effects | The affected workbooks regenerate once (a `CORR=` token joins the change-detection hash). |
| Rollback | Retire first: set `"retired": true` on the case and let a run finish, which regenerates the files the rows return to and removes any correction-only workbook. Only then remove the case or the variable. Removing the variable outright leaves correction-only workbooks on the sheet (they bill those rows twice). See [Turning it off / rolling back](../../website/docs/runbook/reporting-corrections.md#turning-it-off--rolling-back). |

File format: start from [`docs/templates/reporting_corrections.template.json`](../templates/reporting_corrections.template.json).
The real file is private. Keep it outside the repository and never put it, or any name, WR number or
row id from it, in a commit, issue or log.

Check a file locally without any external write:

```bash
python -m pipeline.reporting_corrections validate --file <private.json>
python -m pipeline.reporting_corrections preview --file <private.json> --rows-json <private_rows.json>
```

Local dry run, limited to one WR, with uploads off (see the runbook for the full procedure):

```bash
TEST_MODE=true SKIP_UPLOAD=true WR_FILTER=<wr> REPORTING_CORRECTIONS_FILE=<private.json> PYTHONUTF8=1 python generate_weekly_pdfs.py
```

For scheduled runs the runbook describes supplying the file through a repository secret that the
weekly workflow decodes to a temporary path on the runner and exports as `REPORTING_CORRECTIONS_FILE`.
That "Stage reporting corrections" step is not in `weekly-excel-generation.yml` yet (owner approval
pending); the exact YAML is in the runbook, `website/docs/runbook/reporting-corrections.md` step 5.

Fail-closed rule: when `REPORTING_CORRECTIONS_FILE` is set but the file cannot be loaded (missing,
unreadable, outside the allowed directories, invalid, or any unexpected loader error), `main()` stops
the run before any Smartsheet read, upload or Supabase billing write: it logs `🚫 Reporting corrections:
file unavailable (<class>) -- run stopped, nothing generated or uploaded`, exits non-zero and checks in
ERROR. It never falls back to running without corrections. Unset means feature off, unchanged.

## Required vs optional

- Hard requirement: `SMARTSHEET_API_TOKEN`. Without it a live (non-`TEST_MODE`) run cannot read sheets.
- Everything else has a code default. Invalid numeric or sheet-id values either fall back to the default
  with a warning (`TARGET_SHEET_ID`, `RES_GROUPING_MODE`) or are coerced by `int(... or default)`, so
  an empty string behaves like unset.
- Fail-closed settings: `FOREMAN_NOTES_PILOT_GFS` empty means no pilot groups; a column-title mismatch
  on the General Foreman lookup means no pilot groups; a set-but-unloadable corrections file stops the
  run (see above).

## Per-environment configuration

| Environment | How values are supplied |
|-------------|-------------------------|
| Local development | A `.env` in the project root (copy from [`.env.example`](../../.env.example); see also `.env.template`), or variables exported in your shell. Use `SKIP_UPLOAD=true` for a dry run; for a synthetic run also blank `SMARTSHEET_API_TOKEN` and set `TEST_MODE=true`. Validation commands: [`docs/ai/safe-commands.md`](../ai/safe-commands.md). |
| GitHub Actions cron | [`.github/workflows/weekly-excel-generation.yml`](../../.github/workflows/weekly-excel-generation.yml) sets the job `env:` from repository secrets (`SMARTSHEET_API_TOKEN`, `SENTRY_DSN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `FOREMAN_NOTES_PILOT_GFS`), repository variables (`HELPER2_ENABLED`, `FOREMAN_NOTES_UPLOAD`, discovery folder ids, `EXCLUDE_WRS`), and workflow inputs. `TIME_BUDGET_MINUTES` is set here. |
| Cloud Agent installs | `scripts/cloud-agent-install.sh`. |

Repository secret and variable values live in GitHub settings and cannot be verified from the repository.
<!-- VERIFY: which repository secrets and variables are currently set in GitHub settings -->

## Related docs

- [`.github/prompts/configuration-environment.md`](../../.github/prompts/configuration-environment.md): authoritative variable catalog.
- [`docs/ai/architecture.md`](../ai/architecture.md): module map, schedules and timeouts.
- [`docs/ai/safe-commands.md`](../ai/safe-commands.md): validated local commands.
- `website/docs/runbook/`: operator runbooks for helper #2, Foreman Notes and reporting corrections.
