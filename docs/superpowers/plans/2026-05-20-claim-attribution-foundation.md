# Foundation A — Claim-Attribution Read Layer & HOLD Contract — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the attribution read-layer and the shared `resolve_claimer` HOLD contract in `billing_audit/`, so later sub-projects (B/C/D) can partition every Excel file by the frozen claiming foreman — with zero production behavior change in this sub-project.

**Architecture:** Extend the Supabase `lookup_attribution` RPC to return all frozen roles (`primary_foreman, helper, helper_dept, vac_crew, source_run_id`) with per-role `#NO MATCH`/blank → NULL normalization. In `billing_audit/writer.py`, add an internal `_lookup_attribution_all(...) -> (row, status)` over the existing `with_retry(op="lookup_attribution")`, refactor the public `lookup_attribution()` into a thin helper-gated wrapper (external behavior unchanged, guarded by the existing 14-test `TestLookupAttribution` suite), and add the pure `resolve_claimer(...)` decision function plus a dormant hold counter + summary. `generate_weekly_pdfs.py` is NOT modified.

**Tech Stack:** Python 3.10+, `unittest` + `mock` (existing `tests/test_billing_audit_shadow.py`), Supabase/PostgREST RPC (SQL applied by operator), `billing_audit.client` primitives (`get_client`, `with_retry`, `_global_disable_reason`).

**Source spec:** `docs/superpowers/specs/2026-05-20-claim-attribution-foundation-design.md`

**Project conventions (CLAUDE.md):** PEP 8, type hints, ≤79-char lines, PEP 257 docstrings; PII-safe logging (counts + sanitized WR only, never foreman/helper/dept/job in logs); append a Living Ledger entry to `CLAUDE.md` at execution time with a `[YYYY-MM-DD HH:MM]` timestamp; `pytest tests/` must exit 0 before finishing.

**GSD compatibility note:** This is a superpowers-format plan. It can be executed directly via subagent-driven-development/executing-plans, or imported into the GSD model — each Task below is an atomic, independently-committable unit suitable for a GSD plan step.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `billing_audit/schema.sql` | Doc-grade canonical DDL; documents the `lookup_attribution` RPC contract | Modify — update the RPC contract block + add the extended `CREATE OR REPLACE` for the operator |
| `billing_audit/writer.py` | Attribution writer + reader; counters | Modify — add `_lookup_attribution_all`, refactor `lookup_attribution`, add `ResolveOutcome`/`ROLE_BY_VARIANT`/`resolve_claimer`, add hold accumulator + `record_attribution_hold`/`summarize_attribution_holds`, extend `_reset_counters_for_tests` |
| `tests/test_billing_audit_shadow.py` | Billing-audit unit tests | Modify — add `TestLookupAttributionAll`, `TestResolveClaimer`, `TestAttributionHoldSummary` |
| `generate_weekly_pdfs.py` | Production pipeline | **NOT modified** |
| `CLAUDE.md` | Living Ledger | Modify at execution time — append one entry |

`resolve_claimer` and the hold helpers live in `writer.py` alongside `lookup_attribution` so the existing import path (`from billing_audit.writer import ...`) is unchanged and attribution logic stays co-located.

---

## Task 1: Extend the Supabase `lookup_attribution` RPC (SQL + schema doc)

The live RPC is operator-applied in Supabase; the repo deliverable is the documented contract in `schema.sql`. No automated test (the RPC is external — its behavior is exercised via mocks in later tasks).

**Files:**
- Modify: `billing_audit/schema.sql` (the `── lookup_attribution (RPC)` block, ~L177-206)

- [ ] **Step 1: Update the `schema.sql` RPC contract block**

Replace the parameter/return contract note in the `lookup_attribution` block so it documents all roles, and append the operator `CREATE OR REPLACE`. The block must read:

```sql
-- ── lookup_attribution (RPC) ────────────────────────────────
-- Read surface for Phase 1.1 Bug C AND the universal claim-
-- attribution effort (Foundation A, 2026-05-20). Returns ALL frozen
-- roles for ONE row so a single call serves any variant.
--
--   PARAMETERS (all named, p_<name>):
--     p_wr                TEXT
--     p_week_ending       DATE
--     p_smartsheet_row_id BIGINT
--
--   RETURNS: one row with
--     primary_foreman TEXT, helper TEXT, helper_dept TEXT,
--     vac_crew TEXT, source_run_id TEXT
--   or zero rows when no snapshot exists for the tuple.
--
-- Each role value is normalized: Smartsheet error tokens (anything
-- starting with '#', e.g. '#NO MATCH') and blank/whitespace-only
-- values are returned as NULL so the Python reader treats them as
-- "no claimer in this role".
--
-- The Python contract is enforced in billing_audit/writer.py
-- (_lookup_attribution_all / resolve_claimer). Do NOT rename the
-- returned column names without updating those call sites.
--
-- OPERATOR: apply this CREATE OR REPLACE in the Supabase SQL Editor,
-- then run `NOTIFY pgrst, 'reload schema';` (or Project Settings →
-- API → Reload schema cache). Adding columns is backward-compatible
-- with the prior helper-only consumer.

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
```

- [ ] **Step 2: Verify the file still parses as documentation (no syntax tooling needed)**

Run: `git diff --stat billing_audit/schema.sql`
Expected: shows `billing_audit/schema.sql` modified.

- [ ] **Step 3: Commit**

```bash
git add billing_audit/schema.sql
git commit -m "docs(billing_audit): extend lookup_attribution RPC to all frozen roles"
```

---

## Task 2: Add `_lookup_attribution_all` (internal reader returning `(row, status)`)

**Files:**
- Modify: `billing_audit/writer.py` (add new function near the existing `lookup_attribution`, ~after L779)
- Test: `tests/test_billing_audit_shadow.py` (new class `TestLookupAttributionAll`)

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/test_billing_audit_shadow.py` (near `TestLookupAttribution`):

```python
class TestLookupAttributionAll(unittest.TestCase):
    """Foundation A: _lookup_attribution_all returns (row, status)."""

    def setUp(self):
        _reset_all()
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)
        os.environ["SUPABASE_URL"] = "https://test.supabase.co"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-key"

    def tearDown(self):
        _reset_all()
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)

    def test_success_dict_row(self):
        from billing_audit.writer import _lookup_attribution_all
        client = _make_fake_supabase_client(
            rpc_side_effect=[mock.Mock(data={
                "primary_foreman": "Alice", "helper": "Bob",
                "helper_dept": "500", "vac_crew": None,
                "source_run_id": "run-1",
            })],
        )
        with mock.patch("billing_audit.writer.get_client",
                        return_value=client):
            row, status = _lookup_attribution_all(
                "91467680", datetime.date(2026, 4, 19), 12345)
        self.assertEqual(status, "success")
        self.assertEqual(row["primary_foreman"], "Alice")
        self.assertEqual(row["helper"], "Bob")

    def test_success_list_row(self):
        from billing_audit.writer import _lookup_attribution_all
        client = _make_fake_supabase_client(
            rpc_side_effect=[mock.Mock(data=[{
                "primary_foreman": "Alice", "helper": None,
                "helper_dept": None, "vac_crew": None,
                "source_run_id": "run-1",
            }])],
        )
        with mock.patch("billing_audit.writer.get_client",
                        return_value=client):
            row, status = _lookup_attribution_all(
                "91467680", datetime.date(2026, 4, 19), 12345)
        self.assertEqual(status, "success")
        self.assertEqual(row["primary_foreman"], "Alice")

    def test_no_row_empty_list(self):
        from billing_audit.writer import _lookup_attribution_all
        client = _make_fake_supabase_client(
            rpc_side_effect=[mock.Mock(data=[])],
        )
        with mock.patch("billing_audit.writer.get_client",
                        return_value=client):
            row, status = _lookup_attribution_all(
                "91467680", datetime.date(2026, 4, 19), 12345)
        self.assertIsNone(row)
        self.assertEqual(status, "no_row")

    def test_fetch_failure_when_with_retry_returns_none(self):
        from billing_audit.writer import _lookup_attribution_all
        client = _make_fake_supabase_client()
        with mock.patch("billing_audit.writer.get_client",
                        return_value=client), \
             mock.patch("billing_audit.writer.with_retry",
                        return_value=None):
            row, status = _lookup_attribution_all(
                "91467680", datetime.date(2026, 4, 19), 12345)
        self.assertIsNone(row)
        self.assertEqual(status, "fetch_failure")

    def test_fetch_failure_when_client_none_and_global_kill(self):
        from billing_audit.writer import _lookup_attribution_all
        from billing_audit import client as ba_client
        ba_client._global_disable_reason = "PGRST106"
        try:
            with mock.patch("billing_audit.writer.get_client",
                            return_value=None):
                row, status = _lookup_attribution_all(
                    "91467680", datetime.date(2026, 4, 19), 12345)
        finally:
            ba_client._global_disable_reason = None
        self.assertIsNone(row)
        self.assertEqual(status, "fetch_failure")

    def test_unavailable_when_client_none_no_kill(self):
        from billing_audit.writer import _lookup_attribution_all
        with mock.patch("billing_audit.writer.get_client",
                        return_value=None):
            row, status = _lookup_attribution_all(
                "91467680", datetime.date(2026, 4, 19), 12345)
        self.assertIsNone(row)
        self.assertEqual(status, "unavailable")

    def test_no_row_on_invalid_input(self):
        from billing_audit.writer import _lookup_attribution_all
        client = _make_fake_supabase_client()
        with mock.patch("billing_audit.writer.get_client",
                        return_value=client):
            row, status = _lookup_attribution_all(
                "91467680", datetime.date(2026, 4, 19), "not-an-int")
        self.assertIsNone(row)
        self.assertEqual(status, "no_row")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestLookupAttributionAll -v`
Expected: FAIL — `ImportError: cannot import name '_lookup_attribution_all'`.

- [ ] **Step 3: Implement `_lookup_attribution_all`**

Add to `billing_audit/writer.py` immediately BEFORE the existing `def lookup_attribution(`:

```python
def _lookup_attribution_all(
    wr: str,
    week_ending: datetime.date,
    smartsheet_row_id: int,
) -> tuple[dict | None, str]:
    """Fetch the full frozen-attribution row for ONE row, with status.

    Foundation A (2026-05-20). Returns a ``(row, status)`` tuple:
      - ``'success'``      : RPC succeeded and a row was found (row is
                             the dict of all roles).
      - ``'no_row'``       : RPC succeeded but no row exists, OR the
                             input is invalid (row is None).
      - ``'fetch_failure'``: the call failed — retries exhausted /
                             permanent error / run-global kill tripped
                             (row is None). Consumers HOLD on this.
      - ``'unavailable'``  : no client (TEST_MODE / missing creds) and
                             NOT an outage (row is None). Consumers use
                             the current value.

    The row dict, when present, carries the RPC columns
    ``primary_foreman, helper, helper_dept, vac_crew, source_run_id``
    (already #NO MATCH/blank-normalized to NULL per role by the RPC).
    Shares the ``op="lookup_attribution"`` retry/circuit-breaker with
    the public ``lookup_attribution`` wrapper.
    """
    from billing_audit import client as _client_mod

    client = get_client()
    if client is None:
        if _client_mod._global_disable_reason is not None:
            return None, "fetch_failure"
        return None, "unavailable"
    if (
        not wr
        or week_ending is None
        or not isinstance(smartsheet_row_id, int)
    ):
        return None, "no_row"

    wr_sanitized = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]
    params = {
        "p_wr": wr_sanitized,
        "p_week_ending": week_ending.isoformat(),
        "p_smartsheet_row_id": smartsheet_row_id,
    }

    def _invoke():
        return (
            client.schema("billing_audit")
            .rpc("lookup_attribution", params)
            .execute()
        )

    result = with_retry(_invoke, op="lookup_attribution")
    if result is None:
        return None, "fetch_failure"

    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data, "success"
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first, "success"
    return None, "no_row"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestLookupAttributionAll -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add billing_audit/writer.py tests/test_billing_audit_shadow.py
git commit -m "feat(billing_audit): add _lookup_attribution_all returning (row, status)"
```

---

## Task 3: Refactor `lookup_attribution()` into a thin helper-gated wrapper

The existing `TestLookupAttribution` suite (14 tests) is the regression guard — it must stay green with no edits.

**Files:**
- Modify: `billing_audit/writer.py` (body of `lookup_attribution`, ~L742-779)

- [ ] **Step 1: Establish the green baseline**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestLookupAttribution -v`
Expected: PASS (the suite passes today; some tests may SKIP if `postgrest` is absent — that is fine).

- [ ] **Step 2: Replace the body of `lookup_attribution` with the wrapper**

Keep the existing signature and docstring; replace ONLY the implementation body (from `client = get_client()` through the final `return None`) with:

```python
    row, status = _lookup_attribution_all(wr, week_ending, smartsheet_row_id)
    if status != "success" or row is None:
        return None
    # Preserve the historical helper-gated contract: callers of this
    # public function get the row only when a helper is present.
    return row if row.get("helper") else None
```

Also append one line to the docstring (above the closing `"""`):

```
    Thin helper-gated wrapper over ``_lookup_attribution_all`` since
    Foundation A (2026-05-20); external behavior is unchanged.
```

- [ ] **Step 3: Run the regression suite to verify it still passes**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestLookupAttribution -v`
Expected: PASS (same pass/skip counts as Step 1 — behavior preserved).

- [ ] **Step 4: Commit**

```bash
git add billing_audit/writer.py
git commit -m "refactor(billing_audit): lookup_attribution as thin wrapper over _lookup_attribution_all"
```

---

## Task 4: Add `ResolveOutcome`, `ROLE_BY_VARIANT`, and `resolve_claimer`

**Files:**
- Modify: `billing_audit/writer.py` (add after `lookup_attribution`)
- Test: `tests/test_billing_audit_shadow.py` (new class `TestResolveClaimer`)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_billing_audit_shadow.py`:

```python
class TestResolveClaimer(unittest.TestCase):
    """Foundation A: resolve_claimer decision table + role map."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def _patch_all(self, row, status):
        return mock.patch(
            "billing_audit.writer._lookup_attribution_all",
            return_value=(row, status),
        )

    def test_disabled_uses_current(self):
        from billing_audit.writer import resolve_claimer
        out = resolve_claimer(
            "helper", "CurrentBob", wr="1", week_ending=None,
            row_id=1, enabled=False)
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "CurrentBob")
        self.assertEqual(out.source, "current")
        self.assertEqual(out.reason, "disabled")

    def test_unavailable_uses_current(self):
        from billing_audit.writer import resolve_claimer
        with self._patch_all(None, "unavailable"):
            out = resolve_claimer(
                "helper", "CurrentBob",
                wr="1", week_ending=datetime.date(2026, 4, 19),
                row_id=1, enabled=True)
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "CurrentBob")
        self.assertEqual(out.reason, "disabled")

    def test_fetch_failure_holds(self):
        from billing_audit.writer import resolve_claimer
        with self._patch_all(None, "fetch_failure"):
            out = resolve_claimer(
                "helper", "CurrentBob",
                wr="1", week_ending=datetime.date(2026, 4, 19),
                row_id=1, enabled=True)
        self.assertEqual(out.action, "hold")
        self.assertIsNone(out.name)
        self.assertEqual(out.reason, "fetch_failure")

    def test_no_row_uses_current_no_history(self):
        from billing_audit.writer import resolve_claimer
        with self._patch_all(None, "no_row"):
            out = resolve_claimer(
                "helper", "CurrentBob",
                wr="1", week_ending=datetime.date(2026, 4, 19),
                row_id=1, enabled=True)
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "CurrentBob")
        self.assertEqual(out.reason, "no_history")

    def test_blank_role_uses_current_no_history(self):
        from billing_audit.writer import resolve_claimer
        row = {"primary_foreman": None, "helper": None,
               "helper_dept": None, "vac_crew": None,
               "source_run_id": "r"}
        with self._patch_all(row, "success"):
            out = resolve_claimer(
                "helper", "CurrentBob",
                wr="1", week_ending=datetime.date(2026, 4, 19),
                row_id=1, enabled=True)
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "CurrentBob")
        self.assertEqual(out.reason, "no_history")

    def test_success_uses_frozen(self):
        from billing_audit.writer import resolve_claimer
        row = {"primary_foreman": "Alice", "helper": "FrozenBob",
               "helper_dept": "500", "vac_crew": "Vinny",
               "source_run_id": "r"}
        with self._patch_all(row, "success"):
            out = resolve_claimer(
                "helper", "CurrentBob",
                wr="1", week_ending=datetime.date(2026, 4, 19),
                row_id=1, enabled=True)
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "FrozenBob")
        self.assertEqual(out.source, "frozen")
        self.assertEqual(out.reason, "success")

    def test_role_map_selects_correct_column(self):
        from billing_audit.writer import resolve_claimer
        row = {"primary_foreman": "Alice", "helper": "FrozenBob",
               "helper_dept": "500", "vac_crew": "Vinny",
               "source_run_id": "r"}
        cases = {
            "primary": "Alice",
            "reduced_sub": "Alice",
            "aep_billable": "Alice",
            "helper": "FrozenBob",
            "reduced_sub_helper": "FrozenBob",
            "aep_billable_helper": "FrozenBob",
            "vac_crew": "Vinny",
        }
        for variant, expected in cases.items():
            with self._patch_all(row, "success"):
                out = resolve_claimer(
                    variant, "CURRENT",
                    wr="1", week_ending=datetime.date(2026, 4, 19),
                    row_id=1, enabled=True)
            self.assertEqual(
                out.name, expected,
                f"variant {variant} should read its frozen role")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestResolveClaimer -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_claimer'`.

- [ ] **Step 3: Implement `ResolveOutcome`, `ROLE_BY_VARIANT`, `resolve_claimer`**

Add to `billing_audit/writer.py` after `lookup_attribution`. Add `NamedTuple` to the existing `from typing import Any` import line so it reads `from typing import Any, NamedTuple`.

```python
class ResolveOutcome(NamedTuple):
    """Result of resolving the claiming foreman for ONE row.

    action : 'use' to group/name by ``name``; 'hold' to defer the row
             this run (attribution unavailable — correctness over
             availability).
    name   : the claimer name when action == 'use'; None on 'hold'.
    source : 'frozen' | 'current' | None — provenance for audit/log.
    reason : 'success' | 'no_history' | 'disabled' | 'fetch_failure'.
    """

    action: str
    name: str | None
    source: str | None
    reason: str


# Variant → which frozen role column governs that file's claimer.
ROLE_BY_VARIANT: dict[str, str] = {
    "primary": "primary_foreman",
    "reduced_sub": "primary_foreman",
    "aep_billable": "primary_foreman",
    "helper": "helper",
    "reduced_sub_helper": "helper",
    "aep_billable_helper": "helper",
    "vac_crew": "vac_crew",
}


def resolve_claimer(
    variant: str,
    current_value: str | None,
    *,
    wr: str,
    week_ending: datetime.date | None,
    row_id: int,
    enabled: bool,
) -> ResolveOutcome:
    """Resolve the claiming foreman for ONE row (Foundation A contract).

    See docs/superpowers/specs/2026-05-20-claim-attribution-
    foundation-design.md §5 for the full decision table. ``enabled`` is
    the caller's kill switch — A does not own a flag. ``current_value``
    is the live Smartsheet value for this variant's role (the fallback).
    HOLD is returned ONLY on a genuine outage (``fetch_failure``); a
    brand-new claim (``no_history``) uses the current value because this
    run is what freezes it.
    """
    if not enabled:
        return ResolveOutcome("use", current_value, "current", "disabled")

    row, status = _lookup_attribution_all(wr, week_ending, row_id)
    if status == "unavailable":
        return ResolveOutcome("use", current_value, "current", "disabled")
    if status == "fetch_failure":
        return ResolveOutcome("hold", None, None, "fetch_failure")
    if status == "no_row" or row is None:
        return ResolveOutcome(
            "use", current_value, "current", "no_history")

    role = ROLE_BY_VARIANT.get(variant, "primary_foreman")
    frozen = row.get(role)
    if frozen:
        return ResolveOutcome(
            "use", str(frozen).strip(), "frozen", "success")
    return ResolveOutcome("use", current_value, "current", "no_history")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestResolveClaimer -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add billing_audit/writer.py tests/test_billing_audit_shadow.py
git commit -m "feat(billing_audit): add resolve_claimer HOLD contract + ROLE_BY_VARIANT"
```

---

## Task 5: Add dormant hold counter + end-of-run summary

**Files:**
- Modify: `billing_audit/writer.py` (add accumulator + two helpers; extend `_reset_counters_for_tests`)
- Test: `tests/test_billing_audit_shadow.py` (new class `TestAttributionHoldSummary`)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_billing_audit_shadow.py`:

```python
class TestAttributionHoldSummary(unittest.TestCase):
    """Foundation A: dormant hold counter + PII-safe summary."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_summary_none_when_no_holds(self):
        from billing_audit.writer import summarize_attribution_holds
        self.assertIsNone(summarize_attribution_holds())

    def test_records_and_summarizes(self):
        from billing_audit.writer import (
            record_attribution_hold, summarize_attribution_holds,
            get_counters,
        )
        wk = datetime.date(2026, 4, 19)
        record_attribution_hold("90773033", wk, "reduced_sub_helper")
        record_attribution_hold("90773033", wk, "reduced_sub_helper")
        record_attribution_hold("90727774", wk, "primary")
        msg = summarize_attribution_holds()
        self.assertIsNotNone(msg)
        self.assertIn("3 row(s)", msg)
        self.assertIn("2 WR(s)", msg)
        self.assertIn("90773033", msg)
        self.assertIn("90727774", msg)
        # No foreman/helper PII in the summary — only WR + counts.
        self.assertEqual(get_counters().get("attribution_rows_held"), 3)

    def test_reset_clears_holds(self):
        from billing_audit.writer import (
            record_attribution_hold, summarize_attribution_holds,
        )
        record_attribution_hold(
            "90773033", datetime.date(2026, 4, 19), "primary")
        _reset_all()
        self.assertIsNone(summarize_attribution_holds())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestAttributionHoldSummary -v`
Expected: FAIL — `ImportError: cannot import name 'record_attribution_hold'`.

- [ ] **Step 3: Implement the accumulator + helpers**

Add to `billing_audit/writer.py` (near the counter block, after `get_counters`):

```python
# Attribution HOLD accumulator (Foundation A, dormant until a consumer
# calls resolve_claimer and acts on action == 'hold'). Tracks rows held
# this run pending attribution, keyed by (sanitized_wr, week_iso,
# variant). PII discipline: only counts + sanitized WR identifiers ever
# leave this structure — never foreman/helper/dept/job.
_attribution_holds: dict[tuple[str, str, str], int] = {}
_attribution_holds_lock = threading.Lock()


def record_attribution_hold(
    wr: str,
    week_ending: datetime.date | None,
    variant: str,
) -> None:
    """Record one row held this run (resolve_claimer → action 'hold')."""
    wr_sanitized = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]
    week_iso = week_ending.isoformat() if week_ending else ""
    key = (wr_sanitized, week_iso, variant)
    with _attribution_holds_lock:
        _attribution_holds[key] = _attribution_holds.get(key, 0) + 1
    _bump_counter("attribution_rows_held")


def summarize_attribution_holds() -> str | None:
    """Emit ONE aggregate WARNING if any rows were held; return the
    message (for testing) or None if nothing was held.

    PII-safe: counts + sanitized WR list only. The pipeline's
    logging→Sentry bridge surfaces this WARNING; a consumer wiring this
    into the run (sub-project B) may escalate to an explicit Sentry
    capture.
    """
    with _attribution_holds_lock:
        if not _attribution_holds:
            return None
        total_rows = sum(_attribution_holds.values())
        wrs = sorted({k[0] for k in _attribution_holds})
    wr_sample = wrs[:20]
    suffix = "" if len(wrs) <= 20 else f" (+{len(wrs) - 20} more)"
    msg = (
        f"⚠️ Attribution HOLD: {total_rows} row(s) across {len(wrs)} "
        f"WR(s) held this run pending attribution "
        f"(reason=fetch_failure). Affected WRs (first 20): "
        f"{wr_sample}{suffix}"
    )
    logging.warning(msg)
    return msg
```

- [ ] **Step 4: Extend `_reset_counters_for_tests` to clear the accumulator**

Find `_reset_counters_for_tests` (~L213-218) and add `_attribution_holds.clear()` inside it (after `_emitted_run_keys.clear()`):

```python
    _emitted_run_keys.clear()
    with _attribution_holds_lock:
        _attribution_holds.clear()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_billing_audit_shadow.py::TestAttributionHoldSummary -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add billing_audit/writer.py tests/test_billing_audit_shadow.py
git commit -m "feat(billing_audit): add dormant attribution-hold counter + summary"
```

---

## Task 6: Full-suite gate + Living Ledger entry

**Files:**
- Modify: `CLAUDE.md` (append one Living Ledger entry)

- [ ] **Step 1: Run the full suite (must be green)**

Run: `python -m pytest tests/ -q`
Expected: PASS — prior total + 17 new tests (7 + 7 + 3), 0 failures. Note the exact `N passed / M skipped` counts for the ledger entry.

- [ ] **Step 2: Syntax-check the package import path**

Run: `python -c "import billing_audit.writer as w; print(hasattr(w, 'resolve_claimer'), hasattr(w, '_lookup_attribution_all'), hasattr(w, 'summarize_attribution_holds'))"`
Expected: `True True True`.

- [ ] **Step 3: Append the Living Ledger entry to `CLAUDE.md`**

Append under the `## Living Ledger` section (after the last entry) a new `- [YYYY-MM-DD HH:MM]` entry (use the real current date/time) that records: Foundation A shipped the attribution read-layer + HOLD contract; the extended `lookup_attribution` RPC (all frozen roles, per-role `#NO MATCH`/blank→NULL); `_lookup_attribution_all` `(row, status)` semantics; the `lookup_attribution` thin-wrapper refactor (external behavior preserved, guarded by `TestLookupAttribution`); `resolve_claimer` + `ROLE_BY_VARIANT` + `ResolveOutcome`; the dormant hold counter/summary; the rule that `no_history` uses the current foreman while only `fetch_failure` HOLDs; that `generate_weekly_pdfs.py` was NOT modified and there is zero production behavior change; and that B/C/D will consume `resolve_claimer` and must each carry a regression test proving two same-week claimers coexist. Reference the spec and plan paths.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: Living Ledger — Foundation A claim-attribution read layer + HOLD contract"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** §4.1 RPC → Task 1. §4.2 reader (`_lookup_attribution_all` + thin wrapper) → Tasks 2–3. §5 `resolve_claimer`/role map/decision table → Task 4. §6 hold counter + summary → Task 5. §9 testing → tests in Tasks 2/4/5 + full-suite gate in Task 6. §10 footprint → matches File Structure (no `generate_weekly_pdfs.py` change). §2 coexistence invariant → recorded for B/C/D in the ledger (Task 6); not implemented in A by design.
- **Placeholders:** none — every code/test step shows complete content; the only deferred concrete value is the ledger timestamp (must be the real execution time).
- **Type consistency:** `_lookup_attribution_all` returns `(dict | None, str)` everywhere; `resolve_claimer` returns `ResolveOutcome(action, name, source, reason)` consistently; `ROLE_BY_VARIANT` values (`primary_foreman`/`helper`/`vac_crew`) match the RPC return columns in Task 1; `record_attribution_hold`/`summarize_attribution_holds` names match between implementation and tests.
