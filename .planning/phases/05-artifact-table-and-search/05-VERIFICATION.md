---
phase: 05-artifact-table-and-search
verified: 2026-06-01T21:00:00-05:00
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Sign in as a billing or admin user and navigate to /dashboard. Confirm the artifact table renders real rows from Supabase (not placeholder text). Scroll to the bottom of a large result set (500+ rows). Confirm new rows load seamlessly without a visible Load More button."
    expected: "Table populates with real artifact rows. Scrolling near the bottom triggers a fetch and new rows append. No mock/sample data visible."
    why_human: "Requires a live Supabase session with real data in public.artifacts. Cannot be verified without network access to the deployed environment."
  - test: "Click the Download button on any artifact row."
    expected: "Button shows a spinner while in flight. The .xlsx file downloads to the local machine. No silent failure — any error surfaces as a toast message."
    why_human: "Requires a live Supabase Storage session with files in the excel-artifacts bucket. createSignedUrl(path, 300) must succeed against a real signed URL."
  - test: "Sign in as a pending-role user and navigate to /dashboard."
    expected: "The artifact table shows zero rows (RLS artifacts_select_billing_or_admin returns 0 for pending). The EmptyDBState copy 'No artifacts yet' renders."
    why_human: "Requires a live Supabase session with a pending-role test account to confirm RLS is enforced end-to-end."
  - test: "Type a partial WR number (e.g. '9000') in the search bar. Wait 250ms. Then type a date string (e.g. '05/26/25')."
    expected: "Table narrows after the 250ms debounce fires, not on every keystroke. Date input normalizes to '052625' and matches week_ending_fmt rows."
    why_human: "Requires a live Supabase session to confirm the server-side .ilike() filter returns correct rows. Debounce timing requires real-time observation."
  - test: "Select one or two variant chips, then click a sortable column header (e.g. 'File Size'). Confirm all three constraints apply simultaneously."
    expected: "Results satisfy the active variant filter AND the sort order in a single server round-trip. No client-side filtering visible."
    why_human: "Requires live data to verify the combined .or().in().order().range() chain returns the correct row set from PostgREST."
---

# Phase 05: Artifact Table and Search — Verification Report

**Phase Goal:** The billing team can see, search, filter, sort, and download their
generated Excel artifacts from a fast, virtualized table that reads real Supabase
data — with no mock fallback anywhere in the path.

**Verified:** 2026-06-01T21:00:00-05:00
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Real Supabase read path — `supabase.from('artifacts')` with no mock fallback anywhere in the artifact read path | VERIFIED | `useArtifactsInfinite.ts:34-39` calls `supabase.from('artifacts').select(...,{count:'exact'})`. `useArtifacts.ts` stub has no `MOCK_ARTIFACTS` import. `api.ts`/`mockData.ts` retain `MOCK_ARTIFACTS` but are not imported by any artifact read-path component. |
| 2 | 6 TABLE-01 columns rendered (WR #, week-ending, variant, file size, created, download) | VERIFIED | `ArtifactTable.tsx:25-32` defines all 6 `ColumnDef` entries. `ArtifactTableRow.tsx:36-77` renders all 6 cells. |
| 3 | Four distinct states: loading skeleton, empty-DB, no-results+clear, error+retry (TABLE-05 / D-07) | VERIFIED | `ArtifactTable.tsx:128-149` uses TanStack Query v5 `status === 'pending'` (not `'loading'`) for skeleton. `ErrorState`, `EmptyDBState`, `NoResultsState` all present and wired. Exact D-07 copy confirmed in `ArtifactEmptyState.tsx`. |
| 4 | Infinite scroll via `useInfiniteQuery` + `.range()` pagination; `useVirtualizer` virtualizes rows in a fixed-height container (TABLE-03) | VERIFIED | `useArtifactsInfinite.ts:21-72` uses `useInfiniteQuery` with `initialPageParam: 0` and `.range(from, to)`. `ArtifactTable.tsx:94-99` uses `useVirtualizer` with `style={{ height: 'calc(100vh - 280px)', overflow: 'auto' }}` (Pitfall 5 satisfied). |
| 5 | `fetchNextPage` is guarded (CR-01 fix applied) — runs in `useEffect`, not render phase | VERIFIED | `ArtifactTable.tsx:109-118`: `useEffect` with `[lastItemIndex, allRows.length, q.hasNextPage, q.isFetchingNextPage, q.fetchNextPage]` dependencies. No bare `fetchNextPage()` call in render body. |
| 6 | Signed-URL download via `createSignedUrl(path, 300)` at click time; no public URLs; no service_role key (TABLE-04 / DATA-05 / SEC-05) | VERIFIED | `useDownloadArtifact.ts:17-19`: `supabase.storage.from('excel-artifacts').createSignedUrl(storagePath, 300)`. No `service_role` present in the file. `useToast` is NOT called inside the hook — `addToast` is threaded as a parameter (Pitfall 7). |
| 7 | Search sanitizer strips single-quote + injection chars (CR-02 fix applied) | VERIFIED | `searchNormalize.ts:25`: `raw.replace(/['",()%*]/g, '').trim()` — single-quote included. `sanitizeSearchTerm` is called before `normalizeSearchTerm` at the query seam (`useArtifactsInfinite.ts:44`). |
| 8 | Debounced 250ms search input; search + variant filter + sort combine in ONE server-side query (SEARCH-01, SEARCH-04) | VERIFIED | `ArtifactTable.tsx:46`: `useDebounce(searchInput, 250)`. `debouncedSearch` feeds into `params.search` which is in the `queryKey`. Single `.or().in().order().range()` chain in `useArtifactsInfinite`. No client-side filtering. |
| 9 | Variant filter multi-select with clearable chips + friendly labels; sort with asc/desc indicators; both server-side (SEARCH-02, SEARCH-03) | VERIFIED | `VariantFilterBar.tsx`: `getVariantLabel(option)` applied to every option and chip. `X` button per chip. "Clear" affordance present. `ArtifactTable.tsx:84,219-253`: `onSortingChange: setSorting`, `manualSorting: true`, `ArrowUp`/`ArrowDown`/`ArrowUpDown` lucide icons per sortable column. |

**Score: 9/9 truths verified**

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `portal-v2/src/lib/searchNormalize.ts` | VERIFIED | `normalizeSearchTerm` + `sanitizeSearchTerm` exported. CR-02 fix: `'` stripped. |
| `portal-v2/src/lib/variantLabels.ts` | VERIFIED | `VARIANT_LABELS` map + `getVariantLabel` fallback. All D-10 test cases covered. |
| `portal-v2/src/hooks/useDebounce.ts` | VERIFIED | 8-line impl, no lodash dep, `useState`+`useEffect` cleanup pattern. |
| `portal-v2/src/lib/types.ts` | VERIFIED | `BillingArtifact` interface present (9 required keys). Express `Artifact` type preserved per D-02. |
| `portal-v2/src/App.tsx` | VERIFIED | `queryClient` at module scope. `QueryClientProvider` wraps `BrowserRouter` as outermost provider. |
| `portal-v2/src/hooks/useArtifactsInfinite.ts` | VERIFIED | `useInfiniteQuery`, `initialPageParam: 0`, `count: 'exact'`, `or()+in()+order()+range()` chain, sanitize+normalize applied. |
| `portal-v2/src/hooks/useDownloadArtifact.ts` | VERIFIED | `createSignedUrl(path, 300)`, error toast via threaded `addToast`, no `useToast()` inside hook, no `service_role`. |
| `portal-v2/src/hooks/useArtifacts.ts` | VERIFIED (stub) | No `MOCK_ARTIFACTS` import. No `[v0]` log. Exported `useArtifacts` name preserved. Returns `Artifact[]` type (WR-06 type mismatch — WARNING only, not a blocker; Phase 07 owns cleanup). |
| `portal-v2/src/components/artifacts/ArtifactTable.tsx` | VERIFIED | `useVirtualizer`, `manualSorting: true`, `status === 'pending'`, guarded `fetchNextPage` in `useEffect`, `useToast()` hoisted, `ToastContainer` co-located, `<ArtifactSearchBar>` + `<VariantFilterBar>` rendered. |
| `portal-v2/src/components/artifacts/ArtifactTableRow.tsx` | VERIFIED | `React.memo` at module scope. 6 cells. `week_ending_fmt` displayed (never raw ISO). `getVariantLabel`, `formatSize`, `formatDate` all used. Download button with `Loader2` spinner when `isDownloading`. |
| `portal-v2/src/components/artifacts/ArtifactEmptyState.tsx` | VERIFIED | `EmptyDBState`, `NoResultsState`, `ErrorState` all exported. Exact D-07 copy present. |
| `portal-v2/src/components/artifacts/ArtifactSearchBar.tsx` | VERIFIED | Controlled input, `onChange('')` clear button, `useDebounce` NOT inside this component (debounce lives in parent). |
| `portal-v2/src/components/artifacts/VariantFilterBar.tsx` | VERIFIED | `getVariantLabel` applied. Clearable chips with `X`. "Clear" affordance. Toggle logic correct. |
| `portal-v2/src/components/dashboard/DashboardPage.tsx` | VERIFIED | Thin shell rendering `<ArtifactTable />`. No legacy `useRuns`, `ArtifactExplorer`, `ArtifactPanel`, `useArtifacts` imports. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `App.tsx` | `@tanstack/react-query` | module-scope `new QueryClient()` + `<QueryClientProvider client={queryClient}>` | VERIFIED | Lines 19-27 (client), line 38 (provider). |
| `useArtifactsInfinite.ts` | `public.artifacts` | `supabase.from('artifacts').select(...,{count:'exact'}).or().in().order().range()` | VERIFIED | Lines 34-61. All four operators confirmed in sequence. |
| `useDownloadArtifact.ts` | `excel-artifacts` bucket | `supabase.storage.from('excel-artifacts').createSignedUrl(storagePath, 300)` | VERIFIED | Lines 17-19. TTL=300 confirmed. |
| `DashboardPage.tsx` | `ArtifactTable.tsx` | `<ArtifactTable />` as dashboard body | VERIFIED | Line 24. |
| `ArtifactTable.tsx` | `useArtifactsInfinite` + `useVirtualizer` | `data.pages.flatMap(p=>p.rows)` → `useVirtualizer count` | VERIFIED | Lines 62-63, 94-99. |
| `ArtifactTable.tsx` | `useDebounce` | `useDebounce(searchInput, 250)` → `params.search` → `queryKey` | VERIFIED | Lines 46, 55-60. |
| `ArtifactSearchBar.tsx` | parent `onChange` prop | controlled input fires `onChange(e.target.value)` | VERIFIED | Line 27. No `useDebounce` inside component (correctly in parent). |
| `VariantFilterBar.tsx` | `getVariantLabel` | renders dynamic option labels through friendly-label map | VERIFIED | Lines 3, 46, 60. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ArtifactTable.tsx` | `allRows` | `q.data?.pages.flatMap(p => p.rows)` from `useArtifactsInfinite` | Yes — `supabase.from('artifacts')` DB query, not static return | FLOWING |
| `useArtifactsInfinite.ts` | `rows` | `supabase.from('artifacts').select(...)...range()` | Yes — PostgREST query against `public.artifacts` with RLS | FLOWING |
| `useDownloadArtifact.ts` | `data.signedUrl` | `supabase.storage.from('excel-artifacts').createSignedUrl(...)` | Yes — live Storage API call at click time | FLOWING (human-verify) |

---

### Requirements Coverage

| Requirement | Phase 05 Plan | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| TABLE-01 | 05-01, 05-03 | 6-column artifact table | SATISFIED | `ArtifactTable.tsx` COLUMNS + `ArtifactTableRow.tsx` 6 cells |
| TABLE-02 | 05-02 | Real Supabase data; mock fallback removed | SATISFIED | `useArtifacts.ts` has no `MOCK_ARTIFACTS`; `useArtifactsInfinite` is the real read path |
| TABLE-03 | 05-02, 05-03 | Virtualized, server-side paginated | SATISFIED | `useVirtualizer` + `useInfiniteQuery` + `.range()` |
| TABLE-04 | 05-02, 05-03 | Download via signed URL with in-progress state | SATISFIED | `useDownloadArtifact` TTL=300, `Loader2` spinner in `ArtifactTableRow` |
| TABLE-05 | 05-03 | Distinct loading / empty / error states | SATISFIED | All 4 states confirmed in `renderBody()` |
| SEARCH-01 | 05-01, 05-04 | Debounced search by WR # or week-ending | SATISFIED | `useDebounce(searchInput, 250)`; `.or(work_request.ilike,week_ending_fmt.ilike)` |
| SEARCH-02 | 05-04 | Variant multi-select with clearable chips | SATISFIED | `VariantFilterBar` with toggle + chips + `X` + "Clear" |
| SEARCH-03 | 05-04 | Sortable columns with asc/desc indicators | SATISFIED | `onSortingChange: setSorting`, `manualSorting: true`, lucide sort icons |
| SEARCH-04 | 05-02, 05-04 | Dynamic options; search+filter+sort combine server-side | SATISFIED | Single `.or().in().order().range()` chain; all three feed `queryKey` |

**All 9 Phase 05 requirements: SATISFIED**

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `ArtifactTable.tsx:58` | `sort.id as ArtifactsQueryParams['sortColumn']` — unchecked `as` cast (WR-01) | WARNING | If a non-sortable column somehow triggers sort, Supabase returns 400. `SORTABLE_IDS` set exists but is not used to guard the cast. Not a blocker — `enableSorting: false` on non-sortable columns is the UI guard. |
| `ArtifactTable.tsx` + `App.tsx:81` | Two independent `ToastContainer` instances (WR-05) | WARNING | Download error toasts render in `ArtifactTable`'s local container; auth toasts in App's container. Both functional; visually two stacks may overlap depending on CSS z-index. Phase 06 (polish) is the correct fix venue. |
| `useArtifacts.ts:10` | Returns legacy `Artifact` type instead of `BillingArtifact` (WR-06) | WARNING | Latent type-safety gap. Phase 07 owns file deletion; no active consumers of this stub's return value. |
| `ArtifactTable.tsx:121-124` | `clearFilters` not wrapped in `useCallback` (WR-04) | INFO | No stale-closure bug today (setters are stable). Lower priority than WR-01/WR-05. |
| `ArtifactTable.tsx:68-76` | Variant-options query fetches all rows; no `.limit()` or distinct (WR-03) | WARNING | With large artifact tables, sends more data than needed over the wire. Bounded by global `staleTime: 30_000`. Not a correctness issue. |

**No blockers found.** All CRITICAL issues from the code review (CR-01, CR-02) are confirmed fixed in commit `82130fb`.

---

### Human Verification Required

The following items require a live Supabase session and cannot be verified programmatically.

#### 1. Live Data Smoke Test — Table Loads Real Rows

**Test:** Sign in as `billing` or `admin` user. Navigate to `/dashboard`.
**Expected:** Artifact table renders real rows from `public.artifacts`. Row count, WR numbers, and week-ending dates match what is in the database. No "No artifacts yet" text unless the database is genuinely empty.
**Why human:** Requires a live authenticated Supabase session. Cannot be confirmed without network access to the deployed environment.

#### 2. Signed-URL Download Delivers Real File

**Test:** Click the Download button on any artifact row. Observe the button state, then check the download.
**Expected:** Button shows spinner (`Loader2`) during the `createSignedUrl` call. The correct `.xlsx` file lands in the downloads folder. If the file is missing from Storage, an error toast appears — no silent failure.
**Why human:** Requires a live Supabase Storage session with files in the `excel-artifacts` bucket.

#### 3. RLS Pending-Role Zero-Row Enforcement

**Test:** Sign in as a `pending`-role test account. Navigate to `/dashboard`.
**Expected:** Table shows zero rows. Either `EmptyDBState` copy ("No artifacts yet") renders, or an error state renders if the RLS policy returns an error rather than empty rows.
**Why human:** Requires a `pending`-role test account in the live Supabase project.

#### 4. 500+ Row Scroll Without Jank

**Test:** With a full artifact dataset loaded, scroll rapidly from top to bottom of the table.
**Expected:** DOM stays shallow (virtualized). No tab freeze. New pages load seamlessly at the scroll boundary. No "Load More" button visible.
**Why human:** Performance feel requires a real browser and a large dataset. Jank cannot be detected by static analysis.

#### 5. Search + Filter + Sort Combine Correctly

**Test:** Type a partial WR number, select a variant chip, and click a column header to sort.
**Expected:** All three constraints apply simultaneously. Results narrow correctly after the 250ms debounce fires. Only one network request fires (not one per constraint).
**Why human:** Requires live data and DevTools network tab to confirm a single combined PostgREST request rather than chained client-side filtering.

---

### Warnings Summary (Non-Blocking)

The following code-review warnings are open but do not block the phase goal:

- **WR-01** (`ArtifactTable.tsx:58`): Sort column `as`-cast lacks runtime guard. Acceptable for Phase 05; `enableSorting: false` on non-sortable columns prevents the bad path in practice.
- **WR-02** (`ArtifactTable.tsx:103`): Infinite-scroll trigger fires at last data row rather than sentinel slot. Functionally correct (loads next page); sentinel semantics are slightly wrong. Cosmetic.
- **WR-03** (`ArtifactTable.tsx:68-76`): Variant-options query fetches all rows without `.limit()`. Bounded by `staleTime`. Acceptable for Phase 05 scale.
- **WR-04** (`ArtifactTable.tsx:121`): `clearFilters` not `useCallback`-wrapped. No active stale-closure bug.
- **WR-05** (`App.tsx:81` + `ArtifactTable.tsx:267`): Duplicate `ToastContainer`. Both functional; visual overlap is a Phase 06 polish concern.
- **WR-06** (`useArtifacts.ts:10`): Stub returns `Artifact[]` not `BillingArtifact[]`. Phase 07 owns deletion.

All six warnings are appropriate candidates for Phase 06 (UI polish) or Phase 07 (Express cleanup), not Phase 05 gap-closure work.

---

_Verified: 2026-06-01T21:00:00-05:00_
_Verifier: Claude (gsd-verifier)_
