---
slug: 3e71b84-merge-pull-request-176-from-jflo21claude
title: "Merge pull request #176 from JFlo21/claude/fix-vac-crews-detection-nN1Tx (3e71b84)"
authors: [runbook-bot]
tags: [project, python, tests]
date: 2026-04-23T20:39:34.513690+00:00
---

**Branch:** `master` &middot; **Commit:** [`3e71b84`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3e71b846da2db67b73251cb6c38a4a99c1386ba8) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/24857698678).

<!-- truncate -->

## Commits in this push

- [`3e71b84`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3e71b84) — Merge pull request #176 from JFlo21/claude/fix-vac-crews-detection-nN1Tx
- [`1762872`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/1762872) — fix(review): leftmost-strong parser + helper file_identifier + valid_wr_weeks sanitize
- [`0a62963`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/0a62963) — fix(review): strong/weak WeekEnding candidate split kills identifier collisions (Codex round-12)
- [`c4b7548`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/c4b7548) — fix(review): rightmost-valid WeekEnding delimiter (Codex round-11)
- [`058c125`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/058c125) — fix(review): format-aware WeekEnding detection handles identifier collisions (Codex round-10)
- [`fbeb09c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/fbeb09c) — fix(review): align hash-prune + cap redacted payload + drop dead test imports
- [`d8bf42b`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/d8bf42b) — fix(review): broaden source WR collision quarantine to sanitized-key alone (Codex round-9 P1)
- [`a0917fc`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a0917fc) — fix(review): build_group_identity picks rightmost WeekEnding (Copilot round-8)
- [`3fc067f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3fc067f) — fix(review): robust build_group_identity parser + source-side WR collision quarantine (Codex round-7)
- [`4c1c7b8`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/4c1c7b8) — docs: correct create_target_sheet_map collision comment to match quarantine behavior
- [`5f35215`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/5f35215) — fix(review): quarantine colliding target_map keys; guard fast-path on partial cache corruption
- [`942a40c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/942a40c) — fix(review): _RE_REDACT_WR matches alphanumeric + path-traversal WR IDs (Codex P2)
- [`0eae5f8`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/0eae5f8) — fix(review): scope weekly fallback to snapshot-mapped sheets; detect WR key collisions (Codex P1/P2)
- [`9d0a2ab`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/9d0a2ab) — fix(review): note-gate + summary coverage + type hint (3 Copilot follow-ups)
- [`47735ca`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/47735ca) — fix(review): align wr_num across target_map, upload task, and delete path (Codex P2)
- [`bd23e72`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/bd23e72) — fix(review): harden cache guard + recalc-note unparseable-date coverage
- [`aaa0a58`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/aaa0a58) — fix(security): sanitize wr_num in filenames, redact PII in Sentry context
- [`d1e6079`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/d1e6079) — fix(vac-crew): recalc fallback rescues current-week rows with blank Snapshot Date

## Changed files

### Python — entry points

- `generate_weekly_pdfs.py`

### Tests

- `tests/test_security_audit_followup.py`
- `tests/test_subcontractor_pricing.py`

### Project docs

- `CLAUDE.md`
