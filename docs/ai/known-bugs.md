Repo-local implementation truth — outranks second-brain notes; verified from repo files on 2026-10-29.

<!-- This file is repo-local IMPLEMENTATION TRUTH. Only list bugs REPRODUCED/observed against real code. -->

# Known Bugs — Generate-Weekly-PDFs-DSR-Resiliency-1

## Source-of-truth hierarchy (highest authority first)

1. Current repo files. 2. Repo-local `docs/ai/` + `.claude/project-state.md`. 3. Repo-local handoff
docs. 4. Global second brain. 5. Global wiki. 6. `raw/` (data only). 7. Chat history / claude-mem.

---

## Bug register

| id | description | severity | area | status | last-checked |
|---|---|---|---|---|---|
| CR-01 | **Historical (was):** `_is_sentinel_identifier` treated ANY filename identifier token starting with `_` as a sentinel placeholder. `_RE_SANITIZE_HELPER_NAME` (`pipeline/config.py:28`) is applied without a strip in `pipeline/excel.py:308/324`, so a real foreman name with a leading space/punctuation also sanitizes to a leading `_`, which fed the sentinel-superseded attachment-cleanup gate and could delete a real person's historical attachment. Identified during Phase 11.1 code-quality review (Codex on PR #377 / gsd code reviewer). **Fix:** `_is_sentinel_identifier` (`pipeline/cleanup.py:116`) now narrows the leading-underscore branch to the `_SANITIZED_ERROR_IDENTIFIERS` allowlist (`pipeline/cleanup.py:98`) plus `is_sentinel_claimer`; `_is_real_name_identifier` (`pipeline/cleanup.py:170`) was added, and the sentinel-superseded gate (`pipeline/cleanup.py:585`) also requires a real-name sibling. Landed in commit `1f159bc` (PR #388), Phase 12 Plan 12-02. | medium | `pipeline/cleanup.py` (protected attachment-cleanup path) | fixed — Phase 12 Plan 12-02 (commit `1f159bc`, PR #388) | 2026-10-29 |
| WR-01 | **Historical (was):** `pipeline/orchestrate.py` imported `AttachmentParentType` from `smartsheet.models.enums.attachment_parent_type` at module top level, the only import of that SDK-internal enum path anywhere in `pipeline/`. **Fix:** the import is now function-local in a `try/except` (`pipeline/orchestrate.py:1352`, consumer at `:1357`) with `_warn_attachment_parent_type_fallback` (`:1307`); no module-top-level import remains. The rest of the package wraps SDK model imports in lazy, guarded imports (`pipeline/discovery.py` does so for `Sheet` / `Folder` from `smartsheet.models`) — that is the pattern WR-01 should align to. Risk if the internal SDK path moves/renames in a future SDK version. **Corrected 2026-09-02:** earlier wording (also in ledger `[2026-09-02 17:45]` and `12-02-PLAN.md` line 25) wrongly said discovery.py lazily imports the *same* enum path; it never imports `AttachmentParentType` at all. | low | `pipeline/orchestrate.py` | fixed — Phase 12 Plan 12-02 (function-local lazy import) | 2026-10-29 |
| OWN-01/03/04 (tracked, not a bug) | Phase 12 ownership backfill (claim-time / as-of-the-week foreman resolution for ~93 `Unknown Foreman` WRs) was planned in Phase 12 and is now complete — see `.planning/ROADMAP.md` Phase 12 (completed 2026-09-10) and `memory-bank/living-ledger.md [2026-09-02 18:15]` (planning entry). Not a code defect; kept here as history because it affects billing attribution correctness. | — | `billing_audit/writer.py`, `scripts/backfill_claim_time_attribution.py`, `scripts/backfill_attribution_snapshot.py`, `scripts/backfill_cell_history_attribution.py` | complete — Phase 12 plans 12-01..12-10 done (2026-09-10) | 2026-10-29 |
| QUAR-01 (gate, flag OFF) | The source WR collision pre-scan in `main()` reads `groups` AFTER `_filter_groups_to_affected`, so an incremental run sees only the affected pairs. Two raw WRs that fold to one sanitized key in different weeks are not quarantined if only one is in scope, and that group uploads against a shared `target_map` key. Unreachable while every run is full. Must be fixed (scan the unfiltered groups) before `RUN_MEMORY_INCREMENTAL_ENABLED` defaults on. Read from code; not reproduced. | high when flag on | pipeline/orchestrate.py | open | 2026-10-30 |

## Notes

- CR-01 and WR-01 were both surfaced by the Phase 11.1 advisory code-quality report
  (`11.1-REVIEW.md`) and were deliberately NOT auto-fixed at the time because CR-01 sits inside
  protected OWN-02 attachment-cleanup code and WR-01 touches the same review-swept range
  (`memory-bank/living-ledger.md [2026-09-02 17:45]`). Both are now fixed (Phase 12 Plan 12-02).
- No other open defects were surfaced in the files read this pass. A full bug sweep was NOT
  performed (out of scope per the token-discipline read list); do not treat this register as
  exhaustive.

## Last verified

- Last verified: 2026-10-29 — re-read `pipeline/cleanup.py` (`_SANITIZED_ERROR_IDENTIFIERS` at
  line 98, `_is_sentinel_identifier` at 116, `_is_real_name_identifier` at 170, sentinel-superseded
  gate at ~585) and `pipeline/orchestrate.py` (function-local `AttachmentParentType` import at
  ~1352, consumer ~1357); cross-checked against `.planning/ROADMAP.md` (Phase 12 completed
  2026-09-10). CR-01 and WR-01 confirmed fixed in code; OWN-01/03/04 complete. Earlier read
  (2026-09-02) had both as open.
