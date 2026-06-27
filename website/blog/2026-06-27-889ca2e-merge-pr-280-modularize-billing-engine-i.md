---
slug: 889ca2e-merge-pr-280-modularize-billing-engine-i
title: "Merge PR #280: modularize billing engine into pipeline/ package (Phase 09) (889ca2e)"
authors: [runbook-bot]
tags: [configuration, github, other, project, python, tests]
date: 2026-06-27T07:30:04.720951+00:00
---

**Branch:** `master` &middot; **Commit:** [`889ca2e`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/889ca2e35b8ac27a0e01702f7855edf9f1c62c03) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/28282563316).

<!-- truncate -->

## Commits in this push

- [`889ca2e`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/889ca2e) — Merge PR #280: modularize billing engine into pipeline/ package (Phase 09)
- [`ff20710`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/ff20710) — fix: address Codex P2 review findings (oracle coverage + facade API)
- [`071a71d`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/071a71d) — fix: prevent facade double-import on direct execution (Greptile P1)
- [`6044e7a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/6044e7a) — ci: make codecov coverage informational (not a merge gate)
- [`45df1ef`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/45df1ef) — docs+test: address PR #280 reviewer comments
- [`2cfa942`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/2cfa942) — fix: VAC pre-pass mirrors Units Completed? gate (LOW-01)
- [`5005040`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/5005040) — refactor: modularize billing engine into pipeline/ package (Phase 09)

## Changed files

### GitHub config

- `.github/copilot-instructions.md`

### Python — entry points

- `generate_weekly_pdfs.py`

### Python — scripts/

- `scripts/check_api_equality.py`
- `scripts/check_facade_completeness.py`
- `scripts/check_run_summary_structure.py`

### Tests

- `tests/golden/baseline_names.json`
- `tests/golden/facade_allowlist.json`
- `tests/golden/mypy_baseline.txt`
- `tests/golden/mypy_baseline_count.txt`
- `tests/golden/run_summary_baseline.json`
- `tests/test_billing_audit_shadow.py`
- `tests/test_entrypoint_no_double_import.py`
- `tests/test_facade_harness.py`
- `tests/test_live_proxy_globals.py`
- `tests/test_performance_optimizations.py`
- `tests/test_primary_claim_attribution.py`
- `tests/test_security_audit_followup.py`
- `tests/test_sentry_init_idempotency.py`
- `tests/test_sentry_log_sanitizer.py`
- `tests/test_sentry_session_tags.py`
- `tests/test_subcontractor_helper_shadow_rescue.py`
- `tests/test_subcontractor_pricing.py`
- `tests/test_subcontractor_primary_claim_attribution.py`
- `tests/test_subproject_e_hash_store.py`
- `tests/test_vac_crew_claim_attribution.py`
- `tests/test_vac_crew_exclusion_leak.py`
- `tests/validate_production_safety.py`

### Project docs

- `.claude/agents/billing-audit-analyst.md`
- `.claude/agents/excel-output-verifier.md`
- `.claude/agents/smartsheet-pipeline-debugger.md`
- `.claude/context-map.md`
- `.claude/project-state.md`
- `.claude/rules/billing-pipeline-guardrails.md`
- `.claude/skills/force-week-regeneration/SKILL.md`
- `.claude/skills/investigate-price-anomaly/SKILL.md`
- `.claude/skills/run-billing-pipeline-locally/SKILL.md`
- `.claude/writeback-pending/README.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `CLAUDE.md`
- `docs/AI_CONTEXT_RESUME.md`
- `docs/CHANGELOG_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/PROJECT_BRIEF.md`
- `docs/refactor-assessment-generate-weekly-pdfs.md`
- `memory-bank/activeContext.md`
- `memory-bank/living-ledger.md`

### Configuration

- `.claude/context-policy.json`
- `codecov.yml`

### Other

- `.claude/hooks/session-context-inject.sh`
- `.claude/hooks/session-handoff.sh`
- `.gitignore`
- `pipeline/__init__.py`
- `pipeline/attribution.py`
- `pipeline/change_detection.py`
- `pipeline/cleanup.py`
- `pipeline/config.py`
- `pipeline/discovery.py`
- `pipeline/excel.py`
- `pipeline/fetch.py`
- `pipeline/grouping.py`
- `pipeline/observability.py`
- `pipeline/orchestrate.py`
- `pipeline/pricing.py`
- `pipeline/types.py`
- `pipeline/upload.py`
- `pipeline/utils.py`
- `scripts/check_mypy_delta.sh`
- `scripts/run_6_gates.sh`
