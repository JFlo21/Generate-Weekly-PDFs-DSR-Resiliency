---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 06
subsystem: billing-attribution
tags: [supabase, backfill, ownership, attribution, sentinel-cleanup, own-03]

requires:
  - phase: 12-01
    provides: scripts/backfill_claim_time_attribution.py (dry-run/apply CLI, source 1-4 resolution)
  - phase: 12-02
    provides: CR-01 sentinel-identifier fix in pipeline/cleanup.py (hard dependency for any future --apply)
  - phase: 12-03
    provides: billing_audit.backfill_attribution RPC, provenance columns, dated backup table
  - phase: 12-05
    provides: website/docs/runbook/ownership-attribution.md operator procedure
provides:
  - A recorded, REJECTED Task 1 dry-run review with live counts and a named script defect blocking any --apply
affects: [12-gap-closure, own-03-remediation]

actuals:
  tokens: 3600
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified: []

key-decisions:
  - "Juan REJECTED the OWN-03 dry-run report (reason: source-3 filename parser defect) — no --apply authorized"

patterns-established: []

requirements-completed: []

coverage:
  - id: D1
    description: "Dry-run of scripts/backfill_claim_time_attribution.py against live Supabase data (207 WRs x 54 weeks, scoped full set), reviewed by Juan against the plan's 7-step verification checklist"
    requirement: OWN-03
    verification: []
    human_judgment: true
    rationale: "Requires human review of proposed claimer names, live production counts, and operator domain knowledge against the dry-run report; Juan's verdict was REJECT — no automated check can approve a production billing-attribution write."

duration: ~15min (documentation/transcription only — no code executed, no live credentials used)
completed: 2026-09-03
status: halted
---

# Phase 12 Plan 06: Ownership Attribution Live Remediation (OWN-03) — HALTED at Task 1

**Juan reviewed the OWN-03 live dry-run and REJECTED it: source 3's filename parser proposed the literal string "Unknown Foreman.xlsx" as a real claimer name for 4,070 rows because production filenames carry no hash suffix — Tasks 2-4 (the live `--apply` and post-run verification) did not run.**

## Performance

- **Duration:** ~15 min (recording Juan's review outcome and writing this summary; no code, no live Supabase/Smartsheet calls)
- **Completed:** 2026-09-03T22:46:12Z
- **Tasks:** 1 of 4 (plan halted at its designed stop; Tasks 2-4 not executed)
- **Files modified:** 0 (Task 1 is read-only by design — "the executor runs nothing against live credentials")

## Accomplishments

- Ran the full-scope dry-run (`python scripts/backfill_claim_time_attribution.py`, default `--dry-run`) scoped to all 207 WRs carrying a named sentinel across 54 weeks; exit code 0, no warnings, no errors.
- Captured the live-authoritative affected-row/WR/pair totals, superseding the two stale ledger snapshots referenced in the plan.
- Identified and recorded a script defect in source 3's filename-derived claimer parsing that would have frozen a placeholder string as a real name across 4,070 rows had `--apply` run.
- Recorded Juan's explicit REJECT verdict, halting the plan before Task 2's authorization gate — no write to `billing_audit.attribution_snapshot` occurred.

## Task Records

### Task 1: Dry-run against live data and owner review of the proposals — REJECTED

**Dry-run invocation.** The plan's "full-scope, no arguments" mode does not exist in the shipped script — it exits 8 unless both `--wr` and `--weeks` are supplied. Juan ran the scoped full set instead: 207 WRs × 54 weeks, covering every (WR, week) holding a named sentinel in `billing_audit.attribution_snapshot`, enumerated read-only via SQL. Exit code 0, no warnings, no errors.

**Live affected totals (authoritative — supersedes the 5,824-rows/93-WRs figure in this plan's objective, ROADMAP.md and REQUIREMENTS.md, and the 5,829-rows/94-WRs figure in `12-RESEARCH.md` § Runtime State Inventory; neither historical figure is a measurement, both are point-in-time ledger snapshots):**
- Named-sentinel rows: 6,764 across 207 WRs and 391 (WR, week) pairs
- Primary sentinel strings: `Unknown Foreman` 5,829; `#NO MATCH` 935
- Helper `#NO MATCH`: 10; `vac_crew`: 0
- Sentinel weeks: 2025-06-29 through 2026-08-30
- Rows already backfilled: 0
- WR keys that are not 8-digit numbers (typos / DCP keys): 52 of 207

**Script scope actually considered:** 5,829 sentinel rows, 94 WRs, 256 (WR, week) pairs. The 945 `#NO MATCH` rows (935 primary + 10 helper) are invisible to the script because `billing_audit.lookup_attribution_bulk` returns NULL for values starting with `#`. This is a scope gap that needs its own decision before a future dry-run.

**Report summary** (`generated_docs/own03_backfill_report.json`, git-ignored):
- total_rows: 5,829
- rows_by_status: proposed 4,762 / conflict 1,066 / unresolved 1
- rows_by_source: backfill_artifacts 5,136 / live 692
- source_1_out_of_week_rows: 0
- roles: primary only
- name_fidelity: desanitized 4,070 / exact 692 / blank 1,067

**DEFECT — the reason for the reject.** All 4,070 `backfill_artifacts` proposals are the literal string `Unknown Foreman.xlsx` (69 WRs, 20 weeks), and all 1,066 conflicts (65 pairs, 24 WRs) are between `.xlsx`-suffixed names. Root cause: `public.artifacts.filename` is the stable, hash-less attachment name (`WR_<wr>_WeekEnding_<mmddyy>_User_<name>.xlsx`); `scripts/backfill_claim_time_attribution.py::_extract_claimer_from_filename` only strips a `_<6hex>.xlsx` tail, so the whole remainder survives and `Unknown_Foreman.xlsx` passes `is_sentinel_claimer`. The 12-01 fixtures all used hash-suffixed names, so this shape was never exercised in test. The RPC guard `is_sentinel_value(s.frozen_<role>)` checks only the CURRENT value, never the proposed value — an `--apply` run would have frozen `Unknown Foreman.xlsx` as a real name in 4,070 rows.

**Sound subset:** 692 `live` (source 1, `row_event`) proposals across 7 WRs and 7 distinct names, fidelity exact. (No names recorded, per the no-real-names rule.)

**Step 3 — known-good sample (ROADMAP success criterion 3):** WR 19073866 has zero rows in every Supabase store (snapshot, backup, group_state, row_state, row_event, group_content_hash, artifacts) — the snapshot was never rebuilt (`frozen_at` from 2026-04-24); the docs carry a placeholder WR number as they carry the placeholder name `Avery Example`. Only WR 89829163 has sentinel primary rows on exactly 082425/083125/091425/092125, but its `group_content_hash` identifiers are sentinel-only, so ROADMAP SC3 "via backfill_hash_history" is not satisfiable from Supabase as currently populated; the retired `hash_history.json` is not on disk. Not confirmed by Juan as a replacement sample yet.

**Step 5 — artifacts cross-check:** 4,070 of 4,070 primary artifact-sourced proposals disagree with a real-name filename (they ARE the sentinel filename itself); the 692 live proposals were not cross-checked, pending the fix. WRs excluded from any apply scope: all (apply rejected in full).

**Step 6 — conflict sanity:** 0 (WR, week, role) groups carry more than one distinct proposed name among `proposed` rows; the 1,066 two-name cases are correctly classified `conflict`.

**Step 7 — Opus MEDIUM carry-over check:** among target `row_id`s, `row_state` matched 6,755 rows and `row_event` matched 6,770 rows, with 0 NULL-week and 0 stale-week entries; 9 target rows have no memory entry.

**Owner reminder carried forward:** the `--apply` backup precondition probe looks for `attribution_snapshot_backup_<today UTC>`; the 2026-09-03 backup is already 226 rows stale (per Living Ledger `[2026-09-03 15:55]`) and must be re-created on the day `--apply` actually runs.

**Juan's verbatim verdict:** `reject: source-3 filename parser defect`

**Cross-reference:** Living Ledger entry `[2026-09-03 17:30]`; `.claude/project-state.md` § "Where the project stands" (latest-ledger-entries bullet); ledger commits `5b38cf6`, `5e1b68c`.

### Tasks 2-4 — NOT EXECUTED

Task 2's `<precondition>` ("Task 1 recorded `approve` or `approve-with-scope`") is unmet by design — Task 1 recorded `reject`. Per the plan and the executor's precondition-gate protocol, Task 2 (DECISION — authorize the one-way live backfill write), Task 3 (execute the live apply), and Task 4 (verify the post-apply scheduled run) were not presented, not auto-selected, and not executed. No production write occurred. No `--apply` was run.

## Files Created/Modified

None. Task 1 is a read-only dry-run; the only artifact it produces (`generated_docs/own03_backfill_report.json`/`.csv`) is git-ignored and was not committed.

## Decisions Made

- Juan REJECTED the OWN-03 dry-run report with reason "source-3 filename parser defect" — no live write authorized. This is the plan's designed stop, not a deviation: the checkpoint's resume-signal explicitly allows `approve`, `approve-with-scope`, or `reject` with reason, and REJECT is the outcome Task 1's own acceptance criteria anticipate.

## Deviations from Plan

None - plan executed exactly as written. Task 1's checkpoint reached its designed REJECT outcome; per Task 2's unmet precondition, execution correctly halts there rather than proceeding to the authorization, apply, or post-run verification tasks.

## Issues Encountered

The dry-run surfaced a defect in `scripts/backfill_claim_time_attribution.py` (shipped in plan 12-01): source 3's filename-derived claimer extraction does not account for the hash-less filename shape production actually stores in `public.artifacts.filename`, causing it to propose a sentinel string as a real name. This is a code defect in an already-shipped plan, not something this plan's checkpoint tasks are scoped to fix (Task 1 is read-only by design). Routed to `/gsd:plan-phase 12 --gaps` rather than fixed inline, per the plan's own "record it as a phase gap" instruction pattern and the Living Ledger's recorded route.

## Halted at Designed Stop

**Gap:** `scripts/backfill_claim_time_attribution.py`'s source-3 (`backfill_artifacts`) filename parser strips only a `_<6hex>.xlsx` hash suffix, but `public.artifacts.filename` (the live, stable attachment name written by `scripts/publish_artifacts_to_supabase.py::_parse_stable`) never carries one. Left unstripped, the whole `_User_<name>.xlsx` remainder — including a sentinel name like `Unknown Foreman.xlsx` — survives as the "extracted" claimer and passes `is_sentinel_claimer`, because the RPC's server-side guard (`is_sentinel_value(s.frozen_<role>)`) only re-checks the CURRENT frozen value, never the newly PROPOSED one. An `--apply` run today would silently freeze the placeholder string as a permanent "real" name across 4,070 rows (69 WRs). A related, smaller scope gap: `lookup_attribution_bulk` returns NULL for values starting with `#`, so the 945 `#NO MATCH` rows are invisible to the script's targeting and need a separate scope decision. The known-good sample (WR 19073866) also has no data in Supabase to prove ROADMAP SC3 via `backfill_hash_history`; WR 89829163 is a partial substitute pending Juan's confirmation.

**Route:** `/gsd:plan-phase 12 --gaps`, to:
1. Fix 12-01 source 3: strip the file extension from any filename-derived candidate BEFORE the sentinel check, and reject any candidate that still carries an extension.
2. Add a proposed-value guard in the script's payload builder and/or the `billing_audit.backfill_attribution` RPC so a value `is_sentinel_value` would reject can never be written — closing the gap the current-value-only guard leaves open.
3. Rebuild the 12-01 test fixtures from the real, hash-less filename shape (`WR_<wr>_WeekEnding_<mmddyy>_User_<name>.xlsx`) instead of the hash-suffixed shape the fixtures previously assumed.
4. Decide the `#NO MATCH` scope gap (whether to extend `lookup_attribution_bulk` or add a client-side path for `#`-prefixed values).
5. Re-decide ROADMAP success criterion 3's known-good sample given WR 19073866 has no Supabase data.

After the gap-closure plan(s) land, 12-06 is re-run from Task 1 and re-summarized as `status: complete`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 12 (Ownership — last known foreman as of the week) is NOT complete. OWN-02 and OWN-03 remain outstanding pending the gap-closure route above and a subsequent clean 12-06 re-run (dry-run review, live apply, post-run verification). No production data was altered by this plan; the dated backup table and the RPC's server-side sentinel-only guard were never exercised because no `--apply` ran.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-03*
*Status: HALTED (designed stop — Task 1 REJECT; Tasks 2-4 not executed)*
