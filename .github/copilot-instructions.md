# Project Guidelines

<!-- Generated from CLAUDE.md @ 24206db on 2026-09-02 by the align-instruction-files skill. Do not hand-edit;
     regenerate from CLAUDE.md when it changes. -->

## Overview

Production billing automation: `generate_weekly_pdfs.py` (thin facade over `pipeline/`) → Smartsheet
row fetch (~550 rows, 13+ sheets) → grouping by Work Request + week ending (+ variant, foreman, dept,
job) → Excel generation (`openpyxl`) → upload back to Smartsheet as row attachments, on a GitHub
Actions cron every ~2 hours on weekdays. **Do not break the pipeline.** Additive, surgical changes
only; never redesign the Smartsheet → Excel → Smartsheet flow unless explicitly asked.

Components: Python engine (`generate_weekly_pdfs.py`, `pipeline/`, `audit_billing_changes.py`,
`billing_audit/`, `pipeline_memory/`), `portal-v2/` (React 18 + TS + Vite + Tailwind + Supabase →
Vercel), `website/` (Docusaurus runbook → Vercel). Legacy Express `portal/` was removed (03153c3) —
never `cd portal`. Full map: `docs/ai/architecture.md`.

## Hard guardrails

- Change-detection key is `(WR, week_ending, variant, foreman, dept, job)` — never shorten it.
- Helper rows need both `helper_dept` and `helper_foreman`; rows with both "Helping Foreman Completed
  Unit?" and "Units Completed?" checked appear only in helper Excel files, never the main file.
- Excel: always `safe_merge_cells()`; never write `oddFooter.right.text`.
- Never use the Smartsheet `@cell` formula in Python or API payloads (UI-only; fails server-side).
- Smartsheet: 300 req/min, `PARALLEL_WORKERS` ≤ 8, SDK 429 retries, token only via env; verify column
  names against `_validate_single_sheet()` in `pipeline/discovery.py` — never guess.
- Job # comes from several column synonyms (`Job #`, `Job#`, `Job Number`, …); do not collapse them.
- Keep the `advanced_options` `key:value,key:value` parser in
  `.github/workflows/weekly-excel-generation.yml`.
- `TIME_BUDGET_MINUTES` (`165`) must stay strictly below the job's `timeout-minutes` (`180`).
- Change detection is `pipeline_memory.group_state`-backed (Supabase), not a local JSON cache;
  `RESET_HASH_HISTORY=true` forces full regeneration.
- `SENTRY_ENABLE_LOGS` stays `false` by default (row PII); standardize Sentry `environment`/`release`.
- New behavior goes in the owning `pipeline/*`, `pipeline_memory/*`, or `billing_audit/*` module,
  never back into the facade (`.claude/rules/python-module-architecture.md`).

## Validation

```bash
pip install -r requirements.txt
pytest tests/ -v                                  # must pass before push
python -m py_compile generate_weekly_pdfs.py
SKIP_UPLOAD=true python generate_weekly_pdfs.py   # dry run
TEST_MODE=true python generate_weekly_pdfs.py     # synthetic data, no token
bash scripts/run_6_gates.sh                       # after any module move
```

Full command list: `docs/ai/safe-commands.md`. Env-var catalog:
`.github/prompts/configuration-environment.md` § Operator quick reference.

## Conventions

- Python: PEP 8, type hints, 4-space indent, ≤ 79-char lines, PEP 257 docstrings.
- Node (`portal-v2/`): ES2022+ ESM, `async`/`await` only, prefer `undefined` over `null`, functions
  over classes, Vitest; never change production code to make it testable.
- Commits: Conventional Commits, subject ≤ 50 chars. PR titles reference the issue. PR body sections:
  Objective · Changes Made · Production Safety Check.
- New rules and incident root causes go to the bottom of `memory-bank/living-ledger.md` as dated
  `[YYYY-MM-DD HH:MM]` entries, in the same PR as the code change.

## Pointers

`CLAUDE.md` (canonical rules) · `.claude/rules/*.md` · `.claude/context-map.md` (read order) ·
`.claude/project-state.md` (status) · `docs/ai/` (implementation truth) · `.github/prompts/` and
`.github/instructions/` (deep guides) · `.github/agents/smartsheet-debugger.agent.md`.
