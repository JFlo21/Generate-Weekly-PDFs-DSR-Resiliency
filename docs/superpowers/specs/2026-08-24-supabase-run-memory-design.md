# Supabase Run Memory — incremental billing pipeline design (v1.4)

**Status:** DRAFT for Juan's review (2026-08-24). No production code, schema, or workflow
changed. Written from the 2026-08-24 diagnosis
(`.planning/debug/unknown-foreman-helper-shadow-2026-08-24.md`).

## 1. Problem statement (Juan, 2026-08-24)

The pipeline re-reads every ProMax sheet every run, keeps its memory in three local
GitHub-cached JSON files, freezes personnel first-write-wins, and audits from scratch.
Wanted: Supabase becomes the memory. Every run upserts every row's current state (no
duplicates), keeps history, and the run only (a) reads what changed on Smartsheet,
(b) rebuilds the (WR, week) files whose rows changed, (c) names each week's file after
the foreman who owned the job *at that time* ("last known foreman as of the week"),
and (d) keeps audit findings as a task list that persists until fixed.

## 2. Evidence the design is built on (run 32743959053, 2026-08-24, 94 min)

| Phase | Wall clock | What it does today | What memory changes |
|---|---|---|---|
| Discovery | 0 min | cached `discovery_cache.json` (7-day TTL) | `sheet_registry` |
| Sheet fetch | **33 min** (15:18-15:51) | full read of 117 sheets, **207,844 rows**, largest 6,054 | `ifVersionAfter` + `rowsModifiedSince`: unchanged sheets cost 1 call; changed sheets return only changed rows |
| Grouping | <1 min | in-memory | group only the affected (WR, week) set, rows pulled from `row_state` |
| Attachment pre-fetch | **20 min** (both 10-min budgets hit) | lists attachments for 762 TARGET + 774 PPP rows | `group_state` stores attachment ids; verify only affected groups |
| Group loop | 13 min | 3,091 `group_content_hash` GETs, 300 `pipeline_run` GET/POST, **12,227 `freeze_attribution` RPCs** | one bulk upsert per sheet; no per-group lookups for unaffected groups |
| Upload + cleanup | ~20 min | 163 files (154 were garbage-claimer churn) | only affected groups; churn removed by ownership fix |

Facts that constrain the design:

- `Foreman`, `Foreman Helping?`, `Helper Dept #` are **column formulas** on the source
  sheets (WR-level lookups into Resource Analyst / dept mapping). Smartsheet keeps no
  per-row history; once a WR is archived every row's `Foreman` blanks. Only a run-time
  record of the observed value preserves "who owned it then".
- `billing_audit` already has: `attribution_snapshot` (per-row frozen personnel, 212,406
  rows), `snapshot_provenance` (sheet_id, row_id, wr, cu, snapshot_date, billed_week;
  208,042 rows), `group_content_hash` (authoritative hash store), `pipeline_run` (269,556
  rows, 2,842 wr/weeks since 2026-04-25), `snapshot_drift`, `feature_flag`. The new layer
  extends this; it does not replace it.
- Backfill sources for "who owned the job" before the memory exists: `public.artifacts`
  filenames (`_User_<name>`, since 2026-05-29, 110,184 rows), `attribution_snapshot`
  (non-sentinel rows), and the pre-attribution local `hash_history.json` (`foreman` per
  WR|week, e.g. `89829163.0|082425 -> Allen Harris`).
- Smartsheet SDK 4.3.0 (installed) `Sheets.get_sheet(sheet_id, if_version_after=,
  rows_modified_since=)`; API `GET /sheets/{id}?ifVersionAfter&rowsModifiedSince`
  (ISO-8601). Verified 2026-08-24 (Context7 + `inspect.signature`).

## 3. Memory model (new Postgres schema `pipeline_memory`, same Supabase project)

```sql
-- One row per source sheet; replaces generated_docs/discovery_cache.json
create table pipeline_memory.sheet_registry (
  sheet_id            bigint primary key,
  name                text not null,
  kind                text not null check (kind in ('primary','subcontractor','original_contract','vac_crew')),
  folder_id           bigint,
  column_mapping      jsonb not null,            -- validated mapping, refreshed on full read
  last_sheet_version  bigint,                    -- from Sheet.version (ifVersionAfter)
  last_read_at        timestamptz,               -- watermark for rowsModifiedSince
  last_full_read_at   timestamptz,
  active              boolean not null default true,
  updated_at          timestamptz not null default now()
);

-- CURRENT state, one row per Smartsheet row; upsert, never duplicated
create table pipeline_memory.row_state (
  sheet_id            bigint not null,
  row_id              bigint not null,
  wr                  text not null,
  week_ending         date,
  snapshot_date       date,
  cu text, pole text, work_type text, quantity numeric, units_total_price numeric,
  units_completed     boolean not null default false,
  foreman_observed    text,        -- value of the Foreman lookup AT THIS OBSERVATION (may be blank)
  helper_observed     text, helper_completed boolean, helper_dept text, helper_job text,
  vac_crew_observed   text, vac_completed boolean,
  row_modified_at     timestamptz, -- Smartsheet row.modifiedAt
  content_hash        text not null,
  first_seen_run      text not null,
  last_seen_run       text not null,
  last_changed_run    text not null,
  deleted_at          timestamptz,
  primary key (sheet_id, row_id)
);
create index on pipeline_memory.row_state (wr, week_ending);

-- HISTORY, append-only, written ONLY when content_hash changes (no per-run duplicates).
-- Range-partitioned by observed_at (monthly); retention decided by Juan.
create table pipeline_memory.row_event (
  event_id     bigint generated always as identity,
  sheet_id bigint not null, row_id bigint not null, run_id text not null,
  observed_at  timestamptz not null default now(),
  change_kind  text not null check (change_kind in ('insert','update','delete','reconcile')),
  after_image  jsonb not null,                    -- same columns as row_state
  primary key (event_id, observed_at)
) partition by range (observed_at);

-- Who owns each (WR, week, variant) file: the "last known foreman as of the week"
create table pipeline_memory.wr_week_ownership (
  wr text not null, week_ending date not null, variant text not null,
  owner_name    text not null,                    -- NEVER a sentinel ('Unknown Foreman', '#NO MATCH')
  owner_role    text not null,                    -- primary_foreman | helper | vac_crew
  owner_source  text not null,                    -- observed_in_week | last_known_before_week | backfill_artifacts | backfill_hash_history | operator
  decided_run   text not null, decided_at timestamptz not null default now(),
  primary key (wr, week_ending, variant, owner_role, owner_name)
);

-- Per generated file; supersedes group_content_hash + attachment pre-fetch
create table pipeline_memory.group_state (
  wr text, week_ending date, variant text, identifier text,
  content_hash text not null, row_count int not null,
  target_sheet_id bigint, attachment_id bigint, attachment_name text,
  last_generated_run text, last_verified_run text, updated_at timestamptz default now(),
  primary key (wr, week_ending, variant, identifier)
);

-- Run ledger (run-level; billing_audit.pipeline_run stays per WR/week)
create table pipeline_memory.run_ledger (
  run_id text primary key, mode text not null check (mode in ('incremental','full','targeted')),
  started_at timestamptz, finished_at timestamptz, release text,
  sheets_checked int, sheets_changed int, rows_seen int, rows_changed int,
  groups_affected int, groups_generated int, status text, notes jsonb
);

-- Audit memory: a finding lives until it is observed fixed
create table pipeline_memory.audit_finding (
  finding_key   text primary key,                 -- sha(check_id|wr|week|cu|pole|...)
  check_id      text not null, severity text not null,
  wr text, week_ending date, cu text, pole text,
  status        text not null check (status in ('open','fixed','resurfaced','acknowledged','suppressed')),
  first_seen_run text not null, last_seen_run text not null, fixed_run text,
  evidence      jsonb not null, acknowledged_by text, acknowledged_at timestamptz,
  updated_at timestamptz default now()
);
create table pipeline_memory.audit_finding_event (
  event_id bigint generated always as identity primary key,
  finding_key text not null references pipeline_memory.audit_finding(finding_key),
  run_id text not null, at timestamptz default now(), transition text not null, detail jsonb
);
```

Write path = one RPC per sheet (`upsert_rows_bulk(jsonb[])`) doing the diff server-side
(hash compare, insert `row_event` only on change, upsert `row_state`, return the set of
affected `(wr, week_ending)` including the *previous* week when a row's week moved).
Reads use PostgREST bulk RPCs like the existing `lookup_attribution_bulk`. Writer uses the
CI service-role key exactly as `billing_audit` does today; RLS: service-role only.

## 4. Run algorithm

```text
run(mode):                       # incremental (7x/day) | full (weekly deep run, RESET_*, memory outage)
  registry = sheet_registry (+ cheap folder walk to register NEW sheets; first read is full)
  affected = {}
  for sheet in registry.active (parallel <= 8):
      if mode == incremental:
          s = get_sheet(sheet.id, if_version_after=sheet.last_sheet_version)
          if s is abbreviated (version unchanged): continue          # 1 call, 0 rows
          rows = get_sheet(sheet.id, rows_modified_since=sheet.last_read_at - SAFETY_WINDOW, level=2).rows
      else:
          rows = get_sheet(sheet.id, level=2).rows                    # full reconcile; also detects deletions
      normalized = normalize(rows, sheet.column_mapping)              # same accept rules as fetch.py today
      affected |= upsert_rows_bulk(sheet.id, run_id, normalized, full=(mode == 'full'))
      registry.update(sheet, version=s.version, last_read_at=now - SAFETY_WINDOW)
  for (wr, week) in affected:
      rows   = row_state.where(wr, week, units_completed, not deleted)  # from Supabase, not Smartsheet
      owner  = decide_owner(wr, week)                                  # section 5
      groups = group_source_rows(rows, owner)                          # existing grouping, ownership-partitioned
      for g in groups:
          if group_state.hash == g.hash and attachment verified: continue
          excel -> upload (delete old attachment by stored attachment_id) -> group_state.upsert
  audit(affected, open_findings)                                       # section 6
  run_ledger.finish()
```

- SAFETY_WINDOW (e.g. 15 min) overlaps consecutive reads so clock skew never loses a row;
  the server-side hash compare makes re-reads idempotent.
- The weekly deep run (`0 5 * * 1`) is the full reconciliation: catches deletions and
  **formula-only changes** (a WR archived / a dept-mapping edit may not bump the row's
  `modifiedAt`; this must be proven in Phase 10 before relying on incremental mode).
- Memory outage (`fetch_failure` / `unavailable`) -> automatic fallback to `full` mode on
  today's code path; memory is never allowed to make the run silently skip work.

## 5. Ownership ("last known foreman as of the week") — replaces sentinel freezing

For each (WR, week_ending):

1. `observed_in_week`: the non-blank `foreman_observed` recorded on that WR's rows by any
   run whose observation fell inside the week (or the first run that saw those rows
   completed). This is what Foundation A meant by "claimed", minus sentinels.
2. `last_known_before_week`: else the latest non-blank foreman observed for that WR at or
   before the week ending (`row_event` history).
3. `backfill_*`: else, for weeks older than the memory, `public.artifacts` `_User_<name>`
   filenames, non-sentinel `attribution_snapshot`, then the 2025 `hash_history.json`
   `foreman` field (imported once, tagged `backfill_hash_history`).
4. else `Unknown Foreman`: still a valid *filename*, but **never written to memory as a
   name**, so a later observation can replace it.

Helper and VAC owners follow the same ladder per role. Row-level partition (which rows go
into which foreman's file) stays per row (Foundation A), but the frozen value is the
observed value, never the sentinel, and it is re-decidable from history.

Example: WR 89829163 rows for WE 2025-09-21 observed with Allen Harris -> his file. If a
prior foreman was observed on the WE 2025-08-16 rows, that week's file carries that name.

**This changes Foundation A's "frozen first-write-wins" contract** (spec 2026-05-20,
fail-safe stance) and needs Juan's explicit approval plus validation against a known-good
sample (production guardrail: billing/reporting outputs).

## 6. Audit memory

`audit_billing_changes.py` computes findings only for `affected` groups plus all `open`
findings. Transition rules: new key -> `open`; seen again -> bump `last_seen_run`
(`acknowledged` -> `resurfaced`); an open finding not produced for a group that WAS
re-audited -> `fixed` (+ `fixed_run`); groups not re-audited leave findings untouched.
The Excel/portal audit surfaces open + resurfaced only.

## 7. Migration (shadow-first, kill-switched, additive) — see ROADMAP v1.4

Phase 10 foundation (shadow writes, zero behavior change) -> Phase 11 incremental read +
affected-group regeneration behind `RUN_MEMORY_INCREMENTAL_ENABLED` with parity proof
(incremental output set == full-run output set for >= 5 consecutive scheduled runs) ->
Phase 12 ownership + sentinel fix + backfill + remediation of the 93 affected WRs ->
Phase 13 audit memory. Local caches (`hash_history.json`, `discovery_cache.json`,
`billing_audit_frozen_rows.json`) are retired only after Phase 11 parity.

## 8. Decisions needed from Juan

Each decision is tagged with the roadmap phase it gates, so `/gsd-discuss-phase N` asks
only what that phase needs. Phase 10 (shadow writes) needs #2, #3, #4 locked — and #5
only to the extent of reserving a provenance column — before planning.

1. Ownership semantics: adopt section 5 ("as-of the week, never a sentinel") over
   "frozen first-write-wins"? Billing-visible; protected area. — **gates Phase 12**
   (OWN-01/02/04); not a Phase 10 gate.
2. Same Supabase project (`poeyztlmsawfoqlanucc`) + new schema `pipeline_memory` (vs.
   extending `billing_audit`)? — **gates Phase 10** (MEM-01).
3. `row_event` retention (proposal: 24 months, monthly partitions). — **gates Phase 10**
   (MEM-01 schema DDL).
4. Keep the weekly deep run as the full reconciliation (required while the
   formula-only-change risk in section 4 is unproven)? — **gates Phase 10** (MEM-04
   experiment design) and Phase 11 (INC-03).
5. Backfill sources allowed (artifacts filenames, 2025 hash_history import)? — **gates
   Phase 12** (OWN-03); Phase 10 only reserves a `source`/provenance column in
   `row_event` / `group_state` so backfilled rows are distinguishable.
6. Audit finding key definition (check_id|wr|week|cu|pole) and who may `acknowledge`. —
   **gates Phase 13** (AUD-01).

## 9. Expected effect (estimate; to be measured in Phase 11 shadow runs)

Frequent run: fetch 33 -> ~3-6 min (most sheets unchanged within a 2-hour window),
attachment pre-fetch 20 -> 0, group loop 13 -> ~2, upload proportional to real changes;
roughly 25 min vs 94 today. Weekly deep run unchanged (~90 min). Smartsheet calls drop
from ~117 full sheet reads + ~1,500 attachment listings to ~117 version checks + changed
sheets; Supabase calls drop from ~16,300 per run to ~130 bulk RPCs.
