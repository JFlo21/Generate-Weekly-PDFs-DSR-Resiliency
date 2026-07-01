---
slug: 8c51a3c-fix-smartsheet-api-resilience-silent-fai
title: "fix: Smartsheet API resilience + silent-failure & PII hardening (#281) (8c51a3c)"
authors: [runbook-bot]
tags: [other, project, python, tests]
date: 2026-07-01T02:49:16.706510+00:00
---

**Branch:** `master` &middot; **Commit:** [`8c51a3c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/8c51a3cd8a8d57353d03c56f70cd0ca40d183049) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/28490059854).

<!-- truncate -->

## Commits in this push

- [`8c51a3c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/8c51a3c) — fix: Smartsheet API resilience + silent-failure & PII hardening (#281)

## Changed files

### Python — entry points

- `generate_weekly_pdfs.py`

### Tests

- `tests/golden/baseline_names.json`
- `tests/golden/facade_allowlist.json`
- `tests/test_billing_audit_shadow.py`
- `tests/test_performance_optimizations.py`
- `tests/test_sentry_frame_var_scrub.py`
- `tests/test_sentry_log_sanitizer.py`
- `tests/test_smartsheet_retry.py`
- `tests/test_subcontractor_helper_shadow_rescue.py`

### Project docs

- `.claude/project-state.md`
- `memory-bank/living-ledger.md`

### Other

- `pipeline/discovery.py`
- `pipeline/fetch.py`
- `pipeline/grouping.py`
- `pipeline/observability.py`
- `pipeline/orchestrate.py`
- `pipeline/retry.py`
