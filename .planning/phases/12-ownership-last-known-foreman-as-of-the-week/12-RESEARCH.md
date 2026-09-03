# Phase 12: Ownership — last known foreman as of the week - Research

**Researched:** 2026-09-02
**Domain:** Billing attribution / claim-time ownership resolution (Python pipeline + Supabase RPC/schema)
**Confidence:** MEDIUM (code surfaces VERIFIED by reading; two architectural questions are genuinely open and flagged, not guessed at)

<user_constraints>
## User Constraints (from decision sources — no CONTEXT.md; `/gsd:discuss-phase` was not run for this phase)

There is no `CONTEXT.md`. The binding decisions live in two artifacts named in the phase brief, both read in full this session:
`docs/superpowers/specs/2026-09-01-own-03-claim-time-backfill-design.md` (design doc, owner decisions applied 2026-09-02 00:35 CDT) and `memory-bank/living-ledger.md` entries `[2026-09-01 18:05]`, `[2026-09-01 18:55]`, `[2026-09-01 19:45]`, `[2026-09-01 19:55]`, `[2026-09-02 00:35]`.

### Locked Decisions

1. **Ownership semantics (§8 #1, ledger `[2026-09-01 19:45]`):** a file for `(WR, week_ending)` is named for, and contains only the rows of, the person who **claimed** those rows in that week — the first non-sentinel value observed on the row at or after it became "completed" for that role — **never** the live Smartsheet value at generation time. A later Smartsheet edit to an already-claimed row is an audit event, not a re-attribution.
2. **No cross-week inheritance (sub-decision, ledger `[2026-09-01 19:55]`):** spec §5 step 2 ("last known foreman at or before the week") is **DROPPED**. A week with no in-week observation keeps the sentinel until a same-week source names someone. **This directly contradicts the still-unedited `REQUIREMENTS.md` OWN-01 wording** ("ladder `observed_in_week → last_known_before_week → backfill → Unknown`") — treat the ledger decision as authoritative; `REQUIREMENTS.md` text is stale and the planner/executor should not implement `last_known_before_week`.
3. **Sentinel is never a claimer (§8 policy A, OWN-02, SHIPPED — PRs #375/#376/#377):** `is_sentinel_claimer()` in `billing_audit/writer.py:105-115` already implements this. Do not re-implement; only the residual gaps below remain.
4. **Backfill sources, in precedence order (§8 #5, spec §3, ledger `[2026-09-01 19:45]` + `[2026-09-02 00:35]`):**
   1. `pipeline_memory.row_event` / `row_state` observed columns (`source='live'`)
   2. non-sentinel `billing_audit.attribution_snapshot` rows for the same `(wr, week_ending, smartsheet_row_id)` (fills one sentinel role only when another role on the same row is real)
   3. `public.artifacts` filenames (`source='backfill_artifacts'`) — group-level, only when the week has exactly ONE real-name identity for that role
   4. 2025 `hash_history.json` foreman field, one-time import (`source='backfill_hash_history'`) — same single-name rule as #3
   5. **DECIDED INCLUDED 2026-09-02 00:35** — Smartsheet cell history (`source='operator'`), but **only** as a separate, capped, off-hours job (`workflow_dispatch` + Saturday-midnight-Central / Sunday 05:00Z cron while a backlog exists) — **never inside `generate_weekly_pdfs.py`**. Default cap 3,000 history requests/run (~10 min of the 300 req/min budget). Reuses the selective cell-history pattern named in `audit_billing_changes.py` (see Common Pitfalls — that "pattern" is a stub, not working code; the real working call is in `pipeline/snapshot_drift.py`).
   - Rules: (a) first source with a non-sentinel name wins; (b) sources 3–4 used only when 1–2 are silent for that row; (c) **no cross-week lookup in any source**; (d) every written value carries provenance (`source` column, already present on `row_event`/`group_state`; `attribution_snapshot` needs new `backfill_source`/`backfill_run_id` columns per spec §7).
5. **Write path = spec §4 option 1 (ledger `[2026-09-02 00:35]`):** a new, **owner-deployed** RPC `billing_audit.backfill_attribution(p_rows jsonb)` — updates `frozen_<role>` **only** where the current value is sentinel/NULL, never touches a real name, returns `updated | skipped_real_name | skipped_no_row` per row. The SQL ships **in the OWN-03 PR as a file for Juan to paste into the Supabase SQL editor** — this repo does not, and cannot, apply Supabase schema/RPC changes itself (see Architecture Patterns). Before any write: copy affected rows to `billing_audit.attribution_snapshot_backup_<date>` (rollback path).
6. **PPP attachments are NEVER purged by any reset (ledger `[2026-09-02 00:35]` item 4).** `reset_wr_list` stays scoped to `TARGET_SHEET_ID` only; this is a closed won't-do, not an open item.
7. **`RESET_WR_LIST` scoping is ALREADY SHIPPED** — `pipeline/orchestrate.py:412-430` `_reset_list_forces_regeneration()` — do not re-plan it; the ledger's "approved as the next small PR" language (19:45) predates this landing.
8. **Sentinel-aware attachment cleanup is ALREADY SHIPPED** (PR #377) — `pipeline/cleanup.py:89-116, 495-508` `_is_sentinel_identifier()` + the sentinel-superseded gate. It has a **known, unfixed defect (CR-01, below)** that Phase 12 is explicitly tagged to fix — this is residual work, not new work.
9. **Not in scope for Phase 12:** OWN-01 ladder's operator-override path (real-name correction) is out of scope; that is OWN-01's own separate deliverable. Runbook contract text is OWN-04's own item, not a byproduct of OWN-02/03 code changes.

### Claude's Discretion

- Exact shape of `scripts/backfill_claim_time_attribution.py` (the spec gives CLI flags and a report schema in §5 but not an implementation).
- Whether `wr_week_ownership` becomes a real new table or whether OWN-01 is satisfied by the existing `attribution_snapshot` + `resolve_claimer` read path plus the new `backfill_source`/`backfill_run_id` provenance columns — **see Open Questions, this is NOT a settled decision** and neither the ledger nor the design spec commits to building the table from the 2026-08-24 draft schema.
- Off-hours workflow YAML shape for source 5 (model after `weekly-excel-generation.yml`'s cron/dispatch pattern, per `.github/instructions/github-actions-ci-cd-best-practices.instructions.md`).

### Deferred Ideas (OUT OF SCOPE)

- Phase 13 (Audit Memory: `audit_finding` / `audit_finding_event`, `wr_week_ownership`'s sibling tables) — do not build any Phase 13 schema now.
- Event-driven change capture / continuous Smartsheet webhook watcher — "ASSESSED, not yet a phase" (ledger `[2026-09-01 19:45]`).
- OWN-01's operator-override correction path (a human overriding a real frozen name) — separate decision, not this phase's backfill work.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OWN-01 | `wr_week_ownership` decides each (WR, week, variant, role) owner by a ladder; sentinels never stored as names. **Ladder text in REQUIREMENTS.md is stale — see Locked Decision #2.** | Architecture Patterns (ladder mapping to existing code); Open Question #1 (table vs. no-table) |
| OWN-02 | `freeze_row`/`resolve_claimer` treat sentinel as no-claimer (SHIPPED); Subproject B/C/D partition by `wr_week_ownership` (residual — currently partitions by `resolve_claimer` output directly, not a `wr_week_ownership` table) | Architecture Patterns; `billing_audit/writer.py:105-146,1058-1146`; `pipeline/grouping.py:239-420` |
| OWN-03 | Dry-run-first backfill from sources 1–5; 93 WRs / 5,824+ rows remediated; validated against WR 19073866 | Code Examples (cell-history reuse, backfill script CLI shape, RPC SQL pattern); Runtime State Inventory; Common Pitfalls |
| OWN-04 | Living Ledger + runbook document the amended Foundation A contract | Documentation Maintenance rule (`.claude/rules/documentation-maintenance.md`); ledger already has OWN-02's entry — OWN-04 needs the runbook (`website/docs/`) side, which is not yet done |

Also carried forward (STATE.md advisory, explicitly tagged for Phase 12, NOT new requirements but must be addressed in this phase's plan):
- **CR-01** `pipeline/cleanup.py:89-116` `_is_sentinel_identifier` — leading-underscore heuristic is a false positive on real names with leading space/apostrophe/paren (verified below).
- **WR-01** `pipeline/orchestrate.py` top-level `AttachmentParentType` import — align to `discovery.py`'s lazy/guarded pattern.
</phase_requirements>

## Summary

Phase 12's requirements sound like four independent items, but the codebase evidence shows the real shape is: **one item already shipped (OWN-02's core sentinel rule), one item that is mostly wiring/documentation (OWN-04), one item that is a genuinely new script + owner-deployed SQL (OWN-03), and one item (OWN-01) whose concrete deliverable is ambiguous** between "build the `wr_week_ownership` table from the 2026-08-24 design draft" and "the ladder is already satisfied by `attribution_snapshot` + `resolve_claimer` + OWN-03's backfill, so OWN-01 is a thin logging/audit layer." The most authoritative and most recent artifact — the 2026-09-01 OWN-03 design spec, which encodes Juan's actual 2026-09-02 00:35 decisions — never mentions `wr_week_ownership` at all; it writes backfilled values straight into the existing `attribution_snapshot.frozen_<role>` columns that `resolve_claimer` already reads. This is the single most important finding for planning: build the plan around what the OWN-03 spec actually describes (extend the existing table, add two provenance columns, ship one new RPC and one new script), and treat the standalone `wr_week_ownership` table as an open question for Juan rather than an assumed requirement, because the spec that carries his most recent sign-off silently supersedes the older design draft that first proposed the table.

The residual OWN-02 work is small: Subproject B/C/D (`pipeline/grouping.py:239-420`) already partition Excel output by whatever `resolve_claimer()` returns — which today is exactly "frozen name if real, else current Smartsheet value." Once OWN-03's backfill fills sentinel `attribution_snapshot` rows with real names (tagged by source), `resolve_claimer`'s existing code picks them up on the next scheduled run with **zero grouping-code changes** — the backfill's whole value proposition is that it works through the existing first-write-wins read path, not a new one.

The two carried-forward code-quality findings (CR-01, WR-01) are real, verified bugs in code Phase 12 owns: `_is_sentinel_identifier()` treats any filename identifier starting with `_` as a placeholder, but `_RE_SANITIZE_HELPER_NAME = re.compile(r'[^\w\-]')` (`pipeline/config.py:28`) sanitizes a real name's leading space/apostrophe/paren to `_` too — without a `.strip()` first (`pipeline/excel.py:308,324`) — so the sentinel-superseded attachment-cleanup gate (`pipeline/cleanup.py:495-508`) can delete a real person's historical attachment. This must ship a fix plus a regression test in the same PR that touches ownership code, because it sits in the protected attachment-cleanup path.

For OWN-03's Source 5 (cell history), the design spec says to reuse the pattern in `audit_billing_changes.py` — but that "pattern" (`_selective_cell_history_enrichment`, line 875) is a **stub that never calls the Smartsheet API** (`history_meta["history_available"] = True` is hardcoded). The actual working reference implementation, with real pacing/budget/cap discipline, is `pipeline/snapshot_drift.py:404-438` (`client.Cells.get_cell_history(sheet_id, row_id, column_id, include_all=True)`, self-pacing `time.sleep`, `max_rows`, `max_minutes` deadline, a pre-flight `TIME_BUDGET_MINUTES` budget guard). The new script should copy that pattern's *shape* (env-var-driven cap + pace + deadline), not the `audit_billing_changes.py` stub.

**Primary recommendation:** Scope the Phase 12 plan around four waves matching the four requirement IDs, but recognize OWN-01 as primarily a *documentation-and-provenance* task (not a new table) unless a `checkpoint:human-verify` with Juan confirms the table is wanted; ship CR-01/WR-01 fixes in the same PR as whichever OWN-02/OWN-03 diff range touches those files (per the Phase 11.1 review's own instruction — these findings were deliberately left for "the next diff range that touches this code"); build OWN-03's script and Source-5 workflow as genuinely new code following `pipeline/snapshot_drift.py`'s pacing pattern, not the `audit_billing_changes.py` stub; and treat every Supabase DDL/RPC change (the backup table, the two new `attribution_snapshot` columns, the `backfill_attribution` function) as **owner-deployed SQL shipped as a file in the PR**, never applied by pipeline code at runtime.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Claim-time ownership resolution (per row, per role) | API/Backend (Python pipeline, `billing_audit/writer.py`) | Database (Supabase `attribution_snapshot`, first-write-wins RPC) | `resolve_claimer` is a pure Python read against a Supabase-owned RPC; the pipeline never writes ownership logic into the DB layer beyond calling the owner-deployed RPC |
| Sentinel detection (`is_sentinel_claimer`) | API/Backend | — | Single source of truth already lives in `billing_audit/writer.py`; `pipeline/cleanup.py` imports it lazily rather than re-implementing |
| Historical backfill (sources 1–4) | API/Backend (new script) | Database (read-only queries against `pipeline_memory`/`attribution_snapshot`/`public.artifacts`) | Script reads three existing Supabase surfaces plus one frozen JSON import; writes go through the new owner-deployed RPC only |
| Historical backfill (source 5, cell history) | API/Backend (new script, separate workflow) | External Service (Smartsheet Cell History API) | Deliberately isolated from the production run (own GitHub Actions workflow) — a rate-limited external-API capability, not a normal pipeline stage |
| Attachment cleanup (sentinel-superseded gate) | API/Backend (`pipeline/cleanup.py`) | External Service (Smartsheet Attachments API) | Already shipped; CR-01 fix stays in this tier |
| Ownership decision log (`wr_week_ownership`, if built) | Database | API/Backend (writer) | Would be a Supabase table like the other `pipeline_memory` tables — but per Open Question #1, may not need to exist as a distinct table at all |
| Excel filename/partition assignment | API/Backend (`pipeline/excel.py`, `pipeline/grouping.py`) | — | Consumes `resolve_claimer()` output already; no architectural change needed once `attribution_snapshot` is backfilled |

## Standard Stack

### Core

No new external packages are required for this phase — every capability (Supabase RPC calls, Smartsheet cell history, dry-run report generation) is served by libraries already pinned in `requirements.txt` and already used elsewhere in this codebase for structurally identical work.

| Library | Version (pinned, `requirements.txt`) | Purpose | Why Standard (already used for this exact pattern) |
|---------|---------|---------|--------------|
| `smartsheet-python-sdk` | `4.3.0` [VERIFIED: requirements.txt:9] | `client.Cells.get_cell_history(...)` for Source 5 | Already used identically in `pipeline/snapshot_drift.py:410-412` |
| `supabase` | `2.31.0` [VERIFIED: requirements.txt:30] | RPC calls to the new `backfill_attribution` function, reads against `pipeline_memory.row_event`/`row_state` | Same client used by every existing `billing_audit`/`pipeline_memory` writer/reader |
| `sentry-sdk` | `>=2.54.0` [VERIFIED: requirements.txt:2] | Error-boundary wrapping around the new script's Supabase/Smartsheet calls, per `.claude/rules/smartsheet-python-optimization.md` §3 | House convention for all new scripts touching Smartsheet writes/reads |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pandas` | `2.2.2` [VERIFIED: requirements.txt:16] | Building the dry-run CSV report (`generated_docs/own03_backfill_report.csv` per spec §5) | Only if the report needs tabular transforms beyond plain `csv`/`json` — a plain `csv.DictWriter` is likely sufficient and avoids a pandas dependency for a one-off script |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Owner-deployed RPC (spec §4 option 1, decided) | Owner-reviewed raw SQL file (spec §4 fallback, option 2) | Option 1 chosen — keeps `freeze_attribution`'s existing first-write-wins invariant enforced server-side instead of trusting the script to get the WHERE clause right every run |
| New `scripts/backfill_claim_time_attribution.py` | Extend existing `scripts/backfill_attribution_snapshot.py` | **Do not extend the existing script** — it does something structurally different (freezes the CURRENT Smartsheet value for a week; see Common Pitfalls) and reusing it would silently violate the "never touches a real name, sources 1–4 only, no cross-week lookup" contract |

**Installation:** No new packages — nothing to add to `requirements.txt`.

## Package Legitimacy Audit

Not applicable — this phase introduces zero new third-party dependencies. Every library used is already pinned and already used for a directly analogous purpose elsewhere in the codebase (see Standard Stack table with file:line citations).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                         PRODUCTION RUN (generate_weekly_pdfs.py, every ~2h)
                         ─────────────────────────────────────────────────
Smartsheet rows ──► fetch.py (__effective_user, falls back to 'Unknown Foreman'
                     when blank — pipeline/fetch.py:885-908)
                         │
                         ▼
              freeze_row() [billing_audit/writer.py:520]
                  - nulls NAMED sentinels before RPC (existing)
                  - calls owner-deployed freeze_attribution RPC (first-write-wins)
                         │
                         ▼
         Supabase: billing_audit.attribution_snapshot
         (frozen per-row primary/helper/vac_crew; PK = wr+week_ending+row_id)
                         │
                         ▼
              resolve_claimer() [billing_audit/writer.py:1058]
                  - reads frozen value via lookup/prefetch RPC
                  - frozen sentinel ⇒ read as no-history (OWN-02, shipped)
                  - frozen real name ⇒ wins over current Smartsheet value
                  - no frozen row ⇒ use current value ("no_history")
                         │
                         ▼
        pipeline/grouping.py Subproject B/C/D partition-by-claimer
        (ALREADY consumes resolve_claimer output — no change needed
         once attribution_snapshot holds real names)
                         │
                         ▼
        pipeline/excel.py filename ("_User_<name>") + pipeline/cleanup.py
        sentinel-superseded attachment prune (CR-01 lives here)


                         OWN-03 BACKFILL (one-time, offline, dry-run-first)
                         ────────────────────────────────────────────────
  scripts/backfill_claim_time_attribution.py (NEW)
     │
     ├─ Source 1: pipeline_memory.row_event / row_state
     │             (foreman_observed/helper_observed/vac_crew_observed
     │              + units_completed/helper_completed/vac_completed,
     │              pipeline_memory/schema.sql:100-170)
     ├─ Source 2: non-sentinel attribution_snapshot rows, same row
     ├─ Source 3: public.artifacts filenames (supabase/portal_schema.sql:24)
     ├─ Source 4: frozen 2025 hash_history.json import
     └─ Source 5 (SEPARATE JOB, own workflow, off-hours cron):
                  scripts/backfill_cell_history_attribution.py (NEW)
                  client.Cells.get_cell_history(...) pattern copied from
                  pipeline/snapshot_drift.py:404-438 (self-paced, capped)
     │
     ▼
  --dry-run (default): generated_docs/own03_backfill_report.json + .csv
     │  (Juan reviews; known-good sample WR 19073866 must match)
     ▼
  --apply --i-approved-this:
     copy affected rows → attribution_snapshot_backup_<date>  (rollback path)
     → billing_audit.backfill_attribution(p_rows jsonb) RPC   (OWNER-DEPLOYED,
        SQL shipped as a file in the PR, applied by Juan in Supabase SQL editor —
        never executed by pipeline/script code)
     → writes ONLY where current value is sentinel/NULL; never touches a real name
     │
     ▼
  Next scheduled run: resolve_claimer() picks up the backfilled real name
  automatically (no grouping-code change); sentinel-superseded cleanup gate
  (pipeline/cleanup.py) removes the stale _Unknown_Foreman attachment.
```

### Recommended Project Structure

```
scripts/
├── backfill_attribution_snapshot.py         # EXISTING — different purpose, do not extend
├── backfill_claim_time_attribution.py       # NEW — OWN-03 sources 1–4, dry-run first
└── backfill_cell_history_attribution.py     # NEW — OWN-03 source 5, separate workflow only
.github/workflows/
└── cell-history-backfill.yml                # NEW — workflow_dispatch + weekend cron,
                                              #   modeled on weekly-excel-generation.yml's
                                              #   schedule + advanced_options patterns
billing_audit/
└── schema.sql                               # add comment block documenting the
                                              # owner-deployed backfill_attribution RPC
                                              # contract (mirrors the existing
                                              # freeze_attribution contract comment,
                                              # lines 173-201)
pipeline/
├── cleanup.py                               # CR-01 fix: _is_sentinel_identifier
└── orchestrate.py                           # WR-01 fix: lazy AttachmentParentType import
generated_docs/
└── own03_backfill_report.{json,csv}         # dry-run report output (gitignored,
                                              # same convention as existing generated_docs/*)
```

### Pattern 1: Reading `attribution_snapshot` via the RPC contract, not raw SQL

**What:** All reads of frozen attribution go through `billing_audit.writer.lookup_attribution` / `_lookup_attribution_all` / `prefetch_attribution` — never a direct `supabase.table(...).select(...)` call.
**When to use:** Any new code (including OWN-03's backfill dry-run report) that needs to know "what is currently frozen for this row" should reuse `_lookup_attribution_all` or `prefetch_attribution`, not hand-roll a query — the RPC already normalizes `#`-tokens and blanks to NULL server-side (`billing_audit/schema.sql:237-240`).
**Example:**
```python
# Source: billing_audit/writer.py:1120 (verified this session)
row, status = _lookup_attribution_all(wr, week_ending, row_id)
# status ∈ {"success", "no_row", "fetch_failure", "unavailable"}
```

### Pattern 2: Owner-deployed Supabase DDL/RPC, shipped as a reviewable SQL file

**What:** `billing_audit/schema.sql` documents (but does not itself apply) RPCs whose body is "owned by the data team" — the file carries an extensive contract comment (parameter names, return shape, a `DROP FUNCTION IF EXISTS` note explaining why bare `CREATE OR REPLACE` silently failed once before) instead of the actual `CREATE FUNCTION freeze_attribution ...` body.
**When to use:** The new `backfill_attribution` RPC and the `attribution_snapshot_backup_<date>` table follow this exact pattern — ship the SQL as a reviewable block in `billing_audit/schema.sql` (or a new `docs/superpowers/specs/` companion) with an "OPERATOR: apply this in the Supabase SQL Editor" instruction, per the existing convention at `billing_audit/schema.sql:246-248`.
**Example:**
```sql
-- Source: billing_audit/schema.sql:173-201 (contract-comment pattern to copy)
-- The ``freeze_attribution`` Postgres function is NOT defined here — its body is
-- deployed and maintained directly in the Supabase project...
-- PARAMETERS (all named, p_<name>): ...
-- RETURNS: ...
```

### Pattern 3: Rate-limited, self-paced Smartsheet cell-history reads

**What:** `pipeline/snapshot_drift.py:404-438` — a working, budget-aware pattern for `client.Cells.get_cell_history`.
**When to use:** OWN-03 Source 5. Copy the shape: `max_rows` cap, `pace_sec` self-throttle (`time.sleep` between calls, never before the first), a wall-clock `deadline`, and a pre-flight budget check gated on `GITHUB_ACTIONS`/`TIME_BUDGET_MINUTES` so a slow environment degrades gracefully instead of stalling.
**Example:**
```python
# Source: pipeline/snapshot_drift.py:404-412 (verified this session — real, working call)
def _fetch_history(sheet_id: int, row_id: int, column_id: int) -> Any:
    if called_once[0]:
        time.sleep(pace_sec)
    called_once[0] = True
    return client.Cells.get_cell_history(
        sheet_id, row_id, column_id, include_all=True
    )
```

### Anti-Patterns to Avoid

- **Reusing `audit_billing_changes.py::_selective_cell_history_enrichment` as the Source-5 implementation:** it is a stub — `history_meta["history_available"] = True` is hardcoded (`audit_billing_changes.py:900-901`), it never calls `client.Cells.get_cell_history`. The design spec's phrase "reuses the selective cell-history pattern" means the *selectivity* idea (only fetch for implicated rows), not working code. Use `pipeline/snapshot_drift.py`'s pattern instead.
- **Extending `scripts/backfill_attribution_snapshot.py` for OWN-03:** that script freezes rows from the **current** Smartsheet state for a target week (`"Populates ... from current completed rows in Smartsheet"`, `scripts/backfill_attribution_snapshot.py:3-4`) — the exact "current always wins" semantics Juan rejected for the claim-time ladder (ledger `[2026-09-01 19:45]` item (a): "current always wins (policy C) is rejected for good"). A new script is required.
- **Writing ownership logic into `pipeline/grouping.py` or `pipeline/excel.py`:** both already consume `resolve_claimer()`'s output faithfully; OWN-03's backfill working through the existing `attribution_snapshot` table means these files likely need **zero** changes for OWN-02/03. Resist the temptation to add a parallel `wr_week_ownership` read path into grouping unless Open Question #1 is explicitly resolved in favor of building that table.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sentinel detection | A new regex/string-match function in the backfill script | Import `billing_audit.writer.is_sentinel_claimer` | Single source of truth already exists; `pipeline/cleanup.py:113` already imports it lazily for exactly this reason — a second implementation risks the two drifting (this is literally how CR-01 happened — a *related but not identical* heuristic in `cleanup.py`) |
| Smartsheet cell-history retry/rate-limit handling | Bespoke retry loop in the new script | `smartsheet-python-sdk`'s built-in 429 handling (already relied on everywhere per `.claude/rules/smartsheet-python-optimization.md` §1) + the `pace_sec`/`max_rows`/`deadline` pattern from `pipeline/snapshot_drift.py` | Custom retry loops duplicate SDK behavior and risk exceeding the 300 req/min budget in ways the SDK already guards against |
| WR sanitization for filename/identifier matching | A new sanitize function for the backfill's `public.artifacts` filename parsing (source 3) | `pipeline.config._RE_SANITIZE_HELPER_NAME` / `_WR_SANITIZE` in `billing_audit/writer.py` | Two independently-maintained sanitizers is the root cause of both CR-01 and the earlier PR #375 helper-path week-key miss (ledger `[2026-09-01 18:55]`) — reuse the existing compiled regex constants, do not write parallel ones |
| First-write-wins concurrency control | Application-level locking around the backfill's writes | The existing `freeze_attribution`/`backfill_attribution` RPC semantics (server-side, first-write-wins by construction) | This is exactly what the owner-deployed RPC pattern exists to centralize — do not attempt to enforce "only write if sentinel" in Python; enforce it in the SQL `WHERE` clause as spec §4 already specifies |

**Key insight:** Nearly everything OWN-03 needs already has a working analog somewhere in this codebase (`snapshot_drift.py` for rate-limited history, `backfill_attribution_snapshot.py` for the CLI/argparse date-validation shape, `writer.py` for sentinel detection and RPC-contract-as-comment). The actual new code surface is small: one new script that reads four existing surfaces and calls one new RPC, plus one new isolated workflow for Source 5.

## Runtime State Inventory

> Included: OWN-03 is a one-time backfill/remediation of existing Supabase state and stale Smartsheet attachments — this is functionally a data migration, even though it is not a rename/rebrand.

> **Row/WR counts are point-in-time ledger snapshots, not live measurements.** This table's
> "5,829 rows / 94 WRs" is the 2026-09-01 ledger count; ROADMAP.md, REQUIREMENTS.md and
> `12-06-PLAN.md` cite "5,824 rows / 93 WRs" from the 2026-08-24 ledger entry. Neither figure
> is authoritative — the backfill script counts sentinel rows dynamically, and the
> **authoritative live count is the one `12-06-PLAN.md` Task 1's dry-run report emits**. Do
> not hard-code either historical number anywhere.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `billing_audit.attribution_snapshot` — 5,829 rows / 94 WRs (per ledger, count as of 2026-09-01) hold the sentinel `Unknown Foreman`/`Unknown Helper`/`Unknown VAC Crew` verbatim in `frozen_<role>` columns (exact column names NOT verified — see Assumptions Log A1). | **Data migration**: the new `backfill_attribution` RPC updates these rows in place, sentinel/NULL-only, with a pre-write backup copy to `attribution_snapshot_backup_<date>`. |
| Stored data | `pipeline_memory.row_event`/`row_state` — has been capturing `foreman_observed`/`helper_observed`/`vac_crew_observed` since Phase 10 shadow writes began (~2026-08-2x); does not cover weeks before that. | No migration — read-only source 1 for the backfill; older weeks fall through to sources 3–5. |
| Live service config | `public.artifacts` filenames encode `_User_<name>`/`_Helper_<name>`/`_VacCrew_<name>` per WR+week — this table lives in the `portal-v2`/Supabase `public` schema (`supabase/portal_schema.sql:24`), separate from `billing_audit`/`pipeline_memory`. | Read-only source 3; no write needed to this table. |
| Stored data | `2025 hash_history.json` — explicitly described as "frozen import; the file itself is retired" (spec §3 row 4) — i.e. this is a **static, no-longer-updated artifact** that must be re-read from wherever it was archived (it is NOT the live `hash_history.json` the codebase retired in Phase 11 Plan 08 / INC-05 — confirm its archived location before the plan assumes a path; not found in this session's search). | **Verify location** before planning assumes a path — flagged as Open Question #3. |
| OS-registered state | None found — GitHub Actions workflows (`.github/workflows/*.yml`) are the only "registered" automation; a new workflow file for Source 5 is additive, not a rename of an existing schedule. | None. |
| Secrets/env vars | No new secrets required — `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`/`SMARTSHEET_API_TOKEN` already exist and are reused as-is by both new scripts. | None. |
| Build artifacts | None — no packaging/build step changes; `generated_docs/own03_backfill_report.{json,csv}` is a new **output** file, not a build artifact requiring reinstall. | None. |
| Live attachments | 93 WRs' stale `_User_Unknown_Foreman` (and helper/VAC equivalents) attachments on `TARGET_SHEET_ID` — these are NOT deleted by the backfill itself; the already-shipped sentinel-superseded cleanup gate (PR #377, `pipeline/cleanup.py:495-508`) removes them **on the next scheduled run after a real name is frozen**, provided CR-01 does not cause a false-positive deletion of a *different* real person's attachment in the interim. | No direct action in OWN-03; **CR-01 fix is a prerequisite for this cleanup to be trustworthy** at the volume 93 WRs will produce. |

## Common Pitfalls

### Pitfall 1: Treating `attribution_snapshot`'s exact write-side column names as known

**What goes wrong:** The design spec (§4) refers to `frozen_primary` / `frozen_helper` / `frozen_vac_crew`; the Python read contract (`billing_audit/schema.sql:207-211,232-234`) documents the RPC's *returned* columns as `primary_foreman`, `helper`, `vac_crew`, `helper_dept`, `source_run_id`. The underlying table DDL is explicitly **not in this repo** — "owned by the data team" — so the actual column names the `backfill_attribution` RPC's `UPDATE` statement must target are not verifiable from the codebase.
**Why it happens:** `attribution_snapshot`'s schema is intentionally opaque to the pipeline (`billing_audit/schema.sql:213-220`); only the RPC I/O contract is documented.
**How to avoid:** The OWN-03 PR's SQL file (Pattern 2) must be reviewed by Juan against the actual live table before he pastes it into the Supabase SQL editor — treat the exact `UPDATE ... SET` column list as something the plan hands to a `checkpoint:human-verify`, not something the plan asserts.
**Warning signs:** A `backfill_attribution` RPC that references a column name not confirmed against the live schema will fail loudly at deploy time (Postgres `column does not exist`) — better than a silent no-op, but still a wasted round trip if not caught before the checkpoint.

### Pitfall 2: CR-01 — leading-character sanitization collision (verified defect, unfixed)

**What goes wrong:** `pipeline/cleanup.py:110-111` treats any filename identifier starting with `_` as a sentinel. `_RE_SANITIZE_HELPER_NAME = re.compile(r'[^\w\-]')` (`pipeline/config.py:28`) converts every non-word/non-hyphen character to `_`, and `pipeline/excel.py:308,324` apply it to the raw name with **no `.strip()` first**. A real foreman name like `" O'Brien"` (leading space) or `"(Contractor) Smith"` sanitizes to a leading `_`, and `_is_sentinel_identifier` then classifies it as a placeholder.
**Why it happens:** The heuristic was added reactively (PR #377, "Codex on PR #377" per the code comment) to catch sanitized Smartsheet error tokens (`#REF!` → `_REF_`) without checking for false positives on real names with leading punctuation.
**How to avoid:** Per the Phase 11.1 review's own recommended fix shape (`memory-bank/living-ledger.md:8892-8893`): narrow the heuristic to known sanitized error spellings (`_REF_`, `_INVALID`, `_NO_MATCH`, …) **or** de-sanitize/strip before calling `is_sentinel_claimer`. Add a regression test with a leading-space name (`tests/test_sentinel_never_a_claimer.py` is the right home — mirror `SentinelPredicateTests`).
**Warning signs:** A real claimer's historical Excel attachment silently disappears from `TARGET_SHEET_ID` after a run where a different claimer's file for the same `(wr, week, variant)` was generated — the sentinel-superseded gate (`cleanup.py:495-508`) is the mechanism.

### Pitfall 3: The `wr_week_ownership` design-draft schema is not deployed and may not match what's needed

**What goes wrong:** Planning code around the 2026-08-24 draft schema (`docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md:98-105`) — which includes a `last_known_before_week` value in its `owner_source` CHECK constraint — silently reintroduces the cross-week inheritance that was explicitly decided OFF on 2026-09-01 19:55.
**Why it happens:** The draft predates the actual decision by ~8 days; nothing in the repo auto-flags that the draft is stale.
**How to avoid:** If the plan does build a `wr_week_ownership` table, its `owner_source` CHECK must be `('observed_in_week', 'backfill_artifacts', 'backfill_hash_history', 'operator')` — **no `last_known_before_week`**. `pipeline_memory/schema.sql:41-48` already explicitly documents that this table was deliberately NOT shipped in Phase 10/11 and is scoped to Phase 12 — treat that comment as the up-to-date pointer, not the 2026-08-24 draft body.
**Warning signs:** Any code or SQL literal containing the string `last_known_before_week`.

### Pitfall 4: Confusing `scripts/backfill_attribution_snapshot.py` (existing) with the new OWN-03 script

**What goes wrong:** The existing script's docstring says "Populates `billing_audit.attribution_snapshot` from current completed rows in Smartsheet" — i.e., it performs exactly the "current always wins" semantics Juan rejected for claim-time ownership. Running it against the 93 affected WRs post-Phase-12 would overwrite sentinel-cleared rows with whatever Smartsheet shows *today*, not the historically-correct claimer.
**Why it happens:** Naming similarity (`backfill_attribution_snapshot.py` vs. the new `backfill_claim_time_attribution.py`) invites confusion for anyone running commands from muscle memory.
**How to avoid:** Document the distinction explicitly in OWN-04's runbook update; consider a distinct, non-confusable script name (already reflected in the design spec: `scripts/backfill_claim_time_attribution.py`).

### Pitfall 5: PARALLEL_WORKERS / rate-limit budget collision if Source 5 ever runs inside the production window

**What goes wrong:** The design spec is explicit that Source 5 must **never** run inside `generate_weekly_pdfs.py` — both share the same Smartsheet API token and the same 300 req/min budget (`CLAUDE.md` → Smartsheet API Integration Standards).
**Why it happens:** A future maintainer might be tempted to wire Source 5 as a flag on the main script for convenience.
**How to avoid:** Keep it a genuinely separate GitHub Actions workflow (own `workflow_dispatch` + cron, per the locked decision), never an env-var-gated branch inside `weekly-excel-generation.yml`.
**Warning signs:** Any PR that adds a `SOURCE_5_ENABLED`-style flag read inside `generate_weekly_pdfs.py` or `pipeline/orchestrate.py`.

## Code Examples

### Sentinel detection — reuse, do not reimplement

```python
# Source: billing_audit/writer.py:105-115 (verified this session)
def is_sentinel_claimer(value: Any) -> bool:
    """True when *value* is blank, a Smartsheet ``#`` error token, or one
    of the pipeline's placeholder claimer names — i.e. NOT a person.
    Exact family only: ``Unknown Person`` is a name, not a sentinel."""
    if value is None:
        return True
    text = str(value).strip()
    if not text or text.startswith("#"):
        return True
    normalized = " ".join(text.replace("_", " ").split()).casefold()
    return normalized in _SENTINEL_CLAIMERS
```

### Cell-history read with pacing/budget/cap (the real pattern to copy for Source 5)

```python
# Source: pipeline/snapshot_drift.py:371-412 (verified this session)
max_rows = _int_env("SNAPSHOT_DRIFT_MAX_ROWS", 40)
pace_sec = _float_env("SNAPSHOT_DRIFT_PACE_SEC", 2.0)
max_minutes = _float_env("SNAPSHOT_DRIFT_MAX_MINUTES", 5.0)
# ... pre-flight TIME_BUDGET_MINUTES guard, then:
def _fetch_history(sheet_id, row_id, column_id):
    if called_once[0]:
        time.sleep(pace_sec)
    called_once[0] = True
    return client.Cells.get_cell_history(
        sheet_id, row_id, column_id, include_all=True
    )
```

### RESET_WR_LIST scoping — already shipped, do not re-plan

```python
# Source: pipeline/orchestrate.py:412-430 (verified this session)
def _reset_list_forces_regeneration(
    wr_num: object, reset_wr_list: set | None
) -> bool:
    """True when ``wr_num`` is named in ``RESET_WR_LIST``.
    Owner-approved scoping (2026-09-01, ledger [2026-09-01 19:45]):
    a per-WR reset purges and regenerates ONLY the listed WRs."""
    if not reset_wr_list:
        return False
    # ... membership check via pipeline.config._normalize_reset_wr
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| "Current Smartsheet value always wins" (policy C) for ownership | Claim-time / as-of-the-week per row, per role — a later Smartsheet edit is an audit event, not a re-attribution | Decided 2026-09-01 19:45 (ledger) | This IS the ownership-semantics change Phase 12 exists to implement; do not build anything that reverts to policy C |
| Local JSON caches (`hash_history.json`, `discovery_cache.json`, `billing_audit_frozen_rows.json`) as cross-run memory | `pipeline_memory.*` Supabase tables (`row_event`, `row_state`, `group_state`, `sheet_registry`) | Retired Phase 11 Plan 08 / INC-05 | Source 4's `hash_history.json` is explicitly a **frozen, no-longer-updated** one-time import for this reason — not a live source |
| Bulk attachment pre-fetch (`ATTACHMENT_PREFETCH_MAX_MINUTES`) | Attachment identity resolved from `pipeline_memory.group_state` | Phase 11 Plan 08 (INC-05) | Both env vars are documented no-ops — do not reference them in any new OWN-03 code or docs |

**Deprecated/outdated:** `ATTACHMENT_PREFETCH_MAX_MINUTES` / `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` (no effect); `DISCOVERY_CACHE_TTL_MIN` / `USE_DISCOVERY_CACHE` (retired, discovery now validates every sheet every run).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `attribution_snapshot`'s actual write-side column names match the RPC's documented read-side names (`primary_foreman`, `helper`, `vac_crew`) closely enough that the design spec's `frozen_primary`/`frozen_helper`/`frozen_vac_crew` naming is descriptive, not literal | Pitfall 1, Locked Decision #5 | The owner-deployed `backfill_attribution` SQL references a nonexistent column and fails at deploy — caught immediately (loud Postgres error), not silently, so risk is schedule-only, not correctness |
| A2 | The frozen 2025 `hash_history.json` (source 4) is archived somewhere accessible to the new backfill script — its post-retirement location was not found in this session's search | Runtime State Inventory | If the file location is wrong/missing, source 4 silently contributes zero rows and more WRs fall through to source 5 (cell history), which is slower and rate-limited — a correctness gap only if source 4 rows genuinely can't be recovered another way |
| A3 | Building a literal `wr_week_ownership` table (vs. relying on `attribution_snapshot` + provenance columns) is genuinely undecided, not just under-specified | Open Question #1, Locked Decision (Claude's Discretion) | If wrong (i.e., Juan actually does want the table per REQUIREMENTS.md's literal wording), skipping it under-delivers OWN-01; flagged explicitly as a checkpoint rather than assumed either way |
| A4 | No GitHub Actions workflow already exists for Source 5's off-hours cron slot (checked `.github/workflows/*.yml` — 11 files present, none named for cell-history backfill) | Recommended Project Structure | Low risk — worst case is a naming collision caught in code review |

**If this table is empty:** N/A — populated above; all four claims are either self-correcting-if-wrong (loud failure) or explicitly routed to a checkpoint.

## Open Questions (RESOLVED)

> All four questions below were answered before planning closed. The question text is left
> verbatim as the record of what was uncertain; each carries a **RESOLVED:** pointer naming
> the decision, plan or task that now owns it.

1. **Does OWN-01 require building the literal `wr_week_ownership` table, or is the ladder satisfied by `attribution_snapshot` + the two new provenance columns?**
   - **RESOLVED: D-12-A** (2026-09-01 19:55) — no `wr_week_ownership` table in Phase 12. OWN-01 is satisfied by `attribution_snapshot` + `resolve_claimer` plus the new `backfill_source` / `backfill_run_id` provenance columns; the table is deferred to Phase 13. Recorded in `12-01-PLAN.md` § Decisions this plan implements and applied by `12-03-PLAN.md`. The `last_known_before_week` cross-week rung in REQUIREMENTS.md is stale and deliberately NOT implemented.
   - What we know: REQUIREMENTS.md and ROADMAP.md both name `wr_week_ownership` explicitly as OWN-01's deliverable and OWN-02's partition source. `pipeline_memory/schema.sql:41-48` confirms the table was deliberately NOT shipped in Phase 10/11 and is "scoped to Phases 12/13." The 2026-08-24 design draft has a full schema for it. But the 2026-09-01 OWN-03 design spec — the most recent, most detailed, Juan-approved artifact — never mentions the table; it writes backfilled values directly into the existing `attribution_snapshot` table that `resolve_claimer` already reads, and spec §7 proposes `backfill_source`/`backfill_run_id` as new *columns on `attribution_snapshot`*, not as fields feeding a separate ownership table.
   - What's unclear: whether the table is still wanted as an audit/query surface for OWN-04's documentation purposes, or whether it was silently superseded by the simpler "extend `attribution_snapshot`" approach once the write-path decision (§4 option 1) was made.
   - Recommendation: Raise this as an explicit `checkpoint:human-verify` (or a discuss-phase question) before the plan commits to (or skips) a new-table migration. Building it unnecessarily is schema debt Juan owns (Supabase migrations require his approval per `.claude/rules/production-guardrails.md`); skipping it when it's actually wanted under-delivers a named requirement.

2. **Exact column names on the live `billing_audit.attribution_snapshot` table** (see Pitfall 1 / Assumption A1) — not discoverable from this repo; the plan should route the RPC SQL through Juan for confirmation against the live schema before merge, per the existing convention that this table's DDL is data-team-owned.
   - **RESOLVED: routed, not guessed** — `12-03-PLAN.md`'s `checkpoint:human-verify` has Juan confirm the write-side role column names against the live schema before he applies the SQL file, and `12-03-SUMMARY.md` records the confirmed names. No plan asserts a column name.

3. **Where is the frozen 2025 `hash_history.json` (source 4) archived post-retirement?** Not found in this session's repo search (the retired JSON caches were removed from the working tree; only `generated_docs/billing_audit_frozen_rows.json` — a different file — is currently untracked in the working directory per `git status`). The plan needs to locate this file (git history? a release artifact? Juan's local archive?) before source 4 can be implemented — flag as a blocking question for the plan's first task, not something to guess at.
   - **RESOLVED: mooted by D-12-B** — source 4 no longer reads any JSON file. It reads the Supabase hash store (`billing_audit.group_content_hash` + `pipeline_memory.group_state`), so there is no archived-file location to find, no `--hash-history <path>` flag and no JSON fixture. Implemented by `12-01-PLAN.md` Task 1's `resolve_source_4`.

4. **Exact off-hours cron slot for Source 5**: the design spec says "Saturday-midnight-Central / Sunday 05:00Z cron while a backlog exists" — this needs a concrete stop condition (how does the workflow know "a backlog exists" and self-disable?). Likely answer: check the count of remaining sentinel rows in `attribution_snapshot` at the start of the run and no-op (or auto-disable) if zero — but this specific mechanism is not spelled out in the spec and needs a plan-level decision.
   - **RESOLVED: routed to `12-04-PLAN.md`** — the cron slot is confirmed at that plan's `checkpoint:decision`, and the stop condition is the `--check-backlog` mechanism (count remaining sentinel rows at start of run; no-op when zero) built in the same plan.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `smartsheet-python-sdk` | Source 5 cell-history reads | [VERIFIED: requirements.txt:9] | `4.3.0` | — |
| `supabase` (Python client) | Reading `pipeline_memory`/`attribution_snapshot`; calling `backfill_attribution` RPC | [VERIFIED: requirements.txt:30] | `2.31.0` | — |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` env vars | All Supabase reads/writes in the new scripts | Assumed present (already required by every existing `billing_audit`/`pipeline_memory` writer) | — | Script must exit non-zero if `get_client()` returns `None`, mirroring `scripts/backfill_attribution_snapshot.py`'s existing contract |
| `SMARTSHEET_API_TOKEN` | Source 5 workflow | Assumed present (existing production secret) | — | — |
| GitHub Actions runner (for Source 5's own workflow) | Off-hours cron job | [VERIFIED: `.github/workflows/` contains 11 existing workflow files, confirming the CI platform and pattern are already in place] | — | — |

**Missing dependencies with no fallback:** none identified — this phase is code/config-only against already-provisioned infrastructure.

**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (unittest-style `TestCase` classes throughout) [VERIFIED: `tests/test_sentinel_never_a_claimer.py`, `tests/test_billing_audit_shadow.py`] |
| Config file | none found dedicated to pytest config beyond defaults — tests run via `pytest tests/ -v` per CLAUDE.md |
| Quick run command | `python -m pytest tests/test_sentinel_never_a_claimer.py -q` (existing OWN-02 suite — 14 tests / 1 skipped as of the #376 gate run) |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OWN-01 (ladder / no cross-week inheritance) | A row with no in-week observation stays sentinel even if a prior week had a real claimer for the same WR | unit | `python -m pytest tests/test_sentinel_never_a_claimer.py -q` (extend `ResolveClaimerSentinelTests`, `billing_audit/writer.py:111`) | ❌ Wave 0 — no test yet asserts absence of cross-week inheritance |
| OWN-02 (residual — CR-01 fix) | A real claimer name with a leading space/apostrophe/paren is NOT treated as a sentinel by `_is_sentinel_identifier` | unit | `python -m pytest tests/test_cleanup.py -q -k sentinel` (verify file name — if no dedicated `tests/test_cleanup.py` exists, add one; grep confirms `cleanup.py` functions are not covered by `test_sentinel_never_a_claimer.py`, which only tests `billing_audit/writer.py`) | ❌ Wave 0 — regression test for the leading-punctuation case does not exist |
| OWN-02 (WR-01 fix) | `orchestrate.py` imports `AttachmentParentType` lazily, matching `discovery.py`'s guarded pattern | unit / static | `python -m pytest tests/test_billing_audit_shadow.py -q -k import` or a grep-based structural test mirroring `test_backfill_splits_dotenv_import_error_from_runtime_error`'s `_read_source`/`_collapse_ws` pattern (`tests/test_billing_audit_shadow.py:2617-2638`) | ❌ Wave 0 |
| OWN-03 (dry-run report correctness) | `--dry-run` produces a report matching known-good WR 19073866 (WE 082425/083125/091425/092125 → `_User_Avery_Example` via `backfill_hash_history`) | integration (fixture-driven, no live Smartsheet/Supabase writes) | `python -m pytest tests/test_backfill_claim_time_attribution.py -q` (new file, mirror `BackfillCliDateValidationTests` structure at `tests/test_billing_audit_shadow.py:2589`) | ❌ Wave 0 — entire new test file |
| OWN-03 (RPC never touches a real name) | The `backfill_attribution` RPC's `WHERE` clause is exercised against a fixture proving a real name is never overwritten | unit (Python-side param construction, since the RPC body itself is owner-deployed and untestable from this repo) | same new test file — assert the script never sends `p_rows` for a row whose current `frozen_<role>` is non-sentinel | ❌ Wave 0 |
| OWN-04 (documentation) | N/A — doc-only requirement | manual-only | N/A (verify via `cd website && npm run build` per `.claude/rules/documentation-maintenance.md`) | N/A |

### Sampling Rate

- **Per task commit:** targeted test file for the touched area (e.g., `python -m pytest tests/test_sentinel_never_a_claimer.py -q` after a `writer.py` change; `python -m py_compile generate_weekly_pdfs.py` after any pipeline-module change)
- **Per wave merge:** `python -m pytest tests/ -q` + `bash scripts/run_6_gates.sh` (existing 6-gate harness: AST import equality, facade completeness, pytest, mypy delta, py_compile, golden run_summary structural diff — [VERIFIED: `scripts/run_6_gates.sh:22-30`])
- **Phase gate:** Full suite green (`bash scripts/run_6_gates.sh`) before `/gsd:verify-work`; additionally, OWN-03's dry-run report must be manually reviewed against the WR 19073866 known-good sample before any `--apply` run (this is a human checkpoint, not an automated gate)

### Wave 0 Gaps

- [ ] `tests/test_backfill_claim_time_attribution.py` — new file; covers OWN-03 dry-run report generation, source precedence, no-cross-week-lookup, and never-overwrite-a-real-name behavior
- [ ] `tests/test_cleanup.py` (or extend an existing cleanup test file if one exists elsewhere — not found in this session's search) — covers CR-01's leading-punctuation regression
- [ ] A structural/grep-based test for WR-01's lazy-import fix, mirroring `tests/test_billing_audit_shadow.py:2617-2638`'s `_read_source`/`_collapse_ws` pattern
- [ ] Fixtures for the four backfill sources (mock `pipeline_memory.row_event` rows, mock `attribution_snapshot` rows, mock `public.artifacts` filenames, a small frozen `hash_history.json` fixture) — none of these exist yet; per `.claude/rules/production-python-safety` conventions (dry-run first, fixtures before live data), building these fixtures is itself Wave 0 work, not incidental to the script

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface — reuses existing `SUPABASE_SERVICE_ROLE_KEY` / `SMARTSHEET_API_TOKEN` |
| V3 Session Management | no | N/A — batch script, no sessions |
| V4 Access Control | yes | The `backfill_attribution` RPC must remain `GRANT EXECUTE ... TO service_role` only (mirror `billing_audit/schema.sql:287,332` pattern for `lookup_attribution`) — never expose it to `anon`/`authenticated` roles, since it can rewrite billing attribution |
| V5 Input Validation | yes | `p_rows jsonb` in the RPC must use explicit typed `jsonb_to_recordset(...)` column lists (mirror `pipeline_memory.upsert_rows_bulk`, `pipeline_memory/schema.sql:250-256`, "never dynamic SQL and never trusting client-shaped jsonb structurally") — this is the established house pattern for every jsonb-accepting RPC in this codebase |
| V6 Cryptography | no | No new cryptographic material — never hand-roll |
| V9 Communications | no | Existing HTTPS-only Supabase/Smartsheet SDK clients unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A backfill script accidentally overwriting a real frozen name (data-integrity, not classic security, but billing-critical) | Tampering | Enforce the sentinel/NULL-only `WHERE` clause **server-side** in the RPC (spec §4), not just in the Python caller — this is the whole reason option 1 (RPC) was chosen over option 2 (raw SQL) |
| SQL injection via dynamically-built `UPDATE` statements if the fallback (spec §4 option 2, raw SQL file) is ever used carelessly | Tampering | The generated `.sql` file must use parameterized values or safe literal escaping, never raw string interpolation of row/name values — mirror the `jsonb_to_recordset` typed-column pattern even in the fallback path |
| Privilege escalation via an overly-broad RPC grant | Elevation of Privilege | `GRANT EXECUTE ... TO service_role` only, `SET search_path = ''` with fully schema-qualified references (mirror `pipeline_memory/schema.sql:250-256`'s SECURITY note for `upsert_rows_bulk`) |
| Rate-limit exhaustion from Source 5 cascading into the production pipeline's own Smartsheet calls | Denial of Service | Strict isolation into its own workflow with its own cap (`max_rows`/`pace_sec`/`deadline`), never inside `generate_weekly_pdfs.py` — already a locked decision, not just a recommendation |

## Sources

### Primary (HIGH confidence — read directly this session)

- `docs/superpowers/specs/2026-09-01-own-03-claim-time-backfill-design.md` — full read, OWN-03 design with applied owner decisions
- `memory-bank/living-ledger.md` lines 8173-8332 (`[2026-09-01 18:05]`, `[18:55]`, `[19:45]`) and 8505-8556 (`[2026-09-02 00:35]`), 8884-8896 (Phase 11.1 CR-01/WR-01 advisory)
- `.planning/REQUIREMENTS.md:270-287`, `.planning/ROADMAP.md:694-720`, `.planning/STATE.md:295-320`
- `billing_audit/writer.py:85-220,520-580,1050-1146` — sentinel definitions, `freeze_row`, `resolve_claimer`
- `pipeline/cleanup.py:89-200` — `_is_sentinel_identifier`, CR-01 defect confirmed in code
- `pipeline/orchestrate.py:400-430,3540-3570` — `_reset_list_forces_regeneration` (confirms this residual item is already shipped)
- `pipeline_memory/schema.sql:40-320` — MEM-01 table DDLs, explicit confirmation `wr_week_ownership` is NOT shipped
- `billing_audit/schema.sql:32-470` — `freeze_attribution`/`lookup_attribution` RPC contract-as-comment pattern, `attribution_snapshot` "owned by the data team" note
- `pipeline/snapshot_drift.py:285-438` — working cell-history call pattern with pacing/budget/cap
- `audit_billing_changes.py:266-905` — confirmed `_selective_cell_history_enrichment` is a stub
- `scripts/backfill_attribution_snapshot.py:1-90` — confirmed this is a different (current-value) backfill tool
- `pipeline/excel.py:215-350`, `pipeline/config.py:24-28` — `_RE_SANITIZE_HELPER_NAME` regex, no-strip confirmation for CR-01
- `supabase/portal_schema.sql:24-51` — `public.artifacts` table definition
- `tests/test_sentinel_never_a_claimer.py`, `tests/test_billing_audit_shadow.py` — test structure and class inventory (grep-verified)
- `.planning/config.json` — `nyquist_validation: true`, `security_enforcement` absent (enabled)
- `requirements.txt` — pinned package versions

### Secondary (MEDIUM confidence)

- `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md:98-105` — `wr_week_ownership` draft schema (superseded status inferred, not stated explicitly anywhere)

### Tertiary (LOW confidence)

- None — no WebSearch was needed; this phase is entirely internal-codebase research with no external library/API unknowns.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, every pattern verified against existing working code with file:line citations
- Architecture (OWN-02/03 mechanics): HIGH — verified by reading the actual RPC contracts, resolver, and grouping code
- Architecture (OWN-01 `wr_week_ownership` table): MEDIUM/LOW — genuinely unresolved between two authoritative-looking sources; flagged as Open Question #1 rather than guessed
- Pitfalls (CR-01/WR-01): HIGH — both confirmed by reading the exact flagged code and the exact regex/sanitizer it collides with
- Source 5 (cell history): HIGH for the technical pattern (`snapshot_drift.py` is real, working code); MEDIUM for the workflow/cron shape (no existing precedent to copy verbatim, only `weekly-excel-generation.yml`'s general schedule syntax)

**Research date:** 2026-09-02
**Valid until:** 14 days (this phase sits on rapidly-evolving decisions — three owner-decision ledger entries landed within 24 hours of this research; re-verify against the ledger before executing if more than ~2 weeks elapse)
