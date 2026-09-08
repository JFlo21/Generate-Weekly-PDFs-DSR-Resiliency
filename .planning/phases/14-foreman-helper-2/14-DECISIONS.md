# Phase 14 Decisions — Owner-Confirmed Live State

Companion to `14-CONTEXT.md` (D-14-xx locked decisions) and `14-PENDING-RESOLUTIONS.md`
(repository-answered gaps A1–A3). This file records only what a read-only look at live
Smartsheet showed. It is OWNER-OBSERVED LIVE STATE, never a dry-run pass and never a
production observation of Helper #2 behavior.

## LIVE-COLUMN-PROBE (plan 14-02, Task 3)

- Observation date: 2026-09-06
- Method: read-only column-metadata reads through the Smartsheet connector, delegated by
  the owner in-session ("Run the probe read only"). Zero writes. No column provisioning,
  no formula repair, no sheet reconnection, no row values read, no person's name recorded.
- Recorded: column titles, column ids, sheet counts, column counts, and one row-count
  filter result. Picklist option lists were returned by the API and deliberately NOT
  recorded.
- Drift versus the 2026-09-05 snapshot in `14-CONTEXT.md`: none observed.

### Q1 — Main ProMax `3239244454645636` carries all six Helper #2 titles

82 columns total. All six exact titles present:

| Title | Column id |
|---|---|
| `Foreman Helping? #2` | `7936189613248388` |
| `Foreman Helper #2 Active?` | `617840218771332` |
| `Helping Foreman #2 Completed Unit?` | `5121439846141828` |
| `Helper #2 Dept #` | `2869640032456580` |
| `Helper #2 Job [#]` | `7373239659827076` |
| `Foreman Helper #2 Email` | `289083157155716` |

Answer: YES, still 6/6.

### Q2 — Does any Intake or ProMax Database sheet carry a PARTIAL Helper #2 set?

Full sweep, every sheet in both folders plus the Resource Analyst sheet:

| Scope | Sheets | 6/6 (FULL) | 0/6 (NONE) | 1–5/6 (PARTIAL) |
|---|---|---|---|---|
| Intake folder `8815193070299012` | 11 | 10 | 1 (Intake ProMax 8) | 0 |
| ProMax Database folder `7644752003786628` (Main, `(NEW)` `277473162907524`, Backups 2–104) | 105 | 104 | 1 (Backup 2) | 0 |
| Resource Analyst `3733355007790980` | 1 | 0 | 1 (not a pipeline data source; see Q4) | 0 |
| Total | 117 | 114 | 3 | 0 |

Answer: NO partial set exists anywhere. The capability-unavailable case that plan 14-07's
fixtures must cover has no live analog today; the fixture stays synthetic (D-14-01 shape:
Helper #1 columns present, Helper #2 columns absent). Column counts observed: 72–79 on
backups, 78 on the intake sheets, 82 on Main.

### Q3 — Intake ProMax 8 `2244739192541060` and Backup 2 `2230129632694148`

| Sheet | Columns | Helper #2 titles present |
|---|---|---|
| Intake ProMax 8 `2244739192541060` | 78 | 0/6 |
| Resiliency Promax Database Backup 2 `2230129632694148` | 72 | 0/6 |

Answer: confirmed, still no Helper #2 columns. Recorded as ACCEPTED STATE under D-14-01.
Not a defect. Not work. Nothing to provision.

### Q4 — Resource Analyst `Foreman Helper #2` (column id `1589780186173316`)

- Sheet `3733355007790980`: 239 columns, 576 rows.
- Column `Foreman Helper #2` id `1589780186173316`, type PICKLIST, present.
- Row-count check: filter `Foreman Helper #2 IS_NOT_BLANK`, projected onto a single
  checkbox column so no name or value was returned. Result: `rowsInFilter = 0`.
- The sheet also carries four Helper-2-adjacent titles that are NOT the six pipeline
  titles (titles and ids only): `Assigned Helper 2?` `1303443306483588`,
  `Foreman Helping #2` `8426301807693700`, `Work Request Helper 2` `4314485728432004`,
  and `Foreman Helper #2` `1589780186173316` above. None of the six pipeline titles
  exist on this sheet, which is expected; it is not a billing data source.

Answer: BLANK ON EVERY ROW (0 of 576 non-blank).

### Markers

LIVE-COLUMN-PROBE: ANSWERED — observed 2026-09-06, read-only.

Pilot-mode consequence: FIXTURE-ONLY. Plan 14-10's pilot must state it ran over fixtures
and must not claim a dry-run over real Helper #2 rows, because no real Helper #2 row
exists on the Resource Analyst sheet as of 2026-09-06.

### Plan consequences carried forward

- 14-07: capability-unavailable fixture remains synthetic; no partial-set fixture is
  required by live evidence (add one only as a defensive shape, not as an observed one).
- 14-10: pilot is fixture-only; re-run this probe (read-only) before any claim of a
  dry-run over real Helper #2 data.
- 14-01 detection guard (`HELPER2_ENABLED` default `'0'`) is consistent with 114/117
  sheets already carrying the full column set: the flag, not column presence, gates
  behavior.

## D-14-08-APPLIED (plan 14-04, Task 1) — owner decision 2026-09-06

- Decision: **include-now** — Juan approved the four additive nullable
  `pipeline_memory.row_state` columns AND their membership in `HASH_FIELDS`
  in the same change (D-14-08 recommended option).
- Columns (additive, nullable, no key/index/constraint/data migration):
  `helper2_observed TEXT`, `helper2_completed BOOLEAN`, `helper2_dept TEXT`,
  `helper2_job TEXT`. Rollback = drop four unused columns.
- Who applies the DDL: Juan (owner), by hand, in Supabase project
  `poeyztlmsawfoqlanucc` via the SQL Editor. No agent applies DDL.
  **Not applied as of 2026-09-06** (live read-only check: 0 `helper2_*`
  columns on `row_state`).
- Sequencing: either order is safe by design and Task 2 must PROVE both —
  old code ignores the new columns; new code must write every other
  `row_state` field when the columns are absent. Juan did not fix the
  timing in this decision; it is his call at rollout (plans 14-09/14-10)
  and is not a precondition for Task 2 or Task 3.
- Expected one-time churn (live read-only figures, 2026-09-06):
  `row_state` = 217,491 rows, `row_event` = 218,931 rows, 58 runs in
  `run_ledger`. Because the weekly workflow has carried
  `RUN_MEMORY_WRITE_ENABLED: '1'` since PR #353 (2026-08-26), the first
  scheduled run after the `HASH_FIELDS` change lands will emit roughly one
  `row_event` per observed row (~217k) — real production writes, NOT
  shadow-only as the plan text assumed. `RUN_MEMORY_INCREMENTAL_ENABLED`
  stays OFF, so the burst changes no Excel output and triggers no
  regeneration; it is a write-volume and run-time cost only.
- Parity: the 14-02 parity finding still holds — the shadow comparator
  hashes within a single run and never reads stored hashes, so the burst
  cannot disturb a parity streak.
- No DDL was executed from this session.

## O-14-B — OPEN: `pipeline_memory.upsert_rows_bulk` does not carry the Helper #2 fields (found 2026-09-06, orchestrator review of 14-04)

- Plan 14-04 added `helper2_observed / helper2_completed / helper2_dept /
  helper2_job` to the `row_state` DDL (`pipeline_memory/schema.sql`
  ~129-132), to the Python payload, and to `HASH_FIELDS` (D-14-08-APPLIED,
  include-now). It deliberately did NOT touch the `upsert_rows_bulk` RPC
  body (typed `jsonb_to_recordset` column list, INSERT list, ON CONFLICT
  set list, and the row_event change JSON around schema.sql ~264-380),
  which still names only the Helper #1 fields.
- Consequence if left as is: the RPC silently ignores the four extra JSON
  keys, so the columns stay NULL forever; the one-time ~217k row_event
  hash churn is still paid on the first run after merge, and no 42703
  error ever fires because nothing references the columns. This is the
  silent-no-op shape Phase 14 exists to avoid.
- 14-04's SUMMARY says the RPC update is "deferred to 14-09/14-10"; no
  plan file (14-07..14-10), 14-CONTEXT.md, or 14-RESEARCH.md mentions
  `upsert_rows_bulk`. The deferral has no owner plan today.
- Orchestrator recommendation (Juan may override): close it as a
  gap-closure plan after phase execution (`/gsd-verify-work 14`), scoped
  to: additive RPC column-list update as SQL TEXT in `schema.sql` (never
  executed by an agent), a source-pin test that the RPC list and
  `HASH_FIELDS` stay in lockstep, and an owner-applied checkpoint. Apply
  the RPC update in the SAME owner SQL session as the row_state DDL and
  BEFORE the code merges, so the first (churn) run after merge also
  persists Helper #2 values instead of paying the burst for nothing.
- Until closed: no plan, summary, or pilot may claim that Helper #2 run
  memory persists. HLP-06 stays Pending.

## D-14-10-APPLIED (plan 14-07, Task 1) — owner decision 2026-09-06

- Decision: **separate-column** — one additive nullable TEXT column on
  `pipeline_memory.sheet_registry`. `column_mapping` stays a pure
  column-title-to-column-id map.
- Column name: `mapping_schema TEXT NULL`. A NULL means the mapping was
  written before the marker existed and is therefore NOT admissible from
  cache; that sheet takes one full validation, after which the upsert
  writes the current marker.
- Marker value: `helper2-v1`, held in a module-level constant in
  `pipeline/discovery.py` (`MAPPING_SCHEMA_MARKER`). Bumping the constant is
  the mechanism a future synonym addition uses to force exactly one more
  revalidation.
- Sixth skip-index admission condition: `mapping_schema` must equal the
  current marker. Null or stale → not admitted. A sheet admitted from cache
  never has its marker promoted; only a full validation earns it.
- Degrade direction (owner-confirmed: "slower but correct is correct"):
  if the watermark select fails specifically because the column does not
  exist, log once, treat every mapping as unmarked, run full validation for
  every sheet, never raise, never admit from cache.
- One-time cost (measured, not estimated): full validation is one bounded
  three-row `get_sheet` per sheet, ~0.3 s/sheet since 11.1-04 —
  121 sheets = 37.7 s of Phase 1 on the production canary run 33683979474.
  Recent runs take 32–55 min against the 165-min `TIME_BUDGET_MINUTES`
  (180-min runner ceiling), so the first run after the marker lands fits
  with ample headroom. The pre-11.1-04 figure (54–83 min) no longer applies.
- Who applies the DDL: Juan (owner), by hand, in Supabase project
  `poeyztlmsawfoqlanucc` via the SQL Editor. **Not applied as of
  2026-09-06** (live read-only check: `sheet_registry` has 121 rows, all with
  a `column_mapping`, columns: sheet_id, name, kind, folder_id,
  column_mapping, last_sheet_version, last_read_at, last_full_read_at,
  active, updated_at — no marker column).
- Sequencing: either order is safe by design and Task 2 proves both (old
  code ignores the column; new code degrades to full validation when it is
  absent). Recommended: apply this column together with the 14-04
  `row_state` DDL and the O-14-B RPC update in one owner SQL session before
  the code merge.
- No DDL was executed from this session.

## O-14-A RESOLVED (plan 14-08, Task 1) — owner decision 2026-09-07

- Decision: **helper2-wins** — an owner-defined fifth option, not one of
  the four the plan listed (`hold`, `helper1-wins`, `both-files`,
  `primary-keeps`). Juan's rule, in his own terms: "if helper 1 & helper 2
  both claim the row, helper 2 should get the production and helper 1
  would not; if helper 1 claims the row and the primary foreman also
  claims the row, that row goes to helper 1's file, not the primary
  foreman's file."
- Precedence chain for one physical unit on one source row:
  **Helper #2 > Helper #1 > primary foreman.** The helper-over-primary
  half is existing behavior (rows with both "Helping Foreman Completed
  Unit?" and "Units Completed?" checked already appear only in the helper
  file, never the main file); the Helper #2-over-Helper #1 half is new and
  is the O-14-A rule.
- Rationale (one sentence, owner's terms): the second helping-foreman slot
  is the later, more specific claim on the unit, so it takes the
  production credit, and a claim that loses is never billed twice.
- Implementation reading (orchestrator; Juan may correct): the conflicted
  row is treated as a Helper #2 row for EVERY flow — internal production
  credit (Helper #2's file shows the line item), subcontractor payment
  (the Helper #2 shadow file, never the Helper #1 shadow file), and
  customer billing (exactly one customer-facing file). The Helper #1 claim
  on that row is dropped for that row only, never silently: it is logged
  once with a distinct reason, counted in the run summary, and sent to
  Sentry.
- Visibility (owner-answered): the conflict signal reaches **Sentry AND
  the run summary**. The Sentry event carries WR, week ending, sheet id,
  and counts only — never a person's name or any row value (PII rule,
  `pipeline/observability.py` `before_send_log` backstop, `_PII_LOG_MARKERS`).
- Rejected regardless: the 2026-07 prototype's abort-before-workbook
  behavior. One conflicted row never stops a production billing run.
- Follow-up 1 (per-slot file duplication: same person in slot 1 on some
  rows and slot 2 on others within one WR/week) — NOT answered in this
  decision; D-14-06's accepted consequence (two files, one per slot) stands.
  Documentation-only, non-blocking; confirm with Juan before the 14-10
  rollout notes are finalized.
- No conflict-handling code existed before this record.

## D-14-07-APPLIED (plan 14-09, Task 2) — owner decision 2026-09-08

- Decision (Juan, chat, 2026-09-08 ≈16:10Z): **sql-first**, and the apply was
  delegated to the Claude session over the Supabase MCP connection ("do sql
  first but apply it yourself through the supabase connection"). This is an
  owner-authorized deviation from the plan's acceptance criterion "No SQL was
  executed from an agent session" and from threat T-14-09-05; the authority
  stayed with Juan, the hands were the session's.
- Applied: **2026-09-08 16:55:11Z** on project `poeyztlmsawfoqlanucc` as
  Supabase migration `20260908165511_helper2_attribution_columns_and_rpcs`
  (single transaction: STEP 1 columns, STEP 2 freeze_attribution drop +
  create + grants, STEP 3/4 both lookups drop + create + grants, NOTIFY
  pgrst). The applied text is the repo file's intent with three deviations
  that preserve the LIVE definitions read back beforehand:
  (a) `freeze_attribution` keeps its deployed positional order (`p_pole`,
  `p_cu`, `p_work_type` precede the role parameters) and the two new
  parameters are appended LAST — Postgres rejects a non-defaulted parameter
  after a defaulted one, so the repo template's mid-list placement could not
  have compiled; PostgREST binds by name, so the writer is unaffected.
  (b) Both lookups keep their deployed pinned `search_path`
  (`billing_audit, public, extensions, pg_temp`), which the repo CREATEs
  omitted; `freeze_attribution` keeps `search_path = ''`.
  (c) The deployed `freeze_attribution` body is per-ROW first-write-wins
  (`ON CONFLICT (wr, week_ending, smartsheet_row_id) DO NOTHING`), not
  per-role as the file's D-12-A note assumes. The splice adds
  `frozen_helper2`/`frozen_helper2_dept` to the INSERT list only and changes
  nothing else. Consequence: a row frozen before the merge never gains a
  Helper #2 value — see O-14-C below.
  The repo file and `schema.sql` were aligned to (a) and (b) in the same
  commit as this record; the contract test still passes.
- Window: intended gap after run 34243784963 (completed 16:49:55Z; nothing
  queued at 16:50:27Z). In fact run 34253845749 was created at 16:53:55Z, so
  the transaction landed ≈75 s into that job's checkout/setup, before the
  pipeline reaches discovery, fetch, grouping, or any billing_audit call.
  Recorded as-is; the intended discipline was a run-free gap.
- Deployment order: SQL first (this record); code merge of
  `feat/phase-12-remediation` still pending. Until the merge, the deployed
  12-parameter writer keeps resolving the RPC (proved below) and writes
  `frozen_helper2` = NULL.
- Pre-state (16:10Z): 222,260 snapshot rows; all three functions owned by
  `postgres`; EXECUTE grants — freeze: anon, authenticated, PUBLIC, postgres,
  service_role; both lookups: PUBLIC, postgres, service_role. Grants were
  re-applied identically (verified post-apply). No triggers on the table; no
  dependent objects on any of the three functions.
- Rollback (no data destroyed by the migration): DROP the 14-parameter
  `freeze_attribution`, the 7-column `lookup_attribution`, and the 10-column
  `lookup_attribution_bulk`; re-run the three pre-state `CREATE OR REPLACE`
  statements and the grant list captured verbatim in the vault at
  `raw/2026-09-08 - billing_audit Helper #2 attribution migration pre-state
  (rollback reference).sql`; optionally `ALTER TABLE ... DROP COLUMN
  frozen_helper2, DROP COLUMN frozen_helper2_dept`; `NOTIFY pgrst, 'reload
  schema'`. Do it in a run-free window.

## D-14-07-VERIFIED (plan 14-09, Task 3) — read-back 2026-09-08

Observed by the Claude session over the Supabase MCP connection under the
owner delegation above (label: OWNER-DELEGATED PRODUCTION READ-BACK).
**Co-signed by Juan 2026-09-08 ≈20:05Z** (chat: "i approve the
d-14-07-verified"); plan 14-09 closed in `a2de0de`.

1. **Both lookups return the Helper #2 columns** (16:56Z): on real row
   WR 91015112 / week ending 2026-09-13 / row 686440379514756 (frozen by run
   34243784963), `lookup_attribution` returned 7 keys and
   `lookup_attribution_bulk` (16 rows for that WR/week) returned 10 keys —
   `helper2` and `helper2_dept` PRESENT with null values, not absent.
   `pg_get_function_result` confirms both RETURNS TABLE shapes.
2. **Table has both columns** (16:56Z): `frozen_helper2` (ordinal 17) and
   `frozen_helper2_dept` (ordinal 18), TEXT, nullable.
3. **Helper #2 freeze leaves the other role columns byte-identical**
   (16:59–17:03Z), on synthetic key WR `ZZ-HELPER2-VERIFY` / 2000-01-01
   (cannot exist in Smartsheet), rows 1 and 2, all deleted afterwards
   (count 0 confirmed, total back to 222,260): the deployed writer's
   12-argument named call froze row 1 (`frozen_helper2` NULL) — the DEFAULT
   NULL compatibility holds; a 14-argument call froze row 2 with
   `frozen_helper2`/`frozen_helper2_dept` written; a second 14-argument call
   on row 1 with DIFFERENT primary, helper, helper_dept, and vac_crew
   returned the original row unchanged — same values and the same
   `frozen_at` (16:59:51.275279Z) — and left `frozen_helper2` NULL (per-row
   first-write-wins, deviation (c)). Both lookups returned both rows with
   the new columns.
4. **Next real run** — run 34253845749 (deployed master code, 12-parameter
   writer; created 16:53:55Z, completed success 17:49:53Z) ran entirely
   against the migrated functions. OBSERVED 17:55Z: 74 `freeze_attribution`
   calls, all HTTP 200, 0 non-200, 0 `PGRST` codes in the job log; 6
   `lookup_attribution_bulk` calls, all 200, and the frozen-row cache
   warm-started 221,616 keys from the new 10-column shape; the 74 rows it
   froze (17:23:09–17:25:23Z, `source_run_id` `34253845749.*`) all carry a
   primary and `frozen_helper2` NULL, exactly what the 12-parameter writer
   must produce. The plan-14-03 degrade-warning check ("no Helper #2
   capability-degrade warning") can only be observed after the branch
   merges, because the deployed writer predates Phase 14 entirely; it stays
   PENDING-UNTIL-MERGE and must be confirmed on the first post-merge run.

Assumption A4 (14-RESEARCH.md): CLOSED by observation for the contract the
plan asked about — a Helper #2 freeze never alters `frozen_primary`,
`frozen_helper`, or `frozen_vac_crew`. Caveat recorded as O-14-C.

## O-14-C — RESOLVED 2026-09-08 (plan 14-11): existing snapshot rows never gained Helper #2 attribution (found 2026-09-08 at the 14-09 apply)

The deployed `freeze_attribution` was per-row first-write-wins. Every row
frozen before the merge (222,260 as of 16:10Z) kept `frozen_helper2` NULL
forever; only rows first seen after the merge carried Helper #2. Options
presented: (1) accept; (2) a per-role fill in the function; (3) a one-off
backfill. **Juan: "work on O-14-C before building out plan 10"** → option
(2), scoped to Helper #2 only, plus the pipeline admission rule it needs
(the freeze loop never re-sent frozen rows), delivered by inserted plan
14-11 (`57144a9`, `c30d8ed`, `0bb018b`) and applied per `O-14-C-APPLIED` /
`O-14-C-VERIFIED` below. A backfill was moot: Helper #2 is blank across
production today, so there was nothing historical to fill.

## O-14-C-APPLIED (plan 14-11, Task 3) — owner decision 2026-09-08

- Decision (Juan, chat, 2026-09-08 ≈20:05Z): **apply-delegated** ("i
  approve the d-14-07-verified & apply-delegated"). Applier: the Claude
  session over the Supabase MCP connection, as for D-14-07-APPLIED.
- Pre-state captured 20:11Z (read-only): the post-14-09 body (per-row `DO
  NOTHING`), identity args unchanged, `search_path = ''`, EXECUTE grants
  anon / authenticated / PUBLIC / postgres / service_role, 222,465 snapshot
  rows, 0 synthetic rows. Parked verbatim in the vault at `raw/2026-09-08 -
  billing_audit freeze_attribution pre-fill body (rollback reference,
  O-14-C).sql`.
- Run state at apply time: `gh run list` at 20:10:59Z — no run in progress
  (34267721160 completed 20:07:03Z; next cron slot 21:00Z). A run-free gap,
  as the plan required.
- Applied: **2026-09-08 20:12:05Z** as Supabase migration
  `20260908201205_helper2_attribution_per_role_fill` — the STEP 2 statement
  of `billing_audit/helper2_attribution_fill.sql` verbatim (CREATE OR
  REPLACE on the identical 14-parameter signature; only change: `ON
  CONFLICT … DO NOTHING` → gated `DO UPDATE` of `frozen_helper2`,
  `frozen_helper2_dept`, and `backfill_provenance.helper2 = {source: live,
  run_id}` where `is_sentinel_value(s.frozen_helper2)` and `NOT
  is_sentinel_value(EXCLUDED.frozen_helper2)`), then `NOTIFY pgrst`.
- Post-apply shape (20:24Z): definition contains `DO UPDATE` and the gate,
  no `DO NOTHING`; identity args, `search_path`, and grants identical to the
  pre-state.
- Rollback: re-run the pre-fill body from the vault file above (same
  signature, no window needed), then `NOTIFY pgrst, 'reload schema'`. No
  data is destroyed by the fill; it only writes into null/sentinel Helper #2
  columns.
- Deviation from the plan's original phase wording ("no SQL from an agent
  session"): owner-authorized, second occurrence, recorded here as with
  D-14-07-APPLIED.

## O-14-C-VERIFIED (plan 14-11, Task 3) — production read-back 2026-09-08

Synthetic key WR `ZZ-HELPER2-VERIFY` / week 2000-01-01 (cannot exist in
Smartsheet), rows 1 and 2; PRODUCTION READ-BACK by the delegated session;
all rows deleted at the end.

1. **12-argument call, row 1** (20:25:09.70Z, the deployed writer's shape):
   row created with primary / helper / dept, `frozen_helper2` NULL,
   `backfill_provenance` NULL, `source_run_id` `verify-run-1`.
2. **14-argument call, row 1, Helper #2 present and EVERY other value
   different** (pole, cu, work_type, primary, helper, dept, vac_crew,
   release, run id `verify-run-2`): FILL observed — `frozen_helper2` =
   `Verify Helper2`, `frozen_helper2_dept` = `DEPT-H2`,
   `backfill_provenance` = `{"helper2": {"source": "live", "run_id":
   "verify-run-2"}}`; every other column byte-identical to observation 1,
   including `frozen_at` 20:25:09.701053Z, `source_run_id` `verify-run-1`,
   `source_release`, pole/cu/work_type, and `backfill_source` /
   `backfill_run_id` still NULL.
3. **14-argument call, row 1, a DIFFERENT Helper #2** (`verify-run-3`):
   REFUSED — row returned unchanged, `frozen_helper2` still `Verify
   Helper2`, provenance still names `verify-run-2`. First-write-wins per
   role holds.
4. **14-argument call, row 2 (fresh key)** (20:25:12.64Z): a new row with
   Helper #2 written and `backfill_provenance` NULL — the insert path is
   untouched; provenance is stamped only by a fill.
5. **Read-back and cleanup**: `lookup_attribution` returned both rows with
   `helper2` / `helper2_dept` populated; `lookup_attribution_bulk` returned
   2 rows; DELETE removed 2 rows; count of synthetic rows afterwards 0
   (re-confirmed 21:51Z, total 222,587 with 0 rows carrying a `helper2`
   provenance entry — no real row has been filled yet, as expected before
   the merge).

Timestamps: observations 1 and 4 carry the database's `frozen_at`
(20:25:09.70Z, 20:25:12.64Z). Observations 2, 3, and 5 followed in the same
sequence; their wall-clock times were not captured. Scheduled run
34279298559 started 21:12:46Z, after the apply and after the synthetic
writes began; a synthetic WR cannot collide with any real row, and the
replace was a same-signature CREATE OR REPLACE, so that overlap carries no
risk, but it is recorded here rather than implied away.

Consequence for the pipeline: with plan 14-11 Task 1 merged, a row frozen
before a Helper #2 appeared on it is re-sent once, filled once, counted as
`snapshots_helper2_filled`, and never touched again for that role. Until
the merge, the deployed 12-parameter writer never satisfies the gate
(observation 1), so today's behaviour is unchanged.

## 14-10-PILOT-REHEARSAL (plan 14-10, Task 2) — rehearsed 2026-09-08

Rehearsal of the pilot in escalating order, `HELPER2_ENABLED` unset (off,
default `'0'`) for both steps run. Full procedure, comparison criteria, and
the per-command flag-consumption reading are on
`website/docs/runbook/foreman-helper-2.md` ("The pilot: rehearsed in
escalating order"). Evidence labels used exactly as defined — never merged.

- **Step 1 — fixtures — EVIDENCE: fixture pass.** `python -m pytest tests/ -q`
  → 2284 passed, 1 skipped, 557 subtests, 42.74s. Reads nothing, writes
  nothing, no token.
- **Step 2 — synthetic mode — EVIDENCE: dry-run pass over synthetic data.**
  `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python
  generate_weekly_pdfs.py` → synthetic in-memory dataset (14 raw rows, 2
  groups), no live Smartsheet read, no Supabase write (`billing_audit` freeze
  and `pipeline_memory` writes are both gated off by `TEST_MODE`), no
  attachment cleanup (`TEST_MODE` short-circuits both the sheet-attachment
  pruning and the remote purge). `generated_docs/run_summary.json` written
  with all 30 baseline keys, all four Helper #2 counters
  (`helper2_capability_unavailable_sheets`,
  `helper2_no_qualifying_completion_sheets`, `helper2_conflict_hold`,
  `helper2_groups_generated`) present and zeroed. `python
  scripts/check_run_summary_structure.py` PASS (30 keys); `bash
  scripts/run_6_gates.sh` PASS (all 6 gates).
- **Step 3 — upload-suppressed, filtered WRs — NOT RUN — no
  credentials/authorization.** As of this record, this file carries no dated
  owner authorization for this specific rehearsal step, so condition (a) of
  the plan's gate is unmet and the step was not run. Independently — the
  flag-consumption reading (recorded in the runbook page) found that
  `SKIP_UPLOAD` does **not** disable the `billing_audit.freeze_attribution`
  write path (gated only by `BILLING_AUDIT_AVAILABLE and not TEST_MODE`, with
  no flag to suppress it), so condition (b) — "no Supabase writes, or every
  such path disabled by the flags in force" — would also not be satisfiable
  by this command as written, independent of authorization. Also independently
  — `LIVE-COLUMN-PROBE` (above) found the Resource Analyst `Foreman Helper #2`
  column blank on all 576 rows as of 2026-09-06, so even an authorized run
  would have no real Helper #2 row to scope to. **Record: fixture-only** — no
  real-data pilot coverage exists for Helper #2 as of this rehearsal.
- **Step 4 — controlled upload — NOT RUN.** Requires the Task 3 owner
  authorization below; never run by an agent.

Overall evidence reached by this plan: **fixture pass** and **dry-run pass
over synthetic data**. Neither **controlled upload verified** nor
**production observed** was reached.
