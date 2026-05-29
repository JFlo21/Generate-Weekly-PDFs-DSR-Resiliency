# Feature Research

**Domain:** Internal billing artifact portal — auth-gated file retrieval for a billing team
**Researched:** 2026-05-29
**Confidence:** HIGH (based on direct codebase inspection + established UX patterns for internal data portals)

---

## What Already Exists (portal-v2 baseline)

Before mapping new features, the existing components that survive into v1.1:

| Component | Status | What it does | v1.1 fate |
|-----------|--------|-------------|-----------|
| `LoginPage.tsx` | EXISTS — no hCaptcha | Email/password Supabase Auth, animated glass card, mode toggle (signin/signup) | KEEP shell, ADD hCaptcha widget, REMOVE signup mode |
| `AuthGuard.tsx` | EXISTS | Redirects unauthenticated users to `/login` | KEEP as-is |
| `SearchBar.tsx` | EXISTS — wrong scope | Searches run names/branches (GitHub-centric) | REPURPOSE for WR # / week-ending |
| `ArtifactExplorer.tsx` | EXISTS — wrong model | Browses files inside a GitHub Actions artifact ZIP via Express | REPLACE with Supabase Storage signed-URL download panel |
| `useArtifacts.ts` | EXISTS — mock fallback bug | Fetches from Express API; silently falls back to `MOCK_ARTIFACTS` on network error | REPLACE with Supabase `artifacts` table query |
| `supabase.ts` | EXISTS | Client initialized; placeholder-safe; no table queries yet | EXTEND with `artifacts` table types + Storage calls |
| `Toast.tsx` | EXISTS | Toast notification primitive (type: success/error/info) | KEEP; extend for Realtime insert toasts |
| `Skeleton.tsx` | EXISTS | Loading placeholder | KEEP |
| `CommandPalette.tsx` | EXISTS | Cmd+K palette backed by Express `/api/search` | REPURPOSE or drop; Express is removed |
| `DashboardPage.tsx`, `RunList.tsx`, `RunCard.tsx` | EXISTS — GitHub-centric | Lists workflow runs from Express | REPLACE with artifact-first layout |
| `StatsGrid.tsx` | EXISTS | Animated counters for run stats | REPURPOSE for artifact counts / last-run date |

**The empty-table bug:** `useArtifacts.ts` silently swaps in `MOCK_ARTIFACTS` on any network/CORS error. Billing team sees fake data and never knows the real table is empty. This is the top-priority correctness fix.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features a billing-team member expects from any internal file portal. Missing any of these = the portal feels broken or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Auth gate — login-first redirect** | Portal is reached via link-out (new tab) from another site; arriving unauthenticated must land on `/login`, not a blank or error state | LOW | `AuthGuard.tsx` already handles redirect; guard must fire before any data fetch |
| **hCaptcha on login form** | Supabase Auth supports hCaptcha natively via `captchaToken` param on `signInWithPassword` / `signUp`; internal tooling still needs bot protection on a public URL | MEDIUM | Requires Supabase project hCaptcha configuration + `@hcaptcha/react-hcaptcha` widget rendered in `LoginPage.tsx`; `VITE_HCAPTCHA_SITE_KEY` env var; token passed to auth call. No signup mode — remove it. |
| **Artifact table with real data** | Users need to see actual files, not mock data | LOW | Replace `useArtifacts.ts` Express-backed mock-fallback hook with a direct Supabase `artifacts` table query; RLS ensures row visibility; no Express proxy |
| **Columns: WR #, week-ending date, variant, file size, created date, download** | These are the exact dimensions billing team uses to identify the right file | LOW | Maps 1:1 to `artifacts` table schema (`work_request`, `week_ending`, `variant`, `size_bytes`, `created_at`); `filename` for display |
| **Download single file via signed URL** | Core job of the portal — get the Excel | LOW | `supabase.storage.from('artifacts').createSignedUrl(path, 300)` (5-min TTL); open in new tab or trigger browser download; no server proxy required |
| **Empty state / zero results** | Table must communicate "no artifacts yet" vs "search returned nothing" vs "loading" with distinct messaging | LOW | Three distinct states: skeleton during load, empty-database illustration on first load, "no results" inline message with clear-filters CTA on filtered empty |
| **Loading skeleton** | Table rows should show skeleton placeholders while Supabase query is in-flight | LOW | `Skeleton.tsx` already exists; apply per-row in the artifact table |
| **Error state** | If the Supabase query or signed-URL call fails, user must see an actionable error, never silent mock data | LOW | Eliminate the mock-fallback pattern entirely; surface error inline with retry button |
| **Variant badge display** | Variants (`primary`, `helper`, `VacCrew`, `_AEPBillable`, `_ReducedSub`) must be human-readable, not raw underscore strings | LOW | Map variant enum values to colored `Badge.tsx` chips; existing `Badge.tsx` primitive available |
| **Responsive layout** | Billing team may open the portal on a laptop; table must not overflow at common viewport widths | LOW | Tailwind responsive breakpoints; priority columns (WR #, week-ending, variant, download) always visible; size/created collapse at smaller widths |

### Differentiators (Elevate UX Beyond Bare Minimum)

Features that make the portal feel fast and purposeful rather than just "a list of files."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Debounced WR # / week-ending search** | Billing team's primary lookup is "give me WR_12345 for week 08/25" — a search bar faster than scrolling a long table | LOW | Debounce 250–300 ms (lodash `debounce` or `useDebounce` hook); fires a Postgres `ilike` on `work_request` or exact match on `week_ending`; `SearchBar.tsx` shell already exists, just needs new placeholder + handler |
| **Sortable columns** | Created date descending is the default (newest files first); WR # and week-ending sort let billing team scan chronologically or by job | LOW | Client-side sort for small result sets (<500 rows); column header click toggles asc/desc; sort indicator arrow (Lucide `ArrowUp`/`ArrowDown`) in header; active sort column highlighted |
| **Filterable variant column** | Billing team often wants "show me only _AEPBillable files" without typing | MEDIUM | Multi-select dropdown filter on `variant` column; options populated from distinct values in result set; selected filters shown as clearable chips below search bar; "clear all" control |
| **Clearable filter chips** | Filter state must be visible and easy to reset — internal tools that hide active filters confuse users | LOW | Chip row renders one badge per active filter (variant); X on each chip clears that filter; chips only render when at least one filter is active |
| **Column sort indicators** | Users must know which column is sorted and in which direction | LOW | Header cell shows sort icon; active column uses brand color; inactive columns show faint neutral icon on hover only |
| **Realtime new-artifact toast** | When the 2-hour cron run publishes new files while the portal is open, billing team should see them without a manual refresh | MEDIUM | Supabase Realtime `channel.on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'artifacts' })` subscription; on INSERT fire a `Toast` ("New artifacts available — click to refresh") rather than auto-inserting rows mid-scroll (prevents disorienting scroll-jump) |
| **Framer Motion row entrance animation** | New rows animate in subtly (fade + slide) on initial load and after refresh; consistent with existing `PageTransition.tsx` and `ArtifactExplorer.tsx` spring patterns | LOW | `AnimatePresence` + `motion.tr` with `initial={{ opacity: 0, y: 8 }}` → `animate={{ opacity: 1, y: 0 }}`; stagger delay on initial load |
| **Download button hover state + loading spinner** | Signed-URL generation is async (one round-trip to Supabase Storage); the button must indicate it is working | LOW | Button shows spinner while `createSignedUrl` is in-flight; disables to prevent double-click; reverts on error with toast |
| **Cmd+K palette repurposed for artifact lookup** | `CommandPalette.tsx` already exists and is wired to keyboard shortcut; rebase it onto the Supabase `artifacts` table instead of the removed Express `/api/search` | MEDIUM | Replace `SearchHit` data source from `api.search()` to a Supabase query; palette results show WR #, week-ending, variant; selecting a result scrolls table to that row or triggers download. Dependency: artifact table must be live. |
| **"Last updated" timestamp in header** | Shows when the most recent artifact was published — billing team sanity check that cron is running | LOW | `SELECT MAX(created_at) FROM artifacts` fetched once on mount; rendered as "Last run: X minutes ago" with `date-fns` `formatDistanceToNow` |

### Anti-Features (Explicitly Out of Scope for v1.1)

Features that seem valuable but must be deferred or rejected to keep v1.1 shippable and correct.

| Feature | Why Requested | Why Problematic / Deferred | Alternative |
|---------|--------------|---------------------------|-------------|
| **In-browser Excel preview (styled HTML)** | Billing team wants to verify file contents without downloading | Requires `exceljs` or SheetJS parsing client-side (~1 MB bundle) or a Supabase Edge Function; significant complexity; OUT OF SCOPE per `PROJECT.md` "deferred from v1" block | Download the file; open in Excel/Google Sheets |
| **Bulk ZIP download** | "Download all files for WR_12345 week 08/25" | Requires server-side ZIP assembly (Edge Function or client streaming); no S3 equivalent in Supabase Storage v1; OUT OF SCOPE per `PROJECT.md` | Download individually; future v1.2 via Edge Function |
| **Role management UI (admin panel)** | `AdminPage.tsx` + `UsersPage.tsx` already exist; tempting to wire them up | Internal portal has one operator (Juan Flores); role management UI adds auth complexity and surface area with zero v1.1 business value | Manage roles directly in Supabase dashboard |
| **Self-service signup** | `LoginPage.tsx` has a signup mode toggle | Billing team members are provisioned by the admin, not self-registered; open signup on an internal billing portal is a security hole | Remove signup toggle; admin creates users in Supabase dashboard |
| **CSV or PDF export of the artifact table** | Common request in internal data tools | The artifacts themselves ARE the deliverable; exporting a table of file names adds no billing value | Existing Excel files cover the use case |
| **reCAPTCHA on login** | Alternative to hCaptcha | Supabase Auth supports hCaptcha natively; reCAPTCHA requires a custom Edge Function token validator — extra code, extra attack surface, no benefit here; OUT OF SCOPE per `PROJECT.md` | hCaptcha only |
| **iframe embedding** | Another team wants to embed the portal | `frame-ancestors 'none'` is locked in CSP; embedding billing artifacts in arbitrary iframes is a security risk; OUT OF SCOPE per `PROJECT.md` | Link-out (new tab) is the access model |
| **Pagination (server-side cursor)** | Large datasets need pagination | The artifact table will have O(100s) of rows for months; indexed Postgres query + client-side virtual scrolling handles it without pagination complexity; revisit at 10k+ rows | Row virtualization (`@tanstack/react-virtual`) for long lists |
| **RunCard / workflow run list view** | `RunList.tsx` and `RunCard.tsx` are already built | The new portal is artifact-first, not run-first; billing team doesn't care which GitHub Actions run generated the file — they care about WR # and week-ending | Artifact table is the primary surface; run metadata is a secondary display field if needed |
| **Activity log UI** | `ActivityPage.tsx` exists | Download audit trail in Supabase (`artifact_downloads` table) is a security feature, not a user-facing dashboard for v1.1 | Log to Supabase table silently; surface in v2 |
| **Realtime auto-insert of new rows into table** | More "live" than a toast | Auto-inserting rows mid-scroll disorients users; toast + manual refresh is the correct pattern for a periodic-cron system where arrivals are infrequent (every 2 hours) | Toast notification only |

---

## Feature Dependencies

```
[AUTH-01: hCaptcha login gate]
    └──required by──> [AUTH-02: remove signup mode]
    └──required by──> [AUTH-03: AuthGuard redirect on link-out arrival]

[DATA-01: artifacts Postgres table + RLS]
    └──required by──> [TABLE-01: artifact table with real data]
    └──required by──> [SEARCH-01: debounced WR # / week-ending search]
    └──required by──> [SEARCH-02: variant column filter]
    └──required by──> [UI-05: Realtime new-artifact toast]
    └──required by──> [UI-06: Cmd+K palette on artifact data]

[DATA-02: Supabase Storage bucket + signed URLs]
    └──required by──> [TABLE-02: single-file download button]

[TABLE-01: artifact table rendering]
    └──required by──> [SEARCH-01: debounced search] (search filters the table)
    └──required by──> [SEARCH-02: variant filter chips] (filters the table)
    └──required by──> [TABLE-03: sortable columns] (sorts the table)

[TABLE-02: signed-URL download]
    └──enhances──> [TABLE-01] (download is a column action in the table)

[UI-05: Realtime subscription]
    └──enhances──> [TABLE-01] (triggers refresh prompt)
```

### Dependency Notes

- **AUTH before DATA:** The auth gate (RLS + anon key) must be in place before the artifacts table is exposed to the frontend; an open table defeats the security model.
- **DATA-01 before all TABLE/SEARCH:** The Supabase `artifacts` table and its RLS policies are the prerequisite for every table, search, and filter feature.
- **TABLE-01 is the trunk:** Sort, search, filter, and download are all modifiers on the artifact table — none are independent surfaces.
- **Cmd+K palette is optional/additive:** It enhances TABLE-01 but does not block it; safe to defer to a later phase within v1.1.

---

## MVP Definition

### Launch With (v1.1 core)

Minimum required for the portal to be credibly useful to the billing team:

- [ ] **Fix the empty-table bug** — eliminate `MOCK_ARTIFACTS` silent fallback; surface real errors
- [ ] **Supabase `artifacts` table query** — replace `useArtifacts.ts` Express hook with direct Supabase query
- [ ] **Artifact table** — WR #, week-ending, variant badge, file size, created date, download button
- [ ] **Signed-URL single-file download** — 5-min TTL, download spinner, error toast on failure
- [ ] **Auth gate** — login-first redirect; hCaptcha on login form; signup mode removed
- [ ] **Debounced search** — WR # or week-ending text search via Postgres `ilike`
- [ ] **Empty / loading / error states** — distinct, actionable, no silent mock fallback
- [ ] **RLS on `artifacts` table** — authenticated users only; anon key returns nothing

### Add After Core is Working (v1.1 follow-on phases)

- [ ] **Variant column multi-select filter + chips** — after table is live and real data confirms variant values in use
- [ ] **Sortable columns** — simple; add in same phase as filter
- [ ] **Realtime new-artifact toast** — after Supabase channel subscription is confirmed working in staging
- [ ] **Cmd+K palette rebased on artifacts** — after table is stable; palette is an accelerator, not a blocker

### Defer to v2+

- [ ] **Bulk ZIP download** — needs Edge Function; no v1.1 business pressure
- [ ] **In-browser Excel preview** — significant bundle cost; out of scope per PROJECT.md
- [ ] **Activity log UI** — audit trail is silent in v1.1; surface later
- [ ] **Server-side cursor pagination** — not needed until artifact count exceeds ~1000 rows

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Fix empty-table bug (remove mock fallback) | HIGH | LOW | P1 |
| Artifact table with real Supabase data | HIGH | LOW | P1 |
| Single-file signed-URL download | HIGH | LOW | P1 |
| Auth gate + hCaptcha + remove signup | HIGH | MEDIUM | P1 |
| Debounced search (WR # / week-ending) | HIGH | LOW | P1 |
| Empty / loading / error states | HIGH | LOW | P1 |
| RLS on artifacts table | HIGH | LOW | P1 |
| Sortable columns | MEDIUM | LOW | P2 |
| Variant filter chips (multi-select) | MEDIUM | MEDIUM | P2 |
| Realtime new-artifact toast | MEDIUM | MEDIUM | P2 |
| Framer Motion row entrance animation | LOW | LOW | P2 |
| "Last updated" timestamp in header | LOW | LOW | P2 |
| Download button spinner / loading state | MEDIUM | LOW | P2 |
| Cmd+K palette on artifact data | LOW | MEDIUM | P3 |
| Bulk ZIP download | MEDIUM | HIGH | P3 (v2+) |
| In-browser Excel preview | LOW | HIGH | P3 (v2+) |
| Activity log UI | LOW | MEDIUM | P3 (v2+) |

---

## portal-v2 Component Reuse Map

Explicit accounting of what survives, what gets replaced, and what is new — critical for preventing rework.

| Component / Hook | Action | Notes |
|-----------------|--------|-------|
| `LoginPage.tsx` | MODIFY | Add `@hcaptcha/react-hcaptcha` widget; remove signup mode toggle; pass `captchaToken` to Supabase auth call |
| `AuthGuard.tsx` | KEEP | Already handles unauthenticated redirect |
| `useAuth.ts` | KEEP | Supabase Auth session management already wired |
| `SearchBar.tsx` | REPURPOSE | Change placeholder to "Search by WR # or week-ending…"; debounce handler; clear button already present |
| `Toast.tsx` + `useToast.ts` | KEEP + EXTEND | Add Realtime insert notification message type |
| `Skeleton.tsx` | KEEP | Apply to artifact table rows during load |
| `Badge.tsx` | KEEP | Use for variant chips; may need new color mappings per variant |
| `GlassCard.tsx` | KEEP | Login page uses it; may use in stats header |
| `ParticleBackground.tsx` | KEEP | Login page atmosphere |
| `PageTransition.tsx` | KEEP | Route transition wrapper |
| `Sidebar.tsx` + `Navbar.tsx` + `DashboardLayout.tsx` | KEEP shell | Strip GitHub-run navigation; repoint to artifact-first layout |
| `ArtifactExplorer.tsx` | REPLACE | Current model browses files inside a ZIP via Express; new model is signed-URL download of a single `.xlsx`; component may be simplified to a download panel or removed |
| `ArtifactPanel.tsx` | EVALUATE | Inspect before decision; likely replaced with simplified download action |
| `FilePreview.tsx`, `StyledExcelView.tsx`, `InteractiveExcelView.tsx` | REMOVE | Excel preview is an anti-feature for v1.1; these depend on removed Express endpoints |
| `RunList.tsx`, `RunCard.tsx` | REMOVE | GitHub-run-centric view is replaced by artifact-first table |
| `CommandPalette.tsx` | REPURPOSE (P3) | Rebase data source from `api.search()` to Supabase `artifacts` query; defer if time-constrained |
| `StatsGrid.tsx` | REPURPOSE | Replace GitHub run counters with artifact count + last-run timestamp |
| `useArtifacts.ts` | REPLACE | Remove Express + mock-fallback; new hook queries `artifacts` table directly |
| `useRuns.ts` | REMOVE | GitHub runs hook has no role in artifact-first portal |
| `lib/api.ts` | REMOVE (or gut) | All calls went to Express; Express is gone; Supabase calls go through `lib/supabase.ts` directly |
| `lib/mockData.ts` | REMOVE | Source of the empty-table bug; no mock data in production portal |
| `lib/types.ts` | EXTEND | Add `ArtifactRecord` type matching `artifacts` table schema; keep `Profile`, `Toast`, `ActivityLog`; remove GitHub-centric `WorkflowRun`, `Artifact` (GitHub shape), `ArtifactFile`, `Job` types |
| `supabase/` directory | EXTEND | Add `artifacts` table migration + RLS policies + Storage bucket config |

---

## Sources

- Direct codebase inspection: `portal-v2/src/**` (2026-05-29)
- `PROJECT.md` v1.1 milestone definition + Out of Scope constraints (2026-05-29)
- Supabase Auth hCaptcha docs: native `captchaToken` parameter on `signInWithPassword` (HIGH confidence — Context7 / official Supabase Auth docs)
- Supabase Realtime `postgres_changes` INSERT subscription pattern (HIGH confidence — established Supabase Realtime pattern)
- Supabase Storage `createSignedUrl` for time-limited download links (HIGH confidence)
- UX pattern: toast-on-insert vs auto-row-insert for infrequent periodic updates — standard practice in internal ops tooling; avoids scroll-jump disorientation
- Domain knowledge: internal billing portals — file retrieval > content preview; WR # + date = primary lookup keys; role management UI is operational overhead not user value at small team size

---

*Feature research for: Portal — Supabase-native Artifact Portal (v1.1)*
*Researched: 2026-05-29*
