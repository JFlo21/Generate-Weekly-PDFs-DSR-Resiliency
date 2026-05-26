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

## Hotfix: v1.0.1 — Phase 02 (Attribution Bulk-Prefetch + Historical Claimer Remediation)

**Shipped:** 2026-05-26 (post-v1.0-tag hotfix line on master)
**Phases:** 1 (Phase 02) | **Plans:** 6 (4 executed + 2 gap-closure) | **Tests at close:** 986 passed / 29 skipped / 69 subtests

### What Was Built
- A single bulk `lookup_attribution_bulk` RPC + fail-safe `prefetch_attribution` reader replaced the four per-row attribution pre-passes (Foundation A/B/C/D), feeding a shared `_attr_map` consumed O(1) at every claimer-resolution site.
- Removed the `ATTRIBUTION_RESOLUTION_WEEKS` recency-scope gate entirely (it was the footgun behind the incident) and added graceful degradation (`ATTRIBUTION_BULK_PREFETCH_FALLBACK`, default-ON) that distinguishes a missing RPC (`rpc_missing` → per-row fallback) from a genuine outage (`fetch_failure` → HOLD).
- A default-OFF, dry-run-first, isolated `run_claimer_remediation` garbage-attachment sweep (TARGET + PPP, live-identity exempt) reachable via `advanced_options`, plus a documented human-gated runbook for safely re-activating Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE` stays dormant `'0'`).

### Root Cause (why the hotfix existed)
The v1.0 `ATTRIBUTION_RESOLUTION_WEEKS=8` scope hotfix gated group-KEY / filename formation (not merely skip optimization). When Sub-project E was flipped authoritative (`67539ec`), its `no_row → regenerate` wave for historical groups resolved claimers from the empty out-of-scope pre-pass → `_User__NO_MATCH` / `_User_Unknown_Foreman` names on 372 of 1,116 files. The frozen-claimer data existed in `attribution_snapshot`; the read side just never loaded it for old weeks.

### What Worked
- **Bulk-load-not-scope.** The fix eliminated per-row network cost entirely (O(chunks), ~137k → a few RPCs) rather than re-tuning a recency window — removing the gate-on-key-formation footgun at the root.
- **Ship-dormant + human-gated flip.** Sub-project E re-activation was kept a separate, deliberately human-gated operator action — the exact guardrail whose absence (a premature auto-flip) caused the incident.
- **Audit-before-close caught the real shape:** v1.0 was already tagged; the audit surfaced that Phase 02 is a post-tag hotfix line, avoiding a destructive re-archive.

### What Was Inefficient
- **A v1.0 hotfix (the `ATTRIBUTION_RESOLUTION_WEEKS` scope gate) became a production incident** because a recency/scope gate was placed on identity-tuple formation rather than on a pure skip optimization. One guardrail mistake cascaded into garbage filenames across hundreds of files.
- **One BLOCKER + 9 advisory review findings** required a 2-plan gap-closure round (02-05/02-06) after the original 4 plans.

### Patterns Established
- **A recency/scope gate must NEVER sit on group-KEY / filename formation — only on skip optimizations.** Any value that participates in `history_key` / `file_identifier` / `valid_wr_weeks` / on-disk filename must be resolved for every group that generates.
- **Per-row external I/O over all source rows must be ELIMINATED via bulk load, not merely parallelized** — parallelism hides an O(all-history) call count until the dataset grows enough to blow the time budget.
- **A go-live flip that depends on a separate code fix is a documented, human-gated operator action — never bundled into the fix PR.**

### Key Lessons
1. **Scope/recency gates belong on skip paths, never on identity formation.** The v1.0 scope hotfix saved time-budget but silently corrupted filenames once another feature (E) consumed the same path differently.
2. **Dormant-ship + explicit human gate is the correct pattern for data-contract-dependent activations** (Supabase RPC deploy, schema change, backfill). The incident was a skipped gate, not a code bug.
3. **Bulk-load is the durable fix for per-row I/O at history scale** — not parallelization, not scoping.

### Cost Observations
- Model mix: Opus 4.7 (planning, gap-closure, audit, milestone close); integration check + Nyquist auditor available as Sonnet subagents.
- Sessions: multiple across 2026-05-26 (incident diagnosis → bulk-prefetch fix → remediation → gap-closure → validation → audit → hotfix close).
- Notable: full Nyquist VALIDATION coverage reached for all three phases during close (Phase 01 reconstructed State B, Phase 01.1 promoted from draft, Phase 02 already compliant).

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 2 | 19 | First GSD milestone on an established production repo; introduced inserted-phase hotfix flow + milestone audit-before-close gate |
| v1.0.1 | 1 | 6 | Post-tag hotfix line; bulk-load replaces per-row I/O; ship-dormant + human-gated activation pattern formalized |

### Cumulative Quality

| Milestone | Tests (pass) | Skipped | Zero-Dep Additions |
|-----------|--------------|---------|--------------------|
| v1.0 | 682 | 26 | All additive (no new top-level deps; `xlsxwriter` deliberately not added) |
| v1.0.1 | 986 | 29 | All additive (new Supabase RPC + reader; no new top-level Python deps) |

### Top Lessons (Verified Across Milestones)

1. End-to-end pipeline tests prevent the "mirror passes, production reverts" trap — established v1.0; re-validate in v1.1.
2. Kill-switch-first + additive-only is the safe pattern for changes to the production billing engine — held through v1.0.
