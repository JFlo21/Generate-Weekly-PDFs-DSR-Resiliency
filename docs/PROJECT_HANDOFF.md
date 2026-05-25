# Project Handoff — Setup on a New Computer

> **Goal:** clone this repo on another machine (desktop ⇄ laptop) and resume
> the AI-assisted workflow with full project context. This file covers the
> environment + tooling setup. For "where I left off," read
> [`AI_CONTEXT_RESUME.md`](./AI_CONTEXT_RESUME.md). For the authoritative
> project rules, read [`/CLAUDE.md`](../CLAUDE.md).
>
> **No secrets are stored in this repo.** All tokens/keys are provided via
> environment variables (local `.env`, never committed) or GitHub Actions
> secrets. See "Environment variables" below.

## 1. Project overview

A Python billing-automation pipeline plus two web surfaces:

- **`generate_weekly_pdfs.py`** — the production engine. Smartsheet → filter →
  group by Work Request + week → generate Excel (`openpyxl`) → upload
  attachments back to Smartsheet. Runs on a GitHub Actions cron (~every 2h on
  weekdays). Sibling: `audit_billing_changes.py`.
- **`portal/`** — legacy Express (Node 20+, CommonJS) artifact-viewing API.
- **`portal-v2/`** — React 18 + TypeScript + Vite + Tailwind + Supabase frontend.
- **`website/`** — Docusaurus runbook. **`scripts/`** — Notion sync + utilities.
- **`billing_audit/`** — Supabase read/write layer for claim attribution.

Full architecture + guardrails: [`/CLAUDE.md`](../CLAUDE.md).

## 2. Required tools

| Tool | Version | For |
|---|---|---|
| Python | 3.10+ (CI uses 3.11 and 3.12) | the billing engine + tests |
| Node.js | 20+ | `portal/`, `portal-v2/`, `website/` |
| Git | any recent | version control |
| GitHub CLI (`gh`) | optional | PRs, issue ops |
| Claude Code | latest | the AI workflow (see §7) |

## 3. Clone / pull the repo

This repo already has a remote (`origin`). On the new machine:

```bash
# First time:
git clone <your-origin-remote-url> Generate-Weekly-PDFs-DSR-Resiliency
cd Generate-Weekly-PDFs-DSR-Resiliency

# Already cloned — get the latest:
git fetch origin
git checkout master
git pull origin master

# To continue in-flight work, check out the relevant feature branch, e.g.:
#   git checkout feat/subproject-c-vac-crew-claim-attribution   (PR #219)
#   git checkout ai-context-portability                          (this context branch)
```

(The remote URL is whatever `git remote -v` prints in your existing clone —
this handoff intentionally does not hard-code machine-specific paths.)

## 4. Install dependencies

```bash
# Python engine
pip install -r requirements.txt

# Portal (Express backend)
cd portal && npm install && cd ..

# Portal-v2 (React frontend)
cd portal-v2 && npm install && cd ..

# Docusaurus runbook
cd website && npm install && cd ..
```

## 5. Environment variables (placeholders only — never commit real values)

Copy the example files and fill in your own values locally. **Do not commit
`.env`/`.env.local`** (they are gitignored).

```bash
cp .env.example .env                    # root: SMARTSHEET_API_TOKEN, SENTRY_DSN, ...
cp portal-v2/.env.example portal-v2/.env.local   # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
```

| Variable | Where | Notes |
|---|---|---|
| `SMARTSHEET_API_TOKEN` | root `.env` + GitHub Actions secret | **Required** for real runs. Omit + use `TEST_MODE=true` for synthetic runs. |
| `SENTRY_DSN` | root `.env` + GitHub Actions secret | Error monitoring. Optional locally. |
| `AUDIT_SHEET_ID` | root `.env` | Optional audit tracking. |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | `portal-v2/.env.local` | Frontend Supabase (anon key only — never the service-role key). |
| `SUPABASE_SERVICE_ROLE_KEY` | GitHub Actions secret only | Used by `billing_audit/`; **never** put in a committed file or the frontend. |

The full 30+ env-var reference is in `CLAUDE.md` and
`.github/prompts/configuration-environment.md`. For production, secrets live in
**GitHub repository secrets** (Settings → Secrets and variables → Actions), not
in any file.

## 6. Run / verify locally

```bash
# Python engine — synthetic mode (no API token needed)
TEST_MODE=true python generate_weekly_pdfs.py

# Tests (must pass before pushing)
pytest tests/ -v

# Syntax-only check
python -m py_compile generate_weekly_pdfs.py

# Portal-v2 dev (needs the Express backend running for /api proxy)
cd portal && npm start         # terminal 1 (:3000)
cd portal-v2 && npm run dev    # terminal 2 (:5173)
```

## 7. AI tooling — reproduce the Claude Code workflow

This project's AI workflow relies on **Claude Code plugins/skills installed at
the user level** (`~/.claude/`), not committed into the repo (they are generic,
cross-project framework tooling that updates independently). To get the same
workflow on the new machine, install the same plugins/marketplaces. The set in
use here (from the user-level `~/.claude/settings.json` `enabledPlugins`):

- **superpowers** — TDD, brainstorming, writing-plans, subagent-driven
  development, systematic-debugging, code-review, finishing-a-branch
  (`claude-plugins-official`).
- **GSD** suite — phase/plan/execute workflow skills + agents (installed as
  user-level skills/agents under `~/.claude/skills/` and `~/.claude/agents/`).
- **context-mode** (`context-mode` marketplace) — context-window protection /
  sandboxed command + search tooling.
- **claude-mem** (`thedotmack` marketplace) — cross-session memory; its query
  MCP tools require the worker running: `npx claude-mem start`
  (web viewer at `http://localhost:37777`).
- Plus the official set used incidentally: context7, code-review, supabase,
  sentry, plugin-dev, huggingface-skills, microsoft-docs, etc.

Install via Claude Code's plugin manager (the marketplaces above) on the new
machine. **Do not** copy `~/.claude/settings.local.json`, auth/session files,
hooks with machine-specific absolute paths, or tokens — those are
machine-specific and/or sensitive.

### Project-specific AI context that IS in the repo (auto-loaded / referenced)

- [`/CLAUDE.md`](../CLAUDE.md) — authoritative project rules + Living Ledger
  (Claude Code loads this automatically from the repo root).
- [`/AGENTS.md`](../AGENTS.md) — Codex-targeted mirror of the same context.
- `.claude/rules/` — `smartsheet-python-optimization.md`,
  `documentation-maintenance.md`.
- `.github/instructions/`, `.github/prompts/`, `.github/copilot-instructions.md`
  — Copilot/assistant instructions + domain prompts.
- `.github/agents/smartsheet-debugger.agent.md` — pipeline-debugging agent.
- `docs/superpowers/specs/` + `docs/superpowers/plans/` — design specs +
  implementation plans for the claim-attribution sub-projects.
- `memory-bank/` — longer-form project context.

## 8. Verify Claude Code has the project context

After opening Claude Code from the repo root, confirm:

1. It references `CLAUDE.md` rules (e.g. ask "what are the Smartsheet
   guardrails?" — it should cite the `@cell` restriction + additive-only rule).
2. The expected skills are available (e.g. `superpowers:brainstorming`,
   `gsd-*`). If `claude-mem` search is desired, run `npx claude-mem start`
   first so its MCP tools register at session start.
3. Read `docs/AI_CONTEXT_RESUME.md` for the latest status.

## 9. Update this handoff before stopping work

- Update `docs/AI_CONTEXT_RESUME.md` (status, open tasks, decisions).
- Append decisions to the `CLAUDE.md` Living Ledger with a `[YYYY-MM-DD HH:MM]`
  timestamp.
- Commit + push so the other machine pulls the latest context.
- Never commit secrets — re-check `git diff --staged` before committing.
