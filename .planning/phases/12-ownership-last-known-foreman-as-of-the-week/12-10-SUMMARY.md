---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 10
subsystem: billing-attribution-backfill
tags: [own-02, own-03, gap-closure, g-12-3, independent-review, backup, dry-run, re-entry]

# Dependency graph
requires:
  - phase: 12-ownership-last-known-foreman-as-of-the-week (12-07)
    provides: source-3 extension-stripping parser fix and the `_build_apply_payload` proposed-value guard
  - phase: 12-ownership-last-known-foreman-as-of-the-week (12-08)
    provides: D-12-C (`#NO MATCH` scope = defer) and D-12-D (SC3 sample = WR 89829163 / backfill_artifacts) pinning this plan's invocation posture
  - phase: 12-ownership-last-known-foreman-as-of-the-week (12-09)
    provides: live server-side extension guard deployed in the `backfill_attribution` RPC
provides:
  - "Independent production-risk review verdict: pass, 8-point rubric, zero fix round (Task 1)"
  - "Same-UTC-day backup table billing_audit.attribution_snapshot_backup_20260904, service_role-readable, prior-day table preserved (Task 2)"
  - "Zero-defect scoped dry-run evidence on WR 89732091 x 7 weeks: 0 extension-bearing / 0 sentinel proposals, against 235 of 235 pre-fix (Task 3)"
  - "12-06 declared formally re-entrant from its own Task 1"
affects: [12-06]

# Actuals (#2632)
actuals:
  tokens: 6400
  tasks: 3
  commits: 1

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Independent fresh-context reviewer dispatched with diff-only scope + a fixed rubric (no authoring rationale) as the gate before a rejected production write path reopens"
    - "Verification dry-run report resolved and deleted inside the task, outside the repository working tree, so PII never has a chance to be committed even accidentally"

key-files:
  created:
    - .planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-10-SUMMARY.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Task 1 independent review verdict: pass — 2 LOW, non-blocking findings (source-4 unfiltered extensions on non-filename identifiers; the extension guard strictly narrows an already-identical extraction path), 6 OK; zero fix round required."
  - "Owner-authorized deviation (Task 2): at Juan's explicit choice, the orchestrating main session ran STEP 1 (dated backup CREATE TABLE + GRANT) via the Supabase MCP rather than Juan running it by hand in the SQL editor — mirrors the same owner-directed deviation pattern already recorded in 12-09 for STEP 4/5."
  - "Task 3 zero-defect dry-run confirmed: 235 of 235 extension-bearing proposals (pre-fix) -> 0 of 0 (post-fix) on the identical WR 89732091 x 7-week scope; the zero is vacuous-but-correct — none of sources 1-4 hold a legitimate name for these rows, which is the correct shape for a filename that encodes 'no foreman recorded'."
  - "Juan's resume signal `re-enter-12-06` (2026-09-04) confirms all five re-entry conditions and hands control back to 12-06's own Task 1."
  - "attribution_snapshot_backup_20260904 is valid for an --apply precondition only through 2026-09-04 23:59 UTC; if the 12-06 apply slips past 2026-09-05 00:00 UTC, STEP 1 must be re-run against that new UTC day before --apply can succeed."

requirements-completed: [OWN-02, OWN-03]

coverage:
  - id: D1
    description: "An independent reviewer with no authoring context judged the combined 12-07 + 12-09 delta against an 8-point production-risk rubric and returned pass, with file:line evidence for every finding and zero fix rounds needed."
    requirement: OWN-03
    verification:
      - kind: other
        ref: "Opus production-risk-reviewer verdict, dispatched by the execute-phase orchestrator over `git diff 2c794a9..786329b` scoped to scripts/backfill_claim_time_attribution.py, tests/test_backfill_claim_time_attribution.py, billing_audit/own03_backfill_attribution.sql, billing_audit/schema.sql"
        status: pass
      - kind: unit
        ref: "python -m pytest tests/ -q"
        status: pass
      - kind: other
        ref: "python -m py_compile scripts/backfill_claim_time_attribution.py"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh"
        status: pass
    human_judgment: false
  - id: D2
    description: "A backup table named attribution_snapshot_backup_20260904 exists, is service_role-readable, and its exact name is recorded so the --apply precondition probe finds it."
    requirement: OWN-03
    verification:
      - kind: manual_procedural
        ref: "Juan's approval of the Task 2 human-verify checklist (STEP 1 run in the Supabase SQL editor / via MCP at his direction, both CREATE and GRANT substituted, VERIFY query listing both dated tables, matching row counts)"
        status: pass
    human_judgment: true
    rationale: "Confirming a live production DDL apply and its resulting table state is an owner-verified fact about real Supabase infrastructure; the task's own <verify> block requires a <human-check> and explicitly prohibits the executor from running or self-verifying DDL."
  - id: D3
    description: "A scoped, read-only dry-run against live data exits 0 with zero extension-bearing proposals and zero sentinel-classified proposals on the exact scope that previously produced 235 of 235 placeholder proposals."
    requirement: OWN-03
    verification:
      - kind: other
        ref: "python -c '...' extension_bearing_proposals check against ${TMPDIR:-/tmp}/own03_verify/own03_backfill_report.json (deleted after counting)"
        status: pass
      - kind: other
        ref: "git status --porcelain"
        status: pass
    human_judgment: true
    rationale: "Task 3's <verify> block requires Juan to review the before/after counts and explicitly confirm the source-3 defect is closed via the `re-enter-12-06` resume signal; this is a production-risk judgment about live data, not a fully automatable pass/fail."
  - id: D4
    description: "12-06 is declared re-entrant from its Task 1 with the invocation posture pinned by 12-08's decisions, and the re-entry conditions are written down."
    verification: []
    human_judgment: true
    rationale: "The re-entry declaration is a governance statement confirmed by Juan's explicit `re-enter-12-06` resume signal, not a testable code artifact."

# Metrics
duration: ~15min (continuation session — Tasks 1-3 were executed 2026-09-04 by the orchestrator and
  prior continuation agents; this session's work was recording Task 3's counts-only evidence,
  authoring this SUMMARY, and closing state/roadmap/requirements tracking)
completed: 2026-09-04
status: complete
---

# Phase 12 Plan 10: Independent review, fresh backup, zero-defect dry-run, and 12-06 re-entry Summary

**An independent Opus reviewer with no authoring context returned `pass` on the combined 12-07 + 12-09 fix, Juan created a fresh same-UTC-day backup table via the Supabase MCP at his direction, a scoped live dry-run showed the source-3 placeholder defect had gone from 235-of-235 to 0-of-0 extension-bearing proposals, and Juan replied `re-enter-12-06` — formally reopening plan 12-06 at its own Task 1.**

## Performance

- **Duration:** ~15 min for this continuation (Tasks 1-3 executed 2026-09-04 by the orchestrator
  and prior continuation agents; this session recorded Task 3's evidence and closed out the plan)
- **Started:** 2026-09-04 (Task 1 dispatch, ~05:45 UTC)
- **Completed:** 2026-09-04
- **Tasks:** 3/3 completed
- **Files modified:** 4 (this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md; no production code changed by this plan)

## Accomplishments

- Independent production-risk review of the combined 12-07 + 12-09 delta returned `pass` with
  file:line evidence for all 8 rubric findings, zero fix rounds required.
- A fresh same-UTC-day backup table (`attribution_snapshot_backup_20260904`) exists, is
  `service_role`-readable, and its exact name and row counts are recorded, restoring the
  `--apply` precondition's satisfiability.
- A scoped, read-only verification dry-run against live data on the exact pre-fix reproduction
  scope (WR 89732091, 7 weeks) shows the source-3 placeholder defect is closed: 235 of 235
  extension-bearing proposals before the fix, 0 of 0 after.
- Plan 12-06 is formally declared re-entrant from its own Task 1, with its Tasks 2-4 still gated
  behind Juan's APPROVE / APPROVE WITH SCOPE / REJECT verdict exactly as originally written.

## Task Commits

None of the three tasks produced a repository diff of their own — Task 1 was a read-only
independent review, Task 2 was owner-executed production DDL (no repo file changed), and Task 3
was a read-only dry-run whose only artifact (the name-bearing report) was deliberately created
and deleted outside the repository working tree. This plan's only commits are the SUMMARY and
state-tracking commits below.

1. **Task 1: Independent production-risk review of the combined fix** — no commit (review-only).
   Verdict `pass` recorded in full below.
2. **Task 2: Juan creates a fresh same-UTC-day backup table** — no repository commit (owner DDL
   against production Supabase). Recorded below.
3. **Task 3: Zero-defect verification dry-run, then re-entry into 12-06** — no repository commit
   (read-only run; report directory deleted after counts were extracted). Recorded below.

**Plan metadata:** this SUMMARY + STATE.md/ROADMAP.md/REQUIREMENTS.md, committed together as
`docs(12-10): close plan — independent review, backup, zero-defect dry-run`.

## Task 1: Independent Production-Risk Review

Dispatched by the execute-phase orchestrator (~05:45 UTC 2026-09-04) as an Opus-pinned
`production-risk-reviewer` with no authoring context. Scope: `git diff 2c794a9..786329b` limited
to `scripts/backfill_claim_time_attribution.py`, `tests/test_backfill_claim_time_attribution.py`,
`billing_audit/own03_backfill_attribution.sql`, `billing_audit/schema.sql`, plus the plan's
8-point rubric.

**Verdict: pass.**

1. FINDING (LOW): source 4 feeds raw DB identifiers into `_resolve_single_name` with no
   extension filter (`script :725`); source 3 rejects only the closed extension set, so an
   extension outside `xlsx|xlsm|xls|csv|pdf|json` (e.g. `.xlsb`) survives (`:1015`). Source-4
   identifiers are sanitized name segments, never filenames
   (`pipeline/orchestrate.py:504-520`); sources 1/2 read observed name fields. Anything in the
   closed set that leaks is caught by the payload guard (`:1304`) and the SQL guard
   (`own03 :342`). Not blocking.
2. OK: pattern anchored (`$`) with a literal dot before a 6-token closed set (`:171-173`);
   the helper sanitizer deletes dots, the identifier sanitizer preserves them, so
   initialled/suffixed names are never truncated.
3. FINDING (LOW): extraction identical (`remainder[:match.start()]` before/after,
   `:1008-1009`; `.strip("_")` unchanged `:1012`); the new
   `if _FILENAME_DOC_EXTENSION_RE.search(name_part): return None` (`:1015-1016`) sits on the
   shared tail, so a hash-suffixed name whose post-strip segment still ends in a doc extension
   now yields `None` instead of a proposal. Strictly narrowing; a documented delta, not a
   defect.
4. OK: the payload guard sits after the `is_target` fork and covers both
   `include_blank_roles` branches (`:1296-1316`); `is_sentinel_claimer(None)` is `True` so
   blank values are skipped.
5. OK: zero deletions in `own03_backfill_attribution.sql`; `is_sentinel_value` (`:234`)
   untouched; the three `UPDATE ... WHERE` clauses unchanged (`:385, :403, :421`). The guard
   applies to `v_row.value` in the pre-validation loop only.
6. OK: the Python warning emits a count only (`:1320-1326`); the SQL `RAISE` interpolates
   `role`/`wr`/`week_ending`/`smartsheet_row_id`, never the value (`:343-345`); test names are
   fictional.
7. OK: the validation loop closes at `:355`, `RETURN QUERY` begins at `:369`; `RAISE` aborts
   the whole call before any `UPDATE`.
8. OK: no change to `generate_weekly_pdfs.py`, `pipeline/*`, `audit_billing_changes.py`, or
   `lookup_attribution_bulk` in the scoped files.

**Findings requiring a fix: none.** No fix round was needed.

**Residual risks (non-blocking, carried forward, not this plan's to close):**

- Closed-set coverage is exact, not general; widen all three lists together if the artifacts
  table gains another writer.
- Trailing-whitespace evasion (`"Avery Example.xlsx "`) is unreachable today because upstream
  normalization trims.
- Pre-existing, unchanged: `_FILENAME_HASH_SUFFIX_RE` `_[0-9a-fA-F]{6}\.xlsx$` (`:161`) eats a
  final name segment of six hex letters (e.g. `..._User_Ada_Facade.xlsx` -> `Ada`). Separate
  ticket, not G-12-3.
- The 12-06 dry-run report (the REJECTED one) is no longer a valid approval artifact; a fresh
  dry-run (this plan's Task 3) had to be reviewed before any future `--i-approved-this`.
- The 12-09 NOTIFY-pgrst risk is CLOSED: the orchestrator ran `NOTIFY` and confirmed the guard
  in `pg_get_functiondef` at 05:37 UTC (see 12-09-SUMMARY.md).
- Fail-closed is all-or-nothing per RPC call (`exit 6` on one bad row); the Python pre-filter
  keeps that rare.

**Verify gate (re-run at Task 1 close):** `python -m pytest tests/ -q` — 2117 passed, 1 skipped,
441 subtests. `python -m py_compile scripts/backfill_claim_time_attribution.py` — clean.
`bash scripts/run_6_gates.sh` — ALL 6 GATES PASSED.

## Task 2: Fresh Same-UTC-Day Backup Table

**Owner-authorized deviation.** The plan's Task 2 `<action>` specifies Juan runs STEP 1 by hand
in the Supabase SQL editor. At Juan's explicit choice — the same owner-directed deviation
pattern already used and recorded in 12-09 for STEP 4/5 — the orchestrating main session ran
STEP 1 through the Supabase MCP instead. No executor agent, script, or automated pipeline code
executed any DDL; only the human-directed orchestrating session, acting on Juan's explicit
real-time instruction.

**Result (2026-09-04 06:07:36 UTC):**

- New table: `billing_audit.attribution_snapshot_backup_20260904`.
- Row count: 220,621 — matches the live `billing_audit.attribution_snapshot` row count
  (220,621) exactly. The counts agree.
- `GRANT SELECT ... TO service_role` applied against that exact table name; confirmed
  `service_role` SELECT = `true`.
- STEP 1 VERIFY query listed both `attribution_snapshot_backup_20260904` and
  `attribution_snapshot_backup_20260903` — the prior-day backup (220,010 rows) was preserved,
  never replaced or dropped.
- Juan reviewed and replied `approved`.

**Validity window.** This backup satisfies the `--apply` precondition probe (which builds the
expected name from TODAY's UTC date) only for an apply performed on 2026-09-04. **If the 12-06
apply slips past 2026-09-05 00:00 UTC, STEP 1 must be re-run against the new UTC day before
`--apply` can succeed** — the probe will otherwise exit 3.

## Task 3: Zero-Defect Verification Dry-Run, Then Re-Entry into 12-06

**Invocation** (read-only, exit 0, executed by the previous continuation agent):

```
REPORT_DIR="${TMPDIR:-/tmp}/own03_verify"
rm -rf "$REPORT_DIR" && mkdir -p "$REPORT_DIR"

python scripts/backfill_claim_time_attribution.py \
  --wr 89732091 \
  --weeks 071325,072025,072725,080325,081025,090725,091425 \
  --report-dir "$REPORT_DIR"
```

No `--include-blank-roles` (per D-12-C = `defer`), no `--apply`, no `--i-approved-this`.

**Literal resolved `REPORT_DIR`:** `${TMPDIR:-/tmp}/own03_verify` resolved in the Git Bash shell
to `/tmp/own03_verify`, which is Windows path
`C:\Users\juflores\AppData\Local\Temp\own03_verify` — outside the repository working tree in
both representations. The script's own `_warn_if_report_dir_outside_generated_docs` WARNING
fired as expected (not a failure). After the counts below were extracted, `$REPORT_DIR` was
deleted. `git status --porcelain` was clean apart from pre-existing untracked items unrelated to
this plan.

**Counts — same WR, same 7 weeks, same 235 sentinel rows, before (pre-fix reproduction) vs.
after (this run). Counts, WR numbers and source labels only — no proposed value, no claimer
name, per this plan's hard prohibition:**

| Metric | Before (pre-fix) | After (this run) |
|---|---|---|
| Rows considered | 235 | 235 |
| `status = proposed` | 235 | **0** |
| `status = unresolved` | 0 | **235** |
| Extension-bearing proposals (of proposed rows) | 235 of 235 | **0 of 0** |
| Sentinel-classified proposals (`is_sentinel_claimer`) | — | **0 of 0** |
| `rows_by_source` | (single placeholder source) | **`{}`** (no source produced a candidate) |
| `include_blank_roles` | — | `False` |

Every row's evidence reason is the script's single generic exhausted-precedence fallback ("no
source (1-4, as enabled by `--sources`) produced a candidate for this row/role").

**Interpretation, recorded per the resume instructions:** the placeholder value is no longer
proposed anywhere on this scope — the source-3 defect the reviewed fix targeted is closed. The
zero is **vacuous but correct** on this specific scope: none of sources 1-4 currently hold a
legitimate name for these 235 rows, which is exactly the correct shape for a filename that
encodes "no foreman recorded" rather than a wrong guess. Whether the 4,070 formerly-placeholder
rows across the full rejected-run population resolve via source 4 or end unresolved is what
12-06's own Task 1 full-scope dry-run must show — this plan proves the defect mechanism is
fixed, not that every row now resolves to a name.

**Automated verify gate:** the extension-bearing-proposal checker
(`extension_bearing_proposals=0 of 0 rows`, exit 0) and `git status --porcelain` (clean) both
passed against the resolved `$REPORT_DIR` path, per the plan's own `<verify>` block.

### Re-entry conditions — all five met

1. 12-07's parser fix and 12-09's live RPC guard are both in place.
2. An independent reviewer returned `pass` (Task 1, above).
3. A same-UTC-day backup exists under the recorded name (`attribution_snapshot_backup_20260904`,
   Task 2, above), valid for `--apply` only through 2026-09-04 23:59 UTC.
4. The scoped dry-run shows zero extension-bearing and zero sentinel proposals (Task 3, above).
5. The `--include-blank-roles` posture (`defer`, D-12-C) and the SC3 sample
   (`substitute-89829163`, D-12-D) are pinned by 12-08.

**Juan's resume signal:** `re-enter-12-06` (2026-09-04), selected from the orchestrator's
prompt after reviewing the before/after counts above.

### 12-06 re-entry declaration

**Plan 12-06 is now formally re-entrant from its own Task 1.** Its Task 1 is the full-scope
owner review Juan must still perform against 12-06's own seven-step checklist, invoked with the
posture pinned by 12-08 (no `--include-blank-roles`; SC3 sample WR 89829163 verified via
`backfill_artifacts`). 12-06's Tasks 2-4 (the one-way `--apply` decision, the apply itself, and
post-run scheduled-billing verification) remain gated behind Juan's own
APPROVE / APPROVE WITH SCOPE / REJECT verdict, exactly as originally written in 12-06-PLAN.md.
`12-06-PLAN.md` was not modified by this plan — confirmed byte-for-byte unchanged
(`git status --porcelain` shows it untouched).

## Files Created/Modified

- `.planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-10-SUMMARY.md` — this file.
- `.planning/STATE.md` — plan position, decisions, session continuity (via `gsd-tools query
  state.*`).
- `.planning/ROADMAP.md` — Phase 12 plan-progress row for 12-10 (via `gsd-tools query
  roadmap.update-plan-progress`).
- `.planning/REQUIREMENTS.md` — OWN-02 and OWN-03 marked complete (shared-ID gate cleared: both
  declaring siblings, 12-06 and 12-10, now have a `*-SUMMARY.md`; see Requirements note below).

No production code (`scripts/*`, `billing_audit/*.sql`, `tests/*`) was modified by this plan —
all three tasks were review, owner-DDL, and read-only-dry-run tasks by design.

## Decisions Made

See `key-decisions` in frontmatter. In prose:

- Task 1's independent review verdict is `pass`; no fix round was needed, closing the
  independent-judgment re-entry condition.
- Task 2's backup DDL was applied via the Supabase MCP at Juan's explicit direction (not by
  hand in the SQL editor as originally planned) — an owner-authorized deviation, mirroring the
  same pattern 12-09 already used for STEP 4/5.
- Task 3's counts prove the source-3 defect is closed on the exact scope that previously failed
  100%; Juan's `re-enter-12-06` reply is the explicit acknowledgment that 12-06 re-entry begins
  at Task 1 with the full-scope owner review still outstanding.

## Deviations from Plan

### Owner-authorized deviations (not Rule 1-4 auto-fixes)

**1. Task 2's backup DDL apply method deviated from the plan's stated procedure, at Juan's
explicit choice.**
- **Found during:** Task 2 (the `blocking-human` checkpoint).
- **What the plan specified:** the plan's Task 2 `<action>` and `<how-to-verify>` state "Juan
  performs these steps [in the Supabase SQL editor]" and "the executor performs none of these
  steps itself and does not use an MCP write tool."
- **What actually happened:** at Juan's explicit choice, the orchestrating main session — not
  an executor agent, not a script — ran STEP 1 (the `CREATE TABLE ... AS SELECT` and the
  `GRANT SELECT ... TO service_role`) via the Supabase MCP. This mirrors the identical
  owner-authorized deviation already recorded in 12-09-SUMMARY.md for that plan's STEP 4/5
  apply.
- **Why this is not a Rule 4 violation:** Juan proactively chose the mechanism for
  already-approved DDL and then reviewed the resulting live read-backs (table name, row count
  agreement, GRANT confirmation, VERIFY listing) before this task closed. The owner made both
  the instruction and the approval.
- **Verification:** the row-count agreement (220,621 = 220,621), the `service_role` SELECT =
  `true` confirmation, and the VERIFY listing showing both dated tables, all above.
- **Impact:** none on the shipped artifact set — this plan modifies no repository file for
  Task 2; only the mechanism of applying already-reviewed SQL (SQL editor vs. MCP tool, both
  under Juan's real-time direction) differs from the plan's original text.

**2. (Reference, not new — recorded in 12-09-SUMMARY.md) Task 3's SQL apply in plan 12-09 (STEP
4 + STEP 5) was likewise applied via the Supabase MCP at Juan's explicit written instruction
("you run step 4 for me to validate this step"), rather than by hand as that plan's text
specified. Not re-litigated here; see 12-09-SUMMARY.md's own Deviations section for the full
record.**

**Total deviations:** 2 owner-authorized deviations across this gap-closure arc (1 in this
plan's Task 2, 1 already recorded in 12-09). **Impact:** none on any shipped artifact or
contract — only the DDL-application channel changed, always under Juan's explicit real-time
direction and subsequent approval.

## Issues Encountered

None.

## User Setup Required

None — Task 2's backup creation and Task 3's dry-run review were both Juan's own
already-completed actions (via the orchestrating session at his direction), recorded above.

## Next Phase Readiness

- **Plan 12-06** is re-entrant from its own Task 1. Its Tasks 2-4 remain gated behind Juan's own
  APPROVE / APPROVE WITH SCOPE / REJECT verdict.
- **Backup validity:** `attribution_snapshot_backup_20260904` is valid for `--apply` purposes
  only through 2026-09-04 23:59 UTC. If 12-06's apply is not performed on 2026-09-04 UTC, STEP 1
  must be re-run for the new UTC day before `--apply` will pass its precondition probe.
- **Requirements:** OWN-02 and OWN-03 are marked complete in `REQUIREMENTS.md` (shared-ID gate
  cleared — both declaring plans, 12-06 and 12-10, now have a `*-SUMMARY.md` on disk). This
  reflects that the gap-closure arc (G-12-3) and its review/backup/verification requirements are
  satisfied; 12-06's own remaining live-apply work is tracked independently through its own
  Tasks 2-4 and does not gate this requirement completion per the mechanical shared-ID rule.
- No real claimer name was written into this summary, `STATE.md`, `ROADMAP.md`, or any committed
  file — counts, a WR number, and option ids only.

## Self-Check: PASSED

- `.planning/phases/12-ownership-last-known-foreman-as-of-the-week/12-10-SUMMARY.md` exists on
  disk with the content above.
- `git log --oneline --all --grep="12-10"` finds this plan's closing commit(s) once committed
  below.
- Task 1 verdict source verified against
  `C:/Users/juflores/AppData/Local/Temp/claude/C--Users-juflores-dev-Generate-Weekly-PDFs-DSR-Resiliency-1/f8684c2d-3b55-42e4-948b-9c03e91d5b68/scratchpad/12-10-task1-independent-review.md`
  — transcribed verbatim above.
- Task 2 and Task 3 figures verified against the `<completed_tasks>` and `<user_response>`
  evidence supplied to this continuation agent, transcribed verbatim (counts and table names
  only, no claimer names).
- `12-06-PLAN.md` confirmed unmodified by this plan (`git status --porcelain` shows no change to
  it).

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-04*
