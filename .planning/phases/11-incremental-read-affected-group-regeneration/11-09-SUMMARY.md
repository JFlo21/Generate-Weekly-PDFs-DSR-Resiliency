---
phase: 11-incremental-read-affected-group-regeneration
plan: 09
subsystem: pipeline
tags: [incremental-read, affected-group-regeneration, supabase, parity, tdd, gap-closure]

# Dependency graph
requires:
  - phase: 11-incremental-read-affected-group-regeneration
    provides: "Plan 04's D-04 Option C selector (_resolve_row_wr_week / _filter_groups_to_affected / row_state-membership-only), Plan 05's shadow-parity harness (_shadow_parity_input_sets / compare_shadow_parity), and 11-VERIFICATION.md Gap 2's documented divergence evidence (production_frequent runs 34648318434.1, 34541106039.1)"
provides:
  - "pipeline/orchestrate.py::_resolve_row_wr_week -- fixed to derive its WR component via pipeline_memory.writer._sanitized_wr (the SAME function that produces row_state.wr), closing the confirmed WR-form + falsy-WR divergence"
  - "tests/test_parity_shadow.py::UserVariantCandidateParityTests -- fixture-backed end-to-end reproduction of the live USER-variant candidate-set miss, RED before the fix, GREEN after"
  - "tests/test_incremental_read.py::AffectedPairKeyContractTests -- bidirectional contract pinning _resolve_row_wr_week to pipeline_memory.writer._sanitized_wr/_coerce_date across 8 WR shapes + 4 week shapes, plus the subset-only / no-admit-everything / regression-guard properties"
  - "Three tracking records discharging 11-VERIFICATION.md Gap 2's 'not filed as a tracked todo' finding: .planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md, this phase's deferred-items.md '## 11-09' section, and a dated memory-bank/living-ledger.md entry"
affects: ["11-10 (owns the fresh >=5-run production_frequent streak this fix requires before the INC-04 gate is considered held again, and the D-05/Option-B override decision for Gap 1)"]

# Actuals (#2632)
actuals:
  tokens: 8450
  tasks: 3
  commits: 4
  plan_head_before: bc57e52276e0a6344d5522cc8c8b76ac907ffe54

tech-stack:
  added: []
  patterns:
    - "One shared derivation instead of two parallel re-implementations: when two subsystems must independently compare the SAME identity key, one side calls the other's canonical function rather than re-deriving it -- the durable rule this plan's fix and ledger entry establish."
    - "Fixture cassette + real-engine invocation (group_source_rows) for a parity reproduction test, mirroring tests/fixtures/incremental/deleted_row.json's convention: a synthetic JSON cassette, no live Smartsheet/Supabase call, one mocked Supabase-backed boundary (billing_audit.writer.resolve_claimer) exactly where the codebase's own precedent (tests/test_primary_claim_attribution.py) already mocks it."
  discovered_apis: []

key-files:
  created:
    - tests/fixtures/incremental/user_variant_candidate_miss.json
    - .planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md
  modified:
    - pipeline/orchestrate.py
    - tests/test_parity_shadow.py
    - tests/test_incremental_read.py
    - tests/test_own04_documentation.py
    - .planning/phases/11-incremental-read-affected-group-regeneration/deferred-items.md
    - memory-bank/living-ledger.md

key-decisions:
  - "Confirmed cause (a) WR-form mismatch + (b) falsy-WR mismatch, both in pipeline/orchestrate.py:1607 (_resolve_row_wr_week): the group side derived WR as str(wr).split('.')[0] with no _WR_SANITIZE substitution and no 50-character truncation, and treated ANY falsy raw value as empty, while pipeline_memory.writer._sanitized_wr (pipeline_memory/writer.py:704) applies both sanitize-then-truncate and only special-cases a MISSING value -- the two derivations resolved a raw WR containing a sanitizer-affected character (the live class: an embedded space) to two different strings, so the affected-pair comparison never matched and a genuine USER-variant group was silently dropped from the D-04 incremental candidate set."
  - "Fix delegates _resolve_row_wr_week's WR component to pipeline_memory.writer._sanitized_wr directly, rather than re-implementing its contract a second time -- pipeline/orchestrate.py already imports pipeline_memory.writer and already calls its date coercer on the next line, so this adds no new dependency and does not cross the package-boundary contract (which forbids pipeline_memory importing pipeline.*, not the reverse)."
  - "WR-normalization is not injective (two distinct raw values can sanitize to one key); this can only WIDEN the incremental candidate, never narrow it (T-11-18's safe direction), and the unmodified hash-skip gate then skips the unchanged ones exactly as the full run does -- recorded as an accepted residual, not remediated."
  - "[Rule 1 - Bug, scope-boundary exception] Task 3's required living-ledger.md append (a new '## [2026-09-14 ...]' dated heading, per this plan's own acceptance criteria) became the file's newest '## [' heading and broke tests/test_own04_documentation.py::test_records_phase_12_gap_closure_decisions, whose _newest_ledger_entry() helper located Phase 12's gap-closure entry by literal file position rather than by content. This is a regression directly caused by this plan's own required change (the plan's <verification> item 1 requires the full suite to stay green), not a pre-existing unrelated defect, so it was auto-fixed: _newest_ledger_entry() now locates the SAME Phase 12 entry by its durable D-12-C content marker, pinned regardless of what gets appended after it. tests/test_own04_documentation.py is NOT in this plan's files_modified frontmatter list; this is a documented, in-scope-by-necessity deviation."
  - "Cause (c) (an outside-the-selector cause, e.g. a new group with no prior group_state row, or a hash input outside HASH_FIELDS) was NOT the confirmed cause: the WR-form divergence in (a)/(b) reproduces the exact live symptom (actual_not_in_candidate for a USER-variant group) end-to-end with a real grouping-engine invocation, and the fix alone (no comparator change, no widening of the candidate predicate) turns the reproduction green -- no evidence pointed at cause (c) for this defect."

requirements-completed: []

coverage:
  - id: D1
    description: "Fixture-backed end-to-end reproduction that a USER-variant primary group of an affected (WR, week_ending) pair reaches the D-04 incremental candidate set, exercising the real group_source_rows -> _filter_groups_to_affected -> _shadow_parity_input_sets -> compare_shadow_parity path with no hand-written group keys. RED before the Task 2 fix (verdict=fail, reason=actual_not_in_candidate, matching the live evidence class), GREEN after."
    requirement: "INC-02"
    verification:
      - kind: unit
        ref: "tests/test_parity_shadow.py::UserVariantCandidateParityTests (5 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "_resolve_row_wr_week's WR component is fixed to be byte-identical to what pipeline_memory.writer._sanitized_wr produces for the same row (the value that actually reaches row_state.wr), pinned by a bidirectional contract test across 8 WR shapes and 4 week shapes, plus the subset-only / no-admit-everything / regression-guard properties that prove the fix widened nothing into an admit-everything path."
    requirement: "INC-04"
    verification:
      - kind: unit
        ref: "tests/test_incremental_read.py::AffectedPairKeyContractTests (5 tests, 15 subtests)"
        status: pass
      - kind: other
        ref: "git diff --numstat -- pipeline/orchestrate.py -> 37 added / 15 removed lines, confined to _resolve_row_wr_week (body + docstring); pipeline/grouping.py, pricing.py, attribution.py, excel.py, config.py, pipeline_memory/schema.sql, requirements.txt, .github/workflows/ all byte-for-byte unchanged (git diff --exit-code clean)"
        status: pass
      - kind: other
        ref: "python -m pytest tests/ -q -> 2426 passed / 1 skipped / 610 subtests (2026-09-12 baseline: 2416 / 1 / 595 -- +10 tests, +15 subtests, zero regressions); bash scripts/run_6_gates.sh -> ALL 6 GATES PASSED; python -m py_compile generate_weekly_pdfs.py -> exit 0"
        status: pass
    human_judgment: false
  - id: D3
    description: "The live divergence is tracked in three places so it is no longer an untracked UAT observation: a dated todo in .planning/todos/pending/, a phase deferred-items.md section, and a dated memory-bank/living-ledger.md entry recording the durable one-shared-derivation rule."
    requirement: "INC-02"
    verification:
      - kind: other
        ref: ".planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md (contains both run ids 34648318434 and 34541106039); deferred-items.md '## 11-09 (Gap 2 ...)' section; memory-bank/living-ledger.md '## [2026-09-14 18:00] ...' entry (append-only, previous final heading '## [2026-09-11 23:40] ...' still present)"
        status: pass
    human_judgment: false

duration: ~55min
completed: 2026-09-14
status: complete
---

# Phase 11 Plan 09: USER-Variant Candidate-Set Divergence (Gap 2) Summary

**Fixed a confirmed WR-sanitization mismatch in `pipeline/orchestrate.py::_resolve_row_wr_week` that silently dropped genuine USER-variant primary groups from the D-04 incremental candidate set — pinned by a fixture-backed reproduction and a bidirectional contract test, with the live defect tracked in three places.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-09-14 (session start)
- **Completed:** 2026-09-14
- **Tasks:** 3
- **Files modified:** 8 (2 created, 6 modified; see key-files)

## Accomplishments

- Reproduced 11-VERIFICATION.md Gap 2 end-to-end with a synthetic, non-real-data cassette
  (`tests/fixtures/incremental/user_variant_candidate_miss.json`) and
  `UserVariantCandidateParityTests`, which fails before the fix with the exact live symptom
  (`verdict: fail`, `reason: actual_not_in_candidate` for a `_USER_`-suffixed primary group) and
  passes after it.
- Confirmed the root cause against the code (not assumed): `_resolve_row_wr_week` derived WR as
  `str(wr).split('.')[0]` with no `_WR_SANITIZE` substitution and no 50-character truncation,
  while `pipeline_memory.writer._sanitized_wr` — the function that actually produces
  `row_state.wr`, the value the affected set is built from — applies both. A raw WR containing a
  sanitizer-affected character (the live class: an embedded space) therefore resolved to two
  different strings on the two sides.
- Fixed at one place with one shared derivation: `_resolve_row_wr_week` now calls
  `pipeline_memory.writer._sanitized_wr` directly instead of re-implementing its contract.
  `pipeline/grouping.py`, `pricing.py`, `attribution.py`, `excel.py`, `config.py`,
  `pipeline_memory/schema.sql`, `requirements.txt`, and `.github/workflows/` are all
  byte-for-byte unchanged; `RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF (D-11).
- Pinned the fix with a bidirectional contract test (`AffectedPairKeyContractTests`) across 8 WR
  shapes and 4 week shapes, plus the subset-only, no-admit-everything, and regression-guard
  properties, so a future edit to either derivation fails a test instead of silently drifting.
- Filed the previously-untracked live defect in three places: a dated todo, a phase
  `deferred-items.md` section, and a dated `memory-bank/living-ledger.md` entry recording the
  durable "call the other side's derivation" rule.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end reproduction (RED)** — `1feedeb` (test)
2. **Task 2: Confirm divergence + surgical fix (GREEN)** — `04c618a` (feat)
3. **Task 3: File the defect + record the durable rule** — `1ba2293` (docs)
4. **Deviation: pin OWN-04 ledger test to its entry, not file position** — `a604931` (fix)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

## Files Created/Modified

- `tests/fixtures/incremental/user_variant_candidate_miss.json` — synthetic two-row cassette; one
  Work Request # with an embedded space (the sanitizer-affected form) and two distinct foreman
  names sharing one (WR, week) pair.
- `tests/test_parity_shadow.py` — `UserVariantCandidateParityTests` (5 tests): the reproduction,
  adjacency, empty/single-row edges, reversed-ordering invariance, and hash-mismatch/both-empty
  probes.
- `pipeline/orchestrate.py` — `_resolve_row_wr_week` fixed and re-documented (37 added / 15
  removed lines, confined to this one function).
- `tests/test_incremental_read.py` — `AffectedPairKeyContractTests` (5 tests, 15 subtests): the
  bidirectional WR/week parity contract, subset-only property, no-admit-everything property, and
  regression guard.
- `.planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md` — tracked
  defect record (created).
- `.planning/phases/11-incremental-read-affected-group-regeneration/deferred-items.md` — new
  `## 11-09 (Gap 2 — INC-02 candidate divergence)` section.
- `memory-bank/living-ledger.md` — dated `## [2026-09-14 18:00]` entry.
- `tests/test_own04_documentation.py` — deviation fix (see Deviations below); NOT in this plan's
  `files_modified`.

## Decisions Made

See `key-decisions` in frontmatter. The most consequential: the confirmed cause is (a) WR-form
mismatch plus (b) falsy-WR mismatch (not cause (c), an outside-the-selector cause) — the fix
alone, with no comparator or predicate change, reproduces and then resolves the exact live
symptom.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, scope-boundary exception] Fixed `tests/test_own04_documentation.py`'s ledger-position assumption**
- **Found during:** Plan-level verification (`bash scripts/run_6_gates.sh`, run once after Task 3)
- **Issue:** Task 3's required `memory-bank/living-ledger.md` append (a new dated `## [` heading,
  per this plan's own Task 3 acceptance criteria) became the file's newest `## [` heading.
  `test_records_phase_12_gap_closure_decisions`'s `_newest_ledger_entry()` helper located "the
  newest ledger entry" by literal file position (the last `## [` heading) rather than by content,
  so it started checking my new, unrelated entry instead of Phase 12's gap-closure entry and
  failed on a missing `D-12-C` marker.
- **Fix:** `_newest_ledger_entry()` now locates the SAME Phase 12 entry by its durable `D-12-C`
  content marker (confirmed unique to that one entry in the whole ledger) instead of by position,
  so it stays pinned regardless of what gets appended after it.
- **Files modified:** `tests/test_own04_documentation.py`
- **Verification:** `python -m pytest tests/test_own04_documentation.py -q` → 25 passed;
  full suite `python -m pytest tests/ -q` → 2426 passed / 1 skipped / 610 subtests;
  `bash scripts/run_6_gates.sh` → ALL 6 GATES PASSED.
- **Committed in:** `a604931` (separate commit, not folded into Task 3's docs commit).

---

**Total deviations:** 1 auto-fixed (Rule 1, scope-boundary exception — directly caused by this
plan's own required Task 3 change, and necessary to satisfy the plan's own `<verification>` item
1 requiring the full suite to stay green).
**Impact on plan:** No production behavior change. The fix corrects a fragile test assumption
(pin-by-position instead of pin-by-content) that this plan's required, append-only ledger write
was always going to break for the next plan to touch the ledger — this plan happened to be that
next plan. No scope creep: the file is a test-only structural check on an unrelated Phase 12
runbook page, and the fix makes that check MORE robust, not less strict.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None — no external service configuration required. `RUN_MEMORY_INCREMENTAL_ENABLED` remains OFF
by default; this plan's fix is inert in production today (the incremental branch it corrects is
unreachable while the flag is off).

## Threat Flags

None. This plan's own STRIDE threat register (T-11-23..T-11-28, T-11-SC) was fully dispositioned
within its own scope: T-11-23 (WR-key derivation tampering) mitigated by the one-shared-derivation
fix + bidirectional contract test; T-11-24 (silent billing omission via narrowing) mitigated by
the subset-only and no-admit-everything property tests; T-11-25 (WR normalization collisions)
accepted (widens only, no billing effect, recorded in `deferred-items.md`); T-11-26 (information
disclosure via the new cassette/todo/ledger) mitigated (synthetic WR/foreman values only, no real
Work Request number or person's name — confirmed by grep); T-11-27 (repudiation of an untracked
live defect) mitigated by the three tracking records; T-11-28 (a flag flip or protected-area edit
smuggled into the fix) mitigated (`git diff --exit-code` clean on every protected path); T-11-SC
(package-manager install) not applicable — no package was installed by this plan. No new,
un-dispositioned surface was introduced.

## Next Phase Readiness

- `UserVariantCandidateParityTests` and `AffectedPairKeyContractTests` are both green, and the
  full regression suite is green with zero regressions (2426 passed / 1 skipped / 610 subtests).
- `bash scripts/run_6_gates.sh` passes ALL 6 gates on the final commit (`a604931`).
- `RUN_MEMORY_INCREMENTAL_ENABLED` was NOT changed — it stays OFF (D-11). No workflow, schedule,
  schema, or billing-formula change.
- The fresh, currently-held ≥5 consecutive-pass `production_frequent` streak this fix requires
  before the INC-04 gate is considered held again is explicitly OWNER-GATED in plan 11-10 Task 3
  (D-09) — this plan does not and cannot establish that streak itself (it requires live scheduled
  runs after this fix ships). The flag flip itself remains a separate operator PR under D-11 and
  is NOT authorized by this closure.
- `11-REVIEW.md` WR-01 (`_is_abbreviated_response` treating a zero-row full response as an
  unchanged delta probe) is a different code path (the read-side delta probe in
  `pipeline/fetch.py`, not the group-side candidate selector this plan fixed) and remains open,
  recorded in `deferred-items.md` for a future plan.
- No blockers.

---
*Phase: 11-incremental-read-affected-group-regeneration*
*Completed: 2026-09-14*

## Self-Check: PASSED

All created/modified files confirmed present on disk:
`tests/fixtures/incremental/user_variant_candidate_miss.json`,
`.planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md`,
`pipeline/orchestrate.py`, `tests/test_parity_shadow.py`, `tests/test_incremental_read.py`,
`tests/test_own04_documentation.py`, `deferred-items.md`, `memory-bank/living-ledger.md`.
All 4 commits (`1feedeb`, `04c618a`, `1ba2293`, `a604931`) confirmed present via
`git log --oneline --all`. Full suite re-run confirmed green
(2426 passed / 1 skipped / 610 subtests); `bash scripts/run_6_gates.sh` confirmed ALL 6 GATES
PASSED on the final commit.
