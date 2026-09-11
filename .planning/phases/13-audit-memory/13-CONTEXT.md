# Phase 13: Audit Memory - Context

**Gathered:** 2026-09-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit findings produced by `audit_billing_changes.py` persist across runs like a task
list: created once, carried while unresolved, closed when the fixing run no longer
reproduces them. Phase 13 delivers (AUD-01) `pipeline_memory.audit_finding` /
`audit_finding_event` with a stable per-check finding key and the lifecycle
open → fixed | resurfaced | acknowledged | suppressed; (AUD-02) each audit run evaluates
only affected groups + open findings, and a finding not reproduced on a re-audited group
becomes `fixed` with the fixing run id; (AUD-03) open + resurfaced findings are exposed
through SQL views and per-WR history is queryable in SQL. The Excel/portal visual surface
is an explicit follow-up, not Phase 13 scope. Phase 13 also CLOSES decision D-12-A by
dropping the `wr_week_ownership` table for good (docs-only). Everything ships shadow-first,
default-OFF, fail-open, additive — the billing pipeline's behavior and outputs do not change.

</domain>

<decisions>
## Implementation Decisions

### Finding identity (spec §8 #6a — owner decision 2026-09-11)
- **D-01 [owner]: Per-check natural key.** `finding_key = sha256` of the canonical
  `|`-joined, normalized identity fields for that check: `check_id` + the identity fields the
  check ALREADY emits + `week_ending` joined from the source row at persist time. The spec's
  draft template `sha(check_id|wr|week|cu|pole)` is superseded: no check emits `week` or
  `pole` today, and uniform placeholders would collapse distinct findings. Evidence values
  (prices, deltas, variance %) and Smartsheet `row_id` are NEVER part of the key — they live
  in `evidence jsonb`. Identity recipe (a durable contract; changing it orphans open findings):
  - `rate_sanity_mismatch` → `check_id | wr | week_ending | cu | work_type`
  - `price_variance_anomaly` → `check_id | wr | week_ending` (see D-CD-01 for pooled weeks)
  - `data_consistency_issue` → `check_id | wr | week_ending | sorted(issue codes)` (D-CD-02)
  The identity columns (`check_id`, `wr`, `week_ending`, `cu`, …) are ALSO stored as plain
  columns so history is queryable without unhashing. — **Reversibility:** one-way — a
  recipe change later requires a key-migration of every open finding (rehash + event rows);
  the planner gets a `checkpoint:decision` before the task that fixes the recipe in code.
- **D-02 [owner]: No edits to the four check-emission functions** in
  `audit_billing_changes.py` to satisfy the key. A new mapping (check_id → identity-field
  list) in the owning `billing_audit/` or `pipeline_memory/` module derives the key from the
  existing finding dicts + the source row. Adding a new check type in future MUST add a recipe
  entry (planner: make the mapping exhaustive and tested so an unknown check_id fails loudly
  in tests, never silently in production).

### Check scope and severity (spec §8 #6b — owner decision 2026-09-11)
- **D-03 [owner]: Three WR-scoped checks are memory-backed:** `price_variance_anomaly`,
  `data_consistency_issue`, `rate_sanity_mismatch`. `recent_discussion` (sheet-level, no
  `(wr, week_ending)`) keeps today's run-only behavior untouched and is NOT persisted.
- **D-04 [owner]: `audit_finding.severity` = the check's own emitted `low|medium|high`.**
  Never derived from, and never feeding back into, the run-level `_risk_level_for` ladder
  (a count rollup with price-variance excluded by default). Any rolled-up risk indicator for
  the SQL views is computed at query time over open + resurfaced findings; the existing
  `summary.risk_level` behavior and its Sentry/log output are unchanged.

### Acknowledge / suppress authority (spec §8 #6c — owner decision 2026-09-11)
- **D-05 [owner]: Owner-only via direct SQL with the service-role, v1.** Juan sets
  `acknowledged` / `suppressed` (`acknowledged_by`, `acknowledged_at`) by SQL; every manual
  transition is recorded as an `audit_finding_event` row (planner: provide a small SQL
  helper function `pipeline_memory.acknowledge_finding(finding_key, actor, transition, note)`
  so the event row is never forgotten — still service-role only). No new RLS policy, no
  portal page, no workflow input, no Smartsheet sheet in Phase 13. — **Reversibility:**
  reversible — later surfaces (workflow_dispatch input, portal page) are additive on top.

### `wr_week_ownership` placement (D-12-A carry-forward — owner decision 2026-09-11)
- **D-06 [owner]: Dropped for good.** OWN-01 is satisfied by the `resolve_claimer` ladder over
  `billing_audit.attribution_snapshot` plus the `backfill_source` / `backfill_run_id`
  provenance columns (validated live 2026-09-05). No `wr_week_ownership` table, view, or
  `last_known_before_week` rung will be built. Phase 13 records this as **D-13-A** in the
  docs only: spec §5 note, `REQUIREMENTS.md` OWN-01/OWN-02 re-scope notes, `ROADMAP.md`
  D-12-A line ("deferred to Phase 13" → "dropped, D-13-A"), and the reserved-name comment in
  `pipeline_memory/schema.sql`. No code, no schema. — **Reversibility:** reversible — a
  future consumer can add a derived read-only view in its own phase.

### Audit surface (AUD-03 — owner decision 2026-09-11)
- **D-07 [owner]: SQL views now; visual surface is a tracked follow-up.** Phase 13 ships
  `pipeline_memory.open_findings` (status IN ('open','resurfaced'), ordered by severity /
  last_seen_run) and `pipeline_memory.finding_history_by_wr` (every finding + its events per
  WR). The Excel workbook / portal-v2 page / audit-sheet summary row is NOT built in Phase 13;
  the planner adds a ROADMAP backlog entry ("AUD-03 visual surface — decide after observing
  real finding volume") so the requirement's second half is not silently dropped.
  `_log_to_audit_sheet` stays a placeholder. — **Reversibility:** reversible.

### Lifecycle and run semantics (from spec §6, clarified for the planner)
- **D-08 [spec]: Transitions.** New key → `open` (+ event `opened`). Seen again → bump
  `last_seen_run` (+ event `seen`); if status was `acknowledged` → `resurfaced`
  (+ event `resurfaced`). An `open` or `resurfaced` finding whose group WAS re-audited this
  run and was not produced → `fixed`, `fixed_run = run_id` (+ event `fixed`). Findings whose
  group was NOT re-audited are untouched. `suppressed` and `fixed` findings seen again:
  `fixed` → `open` again (event `reopened`, `fixed_run` cleared); `suppressed` never changes
  status and never surfaces (last_seen_run still bumps) — see Claude's discretion.
- **D-09 [carried, Phase 10/11]: Rollout = shadow-first, default-OFF, fail-open.** New env
  flag `AUDIT_MEMORY_ENABLED` (default `0`), the direct analog of
  `RUN_MEMORY_WRITE_ENABLED`; every Supabase call goes through the existing
  `with_retry(op=...)` + per-op circuit breaker pattern; any failure logs + Sentry breadcrumb
  and the run continues with today's audit output. Never block billing on audit memory.
- **D-10 [carried, Phase 11]: "Re-audited group" = the set of `(wr, week_ending)` pairs whose
  rows were in this run's audited row set.** With `RUN_MEMORY_INCREMENTAL_ENABLED=0` (today)
  the audit sees `all_rows`, so every group present is re-audited; when incremental read is on,
  the audit input is rows for the Phase 11 affected set ∪ rows for the groups of all
  `open`/`resurfaced` findings. The weekly deep run (`mode='full'`) re-audits everything.
  `run_ledger.mode` / `run_id` are the provenance for `first_seen_run` / `last_seen_run` /
  `fixed_run`.
- **D-11 [carried]: Schema lives in `pipeline_memory`** (spec §8 #2), service-role only,
  reapply-safe DDL appended to `pipeline_memory/schema.sql` (`CREATE TABLE IF NOT EXISTS`,
  `CREATE OR REPLACE FUNCTION`). Applying DDL to the live project is a protected-area step
  Juan performs (Supabase connector) after the PR is reviewed — the plan carries a
  `checkpoint:human-verify` there, exactly like Phase 10/12.

### Claude's Discretion
- **D-CD-01:** How `price_variance_anomaly` maps to a week: the check pools Units Total Price
  per WR across rows. Researcher verifies whether the pool spans weeks; if it does, the key's
  `week_ending` is the pooled rows' week when unique, else NULL with the finding treated as
  re-audited whenever ANY affected pair for that WR is re-audited. Document the choice in
  RESEARCH.md / the plan.
- **D-CD-02:** `data_consistency_issue` identity uses the sorted set of issue codes (stable
  strings from `row_issues`, e.g. `invalid_quantity_format`) rather than `row_index`. If the
  researcher finds the issue strings are not stable, fall back to `wr | week_ending` only.
- **D-CD-03:** Server-side vs client-side transitions: prefer one RPC
  (`pipeline_memory.upsert_audit_findings(p_run_id, p_findings jsonb, p_reaudited_pairs jsonb)`)
  that applies D-08 atomically in SQL, mirroring `upsert_rows_bulk`; client-side only if the
  RPC proves awkward to test.
- **D-CD-04:** `suppressed` semantics as stated in D-08 (terminal-hidden, still tracks
  `last_seen_run`).
- **D-CD-05:** Retention: no purge in Phase 13; `audit_finding_event` growth is bounded by
  finding volume (measure in shadow before deciding).

### Folded Todos
- **Run-memory shadow-write follow-ups (Phase 10 REVIEW WR-01..04, IN-01)** —
  `.planning/todos/pending/2026-08-25-run-memory-review-followups.md`. WR-01/02/03 already
  landed (writer reuses `parse_price` / `_parse_quantity`; struck through in the todo). Only
  **WR-04** (`run_ledger.sheets_changed` never populated) and **IN-01** remain → one small
  hygiene task in the last plan (Phase 13 writes `run_ledger`-adjacent code anyway). Move the
  todo to `done/` when closed.
- **Class-A mypy finding** `billing_audit/snapshot_store.py:370` `int(row.get(...))` —
  `.planning/todos/pending/2026-08-25-fix-snapshot-store-int-arg-type.md`. One-line guard
  (`if sheet_id is None or row_id is None: continue` before the cast) + baseline decrement;
  fits because Phase 13 touches the `billing_audit` Supabase layer.
- **Gate-4 mypy hardening (Phase 09 REVIEW WR-02/WR-03/IN-01)** —
  `.planning/todos/pending/2026-08-25-harden-check-mypy-delta-followups.md`. Low priority,
  `scripts/` only; last plan, may be split out if the phase runs long.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design and requirements
- `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md` §3 (draft
  `audit_finding` / `audit_finding_event` DDL, lines ~125-138 — key template SUPERSEDED by
  D-01), §6 (transition rules — basis of D-08), §8 #6 (the owner decision now locked here).
- `.planning/ROADMAP.md` — Phase 13 section (goal, success criteria 1-3) and decision
  **D-12-A** (~line 783) which D-06 closes.
- `.planning/REQUIREMENTS.md` — AUD-01..03 (lines ~303-310); OWN-01/OWN-02 re-scope notes
  (lines ~270-290) to be updated by D-06.
- `.planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md` — affected
  `(wr, week_ending)` set, full-read escalation triggers, deep-run reconciliation (D-10).
- `.planning/phases/10-run-memory-foundation-shadow-writes/10-CONTEXT.md` — shadow-first /
  default-OFF / fail-open contract and the `pipeline_memory` schema conventions (D-09, D-11).

### Code that Phase 13 extends
- `audit_billing_changes.py` — `BillingAudit.audit_financial_data` (line ~333) and the four
  check emitters (lines ~437-700: `_detect_price_anomalies`, `_validate_data_consistency`,
  `_detect_rate_sanity_mismatches`, `_detect_suspicious_changes`); `_risk_level_for` /
  `_total_issues_for_risk` (lines ~191-250) must stay unchanged (D-04);
  `_log_to_audit_sheet` placeholder (line ~800) stays a placeholder (D-07).
- `pipeline/orchestrate.py` ~lines 2903-2925 — the single audit call site
  (`audit_financial_data(source_sheets, all_rows)`); the memory write hooks in after it.
- `pipeline_memory/schema.sql` — header comment lines 40-46 reserve `audit_finding` /
  `audit_finding_event` / `wr_week_ownership`; `run_ledger` (line ~253) and
  `upsert_rows_bulk` (line ~316) are the patterns for the new DDL/RPC.
- `pipeline_memory/reader.py` — `map_affected_to_sheets` (line ~282) and
  `get_last_run_ledger_status` (line ~236): chunked, injection-safe affected-set reads and
  the fail-open contract to copy.
- `pipeline_memory/writer.py` — `_parse_affected_set` and the `run_ledger_start/finish`
  write path; WR-04 (`sheets_changed`) folded todo lives here.
- `billing_audit/client.py` — `with_retry(op=)`, per-op circuit breaker, `_breaker_lock`,
  `close_circuit(observed_generation=)` (PR #407 lesson: every breaker transition under the
  lock; out-of-band closes need the generation check). `pipeline_memory/client.py` is the
  twin (its breaker still lacks the lock — separate follow-up PR, not Phase 13).
- `pipeline/config.py` lines ~490-530 — `RUN_MEMORY_WRITE_ENABLED` /
  `RUN_MEMORY_INCREMENTAL_ENABLED` flag pattern for `AUDIT_MEMORY_ENABLED`.

### Folded todos
- `.planning/todos/pending/2026-08-25-run-memory-review-followups.md`
- `.planning/todos/pending/2026-08-25-fix-snapshot-store-int-arg-type.md`
- `.planning/todos/pending/2026-08-25-harden-check-mypy-delta-followups.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline_memory.upsert_rows_bulk` — server-side diff RPC; template for
  `upsert_audit_findings` (jsonb in, transitions in SQL, affected pairs returned).
- `billing_audit.client.with_retry` + breaker — wrap every audit-memory Supabase call with a
  dedicated op name (`audit_finding_upsert`) so a failing RPC trips its own breaker.
- `pipeline_memory.reader.map_affected_to_sheets` — chunked `IN` handling and the
  "empty input vs empty result" distinction to copy for reading open findings by WR.
- `tests/test_billing_audit_shadow.py` and the Phase 10/11 shadow tests — fake Supabase client
  (`_make_fake_supabase_client`, `_fake_rpc_response`) and breaker fixtures.
- Finding dict shapes already carry `work_request`, `severity`, and per-check fields; the
  source rows carry `Weekly Reference Logged Date` (week ending) used by grouping.

### Established Patterns
- Shadow writes ride the existing run: flag OFF by default, fail-open, Sentry breadcrumb on
  every degrade, never a second Smartsheet read.
- Schema is reapply-safe SQL checked into the repo; Juan applies it through the Supabase
  connector after review (protected area). RLS: service-role only.
- Change-detection key `(WR, week_ending, variant, foreman, dept, job)` is untouched —
  audit memory keys on `(wr, week_ending)` only, matching the Phase 11 affected set.
- Ledger discipline: append a `[YYYY-MM-DD HH:MM]` entry to `memory-bank/living-ledger.md`
  for the new key contract and the D-13-A closure.

### Integration Points
- `pipeline/orchestrate.py` after `audit_financial_data(...)`: build finding rows from
  `audit_results`, compute keys, call the RPC with `run_id` + the re-audited pair set
  (D-10), log a one-line summary (opened / seen / fixed / resurfaced counts).
- `run_ledger` provides `run_id` and `mode`; the deep run sets "all groups re-audited".
- SQL views `open_findings` / `finding_history_by_wr` are read by humans (SQL editor) in
  Phase 13; a future surface reads the same views.

</code_context>

<specifics>
## Specific Ideas

- Success criterion 1 is the acceptance test shape: fixture-seed one finding, run three
  audits that reproduce it (status stays `open`, `last_seen_run` advances), one run that
  re-audits the group without reproducing it (`fixed` + `fixed_run`), then `acknowledge` by
  SQL and reproduce it once more (`resurfaced`). Unit tests against the fake client plus one
  live shadow observation on a scheduled run after Juan applies the DDL.
- Success criterion 2 (wall clock proportional to affected groups + open findings) is
  measured, not asserted: log audited-row and open-finding counts per run.

</specifics>

<deferred>
## Deferred Ideas

- **AUD-03 visual surface** (generated audit workbook in `generated_docs/`, read-only
  portal-v2 page with an RLS policy, or the `_log_to_audit_sheet` summary row) — decide after
  observing real finding volume; ROADMAP backlog item created by the planner.
- **`workflow_dispatch` acknowledge input** (`advanced_options` key `ack_finding_keys:`) —
  v1.1 add-on once SQL-only acknowledgement is trusted; GitHub Actions change needs owner
  approval.
- **portal-v2 acknowledge page** with a role model — future phase, after the read-only surface.
- **`recent_discussion` findings in memory** — only if a `fixed` rule is defined for
  sheet-level discussions.
- **`wr_week_ownership` derived view** — only if a concrete consumer appears (own phase).
- **`pipeline_memory/client.py` breaker lock** — mirror `_breaker_lock` from PR #407;
  separate small PR, not Phase 13.

### Reviewed Todos (not folded)
None — all three keyword matches were folded (see Folded Todos).

</deferred>

---

*Phase: 13-audit-memory*
*Context gathered: 2026-09-11*
