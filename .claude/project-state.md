# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-09-08 12:30 CDT (2026-09-08 17:30Z) · **overwrite-in-place each session** — this is
the canonical "where the project stands" landing spot for the global Stop write-back reminder. Cap ≤ 120
lines (`align-instruction-files` skill); history goes to `memory-bank/living-ledger.md`, never here._

_Latest ledger entries: `[2026-09-03 15:55]` (RPC EXECUTE defaults to PUBLIC; dated backups expire), `[2026-09-03 13:55]` (Phase 12 ownership contract, waves 2–3), `[2026-09-03 11:05]` (Greptile source-1 in-week guard fix on PR #387), `[2026-09-03 01:20]` (Phase 12 wave 1 — OWN-03 backfill tracer, review fix round, PR #387),
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
  **GSD tooling (global, 2026-09-06 20:20Z):** gsd-core 1.13.0 via the marketplace plugin + junction layout;
  this session's `/gsd-core:gsd-update` ran the forbidden npm reinstall and was fully rolled back the same
  session (no repo file changed). Record: `~/.claude/project-state.md` 2026-09-06 + `~/.claude/lessons-learned.md`
  (2026-08-23 lesson, "Recurred" addendum). Rule: never accept the npm install prompt on this machine.
- **Phase 14 "Foreman Helper #2" — EXECUTING since 2026-09-06 20:29Z (Juan invoked `/gsd-execute-phase 14`; wave 1:
  14-01 ✓, 14-02 in progress — status below). Planning record (02:45Z):**
  `/gsd-plan-phase 14 --research` completed end to end — researcher (`14-RESEARCH.md`, `7b95fe4`), Nyquist seed
  (`7e646e4`), pattern mapper (`14-PATTERNS.md`, `e5287a8`), planner (10 plans / 6 waves), checker × 3 (iter 1: 2 blockers
  — checkpoint tasks lacked the canonical `<decision>/<options>/<resume-signal>` children and four owner checkpoints lacked
  `gate="blocking-human"`, which auto-mode silently bypasses; revised → iter 2: 0 blockers / 4 warnings; orchestrator fixed
  three → iter 3: 0 blockers / 1 cosmetic tally, fixed after the run and re-validated deterministically). Gates: plan
  structure 10/10 valid, verify-command probes 63/63 clean, decision coverage 12/12, requirements HLP-01..07 7/7, plan:post
  gap analysis 19/19. Committed `fd2d5af` (D-14-10 bullet reflow so the GSD parser reads it) and **`af1221e` `docs(14):
  create phase plan`** (10 × PLAN.md + RESEARCH + VALIDATION + STATE + ROADMAP) on `feat/phase-12-remediation`; nothing pushed.
  **Seven `blocking-human` checkpoints** hold every production boundary: 14-02 T3 (owner-run live column probe), 14-04 T1
  (`row_state` Helper #2 DDL + hash inclusion), 14-07 T1 (`sheet_registry` mapping-schema marker shape), 14-08 T1 (**O-14-A**
  same-row dual-helper rule, still OPEN — only its Task 2 is blocked), 14-09 T2/T3 (attribution migration apply + read-back
  that closes assumption A4), 14-10 T3 (flag default / Actions wiring / one controlled upload). 14-10 T2's live
  upload-suppressed rehearsal step is preconditioned on a dated owner authorization and a code-verified no-write reading.
  STATE.md (GSD-owned): `current_phase: 14`, frontmatter `status: executing` = GSD's "READY TO EXECUTE" position,
  `stopped_at` = planning-approval checkpoint; the Phase 12 resume pointer (12-06 Task 4, Sat 15:00Z run) lives in
  `.planning/HANDOFF.json`. The assembled planner prompt (`14-PLANNER-BUNDLE.md`) was moved to the session scratchpad,
  not committed. **Execution 2026-09-06 (sequential on the main tree — GSD #683 degrade, branch HEAD 59 ahead of
  `origin/master`):** 14-01 tracer DONE `3d6bcfb`→`11a473d` — `HELPER2_ENABLED` (default `'0'`, `pipeline/config.py`),
  `FORMULA_ERROR_VALUES` + `normalize_helper_value()` fabricated-claim guard (`types.py`, also rejects literal `NA`), six
  Helper #2 synonyms (`discovery.py`), `sheet_has_helper2_columns` gate + `_detect_helper2_row()` (`fetch.py`),
  `valid_helper2_row` + `helper2` emission with the primary gate extended `and not valid_helper2_row` (`grouping.py`),
  `HELPER2=` hash meta + `Helper2` filename token (`change_detection.py`), `derive_group_identity` branch
  (`orchestrate.py`), `_Helper2_<name>` suffix + header (`excel.py`) — all parallel sibling blocks, no Helper #1 tuple
  widened. New `tests/test_foreman_helper_2.py`, `tests/test_helper2_family_parity.py` (`KNOWN_DEFERRED` for 14-06's
  two `excel.py` shadow branches); 3 source-text pins updated in `test_subcontractor_pricing.py` /
  `test_subcontractor_helper_shadow_rescue.py`. Suite 2140 passed / 1 skipped; FIXTURE PASS only. `REQUIREMENTS.md`
  untouched (cross-plan HLP ids). **No Smartsheet, Supabase, workflow, attachment change; nothing pushed.** 14-02
  (docs-only) T1 `8dfea37` + T2 `55e3428` done → `14-PENDING-RESOLUTIONS.md`: A1/A2 first-run suppression SAFE
  (`group_state` skip keyed on the full variant tuple; pre-seed needs exact variant match), parity check gated off in
  prod, A3 = attribution/pricing no change for plain `helper2` (shadow pricing → 14-06), observability PII-marker gap
  (`HELPER2 GROUP CREATED` embeds a raw name → 14-07/14-08). **STOPPED at T3 `blocking-human` (21:25Z):** owner-run
  read-only live column probe (4 questions: Main ProMax six titles, partial sets elsewhere, Intake 8/Backup 2 still
  bare, Resource Analyst `Foreman Helper #2` still blank) → record titles/ids/counts only in `14-DECISIONS.md` with
  `LIVE-COLUMN-PROBE: ANSWERED` + date + pilot consequence + `read-only`; reply "approved" to resume.
  **T3 probe RUN (owner-delegated, 2026-09-06 ~23:20Z, read-only via the Smartsheet connector, zero writes):**
  117 sheets swept (Intake folder 11 + ProMax Database folder 105 + Resource Analyst) → 114 FULL 6/6, 3 NONE
  (Intake ProMax 8, Backup 2, Resource Analyst), **0 PARTIAL**; Main ProMax 6/6 with ids; RA `Foreman Helper #2`
  (`1589780186173316`) 0 non-blank of 576 rows → **14-10 pilot is FIXTURE-ONLY**; no drift vs the 09-05 snapshot.
  Recorded in `14-DECISIONS.md` (titles/ids/counts only, no names, no picklist options). **14-02 ✓** T3 `41f14b1`,
  closeout `34c2f56` (SUMMARY Self-Check PASSED; only `.planning/` touched). **Wave 1 gate green** (py_compile OK;
  2140 passed / 1 skipped). Closeout had flipped HLP-04/06/07 to Complete prematurely → reverted to Pending in
  `32e8452` (owners: 14-03/04/05/09 for HLP-06, 14-10 for HLP-07, 14-07/14-10 for HLP-04; verifier flips on
  evidence). **Wave 2 (sequential): 14-03 ✓** `7509709` `5c44d49` `58d73d2` + docs `4ecb76a` `595fe70` — `p_helper2`
  in the freeze payload and all-sentinel gate, D-14-07a degrade path (`helper2_attribution_degraded` counter, golden
  25 keys), `helper2` in `ROLE_BY_VARIANT`; 6 gates green, 2156 passed / 1 skipped; FIXTURE PASS only. **14-05 ✓**
  `9fd7ee4` `4b7940b` `3224982` `a706b11` `40365e2` + docs `dcf2406` — cleanup orphan-supersede frozenset gains the
  three Helper #2 variants (legacy gates byte-identical), `normalize_variant` parses `_AEPBillable_Helper2_` /
  `_ReducedSub_Helper2_` / `_Helper2_` ahead of the bare checks, portal `VARIANT_LABELS` +3 keys; 2172 passed /
  1 skipped. **Portal typecheck NOT run** (`portal-v2/node_modules` absent; recorded as human-judgment D6 in the
  SUMMARY — run `npm run typecheck` in `portal-v2/` before merge). **14-04 T1 `blocking-human`
  presented to Juan (00:05Z 09-07):** approve four additive nullable `row_state` columns + choose `HASH_FIELDS`
  include-now / defer-hash / reject-ddl. Live read-only facts (`poeyztlmsawfoqlanucc`): row_state 217,491 rows,
  row_event 218,931, 58 runs, no helper2 columns yet. **Correction to the plan text:** `RUN_MEMORY_WRITE_ENABLED`
  is `'1'` in the weekly workflow since PR #353 (2026-08-26), so include-now means ~217k real row_event inserts on
  the first production run after deploy (read path still OFF, so no output/regeneration effect). Awaiting decision.
  **14-06 started ahead of 14-04 (00:20Z 09-07)** on dependency truth: it depends on 14-01/03/05 only and shares no
  file with 14-04 (`pipeline_memory/*`, `scripts/mem04_passive_compare.py`); wave-2 gate re-run in background;
  key-links for 14-06/14-07 clean. 14-07 (depends on 14-04) and 14-08+ stay blocked until Juan answers 14-04 T1.
  **Wave-2 gate green** (2172 passed / 1 skipped). **14-06 ✓** `b320e6b` `321d503` `fbaf085` + docs `33cdc27` —
  subcontractor Helper #2 shadow partition in `grouping.py`, shadow filename/header/hash sub-bucketing in
  `excel.py` / `change_detection.py`, PPP dual-route gate in `upload.py`; `KNOWN_DEFERRED` cleared; 6 gates green,
  2196 passed / 1 skipped; D-14-09 byte-identity fixture unaffected; FIXTURE PASS only. Its closeout marked
  HLP-01/02/05 Complete — HLP-05 reverted to Pending (14-08 still owes it); HLP-01/02 owner plans are all done.
  **Run is now blocked solely on Juan's 14-04 T1 decision** (14-07 → 14-08 → 14-09 → 14-10 chain behind it).
  **Juan decided `include-now` (2026-09-06 evening CDT):** recorded as `D-14-08-APPLIED` in `14-DECISIONS.md` (four
  columns, owner-applied in `poeyztlmsawfoqlanucc` via SQL Editor, NOT applied yet, timing left to rollout, ~217k
  one-time production row_events because the write flag is ON, read flag OFF). 14-04 continuation executor
  running Tasks 2–3 (schema.sql DDL text, writer payload + `HASH_FIELDS` append, passive-compare mirror; must prove
  both DDL orders). No DDL executed from the session.
  **14-04 ✓** `c452f72` (decision) `72dcd8d` (row_state DDL text + payload + `HASH_FIELDS` append) `c9739d7` (mem04
  mirror) + docs `3dd88b7`; 2206 passed / 1 skipped, 6 gates green; schema.sql diff additive-only. Rule-3 deviation:
  `tests/test_incremental_read.py::test_schema_untouched` (Phase 11 blanket freeze) replaced by
  `test_schema_changes_are_additive_only` (zero removed/modified lines). HLP-06 flipped Complete again → reverted
  `f4e3c14`. **NEW OPEN ITEM O-14-B (`14-DECISIONS.md`, commit follows):** `upsert_rows_bulk` RPC body still lists
  only Helper #1 fields, so helper2 columns would stay NULL after the DDL and the ~217k churn buys nothing; no plan
  owns the RPC update. Recommendation: gap-closure plan via `/gsd-verify-work 14`, owner applies RPC + DDL in one
  SQL session before the code merge. **Wave 2 closed green** (2206 passed / 1 skipped). **Juan decided 14-07 T1:
  `separate-column`, degrade "slower but correct"** → `D-14-10-APPLIED` in `14-DECISIONS.md`: `sheet_registry.
  mapping_schema TEXT NULL`, marker `helper2-v1` (`MAPPING_SCHEMA_MARKER` in `pipeline/discovery.py`), sixth
  skip-index gate, unknown-column → one warning + full validation for all sheets; one-time cost 37.7 s Phase 1
  (11.1-04 canary); owner-applied in `poeyztlmsawfoqlanucc`, not applied yet (unverified 2026-09-08). **14-07 COMPLETE
  (2026-09-08 14:05Z):** `0f2874f` T1 record · `50b630d`/`2e98d3f` T2 marker, sixth skip-index gate, reader degrade,
  writer · `ac38699`/`e7aa054` T3 `helper2_no_qualifying_completion`, price-exclusion Helper #2 tag, partial-column,
  Intake-8 fixture (HLP-04, fixture-only), failed-validation pinned · `af7d55f` SUMMARY + STATE/ROADMAP (7/10).
  Evidence: helper suite 31 passed / 26 subtests; full suite 2222 passed / 1 skipped / 541 subtests; ALL 6 GATES PASSED.
  HLP-03 stays Pending until 14-08, HLP-04 until 14-10 (last-contributing-plan convention).
  **Juan resolved O-14-A (2026-09-07): `helper2-wins`** — owner-defined fifth option: Helper #2 > Helper #1 >
  primary on one row; losing claim dropped for that row with visibility in **Sentry AND run summary** (no PII);
  prototype abort rejected. Recorded as `O-14-A RESOLVED` in `14-DECISIONS.md`, committed `ede01a9` (= 14-08 T1).
  Follow-up on per-slot file duplication unanswered → D-14-06 default stands, doc-only. **14-08 COMPLETE (2026-09-08
  15:07Z; `/gsd-core:execute-phase 14` resumed, Sonnet executor sequential on the main tree — worktree base-check
  degraded, branch 97+ ahead of `origin/master`):** `c1d096b`/`b3ae217` T2 helper2-wins at the plain + shadow emission
  sites in `pipeline/grouping.py` (pre-pass agreement, conflict reason logged once, counted, Sentry ids/counts only;
  14-06 placeholder test replaced) · `4aeea1e`/`bede1c0` T3 four pre-seeded Helper #2 run-summary counters in
  `pipeline/orchestrate.py` + `tests/golden/run_summary_baseline.json` (25 → 29 keys) · `30d7d8a` SUMMARY + STATE/
  ROADMAP (8/10) + HLP-03/HLP-05 Complete (that docs commit lacks the session trailers — left un-amended). Orchestrator
  gates: full suite 2230 passed / 1 skipped / 541 subtests; ALL 6 GATES PASSED; schema-drift/ui gates clear. Ledgers
  `fe01e6e`. **Incident (read-only):** the executor's first `TEST_MODE=true` run loaded the `.env` token and fetched
  121 live sheets / 217,741 rows (18.8 min) before the orchestrator killed it ahead of Excel/upload — no write; fixed
  in `0203e27` (CLAUDE.md/copilot/safe-commands now `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true
  PYTHONUTF8=1 …`, living-ledger `[2026-09-08 10:20]`). **14-09 T1 DONE `66924c0` (+ `a64f761` blocker
  record), STOPPED at T2 `blocking-human` 15:45Z:** `billing_audit/helper2_attribution.sql` (5 owner-run steps; STEP 2b is a
  manual splice because the freeze body lives only in Supabase), `schema.sql` contract/comment fix, contract test (19 passed).
  Orchestrator fix `c786ec3`: `DEFAULT NULL` on `p_helper2`/`p_helper2_dept` so the deployed 12-parameter writer still
  resolves the RPC after the migration (PostgREST needs every non-default named arg) — this is what makes sql-first safe.
  Gates on the fixed tree (final rerun after `c786ec3`): full suite 2249 passed / 1 skipped / 550 subtests; ALL 6 GATES
  PASSED. **14-09 T2 DONE — Juan chose `sql-first` and delegated the apply to the session (Supabase MCP), 2026-09-08:**
  migration `20260908165511_helper2_attribution_columns_and_rpcs` applied 16:55:11Z on `poeyztlmsawfoqlanucc` as one
  transaction (2 nullable columns; `freeze_attribution` rebuilt from its live body with `p_helper2`/`p_helper2_dept`
  appended LAST `DEFAULT NULL`; both lookups DROP+CREATE with the new columns and their live pinned `search_path`; grants
  restored identically). Landed ≈75 s into run 34253845749's job setup (created 16:53:55Z, before any billing_audit call)
  rather than the intended run-free gap — recorded as-is. Pre-state + rollback: vault `raw/2026-09-08 - billing_audit
  Helper #2 attribution migration pre-state (rollback reference).sql`. **T3 read-back (D-14-07-VERIFIED) checks 1–3
  OBSERVED** (both lookups return the columns on a real row; table has both columns; synthetic-row freeze test: 12-arg
  writer call resolves, 14-arg call writes Helper #2, conflicting re-freeze leaves the row byte-identical; synthetic rows
  deleted, total back to 222,260). **Check 4 OBSERVED 17:55Z:** run 34253845749 (deployed master writer, created
  16:53:55Z, success 17:49:53Z) made 74 `freeze_attribution` calls, all 200, 0 PGRST; 6 bulk lookups, all 200; 221,616
  keys warm-started through the new shape; its 74 rows carry a primary and `frozen_helper2` NULL. The Phase 14
  degrade-warning check is post-merge only (PENDING-UNTIL-MERGE). Records + SQL alignment: `3d6263a`. **O-14-C → plan
  14-11 (inserted 2026-09-08, wave 6; 14-10 moved to wave 7, depends on 14-11; Juan: "work on O-14-C before building
  out plan 10"):** first-write-wins per ROLE for Helper #2 only — T1 (TDD) admission rule (`helper2_fill_admits`: row
  has valid Helper #2 AND prefetched helper2 null/sentinel AND flag on) + `snapshots_helper2_filled` counter (baseline
  → 30 keys); T2 `billing_audit/helper2_attribution_fill.sql` (CREATE OR REPLACE, same 14-param signature, `ON CONFLICT
  DO UPDATE SET frozen_helper2/frozen_helper2_dept/backfill_provenance.helper2={live,run_id} WHERE is_sentinel_value(s.
  frozen_helper2) AND NOT is_sentinel_value(EXCLUDED.frozen_helper2)`) + contract test; T3 `blocking-human` apply
  (apply-delegated / apply-owner / defer) + synthetic-row read-back → `O-14-C-APPLIED` / `O-14-C-VERIFIED`. **NEXT:**
  Juan types "approved" at 14-09 T3 → 14-09 closeout; 14-11 T1–T2 execute (repo-only, inert against the deployed
  function) → T3 decision → 14-10. No Smartsheet write or workflow change without Juan.

## Latest work (2026-09-03 evening → 2026-09-05 00:30 UTC) — Phase 12 waves 2–3 merged (PR #388 → `1f159bc`, master green); 12-03 SQL live + verified; G-12-3 gap closure DONE on `feat/phase-12-remediation` (12-07..12-10 ✓; RPC extension guard + `attribution_snapshot_backup_20260904` live); **12-06 Task 1 full-scope dry-run RE-RUN clean (0/0/0 guards) — awaiting Juan's verdict**; code-quality pass: CR-01 latent (0 live rows), WR-01 ledger-test brittleness — nothing pushed

- **2026-09-05 00:24–00:26 UTC (19:24 CDT 09-04) — `/gsd-execute-phase 12` resumed at 12-06 Task 1; orchestrator ran the
  read-only full-scope dry-run, checkpoint presented, WAITING on Juan (`approve` / `approve-with-scope` / `reject`).**
  Index note: `init.execute-phase` counts 12-06 complete (SUMMARY presence only) but `phase-plan-index` honors
  `status: blocked` and lists it as the only runnable plan (wave 4) — no stuck-on-halt. Scope enumerated read-only via
  Supabase MCP SQL, identical to the 09-03 run: 207 WRs × 54 weeks, 391 pairs, 6,764 named-sentinel rows (5,829
  primary `Unknown Foreman` + 945 `#NO MATCH`, deferred per D-12-C); snapshot 221,276 rows (655 above the `_20260904`
  backup), 0 rows carry `backfill_run_id`. Dry-run exit 0 in 95 s, 652 reads all 200, report in the session scratchpad
  (`own03_dryrun/`, outside the repo; never committed). **Result:** 5,829 rows → proposed 1,758 (artifacts 1,066 +
  live 692; 30 WRs, 76 pairs, 24 names), conflict 0, unresolved 4,071 (70 WRs, 180 pairs, all exhausted-precedence);
  `backfill_hash_history` resolved 0 — the 4,070 formerly-placeholder rows are genuinely evidence-less (SQL: their 180
  pairs hold only placeholder-named artifacts or none). **Guards:** extension-bearing 0, hash-tailed 0 (CR-01 check),
  sentinel-classified 0, blank/punctuation 0. **Cross-check:** 1,758/1,758 proposals agree with the `public.artifacts`
  filename, 0 disagreements; independent SQL finds real-name artifacts on exactly those 76 pairs / 30 WRs. **Finding:**
  D-12-D sample WR 89829163 is UNRESOLVED on all four weeks — its 33 artifacts and its hash identifiers are all
  placeholder-named, so ROADMAP SC3 as amended is unsatisfiable (the 09-03 run "resolved" it only via the defect);
  candidates with one name over ≥4 weeks: 89746993, 89841789, 89848991 (artifacts), 90851321 (live, 6 weeks) — Juan
  to re-decide with the verdict. **Backup:** UTC rolled to 09-05, so `_20260904` no longer passes the `--apply` probe;
  Task 3 needs a fresh STEP 1 (`_20260905`, valid to 2026-09-06 00:00 UTC) — not created. No executor dispatched; tree
  unchanged apart from the pre-existing claude-mem docs edits. Evidence: scratchpad `own03_dryrun/evidence_12-06_task1.md`.
  **Juan: `I approve` (Task 1) → recorded + committed `9fab1ab`. Task 2: Juan `apply-full` (2026-09-05 ~02:45 UTC) →
  recorded in 12-06-SUMMARY (`29c3859`). **Task 3 DONE 2026-09-05 03:40–04:15 UTC (Fri 22:40 CDT) at Juan's `Run it`:**
  orchestrator ran STEP 1 via Supabase MCP → `attribution_snapshot_backup_20260905` = 221,276 rows = live, service_role
  SELECT true, `_20260903`/`_20260904` intact; then the local CLI apply over the exact dry-run scope (exit 0, 97 s, 657
  reads all 200, 4 RPC calls): **updated 1,758 / skipped_real_name 0 / skipped_no_row 0 / client-side 0 / errors 0**
  (artifacts 1,066 + live 692; 30 WRs / 76 pairs / 24 names). Read-back: 219,518 untouched rows → 0 diffs on all three
  role columns vs the backup, 0 rows missing either way; all 1,758 touched rows were sentinel in the backup and are real
  now, helper/vac unchanged, provenance jsonb present + source-matched, vocabulary valid, total = updated. Observation:
  `backfill_run_id` = '' on all 1,758 (local run, no GITHUB_RUN_ID; `_compute_run_id()` normalizes to '') → low-severity
  provenance note for verify-work. Remaining: `Unknown Foreman` primary 4,071 (→ source 5), `#NO MATCH` 945 (D-12-C).
  **Task 4 = observe the first post-apply `weekly-excel-generation.yml` run = Sat 2026-09-05 15:00 UTC** (the workflow
  has a weekend cron `0 15,19,23 * * 0,6`; 0 runs since the 03:45Z apply — last run 2026-09-04 23:13Z, 6 files, ~33 min
  baseline). Juan typed `Verified` at ~05:40Z before any run existed → not accepted; he chose to wait. Expect ≈ 76 files
  / 30 WRs regenerating under real names vs the 6-file baseline; placeholder attachments removed by the
  sentinel-superseded gate; no PPP deletions; duration < 165 min; 3 WR spot-checks. Trigger: `check the run`.
  ROADMAP SC3 sample must be re-decided (`sc3: <WR>`) before Task 4 step 2 (WR 89829163 unresolvable; candidates
  89746993 / 89841789 / 89848991 / 90851321). Do NOT drop `_20260903` / `_20260904` / `_20260905` until Task 4 is
  verified. Evidence: scratchpad `own03_apply/`.**
  **Read-only probe of `public.smartsheet_unified_history` (Juan's question, ~01:00–02:00 UTC):** audit-trigger change
  log of `smartsheet_unified` (~60.2M rows, captures start 2025-11-04 — after every affected week), plus an undocumented
  derived `smartsheet_unified_history_foreman` change-log (1.29M rows). Via the `row_state` bridge (5,820/5,829 rows →
  10 sheets) it gives 3,987 of the 4,071 unresolved rows a real→placeholder flip (Nov 2025 954 · Dec 727 · Jan 2026
  2,306 = a systemic remap, all ≥30 days after the week); 2,306 rows / 20 WRs carry ONE prior name, 1,681 rows / 22 WRs
  carry TWO (A → placeholder → B → placeholder; WR 89829163 is one of them), 84 no flip. Verdict: useful as a
  cross-check, not admissible under D-12-A (no in-week evidence); the designed path for these rows is source 5
  (`backfill_cell_history_attribution.py`, now viable: ≤2 calls/row, MAX_ROWS 1,200/run → ~4 runs). Any use of the
  history table as a source needs a new decision (D-12-E) and a gap plan. Evidence: scratchpad
  `own03_dryrun/evidence_unified_history_probe.md`. Nothing written to Supabase. **Whole-project inventory (same
  session, read-only):** every other candidate is either current-state (unified / `_corrected` [0 corrected rows] /
  folder_sync / live → sentinel on 4,070), a later-starting change log (folder_sync_history 2026-04, project_list_history
  2026-02, run memory 2026-08), absent for these row_ids (archived_promax_work_requests, promax_current_snapshot),
  name-free (pipeline_run, snapshot_provenance, group_content_hash, group_state), derived views over the same tables,
  or the storage bucket (created 2026-05-29, 0 pre-Nov-2025 files). Conclusion: no Supabase store holds in-week
  Jul–Nov 2025 foreman evidence for the 4,071 rows; only Smartsheet cell history (source 5) can.
- **2026-09-04 ~07:15 UTC — `/gsd-execute-phase 12 --gaps-only` CLOSED: 12-07..12-10 ✓, 12-06 re-entrant, phase left
  incomplete by design.** Wave-3 gates green (pytest 2,117 passed / 1 skipped / 441 subtests; `py_compile`; schema-drift,
  codebase-drift and UI gates `block: false`; 6-gate harness ALL PASSED). Close-out commits: `5121c30` reverted the
  executor's premature OWN-02/OWN-03 "Complete" marks (the shared-ID gate was satisfied by 12-06's halted SUMMARY while
  the live apply has not happened) and moved OWN-03's sample to WR 89829163 per D-12-D; `7ce962a` flipped
  `12-06-SUMMARY.md` to `status: blocked` so the plan index lists 12-06 as the only runnable plan; `634d93b` committed
  the code-quality report. `verify_phase_goal` / `update_roadmap` skipped on purpose (12-06 incomplete). **Code-quality
  pass (Opus `gsd-code-reviewer`, 7 delta files since `2c794a9`, `12-REVIEW.md`, advisory): 1 blocker, 9 warnings,
  2 info.** CR-01 (verified in code): `_FILENAME_HASH_SUFFIX_RE` expects a 6-hex tail but `pipeline/excel.py:412`
  emits the 16-hex `hexdigest()[:16]` tail, so a hash-tailed `..._User_Unknown_Foreman_<16hex>.xlsx` would pass every
  extension guard (Python strip/reject, payload builder, RPC) and be written as a real name. Live exposure today:
  none — a read-only count of `public.artifacts` shows 116,906 rows, 0 with any hash tail (first row 2026-05-29,
  after the `SUPABASE_HASH_STORE_AUTHORITATIVE=1` flip); the defect returns only if that flag is reverted. WR-01
  (verified): `tests/test_own04_documentation.py::_newest_ledger_entry` asserts D-12-C/D-12-D in the NEWEST
  `living-ledger.md` entry, so the next bottom-append (the CLAUDE.md rule) turns the push-gating suite red — no ledger
  entry was appended this session for that reason; session lessons went to the vault (`guardrail-allowlist-and-gsd-ops-lessons` §11).
  Other warnings: ROADMAP `### Phase 12` hard-assert (WR-02), fixtures never exercise a hash-bearing production shape
  (WR-08), runbook `--apply` example still names WR 19073866 (WR-09). Route: `/gsd-verify-work 12` after 12-06 files
  these as gaps (CR-01 fix = `{16}` tail + production-shape fixtures, folded with the six-hex-letter over-match ticket;
  WR-01 fix = search every ledger entry). Session mechanics worth knowing: the harness-boundary hook denies any
  gsd-tools argument containing the token "review" (commit messages, decisions, `query init.code-review`) — reword or
  resolve the inputs from files; Bash-scripted ledger edits are invisible to the context-continuity Stop hook (it reads
  `session-delta.jsonl`, Edit/Write only); `status: blocked` (not `halted`) is the only SUMMARY state that makes a
  plan re-entrant; the GSD executor has no Agent tool, so plan tasks that require an independent reviewer run from the
  orchestrator; ~104 KB of executor context shipped as one bundle file the executor Reads first (7/7 dispatches fine).
- **2026-09-03 late night → 2026-09-04 — `/gsd-execute-phase 12 --gaps-only` run detail (3 waves, sequential on
  `feat/phase-12-remediation`; worktree base-check degraded because HEAD is ahead of `origin/HEAD`; ledger commits
  `360fde7`, `27787cc`, `f2765fc`).** 12-07 DONE
  (Sonnet executor, 7 commits `8d27e36`…`f14aa5c`, SUMMARY `Self-Check: PASSED`): `_extract_claimer_from_filename`
  now strips exactly one trailing document extension when the `_<6hex>.xlsx` hash tail is absent and rejects any
  candidate still ending in one, so the live hash-less `..._User_Unknown_Foreman.xlsx` shape reaches
  `is_sentinel_claimer` as a classifiable sentinel (no proposal); the hash-suffixed path is byte-identical;
  `_build_apply_payload` gained a `proposed_value` sentinel/extension guard mirroring the `current_value` one.
  File suite 60/60; full suite 2,107 passed / 1 skipped / 416 subtests; diff confined to the two declared files.
  12-08 DONE (continuation executor after Juan's written answers at the blocking-human gates, 3 commits
  `cf13670`…`e1c7ac8`): **D-12-C = `defer`** (the 945 `#NO MATCH` rows stay out of OWN-03; 12-10's re-run carries no
  `--include-blank-roles`), **D-12-D = `substitute-89829163`** (ROADMAP SC3 now names WR 89829163 WE
  082425/083125/091425/092125 resolved via `backfill_artifacts`; WR 19073866 dropped as unprovable); runbook
  scope statement, ledger `[2026-09-04 10:05]`, docs tests 25/25, Docusaurus typecheck + build green;
  REQUIREMENTS.md deliberately left Pending for OWN-03/OWN-04. Wave 1 close gates: post-wave pytest 2,112 passed /
  1 skipped / 416 subtests (37.8 s), py_compile, schema-drift / codebase-drift / UI gates clear.
  **Wave 2 — 12-09 Tasks 1–2 DONE** (`f6aa6d9` test, `b51faa0` feat, `5baed30` docs): STEP 4's validation loop now
  also raises when a proposed `value` ends in `xlsx|xlsm|xls|csv|pdf|json` (case-insensitive), pinned to 12-07's
  `_FILENAME_DOC_EXTENSION_RE` by the contract test (25/25); `is_sentinel_value`, STEP 5 REVOKE/GRANT, RETURNS
  TABLE, `p_rows` list and the three UPDATEs untouched (diff gates exit 0); `schema.sql` documents the two-ground
  refusal (comment-only). Suite 2,117 passed / 1 skipped / 441 subtests. **Task 3 APPLIED LIVE 2026-09-04 05:37 UTC**
  by the main session through the Supabase MCP at Juan's explicit instruction ("you run step 4 for me") — STEP 4
  (DROP + CREATE) then STEP 5 REVOKE/GRANT + `NOTIFY pgrst` on `poeyztlmsawfoqlanucc`; STEPs 1–3 not re-run.
  Read-backs: EXECUTE anon=false / authenticated=false / postgres=true / service_role=true, `proacl`
  `{postgres=X/postgres,service_role=X/postgres}`, extension guard present in `pg_get_functiondef`,
  `backfill_run_id IS NOT NULL` = 0, snapshot 220,621 rows unchanged; no RPC call made. Juan replied `approved`;
  12-09 CLOSED by a continuation executor (`f269f78` SUMMARY, `786329b` STATE/ROADMAP; deviation recorded =
  owner-authorized MCP apply). Wave 2 close gates: pytest 2,117 / 1 skipped / 441 subtests, py_compile, drift + UI
  gates clear. **Wave 3 — 12-10 Task 1 independent Opus `production-risk-reviewer` = PASS** (orchestrator-dispatched
  because the executor has no Agent tool; scoped diff `2c794a9..786329b` on the four files + the plan's 8-point
  rubric; no fix round; 2 LOW notes — source-4 identifiers bypass the extension filter but are name segments, and
  the residual-extension reject also narrows the hash-suffixed path; residual risks recorded, incl. the
  pre-existing `_FILENAME_HASH_SUFFIX_RE` over-match on a six-hex-letter final name segment → separate ticket).
  12-10 Task 1 closed by the executor (suite 2,117, py_compile, `run_6_gates.sh` ALL 6 PASSED; review-only, no
  commit). **Task 2 backup created 2026-09-04 06:07:36 UTC** by the main session via Supabase MCP at Juan's choice
  ("Run STEP 1 for me via MCP"): `attribution_snapshot_backup_20260904` = 220,621 rows = live 220,621,
  `service_role` SELECT granted, `_20260903` (220,010) untouched; valid only for an apply before 2026-09-05 00:00 UTC
  (19:00 CDT 2026-09-04) — re-run STEP 1 if the 12-06 apply slips. **Task 3 dry-run DONE** (read-only, exit 0, exact
  pre-fix scope WR 89732091 × 7 weeks, no `--include-blank-roles`, report in the system temp dir then deleted,
  tree clean): 235 rows → 0 `proposed` / 235 `unresolved`; extension-bearing proposals 0 of 0 (was 235 of 235),
  sentinel-classified 0 of 0, `rows_by_source` `{}` — the placeholder is gone but no source has a real name for
  these rows, so the zero is vacuous; whether the 4,070 formerly-placeholder rows resolve via source 4 or end
  unresolved is 12-06 Task 1's full-scope dry-run to show. Awaiting Juan's `re-enter-12-06` / `hold`.
  Still to run: 12-09 (Juan applies the RPC extension guard, STEP 4 + STEP 5), 12-10 (Opus production-risk review
  of 12-07 + 12-09, fresh same-UTC-day backup, zero-defect live dry-run), then 12-06 re-entry at Task 1. The
  `.continue-here.md` blocking constraint was acknowledged: no PR carrying 12-07/12-09 before the Opus review
  (12-10 Task 1 encodes it).
- **2026-09-03 late — `/gsd-verify-work 12` started (UAT session open, branch `feat/phase-12-remediation`):**
  the `verify:pre` api-coverage gate (ai-integration capability) blocked with 4 bogus row errors because the
  phase `COVERAGE.md` "for the record" inventory table was parsed as a coverage matrix alongside the valid
  `No external API integration:` declaration; the table is now a bulleted list (same content) and the gate
  passes (`none_declared: true`, 3 detector signals overridden). `12-UAT.md` created from the six SUMMARY
  `coverage:` blocks: 21 entries, 18 auto-passed (tests), 3 human checkpoints pending — (1) 12-03 live SQL apply,
  (2) 12-04 dispatch-only workflow isolation, (3) 12-06 dry-run verdict (expected to log the known source-3
  filename-parser REJECT as the gap that feeds the gsd-planner gap-closure plans). **Checkpoint 1 PASSED** on
  Juan's request via a read-only Supabase MCP catalog check (project `poeyztlmsawfoqlanucc`): both tables live
  (snapshot 220,433 / backup_20260903 220,010 — drift now 423 rows, re-create on apply day), provenance columns +
  five-value CHECK present, RPC SECURITY INVOKER with EXECUTE = `service_role` only, `is_sentinel_value` keeps
  default PUBLIC EXECUTE (matches the SQL file, which revokes only the RPC), 0 rows carry `backfill_run_id`.
  **Checkpoint 2 PASSED** (read-only, no dispatch): `cell-history-backfill.yml` on master has no `schedule:`,
  own concurrency group, `timeout-minutes` 60 > cap 45, inputs bound via `env:`, no `${{` in `run:`, `--apply`
  only in comments, backfill step gated on `backlog_rows != '0'`; 48 unit tests green; GitHub registers it
  active with 0 runs. **Checkpoint 3 = ISSUE (blocker)**, re-verified by the session on Juan's request: Juan's
  full-set report analysed in-sandbox (4,070 of 4,762 proposals are the single string `Unknown Foreman.xlsx`; 0
  rows for WR 19073866; 0 via `backfill_hash_history`) and a scoped read-only live dry-run (WR 89732091 × 7
  weeks, report to scratchpad) reproduced it: exit 0, 235/235 rows propose `Unknown Foreman.xlsx`. UAT closed
  `status: diagnosed` (20 pass / 1 issue / 0 pending); gap `G-12-3` carries the root cause + 5 missing items
  from 12-06-SUMMARY § Halted at Designed Stop (no debug agent — nothing to re-derive). UAT + COVERAGE.md +
  ledgers committed `1e7fc1d`. **Gap-closure planned (Opus gsd-planner, `67bda0e`):** 12-07 (source-3 extension
  strip/reject + `_build_apply_payload` guard + hash-less fixtures, wave 1), 12-08 (owner decisions: `#NO MATCH`
  scope, SC3 sample → D-12-C / D-12-D, wave 1), 12-09 (owner-applied SQL: extension check in the RPC validation
  loop, wave 2), 12-10 (Opus production-risk review, fresh STEP 1 backup, zero-defect dry-run, re-entry into
  12-06 Task 1, wave 3); all `gap_ids: [G-12-3]`. **Root-cause correction (verified, SQL line 320):** the RPC
  already raises on a sentinel proposed value; the blindness is that `is_sentinel_value` never strips a file
  extension, so `Unknown Foreman.xlsx` passes in both layers — 12-09 adds an extension check and leaves
  `is_sentinel_value` byte-identical (it also drives the per-role `UPDATE … WHERE` targeting). **Plan-checker
  PASSED (iteration 3/3)** after two revision rounds that made every `<verify>` gate failing-capable (`7df9cbc`:
  `$SCRATCHPAD` → resolved `REPORT_DIR`, typecheck gate, SQL diff token gate; `7c47d45`: schema.sql doc test,
  option-aware D-12-C/D-12-D + SC3 tests). UAT correction committed `6684355`. **Next: `/clear` →
  `/gsd-execute-phase 12 --gaps-only`** (12-08 decisions and 12-09 SQL apply pause for Juan; no live write in any
  gap plan) → re-run 12-06 on a fresh same-UTC-day backup → `/gsd-verify-work 12` reconciles G-12-3. Second brain
  written back 2026-09-03 late (vault log `[2026-09-03t]`/`[2026-09-03u]`: project page subsection, PostgREST §4
  correction, gsd-ops-lessons §§9–10, dashboard/index/current-state); global `lessons-learned.md` entry added.
- **2026-09-03 night — 12-06 Task 1 read-only evidence (Juan asked the main session to run it):** dry-run for the
  plan's WR 19073866 exited 0 with 0 rows — that WR has zero rows in every Supabase store (snapshot, backup,
  group_state, row_state, row_event, group_content_hash, artifacts); the snapshot was never rebuilt (frozen_at from
  2026-04-24) and no Python path deletes snapshot rows, so the docs' WR is a placeholder or the rows were removed by
  hand. Fingerprint: only WR 89829163 has sentinel primary rows on exactly 082425/083125/091425/092125, but its
  `group_content_hash` identifiers are sentinel-only (2026-05-26) and `hash_history.json` is gone — ROADMAP SC3 "via
  backfill_hash_history" is not satisfiable from Supabase (phase gap to record). The auto-mode classifier blocks the
  script for any other WR; full-set lists are in the session scratchpad (`own03_wr_union.txt`, `own03_weeks_union.txt`).
  Live inventory: 6,764 named-sentinel rows / 207 WRs / 391 pairs (Unknown Foreman 5,829 + #NO MATCH 935 primary,
  10 helper, 0 vac; 52 non-8-digit WR keys; 0 backfilled). Source ceiling by SQL: sources 3/4 = 83 pairs / 32 WRs /
  1,985 rows; sources 1/2 = 692 primary rows / 7 WRs; ~4,000 rows have sentinel-only history (source 5 territory).
  Opus-MEDIUM check: 0 NULL-week / 0 stale-week row_state+row_event entries; 9 target rows without memory rows.
  **Full-set dry-run (Juan ran it via `!`, 207 WRs × 54 weeks): exit 0, 5,829 rows considered, proposed 4,762 /
  conflict 1,066 / unresolved 1 — and it is NOT safe to apply.** Source 3 (`backfill_artifacts`) strips a mandatory
  `_<6hex>.xlsx` suffix, but `public.artifacts.filename` has no hash (e.g. `WR_<wr>_WeekEnding_<mmddyy>_User_<name>.xlsx`),
  so the whole remainder survives and `Unknown_Foreman.xlsx` passes `is_sentinel_claimer`: all 4,070 artifact
  proposals are the literal "Unknown Foreman.xlsx" (69 WRs) and all 1,066 conflicts are `.xlsx`-suffixed names; the
  RPC guard only checks the CURRENT value (`is_sentinel_value(s.frozen_<role>)`), never `q.value`, so `--apply` would
  have frozen that string as a real name. Only the 692 `live` (source 1) proposals across 7 WRs are sound. Second
  scope gap: `lookup_attribution_bulk` nulls `#…` values, so the 935 primary + 10 helper `#NO MATCH` rows are
  invisible to default targeting. Verdict for Task 1: REJECT → fix 12-01 source 3 (+ RPC/script guard on the
  proposed value, fixtures with hash-less filenames) before any apply. Juan's verdict `reject: source-3 filename
  parser defect` recorded; continuation executor wrote `12-06-SUMMARY.md` as `status: halted` (`090c5dc`), STATE +
  ROADMAP show 12-06 HALTED (`417a085`); ledger `[2026-09-03 17:30]`; vault: PostgREST patterns §4, project page,
  current-state, log `[2026-09-03q]`/`[2026-09-03r]`, global lessons-learned. Phase 12 is stuck on the halt: next is
  the verifier → `/gsd:plan-phase 12 --gaps` → `/gsd:execute-phase 12 --gaps-only` → re-run 12-06.
- **2026-09-03 night — 12-06 dispatched, halted at Task 1 (blocking-human):** `/gsd-execute-phase 12` on `feat/phase-12-remediation` (sequential, worktree base-check degraded because HEAD is ahead of `origin/HEAD`); the Sonnet executor read the plan, 12-03-SUMMARY and the runbook, made zero live calls, and returned the Task 1 dry-run checkpoint for Juan. Finding: the plan's step 1 ("full-scope dry-run with no args") does not exist — `scripts/backfill_claim_time_attribution.py` exits 8 unless both `--wr` and `--weeks` are given (runbook § Running the backfill is correct); run scoped dry-runs (known-good WR 19073866 first, then the extended sample, then the remediation set). Owner reminder: the `--apply` probe wants `attribution_snapshot_backup_<today UTC>`; re-create the backup (SQL STEP 1) on the apply day. STATE.md tracking updated by `state.begin-phase`; no SUMMARY yet.
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
- **2026-09-03 evening — PR #388 MERGED** (squash `1f159bc`, 21:02 UTC; master CI Checks, tests + coverage, lint,
  runbook changelog stub `a89e672`, Notion sync all green). 12-06 is the only open Phase 12 plan; next branch
  `feat/phase-12-remediation` off master `e340288`. Second brain updated the same evening: new vault tool page
  `wiki/tools/supabase-mcp.md` (plugin rules + gotchas) and `Supabase PostgREST Integration Patterns` §3
  (REVOKE-before-GRANT, read grants back, dated-backup expiry) hold the durable lessons; dashboard + index current.
- **2026-09-03 afternoon → evening — Phase 12 waves 2–3 DONE, phase gates run, PR #388 (merged, see above):**
  12-02 ✓, 12-04 ✓ (workflow **dispatch-only** by owner re-decision after Opus H1 — the backfill step takes candidates
  only from the sources-1-4 report, which a fresh runner never has, so a cron would be a permanently green no-op; the
  Sunday cron returns in 12-06 with a candidate source), 12-05 ✓ (runbook `ownership-attribution.md`, 4 pages
  rewritten, 20 docs tests, Docusaurus typecheck + build green, ledger `[2026-09-03 13:55]`), 12-03 Tasks 1–3 ✓
  (Juan `approve`d the DDL and **applied it live 2026-09-03 — Task 4 APPROVED**: backup table
  `attribution_snapshot_backup_20260903`, five-tag CHECK confirmed by STEP 2 VERIFY, predicate + RPC created;
  **Greptile on #388 (`27c7ca5`): per-role `backfill_provenance JSONB`; STEP 2 + STEP 4 re-applied live the same
  evening through the Supabase MCP plus a STEP 5 REVOKE (`a227463`) — the RPC had been PUBLIC-executable. Full
  read-only report in `12-03-SUMMARY.md`: STEP 0b 0 dups, live 220,236 vs backup 220,010 (cron drift — 12-06
  re-creates the backup), spot check true/true/false, smoke `skipped_no_row`, 0 backfilled rows, EXECUTE =
  `service_role` only**),
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

1. Owner: paste the `FROZEN MIRROR` header into `AGENTS.md` by hand (text in the PR #385 body; the harness-boundary
   hook denies every ClaudeOS write to that file). PR #387 (wave 1) and #388 are both MERGED (checked 2026-09-04).
   Work paused 2026-09-04 07:28 UTC: handoff in `.planning/HANDOFF.json` + the Phase 12 `.continue-here.md`
   (`/gsd:resume-work`).
2. PR #388 merged (`1f159bc`; 12-03 SQL fully applied and verified live). **Gap closure DONE** on
   `feat/phase-12-remediation` (12-07..12-10 ✓; D-12-C `defer`, D-12-D `substitute-89829163`; RPC STEP 4 + 5 live
   2026-09-04 05:37 UTC; `attribution_snapshot_backup_20260904` = 220,621 rows at 06:07 UTC, valid for the `--apply`
   probe only before 2026-09-05 00:00 UTC = 19:00 CDT 2026-09-04 — re-run STEP 1 if 12-06 slips). **Next: `/clear` →
   `/gsd-execute-phase 12`** runs 12-06 from Task 1 (cheap read-only checks → full-population dry-run whose report must
   show 0 extension-bearing AND 0 hash-tailed proposals → Juan's apply decision → same-UTC-day apply → post-run check);
   restore the Sunday cron only together with a real candidate source. Then `/gsd-verify-work 12` reconciles G-12-3
   and files the code-quality findings as gaps (CR-01 `_FILENAME_HASH_SUFFIX_RE` 6-hex vs 16-hex production tail —
   latent, 0 of 116,906 live artifacts affected; WR-01 `test_own04_documentation.py` newest-ledger-entry pin — do not
   append to `living-ledger.md` until it is fixed) → `phase.complete 12`. Owner security item seen live:
   `anon`/`authenticated` hold full DML grants on `billing_audit.attribution_snapshot` behind RLS — confirm the
   policies deny them before relying on it.
3. Owner-owned Phase 12 steps stay blocking checkpoints: read-only count of NULL/stale-week `row_event`/`row_state`
   rows for the target row_ids before `--apply` (Opus MED, 2026-09-03); confirm live `attribution_snapshot` column names, apply
   `billing_audit/own03_backfill_attribution.sql`, approve the dry-run report, run `--apply`, restore the source-5
   cell-history cron only with a candidate source, attachment replacement.
4. **Phase 14 (Foreman Helper #2) — EXECUTING (wave 1 ✓: 14-01 `11a473d`, 14-02 `34c2f56`, gate green; wave 2 in
   progress sequentially: 14-03 → 14-04 [T1 `blocking-human`: approve additive `row_state` DDL + `HASH_FIELDS`
   inclusion, owner-applied] → 14-05; waves 3–6 follow in the same `/gsd-execute-phase 14` run):** for the later checkpoints review `.planning/phases/14-foreman-helper-2/14-0N-PLAN.md`
   (start with 14-01 tracer, 14-08 O-14-A, 14-09 migration, 14-10 rollout). Decide **O-14-A** (row with BOTH helper completions
   checked; recommended = hold the row with visibility, distinct log reason, counter) and confirm the per-slot identity consequence
   (same person in slot 1 and slot 2 within one WR/week → two files; asked again inside 14-08 T1). Two planner calls to accept or
   overrule at their checkpoints: `HASH_FIELDS` includes the Helper #2 fields (14-04 T1) and the mapping-schema marker is a separate
   nullable `sheet_registry` column (14-07 T1). Waves 1–3 are code + fixtures behind
   `HELPER2_ENABLED='0'`; every DDL apply, workflow edit, and upload stays behind its `blocking-human` checkpoint.

## Open owner items

- **claude-mem capture was degraded 2026-09-02 20:47 → 2026-09-04 19:03 CDT** (upstream thedotmack/claude-mem
  #3857: v13.24.0 ships the 13.23.1 worker bundle → hook kill/respawn loop, 5,767 kills). **Fixed 2026-09-04
  19:03 CDT**: Juan relabeled the four `"13.23.1"` literals in the marketplace `worker-service.cjs` to `"13.24.0"`
  (backup in the session scratchpad); verified worker 13.24.0 stable, 0 mismatch kills after the patch, cloud sync
  drained (hub reachable, pending 0, head = projected = local cursor; no extra env var needed). Treat claude-mem
  summaries from that window as incomplete — `.planning/HANDOFF.json` and these ledgers are the Phase 12 record.
  Caveat: the marketplace file is now git-dirty; if a future plugin auto-update fails to pull, revert that file first.
  Also: the `_20260904` backup window closed at 19:00 CDT — 12-06 Task 3 needs a fresh STEP 1 backup on apply day.
  Details: `docs/CHANGELOG_CONTEXT.md` 2026-09-04 (evening).
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
