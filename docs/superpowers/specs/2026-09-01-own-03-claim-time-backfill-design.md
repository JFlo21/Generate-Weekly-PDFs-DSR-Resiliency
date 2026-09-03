# OWN-03 — Claim-time attribution backfill (design)

Status: DESIGN — owner decisions applied 2026-09-02 00:35 CDT (write path = §4 option 1 RPC; source 5 cell history INCLUDED as a separate capped weekend job; no cross-week inheritance; PPP attachments never purged) · Date: 2026-09-01 · Phase 12 (Ownership) · Requirement OWN-03
Decisions this design implements: ledger `[2026-09-01 19:45]` (spec §8 #1 = claim-time /
as-of-the-week ownership per row and per role; §8 #5 = allowed sources 1–4; §5 step 2
cross-week inheritance = OFF, decided 19:55).

## 1. Goal

For every `(wr, week_ending, smartsheet_row_id)` whose frozen claimer for a role is a
placeholder (`Unknown Foreman`, `Unknown Helper`, `Unknown VAC Crew`, `#…`, blank) — 5,829
rows / 94 WRs on 2026-09-01 for the primary role alone — derive the person who actually
claimed the row **in that week** from observed history, write it back with provenance, and
let the next scheduled run regenerate the file under the real name. Nothing is inferred
across weeks. Rows that no source can name stay placeholders (and keep their sentinel file
until a real-name identity appears — PR #377 cleans the stale one up then).

## 2. What "claim time" means operationally (per row, per role)

The claim-time value for a role is the **first non-sentinel value observed on that row at
or after the moment the row became completed for that role**, where "completed" is:

| Role | Row is claimed when | Name column |
|---|---|---|
| primary | `Units Completed?` checked | `Foreman Assigned?` else `Foreman` (fetch.py effective-user rule) |
| helper | `Foreman Helping?` non-blank AND `Helping Foreman Completed Unit?` checked AND `Units Completed?` | `Foreman Helping?` |
| vac_crew | `VAC Crew Helping?` non-blank AND `Vac Crew Completed Unit?` checked AND `Units Completed?` | `VAC Crew Helping?` |
| subcontractor helper / reduced_sub / aep_billable | same as helper / primary on subcontractor sheets | same |

A later edit to the name cell on an already-claimed row is an audit event, never a
re-attribution (owner decision). A correction needs an explicit operator override record
(OWN-01 ladder, out of scope here).

## 3. Sources, in precedence order (decided)

| # | Source | Provenance tag | Covers | Notes |
|---|---|---|---|---|
| 1 | `pipeline_memory.row_event` / `row_state` — `foreman_observed`, `helper_observed`, `vac_crew_observed` with `observed_at` / `row_modified_at`, `units_completed`, `helper_completed`, `vac_completed` | `live` | weeks since Phase 10 shadow writes began (2026-08-2x) | The only source with a timestamped per-role history. Take the earliest event where the role's completed flag is true and the name is non-sentinel. |
| 2 | `billing_audit.attribution_snapshot` non-sentinel `frozen_primary` / `frozen_helper` / `frozen_vac_crew` for the SAME `(wr, week_ending, smartsheet_row_id)` | `live` (already frozen) | any week the pipeline has run | Only fills a role that is sentinel while another role on the same row is real — never rewrites a real name. |
| 3 | `public.artifacts` filenames for the same `work_request` + `week_ending`: `_User_<name>`, `_Helper_<name>`, `_VacCrew_<name>` | `backfill_artifacts` | weeks older than run memory | Group-level, not row-level: applies to a row only when the week has exactly ONE real-name identity for that role (two names in one week means we cannot say which rows were whose without source 1). |
| 4 | 2025 `hash_history.json` `foreman` field (frozen import; the file itself is retired) | `backfill_hash_history` | 2025 weeks | Group-level, same single-name rule as source 3. |
| 5 (DECIDED 2026-09-02: included) | Smartsheet cell history for the role's name column(s) + its completed checkbox — the name in effect at the timestamp the box was checked | `operator` | rows 1–4 leave unresolved, and the two-names-in-one-week conflicts 3–4 cannot adjudicate | Runs ONLY in its own workflow (`workflow_dispatch` + Saturday-midnight-Central / Sunday 05:00Z cron while a backlog exists), never inside `generate_weekly_pdfs.py`; 2–3 history requests per row; capped per run (default 3,000 requests ≈ 10 min of the shared 300 req/min budget); dry-run by default. Reuses the selective cell-history pattern in `audit_billing_changes.py`. |

Rules: (a) first source that yields a non-sentinel name for the role wins; (b) sources
3–4 are used only when 1–2 are silent for that row; (c) **no cross-week lookup in any
source** — a row's week is the `Weekly Reference Logged Date` week, and only that week's
evidence counts; (d) every written value carries its provenance so live observations and
backfills stay distinguishable (spec §8 #5 reserved the column for exactly this).

## 4. Write path (APPROVED 2026-09-02: option 1 — owner deploys the RPC; backup table first)

`freeze_attribution` is first-write-wins at row granularity and its body lives in Supabase,
so the backfill cannot go through the RPC. Proposed, in order of preference:

1. **New RPC `billing_audit.backfill_attribution(p_rows jsonb)`** (owner-deployed): for each
   input row, `UPDATE attribution_snapshot SET frozen_<role> = value, backfill_source = tag,
   backfill_run_id = run` **only where the current value is a sentinel or NULL**. Never
   touches a real name. Returns per-row `updated | skipped_real_name | skipped_no_row`.
2. Fallback: the same statement run as owner-reviewed SQL from a generated file
   (`generated_docs/own03_backfill_<date>.sql`), after a dry-run report.

Before any write: copy the affected rows to `billing_audit.attribution_snapshot_backup_<date>`
(rollback = restore from that table). Row cache (`billing_audit_row_cache`) is not touched:
rows the pipeline has already frozen stay cached; the resolver reads the corrected value on
the next run through `lookup_attribution` / `prefetch_attribution` as today.

## 5. Script shape

`scripts/backfill_claim_time_attribution.py` (new; read-only by default)

```
--wr 91234567,…      scope to WRs (default: every WR with a sentinel role)
--weeks 2026-07-05,… scope to week-endings
--roles primary,helper,vac_crew
--sources 1,2,3,4    (5 never on by default)
--dry-run            (default ON) → writes generated_docs/own03_backfill_report.json + .csv
--apply              requires --i-approved-this and the backup table to exist
```

Report per row: `wr, week_ending, row_id, role, current_value, proposed_value, source,
evidence` (event id / snapshot / artifact filename / hash-history key). Summary: rows by
source, rows still unresolved, rows with conflicting evidence (two names in the same week
from different sources — always left unresolved and listed).

## 6. Validation (before `--apply`)

- Known-good sample: ≥ 3 WRs the billing team can vouch for, including one with a mid-week
  handoff and one helper/VAC mix; the dry-run must reproduce the names they expect.
- Cross-check: for every proposed primary name, the `public.artifacts` filename for that
  WR+week (when one exists) must agree or the row is flagged.
- Nothing proposed for a row whose week has two real names from source 3/4 only.
- After apply: the next scheduled run's `sentinel_claimers_ignored` should DROP for the
  backfilled WRs (the resolver now finds a real frozen name) and their files regenerate
  under the real name; PR #377's cleanup removes the stale sentinel file in the same run.

## 7. Consequences and open items

- OWN-02's "use current" fallback remains for rows no source can name; with this backfill
  it becomes the exception rather than the rule.
- `row_event.source` / `group_state.source` already accept `backfill_artifacts`,
  `backfill_hash_history`, `operator`; `attribution_snapshot` needs a `backfill_source` /
  `backfill_run_id` column pair (owner-deployed with the RPC).
- Source 5 (cell history) is the only way to name rows from weeks before run memory whose
  artifact filename is a sentinel or missing. DECIDED 2026-09-02: included, as a separate
  capped off-hours job (see §3 row 5); zero runtime impact on the production run.
- PPP attachments are never purged by any reset (owner, 2026-09-02); the backfill never
  deletes attachments — regeneration under the real name and PR #377's same-week cleanup
  handle the stale placeholder on the target sheet.
- Not in scope: overrides of real names (OWN-01), runbook contract text (OWN-04).
