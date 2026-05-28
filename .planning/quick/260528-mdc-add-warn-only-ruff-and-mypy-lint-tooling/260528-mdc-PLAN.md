---
phase: quick-260528-mdc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - requirements-dev.txt
  - .github/workflows/python-lint.yml
autonomous: true
requirements:
  - QT-MDC-01  # Wire up warn-only ruff + mypy tool config (pyproject.toml, tool tables only)
  - QT-MDC-02  # Add isolated, non-blocking python-lint CI workflow on push + PR
  - QT-MDC-03  # Keep dev tooling out of production requirements.txt; production workflow untouched

must_haves:
  truths:
    - "ruff and mypy are configured and runnable from a separate dev-deps file without touching production requirements.txt"
    - "A new isolated GitHub Actions workflow runs ruff + mypy on push and pull_request"
    - "Lint/type-check findings can NEVER fail CI, block a merge, or affect the production pipeline (warn-only)"
    - "The production cron workflow weekly-excel-generation.yml is byte-for-byte unchanged"
    - "pyproject.toml contains only tool config tables, not build-system or project tables"
  artifacts:
    - path: "pyproject.toml"
      provides: "ruff + mypy tool configuration (tool-config-only, no packaging tables)"
      contains: "[tool.ruff]"
    - path: "requirements-dev.txt"
      provides: "Isolated dev tooling pins (ruff, mypy) — NOT installed by the production pipeline"
      contains: "ruff"
    - path: ".github/workflows/python-lint.yml"
      provides: "Isolated non-blocking lint/type-check CI workflow on push + pull_request"
      contains: "continue-on-error: true"
  key_links:
    - from: ".github/workflows/python-lint.yml"
      to: "requirements-dev.txt"
      via: "pip install -r requirements-dev.txt"
      pattern: "requirements-dev.txt"
    - from: ".github/workflows/python-lint.yml"
      to: "pyproject.toml"
      via: "ruff/mypy auto-discover their [tool.*] config tables"
      pattern: "ruff check|mypy"
---

<objective>
Wire up Python lint (ruff) + static type-check (mypy) tooling for the
production billing engine in WARN-ONLY (non-blocking) mode. CLAUDE.md and
AGENTS.md currently flag ruff/mypy as "aspirational — not yet wired up";
this task makes them real and runnable in CI without any risk to the
production Smartsheet -> Excel -> Smartsheet pipeline.

Purpose: Surface lint/type findings for visibility now; defer enforcement.
The ~3,100-line `generate_weekly_pdfs.py` has never been linted, so many
findings are expected — that is acceptable in warn-only mode. We do NOT
reformat or auto-fix production code in this task.

Output (all ADDITIVE new files — no production code modified):
- `pyproject.toml` (tool-config-only: `[tool.ruff]` / `[tool.ruff.lint]` /
  `[tool.mypy]`; NO `[build-system]`, NO `[project]`)
- `requirements-dev.txt` (isolated dev pins: ruff, mypy)
- `.github/workflows/python-lint.yml` (isolated, non-blocking, push + PR)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

# LOCKED production-safety constraints (NON-NEGOTIABLE — do not revisit):
# 1. Do NOT modify .github/workflows/weekly-excel-generation.yml or ANY existing
#    workflow. Create a NEW isolated workflow file instead.
# 2. The lint/type-check CI must be NON-BLOCKING (continue-on-error: true and/or
#    --exit-zero for ruff). A finding must NEVER fail CI or affect production.
# 3. Do NOT add ruff/mypy to the production requirements.txt. Use requirements-dev.txt.
# 4. pyproject.toml = ONLY [tool.ruff]/[tool.ruff.lint]/[tool.mypy] tables.
#    NO [build-system], NO [project] (those would change how pip/build treat the repo).

<interfaces>
<!-- Conventions extracted from the codebase. Mirror these EXACTLY. -->

CLAUDE.md / AGENTS.md Python conventions:
- PEP 8, comprehensive type hints, 4-space indent, line length <= 79 chars,
  PEP 257 docstrings.
- Primary language: Python 3.10+. CI runs Python 3.12 (3.11+ locally is fine).

Production workflow conventions to MIRROR (from
.github/workflows/weekly-excel-generation.yml — read-only reference, do NOT edit):
- `permissions:` block at workflow level: `contents: read`
- `uses: actions/checkout@v4`
- `uses: actions/setup-python@v5` with `python-version: '3.12'`

First-party Python that mypy should TYPE-CHECK (root engine + package):
- generate_weekly_pdfs.py        (production entry point, ~3,100 lines)
- audit_billing_changes.py       (imported by the main script)
- billing_audit/                 (client.py, fingerprint.py, writer.py, __init__.py)

Directories mypy/ruff MUST EXCLUDE (vendored / non-engine / other languages):
- portal/         (Node.js Express)
- portal-v2/      (React/TS)
- website/        (Docusaurus; contains website/node_modules/**/*.py)
- node_modules/   (any)
- archive/        (archived backup copies of the engine)
- .planning/      (planning artifacts)
- tests/          (excluded from mypy scope; ruff still lints them harmlessly)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add tool-config-only pyproject.toml and isolated requirements-dev.txt</name>
  <files>pyproject.toml, requirements-dev.txt</files>
  <action>
Create TWO new files. Do NOT modify requirements.txt or any production code.

(A) `pyproject.toml` — TOOL CONFIG ONLY. This file MUST contain ONLY
`[tool.ruff]`, `[tool.ruff.lint]`, and `[tool.mypy]` tables. It MUST NOT
contain a `[build-system]` table or a `[project]` table (per LOCKED
constraint 4 — adding either changes how pip/build tools treat the repo and
could alter `pip install -r requirements.txt` behavior). Lenient, warn-only,
convention-aligned config:

```toml
# Tool configuration ONLY (ruff + mypy). Deliberately NO [build-system]
# and NO [project] table: this repo is a script collection, not a packaged
# distribution. Adding packaging tables would change how pip/build tools
# treat the repo and risk the production `pip install -r requirements.txt`
# step. See the 260528-mdc quick PLAN.md (LOCKED constraint 4).

[tool.ruff]
# Match the repo's PEP 8 line-length convention (CLAUDE.md / AGENTS.md).
line-length = 79
# Lowest supported runtime is Python 3.10+ (CLAUDE.md). CI runs 3.12.
target-version = "py310"
# Never lint vendored / non-engine / other-language trees.
extend-exclude = [
    "portal",
    "portal-v2",
    "website",
    "node_modules",
    "archive",
    ".planning",
]

[tool.ruff.lint]
# Conservative baseline since the 3,100-line engine has never been linted:
# E (pycodestyle errors), F (pyflakes), I (import sorting), UP (pyupgrade),
# B (flake8-bugbear). Warn-only mode means findings are surfaced, not enforced.
select = ["E", "F", "I", "UP", "B"]
ignore = []

[tool.mypy]
# Lowest supported runtime (CLAUDE.md). Lenient — do NOT enable --strict.
python_version = "3.10"
# smartsheet-python-sdk, openpyxl, supabase, etc. ship without type stubs.
ignore_missing_imports = true
# Warn-only posture: surface issues without forcing annotations everywhere.
warn_return_any = false
warn_unused_configs = true
# Scope to first-party engine code only; skip vendored / other-language trees.
exclude = [
    "portal/",
    "portal-v2/",
    "website/",
    "node_modules/",
    "archive/",
    "tests/",
    ".planning/",
]
```

(B) `requirements-dev.txt` — isolated dev tooling, NEVER installed by the
production pipeline. Pin recent versions:

```
# Dev-only lint/type-check tooling. NOT part of the production pipeline.
# The production pipeline installs ONLY requirements.txt — do NOT add these
# tools there (LOCKED constraint 3). Install locally / in CI with:
#   pip install -r requirements-dev.txt
ruff==0.8.6
mypy==1.14.1
```
  </action>
  <verify>
    <automated>python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); assert 'tool' in d and 'ruff' in d['tool'] and 'mypy' in d['tool'], 'missing tool tables'; assert 'build-system' not in d, 'build-system table present'; assert 'project' not in d, 'project table present'; print('pyproject OK')"</automated>
    <automated>python -c "t=open('requirements-dev.txt').read().lower(); assert 'ruff' in t and 'mypy' in t, 'dev deps missing'; print('dev-deps OK')"</automated>
    <automated>python -c "t=open('requirements.txt').read().lower(); assert 'ruff' not in t and 'mypy' not in t, 'PROD requirements.txt polluted with dev tools'; print('prod requirements clean')"</automated>
  </verify>
  <done>
pyproject.toml exists with [tool.ruff], [tool.ruff.lint], [tool.mypy] and NO
[build-system]/[project] tables; requirements-dev.txt exists pinning ruff +
mypy; requirements.txt is unchanged (no ruff/mypy added).
  </done>
</task>

<task type="auto">
  <name>Task 2: Add isolated, non-blocking python-lint CI workflow</name>
  <files>.github/workflows/python-lint.yml</files>
  <action>
Create a NEW workflow file `.github/workflows/python-lint.yml`. Do NOT touch
weekly-excel-generation.yml or any other existing workflow (LOCKED constraint 1).
The workflow MUST be NON-BLOCKING (LOCKED constraint 2): a finding can never
fail CI. Use BOTH belt-and-suspenders mechanisms — `continue-on-error: true`
on the job AND non-blocking run semantics on each tool step (ruff `--exit-zero`,
mypy with `|| true`). Trigger on `push` and `pull_request` only — NO `schedule`,
NO cron. Single Python version (3.12, matching CI). Keep it minimal. Mirror the
production workflow's action versions and least-privilege permissions.

```yaml
name: Python Lint (warn-only)

# Visibility-first, non-blocking lint + type-check for the Python billing
# engine. Findings NEVER fail CI, block a merge, or affect the production
# cron pipeline (weekly-excel-generation.yml). This is intentionally
# warn-only — enforcement is a separate, later decision.
#
# Isolated from production: this file is the ONLY lint/type-check workflow.
# weekly-excel-generation.yml is untouched.

permissions:
  contents: read

on:
  push:
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    # Belt-and-suspenders #1: the entire job is non-blocking, so even an
    # infrastructure hiccup in lint/type-check cannot fail the check run.
    continue-on-error: true
    timeout-minutes: 15
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dev tooling
        # Dev tools only — NOT the production requirements.txt.
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Ruff (warn-only)
        # Belt-and-suspenders #2: --exit-zero makes ruff always exit 0 even
        # when it reports findings, AND continue-on-error guards the step.
        continue-on-error: true
        run: ruff check . --exit-zero

      - name: Mypy (warn-only)
        # Belt-and-suspenders #2: `|| true` swallows a non-zero mypy exit,
        # AND continue-on-error guards the step. Scope to first-party engine
        # files; mypy reads exclude/ignore_missing_imports from pyproject.toml.
        continue-on-error: true
        run: mypy generate_weekly_pdfs.py audit_billing_changes.py billing_audit || true
```
  </action>
  <verify>
    <automated>python -c "import yaml" 2>nul || pip install pyyaml -q</automated>
    <automated>python -c "import yaml; d=yaml.safe_load(open('.github/workflows/python-lint.yml')); on=d.get('on') or d.get(True); assert 'push' in on and 'pull_request' in on, 'must trigger on push + pull_request'; assert 'schedule' not in on, 'must NOT be scheduled'; job=d['jobs']['lint']; assert job.get('continue-on-error') is True, 'job must be non-blocking'; print('workflow non-blocking + correct triggers OK')"</automated>
    <automated>git diff --quiet -- .github/workflows/weekly-excel-generation.yml && echo "PROD workflow unchanged" || (echo "FAIL: production workflow modified" && exit 1)</automated>
  </verify>
  <done>
.github/workflows/python-lint.yml exists; triggers on push + pull_request (no
schedule/cron); the lint job has continue-on-error: true; ruff runs with
--exit-zero and mypy with `|| true`; weekly-excel-generation.yml is unchanged.
  </done>
</task>

</tasks>

<verification>
Phase-level checks (run from repo root):

1. Production workflow byte-for-byte unchanged:
   `git diff --stat -- .github/workflows/weekly-excel-generation.yml` shows NO changes.
2. Production requirements.txt unchanged (no ruff/mypy):
   `git diff -- requirements.txt` shows NO changes.
3. Only additive new files in the changeset:
   `git status --porcelain` shows only `pyproject.toml`, `requirements-dev.txt`,
   `.github/workflows/python-lint.yml` as new (untracked/added). Any doc-pointer
   edit (CLAUDE.md / AGENTS.md "Validation Commands") is the ONLY allowed exception
   and was intentionally skipped this task to keep blast radius minimal.
4. pyproject.toml is tool-config-only:
   parses with tomllib; has [tool.ruff] + [tool.mypy]; NO [build-system]/[project].
5. New workflow is non-blocking and correctly triggered (push + pull_request, no cron).
6. Tools actually run locally (sanity — findings are expected and OK):
   `pip install -r requirements-dev.txt && ruff check . --exit-zero` exits 0.
</verification>

<success_criteria>
- pyproject.toml created with ONLY [tool.ruff]/[tool.ruff.lint]/[tool.mypy]
  tables (no [build-system], no [project]); line-length 79; target py310;
  mypy ignore_missing_imports + lenient flags; vendored/other-language dirs excluded.
- requirements-dev.txt created pinning ruff + mypy; requirements.txt untouched.
- .github/workflows/python-lint.yml created: isolated, triggers on push +
  pull_request only, single Python 3.12, NON-BLOCKING (job continue-on-error
  + ruff --exit-zero + mypy `|| true`).
- weekly-excel-generation.yml and all other existing workflows are byte-for-byte unchanged.
- Changeset limited to the three additive new files.
</success_criteria>

<output>
After completion, create
`.planning/quick/260528-mdc-add-warn-only-ruff-and-mypy-lint-tooling/260528-mdc-SUMMARY.md`
</output>
