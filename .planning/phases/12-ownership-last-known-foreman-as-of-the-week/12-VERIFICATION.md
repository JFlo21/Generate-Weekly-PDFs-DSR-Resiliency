---
phase: 12-ownership-last-known-foreman-as-of-the-week
verified: 2026-09-11T01:25:56Z
status: passed
score: 77/77 must-haves verified
covered_files:
  - ".github/workflows/cell-history-backfill.yml"
  - ".planning/REQUIREMENTS.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-01-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-01-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-02-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-02-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-03-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-03-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-04-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-04-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-05-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-05-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-06-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-06-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-07-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-07-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-08-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-08-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-09-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-09-SUMMARY.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-10-PLAN.md"
  - ".planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-10-SUMMARY.md"
  - "billing_audit/own03_backfill_attribution.sql"
  - "billing_audit/schema.sql"
  - "billing_audit/writer.py"
  - "memory-bank/living-ledger.md"
  - "pipeline/cleanup.py"
  - "pipeline/orchestrate.py"
  - "scripts/backfill_cell_history_attribution.py"
  - "scripts/backfill_claim_time_attribution.py"
  - "tests/test_backfill_cell_history_attribution.py"
  - "tests/test_backfill_claim_time_attribution.py"
  - "tests/test_billing_audit_shadow.py"
  - "tests/test_own03_backfill_sql_contract.py"
  - "tests/test_own04_documentation.py"
  - "tests/test_sentinel_never_a_claimer.py"
  - "website/docs/runbook/ownership-attribution.md"
  - "website/sidebars.ts"
covered_digest: "v1:sha256:6672c05c6902a2fc244430de8ce549e842622d743e9acfcd31712c1aed311c0b"
behavior_unverified: 0 # Every behavior-dependent truth (live apply, post-apply scheduled run) has recorded owner-observed evidence in 12-06-SUMMARY.md / 12-UAT.md; nothing is "present but unexercised"
overrides_applied: 6 # PASSED (override) items included in the score — carried forward from the 2026-09-03 report; each shipped shape was the one Juan approved through 12-03 T3, 12-04 re-decision and the 12-06 apply
overrides:
  - must_have: "The workflow's schedule is a single Sunday 05:00 UTC cron and its workflow_dispatch inputs are bound to env: entries, never interpolated into run: shell text."
    reason: "Owner re-decided 12-04 Task 3 to dispatch-only after Opus H1 (a cron would be a permanently green no-op on the production token). Shipped shape: no schedule: key, workflow_dispatch only, inputs bound to env: (zero ${{ in any run: block; UAT test 2 pass on master merge 1f159bc)."
    accepted_by: "Juan (verbatim 'dispatch-only now (Recommended)', 12-04-SUMMARY § Re-decision); applied in 90d715b"
    accepted_at: "2026-09-03"
  - must_have: "scripts/backfill_cell_history_attribution.py resolves a claimer from the Smartsheet cell history of the role's name column at the timestamp its completion checkbox was checked, and tags every value it proposes with provenance 'operator'."
    reason: "Opus review: 'operator' means human-entered; a cell-history inference is machine-derived. Shipped tag is 'backfill_cell_history'; 'operator' is reserved and unwritten. Resolution mechanism unchanged and tested (test_happy_path_uses_backfill_cell_history_provenance, passing 2026-09-11)."
    accepted_by: "orchestrator (12-04 pre-checkpoint review fix 101489d; vocabulary extended in 12-03 f3b6db3, presented at the 12-03 Task 3 checkpoint Juan approved)"
    accepted_at: "2026-09-03"
  - must_have: "attribution_snapshot.backfill_source carries a CHECK constraint restricted to 'live', 'backfill_artifacts', 'backfill_hash_history' and 'operator'; the file contains no cross-week provenance value and no occurrence of last_known_before_week (D-12-A)."
    reason: "Shipped CHECK and RPC guard accept five values — the four planned plus 'backfill_cell_history'. Still no cross-week value and zero occurrences of last_known_before_week; test_vocabulary_has_exactly_five_tags and test_check_and_guard_lists_match pin the set (passing 2026-09-11)."
    accepted_by: "orchestrator (12-03 addendum 'Vocabulary extension for source 5', f3b6db3); Juan's 12-03 Task 3 'approve' recorded post-addendum; live CHECK applied by Juan (UAT test 1 pass)"
    accepted_at: "2026-09-03"
  - must_have: "The sentinel-superseded delete gate at pipeline/cleanup.py:495-508 is unchanged apart from the predicate it calls."
    reason: "The gate hunk changed by exactly one line on the sibling side: `and not _is_sentinel_identifier(_vw[3])` became `and _is_real_name_identifier(_vw[3])` (98b5ea3, Opus HIGH: safety-narrowing so an unlisted leading-underscore token such as _DATE_EXPECTED can never trigger a deletion). Victim-side predicate and surrounding logic otherwise byte-identical; the gate now lives at cleanup.py:582-597 and is pinned by test_unlisted_underscore_sibling_never_triggers / test_underscore_real_name_sibling_is_neutral."
    accepted_by: "orchestrator (12-02 'Post-execution review fixes' addendum, Opus FIX-FIRST round); UAT test 11 pass"
    accepted_at: "2026-09-03"
  - must_have: "Every cell-history request is self-paced by CELL_HISTORY_BACKFILL_PACE_SEC, never sleeping before the first call of the run, and the run stops fetching when either CELL_HISTORY_BACKFILL_MAX_REQUESTS (default 3000), CELL_HISTORY_BACKFILL_MAX_ROWS or the CELL_HISTORY_BACKFILL_MAX_MINUTES wall-clock deadline is reached; rows past any cap are reported unresolved, never silently dropped."
    reason: "Pacing, first-call-no-sleep and all three caps are implemented and tested. Deviation: a request/wall-clock cap trip DEFERS the not-yet-attempted candidates (summary.cap_reached / summary.candidates_deferred, exit 0) instead of writing per-row 'unresolved' rows; the row cap still writes per-row unresolved. Counted and logged, never silent."
    accepted_by: "orchestrator (12-04 pre-checkpoint review fix 101489d); UAT test 15 pass"
    accepted_at: "2026-09-03"
  - must_have: "A per-row exception is caught, logged as a WARNING, and leaves that row unresolved — one bad row never aborts the run."
    reason: "Opus HIGH 'laundered read failures': treating a Smartsheet/mapping read failure as 'unresolved' would silently produce a wrong report. Shipped: failing candidate marked status='error' (exception TYPE only), further Smartsheet calls stop, report still written with summary.read_failures / summary.aborted, exit 7. Pinned by test_read_failure_aborts_run_with_error_status. Fail-closed direction for billing data."
    accepted_by: "orchestrator (12-04 pre-checkpoint review fix 101489d); UAT test 16 pass"
    accepted_at: "2026-09-03"
re_verification:
  previous_status: human_needed
  previous_score: 49/62
  gaps_closed:
    - "12-03 T4: OWN-03 SQL objects applied live by Juan (UAT test 1 pass; five-value vocabulary confirmed; STEP 4/5 re-applied after the 12-09 extension guard, 12-09-SUMMARY live read-back reviewed by Juan)"
    - "12-06 T1: live dry-run reviewed — first run REJECTED 2026-09-03 (G-12-3 source-3 parser defect), closed by 12-07..12-10, re-run 2026-09-05 APPROVED verbatim 'I approve' (1,758 rows / 30 WRs / 76 pairs, 0 conflicts)"
    - "12-06 T2: apply-full chosen in writing (2026-09-05)"
    - "12-06 T3: --apply --i-approved-this executed 2026-09-05 03:43Z after same-UTC-day backup attribution_snapshot_backup_20260905 (221,276 rows): updated 1,758 / skipped_real_name 0 / skipped_no_row 0 / errors 0; 219,518 untouched rows 0 differences vs backup"
    - "12-06 T4: post-apply scheduled run 33974128574 observed (seven read-only observations, all pass); Juan 'Approved' 2026-09-10; D-12-E adopts WR 89746993 as the SC3 sample; three backup tables dropped after the live table (224,371 rows / 1,758 backfilled) was verified"
    - "Docusaurus build backstop (12-05 truth 12): UAT test 19 pass — build SUCCESS with no broken cross-links, recorded by Juan"
    - "Override confirmation (previous human item 7): the six shipped shapes were the ones carried through the owner-approved 12-03 T3 / 12-04 re-decision / 12-06 apply; carried forward as accepted"
  gaps_remaining: []
  regressions: []
advisory: # Known, non-blocking findings — filed with status and owner in § Gaps Summary; none makes a must-have FAILED
  - finding: "sentinel_claimers_ignored is not observable in production output (counter exists in writer.py:206/1598 and is merged into the in-process run_summary at orchestrate.py:5425, but no run_summary.json artifact is uploaded; only artifact_manifest.json)"
    category: other
    reason: "Observability only; SC3 was verified by attachment inventory instead. Resolve by uploading run_summary.json or surfacing the counter in the step summary."
    evidence_status: "12-06-SUMMARY Task 4 item 1; grep of pipeline/ and .github/workflows/ 2026-09-11"
  - finding: "backfill_run_id = '' on local operator runs (_compute_run_id() returns '' without GITHUB_RUN_ID, script lines 500-509); the 1,758 live-backfilled rows carry backfill_source but an empty run id"
    category: other
    reason: "Provenance is weaker than designed for locally driven applies; not a data-integrity defect (rows still distinguishable by backfill_source/backfill_provenance). Resolve with a local fallback id (e.g. 'local-<utc timestamp>')."
    evidence_status: "12-06-SUMMARY Task 3 note; code read 2026-09-11"
  - finding: "The sentinel-superseded gate (cleanup.py:582-622) deletes the stale _User_Unknown_Foreman attachment but leaves the Unknown_Foreman pipeline_memory.group_state row in place; no delete path for group_state exists in pipeline/ or pipeline_memory/"
    category: architectural
    reason: "Hygiene / stale-memory residue; run 33974128574 showed no placeholder churn on the 76 backfilled pairs, so the goal holds. Resolve by retiring the superseded group_state row in the same gate (or a follow-up sweep)."
    evidence_status: "grep pipeline/ pipeline_memory/ 2026-09-11 (0 matches for a group_state delete)"
  - finding: "CR-01 (12-REVIEW): _FILENAME_HASH_SUFFIX_RE = _[0-9a-fA-F]{6}\\.xlsx$ (script line 161) encodes a 6-hex fixture tail while production embeds a 16-hex data_hash (change_detection.py:381/502); for that shape the extension strip could leave the hash glued to the name"
    category: security
    reason: "Latent: 0 live filenames affected while SUPABASE_HASH_STORE_AUTHORITATIVE=1 (hash-less shape), the live apply is complete and the RPC only ever overwrites a sentinel. Must be fixed before any future --apply against hash-bearing filenames (derive width from change_detection.py, accept 6 for legacy fixtures)."
    evidence_status: "12-REVIEW.md CR-01; code read 2026-09-11; not fixed in this phase by design"
  - finding: "WR-01 (12-REVIEW): tests/test_own04_documentation.py::_newest_ledger_entry pins D-12-C / D-12-D to the NEWEST '## [' ledger heading (lines 95-100, 179-186); it passes today only because [2026-09-04 10:05] is still the last heading"
    category: other
    reason: "Guaranteed to fail on the next mandated ledger append (CLAUDE.md requires one per architectural change). Resolve by searching all headings or a specific dated heading."
    evidence_status: "grep of memory-bank/living-ledger.md headings 2026-09-11; not fixed in this phase by design"
  - finding: "WR-09 (12-REVIEW): website/docs/runbook/ownership-attribution.md lines 247 and 276 showed, at verification time, `--wr 19073866 --weeks 082425,083125,091425,092125` as the copy-pasteable dry-run/apply command while the same page (214-219) says that WR has zero rows and D-12-E names WR 89746993"
    category: other
    reason: "Documentation drift; the command is harmless (dry-run default, zero rows) but misleads an operator. RESOLVED in the same docs PR (#404): both example commands now read --wr 89746993 --weeks 082425,083125,090725,091425."
    evidence_status: "grep of the runbook 2026-09-11; fixed in PR #404 — not an open follow-up"
---

# Phase 12: Ownership — last known foreman as of the week — Verification Report

**Phase Goal:** Each (WR, week) file is named for — and partitioned by — the foreman/helper/VAC who owned the job at that time, derived from observed history, never from a sentinel. Repairs the 2026-08-24 `_User_Unknown_Foreman` defect and the 93 affected WRs.
**Verified:** 2026-09-11T01:25:56Z (branch `fix/phase-14-cr01-cr02-wr03`, working tree; `git diff --stat` on `billing_audit/writer.py` and `tests/test_billing_audit_shadow.py` is empty, so the verified code equals HEAD for those files)
**Status:** passed
**Re-verification:** Yes — full regeneration after gap closure (previous report 2026-09-03, `human_needed`, 49/62; it predated plans 12-07..12-10 and the 12-06 Tasks 1-4 records)

## Verification scope and method

- All ten plans complete. 12-06 Tasks 1-3 landed 2026-09-05 (live apply, 1,758 rows / 30 WRs / 76 pairs), Task 4 observed on scheduled run 33974128574 and approved by Juan 2026-09-10 (D-12-E). Gap G-12-3 (source-3 hash-less filename parser) closed by 12-07..12-10 on 2026-09-04.
- Codebase checks: grep/sed reads of the artifacts listed in `covered_files`; one pytest run with `SMARTSHEET_API_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_KEY`, `SENTRY_DSN` blanked: `tests/test_backfill_claim_time_attribution.py tests/test_own03_backfill_sql_contract.py tests/test_own04_documentation.py tests/test_backfill_cell_history_attribution.py tests/test_sentinel_never_a_claimer.py tests/test_billing_audit_shadow.py` → **403 passed, 162 subtests passed in 8.02s, exit 0** (`-k sentinel` on the shadow file enumerates 5 tests). No Supabase, Smartsheet, `.env` or GitHub access from this verifier.
- Live facts cited without re-checking (orchestrator-verified 2026-09-10, read-only): `billing_audit.attribution_snapshot` 224,371 rows / 1,758 with `backfill_provenance`; 0 `attribution_snapshot_backup_%` tables remain; on `TARGET_SHEET_ID` the 76 backfilled pairs carry real-name attachments and 0 `_User_Unknown_Foreman` placeholders; 152 placeholders remain sheet-wide on non-backfilled pairs (the 4,071 evidence-less rows, routed to source 5).
- SUMMARY addenda were treated as superseding plan text only where an explicit override is recorded in the frontmatter (six, carried forward). `gsd-tools query verify.artifacts` / `verify.key-links` still return 0 items for these plans (flat-string artifact lists), so artifact/link checks are manual.
- Docusaurus build was not run here (writes `website/build`); the backstop is covered by UAT test 19 (owner-recorded pass).

## Goal Achievement

### Roadmap Success Criteria (the contract)

| # | Success criterion | Status | Evidence |
| --- | --- | --- | --- |
| SC1 | `resolve_claimer`/`freeze_row` never store or honor `Unknown Foreman` / `#…` as a claimer (TDD in `tests/test_billing_audit_shadow.py`) | ✓ VERIFIED | `writer.py:120` `is_sentinel_claimer` (exact family); `freeze_row` nulls every named sentinel per role (889-909, defers an all-sentinel tuple, `sentinel_freezes_deferred`); `resolve_claimer` 1592-1598 treats a frozen sentinel as no-history (`sentinel_claimers_ignored`). 5 sentinel tests in the shadow file + `tests/test_sentinel_never_a_claimer.py` pass. Behavioral truth with behavioral evidence. |
| SC2 | Dry-run backfill report lists, per affected (WR, week), the proposed owner and its source; Juan approves before the live remediation | ✓ VERIFIED | Report shape (wr, week_ending, role, proposed_value, source, name_fidelity, status) pinned by `tests/test_backfill_claim_time_attribution.py`; live: first dry-run REJECTED 2026-09-03 (G-12-3), re-run 2026-09-05 APPROVED verbatim `I approve` (1,758 / 30 WRs / 76 pairs, 0 conflicts) before Task 2/3 — 12-06-SUMMARY, UAT test 3 pass. |
| SC3 | WR 89746993 WE 082425/083125/090725/091425 regenerate under `_User_<real resolved name>` (114 backfilled rows; person not recorded — T-12-28) and the `_User_Unknown_Foreman` counterpart is removed by the sentinel-superseded gate; no placeholder churn remains on the backfilled pairs in the scheduled run (D-12-D, D-12-E) | ✓ VERIFIED (owner-observed) | Code: gate at `cleanup.py:582-622` (victim `_is_sentinel_identifier`, sibling `_is_real_name_identifier` + attached-now check, Sentry breadcrumb `sentinel_superseded`), tests pass. Live: run 33974128574 — WR 89746993 swap observed, four spot-check WRs (89841789, 89848991, 89877351, 89954686) regenerated under real names in the same run with the Unknown_Foreman file removed seconds later, and a fifth (90851321) was already live under its real name from an earlier run and untouched; 76 pairs / 0 placeholders on the target sheet; Juan `Approved` 2026-09-10 (12-06-SUMMARY Task 4; UAT test 34 pass). |
| SC4 | Living Ledger + runbook document the amended Foundation A contract | ✓ VERIFIED | `memory-bank/living-ledger.md:9182` `[2026-09-03 13:55]` entry (D-12-A, D-12-B, amended Foundation A, CR-01, WR-01) plus `:9289` `[2026-09-04 10:05]` (G-12-3, D-12-C/D); `website/docs/runbook/ownership-attribution.md:101` § "The amended Foundation A contract" (first-write-wins holds for a real name only), D-12-A..E noted (84, 140, 194, 213-219); `website/sidebars.ts:23`; `tests/test_own04_documentation.py` passes. |

### Plan-level truths (regression check of the 2026-09-03 must-haves + the four gap-closure plans)

Status key: ✓ VERIFIED · ✓ (override) PASSED via recorded override · ✓ (owner) live step with recorded owner evidence.

**12-01 — OWN-03 claim-time backfill script (10)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Dry-run for the known-good sample proposes a real name via `backfill_hash_history`, zero writes | ✓ VERIFIED | `test_resolves_all_four_weeks_via_source_4` passes; live sample re-based to WR 89746993 by D-12-E (WR 19073866 has zero rows in any store). |
| 2 | Ladder 1 → 2 → 3 → 4 → sentinel, week-scoped, no cross-week rung | ✓ VERIFIED | `_SOURCE_TAGS` 198-199; `_in_target_week`; UAT test 5 pass. |
| 3 | Two distinct real names in source 3/4 → `conflict`, empty proposed_value | ✓ VERIFIED | `_resolve_single_name`; UAT test 6 pass. |
| 4 | No source names the row → `unresolved` + reason, exit 0 | ✓ VERIFIED | `test_zero_candidates_across_all_sources_is_unresolved`. |
| 5 | Sentinel classification only via `billing_audit.writer.is_sentinel_claimer` | ✓ VERIFIED | Script imports `is_sentinel_claimer` (1304); no second sanitizer. |
| 6 | Deterministic precedence / tie-breaks / sorted report | ✓ VERIFIED | Sorted by (wr, week_ending, row_id); tests pass. |
| 7 | `name_fidelity` desanitized for filename/identifier values, exact for observed names | ✓ VERIFIED | Sources 1/2 `exact`, 3/4 `desanitized`; tests pass. |
| 8 | `--apply` never includes a row whose current frozen value is a real name | ✓ VERIFIED | `_build_apply_payload` 1262-1310 gates on current AND proposed value; live: skipped_real_name 0 and 219,518 untouched rows 0 diffs. |
| 9 | `--dry-run` default; `--apply` refused without `--i-approved-this` (exit 4) and a readable dated backup (exit 3) | ✓ VERIFIED | 46-50, 1607, 1724-1729; UAT test 7 pass. |
| 10 | Report .json/.csv git-ignored | ✓ VERIFIED | `.gitignore` `generated_docs/own03_*`; UAT test 8 pass. |

**12-02 — OWN-02 residuals CR-01 / WR-01 (7)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1-4 | `_is_sentinel_identifier` allowlist semantics, fail-safe direction, shared normalization | ✓ VERIFIED | `cleanup.py:116-195`; UAT test 9 pass; tests pass. |
| 5-6 | Function-local `AttachmentParentType` import with string fallback | ✓ VERIFIED | UAT test 10 pass. |
| 7 | Delete gate unchanged apart from the predicate | ✓ (override) | Override #4. |

**12-03 — owner-applied SQL (10)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1-6, 8-9 | Owner-applied file, sentinel-only WHERE (`is_sentinel_value` 385/403/421), one result row per input, typed recordset, three static UPDATEs, `SET search_path = ''`, STEP 0 query, schema.sql contract block | ✓ VERIFIED | `own03_backfill_attribution.sql`; `tests/test_own03_backfill_sql_contract.py` passes; UAT tests 12-13 pass. |
| 7 | CHECK vocabulary | ✓ (override) | Override #3 (five values, no cross-week value). |
| 10 | Backup table readable by service_role after apply | ✓ (owner) | UAT test 1 pass; 12-10 T2 (`_20260904`) and 12-06 T3 (`_20260905`, 221,276 rows) confirmed; all three backups dropped 2026-09-10 after verification. |

**12-04 — source 5 cell-history script + workflow (10)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1, 3, 4, 8 | Provenance tag; caps/pacing; per-row failure; workflow schedule | ✓ (override) | Overrides #2, #5, #6, #1. |
| 2, 5, 6, 7, 9, 10 | Candidate set from the sources 1-4 report; `--check-backlog` bounded read; no production module calls `get_cell_history` or reads `CELL_HISTORY_BACKFILL_*`; own concurrency group; skip when backlog 0; never more than MAX_REQUESTS calls | ✓ VERIFIED | `tests/test_backfill_cell_history_attribution.py` passes; UAT tests 14-17 pass; workflow static check (UAT test 2). |

**12-05 — OWN-04 documentation (12)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1-11 | Runbook ladder as implemented, D-12-A/B, Foundation A, do-not-run warning, owning component per flow, rollback, sidebar, env vars, dated ledger entry at the bottom, no real claimer name | ✓ VERIFIED | Runbook + sidebar + ledger as cited under SC4; `tests/test_own04_documentation.py` passes; UAT tests 18, 20, 21 pass. |
| 12 | Docusaurus build with no broken cross-links | ✓ (owner) | UAT test 19 pass (build SUCCESS recorded). |

**12-06 — live rollout (9)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Live dry-run resolves the sample | ✓ (owner) | Re-run 2026-09-05 exit 0, 1,758 proposed / 0 conflicts; sample re-based by D-12-E. |
| 2 | Juan approves the report before any --apply, recorded | ✓ (owner) | `I approve` 2026-09-05, 12-06-SUMMARY. |
| 3 | `public.artifacts` cross-check agrees | ✓ (owner) | 12-06 Task 1 re-run: all G-12-3 / CR-01 guards 0. |
| 4 | --apply reports updated / skipped_real_name / skipped_no_row | ✓ (owner) | 1,758 / 0 / 0, errors 0. |
| 5 | Zero real-name rows modified (backup comparison) | ✓ (owner) | 219,518 untouched rows, 0 differences vs `_20260905`; provenance total 1,758 = updated. |
| 6 | Post-apply run regenerates under real names, stale attachments removed, `sentinel_claimers_ignored` drops | ✓ (owner, partial on the counter clause) | Regeneration + removal observed on run 33974128574; the counter is not observable in production output → advisory #1. |
| 7 | No PPP attachment deleted | ✓ (owner) | 12-06 Task 4 seven observations all pass. |
| 8 | No real claimer name committed | ✓ VERIFIED | Report files git-ignored; 12-10 T3 report resolved outside the working tree. |
| 9 | Post-apply run inside TIME_BUDGET_MINUTES | ✓ (owner) | 12-06 Task 4 (74 generated / 74 uploaded within budget). |

**12-07 — G-12-3 source-3 fix (5)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| D1 | Live hash-less sentinel filename never yields a source-3 proposal | ✓ VERIFIED | `_FILENAME_DOC_EXTENSION_RE` (171) stripped before the sentinel check (1006-1014); tests pass; UAT 22. |
| D2 | Hash-less real-name filename resolves to the desanitized name | ✓ VERIFIED | Tests pass; UAT 23. |
| D3 | Hash-suffixed shape unchanged | ✓ VERIFIED | Branch on `_FILENAME_HASH_SUFFIX_RE` (1006); UAT 24. |
| D4 | Both shapes exercised by every source-3 case | ✓ VERIFIED | Parameterized fixtures (d4e05eb); UAT 25. |
| D5 | `_build_apply_payload` refuses a sentinel or extension-bearing proposed_value | ✓ VERIFIED | Line 1304; UAT 27. |

**12-08 — owner scope decisions (3)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | D-12-C recorded as option `defer` (945 #NO MATCH rows out of scope) | ✓ VERIFIED | ROADMAP, runbook 194, ledger 9289; `test_own04_documentation.py` reads it back. |
| 2 | D-12-D recorded (since superseded by D-12-E, 2026-09-10) | ✓ VERIFIED | ROADMAP + runbook 213-219 record both. |
| 3 | 12-10 invocation posture: no `--include-blank-roles` | ✓ VERIFIED | 12-10 T3 and 12-06 T3 scopes recorded without the flag. |

**12-09 — SQL extension guard (3)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| D1 | STEP 4 raises on an extension-bearing proposed value | ✓ VERIFIED | SQL 332-344; contract test passes; UAT 28. |
| D2 | schema.sql documents the two-ground refusal | ✓ VERIFIED | UAT 29. |
| D3 | Amended RPC deployed live | ✓ (owner) | 12-09-SUMMARY: STEP 4+5 re-applied, four live read-back answers (apply timestamp, EXECUTE holders) reviewed by Juan; UAT 26 marked pass at the consolidated owner checkpoint (12-UAT.md 34/34), backed by the recorded review and the successful 12-06 apply through the amended RPC. |

**12-10 — review, backup, dry-run, re-entry (4)**

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| D1 | Independent production-risk verdict on the 12-07 + 12-09 delta | ✓ VERIFIED | Verdict pass, 8-point rubric, 2 LOW; UAT 33 pass. |
| D2 | Same-UTC-day backup `_20260904` existed and was readable | ✓ (owner) | 12-10-SUMMARY T2 (superseded by `_20260905` for the actual apply). |
| D3 | Scoped dry-run: 0 extension-bearing / 0 sentinel proposals (was 235/235) | ✓ (owner) | 12-10-SUMMARY T3, WR 89732091 x 7 weeks. |
| D4 | 12-06 re-entrant from Task 1, then completed | ✓ VERIFIED | ROADMAP plan list; commits 7ce962a, 9fab1ab … and the closure squash 9ba7eb7 (PR #404). |

**Score:** 77/77 truths verified (4 roadmap SCs + 73 plan-level; 6 by recorded override, 13 by recorded owner evidence; 0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `billing_audit/writer.py` | sentinel-aware `freeze_row` / `resolve_claimer` + counters | ✓ VERIFIED | 120-142, 202-207, 778-909, 1514-1598; wired into `pipeline/orchestrate.py` (`get_counters()` merged at 5425). |
| `scripts/backfill_claim_time_attribution.py` | sources 1-4, dry-run/apply CLI, guards | ✓ VERIFIED | 1,7xx lines; exercised by 12-06 live apply. |
| `scripts/backfill_cell_history_attribution.py` + `.github/workflows/cell-history-backfill.yml` | source 5, isolated dispatch-only job | ✓ VERIFIED | Tests pass; workflow static check (UAT 2). Not yet run live (152 placeholders remain on non-backfilled pairs — future source-5 work). |
| `billing_audit/own03_backfill_attribution.sql` / `schema.sql` | owner-applied RPC + provenance columns + extension guard | ✓ VERIFIED | Applied live (UAT 1, 12-09). |
| `pipeline/cleanup.py` | sentinel-superseded gate with CR-01 fail-safe | ✓ VERIFIED | 116-195, 582-622; observed acting on run 33974128574. |
| `website/docs/runbook/ownership-attribution.md`, `website/sidebars.ts`, `memory-bank/living-ledger.md` | OWN-04 docs | ✓ VERIFIED | See SC4; WR-09 stale example command (advisory #6) fixed in PR #404. |
| Six test files | TDD coverage | ✓ VERIFIED | 403 passed. |

### Key Link Verification

| From | To | Via | Status |
| --- | --- | --- | --- |
| `pipeline/orchestrate.py` | `billing_audit/writer.py` `resolve_claimer` / `freeze_row` / `get_counters` | import + call (5407-5425) | WIRED |
| `scripts/backfill_claim_time_attribution.py` | `billing_audit.backfill_attribution` RPC | `--apply --i-approved-this` after backup probe (1724-1729) | WIRED (live apply 2026-09-05) |
| `scripts/backfill_claim_time_attribution.py` | `billing_audit.writer.is_sentinel_claimer` | import, used in `_build_apply_payload` (1304) | WIRED |
| `pipeline/cleanup.py` gate | `pipeline_memory.group_state` | none — the gate never retires the superseded row | NOT WIRED by design gap (advisory #3, non-blocking) |
| `website/sidebars.ts` | `runbook/ownership-attribution` | line 23 | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Real data | Status |
| --- | --- | --- | --- | --- |
| backfill report | proposed_value / source | `row_event`/`row_state`, same-row roles, `public.artifacts`, `group_content_hash` + `group_state` (Supabase) | Yes (live: 1,758 rows from 24 real names) | ✓ FLOWING |
| `resolve_claimer` | frozen name | `billing_audit.attribution_snapshot` (post-backfill real names) | Yes (run 33974128574 regenerated under real names) | ✓ FLOWING |
| cleanup gate | sibling identity | `valid_wr_weeks` + `_row_attached_idents` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase test files (single run, credentials blanked) | `python -m pytest -q <6 files>` | 403 passed, 162 subtests, 8.02s | ✓ PASS |
| SC1 TDD exists in the shadow file | `pytest --collect-only tests/test_billing_audit_shadow.py -k sentinel` | 5/231 collected | ✓ PASS |
| Production hash width vs script regex | grep | `hexdigest()[:16]` vs `{6}` | ✓ confirms CR-01 as latent (advisory #4) |
| `group_state` retirement path | grep pipeline/ pipeline_memory/ | 0 matches | ✓ confirms advisory #3 |
| Docusaurus build | not run (writes `website/build`) | UAT test 19 pass | ? SKIP → owner evidence |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes are declared by the plans or present in the repository. SKIPPED.

### Requirements Coverage

| Requirement | Source plans | Status | Evidence |
| --- | --- | --- | --- |
| OWN-01 | 12-03, 12-05 (D-12-A) | ✓ SATISFIED as re-scoped | No `wr_week_ownership` table (deferred to Phase 13 per D-12-A); ladder observed_in_week → backfill_artifacts → backfill_hash_history → backfill_cell_history → sentinel with provenance columns. REQUIREMENTS.md OWN-01 re-worded to the shipped ladder and marked Complete with the D-12-A note (PR #404). |
| OWN-02 | 12-02, 12-06 | ✓ SATISFIED | SC1 + SC3. Tracker marked Complete (PR #404). |
| OWN-03 | 12-01, 12-03, 12-04, 12-06..12-10 | ✓ SATISFIED (scope as decided) | 1,758 rows / 30 WRs / 76 pairs remediated and attachments replaced; 945 #NO MATCH rows deferred (D-12-C); 4,071 evidence-less rows routed to source 5 (152 placeholders remain sheet-wide). REQUIREMENTS.md OWN-03 re-scoped and marked Complete with the D-12-C / D-12-E note (PR #404). |
| OWN-04 | 12-05, 12-08 | ✓ SATISFIED | SC4. Tracker marked Complete (PR #404). |

No orphaned requirement IDs: REQUIREMENTS.md maps exactly OWN-01..04 to Phase 12.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `scripts/backfill_claim_time_attribution.py` | 161 | 6-hex hash-suffix regex vs 16-hex production hash (CR-01) | ⚠️ Warning (latent) | Advisory #4 |
| `scripts/backfill_claim_time_attribution.py` | 500-509 | `_compute_run_id()` returns `''` locally | ⚠️ Warning | Advisory #2 |
| `tests/test_own04_documentation.py` | 95-100, 179-186 | newest-ledger-heading pin (WR-01) | ⚠️ Warning | Advisory #5 |
| `website/docs/runbook/ownership-attribution.md` | 247, 276 | stale sample WR in example command (WR-09) | ℹ️ Info | Advisory #6 — fixed in PR #404 |
| `pipeline/cleanup.py` | 582-622 | gate leaves the superseded `group_state` row | ⚠️ Warning | Advisory #3 |

No `TBD` / `FIXME` / `XXX` markers found in the phase-modified files.

### Prohibitions (judgment-tier, ADR-550 — recorded, not silently passed)

| # | Prohibition | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | Never store or honor a sentinel as a claimer | not violated | SC1 code + tests; SQL WHERE `is_sentinel_value`. |
| 2 | Never overwrite a real frozen name | not violated (live-proven) | 219,518 untouched rows, 0 diffs vs backup; skipped_real_name 0. |
| 3 | Never infer ownership across weeks | not violated | No cross-week rung; `_in_target_week`. |
| 4 | Never apply Supabase DDL/RPC from script or pipeline code | not violated | Owner-applied via SQL editor / connector at Juan's instruction (12-09, 12-10 recorded deviations). |
| 5 | Never commit claimer PII | not violated | Reports git-ignored; grep of the lines added by PR #404 shows only fictional names and the `_User_<real resolved name>` alias — the D-12-E sample person is redacted per T-12-28 (WR, weeks and counts only). |
| 6 | Never read current Smartsheet row state as a backfill source | not violated | Script has no `smartsheet` import. |
| 7 | Never delete a real claimer's attachment | not violated (live-observed) | Task 4: no real-name attachment lost, no PPP deleted. |
| 8-12 | Gate hunk unchanged; no second sentinel matcher; no EXECUTE to anon/authenticated; no `EXECUTE format`; no cross-week CHECK value | not violated / accepted override #4 | Contract tests pass. |

These were resolved at the end-of-phase human checkpoint (12-UAT.md, 34 tests) rather than by this verifier alone.

### Human Verification Required

None outstanding. Every previously pending owner step (12-03 T4, 12-06 T1-T4, Docusaurus build, override confirmation) now carries recorded evidence in 12-06-SUMMARY.md / 12-UAT.md. UAT tests 26, 30, 31, 32 were marked `pass` at the consolidated owner checkpoint (12-UAT.md 34/34).

### Gaps Summary

The phase goal is achieved: sentinels are never claimers (SC1), the dry-run report was approved before the apply (SC2), the backfilled pairs regenerate under real names with the placeholder counterpart removed and zero churn on the scheduled run (SC3, D-12-E), and the amended Foundation A contract is documented (SC4). Six non-blocking items were filed (all listed in `advisory:` above); five remain open as owner follow-ups and #6 (WR-09) was fixed in the same docs PR (#404):

| # | Item | Status | Owner |
| --- | --- | --- | --- |
| 1 | `sentinel_claimers_ignored` not emitted in production output (counter exists and is merged into the in-process run summary; no run_summary.json artifact) | open — observability | Phase 13 / next pipeline PR |
| 2 | `backfill_run_id = ''` on local operator runs | open — provenance | next backfill-script PR |
| 3 | Sentinel-superseded gate leaves the stale `Unknown_Foreman` `group_state` row | open — hygiene | Phase 13 (memory) or cleanup follow-up |
| 4 | CR-01 `_FILENAME_HASH_SUFFIX_RE` 6-hex vs 16-hex (latent, 0 live filenames affected while `SUPABASE_HASH_STORE_AUTHORITATIVE=1`) | open — must fix before any future `--apply` | backfill-script PR (from 12-REVIEW) |
| 5 | WR-01 newest-`## [` ledger-heading pin in `tests/test_own04_documentation.py` | open — will break on the next ledger append | test follow-up (from 12-REVIEW) |
| 6 | WR-09 runbook example named WR 19073866 | resolved — fixed in PR #404 (both example commands now name WR 89746993) | none |

Tracker: `.planning/REQUIREMENTS.md` OWN-01..04 are marked Complete with the D-12-A / D-12-C / D-12-E scope notes (PR #404).

---

_Verified: 2026-09-11T01:25:56Z_
_Verifier: Claude (gsd-verifier)_
