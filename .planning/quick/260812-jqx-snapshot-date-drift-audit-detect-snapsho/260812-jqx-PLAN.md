---
phase: quick-260812-jqx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pipeline/snapshot_drift.py
  - billing_audit/snapshot_store.py
  - billing_audit/schema.sql
  - pipeline/config.py
  - pipeline/orchestrate.py
  - audit_billing_changes.py
  - tests/test_snapshot_drift_audit.py
  - memory-bank/living-ledger.md
autonomous: true
requirements: [QT-260812-jqx]

user_setup:
  - service: supabase
    why: "New additive tables billing_audit.snapshot_provenance + billing_audit.snapshot_drift (D-06, D-07). The pipeline NEVER runs DDL — schema.sql is documentation-grade and applied by hand."
    dashboard_config:
      - task: "Apply the two appended CREATE TABLE IF NOT EXISTS blocks from billing_audit/schema.sql"
        location: "Supabase Dashboard -> project poeyztlmsawfoqlanucc -> SQL Editor"
      - task: "Confirm 'billing_audit' is listed under Exposed schemas, then reload the PostgREST cache"
        location: "Supabase Dashboard -> Project Settings -> API -> Exposed schemas"
      - task: "Verify assumptions A1/A4 against ONE known-drifted row: cell-history entry ordering and the literal modified_by email for automation writes. If the email is not 'automation@smartsheet.com', set SNAPSHOT_DRIFT_AUTOMATION_EMAIL rather than editing code."
        location: "Smartsheet UI -> a row from the 2026-08-12 drift incident -> Snapshot Date cell history"
  - service: github-actions
    why: "Both kill-switches ship at safe defaults; no workflow change is required to land this. Flipping the hold gate on is a deliberate operator action AFTER A1/A4 are verified."
    env_vars:
      - name: SNAPSHOT_DRIFT_HOLD_ENABLED
        source: "Leave UNSET (defaults false, D-08). Set to 'true' in .github/workflows/weekly-excel-generation.yml only after a live run shows correct automation_self_fire classification."

estimate:
  tokens: 78000
  raw_tokens: 78000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A row whose computed billing week differs from its recorded prior billed week is detected as a drift candidate using ZERO extra Smartsheet API calls (D-04)."
    - "First sight of a row seeds provenance silently: no drift flag, no cell-history call, no hold (D-09)."
    - "An automation self-fire on an already-billed row is held to BOTH its prior Weekly Reference Logged Date AND its prior Snapshot Date, so the row still appears in the workbook day-tables and the prior week's content hash is unchanged (D-01, RESEARCH caveat 1)."
    - "A manual edit is shadow-logged and NEVER held (D-02)."
    - "Any classification failure — API error, missing column id, per-run cap exhausted, sub-budget short — yields classification 'unclassified': flagged, never held (D-03, D-10)."
    - "With SNAPSHOT_DRIFT_AUDIT_ENABLED=false and SNAPSHOT_DRIFT_HOLD_ENABLED=false, pipeline behaviour is byte-identical to today (D-08)."
    - "Only automation self-fire holds inflate the audit total_issues / risk_level; manual and unclassified drift are counted but do not escalate risk (D-01, RESEARCH caveat 5)."
    - "A missing Supabase client, an unapplied migration, or a PostgREST fetch failure makes the whole feature a no-op — it can never break the billing run (D-07)."
  artifacts:
    - "pipeline/snapshot_drift.py — apply_snapshot_drift_holds() + the classifier, the only place drift logic lives"
    - "billing_audit/snapshot_store.py — bulk provenance read, bulk provenance upsert, append-only drift-event insert"
    - "billing_audit/schema.sql — appended billing_audit.snapshot_provenance + billing_audit.snapshot_drift DDL (manual apply)"
    - "pipeline/config.py — SNAPSHOT_DRIFT_AUDIT_ENABLED / SNAPSHOT_DRIFT_HOLD_ENABLED / SNAPSHOT_DRIFT_MAX_ROWS / SNAPSHOT_DRIFT_PACE_SEC / SNAPSHOT_DRIFT_MAX_MINUTES / SNAPSHOT_DRIFT_AUTOMATION_EMAIL"
    - "pipeline/orchestrate.py — ONE call site at the pre-grouping seam"
    - "audit_billing_changes.py — drift counters + escalate_risk_for_snapshot_drift()"
    - "tests/test_snapshot_drift_audit.py — RED-first suite covering the 9 research cases"
    - "memory-bank/living-ledger.md — dated [YYYY-MM-DD HH:MM] entry"
  key_links:
    - "pipeline/orchestrate.py pre-grouping seam (after the audit else-branch at :577, before the grouping span at :580) -> apply_snapshot_drift_holds(all_rows, source_sheets, client, session_start). Upstream of the five Weekly Reference Logged Date pre-pass readers at grouping.py:170/234/289/360/417 and of the single week computation at grouping.py:440-463."
    - "Held row rewrites BOTH fields -> grouping.py:440-463 (week key) AND excel.py:711-736 (Monday-Sunday snapshot filter) AND change_detection.py:115/143/169 (sort key + legacy hash + extended hash). Rewriting only the week silently deletes the row from every day-table."
    - "row['__source_sheet_id'] + row['__row_id'] (fetch.py:315-331) -> source['column_mapping']['Snapshot Date'] / ['Units Completed?'] (discovery.py:438/448/489, surfaced at :615) -> smartsheet.Cells.get_cell_history(sheet_id, row_id, column_id, include_all=True)"
    - "billing_audit.client.get_client() returning None (client.py:243-294) -> whole feature no-ops; every new store function inherits the never-raise contract"
    - "drift_summary['automation_self_fire_holds'] -> audit_billing_changes.escalate_risk_for_snapshot_drift() -> summary['risk_level'] using the existing 0 / <=3 / else thresholds (audit_billing_changes.py:509-517)"
---

<objective>
Add a defence-in-depth snapshot-date drift audit to the production billing
pipeline: detect rows whose billing week moved away from the week they were
last billed under, classify each mover as an automation self-fire or a
legitimate manual edit via targeted Smartsheet cell-history lookups, record
every drift event durably in a new additive Supabase shadow layer, and —
for automation self-fires ONLY — hold the row at its previously-billed week
so the workbook stays correct.

Background (living-ledger `[2026-08-12 13:40]`): the per-sheet "record
Snapshot Date" Smartsheet automation fires on ANY row change where
`Units Completed?` is checked, so same-value saves and bulk API touches
re-stamp Snapshot Date to today. `Weekly Reference Logged Date` is Snapshot
Date snapped to Sunday, so each re-stamp silently moves an already-billed
unit into the current billing week. Juan is fixing the automation trigger
in the Smartsheet UI; this task is the pipeline-side backstop.

**Locked decision IDs used throughout this plan** (from
`260812-jqx-CONTEXT.md`, which uses prose sections rather than numbered IDs
— this mapping is the traceability contract):

| ID | Locked decision |
|---|---|
| D-01 | Hold prior week + flag HIGH — automation self-fires only |
| D-02 | Manual edits are NEVER blocked or held; shadow-logged only |
| D-03 | Unclassifiable drift must NOT hold: fail-open on gating, fail-closed on logging |
| D-04 | Cell-history spend on week-movers ONLY, per-run cap ~40 rows, ~2s pacing, ~2 calls/row |
| D-05 | Classifier signature: `automation@smartsheet.com` Snapshot Date write with NO `Units Completed?` change within +/-2 minutes |
| D-06 | New additive Supabase table(s); existing `billing_audit` tables untouched |
| D-07 | Supabase schema ADDITION only; reviewed + applied manually by Juan; pipeline never runs DDL |
| D-08 | Separate kill-switches — detection/logging defaults ON, the HOLD gate defaults OFF |
| D-09 | v1 provenance seeded from the first run that sees a row; no history backfill |
| D-10 | Respect TIME_BUDGET_MINUTES; degrade to `unclassified` when the budget is tight, never stall |

Purpose: already-billed units stop silently drifting weeks, and every drift
becomes queryable evidence pointing at the exact row to repair upstream.
Output: one new pipeline module, one new Supabase store module, appended
documentation-grade DDL, six env-var switches, a single orchestrate call
site, additive audit counters, and a RED-first pytest suite.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260812-jqx-snapshot-date-drift-audit-detect-snapsho/260812-jqx-CONTEXT.md
@.planning/quick/260812-jqx-snapshot-date-drift-audit-detect-snapsho/260812-jqx-RESEARCH.md
@CLAUDE.md
@.claude/rules/billing-pipeline-guardrails.md
@.claude/rules/smartsheet-python-optimization.md
</context>

<source_coverage_audit>
| Source | Item | Covered by |
|---|---|---|
| GOAL | Detect Snapshot Date changes on rows whose week was already billed | Task 1 |
| GOAL | Classify automation self-fire vs legitimate manual edit via cell history | Task 2 |
| GOAL | Flag ALL drift (run log + Supabase shadow + audit risk level) | Task 1 (log + Supabase), Task 3 (risk level) |
| GOAL | Hold-prior-week gate ONLY for automation self-fires, never manual | Task 3 |
| REQ | none — quick task, no ROADMAP requirement IDs | n/a |
| CONTEXT | D-01 hold prior week + flag HIGH (self-fires only) | Task 3 |
| CONTEXT | D-02 manual edits never blocked | Task 3 |
| CONTEXT | D-03 unclassifiable → flag, no hold | Task 2 + Task 3 |
| CONTEXT | D-04 week-movers only, capped, paced | Task 1 (candidate selection) + Task 2 (cap/pace) |
| CONTEXT | D-05 classifier signature | Task 2 |
| CONTEXT | D-06 new additive Supabase table | Task 1 |
| CONTEXT | D-07 manual apply by Juan; pipeline never runs DDL | Task 1 + user_setup |
| CONTEXT | D-08 separate kill-switches, hold defaults OFF | Task 1 (both declared) + Task 3 (hold honoured) |
| CONTEXT | D-09 silent first-run seed | Task 1 |
| CONTEXT | D-10 time-budget degradation | Task 2 |
| RESEARCH | Caveat 1 — rewrite BOTH week AND snapshot fields | Task 3 |
| RESEARCH | Caveat 2 — mandatory pacing / cap / sub-budget / pre-flight guard | Task 2 |
| RESEARCH | Caveat 3 — SNAPSHOT_DRIFT_HOLD_ENABLED defaults OFF | Task 1 + Task 3 |
| RESEARCH | Caveat 4 — no new mutating AUDIT_SHEET_ID write in v1 | Task 3 (explicitly excluded) |
| RESEARCH | Caveat 5 — fold ONLY self-fires into total_issues | Task 3 |
| RESEARCH | Caveat 6 — bulk Supabase reads only; silent first-run seed | Task 1 |
| RESEARCH | Caveat 7 — fail-open gating, fail-closed logging | Task 2 + Task 3 |
| RESEARCH | Seam at orchestrate.py:578; zero grouping.py/excel.py edits | Task 1 (seam) + diff guard on every task |
| RESEARCH | Package Legitimacy Audit: N/A, no new packages | no install task exists in this plan |

No item is MISSING. No item is deferred.
</source_coverage_audit>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: End-to-end drift detection — one path, zero Smartsheet API calls</name>
  <files>tests/test_snapshot_drift_audit.py, billing_audit/snapshot_store.py, billing_audit/schema.sql, pipeline/config.py, pipeline/snapshot_drift.py, pipeline/orchestrate.py</files>
  <precondition>`pytest tests/ -v` passes on a clean tree before any edit (this is the behaviour-neutrality baseline the diff guard is measured against).</precondition>
  <read_first>
    - `billing_audit/client.py:221-294` — `get_client()` returns `None` and never raises; every new store function inherits that contract.
    - `billing_audit/writer.py:1144-1264` — `lookup_group_hash` / `upsert_group_hash`: the plain-table read/write shape to copy (NOT the RPC shape — an RPC would need a Supabase Dashboard deploy outside this repo).
    - `billing_audit/writer.py:840` `prefetch_attribution` — the bulk-read shape.
    - `billing_audit/writer.py:418` `_sanitized_wr` — WR sanitization / collision-quarantine rules.
    - `pipeline/fetch.py:315-331` — every row carries `__source_sheet_id` and `__row_id`.
    - `pipeline/orchestrate.py:544-585` — the audit block and the grouping span that bracket the seam.
    - `pipeline/grouping.py:438-467` — the single place a row's billing week is computed, from `Weekly Reference Logged Date` via `excel_serial_to_date`.
    - `tests/test_rate_sanity_audit.py:1-60` — the 260812-isx RED-first, no-network fixture pattern.
    - `tests/test_billing_audit_shadow.py` — the Supabase writer mock pattern.
  </read_first>
  <behavior>
    - Test: a row with no provenance baseline produces zero drift candidates, triggers zero cell-history calls, and is queued for a provenance seed (D-09).
    - Test: a row whose computed week equals its recorded `billed_week` produces zero drift candidates and zero cell-history calls (D-04).
    - Test: a row whose computed week differs from its recorded `billed_week` is emitted as a candidate with `classification` set to the not-yet-classified value, is NOT held, and its `Weekly Reference Logged Date` and `Snapshot Date` are unchanged.
    - Test: with the audit kill-switch disabled, `apply_snapshot_drift_holds` returns its zeroed summary immediately, performs no Supabase call, and leaves every row dict identical by value (D-08).
    - Test: when `get_client()` returns `None`, the whole pass no-ops and returns a summary flagged as unavailable — no exception escapes.
    - Test: a raised exception from the provenance bulk read is swallowed and degrades to the no-baseline path.
    - Test: provenance upsert is invoked at most once per run with a batched payload — never once per row (RESEARCH caveat 6; reproduces the 2026-04-24 retry-exhaustion incident if violated).
  </behavior>
  <action>
Write the failing tests FIRST in `tests/test_snapshot_drift_audit.py`, run them RED, then implement.

**(a) `billing_audit/snapshot_store.py`** — new module, imports `get_client`
and `with_retry` from `billing_audit.client` and `_sanitized_wr` from
`billing_audit.writer`. Three public functions, each fail-safe (catch their
own errors, never raise, return a neutral value when `get_client()` is
`None`), mirroring `upsert_group_hash` at `billing_audit/writer.py:1222`:
    - `fetch_snapshot_provenance(keys)` — ONE select for all
      `(sheet_id, row_id)` pairs in the run, returning a dict keyed by that
      tuple. Bulk only; per-row reads are forbidden (D-06, RESEARCH caveat 6).
      Return `({}, status)` where status distinguishes success / no rows /
      fetch failure / unavailable, matching the `lookup_group_hash` status
      vocabulary.
    - `upsert_snapshot_provenance(records)` — ONE batched upsert on the
      `(sheet_id, row_id)` primary key.
    - `insert_snapshot_drift_events(events)` — ONE batched append-only insert.

**(b) `billing_audit/schema.sql`** — APPEND two
`CREATE TABLE IF NOT EXISTS` blocks plus `service_role` grants at the end of
the file; change nothing above (D-06, D-07). The file header already states
it is documentation-grade and manually applied — the pipeline executes no
DDL. Follow the existing comment style used for `group_content_hash`
(`billing_audit/schema.sql:139-145`), including a note that when the table is
absent the reader degrades to a fetch failure and prior behaviour is kept.
    - `billing_audit.snapshot_provenance` — state table, PK
      `(sheet_id BIGINT, row_id BIGINT)`, plus `wr TEXT`, `cu TEXT`,
      `snapshot_date DATE`, `billed_week DATE`, `run_id TEXT`,
      `first_seen_at TIMESTAMPTZ`, `last_seen_at TIMESTAMPTZ`.
    - `billing_audit.snapshot_drift` — append-only event table keyed
      `(sheet_id, row_id, detected_at)`, plus `wr`, `cu`,
      `prior_snapshot_date`, `new_snapshot_date`, `prior_billed_week`,
      `new_week`, `changed_by TEXT`, `classification TEXT`,
      `held BOOLEAN NOT NULL DEFAULT FALSE`, `run_id TEXT`, and an index on
      `(wr, detected_at DESC)`.
    Splitting state from events keeps the upsert idempotent while preserving
    a complete audit trail.

**(c) `pipeline/config.py`** — declare six module-level switches next to the
`TIME_BUDGET_MINUTES` family at `:106`, each read via `os.getenv` with a
default, documented in the same comment style as the surrounding block
(D-08): `SNAPSHOT_DRIFT_AUDIT_ENABLED` (default true),
`SNAPSHOT_DRIFT_HOLD_ENABLED` (default false — the gate is opt-in until a
live run proves the classifier, per D-08 and RESEARCH caveat 3),
`SNAPSHOT_DRIFT_MAX_ROWS` (default 40), `SNAPSHOT_DRIFT_PACE_SEC`
(default 2.0), `SNAPSHOT_DRIFT_MAX_MINUTES` (default 5),
`SNAPSHOT_DRIFT_AUTOMATION_EMAIL` (default `automation@smartsheet.com`, so
assumption A4 can be corrected by configuration instead of a code change).

**(d) `pipeline/snapshot_drift.py`** — new module.
`apply_snapshot_drift_holds(all_rows, source_sheets, client, session_start)`
returns a summary dict. In this task it detects only:
    1. Honour the audit kill-switch first — read it per call, not at import,
       exactly as `audit_billing_changes.py:376` does for the rate-sanity
       switch. Disabled means an immediate zeroed summary, no Supabase touch.
    2. Build `(sheet_id, row_id)` keys from `__source_sheet_id` / `__row_id`
       for rows that carry a WR and a parseable `Weekly Reference Logged
       Date` (use the existing `excel_serial_to_date`, never `dateutil`
       directly).
    3. One bulk provenance fetch.
    4. Absent baseline means seed only: no candidate, no flag, no history
       call, no hold (D-09). Same for a fetch failure or an unavailable
       client — the pass degrades to seed-and-continue.
    5. Baseline present and computed week equals `billed_week` means refresh
       `last_seen_at` and move on — zero extra API calls (D-04).
    6. Baseline present and weeks differ means emit a drift candidate
       carrying prior/new snapshot date, prior/new week, and a placeholder
       classification. Do NOT mutate the row in this task.
    7. Log one INFO summary line per run: candidate count, seeded count, and
       the counts by classification.
    8. Write drift events and upsert provenance in one batched call each at
       the end of the pass. Provenance records the week the row will
       actually be billed under this run.
    Use function-local lazy imports for `billing_audit.snapshot_store` so a
    missing/failed Supabase package can never affect module import, matching
    the 260812-isx pattern. Wrap the whole body so no exception escapes to
    the caller.

**(e) `pipeline/orchestrate.py`** — insert exactly ONE call site between the
audit `else:` branch close at `:577` and the grouping log line at `:580`,
wrapped in its own `try`/`except` that logs a warning and continues. This
placement is upstream of the five `Weekly Reference Logged Date` pre-pass
readers at `pipeline/grouping.py:170/234/289/360/417` and of the single week
computation at `:440-463`, which is what makes zero grouping edits possible.
Import the new function at the existing import block. Do not touch any other
line of `orchestrate.py`.

PEP 8, type hints, 4-space indent, lines at or under 79 characters, PEP 257
docstrings throughout.
  </action>
  <verify>
    <automated>pytest tests/test_snapshot_drift_audit.py -v && python -m py_compile generate_weekly_pdfs.py pipeline/snapshot_drift.py billing_audit/snapshot_store.py && test "$(git diff --name-only -- pipeline/grouping.py pipeline/excel.py | wc -l)" -eq 0 && test "$(git diff -U0 -- pipeline/orchestrate.py | grep -c '^@@')" -le 2</automated>
  </verify>
  <done>The new test file passes; `pipeline/snapshot_drift.py` and `billing_audit/snapshot_store.py` compile; `billing_audit/schema.sql` gained exactly two new table definitions and no edits above them; `pipeline/grouping.py` and `pipeline/excel.py` have zero diff hunks; `pipeline/orchestrate.py` has at most two diff hunks (the import and the seam).</done>
  <reversibility rating="reversible">Detection-only, gated behind a kill-switch, mutates no row and no billing artifact; reverting is a file delete plus removing one call site.</reversibility>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Cell-history classifier with pacing, cap, and sub-budget</name>
  <files>pipeline/snapshot_drift.py, tests/test_snapshot_drift_audit.py</files>
  <precondition>`SMARTSHEET_API_TOKEN` is NOT required — every test in this task mocks the SDK client; no live Smartsheet call is made during implementation or verification.</precondition>
  <read_first>
    - `pipeline/discovery.py:436-489` and `:615` — `column_mapping['Snapshot Date']` assignment and the `{'id', 'name', 'column_mapping'}` source-sheet dict shape.
    - `pipeline/fetch.py:276` — `sheet_has_snapshot_date_column`, proof that the Snapshot Date mapping is explicitly optional per sheet.
    - `pipeline/orchestrate.py:683-685` — the canonical `TIME_BUDGET_MINUTES` + `GITHUB_ACTIONS_MODE` pre-flight guard to copy verbatim in shape.
    - `pipeline/orchestrate.py:416` — `session_start` anchor.
    - `pipeline/utils` `is_checked` / `billing_audit/writer.py` `_is_checked` — Smartsheet checkbox truthiness returns str, bool, or 1 variably.
    - `audit_billing_changes.py:683-690` — the existing cell-history stub that makes no API call; this is greenfield, there is no in-repo call to copy.
  </read_first>
  <behavior>
    - Test: a Snapshot Date history entry written by the configured automation identity, with no `Units Completed?` history entry inside the +/-2 minute window, classifies as an automation self-fire (D-05).
    - Test: the same Snapshot Date entry accompanied by a `Units Completed?` change 30 seconds earlier classifies as manual.
    - Test: a Snapshot Date entry written by a human email classifies as manual regardless of the `Units Completed?` timeline (D-02).
    - Test: `get_cell_history` raising any exception classifies as unclassified (D-03).
    - Test: a source sheet missing either column id in `column_mapping` classifies as unclassified with zero API calls (assumption A2).
    - Test: with the per-run cap set to 1 and two candidates present, the first is classified and the second is unclassified — exactly two API calls total (D-04).
    - Test: with `TIME_BUDGET_MINUTES` set, GitHub-Actions mode on, and remaining budget below the sub-budget, every candidate is unclassified and zero API calls are made (D-10).
    - Test: history entries supplied newest-first and oldest-first both yield the same classification, proving the code sorts by `modified_at` itself (assumption A1).
    - Test: `modified_by` supplied as an object with `.email`, as a bare string, and as `None` are all handled without raising (assumption A1).
    - Test: pacing sleep is invoked between calls with the configured interval and is NOT invoked before the first call.
  </behavior>
  <action>
Write the failing tests FIRST, run them RED, then implement inside
`pipeline/snapshot_drift.py`. Every candidate produced by Task 1 now gets a
classification.

Add `_classify_drift_candidate(client, candidate, column_ids, deadline)`
returning one of three classification values: automation self-fire, manual,
or unclassified. Rules:

    1. **Pre-flight budget guard, before any call.** Copy the shape at
       `pipeline/orchestrate.py:683-685`: when `TIME_BUDGET_MINUTES` is set
       and running under GitHub Actions, compute remaining minutes from
       `session_start`; if remaining is below `SNAPSHOT_DRIFT_MAX_MINUTES`,
       skip classification for the entire run — every candidate becomes
       unclassified and a single INFO line records the skip reason (D-10).
       Also enforce the sub-budget as a running deadline inside the loop, so
       a slow phase stops early rather than eating the session budget.
    2. **Cap.** Process at most `SNAPSHOT_DRIFT_MAX_ROWS` candidates per run,
       in deterministic order (sort by sheet id then row id so reruns are
       reproducible). Every candidate beyond the cap is unclassified (D-04).
    3. **Column ids.** Resolve `Snapshot Date` and `Units Completed?` column
       ids from the candidate's own source sheet `column_mapping`. If either
       is absent, return unclassified without any API call (assumption A2 —
       the Snapshot Date mapping is already known to be optional per sheet).
    4. **Two calls per candidate**, both
       `client.Cells.get_cell_history(sheet_id, row_id, column_id,
       include_all=True)` — Snapshot Date first, then `Units Completed?`
       (D-04). If the Snapshot Date history alone already rules out the
       automation identity, skip the second call and save the quota.
    5. **Self-pacing is mandatory.** Sleep `SNAPSHOT_DRIFT_PACE_SEC` between
       calls (never before the first). The SDK's `max_retry_time` is 30
       seconds of exponential backoff that only engages when the server sets
       `shouldRetry`; roughly four attempts exhaust it, so it will not
       absorb a sustained cell-history throttle. Do not add a custom retry
       loop — pacing plus the SDK's own retry is the whole strategy
       (RESEARCH caveat 2 and the Don't Hand-Roll table).
    6. **Defensive parsing.** Sort `IndexResult.data` by `modified_at` in
       code rather than trusting API ordering; read the identity via
       `getattr(modified_by, 'email', None)` falling back to `str(...)`;
       compare case-insensitively against
       `SNAPSHOT_DRIFT_AUTOMATION_EMAIL`. Use the shared checkbox-truthiness
       helper for `Units Completed?` values rather than `bool()`.
    7. **Signature.** The newest Snapshot Date write by the automation
       identity, with NO `Units Completed?` history entry whose
       `modified_at` falls within +/-2 minutes of it, is an automation
       self-fire. Anything else is manual (D-05).
    8. **Fail-open.** Wrap each candidate's classification in its own
       try/except: any exception, timeout, retry exhaustion, or malformed
       payload yields unclassified and the loop continues (D-03). The run
       log records every unclassified candidate with the reason so the
       fail-closed logging half of D-03 still holds.

Counters returned in the summary: candidates seen, classified, and the
per-classification counts, plus the skip reason when the budget guard fires.
  </action>
  <verify>
    <automated>pytest tests/test_snapshot_drift_audit.py -v && python -m py_compile pipeline/snapshot_drift.py && test "$(git diff --name-only -- pipeline/grouping.py pipeline/excel.py | wc -l)" -eq 0</automated>
  </verify>
  <done>All classifier tests pass, including both history orderings, all three `modified_by` shapes, the cap, the budget guard, and the missing-column-id path. Zero live Smartsheet calls occur during the suite. `pipeline/grouping.py` and `pipeline/excel.py` still have zero diff hunks.</done>
  <reversibility rating="reversible">Read-only Smartsheet calls behind an existing kill-switch; no row, price, hash, filename, or upload behaviour is touched.</reversibility>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Hold-prior-week override (both fields) + audit risk wiring</name>
  <files>pipeline/snapshot_drift.py, audit_billing_changes.py, pipeline/orchestrate.py, tests/test_snapshot_drift_audit.py, memory-bank/living-ledger.md</files>
  <precondition>Tasks 1 and 2 are committed and `pytest tests/ -v` is green — the hold override is only safe on top of a classifier that already fails open.</precondition>
  <read_first>
    - `pipeline/excel.py:711-736` — `generate_excel` buckets rows by `Snapshot Date` and drops any row outside the group's Monday-Sunday window. This is the caveat that makes rewriting one field a silent under-bill.
    - `pipeline/change_detection.py:115` (sort key), `:143` (legacy row_data), `:169` (extended row_fields) — `Snapshot Date` participates in the content hash in both modes.
    - `pipeline/grouping.py:1167` — where `__week_ending_date` is stamped onto the group.
    - `pipeline/orchestrate.py:1461` — `history_key` is built from the group, not the row, so it follows automatically.
    - `audit_billing_changes.py:185-206` — how the 260812-isx rate-sanity bucket was declared and wired as a numbered step.
    - `audit_billing_changes.py:490-517` — summary keys, the `total_issues` sum, and the 0 / <=3 / else risk thresholds.
    - `audit_billing_changes.py:586-617` — `_log_to_audit_sheet` builds a dict and discards it. It writes nothing to Smartsheet.
  </read_first>
  <behavior>
    - Test: an automation self-fire candidate with the hold gate enabled rewrites BOTH `Weekly Reference Logged Date` and `Snapshot Date` back to the provenance values, and preserves the drifted originals under private keys.
    - Test: the held row survives `generate_excel`'s Monday-Sunday snapshot filter — the group's day-table row count equals the group's row count (the warning sign named in RESEARCH pitfall 1).
    - Test: the prior week's content hash computed over the held row equals the hash computed before the drift, in both legacy and extended change-detection modes.
    - Test: a manual candidate is never mutated even when the hold gate is enabled (D-02).
    - Test: an unclassified candidate is never mutated even when the hold gate is enabled (D-03).
    - Test: with the hold gate at its default, an automation self-fire is flagged and recorded but the row is NOT mutated (D-08).
    - Test: four automation self-fire holds escalate `risk_level` to HIGH; four manual drifts and four unclassified drifts leave `risk_level` unchanged (D-01, RESEARCH caveat 5).
    - Test: the drift event rows written to Supabase carry the classification and the held boolean for every candidate, including manual and unclassified (D-03 fail-closed logging).
    - Test: with both kill-switches at values that disable the feature, a representative `all_rows` fixture is value-identical after the pass and `risk_level` matches the pre-change baseline (D-08).
  </behavior>
  <action>
Write the failing tests FIRST, run them RED, then implement.

**(a) The override, in `pipeline/snapshot_drift.py`.** Gate on
`SNAPSHOT_DRIFT_HOLD_ENABLED` read per call. Apply ONLY to candidates
classified as an automation self-fire (D-01); manual and unclassified
candidates flow through untouched (D-02, D-03). For each held row set
`Weekly Reference Logged Date` to the provenance `billed_week` and
`Snapshot Date` to the provenance `snapshot_date`, and stash the drifted
originals plus the classification and the evidence timestamps under private
double-underscore keys so they survive into logging, the Supabase event row,
and any later diagnosis.

Rewriting both fields is load-bearing in three independent places and the
tests above pin each one:
    - `Weekly Reference Logged Date` drives the week key at
      `pipeline/grouping.py:440-463`.
    - `Snapshot Date` drives `generate_excel`'s Monday-Sunday bucket filter
      at `pipeline/excel.py:711-736`. A row held into the prior week while
      still carrying the drifted snapshot passes grouping, counts toward
      group membership, and is then excluded from every day-table — a silent
      under-bill, strictly worse than the drift itself.
    - `Snapshot Date` is inside the content hash at
      `pipeline/change_detection.py:143` and `:169` and inside the sort key
      at `:115`. Restoring it is what makes the prior week's hash stable and
      stops the pointless regeneration churn.
Because the rewrite happens before grouping, the row can only ever land in
the prior week's group — the current week never sees it, so no de-duplication
logic is needed. The change-detection key stays
`(WR, week, variant, foreman, dept, job)`, unshortened.

For each held row emit one deterministic run-log line carrying WR, row id,
prior week, drifted week, and the evidence timestamps, so the hold decision
is visible without opening Supabase.

**(b) Audit wiring, in `audit_billing_changes.py`.** Additive only.
Declare drift counters alongside `total_rate_sanity_mismatches` at `:493-496`
and add a new module-level function
`escalate_risk_for_snapshot_drift(summary, self_fire_holds)` that recomputes
`risk_level` from the existing `total_issues` sum PLUS the self-fire hold
count, reusing the same 0 / <=3 / else thresholds at `:509-517`, and appends
a matching recommendation. It runs post-hoc because the drift pass executes
after `audit_financial_data`. Only automation self-fire holds feed it —
folding in manual drift would drive a routine batch of legitimate edits to
HIGH and desensitise the signal (RESEARCH caveat 5).

Leave the three-way inconsistency between `_generate_audit_summary`'s
`total_issues` (`:502-507`), `_log_to_audit_sheet`'s three-term sum
(`:599`), and `_compute_trend`'s three-term sum (`:638-639`) exactly as it
is — pre-existing and out of scope.

**Explicitly NOT in this task:** any new mutating Smartsheet write to
`AUDIT_SHEET_ID`. `_log_to_audit_sheet` is a no-op placeholder that builds a
dict and discards it (`audit_billing_changes.py:611-614`), so a real audit
sheet write would be a brand-new mutating call site in a protected area,
requiring Juan's approval, `SKIP_UPLOAD` gating, and audit-sheet column-id
discovery. That is a separate task. The durable, queryable flag surface in
v1 is the Supabase shadow layer plus the run log (RESEARCH caveat 4).

**(c) `pipeline/orchestrate.py`.** Extend only the existing seam added in
Task 1 so the returned summary counters are merged into
`audit_results['summary']` and `escalate_risk_for_snapshot_drift` is called
when the audit ran. No new call site; no other line changes.

**(d) `memory-bank/living-ledger.md`.** APPEND one dated
`[YYYY-MM-DD HH:MM]` entry at the BOTTOM of the file per the repo's
self-documenting rule. Record: the drift root cause, the both-fields
requirement and why one field is a silent under-bill, the fail-open gating /
fail-closed logging rule, the six env switches with their defaults, the
manual-DDL requirement, and the two live assumptions still to verify
(cell-history ordering and the automation identity email).
  </action>
  <verify>
    <automated>pytest tests/test_snapshot_drift_audit.py -v && pytest tests/ -v && python -m py_compile generate_weekly_pdfs.py pipeline/snapshot_drift.py audit_billing_changes.py && test "$(git diff --name-only -- pipeline/grouping.py pipeline/excel.py | wc -l)" -eq 0</automated>
    <human-check>Run `SKIP_UPLOAD=true WR_FILTER=<one known-drifted WR> SNAPSHOT_DRIFT_HOLD_ENABLED=true python generate_weekly_pdfs.py` against real Smartsheet data and confirm from the run log that the drifted row is classified as an automation self-fire, is held to the prior week, and appears in the generated workbook's day-table for that week. This is the live check for assumptions A1 and A4; if the classification comes back unclassified, correct `SNAPSHOT_DRIFT_AUTOMATION_EMAIL` rather than the classifier.</human-check>
  </verify>
  <done>The full suite passes (previous count plus the new file, no regressions). Held rows survive the Monday-Sunday filter and keep a stable prior-week hash in both change-detection modes. Manual and unclassified candidates are never mutated. Four self-fire holds escalate risk to HIGH; manual and unclassified drift do not. With the feature disabled, rows and `risk_level` are identical to baseline. `pipeline/grouping.py` and `pipeline/excel.py` still have zero diff hunks. A dated ledger entry is appended.</done>
  <reversibility rating="costly">The hold override changes which week a unit is billed under. It ships behind a default-off gate and is reversible by unsetting the gate, but any workbook generated while it was enabled would need regeneration via REGEN_WEEKS to undo.</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Smartsheet API to pipeline | Row values, cell-history payloads, and `modified_by` identities are attacker-influenceable input; the classifier's hold decision depends on them |
| Pipeline to Supabase (`service_role`) | New writes to `billing_audit.snapshot_provenance` and `billing_audit.snapshot_drift` cross into the privileged data tier |
| Environment configuration to gating behaviour | Six env vars control whether billing weeks are rewritten |
| Run log and Sentry to operators | Drift evidence lines may carry row-level identifiers |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-jqx-01 | Spoofing | `_classify_drift_candidate` identity check | medium | mitigate | A forged or renamed `modified_by` email would misclassify. Mitigated by fail-open (a non-matching identity yields manual, never a hold) plus `SNAPSHOT_DRIFT_AUTOMATION_EMAIL` being operator-controlled, plus the default-off hold gate — a spoof cannot cause a hold without an operator first enabling gating. |
| T-jqx-02 | Tampering | hold override in `pipeline/snapshot_drift.py` | high | mitigate | Rewriting billing dates is the highest-blast-radius action here. Mitigated by: self-fires only, `SNAPSHOT_DRIFT_HOLD_ENABLED` defaulting off, rewriting BOTH fields so the workbook cannot silently lose the row, and the Task 3 hash-stability and Monday-Sunday-filter tests. |
| T-jqx-03 | Repudiation | drift decisions | medium | mitigate | Every candidate — held, manual, or unclassified — is written to the append-only `billing_audit.snapshot_drift` table with classification, `changed_by`, `held`, and `run_id`, plus a deterministic run-log line for each hold. |
| T-jqx-04 | Information disclosure | run log, Sentry breadcrumbs, Supabase event rows | medium | mitigate | Log WR, row id, dates, and the classification only. Do not log full row dicts, pricing, or personnel fields. Sentry Logs stay off by default (`SENTRY_ENABLE_LOGS`) and the existing `before_send_log` sanitizer remains the backstop. |
| T-jqx-05 | Denial of service | Smartsheet cell-history endpoint | high | mitigate | Week-movers only, `SNAPSHOT_DRIFT_MAX_ROWS` cap, `SNAPSHOT_DRIFT_PACE_SEC` self-pacing, `SNAPSHOT_DRIFT_MAX_MINUTES` sub-budget with a pre-flight guard, and no custom retry loop layered on the SDK's 30-second budget. Worst case is roughly 40 rows times 2 calls times 2 seconds, about 2.7 minutes. |
| T-jqx-06 | Denial of service | billing run availability via Supabase | high | mitigate | Every store function inherits the `get_client()`-returns-`None` contract, catches its own errors, and never raises. Bulk reads only — per-row reads caused the 2026-04-24 retry-exhaustion incident. An unapplied migration degrades to the no-baseline path. |
| T-jqx-07 | Elevation of privilege | `billing_audit` schema surface | medium | mitigate | Schema ADDITION only: two new tables plus `service_role` grants appended to `schema.sql`. No RLS, policy, or column change to any existing table. The pipeline executes no DDL; Juan applies it by hand. |
| T-jqx-SC | Tampering | package-manager installs | low | accept | No new third-party packages. `smartsheet-python-sdk==4.3.0` and `supabase` are already declared and in use, so no install task exists in this plan and no legitimacy gate is triggered. If any task ever adds a `pip install`, run the Package Legitimacy Gate first. |
</threat_model>

<verification>
1. `pytest tests/test_snapshot_drift_audit.py -v` — the new suite, all cases green.
2. `pytest tests/ -v` — full suite, no regressions against the pre-change count.
3. `python -m py_compile generate_weekly_pdfs.py pipeline/snapshot_drift.py billing_audit/snapshot_store.py audit_billing_changes.py`.
4. Diff guard: `git diff --name-only -- pipeline/grouping.py pipeline/excel.py` returns nothing.
5. Seam guard: `git diff -U0 -- pipeline/orchestrate.py | grep -c '^@@'` is at most 3 (import, seam, summary merge).
6. Schema guard: the `billing_audit/schema.sql` diff is append-only — no hunk touches an existing object definition.
7. Off-switch equivalence: with `SNAPSHOT_DRIFT_AUDIT_ENABLED=false` and `SNAPSHOT_DRIFT_HOLD_ENABLED=false`, a `TEST_MODE=true` run produces the same `run_summary.json` key set and the same generated filenames as before the change.
8. Live operator check (`<human-check>` on Task 3): confirm cell-history entry ordering (A1) and the literal automation identity email (A4) against one known-drifted row before enabling the hold gate in the workflow.
</verification>

<success_criteria>
- Drift on already-billed rows is detected with zero extra Smartsheet API calls; only week-movers cost history lookups, capped and paced.
- Automation self-fires are held to the prior week with BOTH date fields rewritten; the held row still appears in the workbook day-tables and the prior week's content hash is unchanged.
- Manual edits are never held. Unclassifiable drift is never held. Both are still recorded.
- Only automation self-fire holds escalate `risk_level`.
- Both kill-switches off reproduces today's behaviour exactly; the hold gate ships off.
- No Supabase DDL is executed by the pipeline; no new mutating Smartsheet write exists.
- Zero diff hunks inside `pipeline/grouping.py` and `pipeline/excel.py`.
- Full pytest suite green; `py_compile` clean; a dated ledger entry is appended.
</success_criteria>

<output>
Create `.planning/quick/260812-jqx-snapshot-date-drift-audit-detect-snapsho/260812-jqx-SUMMARY.md` when done.
</output>
