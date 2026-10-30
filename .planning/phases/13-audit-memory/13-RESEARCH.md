# Phase 13: Audit Memory - Research

**Researched:** 2026-09-11
**Domain:** Supabase-backed finding-lifecycle persistence layered onto an existing, unmodified Python audit engine (`audit_billing_changes.py`), following the `pipeline_memory` conventions established in Phases 10-12.
**Confidence:** HIGH (code facts verified by direct Read of source; schema/pattern facts verified against `pipeline_memory/schema.sql` and `billing_audit/client.py`). The two facts the orchestrator flagged for verification are both resolved below.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Finding identity (spec §8 #6a — owner decision 2026-09-11)**
- **D-01 [owner]: Per-check natural key.** `finding_key = sha256` of the canonical `|`-joined, normalized identity fields for that check: `check_id` + the identity fields the check ALREADY emits + `week_ending` joined from the source row at persist time. The spec's draft template `sha(check_id|wr|week|cu|pole)` is superseded: no check emits `week` or `pole` today, and uniform placeholders would collapse distinct findings. Evidence values (prices, deltas, variance %) and Smartsheet `row_id` are NEVER part of the key — they live in `evidence jsonb`. Identity recipe (a durable contract; changing it orphans open findings):
  - `rate_sanity_mismatch` → `check_id | wr | week_ending | cu | work_type`
  - `price_variance_anomaly` → `check_id | wr | week_ending` (see D-CD-01 for pooled weeks)
  - `data_consistency_issue` → `check_id | wr | week_ending | sorted(issue codes)` (D-CD-02)
  The identity columns (`check_id`, `wr`, `week_ending`, `cu`, …) are ALSO stored as plain columns so history is queryable without unhashing. — **Reversibility:** one-way — a recipe change later requires a key-migration of every open finding (rehash + event rows); the planner gets a `checkpoint:decision` before the task that fixes the recipe in code.
- **D-02 [owner]: No edits to the four check-emission functions** in `audit_billing_changes.py` to satisfy the key. A new mapping (check_id → identity-field list) in the owning `billing_audit/` or `pipeline_memory/` module derives the key from the existing finding dicts + the source row. Adding a new check type in future MUST add a recipe entry (planner: make the mapping exhaustive and tested so an unknown check_id fails loudly in tests, never silently in production).

**Check scope and severity (spec §8 #6b — owner decision 2026-09-11)**
- **D-03 [owner]: Three WR-scoped checks are memory-backed:** `price_variance_anomaly`, `data_consistency_issue`, `rate_sanity_mismatch`. `recent_discussion` (sheet-level, no `(wr, week_ending)`) keeps today's run-only behavior untouched and is NOT persisted.
- **D-04 [owner]: `audit_finding.severity` = the check's own emitted `low|medium|high`.** Never derived from, and never feeding back into, the run-level `_risk_level_for` ladder (a count rollup with price-variance excluded by default). Any rolled-up risk indicator for the SQL views is computed at query time over open + resurfaced findings; the existing `summary.risk_level` behavior and its Sentry/log output are unchanged.

**Acknowledge / suppress authority (spec §8 #6c — owner decision 2026-09-11)**
- **D-05 [owner]: Owner-only via direct SQL with the service-role, v1.** Juan sets `acknowledged` / `suppressed` (`acknowledged_by`, `acknowledged_at`) by SQL; every manual transition is recorded as an `audit_finding_event` row (planner: provide a small SQL helper function `pipeline_memory.acknowledge_finding(finding_key, actor, transition, note)` so the event row is never forgotten — still service-role only). No new RLS policy, no portal page, no workflow input, no Smartsheet sheet in Phase 13. — **Reversibility:** reversible — later surfaces (workflow_dispatch input, portal page) are additive on top.

**`wr_week_ownership` placement (D-12-A carry-forward — owner decision 2026-09-11)**
- **D-06 [owner]: Dropped for good.** OWN-01 is satisfied by the `resolve_claimer` ladder over `billing_audit.attribution_snapshot` plus the `backfill_source` / `backfill_run_id` provenance columns (validated live 2026-09-05). No `wr_week_ownership` table, view, or `last_known_before_week` rung will be built. Phase 13 records this as **D-13-A** in the docs only: spec §5 note, `REQUIREMENTS.md` OWN-01/OWN-02 re-scope notes, `ROADMAP.md` D-12-A line ("deferred to Phase 13" → "dropped, D-13-A"), and the reserved-name comment in `pipeline_memory/schema.sql`. No code, no schema. — **Reversibility:** reversible — a future consumer can add a derived read-only view in its own phase.

**Audit surface (AUD-03 — owner decision 2026-09-11)**
- **D-07 [owner]: SQL views now; visual surface is a tracked follow-up.** Phase 13 ships `pipeline_memory.open_findings` (status IN ('open','resurfaced'), ordered by severity / last_seen_run) and `pipeline_memory.finding_history_by_wr` (every finding + its events per WR). The Excel workbook / portal-v2 page / audit-sheet summary row is NOT built in Phase 13; the planner adds a ROADMAP backlog entry ("AUD-03 visual surface — decide after observing real finding volume") so the requirement's second half is not silently dropped. `_log_to_audit_sheet` stays a placeholder (D-07). — **Reversibility:** reversible.

**Lifecycle and run semantics (from spec §6, clarified for the planner)**
- **D-08 [spec]: Transitions.** New key → `open` (+ event `opened`). Seen again → bump `last_seen_run` (+ event `seen`); if status was `acknowledged` → `resurfaced` (+ event `resurfaced`). An `open` or `resurfaced` finding whose group WAS re-audited this run and was not produced → `fixed`, `fixed_run = run_id` (+ event `fixed`). Findings whose group was NOT re-audited are untouched. `suppressed` and `fixed` findings seen again: `fixed` → `open` again (event `reopened`, `fixed_run` cleared); `suppressed` never changes status and never surfaces (last_seen_run still bumps) — see Claude's discretion.
- **D-09 [carried, Phase 10/11]: Rollout = shadow-first, default-OFF, fail-open.** New env flag `AUDIT_MEMORY_ENABLED` (default `0`), the direct analog of `RUN_MEMORY_WRITE_ENABLED`; every Supabase call goes through the existing `with_retry(op=...)` + per-op circuit breaker pattern; any failure logs + Sentry breadcrumb and the run continues with today's audit output. Never block billing on audit memory.
- **D-10 [carried, Phase 11]: "Re-audited group" = the set of `(wr, week_ending)` pairs whose rows were in this run's audited row set.** With `RUN_MEMORY_INCREMENTAL_ENABLED=0` (today) the audit sees `all_rows`, so every group present is re-audited; when incremental read is on, the audit input is rows for the Phase 11 affected set ∪ rows for the groups of all `open`/`resurfaced` findings. The weekly deep run (`mode='full'`) re-audits everything. `run_ledger.mode` / `run_id` are the provenance for `first_seen_run` / `last_seen_run` / `fixed_run`.
- **D-11 [carried]: Schema lives in `pipeline_memory`** (spec §8 #2), service-role only, reapply-safe DDL appended to `pipeline_memory/schema.sql` (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE FUNCTION`). Applying DDL to the live project is a protected-area step Juan performs (Supabase connector) after the PR is reviewed — the plan carries a `checkpoint:human-verify` there, exactly like Phase 10/12.

### Claude's Discretion
- **D-CD-01:** How `price_variance_anomaly` maps to a week: the check pools Units Total Price per WR across rows. Researcher verifies whether the pool spans weeks; if it does, the key's `week_ending` is the pooled rows' week when unique, else NULL with the finding treated as re-audited whenever ANY affected pair for that WR is re-audited. Document the choice in RESEARCH.md / the plan. **(Resolved by this research — see Summary point 1 and Pitfall 1: the pool has NO week-scoping at all, so it routinely spans weeks; the NULL-when-not-unique path is expected to be exercised regularly, not an edge case.)**
- **D-CD-02:** `data_consistency_issue` identity uses the sorted set of issue codes (stable strings from `row_issues`, e.g. `invalid_quantity_format`) rather than `row_index`. If the researcher finds the issue strings are not stable, fall back to `wr | week_ending` only. **(Resolved by this research — see Summary point 2 and Pitfall 2: the strings are stable literal English sentences, NOT slug-style codes like the example — the fallback does not trigger, but the exact wording is now load-bearing for identity and must be pinned by test.)**
- **D-CD-03:** Server-side vs client-side transitions: prefer one RPC (`pipeline_memory.upsert_audit_findings(p_run_id, p_findings jsonb, p_reaudited_pairs jsonb)`) that applies D-08 atomically in SQL, mirroring `upsert_rows_bulk`; client-side only if the RPC proves awkward to test.
- **D-CD-04:** `suppressed` semantics as stated in D-08 (terminal-hidden, still tracks `last_seen_run`).
- **D-CD-05:** Retention: no purge in Phase 13; `audit_finding_event` growth is bounded by finding volume (measure in shadow before deciding).

### Deferred Ideas (OUT OF SCOPE)
- **AUD-03 visual surface** (generated audit workbook in `generated_docs/`, read-only portal-v2 page with an RLS policy, or the `_log_to_audit_sheet` summary row) — decide after observing real finding volume; ROADMAP backlog item created by the planner.
- **`workflow_dispatch` acknowledge input** (`advanced_options` key `ack_finding_keys:`) — v1.1 add-on once SQL-only acknowledgement is trusted; GitHub Actions change needs owner approval.
- **portal-v2 acknowledge page** with a role model — future phase, after the read-only surface.
- **`recent_discussion` findings in memory** — only if a `fixed` rule is defined for sheet-level discussions.
- **`wr_week_ownership` derived view** — only if a concrete consumer appears (own phase).
- **`pipeline_memory/client.py` breaker lock** — mirror `_breaker_lock` from PR #407; separate small PR, not Phase 13.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUD-01 | `audit_finding` / `audit_finding_event` persist every finding with a stable key and lifecycle open → fixed \| resurfaced \| acknowledged \| suppressed. | Pattern 1 (RPC template) + Pattern 2 (fail-open writer) + Code Examples (verified emitted-field shapes per check) + Pitfalls 1-4 (key-derivation gaps resolved) give the concrete key-derivation and write-path design; `pipeline_memory/schema.sql`'s existing five-table precedent is the DDL template. |
| AUD-02 | Each audit run evaluates only affected groups + open findings; findings not reproduced on a re-audited group transition to `fixed` with the fixing run id. | Pattern 4 (chunked reads) + Pitfall 5 (per-check "was this check run this run" nuance) + System Architecture Diagram give the re-audited-pairs computation shape, reusing Phase 11's affected-set and `run_ledger.mode`/`run_id` provenance (D-10). |
| AUD-03 | Excel/portal audit surfaces open + resurfaced findings only; history is queryable per WR. | D-07 (locked, deferred visual surface) means Phase 13 only needs the two SQL views (`open_findings`, `finding_history_by_wr`); Validation Architecture section documents the manual SQL-editor verification path in lieu of an automated test (no precedent exists in this repo for automated live-view testing). |
</phase_requirements>

## Summary

Phase 13 adds a second `pipeline_memory`-schema feature (`audit_finding` / `audit_finding_event`) that turns the three WR-scoped audit checks in `audit_billing_changes.py` into a task-list-like memory: a finding is created once, survives runs where it keeps reproducing, and is marked `fixed` the first time a re-audited group stops reproducing it. This mirrors the Phase 10 `pipeline_memory` shadow-write architecture almost exactly — same schema, same service-role-only RLS, same `with_retry(op=)` + per-op circuit-breaker pattern, same default-OFF env-flag convention, same reapply-safe DDL discipline — so the *infrastructure* risk is low. The *design* risk is concentrated entirely in D-01's finding-key contract, because none of the three check-emission functions were written with a durable identity key in mind, and this research confirms two consequential gaps CONTEXT.md's decisions already anticipated and partially resolved (D-CD-01, D-CD-02):

1. `_detect_price_anomalies` (`price_variance_anomaly`) pools `Units Total Price` **per Work Request # only** — there is no week-scoping anywhere in the function. It is called once per run with `all_rows` (pipeline/orchestrate.py:2910), which is not week-scoped either. This means a WR's price pool routinely spans multiple `week_ending` values within a single run, exactly the ambiguity D-CD-01 anticipated. The emitted finding dict carries no `week_ending`, `cu`, or row reference at all — only `work_request`, `price_range`, `average_price`, `variance_percentage`, `severity`, `description`.
2. `_validate_data_consistency` (`data_consistency_issue`) emits a `row_index` (position in the `rows` list passed to `audit_financial_data`) plus a list of **literal English sentence strings** (`"Missing Work Request #"`, `"Invalid quantity format"`, etc.) — not slug-style codes like the CONTEXT.md example `invalid_quantity_format`. They ARE deterministic/stable (fixed string literals in code), so D-CD-02's "not stable → fall back to `wr | week_ending`" branch does NOT trigger — but the plan must be explicit that these exact sentence strings become part of a durable hash key, so any future *wording* edit to this function (even a typo fix) will silently orphan every open `data_consistency_issue` finding. `row_index` is a single-source-row pointer, so `week_ending` join is unambiguous here (unlike price_variance_anomaly).
3. `_detect_rate_sanity_mismatches` (`rate_sanity_mismatch`) matches D-01's assumed shape almost exactly: it emits `work_request`, `cu`, `work_type` per finding — all three of D-01's declared identity fields are real, already-emitted fields. But it too carries no row reference, so if two in-scope rows in the same run share `(wr, cu, work_type)` **and** the same `week_ending`, their findings collapse to one key (an accepted, D-01-endorsed limitation, not a bug to fix).

**Primary recommendation:** Build a single new module (e.g. `pipeline_memory/audit_findings.py`, mirroring the `writer.py`/`reader.py` split) that (a) computes `finding_key` server's-eye-view by joining each emitted finding dict back to its `week_ending` via the *same* `row.get('Weekly Reference Logged Date')` + `pipeline.utils.excel_serial_to_date(...)` pattern already used at `pipeline/orchestrate.py:784-785`, (b) ships one `pipeline_memory.upsert_audit_findings(p_run_id, p_findings jsonb, p_reaudited_pairs jsonb)` RPC that applies D-08's transition table atomically in SQL (mirroring `upsert_rows_bulk`'s `jsonb_to_recordset` + `SET search_path = ''` pattern), and (c) wraps every call in `with_retry(op="audit_finding_upsert")` behind a new `AUDIT_MEMORY_ENABLED` flag using the exact `os.getenv(...).strip().lower() in ('1','true','yes','on')` idiom already used for `RUN_MEMORY_WRITE_ENABLED` / `RUN_MEMORY_INCREMENTAL_ENABLED`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Finding key derivation (check dict → identity fields + week_ending) | API/Backend (Python, `pipeline_memory/` new module) | — | Pure data-shaping over existing `audit_results` + `all_rows`; no I/O |
| Finding lifecycle transitions (open/fixed/resurfaced/acknowledged/suppressed) | Database/Storage (Supabase RPC, SQL) | API/Backend (Python caller) | D-CD-03 prefers one atomic server-side RPC mirroring `upsert_rows_bulk`; Python only shapes jsonb in and logs the summary out |
| Acknowledge/suppress transitions | Database/Storage (SQL helper function, service-role) | — | D-05: owner-only via direct SQL; no portal/RLS/workflow surface in Phase 13 |
| Open + history read surface | Database/Storage (SQL views `open_findings`, `finding_history_by_wr`) | — | D-07: SQL views now, no Excel/portal visual surface this phase |
| Resilience (fail-open on Supabase outage) | API/Backend (`billing_audit.client`-style breaker, reused pattern) | — | D-09: every Supabase call goes through `with_retry(op=)` + per-op breaker; audit output must be unaffected by memory outages |
| Kill switch / rollout gating | API/Backend (`pipeline/config.py` env flag) | — | D-09: `AUDIT_MEMORY_ENABLED` default `0`, direct analog of `RUN_MEMORY_WRITE_ENABLED` |

## Standard Stack

This phase adds **no new external dependencies**. It extends the existing production stack:

### Core (existing, reused)
| Library | Version (verified in repo) | Purpose | Why reused |
|---------|---------|---------|--------------|
| `supabase-py` client (via `billing_audit/client.py` / `pipeline_memory/client.py` pattern) | already pinned in `requirements.txt` (not re-verified here — unchanged by this phase) | Supabase REST/RPC calls | Same client construction pattern (`get_client()`, `with_retry`) as Phase 10-12; no new client needed |
| PostgreSQL / Supabase (`pipeline_memory` schema) | live project `poeyztlmsawfoqlanucc` (per `.planning/STATE.md` Infrastructure Topology note) | Durable finding storage | Same schema namespace as `sheet_registry`/`row_state`/`row_event`/`group_state`/`run_ledger` |

**Package Legitimacy Audit:** Not applicable — Phase 13 installs no new packages. `requirements.txt` is untouched.

**Installation:** None required.

## Architecture Patterns

### System Architecture Diagram

```
Smartsheet rows (all_rows, this run)
        │
        ▼
audit_billing_changes.py :: BillingAudit.audit_financial_data(source_sheets, all_rows)
  ├─ _detect_price_anomalies(all_rows)          → [price_variance_anomaly, ...]   (UNCHANGED, D-02)
  ├─ _validate_data_consistency(all_rows)        → [data_consistency_issue, ...]   (UNCHANGED, D-02)
  ├─ _detect_rate_sanity_mismatches(all_rows,…)  → [rate_sanity_mismatch, ...]     (UNCHANGED, D-02)
  └─ _detect_suspicious_changes(source_sheets)   → [recent_discussion, ...]        (NOT persisted, D-03)
        │  audit_results dict (returned, no memory writes inside this class)
        ▼
pipeline/orchestrate.py  (after existing audit_financial_data(...) call, ~line 2910)
        │
        ▼
NEW: pipeline_memory/audit_findings.py :: build_finding_payloads(audit_results, all_rows, run_id)
  - joins each finding dict back to source row(s) via wr (+row_index for
    data_consistency_issue, +cu/work_type for rate_sanity_mismatch, +WR-wide
    row set for price_variance_anomaly) to resolve week_ending
    (row.get('Weekly Reference Logged Date') → pipeline.utils.excel_serial_to_date)
  - computes finding_key = sha256(check_id|...identity fields...|week_ending)
  - computes re-audited (wr, week_ending) pairs from this run's affected/full set (D-10)
        │  p_findings jsonb, p_reaudited_pairs jsonb
        ▼
AUDIT_MEMORY_ENABLED flag gate → with_retry(op="audit_finding_upsert")
        │
        ▼
Supabase RPC: pipeline_memory.upsert_audit_findings(p_run_id, p_findings, p_reaudited_pairs)
  - applies D-08 transition table atomically:
      new key            → open (+event opened)
      seen again         → bump last_seen_run (+event seen); acknowledged→resurfaced
      open/resurfaced,
        group re-audited,
        not reproduced   → fixed, fixed_run=run_id (+event fixed)
      fixed seen again   → open again (+event reopened, fixed_run cleared)
      suppressed         → never changes status, last_seen_run still bumps
        │
        ▼
pipeline_memory.audit_finding / audit_finding_event  (Supabase tables)
        │
        ▼
pipeline_memory.open_findings / finding_history_by_wr  (SQL views, read via SQL editor — no Excel/portal surface, D-07)
```

### Recommended Project Structure
```
pipeline_memory/
├── audit_findings.py   # NEW — key derivation, week_ending join, RPC call wrapper
├── schema.sql           # append new CREATE TABLE / CREATE OR REPLACE FUNCTION / views (reapply-safe)
├── writer.py             # UNCHANGED except WR-04 hygiene follow-up (sheets_changed)
├── reader.py             # UNCHANGED (existing chunked-read pattern is the template, not touched)
└── client.py              # UNCHANGED — reuse get_client() / with_retry()

pipeline/
├── config.py             # add AUDIT_MEMORY_ENABLED flag (same block style as RUN_MEMORY_* flags)
└── orchestrate.py        # add one hook call right after the existing audit_financial_data(...) call (~line 2910)

audit_billing_changes.py  # UNTOUCHED (D-02) — no edits to the four check-emission functions
```

### Pattern 1: Server-side atomic upsert RPC (mirror `upsert_rows_bulk`)
**What:** One `jsonb_to_recordset`-typed RPC that receives all of a run's findings plus the re-audited-pairs set, and performs the entire D-08 transition table inside one `plpgsql` function, `SET search_path = ''`, `VOLATILE`.
**When to use:** Every audit-memory write this run, chunked if the row count ever approaches PostgREST's ~1MB body limit (unlikely for findings — orders of magnitude fewer than `row_state` rows).
**Example (the exact template to copy, verified in this repo):**
```sql
-- Source: pipeline_memory/schema.sql:316-337 (upsert_rows_bulk, verified)
CREATE OR REPLACE FUNCTION pipeline_memory.upsert_rows_bulk(
    p_sheet_id BIGINT,
    p_run_id   TEXT,
    p_rows     JSONB
)
RETURNS TABLE (wr TEXT, week_ending DATE)
LANGUAGE plpgsql
VOLATILE
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    WITH incoming AS (
        SELECT
            q.row_id, q.wr, q.week_ending, q.snapshot_date, q.cu, q.pole,
            q.work_type, q.quantity, q.units_total_price, q.units_completed,
            q.foreman_observed, q.helper_observed, q.helper_completed,
            q.helper_dept, q.helper_job, q.vac_crew_observed,
            q.helper2_observed, q.helper2_completed, q.helper2_dept, q.helper2_job,
            q.vac_completed, q.row_modified_at, q.content_hash
        FROM jsonb_to_recordset(p_rows) AS q(
            row_id             BIGINT,
            ...
        )
    )
    ...
END;
$$;
```
`pipeline_memory.upsert_audit_findings(p_run_id, p_findings jsonb, p_reaudited_pairs jsonb)` (D-CD-03) should follow this exact shape: typed `jsonb_to_recordset`, `SET search_path = ''`, `VOLATILE`, one CTE per input array, `RETURN QUERY` with a summary row (opened/seen/fixed/resurfaced counts) for the Python caller to log.

### Pattern 2: Python-side fail-open, never-raises write wrapper
**What:** Every write function checks `client is None` → return, checks the flag function → return, builds payload, calls `with_retry(_invoke, op="...")`, bumps a counter on `None` result, never raises.
**When to use:** The new `audit_findings.py` module's single write entrypoint (called once per run after `audit_financial_data`).
**Example:**
```python
# Source: pipeline_memory/writer.py:157-194 (run_ledger_start, verified — exact pattern to copy)
def run_ledger_start(run_id: str, mode: str,
                      release: str | None = None) -> None:
    client = get_client()
    if client is None:
        return
    if not _client_write_enabled():
        return

    payload = {
        "run_id": run_id,
        "mode": mode,
        "started_at": _utcnow_iso(),
        "release": release or "",
        "status": "running",
    }

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("run_ledger")
            .upsert(payload, on_conflict="run_id")
            .execute()
        )

    result = with_retry(_invoke, op="run_ledger_upsert")
    if result is None:
        _bump_counter("run_ledger_errored")
        return
    _bump_counter("run_ledger_written")
```

### Pattern 3: Per-op circuit breaker with owner-decided half-open close
**What:** Every Supabase call site passes a distinct `op` string; a breaker tracked per-op trips after N consecutive failures; `close_circuit(op, observed_generation=...)` lets a caller that independently proved the endpoint is healthy close a stale breaker — all breaker-state mutation happens under one lock (`_breaker_lock`), the PR #407 lesson this repo just fixed.
**When to use:** The new `audit_finding_upsert` op must get its OWN op string (never share `run_ledger_upsert` or any `pipeline_memory` op) so an audit-memory outage cannot mask, or be masked by, an unrelated `pipeline_memory` outage.
**Example (verified, `billing_audit/client.py:646-720`):**
```python
def with_retry(fn: Callable[..., Any], *args: Any,
               op: str = "default", **kwargs: Any) -> Any:
    if _global_disable_reason is not None:
        return None
    with _breaker_lock:
        circuit_open = op in _open_circuits
    if circuit_open:
        return None
    # ... 4 attempts, exponential backoff, breaker trips on N consecutive failures
```
Note (D-11 / canonical refs): `billing_audit.client.py`'s breaker has the lock fix from PR #407; **`pipeline_memory/client.py`'s breaker does NOT yet have it** — that is an explicitly separate, already-tracked follow-up PR (not Phase 13 scope). Confirm which client module Phase 13's new writer calls into (`pipeline_memory.client`, per D-11 "Schema lives in `pipeline_memory`") and do not assume it inherits the lock fix.

### Pattern 4: Chunked, injection-safe reads with the empty-input/empty-result distinction
**What:** `map_affected_to_sheets`-style reads chunk at a fixed constant (`_MAPPING_CHUNK_SIZE = 500` in `reader.py`, `_CHUNK_ROWS = 500` in `writer.py`) and explicitly distinguish "no input given" from "input given, zero rows returned."
**When to use:** Reading `open`/`resurfaced` findings scoped to this run's affected WRs (D-CD-03's incremental path — only affected groups + open findings are evaluated, per AUD-02).
**Example (verified, `pipeline_memory/reader.py:356-357`):**
```python
wrs[i:i + _MAPPING_CHUNK_SIZE]
for i in range(0, len(wrs), _MAPPING_CHUNK_SIZE)
```

### Anti-Patterns to Avoid
- **Editing the four check-emission functions to add `week_ending`/stable codes:** D-02 explicitly forbids this. All key-derivation logic lives in the new mapping module, reading `audit_results` + `all_rows` — never inside `audit_billing_changes.py`.
- **Trusting `row_index` for `price_variance_anomaly` or `rate_sanity_mismatch`:** neither emits a row index; only `data_consistency_issue` does. Do not write a generic "look up `rows[row_index]`" helper and apply it to all three checks.
- **Sharing a Supabase `op` string across `pipeline_memory` writers:** breaks per-endpoint breaker isolation (see `billing_audit/client.py`'s documented rule that SELECT/UPSERT sides of one endpoint must never share an op).
- **Treating `RATE_SANITY_AUDIT_ENABLED=false` as impossible:** it is a real, already-shipped kill switch (`audit_billing_changes.py:560`) that makes `_detect_rate_sanity_mismatches` return `[]` for the whole run. The finding-key mapping must tolerate an empty list from any of the three checks in any run without treating it as "everything just got fixed" — it must still distinguish "check ran and found nothing" from "check didn't run" for the D-08 fixed-transition logic (only groups that WERE re-audited should transition existing open findings to `fixed`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic multi-row upsert with per-row diff/transition logic | A Python loop that reads-then-writes each finding row | One `jsonb_to_recordset` RPC (`upsert_audit_findings`), mirroring `upsert_rows_bulk` | Server-side atomicity avoids read-then-write races across concurrent/retried calls; matches the existing `upsert_rows_bulk` precedent exactly |
| Circuit breaker / retry logic | A new bespoke retry wrapper for audit-memory calls | `billing_audit.client.with_retry(op=...)` or the `pipeline_memory.client` equivalent, with a dedicated `op` | Already handles transient-error classification, exponential backoff, and per-op breaker isolation; a second implementation risks diverging semantics |
| Env-flag rollout gate | A custom feature-flag table or config format | `os.getenv('AUDIT_MEMORY_ENABLED', '0').strip().lower() in ('1','true','yes','on')` — same idiom as `RUN_MEMORY_WRITE_ENABLED` / `RUN_MEMORY_INCREMENTAL_ENABLED` (`pipeline/config.py:494-529`) | Consistency lets operators reason about all memory-write flags with one mental model; a differently-shaped flag is a footgun for the next incident responder |
| SQL helper for owner-only manual transitions | A raw multi-statement UPDATE run ad hoc from the SQL editor | `pipeline_memory.acknowledge_finding(finding_key, actor, transition, note)` (D-05) | Guarantees the `audit_finding_event` row is never forgotten on a manual transition; matches the "every transition is an event" invariant D-08 establishes for automated transitions |

**Key insight:** Every piece of "hard" infrastructure this phase needs (bulk upsert RPC shape, breaker, chunked reads, fail-open write wrapper, env-flag convention) already has a working, tested implementation in this repo from Phase 10-12. The actual net-new engineering is narrow: the finding-key derivation function and the D-08 transition SQL. Resist the temptation to generalize or refactor the existing `pipeline_memory` helpers while adding this — D-02's "no edits to the check functions" spirit extends to "don't touch working `pipeline_memory` infrastructure either" unless a plan task explicitly requires it (e.g., the folded WR-04 hygiene task).

## Common Pitfalls

### Pitfall 1: `price_variance_anomaly`'s WR-wide, week-agnostic pooling breaks the naive key assumption
**What goes wrong:** Assuming `_detect_price_anomalies` findings map 1:1 to a single `(wr, week_ending)` the way the other two checks roughly do. They don't — the function pools every row for a WR across the entire `all_rows` list handed to `audit_financial_data`, with zero week filtering.
**Why it happens:** `all_rows` (the argument at `pipeline/orchestrate.py:2910`) is whatever set of rows this run is auditing — under `RUN_MEMORY_INCREMENTAL_ENABLED=0` (today, per D-10) that's every row in every source sheet, spanning many weeks; under incremental mode it's the Phase 11 affected set ∪ open-finding groups, which can also span multiple weeks for the same WR.
**How to avoid:** Implement D-CD-01 exactly as CONTEXT.md specifies: at persist time, collect the distinct `week_ending` values of the rows that contributed to a given WR's price pool (via `row.get('Weekly Reference Logged Date')` → `excel_serial_to_date`); if exactly one distinct value exists, use it; otherwise store `week_ending = NULL` for that finding and treat it as "re-audited" whenever ANY `(wr, week_ending)` pair for that WR appears in this run's re-audited-pairs set.
**Warning signs:** A `price_variance_anomaly` finding that never transitions to `fixed` even after the anomalous pricing is corrected (because the "re-audited" join was scoped too narrowly to a single week that never matches), or a finding that flaps open/fixed every run because week_ending resolution is nondeterministic across runs with different affected-row sets.

### Pitfall 2: `data_consistency_issue`'s identity strings are prose, not codes — wording changes are a silent key-migration event
**What goes wrong:** `row_issues` entries are literal strings (`"Missing Work Request #"`, `"Negative price detected"`, `"Invalid price format"`, `"Zero or negative quantity"`, `"Invalid quantity format"`, or `f"Missing {field}"` for each of `['Work Request #', 'Units Total Price', 'Quantity', 'CU']`) — 8 distinct possible literals total, verified at `audit_billing_changes.py:487-509`. If a future PR "cleans up" one of these messages (e.g. `"Invalid quantity format"` → `"Quantity format invalid"`), every open finding keyed on the old string is silently orphaned (a new key is created, the old one never transitions to `fixed` because it's simply never seen again).
**Why it happens:** D-01 explicitly keys on "the identity fields the check ALREADY emits" — for this check, that's the `issues` list itself (per D-CD-02, `sorted(issue codes)`), so the message text IS the identity data, by design.
**How to avoid:** Document this coupling loudly in the plan (a comment at both the finding-key mapping AND at the top of `_validate_data_consistency` itself, even though D-02 forbids *behavior* edits — a comment-only addition noting "these string literals are load-bearing for audit-memory identity, see finding-key mapping" is not a behavior change and should be in scope). Add a test that pins the exact 8 literal strings so a future rewording is caught by CI before it silently orphans findings in production.
**Warning signs:** An open `data_consistency_issue` finding that never transitions to `fixed` despite the underlying data problem being resolved, immediately after a PR that touched `_validate_data_consistency`'s message text.

### Pitfall 3: Row-level ambiguity for `rate_sanity_mismatch` (accepted, but must be documented)
**What goes wrong:** Two in-scope rows sharing the exact same `(wr, cu, work_type, week_ending)` produce two separate finding dicts from `_detect_rate_sanity_mismatches`, but they hash to the SAME `finding_key` (D-01 deliberately excludes row/`row_id` from the key). The second finding silently collapses into the first (bumps `last_seen_run`, does not create a second finding).
**Why it happens:** D-01 is explicit that Smartsheet `row_id` is never part of the key ("Evidence values ... and Smartsheet `row_id` are NEVER part of the key"), and the check itself has no natural per-finding row disambiguator beyond `(wr, cu, work_type)`.
**How to avoid:** This is an accepted design tradeoff, not a bug to fix in Phase 13. Document it as a known limitation in the plan and in a code comment at the finding-key mapping function, so a future incident investigator doesn't waste time thinking memory dropped a finding.
**Warning signs:** Fewer `audit_finding` rows than `rate_sanity_mismatch` dicts in a given run's `audit_results` — expected and benign, but worth a one-line log-count sanity check (e.g., "N mismatches emitted this run, M distinct keys") so a large N-M gap gets noticed if it ever grows unexpectedly.

### Pitfall 4: `_detect_suspicious_changes` (`recent_discussion`) has no `(wr, week_ending)` at all
**What goes wrong:** Building the finding-key mapping generically over "every dict in `audit_results`" would try to key `recent_discussion` findings (which carry `sheet_id`, `sheet_name`, `discussion_id` — no `work_request`, no `week_ending`) and either crash or silently produce garbage keys.
**Why it happens:** `_detect_suspicious_changes` operates over `source_sheets`, not rows, and is explicitly out of scope for memory persistence per D-03.
**How to avoid:** The finding-key mapping function must explicitly whitelist the three check `type` values it processes (`price_variance_anomaly`, `data_consistency_issue`, `rate_sanity_mismatch`) and pass through anything else (notably `recent_discussion`) completely untouched, exactly as it flows to `_log_to_audit_sheet` today (still a placeholder, D-07).
**Warning signs:** A test that feeds a synthetic `recent_discussion` finding into the mapping function and expects it to be silently skipped, not raise.

### Pitfall 5: `SKIP_CELL_HISTORY` / `skip_cell_history` gating means `_detect_suspicious_changes` sometimes doesn't run at all — irrelevant to memory, but a good template for reading D-08's "group re-audited" semantics correctly
**What goes wrong:** None directly for Phase 13 (this check is not persisted), but the pattern of "a check that sometimes doesn't run this run" is exactly the shape D-10 already solves for re-audited-group computation — a naive implementation might assume all three memory-backed checks always run together.
**Why it happens:** `RATE_SANITY_AUDIT_ENABLED` (env, default `"true"`, checked at `audit_billing_changes.py:560`) can independently disable `_detect_rate_sanity_mismatches` for an entire run while `_detect_price_anomalies` and `_validate_data_consistency` still run normally.
**How to avoid:** The "group WAS re-audited this run" computation (D-10) must be understood PER-CHECK, not per-run: if `RATE_SANITY_AUDIT_ENABLED=false` for a run, no `rate_sanity_mismatch` finding should transition to `fixed` in that run even for groups that WERE re-audited by the other two checks, because the rate-sanity check simply didn't execute.
**Warning signs:** A flood of `rate_sanity_mismatch` findings transitioning to `fixed` immediately after someone temporarily sets `RATE_SANITY_AUDIT_ENABLED=false` for an unrelated diagnostic run, then `open`/`reopened` again the next run.

## Code Examples

### Deriving week_ending from a source row (the exact existing pattern to reuse)
```python
# Source: pipeline/orchestrate.py:784-785 (verified — the established
# pattern for resolving week_ending from a raw Smartsheet row)
row['__mem_week_ending'] = _utils.excel_serial_to_date(
    row.get('Weekly Reference Logged Date')
)
```

### Env-flag convention to mirror for AUDIT_MEMORY_ENABLED
```python
# Source: pipeline/config.py:494-496 and 527-529 (verified — the exact
# idiom both RUN_MEMORY_WRITE_ENABLED and RUN_MEMORY_INCREMENTAL_ENABLED
# use; AUDIT_MEMORY_ENABLED should follow this literally, per D-09)
RUN_MEMORY_WRITE_ENABLED = os.getenv(
    'RUN_MEMORY_WRITE_ENABLED', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
```

### The three memory-backed checks' actual emitted-field shapes (verified, `audit_billing_changes.py`)
```python
# price_variance_anomaly — audit_billing_changes.py:464-472
{
    "type": "price_variance_anomaly",
    "work_request": wr_num,
    "price_range": price_range,
    "average_price": avg_price,
    "variance_percentage": (price_range / avg_price) * 100,
    "severity": "medium",              # ALWAYS "medium" — never varies
    "description": f"High price variance detected in WR# {wr_num}"
}
# NO week_ending, NO cu, NO row reference of any kind.

# data_consistency_issue — audit_billing_changes.py:511-518
{
    "type": "data_consistency_issue",
    "row_index": i,                     # position in `rows` — do NOT use in the key (D-01)
    "work_request": row.get('Work Request #', 'Unknown'),
    "issues": row_issues,               # list of literal strings, see Pitfall 2
    "severity": "low" if len(row_issues) == 1 else "medium"
}
# row_index gives an UNAMBIGUOUS single source row → week_ending join is safe here.

# rate_sanity_mismatch — audit_billing_changes.py:613-627
{
    "type": "rate_sanity_mismatch",
    "work_request": wr,
    "cu": cu,
    "work_type": work_type,
    "quantity": qty,
    "expected_price": round(expected, 2),
    "actual_price": round(actual, 2),
    "delta": round(actual - expected, 2),
    "severity": "high",                 # ALWAYS "high" — never varies
    "description": "..."
}
# NO week_ending, NO row reference — wr+cu+work_type match against `rows`
# (or the same in-scope filter) needed to resolve week_ending; see Pitfall 3
# for the residual ambiguity this leaves.
```

## State of the Art

| Old Approach (spec draft) | Current Approach (this research + D-01..D-11) | When Changed | Impact |
|--------------------------|------------------------------------------------|---------------|--------|
| `sha(check_id\|wr\|week\|cu\|pole)` uniform key template (design spec §3) | Per-check natural key built from each check's ACTUAL emitted fields (D-01), verified against code in this research | 2026-09-11 (D-01, this research) | The uniform template would have collapsed distinct `price_variance_anomaly` findings (no check emits `pole`) and produced a key with placeholder/empty segments for two of the three checks |
| `wr_week_ownership` table (design spec, D-12-A originally deferred to Phase 13) | Dropped for good (D-06/D-13-A) — `resolve_claimer` ladder over `attribution_snapshot` already satisfies OWN-01 | 2026-09-05 (validated live), 2026-09-11 (D-06 formalizes) | Phase 13 does zero work on this table; only a docs/reserved-name-comment cleanup in `schema.sql` |
| Excel/portal audit surface bundled with AUD-03 | SQL views only this phase (D-07); visual surface deferred to a ROADMAP backlog item pending observed finding volume | 2026-09-11 (D-07) | Phase 13's plan should NOT include Excel workbook, portal-v2 page, or `_log_to_audit_sheet` implementation tasks — only the backlog entry |

**Deprecated/outdated:**
- The design-spec draft's `sha(check_id|wr|week|cu|pole)` key template at `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md` §3 (lines ~125-138) is explicitly superseded by D-01 and should not be used as a reference for the actual key computation, only as historical context.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The audit-memory writer should call into `pipeline_memory/client.py`'s `get_client()`/`with_retry()` (D-11: "Schema lives in `pipeline_memory`"), NOT `billing_audit/client.py`'s — meaning it inherits `pipeline_memory/client.py`'s breaker WITHOUT the PR #407 lock fix. | Pattern 3 | If the plan instead reuses `billing_audit.client`, the breaker gets the lock fix "for free" but the schema/client pairing would then contradict D-11's explicit schema placement; if the plan correctly uses `pipeline_memory.client` per D-11, the lock-free breaker is a real (already-tracked, separately-owned) residual risk under concurrent access this phase does not fix. |
| A2 | `all_rows` passed to `audit_financial_data` at `pipeline/orchestrate.py:2910` can, in practice, contain rows spanning more than one `week_ending` for a single WR in both full and incremental modes — this research did not execute a live run to directly observe a multi-week pool for one WR, it infers this from the absence of any week-scoping code in `_detect_price_anomalies` combined with `all_rows`'s known multi-sheet/multi-week composition. | Pitfall 1 | If in practice `all_rows` per run is *usually* single-week per WR (e.g., because most WRs only have one active week's rows in a typical run), the D-CD-01 NULL-week_ending fallback path will be exercised far less often than this research implies — worth a one-run production log check (count distinct week_ending per WR in `all_rows`) before finalizing the mapping logic. |

## Open Questions

1. **Does `pipeline_memory/client.py` need its own dedicated breaker-lock fix before Phase 13 ships, or is the lock-free breaker an acceptable residual risk for the audit-finding write path specifically?**
   - What we know: `billing_audit/client.py`'s breaker has the PR #407 lock fix (verified); `pipeline_memory/client.py`'s does not (per CONTEXT.md canonical refs, not independently re-verified line-by-line in this research pass since it's declared explicitly out of scope).
   - What's unclear: Whether the audit-finding write path's concurrency profile (once per run, single-threaded call site at `pipeline/orchestrate.py`) makes the missing lock a non-issue in practice, versus a real risk if `run_ledger_start`/`upsert_rows_bulk`/`upsert_audit_findings` calls ever run concurrently on separate threads within one run.
   - Recommendation: Treat as out of scope per CONTEXT.md's explicit deferral ("separate small PR, not Phase 13"); the plan should not silently fix this as a "while I'm in the file" change.

2. **What is the actual observed multi-week-pool frequency for `price_variance_anomaly` in production `all_rows`?**
   - What we know: The code has no week-scoping; `all_rows` spans many sheets/weeks in full-read mode (today's default, D-10).
   - What's unclear: The real-world frequency of a single WR having rows from >1 distinct week in one run's `all_rows` — this determines how often the D-CD-01 NULL-week_ending path actually fires versus the clean single-week path.
   - Recommendation: The plan's Success Criterion 1 fixture-seed test should include both a single-week and a multi-week price-anomaly fixture to exercise both paths; a one-time production log-count check (as flagged in Assumption A2) would sharpen this further but is not blocking.

## Environment Availability

Skipped — this phase has no new external tool/service dependencies. The Supabase project, `pipeline_memory` schema, and Python client machinery already exist and are live (verified: `pipeline_memory/schema.sql`, `billing_audit/client.py`, `.planning/STATE.md` Infrastructure Topology note for project `poeyztlmsawfoqlanucc`).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, `tests/` directory) |
| Config file | none dedicated — `pytest tests/ -v` per CLAUDE.md Validation commands |
| Quick run command | `pytest tests/test_billing_audit_shadow.py -v` (existing fake-Supabase-client fixtures: `_make_fake_supabase_client`, `_fake_rpc_response`, verified present at `tests/test_billing_audit_shadow.py:136,148`) |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUD-01 | Finding created once, stable key, lifecycle transitions (open→fixed/resurfaced/acknowledged/suppressed) | unit (fake Supabase client) | `pytest tests/test_audit_findings.py -x` | ❌ Wave 0 — new test file, mirroring `tests/test_billing_audit_shadow.py`'s fixture pattern |
| AUD-01 | Finding-key derivation matches D-01 recipe per check type, including the price_variance_anomaly multi-week NULL path (D-CD-01) and the data_consistency_issue literal-string pin (Pitfall 2) | unit | `pytest tests/test_audit_findings.py -k key_derivation -x` | ❌ Wave 0 |
| AUD-02 | Only affected groups + open findings evaluated; a finding not reproduced on a re-audited group transitions to `fixed` with fixing run id | unit + fixture-seed integration (Success Criterion 1 shape) | `pytest tests/test_audit_findings.py -k lifecycle -x` | ❌ Wave 0 |
| AUD-03 | `open_findings` / `finding_history_by_wr` SQL views return status IN ('open','resurfaced') and full per-WR history respectively | manual SQL verification (SQL editor, post-DDL-apply) — no automated harness exists for live Supabase view content in this repo today | N/A (checkpoint:human-verify after DDL apply, per D-11) | ❌ Wave 0 — no existing precedent for automated SQL-view testing in this repo; matches the DDL-apply pattern already used for `pipeline_memory` in Phase 10 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_audit_findings.py -x` (or the closest new/modified test file)
- **Per wave merge:** `pytest tests/ -v` (full suite, 2333+ tests per Phase 14 closeout baseline)
- **Phase gate:** Full suite green before `/gsd:verify-work`; DDL apply + live read-back checkpoint (D-11) before declaring AUD-03 satisfied

### Wave 0 Gaps
- [ ] `tests/test_audit_findings.py` — new file, covers AUD-01/AUD-02 key derivation and lifecycle transitions against a fake Supabase client (mirror `_make_fake_supabase_client`/`_fake_rpc_response` from `tests/test_billing_audit_shadow.py`)
- [ ] No new shared fixtures needed — existing `tests/test_billing_audit_shadow.py` and Phase 10/11 shadow-test fixtures are directly reusable (per CONTEXT.md Reusable Assets)
- [ ] Framework install: none — pytest already installed and in use

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface — service-role-only, no portal/user-facing auth changes this phase |
| V3 Session Management | no | Not applicable — no session-based access added |
| V4 Access Control | yes | RLS restricted to `service_role` only (mirror `pipeline_memory`'s existing `DROP POLICY IF EXISTS service_role_all ... CREATE POLICY service_role_all ... USING (auth.role() = 'service_role')` pattern, verified present for the other five `pipeline_memory` tables at `schema.sql:587-604`); no `anon`/`authenticated` grants on `audit_finding`/`audit_finding_event` (mirror `REVOKE ALL ... FROM anon, authenticated` at `schema.sql:615-618`) |
| V5 Input Validation | yes | The `upsert_audit_findings` RPC must use explicit typed `jsonb_to_recordset(...)` column lists, never dynamic SQL and never trusting client-shaped jsonb structurally — exactly the existing T-10-03/ASVS-V5 discipline documented for `upsert_rows_bulk` at `schema.sql:276-282` |
| V6 Cryptography | yes (narrow) | `finding_key = sha256(...)` — use Postgres's built-in `digest(..., 'sha256')` (pgcrypto) or compute the hash in Python before sending it to the RPC; either is acceptable, but pick ONE side as authoritative so a key computed in Python always matches one computed in SQL, and pin that choice with a cross-language parity test (the exact `_HASH_PRUNE_VERSION`-style discipline already used elsewhere in this repo for hash-contract stability) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Dynamic SQL / structural trust of client-shaped jsonb in the new RPC | Tampering | Typed `jsonb_to_recordset(...)` column list only (mirror `upsert_rows_bulk`), never string-concatenated SQL |
| Mutable search_path privilege-escalation (the exact advisory finding already fixed on every `billing_audit`/`pipeline_memory` RPC) | Elevation of Privilege | `SET search_path = ''` on the new function, schema-qualify every object reference, per `schema.sql:278-280`'s documented precedent |
| Accidental `anon`/`authenticated` read access to billing-adjacent audit findings | Information Disclosure | Explicit `REVOKE ALL ... FROM anon, authenticated` + service-role-only RLS policy on both new tables, mirroring the existing five `pipeline_memory` tables exactly |
| Finding-key collision/orphaning from an uncoordinated wording change in a check-emission function (Pitfall 2) | Tampering (data integrity, not classic security) | Pin the exact literal-string set with a dedicated test; treat any change to those strings as requiring a documented key-migration task (D-01's own stated reversibility cost) |

## Sources

### Primary (HIGH confidence — direct Read of repo source this session)
- `audit_billing_changes.py:333-732` — `audit_financial_data`, all four check-emission functions, `_generate_audit_summary` — read in full this session
- `pipeline/orchestrate.py:2880-2934` — the audit call site (`audit_financial_data(source_sheets, all_rows)`) and its exception/Sentry handling — read in full
- `pipeline/orchestrate.py:784-785` — `__mem_week_ending` derivation pattern (`excel_serial_to_date(row.get('Weekly Reference Logged Date'))`) — read in full
- `pipeline_memory/schema.sql:1-49, 238-337, 615-676` — header comment (reserved names for Phase 13), `run_ledger` table, `upsert_rows_bulk` RPC, RLS/GRANT/REVOKE block, retention function — read in full
- `billing_audit/client.py:640-720` — `with_retry` docstring and body (breaker, per-op tracking, `_breaker_lock`) — read in full
- `pipeline/config.py:485-549` — `RUN_MEMORY_WRITE_ENABLED`, `RUN_MEMORY_INCREMENTAL_ENABLED` flag definitions and surrounding sub-budget constants — read in full
- `pipeline_memory/writer.py:157-266` — `run_ledger_start`, `run_ledger_finish`, `_RUN_LEDGER_FINISH_COLUMNS`, `streak_eligible_from_env` — read in full
- `pipeline_memory/reader.py`, `pipeline_memory/writer.py` (grep pass) — confirmed `_MAPPING_CHUNK_SIZE = 500` / `_CHUNK_ROWS = 500` chunking discipline
- `tests/test_billing_audit_shadow.py:136-165` — confirmed `_fake_rpc_response` / `_make_fake_supabase_client` fixture existence and shape
- `.planning/phases/13-audit-memory/13-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — required-reading context, read in full this session

### Secondary (MEDIUM confidence)
- None — this research relied entirely on direct source verification and the project's own locked CONTEXT.md decisions; no external web/docs lookups were needed since this phase extends an existing in-repo pattern rather than introducing a new external library.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all reused components verified present in repo
- Architecture: HIGH — every pattern cited (breaker, chunking, fail-open writer, RPC shape) verified by direct Read of the exact source lines this session
- Pitfalls: HIGH for the two orchestrator-flagged facts (pooling strategy, emitted-field shapes) — both fully resolved by reading `audit_billing_changes.py` directly; MEDIUM for the production frequency of the multi-week price-pool case (Assumption A2, not directly observed in a live run this session)

**Research date:** 2026-09-11
**Valid until:** 2026-10-11 (30 days — stable, in-repo pattern extension; re-verify sooner only if `audit_billing_changes.py`'s check-emission functions or `pipeline_memory/schema.sql`'s reserved-name header comment change before planning starts)
