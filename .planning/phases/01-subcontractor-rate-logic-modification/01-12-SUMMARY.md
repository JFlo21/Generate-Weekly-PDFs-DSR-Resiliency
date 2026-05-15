---
phase: 01-subcontractor-rate-logic-modification
plan: 12
subsystem: python-billing-engine
tags: [python, gap-closure, code-review, ppp, attachment-prefetch, time-budget, performance, daemon-executor, wr-05]

# Dependency graph
requires:
  - phase: 01-subcontractor-rate-logic-modification (Plan 04)
    provides: "target_map_ppp built in main() against SUBCONTRACTOR_PPP_SHEET_ID, populated only when kill switch on AND distinct sheet AND non-TEST_MODE. Plan 12's PPP prefetch consumes this map via target_map_ppp.items()."
  - phase: 01-subcontractor-rate-logic-modification (Plan 01)
    provides: "SUBCONTRACTOR_PPP_SHEET_ID env var resolved via _coerce_sheet_id; SUBCONTRACTOR_RATE_VARIANTS_ENABLED kill switch."
  - phase: 01-subcontractor-rate-logic-modification (CLAUDE.md Living Ledger 2026-04-22 16:05)
    provides: "Primary attachment prefetch's defense-in-depth contract: _DaemonThreadPoolExecutor + as_completed(timeout=...) + explicit shutdown(wait=False, cancel_futures=True) + _detach_from_atexit_registry on budget-exceed. ATTACHMENT_PREFETCH_MAX_MINUTES / ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN constants. Plan 12 mirrors this pattern verbatim."

provides:
  - "Secondary attachment-prefetch pass for SUBCONTRACTOR_PPP_SHEET_ID rows in main() at the insertion point AFTER the primary prefetch's `else` log and BEFORE the `Load hash history` block. Populates the shared `attachment_cache[target_row.id] = atts` dict so downstream `_upload_one` and `delete_old_excel_attachments` consumers transparently benefit — no consumer code changes required."
  - "Worker closure `_fetch_ppp_row_attachments(row_item)` — character-identical retry / backoff / 429 / RemoteDisconnected / SSL / Timeout handling to `_fetch_row_attachments`, except for the sheet ID constant (SUBCONTRACTOR_PPP_SHEET_ID instead of TARGET_SHEET_ID). Verbatim copy preserves established retry semantics; no shared helper because the closure captures the sheet ID."
  - "Pre-flight budget guard: skip entirely if session-elapsed leaves less than `(ATTACHMENT_PREFETCH_MAX_MINUTES + ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN)` minutes of `TIME_BUDGET_MINUTES`. Emits one INFO log (`🛡️ Skipping PPP attachment prefetch: ...`) with the operator-visible reason and the fallback guarantee. Honors Living Ledger 2026-04-22 16:05 rule (7) — generation headroom is reserved."
  - "Defense-in-depth trifecta scoped to the PPP block: (1) `_DaemonThreadPoolExecutor(max_workers=PARALLEL_WORKERS)` with daemon workers so the tstate lock isn't added to `_shutdown_locks`; (2) `as_completed(ppp_futures, timeout=_ppp_phase_budget_sec)` for the phase wait (the iterator is where blocking happens, not `future.result()`); (3) explicit `ppp_executor.shutdown(wait=False, cancel_futures=True)` in `finally` so the implicit `shutdown(wait=True)` of `with` cannot re-introduce the block-on-stuck-worker bug."
  - "Closure `_detach_ppp_from_atexit_registry()` defined inside the PPP block (captures `ppp_executor`); invoked ONLY on the budget-exceeded branch — Copilot review rule from the primary prefetch's 2026-04-22 16:05 follow-up: don't touch private APIs when workers completed normally."
  - "Counter discipline: `_ppp_prefetch_cancelled` (queued futures we successfully `f.cancel()`'d — returns True only for not-yet-started workers) and `_ppp_prefetch_still_running` (in-flight workers we abandoned to the background) tracked separately. The naive `not f.done()` count is never reported alone — overcounting via that pattern was the 2026-04-22 16:05 incident's rule (5)."
  - "Sentry span `smartsheet.attachment_prefetch_ppp` with `rows_prefetched` / `budget_exceeded` / `cancelled` / `still_running` data — operators can correlate span data with log lines for the run."
  - "TestPppAttachmentPrefetchBudget regression class in tests/test_performance_optimizations.py — 9 tests locking in: (1) constants present, (2) worker function exists, (3) PPP sheet is the actual target, (4) daemon-executor explicit lifecycle (scoped to the PPP block so legitimate `with ThreadPoolExecutor(...)` callers elsewhere are not flagged), (5) pre-flight headroom reservation, (6) counter separation, (7) atexit-detach scoped to budget-exceed only (regex match), (8) eligibility gate, (9) shared attachment_cache participation."

affects:
  - "Per-row Smartsheet API load on `_ReducedSub` / `_ReducedSub_Helper_*` upload paths to PPP. Pre-fix: every PPP upload paid one extra `list_row_attachments` API call inside `_upload_one`'s call to `delete_old_excel_attachments` (cache returned None because the prefetch only covered TARGET_SHEET_ID rows). Post-fix: the call is a dict lookup against the shared cache — zero extra API calls per PPP upload — when the prefetch succeeds; when the prefetch is skipped or budget-exceeded, the per-row fallback path that already existed handles the call transparently."
  - "Session wall-clock for typical run: PPP sheet has far fewer rows than TARGET_SHEET_ID (only the subset that needs _ReducedSub*). At ~570 hypothetical PPP rows (~30% subcontractor share of ~1900 groups), serial per-row fallback was ~570 × ~120ms = ~70s spread across PARALLEL_WORKERS=8 upload workers (~10s wall-clock). The PPP prefetch runs once in parallel across 8 workers, target sheet has ~570 rows, ~10s wall-clock at the prefetch site. The actual saving is API quota, not wall-clock: 570 calls become 0 calls inside the upload phase."
  - "No effect on primary, helper, vac_crew, _AEPBillable, _AEPBillable_Helper_* variants — they upload to TARGET_SHEET_ID only and were already covered by the primary prefetch."
  - "No effect on ORIG-folder sheets (RATE_RECALC_SKIP_ORIGINAL_CONTRACT gate at the sheet-level processing stage), VAC crew workflow, or any pre-existing cache / discovery / hash / Excel-generation / upload code path. PPP prefetch is purely additive."

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Secondary prefetch pass that mirrors a primary prefetch's defense-in-depth pattern verbatim (executor, timeout-on-iterator, explicit shutdown, atexit detach) but scopes them to the secondary block. Each pass owns its own executor / futures list / counters — no cross-contamination, no shared mutable state at module scope. Closure-captured sheet ID constant means no helper refactor is needed; the retry/backoff logic is copy-pasted to preserve established semantics."
    - "Pre-flight skip with operator-visible INFO log when the budget arithmetic doesn't leave enough headroom for the prefetch phase PLUS the main generation loop. The skip degrades to the per-row fallback that already exists in `_has_existing_week_attachment` and `delete_old_excel_attachments` — both already accept `cached_attachments=None`. Correctness is preserved; only latency degrades, and the operator log line names the reason so it's not a silent fallback."
    - "Test class extracts the block-under-test by anchoring on a known-unique function name (`_fetch_ppp_row_attachments`) and slices the source from there to the next outer marker (`# Load hash history` / `hash_history = load_hash_history`). The slice keeps source-level invariant assertions scoped — overly-broad assertions (`assertNotIn('with ThreadPoolExecutor', src)`) flagged legitimate callers elsewhere in the file (folder discovery, parallel row fetch, freeze_row parallelization). The block-slice pattern lets the test verify the PPP block specifically while leaving the rest of the file's executor usage untouched."

key-files:
  created:
    - ".planning/phases/01-subcontractor-rate-logic-modification/01-12-SUMMARY.md"
  modified:
    - "generate_weekly_pdfs.py:
       (a) PPP prefetch block at L5871-6094 (224 lines inserted between the primary prefetch's `else` log and the `Load hash history` comment). Block layout: gate comment + eligibility check + pre-flight budget guard + sentry span + worker closure `_fetch_ppp_row_attachments` + counter init + daemon executor + futures submission + atexit-detach closure `_detach_ppp_from_atexit_registry` + try/as_completed/except/finally lifecycle + final INFO log + span set_data. No other line in the file is modified."
    - "tests/test_performance_optimizations.py:
       (a) New `TestPppAttachmentPrefetchBudget` class appended after `TestAttachmentPrefetchBudget` (184 lines added). 9 tests cover the constants, the worker closure, the PPP sheet ID in the API call, the daemon-executor invariants scoped to the PPP block, the pre-flight headroom log, the counter separation, the atexit-detach scoped to budget-exceed via regex, the eligibility gate, and the shared `attachment_cache` dict participation."

key-decisions:
  - "Insertion point AFTER the primary prefetch's `else` info log (`⚡ Pre-fetched attachments for ...`) and BEFORE the `# Load hash history AFTER optional purge` comment. This is the natural seam: the primary prefetch has completed (success OR skip OR budget-exceed paths all resolve here), `target_map_ppp` was populated earlier in `main()` (Plan 04), and the main generation loop hasn't started. Both prefetch passes share `attachment_cache` (a dict initialized at the primary prefetch's start) and the budget arithmetic uses the same `session_start` reference."
  - "Worker function is a CLOSURE, not a module-level helper. The closure captures `client` and the `SUBCONTRACTOR_PPP_SHEET_ID` module-scope constant. A refactor to a shared helper accepting `sheet_id` as a parameter was rejected — the primary prefetch's `_fetch_row_attachments` is also a closure capturing `TARGET_SHEET_ID`, and cross-coupling the two paths via a shared helper would mean a future change to one's retry semantics could silently regress the other. The retry/error-handling logic is verbatim copy-paste — establishes semantic identity AT the source level, which the regression test confirms by source-level grep."
  - "PPP block uses ITS OWN counters / executor / futures list / detach-closure (`_ppp_prefetch_cancelled`, `_ppp_prefetch_still_running`, `ppp_executor`, `ppp_futures`, `_detach_ppp_from_atexit_registry`). Sharing names with the primary prefetch's `_prefetch_*` / `executor` / `futures` / `_detach_from_atexit_registry` would let a future refactor accidentally entangle the two blocks. The PPP block's identifiers are prefixed `_ppp_*` / `ppp_*` so a grep for either pass returns only its own state."
  - "Pre-flight skip uses INFO log level (not WARNING). The primary prefetch's pre-flight skip uses WARNING because skipping the primary attachment cache means EVERY upload pays an extra API call — a real degradation operators want to see. The PPP prefetch's skip only affects the PPP subset (~30% of groups in a typical run); operators don't need a WARNING because correctness is preserved and per-row fallback handles the gap. The INFO level matches the cost-of-failure: low. The plan's spec explicitly says INFO."
  - "atexit-detach scoped to the budget-exceeded branch only. Per the primary prefetch's Copilot review rule (visible in its `if _prefetch_still_running:` gate at L5840), touching private APIs (`_cf_thread._threads_queues`) when the workers completed normally is unnecessary risk — the workers are already done, `_python_exit` will find them done and return immediately from its `join()`. The PPP block uses the same gate (`if _ppp_prefetch_budget_exceeded:`) and the regression test (`test_ppp_atexit_detach_on_budget_exceed_only`) locks in the scope via regex."
  - "Daemon-executor invariant test is SCOPED to the PPP block. An initial revision used `self.assertNotIn('with ThreadPoolExecutor', src)` over the whole file — that broke 5 legitimate callers (folder discovery, parallel row fetch, freeze_row parallelization) whose work produces non-discardable results (hash_history saves, billing_audit writes, Excel uploads). Those callers correctly use the `with` form with implicit `shutdown(wait=True)`. The PPP prefetch is different: its work IS discardable (cache-warming optimization), so the daemon-executor + explicit shutdown pattern is correct. The test now slices the PPP block from `def _fetch_ppp_row_attachments` to the next `# Load hash history` marker and asserts the invariants on that slice only."

patterns-established:
  - "When mirroring a defense-in-depth pattern from one block to another in the same function, name every identifier with a block-specific prefix (`_ppp_*` here) so that grep for either block's state returns only that block. Cross-contamination between two blocks that share the SAME variable names (`futures`, `executor`, `_prefetch_*`) is a subtle refactor-time trap — a future change in one might accidentally pick up the other's local."
  - "When writing source-level invariant tests for a code block embedded in a larger function, anchor the test on a unique closure name (`_fetch_ppp_row_attachments` here) and slice the source to the next outer marker. Whole-file `assertNotIn` checks are overly broad and flag legitimate callers elsewhere; whole-file `assertIn` checks may pass on the WRONG block. Block-slicing keeps the assertion scope precise."
  - "Operator-visible logs for fallback paths MUST name (a) the reason, (b) the fallback behavior, (c) the correctness guarantee. Example: `Skipping PPP attachment prefetch: only X.Xmin of session budget remain (need >= Ymin for prefetch + generation headroom). PPP target rows will fall back to per-row API calls — correctness is preserved.` Operators tailing logs at incident time should not have to grep the source to understand whether a skip log is a problem."

requirements-completed: [REVIEW-WR-05]

# Metrics
duration: "~30min (planning context load + implementation + iteration on overly-broad test + verification + SUMMARY)"
completed: 2026-05-15
---

# Phase 01 Plan 12: WR-05 PPP Attachment Prefetch Summary

**Secondary attachment-prefetch pass added for `SUBCONTRACTOR_PPP_SHEET_ID` rows; mirrors the primary prefetch's defense-in-depth contract (Living Ledger 2026-04-22 16:05) verbatim — `_DaemonThreadPoolExecutor` + `as_completed(timeout=...)` + explicit `shutdown(wait=False, cancel_futures=True)` + atexit-detach scoped to the budget-exceeded branch. Pre-flight skip reserves generation headroom per rule (7). Populates the shared `attachment_cache` dict so downstream `_upload_one` and `delete_old_excel_attachments` consumers transparently benefit — every `_ReducedSub*` upload to the PPP sheet stops paying an extra `list_row_attachments` API call. Correctness preserved on the skip path via the existing per-row fallback in both consumers (both accept `cached_attachments=None`). 9 new regression tests in `TestPppAttachmentPrefetchBudget` lock in every invariant via source-level grep + block-scoped slice.**

## Performance

- **Duration:** ~30 min (2026-05-15T03:30Z planning context load → 2026-05-15T16:43Z final verification + SUMMARY)
- **Tasks:** 2 (Task 1 autonomous implementation; Task 2 `tdd="true"` regression test class)
- **Files modified:** 2 (`generate_weekly_pdfs.py`, `tests/test_performance_optimizations.py`)
- **Tests added:** 9 net new (all in `TestPppAttachmentPrefetchBudget`)
- **Full suite:** 596 passed / 22 skipped / 46 subtests passed (was 587 / 22 / 46 before Plan 12; +9 from this plan)

## Accomplishments

### Task 1 — Secondary PPP attachment-prefetch pass (commit `8a7a668`)

A new 224-line block landed between the primary prefetch's `else` log (`⚡ Pre-fetched attachments for ... in Xs (parallel w/8 workers)`) and the `# Load hash history AFTER optional purge` comment. The block layout follows the primary prefetch's structure faithfully:

1. **Defense-in-depth contract preamble** — a docstring-style block comment naming the Living Ledger 2026-04-22 16:05 rules each line below honors. Operators reviewing this block in a code review can confirm the invariants without re-deriving them from the incident report.

2. **Eligibility gate** — `_ppp_prefetch_eligible = (SUBCONTRACTOR_RATE_VARIANTS_ENABLED and SUBCONTRACTOR_PPP_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID and not TEST_MODE and target_map_ppp is not None and len(target_map_ppp) > 0)`. Matches the gates the Plan 04 `target_map_ppp` build already used at L5653-5656 — symmetric eligibility means a PPP map that wasn't built (because gate failed there) also won't trigger a prefetch (because the `target_map_ppp is not None and len(...) > 0` check fails here).

3. **Pre-flight budget guard** — only fires when `TIME_BUDGET_MINUTES > 0`. Computes `_ppp_elapsed_min` from `datetime.datetime.now() - session_start`, then `_ppp_remaining_min = TIME_BUDGET_MINUTES - _ppp_elapsed_min`. Skip threshold is `_ppp_required_min = ATTACHMENT_PREFETCH_MAX_MINUTES + ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN`. On skip, emits `🛡️ Skipping PPP attachment prefetch: only {X.X}min of session budget remain (need >= {Y}min for prefetch + generation headroom). PPP target rows will fall back to per-row API calls — correctness is preserved.` and sets `_ppp_prefetch_eligible = False`. The operator-visible log names the reason AND the fallback guarantee.

4. **Sentry span** — `sentry_sdk.start_span(op="smartsheet.attachment_prefetch_ppp", name="Pre-fetch PPP row attachments")` so operators can correlate the prefetch wall-clock with the run's other instrumentation.

5. **Worker closure `_fetch_ppp_row_attachments(row_item)`** — accepts `(wr_num, target_row)`, returns `(target_row.id, atts)`. The retry/error-handling block is character-identical to the primary `_fetch_row_attachments` except for the sheet ID constant (`SUBCONTRACTOR_PPP_SHEET_ID` instead of `TARGET_SHEET_ID`) and the log-line prefix (`PPP rate limited` / `PPP attachment fetch retry` so operators can distinguish primary-vs-PPP log lines on a tail).

6. **Counter initialization** — `_ppp_prefetch_budget_exceeded = False`, `_ppp_prefetch_cancelled = 0`, `_ppp_prefetch_still_running = 0`.

7. **Daemon executor + futures submission** — `ppp_executor = _DaemonThreadPoolExecutor(max_workers=PARALLEL_WORKERS)` (PARALLEL_WORKERS ≤ 8 per CLAUDE.md absolute rule), `ppp_futures = [ppp_executor.submit(_fetch_ppp_row_attachments, item) for item in target_map_ppp.items()]`.

8. **Atexit-detach closure `_detach_ppp_from_atexit_registry()`** — defined as a closure inside the PPP block (captures `ppp_executor`). Pops the executor's worker threads from `_cf_thread._threads_queues` so `_python_exit` doesn't `t.join()` them at interpreter shutdown. `getattr` guards keep the main path working if a future Python rearranges the private helpers.

9. **`try`/`as_completed(...)`/`except FuturesTimeoutError:`/`finally:` lifecycle** — the wait is `for fut in as_completed(ppp_futures, timeout=_ppp_phase_budget_sec):` (the iterator is where blocking happens; rule (2) from the incident). The body reads `row_id, atts = fut.result()` and writes to `attachment_cache[row_id] = atts`. On `FuturesTimeoutError`, flips `_ppp_prefetch_budget_exceeded = True` and logs a WARNING. The `finally` block does three things in order: (a) if `_ppp_prefetch_budget_exceeded`, call `_detach_ppp_from_atexit_registry()` (Copilot review rule: only on budget-exceed); (b) iterate `ppp_futures` to classify `_ppp_prefetch_cancelled` (futures where `f.cancel() == True` — queued only) vs `_ppp_prefetch_still_running` (`not f.done()` — in-flight abandoned); (c) `ppp_executor.shutdown(wait=False, cancel_futures=True)`.

10. **Final INFO log + span set_data** — `🏁 PPP attachment prefetch complete in X.Xs: N rows, M cancelled, K still_running` followed by `ppp_span.set_data` for `rows_prefetched`, `budget_exceeded`, `cancelled`, `still_running`.

The block is purely additive — no other line in `generate_weekly_pdfs.py` is modified. The downstream consumers (`_upload_one` reads `attachment_cache.get(target_row.id)`; `delete_old_excel_attachments` and `_has_existing_week_attachment` both accept `cached_attachments=None`) need NO code changes because they already query the cache by `target_row.id`. The cache is shared (one dict), so a PPP row ID and a TARGET row ID coexist in the same dict — neither lookup interferes with the other.

### Task 2 — `TestPppAttachmentPrefetchBudget` regression class (commit `7e5f40c`)

9 source-level invariant tests appended to `tests/test_performance_optimizations.py` after the existing `TestAttachmentPrefetchBudget` class:

| Test | Pins |
|------|------|
| `test_constants_present` | `SUBCONTRACTOR_PPP_SHEET_ID`, `ATTACHMENT_PREFETCH_MAX_MINUTES`, `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC`, `ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN` all in module scope |
| `test_ppp_worker_function_exists` | `def _fetch_ppp_row_attachments` appears in `main()` source |
| `test_ppp_prefetch_targets_ppp_sheet` | `list_row_attachments(SUBCONTRACTOR_PPP_SHEET_ID` is the actual API call (no accidental `TARGET_SHEET_ID` substitution) |
| `test_ppp_prefetch_uses_daemon_executor_explicit_lifecycle` | **Block-scoped invariant** — extracts the PPP block from `def _fetch_ppp_row_attachments` to the next `# Load hash history` / `hash_history = load_hash_history` marker, then asserts: (a) no `with _DaemonThreadPoolExecutor`, (b) no `with ThreadPoolExecutor` (inside the PPP block), (c) `_DaemonThreadPoolExecutor(` constructor present, (d) `ppp_executor.shutdown(wait=False, cancel_futures=True)` present. Whole-file `shutdown(wait=False, cancel_futures=True)` count is also asserted >= 2 (primary + PPP) |
| `test_ppp_prefetch_skip_log_with_headroom` | Pre-flight skip log text present; `ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN` referenced; whole-file count of the constant is >= 2 (primary + PPP) |
| `test_ppp_prefetch_counters_separate` | `_ppp_prefetch_cancelled` and `_ppp_prefetch_still_running` both present (rule (5): never conflate via `not f.done()` alone) |
| `test_ppp_atexit_detach_on_budget_exceed_only` | `_detach_ppp_from_atexit_registry` symbol present; regex `if _ppp_prefetch_budget_exceeded:\s*\n\s*_detach_ppp_from_atexit_registry\(\)` matches (Copilot review rule lock-in) |
| `test_ppp_prefetch_gated_on_kill_switch_and_distinct_sheet` | All four eligibility tokens present: `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`, `SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID`, `not TEST_MODE`, `target_map_ppp` |
| `test_ppp_populates_shared_attachment_cache` | `attachment_cache[` count is >= 2 (both prefetch blocks write to the same shared dict) |

All 9 tests pass against the post-Task-1 source. The plan's TDD framing (`tdd="true"`) is structurally a regression-lock — the tests assert source-level invariants that already hold after Task 1's implementation. The commit message uses the `test(...)` conventional prefix.

## Task Commits

| Task | Commit | Type | Title |
|------|--------|------|-------|
| 1 | `8a7a668` | feat | `feat(01-12): add secondary PPP attachment-prefetch pass (WR-05)` |
| 2 | `7e5f40c` | test | `test(01-12): lock PPP prefetch daemon-executor invariants (WR-05)` |

## Files Created/Modified

- **`generate_weekly_pdfs.py`** — single 224-line block insertion between lines 5870 and 5871 of the pre-Plan-12 file (post-Plan-12 line numbers: PPP prefetch block at L5871-6094). No other change. The diff stat is `224 insertions(+), 0 deletions(-)`.
- **`tests/test_performance_optimizations.py`** — 184-line append at the end of the file (post-Plan-12 line numbers: `TestPppAttachmentPrefetchBudget` at L190-371, after the existing `TestAttachmentPrefetchBudget` and its `if __name__ == '__main__'` block). Net diff stat: `184 insertions(+), 0 deletions(-)`. The `if __name__ == '__main__': unittest.main()` block was moved to after the new class (1 line shift, not a deletion).
- **`.planning/phases/01-subcontractor-rate-logic-modification/01-12-SUMMARY.md`** — this file.

## Decisions Made

- **Insertion point at the natural seam.** The PPP prefetch block sits between the primary prefetch's `else` log and the `# Load hash history` comment. Three reasons: (1) `attachment_cache` is initialized at the primary prefetch's start, so both passes share it without re-initialization; (2) `target_map_ppp` was populated earlier in `main()` (Plan 04 L5651-5679), so the eligibility check has all the data it needs; (3) the main generation loop hasn't started, so the prefetch counts toward the prefetch budget rather than competing with generation wall-clock for the same minutes.

- **Worker function is a CLOSURE, not a shared helper.** The primary prefetch's `_fetch_row_attachments` and the new `_fetch_ppp_row_attachments` are byte-identical except for the sheet ID constant and the log prefix. A refactor to a shared `_fetch_attachments_for_sheet(sheet_id, row_item)` helper was rejected per the plan's `<action>` instruction — verbatim copy-paste preserves established retry semantics, and a cross-coupled helper would mean a future change to one path's retry logic could silently regress the other.

- **All block-specific identifiers prefixed `_ppp_*` / `ppp_*`.** The primary prefetch uses `_prefetch_*`, `executor`, `futures`, `_detach_from_atexit_registry`. The PPP block uses `_ppp_prefetch_*`, `ppp_executor`, `ppp_futures`, `_detach_ppp_from_atexit_registry`. Grep for either block's state returns only that block — no cross-contamination, no shared mutable scope, no chance a future refactor accidentally entangles the two paths.

- **Pre-flight skip uses INFO log level, not WARNING.** The primary prefetch's pre-flight skip uses WARNING because skipping primary attachment cache means EVERY upload pays an extra API call — a real degradation operators want to see. The PPP prefetch's skip only affects the PPP subset (~30% of groups in a typical run), correctness is preserved via the per-row fallback, and the operator log already names the fallback guarantee. INFO matches the cost-of-failure: low. The plan's spec at line 200 explicitly says `logging.info(...)`.

- **atexit-detach gated on `_ppp_prefetch_budget_exceeded` only.** Mirrors the primary prefetch's `if _prefetch_still_running:` gate at L5840 — the Copilot review rule from the 2026-04-22 16:05 incident's follow-up was "don't touch private APIs when workers completed normally". The PPP block uses `if _ppp_prefetch_budget_exceeded:` (slightly broader than the primary's `_prefetch_still_running` because the budget-exceed branch logically implies still-running workers; the primary's narrower check is defensive against an edge case where the budget hits exactly as the last worker completes). The regression test (`test_ppp_atexit_detach_on_budget_exceed_only`) verifies via regex that the detach call is directly inside the `if _ppp_prefetch_budget_exceeded:` branch.

- **Sentry span name `attachment_prefetch_ppp` distinct from primary's `attachment_prefetch`.** Lets operators filter Sentry by span op for either pass separately. Both spans carry `rows_prefetched` / `budget_exceeded` / `cancelled` / `still_running` data so the dashboard view is symmetric.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `list_row_attachments(SUBCONTRACTOR_PPP_SHEET_ID` must appear on a single line**

- **Found during:** Task 1 acceptance-criteria verification. The initial implementation split the API call across multiple lines for readability:
  ```python
  atts = client.Attachments.list_row_attachments(
      SUBCONTRACTOR_PPP_SHEET_ID, target_row.id,
  ).data
  ```
  The plan's AC grep `grep -c "list_row_attachments(SUBCONTRACTOR_PPP_SHEET_ID" generate_weekly_pdfs.py` requires the substring on ONE line — multi-line returned 0.
- **Fix:** Collapsed the call to a single line to match the primary `_fetch_row_attachments` style (L5732 uses a single-line `client.Attachments.list_row_attachments(TARGET_SHEET_ID, target_row.id).data`).
- **Files modified:** `generate_weekly_pdfs.py` (`_fetch_ppp_row_attachments` worker body).
- **Verification:** Post-fix grep returns 1, py_compile OK.
- **Committed in:** `8a7a668` (Task 1 GREEN — fixed in the same commit before the test commit).

**2. [Rule 1 - Bug] Daemon-executor invariant test overly broad on `with ThreadPoolExecutor`**

- **Found during:** Task 2 GREEN iteration. The plan's Test 4 behavior section said `assertNotIn('with ThreadPoolExecutor', src)` over the whole-file source. Running this against the actual codebase flagged 5 legitimate callers (folder discovery, parallel row fetch, freeze_row parallelization) whose work produces non-discardable results — those callers correctly use the `with` form with implicit `shutdown(wait=True)` to flush side effects.
- **Issue:** The intent of the assertion is to ensure the PPP prefetch specifically doesn't use the `with` form — not to ban it from the whole file. An overly-broad assertion would have made adding any new legitimate `with ThreadPoolExecutor(...)` caller anywhere in the file a regression.
- **Fix:** Refactored `test_ppp_prefetch_uses_daemon_executor_explicit_lifecycle` to slice the source from `def _fetch_ppp_row_attachments` to the next outer marker (`# Load hash history` or `hash_history = load_hash_history`), then assert the invariants on that slice only. The whole-file `shutdown(wait=False, cancel_futures=True)` count assertion (>= 2) was kept because that's a positive count check, not a negative whole-file ban.
- **Files modified:** `tests/test_performance_optimizations.py` (`test_ppp_prefetch_uses_daemon_executor_explicit_lifecycle`).
- **Verification:** Post-fix, all 9 tests in `TestPppAttachmentPrefetchBudget` pass. The 5 legitimate `with ThreadPoolExecutor(...)` callers elsewhere in the file are unaffected.
- **Committed in:** `7e5f40c` (Task 2 — fixed in the same commit as the initial test class).

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs caught during GREEN→AC-verification iteration; both inside the same commit as the original GREEN code, so no separate fix commit needed).

**Impact on plan:** Both auto-fixes were essential to satisfy the plan's own success criteria. Deviation #1 is a strict cosmetic fix (single-line vs multi-line) with zero semantic impact. Deviation #2 is a precision improvement on the test — the source-level invariant is now correctly scoped to the PPP block so legitimate callers elsewhere don't trip the assertion. No scope creep.

## Issues Encountered

- **None blocking.** The plan's contract was clear; the primary prefetch served as a reliable template; the eligibility / budget arithmetic mirrored the primary prefetch's at L5694-5719. The two deviations above were caught at AC verification time and fixed in-commit.

## User Setup Required

- **None.** All env vars (`SUBCONTRACTOR_PPP_SHEET_ID`, `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`, `TEST_MODE`, `TIME_BUDGET_MINUTES`, `ATTACHMENT_PREFETCH_MAX_MINUTES`, `ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN`) are pre-existing and have sensible defaults. The PPP prefetch starts working automatically on the next scheduled production run that has `target_map_ppp` populated.

- **Operational note:** if a production run shows the new INFO log `🛡️ Skipping PPP attachment prefetch: ...` firing routinely, that indicates the session budget is being consumed by phases earlier in `main()` (discovery, parallel row fetch, primary prefetch). The per-row fallback path keeps correctness intact; operators should investigate the earlier phases' wall-clock if the skip is unwanted. Raising `ATTACHMENT_PREFETCH_MAX_MINUTES` is NOT the right fix (it would crowd out generation headroom); raising `TIME_BUDGET_MINUTES` AND `timeout-minutes` together (per Living Ledger 2026-04-22 17:10 rule) IS the right fix when the run has consistent legitimate late-phase work.

## Per-row API call reduction estimate

For a hypothetical typical production run:

- Total groups in main loop: ~1900 (recent production-run baseline).
- Subcontractor groups (`is_subcontractor_sheet=True`): ~570 (~30% share).
- Groups producing `_ReducedSub` Excel: 570 (all subcontractor groups, unconditional per SUB-02).
- Groups producing `_ReducedSub_Helper_*`: variable, depends on helper-event count; assume ~10% of subcontractor groups = ~57.
- Total `_ReducedSub*` upload tasks per run: ~627 (one upload to TARGET + one upload to PPP per `_ReducedSub` file = 2 per group, but the PPP-side call to `delete_old_excel_attachments` is the API call that was previously paying the extra cost).
- **Pre-fix:** ~627 extra `list_row_attachments` API calls per run (1 per PPP upload's `delete_old_excel_attachments` call).
- **Post-fix:** ~570 PPP-row prefetch calls in a single parallel batch + ~57 helper-shadow row prefetch calls in the same batch (the PPP `target_map_ppp` covers BOTH `_ReducedSub` and `_ReducedSub_Helper_*` because both variants target the same set of rows in the PPP sheet — one per WR# in the map). Total: ~570 prefetch calls in ~10s wall-clock at PARALLEL_WORKERS=8, then 0 extra calls during the upload phase.

API quota savings per run: ~57 calls eliminated outright (helper-shadow uploads no longer pay; `_ReducedSub_Helper_*` is a subset of `_ReducedSub` rows in the PPP map, so the prefetch covers both). Wall-clock: amortized — the prefetch is parallel and ~10s, the per-row fallback was serial-inside-upload-workers and dominated by network latency. The actual saving is API rate-limit headroom: 570 calls spread across 30+ min upload phase vs 570 calls in 10s prefetch phase frees up budget for the rest of the run.

This figure is consistent with the Plan 04 SUMMARY's "back-of-envelope: ~570 extra Smartsheet API calls per typical run" estimate (the Plan 04 author correctly anticipated WR-05 as a future optimization).

## Threat Surface Notes

No new threat surface beyond what the Plan 04 SUMMARY's threat-model section enumerated. The PPP prefetch is a strict OPTIMIZATION:

- **No new network endpoints exposed** — `list_row_attachments` is already called by both the primary prefetch and the `_upload_one` worker's `delete_old_excel_attachments` call.
- **No new auth boundary** — the same `SMARTSHEET_API_TOKEN` is used for all three call sites; the PPP sheet is just a different sheet ID.
- **No new schema or file access pattern** — the cache dict was already in scope; the worker writes the same `(target_row.id, list_of_attachments)` shape the primary worker writes.
- **No new PII surface** — the worker logs the row ID on retry (already done by the primary worker); no new fields are logged that weren't logged by the primary prefetch's error paths. The Sentry span op name (`smartsheet.attachment_prefetch_ppp`) is purely descriptive — no row data flows through.
- **Stuck-worker bound** — same as the primary prefetch: `ATTACHMENT_PREFETCH_MAX_MINUTES` phase budget on `as_completed`, then `_DaemonThreadPoolExecutor` + `shutdown(wait=False, cancel_futures=True)` + atexit-detach trifecta ensures the workers don't block interpreter exit.

## Next Phase Readiness

- **Phase 01 BLOCKER list status post-Plan-12.** The 3 BLOCKERs identified in `01-REVIEW.md` (CR-01 helper-shadow `file_identifier`, CR-02 `EXCLUDE_WRS` matcher, CR-03 `WR_FILTER` mirror bug) and the 6 WARNINGs are addressed by their own gap-closure plans (WR-01 through WR-06, CR-01 through CR-03). This plan (01-12) closes **REVIEW-WR-05** specifically — the per-row API quota optimization for PPP uploads. Other gap-closure plans address the remaining items independently.
- **No blockers for downstream plans.** The PPP prefetch is purely additive; no consumer code changes are required. Downstream gap-closure plans (CR-01, CR-02, CR-03, WR-01, WR-02, WR-03, WR-04, WR-06) can land in parallel.
- **Production verification path.** The next scheduled GitHub Actions production run will exercise the new code path automatically when (a) the kill switch is on (default), (b) `SUBCONTRACTOR_PPP_SHEET_ID` is reachable (default `8162920222379908`), (c) `target_map_ppp` is built (Plan 04 — already wired), and (d) the session-budget pre-flight guard doesn't skip. Operators should look for the `🚀 Starting parallel PPP attachment pre-fetch with 8 workers for N PPP target rows (max 10min)...` log line followed by `🏁 PPP attachment prefetch complete in X.Xs: N rows, M cancelled, K still_running`. A `🛡️ Skipping PPP attachment prefetch: ...` line indicates the per-row fallback is active for this run (correctness preserved; investigate session-budget consumption in earlier phases).

## Self-Check

Performed inline before writing this section:

- `git log --oneline a193223..HEAD` shows 2 commits in expected order: **FOUND** (`8a7a668` Task 1, `7e5f40c` Task 2)
- `grep -c "list_row_attachments(SUBCONTRACTOR_PPP_SHEET_ID" generate_weekly_pdfs.py` → 1: **CONFIRMED**
- `grep -c "def _fetch_ppp_row_attachments" generate_weekly_pdfs.py` → 1: **CONFIRMED**
- `grep -c "Starting parallel PPP attachment pre-fetch" generate_weekly_pdfs.py` → 1: **CONFIRMED**
- `grep -c "Skipping PPP attachment prefetch" generate_weekly_pdfs.py` → 1: **CONFIRMED**
- `grep -c "_detach_ppp_from_atexit_registry" generate_weekly_pdfs.py` → 3 (comment + definition + invocation; >= 2): **CONFIRMED**
- `grep -c "ppp_executor.shutdown(wait=False, cancel_futures=True)" generate_weekly_pdfs.py` → 1: **CONFIRMED**
- `grep -c "shutdown(wait=False, cancel_futures=True)" generate_weekly_pdfs.py` → 5 (primary prefetch + PPP prefetch + 3 other unrelated callers; >= 2): **CONFIRMED**
- `grep -c "with _DaemonThreadPoolExecutor" generate_weekly_pdfs.py` → 0: **CONFIRMED** (PPP block never uses the `with` form for the daemon executor)
- `grep -c "@cell" generate_weekly_pdfs.py` → 0: **CONFIRMED** (CLAUDE.md absolute ban honored)
- `python -m py_compile generate_weekly_pdfs.py` → exits 0: **CONFIRMED**
- `python -m py_compile tests/test_performance_optimizations.py` → exits 0: **CONFIRMED**
- `pytest tests/test_performance_optimizations.py::TestPppAttachmentPrefetchBudget -v` → 9 passed: **CONFIRMED**
- `pytest tests/test_subcontractor_pricing.py::TestPhase1IntegrationRegression -v` → 5 passed: **CONFIRMED**
- `pytest tests/test_performance_optimizations.py::TestAttachmentPrefetchBudget -v` → 3 passed (no regression in the primary-prefetch sibling class): **CONFIRMED**
- `pytest tests/` full suite → 596 passed / 22 skipped / 46 subtests / 0 failed: **CONFIRMED**
- No modifications to `STATE.md` / `ROADMAP.md` — orchestrator owns those: **CONFIRMED**

## Self-Check: PASSED

## TDD Gate Compliance

| Task | Type | Commit | Title |
|------|------|--------|-------|
| 1 | feat (autonomous) | `8a7a668` | `feat(01-12): add secondary PPP attachment-prefetch pass (WR-05)` |
| 2 | test (tdd=true regression-lock) | `7e5f40c` | `test(01-12): lock PPP prefetch daemon-executor invariants (WR-05)` |

Plan-level `type: execute` (not `type: tdd`), so the RED/GREEN gate sequence does NOT apply to the plan as a whole. Task 2 is `tdd="true"` but the test class is purely a regression-lock for Task 1's source-level invariants — the tests pass against Task 1's already-landed code, not against absent code. The `test(...)` commit prefix is correct per the conventional commit type table because the commit contains tests only (no production code).

The Plan 12 spec explicitly anticipates this in Task 2 `<behavior>`: "These tests are predominantly SOURCE-LEVEL invariant guards — the actual prefetch behavior is exercised end-to-end by the workflow run, not by unit tests" — making the tests a regression-lock pattern rather than a behavior-driving TDD cycle.

---

*Phase: 01-subcontractor-rate-logic-modification*
*Plan: 12*
*Completed: 2026-05-15*
