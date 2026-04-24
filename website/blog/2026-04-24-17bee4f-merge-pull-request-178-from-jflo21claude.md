---
slug: 17bee4f-merge-pull-request-178-from-jflo21claude
title: "Merge pull request #178 from JFlo21/claude/add-supabase-snapshot-writer-QEbGJ (17bee4f)"
authors: [runbook-bot]
tags: [other, python, tests, workflows]
date: 2026-04-24T06:13:12.398046+00:00
---

**Branch:** `master` &middot; **Commit:** [`17bee4f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/17bee4fa4832817249379f76d5851781afa3c1c6) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/24875199847).

<!-- truncate -->

## Commits in this push

- [`17bee4f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/17bee4f) — Merge pull request #178 from JFlo21/claude/add-supabase-snapshot-writer-QEbGJ
- [`f1cdbf6`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/f1cdbf6) — fix(review): PII-safe span name + sampled latency validator
- [`a949a2a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a949a2a) — fix(review): backfill fails on unexpected freeze_row exceptions (Codex P2)
- [`15bf03c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/15bf03c) — fix(review): flag-resolved contract + rerun-aware run_id + robust validator
- [`0a4e829`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/0a4e829) — harden: pre-loop try/except + production-safety validation harness
- [`8fe5d2d`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/8fe5d2d) — fix(review): resolve primary from __effective_user, not variant-scoped field
- [`fb371a3`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/fb371a3) — fix(review): freeze + fingerprint use effective assignee, not raw Foreman
- [`bf57ce9`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/bf57ce9) — fix(review): sub-bucket helper rows by identity before hashing (Codex P2)
- [`7027e8c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/7027e8c) — fix(review): timestamp run_id fallback + distinguish backfill flag failures
- [`e177360`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/e177360) — fix(review): row-level fail-open + gated pre-aggregation + robust tests
- [`a6275e4`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a6275e4) — fix(review): any_flag_enabled fails open on flag-read blip (Codex P2)
- [`f110ca3`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/f110ca3) — fix(review): variant-aware aggregated content hash + minor polish
- [`34194c9`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/34194c9) — fix(review): split cheap bucket assembly from lazy content-hash (Codex P2)
- [`2adb599`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/2adb599) — fix(review): gate fingerprint pre-aggregation behind flag + sync docstring
- [`c44df3d`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/c44df3d) — fix(review): aggregate pipeline_run.content_hash across variants (Codex P2)
- [`1f8213a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/1f8213a) — fix(review): cross-variant fingerprint + distinct ops for breaker isolation
- [`cb8eb38`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/cb8eb38) — fix(review): load dotenv in backfill before get_client() (Codex P2)
- [`7396178`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/7396178) — fix(review): align circuit-breaker docstring + normalize freeze_row args
- [`356867a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/356867a) — fix(review): normalize backfill release/run_id to empty strings (Codex P2)
- [`d3e5fe2`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/d3e5fe2) — fix(review): per-op circuit breaker + accurate attempt/cost reporting
- [`b505c53`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/b505c53) — fix(review): recover from transient flag blips + drop remaining self-import
- [`cba0cb1`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/cba0cb1) — fix(review): batch of PR #178 hot-path + resilience optimizations
- [`1291b71`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/1291b71) — fix(review): record dedup key only after successful upsert (Codex P2)
- [`d9075ed`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/d9075ed) — fix(review): address PR #178 review feedback (Codex + Copilot)
- [`56ec20a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/56ec20a) — feat: add Supabase attribution snapshot writer (shadow mode)

## Changed files

### Workflows & CI

- `.github/workflows/weekly-excel-generation.yml`

### Python — entry points

- `generate_weekly_pdfs.py`

### Python — scripts/

- `scripts/backfill_attribution_snapshot.py`

### Tests

- `tests/test_billing_audit_shadow.py`
- `tests/test_validate_production_safety.py`
- `tests/validate_production_safety.py`

### Other

- `billing_audit/__init__.py`
- `billing_audit/client.py`
- `billing_audit/fingerprint.py`
- `billing_audit/writer.py`
- `requirements.txt`
