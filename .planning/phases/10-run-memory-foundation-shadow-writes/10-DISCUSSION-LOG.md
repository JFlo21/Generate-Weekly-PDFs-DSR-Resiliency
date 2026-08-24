# Phase 10: Run-Memory Foundation (shadow writes) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-08-24
**Phase:** 10-run-memory-foundation-shadow-writes
**Areas discussed:** Where the memory lives (#2 + #5), How long history is kept (#3), Safety net + MEM-04 proof (#4)
**Mode:** advisor (USER-PROFILE present; Vendor Philosophy `conservative` -> calibration tier `full_maturity`; Learning Style `guided` -> NON_TECHNICAL_OWNER=true, outcome-first framing). Three parallel `gsd-advisor-researcher` (sonnet) packets synthesized before each table. Area offered but not selected: "Shadow rollout posture" (recorded as Claude's discretion in CONTEXT.md).

---

## Where the memory lives (#2)

| Option | Description | Selected |
|--------|-------------|----------|
| New `pipeline_memory` schema | Isolated from protected billing_audit tables; one extra PostgREST exposed-schema + reload-cache step (known PGRST106 runbook); own service-role-only RLS | ✓ |
| Extend `billing_audit` | No exposure step; reuse sibling RLS/grant boilerplate; group_state could replace group_content_hash in place; DDL blast radius next to protected tables | |
| `public` with `pm_` prefix | Exposed by default; shares portal namespace; needs explicit REVOKE per table to keep internal state from anon/authenticated | |
| Separate Supabase project | (researched, not offered) Rejected by Phase 03 D-01; doubles secrets + setup for no isolation gain over a new schema | |

**User's choice:** New `pipeline_memory` schema
**Notes:** Research established that `billing_audit/writer.py` already uses per-call `client.schema("billing_audit")`, so a second schema is a proven one-string pattern. `group_content_hash` supersession deferred to Phase 11+.

## Provenance column (#5, reservation only)

| Option | Description | Selected |
|--------|-------------|----------|
| `source` enum + `source_ref` | `source text NOT NULL DEFAULT 'live'` CHECK enum + nullable `source_ref text`; same idiom as `wr_week_ownership.owner_source` | ✓ |
| `source` enum only | Single CHECK column; Phase 12 would likely need an ALTER to add the reference pointer | |
| jsonb `provenance` blob | Open-ended; no CHECK; slower filtering on row_event; inconsistent with sibling columns | |

**User's choice:** `source` enum + `source_ref`
**Notes:** Reserved values `live`, `backfill_artifacts`, `backfill_hash_history`, `operator`; Phase 10 writes `'live'` only.

---

## How long history is kept (#3)

| Option | Description | Selected |
|--------|-------------|----------|
| Single table + pg_cron sliced DELETE, 24 mo | No partitioning; indexes on observed_at, (sheet_id,row_id), (wr,week_ending); daily/weekly sliced purge | ✓ |
| Monthly partitions + custom maintenance | Spec draft, but pg_partman is unavailable on hosted Supabase -> hand-written pg_cron create/drop function; missed future partition = writer INSERT failure | |
| Yearly partitions + custom maintenance | Fewer live partitions; same bespoke-maintenance caveat; retention rounds to whole years | |
| Keep forever, revisit after Phase 11 | No retention job now; dated reminder to decide on measured volume | |

**User's choice:** Single table + pg_cron sliced DELETE, 24-month window
**Notes:** Key research fact - pg_partman is not installable on hosted Supabase (supabase/postgres#1586). Phase 12 backfill does not depend on row_event history depth (ownership ladder uses artifacts / attribution_snapshot / imported hash_history; decisions persist in wr_week_ownership). Revisit trigger: Phase 11 volume >= ~10x projection or tens of GB.

---

## Safety net + MEM-04 proof (#4)

### Proof method

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: fixture + passive | Disposable non-prod sheets for the causal edit-and-observe test (recorded as replayable pytest fixture) + passive comparison over consecutive shadow-run full reads | ✓ |
| Fixture only | Disposable-sheet experiment + recorded fixture; no production corroboration | |
| Passive only | Watch shadow runs for a naturally occurring formula-only change; may never observe a case | |
| Docs / support ticket only | (researched, not offered) Smartsheet docs verified silent on formula-driven `modifiedAt`; non-reproducible | |

**User's choice:** Hybrid
**Notes:** Smartsheet Get Sheet docs (Context7, 2026-08-24) document `rowsModifiedSince` / `ifVersionAfter` / `level` but say nothing about cross-sheet-formula recalculation bumping `modifiedAt` or `Sheet.version` - hence a controlled experiment is required.

### Full-reconciliation cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Weekly deep run stays full | No schedule change; Monday run is the deletion/formula-change safety net; revisit after MEM-04 | ✓ |
| Daily full reconcile | ~94 min x 7/week extra; risk of overlapping the 2-hour cadence | |
| Every-Nth-run full | Rotation bookkeeping, no business-boundary meaning | |

**User's choice:** Weekly deep run stays full

### Fixture sheet creation (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Juan creates by hand in Smartsheet UI | Sandbox folder: lookup sheet + dependent sheet with cross-sheet INDEX/MATCH; script read-only; Juan makes the triggering edit by hand | ✓ |
| Script creates via API | One-time Smartsheet API write (guarded area) using the CI token | |
| Skip fixture - passive only | No test sheets | |

**User's choice:** Juan creates them by hand -> **zero Smartsheet API writes in the plan**.
**Notes:** Juan first asked "why do we need to create a Smartsheet memory sheet? I thought the memory would be in Supabase" - clarified that memory is Supabase-only and the fixture sheets are a throwaway test rig for the MEM-04 API-behaviour experiment, never memory. Confirmed after clarification.

### Raw evidence the MEM-04 experiment records (from research packet)
1. Fixture/lookup sheet ids, column structure, exact formula construction; disposable/non-production label and eventual disposition.
2. Timestamped sequence: T0 baseline full `get_sheet()` (per-row `modifiedAt`, `Sheet.version`); T1 the hand edit on the LOOKUP sheet (cell, old->new, time); T2 `get_sheet(if_version_after=<T0 version>)`; T3 `get_sheet(rows_modified_since=<T0 watermark - SAFETY_WINDOW>, level=2)`.
3. Raw request/response JSON saved as recorded cassettes (vcrpy-style) for a replayable pytest fixture.
4. Whether the DEPENDENT sheet's `Sheet.version` incremented after only the lookup sheet was edited.
5. Per-row `modifiedAt` diff pre/post for affected rows.
6. Whether the affected row appears in the `rows_modified_since` set and whether its cell value is fresh or stale.
7. Poll/retry timing to separate "never updates" from "recalculation lag".
8. Exact SDK call signatures and pinned versions (`smartsheet-python-sdk==4.3.0`, API version/date).
9. Both scenarios recorded separately: (a) WR archived -> `Foreman` blanks; (b) dept-mapping value edited in place.
10. SAFETY_WINDOW sensitivity: rerun with and without the overlap watermark.
11. One explicit PASS/FAIL verdict sentence for future readers.
12. Cassette path + test sheet ids so the experiment is rerunnable.

---

## Claude's Discretion

- Shadow rollout posture (flag default off in code; workflow flip in a separate PR after a SKIP_UPLOAD real-data dry run; memory-write time sub-budget; fail-open per sheet).
- `content_hash` column set (must include formula-derived personnel columns).
- `upsert_rows_bulk` RPC design, chunk size, `row_event` PK after de-partitioning.
- Module placement (`pipeline/memory.py` vs `run_memory/` package), `run_ledger.notes`, counters/summary lines.

## Deferred Ideas

- Retire `billing_audit.group_content_hash` -> `pipeline_memory.group_state`; drop local JSON caches (Phase 11+ after parity).
- Partition `row_event` (only if measured volume >= ~10x projection).
- Daily / every-Nth-run reconciliation (only if MEM-04 shows a gap).
- Ownership semantics (#1) and backfill (#5) -> Phase 12; audit finding key (#6) -> Phase 13.
