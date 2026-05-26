# Phase 2: Attribution Bulk-Prefetch + Historical Claimer Remediation - Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 10 new/modified files
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `billing_audit/schema.sql` | config/DDL | request-response | `billing_audit/schema.sql` (existing `lookup_attribution` RPC, lines 249-277) | exact — same file, extending a sibling RPC |
| `billing_audit/writer.py` | service | request-response | `billing_audit/writer.py` `_lookup_attribution_all` (L754-837), `lookup_group_hash` (L995-1068) | exact — same file, sibling reader functions |
| `generate_weekly_pdfs.py` (4 pre-pass blocks → bulk map) | service/transform | batch | `generate_weekly_pdfs.py` Subproject B pre-pass (L5460-5535), `_attribution_resolution_cutoff` (L5335-5395) | exact — same function, sibling pre-pass blocks |
| `generate_weekly_pdfs.py` (remove scope helpers + banner) | config | batch | `generate_weekly_pdfs.py` L637-647 env-read block, L838-841 banner | exact — same file, inline removals |
| `generate_weekly_pdfs.py` (remediation mode) | service | batch | `generate_weekly_pdfs.py` `cleanup_untracked_sheet_attachments` (L2963-3060), `build_group_identity` (L2963 signature) | role-match — same destructive-attachment-cleanup pattern + dry-run-first precedent |
| `.github/workflows/weekly-excel-generation.yml` | config | — | `.github/workflows/weekly-excel-generation.yml` L375-464 (existing sub-project kill-switch pin block) | exact — same file, same pin block |
| `website/docs/reference/environment.md` | docs | — | `website/docs/reference/environment.md` existing `VAC_CREW_LEGACY_CLEANUP_ENABLED`, `SUPABASE_HASH_STORE_AUTHORITATIVE` sections | exact — same file, sibling env-var doc blocks |
| `tests/test_billing_audit_shadow.py` | test | request-response | `tests/test_billing_audit_shadow.py` `LookupGroupHashTests` (L4978-5057) | exact — same file, sibling reader test class |
| `tests/test_primary_claim_attribution.py` | test | batch | `tests/test_primary_claim_attribution.py` `TestPrimaryClaimerPrePassEmission` (existing) | exact — same file, extend with historical-regression class |
| `tests/test_attribution_resolution_scope.py` | test | — | DELETE — functionality replaced by historical-regression test in `test_primary_claim_attribution.py` | superseded |

---

## Pattern Assignments

### `billing_audit/schema.sql` — `lookup_attribution_bulk` RPC (new)

**Analog:** `billing_audit/schema.sql` lines 249-277 (`lookup_attribution` RPC)

**Role:** DDL / Supabase RPC definition
**Data flow:** request-response (PostgREST function)

**Existing RPC pattern to extend** (lines 249-277 — copy this structure exactly):
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
```

**New bulk RPC shape** (replaces the `WHERE` clause + adds `LATERAL jsonb_to_recordset` join; CASE block is VERBATIM copy — one source of truth per D-01):
```sql
CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(
    p_wr_weeks jsonb   -- e.g. '[{"wr":"90001","week_ending":"2026-04-19"}, ...]'
)
RETURNS TABLE (
    wr                TEXT,
    week_ending       DATE,
    smartsheet_row_id BIGINT,
    primary_foreman   TEXT,
    helper            TEXT,
    helper_dept       TEXT,
    vac_crew          TEXT,
    source_run_id     TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        s.wr,
        s.week_ending,
        s.smartsheet_row_id,
        -- EXACT same CASE blocks as lookup_attribution above (D-01: one source of truth)
        CASE WHEN s.frozen_primary     LIKE '#%' OR btrim(s.frozen_primary)     = '' THEN NULL ELSE s.frozen_primary     END,
        CASE WHEN s.frozen_helper      LIKE '#%' OR btrim(s.frozen_helper)      = '' THEN NULL ELSE s.frozen_helper      END,
        CASE WHEN s.frozen_helper_dept LIKE '#%' OR btrim(s.frozen_helper_dept) = '' THEN NULL ELSE s.frozen_helper_dept END,
        CASE WHEN s.frozen_vac_crew    LIKE '#%' OR btrim(s.frozen_vac_crew)    = '' THEN NULL ELSE s.frozen_vac_crew    END,
        s.source_run_id
    FROM jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)
    JOIN billing_audit.attribution_snapshot AS s
      ON s.wr = q.wr AND s.week_ending = q.week_ending;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution_bulk(jsonb) TO service_role;
```

**Co-ship DDL pattern** (from `group_content_hash` block, lines 128-169 — new DDL must follow the same operator-instruction comment block + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` idempotency guards + `GRANT EXECUTE ... TO service_role`):
```sql
-- ── lookup_attribution_bulk (RPC) ────────────────────────────────
-- [operator instruction comment block — schema must be in Exposed schemas,
--  NOTIFY pgrst, 'reload schema'; required after apply]
-- OPERATOR: apply this CREATE OR REPLACE in the Supabase SQL Editor,
-- then run `NOTIFY pgrst, 'reload schema';` (or Project Settings →
-- API → Reload schema cache). Required before the bulk-prefetch
-- fix resolves real claimers at runtime (D-01 operator coordination).
```

---

### `billing_audit/writer.py` — `prefetch_attribution` + map-aware `resolve_claimer` (new/modified)

**Analog:** `billing_audit/writer.py` `_lookup_attribution_all` (lines 754-837) and `lookup_group_hash` (lines 995-1068)

**Role:** service (Supabase reader)
**Data flow:** request-response

**Imports pattern** (copy from the top of writer.py — already present, no new imports needed):
```python
import datetime
import logging
from typing import NamedTuple
from billing_audit.client import get_client, with_retry
import re
_WR_SANITIZE = re.compile(r'[^\w\-]')
```

**Fail-safe reader shell** — copy `_lookup_attribution_all` (lines 754-837) and `lookup_group_hash` (lines 995-1068) as the structural template:
```python
def prefetch_attribution(
    pairs: set[tuple[str, datetime.date]],
) -> tuple[dict[tuple[str, datetime.date, int], dict], str]:
    """Bulk-load frozen attribution for the run's (wr, week_ending) set.

    Returns ((wr, week_ending, smartsheet_row_id) -> roles-dict, status).
    status ∈ 'success' | 'no_row' | 'fetch_failure' | 'unavailable'.

    Fail-safe: NEVER raises; a Supabase failure returns ({}, 'fetch_failure')
    so resolve_claimer applies each variant's documented fallback (D-04).
    Reuses with_retry(op="lookup_attribution_bulk") — DISTINCT op id so a
    bulk-read outage cannot disable freeze_attribution / pipeline_run_* /
    lookup_attribution / lookup_group_hash (op-isolation, D-13).
    """
    from billing_audit import client as _client_mod

    client = get_client()
    if client is None:
        if _client_mod._global_disable_reason is not None:
            return {}, "fetch_failure"
        return {}, "unavailable"

    if not pairs:
        return {}, "no_row"

    # chunk pairs (≤ ~500/payload — Pitfall 2 sizing: ~45 bytes/pair,
    # conservative 500 is 2 orders of magnitude under the ~1 MB limit)
    _CHUNK_SIZE = 500
    pair_list = list(pairs)
    chunks = [pair_list[i:i + _CHUNK_SIZE]
              for i in range(0, len(pair_list), _CHUNK_SIZE)]

    result_map: dict[tuple[str, datetime.date, int], dict] = {}
    overall_status = "no_row"

    for chunk in chunks:
        payload = [
            {"wr": _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50],
             "week_ending": we.isoformat()}
            for wr, we in chunk
        ]

        def _invoke(_p=payload):
            return (
                client.schema("billing_audit")
                .rpc("lookup_attribution_bulk", {"p_wr_weeks": _p})
                .execute()
            )

        try:
            result = with_retry(_invoke, op="lookup_attribution_bulk")
            if result is None:
                return {}, "fetch_failure"
            data = getattr(result, "data", None) or []
            if isinstance(data, dict):
                data = [data] if data else []
            for row in data:
                if not isinstance(row, dict):
                    continue
                try:
                    key = (
                        str(row["wr"]),
                        datetime.date.fromisoformat(str(row["week_ending"])),
                        int(row["smartsheet_row_id"]),
                    )
                except (KeyError, ValueError, TypeError):
                    continue
                result_map[key] = row
            if data:
                overall_status = "success"
        except Exception:
            logging.warning(
                "⚠️ Attribution bulk prefetch hit an unexpected error; "
                "treating as fetch_failure (HOLD for B/C, use-current for D)."
            )
            return {}, "fetch_failure"

    return result_map, overall_status
```

**Map-aware `resolve_claimer` modification** — add `prefetched_map` keyword-only param; replace the `_lookup_attribution_all(...)` call with a map lookup that yields the same `(row, status)` shape:

**Existing `resolve_claimer` signature** (lines 869-877 — the ONLY change is adding `prefetched_map`):
```python
def resolve_claimer(
    variant: str,
    current_value: str | None,
    *,
    wr: str,
    week_ending: datetime.date | None,
    row_id: int,
    enabled: bool,
    prefetched_map: dict | None = None,   # NEW — D-03
) -> ResolveOutcome:
```

**Map-aware lookup injection** — replaces only the `_lookup_attribution_all(...)` call at line 893; everything below it (ROLE_BY_VARIANT lookup, frozen_str check, ResolveOutcome returns) is UNCHANGED:
```python
    if not enabled:
        return ResolveOutcome("use", current_value, "current", "disabled")

    # D-03: if a preloaded map is provided, use it for O(1) lookup
    # instead of a per-row RPC. The (row, status) shape is identical
    # to _lookup_attribution_all so the decision table below is unchanged.
    if prefetched_map is not None:
        # Overall load status: if the map is empty AND it was a
        # fetch_failure, the caller signals that by passing a sentinel
        # (convention: map is {} and status is tracked separately).
        # Simplest shape: map non-None + key present → (row, "success");
        # map non-None + key absent → (None, "no_row") for genuine
        # no-frozen-data; map is {} (total failure) is handled by
        # fetch_failure sentinel from prefetch_attribution caller.
        _key = (wr, week_ending, row_id) if week_ending and row_id else None
        if _key is not None and _key in prefetched_map:
            row, status = prefetched_map[_key], "success"
        else:
            row, status = None, "no_row"
    else:
        row, status = _lookup_attribution_all(wr, week_ending, row_id)

    # --- remainder of resolve_claimer UNCHANGED from line 894 onwards ---
    if status == "unavailable":
        return ResolveOutcome("use", current_value, "current", "disabled")
    if status == "fetch_failure":
        return ResolveOutcome("hold", None, None, "fetch_failure")
    if status == "no_row" or row is None:
        return ResolveOutcome("use", current_value, "current", "no_history")
    role = ROLE_BY_VARIANT.get(variant, "primary_foreman")
    frozen = row.get(role)
    frozen_str = str(frozen).strip() if frozen is not None else ""
    if frozen_str:
        return ResolveOutcome("use", frozen_str, "frozen", "success")
    return ResolveOutcome("use", current_value, "current", "no_history")
```

**`ROLE_BY_VARIANT` and `ResolveOutcome`** (lines 840-866 — copy VERBATIM, no changes):
```python
class ResolveOutcome(NamedTuple):
    action: str       # 'use' | 'hold'
    name: str | None
    source: str | None
    reason: str       # 'success' | 'no_history' | 'disabled' | 'fetch_failure'

ROLE_BY_VARIANT: dict[str, str] = {
    "primary": "primary_foreman",
    "reduced_sub": "primary_foreman",
    "aep_billable": "primary_foreman",
    "helper": "helper",
    "reduced_sub_helper": "helper",
    "aep_billable_helper": "helper",
    "vac_crew": "vac_crew",
}
```

---

### `generate_weekly_pdfs.py` — Replace 4 pre-pass blocks with bulk map (modified)

**Analog:** `generate_weekly_pdfs.py` existing Subproject B pre-pass (lines 5460-5535), Subproject C pre-pass (lines 5537-5608), Subproject D pre-pass (lines 5610-5704)

**Role:** service/transform (row grouping)
**Data flow:** batch

**Remove these helpers entirely** (D-05 — delete the function bodies and their callers):
- `_attribution_resolution_cutoff()` (lines 5335-5352)
- `_attribution_week_in_scope()` (lines 5354-5395)
- Env-read block: `ATTRIBUTION_RESOLUTION_WEEKS` (lines 637-647)
- Banner line: L838-841

**Remove these 4 scope gates** (one `if not _attribution_week_in_scope(_we_d): continue` in each of the 4 blocks):
- Subproject B gate: line 5492
- Subproject C gate: line 5565
- Subproject D gate: line 5657
- Sub-helper direct-lookup gate: line 6203

**Bulk map build — replace all 4 pre-pass ThreadPoolExecutor blocks** with a single prefetch call placed BEFORE all four (at the top of `group_source_rows`, after `_bug_c_warning_seen` initialization):

The pair-set assembly pattern (copy structure from lines 5473-5493, generalized):
```python
# Phase 2 (2026-05-26): single bulk attribution prefetch for ALL variants.
# Replaces the 4 per-row pre-pass blocks (B/C/D/sub-helper). The run's
# exact (wr, week_ending) set is bounded to completed rows across all
# variants — no recency gate (D-05/D-02: exact-set removes the root cause).
_attr_pairs: set[tuple[str, datetime.date]] = set()
if BILLING_AUDIT_AVAILABLE and (
    SUBCONTRACTOR_RATE_VARIANTS_ENABLED
    or VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
    or PRIMARY_CLAIM_ATTRIBUTION_ENABLED
    or SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
):
    for _r in rows:
        _wr_raw = _r.get('Work Request #')
        _ld = _r.get('Weekly Reference Logged Date')
        if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
            continue
        _we = excel_serial_to_date(_ld)
        if _we is None:
            continue
        _we_d = _we.date() if isinstance(_we, datetime.datetime) else _we
        # NOTE: NO _attribution_week_in_scope gate — D-05 removes it.
        _attr_pairs.add((str(_wr_raw).split('.')[0], _we_d))

_attr_map: dict = {}
_attr_status: str = "unavailable"
if _attr_pairs:
    try:
        from billing_audit.writer import prefetch_attribution as _prefetch_attribution
        _attr_map, _attr_status = _prefetch_attribution(_attr_pairs)
    except Exception:
        logging.exception(
            "⚠️ Attribution bulk prefetch failed; falling back to "
            "use-current for all variants (D-04 per-variant policy applies)"
        )
        _attr_map, _attr_status = {}, "fetch_failure"
```

**Consumption at each variant pre-pass site** — replaces the ThreadPoolExecutor loop. The per-variant map (e.g. `_sub_primary_claimer_map`) is now built with an O(1) read. Pattern (copy once per variant, adjust `variant` string and kill-switch):
```python
# Subproject B: build per-variant map from bulk result (O(1) per row)
_sub_primary_claimer_map: dict = {}
if BILLING_AUDIT_AVAILABLE and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
    for _r in rows:
        _sid = _r.get('__source_sheet_id')
        if _sid is None or _sid not in _FOLDER_DISCOVERED_SUB_IDS:
            continue
        _rid = _r.get('__row_id')
        if not isinstance(_rid, int):
            continue
        _wr_raw = _r.get('Work Request #')
        _ld = _r.get('Weekly Reference Logged Date')
        if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
            continue
        _we = excel_serial_to_date(_ld)
        if _we is None:
            continue
        _we_d = _we.date() if isinstance(_we, datetime.datetime) else _we
        _wr_key = str(_wr_raw).split('.')[0]
        _eu = _r.get('__effective_user', 'Unknown Foreman')
        from billing_audit.writer import resolve_claimer as _resolve_claimer
        _sub_primary_claimer_map[_rid] = _resolve_claimer(
            'reduced_sub', _eu,
            wr=_wr_key, week_ending=_we_d, row_id=_rid,
            enabled=SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED,
            prefetched_map=_attr_map,    # D-03: O(1) map read, no RPC
        )
```

**Sub-helper direct lookup modification** (lines 6200-6264) — replace the `lookup_attribution` per-row RPC call with a direct map read:
```python
# Phase 2 (2026-05-26): replace per-row lookup_attribution RPC with
# O(1) map read from _attr_map. D-12 fallback preserved unchanged.
_attributed_helper = helper_foreman  # D-12 default
if (
    is_subcontractor_row
    and SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
    # NO _attribution_week_in_scope gate (D-05)
):
    _attr_key = (wr_key, week_ending_date, r.get('__row_id'))
    _attr_row = _attr_map.get(_attr_key)
    if _attr_row is not None:
        _frozen_helper = _attr_row.get('helper')
        if _frozen_helper:
            _attributed_helper = str(_frozen_helper).strip()
        else:
            _attribution_reason = 'no_history'
    else:
        _attribution_reason = (
            'fetch_failure' if _attr_status == 'fetch_failure' else 'no_history'
        )
```

---

### `generate_weekly_pdfs.py` — Remediation mode (new branch)

**Analog:** `generate_weekly_pdfs.py` `cleanup_untracked_sheet_attachments` (lines 2963-3060) and `build_group_identity` (referenced therein)

**Role:** service (destructive attachment sweep)
**Data flow:** batch

**`cleanup_untracked_sheet_attachments` signature** (lines 2963-2976 — the remediation function must accept the same `valid_wr_weeks` and `attachment_cache` params for the live-identity exemption):
```python
def cleanup_untracked_sheet_attachments(
    client,
    target_sheet_id: int,
    valid_wr_weeks: set,
    test_mode: bool,
    attachment_cache: dict | None = None,
    target_sheet=None,
    variant_whitelist: set[str] | None = None,
    sub_wr_scope: set[str] | None = None,
    sub_offcontract_variants: set[str] | None = None,
    sub_legacy_primary_variants: set[str] | None = None,
    vac_legacy_wr_scope: set[str] | None = None,
    primary_wr_scope: set[str] | None = None,
):
```

**Remediation function shape** — new `run_claimer_remediation(client, dry_run: bool, window_weeks: int)`:
```python
def run_claimer_remediation(
    client,
    dry_run: bool,
    window_weeks: int,
) -> None:
    """Garbage-sweep _NO_MATCH / _Unknown_Foreman attachments (D-06/D-07/D-08).

    Isolated from normal cron generation. Default-OFF (REMEDIATE_CLAIMERS env var).
    Live-identity exemption: any attachment whose build_group_identity() 4-tuple
    is in valid_wr_weeks is exempt — never deleted. ([2026-05-19 23:45] rule.)

    dry_run=True: report-only (counts what WOULD be deleted). Execute on re-run.
    window_weeks: how many weeks back to sweep (default ~26).
    """
    _GARBAGE_PATTERNS = ('_NO_MATCH', '_Unknown_Foreman')
    # Build valid_wr_weeks from the current run (same set the normal path builds).
    # Iterate TARGET + PPP sheet attachments for each row in the window.
    # For each attachment name:
    #   parsed = build_group_identity(name)
    #   if parsed and any(pat in name for pat in _GARBAGE_PATTERNS):
    #       if parsed[:4] not in valid_wr_weeks:  # live-identity exemption
    #           if dry_run: log/count; else: client.Attachments.delete_attachment(...)
    ...
```

**Env-gated entry pattern** (copy from existing env-read pattern at L637-647 for safe parse):
```python
try:
    REMEDIATE_CLAIMERS = os.getenv('REMEDIATE_CLAIMERS', '0').lower() in (
        '1', 'true', 'yes', 'on')
    REMEDIATION_WINDOW_WEEKS = int(
        os.getenv('REMEDIATION_WINDOW_WEEKS', '26').strip() or '26')
except (ValueError, TypeError):
    logging.warning(
        "⚠️ Invalid REMEDIATION_WINDOW_WEEKS="
        f"{os.getenv('REMEDIATION_WINDOW_WEEKS')!r}; falling back to 26")
    REMEDIATION_WINDOW_WEEKS = 26
```

**Startup banner pattern** (copy from lines 832-841 — log the resolved state):
```python
logging.info(f"📋 REMEDIATE_CLAIMERS={REMEDIATE_CLAIMERS}")
logging.info(f"📋 REMEDIATION_WINDOW_WEEKS={REMEDIATION_WINDOW_WEEKS}")
```

---

### `.github/workflows/weekly-excel-generation.yml` (modified)

**Analog:** `.github/workflows/weekly-excel-generation.yml` lines 375-464 (existing sub-project kill-switch pin block)

**Role:** config (CI/CD workflow)
**Data flow:** batch

**Existing pin block pattern to copy** (lines 383-453 — each pin follows this exact shape):
```yaml
          # Sub-project X (YYYY-MM-DD): [one-line description].
          # Set to '0' to [revert behavior]. [Relationship to sibling flags].
          # Living Ledger [date].
          FLAG_NAME: '1'
```

**Remove** (D-05):
```yaml
          # Perf hotfix 2026-05-26: scope the per-row frozen-attribution ...
          ATTRIBUTION_RESOLUTION_WEEKS: '8'
```

**Add** (D-12, default-OFF):
```yaml
          # Phase 2 (2026-05-26): one-shot garbage-attachment remediation.
          # ISOLATED from the cron generation path. dry_run-first: set to '1'
          # to report would-delete counts; re-run with REMEDIATION_DRY_RUN='0'
          # to execute. Default-OFF so remediation NEVER fires on scheduled cron.
          # Living Ledger [2026-05-26].
          REMEDIATE_CLAIMERS: '0'
          REMEDIATION_WINDOW_WEEKS: '26'
          REMEDIATION_DRY_RUN: '1'
```

**The `SUPABASE_HASH_STORE_AUTHORITATIVE` flip is NOT in this PR** (D-11 — operator action only, post-validation).

---

### `website/docs/reference/environment.md` (modified)

**Analog:** `website/docs/reference/environment.md` `VAC_CREW_LEGACY_CLEANUP_ENABLED` section and `SUPABASE_HASH_STORE_AUTHORITATIVE` section

**Role:** docs
**Data flow:** n/a

**Existing env-var doc section shape** (copy `VAC_CREW_LEGACY_CLEANUP_ENABLED` pattern):
```markdown
### `VAC_CREW_LEGACY_CLEANUP_ENABLED`

*(Added 2026-05-21, Sub-project C — VAC crew claim attribution.)*

**Default:** `'1'` (on) — truthy values are `1` / `true` / `yes` / `on`

[description paragraph]

**Rollback path:** Set to `'0'` ...

**Workflow pin:** `.github/workflows/weekly-excel-generation.yml`
`env:` block alongside `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`. Per the
[2026-04-24 14:30] workflow-pinning rule, a repo Variable cannot
silently override the pinned value without code review.

**Startup banner:** The resolved state is logged at startup as ...
```

**Remove** `ATTRIBUTION_RESOLUTION_WEEKS` section entirely (D-05).

**Add** three new sections for `REMEDIATE_CLAIMERS`, `REMEDIATION_WINDOW_WEEKS`, `REMEDIATION_DRY_RUN` following the above shape.

---

### `tests/test_billing_audit_shadow.py` — bulk reader tests (new classes)

**Analog:** `tests/test_billing_audit_shadow.py` `LookupGroupHashTests` (lines 4978-5057)

**Role:** test
**Data flow:** request-response

**Test class setUp/tearDown pattern** (copy exactly — lines 4981-4985):
```python
class PrefetchAttributionTests(unittest.TestCase):
    """Phase 2: bulk attribution prefetch reader."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()
```

**Fail-safe status test template** (copy from `LookupGroupHashTests` — lines 4987-5056):
```python
    def test_success_returns_map(self):
        import billing_audit.writer as w
        # mock client.schema(...).rpc(...).execute() returning list of rows
        fake_client = mock.MagicMock()
        fake_client.schema.return_value.rpc.return_value.execute.return_value \
            = mock.MagicMock(data=[{
                "wr": "90001", "week_ending": "2026-04-19",
                "smartsheet_row_id": 123, "primary_foreman": "Alice",
                "helper": None, "helper_dept": None, "vac_crew": None,
                "source_run_id": "run1",
            }])
        with mock.patch.object(w, "get_client", return_value=fake_client):
            result_map, status = w.prefetch_attribution(
                {("90001", datetime.date(2026, 4, 19))})
        self.assertEqual(status, "success")
        key = ("90001", datetime.date(2026, 4, 19), 123)
        self.assertIn(key, result_map)
        self.assertEqual(result_map[key]["primary_foreman"], "Alice")

    def test_client_none_no_kill_is_unavailable(self):
        import billing_audit.writer as w
        with mock.patch.object(w, "get_client", return_value=None):
            m, status = w.prefetch_attribution({("90001", datetime.date(2026, 4, 19))})
        self.assertEqual(status, "unavailable")
        self.assertEqual(m, {})

    def test_client_none_with_global_kill_is_fetch_failure(self):
        import billing_audit.writer as w
        from billing_audit import client as ba_client
        ba_client._global_disable_reason = "PGRST106"
        try:
            with mock.patch.object(w, "get_client", return_value=None):
                m, status = w.prefetch_attribution({("90001", datetime.date(2026, 4, 19))})
        finally:
            ba_client._global_disable_reason = None
        self.assertEqual(status, "fetch_failure")
        self.assertEqual(m, {})

    def test_with_retry_none_is_fetch_failure(self):
        import billing_audit.writer as w
        fake = mock.MagicMock()
        with mock.patch.object(w, "get_client", return_value=fake), \
             mock.patch.object(w, "with_retry", return_value=None):
            m, status = w.prefetch_attribution({("90001", datetime.date(2026, 4, 19))})
        self.assertEqual(status, "fetch_failure")

    def test_unexpected_exception_is_fetch_failure(self):
        import billing_audit.writer as w
        fake = mock.MagicMock()
        with mock.patch.object(w, "get_client", return_value=fake), \
             mock.patch.object(w, "with_retry", side_effect=RuntimeError("boom")):
            m, status = w.prefetch_attribution({("90001", datetime.date(2026, 4, 19))})
        self.assertEqual(status, "fetch_failure")

    def test_empty_pairs_returns_no_row(self):
        import billing_audit.writer as w
        m, status = w.prefetch_attribution(set())
        self.assertEqual(status, "no_row")
        self.assertEqual(m, {})

    def test_no_per_row_rpc_when_map_used(self):
        # REQ-1/3: resolver invoked with prefetched_map issues 0 per-row RPCs
        import billing_audit.writer as w
        with mock.patch.object(w, "_lookup_attribution_all") as mock_lookup:
            out = w.resolve_claimer(
                "primary", "Alice",
                wr="90001", week_ending=datetime.date(2026, 4, 19),
                row_id=123, enabled=True,
                prefetched_map={("90001", datetime.date(2026, 4, 19), 123):
                                {"primary_foreman": "FrozenAlice"}},
            )
        mock_lookup.assert_not_called()
        self.assertEqual(out.name, "FrozenAlice")
        self.assertEqual(out.reason, "success")
```

**Map-aware `resolve_claimer` test class** (new sibling, follows same setUp/tearDown):
```python
class ResolveClaimerMapAwareTests(unittest.TestCase):
    """Phase 2: map-aware resolve_claimer (prefetched_map param)."""
    def setUp(self):
        _reset_all()
    def tearDown(self):
        _reset_all()

    def test_map_hit_returns_frozen(self):
        ...  # prefetched_map with key → action='use', source='frozen'
    def test_map_miss_success_overall_is_no_history(self):
        ...  # key absent in non-empty map, status='success' → no_history → use-current
    def test_fetch_failure_map_holds_for_b_c(self):
        ...  # fetch_failure total: B/C variants → action='hold'
    def test_fetch_failure_map_uses_current_for_d(self):
        ...  # fetch_failure total: D primary variant → action='use' (never HOLD)
    def test_disabled_returns_current_regardless_of_map(self):
        ...  # enabled=False → 'disabled', map not consulted
```

---

### `tests/test_primary_claim_attribution.py` — historical regression class (new class in existing file)

**Analog:** `tests/test_primary_claim_attribution.py` `TestPrimaryClaimerPrePassEmission` (existing class)

**Role:** test (behavioral, RED-before/GREEN-after)
**Data flow:** batch

**Historical regression test pattern** (REQ-2/6b — the incident reproduction):
```python
class TestHistoricalClaimerRegression(unittest.TestCase):
    """Phase 2 REQ-2/6b: historical (>8-week-old) group resolves REAL frozen
    claimer after the bulk-prefetch fix. RED before fix (scope gate returned
    Unknown Foreman); GREEN after (bulk map returns real name).

    Evidence anchor: incident run 26439205107 — 372 garbage files
    (131 _User__NO_MATCH, 241 _User_Unknown_Foreman) concentrated in
    old weeks, because ATTRIBUTION_RESOLUTION_WEEKS=8 excluded those weeks
    from the per-row pre-pass. Attribution_snapshot had the real names all along.
    """

    def setUp(self):
        # Pin all kill switches to ensure the D primary-attribution path fires.
        os.environ.setdefault('PRIMARY_CLAIM_ATTRIBUTION_ENABLED', '1')
        os.environ.setdefault('BILLING_AUDIT_AVAILABLE', '1')
        # No ATTRIBUTION_RESOLUTION_WEEKS (removed in Phase 2).

    def tearDown(self):
        os.environ.pop('PRIMARY_CLAIM_ATTRIBUTION_ENABLED', None)
        os.environ.pop('BILLING_AUDIT_AVAILABLE', None)

    def test_historical_group_resolves_real_claimer_from_bulk_map(self):
        """GREEN after fix: a >8-week-old row gets the real frozen claimer."""
        import datetime
        from billing_audit.writer import resolve_claimer, ResolveOutcome
        old_date = datetime.date.today() - datetime.timedelta(weeks=20)
        row_id = 9999
        frozen_map = {("90001", old_date, row_id): {"primary_foreman": "Real Name"}}
        out = resolve_claimer(
            "primary", "Unknown Foreman",
            wr="90001", week_ending=old_date, row_id=row_id,
            enabled=True, prefetched_map=frozen_map,
        )
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "Real Name")
        self.assertEqual(out.source, "frozen")

    def test_no_frozen_data_falls_back_to_current(self):
        """No snapshot row → no_history → use current foreman (not HOLD)."""
        import datetime
        from billing_audit.writer import resolve_claimer
        old_date = datetime.date.today() - datetime.timedelta(weeks=20)
        # Empty map = no frozen data for this row
        out = resolve_claimer(
            "primary", "CurrentForeman",
            wr="90001", week_ending=old_date, row_id=9999,
            enabled=True, prefetched_map={},   # non-None map, key absent
        )
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "CurrentForeman")
        self.assertEqual(out.reason, "no_history")
```

---

### `tests/test_attribution_resolution_scope.py` — DELETE

**Disposition:** DELETE per D-05 recommendation. The file tests `_attribution_resolution_cutoff` and `_attribution_week_in_scope`, both of which are removed. The replacement regression lives in `TestHistoricalClaimerRegression` above.

**Pitfall 4 guard** — the import-guard pattern from this file (lines 22-26) must be carried into any NEW test module that calls `_ensure_smartsheet_mocked()`:
```python
# Guard: only stub smartsheet when NOT already installed as a real package.
# Calling _ensure_smartsheet_mocked() unconditionally at module top level
# installs a bare MagicMock into sys.modules during pytest COLLECTION, which
# breaks suites that import from the real SDK (TestDiscoverFolderSheets etc).
# [2026-05-26 01:45] Living Ledger rule 3.
try:
    import smartsheet  # noqa: F401
except ImportError:
    _ensure_smartsheet_mocked()
```

---

## Shared Patterns

### Pattern: `with_retry(fn, op="<DISTINCT_ID>")` call shape

**Source:** `billing_audit/client.py` lines 539-540, 814
**Apply to:** `prefetch_attribution` in `billing_audit/writer.py`

```python
# The op= identifier MUST be distinct from all existing ops:
#   "freeze_attribution", "pipeline_run_select", "pipeline_run_upsert",
#   "feature_flag", "lookup_attribution", "lookup_group_hash"
# Use: op="lookup_attribution_bulk"
result = with_retry(_invoke, op="lookup_attribution_bulk")
if result is None:
    return {}, "fetch_failure"
```

### Pattern: `get_client()` + global-kill check

**Source:** `billing_audit/writer.py` lines 785-791 (`_lookup_attribution_all` preamble)
**Apply to:** `prefetch_attribution`

```python
from billing_audit import client as _client_mod

client = get_client()
if client is None:
    if _client_mod._global_disable_reason is not None:
        return {}, "fetch_failure"   # outage
    return {}, "unavailable"         # no creds / TEST_MODE
```

### Pattern: RPC invoke shape

**Source:** `billing_audit/writer.py` lines 806-811 (`_lookup_attribution_all` inner `_invoke`)
**Apply to:** `prefetch_attribution`'s per-chunk `_invoke`

```python
def _invoke(_p=payload):
    return (
        client.schema("billing_audit")
        .rpc("lookup_attribution_bulk", {"p_wr_weeks": _p})
        .execute()
    )
```

### Pattern: Belt-and-suspenders `except Exception` never-raises contract

**Source:** `billing_audit/writer.py` lines 825-837 (`_lookup_attribution_all`) and lines 1058-1067 (`lookup_group_hash`)
**Apply to:** `prefetch_attribution`

```python
except Exception:
    logging.warning(
        "⚠️ Attribution bulk prefetch hit an unexpected error; "
        "treating as fetch_failure (HOLD for B/C, use-current for D)."
    )
    return {}, "fetch_failure"
```

### Pattern: Workflow `env:` kill-switch pin

**Source:** `.github/workflows/weekly-excel-generation.yml` lines 383-414 (sub-project B/C/D/E pin block)
**Apply to:** new `REMEDIATE_CLAIMERS`, `REMEDIATION_WINDOW_WEEKS`, `REMEDIATION_DRY_RUN` pins

```yaml
          # Phase 2 (2026-05-26): [description]. Default-OFF [reason].
          # Living Ledger [2026-05-26].
          REMEDIATE_CLAIMERS: '0'
```

### Pattern: Live-identity exemption in attachment cleanup

**Source:** `generate_weekly_pdfs.py` `cleanup_untracked_sheet_attachments` (lines 2963-3060) — the `ident not in valid_wr_weeks` check
**Apply to:** `run_claimer_remediation`

The remediation function MUST check `build_group_identity(attachment_name)` → returns a 4-tuple `(wr, week, variant, identifier)` → skip deletion if that 4-tuple is in `valid_wr_weeks`. This is the `[2026-05-19 23:45]` live-identity exemption.

### Pattern: Env-var safe parse

**Source:** `generate_weekly_pdfs.py` lines 637-647 (`ATTRIBUTION_RESOLUTION_WEEKS` parse — ironically the pattern to copy when adding `REMEDIATION_WINDOW_WEEKS`)
**Apply to:** `REMEDIATION_WINDOW_WEEKS` env read

```python
try:
    REMEDIATION_WINDOW_WEEKS = int(
        os.getenv('REMEDIATION_WINDOW_WEEKS', '26').strip() or '26')
except (ValueError, TypeError):
    logging.warning(
        "⚠️ Invalid REMEDIATION_WINDOW_WEEKS="
        f"{os.getenv('REMEDIATION_WINDOW_WEEKS')!r}; falling back to 26")
    REMEDIATION_WINDOW_WEEKS = 26
```

---

## No Analog Found

All files have close analogs. No file in this phase requires inventing new patterns.

---

## Metadata

**Analog search scope:**
- `billing_audit/schema.sql` (278 lines, fully read)
- `billing_audit/writer.py` (lines 740-1068, targeted reads)
- `billing_audit/client.py` (lines 60-660, targeted reads)
- `generate_weekly_pdfs.py` (lines 630-660, 2963-3060, 5325-5704, 5855-5915, 6185-6284)
- `.github/workflows/weekly-excel-generation.yml` (lines 375-464)
- `website/docs/reference/environment.md` (targeted grep)
- `tests/test_billing_audit_shadow.py` (lines 4978-5100)

**Files scanned:** 7
**Pattern extraction date:** 2026-05-26
