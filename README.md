<div align="center">

<img src="https://github.com/user-attachments/assets/6f99f3d6-a519-47d8-bbf0-7cf8b356e773" alt="LineTec Services — A Centuri Company" width="480">

# LineTec Services — Weekly Billing Automation

**Production billing engine that turns Smartsheet field data into
polished, audit-ready weekly Excel reports — automatically.**

![Python](https://img.shields.io/badge/Python-3.10%2B-b22222?logo=python&logoColor=white)
![Smartsheet](https://img.shields.io/badge/Smartsheet-API-708090?logo=smartsheet&logoColor=white)
![Excel](https://img.shields.io/badge/Excel-openpyxl-b22222?logo=microsoftexcel&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-708090?logo=githubactions&logoColor=white)
![Sentry](https://img.shields.io/badge/Monitoring-Sentry-b22222?logo=sentry&logoColor=white)

</div>

---

## 🏗️ What This Repository Is

This is LineTec Services' **production billing automation system**. On a
cron schedule (roughly every 2 hours on weekdays), it:

1. **Connects to Smartsheet** and auto-discovers 13+ source sheets via
   folder-based discovery, validating column mappings.
2. **Fetches ~550 rows in parallel** (ThreadPoolExecutor, capped at 8
   workers to respect Smartsheet's 300 req/min rate limit).
3. **Filters and groups rows** by Work Request #, week-ending date,
   variant, foreman, department, and job.
4. **Detects changes** with SHA256 hashes per group so unchanged weeks
   are skipped (hashes live in Supabase `pipeline_memory.group_state`; the
   local `hash_history.json` cache was retired in Phase 11, INC-05).
5. **Generates styled Excel workbooks** (`openpyxl`) with the LineTec
   logo, formatted headers, and totals.
6. **Audits financial data** (`audit_billing_changes.py`) for price
   anomalies with LOW/MEDIUM/HIGH risk levels.
7. **Uploads the finished reports back to Smartsheet** as attachments
   on the target sheet.

```
Smartsheet API → discovery → parallel fetch → filter + group by WR/week
   → SHA256 change detection → Excel generation → audit → upload
```

## 📁 Repository Layout

| Path | Purpose |
|------|---------|
| `generate_weekly_pdfs.py` | Production entry point (facade over `pipeline/`) |
| `pipeline/` | Core engine modules — discovery, fetch, grouping, pricing, change detection, Excel, upload, cleanup |
| `audit_billing_changes.py` | Price anomaly / risk-level audit engine |
| `billing_audit/` | Supabase-backed audit fingerprinting and writer |
| `portal-v2/` | React 18 + TypeScript + Vite + Supabase dashboard (deploys to Vercel) |
| `website/` | Docusaurus living runbook (deploys to Vercel) |
| `scripts/` | Notion sync, artifact manifest, runbook, and Supabase publishing utilities |
| `tests/` | Pytest suite for the Python engine |
| `.github/workflows/weekly-excel-generation.yml` | Production cron + manual dispatch workflow |
| `generated_docs/` | Output directory (gitignored, safe to clear) |

## 🚀 Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and set:
SMARTSHEET_API_TOKEN=your_actual_api_token_here
```

To get a token: Smartsheet → profile picture → **Apps & Integrations**
→ **API Access** → **Generate new access token**.

### 3. Run

```bash
# Full production run
python generate_weekly_pdfs.py

# Local dry run — generate Excel files but skip Smartsheet upload
SKIP_UPLOAD=true python generate_weekly_pdfs.py

# Synthetic test mode — uses an in-memory dataset ONLY when
# SMARTSHEET_API_TOKEN is absent. If a token is set in your
# environment, the real Smartsheet client is used instead, so
# unset it to guarantee the synthetic, offline route:
SMARTSHEET_API_TOKEN= TEST_MODE=true python generate_weekly_pdfs.py

# Limit scope to specific Work Requests
SMARTSHEET_API_TOKEN= TEST_MODE=true WR_FILTER=WR_12345,WR_67890 python generate_weekly_pdfs.py
```

Generated files land in `generated_docs/` as
`WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}{variant}_{hash}.xlsx`.

## 🧪 Testing & Validation

```bash
pytest tests/ -v                               # full suite — must pass before push
pytest tests/ --cov                            # with coverage
python -m py_compile generate_weekly_pdfs.py   # syntax-only check
```

## ⚙️ Configuration

All behavior is controlled by **30+ environment variables** read via
`os.getenv()` with safe defaults. The most commonly used:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SMARTSHEET_API_TOKEN` | — | **Required.** Smartsheet API access |
| `TARGET_SHEET_ID` | `5723337641643908` | Destination sheet for Excel attachments |
| `AUDIT_SHEET_ID` | — | Destination for audit rows/stats |
| `SKIP_UPLOAD` | `false` | Generate locally without uploading |
| `TEST_MODE` | `false` | Synthetic data only when `SMARTSHEET_API_TOKEN` is absent |
| `RES_GROUPING_MODE` | `both` | `primary`, `helper`, or `both` |
| `WR_FILTER` | — | Comma list of Work Requests to process |
| `FORCE_GENERATION` | `false` | Bypass change detection |
| `RESET_HASH_HISTORY` | `false` | Force full regeneration in CI |
| `SENTRY_DSN` | — | Sentry.io error monitoring |

Full reference: `.github/prompts/configuration-environment.md` and
`.github/instructions/copilot-setup.instructions.md`.

## 🔄 CI/CD & Operations

- **`weekly-excel-generation.yml`** — production cron: 7 runs/day on
  weekdays, 3 runs/day on weekends, plus a weekly comprehensive Monday
  run. Manual dispatch supports an `advanced_options`
  `key:value,key:value` field (e.g.
  `max_groups:50,regen_weeks:081725;082425`).
- **`snyk-security.yml`** / **`python-lint.yml`** / **`ci-checks.yml`**
  — security scanning and lint/test gates.
- **`docs-changelog.yml`** — appends a runbook changelog entry on every
  merge to `master`.
- **Azure DevOps mirror** — see `README_AZURE.md`,
  `AZURE_QUICKSTART.md`, `AZURE_PIPELINE_SETUP.md`, and
  `AZURE_ARCHITECTURE.md`.
- **Sentry** — Python, Node, and React monitoring
  (`docs/sentry-implementation.md`).

## 🛠️ Utility Scripts

| Script | Purpose |
|--------|---------|
| `audit_billing_changes.py` | Monitor Smartsheet for unauthorized billing changes |
| `cleanup_excels.py` | Remove stale Excel files, preserving the latest per (WR, week) |
| `diagnose_pricing_issues.py` | Explain why work items were excluded due to pricing |
| `analyze_excel_totals.py` | Diagnostic tool for analyzing Excel file totals |
| `run_info.py` | List available scripts and usage |

## 📖 Documentation

- **`wiki.md`** — the in-repo wiki: architecture deep dive, data flow,
  and operations guide.
- **`website/`** — Docusaurus living runbook
  (`cd website && npm install && npm run start`).
- **`SECURITY.md`** — security policy and vulnerability reporting.
- **`memory-bank/`** — long-form project context and the Living Ledger
  of operational rules.
- **`AGENTS.md` / `CLAUDE.md`** — AI-agent working agreements for this
  codebase.

## 🆘 Support

| Problem | Where to look |
|---------|---------------|
| Smartsheet connection | Check `SMARTSHEET_API_TOKEN` in `.env` |
| Excel generation | Console logs (emoji-tagged: 🚀 ⚠️ ❌ ✅) |
| Change detection | `.github/prompts/change-detection-troubleshooting.md` |
| Azure pipeline | `README_AZURE.md` and companion docs |

---

<div align="center">

**LineTec Services** · *A Centuri Company*

⚡ Powering weekly billing operations with automation, accuracy, and audit trails. ⚡

</div>
