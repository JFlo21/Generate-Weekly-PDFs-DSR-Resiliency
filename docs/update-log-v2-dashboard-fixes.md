# Update Log — Dashboard & Artifact Explorer Stabilization

**Date:** 2026-04-18
**Branch:** `railway-disconnection-plan`
**Scope:** `portal-v2/` frontend only. No backend code touched.

This log documents every change made to fix "artifacts not loading," the
broken dashboard table rendering, and the CORS-related UI regressions
reported against the v0 preview deployment.

> **Documentation convention.** This repo does **not** use Docusaurus. The
> established documentation pattern is `docs/` (implementation guides like
> `railway-to-render-transition-plan.md`, `sentry-implementation.md`) plus
> `memory-bank/` (project-state files like `activeContext.md`). This log
> follows that convention.

---

## 1. Diagnosis (from browser console)

The attached console output showed three distinct failures happening in
parallel on the v0 preview deployment:

| # | Symptom | Root cause |
|---|---|---|
| 1 | `Access to fetch at 'https://…railway.app/api/runs' has been blocked by CORS policy` | Railway backend's `CORS_ORIGIN` does not include the v0 preview origin `https://vm-7llxm0xcitwzuesa6yt2qnyn.vusercontent.net`. Browser throws `TypeError: Failed to fetch` before any response arrives. |
| 2 | `/api/events` fails repeatedly, ~3s cadence | `EventSource` auto-reconnect loop; CORS blocks leave the source stuck in `CONNECTING`, and the browser retries forever. |
| 3 | `/rest/v1/profiles?...` returns HTTP 406, `Cannot coerce the result to a single JSON object` | `supabase.from('profiles').select().single()` requires exactly one row. The logged-in user has no profile row yet, so zero rows → 406. |

A separate UX regression (not visible in console but reported by the user)
compounded the perception of "artifacts not loading":

| # | Symptom | Root cause |
|---|---|---|
| 4 | "I don't see the Excel files to download" even after data loaded | `DashboardPage.tsx` never auto-selected a run. `selectedRun` stays `null` until the user clicks a `RunCard`, which means `<ArtifactPanel run={null} />` short-circuits and renders nothing. |
| 5 | Navbar shows "Offline" when displaying sample data | `useRuns` flipped `isConnected = true` after the fallback, but the pill text/color didn't distinguish "live" from "sample data," so users had no signal about *why* they were seeing sample data. |

---

## 2. Fixes applied

All changes are surgical — no architectural rewrites.

### 2.1 Graceful backend-unreachable fallback

**File:** `portal-v2/src/hooks/useRuns.ts`

- Classify fetch errors: `TypeError` / `Failed to fetch` / `NetworkError` /
  `Load failed` → network error → swap in `MOCK_RUNS` from
  `portal-v2/src/lib/mockData.ts` so the dashboard is never empty.
- Introduce `isSampleData: boolean` state. Flips `true` when the fallback
  path runs, flips back to `false` on the next successful real fetch.
- Close `EventSource` on *any* error to stop the reconnect flood; the
  2-minute poll covers updates anyway.

**File:** `portal-v2/src/hooks/useArtifacts.ts`

- Same network-error classification. Falls back to
  `MOCK_ARTIFACTS[runId] ?? MOCK_ARTIFACTS[1]` so the right-hand Artifacts
  panel still renders sample Excel files for download.

**File:** `portal-v2/src/lib/api.ts`

- `search()` wraps its `fetch` in try/catch; on network errors it returns
  the in-memory `mockSearch(q)` results instead of throwing, so Cmd+K
  keeps working during CORS outages.

### 2.2 Supabase profile 406 resolved

**File:** `portal-v2/src/hooks/useAuth.ts`

- Switched `supabase.from('profiles').select().single()` to
  `.maybeSingle()`. Zero rows now returns `{ data: null, error: null }`
  instead of HTTP 406. Error logs downgraded to a single `console.warn`
  to stop the console spam.

### 2.3 Auto-select latest run (the "missing artifacts" fix)

**File:** `portal-v2/src/components/dashboard/DashboardPage.tsx`

- New `userHasSelected` state distinguishes "page just loaded" from "user
  clicked around."
- New `useEffect` selects `runs[0]` (most recent) automatically once
  `runs` is populated and the user hasn't interacted yet.
- `RunCard.onSelect` and `ArtifactPanel.onClose` both mark
  `userHasSelected = true` so manual deselection is honored.
- Net effect: as soon as the dashboard loads (real or sample data), the
  user sees the latest run's artifacts — including the downloadable
  `.xlsx` files — without needing to click anything.

### 2.4 Clear "Sample data" indicator throughout the UI

**File:** `portal-v2/src/components/layout/DashboardLayout.tsx`

- Banner is now gated on the runtime `isSampleData` flag from `useRuns`
  instead of the compile-time `USE_MOCK` constant. This means the banner
  correctly shows during runtime CORS fallbacks, not just when
  `VITE_API_BASE_URL` is unset.
- Banner copy updated to explain the cause: "Showing sample data — the
  backend is unreachable (CORS or offline). Real runs will appear
  automatically once the API is reachable."

**File:** `portal-v2/src/components/layout/Navbar.tsx`

- Connection pill now has three distinct states with matching colors:
  - **Sample data** — amber pill + `Beaker` icon
  - **Live** — emerald pill + `Wifi` icon
  - **Offline** — slate pill + `WifiOff` icon
- Tooltip on each state explains the cause so it's debuggable without
  opening DevTools.

---

## 3. Verification checklist

Use this after every deploy to confirm the dashboard is healthy.

1. **Page load populates immediately.** Hard refresh the dashboard.
   Within 2 seconds you should see:
   - A `RunCard` for the latest run highlighted as selected.
   - The Artifact Panel on the right listing the run's artifacts with
     working "Explore" and "Zip" buttons.
2. **Sample-data banner is accurate.**
   - If the Railway backend is reachable and CORS allows the origin →
     no banner, navbar shows "Live" (emerald).
   - If CORS is blocking or the backend is offline → amber banner appears
     and the navbar shows "Sample data" (amber).
3. **Excel download works.**
   - Click "Zip" on any artifact → `.zip` download starts.
   - Click "Explore" → the ArtifactExplorer opens, the file tree lists
     the archive contents, clicking an `.xlsx` file renders the styled
     preview, and the "Download .xlsx" button saves the original file.
4. **Cmd+K (⌘K / Ctrl+K) palette** opens, searches, and returns results
   even when the backend is unreachable (falls back to `mockSearch`).
5. **Console is quiet.** No repeated `Failed to fetch` spam, no 406 on
   `/profiles`, no `EventSource` reconnect loop.

---

## 4. Known remaining work (not in this changeset)

- **Permanent fix for CORS:** add
  `https://*.vusercontent.net`, `https://vercel.app`, and the production
  Vercel domain to the backend's `CORS_ORIGIN` env var once the service
  moves from Railway to Render (per `railway-to-render-transition-plan.md`).
- **Supabase profile auto-provisioning:** add a Postgres trigger on
  `auth.users` insert to create a default row in `profiles`. Tracked
  separately from this dashboard stabilization work.
- **Artifact preview caching:** the LRU cache layer
  (`portal/services/artifactCache.js`) is implemented but only exercised
  once the Render deployment is live.

---

## 5. Files touched in this changeset

- `portal-v2/src/hooks/useRuns.ts`
- `portal-v2/src/hooks/useArtifacts.ts`
- `portal-v2/src/hooks/useAuth.ts`
- `portal-v2/src/lib/api.ts`
- `portal-v2/src/components/dashboard/DashboardPage.tsx`
- `portal-v2/src/components/layout/DashboardLayout.tsx`
- `portal-v2/src/components/layout/Navbar.tsx`
- `docs/update-log-v2-dashboard-fixes.md` (this file)
- `memory-bank/activeContext.md` (status note appended)
