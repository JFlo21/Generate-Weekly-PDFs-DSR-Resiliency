<!-- generated-by: gsd-doc-writer -->
# Testing

How to run, write, and gate the tests for the billing pipeline (Python) and the `portal-v2` web app
(Vitest). The Python engine is production-critical, so the suite is the main safety net: it must pass
before any push.

For environment variables referenced here, see [Configuration](configuration.md). For the module map
the tests exercise, see [Architecture](../ai/architecture.md).

## Test framework and setup

| Surface | Framework | Location | Pinned in |
|---|---|---|---|
| Python engine, `pipeline/`, `pipeline_memory/`, `billing_audit/`, `scripts/` | `pytest` 9.0.3 (+ `pytest-cov` 6.0.0) | `tests/` (about 80 `test_*.py` files) | `requirements.txt` |
| `portal-v2` | Vitest 4 + jsdom, Testing Library, `jest-axe` | `portal-v2/src/**/__tests__/` (20 test files) | `portal-v2/package.json` |
| Lint / type check (warn-only, not tests) | `ruff` 0.8.6, `mypy` 1.14.1 | `pyproject.toml` | `requirements-dev.txt` |

Setup:

```bash
pip install -r requirements.txt      # includes pytest and pytest-cov
cd portal-v2 && npm install          # only needed for the web app tests
```

There is no `pytest.ini`, `conftest.py`, or `tests/__init__.py`. Roughly half the test files insert the
repository root into `sys.path` themselves, so prefer `python -m pytest` (which also puts the current
directory on the path) over a bare `pytest`.

Python 3.10 is the lowest supported runtime; CI runs 3.12.

## Running tests

### Python

```bash
python -m pytest tests/ -v                                   # full suite (must pass before push)
python -m pytest tests/ -q                                   # quiet, what the pre-push hook and Gate 3 run
python -m pytest tests/test_subcontractor_pricing.py -v      # one file
python -m pytest tests/test_vac_crew.py::test_name -v        # one test
python -m pytest tests/ -k foreman_notes -v                  # by keyword
python -m pytest tests/ --cov=. --cov-branch --cov-report=xml   # coverage, as CI does
```

Sanity checks that are not part of pytest:

```bash
python -m py_compile generate_weekly_pdfs.py     # syntax check of the facade
bash scripts/run_6_gates.sh                      # 6-gate harness (see below)
```

### portal-v2 (Vitest)

```bash
cd portal-v2
npm test              # vitest run --passWithNoTests
npm run test:watch    # vitest in watch mode
npm run lint          # eslint --max-warnings 0
```

`portal-v2/vitest.config.ts` uses the `jsdom` environment, enables Vitest globals, and loads
`src/test/setup.ts` (registers `@testing-library/jest-dom` and the `jest-axe` `toHaveNoViolations`
matcher). jsdom silently disables the axe colour-contrast rule, so contrast is checked manually, not by
the suite.

## The 6-gate harness

`scripts/run_6_gates.sh` is the behavioral-equivalence oracle to run after any module move or refactor
of the engine. It uses `set -euo pipefail`, so the first failing gate aborts the run.

| Gate | Command | What it checks |
|---|---|---|
| 1 | `python scripts/check_api_equality.py` | AST public-API equality against `tests/golden/baseline_names.json` |
| 2 | `python scripts/check_facade_completeness.py` | Every name in `tests/golden/facade_allowlist.json` still resolves on the facade |
| 3 | `python -m pytest tests/ -q` | Full test suite |
| 4 | `bash scripts/check_mypy_delta.sh` | mypy error count has not grown vs `tests/golden/mypy_baseline*.txt` |
| 5 | `python -m py_compile generate_weekly_pdfs.py` | Facade compiles |
| 6 | `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py`, then `python scripts/check_run_summary_structure.py` | `generated_docs/run_summary.json` keys and value types match `tests/golden/run_summary_baseline.json` |

Gate 6 is structural only: it compares key sets and value types, not values or timestamps. The scripts
themselves are unit-tested in `tests/test_facade_harness.py`, including a check that the Gate 6
invocation stays pinned to the synthetic dataset.

## TEST_MODE vs SKIP_UPLOAD

These two switches are independent and are often confused. Both are read in `pipeline/config.py`.

| Variable | Default | Effect | Does NOT do |
|---|---|---|---|
| `TEST_MODE` | `false` (accepts `1`, `true`, `yes`) | Selects a synthetic in-memory dataset **only when `SMARTSHEET_API_TOKEN` is falsy**; enables `WR_FILTER` scoping; changes some dry-run behavior in Excel generation and Foreman Notes | Does not by itself stop live reads or uploads |
| `SKIP_UPLOAD` | `false` | Dry run: nothing is uploaded to Smartsheet, and destructive attachment deletes and pruning are skipped (`dry_run=SKIP_UPLOAD`) | Does not stop live reads of Smartsheet sheets |

Safe combinations:

```bash
# Fully local, deterministic, no network: synthetic data, no uploads.
# Blank the token explicitly (see warning below).
SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py

# Real read-only dry run: reads live sheets, writes nothing back.
SKIP_UPLOAD=true python generate_weekly_pdfs.py

# Scope a synthetic or dry run to specific work requests.
TEST_MODE=true WR_FILTER=<wr>,<wr> python generate_weekly_pdfs.py
```

Warning: `generate_weekly_pdfs.py` calls `load_dotenv()`, which fills `SMARTSHEET_API_TOKEN` from a
developer `.env` when the variable is absent. With a token present, `TEST_MODE=true` reads every live
source sheet instead of using synthetic rows (a multi-minute, large read). Always pass an **empty**
`SMARTSHEET_API_TOKEN=` rather than unsetting it: `load_dotenv()` never overrides an existing variable,
and an empty value is falsy so the engine falls back to the synthetic dataset. Tests that launch the
engine as a subprocess (for example `tests/test_entrypoint_no_double_import.py`) set it the same way.

The synthetic rows come from `_build_synthetic_rows()` in `pipeline/orchestrate.py`. Set
`PYTHONUTF8=1` on Windows so the emoji startup banners do not crash a cp1252 console.

Some variables listed in `.github/prompts/testing-and-validation.md` (`SKIP_FILE_OPERATIONS`,
`DRY_RUN_UPLOADS`, `MOCK_SMARTSHEET_UPLOAD`, `SYNTHETIC_WR_COUNT`, `ENABLE_AUDIT_ANOMALIES`) are not read
anywhere in `pipeline/`, `generate_weekly_pdfs.py`, or `audit_billing_changes.py`; setting them has no
effect. Use only the switches documented in [Configuration](configuration.md).

## Synthetic-fixture rule (no real data)

All test inputs must be synthetic. Never commit or paste into a test:

- real Smartsheet rows, cell values, attachments, or exported Excel files
- real work-request numbers, employee or foreman names, customer names, or sheet and row identifiers
- API tokens, `.env` contents, Supabase keys, or any other secret

Conventions the existing suite follows:

- Use obviously fake people and labels (for example `Foreman A`, `Helper H`) and fake numeric ids in an
  unmistakable range (for example the `9000000x` work requests and `7001` sheet id in
  `tests/_reporting_corrections_fixture.py`).
- State provenance inside the fixture. JSON fixtures carry a `provenance` field saying where the
  scenario came from (see `tests/fixtures/incremental/`); new fixtures must state that they are
  synthetic. One legacy fixture there records a live sheet-shape capture (`abbreviated_sheet_response.json`,
  structure only); do not add more of those.
- Keep fixtures free of the wall clock and the host: use fixed dates, and pin environment variables
  (the Foreman Notes golden helper does this with `pinned_env`).
- Import nothing from the pipeline in a pure fixture module, so a golden-hash generator can load it
  against a pristine checkout.
- Never point a test at live Smartsheet or Supabase. Mock the client; inject stubs for `smartsheet` into
  `sys.modules` only when the SDK is genuinely unimportable (see `_ensure_smartsheet_mocked()` in
  `tests/test_billing_audit_shadow.py`).
- Any engine subprocess a test spawns must set `TEST_MODE=true`, `SKIP_UPLOAD=true`, and an empty
  `SMARTSHEET_API_TOKEN`.

## Writing new tests

### Python

- File naming: `tests/test_<topic>.py`, with `test_*` functions or `unittest.TestCase` classes (both are
  used). Underscore-prefixed modules (`tests/_foreman_notes_golden.py`,
  `tests/_reporting_corrections_fixture.py`) are shared helpers, not tests.
- Location of shared data:

  | Path | Contents |
  |---|---|
  | `tests/fixtures/foreman_notes/` | Golden record for Foreman Notes (`golden_off.json`), regenerated with `python tests/_foreman_notes_golden.py --write` |
  | `tests/fixtures/incremental/` | Synthetic sheet-response and row-state scenarios for incremental reads, plus a SQL contract fixture |
  | `tests/fixtures/mem04/` | Synthetic formula-change scenarios |
  | `tests/golden/` | Frozen baselines consumed by the 6-gate harness (API names, facade allowlist, mypy count, `run_summary` shape) |

- Prefer `tmp_path` / `tempfile.TemporaryDirectory()` for any output folder; never write into
  `generated_docs/` from a test.
- Tests reach engine behavior through the `generate_weekly_pdfs` facade (`import generate_weekly_pdfs as
  gwp`) and monkeypatch values on it, because `pipeline/*` modules read settings such as `TEST_MODE`
  from the facade at call time. New behavior belongs in the owning `pipeline/*`, `pipeline_memory/*`, or
  `billing_audit/*` module, not in the facade.
- Behavior that is billing-visible needs a test in the same change: a regression test for any fix to
  grouping, change detection, hashing, attribution, or filename rules. Do not weaken a guardrail test to
  make a change pass.
- Platform-specific cases use `pytest.mark.skipif` with a reason (for example the POSIX exec-bit check in
  `tests/test_cloud_agent_install.py` is skipped on Windows).
- Several documentation-contract tests (for example `tests/test_own04_documentation.py`) read repository
  docs as plain text. If you edit a runbook page they cover, run the suite before pushing.

### portal-v2

Follow `.github/instructions/nodejs-javascript-vitest.instructions.md`:

- Use Vitest; write tests for new features and bug fixes, including edge cases and error handling.
- Never change production code to make it easier to test; write the test against the code as it is.
- Co-locate tests in an `__tests__/` folder beside the code (`*.test.ts` / `*.test.tsx`), as the existing
  hooks, components, and `lib` tests do.
- Use `undefined`, not `null`, for optional values in new test code.

## Coverage requirements

| Type | Threshold |
|---|---|
| Lines / branches / functions / statements | No coverage threshold configured |

Coverage is informational. `codecov.yml` marks both project and patch status as `informational: true`,
because large relocation PRs move already-tested lines into new files and would read as low patch
coverage. Correctness is gated by the 6-gate harness and the full suite, not by a percentage. Coverage
reports are still posted on every PR as a guide for reviewers.

## CI integration

| Workflow | Trigger | Test step |
|---|---|---|
| `.github/workflows/ci-checks.yml` ("CI Checks", job `test`) | PR and push to `master` | `python -m py_compile generate_weekly_pdfs.py`, then `python -m pytest tests/ -v --tb=short` on Python 3.12, 15-minute timeout |
| `.github/workflows/codecov.yml` ("Run tests and upload coverage") | PR and push to `master` / `main` | `pytest --cov=. --cov-branch --cov-report=xml`, then upload to Codecov, 30-minute timeout |
| `.github/workflows/python-lint.yml` ("Python Lint (warn-only)") | Every push and PR | `ruff check . --exit-zero` and mypy; never fails the build |

CI installs only `requirements.txt`. The Vitest suite for `portal-v2` is not run by any workflow in
`.github/workflows/`, so run `npm test` and `npm run lint` locally before pushing changes under
`portal-v2/`.

## Pre-push hook

`.github/hooks/pre-push-tests.json` is a Claude Code `PreToolUse` hook. When the agent's terminal tool is
about to run a command matching `git push`, the hook runs `python -m pytest tests/ -q` and denies the
push with "Tests must pass before pushing" if pytest exits non-zero. It has a 120-second timeout.

Limits to be aware of:

- It gates only agent-issued pushes through that tool. A plain `git push` typed in your own shell is not
  gated, so run the suite yourself first.
- Only a `windows` command is defined in the hook file, so it does not apply on other platforms.
- It runs the whole suite quietly; use `python -m pytest tests/ -v` to see failure detail.

## Before you push

1. `python -m pytest tests/ -v` passes.
2. `python -m py_compile generate_weekly_pdfs.py` is clean.
3. After any module move or facade change: `bash scripts/run_6_gates.sh` passes.
4. For `portal-v2` changes: `cd portal-v2 && npm test && npm run lint`.
5. If a change touches billing output, confirm with a synthetic dry run
   (`SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py`) before relying
   on a real read-only run (`SKIP_UPLOAD=true`).

## Related docs

- [Configuration](configuration.md) for `TEST_MODE`, `SKIP_UPLOAD`, `WR_FILTER`, and the other run flags
- [Architecture](../ai/architecture.md) for the facade and `pipeline/` module map
- `docs/ai/safe-commands.md` for the verified command list
- `.github/prompts/testing-and-validation.md` for the longer testing prompt (see the caveat above on
  variables it mentions that the code does not read)
