# Architecture Research

**Domain:** Supabase-native artifact portal (billing Excel browser + download gate)
**Researched:** 2026-05-29
**Confidence:** HIGH — grounded in existing codebase, live workflow YAML, billing_audit/schema.sql,
portal-v2 source, and verified against Supabase official docs.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  GitHub Actions  weekly-excel-generation.yml                             │
│  (UNCHANGED billing pipeline — generate_weekly_pdfs.py stays untouched) │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  [EXISTING] Generate reports step                                  │  │
│  │  python generate_weekly_pdfs.py → generated_docs/WR_*.xlsx        │  │
│  └────────────────────────┬───────────────────────────────────────────┘  │
│                           │ (files on runner disk)                       │
│  ┌────────────────────────▼───────────────────────────────────────────┐  │
│  │  [NEW] Publish artifacts step  (continue-on-error: true)           │  │
│  │  python scripts/publish_artifacts.py                               │  │
│  │  • supabase-py  service_role key (SUPABASE_SERVICE_ROLE_KEY)       │  │
│  │  • for each WR_*.xlsx: upload to Storage + upsert artifacts row    │  │
│  └──────┬────────────────────────────────────────────────────────────┘  │
│         │ (EXISTING steps continue unchanged)                            │
│  ┌──────▼─────────────────────────────────────────────────────────────┐  │
│  │  [EXISTING] Save caches, upload GitHub Actions artifact, summary   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                    │ supabase-py  service_role
                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Supabase Project  (existing project — billing_audit schema already live) │
│                                                                          │
│  ┌─────────────────────────┐   ┌──────────────────────────────────────┐  │
│  │  Postgres               │   │  Storage                             │  │
│  │  schema: public         │   │  bucket: excel-artifacts  (PRIVATE)  │  │
│  │  table: artifacts       │   │  path: {week_ending}/{filename}      │  │
│  │                         │   │                                      │  │
│  │  schema: billing_audit  │   │  Objects governed by storage RLS     │  │
│  │  (existing: pipeline_run│   │  SELECT: authenticated users only    │  │
│  │   group_content_hash    │   │  INSERT/UPDATE: service_role only    │  │
│  │   attribution_snapshot) │   └──────────────────────────────────────┘  │
│  └─────────────────────────┘                                             │
│                                                                          │
│  Auth:  Supabase Auth + hCaptcha on login                                │
│  RLS:   artifacts table SELECT for authenticated users                   │
│  Realtime:  postgres_changes on public.artifacts (INSERT)                │
└──────────────────────────────────────────────────────────────────────────┘
                    ▲ supabase-js  anon key + JWT
                    │
┌──────────────────────────────────────────────────────────────────────────┐
│  portal-v2  (React 18 + Vite + TS + Tailwind + Framer Motion)           │
│  Deployed: Vercel  root = portal-v2                                      │
│                                                                          │
│  ┌──────────────┐  ┌─────────────────────────────────────────────────┐  │
│  │  Auth gate   │  │  Artifact Explorer (rebuilt)                    │  │
│  │  /login      │  │  /artifacts                                     │  │
│  │  hCaptcha    │  │  • supabase-js .from('artifacts').select()      │  │
│  │  Supabase    │  │  • Indexed Postgres filter: wr + week_ending    │  │
│  │  Auth        │  │  • Virtualized table (no mock fallback)         │  │
│  │              │  │  • createSignedUrl → download .xlsx             │  │
│  │              │  │  • Realtime subscription for live inserts       │  │
│  └──────────────┘  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## New vs. Modified Components

### New Components

| Component | Type | Purpose |
|-----------|------|---------|
| `public.artifacts` Postgres table | NEW database object | Per-file metadata store: WR, week, variant, path, sha256, size, run_id |
| `excel-artifacts` Storage bucket | NEW Supabase resource | Private bucket holding the actual .xlsx files |
| Storage RLS policies | NEW database policies | Restrict object SELECT to authenticated users; INSERT/UPDATE to service_role |
| `artifacts` table RLS policies | NEW database policies | SELECT for authenticated; INSERT/UPDATE for service_role |
| `scripts/publish_artifacts.py` | NEW Python script | Additive GA step: upload xlsx to Storage + upsert artifacts row |
| `billing_audit/schema.sql` artifact DDL block | NEW DDL section | Canonical schema for `public.artifacts` (same apply pattern as billing_audit) |
| `portal-v2/src/hooks/useArtifactsTable.ts` | NEW hook | Replaces `useArtifacts.ts` — reads from `public.artifacts` via supabase-js |
| `portal-v2/src/hooks/useArtifactRealtime.ts` | NEW hook | Realtime subscription on `public.artifacts` INSERT events |
| `portal-v2/src/pages/ArtifactExplorer.tsx` | NEW page | Virtualized, filterable, sortable artifact table reading Supabase directly |
| `portal-v2/src/lib/storage.ts` | NEW module | `createSignedUrl` wrapper with 60-second expiry for on-demand downloads |
| Login page with hCaptcha | NEW page | `/login` — Supabase Auth email+password + hCaptcha token |

### Modified Components

| Component | Change | What Stays the Same |
|-----------|--------|---------------------|
| `portal-v2/src/lib/types.ts` | Add `BillingArtifact` interface for the new table shape; retire Express-era `Artifact`, `WorkflowRun`, `ArtifactFile` types | `Profile`, `ActivityLog`, `UserRole`, `Toast` types unchanged |
| `portal-v2/src/lib/api.ts` | Remove all Express proxy calls; keep only Supabase-js direct calls | `getApiAuthHeaders()` / `supabase.auth.getSession()` pattern stays |
| `portal-v2/src/lib/supabase.ts` | No change needed — client already created from `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | Client creation pattern stays |
| `portal-v2/src/hooks/useArtifacts.ts` | Replace Express-backed fetching with Supabase query; remove mock fallback | Hook signature unchanged to minimize downstream diff |
| `portal-v2/vercel.json` | Add `headers` block for CSP + `frame-ancestors 'none'`; SPA rewrite already correct | `rewrites` rule stays |
| `.github/workflows/weekly-excel-generation.yml` | Add one new step "Publish to Supabase" after "Generate reports", before cache saves | All existing steps, env vars, timeouts, concurrency rules unchanged |
| `requirements.txt` | Add `supabase` (supabase-py) if not already present | All existing deps unchanged |
| `portal/` (Express backend) | REMOVED entirely | N/A |

---

## `public.artifacts` Table — Concrete DDL Sketch

The table lives in the `public` schema (not `billing_audit`) so PostgREST exposes it via the
default Data API without requiring schema-cache changes. This avoids the PGRST106 footgun that
the billing_audit schema required.

```sql
-- ============================================================
-- public.artifacts
-- Per-Excel-file metadata written by the GitHub Actions
-- publish step and read by portal-v2 via supabase-js.
-- Schema: public (auto-exposed by PostgREST; no schema-cache
-- reload required unlike billing_audit tables).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.artifacts (
    -- Surrogate primary key for supabase-js row identity
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Billing identity — mirrors the filename tokens
    work_request    TEXT        NOT NULL,   -- sanitized WR, e.g. "90001"
    week_ending     DATE        NOT NULL,   -- canonical date, e.g. 2026-05-17
    week_ending_fmt TEXT        NOT NULL,   -- MMDDYY text, e.g. "051725" (display + filename join)
    variant         TEXT        NOT NULL,   -- 'primary' | 'helper' | 'vac_crew' |
                                            --   'aep_billable' | 'reduced_sub' |
                                            --   'aep_billable_helper' | 'reduced_sub_helper'

    -- File identity
    filename        TEXT        NOT NULL,   -- full basename, e.g. WR_90001_WeekEnding_051725.xlsx
    storage_path    TEXT        NOT NULL,   -- bucket-relative: {week_ending_iso}/{filename}
    size_bytes      BIGINT      NOT NULL DEFAULT 0,
    sha256          TEXT        NOT NULL,   -- hex SHA-256 of file content

    -- Provenance
    run_id          TEXT        NOT NULL,   -- GitHub Actions run ID (string for safety)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),

    -- Idempotent upsert key: dedupe on sha256 + run_id.
    -- sha256 alone would prevent re-upload of identical content across runs,
    -- but run_id scoping means a deliberate force-regeneration with
    -- RESET_HASH_HISTORY=true creates fresh rows for the new run rather
    -- than silently skipping. Use ON CONFLICT (sha256) DO UPDATE on
    -- storage_path / size_bytes / run_id / created_at to keep the table
    -- current without duplicating rows for same-content re-runs.
    UNIQUE (sha256)
);

-- Fast filtering by WR (primary access pattern: "show me all weeks for WR 90001")
CREATE INDEX IF NOT EXISTS idx_artifacts_work_request
    ON public.artifacts (work_request, week_ending DESC);

-- Fast filtering by week_ending (secondary access pattern: "show week 051725")
CREATE INDEX IF NOT EXISTS idx_artifacts_week_ending
    ON public.artifacts (week_ending DESC);

-- Fast lookup for the publish script's idempotency check (sha256 existence)
-- The UNIQUE constraint creates this implicitly; explicit index for clarity.
-- No separate CREATE INDEX needed — UNIQUE already creates a btree index.

-- Backfill-safe column adds (same pattern as billing_audit convention):
ALTER TABLE public.artifacts
    ADD COLUMN IF NOT EXISTS week_ending_fmt TEXT;
-- Backfill existing rows if any: UPDATE public.artifacts SET week_ending_fmt =
--   to_char(week_ending, 'MMDDYY') WHERE week_ending_fmt IS NULL;
```

**Deduplication rationale — sha256 vs. filename:**
Deduping on `sha256` is correct because the filename embeds a timestamp and hash token when
`SUPABASE_HASH_STORE_AUTHORITATIVE=0` (legacy mode). With `SUPABASE_HASH_STORE_AUTHORITATIVE=1`
(current: clean filenames without token), filenames are stable per `(WR, week, variant, foreman)`.
In either mode, sha256 is the stable identity. The publish script should:

```python
# Idempotent upsert pattern (supabase-py)
client.table("artifacts").upsert(
    row_dict,
    on_conflict="sha256"  # ignore/update on same content
).execute()
```

---

## Supabase Storage — Bucket Layout and Signed URLs

### Bucket

- **Name:** `excel-artifacts`
- **Visibility:** Private (no public URL access; all reads via signed URL)
- **Object path convention:** `{week_ending_iso}/{filename}`
  - Example: `2026-05-17/WR_90001_WeekEnding_051725.xlsx`
  - `week_ending_iso` = ISO date string (`YYYY-MM-DD`) derived from the `week_ending` DATE column
  - This groups files by week at the storage layer, making manual inspection and lifecycle policies straightforward
  - Matches the `storage_path` column in `public.artifacts`

### Signed URL Generation (frontend)

```typescript
// portal-v2/src/lib/storage.ts
import { supabase } from './supabase';

const BUCKET = 'excel-artifacts';
const SIGNED_URL_EXPIRY_SECONDS = 60; // 60s: enough for browser download initiation

export async function getSignedDownloadUrl(storagePath: string): Promise<string> {
  const { data, error } = await supabase.storage
    .from(BUCKET)
    .createSignedUrl(storagePath, SIGNED_URL_EXPIRY_SECONDS);

  if (error || !data?.signedUrl) {
    throw new Error(`Failed to generate signed URL: ${error?.message ?? 'unknown'}`);
  }
  return data.signedUrl;
}
```

**Expiry design:** 60 seconds is intentional — the URL is generated on the download button click
and immediately used. This minimizes the window where a leaked URL could be used by an
unauthenticated party. The `createSignedUrl` call requires the user's JWT to be valid (RLS SELECT
policy on `storage.objects`), so the 60s expiry is the only attack surface.

**No expiry maximum concern for this use case:** Supabase allows arbitrary `expiresIn` values in
seconds. 60s is well within any platform limit.

---

## RLS Policy Model

### `public.artifacts` Table Policies

```sql
-- Enable RLS
ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY;

-- SELECT: any authenticated billing-team user can read all artifacts.
-- No role filtering in v1 — defer admin/role-based scoping to v2.
CREATE POLICY "artifacts_select_authenticated"
    ON public.artifacts
    FOR SELECT
    TO authenticated
    USING (true);

-- INSERT / UPDATE: service_role only (GitHub Actions publish step).
-- The anon key used by portal-v2 CANNOT write to this table.
-- service_role bypasses RLS, so no explicit policy is needed for it —
-- but documenting intent here for operator clarity.
-- (No INSERT/UPDATE policy for 'authenticated' role = portal users cannot write.)
```

### Storage Bucket Policies (`storage.objects`)

Supabase Storage RLS operates on `storage.objects`. For a private bucket, policies must be
created on `storage.objects` filtered by `bucket_id`.

```sql
-- SELECT (required for createSignedUrl to succeed):
-- Any authenticated user can generate a signed URL for any object in the bucket.
CREATE POLICY "storage_artifacts_select_authenticated"
    ON storage.objects
    FOR SELECT
    TO authenticated
    USING (bucket_id = 'excel-artifacts');

-- INSERT (publish step uses service_role — bypasses RLS; no policy needed).
-- Documenting intent: authenticated portal users CANNOT upload.
-- If explicit INSERT policy is needed for non-service_role paths, scope it:
-- USING (bucket_id = 'excel-artifacts' AND auth.role() = 'service_role')
-- But service_role already bypasses RLS, so this is documentation only.
```

**Key constraint:** `createSignedUrl` requires a `SELECT` policy on `storage.objects` for the
calling role. The authenticated user's JWT is validated against this policy before Supabase
issues the signed URL. Without this policy, `createSignedUrl` returns a 400/403 error even
for private buckets.

**service_role in GitHub Actions:** The publish script uses `SUPABASE_SERVICE_ROLE_KEY` (already
present in the workflow as a secret). service_role bypasses RLS entirely, so the script can
upload to Storage and upsert into `public.artifacts` without any INSERT policies.

---

## Data Flow — End to End

### Write Path (GitHub Actions → Supabase)

```
generate_weekly_pdfs.py completes
    → generated_docs/WR_*.xlsx files on runner disk
    ↓
[NEW STEP] publish_artifacts.py  (continue-on-error: true)
    ↓
for each WR_*.xlsx:
    1. Compute sha256 of file bytes
    2. Build storage_path = "{week_ending_iso}/{filename}"
    3. Upload to Storage bucket "excel-artifacts":
          supabase.storage.from_("excel-artifacts")
              .upload(storage_path, file_bytes,
                      file_options={"content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    "upsert": True})
       (upsert=True handles re-runs gracefully — same path replaces the object)
    4. Upsert metadata to public.artifacts:
          supabase.table("artifacts").upsert(
              {"work_request": wr, "week_ending": week_ending_iso,
               "week_ending_fmt": mmddyy, "variant": variant,
               "filename": filename, "storage_path": storage_path,
               "size_bytes": size_bytes, "sha256": sha256,
               "run_id": GITHUB_RUN_ID},
              on_conflict="sha256"
          ).execute()
    ↓
[EXISTING] Save caches, upload GitHub Actions artifact, summary steps
    (unchanged — the publish step failure does NOT block these)
```

**Failure isolation:** `continue-on-error: true` on the publish step ensures that a Supabase
outage, network blip, or schema error NEVER fails the billing run or blocks the cache save.
The billing pipeline's correctness is unaffected. The worst outcome is stale portal data until
the next run succeeds.

**Idempotency:** sha256-based upsert means re-running the same workflow with the same files
produces no duplicate rows. Re-running with `RESET_HASH_HISTORY=true` (force regen) produces new
files with a new run_id; if content is identical, sha256 matches and the row updates `run_id` and
`created_at`. If content differs, sha256 differs and a new row is inserted.

**Position in workflow:** After "Generate reports" (line ~525), after "Create Sentry release"
(~line 527), BEFORE "Generate artifact manifest" (~line 550). This ordering means the publish
step runs after Excel files are generated but before the GitHub Actions artifact zip is assembled.
The manifest step can then optionally reference Supabase metadata if desired.

Alternatively, it can slot AFTER "Generate artifact manifest" to allow the manifest script to
remain unchanged. Either position works — the key constraint is BEFORE the cache-save steps so
a billing-run failure doesn't also block the publish, and the publish step's `continue-on-error`
ensures the caches save regardless.

### Read Path (portal-v2 → Supabase)

```
User navigates to /artifacts (authenticated)
    ↓
useArtifactsTable hook
    supabase
      .from('artifacts')
      .select('id, work_request, week_ending, week_ending_fmt, variant, filename, storage_path, size_bytes, sha256, run_id, created_at')
      .order('week_ending', { ascending: false })
      .order('work_request', { ascending: true })
      [optional: .eq('work_request', filter) / .eq('week_ending', filterDate)]
    → rows (no mock fallback in v1.1 — real data or empty state)
    ↓
ArtifactExplorer renders virtualized table
    (react-virtual or CSS-only windowing — no external dep required for
     a few hundred rows at peak; add tanstack-virtual if > 1000 rows)
    ↓
User clicks Download for a row
    ↓
storage.ts getSignedDownloadUrl(row.storage_path)
    → supabase.storage.from('excel-artifacts').createSignedUrl(path, 60)
    → signed URL (60s expiry)
    ↓
Browser fetch / anchor click → .xlsx downloads
```

### Realtime Path (live insert notification)

```
New cron run completes → publish step upserts rows to public.artifacts
    ↓
Supabase Realtime broadcasts postgres_changes INSERT event
    ↓
useArtifactRealtime hook (portal-v2)
    supabase.channel('artifacts-inserts')
      .on('postgres_changes',
          { event: 'INSERT', schema: 'public', table: 'artifacts' },
          (payload) => {
            // Append new row to table state or invalidate query
            // Show toast: "New artifacts available from run {run_id}"
          })
      .subscribe()
    ↓
ArtifactExplorer updates without page refresh
```

**Realtime requirement:** The `public.artifacts` table must have `REPLICA IDENTITY FULL` or at
minimum the default `DEFAULT` (primary key only). INSERT events work with the default setting —
the new row's columns are included in the payload. No extra configuration needed.

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| `generate_weekly_pdfs.py` | Billing Excel generation (UNCHANGED) | Smartsheet API, Supabase billing_audit schema, generated_docs/ |
| `scripts/publish_artifacts.py` | Upload xlsx to Storage + upsert artifacts table | Supabase Storage API, public.artifacts, runner disk |
| `public.artifacts` table | Per-file metadata, query surface for portal | Supabase Postgres, RLS, Realtime |
| `excel-artifacts` Storage bucket | Binary xlsx object store | Supabase Storage, signed URL issuance |
| Supabase Auth | User session management, JWT issuance | portal-v2, hCaptcha verification service |
| `portal-v2/src/lib/storage.ts` | Signed URL generation on-demand | Supabase Storage JS SDK |
| `portal-v2/src/hooks/useArtifactsTable.ts` | Table query, filter/sort state | public.artifacts via supabase-js |
| `portal-v2/src/hooks/useArtifactRealtime.ts` | Live INSERT subscription | Supabase Realtime channel |
| `portal-v2/src/pages/ArtifactExplorer.tsx` | Virtualized table UI, search/filter controls | useArtifactsTable, useArtifactRealtime, storage.ts |
| `portal-v2/src/pages/Login.tsx` | Auth gate with hCaptcha | Supabase Auth, hCaptcha JS widget |

---

## Vercel Wiring

**Project configuration:**
- Root directory: `portal-v2` (Vercel detects Vite automatically)
- Build command: `tsc -b && vite build` (matches `npm run build` in package.json)
- Output directory: `dist` (Vite default)
- Framework preset: Vite

**SPA rewrite:** Already in `portal-v2/vercel.json`:
```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```

**Headers block to add** (CSP + frame-ancestors):
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Content-Security-Policy", "value": "frame-ancestors 'none'" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ]
}
```

**Environment variables (Vercel dashboard, Production + Preview):**

| Variable | Value source | Notes |
|----------|-------------|-------|
| `VITE_SUPABASE_URL` | Supabase project URL | Required; placeholder fallback in supabase.ts prevents hard crash |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public key | Required |
| `VITE_HCAPTCHA_SITEKEY` | hCaptcha dashboard sitekey | Required for login page; safe to expose (public key) |
| `VITE_SENTRY_DSN` | Sentry DSN | Optional; Sentry already initialized in sentry.ts |

**Broken Vercel↔Supabase connection symptoms and fixes:**

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| All queries return 0 rows; no auth errors | `VITE_SUPABASE_URL` or `VITE_SUPABASE_ANON_KEY` missing | Add env vars in Vercel dashboard → Redeploy |
| Auth redirect loops to wrong domain | Supabase Auth `Site URL` not set to Vercel domain | Dashboard → Auth → URL Configuration → set Site URL to `https://your-portal.vercel.app` |
| Signed URL 403 | Storage SELECT policy missing | Apply `storage_artifacts_select_authenticated` policy |
| hCaptcha widget missing | `VITE_HCAPTCHA_SITEKEY` unset | Add env var; widget renders but is non-functional without sitekey |
| Realtime not firing | Table not in Supabase Realtime publication | Dashboard → Database → Replication → add `public.artifacts` to `supabase_realtime` publication |
| `PGRST106` errors in browser | `public` schema not in PostgREST exposed schemas | Dashboard → API → Data API Settings → confirm `public` is listed (it is by default) |

---

## `scripts/publish_artifacts.py` — Key Design Constraints

This is a NEW file. It must follow the repo's Python conventions and guardrails:

1. **PEP 8, type hints, PEP 257 docstrings** — same standard as the rest of the repo.
2. **No modification of `generate_weekly_pdfs.py`** — publish_artifacts.py reads `generated_docs/WR_*.xlsx` from disk after the billing script completes. Zero coupling.
3. **Sentry instrumentation** — wrap the per-file upload in a `sentry_sdk.start_span` + `capture_exception` boundary. Use `_redact_exception_message()` pattern if importing from billing script; otherwise inline a simpler redaction (no WR/foreman PII in exception messages passed to Sentry).
4. **WR sanitization** — apply the same `_RE_SANITIZE_HELPER_NAME.sub('_', wr)[:50]` pattern when deriving `work_request` from filenames to ensure Supabase rows match the billing engine's sanitized keys.
5. **`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`** — already present as GitHub Actions secrets. The script reads them via `os.getenv()`. Both are already injected into the "Generate reports" step env block (lines 241–242 of the workflow); re-use the same secrets in the new publish step.
6. **Filename parsing** — use `scripts/generate_artifact_manifest.py` as a model; it already parses `WR_{wr}_WeekEnding_{MMDDYY}_{...}.xlsx` tokens. The publish script should import or replicate the same parser rather than duplicating regex.
7. **`supabase-py` dependency** — add `supabase>=2.0.0` to `requirements.txt` in the same PR. Verify it is not already present before adding.
8. **No `xlsxwriter`** — the publish script reads files, never writes them. No new Excel engine.

---

## Recommended Project Structure (new files only)

```
portal-v2/src/
├── hooks/
│   ├── useArtifacts.ts          # MODIFIED: replace Express calls with Supabase query
│   ├── useArtifactRealtime.ts   # NEW: Realtime INSERT subscription
│   └── useArtifactsTable.ts     # NEW: primary query hook (filter/sort state)
├── lib/
│   ├── storage.ts               # NEW: getSignedDownloadUrl wrapper
│   └── types.ts                 # MODIFIED: add BillingArtifact interface
├── pages/
│   ├── ArtifactExplorer.tsx     # NEW: rebuilt virtualized table page
│   └── Login.tsx                # NEW (or MODIFIED): add hCaptcha widget
scripts/
└── publish_artifacts.py         # NEW: GA publish step
billing_audit/
└── schema.sql                   # MODIFIED: append public.artifacts DDL block
portal/                          # REMOVED entirely
```

---

## Suggested Build Order (Dependency-Driven)

```
Phase 1: Data Layer Foundation
  ├── Apply public.artifacts DDL + RLS policies to Supabase
  ├── Apply Storage bucket creation + Storage RLS policies
  ├── Write + test scripts/publish_artifacts.py locally (SKIP_UPLOAD pattern)
  └── Add publish step to weekly-excel-generation.yml (continue-on-error)
  → GATE: at least one real run must produce rows in public.artifacts
           before frontend work begins. Unblock with a manual dispatch.

Phase 2: Auth Gate
  ├── Enable hCaptcha in Supabase Auth dashboard (secret key)
  ├── Add VITE_HCAPTCHA_SITEKEY to Vercel env
  ├── Build /login page with @hcaptcha/react-hcaptcha + Supabase signInWithPassword
  └── Auth guard (PrivateRoute / loader redirect) wrapping /artifacts
  → GATE: can log in and reach a protected page.

Phase 3: Artifact Table (Core Portal Feature)
  ├── Build useArtifactsTable hook (supabase-js query, filter/sort state)
  ├── Build ArtifactExplorer page (virtualized table, search bar)
  ├── Wire storage.ts getSignedDownloadUrl on download click
  └── Remove mock fallback from useArtifacts.ts (empty-table bug fix)
  → GATE: real artifacts browsable and downloadable.

Phase 4: Realtime + Polish
  ├── Add useArtifactRealtime hook (postgres_changes INSERT subscription)
  ├── Enable public.artifacts in Supabase Realtime publication
  ├── Framer Motion animations on table rows / notifications
  └── Dynamic search (debounced .ilike filter on work_request / week_ending_fmt)

Phase 5: Security Hardening
  ├── Update portal-v2/vercel.json with headers block (CSP, frame-ancestors)
  ├── /security-review pass: RLS audit, signed-URL scoping, secret hygiene
  └── Remove portal/ Express backend directory
```

**Dependency rationale:**
- Phase 1 must complete before Phase 3 — the frontend cannot be tested against real data until
  the publish script runs at least once and populates `public.artifacts`.
- Phase 2 can run in parallel with Phase 1 (Auth does not depend on the artifacts table).
- Phase 3 requires Phase 1 data AND Phase 2 auth gate to be meaningful.
- Phase 4 requires Phase 3 table to exist (Realtime subscription only useful with data flowing).
- Phase 5 (Express removal) is last — it can be done at any point after Phase 3 confirms the
  portal works without it, but deleting it earlier risks stranding any debugging surface.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Wrapping publish_artifacts.py failure in a hard failure

**What people do:** Remove `continue-on-error: true` from the publish step, or raise the step's
error to a job-level failure.
**Why it's wrong:** A Supabase outage would then fail the billing run, block cache saves, and
lose `hash_history.json` — causing full regeneration on the next run. The billing pipeline's
correctness must be completely independent of the portal's data layer.
**Do this instead:** Keep `continue-on-error: true`. Add Sentry `capture_exception` inside the
script so failures surface in the Sentry dashboard without blocking the run.

### Anti-Pattern 2: Reading artifacts from GitHub Actions artifact ZIPs in the frontend

**What people do:** Keep the Express artifact API pattern (fetch GitHub Actions API → download
zip → parse → serve).
**Why it's wrong:** GitHub Actions artifacts expire (90 days default), the GitHub API requires
a PAT with repo scope, and the pattern couples the portal to GitHub's rate limits and auth model.
The v1.1 goal is specifically to eliminate this coupling.
**Do this instead:** The publish step writes to Supabase Storage on every run. The frontend reads
from `public.artifacts` and generates signed URLs from Storage.

### Anti-Pattern 3: Storing week_ending as MMDDYY text only in Postgres

**What people do:** Store `week_ending` as `TEXT` (e.g., "051725") to match the filename token.
**Why it's wrong:** Postgres cannot sort or range-filter text dates correctly. "120124" (Dec 1)
sorts before "051725" (May 17) lexicographically even though May precedes December when parsed.
The index on `week_ending DESC` is only useful if the column is `DATE`.
**Do this instead:** Store `week_ending` as `DATE` (primary sort/filter column) AND
`week_ending_fmt` as `TEXT` (display and filename join). The publish script derives both from the
filename MMDDYY token via `datetime.strptime(mmddyy, "%m%d%y").date()`.

### Anti-Pattern 4: Removing the mock fallback before Supabase data exists

**What people do:** Delete `MOCK_ARTIFACTS` and the mock fallback in `useArtifacts.ts` at the
start of development, then have nothing to render during development.
**Why it's wrong:** Development happens before Phase 1 completes and before the publish step runs.
**Do this instead:** Replace the mock fallback with an explicit empty-state component (not a mock)
once real data flows. The empty state is a feature (it means "no artifacts yet"), not a bug.

### Anti-Pattern 5: Deduping on filename instead of sha256

**What people do:** Use `UNIQUE(filename)` as the upsert conflict target.
**Why it's wrong:** With `SUPABASE_HASH_STORE_AUTHORITATIVE=0` (legacy filenames containing
timestamps and hash tokens), every run produces a different filename for the same content.
Deduping on filename creates a new row every run, causing unbounded table growth. With
`SUPABASE_HASH_STORE_AUTHORITATIVE=1` (clean filenames), filename-based deduplication works, but
the column is not guaranteed stable across future changes. sha256 is the only stable content
identity regardless of naming convention.

---

## Integration Points

### External Services

| Service | Integration | Notes |
|---------|------------|-------|
| Supabase Storage | supabase-py upload (service_role); supabase-js createSignedUrl (anon+JWT) | Private bucket; signed URLs 60s expiry |
| Supabase Auth | Email+password + hCaptcha token; JWT in all supabase-js calls | Site URL must match Vercel domain |
| Supabase Realtime | postgres_changes channel on public.artifacts INSERT | Table must be in supabase_realtime publication |
| hCaptcha | Frontend: @hcaptcha/react-hcaptcha widget; Backend: Supabase validates secret key server-side | VITE_HCAPTCHA_SITEKEY safe to expose; secret key is in Supabase dashboard only |
| Vercel | SPA host for portal-v2; env vars injected at build time (VITE_ prefix) | Root dir = portal-v2; output dir = dist |
| Sentry | Python: existing sentry_sdk in publish_artifacts.py; React: existing @sentry/react in portal-v2 | Reuse existing DSN secrets |
| GitHub Actions secrets | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — already present in workflow | Do NOT use anon key in Actions; service_role only |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|--------------|-------|
| `generate_weekly_pdfs.py` ↔ `publish_artifacts.py` | File system only — publish reads generated_docs/WR_*.xlsx after billing script exits | Zero code coupling; billing script never imports publish |
| `publish_artifacts.py` ↔ `public.artifacts` | supabase-py upsert with on_conflict="sha256" | Idempotent; safe to re-run |
| `portal-v2` ↔ `public.artifacts` | supabase-js .from('artifacts').select() with JWT | RLS enforced; anon key cannot write |
| `portal-v2` ↔ `excel-artifacts` bucket | supabase-js createSignedUrl with JWT | SELECT policy required for authenticated role |
| `portal-v2` ↔ `portal/` Express | REMOVED — no communication after Express deletion | Express proxy routes (/api/runs, /api/artifacts/:id) are eliminated |

---

## Scaling Considerations

This is an internal billing portal with a small, fixed user base (1 senior engineer + billing
team). Scaling is not a primary concern. For reference:

| Scale | Architecture Notes |
|-------|-------------------|
| Current (1–10 users) | Supabase free/pro tier; no connection pooling needed; simple supabase-js queries |
| 10–100 users | Supabase pro tier; add Supabase connection pooler (PgBouncer) if query latency increases |
| 100+ users | Not in scope; this is an internal tool |

The `artifacts` table will accumulate roughly 50–200 rows per cron run (one per generated Excel).
At 7 runs/weekday + 3 runs/weekend = 43 runs/week × ~100 rows = ~4,300 rows/week. After one year,
~220,000 rows — well within Postgres's comfortable range for indexed point queries. No
partitioning or archival needed in v1.

---

## Sources

- [Supabase Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control) — RLS on storage.objects, SELECT policy requirement for createSignedUrl (MEDIUM confidence — WebSearch verified)
- [Supabase JS createSignedUrl reference](https://supabase.com/docs/reference/javascript/storage-from-createsignedurl) — expiresIn parameter (MEDIUM confidence — WebSearch verified)
- [Supabase Realtime Postgres Changes](https://supabase.com/docs/guides/realtime/postgres-changes) — INSERT subscription, filter syntax (MEDIUM confidence — WebSearch verified)
- [Supabase hCaptcha Auth](https://supabase.com/docs/guides/auth/auth-captcha) — enable CAPTCHA, sitekey vs secret key split (MEDIUM confidence — WebSearch verified)
- [Supabase Python SDK upsert](https://supabase.com/docs/reference/python/upsert) — on_conflict parameter (MEDIUM confidence — WebSearch verified)
- `billing_audit/schema.sql` — existing DDL patterns (idempotent ALTER TABLE IF NOT EXISTS, PGRST106 warning, PostgREST schema exposure) — HIGH confidence (live file)
- `.github/workflows/weekly-excel-generation.yml` — step order, existing secrets, timeout budget — HIGH confidence (live file)
- `portal-v2/src/lib/api.ts`, `useArtifacts.ts`, `types.ts`, `supabase.ts` — current frontend architecture to modify — HIGH confidence (live files)
- `portal-v2/package.json` — existing deps (supabase-js ^2.45.4, framer-motion ^11, react-router-dom ^6) — HIGH confidence (live file)

---
*Architecture research for: v1.1 Portal — Supabase-native Artifact Portal*
*Researched: 2026-05-29*
