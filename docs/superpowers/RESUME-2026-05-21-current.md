# RESUME — 2026-05-21 (current state, robust handoff)

> Written because claude-mem install set `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`
> (disables Claude Code built-in auto-memory) and claude-mem's own memory has
> no data for this session yet. This repo doc is the authoritative handoff.
> Also see the `memory/` files under the Claude projects dir if still loaded.

## Git / PR state
- **PR #216** (helper-completed exclusion hotfix) — MERGED to master (`d1b6c54`).
- **PR #215** (Subproject B, branch `feat/subproject-b-primary-claim-attribution`)
  — reviewed clean, reconciled with #216 (merge `5535f7b`, head `af92ae9`),
  **mergeable**, suite 753 passed / 26 skipped / 58 subtests. NOT yet merged.
- Decision: **user merges PR #215 first**, THEN Sub-project C off the updated master.

## What just shipped
- Subproject B = subcontractor PRIMARY variants (`reduced_sub`/`aep_billable`)
  re-partitioned by frozen primary claimer (`_ReducedSub_User_<name>` /
  `_AEPBillable_User_<name>`) via Foundation A `resolve_claimer` + HOLD.
- Helper-exclusion fix: helper-COMPLETED subcontractor rows (Units Completed?
  AND Helping Foreman Completed Unit? both checked) are EXCLUDED from primary
  files — they belong solely to `_*_Helper_<name>` shadow files. Guard =
  `_sub_is_valid_helper_row` in `group_source_rows`.

## IN PROGRESS — UAT (paused for context/plugins)
Conversational UAT, tracked in `docs/superpowers/2026-05-21-subproject-b-helper-exclusion-UAT.md`.
4 tests. **Test 1 was presented, awaiting operator's plain-text answer:**
"Does a helper-completed line item appear ONLY in `_ReducedSub_Helper_*` /
`_AEPBillable_Helper_*`, NOT in the primary file?" (scope = master/production,
hotfix #216 merged — validatable now). Tests 2-4 need a run of the B branch
(`_USER_` partitioning is on B only, not master). Resume by re-presenting Test 1.

## DONE this session (uncommitted on the B branch)
- **Dept # population** (operator requirement 2026-05-21) — FIXED. Root cause:
  `generate_excel`'s REPORT DETAILS display-value selector gated helper display
  on the bare `if variant == 'helper'` (exact match), so `reduced_sub_helper` /
  `aep_billable_helper` fell through to the `else` (primary) branch and showed
  the PRIMARY `Dept #` / `Job #`. Fix: added an `elif variant in
  ('reduced_sub_helper','aep_billable_helper'):` branch sourcing `__helper_dept`
  / `__helper_job`, keeping `display_foreman = current_foreman` (the attributed
  helper — folding into the `helper` branch would have regressed foreman to the
  current `__helper_foreman`). Foreman was already correct. Scope: Dept # AND
  Job # (operator-approved). Tests: `TestSubcontractorHelperVariantDeptJobDisplay`
  (4 methods, drives real `generate_excel` + reopens workbook). `pytest tests/`
  → 757 passed / 26 skipped / 60 subtests. Living Ledger entry [2026-05-21 12:35]
  appended. **Not committed** — awaiting your go-ahead.

## QUEUED — not started
- **Sub-project C** = re-partition vac_crew Excel files by the FROZEN vac-crew
  claimer (`frozen_vac_crew` via Foundation A `resolve_claimer`), same shape as B.
  Start with brainstorming → spec → plan → superpowers subagent-driven-development.
  Branch off post-B-merge master. Then D (primary-workflow primary) → E
  (Supabase hash-store + filename token stripping).

## Tooling notes
- `/gsd-code-review` and `/gsd-verify-work` do NOT work on superpowers-plan
  branches (they require a `.planning/phases/` GSD phase). Use ad-hoc reviewer
  agents / conversational UAT instead.
- Plugins installed this session: **context-mode** (v1.0.146) + **claude-mem**
  (v13.3.0). Both activate on Claude Code restart. claude-mem worker: start with
  `npx claude-mem start` (web viewer http://localhost:37777). Both have
  hooks — watch for overlap.
- Stray branches `codex-helper-generation-analysis` / `codex-helper-generation-bug`
  are redundant (safe to `git branch -D`).
