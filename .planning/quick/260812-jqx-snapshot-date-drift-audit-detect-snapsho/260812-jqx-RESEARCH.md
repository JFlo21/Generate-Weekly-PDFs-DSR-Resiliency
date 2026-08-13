# Quick Task 260812-jqx: Snapshot-Date Drift Audit — Research

**Researched:** 2026-08-12
**Domain:** Production Python billing pipeline (Smartsheet → grouping → Excel → attachment) + `billing_audit` Supabase shadow layer
**Confidence:** HIGH on the in-repo seams (all cited files opened this session); MEDIUM on Smartsheet cell-history *runtime* semantics (SDK source read; live API response shape not exercised — no cell-history call exists in this repo today)
**Mode:** Feasibility-first (quick task). No domain survey.

---

<user_constraints>
## User Constraints (from CONTEXT.md — LOCKED)

### Locked Decisions

- **Hold prior week + flag HIGH.** The pipeline keeps billing the row under its
  previously-billed week (ignores the drifted date for grouping), flags HIGH on the
  billing audit sheet + Supabase, and reports which row to repair upstream. Files stay
  correct; nothing silently moves weeks.
- Manual edits are NEVER blocked or held — they flow through normally and are
  shadow-logged.
- Unclassifiable drift (history unavailable, cap exhausted, API error) must NOT hold the
  row — flag it as `unclassified` and let it flow (fail-open on gating, fail-closed on
  logging).
- **Only week-movers, capped.** Spend history lookups ONLY on rows whose computed billing
  week differs from the previously-billed week for that row, with a per-run cap (~40 rows)
  and pacing (~2s between calls; ~2 calls per row: Snapshot Date + Units Completed?).
  Everything else costs zero extra API calls.
- Classifier signature: a Snapshot Date write by `automation@smartsheet.com` with NO
  `Units Completed?` change within ±2 minutes = automation self-fire. Otherwise
  manual/legitimate.
- **New additive Supabase table** (e.g. `snapshot_drift` / provenance: sheet_id, row_id,
  WR, CU, prior snapshot date, new snapshot date, prior billed week, new week, changed_by,
  classification, run_id, detected_at). Written additively by the pipeline; the existing
  `billing_audit` tables stay untouched.
- Approved as a Supabase schema ADDITION only — no RLS/policy/schema changes to existing
  tables. Migration must be reviewed by Juan before apply (protected area).

### Claude's Discretion

- Exact table/column naming and index choices.
- Flag format on the billing audit sheet (reuse the existing `_log_to_audit_sheet` shape
  from `audit_billing_changes.py`).
- Env-var kill-switches and defaults (mirror RATE_SANITY pattern: default enabled for
  detection/logging; the HOLD gate gets its OWN kill-switch so gating can be disabled
  independently of detection).
- Whether v1 per-row provenance is seeded from the first run that sees a row (no history
  backfill required).

### Deferred Ideas (OUT OF SCOPE)

None declared in CONTEXT.md. The Smartsheet-UI automation fix (trigger → "when Units
Completed? changes to Checked" + condition "Snapshot Date is blank") is Juan's, not this
task's.
</user_constraints>

---

## Summary

All six research questions resolve to **concrete, additive seams that already exist**. The
single biggest finding is that the audit already runs *before* grouping in the same
function, so both the drift detector and the week override fit in one un-contended window
(`pipeline/orchestrate.py:578-582`) with **zero edits inside `pipeline/grouping.py`**.

Two findings materially change the plan versus what the task description assumes:

1. **`_log_to_audit_sheet` writes nothing.** It is a no-op placeholder that builds a dict
   and logs a success message. "Flag on the billing audit sheet" is therefore not a
   reuse — it is either (a) log-only parity with today, or (b) a NEW mutating Smartsheet
   write to `AUDIT_SHEET_ID`, which is a protected-area change needing Juan's approval and
   `SKIP_UPLOAD` gating.
2. **Rewriting `Weekly Reference Logged Date` alone silently deletes the row from the
   Excel body.** `pipeline/excel.py` buckets rows by `Snapshot Date` and drops anything
   outside the group's Monday–Sunday window. The hold override must rewrite **both**
   fields.

**Primary recommendation:** Implement as a pre-grouping row transform inserted at
`pipeline/orchestrate.py:578`, backed by a new `billing_audit.snapshot_provenance` table
(PK `sheet_id,row_id`) seeded silently on first sight; rewrite BOTH `Weekly Reference
Logged Date` and `Snapshot Date` on held rows; keep the audit-sheet surface log-only in v1
and treat a real `AUDIT_SHEET_ID` write as a separate approval-gated follow-up.

---

## Q1 — Supabase Shadow Layer: What Exists, and the Additive Path

### What the `billing_audit` package is

| File | Lines | Role |
|---|---|---|
| `billing_audit/client.py` | 739 | `get_client()`, `with_retry()`, feature-flag reads, run-global kill switch |
| `billing_audit/writer.py` | 1264 | `freeze_row`, `emit_run_fingerprint`, `lookup_group_hash`, `upsert_group_hash`, `prefetch_attribution` |
| `billing_audit/schema.sql` | 330 | Documentation-grade DDL, **manually applied** |
| `billing_audit/fingerprint.py` | 62 | assignment fingerprint |

**Credentials + disable conditions** [VERIFIED: `billing_audit/client.py:221-294`]. `get_client()`
returns `None` — never raises — when any of these hold. Verbatim from `:259-260`:

```python
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
```

plus `TEST_MODE` (`:251`), missing `supabase` package (`:270`), construction failure
(`:281`), and a run-global PostgREST kill (`:243-244`):

```python
    if _global_disable_reason is not None:
        return None
```

That `None`-not-raise contract is the fail-safe posture every new writer must inherit:
**a misconfigured billing_audit integration must never break the billing run** (ledger
`[2026-04-24 10:50]`).

### Tables the pipeline owns vs. tables the data team owns

[VERIFIED: `billing_audit/schema.sql:32,63,146` — verbatim object names]

```sql
CREATE TABLE IF NOT EXISTS billing_audit.feature_flag (
CREATE TABLE IF NOT EXISTS billing_audit.pipeline_run (
CREATE TABLE IF NOT EXISTS billing_audit.group_content_hash (
```

`attribution_snapshot` and the `freeze_attribution` / `lookup_attribution` /
`lookup_attribution_bulk` RPCs are **NOT** in this file — the body lives in the Supabase
project and is owned by the data team [VERIFIED: `billing_audit/schema.sql:211-218`].

### Migration mechanism — there is none (deliberately)

[VERIFIED: `billing_audit/schema.sql:4-8`, verbatim]

> `-- This file is documentation-grade SQL. It is NOT auto-applied by`
> `-- the Python pipeline — apply it manually in the Supabase SQL`
> `-- Editor (Project Settings → SQL Editor) the first time you wire`
> `-- the ``billing_audit`` integration to a new project, and again`
> `-- whenever this file is updated to add a column.`

The pipeline never executes DDL. **The additive path for a new `snapshot_drift` table is
therefore: append a `CREATE TABLE IF NOT EXISTS` block to `schema.sql`, and Juan applies it
in the SQL Editor + confirms `billing_audit` is in "Exposed schemas" + reloads the
PostgREST cache** [VERIFIED: `billing_audit/schema.sql:10-16`]. This matches the CONTEXT
decision exactly ("Migration must be reviewed by Juan before apply").

Until the DDL is applied, the reader must degrade the same way `group_content_hash` does —
surface as a fetch failure and fall through to prior behaviour, never regenerate-block
[VERIFIED: `billing_audit/schema.sql:139-145`].

### Is there per-row provenance today?

**Partially — and it is not usable as a prior-billed-week oracle.**

`freeze_row` upserts one row per `(wr, week_ending, smartsheet_row_id)` into
`attribution_snapshot`, first-write-wins [VERIFIED: `billing_audit/writer.py:466-472`; PK
shape verbatim at `billing_audit/schema.sql:205`: "PRIMARY KEY shape: (wr, week_ending,
smartsheet_row_id)"]. Params sent verbatim [VERIFIED: `billing_audit/writer.py:550-553`]:

```python
    params = {
        "p_wr": wr,
        "p_week_ending": week_ending.isoformat(),
        "p_smartsheet_row_id": row_id,
```

Three reasons it cannot answer "what week was this row billed under?":

1. The read RPC **takes `p_week_ending` as an input parameter** [VERIFIED:
   `billing_audit/schema.sql:225-228`] — you must already know the week to look it up.
2. It stores personnel, not dates — no snapshot date column in the Python contract
   [VERIFIED: `billing_audit/schema.sql:206-209`: "Columns the reader depends on: `helper
   TEXT`, `helper_dept TEXT`, `source_run_id TEXT`"].
3. Writes are gated on a flag seeded **FALSE** [VERIFIED: `billing_audit/schema.sql:44-48`,
   verbatim seed values `('write_attribution_snapshot', FALSE)`,
   `('emit_assignment_fingerprint', FALSE)`], and only fire for `Units Completed?`-checked
   rows [VERIFIED: `billing_audit/writer.py:533`].

**Conclusion: a new table is required.** See Q5.

### Model to copy for the new reader/writer

`lookup_group_hash` / `upsert_group_hash` [VERIFIED: `billing_audit/writer.py:1144,1222`]
are the closest analogue: plain table read/write (no RPC, no data-team coordination),
`with_retry`-wrapped, fail-safe on error. Copy that shape rather than the RPC shape — an
RPC would require a Supabase Dashboard function deploy outside this repo.

---

## Q2 — The Hold-Prior-Week Seam (riskiest part)

### Where a row's billing week is computed — one place

[VERIFIED: `pipeline/grouping.py:438-467`, verbatim]

```python
    for r in rows:
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')
...
            # Parse the Weekly Reference Logged Date - this IS the week ending date
            week_ending_date = excel_serial_to_date(log_date_str)
            if week_ending_date is None:
                logging.warning(f"Could not parse Weekly Reference Logged Date '{log_date_str}' for WR# {wr_key}. Skipping row.")
                continue
            week_end_for_key = week_ending_date.strftime("%m%d%y")
```

`Snapshot Date` is **not** read for week computation in `group_source_rows` — only for the
AEP-billable cutoff [VERIFIED: `pipeline/grouping.py:774`]. Snapshot → Sunday snapping
happens *in Smartsheet*, not in Python (ledger `[2026-08-12 13:40]`: "`Weekly Reference
Logged Date` = Snapshot Date snapped to Sunday"). Every variant key, and `__week_ending_date`
stamped at `pipeline/grouping.py:1167`, derives from those two locals.

### The additive hook point

`group_source_rows` is called **once**, and the audit already runs **before** it
[VERIFIED: `pipeline/orchestrate.py:553` and `:582`, verbatim]:

```python
                    audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
...
            groups = group_source_rows(all_rows)
```

**Concrete hook: insert the drift pass between `pipeline/orchestrate.py:577` (the audit
`else:` branch close) and `:580` (`logging.info("📂 Grouping data...")`).** A function
`apply_snapshot_drift_holds(all_rows, source_sheets, client, session_start) -> list[dict]`
placed there:

- sees the same `all_rows` the audit just inspected and the same `source_sheets`
  (which carry `column_mapping` — see Q3);
- runs upstream of **all** grouping passes, including the five earlier
  `Weekly Reference Logged Date` pre-pass readers at `pipeline/grouping.py:170, 234, 289,
  360, 417`, so VAC-claim reconciliation and the main loop stay mutually consistent;
- requires **zero** edits inside `pipeline/grouping.py`.

### Double-count: solved structurally, no dedup logic needed

Because the transform rewrites the row's own fields before grouping, `week_ending_date` is
computed once from the corrected value — the row can only land in W1's groups. W2 never
sees it. `history_key` follows automatically, since it is built from the group, not the row
[VERIFIED: `pipeline/orchestrate.py:1461`, verbatim]:

```python
                history_key = f"{wr_num}|{week_raw}|{variant}|{identifier}"
```

The full change-detection key (WR, week, variant, foreman, dept, job) is preserved
untouched.

### ⚠️ CRITICAL: the override MUST rewrite BOTH fields

`generate_excel` buckets rows by `Snapshot Date` and **silently drops** any row whose
snapshot falls outside the group's Monday–Sunday window [VERIFIED: `pipeline/excel.py:711-736`,
verbatim]:

```python
    if week_ending_date:
        # Calculate Monday of the week (6 days before Sunday)
        week_start_date = week_ending_date - timedelta(days=6)  # Monday of that week
        week_end_date = week_ending_date  # Sunday of that week
...
    for row in group_rows:
        snap = row.get('Snapshot Date')
...
            # Include snapshot dates that fall within the Monday-Sunday range
            if week_start_date and week_end_date:
                if week_start_date <= dt <= week_end_date:
                    date_to_rows[dt].append(row)
```

A row held into W1 while still carrying a W2 `Snapshot Date` passes grouping, counts toward
group membership, and is then **excluded from every day-table in the workbook** — a silent
under-bill. The transform must set both:

- `r['Weekly Reference Logged Date'] = <prior billed week>` — controls grouping
- `r['Snapshot Date']  = <prior snapshot date>` — controls Excel day-bucketing
- preserve the drifted originals under private keys (e.g. `__drifted_snapshot_date`,
  `__drifted_week`, `__drift_classification`) for logging / Supabase / audit.

### Hash interaction — rewriting both is also what *stops the churn*

`Snapshot Date` is inside the content hash in **both** legacy and extended modes, and in the
sort key [VERIFIED: `pipeline/change_detection.py:115` (sort), `:143` (legacy row_data),
`:169` (extended `row_fields`), verbatim examples]:

```python
        str(x.get('Snapshot Date', '')),
...
                f"{row.get('Snapshot Date', '')}"
...
            str(row.get('Snapshot Date', '') or ''),
```

So holding the week while leaving the drifted snapshot in place would still perturb W1's
hash and force a pointless regeneration every run. Restoring both fields makes W1's hash
**byte-stable** — the drift becomes fully invisible to the billing artifact, which is
exactly the CONTEXT goal ("Files stay correct; nothing silently moves weeks").

**Verdict for Q2: achievable additively, one insertion point, zero protected-internals
edits — conditional on rewriting both fields.**

---

## Q3 — Cell History Mechanics

### There is no existing cell-history call in this repo

`_selective_cell_history_enrichment` is a stub that makes **no API call** [VERIFIED:
`audit_billing_changes.py:683-690`, verbatim]:

```python
            # Minimal sample: we just record existence of history (actual per-cell diff can be expanded later)
            history_meta = {"sheet_id": sheet_id, "row_id": row_id, "work_request": wr}
            try:
                # We avoid deep iteration to limit API usage; could call cell history endpoints if needed.
                history_meta["history_available"] = True
```

`_detect_suspicious_changes` likewise only reads sheet discussions, not cell history
[VERIFIED: `audit_billing_changes.py:461`]. **This is greenfield.**

### SDK method (4.3.0 pinned)

[VERIFIED: `requirements.txt:9` — `smartsheet-python-sdk==4.3.0`; installed 4.3.0 confirmed]
[VERIFIED: installed `smartsheet/cells.py`, signature read via `inspect` this session]

```python
Cells.get_cell_history(self, sheet_id, row_id, column_id,
                       include=None, page_size=None, page=None,
                       include_all=None, level=None)
    -> Union[IndexResult[CellHistory], Error]
    # GET /sheets/{sheet_id}/rows/{row_id}/columns/{column_id}/history
```

`CellHistory` attributes [VERIFIED: `smartsheet.models.cell_history.CellHistory.__dict__`
inspected this session]: `_modified_at`, `_modified_by`, plus the full `Cell` surface
(`_value`, `_display_value`, `_column_id`, `_object_value`, …).

**It takes a `column_id`, not a column name.** Getting `Snapshot Date`'s and
`Units Completed?`'s column ids is the pre-work.

### Row + column identity are both available at the seam

Every row dict carries its provenance [VERIFIED: `pipeline/fetch.py:315-331`, verbatim]:

```python
                    # Attach provenance metadata for audit (used to fetch selective cell history later)
                    if row_data:
                        row_data['__sheet_id'] = source['id']
...
                        row_data['__source_sheet_id'] = source['id']
                        row_data['__row_id'] = row.id
```

Column ids come from the source-sheet dict [VERIFIED: `pipeline/discovery.py:615`, verbatim]:

```python
                return {'id': sid,'name': sheet.name,'column_mapping': mapping}
```

with `mapping['Snapshot Date']` assigned at `pipeline/discovery.py:438` (`mapping['Snapshot
Date'] = s_exact.id`) plus keyword and fuzzy fallbacks at `:448` and `:489`. `source_sheets`
is in scope at the seam — it is passed to the audit at `pipeline/orchestrate.py:553`.

⚠️ `'Units Completed?'` presence in `column_mapping` is **per-sheet and not guaranteed**
(the Snapshot Date mapping itself is explicitly optional — `sheet_has_snapshot_date_column`
guard at `pipeline/fetch.py:276`). The classifier must check both column ids exist for the
row's sheet and emit `unclassified` (never hold) when either is missing. [ASSUMED that
`Units Completed?` maps on all currently-discovered sheets — not verified per sheet.]

### Pagination + per-call cost

`include_all=True` returns the whole history for one cell in one request; `page_size`/`page`
paginate. Snapshot-Date cell histories are short (one entry per automation fire), so
`include_all=True` = 1 request per cell. **2 requests per candidate row** (Snapshot Date +
Units Completed?), matching the CONTEXT budget. [CITED: SDK docstring in
`smartsheet/cells.py`, read this session.]

[ASSUMED] Ordering of `IndexResult.data` (oldest-first vs newest-first) and the exact
`modified_by` shape (`User` object with `.email`) are not verified against the live API —
no call exists in-repo to copy. The classifier must sort by `modified_at` itself and read
the email defensively (`getattr(mb, 'email', None) or str(mb)`).

### 429 behaviour — the SDK's retry budget is 30 seconds, not unlimited

[VERIFIED: installed `smartsheet/smartsheet.py`, read via `inspect` this session]

- `Smartsheet.__init__(..., max_retry_time=30, ...)` — **default 30 seconds total**.
- `request_with_retry` retries only when the server sets `shouldRetry` on the error result:
  `if native.result.should_retry:` … `backoff = self._user_calc_backoff.calc_backoff(...)`;
  `if backoff < 0: break`.
- `DefaultCalcBackoff.calc_backoff` = `(2 ** previous_attempts) + random.random()`, and
  returns `-1` (drop out of the retry loop) once `total_elapsed_time + backoff >
  self._max_retry_time`.

So a sustained 30-req/min throttle exhausts the SDK's budget after roughly 4 attempts
(2+4+8+16 ≈ 30s) and then raises. **Self-pacing (~2s between calls, per the CONTEXT
decision) is mandatory — the SDK will not ride out the cell-history rate limit for you** —
and any exhausted-retry exception must map to `unclassified` (flag, no hold), per the
locked fail-open rule.

---

## Q4 — Audit Outputs

### `_log_to_audit_sheet` writes NOTHING today

[VERIFIED: `audit_billing_changes.py:586-617`, verbatim tail]

```python
            # Placeholder: actual Smartsheet row creation would map these keys to column IDs.
            
            # Note: Actual implementation would require proper Smartsheet row creation
            self.logger.info("📋 Audit results logged to audit sheet")
```

It builds `audit_row` (`:596-610`) with keys `Audit Timestamp`, `Risk Level`,
`Total Issues`, `Sheets Audited`, `Rows Audited`, `Anomalies`, `Unauthorized Changes`,
`Data Issues`, `Risk Direction`, `Risk Level Δ`, `Issues Δ`, `Issues Δ %`, `Enriched Rows`
— then discards it. It is gated on `AUDIT_SHEET_ID` [VERIFIED: `audit_billing_changes.py:125`
`self.audit_sheet_id = os.getenv("AUDIT_SHEET_ID")` and `:580` `if self.audit_sheet_id:`].

**Planning implication (do not skip this):** "flag drift on the billing audit sheet" has two
readings and they have very different risk profiles.

| Option | Work | Risk |
|---|---|---|
| **A (recommended v1)** — add drift keys to the existing `audit_row` dict + a per-run INFO log line | trivial, additive, zero API surface | none; but visibility is log-only, same as every other audit metric today |
| **B** — implement a real `Sheets.add_rows` against `AUDIT_SHEET_ID` | new mutating Smartsheet write | **protected area.** Needs Juan's explicit approval, `SKIP_UPLOAD` gating (cf. quick task 260722-nst, which gated the 6th mutating call site on `SKIP_UPLOAD`), and column-id discovery for the audit sheet. Should be its own task. |

The Supabase shadow layer (Q1/Q5) is the *actual* durable, queryable flag surface in v1.

### How 260812-isx folded its findings in — the pattern to copy

[VERIFIED: `audit_billing_changes.py` read this session]

1. New results bucket declared in the `audit_results` literal — `:185`
   `"rate_sanity_mismatches": [],`
2. New detector method — `:358` `def _detect_rate_sanity_mismatches(self, rows: List[Dict]) -> List[Dict]:`
3. Wired as a numbered step in `audit_financial_data` between data-consistency and
   suspicious-change detection — `:198-206` (comment verbatim: "2.5 Report-only rate-sanity
   check (260812-isx): Units Total Price vs New Rates rate x Quantity. Never mutates rows,
   pricing, grouping, filenames, hashes, or upload behavior.")
4. Kill-switch read **per call**, not at import — `:376`
   `if os.getenv("RATE_SANITY_AUDIT_ENABLED", "true").lower() != "true":`
5. Summary keys added — `:493-496` `"total_rate_sanity_mismatches"`, `"rate_sanity_skipped"`
6. Folded into `total_issues` → drives `risk_level` — `:502-507`:

```python
        total_issues = (
            summary["total_anomalies"]
            + summary["total_unauthorized_changes"]
            + summary["total_data_issues"]
            + summary["total_rate_sanity_mismatches"]
        )
```

with thresholds `0 → LOW`, `<=3 → MEDIUM`, `else HIGH` (`:509-517`).

### ⚠️ Known inconsistency the drift bucket must navigate

`_generate_audit_summary`'s `total_issues` **includes** rate-sanity (`:502-507`), but two
other "total issues" computations **do not**:

- `_log_to_audit_sheet` `"Total Issues"` — [VERIFIED: `audit_billing_changes.py:599`]
  `summary.get("total_anomalies",0) + summary.get("total_unauthorized_changes",0) + summary.get("total_data_issues",0)`
- `_compute_trend` cur/prev issues — [VERIFIED: `audit_billing_changes.py:638-639`], same
  3-term sum
- `audit_financial_data`'s risk-history entry — [VERIFIED: `audit_billing_changes.py:244`],
  same 3-term sum

**Recommendation:** fold **only automation-self-fire holds** into `_generate_audit_summary`'s
`total_issues` (so 4+ self-fires trip HIGH, matching the locked "flag HIGH" decision), and
keep `manual` + `unclassified` drift as separate reported counters that do **not** inflate
risk level. Otherwise a routine batch of legitimate manual edits would drive the whole run
to HIGH and desensitise the signal. Do not "fix" the three-way total inconsistency in this
task — it is pre-existing and out of scope.

---

## Q5 — Prior-Billed-Week Provenance: the v1 Seed

No usable oracle exists (Q1). Cleanest v1, aligned with the locked decision:

**New table `billing_audit.snapshot_provenance`, PK `(sheet_id, row_id)`**, appended to
`billing_audit/schema.sql` for Juan to apply:

| column | type | note |
|---|---|---|
| `sheet_id` | `BIGINT NOT NULL` | from `row['__source_sheet_id']` |
| `row_id` | `BIGINT NOT NULL` | from `row['__row_id']` |
| `wr` | `TEXT` | sanitized, per `_sanitized_wr` (`billing_audit/writer.py:418`) |
| `cu` | `TEXT` | |
| `snapshot_date` | `DATE` | last snapshot the row was billed under |
| `billed_week` | `DATE` | last week the row was billed under |
| `run_id` / `first_seen_at` / `last_seen_at` | `TEXT` / `TIMESTAMPTZ` | audit metadata |

Drift detection then reduces to: `current_week != provenance.billed_week` → candidate.

`snapshot_drift` (the event log from CONTEXT) is a **second, append-only** table keyed
`(sheet_id, row_id, detected_at)` carrying prior/new snapshot + week, `changed_by`,
`classification ∈ {automation_self_fire, manual, unclassified}`, `held BOOLEAN`, `run_id`.
Splitting state (provenance) from events (drift) keeps the upsert idempotent and the audit
trail complete.

**First-run behaviour (mandatory): silent.** Absent baseline row ⇒ not drift ⇒ **no history
call, no flag, no hold** — just seed the provenance row. This mirrors the existing fail-safe
posture for `group_content_hash` [VERIFIED: `billing_audit/schema.sql:139-145`, verbatim:
"the pipeline falls back to hash_history.json and behaves exactly as before (fail-safe to
regenerate)"]. Same rule when the table is absent / PostgREST cache not reloaded / creds
missing: `get_client()` returns `None` → whole feature no-ops.

**Read pattern — bulk, never per-row.** Per-row Supabase reads are what caused the
2026-04-24 log-spam / retry-exhaustion incident (ledger `[2026-04-24 10:50]`). Copy
`prefetch_attribution` [VERIFIED: `billing_audit/writer.py:840`] / the
`lookup_attribution_bulk(jsonb)` bulk shape [VERIFIED: `billing_audit/schema.sql:299`] — one
select for all `(sheet_id,row_id)` in the run, then an in-memory dict lookup.

**Write timing:** upsert provenance **after** grouping succeeds, in the same phase where
`freeze_row` already iterates group rows [VERIFIED: `pipeline/orchestrate.py:1626`, `:1664`],
or as one bulk upsert at end-of-run. Never inside the per-row loop as individual calls.

---

## Q6 — Budget / Ordering

**Config** [VERIFIED: `pipeline/config.py:106`, verbatim]:

```python
TIME_BUDGET_MINUTES = int(os.getenv('TIME_BUDGET_MINUTES', '0') or 0)
```

and [VERIFIED: `pipeline/config.py:33`] `GITHUB_ACTIONS_MODE = os.getenv('GITHUB_ACTIONS') == 'true'`.

**Anchor** [VERIFIED: `pipeline/orchestrate.py:416`]: `session_start = datetime.datetime.now()`.

**Canonical pre-flight guard to copy** [VERIFIED: `pipeline/orchestrate.py:683-685`, verbatim]:

```python
            if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
                _pre_elapsed_min = (datetime.datetime.now() - session_start).total_seconds() / 60.0
                _remaining_min = TIME_BUDGET_MINUTES - _pre_elapsed_min
```

(the mid-loop stop variant is at `:1337-1344`).

The drift seam sits at ~`:578` — **before** both attachment pre-fetch phases (`:683`, `:879`)
and long before the generation loop. Budget consumed by then is only discovery + fetch +
audit, so remaining budget is at its maximum. Recommended shape, mirroring the
`ATTACHMENT_PREFETCH_MAX_MINUTES` family documented in `CLAUDE.md`:

- `SNAPSHOT_DRIFT_AUDIT_ENABLED` (default `true`) — detection + Supabase logging
- `SNAPSHOT_DRIFT_HOLD_ENABLED` (default **`false`**, its own switch per the locked
  discretion note) — the gating action only
- `SNAPSHOT_DRIFT_MAX_ROWS` (default `40`) — per-run classification cap
- `SNAPSHOT_DRIFT_PACE_SEC` (default `2.0`) — inter-call sleep
- `SNAPSHOT_DRIFT_MAX_MINUTES` (default `5`) — phase sub-budget **and** the pre-flight
  threshold: if `_remaining_min < SNAPSHOT_DRIFT_MAX_MINUTES`, skip classification entirely
  → every candidate becomes `unclassified` → flagged, never held

Budget arithmetic: 40 rows × 2 calls × 2 s ≈ 160 s ≈ 2.7 min, leaving headroom inside a 5-min
sub-budget for SDK backoff. Well inside the 30 req/min endpoint limit (≈30 req/min actual).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Supabase retry / error classification | a new retry loop | `billing_audit.client.with_retry` + `_classify_postgrest_error` | run-global kill codes + Sentry breadcrumbs already tuned by the 2026-04-24 incident |
| Supabase kill-switch | a new env flag for credentials | `get_client()` returning `None` | single fail-safe contract every writer inherits |
| WR sanitization | `str(wr).split('.')[0]` inline | `billing_audit/writer.py:418` `_sanitized_wr` | collision-quarantine rules live there |
| Checkbox truthiness | `bool(value)` | `writer._is_checked` / `pipeline.utils.is_checked` | Smartsheet returns str/bool/1 variably |
| Date coercion | `dateutil.parser` directly | `excel_serial_to_date` / `writer._coerce_week_ending` | Excel serials + Smartsheet strings both appear |
| Rate-limit backoff | a sleep-retry wrapper on Smartsheet | SDK `request_with_retry` **plus** explicit pacing | SDK covers `shouldRetry` only, and only for 30 s |

---

## Common Pitfalls (phase-specific)

1. **Rewriting only the week field.** Row silently disappears from the Excel body
   (`pipeline/excel.py:722-736`). Rewrite `Snapshot Date` too. *Warning sign:* group row
   count > sum of day-table row counts.
2. **Running the transform after grouping.** The five pre-pass readers
   (`pipeline/grouping.py:170,234,289,360,417`) would see the drifted value while the main
   loop sees the held value → VAC-claim reconciliation divergence. Insert at
   `orchestrate.py:578`, never later.
3. **Treating an API error as "not a self-fire" and holding anyway.** Locked rule: fail-open
   on gating. Any exception, missing column id, cap exhaustion, or budget shortfall ⇒
   `unclassified` ⇒ flag, no hold.
4. **Per-row Supabase reads.** Reproduces the 2026-04-24 log-spam/retry-exhaustion incident.
   Bulk only.
5. **Flipping risk_level HIGH on manual-edit drift.** Fold only automation self-fires into
   `total_issues`.
6. **Assuming `_log_to_audit_sheet` writes to Smartsheet.** It does not.
7. **First run holding everything.** No baseline ⇒ everything looks like drift if the
   absent-baseline case isn't explicitly a no-op.

---

## Project Constraints (from CLAUDE.md)

- `generate_weekly_pdfs.py` / the pipeline package is **production-critical**; additive,
  surgical changes only. Preserve the Smartsheet → Excel → Smartsheet attachment pipeline.
- Change-detection key `(WR, week, variant, foreman, dept, job)` — never shorten.
- `safe_merge_cells()` only; never write `oddFooter.right.text`.
- `PARALLEL_WORKERS ≤ 8` (Smartsheet 300 req/min).
- Never use the Smartsheet `@cell` function in Python or API payloads.
- `TIME_BUDGET_MINUTES` must stay strictly below the workflow's `timeout-minutes`.
- PEP 8, type hints, 4-space indent, ≤79 char lines, PEP 257 docstrings.
- Validate with `pytest tests/ -v` and `python -m py_compile generate_weekly_pdfs.py` before push.
- Append a dated `[YYYY-MM-DD HH:MM]` entry to `memory-bank/living-ledger.md` in the same PR.
- **Protected areas requiring Juan's approval:** Supabase schema/RLS changes (the new DDL —
  already acknowledged in CONTEXT), and any new mutating Smartsheet write (audit-sheet
  Option B).

---

## Package Legitimacy Audit

**N/A — this task adds no new third-party packages.** Every dependency it needs is already
declared and in use: `smartsheet-python-sdk==4.3.0` [VERIFIED: `requirements.txt:9`] and the
`supabase` client already consumed by `billing_audit/client.py:270` (`from supabase import
create_client`). No `pip install` step should appear in the plan; if one does, run the
legitimacy gate then.

---

## Validation Architecture

| Property | Value |
|---|---|
| Framework | pytest (per `CLAUDE.md`; `tests/` suite, ~1101 tests at Phase 09 close) |
| Quick run | `pytest tests/test_snapshot_drift_audit.py -v` (new file) |
| Full suite | `pytest tests/ -v` |
| Syntax gate | `python -m py_compile generate_weekly_pdfs.py` |

Wave-0 gaps: `tests/test_snapshot_drift_audit.py` does not exist. Model it on
`tests/test_rate_sanity_audit.py` (the 260812-isx RED-first suite, which instantiates
`BillingAudit(client=None, skip_cell_history=True)` at `:51` — a working no-network fixture
pattern) and on `tests/test_billing_audit_shadow.py` for the Supabase writer mocks.

Minimum RED-first cases: (1) no baseline ⇒ no drift, no history call, provenance seeded;
(2) week unchanged ⇒ zero history calls; (3) automation self-fire ⇒ held + both fields
rewritten + HIGH; (4) manual edit ⇒ flagged, NOT held; (5) API raises ⇒ `unclassified`, not
held; (6) cap/budget exhausted ⇒ `unclassified`; (7) kill-switches off ⇒ byte-identical
prior behaviour; (8) held row survives `generate_excel`'s Monday–Sunday snapshot filter;
(9) held row's W1 content hash is stable across the drift.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | `IndexResult[CellHistory].data` ordering and `modified_by.email` shape | Q3 | Classifier reads the wrong entry → wrong hold decision. Mitigate: sort by `modified_at` in code, read email via `getattr`. **Verify against one live cell before locking the classifier.** |
| A2 | `'Units Completed?'` is mapped in `column_mapping` on all discovered sheets | Q3 | Missing column id → classification impossible on that sheet. Mitigate: explicit presence check → `unclassified`. |
| A3 | Smartsheet cell-history endpoint limit is 30 req/min | Q3/Q6 | Sourced from the ledger `[2026-08-12 13:40]` operator note, not from Smartsheet docs this session. If lower, pacing must widen. |
| A4 | `automation@smartsheet.com` is the literal `modified_by` email for automation writes | Q3 | Classifier never matches → everything `unclassified` (fail-open, so safe but useless). Verify on one known-drifted row. |
| A5 | Snapshot-Date cell histories are short enough for `include_all=True` in one request | Q3 | Extra pages → extra requests → cap math off. Mitigate: `page_size` + read only the newest page. |

---

## FEASIBILITY VERDICT

### (a) Detection + flagging + Supabase shadow — **FEASIBLE**
Clean additive path end-to-end: seam at `pipeline/orchestrate.py:578`, provenance/event
tables appended to `billing_audit/schema.sql` (manual apply, matching the locked decision),
writer modeled on `lookup_group_hash`/`upsert_group_hash`, and the 260812-isx audit-wiring
pattern for summary/kill-switch. Detection itself costs **zero** extra API calls.
**Top risk:** `_log_to_audit_sheet` is a no-op placeholder (`audit_billing_changes.py:611-614`)
— "flag on the billing audit sheet" is log-only unless a new mutating `AUDIT_SHEET_ID` write
is built, which is a protected-area change needing Juan's approval and `SKIP_UPLOAD` gating.
Scope v1 to the Supabase surface + log line.

### (b) Automation-vs-manual classification within rate limits — **FEASIBLE-WITH-CAVEATS**
`Cells.get_cell_history(sheet_id, row_id, column_id, include_all=True)` exists in SDK 4.3.0;
`__source_sheet_id`/`__row_id` are on every row (`pipeline/fetch.py:317-331`) and column ids
are in `source['column_mapping']` (`pipeline/discovery.py:615`), both in scope at the seam.
40 rows × 2 calls × 2 s ≈ 2.7 min fits a 5-min sub-budget.
**Top risk:** entirely greenfield — no cell-history call exists in this repo to copy, and the
SDK's retry budget is only `max_retry_time=30` seconds of exponential backoff, so it will
**not** absorb the 30 req/min throttle. Self-pacing is mandatory, and A1/A4 (history ordering,
`modified_by` email shape) must be verified against one live drifted row before the classifier
is locked. Fail-open to `unclassified` keeps every unknown safe.

### (c) Hold-prior-week gating — **FEASIBLE-WITH-CAVEATS**
A genuinely narrow additive seam exists: one pre-grouping row transform at
`pipeline/orchestrate.py:578`, upstream of the single week computation at
`pipeline/grouping.py:440/463`, with **zero edits inside `grouping.py`** and no
double-count risk (the row is rewritten before it can reach any group).
**Top risk:** the override must rewrite **both** `Weekly Reference Logged Date` **and**
`Snapshot Date`. Rewriting only the week leaves the row inside the W1 group but outside
`generate_excel`'s Monday–Sunday snapshot filter (`pipeline/excel.py:711-736`), silently
deleting it from the workbook body — a worse outcome than the drift. Restoring both fields
also re-stabilises the W1 content hash (`pipeline/change_detection.py:143,169`), eliminating
regeneration churn. Ship with `SNAPSHOT_DRIFT_HOLD_ENABLED` defaulting **off**, separate from
the detection switch.

---

## Sources

### Primary (HIGH — files opened this session)
- `pipeline/orchestrate.py` (:416, :525-585, :683-685, :1337-1344, :1461, :1500, :1626-1664)
- `pipeline/grouping.py` (:425-484, :1150-1189)
- `pipeline/excel.py` (:690-749)
- `pipeline/change_detection.py` (:105-184)
- `pipeline/fetch.py` (:300-349)
- `pipeline/config.py` (:33, :106, :246-257)
- `pipeline/discovery.py` (:436-489, :615)
- `audit_billing_changes.py` (:115-266, :440-520, :580-691)
- `billing_audit/client.py` (:221-300)
- `billing_audit/writer.py` (:460-620, :840, :1144-1264)
- `billing_audit/schema.sql` (:1-250)
- `requirements.txt` (:9)
- Installed `smartsheet-python-sdk` 4.3.0 — `cells.py`, `smartsheet.py`,
  `models/cell_history.py`, `models/error_result.py` (read via `inspect` this session)
- `memory-bank/living-ledger.md` `[2026-08-12 13:40]`, `[2026-08-12 14:05]`,
  `[2026-04-24 10:50]`
- `.planning/quick/260812-jqx-.../260812-jqx-CONTEXT.md`, `.planning/STATE.md`, `CLAUDE.md`

### Not consulted
No web/Context7 lookups were needed — every question resolved against in-repo source or the
installed SDK. Smartsheet's published cell-history rate limit (A3) and the automation
`modified_by` identity (A4) remain operator-sourced, not doc-verified.

---

## Metadata

**Confidence breakdown:**
- Supabase shadow layer + additive migration path: **HIGH** — schema.sql and client/writer read verbatim
- Hold-prior-week seam + both-fields requirement: **HIGH** — grouping, orchestrate, excel, and change_detection all read at the exact lines
- Cell-history mechanics: **MEDIUM** — SDK source verified, live response shape assumed (A1, A4, A5)
- Audit-sheet output path: **HIGH** — placeholder status verified verbatim
- Rate-limit numbers: **MEDIUM** — SDK backoff verified; 30 req/min endpoint limit is operator-sourced (A3)

**Research date:** 2026-08-12
**Valid until:** 2026-09-11 (stable in-repo domain; re-verify if the SDK pin or `billing_audit/schema.sql` changes)
