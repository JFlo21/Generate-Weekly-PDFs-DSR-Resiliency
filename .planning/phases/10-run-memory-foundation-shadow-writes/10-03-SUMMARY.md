---
phase: 10-run-memory-foundation-shadow-writes
plan: 03
subsystem: database
tags: [supabase, postgres, pipeline_memory, shadow-write, fail-open, sheet_registry, group_state, attachment-side-channel, billing-pipeline]

# Dependency graph
requires:
  - phase: 10-run-memory-foundation-shadow-writes
    provides: "plan 10-01's pipeline_memory package (client.py, schema.sql, run_ledger) and plan 10-02's row_state/row_event writer + _run_memory_write_phase per-sheet loop, both of which this plan extends"
provides:
  - "pipeline/fetch.py::_LAST_SHEET_VERSIONS / get_last_sheet_versions -- per-sheet Sheet.version watermark, captured inside the fetch loop, never written onto any row dict"
  - "pipeline_memory/writer.py::upsert_sheet_registry -- one table upsert on sheet_registry with on_conflict='sheet_id', folder_id reserved/omitted, fail-open"
  - "pipeline_memory/writer.py::upsert_group_state / bump_group_state_withheld -- one table upsert on the five-part group_state key, attachment keys omitted (not nulled) when absent"
  - "pipeline/orchestrate.py::_resolve_mem_sheet_kind / _extract_attachment_id_name / _build_group_state_flush -- three standalone, pure, directly-testable helper functions"
  - "pipeline/orchestrate.py's group loop / _upload_one / post-upload flush -- the deferred group_state record, the lock-guarded attachment side channel, and the third (group_state) flush positioned after both existing production flushes"
affects: [10-06-apply-schema-and-control-run]

# Actuals (#2632)
actuals:
  tokens: 12672
  tasks: 3
  commits: 6

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Standalone, pure, fully-typed module-level helper functions (_resolve_mem_sheet_kind, _extract_attachment_id_name, _build_group_state_flush) instead of closures nested inside main() -- same testability rationale as 10-02's _run_memory_write_phase, extended one step further: a module-level function reading a live-proxy global at call time is exactly as 'live' as a nested closure doing the same read, but is independently unit-testable without invoking any of main()'s Smartsheet/Excel/Sentry machinery"
    - "Structural (source-inspection) tests for logic that lives inside a closure that cannot be extracted without risking the delete-then-upload billing guard -- mirrors the existing precedent in tests/test_skip_upload_delete_gating.py for the exact same nested _upload_one function"
    - "Two-pass shadow write for a value not yet known on the first pass (sheet_registry's version watermark): call the same idempotent upsert twice, once before and once after the value becomes available, rather than restructuring the run to compute it earlier"

key-files:
  created: []
  modified:
    - pipeline/fetch.py
    - pipeline_memory/writer.py
    - pipeline/orchestrate.py
    - tests/test_pipeline_memory_shadow.py

key-decisions:
  - "_resolve_mem_sheet_kind, _extract_attachment_id_name, and _build_group_state_flush are standalone module-level functions in pipeline/orchestrate.py rather than closures nested inside main() (the plan's literal 'local closure' wording) -- functionally identical (all three still read live-proxy globals / caller-supplied state at call time, never a module-level snapshot), but directly unit-testable via mock.patch.object without invoking main()'s full Smartsheet/Excel/Sentry machinery, matching the established _run_memory_write_phase pattern from plan 10-02"
  - "The attachment side-channel key uses task['file_identifier'], not task['identifier'] -- the two differ for helper-variant groups (identifier is the composite 'foreman|dept|job' string used as the group_state DB key; file_identifier is the shorter sanitized-foreman string baked into the filename and used by delete_old_excel_attachments) -- per 10-03-PLAN.md's <interfaces> key_links, confirmed against pipeline/orchestrate.py's existing call site at delete_old_excel_attachments(..., identifier=task['file_identifier'])"
  - "sheet_registry's kind resolver and version watermark are written via TWO idempotent upserts (pass 1 right after discovery, pass 2 after the row-write phase) rather than deferring the whole registry write to the end of the run -- keeps the hook next to the phase it observes (discovery -> registry existence; fetch -> version watermark) instead of accumulating more deferred state"
  - "The new group_state flush's computation call (_build_group_state_flush) plus the writer call are both wrapped in their own try/except, even though the pure function is proven not to raise given this call site's consistent dict shape -- defense-in-depth matching every other pipeline_memory hook in main(), and explicitly required by the T-10-11 threat mitigation (the two earlier flushes must be provably unaffected by a failure in this one)"

requirements-completed: [MEM-01, MEM-03]

coverage:
  - id: D1
    description: "sheet_registry holds one row per validated source sheet (name, kind, column_mapping, last_sheet_version) via upsert_sheet_registry, called twice per run so the version watermark lands once pipeline.fetch has captured it; folder_id stays reserved/omitted"
    requirement: MEM-01
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::SheetVersionWatermarkTests, SheetKindClassificationTests, SheetRegistryWriterTests"
        status: pass
      - kind: other
        ref: "python -c AST import-isolation check on pipeline_memory/writer.py -> WRITER_BOUNDARY_OK"
        status: pass
    human_judgment: false
  - id: D2
    description: "group_state writer + deferred record + attachment side channel: upsert_group_state upserts on the five-part (wr,week_ending,variant,identifier,target_sheet_id) key, omits attachment_id/attachment_name when absent, and a reduced_sub fan-out's two upload legs produce two distinct rows with distinct attachment ids; the upload worker's four-string return contract and the delete-then-upload order are unchanged"
    requirement: MEM-03
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::GroupStateWriterTests, AttachmentSideChannelTests"
        status: pass
      - kind: other
        ref: "python -m pytest tests/test_skip_upload_delete_gating.py tests/test_orphaned_primary_attachment.py -q (unmodified, still pass)"
        status: pass
    human_judgment: false
  - id: D3
    description: "group_state is flushed under the same crash-consistency withhold contract as the existing durable hash store: a group whose upload errored or was suppressed by SKIP_UPLOAD does not advance its group_state row, the new flush is positioned strictly after both existing production flushes, and a zero-deferred-records run never calls the writer at all"
    requirement: MEM-03
    verification:
      - kind: unit
        ref: "tests/test_pipeline_memory_shadow.py::GroupStateFlushComputationTests"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- generate_weekly_pdfs.py tests/golden/run_summary_baseline.json .github/workflows/ requirements.txt pipeline/upload.py"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh"
        status: pass
    human_judgment: false

duration: ~37min
completed: 2026-08-25
status: complete
---

# Phase 10 Plan 03: Run-Memory Foundation (shadow writes) Summary

**`sheet_registry` and `group_state` -- the two remaining MEM-01 tables -- are now shadow-written from `pipeline/orchestrate.py`, including the `reduced_sub` fan-out's per-sheet attachment ids captured through a lock-guarded side channel, without changing the upload worker's four-string contract or the delete-then-upload billing guard.**

## Performance

- **Duration:** ~37 min
- **Started:** 2026-08-25T17:55Z (approx., continuing from plan 10-05's completion)
- **Completed:** 2026-08-25T18:32Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `pipeline/fetch.py` captures each source sheet's own `Sheet.version` into a thread-safe, lock-guarded module-level dict (`_LAST_SHEET_VERSIONS`) right after the sheet fetch succeeds -- the only place the `Sheet` object is in scope this run -- and exposes it via `get_last_sheet_versions()`, never writing it onto any row dict
- `pipeline_memory/writer.py::upsert_sheet_registry` issues one `on_conflict="sheet_id"` upsert per call, with `kind` and `last_sheet_version` supplied by the caller so the package keeps importing nothing from `pipeline.*`; `folder_id` stays reserved/omitted per the plan's flagged assumption
- `pipeline/orchestrate.py::_resolve_mem_sheet_kind` classifies a sheet as `subcontractor` / `original_contract` / `primary` by reading `pipeline.discovery`'s live-proxy globals at call time; the registry hook fires twice per run (pass 1 right after discovery, pass 2 once the version watermark is known) -- both idempotent upserts on the same key
- `pipeline_memory/writer.py::upsert_group_state` upserts on the five-part `(wr,week_ending,variant,identifier,target_sheet_id)` key, including `attachment_id`/`attachment_name` only when non-`None` so PostgREST's partial-upsert semantics never clobber a prior run's attachment metadata; `bump_group_state_withheld` is a tiny public counter entry point for the flush's withhold decision
- `pipeline/orchestrate.py::_upload_one` captures the created attachment's id/name (via the new pure `_extract_attachment_id_name` helper) into a `threading.Lock`-guarded side channel keyed by `(group_key, variant, file_identifier, target_sheet_id)`, wrapped in its own swallow-everything `try/except` -- the delete-then-upload order, the retry wrapper, and the worker's four status strings are all unchanged and verified via source inspection
- A third, independent post-upload flush (`_build_group_state_flush`, a pure standalone function) is positioned strictly after the local hash-history flush and the durable hash-store flush, reusing the same `_group_upload_ok` map: a group whose upload did not fully complete is withheld (counted, no memory row), and a `reduced_sub` group's one deferred record expands into one row per matching upload-task `target_sheet_id`, driven from the actual task list rather than a hard-coded sheet-id pair
- `tests/test_pipeline_memory_shadow.py` grew from 39 to 69 tests: 30 new tests across `SheetVersionWatermarkTests`, `SheetKindClassificationTests`, `SheetRegistryWriterTests`, `GroupStateWriterTests`, `AttachmentSideChannelTests`, and `GroupStateFlushComputationTests`

## Task Commits

Each task was committed atomically (all three are `tdd="true"` behaviorally exercised, so each has an honest RED test commit followed by a GREEN feat commit; Task 3 also has a small follow-up defense-in-depth fix commit):

1. **Task 1: sheet_registry -- capture the version watermark and shadow-write the registry** - `8fb7e3f` (test, RED) + `ad59cc8` (feat, GREEN)
2. **Task 2: group_state writer, deferred record, and the attachment side channel** - `91ca57d` (test, RED) + `1d4bbae` (feat, GREEN)
3. **Task 3: Flush group_state under the existing withhold contract** - `1ff83bb` (feat) + `34c3c8b` (fix: defense-in-depth try/except)

## TDD Gate Compliance

All three tasks followed an honest RED -> GREEN cycle, verified by reverse-applying (`git apply -R`) each task's production-code diff via a scratchpad patch file (never `git stash`), confirming the corresponding test class(es) fail with `AttributeError`/`ValueError` against the pre-implementation state, then re-applying (`git apply`) and confirming GREEN:

- **Task 1:** RED gate `8fb7e3f` -- 11 tests failed with `AttributeError: module 'pipeline_memory.writer' has no attribute 'upsert_sheet_registry'` (and equivalent for `pipeline.orchestrate._resolve_mem_sheet_kind` / `pipeline.fetch.get_last_sheet_versions`) against the reverted state. GREEN gate `ad59cc8` -- all 11 passed after restoring.
- **Task 2:** RED gate `91ca57d` -- 12 of 14 targeted tests failed with `AttributeError` against the reverted state (2 structural-inspection tests on pre-existing code -- delete-precedes-attach, four known return strings -- passed trivially both before and after, since those properties were already true; this is the same "implementation-invariant test" honesty note plan 10-02's SUMMARY documented for its own `__row_modified_at` capture). GREEN gate `1d4bbae` -- all 14 passed after restoring (2 test bugs were fixed along the way -- see Issues Encountered).
- **Task 3:** RED gate `1ff83bb`'s test half -- all 5 `GroupStateFlushComputationTests` failed with `AttributeError: module 'pipeline.orchestrate' has no attribute '_build_group_state_flush'` against the reverted state. GREEN -- all 5 passed after restoring. Task 3 is `type="auto"` (not `tdd="true"` in the frontmatter), so RED+GREEN landed in one commit rather than two, honoring the same reverse-apply verification discipline.
- **Full regression after every task:** `python -m pytest tests/ -q` (1470 -> 1484 -> 1489 passed, 1 skipped, 132 subtests, up from the 1459-passed baseline) and `bash scripts/run_6_gates.sh` (`ALL 6 GATES PASSED`, mypy delta `65 -> 65` neutral every time).

## Files Created/Modified
- `pipeline/fetch.py` - `_LAST_SHEET_VERSIONS` / `_LAST_SHEET_VERSIONS_LOCK` / `get_last_sheet_versions()`; one capture line inside the per-sheet fetch loop (10 lines net excluding the module-level block)
- `pipeline_memory/writer.py` - `upsert_sheet_registry`, `upsert_group_state`, `bump_group_state_withheld`; `Callable` added to the `typing` import
- `pipeline/orchestrate.py` - `_resolve_mem_sheet_kind`, `_extract_attachment_id_name`, `_build_group_state_flush` (three standalone module-level functions); the two sheet_registry hook call sites; hoisted `_deferred_group_state` / `_mem_attachment_side_channel` / its lock; the group-loop deferred-record append; the attachment side-channel capture inside `_upload_one`; the third post-upload flush, wrapped in its own outer `try/except`
- `tests/test_pipeline_memory_shadow.py` - 39 -> 69 tests: 11 new (Task 1), 14 new (Task 2), 5 new (Task 3), plus 1 pre-existing structural pattern (source inspection) reused across all three

## Decisions Made
See `key-decisions` in frontmatter. All are load-bearing for either correctness (the `identifier`-vs-`file_identifier` side-channel key) or testability (standalone module-level functions instead of closures nested inside `main()`), and are documented inline in the code they govern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two test-authoring bugs in the first draft of `AttachmentSideChannelTests`**
- **Found during:** Task 2, running `python -m pytest tests/test_pipeline_memory_shadow.py -q` after restoring the implementation
- **Issue:** (a) `mock.Mock(id=999, name="foo.xlsx")` does not set a `.name` attribute -- `name` is a reserved `Mock` constructor kwarg that sets the mock's own repr name, not an attribute, so `_extract_attachment_id_name` correctly returned a `Mock` object instead of the string `"foo.xlsx"`. (b) `src.index("_extract_attachment_id_name(")` in the "wrapped in its own try/except" structural test found the function's *definition* line (the first occurrence in the file) instead of the *call site* inside `_upload_one`, since `_extract_attachment_id_name(` is a substring of `def _extract_attachment_id_name(`.
- **Fix:** (a) Set `attach.data.name = "foo.xlsx"` post-construction instead of via the `Mock()` kwarg. (b) Search for the call-site occurrence starting from `src.index("def _upload_one")` instead of from the start of the file, and widened the surrounding-text window (60 -> 150 chars before, 500 -> 900 chars after) to actually span from the `try:` line to the `except Exception:` line of the multi-line capture block.
- **Files modified:** `tests/test_pipeline_memory_shadow.py`
- **Verification:** `python -m pytest tests/test_pipeline_memory_shadow.py -q` -> 64/64 then 69/69 passed after each subsequent task's tests were added back.
- **Committed in:** `1d4bbae` (Task 2 GREEN commit) -- the bugs were caught and fixed before that commit, so the committed test file never carried them.

---

**Total deviations:** 1 auto-fixed (1 blocking, test-only -- no production-code behavior was affected)
**Impact on plan:** Necessary for Task 2's own `<verify>` block to pass; both fixes were caught during the GREEN-phase run, before any commit landed with the bug present. No scope creep.

## Issues Encountered

**Splitting one large multi-task edit into per-task RED/GREEN commits.** Because `pipeline/orchestrate.py`'s three new helper functions (`_resolve_mem_sheet_kind`, `_extract_attachment_id_name`, `_build_group_state_flush`) were originally written together in a single pass (matching how tightly the three tasks' interfaces are specified in the plan), and because each task's own `<verify>` block runs `python -m pytest tests/test_pipeline_memory_shadow.py -q` against the *whole file*, committing Task 1 first required temporarily removing the Task 2/3 test classes and helper functions (saved to a scratchpad file, never deleted from disk permanently) so Task 1's commit boundary was honest -- the test file at that commit genuinely only exercises Task 1's behavior, and the production code at that commit contains only what Task 1 actually needs. The same approach was repeated for Task 2. This is more ceremony than a single "big-bang" commit would have required, but it keeps the per-task atomic-commit narrative accurate: `git show ad59cc8` shows exactly the sheet_registry work, `git show 1d4bbae` shows exactly the group_state-writer-and-side-channel work, and `git show 1ff83bb` shows exactly the flush work. Resolved cleanly -- no lasting effect, and every intermediate state was independently verified (full suite + 6 gates) before its commit.

**The `git stash` prohibition + the RED-verification need.** Proving an honest RED state normally wants "temporarily remove the implementation, run the tests, put it back" -- exactly what `git stash` is for, but `git stash` is explicitly forbidden in this worktree-adjacent execution context (shared `refs/stash` across sibling worktrees, #3542). Used `git diff -- <files> > scratchpad/taskN.patch` followed by `git apply -R` / `git apply` instead -- a targeted, reversible patch-file round-trip that touches only the intended files and leaves no shared state. Resolved cleanly; documented here as the reusable pattern for any future TDD-gated plan running under the same constraint.

## User Setup Required

None - no external service configuration required this plan. `RUN_MEMORY_WRITE_ENABLED` stays default OFF in code; `pipeline_memory/schema.sql` (already complete from plan 10-01, including `group_state`'s five-part primary key and `sheet_registry`'s `kind` CHECK constraint) is still not applied to any live Supabase project -- plan 10-06's operator checkpoint -- so none of this plan's new code paths have ever made a live network call.

## Next Phase Readiness

- All three MEM-01 tables `sheet_registry`, `row_state`/`row_event` (10-02), and `group_state` now have a complete, tested, fail-open shadow-write path from `pipeline/orchestrate.py`; only `run_ledger` (10-01) and this plan's two tables were outstanding, and both are now wired.
- `RUN_MEMORY_WRITE_ENABLED` stays OFF in code; `git diff --exit-code -- generate_weekly_pdfs.py .github/workflows/ requirements.txt tests/golden/run_summary_baseline.json billing_audit/ pipeline/upload.py` is clean, and all 6 gates + the full 1489-test suite pass (up from the 1459-test baseline recorded at the start of this dispatch).
- `tests/test_skip_upload_delete_gating.py` and `tests/test_orphaned_primary_attachment.py` pass unmodified, confirming the attachment side-channel addition did not disturb the existing upload-path contracts.
- Plan 10-06 (apply schema + operator checkpoint + control-run byte comparison) is next; it needs the complete `pipeline_memory/schema.sql` (already shipped in 10-01) applied to `poeyztlmsawfoqlanucc`, PostgREST "Exposed schemas" + "Reload schema cache", and a `SKIP_UPLOAD=true` real-data control-run diff before `RUN_MEMORY_WRITE_ENABLED` can be flipped on in a separate, later PR.
- No blockers for plan 10-06.

## Self-Check: PASSED

All modified files found on disk (`pipeline/fetch.py`, `pipeline_memory/writer.py`, `pipeline/orchestrate.py`, `tests/test_pipeline_memory_shadow.py`, this SUMMARY.md). All six task commits (`8fb7e3f`, `ad59cc8`, `91ca57d`, `1d4bbae`, `1ff83bb`, `34c3c8b`) found in git log. `python -m pytest tests/ -q` -> 1489 passed, 1 skipped, 132 subtests. `bash scripts/run_6_gates.sh` -> ALL 6 GATES PASSED, mypy delta 65 -> 65 (neutral).

---
*Phase: 10-run-memory-foundation-shadow-writes*
*Completed: 2026-08-25*
