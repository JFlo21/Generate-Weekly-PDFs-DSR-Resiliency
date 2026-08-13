# Quick task 260813-nhn — Research

**Researched:** 2026-08-13
**Domain:** Supabase/PostgREST bulk read (RPC), audit scope-gate parity, direct unit coverage
**Confidence:** HIGH (all claims from in-repo `Read` this session + installed-package
introspection + one official PostgREST docs fetch)

---

## Summary

Three independent follow-ups, one shared root cause behind (A): the billing-audit shadow
layer was sized against the *filtered/grouped* row count (~550) but actually runs against
the **unfiltered `all_rows` set (~199,717 in the 2026-08-12 live dry run)**. At that scale
`fetch_snapshot_provenance`'s two-`.in_` GET is a multi-megabyte URL that a proxy will
reject — WR-02 is not a tidy-up, it is very likely a **live silent failure**. The repo
already contains the exact fix pattern (`lookup_attribution_bulk` jsonb RPC + PGRST202
degrade probe), so (A) is a copy of a proven shape rather than a design exercise.

(B) is a one-line AND. (C) is a characterization suite that must land **before** (A) so the
refactor is guarded.

**Primary recommendation:** Land in order **B → C → A(SQL) → A(Python) → upsert-chunking**.
C-before-A is the load-bearing sequencing decision.

---

## Part A — WR-02: RPC bulk provenance read

### A.1 Current state (file:line)

| Symbol | Location | Contract |
|---|---|---|
| `fetch_snapshot_provenance(keys)` | `billing_audit/snapshot_store.py:43-127` | `(dict[(sheet,row)] , status)`; statuses `success`/`no_row`/`fetch_failure`/`unavailable`; NEVER raises |
| `upsert_snapshot_provenance(records)` | `snapshot_store.py:130-157` | `None`; `on_conflict="sheet_id,row_id"`; NEVER raises |
| `insert_snapshot_drift_events(events)` | `snapshot_store.py:160-188` | `None`; append-only insert; NEVER raises |
| `sanitized_wr` | `snapshot_store.py:31` | re-export of `writer._sanitized_wr` (`writer.py:418-429`) |
| `_PROVENANCE_COLUMNS` | `snapshot_store.py:37-40` | exactly the 9 columns of the table |

The read body (`snapshot_store.py:88-96`):

```python
client.schema("billing_audit").table(_PROVENANCE_TABLE)
    .select(_PROVENANCE_COLUMNS)
    .in_("sheet_id", sheet_ids)
    .in_("row_id", row_ids)
    .execute()
```

`get_client()` / `with_retry` semantics (`billing_audit/client.py`):
- `get_client()` → `None` on TEST_MODE, missing creds, missing `supabase`, init failure, or
  a tripped run-global kill (`client.py:221-294`, kill check at `:243-244`).
- `with_retry(fn, op=...)` — 4 attempts, `2**attempt + 0.5` backoff, per-`op` circuit
  breaker at 3 consecutive failures, run-global kill short-circuit
  (`client.py:539-739`). **It eats every exception and returns `None`** — the reason code
  is discarded (`client.py:723-739`). That is why `prefetch_attribution` needs a probe
  re-invoke to recover the code (`writer.py:907-931`).
- `_classify_postgrest_error` verdicts (verified by running it this session):
  `PGRST202 -> (is_transient=False, is_global_kill=False, 'PGRST202')`;
  `42883 -> (False, False, '42883')`. Both bail after **one** attempt — a missing function
  costs one round trip, not a retry storm. [VERIFIED: `billing_audit/client.py:310-391`,
  executed]

`schema.sql` conventions (`billing_audit/schema.sql:1-398`, read end to end):
- Header: "documentation-grade SQL … NOT auto-applied by the Python pipeline — apply it
  manually in the Supabase SQL Editor" (`:1-24`).
- Every block carries an `OPERATOR:` note ending in `NOTIFY pgrst, 'reload schema';`
  (`:244-246`, `:294-298`, `:340-347`).
- Existing RPCs: `LANGUAGE sql` + `STABLE`, no explicit `SECURITY` clause (⇒ **INVOKER**),
  no `SET search_path`, fully schema-qualified bodies, followed by
  `GRANT EXECUTE ON FUNCTION … TO service_role;` (`:257-285`, `:299-330`).
- The two jqx tables are at `:355-366` (`snapshot_provenance`, PK `(sheet_id,row_id)`,
  `GRANT SELECT, INSERT, UPDATE … TO service_role`) and `:377-398` (`snapshot_drift`, PK
  `(sheet_id,row_id,detected_at)`, index `idx_snapshot_drift_wr_detected_at`,
  `GRANT SELECT, INSERT`).
- **No RLS anywhere in the file** — WR-03 proposed `ENABLE ROW LEVEL SECURITY` on the two
  new tables (`260812-jqx-REVIEW.md:165-184`). Out of scope here; note it so Juan can apply
  it in the same manual pass if he wants.
- Documented footgun at `:248-254`: `CREATE OR REPLACE FUNCTION` **cannot change a
  function's return columns** — the 2026-05-27 incident where the multi-role
  `lookup_attribution` silently never deployed. Directly informs the return-type choice below.

### A.2 Key volume — quantify the over-fetch

`apply_snapshot_drift_holds(all_rows, …)` is called at `pipeline/orchestrate.py:587` with
the **same `all_rows`** the audit receives. `_collect_candidate_rows`
(`pipeline/snapshot_drift.py:154-177`) keeps every row with an int `__source_sheet_id`,
int `__row_id`, a `Work Request #`, and a parseable `Weekly Reference Logged Date` — i.e.
nearly all of them. The read is issued with `sorted(keyed_rows.keys())`
(`snapshot_drift.py:545-547`).

Live-run scale [VERIFIED: `memory-bank/living-ledger.md:5497`], quoted verbatim:

> `115,272/199,717 rows (58%) — history legitimately priced under OLD`

So `all_rows ≈ 199,717`, not ~550. The `~550 row IDs … ~10KB today` estimate in
`260812-jqx-REVIEW.md:152-154` is **off by ~360×** — it used the CLAUDE.md "~550 rows"
figure, which describes grouped/filtered output, not `all_rows`.

| Dimension | Value | Consequence |
|---|---|---|
| distinct `row_id`s | ~2×10⁵ | Smartsheet row ids are ~16-19 digits ⇒ `row_id=in.(…)` ≈ **3.4–4 MB of querystring** |
| distinct `sheet_id`s | ~13 (CLAUDE.md: "13+ source sheets") | ~250 B — negligible |
| transport | GET | `.in_()` → `filter()` → query param; `select()` issues **GET** [VERIFIED: `postgrest.base_request_builder.BaseFilterRequestBuilder.in_`, introspected this session] |
| practical URL ceiling | ~4–8 KB request line (nginx/Kong `large_client_header_buffers`) | request rejected long before it reaches Postgres |
| cross-product | `sheet_id ∈ S AND row_id ∈ R` matches S×R server-side | after run 1 the provenance table holds ~2×10⁵ rows whose sheet_ids are the same ~13 — the query returns **essentially the whole table** every run; `wanted` discards the surplus client-side (`snapshot_store.py:113-114`) |
| PostgREST `db-max-rows` | project-configurable | a silent truncation here degrades to `no_row` for the truncated keys ⇒ false "first-sight" seeds. Not observed, but the RPC removes the exposure by returning only matched pairs |

**Inference (MEDIUM confidence, no run log inspected):** the two-`.in_` read is already
failing in production and surfacing as `fetch_failure` → seed-only degrade
(`snapshot_drift.py:551`, `:567-575`), i.e. the drift audit never establishes a baseline.
Cheap verification: grep a recent Actions log for
`billing_audit[fetch_snapshot_provenance] RPC failed` (`client.py:723-726`). Worth doing
before planning so the fix is framed as a repair, not a polish.

**Sibling defect found (same root cause, not in the original WR-02 text):**
`upsert_snapshot_provenance` (`snapshot_store.py:143-149`) also sends **one unchunked
body**. `_provenance_record` (`snapshot_drift.py:180-201`) is 9 fields ≈ 200 B JSON; at
~2×10⁵ records that is a **~40 MB POST body**. Recommend chunking it in the same task
(details in the plan). `insert_snapshot_drift_events` is bounded by
`SNAPSHOT_DRIFT_MAX_ROWS` (40) and needs no chunking.

### A.3 supabase-py capability

`requirements.txt` pins `supabase==2.31.0` (postgrest 2.31.0). Introspected this session:

```
Client.schema(self, schema: str) -> postgrest._sync.client.SyncPostgrestClient
SyncPostgrestClient.rpc(self, func, params, count=None, head=False, get=False)
```

`Client.schema()` returns the **postgrest client itself**, which carries `.rpc(...)`.
So `client.schema('billing_audit').rpc(name, params).execute()` is supported — and is
already the shape used in production at `writer.py:900-903` and asserted by the existing
test harness docstring at `tests/test_billing_audit_shadow.py:152`.
`rpc` posts params as a **JSON body** (`method = "HEAD" if head else "GET" if get else
"POST"`), so there is no URL-length exposure. [VERIFIED: installed
`postgrest/_sync/client.py`, `supabase/_sync/client.py`]

### A.4 Recommended SQL — append to `billing_audit/schema.sql`

Place it **after** the `snapshot_drift` block (end of file), matching the file's
chronological-append convention.

```sql
-- ── lookup_snapshot_provenance_bulk (RPC) — WR-02 (260813-nhn) ───────
-- Bulk read surface for ``snapshot_store.fetch_snapshot_provenance``.
-- Replaces a two-``.in_`` GET whose querystring grew with the run's
-- row count (~2x10^5 (sheet_id,row_id) pairs on a live run -- see
-- memory-bank/living-ledger.md [2026-08-13 15:30], 199,717 rows) and
-- which matched the sheet x row CROSS-PRODUCT server-side, returning
-- essentially the whole table for the client to discard. This RPC
-- takes the pairs as a POST body (no URL limit) and matches the EXACT
-- tuples, so the response carries only rows the caller asked for.
--
-- RETURNS SETOF the table (not an explicit RETURNS TABLE list) on
-- purpose: the reader wants every column, and a composite-type return
-- sidesteps the "CREATE OR REPLACE cannot change return columns"
-- footgun documented at L248-254 (incident 2026-05-27) if a column is
-- ever added to snapshot_provenance.
--
-- SECURITY: INVOKER (no SECURITY DEFINER), matching lookup_attribution
-- and lookup_attribution_bulk above. service_role already holds SELECT
-- on the table (see the GRANT under the CREATE TABLE), so DEFINER would
-- add a privilege-escalation surface for zero benefit.
--
-- OPERATOR: apply this CREATE OR REPLACE in the Supabase SQL Editor,
-- then run `NOTIFY pgrst, 'reload schema';` (or Project Settings ->
-- API -> Reload schema cache). Until applied, the Python reader detects
-- PGRST202 ("function not found", HTTP 404) and falls back to the
-- chunked ``.in_`` select path with a one-time WARNING -- billing
-- behaviour is unaffected either way (D-07).
CREATE OR REPLACE FUNCTION billing_audit.lookup_snapshot_provenance_bulk(
    p_keys jsonb   -- e.g. '[{"sheet_id":1824542300262276,"row_id":42}, ...]'
)
RETURNS SETOF billing_audit.snapshot_provenance
LANGUAGE sql
STABLE
AS $$
    SELECT p.*
    FROM jsonb_to_recordset(p_keys) AS q(sheet_id BIGINT, row_id BIGINT)
    JOIN billing_audit.snapshot_provenance AS p
      ON p.sheet_id = q.sheet_id
     AND p.row_id   = q.row_id;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_snapshot_provenance_bulk(jsonb)
    TO service_role;
```

Design choices and why:

| Choice | Rationale |
|---|---|
| `jsonb` array of `{sheet_id,row_id}` | Exact mirror of `lookup_attribution_bulk(p_wr_weeks jsonb)` (`schema.sql:299-328`) — same `jsonb_to_recordset` + JOIN idiom, zero new concepts for the operator |
| `RETURNS SETOF <table>` | Reader wants all 9 columns; avoids the documented CREATE-OR-REPLACE return-type trap (`schema.sql:248-254`). No `DROP FUNCTION` line needed |
| `LANGUAGE sql STABLE`, INVOKER | Byte-consistent with both existing RPCs |
| `GRANT EXECUTE … TO service_role` | Same as `:285`, `:330` |
| **No** `SET search_path = ''` | Neither existing RPC sets it; body is fully schema-qualified and INVOKER, so it is not an escalation vector. Adding it would silence Supabase's `function_search_path_mutable` advisor lint — worth a separate, file-wide decision, not a one-function deviation |
| No new index | The JOIN hits the PK `(sheet_id,row_id)` (`schema.sql:365`) — already optimal |

### A.5 Python degrade path

`with_retry` returns bare `None` on failure (`client.py:723-739`), so the reason code must
be recovered with the **bounded one-shot probe** already proven at `writer.py:907-931`.
PGRST202 = HTTP **404**, "Could not find the … function in the schema cache"
[CITED: https://docs.postgrest.org/en/v13/references/errors.html]. `_classify_postgrest_error`
returns it as permanent-but-not-global-kill, so it costs exactly one attempt.

**Status vocabulary MUST stay the existing four.** Do *not* return `rpc_missing` from
`fetch_snapshot_provenance`: `pipeline/snapshot_drift.py:551` computes

```python
summary["available"] = status not in ("unavailable", "fetch_failure")
```

so any new status would be silently reported as *available*. Keep `rpc_missing` internal.

Diff outline for `snapshot_store.py` (≤79 cols, type hints, PEP 8):

```
+ _PROVENANCE_RPC = "lookup_snapshot_provenance_bulk"
+ _RPC_CHUNK_SIZE = 5000        # ~50 B/pair -> ~250 KB body
+ _FALLBACK_ROW_ID_CHUNK = 200  # ~3.4 KB of ids -> under a 4 KB request line
+ _rpc_missing_logged: bool = False   # module-level, one-time WARNING

  def fetch_snapshot_provenance(keys): ...
      # unchanged prologue: empty-keys -> ({}, 'no_row');
      # client/None + _global_disable_reason peek INSIDE the try (IN-05)
+     rows, status = _fetch_via_rpc(client, wanted)      # chunked POST
+     if status == "rpc_missing":
+         _log_rpc_missing_once()                        # WARNING, once/process
+         rows, status = _fetch_via_in_(client, wanted)  # chunked GET
      # shared tail: dict->list normalization, int() key coercion,
      # `wanted` filter, empty-result -> 'no_row', else 'success'
```

Notes that matter:
- Reuse the **existing** `op="fetch_snapshot_provenance"` for the fallback select, and use a
  **distinct** `op="lookup_snapshot_provenance_bulk"` for the RPC — op isolation is the D-13
  rule spelled out at `client.py:565-583` and `writer.py:866-868`. Without it, RPC-missing
  failures would burn the select path's breaker before the fallback ever runs.
- Keep the whole thing inside the outer `try/except Exception` (`snapshot_store.py:75,118`)
  — the IN-05 fix that `tests/test_snapshot_store.py` exists to pin.
- The **fallback must be chunked too**. An unchunked fallback simply reproduces the 3.4 MB
  URL that motivated the change. Chunk on `row_id` (the large axis); keep the small
  `sheet_id` list whole on every chunk.
- One-time log: module-level `_rpc_missing_logged` flag, mirroring
  `client._global_disable_logged` (`client.py:180`, `:410-412`). Expose a reset in the
  test helper path or reset it directly in tests.
- `int()` coercion on response keys must stay — PostgREST can serialize BIGINT as a string.

---

## Part B — P2: `RATE_RECALC_WEEKLY_FALLBACK` in the audit scope gate

### B.1 Production gate, quoted verbatim

`pipeline/fetch.py:389-403`:

```python
effective_cutoff_date, _recalc_via_fallback = (
    _resolve_rate_recalc_cutoff_date(
        row_data,
        RATE_CUTOFF_DATE,
        # See ``sheet_has_snapshot_date_column``
        # — disable the fallback on sheets
        # that never map Snapshot Date so
        # we don't re-price whole legacy
        # sheets by weekly date.
        weekly_fallback_enabled=(
            RATE_RECALC_WEEKLY_FALLBACK
            and sheet_has_snapshot_date_column
        ),
    )
)
```

`sheet_has_snapshot_date_column = 'Snapshot Date' in column_mapping` — `pipeline/fetch.py:276`.

### B.2 Where the flag lives

`pipeline/pricing.py:64-66` (verbatim):

```python
RATE_RECALC_WEEKLY_FALLBACK = os.getenv(
    'RATE_RECALC_WEEKLY_FALLBACK', '1'
).lower() in ('1', 'true', 'yes', 'on')
```

- Default **ON** (`'1'`).
- **Frozen at import** — a module-level constant, not re-read per call.
- Re-exported into the facade at `generate_weekly_pdfs.py:194` (static re-export, *not* one
  of the four PEP-562 live-proxy names per STATE.md Phase 09-03), imported into
  `pipeline/fetch.py:42` and `pipeline/orchestrate.py:151`. Startup banner logs its state at
  `generate_weekly_pdfs.py:314-320`.
- `tests/test_subcontractor_pricing.py:1182-1184` already asserts
  `generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK` exists and is a `bool` — the facade
  attribute is an established, patchable test seam.

### B.3 The audit-side bug

`audit_billing_changes.py:149-158`:

```python
sheet_id = row.get('__source_sheet_id')
weekly_fallback_enabled = bool(
    snapshot_column_index and snapshot_column_index.get(sheet_id, False)
)

effective_date, _used_fallback = _resolve_rate_recalc_cutoff_date(
    row,
    _gwp._AEP_BILLABLE_CUTOFF,
    weekly_fallback_enabled=weekly_fallback_enabled,
)
```

Half the production condition. With `RATE_RECALC_WEEKLY_FALLBACK=false`, production does
**not** recalculate a blank-snapshot row (`fetch.py:398-401`), but the audit still calls it
current-cycle and can report it as a mismatch — exactly the Codex P2 finding.

### B.4 Recommended fix — read the facade constant, not `os.getenv`

```python
    weekly_fallback_enabled = bool(
        _gwp.RATE_RECALC_WEEKLY_FALLBACK
        and snapshot_column_index
        and snapshot_column_index.get(sheet_id, False)
    )
```

`_gwp` is already bound two lines above (`audit_billing_changes.py:141`) — **no new import**.

Justification for the facade constant over per-call `os.getenv` (the
`RATE_SANITY_AUDIT_ENABLED` convention at `audit_billing_changes.py:502`):

1. **Mirroring is the point.** The audit must reproduce what production *did*, and
   production used the value frozen at import. A per-call `os.getenv` would let the two
   disagree if the environment changed mid-run — the audit would classify as in-scope a
   row production deliberately did not recalculate. That is the same class of defect P2
   reports, re-introduced from the other side.
2. **Precedent in the same function.** `_rate_sanity_in_scope` already reads
   `_gwp._AEP_BILLABLE_CUTOFF` (`:156`) — a facade constant, same convention.
3. **The finding itself names it:** "Include `_gwp.RATE_RECALC_WEEKLY_FALLBACK` in this
   condition".
4. **Testability is unaffected** — `mock.patch.object(generate_weekly_pdfs,
   'RATE_RECALC_WEEKLY_FALLBACK', False)` works on a static facade re-export and is the
   documented Phase-09 test pattern.
5. The `os.getenv` convention applies to switches the **audit itself owns**
   (`RATE_SANITY_AUDIT_ENABLED`), not to a production-owned constant it is mirroring.

**Where the AND goes:** in `_rate_sanity_in_scope`, **not** in
`_rate_sanity_snapshot_column_index` (`audit_billing_changes.py:80-97`). That helper maps
sheet → column presence, which is flag-independent — exactly like production's
`sheet_has_snapshot_date_column` (`fetch.py:276`), where the AND happens at the call site
(`fetch.py:398-401`). Structural mirror, one place to reason about.

Also update the `_rate_sanity_in_scope` docstring F1 bullet (`:134-138`) to name both
conjuncts, and its `pipeline/fetch.py:276, 389-402` citation stays accurate.

### B.5 Test impact

`RateSanityTestBase.setUp` (`tests/test_rate_sanity_audit.py:31-41`) patches only
`_SUBCONTRACTOR_RATES` — nothing touches the flag.

| Test | Action |
|---|---|
| R6 `:656-687` | **No change needed** (out-of-scope either way), but becomes hermetic via the setUp patch below |
| R7 `:689-713` | **Implicitly depends on the flag being ON.** Today it passes only because the default is `'1'`; a dev shell with `RATE_RECALC_WEEKLY_FALLBACK=0` breaks it (constant frozen at import). Make it explicit |
| R8 `:715-738` | No change (unknown sheet → out of scope regardless) |
| R9 `:740-754` | No change (snapshot branch never consults the flag) |
| R10 `:756-807` | No change |

**Recommended amendment (one place):** add to `TestRateSanityScopeHardening.setUp`
(`:544-546`) a `mock.patch.object(generate_weekly_pdfs, 'RATE_RECALC_WEEKLY_FALLBACK',
True)` + `self.addCleanup(...)`. That makes R6–R10 hermetic without editing five bodies,
and lets the new flag-off test override locally.

**New tests:**

- **R11 — flag OFF, sheet DOES map Snapshot Date, blank snapshot, post-cutoff weekly →
  out of scope, reason `pre_cutoff_or_undated`.** This is the RED test; it fails on
  today's code. (Same fixture as R7, flag flipped.)
- **R12 — flag OFF, row HAS a post-cutoff Snapshot Date → still IN scope (1 mismatch).**
  Guards against over-correcting: the flag gates only the fallback branch, never the
  primary snapshot branch (`pipeline/utils.py:117-119` returns on the snapshot branch
  before the fallback branch is reached).
- **R13 (optional) — flag ON, sheet maps NO Snapshot Date → still out of scope.** Pins
  that the two conjuncts are ANDed, not ORed.

---

## Part C — WR-05: direct `snapshot_store.py` coverage

### C.1 What exists

`tests/test_snapshot_store.py` — 47 lines, 2 tests, both narrow IN-05 never-raises locks
(`get_client` raising; uncoercible key tuple). Its own docstring says "the fuller suite
remains a follow-up" (`:9-10`).

`tests/test_snapshot_drift_audit.py:90-105` patches all three snapshot_store functions at
the module boundary — so none of the real I/O code is exercised anywhere.

Reusable mock harness: `tests/test_billing_audit_shadow.py:141-220`
(`_make_fake_supabase_client`) already builds the
`client.schema('billing_audit').rpc(...).execute()` **and**
`.table(...).select(...)...execute()` chains. Extend that shape rather than inventing one.

### C.2 Mocking boundary

Patch **`billing_audit.snapshot_store.get_client`** only; let the real `with_retry` run
(it is pure Python, and only sleeps on the transient path). Call
`billing_audit.client.reset_cache_for_tests()` (`client.py:297-307`) in `setUp`/`addCleanup`
to clear `_open_circuits`, `_consecutive_failures`, and `_global_disable_reason` between
tests. No Supabase writes are possible — the client is a `Mock`.

### C.3 Test list (pre-RPC, characterization — all should pass on today's code)

`fetch_snapshot_provenance`:

| # | Case | Expected | Pins |
|---|---|---|---|
| F1 | `keys=[]` | `({}, 'no_row')`, `get_client` never called | `:68-69` |
| F2 | client `None`, `_global_disable_reason is None` | `({}, 'unavailable')` | `:79-82` |
| F3 | client `None`, `_global_disable_reason='PGRST106'` | `({}, 'fetch_failure')` | `:80-81` |
| F4 | `resp.data == []` | `no_row` | `:104,115-116` |
| F5 | `resp.data is None` | `no_row` | `:101-104` |
| F6 | `resp.data` is a bare **dict** | normalized to 1-item list → `success` | `:102-103` |
| F7 | response includes an unrequested cross-product pair | filtered out; only wanted pair returned; `success` | `:113-114` |
| F8 | response row with `sheet_id=None` / `'abc'` | skipped, no raise | `:109-112` |
| F9 | rows returned but **none** in `wanted` | `no_row` (not `success`) | `:115-116` |
| F10 | `with_retry` → `None` (execute always raises a permanent APIError) | `fetch_failure` | `:99-100` |
| F11 | response ids as **strings** (`"123"`) | `int()` coercion matches the key | `:110` |
| F12 | `.select()` chain raises `TypeError` | `fetch_failure`, never raises | `:118-127` |
| F13 | requested column list | `select` called with `_PROVENANCE_COLUMNS` (9 cols, matches `schema.sql:355-366`) | `:37-40` |

`upsert_snapshot_provenance`:

| # | Case | Expected |
|---|---|---|
| U1 | `records=[]` | no client call at all (`:137-138`) |
| U2 | client `None` | no-op, returns `None` (`:139-141`) |
| U3 | happy path | `.upsert(records, on_conflict="sheet_id,row_id")` verbatim — pins the PK contract against `schema.sql:365` (`:147`) |
| U4 | `execute()` raises | returns `None`, never raises, logs (`:151-157`) |

`insert_snapshot_drift_events`:

| # | Case | Expected |
|---|---|---|
| I1 | `events=[]` | no client call (`:167-168`) |
| I2 | client `None` | no-op (`:170-172`) |
| I3 | happy path | single `.insert(list(events))`, one `execute()` (`:176-180`) |
| I4 | `execute()` raises | never raises (`:182-188`) |

Module contract:

| # | Case | Expected |
|---|---|---|
| M1 | `snapshot_store.sanitized_wr is writer._sanitized_wr` | identity holds — guards the `noqa: F401` re-export at `:31` |

### C.4 Post-RPC additions (land with Part A, RED-first)

| # | Case | Expected |
|---|---|---|
| A1 | RPC available | `.rpc('lookup_snapshot_provenance_bulk', {'p_keys': [...]})` called; `.table().select()` **not** called |
| A2 | RPC payload shape | each element is `{'sheet_id': int, 'row_id': int}` |
| A3 | RPC raises PGRST202 | falls back to the `.in_` select path → `success`; returned status is one of the original four (never `'rpc_missing'`) |
| A4 | one-time log | two calls in the same process → exactly **one** WARNING |
| A5 | RPC raises a transient error until retries exhaust | `fetch_failure`, **no** `.in_` fallback (no retry storm) |
| A6 | chunking (RPC) | 1200 keys at `_RPC_CHUNK_SIZE=500` → exactly 3 rpc invocations, results merged |
| A7 | chunking (fallback) | 1000 keys at `_FALLBACK_ROW_ID_CHUNK=200` → 5 select invocations; `sheet_id` list whole on each |
| A8 | op isolation | RPC failures increment the `lookup_snapshot_provenance_bulk` breaker, not `fetch_snapshot_provenance` (assert via `client._consecutive_failures`) |
| A9 | upsert chunking (if adopted) | 2500 records at `_UPSERT_CHUNK=1000` → 3 upsert calls |

---

## Recommended plan shape

**Ordering is load-bearing: C before A.** The WR-05 suite is the behavioural oracle for the
WR-02 refactor. Writing it after the refactor tests the new code against itself.

| # | Task | Files | TDD point |
|---|---|---|---|
| **T1** | **P2 flag fix (B)** | `audit_billing_changes.py:150-152` (+ docstring `:134-138`), `tests/test_rate_sanity_audit.py` | **RED:** add R11 (flag OFF → out of scope) — fails today. **GREEN:** add `_gwp.RATE_RECALC_WEEKLY_FALLBACK and` to the condition. Then add R12/R13 and the hermetic `setUp` patch. Smallest, highest-regression-risk change — ship first, alone |
| **T2** | **WR-05 characterization suite (C)** | `tests/test_snapshot_store.py` (expand from 47 lines) | All F/U/I/M tests **GREEN on unmodified `snapshot_store.py`**. Any that go RED are real pre-existing bugs — surface, don't silently fix |
| **T3** | **schema.sql RPC block (A-SQL)** | `billing_audit/schema.sql` (append at EOF) | No test — the file is never executed by CI (`schema.sql:1-24`). Verification = manual read against the two existing RPC blocks for style parity. Optionally include WR-03's two `ENABLE ROW LEVEL SECURITY` lines so Juan's single manual pass covers everything |
| **T4** | **RPC-first reader (A-Python)** | `billing_audit/snapshot_store.py`, `tests/test_snapshot_store.py` | **RED:** A1–A8. **GREEN:** implement per §A.5. **Regression gate:** the entire T2 suite must pass **unchanged** — that is the proof the 4-status vocabulary and never-raises contract survived |
| **T5** | **Chunk `upsert_snapshot_provenance`** (recommended, can defer) | `snapshot_store.py:130-157`, tests | **RED:** A9. Same root cause as WR-02 (~40 MB body at live scale). If deferred, record it as a new WR item |
| **T6** | **Docs + state** | `memory-bank/living-ledger.md` (new `[YYYY-MM-DD HH:MM]` entry per CLAUDE.md autonomous-memory rule), `.planning/STATE.md` quick-task row, blockers list (add "apply `lookup_snapshot_provenance_bulk` RPC") | No code |

**Commits:** one per task, Conventional Commits, subject ≤50 chars. T3+T4 may share a PR but
should be separate commits (SQL is operator-facing, Python is not).

**Gate:** `pytest tests/ -v` green + `python -m py_compile generate_weekly_pdfs.py` before
push (CLAUDE.md validation commands; `.github/hooks/pre-push-tests.json`).

---

## Constraints honoured

| Constraint | How |
|---|---|
| Report-only audit | T1 touches only `_rate_sanity_in_scope`'s scope classification; no price/grouping/hash/filename/upload path is reachable from it |
| No Supabase writes from tests | `get_client` patched to a `Mock` in every new test; `reset_cache_for_tests()` in cleanup |
| Kill switches unchanged in meaning | `RATE_RECALC_WEEKLY_FALLBACK` keeps its default-ON, frozen-at-import semantics; `RATE_SANITY_AUDIT_ENABLED` untouched; no new env var introduced |
| `schema.sql` is manual-apply | Append-only DDL with an `OPERATOR:` note; nothing in CI executes it; Python degrades on PGRST202 |
| Status vocabulary unchanged | `rpc_missing` stays internal — required by `pipeline/snapshot_drift.py:551` |
| Full suite stays green | T2 lands before T4 and is re-run unchanged as the refactor gate |
| PEP 8 + type hints + ≤79 cols | Existing `snapshot_store.py` already conforms; new helpers follow |
| No production-logic redesign | Both changes are additive; the Smartsheet → Excel → attachment pipeline is not touched |

---

## Open questions / decisions for Juan

1. **Is the two-`.in_` read already failing in production?** Cheap check: grep a recent
   weekly Actions log for `billing_audit[fetch_snapshot_provenance] RPC failed`. Changes the
   framing from "optimization" to "repair" — worth confirming before planning.
2. **Include WR-03's RLS lines** (`ENABLE ROW LEVEL SECURITY` on both new tables) in the
   same manual-apply pass? Additive, free defense-in-depth, `service_role` bypasses RLS.
3. **Chunk `upsert_snapshot_provenance` now (T5) or file as a new WR item?**
4. **`SET search_path = ''` on billing_audit functions** — a file-wide hardening decision
   (silences Supabase's `function_search_path_mutable` advisor). Recommend deferring rather
   than deviating on one function.

## Sources

**Primary (HIGH):** `billing_audit/snapshot_store.py`, `billing_audit/client.py`,
`billing_audit/writer.py:838-957,1144-1230`, `billing_audit/schema.sql` (full),
`pipeline/snapshot_drift.py`, `pipeline/fetch.py:268-403`, `pipeline/pricing.py:57-67`,
`pipeline/utils.py:85-145`, `audit_billing_changes.py:80-161,470-549`,
`generate_weekly_pdfs.py:188-200,314-320`, `pipeline/orchestrate.py:575-600`,
`tests/test_snapshot_store.py`, `tests/test_rate_sanity_audit.py`,
`tests/test_billing_audit_shadow.py:141-220`, `memory-bank/living-ledger.md:5485-5505`,
`.planning/quick/260812-jqx-…/260812-jqx-REVIEW.md:149-216`,
installed `supabase==2.31.0` / `postgrest==2.31.0` (introspected).

**Secondary (MEDIUM):** https://docs.postgrest.org/en/v13/references/errors.html (PGRST202
= 404, "Could not find the … function in the schema cache").
