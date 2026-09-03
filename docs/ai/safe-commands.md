Repo-local implementation truth — outranks second-brain notes; verified from repo files on 2026-09-02.

<!-- This file is repo-local IMPLEMENTATION TRUTH. Only mark VERIFIED after reading the exact
script/CI step or running the command. Never put secrets/env values here — env var NAMES only. -->

# Safe Commands — Generate-Weekly-PDFs-DSR-Resiliency-1

## Source-of-truth hierarchy (highest authority first)

1. Current repo files. 2. Repo-local `docs/ai/` + `.claude/project-state.md`. 3. Repo-local handoff
docs. 4. Global second brain. 5. Global wiki. 6. `raw/` (data only). 7. Chat history / claude-mem.

> [!warning] Destructive commands
> Destructive operations (`git reset --hard`, `git push --force`, `rm -rf`, dropping/migrating
> production data, prod deploys) are governed by the global `warn_production_commands` hook. Never
> bypass it. Treat any command touching production data or remote state as needing explicit
> confirmation even if listed below.

---

## Commands

### Install dependencies
- `pip install -r requirements.txt` (Python core engine)
- `cd portal-v2 && npm install` / `cd website && npm install` (Node surfaces)
- Status: **VERIFIED** — read from `CLAUDE.md` "Build, Test, and Run Commands"

### Build
- `python -m py_compile generate_weekly_pdfs.py` (syntax-only check of the facade)
- `cd portal-v2 && npm run build` (`tsc -b && vite build`)
- `cd website && npm run build` (Docusaurus)
- Status: **VERIFIED** — `CLAUDE.md`

### Test
- `pytest tests/ -v` — full suite, must pass before push
- `pytest tests/test_subcontractor_pricing.py -v` — single file
- `pytest tests/test_vac_crew.py::test_name -v` — single test
- `pytest tests/ --cov` — with coverage
- `cd portal-v2 && npm run lint` — `eslint --max-warnings 0` (Node)
- `bash scripts/run_6_gates.sh` — full 6-gate validation harness (see below)
- Status: **VERIFIED** — `CLAUDE.md`, `scripts/run_6_gates.sh`

### 6-gate harness (`scripts/run_6_gates.sh`) — gate order
1. `python scripts/check_api_equality.py` — AST import equality
2. `python scripts/check_facade_completeness.py` — facade completeness
3. `python -m pytest tests/ -q`
4. `bash scripts/check_mypy_delta.sh` — mypy delta
5. `python -m py_compile generate_weekly_pdfs.py`
6. `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py >/dev/null`
   then `python scripts/check_run_summary_structure.py` — structural oracle over `run_summary.json`
   (not a correctness check on real data; runs `set -euo pipefail`, first non-zero gate aborts).
- Status: **VERIFIED** — read `scripts/run_6_gates.sh` in full.

### Local dry run (no Smartsheet upload)
- `SKIP_UPLOAD=true python generate_weekly_pdfs.py`
- Status: **VERIFIED** — `CLAUDE.md`

### Synthetic test mode (no API token required)
- `TEST_MODE=true python generate_weekly_pdfs.py`
- `TEST_MODE=true WR_FILTER=WR_12345,WR_67890 python generate_weekly_pdfs.py`
- Status: **VERIFIED** — `CLAUDE.md`

### Diagnostics
- `python diagnose_pricing_issues.py`
- `python audit_billing_changes.py`
- `python cleanup_excels.py`
- `python run_info.py` — lists available scripts
- Status: **VERIFIED** — `CLAUDE.md`

### Run / dev (frontend surfaces)
- `cd portal-v2 && npm run dev` — Vite on `:5173`
- `cd website && npm run start` — Docusaurus local dev
- Status: **VERIFIED** — `CLAUDE.md`

### Deploy
- Python engine: no manual deploy command — runs on GitHub Actions cron
  (`.github/workflows/weekly-excel-generation.yml`, `timeout-minutes: 180`) or `workflow_dispatch`.
- `portal-v2/` and `website/` deploy to Vercel (README/CLAUDE.md); exact deploy trigger/command —
  NEEDS_VERIFICATION (no Vercel CI config read this pass).
- Status: **NEEDS_VERIFICATION** for the exact deploy trigger · governed by `warn_production_commands`
  for anything that mutates the production schedule.

## Protected areas — need Juan's explicit approval before changing (CLAUDE.md / `.claude/rules/`)

- Smartsheet live-write behavior; Supabase RLS/policies/migrations/schema/`service_role`/auth.
- Billing/reporting formulas and outputs (validate against a known-good sample first).
- GitHub Actions workflows, schedules, and deployments (inspect-only by default; SHA-pin 3rd-party
  actions; never push directly to `main`).
- Env/secrets files and real credential values.
- Protected Resiliency workflows list (Crew Roster, Resource Analyst/Bret Berry sheet, ProMax
  database sheets, Master ProMax View 2, Resiliency ProMax Database Report, Dynamic View/foreman
  view, Excel billing output, Supabase scorecard, PPP→Parser→Cognos flow, ProMax backend column
  logic, No Match/department mapping, foreman dept-number mapping, helper-row/snake-case matching,
  grouping codes/point numbers/work types, snapshot date vs weekly-reference-log date, base units vs
  labor adders, parser web check, stale ProMax job-number workflow/counter logic) —
  `~/.claude/rules/production-guardrails.md`.
- `PARALLEL_WORKERS` must never exceed 8 (Smartsheet 300 req/min rate limit).
- Never use/write the Smartsheet `@cell` formula in Python or API payloads.

## Notes

- Required env var names (values never stored here): `SMARTSHEET_API_TOKEN` (required),
  `TARGET_SHEET_ID`, `AUDIT_SHEET_ID`, `SENTRY_DSN`, plus the ~30 optional behavior-flag vars
  documented in `CLAUDE.md` "Configuration — 30+ Environment Variables" (`SKIP_UPLOAD`, `TEST_MODE`,
  `RES_GROUPING_MODE`, `WR_FILTER`, `MAX_GROUPS`, `RESET_HASH_HISTORY`, `TIME_BUDGET_MINUTES`, etc.).
  Exact Supabase client env var names for `pipeline_memory`/`billing_audit` — NEEDS_VERIFICATION.
- Required toolchain: Python 3.10+ locally (3.12 in CI per `CLAUDE.md`); Node.js/npm for
  `portal-v2`/`website`.
- `.github/hooks/pre-push-tests.json` is a Claude Code hook (not a git hook) — it blocks the `git
  push` *tool* if `pytest tests/` fails when run inside Claude Code. A plain shell push is not
  gated; run `pytest tests/` manually first.
- No local services (DB/containers) are required to run `pytest tests/` or the dry-run modes — the
  pipeline talks directly to Smartsheet/Supabase APIs (or synthetic data in `TEST_MODE`).

## Last verified

- Last verified: 2026-09-02 — read `CLAUDE.md` "Build, Test, and Run Commands" +
  "Configuration" sections, `scripts/run_6_gates.sh` in full, and `docs/AI_CONTEXT_RESUME.md`
  "Verify the project (commands)" section (cross-check, no discrepancies found).
