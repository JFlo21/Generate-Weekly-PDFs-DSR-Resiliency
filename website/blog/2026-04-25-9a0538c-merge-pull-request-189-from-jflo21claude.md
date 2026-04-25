---
slug: 9a0538c-merge-pull-request-189-from-jflo21claude
title: "Merge pull request #189 from JFlo21/claude/debug-billing-audit-logs-2FiTe (9a0538c)"
authors: [runbook-bot]
tags: [other, project, python, tests]
date: 2026-04-25T03:57:02.754999+00:00
---

**Branch:** `master` &middot; **Commit:** [`9a0538c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/9a0538c7f15984e084d115ca98ee8ca19936d7fe) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/24922016299).

<!-- truncate -->

## Commits in this push

- [`9a0538c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/9a0538c) — Merge pull request #189 from JFlo21/claude/debug-billing-audit-logs-2FiTe
- [`d0d8a0c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/d0d8a0c) — fix(billing_audit): address PR #189 review feedback on perf commit
- [`e1c828f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/e1c828f) — perf(billing_audit): parallelize per-row freeze_row to fix 1h→3h regression
- [`cfaab1f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/cfaab1f) — fix(billing_audit): address PR #189 review feedback
- [`a46b555`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a46b555) — fix(billing_audit): classify SQLSTATE codes + ship canonical schema.sql

## Changed files

### Python — entry points

- `generate_weekly_pdfs.py`

### Tests

- `tests/test_billing_audit_shadow.py`
- `tests/validate_production_safety.py`

### Project docs

- `CLAUDE.md`

### Other

- `billing_audit/__init__.py`
- `billing_audit/client.py`
- `billing_audit/schema.sql`
- `billing_audit/writer.py`
