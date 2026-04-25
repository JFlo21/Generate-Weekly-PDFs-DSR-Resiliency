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
  mislead Sentry. (6) **Three things block interpreter exit for
  a non-daemon worker and ALL THREE must be addressed to actually
  bound a stall:** (a) `concurrent.futures.thread._python_exit`
  (registered via `threading._register_atexit`) joins every worker
  in `_threads_queues`; (b) `threading._shutdown` joins every
  tstate lock in `_shutdown_locks` — non-daemon threads add
  themselves there via `_set_tstate_lock` at startup; (c) the
  executor's own `shutdown(wait=True)` joins all workers on
  `with`-block exit. The pre-fetch defeats all three by (a)
  popping from `_threads_queues` on the budget-exceeded path (see
  `_detach_from_atexit_registry`), (b) using
  `_DaemonThreadPoolExecutor` — a subclass that creates
  `daemon=True` workers, so `_set_tstate_lock` skips adding them
  to `_shutdown_locks` — and (c) explicit
  `shutdown(wait=False, cancel_futures=True)` instead of `with`.
  Empirical note: an earlier revision did only (a) and still hung
  ~5s at interpreter exit in a repro; (a)+(b)+(c) exits in ~0.05s.
  This trifecta is safe ONLY because the pre-fetch cache is an
  optimization with an always-available per-row fallback. Do NOT
  copy this pattern onto a `ThreadPoolExecutor` whose workers
  produce results the main flow depends on (generation, upload,
  hash_history) — the atexit join is what guarantees those
  workers' side effects are flushed before `return 0` is visible
  to the shell.
  (7) The pre-flight skip condition must reserve
  *generation headroom* beyond the pre-fetch budget
  (`ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN`, default 2
  minutes). Without it, a setup with remaining ==
  `ATTACHMENT_PREFETCH_MAX_MINUTES` would still run pre-fetch and
  leave zero time for the generation loop — recreating the
  original incident's zero-output failure mode.
  (8) Test files that `importlib.reload(generate_weekly_pdfs)`
  MUST patch `SENTRY_DSN=""` + `sentry_sdk.init` around the
  reload (see `_safe_reload_gwp` in
  `tests/test_performance_optimizations.py`); otherwise a dev
  shell with a real `SENTRY_DSN` causes each reload to fire a
  live Sentry init during test runs. Mirrors the pattern in
  `tests/test_sentry_log_sanitizer.py`. Regression tests:
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
- [2026-04-22 18:30] Silent VAC crew detection failure when a
  folder-discovered sheet's VAC Crew column titles drift from the
  exact strings in the `synonyms` dict of `_validate_single_sheet`.
  **Context:** Sheet ID `1413438401105796` in folder
  `8815193070299012` (an `ORIGINAL_CONTRACT_FOLDER_IDS` entry) was
  correctly discovered via `discover_folder_sheets` and merged into
  `base_sheet_ids`, but its VAC Crew columns carried subtle title
  variants (whitespace / case / punctuation drift) that the
  exact-string loop at the `if c.title in synonyms and
  synonyms[c.title] not in mapping:` gate could not absorb. With
  the two key columns (`VAC Crew Helping?` and
  `Vac Crew Completed Unit?`) missing from `column_mapping`,
  `sheet_has_vac_crew_columns` in `_fetch_and_process_sheet`
  evaluated `False`, the row-level detection block was skipped
  wholesale, and every VAC crew row for that sheet — including
  a foreman's whose production data the reporter surfaced to us —
  flowed through the primary variant and never produced a
  `_VacCrew` Excel. (Foreman name redacted: billing-row foreman
  names are PII and must not be committed to this repository per
  the Sentry Logs sanitizer rule earlier in this ledger.) The deceptive part: the diagnostic
  log `"🚐 VAC Crew columns found in sheet: [...]"` still fired
  because it uses a broader substring check
  (`'Vac Crew' in c.title or 'VAC Crew' in c.title`), so operators
  tailing logs saw the columns "found" even though the actual
  mapping had silently failed. **Fix (additive, production-safe):**
  (1) Introduced `_normalize_column_title_for_vac_crew(t)` —
  lowercases, collapses whitespace runs, strips trailing `?`/`#`
  with optional surrounding spaces. Scoped narrowly (name
  explicitly mentions `vac_crew`) so primary/helper exact-match
  behaviour is unchanged. (2) Added a fuzzy fallback pass inside
  `_validate_single_sheet` that runs AFTER the exact-match loop:
  for each canonical VAC Crew name in `_vac_crew_fuzzy_canonicals`
  that isn't already in `mapping`, scan remaining columns using
  the normalized comparison and assign the first match. Already-
  mapped column IDs are excluded so the fuzzy pass cannot clobber
  an exact match. When a fuzzy match fires, log a WARNING with
  the raw title so operators can promote it to an explicit synonym
  if the variant is permanent. (3) Broadened the substring
  detector for `vac_crew_columns_found` to be case-insensitive and
  to catch `'vac-crew'` variants, so the summary log and the
  follow-up warning both surface all-lowercase sheets. (4) After
  the fuzzy pass, if `vac_crew_columns_found` is non-empty but the
  two key mappings (`VAC Crew Helping?`, `Vac Crew Completed
  Unit?`) are still absent, emit an actionable WARNING with the
  raw titles so operators know detection will be disabled for that
  sheet. (5) Bumped `DISCOVERY_CACHE_VERSION` from 3 → 4 so
  existing caches (which may have persisted a stale mapping
  without VAC Crew columns) are invalidated on the next run
  instead of waiting up to `DISCOVERY_CACHE_TTL_MIN` (7 days).
  **New rules:** (1) Any column-mapping synonyms dict that accepts
  only a small, hard-coded set of case variants is a silent-skip
  trap whenever the downstream detection uses the mapped keys as
  an on/off gate. When the gate controls a whole variant's
  generation (VAC crew here, helper previously), add a fuzzy
  fallback pass and an operator-visible WARNING if the key
  columns still don't resolve. Do NOT rely on substring-match
  diagnostic logs alone — they can falsely advertise success.
  (2) Fuzzy fallback must be scoped by naming and by canonical
  list — do NOT broaden matching for primary/helper columns
  without a documented production incident driving it. Helper and
  primary flows have stable exact-match history; an unscoped
  normalizer risks colliding unrelated column titles (e.g. a
  primary `Foreman` column fuzzy-matching a helper `Foreman
  Helping?` with the `?` stripped). (3) When a bug could leave
  `generated_docs/discovery_cache.json` holding an incorrect
  `column_mapping` for an existing (already-discovered) sheet,
  bump `DISCOVERY_CACHE_VERSION` — the `_new_from_folders` check
  in `discover_source_sheets` only invalidates on NEW sheet IDs,
  so in-place column additions inside an already-cached sheet do
  NOT trigger a refresh on their own. Regression tests:
  `tests/test_vac_crew.py::TestVacCrewColumnTitleNormalizer` and
  `tests/test_vac_crew.py::TestVacCrewColumnFuzzyFallback` cover
  whitespace / case / punctuation drift, exact-match preservation
  when both forms are present, and the cache-version bump.
- [2026-04-23 00:00] Current-week VAC crew Excel files silently not
  generating because the pre-acceptance rate recalc required a
  populated `Snapshot Date`. **Reported symptom:** VAC crew
  attachments produced for week ending 04/12/26 but nothing for
  week ending 04/19/26, despite operators confirming the usual
  criteria (VAC Crew Helping? populated, Vac Crew Completed Unit?
  and Units Completed? both checked) on those current-week rows.
  **Root cause:** The recalc block in `_fetch_and_process_sheet`
  was gated strictly on `Snapshot Date >= RATE_CUTOFF_DATE`. For
  rows freshly logged in the most recent week, Smartsheet's
  snapshot automation has not yet populated `Snapshot Date`, so
  the outer `if snapshot_raw_pre:` short-circuited and recalc was
  entirely skipped. The row's `Units Total Price` therefore
  retained whatever SmartSheet had — which for VAC crew specialty
  CUs is often 0 or blank because the upstream Smartsheet price
  formula itself depends on the CU being present in the legacy
  rates map. The downstream `has_price` gate then evaluated
  False and the row was dropped before VAC crew detection or
  grouping could run. WE 04/12 rows escaped the trap only because
  they'd been on the sheet long enough for the snapshot
  automation to fire. **Fix (additive, production-safe):**
  (1) Introduced `RATE_RECALC_WEEKLY_FALLBACK` env var (default
  `true`; truthy values `1`/`true`/`yes`/`on`) that enables a
  Weekly-Ref-Date fallback path when `Snapshot Date` is blank or
  unparseable. (2) Extracted the recalc gating into a new helper
  `_resolve_rate_recalc_cutoff_date(row_data, cutoff_date, *,
  weekly_fallback_enabled=True) -> (effective_cutoff_date,
  used_fallback)`. The helper returns the snapshot date when that
  is populated and `>= cutoff` (primary rule, unchanged); it
  falls back to `Weekly Reference Logged Date` only when the
  snapshot value is blank/unparseable AND the weekly date parses
  AND the weekly date is `>= cutoff`. Rows with a populated
  snapshot date that is *pre-cutoff* still return `None` — the
  fallback does NOT override the snapshot-keyed business rule.
  (3) Added `fallback_applied` counter alongside the existing
  `recalculated` / `skipped` counters and surfaced it in the
  per-sheet "Rate recalc summary" log. (4) Updated the per-row
  "Dropped VAC/helper row" WARNING's `_recalc_note` to distinguish
  three cases for operators: recalc ran with `missing_rate`,
  recalc ran via Weekly-Ref-Date fallback with `missing_rate`,
  and recalc skipped because the fallback was disabled AND
  `Snapshot Date` was blank (points operators at the env var
  instead of at `NEW_RATES_CSV`). **New rules:** (1) The ledger
  guardrail from 2026-04-21 — "Do NOT change the cutoff column
  from `Snapshot Date` to `Weekly Reference Logged Date`" —
  stands. A *fallback* when Snapshot Date is missing is
  explicitly NOT the same as replacing the primary column; the
  snapshot rule still controls every row that has a snapshot
  value. Any future broadening of the recalc gate (e.g. allowing
  the fallback to trump a pre-cutoff snapshot date) would
  violate the guardrail and must be rejected without a documented
  production-incident justification. (2) Any new pre-acceptance /
  pre-`has_price` data transformation tied to a business cutoff
  MUST degrade gracefully when the driving column is blank.
  Silent skip-on-blank is a current-week failure trap: the
  freshly entered rows operators expect to see on Monday morning
  are exactly the rows most likely to have blank
  automation-populated columns. (3) When a config env var's
  default changes observable production behaviour (here:
  `RATE_RECALC_WEEKLY_FALLBACK=1` rescues rows that previously
  silently dropped), the `if RATE_CUTOFF_DATE:` boot-up log block
  MUST print the fallback's resolved state so operators grepping
  the startup banner can tell at a glance whether the rescue is
  active. Regression tests:
  `tests/test_subcontractor_pricing.py::TestWeeklyRefDateFallbackCutoff`
  covers the env constant's presence, the snapshot-post-cutoff
  primary path (no fallback), the snapshot-pre-cutoff guardrail
  (fallback must NOT override), the incident case (blank
  Snapshot + post-cutoff Weekly → fallback triggers), the
  all-blank and pre-cutoff-Weekly no-op cases, the
  `weekly_fallback_enabled=False` legacy-behaviour preservation
  path, unparseable-Snapshot fallthrough, the `cutoff=None`
  defensive guard, and an end-to-end check that drives
  `_resolve_rate_recalc_cutoff_date` → `recalculate_row_price`
  and asserts the row's `Units Total Price` is updated in-place
  so the downstream `has_price` gate will accept it.
- [2026-04-23 12:00] Security-tightening audit on
  `generate_weekly_pdfs.py`. Two real attack surfaces fixed, plus
  a hygiene cleanup. **(1) Path traversal via `wr_num` in Excel
  filenames.** `wr_num` is derived from the row's
  `Work Request #` column at two sites (inside `generate_excel`
  and in the main group-processing loop) and embedded directly
  into `os.path.join(week_output_folder, output_filename)` →
  `workbook.save(final_output_path)`. Realistic production WR#s
  are numeric, so normal data is unaffected, but a malicious
  `1234/../evil` value would have escaped `generated_docs/<week>/`.
  Fix: apply `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]`
  at BOTH derivation sites — in-place numeric WR#s pass through
  unchanged (`\w` includes 0-9), and sanitizing consistently at
  both sites keeps `history_key`, `_has_existing_week_attachment`
  prefix matching, and the actual on-disk filename all lined up
  (sanitizing only one site would break attachment matching).
  **(2) PII leakage via Sentry `context_data['error_message']`.**
  Five `sentry_capture_with_context(...)` call sites passed
  `str(e)` straight into `context_data`, which is attached as
  Sentry event context — bypassing the `before_send_log` hook
  (that hook only scrubs logging records, not `event['contexts']`).
  Fix: new helper `_redact_exception_message(exc, *, max_len=240)`
  strips WR identifiers (`WR=<redacted>`), dollar amounts
  (`$<redacted>`), emails (`<email>`), and
  `customer=`/`foreman=`/`dept=`/`snapshot=`/`cu=`/`job=` key-
  value pairs, prefixes the exception class name for event-
  grouping stability, collapses whitespace, and truncates.
  All five sites now use it. **(3) Discovery cache schema guard.**
  `cache.get('sheets', [])` was trusted blindly — a malformed
  entry without `column_mapping` would crash
  `_fetch_and_process_sheet` later with a KeyError.
  Fix: filter to `_valid_cached_sheets` (requires dict with
  int `id` and dict `column_mapping`), log an operator WARNING
  when entries are dropped with a pointer to delete
  `DISCOVERY_CACHE_PATH` for a clean rediscovery. **(4) Hygiene:**
  removed unused `import inspect`. **Legacy-code note:**
  `VAC_CREW_SHEET_IDS` / `VAC_CREW_FOLDER_IDS` at line ~319-320
  are intentionally retained — the line 318 comment correctly
  flags them as test-only, and they're read exclusively by
  `tests/test_vac_crew.py::TestVacCrewSheetIdsConfig` (4 tests).
  No production code path touches them. Removing the pair is a
  separate coordinated change with those tests; it is not a
  conflict risk in its current form. **New rules:**
  (1) Any user-controllable string (row field, Smartsheet cell
  value, env-var-derived identifier) that flows into
  `os.path.join(...)` / `workbook.save(...)` / any `open(path,
  'w')` MUST pass through a filesystem-safety sanitizer at each
  derivation site — not just at the final filename assembly —
  so downstream comparisons (history keys, attachment prefix
  matching) stay consistent. Reuse `_RE_SANITIZE_HELPER_NAME`
  (`[^\w\-]`) or a tighter pattern; do not invent new ones
  per-site. (2) Never pass raw `str(exc)` into
  `sentry_capture_with_context(...)`'s `context_data` payload.
  That dict lands in `event['contexts']` and bypasses the
  `before_send_log` sanitizer. Use
  `_redact_exception_message(e)` so row PII stays out of the
  Sentry dashboard. (3) Any JSON file loaded from disk into a
  typed shape (discovery cache, hash history, future caches)
  MUST guard each entry with `isinstance(...)` checks before
  trusting `entry['id']` / `entry['column_mapping']` / similar
  — a corrupt cache should WARN and drop the bad entries, not
  crash the whole run. Regression tests:
  `tests/test_security_audit_followup.py` covers WR#
  sanitization (regex, no-op for numeric, cannot-escape-
  OUTPUT_FOLDER, filename shape), `_redact_exception_message`
  (WR / money / customer+foreman tokens / email / class prefix
  / truncation / unrepresentable exception / None / realistic
  end-to-end), the discovery-cache schema guard (kept / dropped
  variants, matches-production-filter comprehension), and the
  `inspect` import removal.
- [2026-04-23 18:05] PR #176 review-driven tightening on top of the
  2026-04-23 12:00 security audit. Three follow-ups addressed:
  **(1) Cache `name` field guard.** The original
  `_valid_cached_sheets` filter validated `id` and `column_mapping`
  but not `name` — `_fetch_and_process_sheet` accesses
  `source['name']` directly in several log lines / Sentry
  breadcrumbs and would KeyError on a cached entry missing the
  field. Filter now also requires `isinstance(s.get('name'), str)`.
  **(2) All-dropped → forced rediscovery (P1).** With the new
  filter in place, a cache where *every* entry was malformed would
  have made the fresh-cache path return `[]`, silently turning the
  run into a no-op. Added a guard: when `_raw_cached_sheets` is
  non-empty but `_valid_cached_sheets` is empty, raise `ValueError`
  so the outer `except Exception as e:
  logging.info("Cache load failed, refreshing discovery: {e}")`
  handler catches it and falls through to full rediscovery from
  `base_sheet_ids` — same failure mode as the existing
  schema-outdated / unreadable-cache paths. Partial-drop cases
  (some valid, some malformed) still succeed with the valid
  subset.
  **(3) `_recalc_note` branch handles unparseable Snapshot Date.**
  The fallback-disabled drop warning previously keyed on
  `not row_data.get('Snapshot Date')`, which treats a present but
  unparseable cell (e.g. `'not-a-date'`) as "populated" and
  suppresses the note — yet
  `_resolve_rate_recalc_cutoff_date` treats unparseable Snapshot
  Date *the same* as blank (skipping recalc). The condition now
  reuses `excel_serial_to_date(row_data.get('Snapshot Date')) is
  None`, so the note fires consistently with the recalc gate. The
  warning text also updated to read
  "Snapshot Date is blank or unparseable". **New rules:**
  (1) Any filter that drops untrusted data structures MUST also
  handle the all-dropped case — either by forcing the calling
  path to rediscover or by failing loudly. A filter that returns
  an empty list through a success path is a silent-no-op trap.
  (2) Operator-facing "why was this dropped?" notes MUST be
  based on the *parsed/derived* state (the same helper used by
  the business-logic gate), not on raw cell truthiness. Keying
  on raw cells drifts as parser behaviour evolves and produces
  misleading guidance when the cell is malformed. Regression
  tests: new classes in `tests/test_security_audit_followup.py`
  — `TestDiscoveryCacheSchemaGuard` (extended for the `name`
  field), `TestDiscoveryCacheAllDroppedForcesRediscovery`
  (all-malformed raises, partial-drop preserves valid subset,
  empty-cache is not miscategorised), and
  `TestRecalcNoteHandlesUnparseableSnapshotDate` (blank /
  unparseable / valid Snapshot Date behaviour of the note's
  condition).
- [2026-04-23 18:25] PR #176 P2 follow-up: the `wr_num`
  sanitization landed earlier today was inconsistent across the
  upload/delete pipeline. The main loop sanitized `wr_num` at
  derivation (line ~4138) and `generate_excel` sanitized its
  local copy before filename construction, but the upload-task
  builder was reading `wr_numbers[0]` from `generate_excel`'s
  raw return tuple — and `create_target_sheet_map` populated
  `target_map` with *unsanitized* WR# keys pulled straight from
  the target sheet's cells. For any WR whose value gets rewritten
  by `_RE_SANITIZE_HELPER_NAME` (the path-traversal test case
  being the motivating example), the pipeline disagreed with
  itself: the skip-check at line 4283 looked up a sanitized key
  in a raw-keyed map and missed, the upload path at line 4321
  looked up a raw key that diverged from the sanitized filename
  actually on disk, and `delete_old_excel_attachments` received
  a raw WR that did NOT match the sanitized filename prefix of
  the prior run's attachment — causing repeated regeneration and
  orphaned duplicate attachments over time. **Fix:**
  (1) Sanitize target_map keys at populate time inside
  `create_target_sheet_map` using the same
  `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]` expression as
  every other site. For realistic numeric WR#s this is a no-op,
  so production data is unaffected. (2) Build the upload task
  from the main-loop sanitized `wr_num` instead of reading
  `wr_numbers[0]` from `generate_excel`'s raw return. The "not
  found in target sheet" warning now also reports the sanitized
  identifier so logs are internally consistent. **New rule:**
  When a sanitizer is added at a derivation site, EVERY
  downstream consumer of that identifier — target-sheet maps
  populated from cells, upload-task dicts, hash-history keys,
  attachment prefix matches, delete-old-attachment filters —
  MUST consume the sanitized value. Sanitization that's only
  applied to ONE path creates a silent split-brain where some
  lookups succeed and others fail, which is worse than no
  sanitization at all. Helper audit: `_RE_SANITIZE_HELPER_NAME`
  is idempotent (applying it twice gives the same result), so
  it's safe to apply at both producer and consumer sites without
  having to reason about which one "owns" the canonicalisation.
  Regression tests: new
  `TestWrIdentifierConsistencyAcrossUploadPath` class in
  `tests/test_security_audit_followup.py` locks in numeric
  no-op behaviour, sanitizer idempotence, sanitized
  source-row + sanitized target_map match, and the inverse
  property that a raw WR must NOT match a sanitized target_map
  (guards against regressing to the P2 bug).
- [2026-04-23 18:50] PR #176 round-3 Copilot review follow-ups.
  Three targeted refinements on top of the security-tightening
  audit: **(1) Misleading operator note.** The
  fallback-disabled `_recalc_note` fired whenever Snapshot Date
  was blank/unparseable, regardless of the row's Weekly Reference
  Logged Date. For rows whose weekly date is also blank,
  unparseable, or pre-cutoff, flipping
  `RATE_RECALC_WEEKLY_FALLBACK=1` would NOT rescue the row — the
  note was sending operators on a false lead. Fix: new helper
  `_weekly_would_trigger_fallback(weekly_raw, cutoff_date) -> bool`
  mirrors the secondary branch of
  `_resolve_rate_recalc_cutoff_date` exactly, and the
  `_recalc_note` gate now requires it to return True before
  suggesting the env var. Wording clarified to
  "Weekly Reference Logged Date is >= RATE_CUTOFF_DATE so setting
  the env var…". **(2) Invisible per-sheet summary.** The summary
  only logged when `skipped > 0` or `recalculated > 0`. If
  fallback rows all hit non-reportable outcomes
  (`invalid_quantity` / `zero_rate`), `fallback_applied` could be
  non-zero while both other counters were zero — zero log output,
  zero visibility into whether the fallback ever fired. Fix:
  added an `elif fallback_applied:` branch that logs a neutral
  `0 recalculated, 0 skipped (N via Weekly-Ref-Date fallback)`
  line. **(3) Misleading type hint.**
  `_redact_exception_message(exc: Exception, …)` actually accepts
  `None` (tests cover that branch as intentional API surface).
  Changed the annotation to `BaseException | None` so callers and
  future refactorers aren't misled. **New rules:** (1) Any
  operator-directed "enable env var X" drop note MUST gate on the
  condition that the env var would actually change this row's
  outcome — otherwise the note is a false lead that wastes
  on-call time. When the gating logic is non-trivial, extract it
  to a helper so the note-gate and the code-gate cannot drift.
  (2) Any counter that tracks an independent code-path dimension
  (`fallback_applied` independent of recalc outcome) MUST have a
  log branch that fires on that dimension alone, or it's a write-
  only metric. (3) Type annotations MUST match what the function
  actually accepts. `exc: Exception` on a function that also
  takes `None` is drift that accumulates (IDE warnings, caller
  refactors, new contributors "fixing" the `None` handling
  because it "shouldn't be possible"). Regression tests:
  `tests/test_security_audit_followup.py` gains
  `TestWeeklyWouldTriggerFallback` (post-cutoff / pre-cutoff /
  blank / unparseable / None-cutoff), `TestRateRecalcSummaryCoversFallbackOnly`
  (decision-surface table showing all three counters gate the
  log), and `TestRedactExceptionMessageSignature` (annotation
  must mention None + behaviour regression guard).
- [2026-04-23 19:15] PR #176 round-4 Codex follow-ups. Two
  findings flagged after the note-gate fix: **(P1) Weekly-Ref-Date
  fallback would re-price whole legacy sheets that never map a
  Snapshot Date column.** The fallback activates whenever
  `row_data.get('Snapshot Date') is None`. On sheets whose
  `column_mapping` doesn't include `Snapshot Date` at all, every
  row has `None` for that field, and the fallback silently
  changed the cutoff basis for the entire sheet instead of
  rescuing current-week automation-lag rows. Fix: compute
  `sheet_has_snapshot_date_column = 'Snapshot Date' in
  column_mapping` once per sheet alongside the existing
  `sheet_has_vac_crew_columns` probe, and pass
  `weekly_fallback_enabled=RATE_RECALC_WEEKLY_FALLBACK and
  sheet_has_snapshot_date_column` into
  `_resolve_rate_recalc_cutoff_date`. Legacy sheets preserve the
  pre-fix "no recalc when Snapshot is absent" behaviour exactly.
  **(P2) `target_map` sanitization could collapse distinct WR#
  cell values to the same key.** Two raw values that differ only
  in stripped characters (`1234/evil` vs `1234\\evil`) or whose
  first 50 chars happen to match yield the same key, and the
  later row silently overwrote the earlier — retargeting uploads
  / deletes at the wrong target-sheet row. Fix: track the raw
  value that first produced each sanitized key and, on
  collision, log a WARNING and keep the first-seen mapping
  (deterministic across runs). Realistic numeric WR#s cannot
  collide, so production data is unaffected. **New rules:**
  (1) Any "rescue" fallback tied to a column's absence MUST be
  gated on the column actually being mapped, not on the row's
  field being falsy — otherwise the rescue becomes a blanket
  re-evaluation on sheets that never had the column. The gate
  belongs at the call site (where `column_mapping` is in scope)
  and should reuse the existing per-sheet flag pattern
  (`sheet_has_<column>_<label>`). (2) When using a lossy
  sanitizer (regex + truncation) as a dict key, collisions MUST
  be detected and surfaced, not silently overwrite. Keep the
  first-seen mapping for determinism and log a WARNING that
  includes BOTH raw values so operators can audit the source.
  Regression tests: new
  `TestWeeklyFallbackGatedOnSnapshotColumn` (3 cases covering
  sheet-has-column rescues row / sheet-lacks-column preserves
  legacy / call-site boolean truth table) and
  `TestTargetMapWrKeyCollisionDetection` (sanitizer produces
  collisions for crafted `/` vs `\\`, truncation collisions at
  the 50-char boundary, first-seen is kept, repeated raw WR#
  doesn't inflate the counter) in
  `tests/test_security_audit_followup.py`.
- [2026-04-23 19:40] PR #176 round-5 Codex P2: `_RE_REDACT_WR` was
  too narrow — it only matched digit-only WR tokens
  (`\bWR\s*[#:=]?\s*\d+`), which caused two leaks into Sentry
  `context_data`: (1) alphanumeric identifiers like
  `WR=ABCD-123` passed through unredacted entirely; and (2)
  path-traversal suffixes like `WR=1234/../evil` redacted only
  the `1234`, leaving `/../evil` in the payload. Fix: broadened
  to `\bWR(?![a-zA-Z])\s*[#:=]?\s*[\w/\\\-.]+`. The negative
  lookahead `(?![a-zA-Z])` prevents over-matching English words
  that start with `WR` (`WRITE`, `WRAP`, `WRITTEN`), and the
  identifier char class includes word chars plus `/ \ . -` so
  decorated, alphanumeric, or path-traversal tokens are captured
  in full. The `+` stops at the first whitespace/delimiter so
  only the identifier itself is redacted, leaving surrounding
  prose intact. **New rule:** When writing a redaction regex for
  an identifier, do NOT assume the identifier shape (digits vs
  alphanumerics vs decorated). The identifier body should accept
  any non-delimiter character and stop at a clear terminator
  (whitespace, comma, quote, paren). Overly-restrictive bodies
  leak attacker-controlled suffixes; the negative lookahead
  guards against over-matching natural-language words. Regression
  tests: `TestRedactExceptionMessage` gains `test_redacts_alphanumeric_wr_identifier`,
  `test_redacts_path_traversal_wr_fully`,
  `test_redact_wr_does_not_swallow_english_prose`, and
  `test_redact_wr_handles_backslash_paths`.
- [2026-04-23 20:10] PR #176 round-6 Codex follow-ups. Two
  correctness gaps promoted by the previous fixes themselves:
  **(P1) target_map collision detection was advisory, not
  protective.** The earlier fix logged a WARNING on sanitized-WR#
  collisions but kept the first-seen mapping and left the key
  usable — a later code path could still upload/delete
  attachments on the wrong target-sheet row when the two WRs
  differed only by stripped characters or shared the first 50
  chars. Fix: on collision, `del target_map[key]` AND add the
  key to a `_quarantined_keys` set. Subsequent re-collisions for
  the same key are also counted and logged. Downstream
  `if wr_num in target_map:` check returns False for BOTH
  (or ALL) ambiguous WRs, so the existing "not found in target
  sheet" warning fires for each, uploads are skipped, and
  operators know to deduplicate the target sheet. A loud
  not-found failure is strictly safer than a silent
  wrong-row upload. **(P2) Fresh-cache fast path could return a
  reduced sheet list on partial cache corruption.** The only
  gate was `_new_from_folders`; a malformed cached entry that
  belonged to a static base sheet (not in
  `_all_folder_discovered_ids`) wouldn't flag new_from_folders,
  so the function returned `_valid_cached_sheets` with one sheet
  silently missing — and it stayed missing until
  `DISCOVERY_CACHE_TTL_MIN` (default 7 days). Fix: introduce
  `_partial_cache_corruption = bool(_raw_cached_sheets) and
  len(_valid_cached_sheets) != len(_raw_cached_sheets)` and add
  `and not _partial_cache_corruption` to the fast-path gate.
  Any drop now forces incremental mode, which re-validates
  base_sheet_ids and rediscovers the dropped sheet on this run.
  A dedicated log line announces the revalidation so the cause
  is visible. **New rules:** (1) A collision-detection guard
  that logs but still returns a value is advisory, not
  protective. If an ambiguous key could drive a side-effecting
  downstream operation (upload, delete, state mutation), the
  guard MUST remove/reject the key, not merely note that it's
  ambiguous. Use "quarantine sets" to guarantee the ambiguity
  cannot leak. (2) Cache fresh-path gates must consider ALL
  failure modes of the preceding validation step, not just the
  externally-visible ones. If a schema filter could have
  dropped an entry that belongs to a statically-required set
  (base_sheet_ids here), the fast path cannot trust its own
  cached output — force incremental/full rediscovery instead.
  Regression tests updated:
  `TestTargetMapWrKeyCollisionDetection::test_collision_quarantines_both_rows`
  (replaces the keep-first-seen test),
  `test_third_colliding_row_is_also_rejected`, and the existing
  `test_identical_raw_wrs_do_not_register_as_collision` now
  asserts the quarantine set stays empty. New class
  `TestDiscoveryCacheFastPathSkipsOnPartialCorruption` covers
  the truth-table of the new gate and the
  `_partial_cache_corruption` detection boolean (empty-cache,
  no-drops, one-dropped, all-dropped).
- [2026-04-23 20:40] PR #176 round-7 Codex follow-ups. Two
  companion issues to the round-6 sanitizer work:
  **(P2) ``build_group_identity`` broke on sanitized WR tokens
  containing underscores.** The parser assumed
  ``parts[2] == 'WeekEnding'`` and extracted ``wr = parts[1]``,
  which is only valid when the WR token has zero underscores.
  But ``_RE_SANITIZE_HELPER_NAME`` converts any non-word / non-
  dash character to ``_``, so an input like ``1234/../evil``
  produces a filename ``WR_1234____evil_WeekEnding_...`` and the
  parser returned ``None``. Downstream attachment-identity flows
  (``_has_existing_week_attachment``,
  ``delete_old_excel_attachments``, stale-variant cleanup) then
  failed to match prior runs' files on disk, causing repeated
  regeneration and orphaned attachment accumulation on any WR#
  whose raw value was sanitization-sensitive. Fix: the parser
  now locates ``WeekEnding`` via ``parts.index(...)`` and joins
  ``parts[1:we_idx]`` for the WR token. Variant-marker detection
  (``Helper`` / ``VacCrew`` / ``User``) is scoped to the
  post-``WeekEnding`` tail so a sanitized WR that happens to
  contain one of those literal tokens cannot false-positive the
  variant. Realistic numeric WR#s still parse identically via
  the same code path. **(P1) Source-side WR# collisions across
  groups.** The main loop uses the sanitized WR as the canonical
  key for ``history_key``, ``target_map`` lookups, and Excel
  filenames. If two source groups have raw WR# values that fold
  to the same sanitized key (within the same week + variant),
  one group's hash history overwrites the other's and both
  groups target the same target-sheet row. Fix: pre-scan
  ``groups.items()`` once before the main loop, build a
  ``defaultdict(set)`` keyed by ``(sanitized_wr, week, variant)``,
  and flag any key mapped by more than one distinct raw WR as
  a ``_quarantined_source_wr_keys`` entry. The per-group skip
  is gated on that set immediately after the main loop's
  sanitization step — a quarantined group is skipped with an
  operator-visible WARNING before touching ``history_key``,
  ``target_map``, or ``generate_excel``. **New rules:**
  (1) Any filename parser that splits on a character and
  asserts a fixed-position marker is fragile if the filename's
  components can legitimately contain that character. Use
  ``list.index(marker)`` + span-joins so the parser degrades
  gracefully rather than returning ``None`` silently — a
  silent-return-None from an attachment-identity parser is a
  repeated-regeneration trap. (2) Whenever a sanitizer collapses
  the keyspace (regex + truncation), the pre-pass that detects
  same-key collisions must run at BOTH endpoints of the key —
  the place the key is constructed (source side, here
  ``groups.items()``) AND the place the key is consumed (target
  side, here ``target_map``). Round-6 fixed the target side;
  this round adds the source side. The symmetry is what keeps
  hash history, upload tasks, and target-row lookups from ever
  being driven by the same ambiguous key. Regression tests:
  new ``TestBuildGroupIdentityWithUnderscoresInWr`` (5 cases —
  plain numeric, sanitized-underscore WR round-trip, VacCrew
  filename, Helper filename, no-``WeekEnding`` fails, WR that
  is literally ``Helper`` but variant stays ``primary``) and
  ``TestSourceWrCollisionQuarantine`` (3 cases — slash/backslash
  collision detected, noise-free on realistic numeric WRs,
  scoped by week AND variant tuple).
- [2026-04-23 21:00] PR #176 round-9 Codex P1: the round-7
  source-collision pre-scan was too narrowly scoped. Keying on
  ``(sanitized_wr, week, variant)`` missed cross-week and
  cross-variant collisions, which still reach ``target_map``
  because downstream routing uses the sanitized WR alone — not
  the tuple. Attack surface: if the target sheet has WR A but
  not WR B (both folding to sanitized K), the target-side
  quarantine at ``create_target_sheet_map`` doesn't fire
  (only one raw seen), and B's source group resolves
  ``target_map[K]`` to A's row, uploading B's Excel to A's
  target-sheet row → cross-WR data corruption. Fix: broaden
  the source-side quarantine key from
  ``(sanitized_wr, week, variant)`` to the sanitized WR alone.
  Any pair of distinct raw WRs folding to the same sanitized
  key anywhere in the run is a collision, and every affected
  group is skipped — regardless of week or variant — with a
  WARNING listing all raw values. Realistic numeric WR#s still
  can't collide (same numeric WR across multiple weeks is
  ONE raw, not a collision), so production remains zero-impact.
  **New rule:** When a sanitizer collapses a keyspace and the
  sanitized key drives downstream routing (target_map,
  attachment identity, filename), collision detection MUST be
  keyed on the sanitized value ALONE — not on any tuple that
  includes context the router doesn't use. Otherwise
  cross-context collisions can slip past the quarantine and
  corrupt routing. The per-context variables (``week``,
  ``variant``) are still part of the *downstream* key that
  disambiguates properly-distinct entries; they are NOT part of
  the collision-detection key because that key tracks "can two
  raws masquerade as one" and is a pure sanitizer-level
  property. Regression tests updated: existing
  ``test_pre_scan_scoped_by_week_and_variant`` removed
  (asserted the old, unsafe invariant); new
  ``test_pre_scan_catches_cross_week_collisions`` and
  ``test_pre_scan_catches_cross_variant_collisions`` lock in
  the broader quarantine. A reusable ``_run_pre_scan`` test
  helper mirrors the production pre-scan so the test drift
  between case-setups is eliminated.
- [2026-04-24 10:50] Production incident: the billing_audit
  attribution-snapshot integration spammed the session log with
  repeated retries against Supabase — HTTP 406 Not Acceptable on
  every call to ``feature_flag``, ``freeze_attribution``,
  ``pipeline_run_select``, and ``pipeline_run_upsert``. Each op
  burned the full 4-attempt × (1.5 + 2.5 + 4.5s) backoff budget
  before each op's circuit breaker tripped independently at 3
  exhaustions. **Root cause:** ``billing_audit/client.py``'s
  ``with_retry`` treated EVERY ``postgrest.APIError`` as
  transient. A 406 from PostgREST is actually a PERMANENT
  rejection — in this case code ``PGRST106`` ("The schema must
  be one of the following: public"), which means the
  ``billing_audit`` schema is not in Supabase's exposed-schemas
  list. No amount of retrying can fix a server-side
  schema-exposure configuration. **Fix (additive,
  production-safe):** (1) New ``_classify_postgrest_error(exc)
  -> (is_transient, is_global_kill, reason_code)`` helper
  inspects ``APIError.code``: codes starting with ``PGRST1`` /
  ``PGRST2`` / ``PGRST3`` and HTTP ``4xx`` stringified codes
  are classified permanent (bail after first attempt); codes
  in ``_PGRST_GLOBAL_KILL_CODES`` (``PGRST106`` schema not
  exposed, ``PGRST301`` / ``PGRST302`` JWT invalid/expired)
  additionally flip a run-global kill switch
  (``_global_disable_reason``). An APIError with no code
  (exotic body-parse failure) and HTTP ``5xx`` codes stay
  transient. (2) ``get_client()`` now returns ``None`` when the
  kill switch is set, so every downstream writer path
  (``freeze_row``, ``emit_run_fingerprint``,
  ``any_flag_enabled``) silently no-ops for the rest of the
  run — identical to the "missing credentials" and ``TEST_MODE``
  paths. Preserves the existing fail-safe contract: a
  misconfigured billing_audit integration must never break the
  billing pipeline itself. (3) New ``_disable_for_run`` emits
  exactly ONE operator-facing WARNING on first trip, naming the
  reason code and pointing at the concrete fix — for PGRST106,
  "Supabase: Project Settings → API → Data API Settings →
  'Exposed schemas': add 'billing_audit', save, and reload the
  schema cache". For PGRST301/302, points at
  ``SUPABASE_SERVICE_ROLE_KEY`` rotation. (4) Non-global
  permanent errors (generic PGRST1xx from a malformed payload,
  etc.) still increment the per-op circuit breaker counter but
  do NOT poison unrelated ops — the existing per-op breaker
  isolation contract is preserved. **New rules:** (1) When
  wrapping a library exception type (``APIError``,
  ``ClientError``) in a retry helper, classify by the
  exception's carried metadata (``code``, ``status_code``,
  SQLSTATE), not by the class itself. Treating a class as
  uniformly transient burns retry budget on permanent errors
  and spams operator logs. The classifier is the single place
  to teach the retry helper which codes are worth retrying.
  (2) When a failure is INTEGRATION-WIDE (schema exposure,
  auth key), a per-op circuit breaker alone is insufficient —
  it measures N endpoints to a schema all failing, which is
  already known from the first failure. Ship a run-global kill
  switch that flips ``get_client()`` to ``None`` on detection
  so the rest of the run skips ALL integration work at the
  zero-network cost. (3) Permanent-error WARNINGs must tell
  operators WHERE TO FIX IT, not just WHAT HAPPENED. For every
  code in ``_PGRST_GLOBAL_KILL_CODES`` the disable message
  names the exact Supabase Dashboard path or env-var to check
  — a 2 AM on-call engineer should not have to read the
  PostgREST docs to understand what to do. (4) The kill
  switch is test-reset-sensitive: ``reset_cache_for_tests``
  MUST clear ``_global_disable_reason`` and
  ``_global_disable_logged`` or one test's tripped state leaks
  into unrelated tests in the same pytest run. Regression
  tests: new
  ``tests/test_billing_audit_shadow.py::PostgrestErrorClassificationTests``
  (11 tests) — classifier contract (global-kill for PGRST106 /
  PGRST301, op-permanent for generic PGRST1xx, permanent for
  HTTP 4xx, transient for HTTP 5xx / missing code), retry
  short-circuit (one attempt on permanent APIError, no
  ``time.sleep`` backoff), global kill (one WARNING with
  "Exposed schemas" text, ``get_client()`` returns None after
  trip, other ops fast-fail without fn invocation), and
  ``reset_cache_for_tests`` resets both new state variables.
  Zero changes to group-processing, Excel-generation, upload,
  or hash-history paths — the billing pipeline itself is
  untouched by this fix.
- [2026-04-24 11:30] Production over-pricing risk on the two
  original-contract folders. Operators report Smartsheet has now
  implemented the post-cutoff rates natively inside each sheet's
  ``Units Total Price`` column for sheets in folders
  ``7644752003786628`` and ``8815193070299012``
  (``ORIGINAL_CONTRACT_FOLDER_IDS``) whenever ``Snapshot Date >=
  2026-04-12`` and ``Units Completed? = true``. The Python-side
  pre-acceptance rate recalc in ``_fetch_and_process_sheet`` was
  still firing on those sheets (the existing gate only excluded
  subcontractor sheets), so for every post-cutoff row the
  Smartsheet-authoritative price was being overwritten in-place
  by ``rate × qty`` from ``NEW_RATES_CSV`` via
  ``recalculate_row_price``. Where the CSV and Smartsheet's
  formula agreed this was a no-op; where they disagreed (CU
  naming drift, work-type parsing edge cases, quantity
  interpretation), the row shipped with an over- or under-billed
  ``Units Total Price``. Root cause, not a symptom — running two
  pricing systems sequentially on the same row is the bug;
  fixing Smartsheet's formula or the CSV individually would not
  have closed the hole. **Fix (additive, production-safe):**
  (1) New env var ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT``
  (default ``'1'`` / True; accepts ``1``/``true``/``yes``/``on``)
  wired into the startup banner alongside
  ``RATE_RECALC_WEEKLY_FALLBACK`` so its resolved state is
  visible on every run. (2) New per-sheet flag
  ``is_original_contract_sheet = source['id'] in
  _FOLDER_DISCOVERED_ORIG_IDS`` computed once alongside
  ``is_subcontractor_sheet`` in ``_fetch_and_process_sheet``;
  ``_FOLDER_DISCOVERED_ORIG_IDS`` is populated unconditionally
  by ``discover_folder_sheets`` at the top of
  ``discover_source_sheets`` on every run (before the
  discovery-cache branch), so the membership test is reliable
  even when the cache is served warm. (3) Composite
  short-circuit ``_skip_recalc_original_contract`` fires only
  when ``RATE_CUTOFF_DATE`` is set AND the env var is on AND
  the sheet is in the ORIG folder AND the sheet is NOT a
  subcontractor sheet — preserving the existing subcontractor
  exclusion as primary (a sheet misconfigured into both sets
  still skips via the subcontractor path and the ORIG skip log
  never duplicates). (4) One ``🛡️`` info log per sheet when the
  guard fires; the row-level gate adds ``and not
  _skip_recalc_original_contract`` to short-circuit at zero
  cost per row without spamming logs. (5) Per-sheet "Rate
  recalc summary" is suppressed on skipped sheets (all counters
  are zero by construction — the summary would be noise). The
  single 🛡️ info log is the authoritative per-sheet signal.
  (6) The "Dropped VAC/helper row" warning's fallback-disabled
  ``_recalc_note`` branch gains ``and not
  _skip_recalc_original_contract`` so operators are not told
  to flip ``RATE_RECALC_WEEKLY_FALLBACK=1`` on sheets where
  doing so would not change anything (recalc is skipped by
  design). **What stays unchanged:** ``recalculate_row_price``,
  ``_resolve_rate_recalc_cutoff_date``,
  ``build_cu_to_group_mapping``, ``load_rate_versions``, the
  Weekly-Ref-Date fallback, the snapshot-keyed primary cutoff
  rule, subcontractor (Arrowhead) sheets' existing "keep
  SmartSheet price" behaviour, and every test currently locking
  in recalc behaviour for non-ORIG sheets. The fix is purely
  additive. **New rules:** (1) When an external system
  (Smartsheet here, any SaaS with server-side formulas) starts
  emitting authoritative values for a column we also compute
  locally, add a per-sheet / per-scope guard that short-circuits
  the local computation rather than trying to reconcile two
  independent sources row-by-row. Sequential double-writes on
  the same field are a silent-corruption trap: where the two
  systems agree, it's a no-op and no one notices; where they
  disagree, the last write wins and the disagreement ships to
  production unaudited. (2) Any such guard MUST be env-gated
  with a default-ON kill switch
  (``RATE_RECALC_SKIP_ORIGINAL_CONTRACT=0`` here) so operators
  can restore pre-fix behaviour if the external system's
  authoritative source breaks, without shipping a code change.
  (3) Log the guard's active state in the startup banner and
  emit one info log per sheet when it fires. Do NOT spam the
  row-level gate with a log — use the per-sheet flag as the
  single announcement surface. (4) Any follow-up operator note
  that suggests an env-var flip (e.g. "set
  ``RATE_RECALC_WEEKLY_FALLBACK=1`` to rescue this row") MUST
  gate on whether the flip would actually change this sheet's
  behaviour. On skipped sheets, tell the operator the correct
  story (or stay silent) — a false lead wastes on-call time.
  Regression tests:
  ``tests/test_subcontractor_pricing.py::TestOriginalContractFolderSkipsRateRecalc``
  (8 tests) covers the env-var wiring (exists + is ``bool``),
  the default folder-ID list (contains ``7644752003786628`` and
  ``8815193070299012``), the truth-table of the guard (fires on
  ORIG + cutoff + env on; does NOT fire on non-ORIG; does NOT
  fire with env off; does NOT fire without cutoff; does NOT
  fire on subcontractor sheets — subcontractor exclusion stays
  primary), and an isolation test that ``recalculate_row_price``
  itself is unchanged by the guard (callers invoking the helper
  directly still get the full recalc behaviour regardless of
  env vars).
- [2026-04-24 14:30] Retired the Python CSV-side rate recalc
  feature in production. Follow-up to the 11:30 entry above:
  rather than rely solely on the per-sheet
  ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` guard to protect the
  two original-contract folders, operators decided that since
  Smartsheet's native pricing is now authoritative for those
  folders, the entire CSV-side recalc path should be treated as
  legacy across the production workflow — there is no remaining
  production sheet that needs Python-side post-cutoff rate
  recalculation. **Change:** ``.github/workflows/weekly-excel-
  generation.yml`` now hardcodes ``RATE_CUTOFF_DATE: ''``,
  ``NEW_RATES_CSV: ''``, ``OLD_RATES_CSV: ''`` (was
  ``${{ vars.<NAME> || '' }}``) with a prominent LEGACY comment
  block explaining the retirement and revert path. A repo
  Variable that re-introduces a value is now ignored by the
  workflow — pinning the value at the workflow layer makes the
  decision code-reviewable through git history rather than
  hidden in GitHub Actions UI. **Defense-in-depth on the Python
  side:** ``generate_weekly_pdfs.py`` now emits a WARNING in the
  startup banner whenever ``RATE_CUTOFF_DATE`` is detected,
  pointing operators at this ledger entry. This catches local
  dev shells, ad-hoc scripts, or future workflows that might
  re-introduce the env var by accident. **What stays:** every
  recalc helper (``recalculate_row_price``,
  ``_resolve_rate_recalc_cutoff_date``,
  ``build_cu_to_group_mapping``, ``load_rate_versions``), the
  ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` guard from the prior
  commit on this branch, and every existing test. The code is
  retained intentionally so re-enablement is a one-line workflow
  revert (restore the three ``${{ vars.<NAME> || '' }}`` lines)
  rather than a code rewrite. **Docs:** ``website/docs/reference/
  environment.md`` "Rate contract versioning" section now leads
  with a Docusaurus ``:::caution LEGACY`` admonition pointing
  at this entry, and each row in the variable table is prefixed
  with ``(LEGACY)``. **New rules:** (1) When an external system
  takes over a column we used to compute locally AND there is no
  remaining local consumer that benefits from the local
  computation, retire the local feature in the workflow layer
  — do NOT just leave it env-gated. Workflow pinning is
  enforceable through git history; repo-Variable defaults are
  not. (2) Retire vs. delete: keep the code paths intact behind
  the workflow pin if the underlying business problem (post-
  cutoff billing) could realistically come back (rate contract
  renegotiation, new subcontractor, Smartsheet formula
  regression). The marginal carrying cost of retained code +
  tests is much lower than the cost of rewriting the recalc
  pipeline from scratch under incident pressure. (3) When
  retiring an env-var-gated feature, ALSO emit a runtime
  WARNING when the env var is detected — silent retirement is
  a footgun for any developer running locally with stale
  ``.env`` files. The WARNING must point at the ledger entry
  that explains why, not just say "deprecated". (4) Any future
  un-retire of this feature MUST be paired with explicit
  verification that the rows being re-priced are NOT already
  Smartsheet-priced for the same column. The
  ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` guard remains the
  default-on protection for the two folders documented in the
  11:30 entry above; if a future engineer disables the guard
  without confirming Smartsheet's formula has been removed
  first, the same silent-corruption trap reopens. No new tests
  are added for this retirement — existing tests in
  ``tests/test_subcontractor_pricing.py``, ``tests/test_vac_crew.py``,
  and ``tests/test_security_audit_followup.py`` already cover
  the retained code paths because they explicitly set
  ``RATE_CUTOFF_DATE`` in setUp/tearDown for isolation. Verified
  via ``pytest tests/`` (393 passed / 17 skipped) post-change.
- [2026-04-25 12:00] Production incident: every WR group in the
  2026-04-24 16:55 weekly run logged paired warnings for
  ``billing_audit[pipeline_run_select]`` (4 retries, "exhausted
  retries") and ``billing_audit[pipeline_run_upsert]`` (1 attempt,
  "immediate failures"), eventually tripping each per-op circuit
  breaker after 3 calls. The ``freeze_attribution`` RPC kept
  returning HTTP 200 OK throughout, isolating the failure to
  the ``pipeline_run`` table. **Two compounding root causes:**
  **(1) Schema drift, P0.** The ``pipeline_run`` reader/writer
  in ``billing_audit/writer.py`` (``emit_run_fingerprint``) was
  introduced on 2026-04-23 in commits ``56ec20a`` / ``1f8213a``
  / ``c44df3d``, but the matching ``CREATE TABLE
  billing_audit.pipeline_run`` was never committed and never
  applied to the deployed Supabase project. PostgREST therefore
  rejected every SELECT/UPSERT with PostgreSQL SQLSTATE ``42P01``
  (undefined_table) — or ``42703`` (undefined_column) on
  partial-deploy environments — surfaced as HTTP 400.
  **(2) Classifier blind spot, P1.**
  ``_classify_postgrest_error`` in ``billing_audit/client.py``
  recognised PGRST1xx/2xx/3xx prefixes and stringified HTTP 4xx
  codes, but did NOT recognise PostgreSQL SQLSTATE codes — even
  though the file's own preamble (``"or a SQLSTATE"`` at the
  ``APIError.code`` comment) acknowledged they were possible.
  When PostgREST returns ``{"code":"42703",...}``, that string
  fell through every check and landed in the catch-all transient
  branch, burning the full 4-attempt × (1.5+2.5+4.5s) backoff
  budget per call before each per-op breaker tripped. The
  asymmetry between SELECT (4 retries) and UPSERT (1 attempt)
  in the log is exactly this: the SELECT 400 carried a parseable
  ``code="42P01"`` (no PGRST/HTTP match → transient), the UPSERT
  400 carried ``code="400"`` from
  ``generate_default_error_message`` (HTTP-permanent match →
  bail). **Fix (additive, production-safe):** (1) Added
  ``billing_audit/schema.sql`` with canonical DDL for
  ``feature_flag``, ``pipeline_run``, and the
  ``freeze_attribution`` RPC parameter contract; ``ALTER TABLE
  … ADD COLUMN IF NOT EXISTS`` blocks let operators apply the
  fix to a partial pipeline_run without dropping data. (2) Added
  ``_PG_SQLSTATE_PERMANENT_PREFIXES = ("22", "23", "42")`` to
  ``billing_audit/client.py`` and a length-gated check in
  ``_classify_postgrest_error`` (only 5-char codes match,
  preventing false-positives against a hypothetical short PGRST
  code). (3) Updated ``billing_audit/__init__.py`` to point at
  ``schema.sql`` from the package docstring. (4) Five new tests
  in ``tests/test_billing_audit_shadow.py::PostgrestErrorClassificationTests``
  cover ``42P01``, ``42703``, classes 22/23 representative codes,
  the retryable SQLSTATE classes (``08``/``40``/``53``/``57``)
  that must NOT be added to the permanent list, and the
  ``len(code) == 5`` guard against short novel codes.
  **What stays unchanged:** the per-op circuit breaker, the
  run-global kill switch (``_disable_for_run``), the
  ``freeze_attribution`` RPC path, every existing classifier
  test, and the billing pipeline itself (Excel generation,
  Smartsheet upload, hash history are all unaffected by
  pipeline_run failures by design — see the 2026-04-24 10:50
  ledger entry's "fail-safe" rule). **New rules:**
  (1) Any new Supabase table or column the pipeline reads/writes
  MUST be defined in ``billing_audit/schema.sql`` in the same
  PR that adds the Python code. The repo cannot have a writer
  whose matching DDL exists only in a Supabase Dashboard
  somebody else's hands. Reviewers MUST block merges that add
  ``client.schema(...).table(...)`` references against a column
  not present in ``schema.sql``. (2) When a retry-classification
  helper accepts an exception type whose ``code`` field is
  documented as multi-source (PGRST codes, HTTP statuses, AND
  SQLSTATEs in our case), every documented source MUST have
  explicit handling AND a regression test. The pre-fix behaviour
  was correct for two of three sources — that's not "good
  enough", that's a silent-degradation trap. (3) When extending
  a code-prefix list (here: SQLSTATE classes), gate the prefix
  check on the format's known length (``len(code) == 5`` for
  SQLSTATEs) so a future PostgREST code that happens to start
  with the same digits cannot be accidentally swept into the
  permanent classification. (4) When adding entries to a
  permanent-prefix list, ALSO add a regression test that
  asserts the *retryable* siblings are NOT included — for
  SQLSTATEs that means ``08`` / ``40`` / ``53`` / ``57``
  classes must remain transient. Otherwise the next PR
  widening the list has no guard against suppressing the very
  conditions the retry loop exists for. Verified via
  ``pytest tests/test_billing_audit_shadow.py::PostgrestErrorClassificationTests -v``
  (22 passed, 54 subtests passed) post-fix.
- [2026-04-25 14:00] Production runtime regression: weekly workflow
  crept from ~1h baseline to 2-3h, often timing out before
  ``TIME_BUDGET_MINUTES=180`` allowed Excel generation to start.
  Operator burned through GitHub Actions minutes on runs that
  produced zero output. **Root cause:** the 2026-04-23 ``freeze_row``
  integration (commits ``56ec20a`` / ``1f8213a`` / ``c44df3d``) added
  a per-row Supabase RPC call inside the main group-processing loop
  in ``generate_weekly_pdfs.py`` (``for _row in group_rows:
  _billing_audit_writer.freeze_row(_row, ...)``) with NO parallelism.
  At ~120ms per ``freeze_attribution`` HTTP round-trip, a busy WR
  group with 30-150 rows costs 3.6-18 seconds purely on serial
  Supabase latency. Across 1900+ groups in a typical run, that
  compounded into ~2 hours of NEW wall-clock time on top of the
  pre-billing_audit ~1h baseline. The 2026-04-24 16:55-17:04
  production log confirmed it directly: ~8 ``freeze_attribution``
  POSTs per second sustained between WR group markers, hundreds in
  a row before each ``Skip (unchanged + attachment exists)`` line.
  **Fix (additive, production-safe):** wrap the ``freeze_row`` loop
  in a ``ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS,
  len(group_rows)))`` (cap 8, matching every other parallel I/O
  loop in the codebase). Single-row groups skip the executor to
  avoid setup overhead. Future-result iteration via
  ``as_completed`` swallows any unexpected exception per-row with a
  defensive ``logging.exception`` (including the sanitized
  ``__row_id`` so one bad row in a 100-row group can be pinpointed)
  so one bad row cannot kill the group's billing_audit work —
  ``freeze_row`` is fail-safe (catches its own errors). Expected
  speedup: 5-8× on the per-row RPC phase, restoring runtime to
  ~1.2h for a typical run with ~80% completed-row coverage.
  **Thread-safety analysis (the property the parallelization
  relies on, corrected after Copilot review feedback on PR #189):**
  (1) ``_counters`` writes go through ``_bump_counter`` which takes
  ``_counters_lock``. The bare ``dict[k] += 1`` is a multi-bytecode
  read-modify-write (``BINARY_SUBSCR`` → ``BINARY_ADD`` →
  ``STORE_SUBSCR``); the GIL holds each bytecode atomic but a
  thread can be preempted between them, so without the lock two
  threads can both read the counter at N, both compute N+1, and
  both store N+1 — losing one increment. The lock makes counter
  writes exact under any contention level; ``get_counters()``
  also takes the lock so the snapshot is internally consistent.
  (2) ``with_retry`` writes to ``_consecutive_failures`` /
  ``_open_circuits`` are NOT lock-protected today. Without
  protection a worker could observe the counter at 2 and another
  at 3 simultaneously, both classifying "below threshold" and
  producing one extra retry attempt before the breaker trips.
  **The 2026-04-25 inter-attempt re-check** ensures workers that
  started before the breaker opened will exit at the next retry
  boundary (``time.sleep(backoff)`` followed by a re-check of
  ``_open_circuits`` and ``_global_disable_reason``), bounding
  the worst-case retry storm to one extra round per in-flight
  worker. This addresses Codex P1 review feedback that
  parallelization without the inter-attempt check would let an
  outage generate up to 8 workers × 4 attempts = 32 doomed RPCs
  per op before the breaker engaged.
  Acceptable for a fail-safe metrics path. (3) ``get_client()``
  is memoized via ``_client_cache`` so concurrent ``freeze_row``
  callers share the same ``supabase.Client`` instance; the
  upstream library documents thread-safety for HTTP calls.
  **What stays unchanged:** ``freeze_row`` itself (signature,
  return value, error semantics), ``emit_run_fingerprint``
  (already once-per-group via dedup), every existing ``freeze_row``
  test, ``TIME_BUDGET_MINUTES``, ``PARALLEL_WORKERS`` env-var
  contract, and the budget-check at the top of the per-group loop
  (the parallelized inner block STILL counts against the budget;
  the budget guard simply fires on the next iteration). **New
  rules:** (1) Any new per-row I/O call inside the main group
  loop (``for _row in group_rows: api.foo(_row)``) MUST be
  parallelized via ``ThreadPoolExecutor(max_workers=
  min(PARALLEL_WORKERS, len(group_rows)))`` from the start, not
  added serial-first and parallelized later. The cost compounds
  across ~1900 groups × dozens of rows per group; serial-by-default
  is a P0 latency trap. Single-row guard (``if len(group_rows)
  <= 1``) avoids ThreadPoolExecutor setup overhead for the common
  helper / vac_crew variant case. (2) ``ThreadPoolExecutor``
  invocations of fail-safe writers MUST still wrap
  ``f.result()`` in ``try/except Exception`` with
  ``logging.exception`` — if the writer ever regresses and
  raises, the parallel iteration must not poison the rest of
  the group's writes. (3) When extending the per-group
  billing_audit block, also bump
  ``tests/validate_production_safety.py``
  ``validate_per_group_try_catches_all`` window cap to match
  the new block size — the validator scans a fixed character
  window from the block header to confirm the broad
  ``except Exception as _audit_err:`` is still present.
  Regression tests:
  ``tests/test_billing_audit_shadow.py::FreezeRowConcurrencyTests``
  covers (a) 50 concurrent ``freeze_row`` calls produce exactly
  50 counter outcomes (no silent drops, no exceptions) and
  (b) mixed completed / skipped rows under concurrent invocation
  preserve counter accuracy. Verified via ``pytest tests/`` →
  417 passed / 54 subtests passed post-fix (was 415 before; +2
  new concurrency tests).
