# Phase 2: Attribution Bulk-Prefetch + Historical Claimer Remediation - Research

**Researched:** 2026-05-26
**Domain:** Supabase/PostgREST bulk RPC design + Python billing pipeline read-side refactor + production Smartsheet attachment remediation
**Confidence:** HIGH (codebase + locked decisions); MEDIUM (Supabase jsonb payload sizing — no single hard published limit, cross-verified ~1 MB)

## Summary

This phase is **already heavily designed** (6 locked SPEC requirements + 14 locked decisions D-01..D-14). The job is not to redesign but to surface the technical unknowns the planner must resolve and define the Validation Architecture. The change is **read-side only**: replace four per-row `lookup_attribution` Supabase RPC pre-pass sites in `generate_weekly_pdfs.py` with ONE bulk in-memory load of `billing_audit.attribution_snapshot`, remove the `ATTRIBUTION_RESOLUTION_WEEKS=8` week-scope that was silently gating group-KEY/filename formation (the root cause), then remediate a ~26-week window of already-corrupted (`_NO_MATCH` / `_Unknown_Foreman`) attachments and re-activate Sub-project E behind an operator gate.

The existing code provides every primitive needed: `resolve_claimer` / `ResolveOutcome` / `ROLE_BY_VARIANT` (the use/HOLD decision table, reused verbatim), `with_retry` + per-op circuit breaker + `_classify_postgrest_error` (the fail-safe machinery, reused with a DISTINCT op id), the `lookup_attribution` RPC's `#NO MATCH`/blank → NULL CASE normalization (reused server-side, one source of truth), `build_group_identity` (the filename parser the garbage sweep keys on), and `cleanup_untracked_sheet_attachments` (the live-identity-exempt deletion precedent). The four pre-pass blocks are near-identical in shape — collapsing them to a single shared prefetch is a clean, surgical refactor.

**Primary recommendation:** Add `lookup_attribution_bulk(p_wr_weeks jsonb)` to `schema.sql` (LATERAL `jsonb_to_recordset` join, reusing the existing per-role CASE) + a fail-safe `prefetch_attribution(pairs)` reader in `writer.py` (DISTINCT op id `lookup_attribution_bulk`, chunked at ~500 `(wr,week)` pairs/payload with sequential or ≤8-worker parallel chunks) that returns a `(wr, week_ending, smartsheet_row_id) → frozen-roles-dict` map; make `resolve_claimer` map-aware via an optional `prefetched_map` param that short-circuits the per-row RPC; build the map ONCE at the top of `group_source_rows` from the run's exact `(wr,week)` set; drive remediation through a NEW default-OFF env-gated dry-run-first mode that name-pattern-sweeps `*_NO_MATCH*` / `*_Unknown_Foreman*` attachments with the live-identity exemption.

## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01 .. D-14 — research THESE, not alternatives)

- **D-01 — New bulk RPC.** Add `lookup_attribution_bulk(p_wr_weeks jsonb)` to `billing_audit/schema.sql` + a matching reader in `writer.py`. Returns all matching `attribution_snapshot` rows in one round-trip, applying the SAME server-side `#NO MATCH`/blank → NULL per-role CASE the single-row RPC does (do NOT replicate CASE in Python). DDL co-ships in the same PR (schema-co-ship rule). **Operator deploy + PostgREST schema-cache reload required at merge.** Rejected: direct table SELECT.
- **D-02 — Load the exact run `(wr, week_ending)` set.** Bounded to exactly the pairs this run discovered/grouped — NOT a recency superset (a superset reintroduces the exact bug). Chunk if one payload is too large (planner decision).
- **D-03 — Map-aware resolver, keep Foundation A contract.** Add `prefetch_attribution(pairs)` returning a map keyed by `(wr, week_ending, smartsheet_row_id)` → frozen-roles row. `resolve_claimer` reads a preloaded map (optional `prefetched_map` param OR thin sibling resolver — planner picks) instead of per-row RPC. use/`no_history`/`disabled`/`fetch_failure`(HOLD) table + `ROLE_BY_VARIANT` preserved EXACTLY.
- **D-04 — Bulk-load total-failure = preserve existing per-variant policy.** Whole-RPC failure → affected keys treated as `fetch_failure`; `resolve_claimer` applies each variant's existing policy: Sub-project D (production primary) → use-current (never HOLD); Sub-projects B (sub primary) + C (vac_crew) → HOLD. Do NOT invent "HOLD the whole run".
- **D-05 — Drop `ATTRIBUTION_RESOLUTION_WEEKS` entirely.** Remove env read (~L638-647), all four `_attribution_week_in_scope` gates (~L5492/5565/5657/6203), `_attribution_resolution_cutoff` (L5335) + `_attribution_week_in_scope` (L5354) helpers, startup banner (L839-840), workflow `env:` pin, `environment.md` entry, and `tests/test_attribution_resolution_scope.py` (delete OR repurpose — planner picks).
- **D-06 — Dedicated env-gated one-shot remediation mode.** Default-OFF flag (e.g. `REMEDIATE_CLAIMERS=1`; final name = planner) — ISOLATED from cron generation, own logging/counters/dry-run. Rejected: reusing `REGEN_WEEKS` + generic cleanup.
- **D-07 — Name-pattern garbage sweep.** Within the window, delete ONLY `*_NO_MATCH*` / `*_Unknown_Foreman*` attachments (TARGET + PPP). Must respect the live-identity exemption ([2026-05-19 23:45]).
- **D-08 — Dry-run-first + env-configurable window.** Window env-configurable (default ~26 weeks / ~6 months). First invocation report-only (logs counts of would-regenerate + would-delete), operator reviews, re-runs to execute. Default-OFF so it never fires on cron.
- **D-09 — Order: fix → validate → flip `AUTHORITATIVE=1` → remediate.** Land fix with `AUTHORITATIVE=0`; validate clean run; flip to `1`; THEN remediate (regenerated files are clean-named, no token→clean double-churn).
- **D-10 — Validation gate = an acceptance-criteria run** (evidence-based, not spot-check): zero garbage names for rows w/ frozen claimer; HTTP request count O(distinct bulk queries) vs ~137k; runtime ≤165 min; `pytest tests/` green incl. RED-before/GREEN-after regression.
- **D-11 — The `AUTHORITATIVE=1` flip is a gated operator follow-up.** Phase ships fix + remediation mode + re-activation runbook; the one-line workflow change is a SEPARATE operator action after a green D-10 run (NOT auto-committed in the fix PR).
- **D-12 — New flags:** default-ON for fixes-as-default, default-OFF for destructive remediation; PINNED in workflow `env:` + surfaced in startup banner.
- **D-13 — Bulk reader stays fail-safe:** reuse `with_retry` + per-op circuit breaker + `_classify_postgrest_error` with a DISTINCT op id (`lookup_attribution_bulk`) — op-isolation invariant.
- **D-14 — Preserve ALL CR-01 four-site identity lockstep + mirror-matcher invariants.** This phase changes only WHERE the claimer value comes from (bulk map vs per-row RPC). Resolved claimer flows into the exact same identity surfaces unchanged.

### Claude's Discretion (planner picks — research options, recommend)

- Exact bulk-RPC payload chunking strategy if `(wr,week)` set exceeds a safe single-payload size (D-02).
- Resolver wiring shape — `prefetched_map` param on `resolve_claimer` vs thin sibling resolver (D-03).
- Disposition of `tests/test_attribution_resolution_scope.py` — delete vs repurpose into a historical-group-resolves-real-claimer regression (D-05).
- Where in the run flow the prefetch map is built (once, before the 4 pre-pass blocks / before `group_source_rows`) — minimum-diff.
- Final names for the remediation flag + window env var (D-06/D-08).
- Living Ledger entry timestamp — executor sets at commit time.

### Deferred Ideas (OUT OF SCOPE)

- **Missing-`Helper Dept #` hard gate relaxation** (126 rows in run 26200546881) — separate Smartsheet-data/gate decision; preserved so it isn't lost.
- **Deep-history (>~6 months) remediation** — left as-is; code fix self-heals on next natural edit.
- **Railway → Render migration + Artifact Explorer redesign** — separate v1.1.
- Any change to the FREEZE/write side (`freeze_row`, snapshot population) — already correct (~99% populated).
- Re-architecting change-detection beyond Sub-project E.
- Fixing upstream Smartsheet `#NO MATCH` formula data quality — the frozen snapshot is the source of truth.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-1 | Bulk attribution prefetch (replace 4 per-row RPC pre-pass sites with one in-memory load) | `prefetch_attribution(pairs)` + `lookup_attribution_bulk` RPC; map keyed `(wr, week, row_id)`; resolver reads O(1). §Standard Stack, §Architecture Patterns |
| REQ-2 | Correct claimer on every generated file (no garbage names for rows with a frozen claimer) | Removing `_attribution_week_in_scope` from key formation; map covers exact run set (D-02) so no generated group misses its claimer. §Architecture Patterns, §Validation |
| REQ-3 | No time-budget regression (≤165 min) | Bulk load collapses ~137k RPCs to O(distinct bulk queries); chunked ≤8-worker or sequential. §Don't Hand-Roll, §Pitfalls |
| REQ-4 | Recent-window (~26 wk) remediation of corrupted files | Name-pattern sweep (`*_NO_MATCH*`/`*_Unknown_Foreman*`) + live-identity exemption, reusing `build_group_identity` + `cleanup_untracked_sheet_attachments` precedent. §Architecture Patterns |
| REQ-5 | Safe Sub-project E re-activation (`AUTHORITATIVE=1`) | Gated operator follow-up (D-09/D-11); fix restores E's "regen is safe" invariant. §State of the Art |
| REQ-6 | Regression coverage (RED-before/GREEN-after) | Unit tests on map builder; behavioral test that a historical group resolves real claimer; fail-safe degradation test. §Validation Architecture |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bulk attribution read (snapshot → frozen roles) | Supabase (PostgREST RPC) | `billing_audit/writer.py` reader | Normalization (`#NO MATCH`→NULL) stays server-side per D-01 (one source of truth); reader only marshals the map |
| Retry / circuit-breaker / kill-switch | `billing_audit/client.py` | — | Existing fail-safe machinery; bulk reader reuses with distinct op id (D-13) |
| Claimer decision (use/HOLD/no_history/disabled) | `billing_audit/writer.py` `resolve_claimer` | — | Foundation A contract preserved verbatim (D-03); only the data source changes |
| Map build + O(1) resolution wiring | `generate_weekly_pdfs.py` `group_source_rows` | `prefetch_attribution` | The run's `(wr,week)` set is assembled during grouping; prefetch runs once before the emission loop |
| Group-key / filename formation (identity) | `generate_weekly_pdfs.py` (4 CR-01 sites + `generate_excel`) | — | Unchanged grammar (D-14); resolved claimer flows into the same surfaces |
| Remediation sweep (delete garbage attachments) | `generate_weekly_pdfs.py` (new isolated mode) | Smartsheet `Attachments` API | Destructive op against production attachments; isolated + dry-run-first (D-06/D-08) |
| E re-activation flip | `.github/workflows/weekly-excel-generation.yml` `env:` | Operator | Human gate between validation and going-live (D-11) |

## Standard Stack

### Core (all already in the repo — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `supabase` (supabase-py) | already pinned | RPC client (`client.schema("billing_audit").rpc(name, params).execute()`) | Existing `lookup_attribution` / `lookup_group_hash` use this exact idiom `[VERIFIED: billing_audit/writer.py L806-811]` |
| `postgrest` (APIError) | already pinned | Error classification surface for `with_retry` | `_classify_postgrest_error` keys on `APIError.code` `[VERIFIED: billing_audit/client.py L310-380]` |
| `smartsheet` (SDK) | already pinned | Attachment list/delete for remediation; respects 300 req/min, SDK 429 retry | `.claude/rules/smartsheet-python-optimization.md` policy; `PARALLEL_WORKERS ≤ 8` `[CITED: .claude/rules/smartsheet-python-optimization.md]` |
| `concurrent.futures.ThreadPoolExecutor` | stdlib | Bounded-parallel chunked bulk fetch (if chunked) | `max_workers=min(PARALLEL_WORKERS, n)` is the established pattern `[VERIFIED: generate_weekly_pdfs.py L5517-5519]` |
| `openpyxl` | already pinned | Excel generation (engine policy: do NOT switch to xlsxwriter) | `.claude/rules/smartsheet-python-optimization.md` §scope `[CITED]` |

**Installation:** none — this phase adds NO Python dependencies. The only new external artifact is the `lookup_attribution_bulk` SQL function, deployed by the data team (D-01).

**Version verification:** N/A — no new packages. The schema change is SQL deployed manually to Supabase (operator coordination per D-01), exactly mirroring the existing `lookup_attribution` RPC deployment.

### Supporting (reused verbatim)

| Symbol | Location | Purpose | When to Use |
|--------|----------|---------|-------------|
| `resolve_claimer` / `ResolveOutcome` / `ROLE_BY_VARIANT` | `writer.py` L869/L840/L858 | use/HOLD decision table | Reused verbatim; only data source changes (D-03) |
| `with_retry` | `client.py` | retry + per-op circuit breaker | Wrap the bulk RPC invoke; pass `op="lookup_attribution_bulk"` (D-13) |
| `_classify_postgrest_error` | `client.py` L310 | transient vs permanent vs global-kill | Used inside `with_retry`; PGRST106/301/302 trip the run-global kill |
| `build_group_identity` | `generate_weekly_pdfs.py` L2639 | parse `(wr, week, variant, identifier)` from filename | Drives the remediation live-identity exemption + parser-based variant detection |
| `cleanup_untracked_sheet_attachments` | L2963 | variant-aware, live-identity-exempt attachment deletion | PRECEDENT for the garbage sweep (D-07) — extend or sibling |
| `delete_old_excel_attachments` | L3258 | same-identity attachment replacement | Reference only — CANNOT remove garbage (different identity than correct file, per D-07) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `lookup_attribution_bulk` RPC (D-01) | Direct PostgREST table SELECT with `in.(...)` filter | REJECTED in D-01: requires exposing `attribution_snapshot` for SELECT + a second copy of the `#NO MATCH`→NULL normalization in Python (two sources of truth) |
| Exact `(wr,week)` set (D-02) | `week_ending >= cutoff` superset | REJECTED in D-02: reintroduces a recency window — a generated group older than cutoff misses its claimer = the exact bug |
| `prefetched_map` param on `resolve_claimer` | thin sibling resolver `resolve_claimer_from_map` | Planner's call (D-03). Param is minimum-diff (one new keyword-only arg, default `None` = current per-row behavior preserved); sibling avoids touching the hot Foundation A signature but duplicates the decision table |

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────────────┐
  Run discovery/grouping  │  group_source_rows(rows)                     │
  assembles the run's     │                                              │
  (wr, week_ending) set ──┼──► STEP 0: build run pair-set                │
                          │      pairs = {(wr, week_ending) for each      │
                          │              completed row}                   │
                          │                 │                            │
                          │                 ▼                            │
                          │   prefetch_attribution(pairs)  ──────────────┼──► chunk pairs (≤~500/payload)
                          │                 │                            │      │
                          │                 │            billing_audit.   │      ▼
                          │                 │            writer            │  lookup_attribution_bulk(jsonb)
                          │                 │            with_retry(       │   (PostgREST RPC, op-isolated)
                          │                 │              op=             │      │
                          │                 │              "lookup_        │      ▼  LATERAL jsonb_to_recordset
                          │                 │               attribution_   │   JOIN attribution_snapshot
                          │                 │               bulk")  ◄──────┼──── rows w/ per-role CASE
                          │                 │                            │      (#NO MATCH/blank → NULL)
                          │                 ▼                            │
                          │   MAP: (wr, week, row_id) → frozen-roles dict │
                          │                 │                            │
                          │   ┌─────────────┼──────────────┬─────────────┐
                          │   ▼             ▼              ▼             ▼
                          │  B sub-primary  C vac_crew  D primary   1.1 sub-helper
                          │  resolve(map)   resolve(map) resolve(map) lookup(map)
                          │   │             │              │             │
                          │   ▼  ResolveOutcome (use/hold/no_history/disabled — UNCHANGED)
                          │   └──────────────┬─────────────┴─────────────┘
                          │                  ▼
                          │   CR-01 identity sites (group key / filename / valid_wr_weeks /
                          │   current_keys) — UNCHANGED grammar, claimer value now from map
                          └──────────────────┬───────────────────────────┘
                                             ▼
                                  generate_excel → upload (TARGET / PPP)

  ── Separate, env-gated, default-OFF, dry-run-first mode (D-06/D-07/D-08) ──
  REMEDIATE_CLAIMERS=1 ──► load TARGET+PPP attachments in window
                          ──► for each attachment: build_group_identity(name)
                          ──► if name matches *_NO_MATCH* / *_Unknown_Foreman*
                              AND identity NOT in valid (live) identity set
                              ──► DRY-RUN: log/count; EXECUTE: delete_attachment
```

### Recommended Project Structure (files touched — additive/surgical)

```
billing_audit/
├── schema.sql          # + lookup_attribution_bulk(p_wr_weeks jsonb) RPC (D-01)
├── writer.py           # + prefetch_attribution(pairs) reader; resolve_claimer map-aware (D-03)
└── client.py           # UNCHANGED (reused: with_retry, breaker, classifier)

generate_weekly_pdfs.py # - 4 _attribution_week_in_scope gates + helpers + banner + env read (D-05)
                        # ~ 4 pre-pass blocks → 1 prefetch + O(1) map reads (D-01/D-03)
                        # + remediation mode (new isolated branch, default-OFF) (D-06)
                        # + remediation-window env var + flag, banner lines (D-08/D-12)

.github/workflows/weekly-excel-generation.yml  # - ATTRIBUTION_RESOLUTION_WEEKS pin; + remediation flag pin (default-OFF) (D-05/D-12)
website/docs/reference/environment.md           # - ATTRIBUTION_RESOLUTION_WEEKS; + remediation flag + window var
tests/                  # repurpose test_attribution_resolution_scope.py; add bulk-reader + historical-regression tests
```

### Pattern 1: Bulk RPC SQL (LATERAL jsonb_to_recordset, reuse the CASE)

**What:** One RPC accepts `p_wr_weeks jsonb` (array of `{wr, week_ending}`), unnests it, LATERAL/INNER joins `attribution_snapshot`, applies the SAME per-role CASE the single-row RPC uses.
**When to use:** REQ-1 bulk fetch; one round trip per chunk.
**Confirmed join key (D-02 question 2):** `(wr, week_ending, smartsheet_row_id)` is the snapshot PK `[VERIFIED: schema.sql L207-208]`. The bulk RPC filters on the run's `(wr, week_ending)` pairs and returns ALL matching rows (every `smartsheet_row_id` under those pairs) so the Python map is keyed by the full triple.

```sql
-- Source: pattern derived from existing lookup_attribution (schema.sql L249-275)
-- + PostgreSQL jsonb_to_recordset (CITED: postgresql.org JSON functions)
CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(
    p_wr_weeks jsonb   -- e.g. '[{"wr":"90001","week_ending":"2026-04-19"}, ...]'
)
RETURNS TABLE (
    wr                TEXT,
    week_ending       DATE,
    smartsheet_row_id BIGINT,
    primary_foreman   TEXT,
    helper            TEXT,
    helper_dept       TEXT,
    vac_crew          TEXT,
    source_run_id     TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        s.wr,
        s.week_ending,
        s.smartsheet_row_id,
        -- EXACT same normalization as lookup_attribution (one source of truth, D-01)
        CASE WHEN s.frozen_primary     LIKE '#%' OR btrim(s.frozen_primary)     = '' THEN NULL ELSE s.frozen_primary     END,
        CASE WHEN s.frozen_helper      LIKE '#%' OR btrim(s.frozen_helper)      = '' THEN NULL ELSE s.frozen_helper      END,
        CASE WHEN s.frozen_helper_dept LIKE '#%' OR btrim(s.frozen_helper_dept) = '' THEN NULL ELSE s.frozen_helper_dept END,
        CASE WHEN s.frozen_vac_crew    LIKE '#%' OR btrim(s.frozen_vac_crew)    = '' THEN NULL ELSE s.frozen_vac_crew    END,
        s.source_run_id
    FROM jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)
    JOIN billing_audit.attribution_snapshot AS s
      ON s.wr = q.wr AND s.week_ending = q.week_ending;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution_bulk(jsonb) TO service_role;
```

**Note for the planner:** the SQL above returns ALL `smartsheet_row_id` rows for each pair — the Python map then indexes by the full triple. This is the minimal-round-trip shape. `[ASSUMED]` that an index on `(wr, week_ending)` already supports the snapshot PK lookup efficiently; the data team owns the snapshot DDL/indexes (opaque to the pipeline per schema.sql L211-218) — flag for operator confirmation, not a code blocker.

### Pattern 2: Fail-safe bulk reader (DISTINCT op id, mirror lookup_group_hash)

**What:** `prefetch_attribution(pairs) -> (map, status)` that wraps the chunked RPC in `with_retry(op="lookup_attribution_bulk")`, classifies failures via the existing machinery, and returns a map plus an overall status.
**When to use:** REQ-1; called once per run.

```python
# Source: pattern mirrors _lookup_attribution_all (writer.py L754-837)
#         + lookup_group_hash fail-safe shape (writer.py / LookupGroupHashTests)
def prefetch_attribution(
    pairs: set[tuple[str, datetime.date]],
) -> tuple[dict[tuple[str, datetime.date, int], dict], str]:
    """Bulk-load frozen attribution for the run's (wr, week_ending) set.

    Returns ((wr, week_ending, smartsheet_row_id) -> roles-dict, status).
    status ∈ 'success' | 'no_row' | 'fetch_failure' | 'unavailable'.
    Fail-safe: NEVER raises; a Supabase failure returns ({}, 'fetch_failure')
    so resolve_claimer applies each variant's documented fallback (D-04).
    Reuses with_retry(op="lookup_attribution_bulk") — DISTINCT op id so a
    bulk-read outage cannot disable freeze_attribution / pipeline_run_* /
    lookup_attribution / lookup_group_hash (op-isolation, D-13).
    """
    # chunk pairs (≤ ~500/payload — see Pitfall 2); for each chunk:
    #   client.schema("billing_audit").rpc("lookup_attribution_bulk",
    #       {"p_wr_weeks": [{"wr": w, "week_ending": d.isoformat()} for ...]})
    # merge chunk results into one map; map key = (wr, parsed_date, row_id)
    ...
```

**Resolver wiring (D-03 question 3):** add a keyword-only `prefetched_map: dict | None = None` to `resolve_claimer`. When provided, it replaces the `_lookup_attribution_all(...)` call with an O(1) lookup that yields the SAME `(row, status)` shape:
- key present → `(roles_dict, "success")`
- key absent, map non-None, overall load succeeded → `(None, "no_row")` (genuine no-frozen-data → use-current)
- overall load failed → `(None, "fetch_failure")` (D-04 per-variant policy)

The use/`no_history`/`disabled`/`fetch_failure` branch logic below that line is UNCHANGED — this is the minimum-diff path and keeps Foundation A's contract byte-for-byte for the per-row callers (param defaults `None`).

### Pattern 3: Remediation name-pattern sweep (live-identity-exempt, dry-run-first)

**What:** A NEW default-OFF env-gated mode that, for the window's week-endings, lists TARGET + PPP attachments, parses each name with `build_group_identity`, and deletes ONLY names matching `*_NO_MATCH*` / `*_Unknown_Foreman*` whose identity is NOT in the live-identity set built this run.
**When to use:** REQ-4; operator-triggered, never on cron.

**Key facts the planner needs:**
- Garbage files are CLEAN-named (no `_<timestamp>_<hash>` token) because they were uploaded under `AUTHORITATIVE=1` — the sweep keys on the `_NO_MATCH` / `_Unknown_Foreman` substring, NOT token shape, so it works whether or not E is active `[CITED: 02-CONTEXT.md §Specific Ideas]`.
- The garbage file has a DIFFERENT identity than the correct-claimer file (claimer `_NO_MATCH` vs the real name), so same-identity replacement (`delete_old_excel_attachments`) NEVER removes it — an explicit pattern sweep is required (D-07).
- The live-identity exemption ([2026-05-19 23:45]): an attachment whose `build_group_identity` tuple `(wr, week, variant, identifier)` is in `valid_wr_weeks` (the live set generated this run) is exempt — guards against deleting a legitimately-claimed file that happens to share a WR. A genuinely-orphaned garbage file is NEVER in the live set, so it is deleted.
- `cleanup_untracked_sheet_attachments` (L2963) is the precedent — its `sub_legacy_primary_variants` / `vac_legacy_wr_scope` / `primary_wr_scope` params all show the "scoped + live-exempt unconditional delete" shape. A new `garbage_name_patterns` parameter (or a sibling function) is the cleanest extension.

### Anti-Patterns to Avoid

- **Re-introducing any recency window into key formation.** D-02/D-05 are explicit: the bug was a recency gate on KEY formation. The bulk load loads the EXACT run set — no `>= cutoff` anywhere near claimer resolution.
- **Duplicating the `#NO MATCH`→NULL CASE in Python.** D-01: one source of truth (server-side). The map carries already-normalized roles.
- **Parallelizing per-row instead of eliminating per-row.** [2026-04-25 14:00] / [2026-05-26 01:45]: the goal is to ELIMINATE per-row network cost (O(rows)), not to make it parallel. Parallelism hid the O(all-history) count until data grew.
- **Folding remediation into generic cleanup / `REGEN_WEEKS`.** D-06: destructive prod-attachment op must be isolated, observable, reversible, dry-run-first.
- **Auto-committing the `AUTHORITATIVE=1` flip in the fix PR.** D-11: the human gate is the whole point — the premature flip (`67539ec`) caused this incident.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-role `#NO MATCH`/blank normalization | Python CASE replication | The bulk RPC's server-side CASE (D-01) | One source of truth; the single-row RPC already does it identically |
| Retry / circuit breaker / kill switch | New retry loop for the bulk reader | `with_retry` + `_classify_postgrest_error` (distinct op id) | D-13; reusing avoids the [2026-04-25] retry-spam class of bug |
| use/HOLD/no_history/disabled decision | New resolution logic | `resolve_claimer` + `ROLE_BY_VARIANT` (map-aware) | D-03; Foundation A contract, 4 sub-projects depend on it |
| Filename → identity parse | New regex for the garbage sweep | `build_group_identity` (L2639) | Battle-hardened across rounds 10/11 pathologies; the variant + identity it returns drives the live-identity exemption |
| Live-identity-exempt deletion | Ad-hoc delete loop | `cleanup_untracked_sheet_attachments` precedent | [2026-05-19 23:45] live-identity exemption already solved here |

**Key insight:** Every primitive this phase needs already exists and is tested. The work is *re-plumbing the data source* (per-row RPC → bulk map) and *adding a narrow destructive mode* — not building new infrastructure. The smallest correct diff is the safest one given this is production-critical billing code.

## Runtime State Inventory

> This is a read-side refactor + a one-shot remediation, not a rename. The relevant "runtime state" is the live Supabase RPC surface and the live Smartsheet attachments.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `billing_audit.attribution_snapshot` (~142k rows, ~99% `frozen_primary` populated back to mid-2025) — the source of truth; UNCHANGED by this phase (read-only) | None — read-only |
| Live service config | New `lookup_attribution_bulk` RPC must be deployed to the live Supabase project + PostgREST schema cache reloaded (`NOTIFY pgrst, 'reload schema';`) before the fix is live (D-01) | **Operator deploy** (data team) — mirrors existing `lookup_attribution` deployment |
| Live service config | `SUPABASE_HASH_STORE_AUTHORITATIVE` workflow `env:` flip 0→1 (D-09/D-11) | **Operator action** post-validation; NOT auto-committed |
| OS-registered state | GitHub Actions cron schedule + `timeout-minutes:180` / `TIME_BUDGET_MINUTES:165` — UNCHANGED; remediation flag pinned default-OFF so cron never triggers it | Pin remediation flag default-OFF in workflow `env:` (D-12) |
| Secrets/env vars | `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` — UNCHANGED. `ATTRIBUTION_RESOLUTION_WEEKS` REMOVED from workflow pin + env read + docs (D-05). New remediation flag + window var ADDED, pinned default-OFF (D-08/D-12) | Update workflow `env:` + `environment.md` |
| Build artifacts | Live Smartsheet attachments: 372 garbage files in incident run `26439205107` (131 `_User__NO_MATCH`, 241 `_User_Unknown_Foreman`), concentrated in old weeks, on TARGET + PPP | **Remediation sweep** (REQ-4) deletes these in the ~26-week window; deeper history self-heals (out of scope) |

**Nothing found in category:** the `freeze_attribution` write path, snapshot DDL, change-detection key shape, and variant grammar are all explicitly UNTOUCHED — verified against D-14 + SPEC Boundaries.

## Common Pitfalls

### Pitfall 1: Splitting the four pre-pass blocks out of lockstep (CR-01 / D-14)

**What goes wrong:** The four pre-pass sites (B sub-primary ~L5471, C vac_crew ~L5547, D primary ~L5622, 1.1 sub-helper ~L6203) each feed a claimer into the group-KEY / filename / `valid_wr_weeks` / `current_keys` identity surfaces. If the refactor changes the value but not in lockstep across all consumption sites (vac ~L5796, primary ~L5875, sub-primary ~L6052), attachment-identity matching and hash-history persistence break → regeneration churn + orphans.
**Why it happens:** The map is built once but consumed in four places; an inconsistent default (`None` vs `Unknown Foreman` sentinel vs current foreman) silently diverges identities.
**How to avoid:** Preserve the EXACT existing per-variant fallback semantics at each consumption site (D never HOLDs → use-current; B/C HOLD; map miss → use-current never HOLD). The resolved `ResolveOutcome` must flow into the same surfaces unchanged (D-14). Source-grep guard tests that all four CR-01 sites carry the claimer (the existing Sub-project test pattern).
**Warning signs:** Tests assert keys are PRESENT but not that wrong keys are ABSENT (the [2026-05-21 10:30] over-emission lesson) — assert both.

### Pitfall 2: jsonb RPC payload too large → "Body exceeded 1mb limit"

**What goes wrong:** A run touches hundreds of WRs across many weeks; a single `jsonb` array of all `(wr, week)` pairs could exceed PostgREST's request-body limit.
**Why it happens:** Supabase/PostgREST enforces a request body size limit (commonly ~1 MB; not a single universally-published hard number — varies by infra) `[VERIFIED: cross-referenced Supabase community + supabase/cli#274 "Body exceeded 1mb limit"]`.
**How to avoid:** Chunk the `(wr, week)` set. **Sizing math:** each pair as `{"wr":"90001","week_ending":"2026-04-19"}` ≈ ~45 bytes; ~1 MB / 45 B ≈ ~22,000 pairs theoretical ceiling. **Recommended safe batch: ~500 pairs/payload** (≈ 22 KB — two orders of magnitude under the limit, comfortable headroom). At ~500/chunk, a run with (e.g.) 550 WRs × several weeks → a handful of chunks. Chunks can be sequential (a handful of round trips, dwarfed by the ~137k baseline) OR `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, n_chunks))` if measured latency warrants. **Recommendation: start sequential** (simplest, already O(chunks) ≪ O(rows)); add bounded parallelism only if a real run shows it's needed.
**Warning signs:** HTTP 413 / "Body exceeded 1mb limit" in the run log; a `fetch_failure` status that classifies as a permanent 4xx.

### Pitfall 3: Remediation sweep collateral-deleting a legitimate file

**What goes wrong:** A file legitimately named with a real claimer that *contains* a matched substring, or a live correct file for a WR that also had garbage, gets deleted.
**Why it happens:** Pattern matching on substring without the live-identity exemption.
**How to avoid:** D-07 patterns (`_NO_MATCH` / `_Unknown_Foreman`) are not realistic real-claimer-name substrings, AND the live-identity exemption ([2026-05-19 23:45]) guarantees any identity generated this run is exempt. Dry-run-first (D-08) surfaces exact counts + names for operator review before any delete.
**Warning signs:** Dry-run report shows a delete count that doesn't match the expected garbage count; a name in the would-delete list contains a real foreman name.

### Pitfall 4: Test stub shadowing the real Smartsheet SDK at collection

**What goes wrong:** A new test module that calls `_ensure_smartsheet_mocked()` unconditionally at import installs a bare `smartsheet` MagicMock during pytest COLLECTION; if it sorts alphabetically before suites needing the real SDK, it breaks them with "'smartsheet' is not a package".
**Why it happens:** [2026-05-26 01:45] rule 3 — documented in `test_attribution_resolution_scope.py` L22-26.
**How to avoid:** Guard `_ensure_smartsheet_mocked()` behind `try: import smartsheet except ImportError:` (copy the existing pattern verbatim).
**Warning signs:** Unrelated `TestDiscoverFolderSheets`-style tests fail only when the new module is present.

## Code Examples

### Building the run's exact (wr, week) pair-set (D-02)

```python
# Source: derived from existing pre-pass row filters (generate_weekly_pdfs.py L5481-5488)
# The run's (wr, week_ending) set is assembled from completed rows during grouping.
_pairs: set[tuple[str, datetime.date]] = set()
for _r in rows:
    _wr_raw = _r.get('Work Request #')
    _ld = _r.get('Weekly Reference Logged Date')
    if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
        continue
    _we = excel_serial_to_date(_ld)
    if _we is None:
        continue
    _we_d = _we.date() if isinstance(_we, datetime.datetime) else _we
    _pairs.add((str(_wr_raw).split('.')[0], _we_d))
# NOTE: NO _attribution_week_in_scope gate — the whole point of D-05.
_attr_map, _attr_status = prefetch_attribution(_pairs)   # built ONCE
```

### Map-aware resolution at a pre-pass site (replaces per-row RPC)

```python
# Source: replaces the ThreadPoolExecutor per-row resolve loop (L5500-5535).
# After the bulk map is built, resolution is O(1) — no executor, no RPC.
for _r in <completed rows for this variant>:
    _rid = _r.get('__row_id')
    _out = resolve_claimer(
        '<variant>', _current_value,
        wr=_wr, week_ending=_we_d, row_id=_rid,
        enabled=<variant kill switch>,
        prefetched_map=_attr_map,      # NEW: map-aware (D-03)
    )
    _claimer_map[_rid] = _out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-row `lookup_attribution` RPC, unbounded (~137k calls) | This phase: one bulk RPC per chunk | This phase | Eliminates timeout; O(distinct bulk queries) |
| `ATTRIBUTION_RESOLUTION_WEEKS=8` recency gate on KEY formation | Removed entirely (D-05) | This phase | Fixes garbage-claimer root cause |
| `SUPABASE_HASH_STORE_AUTHORITATIVE=1` prematurely flipped (67539ec) → corruption → reverted to 0 (46cd05d/PR #234) | Gated operator flip AFTER validation (D-09/D-11) | This phase | Restores E's "regen is safe" invariant |

**Deprecated/outdated by this phase:**
- `ATTRIBUTION_RESOLUTION_WEEKS` env var + `_attribution_resolution_cutoff` + `_attribution_week_in_scope` + the 4 gates + banner line + workflow pin + `environment.md` entry — all removed (D-05).
- The per-row ThreadPoolExecutor resolve loops in the four pre-pass blocks — collapsed to O(1) map reads.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Supabase/PostgREST request-body limit ≈ 1 MB (not a single universally-published hard number) | Pitfall 2 | LOW — the ~500-pair recommendation is 2 orders of magnitude under any plausible limit; chunk size is tunable |
| A2 | `attribution_snapshot` has an index supporting `(wr, week_ending)` join efficiency | Pattern 1 note | LOW — data team owns snapshot DDL/indexes (opaque to pipeline); flag for operator confirm, not a code blocker. If missing, a one-line `CREATE INDEX` on Supabase resolves it |
| A3 | A run's `(wr, week)` set is a few thousand pairs at most (≈550 WRs × handful of weeks) | Pitfall 2 sizing | LOW — even 10k pairs is ~20 chunks at 500/chunk, still ≪ 137k |
| A4 | The bulk RPC returning ALL `smartsheet_row_id` rows per pair (rather than per-row filtering) is acceptable volume | Pattern 1 | LOW — a pair's row set is the same rows the run is already processing; map size is bounded by run size |
| A5 | `jsonb_to_recordset` with a `DATE` column coerces ISO `YYYY-MM-DD` strings correctly | Pattern 1 | LOW — standard PostgreSQL behavior; the single-row RPC already takes `p_week_ending DATE` from `week_ending.isoformat()` (writer.py L802) |

**If this table is empty:** it is not — all 5 are LOW-risk, none block planning; A1/A2 warrant a one-line operator confirmation at deploy.

## Open Questions (RESOLVED)

1. **Exact remediation-mode entry shape — top-level branch vs sibling entry point.**
   - What we know: D-06 mandates an isolated, env-gated, dry-run-first mode with own logging/counters; CONTEXT §Integration Points says "a new top-level branch in `generate_weekly_pdfs.py` (or a sibling entry point — planner picks)".
   - What's unclear: whether to add a branch in `main()` or a separate callable.
   - Recommendation: a new top-level branch gated by the default-OFF flag, calling a dedicated `run_claimer_remediation(dry_run: bool, window_weeks: int)` function — keeps the isolation explicit and unit-testable without invoking full generation.

2. **`prefetched_map` param vs thin sibling resolver (D-03).**
   - What we know: D-03 leaves it to the planner; both preserve the decision table.
   - Recommendation: keyword-only `prefetched_map=None` on `resolve_claimer` — minimum-diff, default preserves per-row behavior, single decision-table copy.

3. **Disposition of `tests/test_attribution_resolution_scope.py` (D-05).**
   - What we know: the file tests behavior being removed; D-05 says delete OR repurpose.
   - Recommendation: DELETE it (the scope it tests is gone) and add the replacement regression in `test_primary_claim_attribution.py` (historical group → real claimer, RED-before/GREEN-after per REQ-6b). Keep the `_ensure_smartsheet_mocked` import-guard pattern in any new module.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `supabase` / `postgrest` (Python) | bulk reader | ✓ (already pinned/used) | as in requirements.txt | — |
| `smartsheet` SDK | remediation sweep | ✓ (production engine) | as pinned | — |
| `lookup_attribution_bulk` RPC (live Supabase) | bulk read at runtime | ✗ (must be deployed) | — | Reader degrades to `fetch_failure` → per-variant fallback (D-04) until deployed; pipeline behaves as today (fail-safe) |
| Live `attribution_snapshot` data | correct claimers | ✓ (~142k rows, ~99% populated) | — | — |

**Missing dependencies with no fallback:** none that block code — but **the `lookup_attribution_bulk` RPC deploy + PostgREST cache reload is a hard prerequisite for the fix to actually resolve claimers at runtime** (D-01 operator coordination). Until deployed, the reader returns `fetch_failure`/`no_row` and the pipeline is fail-safe (no crash), but claimers won't be corrected — so the validation gate (D-10) must run AFTER the RPC is live.

**Missing dependencies with fallback:** the RPC itself — fail-safe degradation per D-04 means the pipeline never crashes pre-deploy.

## Validation Architecture

> `workflow.nyquist_validation` not explicitly false in config — section INCLUDED.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (with `unittest.TestCase` classes) + coverage |
| Config file | none dedicated; invoked via `pytest tests/` `[CITED: CLAUDE.md Validation Commands]` |
| Quick run command | `pytest tests/test_billing_audit_shadow.py -x -q` (bulk reader) |
| Full suite command | `pytest tests/ -v` (current baseline ~961 passing per SPEC) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-1 | `prefetch_attribution` builds correct `(wr, week, row_id) → roles` map from synthetic snapshot rows | unit | `pytest tests/test_billing_audit_shadow.py::PrefetchAttributionTests -x` | ❌ Wave 0 (new) |
| REQ-1 | Map-aware `resolve_claimer(prefetched_map=...)` returns the SAME `ResolveOutcome` as the per-row path for use/no_history/fetch_failure/disabled | unit | `pytest tests/test_billing_audit_shadow.py::ResolveClaimerMapAwareTests -x` | ❌ Wave 0 (new) |
| REQ-1/3 | Attribution issues O(distinct bulk queries) not O(rows) — resolver invoked with map issues 0 per-row RPCs | unit (mock RPC, assert call count) | `pytest tests/test_billing_audit_shadow.py::PrefetchAttributionTests::test_no_per_row_rpc -x` | ❌ Wave 0 (new) |
| REQ-2/6b | A historical (out-of-old-8-week-scope) generated group resolves its REAL frozen claimer, NOT use-current — RED before fix, GREEN after | behavioral (drive `group_source_rows`, mock map) | `pytest tests/test_primary_claim_attribution.py::TestHistoricalClaimerRegression -x` | ❌ Wave 0 (new) |
| REQ-2 | A genuine no-frozen-data row still falls back to use-current (`no_history`) | behavioral | `pytest tests/test_primary_claim_attribution.py::TestHistoricalClaimerRegression::test_no_frozen_falls_back -x` | ❌ Wave 0 (new) |
| REQ-6d | Bulk-load total-failure degrades to documented per-variant fallback (D never HOLDs; B/C HOLD); never crash / silent wrong value | unit + behavioral | `pytest tests/test_billing_audit_shadow.py::PrefetchAttributionTests::test_failure_is_fetch_failure -x` | ❌ Wave 0 (new) |
| REQ-4 | Remediation dry-run reports correct would-delete counts for `*_NO_MATCH*`/`*_Unknown_Foreman*`; live-identity exemption preserves correct files; execute deletes only garbage | unit (mock Smartsheet attachments) | `pytest tests/test_<remediation>.py -x` | ❌ Wave 0 (new) |
| REQ-1/D-14 | All four CR-01 identity sites carry the resolved claimer (source-grep guard) | source-grep | existing Sub-project invariant pattern, extended | ⚠ extend existing |
| REQ-5 | `SUPABASE_HASH_STORE_AUTHORITATIVE` flip is NOT in the fix PR (gated) | source/workflow check | manual + D-11 runbook | manual gate |

### Concrete checkable signals (the load-bearing validations)

1. **Map builder correctness (REQ-1, unit-testable on synthetic rows):** feed synthetic snapshot rows (incl. `#NO MATCH` and blank roles — already NULL'd server-side, so the mock returns NULL) → assert map key = `(wr, week_ending, row_id)` and roles dict matches; assert keys absent from input pairs are absent from the map.
2. **Historical-group RED/GREEN (REQ-2/6b — the incident reproduction):** build a row whose `week_ending` is >8 weeks old (out of the OLD scope) with a frozen `primary_foreman="Real Name"` in the (mocked) bulk map. Drive `group_source_rows`. **RED (pre-fix / with the old scope gate):** the row is out-of-scope → map miss → `_d_claimer = effective_user or 'Unknown Foreman'` → key contains `_USER__NO_MATCH` / `_Unknown_Foreman`. **GREEN (post-fix):** the bulk map (exact-set, no scope) yields `Real Name` → key contains `_USER_Real_Name`. Evidence anchor: incident run `26439205107` (372 garbage files: 131 `_User__NO_MATCH`, 241 `_User_Unknown_Foreman`, concentrated in old weeks).
3. **No-frozen-data fallback (REQ-2):** a row whose pair is in the run set but has NO snapshot row → map miss with `status='success'` overall → resolver returns `(None, "no_row")` → `no_history` → use-current. Assert the key uses the current foreman, not a crash/HOLD.
4. **Total-failure degradation (REQ-6d):** `prefetch_attribution` returns `({}, "fetch_failure")` (RPC mocked to fail). Assert: D primary → use-current (never HOLD); B sub-primary + C vac_crew → `ResolveOutcome.action == "hold"` (the existing per-variant policy, unchanged). Never raises.
5. **HTTP-count signal (REQ-1/3, acceptance-run evidence per D-10):** in the acceptance run log, attribution requests = number of bulk chunks (single/low-double digits), NOT the ~137k `POST /rpc/lookup_attribution` baseline. Unit-level proxy: mock the RPC and assert it's called `ceil(n_pairs / chunk_size)` times, and `resolve_claimer(prefetched_map=...)` issues 0 per-row RPCs.

### Sampling Rate

- **Per task commit:** `pytest tests/test_billing_audit_shadow.py tests/test_primary_claim_attribution.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** `pytest tests/ -v` fully green + the D-10 acceptance run (zero garbage names, O(chunks) HTTP, ≤165 min) before the operator flips `AUTHORITATIVE=1`.

### Wave 0 Gaps

- [ ] `tests/test_billing_audit_shadow.py` — add `PrefetchAttributionTests` + `ResolveClaimerMapAwareTests` (mirror the `LookupGroupHashTests` fail-safe shape: success / no_row / unavailable / global-kill-is-fetch-failure / with_retry-None-is-fetch_failure / unexpected-exception-is-fetch_failure).
- [ ] `tests/test_primary_claim_attribution.py` — add `TestHistoricalClaimerRegression` (RED-before/GREEN-after; no-frozen fallback).
- [ ] `tests/test_<remediation>.py` — NEW module for the dry-run + live-identity-exempt sweep (use the `_ensure_smartsheet_mocked` import-guard pattern, Pitfall 4).
- [ ] Repurpose/delete `tests/test_attribution_resolution_scope.py` (D-05) — recommend DELETE; replacement regression lives in `test_primary_claim_attribution.py`.
- [ ] Map-aware resolution tests in `test_subcontractor_primary_claim_attribution.py` + `test_vac_crew_claim_attribution.py` (B/C variants still HOLD on failure; map drives the claimer).

## Security Domain

> `security_enforcement` not explicitly false — section included. This is a billing pipeline touching PII (foreman names) + Supabase + Smartsheet.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no new auth surface) | Supabase service-role key unchanged; PGRST301/302 already trip the global kill |
| V3 Session Management | no | N/A |
| V4 Access Control | yes | `GRANT EXECUTE ... TO service_role` on the new RPC (mirror existing `lookup_attribution` grant, schema.sql L277) |
| V5 Input Validation | yes | `p_wr_weeks jsonb` validated server-side by `jsonb_to_recordset` typed columns; Python sanitizes `wr` via `_WR_SANITIZE` before building pairs (writer.py L799) |
| V6 Cryptography | no | No new crypto |
| V7 Logging (PII) | yes | Frozen role names are PII — existing `before_send_log` sanitizer + `_PII_LOG_MARKERS` + redaction discipline preserved; remediation dry-run logs counts + sanitized identifiers only, NOT raw foreman names |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PII leakage of foreman names into logs/Sentry | Information Disclosure | Existing sanitizers preserved (CLAUDE.md [2026-04-20 12:00] / [2026-04-23 12:00]); remediation logs counts + sanitized identifiers only |
| jsonb payload injection | Tampering | Typed `jsonb_to_recordset(... AS q(wr TEXT, week_ending DATE))` + parameterized RPC (no string concatenation); `_WR_SANITIZE` on the Python side |
| Destructive over-deletion of correct attachments | Tampering / DoS-of-data | Name-pattern + live-identity exemption + dry-run-first + default-OFF flag (D-07/D-08) |
| Retry-spam DoS on a misconfigured Supabase | DoS | `_classify_postgrest_error` + per-op circuit breaker + run-global kill (D-13), reused unchanged |

## Sources

### Primary (HIGH confidence)
- `billing_audit/writer.py` L754-944 — `_lookup_attribution_all`, `resolve_claimer`, `ResolveOutcome`, `ROLE_BY_VARIANT`, `lookup_attribution` (the reused contract).
- `billing_audit/client.py` L62-380 — `with_retry` machinery, `_classify_postgrest_error`, circuit breaker, `_PGRST_GLOBAL_KILL_CODES`, `get_client()` kill switch.
- `billing_audit/schema.sql` L200-277 — `attribution_snapshot` PK shape + the `lookup_attribution` RPC's per-role `#NO MATCH`/blank → NULL CASE (the bulk RPC reuses this).
- `generate_weekly_pdfs.py` L638-647, L5335-5395 (scope helpers), L5460-5704 (3 pre-pass blocks), L5780-5899 (consumption), L6185-6264 (sub-helper lookup), L2639-2758 (`build_group_identity`), L2963-3060 (`cleanup_untracked_sheet_attachments`).
- `tests/test_billing_audit_shadow.py` L4978-5057 (`LookupGroupHashTests` — the fail-safe reader test template) + `tests/test_attribution_resolution_scope.py` (to be deleted/repurposed).
- `02-SPEC.md` (6 requirements) + `02-CONTEXT.md` (D-01..D-14) + `CLAUDE.md` Living Ledger ([2026-05-26 01:45], [2026-04-25 12:00], [2026-04-25 14:00], [2026-05-19 23:45], CR-01 entries).

### Secondary (MEDIUM confidence)
- [PostgreSQL JSON Functions — jsonb_to_recordset](https://www.postgresql.org/docs/9.5/functions-json.html) — LATERAL/recordset unnest pattern for the bulk RPC.
- [supabase/cli#274 "Body exceeded 1mb limit"](https://github.com/supabase/cli/issues/274) — evidence of a ~1 MB request-body limit in PostgREST/Supabase contexts.

### Tertiary (LOW confidence — flagged for validation)
- [passing json as parameter to rpc — size limit? (Supabase community)](https://www.answeroverflow.com/m/1030772704451776522) — "no explicit limit but you'll hit memory limits; chunk large payloads" — corroborates the chunking recommendation; no single published hard number (hence A1 LOW-risk + the conservative 500-pair batch).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every primitive exists in-repo and is verified by direct read.
- Architecture: HIGH — the four pre-pass blocks are near-identical and the resolver/reader contracts are explicit; the bulk RPC is a direct generalization of the existing single-row RPC.
- Pitfalls: HIGH — drawn from the Living Ledger's own documented incidents (CR-01 lockstep, retry-spam, live-identity exemption, test-stub shadowing).
- jsonb payload sizing: MEDIUM — no single published hard limit; ~1 MB cross-verified, mitigated by a conservative 500-pair chunk recommendation 2 orders of magnitude under it.

**Research date:** 2026-05-26
**Valid until:** ~2026-06-25 (stable; the only external-facing variable is the Supabase request-body limit, which the conservative chunk size insulates against).
