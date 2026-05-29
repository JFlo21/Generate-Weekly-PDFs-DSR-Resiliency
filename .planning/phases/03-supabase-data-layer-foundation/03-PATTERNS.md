# Phase 03: Supabase Data Layer Foundation - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 5 (4 new, 1 modified)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/publish_artifacts_to_supabase.py` | service (publish script) | batch + request-response | `billing_audit/client.py` + `scripts/generate_artifact_manifest.py` | role-match (same Supabase stack, same batch-of-files pattern) |
| `supabase/portal_schema.sql` | config (DDL) | — | `billing_audit/schema.sql` | exact (same project, same DDL conventions, same apply-in-SQL-Editor pattern) |
| `.github/workflows/weekly-excel-generation.yml` | config (CI step addition) | event-driven | self (existing `billing_audit` additive steps) | exact (modify-in-place, same `continue-on-error` + `always()` pattern) |
| `tests/test_publish_artifacts_to_supabase.py` | test | — | `tests/test_billing_audit_shadow.py` + `tests/test_subproject_e_hash_store.py` | exact (same mocking discipline, same unittest.TestCase structure) |
| `portal-v2/src/lib/supabase.ts` | utility (read-path client) | request-response | self (read-only reference; no changes in this phase) | — |

---

## Pattern Assignments

### `scripts/publish_artifacts_to_supabase.py` (service, batch)

**Primary analog:** `billing_audit/client.py`
**Supporting analog:** `scripts/generate_artifact_manifest.py`

#### Imports pattern — mirror `billing_audit/client.py` lines 1-37

```python
"""Publish generated Excel artifacts to Supabase Storage + public.artifacts.

Additive post-billing CI step. Designed to be loud-but-non-fatal:
all exceptions are caught, reported to Sentry and $GITHUB_STEP_SUMMARY,
and the script exits 0 so a Supabase outage never fails the billing run.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Reuse helpers from existing modules — do not re-implement
from billing_audit.client import get_client, with_retry
from scripts.generate_artifact_manifest import (
    calculate_file_hash,
    parse_excel_filename,
)

try:
    import sentry_sdk  # type: ignore
except Exception:
    sentry_sdk = None  # type: ignore[assignment]
```

#### TEST_MODE / env-guard pattern — mirror `billing_audit/client.py` lines 183-190

```python
def _is_test_mode() -> bool:
    """Match the pipeline's TEST_MODE semantics without importing generate_weekly_pdfs."""
    return os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes", "on")

def _skip_upload() -> bool:
    """Honor SKIP_UPLOAD=true for local dry-runs (mirrors generate_weekly_pdfs.py convention)."""
    return os.getenv("SKIP_UPLOAD", "false").lower() in ("1", "true", "yes", "on")
```

#### Variant normalizer — from RESEARCH.md Item 1 (mirrors `generate_weekly_pdfs.py` L2834 precedence)

```python
def normalize_variant(filename: str) -> str:
    """Map filename suffix tokens → one of the 7 canonical snake_case variant values.

    Precedence mirrors generate_weekly_pdfs.py L2834
    (AEPBillable → ReducedSub → VacCrew → Helper → User).
    Match most-specific token first to avoid AEPBillable_Helper matching _Helper_ alone.
    """
    if "_AEPBillable_Helper_" in filename:
        return "aep_billable_helper"
    if "_ReducedSub_Helper_" in filename:
        return "reduced_sub_helper"
    if "_AEPBillable" in filename:
        return "aep_billable"
    if "_ReducedSub" in filename:
        return "reduced_sub"
    if "_VacCrew" in filename:
        return "vac_crew"
    if "_Helper_" in filename:
        return "helper"
    return "primary"  # bare or _User_ named primary
```

**Critical note:** `parse_excel_filename` (lines 26-54 of `scripts/generate_artifact_manifest.py`) is positionally broken for non-bare-primary filenames — use it ONLY for `work_request` (parts[1]) and `week_ending` (parts[3]). Compute `sha256` from file bytes via `calculate_file_hash`, never from the filename's embedded hash token.

#### MMDDYY → ISO date conversion — from RESEARCH.md Item 6

```python
week_ending_iso = datetime.strptime(mmddyy, "%m%d%y").date().isoformat()
# "051725" → "2025-05-17"
```

#### Core publish loop — reusing `with_retry` from `billing_audit/client.py` lines 539-659

```python
def publish_file(client: Any, local_path: Path, docs_folder: Path) -> bool:
    """Upload one .xlsx to Storage and upsert its metadata row. Returns True on success."""
    filename = local_path.name
    parsed = parse_excel_filename(filename)
    if parsed is None:
        logging.warning("WARNING: Skipping unparseable filename: %s", filename)
        return False

    wr = parsed["work_request"]            # stable at position 1
    mmddyy = parsed["week_ending"]         # stable at position 3
    variant = normalize_variant(filename)
    sha256_hex = calculate_file_hash(str(local_path))
    if sha256_hex is None:
        logging.warning("WARNING: Could not hash %s — skipping", filename)
        return False

    week_ending_iso = datetime.strptime(mmddyy, "%m%d%y").date().isoformat()
    storage_path = f"{week_ending_iso}/{filename}"
    size_bytes = local_path.stat().st_size
    run_id = os.environ.get("GITHUB_RUN_ID", "local")

    # Storage upload — reuse with_retry for bounded retry + circuit breaker
    def _upload():
        with open(local_path, "rb") as fh:
            client.storage.from_("excel-artifacts").upload(
                path=storage_path,
                file=fh.read(),
                file_options={
                    "content-type": (
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    ),
                    "upsert": "true",   # re-run replaces same path (verify keyword for 2.9.1)
                },
            )

    res = with_retry(_upload, op="artifact_storage_upload")
    # with_retry returns None on exhausted/classified-permanent failure

    # Metadata upsert — idempotent on sha256 per D-08
    row = {
        "work_request":    wr,
        "week_ending":     week_ending_iso,
        "week_ending_fmt": mmddyy,
        "variant":         variant,
        "filename":        filename,
        "storage_path":    storage_path,
        "size_bytes":      size_bytes,
        "sha256":          sha256_hex,
        "run_id":          run_id,
    }
    with_retry(
        lambda: client.table("artifacts").upsert(row, on_conflict="sha256").execute(),
        op="artifact_table_upsert",
    )
    return True
```

#### File discovery — mirror `generate_artifact_manifest.py` lines 100-120 (root + YYYY-MM-DD subfolders)

```python
import re

def collect_xlsx_files(docs_folder: Path) -> list[Path]:
    """Scan root + YYYY-MM-DD week subfolders — mirrors generate_artifact_manifest.py L100-120."""
    files: list[Path] = []
    if not docs_folder.exists():
        return files
    for f in docs_folder.iterdir():
        if f.is_file() and f.name.startswith("WR_") and f.suffix == ".xlsx":
            files.append(f)
    for subfolder in docs_folder.iterdir():
        if subfolder.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", subfolder.name):
            for f in subfolder.iterdir():
                if f.is_file() and f.name.startswith("WR_") and f.suffix == ".xlsx":
                    files.append(f)
    return files
```

#### Failure isolation / loud-but-non-fatal pattern — D-06 contract

```python
def main(docs_folder_arg: str) -> None:
    docs_folder = Path(docs_folder_arg)

    if _is_test_mode() or _skip_upload():
        logging.info("INFO: publish_artifacts_to_supabase skipped (TEST_MODE or SKIP_UPLOAD)")
        return

    client = get_client()
    if client is None:
        _emit_summary("WARNING: Supabase client unavailable — artifact publish skipped")
        return

    files = collect_xlsx_files(docs_folder)
    if not files:
        logging.info("INFO: No WR_*.xlsx files found in %s — nothing to publish", docs_folder)
        return

    failed: list[str] = []
    published = 0
    for f in files:
        try:
            ok = publish_file(client, f, docs_folder)
            if ok:
                published += 1
        except Exception as exc:
            failed.append(f.name)
            # Aggregate error, no per-filename PII in Sentry body (D security / Pitfall D)
            if sentry_sdk is not None:
                sentry_sdk.capture_exception(exc)
            logging.warning(
                "WARNING: publish_artifacts_to_supabase failed for %d file(s): %s",
                len(failed),
                type(exc).__name__,
            )

    _emit_summary(
        f"publish_artifacts_to_supabase: published={published} failed={len(failed)}"
    )

def _emit_summary(message: str) -> None:
    """Write to $GITHUB_STEP_SUMMARY if available (D-06 loud-on-failure contract)."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as fh:
            fh.write(f"- {message}\n")
    logging.warning(message)

if __name__ == "__main__":
    docs_folder_arg = sys.argv[1] if len(sys.argv) > 1 else "generated_docs"
    main(docs_folder_arg)
```

---

### `supabase/portal_schema.sql` (config, DDL)

**Analog:** `billing_audit/schema.sql`

#### File header + apply-instructions pattern — mirror `billing_audit/schema.sql` lines 1-24

```sql
-- ============================================================
-- Canonical DDL for the portal ``public`` schema.
--
-- This file is documentation-grade SQL. It is NOT auto-applied
-- by the Python pipeline — apply it manually in the Supabase
-- SQL Editor (Project Settings → SQL Editor) the first time,
-- and again whenever this file is updated to add a column.
--
-- After running, confirm in:
--   Supabase → Project Settings → API → Data API Settings →
--     "Exposed schemas"
-- that ``public`` is listed (it is by default; do NOT remove it).
-- No schema-cache reload is required for ``public`` — PostgREST
-- exposes it automatically (contrast: ``billing_audit`` required
-- a manual "Exposed schemas" add + cache reload; see CLAUDE.md
-- Living Ledger [2026-04-24]).
--
-- The Python writer contract is enforced in
-- ``scripts/publish_artifacts_to_supabase.py``. If you add or
-- rename columns here, update that script in the same PR.
-- ============================================================
```

#### Table + index DDL pattern — mirror `billing_audit/schema.sql` lines 63-126

Key conventions extracted from the analog:
- `CREATE TABLE IF NOT EXISTS` (idempotent re-apply)
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` guards BEFORE `CREATE INDEX` (partial-deploy safety — see billing_audit/schema.sql L77-88 commentary)
- `TEXT NOT NULL` with NO CHECK constraint for forward-compatible enum-like columns (billing_audit/schema.sql L97-104)
- `TIMESTAMPTZ NOT NULL DEFAULT NOW()` for timestamps
- Compound indexes with `DESC` for date columns

```sql
CREATE TABLE IF NOT EXISTS public.artifacts (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    work_request    TEXT        NOT NULL,
    week_ending     DATE        NOT NULL,
    week_ending_fmt TEXT        NOT NULL,   -- MMDDYY for display / filename join (D-09)
    variant         TEXT        NOT NULL,   -- 7 canonical values; NO CHECK — forward-compat
                                            -- (mirrors billing_audit.pipeline_run.variant
                                            --  at schema.sql L97-104)
    filename        TEXT        NOT NULL,
    storage_path    TEXT        NOT NULL,
    size_bytes      BIGINT      NOT NULL DEFAULT 0,
    sha256          TEXT        NOT NULL,
    run_id          TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id),
    UNIQUE (sha256)                         -- D-08 idempotency key
);

-- Backfill-safe column-add guard (mirrors billing_audit/schema.sql L89-95 pattern).
-- Safe to re-run on a partial-deploy environment; ADD COLUMN IF NOT EXISTS is a no-op
-- when the column already exists. MUST appear before CREATE INDEX (ordering rule at L77-88).
ALTER TABLE public.artifacts
    ADD COLUMN IF NOT EXISTS week_ending_fmt TEXT,
    ADD COLUMN IF NOT EXISTS variant         TEXT,
    ADD COLUMN IF NOT EXISTS storage_path    TEXT,
    ADD COLUMN IF NOT EXISTS size_bytes      BIGINT,
    ADD COLUMN IF NOT EXISTS sha256          TEXT,
    ADD COLUMN IF NOT EXISTS run_id          TEXT,
    ADD COLUMN IF NOT EXISTS created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_artifacts_work_request
    ON public.artifacts (work_request, week_ending DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_week_ending
    ON public.artifacts (week_ending DESC);
```

#### profiles table + role-aware RLS pattern — from RESEARCH.md Pattern 2

```sql
CREATE TABLE IF NOT EXISTS public.profiles (
    id   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'pending'
               CHECK (role IN ('admin', 'billing', 'pending'))
    -- CHECK is appropriate here: the role set is an operator-controlled
    -- enum that must be enforced at the DB layer (unlike variant, which
    -- is writer-controlled and forward-compatible).
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Self-read: any user can read their own profile row (needed for role check in the app)
CREATE POLICY profiles_self_read ON public.profiles
    FOR SELECT USING (auth.uid() = id);

-- Admin-all: admins can read/write all profiles (for the Phase 04 admin UI)
CREATE POLICY profiles_admin_all ON public.profiles
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.profiles
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY;

-- Role-aware SELECT: only admin and billing roles can read artifact rows.
-- pending and anonymous get zero rows (D-11).
-- service_role (CI publish step) bypasses RLS — no INSERT policy needed.
CREATE POLICY artifacts_select_billing_or_admin ON public.artifacts
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles
            WHERE id = auth.uid() AND role IN ('admin', 'billing')
        )
    );

-- Storage SELECT policy — REQUIRED for createSignedUrl on the private bucket (Item 4).
-- Without this policy, createSignedUrl returns 400/403 even for valid authenticated sessions.
CREATE POLICY storage_artifacts_role_select ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'excel-artifacts'
        AND EXISTS (
            SELECT 1 FROM public.profiles
            WHERE id = auth.uid() AND role IN ('admin', 'billing')
        )
    );

-- GRANT for the service_role (publish step's write path bypasses RLS automatically;
-- this grant is for explicit execute on any future RPCs, mirroring
-- billing_audit/schema.sql L285, L330)
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;
```

#### Anti-pattern guardrails extracted from `billing_audit/schema.sql`

- Do NOT write `USING (true)` — that gives any `pending` user access to billing PII (billing_audit/schema.sql L97-104 commentary + PITFALLS.md P3).
- Do NOT add `CHECK (variant IN (...))` on `public.artifacts.variant` — a future 8th variant silently drops rows under `continue-on-error` (schema.sql L97-104 forward-compat note).
- Do NOT run `CREATE INDEX` before the `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` guards (schema.sql L77-88 ordering rule — Supabase SQL Editor halts on first error).

---

### `.github/workflows/weekly-excel-generation.yml` (config, event-driven — additive step)

**Analog:** existing `billing_audit`-related steps in the same file (the "Create Sentry release" step at lines 527-542 is the closest structural match: same `if: always()`, `continue-on-error: true`, Supabase secrets already wired at lines 241-242).

#### Secret wiring already present — `weekly-excel-generation.yml` lines 241-242

```yaml
# In the "Generate reports" step env block (lines 241-242):
SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

These env vars are step-scoped (not job-level). The new publish step MUST re-declare them in its own `env:` block.

#### Insertion point — after line 579 ("Generate artifact manifest" step end), before line 738 (cache-save block)

Exact surrounding context for placement:

```yaml
      - name: Generate artifact manifest        # ends ~L579
        id: manifest
        if: always() && steps.exec.outputs.should_run == 'true'
        run: |
          ...

      # <<<< INSERT NEW STEP HERE >>>>

      - name: Organize artifacts by Work Request  # L581
        id: organize
        ...

      # ... upload + summary steps (L626-736) ...

      # ==================== CACHE SAVE (runs even on timeout/failure) ====================
      - name: Save hash history cache             # L739 — MUST run after publish
        if: always()
        uses: actions/cache/save@v4
```

#### New step pattern — mirror "Create Sentry release" step (lines 527-542) for `continue-on-error` + `if: always()`

```yaml
      - name: Publish artifacts to Supabase
        id: publish_supabase
        if: always() && steps.exec.outputs.should_run == 'true'
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          SENTRY_DSN: ${{ secrets.SENTRY_DSN }}
          ENVIRONMENT: production
          SENTRY_RELEASE: ${{ env.SENTRY_RELEASE }}   # slash-free release from "Compute Sentry release" step
          GITHUB_RUN_ID: ${{ github.run_id }}
        run: python scripts/publish_artifacts_to_supabase.py generated_docs
```

Key constraints:
- `continue-on-error: true` — a Supabase outage must never fail the billing run or block the cache-save steps (D-06).
- Step-level `env:` block required — `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` from the "Generate reports" step env are NOT inherited (step-scoped).
- `if: always() && steps.exec.outputs.should_run == 'true'` — mirrors the manifest step condition (line 552) so the publish runs whenever the billing run ran, even if a downstream step errored.
- Placed BEFORE the `Save hash history cache` step (line 739) — combined with `continue-on-error: true`, guarantees `if: always()` cache-save steps still run regardless of publish outcome.

---

### `tests/test_publish_artifacts_to_supabase.py` (test)

**Primary analog:** `tests/test_billing_audit_shadow.py` (mocking discipline, unittest.TestCase structure)
**Supporting analog:** `tests/test_subproject_e_hash_store.py` (filename parsing tests)

#### File header + mock-bootstrap pattern — mirror `test_billing_audit_shadow.py` lines 1-79

```python
"""Unit tests for scripts/publish_artifacts_to_supabase.py.

Tests are fully mocked — no real Supabase API calls, no real filesystem
writes beyond tempfiles. Covers:
  - normalize_variant: all 7 token forms → 7 canonical values
  - MMDDYY → ISO date conversion and bad-format rejection
  - sha256 computed from file bytes (not filename token)
  - upsert payload shape + on_conflict="sha256" (idempotent per D-08)
  - Failure isolation: exceptions caught, exit 0, WARNING + summary emitted
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
```

#### Mocking pattern for Supabase client — mirror `test_billing_audit_shadow.py` mock discipline

```python
class TestNormalizeVariant(unittest.TestCase):
    """All 7 filename token forms map to correct canonical variant values."""

    def setUp(self):
        # Import the module under test; mock get_client so no real
        # Supabase connection is attempted on module import
        with mock.patch("billing_audit.client.get_client", return_value=None):
            import scripts.publish_artifacts_to_supabase as pub
            self.pub = pub

    def test_bare_primary(self):
        self.assertEqual(self.pub.normalize_variant("WR_90001_WeekEnding_051725_abc123.xlsx"), "primary")

    def test_user_primary(self):
        self.assertEqual(self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_User_Jane_Smith_abc123.xlsx"), "primary")

    def test_helper(self):
        self.assertEqual(self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_Helper_Bob_abc123.xlsx"), "helper")

    def test_vac_crew_bare(self):
        self.assertEqual(self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_VacCrew_abc123.xlsx"), "vac_crew")

    def test_vac_crew_named(self):
        self.assertEqual(self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_VacCrew_Alice_abc123.xlsx"), "vac_crew")

    def test_aep_billable(self):
        self.assertEqual(self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_AEPBillable_abc123.xlsx"), "aep_billable")

    def test_reduced_sub(self):
        self.assertEqual(self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_ReducedSub_abc123.xlsx"), "reduced_sub")

    def test_aep_billable_helper(self):
        # Must match before _Helper_ alone (precedence test)
        self.assertEqual(
            self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_AEPBillable_Helper_Bob_abc123.xlsx"),
            "aep_billable_helper",
        )

    def test_reduced_sub_helper(self):
        self.assertEqual(
            self.pub.normalize_variant("WR_90001_WeekEnding_051725_103000_ReducedSub_Helper_Bob_abc123.xlsx"),
            "reduced_sub_helper",
        )
```

#### Mocked upsert payload test — mirror `test_billing_audit_shadow.py` RPC-param mapping tests

```python
class TestUpsertPayload(unittest.TestCase):
    """Upsert row has correct keys + on_conflict="sha256"; re-run does not duplicate."""

    def test_idempotent_upsert(self):
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            prefix="WR_90001_WeekEnding_051725_",
            delete=False,
        ) as f:
            f.write(b"fake-xlsx-content")
            tmp_path = Path(f.name)

        mock_client = mock.MagicMock()
        mock_upsert_chain = mock.MagicMock()
        mock_client.table.return_value.upsert.return_value.execute = mock_upsert_chain

        with mock.patch("billing_audit.client.with_retry") as mock_retry:
            mock_retry.side_effect = lambda fn, *a, op="default", **kw: fn()
            # ... call publish_file and assert on mock_client.table().upsert.call_args
            upsert_call = mock_client.table("artifacts").upsert.call_args
            self.assertIn("sha256", upsert_call[0][0])
            self.assertEqual(upsert_call[1].get("on_conflict"), "sha256")

        tmp_path.unlink(missing_ok=True)
```

#### Failure isolation test — D-06 contract (exit 0, WARNING emitted)

```python
class TestFailureIsolation(unittest.TestCase):
    """Exceptions inside publish_file are caught; main() does not raise; summary emitted."""

    def test_supabase_outage_does_not_raise(self):
        with mock.patch("billing_audit.client.get_client") as mock_get:
            mock_get.return_value = None  # simulates outage / missing creds
            import scripts.publish_artifacts_to_supabase as pub
            # Should return without raising — not sys.exit(1)
            try:
                pub.main("nonexistent_folder")
            except SystemExit as exc:
                self.fail(f"main() called sys.exit({exc.code}) — must exit 0")
```

---

### `portal-v2/src/lib/supabase.ts` (utility, read-path client — READ-ONLY reference this phase)

**Analog:** self (no changes in Phase 03; read-path is consumed starting Phase 05)

#### Current shape — `portal-v2/src/lib/supabase.ts` lines 1-18

```typescript
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const supabase: SupabaseClient = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key'
);

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);
```

**Planner note:** the silent-placeholder-on-missing-env behavior (lines 13-16) means the client is always constructed but silently points at a dead endpoint when env vars are absent. This is a known bug noted in CONTEXT.md for a later phase. Phase 03 does NOT modify this file. The planner should note it as a read-path dependency for Phase 05 and record the placeholder-URL bug for that phase's scope.

---

## Shared Patterns

### Pattern 1: Supabase client construction (get_client)
**Source:** `billing_audit/client.py` lines 221-294
**Apply to:** `scripts/publish_artifacts_to_supabase.py`

```python
# Import and call directly — do not re-implement create_client inline.
# get_client() returns None when: TEST_MODE, missing creds, supabase package absent,
# construction raises, or run-global kill switch tripped.
from billing_audit.client import get_client

client = get_client()
if client is None:
    # loud, non-fatal path
    ...
```

Key env var names (lines 259-260): `os.getenv("SUPABASE_URL")` and `os.getenv("SUPABASE_SERVICE_ROLE_KEY")` — must match GitHub Actions secret names exactly.

### Pattern 2: Retry + SQLSTATE classifier (with_retry + _classify_postgrest_error)
**Source:** `billing_audit/client.py` lines 539-659 (`with_retry`), lines 310-391 (`_classify_postgrest_error`)
**Apply to:** all Storage upload and table upsert calls in `scripts/publish_artifacts_to_supabase.py`

```python
from billing_audit.client import with_retry

# Wrap each Supabase call in with_retry with a stable op string.
# Returns None on permanent / exhausted failure; returns fn() result on success.
# Op names for the publish script (must be distinct per D-07 + circuit-breaker isolation):
res = with_retry(fn, op="artifact_storage_upload")   # Storage upload
res = with_retry(fn, op="artifact_table_upsert")     # metadata upsert
```

Classifier behavior (lines 310-391):
- Permanent (no retry): PGRST1xx/2xx/3xx, SQLSTATE 22/23/42, HTTP 4xx except 408/429
- Global-kill: PGRST106, PGRST301, PGRST302 → `get_client()` returns None for rest of run
- Transient (retry): network errors, HTTP 408/429/5xx, unknown codes

**Process-isolation note (RESEARCH.md Item 7):** The publish script runs in a separate `python` process from "Generate reports", so `billing_audit.client` module-level circuit-breaker state is isolated between the two steps. No cross-contamination risk.

### Pattern 3: Sentry breadcrumb emission
**Source:** `billing_audit/client.py` lines 193-218 (`_sentry_breadcrumb`)
**Apply to:** `scripts/publish_artifacts_to_supabase.py` failure path

```python
# Lazy import pattern — sentry_sdk is a no-op when not initialized
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

# Capture exception without PII in message body (Pitfall D)
if sentry_sdk is not None:
    sentry_sdk.capture_exception(exc)
# Log only aggregate counts + error type, never per-file WR/foreman/customer names
logging.warning("WARNING: publish failed for %d file(s): %s", count, type(exc).__name__)
```

### Pattern 4: Billing-audit DDL conventions
**Source:** `billing_audit/schema.sql` lines 1-170
**Apply to:** `supabase/portal_schema.sql`

- `CREATE TABLE IF NOT EXISTS` — idempotent re-apply
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` guards BEFORE every `CREATE INDEX` (L77-88 ordering rule)
- `TEXT` with no CHECK for writer-controlled enum-like columns (L97-104 forward-compat)
- `TIMESTAMPTZ NOT NULL DEFAULT NOW()` for all timestamps
- `GRANT EXECUTE ON FUNCTION ... TO service_role` after each RPC (L285, L330)
- Header comment block with SQL Editor apply instructions + Python contract pointer (L1-24)

### Pattern 5: Test mocking discipline
**Source:** `tests/test_billing_audit_shadow.py` lines 1-79, `tests/test_subproject_e_hash_store.py` lines 1-30
**Apply to:** `tests/test_publish_artifacts_to_supabase.py`

```python
# Pattern: _ensure_smartsheet_mocked() idiom — inject stubs before importing
# the module under test. For the publish script, mock billing_audit.client.get_client
# and billing_audit.client.with_retry at the boundary (not the Supabase SDK internals).
# Use unittest.TestCase + mock.patch. Never make real API calls.
# Use tempfile.NamedTemporaryFile for file content tests.
```

Run command: `pytest tests/test_publish_artifacts_to_supabase.py -v`
Full suite gate: `pytest tests/ -v` (must pass before push — pre-push hook enforces this)

---

## No Analog Found

No files in this phase lack a close analog. All patterns are grounded in existing codebase files.

---

## Critical Warnings for Planner

1. **`parse_excel_filename` positional breakage** — the function at `scripts/generate_artifact_manifest.py` lines 26-54 uses fixed-position split on `_`. Position 1 (`work_request`) and position 3 (`week_ending`) are stable across all 7 variants. Positions 4+ shift for non-primary filenames. Use only positions 1 and 3; derive `variant` from `normalize_variant(filename)` and `sha256` from `calculate_file_hash(filepath)`.

2. **`storage.objects` SELECT policy is mandatory for `createSignedUrl`** — without the `storage_artifacts_role_select` policy in the DDL, Phase 05 download buttons will 403 even for valid admin/billing sessions. It must land in the same DDL PR.

3. **`continue-on-error: true` placement is load-bearing** — the publish step must be placed BEFORE the `Save hash history cache` step (line 739 in the workflow). If placed after, a Supabase outage that makes the step exit non-zero would (without `continue-on-error`) block the `if: always()` cache-save steps.

4. **`variant TEXT` no CHECK on `public.artifacts`** — mirrors `billing_audit/schema.sql` L97-104 precedent. A CHECK constraint would hard-reject a future 8th variant and silently drop rows under `continue-on-error`. Use an application-level assertion + Sentry capture in the publish script instead.

5. **`supabase==2.9.1` is the installed version** — `requirements.txt` line 27. RESEARCH.md Item 6 flags that the `upload()` upsert keyword (`"upsert": "true"` as a string in `file_options`) and the `table().upsert(on_conflict=...)` signature must be verified against 2.9.1 in Wave 0. Do not assume 2.30.x call shapes.

6. **Step-scoped env vars** — `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from the "Generate reports" step env block (lines 241-242) are NOT available to subsequent steps. The new publish step must declare them in its own `env:` block.

---

## Metadata

**Analog search scope:** `billing_audit/`, `scripts/`, `tests/`, `portal-v2/src/lib/`, `.github/workflows/`
**Files read:** `billing_audit/client.py`, `billing_audit/schema.sql`, `scripts/generate_artifact_manifest.py`, `.github/workflows/weekly-excel-generation.yml`, `requirements.txt`, `portal-v2/src/lib/supabase.ts`, `tests/test_billing_audit_shadow.py`, `tests/test_subproject_e_hash_store.py`
**Pattern extraction date:** 2026-05-29
