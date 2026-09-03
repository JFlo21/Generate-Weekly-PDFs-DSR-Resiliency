Repo-local implementation truth — outranks second-brain notes; verified from repo files on 2026-09-02.

<!-- This file is repo-local IMPLEMENTATION TRUTH. Only list bugs REPRODUCED/observed against real code. -->

# Known Bugs — Generate-Weekly-PDFs-DSR-Resiliency-1

## Source-of-truth hierarchy (highest authority first)

1. Current repo files. 2. Repo-local `docs/ai/` + `.claude/project-state.md`. 3. Repo-local handoff
docs. 4. Global second brain. 5. Global wiki. 6. `raw/` (data only). 7. Chat history / claude-mem.

---

## Bug register

| id | description | severity | area | status | last-checked |
|---|---|---|---|---|---|
| CR-01 | `pipeline/cleanup.py:89-116` `_is_sentinel_identifier` treats ANY filename identifier token starting with `_` as a sentinel placeholder. `_RE_SANITIZE_HELPER_NAME` (`pipeline/config.py:28`) is applied without a strip in `pipeline/excel.py:308/324`, so a real foreman name with a leading space/punctuation also sanitizes to a leading `_`. Feeds the sentinel-superseded attachment-cleanup gate (`pipeline/cleanup.py:495-508`), which could delete a real person's historical attachment. Identified during Phase 11.1 code-quality review (Codex on PR #377 / gsd code reviewer). | medium | `pipeline/cleanup.py` (protected attachment-cleanup path) | open — planned fix in Phase 12 Plan 12-02 | 2026-09-02 |
| WR-01 | `pipeline/orchestrate.py:44` imports `AttachmentParentType` from `smartsheet.models.enums.attachment_parent_type` at module top level, unlike `pipeline/discovery.py`'s lazy, guarded import of the same SDK-internal path (used at `orchestrate.py:1287-1297`). Inconsistent import pattern; risk if the internal SDK path moves/renames in a future SDK version. | low | `pipeline/orchestrate.py` | open — planned fix in Phase 12 Plan 12-02 (align to lazy pattern) | 2026-09-02 |
| OWN-01/03/04 (tracked, not a bug) | Phase 12 ownership backfill (claim-time / as-of-the-week foreman resolution for ~93 `Unknown Foreman` WRs) is planned but not yet executed — see `.planning/ROADMAP.md` Phase 12 and `memory-bank/living-ledger.md [2026-09-02 19:25]`. Not a code defect; listed here because it is an explicitly open item affecting billing attribution correctness. | — | `billing_audit/writer.py`, backfill scripts (not yet created) | in-progress — plans 12-01..12-06 not started | 2026-09-02 |

## Notes

- CR-01 and WR-01 were both surfaced by the Phase 11.1 advisory code-quality report
  (`11.1-REVIEW.md`) and are deliberately NOT auto-fixed because CR-01 sits inside protected
  OWN-02 attachment-cleanup code and WR-01 touches the same review-swept range
  (`memory-bank/living-ledger.md [2026-09-02 17:45]`).
- No other open defects were surfaced in the files read this pass. A full bug sweep was NOT
  performed (out of scope per the token-discipline read list); do not treat this register as
  exhaustive.

## Last verified

- Last verified: 2026-09-02 — read `pipeline/cleanup.py:89-120` (full `_is_sentinel_identifier`
  function) and `pipeline/orchestrate.py` import block + usage grep for `AttachmentParentType`;
  cross-checked against `memory-bank/living-ledger.md` `[2026-09-02 17:45]` and `.planning/ROADMAP.md`
  Phase 12 plan list (`12-02-PLAN.md` scope line). Both CR-01 and WR-01 confirmed still present in
  code (not yet fixed as of this read).
