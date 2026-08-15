---
phase: quick-260814-me8
plan: 01
subsystem: infra
tags: [health-check, github-actions, ci, config-guardrail, greptile]

# Dependency graph
requires:
  - phase: quick-260814-system-health-entrypoint
    provides: validate_system_health.py entry point and CheckResult/HealthContext scaffolding
provides:
  - check_production_workflow_config() parsing weekly-excel-generation.yml directly for PARALLEL_WORKERS / PARALLEL_WORKERS_DISCOVERY / TIME_BUDGET_MINUTES drift
  - registration of production_workflow_config in run_checks()
  - relabeled check_config_sanity scope (process-env-only, secondary layer)
affects: [system-health-check-workflow, billing-pipeline-guardrails]

actuals:
  tokens: 5093
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "stdlib-only YAML text parsing (comment-stripping + regex key/value extraction) instead of adding PyYAML, mirroring the module's existing no-new-deps posture"
    - "detail-hygiene helper (redact secrets-context marker + echo-limit truncation) applied to every raw value before it can reach a JSON report string"

key-files:
  created: []
  modified:
    - validate_system_health.py
    - tests/test_validate_system_health.py

key-decisions:
  - "Parse the authoritative workflow file (weekly-excel-generation.yml) directly instead of trusting the health job's own process environment, which structurally never carries PARALLEL_WORKERS/TIME_BUDGET_MINUTES"
  - "GitHub expression values (${{ ... || 'N' }}) resolve to their || fallback literal, since that is what a scheduled (non-dispatch) run actually receives"
  - "Only a missing workflow file is CRITICAL; every parse ambiguity (unresolvable expression, non-numeric value) degrades to WARN so a YAML formatting change cannot hard-fail the health job"
  - "check_config_sanity kept as an explicitly-labelled secondary layer (process-environment scope only) rather than removed, in case the health job is ever given those env vars directly"

patterns-established:
  - "Detail-hygiene: redact any value containing the secrets-context marker and cap echo length before a workflow value reaches a problem string or a ctx.notes entry"

requirements-completed: [GREPTILE-339-CONFIG-VACUOUS]

coverage:
  - id: D1
    description: "check_production_workflow_config detects PARALLEL_WORKERS / PARALLEL_WORKERS_DISCOVERY / TIME_BUDGET_MINUTES drift in weekly-excel-generation.yml even though the health job's process env never exports them"
    requirement: "GREPTILE-339-CONFIG-VACUOUS"
    verification:
      - kind: unit
        ref: "tests/test_validate_system_health.py::TestProductionWorkflowConfig (12 cases: happy path, comment immunity, over-cap primary/discovery, at-cap boundary, non-numeric budget, ceiling comparison both directions, missing file, unresolvable expression, absent keys, detail hygiene)"
        status: pass
    human_judgment: false
  - id: D2
    description: "production_workflow_config is registered inside run_checks() and check_config_sanity states its process-environment-only scope"
    requirement: "GREPTILE-339-CONFIG-VACUOUS"
    verification:
      - kind: unit
        ref: "tests/test_validate_system_health.py::TestProductionCheckRegistration::test_production_check_is_registered"
        status: pass
      - kind: unit
        ref: "tests/test_validate_system_health.py::TestConfigSanityScopeLabel::test_env_check_detail_states_process_scope"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full test suite passes with no regressions, py_compile clean, and the live workflow file (currently pinned to worker=8/8, TIME_BUDGET_MINUTES=165, timeout-minutes=180) grades STATUS_OK"
    verification:
      - kind: unit
        ref: "python -m pytest tests/ -q -> 1371 passed, 132 subtests passed"
        status: pass
      - kind: other
        ref: "python -c \"import validate_system_health as vsh; vsh.check_production_workflow_config(vsh.HealthContext())\" -> ('ok', 'production workflow config within documented guardrails')"
        status: pass
    human_judgment: false

duration: ~15min
completed: 2026-08-14
status: complete
---

# Quick Task 260814-me8: Fix vacuous health-check config guardrail Summary

**`check_production_workflow_config` parses `weekly-excel-generation.yml` directly with stdlib-only regex/comment-stripping so the health check can actually catch PARALLEL_WORKERS/TIME_BUDGET_MINUTES drift, closing the Greptile finding that the guardrail read an environment structurally guaranteed to be empty.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3/3 completed
- **Files modified:** 2 (`validate_system_health.py`, `tests/test_validate_system_health.py`)
- **Commits:** 1 atomic commit

## Accomplishments

- Added `check_production_workflow_config(ctx, path=None)` — reads `.github/workflows/weekly-excel-generation.yml` from disk (path resolved from `__file__`, never process cwd, mirroring `check_facade_import`), strips comments before any key/ceiling match, resolves GitHub Actions expression fallbacks (`${{ ... || 'N' }}`), and grades the two `PARALLEL_WORKERS*` keys against the documented cap of 8 and `TIME_BUDGET_MINUTES` as strictly-less-than the max live `timeout-minutes`.
- Registered `production_workflow_config` inside `run_checks()` immediately after `config_sanity`, so both config layers report adjacently in the JSON output and CI logs.
- Relabeled `check_config_sanity`'s docstring and every emitted problem/OK string to explicitly state its scope is "process environment" only (wording-only change — no status, threshold, or SENTRY_DSN behavior touched).
- Added detail-hygiene: any raw workflow value that contains a secrets-context marker is fully redacted, and every echoed value is truncated to a fixed limit, before it can reach a problem string, a note, or the JSON report.
- Verified live: importing the module and calling the new check against the real (unmodified) `weekly-excel-generation.yml` returns `STATUS_OK` — the file currently pins both worker fallbacks to 8, `TIME_BUDGET_MINUTES` to 165, and `timeout-minutes` to 180.

## Task Commits

Executed as a single atomic commit per plan's Task 3 instruction (both files changed together; TDD red/green was done inline within the one commit rather than as separate test/feat commits, since the plan's task-level commit protocol calls for one commit covering the two files):

1. **Tasks 1–3: parse production workflow, register check, relabel scope, validate + commit** — `9690cdd` (`fix(quick-260814-me8): parse prod workflow for health config drift`)

## Files Created/Modified

- `validate_system_health.py` — added `WORKFLOW_PATH`, `MAX_PARALLEL_WORKERS`, `WORKFLOW_WORKER_KEYS`, detail-hygiene constants, four private stdlib parsing helpers (`_strip_comment`, `_resolve_value`, `_find_key_value`, `_find_timeout_minutes`), `_sanitize_detail_value`, `check_production_workflow_config`, registration in `run_checks()`, and the `check_config_sanity` scope relabel.
- `tests/test_validate_system_health.py` — new `TestProductionWorkflowConfig` (12 cases against temp-file fixtures), `TestProductionCheckRegistration`, and `TestConfigSanityScopeLabel` classes (14 new tests total; suite grew from 21 to 35 tests).

## Decisions Made

- Parsed the workflow YAML with stdlib regex/text handling rather than adding PyYAML — the plan explicitly excluded that dependency, and the existing module has zero non-stdlib parsing dependencies today.
- Comment lines are stripped globally before any regex match runs (both for key lookups and the `timeout-minutes` ceiling collector), so a value or ceiling that only ever appears inside a `#` comment can neither satisfy nor trip the guardrail.
- `TIME_BUDGET_MINUTES` is only compared against the ceiling when at least one live `timeout-minutes` value was found; otherwise the ambiguity becomes an informational note, not a problem, keeping the disposition monotonically conservative (never false-positive WARN on absence).

## Deviations from Plan

None — plan executed exactly as written. All `must_haves.truths` and `key_links` in the plan frontmatter are satisfied by the implementation (verified against the live workflow file's actual line content, which had drifted a few lines from the plan's stated line numbers 271/272/535 to 280/281/544 due to intervening commits — the parser is line-number-agnostic by design, so this had no functional impact).

## Issues Encountered

None. The parser was validated against the real (unmodified) `weekly-excel-generation.yml` file content before finalizing the tests, confirming the comment-stripping and expression-fallback logic matches the file's actual shapes (prose mention of `timeout-minutes: 180` at line 6, prose mentions of `TIME_BUDGET_MINUTES` in the comment block preceding line 544, live `timeout-minutes: 180` at line 130, live worker/budget keys at lines 280/281/544).

## User Setup Required

None — no external service configuration required. This is a pure code change to a health-check script that already runs unattended in `system-health-check.yml`.

## Next Phase Readiness

- The fix is committed on `feat/260814-system-health-entrypoint` at `9690cdd` in the worktree `scratchpad/pr339-wt`, ready to be pushed/reviewed as part of PR #339's follow-up.
- `.github/workflows/weekly-excel-generation.yml` was read-only throughout — confirmed via `git status --short` showing only the two intended files changed.
- No blockers. This closes the single outstanding Greptile finding referenced by requirement `GREPTILE-339-CONFIG-VACUOUS`.

---
*Quick task: 260814-me8*
*Completed: 2026-08-14*

## Self-Check: PASSED
- FOUND: .planning/quick/260814-me8-fix-health-check-config-guardrail-vacuou/260814-me8-SUMMARY.md
- FOUND: commit 9690cdd (worktree scratchpad/pr339-wt, branch feat/260814-system-health-entrypoint)
