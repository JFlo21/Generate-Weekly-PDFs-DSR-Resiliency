# Project Guidelines

## Overview

Production billing automation: Smartsheet API → row filtering → WR grouping → Excel generation → upload. Processes ~550 rows across 13+ sheets on a cron schedule. **Do not break the pipeline.**

Three components:
- **`generate_weekly_pdfs.py`** — Core Python billing engine (production entry point)
- **`portal/`** — Legacy Express backend (Node 20+, ESM)
- **`portal-v2/`** — React + TypeScript + Supabase frontend (Vite, Tailwind)

## Build and Test

```bash
# Python (core engine)
pip install -r requirements.txt
pytest tests/ -v                          # 33 tests, all must pass
python -m py_compile generate_weekly_pdfs.py  # syntax check

# Portal v2 (React frontend)
cd portal-v2 && npm install && npm run build

# Portal (Express backend)
cd portal && npm install && npm run test
```

## Architecture

- **Data flow**: `generate_weekly_pdfs.py` auto-discovers source sheets via folder IDs, validates columns, fetches rows in parallel (ThreadPoolExecutor), groups by WR + week, generates styled Excel with openpyxl, uploads to Smartsheet
- **Change detection**: SHA256 hash per (WR, week, variant, foreman, dept, job) — skips unchanged groups
- **Audit**: `audit_billing_changes.py` tracks price anomalies with risk levels (LOW/MEDIUM/HIGH)
- **CI/CD**: GitHub Actions scheduled runs (every 2 hrs weekdays), Azure DevOps sync on push
- See `.github/prompts/architecture-analysis.md` for full decomposition

## Conventions

- **Python**: PEP 8, type hints, 4-space indent, max 79 chars. See `.github/instructions/python.instructions.md`
- **Node.js**: ES2022+, async/await, no callbacks, no `null`. See `.github/instructions/nodejs-javascript-vitest.instructions.md`
- **Config**: All behavior controlled by 30+ env vars via `os.getenv()` with defaults. See `.github/instructions/copilot-instructions.md` (in `instructions/`) for full list
- **Editing philosophy**: Minimal, surgical changes. Preserve existing structure. See `.github/instructions/taming-copilot.instructions.md`
- **Subcontractor sheets**: Folder-based discovery is primary. See `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`

## Critical Pitfalls

- **Smartsheet rate limit**: 300 req/min — parallel workers capped at 8; SDK handles 429 retries
- **Hash history is ephemeral in CI** — set `RESET_HASH_HISTORY=true` for full regeneration
- **Helper rows**: Require `helper_dept` + `helper_foreman`; Job # is optional
- **Excel corruption**: Use `safe_merge_cells()` with overlap detection; never write `oddFooter.right.text`
- **GitHub Actions 10-input limit**: `advanced_options` field parses `key:value,key:value` format
- See `.github/prompts/change-detection-troubleshooting.md` and `.github/prompts/error-handling-resilience.md`

## Key Files

| File | Purpose |
|------|---------|
| `generate_weekly_pdfs.py` | Core billing engine (~2950 lines) |
| `audit_billing_changes.py` | Price anomaly detection, imported by main |
| `.github/workflows/weekly-excel-generation.yml` | Production cron + manual dispatch |
| `generated_docs/hash_history.json` | Change detection cache |
| `portal-v2/src/` | React dashboard (Supabase auth, RLS) |
| `portal-v2/supabase/schema.sql` | Database schema with RLS policies |

## Detailed References

Domain-specific guides live in `.github/prompts/` and `.github/instructions/`. Key ones:
- **Business logic**: `.github/prompts/data-processing-business-logic.md`
- **Performance**: `.github/instructions/performance-optimization.instructions.md`
- **Testing**: `.github/prompts/testing-and-validation.md`
- **Config/env vars**: `.github/prompts/configuration-environment.md`
- **CI/CD**: `.github/instructions/github-actions-ci-cd-best-practices.instructions.md`
