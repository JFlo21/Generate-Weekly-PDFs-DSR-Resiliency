# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-09-03 01:25 CDT (06:25Z) · **overwrite-in-place each session** — this is
the canonical "where the project stands" landing spot for the global Stop write-back reminder. Cap ≤ 120
lines (`align-instruction-files` skill); history goes to `memory-bank/living-ledger.md`, never here._

_Latest ledger entries: `[2026-09-03 13:55]` (Phase 12 ownership contract, waves 2–3), `[2026-09-03 11:05]` (Greptile source-1 in-week guard fix on PR #387), `[2026-09-03 01:20]` (Phase 12 wave 1 — OWN-03 backfill tracer, review fix round, PR #387),
`[2026-09-02 22:05]` (instruction-file alignment run 1 — what moved where),
`[2026-09-02 21:20]` (memory-bank pages retired; pre-ledger April-2026 history imported),
`[2026-09-02 20:45]` (align skill), `[2026-09-02 20:20]` (bootstrap audit), `[2026-09-02 18:15]`
(Phase 12 plan-phase, D-12-A / D-12-B)._

## Where the project stands

- **Milestone v1.4 "Supabase Run Memory":** Phase 10 closed 2026-08-25 (6/6), Phase 11 closed
  2026-08-31 (8/8, INC-05 retirement shipped), Phase 11.1 closed 2026-09-02 (4/4; PR #384 `13e8e76`;
  canary run 33683979474 met SC-1 — `⚡ Phase 1 complete` 37.7 s, was 3,214 s). **Phase 12 (Ownership —
  last known foreman as of the week) is PLANNED:** 6 plans / 4 waves, checker 0 blockers,
  **wave 1 (12-01) EXECUTED 2026-09-03 → PR #387** (`feat/phase-12-ownership`; waves 2–4 not started; phase not
  marked complete). Phase 13 = the deferred `wr_week_ownership` table (D-12-A).
- **Production posture:** `pipeline_memory` write path ON since #353 (`RUN_MEMORY_WRITE_ENABLED: '1'` on
  the `Generate reports` step only); `RUN_MEMORY_INCREMENTAL_ENABLED` OFF; change detection and
  attachment identity are `group_state`-backed (local JSON caches retired, INC-05); the Supabase hash
  store is authoritative with clean filenames; `TIME_BUDGET_MINUTES=165` under `timeout-minutes: 180`.
- **Open defects (`docs/ai/known-bugs.md`):** CR-01 (`_is_sentinel_identifier` leading-`_` rule inside the
  protected cleanup path) and WR-01 (top-level `AttachmentParentType` import in `pipeline/orchestrate.py`),
  both scheduled for Phase 12 Plan 12-02. Executor note: the plan's "align to discovery.py's lazy import
  of the same path" wording is wrong — discovery.py never imports that enum; align to its lazy
  `Sheet` / `Folder` import pattern instead.
- **GSD health:** HEALTHY as of 2026-09-02 (the inserted Phase 01.1 is now declared to the parser).

## Latest work (2026-09-03 early) — Phase 12 wave 1 executed: OWN-03 backfill tracer → PR #387

- `/gsd-execute-phase 12` (wave filter 1) on branch `feat/phase-12-ownership` off `560115f`; GSD executor (Sonnet,
  harness worktree) delivered plan 12-01 in 6 commits: `scripts/backfill_claim_time_attribution.py` (dry-run default,
  4-source week-scoped ladder, conflict/unresolved outcomes, gated `--apply` → owner RPC), 40 fixture tests,
  `.gitignore` for the PII report. Merged via `worktree.cleanup-wave` (`c9edd5c`), tracking commit `9d93963`.
- Gates: full suite 1,986 → 1,994 passed; 6-gate harness passed; GSD wave-post gates (schema drift, codebase drift,
  UI) all clear; haiku-verifier 10/10 must_haves.
- **Independent Opus production-risk review found real defects** (blank-role targeting → fabricated helper/vac_crew
  proposals via source 2; per-row source-1 queries; `with_retry` None → silent `[]`; no `.order()` → non-deterministic
  reports; RPC count not reconciled). One Sonnet fix round (`d922d29`, SUMMARY addendum `9607190`) closed all seven
  findings; named-sentinel-only targeting is now the default with `--include-blank-roles` opt-in — **Juan to confirm
  that default before 12-06**. Deferred design items: `--from-report` approval binding, public `ROLE_BY_VARIANT`.
- Also this session: local `master` reset to `origin/master` after PR #385; PR #386 (docs: record the #385 merge).
- **2026-09-03 afternoon → evening — Phase 12 waves 2–3 DONE, phase gates run, PR #388 open (Juan merges):**
  12-02 ✓, 12-04 ✓ (workflow **dispatch-only** by owner re-decision after Opus H1 — the backfill step takes candidates
  only from the sources-1-4 report, which a fresh runner never has, so a cron would be a permanently green no-op; the
  Sunday cron returns in 12-06 with a candidate source), 12-05 ✓ (runbook `ownership-attribution.md`, 4 pages
  rewritten, 20 docs tests, Docusaurus typecheck + build green, ledger `[2026-09-03 13:55]`), 12-03 Tasks 1–3 ✓
  (Juan `approve`d the DDL and **applied it live 2026-09-03 — Task 4 APPROVED**: backup table
  `attribution_snapshot_backup_20260903`, five-tag CHECK confirmed by STEP 2 VERIFY, predicate + RPC created; the
  STEP 0/0b/3/6 answers and the grant list were not reported and are re-checked read-only in 12-06 Task 1),
  12-06 not started (owner-run after merge + apply). Gates: Opus whole-branch integration review **SHIP** (7 seams
  OK; 2 MEDIUM fixed in the SQL, LOW-1 carried), `/gsd-code-review 12` 0 critical / 3 warnings (WR-01 false-zero
  backlog + WR-02 fixed, WR-03 accepted), gsd-verifier **human_needed** (49/62 verified · 0 failed · 13 owner
  items, `12-VERIFICATION.md`), full suite **2,093 passed / 1 skipped / 405 subtests**. `phase.complete 12`
  correctly refuses until 12-06 has a summary. Branch: 41 commits, 30 files, +5.6k/−39.
- **2026-09-03 afternoon — Phase 12 wave 2 executed** on `feat/phase-12-wave-2` (off master `77a675b`, PR #387
  squash `e1b6302` merged 12:11 CDT; `feat/phase-12-ownership` deleted). Three GSD executors in harness worktrees:
  12-02 complete (CR-01 allowlist predicate + WR-01 lazy import, RED→GREEN, suite 2007) then an Opus review FIX-FIRST
  round on its branch (`98b5ea3`: unlisted leading-underscore tokens are now neutral on BOTH sides of the sentinel-
  superseded delete gate via `_is_real_name_identifier`; non-str/whitespace hardening; one-time WARNING on the
  `AttachmentParentType` fallback; suite 2011); 12-03 halted at its Task 3 blocking-human decision (SQL + contract test
  authored; Opus FIX-FIRST round delegated to a Sonnet worker: PII out of the RAISE, full-whitespace btrim, `#variable_conflict`,
  contract test pins payload keys to `_build_apply_payload`); 12-04 authored the source-5 cell-history job + 79-test suite,
  halted at its Task 3 decision, then an Opus FIX-FIRST round (`101489d`: week window `week_ending - 6d`, conflict on
  differing names, `display_value` first, read failure = `error` + exit 7, `_CapReached` defers). **WAVE 2 MERGED**
  (`b00df03`/`683edb3`/`b037c3a`, 13 files, +3,712/-21) — post-merge gate: py_compile OK, suite **2056 passed / 1 skipped /
  386 subtests**; schema-drift / codebase-drift / ui gates clear; 12-02 marked complete in ROADMAP. **Waiting on Juan:**
  12-03 Task 3 (`approve` / `approve-with-correction` / `hold` the one-way Supabase DDL) and 12-04 Task 3 (`approve-cron` /
  `approve-dispatch-only` / `hold` the cell-history workflow). Nothing pushed yet; no PR yet.
- **2026-09-03 late morning — Greptile fix on PR #387 (`988680a`):** source 1 never matched a `row_event`/`row_state` row's own
  `week_ending` to the target week (cross-week owner leak, D-12-A violation missed by every prior gate). Fixed with
  `_in_target_week()` + `week_ending` in the bulk select; NULL week = not in-week; 4 tests added, suite 1,998. Opus
  production-risk review re-run on the fix (handoff constraint). Juan confirmed the named-sentinel-only targeting
  default. PR #386 closed (commit rides in #387). Ledger `[2026-09-03 11:05]`.

## Previous work (2026-09-02 evening) — instruction-file alignment, run 1 — **merged: PR #385 squash `26b3c4f` (23:08 CDT)**

- **Step 0 before:** CLAUDE.md 369 lines (> 150), this file 1,555 (> 120), both mirrors stale since
  2026-08-17, memory-bank pages 67–149 days old, 0 dangling pointers.
- **Step 1** `/gsd-core:health`: W002/W007 ("Phase 01.1 on disk, not in ROADMAP") were a parser miss —
  the checklist regex rejects a pre-colon `(INSERTED)` tag; moved the tag after the colon on one
  ROADMAP line (`d9740f2`) → HEALTHY.
- **Step 2** docs-update, verification half only: gsd-doc-verifier on CLAUDE.md 71/74,
  `docs/ai/architecture` 77/77, `implementation-truth` 94/94, `safe-commands` 44/44, `known-bugs` 19/20
  (WR-01 wording corrected), `decisions` 21/21, PROJECT_BRIEF 14/14, README 37/38 (stale
  `hash_history.json` line fixed), plus AI_CONTEXT_RESUME / sentry-implementation / SECURITY (PR body).
  Canonical-doc generation (README rewrite + 5 new GSD docs) deliberately **skipped** — it would add
  duplicate drifting copies; owner call. Six `memory-bank/*` pages → ≤ 8-line stubs; surviving facts →
  `docs/ai/architecture.md` § Domain model and a rewritten `docs/PROJECT_BRIEF.md`; pre-ledger
  April-2026 history → ledger `[2026-09-02 21:20]`.
- **Step 3** CLAUDE.md 369 → ≤ 150 lines (rules + pointers only). Moves: pipeline flow / cron schedule /
  runner timeouts → `docs/ai/architecture.md`; env-var catalog → `.github/prompts/configuration-environment.md`
  § Operator quick reference; command lists + aspirational `uv` → `docs/ai/safe-commands.md`; ecosystem
  and persona text condensed into CLAUDE.md § Role. `.github/copilot-instructions.md` regenerated.
  **`AGENTS.md` freeze BLOCKED** — the harness-boundary hook denies every ClaudeOS write to that file;
  Juan pastes the `FROZEN MIRROR` header by hand (text in the PR body); skill bumped to v1.1.
- **Step 4** this file cut to ≤ 120 lines; every dropped dated section has a ledger entry except
  2026-08-15 (#340 merge, health system complete) — recorded in `[2026-09-02 22:05]`.
- **Steps 5–7** `docs/AI_CONTEXT_RESUME.md` snapshot added; Step 0 re-run clean; ledger,
  `docs/CHANGELOG_CONTEXT.md`, vault project page + `wiki/log.md` updated; docs-only PR #385 opened.
- **Merge (2026-09-02 23:08 CDT):** Greptile review issue fixed first (`deac60e` — discovery is NOT
  "validated every run"; D-11.1-01 registry-version skip gate documented in CLAUDE.md, `docs/ai/*`, and
  the config quick reference). PR #385 squash-merged as `26b3c4f`; origin's runbook bot added `e7852d6`
  / `560115f`. Local `master` reset to `origin/master`, the branch deleted (all 15 local-only docs commits
  were inside the squash).

## Next

1. Owner: squash-merge PR #387 (wave 1; #386 closed, targeting default confirmed 2026-09-03);
   paste the `FROZEN MIRROR` header into `AGENTS.md` by hand (text in the PR #385 body; the harness-boundary hook
   denies every ClaudeOS write to that file).
2. Owner: merge PR #388 (waves 2–3; 12-03 SQL already applied live). Then a fresh session: `/clear` →
   `/gsd-execute-phase 12` → 12-06 (Task 1 first re-runs the read-only checks Juan did not report: STEP 0 column
   names, STEP 0b zero rows, backup vs live count, spot check, smoke test, UPDATE grant; then dry-run review → apply
   decision → same-UTC-day apply → post-run check); restore the Sunday cron only together with a real candidate
   source. After 12-06: `/gsd-verify-work 12` → `phase.complete 12`.
3. Owner-owned Phase 12 steps stay blocking checkpoints: read-only count of NULL/stale-week `row_event`/`row_state`
   rows for the target row_ids before `--apply` (Opus MED, 2026-09-03); confirm live `attribution_snapshot` column names, apply
   `billing_audit/own03_backfill_attribution.sql`, approve the dry-run report, run `--apply`, restore the source-5
   cell-history cron only with a candidate source, attachment replacement.

## Open owner items

- Confirm the Smartsheet API token flagged in April 2026 (old `memory-bank/progress.md`) was rotated.
- Decide whether to run the full `/gsd-core:docs-update` generation (README update + 5 canonical docs).
- Track-or-ignore: `.agents/skills/`, `.serena/project*.yml` + `memories/`, `.planning/state.json`,
  `website/.claude/`. Delete-or-keep: `replit.md`, `Copilot-Processing.md`, `wiki.md` (stale root docs).
- Correct the WR-01 wording in `12-02-PLAN.md` line 25 through a GSD verb, or let the executor note it.
- GitHub reports 16 Dependabot alerts on `master` (11 high) — triage (`dependency-auditor`).

## Protected areas (Juan's approval required)

Smartsheet live writes · Supabase RLS / schema / migrations / RPC (owner-deployed only) · billing and
attribution formulas or outputs · `generate_weekly_pdfs.py` / `pipeline/*` behavior · GitHub Actions
workflows and schedules · env / secrets · the protected Resiliency workflow list in
`~/.claude/rules/production-guardrails.md`. Never push to `master`; never expose service-role keys;
public repo → aliases only, no PII.

## Verification commands

`pytest tests/ -v` · `python -m py_compile generate_weekly_pdfs.py` · `bash scripts/run_6_gates.sh` ·
`TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py` ·
`node ~/.claude/gsd-core/bin/gsd-tools.cjs query validate.health` · Step 0 drift check in
`.claude/skills/align-instruction-files/SKILL.md`.

## History pointer

Everything before this session: `memory-bank/living-ledger.md` (dated entries — grep, never load
whole), `docs/CHANGELOG_CONTEXT.md` (operator-facing mirror), `docs/AI_CONTEXT_RESUME.md` (snapshots),
`.planning/` (GSD phases 01–12; Phase 09 turned the 10,476-line facade into the 13-module `pipeline/`
package, PR #280).
