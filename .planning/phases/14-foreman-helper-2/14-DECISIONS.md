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
