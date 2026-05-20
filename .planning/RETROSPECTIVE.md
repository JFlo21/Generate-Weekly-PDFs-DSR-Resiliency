# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Subcontractor Rate Logic

**Shipped:** 2026-05-20
**Phases:** 2 (01 + inserted 01.1) | **Plans:** 19 | **Tests at close:** 682 passed / 26 skipped / 58 subtests

### What Was Built
- Two subcontractor-scoped Excel variants — `_AEPBillable` (3%-increase AEP rates, snapshot-gated) and `_ReducedSub` (13%-reduced rates) — priced from `data/subcontractor_rates.csv`, additive to the production pipeline.
- Dual-target attachment routing (`_ReducedSub` → TARGET + `SUBCONTRACTOR_PPP_SHEET_ID`) with independent collision quarantine, daemon-executor PPP prefetch, and a symmetric end-of-run PPP cleanup pass.
- Shadow-foreman/helper variants made production-functional via the Phase 01.1 pre-acceptance price rescue, variant partitioning, PPP cleanup whitelist, and per-row claim-history attribution against `billing_audit.attribution_snapshot`.

### What Worked
- **Kill-switch-first, additive-only discipline.** Every new code path gates on `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` (default-ON, workflow-pinned) with byte-identical primary/helper/VAC-crew/ORIG-folder outputs preserved — the "don't break production" constraint held end-to-end.
- **Living Ledger as the decision spine.** ~30 dated ADR-equivalent rules in CLAUDE.md gave every gap-closure round a precedent to extend rather than re-derive (e.g., the source-side WR collision quarantine and the daemon-executor prefetch trifecta were reused verbatim for the PPP leg).
- **Cross-phase integration check caught nothing broken** because the variant-string vocabulary was kept consistent through group keys → `build_group_identity` → filter matchers → `pipeline_run.variant` → PPP whitelist.

### What Was Inefficient
- **Phase 01 shipped with three latent production bugs** (helper-shadow rescue gap, additive-vs-partition tagging, stale PPP attachments) that only surfaced in production and required the inserted Phase 01.1 hotfix + a 2-cycle `/gsd-debug` session. Root cause: unit tests exercised helpers in isolation; the full main-loop attachment-identity / row-acceptance pipeline was never driven end-to-end.
- **Two gap-closure rounds** (~30+ review findings across CR/WR/IN) after the original 6 plans — a lot of it traceable to the same class of "mirror test passes while production reverted" trap.
- **Traceability drift:** Phase 01.1's SUB-08..12 were verified in VERIFICATION.md but never recorded in REQUIREMENTS.md or SUMMARY frontmatter — only caught and fixed during the milestone audit.

### Patterns Established
- **Three-site identity-consistency invariant** for any new filename-embedding variant (per-group identifier + `valid_wr_weeks` cleanup tuple + `current_keys` prune key must move in lockstep).
- **Mirror-matcher invariant**: a new group-key suffix must extend BOTH `_key_matches_wr` and `_key_matches_excluded_wr`.
- **Pre-acceptance-rescue generalization**: any new pricing surface that diverges from `Units Total Price` needs a parallel rescue at the row-acceptance gate, env-gated default-ON.
- **End-to-end test methodology**: row-flow bug fixes MUST add a test that drives the real pipeline; static mirror classes do not count.

### Key Lessons
1. **Drive the full pipeline in tests for any row-flow / attachment-identity change.** The Phase 01 → 01.1 bug cluster was entirely a "tested the helper, not the path" failure. Phase 01.1 added `TestEndToEndPipeline` as the standing guard.
2. **Close the requirements loop at phase completion, not at milestone close.** Formalize new requirement IDs in REQUIREMENTS.md + SUMMARY frontmatter the moment a phase introduces them.
3. **A retroactively-bootstrapped GSD project inherits real production risk.** "Code-complete + tests green" is necessary but not sufficient here — production-observable acceptance (live cron) is a first-class deferred item, not an afterthought.

### Cost Observations
- Model mix: predominantly Opus 4.7 (planning, gap-closure, audit); integration check delegated to a Sonnet subagent.
- Sessions: multiple across 2026-05-14 → 2026-05-20 (planning bootstrap → Phase 01 → gap-closure → Phase 01.1 hotfix → audit → close).
- Notable: the inserted hotfix phase (01.1) cost roughly as much review/closure effort as the original feature, underscoring the value of end-to-end tests up front.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 2 | 19 | First GSD milestone on an established production repo; introduced inserted-phase hotfix flow + milestone audit-before-close gate |

### Cumulative Quality

| Milestone | Tests (pass) | Skipped | Zero-Dep Additions |
|-----------|--------------|---------|--------------------|
| v1.0 | 682 | 26 | All additive (no new top-level deps; `xlsxwriter` deliberately not added) |

### Top Lessons (Verified Across Milestones)

1. End-to-end pipeline tests prevent the "mirror passes, production reverts" trap — established v1.0; re-validate in v1.1.
2. Kill-switch-first + additive-only is the safe pattern for changes to the production billing engine — held through v1.0.
