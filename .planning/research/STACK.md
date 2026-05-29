# Stack Research

**Domain:** Supabase-native artifact portal (React SPA + GitHub Actions publish pipeline)
**Researched:** 2026-05-29
**Confidence:** HIGH (all critical versions verified via npm/PyPI/official docs; patterns verified via Supabase official docs)

---

## Context: What Already Exists (Do Not Re-research)

`portal-v2/` is already wired with the following — confirmed from `package.json`:

| Package | Installed Version |
|---------|------------------|
| react | ^18.3.1 |
| react-dom | ^18.3.1 |
| @supabase/supabase-js | ^2.45.4 |
| framer-motion | ^11.11.17 |
| react-router-dom | ^6.28.0 |
| lucide-react | ^0.460.0 |
| tailwindcss | ^3.4.14 |
| typescript | ^5.6.3 |
| vite | ^6.4.2 |
| @sentry/react | ^8.0.0 |
| @sentry/vite-plugin | ^2.0.0 |
| clsx | ^2.1.1 |
| tailwind-merge | ^2.5.4 |

**These require zero change.** The sections below cover ONLY what must be ADDED.

---

## Recommended Stack Additions

### 1. GitHub Actions Publish Step — Python supabase-py

**Mechanism: supabase-py (recommended over Supabase CLI or raw REST)**

| Technology | Version | Where Installed | Purpose |
|------------|---------|-----------------|---------|
| supabase (PyPI) | ^2.30.0 | GitHub Actions runner (`requirements.txt`) | Upload Excel to Storage + upsert artifact metadata into Postgres `artifacts` table |

**Why supabase-py over alternatives:**

- **Supabase CLI** (`supabase storage cp`): designed for schema migrations and local dev; lacks a native Postgres upsert surface — you would need a separate `curl` to PostgREST anyway, making it two different auth models to manage. Not idiomatic for a Python workflow.
- **Raw Storage REST + PostgREST curl**: requires hand-rolled multipart upload and separate HTTP calls; more attack surface for auth errors; brittle to API-key format changes (Supabase is actively migrating from `service_role` JWT to `sb_secret_xxx` keys — a Python SDK call abstracts this).
- **supabase-py**: single dependency, same auth surface as the frontend client, native `storage.from_().upload()` with `upsert=True` option, and `table().upsert()` for the metadata row. Maintained actively (v2.30.0 released 2026-05-06). The GitHub Actions step stays pure Python, consistent with the repo's Python-first CI ethos.

**Secret handling:** `SUPABASE_SERVICE_ROLE_KEY` is stored as a GitHub Actions secret and injected via `env:`. It is used ONLY in the CI publish step, never in `portal-v2/` or committed to source. The frontend uses the anon/publishable key exclusively.

**Integration point:** A new additive step appended to the tail of `weekly-excel-generation.yml` (after Excel generation + Smartsheet upload). It runs only when `SKIP_UPLOAD != 'true'` and is gated by `if: success()` so a billing pipeline failure does not attempt a partial publish.

**Canonical call shapes:**

```python
# Storage upload
client.storage.from_("artifacts").upload(
    path=storage_path,        # e.g. "2026/WR_12345_WeekEnding_052926_{hash}.xlsx"
    file=open(local_path, "rb"),
    file_options={"upsert": "true", "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
)

# Metadata upsert
client.table("artifacts").upsert({
    "work_request": wr,
    "week_ending": week_ending,      # ISO date string YYYY-MM-DD
    "variant": variant,
    "filename": filename,
    "storage_path": storage_path,
    "size_bytes": size_bytes,
    "sha256": sha256_hex,
    "run_id": os.environ["GITHUB_RUN_ID"],
    "created_at": datetime.utcnow().isoformat() + "Z",
}, on_conflict="storage_path").execute()
```

---

### 2. portal-v2 Frontend — New Additions Only

#### 2a. Row Virtualization: @tanstack/react-virtual

| Library | Version | Where Installed | Purpose |
|---------|---------|-----------------|---------|
| @tanstack/react-virtual | ^3.13.26 | `portal-v2/` (production dep) | Virtualized artifact table — only renders visible rows, O(1) memory regardless of row count |

**Why this over alternatives:**

- **react-window / react-virtualized**: older APIs, less TypeScript-native, not headless (impose DOM structure). TanStack Virtual is the current community standard for headless virtualization.
- **@tanstack/react-virtual v3** is the stable release series (v3.13.26, May 2026). The library reached stable v3 in 2024 and is actively maintained.
- `useVirtualizer` hook works without any wrapper component — it exposes `virtualItems`, `totalSize`, and scroll event handlers. You control the DOM entirely, which is required here because columns are styled with Tailwind and the table structure is driven by `@tanstack/react-table`.
- Pairing with `@tanstack/react-table` (see 2b below) is the standard pattern: react-table owns row model + sort/filter state, react-virtual owns the rendering window over `table.getRowModel().rows`.

**Integration point:** Installed in `portal-v2/`. The artifact table component uses `useVirtualizer` over the sorted+filtered rows from `useReactTable`. The container `<div>` gets `height` and `overflow-y: auto`; inner rows are positioned via `transform: translateY(...)` using `virtualItem.start`.

#### 2b. Headless Table: @tanstack/react-table

| Library | Version | Where Installed | Purpose |
|---------|---------|-----------------|---------|
| @tanstack/react-table | ^8.21.3 | `portal-v2/` (production dep) | Column definitions, sort state, column filter state, global search filter — headless, zero DOM |

**Why pair with react-table instead of hand-rolling:**

- Sort + multi-column filter state is non-trivial to build correctly (column-specific filter functions, multi-sort priority, server vs client model). React Table v8 (`@tanstack/react-table`) handles this with `getSortedRowModel()`, `getFilteredRowModel()`, and typed `ColumnDef`.
- The filter model distinguishes column-level filters (variant, week_ending range) from global filter (WR # / free-text search) — both are built in.
- The library is headless: it returns arrays of header/cell objects; you render them with Tailwind-styled `<th>` / `<td>` elements. No style lock-in.
- For this artifact table, client-side sort/filter is appropriate: the dataset is bounded (at most a few hundred artifacts per week window), Supabase already returns indexed data, and the UX requires instant keystroke-level response without a round-trip.

**Integration pattern:**

```typescript
const table = useReactTable({
  data: artifacts,          // ArtifactRow[] from Supabase query
  columns,
  state: { sorting, columnFilters, globalFilter },
  onSortingChange: setSorting,
  onColumnFiltersChange: setColumnFilters,
  onGlobalFilterChange: setGlobalFilter,
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
});
// then virtualizer runs over table.getRowModel().rows
```

#### 2c. hCaptcha: @hcaptcha/react-hcaptcha

| Library | Version | Where Installed | Purpose |
|---------|---------|-----------------|---------|
| @hcaptcha/react-hcaptcha | ^2.0.2 | `portal-v2/` (production dep) | CAPTCHA widget on the Supabase Auth login page; produces a `captchaToken` consumed by `supabase.auth.signInWithPassword` |

**Why hCaptcha and not reCAPTCHA:**

Supabase Auth natively accepts a `captchaToken` in its auth call options (`signInWithPassword`, `signUp`) for hCaptcha only. reCAPTCHA would require a custom Supabase Edge Function to verify the token server-side — additional code, additional attack surface, and explicitly out-of-scope per `PROJECT.md`.

**Integration pattern (Supabase-native):**

```typescript
// 1. Enable hCaptcha in the Supabase Dashboard → Auth → Security
// 2. Add VITE_HCAPTCHA_SITE_KEY to Vercel env vars (public, non-secret)
// 3. In the login form component:
import HCaptcha from '@hcaptcha/react-hcaptcha';

const captchaRef = useRef<HCaptcha>(null);
const [captchaToken, setCaptchaToken] = useState<string | null>(null);

// Render the widget:
<HCaptcha
  sitekey={import.meta.env.VITE_HCAPTCHA_SITE_KEY}
  onVerify={(token) => setCaptchaToken(token)}
  ref={captchaRef}
/>

// On submit:
const { error } = await supabase.auth.signInWithPassword({
  email,
  password,
  options: { captchaToken: captchaToken! },
});
captchaRef.current?.resetCaptcha();
```

**Configuration required:** hCaptcha site key and secret registered at dashboard.hcaptcha.com; secret entered in Supabase Dashboard → Auth → Bot and Abuse Protection. The `VITE_HCAPTCHA_SITE_KEY` is non-sensitive (it is embedded in the frontend bundle by design, same as Google's site key). The hCaptcha secret lives ONLY in the Supabase Dashboard — never in any env file or GitHub secret.

---

### 3. supabase-js v2 Client Patterns (portal-v2)

`@supabase/supabase-js` is already installed at `^2.45.4`. The current Context7-verified version is `2.58.0` — the range `^2.45.4` will resolve to `2.58.x` on `npm install`. No version bump needed; `^` already picks it up.

**Three integration points required:**

#### 3a. Querying the `artifacts` table with RLS

```typescript
// Authenticated client (uses JWT from Supabase Auth session)
const { data, error } = await supabase
  .from('artifacts')
  .select('id, work_request, week_ending, variant, filename, storage_path, size_bytes, sha256, created_at')
  .order('created_at', { ascending: false })
  .limit(500);  // bounded query; row count is small
```

The `artifacts` table RLS policy: `SELECT` allowed for `auth.role() = 'authenticated'`. No anonymous reads. The anon key is included in the frontend bundle but the RLS policy prevents any data access without a valid session.

#### 3b. Signed download URL

```typescript
const { data, error } = await supabase.storage
  .from('artifacts')
  .createSignedUrl(storagePath, 60);  // 60-second TTL
// data.signedUrl is the time-limited presigned URL
window.open(data.signedUrl, '_blank');
```

**TTL reasoning:** 60 seconds is sufficient for a browser to initiate a download from a clicked button; it prevents hotlinking. The signed URL scopes to the exact `storagePath` — it cannot enumerate other artifacts.

**Storage bucket RLS:** The `artifacts` bucket is set to **private** (not public). Download requires an authenticated signed URL. Service role is used only by the CI publish step; the frontend client uses the anon key + session JWT.

#### 3c. Realtime subscription (postgres_changes)

```typescript
const channel = supabase
  .channel('artifact-inserts')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'artifacts',
    },
    (payload) => {
      // Optimistically prepend to artifacts list
      setArtifacts((prev) => [payload.new as ArtifactRow, ...prev]);
    }
  )
  .subscribe();

// Cleanup on unmount:
return () => { supabase.removeChannel(channel); };
```

**RLS and Realtime:** Supabase Realtime applies RLS before broadcasting — it checks whether the subscribing user's session would pass `SELECT` on the incoming row. Since the `artifacts` table has `authenticated`-only SELECT, only logged-in users receive change events. No additional Realtime-specific policy is needed beyond the table RLS.

**What this replaces:** The legacy Express SSE poller (`/api/runs/status` SSE endpoint in `portal/server.js`). The Realtime channel delivers new-artifact notifications with sub-second latency and auto-reconnects.

---

## Vercel Deployment Configuration (portal-v2 in Monorepo)

**No new npm packages needed.** This is a Vercel project-settings + `vercel.json` concern.

### Required Vercel Project Settings

| Setting | Value | Reason |
|---------|-------|--------|
| Root Directory | `portal-v2` | Monorepo subdir; Vercel must `cd` into it before build |
| Build Command | `npm run build` (default) | Runs `tsc -b && vite build` |
| Output Directory | `dist` (default for Vite) | Vite outputs to `dist/` |
| Install Command | `npm ci` | Deterministic installs |
| Node.js Version | 20.x | Matches repo constraint |

### vercel.json (place in `portal-v2/vercel.json`)

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
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

The SPA rewrite (`/(.*)` → `/index.html`) is required for `react-router-dom` deep links — without it, a direct URL to `/artifacts/WR_12345` returns a Vercel 404. The `frame-ancestors 'none'` header locks the no-iframe requirement from `PROJECT.md`.

### Environment Variables (Vercel Dashboard)

| Variable | Value | Exposure |
|----------|-------|----------|
| `VITE_SUPABASE_URL` | `https://<project>.supabase.co` | Build-time, bundled (public) |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/publishable key | Build-time, bundled (public by design) |
| `VITE_HCAPTCHA_SITE_KEY` | hCaptcha site key | Build-time, bundled (public by design) |
| `VITE_SENTRY_DSN` | Sentry DSN | Build-time, bundled (public by design) |

**FORBIDDEN in Vercel env:** `SUPABASE_SERVICE_ROLE_KEY` must NEVER be set in the Vercel project. It belongs exclusively in GitHub Actions secrets. Adding it to Vercel would expose it to the browser bundle.

**`VITE_` prefix is mandatory** for Vite to inline env vars at build time. Anything without `VITE_` is excluded from the bundle by Vite's design.

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `service_role` key in `portal-v2/` or Vercel env | Bypasses RLS; if leaked via bundle exposes all data | Use anon key + session JWT in frontend; service_role only in GitHub Actions secret |
| Supabase CLI in the publish step | No native Postgres upsert; two auth models; overkill for a single-table write | supabase-py with `table().upsert()` |
| reCAPTCHA | Requires custom Edge Function for server-side verification; out of scope per PROJECT.md | `@hcaptcha/react-hcaptcha` — natively supported by Supabase Auth |
| react-window / react-virtualized | Older API, less TS-native, not headless | `@tanstack/react-virtual` v3 |
| `exceljs` server-side preview in CI or Edge Function | Explicitly deferred from v1 Artifact Explorer (PROJECT.md "Out of Scope") | Signed download URL for raw `.xlsx` |
| Custom SSE endpoint (Express pattern) | Express backend is being removed | Supabase Realtime `postgres_changes` channel |
| `@tanstack/react-query` | Adds another state-management layer; the artifact dataset is small and Realtime handles updates | Direct `supabase-js` query in a `useEffect` + Realtime channel |
| CSV / ZIP / PDF export | Out of scope for v1 (PROJECT.md "Out of Scope") | Deferred to v2+ |

---

## Installation Commands

### portal-v2 (new additions only)

```bash
cd portal-v2
npm install @tanstack/react-virtual @tanstack/react-table @hcaptcha/react-hcaptcha
```

### GitHub Actions runner (requirements.txt addition)

```
# Add to requirements.txt — scoped to the publish step only
supabase>=2.30.0
```

Or if a separate requirements-publish.txt is preferred to isolate the new dependency from the billing pipeline's environment:

```bash
pip install supabase>=2.30.0
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CI publish mechanism | supabase-py | Supabase CLI | No native Postgres upsert; two-auth-model complexity |
| CI publish mechanism | supabase-py | Raw REST + curl | Hand-rolled multipart; brittle to API key format migration |
| Row virtualization | @tanstack/react-virtual v3 | react-window | Older API, less TS-native, imposes DOM structure |
| Table logic | @tanstack/react-table v8 | Hand-rolled sort/filter | Correct multi-sort + filter state management is non-trivial; react-table is well-tested |
| CAPTCHA | @hcaptcha/react-hcaptcha | reCAPTCHA | Requires custom Edge Function server-side verify; out of scope |
| Realtime updates | Supabase Realtime postgres_changes | Polling / SSE | SSE required the Express backend being removed; Realtime is native to Supabase and RLS-aware |

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| @tanstack/react-virtual | ^3.13.26 | React 18.x | v3 stable; `useFlushSync: false` optional for React 19 compat |
| @tanstack/react-table | ^8.21.3 | React 18.x | v8 stable; headless, no peer dep conflicts |
| @hcaptcha/react-hcaptcha | ^2.0.2 | React 18.x | Includes TS types; no @types package needed |
| supabase (Python) | ^2.30.0 | Python 3.10+ | Python 3.12 in CI — confirmed compatible |
| @supabase/supabase-js | ^2.45.4 (→ 2.58.x) | React 18, Vite 6 | Node 18 dropped in 2.79.0; runner uses Node 20 — fine |

---

## Sources

- [@tanstack/react-virtual npm](https://www.npmjs.com/package/@tanstack/react-virtual) — version 3.13.26 confirmed (May 2026)
- [@tanstack/react-table npm / Cloudsmith Navigator](https://cloudsmith.com/navigator/npm/@tanstack/react-table) — version 8.21.3 confirmed
- [@hcaptcha/react-hcaptcha npm](https://www.npmjs.com/package/@hcaptcha/react-hcaptcha) — version 2.0.2 confirmed (Jan 2026)
- [supabase PyPI](https://pypi.org/project/supabase/) — version 2.30.0 confirmed (May 6, 2026)
- [Supabase Auth CAPTCHA docs](https://supabase.com/docs/guides/auth/auth-captcha) — hCaptcha native integration + `captchaToken` option verified
- [Supabase Realtime Postgres Changes docs](https://supabase.com/docs/guides/realtime/postgres-changes) — `channel().on('postgres_changes')` pattern verified; RLS enforcement confirmed
- [Supabase Storage createSignedUrl JS ref](https://supabase.com/docs/reference/javascript/storage-from-createsignedurl) — signed URL API verified
- [Supabase Storage upload Python ref](https://supabase.com/docs/reference/python/storage-from-upload) — `upsert=True` option verified
- [Vercel Vite framework docs](https://vercel.com/docs/frameworks/vite) — root directory + SPA rewrite pattern verified
- [Vercel community: SPA rewrite for Vite](https://community.vercel.com/t/rewrite-to-index-html-ignored-for-react-vite-spa-404-on-routes/8412) — confirmed required for react-router-dom deep links
- [Supabase API key migration discussion](https://github.com/orgs/supabase/discussions/29260) — legacy keys valid until end of 2026; new `sb_secret_xxx` format noted

---

*Stack research for: v1.1 Portal — Supabase-native Artifact Portal*
*Researched: 2026-05-29*
