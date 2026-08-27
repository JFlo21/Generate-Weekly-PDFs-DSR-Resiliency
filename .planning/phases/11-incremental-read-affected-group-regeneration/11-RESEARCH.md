# Phase 11: Incremental Read + Affected-Group Regeneration - Research

**Researched:** 2026-08-26
**Domain:** Incremental Smartsheet delta-read + scoped billing-group regeneration, layered on the Phase 10 `pipeline_memory` Supabase schema
**Confidence:** HIGH (code-verified against the current tree; two items — the ordering restructuring and the cleanup/pruning consumers — are original synthesis flagged `[ASSUMED]` pending planner/executor confirmation)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

D-01..D-12 are LOCKED in `.planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md`. Full text is not re-copied here verbatim in full (12 multi-paragraph decisions) — this research treats every one as a hard constraint and cites the exact section when relevant. Headline commitments, quoted verbatim from `11-CONTEXT.md`:

- **D-01** (watermark): "**Fixed overlap, capture-time watermark.** Per registered sheet the frequent run calls `Sheets.get_sheet(sheet_id, if_version_after=last_sheet_version, rows_modified_since=last_read_at − SAFETY_WINDOW)`... `last_read_at` is captured **immediately before** the read is issued and persisted **as captured** (UTC-aware ISO-8601); the `SAFETY_WINDOW` subtraction is applied **only when building the query filter** — never persist `now − SAFETY_WINDOW`."
- **D-02** (escalation triggers): seven FULL-read triggers ship in the same change as D-01 (new sheet / `column_mapping` drift / 401-403 isolation / memory outage / operator reset flags / prior run not `success` / non-`production_frequent` execution type).
- **D-03**: "**Deletions are never detected on the frequent path.**" — deletion + formula-only reconciliation is the weekly deep run's job (INC-03).
- **D-04** (row source): "**Option C — hybrid: `row_state` decides membership, a scoped full re-fetch supplies content, the generation pipeline is unmodified.**"
- **D-05**: INC-02's "rows come from `row_state`" clause is deliberately **not satisfied this phase** — logged as an approved deferral, not a gap.
- **D-06**: "**Nothing outside the affected scope is touched in incremental mode.**" Every `all_rows`/target-row consumer downstream of PHASE 2 is either scoped to the affected groups or skipped for the run.
- **D-07/D-08/D-09** (parity): "**Shadow-incremental, in-process, on the same fetched snapshot**"; the shadow "also issues the real delta reads"; streak = consecutive **parity-evaluated** `production_frequent` runs (pass counts, fail resets, skipped excluded).
- **D-10**: Plan 01 = WR-01 + WR-04 + IN-01 (write-flip preconditions); the `RUN_MEMORY_WRITE_ENABLED` flip is its own operator-gated PR, assumed landed by later plans (`checkpoint:human-verify`).
- **D-11**: `RUN_MEMORY_INCREMENTAL_ENABLED` default OFF in code, scoped to `production_frequent` only; fallback visibility lives in `run_ledger.mode`/`notes.fallback_reason` only — `run_summary.json` untouched.
- **D-12**: INC-05 retirement (local JSON caches + attachment pre-fetch) is its own PR strictly after the D-09 streak; records frequent-run wall-clock before/after (baseline 94 min, run `32743959053`).

### Claude's Discretion

- Exact names/defaults of new config constants (`SAFETY_WINDOW_MINUTES=15`, `RUN_MEMORY_SHADOW_MAX_MINUTES`, per-call timeout), following the `ATTACHMENT_PREFETCH_*` / `RUN_MEMORY_WRITE_*` pattern in `pipeline/config.py` (documented in `.github/prompts/configuration-environment.md` in the same PR).
- The affected-set → sheet mapping query and the exact D-06 scoping of each downstream `all_rows` consumer.
- Streak query implementation, `parity_details` JSON shape, Sentry event shape for a parity `fail`.
- Fixture design for success criterion 3 (deep run detects a deleted row + a formula-only change; repairs `row_state`/`group_state`) and the one live verification.
- Module layout for the shadow comparison (new module vs. `pipeline_memory/`), keeping `orchestrate.py` edits to hooks.

### Deferred Ideas (OUT OF SCOPE)

- Option B (`row_state`-exclusive raw-field sourcing, schema extension) — later slice, gated on D-04 running clean ≥5 runs.
- Dual-output byte-level parity on the weekly deep run — optional hardening after INC-04.
- Replay harness (capture+replay offline) — possible CI supplement, not scheduled-run evidence.
- Self-scaling overlap window — revisit only if cron cadence changes (10-CONTEXT D-07 locks it today).
- Manual-dispatch-only opt-in for the first incremental run — not chosen; `production_frequent` scoping is the safety net.
- 44-open-PR backlog triage — separate pass.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INC-01 | Frequent runs use `ifVersionAfter` + `rowsModifiedSince` per registered sheet; unchanged sheets cost one call and zero rows. | Architecture Patterns Pattern 1 (D-01 delta read); Code Examples "Delta read + abbreviated-response detection"; `pipeline/fetch.py:247-267` current full-read call site to extend; `scripts/mem04_experiment.py:344-362` proven probe shape. |
| INC-02 | Only (WR, week) groups touched by changed rows (incl. moved-week prior pair) are regrouped/regenerated/uploaded; rows sourced from `row_state` (partially deferred per D-05). | Architecture Patterns Pattern 2 (D-04 hybrid); "The Ordering Problem" subsection; `pipeline_memory/schema.sql:280-477` affected-set UNION; `pipeline/orchestrate.py:1024-1029` grouping call site to restructure. |
| INC-03 | Weekly deep run performs full read + reconciliation (deletions, formula-only changes) and refreshes `sheet_registry.column_mapping`. | Common Pitfall "Deletions are structurally invisible to delta reads"; Validation Architecture SC3 fixture design. |
| INC-04 | Behind `RUN_MEMORY_INCREMENTAL_ENABLED` (default OFF) with shadow parity proof for ≥5 consecutive scheduled runs before defaulting ON. | Architecture Patterns Pattern 3 (D-07/D-08 shadow); Don't Hand-Roll "parity comparator"; Validation Architecture SC1/SC2. |
| INC-05 | Local JSON caches + attachment pre-fetch phases retired only after INC-04; `group_state` holds attachment ids. | Architecture Patterns Pattern 4 (D-12 retirement order); `.github/workflows/weekly-excel-generation.yml:159-192,771-793` cache steps inventory. |
</phase_requirements>

## Summary

Phase 11 is not a fresh integration — it is a **scoping and reordering problem** layered on a fully-built, currently write-OFF Supabase schema (`pipeline_memory`, shipped shadow-mode in Phase 10). Every table, RPC, and Python writer function this phase needs already exists and is schema-frozen (D-04 mandates zero schema change). The work is: (1) make `pipeline/fetch.py`'s per-sheet read conditionally use `if_version_after`/`rows_modified_since` and detect the SDK's abbreviated response; (2) promote `upsert_rows_bulk`'s already-computed affected `(wr, week_ending)` set from observability-only to the scope selector for a **second, full, sheet-scoped** re-fetch; (3) run the **existing, unmodified** `group_source_rows()` → `pricing.py` → `attribution.py` → `excel.py` pipeline over that scoped re-fetch; and (4) audit every downstream consumer of `all_rows`/`groups` in `pipeline/orchestrate.py` (there are more of them than the ROADMAP text names, and at least two — the hash-history stale-key prune and the untracked-attachment cleanup — will silently **delete live data for untouched groups** if not explicitly re-gated for incremental mode).

The highest-risk finding of this research is **not** the Smartsheet API mechanics (those are already fixture-proven: MEM-04 passed, `scripts/mem04_experiment.py` already exercises the exact `if_version_after`/`rows_modified_since` call shapes against SDK 4.3.0). The highest-risk finding is that `pipeline/orchestrate.py`'s end-of-run maintenance blocks (`valid_wr_weeks` at line 2912, the hash-history stale-key prune at line 3164, and both `cleanup_untracked_sheet_attachments` call sites at lines 3054 and 3131) all iterate `groups.items()` **unconditionally** to decide what is "still live" versus "no longer in source data." In full mode `groups` is every group; in incremental mode (per D-04) `groups` will be *only the affected subset* — so without an explicit incremental-mode gate, these three blocks will treat every untouched, still-valid group's hash-history entry and Smartsheet attachment as stale and **delete it**. This is exactly the class of defect D-06 exists to prevent, and the repo already ships the fix mechanism for one of the two consumers: `KEEP_HISTORICAL_WEEKS` (`pipeline/config.py:578`, consumed at `pipeline/cleanup.py:429`) was built, in a prior sub-project, for precisely "preserve identities not processed this run" — it is currently OFF by default and unused for this purpose, but reusing it (forcing it true for the incremental-mode cleanup call) is a smaller, better-understood fix than writing new skip logic. The hash-history prune has an analogous existing guard (`not _time_budget_exceeded`, `orchestrate.py:3169`) built for the *same* "we didn't reach every group this run" reasoning — extending its condition to also require `mode == 'full'` is the natural fix, not a new mechanism.

The second-highest-risk finding is a genuine **ordering problem** with no existing analog: today, `_run_memory_write_phase()` (the affected-set producer) runs *after* the full `get_all_source_rows()` fetch and *before* grouping (`orchestrate.py:890, 913, 1027`) — that ordering only works because the fetch is already full. For a delta-first read, the affected set can only be known *after* a small delta fetch, but the pipeline then needs a *second, full, sheet-scoped* fetch to get complete group content before grouping can run. This requires restructuring PHASE 2 into two sub-phases gated on run mode; it is described in detail below with three concrete options and a recommendation, because CONTEXT.md's Discretion list explicitly assigns this synthesis to research.

**Primary recommendation:** Implement D-04 as: PHASE 2a delta-read (new function, reuses `pipeline.fetch`'s retry/thread-pool machinery) → existing `_run_memory_write_phase()` unmodified, fed the delta rows → new `pipeline_memory` reader function mapping the affected set to sheet ids via `row_state`'s existing `idx_row_state_wr_week` index → PHASE 2b scoped full re-fetch calling the **existing, unmodified** `get_all_source_rows()` with the sheet list narrowed to that mapped set → **existing, unmodified** `group_source_rows()` restricted to group keys whose `(wr, week)` prefix is in the affected set. Gate every end-of-run maintenance block (`valid_wr_weeks`/cleanup, hash-history prune) on `mode == 'full'` (reusing `KEEP_HISTORICAL_WEEKS` and the `_time_budget_exceeded` guard's existing pattern) rather than inventing new skip logic. The shadow-parity comparator (D-07/D-08) should be a new, small module (not inside `pipeline_memory/`, which is a client/writer package with a documented "imports nothing from `pipeline.*`" boundary) that consumes the already-computed `calculate_data_hash()` value from the existing group loop (`orchestrate.py:1810`) — no second Excel pass, no new hashing primitive.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Delta read detection (`if_version_after`/`rows_modified_since`) | Backend batch job (`pipeline/fetch.py`) | External API (Smartsheet) | The SDK call and abbreviated-response parsing are pure I/O-adjacent logic inside the existing fetch module; no new tier. |
| Affected-set computation | Backend batch job (`pipeline_memory/writer.py`, unmodified) | Database (Supabase `upsert_rows_bulk` RPC) | Already server-side (`schema.sql:280-477`); Python only chunks/dispatches. |
| Affected-set → sheet mapping | Database (Supabase `row_state`, new SELECT) | Backend batch job (new reader function) | `row_state.sheet_id`/`wr`/`week_ending` already exist with an index; this is a read query, not new storage. |
| Scoped full re-fetch | Backend batch job (`pipeline/fetch.py`, unmodified function, narrowed input) | External API (Smartsheet) | Reuses `get_all_source_rows()` verbatim — zero grouping/pricing/attribution risk. |
| Grouping / pricing / attribution / Excel generation | Backend batch job (`pipeline/grouping.py`, `pricing.py`, `attribution.py`, `excel.py`) | — | D-04 mandates these stay **unmodified**; only their *input* is scoped. |
| End-of-run cleanup/pruning (attachments, hash-history) | Backend batch job (`pipeline/orchestrate.py`, `pipeline/cleanup.py`) | External API (Smartsheet attachments) | Must be re-gated per D-06; currently assumes full-mode `groups` coverage. |
| Parity shadow comparison | Backend batch job (new module) | Database (`run_ledger.notes`) | In-process, same run, no second Excel pass — not a separate service. |
| Rollout gating | CI/CD config (`.github/workflows/weekly-excel-generation.yml`) | Backend batch job (`pipeline/config.py` flags) | `RUN_MEMORY_INCREMENTAL_ENABLED` keyed on `EXECUTION_TYPE`, mirroring existing flag-family pattern. |

## Standard Stack

No new library dependency is introduced by this phase.

### Core (already pinned — verified this session)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `smartsheet-python-sdk` | `==4.3.0` `[VERIFIED: requirements.txt]` | `Sheets.get_sheet(if_version_after=…, rows_modified_since=…)` — the delta-read primitive INC-01 needs | Already pinned exact (upper-bound incident on 4.0.0, Living Ledger `[2026-06-08]`); `if_version_after`/`rows_modified_since` mapping to `ifVersionAfter`/`rowsModifiedSince` query params already fixture-proven against this exact version (`11-ADVISOR-read-watermark-safety-window.md`, `scripts/mem04_experiment.py`). |
| `supabase` (Python client) | `==2.31.0` `[VERIFIED: requirements.txt]` | PostgREST client for `pipeline_memory.row_state`/`run_ledger` reads this phase adds | Already the sole writer client for Phase 10's `pipeline_memory` schema; no version bump implied by adding SELECT queries. |
| `sentry-sdk` | `>=2.54.0` `[VERIFIED: requirements.txt]` | Parity-`fail` alerting (D-07: "loud even though the run never acts on it") | Already the project's error/breadcrumb channel; `sentry_add_breadcrumb`/`sentry_capture_message_with_context` helpers already used throughout `orchestrate.py`. |

### Alternatives Considered

Not applicable — this phase adds no new library. All "alternatives" are architectural options among the existing stack, captured in the four `11-ADVISOR-*.md` files and reproduced in Architecture Patterns below.

**Installation:** none — no `requirements.txt` change.

## Package Legitimacy Audit

**No external packages are installed by this phase.** `smartsheet-python-sdk==4.3.0`, `supabase==2.31.0`, and `sentry-sdk>=2.54.0` are pre-existing pins in `requirements.txt` `[VERIFIED: requirements.txt]`; Phase 11 only calls already-imported SDK/client methods (`Sheets.get_sheet` with additional kwargs; `supabase-py`'s `.table()`/`.rpc()` for new SELECT queries against `pipeline_memory`). The Package Legitimacy Gate is not applicable — no `npm view`/`pip index versions`/registry check is needed because nothing new is being added.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────────┐
                         │   .github/workflows/weekly-excel-generation  │
                         │   "Determine execution type" step (194-209)  │
                         │   -> EXECUTION_TYPE env (production_frequent │
                         │      / weekend_maintenance / weekly_         │
                         │      comprehensive / manual)                 │
                         └───────────────────┬───────────────────────────┘
                                             │ EXECUTION_TYPE
                                             v
┌────────────────────────────────────────────────────────────────────────────┐
│ pipeline/orchestrate.py :: main()                                          │
│                                                                              │
│  PHASE 1 discovery (846-859) ─────────────────────────────────────────┐    │
│                                                                         │    │
│  mode = resolve_mode(EXECUTION_TYPE, sheet_registry, run_ledger, flags)│    │
│           (D-02: 7 escalation triggers -> 'full'; else 'incremental'  │    │
│            only when RUN_MEMORY_INCREMENTAL_ENABLED)                  │    │
│                                                                         │    │
│  ┌─── mode == 'incremental' ──────────────┐  ┌─── mode == 'full' ────┐│    │
│  │ PHASE 2a: per-sheet delta read          │  │ PHASE 2 (unchanged): │││    │
│  │  Sheets.get_sheet(if_version_after=...) │  │  get_all_source_rows │││    │
│  │  -> abbreviated? skip : rows_modified_  │  │  (full, every sheet) │││    │
│  │      since(...) full row set for THAT   │  └───────────┬──────────┘│    │
│  │      sheet                              │              │           │    │
│  │       v                                 │              │           │    │
│  │  _run_memory_write_phase() (UNMODIFIED, │              │           │    │
│  │   385-557) -> upsert_rows_bulk RPC      │              │           │    │
│  │   (schema.sql:280-477) -> affected      │              │           │    │
│  │   (wr, week_ending) set                 │              │           │    │
│  │       v                                 │              │           │    │
│  │  NEW: map_affected_to_sheets(affected)  │              │           │    │
│  │   SELECT DISTINCT sheet_id FROM         │              │           │    │
│  │   row_state WHERE (wr,week_ending) IN.. │              │           │    │
│  │       v                                 │              │           │    │
│  │  PHASE 2b: get_all_source_rows(         │              │           │    │
│  │   client, sheets=mapped_sheets)         │              │           │    │
│  │   (EXISTING FUNCTION, narrowed input)   │              │           │    │
│  └──────────────────┬───────────────────────┘              │           │    │
│                     └───────────────┬─────────────────────┘           │    │
│                                     v                                  │    │
│               all_rows (full mode: everything;                        │    │
│                          incremental mode: affected sheets only)      │    │
│                                     v                                  │    │
│         group_source_rows(all_rows) (1027, UNMODIFIED)                │    │
│         -- incremental: filter groups to keys whose (wr,week)         │    │
│            prefix is in `affected` before the group loop              │    │
│                                     v                                  │    │
│  group loop (1794+): calculate_data_hash() (1810, UNMODIFIED)          │    │
│    -> regenerate/skip decision -> Excel -> upload -> group_state       │    │
│                                     v                                  │    │
│  ┌─ D-07/D-08 shadow (mode=='full' AND RUN_MEMORY_WRITE_ENABLED) ────┐ │    │
│  │  NEW small module: compute what incremental WOULD have selected   │ │    │
│  │  from THIS run's own affected set; compare group-key sets AND     │ │    │
│  │  per-group calculate_data_hash() values against what full mode    │ │    │
│  │  actually regenerated -> run_ledger.notes.parity_verdict          │ │    │
│  └─────────────────────────────────────────────────────────────────┘ │    │
│                                     v                                  │    │
│  end-of-run maintenance -- MUST gate on mode=='full':                 │    │
│    valid_wr_weeks (2912) / cleanup_untracked_sheet_attachments        │    │
│    (3054, 3131) / hash-history stale prune (3164-3259)                │    │
│                                     v                                  │    │
│  run_ledger_finish(mode=..., ...) (3284) -> run_summary.json (frozen  │    │
│    21-key contract, UNCHANGED) + Sentry tags                          │    │
└────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
pipeline/
├── fetch.py             # ADD: delta-read function(s); abbreviated-response
│                         #   detection; scoped-sheet-list support for the
│                         #   existing get_all_source_rows() call
├── orchestrate.py        # ADD: mode resolution (D-02 triggers), PHASE 2a/2b
│                         #   split, incremental-mode gates on maintenance
│                         #   blocks; MODIFY: run_ledger_start/finish mode arg
├── cleanup.py             # MODIFY (small): incremental-mode call sites pass
│                         #   keep_historical=True (reuse KEEP_HISTORICAL_WEEKS)
├── change_detection.py    # UNCHANGED (calculate_data_hash reused as-is)
├── grouping.py            # UNCHANGED (D-04 mandate)
├── excel.py               # UNCHANGED (D-04 mandate)
pipeline_memory/
├── writer.py              # ADD: WR-01 fix (parse_price/_parse_quantity reuse
│                         #   in _row_to_payload); WR-04 (sheets_changed)
├── reader.py              # NEW: affected-set -> sheet mapping query; D-09
│                         #   streak-scan query over run_ledger. writer.py's
│                         #   "imports nothing from pipeline.*" boundary and
│                         #   its name (writer) argue for a sibling reader
│                         #   module, not new writer.py responsibilities.
├── schema.sql             # UNCHANGED (D-04: zero schema change)
pipeline/parity/           # NEW (or top-level pipeline/parity.py if small):
├── shadow_compare.py       #   D-07/D-08 shadow-incremental comparator,
│                         #   hooked from orchestrate.py, never imported
│                         #   by grouping/excel/pricing
tests/
├── test_pipeline_memory_shadow.py   # ADD affected-set-mapping, WR-01 tests
├── test_incremental_read.py         # NEW: delta-read + mode-resolution tests
├── test_parity_shadow.py            # NEW: shadow comparator tests
├── fixtures/incremental/            # NEW: deleted-row + formula-only-change
│                                     #   fixtures for INC-03 / success criterion 3
```

### Pattern 1: Delta read with abbreviated-response detection (D-01, INC-01)

**What:** Per registered sheet, call `Sheets.get_sheet` with `if_version_after` first; if the SDK returns an abbreviated response (no usable `rows`), the sheet is unchanged — zero-row skip. Only on a version bump does the run request `rows_modified_since`.

**When to use:** Every `production_frequent` run when `RUN_MEMORY_INCREMENTAL_ENABLED=1` and the sheet is not subject to one of the D-02 full-read triggers.

**Verified probe shape** `[VERIFIED: scripts/mem04_experiment.py:344-362]` (quoted verbatim):
```python
        # T2: ifVersionAfter -- abbreviated (version only) when the
        # dependent sheet's version has NOT advanced past baseline.
        t2_capture = _capture_full_sheet(
            client, args.dependent_sheet_id, f"T2 poll {attempt}",
            if_version_after=baseline_version, level=2,
        )
        t2_capture["abbreviated"] = "rows" not in t2_capture["raw_response"]

        # T3a: rows_modified_since WITH the SAFETY_WINDOW overlap.
        t3a_capture = _capture_full_sheet(
            client, args.dependent_sheet_id, f"T3a (overlap) poll {attempt}",
            rows_modified_since=overlap_watermark, level=2,
        )
```
The `"rows" not in raw_response` check operates on the dict form of the response; the **production** `_fetch_and_process_sheet` in `pipeline/fetch.py` currently has NO such check — it goes straight to `for row in sheet.rows:` at `pipeline/fetch.py:326` `[VERIFIED: pipeline/fetch.py:326]` (`"for row in sheet.rows:"`), which will raise if the SDK's abbreviated `Sheet` object exposes `rows` as `None` rather than omitting the attribute. **This is new logic, not an extension of existing logic** — `[ASSUMED]` that `getattr(sheet, 'rows', None)` is the correct production-code equivalent of the experiment script's dict-based check; verify against a live abbreviated response (or the SDK source for `Sheet.rows`'s default) before relying on it, since the experiment script inspects a serialized dict, not the live SDK object the pipeline actually receives.

**Existing call site to extend** `[VERIFIED: pipeline/fetch.py:247-256]`:
```python
                    sheet = smartsheet_call_with_retry(
                        client.Sheets.get_sheet,
                        source['id'],
                        column_ids=column_ids_param,
                        label=f"fetch sheet {source['name']}",
                    )
```
`smartsheet_call_with_retry` already wraps this call with the retry/backoff machinery `[VERIFIED: pipeline/fetch.py:242-256]`; a new delta-read variant should reuse this same wrapper, adding `if_version_after`/`rows_modified_since` as additional kwargs, not a parallel HTTP path.

### Pattern 2: Hybrid affected-group regeneration (D-04, INC-02) and the ordering problem

**What:** `row_state` decides *which* sheets and groups need attention; a scoped, full (non-delta) re-fetch of only those sheets supplies content; grouping/pricing/attribution/excel run unmodified.

**The ordering problem (Discretion item 2 — original synthesis, `[ASSUMED]` design, not yet code-verified against a working incremental implementation):**

Today's linear order in `main()`:
1. PHASE 1 discovery → `source_sheets` (`orchestrate.py:846-859`)
2. PHASE 2 fetch (full, every sheet) → `all_rows` (`orchestrate.py:890`) `[VERIFIED: pipeline/orchestrate.py:887-898]`
3. `_run_memory_write_phase(all_rows, ...)` → `_mem_affected` (observability-only today) (`orchestrate.py:904-929`) `[VERIFIED: pipeline/orchestrate.py:912-929]`
4. `group_source_rows(all_rows)` → `groups` (`orchestrate.py:1027`) `[VERIFIED: pipeline/orchestrate.py:1024-1029]`

The affected set is only knowable *after* step 2's fetch — which is exactly the full read INC-01 exists to avoid. For a true delta-first read, the affected set must come from a **small** delta fetch, but grouping needs a **complete** row set for every sheet touching an affected `(wr, week_ending)` pair (a group's rows can span multiple sheets — subcontractor + primary, or a helper-shadow variant on a different sheet — so a delta read of only the ONE sheet that changed would starve `group_source_rows()` of the other sheets' rows for that same group).

**Three concrete options** (this synthesis, not found pre-built in the codebase):

1. **RECOMMENDED — Split PHASE 2 into 2a (delta) + write + map + 2b (scoped full), gated on `mode`.** In incremental mode: run a new small delta-fetch function per sheet (reusing `smartsheet_call_with_retry` and the existing `ThreadPoolExecutor` pattern) → feed those rows into the **existing, unmodified** `_run_memory_write_phase()` to get the affected set → new `pipeline_memory/reader.py` function `SELECT DISTINCT sheet_id FROM pipeline_memory.row_state WHERE (wr, week_ending) IN (...)` (uses the existing `idx_row_state_wr_week` index `[VERIFIED: pipeline_memory/schema.sql:128-129]` — `"CREATE INDEX IF NOT EXISTS idx_row_state_wr_week ON pipeline_memory.row_state (wr, week_ending);"`) → call the **existing, unmodified** `get_all_source_rows(client, source_sheets)` with `source_sheets` narrowed to the mapped sheet-id list. In full mode, skip 2a/2b entirely and keep today's single call. **Why recommended:** `get_all_source_rows()` and `_run_memory_write_phase()` are reused byte-for-byte — only their *inputs* are scoped, which is the lowest-risk way to satisfy D-04's "the generation pipeline is unmodified."
2. **REJECTED (anti-pattern) — full fetch first, filter groups afterward.** Keep today's order unchanged; use the affected set only to skip Excel generation/upload for non-affected groups after the fact. Zero code restructuring, but delivers **none** of INC-01's read-cost savings (ROADMAP success criterion 1 requires `rows_seen ≪ 208k`; this option's `rows_seen` is unchanged). Flagged explicitly because it is the easiest option to reach for and directly fails SC1 — a planner must not choose it as the "safe" default.
3. **Alternative — interleave delta-read and write per sheet in one loop** (closer to the design-spec §4 pseudocode: `for sheet in registry.active: ... affected |= upsert_rows_bulk(...)`). Reduces two passes over `source_sheets` to one, but breaks `_run_memory_write_phase()`'s current documented contract ("Consumes rows ALREADY fetched this run... never issues its own Smartsheet call" `[VERIFIED: pipeline/orchestrate.py:394-395]`) — would need a new interleaved function rather than reusing the existing one, increasing surface area for a first cut.

**Affected-set UNION already includes the moved-week prior pair** `[VERIFIED: pipeline_memory/schema.sql:469-475]`:
```sql
    SELECT c.wr, c.week_ending
    FROM changed AS c
    UNION
    SELECT c.wr, c.prior_week_ending
    FROM changed AS c
    WHERE c.prior_week_ending IS NOT NULL
      AND c.prior_week_ending IS DISTINCT FROM c.week_ending;
```
This is already server-side and requires no Python change — D-04 explicitly calls this out as "already the server-side UNION."

**`row_state` columns available for the mapping query** `[VERIFIED: pipeline_memory/schema.sql:100-129]` (quoted): the table has `sheet_id BIGINT NOT NULL`, `row_id BIGINT NOT NULL`, `wr TEXT NOT NULL`, `week_ending DATE`, plus `PRIMARY KEY (sheet_id, row_id)` and `CREATE INDEX IF NOT EXISTS idx_row_state_wr_week ON pipeline_memory.row_state (wr, week_ending);`. No schema change is needed for the mapping query (D-04: "Zero schema change").

**`units_completed` is already a hash field — no special case needed** `[VERIFIED: pipeline_memory/writer.py:460-477]` (`HASH_FIELDS` tuple includes `"units_completed"` at position 9 of 16). D-04's note that "un-accepted rows... are an ordinary content-hash diff, not a special case" is directly confirmed by this tuple.

### Pattern 3: Shadow-incremental parity proof (D-07/D-08, INC-04)

**What:** While `RUN_MEMORY_INCREMENTAL_ENABLED` is OFF, every full run additionally computes what incremental *would* have selected (from this run's own affected set) and compares it to what full mode actually regenerated.

**Data available at the comparison hook** `[VERIFIED: pipeline/orchestrate.py:615-676]` — `_build_group_state_flush` is the existing function closest to the comparison point; its inputs are `deferred_records` (per group: `group_key`, `wr_num`, `week_iso`, `variant`, `identifier`, `data_hash`, `row_count` — built earlier in the group loop), `group_upload_ok` (dict `group_key -> bool`, i.e. "was this group actually regenerated/uploaded this run"), `upload_tasks`, and `attachment_side_channel`. The per-group hash itself is computed earlier at `calculate_data_hash(group_rows)` `[VERIFIED: pipeline/orchestrate.py:1810]`. For the shadow comparison: candidate set = `_mem_affected` (from `_run_memory_write_phase`, already computed at `orchestrate.py:929`); actual set = the group keys for which `group_upload_ok[group_key]` is true (or more precisely, every group whose `data_hash` differed from its stored `group_state.content_hash`/`hash_history` value this run — the regenerate decision, not just the upload-success flag). Comparing **candidate set == actual set** (group-key equality) and, for the intersection, **candidate hash == actual hash** (both already `calculate_data_hash()` output) satisfies D-07's (a) and (b) without a second Excel/openpyxl pass.

**"Never a vacuous PASS" discipline** (from the parity-proof ADVISOR file, matching Phase 10's `compare_control_run.py` precedent `[CITED: 11-ADVISOR-parity-proof-harness.md]`): the shadow block must prove it actually ran (non-zero groups compared, non-zero delta-read rows) before reporting `pass`; any failure inside the sub-budgeted block (mirroring `RUN_MEMORY_WRITE_MAX_MINUTES`'s pattern) must report `skipped` with a reason, never a silent `pass`.

**Sub-budget pattern to mirror exactly** `[VERIFIED: pipeline/config.py:471-490]` (quoted):
```python
RUN_MEMORY_WRITE_MAX_MINUTES = int(
    os.getenv('RUN_MEMORY_WRITE_MAX_MINUTES', '10') or 10
)
RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC = int(
    os.getenv('RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC', '45') or 45
)
RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN = int(
    os.getenv('RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN', '2') or 2
)
```
And the pre-flight guard shape it mirrors `[VERIFIED: pipeline/orchestrate.py:437-469]` — elapsed → remaining → required (`RUN_MEMORY_WRITE_MAX_MINUTES + RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN`) → skip-with-WARNING-and-Sentry-breadcrumb if insufficient. `RUN_MEMORY_SHADOW_MAX_MINUTES` / `RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC` / `RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN` should be named analogously (Claude's Discretion, D-08).

**Verdict persistence location** — `run_ledger.notes` JSONB, never `run_summary.json`. `run_ledger.mode` CHECK already allows exactly the values needed `[VERIFIED: pipeline_memory/schema.sql:227-242]` (`"mode TEXT NOT NULL CHECK (mode IN ('incremental', 'full', 'targeted'))"`); `notes JSONB` and `sheets_changed INT` are also already columns.

### Pattern 4: Retirement ordering (D-12, INC-05)

**What:** Local JSON caches and attachment pre-fetch retire only after the D-09 streak, as their own PR.

**Cache steps that persist rollback state across runs** `[VERIFIED: .github/workflows/weekly-excel-generation.yml:165-186,771-793]` — three `actions/cache/restore@v4` + `actions/cache/save@v4 if: always()` pairs for `generated_docs/hash_history.json`, `generated_docs/discovery_cache.json`, `generated_docs/billing_audit_frozen_rows.json`. The `if: always()` on save is deliberate — "these `if: always()` saves exist precisely so a failed run keeps cache state" (D-12 verbatim). These three steps plus `ATTACHMENT_PREFETCH_MAX_MINUTES`/`ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` (`pipeline/config.py:116-120`) and the two attachment pre-fetch blocks (`orchestrate.py:1115-1196` target-row prefetch, `~1292-1445` PPP prefetch) are the INC-05 retirement scope — none of them are touched in Phase 11 itself.

### Anti-Patterns to Avoid

- **Filtering after a full fetch instead of scoping the fetch itself** (Option 2 above): satisfies nothing measurable in ROADMAP SC1 (`rows_seen ≪ 208k`). Do not accept this as "good enough for a first cut."
- **Letting end-of-run maintenance iterate `groups.items()` unconditionally in incremental mode**: silently deletes hash-history entries and Smartsheet attachments for every group not touched this run (see Common Pitfalls below — this is the single highest-severity risk in this phase).
- **Persisting `now − SAFETY_WINDOW` instead of the capture-time value**: explicitly superseded by D-01. The design-spec draft's pseudocode does this at line 162 `[VERIFIED: docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md:162]` (`"registry.update(sheet, version=s.version, last_read_at=now - SAFETY_WINDOW)"`) — do not copy this line into new code; it compounds the overlap every run.
- **Treating a missing scenario/probe as a PASS** for the D-09 streak or the D-07 shadow verdict — must be `undetermined`/`skipped`, per the Phase 10 precedent `[CITED: STATE.md — "MEM-04 verdict derivation is undetermined-unless-fully-evidenced"]`.
- **Reusing `pipeline_memory/writer.py` for read queries.** The module's own docstring scopes it to writes (`"Supabase pipeline_memory writer."` `[VERIFIED: pipeline_memory/writer.py:1]`); no `SELECT`/read helper exists in `pipeline_memory/client.py` today `[VERIFIED: pipeline_memory/client.py function list — get_client, with_retry, _write_enabled, _client_options, _classify_postgrest_error, _disable_for_run; no read/query function present]`. A new `reader.py` (or equivalently named module) is genuinely new surface, not a gap in an existing one.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Preserve attachments/hash-history for groups not processed this run" | A new incremental-mode-specific skip flag threaded through `cleanup_untracked_sheet_attachments` | `KEEP_HISTORICAL_WEEKS` (`pipeline/config.py:578`, consumed at `pipeline/cleanup.py:429`) | This flag already exists for exactly this semantic ("Preserve attachments for weeks not processed this run" `[VERIFIED: pipeline/config.py:578]`) but defaults False and is currently unused for incremental scoping. Passing `keep_historical=True`-equivalent at the incremental-mode call site reuses tested code instead of writing a parallel gate. |
| "Don't prune hash-history for groups we didn't reach this run" | A separate incremental-mode conditional around the stale-key prune block | Extend the **existing** `if not _time_budget_exceeded:` guard (`orchestrate.py:3169`) to `if not _time_budget_exceeded and mode == 'full':` | The code's own comment already states the identical rationale for the existing guard: `"Only prune on FULL runs (not time-budget-truncated runs) to avoid deleting entries for groups that simply weren't reached this run"` `[VERIFIED: pipeline/orchestrate.py:3166-3168]`. Incremental mode is the same class of "didn't reach every group" as a time-budget-truncated run — reuse the guard's reasoning, not new logic. |
| Change-detection hashing for the shadow comparator | A second/simplified hash function for the parity check | `pipeline.change_detection.calculate_data_hash()` (already computed in the group loop at `orchestrate.py:1810`, before the comparator would need it) | Building a second hash risks the two hashes drifting (e.g. one honoring `EXTENDED_CHANGE_DETECTION`, one not) and comparing apples to oranges — a false parity PASS or FAIL neither of which reflects real divergence. |
| Retry/backoff for the new delta-read call | A parallel retry loop for `if_version_after`/`rows_modified_since` | `pipeline.retry.smartsheet_call_with_retry` (already wraps the existing `client.Sheets.get_sheet` call at `pipeline/fetch.py:247-252`) | Consistent 429/backoff handling, consistent Sentry span (`smartsheet.api`) naming, consistent behavior under the existing `PARALLEL_WORKERS ≤ 8` cap. |
| Sub-budget / pre-flight-guard mechanics for the shadow block | New timing/threshold logic | The `ATTACHMENT_PREFETCH_*` / `RUN_MEMORY_WRITE_*` elapsed→remaining→required pattern (`pipeline/orchestrate.py:437-469`, `1122-1153`) | Two prior sub-budget implementations already exist, tested, and battle-proven against `TIME_BUDGET_MINUTES=165`; a third one should be a copy of the pattern, not a new design. |

**Key insight:** almost everything this phase needs to *build* is small (a delta-read variant, a mapping query, a mode-resolution function, a comparator). Almost everything it needs to *change* is a **gate**, not new logic — and in two of the highest-risk cases (`KEEP_HISTORICAL_WEEKS`, the `_time_budget_exceeded` guard) the gate mechanism already exists in the codebase for a conceptually identical reason and only needs to be pointed at the new `mode` variable.

## Common Pitfalls

### Pitfall 1: End-of-run maintenance treats "not in this run's `groups`" as "delete it" (CRITICAL)

**What goes wrong:** In incremental mode, `groups` (per D-04) will contain only the affected subset. Three blocks in `orchestrate.py` build their "what's still live" set directly from `groups.items()` with no other source of truth:
- `valid_wr_weeks` builder `[VERIFIED: pipeline/orchestrate.py:2912-2993]` — iterates every `key, group_rows in groups.items()` to build the 4-tuple set passed to `cleanup_untracked_sheet_attachments`.
- Two `cleanup_untracked_sheet_attachments` call sites `[VERIFIED: pipeline/orchestrate.py:3054-3067 (TARGET_SHEET_ID), 3109-3146 (SUBCONTRACTOR_PPP_SHEET_ID)]`, both passed `valid_wr_weeks`.
- The hash-history stale-key prune `[VERIFIED: pipeline/orchestrate.py:3164-3259]`: `current_keys` is built the same way (`for key, group_rows in groups.items():`, line 3171), and `stale_keys = [k for k in hash_history if k not in current_keys]` (line 3254) then **deletes** every hash-history key not in `current_keys` (lines 3255-3257), gated only by `if history_updates:` (line 3165) and `if not _time_budget_exceeded:` (line 3169) — neither of which is incremental-mode-aware today.

**Why it happens:** These blocks were written when `groups` always meant "every currently-valid group" (the only mode that existed). D-04 changes that invariant for incremental mode without any of these three call sites being told.

**How to avoid:** Gate all three per the Don't-Hand-Roll entries above — pass `KEEP_HISTORICAL_WEEKS=True`-equivalent into both `cleanup_untracked_sheet_attachments` calls when `mode == 'incremental'`, and extend the stale-key prune's existing `_time_budget_exceeded` guard to also require `mode == 'full'`. Verify with a dedicated regression test asserting zero deletions/prunes when `mode == 'incremental'` and `groups` is a strict subset of `hash_history`'s keys.

**Warning signs:** A live incremental run's Smartsheet attachment count for an untouched WR/week drops to zero, or `hash_history.json` shrinks between two incremental runs with no corresponding `RESET_*` flag set. `run_ledger.mode='incremental'` combined with a `groups_total` in `run_summary.json` far smaller than the historical average is the leading indicator to alert on (D-11: "Scoped counters are reported with `run_ledger.mode = 'incremental'` so the numbers are never mistaken for a full run's").

### Pitfall 2: The off-contract/legacy-migration cleanup gates are ALREADY naturally scoped — don't over-fix them

**What goes wrong:** A naive reading of `pipeline/cleanup.py`'s docstring (7 different `valid_wr_weeks`-exemption gates for Subprojects B/C/D legacy-attachment migrations, lines ~250-390) suggests every one of them needs an incremental-mode audit.

**Why it isn't actually dangerous:** Each of these gates is additionally conditioned on `wr in sub_wr_scope` (or `vac_legacy_wr_scope`/`primary_wr_scope`) `[VERIFIED: pipeline/cleanup.py:261-269]` — and those scope sets are themselves built from `groups` at the call site (`_build_subcontractor_wr_scope(groups)` etc., `orchestrate.py:3018-3053`). In incremental mode, a WR not in this run's `groups` is *also* not in `sub_wr_scope`, so these specific gates never fire for it — they are safe by construction, unlike the bare `identity_groups`-prune (Pitfall 1) which iterates every attachment on the sheet regardless of scope.

**How to avoid:** Don't spend planning/execution effort re-gating these 7 sites individually; verify (with a test) that they're already correctly scoped via `sub_wr_scope`/`vac_legacy_wr_scope`/`primary_wr_scope`, and focus the fix effort on the `KEEP_HISTORICAL_WEEKS` gate (Pitfall 1) instead.

**Warning signs:** A code review that "fixes" these 7 sites with new incremental-mode conditionals is doing unnecessary, risk-adding surgery on already-safe code — watch for scope creep here specifically.

### Pitfall 3: Abbreviated-response detection has no production precedent

**What goes wrong:** `_fetch_and_process_sheet` (`pipeline/fetch.py:178-...`) has zero existing handling for a `Sheet` object without usable `rows` — it iterates `for row in sheet.rows:` unconditionally (`fetch.py:326`). The only place abbreviated-response detection exists today is the **experiment script** (`scripts/mem04_experiment.py:351`), which checks a serialized **dict** (`"rows" not in t2_capture["raw_response"]`), not the live SDK object.

**Why it happens:** Phase 10 only needed to *prove* the SDK behavior (via the experiment script); it never needed production code to *branch* on it.

**How to avoid:** Write a small, directly-unit-tested helper (e.g. `_is_abbreviated_response(sheet) -> bool`) that checks the live `Sheet` object (likely `getattr(sheet, 'rows', None) is None`, but this must be verified against a real abbreviated response or SDK source before being trusted — `[ASSUMED]`, not yet confirmed against the live object shape). Add a fixture/cassette test mirroring `mem04_experiment.py`'s captured cassettes (`tests/fixtures/mem04/*.json`) so this detection has the same evidence discipline MEM-04 already established.

**Warning signs:** An `AttributeError: 'NoneType' object has no attribute ...` (or similar) the first time a delta-read call actually receives an abbreviated response in a real run — this is exactly the kind of "worked in every test because the fixture always had rows" failure the fixture design should pre-empt.

### Pitfall 4: `run_summary.json`'s existing `"mode"` key means something different from `run_ledger.mode`

**What goes wrong:** `run_summary.json` already has a `"mode"` key `[VERIFIED: tests/golden/run_summary_baseline.json:16]` (`"mode": "PRODUCTION"`) — sourced from `"mode": "TEST" if TEST_MODE else "PRODUCTION"` `[VERIFIED: pipeline/orchestrate.py:3320]`. The NEW `run_ledger.mode` (`incremental`/`full`/`targeted`) is a completely different axis. Anyone reading `run_summary.json` for "was this an incremental run?" will find nothing — by design (D-11: `run_summary.json` is not touched), but this is easy to miss.

**Why it happens:** Two independently-evolved "mode" concepts (TEST_MODE vs. Supabase run_ledger.mode) now coexist with the same JSON key name in one artifact and a different column name in another.

**How to avoid:** Document this explicitly in the phase's runbook/`configuration-environment.md` update so operators/dashboards know to check `run_ledger.mode` (Supabase) for incremental-vs-full, never `run_summary.json.mode` (which stays PRODUCTION/TEST forever).

**Warning signs:** A support runbook or dashboard query that filters `run_summary.json` on `mode` expecting to find "incremental" and gets nothing.

### Pitfall 5: WR-01 — unparsed numerics silently drop whole chunks under fail-open

**What goes wrong:** `_row_to_payload` sends raw cell values straight through: `"quantity": row_data.get("Quantity"), "units_total_price": row_data.get("Units Total Price"),` `[VERIFIED: pipeline_memory/writer.py:622-623]`. `upsert_rows_bulk`'s SQL RPC declares these as `NUMERIC` `[VERIFIED: pipeline_memory/schema.sql:307-308]` (`"quantity NUMERIC, units_total_price NUMERIC,"`). A decorated value like `"$1,234.50"` or `"12 ea"` fails the Postgres NUMERIC cast; under the fail-open contract, the **entire 500-row chunk** silently drops (todo file, quoted: `"A decorated value (\"$1,234.50\", \"12 ea\") fails the Postgres cast and, under fail-open, drops the whole 500-row chunk silently."` `[CITED: .planning/todos/pending/2026-08-25-run-memory-review-followups.md]`).

**Why it happens:** The engine's own parsers (`parse_price()`, `_parse_quantity()`) were never wired into the memory-writer payload builder — they live in a different module (`pipeline/pricing.py`) that `pipeline_memory` deliberately does not import (package-boundary contract).

**How to avoid:** This is Phase 11 plan 01 per D-10. Fix: import and call `pipeline.pricing.parse_price`/`_parse_quantity` inside `_row_to_payload` for the `units_total_price`/`quantity` fields (this is the ONE place `pipeline_memory` may need to cross its "imports nothing from pipeline.*" boundary, or the values must be pre-parsed by the caller in `orchestrate.py` before being handed to `upsert_rows_bulk` — the caller-resolves-then-passes pattern already used for `week_ending`/`snapshot_date` via `__mem_week_ending`/`__mem_snapshot_date` `[VERIFIED: pipeline/orchestrate.py:489-495]` is the safer option, preserving the package boundary). Add a regression test with decorated inputs (`"$1,234.50"`, `"12 ea"`) asserting a valid NUMERIC payload is sent.

**Warning signs:** `rows_upsert_errored` counter spikes for a sheet with known price-decoration in its source data (e.g. a sheet where `Units Total Price` sometimes carries a currency symbol from a Smartsheet formula).

**Exact functions to reuse** `[VERIFIED: pipeline/pricing.py:91-129 (_parse_quantity), 132-146 (parse_price)]`:
```python
def _parse_quantity(qty_raw: "str | float | int | None") -> float:
    ...
def parse_price(price_str: str | float | int | None) -> float:
    """Safely convert a price string to a float. ...
    Returns:
        float: Parsed price value, or 0.0 if parsing fails
    """
```

### Pitfall 6: `column_mapping` drift detection (D-02 trigger 2) requires a new comparison, not an existing one

**What goes wrong:** D-02's second full-read trigger is "`column_mapping` drift detected during validation." No code path today compares a freshly-discovered `column_mapping` against `sheet_registry.column_mapping` — `pipeline_memory`'s only registry write is `upsert_sheet_registry` (`pipeline_memory/writer.py:287-358`), an unconditional upsert with no read-back/compare step, and there is no reader function in `pipeline_memory/client.py` to fetch the stored value for comparison (confirmed function inventory: `get_client`, `with_retry`, `_write_enabled`, `_client_options`, `_classify_postgrest_error`, `_disable_for_run` — no SELECT helper) `[VERIFIED: pipeline_memory/client.py function definitions, grep confirmed no read/select function present]`.

**Why it happens:** Phase 10 was write-only shadow mode by design (COVERAGE.md OPT-OUT: `"table:sheet_registry SELECT (drive discovery from memory) | OPT-OUT | Discovery stays on discovery_cache.json this phase"` `[VERIFIED: .planning/phases/10-run-memory-foundation-shadow-writes/COVERAGE.md]`).

**How to avoid:** This drift check needs a new `pipeline_memory/reader.py` function reading `sheet_registry.column_mapping` for the sheet, compared (dict equality) against the value `discover_source_sheets()`/`_validate_single_sheet()` just produced this run. Budget this as new surface, not a gate on existing logic.

**Warning signs:** A column-mapping change (e.g. a renamed Smartsheet column) silently continues under a stale mapping in incremental mode because this trigger was never wired.

## Code Examples

### Delta read + abbreviated-response detection (pattern to implement, adapted from the proven experiment probe)

```python
# Source: pattern verified against scripts/mem04_experiment.py:344-362
# and pipeline/fetch.py:247-267 (existing full-read call site + retry wrapper)
def _fetch_sheet_delta(client, source, last_sheet_version, last_read_at_minus_window):
    sheet = smartsheet_call_with_retry(
        client.Sheets.get_sheet,
        source['id'],
        if_version_after=last_sheet_version,
        label=f"delta-probe sheet {source['name']}",
    )
    if getattr(sheet, 'rows', None) is None:   # [ASSUMED] verify against a
        return None                             # real abbreviated response
    sheet = smartsheet_call_with_retry(
        client.Sheets.get_sheet,
        source['id'],
        rows_modified_since=last_read_at_minus_window,
        column_ids=",".join(str(c) for c in source['column_mapping'].values()),
        label=f"delta-read sheet {source['name']}",
    )
    return sheet
```

### Affected-set → sheet mapping (new query; no schema change)

```sql
-- Source: pattern derived from pipeline_memory/schema.sql:100-129
-- (row_state columns + idx_row_state_wr_week index), read-only, new query
SELECT DISTINCT sheet_id
FROM pipeline_memory.row_state
WHERE (wr, week_ending) IN (
    -- one (wr, week_ending) pair per row from the affected set
    ($1, $2), ($3, $4), ...
);
```

### Reusing `KEEP_HISTORICAL_WEEKS` for incremental-mode cleanup safety

```python
# Source: pipeline/cleanup.py:429 (existing gate, verbatim)
#   if ident not in valid_wr_weeks and KEEP_HISTORICAL_WEEKS:
#       continue
# Pattern: at the incremental-mode call site in orchestrate.py, pass the
# equivalent of KEEP_HISTORICAL_WEEKS=True for this call only (do not
# flip the global env-driven constant — override at the call boundary,
# e.g. a new keep_historical: bool parameter threaded through
# cleanup_untracked_sheet_attachments, defaulting to the existing
# module constant so full-mode behavior is unchanged).
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Full `Sheets.get_sheet(column_ids=...)` read of every sheet, every run (~208k rows) | Per-sheet `if_version_after` probe first; `rows_modified_since` only on a version bump | Phase 11 (this phase, not yet shipped) | INC-01's `rows_seen ≪ 208k` target; ~94min baseline frequent-run wall clock (run `32743959053`) is the before/after comparator D-12 requires. |
| `hash_history.json` / `discovery_cache.json` / `billing_audit_frozen_rows.json` local caches, restored/saved every run via GitHub Actions cache | `pipeline_memory.row_state`/`group_state`/`sheet_registry` durable Supabase store | Phase 10 (schema shipped, write OFF); local caches retired only after Phase 11's D-09 streak (D-12) | Removes 3 cache restore/save step pairs and the two attachment pre-fetch phases from the workflow, but NOT in this phase — INC-05 is its own later PR. |
| `row_state`/`group_state` written but never read back (observability only) | `upsert_rows_bulk`'s affected set becomes the scope selector for regeneration | Phase 11 (D-04, this phase) | The single largest behavior change this phase makes — Phase 10 explicitly OPT-ED OUT of this ("Reading memory back to drive a run... would make memory an input to a billing decision, which MEM-03 forbids" `[CITED: COVERAGE.md]`) precisely so Phase 11 could do it deliberately, with a parity gate. |

**Deprecated/outdated:** the design-spec draft's persist-time `last_read_at = now − SAFETY_WINDOW` (§4, line 162) is superseded by D-01's capture-time-then-filter-time-subtraction approach; do not resurrect it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The live SDK's abbreviated `Sheet` object exposes `rows` as `None` (or an equivalent falsy/absent state) rather than raising or omitting the attribute entirely — the experiment script only verified this against a serialized dict, not the live object. | Pattern 1, Pitfall 3, Code Examples | Delta-read code crashes with `AttributeError` on the first real abbreviated response in production, or (worse) silently misclassifies an abbreviated response as a full one and processes stale/empty data. |
| A2 | The three-option ordering-problem synthesis (Pattern 2) and its "RECOMMENDED" ranking is original analysis for this research session, not found pre-built in any prior plan/summary — no code currently implements any of the three options. | Pattern 2 | If the planner picks a materially different restructuring, the specific line-number call sites cited here for the PHASE 2a/2b split will not directly apply, though the underlying constraint (affected set needed before grouping, complete row set needed before grouping) still holds. |
| A3 | `KEEP_HISTORICAL_WEEKS`-equivalent behavior, when threaded into the incremental-mode `cleanup_untracked_sheet_attachments` call sites, is sufficient to prevent the Pitfall-1 deletion risk without also needing to touch the 7 off-contract/legacy-migration gates (Pitfall 2's claim that those are already safe by construction via `sub_wr_scope`/etc.). This is derived from reading the gate conditions, not from running a live incremental test. | Pitfall 1, Pitfall 2, Don't Hand-Roll | If `sub_wr_scope`/`vac_legacy_wr_scope`/`primary_wr_scope` are ever built from something OTHER than `groups` in a future change, this safety argument breaks silently. A regression test pinning "zero off-contract deletions for untouched WRs in incremental mode" would catch this early. |
| A4 | The hash-history stale-prune fix (extend `_time_budget_exceeded` guard to also require `mode == 'full'`) is semantically correct and sufficient — i.e., no *other* code path re-derives `current_keys` or independently prunes `hash_history` outside this one block. | Don't Hand-Roll, Pitfall 1 | An unaudited second prune site (not found in this research's grep sweep) could still delete historical entries in incremental mode. |
| A5 | Package-boundary preference for fixing WR-01 (caller pre-parses via `__mem_*` keys, mirroring the `week_ending`/`snapshot_date` pattern) over having `pipeline_memory` import `pipeline.pricing` directly — both are technically viable; this research recommends the caller-resolves pattern for consistency but does not mandate it. | Pitfall 5 | If the planner instead has `pipeline_memory` import `pipeline.pricing`, it's a one-line deviation from the stated "imports nothing from pipeline.*" boundary comment already in the codebase — worth a `checkpoint:decision` either way, not a blocking issue. |

## Open Questions

1. **Does the live Smartsheet SDK's abbreviated `Sheet` object actually expose `rows=None`, or does the attribute error / return an empty list?**
   - What we know: `scripts/mem04_experiment.py` confirms abbreviated detection works against a serialized dict (`"rows" not in raw_response`).
   - What's unclear: the live SDK object's attribute behavior in the abbreviated case — never exercised by production code.
   - Recommendation: add a Task 0/fixture step that captures one real abbreviated `Sheet` object's `dir()`/`hasattr` shape (reusing the existing MEM-04 sandbox rig) before writing the production detection helper.
   - **RESOLVED — plan 11-02 Task 1.** `tests/fixtures/incremental/abbreviated_sheet_response.json` pins the real abbreviated `Sheet` shape as a cassette (Wave 0 item), and `pipeline.fetch._is_abbreviated_response` uses a defensive falsy check rather than assuming `rows=None` — so the helper is correct whether the live SDK returns `None`, an empty list, or omits the attribute entirely. The cassette is the regression that keeps it correct if the SDK shape changes.

2. **Should the shadow comparator (D-07/D-08) live as a new top-level `pipeline/parity.py` module or a new `pipeline_memory/reader.py`-adjacent module?**
   - What we know: CONTEXT.md explicitly defers this to Claude's Discretion; `pipeline_memory` has a documented "imports nothing from pipeline.*" boundary that a comparator (which needs `calculate_data_hash` from `pipeline.change_detection`) would violate if placed inside `pipeline_memory/`.
   - What's unclear: whether the planner prefers a single `pipeline/parity.py` or a `pipeline/parity/` sub-package (this research recommends the latter only if the comparator plus its shadow-delta-read logic exceeds ~300-400 lines; otherwise a single module is simpler).
   - Recommendation: default to a single `pipeline/parity.py` module; split only if it grows large, following the same "hooks in orchestrate.py, logic elsewhere" pattern the writer-phase functions already establish.
   - **RESOLVED — plan 11-05 Task 2.** A single top-level `pipeline/parity.py` module holding `compare_shadow_parity` and `run_shadow_delta_reads`, with the hooks in `orchestrate.py`. This keeps the `pipeline_memory` "imports nothing from `pipeline.*`" boundary intact, since the comparator needs `calculate_data_hash` from `pipeline.change_detection`. No sub-package this phase.

3. **Exact wording/threshold for D-02 trigger 6 ("previous run status != 'success' or finished_at IS NULL")** — does this require a new `pipeline_memory/reader.py` query against `run_ledger` before every incremental run, and what happens if THAT read itself fails (memory outage during mode-resolution, not during the run itself)?
   - What we know: D-02 lists this as one of 7 triggers; `run_ledger` has `status`/`finished_at` columns already.
   - What's unclear: the fail-open behavior for the mode-resolution query itself (presumably: read failure ⇒ treat as "cannot confirm previous run succeeded" ⇒ fall back to full mode, consistent with the general fail-open contract, but not explicitly stated in D-02).
   - Recommendation: treat a mode-resolution-query failure as equivalent to trigger 4 (memory outage → full mode) since it is the same underlying failure class.
   - **RESOLVED — plan 11-02 Task 2.** `get_last_run_ledger_status` returns `None` on any read failure, and `resolve_run_mode` reads `None` as "cannot confirm the previous run succeeded" and fires trigger 6, escalating to a full read. The fail-open contract therefore covers the mode-resolution query itself, not just the run: a memory outage during mode resolution and a memory outage during the run both land in full mode.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Smartsheet API (SDK) | INC-01 delta reads | ✓ `[VERIFIED: requirements.txt]` | `smartsheet-python-sdk==4.3.0` | n/a — required; SDK already pinned and proven against MEM-04 |
| Supabase project `poeyztlmsawfoqlanucc` / `pipeline_memory` schema | INC-02/INC-04 affected-set + parity | ✓ (live since Phase 10, write OFF) `[CITED: STATE.md — "pipeline_memory live on Supabase (write path OFF in prod)"]` | schema version per `pipeline_memory/schema.sql` (unchanged this phase) | D-11: outage ⇒ automatic full-mode fallback (existing fail-open contract) |
| `RUN_MEMORY_WRITE_ENABLED` flip (production) | Every plan after plan 01 (D-10) | ✗ — not yet flipped; separate operator-gated PR | n/a | `checkpoint:human-verify` before the first plan needing populated memory |
| `pg_cron` on the Supabase project | Retention (`purge_row_event_slice`), unrelated to this phase's reads | Unverified as of Phase 10 (`10-CONTEXT.md` Open Question) | n/a | Not blocking for Phase 11 — retention runs independently of the read/regeneration path |

**Missing dependencies with no fallback:** none blocking Phase 11's planning — the write-flip is a known, already-scheduled precondition (D-10), not an unplanned gap.

**Missing dependencies with fallback:** Supabase outage during an incremental run already has a documented fallback (full mode, D-02 trigger 4).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (per `pytest tests/ -v`, project-wide convention) `[VERIFIED: CLAUDE.md — "Run Tests: pytest tests/ -v"]` |
| Config file | none dedicated — root `pytest.ini`/`pyproject.toml` not inspected this session; existing suite runs via `pytest tests/ -q` in `scripts/run_6_gates.sh:29` `[VERIFIED: scripts/run_6_gates.sh:28-29]` |
| Quick run command | `pytest tests/test_pipeline_memory_shadow.py tests/test_mem04_formula_change.py -v` |
| Full suite command | `pytest tests/ -v` (baseline: 1525 passed / 135 subtests per `11-CONTEXT.md` protected-areas note) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|-------------|
| INC-01 | Unchanged sheet costs one call, zero rows | unit | `pytest tests/test_incremental_read.py::test_abbreviated_response_skips_sheet -x` | ❌ Wave 0 |
| INC-01 | Abbreviated-response detection matches live SDK shape | unit + fixture | `pytest tests/test_incremental_read.py::test_abbreviated_response_detection_matches_cassette -x` | ❌ Wave 0 (new cassette fixture needed, see Open Question 1) |
| INC-02 | Affected set maps to correct sheet ids via `row_state` | unit | `pytest tests/test_pipeline_memory_shadow.py::AffectedSetMappingTests -x` | ❌ Wave 0 (new test class; `AffectedSetParsingTests` at line 1100 already tests the RPC-response parse, not the sheet-mapping query) |
| INC-02 | Scoped full re-fetch + grouping restricted to affected `(wr, week)` produces the same group content as full mode for that subset | integration | `pytest tests/test_incremental_read.py::test_scoped_regeneration_matches_full_mode -x` | ❌ Wave 0 |
| INC-02 (D-06) | Zero deletions/prunes for untouched groups in incremental mode | regression | `pytest tests/test_incremental_read.py::test_keep_historical_weeks_protects_untouched_groups -x` | ❌ Wave 0 — this is the single most important new test in the phase (Pitfall 1) |
| INC-03 | Weekly deep run detects a deleted row and repairs `row_state`/`group_state` | fixture + manual | `pytest tests/test_incremental_read.py::test_deep_run_detects_deletion -x` + one live verification (success criterion 3) | ❌ Wave 0 (new fixture under `tests/fixtures/incremental/`) |
| INC-03 | Weekly deep run detects a formula-only change | fixture (reuse MEM-04 cassettes) | `pytest tests/test_mem04_formula_change.py::RealCassetteVerdictTests -v` (existing, already PASS per 10-05-SUMMARY.md) | ✅ existing |
| INC-04 | Shadow parity: group-key set equality + per-group hash equality | unit | `pytest tests/test_parity_shadow.py::test_group_key_and_hash_equality -x` | ❌ Wave 0 |
| INC-04 | Never a vacuous PASS (skipped-with-reason on incomplete comparison) | unit | `pytest tests/test_parity_shadow.py::test_incomplete_comparison_never_passes -x` | ❌ Wave 0 |
| INC-04 | Streak query: pass/fail/skipped semantics over `run_ledger` | unit | `pytest tests/test_pipeline_memory_shadow.py::StreakQueryTests -x` | ❌ Wave 0 |
| WR-01 | Decorated numeric inputs (`"$1,234.50"`, `"12 ea"`) parse correctly before `upsert_rows_bulk` | unit | `pytest tests/test_pipeline_memory_shadow.py::BulkPayloadContractTests -v` (extend existing class at line 549) | ✅ class exists, add cases |
| WR-04 | `run_ledger.sheets_changed` populated | unit | `pytest tests/test_pipeline_memory_shadow.py -k sheets_changed -x` | ❌ Wave 0 |
| Sanity | `pytest tests/ -v` + `python -m py_compile generate_weekly_pdfs.py` gate holds | full suite | `pytest tests/ -v && python -m py_compile generate_weekly_pdfs.py` | ✅ existing (CLAUDE.md-mandated) |

### Sampling Rate

- **Per task commit:** the quick run command above (targeted memory + incremental test files).
- **Per wave merge:** `pytest tests/ -v` (full 1525+ suite) + `python -m py_compile generate_weekly_pdfs.py`.
- **Phase gate:** `bash scripts/run_6_gates.sh` (6 gates: AST import equality, facade completeness, pytest, mypy delta, py_compile, golden `run_summary` structure — `[VERIFIED: scripts/run_6_gates.sh:22-52]`) green, PLUS the ROADMAP's own success criteria (parity streak, live deletion/formula-change verification, wall-clock before/after) before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_incremental_read.py` — covers INC-01, INC-02, INC-03 (new file)
- [ ] `tests/test_parity_shadow.py` — covers INC-04 (new file)
- [ ] `tests/fixtures/incremental/deleted_row.json`, `tests/fixtures/incremental/formula_only_change.json` — INC-03 fixtures (new)
- [ ] `tests/fixtures/mem04/abbreviated_response.json` (or equivalent) — a real captured abbreviated-`Sheet` cassette to close Open Question 1, following the `tests/fixtures/mem04/mem04_blank_lookup.json` / `mem04_edit_mapping.json` precedent `[CITED: 10-05-SUMMARY.md]`
- [ ] `AffectedSetMappingTests`, `StreakQueryTests` — new test classes in `tests/test_pipeline_memory_shadow.py` (the file already has 19 test classes covering every other writer-side contract; these two are the read-side gap)

*(Framework install: none — `pytest` already the project standard, no new dependency.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no | No new auth surface; Smartsheet API token and Supabase service-role key are unchanged, already-provisioned secrets. |
| V3 Session Management | no | Batch job, no sessions. |
| V4 Access Control | yes | New `SELECT` queries against `pipeline_memory.row_state`/`run_ledger` must go through the same `service_role`-only client (`pipeline_memory/client.py::get_client()`) already locked down by RLS + explicit `REVOKE ALL ... FROM anon, authenticated` `[VERIFIED: pipeline_memory/schema.sql:503-551]`. No new grant is needed for `service_role` (it already has `SELECT` on all tables in the schema — `[VERIFIED: pipeline_memory/schema.sql:494-495]`, `"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA pipeline_memory TO service_role;"`). |
| V5 Input Validation | yes | The new mapping query must use parameterized `IN (...)` construction (via the `supabase-py` client's query builder or an RPC with a typed `jsonb_to_recordset`/array parameter, mirroring `upsert_rows_bulk`'s existing typed-recordset pattern `[VERIFIED: pipeline_memory/schema.sql:299-319]`), never string-interpolated SQL — the affected set is derived from Smartsheet cell content and must be treated as untrusted for query-construction purposes even though it currently only feeds a read. |
| V6 Cryptography | no | No new cryptographic operation; `calculate_data_hash()` (SHA-256, unchanged) is reused as-is, not implemented fresh. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| SQL injection via the affected-set → sheet mapping query | Tampering | Use Postgres RPC with typed parameters (array/`jsonb_to_recordset`) exactly as `upsert_rows_bulk` already does — never build a raw `WHERE (wr, week_ending) IN (...)` string by interpolation. |
| Silent data loss (destructive) via the D-06 cleanup/prune consumers | Tampering / (unintentional) Denial of Service on billing data | Explicit incremental-mode gates per Pitfall 1 — this is the phase's dominant threat, not an external attacker; the "STRIDE" framing here is "our own code deletes live billing attachments" not an adversary. |
| Fail-open masking a real error as "nothing changed" | Repudiation (of the failure itself) | Preserve the existing fail-open contract's counters (`rows_upsert_errored`, etc.) and extend it: a delta-read failure must fall back to full mode (D-02 trigger 4), never silently skip the sheet as if unchanged. |
| Elevation via the exposed `pipeline_memory` schema (already mitigated in Phase 10) | Elevation of Privilege | No new exposure this phase — the existing RLS + REVOKE posture (`schema.sql:502-551`) already covers the new read queries since they use the same `service_role` client. |

## Sources

### Primary (HIGH confidence — read directly this session)
- `pipeline_memory/schema.sql` (full file, 618 lines) — table DDL, RPC, RLS/GRANT/REVOKE, retention.
- `pipeline_memory/writer.py` (full file, 744 lines) — `HASH_FIELDS`, `_row_to_payload`, `upsert_rows_bulk`, `run_ledger_start/finish`, `upsert_group_state`.
- `pipeline_memory/client.py` (function inventory via grep) — confirmed no read/query helper exists.
- `pipeline/config.py` (full file, 589 lines) — `RUN_MEMORY_WRITE_*`, `ATTACHMENT_PREFETCH_*`, `KEEP_HISTORICAL_WEEKS`.
- `pipeline/fetch.py` (lines 80-360) — `get_all_source_rows`, `_fetch_and_process_sheet`, `_is_auth_api_error`, `client.Sheets.get_sheet` call site.
- `pipeline/change_detection.py` (lines 1-140) — `calculate_data_hash()`.
- `pipeline/orchestrate.py` (lines 360-700, 820-1050, 1100-1200, 1780-1950, 2600-2670, 2900-3070, 3069-3200, 3250-3400) — `_run_memory_write_phase`, PHASE 1/2, group loop, attachment pre-fetch, cleanup/prune blocks, `run_ledger_finish`, `run_summary.json` write.
- `pipeline/cleanup.py` (lines 90-130, 240-280, 395-520) — `cleanup_untracked_sheet_attachments`, `KEEP_HISTORICAL_WEEKS` gate, `delete_old_excel_attachments`.
- `pipeline/pricing.py` (lines 85-165) — `_parse_quantity`, `parse_price`.
- `scripts/mem04_experiment.py` (lines 290-380) — T2/T3a/T3b probe implementation.
- `.github/workflows/weekly-excel-generation.yml` (lines 150-260, 760-800) — execution-type step, cache restore/save, env block.
- `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md` (§4, lines 147-226) — run algorithm, superseded persist-time line.
- `.planning/phases/10-run-memory-foundation-shadow-writes/COVERAGE.md` (line 33 + surrounding) — deletion-reconciliation OPT-OUT.
- `.planning/phases/10-run-memory-foundation-shadow-writes/10-05-SUMMARY.md`, `10-06-SUMMARY.md` (heads) — MEM-04 PASS verdict, real-run parity lessons.
- `.planning/todos/pending/2026-08-25-run-memory-review-followups.md` (full) — WR-01/WR-04/IN-01 detail.
- `tests/golden/run_summary_baseline.json` (full, 22 lines / 21 keys + PID marker) — frozen contract enumeration.
- `scripts/run_6_gates.sh` (full, 52 lines) — 6-gate harness commands.
- `tests/test_pipeline_memory_shadow.py`, `tests/test_mem04_formula_change.py` (class-name inventory via grep) — existing test surface.
- `requirements.txt` (grep) — exact pinned versions.
- `.planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md` (full) — D-01..D-12, canonical refs.
- `.planning/phases/11-incremental-read-affected-group-regeneration/11-ADVISOR-*.md` (all 4, full) — alternatives-considered tables reproduced in Architecture Patterns.
- `.planning/REQUIREMENTS.md` (lines 220-268) — INC-01..INC-05 text.
- `.planning/STATE.md` (full) — project history, Phase 10 close, live-schema confirmation.

### Secondary (MEDIUM confidence)
- `11-ADVISOR-*.md` files' own citation of "official docs" for the abbreviated-Sheet-response behavior (advisor-researcher output, not independently re-verified against Smartsheet's public API docs this session).

### Tertiary (LOW confidence / flagged for validation)
- The abbreviated `Sheet` object's live attribute shape (`rows=None` vs. attribute-absent) — see Assumption A1 / Open Question 1.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; all versions read directly from `requirements.txt`.
- Architecture: HIGH for what exists (schema, writer, existing fetch/orchestrate code, all read directly); MEDIUM for the ordering-problem synthesis (Pattern 2, Assumption A2) since no code implements it yet — it is this session's design proposal, not a discovered fact.
- Pitfalls: HIGH for Pitfalls 1, 2, 4, 5, 6 (all directly traced to specific verified line numbers); MEDIUM for Pitfall 3 (the fix approach is sound but the exact SDK attribute behavior is unverified — Assumption A1).

**Research date:** 2026-08-26
**Valid until:** 30 days (stable internal codebase; re-verify sooner if `pipeline/orchestrate.py`, `pipeline_memory/schema.sql`, or the `smartsheet-python-sdk` pin change before planning starts).
