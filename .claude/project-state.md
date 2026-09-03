# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-09-02 22:05 CDT (2026-09-03 03:05Z) · **overwrite-in-place each session** — this is
the canonical "where the project stands" landing spot for the global Stop write-back reminder. Cap ≤ 120
lines (`align-instruction-files` skill); history goes to `memory-bank/living-ledger.md`, never here._

_Latest ledger entries: `[2026-09-02 22:05]` (instruction-file alignment run 1 — what moved where),
`[2026-09-02 21:20]` (memory-bank pages retired; pre-ledger April-2026 history imported),
`[2026-09-02 20:45]` (align skill), `[2026-09-02 20:20]` (bootstrap audit), `[2026-09-02 18:15]`
(Phase 12 plan-phase, D-12-A / D-12-B)._

## Where the project stands

- **Milestone v1.4 "Supabase Run Memory":** Phase 10 closed 2026-08-25 (6/6), Phase 11 closed
  2026-08-31 (8/8, INC-05 retirement shipped), Phase 11.1 closed 2026-09-02 (4/4; PR #384 `13e8e76`;
  canary run 33683979474 met SC-1 — `⚡ Phase 1 complete` 37.7 s, was 3,214 s). **Phase 12 (Ownership —
  last known foreman as of the week) is PLANNED:** 6 plans / 4 waves, checker 0 blockers,
  `.planning/STATE.md` "Ready to execute". Phase 13 = the deferred `wr_week_ownership` table (D-12-A).
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

## Latest work (2026-09-02 evening) — instruction-file alignment, run 1 (branch `docs/align-instruction-files`)

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
  `docs/CHANGELOG_CONTEXT.md`, vault project page + `wiki/log.md` updated; docs-only PR opened
  (nothing pushed to `master`).

## Next

1. Owner: review/merge the docs PR; paste the `FROZEN MIRROR` header into `AGENTS.md` by hand.
2. `/clear` → `/gsd-execute-phase 12` — wave 1 = 12-01 tracer
   (`scripts/backfill_claim_time_attribution.py`, dry-run WR 19073866 → `_User_Avery_Example` via
   source 4) on a branch → PR.
3. Owner-owned Phase 12 steps stay blocking checkpoints: confirm live `attribution_snapshot` column
   names, apply `billing_audit/own03_backfill_attribution.sql`, approve the dry-run report, run
   `--apply`, enable the source-5 cell-history cron, attachment replacement.

## Open owner items

- Confirm the Smartsheet API token flagged in April 2026 (old `memory-bank/progress.md`) was rotated.
- Decide whether to run the full `/gsd-core:docs-update` generation (README update + 5 canonical docs).
- Track-or-ignore: `.agents/skills/`, `.serena/project*.yml` + `memories/`, `.planning/state.json`,
  `website/.claude/`. Delete-or-keep: `replit.md`, `Copilot-Processing.md`, `wiki.md` (stale root docs).
- Correct the WR-01 wording in `12-02-PLAN.md` line 25 through a GSD verb, or let the executor note it.

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
