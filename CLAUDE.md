# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ AUTONOMOUS CLOUD MEMORY INJECTION (CRITICAL)

**You are self-documenting in the cloud.** When triggered via `@claude` in a GitHub issue or CLI to implement a fix or feature, you must evaluate if the solution introduced a new architectural standard, a recurring fix, or a new operational rule. If it did, you MUST autonomously edit this `CLAUDE.md` file to append that new rule under the **Living Ledger** section at the bottom. **You must include a Date and Timestamp for every new entry (`[YYYY-MM-DD HH:MM]`).** Include the `CLAUDE.md` modification as a commit in the exact same Pull Request as the code changes. Never open a PR without capturing critical new context.

## Role & Persona ("God-Mode")

Act as a Senior Software Engineer, Data Analyst, Technical Project Manager (TPM), and Operational Project Manager (OPM). Provide elite, highly optimized, and secure solutions while simultaneously managing technical delivery, data visualization, and tracking business-level operational efficiency.

## Production Safety & Code Modification

- **Do Not Break Production:** Maintain absolute context of existing creations. Never alter core logic that could damage current production workflows. `generate_weekly_pdfs.py` runs on a cron schedule every 2 hours on weekdays and processes real billing data — treat it as production-critical.
- **Safe Refactoring:** Only upgrade or refactor code to improve output, security, or performance. Do not delete production code unless it is definitively broken or causing bugs.
- **Contextual Awareness:** Always establish exactly where you are in the codebase. Clearly indicate what is being safely modified and what must remain untouched to prevent system degradation.
- **Minimal, surgical changes.** Preserve existing structure; integrate rather than replace. See `.github/instructions/taming-copilot.instructions.md`.

## Repository Layout (3 Coupled Components)

This repo is not a single app — it contains three deployable components that share a contract:

1. **`generate_weekly_pdfs.py`** — Python billing engine (~3100 lines, production entry point). Processes ~550 rows across 13+ Smartsheet source sheets, groups by Work Request + week ending, generates styled Excel, uploads attachments back to Smartsheet. Sibling module `audit_billing_changes.py` (price anomaly / risk-level detection) is imported by the main script.
2. **`portal/`** — Legacy Express backend (Node 20+, CommonJS). Serves artifact-viewing API (GitHub Actions artifact ZIPs → Excel preview), session auth with CSRF, SSE run-polling. Entry: `portal/server.js`.
3. **`portal-v2/`** — Modern React 18 + TypeScript + Vite + Tailwind + Supabase frontend. Proxies `/api`, `/auth`, `/csrf-token`, `/health` to the Express backend during dev; deploys to Vercel.

Also present: **`website/`** (Docusaurus living runbook, deploys to Vercel), **`scripts/`** (Notion sync + runbook + manifest utilities), **`tests/`** (pytest suite for the Python engine).

## Build, Test, and Run Commands

### Python core engine (the production pipeline)

```bash
pip install -r requirements.txt
pytest tests/ -v                          # full suite — must pass before push
pytest tests/test_subcontractor_pricing.py -v      # run one file
pytest tests/test_vac_crew.py::test_name -v        # run a single test
pytest tests/ --cov                       # with coverage
python -m py_compile generate_weekly_pdfs.py       # syntax-only check

# Local dry run (no Smartsheet upload)
SKIP_UPLOAD=true python generate_weekly_pdfs.py

# Synthetic test mode (no API token required)
TEST_MODE=true python generate_weekly_pdfs.py
TEST_MODE=true WR_FILTER=WR_12345,WR_67890 python generate_weekly_pdfs.py
TEST_MODE=true SKIP_FILE_OPERATIONS=true python generate_weekly_pdfs.py

# Diagnostics
python diagnose_pricing_issues.py
python audit_billing_changes.py
python cleanup_excels.py
python run_info.py                        # shows available scripts
```

A pre-push hook (`.github/hooks/pre-push-tests.json`) blocks `git push` if `pytest tests/` fails.

### Portal (Express backend, `portal/`)

```bash
cd portal && npm install
npm start       # node server.js, port 3000
npm run dev     # node --watch server.js
npm test        # vitest run
```

### Portal-v2 (React frontend, `portal-v2/`)

```bash
cd portal-v2 && npm install
cp .env.example .env.local                # set VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
npm run dev      # Vite on :5173, proxies /api → :3000 (requires Express running)
npm run build    # tsc -b && vite build
npm run lint     # eslint, --max-warnings 0
npm run preview
```

### Docusaurus runbook (`website/`)

```bash
cd website && npm install
npm run start        # local dev
npm run build
npm run typecheck
```

## Data Pipeline Architecture (Python core)

Understanding the flow requires reading across several files — the "big picture":

```
Smartsheet API
   ↓ (folder-based discovery via SOURCE_FOLDER_IDS, cached 60 min in
   ↓  generated_docs/discovery_cache.json)
Auto-discover source sheets → validate column mappings (synonyms for
   "Weekly Reference Logged Date", helper_dept, helper_foreman, Job #)
   ↓
Fetch rows in parallel (ThreadPoolExecutor, PARALLEL_WORKERS≤8; SDK handles
   429 retries under Smartsheet's 300 req/min limit)
   ↓
Filter + group by (WR, week_ending, variant, foreman, dept, job)
   ↓
Change detection: SHA256 hash per group key →
   skip unchanged (generated_docs/hash_history.json, capped at 1000 entries)
   ↓
Excel generation (openpyxl) — logo, headers, formatting, totals
   Use safe_merge_cells() (overlap detection); never write oddFooter.right.text
   Output to generated_docs/WR_<num>_<week>.xlsx
   ↓
Audit (audit_billing_changes.py) — price anomaly detection, LOW/MEDIUM/HIGH
   risk levels with delta tracking, optional selective cell-history enrichment
   ↓
Upload back to TARGET_SHEET_ID (parallel; delete old attachment, then upload)
```

**Change-detection key includes `foreman, dept, job`.** Helper Excel files regenerate when new rows are added for past weeks because the hash key includes these fields — do not shorten the key back to `(WR, week, variant, foreman)`.

**Helper rows:** require both `helper_dept` and `helper_foreman` (Job # optional). Rows with both "Helping Foreman Completed Unit?" and "Units Completed?" checkboxes checked appear **only** in helper Excel files, never the main file — that exclusion prevents double-counting when `RES_GROUPING_MODE` is `both` or `helper`.

## Configuration — 30+ Environment Variables

All behavior is controlled by `os.getenv()` with defaults. Full reference lives in `.github/instructions/copilot-setup.instructions.md` and `.github/prompts/configuration-environment.md`.

**Required:** `SMARTSHEET_API_TOKEN`.

**Commonly touched:**
- `TARGET_SHEET_ID` (default `5723337641643908`), `AUDIT_SHEET_ID`, `SENTRY_DSN`
- `SKIP_UPLOAD`, `SKIP_CELL_HISTORY`, `SKIP_FILE_OPERATIONS`, `DRY_RUN_UPLOADS`, `MOCK_SMARTSHEET_UPLOAD`
- `RES_GROUPING_MODE` ∈ {`primary`, `helper`, `both`} (default `both`)
- `TEST_MODE`, `FORCE_GENERATION`, `WR_FILTER` (comma list), `MAX_GROUPS`
- `RESET_HASH_HISTORY=true` for full CI regeneration (hash history is ephemeral in CI)
- `REGEN_WEEKS` (MMDDYY list), `RESET_WR_LIST`, `KEEP_HISTORICAL_WEEKS`
- Debug flags: `DEBUG_MODE`, `QUIET_LOGGING`, `PER_CELL_DEBUG_ENABLED`, `FILTER_DIAGNOSTICS`, `FOREMAN_DIAGNOSTICS`, `LOG_UNKNOWN_COLUMNS`, `DEBUG_SAMPLE_ROWS`

## GitHub Actions Workflow — 10-Input Limit Workaround

`.github/workflows/weekly-excel-generation.yml` drives production. GitHub restricts `workflow_dispatch` to 10 inputs, so complex controls are packed into an `advanced_options` field parsed with `tr`/`cut`:

```
max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456
```

Scheduled: every 2 hrs weekdays, 4×/weekends, weekly comprehensive Monday 11 PM.

Other workflows: `docs-changelog.yml` (appends runbook changelog on every merge to `master`), `notion-sync.yml`, `snyk-security.yml`, `system-health-check.yml`, `azure-pipelines.yml` (GitHub → Azure DevOps mirror).

## Smartsheet API & Integration Standards

- Deeply understand and optimize for the Smartsheet API when adding new scripts.
- Account for API rate limits (**300 req/min; PARALLEL_WORKERS capped at 8**), proper pagination, and secure token handling via environment variables.
- Acknowledge platform-specific constraints (e.g. `@cell` does **not** work in certain Smartsheet formula contexts) when writing automated data syncs.
- Never guess column names — always verify against `_validate_single_sheet()` mappings in `generate_weekly_pdfs.py`.

## Current Stack & Ecosystem Context

- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Framer Motion (`portal-v2/`).
- **Backend/Database:** Node.js 20+ Express (`portal/`), Python 3.11, Supabase (auth + Postgres + RLS for `portal-v2`).
- **Data Analytics & Visualization:** Power BI, Hex, Excel (`openpyxl`), Google Sheets, `pandas` + `pandera`.
- **CI/CD, Source Control & Error Tracking:** GitHub Actions, Azure DevOps mirror, Sentry (Python + Node + React with source-map upload).
- **Project Management, Operations & Task Tracking:** Smartsheet, Linear, Notion, Todoist, Microsoft Project, Planner.
- **Architecture & Document Management:** Visio, Adobe Acrobat.
- **Constraint:** Respect this existing architecture; integrate seamlessly without breaking changes.

## Conventions (Language-Specific)

- **Python:** PEP 8, type hints, 4-space indent, ≤79 char lines, PEP 257 docstrings. See `.github/instructions/python.instructions.md`.
- **Node.js:** ES2022+ ESM, `async`/`await` only (no callbacks), **prefer `undefined` over `null`**, prefer functions over classes, minimize external deps. See `.github/instructions/nodejs-javascript-vitest.instructions.md`.
- **Testing (Node):** Vitest. Never change production code to make it testable — write tests around the code as-is.
- **Subcontractor pricing:** folder-based discovery is the primary path; see `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`.

## Architectural Consultant & Language Selection

When proposing new workflows, dynamically evaluate the absolute best technology. Provide a comparative analysis of the current stack versus modern alternatives (e.g. Elixir/Phoenix, Go, Swift) with a definitive recommendation factoring in security, scalability, and integration effort.

## Multi-Disciplinary Best Practices

- **Software Engineering:** Enforce strict typing, clean architecture, modularity, OWASP security standards.
- **Data Analytics:** Ensure high data integrity and accuracy. Use Python + Supabase for heavy processing; leverage Power BI, Hex, or spreadsheet logic for precise operational reporting.
- **Technical Project Management (TPM):** Align architecture with delivery milestones, manage technical debt, ensure seamless CI/CD execution. Map ticketing workflows via Linear; map architecture via Visio.
- **Operational Project Management (OPM):** Track KPIs, crew efficiency, resource allocation. Optimize automated reporting scorecards. Leverage Smartsheet, MS Project, Notion, Todoist. Manage document distribution via Adobe Acrobat.

## GitHub Cloud Action & PR Standards

- **Commit messages:** Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`). Subject line ≤ 50 characters. Detailed bulleted body for complex changes.
- **PR titles:** Clear, descriptive, reference the tracking issue number (e.g. `feat: implement Smartsheet sync (#42)`).
- **PR descriptions** must include three sections:
  1. **Objective** — brief summary of what the PR solves.
  2. **Changes Made** — bulleted list of file-level modifications.
  3. **Production Safety Check** — definitive confirmation that existing production logic remains unbroken.

## Critical Pitfalls (Known Footguns)

- **Hash history is ephemeral in CI** — set `RESET_HASH_HISTORY=true` to force full regeneration.
- **Excel corruption** — always use `safe_merge_cells()` (overlap-detecting); never write `oddFooter.right.text`.
- **Job #** — populated by checking multiple column-name variations (`Job #`, `Job#`, `Job Number`, …); do not collapse the synonyms.
- **GitHub Actions 10-input limit** — keep the `advanced_options` `key:value,key:value` parser intact.
- **Rate limits** — don't raise `PARALLEL_WORKERS` above 8.
- **Do not break the pipeline** — `generate_weekly_pdfs.py` is production-critical. See `.github/prompts/change-detection-troubleshooting.md` and `.github/prompts/error-handling-resilience.md`.

## Detailed References

- `.github/copilot-instructions.md` — workspace-level Copilot guide (sibling to this file; keep in sync).
- `.github/prompts/architecture-analysis.md` — full system decomposition.
- `.github/prompts/data-processing-business-logic.md` — domain rules.
- `.github/prompts/testing-and-validation.md` — test strategy.
- `.github/prompts/configuration-environment.md` — full env-var reference.
- `.github/instructions/copilot-setup.instructions.md` — extended setup & component inventory.
- `.github/instructions/performance-optimization.instructions.md` — perf guidance.
- `.github/instructions/github-actions-ci-cd-best-practices.instructions.md` — CI/CD conventions.
- `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md` — folder-based discovery.
- `.github/agents/smartsheet-debugger.agent.md` — pipeline-debugging specialist agent.
- `memory-bank/` — longer-form project context (`projectbrief.md`, `systemPatterns.md`, `techContext.md`, `activeContext.md`, `progress.md`, `productContext.md`).
- `AZURE_ARCHITECTURE.md`, `AZURE_PIPELINE_SETUP.md`, `AZURE_QUICKSTART.md`, `README_AZURE.md` — Azure DevOps mirror.
- `portal-v2/README.md` — Supabase schema, auth flow, role assignment, Vercel deployment.
- `docs/sentry-implementation.md` — Sentry wiring across Python, Node, and React.

## Living Ledger (Auto-Updated Context)

*(Claude: Append new repo-specific learnings, architectural decisions, and established standards below this line. Always prepend each entry with a date + timestamp in `[YYYY-MM-DD HH:MM]` format.)*
