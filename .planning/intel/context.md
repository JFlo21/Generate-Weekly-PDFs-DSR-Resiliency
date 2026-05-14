# Context

Running notes synthesized from DOC-class sources in the ingest set,
keyed by topic and attributed to each source.

---

## Project overview / mission

> source: `memory-bank/projectbrief.md`,
> `CLAUDE.md` (Project Summary), `README.md`,
> `memory-bank/productContext.md`

The repository's primary production workflow is a Python billing
automation pipeline: data is fetched from Smartsheet, rows are
filtered and grouped by billing logic, Excel workbooks are
generated, and the finished files are uploaded back to Smartsheet
as attachments. The main workflow processes roughly 550 rows
across 13+ sheets on a scheduled basis. Three Excel variants are
produced: **primary**, **helper** (one per Helping Foreman per
WR per week), and **VAC crew**. Supabase is used in `portal-v2`,
not as the core destination for the main data pipeline.

## Repository layout (3 coupled components)

> source: `CLAUDE.md` (Repository Layout),
> `.github/copilot-instructions.md`,
> `.github/instructions/copilot-setup.instructions.md`,
> `website/docs/runbook/overview.md`

1. **`generate_weekly_pdfs.py`** — Python billing engine
   (~3100 lines, production entry point). Processes ~550 rows
   across 13+ Smartsheet source sheets, groups by Work
   Request + week ending, generates styled Excel via
   `openpyxl`, uploads attachments. Sibling
   `audit_billing_changes.py` (price anomaly / risk-level
   detection) is imported by the main script.
2. **`portal/`** — Legacy Express backend (Node 20+, CommonJS).
   Serves artifact-viewing API (GitHub Actions artifact ZIPs
   → Excel preview), session auth with CSRF, SSE
   run-polling. Entry: `portal/server.js`.
3. **`portal-v2/`** — Modern React 18 + TypeScript + Vite +
   Tailwind + Supabase frontend. Proxies `/api`, `/auth`,
   `/csrf-token`, `/health` to the Express backend during
   dev; deploys to Vercel.

Also present: **`website/`** (Docusaurus living runbook,
deploys to Vercel), **`scripts/`** (Notion sync + runbook +
manifest utilities), **`tests/`** (pytest suite).

## Data pipeline architecture

> source: `CLAUDE.md` (Data Pipeline Architecture),
> `memory-bank/systemPatterns.md`,
> `memory-bank/techContext.md`,
> `.github/prompts/architecture-analysis.md`,
> `website/docs/runbook/overview.md`,
> `website/docs/runbook/python-modules.md`

```
Smartsheet API
  ↓ (folder-based discovery, cached in
  ↓  generated_docs/discovery_cache.json for DISCOVERY_CACHE_TTL_MIN
  ↓  minutes — default 7 days)
Auto-discover source sheets → validate column mappings
  ↓
Fetch rows in parallel (ThreadPoolExecutor, PARALLEL_WORKERS ≤ 8)
  ↓
Filter + group by (WR, week_ending, variant, foreman, dept, job)
  ↓
Pre-fetch target-row attachments (sub-budget
  ATTACHMENT_PREFETCH_MAX_MINUTES, per-future
  ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC)
  ↓
Change detection: SHA256 hash per group key →
  skip unchanged (generated_docs/hash_history.json,
  capped at 1000 entries)
  ↓
Excel generation (openpyxl) — logo, headers, formatting, totals
  ↓
Audit (audit_billing_changes.py) — LOW/MEDIUM/HIGH risk
  ↓
Upload back to TARGET_SHEET_ID (parallel; delete old attachment,
  then upload)
```

## Environment variable inventory

> source: `website/docs/reference/environment.md`,
> `.github/prompts/configuration-environment.md`,
> `CLAUDE.md` (Configuration section),
> `.github/instructions/copilot-setup.instructions.md`

- Required: `SMARTSHEET_API_TOKEN`.
- Commonly touched: `TARGET_SHEET_ID` (default
  `5723337641643908`), `AUDIT_SHEET_ID`, `SENTRY_DSN`,
  `SKIP_UPLOAD`, `SKIP_CELL_HISTORY`, `RES_GROUPING_MODE`
  (default `both`), `TEST_MODE`, `FORCE_GENERATION`,
  `WR_FILTER`, `MAX_GROUPS`, `RESET_HASH_HISTORY`,
  `REGEN_WEEKS`, `RESET_WR_LIST`, `KEEP_HISTORICAL_WEEKS`,
  `DISCOVERY_CACHE_TTL_MIN`, `USE_DISCOVERY_CACHE`,
  `EXTENDED_CHANGE_DETECTION`.
- Time-budget family: `TIME_BUDGET_MINUTES` (default 0
  local / 180 in workflow), `ATTACHMENT_PREFETCH_MAX_MINUTES`
  (10), `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` (45),
  `ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN` (2).
- Debug flags: `DEBUG_MODE`, `QUIET_LOGGING`,
  `PER_CELL_DEBUG_ENABLED`, `FILTER_DIAGNOSTICS`,
  `FOREMAN_DIAGNOSTICS`, `LOG_UNKNOWN_COLUMNS`,
  `DEBUG_SAMPLE_ROWS`.
- Sentry: `SENTRY_DSN`, `SENTRY_ENABLE_LOGS` (default
  `false`).
- Legacy / retired (workflow pinned to empty,
  see `decisions.md` 2026-04-24 14:30):
  `RATE_CUTOFF_DATE`, `NEW_RATES_CSV`, `OLD_RATES_CSV`.
- Documented but NOT currently consumed by
  `generate_weekly_pdfs.py`: `SKIP_FILE_OPERATIONS`,
  `DRY_RUN_UPLOADS`, `MOCK_SMARTSHEET_UPLOAD` — aspirational.

## Variant detection and grouping keys

> source: `memory-bank/systemPatterns.md`,
> `memory-bank/projectbrief.md`,
> `.github/prompts/data-processing-business-logic.md`,
> `CLAUDE.md`

- Group key includes `foreman, dept, job` for full
  disambiguation.
- Helper variant: requires both `helper_dept` and
  `helper_foreman`; Job # optional. Rows with both
  `Helping Foreman Completed Unit?` and `Units Completed?`
  checked go ONLY into helper Excel, never primary.
- VAC crew variant: requires VAC Crew Helping? populated +
  Vac Crew Completed Unit? + Units Completed? both checked.
  Group key format `{week}_{wr}_VACCREW` does NOT split per
  VAC crew member, so the hash MUST capture per-row VAC crew
  fields (see `decisions.md` 2026-04-22 00:00).

## CI/CD and operations

> source: `.github/instructions/github-actions-ci-cd-best-practices.instructions.md`,
> `website/docs/runbook/workflows.md`,
> `website/docs/runbook/operations.md`,
> `.github/prompts/weekly-release.prompt.md`,
> `docs/update-log-v2-dashboard-fixes.md`

- Primary workflow: `.github/workflows/weekly-excel-generation.yml`.
- Supporting workflows: `docs-changelog.yml` (appends
  runbook changelog on every merge to `master`),
  `notion-sync.yml`, `snyk-security.yml`,
  `system-health-check.yml`,
  `azure-pipelines.yml` (GitHub → Azure DevOps mirror).
- Release-tagging conventions: Conventional Commits
  (`feat:`, `fix:`, `chore:`, `refactor:`), subject ≤ 50
  chars, three-section PR descriptions (Objective / Changes
  Made / Production Safety Check).

## Sentry telemetry

> source: `docs/sentry-implementation.md`, `CLAUDE.md`
> (Architecture Decisions / Sentry Telemetry)

- Sentry wired across Python (`generate_weekly_pdfs.py`),
  Node (`portal/`), and React (`portal-v2/`) with
  source-map upload.
- Privacy guarantee: INFO-path logs that embed row PII are
  *intentionally not captured*. `before_send_log` sanitizer
  is defense-in-depth backstop alongside the
  `SENTRY_ENABLE_LOGS` env gate.
- Render auto-tags `SENTRY_RELEASE` from
  `RENDER_GIT_COMMIT`.

## Azure DevOps mirror

> source: `AZURE_ARCHITECTURE.md`,
> `AZURE_PIPELINE_SETUP.md`,
> `AZURE_QUICKSTART.md`,
> `README_AZURE.md`

The repo's GitHub workflows are mirrored to Azure DevOps via
`.github/workflows/azure-pipelines.yml`. Setup and
architecture are documented in the four AZURE_* files at repo
root; this is a side channel for organizations that require
Azure Pipelines visibility.

## Portal-v2 frontend

> source: `portal-v2/README.md`,
> `website/docs/runbook/portals.md`,
> `docs/update-log-v2-dashboard-fixes.md`

React 18 + TypeScript + Vite + Tailwind + Framer Motion +
Supabase auth/DB. Local dev: `npm run dev` (Vite on :5173,
proxies `/api`/`/auth`/`/csrf-token`/`/health` to Express
on :3000). Deploys to Vercel. `.env.local` needs
`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. RLS
policies and role assignment documented in `portal-v2/README.md`.

## Docusaurus runbook

> source: `website/docs/intro.md`,
> `website/docs/reference/how-this-site-updates.md`,
> `.claude/rules/documentation-maintenance.md`

Living runbook lives in `website/`. `docs-changelog.yml`
appends an auto-stub on every merge to `master`; engineers
expand the stub into a proper synthesized entry (what / why /
how, in present tense, for the on-call engineer reading at 2
AM) before the next release. Validation: `npm run typecheck`
and `npm run build` inside `website/`.

## Memory bank conventions

> source: `memory-bank/projectbrief.md`,
> `memory-bank/productContext.md`,
> `memory-bank/activeContext.md`,
> `memory-bank/systemPatterns.md`,
> `memory-bank/techContext.md`,
> `memory-bank/progress.md`,
> `.github/instructions/memory-bank.instructions.md`

`memory-bank/` is the longer-form project context. Six core
files: `projectbrief.md` (mission), `productContext.md`
(why), `activeContext.md` (now), `systemPatterns.md` (how),
`techContext.md` (stack), `progress.md` (status). The
`activeContext.md` is the rolling status log and currently
notes the Railway-to-Render transition as in-flight.

## Active in-flight work (per memory-bank)

> source: `memory-bank/activeContext.md`,
> `docs/update-log-v2-dashboard-fixes.md`,
> `docs/railway-to-render-transition-plan.md`

- VAC Crew data isolation fixes — completed.
- Railway-to-Render transition — approved plan, pre-
  implementation. Migration phases 0–6 detailed in
  `docs/railway-to-render-transition-plan.md`.
- Dashboard / Artifact Explorer stabilization — recent
  updates in `docs/update-log-v2-dashboard-fixes.md`.
- Arrowhead contract job number handling — referenced as
  area of active attention.

## Critical pitfalls (known footguns)

> source: `CLAUDE.md` (Critical Pitfalls),
> `.github/prompts/change-detection-troubleshooting.md`,
> `.github/prompts/error-handling-resilience.md`,
> `.github/instructions/performance-optimization.instructions.md`

- Hash history is ephemeral in CI — set
  `RESET_HASH_HISTORY=true` to force full regeneration.
- Excel corruption — always use `safe_merge_cells()`; never
  write `oddFooter.right.text`.
- Job # — populated by checking multiple column-name
  variants (`Job #`, `Job#`, `Job Number`, …); do not
  collapse the synonyms.
- GitHub Actions 10-input limit — keep the
  `advanced_options` parser intact.
- Rate limits — don't raise `PARALLEL_WORKERS` above 8.
- Smartsheet `@cell` is UI-only — never write it in Python.

## Coding conventions

> source: `.github/instructions/python.instructions.md`,
> `.github/instructions/nodejs-javascript-vitest.instructions.md`,
> `.github/instructions/taming-copilot.instructions.md`,
> `.github/instructions/ai-agent-best-practices.instructions.md`,
> `.github/instructions/copilot-thought-logging.instructions.md`

- Python: PEP 8, type hints, 4-space indent, ≤79 char lines,
  PEP 257 docstrings.
- Node.js: `async`/`await` only; prefer `undefined` over
  `null`; prefer functions over classes; minimize external
  deps. `portal/` CommonJS; `portal-v2/` ESM.
- Tests (Node): Vitest. Never change production code to
  make it testable.
- AI-agent rules of engagement: minimal, surgical changes;
  preserve existing structure; integrate rather than replace.

## Testing strategy

> source: `.github/prompts/testing-and-validation.md`,
> `.github/instructions/copilot-setup.instructions.md`

- Authoritative: `pytest tests/ -v`.
- Single-file: `pytest tests/test_subcontractor_pricing.py -v`.
- Single-test: `pytest tests/test_vac_crew.py::test_name -v`.
- With coverage: `pytest tests/ --cov`.
- Syntax check: `python -m py_compile generate_weekly_pdfs.py`.
- Aspirational `uv` migration is not wired up.

## Smartsheet debugger agent

> source: `.github/agents/smartsheet-debugger.agent.md`

Pipeline-debugging specialist agent definition lives at
`.github/agents/smartsheet-debugger.agent.md` and is the
designated routing target for any incident triage involving
the Smartsheet billing pipeline.

## Helper scripts inventory

> source: `website/docs/runbook/scripts.md`,
> `website/docs/runbook/python-modules.md`

- `audit_billing_changes.py` — price anomaly /
  risk-level detection.
- `cleanup_excels.py` — generated-docs maintenance.
- `diagnose_pricing_issues.py` — diagnostics.
- `run_info.py` — shows available scripts.
- `scripts/` directory — Notion sync + runbook + manifest
  utilities.

## Artifact preservation and dashboard surface

> source: `.github/instructions/artifact-preservation.instructions.md`,
> `website/docs/runbook/portals.md`,
> `docs/update-log-v2-dashboard-fixes.md`,
> `docs/railway-to-render-transition-plan.md` (§7)

Generated Excel files are uploaded to Smartsheet as
attachments AND retained as GitHub Actions artifacts. The
portal surface (`portal/` API + `portal-v2/` dashboard) is
the operator's window into both stores. The Railway → Render
migration plan ships a redesigned Artifact Explorer that
makes those artifacts visually first-class (see
`requirements.md` REQ-artifact-explorer-v1).
