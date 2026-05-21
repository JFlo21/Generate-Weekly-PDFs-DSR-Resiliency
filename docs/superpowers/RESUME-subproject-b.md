# RESUME — Subproject B (Subcontractor Primary Claim Attribution)

**Saved:** 2026-05-20 (mid-execution context handoff)
**Why:** Session approaching context limit. This file lets a fresh session pick up EXACTLY where we stopped.

---

## TL;DR — where we are right now

- **Mission:** Implement **Subproject B** of the universal per-line-item claim-attribution effort: re-partition the subcontractor PRIMARY Excel variants (`reduced_sub` / `aep_billable`) by the **frozen primary claimer** from `billing_audit`, consuming Foundation A's `resolve_claimer` + HOLD contract. Foundation A already shipped (on master).
- **Method:** superpowers **subagent-driven-development** — fresh subagent per task, two-stage review (spec then code-quality) between tasks. (Decided: superpowers plan + GSD quality gates after.)
- **Branch:** `feat/subproject-b-primary-claim-attribution` (off `master`; carries the spec + plan commits). **Do NOT work on master.**
- **Progress:** Tasks **1–7 of 11 are committed and the full suite is green (738 passed / 26 skipped).** HEAD = `3297753`.
- **EXACT NEXT STEP:** (1) Run Task 7's formal **two-stage review** (it was committed + suite-verified but the spec/code-quality review subagents had NOT been dispatched when we paused — see "Outstanding" below). (2) Then implement **Task 8** (hash-history prune). Then Tasks 9, 10, 11, final whole-impl review, finishing-a-development-branch, then GSD gates.

## Key artifacts (read these on resume)

- **Spec:** `docs/superpowers/specs/2026-05-20-subproject-b-subcontractor-primary-claim-attribution-design.md`
- **Plan (task-by-task, full code):** `docs/superpowers/plans/2026-05-20-subproject-b-subcontractor-primary-claim-attribution.md`
- **Foundation A spec (parent):** `docs/superpowers/specs/2026-05-20-claim-attribution-foundation-design.md`
- New test file: `tests/test_subcontractor_primary_claim_attribution.py`

## The 5 operator-approved design decisions (the contract)

1. **Partition model = fallback-to-current.** Rows with a frozen primary claimer group under that claimer; rows with no frozen claimer yet (`no_history`) fall back to current `effective_user`. (All rows reaching the variant block are `Units Completed?`-checked.)
2. **Kill switch (attribution) = reuse `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`** (default on). Documented scope broadened to cover primary partitioning too.
3. **Filename = `_ReducedSub_User_<name>` / `_AEPBillable_User_<name>`** (reserved `_User_` token; parser unambiguous vs `_Helper_`).
4. **Migration = explicit forced cleanup + one-time version-sentinel hash prune**, gated by the NEW kill switch `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED` (default on, destructive-cleanup rule [2026-05-19 22:00] #4).
5. **Outage = HOLD.** On `fetch_failure`, defer the row (`record_attribution_hold`) and emit no primary file that run; fire `summarize_attribution_holds()` once at end-of-run. B is Foundation A's first HOLD consumer. **Accepted asymmetry:** primary HOLDs on outage; the unchanged Phase 1.1 helper-shadow path still falls back and generates.
6. **Wiring = Approach A (parallel pre-pass).** `group_source_rows` resolves all subcontractor rows' claimers in a bounded `ThreadPoolExecutor` into `{__row_id: ResolveOutcome}` BEFORE the grouping loop (honors the [2026-04-25 14:00] per-row-Supabase latency lesson). `billing_audit/` is NOT modified.

## Task status + commit SHAs (on `feat/subproject-b-primary-claim-attribution`)

| Task | What | Commit(s) | Review status |
|---|---|---|---|
| 1 | Parser: `_User_` token in ReducedSub/AEPBillable branches of `build_group_identity` | `e759321` + fix `5063047` | spec ✅ + code-quality ✅ (fixes applied: trimmed test imports, added empty-claimer contract test, comments) |
| 2 | `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED` env var + startup banner | `d8dd30e` | controller-verified (inert config) ✅ |
| 3 | `_subcontractor_primary_variant_suffix` helper + `generate_excel` rewire | `06dac00` | controller-verified (diff + round-trip test) ✅ |
| 4 | **Core:** parallel attribution pre-pass + HOLD-aware emission | `07c2b0f` | spec (controller) ✅ + code-quality (subagent) ✅ — reviewer confirmed correct; its "Critical" was just "Task 5 must land before merge" |
| 5 | Three identity sites (CR-01 lockstep) + behavioral round-trip test | `7ff45e7` | controller-verified (diff + round-trip test) ✅ |
| 6 | End-of-run `summarize_attribution_holds()` call in `main()` | `5343002` | controller-verified (placement) ✅ |
| 7 | Migration: `sub_legacy_primary_variants` param + gate + both call sites + signature test update | `3297753` | **committed + suite green, but FORMAL TWO-STAGE REVIEW NOT YET RUN** ⚠️ |

Earlier commits on the branch: `3ce7b02` (plan), `706a7ca` (spec), then `646fdea` (master merge base).

## Outstanding before continuing

1. **Task 7 review (do this FIRST on resume).** Task 7 touched DESTRUCTIVE attachment-deletion logic and 4 files. Dispatch a code-quality review (base `5343002` → head `3297753`) focused on: the new migration gate (`not _identifier` + `ident not in valid_wr_weeks` live-exemption), the TARGET call-site `_sub_scope` decoupling (must stay byte-identical when only `LEGACY_HELPER` is on), the PPP call-site addition, and TWO collateral test edits the implementer made beyond the stated scope:
   - `tests/test_security_audit_followup.py` — updated `TestPppCleanupUntrackedAttachments.test_cleanup_function_signature_unchanged` (added `sub_legacy_primary_variants` as 10th param + default-None check). **Verify this is correct, not a weakening.**
   - `tests/test_subcontractor_pricing.py` — `TestPppCleanupInvocationCarriesWhitelist::test_target_cleanup_does_not_carry_whitelist` had a brittle regex (`[^()]*`) that broke on the new nested parens `sub_offcontract_variants=(_target_offcontract or None)`; implementer widened it to `(?:[^()]|\([^()]*\))*`. **Verify the regex still asserts the original intent (TARGET carries no `variant_whitelist`).**

## Remaining tasks (full code in the plan file)

- **Task 8** — `_run_subproject_b_hash_prune(hash_history, groups)` + `SUBPROJECT_B_HASH_PRUNE_VERSION = 1` (sentinel key `_subproject_b_prune_version`, distinct from Phase 1.1's `_phase_prune_version`) + register PII marker `"Subproject B hash-history prune"` in `_PII_LOG_MARKERS` + call site (fail-safe try/except) right after the `_run_phase_1_1_hash_prune(hash_history, groups)` call (~the load_hash_history region in `main()`). Drops legacy blank-identifier `reduced_sub`/`aep_billable` orphans for in-scope sub WRs. `save_hash_history`/`load_hash_history` already preserve any `_`-prefixed sentinel. Tests use in-memory dicts (no new imports needed). Expected suite after: ~743.
- **Task 9** — regression tests: `TestNonSubVariantsPreserved`, `TestPrePassConcurrency` (50-row parallel resolve), `TestSubprojectBProductionInvariants` (source-grep guards). Then full suite.
- **Task 10** — pin `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED: '1'` in `.github/workflows/weekly-excel-generation.yml`; document new var + broadened `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED` scope in `website/docs/reference/environment.md`. (Docusaurus build may not run locally — rely on CI if so.)
- **Task 11** — append Living Ledger entry to `CLAUDE.md` (date-stamped) covering B + the 5 decisions + the new env var + `SUBPROJECT_B_HASH_PRUNE_VERSION` + accepted HOLD asymmetry + CR-01 extension + final `pytest tests/` count. Final `pytest tests/` must exit 0.
- **Final whole-implementation code review** (base = branch point `646fdea` or `3ce7b02`, head = final commit).
- **Finish branch:** invoke `superpowers:finishing-a-development-branch` (PR / merge decision).
- **Then GSD gates:** `/gsd-code-review` on the branch diff + `/gsd-verify-work` UAT (user-triggered for the latter). Address HIGH/BLOCKER findings before merge.

## Process learnings / GOTCHAS (important for the resuming session)

1. **Subagent shell permissions:** A FRESH foreground `Agent` dispatch CAN run `pytest`/`git commit`. A **background `SendMessage`-resume gets shell DENIED** — so for review fixes, either dispatch a fresh foreground agent OR (for trivial fixes) apply + verify + commit yourself as controller.
2. **Branch fragmentation:** Long/heavy subagent runs (Tasks 3 & 4, high tool counts) created stray `codex-*` branches and even **renamed the active branch** (Task 4 ended on `codex-helper-generation-analysis`). After EVERY implementer task, run `git branch --show-current`; if drifted, `git checkout feat/subproject-b-primary-claim-attribution && git merge --ff-only <stray>` to reconcile (fast-forward only — non-destructive). Stray branches present: `codex-helper-generation-bug` (`ba60239`), `codex-helper-generation-analysis` (`07c2b0f`). They are redundant; user may delete with `git branch -D` (destructive — needs user consent).
3. **Test file import discipline:** `tests/test_subcontractor_primary_claim_attribution.py` header was trimmed to a minimal set in Task 1; each task adds the imports its appended classes need. Currently present: `sys, unittest, Path, _ensure_smartsheet_mocked, inspect, pathlib, mock, _reset_all`, module-level `from billing_audit.writer import ResolveOutcome`, and the `_make_sub_primary_row` fixture. Reuse fixtures/imports already there.
4. **Review calibration used:** full two-stage subagent review for complex/destructive tasks (4 done, 7 pending); direct controller verification (read diff + run suite) for mechanical/inert tasks (2, 3, 5, 6) and trivial fixes.
5. **Never on master.** Production billing engine; 2-hourly cron runs from master. Keep work on the feat branch; merge via PR after review.

## How to resume (suggested first moves)

1. `git -C <repo> branch --show-current` → must be `feat/subproject-b-primary-claim-attribution` at `3297753`. If not, reconcile per gotcha #2.
2. `python -m pytest tests/ -q` → expect `738 passed, 26 skipped`.
3. Run the **Task 7 review** (Outstanding #1). Fix anything it flags.
4. Implement **Task 8** from the plan (subagent-driven), then 9, 10, 11, final review, finish branch, GSD gates.
