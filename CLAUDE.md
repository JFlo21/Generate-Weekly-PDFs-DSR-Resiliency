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
Pre-fetch target-row attachments (ThreadPoolExecutor, PARALLEL_WORKERS≤8)
   into an in-memory cache to avoid 2-3 per-row API calls per group later.
   **Sub-budget** ATTACHMENT_PREFETCH_MAX_MINUTES (default 10) + **per-future
   timeout** ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC (default 45s) ensure a
   stuck HTTP call cannot consume the session budget. Pre-flight guard
   skips the phase entirely if less than the pre-fetch budget is left of
   TIME_BUDGET_MINUTES. Consumers (_has_existing_week_attachment,
   delete_old_excel_attachments, cleanup_untracked_sheet_attachments) all
   accept a missing cache entry and fall back to per-row on-demand lookup.
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
- Time-budget family (GitHub Actions only):
  - `TIME_BUDGET_MINUTES` — session graceful-stop budget. Default `0`
    (disabled) for local runs; the weekly workflow sets `180` (3h). Raised
    from `80` on 2026-04-22 after a pre-fetch stall consumed the whole
    session with zero output. Must stay strictly less than the workflow's
    `timeout-minutes` (currently `195`).
  - `ATTACHMENT_PREFETCH_MAX_MINUTES` (default `10`) — phase sub-budget
    for the target-row attachment pre-fetch. Also the threshold for the
    pre-flight guard that skips pre-fetch entirely when the session
    budget is already mostly consumed.
  - `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` (default `45`) — per-future
    wait inside the pre-fetch consumer loop. A stuck HTTP call cannot
    block the consumer beyond this; its row falls back to per-row lookup.
- Debug flags: `DEBUG_MODE`, `QUIET_LOGGING`, `PER_CELL_DEBUG_ENABLED`, `FILTER_DIAGNOSTICS`, `FOREMAN_DIAGNOSTICS`, `LOG_UNKNOWN_COLUMNS`, `DEBUG_SAMPLE_ROWS`
- Sentry Logs gate: `SENTRY_ENABLE_LOGS` (default `false`). Keep off by
  default because INFO-path logs can embed row PII; the `before_send_log`
  sanitizer in `generate_weekly_pdfs.py` is the defense-in-depth backstop.

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

**Runner timeouts (the `core` job in `weekly-excel-generation.yml`):**
- `timeout-minutes: 195` — hard Actions ceiling.
- `TIME_BUDGET_MINUTES: '180'` — Python graceful-stop budget.
- The 15-minute gap is reserved for post-job cache-save and artifact-
  upload steps. Never raise `TIME_BUDGET_MINUTES` without also raising
  `timeout-minutes` by at least as much — otherwise Actions hard-kills
  the job before the graceful stop fires and cache/attachment-upload
  progress is lost.

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
- [2026-04-22 00:00] VAC crew Excel files silently not regenerating
  when a non-first-sorted row's VAC crew fields change. **Root
  cause:** `calculate_data_hash()` built `vac_crew` variant
  metadata (VACCREW / VACCREW_DEPT / VACCREW_JOB) from
  `sorted_rows[0]` only — mirroring the helper pattern — but the
  `vac_crew` group key (`{week}_{wr}_VACCREW`, created in
  `group_source_rows`) does NOT split per foreman the way helper
  groups do (`{week}_{wr}_HELPER_{helper}`). A single VAC crew
  group therefore contains every VAC crew member for that
  WR+week. Editing the dept/job/name on a member that didn't sort
  first left the hash unchanged, the "unchanged + attachment
  exists" skip path fired, and no Excel regenerated even though
  the row fully met VAC crew criteria (dept #, name, both
  `Vac Crew Completed Unit?` and `Units Completed?` checked).
  Adding a row already regenerated (ROWCOUNT changed), so only
  *modifications* to existing rows were silently lost. **Fix:**
  include `__vac_crew_name`, `__vac_crew_dept`, `__vac_crew_job`
  directly in the per-row `row_str` that feeds the hash (scoped
  to the `vac_crew` variant so primary/helper hash stability is
  preserved). Per-row inclusion is strictly more sensitive than
  aggregating values into `meta_parts` and avoids two review-caught
  pitfalls of set-based aggregation: **set dedup** (depts
  `{500, 500, 600}` + editing one row 500→600 leaves the set
  unchanged) and **delimiter collision** (`','.join` on free-text
  names cannot distinguish `['A,B','C']` from `['A','B,C']`).
  Helper metadata was left on `sorted_rows[0]` because helper
  groups already partition by foreman and every row in a helper
  group shares identical helper info. **Secondary fix:** bumped
  `DISCOVERY_CACHE_VERSION` from 2 → 3 so any discovery cache
  created before VAC crew columns were added to a particular
  existing sheet in Smartsheet is re-validated on the next run
  rather than waiting up to `DISCOVERY_CACHE_TTL_MIN` (default 7
  days) for the mapping to refresh. **New rules:** (1) Whenever a
  group key variant does NOT include a disambiguating identifier
  (the way `_VACCREW` doesn't include the VAC crew name the way
  `_HELPER_<name>` does), the corresponding hash MUST capture
  per-row field changes at the row level — a set-based
  `meta_parts` aggregation of free-text values is a two-way
  silent-skip trap (dedup + delimiter collision). (2) When fixing
  a bug that could leave existing discovery caches with incorrect
  column mappings, bump `DISCOVERY_CACHE_VERSION` so the fix takes
  effect immediately instead of eventually. (3) Living-ledger
  entries and code comments in this codebase must refer to
  functions / group-key formats / env-var names — not hard-coded
  line numbers — because line numbers drift as the file grows.
  Regression tests:
  `tests/test_vac_crew.py::TestVacCrewHashAggregation` covers
  dept-edit and name-edit on non-first rows, the set-dedup
  collision case (`{500, 500, 600}` with a 500→600 edit), the
  delimiter-collision case (commas in free-text names), and
  hash stability when nothing changes. The test class pins
  `EXTENDED_CHANGE_DETECTION`, `RATE_CUTOFF_DATE`, and
  `_RATES_FINGERPRINT` in `setUp`/`tearDown` so developer env-var
  overrides don't destabilize the suite.
- [2026-04-22 16:05] Production incident: a scheduled run finished
  with **0 Excel files generated, 0 uploaded** despite completing
  discovery, row fetch, and grouping (1910 groups identified). Root
  cause was the attachment pre-fetch phase — a `ThreadPoolExecutor`
  + `as_completed` consumer loop around
  `client.Attachments.list_row_attachments` — stalling for ~16
  minutes on the last ~14 of 539 target rows after 4
  `RemoteDisconnected` retries on the Smartsheet `/attachments`
  endpoint. The consumer used a blocking `future.result()` with no
  per-future timeout, so one stuck HTTP worker serialized the tail
  of the batch. Combined with the preceding discovery + row fetch,
  total elapsed hit 82.4 min **before** the group-processing loop
  ran its first iteration; the existing `TIME_BUDGET_MINUTES=80`
  guard then exited immediately with "1910 group(s) remaining" and
  no generation occurred. **Fix (additive, production-safe):**
  (1) Introduced `ATTACHMENT_PREFETCH_MAX_MINUTES` (default 10) and
  `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` (default 45) env vars.
  (2) Pre-flight guard: if `session elapsed` already leaves less
  than `ATTACHMENT_PREFETCH_MAX_MINUTES` of the session budget,
  skip the pre-fetch entirely — per-row fallback paths in
  `_has_existing_week_attachment` and `delete_old_excel_attachments`
  already handle a missing cache entry transparently.
  (3) Phase sub-budget is enforced on the **wait itself**:
  `as_completed(futures, timeout=ATTACHMENT_PREFETCH_MAX_MINUTES*60)`.
  The iterator raises `FuturesTimeoutError` if no further future
  completes inside that window — this is the only timeout that can
  break out of a stall. An earlier revision of this fix put the
  timeout on `future.result(timeout=...)` alone, which was dead
  code: `as_completed` only yields futures that are already done,
  so their `.result(timeout=...)` returns immediately and the
  timeout branch can never fire.
  (4) Non-blocking executor shutdown. The pre-fetch must NOT use
  `with ThreadPoolExecutor(...)` — that forces `shutdown(wait=True)`
  on exit, which still blocks on stuck in-flight threads and
  defeats the whole point of the sub-budget. The code uses
  explicit `executor.shutdown(wait=False, cancel_futures=True)` in
  `finally`; queued-but-not-started futures are cancelled and
  still-running threads are abandoned to the background (SDK retry
  backoff is bounded; the workflow's `timeout-minutes: 195` is the
  hard ceiling).
  (5) Counters reflect reality: the log / Sentry span report
  `cancelled` (futures where `f.cancel() == True`) and
  `still_running` (in-flight futures we abandoned) separately
  instead of conflating them via `not f.done()` — which overcounts
  abandons because `cancel()` returns `False` once a task has
  started.
  **New rules:** (1) Any pre-flight / pre-processing phase that
  shares `TIME_BUDGET_MINUTES` with the main generation loop MUST
  have its own sub-budget sized well below the session budget. A
  pre-flight phase burning the entire session budget with zero
  output is an existential bug, not a performance bug — treat it
  as P0. (2) When timing out a `ThreadPoolExecutor.submit` +
  `as_completed` consumer hitting an external API, the timeout
  MUST be on `as_completed(..., timeout=...)` (or an equivalent
  `wait(..., timeout=...)`) — the iterator is where blocking
  happens, not `future.result()`. Relying on the upstream SDK's
  HTTP timeout is insufficient because urllib3 retries can
  multiply it. (3) Also never use `with ThreadPoolExecutor(...)`
  for such a consumer: the context manager's implicit
  `shutdown(wait=True)` will re-block on whatever the timeout was
  meant to escape. Always manage the executor explicitly and call
  `shutdown(wait=False, cancel_futures=True)` when time-boxing.
  (4) When skipping an optimization on a budget-exceeded path,
  verify the fallback path still works end-to-end — partial /
  skipped pre-fetch here is safe *only* because both attachment
  consumers already accept `cached_attachments=None`; adding a new
  consumer that assumes the cache is populated would reintroduce
  this class of bug. (5) `Future.cancel()` returns `True` only for
  queued futures — running threads cannot be cancelled. Account
  for this in any abandoned/cancelled metric or the number will
  mislead Sentry. Regression tests:
  `tests/test_performance_optimizations.py::TestAttachmentPrefetchBudget`
  locks in the new constants (with env-isolated `patch.dict` +
  `importlib.reload` so a developer's local env doesn't leak into
  the assertions) and the `FuturesTimeoutError` import.
- [2026-04-22 17:10] Raised weekly-workflow session time budget from
  `TIME_BUDGET_MINUTES=80` → `180` (3h) and the matching runner
  `timeout-minutes` from `90` → `195`. Rationale: even with the
  pre-fetch sub-budget landed earlier today, the main generation
  loop still needs enough headroom to process the full group set
  (1910 groups on the incident run) in a single session rather
  than always relying on backlog catch-up. **Rule:** the workflow
  `timeout-minutes` value must always exceed `TIME_BUDGET_MINUTES`
  by the length of the post-job cache-save + artifact-upload
  steps (~10-15min). Today's cushion is 15min. Never raise
  `TIME_BUDGET_MINUTES` without also raising `timeout-minutes` by
  at least as much, or Actions hard-kills the job before the
  graceful stop fires and the `save_hash_history` / Sentry flush
  / attachment upload tails are lost. Code changes were
  additive-only (config values + comments + one dead-variable
  cleanup — the unused `wr_num` unpack in `_fetch_row_attachments`
  became `_, target_row = row_item` since only `target_row.id` is
  referenced inside the closure). No behavioral change to
  discovery, row fetch, grouping, hashing, generation, or upload.
