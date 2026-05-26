# Sub-project E — Supabase Hash-Store + Filename Token Stripping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Supabase the durable per-group change-detection hash store and strip the `_<timestamp>`/`_<hash>` tokens from generated Excel filenames, behind a default-OFF kill switch with day-one shadow writes.

**Architecture:** New `billing_audit.group_content_hash` table keyed `(wr, week_ending, variant, identifier)`. `billing_audit/writer.py` gains a fail-safe `upsert_group_hash` (shadow write) and a retry/circuit-breaker `lookup_group_hash` (authoritative read). Two env flags gate behavior: `SUPABASE_HASH_STORE_WRITE_ENABLED` (default ON — shadow write) and `SUPABASE_HASH_STORE_AUTHORITATIVE` (default OFF — flips the skip gate to read Supabase, strips filename tokens, and stops `delete_old_excel_attachments` relying on the filename hash). `hash_history.json` is retained as a local fast cache + offline fallback; a Supabase outage degrades to "regenerate," never "skip."

**Tech Stack:** Python 3.10+, `openpyxl`, Smartsheet SDK, Supabase (PostgREST via `supabase-py`), `pytest`. Spec: `docs/superpowers/specs/2026-05-25-subproject-e-supabase-hash-store-design.md`.

**Key verified anchors (line numbers approximate — search by name):**
- Filename build: `generate_excel` `output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}_{data_hash}.xlsx"` (~L6655).
- Primary skip gate: `history_key = f"{wr}|{week}|{variant}|{identifier}"`; `_prev_history_entry.get('hash') == data_hash` → `_hash_unchanged` (~L8507-8530); `ATTACHMENT_REQUIRED_FOR_SKIP` (~L8854).
- Durable backstop today: `delete_old_excel_attachments` → `extract_data_hash_from_filename(att.name)` (~L3169-3171).
- Identity parser: `build_group_identity` (~L2568) — STRONG match needs `WeekEnding`+6-digit week+6-digit timestamp; WEAK match is week-only fallback.
- Supabase writer patterns: `emit_run_fingerprint`, `freeze_row`, `with_retry`, `get_client()`, `_classify_postgrest_error`, run-global kill switch (`billing_audit/writer.py`, `billing_audit/client.py`).
- Schema: `billing_audit/schema.sql` (`feature_flag`, `pipeline_run`, `lookup_attribution`).

---

### Task 1: Config flags + Supabase schema

**Files:**
- Modify: `generate_weekly_pdfs.py` (flag block near other env flags ~L574-590; startup banner near the other `📋` lines ~L760-790)
- Modify: `billing_audit/schema.sql` (append a new table after `pipeline_run`)
- Test: `tests/test_subproject_e_hash_store.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_subproject_e_hash_store.py
import inspect
import unittest
import generate_weekly_pdfs as gwp
from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked
_ensure_smartsheet_mocked()


class TestConfigFlags(unittest.TestCase):
    def test_write_flag_default_on_is_bool(self):
        self.assertIsInstance(gwp.SUPABASE_HASH_STORE_WRITE_ENABLED, bool)

    def test_authoritative_flag_is_bool(self):
        self.assertIsInstance(gwp.SUPABASE_HASH_STORE_AUTHORITATIVE, bool)

    def test_banner_logs_both_flags(self):
        src = inspect.getsource(gwp)
        self.assertIn("📋 SUPABASE_HASH_STORE_WRITE_ENABLED=", src)
        self.assertIn("📋 SUPABASE_HASH_STORE_AUTHORITATIVE=", src)


class TestSchemaHasGroupContentHash(unittest.TestCase):
    def test_schema_defines_group_content_hash_table(self):
        import pathlib
        sql = pathlib.Path("billing_audit/schema.sql").read_text(encoding="utf-8")
        self.assertIn("billing_audit.group_content_hash", sql)
        for col in ("wr", "week_ending", "variant", "identifier", "content_hash", "updated_at"):
            self.assertIn(col, sql)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_subproject_e_hash_store.py -v`
Expected: FAIL — `AttributeError: module 'generate_weekly_pdfs' has no attribute 'SUPABASE_HASH_STORE_WRITE_ENABLED'`.

- [ ] **Step 3: Add the flags + banner (generate_weekly_pdfs.py)**

Near the other env flags (after `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`):

```python
# Sub-project E: durable Supabase change-detection hash store.
# WRITE: shadow-write the per-group hash to Supabase every run (harmless
# even while not authoritative — populates the durable store).
SUPABASE_HASH_STORE_WRITE_ENABLED = os.getenv(
    'SUPABASE_HASH_STORE_WRITE_ENABLED', '1'
).lower() in ('1', 'true', 'yes', 'on')
# AUTHORITATIVE: when ON, the skip gate reads Supabase (json cache fallback,
# regenerate on miss/outage), filenames drop the _<timestamp>/_<hash> tokens,
# and delete_old_excel_attachments stops relying on the filename hash.
# Default OFF — ship dormant; flip after the store is validated.
SUPABASE_HASH_STORE_AUTHORITATIVE = os.getenv(
    'SUPABASE_HASH_STORE_AUTHORITATIVE', '0'
).lower() in ('1', 'true', 'yes', 'on')
```

In the startup banner block (mirror the existing `📋` lines):

```python
logging.info(f"📋 SUPABASE_HASH_STORE_WRITE_ENABLED={SUPABASE_HASH_STORE_WRITE_ENABLED}")
logging.info(f"📋 SUPABASE_HASH_STORE_AUTHORITATIVE={SUPABASE_HASH_STORE_AUTHORITATIVE}")
```

- [ ] **Step 4: Add the table (billing_audit/schema.sql)**

Append after the `pipeline_run` block + its index (follow the `ADD COLUMN IF NOT EXISTS` convention used for `pipeline_run`):

```sql
-- Sub-project E: durable per-group change-detection hash store.
-- Keyed on the same 4-tuple as the engine's history_key
-- (f"{wr}|{week}|{variant}|{identifier}"). identifier defaults to ''
-- for bare primary / legacy-shape groups.
CREATE TABLE IF NOT EXISTS billing_audit.group_content_hash (
    wr            TEXT        NOT NULL,
    week_ending   DATE        NOT NULL,
    variant       TEXT        NOT NULL,
    identifier    TEXT        NOT NULL DEFAULT '',
    content_hash  TEXT        NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (wr, week_ending, variant, identifier)
);

ALTER TABLE billing_audit.group_content_hash
    ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE billing_audit.group_content_hash
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_subproject_e_hash_store.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add generate_weekly_pdfs.py billing_audit/schema.sql tests/test_subproject_e_hash_store.py
git commit -m "feat(billing): E Task 1 — hash-store flags + group_content_hash schema"
```

---

### Task 2: `lookup_group_hash` reader (billing_audit/writer.py)

**Files:**
- Modify: `billing_audit/writer.py` (add after `_lookup_attribution_all`)
- Test: `tests/test_billing_audit_shadow.py` (new class `LookupGroupHashTests`)

- [ ] **Step 1: Write the failing test**

```python
# in tests/test_billing_audit_shadow.py
class LookupGroupHashTests(unittest.TestCase):
    def setUp(self):
        import billing_audit.writer as w
        w.reset_cache_for_tests()

    def test_success_returns_hash(self):
        import billing_audit.writer as w
        client = _make_fake_supabase_client(
            _fake_rpc_response([{"content_hash": "abc123"}])
        )
        with mock.patch.object(w, "get_client", return_value=client):
            h, status = w.lookup_group_hash("90001", "2026-04-19", "primary", "Alice")
        self.assertEqual(h, "abc123")
        self.assertEqual(status, "success")

    def test_no_row_returns_none(self):
        import billing_audit.writer as w
        client = _make_fake_supabase_client(_fake_rpc_response([]))
        with mock.patch.object(w, "get_client", return_value=client):
            h, status = w.lookup_group_hash("90001", "2026-04-19", "primary", "")
        self.assertIsNone(h)
        self.assertEqual(status, "no_row")

    def test_client_none_returns_unavailable(self):
        import billing_audit.writer as w
        with mock.patch.object(w, "get_client", return_value=None):
            h, status = w.lookup_group_hash("90001", "2026-04-19", "primary", "")
        self.assertIsNone(h)
        self.assertIn(status, ("unavailable", "disabled"))
```

(Reuse `_make_fake_supabase_client` / `_fake_rpc_response` already imported in that file. If the fake builder's query shape differs from `.table(...).select(...).eq(...).execute()`, mirror whatever `_lookup_attribution_all`'s tests use.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_billing_audit_shadow.py::LookupGroupHashTests -v`
Expected: FAIL — `AttributeError: module 'billing_audit.writer' has no attribute 'lookup_group_hash'`.

- [ ] **Step 3: Implement `lookup_group_hash`**

```python
# billing_audit/writer.py
def lookup_group_hash(wr, week_ending, variant, identifier):
    """Read the durable per-group content hash from Supabase.

    Returns (content_hash | None, status) where status is one of
    'success' | 'no_row' | 'fetch_failure' | 'unavailable' | 'disabled'.
    Shares the with_retry / per-op circuit breaker / run-global kill
    switch used by the rest of this module. A genuine outage returns
    'fetch_failure' (distinct from 'no_row').
    """
    client = get_client()
    if client is None:
        return None, "unavailable"
    try:
        def _op():
            return (
                client.schema("billing_audit")
                .table("group_content_hash")
                .select("content_hash")
                .eq("wr", str(wr))
                .eq("week_ending", str(week_ending))
                .eq("variant", str(variant))
                .eq("identifier", identifier or "")
                .limit(1)
                .execute()
            )
        resp = with_retry(_op, op="lookup_group_hash")
        rows = getattr(resp, "data", None) or []
        if not rows:
            return None, "no_row"
        return rows[0].get("content_hash"), "success"
    except Exception:
        logging.exception("lookup_group_hash failed")
        return None, "fetch_failure"
```

(Match the exact client/query idiom and `with_retry` signature used by `_lookup_attribution_all` in this file — copy its shape verbatim, only changing table/columns.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_billing_audit_shadow.py::LookupGroupHashTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add billing_audit/writer.py tests/test_billing_audit_shadow.py
git commit -m "feat(billing): E Task 2 — lookup_group_hash reader"
```

---

### Task 3: `upsert_group_hash` writer (billing_audit/writer.py)

**Files:**
- Modify: `billing_audit/writer.py` (add next to `lookup_group_hash`)
- Test: `tests/test_billing_audit_shadow.py` (new class `UpsertGroupHashTests`)

- [ ] **Step 1: Write the failing test**

```python
class UpsertGroupHashTests(unittest.TestCase):
    def setUp(self):
        import billing_audit.writer as w
        w.reset_cache_for_tests()

    def test_upsert_calls_supabase(self):
        import billing_audit.writer as w
        client = _make_fake_supabase_client(_fake_rpc_response([{"content_hash": "h"}]))
        with mock.patch.object(w, "get_client", return_value=client):
            w.upsert_group_hash("90001", "2026-04-19", "primary", "Alice", "h")
        self.assertTrue(client.schema.called or client.table.called)

    def test_upsert_never_raises_on_error(self):
        import billing_audit.writer as w
        boom = mock.MagicMock()
        boom.schema.side_effect = RuntimeError("supabase down")
        with mock.patch.object(w, "get_client", return_value=boom):
            # Must not raise — fail-safe like freeze_row.
            w.upsert_group_hash("90001", "2026-04-19", "primary", "Alice", "h")

    def test_upsert_noop_when_client_none(self):
        import billing_audit.writer as w
        with mock.patch.object(w, "get_client", return_value=None):
            w.upsert_group_hash("90001", "2026-04-19", "primary", "", "h")  # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_billing_audit_shadow.py::UpsertGroupHashTests -v`
Expected: FAIL — no attribute `upsert_group_hash`.

- [ ] **Step 3: Implement `upsert_group_hash`**

```python
def upsert_group_hash(wr, week_ending, variant, identifier, content_hash):
    """Best-effort durable write of a per-group content hash. Fail-safe:
    catches its own errors and never raises (mirrors freeze_row), so a
    Supabase problem can never break the billing pipeline."""
    client = get_client()
    if client is None:
        return
    try:
        def _op():
            return (
                client.schema("billing_audit")
                .table("group_content_hash")
                .upsert(
                    {
                        "wr": str(wr),
                        "week_ending": str(week_ending),
                        "variant": str(variant),
                        "identifier": identifier or "",
                        "content_hash": content_hash,
                        "updated_at": "now()",
                    },
                    on_conflict="wr,week_ending,variant,identifier",
                )
                .execute()
            )
        with_retry(_op, op="upsert_group_hash")
    except Exception:
        logging.exception("upsert_group_hash failed (non-fatal)")
```

(If the installed `supabase-py` rejects the literal `"now()"`, drop the `updated_at` key and let the column DEFAULT NOW() apply — verify against the version pinned in `requirements.txt`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_billing_audit_shadow.py::UpsertGroupHashTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add billing_audit/writer.py tests/test_billing_audit_shadow.py
git commit -m "feat(billing): E Task 3 — upsert_group_hash fail-safe writer"
```

---

### Task 4: `build_group_identity` clean-name support (KEY RISK)

**Files:**
- Modify: `generate_weekly_pdfs.py` `build_group_identity` (~L2643-2697 candidate-selection block)
- Test: `tests/test_subproject_e_hash_store.py` (new class `TestBuildGroupIdentityCleanNames`)

**Why:** Today the parser's STRONG `WeekEnding` match requires a 6-digit timestamp after the 6-digit week. Clean names have NO timestamp, so every clean name falls onto the WEAK (week-only) path. The parser must select the structural `WeekEnding` unambiguously for clean names AND still parse legacy token-bearing names (both coexist during migration).

- [ ] **Step 1: Write the failing test**

```python
class TestBuildGroupIdentityCleanNames(unittest.TestCase):
    def _id(self, name):
        return generate_weekly_pdfs.build_group_identity(name)

    def test_clean_bare_primary(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926.xlsx"),
            ("90001", "041926", "primary", None),
        )

    def test_clean_primary_user(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_User_Jane_Smith.xlsx"),
            ("90001", "041926", "primary", "Jane_Smith"),
        )

    def test_clean_helper(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_Helper_Bob.xlsx"),
            ("90001", "041926", "helper", "Bob"),
        )

    def test_clean_vaccrew_named(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_VacCrew_Vic.xlsx"),
            ("90001", "041926", "vac_crew", "Vic"),
        )

    def test_clean_vaccrew_bare(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_VacCrew.xlsx"),
            ("90001", "041926", "vac_crew", ""),
        )

    def test_clean_reducedsub_user(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_ReducedSub_User_Sue.xlsx"),
            ("90001", "041926", "reduced_sub", "Sue"),
        )

    def test_legacy_tokened_name_still_parses(self):
        # Coexistence: old attachments keep timestamp+hash.
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_120000_User_Jane_Smith_abcdef0123456789.xlsx"),
            ("90001", "041926", "primary", "Jane_Smith"),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestBuildGroupIdentityCleanNames -v`
Expected: clean-name cases FAIL (the trailing-hash assumption in the variant-suffix/identifier extraction or the strong/weak selection mis-parses); the legacy case PASSES. Capture the actual failures before fixing.

- [ ] **Step 3: Make the parser timestamp-independent**

The candidate-selection block already keeps a WEAK (week-only) path; the fix is to make the WEAK path safe as the PRIMARY path for clean names while keeping the STRONG path for legacy names. The structural `WeekEnding` is always the LEFTMOST `WeekEnding` immediately followed by a 6-digit week, in BOTH formats (a sanitized identifier can only contain a `WeekEnding_<6digits>` AFTER the structural one). So selection becomes: prefer the leftmost STRONG match if present (legacy), else the leftmost WEAK match (clean) — which the current code already does (`_strong_candidates[0]` else `_weak_candidates[0]`).

The real fix is in the **identifier/variant tail extraction** (the code after `tail = parts[we_idx + 2:]`, ~L2697 onward): it currently assumes the LAST tail token is the 16-char hash and strips it. For a clean name there is no hash token, so the identifier must NOT drop the last token. Make hash-stripping conditional:

```python
tail = parts[we_idx + 2:]
# Sub-project E: clean names have no trailing 16-char hash token. Only
# strip a trailing token when it actually looks like the legacy hash
# (16 chars, hex-ish) so clean-name identifiers keep their last segment.
if tail and len(tail[-1]) == 16 and all(c in '0123456789abcdef' for c in tail[-1].lower()):
    tail = tail[:-1]
# Legacy names also carry a 6-digit timestamp at tail[0] (right after the
# week). Clean names do not. Strip a leading 6-digit timestamp only when
# the NEXT token is a variant marker or there is more than just the date —
# i.e. when tail[0] is 6 digits AND (len(tail) == 0 after it OR tail[1]
# is a known marker / identifier). Simplest robust rule: drop a leading
# 6-digit all-digit token (timestamp) iff present.
if tail and len(tail[0]) == 6 and tail[0].isdigit():
    tail = tail[1:]
```

Then keep the existing earliest-reserved-token dispatch over `tail` unchanged. Verify the dispatch handles an empty `tail` (bare primary → `('primary', None)`).

> NOTE: the exact edit must be reconciled with the real code after `tail = parts[we_idx + 2:]`. Read that block first; the two conditional strips above replace the unconditional timestamp+hash handling. Preserve the reserved-token dispatch and the D earliest-position hardening.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestBuildGroupIdentityCleanNames -v`
Then the full existing parser suites (must stay green):
`python -m pytest tests/test_primary_claim_attribution.py tests/test_vac_crew_claim_attribution.py tests/test_subcontractor_primary_claim_attribution.py -k "identity or Identity or build_group" -v`
Expected: PASS (clean + legacy).

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subproject_e_hash_store.py
git commit -m "feat(billing): E Task 4 — build_group_identity parses clean (token-less) names"
```

---

### Task 5: Deterministic clean filename in `generate_excel` (gated)

**Files:**
- Modify: `generate_weekly_pdfs.py` `generate_excel` filename block (~L6653-6655)
- Test: `tests/test_subproject_e_hash_store.py` (`TestCleanFilename`)

- [ ] **Step 1: Write the failing test**

```python
class TestCleanFilename(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._orig_auth = gwp.SUPABASE_HASH_STORE_AUTHORITATIVE
        self._orig_out = gwp.OUTPUT_FOLDER
        self._tmp = tempfile.TemporaryDirectory()
        gwp.OUTPUT_FOLDER = self._tmp.name

    def tearDown(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = self._orig_auth
        gwp.OUTPUT_FOLDER = self._orig_out
        self._tmp.cleanup()

    def _row(self, foreman="PF"):
        import datetime
        return {
            'Work Request #': '90001', 'Weekly Reference Logged Date': '2026-04-19',
            'Units Completed?': True, 'Units Total Price': '$100.00',
            'CU': 'XYZ', 'Work Type': 'Install', 'Quantity': 1,
            'Customer Name': 'C', 'Foreman': foreman, 'Dept #': '500', 'Job #': 'J-1',
            '__effective_user': foreman, '__current_foreman': foreman,
            '__variant': 'primary', '__week_ending_date': datetime.datetime(2026, 4, 19),
        }

    def _name(self):
        import os, datetime
        r = gwp.generate_excel('041926_90001', [self._row()],
                               datetime.datetime(2026, 4, 19), data_hash='deadbeefcafe0001')
        return os.path.basename(r[0])

    def test_authoritative_on_strips_timestamp_and_hash(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        name = self._name()
        self.assertEqual(name, 'WR_90001_WeekEnding_041926_User_PF.xlsx')

    def test_authoritative_off_keeps_tokens(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = False
        name = self._name()
        self.assertIn('deadbeefcafe0001', name)
        self.assertTrue(name.endswith('.xlsx'))
```

(Primary partitioning requires `PRIMARY_CLAIM_ATTRIBUTION_ENABLED` + `RES_GROUPING_MODE in ('helper','both')` for the `_User_` suffix — set them in setUp if the default does not already yield `_User_PF`. If attribution is off in the test env, assert the bare `WR_90001_WeekEnding_041926.xlsx` instead.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestCleanFilename -v`
Expected: `test_authoritative_on_strips_timestamp_and_hash` FAILS (name still has timestamp/hash).

- [ ] **Step 3: Gate the filename construction**

Replace the `output_filename` block (~L6653-6655):

```python
if SUPABASE_HASH_STORE_AUTHORITATIVE:
    # Sub-project E: deterministic clean name — durable hash lives in
    # Supabase, so no _<timestamp>/_<hash> tokens in the filename.
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}{variant_suffix}.xlsx"
elif data_hash:
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}_{data_hash}.xlsx"
else:
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}.xlsx"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestCleanFilename -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subproject_e_hash_store.py
git commit -m "feat(billing): E Task 5 — deterministic clean filename when authoritative"
```

---

### Task 6: Shadow-write the group hash into the generation path (gated on WRITE flag)

**Files:**
- Modify: `generate_weekly_pdfs.py` main loop, right after a group's `data_hash` is computed and `history_key` known (~L8507-8530 area) OR where `hash_history[history_key]` is written after a successful generation/upload.
- Test: `tests/test_subproject_e_hash_store.py` (`TestShadowWrite`)

- [ ] **Step 1: Write the failing test** (source-level + call guard)

```python
class TestShadowWrite(unittest.TestCase):
    def test_upsert_call_present_and_gated(self):
        import inspect
        src = inspect.getsource(gwp)
        self.assertIn("upsert_group_hash(", src)
        # Gated on the WRITE flag.
        self.assertRegex(
            src,
            r"SUPABASE_HASH_STORE_WRITE_ENABLED[\s\S]{0,400}upsert_group_hash\(",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestShadowWrite -v`
Expected: FAIL — `upsert_group_hash(` absent.

- [ ] **Step 3: Wire the shadow write**

Where `hash_history[history_key] = {...}` is set after a group is generated/uploaded (the json-cache write), add the parallel durable write, gated + fail-safe:

```python
if (
    SUPABASE_HASH_STORE_WRITE_ENABLED
    and BILLING_AUDIT_AVAILABLE
    and not TEST_MODE
):
    try:
        _billing_audit_writer.upsert_group_hash(
            wr_num, week_raw, variant, identifier or '', data_hash
        )
    except Exception:
        logging.exception("E shadow hash write failed (non-fatal)")
```

(Use the same module handle the engine already uses for `freeze_row` — e.g. `_billing_audit_writer`. `week_raw` is `MMDDYY`; if the table column is `DATE`, convert via the same week-ending date the group already carries — pass the ISO date used elsewhere, not the MMDDYY string. Reconcile the date format with Task 2/3's `week_ending` type at execution time and keep lookup+upsert consistent.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestShadowWrite -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subproject_e_hash_store.py
git commit -m "feat(billing): E Task 6 — shadow-write group hash to Supabase"
```

---

### Task 7: Authoritative skip gate (read Supabase, json fallback, regenerate on miss)

**Files:**
- Modify: `generate_weekly_pdfs.py` skip-gate block (~L8507-8530: compute `_hash_unchanged`)
- Test: `tests/test_subproject_e_hash_store.py` (`TestAuthoritativeSkipGate`) — source-level + targeted behavior

- [ ] **Step 1: Write the failing test**

```python
class TestAuthoritativeSkipGate(unittest.TestCase):
    def test_gate_reads_supabase_when_authoritative(self):
        import inspect
        src = inspect.getsource(gwp)
        # When authoritative, the unchanged decision must consult lookup_group_hash.
        self.assertRegex(
            src,
            r"SUPABASE_HASH_STORE_AUTHORITATIVE[\s\S]{0,600}lookup_group_hash\(",
        )
        # Fallback to the json cache must remain reachable (not deleted).
        self.assertIn("_prev_history_entry", src)
```

(Add a behavioral test too if a thin helper is extracted — see Step 3.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestAuthoritativeSkipGate -v`
Expected: FAIL — `lookup_group_hash(` not near the gate.

- [ ] **Step 3: Implement the gate (extract a testable helper)**

Add a pure helper near the skip gate so the decision is unit-testable:

```python
def _resolve_unchanged_for_skip(history_key, data_hash, hash_history,
                                wr_num, week_iso, variant, identifier):
    """Return True iff the group's content hash is unchanged vs the durable
    store. Supabase is authoritative when SUPABASE_HASH_STORE_AUTHORITATIVE;
    on outage/miss it falls back to the hash_history.json cache; a true miss
    returns False (regenerate — the safe default)."""
    if SUPABASE_HASH_STORE_AUTHORITATIVE and BILLING_AUDIT_AVAILABLE and not TEST_MODE:
        _h, _status = _billing_audit_writer.lookup_group_hash(
            wr_num, week_iso, variant, identifier or '')
        if _status == 'success':
            return _h == data_hash
        if _status == 'no_row':
            return False  # new/never-stored group → regenerate
        # fetch_failure / unavailable / disabled → fall through to json cache.
    _prev = hash_history.get(history_key)
    return bool(_prev and _prev.get('hash') == data_hash)
```

Then replace the inline `_hash_unchanged = bool(_prev_history_entry and ...)` with:

```python
_hash_unchanged = (
    _resolve_unchanged_for_skip(
        history_key, data_hash, hash_history,
        wr_num, week_iso, variant, identifier)
    if _history_eligible_for_skip else False
)
```

Keep `_history_eligible_for_skip` (FORCE_GENERATION / REGEN_WEEKS / RESET_* gating) and the `ATTACHMENT_REQUIRED_FOR_SKIP` check downstream **unchanged** — a matching hash with a missing attachment must still regenerate. Add unit tests for `_resolve_unchanged_for_skip` covering: authoritative success-match → True; success-mismatch → False; no_row → False; fetch_failure → json fallback (True/False); authoritative off → json only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestAuthoritativeSkipGate -v`
Then full suite: `python -m pytest tests/ -q`
Expected: PASS / no regressions.

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subproject_e_hash_store.py
git commit -m "feat(billing): E Task 7 — Supabase-authoritative skip gate with json fallback"
```

---

### Task 8: `delete_old_excel_attachments` clean-name handling

**Files:**
- Modify: `generate_weekly_pdfs.py` `delete_old_excel_attachments` (~L3114-3190)
- Test: `tests/test_subproject_e_hash_store.py` (`TestDeleteOldCleanNames`)

- [ ] **Step 1: Write the failing test**

```python
class TestDeleteOldCleanNames(unittest.TestCase):
    def test_clean_name_does_not_short_circuit_on_filename_hash(self):
        import inspect
        src = inspect.getsource(gwp.delete_old_excel_attachments)
        # When authoritative, the unchanged-skip must NOT depend on
        # extract_data_hash_from_filename (it returns None for clean names).
        self.assertIn("SUPABASE_HASH_STORE_AUTHORITATIVE", src)
```

(Add a behavioral test driving `delete_old_excel_attachments` with a mocked client whose attachment list contains an old token-named file + a clean-named file for the same identity, asserting the old one is selected for deletion via `build_group_identity` identity match — mirror the harness in `tests/test_subcontractor_helper_shadow_rescue.py::TestLegacyHelperTargetCleanupE2E`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestDeleteOldCleanNames -v`
Expected: FAIL — `SUPABASE_HASH_STORE_AUTHORITATIVE` not referenced in the function.

- [ ] **Step 3: Gate the filename-hash short-circuit**

In `delete_old_excel_attachments`, wrap the `extract_data_hash_from_filename` skip (~L3169-3171) so it only applies in legacy mode:

```python
existing_hash = extract_data_hash_from_filename(att.name)
if (
    not SUPABASE_HASH_STORE_AUTHORITATIVE
    and existing_hash == current_data_hash
):
    logging.info(f"⏩ Unchanged ({variant} WR {wr_num} Week {week_raw}) hash {current_data_hash}; skipping regeneration & upload")
    return ...  # preserve the existing return shape
```

Identity-based selection of which attachments to delete (via `build_group_identity`) is unchanged and now pairs old token-named attachments with new clean ones (Task 4).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestDeleteOldCleanNames -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subproject_e_hash_store.py
git commit -m "feat(billing): E Task 8 — delete_old_excel_attachments clean-name handling"
```

---

### Task 9: Migration / cutover end-to-end test

**Files:**
- Test only: `tests/test_subproject_e_hash_store.py` (`TestMigrationCutover`)

- [ ] **Step 1: Write the test**

```python
class TestMigrationCutover(unittest.TestCase):
    def test_first_authoritative_run_regenerates_on_empty_store(self):
        import billing_audit.writer as w
        # Empty store → lookup returns no_row → unchanged=False → regenerate.
        with mock.patch.object(w, "lookup_group_hash", return_value=(None, "no_row")):
            self.assertFalse(
                gwp._resolve_unchanged_for_skip(
                    "90001|041926|primary|", "h", {}, "90001", "2026-04-19", "primary", "")
            )

    def test_shadow_populated_store_allows_skip(self):
        import billing_audit.writer as w
        with mock.patch.object(w, "lookup_group_hash", return_value=("h", "success")), \
             mock.patch.object(gwp, "SUPABASE_HASH_STORE_AUTHORITATIVE", True), \
             mock.patch.object(gwp, "BILLING_AUDIT_AVAILABLE", True), \
             mock.patch.object(gwp, "TEST_MODE", False):
            self.assertTrue(
                gwp._resolve_unchanged_for_skip(
                    "90001|041926|primary|", "h", {}, "90001", "2026-04-19", "primary", "")
            )

    def test_extract_hash_returns_none_for_clean_name(self):
        self.assertIsNone(
            gwp.extract_data_hash_from_filename("WR_90001_WeekEnding_041926_User_PF.xlsx"))
```

(Patch `_billing_audit_writer.lookup_group_hash` at whatever attribute the engine actually calls — reconcile with Task 7's call site.)

- [ ] **Step 2: Run + verify**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestMigrationCutover -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_subproject_e_hash_store.py
git commit -m "test(billing): E Task 9 — migration/cutover behavior"
```

---

### Task 10: Workflow pin + docs

**Files:**
- Modify: `.github/workflows/weekly-excel-generation.yml` (env block)
- Modify: `website/docs/reference/environment.md`
- Test: `tests/test_subproject_e_hash_store.py` (`TestWorkflowPinned`)

- [ ] **Step 1: Write the failing test**

```python
class TestWorkflowPinned(unittest.TestCase):
    def test_flags_pinned_in_workflow(self):
        import pathlib
        wf = pathlib.Path(".github/workflows/weekly-excel-generation.yml").read_text(encoding="utf-8")
        self.assertIn("SUPABASE_HASH_STORE_WRITE_ENABLED:", wf)
        self.assertIn("SUPABASE_HASH_STORE_AUTHORITATIVE:", wf)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestWorkflowPinned -v`
Expected: FAIL.

- [ ] **Step 3: Pin the flags + document**

In `weekly-excel-generation.yml` env block (mirror the other pinned flags):

```yaml
          # Sub-project E (dormant ship): shadow-write the durable Supabase
          # hash store from day one; keep the authoritative read + filename
          # token stripping OFF until validated in production.
          SUPABASE_HASH_STORE_WRITE_ENABLED: '1'
          SUPABASE_HASH_STORE_AUTHORITATIVE: '0'
```

In `website/docs/reference/environment.md`, add a "Sub-project E — Supabase hash store" section documenting both flags, the dormant rollout, the OPERATOR step (apply `schema.sql` + reload PostgREST schema cache), and the one-line revert (`SUPABASE_HASH_STORE_AUTHORITATIVE=0`).

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestWorkflowPinned -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/weekly-excel-generation.yml website/docs/reference/environment.md tests/test_subproject_e_hash_store.py
git commit -m "feat(billing): E Task 10 — pin E flags + document dormant rollout"
```

---

### Task 11: Production invariants + Living Ledger + full suite

**Files:**
- Test: `tests/test_subproject_e_hash_store.py` (`TestProductionInvariants`)
- Modify: `CLAUDE.md` (Living Ledger entry)

- [ ] **Step 1: Write source-grep guard tests**

```python
class TestProductionInvariants(unittest.TestCase):
    def setUp(self):
        import inspect
        self.src = inspect.getsource(gwp)

    def test_clean_filename_gated(self):
        self.assertRegex(
            self.src,
            r"SUPABASE_HASH_STORE_AUTHORITATIVE[\s\S]{0,200}"
            r'WR_\{wr_num\}_WeekEnding_\{week_end_raw\}\{variant_suffix\}\.xlsx',
        )

    def test_skip_gate_consults_supabase(self):
        self.assertIn("lookup_group_hash(", self.src)

    def test_shadow_write_present(self):
        self.assertIn("upsert_group_hash(", self.src)

    def test_attachment_required_preserved(self):
        self.assertIn("ATTACHMENT_REQUIRED_FOR_SKIP", self.src)
```

- [ ] **Step 2: Run to verify**

Run: `python -m pytest tests/test_subproject_e_hash_store.py::TestProductionInvariants -v`
Expected: PASS (after Tasks 5/6/7 landed).

- [ ] **Step 3: Add the Living Ledger entry**

Append a `[YYYY-MM-DD HH:MM]` entry to `CLAUDE.md` documenting: the durable-store migration, the two flags + dormant rollout, the fail-safe-to-regenerate contract, the `build_group_identity` clean-name parser change, the no-bulk-migration self-healing cutover, and the new rule: *"the durable change-detection hash lives in `billing_audit.group_content_hash`; filenames are identity-only (no hash/timestamp) when authoritative; a Supabase outage degrades to regenerate, never skip."*

- [ ] **Step 4: Full suite + syntax**

Run: `python -m py_compile generate_weekly_pdfs.py && python -m pytest tests/ -q`
Expected: 0 failed; ~30+ net new tests.

- [ ] **Step 5: Commit**

```bash
git add tests/test_subproject_e_hash_store.py CLAUDE.md
git commit -m "feat(billing): E Task 11 — production invariants + Living Ledger"
```

---

## Self-Review

**Spec coverage:** schema (T1), writer/reader (T2-T3), clean-name parser (T4), clean filename (T5), shadow write (T6), authoritative gate + json fallback (T7), cleanup clean-name handling (T8), migration (T9), workflow pin + docs (T10), invariants + ledger (T11). All spec sections covered.

**Open reconciliations for the executor (resolve against live code, not placeholders to skip):**
1. `week_ending` type: the Supabase column is `DATE`; the engine carries both `week_raw` (`MMDDYY`) and a week-ending `datetime`. Pick ONE representation and use it consistently in `upsert_group_hash`, `lookup_group_hash`, and both call sites (recommend the ISO `YYYY-MM-DD` string from the group's `__week_ending_date`).
2. `_billing_audit_writer` handle: use whatever module alias the engine already calls `freeze_row` / `emit_run_fingerprint` through.
3. Task 4's tail edit must be reconciled with the real code after `tail = parts[we_idx + 2:]` (read it first); preserve the D earliest-reserved-token dispatch.
4. `delete_old_excel_attachments` return shape (Task 8) — preserve exactly.

**Placeholder scan:** none — every code step shows real code; reconciliation notes point at specific live anchors.
