<!-- generated-by: gsd-doc-writer -->
# Getting Started

This guide takes you from a fresh clone to a verified local setup of the billing pipeline. It
covers the Python engine (`generate_weekly_pdfs.py` and the `pipeline/` package). The
`portal-v2/` and `website/` Node surfaces are optional and described only briefly under
[Next steps](#next-steps).

> **Production-critical.** This repository drives real billing automation on a GitHub Actions
> cron. Follow the safe local path below: it never uploads to Smartsheet. Do not change
> workflows, schedules, or billing logic as part of setup.

## Prerequisites

- **Python 3.10 or newer.** 3.10 is the lowest supported runtime (`pyproject.toml`); CI runs 3.12
  (`.github/workflows/weekly-excel-generation.yml`).
- **pip** (ships with Python).
- **git**.
- **A Smartsheet API token** — only needed for read-only runs against live data. The synthetic
  test mode and the test suite do not need one.
- **Node.js and npm** — only if you will work on `portal-v2/` or `website/`. Not needed for the
  Python engine.

No local database or container services are required; the pipeline talks directly to the
Smartsheet and Supabase APIs (or generates synthetic data in `TEST_MODE`).

## Installation

1. Clone the repository and enter it.

   ```bash
   git clone <repository-url>
   cd Generate-Weekly-PDFs-DSR-Resiliency-1
   ```

   <!-- VERIFY: remote repository URL (replace <repository-url> with the team's actual remote) -->

2. (Recommended) Create and activate a virtual environment.

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows (Git Bash): source .venv/Scripts/activate
   ```

3. Install the pinned runtime and test dependencies.

   ```bash
   pip install -r requirements.txt
   ```

   `requirements.txt` includes `pytest` and `pytest-cov`. Lint and type-check tooling (`ruff`,
   `mypy`) lives in `requirements-dev.txt` and is optional for first run:

   ```bash
   pip install -r requirements-dev.txt
   ```

4. Create your local environment file from the template and fill it in yourself.

   ```bash
   cp .env.example .env
   ```

   The Smartsheet token is read **only** from the environment (`.env` locally, repository secrets
   in CI). Set `SMARTSHEET_API_TOKEN` in your own `.env`; never paste a token into code, docs,
   issues, or commit messages, and never commit `.env`. The full variable catalog is in
   [configuration.md](configuration.md).

## First run

Start with the checks that cannot touch Smartsheet, then move to a dry run.

1. **Syntax check and test suite.** This is the gate that must pass before any push.

   ```bash
   python -m py_compile generate_weekly_pdfs.py
   pytest tests/ -v
   ```

2. **Synthetic run (safe, no token needed).** `TEST_MODE=true` generates synthetic data instead
   of reading Smartsheet. Blank the token explicitly: if a token is present in your `.env`,
   `TEST_MODE` reads every live source sheet (read-only, but large and slow).

   ```bash
   SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py
   ```

   This should complete without uploading anything and write generated workbooks to
   `generated_docs/` (the `.xlsx` files there are git-ignored).

3. **Optional: live read, no upload.** With a token in `.env`, `SKIP_UPLOAD=true` runs the full
   pipeline against live Smartsheet data and generates Excel files locally, but skips the
   delete-and-upload step.

   ```bash
   SKIP_UPLOAD=true python generate_weekly_pdfs.py
   ```

   To scope a synthetic run to specific work requests, combine `TEST_MODE` with `WR_FILTER`
   (comma-separated list) and optionally `MAX_GROUPS`:

   ```bash
   TEST_MODE=true SKIP_UPLOAD=true WR_FILTER=<wr-id-1>,<wr-id-2> python generate_weekly_pdfs.py
   ```

Never run the generator without `SKIP_UPLOAD=true` from a workstation: an unrestricted run
deletes and replaces row attachments on the target Smartsheet.

### Full validation harness

After moving or editing modules, run the 6-gate harness (API equality, facade completeness,
pytest, mypy delta, `py_compile`, and a synthetic run checked against the `run_summary.json`
structure):

```bash
bash scripts/run_6_gates.sh
```

The first failing gate aborts the run. The mypy gate needs the dev tooling from
`requirements-dev.txt`.

## Common setup issues

- **`ModuleNotFoundError` when running tests or the generator.** The virtual environment is not
  active, or dependencies were not installed. Re-activate it and run
  `pip install -r requirements.txt`.
- **A `TEST_MODE` run is unexpectedly slow or hits the API.** A real token in `.env` makes
  `TEST_MODE` fetch live sheets. Prefix the command with `SMARTSHEET_API_TOKEN=` (empty) as shown
  above.
- **Missing or invalid token on a live read.** `SMARTSHEET_API_TOKEN` is the one required
  variable. Confirm it is set in `.env`; do not echo it in a terminal that is being logged.
- **Unicode errors in Windows consoles.** Set `PYTHONUTF8=1` for the command, as in the synthetic
  run above.
- **Rate-limit errors from Smartsheet (HTTP 429).** The API allows 300 requests per minute. Keep
  `PARALLEL_WORKERS` at 8 or below; the SDK retries 429 responses automatically.
- **`git push` is blocked inside Claude Code.** `.github/hooks/pre-push-tests.json` blocks the
  push tool when `pytest tests/` fails. Fix the failing test; a plain shell push is not gated, so
  run `pytest tests/` manually first.
- **Do not `cd portal`.** The legacy Express `portal/` directory was removed; the web app is
  `portal-v2/`.

## Next steps

- [configuration.md](configuration.md) — environment variables, defaults, required versus
  optional settings, and local versus CI differences.
- [../ai/architecture.md](../ai/architecture.md) — module map, data stores, schedules, and the
  grouping and change-detection model.
- [../ai/safe-commands.md](../ai/safe-commands.md) — the verified command list, including
  diagnostics (`diagnose_pricing_issues.py`, `audit_billing_changes.py`).
- [../../README.md](../../README.md) — project overview.
- [../../CLAUDE.md](../../CLAUDE.md) — production guardrails to read before changing any
  pipeline behavior.
- `portal-v2/` (React, Vite, Supabase) and `website/` (Docusaurus runbook) each have their own
  `package.json`: run `npm install` then `npm run dev` / `npm run start` inside the directory.
  See `portal-v2/README.md` for its environment setup.
