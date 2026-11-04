# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-11-03 (Foreman Notes pilot LIVE; PR #447 corrections open; fail-closed notes-token
fix and doc alignment in flight) · **overwrite-in-place each session** — the canonical "where the project
stands" landing spot for the global Stop write-back reminder. Cap ≤ 120 lines (`align-instruction-files`);
history goes to `memory-bank/living-ledger.md` (grep the dated header), never here._

## Where it stands

- PR #451 `fix/corrections-load-fail-closed` (stacked on #447; retarget to master after #447 merges):
  `REPORTING_CORRECTIONS_FILE` set but unloadable now stops the run (ERROR check-in, exit 1) instead of
  running feature-off and double-billing an applied correction. Owner hand steps: paste the runbook
  "Stage reporting corrections" step into the workflow (hook-blocked in-session), create the secret, set
  `REPORTING_CORRECTIONS_REQUIRED=true` while a correction is applied. Merge order: #449 → #447 → #451 → #450.
- 2026-11-04 drift-check repairs (docs PR #449): `docs/ai/` pages back under 130 lines (hierarchy →
  context-map pointer, history → ledger), `.agents/skills` mirror resynced, nested hook output ignored,
  `.serena/project.yml` tracked. Open: track or ignore `.agents/`; `.planning/state.json` +
  `.continue-here.md` are GSD-owned (commit via `/gsd:*`); `/gsd:health` skipped while Phase 15 is live.
- **Production posture (milestone v1.4 "Supabase Run Memory")**: Phases 10, 11.1, 12, 14 closed;
  `pipeline_memory` write path ON (`RUN_MEMORY_WRITE_ENABLED='1'` on the `Generate reports` step only);
  `RUN_MEMORY_INCREMENTAL_ENABLED` OFF; change detection and attachment identity are `group_state`-backed;
  `TIME_BUDGET_MINUTES=165` under `timeout-minutes: 180`. Repo variables: `HELPER2_ENABLED=1` (since
  2026-09-09, permanent; flag-off is an emergency kill switch only, O-14-D), `FOREMAN_NOTES_UPLOAD=1`
  (since 2026-10-31, read back 2026-11-03; rollback `gh variable set FOREMAN_NOTES_UPLOAD --body 0`).
- **Phase 15 Foreman Notes pilot — LIVE (2026-10-31)**: #437 (`85fac23a`), #444 (`cf4fc14e`, hold pilot
  groups on GF-lookup failure + Sentry upgrade) and #445 (`d589eded`, scope `pilot`, secret allowlist)
  merged. Run 41681444921 (2026-11-03 17:09Z) logged `allowlist=3 gf_rows=920 pilot_wrs=289`; the 8 runs
  from 2026-11-02 19:08Z through 2026-11-03 19:07Z all succeeded (read 21:00Z). Sentry: zero foreman-notes
  errors in 7 days; `GENERATE-WEEKLY-EXCEL-AK` is the pre-existing `A3` data-entry alert under a new
  fingerprint after the #444 upgrade, not a regression. GF-lookup churn todo closed by the #444 hold
  (`.planning/todos/done/2026-10-30-foreman-notes-gf-lookup-failure-churns-pilot-groups.md`); reusing
  the last known pilot set on lookup failure stays an owner option.
- **Foreman Notes token fail-open (found 2026-11-03)**: a `group_notes_token` failure returns `""`, so
  the `NOTES_FP` meta token is dropped and the group fingerprints as "no notes" (hash + hold path only;
  run reporting already counts it as `digest_failures`). Fix in progress on branch
  `fix/foreman-notes-token-fail-closed` (worktree `gwp-fntoken`, from `13a1dcb1`) — **draft PR #450**
  (`3ec49835` fix, `d70adf6b` tests-only round): per-run token-failure registry keyed by sorted (sheet,
  row, variant) triples; main() holds the pilot group like a GF-lookup hold, never in TEST_MODE; hashes
  byte-identical to master; WR list only on the `notes_digest_failed` event. pytest 2875 / 3 skipped, 6
  gates, Opus production-risk review merge-safe. **Owner decision**: `RESET_*` purge runs before the hold,
  so a reset covering a pilot WR whose token fails leaves the row without a workbook until the token
  recovers (regenerate instead, or document "re-run RESET after recovery").
- **WR 91006877 reporting correction — PR #447** (branch `fix/wr-91006877-reporting-correction`, worktree
  `gwp-corr`, starts at `c5536351`, head moves with review fixes; owned by its own session — one writer per
  branch): opt-in `pipeline/reporting_corrections.py` (exact `(sheet_id, row_id)` re-credit; `$0.00` rows
  reconcile-only), `CORR=` hash token, runbook page `website/docs/runbook/reporting-corrections.md` (on the
  branch). Ready for review and approved; review rounds 1-3 (`157f3506`, `4e3e2290`, `8bceceaa`): cleanup
  held on failed or partial sheet reads and gated on `RES_GROUPING_MODE=both` + claim attribution on;
  helper/VAC/legacy-owner cases BLOCK rather than mis-credit; logs carry field names only. Validation at
  `8bceceaa`: pytest 2928 passed / 3 skipped; 6 gates; CodeQL clean. **Owner decisions**: may a correction
  override the VAC duplicate-unit rule (blocked today); primary owner change under legacy grouping
  (blocked today). **Owner gates**: workflow step + `REPORTING_CORRECTIONS_JSON_B64` secret (separate
  PR), covering-helper choice.
- **Docs**: PR #448 (`docs/state-2026-11-03`) refreshes this file to the post-#444 state — ready to merge.
  Draft PR #449 (`docs/claudeos-doc-alignment`, stacked on #448) ran `align-instruction-files`: this cut,
  `paths:`-scoped rules, compaction guidance in `CLAUDE.md`, mirror regen (ledger `[2026-11-03 20:30]`).
- **QUAR-01 plan (2026-10-30)**: `.planning/todos/pending/2026-10-30-close-quar-01-incremental-collision-gap-and-enforce-flag-gat.md`
  — enforce the incremental gate in code without a schema change. Not implemented. PRs #439, #442, #443
  merged 2026-10-30.
- **Phase 11 (incremental read)**: NOT marked complete. Selector fix merged as PR #409; `11-VERIFICATION.md`
  = `human_needed` 6/8 — the open item is ≥5 clean post-fix `production_frequent` runs (`11-UAT.md` test
  37); G-11-37 first-run check passed 2026-10-30 (ledger `[2026-10-30 07:20]`). Nyquist + security gates
  closed 2026-09-12. WR-01 (`_is_abbreviated_response` zero-row delta) still an owner decision.
- **Phase 13 (Audit Memory)**: executed on `plan/phase-13` (27 commits; not pushed, no PR); DDL live as
  migration `audit_memory_findings_lifecycle_views`; `acknowledge_finding` grant applied live 2026-10-30;
  Nyquist + security gates closed 2026-09-12; `13-UAT.md` blocked on a release build (`AUDIT_MEMORY_ENABLED`
  not wired into the workflow env). Next: PR `plan/phase-13` → wire the flag shadow-first → ≥2 runs.
- **v1.4 milestone re-audit (2026-09-13, `859c98c`)**: `gaps_found` 19/23 — sole blocker is Phase 11
  verification; SECURITY.md complete for 11, 11.1, 12, 13, 14. Report `.planning/v1.4-MILESTONE-AUDIT.md`.
- **Tooling notes**: GSD healthy (gsd-core 1.13.0) — never accept the npm reinstall prompt on this machine;
  claude-mem restored from the marketplace checkout 2026-09-11 (re-copy from
  `~/.claude/plugins/marketplaces/thedotmack/plugin` if hooks stop capturing).
- **CI noise**: `code/snyk` ("Code test limit reached") and the Azure DevOps mirror build fail on every PR
  and master commit; master carries no required checks. Diagnosis of the mirror pipeline is an owner item.

## Live Supabase state

- **billing_audit**: migrations `20260908165511` (attribution columns + RPCs) and `20260908201205`
  (per-role Helper #2 fill) live; Phase 12 attribution backfill applied 2026-09-05 (1,758 rows), snapshot
  backups dropped 2026-09-10 (live table 224,371 rows).
- **pipeline_memory**: migration `20260909022129_helper2_row_state_columns_marker_and_rpc` live
  (`row_state` Helper #2 columns, `sheet_registry.mapping_schema`); `audit_memory_findings_lifecycle_views`
  live (Phase 13). Rollback references parked in the owner's vault `raw/` folder. The repo never applies DDL.

## Open items / owner decisions

- Merge PR #448 (docs/state) and PR #447 (corrections; owner gates above stay out of it).
- PR #450 (fail-closed notes-token hold): mark ready + merge on owner call; decide the RESET-purge interaction.
- Branch/worktree hygiene inventory (2026-11-03): 22 gone-upstream + 9 merged tracked branches; worktrees
  `gwp-1115`, `gwp-mermaid`, `gwp-regen` idle — deletions only on owner approval.
- Owner statement 2026-11-03: `AGENTS.md` is Claude-owned, not Codex-owned. The global ClaudeOS rule
  (`~/.claude/rules/production-guardrails.md` harness boundary) and `hooks/harness-boundary-guard.js` still
  say Codex-owned; amending them is a global, owner-approved change, then a repo PR fixes the mirrored wording
  (`.claude/skills/align-instruction-files/SKILL.md`, `.claude/context-map.md`, `docs/AI_CONTEXT_RESUME.md`).
- Codex comments on PR #449 (listed, never applied — harness boundary): changelog rule scoping (same point as
  Greptile, fixed); context-map Python-rule scope (fixed via Copilot); P1 asks to restore the `keep_historical`
  cleanup gate line (`14-DECISIONS.md` 723-730) that this cut dropped — owner call to restore one line.
- Phase 11 test 37 streak reading; Phase 13 PR; Codex threads on PRs #399/#400/#402; Dependabot triage.

## Next actions

1. Owner: merge in order PR #448 → #449 (docs), then #447 (corrections), then #450 (token hold; rebase if
   `orchestrate.py` conflicts with #447). `AGENTS.md` frozen 2026-11-03 (owner-approved, `32c6e7ff`).
2. Follow PR #450 bot reviews (Copilot/Greptile/Cursor; Codex comments are listed, never applied).
3. Owner: PR #447 gates (workflow step + secret PR, VAC override, legacy-owner change, covering-helper).
4. Phase 11 test 37 → re-verify → validate-phase 11.1/12/14 → v1.4 re-audit; Phase 13 PR when asked.

## Risks and guardrails

- No Smartsheet write, workflow, or schedule change without Juan. Supabase DDL/RPC only under owner
  approval or explicit delegation. Never push to `master`.
- Synthetic dry runs must blank the token — `TEST_MODE=true` with a real token reads every source sheet live.
- `PARALLEL_WORKERS ≤ 8` (Smartsheet 300 req/min). Never shorten the change-detection key
  `(WR, week_ending, variant, foreman, dept, job)`.
- One writer per branch/worktree: a second session on the same checkout overwrites the first.

## Pointers

- Ledger: `memory-bank/living-ledger.md` (dated entries — grep, never load the whole file).
- Changelog: `docs/CHANGELOG_CONTEXT.md` · Decisions: `docs/DECISIONS.md` (stub),
  `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`.
- Roadmap / GSD position: `.planning/ROADMAP.md`, `.planning/STATE.md`.
- Runbooks: `website/docs/runbook/foreman-helper-2.md`, `foreman-notes-pilot.md`.
