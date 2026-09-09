# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-09-08 21:30 CDT (2026-09-09 02:30Z) · **overwrite-in-place each session** — this is
the canonical "where the project stands" landing spot for the global Stop write-back reminder. Cap ≤ 120
lines (`align-instruction-files` skill); history goes to `memory-bank/living-ledger.md`, never here._

## Where it stands

- **Milestone v1.4 "Supabase Run Memory"**: Phases 10 (2026-08-25), 11 (2026-08-31), and 11.1 (2026-09-02,
  PR #384 `13e8e76`) are closed. Production posture: `pipeline_memory` write path ON since PR #353
  (`RUN_MEMORY_WRITE_ENABLED='1'` on the `Generate reports` step only); `RUN_MEMORY_INCREMENTAL_ENABLED` OFF;
  change detection and attachment identity are `group_state`-backed; `TIME_BUDGET_MINUTES=165` under
  `timeout-minutes: 180`.
- **Phase 12 (Ownership)**: waves 1–3 plus gap closure (plans 12-01..12-10) merged via PR #387 and PR #388;
  the live attribution backfill is applied (1,758 rows updated, read-back clean). **12-06 Task 4** (first
  post-apply scheduled-run check) is still owed — pointer `.planning/HANDOFF.json`. Phase 13 (the deferred
  `wr_week_ownership` table, D-12-A) has not started.
- **Phase 14 (Foreman Helper #2)**: 11/11 plans executed; PR #389 squash-merged to master `ba6eeaf`
  (2026-09-09 01:37Z) as a documented-only rollout. Gap-closure plan 14-12 is now IN PROGRESS on PR #390 —
  see the section below.
- **GSD tooling**: HEALTHY as of 2026-09-06 (gsd-core 1.13.0 via the marketplace plugin); a forbidden npm
  reinstall that session was fully rolled back — never accept the npm install prompt on this machine.
- **CI noise**: `code/snyk` ("Code test limit reached") and the Azure DevOps mirror build fail on every PR
  (same on merged #388/#389); master carries no required checks.

## Phase 14 — Foreman Helper #2

- **Status**: 11/11 plans executed; PR #389 squash-merged to master `ba6eeaf` at 2026-09-09 01:37Z as a
  documented-only rollout (`D-14-12-ROLLOUT`: `HELPER2_ENABLED` default `'0'`, workflow unwired at merge).
  `14-VERIFICATION.md` = `passed` 7/7 after the 14-12 addendum (HLP-06 closed). Post-merge work continues on
  `chore/phase-14-post-merge`; **PR #390 is open** (docs + plan 14-12).
- **Plan 14-12 (gap closure) — IN PROGRESS**: Task 1 done — `1563199` lockstep test proving
  `upsert_rows_bulk`'s lists ⊇ `HASH_FIELDS`; `cf556d8` RPC text + `pipeline_memory/helper2_columns_migration.sql`
  + `14-12-PLAN.md`. **Task 2 APPLIED** 2026-09-09 02:21:29Z as Supabase migration
  `20260909022129_helper2_row_state_columns_marker_and_rpc` (adds `row_state.helper2_observed/completed/dept/job`
  + `sheet_registry.mapping_schema`; `upsert_rows_bulk` now carries the four fields; grants and `search_path`
  unchanged; pre-state parked in the vault `raw/` folder). **Task 2 VERIFIED** 02:22–02:27Z (`D-14-13-VERIFIED`:
  columns, function text, grants, synthetic insert / no-op resend / update round-trip on sheet_id `-14012`, rows
  deleted). **Task 3 IN PROGRESS**: workflow env line `HELPER2_ENABLED: ${{ vars.HELPER2_ENABLED || '0' }}` added,
  runbook + environment docs flipped, records `D-14-13-DDL-APPLIED`/`VERIFIED`, `O-14-B RESOLVED`,
  `O-14-A-FOLLOWUP-1 CONFIRMED`, `D-14-14-ENABLE` written, HLP-06 Complete; next: commit, push, retitle and merge
  PR #390, then `gh variable set HELPER2_ENABLED --body 1`.
- **Owner instruction** (Juan, 2026-09-08): apply both DDLs, close O-14-B, confirm Follow-up 1, "then enable
  the helper 2 once these issues are fixed".
- **First scheduled run on merged code** is the Tue 2026-09-09 13:00Z slot (the 01:00Z run `34299267004`
  ran pre-merge on `bc2de79`, success). Expect a one-time ~217k `row_event` churn from the `HASH_FIELDS`
  change, one full validation per sheet then `mapping_schema` markers written (no degrade warning — the
  column now exists), 14-param `freeze_attribution` OK, and Helper #2 counters at 0 (Resource Analyst
  Helper #2 column is blank on all 576 rows).

## Live Supabase state

- **billing_audit**: migrations `20260908165511` (attribution columns + RPCs) and `20260908201205`
  (per-role Helper #2 fill) remain live.
- **pipeline_memory**: migration `20260909022129_helper2_row_state_columns_marker_and_rpc` is live
  (14-12 Task 2) — adds the `row_state` Helper #2 columns and `sheet_registry.mapping_schema`; read back
  clean (`D-14-13-VERIFIED`).
- **Phase 12 attribution**: live backfill applied 2026-09-05 (1,758 rows); snapshot backups
  `_20260903`/`_20260904`/`_20260905` retained until 12-06 Task 4 verifies the post-apply run.

## Open items / owner decisions

- **O-14-B** (`upsert_rows_bulk` RPC gap): RESOLVED 2026-09-09 (`D-14-13-VERIFIED`).
- **O-14-A Follow-up 1** (per-slot Helper #2 duplication): CONFIRMED by Juan 2026-09-08 (`O-14-A-FOLLOWUP-1`).
- **12-06 Task 4**: first post-apply scheduled-run check still owed — pointer `.planning/HANDOFF.json`.
- **HELPER2_ENABLED**: wired, variable-driven (`D-14-14-ENABLE`); the repo variable flips to `1` right after
  PR #390 merges. Repo default stays `'0'`.

## Next actions

1. Commit 14-12 Tasks 2–3 + the Greptile condensation, push, retitle PR #390 as the 14-12 feature PR, wait
   for CI, squash-merge.
2. `gh variable set HELPER2_ENABLED --body 1` right after the merge; confirm with `gh variable list`.
3. Watch the Tue 2026-09-09 13:00Z scheduled run: one-time `row_event` churn, Helper #2 counters present,
   no degrade warning, no `_Helper2_` workbook (RA column blank). Then `/gsd-code-review 14`.
5. Phase 12: run 12-06 Task 4 (first post-apply scheduled-run check).

## Risks and guardrails

- No Smartsheet write, workflow, or schedule change without Juan.
- Supabase DDL/RPC changes only under owner approval or explicit delegation.
- Synthetic dry runs must blank the token — `TEST_MODE=true` with a real token performs a live read of
  every source sheet.
- `PARALLEL_WORKERS ≤ 8` (Smartsheet 300 req/min).
- Never shorten the change-detection key `(WR, week_ending, variant, foreman, dept, job)`.

## Pointers

- Ledger: `memory-bank/living-ledger.md` (dated entries — grep, never load the whole file).
- Changelog: `docs/CHANGELOG_CONTEXT.md`.
- Roadmap: `.planning/ROADMAP.md`.
- Decisions: `docs/DECISIONS.md`, `.planning/phases/14-foreman-helper-2/14-DECISIONS.md`.
- Runbook: `website/docs/runbook/foreman-helper-2.md`.
- Handoff: `.planning/HANDOFF.json` (Phase 12 12-06 Task 4 resume pointer).
