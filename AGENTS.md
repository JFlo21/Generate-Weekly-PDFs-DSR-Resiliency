# AGENTS.md

## Project Overview

Production billing automation system that generates weekly Excel reports from Smartsheet data. Three main components:

- **Python core** (`generate_weekly_pdfs.py`): CLI pipeline that fetches Smartsheet rows, groups by Work Request, generates formatted Excel reports, and optionally uploads them back.
- **Portal** (`portal/`): Express.js backend serving a report viewer for GitHub Actions artifacts.
- **Portal v2** (`portal-v2/`): React/TypeScript frontend (Vite + Tailwind + Supabase) that proxies API calls to the Express backend.

## Tech Stack

| Component   | Stack                                                              |
| ----------- | ------------------------------------------------------------------ |
| Core        | Python 3.12, Smartsheet SDK, openpyxl, pandas, Sentry              |
| Portal      | Node.js 20+, Express 4, CommonJS, Vitest                          |
| Portal v2   | React 18, TypeScript, Vite 6, Tailwind CSS, Supabase, Framer Motion |
| CI/CD       | GitHub Actions, Azure DevOps mirror                                |

## Repository Layout

```
/                           Python scripts, config, requirements.txt
portal/                     Express backend (server.js, routes/, services/, middleware/)
portal-v2/                  React/TS frontend (src/, supabase/schema.sql)
scripts/                    Utility scripts (generate_artifact_manifest.py)
tests/                      Python tests (pytest)
generated_docs/             Output directory for Excel files (gitignored)
.github/workflows/          CI workflows (codecov, weekly-excel-generation, snyk, azure sync)
.github/instructions/       Copilot/agent instruction files
.github/prompts/            Contextual prompt files for AI agents
```

## Setup & Dependencies

### Python

```bash
pip install -r requirements.txt
```

### Portal (Express)

```bash
cd portal && npm install
```

### Portal v2 (React)

```bash
cd portal-v2 && npm install
```

## Running the Application

### Python core

```bash
# Synthetic test mode (no API token needed)
TEST_MODE=true python generate_weekly_pdfs.py

# Production run (requires SMARTSHEET_API_TOKEN in .env)
python generate_weekly_pdfs.py
```

### Portal backend

```bash
cd portal
npm start        # production (port 3000)
npm run dev      # watch mode
```

### Portal v2 frontend

```bash
cd portal-v2
npm run dev      # Vite dev server (port 5173, proxies /api to portal on 3000)
npm run build    # tsc -b && vite build
```

## Testing

### Python tests

```bash
pytest tests/                               # run all tests
pytest tests/ --cov                         # with coverage
pytest --cov=. --cov-branch --cov-report=xml  # CI command
```

### Portal tests (Vitest)

```bash
cd portal && npm test    # vitest run
```

### Portal v2

No automated test suite is configured. Lint with:

```bash
cd portal-v2 && npm run lint   # eslint (may require adding eslint as devDependency)
```

## Environment Variables

Copy the appropriate `.env.example` files before running:

```bash
cp .env.example .env                # root Python config
cp portal/.env.example portal/.env  # portal backend
cp portal-v2/.env.example portal-v2/.env  # portal v2 frontend
```

Key variables:

| Variable                 | Component  | Purpose                            |
| ------------------------ | ---------- | ---------------------------------- |
| `SMARTSHEET_API_TOKEN`   | Python     | Smartsheet API access              |
| `SENTRY_DSN`             | Python     | Error monitoring                   |
| `GITHUB_TOKEN`           | Portal     | GitHub Actions artifact access     |
| `GITHUB_OWNER`           | Portal     | GitHub repo owner                  |
| `GITHUB_REPO`            | Portal     | GitHub repo name                   |
| `VITE_SUPABASE_URL`      | Portal v2  | Supabase project URL               |
| `VITE_SUPABASE_ANON_KEY` | Portal v2  | Supabase anon key                  |

## CI/CD

CI runs on push/PR to `master`/`main`:

- **codecov.yml**: `pytest --cov=. --cov-branch --cov-report=xml` (Python 3.12)
- **snyk-security.yml**: Snyk Code, Open Source, IaC, and Container scans
- **weekly-excel-generation.yml**: Scheduled runs (every 2h weekdays) + manual dispatch
- **azure-pipelines.yml**: Mirrors `master` to Azure DevOps

## Code Conventions

### Python

- PEP 8 style, 4 spaces, 79-char lines
- PEP 257 docstrings, type hints via `typing`
- Env var pattern: `os.getenv('VAR', 'default')` with boolean parsing
- See `.github/instructions/python.instructions.md`

### JavaScript (Portal)

- ES2022, CommonJS, async/await
- Prefer functions over classes, `undefined` over `null`
- See `.github/instructions/nodejs-javascript-vitest.instructions.md`

### TypeScript (Portal v2)

- Strict TypeScript with `tsconfig.json`
- Tailwind CSS for styling
- React functional components with hooks

## Cursor Cloud Specific Instructions

### Running the Portal stack for manual testing

Start both the Express backend and Vite dev server:

```bash
# Terminal 1 - Portal backend
cd portal && npm run dev

# Terminal 2 - Portal v2 frontend
cd portal-v2 && npm run dev
```

The frontend at `http://localhost:5173` proxies API requests to `http://localhost:3000`.

### Running Python in test mode

No external API token is needed for local testing:

```bash
TEST_MODE=true python generate_weekly_pdfs.py
```

### When to perform manual GUI testing

- Any change to `portal-v2/src/**/*.tsx`, `*.css`, or Tailwind config should be tested in the browser.
- Any change to `portal/public/**` or `portal/routes/**` that affects API responses should be verified via the portal v2 frontend or `curl`.

### When automated tests are sufficient

- Python logic changes: run `pytest tests/`.
- Portal backend changes with existing test coverage: run `cd portal && npm test`.

## Additional Context

Deeper context for AI agents is available in:

- `.github/instructions/` - coding conventions, best practices, artifact guides
- `.github/prompts/` - domain-specific prompts (architecture, data processing, error handling, testing, change detection)
