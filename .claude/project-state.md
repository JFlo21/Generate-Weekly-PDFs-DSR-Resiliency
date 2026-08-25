# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-08-25 01:10 CDT · **overwrite-in-place each session** (this is the
canonical "where the project stands" landing spot for the global Stop
write-back reminder). Keep it terse; link to history rather than duplicating it._

_Latest ledger entry: `memory-bank/living-ledger.md` `[2026-08-25 00:02]` (mypy Gate 4
re-baselined 56 → 65 by Juan's `rebaseline` decision, every accepted finding attributed;
commit `da7d73c`). **Phase 09 CLOSED 2026-08-25** — verifier 6/6 (`410235e`), v1.3 milestone
complete. Next: `/gsd-core:gsd-execute-phase 10` (Run-Memory Foundation; pauses at the
10-05/10-06 human checkpoints). Optional first: `/gsd-core:gsd-complete-milestone` to archive v1.3.
Git: `master` ahead ~25 / behind 15 of `origin/master` — pull/rebase before pushing; **PR open:** https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/349
(branch `feat/phase-09-gap-closure`, merged with origin/master; after merge: `git checkout master && git reset --hard origin/master`)._

## Latest work (2026-08-25 01:10 CDT) — `/gsd-execute-phase 09 --gaps-only` COMPLETE: G-09-MOD-06 closed, `rebaseline` executed, tail gates green, phase closed
000000000000000000000000. **Wave 2 resumed:** Juan replied `rebaseline` → continuation
   executor recorded it (`6c6ca41`/`a1499d6`); orchestrator regenerated the golden
   baseline with the gate's own invocation (65 lines, LF) and committed it with the
   attributed ledger entry + a todo for the single class-A finding (`da7d73c`).
   `bash scripts/run_6_gates.sh` → **ALL 6 GATES PASSED in 32 s** (Gate 4 `65 -> 65`;
   Gate 6 synthetic, 0 API calls, hash_history sha unchanged). **Tail gates:** Nyquist
   +8 pin tests (`d4e6911`, harness file 21 tests) + `09-VALIDATION.md` (`178148b`);
   `09-SECURITY.md` threats_open 0 (`c631a43`); regression gate 726 passed on prior-phase
   files; `09-REVIEW.md` 0 critical / 3 warning / 1 info — Gate 4 follow-ups tracked
   as a todo (`b9e1643`); ui-review skipped (no frontend surface); **gsd-verifier
   passed 6/6** → `phase.complete` (`410235e`). Suite: **1386 passed + 132 subtests**.
   ROADMAP/STATE/PROJECT evolved by hand (this ROADMAP layout isn't parsed by
   `roadmap.analyze`). Vault: project page §"Phase 09 gap closure executed", dashboard
   row, log `[2026-08-25a]`. Pushed as https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/349. `generated_docs/hash_history.json` still
   carries the pre-existing local prune-marker diff (untouched, leave or discard).

## Previous (2026-08-24 23:30 CDT) — `/gsd-execute-phase 09 --gaps-only` Wave 1 DONE, Wave 2 at checkpoint (7 commits `7633432`..`76011aa`)
0000000000000000000000. Sequential mode (base-check auto-degrade: HEAD ≠ origin/HEAD).
   Pre-dispatch hygiene commit `7633432` (ledger/state/config from earlier
   sessions). **09-07 complete** (`c4fb38a` RED → `6a5d321` GREEN → `1bd0bee`
   LF pin → `a925453` ledger → `dd3a9fb` SUMMARY): Gate 4 now hard-fails on
   non-integer operands (`_assert_count`) and strips CR/tab; 5 fail/pass-
   capability tests run the real script bytes; `tests/golden/*.txt text eol=lf`.
   Post-wave gate: py_compile OK, **1380 passed + 132 subtests**. Measured
   handoff: `FAIL: mypy error lines increased (56 -> 65)` exit 1. **09-08
   Tasks 1–2 complete** (`4441b52` Gate 6 pinned `SMARTSHEET_API_TOKEN=` →
   synthetic path, PASS 21 keys in 2 s, mode=synthetic/sheets=0/api_calls=0,
   hash_history sha256 unchanged; `76011aa` attribution report
   `.planning/debug/mypy-delta-56-to-65-2026-08-24.md`: 10 new findings =
   1 A (`billing_audit/snapshot_store.py:370`, runtime-guarded) / 2 B / 7 C /
   0 D, none from Phase 09 — all from post-09 quick tasks). **Task 3 checkpoint
   open** (see header). `run_6_gates.sh` intentionally still red at Gate 4
   until the decision is implemented. Observation to carry: baseline stores
   Windows `\` paths → Gate 4 FAIL-diff would be noise on Linux CI.

## Previous (2026-08-24 14:35 CDT) — DIAGNOSIS ONLY: `_User_Unknown_Foreman` (WR 89829163) root-caused; helper-sheet gaps traced to data gates
0000000000000000. GSD debug session
   `.planning/debug/unknown-foreman-helper-shadow-2026-08-24.md`
   (status root_cause_found; no code/data/workflow change). (1) The
   source sheets' `Foreman` column is a WR-level RA lookup that blanks
   when a WR is archived; `freeze_row` then froze the literal
   `'Unknown Foreman'` sentinel as the claimer (first-write-wins,
   2026-04-24 backfill run 24912872441) and `resolve_claimer` never
   re-resolves it → 5,824 snapshot rows / 93 WRs affected; ~154
   garbage-claimer primaries regenerate every run. Fix direction
   (needs Juan): null the sentinel at freeze + treat frozen sentinel
   as no_history + approved remediation SQL + durable "last known
   foreman" source for archived WRs. (2) Helper sheets: scheduled run
   32743959053 evaluated all 166+5 helper groups (0 dropped); missing
   helper files are data-gated (`Helper Dept #` formula blank — WRs
   91499829/90550059 — or `Foreman Helping?` blank). Need one concrete
   (WR, week, helper, run) example for the "only after full regen"
   claim. Ledger entry `[2026-08-24 14:35]`; wiki project page + log
   updated. Manual run 32748717671 (Juan, 16:04 UTC) was still
   in_progress at last check.

## Latest work (2026-08-24 22:00 CDT) — `/gsd-verify-work 09` DONE: retroactive verification → gaps_found (Gate 4 vacuous); gap-closure plans 09-07/09-08 **checker PASSED** (`c8986b6`, addendum `8af3dfb`)
000000000000000000000. Phase 09 had NO GSD artifacts on disk (never committed;
   PR #280 `889ca2e` merged 2026-06-27; ROADMAP still `[ ]`). Created
   `.planning/phases/09-engine-modularization-pipeline-package-split/`;
   `gsd-verifier` (sonnet) wrote `09-VERIFICATION.md` — **retroactive**,
   5/6 must-haves verified against code (MOD-01..05), **MOD-06 FAILED**:
   `scripts/check_mypy_delta.sh` cannot fail — `tests/golden/mypy_baseline_count.txt`
   is CRLF on this `core.autocrlf=true` checkout, `tr -d ' \n'` leaves `\r`,
   the `-gt` test errors inside an `if` → falls through to PASS while mypy
   drifted **56 → 65** (bug present since Phase 09's own merge `5005040`; no
   Gate-4 fail-capability test exists). Live gates today: G1/G2/G3(1375)/G5
   PASS; **G6 PASS on the synthetic path** (`SMARTSHEET_API_TOKEN=""` — with
   the `.env` token present, `TEST_MODE` does a full 118-sheet/208,511-row
   production READ (orchestrate.py:299); that stalled run was killed, no
   writes possible: SKIP_UPLOAD + no Supabase creds locally). Gap-closure
   plans (opus, `c8986b6`): **09-07** (Gate-4 fail tests RED→GREEN, harden
   script, `tests/golden/*.txt eol=lf`, ledger rules; autonomous) → **09-08**
   (pin Gate 6 token-blank, attribute the 9 new mypy errors, **blocking-human**
   decision fix-types / rebaseline / split). Expect the harness RED at Gate 4
   after 09-07 until Juan's 09-08 decision — that is correct. Latent: mypy
   baseline stores Windows backslash paths (Linux diff noise) — flagged, not
   planned. Next: checker verdict → `/gsd-core:gsd-execute-phase 09 --gaps-only`
   → re-run `/gsd-verify-work 09` → then Phase 10 execution. Harness is NOT
   invoked by any GitHub workflow (developer-side only).

## Previous (2026-08-24 18:30 CDT) — Phase 10 plan-phase (docs only; no code/schema/workflow)
00000000000000000000. `/gsd-core:gsd-plan-phase 10` running (agent-teams OFF; single
   orchestrator). Done so far: `10-RESEARCH.md` (sonnet researcher, commit
   `2c86ca5`; HIGH confidence stack/architecture, MEDIUM pg_cron project state +
   MEM-04 SDK shape), `10-VALIDATION.md` Nyquist draft (`7621e82`), and
   `10-PATTERNS.md` (sonnet pattern mapper, `25ffbdb`; 10 files → analogs). Two
   planner-critical pitfalls surfaced: `row_state.foreman_observed` must store the
   RAW `Foreman` cell, never `__effective_user` (the `'Unknown Foreman'` sentinel
   defect); the `pipeline_memory` writer needs its OWN client/kill-switch state,
   not `billing_audit.client`'s schema-agnostic global disable. Spec-less edge
   probe: 6 unresolved items (MEM-01/03/04 unclassified; MEM-02 adjacency/empty/
   ordering) handed to the planner. **Plans landed** (opus planner, 42 min,
   commits `4ccb54c` + `cc65b71`): 6 plans / 4 waves — 10-01 tracer
   (`pipeline_memory/` pkg, independent fail-open client, full DDL, `run_ledger`,
   flag default OFF) ∥ 10-04 (MEM-04 read-only probe CLI + cassette harness);
   10-02 (`row_state`/`row_event` chunked bulk write, own sub-budget) ∥ 10-05
   (MEM-04 experiment, **blocking-human**: Juan hand-edits the sandbox rig);
   10-03 (`sheet_registry` + `group_state`); 10-06 (control-vs-shadow byte proof,
   **blocking-human** DDL apply + PostgREST expose + retention-job review). Planner
   decisions: `group_state` PK promoted to `(wr, week_ending, variant, identifier,
   target_sheet_id)` (reduced_sub fan-out); `run_summary.json` stays 21 keys
   (counters → `run_ledger.notes`); `upsert_rows_bulk` always chunks at 500;
   `sheet_registry.kind` drops `vac_crew`. Also `COVERAGE.md` + filled
   `10-VALIDATION.md`. **Plan-checker: iteration 1 = 1 BLOCKER + 3 warnings**
   (10-06 scoped real-data `SKIP_UPLOAD` runs with `WR_FILTER`, which
   `grouping.py:1222` only honors under `TEST_MODE` → fixed to `MAX_GROUPS`;
   added `git diff --exit-code -- billing_audit/` guards; Nyquist latency
   rationale + sub-30s first checks; RESOLVED markers on RESEARCH open
   questions; DDL checkpoint cross-refs corrected to 10-06 T2) → revision
   `321f595` → **iteration 2 = VERIFICATION PASSED** (1 cosmetic warning:
   PATTERNS.md rows, fixed). Gates: requirements 4/4, decisions 9/9,
   gap-analysis 13/13, verify-path probe 59/59 clean. STATE.md → "Ready to
   execute" (6 plans); ROADMAP annotated (4 waves); final commit `94b6d80`.
   **Phase 10 is PLANNED — next: `/gsd-core:gsd-execute-phase 10`.** Planner
   flag still stands: `STATE.md` reads `current_phase: 9` — run
   `/gsd-verify-work 09` first for a clean handoff (10-01 Task 1 has a
   `run_6_gates.sh`-must-pass precondition on an unmodified checkout).
   Next after planning: `/gsd-core:gsd-execute-phase 10` (Phase 09 already merged).

## Previous (2026-08-24 17:05 CDT) — Phase 10 discuss-phase DONE; CONTEXT.md locked (docs only, no code/schema/workflow)
0000000000000000000. `/gsd-discuss-phase 10` (advisor mode, 3 sonnet research
   packets) produced `.planning/phases/10-run-memory-foundation-shadow-writes/
   10-CONTEXT.md` + `10-DISCUSSION-LOG.md` (commit `11f6c8d`) and a STATE.md
   session row (`481a02a`). Locked: **#2** new `pipeline_memory` schema in
   `poeyztlmsawfoqlanucc`, service-role-only RLS, versioned SQL mirror,
   PostgREST exposed-schema step explicit (PGRST106 runbook); **#5-prov**
   `source` CHECK enum + nullable `source_ref` on row_event/group_state;
   **#3** row_event = single UNPARTITIONED table (pg_partman is not
   installable on hosted Supabase), indexes observed_at/(sheet_id,row_id)/
   (wr,week_ending), 24-mo pg_cron sliced DELETE; **#4** weekly deep run
   stays the full reconcile, no schedule change; **MEM-04** = hybrid proof —
   Juan hand-builds 2 disposable sandbox sheets, READ-ONLY script records
   `if_version_after`/`rows_modified_since` as a replayable pytest cassette +
   passive shadow-run comparison; zero Smartsheet API writes. Rollout posture
   (flag off in code, workflow flip in a separate PR, write sub-budget) left
   as Claude's discretion with conservative defaults. Next: `/clear` →
   `/gsd-plan-phase 10`. Still uncommitted: ROADMAP v1.4 diff + untracked
   spec; `.claude/project-state.md` + ledger edits from this session.

## Previous (2026-08-24 15:58 CDT) — Phase 10 plan-phase PAUSED at context gate; three blockers fixed (no code)
000000000000000000. `/gsd-plan-phase 10` ran init (reqs MEM-01..04, models
   sonnet/opus/sonnet, security hook ASVS L1 block-on-high, UI gate
   frontend=false, drift skipped) and stopped at the no-CONTEXT gate —
   Juan chose "discuss-phase first". Empty phase dir created:
   `.planning/phases/10-run-memory-foundation-shadow-writes/`. Fixes
   applied afterwards: (1) `.claude/settings.local.json` (gitignored)
   sets `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` for THIS repo only —
   GSD orchestration stalls under agent-teams (open-gsd/gsd-core#1355);
   global `~/.claude/settings.json` still has it "1" for other repos;
   takes effect on the NEXT session. (2) v1.4 MEM/INC/OWN/AUD reqs
   merged into `.planning/REQUIREMENTS.md` (+16 traceability rows,
   coverage line) and committed with the milestone copy — commit
   `7e7c818` on master, NOT pushed — so plan-phase Step 13 coverage
   gate can see them. (3) ROADMAP Phase 10/12/13 "Depends on" and spec
   §8 now tag each Juan decision with the phase it gates: Phase 10 =
   #2 schema placement, #3 row_event retention, #4 deep run = full
   reconciliation (+#5 only as a provenance column); #1 → Phase 12,
   #5 backfill → Phase 12, #6 → Phase 13. ROADMAP.md and the spec
   remain UNCOMMITTED (ROADMAP carries Juan's earlier ~1,000-line v1.4
   draft diff; spec is untracked). Next: restart session (so the env
   override loads) → `/gsd-discuss-phase 10` → `/gsd-plan-phase 10`
   (research=yes already chosen). Note: Phase 09 MOD-01..11 are also
   absent from REQUIREMENTS.md (pre-existing, untouched).

## Previous (2026-08-24 15:30 CDT) — v1.4 "Supabase Run Memory" PLANNED (GSD draft, no code)
00000000000000000. Juan asked for a Supabase-as-memory redesign: per-row
   state + history every run (no duplicates), incremental Smartsheet
   reads, regenerate only affected (WR, week) files, "last known foreman
   as of the week" ownership, audit findings that persist until fixed.
   Written: spec `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md`
   (schema draft `pipeline_memory.*`, run algorithm, ownership ladder,
   audit lifecycle, evidence table from run 32743959053: fetch 33 min /
   207,844 rows, attachment pre-fetch 20 min, 12,227 freeze RPCs,
   3,091 hash GETs), `.planning/milestones/v1.4-REQUIREMENTS.md`
   (MEM/INC/OWN/AUD), ROADMAP.md Phases 10–13 + Progress rows.
   Verified: SDK 4.3.0 `get_sheet(if_version_after=, rows_modified_since=)`
   + API `ifVersionAfter`/`rowsModifiedSince` (Context7). BLOCKED on
   Juan's spec §8 decisions (ownership semantics vs Foundation A
   first-write-wins, schema placement, retention, deep-run
   reconciliation, backfill sources). Next: `/gsd:plan-phase 10` after
   decisions; `/lattice-init` before implementation.

## Previous (2026-08-15 01:12 CDT) — #340 MERGED (`96e42cb`); local repo tidied; #338 last open PR
000000000000000. Juan merged+deleted #340. Local: 5 [gone] branches
   deleted (260812-isx…260814-health-guardrail-hardening), 9 stale
   remote refs pruned, master ff'd to `644b1af`. Health system now
   COMPLETE on master: entry point (#339) + verified green manual run
   31860218831 (OK) + hardened dispositions (#340). Open: #338 only
   (docs, `8c06bdb`). Watch: Aug 16 ~02:20 UTC cron = first scheduled
   green expected.

## Previous (2026-08-14 23:10 CDT) — PR #340 OPEN: guardrail-check hardening (#339 follow-up)
00000000000000. Juan approved closing the warm follow-ups → **PR #340**
   (`06b979d`, branch feat/260814-health-guardrail-hardening): absent
   TIME_BUDGET_MINUTES in the production workflow now WARNs (engine
   default 0 = budget disabled = 180-min hard-kill risk; worker-key
   absence stays a note — default 8 AT cap, asymmetry documented
   in-code); worker counts <1 WARN as non-positive. +4 tests (0/neg/
   boundary-1/absent split); at-cap fixture given valid budget. Suite
   1375+132 green; live smoke vs real workflow still OK. ctx.client
   pre-auth cosmetic finding intentionally SKIPPED (triaged, closed).
   Commit-body test count "1378" is a typo (1375 correct — noted in
   PR body). Pending: Juan merges #338 + #340; watch tomorrow's
   ~02:20 UTC cron for first scheduled green.

## Previous (2026-08-14 22:05 CDT) — #339 MERGED (`2cb20ab`); FIRST GREEN health run verified; #338 refreshed
0000000000000. Juan merged #339 (02:48 UTC). Manual dispatch run
   31860218831 on merged master = **success, Overall status: OK** —
   first green system-health run ever; all checks passed incl. the
   new production-workflow guardrail parse (8/8/165/180). Nightly
   02:20 UTC Aug 15 run had fired 28 min PRE-merge on 864cf09 (last
   legacy failure — expected). #338 follow-up done: merged master
   into the branch (brings shipped script; prevents another
   stale-base bot round) + replaced the KNOWN BROKEN callout with a
   dated FIXED note citing #339 + run 31860218831; pushed `8c06bdb`,
   awaiting Juan's merge. Post-merge bot refinements on #339 code
   (absent-TIME_BUDGET leniency vs pipeline/config.py:106 default;
   0/negative worker counts pass cap; ctx.client set pre-auth)
   remain UNTRIAGED — offered as a small follow-up PR on master.

## Previous (2026-08-14 17:55) — GSD quick 260814-me8: #339 vacuous-guardrail Greptile fix pushed (`881a1ef`); MERGEABLE
000000000000. Ran via GSD quick lane (opus planner → sonnet executor →
   haiku verifier, all PASS): new `check_production_workflow_config`
   in validate_system_health.py parses weekly-excel-generation.yml
   DIRECTLY (stdlib regex; comment-stripped; `\|\| 'N'` GitHub-
   expression fallbacks resolved as the scheduled-run value) and
   grades PARALLEL_WORKERS/_DISCOVERY ≤8 + TIME_BUDGET_MINUTES
   strictly < max timeout-minutes; missing workflow file = CRITICAL;
   values redacted/truncated before report echo. Env check kept,
   relabeled process-env-only. Commits `9690cdd` (code, 14 new tests
   → 35 in file) + `881a1ef` (GSD docs: PLAN/SUMMARY/STATE row).
   Suite 1371+132 green; live smoke vs real workflow = STATUS_OK
   (8/8/165/180, no current drift). Workflow file untouched
   (protected). GSD artifacts ride PR #339 via tracked .planning/.
   Note: gsd-tools shim at ~/.claude redirects to a BROKEN .codex
   plugin cache copy (missing lib/cli-exit.cjs); worked around via
   ~/.claude/plugins/cache/gsd-core/.../bin/gsd-tools.cjs — repair
   pending (npm install && npm run build:lib in the codex cache).

## Previous (2026-08-14 15:35) — #338 stale-base Greptile finding resolved by merging master into the branch (`4e4d039`)
00000000000. Round-2 Greptile finding on #338 ("PRICE_VARIANCE_IN_RISK
   not implemented") was a STALE-BASE artifact: the branch forked at
   `3711b92`, before #336's squash (`359a073`) added
   `_price_variance_in_risk`. Doc text is correct against master, so
   the fix was merging origin/master into the branch (clean, no
   conflicts) — NOT rewording the doc to describe pre-#336 behavior.
   Suite 1336+132 green on the merged branch; #338 MERGEABLE at
   `4e4d039`. Lesson: verify bot findings against the branch's
   merge-base before "fixing" docs that are right on master.

## Previous (2026-08-14 15:05) — PR #339 OPEN: maintained validate_system_health.py (nightly workflow fix)
0000000000. **#337 MERGED by Juan (19:15 UTC).** Then Juan approved
   adding the missing health entry point → **PR #339** opened:
   `validate_system_health.py` + 21 offline tests + gitignore +
   ledger entry. Matches system-health-check.yml's EXISTING contract
   (always writes generated_docs/system_health.json, exits 0 when
   written; evaluate step owns pass/fail) → **workflow file untouched**
   (protected area). Read-only, ≤2 API calls/run, no secrets/PII in
   output. Full suite 1357 passed +132 subtests; local smoke run
   verified (facade probe green after Windows UTF-8 subprocess fix —
   lesson in ledger). **Pending:** Juan merges #338 + #339, then
   remove the KNOWN BROKEN callout from docs/sync-job-run-logs.md;
   first green nightly run confirms end-to-end.

## Previous (2026-08-14 14:35) — #338 Greptile fixes pushed (`fd55190`); MERGEABLE
000000000. All 3 Greptile findings on **#338** (docs/sync-job-run-logs.md)
   verified VALID against master and fixed, docs-only: (1) audit risk
   is a per-RUN count ladder (0/≤3/>3 via `_risk_level_for`), not
   per-anomaly dollar-delta — doc now says so + price-variance
   report-only default; (2) `validate_system_health.py` does NOT
   exist → system-health-check.yml fails nightly (last 3 runs
   failure) — documented KNOWN BROKEN, intended-vs-actual;
   **follow-up decision for Juan: add the entry point or repoint the
   workflow (protected area)**; (3) Snyk: only code/iac tests carry
   `|| true`; monitor + SARIF upload unguarded; missing token ≠
   silent skip. No workflow/code touched.

## Previous (2026-08-14 13:30) — #337 Greptile fix pushed (`874020e`); still MERGEABLE
00000000. Greptile finding on **#337** fixed (valid): the new hold-gate
   ledger entry cited `snapshot_drift.py` line numbers (465 gate /
   512 log) — replaced with symbol refs (`_apply_holds()` gate +
   "🔒 Snapshot-drift hold" INFO line, verified still the ONLY
   changed_by log site). Docs-only commit `874020e` via temp
   worktree; older merged ledger entries left as-is (append-only).
   Repo-local `core.longpaths=true` set (Windows checkout fix).

## Previous (2026-08-14 13:15) — PR #336 MERGED (squash 359a073); #337 conflict pre-resolved → MERGEABLE; vault synced
0000000. Juan merged **#336** (price-variance demotion live on master —
   next scheduled run should report risk_level LOW/MEDIUM with
   anomalies ~575 still visible report-only). **#337** updated:
   merged origin/master into the branch, resolved the expected
   living-ledger EOF conflict (both blocks kept, chronological,
   merge commit `553a068`) → GitHub reports MERGEABLE; one-click
   for Juan once checks finish. Second brain synced: project page
   close-out (Open items → CLOSED, durable lessons 4–7) +
   wiki/log.md 2026-08-14 entry. Local master pulled to `afceb29`.

## Previous (2026-08-14 MIDDAY) — queue executed: PR #336 (demote price-variance from risk) + PR #337 (hold gate ON) both OPEN; mismatches=0 confirmed
000000. **Run 31813915527 (15:19 UTC): rate-sanity mismatches=0** —
   both repairs verified at production scale; no new automation-race
   hits. Drift run 3: candidates=110 all legit (manual=40,
   unclassified=70, self_fire=0, holds=0). **PR #336**
   (`feat/260814-demote-price-variance-risk`): `_total_issues_for_risk`
   shared helper + `PRICE_VARIANCE_IN_RISK` (default false); detector
   stays report-only; 13 new tests; suite 1336+132 green; ledger
   `[2026-08-14 11:10]`; Greptile review fixes pushed (`f9e82ad`):
   typed test helpers + flag documented in configuration-environment.md
   + `price_variance_in_risk` advanced_options dispatch passthrough. **PR #337**
   (`feat/260814-enable-drift-hold-gate`): SNAPSHOT_DRIFT_HOLD_ENABLED
   → 'true' in workflow env + IN-04 resolved (changed_by kept —
   automation-only by construction, verified); ledger `[11:25]`.
   **Merge #336 FIRST; #337 will then show a trivial ledger conflict
   (both append at EOF) — keep both blocks, chronological order.**
   After merge: expect audit risk_level LOW/MEDIUM (anomalies still
   reported ~575), holds=0 steady state.

## Previous (2026-08-14 AM) — both underbilled rows REPAIRED (Juan-approved API re-save) + drift steady state ACHIEVED
00000. **Repair executed + verified** (ledger `[2026-08-14 10:05]`):
   91718610 → $113.68 (Backup 83; wk-08-09 Excel REGENERATED by run
   31805121266); 91173728 → $1,179.36 (Backup 73; wk-08-16 file
   regenerates next scheduled run via hash change). Working idiom:
   same-value write = Smartsheet no-op; text→number Quantity
   type-flip forces recalc. Snapshot Dates NOT re-stamped; no
   automation revert on either edit (consistent with the 08-13
   automation fix). Run 31805121266: rate-sanity mismatches=1 (row 1
   pre-run fix) → expect 0 next run. **Drift steady state:
   candidates=0 seeded=155 unchanged=200,765 holds=0 → hold-gate PR
   (SNAPSHOT_DRIFT_HOLD_ENABLED) unblocked, awaiting Juan.**

## Previous (2026-08-13 NIGHT) — 2 rate-sanity mismatches IDENTIFIED (read-only repro) + legacy-detector verdict: era gate insufficient
0000. **Juan confirmed the Smartsheet automation UI trigger fix is DONE**
   (queue item 4 → future repair sweep unblocked). Read-only local
   repro (scratchpad driver, detector-only) matched burn-in counters
   and identified the 2 mismatches — **both underbilled exactly one
   unit** (actual = rate × (qty−1), stale Install-Quantity formula
   class): WR 91718610 / SAA-DE-20 / Inst / qty 2 ($56.84 vs
   $113.68; ProMax Backup 82/83 + Intake Promax 9) and WR 91173728 /
   DEC-20AL-C / Inst / qty 4 ($884.52 vs $1,179.36). **Juan action:**
   check Quantity vs Install Quantity on those rows, re-save to
   recalc — upstream fix only. **Legacy `_detect_price_anomalies`
   measured:** 575 → 239 flags under the rate-sanity era gate (risk
   still HIGH); per-(WR,CU) re-base explodes (5,192–6,968) —
   recommendation: retire/demote (exclude from risk ladder or
   env-flag off), needs Juan's go. NEW gap: audit's "AUDIT: Risk"
   Sentry alert produces ZERO org events in 7d (suspect oversized
   audit_results context dropped at ingest + T-ISX-01 tension).
   No production code changed. Ledger `[2026-08-13 23:00]`.
   **ROOT CAUSE CONFIRMED via cell history (`[2026-08-14 00:50]`):**
   both mismatches = automation-triggered recalc racing a human qty
   edit (correct price reverts 2-3s later to stale-qty price).
   Exact rows: Backup 83 row 5538447881863044 (91718610, wk 08-09,
   already underbilled $56.84) + Backup 73 row 1166598725369732
   (91173728, **wk 08-16 CURRENT — re-save before next run** or it
   bills $294.84 short). Both predate Juan's 08-13 automation fix;
   rate-sanity counters on future runs verify whether the race died.

## Previous (2026-08-13 EVE) — #334 MERGED + **billing_audit DDL APPLIED TO PRODUCTION** → PR #335 OPEN (schema.sql mirror)
000. **DDL LIVE (Juan-approved, via Supabase MCP):** 3 migrations on
   project `poeyztlmsawfoqlanucc` — drift tables
   (`snapshot_provenance`, `snapshot_drift`) + `lookup_snapshot_
   provenance_bulk` RPC + search_path pin. WR-03 RESOLVED at apply:
   RLS + `service_role_all` policies on both new tables (sibling
   parity). Verified live: tables/RLS/policies present, RPC callable
   (0 rows = correct empty state), `pgrst_ddl_watch` auto-reloaded
   PostgREST, advisors clean of new findings. schema.sql mirrored →
   **PR #335 OPEN** (`chore/260813-schema-sql-mirror-applied-ddl`,
   c6fa488; suite re-run 1323+132). **BURN-IN RUN 1 CLEAN** (GH run
   31761117011): drift seeded 200,765 / candidates=0 / holds=0, RPC
   active (no PGRST202); rate-sanity mismatches=2 (was 115,272),
   out_of_scope=115,340. NEW FINDING: risk HIGH now driven by LEGACY
   price-variance detector (575 anomalies, unscoped) — candidate
   follow-up needs Juan's go. Hold gate stays OFF until a few clean
   runs. Ledger `[2026-08-13 22:00]`. Remaining Juan items:
   Smartsheet automation UI trigger fix + remediation prompt (still
   REQUIRED before any snapshot-date repair sweep); IN-04 PII call.

## Previous (2026-08-13 PM) — #332 & #333 MERGED → PR #334 MERGED: RPC bulk provenance read + audit follow-ups (GSD 260813-nhn)
00. **GSD quick task 260813-nhn → PR #334 OPEN** (branch
   `feat/260813-nhn-snapshot-store-followups`, 8 commits
   8918dea..6e78ab3). Closed: P2/#333 weekly-fallback flag parity
   (`RATE_RECALC_WEEKLY_FALLBACK` AND column mapping); WR-05 24-test
   snapshot_store characterization oracle; WR-02 RPC bulk provenance
   read — `lookup_snapshot_provenance_bulk(p_keys jsonb)` appended to
   billing_audit/schema.sql (manual apply WITH the 2 jqx blocks, then
   `NOTIFY pgrst, 'reload schema'`), Python RPC-first w/ PGRST202
   probe → CHUNKED .in_ fallback capped at `_FALLBACK_MAX_CHUNKS=50`;
   sibling fix: upsert chunked (1000/POST). Safety review
   (SAFE-WITH-NOTES) fix round `d63457c`: zero-row RPC corroboration
   probe (mis-applied RPC returning [] can no longer rebase every
   baseline — empty-table probe distinguishes genuine first sight),
   fallback cap, log fix. RESEARCH quantified: at 199,717 keys the
   old two-.in_ read = ~3.4-4MB GET (would fail on DDL apply);
   upsert = ~40MB POST. Status vocabulary frozen at
   success/no_row/fetch_failure/unavailable. Suite **1323+132**
   (39 new); haiku PASS 8/8 + re-verify PASS; no pipeline/ changes.
   WR-03 RLS deliberately NOT included (Juan's DDL call). IN-04
   (changed_by email at INFO) still open — Juan's PII-posture call.
   **Next: Juan reviews/merges PR #334.**
0. **GSD quick task 260813-m5j (research→plan→execute→verify):** the two
   post-merge #332 review findings fixed on
   `feat/260813-m5j-rate-sanity-scope-hardening` → **PR #333 OPEN**.
   KEY RESEARCH CORRECTION: Copilot's "restrict to subcontractor
   membership" was INVERTED — the incident sheet (Backup 86,
   1824542300262276) is one of 110/115 NON-subcontractor sheets; the
   gate now EXCLUDES `__is_subcontractor` rows (reason
   `subcontractor_basis`). Codex F1: weekly fallback fail-closed via
   `_rate_sanity_snapshot_column_index()` from source_sheets
   column_mapping (latent today: 115/115 sheets map Snapshot Date).
   VAC-on-non-sub stays in scope (test R4). Suite 1284+132,
   haiku-verifier PASS 8/8. Commits 4245450/a7c27b2/63c38c7/ca77332.
   **Next: Juan reviews/merges PR #333.**
1. **Rate-sanity scoping (task 4 of the 08-13 list, Juan's GO):**
   `_rate_sanity_in_scope()` in `audit_billing_changes.py` reuses the
   SUB-01/D-08 era gate (`_resolve_rate_recalc_cutoff_date`, cutoff
   `_AEP_BILLABLE_CUTOFF` 2026-04-12, weekly-ref fallback). Pre-cutoff/
   undatable rows → new `rate_sanity_out_of_scope` counter, never
   checked. Kills the 58% old-rates false-positive class (115,272/
   199,717 rows) that pinned risk HIGH every CI run. TDD, 8 new tests.
2. **jqx review nits closed:** IN-01 utcnow → now(utc); IN-02 module
   logger; IN-03 cross-pin comments; IN-05 snapshot_store NEVER-raises
   made real + first direct tests (`tests/test_snapshot_store.py`,
   chips at WR-05); IN-07 shared `_risk_level_for()`. NOT done: IN-04
   (PII posture — Juan), WR-02 (RPC), WR-03 (RLS/DDL — Juan).
3. **WR_FILTER skill-doc fixed** (TEST_MODE-only, grouping.py:1222) +
   runbook blog rewritten for scoping + ledger `[2026-08-13 15:30]`.
4. **Suite 1274 passed** (1263 + 11 new), py_compile clean. Branch
   `feat/260813-rate-sanity-current-cycle-scope`, 3 commits
   (93a32dd feat / 5320b1f fix / 6e51313 docs; IN-07 diff rides in
   the feat commit). **Next: Juan reviews/merges PR #332.** Juan's own
   ops queue unchanged: Smartsheet automation UI fix → remediation
   prompt on other DB sheets → apply 2 DDL blocks in
   billing_audit/schema.sql → burn-in → enable hold gate.

## Previous work (2026-08-12) — SAA-DE-20 overbill root-caused (upstream data, not code) + Snapshot Date automation defect proven + quick task 260812-isx in flight
1. **Field-reported wrong pricing solved:** WR 91916464 / Point 27 /
   SAA-DE-20 showed 3 EA @ $341.04 (should be 3 × $56.84 = $170.52).
   Root cause: stale Smartsheet `Install Quantity` formula cell on
   "Resiliency Promax Database Backup 86" (Quantity edited 6→3 on
   2026-08-06, formula never recalculated). Contract rate and Python
   pipeline both verified CORRECT (primary variant is pass-through by
   design). Juan re-saved the row → now $170.52; next cron regenerates
   the WE 080926 file via hash change. Full evidence chain in
   `memory-bank/living-ledger.md` `[2026-08-12 13:40]`.
2. **Snapshot Date automation defect proven via cell history:** the
   per-sheet "record a date" automation uses a row-change trigger with
   "Units Completed? is checked" as a condition, so ANY edit (even
   same-value saves and bulk touches) re-stamps Snapshot Date to today
   → units jump billing weeks → audit errors. Fix is UI-side per sheet:
   field-scoped trigger ("Units Completed? changes to Checked") +
   "Snapshot Date is blank" write-once condition; fix the template
   sheet so backup copies inherit it. Recommendation delivered to Juan;
   NOT yet applied (his action).
3. **SESSION HANDOFF (2026-08-12 ~16:35 CDT) — resume points:**
   - **PR #329 Greptile fixes DONE + PUSHED** (`64d7249`/`e003124`/
     `8802e98`, suite 1230+130). Latent quirk untouched:
     risk_trend.json write no-ops on fresh generated_docs/.
   - **Quick task 260812-jqx EXECUTED (reviews in flight):** branch
     `feat/260812-jqx-snapshot-drift-audit` stacked on isx tip
     `3f7be82`. Commits: `8db2845` (planning docs), `55329a1` (drift
     detection, zero extra API calls: pipeline/snapshot_drift.py +
     billing_audit/snapshot_store.py + additive schema.sql + config +
     orchestrate seam), `c58a9bd` (cell-history classifier, 40-row cap
     ~2s pacing sub-budget), `0a68aeb` (hold-prior-week override +
     audit risk wiring + post-seam Sentry capture on holds), `0b5051a`
     (SUMMARY docs). Full suite **1257 passed + 132 subtests** (27 new
     tests), zero regressions; grouping/excel zero hunks; orchestrate
     2 hunks. Deviations: test-only budget-boundary flake fix;
     plan-check Sentry warning honored. Locked decisions held: hold
     gate default OFF, never hold manual edits, fail-open gating/
     fail-closed logging, no AUDIT_SHEET_ID mutation, DDL manual-apply.
     **Reviews DONE:** gsd-verifier 8/8 zero gaps; haiku rubric 10/10
     PASS; code review 2 Critical / 5 Warning / 7 Info → fix round
     `a56190c` (CR-01 upsert gated on fetch status — no baseline
     rebase on failed read), `81da106` (CR-02 null-prior-date holds
     skipped), `7a58c62` (WR-01 unparseable ts → unclassified;
     window env-tunable SNAPSHOT_DRIFT_UNITS_WINDOW_MINUTES default
     15; WR-04 test pacing zeroed). Suite **1262 + 132 subtests**
     (~13s). Deferred to PR follow-ups: WR-02 (bulk .in_ → RPC),
     WR-03 (RLS on new tables — Juan's DDL call), WR-05 (direct
     snapshot_store tests), info nits. **SHIPPED: PR #330 → master**
     (#329 was squash-merged as `647a688` at 20:33Z, isx branch
     deleted; jqx rebased onto origin/master — new SHAs
     b115e63..d3333e4 + this ledger commit — suite re-run green
     post-rebase, force-pushed with lease). Local master is stale;
     `git switch master && git pull` when convenient.
     **Greptile round (post-open): `4104ca1`** — unclassified drifts
     no longer rebase the provenance baseline (classification-aware
     finalization; unclassified rows retry next run). Suite 1263+132.
     **Live dry run (SKIP_UPLOAD, 53min):** drift audit no-op path
     verified on 199,815 real rows (CR-01 skip observed live);
     FINDING: #329 rate-sanity flags 115,272/199,717 rows (58% — old
     historical rates vs New-Rates basis) → risk_level HIGH every CI
     run; no Smartsheet writes exist (AUDIT_SHEET_ID never written);
     Juan to choose kill-switch vs scoping follow-up. Also:
     WR_FILTER only works with TEST_MODE (grouping.py:1222) — the
     run-billing-pipeline-locally skill table is wrong on this.
   - **A1/A4 VERIFIED LIVE (WINDOWS #1 closed):** read-only probes
     with Juan's token proved newest-first history + automation
     identity, captured the full Point 27 drift-and-revert chain, and
     CORRECTED the signature: automation batches stamps (legit writes
     up to 4m22s after the check → 15-min window), and Weekly
     Reference Logged Date is automation-WRITTEN (repair must revert
     it too). Ledger `[2026-08-12 17:05]`. Backup 86 scanned clean
     (no stamps ≥ 08-08). Note: Juan's `.env` names the token
     `SMARTSHEET_API_KEY`; the pipeline reads `SMARTSHEET_API_TOKEN`.
   - **Juan's own actions pending:** Smartsheet automation trigger fix
     in UI per living-ledger [2026-08-12 13:40] (field-scoped trigger
     + "Snapshot Date is blank" condition, per sheet + template) —
     REQUIRED before any snapshot-date repair sweep (writes would be
     re-stamped); run the remediation prompt with a Smartsheet-capable
     AI; review/merge PR #329; later: apply jqx DDL (2 blocks in
     billing_audit/schema.sql), verify A1/A4, enable hold gate after
     burn-in.
4. **Quick task 260812-isx (GSD quick) COMPLETE → PR #329 OPEN:**
   report-only rate-sanity audit check (Units Total Price vs expected
   New-Rates rate × Quantity via `_SUBCONTRACTOR_RATES`, kill-switch
   `RATE_SANITY_AUDIT_ENABLED`). Commits a7f5d77/2cb9897/ad3fa19 +
   docs c61bacb on branch `feat/260812-isx-rate-sanity-audit`
   (local master reset to origin/master — nothing pushed to main).
   Full suite 1228 passed + 130 subtests, 0 regressions; independent
   haiku-verifier PASS 8/8 (report-only, no hunks in pipeline/ or
   generate_weekly_pdfs.py). Next: Juan reviews/merges PR #329; apply
   the Snapshot Date automation UI fix per living-ledger
   `[2026-08-12 13:40]`.

## Previous work (2026-07-22) — Phase 08 SDK 4.3.0 migration EXECUTED (both plans)
1. **Phase 08 executed via `/gsd-execute-phase 08`** on branch
   `feat/phase-08-sdk-430-migration` (unpushed; no PR yet). Wave 1 (08-01,
   merge `6334531`): SDK 4.3.0 installed (env upgrade 3.9.0→4.3.0), dead
   27-line 3.x re-export shim removed from `generate_weekly_pdfs.py`, Gate 1
   baseline 178→177 (`_exc_name`), six gates ALL PASSED + full suite green.
   Wave 2 (08-02, merge `72f72ef`): `requirements.txt` pin lifted to exact
   `smartsheet-python-sdk==4.3.0`, Living Ledger entries added, D-06/D-07
   rollout+rollback runbooks captured in `08-02-SUMMARY.md`.
2. **D-05 live read-only probe: APPROVED by Juan** (bounded
   `SKIP_UPLOAD=true WR_FILTER=... MAX_GROUPS=5` run, real transport, 2,771
   groups validated, 5 Excel generated, zero SDK error-shape drift).
   **Finding:** `SKIP_UPLOAD=true` is NOT fully read-only — the
   delete-old-attachment step still ran (WR 89881161 weeks 072025/081725
   deleted; hash withheld → next weekday cron regenerates + re-uploads
   automatically; Juan chose wait-for-cron). Logged in phase
   `deferred-items.md` + Living Ledger; follow-up fix candidate: gate the
   delete on SKIP_UPLOAD too.
3. **Test hermeticity fix (`4aa19ff`):**
   `tests/test_entrypoint_no_double_import.py` now sets
   `SMARTSHEET_API_TOKEN=''` (was `pop()`) — the engine's `load_dotenv()`
   re-injected the token from Juan's new repo-root `.env`, flipping the
   banner test into a real multi-minute API fetch (180s timeout). Empty
   string survives dotenv (no override) and stays falsy → synthetic path.
   Post-merge gate green: 1164 passed + 130 subtests.
4. **Security gate CLEARED (2026-07-22 PM): `/gsd:secure-phase 08` run.**
   gsd-security-auditor verified 5/6 threats closed; the 6th (T-08-03,
   `SKIP_UPLOAD=true` still ran the attachment DELETE — materialized in
   the D-05 probe) was **fixed same-session, Juan-approved**: `dry_run`
   param on `delete_old_excel_attachments` /
   `cleanup_untracked_sheet_attachments` / `purge_existing_hashed_outputs`
   (`pipeline/cleanup.py`), wired `dry_run=SKIP_UPLOAD` at all 5 mutating
   call sites in `pipeline/orchestrate.py`. New invariant (ledger
   `[2026-07-22 14:37]`): SKIP_UPLOAD=true ⇒ zero Smartsheet mutations.
   TDD'd (`tests/test_skip_upload_delete_gating.py`, 7 tests; signature
   pin → v6); full suite **1171 passed + 130 subtests**. Threat register:
   `.planning/phases/08-*/08-SECURITY.md` (6/6 closed, threats_open: 0).
   Deferred item "SKIP_UPLOAD deletes prior attachments" marked RESOLVED.
5. **Nyquist gate CLEARED (2026-07-22 PM): `/gsd:validate-phase 08` run.**
   0 gaps; all 6 task commands re-run live and green (six gates PASSED —
   note: gate run took ~35 min because TEST_MODE + `.env` token does real
   reads; unset the token for local gate runs). New automated row
   08-SEC-T1 covers the SKIP_UPLOAD zero-mutation invariant. Commits
   `fa80b48` (validation), `8777246` (security docs), `442cb92` (fix).
6. **UAT COMPLETE (2026-07-22 ~16:30 CDT): `/gsd-verify-work 08` — 6/6
   passed, 0 issues** (commit `d78e7d5`). Full-UAT in
   `.planning/phases/08-*/08-UAT.md`; the old 1-test `08-HUMAN-UAT.md`
   closed (its attachment-loss check = Test 5, Juan-confirmed: WR
   89881161 self-healed via cron, WR 89708709/90093002 intact).
   `08-VERIFICATION.md` flipped `human_needed` → `passed` (the human
   gate it awaited was exactly Test 5). Roadmap/STATE/PROJECT transition
   had already run in the prior session — no re-transition.
7. **PR #286 OPEN** (branch pushed 2026-07-22 ~16:40 CDT). **Review fix
   shipped (quick task 260722-nst, ~17:35 CDT):** the 6th mutating call
   site — `run_claimer_remediation` in the isolated REMEDIATE_CLAIMERS
   branch (`pipeline/orchestrate.py` ~452) — now uses
   `dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD` (test `458d7e5`, fix
   `60d0473`, docs `1b6ff9a`; TestRemediationGatesOnSkipUpload pins it;
   8/8 gating tests green; haiku-verifier PASS 4/4). SKIP_UPLOAD=true ⇒
   zero mutations now covers ALL 6 call sites. **Next per D-06:** merge
   in a weekday daytime window right after a green scheduled run, then
   fire ONE watched `workflow_dispatch` canary; then
   `/gsd-verify-work 09`. Also: Juan's `.env` line-1 token
   surfaced in an editor selection into chat — rotation recommended.
   Carry-forward WARNING for next phase's register: `TEST_MODE=true` with
   a real token still performs real Smartsheet reads.

## Current milestone
**v1.3.1 — Smartsheet API resilience & silent-failure hardening** (follow-up to
Phase 09, **✅ COMPLETE & MERGED, PR #281 → `8c51a3c`** on 2026-07-01 UTC).
Shipped from `fix/api-resilience-silent-failures` (cut fresh from
`origin/master`; branch deleted on merge). Three change areas, all TDD'd, all 6
gates green, PII scrubs dummy-transport-verified:
1. **Transient-retry resilience (the API errors).** New `pipeline/retry.py`
   `smartsheet_call_with_retry()` — retries the transients the SDK does NOT
   itself drive to success (generic `ApiError` **code 4000**, server timeout,
   rate limit, network drops), **bounded total sleep** so it can't blow
   `ATTACHMENT_PREFETCH_MAX_MINUTES` / `TIME_BUDGET_MINUTES`, **raises on
   exhaust**. Applied to the hot bare call sites (`fetch.py` per-sheet
   `get_sheet`, `discovery.py` folder browse + validate `get_sheet`); the
   discovery drop handler (was silent `return None`) now **escalates via
   `observability.sentry_capture_sheet_drop`** — a SANITIZED `capture_message`
   (NOT `capture_exception`, which would attach `include_local_variables`
   frames holding sampled billing-row PII) that TAGS the event
   `error_location=discovery_sheet_drop`; the global `before_send` hook
   (`_scrub_sheet_drop_frame_vars`) then strips every frame's data-bearing
   fields from that tagged event (a scope event-processor runs too early —
   `attach_stacktrace` appends the thread stacktrace after scope processors
   run) — so a dropped source sheet (= missing billing) is loud without
   exfiltrating row data. The 3 duplicate inline
   retry blocks in `orchestrate.py` (target/PPP attachment prefetch + upload)
   were **consolidated** into the helper. The upload worker is **behavior-
   preserving** vs the original inline loop (passes the prefetch cache every
   attempt). Codex flagged a retry idempotency gap in `SUPABASE_HASH_STORE_
   AUTHORITATIVE` clean-filename mode (ON in prod), but it is **not solvable by
   attachment inspection** (clean names carry no timestamp/hash, so a freshly
   committed file is indistinguishable from a stale same-identity one — both
   delete-then-reupload and preserve-on-identity are unsafe). Kept the safe
   baseline (benign self-healing duplicate on a rare retry, reconciled next
   run); the proper fix (upload-then-delete-by-attachment-age) changes the
   delete→upload guardrail and is **deferred to a dedicated PR**. Now-dead
   `time` / `ss_exc` imports removed.
2. **F1 (pre-existing deferred finding) fixed.** `grouping.py` sub-helper
   `no_history` fallback was silent — `resolve_claimer` returns
   `('use', current, 'current', 'no_history')` and the `action=='use'` branch
   zeroed the reason, so the per-WR WARNING never fired. One-line propagate-
   the-reason fix + reason-branched remediation (`no_history` vs `fetch_failure`
   vs `unavailable`); the 2 dead-path tests (mocked an impossible `action`)
   rewritten to the **real** `resolve_claimer` contract (red-first proven).
3. **Sentry PII hardening across all THREE data planes** (review-driven).
   Row PII (WR/week/foreman/dept/job/price) must never reach Sentry. Closed:
   (a) **event frames** → `before_send` `_scrub_sheet_drop_frame_vars` (a scope
   event-processor runs too early — `attach_stacktrace` appends thread frames
   after it); (b) **breadcrumb `message`** → `before_breadcrumb` drops any crumb
   whose message hits `_PII_LOG_MARKERS` (`LoggingIntegration(level=INFO)` turns
   every INFO/WARNING into a breadcrumb *unconditionally*, independent of the
   `SENTRY_ENABLE_LOGS` gate); (c) **breadcrumb `data`** → same hook strips
   row-identifier keys via the new `_PII_BREADCRUMB_DATA_KEYS` registry (manual
   crumbs carry PII in `data` under a benign message — e.g. the skip/regenerate
   crumbs). All three empirically verified with a real `sentry_sdk.Client` +
   dummy transport.

**Deferred (dedicated PR):** the retry-idempotency gap in
`SUPABASE_HASH_STORE_AUTHORITATIVE` clean-filename mode is **not solvable by
attachment inspection** (clean names carry no timestamp/hash, so a freshly
committed file is indistinguishable from a stale same-identity one). Kept the
safe behavior-preserving baseline (benign self-healing duplicate on a rare
retry, reconciled next run); the proper fix (upload-then-delete-by-attachment-
age) changes the delete→upload guardrail.

**Status:** MERGED. `run_6_gates.sh` exit 0 at merge (G1 178 names · G2 108
facade · **G3 1149 pytest** +130 subtests · G4 mypy 56→56 · G5 py_compile · G6
21-key TEST_MODE run). **All findings across 8 reviewer passes resolved**
(4 real Codex fixes: before_send frame scrub · attribution `unavailable`≠
`no_history` · breadcrumb message-scrub · breadcrumb data-scrub; 2 sys.path
test bootstraps; 3 Copilot doc-accuracy nits incl. the retry.py 4000-vs-
InternalServerError contract). 0 unresolved review threads; final Copilot
review generated no new comments. Production guardrails UNCHANGED (change-key,
delete→upload order, `@cell`=0, `PARALLEL_WORKERS≤8`, filename/attachment). See
`memory-bank/living-ledger.md` (newest entries) for the full what/why/rules.

## Active work
**🔧 WR 90968595 missing-rows bug: ROOT CAUSE CONFIRMED, fix in PR (2026-07-06).**
Not attribution/filtering — a crash-consistency bug in the Sub-project E hash
store: failed run 28752355941 (7/5, runner lost) upserted the new group hash
during emission but died before the upload phase, so under authoritative clean
filenames the skip gate deadlocks ("unchanged + attachment exists") and the 7/5
ProMax rows never publish; regen can't recover. Fix: `orchestrate.py` defers hash
upserts and flushes ONLY after the group's upload legs succeed (withhold on
error/dry-run → regenerate next run). 4 regression tests; suite 1153 passed +130
subtests. **Pending:** merge fix PR (stacked on #282) → one-time remediation
`workflow_dispatch` `advanced_options=regen_weeks:070526` → verify the 7/5 rows in
the regenerated file → archive debug session `wr-90968595-rows-not-pulled` +
apply the held second-brain write-back packet. Full rule: newest
`memory-bank/living-ledger.md` entry.

## History pointer
**Phase 09 — engine modularization (✅ COMPLETE & MERGED, PR #280 → `889ca2e`).**
10,476-line `generate_weekly_pdfs.py` → 13-module `pipeline/` package behind a
709-line thin facade, zero behavior change, 7 waves each 6-gate-verified. Full
wave-by-wave history in `memory-bank/living-ledger.md`.

_Paused alongside:_ **v1.2 — smartsheet-python-sdk 4.0.0 migration** (Phase 08).
SDK pinned `<4.0.0` in `requirements.txt` as a CI import hotfix; the breaking
4.0.0 migration is not yet executed. **Now unblocked** (Phase 09 merged) but
still touches the same engine — coordinate before starting.
