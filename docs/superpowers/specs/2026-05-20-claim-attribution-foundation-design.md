# Foundation A — Claim-Attribution Read Layer & HOLD Contract

**Date:** 2026-05-20
**Status:** Approved design (pre-implementation)
**Author:** Brainstormed with the operator; design sections approved 1–4.
**Scope:** Sub-project **A** of the larger "universal per-line-item claim attribution" effort. This spec covers ONLY Foundation A. B/C/D/E each get their own spec.

---

## 1. Motivation & the larger vision

### The goal (whole system)

Every generated Excel file should be **partitioned by the foreman who claimed each line item** — "claimed" = that foreman logged the unit complete (`Units Completed?` checked) on ProMax, captured at claim time. Each file holds *only* that foreman's claimed units, is named after them, and the attribution is **frozen first-write-wins per row**. This serves billing audit directly: it answers "which foreman claimed which line items, on which day, in which week-ending period," and survives reschedules.

This is the generalization of the subcontractor helper-shadow feature (Phase 1.1, already shipped) to **every variant and both workflows**: primary foreman, helpers, and VAC crew, on both the primary and subcontractor sheets (including the subcontractor `ReducedSub` / `AEPBillable` primary-foreman files).

### Why this is decomposed

The full system rewrites grouping for every variant (primary groups move from one-per-WR to one-per-claimer), changes every filename, makes Supabase load-bearing for file organization, and forces a one-time migration of existing attachments on the Smartsheets. Shipping that as one change to a 2-hourly production billing pipeline is unsafe. Decomposition (operator-approved):

- **A — Attribution-read foundation (THIS SPEC).** Extend the read layer + define the shared resolution/HOLD contract. No grouping, filename, or migration changes. Zero observable production behavior change.
- **B — Subcontractor primary** (`ReducedSub` / `AEPBillable`) → partition by `frozen_primary`, name the file.
- **C — VAC crew** → partition by `frozen_vac_crew`, name the file.
- **D — Primary workflow primary foreman** → partition by `frozen_primary` (highest blast radius + largest migration; deliberately last). Non-sub helpers fold in here or as their own step.
- **E — Supabase hash-store migration** + stripping the `_<hash>` and `_<timestamp>` tokens from filenames (depends on Supabase being the change-detection source of truth).
- Subcontractor helper-shadow is already implemented (Phase 1.1) and was unblocked operationally on 2026-05-20 when the `lookup_attribution` RPC was deployed.

### Fail-safe stance (operator decision)

**Correctness over availability.** When attribution cannot be trusted, **HOLD** the affected files rather than risk mis-attributing billing. A brand-new claim is NOT an outage (`no_history` → use the current foreman, since this run is what freezes them); only genuine `fetch_failure`/outage/kill states HOLD.

---

## 2. Cross-cutting invariant (governs B/C/D — recorded here)

**Claimer-file coexistence & no-cross-delete invariant:**

- Each file holds **only** the line items claimed by one foreman, named after that foreman.
- Attribution is **frozen first-write-wins per row**: a unit claimed by Foreman A stays attributed to A; units the new foreman claims after a reschedule are *new* rows that freeze to the new foreman.
- A foreman switch **within the same week-ending period** produces a **second** file (new foreman's name, only their rows), and **the prior foreman's file must remain** — the two must **never** cross-delete or overwrite each other.

This holds because the foreman name is part of the file's **identity tuple** `(wr, week, variant, identifier=foreman)`. Two claimers on the same WR+week+variant are different identities → distinct filenames, distinct `valid_wr_weeks` entries → the attachment cleanup keeps both (it only prunes older copies *within the same identity*). Every variant rollout (B/C/D) MUST carry a regression test proving two same-week claimers coexist.

Foundation A only *enables* this (it returns the per-row frozen claimer); it does not group or delete anything.

---

## 3. Architecture & boundaries (Foundation A)

A is confined to `billing_audit/` plus the Supabase RPC. Units:

1. **Supabase `lookup_attribution` RPC — extended (additive).** Returns all frozen roles, not just helper.
2. **Existing Python reader `lookup_attribution()` — external behavior UNCHANGED** (thin wrapper internally).
3. **New `resolve_claimer(...)` — the shared contract.** The only new public surface. Nobody imports it in A.
4. **Hold counter + end-of-run alerting helper.** Defined + unit-tested, but **dormant** (no consumer holds in A).

**Explicit non-goals for A:** no `group_source_rows` changes, no filename changes, no `generate_excel` changes, no attachment migration, no modification to the live sub-helper path. **`generate_weekly_pdfs.py` is not modified in A.**

---

## 4. Data layer

### 4.1 Supabase `lookup_attribution` RPC (extended)

Today returns `helper, helper_dept, source_run_id`. Extend to return all three roles in one call so a single lookup serves any variant. Apply the `#NO MATCH` / blank → `NULL` normalization **per role** (centralizes the Smartsheet-error-token defense established 2026-05-20).

```sql
CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution(
    p_wr                TEXT,
    p_week_ending       DATE,
    p_smartsheet_row_id BIGINT
)
RETURNS TABLE (
    primary_foreman TEXT,
    helper          TEXT,
    helper_dept     TEXT,
    vac_crew        TEXT,
    source_run_id   TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE WHEN s.frozen_primary     LIKE '#%' OR btrim(s.frozen_primary)     = '' THEN NULL ELSE s.frozen_primary     END AS primary_foreman,
        CASE WHEN s.frozen_helper      LIKE '#%' OR btrim(s.frozen_helper)      = '' THEN NULL ELSE s.frozen_helper      END AS helper,
        CASE WHEN s.frozen_helper_dept LIKE '#%' OR btrim(s.frozen_helper_dept) = '' THEN NULL ELSE s.frozen_helper_dept END AS helper_dept,
        CASE WHEN s.frozen_vac_crew    LIKE '#%' OR btrim(s.frozen_vac_crew)    = '' THEN NULL ELSE s.frozen_vac_crew    END AS vac_crew,
        s.source_run_id
    FROM billing_audit.attribution_snapshot AS s
    WHERE s.wr                = p_wr
      AND s.week_ending       = p_week_ending
      AND s.smartsheet_row_id = p_smartsheet_row_id
    LIMIT 1;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution(TEXT, DATE, BIGINT) TO service_role;
-- Then: NOTIFY pgrst, 'reload schema';
```

Notes:
- The primary role is returned as `primary_foreman` (not `primary`) to avoid the SQL reserved word entirely — no quoting needed, and the Python role map reads the `primary_foreman` key.
- Adding columns is backward-compatible: the current reader reads only `helper` and ignores extras.
- `btrim` guards whitespace-only values; the `#%` guard catches all Smartsheet error tokens (`#NO MATCH`, `#INVALID VALUE`, `#UNPARSEABLE`, …).
- Column source names (`frozen_primary`, `frozen_helper`, `frozen_helper_dept`, `frozen_vac_crew`, `source_run_id`) confirmed against the live `attribution_snapshot` schema on 2026-05-20.

### 4.2 Python reader (`billing_audit/writer.py`)

- **`_lookup_attribution_all(wr, week_ending, row_id) -> (row: dict | None, status: str)`** — new internal. Invokes the RPC through the existing `with_retry(op="lookup_attribution")` (same circuit breaker, `_global_disable_reason`, classifier — no new failure surface). Returns the full role dict **ungated** plus a status (see §5). Sanitizes `wr` with the existing `_WR_SANITIZE` (idempotent).
- **`lookup_attribution()`** — refactored to a **thin helper-gated wrapper** over `_lookup_attribution_all` that preserves its *exact* external behavior (returns the dict only when `helper` is populated, else `None`). The existing `TestLookupAttribution` suite (14 tests) is the regression guard. This is the one place A refactors an existing function's internals; its observable contract is unchanged. The sub-helper consumer's import path (`from billing_audit.writer import lookup_attribution`) is unchanged.

---

## 5. The `resolve_claimer` contract

**Signature** (in `billing_audit/writer.py`, imported by B/C/D later):

```
resolve_claimer(variant, current_value, *, wr, week_ending, row_id, enabled) -> ResolveOutcome
```

- `current_value` — the live Smartsheet value for this variant's role (the fallback): `effective_user` for primary/sub-primary, `helper_foreman` for helper variants, `vac_crew_name` for vac crew.
- `enabled` — the caller's kill-switch boolean. A does NOT own the flag.
- `ResolveOutcome` — `NamedTuple(action: 'use'|'hold', name: str|None, source: 'frozen'|'current'|None, reason: str)`.

**Variant → role map (`ROLE_BY_VARIANT`):**

| Variant | Role key read from RPC result |
|---|---|
| `primary`, `reduced_sub`, `aep_billable` | `primary_foreman` |
| `helper`, `reduced_sub_helper`, `aep_billable_helper` | `helper` |
| `vac_crew` | `vac_crew` |

**Decision table (the whole contract):**

| Situation | Detection | Outcome |
|---|---|---|
| Feature off | `enabled` is False | `use` current, reason `disabled` |
| Client unavailable, not an outage (TEST_MODE / no creds) | `get_client()` None AND `_global_disable_reason` is None | `use` current, reason `disabled` |
| **Outage / kill** | `_global_disable_reason` set, OR the RPC call returned None after retries (transient exhausted / permanent error) | **`hold`**, reason `fetch_failure` |
| Brand-new claim | RPC succeeded, no row | `use` current, reason `no_history` |
| Role blank on the frozen row | RPC succeeded, row found, role value NULL | `use` current, reason `no_history` |
| Claimed | RPC succeeded, role value present | `use` **frozen**, reason `success` |

**Status detection inside `_lookup_attribution_all`** (drives the table):
- `get_client()` is None: if `billing_audit.client._global_disable_reason` is set → status `fetch_failure`; else → status `unavailable`.
- Client present: `result = with_retry(_invoke, op="lookup_attribution")`.
  - `result is None` → the call FAILED after retries → status `fetch_failure`.
  - `result` present, `result.data` empty → status `no_row`.
  - `result` present, row found → status `success` (returns the role dict).

**Precision win over today's sub-helper heuristic:** a transient outage (5xx / connection drop that exhausts retries) is currently mis-read as `no_history`; here it is `fetch_failure → HOLD`, because "the call object came back None" is treated as failure, distinct from "the call succeeded but returned zero rows." This is what makes "correctness over availability" actually hold.

**Consumer usage (B/C/D, not A):** if `outcome.action == 'hold'` → do not emit that row's group this run (defer to a later run) and record a hold; else use `outcome.name` to build the group key + filename.

---

## 6. Hold counter & alerting (defined, dormant in A)

- A module-level counter in `billing_audit/` tracks held rows by `(wr, week_ending, variant)`, reusing the existing `_bump_counter` / `get_counters` pattern.
- An end-of-run summary helper emits **one** Sentry warning + log line, e.g. `"⚠️ Attribution HOLD: N row(s) across M WR(s) held this run pending attribution (reason=fetch_failure)"`, so a Supabase outage that suppresses files is loudly visible, not silent.
- In A this helper is unit-tested but **not wired into the main run** (nothing holds yet). B calls `resolve_claimer`, accumulates holds, and invokes the summary at end-of-run.
- Log body must avoid row PII per the CLAUDE.md sanitizer rule; counts + WR identifiers only (WR is sanitized).

---

## 7. Config

A adds **no new env var**. `resolve_claimer` takes `enabled` as a parameter; each consumer passes its own flag. The existing `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED` is untouched. Whether B/C/D share one universal flag or get per-variant flags is deferred to those specs.

---

## 8. Error handling / fail-safe

- Reuses the established `with_retry` + `_classify_postgrest_error` + run-global kill machinery unchanged — no new failure surface.
- The reader/`resolve_claimer` never raise on a Supabase failure: failures map to `fetch_failure` (→ HOLD signal) or `unavailable` (→ use-current). A defensive `try/except` around the lookup treats unexpected exceptions as `fetch_failure`.
- A introduces no behavior that can break the billing pipeline (nothing consumes the HOLD signal yet).

---

## 9. Testing

- **`resolve_claimer`** (pure function): exhaustive table test — all 6 decision rows × the role map, asserting each variant reads the correct frozen column and the right `(action, source, reason)` is returned.
- **`_lookup_attribution_all`**: mocked-RPC tests for all-roles row / no-row / `with_retry`→None (fetch_failure) / client-None+global-kill (fetch_failure) / client-None+no-kill (unavailable). Mirror the existing `TestLookupAttribution` postgrest-gated skip pattern (skips on dev without `postgrest` installed).
- **Regression:** the existing `TestLookupAttribution` (14 tests) must still pass unchanged — guard proving the thin-wrapper refactor preserved `lookup_attribution()`'s external behavior.
- **Hold counter/summary:** unit test for accumulation + one-line summary formatting (PII-free).
- No integration/grouping tests in A (no grouping change). `pytest tests/` must exit 0.

---

## 10. File footprint

- **Supabase:** extended `lookup_attribution` RPC (operator applies the SQL in §4.1 + reloads schema cache).
- **`billing_audit/writer.py`:** add `_lookup_attribution_all`, refactor `lookup_attribution` to thin wrapper, add `resolve_claimer` + `ResolveOutcome` + `ROLE_BY_VARIANT` + hold counter/summary helper.
- **`billing_audit/schema.sql`:** update the documented `lookup_attribution` RPC contract to the new return shape.
- **`tests/test_billing_audit_shadow.py`:** the new tests in §9.
- **`generate_weekly_pdfs.py`:** NOT modified.
- **`CLAUDE.md`:** Living Ledger entry added at execution time per repo rule.

---

## 11. Out of scope (future sub-projects)

- Any `group_source_rows` / `generate_excel` / filename change (B/C/D).
- Attachment migration of existing files to per-claimer identities (B/C/D).
- Supabase-backed change-detection hash store and filename hash/timestamp removal (E).
- Retrofitting the live sub-helper shadow onto `resolve_claimer` (deferred; sub-helper proves itself first).
