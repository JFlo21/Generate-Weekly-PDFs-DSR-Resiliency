---
phase: quick-260528-mdc
plan: "01"
subsystem: ci-tooling
tags: [ruff, mypy, lint, ci, warn-only, dev-tooling]
dependency_graph:
  requires: []
  provides: [warn-only ruff+mypy lint workflow, pyproject tool config]
  affects: [.github/workflows/python-lint.yml, pyproject.toml, requirements-dev.txt]
tech_stack:
  added: [ruff==0.8.6, mypy==1.14.1]
  patterns: [non-blocking CI lint, isolated dev-deps file, tool-config-only pyproject]
key_files:
  created: [pyproject.toml, requirements-dev.txt, .github/workflows/python-lint.yml]
  modified: []
decisions:
  - "Lint/type-check is WARN-ONLY (non-blocking): job-level continue-on-error +
    ruff --exit-zero + mypy || true. Visibility first; enforcement is a later decision."
  - "Dev tools (ruff, mypy) live in requirements-dev.txt, NEVER requirements.txt, so the
    production pipeline's pip install is byte-identical."
  - "pyproject.toml is tool-config-only (no [build-system]/[project]) so pip/build behavior
    is unchanged."
  - "New isolated workflow python-lint.yml; production weekly-excel-generation.yml untouched."
metrics:
  completed: "2026-05-28"
  note: "Executor interrupted by an API socket error after creating the 3 files but before
    committing/summarizing; orchestrator verified the files against all gates, committed
    (7f8dbfb), and wrote this summary."
---

# Quick Task 260528-mdc: Warn-only ruff + mypy lint tooling — Summary

Wired up Python lint + type-check tooling for the ~3,100-line production billing engine in
**warn-only (non-blocking)** mode, fully isolated from the production pipeline. CLAUDE.md
had flagged ruff/mypy/uv as "aspirational, not yet wired up"; this makes ruff + mypy real
and safe without any risk to the Smartsheet → Excel → Smartsheet cron workflow.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tool-config `pyproject.toml` + isolated `requirements-dev.txt` | 7f8dbfb | pyproject.toml, requirements-dev.txt |
| 2 | Isolated non-blocking `python-lint.yml` workflow | 7f8dbfb | .github/workflows/python-lint.yml |

(Both plan tasks were committed together as a single atomic change — 3 files, 103 insertions.)

## Production-Safety Gates (all verified by orchestrator)

- **weekly-excel-generation.yml UNCHANGED** — `git diff --quiet` clean; new workflow is separate.
- **requirements.txt UNCHANGED** — no `ruff`/`mypy` added; production `pip install` unaffected.
- **pyproject.toml tool-config-only** — `tomllib` parse confirms `[tool.ruff]`+`[tool.mypy]`
  present, `[build-system]`/`[project]` absent.
- **Workflow non-blocking** — job `continue-on-error: true`, `ruff check . --exit-zero`,
  `mypy ... || true`; triggers on `push`/`pull_request` only (no `schedule`/cron).
- **Blast radius** — only the 3 additive new files changed (+ .planning docs). No production
  Python touched; no auto-fix/reformat performed.

## Config Decisions

- **ruff:** `line-length = 79` (CLAUDE.md PEP 8), `target-version = "py310"`,
  `select = ["E","F","I","UP","B"]`, vendored/other-language trees excluded.
- **mypy:** `python_version = "3.10"`, `ignore_missing_imports = true` (SDKs lack stubs),
  lenient (no `--strict`); scoped to first-party engine, excludes portal/website/tests/etc.
- **CI:** `actions/checkout@v4`, `actions/setup-python@v5`, Python `3.12` (matches prod CI),
  `permissions: contents: read`.

## Deviations from Plan

### Process deviation (not a content deviation)

The gsd-executor subagent was interrupted by an API socket error after it had created all
three files but **before** it committed them or wrote this SUMMARY. The orchestrator did not
re-spawn (to avoid duplicate/conflicting writes); instead it independently verified the
already-created files against every plan verify gate (all passed), committed them atomically
(7f8dbfb), and authored this summary. File contents match the plan exactly; no rework needed.

## Self-Check

- pyproject.toml exists, valid TOML, tool-config-only: PASS
- requirements-dev.txt has ruff + mypy; requirements.txt does not: PASS
- python-lint.yml non-blocking (continue-on-error + --exit-zero), push/PR only, no cron: PASS
- weekly-excel-generation.yml untouched: PASS
- Commit 7f8dbfb: verified via `git log`
- Files changed = 3 additive new files only: PASS

## Self-Check: PASSED

## Follow-ups (optional, not in scope)

- After observing a few CI runs, decide whether to promote any ruff rule subset to blocking.
- Consider a one-time `ruff check --statistics` baseline to size the cleanup backlog.
- `uv` migration remains aspirational (CLAUDE.md) — untouched here.
