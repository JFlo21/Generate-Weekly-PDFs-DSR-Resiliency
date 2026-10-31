# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-10-30 (GF-lookup hold + Foreman Notes Sentry upgrade, draft PR #444 stacked on #437) · **overwrite-in-place each session** — this is
the canonical "where the project stands" landing spot for the global Stop write-back reminder. Cap ≤ 120
lines (`align-instruction-files` skill); history goes to `memory-bank/living-ledger.md`, never here._

## Where it stands

- **Milestone v1.4 "Supabase Run Memory"**: Phases 10 (2026-08-25), 11 (2026-08-31), and 11.1 (2026-09-02,
  PR #384 `13e8e76`) are closed. Production posture: `pipeline_memory` write path ON since PR #353
  (`RUN_MEMORY_WRITE_ENABLED='1'` on the `Generate reports` step only); `RUN_MEMORY_INCREMENTAL_ENABLED` OFF;
  change detection and attachment identity are `group_state`-backed; `TIME_BUDGET_MINUTES=165` under
  `timeout-minutes: 180`.
- **QUAR-01 plan (2026-10-30)**: `.planning/todos/pending/2026-10-30-close-quar-01-incremental-collision-gap-and-enforce-flag-gat.md`
  — enforce the incremental gate in code and close the blind spot without a schema change. Not implemented.
  PRs #439 (`e63dc3f`), #442 (`59c4e27`) and #443 (`a201fbe`) merged 2026-10-30. #437 is open: Sentry and
  notes-hash fixes (`c06bdef`) passed independent review, and the four Greptile findings of 2026-10-30 are
  fixed (colour cache cleared per run, runbook variant wording, docstrings, test type hints). Review round 2 (`3e7c733`, 2026-10-30): dry-run warning names AUDIT_MEMORY_ENABLED, secret-not-variable comment, test scope pinning, docs fixes; 16 threads replied (Sentry P1 already fixed in `7c16611`; first-day header merge skip is pre-existing on master, kept). #440 merged, so the D-15-13 gate is met. Only open thread: GF-lookup churn, tracked in `.planning/todos/pending/2026-10-30-foreman-notes-gf-lookup-failure-churns-pilot-groups.md` (owner picks hold-for-run vs reuse-last-known-set). Parity reading 2026-10-30T18:32:34Z: streak 5, recorded in
  `11-VERIFICATION.md`; D-15-13 condition met, FN-13 closes at merge. `FOREMAN_NOTES_UPLOAD` stays off until
  draft PR #444 (GF-lookup hold + Sentry upgrade, quick `261030-suf`) merges and the owner approves the workflow change.
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
  **Nyquist validated 2026-09-12** (`/gsd:validate-phase 13`, `e320155`): 14/14 per-task rows green, 0 gaps,
  `nyquist_compliant: true`; evidence re-run in-session (59+15+42 targeted tests, 6-gate harness, website build).
  Security gate closed `2047a67`. Remaining open: UAT test 1 (blocked on release build) and the VERIFICATION
  wall-clock observation — both need the code on `master` and `AUDIT_MEMORY_ENABLED=1` live.
- **Milestone v1.4 re-audit (2026-09-13, `859c98c`; supersedes `b6053bd`)**: still `gaps_found` — 19/23
  requirements, integration 5/5, flows 5/5 re-traced at HEAD (no code changed since 09-12). SECURITY.md now
  6/6 (0 open threats); Nyquist compliant 10, 11, 13 — 11.1, 12, 14 still `draft`. Sole blocker unchanged:
  no `11-VERIFICATION.md` (INC-01..04 partial; INC-02 D-05 approved-partial). Deployment gap: `AUDIT_MEMORY_ENABLED`
  absent from the workflow env. Closure order: verify-work 11 → validate-phase 11.1/12/14 → re-audit.
  Report: `.planning/v1.4-MILESTONE-AUDIT.md`.
- **Phase 11 UAT complete (2026-09-14, `ea5a82f`)**: `/gsd:verify-work 11` — 36/36 pass, 0 issues (31 coverage
  auto-passed, 5 owner-delegated checkpoints agent-validated against live `run_ledger`/`row_state`, Sentry issue
  GENERATE-WEEKLY-EXCEL-AH, and the 11-07/11-08 decision record).
- **Phase 11 verification gate run (2026-09-14, `1880362`)**: `/gsd:execute-phase 11` resumed at the gates (#2868
  route, no plans re-run). Regression gate: pytest 2416 passed / 1 skipped / 595 subtests. `11-VERIFICATION.md` =
  **`gaps_found` 5/8**: (1) group rows still re-fetched from Smartsheet, not `row_state` — the dated D-05
  owner-approved deferral (INC-02 Pending); needs Option B or an explicit override in the frontmatter; (2) live
  `actual_not_in_candidate` parity fails on USER-variant groups (runs 34648318434.1, 34541106039.1) — a real,
  untracked D-04 candidate-selector gap that resets the ≥5-pass streak. Neither affects production today
  (`RUN_MEMORY_INCREMENTAL_ENABLED` OFF). Phase 11 NOT re-marked complete. Code review (`11-REVIEW.md`,
  `697eda9`, standard, 29 SUMMARY-scoped files): 0 Critical / 1 Warning / 2 Info — **WR-01** `pipeline/fetch.py`
  `_is_abbreviated_response` treats a zero-row full response (whole sheet deleted) as an unchanged delta probe, so
  the deletion adds nothing to the affected set that run and the watermark advances; bounded by the weekly deep
  run (≤ ~1 week latency). Owner decision pending (`/gsd:code-review 11 --fix` or a todo).
  **Gap-closure planned 2026-09-14 (`/gsd:plan-phase 11 --gaps`, `44efdfc`)**: two additive plans — `11-09`
  (wave 1, autonomous: fixture-backed RED reproduction of the USER-variant candidate miss, then a surgical
  selector fix preserving D-04 Option C; leading hypothesis: `orchestrate.py` `_resolve_row_wr_week` derives
  `wr_key` without the `pipeline_memory/writer.py` `_sanitized_wr` sanitizer that `row_state.wr` carries; files
  the defect as tracked) and `11-10` (wave 2, `autonomous: false`: D-05 override recorded in
  `11-VERIFICATION.md` frontmatter only on Juan's explicit checkpoint decision; ≥5-run clean-streak reading is
  owner-supplied, never computed by the executor).
  **Gap-closure EXECUTED 2026-09-14 (`/gsd:execute-phase 11 --gaps-only`, sequential on `plan/phase-13`,
  `1feedeb`..`1aa5f2a`)**: 11-09 confirmed the hypothesis — `_resolve_row_wr_week` now delegates to
  `pipeline_memory.writer._sanitized_wr` (`04c618a`; fixture `tests/fixtures/incremental/user_variant_candidate_miss.json`,
  +10 tests; suite 2426/1 skipped/610 subtests, 6-gate harness green; grouping/pricing/attribution/excel/workflows
  byte-identical). 11-10: D-05 Option C override ACCEPTED by Juan Flores 2026-09-14T17:36:08Z and recorded in
  `11-VERIFICATION.md` frontmatter (`overrides_applied: 1`, `5240d85`); post-fix streak recorded verbatim as
  **not yet observable (0 post-fix runs — fix unpushed/unmerged, cron runs default branch)** (`5c8293d`).
  Re-verification (`1aa5f2a`) = **`human_needed` 6/8** — no code gaps; one open live-data item (≥5 clean post-fix
  `production_frequent` runs) persisted as `11-UAT.md` test 37. Incremental code review (`3e9dc0a`, 8 files):
  0 Critical / 2 Warning / 2 Info — WR-02 this file over its 120-line cap; WR-03/IN-03 tautological contract
  tests; WR-01/IN-01/IN-02 still open. Phase 11 NOT marked complete. `RUN_MEMORY_INCREMENTAL_ENABLED` still OFF.
  **Fix shipped as PR #409** (`fix/phase-11-gap2-selector` off `origin/master`: cherry-picks `1feedeb` `04c618a`
  `1ba2293` `a604931`; suite 2348 / 1 skipped / 610 green); 11-10 records stay on `plan/phase-13` for the Phase 13 PR.
  Next: merge #409 → ≥5 clean `production_frequent` runs → `/gsd-verify-work 11` test 37 → re-verify →
  validate-phase 11.1/12/14 → v1.4 re-audit.
  **Phase 11 Nyquist closed 2026-09-12** (`/gsd:validate-phase 11`, `ccdaa08`): 30 per-task rows green, INC-01..05
  all COVERED, 0 gaps, `nyquist_compliant: true`; quick set 383 passed, full suite 2416/1 skipped re-run in-session.
  INC-02 stays D-05 approved-partial (production observation, Manual-Only). **Phase 11 security gate closed
  2026-09-12** (`/gsd:secure-phase 11`, `7965507`): `11-SECURITY.md` created from the eight plan-time
  `<threat_model>` registers — 45 threats (40 mitigated, 5 accepted → AR-11-01..05), `threats_open: 0`, ASVS L1
  grep-level; short-circuit rule applied (no auditor subagent). T-11-43 closes on the owner's documented 5/5
  streak re-authorisation citation, not a live re-derivation. Still open for 11: no VERIFICATION.md exists and
  none was created (audit accepted as a doc-coverage gap). **Phase 11.1 security gate closed 2026-09-12**
  (`/gsd:secure-phase 11.1`, `ad24b01`): `11.1-SECURITY.md` — 18 threats (16 plan-time from plans 01/02/04 +
  2 retroactive for plan 03's PR #378 warm start, which had no threat model), 16 mitigated, 2 accepted
  (AR-11.1-01..02), `threats_open: 0`, ASVS L1, short-circuit (no auditor). **Phase 12 security gate closed
  2026-09-12** (`/gsd:secure-phase 12`, `61b40d3`): `12-SECURITY.md` — 61 plan-time STRIDE entries from all ten
  plans (52 unique + 10× T-12-SC collapsed; reused IDs T-12-20..28/30 disambiguated by `(Pnn)` suffix), 59
  mitigated with L1 grep / pinned-test / SUMMARY live-confirmation evidence, 2 accepted (AR-12-01 cell-history
  artifact names, AR-12-02 regeneration-burst budget), `threats_open: 0`, short-circuit (no auditor).
  **Phase 14 security gate closed 2026-09-13** (`/gsd:secure-phase 14`, `c96a141`): `14-SECURITY.md` — 70
  plan-time threats from all fourteen plans (62 tabular in 14-01..11, 4 bulleted in 14-12, 2+2 unnumbered in
  14-13/14 assigned `T-14-13-0n`/`T-14-14-0n`), 56 mitigated with L1 grep / pinned-test / SUMMARY read-back
  evidence, 14 accepted (AR-14-01..04: discovery synonyms, 11× no-packages SC rows, `helper2_observed` same
  RLS class, portal label token), `threats_open: 0`, short-circuit (no auditor). The three owner-delegated
  production applies (14-09/11/12) close their own T-*-05/T-*-03 EoP rows as recorded owner decisions, not
  auto-mode. **v1.4 SECURITY.md coverage is now complete (11, 11.1, 12, 13, 14).**
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
  closure PR #398 → `45bdbbf`; code review report PR #399 → `94f2636` (`14-REVIEW.md`, standard depth, 71 files: 2 Critical / 3 Warning / 1 Info — **CR-01** Helper #2 subcontractor shadow files fall outside the rate-matrix gate in `pipeline/pricing.py`, **CR-02** `EXCLUDE_WRS` / `WR_FILTER` matchers in `pipeline/grouping.py` do not recognise `_HELPER2_` group keys). **Owner decision 2026-09-10: `--fix`.** All 5 Critical/Warning findings fixed on local branch `fix/phase-14-cr01-cr02-wr03` (`0e10891`..`7e9c56e`, `14-REVIEW-FIX.md` all_fixed; six gates, rubric + production-risk passes; bot-review follow-ups through `c7544b4`, incl. the `SUB_RATES_FP` hash gate widened to the Helper #2 shadows, suite 2333/1 skipped) — **PR #402 MERGED 2026-09-10 20:25Z → `6e6e1e8`** (review rounds: Copilot ×3, Greptile ×4, Codex, Cursor; follow-ups through `dc484f2`; synthesized operator changelog `website/blog/2026-09-10-pr402-phase-14-review-fixes.md`; local fix branch deleted, remote branch still on origin); IN-01 self-resolved with CR-02. PR #402 owner follow-ups DECIDED 2026-09-11 (D-14-FOLLOWUPS; record `.planning/todos/done/2026-09-10-pr402-review-followups.md`): breaker half-open **MERGED via PR #407 → `0585758`** (2026-09-11 15:48Z, branch deleted; `close_circuit()` closes a stale `freeze_attribution` breaker on a successful Helper #2 probe; review round 1 serialised every breaker transition under one `_breaker_lock` and added a trip-generation check so a trip that happens while the probe is in flight survives — follow-up: mirror `_breaker_lock` into the `pipeline_memory` twin breaker); `keep_historical` cleanup DEFERRED behind the `RUN_MEMORY_INCREMENTAL_ENABLED` rollout gate (no code until incremental read is ever enabled).
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
- **FOREMAN_NOTES_UPLOAD** (Phase 15 pilot, 3 GFs): PR #445 wires scope `pilot` + secret allowlist +
  variable switch (default `'0'` = off). After merge the owner confirms the secret holds 3 names, then
  `gh variable set FOREMAN_NOTES_UPLOAD --body 1`; first run should log `allowlist=3`, `pilot_wrs` > 0.

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
