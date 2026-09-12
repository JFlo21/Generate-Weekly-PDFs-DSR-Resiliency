# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-09-11 22:35 CDT (2026-09-12 03:35Z) · **overwrite-in-place each session** — this is
the canonical "where the project stands" landing spot for the global Stop write-back reminder. Cap ≤ 120
lines (`align-instruction-files` skill); history goes to `memory-bank/living-ledger.md`, never here._

## Where it stands

- **Milestone v1.4 "Supabase Run Memory"**: Phases 10 (2026-08-25), 11 (2026-08-31), and 11.1 (2026-09-02,
  PR #384 `13e8e76`) are closed. Production posture: `pipeline_memory` write path ON since PR #353
  (`RUN_MEMORY_WRITE_ENABLED='1'` on the `Generate reports` step only); `RUN_MEMORY_INCREMENTAL_ENABLED` OFF;
  change detection and attachment identity are `group_state`-backed; `TIME_BUDGET_MINUTES=165` under
  `timeout-minutes: 180`.
- **Phase 12 (Ownership)**: **COMPLETE 2026-09-10** — 10/10 plans (incl. 4 gap-closure plans). `/gsd-verify-work 12`
  passed: `12-UAT.md` 34/34, `12-VERIFICATION.md` 77/77 must-haves; 5 open advisory gaps for owner follow-up, the 6th — runbook WR-09 — fixed in the PR; docs PR #404
  MERGED 2026-09-11 03:39Z → `9ba7eb7`. Live attribution backfill applied 2026-09-05 (1,758 rows); 12-06 Task 4 approved 2026-09-10 ~23:45Z
  (`Adopt 89746993` for D-12-E; snapshot backups dropped).
- **Phase 13 (Audit Memory)**: **EXECUTED 2026-09-11, pending `/gsd-verify-work 13`** — 6/6 plans on branch
  `plan/phase-13` (sequential executors, 27 commits `5adebb0`..`e13a6ba`; nothing pushed, no PR yet). Shipped:
  `pipeline_memory/audit_findings.py` (owner-confirmed `v1` finding-key recipe, all three checks, fail-open
  writer behind `AUDIT_MEMORY_ENABLED` — default OFF, D-09), `upsert_audit_findings` RPC with the full D-08
  transition table, `open_findings` / `finding_history_by_wr` views + `acknowledge_finding` (service_role
  only). **DDL applied live** to `poeyztlmsawfoqlanucc` by owner delegation as migration
  `audit_memory_findings_lifecycle_views` (v`20260912023008`); lifecycle read-back verified and rows cleaned.
  Suite 2416/1 skipped, 6 gates green. `13-REVIEW.md` 0 Critical / 3 Warning / 1 Info (WR-01 explicit
  `GRANT EXECUTE` for the RPC; WR-02 skip counters not surfaced to `run_summary`; WR-03 `IDENTITY_RECIPES`
  unread by code). `13-VERIFICATION.md` = `human_needed` 13/14 — only success criterion 2 (wall clock
  proportional to affected groups) is production-observed; `13-UAT.md` holds it. **`13-SECURITY.md`
  written 2026-09-12 (`2047a67`): 41/41 plan-time STRIDE threats closed (33 mitigated with L1 grep evidence,
  8 accepted → AR-13-01..03), `threats_open: 0`, verify:post security gate satisfied; one non-blocking
  residual note (raw exception text in the orchestrator's audit-memory failure log line).**
  **`/gsd-verify-work 13` run 2026-09-12 → `13-UAT.md` = `partial`**: the one
  test is `blocked` (`release-build`) — code not on `origin/master` (branch 38 ahead), flag not wired into
  `weekly-excel-generation.yml`, run 34657240194 shows 0 `Audit-memory` log lines; unblock steps recorded in
  the UAT file. `13-COVERAGE.md` added (no-external-API declaration) to clear the `api-coverage` verify:pre
  gate (commit `b4e7a15`). Next: open PR `plan/phase-13` → master → wire + flip
  `AUDIT_MEMORY_ENABLED` (shadow-first) → observe ≥2 runs → re-run `/gsd-verify-work 13`.
  Discussed 2026-09-11 (`13-CONTEXT.md`, commit `80a79b9`): spec §8 #6 LOCKED (per-check natural finding key; three WR-scoped checks;
  owner-only SQL acknowledge) and D-12-A CLOSED (`wr_week_ownership` dropped for good → D-13-A, docs-only). Next: `/gsd:plan-phase 13`.
- **Phase 14 (Foreman Helper #2)**: COMPLETE 2026-09-10 — 14/14 plans executed and observed; O-14-E RESOLVED.
  PR #389 → `ba6eeaf`, #390 → `661d6d3`, #394 → `7ded60c`, #395 → `d079e81`, #396 → `736141a`, #397 → `92c9ed6`,
  closure PR #398 → `45bdbbf`; code review report PR #399 → `94f2636` (`14-REVIEW.md`, standard depth, 71 files: 2 Critical / 3 Warning / 1 Info — **CR-01** Helper #2 subcontractor shadow files fall outside the rate-matrix gate in `pipeline/pricing.py`, **CR-02** `EXCLUDE_WRS` / `WR_FILTER` matchers in `pipeline/grouping.py` do not recognise `_HELPER2_` group keys). **Owner decision 2026-09-10: `--fix`.** All 5 Critical/Warning findings fixed on local branch `fix/phase-14-cr01-cr02-wr03` (`0e10891`..`7e9c56e`, `14-REVIEW-FIX.md` all_fixed; six gates, rubric + production-risk passes; bot-review follow-ups through `c7544b4`, incl. the `SUB_RATES_FP` hash gate widened to the Helper #2 shadows, suite 2333/1 skipped) — **PR #402 MERGED 2026-09-10 20:25Z → `6e6e1e8`** (review rounds: Copilot ×3, Greptile ×4, Codex, Cursor; follow-ups through `dc484f2`; synthesized operator changelog `website/blog/2026-09-10-pr402-phase-14-review-fixes.md`; local fix branch deleted, remote branch still on origin); IN-01 self-resolved with CR-02. PR #402 owner follow-ups DECIDED 2026-09-11 (D-14-FOLLOWUPS; record `.planning/todos/done/2026-09-10-pr402-review-followups.md`): breaker half-open IMPLEMENTED on PR #407 (`close_circuit()` closes a stale `freeze_attribution` breaker on a successful Helper #2 probe; review round 1 serialised every breaker transition under one `_breaker_lock` and added a trip-generation check so a trip that happens while the probe is in flight survives — follow-up: mirror `_breaker_lock` into the `pipeline_memory` twin breaker); `keep_historical` cleanup DEFERRED behind the `RUN_MEMORY_INCREMENTAL_ENABLED` rollout gate (no code until incremental read is ever enabled).
  **Helper #2 is ENABLED** for scheduled runs via the repo variable `HELPER2_ENABLED=1` — section below.
- **GSD tooling**: HEALTHY as of 2026-09-06 (gsd-core 1.13.0 via the marketplace plugin); a forbidden npm
  reinstall that session was fully rolled back — never accept the npm install prompt on this machine.
- **claude-mem**: the 13.24.7 plugin cache was gutted by the plugin updater (only hooks/modes/node_modules
  survived); restored from the marketplace checkout 2026-09-11 — if hooks stop capturing again, re-copy
  package.json, scripts/, skills/, sqlite/, ui/ from `~/.claude/plugins/marketplaces/thedotmack/plugin`.
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
- **Phase 12 attribution**: live backfill applied 2026-09-05 (1,758 rows); 12-06 Task 4 observed the post-apply
  run 2026-09-10 (all pass) and Juan approved it ~23:45Z; snapshot backups `_20260903`/`_20260904`/`_20260905`
  dropped via the Supabase connector (migration `drop_attribution_snapshot_backups_20260903_04_05`) — 0 left,
  live table unchanged at 224,371 rows / 1,758 with `backfill_provenance`.

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
- **12-06 Task 4 observed and APPROVED** (run 33974128574: 74 files regenerated, 64 placeholders removed, sample
  WR 89746993 pass, 47:51 < 165 min) — Juan replied `Approved` / `Adopt 89746993` (D-12-E) / backups dropped
  2026-09-10 ~23:45Z; 12-06 COMPLETE. First run after `6e6e1e8` (`34530899488`) clean, no Helper #2 shadow groups.
- **HELPER2_ENABLED**: ENABLED (variable `1` since 2026-09-09 02:49:58Z); repo default stays `'0'`.

## Next actions

1. PR #404 merged (`9ba7eb7`) and the post-merge write-back PR #405 merged (`6fd676a`); Phase 12 records final.
2. PR #402 follow-ups DECIDED 2026-09-11 (D-14-FOLLOWUPS): breaker half-open = clear on probe success (PR open,
   branch `fix/breaker-half-open-on-probe`); `keep_historical` DEFERRED — gate before `RUN_MEMORY_INCREMENTAL_ENABLED`.
3. Phase 13 (Audit Memory) — **PLANNED 2026-09-11** on `plan/phase-13` (`2c53d32`, `96cebea`): 6 plans / 5 waves (`13-01` tracer on `rate_sanity_mismatch` with a blocking `checkpoint:decision` on the one-way finding-key recipe — planner proposes a `FINDING_KEY_RECIPE_VERSION='v1'` token; `13-02` folded todos; `13-03` other two checks + message-string pin; `13-04` D-08 transitions + AUD-02 scoping; `13-05` views/acknowledge/RLS with owner DDL-apply checkpoint; `13-06` docs/ledger). Checker PASSED (0 blockers/0 warnings/1 advisory); coverage 3/3 REQ, 11/11 decisions, gap analysis 19/19. Research `d265800`, validation `46dda31`. Next: `/gsd:execute-phase 13` (wave 1 stops at 13-01 Task 1 for the recipe decision).
4. Owner: Codex threads (PR #399/#400/#402), Dependabot triage.

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
- Handoff: `.planning/HANDOFF.json` (Phase 12 CLOSED; next = PR #402 follow-ups, Phase 13 when asked).
