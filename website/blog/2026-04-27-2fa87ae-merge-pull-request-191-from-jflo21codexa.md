---
slug: 2fa87ae-merge-pull-request-191-from-jflo21codexa
title: "Merge pull request #191 from JFlo21/codex/analyze-performance-issues-in-actions-workflow (2fa87ae)"
authors: [runbook-bot]
tags: [other, python, tests, workflows]
date: 2026-04-27T01:36:51.480587+00:00
---

**Branch:** `master` &middot; **Commit:** [`2fa87ae`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/2fa87aec32b137703cfe47dfdfa08a92ad5ca0ba) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/24972495508).

<!-- truncate -->

## Commits in this push

- [`2fa87ae`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/2fa87ae) — Merge pull request #191 from JFlo21/codex/analyze-performance-issues-in-actions-workflow
- [`408a1c0`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/408a1c0) — fix: ensure BA row cache file exists, optimize uncached check, add tests
- [`df47344`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/df47344) — fix: address CodeQL, reviewer, and docstring issues from PR #191
- [`fbffa7d`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/fbffa7d) — Cache successful freeze rows to cut repeated Supabase RPCs
- [`e2f3eeb`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/e2f3eeb) — Cap weekly workflow runtime to 1h50 with budget cushion

## Changed files

### Workflows & CI

- `.github/workflows/weekly-excel-generation.yml`

### Python — entry points

- `generate_weekly_pdfs.py`

### Tests

- `tests/test_billing_audit_shadow.py`

### Other

- `billing_audit/writer.py`
