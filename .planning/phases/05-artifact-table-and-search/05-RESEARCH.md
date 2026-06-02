# Phase 05: Artifact Table and Search — Research

**Researched:** 2026-06-01
**Domain:** TanStack Table v8 + TanStack Virtual v3 + TanStack Query v5 + supabase-js v2 + Vite/React 18 headless table
**Confidence:** HIGH — all TanStack API shapes verified via Context7; supabase-js API verified via Context7; existing codebase read directly from disk; package versions confirmed via npm registry.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** New Supabase artifact table becomes the primary dashboard view — the post-login landing at `/dashboard` renders it directly. The Express-era runs list is retired from the primary path.
- **D-02:** Remove only the mock path this phase. Delete the silent `[v0]` mock fallback in `useArtifacts.ts` and the mock-coupled `useArtifacts(runId)` path, and stop rendering the legacy run/explorer UI. Leave Express-coupled files physically in the tree for Phase 07 to delete.
- **D-03:** Power the table with TanStack Table v8 (headless table logic), TanStack Virtual (row virtualization), and TanStack Query v5 (server-state: caching, retries, `useInfiniteQuery`). Add them to `portal-v2/package.json` (ESM, React 18 compatible).
- **D-04:** Build the table headless on existing primitives — Tailwind markup + `GlassCard` / `Badge` / `Skeleton` / `Toast` + Linetec brand styling. No pre-built data-grid (MUI DataGrid / AG Grid explicitly rejected).
- **D-05:** Infinite windowed scroll — TanStack Query `useInfiniteQuery` + Supabase `.range()` page fetches, rendered through TanStack Virtual. NOT numbered pages, NOT a "Load more" button.
- **D-06:** Default sort is `week_ending` DESC (newest billing week first). Sort is server-side (`.order()`), combinable with search + variant filter.
- **D-07:** Three tailored loading/empty/error states: Loading → `Skeleton` rows; Empty DB → "No artifacts yet — they'll appear here after the next billing run."; Zero matches → "No results match your search/filters" + Clear filters action; Fetch failure → "Couldn't load artifacts" + Retry action.
- **D-08:** Search input is format-flexible — accept `MMDDYY` (`052625`), `MM/DD/YY` (`05/26/25`), and ISO (`2025-05-26`); normalize before querying against `week_ending_fmt` / `week_ending`.
- **D-09:** Match semantics are case-insensitive substring (`ilike %term%`) on WR # OR week-ending. Filtering/search runs server-side (Postgres), combined with variant filter and sort. Search debounced 250ms. Search scope: WR # + week-ending only.
- **D-10:** Variant multi-select uses human-friendly labels via a known mapping. Available options derived dynamically from distinct `variant` values actually present. Clearable filter chips.

### Claude's Discretion

- Exact download-button in-progress UX (spinner-on-button vs row-level busy state); trigger browser download of single `.xlsx` via click-time signed URL; surface failures through existing `Toast`/`useToast`.
- The redefined `Artifact` TypeScript type in `portal-v2/src/lib/types.ts` to match the `public.artifacts` row shape; whether to keep the old type aliased until Phase 07.
- Fetch window / page size for `useInfiniteQuery` `.range()` (e.g., 50–100/page) and TanStack Virtual overscan tuning.
- The thin `supabase-js` data-access layer / query-key design for TanStack Query.
- Column set/order presentation details within the locked TABLE-01 columns.
- Where TanStack Query's `QueryClientProvider` is mounted in the app tree.

### Deferred Ideas (OUT OF SCOPE)

- Filename search (SEARCH-01 scopes to WR # + week-ending only).
- Deep animation polish, full responsive breakpoints, WCAG-AA accessibility audit (Phase 06).
- Realtime new-artifact toast (DATA-06) — Phase 06.
- Physical deletion of Express-coupled run/explorer components + `mockData.ts` + the Express backend (`portal/`) — Phase 07.
- Excel content preview / in-browser rendering — explicitly out of v1.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TABLE-01 | User sees a table of available artifacts with columns: Work Request #, week-ending date, variant, file size, created date, download action | TanStack Table v8 `useReactTable` + column defs; `BillingArtifact` type maps exactly to these columns |
| TABLE-02 | Table renders REAL Supabase data; silent mock-data fallback removed; genuine fetch failures surface a real error state | Remove `useArtifacts.ts` mock fallback; replace with TanStack Query hook reading `public.artifacts` |
| TABLE-03 | Table is row-virtualized and fetches via server-side filtering + pagination; fast and low-memory regardless of artifact history | TanStack Virtual `useVirtualizer` + `useInfiniteQuery` + Supabase `.range()`; 2,383 rows already live |
| TABLE-04 | User can download an artifact via its signed URL, with a visible in-progress/download state | `supabase.storage.from('excel-artifacts').createSignedUrl(path, 300)` at click time; row-level or button-level busy state |
| TABLE-05 | Table shows distinct, explicit loading, empty, and error states | Four distinct states from D-07; TanStack Query `status` + `isFetchingNextPage` flags |
| SEARCH-01 | Debounced search bar filters the table by Work Request # or week-ending date | Custom `useDebounce(250)` hook + Supabase `.or('work_request.ilike.%t%,week_ending_fmt.ilike.%t%')` |
| SEARCH-02 | User can filter by variant via a multi-select control with clearable filter chips | Supabase `.in('variant', [...])` combined in the query chain; `Badge` chips with clear action |
| SEARCH-03 | User can sort columns (WR #, week-ending, size, created) with clear asc/desc indicators | TanStack Table `manualSorting: true` + Supabase `.order(col, {ascending})` re-query on sort state change |
| SEARCH-04 | Search and filters are dynamic and combine; results satisfy search AND active filters | All of `.or(search)`, `.in(variants)`, `.order(sort)`, `.range(page)` chained on one query builder |

</phase_requirements>

---

## Summary

Phase 05 builds the primary dashboard view: a virtualized, server-filtered, server-sorted, paginated table of Excel billing artifacts backed by the 2,383 real rows already in `public.artifacts` on Supabase project `poeyztlmsawfoqlanucc`. The phase wires TanStack Query v5 `useInfiniteQuery` for server-state management, TanStack Table v8 for headless column/sort logic, and TanStack Virtual v3 `useVirtualizer` for DOM-shallow row rendering — all three are net-new dependencies. The supabase-js query chain (`.or()`, `.in()`, `.order()`, `.range()`) delivers server-side search/filter/sort/pagination from a single combinable builder, and `storage.createSignedUrl` at click-time delivers signed downloads.

The current portal shows mock data because `api.ts` calls the removed Express `/api` which triggers the `TypeError` → mock fallback in `useArtifacts.ts`. The fix is not merely deleting the fallback — it is rewiring the read path to `supabase.from('artifacts')` + TanStack Query. The legacy `DashboardPage` (runs list + `ArtifactPanel` + `ArtifactExplorer`) is replaced entirely as the `/dashboard` index route rendering, with Express-coupled files left physically for Phase 07 deletion.

**Primary recommendation:** Wire `useInfiniteQuery` with a Supabase `.range()`-based `queryFn`, feed all fetched pages through `data.pages.flatMap(p => p.rows)` into a `useVirtualizer` count, and trigger `fetchNextPage` when the last virtual item index is within `overscan` of the total loaded count. Use `manualSorting: true` and reset pages on sort/filter/search changes by including those values in the `queryKey`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Artifact metadata reads | Frontend (supabase-js direct) | Database (RLS) | DATA-04 decision; no Express in path |
| Signed URL generation | Frontend (supabase-js) | Supabase Storage (RLS policy) | Client-side at click-time per DATA-05 |
| Row pagination | Database (Supabase `.range()`) | Frontend (TanStack Query page accumulation) | Server-side pagination keeps memory flat |
| Search/filter/sort | Database (Postgres `.or()`, `.in()`, `.order()`) | Frontend (debounce, query key invalidation) | Filters run in Postgres, not JS; 2,383+ rows |
| Row virtualization | Frontend (TanStack Virtual) | — | DOM-shallow rendering for 500+ row goal |
| Table column/sort state | Frontend (TanStack Table) | — | Headless logic only; no DOM ownership |
| Auth gating | Frontend (AuthGuard + RoleGuard) | Database (RLS) | Defense in depth — UI + DB both gate |
| Download in-progress state | Frontend (component state) | — | Per-row or per-button busy flag |
| Error/empty/loading states | Frontend (TanStack Query status) | — | `status === 'pending'` / `'error'` / `isFetchingNextPage` |
| Variant label mapping | Frontend (static map) | — | Known mapping at D-10; no DB involvement |

---

## Standard Stack

### Net-New Dependencies (add to `portal-v2/package.json`)

| Library | Version (verified) | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| `@tanstack/react-table` | `8.21.3` | Headless table logic: column defs, sort state, row model | D-03 locked; industry standard for headless React tables |
| `@tanstack/react-virtual` | `3.14.1` | Row virtualization: `useVirtualizer`, DOM-shallow rows | D-03 locked; best-in-class headless virtualizer |
| `@tanstack/react-query` | `5.100.14` | Server-state: `useInfiniteQuery`, caching, retries, stale-while-revalidate | D-03 locked; v5 is current stable |

[VERIFIED: npm registry — `npm view @tanstack/react-table version`, `@tanstack/react-virtual`, `@tanstack/react-query`]

### Existing Dependencies Reused (already in `portal-v2/package.json`)

| Library | Version | Reuse Purpose |
|---------|---------|---------------|
| `@supabase/supabase-js` | `^2.45.4` | `supabase.from('artifacts')` queries + `storage.createSignedUrl` |
| `framer-motion` | `^11.11.17` | Tasteful entrance (Phase 06 primary; available for subtle use here) |
| `lucide-react` | `^0.460.0` | Sort indicators, download icon, clear/X icons |
| `tailwind-merge` / `clsx` | current | `cn()` helper for conditional classes |

[VERIFIED: `portal-v2/package.json` read directly]

### Alternatives Considered (locked — do NOT re-open)

| Instead of | Could Use | Why Locked Against |
|------------|-----------|-------------------|
| TanStack Table v8 | MUI DataGrid, AG Grid | Heavy bundle, opinionated styling fights Tailwind/glass; AG Grid enterprise-licensed for best features |
| TanStack Virtual | react-window, react-virtuoso | TanStack Virtual is the same author's recommended upgrade; tighter TanStack Table integration |
| TanStack Query v5 | SWR, Zustand + fetch | v5 `useInfiniteQuery` has `initialPageParam` (required); best-in-class `status` + `isFetchingNextPage` flags |

**Installation:**
```bash
cd portal-v2
npm install @tanstack/react-table @tanstack/react-virtual @tanstack/react-query
```

**Version verification (run before writing lockfile):**
```bash
npm view @tanstack/react-table version    # 8.21.3
npm view @tanstack/react-virtual version  # 3.14.1
npm view @tanstack/react-query version    # 5.100.14
```

---

## Architecture Patterns

### System Architecture Diagram

```
Authenticated user at /dashboard
        │
        ▼
  DashboardPage (NEW — replaces legacy runs layout)
        │
        ├─── ArtifactTablePage (or inline)
        │         │
        │    SearchBar (debounced 250ms)
        │    VariantFilter (multi-select chips)
        │    SortState (column header clicks)
        │         │
        │         ▼
        │    useArtifactsInfinite() ← NEW hook (TanStack Query)
        │         │ queryKey: ['artifacts', search, variants, sortCol, sortDir]
        │         │
        │         ▼
        │    Supabase PostgREST query builder
        │         supabase.from('artifacts')
        │           .select('id,work_request,week_ending,week_ending_fmt,
        │                    variant,filename,storage_path,size_bytes,created_at',
        │                   { count: 'exact' })
        │           .or('work_request.ilike.%t%,week_ending_fmt.ilike.%t%')  ← if search
        │           .in('variant', [...])                                      ← if filter
        │           .order('week_ending', { ascending: false })
        │           .range(from, to)                                           ← pagination
        │         │
        │         ▼
        │    public.artifacts (RLS: admin/billing only)
        │         │
        │         ▼
        │    pages[] → flatMap → allRows[]
        │         │
        │         ▼
        │    useVirtualizer({ count: allRows.length, estimateSize: () => 56 })
        │         │
        │         ▼
        │    Virtual row rendering (absolute-positioned rows in position:relative wrapper)
        │         │
        │    Last virtualItem.index near allRows.length → fetchNextPage()
        │
        │
        ├─── Download click on a row
        │         │
        │         ▼
        │    supabase.storage.from('excel-artifacts')
        │         .createSignedUrl(row.storage_path, 300)
        │         │
        │         ▼
        │    { data: { signedUrl } }  — 5-min TTL signed URL
        │         │
        │         ▼
        │    Trigger browser download (window.open or <a href> click)
        │    Error → addToast('error', 'Could not generate download link')
        │
        └─── QueryClientProvider (mounted in App.tsx, wraps AuthProvider)
```

### Recommended Project Structure (new files only)

```
portal-v2/src/
├── components/
│   └── artifacts/
│       ├── ArtifactTable.tsx       # NEW: headless table shell + virtualizer
│       ├── ArtifactTableRow.tsx    # NEW: memoized row component (React.memo)
│       ├── ArtifactSearchBar.tsx   # NEW: debounced search input
│       ├── VariantFilterBar.tsx    # NEW: multi-select variant chips
│       └── ArtifactEmptyState.tsx  # NEW: empty/error/no-results states
├── hooks/
│   ├── useArtifactsInfinite.ts     # NEW: TanStack Query useInfiniteQuery hook
│   ├── useDownloadArtifact.ts      # NEW: signed URL + browser download + toast
│   └── useDebounce.ts              # NEW: 250ms debounce (tiny, no dep needed)
└── lib/
    └── variantLabels.ts            # NEW: D-10 variant → human-friendly label map
```

Files to modify:
```
portal-v2/src/
├── App.tsx                         # MODIFY: add QueryClientProvider wrap
├── lib/types.ts                    # MODIFY: add BillingArtifact interface
├── hooks/useArtifacts.ts           # MODIFY: gut mock fallback; may become stub
└── components/dashboard/DashboardPage.tsx  # REPLACE body with ArtifactTable
```

### Pattern 1: QueryClientProvider Mount Point

`QueryClientProvider` wraps the entire app in `App.tsx`, outside `AuthProvider` but inside `BrowserRouter`. This ensures all routes and the auth layer can use TanStack Query hooks. Create `QueryClient` once at module scope (not inside the component).

```typescript
// portal-v2/src/App.tsx
// Source: https://tanstack.com/query/v5/docs/react/reference/QueryClientProvider
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,       // 30s — artifact rows don't change mid-session
      retry: 2,                // retry twice on network errors
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const { toasts, removeToast } = useToast();
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <AuthProvider>
            {/* ...routes unchanged... */}
          </AuthProvider>
        </ErrorBoundary>
      </BrowserRouter>
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </QueryClientProvider>
  );
}
```

[VERIFIED: Context7 /tanstack/query — QueryClientProvider reference docs]

### Pattern 2: useInfiniteQuery with Supabase .range() Pagination

The critical v5 difference from v4: `initialPageParam` is **required** (was optional/inferred in v4). Without it, TypeScript errors and runtime failures occur.

```typescript
// portal-v2/src/hooks/useArtifactsInfinite.ts
// Source: https://tanstack.com/query/v5/docs/react/reference/useInfiniteQuery
import { useInfiniteQuery } from '@tanstack/react-query';
import { supabase } from '../lib/supabase';

const PAGE_SIZE = 75; // fetches 75 rows per page; ~30 visible rows per viewport

export interface ArtifactsQueryParams {
  search: string;
  variants: string[];
  sortColumn: 'week_ending' | 'work_request' | 'size_bytes' | 'created_at';
  sortAscending: boolean;
}

export function useArtifactsInfinite(params: ArtifactsQueryParams) {
  return useInfiniteQuery({
    queryKey: ['artifacts', params.search, params.variants, params.sortColumn, params.sortAscending],
    queryFn: async ({ pageParam }) => {
      const from = pageParam * PAGE_SIZE;
      const to = from + PAGE_SIZE - 1;

      let query = supabase
        .from('artifacts')
        .select(
          'id,work_request,week_ending,week_ending_fmt,variant,filename,storage_path,size_bytes,created_at',
          { count: 'exact' }
        );

      // Server-side OR search: WR# OR week-ending (ilike = case-insensitive substring)
      if (params.search.trim()) {
        const term = params.search.trim();
        query = query.or(
          `work_request.ilike.%${term}%,week_ending_fmt.ilike.%${term}%`
        );
      }

      // Server-side variant filter
      if (params.variants.length > 0) {
        query = query.in('variant', params.variants);
      }

      // Server-side sort
      query = query.order(params.sortColumn, { ascending: params.sortAscending });

      // Server-side pagination (range is inclusive: from=0,to=74 returns 75 rows)
      const { data, error, count } = await query.range(from, to);

      if (error) throw error;
      return { rows: data ?? [], count: count ?? 0 };
    },
    initialPageParam: 0,                        // REQUIRED in v5 — not optional
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.flatMap(p => p.rows).length;
      return loaded < (lastPage.count ?? 0) ? allPages.length : undefined;
    },
  });
}
```

**Key v5 facts:**
- `status === 'pending'` (not `'loading'`) is the initial loading state [VERIFIED: Context7 migrating-to-v5]
- `isLoading` in v5 = `isPending && isFetching` (not the same as v4 `isLoading`)
- `isFetchingNextPage` is the flag for "scroll-triggered next page loading"
- All query methods use single-object argument: `queryClient.invalidateQueries({ queryKey: [...] })`

### Pattern 3: TanStack Virtual Row Virtualization

The virtualizer needs: (1) a fixed-height scroll container with `overflow: auto`, (2) a position-relative inner wrapper sized to `getTotalSize()`, (3) absolute-positioned rows using `virtualItem.start` as `translateY`.

```typescript
// portal-v2/src/components/artifacts/ArtifactTable.tsx
// Source: https://tanstack.com/virtual/v3/docs/introduction
import { useVirtualizer } from '@tanstack/react-virtual';
import { useRef, useCallback } from 'react';

function ArtifactTable({ params }: { params: ArtifactsQueryParams }) {
  const { data, status, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useArtifactsInfinite(params);

  const allRows = data?.pages.flatMap(p => p.rows) ?? [];

  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: hasNextPage ? allRows.length + 1 : allRows.length, // +1 for loading sentinel
    getScrollElement: () => parentRef.current,
    estimateSize: () => 56,          // fixed row height; no dynamic measurement needed
    overscan: 5,                     // render 5 rows above/below visible window
  });

  // Trigger next page fetch when approaching the end
  const virtualItems = rowVirtualizer.getVirtualItems();
  const lastItem = virtualItems[virtualItems.length - 1];
  if (lastItem && lastItem.index >= allRows.length - 1 && hasNextPage && !isFetchingNextPage) {
    fetchNextPage();
  }

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualItems.map((virtualRow) => {
          const row = allRows[virtualRow.index];
          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              {row ? <ArtifactTableRow row={row} /> : <SkeletonRow />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

**Critical:** Row component must be wrapped in `React.memo` to prevent full re-renders on scroll. Stable props prevent `memo` bypass.

### Pattern 4: TanStack Table v8 Column Definitions

TanStack Table provides headless sort state management. With `manualSorting: true`, the table does not re-sort accumulated pages in JavaScript — instead, a sort-state change updates the `queryKey` and TanStack Query re-fetches from page 0 with the new `.order()` parameter.

```typescript
// Source: https://tanstack.com/table/v8/docs
import {
  useReactTable,
  getCoreRowModel,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import type { BillingArtifact } from '../../lib/types';

const columns: ColumnDef<BillingArtifact>[] = [
  { accessorKey: 'work_request', header: 'Work Request #', enableSorting: true },
  { accessorKey: 'week_ending', header: 'Week Ending', enableSorting: true },
  { accessorKey: 'variant', header: 'Variant', enableSorting: false },
  { accessorKey: 'size_bytes', header: 'File Size', enableSorting: true },
  { accessorKey: 'created_at', header: 'Created', enableSorting: true },
  { id: 'download', header: 'Download', enableSorting: false },
];

const [sorting, setSorting] = useState<SortingState>([
  { id: 'week_ending', desc: true }, // D-06 default: week_ending DESC
]);

const table = useReactTable({
  data: allRows,
  columns,
  state: { sorting },
  onSortingChange: setSorting,
  getCoreRowModel: getCoreRowModel(),
  manualSorting: true,     // CRITICAL: prevents client-side re-sort of accumulated pages
  manualFiltering: true,   // all filtering is server-side
  manualPagination: true,  // pagination is infinite/server-side
});
```

**When `sorting` state changes:** derive `sortColumn` + `sortAscending` from `sorting[0]` and pass to `useArtifactsInfinite`. The `queryKey` array includes these values, triggering a fresh fetch from page 0 with the new `.order()` applied.

### Pattern 5: Supabase Multi-Column OR Search + .in() Variant Filter

The PostgREST `.or()` method takes a raw filter string. Combining OR search with AND variant filter:

```typescript
// Source: Context7 /supabase/supabase-js — or() method docs
// Both .or() (search) and .in() (variant filter) apply simultaneously (AND semantics between clauses)

let query = supabase.from('artifacts').select('*', { count: 'exact' });

if (search.trim()) {
  // OR: matches work_request OR week_ending_fmt (case-insensitive substring)
  // D-08: normalize before querying — search term may be MMDDYY, MM/DD/YY, or ISO
  const normalized = normalizeSearchTerm(search.trim());
  query = query.or(
    `work_request.ilike.%${normalized}%,week_ending_fmt.ilike.%${normalized}%`
  );
}

if (variants.length > 0) {
  // AND: only rows whose variant is in the selected set
  query = query.in('variant', variants);
}

query = query
  .order('week_ending', { ascending: false })
  .range(from, to);
```

**D-08 date normalization (before querying `week_ending_fmt`):**
```typescript
// portal-v2/src/lib/searchNormalize.ts
export function normalizeSearchTerm(raw: string): string {
  // Strip slashes: '05/26/25' → '052625'
  const noSlashes = raw.replace(/\//g, '');
  // ISO date '2025-05-26' → extract MMDDYY: '052625'
  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const [, , mm, dd] = isoMatch;
    const yy = isoMatch[1].slice(2);
    return `${mm}${dd}${yy}`;
  }
  return noSlashes;
}
```
Then search `week_ending_fmt.ilike.%${normalized}%`. The `work_request` ilike handles WR# substrings naturally.

**IMPORTANT — `.range()` inclusive semantics:** `range(0, 74)` sets `offset=0&limit=75` (to − from + 1). Page N: `from = N * PAGE_SIZE`, `to = from + PAGE_SIZE - 1`. [VERIFIED: Context7 /supabase/supabase-js — range() source code]

**IMPORTANT — `count: 'exact'` is needed for `hasNextPage`:** Include it in `.select()` options. Returns `count` in the response alongside `data`. [VERIFIED: Context7 /supabase/supabase-js — select with count test]

### Pattern 6: createSignedUrl + Browser Download

```typescript
// portal-v2/src/hooks/useDownloadArtifact.ts
import { useState, useCallback } from 'react';
import { supabase } from '../lib/supabase';

const BUCKET = 'excel-artifacts';
const SIGNED_URL_TTL = 300; // 5 minutes (D-10 from Phase 03 contract)

export function useDownloadArtifact() {
  const [downloading, setDownloading] = useState<string | undefined>(undefined); // row id
  const { addToast } = useToast();

  const download = useCallback(async (rowId: string, storagePath: string, filename: string) => {
    setDownloading(rowId);
    try {
      const { data, error } = await supabase.storage
        .from(BUCKET)
        .createSignedUrl(storagePath, SIGNED_URL_TTL);

      if (error || !data?.signedUrl) {
        throw new Error(error?.message ?? 'Failed to generate download link');
      }

      // Trigger browser download: create a temporary <a> and click it
      const a = document.createElement('a');
      a.href = data.signedUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Download failed';
      addToast('error', msg);
    } finally {
      setDownloading(undefined);
    }
  }, [addToast]);

  return { download, downloading };
}
```

[VERIFIED: Context7 /supabase/supabase-js — createSignedUrl API docs; TTL = 300s per Phase 03 D-10 contract]

### Pattern 7: useDebounce Hook (no extra dependency)

The project values "minimize external deps." A tiny `useDebounce` hook is 8 lines and needs no library:

```typescript
// portal-v2/src/hooks/useDebounce.ts
import { useState, useEffect } from 'react';

export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}
```

Usage: `const debouncedSearch = useDebounce(searchInput, 250);` — pass `debouncedSearch` into `useArtifactsInfinite`. [ASSUMED — no library dep needed; standard React pattern]

### Pattern 8: BillingArtifact Type Redefinition

The existing `Artifact` type in `types.ts` is the Express-era GitHub Actions ZIP artifact shape (`size_in_bytes`, `archive_download_url`, `expired`). Phase 05 adds a new `BillingArtifact` interface matching the `public.artifacts` row:

```typescript
// portal-v2/src/lib/types.ts  (ADD — do not delete Artifact until Phase 07)
export interface BillingArtifact {
  id: string;              // uuid
  work_request: string;    // e.g. "90001"
  week_ending: string;     // ISO date string "2026-05-17" (DATE stored as ISO by supabase-js)
  week_ending_fmt: string; // MMDDYY display "051726"
  variant: string;         // '' | 'helper' | 'vac_crew' | '_AEPBillable' | etc.
  filename: string;        // "WR_90001_WeekEnding_051726.xlsx"
  storage_path: string;    // "{week_ending_iso}/{filename}"
  size_bytes: number;
  created_at: string;      // ISO timestamp
}
```

Keep old `Artifact`, `WorkflowRun`, `ArtifactFile` etc. — Phase 07 deletes them.

### Pattern 9: D-10 Variant Label Map

```typescript
// portal-v2/src/lib/variantLabels.ts
export const VARIANT_LABELS: Record<string, string> = {
  '': 'Primary',
  'helper': 'Helper',
  'vac_crew': 'VAC Crew',
  '_AEPBillable': 'AEP Billable (Sub)',
  '_ReducedSub': 'Reduced Sub',
};

export function getVariantLabel(variant: string): string {
  if (variant in VARIANT_LABELS) return VARIANT_LABELS[variant];
  // Combo labels: '_AEPBillable_Helper_<name>' → 'AEP Billable · Helper'
  if (variant.startsWith('_AEPBillable_Helper')) return 'AEP Billable · Helper';
  if (variant.startsWith('_ReducedSub_Helper')) return 'Reduced Sub · Helper';
  // Unknown: de-prefix and humanize
  return variant.replace(/^_/, '').replace(/_/g, ' ');
}
```

Dynamic variant options come from `SELECT DISTINCT variant FROM artifacts` — can be a separate `useQuery` or derived from the first page's data via `Array.from(new Set(allRows.map(r => r.variant)))`.

### Anti-Patterns to Avoid

- **Inline component definitions inside the virtualizer loop:** Define `ArtifactTableRow` as a separate module-level component, not inline inside `getVirtualItems().map(...)`. Inline definitions break `React.memo` because the reference changes every render.
- **Client-side sort on accumulated pages:** Without `manualSorting: true`, TanStack Table will attempt to re-sort all loaded rows in JS, scrambling the server's order between pages. Always keep `manualSorting: true` when using `useInfiniteQuery`.
- **`initialPageParam` omitted in v5:** This is the most common v4 → v5 migration mistake. `useInfiniteQuery` in v5 requires `initialPageParam` explicitly — it has no default. Omitting it causes TypeScript errors and runtime failures.
- **`status === 'loading'`:** v5 renamed this to `'pending'`. Code using `status === 'loading'` will never match.
- **Pre-generating signed URLs at table load:** Never call `createSignedUrl` for every row on mount. It fires N Storage API calls and they expire before the user clicks. Generate only at click time.
- **Fetching all rows without `.range()`:** Without pagination, a single query loads all 2,383+ rows. Memory bloat + slow initial load. Always paginate.
- **`or()` with unsanitized user input:** The `.or()` filter takes raw PostgREST syntax. A `%` or `,` in the search term can break the query. Sanitize: `term.replace(/[%_,()]/g, '')` before interpolating into the filter string.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Server-state caching + retries | Custom fetch + useState | TanStack Query `useInfiniteQuery` | Race conditions, stale closure bugs, deduplication, background refetch — all solved |
| Row virtualization | Manual `IntersectionObserver` DOM slice | TanStack Virtual `useVirtualizer` | Scroll position jumps, measurement loops, overscan — all solved |
| Headless sort state + column model | Custom `sortBy` + `sortDir` state | TanStack Table `useReactTable` | Header click handlers, sort indicator state, column resize — built-in |
| Debounce | Lodash `debounce` or a dep | Tiny `useDebounce` hook (8 lines) | No dependency needed; too small to justify a package |
| Variant label lookup | Regex parsing of raw variant strings | `VARIANT_LABELS` map + `getVariantLabel()` | D-10 mapping is a known, finite set |
| Signed URL trigger | Custom fetch to Express proxy | `supabase.storage.from().createSignedUrl()` direct | No backend needed; Supabase Storage handles it with JWT + RLS |

---

## Common Pitfalls

### Pitfall 1: `initialPageParam` Missing (v5 Breaking Change)
**What goes wrong:** TypeScript error: "Property 'initialPageParam' is missing in type..." and runtime: `pageParam` is `undefined` on first fetch, causing `from = NaN`.
**Why it happens:** v4 inferred `initialPageParam: 0` from `getNextPageParam`. v5 requires it explicitly.
**How to avoid:** Always include `initialPageParam: 0` in every `useInfiniteQuery` call.
**Warning signs:** `from = NaN` in the Supabase query URL; TypeScript errors on `useInfiniteQuery`.

### Pitfall 2: `manualSorting: true` Omitted from `useReactTable`
**What goes wrong:** After the first sort click, TanStack Table re-sorts ALL accumulated pages client-side in JS, scrambling the server's `week_ending DESC` order between pages. Rows from page 3 intermix with page 1 rows.
**Why it happens:** `manualSorting` defaults to `false` — the table assumes it owns sorting.
**How to avoid:** Always set `manualSorting: true`, `manualFiltering: true`, `manualPagination: true` when the server owns all of these.
**Warning signs:** After sorting, earlier pages appear out of order; rows jump on scroll.

### Pitfall 3: Virtualized Rows with Unstable Keys or Inline Component Definitions
**What goes wrong:** Using `virtualItem.index` as React `key` causes remounts during sort/filter. Inline row components (defined inside `getVirtualItems().map(...)`) break `React.memo` — the prop reference changes every render, causing all visible rows to re-render on any state change.
**Why it happens:** Developer writes the loop body inline for convenience.
**How to avoid:** Use `virtualItem.key` (the virtualizer's stable key) for the outer `div`. Use `row.id` (Postgres UUID) as the React key for the row component. Extract `ArtifactTableRow` as a module-level `React.memo` component.
**Warning signs:** React DevTools Profiler shows all visible rows highlighted on every scroll/search.

### Pitfall 4: `.or()` Filter String Not Sanitized
**What goes wrong:** A search term containing `%` (e.g., "100%") or commas becomes malformed PostgREST syntax, causing a 400 error or unintended filter broadening.
**Why it happens:** `.or()` takes raw PostgREST syntax strings — there is no automatic escaping.
**How to avoid:** Sanitize user input before interpolating: `term.replace(/[,()]/g, '').trim()`. The `%` sign inside ilike patterns is the wildcard, so strip any literal `%` the user types: `term.replace(/%/g, '')`.
**Warning signs:** 400 errors from Supabase when typing certain characters; `search.includes('%')` in the filter string.

### Pitfall 5: Scroll Container Without Explicit Height Breaks Virtualization
**What goes wrong:** TanStack Virtual requires the scroll container (`parentRef`) to have a fixed or constrained height with `overflow: auto`. If the container grows to fit all content (e.g., `height: auto`), every row renders — virtualization is defeated.
**Why it happens:** Tailwind's default container behavior is `height: auto`. Developers apply Tailwind classes without setting a pixel/viewport height.
**How to avoid:** Set the scroll container to a constrained height: `style={{ height: 'calc(100vh - 240px)', overflow: 'auto' }}` or a fixed `600px`. `max-h-[calc(100vh-240px)]` with `overflow-auto` in Tailwind works.
**Warning signs:** All 2,383 rows render in the DOM simultaneously; Chrome Memory tab shows 200+ MB.

### Pitfall 6: `fetchNextPage` Called Inside the Render Body Without Guards
**What goes wrong:** If `fetchNextPage` is called synchronously inside the render function (not in a `useEffect` or event handler), it re-triggers on every render, causing infinite fetch loops.
**Why it happens:** Scroll-trigger logic is written inline in the render body: `if (near end) fetchNextPage()`.
**How to avoid:** Check `!isFetchingNextPage` AND `hasNextPage` before calling. Use a `useEffect` or call from the virtualizer's scroll event — but a guard-checked inline call in render body works IF the guards are correct (React's render is pure; calling `fetchNextPage` is a side effect that TanStack Query deduplicates internally when already fetching).
**Warning signs:** Network tab shows the same page being fetched repeatedly; `isFetchingNextPage` flickers.

### Pitfall 7: `useToast` Called Inside `useDownloadArtifact` But Toast State Lives in `App.tsx`
**What goes wrong:** `useToast` in the project returns its own independent `toasts` state. If `useDownloadArtifact` creates its own `useToast()` instance, the toasts it adds are on a different state atom than the `ToastContainer` in `App.tsx`, so they never render.
**Why it happens:** `useToast` is not context-backed — it's a plain hook returning local state. Each call creates an independent instance.
**How to avoid:** Thread `addToast` down as a prop to `useDownloadArtifact`, or lift `useToast()` to the `ArtifactTable` component and pass `addToast` into the download hook. See existing pattern: `App.tsx` calls `useToast()` and passes `toasts`/`removeToast` directly to `ToastContainer`.
**Warning signs:** Download errors produce no visible toast; `useToast` appears in multiple places in the tree.

### Pitfall 8: `week_ending` Column Displays Raw ISO Date String
**What goes wrong:** `public.artifacts.week_ending` is a Postgres DATE stored as ISO (`2026-05-17`). supabase-js returns it as the string `"2026-05-17"`. Displaying it raw is unpolished; the team uses MMDDYY format mentally.
**How to avoid:** Use `week_ending_fmt` (TEXT, MMDDYY) for display in the table cell. Use the ISO `week_ending` for sort comparisons (Postgres handles this correctly via DATE index). Display as `row.week_ending_fmt` formatted with slashes: `'052625' → '05/26/25'` or via `formatDate(row.week_ending)`.
**Warning signs:** Table shows "2026-05-17" in the week-ending column instead of a human-readable date.

---

## Code Examples

### Complete Supabase query chain (all combinable)

```typescript
// Source: Context7 /supabase/supabase-js — range(), ilike(), or(), in(), order(), count
const PAGE_SIZE = 75;
const from = pageParam * PAGE_SIZE;
const to = from + PAGE_SIZE - 1;

const { data, error, count } = await supabase
  .from('artifacts')
  .select(
    'id,work_request,week_ending,week_ending_fmt,variant,filename,storage_path,size_bytes,created_at',
    { count: 'exact' }
  )
  .or(`work_request.ilike.%${normalizedSearch}%,week_ending_fmt.ilike.%${normalizedSearch}%`)
  .in('variant', selectedVariants)         // omit entirely if selectedVariants.length === 0
  .order('week_ending', { ascending: false })
  .range(from, to);
```

### TanStack Query status flags for the four states (D-07)

```typescript
// Source: Context7 /tanstack/query — status, isPending, isFetchingNextPage docs
const { status, data, error, fetchNextPage, hasNextPage, isFetchingNextPage, refetch } =
  useArtifactsInfinite(params);

const allRows = data?.pages.flatMap(p => p.rows) ?? [];
const totalCount = data?.pages[0]?.count ?? 0;

// State 1: Initial loading
if (status === 'pending') return <SkeletonRows />;

// State 2: Fetch failure
if (status === 'error') return <ErrorState error={error} onRetry={() => refetch()} />;

// State 3: Empty DB (no search/filter active, 0 total rows)
if (allRows.length === 0 && !params.search && params.variants.length === 0) {
  return <EmptyDB />;
}

// State 4: Zero matches (search/filter active, 0 results)
if (allRows.length === 0) {
  return <NoResults onClear={clearFilters} />;
}

// Success: render table
```

### Trigger next page on scroll-end approach

```typescript
// Inside ArtifactTable render — called each render; guarded to prevent re-trigger
const virtualItems = rowVirtualizer.getVirtualItems();
const lastItem = virtualItems[virtualItems.length - 1];
if (
  lastItem &&
  lastItem.index >= allRows.length - 1 &&
  hasNextPage &&
  !isFetchingNextPage
) {
  void fetchNextPage(); // fire-and-forget; TanStack Query deduplicates concurrent calls
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `status: 'loading'` | `status: 'pending'` | TanStack Query v5 (2023) | Code using `=== 'loading'` never matches in v5 |
| `isLoading` = initial load | `isPending` = initial load; `isLoading` = `isPending && isFetching` | TanStack Query v5 | Different meaning; use `isPending` for skeleton state |
| `initialPageParam` optional | `initialPageParam` REQUIRED | TanStack Query v5 | TypeScript error + runtime NaN without it |
| `queryClient.isFetching(key, filters)` | `queryClient.isFetching({ queryKey, ...filters })` | TanStack Query v5 | All client methods use single-object argument |
| react-window / react-virtualized | TanStack Virtual (`@tanstack/react-virtual`) | 2022+ | TanStack Virtual is the recommended modern replacement |
| Express proxy for artifact downloads | Direct `supabase.storage.createSignedUrl()` | Phase 03 decision | No server needed; RLS + JWT controls access |

**Deprecated/outdated patterns in this codebase:**
- `useArtifacts(runId)` — runId-coupled hook reading Express `/api/artifacts`; this hook is gutted/replaced in Phase 05
- `api.getArtifacts(runId)` in `api.ts` — Express call; no longer needed for the artifact table
- Express-era `Artifact` type in `types.ts` — superseded by `BillingArtifact`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A tiny `useDebounce` hook (8 lines) needs no library dep | Don't Hand-Roll / Pattern 7 | Negligible — the hook is trivial to implement correctly |
| A2 | PAGE_SIZE = 75 rows balances fetch count vs memory | Pattern 2 | Tunable at runtime; change without re-architecture |
| A3 | Scroll container height `calc(100vh - 240px)` fits the layout | Pattern 3 | Easy to adjust in CSS; no logic dependency |
| A4 | Variant `''` (empty string) represents "Primary" | Pattern 9 / D-10 | If the DB actually stores `'primary'`, the label map key needs updating — verify against a live `public.artifacts` row |
| A5 | `useToast` is not context-backed (each call creates independent state) | Pitfall 7 | If Phase 04 added context-backed toast, this pitfall doesn't apply — verify `useToast.ts` (read: it's a plain hook, confirmed) |
| A6 | `QueryClientProvider` wrapped outside `AuthProvider` in `App.tsx` is the correct mount point | Pattern 1 | Could go inside; outside is conventional and avoids re-creating the client on auth state changes |

---

## Open Questions

1. **Distinct variant fetch for filter options (SEARCH-04)**
   - What we know: D-10 says options are derived dynamically from distinct values actually present
   - What's unclear: Is a separate `SELECT DISTINCT variant` query needed, or can we derive from accumulated page data?
   - Recommendation: Derive from first-page data initially (`Array.from(new Set(allRows.map(r => r.variant)))`). Add a dedicated `useQuery(['artifact-variants'])` only if users need to see variants that aren't in the current search/filter result set. The second approach is more complete for SEARCH-04 compliance.

2. **Scroll container height and `DashboardLayout` constraints**
   - What we know: `DashboardPage` currently uses `p-6 lg:p-8 space-y-6 max-w-6xl mx-auto`
   - What's unclear: The exact available height after header and padding to set the virtualizer scroll container
   - Recommendation: Use `h-[calc(100vh-theme(spacing.40))]` (Tailwind JIT) or a `flex-1 min-h-0` pattern so the table fills the available space. Inspect in dev, not a planning blocker.

3. **ToastContainer location in `App.tsx` vs thread-through**
   - What we know: `App.tsx` calls `useToast()` at the top level and renders `<ToastContainer>`. The download hook needs `addToast`.
   - What's unclear: Whether to thread `addToast` as a prop, use a context, or call `useToast()` at the `ArtifactTable` level and pass the same state to both the table and the container.
   - Recommendation: For Phase 05, hoist `useToast()` to a context (a simple `ToastContext`) or thread `addToast` down from `DashboardPage`. Threading is simpler for a single phase; context is more scalable. Either works.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js / npm | Installing TanStack packages | ✓ | (project is active) | — |
| `@supabase/supabase-js` | Artifact reads + signed URLs | ✓ (in package.json) | `^2.45.4` | — |
| Supabase project `poeyztlmsawfoqlanucc` | Live artifact data | ✓ | 2,383 rows as of 2026-06-01 | — |
| `excel-artifacts` Storage bucket | Signed URL downloads | ✓ (Phase 03 complete) | private | — |
| Storage SELECT RLS policy | `createSignedUrl` authorization | ✓ (Phase 03 applied) | admin/billing | — |
| `@tanstack/react-table` | TABLE-01, SEARCH-03 | ✗ (not yet installed) | 8.21.3 (net-new) | None — install required |
| `@tanstack/react-virtual` | TABLE-03 | ✗ (not yet installed) | 3.14.1 (net-new) | None — install required |
| `@tanstack/react-query` | TABLE-02, TABLE-03, SEARCH-04 | ✗ (not yet installed) | 5.100.14 (net-new) | None — install required |

**Missing dependencies with no fallback:**
- All three TanStack packages must be installed in Wave 0 before any component work begins

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 2.1.9 + @testing-library/react 16.3.2 |
| Config file | `portal-v2/vite.config.ts` (Vitest configured via Vite) |
| Quick run command | `cd portal-v2 && npm test` |
| Full suite command | `cd portal-v2 && npm test -- --coverage` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TABLE-01 | `BillingArtifact` type has correct shape (id, work_request, week_ending, etc.) | unit (type test) | `npm test -- src/lib/__tests__/types.test.ts` | ❌ Wave 0 |
| TABLE-02 | `useArtifacts.ts` has no reference to `MOCK_ARTIFACTS` outside explicit mock gate | unit (import check) | `npm test -- src/hooks/__tests__/useArtifacts.test.ts` | ❌ Wave 0 |
| TABLE-03 | `useArtifactsInfinite` calls `supabase.from('artifacts').range(0, N-1)` on first mount | unit (mock supabase) | `npm test -- src/hooks/__tests__/useArtifactsInfinite.test.ts` | ❌ Wave 0 |
| TABLE-04 | `useDownloadArtifact.download()` calls `createSignedUrl` and triggers download; on error shows toast | unit (mock supabase) | `npm test -- src/hooks/__tests__/useDownloadArtifact.test.ts` | ❌ Wave 0 |
| TABLE-05 | ArtifactTable renders Skeleton when `status === 'pending'`; error state when `status === 'error'`; empty state when 0 rows | unit (RTL) | `npm test -- src/components/artifacts/__tests__/ArtifactTable.test.tsx` | ❌ Wave 0 |
| SEARCH-01 | `useDebounce(value, 250)` does not emit until 250ms after last change | unit | `npm test -- src/hooks/__tests__/useDebounce.test.ts` | ❌ Wave 0 |
| SEARCH-02 | `getVariantLabel('')` returns `'Primary'`; unknown variants return de-prefixed form | unit | `npm test -- src/lib/__tests__/variantLabels.test.ts` | ❌ Wave 0 |
| SEARCH-03 | `manualSorting: true` is set in `useReactTable` config (TypeScript compile check) | type | build (`tsc -b`) | — |
| SEARCH-04 | `normalizeSearchTerm('05/26/25')` returns `'052625'`; `normalizeSearchTerm('2025-05-26')` returns `'052625'` | unit | `npm test -- src/lib/__tests__/searchNormalize.test.ts` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd portal-v2 && npm test`
- **Per wave merge:** `cd portal-v2 && npm test -- --coverage && npm run lint && npm run build`
- **Phase gate:** Full suite green + `npm run build` passes before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `portal-v2/src/lib/__tests__/types.test.ts` — add `BillingArtifact` contract assertions (file exists; add new `describe` block)
- [ ] `portal-v2/src/hooks/__tests__/useArtifacts.test.ts` — assert no mock fallback; currently no test
- [ ] `portal-v2/src/hooks/__tests__/useArtifactsInfinite.test.ts` — new file; mock `supabase.from`
- [ ] `portal-v2/src/hooks/__tests__/useDownloadArtifact.test.ts` — new file; mock storage API
- [ ] `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx` — new file; RTL render states
- [ ] `portal-v2/src/hooks/__tests__/useDebounce.test.ts` — new file; vi.useFakeTimers pattern
- [ ] `portal-v2/src/lib/__tests__/variantLabels.test.ts` — new file; mapping assertions
- [ ] `portal-v2/src/lib/__tests__/searchNormalize.test.ts` — new file; D-08 format normalization
- [ ] Install: `npm install @tanstack/react-table @tanstack/react-virtual @tanstack/react-query` in Wave 0

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (gate) | `AuthGuard` + `useAuth` from Phase 04; `getUser()` for server-verified session |
| V3 Session Management | yes (inherited) | Phase 04 supabase-js session; `setSessionStorage` based on "Remember me" |
| V4 Access Control | yes | `RoleGuard` UI gate + Supabase RLS (`current_user_role() IN ('admin','billing')`) |
| V5 Input Validation | yes | Search term sanitized before `.or()` interpolation; no user-controlled SQL |
| V6 Cryptography | partial | Signed URLs use Supabase-managed HMAC signing; 300s TTL per Phase 03 D-10 |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unsanitized search term in `.or()` PostgREST filter | Tampering | Strip `,()%` from user input before interpolating |
| Signed URL generated at page load (pre-generated) | Information Disclosure | Always generate at click-time only; never store signed URLs |
| RLS bypass via `pending` role | Elevation of Privilege | Phase 03 policy: `current_user_role() IN ('admin','billing')` — not `USING(true)` |
| `service_role` key in frontend bundle | Information Disclosure | Never `VITE_SUPABASE_SERVICE_ROLE_KEY` — client uses anon key only |

---

## Sources

### Primary (HIGH confidence)

- Context7 `/tanstack/query` — `useInfiniteQuery` v5 API, `initialPageParam`, `getNextPageParam`, `QueryClientProvider`, migrating-to-v5 breaking changes [VERIFIED]
- Context7 `/tanstack/virtual` — `useVirtualizer`, `estimateSize`, `overscan`, `getTotalSize`, `getVirtualItems`, `VirtualItem` shape [VERIFIED]
- Context7 `/tanstack/table` — `useReactTable`, `manualSorting`, infinite scroll + `useInfiniteQuery` integration pattern [VERIFIED]
- Context7 `/supabase/supabase-js` — `createSignedUrl`, `.range()` inclusive semantics, `.or()` PostgREST syntax, `.ilike()` method, `count: 'exact'` [VERIFIED]
- `portal-v2/package.json` — current dependency set; no TanStack packages present [VERIFIED: file read]
- `portal-v2/src/App.tsx` — current app tree; `QueryClientProvider` mount point identified [VERIFIED: file read]
- `portal-v2/src/hooks/useAuth.ts` — `role`, `isAdmin`, `isBilling` shape confirmed [VERIFIED: file read]
- `portal-v2/src/hooks/useToast.ts` — plain hook, not context-backed; Pitfall 7 confirmed [VERIFIED: file read]
- `portal-v2/src/hooks/useArtifacts.ts` — mock fallback code confirmed at lines 28–35 [VERIFIED: file read]
- `portal-v2/src/lib/types.ts` — Express-era `Artifact` type confirmed; `BillingArtifact` not yet defined [VERIFIED: file read]
- `portal-v2/src/lib/supabase.ts` — fail-loud client confirmed; `isSupabaseConfigured` guard present [VERIFIED: file read]
- `portal-v2/src/lib/utils.ts` — `formatSize`, `formatDate`, `cn` confirmed available [VERIFIED: file read]
- `portal-v2/src/components/ui/` — `GlassCard`, `Badge`, `Skeleton`, `ToastContainer` shapes confirmed [VERIFIED: files read]
- `supabase/portal_schema.sql` — exact `public.artifacts` DDL, RLS policies, `storage.objects` SELECT policy [VERIFIED: file read]
- `.planning/STATE.md` — live topology: 2,383 rows in `public.artifacts` on project `poeyztlmsawfoqlanucc` as of 2026-06-01 [VERIFIED: file read]
- npm registry — `@tanstack/react-table@8.21.3`, `@tanstack/react-virtual@3.14.1`, `@tanstack/react-query@5.100.14` [VERIFIED: `npm view`]

### Secondary (MEDIUM confidence)

- `.planning/research/ARCHITECTURE.md` — signed URL design, component boundary map, Pitfall 10 (virtualization) [CITED: planning file]
- `.planning/research/PITFALLS.md` — Pitfall 5 (mock fallback), Pitfall 10 (virtualization), Pitfall 4 (signed URL), Pitfall 3 (RLS USING true) [CITED: planning file]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all package versions verified via npm registry; API shapes verified via Context7
- Architecture: HIGH — existing code read directly; Supabase schema confirmed; query chain verified against supabase-js source
- Pitfalls: HIGH — most sourced from existing `PITFALLS.md` (grounded in live code) + Context7-verified v5 breaking changes
- Test map: MEDIUM — Vitest infrastructure confirmed present; test file gaps identified; specific test shapes are ASSUMED patterns

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (TanStack packages move quickly; re-verify versions before install)
