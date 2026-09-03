---
phase: 12-ownership-last-known-foreman-as-of-the-week
plan: 05
subsystem: documentation
tags: [docusaurus, runbook, living-ledger, billing-attribution, backfill, pytest]

# Dependency graph
requires:
  - phase: 12-01
    provides: "scripts/backfill_claim_time_attribution.py — sources 1-4 ladder, CLI surface, exit codes 0/2/3/4/6/7/8, named-sentinel targeting, in-week source-1 guard"
  - phase: 12-02
    provides: "pipeline/cleanup.py CR-01 allowlist + _is_real_name_identifier; pipeline/orchestrate.py WR-01 guarded AttachmentParentType import"
  - phase: 12-03
    provides: "billing_audit/own03_backfill_attribution.sql — backup table, backfill_source / backfill_run_id, is_sentinel_value, backfill_attribution RPC, five-tag vocabulary"
  - phase: 12-04
    provides: "scripts/backfill_cell_history_attribution.py (source 5) and .github/workflows/cell-history-backfill.yml (dispatch-only after the owner re-decision)"
provides:
  - "website/docs/runbook/ownership-attribution.md — the operator-facing account of the ownership ladder AS IMPLEMENTED (D-12-A, D-12-B, amended Foundation A, five provenance tags, procedure, exit codes, two-scripts warning, dispatch job, rollback, component owners)"
  - "Rewritten website/docs/runbook/scripts.md, workflows.md and reference/environment.md that link to the ownership page instead of restating it"
  - "memory-bank/living-ledger.md [2026-09-03 13:55] — the durable record of D-12-A, D-12-B, the amended Foundation A contract, CR-01, WR-01, source-5 isolation and the two-scripts trap"
  - "tests/test_own04_documentation.py — 20-test structural gate that fails if the dropped cross-week rung, the non-existent --hash-history flag, the retired ATTACHMENT_PREFETCH_ / DISCOVERY_CACHE_ variables, or a shipped wr_week_ownership table ever re-enter the page"
affects: [12-06]

# Actuals (#2632) — chars/4 over the realized diff of every file this plan touched
# (git diff 9bbbb9f~1..c968d44 over the nine files below), NOT a harness token count.
actuals:
  tokens: 12272
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Documentation structural gate: a pytest module reads a runbook page as text (HTML comments stripped) and asserts required headings / vocabulary and ZERO occurrences of retired or never-shipped literals, with a sentence-scoped allowance (wr_week_ownership only alongside 'Phase 13') — keeps a decision record honest without a Docusaurus build"
    - "Runbook cross-linking by Docusaurus file path (ownership-attribution.md, ../reference/environment.md#anchor) so the build's link/anchor checker validates every reference; heading slugs confirmed in the built HTML (minified, unquoted id= attributes)"

key-files:
  created:
    - website/docs/runbook/ownership-attribution.md
    - tests/test_own04_documentation.py
  modified:
    - website/sidebars.ts
    - website/docs/runbook/scripts.md
    - website/docs/runbook/workflows.md
    - website/docs/reference/environment.md
    - website/docs/runbook/auth-rbac-bootstrap.md
    - website/docs/runbook/vercel-deployment.md
    - memory-bank/living-ledger.md

key-decisions:
  - "Documented AS IMPLEMENTED, not as planned: the provenance vocabulary is five tags (backfill_cell_history included), source 5 paces at 0.5 s and tags backfill_cell_history (operator is reserved, unwritten), the sources 1-4 CLI requires both --wr and --weeks (exit 8) and targets named sentinels only by default, and the 12-03 SQL is authorized but not yet confirmed live — every one of these overrides the plan text per the wave 1-2 SUMMARY addenda."
  - "cell-history-backfill.yml is documented as manual workflow_dispatch ONLY with no cron anywhere in the runbook, workflow inventory, docs test, or ledger — per the orchestrator's mid-execution course correction (owner re-decided 12-04 Task 3 to dispatch-only, resolving Opus H1). The Sunday 05:00 UTC schedule is described only as deferred to 12-06 together with a real candidate source."
  - "The fresh-runner precondition is stated truthfully: a dispatch today is a bounded no-op (Supabase reads only, zero Smartsheet calls) because the backfill step takes candidates only from generated_docs/own03_backfill_report.json, which no shipped step produces on the runner; nothing works through the backlog unattended."
  - "The two-scripts warning states the policy conflict and that backfill_attribution_snapshot.py's effect on an already-repaired row is UNVERIFIABLE from this repo (the freeze_attribution RPC body lives in Supabase) rather than asserting a mechanism — the plan's 'would overwrite the repair' wording could not be proven from repo evidence and was not repeated."
  - "sidebar_position 7 collided with auth-rbac-bootstrap, so that page moved to 8 and vercel-deployment to 9 exactly as the plan's conditional instruction directs; website/sidebars.ts is an explicit array so ordering is unaffected either way."
  - "environment.md's retired ATTACHMENT_PREFETCH_* / DISCOVERY_CACHE_* entries were already marked 'Retired — no-op' (Performance section, PR #373) — verified and left unchanged; the only environment.md rewrite beyond the new CELL_HISTORY_BACKFILL_* table is the REMEDIATE_CLAIMERS sentinel passage, which now says a provenance-tagged backfilled value is used before the CURRENT Smartsheet foreman."

patterns-established:
  - "Docs-as-contract test (tests/test_own04_documentation.py): negative greps for retired / never-shipped literals are the gate that keeps a runbook from re-deriving a rejected design."

requirements-completed: [OWN-01, OWN-04]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "website/docs/runbook/ownership-attribution.md exists, is reachable from the Runbook sidebar, and documents the ladder as implemented with D-12-A / D-12-B, the five provenance tags, both backfill scripts, rollback, and component owners, with zero forbidden literals"
    requirement: "OWN-04"
    verification:
      - kind: unit
        ref: "tests/test_own04_documentation.py (20 tests: existence/id, 3 headings, 5 tags, sentinel, both scripts, D-12-A/B, 4 forbidden literals absent, wr_week_ownership only as a Phase 13 deferral, sidebar entry)"
        status: pass
      - kind: other
        ref: "npm --prefix website run typecheck — tsc, zero 'error TS' lines"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts.md, workflows.md and environment.md rewritten with one coherent account (scripts told apart with the current-value warning in exactly one place; cell-history-backfill.yml inventoried as dispatch-only with caps, own concurrency group, backlog gate; four CELL_HISTORY_BACKFILL_* variables each marked never read by the production run) and no broken cross-links"
    requirement: "OWN-04"
    verification:
      - kind: other
        ref: "npm --prefix website run build — '[SUCCESS] Generated static files', no 'Broken link' / 'broken anchors' output (onBrokenLinks: warn, onBrokenAnchors default warn); every linked anchor confirmed present in build/docs/**/*.html (id=cell-history-backfillyml, id=ownership-attribution-backfill, id=ownership-attribution-backfill-source-5, id=the-dispatch-job-cell-history-backfillyml, id=running-the-backfill, id=rollback)"
        status: pass
    human_judgment: false
  - id: D3
    description: "memory-bank/living-ledger.md ends with one dated [2026-09-03 13:55] entry recording D-12-A, D-12-B, the amended Foundation A contract, CR-01, WR-01, source-5 isolation and the two-scripts trap, with no credential-shaped string and CLAUDE.md untouched"
    requirement: "OWN-01"
    verification:
      - kind: other
        ref: "grep counts on the entry: D-12-A=2 D-12-B=2 CR-01=2 WR-01=2 backfill_source=2 backfill_run_id=1 cell-history-backfill.yml=1; zero matches for SUPABASE_SERVICE_ROLE_KEY / SMARTSHEET_API_TOKEN / JWT-, ghp_-, sk--shaped tokens / supabase.co URLs; git diff --name-only 9bbbb9f~1..HEAD does not list CLAUDE.md"
        status: pass
      - kind: unit
        ref: "python -m pytest tests/ -q — 2090 passed, 1 skipped, 405 subtests passed (33 s)"
        status: pass
    human_judgment: false
  - id: D4
    description: "No forbidden path touched: .github/workflows/*, scripts/*, billing_audit/*, pipeline/* and every pre-existing test file are unchanged by this plan's commits"
    verification:
      - kind: other
        ref: "git diff --name-only 9bbbb9f~1..HEAD lists exactly the nine files under key-files plus .planning/ — zero matches for ^(\\.github/workflows/|scripts/|billing_audit/|pipeline/) and no tests/ file other than tests/test_own04_documentation.py"
        status: pass
    human_judgment: false

# Metrics
duration: ~17min
completed: 2026-09-03
status: complete
---

# Phase 12 Plan 05: OWN-04 Ownership Runbook and Living Ledger Summary

**One operator-facing runbook page documents the claim-time ownership ladder exactly as waves 1-2 shipped it — five provenance tags, no cross-week rung, no `wr_week_ownership` table, the amended first-write-wins contract enforced in Python and SQL, a dispatch-only cell-history job whose fresh-runner no-op is stated plainly — with three existing pages rewritten to point at it, a dated Living Ledger entry, and a 20-test structural gate that fails if a rejected design ever re-enters the page.**

## Performance

- **Duration:** ~17 min (13:42 branch check → 13:57 CDT last commit)
- **Tasks:** 3 of 3 completed (all `type="auto"`)
- **Files modified:** 9 (2 created, 7 modified) plus `.planning/WINDOWS.md` (one deviation entry)

## Accomplishments

- `website/docs/runbook/ownership-attribution.md` (new, `sidebar_position: 7`, listed after `runbook/operations` in `website/sidebars.ts`): who owns a (WR, week) file and the three role claim conditions; the ladder as implemented (`observed_in_week` → same-row other role → `backfill_artifacts` → `backfill_hash_history` → cell history → sentinel) with D-12-A and D-12-B in admonitions; the amended Foundation A contract and its three enforcement points (`is_sentinel_claimer`, `billing_audit.is_sentinel_value`, the RPC `WHERE`); the five-tag `backfill_source` vocabulary; a sources-and-limits table with abstention rules and the single-name rule; the dry-run → review → same-UTC-day backup → `--apply --i-approved-this` procedure with both scripts' exit-code tables; the dispatch job's triggers, isolation, caps, backlog gate and its fresh-runner no-op precondition; the Pitfall 4 two-scripts warning; what the next production run does after an apply (regeneration under the real name, sentinel-superseded cleanup, the CR-01 fail-safe direction); rollback from `attribution_snapshot_backup_<YYYYMMDD>`; and a who-owns-what table naming the component for every flow. Only fictional names (`Avery Example`, `Pat Example`, `Sam Sample`) appear.
- `website/docs/runbook/scripts.md`: new "Ownership attribution backfill" section that tells the three `attribution_snapshot` writers apart in one place and links to the ownership page rather than restating the ladder.
- `website/docs/runbook/workflows.md`: `cell-history-backfill.yml` added to the inventory as **manual `workflow_dispatch` only** (no cron; schedule deferred to 12-06 with a candidate source), with `permissions: contents: read`, its own `cell-history-backfill-` concurrency group, `timeout-minutes: 60` above the 45-minute script cap, the four pinned caps, the Supabase-only backlog gate, the artifact upload, the shared-token rationale, and the fresh-runner precondition.
- `website/docs/reference/environment.md`: new "Ownership attribution backfill (source 5)" table for `CELL_HISTORY_BACKFILL_MAX_REQUESTS` (3000), `_MAX_ROWS` (1200), `_PACE_SEC` (0.5), `_MAX_MINUTES` (45), each marked read only by the source-5 script and never by the production run; the `REMEDIATE_CLAIMERS` sentinel passage now states that a provenance-tagged backfilled value is used before the current Smartsheet foreman and links to the ownership page. The retired `ATTACHMENT_PREFETCH_*` / `DISCOVERY_CACHE_*` entries were already documented as no-ops and were verified, not touched.
- `memory-bank/living-ledger.md`: one `[2026-09-03 13:55]` entry at the bottom (after `[2026-09-03 11:05]`) recording, in the plan's order, D-12-A, D-12-B, the amended Foundation A contract, the CR-01 rule, the WR-01 rule, source-5 isolation (dispatch-only shape and why), the two-scripts trap, and the items carried to 12-06. `CLAUDE.md` untouched.
- `tests/test_own04_documentation.py`: 20 tests following the `tests/test_generate_runbook_entry.py` module shape.

## Task Commits

1. **Task 1: Write the ownership-attribution runbook page** — `9bbbb9f` (docs)
2. **Task 2: Rewrite the affected existing runbook and reference pages** — `e0eebd7` (docs)
3. **Task 3: Append the dated Living Ledger entry** — `97b6501` (docs)
4. **Post-task wording fix (all three tasks' files)** — `c968d44` (docs) — see Deviations 5

**Plan metadata:** this SUMMARY.md's commit follows. STATE.md / ROADMAP.md / REQUIREMENTS.md are owned centrally by the orchestrator after the wave (same convention as 12-04) and were not edited here.

## Files Created/Modified

- `website/docs/runbook/ownership-attribution.md` — new runbook page (see Accomplishments).
- `website/sidebars.ts` — `'runbook/ownership-attribution'` inserted after `'runbook/operations'`; nothing removed.
- `website/docs/runbook/auth-rbac-bootstrap.md`, `website/docs/runbook/vercel-deployment.md` — `sidebar_position` 7→8 and 8→9 (frontmatter only; plan-directed collision fix).
- `website/docs/runbook/scripts.md`, `website/docs/runbook/workflows.md`, `website/docs/reference/environment.md` — targeted rewrites described above.
- `memory-bank/living-ledger.md` — one appended entry.
- `tests/test_own04_documentation.py` — new structural gate.
- `.planning/WINDOWS.md` — one `deviation` entry (dispatch-only re-decision during execution).

## Decisions Made

See `key-decisions` in frontmatter — summarized: (1) documented as implemented, with the wave 1-2 SUMMARY addenda overriding the plan text everywhere they differ; (2) the cell-history workflow is described as dispatch-only, no cron, per the mid-execution course correction; (3) the fresh-runner no-op precondition is stated plainly; (4) the two-scripts warning states unverifiability rather than an unproven mechanism; (5) the sidebar-position collision was resolved as the plan instructs; (6) the retired variables were already correct.

## Deviations from Plan

### Reality delta (plan text superseded by what shipped)

**1. [Documented as implemented] Plan vocabulary and numbers replaced by the shipped ones**
- **Found during:** Task 1 read-first
- **Issue:** The plan (written before the review rounds) lists four provenance tags plus `sentinel`, a 0.25 s pace, and a "runs on the Sunday cron" workflow; the shipped code has five tags (`backfill_cell_history` added in `f3b6db3`), a 0.5 s pace (`101489d`), source 5 tagging `backfill_cell_history` (not `operator`), both `--wr` and `--weeks` required (exit 8), named-sentinel-only default targeting, and a source-1 in-week guard (D-12-A, Greptile fix).
- **Fix:** Every page and the ledger use the shipped values; the docs test pins all five tags.
- **Files modified:** all documentation files in this plan
- **Commits:** `9bbbb9f`, `e0eebd7`, `97b6501`

**2. [Mid-execution course correction] Workflow documented as dispatch-only**
- **Found during:** Task 1 (orchestrator message while the page was being written; the `schedule:` block was removed from the workflow in `90d715b` on this branch)
- **Issue:** Plan Task 2 says to document "the Sunday 05:00 UTC cron if plan 12-04 Task 3 selected `approve-cron`"; the owner re-decided to dispatch-only after the Opus H1 finding.
- **Fix:** No scheduled run is described anywhere in the runbook, workflow inventory, docs test or ledger; the cron appears only as "approved, then re-decided to dispatch-only; deferred to 12-06 with a real candidate source". The workflow file and its tests were not touched by this plan.
- **Files modified:** `ownership-attribution.md`, `workflows.md`, `scripts.md`, `environment.md`, `living-ledger.md`
- **Commits:** `9bbbb9f` (rewritten before commit), `e0eebd7`, `97b6501`; recorded in `.planning/WINDOWS.md` as a `deviation`

### Auto-fixed / plan-directed adjustments

**3. [Plan-directed] `sidebar_position` renumbered on two pages not in `files_modified`**
- **Found during:** Task 1
- **Issue:** `auth-rbac-bootstrap.md` already had `sidebar_position: 7`.
- **Fix:** 7→8 and `vercel-deployment.md` 8→9, exactly as the plan's "renumber only if they collide" instruction directs. Frontmatter only.
- **Commit:** `9bbbb9f`

**4. [Rule 2 - Missing critical] `environment.md` sentinel passage corrected**
- **Found during:** Task 2 read-first
- **Issue:** The `REMEDIATE_CLAIMERS` passage said the next run resolves a frozen sentinel "from the CURRENT Smartsheet foreman" with no mention of the OWN-03 backfilled value — after this phase that would contradict the ownership page (documentation-maintenance rule: rewrite, do not contradict).
- **Fix:** One sentence rewritten: backfilled value first, current value otherwise, with a link to the ownership page.
- **Commit:** `e0eebd7`

**5. [Rule 1 - Accuracy] Unverifiable mechanism removed from the two-scripts warning**
- **Found during:** Self-review after Task 3
- **Issue:** The plan's wording ("would overwrite the repair with the current value") and my first draft both asserted what `scripts/backfill_attribution_snapshot.py` does to an already-repaired row. That path runs through the Supabase-resident `freeze_attribution` RPC, whose body is not in this repo (ledger `[2026-09-02 00:35]` records the same reliance), so neither claim can be verified here. A separate sentence attributed regeneration to the content hash where the verifiable mechanism is the group identity carrying the real name.
- **Fix:** The warning (page, `scripts.md`, ledger) now states the policy conflict and the unverifiability and keeps the instruction "never run it against remediated WRs"; the regeneration sentence names the group identity.
- **Files modified:** `ownership-attribution.md`, `scripts.md`, `living-ledger.md`
- **Commit:** `c968d44`

**6. [No change needed] Retired variables already correct**
- The plan asks to correct `ATTACHMENT_PREFETCH_MAX_MINUTES`, `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC`, `DISCOVERY_CACHE_TTL_MIN`, `USE_DISCOVERY_CACHE` if presented as live; `environment.md` § Performance already marks all four "Retired — no-op" (PR #373). Verified, untouched.

---

**Total deviations:** 2 reality-delta, 1 plan-directed, 1 Rule 2, 1 Rule 1 accuracy, 1 no-op. No architectural change, no dependency added, no forbidden path touched.

## Issues Encountered

- The first anchor check grepped the built HTML for `id="..."`; Docusaurus 3.10 emits minified, unquoted `id=...` attributes, so the check returned zero even for known headings. Re-run with the unquoted form: every linked anchor is present. Not a documentation defect.
- `website/docusaurus.config.ts` sets `onBrokenLinks: 'warn'` (and leaves `onBrokenAnchors` at its default `warn`), so a broken link would not fail the build; the build output was grepped for `broken` and produced none, and the anchors were confirmed directly as above.

## Verification (this run)

- `python -m pytest tests/test_own04_documentation.py -q` — 20 passed (after Tasks 1, 2, 3 and the wording fix).
- `npm --prefix website run typecheck` — `tsc`, zero `error TS` lines (after Task 1 and after the final edit).
- `npm --prefix website run build` — `[SUCCESS] Generated static files in "build"`, no `Broken link` / broken-anchor output (after Task 2 and after the final edit).
- `python -m pytest tests/ -q` — 2090 passed, 1 skipped, 405 subtests passed.
- `git diff --name-only 9bbbb9f~1..HEAD` — nine documentation/test files only; no `.github/workflows/*`, `scripts/*`, `billing_audit/*`, `pipeline/*`, `CLAUDE.md`, or pre-existing test file.
- Line endings: every edited file kept its CRLF working copy (`file`), index stays LF (`core.autocrlf=true`).
- Nothing pushed.

## User Setup Required

None. Documentation only. The page itself lists two owner items it documents truthfully rather than resolves: the 12-03 Task 4 live apply (SQL not yet confirmed live) and a candidate source for the dispatch job (12-06).

## Next Phase Readiness

- Plan 12-06 (live apply, human checkpoint) can send an operator to `website/docs/runbook/ownership-attribution.md` § "Running the backfill" and § "Rollback" as the procedure of record; when 12-06 restores the Sunday cron together with a candidate source, the "dispatch job" section, `workflows.md`, `environment.md`, and the ledger's source-5 bullet need the schedule sentence rewritten (the docs test does not pin the absence of a cron, so it will not block that change).
- No known stubs. No skipped tests. No unrun `<verify>` commands — every plan-level verification command was executed in this session and passed.

---
*Phase: 12-ownership-last-known-foreman-as-of-the-week*
*Completed: 2026-09-03*

## Self-Check: PASSED

- FOUND: website/docs/runbook/ownership-attribution.md, tests/test_own04_documentation.py, memory-bank/living-ledger.md, website/sidebars.ts (with runbook/ownership-attribution), this SUMMARY
- FOUND commits: 9bbbb9f (Task 1), e0eebd7 (Task 2), 97b6501 (Task 3), c968d44 (wording fix)
- VERIFIED this run: docs test 20 passed; tsc clean; site build SUCCESS with no broken-link output; full suite 2090 passed / 1 skipped; no forbidden path in git diff --name-only 9bbbb9f~1..HEAD
