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

- **Python billing engine** — runs on GitHub Actions runners (`ubuntu`, per `weekly-excel-generation.yml`),
  scheduled cron (weekdays every ~2h, weekends 3x/day, weekly deep run) + `workflow_dispatch`.
  `timeout-minutes: 180` job ceiling; mirrored to Azure DevOps via `azure-pipelines.yml`.
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

## Last verified

- Last verified: 2026-09-02 — read `CLAUDE.md`, `README.md` (repo layout table), `pipeline/`,
  `pipeline_memory/`, `billing_audit/` module docstrings, both `schema.sql` files (table/RPC names +
  header comments only), `.github/workflows/weekly-excel-generation.yml` (triggers/timeouts), and
  `requirements.txt`. Exact deploy commands for `portal-v2`/`website` to Vercel — NEEDS_VERIFICATION
  (asserted from README/CLAUDE.md text, not a CI config read this pass).
