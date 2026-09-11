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
  - OWN-03 live remediation landed (1,758 rows updated 2026-09-05, read-back clean); Task 4 post-apply
    observation transcribed and APPROVED by Juan 2026-09-10; ROADMAP success criterion 3 sample WR 89746993
    recorded (D-12-E); the three attribution_snapshot backups dropped
affects: [12-gap-closure, own-03-remediation]

actuals:
  tokens: 3600
  tasks: 4
  commits: 1

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified: []

key-decisions:
  - "Juan REJECTED the OWN-03 dry-run report (reason: source-3 filename parser defect) — no --apply authorized"
  - "Re-run 2026-09-05: Juan APPROVED the full-scope dry-run report as-is (verbatim: `I approve`) — 1,758 proposed rows / 30 WRs / 76 pairs, 0 conflicts, all G-12-3 and CR-01 guards 0; Task 2 decision pending"
  - "D-12-D sample WR 89829163 is unresolvable (placeholder-only artifacts and hash identifiers) — ROADMAP SC3 needs a new sample; routed to the verify-work pass, not fixed inside 12-06"
  - "Task 2 (2026-09-05): Juan chose `apply-full` (verbatim) — apply the whole approved report (same --wr/--weeks scope as the dry-run, no --include-blank-roles); Task 3 requires a fresh same-UTC-day STEP 1 backup first"
  - "Whole-project read-only inventory: no Supabase store holds in-week Jul–Nov 2025 foreman evidence for the 4,071 unresolved rows; they route to source 5 (Smartsheet cell history) after the apply"
  - "Task 3 (2026-09-05 03:43 UTC): live apply executed by the orchestrator at Juan's `Run it` after a fresh same-UTC-day STEP 1 backup (`attribution_snapshot_backup_20260905`, 221,276 rows): updated 1,758 / skipped_real_name 0 / skipped_no_row 0 / errors 0; 219,518 untouched rows show 0 differences vs the backup; provenance total 1,758 = updated; backfill_run_id is '' on local runs (note for verify-work)"
  - "Task 4 (2026-09-10): seven post-apply observations transcribed read-only from run 33974128574 (first scheduled run after the apply), Smartsheet target-sheet inventory and Supabase — all pass; substitute SC3 sample WR 89746993 proposed"
  - "Task 4 (2026-09-10 ~23:45Z): Juan replied `Approved`, `Adopt 89746993` (D-12-E) and `Yes drop them using our supabase connector` — backups dropped, plan complete"

patterns-established: []

requirements-completed: []

coverage:
  - id: D1
    description: "Dry-run of scripts/backfill_claim_time_attribution.py against live Supabase data (207 WRs x 54 weeks, scoped full set), reviewed by Juan against the plan's 7-step verification checklist"
    requirement: OWN-03
    verification: []
    human_judgment: true
    rationale: "Requires human review of proposed claimer names, live production counts, and operator domain knowledge against the dry-run report; Juan's first verdict (2026-09-03) was REJECT and the 2026-09-05 re-run was APPROVED — no automated check can approve a production billing-attribution write."

duration: ~15min per checkpoint session (documentation/transcription only — no code executed by the executor; the 2026-09-05 apply and 2026-09-10 observations were orchestrator-run at Juan's instruction)
completed: 2026-09-10
# History: re-entered 2026-09-04 after G-12-3 closed (12-07..12-10, Juan: `re-enter-12-06`) via the
# `blocked` re-entrant state (#3345); Tasks 1-3 landed 2026-09-05 and Task 4 was observed 2026-09-10,
# then APPROVED 2026-09-10 ~23:45Z (Juan: `Approved`, `Adopt 89746993`, `Yes drop them using our
# supabase connector`) — this file was rewritten into a completion record at that point.
status: complete
---

# Phase 12 Plan 06: Ownership Attribution Live Remediation (OWN-03) — COMPLETE (Tasks 1–4; Task 4 approved 2026-09-10)

**Re-run 2026-09-05 (after the G-12-3 gap closure 12-07..12-10): the full-scope read-only dry-run was clean — 1,758 proposed rows over 30 WRs / 76 pairs from 24 real names, 0 conflicts, 4,071 rows genuinely evidence-less, every G-12-3 / CR-01 guard at 0, every proposal matching its `public.artifacts` filename — Juan APPROVED it (`I approve`), chose `apply-full`, and said `Run it`. The orchestrator created the same-UTC-day backup `attribution_snapshot_backup_20260905` and ran the apply: 1,758 rows updated, 0 skipped, 0 errors, 0 differences on the 219,518 untouched rows, provenance total = updated. Task 4 (observe the first post-apply scheduled run) was performed read-only on 2026-09-10 — see Task 4 below — and Juan then replied `Approved` (with `Adopt 89746993` for D-12-E and `Yes drop them using our supabase connector` for the backups) at ~23:45Z, closing the plan. The 2026-09-03 first attempt below was REJECTED because source 3's filename parser proposed "Unknown Foreman.xlsx" as a real name for 4,070 rows; that record is preserved unchanged as history.**

## Performance

- **Duration:** ~15 min (recording Juan's review outcome and writing this summary; no code, no live Supabase/Smartsheet calls)
- **Completed:** 2026-09-10 ~23:45Z (Task 4 approved); Task 1 first attempt 2026-09-03T22:46:12Z (REJECT), Tasks 1–3 re-run 2026-09-05, Task 4 observed 2026-09-10
- **Tasks:** 4 of 4 (Task 1 halted at its designed stop on 2026-09-03; re-entered after 12-07..12-10 and completed)
- **Files modified:** 0 repo files by the plan itself (Task 1 is read-only by design); one production write — the Task 3 live apply (1,758 rows, 2026-09-05) — plus the three backups dropped after Task 4

## Accomplishments

- Ran the full-scope dry-run (`python scripts/backfill_claim_time_attribution.py`, default `--dry-run`) scoped to all 207 WRs carrying a named sentinel across 54 weeks; exit code 0, no warnings, no errors.
- Captured the live-authoritative affected-row/WR/pair totals, superseding the two stale ledger snapshots referenced in the plan.
- Identified and recorded a script defect in source 3's filename-derived claimer parsing that would have frozen a placeholder string as a real name across 4,070 rows had `--apply` run.
- Recorded Juan's explicit REJECT verdict, halting the plan before Task 2's authorization gate — no write to `billing_audit.attribution_snapshot` occurred.

## Task Records

### Task 1 (re-run 2026-09-05): Dry-run against live data and owner review of the proposals — APPROVED

**Invocation (read-only, run by the execute-phase orchestrator, not an executor; 2026-09-05 00:24:09Z → 00:25:44Z, 95 s, exit 0).** `python scripts/backfill_claim_time_attribution.py --wr <207 WRs> --weeks <54 weeks> --report-dir <session scratchpad>/own03_dryrun` — no `--include-blank-roles` (D-12-C), no `--apply`. The report was written outside the repository and never committed; 652 Supabase reads, all HTTP 200; one expected WARNING (report dir outside `generated_docs`). Scope enumerated read-only via SQL over `billing_audit.attribution_snapshot` and identical to the 2026-09-03 run: 207 WRs × 54 weeks (062925..083026), 391 (WR, week) pairs, 6,764 named-sentinel rows = 5,829 primary `Unknown Foreman` + 935 primary `#NO MATCH` + 10 helper `#NO MATCH` (the 945 `#`-prefixed rows stay out per D-12-C). Snapshot 221,276 rows (655 above `attribution_snapshot_backup_20260904`); 0 rows carry `backfill_run_id`.

**Step 2 — report summary block (live, authoritative):**
- total_rows: 5,829 (primary role only; every `current_value` is `Unknown Foreman`)
- rows_by_status: proposed 1,758 / conflict 0 / unresolved 4,071
- rows_by_source: backfill_artifacts 1,066 / live 692 / backfill_hash_history 0
- name_fidelity: exact 692 / desanitized 1,066 / blank 4,071
- source_1_out_of_week_rows: 0
- Proposed scope: 30 WRs, 76 (WR, week) pairs, 24 distinct names (19 via artifacts, 7 via live)
- Unresolved: 70 WRs, 180 pairs, all "no source 1-4 produced a candidate" — the 4,070 formerly-placeholder rows plus the first run's 1 unresolved; source 4 resolved none of them
- Delta vs the first run: the 1,066 former conflicts (placeholder-vs-real filename pairs) each now propose their single real name; the 4,070 placeholder proposals became unresolved

**G-12-3 / CR-01 guards over the 1,758 proposed values (computed in-sandbox, counts only):** extension-bearing 0 · hash-tailed (`_[0-9a-fA-F]{6,16}$`) 0 · any 16-hex run 0 · sentinel-classified (`is_sentinel_claimer`) 0 · leading punctuation 0 · blank 0.

**Step 3 — known-good sample (ROADMAP SC3 as amended by D-12-D, WR 89829163 WE 082425/083125/091425/092125):** all four weeks UNRESOLVED (49 report rows on this WR). Read-only SQL: snapshot rows 13/19/7/10, all sentinel; `public.artifacts` 9/8/8/8 per week, ALL placeholder-named (0 real names); `billing_audit.group_content_hash` 1 identifier per week, sentinel-only; no `pipeline_memory.group_state` rows. The 2026-09-03 run "resolved" this WR only through the parser defect, so SC3 as written is not satisfiable by any source. This is a sample-selection issue, not a script or source-precedence defect — the `STOP` clause in the plan's step 3 (different source / different name) does not apply. Retired sample WR 19073866: 0 rows (unchanged). Replacement candidates (one name across ≥4 weeks): WR 89746993 (114 rows, 4 weeks, artifacts), 89841789 (92, 4, artifacts), 89848991 (91, 4, artifacts), 90851321 (540, 6, live). Routed to the verify-work pass as a ROADMAP amendment.

**Step 4 — extended sample:** left to Juan's billing-side knowledge over the report CSV (outside the repo); suggested WRs 90851321, 89746993, 91366851. No names recorded here.

**Step 5 — artifacts cross-check (spec §6):** 1,758 of 1,758 primary proposals agree with the `public.artifacts` filename for their WR and week (artifacts-sourced 1,066 agree, live-sourced 692 agree); 0 disagreements; 0 proposed pairs without an artifact. WRs excluded from the apply scope as a result: none. Independent SQL over the whole population: 256 sentinel-primary pairs → 76 pairs (30 WRs) hold a real-name `_User_` artifact = exactly the proposed pairs; 179 hold only placeholder-named or tokenless artifacts and 1 holds none = the 180 unresolved pairs (19,773 artifacts total: 19,063 placeholder-named, 684 real-name, 26 without a `_User_` token).

**Step 6 — conflict sanity:** 0 (WR, week, role) groups carry more than one distinct proposed name; 0 rows classified `conflict`.

**Step 7 — Juan's verbatim verdict (2026-09-04 evening CDT, after the orchestrator's recommendation to approve):** `I approve` → **APPROVE (as-is, full report).**

**Backup note carried to Task 3:** the UTC date rolled to 2026-09-05 during this session, so `attribution_snapshot_backup_20260904` no longer satisfies the same-UTC-day `--apply` probe (exit 3). A fresh STEP 1 backup for the apply day is required before `--apply`; `_20260903` and `_20260904` must not be dropped or overwritten.

### Task 1 (first attempt 2026-09-03): Dry-run against live data and owner review of the proposals — REJECTED

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

### Task 2 (2026-09-05): DECISION — authorize the one-way live backfill write — `apply-full`

**Option id:** `apply-full` · **Juan's verbatim response (2026-09-04 evening CDT / 2026-09-05 UTC):** `apply-full`

**Context put in front of Juan before the answer:** the Task 1 counts above (1,758 proposed rows / 30 WRs / 76 pairs, 0 conflicts, all guards 0, 1,758/1,758 artifact agreement); the orchestrator's recommendation `apply-full`; a read-only probe, at Juan's request, of `public.smartsheet_unified_history` and then of every other table in the Supabase project as a possible source for the 4,071 unresolved rows — conclusion: no Supabase store holds in-week evidence for those rows (the unified history holds only post-remap "last known" names, ≥30 days after the week, two candidates on 22 of 42 WRs), so they route to source 5 (Smartsheet cell history) after this apply and do not change the apply scope. Evidence: session scratchpad `own03_dryrun/evidence_unified_history_probe.md`.

**Exact scope to apply (identical to the approved dry-run):** `--wr` = the 207 named-sentinel WRs and `--weeks` = the 54 `week_ending_fmt` tokens enumerated read-only from `billing_audit.attribution_snapshot` (lists preserved in the session scratchpad `own03_dryrun/scope_wrs.csv` / `scope_weeks.csv`); `--roles` default (all three; only `primary` targets exist); `--sources` default 1,2,3,4; **no** `--include-blank-roles` (D-12-C); plus `--apply --i-approved-this --report-dir <outside the repo>`. The script re-resolves on apply, so the live tallies may differ from 1,758 by whatever `pipeline_memory` observed between the dry-run and the apply; Task 3 records the actual `updated` count.

**Precondition carried into Task 3:** the run's UTC date must have a same-day backup. UTC rolled to 2026-09-05 before this decision, so `attribution_snapshot_backup_20260904` no longer satisfies the probe (exit 3); STEP 1 must create `attribution_snapshot_backup_20260905` (CREATE TABLE IF NOT EXISTS … AS SELECT + GRANT SELECT TO service_role) on the apply day, before 2026-09-06 00:00 UTC, or a later day's equivalent. Existing backups `_20260903` and `_20260904` are not to be dropped.

### Task 3 (2026-09-05 03:40–04:15 UTC): Execute the live apply and verify no real name was touched — DONE

**Who ran it:** the execute-phase orchestrator (main session), at Juan's explicit written instruction `Run it` (2026-09-04 ~22:40 CDT), after Task 2's `apply-full`. No executor touched live credentials.

**STEP 1 backup (same UTC day, 03:40 UTC):** `CREATE TABLE IF NOT EXISTS billing_audit.attribution_snapshot_backup_20260905 AS SELECT * FROM billing_audit.attribution_snapshot;` + `GRANT SELECT … TO service_role;` via the Supabase MCP. VERIFY: `attribution_snapshot_backup_20260905` = 221,276 rows = live 221,276; `has_table_privilege('service_role', …, 'SELECT')` = true; `_20260904` (220,621) and `_20260903` (220,010) intact; 0 live rows carried `backfill_run_id` before the apply.

**Apply invocation (03:43:29Z → 03:45:06Z, 97 s, exit 0):** `python scripts/backfill_claim_time_attribution.py --apply --i-approved-this --wr <207 WRs> --weeks <54 weeks> --report-dir <session scratchpad>/own03_apply` — the exact Task 1/Task 2 scope, no `--include-blank-roles`. 657 Supabase reads (all HTTP 200), 4 `rpc/backfill_attribution` calls, 0 local RPC-call failures, one expected report-dir WARNING. The apply re-resolved 5,829 sentinel rows to the same 1,758 proposed / 4,071 unresolved as the dry-run.

**Step 2 — apply tallies (from the rewritten report summary):**
- `updated` **1,758** · `skipped_real_name` **0** · `skipped_no_row` **0** · `skipped_client_side_real_name` **0** · `error` 0
- updated by source: `backfill_artifacts` 1,066 / `live` 692 · role: primary only · 30 WRs · 76 (WR, week) pairs · 24 distinct names
- updated-value guards: extension-bearing 0 · hash-tailed 0

**Step 3 — no real name overwritten (read-only SQL at 04:15 UTC, live vs `attribution_snapshot_backup_20260905`):** rows with `backfill_run_id IS NULL` = 219,518; differences on `frozen_primary` **0**, `frozen_helper` **0**, `frozen_vac_crew` **0**; rows missing in backup 0; backup rows missing in live 0; live and backup both 221,276 rows. For the 1,758 touched rows: every backup value was a sentinel (1,758/1,758), every live value is now non-sentinel (0 still sentinel), `frozen_helper` / `frozen_vac_crew` unchanged on all 1,758, no extension or hash tail in any written name.

**Step 4 — provenance landed:** `backfill_source` breakdown `{live: 692, backfill_artifacts: 1,066}` = **1,758 = the `updated` tally**; every value in the five-member vocabulary; `backfill_provenance` carries a `primary` entry whose `source` matches `backfill_source` on 1,758/1,758. **Observation:** `backfill_run_id` is the empty string `''` on all 1,758 rows (not NULL — the RPC's `IS NOT NULL` identity still holds) because `_compute_run_id()` returns `''` when `GITHUB_RUN_ID` is absent, i.e. for a local operator run. Rows remain identifiable by `backfill_run_id IS NOT NULL` and by `backfill_provenance`, but the run id carries no value; route to `/gsd-verify-work 12` as a low-severity provenance note (a local-run identifier such as a UTC timestamp would close it), not a blocker.

**Step 5 — backup retained:** `attribution_snapshot_backup_20260905` not dropped (nor `_20260903` / `_20260904`); keep until Task 4 verifies the post-apply scheduled run.

**Remaining sentinel population after the apply:** `Unknown Foreman` primary 4,071 (the evidence-less set → source 5), `#NO MATCH` primary 935 + helper 10 (deferred, D-12-C).

Counts, WR numbers and source labels only — no claimer name recorded, per the plan's prohibition. Evidence: session scratchpad `own03_apply/` (report, run log, `analyze_apply.py`, `evidence_12-06_task3.md`).

### Task 4 (observed and APPROVED 2026-09-10): verify the next scheduled run regenerates under real names and cleans up

**Lead.** The apply landed Friday 2026-09-04 22:45 CDT (2026-09-05 03:45Z); the first scheduled run after it was **33974128574** (`weekly_maintenance` trigger, head `3fa4527`, 2026-09-05 15:13:18Z → 16:02:29Z, `success`, Python step 47:51, well under the 165-min budget) — the natural target for this task's seven observations. Juan's earlier `Verified` at ~05:40Z predated any such run and was not accepted; this pass performed the seven observations read-only on 2026-09-10 ~23:15Z against that run plus a live Smartsheet target-sheet inventory and Supabase reads (full evidence: session scratchpad `task4-evidence.md`). Conclusion: all seven observations pass (one production metric gap and one hygiene note recorded below, neither a blocker). **Juan replied `Approved` 2026-09-10 ~23:45Z** (plus `Adopt 89746993` for the D-12-E sample and `Yes drop them using our supabase connector` for the backups) — the plan's resume-signal is satisfied and this frontmatter is now a completion record.

1. **`sentinel_claimers_ignored`** — not emitted by production (0 occurrences across all three inspected runs; no `run_summary.json` artifact, only `artifact_manifest.json`). Proxy evidence instead: run 33974128574 generated 74 files / uploaded 74, `🔄 Sentinel-superseded attachment detected` 63 times, `🗑️ Removed off-contract variant` 64 times (all 64 `_User_Unknown_Foreman`, all on `TARGET_SHEET_ID` 5723337641643908). Live today: 152 `_User_Unknown_Foreman` attachments remain on the target sheet, 0 on any of the 76 backfilled (WR, week) pairs; 13 sit on backfilled WRs at non-backfilled weeks, all `backfilled = 0` / `frozen_primary = 'Unknown Foreman'` (expected — the 4,071 evidence-less rows routed to source 5, not a gap). **Verdict: pass for the backfilled scope; gap for verify-work** — no `sentinel_claimers_ignored` counter exists in production output.
2. **Sample WR / attachment swap** — ROADMAP SC3's WR 19073866 has 0 rows in every Supabase store; D-12-D's substitute 89829163 has placeholder-only artifacts. Substitute sample **WR 89746993** (4 weeks, 114 backfilled rows; the resolved person is not recorded here — T-12-28): `WR_89746993_WeekEnding_{082425,083125,090725,091425}_User_<real resolved name>.xlsx` all present on the target sheet today (created 2026-09-05, `last_generated_run` 33974128574.1); the prior `..._090725_User_Unknown_Foreman.xlsx` was detected superseded and removed within the same run (15:58:58Z → 15:58:59Z). **Verdict: pass.** ROADMAP SC3 sample re-decided by the owner: 19073866 → 89746993 (D-12-E, recorded in ROADMAP.md).
3. **Spot-checks** — five additional backfilled WRs spot-checked: four (89841789, 89848991, 89877351, 89954686) regenerated under the real `_User_<name>` filename in run 33974128574 with the matching `_User_Unknown_Foreman` file removed seconds later, no `RESET_WR_LIST` nudge needed; the fifth (90851321) was already live under its real name from an earlier run and was untouched by this run (consistent). Across the whole set: all 76 backfilled pairs have a `group_state` row; 91 `_User_<real name>` rows across 30 WRs; 0 live placeholder attachments on those pairs. **Verdict: pass.** Hygiene note (not a gap): 15 `pipeline_memory.group_state` rows for `Unknown_Foreman` on backfilled pairs remain after their attachment was deleted — the sentinel-superseded gate removes the attachment but leaves the stale `group_state` row.
4. **No PPP attachment deleted** — every `🗑️ Removed off-contract variant` line in run 33974128574 names sheet 5723337641643908 (`TARGET_SHEET_ID`); 0 reference `SUBCONTRACTOR_PPP_SHEET_ID` 8162920222379908 or any other sheet; the 51 `✅ Deleted:` lines are the normal delete-then-reupload replace pattern. **Verdict: pass** (confirmed by log inspection; no before/after PPP count was captured).
5. **No real person's history touched** — 0 of the 1,758 backfilled rows have a punctuation-leading `frozen_primary`; all 64 removals were `_User_Unknown_Foreman` files; the only punctuation-leading attachments on the sheet are the 10 `WR_90250489_..._User__NO_MATCH.xlsx` files (D-12-C `defer`), all still present. **Verdict: pass.**
6. **Duration vs `TIME_BUDGET_MINUTES`** — run 33974128574 Python step 47:51 (baseline pre-apply run 33928680844: 31:55; the first post-6e6e1e8 run 34530899488: 63:19) — never within reach of the 165-min budget. **Verdict: pass.**
7. **Conclusion / Sentry** — 33974128574 `success`; Sentry `generate-weekly-excel` has no new issue first-seen after 2026-09-05; the run's `🚨 Shadow parity FAIL` line is the pre-existing GENERATE-WEEKLY-EXCEL-AH (INC-06, recurring since 2026-08-19), not new; the chronic "154 group(s) ... have no row on target sheet" line is a pre-existing data-quality condition present in all three inspected runs. **Verdict: pass.**

**Not a gap / gap candidates for `/gsd-verify-work 12`:** (a) `sentinel_claimers_ignored` has no production counter — verify sentinel churn via the `Sentinel-superseded` / `Removed off-contract variant` log lines and the target-sheet inventory instead; (b) `backfill_run_id = ''` (not NULL) on local-operator runs (pre-existing observation from Task 3); (c) stale `Unknown_Foreman` `group_state` rows survive the sentinel-superseded attachment delete (hygiene, not correctness); (d) the SC3 sample substitution (19073866 → 89746993, D-12-E) — recorded in ROADMAP.md; (e) CR-01 / WR-01 (already known, filed in `12-REVIEW.md`).

**Owner actions DONE (2026-09-10 ~23:45Z, Juan's reply verbatim: `Approved` / `Adopt 89746993` / `Yes drop them using our supabase connector`):**

1. Approved this Task 4 record.
2. Recorded ROADMAP SC3 sample 89746993 (decision D-12-E).
3. Dropped the three backups `attribution_snapshot_backup_20260903` / `_20260904` / `_20260905` via the Supabase connector — migration `drop_attribution_snapshot_backups_20260903_04_05` on project `poeyztlmsawfoqlanucc`. Pre-check: live `billing_audit.attribution_snapshot` 224,371 rows / 1,758 with `backfill_provenance`, no dependent views; backups held 220,010 / 220,621 / 221,276 rows. Post-check: 0 `attribution_snapshot_backup_%` tables remain; live table unchanged at 224,371 / 1,758.

The 2026-09-03 first-attempt note below records why Tasks 2-4 did not run then: Task 1 recorded `reject`, so Task 2's precondition was unmet by design.

## Files Created/Modified

None. Task 1 is a read-only dry-run; the only artifact it produces (`generated_docs/own03_backfill_report.json`/`.csv`) is git-ignored and was not committed.

## Decisions Made

- Juan REJECTED the OWN-03 dry-run report with reason "source-3 filename parser defect" — no live write authorized. This is the plan's designed stop, not a deviation: the checkpoint's resume-signal explicitly allows `approve`, `approve-with-scope`, or `reject` with reason, and REJECT is the outcome Task 1's own acceptance criteria anticipate.

## Deviations from Plan

None - plan executed exactly as written. Task 1's checkpoint reached its designed REJECT outcome; per Task 2's unmet precondition, execution correctly halts there rather than proceeding to the authorization, apply, or post-run verification tasks.

## Issues Encountered

The dry-run surfaced a defect in `scripts/backfill_claim_time_attribution.py` (shipped in plan 12-01): source 3's filename-derived claimer extraction does not account for the hash-less filename shape production actually stores in `public.artifacts.filename`, causing it to propose a sentinel string as a real name. This is a code defect in an already-shipped plan, not something this plan's checkpoint tasks are scoped to fix (Task 1 is read-only by design). Routed to `/gsd:plan-phase 12 --gaps` rather than fixed inline, per the plan's own "record it as a phase gap" instruction pattern and the Living Ledger's recorded route.

## Checkpoint history

**Status update (2026-09-10, final):** the gap route below was closed by plans 12-07..12-10 (2026-09-04); 12-06
re-entered and ran Tasks 1-3 to completion on 2026-09-05; Task 4's seven observations were recorded 2026-09-10
(all pass, above) and Juan replied `Approved` the same day ~23:45Z (plus `Adopt 89746993` and `Yes drop them
using our supabase connector`), closing the plan. This section is preserved as history of the 2026-09-03 REJECT
outcome and the subsequent re-entry; the plan is no longer halted — it is COMPLETE.

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

Plan 12-06 (Ownership Attribution Live Remediation, OWN-03) is COMPLETE: Tasks 1-3 landed the live apply
(2026-09-05, 1,758 rows), Task 4's seven observations are on record (2026-09-10, all pass), and Juan approved
Task 4 plus D-12-E (sample WR 89746993) and the backup drop on 2026-09-10 ~23:45Z. `/gsd-verify-work 12`
passed 2026-09-11 (12-UAT.md 34/34, 12-VERIFICATION.md 77/77 must-haves; the Task 4 gap list — no
`sentinel_claimers_ignored` counter in production output, `backfill_run_id=''` on local runs, stale
`Unknown_Foreman` `group_state` rows after the sentinel-superseded delete, CR-01, WR-01 — is parked as owner
follow-ups) and `phase.complete 12` closed the phase. Next, in order: (1) the PR #402 owner follow-ups
(`.planning/todos/pending/2026-09-10-pr402-review-followups.md`); (2) Phase 13 (`wr_week_ownership`, D-12-A)
only when Juan asks.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-10 (first attempt halted 2026-09-03)*
*Status: COMPLETE (Tasks 1-4; Task 4 approved 2026-09-10 ~23:45Z — see Checkpoint history)*
