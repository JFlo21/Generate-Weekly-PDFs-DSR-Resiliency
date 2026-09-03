---
id: ownership-attribution
title: Ownership and claim-time attribution
sidebar_position: 7
---

# Ownership and claim-time attribution

*(Phase 12, OWN-01 / OWN-02 / OWN-03 / OWN-04. Written 2026-09-03 from what
shipped, not from the requirements text — where `REQUIREMENTS.md` and this page
disagree, this page is current. All claimer names on this page are fictional:
`Avery Example`, `Pat Example`, `Sam Sample`.)*

This page is the one place that explains who a weekly Excel file belongs to, how
the pipeline decides that, how to repair a file that was frozen under a
placeholder name, and how to undo the repair. It supersedes the ladder wording
in `REQUIREMENTS.md` OWN-01.

## Who owns a (WR, week) file

**Component owner:** Python billing pipeline (`generate_weekly_pdfs.py` on its
GitHub Actions cron) for every rule in this section.

A file for a Work Request and a week-ending is named for, and contains only the
rows of, the person who **claimed** those rows in that week. "Claimed" means the
first non-sentinel name observed on the row at or after the moment the row became
completed for that role:

| Role | Row is claimed when | Name column |
| --- | --- | --- |
| primary | `Units Completed?` checked | `Foreman` |
| helper | `Foreman Helping?` non-blank AND `Helping Foreman Completed Unit?` checked AND `Units Completed?` checked | `Foreman Helping?` |
| vac_crew | `VAC Crew Helping?` non-blank AND `Vac Crew Completed Unit?` checked AND `Units Completed?` checked | `VAC Crew Helping?` |

Subcontractor sheets (`_ReducedSub` / `_AEPBillable` variants) follow the same
primary and helper rules.

Worked example (owner decision, 2026-09-01 19:45): Avery Example claims the
week-ending 07-05 rows, the job is reassigned, and Pat Example claims the
week-ending 07-19 rows. Avery's file exists for 07-05 and Pat's for 07-19, even
though Smartsheet now shows Pat on the WR. Within one week, rows Avery claimed
on Monday stay Avery's and rows Pat claimed on Thursday stay Pat's: two files
for that week, one per claimer, each carrying only its own rows.

Three consequences you must not argue with in an incident:

- **The live Smartsheet name at generation time is a fallback, not the rule.**
  `billing_audit.writer.resolve_claimer` uses it only when no frozen or
  backfilled value exists for the row and role.
- **A later Smartsheet edit to an already-claimed row is an audit event, never
  a re-attribution.** The file does not move to the new name.
- **Correcting a real frozen name needs an operator override** (an explicit,
  audited record). That override mechanism is out of scope for Phase 12; today
  a wrong real name is a data-team ticket, not something a script fixes.

## Ownership ladder

When a row's frozen value for a role is a sentinel (`Unknown Foreman`,
`Unknown Helper`, `Unknown VAC Crew`, `#NO MATCH`, blank), the backfill resolves
the claimer by walking these sources in order and stopping at the first one that
names the row. Every source reads **only the row's own week**.

1. **`observed_in_week`** — source 1: `pipeline_memory.row_event` /
   `row_state` (provenance tag `live`). Only events whose own `week_ending`
   equals the target week count; out-of-week rows are tallied in
   `summary.source_1_out_of_week_rows` and ignored.
2. **Same row, another role** — source 2: a non-sentinel value already frozen
   for a different role on the same `attribution_snapshot` row (tag `live`).
   Fills a sentinel role only; never rewrites a real name.
3. **`backfill_artifacts`** — source 3: `public.artifacts` filenames for the
   same WR and week (tag `backfill_artifacts`). Group-level; single-name rule
   (see below).
4. **`backfill_hash_history`** — source 4: identifier tokens in
   `billing_audit.group_content_hash` and `pipeline_memory.group_state` for the
   same WR and week (tag `backfill_hash_history`). Group-level; single-name
   rule.
5. **Cell history** — source 5: the Smartsheet cell history of the role's
   completion checkbox and name column, the name in effect at the moment the box
   was checked (tag `backfill_cell_history`). Runs only in its own workflow,
   never inside the billing run.
6. **Sentinel** — no source named the row. It keeps its placeholder, and the
   next scheduled run keeps using the current Smartsheet value as the fallback.

:::note D-12-A — no cross-week rung, no ownership table
There is deliberately **no** "last known foreman at or before the week" step.
That rung was decided OFF by the owner on 2026-09-01 19:55: a week with no
in-week evidence keeps its sentinel rather than inheriting a name from an
earlier week. `REQUIREMENTS.md` OWN-01 was written before that decision and
still describes the dropped rung; this page is current.

The second half of D-12-A: Phase 12 ships **no** `wr_week_ownership` table —
that table is deferred to Phase 13. The ladder above is served entirely by
`billing_audit.attribution_snapshot` (one row per WR, week, Smartsheet row),
`resolve_claimer`, and two provenance columns added in Phase 12:
`backfill_source` and `backfill_run_id`. Anything you read elsewhere that
describes a shipped `wr_week_ownership` table is stale until Phase 13 builds it.
:::

## The amended Foundation A contract

Foundation A (2026-05-20) froze the first value seen for each row and role and
never overwrote it: **first-write-wins**. That still holds for a real name. Once
`Sam Sample` is frozen as the primary claimer of a row, nothing in this repo —
not the scheduled run, not either backfill script, not the RPC — replaces it.

What changed on the 2026-08-24 defect repair (owner policy A, shipped
2026-09-01): a frozen **sentinel** is now read as "no claimer". The scheduled run
already treated it as no-history (`resolve_claimer` falls through to the current
value; `freeze_row` nulls sentinel roles and defers a freeze when no role holds a
real name). Phase 12 extends that: a provenance-tagged backfilled value may
replace a frozen sentinel, and only a frozen sentinel.

The rule is enforced at three independent points, and all three must agree
before a value lands:

| Enforcement point | Where | What it does |
| --- | --- | --- |
| `billing_audit.writer.is_sentinel_claimer` | Python, `billing_audit/writer.py` | Blank, `#`-prefixed error tokens, and the exact placeholder family (`Unknown Foreman`, `Unknown`, `Unknown Helper`, `Unknown VAC Crew`, `No Match`) after strip / underscore-to-space / whitespace-collapse / casefold. `Unknown Person` is a name, not a sentinel. The `--apply` payload builder drops any row whose current value is not a sentinel. |
| `billing_audit.is_sentinel_value` | SQL, `billing_audit/own03_backfill_attribution.sql` STEP 3 | The SQL twin of the Python predicate, trimming all whitespace (not only spaces) before the blank, `#`-prefix, and vocabulary checks. |
| `WHERE` clause of `billing_audit.backfill_attribution` | SQL, same file STEP 4 | Each of the three per-role `UPDATE` statements is gated by `is_sentinel_value` on the row's current value. A payload row whose target is a real name returns `skipped_real_name` and touches nothing. |

Provenance vocabulary: the `backfill_source` column accepts exactly five values —
`live`, `backfill_artifacts`, `backfill_hash_history`, `backfill_cell_history`,
`operator`. Sources 1 and 2 tag `live`, source 3 `backfill_artifacts`, source 4
`backfill_hash_history`, source 5 `backfill_cell_history`. `operator` is reserved
for a human-entered override; no shipped script writes it.

## Sources and their limits

| # | Source | Tag | Coverage window | Abstains when |
| --- | --- | --- | --- | --- |
| 1 | `pipeline_memory.row_event` / `row_state` | `live` | Weeks since run-memory writes began (`RUN_MEMORY_WRITE_ENABLED`, 2026-08) | The row has no event whose own `week_ending` equals the target week, or the event's name is a sentinel. A NULL or missing week is never in-week evidence. |
| 2 | Same `attribution_snapshot` row, another role | `live` | Any week the pipeline has run | No other role on the row holds a real name. |
| 3 | `public.artifacts` filenames (`_User_`, `_Helper_`, `_VacCrew_` and the four subcontractor tokens) | `backfill_artifacts` | Any week an artifact row was recorded for the WR | Two distinct real names exist for the same week and role (conflict), or no filename names the role. |
| 4 | `billing_audit.group_content_hash` + `pipeline_memory.group_state` identifier tokens | `backfill_hash_history` | Weeks seen in a run since the durable hash store went live (2026-05-25) | Two distinct real names for the same week and role (conflict), or the week was never seen by a run since 2026-05-25. |
| 5 | Smartsheet cell history (checkbox first, then name column) | `backfill_cell_history` | Any week, subject to the request / row / wall-clock caps | The checkbox never becomes checked on or after `week_ending - 6 days`, the name in effect is a sentinel, or two different names were in effect at different in-window claims (conflict). |

:::note D-12-B — source 4 reads Supabase, not a file
Source 4 reads `billing_audit.group_content_hash` and
`pipeline_memory.group_state`. It does **not** read the retired
`hash_history.json`, and there is no command-line flag to point it at a file.
When several entries carry the same winning name, the script prefers the entry
whose `updated_at` predates the 2026-08-24 defect cutoff, then the earliest
`updated_at`. A week never seen by a run since 2026-05-25 is simply outside
source 4's coverage and falls through to sources 3 and 5.
:::

**Single-name rule (sources 3 and 4).** These sources are group-level: a filename
or hash-store token names a whole (WR, week, variant), not a row. They therefore
apply only when the week has exactly **one** real name for the role. Two distinct
real names (Avery Example and Pat Example both on week-ending 07-05) means the
source cannot say which rows were whose without source 1, so it abstains and the
row is reported as `conflict` with an empty `proposed_value`. Conflicts are
source 5's job.

**Source 5 rules** (`scripts/backfill_cell_history_attribution.py`): the
completion checkbox's history is fetched first; if it never becomes checked the
row is unresolved without spending a second request on the name column. Only a
falsy-to-truthy transition dated on or after `week_ending - 6 days` counts as a
claim (no upper bound — a late tick after the week-ending is still this row's
own claim); an earlier tick belongs to a prior week's claim on a re-dated row.
For each claim the name in effect is the last name-history entry at or before
that timestamp, reading `display_value` (a contact-list `value` is an email).
One distinct name across all claims is `proposed`; different names are
`conflict` (the evidence lists timestamps only, never the names); none is
`unresolved`. A cell-history read failure marks the row `error`, stops further
Smartsheet calls, still writes the report, and exits 7. A request or wall-clock
cap tripping mid-run defers the remaining candidates (`summary.cap_reached`,
`summary.candidates_deferred`) and exits 0; they are retried next time.

Two production caveats for source 5 as of 2026-09-03:

- It resolves a row's sheet and column ids from `pipeline_memory.row_state` and
  `sheet_registry`. Until `RUN_MEMORY_WRITE_ENABLED` is on in production and one
  full run has populated them, every candidate resolves to `unresolved` with
  reason "sheet id or column mapping unavailable for this row".
- It takes candidates only from the sources 1-4 report
  (`generated_docs/own03_backfill_report.json`). See
  [The dispatch job](#the-dispatch-job-cell-history-backfillyml) for what that
  means on a fresh GitHub Actions runner.

## Running the backfill

**Component owner:** one-time / off-hours operator remediation
(`scripts/backfill_claim_time_attribution.py`), run from a workstation with
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the environment. It never
reads current Smartsheet row state and needs no Smartsheet token.

Prerequisite for `--apply` only: the owner-applied SQL in
`billing_audit/own03_backfill_attribution.sql` (backup table, provenance
columns, `is_sentinel_value`, the `backfill_attribution` RPC) must be live in
the Supabase project. As of 2026-09-03 the apply was authorized (12-03 Task 3,
`approve`) but the live schema has not yet been confirmed; until it is,
`--apply` stops at exit 3 and the dry run is the only step available. The RPC is
`SECURITY INVOKER` with `EXECUTE` granted to `service_role` only, so the
applying role must also hold `UPDATE` on `billing_audit.attribution_snapshot`.

1. **Dry run.** Both `--wr` and `--weeks` are required (exit 8 otherwise): no
   source available to the script can enumerate "every WR with a sentinel role"
   without a raw `attribution_snapshot` scan, which is prohibited by design.

   ```bash
   python scripts/backfill_claim_time_attribution.py \
     --wr 19073866 --weeks 082425,083125,091425,092125
   ```

   Optional: `--roles primary,helper,vac_crew` (default all three),
   `--sources 1,2,3,4`, `--report-dir` (anything outside `generated_docs/`
   warns that the files will not be git-ignored). Default targeting is
   **named-sentinel only** — a role whose frozen value is blank or NULL is
   left alone; `--include-blank-roles` opts those in and is recorded in the
   report summary.

2. **Review the report.** `generated_docs/own03_backfill_report.csv` (and
   `.json`) is byte-identical across two runs over the same data. Each row is
   `proposed` (with `proposed_value`, `source`, evidence), `conflict` (empty
   value, evidence names the sources), or `unresolved` (a reason). Check
   `summary.source_1_out_of_week_rows`; a large number on an all-unresolved run
   usually means the `week_ending` column is NULL on the memory tables. The
   report is git-ignored because it carries claimer names — never commit it or
   paste it into an issue.

3. **Create the same-UTC-day backup** by running STEP 1 of
   `billing_audit/own03_backfill_attribution.sql` in the Supabase SQL editor.
   The script probes for `billing_audit.attribution_snapshot_backup_<YYYYMMDD>`
   using **today's UTC date**, so the backup and the apply must happen on the
   same UTC day.

4. **Apply.**

   ```bash
   python scripts/backfill_claim_time_attribution.py \
     --wr 19073866 --weeks 082425,083125,091425,092125 \
     --apply --i-approved-this
   ```

   The payload carries only rows whose current value is a sentinel; the RPC
   re-checks that server-side. Each RPC chunk's result count must equal the
   chunk size, and every per-row result must be one of `updated`,
   `skipped_real_name`, `skipped_no_row` — anything else is counted as an
   error and the run exits 6. The live apply against the remediation set is
   plan 12-06's human checkpoint; do not run it ad hoc.

5. **Optionally run source 5** on what is still `unresolved` or `conflict`:

   ```bash
   python scripts/backfill_cell_history_attribution.py \
     --report generated_docs/own03_backfill_report.json
   ```

   It writes `generated_docs/own03_cell_history_report.{json,csv}` and shares
   the `--apply --i-approved-this` gate, backup probe, and RPC caller with the
   first script. It needs `SMARTSHEET_API_TOKEN` only when at least one
   candidate is in scope. Prefer the dispatch job below for anything larger
   than a handful of WRs so it stays inside the caps.

Exit codes, `scripts/backfill_claim_time_attribution.py`:

| Code | Meaning |
| --- | --- |
| 0 | Success, including a run whose every row is unresolved. |
| 2 | No Supabase client (`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` missing or unusable). |
| 3 | `--apply`: the same-UTC-day backup table is definitively absent. Run STEP 1 of the SQL file first. |
| 4 | `--apply` without `--i-approved-this`. Zero writes, zero RPC calls. |
| 6 | `--apply`: the RPC raised, returned a per-row error, or returned a result count that does not match the chunk. |
| 7 | A source read failed, attribution discovery reported a definitive failure, or the backup probe failed for a reason other than "absent". Never reported as an empty result. |
| 8 | `--wr` and `--weeks` were not both given. |

Exit codes, `scripts/backfill_cell_history_attribution.py`: 0, 2, 3, 4, 6 and 7
carry the same meaning; 2 means `SMARTSHEET_API_TOKEN` is unset while
candidates are in scope, and 7 additionally covers a cell-history read failure
(the report is still written with the failing row marked `error`) or a
`--check-backlog` whose Supabase fallback scan failed. There is no exit 8 —
scoping comes from the report file.

## The dispatch job: `cell-history-backfill.yml`

**Component owner:** `.github/workflows/cell-history-backfill.yml` is the only
place `scripts/backfill_cell_history_attribution.py` runs in CI. It is a
separate, budget-capped job because both it and the billing run share one
`SMARTSHEET_API_TOKEN` and one 300 requests-per-minute ceiling.

- **Trigger:** manual `workflow_dispatch` only, with inputs `dry_run`,
  `wr_filter`, `max_requests`. There is **no cron**. The Sunday 05:00 UTC
  schedule agreed in the 2026-09-01 design (clear of the 15:00 / 19:00 / 23:00
  UTC weekend billing crons) was approved and then re-decided to dispatch-only
  by the owner on 2026-09-03 (12-04 Task 3, resolving the Opus H1 finding
  described below); it is deferred to plan 12-06 and returns only together
  with a real candidate source for the backfill step. Do not add a `schedule:`
  key before then.
- **Isolation:** its own concurrency group (`cell-history-backfill-` plus the
  git ref), queue mode, so it never queues behind or blocks `weekly-excel-*`;
  `permissions: contents: read`; `timeout-minutes: 60`, strictly above the
  script's 45-minute cap so the graceful stop writes the report before the
  runner is killed. Dispatch it outside the billing crons: a run that overlaps
  one shares the same 300 requests-per-minute token budget.
- **Caps (job env):** `CELL_HISTORY_BACKFILL_MAX_REQUESTS=3000`,
  `CELL_HISTORY_BACKFILL_MAX_ROWS=1200`, `CELL_HISTORY_BACKFILL_PACE_SEC=0.5`
  (120 requests per minute, 40% of the shared budget — never set it lower),
  `CELL_HISTORY_BACKFILL_MAX_MINUTES=45`. Documented in
  [Environment reference](../reference/environment.md#ownership-attribution-backfill-source-5).
- **Backlog gate:** a first step runs `--check-backlog` with only the Supabase
  secrets bound (zero Smartsheet calls): the count from the sources 1-4 report
  when present, otherwise a `LIMIT`-capped scan of `attribution_snapshot`. The
  backfill step is skipped when the count is `0`; a broken backend exits 7 and
  fails the job rather than looking like an empty queue.
- **Dry run only.** The backfill step never passes `--apply`. Dispatching with
  `dry_run=false` fails the step with an error before any call; the live write
  stays plan 12-06's human checkpoint.
- **Output:** `own03-cell-history-report-run<N>` artifact (30 days). The report
  never enters git.

:::warning Known precondition — a dispatch today is a bounded no-op
The backfill step takes candidates only from
`generated_docs/own03_backfill_report.json`, the sources 1-4 dry-run output.
That file is git-ignored and does not exist on a fresh runner, and the sources
1-4 script will not enumerate candidates without explicit `--wr` / `--weeks`
scoping. So a dispatch today passes the backlog gate, finds zero in-scope
candidates, writes an empty report with a `::warning::` annotation naming this
precondition, and exits 0 — Supabase reads only, zero Smartsheet calls. Nothing
works through the sentinel backlog unattended. This is exactly why the cron was
removed (12-04 review, Opus H1): an unattended run would have been a
permanently green no-op on the production token. Plan 12-06 owns supplying a
candidate source; until then the job is only useful when you have produced the
sources 1-4 report and can place it on the runner yourself, which no shipped
step does.
:::

## Two scripts, opposite semantics

:::danger Pitfall 4 — do not confuse the two backfill scripts
`scripts/backfill_attribution_snapshot.py` freezes **whatever Smartsheet shows
today** for a target week ("policy C", current always wins). That policy was
rejected for good on 2026-09-01 19:45.

`scripts/backfill_claim_time_attribution.py` derives the **historically correct
claimer** from the ladder above and never reads current row state.

Running the older script against a WR that the newer one has remediated
re-applies the rejected policy: it submits today's Smartsheet value for every
completed row of the week through the Supabase-resident `freeze_attribution`
RPC. That RPC's body is not in this repo, so what it does to a row that already
holds a repaired value cannot be verified here — do not rely on first-write-wins
to protect a repair. Never run `scripts/backfill_attribution_snapshot.py`
against the remediated WRs, and never use it as a shortcut when the claim-time
script reports `unresolved`: a row no source can name keeps its sentinel by
design.
:::

## After the backfill

**Component owner:** Python billing pipeline (`generate_weekly_pdfs.py`). No
operator step is needed after a successful apply.

On the next scheduled run, `resolve_claimer` finds the real frozen name for the
backfilled rows through the same bulk prefetch it already performs — no grouping
code changes, no hash reset. The group identity now carries the real name
(`_User_Avery_Example` instead of `_User_Unknown_Foreman`), so the file
regenerates under the real name and is uploaded.
In the same run the sentinel-superseded gate in `pipeline/cleanup.py` deletes
the stale placeholder attachment (`_User_Unknown_Foreman`,
`_Helper_Unknown_Helper`, `_VacCrew_Unknown_VAC_Crew`, `_User__NO_MATCH`, and
the sanitized error tokens in its allowlist) once a real-name identity for the
**same WR, same week-ending, same variant** is live and physically attached to
the row. The run summary's `sentinel_claimers_ignored` count should drop for the
backfilled WRs.

What the gate will never do (CR-01, 12-02): treat a real name whose sanitized
form starts with an underscore (`_O_Brien` from a leading apostrophe,
`_Contractor__Smith` from a leading parenthesis) as a sentinel. A leading
underscore classifies as a sentinel only when the rest of the token is in the
`_SANITIZED_ERROR_IDENTIFIERS` allowlist (`_REF_`, `_INVALID`, `_NO_MATCH`, and
the other sanitized Smartsheet error spellings); any other leading-underscore
token is neutral on both sides of the gate — never a deletion victim, never the
replacement that triggers one. The fail-safe direction is "real name, decline
to delete".

PPP attachments are never purged by any reset (owner, 2026-09-02). The backfill
deletes no attachments itself; regeneration under the real name plus the
same-week cleanup handle the stale placeholder on the target sheet.

## Rollback

**Component owner:** owner-applied SQL in the Supabase SQL editor; no repo code
performs a rollback.

Restore the affected rows from `billing_audit.attribution_snapshot_backup_<YYYYMMDD>`
— the table STEP 1 of `billing_audit/own03_backfill_attribution.sql` created on
the day of the apply. Rows the backfill touched are the ones with a non-NULL
`backfill_run_id`; restore `frozen_primary` / `frozen_helper` / `frozen_vac_crew`
from the backup for those keys and NULL out `backfill_source` /
`backfill_run_id`. Do **not** drop the backup table until the next scheduled
run has been verified (files under the expected names, `sentinel_claimers_ignored`
where you expect it, no unexpected deletions in the cleanup log). The
`backfill_attribution` RPC and `is_sentinel_value` predicate are freely
droppable; the two provenance columns are a coordinated `ALTER TABLE ... DROP COLUMN`
with the data team, not a routine rollback step.

## Who owns what

| Flow | Owner | Runs |
| --- | --- | --- |
| Resolving a row's claimer, regenerating the file, deleting the superseded placeholder attachment | Python billing pipeline — `generate_weekly_pdfs.py` via `pipeline/` (`billing_audit/writer.py`, `pipeline/cleanup.py`) | Every `weekly-excel-generation.yml` run |
| Sources 1-4 backfill (dry run, report, `--apply`) | `scripts/backfill_claim_time_attribution.py` — one-time / off-hours operator remediation | By hand, from a workstation; the live apply is plan 12-06's human checkpoint |
| Source 5 cell-history backfill | `scripts/backfill_cell_history_attribution.py` | Dry runs from `.github/workflows/cell-history-backfill.yml` (manual `workflow_dispatch`; no cron until plan 12-06) or by hand from a workstation; `--apply` only by hand under plan 12-06's checkpoint; never inside the billing run — a structural test fails if any production module calls `get_cell_history` for this feature or reads a `CELL_HISTORY_BACKFILL_*` variable |
| Backup table, provenance columns, `is_sentinel_value`, `backfill_attribution` RPC | Owner-applied from `billing_audit/own03_backfill_attribution.sql` in the Supabase SQL editor | Once per environment, by Juan; never executed by repo code |
| Rollback | Owner-applied SQL against the dated backup table | Only if the post-apply run is wrong |

Related pages: [Helper scripts](scripts.md#ownership-attribution-backfill),
[GitHub Actions workflows](workflows.md#cell-history-backfillyml),
[Environment reference](../reference/environment.md#ownership-attribution-backfill-source-5).
