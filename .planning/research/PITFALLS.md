# Pitfalls Research

**Domain:** Supabase-native Artifact Portal — React 18 + Vite + supabase-js on Vercel, replacing Express backend. Billing PII data (WR numbers, foreman/customer names, dollar amounts). Additive GitHub Actions publish step. Production Python billing pipeline untouched.
**Researched:** 2026-05-29
**Confidence:** HIGH — pitfalls grounded in actual portal-v2 source code, confirmed Supabase documentation, and project-specific incident history from the Living Ledger.

---

## Critical Pitfalls

### Pitfall 1: service_role Key Leaking Into the Frontend Bundle

**What goes wrong:**
The Supabase `service_role` key bypasses ALL Row-Level Security. If it ends up in a `VITE_` environment variable, Vite bakes it into the JavaScript bundle at build time. Anyone who opens DevTools → Sources or runs `strings` on the bundle can extract it and read, write, or delete every row in every table, including billing PII.

**Why it happens:**
Developers reach for `VITE_SUPABASE_SERVICE_ROLE_KEY` because it looks like the other Supabase env vars (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) and it "just works" for testing. The GitHub Actions workflow already has `SUPABASE_SERVICE_ROLE_KEY` wired as a secret for the Python pipeline (line 242 of `weekly-excel-generation.yml`) — copying that variable name and prepending `VITE_` is a one-typo disaster.

**How to avoid:**
- The service_role key lives ONLY in GitHub Actions Secrets (`SUPABASE_SERVICE_ROLE_KEY`) and the Supabase dashboard backend. It must never appear in any file under `portal-v2/` or any Vercel environment variable.
- The `portal-v2` client uses ONLY `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`. The anon key is intentionally public — RLS is what protects the data, not key secrecy.
- Lint rule: add a grep CI step that fails if any `VITE_` variable name contains `SERVICE` or `SECRET`.
- In the additive publish step (GitHub Actions), use the service_role key server-side only, passed via `env:` block in the workflow step, never echoed or written to disk.

**Warning signs:**
- A `VITE_SUPABASE_SERVICE_ROLE_KEY` variable exists in Vercel project settings.
- The built `dist/assets/*.js` contains the string `eyJhbGci` (JWT prefix) longer than the anon key.
- The supabase client in `portal-v2/src/lib/supabase.ts` is initialized with anything other than `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.

**Phase to address:**
Phase 1 (Supabase Data Layer) — before any code is written. This is a pre-condition, not a feature.

---

### Pitfall 2: Public Storage Bucket Exposing Billing PII

**What goes wrong:**
Supabase Storage buckets have two modes: public (any URL serves the file, no auth) and private (requires a signed URL or service_role). If the `artifacts` bucket is created as public, every Excel file — containing WR numbers, foreman names, dollar amounts — is accessible to anyone with the URL pattern, which is guessable (`/storage/v1/object/public/artifacts/WR_12345_WeekEnding_...xlsx`).

**Why it happens:**
The Supabase dashboard defaults new buckets to public in some UI flows. The Storage setup guide examples often use public buckets for simplicity. Developers testing downloads find public buckets "work immediately" without signed-URL plumbing and ship without changing the setting.

**How to avoid:**
- Create the `artifacts` bucket with `public: false` explicitly. Verify in the Supabase dashboard under Storage → Policies that the bucket shows "Private."
- All file access from the frontend uses `supabase.storage.from('artifacts').createSignedUrl(path, expirySeconds)` — never the public URL method `getPublicUrl()`.
- The publish script (GitHub Actions) uploads using the service_role client to a private bucket. Downloads use signed URLs with a short expiry (600 seconds = 10 minutes is appropriate; see Pitfall 5 for expiry scoping).
- Add a Supabase storage policy that allows `SELECT` only for authenticated users (RLS on storage objects mirrors the `artifacts` table RLS).

**Warning signs:**
- `supabase.storage.from('artifacts').getPublicUrl(...)` appears anywhere in `portal-v2/src/`.
- The bucket URL (`/storage/v1/object/public/artifacts/...`) returns a file without an Authorization header.
- Supabase dashboard shows the bucket as "Public."

**Phase to address:**
Phase 1 (Supabase Data Layer) — bucket creation is the first infrastructure act.

---

### Pitfall 3: RLS Disabled or `USING (true)` Footgun

**What goes wrong:**
A `USING (true)` policy grants unrestricted SELECT to all callers, including unauthenticated (anon) requests. This is functionally equivalent to disabling RLS. With the `artifacts` table exposed via PostgREST (the Supabase API layer), any anon caller can `GET /rest/v1/artifacts` and retrieve all metadata rows — WR numbers, foreman names, filenames, SHA256 hashes.

**Why it happens:**
Developers add `USING (true)` while debugging a 403 to confirm "the policy is the problem." They fix the actual issue but forget to remove the permissive policy. Supabase also ships some template projects with `USING (true)` as a placeholder.

**How to avoid:**
The correct policy for the `artifacts` table:
```sql
-- Only authenticated (logged-in) users can read artifacts
CREATE POLICY "artifacts_select_authenticated"
  ON artifacts FOR SELECT
  TO authenticated
  USING (true);

-- anon role gets nothing
-- (no INSERT/UPDATE/DELETE policies — writes come via service_role from Actions)
```
Note: `TO authenticated` with `USING (true)` is correct and intentional — the `TO authenticated` clause restricts the policy to the `authenticated` role, so unauthenticated (anon) callers cannot read. The `USING (true)` clause applies only within that role scope. This is the standard Supabase pattern for "all logged-in users can read all rows."

Verify with:
```sql
SELECT schemaname, tablename, policyname, roles, qual
FROM pg_policies WHERE tablename = 'artifacts';
```
Confirm `roles = {authenticated}` and no policy exists for `{anon}`.

**Warning signs:**
- `curl https://<project>.supabase.co/rest/v1/artifacts -H "apikey: <anon-key>"` returns rows (without Authorization Bearer token).
- A policy in the dashboard shows `roles: anon` or `roles: public`.
- The `artifacts` table has RLS disabled entirely (visible in Table Editor → RLS toggle).

**Phase to address:**
Phase 1 (Supabase Data Layer) — schema + RLS DDL committed together in the same PR.

---

### Pitfall 4: Signed URL Expiry Too Long or Unscoped

**What goes wrong:**
A signed URL with a 24-hour or 7-day expiry is effectively a shareable public link for the duration. For billing PII, a link forwarded in Slack or email remains valid long after the session that generated it ends. Worse, signed URLs in Supabase Storage are not scoped to the requesting user — any signed URL for any path can be generated by any authenticated user unless a Storage policy restricts path access.

**Why it happens:**
Developers set long expiry (86400 seconds, "just 24 hours") to avoid users hitting expired links. They don't realize that a short expiry + refresh-on-demand is architecturally safer and no worse in UX.

**How to avoid:**
- Expiry: 600 seconds (10 minutes) for download-on-click patterns. Generate the signed URL at click time, not at page load. Do not pre-generate and cache signed URLs in the `artifacts` table.
- Scope: Storage RLS policy should restrict `SELECT` on `storage.objects` to paths under the user's own session or to a known prefix. For this portal (all authenticated users can see all artifacts), the path-scoping is less critical than the expiry, but the policy must still require `authenticated` role:
```sql
CREATE POLICY "artifacts_storage_select"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (bucket_id = 'artifacts');
```
- Never store a signed URL in the `artifacts` Postgres table — it will expire and the stored value becomes stale garbage. Store only `storage_path`; generate signed URLs transiently.

**Warning signs:**
- `createSignedUrl` called with `expiresIn` > 3600 (1 hour).
- Signed URLs are persisted in the `artifacts` table or in localStorage/sessionStorage.
- Signed URL generation happens at table-load time (pre-generating 50+ URLs on page mount).

**Phase to address:**
Phase 1 (Supabase Data Layer) for policy; Phase 2 (Frontend table + download) for the click-time generation pattern.

---

### Pitfall 5: The Mock-Fallback Bug Surviving the Migration (Known Existing Bug)

**What goes wrong:**
`useArtifacts.ts` (line 32–37) silently falls back to `MOCK_ARTIFACTS` on any `TypeError` or network-error-looking exception. `supabase.ts` initializes the client with `'https://placeholder.supabase.co'` when env vars are missing. Combined: a mis-configured Vercel deployment (missing `VITE_SUPABASE_URL`) will render the portal with mock data, showing no error — the billing team sees fake WR numbers from the sample dataset rather than real data or an honest error. This is the confirmed "empty table / wrong data" bug from the project context.

**Why it happens:**
The fallback was added for dev/preview DX — it keeps the UI interactive when the Express backend is unreachable. The problem is that the same fallback fires for Supabase misconfiguration, making failures invisible.

**How to avoid:**
- Remove the mock-data network-error fallback from `useArtifacts.ts` entirely in v1.1. Replace with an explicit error state rendered in the UI.
- Update `supabase.ts`: instead of a silent placeholder client, detect missing env vars and throw (or export a `configError` the app can surface on mount):
```typescript
if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set. ' +
    'Check Vercel environment variables.'
  );
}
```
- Keep `MOCK_ARTIFACTS` / `mockData.ts` only behind an explicit `VITE_USE_MOCK=true` flag for intentional demo mode — never as a silent fallback.
- Add a Vercel deployment check: the `build` command should fail if `VITE_SUPABASE_URL` is unset.

**Warning signs:**
- The portal renders with "DSR_Weekly_Report.xlsx" or "Resiliency_Summary.xlsx" — these are mock filenames.
- `[v0] Artifacts backend unreachable, using sample data.` appears in the browser console.
- No error toast or error state is shown in the UI when the Supabase connection fails.

**Phase to address:**
Phase 2 (Frontend table rebuild) — this is the first thing to remove when rebuilding `useArtifacts.ts` on top of Supabase.

---

### Pitfall 6: `getSession()` Used for Server-Trust Auth Decisions

**What goes wrong:**
`supabase.auth.getSession()` returns the session from the client's localStorage/cookie — it is client-controlled and can be tampered with. Using it to decide whether to show billing data is a security anti-pattern: a malicious actor could craft a fake session object in localStorage and bypass the auth check. The correct call for any auth decision that gates data is `supabase.auth.getUser()`, which validates the JWT with the Supabase Auth server.

**Why it happens:**
`getSession()` is faster (no network call) and appears in many supabase-js examples for getting the current user. The distinction between "client-stored session" and "server-verified user" is subtle and not prominently documented.

The existing `useAuth.ts` (line 50) already uses `getSession()` to initialize the auth state. This is the race window: between mount and the `onAuthStateChange` listener firing, `session` is set from client storage without server verification. The `getUser()` call should be the source of truth for gating data queries.

**How to avoid:**
- Use `supabase.auth.getUser()` (async, server round-trip) to verify the session before issuing any Supabase query that touches billing data.
- `getSession()` is acceptable for: initializing the loading spinner, determining whether to show the login page, and reducing FOUC. It is NOT acceptable for: deciding whether to execute a query against the `artifacts` table.
- Pattern:
```typescript
// On mount — check server truth
const { data: { user }, error } = await supabase.auth.getUser();
if (error || !user) { navigate('/login'); return; }
// Now safe to query artifacts
```
- RLS is the ultimate backstop: even if `getSession()` returns a stale or forged session, Supabase will reject queries where the JWT doesn't validate. Use `getUser()` as the application layer defense; RLS as the database layer defense.

**Warning signs:**
- `getSession()` is the sole auth check before rendering the artifact table.
- Auth guard component checks `session !== null` (from `getSession`) without a `getUser()` verification path.
- No server-round-trip auth check exists anywhere in the data-fetch path.

**Phase to address:**
Phase 3 (Auth + hCaptcha) — but the RLS backstop from Phase 1 provides coverage if Phase 3 ships later.

---

### Pitfall 7: hCaptcha Token Replay and Sitekey/Secret Mismatch

**What goes wrong:**
Three distinct failures:
1. **Token replay**: hCaptcha tokens are single-use. If the frontend submits the same token twice (e.g., from a cached form state or a retry loop), the second call fails with a cryptic auth error rather than a clear "captcha expired" message.
2. **Sitekey/secret mismatch**: The Supabase Auth dashboard captcha secret and the `data-sitekey` on the hCaptcha widget must match the same hCaptcha site configuration. Using a test sitekey with a production secret (or vice versa) causes all captcha verifications to fail silently — Supabase rejects the login with a generic error.
3. **Client-side verification only**: Never check "did the widget render successfully" and skip backend verification. Supabase Auth handles server-side verification when `captchaToken` is passed to `signInWithPassword` — do not add a second client-side check that can be bypassed.

**Why it happens:**
hCaptcha's test sitekey (`10000000-ffff-ffff-ffff-000000000001`) auto-succeeds on every challenge, making local dev work regardless of secrets. When the production sitekey is swapped in, secret mismatches surface as auth failures that look like network errors.

**How to avoid:**
- In Supabase Auth → Settings → Auth → Captcha: enable hCaptcha, paste the **secret key** (not the sitekey). Record which hCaptcha site config this secret belongs to.
- In the login component: pass the hCaptcha `data-sitekey` that corresponds to that same site config.
- On login form submit: call `supabase.auth.signInWithPassword({ email, password, options: { captchaToken } })` where `captchaToken` comes from the hCaptcha widget's `onVerify` callback.
- Reset the hCaptcha widget after every login attempt (success or failure) so the token cannot be reused.
- Never store the captchaToken in state beyond the single submit call.
- Vercel preview environments: use hCaptcha test keys in preview, production keys in production. Set these as Vercel environment variable overrides scoped by environment.

**Warning signs:**
- Login always fails in production but works locally.
- Supabase Auth logs show `captcha verification failed` or `invalid captcha token`.
- The hCaptcha widget renders but login still fails after checking the box.
- The Supabase Auth dashboard shows captcha enabled but no secret is set.

**Phase to address:**
Phase 3 (Auth + hCaptcha).

---

### Pitfall 8: Supabase Realtime — Table Not Added to Publication / RLS Interaction

**What goes wrong:**
Two common failures:
1. **Missing publication**: Supabase Realtime uses PostgreSQL logical replication. The `artifacts` table must be added to the `supabase_realtime` publication. Without this, `channel.on('postgres_changes', ...)` subscriptions connect but never fire — the UI never sees new artifacts from a cron run.
2. **RLS blocking Realtime**: Supabase Realtime respects RLS for `postgres_changes` events (as of Supabase Realtime RLS support). If RLS is correctly set to `authenticated` only, the Realtime channel must be created with an authenticated client (the user's JWT, not the anon key). An anon-key Realtime channel will connect but receive no events.

**Why it happens:**
Realtime setup in the Supabase dashboard is a separate step from table creation. Developers create the table, set up RLS, and wire the frontend subscription, but forget to enable Realtime on the table. The subscription appears to work (no error) because the WebSocket connection succeeds — the absence of events looks like "nothing changed" rather than "misconfigured."

**How to avoid:**
```sql
-- Add artifacts to the realtime publication
ALTER PUBLICATION supabase_realtime ADD TABLE artifacts;
```
This DDL must be in the schema migration committed in Phase 1.

In the frontend, create the Realtime channel after confirming the user is authenticated:
```typescript
const channel = supabase
  .channel('artifacts-changes')
  .on('postgres_changes',
    { event: 'INSERT', schema: 'public', table: 'artifacts' },
    (payload) => { /* handle new artifact */ }
  )
  .subscribe();
```
The `supabase` client here uses the user's JWT (set by `supabase.auth.setSession()` or managed by `onAuthStateChange`) — not a service_role client.

Cleanup on unmount:
```typescript
useEffect(() => {
  const channel = supabase.channel(...).on(...).subscribe();
  return () => { supabase.removeChannel(channel); };
}, []);
```

**Warning signs:**
- New artifacts uploaded by a cron run do not appear in the portal until the user refreshes.
- Browser DevTools → Network → WS shows the Realtime WebSocket connected but no messages arrive.
- `supabase.getChannels()` returns a channel with status `SUBSCRIBED` but no events fire.
- The `artifacts` table is not listed in `SELECT * FROM pg_publication_tables WHERE pubname = 'supabase_realtime'`.

**Phase to address:**
Phase 1 (Supabase Data Layer) for the DDL; Phase 4 (Realtime integration) for the frontend subscription.

---

### Pitfall 9: Realtime Subscription Leaks on Unmount

**What goes wrong:**
If the component that holds the Realtime subscription unmounts (e.g., user navigates away, session expires, React Strict Mode double-invokes effects) without calling `supabase.removeChannel(channel)`, Supabase accumulates open WebSocket channels. Each reconnect or page re-entry adds another subscription. With the default Supabase channel limit per client, this eventually causes new subscriptions to silently fail.

**Why it happens:**
React's `useEffect` cleanup is easy to forget. The Supabase `channel.subscribe()` call is async, so the returned channel object must be captured in a ref or closure for the cleanup function — developers who write `supabase.channel(...).on(...).subscribe()` inline have no handle to pass to `removeChannel`.

**How to avoid:**
Always capture the channel and clean up:
```typescript
useEffect(() => {
  const channel = supabase
    .channel('artifacts-live')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'artifacts' }, handler)
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}, []);  // empty deps — subscribe once per mount
```
In React Strict Mode (development), the effect runs twice — `removeChannel` fires between the two invocations. Verify the subscription survives this in dev before assuming it works in production.

**Warning signs:**
- `supabase.getChannels().length` grows beyond 1 after navigating away and back.
- New artifact notifications fire multiple times per event (duplicate handlers from stale subscriptions).
- Supabase dashboard → Realtime → Channels shows many open channels from the same client.

**Phase to address:**
Phase 4 (Realtime integration).

---

### Pitfall 10: Virtualization Pitfalls — Unstable Keys, Remeasurement Loops, Re-render Storms

**What goes wrong:**
The original portal-v2 artifact table was described as "memory-intensive and slowing the computer." The standard fix is row virtualization (TanStack Virtual or react-window), but naive implementations introduce new problems:
1. **Unstable row keys**: Using array index as key causes the virtualizer to remount rows during sort/filter, triggering full re-renders of every visible row.
2. **No fixed row height**: Virtualization libraries that measure row height dynamically (`estimateSize` + resize observer per row) create measurement loops when rows have animated height changes (Framer Motion). The scroll position jumps.
3. **Re-render storms from inline object creation**: Passing `{ style: computedStyle }` as a prop inline to each virtual row creates a new object reference every render, breaking `React.memo` and causing all visible rows to re-render on any state change (sort direction toggle, search input).
4. **Fetching all rows on mount**: Loading the full `artifacts` table (could be hundreds of rows across many weeks/WRs) into the React component tree before virtualizing defeats the memory saving. The correct pattern is server-side pagination (Postgres `LIMIT`/`OFFSET` or cursor-based) with the virtualizer rendering only the fetched page.

**How to avoid:**
- Row key: use `artifact.id` (Postgres primary key, stable across re-renders).
- Fixed row height: set a fixed `estimateSize` (e.g., 56px) and do not animate individual row height. Animate row content (opacity, translateY) not height.
- Memoize row renderers: `React.memo` + stable prop references. Extract the row component; do not define it inline in the virtualizer loop.
- Pagination: fetch 50 rows at a time. Use Supabase's `.range(from, to)` (maps to `LIMIT`/`OFFSET`) or `created_at`-based cursor pagination. Implement infinite scroll with the virtualizer's `overscan` triggering the next page fetch.
- Search/filter: issue a Supabase query with `.ilike('work_request', '%WR_12345%')` server-side — do not load all rows and filter in JavaScript.

**Warning signs:**
- Browser tab memory climbs above 200 MB with the artifact table open.
- Scrolling is janky or the viewport jumps on sort.
- React DevTools Profiler shows all visible rows re-rendering on a sort click.
- A single `useArtifacts` fetch loads 500+ rows in one query.

**Phase to address:**
Phase 2 (Frontend table rebuild).

---

### Pitfall 11: VITE_ Env Vars Are Build-Time and Fully Public

**What goes wrong:**
`VITE_` prefixed variables are inlined into the JavaScript bundle at build time by Vite. They are readable by anyone who inspects the bundle — there is no runtime secret injection. This is by design: the anon key and Supabase URL are meant to be public (RLS protects the data). The pitfall is treating `VITE_` variables as a secrets store. Beyond the service_role key (Pitfall 1), other sensitive values that must never be `VITE_`-prefixed: internal Supabase project refs, admin tokens, webhook secrets.

Additionally: Vercel environment variables can be scoped to Preview, Development, or Production. A `VITE_` variable set only in Production but not Preview causes Preview deployments to render with the placeholder Supabase client — silently falling back to mock data (Pitfall 5). This is a common "it works in prod but breaks in preview" failure.

**How to avoid:**
- `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`: set in Vercel for ALL environments (Production, Preview, Development). These are safe to expose.
- Any other Supabase secret: use Vercel server-side environment variables (without `VITE_` prefix) in a Vercel Edge Function or API Route. For this portal (no server-side rendering, no Vercel Functions), there are no other secrets needed in the frontend.
- Add a build-time check in `vite.config.ts`:
```typescript
if (!process.env.VITE_SUPABASE_URL) {
  throw new Error('VITE_SUPABASE_URL is required at build time');
}
```

**Warning signs:**
- Preview deployments show mock data while production shows real data.
- `VITE_SUPABASE_URL` is set to `Production` only in Vercel settings.
- The built bundle (run `strings dist/assets/*.js | grep supabase`) shows `placeholder.supabase.co`.

**Phase to address:**
Phase 1 (Supabase Data Layer) — Vercel project setup is the first step.

---

### Pitfall 12: Vercel SPA 404 on Direct URL and Missing Root Directory

**What goes wrong:**
Two distinct Vercel configuration failures:
1. **Missing SPA rewrite**: React SPA routing (React Router or similar) requires all routes (`/dashboard`, `/login`, `/artifacts/WR_12345`) to serve `index.html`. Without the Vercel rewrite, navigating directly to `/dashboard` or refreshing on any route returns a 404.
2. **Wrong root directory**: If Vercel's project settings have the root directory set to `/` (repo root) instead of `portal-v2/`, Vite's build output goes to the wrong path and Vercel either fails to find the build or serves the wrong `index.html`.

The existing `portal-v2/vercel.json` already has the correct rewrite (`{ "source": "/(.*)", "destination": "/index.html" }`). The risk is losing it during the Express-removal refactor or overriding it via Vercel dashboard settings.

**How to avoid:**
- Keep `portal-v2/vercel.json` with the catch-all rewrite. Do not delete it.
- Verify Vercel project settings: Root Directory = `portal-v2`, Build Command = `npm run build`, Output Directory = `dist`.
- After Express removal, confirm that `VITE_API_BASE_URL` is removed from Vercel env vars (it pointed to the Express backend). Leaving it set causes `api.ts` to attempt Express routes that no longer exist.
- Post-deploy smoke test: navigate directly to `/login` and `/dashboard` — both must load without 404.

**Warning signs:**
- Vercel deployment succeeds but browsing to `/login` returns a 404 or Vercel's default 404 page.
- The Vercel build log shows "No framework detected" or builds from the repo root instead of `portal-v2/`.
- `VITE_API_BASE_URL` is still set in Vercel after the Express backend is removed.

**Phase to address:**
Phase 5 (Express removal + Vercel cleanup).

---

### Pitfall 13: Additive Publish Step Failing the Billing Workflow

**What goes wrong:**
The additive GitHub Actions step that publishes artifacts to Supabase runs inside `weekly-excel-generation.yml`. If it fails (network error, Supabase unavailable, schema mismatch, malformed filename), it must NOT fail the billing workflow's exit code. The production Python pipeline's core mission — generating and uploading Excel files to Smartsheet — is independent of the Supabase publish. A broken publish step that propagates a non-zero exit code would cause the entire workflow to show as failed, triggering incident response for a billing system that is actually healthy.

**Why it happens:**
GitHub Actions steps fail by default on non-zero exit codes. A publish script that raises an exception or a `curl` call that fails network connectivity will set the step's exit code to non-zero and fail the job.

**How to avoid:**
- The publish step must use `continue-on-error: true`:
```yaml
- name: Publish artifacts to Supabase
  continue-on-error: true
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
  run: python scripts/publish_to_supabase.py
```
- The publish script must catch all exceptions internally, log them (Sentry capture), and exit 0. Failures are surfaced via Sentry, not via workflow failure.
- Do not place the publish step before the Excel upload to Smartsheet. Order: (1) Excel generation, (2) Smartsheet upload, (3) Supabase publish.
- Test the failure path explicitly: run the publish script with an invalid `SUPABASE_URL` and confirm the workflow still exits green.

**Warning signs:**
- The `weekly-excel-generation.yml` publish step does not have `continue-on-error: true`.
- A Supabase outage triggers billing team incident response.
- The publish step runs before the Smartsheet upload step.

**Phase to address:**
Phase 1 (Supabase Data Layer) — the publish step architecture is set here.

---

### Pitfall 14: Duplicate Artifact Rows From Non-Idempotent Upsert

**What goes wrong:**
The billing cron runs 7 times per weekday. If a WR's data hasn't changed (SHA256 hash matches), the Python engine skips regeneration. But if the publish step re-runs for any reason (workflow re-run, `force_generation=true`, hash history reset), it may attempt to insert a row for an artifact that already exists in the `artifacts` table. A plain `INSERT` creates a duplicate row. The portal then shows the same file twice with different `created_at` timestamps.

**Why it happens:**
The publish script inserts one row per file. Without an `ON CONFLICT` clause, re-runs create duplicates. The `sha256` hash is the natural idempotency key — same file, same hash, same row.

**How to avoid:**
Use an upsert with a unique constraint on `(work_request, week_ending, variant, sha256)` or on `storage_path`:
```sql
-- Unique constraint (add in schema DDL)
ALTER TABLE artifacts ADD CONSTRAINT artifacts_storage_path_key UNIQUE (storage_path);

-- Upsert in publish script (Python / supabase-py)
supabase.table('artifacts').upsert(
    row_data,
    on_conflict='storage_path'
).execute()
```
The `storage_path` is deterministic from `(WR, week_ending, variant, sha256)` — same file always produces the same path. On re-run, the upsert updates `run_id` and `created_at` instead of inserting a new row.

**Warning signs:**
- The `artifacts` table has multiple rows with the same `filename` and `work_request`.
- The portal shows duplicate entries for the same WR + week_ending combination.
- The publish script uses `supabase.table('artifacts').insert(...)` without `upsert`.

**Phase to address:**
Phase 1 (Supabase Data Layer) — the unique constraint and upsert pattern are schema decisions.

---

### Pitfall 15: `week_ending` Date Format Inconsistency (MMDDYY vs ISO)

**What goes wrong:**
The Python billing pipeline uses `MMDDYY` format for `week_ending` in filenames (e.g., `WR_12345_WeekEnding_052625_...xlsx`). The `artifacts` table `week_ending` column stores this value. If the publish script stores it as a raw `MMDDYY` string and the frontend searches/filters by ISO date (`2025-05-26`), the search returns nothing. Conversely, if the publish script converts to ISO but the filename-parsing logic on the frontend expects `MMDDYY`, downloads break.

**Why it happens:**
The MMDDYY format is a legacy artifact of the existing pipeline's filename convention (`build_group_identity` / `build_filename` in `generate_weekly_pdfs.py`). New Supabase-aware code defaults to ISO 8601 because that's what Postgres `DATE` columns expect. The two systems meet at the `artifacts` table schema definition — if the schema choice isn't made explicitly, both conventions appear in different places.

**How to avoid:**
- Store `week_ending` as a Postgres `DATE` column (ISO 8601 under the hood). The publish script converts `MMDDYY` → `DATE` at insert time:
```python
from datetime import datetime
week_ending_date = datetime.strptime(mmddyy_str, '%m%d%y').date().isoformat()
# e.g., '052625' → '2025-05-26'
```
- The `storage_path` and `filename` fields retain the original `MMDDYY` string for download URL construction.
- Frontend search uses the ISO date (from the `DATE` column) for filtering, formats it for display (`May 26, 2025`), and passes the raw `filename` to the download URL.
- Add a unit test in the publish script that asserts `'052625'` → `'2025-05-26'` and that a bad format raises an explicit error rather than inserting a null.

**Warning signs:**
- The `week_ending` column in `artifacts` is `TEXT` type holding `MMDDYY` strings.
- Date filter in the portal returns no results despite matching artifacts existing.
- The publish script does not call `strptime` or equivalent date parsing.

**Phase to address:**
Phase 1 (Supabase Data Layer) — schema column type decision.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `mockData.ts` fallback active during v1.1 dev | Frontend renders without Supabase configured | Masks misconfiguration in production; known to produce the empty-table bug | Never — remove fallback, gate behind explicit `VITE_USE_MOCK=true` |
| `USING (true)` policy without `TO authenticated` | Unblocks development immediately | anon callers can read billing PII | Never — always specify the role |
| Pre-generate signed URLs at page load | Simpler code | 50+ URLs generated per visit, all expire before user downloads | Never for PII data — generate at click time |
| Store service_role key in Vercel env | "Works like local" | Key is visible in Vercel dashboard; one misconfigured `VITE_` prefix exposes it to the bundle | Never |
| `week_ending TEXT` column (MMDDYY raw) | No conversion code needed | Date range queries, sorting, and display formatting all require workarounds | Never — use `DATE` type |
| `continue-on-error: false` on publish step | Easier to see publish failures | Supabase outage fails the billing workflow | Never — billing pipeline must not depend on portal publishing |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Supabase Storage | `createClient` with service_role in `portal-v2` | `createClient` with anon key only; service_role only in Actions |
| Supabase Auth + hCaptcha | Test sitekey in production Vercel | Scope hCaptcha keys by Vercel environment (Preview vs Production) |
| Supabase Realtime | Forgetting `ALTER PUBLICATION supabase_realtime ADD TABLE artifacts` | Include DDL in schema migration; verify with `pg_publication_tables` |
| Supabase PostgREST | No `TO authenticated` on RLS policy | Always specify role; verify with anon `curl` that returns 0 rows |
| Vercel + Vite | `VITE_` vars set for Production only | Set all `VITE_SUPABASE_*` for Production + Preview + Development |
| GitHub Actions publish | Non-zero exit fails billing workflow | `continue-on-error: true` + internal exception handling in publish script |
| supabase-js auth | `getSession()` for data-gate decisions | `getUser()` for server-verified auth; `getSession()` for UI-only state |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetch all `artifacts` rows on mount | Tab freezes, memory > 200 MB, Smartsheet-style "slows the computer" symptom | Server-side pagination (`LIMIT 50`), infinite scroll | ~100+ rows in the table |
| Client-side filter/search on full dataset | Search input lags; full re-renders on keystroke | Supabase `.ilike()` queries, debounced | ~50+ rows |
| Pre-generating signed URLs at render time | 50+ Storage API calls on page load, slow TTFB for table | Generate on download click only | Every page load |
| No `React.memo` on virtual row renderer | All visible rows re-render on sort/filter | Memoize row component, stable prop references | Visible row count > 10 |
| Realtime subscription without cleanup | Multiple duplicate event handlers accumulate | `useEffect` cleanup with `supabase.removeChannel()` | After 2-3 navigation cycles |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `service_role` key in `VITE_` variable | Complete database compromise; RLS bypass; all billing PII exposed | Key only in GitHub Actions Secrets + Supabase backend; grep CI check |
| Public Storage bucket | Any URL-holder downloads any billing Excel without auth | Create bucket with `public: false`; use `createSignedUrl` only |
| `USING (true)` without `TO authenticated` | anon callers read all artifacts metadata | Always specify `TO authenticated` in policy; test with anon curl |
| Signed URL expiry > 1 hour | Forwarded link gives prolonged access to billing PII | 600-second expiry; generate at click time, not page load |
| `getSession()` as data-gate | Stale/forged client session bypasses auth UI | `getUser()` for auth verification; RLS as backstop |
| hCaptcha client-side-only check | Bot login attempts succeed if server-side captcha disabled | Enable captcha in Supabase Auth dashboard; pass `captchaToken` to `signInWithPassword` |
| Storing signed URLs in `artifacts` table | Stale URLs + PII in database record | Store only `storage_path`; generate URLs transiently |

---

## "Looks Done But Isn't" Checklist

- [ ] **RLS enabled**: Verify with anon `curl` against `/rest/v1/artifacts` — must return `[]` not billing rows.
- [ ] **Storage bucket private**: Attempt `getPublicUrl` — must return a URL that 401s or 403s.
- [ ] **service_role key absent from frontend**: Run `grep -r SERVICE_ROLE portal-v2/` — must return nothing.
- [ ] **Mock fallback removed**: Confirm `useArtifacts.ts` has no reference to `MOCK_ARTIFACTS` outside an explicit `VITE_USE_MOCK` gate.
- [ ] **Realtime firing**: Upload a test artifact via the publish script while the portal is open — new row must appear without refresh.
- [ ] **Publish step non-blocking**: Kill the Supabase URL env var and run the workflow — billing steps must still pass green.
- [ ] **Signed URL expiry**: Inspect the URL returned by `createSignedUrl` — token expiry claim must be < 1 hour from now.
- [ ] **SPA routes work**: Navigate directly to `/login` and `/dashboard` on the Vercel preview URL — both must load without 404.
- [ ] **`week_ending` parses correctly**: Insert a row with `week_ending='052625'` via the publish script — verify the `artifacts` table stores `2025-05-26` (DATE type).
- [ ] **hCaptcha production keys**: Log in on the production Vercel URL (not localhost) — the hCaptcha widget must render and login must succeed.
- [ ] **`getUser()` called**: Confirm the auth guard component calls `supabase.auth.getUser()`, not just `getSession()`, before allowing access to the artifact table route.
- [ ] **`portal/` Express backend removed**: Confirm `portal/server.js` and related Express files are deleted and `VITE_API_BASE_URL` is removed from Vercel env vars.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| service_role key leaked in bundle | HIGH | Rotate the key immediately in Supabase dashboard; redeploy with key removed from Vercel; audit Supabase logs for unauthorized access |
| Public bucket exposing PII | HIGH | Change bucket to private in Supabase dashboard (immediate); audit Storage access logs; notify stakeholders if access confirmed |
| RLS disabled / `USING (true)` anon | MEDIUM | Add correct policy immediately; verify with anon curl; check Supabase API logs for anon reads |
| Mock fallback showing fake data | LOW | Set `VITE_SUPABASE_URL` correctly in Vercel; redeploy; confirm real data renders |
| Realtime not firing | LOW | `ALTER PUBLICATION supabase_realtime ADD TABLE artifacts`; run in Supabase SQL editor; subscription fires immediately |
| Publish step failing billing workflow | MEDIUM | Add `continue-on-error: true` to publish step; re-run failed workflow; Supabase publish failures are non-critical |
| Duplicate artifact rows | LOW | `DELETE FROM artifacts WHERE ctid NOT IN (SELECT min(ctid) FROM artifacts GROUP BY storage_path)`; add unique constraint; switch to upsert |
| Signed URL too long / stale | LOW | Update `createSignedUrl` call to use 600-second expiry; no data exposure occurred (URLs are authenticated) |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| service_role key leak (P1) | Phase 1: Supabase Data Layer | `grep -r SERVICE_ROLE portal-v2/`; Vercel env var audit |
| Public Storage bucket (P2) | Phase 1: Supabase Data Layer | Anon GET of storage URL returns 401/403 |
| RLS disabled / USING(true) (P3) | Phase 1: Supabase Data Layer | Anon curl `/rest/v1/artifacts` returns `[]` |
| Signed URL expiry unscoped (P4) | Phase 1 (policy) + Phase 2 (click-time gen) | Inspect JWT `exp` claim in signed URL |
| Mock-fallback bug surviving (P5) | Phase 2: Frontend table rebuild | No `MOCK_ARTIFACTS` reference in useArtifacts; error state renders on misconfiguration |
| `getSession()` for server-trust (P6) | Phase 3: Auth + hCaptcha | Auth guard calls `getUser()`; RLS backstop confirmed in Phase 1 |
| hCaptcha token replay / mismatch (P7) | Phase 3: Auth + hCaptcha | Production login with production hCaptcha keys succeeds |
| Realtime missing from publication (P8) | Phase 1 (DDL) + Phase 4 (subscription) | Upload test artifact; portal updates without refresh |
| Realtime subscription leak (P9) | Phase 4: Realtime integration | Navigate away and back 3x; `supabase.getChannels().length === 1` |
| Virtualization pitfalls (P10) | Phase 2: Frontend table rebuild | Memory < 100 MB with 200 artifacts; scroll is smooth |
| VITE_ vars public / Preview scoping (P11) | Phase 1: Supabase Data Layer | Preview deployment shows real data (not mock) |
| Vercel SPA 404 / root directory (P12) | Phase 5: Express removal + Vercel cleanup | Direct navigation to `/login` on Preview URL succeeds |
| Publish step failing billing workflow (P13) | Phase 1: Supabase Data Layer | Workflow passes with invalid Supabase URL on publish step |
| Non-idempotent upsert (P14) | Phase 1: Supabase Data Layer | Re-run publish script twice; artifact count unchanged |
| week_ending format inconsistency (P15) | Phase 1: Supabase Data Layer | `052625` stored as `2025-05-26`; date filter returns correct rows |

---

## Sources

- Portal-v2 source: `portal-v2/src/lib/supabase.ts` (placeholder client bug, confirmed), `portal-v2/src/hooks/useArtifacts.ts` (mock-fallback bug, confirmed), `portal-v2/src/hooks/useAuth.ts` (`getSession` pattern, confirmed), `portal-v2/src/lib/api.ts` (Express coupling, confirmed)
- Project context: `.planning/PROJECT.md` — privacy guarantee, billing PII scope, additive workflow constraint, Supabase secrets already in workflow (line 241-242 of `weekly-excel-generation.yml`)
- Supabase Auth hCaptcha: https://supabase.com/docs/guides/auth/auth-captcha
- Supabase RLS patterns: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase Realtime RLS: https://supabase.com/docs/guides/realtime/postgres-changes (RLS interaction confirmed)
- Supabase Storage signed URLs: https://supabase.com/docs/reference/javascript/storage-from-createsignedurl
- supabase-js `getUser()` vs `getSession()`: https://supabase.com/docs/reference/javascript/auth-getuser (server-side verification)
- Vite env var security: https://vitejs.dev/guide/env-and-mode#env-variables-and-modes (VITE_ prefix = public/build-time)
- Living Ledger (CLAUDE.md) — `_redact_exception_message`, PII guardrails, Supabase SQLSTATE classification, `billing_audit` schema DDL requirement per PR

---
*Pitfalls research for: Supabase-native Artifact Portal (v1.1 milestone — portal-v2, React 18 + Vite + supabase-js, billing PII)*
*Researched: 2026-05-29*
