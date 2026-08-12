---
phase: quick-260812-jqx
reviewed: 2026-08-12T21:44:27Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - pipeline/snapshot_drift.py
  - billing_audit/snapshot_store.py
  - billing_audit/schema.sql
  - pipeline/config.py
  - pipeline/orchestrate.py
  - audit_billing_changes.py
  - tests/test_snapshot_drift_audit.py
findings:
  critical: 2
  warning: 5
  info: 7
  total: 14
status: issues_found
---

# Quick Task 260812-jqx: Code Review Report

**Reviewed:** 2026-08-12T21:44:27Z
**Depth:** standard (with cross-file tracing into pipeline/excel.py, pipeline/grouping.py, billing_audit/client.py, billing_audit/writer.py)
**Files Reviewed:** 7
**Status:** issues_found
**Diff range:** 3f7be82..HEAD (55329a1, c58a9bd, 0a68aeb, 0b5051a)

## Summary

The snapshot-date drift audit is well-structured: detection defaults on
/ hold defaults off (verified at `pipeline/snapshot_drift.py:490-493`
and `pipeline/config.py`), holds apply only to `automation_self_fire`
candidates, cell-history lookups are capped at 40 rows with 2s pacing
and a session sub-budget, schema changes are additive-only, no new
AUDIT_SHEET_ID writes exist, and the outer entry point never raises.
All 27 new tests pass (`pytest tests/test_snapshot_drift_audit.py`,
31.66s).

However, two Critical defects break the audit's own invariants:
(CR-01) a transient Supabase read failure causes the run to re-seed and
**overwrite every existing provenance baseline** with the current week
— silently laundering any in-flight drift and violating the
fail-closed-logging half of D-03; and (CR-02) a hold applied to a row
whose baseline `snapshot_date` is NULL writes `None` into
`Snapshot Date`, which the Excel day-block filter
(`pipeline/excel.py:723-729`) then silently drops from the workbook —
the exact "strictly worse than the drift itself" failure the module's
own docstring warns against (RESEARCH pitfall 1).

## Narrative Findings (AI reviewer)

### Critical Issues

#### CR-01: Provenance upsert not gated on fetch status — transient read failure poisons every baseline

**File:** `pipeline/snapshot_drift.py:507-514, 530-537, 600-606` (with `billing_audit/snapshot_store.py:126-153`)
**Issue:** When the bulk provenance read fails transiently
(`with_retry` exhaustion or an open read-op circuit breaker →
`status == "fetch_failure"`), `baseline_map` is `{}` and **every** row
degrades to the first-sight seed path. The subsequent
`upsert_snapshot_provenance(provenance_records)` at line 601 is not
gated on `status` — and unlike the `unavailable` case (client is
`None`, upsert no-ops), a transient read failure leaves the write path
healthy (`with_retry` circuit breakers are per-op by design, see
`billing_audit/client.py`). The upsert therefore OVERWRITES every
existing baseline's `billed_week` with the row's *current* computed
week and resets `first_seen_at` to now. Any drift that occurred before
that run is silently accepted as the new baseline: no candidate, no
`snapshot_drift` event, no future detection. One bad read window
rebases the entire provenance table and defeats the audit's fail-closed
logging guarantee (D-03). `TestTask1FetchRaisesDegradesToSeed` asserts
the seed degrade but never checks that the upsert is suppressed, so the
bug is test-endorsed.
**Fix:**
```python
# apply_snapshot_drift_holds, after building records:
try:
    if status in ("success", "no_row"):
        _store.upsert_snapshot_provenance(provenance_records)
    else:
        logger.warning(
            "⚠️ Snapshot-drift provenance upsert skipped: bulk read "
            "status=%s (avoid rebasing existing baselines).", status,
        )
except Exception:
    ...
```
Add a test: fetch returns `({}, "fetch_failure")` → `mock_upsert.assert_not_called()`.

#### CR-02: Hold with NULL prior `snapshot_date` silently drops the billed row from the workbook

**File:** `pipeline/snapshot_drift.py:461` (with `pipeline/excel.py:723-729`)
**Issue:** `_apply_holds` rewrites
`row["Snapshot Date"] = _iso_date_str(candidate["prior_snapshot_date"])`.
The provenance baseline's `snapshot_date` is nullable
(`billing_audit/schema.sql`: `snapshot_date DATE` with no NOT NULL) and
is NULL whenever a row was seeded while its `Snapshot Date` cell was
blank or unparseable — an *observed* production state: rows with a
`Weekly Reference Logged Date` but no snapshot because "Smartsheet's
snapshot automation has not fired yet (the observed VAC crew failure
mode)" (`pipeline/utils.py:85-90`). For such a candidate, the hold sets
`Snapshot Date` to `None`; grouping places the row in the prior week,
but `generate_excel`'s Monday–Sunday day-block filter does
`excel_serial_to_date(snap) is None → continue`, so the held row is
**silently excluded from the workbook body** — a billing-visible row
drop, the exact failure the module docstring names RESEARCH pitfall 1.
`TestTask3HeldRowSurvivesExcelFilter` only covers the non-NULL prior
snapshot case. Gated today by `SNAPSHOT_DRIFT_HOLD_ENABLED=false`, but
this is the feature's primary path once the flag is turned on per the
plan.
**Fix:**
```python
# _apply_holds, before mutating the row:
prior_snapshot = _coerce_date(candidate["prior_snapshot_date"])
if prior_snapshot is None:
    logging.warning(
        "⚠️ Snapshot-drift hold skipped for WR %s row %s: no prior "
        "snapshot date on baseline (row would be dropped by the "
        "Excel week filter).",
        candidate["wr"], candidate["row_id"],
    )
    continue  # classify + log only; never hold
row["Snapshot Date"] = prior_snapshot.isoformat()
```
Add a test: baseline with `snapshot_date=None`, hold enabled → row not
mutated (or mutated with a non-None fallback), and the drift event
still recorded.

### Warnings

#### WR-01: `automation_self_fire` classification granted without timestamp corroboration

**File:** `pipeline/snapshot_drift.py:316-328`
**Issue:** When the newest Snapshot Date history entry has a missing or
unparseable `modified_at` (`newest_ts is None`), the ±2-minute
units-change window cannot be evaluated. `nearby_units_change` stays
`False`, so an automation-identity write is classified
`automation_self_fire` — i.e. hold-eligible — on incomplete evidence.
The conservative direction (D-03/D-05: hold only on solid evidence) is
`unclassified`.
**Fix:** After computing `newest_ts`, add:
```python
if newest_ts is None:
    return _CLASSIFICATION_UNCLASSIFIED, newest_email
```

#### WR-02: Bulk provenance read uses two `.in_` filters — URL-length growth and cross-product over-fetch

**File:** `billing_audit/snapshot_store.py:79-91`
**Issue:** `.in_("sheet_id", sheet_ids).in_("row_id", row_ids)` puts
~550 row IDs + 13 sheet IDs into a GET querystring (~10KB today,
growing linearly with row count toward PostgREST/proxy URL limits) and
matches the sheet×row cross-product server-side (any row whose row_id
collides across sheets is fetched and discarded by the client-side
`wanted` filter — correct, but wasted transfer). The repo already
solved this exact class of bulk-lookup with the
`billing_audit.lookup_attribution_bulk(jsonb)` RPC
(`billing_audit/schema.sql:~300-330`).
**Fix:** Add a `lookup_snapshot_provenance_bulk(jsonb)` RPC taking
`[(sheet_id, row_id), ...]` pairs (POST body, exact-key match), or at
minimum document the row-count ceiling and chunk the `.in_` lists.

#### WR-03: New tables ship without Row Level Security

**File:** `billing_audit/schema.sql` (appended `snapshot_provenance` / `snapshot_drift` blocks)
**Issue:** Both new tables rely on grants alone (`service_role` only)
while the `billing_audit` schema is PostgREST-exposed — the block's own
operator note instructs confirming schema exposure. This matches the
existing posture of the other `billing_audit` tables (no
RLS anywhere in the file), but for *new* tables
`ALTER TABLE ... ENABLE ROW LEVEL SECURITY` with no policies is a free
defense-in-depth line: `service_role` bypasses RLS, and `anon`/
`authenticated` stay locked out even if default privileges or a future
grant leak. Additive, touches nothing existing.
**Fix:**
```sql
ALTER TABLE billing_audit.snapshot_provenance ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_audit.snapshot_drift ENABLE ROW LEVEL SECURITY;
```
(Manual apply by Juan alongside the CREATE TABLE blocks — Supabase
schema changes remain his approval per production guardrails.)

#### WR-04: Test file spends ~25-30s in real `time.sleep` on every suite run

**File:** `tests/test_snapshot_drift_audit.py` (classifier/hold tests; base class at :289-304)
**Issue:** Only `TestTask2PacingBetweenCalls` mocks
`pipeline.snapshot_drift.time.sleep`. Every other test that drives two
cell-history calls (self-fire, nearby-units, per-run cap, ordering
independence ×2, modified-by shapes, all five Task-3 hold tests, the
three-outcome event test) pays a real 2.0s pacing sleep. Measured: 27
tests take **31.66s** wall (nearly all sleep). This silently inflates
every `pytest tests/` run — the pre-push gate — by half a minute.
**Fix:** Set `SNAPSHOT_DRIFT_PACE_SEC=0` in
`SnapshotDriftClassifierTestBase.setUp` (via
`mock.patch.dict(os.environ, ...)` + `addCleanup`); have
`TestTask2PacingBetweenCalls` set it explicitly to `2.0` since it
asserts `call.args[0] == 2.0`.

#### WR-05: `billing_audit/snapshot_store.py` has zero direct test coverage

**File:** `billing_audit/snapshot_store.py` (all three public functions)
**Issue:** Every test patches `fetch_snapshot_provenance`,
`upsert_snapshot_provenance`, and `insert_snapshot_drift_events` at the
module boundary. The only code in this change that performs live
Supabase I/O — the `.in_` query construction, the `wanted`-set
filtering, the dict-shaped response normalization (:98-99), the
`int()` key coercion (:105-108), and the four-value status vocabulary —
is exercised by nothing. A regression there (e.g. a supabase-py builder
change) would pass the whole suite.
**Fix:** Add a small test module mocking `get_client()`/`with_retry`
that asserts: key filtering drops cross-product rows, dict response is
normalized to a list, `None` response → `fetch_failure`, empty data →
`no_row`, and client-None with/without `_global_disable_reason` →
`unavailable`/`fetch_failure`.

### Info

#### IN-01: `datetime.datetime.utcnow()` is deprecated

**File:** `pipeline/snapshot_drift.py:120`
**Issue:** Emits `DeprecationWarning` on Python 3.12 (CI runtime).
**Fix:** `datetime.datetime.now(datetime.timezone.utc).strftime(...)`.

#### IN-02: Mixed root-`logging` and module-`logger` calls

**File:** `pipeline/snapshot_drift.py:373, 466, 615` (root) vs `:330, 603, 610, 626` (module logger)
**Issue:** Same module logs through two different loggers; filtering or
handler configuration will treat them inconsistently.
**Fix:** Standardize on the module `logger`.

#### IN-03: Env-var defaults defined in two places

**File:** `pipeline/config.py:128-172` and `pipeline/snapshot_drift.py:351-354, 490-493`
**Issue:** The config constants are documentation-only by design
(module re-reads env per call), but each default is now hardcoded in
both files (`40`, `2.0`, `5`, `'automation@smartsheet.com'`, switch
defaults). A future change to one side silently diverges the other.
**Fix:** Single module-level defaults dict in `snapshot_drift.py` that
`config.py` references (or a comment cross-pinning the pairs).

#### IN-04: `changed_by` email logged at INFO into CI run logs

**File:** `pipeline/snapshot_drift.py:466-473`
**Issue:** Every hold logs the modified-by email into GitHub Actions
logs. Consistent with existing log posture (foreman names, WRs), but
the repo's own rationale for `SENTRY_ENABLE_LOGS=false` is that
INFO-path logs can embed row PII — worth a deliberate choice here.
**Fix:** Consider logging only the classification and moving the email
to the Supabase event row (already captured there).

#### IN-05: `fetch_snapshot_provenance` "NEVER raises" contract has a hole

**File:** `billing_audit/snapshot_store.py:71-81`
**Issue:** The `_client_mod._global_disable_reason` peek (private-attr
reach-in), `get_client()`, and the key-coercion comprehensions run
*outside* the try/except; an exception there escapes despite the
docstring's NEVER-raises claim. The caller in `snapshot_drift.py`
wraps it (:507-512), so it is contained in practice.
**Fix:** Move the client/keys setup inside the try, or expose a public
`is_globally_disabled()` helper on `billing_audit.client`.

#### IN-06: No runbook/changelog entry for operator-visible surface

**File:** (docs gap — `website/` untouched in 3f7be82..HEAD)
**Issue:** This change adds six operator-facing env vars, two Supabase
tables requiring a manual SQL-editor apply + PostgREST cache reload,
and a new hold behavior — the documentation-maintenance rule requires a
synthesized runbook changelog entry, and the sibling quick task
(260812-isx, commit e003124) set the precedent. The schema.sql header
carries the operator steps, and `docs-changelog.yml` will append a
stub on merge.
**Fix:** Expand the stub into a proper entry (what/why/operator impact,
including the manual DDL step and the hold-flag rollout plan) before
the next release.

#### IN-07: Risk thresholds duplicated between `_generate_audit_summary` and `escalate_risk_for_snapshot_drift`

**File:** `audit_billing_changes.py:508-517` and `:695-747`
**Issue:** The 0 / ≤3 / else risk ladder is re-derived post-hoc
(self-documented, and verified safe today: `risk_level` has no other
writers and the escalated total is strictly ≥ the original, so no
downgrade is possible). A future threshold change in one place will
silently diverge the other.
**Fix:** Extract a shared `_risk_level_for(total_issues: int) -> str`
used by both.

## Invariant Verification (production context)

| Invariant | Status |
|---|---|
| Report-only by default (`SNAPSHOT_DRIFT_HOLD_ENABLED` default false) | PASS (`config.py`, `snapshot_drift.py:493`) |
| Holds only for automation self-fires, never manual/unclassified | PASS (`_apply_holds:445`, tests Task3 Manual/Unclassified) |
| Fail-open gating / errors never block billing | PASS (outer catch-all `:623-631`, orchestrate seam try/except `:586-620`) |
| Fail-closed logging (every candidate recorded) | **FAIL under transient fetch failure** — see CR-01 (drift laundered into baseline with no event) |
| Cell-history ≤ 40 rows, ~2s paced, week-movers only | PASS (`SNAPSHOT_DRIFT_MAX_ROWS=40`, `pace_sec=2.0`, candidates = week-movers only) |
| schema.sql additive only | PASS (append-only diff; `CREATE TABLE IF NOT EXISTS`) |
| No new mutating AUDIT_SHEET_ID writes | PASS (no Smartsheet writes anywhere in the new code) |
| PARALLEL_WORKERS ≤ 8 / 300 req/min | PASS (classification is serial + paced) |
| No `@cell` in API payloads | PASS |

**Validation evidence:** `pytest tests/test_snapshot_drift_audit.py -q`
→ 27 passed, 2 subtests, 31.66s. `python -m py_compile` on all five
touched Python files → OK.

---

_Reviewed: 2026-08-12T21:44:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
