---
phase: 01-subcontractor-rate-logic-modification
plan: 08
subsystem: python-billing-pipeline
tags: [python, gap-closure, code-review, helper-shadow, attachment-identity, hash-history, valid-wr-weeks, current-keys]
requirements: [REVIEW-CR-01]
dependency_graph:
  requires:
    - "01-01..01-07 (Phase 1 subcontractor variant infrastructure plus the wave-5 filter-matcher fixes from 01-07; specifically Plan 02's parser extension that emits `(wr, week, 'aep_billable_helper', '<sanitized_foreman>')` tuples for `_AEPBillable_Helper_<name>_<hash>.xlsx` filenames)"
  provides:
    - "Helper-shadow `file_identifier` derivation aligned at all THREE main-loop sites (per-group identifier construction, `valid_wr_weeks` cleanup-tuple builder, `current_keys` hash-history-prune key) so `aep_billable_helper` / `reduced_sub_helper` variants integrate correctly with `_has_existing_week_attachment`, `delete_old_excel_attachments`, `cleanup_untracked_sheet_attachments`, and the hash-history skip optimization."
    - "Regression class `TestHelperShadowVariantFileIdentifier` proving the round-trip (main-loop derivation -> filename -> parser -> back to same identifier) plus source-level grep guards against silent production revert."
  affects:
    - "generate_weekly_pdfs.py: main() per-group variant branch (Site 1, ~L6013), valid_wr_weeks cleanup-tuple builder (Site 2, ~L6732), current_keys hash-history-prune (Site 3, ~L6801)."
    - "tests/test_subcontractor_pricing.py: +1 test class (`TestHelperShadowVariantFileIdentifier`), +9 methods, including 2 source-level grep guards."
tech-stack:
  added: []
  patterns:
    - "Three-site lock-step invariant — when an identity tuple is constructed at multiple sites in the same function (`main()`), every site must use byte-identical derivation logic for every variant. Drift between sites is the bug shape CR-01 documents: pre-fix Sites 1 and 3 both fell through to the User-derived `else` branch, which aligned by accident; with Site 1 now correctly deriving from `__helper_foreman`, Sites 2 and 3 must follow or the alignment breaks the OTHER way."
    - "Source-level grep guards for nested cascade fixes — the three identity-construction sites live inside `main()` (a ~2000-line function) and cannot be imported / monkey-patched directly, so the regression test class includes 2 source-level guards (per the same defense pattern used in Plan 01-07's `TestExcludeWrsMatchesAllVariants` / `TestWrFilterMatchesAllVariants`) that read `generate_weekly_pdfs.py` and assert the three-tuple gate `('helper', 'aep_billable_helper', 'reduced_sub_helper')` appears at >= 3 locations. Defeats the 'test mirror passes but production reverted' failure mode."
    - "`identifier` vs `file_identifier` distinction preserved — `identifier` is the history-key shape (pipe-joined triple `{foreman}|{dept}|{job}` for helper-style variants), `file_identifier` is the filename-embedded form (sanitized foreman name only). The two diverge for helper-style variants and coincide for non-helper variants. Sites 1 and 3 build the history-key shape; Site 2 builds only the file-identifier shape. Same invariant as the legacy `helper` branch."
key-files:
  created: []
  modified:
    - generate_weekly_pdfs.py
    - tests/test_subcontractor_pricing.py
decisions:
  - "Did NOT modify the legacy `helper` branch body — only widened the gate condition (`variant == 'helper'` -> `variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper')`). The legacy helper-variant behavior is byte-identical to pre-fix."
  - "Did NOT add the non-helper subcontractor variants (`aep_billable`, `reduced_sub`) to the helper-gate. Their filenames carry no identifier suffix and `build_group_identity` correctly returns `identifier=''` for them, so the existing `else` branch fallthrough is correct. Adding them to the helper-gate would set `identifier='||'` (literal pipes-on-empties) and break hash-history bucket cohesion for primary subcontractor variants."
  - "Preserved the `vac_crew` branch's `identifier=''` / `file_identifier=''` behavior unchanged (CR-01 only addresses the helper-shadow gap)."
  - "Defensive permissiveness on empty `__helper_foreman` is intentional and kept — upstream `_valid_helper_row` gate in `group_source_rows` prevents empty foreman from reaching this code path in production, but the identifier derivation itself does not crash if the gate is ever bypassed (returns `file_identifier=''`). WR-03 in plan 01-10 will add a defensive raise at the `generate_excel` filename-suffix branch (a different code path)."
  - "Three-site fix bundled into one plan rather than three separate plans — drift between sites is exactly the bug shape; splitting would reintroduce the masked-by-accident state CR-01 documents."
metrics:
  duration_minutes: 7
  completed_date: "2026-05-15"
  tasks_completed: 4
  files_modified: 2
  tests_added: 9
  subtests_added: 0
  full_suite_passing: 556
  full_suite_skipped: 22
  insertions: 267
  deletions: 5
---

# Phase 01 Plan 08: CR-01 three-site helper-shadow attachment identity fix Summary

REVIEW-CR-01 closed: extend the three identity-construction sites inside `main()` so the two helper-shadow variants (`aep_billable_helper`, `reduced_sub_helper`) derive `file_identifier` / `identifier` from `__helper_foreman` instead of falling through to the `User`-derived `else` branch — restoring the round-trip with `build_group_identity`, re-enabling the skip-unchanged optimization for shadow variants, and unblocking `delete_old_excel_attachments` from finding prior shadow-variant attachments by identifier match.

## Objective

Phase 1's subcontractor pipeline emits two new helper-shadow variants whose Excel filenames look like `WR_<wr>_WeekEnding_<MMDDYY>_<timestamp>_AEPBillable_Helper_<foreman>_<hash>.xlsx` (and the `_ReducedSub_Helper_` twin). Plan 02 correctly extended `build_group_identity` to parse those filenames into `(wr, week, 'aep_billable_helper', '<sanitized_foreman>')` tuples. But three sister sites inside `main()` that build the OTHER side of the comparison continued to derive `file_identifier=''` for shadow variants — falling through to the `User`-keyed `else` branch that returns `''` because shadow rows don't have `User` populated. The two sides therefore never matched, which silently:

1. **Broke skip-unchanged for shadow variants** — every 2h cron regenerated and re-uploaded every `_AEPBillable_Helper_*` / `_ReducedSub_Helper_*` file even when nothing changed. With 7 weekday runs × N helper-shadow groups × 2 (TARGET + PPP for `_ReducedSub_Helper_*`), this is meaningful Smartsheet API pressure (delete + attach calls per file per run).
2. **Made `delete_old_excel_attachments` miss prior shadow-variant attachments** — the per-row delete step compared `parsed_identifier='Jane_Smith'` against `task_file_identifier=''` and never found a match. On `TARGET_SHEET_ID` the end-of-run `cleanup_untracked_sheet_attachments` masked this by timestamp-pruning all-but-newest per identity, but on `SUBCONTRACTOR_PPP_SHEET_ID` there is no equivalent cleanup pass (until WR-01 lands in plan 01-13) — so `_ReducedSub_Helper_*` attachments orphaned permanently on PPP, one extra per run.

The fix is a three-site lock-step extension of the existing `helper` branch's gate condition: the helper-shadow variants share the `__helper_foreman`-based derivation rather than fall through to the `User`-keyed `else`.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Site 1: main-loop per-group identifier / file_identifier for shadow variants | `23f9ed4` | `generate_weekly_pdfs.py` |
| 2 | Site 2: valid_wr_weeks cleanup-tuple builder for shadow variants | `4f77a84` | `generate_weekly_pdfs.py` |
| 3 | Site 3: current_keys hash-history-prune key for shadow variants | `f1b3b5d` | `generate_weekly_pdfs.py` |
| 4 | TestHelperShadowVariantFileIdentifier regression class (9 tests) | `d5cdfa9` | `tests/test_subcontractor_pricing.py` |

## Site-by-Site Diff Summary

**Site 1 — main-loop per-group identifier construction (`generate_weekly_pdfs.py:6013`, inside `main()`'s `for group_key, group_rows in groups.items():` loop, immediately above the `history_key = f"{wr_num}|{week_raw}|{variant}|{identifier}"` line):**

```diff
- if variant == 'helper':
+ if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
      helper_foreman = first_row.get('__helper_foreman', '')
      helper_dept = first_row.get('__helper_dept', '')
      helper_job = first_row.get('__helper_job', '')
      identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
      file_identifier = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50] if helper_foreman else ''
  elif variant == 'vac_crew':
      identifier = ''
      file_identifier = ''
  else:
      # Non-helper subcontractor variants (aep_billable, reduced_sub) intentionally
      # fall through here — their filenames carry no identifier suffix.
      user_val = first_row.get('User')
      identifier = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
      file_identifier = identifier
```

This is the most important of the three sites: it determines what `task['file_identifier']` carries into `_has_existing_week_attachment` (the skip-unchanged check) and `_upload_one` → `delete_old_excel_attachments` (the prior-attachment cleanup).

**Site 2 — valid_wr_weeks cleanup-tuple builder (`generate_weekly_pdfs.py:6732`, the second `for group_key, group_rows in groups.items():` loop that runs after generation completes, immediately before `cleanup_untracked_sheet_attachments(client, TARGET_SHEET_ID, valid_wr_weeks, ...)`):**

```diff
  wr = _RE_SANITIZE_HELPER_NAME.sub('_', wr)[:50]
  variant = group_rows[0].get('__variant', 'primary')
- if variant == 'helper':
+ if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
      helper_foreman = group_rows[0].get('__helper_foreman', '')
      file_id = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50] if helper_foreman else ''
  elif variant == 'vac_crew':
      file_id = ''
  else:
      user_val = group_rows[0].get('User')
      file_id = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
  valid_wr_weeks.add((wr, week_raw, variant, file_id))
```

Site 2 builds the 4-tuple identity set that `cleanup_untracked_sheet_attachments` consumes. The pre-fix `else`-fallthrough produced `(wr, week, 'aep_billable_helper', '')` tuples that NEVER matched `build_group_identity`'s parsed `(wr, week, 'aep_billable_helper', 'Jane_Smith')` tuples — risking the cleanup pass either pruning legitimate attachments (mistake them for stale) or missing orphans (fail to recognise them as live). The first `valid_wr_weeks.add(ident)` call earlier in this same block (which consumes `build_group_identity(fname)` output directly) was already correct; only the second add-call needed the fix.

**Site 3 — current_keys hash-history-prune key (`generate_weekly_pdfs.py:6801`, inside `if history_updates:` block, inside `if not _time_budget_exceeded:` arm):**

```diff
  _wr = _RE_SANITIZE_HELPER_NAME.sub('_', _wr)[:50]
  _week = key.split('_',1)[0]
  _variant = group_rows[0].get('__variant', 'primary')
- if _variant == 'helper':
+ if _variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
      _hf = group_rows[0].get('__helper_foreman', '')
      _hd = group_rows[0].get('__helper_dept', '')
      _hj = group_rows[0].get('__helper_job', '')
      _ident = f"{_hf}|{_hd}|{_hj}"
  elif _variant == 'vac_crew':
      _ident = ''
  else:
      _uv = group_rows[0].get('User')
      _ident = _RE_SANITIZE_IDENTIFIER.sub('_', _uv)[:50] if _uv else ''
  current_keys.add(f"{_wr}|{_week}|{_variant}|{_ident}")
```

Site 3 reconstructs Site 1's `history_key` so the hash-history prune knows which keys are still "live" (any key in `hash_history` but not in `current_keys` is treated as stale and deleted before `save_hash_history` runs). Pre-fix, BOTH Sites 1 and 3 fell through to the `User`-derived `else` branch, so the two stayed aligned by accident (both produced `''` identifiers). With Site 1 now correctly deriving from `__helper_foreman`, Site 3 must follow — otherwise the freshly-written hash entry this run is treated as stale on the next run and deleted, permanently breaking hash-skip persistence for shadow variants. Note `_ident` here is the HISTORY-KEY shape (pipe-joined triple), NOT the FILE-IDENTIFIER shape.

## Before/After `_has_existing_week_attachment` Contract

For an `_AEPBillable_Helper_Jane_Smith_<hash>.xlsx` attachment on a target row, with `task['file_identifier']` from Site 1's main-loop derivation:

| Site 1 output (pre-fix) | Site 1 output (post-fix) | `build_group_identity` parsed | Match? |
|------------------------|--------------------------|--------------------------------|--------|
| `file_identifier = ''` (from `User`-keyed else, `User` blank on shadow row) | `file_identifier = 'Jane_Smith'` (from `_RE_SANITIZE_HELPER_NAME.sub('_', 'Jane Smith')`) | `(wr, week, 'aep_billable_helper', 'Jane_Smith')` | pre-fix `False` ; post-fix `True` |

Same shape for `_ReducedSub_Helper_<name>_<hash>.xlsx`. Skip-unchanged optimization now works; orphan accumulation eliminated for the prior-attachment-delete step (orphan accumulation on PPP overall is fully eliminated when paired with WR-01's PPP end-of-run cleanup pass in plan 01-13).

## Test Counts

| Class | Tests | Status |
|-------|-------|--------|
| `TestHelperShadowVariantFileIdentifier` (NEW) | 9 | passed |
| `TestPhase1IntegrationRegression` (Phase 1 byte-identical hash regression) | 5 | passed |
| `TestSubcontractorVariantKillSwitchAndScope` (critical invariant per executor prompt) | 4 | passed |
| Full suite | 556 passed / 22 skipped | passed |

Pre-plan baseline (per 01-07-SUMMARY): 547 passed / 22 skipped. Post-plan: 556 / 22 (+9 new tests, no regressions). The byte-identical-hash regression class confirms Phase 1 ROADMAP success criterion 5 is preserved — the change is identifier-derivation only and does NOT touch `calculate_data_hash`, `_resolve_row_price`, `group_source_rows` row tagging, or `generate_excel` pricing.

## Deviations from Plan

None — plan executed exactly as written. Both helper-shadow variants integrate via the same three-tuple gate `('helper', 'aep_billable_helper', 'reduced_sub_helper')` at all three sites; the non-helper subcontractor variants (`aep_billable`, `reduced_sub`) continue to fall through the `else` branch correctly (their filenames carry no identifier suffix); the legacy `helper` branch body is preserved byte-for-byte.

The plan's Task 2 acceptance criterion stated `grep -c "valid_wr_weeks.add" generate_weekly_pdfs.py` should return `1`, but the file legitimately has TWO `valid_wr_weeks.add(...)` calls — the first at the top of the build block consumes `build_group_identity(fname)` output directly (already returns a 4-tuple, no derivation needed), and the second (the one this plan edits) is the per-group cleanup-tuple builder. Both are correct and pre-existed this plan; the criterion appears to have been written without awareness of the first call. Verified via Python-side context check (`generate_weekly_pdfs.py` rfind for the second add-call, confirmed the three-tuple gate appears 1504 chars upstream in the same block — well within the same logical site).

## Critical Invariants Verified

- `pytest tests/test_subcontractor_pricing.py::TestPhase1IntegrationRegression -v` exits 0 (5/5 — byte-identical hash guarantee preserved per ROADMAP success criterion 5).
- `pytest tests/test_subcontractor_pricing.py::TestSubcontractorVariantKillSwitchAndScope -v` exits 0 (4/4 — kill-switch + ORIG-folder exclusion + dual-folder precedence unchanged).
- `pytest tests/ -v` exits 0 (556 / 22 skipped).
- `python -m py_compile generate_weekly_pdfs.py` exits 0.
- `grep -c "@cell" generate_weekly_pdfs.py` returns 0 (CLAUDE.md absolute ban preserved).
- The three-tuple gate `('helper', 'aep_billable_helper', 'reduced_sub_helper')` appears at 4 source locations in `generate_weekly_pdfs.py`: line 2004 (`calculate_data_hash`, pre-existing from Plan 02), line 6013 (Site 1 main-loop, this plan), line 6732 (Site 2 valid_wr_weeks, this plan), line 6801 (Site 3 current_keys, this plan, `_variant` form). Threshold per plan was `>= 3`; achieved 4.

## Self-Check: PASSED

- All 4 task commits exist:
  - `23f9ed4` Site 1 main-loop file_identifier for shadow variants (CR-01)
  - `4f77a84` Site 2 valid_wr_weeks file_id for shadow variants (CR-01)
  - `f1b3b5d` Site 3 current_keys hash-history prune for shadow variants
  - `d5cdfa9` TestHelperShadowVariantFileIdentifier regression (CR-01)
- All modified files present and compile clean:
  - `generate_weekly_pdfs.py` — 3 helper-shadow gates added; `python -m py_compile` OK.
  - `tests/test_subcontractor_pricing.py` — `TestHelperShadowVariantFileIdentifier` class present (9 tests, all pass); `python -m py_compile` OK.
- No file deletions across any of the four task commits.
- Full pytest suite passes (556 / 22 skipped) with no regressions.

## Threat Flags

None — the change is identifier-derivation logic only. No new network endpoints, no new auth paths, no new file access patterns, no new schema or trust-boundary modifications. The fix narrows (re-aligns) an existing identity comparison; it does not introduce new attack surface.

## Cross-Reference

- Closes REVIEW-CR-01 in `.planning/phases/01-subcontractor-rate-logic-modification/01-REVIEW.md` (all three sites named in the review: main-loop L5966-5983, `valid_wr_weeks` L6660-6671, `current_keys` L6716-6726).
- Paired with WR-01 (plan 01-13, PPP end-of-run cleanup pass) for full belt-and-suspenders elimination of orphan accumulation on `SUBCONTRACTOR_PPP_SHEET_ID`. CR-01 alone fixes the per-row delete-old path; WR-01 adds the catch-all cleanup pass.
- Paired with WR-03 (plan 01-10, defensive raise on empty `__helper_foreman` in `generate_excel` filename suffix branch) — CR-01 keeps identifier derivation permissive (returns `''` and continues), WR-03 will fail loudly at the filename-construction site.
- Sibling pattern to 01-07's three-tuple matcher extension in `_key_matches_excluded_wr` / `_key_matches_wr` — both plans add shadow-variant recognition to existing exact-match cascades using the same source-level grep-guard defense pattern in tests.
