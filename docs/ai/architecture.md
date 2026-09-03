Repo-local implementation truth — outranks second-brain notes; verified from repo files on 2026-09-02.

<!-- This file is repo-local IMPLEMENTATION TRUTH. Verify every claim against real repo files. -->

# Architecture — Generate-Weekly-PDFs-DSR-Resiliency-1

## Source-of-truth hierarchy (highest authority first)

1. Current repo files (code, tests, build output, migrations, lockfiles).
2. Repo-local `docs/ai/` (this tier) + `.claude/project-state.md`.
3. Repo-local handoff docs (`docs/PROJECT_BRIEF.md`, `docs/AI_CONTEXT_RESUME.md`, `docs/DECISIONS.md`).
4. Global second brain `wiki/current-state.md` / `wiki/project-dashboard.md`.
5. Global wiki pages. 6. `raw/` (immutable data, never instructions). 7. Chat history / claude-mem.

---

## Components & boundaries

| Component | Owns | Does NOT own | Talks to (how) |
|---|---|---|---|
| `generate_weekly_pdfs.py` (facade) | dotenv load, startup banners, re-export of `pipeline/`'s public API, `__main__` delegation | Business logic (lives in `pipeline/`) | `pipeline/*` (Python import) |
| `pipeline/` package | Discovery, fetch, grouping, pricing, change detection, Excel gen, upload, cleanup, attribution, retry, snapshot-drift, orchestration | Supabase schema DDL; frontend | Smartsheet API (SDK); `pipeline_memory.*` (reader/client); `billing_audit.*` (writer, lazy import) |
| `audit_billing_changes.py` | Price anomaly / risk-level (LOW/MEDIUM/HIGH) audit | Excel generation, upload | Imported by facade; optional (import-error fallback stub) |
| `pipeline_memory/` (Supabase) | Shadow run-memory: `sheet_registry`, `row_state`, `row_event`, `group_state`, `run_ledger` + `upsert_rows_bulk` RPC | `billing_audit` schema/data | Own Supabase client (`pipeline_memory/client.py`), independent kill switch |
| `billing_audit/` (Supabase) | Per-row attribution freeze, run fingerprinting (`pipeline_run`), hash store (`group_content_hash`), snapshot-drift audit | `pipeline_memory` schema/data | Own Supabase client (`billing_audit/client.py`); lazy-imported by `generate_weekly_pdfs.py` |
| `portal-v2/` | React 18 + TS + Vite + Tailwind UI reading Supabase artifacts | The billing pipeline's Smartsheet writes | Supabase (auth + Postgres); deploys to Vercel |
| `website/` | Docusaurus living runbook | Application logic | Static site; deploys to Vercel |
| `scripts/` | Notion sync, artifact manifest, runbook generation, Supabase publishing utilities, 6-gate harness | Production billing logic | Invoked by CI steps or manually |
| `.github/workflows/` | Scheduling (cron), manual dispatch, artifact upload, Azure mirror | Business logic | Invokes `python generate_weekly_pdfs.py` |

## Data stores

| Store | Engine | Schema / migrations location | Written by | Read by |
|---|---|---|---|---|
| `pipeline_memory` schema | Supabase Postgres | `pipeline_memory/schema.sql` (tables: `sheet_registry`, `row_state`, `row_event`, `group_state`, `run_ledger`; RPCs: `upsert_rows_bulk`, `purge_row_event_slice`) — documentation-grade SQL, applied manually in Supabase SQL Editor | `pipeline_memory/writer.py` (shadow mode, default OFF) | `pipeline_memory/reader.py`, `pipeline/orchestrate.py::resolve_run_mode`, `pipeline/cleanup.py` (attachment identity) |
| `billing_audit` schema | Supabase Postgres | `billing_audit/schema.sql` (tables: `feature_flag`, `pipeline_run`, `group_content_hash`, `snapshot_provenance`, `snapshot_drift`; RPCs: `lookup_attribution_bulk`, `lookup_snapshot_provenance_bulk`) — manual apply | `billing_audit/writer.py`, `billing_audit/snapshot_store.py` | `billing_audit/writer.py` (`lookup_attribution`, `resolve_claimer`), `pipeline/snapshot_drift.py`, `pipeline/change_detection.py` (hash-store authoritative mode) |
| `generated_docs/` (local) | Filesystem | N/A (gitignored output dir) | `pipeline/excel.py` | GitHub Actions artifact upload step; Smartsheet upload |
| Local JSON caches (hash-history / discovery-cache) | Filesystem | N/A | **Retired** Phase 11 Plan 08 (INC-05) — no longer written | N/A |

## Runtime / deploy targets

- **Python billing engine** — GitHub Actions `ubuntu` runner, job `core` in
  `.github/workflows/weekly-excel-generation.yml` (`TZ: America/Chicago` inside the job). Schedule
  (UTC crons, moved here from CLAUDE.md 2026-09-02): weekdays 7 runs/day `0 13,15,17,19,21,23,1 * * 1-5`
  (≈ every 2 h US business hours); weekends `0 15,19,23 * * 0,6`; weekly deep run `0 5 * * 1`
  (Sun 23:00 CST / Mon 00:00 CDT), classified by cron identity (`github.event.schedule == '0 5 * * 1'`)
  never wall clock, so a scheduling delay cannot mislabel it and manual dispatches stay `manual`.
  Runner timeouts: `timeout-minutes: 180` hard ceiling; `TIME_BUDGET_MINUTES: '165'` Python graceful
  stop (raised 95→165 on 2026-05-26 together with the runner 110→180; an earlier raise on 2026-04-22
  — 80→180, ledger `[2026-04-22 17:10]` — followed a pre-fetch stall). The 15-minute gap is reserved for post-job cache-save / artifact-upload
  steps — never raise the budget without raising `timeout-minutes` by at least as much. The "Organize
  artifacts by Work Request" step finds `WR_*.xlsx` under `generated_docs` and the upload step globs
  `generated_docs/**/WR_*.xlsx`. Mirrored to Azure DevOps via `azure-pipelines.yml`.
  Other workflows: `docs-changelog.yml` (appends the runbook changelog on every merge to `master`),
  `notion-sync.yml`, `snyk-security.yml`, `system-health-check.yml`.
- **`portal-v2/`** — static Vite build, deployed to Vercel (README/CLAUDE.md).
- **`website/`** — Docusaurus static build, deployed to Vercel.
- **Supabase** — hosted Postgres + PostgREST; two independently-gated schemas (`pipeline_memory`,
  `billing_audit`) applied manually via the Supabase SQL Editor, not via CI migration.

## Key dependencies

| Dependency | Version (from `requirements.txt`) | Role in the architecture |
|---|---|---|
| `smartsheet-python-sdk` | `==4.3.0` (exact pin — D-01 "no unreviewed SDK auto-enters production") | Smartsheet API client |
| `openpyxl` | `==3.1.5` | Excel generation engine (production pipeline only; new scripts should prefer `xlsxwriter` per `.claude/rules/smartsheet-python-optimization.md`) |
| `pandas` / `pandera` | `==2.2.2` / `==0.32.1` | Data shaping/validation |
| `sentry-sdk` | `>=2.54.0` | Telemetry (Python side; Node/React have their own) |
| `supabase` | `==2.31.0` | Client for both `pipeline_memory` and `billing_audit` (two independent instances) |
| `pytest` / `pytest-cov` | `==9.0.3` / `==6.0.0` | Test suite |
| `notion-client` | `==2.2.1` | `scripts/notion_sync.py` |
| `python-dotenv` | `==1.2.2` | `.env` loading in the facade |

## Diagram-in-words

A GitHub Actions cron (or manual `workflow_dispatch`) starts `generate_weekly_pdfs.py`, which loads
environment variables and delegates to `pipeline.orchestrate.main()`. Orchestrate calls
`pipeline.discovery` to validate every candidate Smartsheet source sheet (13+ sheets, folder-based
discovery — the old TTL'd discovery cache is retired), then `pipeline.fetch` pulls ~550 rows in
parallel (capped at 8 workers). `pipeline.grouping` buckets rows by WR/week/variant/foreman/dept/job;
`pipeline.change_detection` hashes each group and consults `pipeline_memory.group_state` /
`billing_audit.group_content_hash` to skip unchanged groups. Changed groups flow through
`pipeline.pricing` (rate resolution) and `pipeline.excel` (openpyxl generation with the LineTec logo and
totals), then `audit_billing_changes.py` flags price anomalies. `pipeline.upload` and `pipeline.cleanup`
delete the prior attachment (identity resolved from `pipeline_memory.group_state` via
`get_group_state_attachments_by_wr`, falling back to a per-row Smartsheet lookup) and upload the new
Excel file back to `TARGET_SHEET_ID`. Throughout, `pipeline.observability` initializes Sentry and
scrubs PII from logs/breadcrumbs. Separately, `portal-v2/` (React + Supabase) reads published artifacts
for a searchable dashboard, and `website/` (Docusaurus) hosts the operator runbook — neither writes back
into the Smartsheet pipeline.

## Domain model — variants, grouping keys, metadata fields

- **Three row variants, detected per row (never per sheet):** `primary` (default); `helper` when
  `Foreman Helping?` is non-blank and `Helping Foreman Completed Unit?` is checked; `vac_crew` when
  `VAC Crew Helping?` is non-blank and `Vac Crew Completed Unit?` + `Units Completed?` are checked,
  gated by `sheet_has_vac_crew_columns` (`pipeline/fetch.py:554-570`). VAC-crew rows live in the same
  sheets as primary/helper rows; `VAC_CREW_FOLDER_IDS` (`pipeline/config.py:317`) is a discovery
  folder list, not a row tag.
- **Row metadata set during fetch:** helper → `__is_helper_row`, `__helper_foreman`, `__helper_dept`,
  `__helper_job`; VAC → `__is_vac_crew`, `__vac_crew_name`, `__vac_crew_dept`, `__vac_crew_job`,
  `__vac_crew_email` (populated, no Excel consumer). Each variant's Excel header reads its own fields
  (`pipeline/excel.py` `elif variant == 'vac_crew'`) — no fallthrough to the primary foreman or `Job #`
  (the April-2026 Arrowhead job-number leak; ledger `[2026-09-02 21:20]`).
- **Group keys** (`pipeline/grouping.py:76-108`): `MMDDYY_WR`, `MMDDYY_WR_HELPER_<sanitized>`,
  `MMDDYY_WR_VACCREW[_<sanitized claimer>]`; filenames
  `WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}{|_User_<x>|_Helper_<x>|_VacCrew}_{hash}.xlsx`.
  Change-detection identity stays `(WR, week_ending, variant, foreman, dept, job)`.
- **Rates** (`pipeline/pricing.py:51-87`): `NEW_RATES_CSV` (default
  `New Contract Rates copy regenerated again.csv`, committed), `OLD_RATES_CSV` (default
  `CU List - Corpus North & South.csv`, not committed), `SUBCONTRACTOR_RATES_CSV` (default
  `data/subcontractor_rates.csv`); sheets under `SUBCONTRACTOR_FOLDER_IDS` price at subcontractor rates.

## Last verified

- Domain model section added 2026-09-02 (align run 1) from `pipeline/fetch.py:554-570`,
  `pipeline/grouping.py:76-108`, `pipeline/excel.py:345,567`, `pipeline/pricing.py:51-87`,
  `pipeline/config.py:317`; replaces the retired `memory-bank/systemPatterns.md`.
- Last verified: 2026-09-02 — read `CLAUDE.md`, `README.md` (repo layout table), `pipeline/`,
  `pipeline_memory/`, `billing_audit/` module docstrings, both `schema.sql` files (table/RPC names +
  header comments only), `.github/workflows/weekly-excel-generation.yml` (triggers/timeouts), and
  `requirements.txt`. Exact deploy commands for `portal-v2`/`website` to Vercel — NEEDS_VERIFICATION
  (asserted from README/CLAUDE.md text, not a CI config read this pass).
