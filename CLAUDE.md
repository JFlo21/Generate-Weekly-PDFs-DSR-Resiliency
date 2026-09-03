# CLAUDE.md

Guidance for Claude Code in this repository: rules, guardrails, and pointers only. Architecture,
env vars, schedules, and history live in the files linked below (trimmed 2026-09-02 by the
`align-instruction-files` skill — nothing deleted, only moved; see ledger `[2026-09-02 22:05]`).

## What this repo is

Production billing automation. `generate_weekly_pdfs.py` (a thin facade over the `pipeline/`
package) pulls ~550 daily-status rows from 13+ Smartsheet sheets, groups them by Work Request +
week ending (+ variant, foreman, dept, job), generates styled Excel workbooks with `openpyxl`,
and uploads them back to Smartsheet as row attachments on a GitHub Actions cron roughly every
2 hours on weekdays. It is **production-critical**: additive, surgical changes only. Never
replace or redesign the Smartsheet → Excel → Smartsheet pipeline unless explicitly asked.

Three coupled components share one contract (full map: `docs/ai/architecture.md`):
1. Python billing engine — `generate_weekly_pdfs.py` → `pipeline/`, plus `audit_billing_changes.py`
   (price-anomaly audit) and the Supabase layers `billing_audit/` and `pipeline_memory/`.
2. `portal-v2/` — React 18 + TypeScript + Vite + Tailwind + Supabase; deploys to Vercel.
3. `website/` — Docusaurus living runbook; deploys to Vercel.

Legacy Express `portal/` was removed in 03153c3 (2026-06-02) — never `cd portal`; Cloud Agent
installs use `scripts/cloud-agent-install.sh`. Also: `scripts/` (6-gate harness, backfills, Notion
sync) and `tests/` (pytest).

## Role

Act as a senior software engineer, data analyst, technical PM, and operational PM: elite, secure,
optimized solutions that also track delivery and operational efficiency — strict typing, clean
architecture, OWASP; high data integrity (Python + Supabase for heavy processing; Power BI, Hex, or
spreadsheets for reporting); delivery in Linear, architecture in Visio; KPIs, crew efficiency, and
resource allocation via Smartsheet, MS Project, Notion, Todoist (Acrobat for document distribution).
For a new workflow, compare the current stack with modern alternatives and give a definitive
recommendation (security, scalability, integration effort). Integrate with the existing
architecture; never break it.

## Production safety (hard rules)

- **Do not break production.** `generate_weekly_pdfs.py` processes real billing data on a cron.
  Preserve existing behavior; refactor only to improve output, security, or performance; never
  delete production code unless it is definitively broken or causing bugs.
- **Minimal, surgical changes.** Establish exactly where you are in the codebase and state what
  is being modified and what must stay untouched (`.github/instructions/taming-copilot.instructions.md`).
- **Additive logic only** for the billing workflow unless a behavior change is explicitly requested.
- **Data integrity:** never drop tables or overwrite production logic without explicit verification.
- **Python module rules:** `.claude/rules/python-module-architecture.md` — the facade stays thin;
  new behavior goes in the owning `pipeline/*`, `pipeline_memory/*`, or `billing_audit/*` module.

## Guardrails (billing-pipeline footguns)

Index: `.claude/rules/billing-pipeline-guardrails.md`. History and incident root causes:
`memory-bank/living-ledger.md` (grep the header you need; never load the whole file).

- The change-detection key is `(WR, week_ending, variant, foreman, dept, job)`. Never shorten it
  back to `(WR, week, variant, foreman)`; helper files regenerate on new past-week rows because of it.
- Helper rows need both `helper_dept` and `helper_foreman` (Job # optional). Rows with both
  "Helping Foreman Completed Unit?" and "Units Completed?" checked appear only in helper Excel
  files, never the main file — that prevents double-counting under `RES_GROUPING_MODE=both|helper`.
- Excel: always `safe_merge_cells()` (overlap detection); never write `oddFooter.right.text`.
- Never use, write, or suggest the Smartsheet `@cell` formula in Python or API payloads. It is a
  UI-only formula and fails server-side.
- Smartsheet API: 300 req/min; `PARALLEL_WORKERS` ≤ 8; rely on the SDK's 429 retries; paginate
  properly; token only via env. Never guess column names — verify against the
  `_validate_single_sheet()` mappings in `pipeline/discovery.py`.
- Job # is resolved from several column synonyms (`Job #`, `Job#`, `Job Number`, …); do not
  collapse them.
- Keep the `advanced_options` `key:value,key:value` parser in
  `.github/workflows/weekly-excel-generation.yml` even when the input count is under GitHub's
  limit — operational runbooks depend on that exact format.
- `TIME_BUDGET_MINUTES` (Python graceful stop, production `165`) must stay strictly below the
  job's `timeout-minutes` (`180`). Raise both together or Actions hard-kills the job first.
- Change detection is backed by `pipeline_memory.group_state` (Supabase), not a local JSON cache;
  `RESET_HASH_HISTORY=true` forces full regeneration. Attachment identity resolves from
  `group_state` with a per-row on-demand fallback (Phase 11 Plan 08, INC-05).
- Sentry: `SENTRY_ENABLE_LOGS` stays `false` by default (INFO-path logs can embed row PII;
  `before_send_log` in `pipeline/observability.py` is the backstop); `environment` / `release`
  tags are standardized; wrap new optimizations in Sentry error handling for visibility and rollback.

## Validation commands (authoritative)

```bash
pip install -r requirements.txt
pytest tests/ -v                                  # full suite — must pass before push
python -m py_compile generate_weekly_pdfs.py      # syntax check
SKIP_UPLOAD=true python generate_weekly_pdfs.py   # local dry run, no upload
TEST_MODE=true python generate_weekly_pdfs.py     # synthetic data, no token needed
bash scripts/run_6_gates.sh                       # 6-gate harness after any module move
```

Full command list (portal-v2, website, diagnostics, single-test forms, aspirational `uv`,
protected areas): `docs/ai/safe-commands.md`. `.github/hooks/pre-push-tests.json` is a Claude Code
hook that blocks the `git push` tool if `pytest tests/` fails; a plain shell push is not gated.

## Configuration

Required: `SMARTSHEET_API_TOKEN`. Everything else is `os.getenv()` with defaults. The full catalog
(commonly touched flags, discovery folders and rate tables, the time-budget family, debug flags,
retired no-op vars, and flags documented but not yet consumed) lives in
`.github/prompts/configuration-environment.md` § Operator quick reference.

## Pipeline flow (one screen)

Smartsheet folder discovery (every sheet validated every run; the discovery cache is retired) →
parallel fetch (≤ 8 workers) → filter and group by `(WR, week_ending, variant, foreman, dept, job)`
→ attachment identity from `pipeline_memory.group_state` → SHA-256 change detection → Excel
(`openpyxl`; `generated_docs/WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}{variant_suffix}_{hash}.xlsx`)
→ billing audit (`audit_billing_changes.py`, LOW/MEDIUM/HIGH risk) → delete the old attachment,
then upload to `TARGET_SHEET_ID`. Module map, data stores, schedule/timeouts, variant/grouping
model: `docs/ai/architecture.md`. Verified behavior notes: `docs/ai/implementation-truth.md`.

## Conventions

- **Python:** PEP 8, type hints, 4-space indent, ≤ 79-char lines, PEP 257 docstrings
  (`.github/instructions/python.instructions.md`). Release tagging stays compatible with the
  GitHub Actions release workflows.
- **Node (`portal-v2/`):** ES2022+ ESM, `async`/`await` only, prefer `undefined` over `null`,
  functions over classes, minimal deps. Tests use Vitest; never change production code to make
  it testable (`.github/instructions/nodejs-javascript-vitest.instructions.md`).
- **Subcontractor pricing:** folder-based discovery is the primary path
  (`.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`).
- **Commits:** Conventional Commits, subject ≤ 50 chars, bulleted body for complex changes.
  **PR titles** reference the tracking issue (`feat: implement Smartsheet sync (#42)`).
  **PR descriptions** have three sections: Objective · Changes Made · Production Safety Check.
- **Runbook edits** (`website/`): `.claude/rules/documentation-maintenance.md`.

## Living Ledger and cloud memory injection

`memory-bank/living-ledger.md` is the dated ledger of repo learnings, incident root causes, and
established rules (moved out of this file on 2026-05-28 to keep it lean). When a fix or feature —
including an `@claude` run triggered from a GitHub issue — introduces a new architectural
standard, recurring fix, or operational rule, append a `[YYYY-MM-DD HH:MM]` entry to the BOTTOM
of the ledger in the same PR. Never inline the ledger back into this file. The other
`memory-bank/*.md` pages are retired pointer stubs.

## Second-brain write-back

Repo-scoped subagents never edit Juan's second brain (the OneDrive `my-wiki` vault) directly.
They return a compact write-back packet (what changed · why it matters · target vault page),
dropping a file in `.claude/writeback-pending/` when needed; the main session applies vault
edits via `global-second-brain-writeback-bridge` / `global-context-continuity` and clears the
packet (audited by the global `~/.claude/hooks/audit_vault_writes.js` hook). Never place secrets
in a packet. Repo status: `.claude/project-state.md`; navigation map: `.claude/context-map.md`.

## Where to read next

- `.claude/context-map.md` (read order) · `.claude/project-state.md` (current status).
- `docs/ai/` — `architecture.md`, `implementation-truth.md`, `safe-commands.md`, `known-bugs.md`,
  `decisions.md` (pointer index into the ledger).
- `.github/copilot-instructions.md` — Copilot summary regenerated from this file; keep in sync.
- `.github/prompts/` — `architecture-analysis`, `data-processing-business-logic`,
  `testing-and-validation`, `configuration-environment`, `change-detection-troubleshooting`,
  `error-handling-resilience`. `.github/instructions/` — `copilot-setup`,
  `performance-optimization`, `github-actions-ci-cd-best-practices`, and the files cited above.
- `.github/agents/smartsheet-debugger.agent.md` (pipeline-debugging agent) · `AZURE_*.md` and
  `README_AZURE.md` (Azure DevOps mirror) · `portal-v2/README.md` (Supabase schema, auth, roles,
  Vercel) · `docs/sentry-implementation.md` (Sentry wiring across Python, Node, and React).
