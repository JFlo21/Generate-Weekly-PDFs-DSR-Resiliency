---
slug: c1235ac-merge-pull-request-161-from-jflo21claude
title: "Merge pull request #161 from JFlo21/claude/add-sentry-logging-KLMdb (c1235ac)"
authors: [runbook-bot]
tags: [project, python, tests]
date: 2026-04-20T19:01:54.763282+00:00
---

**Branch:** `master` &middot; **Commit:** [`c1235ac`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/c1235acab03c230ffece5dc5edc0db7d56c4b16b) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/24684903902).

<!-- truncate -->

## Commits in this push

- [`c1235ac`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/c1235ac) — Merge pull request #161 from JFlo21/claude/add-sentry-logging-KLMdb
- [`5dade3a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/5dade3a) — fix(sentry): block legacy WR_*.xlsx purge logs in sanitizer
- [`a3f9a34`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a3f9a34) — test(sentry): env-patch import + real-SDK kwarg check
- [`a88b9e9`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a88b9e9) — fix(sentry): block runtime WR-list logs in PII sanitizer
- [`342bb54`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/342bb54) — test(sentry): verify sentry_sdk.init kwargs via mocked init
- [`2fb9c84`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/2fb9c84) — fix(sentry): block totals-validation + group_key logs in sanitizer
- [`0fefe59`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/0fefe59) — fix(sentry): block non-WR#-prefixed WR-identifier logs in sanitizer
- [`20fc63c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/20fc63c) — fix(sentry): block filename-bearing attachment logs in sanitizer
- [`54f1b4b`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/54f1b4b) — fix(sentry): fail closed on falsy non-string log bodies
- [`afa721a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/afa721a) — fix(sentry): block helper/VAC-crew group summary logs in sanitizer
- [`4d65d49`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/4d65d49) — docs(sentry): correct sentry_before_send_log docstring
- [`db884db`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/db884db) — fix(sentry): block ESSENTIAL FIELDS log family in PII sanitizer
- [`a05f6d9`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a05f6d9) — fix(sentry): fail-closed sanitizer, expanded markers, unit tests
- [`613b5fe`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/613b5fe) — feat(sentry): add before_send_log PII sanitizer for Sentry Logs
- [`b8819e0`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/b8819e0) — fix(sentry): gate Sentry Logs behind SENTRY_ENABLE_LOGS env var
- [`f913bc6`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/f913bc6) — feat(sentry): enable Sentry Logs in Python billing engine

## Changed files

### Python — entry points

- `generate_weekly_pdfs.py`

### Tests

- `tests/test_sentry_log_sanitizer.py`

### Project docs

- `CLAUDE.md`
- `docs/sentry-implementation.md`
