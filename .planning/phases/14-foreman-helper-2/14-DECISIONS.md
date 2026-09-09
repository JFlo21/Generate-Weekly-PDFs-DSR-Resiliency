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

## O-14-B — RESOLVED 2026-09-09 (plan 14-12, D-14-13-VERIFIED; was OPEN): `pipeline_memory.upsert_rows_bulk` does not carry the Helper #2 fields (found 2026-09-06, orchestrator review of 14-04)

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

## D-14-12-ROLLOUT (plan 14-10, Task 3) — owner decision 2026-09-08

- Decision (Juan, chat, 2026-09-08 ≈22:45Z): **documented-only** — no
  workflow wiring in this phase, no controlled upload. **Flag default stays
  off** (`HELPER2_ENABLED` default `'0'` in `pipeline/config.py`; the
  workflow does not set it), so the merge ships Helper #2 dormant; any later
  flip is its own approved change.
- Deployment instruction (same message): "i want this to roll out in
  production like right now if it is ready no testing we can debug if
  something goes wrong." Read as: merge `feat/phase-12-remediation` to
  `master` now (the production cron runs from `master`), skipping the pilot
  rehearsal's live steps; the automated gates that already ran stand as the
  evidence (full suite 2284 passed / 1 skipped / 557 subtests; ALL 6 GATES
  PASSED; website typecheck + build). The orchestrating session performs
  the push / PR / merge under this instruction.
- Live preconditions at decision time (read-only, 22:50Z): billing_audit
  `freeze_attribution` carries the per-role fill and both lookups return
  the Helper #2 columns (D-14-07 / O-14-C applied); `pipeline_memory.
  row_state` has **0** of the four D-14-08 Helper #2 columns and
  `pipeline_memory.sheet_registry` has **no** `mapping_schema` column
  (D-14-10) — neither DDL has been applied. Both absences are tolerated by
  the merged code by design: the bulk row_state RPC ignores the extra keys
  (O-14-B, values not persisted), and the mapping-schema marker degrades to
  full validation of every sheet with one warning per run (≈40 s per run
  until the column exists). Applying those two additive nullable columns is
  a separate owner call, not a merge precondition.
- Expected first-run effects after merge (not defects): one-time
  `row_event` churn of roughly one event per observed row (~217k) because
  `HASH_FIELDS` now includes the Helper #2 fields and
  `RUN_MEMORY_WRITE_ENABLED` is `'1'` in the workflow (D-14-08-APPLIED);
  full sheet validation with the mapping-schema warning; the 14-parameter
  freeze call resolving against the live function; zero Helper #2 groups,
  counters at 0, no degrade warning (flag off). Excel output is unchanged
  by design (HLP legacy byte-identity fixtures; `RUN_MEMORY_INCREMENTAL_
  ENABLED` off).
- Also carried in the same merge: Phase 12 gap-closure work (12-06 … 12-09)
  already on this branch since 2026-09-03, whose live steps (OWN-03
  backfill apply, 1,758 rows) were owner-authorized in their own records.
- Still open after the merge: O-14-B (bulk RPC Helper #2 fields) and
  O-14-A Follow-up 1 (per-slot file duplication, accepted pending Juan's
  confirmation); the Smartsheet-side preconditions (Resource Analyst
  assignment automation, Helper #2 Job producer) remain owner checklist
  items.

## D-14-13-DDL-APPLIED (plan 14-12, Task 2) — owner decision 2026-09-08

- Decision: Juan (chat, 2026-09-08 evening CDT) approved applying the two pending additive DDLs
  (D-14-08-APPLIED `row_state` helper2_* x4; D-14-10-APPLIED `sheet_registry.mapping_schema`) and
  closing O-14-B, apply delegated to the session: "do this and then enable the helper 2 once these
  issues are fixed".
- Applied 2026-09-09 02:21:29Z as Supabase migration
  `20260909022129_helper2_row_state_columns_marker_and_rpc` (one transaction): the five
  `ADD COLUMN IF NOT EXISTS` statements from `pipeline_memory/helper2_columns_migration.sql`, then the
  `upsert_rows_bulk` block of `pipeline_memory/schema.sql` at `cf556d8` verbatim (CREATE OR REPLACE on
  the unchanged signature), then the GRANT line. Run window: run 34299267004 (01:00Z slot) had
  completed; next slot 13:00Z.
- Pre-state parked in the vault raw folder: "2026-09-08 - pipeline_memory upsert_rows_bulk pre-state +
  row_state and sheet_registry columns (rollback reference, O-14-B).sql" (def md5 5987e5ed…, len 10240,
  grants service_role/postgres/PUBLIC EXECUTE, proconfig search_path="").
- Rollback: re-run that file's function body; DROP the five columns.

## D-14-13-VERIFIED (plan 14-12, Task 2) — production read-back 2026-09-09

- (a) Columns: `row_state.helper2_observed TEXT`, `helper2_completed BOOLEAN`, `helper2_dept TEXT`,
  `helper2_job TEXT`; `sheet_registry.mapping_schema TEXT` — all nullable, no default.
- (b) Function: `pipeline_memory.upsert_rows_bulk(bigint,text,jsonb)` def md5 378b3353…, len 12035,
  36 `helper2_` mentions, `SET search_path TO ''` kept; grants unchanged (PUBLIC, postgres,
  service_role EXECUTE); proconfig unchanged.
- (c) Synthetic round-trip on `sheet_id = -14012` (DB time 02:22–02:26Z): call 1 (two rows, one with
  Helper #2 values, one without the keys) returned both (wr, week_ending) pairs; row_state stored
  `Helper Two Test / true / 42 / J-99` and NULLs respectively; both row_event after_images carry the
  four helper2 keys. Call 2 (identical payload) returned 0 pairs and added 0 events. Call 3 (Helper #2
  dept 43 / job J-100, new hash) returned 1 pair; row_state updated through the ON CONFLICT set list
  (last_changed_run advanced, first_seen_run kept); third row_event = `update` carrying dept 43.
  Synthetic rows deleted afterwards (3 events + 2 state rows; 0 remain).
- Consequence: O-14-B RESOLVED; HLP-06 cached half met (14-VERIFICATION.md addendum).

## O-14-A-FOLLOWUP-1 — CONFIRMED 2026-09-08 (owner)

- Follow-up 1 (the same person as Helper #1 on some rows and Helper #2 on others within one WR/week
  produces two files, one per slot) was listed as needing written confirmation; Juan replied
  "do this and then enable the helper 2 once these issues are fixed" to that list on 2026-09-08.
  Recorded as confirmed; D-14-06's accepted consequence stands and the runbook documents it.

## D-14-14-ENABLE (plan 14-12, Task 3) — owner decision 2026-09-08

- Decision: enable Helper #2 for the scheduled workflow once the DDLs and O-14-B are fixed (Juan,
  2026-09-08: "…then enable the helper 2 once these issues are fixed"). Overrides the 14-10 runbook
  caution to wait for a real-data pilot: the Resource Analyst Helper #2 column is blank on every live
  row, so enabling changes no workbook until a crew records a second helper.
- Mechanism (as proposed in 14-10 / D-14-12-ROLLOUT): `.github/workflows/weekly-excel-generation.yml`
  "Generate reports" env gains `HELPER2_ENABLED: ${{ vars.HELPER2_ENABLED || '0' }}`; the repo
  variable `HELPER2_ENABLED` is set to `1` after PR #390 merges. Rollback = set the variable to `0`
  (no code change). The repo default in `pipeline/config.py` stays `'0'` so local and synthetic runs
  are byte-identical unless a caller opts in.
- Expected on the first enabled scheduled run: the four Helper #2 counters present in run_summary,
  `helper2_capability_unavailable` on sheets without the column family, no degrade warning, zero
  `_Helper2_` workbooks until real data appears.
- **Addendum 2026-09-09 — APPLIED.** PR #390 squash-merged to master `661d6d3` at 02:49:30Z; the repo
  variable `HELPER2_ENABLED` was set to `1` at 02:49:58Z (`gh variable set HELPER2_ENABLED --body 1`,
  confirmed with `gh variable list`). First scheduled run with the flag on: the Wed 2026-09-09 13:00Z
  slot. Flag-off (`gh variable set HELPER2_ENABLED --body 0`) is an emergency disable, not a
  billing-safe rollback once real Helper #2 claims exist — see O-14-D below. Owner instruction fully executed (DDLs applied, O-14-B closed, Follow-up 1 confirmed,
  flag enabled). Next records: the 13:00Z run check against the expectations above, then
  `/gsd-code-review 14`.
- **Addendum 2026-09-09 — FIRST ENABLED RUN OBSERVED.** Scheduled run `34356004448` (head `be60755`,
  13:16:08Z → 14:26:35Z, 70 min, conclusion success; `run_ledger` mode `full`, status `success`,
  release `@be60755`). Helper #2 expectations all met: `helper2_capability_unavailable` on the two
  Arrowhead sheets (no Helper #2 columns), `helper2_no_qualifying_completion` on every other
  capable sheet, `HELPER2 GROUP CREATED` 0, `_Helper2_` workbooks 0, no degrade warning, 130
  `freeze_attribution` RPC calls all HTTP 200, `row_state.helper2_observed` truthy rows 0. One-time
  memory churn confirmed: 115 sheets written, 218,338 rows sent, 5,451 changed, 2,929 groups
  affected, `row_event` rows for the run 218,338 (previous run: 36). Files generated 7; the 154
  no-target-row skips are identical to the previous run (source-sheet data entry, pre-existing).
  Two observations outside Helper #2: (1) the run's `Shadow parity FAIL` is the flag-off shadow
  incremental READ probe (`RUN_MEMORY_INCREMENTAL_ENABLED` unset), read verdict
  `changed_row_absent_from_delta_read` with 18 sheets abandoned after the 25-minute
  `RUN_MEMORY_SHADOW_MAX_MINUTES` budget; group verdict pass; it also fired on 2 of the 9 pre-merge
  `bc2de79` runs, so it is intermittent and pre-existing, and the 25-minute probe is what makes long
  runs long. (2) **`sheet_registry.mapping_schema` was NOT written** — see O-14-E.

## O-14-E — FIXED 2026-09-09 (plans 14-13 `d079e81` + 14-14 `736141a`), production observation pending: mapping_schema marker never written, registry skip defeated

- **Fix (plan 14-13, Juan approved 2026-09-09 "yes lets write up the fix").** `pipeline/discovery.py`
  now publishes the skip-admitted ids (`get_last_discovery_skip_sids()`, reset per call, mirrors
  `fetch.get_last_sheet_versions`); `pipeline/orchestrate.py` derives
  `_compute_registry_marker_sheets(registry_sheets, skip_sids, column_mapping_sheets)` and passes it as
  `mapping_schema_by_sheet` at BOTH `upsert_sheet_registry` call sites. Marker semantics: fully
  validated this run AND column_mapping written this call — an echoed stored mapping is never
  certified, so a frequent run cannot stamp a possibly pre-Helper-#2 mapping. Consequence: the 121
  existing sheets earn `helper2-v1` on the next `weekly_comprehensive` (Monday 05:00Z) deep run and
  are cache-admitted from then on; a brand-new sheet earns it on its first run.
  `tests/test_mapping_schema_marker_caller.py` (8 tests) pins the getter, the pure helper, both call
  sites (source pin on `orch.main`), and the marker reaching the real writer's payload.
- **Close when observed:** after the first Monday deep run, `select count(*) filter (where
  mapping_schema = 'helper2-v1') from pipeline_memory.sheet_registry` = 121 and the next frequent run
  logs `skipped via sheet_registry` ≈ 121.
- **Owner instruction 2026-09-09 (Juan): cannot wait for the Monday deep run — clear it another way.**
  SQL backfill of the marker was evaluated and REJECTED with evidence: 0 of 121
  `sheet_registry.column_mapping` values carry any Helper #2 key (the last deep run `34086148733`
  ran `6696a46`, pre-Helper-#2 code), so stamping `helper2-v1` on those rows would admit every sheet
  from cache WITHOUT Helper #2 columns and silently disable Helper #2 detection on the 114 capable
  sheets. Juan chose the code change: **plan 14-14** — a frequent run also writes the freshly
  validated mapping (and, through 14-13's marker helper, the marker) for every sheet it fully
  validated this run, with the deep run's drift log + breadcrumb fired per adopted sheet (label
  `Frequent-run full-validation`). Phase 11 D-03's "never silently adopt a drifted mapping" is kept
  in spirit: adoption requires a full validation this run and is logged. Skip-admitted sheets still
  echo their stored mapping unmarked. Expected: the first scheduled run after the 14-14 merge stamps
  all 121 sheets and writes Helper #2-aware mappings (keys present on the 114 capable sheets; the 7
  capability-unavailable sheets may lack them); the run after that skips ≈ 121 via the registry.
  Plan 14-14 merged `736141a` (PR #396, 2026-09-09 22:17Z) after three bot review rounds: the
  frequent-run drift log moved into pass 1 BEFORE the first registry write (an early no-data exit can
  no longer adopt silently), an ordering pin test guards that placement, and the marker/writer
  docstrings plus the closing condition above were aligned.
  First run on the 14-13 merge (`34393726548`, `cbff797`) was clean: both registry upserts 200, 0
  skipped as expected, counters unchanged (114 capable / 7 unavailable), no tracebacks.
- Original record (kept for traceability):

- Expected on the first enabled run: one full validation per sheet, then the `helper2-v1` marker
  written so later runs are admitted from cache again (D-14-10-APPLIED). Observed: all 121 sheets
  fully validated (`Discovery validation split: 121 candidates, 0 skipped`), `sheet_registry` rows
  updated (`last_full_read_at` = run time on all 121, `column_mapping` present on all 121), but
  `mapping_schema` is NULL on all 121 rows after the run.
- Root cause (verified in code 2026-09-09): plan 14-07 added the `mapping_schema_by_sheet` kwarg to
  `pipeline_memory/writer.py::upsert_sheet_registry` and pinned it with `MappingSchemaMarkerWriterTests`,
  but neither call site in `pipeline/orchestrate.py` (pass 1 and pass 2) passes it, so the writer's
  default omits the marker for every sheet. `pipeline/discovery.py`'s sixth admission condition then
  rejects every sheet (NULL ≠ `helper2-v1`) on every run. The 14-VERIFICATION gate tested the writer,
  not the caller.
- Impact: the D-11.1-01 registry-version skip is permanently defeated on every scheduled run — all
  121 sheets take a full column validation every run (about 38 s and 121 column-metadata API calls
  in run `34356004448`, 13:16:45Z → 13:17:23Z). Slower but correct, exactly the D-14-10 degrade
  direction. No billing, grouping, attribution, or Helper #2 detection impact.
- Proposed fix (plan 14-13, needs owner approval — production Python in `pipeline/`): at both
  `upsert_sheet_registry` call sites pass `mapping_schema_by_sheet={sid: MAPPING_SCHEMA_MARKER for sid
  in <sheets that completed full validation this run>}`, with a caller-level test that asserts the
  marker reaches the payload for a fully-validated sheet and is omitted for a cache-admitted one, then
  confirm on the next scheduled run that `skipped via sheet_registry` returns to ~121 and
  `mapping_schema = 'helper2-v1'` on all rows.

## O-14-D — RESOLVED 2026-09-09: flag-off re-routes rows that carried a Helper #2 claim

- **Resolution (Juan, 2026-09-09, option (a) — accept).** Helper #2 is a permanent production
  capability, not a one-time backfill: a crew can record a second helper in any week, so
  `HELPER2_ENABLED` stays at `1` indefinitely. The flag exists only as an emergency kill switch
  (stop the Helper #2 path in one command without a code rollback); there is no planned or scheduled
  flag-off. Option (b) persisted-claim routing would change protected grouping behaviour for a
  scenario the owner never intends to trigger, and option (c) would reverse D-14-12's
  evidence-retention choice — both declined. Accepted rollback behaviour: if an emergency disable
  ever happens with real Helper #2 claims present, rows regroup into the primary / Helper #1
  workbook while the retained `_Helper2_` attachment stays, and the operator reconciles by hand per
  the runbook Rollback section. No code change; docs updated to reflect the closure.
- Original record (kept for traceability):

- Raised by Greptile (P1) and Copilot on PR #391 against the "rollback = set the variable to `0`"
  wording; verified in code 2026-09-09: with `HELPER2_ENABLED` off, `pipeline/fetch.py` sets
  `__is_helper2_row = False` on every row, `pipeline/grouping.py` then computes
  `valid_helper2_row = False`, so a row that also carries "Units Completed?" (dual-checkbox) or a
  Helper #1 claim is emitted to the primary / Helper #1 group on the next run. Cleanup keeps the
  existing `_Helper2_` attachment by design (D-14-12 rollback protection,
  `tests/test_sentinel_superseded_cleanup.py::Helper2RollbackProtectionTests`), so the same unit can
  appear in two workbooks until reconciled by hand. Frozen `billing_audit` attribution is unaffected.
- Impact today: none — no live row carries a Helper #2 claim (Resource Analyst Helper #2 column blank
  on all 576 rows at enablement), so flipping the flag either way changes no workbook.
- Docs corrected in PR #391 (no code change): runbook Rollback section, environment reference,
  project-state, ledger, and the D-14-14-ENABLE addendum now call flag-off an emergency disable.
- Owner decision needed: (a) accept the limitation and reconcile by hand if the flag is ever turned
  off with real Helper #2 data present; (b) add persisted-claim routing — keep a row on its Helper #2
  route while the flag is off when `pipeline_memory.row_state.helper2_*` /
  `billing_audit.attribution_snapshot` show a prior Helper #2 claim (a grouping behaviour change that
  needs its own plan and fixtures); or (c) on disable, also retire the retained `_Helper2_`
  attachments (reverses D-14-12's evidence-retention choice).
