---
slug: abf905d-feat11-08-retire-local-json-caches-and-a
title: "feat(11-08): retire local JSON caches and attachment pre-fetch (INC-05) (#373) (abf905d)"
authors: [runbook-bot]
tags: [configuration, docs, github, other, project, python, tests, workflows]
date: 2026-09-01T02:54:55.721514+00:00
---

**Branch:** `master` &middot; **Commit:** [`abf905d`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/abf905d70748a7ea090819cbc6657373af720472) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/33464298187).

<!-- truncate -->

## Commits in this push

- [`abf905d`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/abf905d) — feat(11-08): retire local JSON caches and attachment pre-fetch (INC-05) (#373)

## Changed files

### Workflows & CI

- `.github/workflows/weekly-excel-generation.yml`

### GitHub config

- `.github/prompts/configuration-environment.md`

### Python — entry points

- `generate_weekly_pdfs.py`

### Tests

- `tests/golden/baseline_names.json`
- `tests/golden/facade_allowlist.json`
- `tests/golden/mypy_baseline.txt`
- `tests/golden/mypy_baseline_count.txt`
- `tests/test_change_detection_tiebreak.py`
- `tests/test_group_identity_and_header_foreman.py`
- `tests/test_incremental_read.py`
- `tests/test_performance_optimizations.py`
- `tests/test_pipeline_memory_shadow.py`
- `tests/test_primary_claim_attribution.py`
- `tests/test_subcontractor_helper_shadow_rescue.py`
- `tests/test_subcontractor_pricing.py`
- `tests/test_subcontractor_primary_claim_attribution.py`
- `tests/test_subproject_e_hash_store.py`
- `tests/test_vac_crew.py`
- `tests/test_vac_crew_claim_attribution.py`

### Docs site

- `website/blog/2026-08-31-inc05-cache-retirement.md`
- `website/docs/learn/for-engineers.md`
- `website/docs/reference/environment.md`
- `website/docs/runbook/operations.md`
- `website/docs/runbook/python-modules.md`
- `website/docs/runbook/workflows.md`

### Project docs

- `.claude/project-state.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/phases/11-incremental-read-affected-group-regeneration/.continue-here.md`
- `.planning/phases/11-incremental-read-affected-group-regeneration/11-07-SUMMARY.md`
- `.planning/phases/11-incremental-read-affected-group-regeneration/11-08-SUMMARY.md`
- `.planning/phases/11-incremental-read-affected-group-regeneration/11-PATTERNS.md`
- `.planning/phases/11-incremental-read-affected-group-regeneration/deferred-items.md`
- `CLAUDE.md`
- `docs/run-memory-write-flip-checklist.md`
- `memory-bank/living-ledger.md`

### Configuration

- `.planning/HANDOFF.json`

### Other

- `billing_audit/schema.sql`
- `pipeline/attribution.py`
- `pipeline/change_detection.py`
- `pipeline/config.py`
- `pipeline/discovery.py`
- `pipeline/observability.py`
- `pipeline/orchestrate.py`
- `pipeline_memory/reader.py`
