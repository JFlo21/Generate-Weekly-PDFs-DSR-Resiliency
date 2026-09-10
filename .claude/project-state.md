# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-09-10 15:40 CDT (2026-09-10 20:40Z) · **overwrite-in-place each session** — this is
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
- **Phase 14 (Foreman Helper #2)**: COMPLETE 2026-09-10 — 14/14 plans executed and observed; O-14-E RESOLVED.
  PR #389 → `ba6eeaf`, #390 → `661d6d3`, #394 → `7ded60c`, #395 → `d079e81`, #396 → `736141a`, #397 → `92c9ed6`,
  closure PR #398 → `45bdbbf`; code review report PR #399 → `94f2636` (`14-REVIEW.md`, standard depth, 71 files: 2 Critical / 3 Warning / 1 Info — **CR-01** Helper #2 subcontractor shadow files fall outside the rate-matrix gate in `pipeline/pricing.py`, **CR-02** `EXCLUDE_WRS` / `WR_FILTER` matchers in `pipeline/grouping.py` do not recognise `_HELPER2_` group keys). **Owner decision 2026-09-10: `--fix`.** All 5 Critical/Warning findings fixed on local branch `fix/phase-14-cr01-cr02-wr03` (`0e10891`..`7e9c56e`, `14-REVIEW-FIX.md` all_fixed; six gates, rubric + production-risk passes; bot-review follow-ups through `c7544b4`, incl. the `SUB_RATES_FP` hash gate widened to the Helper #2 shadows, suite 2333/1 skipped) — **PR #402 open, awaiting merge**; IN-01 self-resolves with CR-02.
  **Helper #2 is ENABLED** for scheduled runs via the repo variable `HELPER2_ENABLED=1` — section below.
- **GSD tooling**: HEALTHY as of 2026-09-06 (gsd-core 1.13.0 via the marketplace plugin); a forbidden npm
  reinstall that session was fully rolled back — never accept the npm install prompt on this machine.
- **CI noise**: `code/snyk` ("Code test limit reached") and the Azure DevOps mirror build fail on every PR
  (same on merged #388/#389/#390); master carries no required checks.

## Phase 14 — Foreman Helper #2

- **Status**: COMPLETE — 14 plans executed, 14-14 Task 2 observed 2026-09-10 (O-14-E RESOLVED); `14-VERIFICATION.md` =
  `passed` 7/7 (HLP-01..07 Complete). PR #389
  (`ba6eeaf`, 2026-09-09 01:37Z, `D-14-12-ROLLOUT` documented-only) and PR #390 (`661d6d3`, 02:49:30Z,
  plan 14-12: O-14-B closure, `HELPER2_ENABLED` wiring, post-merge docs) are both on master.
- **Enabled**: repo variable `HELPER2_ENABLED=1` set 2026-09-09 02:49:58Z (`D-14-14-ENABLE` addendum). The
  workflow "Generate reports" env reads `${{ vars.HELPER2_ENABLED || '0' }}`; the repo default in
  `pipeline/config.py` stays `'0'` (local and synthetic runs unchanged).
- **Flag-off is an emergency disable, not a billing-safe rollback** (`gh variable set HELPER2_ENABLED
  --body 0`): with the flag off, detection clears the Helper #2 marker, so a row that also carries
  "Units Completed?" or a Helper #1 claim regroups into the primary / Helper #1 workbook while cleanup
  keeps the old `_Helper2_` attachment (D-14-12) — the same unit in two files until reconciled by hand.
  Harmless today (no live row carries a Helper #2 claim). Owner decision **O-14-D RESOLVED 2026-09-09**:
  Helper #2 is permanent (flag stays `1` indefinitely, flag-off is an emergency kill switch only), the
  regroup-on-disable limitation is accepted, reconcile by hand if it ever happens — no code change.
- **Plan 14-12 (gap closure) — COMPLETE**: Task 1 `1563199` lockstep test (`upsert_rows_bulk` lists ⊇
  `HASH_FIELDS`) + `cf556d8` RPC text and `pipeline_memory/helper2_columns_migration.sql`; Task 2 applied
  2026-09-09 02:21:29Z as Supabase migration `20260909022129_helper2_row_state_columns_marker_and_rpc` and
  read back clean (`D-14-13-DDL-APPLIED` / `D-14-13-VERIFIED`); Task 3 workflow env line + runbook /
  environment docs + records (`O-14-B RESOLVED`, `O-14-A-FOLLOWUP-1 CONFIRMED`, `D-14-14-ENABLE`).
- **Owner instruction** (Juan, 2026-09-08): apply both DDLs, close O-14-B, confirm Follow-up 1, "then enable
  the helper 2 once these issues are fixed" — executed in full 2026-09-09.
- **First scheduled run on merged + enabled code OBSERVED** — run `34356004448` (head `be60755`, 13:16Z →
  14:26Z, success). Helper #2 clean: capability-unavailable on the 2 Arrowhead sheets, no qualifying
  completion elsewhere, 0 groups, 0 `_Helper2_` files, no degrade warning, 130 `freeze_attribution` calls
  all 200. One-time churn confirmed: 218,338 `row_event` rows (5,451 changed). Files generated 7. The
  `Shadow parity FAIL` is the flag-off shadow READ probe, intermittent and pre-existing (also on 2 of 9
  pre-merge runs). **Gap found: `sheet_registry.mapping_schema` is still NULL on all 121 rows** — the
  orchestrate call sites never pass `mapping_schema_by_sheet`, so every run fully validates all 121
  sheets (~38 s, no billing impact). Recorded as **O-14-E**; fixed by plans 14-13 + 14-14 and RESOLVED
  2026-09-10 (see Open items).
- **Review bots**: Greptile/Copilot's P1 on PR #391 (flag-off re-routes Helper #2 rows) was verified in
  code and recorded as O-14-D with docs corrected, no code change. Codex bot comments on PR #390 are
  outside the ClaudeOS harness boundary — listed for Juan, never applied.

## Live Supabase state

- **billing_audit**: migrations `20260908165511` (attribution columns + RPCs) and `20260908201205`
  (per-role Helper #2 fill) remain live.
- **pipeline_memory**: migration `20260909022129_helper2_row_state_columns_marker_and_rpc` is live
  (14-12 Task 2) — adds the `row_state` Helper #2 columns and `sheet_registry.mapping_schema`; read back
  clean (`D-14-13-VERIFIED`). Pre-state rollback reference parked in the owner's vault `raw/` folder.
- **Phase 12 attribution**: live backfill applied 2026-09-05 (1,758 rows); snapshot backups
  `_20260903`/`_20260904`/`_20260905` retained until 12-06 Task 4 verifies the post-apply run.

## Open items / owner decisions

- **O-14-E** (`mapping_schema` marker never written): RESOLVED 2026-09-10. Plans 14-13 (`d079e81`) + 14-14
  (`736141a`; frequent runs adopt the freshly validated mapping + marker, drift logged before the first
  registry write; SQL backfill rejected — 0/121 stored mappings carried Helper #2 keys). Observed: dispatch
  run `34411958861` stamped 121/121 (114 with Helper #2 keys, 7 capability-unavailable without); scheduled
  run `34415980363` skipped 112/121 via the registry, 0 refresh warnings, counters 7/114 (`14-DECISIONS.md`).
- **O-14-D** (flag-off routing): RESOLVED 2026-09-09 — option (a) accepted; Helper #2 is permanent, the
  flag is an emergency kill switch only, persisted-claim routing declined (`14-DECISIONS.md`).
- **O-14-B** (`upsert_rows_bulk` RPC gap): RESOLVED 2026-09-09 (`D-14-13-VERIFIED`).
- **O-14-A Follow-up 1** (per-slot Helper #2 duplication): CONFIRMED by Juan 2026-09-08 (`O-14-A-FOLLOWUP-1`).
- **12-06 Task 4**: first post-apply scheduled-run check still owed — pointer `.planning/HANDOFF.json`.
- **HELPER2_ENABLED**: ENABLED (variable `1` since 2026-09-09 02:49:58Z); repo default stays `'0'`.

## Next actions

1. Juan's decision on the Phase 14 code-review Criticals (`14-REVIEW.md` CR-01 pricing gate,
   CR-02 WR hold matchers — billing formula + WR controls, protected): fix via
   `/gsd-code-review 14 --fix` or a hand-written TDD PR (extend `test_helper2_family_parity`
   first; validate CR-01 against a known-good Helper #1 subcontractor sample), or accept as-is.
2. Phase 12: run 12-06 Task 4 (first post-apply scheduled-run check), then drop the snapshot backups.
3. Phase 13 (`wr_week_ownership`, D-12-A) — plan only when Juan asks.

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
