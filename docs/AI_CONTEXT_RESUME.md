# AI Context — Resume Where I Left Off

> **Purpose:** durable "pick up where I left off" context so Claude Code (or
> any AI assistant) can continue this project on another machine without the
> live chat history. This is a snapshot; update it before you stop working
> (see the bottom of this file and `PROJECT_HANDOFF.md`).
>
> **Authoritative project rules live in [`/CLAUDE.md`](../CLAUDE.md)** (and the
> Codex mirror [`/AGENTS.md`](../AGENTS.md)). This file is the *status / resume*
> layer, not the rulebook.

_Last updated: 2026-06-30._

> **Live status now lives in [`.claude/project-state.md`](../.claude/project-state.md)**
> (overwritten each session) and [`.planning/STATE.md`](../.planning/STATE.md). This
> file is the periodic *snapshot*; the dated history is in
> [`memory-bank/living-ledger.md`](../memory-bank/living-ledger.md).

## Project status (one paragraph)

Python billing-automation pipeline (`generate_weekly_pdfs.py`): Smartsheet →
row filtering → Work-Request grouping → Excel generation (`openpyxl`) →
attachment upload back to Smartsheet, on a GitHub Actions cron. Production is
healthy. Active work is the **"universal per-line-item claim attribution"**
effort: every Excel file is partitioned by the *frozen* foreman/helper/vac-crew
member who actually claimed each line item, sourced from the
`billing_audit.attribution_snapshot` Supabase table via the Foundation A read
layer.

## Current active work — Phase 09: engine modularization (v1.3)

Splitting the 10,476-line `generate_weekly_pdfs.py` into a `pipeline/` package,
**facade-preserved, zero behavior change**, validated by a 6-gate oracle
(`scripts/run_6_gates.sh`: AST 177-name equality · facade allowlist · pytest ·
mypy delta · py_compile · 21-key run_summary). GSD phase, 7 waves (09-00→09-06),
run **sequential / no-worktree, Opus executors, wave-by-wave** with an
independent gate run + human go between every wave.

- **Waves 0–4 ✓ COMPLETE & independently gate-verified.** W0 harness/scaffold ·
  W1 config/utils/observability · W2 pricing/change_detection · W3 discovery/fetch
  (PEP-562 live-proxy) · **W4 grouping/excel** (added `pipeline/grouping.py` +
  `pipeline/excel.py`; facade now 4745 ln; billing guards byte-for-byte).
- **⏸ Wave 5 NEXT (cleanup/upload/attribution), awaiting human go.** Then W6
  (orchestrate + facade finalize — must re-verify `_billing_audit_writer`
  injection survives the `main()`→`orchestrate.py` move).
- Live status: `.claude/project-state.md` + `.planning/STATE.md`; dated history:
  `memory-bank/living-ledger.md`.

> **Phase 08** (smartsheet-python-sdk 4.0.0 migration) is paused; SDK pinned
> `<4.0.0`. **Phase 08 must NOT run concurrently with Phase 09 — same file.**

## Frozen claim-attribution — diagnosed gaps (read-only debug 2026-06-26, NO fixes applied)

A GSD `find_root_cause_only` debug (`.planning/debug/frozen-claim-history-gap.md`)
found the frozen-attribution system does **not** preserve the previous actor's
historical file for 2 of 5 actor classes, plus a data backfill flaw. **Fixes are
parked pending approval** — Phase 09 Wave 5 relocates this code byte-for-byte, it
does NOT repair it.

- **DATA (P1):** the freeze ran as a one-shot cold-start backfill (~2026-04-24)
  that captured the *current* foreman for all historical weeks (the source
  `Foreman` is a live per-WR value, not per-week history). WR 89834661: 5 weeks of
  the prior foreman's work frozen to the current one; 52 rows frozen
  `Unknown Foreman`. Systemic: 5,183 rows / 89 of 617 WRs frozen `Unknown Foreman`.
- **CODE (P2):** primary `helper` is **uncovered** (no flag, no `resolve_claimer`;
  key + filename use the live helper); subcontractor `helper` is **half-wired**
  (frozen drives group key + Excel cell, but filename/upload-id/change-key use the
  live helper). primary / VAC / sub-primary are correctly wired.
- Fix shapes recorded in the debug file + `living-ledger.md [2026-06-26 14:30]`.

## The claim-attribution rollout (mostly shipped; see status table)

Sequencing — **A → B → C → D → E**:

| Sub-project | Scope | Status |
|---|---|---|
| **Foundation A** | Read layer + HOLD contract: `billing_audit.writer.resolve_claimer`, `ROLE_BY_VARIANT`, `record_attribution_hold`, `summarize_attribution_holds`. Dormant; zero production behavior change. | ✅ Shipped |
| **Phase 1.1** | Subcontractor helper-shadow rescue + variant partition + claim-history attribution. | ✅ Shipped |
| **Subproject B** | Subcontractor **primary** variants (`reduced_sub`/`aep_billable`) re-partitioned by frozen primary claimer → `_ReducedSub_User_<name>` / `_AEPBillable_User_<name>`. | ✅ Merged (PR #215) |
| **Helper-exclusion hotfix** | Helper-completed subcontractor rows excluded from primary files (no double-count). | ✅ Merged (PR #216) |
| **Dept-#/Job-# fix** | Sub-helper Excel files show Helper Dept #/Job # (not the primary's). | ✅ In master via the B branch |
| **Subproject C** | `vac_crew` files re-partitioned by frozen vac-crew claimer → `_VacCrew_<name>`, all sheets. | ✅ Merged (PR #219; cross-sheet unit-dedup follow-up PR #274) |
| **Subproject D** | Primary-workflow (non-subcontractor) **primary** foreman partitioning. Highest blast radius; deliberately last before E. | ✅ Shipped (PR #223; `__variant` follow-up PR #225) |
| **Subproject E** | Supabase hash-store migration + stripping `_<hash>`/`_<timestamp>` tokens from filenames (depends on Supabase being the change-detection source of truth). | ⏳ Not started |

## Recent work completed (most recent first)

- **v1.3.1 — Smartsheet API resilience & silent-failure/PII hardening** —
  new `pipeline/retry.py smartsheet_call_with_retry` (bounded transient retry
  for `ApiError` code 4000 / typed `should_retry` / rate-limit / the SDK's
  transport-drop wrappers) on the discovery + per-sheet fetch hot path; a
  dropped source sheet is now LOUD but PII-safe (`sentry_capture_sheet_drop`)
  instead of a silent `return None`. Also un-silenced the F1 `no_history`
  attribution WARNING and scrubbed row PII from Sentry across all three planes
  (event frames via `before_send`; breadcrumb `message` + `data` via
  `before_breadcrumb`). Additive/surgical — billing behavior unchanged; 6 gates
  green (G3 1149); PII scrubs dummy-transport-verified; all 8 reviewer passes
  resolved. Merged as **PR #281** → commit `8c51a3c`. Deferred to its own PR:
  retry-idempotency in `SUPABASE_HASH_STORE_AUTHORITATIVE` clean-filename mode.
- **Subproject C** (`vac_crew` claim attribution) — implemented via
  brainstorm → spec → plan → subagent-driven TDD; final comprehensive review
  = READY TO MERGE; **PR #219** opened against `master`. Suite: 809 passed.
  Spec: `docs/superpowers/specs/2026-05-21-subproject-c-vac-crew-claim-attribution-design.md`;
  plan: `docs/superpowers/plans/2026-05-21-subproject-c-vac-crew-claim-attribution.md`.
- **Dept-#/Job-# display fix** for subcontractor helper-shadow files
  (`generate_excel` variant branch missed `reduced_sub_helper`/`aep_billable_helper`).
- **PR #215 (Subproject B)** + **PR #216 (helper-exclusion hotfix)** merged.

## Current open tasks / next recommended steps

1. **Phase 09 Wave 5** (cleanup/upload/attribution) — NEXT, on human go. Same
   model: Opus executor, sequential / no-worktree, independent `run_6_gates.sh` +
   stop. Then Wave 6 (orchestrate + facade finalize).
2. **Frozen-attribution fix (parked, awaiting approval)** — wire primary-`helper`
   attribution; fix the sub-helper filename/upload/change-key asymmetry; add a
   blank-foreman guard at freeze; one-time controlled re-attribution of the 5,183
   `Unknown Foreman` rows + the WR 89834661 weeks (manual Supabase + re-freeze
   runbook). Full diagnosis: `.planning/debug/frozen-claim-history-gap.md`.
3. **Subproject E** (last claim-attribution rollout item, not started) — Supabase
   change-detection cutover + filename `_<hash>`/`_<timestamp>` strip. Lands
   cleaner *after* Phase 09 modularizes the upload/change-detection code.

## Known blockers / risks

- **Subproject B UAT Tests 2–4** are not yet validated against a live run
  (they need the per-claimer `_User_` files generated by the cron).
- **Subproject D is the highest-risk** change (touches the core primary
  grouping + the biggest attachment-rename migration). Do it carefully, last.
- **`generate_weekly_pdfs.py` is production-critical** (cron every 2h on
  weekdays, real billing data). Additive, surgical changes only.

## Important decisions already made

- **Frozen first-write-wins attribution** per row; a mid-week foreman switch
  produces a *second* file (the prior claimer's file is never cross-deleted).
- **CR-01 four-site lockstep**: a variant's claimer identifier must be byte-
  identical at (1) main-loop `identifier`/`history_key`, (2) `valid_wr_weeks`,
  (3) `current_keys`, (4) `build_group_identity` parser — and every site gated
  on the variant's kill switch so OFF reproduces exact legacy behavior. (The
  main-loop `history_key` site is distinct from the `group_source_rows`
  emission group-key and is **easy to miss** — Subproject C's review caught
  exactly that.)
- **Correctness over availability:** on a Supabase `fetch_failure`, HOLD the
  affected rows (don't emit a possibly mis-attributed file) rather than guess.
- **Hash-in-filename is retained until Subproject E.** Do not strip it earlier.
- **`billing_audit/` is not modified by B/C/D** — Foundation A already provides
  the read layer.

## Verify the project (commands)

```bash
pip install -r requirements.txt
pytest tests/ -v                 # full suite — must pass before push
python -m py_compile generate_weekly_pdfs.py
TEST_MODE=true python generate_weekly_pdfs.py   # synthetic, no API token
```

`.github/hooks/pre-push-tests.json` is a **Claude Code hook** (not a git
hook): it blocks the `git push` *tool* when `pytest tests/` fails. From a plain
shell, run `pytest tests/` manually before pushing.

## How another computer continues this work

1. Clone/pull the repo and the relevant branch (see `PROJECT_HANDOFF.md`).
2. Install the same Claude Code plugins (the workflow depends on them — list in
   `PROJECT_HANDOFF.md`).
3. Open Claude Code from the repo root so it auto-loads `CLAUDE.md`.
4. Read this file + `CLAUDE.md` "Living Ledger" for the latest decisions.
5. Continue from "Current open tasks" above.

## Before you stop working (update ritual)

- Bump _Last updated_ and the status table here.
- Append any new architectural decision to the **Living Ledger** in `CLAUDE.md`
  (and `AGENTS.md` if you keep the Codex mirror in sync), with a
  `[YYYY-MM-DD HH:MM]` timestamp.
- Commit + push so the other machine can pull the latest context.
