<div align="center">

<img src="https://github.com/user-attachments/assets/6f99f3d6-a519-47d8-bbf0-7cf8b356e773" alt="LineTec Services — A Centuri Company" width="480">

# 📚 Project Wiki

**LineTec Services — Weekly Billing Automation & Excel Generation**

*The in-repo knowledge base for how the system works, how to operate
it, and where everything lives.*

</div>

---

## Table of Contents

1. [Overview](#-overview)
2. [System Architecture](#-system-architecture)
3. [Data Pipeline Deep Dive](#-data-pipeline-deep-dive)
4. [Business Rules](#-business-rules)
5. [Configuration Reference](#-configuration-reference)
6. [CI/CD & Scheduling](#-cicd--scheduling)
7. [Operations Runbook](#-operations-runbook)
8. [Companion Applications](#-companion-applications)
9. [Troubleshooting & FAQ](#-troubleshooting--faq)
10. [Further Reading](#-further-reading)

---

## 🏢 Overview

LineTec Services (a Centuri company) performs electrical distribution
and transmission field work. Crews log completed units in
**Smartsheet**; this repository converts those logs into **weekly,
Work-Request-based Excel billing reports** and attaches them back to
Smartsheet — automatically, on a schedule, with a full audit trail.

**Scale:** ~550 rows per run across 13+ source sheets, processed every
~2 hours on weekdays.

**Guiding principle:** *do not break the pipeline.* The engine is
production-critical; all changes must be additive, minimal, and tested
(`pytest tests/ -v`).

## 🧱 System Architecture

Three coupled components share one contract:

| Component | Stack | Role |
|-----------|-------|------|
| **Billing engine** | Python 3.10+, `smartsheet-python-sdk`, `openpyxl` | Production entry point `generate_weekly_pdfs.py`, a facade over the modular `pipeline/` package |
| **`portal-v2/`** | React 18, TypeScript, Vite, Tailwind, Supabase | Operations dashboard (auth + RLS), deploys to Vercel |
| **`website/`** | Docusaurus | Living runbook, auto-updated changelog on every merge to `master` |

Supporting modules:

- **`pipeline/`** — `discovery.py`, `fetch.py`, `grouping.py`,
  `pricing.py`, `change_detection.py`, `excel.py`, `upload.py`,
  `cleanup.py`, `attribution.py`, `orchestrate.py`, `retry.py`,
  `observability.py`, `config.py`.
- **`audit_billing_changes.py`** — price anomaly detection with
  LOW/MEDIUM/HIGH risk levels and delta tracking.
- **`billing_audit/`** — Supabase-backed audit fingerprinting/writer.
- **`scripts/`** — Notion sync, artifact manifests, runbook entries,
  Supabase artifact publishing.
- **Monitoring** — Sentry across Python, Node, and React.
- **Mirror** — Azure DevOps sync on push (`azure-pipelines.yml`).

## 🔄 Data Pipeline Deep Dive

```
Smartsheet API
   ↓  folder-based discovery (SUBCONTRACTOR_FOLDER_IDS,
   ↓  ORIGINAL_CONTRACT_FOLDER_IDS, VAC_CREW_FOLDER_IDS),
   ↓  cached in generated_docs/discovery_cache.json
Auto-discover source sheets → validate column mappings
   (synonyms for "Weekly Reference Logged Date", helper_dept,
    helper_foreman, Job # variations)
   ↓
Parallel row fetch (ThreadPoolExecutor, PARALLEL_WORKERS ≤ 8;
   SDK retries 429s under the 300 req/min rate limit)
   ↓
Filter + group by (WR, week_ending, variant, foreman, dept, job)
   ↓
Pre-fetch target-row attachments into an in-memory cache
   (sub-budgeted; per-future timeout; falls back to per-row lookup)
   ↓
SHA256 change detection per group key → skip unchanged
   (generated_docs/hash_history.json, capped at 1000 entries)
   ↓
Excel generation (openpyxl): LineTec logo, headers, styling, totals
   → WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}{variant}_{hash}.xlsx
   ↓
Audit (audit_billing_changes.py): anomalies, risk levels, deltas
   ↓
Upload to TARGET_SHEET_ID (delete old attachment, then upload)
```

**Row inclusion rules** — a source row must have:

1. A Work Request # (the grouping key)
2. The *Units Completed?* checkbox checked
3. A positive Units Total Price
4. A valid Weekly Reference Logged Date

## 📏 Business Rules

- **Change-detection key includes `foreman, dept, job`** — helper
  Excel files regenerate when new rows arrive for past weeks. Never
  shorten the key back to `(WR, week, variant, foreman)`.
- **Helper rows** require both `helper_dept` and `helper_foreman`
  (Job # optional). Rows with *both* "Helping Foreman Completed
  Unit?" and "Units Completed?" checked appear **only** in helper
  files — never the main file — to prevent double-counting.
- **Variants**: main (no suffix), `_User_<foreman>`,
  `_Helper_<foreman>`, `_VacCrew`.
- **Excel safety**: always use `safe_merge_cells()` (overlap
  detection); never write `oddFooter.right.text`.
- **Smartsheet formulas**: never use `@cell` from Python — it is a
  UI-only construct and will fail via the API.
- **Job # synonyms** (`Job #`, `Job#`, `Job Number`, …) must not be
  collapsed.

## ⚙️ Configuration Reference

Everything is environment-variable driven (`os.getenv()` with
defaults). Required: **`SMARTSHEET_API_TOKEN`**.

| Category | Variables |
|----------|-----------|
| Core integration | `TARGET_SHEET_ID` (default `5723337641643908`), `AUDIT_SHEET_ID`, `SENTRY_DSN` |
| Run modes | `TEST_MODE`, `SKIP_UPLOAD`, `FORCE_GENERATION`, `WR_FILTER`, `MAX_GROUPS`, `RES_GROUPING_MODE` (`primary`/`helper`/`both`) |
| Change detection | `RESET_HASH_HISTORY`, `EXTENDED_CHANGE_DETECTION`, `REGEN_WEEKS`, `RESET_WR_LIST`, `KEEP_HISTORICAL_WEEKS` |
| Performance | `USE_DISCOVERY_CACHE`, `DISCOVERY_CACHE_TTL_MIN` (default 10080 = 7 days), `SKIP_CELL_HISTORY`, `PARALLEL_WORKERS` (≤ 8) |
| Time budgets (CI) | `TIME_BUDGET_MINUTES` (workflow sets 165), `ATTACHMENT_PREFETCH_MAX_MINUTES` (10), `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` (45) |
| Debugging | `DEBUG_MODE`, `QUIET_LOGGING`, `PER_CELL_DEBUG_ENABLED`, `FILTER_DIAGNOSTICS`, `FOREMAN_DIAGNOSTICS`, `LOG_UNKNOWN_COLUMNS`, `DEBUG_SAMPLE_ROWS` |
| Privacy | `SENTRY_ENABLE_LOGS` (default `false` — keep off; logs can embed row PII) |

Full details: `.github/prompts/configuration-environment.md`.

## 🚀 CI/CD & Scheduling

**Production workflow:** `.github/workflows/weekly-excel-generation.yml`

| Schedule | Cadence |
|----------|---------|
| Weekdays (Mon–Fri) | 7 runs/day (UTC 13, 15, 17, 19, 21, 23, 01) |
| Weekends | 3 runs/day (UTC 15, 19, 23) |
| Weekly deep run | UTC Monday 05:00 (Sunday 11 PM Central) |

- Runner ceiling `timeout-minutes: 180`; Python graceful stop at
  `TIME_BUDGET_MINUTES=165`. The 15-minute gap protects cache-save and
  artifact-upload steps — never raise one without the other.
- **Manual dispatch** packs rare controls into a single
  `advanced_options` input parsed as `key:value,key:value`:
  `max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456`.
  Do not remove this parser — runbooks depend on it.
- Other workflows: `snyk-security.yml`, `python-lint.yml`,
  `ci-checks.yml`, `docs-changelog.yml`, `notion-sync.yml`,
  `system-health-check.yml`, `azure-pipelines.yml` (Azure mirror).

## 🛠️ Operations Runbook

### Everyday commands

```bash
pip install -r requirements.txt
pytest tests/ -v                                   # must pass before push
python -m py_compile generate_weekly_pdfs.py       # syntax check

SKIP_UPLOAD=true python generate_weekly_pdfs.py    # local dry run
TEST_MODE=true python generate_weekly_pdfs.py      # synthetic data, no token

python diagnose_pricing_issues.py                  # pricing exclusions
python audit_billing_changes.py                    # audit sweep
python cleanup_excels.py                           # stale file cleanup
python run_info.py                                 # script inventory
```

### Common operational plays

| Goal | How |
|------|-----|
| Force full regeneration in CI | Dispatch workflow with `reset_hash_history: true` |
| Regenerate specific weeks | `advanced_options: regen_weeks:081725;082425` |
| Reprocess specific WRs | `wr_filter: WR123,WR456` |
| Debug row exclusions | `FILTER_DIAGNOSTICS=true FOREMAN_DIAGNOSTICS=true` |
| Inspect column mapping | `LOG_UNKNOWN_COLUMNS=true DEBUG_SAMPLE_ROWS=5 PER_CELL_DEBUG_ENABLED=true` |

### Institutional memory

- **`memory-bank/living-ledger.md`** — the Living Ledger: dated
  incident root-causes and engineering rules. **Consult it before
  changing grouping, hashing, filename, attachment-cleanup, or
  attribution code.**
- `memory-bank/` — project brief, system patterns, tech context,
  active context, progress.

## 🖥️ Companion Applications

### Portal v2 (`portal-v2/`)

```bash
cd portal-v2 && npm install
cp .env.example .env.local     # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
npm run dev                    # Vite on :5173
npm run build                  # tsc -b && vite build
npm run lint                   # eslint --max-warnings 0
```

React dashboard with Supabase auth + Postgres RLS. Deploys to Vercel.
Schema: `supabase/portal_schema.sql` and `portal-v2/README.md`.

### Docusaurus runbook (`website/`)

```bash
cd website && npm install
npm run start                  # local dev
npm run build && npm run typecheck
```

Every merge to `master` appends a changelog entry via
`docs-changelog.yml`.

## ❓ Troubleshooting & FAQ

**Q: A sheet isn't being discovered.**
Check that it has the required *Weekly Reference Logged Date* column
(synonyms supported). Sheets missing it are skipped with a ⚠️ log.
Also try `USE_DISCOVERY_CACHE=false` to bypass a stale cache.

**Q: A WR group didn't regenerate after data changed.**
Hash-based change detection may consider it unchanged. Use
`FORCE_GENERATION=true` locally or dispatch with
`reset_hash_history: true`. See
`.github/prompts/change-detection-troubleshooting.md`.

**Q: Rows are missing from the report.**
Verify the four inclusion rules (WR #, Units Completed checked,
positive price, valid date). Run with `FILTER_DIAGNOSTICS=true` to get
exclusion-reason counts.

**Q: We're hitting Smartsheet 429s.**
The SDK retries automatically; never raise `PARALLEL_WORKERS` above 8.
Enable `SKIP_CELL_HISTORY=true` to reduce call volume.

**Q: Where do generated files go?**
`generated_docs/` — gitignored and safe to clear. In CI, artifacts are
organized and preserved per
`.github/instructions/artifact-preservation-guide.instructions.md`.

## 📖 Further Reading

| Topic | Location |
|-------|----------|
| Architecture decomposition | `.github/prompts/architecture-analysis.md` |
| Business logic rules | `.github/prompts/data-processing-business-logic.md` |
| Env-var deep dive | `.github/prompts/configuration-environment.md` |
| Testing strategy | `.github/prompts/testing-and-validation.md` |
| Error handling & resilience | `.github/prompts/error-handling-resilience.md` |
| Subcontractor folder discovery | `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md` |
| Azure DevOps mirror | `README_AZURE.md`, `AZURE_QUICKSTART.md`, `AZURE_PIPELINE_SETUP.md`, `AZURE_ARCHITECTURE.md` |
| Sentry wiring | `docs/sentry-implementation.md` |
| Security policy | `SECURITY.md` |

---

<div align="center">

**LineTec Services** · *A Centuri Company*

⚡ Field data in. Billing-ready reports out. Every two hours. ⚡

</div>
