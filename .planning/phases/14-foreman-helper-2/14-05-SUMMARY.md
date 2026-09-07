---
phase: 14-foreman-helper-2
plan: 05
subsystem: billing-pipeline
tags: [python, typescript, smartsheet, foreman-helper, change-detection, portal, tdd]

# Dependency graph
requires:
  - phase: 14-01
    provides: "the '_Helper2_' filename token, HELPER2= hash meta, HELPER2_ENABLED flag, and helper2 / aep_billable_helper2 / reduced_sub_helper2 variant tokens"
provides:
  - "pipeline/cleanup.py: _HELPER_VARIANTS_FOR_ORPHAN_GATE recognizes the Helper #2 family (helper2, aep_billable_helper2, reduced_sub_helper2), so a primary attachment superseded only by a live Helper #2 claim is queued for deletion as a variant-migration orphan"
  - "scripts/publish_artifacts_to_supabase.py: _CANONICAL_VARIANTS (10 members) and normalize_variant's precedence chain parse all three Helper #2 filename shapes, with the two hybrid forms outranking their bare component forms"
  - "portal-v2/src/lib/variantLabels.ts: readable labels for helper2 / aep_billable_helper2 / reduced_sub_helper2"
  - "tests/test_helper2_family_parity.py: pinned-file parity table extended with pipeline/cleanup.py and scripts/publish_artifacts_to_supabase.py, generalized to check both quote styles"
affects: [14-06]

# Actuals (#2632)
actuals:
  tokens: 6764
  tasks: 3
  commits: 6
  plan_head_before: 595fe70

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Quote-style-agnostic literal-parity matching: tests/test_helper2_family_parity.py's _quoted_forms()/_literal_present() check both single- and double-quote forms of a bare literal, because scripts/publish_artifacts_to_supabase.py quotes these tokens with double quotes exclusively while every other pinned file uses single quotes exclusively for the same literal"
    - "Portal label keys follow the producer's actual output convention (the snake_case token normalize_variant() writes), not the pre-existing inconsistent convention already in the file (D-14-13 / A5-adjacent)"

key-files:
  created: []
  modified:
    - pipeline/cleanup.py
    - scripts/publish_artifacts_to_supabase.py
    - portal-v2/src/lib/variantLabels.ts
    - tests/test_sentinel_superseded_cleanup.py
    - tests/test_publish_artifacts_to_supabase.py
    - tests/test_helper2_family_parity.py

key-decisions:
  - "Generalized tests/test_helper2_family_parity.py's SIBLING_PAIRS from single-quote-only literal strings to bare words matched via a new _literal_present() helper that checks BOTH single- and double-quote forms -- scripts/publish_artifacts_to_supabase.py (this plan's second file) quotes these tokens with double quotes exclusively, unlike every pre-existing pinned file, and widening the match discriminator (rather than adding a second, disconnected parity test class) keeps 'the pinned file table' a single mechanism as the plan's action text asked for, verified by grep to introduce no false-positive risk for the 3 existing single-quote-only files."
  - "Did not run `npm install` in portal-v2 when node_modules was found missing -- per explicit project guardrail ('if node_modules are missing, say so rather than installing'). `npm --prefix portal-v2 run build` could not execute (tsc not found); the 3-line label-map addition was verified by manual review only (valid TS object-literal syntax, same shape as the four pre-existing entries)."
  - "Did not repair the pre-existing key-convention inconsistency in portal-v2/src/lib/variantLabels.ts (bare snake_case 'helper'/'vac_crew' vs underscore-capitalized '_AEPBillable'/'_ReducedSub') -- 14-RESEARCH.md Assumption A5 is unresolved and fixing it here would change the rendering of already-published artifacts; the three new keys are keyed on the snake_case form the publisher actually writes, with a one-line comment citing A5."

patterns-established:
  - "A parity/invariant test that must span files with different literal-quoting conventions checks all quote styles at the match layer, rather than either failing to enforce for the odd-convention file or forking a parallel, disconnected test class per convention."

requirements-completed: [HLP-01, HLP-02, HLP-06]

coverage:
  - id: D1
    description: "A primary attachment superseded only by a live Helper #2 claim (plain, AEP-billable shadow, or reduced-sub shadow) for the same WR and week is recognized as a variant-migration orphan, exactly as it is when superseded by a Helper #1 claim"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#VariantMigrationOrphanHelper2Tests::test_primary_superseded_by_helper2_is_queued_for_deletion"
        status: pass
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#VariantMigrationOrphanHelper2Tests::test_primary_superseded_by_aep_billable_helper2_is_queued_for_deletion"
        status: pass
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#VariantMigrationOrphanHelper2Tests::test_primary_superseded_by_reduced_sub_helper2_is_queued_for_deletion"
        status: pass
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#VariantMigrationOrphanHelper2Tests::test_primary_with_no_helper_sibling_of_any_kind_is_untouched"
        status: pass
    human_judgment: false
  - id: D2
    description: "A Helper #2 attachment is never matched by any one-time legacy-migration or unpartitioned rule, and is never swept when produced this run; a placeholder-named Helper #2 file not produced this run IS swept by the pre-existing variant-agnostic sentinel gate"
    requirement: "HLP-01"
    verification:
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#VariantMigrationOrphanHelper2Tests::test_helper2_attachment_never_matched_by_legacy_sub_offcontract_gate"
        status: pass
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#VariantMigrationOrphanHelper2Tests::test_helper2_attachment_produced_this_run_is_never_swept"
        status: pass
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#VariantMigrationOrphanHelper2Tests::test_placeholder_helper2_swept_by_existing_sentinel_gate"
        status: pass
      - kind: other
        ref: "git diff 595fe70..HEAD -- pipeline/cleanup.py (manual review: only the _HELPER_VARIANTS_FOR_ORPHAN_GATE frozenset literal changed; the legacy migration gates and their matching logic are byte-identical)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Rollback safety (D-14-12): a cleanup pass never queues an existing Helper #2 attachment for deletion because HELPER2_ENABLED is off, for either flag value"
    requirement: "HLP-02"
    verification:
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#Helper2RollbackProtectionTests::test_helper2_attachment_survives_cleanup_with_flag_off"
        status: pass
      - kind: unit
        ref: "tests/test_sentinel_superseded_cleanup.py#Helper2RollbackProtectionTests::test_helper2_attachment_survives_cleanup_with_flag_on"
        status: pass
    human_judgment: false
  - id: D4
    description: "normalize_variant maps _AEPBillable_Helper2_ and _ReducedSub_Helper2_ to their own tokens BEFORE the bare AEP-billable/reduced-sub checks, _Helper2_ never cross-matches _Helper_, and every produced variant is a canonical-set member"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_publish_artifacts_to_supabase.py#TestNormalizeVariantHelper2::test_aep_billable_helper2_precedence"
        status: pass
      - kind: unit
        ref: "tests/test_publish_artifacts_to_supabase.py#TestNormalizeVariantHelper2::test_reduced_sub_helper2_precedence"
        status: pass
      - kind: unit
        ref: "tests/test_publish_artifacts_to_supabase.py#TestNormalizeVariantHelper2::test_helper2_never_falls_through_to_helper_or_primary"
        status: pass
      - kind: unit
        ref: "tests/test_publish_artifacts_to_supabase.py#TestNormalizeVariantHelper2::test_helper1_still_normalizes_when_name_starts_with_digit"
        status: pass
      - kind: unit
        ref: "tests/test_publish_artifacts_to_supabase.py#TestNormalizeVariantHelper2::test_all_ten_canonical_values_reachable_and_are_members"
        status: pass
    human_judgment: false
  - id: D5
    description: "The extended family-parity invariant now covers the two silent-gap sites this phase's research discovered outside the original audit scope (pipeline/cleanup.py, scripts/publish_artifacts_to_supabase.py)"
    requirement: "HLP-06"
    verification:
      - kind: unit
        ref: "tests/test_helper2_family_parity.py#HelperFamilyParityTests (PARITY_TABLE now includes pipeline/cleanup.py and scripts/publish_artifacts_to_supabase.py)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The portal renders a readable label for each Helper #2 variant instead of a raw token"
    human_judgment: true
    rationale: "portal-v2/node_modules is not installed in this environment (tsc/vite unavailable); npm install was deliberately not run per project guardrail. The 3-entry VARIANT_LABELS addition was verified by manual code review (valid TS object-literal syntax, identical shape to the 4 pre-existing entries) but not by a running build, typecheck, or rendered-UI check -- a human or a CI run with node_modules present should confirm the portal renders 'Helper 2' / 'AEP Billable · Helper 2' / 'Reduced Sub · Helper 2' instead of a raw token."
---

# Phase 14 Plan 05: Helper #2 Cleanup/Publisher/Portal Lifecycle Summary

**A primary attachment superseded only by a live Helper #2 claim is now recognized as a variant-migration orphan, the publisher's 10-token precedence chain parses every Helper #2 filename shape with the hybrid forms outranking their bare components, the portal has readable Helper #2 labels, and the family-parity invariant now guards the two silent-gap sites this phase's research found outside the original audit scope.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-09-06
- **Tasks:** 3/3 completed
- **Files modified:** 6 (0 created)

## Accomplishments

- `pipeline/cleanup.py`'s `_HELPER_VARIANTS_FOR_ORPHAN_GATE` frozenset now includes `helper2` / `aep_billable_helper2` / `reduced_sub_helper2` alongside the existing Helper #1 family (6 members total) -- a primary attachment superseded only by a Helper #2 claim is queued for deletion exactly as it already is for a Helper #1 claim. Confirmed via `git diff` that the one-time legacy-migration gates and the sentinel-superseded gate are byte-identical; only the frozenset literal changed.
- `scripts/publish_artifacts_to_supabase.py`'s `_CANONICAL_VARIANTS` grew from 7 to 10 members, and `normalize_variant`'s precedence chain gained 3 new branches inserted in the correct order (the two Helper #2 hybrid checks before their bare AEP-billable/reduced-sub counterparts, the plain Helper #2 check before the plain Helper #1 check) -- verified by line-number inspection, not just presence.
- `portal-v2/src/lib/variantLabels.ts` gained readable labels for all three Helper #2 tokens, keyed on the exact snake_case string the publisher writes, with a comment citing the unresolved Assumption A5 key-convention question rather than silently "fixing" it.
- `tests/test_helper2_family_parity.py`'s pinned-file enforcement now covers both sites this phase's research flagged as missed by the original audit scope -- required generalizing the match helper to recognize both single- and double-quote literal forms, since the publisher script's quoting convention differs from every other pinned file.

## Task Commits

Each task was committed atomically (TDD tasks produced a RED test commit and a GREEN implementation commit):

1. **Task 1: The cleanup orphan-supersede gate learns the Helper #2 family** -- `9fd7ee4` (test, RED) + `4b7940b` (feat, GREEN)
2. **Task 2: The artifact publisher parses the three Helper #2 filename tokens in precedence order** -- `3224982` (test, RED) + `a706b11` (feat, GREEN)
3. **Task 3: Portal labels and the extended family-parity invariant** -- `40365e2` (feat)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified

- `pipeline/cleanup.py` -- `_HELPER_VARIANTS_FOR_ORPHAN_GATE` extended to 6 members (3 Helper #1, 3 Helper #2); no other line in the function changed
- `scripts/publish_artifacts_to_supabase.py` -- `_CANONICAL_VARIANTS` extended to 10 members; `normalize_variant` gained 3 precedence-ordered branches and an updated docstring
- `portal-v2/src/lib/variantLabels.ts` -- 3 new `VARIANT_LABELS` entries + a comment citing Assumption A5
- `tests/test_sentinel_superseded_cleanup.py` -- `VariantMigrationOrphanHelper2Tests` (6 tests) + `Helper2RollbackProtectionTests` (2 tests)
- `tests/test_publish_artifacts_to_supabase.py` -- `TestNormalizeVariantHelper2` (7 tests)
- `tests/test_helper2_family_parity.py` -- `PARITY_TABLE` extended with 2 files; `SIBLING_PAIRS`/`KNOWN_DEFERRED` generalized to bare literals matched via a new quote-style-agnostic `_literal_present()` helper

## Decisions Made

See `key-decisions` in frontmatter: (1) generalized the family-parity test's literal matcher to check both quote styles rather than forking a disconnected second test class for the publisher's double-quote convention; (2) declined to run `npm install` when `portal-v2/node_modules` was found missing, per explicit project guardrail, and verified the label-map change by manual review instead; (3) declined to repair the pre-existing key-convention inconsistency in `variantLabels.ts` (Assumption A5 stays unresolved and out of scope).

## Deviations from Plan

None - plan executed exactly as written. The quote-style generalization in `tests/test_helper2_family_parity.py` was anticipated by the plan's own `<read_first>` instruction (`.planning/phases/14-foreman-helper-2/14-PATTERNS.md` section for the publisher script) and is a test-only implementation detail of the plan's own Task 3 instruction to extend "the pinned file table" -- not a change to any must-have behavior, production file, or acceptance criterion.

## Issues Encountered

- `npm --prefix portal-v2 run build` (Task 3's second `<verify>` command) could not run: `portal-v2/node_modules` is not installed in this environment (`tsc` is not found on PATH once invoked via npm's script runner). Per project guardrails ("if node_modules are missing, say so rather than installing"), `npm install` was NOT run. This `<verify>` command is UNRUN, not failed -- the change itself (a 3-entry addition to an existing `Record<string, string>` object literal, same shape as 4 pre-existing entries) was verified by manual code review only. Recorded as `human_judgment: true` (D6) in the coverage block above so `/gsd:verify-work` routes it to a human/CI check with `node_modules` present. Attempting to also log this to `.planning/WINDOWS.md` via `gsd_run windows append --kind unrun-verify` was blocked by an unrelated harness-boundary guard hook (a false-positive "review/convergence command" classification on the `windows append` subcommand); since WINDOWS.md population is documented as best-effort and non-blocking, this was not pursued further and is instead recorded here and in the coverage block.
- All other automated `<verify>` commands ran and passed: `python -m pytest tests/test_sentinel_superseded_cleanup.py tests/test_publish_artifacts_to_supabase.py tests/test_helper2_family_parity.py -q` (72 passed, 90 subtests), `python -m py_compile pipeline/cleanup.py scripts/publish_artifacts_to_supabase.py generate_weekly_pdfs.py` (clean), `python -m pytest tests/ -q` (2172 passed, 1 skipped -- baseline was 2156 passed / 1 skipped before this plan).

## User Setup Required

None - no external service configuration required. No Supabase schema change, no Smartsheet column change, no GitHub Actions change.

## Next Phase Readiness

- `pipeline/cleanup.py` and `scripts/publish_artifacts_to_supabase.py` now fully recognize the plain `helper2` variant plus the two subcontractor shadow tokens (`aep_billable_helper2` / `reduced_sub_helper2`) for lifecycle and publishing purposes, even though `pipeline/excel.py` does not yet emit the two shadow filename shapes (that is plan 14-06's work per `tests/test_helper2_family_parity.py`'s `KNOWN_DEFERRED` entries, unchanged by this plan).
- The family-parity invariant's quote-style-agnostic matcher (`_literal_present()`) is now available as the enforcement mechanism for plan 14-06 to clear its two `KNOWN_DEFERRED` entries in `pipeline/excel.py` when it lands.
- No blockers. `HELPER2_ENABLED` stays off in every environment; nothing in this plan changes that flag's value or reads it in production code paths (only in a rollback-safety test).

## Self-Check: PASSED
