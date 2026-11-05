<!-- generated-by: gsd-doc-writer -->
# Scripts Reference

Reference for every entry under `scripts/`, the top-level utility scripts in the repo root, and the
module CLI `python -m pipeline.reporting_corrections`. Names and invocations were read from the
source; write behavior was read from the code (not from docstrings alone) unless a
`<!-- VERIFY -->` marker says otherwise. Env vars are listed by name only.

Conventions used below:

- **Writes** column: `Smartsheet` / `Supabase` / `Notion` / `Sentry` / `local files` are the external
  or filesystem targets the script can write to. "Read-only" is used only where no write call was found
  in the script body (and, where noted, in the helpers it calls).
- **Workflow** column: the file under `.github/workflows/` that invokes the script, from a grep of
  every workflow. "none" means no workflow references it (operator or developer use only).
- All Python scripts are run from the repo root.
- Supabase clients (`billing_audit.client`, `pipeline_memory.client`) return no client when
  `TEST_MODE` is truthy or credentials are absent, so scripts that depend on them degrade to no-ops
  (or exit non-zero, see each row).

## Index by category

| Category | Entries |
|---|---|
| [6-gate harness](#6-gate-harness) | `run_6_gates.sh`, `check_api_equality.py`, `check_facade_completeness.py`, `check_mypy_delta.sh`, `check_run_summary_structure.py` |
| [Backfills](#backfills) | `backfill_attribution_snapshot.py`, `backfill_claim_time_attribution.py`, `backfill_cell_history_attribution.py` |
| [Checks and diagnostics](#checks-and-diagnostics) | `compare_control_run.py`, `mem04_experiment.py`, `mem04_passive_compare.py`, `security-probe.ts`, `validate_system_health.py`, `diagnose_pricing_issues.py`, `analyze_excel_totals.py`, `analyze_specific_excel.py`, `test_production_reload.py`, `run_info.py`, `verify-azure-setup.sh` |
| [Notion sync](#notion-sync) | `notion_setup.py`, `notion_dashboard.py`, `notion_sync.py` |
| [Artifact manifest and publishing](#artifact-manifest-and-publishing) | `generate_artifact_manifest.py`, `publish_artifacts_to_supabase.py` |
| [Cloud-agent install](#cloud-agent-install) | `cloud-agent-install.sh` |
| [Other](#other) | `generate_runbook_entry.py`, `cleanup_excels.py`, `audit_billing_changes.py`, `generate_weekly_pdfs.py`, `scripts/package.json` |
| [Module CLIs](#module-clis) | `python -m pipeline.reporting_corrections validate\|preview` |

Total: 29 script entries (plus the `scripts/package.json` support files) and 1 module CLI.

---

## 6-gate harness

`bash scripts/run_6_gates.sh` runs six blocking gates in cheapest-first order and aborts on the first
failure (`set -euo pipefail`). It forces `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`. Run it after any
module move or refactor of the facade/`pipeline/` split. No workflow calls it.

| Gate | Command run by the harness | What it checks |
|---|---|---|
| 1 | `python scripts/check_api_equality.py` | Top-level names in `generate_weekly_pdfs.py` plus `pipeline/*.py` still cover the frozen baseline in `tests/golden/baseline_names.json` |
| 2 | `python scripts/check_facade_completeness.py` | Every name in `tests/golden/facade_allowlist.json` resolves via `getattr` on the facade |
| 3 | `python -m pytest tests/ -q` | Full test suite |
| 4 | `bash scripts/check_mypy_delta.sh` | mypy error-line count has not increased vs `tests/golden/mypy_baseline_count.txt` |
| 5 | `python -m py_compile generate_weekly_pdfs.py` | Facade compiles |
| 6 | `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py` then `python scripts/check_run_summary_structure.py` | `generated_docs/run_summary.json` has the same key set and value types as the golden file |

| Name | Purpose | Invocation | Env vars | Writes | Workflow |
|---|---|---|---|---|---|
| `scripts/run_6_gates.sh` | Orchestrates the six gates above | `bash scripts/run_6_gates.sh` | none required. Gate 6 sets `SMARTSHEET_API_TOKEN` (blank), `TEST_MODE`, `SKIP_UPLOAD` for its one process only | local files only (`generated_docs/` from the Gate 6 synthetic run). Gate 6 runs with a blank Smartsheet token, `TEST_MODE=true` and `SKIP_UPLOAD=true`, so no Smartsheet upload and no Supabase client are expected | none |
| `scripts/check_api_equality.py` | Gate 1: AST name-set equality vs frozen baseline | `python scripts/check_api_equality.py` | none | Read-only (reads source and `tests/golden/baseline_names.json`) | none |
| `scripts/check_facade_completeness.py` | Gate 2: facade allowlist resolves | `python scripts/check_facade_completeness.py` | none | Read-only (imports the facade; reads `tests/golden/facade_allowlist.json`) | none |
| `scripts/check_mypy_delta.sh` | Gate 4: mypy error-line count must not increase. Skips (exit 0) if mypy is missing or no baseline is frozen; fails on an unparseable count | `bash scripts/check_mypy_delta.sh` | none | Read-only (compares to `tests/golden/mypy_baseline*.txt`) | none (CI `python-lint.yml` runs mypy directly, warn-only) |
| `scripts/check_run_summary_structure.py` | Gate 6 comparison: structural diff of `run_summary.json` against `tests/golden/run_summary_baseline.json` | `python scripts/check_run_summary_structure.py` | none | Read-only | none |

---

## Backfills

All three are operator-run, one-shot CLIs. Each writes to Supabase only in the mode described; none
writes to Smartsheet (the two that touch Smartsheet only read).

| Name | Purpose | Invocation | Env vars | Writes | Workflow |
|---|---|---|---|---|---|
| `scripts/backfill_attribution_snapshot.py` | Freezes the current completed-row attribution for one week into `billing_audit.attribution_snapshot` (idempotent, first-write-wins). Exits 5 if feature flag `write_attribution_snapshot` is definitively off, 7 if the flag read failed, 2 if no Supabase client | `python scripts/backfill_attribution_snapshot.py --week=MMDDYY [--wr=WR]` | `SMARTSHEET_API_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; optional `SENTRY_RELEASE`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT` | **Supabase** (via `billing_audit.writer.freeze_row`, which calls the snapshot RPC). Smartsheet is read-only (row fetch) | none |
| `scripts/backfill_claim_time_attribution.py` | Resolves the real claimer of sentinel-frozen rows from four historical sources (row event/state, same-row other role, artifact filenames, hash-history tokens) and, only with explicit approval, writes it back with provenance. Never reads current Smartsheet row state | Dry run (default): `python scripts/backfill_claim_time_attribution.py --wr WR --weeks MMDDYY,MMDDYY`. Apply: add `--apply --i-approved-this`. Other flags: `--roles`, `--sources`, `--report-dir`, `--include-blank-roles` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; optional `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT` | Dry run: **local files** (`generated_docs/own03_backfill_report.{json,csv}`) and Supabase reads. `--apply`: **Supabase** via RPC `billing_audit.backfill_attribution`; it requires an existing dated backup table `billing_audit.attribution_snapshot_backup_<YYYYMMDD>` (exit 3 if absent) and `--i-approved-this` (exit 4 without it). No Smartsheet access | none |
| `scripts/backfill_cell_history_attribution.py` | Last-resort claimer resolver: reads Smartsheet cell history of the role's completion checkbox and name column for candidates the script above left unresolved. Paced and capped | `python scripts/backfill_cell_history_attribution.py --report generated_docs/own03_backfill_report.json` (dry run, default). `--check-backlog` makes zero Smartsheet calls. Other flags: `--wr`, `--weeks`, `--roles`, `--report-dir`, `--max-requests`, `--dry-run`, `--apply`, `--i-approved-this` | `SMARTSHEET_API_TOKEN` (only when candidates are in scope; exit 2 if missing), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; tuning: `CELL_HISTORY_BACKFILL_MAX_REQUESTS`, `CELL_HISTORY_BACKFILL_MAX_ROWS`, `CELL_HISTORY_BACKFILL_PACE_SEC` (default 0.5), `CELL_HISTORY_BACKFILL_MAX_MINUTES` | Dry run: **local files** (`generated_docs/own03_cell_history_report.{json,csv}`); Smartsheet is read-only (`Cells.get_cell_history`, one of two callers in the repo (the other is `pipeline/snapshot_drift.py`) per the script's isolation note). `--apply` reuses the **Supabase** RPC write path of the claim-time script with the same backup-table and approval guards | `cell-history-backfill.yml` (manual dispatch only; passes `--dry-run`, rejects `dry_run=false`, never passes `--apply`; also runs `--check-backlog` with Supabase credentials only) |

---

## Checks and diagnostics

| Name | Purpose | Invocation | Env vars | Writes | Workflow |
|---|---|---|---|---|---|
| `scripts/compare_control_run.py` | Proves a control run (memory flag off) and a shadow run (flag on) produced content-identical Excel files (canonicalized hash keyed by stable file identity) and identical billing-relevant `run_summary.json` fields. Exits non-zero on any FAIL; an empty set is a FAIL, never a vacuous PASS | `python scripts/compare_control_run.py --control-dir D --shadow-dir D --control-summary F --shadow-summary F` | none | Read-only (pure filesystem/JSON comparison; docstring states it does not import the pipeline or touch Smartsheet/Supabase) | none |
| `scripts/mem04_experiment.py` | Operator-run probe that tests whether Smartsheet `rowsModifiedSince` / `ifVersionAfter` surface a row whose only change is a cross-sheet formula recalculation. Two phases (`baseline`, `probe`) and two scenarios, against two disposable sandbox sheets; prints a PASS/FAIL/undetermined verdict | `python scripts/mem04_experiment.py --lookup-sheet-id ID --dependent-sheet-id ID --scenario {blank_lookup,edit_mapping} --phase {baseline,probe} [--out PATH]` | `SMARTSHEET_API_TOKEN` | **local files** only: appends to a JSON cassette (default `tests/fixtures/mem04/mem04_cassette.json`). Smartsheet calls are `Sheets.get_sheet` reads; the script contains no sheet/row/cell/attachment write calls. Not reachable from the pipeline | none |
| `scripts/mem04_passive_compare.py` | Read-only analyst diagnostic: across two observations of the same rows, did content-hash changes touch only formula-derived personnel columns, and did `row_modified_at` advance? Output is counts only | `python scripts/mem04_passive_compare.py --run-a A --run-b B [--source json\|supabase]` (default `json`: A/B are exported file paths; `supabase`: A/B are run ids) | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (only with `--source supabase`) | Read-only (Supabase `select` on `pipeline_memory.row_state`; no writes found) | none |
| `scripts/security-probe.ts` | Live row-level-security / signed-URL probe using only the public anon key and a dedicated pending-role test account. Exits 1 on failure | `npx tsx scripts/security-probe.ts` (deps from `scripts/package.json`) | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_PROBE_PENDING_EMAIL`, `SUPABASE_PROBE_PENDING_PASSWORD` | Read-only against data: the code performs `select` on `artifacts`, a storage fetch, and `signInWithPassword`; no insert/update/delete/upsert calls found. Sign-in creates an auth session for the probe account | none (docstring shows a sample CI step, but no workflow references it) |
| `validate_system_health.py` (repo root) | Daily read-only health check. Always writes `generated_docs/system_health.json` with `overall_status` OK/WARN/CRITICAL, exits 0 when the report was written (the workflow decides pass/fail). Probes facade import in a subprocess, env guardrails (`PARALLEL_WORKERS`, `TIME_BUDGET_MINUTES`), Sentry config | `python validate_system_health.py` | `SMARTSHEET_API_TOKEN`; optional `TARGET_SHEET_ID`, `PARALLEL_WORKERS`, `TIME_BUDGET_MINUTES`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`, `GITHUB_SHA`, `GITHUB_RUN_ID` | **local files** (`system_health.json`) and **Sentry** (when `SENTRY_DSN` set). Smartsheet: at most two read calls (current user, target-sheet metadata at `page_size=1`); no row writes or attachment operations | `system-health-check.yml` |
| `diagnose_pricing_issues.py` (repo root) | Explains why rows with Units Completed checked and valid dates are missing from reports (pricing-related exclusions) | `python diagnose_pricing_issues.py` | `SMARTSHEET_API_TOKEN`; optional `TEST_MODE`, `DEBUG_SAMPLE_ROWS`, `DEBUG_ESSENTIAL_ROWS`, `FILTER_DIAGNOSTICS`, `FOREMAN_DIAGNOSTICS`, `LOG_UNKNOWN_COLUMNS` | **local files** (`generated_docs/pricing_diagnostic_results.json`). Smartsheet is read-only (`Sheets.get_sheet`) | none |
| `analyze_excel_totals.py` (repo root) | Diagnostic for Excel total-price calculation discrepancies; falls back to synthetic data with no token | `python analyze_excel_totals.py` | optional `SMARTSHEET_API_TOKEN`, `TEST_MODE`, `DEBUG_SAMPLE_ROWS`, `FILTER_DIAGNOSTICS` | Read-only: no write calls found in the script; it fetches through helper functions (`discover_source_sheets`, `get_all_source_rows`) <!-- VERIFY: helper write behavior not traced; only the script body was checked for Smartsheet/file write calls --> | none |
| `analyze_specific_excel.py` (repo root) | Opens one hard-coded generated workbook and recomputes its total to find discrepancies. Edit the hard-coded workbook path (default argument of `analyze_excel_file()` and a second filename in `analyze_work_request_data()`) before use | `python analyze_specific_excel.py` | none | Read-only (`openpyxl.load_workbook` on a local file) | none |
| `test_production_reload.py` (repo root) | Manual script (defines no `test_*` functions, and CI runs `pytest tests/` only) that reloads the facade per `RES_GROUPING_MODE` value and runs `group_source_rows` on in-memory sample rows to check helper-row exclusion | `python test_production_reload.py` | sets `RES_GROUPING_MODE`, `SKIP_CELL_HISTORY`, `TEST_MODE` itself | Believed read-only: operates on in-memory rows. It sets `TEST_MODE=false` before importing the facade <!-- VERIFY: whether importing generate_weekly_pdfs with TEST_MODE=false and a real SMARTSHEET_API_TOKEN in the environment performs any Smartsheet or Supabase call at import time was not traced --> | none |
| `run_info.py` (repo root) | Prints usage instructions and validates the local environment (.env presence, token) | `python run_info.py` | `SMARTSHEET_API_TOKEN` (presence check) | Read-only (prints only; no write calls found) | none |
| `verify-azure-setup.sh` (repo root) | Checks that the Azure DevOps mirror files exist and are configured | `bash verify-azure-setup.sh` | none found | Believed read-only <!-- VERIFY: only the head of the script and a grep for write/network commands were checked, not the full body --> | none |

---

## Notion sync

Notion scripts write to Notion only. They need the `notion_client` package.

| Name | Purpose | Invocation | Env vars | Writes | Workflow |
|---|---|---|---|---|---|
| `scripts/notion_setup.py` | One-time bootstrap: creates the four run-log databases (Pipeline Runs, Changelog, Codebase Metrics, Incidents) under a parent Notion page and prints their ids to save as repository secrets | `python scripts/notion_setup.py` | `NOTION_TOKEN`, `NOTION_PARENT_PAGE` | **Notion** (creates databases) | none |
| `scripts/notion_dashboard.py` | Run once after setup: creates an Operations Dashboard child page with KPI callouts, database cross-references, and view guidance; also enhances the databases | `python scripts/notion_dashboard.py` | `NOTION_TOKEN`, `NOTION_PARENT_PAGE`, `NOTION_PIPELINE_DB`, `NOTION_CHANGELOG_DB`, `NOTION_METRICS_DB`, `NOTION_INCIDENTS_DB` | **Notion** (creates a page and appends blocks, adds database properties) | none |
| `scripts/notion_sync.py` | Pushes pipeline run data, recent git commits, and codebase metrics to Notion; updates dashboard KPI blocks unless `--skip-kpi` | `python scripts/notion_sync.py --mode {run,commits,metrics,all} [--since DAYS] [--skip-kpi]` (default mode `all`) | `NOTION_TOKEN`, `NOTION_PIPELINE_DB`, `NOTION_CHANGELOG_DB`, `NOTION_METRICS_DB`, `NOTION_INCIDENTS_DB`; run-mode metrics read from `GITHUB_*` context plus `JOB_STATUS`, `EXECUTION_TYPE`, `DURATION_MINUTES`, `ROWS_FETCHED`, `SHEETS_DISCOVERED`, `GROUPS_TOTAL`, `GROUPS_SKIPPED_NO_TARGET_ROW`, `GROUPS_ERRORED`, `FILES_GENERATED`, `FILES_UPLOADED`, `FILES_SKIPPED`, `HASH_UPDATES`, `API_CALLS`, `AUDIT_RISK_LEVEL`, `VARIANT_BREAKDOWN`, `ERROR_SUMMARY` | **Notion** (`pages.create`, `blocks.update`). Also runs `git log` locally in `commits` mode. No Smartsheet or Supabase access | `weekly-excel-generation.yml` (`--mode run`, a `continue-on-error` step) and `notion-sync.yml` (`--mode "$MODE" --since "$SINCE"`; push, daily cron, manual dispatch; skipped when `NOTION_TOKEN` is unset or the `NOTION_ENABLED` repo variable is `false`) |

---

## Artifact manifest and publishing

| Name | Purpose | Invocation | Env vars | Writes | Workflow |
|---|---|---|---|---|---|
| `scripts/generate_artifact_manifest.py` | Builds a JSON manifest (filename parse, SHA-256, size) of the generated `WR_*.xlsx` files. Its `calculate_file_hash` and `parse_excel_filename` are reused by the publisher | `python scripts/generate_artifact_manifest.py [DOCS_FOLDER] [OUTPUT_FILE]` (defaults `generated_docs`, `artifact_manifest.json`) | none | **local files** (manifest JSON). Reads the Excel files; no external writes | `weekly-excel-generation.yml` (`python scripts/generate_artifact_manifest.py generated_docs artifact_manifest.json`) |
| `scripts/publish_artifacts_to_supabase.py` | Additive post-billing step that uploads generated workbooks to Supabase Storage and upserts `public.artifacts` rows (conflict key `sha256`). Loud-but-non-fatal: catches all exceptions, reports to Sentry and `$GITHUB_STEP_SUMMARY`, and exits 0 | `python scripts/publish_artifacts_to_supabase.py generated_docs` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; optional `TEST_MODE` / `SKIP_UPLOAD` (either truthy skips publishing), `GITHUB_RUN_ID`, `GITHUB_STEP_SUMMARY`, `SENTRY_DSN` | **Supabase** (Storage upload and `artifacts` table upsert) and **Sentry** on failure. Writes a summary to `$GITHUB_STEP_SUMMARY` when set. No Smartsheet access | `weekly-excel-generation.yml` (step with `continue-on-error: true`) |

---

## Cloud-agent install

| Name | Purpose | Invocation | Env vars | Writes | Workflow |
|---|---|---|---|---|---|
| `scripts/cloud-agent-install.sh` | Idempotent bootstrap for Cloud Agent / environment builds: `pip install --user -r requirements.txt`, then `npm ci` (or `npm install`) only for app trees whose `package.json` exists. Replaces the old saved command that `cd`-ed into the removed `portal/` directory | `bash scripts/cloud-agent-install.sh` | none (adds `$HOME/.local/bin` to `PATH`) | **local files** only (installs packages into the user site and `node_modules`); no Smartsheet, Supabase, or Notion access | none <!-- VERIFY: the script is referenced from an external Cloud Agent dashboard setting, which cannot be confirmed from the repository --> |

---

## Other

| Name | Purpose | Invocation | Env vars | Writes | Workflow |
|---|---|---|---|---|---|
| `scripts/generate_runbook_entry.py` | Generates a Docusaurus blog post under `website/blog/` summarizing a push to master (buckets changed files by area, lists commit subjects). Exits 0 with no post when there is nothing to report | `python scripts/generate_runbook_entry.py` (prints `POST_PATH=...` for the workflow) | `GITHUB_EVENT_BEFORE`, `GITHUB_SHA`, `GITHUB_REF_NAME`, `GITHUB_REPOSITORY`, `GITHUB_ACTOR`, `GITHUB_RUN_URL` | **local files** (one Markdown file in `website/blog/`); runs `git` read commands. The workflow, not the script, commits and pushes it | `docs-changelog.yml` (commits the post to master with `[skip ci]`) |
| `cleanup_excels.py` (repo root) | Deletes stale `WR_*.xlsx` in `generated_docs/`, keeping the most recent variant per (WR, week-ending) identity. Safe if the directory is absent | `python cleanup_excels.py` | none | **local files** (deletes files). No external writes | none (referenced in repo guidance docs as a manual cleanup step; no workflow calls it) |
| `audit_billing_changes.py` (repo root) | Not a CLI: has no `__main__` entry. It defines `BillingAudit`, imported by `generate_weekly_pdfs.py` and `pipeline/orchestrate.py` for the price-anomaly audit (LOW/MEDIUM/HIGH risk) | imported, not run directly | `AUDIT_SHEET_ID`, `RATE_SANITY_AUDIT_ENABLED`, `PRICE_VARIANCE_IN_RISK`, `SENTRY_DSN` | **local files** (`generated_docs/audit_state.json`, `generated_docs/risk_trend.json`) and **Sentry**. Smartsheet is read-only (`Sheets.get_sheet`); the audit-sheet logging method builds a row dict but its code states the row creation is a placeholder and performs none | none directly (runs inside `weekly-excel-generation.yml` via the facade; `python-lint.yml` only type-checks it) |
| `generate_weekly_pdfs.py` (repo root) | Production entry point: thin facade over `pipeline/`. Pulls Smartsheet rows, groups by `(WR, week_ending, variant, foreman, dept, job)`, generates Excel, audits, and uploads | `python generate_weekly_pdfs.py` (safe local forms: `SKIP_UPLOAD=true python generate_weekly_pdfs.py`; synthetic: `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py`) | Required `SMARTSHEET_API_TOKEN`; the rest are optional `os.getenv()` flags, cataloged in `.github/prompts/configuration-environment.md` (e.g. `SKIP_UPLOAD`, `TEST_MODE`, `TARGET_SHEET_ID`, `TIME_BUDGET_MINUTES`, `PARALLEL_WORKERS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) | **Smartsheet** (deletes the old row attachment, then uploads the new workbook to the target sheet; suppressed by `SKIP_UPLOAD`), **Supabase** (`billing_audit` and `pipeline_memory` writers, gated by Supabase feature flags and disabled under `TEST_MODE` or without credentials) <!-- VERIFY: the exact set of Supabase tables and flags written per run is documented in docs/ai/architecture.md and was not re-derived here -->, **Sentry**, and **local files** (`generated_docs/`, including `run_summary.json`) | `weekly-excel-generation.yml` (cron roughly every 2 hours on weekdays, plus manual dispatch); `ci-checks.yml` only runs `py_compile` on it |
| `scripts/package.json` / `scripts/package-lock.json` | Not scripts: npm manifest for the TypeScript utilities in `scripts/` (`@supabase/supabase-js`, `tsx`, `typescript`, `@types/node`; private, ESM) | `npm --prefix scripts ci` | none | local `node_modules` only | none |

---

## Module CLIs

### `python -m pipeline.reporting_corrections validate|preview`

Operator tool for the opt-in reporting-corrections feature (re-crediting specific, already-billed
source rows to an approved owner and reporting day without touching raw Smartsheet cell values). The
feature is activated in the pipeline only when `REPORTING_CORRECTIONS_FILE` points at a JSON file
(template: `docs/templates/reporting_corrections.template.json`); unset, every hook is an identity
no-op.

**Zero external writes.** The module's docstring states it never imports a `pipeline_memory` or
`billing_audit` writer and performs no I/O except reading the files named on the command line. The CLI
`main` reads the corrections file, and for `preview` also the optional JSON dumps; it prints results to
stdout and writes nothing. It makes no Smartsheet, Supabase, Notion, or Sentry calls and reads no
credentials.

| Command | Invocation | Behavior | Exit codes (from `main`) |
|---|---|---|---|
| `validate` | `python -m pipeline.reporting_corrections validate --file F` | Loads and schema-validates the corrections file; prints `VALID: N correction(s), M row entr(ies)` or one `INVALID:` line per problem | 0 valid; 2 invalid file |
| `preview` | `python -m pipeline.reporting_corrections preview --file F --rows-json ROWS [--memory-json MEM]` | Validates, then previews how each correction would apply against a private row dump (`--rows-json`, required for `preview`) and an optional memory dump; prints matched/unmatched counts | 0 no blocked cases; 1 at least one blocked correction; 2 invalid file or `--rows-json` missing |

Arguments: `--file` (required for both commands), `--rows-json` (required by `preview`),
`--memory-json` (optional, `preview` only). No environment variables are consumed by the CLI itself.
Row dumps are private operational data: keep them out of the repository and out of logs. Log lines the
module emits carry correction ids, counts and row ids only, never person names.

No workflow calls this CLI.

---

## Related references

- `docs/ai/safe-commands.md` for the full list of safe local commands.
- `docs/ai/architecture.md` for the module map, data stores, and schedule/timeouts.
- `.github/prompts/configuration-environment.md` for the environment-variable catalog.
