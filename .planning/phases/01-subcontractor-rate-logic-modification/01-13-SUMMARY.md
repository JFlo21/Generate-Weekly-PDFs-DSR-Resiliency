---
phase: 01-subcontractor-rate-logic-modification
plan: 13
subsystem: python-billing-engine
tags: [python, gap-closure, code-review, ppp, cleanup, orphan-attachments, wr-01]

# Dependency graph
requires:
  - phase: 01-subcontractor-rate-logic-modification (Plan 04)
    provides: "``_target_sheet_ppp_obj`` initialized unconditionally to ``None`` at the top of ``main()`` and populated by ``create_target_sheet_map_for(client, SUBCONTRACTOR_PPP_SHEET_ID)`` only when the kill switch is on AND PPP id is distinct AND non-TEST_MODE. The new PPP cleanup gate consumes this object via ``_target_sheet_ppp_obj is not None``."
  - phase: 01-subcontractor-rate-logic-modification (Plan 08 / CR-01)
    provides: "``valid_wr_weeks`` set's helper-shadow-aware identifier tuples — the shared authority both cleanup invocations consume. Without CR-01's fix, the new PPP cleanup pass would have pruned LIVE shadow-variant attachments because their parsed identifier tuples would not have matched what the source-side loop added to ``valid_wr_weeks``."
  - phase: 01-subcontractor-rate-logic-modification (Plan 12 / WR-05)
    provides: "``attachment_cache`` PPP-row pre-fetched data dict. The PPP cleanup pass reads this dict on the no-uploads branch (TEST_MODE or no-changes); on the normal production branch (``_upload_tasks`` truthy), ``_cleanup_cache`` is ``None`` for both passes per the existing primary-cleanup contract, so the PPP cleanup falls back to per-row attachment lookup — same correctness contract as the TARGET cleanup."

provides:
  - "Secondary ``cleanup_untracked_sheet_attachments`` invocation at end of ``main()`` for ``SUBCONTRACTOR_PPP_SHEET_ID``. Sequenced AFTER the existing TARGET cleanup so any cache invalidation in the primary pass is visible to the PPP pass. Gated on the same four-condition eligibility check Plan 04 used at ``target_map_ppp`` build time (kill switch + PPP id truthy + distinct sheet + ``_target_sheet_ppp_obj is not None``). Distinct Sentry span op ``smartsheet.cleanup_ppp`` so operators can filter the two passes separately in traces."
  - "Belt-and-suspenders defense against PPP orphan accumulation: per-row ``delete_old_excel_attachments`` (called inside ``_upload_one``) is the primary pruning path; CR-01 (plan 01-08) ensures the helper-shadow identifier matches correctly during that primary pass. The new end-of-session cleanup is the safety net catching anything the per-row delete misses — timestamp-identity drift, future refactor regressions, or other identifier-divergence paths."
  - "TestPppCleanupUntrackedAttachments regression class in ``tests/test_security_audit_followup.py`` — 8 source-level invariant tests locking in dual-invocation count, correct first-args, four-condition gate, distinct Sentry span, correct sheet-object passing, shared cache kwarg, deterministic TARGET-before-PPP sequencing, and function-signature stability."

affects:
  - "Per-row orphan-attachment accumulation on ``SUBCONTRACTOR_PPP_SHEET_ID``: pre-fix, the primary-cleanup pass iterated TARGET_SHEET_ID only — any helper-shadow PPP attachment whose per-row ``delete_old_excel_attachments`` call missed (CR-01 pre-fix bug timeframe; future identifier-drift) accumulated indefinitely. Post-fix, the end-of-session cleanup iterates PPP rows, groups attachments by parsed identity tuple, and prunes everything-but-newest per identity — same algorithm the TARGET cleanup uses, on the same shared ``valid_wr_weeks`` set."
  - "API quota: the new PPP cleanup pass iterates the PPP sheet's rows once per session. Per-row API cost is bounded by the existing ``cleanup_untracked_sheet_attachments`` implementation — on the no-uploads branch it benefits from WR-05's pre-fetched ``attachment_cache``; on the normal production branch (``_upload_tasks`` truthy) the per-row API fallback is used (same as the TARGET cleanup uses on the same branch). The PPP sheet has far fewer rows than TARGET_SHEET_ID (only the subset that needs ``_ReducedSub``), so the per-session cost is modest."
  - "No effect on primary, helper, vac_crew, ``_AEPBillable``, or ``_AEPBillable_Helper_*`` upload paths — they target TARGET_SHEET_ID, already cleaned up by the existing pass. No effect on ORIG-folder sheets (the cleanup is sheet-scoped, not group-scoped). No effect on group hashing, Excel generation, or upload code paths — the cleanup is a strict end-of-session pruning operation."

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Symmetric end-of-session sheet-cleanup pattern: when two routing targets exist for the same data (TARGET_SHEET_ID + SUBCONTRACTOR_PPP_SHEET_ID here), each gets its own cleanup invocation gated on the same eligibility predicate that controls upstream routing. Both share the same ``valid_wr_weeks`` set and the same ``_cleanup_cache`` variable; identifier prefixes (``ppp_``-suffixed Sentry span ops) keep operator traces distinguishable."
    - "Defense-in-depth eligibility gate: the new PPP cleanup gate mirrors the Plan 04 ``target_map_ppp`` build gate verbatim (``SUBCONTRACTOR_RATE_VARIANTS_ENABLED and SUBCONTRACTOR_PPP_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID and _target_sheet_ppp_obj is not None``). Symmetric eligibility means a session that did NOT build ``target_map_ppp`` (because the gate failed there) also will NOT clean up PPP (because the same gate fails here) — no risk of the cleanup pass iterating a sheet that wasn't fetched at session start."
    - "Source-level invariant test class for a multi-line code block embedded in a long function: whitespace-tolerant regex (``\\s*\\n?\\s*``) for the multi-line call signature, plus positional-index comparison (``target_match.start() < ppp_match.start()``) to assert textual sequencing. Mirrors the Plan 12 ``TestPppAttachmentPrefetchBudget`` regex pattern for the same family of source-level invariants."

key-files:
  created:
    - ".planning/phases/01-subcontractor-rate-logic-modification/01-13-SUMMARY.md"
  modified:
    - "generate_weekly_pdfs.py: 56-line insertion between the existing TARGET cleanup invocation (L7136) and the ``# Cleanup legacy / stale Excel files`` comment that follows. The block layout: 47-line docstring-style comment explaining the four gates and the cache semantics, 5-line multi-line ``if`` predicate, 1-line ``with sentry_sdk.start_span`` for the new ``smartsheet.cleanup_ppp`` op, and a 7-line multi-line ``cleanup_untracked_sheet_attachments(...)`` call. No other line in the file is modified — the existing TARGET cleanup invocation, ``_cleanup_cache`` derivation, and ``cleanup_untracked_sheet_attachments`` function definition are untouched."
    - "tests/test_security_audit_followup.py: 171-line append of TestPppCleanupUntrackedAttachments class between the previous final class (TestSourceSheetIdFieldConsistency) and the ``if __name__ == '__main__': unittest.main()`` block. 8 tests using ``inspect.getsourcefile`` + ``pathlib.read_text`` for source-level grep + ``inspect.signature`` for function-signature stability."

key-decisions:
  - "Block-level placement inside ``if not TEST_MODE:`` — the new PPP cleanup lives at the same indentation level as the existing TARGET cleanup span block, so they share the kill-switch-style TEST_MODE gate via the outer ``if`` rather than each duplicating it. This honors the plan's specification (``inside the same if not TEST_MODE: block``) and keeps the TEST_MODE skip semantics consistent across both passes — neither runs in TEST_MODE."
  - "Four-condition eligibility gate at the PPP block ITSELF (not the outer TEST_MODE gate). The outer ``if not TEST_MODE:`` block covers both invocations, but the PPP cleanup additionally requires the kill switch + PPP-id-truthy + distinct-sheet + ``_target_sheet_ppp_obj is not None`` conditions. The 4-tuple gate is the EXACT predicate Plan 04 used at ``target_map_ppp`` build time — symmetric eligibility means the PPP cleanup never iterates a sheet that wasn't successfully mapped at session start."
  - "Distinct Sentry span op (``smartsheet.cleanup_ppp``) rather than reusing ``smartsheet.cleanup``. Lets operators filter Sentry traces by op for either pass separately. The TARGET pass keeps its existing ``smartsheet.cleanup`` op untouched — separate traces, separate dashboards possible."
  - "Multi-line ``cleanup_untracked_sheet_attachments(...)`` invocation for the PPP call rather than collapsing it onto one line. The TARGET cleanup uses single-line invocation for compactness, but the PPP call benefits from multi-line readability because the eligibility-gate block above is already multi-line. The plan's ``<action>`` block explicitly showed the multi-line form; tests are tolerant of either format via whitespace regex."
  - "Shared ``_cleanup_cache`` variable consumed by both passes. The TARGET cleanup computes it once above; the PPP cleanup reuses the same variable. Per the existing primary-cleanup contract, on the normal production case (``_upload_tasks`` truthy), ``_cleanup_cache`` is ``None`` for BOTH passes — uploads invalidate the prefetch snapshot. The PPP cleanup's cache benefit is realized only on the no-uploads branch (TEST_MODE skip or no-changes branch). The Plan 12 WR-05 prefetch's PRIMARY value is amortizing per-row ``_upload_one`` API calls — not amortizing the cleanup pass. The two plans are coupled via consistent cache semantics, not via a guaranteed cleanup-time cache hit."
  - "Function signature ``cleanup_untracked_sheet_attachments(client, target_sheet_id, valid_wr_weeks, test_mode, attachment_cache=None, target_sheet=None)`` left unchanged. The function was already parameterized correctly for dual invocations; WR-01 is a second CALL, not a refactor. The signature-stability test (``test_cleanup_function_signature_unchanged``) uses ``inspect.signature`` to lock this in — a future caller adding a 7th parameter is forced to update the test, which forces a code review discussion of dual-invocation impact."
  - "Sequencing: TARGET cleanup runs BEFORE PPP cleanup. Two reasons: (1) the TARGET sheet contains the union of all variants including helper-shadow ``_AEPBillable_Helper_*`` files, so it's the busier pass — running it first lets the PPP pass benefit from any cache state the TARGET pass might warm; (2) operator log output is deterministic — log readers can rely on TARGET cleanup messages appearing before PPP messages. The sequencing test (``test_ppp_invocation_sequenced_after_target``) uses ``target_match.start() < ppp_match.start()`` to lock this in."
  - "Test class structure mirrors Plan 12's ``TestPppAttachmentPrefetchBudget``: source-level invariant guards via ``inspect.getsourcefile`` + grep / regex. Behavioural cleanup is exercised end-to-end by GitHub Actions workflow runs, not by unit tests — mocking the entire Smartsheet SDK + sheet-iteration + attachment-grouping pipeline would be a large investment for minimal additional confidence. The invariant tests catch the failure modes most likely to regress: missing invocation, wrong sheet ID, missing gate condition, accidentally renamed Sentry span, wrong sheet-object passed, missing cache kwarg, swapped sequencing, function-signature drift."

patterns-established:
  - "When a code review identifies an asymmetry (e.g. cleanup runs on sheet A only when both sheet A and sheet B receive uploads), the gap-closure fix mirrors the existing pattern verbatim for the second target rather than refactoring to a generic helper. Verbatim duplication preserves the established semantics on the existing path — a refactor risks silently changing the TARGET cleanup's behaviour while adding the PPP pass. The cost of duplicated code is bounded (one block, ~50 lines); the cost of a regression on the production TARGET cleanup would be high."
  - "Dual-eligibility-gate symmetry: when a downstream consumer (cleanup pass) depends on an upstream producer (``_target_sheet_ppp_obj`` populated by Plan 04's map build), reuse the producer's exact eligibility predicate at the consumer site. Don't trust the producer's output for ``None``-detection alone — name all four conditions at the consumer too. This is defensive against a future refactor that changes the producer's behaviour without updating the consumer."
  - "When a regression test depends on landed source-level formatting that isn't fully predictable (multi-line call indentation, whitespace between tokens), prefer whitespace-tolerant regex (``\\s*\\n?\\s*``) over hardcoded line fragments. Hardcoded fragments break on indent-only edits that have no semantic impact; regex captures the structural intent (function name + first positional arg + second positional arg in textual order) without locking in a specific format."

requirements-completed: [REVIEW-WR-01]

# Metrics
duration: "~15min (worktree base reset + plan + context load + 56-line implementation + 8-test regression class + Rule-1 test fix + verification + SUMMARY)"
completed: 2026-05-15
---

# Phase 01 Plan 13: WR-01 PPP Cleanup Invocation Summary

**Secondary ``cleanup_untracked_sheet_attachments`` invocation added for ``SUBCONTRACTOR_PPP_SHEET_ID``, sequenced AFTER the existing TARGET_SHEET_ID cleanup inside the same ``if not TEST_MODE:`` block. Gated on the same four-condition eligibility predicate Plan 04 used at ``target_map_ppp`` build time. Shares the existing ``_cleanup_cache`` variable for consistent cache semantics across both passes (per the existing primary-cleanup contract). Distinct Sentry span op (``smartsheet.cleanup_ppp``) so operators can filter the two passes separately in traces. Belt-and-suspenders defense — closes REVIEW-WR-01 from 01-REVIEW.md.**

## Performance

- **Duration:** ~15 min (2026-05-15T16:43Z worktree base reset + planning context load → 2026-05-15T16:55Z final verification + SUMMARY)
- **Tasks:** 2 (Task 1 autonomous implementation; Task 2 ``tdd="true"`` regression test class)
- **Files modified:** 2 (``generate_weekly_pdfs.py``, ``tests/test_security_audit_followup.py``)
- **Tests added:** 8 net new (all in ``TestPppCleanupUntrackedAttachments``)
- **Full suite:** 604 passed / 22 skipped (was 596 / 22 at end of plan 12; +8 from this plan)

## Accomplishments

### Task 1 — Secondary PPP cleanup invocation (commit ``0a30c78``)

A new 56-line block landed between the existing single-line TARGET cleanup invocation at L7136 and the ``# Cleanup legacy / stale Excel files`` comment that follows it. The block layout:

1. **Inline docstring-style comment** (47 lines) explaining the four eligibility gates (kill switch, PPP id truthy, distinct sheet, sheet-object availability), the shared ``_cleanup_cache`` semantics, the WR-05 prefetch coupling rationale, and the belt-and-suspenders defense story relative to CR-01's per-row delete fix. Operators reviewing the block can confirm the intent without re-deriving it from ``01-REVIEW.md``.

2. **Four-condition eligibility gate** (5-line multi-line ``if``):
   ```python
   if (
       SUBCONTRACTOR_RATE_VARIANTS_ENABLED
       and SUBCONTRACTOR_PPP_SHEET_ID
       and SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID
       and _target_sheet_ppp_obj is not None
   ):
   ```
   Mirrors the gates Plan 04 used at ``target_map_ppp`` build time (L5653-5656) — symmetric eligibility means a session that didn't build the PPP map also won't iterate the PPP sheet for cleanup.

3. **Sentry span with distinct op name** (1 line): ``with sentry_sdk.start_span(op="smartsheet.cleanup_ppp", name="Cleanup untracked PPP sheet attachments"):``. Op name distinct from the TARGET cleanup's ``smartsheet.cleanup`` op so operators can filter the two passes in Sentry traces.

4. **Multi-line ``cleanup_untracked_sheet_attachments`` invocation** (7 lines): ``client``, ``SUBCONTRACTOR_PPP_SHEET_ID``, ``valid_wr_weeks``, ``TEST_MODE``, ``attachment_cache=_cleanup_cache``, ``target_sheet=_target_sheet_ppp_obj``. Same shared ``valid_wr_weeks`` set the TARGET cleanup uses (the helper-shadow-aware authority per Plan 08 CR-01); same ``_cleanup_cache`` derived above both passes for consistent cache semantics; the PPP equivalent of ``_target_sheet_obj`` as the ``target_sheet`` kwarg so the cleanup iterates PPP rows rather than re-iterating TARGET rows.

The block is purely additive — no other line in ``generate_weekly_pdfs.py`` is modified. The function signature of ``cleanup_untracked_sheet_attachments`` is unchanged; the existing TARGET invocation at L7136 is byte-identical pre/post.

### Task 2 — ``TestPppCleanupUntrackedAttachments`` regression class (commit ``b455aa4``)

8 source-level invariant tests appended to ``tests/test_security_audit_followup.py`` between the existing final class (``TestSourceSheetIdFieldConsistency``) and the ``if __name__ == '__main__': unittest.main()`` block:

| Test | Pins |
|------|------|
| ``test_cleanup_invoked_twice_in_main`` | ``cleanup_untracked_sheet_attachments(`` count >= 3 (definition + 2 invocations) |
| ``test_ppp_invocation_present_with_correct_first_args`` | Multi-line regex matches ``cleanup_untracked_sheet_attachments(\s*client\s*,\s*SUBCONTRACTOR_PPP_SHEET_ID\s*,`` |
| ``test_ppp_invocation_gated_on_all_four_conditions`` | All four eligibility tokens present: ``SUBCONTRACTOR_RATE_VARIANTS_ENABLED``, ``SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID``, ``_target_sheet_ppp_obj is not None``, and ``and SUBCONTRACTOR_PPP_SHEET_ID`` |
| ``test_ppp_invocation_uses_separate_sentry_span`` | ``smartsheet.cleanup_ppp`` present AND ``smartsheet.cleanup`` (TARGET) still present |
| ``test_ppp_invocation_passes_correct_sheet_object`` | Multi-line regex matches the PPP call's body ending in ``target_sheet=_target_sheet_ppp_obj`` |
| ``test_ppp_invocation_passes_shared_cleanup_cache`` | ``attachment_cache=_cleanup_cache`` count >= 2 (TARGET + PPP) |
| ``test_ppp_invocation_sequenced_after_target`` | ``target_match.start() < ppp_match.start()`` — TARGET appears textually BEFORE PPP |
| ``test_cleanup_function_signature_unchanged`` | ``inspect.signature`` returns the exact 6-parameter signature; signature stability locked |

All 8 tests pass against the post-Task-1 source. The plan's ``tdd="true"`` framing is structurally a regression-lock — the tests assert source-level invariants that already hold after Task 1's implementation. The commit message uses the ``test(...)`` conventional prefix.

## Task Commits

| Task | Commit | Type | Title |
|------|--------|------|-------|
| 1 | ``0a30c78`` | feat | ``feat(01-13): add PPP cleanup invocation (WR-01)`` |
| 2 | ``b455aa4`` | test | ``test(01-13): lock PPP cleanup invocation invariants (WR-01)`` |

## Files Created/Modified

- **``generate_weekly_pdfs.py``** — single 56-line block insertion between L7136 (the existing TARGET cleanup invocation) and the ``# Cleanup legacy / stale Excel files`` comment that follows. No other change. Diff stat: ``56 insertions(+), 0 deletions(-)``.
- **``tests/test_security_audit_followup.py``** — 171-line append between the existing final class (``TestSourceSheetIdFieldConsistency``) and the ``if __name__ == '__main__':`` block. The ``if __name__ == '__main__':`` block was preserved in its trailing position via an ``Edit`` that included both the previous final test and the new class plus the trailing block. Diff stat: ``171 insertions(+), 0 deletions(-)``.
- **``.planning/phases/01-subcontractor-rate-logic-modification/01-13-SUMMARY.md``** — this file.

## Decisions Made

- **Block-level placement inside the outer ``if not TEST_MODE:`` gate.** Both cleanup invocations share TEST_MODE skip semantics by living inside the same outer ``if`` block; the PPP block adds its four-condition eligibility gate inside, not in parallel with, the TEST_MODE gate. This matches the plan's specification verbatim and keeps the existing TEST_MODE skip path correct (neither pass runs in TEST_MODE).

- **Worker pattern: multi-line ``if`` + multi-line ``cleanup_untracked_sheet_attachments(...)`` call.** The TARGET cleanup uses single-line invocation for compactness, but the PPP block precedes its call with a 5-line multi-line ``if`` — adopting the multi-line form for the call body matches the surrounding indentation and reads more naturally. Tests use whitespace-tolerant regex to accept either format.

- **Eligibility gate verbatim from Plan 04's ``target_map_ppp`` build site.** A future refactor that changes either the build-time gate or the cleanup-time gate without updating the other would create a routing-vs-cleanup asymmetry. By using the SAME four-condition predicate at both sites, a single-source-of-truth dependency exists: cleanup never iterates a sheet that wasn't mapped.

- **Distinct Sentry span op (``smartsheet.cleanup_ppp``).** Lets operators filter Sentry traces by op for either pass separately. The TARGET pass keeps its existing ``smartsheet.cleanup`` op untouched.

- **Shared ``_cleanup_cache`` variable.** Both passes consume the same variable derived once above (``_cleanup_cache = attachment_cache if not _upload_tasks else None``). This honors the existing primary-cleanup contract — in the normal production case (uploads ran this session), the variable is ``None`` for BOTH passes because uploads invalidate the prefetch snapshot. On the no-uploads branch, both passes share WR-05's prefetched dict transparently. WR-05's primary value is in ``_upload_one`` per-row API amortization; the cleanup-time benefit is only realized on the no-uploads branch — this is consistent cache semantics, not a guaranteed cleanup-time cache hit.

- **Function signature unchanged.** ``cleanup_untracked_sheet_attachments(client, target_sheet_id, valid_wr_weeks, test_mode, attachment_cache=None, target_sheet=None)`` is parameterized correctly for dual invocations. The signature-stability test locks this in — a future caller adding a 7th parameter is forced to update the test, which forces a code review discussion of dual-invocation impact.

- **8 tests instead of the plan's "at least 7" floor.** The plan's ``<behavior>`` listed 6 behaviors; the ``<action>`` block had 8 test methods (one extra: ``test_cleanup_function_signature_unchanged`` using ``inspect.signature``). All 8 land in this commit per the ``<action>`` spec; the AC ``>= 7`` floor is satisfied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Sequencing test's hardcoded source-fragment fallbacks didn't match landed indentation**

- **Found during:** Task 2 GREEN iteration. The plan's ``test_ppp_invocation_sequenced_after_target`` body had two hardcoded source-fragment fallbacks:
  - ``cleanup_untracked_sheet_attachments(\n            client, TARGET_SHEET_ID`` (12-space indent assumption)
  - ``SUBCONTRACTOR_PPP_SHEET_ID,\n                    valid_wr_weeks`` (20-space indent assumption)

  The landed source uses single-line form for the TARGET cleanup invocation (``cleanup_untracked_sheet_attachments(client, TARGET_SHEET_ID, ...)``) — which the test's alternate-form fallback handled correctly. But the PPP cleanup call uses 24-space indentation (the block lives inside ``if not TEST_MODE:`` → ``if (...)``: → ``with sentry_sdk.start_span(...):`` → call, four indentation levels), so the 20-space hardcoded fragment returned -1.
- **Issue:** Hardcoded indent-specific fragments break the test on any indent-only edit that has no semantic impact. The intent of the test (TARGET appears textually before PPP) is structural, not format-specific.
- **Fix:** Replaced both ``src.find(...)`` calls with whitespace-tolerant ``re.search(...)`` patterns matching the function name + ``client`` + sheet ID + ``valid_wr_weeks`` in textual order, with ``\s*\n?\s*`` between tokens. The TARGET regex stops at ``TARGET_SHEET_ID``; the PPP regex extends through ``valid_wr_weeks`` to disambiguate from the function definition or comment mentions of the sheet ID.
- **Files modified:** ``tests/test_security_audit_followup.py`` (``test_ppp_invocation_sequenced_after_target`` only).
- **Verification:** Post-fix, all 8 tests in ``TestPppCleanupUntrackedAttachments`` pass. The intent (sequencing assertion) is preserved; the test is now resilient to indent-only edits.
- **Committed in:** ``b455aa4`` (Task 2 — fixed in the same commit as the initial test class).

---

**Total deviations:** 1 auto-fixed (Rule 1 bug caught during GREEN→AC-verification iteration; fixed in-commit, no separate fix commit needed).

**Impact on plan:** The deviation is a precision improvement on the test — the source-level invariant is now correctly scoped to the structural intent (sequencing assertion) rather than locking in a specific indentation format. No scope creep.

## Issues Encountered

- **Worktree base reset at agent startup.** The worktree was initialized from master tip (`80900694`, no `.planning/` directory) rather than the `gsd/phase-01-subcontractor-rate-logic-modification` branch tip (`478078f`). The `<worktree_branch_check>` step at agent startup detected the divergence and did `git reset --hard 478078fd...`, restoring the expected base with all prior 01-01 through 01-12 work in scope. No semantic impact on the plan execution — only operational. The reset is a known-safe operation per the startup script's protection ranges (HEAD is on a `worktree-agent-*` branch, not a protected ref).

## User Setup Required

- **None.** All env vars (``SUBCONTRACTOR_PPP_SHEET_ID``, ``SUBCONTRACTOR_RATE_VARIANTS_ENABLED``, ``TEST_MODE``) are pre-existing and have sensible defaults. The PPP cleanup pass starts working automatically on the next scheduled production run that has ``_target_sheet_ppp_obj`` populated (default-on conditions: kill switch on, PPP sheet id default ``8162920222379908`` distinct from TARGET, ``create_target_sheet_map_for`` succeeds).

- **Operational note:** if a production run shows the new Sentry span ``smartsheet.cleanup_ppp`` firing but pruning zero attachments per session, that's the expected steady-state — CR-01's per-row delete fix should keep the PPP sheet's helper-shadow attachments correctly pruned during ``_upload_one``. The end-of-session cleanup is the safety net catching anything that slips through. If the cleanup routinely prunes large numbers of attachments per session, that indicates per-row delete drift and operators should investigate ``delete_old_excel_attachments``'s per-row identifier match logic.

## Combined-impact summary across CR-01 + WR-05 + WR-01

The three plans form a defense-in-depth lifecycle for helper-shadow attachments on the PPP sheet:

| Plan | Layer | Defense |
|------|-------|---------|
| **CR-01 (Plan 01-08)** | Per-row delete-time identifier match | ``delete_old_excel_attachments`` recognizes ``_AEPBillable_Helper_*`` / ``_ReducedSub_Helper_*`` parsed identifiers correctly; per-row pruning catches the file at the source. Primary line of defense. |
| **WR-05 (Plan 01-12)** | Per-row upload-time API amortization | PPP attachment prefetch eliminates the per-row ``list_row_attachments`` API call inside ``_upload_one``'s call to ``delete_old_excel_attachments``. Performance optimization; correctness preserved on the skip path via per-row fallback. |
| **WR-01 (Plan 01-13)** | End-of-session sheet-level cleanup | Belt-and-suspenders cleanup pass for PPP catches anything CR-01's per-row delete missed. Safety net for timestamp-identity drift, future identifier-divergence refactors, or any other PPP-side per-row delete failure mode. Iterates PPP rows once, groups attachments by parsed identity tuple, prunes everything-but-newest per identity. |

In combination, helper-shadow PPP attachments are protected by: (a) per-row delete during upload (CR-01 ensures the identifier matches), (b) per-row cache amortization (WR-05 reduces the API quota cost), and (c) end-of-session cleanup (WR-01 catches any drift). The PPP sheet's orphan-attachment accumulation that REVIEW-WR-01 identified is eliminated by this combination.

## Threat Surface Notes

No new threat surface beyond what the Plan 04 / 08 / 12 SUMMARYs enumerated. The PPP cleanup is a strict OPERATIONAL PRUNING pass:

- **No new network endpoints exposed** — ``cleanup_untracked_sheet_attachments`` was already in production for the TARGET sheet; this is a second invocation against a different sheet ID using the same already-validated function.
- **No new auth boundary** — the same ``SMARTSHEET_API_TOKEN`` is used for both passes; the PPP sheet is just a different sheet ID.
- **No new PII surface** — the cleanup function logs filenames and row IDs at INFO level; the existing Sentry ``before_send_log`` sanitizer (Living Ledger 2026-04-20 12:00 entry) handles any PII drift in those log lines.
- **No new schema or file access pattern** — the cleanup uses the same ``valid_wr_weeks`` set the TARGET pass uses and the same ``_cleanup_cache`` variable.

## Next Phase Readiness

- **Phase 01 BLOCKER list status post-Plan-13.** Plan 13 closes **REVIEW-WR-01** specifically — the orphan-attachment accumulation on PPP. The 3 BLOCKERs identified in ``01-REVIEW.md`` (CR-01 helper-shadow ``file_identifier``, CR-02 ``EXCLUDE_WRS`` matcher, CR-03 ``WR_FILTER`` mirror bug) are addressed by their own gap-closure plans (CR-01 = Plan 01-08; CR-02 = Plan 01-09 et al.; CR-03 = Plan 01-09 et al. — review the 01-08 / 01-09 SUMMARYs for exact mapping). Plan 13 is wave 11 of the gap-closure effort.

- **No blockers for downstream plans.** The PPP cleanup is purely additive; no consumer code changes are required. The remaining gap-closure plan (01-14, if it exists) can land in parallel.

- **Production verification path.** The next scheduled GitHub Actions production run will exercise the new code path automatically when (a) ``SUBCONTRACTOR_RATE_VARIANTS_ENABLED`` is on (default), (b) ``SUBCONTRACTOR_PPP_SHEET_ID`` is reachable (default ``8162920222379908``), (c) ``_target_sheet_ppp_obj`` was successfully populated by ``create_target_sheet_map_for`` (Plan 04 already wired), and (d) the run is not TEST_MODE. Operators should look for the new Sentry span op ``smartsheet.cleanup_ppp`` in traces and the existing ``cleanup_untracked_sheet_attachments`` per-sheet INFO log line for the PPP sheet ID.

## Self-Check

Performed inline before writing this section:

- ``git log --oneline 478078f..HEAD`` shows 2 commits in expected order: **FOUND** (``0a30c78`` Task 1, ``b455aa4`` Task 2)
- ``grep -c "cleanup_untracked_sheet_attachments(" generate_weekly_pdfs.py`` → 3: **CONFIRMED**
- ``grep -c "smartsheet.cleanup_ppp" generate_weekly_pdfs.py`` → 1: **CONFIRMED**
- ``grep -c "Cleanup untracked PPP sheet attachments" generate_weekly_pdfs.py`` → 1: **CONFIRMED**
- ``grep -c "_target_sheet_ppp_obj is not None" generate_weekly_pdfs.py`` → 2 (existing build site + new cleanup gate): **CONFIRMED**
- Multi-line regex ``cleanup_untracked_sheet_attachments\(\s*\n*\s*client,\s*SUBCONTRACTOR_PPP_SHEET_ID`` → 1 match: **CONFIRMED**
- ``grep -c "@cell" generate_weekly_pdfs.py`` → 0: **CONFIRMED** (CLAUDE.md absolute ban honored)
- ``grep -c "class TestPppCleanupUntrackedAttachments" tests/test_security_audit_followup.py`` → 1: **CONFIRMED**
- ``python -m py_compile generate_weekly_pdfs.py`` → exits 0: **CONFIRMED**
- ``python -m py_compile tests/test_security_audit_followup.py`` → exits 0: **CONFIRMED**
- ``pytest tests/test_security_audit_followup.py::TestPppCleanupUntrackedAttachments -v`` → 8 passed: **CONFIRMED**
- ``pytest tests/test_subcontractor_pricing.py::TestPhase1IntegrationRegression -v`` → 5 passed: **CONFIRMED**
- ``pytest tests/`` full suite → 604 passed / 22 skipped / 0 failed: **CONFIRMED**
- No modifications to ``STATE.md`` / ``ROADMAP.md`` — orchestrator owns those: **CONFIRMED**
- File paths exist: ``.planning/phases/01-subcontractor-rate-logic-modification/01-13-SUMMARY.md`` (this file, being written): **CONFIRMED on completion**

## Self-Check: PASSED

## TDD Gate Compliance

| Task | Type | Commit | Title |
|------|------|--------|-------|
| 1 | feat (autonomous) | ``0a30c78`` | ``feat(01-13): add PPP cleanup invocation (WR-01)`` |
| 2 | test (tdd=true regression-lock) | ``b455aa4`` | ``test(01-13): lock PPP cleanup invocation invariants (WR-01)`` |

Plan-level ``type: execute`` (not ``type: tdd``), so the RED/GREEN gate sequence does NOT apply to the plan as a whole. Task 2 is ``tdd="true"`` but the test class is purely a regression-lock for Task 1's source-level invariants — the tests pass against Task 1's already-landed code, not against absent code. The ``test(...)`` commit prefix is correct per the conventional commit type table because the commit contains tests only (no production code).

The Plan 13 spec explicitly anticipates this in Task 2 ``<behavior>``: "Source-level invariant guards — the actual cleanup behavior is exercised by end-to-end runs, not unit tests" — making the tests a regression-lock pattern rather than a behavior-driving TDD cycle. Mirrors Plan 12's identical pattern.

---

*Phase: 01-subcontractor-rate-logic-modification*
*Plan: 13*
*Completed: 2026-05-15*
