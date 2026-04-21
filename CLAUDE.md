# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary — Billing Automation & Excel Generation

### Project Overview
This repository's primary production workflow is a Python-based
billing automation pipeline: data is fetched from Smartsheet, rows
are filtered and grouped by billing logic, Excel workbooks are
generated, and the finished files are uploaded back to Smartsheet as
attachments. The main workflow processes roughly 550 rows across 13+
sheets on a scheduled basis. Supabase is used in `portal-v2`, not as
the core destination for the repository's main data pipeline.

### Tech Stack & Constraints
* Primary Language: Python 3.10+
* Core Production Systems: Smartsheet API, Excel generation
  (`openpyxl`), GitHub Actions, Azure DevOps
* Additional App Surfaces: `portal/` (legacy Express backend) and
  `portal-v2/` (React + TypeScript frontend using Supabase)
* Task Automation: Node.js & npm (for portal apps and utility
  scripts)
* Documentation: Docusaurus (runbook in `website/`)
* Monitoring: Sentry (Python + Node + React)
* Constraint: Do not suggest replacing or redesigning the core
  Python/Smartsheet billing workflow unless explicitly requested.
  Preserve the existing Smartsheet → Excel → Smartsheet attachment
  pipeline.

### Architecture Decisions
* Preserve the production billing pipeline: Smartsheet API → row
  filtering → WR grouping → Excel generation → upload.
* Keep changes additive and operationally safe: optimize within the
  existing workflow rather than replacing the transport or storage
  model described by the production scripts.
* Sentry Telemetry: Environment and release variables must be
  standardized. Wrap new optimizations in Sentry error handling for
  instant visibility and rollback.

### Development Conventions
* Code Style: Adhere to strict PEP 8 guidelines. Enforce comprehensive
  type hinting.
* Additive Logic Only: Improve or extend the existing billing
  workflow without changing its fundamental behavior unless
  explicitly requested.
* Release Tagging: Updates must be compatible with GitHub Actions
  release workflows.

### Boundaries & Guardrails
* Smartsheet Formula Restriction: NEVER use, write, or suggest the
  `@cell` function when writing Python scripts or interacting with
  the Smartsheet API. It is strictly an internal UI formula and will
  fail.
* Data Integrity: Do not drop tables or overwrite production logic
  without explicit verification.

### Validation Commands
Current (authoritative):
* Run Tests: `pytest tests/ -v`
* Syntax check: `python -m py_compile generate_weekly_pdfs.py`

Aspirational (future `uv` migration — not yet wired up):
* `uv run pytest tests/`
* `uv run ruff check .`
* `uv run mypy .`

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

# Diagnostics
python diagnose_pricing_issues.py
python audit_billing_changes.py
python cleanup_excels.py
python run_info.py                        # shows available scripts
```

`.github/hooks/pre-push-tests.json` is a **Claude Code hook** (not a standard Git `pre-push` hook). When running Claude Code, it denies the terminal `git push` tool if `pytest tests/` fails. Developers pushing from a normal shell are not gated by it — run `pytest tests/` manually before pushing.

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
   ↓ (folder-based discovery via SUBCONTRACTOR_FOLDER_IDS,
   ↓  ORIGINAL_CONTRACT_FOLDER_IDS, and VAC_CREW_FOLDER_IDS, cached for
   ↓  DISCOVERY_CACHE_TTL_MIN minutes — default 10080 = 7 days — in
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
   Output to generated_docs/WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}{variant_suffix}_{hash}.xlsx
   (variant_suffix ∈ {``, `_User_<foreman>`, `_Helper_<foreman>`, `_VacCrew`};
    the workflow's artifact organizer globs WR_*_WeekEnding_*)
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

**Commonly touched (implemented in `generate_weekly_pdfs.py`):**
- `TARGET_SHEET_ID` (default `5723337641643908`), `AUDIT_SHEET_ID`, `SENTRY_DSN`
- `SKIP_UPLOAD`, `SKIP_CELL_HISTORY`
- `RES_GROUPING_MODE` ∈ {`primary`, `helper`, `both`} (default `both`)
- `TEST_MODE`, `FORCE_GENERATION`, `WR_FILTER` (comma list), `MAX_GROUPS`
- `RESET_HASH_HISTORY=true` for full CI regeneration (hash history is ephemeral in CI)
- `REGEN_WEEKS` (MMDDYY list), `RESET_WR_LIST`, `KEEP_HISTORICAL_WEEKS`
- `DISCOVERY_CACHE_TTL_MIN` (default `10080` = 7 days), `USE_DISCOVERY_CACHE`, `EXTENDED_CHANGE_DETECTION`
- Debug flags: `DEBUG_MODE`, `QUIET_LOGGING`, `PER_CELL_DEBUG_ENABLED`, `FILTER_DIAGNOSTICS`, `FOREMAN_DIAGNOSTICS`, `LOG_UNKNOWN_COLUMNS`, `DEBUG_SAMPLE_ROWS`

**Documented in `.github/prompts/` but not currently consumed by `generate_weekly_pdfs.py`:** `SKIP_FILE_OPERATIONS`, `DRY_RUN_UPLOADS`, `MOCK_SMARTSHEET_UPLOAD`. Treat these as aspirational until they are wired up — setting them today has no effect on the production pipeline.

## GitHub Actions Workflow — `advanced_options` Parser

`.github/workflows/weekly-excel-generation.yml` drives production. The `workflow_dispatch` surface packs rarely-used controls into a single `advanced_options` field parsed with `tr`/`cut` so operators don't have to hunt through a long input list:

```
max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456
```

Do not delete this parser even if the top-level input count is below GitHub's limit today — several operational runbooks depend on this exact `key:value,key:value` format.

**Schedule (UTC crons, `TZ: America/Chicago` inside the job):**
- Weekdays (Mon–Fri): 7 runs/day at UTC `13,15,17,19,21,23,01` (`0 13,15,17,19,21,23,1 * * 1-5`) → roughly every 2 hours during US business hours.
- Weekends (Sat, Sun): 3 runs/day at UTC `15,19,23` (`0 15,19,23 * * 0,6`).
- Weekly deep run: `0 5 * * 1` (UTC Monday 05:00 = Sunday 23:00 CST / Monday 00:00 CDT Central). The job's `if: day==1 && hour==23` guard in Central time is what flips the run into the "weekly comprehensive" branch.

Other workflows: `docs-changelog.yml` (appends runbook changelog on every merge to `master`), `notion-sync.yml`, `snyk-security.yml`, `system-health-check.yml`, `azure-pipelines.yml` (GitHub → Azure DevOps mirror).

## Smartsheet API & Integration Standards

- Deeply understand and optimize for the Smartsheet API when adding new scripts.
- Account for API rate limits (**300 req/min; PARALLEL_WORKERS capped at 8**), proper pagination, and secure token handling via environment variables.
- Acknowledge platform-specific constraints (e.g. `@cell` does **not** work in certain Smartsheet formula contexts) when writing automated data syncs.
- Never guess column names — always verify against `_validate_single_sheet()` mappings in `generate_weekly_pdfs.py`.

## Current Stack & Ecosystem Context

- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Framer Motion (`portal-v2/`).
- **Backend/Database:** Node.js 20+ Express (`portal/`), Python 3.12 in CI (3.11+ locally is fine), Supabase (auth + Postgres + RLS for `portal-v2`).
- **Data Analytics & Visualization:** Power BI, Hex, Excel (`openpyxl`), Google Sheets, `pandas` + `pandera`.
- **CI/CD, Source Control & Error Tracking:** GitHub Actions, Azure DevOps mirror, Sentry (Python + Node + React with source-map upload).
- **Project Management, Operations & Task Tracking:** Smartsheet, Linear, Notion, Todoist, Microsoft Project, Planner.
- **Architecture & Document Management:** Visio, Adobe Acrobat.
- **Constraint:** Respect this existing architecture; integrate seamlessly without breaking changes.

## Conventions (Language-Specific)

- **Python:** PEP 8, type hints, 4-space indent, ≤79 char lines, PEP 257 docstrings. See `.github/instructions/python.instructions.md`.
- **Node.js:** Module system differs by component. **`portal/` is CommonJS** (`"type": "commonjs"`, `require()` / `module.exports`) — do **not** introduce `import`/`export` there. **`portal-v2/` is ES2022+ ESM**. Across both: `async`/`await` only (no callbacks), **prefer `undefined` over `null`**, prefer functions over classes, minimize external deps. See `.github/instructions/nodejs-javascript-vitest.instructions.md`.
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

- [2026-04-17 15:26] Initialized Claude Code workspace layout: added
  `.claude/rules/smartsheet-python-optimization.md` (scope: new scripts
  only — `generate_weekly_pdfs.py` stays on `openpyxl`) and
  `.claude/rules/documentation-maintenance.md` (Docusaurus runbook +
  changelog synthesis, Python/n8n tier boundaries); seeded
  `.claude/commands/` with a `.gitkeep`; prepended `## Project Summary
  — Generate to Excel & Data Sync` block to `CLAUDE.md` (tech stack,
  architecture, conventions, guardrails, validation commands — with
  `uv` flagged aspirational and `pytest tests/ -v` kept authoritative)
  while preserving every pre-existing section verbatim.
- [2026-04-20 00:00] Sentry release naming in GitHub Actions: release
  versions must be slash-free or `sentry-cli releases new` fails with
  `Invalid release version`. Standardized on composing
  `SENTRY_RELEASE` via a "Compute Sentry release" step that exports
  `${GITHUB_REPOSITORY//\//-}@${GITHUB_SHA}` into `$GITHUB_ENV`, then
  reusing that single value for both the Python process and the
  `sentry-cli` release step. Applied in
  `.github/workflows/weekly-excel-generation.yml` and
  `.github/workflows/system-health-check.yml`. Any new workflow that
  creates a Sentry release or tags events with `SENTRY_RELEASE` MUST
  follow this same pattern — do not reintroduce the raw
  `${{ github.repository }}@${{ github.sha }}` form.
- [2026-04-20 12:00] Sentry Logs support wired for the Python
  billing engine, **gated opt-in + defense-in-depth sanitizer**.
  `sentry_sdk.init(...)` in `generate_weekly_pdfs.py` sets
  `enable_logs=` from a new `SENTRY_ENABLE_LOGS` env var (truthy
  values: `1`, `true`, `yes`, `on`; default `false`) AND registers a
  `before_send_log` hook that drops records whose body matches any
  entry in `_PII_LOG_MARKERS` (row-sample diagnostics, cell dumps,
  helper / vac-crew detection logs, rate-recalc traces, foreman
  assignment logs, `Removing …` / `Unchanged (…` / `FORCE
  GENERATION for …` lines — all known INFO paths that embed WR /
  dept / job / foreman / cell / price data). Requires
  `sentry-sdk>=2.35.0`, already pinned in `requirements.txt`.
  Rationale: the engine has INFO-level debug paths
  (`PER_CELL_DEBUG_ENABLED`, row-sample logs, helper / vac-crew
  diagnostics) that can emit billing-row PII; per
  `docs/sentry-implementation.md` "Privacy / Security", that data is
  *intentionally not captured* in Sentry, so forwarding INFO logs by
  default would regress an existing privacy guarantee. New rules:
  (1) Any new Python script that initializes Sentry in this repo
  must route `enable_logs` through the same `SENTRY_ENABLE_LOGS` env
  gate — do not hard-code `True`. (2) Adding a new INFO log that
  embeds row content? Either strip the PII from the message or
  extend `_PII_LOG_MARKERS` in the same PR so the sanitizer keeps
  up. Never rely on the env gate alone. (3) Before flipping
  `SENTRY_ENABLE_LOGS=true` in any environment, audit log call sites
  and keep `PER_CELL_DEBUG_ENABLED` and row-sample debug flags off
  in production. (4) For direct-to-Sentry sends, prefer the existing
  `sentry_capture_message_with_context(...)` helper over the
  upstream `sentry_sdk.logger.*` API, which is less established in
  this codebase and depends on SDK internals that may shift.
  Issue-creation behavior is unchanged regardless of the gate
  (`event_level=logging.ERROR`, so only ERROR+ creates issues;
  INFO/WARNING were already breadcrumbs and become searchable Logs
  only when the gate is on and the sanitizer lets them through).
- [2026-04-21 22:35] VAC crew post-cutoff pricing lag was a *silent
  fall-through* in `recalculate_row_price()`, not a cutoff-column
  bug. **Context:** The cutoff rule is correctly keyed on
  `Snapshot Date >= RATE_CUTOFF_DATE` at
  `generate_weekly_pdfs.py:2127`; Weekly Reference Logged Date is
  the wrong column for this check and must NOT be substituted —
  operators depend on Snapshot Date semantics. **Real root cause:**
  `build_cu_to_group_mapping()` reads the old CSV's
  `Compatible Unit Group` column, which mixes short codes (e.g.
  `ANC-M`, `CPD-SW`) with verbose names (e.g. `Vacuum Switch`,
  `Overhead Switching"`, `Softswitch Type K"`, `1200 KVAR Switched
  Bank`). The new contract CSV keys rates ONLY by short codes. So
  any CU whose old-CSV group is a verbose name that isn't a key in
  the new rates table (heavily concentrated on VAC crew specialty
  work — vacuum switches, softswitches, switched banks) hit the
  "group not in rates_dict" branch in `recalculate_row_price` and
  returned the SmartSheet price unchanged with only a
  `logging.debug` — invisible in production logs. **Fix (additive,
  production-safe):** (1) In `recalculate_row_price` at the
  "group not in rates_dict" branch, fall back to a direct CU-code
  lookup in `rates_dict` before giving up; only activates on exact
  match so it cannot mis-apply a rate. (2) When even the direct CU
  lookup misses, elevate the log to WARNING with CU, mapped group,
  qty, and work type so operators see it immediately. (3) Track
  `{'recalculated', 'skipped'}` counters and a top-CU Counter per
  sheet inside `_fetch_and_process_sheet`, and emit a per-sheet
  WARNING summary when any skips happened — this surfaces the list
  of CU codes the data team needs to add to
  `NEW_RATES_CSV` / `New Contract Rates copy regenerated again.csv`
  (the usual actual resolution). **New rules:** (1) When adding a
  new CU classification (VAC crew, subcontractor variant, etc.),
  verify at least one end-to-end row produces a WARNING-free rate
  recalc before going to production — if the per-sheet summary
  logs `N skipped`, those CUs are missing from the new rates CSV.
  (2) Do NOT change the cutoff column from `Snapshot Date` to
  `Weekly Reference Logged Date` — that was an earlier speculative
  fix and was rolled back; the business rule is explicitly
  snapshot-keyed. (3) Never promote recalc fall-through logs back
  to DEBUG without adding an alternate visibility path — silent
  price retention directly drives billing inaccuracy. Regression
  tests:
  `tests/test_subcontractor_pricing.py::TestRecalculateRowPrice`
  now covers both the CU-direct fallback
  (`test_cu_direct_fallback_when_mapped_group_absent_from_new_rates`)
  and the safety guard that still retains SmartSheet price when
  neither group nor CU is in new rates
  (`test_silent_fallthrough_when_neither_group_nor_cu_in_new_rates`).
- [2026-04-21 23:50] `recalculate_row_price()` now returns
  `(price, priced_from_rates: bool)` instead of inferring success from
  `new_price != old_price` — identical SmartSheet and contract math
  must still count as **recalculated** for per-sheet counters and must
  not inflate **skipped** / top-CU noise. Callers that branch on
  post-cutoff outcomes must use the boolean. The VAC/helper
  zero-price WARNING tail only references the rate-recalc summary when
  `row_rate_recalc_attempted` is true (same nested conditions as the
  recalc block); otherwise it explains that recalc was not run.
  Regression: `test_recalc_success_when_new_price_equals_old_price`.
