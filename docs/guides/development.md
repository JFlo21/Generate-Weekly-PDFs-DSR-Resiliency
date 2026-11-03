<!-- generated-by: gsd-doc-writer -->
# Development

How to set up a local environment, run the checks, and ship a change to this repository.

This repo runs production billing automation on a cron, so every rule below is biased toward small,
additive, well-tested changes. When this page and the code disagree, the code wins. Related pages:

- [`docs/ai/architecture.md`](../ai/architecture.md) - module map, data stores, schedules.
- [`docs/ai/safe-commands.md`](../ai/safe-commands.md) - the verified command list.
- [`docs/guides/configuration.md`](configuration.md) - environment variables.
- [`README.md`](../../README.md) - project overview.

## Local setup

Prerequisites:

- Python 3.10 or newer locally (`target-version = "py310"` in `pyproject.toml`). CI runs Python 3.12.
- Node.js and npm, only if you work on `portal-v2/` or `website/` (the docs-site CI job uses Node 26).
- A Smartsheet API token only if you want a live read. Tests and the synthetic dry run need none.

Steps:

1. Fork and clone the repository, then enter the project root.
2. Create and activate a virtual environment (recommended).
3. Install the production dependencies. This is the only install the pipeline itself needs:

   ```bash
   pip install -r requirements.txt
   ```

4. Optionally install the lint and type-check tools. These are dev-only and must never be added to
   `requirements.txt`:

   ```bash
   pip install -r requirements-dev.txt
   ```

5. For local runs that need credentials, copy `.env.example` to `.env` and fill in values. `.env` is
   loaded by `python-dotenv` in the facade. Never commit a real `.env`, and never paste token, key or
   sheet-id values into code, docs, commits or issues. Variable names and defaults are in
   [`configuration.md`](configuration.md).
6. For the Node surfaces, install per directory:

   ```bash
   npm --prefix portal-v2 install
   npm --prefix website install
   ```

   `scripts/cloud-agent-install.sh` is the idempotent bootstrap used by cloud agent environments. It
   installs `requirements.txt` and runs npm only for trees that exist.

On Windows, set `PYTHONUTF8=1` (the 6-gate script does this for you) so the import-time startup banners
do not crash a cp1252 console.

## Repository layout

| Path | What lives there |
|------|------------------|
| `generate_weekly_pdfs.py` | Thin facade: loads `.env`, re-exports the `pipeline/` public API, delegates `__main__` to `pipeline.orchestrate`. |
| `pipeline/` | The billing engine, split by responsibility (`config`, `discovery`, `fetch`, `grouping`, `pricing`, `change_detection`, `excel`, `upload`, `cleanup`, `attribution`, `retry`, `observability`, `orchestrate`, and others). |
| `pipeline_memory/` | Supabase run-memory layer (reader, writer, client, SQL). |
| `billing_audit/` | Supabase attribution, run fingerprint and hash-store layer. |
| `audit_billing_changes.py` | Price-anomaly audit (LOW / MEDIUM / HIGH). |
| `portal-v2/` | React 18 + TypeScript + Vite + Tailwind app on Supabase. |
| `website/` | Docusaurus runbook. |
| `scripts/` | The 6-gate harness, backfills, Notion sync, artifact and runbook helpers. |
| `tests/` | pytest suite, plus `tests/golden/` and `tests/fixtures/`. |

Do not run commands in a `portal/` directory. The old Express app was removed.

## Code conventions

### Module ownership (most important rule)

`generate_weekly_pdfs.py` is a facade. New behavior goes in the module that owns the responsibility:
`pipeline/*`, `pipeline_memory/*` or `billing_audit/*`. Never add logic back into the facade. Per
`.claude/rules/python-module-architecture.md`:

- Keep modules cohesive. Line count is a review signal, not a target.
- Before adding a new responsibility to an overloaded module, propose extracting it.
- Preserve imports, public APIs, CLI behavior and tests. Avoid circular imports.
- Avoid generic utility dumping grounds. Keep entry points thin.
- Add or update tests before a behavior-preserving refactor.
- Update [`docs/ai/architecture.md`](../ai/architecture.md) after any structural change.

If you add or move a public name that tests or the facade rely on, the two golden files
`tests/golden/baseline_names.json` and `tests/golden/facade_allowlist.json` are what the harness checks
against, so run the 6 gates (below).

### Additive and surgical changes

- Preserve existing billing behavior. Refactor only to improve output, security or performance.
- Do not delete production code unless it is definitively broken.
- State what you are changing and what must stay untouched before you edit.
- Read [`.claude/rules/billing-pipeline-guardrails.md`](../../.claude/rules/billing-pipeline-guardrails.md)
  and the guardrail section of [`CLAUDE.md`](../../CLAUDE.md) before touching grouping, hashing,
  filenames, attachments or attribution. Highlights:
  - The change-detection key is `(WR, week_ending, variant, foreman, dept, job)`. Never shorten it.
  - Helper rows need both `helper_dept` and `helper_foreman`.
  - Use `safe_merge_cells()` for Excel merges and never write `oddFooter.right.text`.
  - Never use the Smartsheet `@cell` formula in Python or API payloads.
  - Keep `PARALLEL_WORKERS` at 8 or below, and `TIME_BUDGET_MINUTES` strictly below the workflow
    `timeout-minutes`.
  - Keep the `advanced_options` `key:value,key:value` parser in
    `.github/workflows/weekly-excel-generation.yml`.
- Workflow, schedule, Supabase schema and billing-output changes need owner approval. Do not change them
  as a side effect of another task.

### Python style

From [`.github/instructions/python.instructions.md`](../../.github/instructions/python.instructions.md):

- PEP 8, 4-space indentation, lines of 79 characters or fewer.
- Type hints on functions, using the `typing` module.
- PEP 257 docstrings placed immediately after `def` or `class`.
- Comments explain why, not what. Handle edge cases explicitly (empty input, invalid types, large data).
- Break large functions into smaller ones.

For brand-new standalone scripts (not the existing pipeline), see
[`.claude/rules/smartsheet-python-optimization.md`](../../.claude/rules/smartsheet-python-optimization.md).
The existing engine stays on `openpyxl`.

### Node style (`portal-v2/`)

ES2022+ ESM, `async`/`await` only, prefer `undefined` over `null`, functions over classes, minimal
dependencies. Tests use Vitest. Do not change production code just to make it testable. Details:
[`.github/instructions/nodejs-javascript-vitest.instructions.md`](../../.github/instructions/nodejs-javascript-vitest.instructions.md).

## Build and check commands

### Python

| Command | Description |
|---------|-------------|
| `pytest tests/ -v` | Full test suite. Must pass before you push. |
| `python -m pytest tests/ -q` | Same suite, quiet output (what the harness and push hook use). |
| `pytest tests/test_vac_crew.py -v` | Run one test file. |
| `pytest tests/ --cov` | Run with coverage. |
| `python -m py_compile generate_weekly_pdfs.py` | Syntax check of the facade (also a CI step). |
| `SKIP_UPLOAD=true python generate_weekly_pdfs.py` | Local dry run. Generates files into `generated_docs/` and does not upload or delete attachments. With a real token present it still reads live sheets. |
| `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py` | Synthetic run. Blank the token, otherwise `TEST_MODE` reads every sheet live. |
| `bash scripts/run_6_gates.sh` | The 6-gate validation harness (below). |
| `ruff check . --exit-zero` | Lint, warn-only. |
| `mypy generate_weekly_pdfs.py audit_billing_changes.py billing_audit` | Type check, warn-only. |

### `portal-v2/` (run from that directory)

| Command | Description |
|---------|-------------|
| `npm run dev` | Vite dev server. |
| `npm run build` | `tsc -b && vite build`. |
| `npm run lint` | ESLint with `--max-warnings 0`. |
| `npm test` | `vitest run --passWithNoTests`. |
| `npm run test:watch` | Vitest in watch mode. |
| `npm run preview` | Preview the production build. |

`portal-v2` needs `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `.env.local`. Copy
`portal-v2/.env.example` and fill in your own values.

### `website/` (run from that directory)

| Command | Description |
|---------|-------------|
| `npm run start` | Docusaurus dev server. |
| `npm run typecheck` | `tsc`. |
| `npm run build` | Production build (what the Docs Site Build job runs). |

Validate runbook edits with `npm run typecheck` and `npm run build` before pushing. Rules for editing the
runbook are in
[`.claude/rules/documentation-maintenance.md`](../../.claude/rules/documentation-maintenance.md): rewrite
affected pages instead of appending stale text, organize by operator workflow, and name which component
owns each flow.

## The 6-gate harness

`bash scripts/run_6_gates.sh` is the behavioral-equivalence check for the engine. Run it after any module
move or other structural change. It uses `set -euo pipefail`, so the first failing gate aborts the run.
Order, cheapest first:

1. `scripts/check_api_equality.py` - AST top-level name equality against `tests/golden/baseline_names.json`
   (catches a dropped or renamed export).
2. `scripts/check_facade_completeness.py` - every name in `tests/golden/facade_allowlist.json` resolves
   through the facade.
3. `python -m pytest tests/ -q` - the full suite.
4. `scripts/check_mypy_delta.sh` - mypy error count must not rise above
   `tests/golden/mypy_baseline_count.txt`. Skips gracefully if mypy is not installed.
5. `python -m py_compile generate_weekly_pdfs.py`.
6. A synthetic run (`SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true`) followed by
   `scripts/check_run_summary_structure.py`, a structural check of `run_summary.json` keys and types.

If a gate fails after a structural change, revert the change rather than patching around the gate.

## Testing expectations

- Add tests for critical paths and edge cases (empty input, duplicate groups, bad dates, large data).
- Behavior-preserving refactors get tests first.
- Tests live in `tests/` as `test_*.py`. Shared data is in `tests/fixtures/` and `tests/golden/`.
- Tests must not need a live Smartsheet or Supabase connection.
- Coverage is informational. `codecov.yml` states it is not a merge gate. The harness is the
  correctness gate.

## Branches

No branch naming convention is documented in the repository. Existing branches use a type prefix such as
`fix/...`. Use a short descriptive name with a Conventional Commit type prefix (`feat/`, `fix/`, `docs/`,
`test/`). Never push directly to `master`; it is the default branch and what the production cron runs.

## Commits

Use Conventional Commits. Keep the subject at 50 characters or fewer and add a bulleted body for complex
changes. Examples from history: `feat(corrections): wire orchestrate run integration`,
`test(corrections): cover reporting corrections`, `docs(runbook): reporting corrections page`.

## Pull requests

1. Make sure the checks pass locally: `pytest tests/ -v`, and `bash scripts/run_6_gates.sh` if you moved or
   renamed anything.
2. Title the PR with the tracking issue number, for example `feat: implement Smartsheet sync (#42)`.
3. Write the description with three sections: **Objective**, **Changes Made**, **Production Safety Check**.
4. If the change affects operators (new env var, schedule, data contract or guardrail), append a dated
   `[YYYY-MM-DD HH:MM]` entry to the bottom of `memory-bank/living-ledger.md` in the same PR. Do not copy
   the ledger into `CLAUDE.md`.
5. If you changed structure or commands, update `docs/ai/architecture.md` and
   [`docs/ai/safe-commands.md`](../ai/safe-commands.md).

There is no PR template file in `.github/`; the three sections above are the project convention.

### What CI runs on a PR

| Workflow | Trigger | What it does | Blocking |
|----------|---------|--------------|----------|
| `ci-checks.yml` ("Compile and test") | PR to and push on `master` | `py_compile` on the facade, then `pytest tests/ -v --tb=short` on Python 3.12 | Yes (intended required check) |
| `python-lint.yml` | Every push and PR | `ruff check . --exit-zero` and mypy | No, warn-only |
| `codecov.yml` | See workflow | `pytest --cov=. --cov-branch`, uploads to Codecov | Informational |
| `docs-site-build.yml` | PRs touching `website/**` | `npm run typecheck` and `npm run build` | Yes for runbook changes |
| `snyk-security.yml` | See workflow | Dependency security scan | See workflow |

The `docs-changelog.yml` workflow appends a stub runbook changelog line on each merge to `master`. Expand
a stub into a proper narrative entry (what, why, how it affects operators) before the next release.

### Pre-push test hook

`.github/hooks/pre-push-tests.json` is a Claude Code hook, not a git hook. It blocks the agent's
`git push` tool call when `python -m pytest tests/ -q` fails. A plain shell `git push` is not gated, so
run `pytest tests/` yourself first.

## Issues

The repository has no issue templates (`.github/ISSUE_TEMPLATE/` does not exist). When filing an issue,
include steps to reproduce, expected versus actual behavior, the affected Work Request count or group
shape (not customer data), and the run context (local, manual dispatch or cron). Do not paste tokens,
sheet ids or personal data.

## Next steps

- [`docs/guides/configuration.md`](configuration.md) - what each environment variable does.
- [`docs/ai/architecture.md`](../ai/architecture.md) - how the pipeline modules fit together.
- [`docs/ai/known-bugs.md`](../ai/known-bugs.md) and [`docs/ai/implementation-truth.md`](../ai/implementation-truth.md) -
  verified behavior and open issues.
