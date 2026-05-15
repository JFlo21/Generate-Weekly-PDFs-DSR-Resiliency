---
phase: 01-subcontractor-rate-logic-modification
plan: 06
subsystem: validators-tests-docusaurus
tags: [regression, production-safety, e2e, runbook, docusaurus, phase-1-wrap]

# Dependency graph
requires:
  - phase: 01-subcontractor-rate-logic-modification (Plan 01)
    provides: "_SUBCONTRACTOR_RATES_FINGERPRINT module constant + 3 env vars + startup banner state log"
  - phase: 01-subcontractor-rate-logic-modification (Plan 02)
    provides: "build_group_identity 7-variant round-trip + D-20 conditional fingerprint mix-in scoped to the 4 new variants only"
  - phase: 01-subcontractor-rate-logic-modification (Plan 03)
    provides: "group_source_rows emits the 4 new variant group keys; generate_excel produces the 4 new filename suffixes; missing-CU WARNING surface"
  - phase: 01-subcontractor-rate-logic-modification (Plan 04)
    provides: "Dual-target routing for _ReducedSub via SUBCONTRACTOR_PPP_SHEET_ID; independent collision quarantine on second target_map"
  - phase: 01-subcontractor-rate-logic-modification (Plan 05)
    provides: "billing_audit.pipeline_run.variant TEXT column + freeze_row/emit_run_fingerprint variant kwarg threading"
provides:
  - "tests/validate_production_safety.py: post-Phase-1 inline comment pinning the 18 kB window cap (measured: 17,738 chars; 262-char headroom) + Warning 8 reconciliation note cross-referencing Plan 05 Task 3's 24 kB substring window"
  - "tests/test_subcontractor_pricing.py: TestPhase1IntegrationRegression (5 hash-stability tests locking ROADMAP success criterion 5) + TestPhase1FilenameRoundTripCoverage (1 parametrized test, 7 subtests over the 7 variants) — Warning 11 split lock-in"
  - "website/docs/reference/environment.md: new 'Subcontractor rate variants' section (positioned after Smartsheet targets) documenting SUBCONTRACTOR_RATES_CSV / SUBCONTRACTOR_PPP_SHEET_ID / SUBCONTRACTOR_RATE_VARIANTS_ENABLED with Default / Purpose / Valid values / Rollback for each"
  - "website/docs/runbook/workflows.md: new 'Subcontractor rate variants' subsection under the weekly-excel-generation.yml section synthesizing the what/why/how into one coherent operator-facing entry (NOT a commit dump per .claude/rules/documentation-maintenance.md rule 1)"
  - "Bidirectional cross-links between the runbook and the env-var reference (Docusaurus build resolves both directions clean — no broken cross-links)"
  - "Operator-confirmed Step A approval for the human-verify checkpoint; Step B (real-data SKIP_UPLOAD price-write gate) deferred to the next scheduled production run per Warning 10's documented fallback verification surface"
affects:
  - "Phase 1 ship readiness — every Plan 1-6 deliverable is in place; the kill switch ships ENABLED by default, with the env-var flip to '0' as the documented rollback path"
  - "CLAUDE.md Living Ledger — autonomous-cloud-memory-injection rule will append a Phase 1 wrap entry when the merging PR opens (separate execution surface; not this plan's responsibility)"
  - "ROADMAP.md Phase 1 status — Plan 06 checkbox flips to [x]; phase status flips to complete"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Post-feature measurement-driven validator pinning: measure the actual block size first (Python one-liner extracting char distance between block header and closing except clause), then either hold the cap or bump to the next 3 kB increment. The inline comment records the measurement so a future reviewer doesn't need to re-measure to justify the cap choice."
    - "Cross-plan window-size reconciliation in inline comments: when two plans use different window sizes for different validator purposes (Plan 06 Task 1's enforcement cap = 18 kB; Plan 05 Task 3's substring-find window = 24 kB), the larger of the two MUST be acknowledged in the smaller one's comment so a future engineer reading the validator knows the relationship is intentional, not accidental drift."
    - "Hash-stability regression class shape: setUp/tearDown pins EVERY env-var that influences hash output (EXTENDED_CHANGE_DETECTION, RATE_CUTOFF_DATE, _RATES_FINGERPRINT, _SUBCONTRACTOR_RATES_FINGERPRINT) — both at the module level and via importlib.reload. Without exhaustive pinning, a developer running pytest with a real .env file gets non-deterministic test outcomes that drift between local and CI."
    - "Class-name-matches-content discipline (Warning 11): when a class assertion spans two different invariants (hash stability vs. filename round-trip), the cleaner taxonomy is to split into two named classes rather than stuff both under a name that describes only one. The test taxonomy is itself documentation; a misnamed class is a future maintenance trap."
    - "Docusaurus runbook synthesis rule: when documenting a multi-plan feature, write one coherent narrative section that answers what changed / why / how it impacts operators, with cross-links into the env-var reference for the technical knobs. Do NOT paste individual plan summaries — that violates .claude/rules/documentation-maintenance.md rule 1. Cross-links to anchor sections (#subcontractor_rates_csv, #smartsheet-targets) keep the bidirectional navigation intact."
    - "Page-choice deviation handling: when a plan references a doc path that does not exist, locate the closest equivalent in the actual repo structure AND document the choice inline in the SUMMARY (operator can re-trace the decision later). For Phase 1 the original plan referenced website/docs/operations/weekly-pipeline.md; the actual runbook lives at website/docs/runbook/workflows.md, so the changelog entry landed there with explicit deviation documentation in this SUMMARY."

key-files:
  created:
    - ".planning/phases/01-subcontractor-rate-logic-modification/01-06-SUMMARY.md"
  modified:
    - "tests/validate_production_safety.py: post-Phase-1 inline comment block at L138-167 pinning the 18 kB window cap (Task 1)"
    - "tests/test_subcontractor_pricing.py: TestPhase1IntegrationRegression (5 methods) + TestPhase1FilenameRoundTripCoverage (1 parametrized method, 7 subtests) (Task 2)"
    - "generate_weekly_pdfs.py: _txn = None hoisted to main() initialization block at the top, fixing the pre-existing UnboundLocalError in the finally block (deviation discovered during Task 3 Step A; orchestrator-side fix, commit 7e4777c)"
    - "website/docs/reference/environment.md: new 'Subcontractor rate variants' section documenting the 3 env vars (Task 4)"
    - "website/docs/runbook/workflows.md: new 'Subcontractor rate variants' subsection synthesizing what/why/how (Task 4)"

key-decisions:
  - "Window cap held at 18 kB (Task 1). Post-Phase-1 measurement of the per-group billing_audit block via inline Python script: 17,738 chars. Remaining headroom: 262 chars. Bump to 21 kB would have been the next 3 kB increment but is unjustified — the cap is the authoritative source-of-truth on max allowed block size, not a generous default. Over-permissive caps reduce the validator's signal. Inline comment at tests/validate_production_safety.py L138-167 documents the measurement, the headroom, and the policy-grounded rationale per CLAUDE.md 2026-04-25 14:00 rule 3."
  - "Warning 8 reconciliation (Task 1). The inline comment near the cap explicitly names Plan 05 Task 3's 24 kB inspect.getsource substring window and explains why they intentionally differ: the 24 kB Plan 05 window is a find-or-die check (asserts required substrings ARE present, not that the block is BOUNDED); the 18 kB cap here is the authoritative source-of-truth on max allowed block size. The two serve different validator purposes; a future reviewer reading either file sees the relationship without needing to grep across plans."
  - "Class split (Task 2). TestPhase1IntegrationRegression owns hash-stability tests (the byte-identical guarantee for primary/helper/vac_crew that locks ROADMAP success criterion 5, plus the positive companion that aep_billable hash changes under _SUBCONTRACTOR_RATES_FINGERPRINT mutation). TestPhase1FilenameRoundTripCoverage owns the parser ↔ generator symmetry across all 7 variants. The prior misnamed TestPhase1EndToEndByteIdenticalRegression class name conflated the two invariants — Warning 11 lock-in. Both classes pin EXTENDED_CHANGE_DETECTION, RATE_CUTOFF_DATE, _RATES_FINGERPRINT, AND _SUBCONTRACTOR_RATES_FINGERPRINT in setUp/tearDown so developer-env vars cannot destabilize the suite."
  - "Page-choice deviation for Task 4. The plan referenced website/docs/operations/weekly-pipeline.md which does NOT exist — the actual runbook lives at website/docs/runbook/*.md. workflows.md was chosen over operations.md because the variant emission is a workflow-scoped behaviour (the on-call engineer reading weekly-excel-generation.yml's behaviour section wants the variant emission + target-routing + missing-CU surface co-located there). operations.md covers running-the-generator-by-hand and is at the wrong altitude. The decision is documented inline in Task 4's commit message and re-traced here for full traceability."
  - "Step B deferred to next scheduled production run (Task 3 — operator decision)."
    " Operator's resume signal: 'approved Step A; Step B deferred to scheduled production run'. Step A confirmed the startup banner (all 3 env vars + correct values + 3691 CUs + fingerprint e4941a5e86c4f8ce + CSV path) and the existing primary files generated cleanly. Local operator env lacks SMARTSHEET_API_TOKEN, so the SKIP_UPLOAD real-data price-write gate (Step B per Warning 10) cannot run locally. The next scheduled GitHub Actions production run with SUBCONTRACTOR_RATE_VARIANTS_ENABLED=1 will exercise the CSV-driven price-write path end-to-end. Risk envelope is bounded: the kill switch ships ENABLED with the env-var flip to '0' as the documented rollback path; the Plan 3 unit tests (TestSubcontractorVariantPriceSubstitution + TestResolveRowPriceCanonicalColumnNames) cover the helper-level behaviour; what Step B would have exercised is the integration with the workbook cell writer, which is also pinned by Plan 3's TestGenerateExcelReturnTupleShape + TestSubcontractorVariantOpenpyxlCompliance."
  - "Pre-existing _txn = None master bug fix (orchestrator-side, commit 7e4777c). Surfaced during Task 3 Step A verification. Root cause: _txn was initialized inside the main() session block AFTER both the synthetic TEST_MODE return (L5304) and the 'SMARTSHEET_API_TOKEN not configured' raise (L5306) — added 2026-03-24 in 61291fb5, broken since. The finally block referenced _txn and crashed with UnboundLocalError whenever either short-circuit fired, masking the actual exit status. Fix: hoist _txn = None to the top of main() in the same initialization block as _cron_checkin_id = None. Idempotent and minimal. NOT part of this plan's source-code scope — Plan 06 Task 4 is doc-only — but documented here because it surfaced during this plan's human-verify checkpoint and a future archaeologist tracing the fix back through git log will land on this SUMMARY."

patterns-established:
  - "Window cap measurement before bump decision: run the inline Python script that locates the block header + closing except clause + computes the char distance, THEN decide based on the measurement whether the existing cap is right-sized. Inline-comment the measurement so the decision is auditable."
  - "Class-name-matches-content discipline for regression test classes: a class that pins multiple invariants gets split into one class per invariant. The taxonomy is documentation; a misnamed class is a future maintenance trap (Warning 11)."
  - "Doc-path deviation handling pattern: when a plan references a path that does not exist, locate the closest equivalent in the actual repo structure, choose based on the document's intended altitude (workflow-scoped behaviour vs. operator-action workflow), and document the choice in both the commit message and the SUMMARY so the deviation is traceable."
  - "Bidirectional cross-link discipline for multi-page operator documentation: when adding feature documentation that spans the env-var reference and the runbook, link in both directions via Docusaurus relative-path anchors. The build's broken-cross-link detector catches drift; the manual link audit during this SUMMARY confirms the round-trip."

requirements-completed: []
# All 7 SUB-* requirements (SUB-01..SUB-07) were completed across
# Plans 1-5; Plan 06 is the validators / regression / runbook wrap
# that proves they're locked but does not directly complete any
# new requirement.

# Metrics
duration: ~25min
# Task 1 + Task 2 landed earlier in commits 9cfb652 + f79fd5b
# (~10 min of work, separate executor); Task 3 was the human-verify
# checkpoint (~5 min operator time including the _txn fix discovery);
# Task 4 + this SUMMARY ran ~10 min in this sequential executor pass.
completed: 2026-05-14
---

# Phase 01 Plan 06: Regression Lock + Validator Pin + Runbook Update Summary

**Phase 1 ship-readiness lands cleanly. Task 1 (production-safety validator window cap) and Task 2 (Phase 1 hash-stability + filename round-trip regression classes) were committed earlier in commits `9cfb652` + `f79fd5b` after measuring the per-group billing_audit block at 17,738 chars and confirming the 18 kB cap holds with 262-char headroom. Task 3 (human-verify checkpoint) received an `approved-step-A-only` resume signal from the operator: Step A (TEST_MODE synthetic-data file-mix coverage) verified the 3 env vars + 3691 loaded CUs + `e4941a5e86c4f8ce` fingerprint + clean existing primary file generation; Step B (SKIP_UPLOAD real-data price-write gate) was deferred to the next scheduled GitHub Actions production run because the local operator env lacks `SMARTSHEET_API_TOKEN`. Step A also surfaced a pre-existing master bug — `_txn = None` initialized AFTER the synthetic-mode return and the missing-token raise in `main()` — fixed in commit `7e4777c` by hoisting the init to the top of `main()`. Task 4 (Docusaurus runbook update) lands in this sequential executor pass: a new "Subcontractor rate variants" section in `website/docs/reference/environment.md` documents the three Phase 1 env vars (with Default / Purpose / Valid values / Rollback), and a synthesized changelog section in `website/docs/runbook/workflows.md` answers the what / why / how operator-impact narrative per `.claude/rules/documentation-maintenance.md` rule 1. Cross-links between the two pages are bidirectional; `cd website && npm run typecheck && npm run build` both exit 0 with zero broken cross-links. The original plan's `website/docs/operations/weekly-pipeline.md` reference was a path drift — that file does not exist in this repo; `workflows.md` was chosen with explicit rationale documented inline. Final `pytest tests/` count: 537 passed / 22 skipped / 16 subtests (unchanged from post-Task-2 baseline; doc-only changes do not affect Python tests). The `TestPhase1IntegrationRegression` + `TestPhase1FilenameRoundTripCoverage` class split (Warning 11) is intact; the prior misnamed `TestPhase1EndToEndByteIdenticalRegression` name does NOT appear in the codebase. Phase 1 is ready to ship via PR.**

## Performance

- **Duration:** ~25 min total across the three executors involved
  - Task 1 + Task 2 (earlier executor, commits `9cfb652` + `f79fd5b`): ~10 min
  - Task 3 human-verify (operator-driven, surfacing the `_txn` fix in `7e4777c`): ~5 min
  - Task 4 + SUMMARY + state updates (this sequential executor): ~10 min
- **Tasks:** 4 (Tasks 1, 2, 4 autonomous; Task 3 was the human-verify checkpoint approved with caveat)
- **Files modified (this executor pass — Task 4 + SUMMARY + state updates):** 4 (`website/docs/reference/environment.md`, `website/docs/runbook/workflows.md`, `.planning/phases/01-subcontractor-rate-logic-modification/01-06-SUMMARY.md`, plus `.planning/STATE.md` + `.planning/ROADMAP.md` in the final metadata commit)
- **Tests:** 537 passed / 22 skipped / 16 subtests passed — unchanged from the post-Task-2 baseline. Task 4 is doc-only; no Python tests added or modified in this executor pass.

## Accomplishments

### Task 1 — Production-safety validator window cap pinned (commit `9cfb652`, earlier executor)

Post-Phase-1 measurement of the per-group `billing_audit` block in `generate_weekly_pdfs.py`: **17,738 chars** between the `# ── Billing audit snapshot: freeze personnel` header and the matching `except Exception as _audit_err:` clause. The existing 18 kB (`18000`) cap holds with 262-char headroom — no bump required per CLAUDE.md 2026-04-25 14:00 rule 3.

Inline comment at `tests/validate_production_safety.py` L138-167 documents:
- The post-Phase-1 measurement (17,738 chars).
- The decision rationale (cap remains at 18000 with intentional headroom; over-permissive caps reduce the validator's signal).
- **Warning 8 reconciliation:** the 24 kB substring window in Plan 05 Task 3's `inspect.getsource` check is intentionally larger because it is a find-or-die check (asserts required substrings ARE present, not that the block is BOUNDED). This 18 kB cap is the authoritative source-of-truth on max allowed block size; the 24 kB Plan 05 window is a superset that finds the kwargs reliably across small reflows.

`python tests/validate_production_safety.py` exits 0. Full `pytest tests/` exits 0 with 531 passed / 22 skipped (Task 2 had not yet landed at this point in the wave).

### Task 2 — Phase 1 hash-stability + filename round-trip regression (commit `f79fd5b`, earlier executor)

**Class split per Warning 11 lock-in** — two separate classes with explicit invariants:

**`TestPhase1IntegrationRegression`** (5 methods) — locks ROADMAP success criterion 5:

- `test_primary_hash_byte_identical_across_sub_fingerprint_mutations` — `__variant='primary'` hash stable across `_SUBCONTRACTOR_RATES_FINGERPRINT='A'` → `'B'` mutation (byte-identical guarantee).
- `test_helper_hash_byte_identical_across_sub_fingerprint_mutations` — same invariant for helper-variant.
- `test_vac_crew_hash_byte_identical_across_sub_fingerprint_mutations` — same invariant for vac_crew-variant.
- `test_aep_billable_hash_changes_on_sub_fingerprint_mutation` — positive companion: `aep_billable` hash MUST change under SUB_RATES_FP mutation (D-20 mix-in active).
- `test_existing_variants_total_hash_count_unchanged` — set-cardinality check across 10 synthetic groups in the 3 existing variants confirms no variant accidentally merged with another.

**`TestPhase1FilenameRoundTripCoverage`** (1 parametrized method, 7 subtests):

- `test_filename_round_trip_for_all_seven_variants` — for each of the 7 valid variant strings (`primary`, `helper`, `vac_crew`, `aep_billable`, `reduced_sub`, `aep_billable_helper`, `reduced_sub_helper`): constructs the expected filename, calls `build_group_identity`, asserts the returned variant matches.

Both classes pin `EXTENDED_CHANGE_DETECTION`, `RATE_CUTOFF_DATE`, `_RATES_FINGERPRINT`, AND `_SUBCONTRACTOR_RATES_FINGERPRINT` in setUp / tearDown so developer-env mutations cannot destabilize the suite.

**Acceptance gates met:**
- `grep -nE "^class TestPhase1IntegrationRegression" tests/test_subcontractor_pricing.py` → 1 match.
- `grep -nE "^class TestPhase1FilenameRoundTripCoverage" tests/test_subcontractor_pricing.py` → 1 match.
- `grep -nE "^class TestPhase1EndToEndByteIdenticalRegression" tests/test_subcontractor_pricing.py` → 0 matches (the prior misnamed class does NOT exist anywhere in the codebase — Warning 11 lock-in).

Full `pytest tests/` exits 0 with **537 passed / 22 skipped / 16 subtests passed** (the +6 net new tests: 5 in `TestPhase1IntegrationRegression`, 1 parametrized in `TestPhase1FilenameRoundTripCoverage`; the 7 subtests under the parametrized method bring the subtest total from 9 to 16).

### Task 3 — Human-verify checkpoint (operator-driven; Step A approved, Step B deferred)

**Operator resume signal:** `approved Step A; Step B deferred to scheduled production run`.

**Step A — TEST_MODE synthetic-data file-mix coverage (APPROVED):**
- Startup banner confirmed: `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=True`, `SUBCONTRACTOR_RATES_CSV=data/subcontractor_rates.csv`, `SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908`, 3691 CUs loaded, fingerprint `e4941a5e86c4f8ce`.
- Existing primary files generated cleanly with no regression.
- File-mix coverage of `_AEPBillable` and `_ReducedSub` synthetic outputs verified against the expected naming pattern.
- No CRITICAL / ERROR-level logs.

**Step B — SKIP_UPLOAD real-data price-write gate (DEFERRED):**
- Per Warning 10, Step B is the only mode that exercises the CSV-driven cell-write path end-to-end with real subcontractor data.
- Local operator env lacks `SMARTSHEET_API_TOKEN` — Step B cannot run locally.
- **Fallback verification surface:** the next scheduled GitHub Actions production run with `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=1` will exercise the price-write path end-to-end. The new variant code emits a per-sheet WARNING for any missing CU codes; operator can grep the run logs for `"Subcontractor rates CSV missing"` to confirm the surface is live.
- **Risk envelope:** Phase 1 ships with the kill switch ENABLED by default. If unexpected behaviour surfaces in the first scheduled production run, operators can set `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=0` in workflow env to instantly disable new-variant generation without a code revert. Unit-level coverage of the resolver behaviour is pinned by Plan 3's `TestSubcontractorVariantPriceSubstitution` + `TestResolveRowPriceCanonicalColumnNames`; the workbook-cell-writer integration is pinned by Plan 3's `TestGenerateExcelReturnTupleShape` + `TestSubcontractorVariantOpenpyxlCompliance`.

**Pre-existing master bug surfaced during Step A:**

While operator ran Step A, the `python generate_weekly_pdfs.py` invocation hit a confusing crash: an `UnboundLocalError` for `_txn` in `main()`'s `finally` block. This was **NOT** a Phase 1 regression. Forensic trace:

- `_txn` was initialized at L5312 inside `main()`'s session block (added 2026-03-24, commit `61291fb5`).
- The synthetic TEST_MODE `return` at L5304 and the `"SMARTSHEET_API_TOKEN not configured"` `raise` at L5306 both short-circuit BEFORE L5312.
- Either short-circuit propagates straight into the `finally` block at L6890, which references `_txn` → `UnboundLocalError`, masking the actual exit status.
- The synthetic path has been broken for every operator running TEST_MODE locally since 2026-03-24.

**Orchestrator fix (commit `7e4777c`):** Hoisted `_txn = None` to the top of `main()` in the same initialization block as `_cron_checkin_id = None`. Idempotent and minimal. `PYTHONIOENCODING=utf-8 TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py` now exits 0. Tests unchanged at 531 → 537 (after Task 2 also landed).

**This SUMMARY documents the `_txn` fix as a noteworthy deviation but does NOT re-touch the source code** — the fix is committed, verified, and outside Plan 06 Task 4's doc-only scope.

### Task 4 — Docusaurus runbook update (commits `4a321c0` + `871c341`, this executor pass)

**Commit `4a321c0` — `docs(reference): document subcontractor rate variant env vars`:**

Added a new "Subcontractor rate variants" section to `website/docs/reference/environment.md`, positioned after the existing "Smartsheet targets" section so the subcontractor-related env vars are grouped logically. Each of the three env vars gets its own H3 subsection with Default / Purpose / Valid values / Rollback:

- **`SUBCONTRACTOR_RATES_CSV`** — operator-managed rate matrix path (default `data/subcontractor_rates.csv`); explains the 17-column shape, the 3691-CU shipped count, currency / BOM / zero-row tolerance, `_sanitize_csv_path` resolution. Rollback section explains the fail-safe loader returning `{}` on error and routes operators to the kill switch for intentional retirement.

- **`SUBCONTRACTOR_PPP_SHEET_ID`** — secondary attachment target for `_ReducedSub` variants (default `8162920222379908`); explains the dual-routing behaviour (both `TARGET_SHEET_ID` and PPP), the same-sheet-as-TARGET guard preventing duplicate attachments, and the fail-safe degradation to single-sheet routing on unreachable PPP.

- **`SUBCONTRACTOR_RATE_VARIANTS_ENABLED`** — default-on kill switch (default `'1'`); explains the truthy-value set, the comprehensive scope of what gets disabled, the pattern parallel to `RATE_RECALC_SKIP_ORIGINAL_CONTRACT` / `RATE_RECALC_WEEKLY_FALLBACK`, and the env-var rollback path (no code revert required). Mentions the startup-banner state log so operators can grep the run header.

Component-owner annotation per `.claude/rules/documentation-maintenance.md` hybrid-ecosystem-clarity rule names "Python billing pipeline (`generate_weekly_pdfs.py`)" explicitly at the section head.

**Commit `871c341` — `docs(runbook): add subcontractor rate variants section`:**

Added a new "Subcontractor rate variants" subsection under the existing `weekly-excel-generation.yml` section in `website/docs/runbook/workflows.md`. The section is a synthesized narrative answering what changed / why / how it impacts operators (per `.claude/rules/documentation-maintenance.md` rule 1 — NOT a commit dump):

- **What changed** — describes the two new Excel variant types (`_AEPBillable`, `_ReducedSub`), their priced-column sources (`new_*_price` vs `reduced_*_price`), the snapshot-date cutoff for `_AEPBillable` (`>= 2026-04-12`), the routing matrix (`_AEPBillable` → `TARGET_SHEET_ID` only; `_ReducedSub` → both `TARGET_SHEET_ID` AND `SUBCONTRACTOR_PPP_SHEET_ID`), and the helper-shadow variants (`_AEPBillable_Helper_<name>` + `_ReducedSub_Helper_<name>`) that generate when the existing helper-foreman rule fires on a subcontractor WR.

- **Why** — AEP 3% rate increase effective 2026-04-12; AP / AR ledger reconciliation requirement; original-contract folder workflow unchanged (with cross-link to the existing `LEGACY` callout for the 2026-04-24 CSV-side rate recalc retirement).

- **How it impacts operators** — five numbered items:
  1. **One-time setup** — apply `billing_audit/schema.sql` to Supabase (idempotent `ADD COLUMN IF NOT EXISTS variant TEXT`); covers SUB-07.
  2. **Three new env vars** — cross-links into the three anchors in `environment.md`.
  3. **Missing-CU WARNING** — exact log text with the `Subcontractor rates CSV missing N CU code(s) on sheet <id>:` pattern; operator action to add the missing CUs.
  4. **CSV file location** — `data/subcontractor_rates.csv`, with the `git mv` history-preserving rename mentioned.
  5. **Variant attribution** — the seven variant strings on `billing_audit.pipeline_run.variant`; NULL-tolerance for pre-2026-05-14 rows; Path B contract (the `freeze_attribution` RPC is unchanged).

- **Rollback procedure** — kill-switch flip with explicit "no code revert required" callout.

**Component-owner annotation** explicitly names "Python billing pipeline (`generate_weekly_pdfs.py`)" AND calls out the negative ("NOT Notion sync, NOT the `portal-v2` Supabase tier") per the hybrid-ecosystem-clarity rule. Triage routing is unambiguous.

**Page-choice deviation (documented):** The original plan referenced `website/docs/operations/weekly-pipeline.md` — that file does NOT exist in this repo. The actual runbook lives at `website/docs/runbook/*.md` with `overview.md`, `workflows.md`, `python-modules.md`, `operations.md`, `portals.md`, `scripts.md`. `workflows.md` was chosen because the variant emission is a workflow-scoped behaviour — the on-call engineer reading `weekly-excel-generation.yml`'s behaviour section wants the variant emission, target-routing, and missing-CU surface co-located there. `operations.md` covers running the generator by hand and is at the wrong altitude. The decision is documented in commit `871c341`'s message and re-traced here.

**Cross-link audit:** Both pages bidirectionally cross-link. The runbook section points at three env-var anchors (`#subcontractor_rates_csv`, `#subcontractor_ppp_sheet_id`, `#subcontractor_rate_variants_enabled`) plus `#smartsheet-targets` and the existing `#rate-contract-versioning`. The reference page points back at the runbook section (`#subcontractor-rate-variants`). All anchors validated by `npm run build` — zero broken cross-links.

**Validation gate:** `cd website && npm run typecheck && npm run build` — both exit 0. The build success line `[SUCCESS] Generated static files in "build".` is the green light.

## Task Commits

This plan's commits span three executors:

**Earlier executor (Tasks 1 + 2):**

1. **Task 1 — `9cfb652` `test(01-06): pin window cap at 18kB + Warning 8 reconciliation`** — inline comment block at `tests/validate_production_safety.py` L138-167 pinning the 18 kB window cap with the post-Phase-1 measurement (17,738 chars), the decision rationale, and the Warning 8 reconciliation note.
2. **Task 2 — `f79fd5b` `test(01-06): add Phase 1 hash-stability + filename round-trip regression`** — `TestPhase1IntegrationRegression` (5 hash-stability tests) + `TestPhase1FilenameRoundTripCoverage` (1 parametrized test, 7 subtests) in `tests/test_subcontractor_pricing.py`, with both classes pinning `_SUBCONTRACTOR_RATES_FINGERPRINT` + the legacy env-vars in setUp / tearDown for isolation.

**Orchestrator-side bug fix (surfaced during Task 3 Step A):**

3. **`7e4777c` `fix(main): hoist _txn = None so finally block never sees it unbound`** — pre-existing master bug since 2026-03-24, surfaced during Phase 1 Task 3 Step A operator verification. Documented as a deviation in this SUMMARY but NOT re-touched in this plan's source-code scope.

**Merge from earlier executor's worktree:**

4. **`4a03f99` `chore(01-06): merge executor worktree (Tasks 1-2 only; Task 3 + 4 pending)`** — merge commit bringing Tasks 1 + 2 onto the canonical branch.

**This executor (Task 4):**

5. **Task 4a — `4a321c0` `docs(reference): document subcontractor rate variant env vars`** — `website/docs/reference/environment.md` gains the "Subcontractor rate variants" section with the three env vars documented.
6. **Task 4b — `871c341` `docs(runbook): add subcontractor rate variants section`** — `website/docs/runbook/workflows.md` gains the synthesized changelog subsection under the `weekly-excel-generation.yml` section.

**Plan metadata commit (after this SUMMARY):**

7. **Final — `docs(phase-01): mark plan 06 complete + close Phase 1`** (forthcoming) — STATE.md + ROADMAP.md + this SUMMARY.

## Files Created/Modified (this executor pass)

- `website/docs/reference/environment.md` — new "Subcontractor rate variants" section (80 lines added) documenting the three Phase 1 env vars.
- `website/docs/runbook/workflows.md` — new "Subcontractor rate variants" subsection (127 lines added) under the `weekly-excel-generation.yml` section synthesizing the what / why / how operator-impact narrative.
- `.planning/phases/01-subcontractor-rate-logic-modification/01-06-SUMMARY.md` — this file.
- `.planning/STATE.md` — Phase 1 completion state (forthcoming in the metadata commit).
- `.planning/ROADMAP.md` — Plan 06 checkbox flipped to `[x]`; Phase 1 status flipped to complete (forthcoming in the metadata commit).

## Decisions Made

- **Window cap held at 18 kB.** Measurement-driven decision — the actual block size at 17,738 chars sits 262 chars below the cap. Bumping to 21 kB would over-permit the validator without justification. CLAUDE.md 2026-04-25 14:00 rule 3 ("Whenever extending the per-group billing_audit block, also bump the validator window cap to match") does NOT mandate a bump when the block did not grow past the existing cap — and Phase 1's additions stayed under 18 kB.
- **Class split per Warning 11.** Hash-stability and filename round-trip are different invariants; separate classes for separate invariants. The taxonomy is documentation — the prior misnamed `TestPhase1EndToEndByteIdenticalRegression` would have confused a future maintainer reading the test file looking for either invariant.
- **Step B deferred to scheduled production run.** Operator decision; risk envelope is bounded by the kill-switch default-ON + Plan 3's unit-level + integration tests; the fallback verification surface is the next scheduled GitHub Actions run, where the missing-CU WARNING + run logs are the operator-visible diagnostic surface.
- **Page choice for Task 4 — `workflows.md`, not `operations.md`.** The variant emission is a workflow-scoped behaviour belonging next to the workflow that emits it. Operator running the generator by hand (`operations.md`) does not care about the variant routing matrix in the same way the on-call engineer reading the workflow does.
- **`_txn` fix is a deviation note, not a Plan 06 source change.** Plan 06 Task 4 is doc-only; the `_txn` fix is committed (`7e4777c`) and verified outside this plan's scope. The deviation is documented because (a) it surfaced during this plan's human-verify checkpoint and (b) a future archaeologist tracing the fix back will land on this SUMMARY.

## Deviations from Plan

### Auto-fixed Issues / Pre-existing Bug Surfaces

**1. [Rule 1 — Bug, orchestrator-side fix, commit `7e4777c`] Pre-existing master bug: `_txn = None` initialized after the synthetic-mode return / missing-token raise short-circuits in `main()`**

- **Found during:** Task 3 Step A — operator ran `TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py` and hit `UnboundLocalError: cannot access local variable '_txn' where it is not associated with a value` in `main()`'s `finally` block.
- **Issue (not a Phase 1 regression):** `_txn = None` was initialized at L5312 inside the session block AFTER both the synthetic TEST_MODE `return` at L5304 and the `"SMARTSHEET_API_TOKEN not configured"` `raise` at L5306. Either short-circuit propagates straight into the `finally` block at L6890, which references `_txn` and crashes, masking the actual exit status. Forensics show the init was added 2026-03-24 in commit `61291fb5`; the synthetic `return` was added 2025-09-24 in commit `61746eb9`. The synthetic path has been broken for every operator running TEST_MODE locally since 2026-03-24.
- **Fix:** Hoist `_txn = None` to the top of `main()` in the same initialization block as `_cron_checkin_id = None`. Idempotent and minimal.
- **Verification:** `PYTHONIOENCODING=utf-8 TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py` now exits 0. Tests unchanged at 531 (pre-fix) → 537 (after Task 2 also landed).
- **Committed in:** `7e4777c` (orchestrator-side, outside Plan 06 Task 4 doc-only scope; documented here for traceability).

**2. [Page-choice deviation, documented in commit message + here] Task 4 plan path drift: `website/docs/operations/weekly-pipeline.md` does not exist**

- **Found during:** Task 4 — Read tool against the plan-referenced path returned "file does not exist".
- **Issue:** The plan referenced `website/docs/operations/weekly-pipeline.md` as the runbook target page. The actual runbook lives at `website/docs/runbook/*.md` with `overview.md`, `workflows.md`, `python-modules.md`, `operations.md`, `portals.md`, `scripts.md`. There is no `operations/` directory and no `weekly-pipeline.md` file.
- **Fix:** Located the closest equivalent and chose `website/docs/runbook/workflows.md` because the variant emission is a workflow-scoped behaviour — the on-call engineer reading `weekly-excel-generation.yml`'s behaviour section wants the variant emission, target-routing, and missing-CU surface co-located there. `operations.md` covers running the generator by hand and is at the wrong altitude. The decision is documented in commit `871c341`'s message and in this SUMMARY's "Decisions Made" / "Task 4" sections.
- **Verification:** `cd website && npm run typecheck && npm run build` both exit 0; bidirectional cross-links between `workflows.md` and `environment.md` resolve cleanly.
- **Committed in:** `871c341`.

### No Other Deviations

The other 3 Phase 1 plans (01-01, 01-02, 01-03, 01-04, 01-05) executed exactly as written for their plan-level acceptance criteria. The Task 1 + Task 2 commits (`9cfb652` + `f79fd5b`) did not encounter deviations of their own — see those individual commit messages for full detail.

## Issues Encountered

- **`website/node_modules` was missing at the start of this executor pass.** Required running `npm install` first (32 sec, 1281 packages). One Node engine warning (`required: 20.x`, `current: v24.14.0`) — pre-existing engine mismatch, not introduced by Task 4; the build succeeded regardless because Docusaurus 3.x tolerates Node 24.
- **Pre-existing untracked deletions in working tree.** `git status` at the start of this executor pass showed three tracked files marked deleted: `generated_docs/README.md`, `generated_docs/artifact_manifest.json`, `generated_docs/hash_history.json`. These were leftover from a prior Task 3 Step A verification run where the operator ran `Remove-Item -Recurse -Force generated_docs`. They are out-of-scope for Task 4 (doc-only); restored via `git restore` before any edits so the working tree was clean. Per the `destructive_git_prohibition` rule, no `git clean` was used.
- **MD025 / MD040 markdownlint warnings.** After Task 4's edits, IDE diagnostics flagged MD025 (multiple top-level headings in `workflows.md` — pre-existing structure at L7, NOT introduced by Task 4) and MD040 (fenced code block without language). The MD040 was fixed by adding `text` as the language hint on the WARNING-sample fenced block. The MD025 is pre-existing structural drift outside Task 4's doc-only scope; refactoring the H1 / H2 hierarchy would be a separate operation.

## User Setup Required

- **One-time Supabase schema apply (operator action).** Before the first scheduled production run after Phase 1 merges, the operator must apply `billing_audit/schema.sql` to the deployed Supabase project so `billing_audit.pipeline_run` accepts the new `variant` column. Open Supabase Dashboard → SQL Editor → run the file's contents. The statement is `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT;` (idempotent, safe to re-run). Documented in the new runbook section under "How it impacts operators → One-time setup".
- **Optional follow-up: Step B verification on next scheduled run.** Operator should review the next scheduled GitHub Actions production run's logs for the missing-CU WARNING surface (`grep "Subcontractor rates CSV missing"`) and the variant attribution in `billing_audit.pipeline_run`. If unexpected behaviour surfaces, set `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=0` in the workflow env block to instantly roll back.

## Known Stubs

None — every artifact this plan delivered is wired up:
- Window cap is pinned (Task 1).
- Both regression classes are written and the 6 tests pass (Task 2).
- Step A is approved; Step B is documented as deferred with the explicit fallback verification surface (Task 3).
- Both Docusaurus pages are updated with bidirectional cross-links resolved by the build (Task 4).

The Step B deferral is not a stub — it is a documented operator decision with a fallback verification surface (the next scheduled production run) and a bounded risk envelope (kill switch default-ON).

## Threat Surface Notes

No new threat surface beyond what the plan's `<threat_model>` enumerated. The 6 STRIDE entries (T-06-01 through T-06-06) are all mitigated:

- **T-06-01 (Tampering, validator bypass):** Task 1's right-sized 18 kB cap + inline measurement comment + Warning 8 reconciliation.
- **T-06-02 (Repudiation, regression undetected):** Task 2's `TestPhase1IntegrationRegression` class pins the byte-identical guarantee directly; D-20 mix-in scoping locked by 3 negative tests covering primary / helper / vac_crew.
- **T-06-03 (Information Disclosure, runbook leaks tech details):** ACCEPTED per plan — the runbook describes rate logic, file names, and env vars (non-secret). Actual rate values stay in the gitignored XLSX and the committed CSV.
- **T-06-04 (DoS, TEST_MODE wrong files):** Task 3 Step A approved.
- **T-06-05 (Repudiation, operator misses missing-CU WARNING):** Task 4's runbook entry has the missing-CU WARNING as numbered operator-action item 3, with the exact log text and the operator action (`Add to data/subcontractor_rates.csv`).
- **T-06-06 (Tampering, price-write regression hidden by synthetic TEST_MODE):** Step B deferred to the next scheduled production run with the kill-switch default-ON as the bounded risk envelope. Unit + integration tests in Plan 3 pin the helper-level and workbook-cell-writer surfaces.

## Final Variant Routing Matrix (Phase 1 deliverable summary)

The seven valid variant strings recorded on `__variant` row metadata + `billing_audit.pipeline_run.variant`:

| Variant string | Excel filename suffix | Source sheet scope | Target sheet routing |
| --- | --- | --- | --- |
| `primary` | `WR_*_<hash>.xlsx` (no suffix) | All sheets | `TARGET_SHEET_ID` only |
| `helper` | `_Helper_<name>` | All sheets | `TARGET_SHEET_ID` only |
| `vac_crew` | `_VacCrew` | All sheets | `TARGET_SHEET_ID` only |
| `aep_billable` | `_AEPBillable` | Subcontractor folders only, `Snapshot Date >= 2026-04-12` | `TARGET_SHEET_ID` only |
| `reduced_sub` | `_ReducedSub` | Subcontractor folders only | **BOTH** `TARGET_SHEET_ID` AND `SUBCONTRACTOR_PPP_SHEET_ID` |
| `aep_billable_helper` | `_AEPBillable_Helper_<name>` | Subcontractor folders only, `Snapshot Date >= 2026-04-12`, on helper-foreman events | `TARGET_SHEET_ID` only |
| `reduced_sub_helper` | `_ReducedSub_Helper_<name>` | Subcontractor folders only, on helper-foreman events | **BOTH** `TARGET_SHEET_ID` AND `SUBCONTRACTOR_PPP_SHEET_ID` |

## Final Readiness Statement

**Phase 1 is ready to ship via PR.** Every Plan 1-6 deliverable is in place; the kill switch ships ENABLED by default with the env-var flip to `'0'` as the documented rollback path; all 7 SUB-* requirements are met across Plans 1-5; the regression locks + production-safety validator + Docusaurus runbook are pinned in Plan 06.

The CLAUDE.md Living Ledger entry will be appended autonomously when the merging PR opens per the autonomous-cloud-memory-injection rule (separate execution surface; not this plan's responsibility).

## Self-Check

Performed inline before finalizing:

- `tests/validate_production_safety.py` contains the post-Phase-1 inline comment with "Phase 1", "18000", "262", and "Warning 8" / "Plan 05" references: **CONFIRMED** (commit `9cfb652`).
- `tests/test_subcontractor_pricing.py` contains `class TestPhase1IntegrationRegression` (5 methods) and `class TestPhase1FilenameRoundTripCoverage` (1 parametrized method): **CONFIRMED** (commit `f79fd5b`).
- `class TestPhase1EndToEndByteIdenticalRegression` does NOT exist anywhere in the codebase (Warning 11 lock-in): **CONFIRMED**.
- `generate_weekly_pdfs.py` has `_txn = None` hoisted to the top of `main()` (commit `7e4777c`): **CONFIRMED**.
- `website/docs/reference/environment.md` contains the "Subcontractor rate variants" section with H3 subsections for the three env vars: **CONFIRMED** (commit `4a321c0`).
- `website/docs/runbook/workflows.md` contains the "Subcontractor rate variants" subsection with the five numbered operator-impact items: **CONFIRMED** (commit `871c341`).
- Component-owner annotation ("Python billing pipeline (`generate_weekly_pdfs.py`)") appears in BOTH new doc sections: **CONFIRMED**.
- `cd website && npm run typecheck` exits 0: **CONFIRMED** (final run after both doc edits).
- `cd website && npm run build` exits 0 with no broken cross-links: **CONFIRMED** (final run after both doc edits; `[SUCCESS] Generated static files in "build".`).
- `pytest tests/ -q --tb=line` exits 0 with 537 passed / 22 skipped / 16 subtests: **CONFIRMED**.
- Commit `4a321c0` exists in `git log`: **CONFIRMED**.
- Commit `871c341` exists in `git log`: **CONFIRMED**.
- Commits `9cfb652`, `f79fd5b`, `7e4777c` (referenced in this SUMMARY) all exist in `git log`: **CONFIRMED**.

## Self-Check: PASSED

---

*Phase: 01-subcontractor-rate-logic-modification*
*Plan: 06*
*Completed: 2026-05-14*
