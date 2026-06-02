---
phase: 05-artifact-table-and-search
reviewed: 2026-06-01T20:51:00-05:00
depth: standard
files_reviewed: 14
files_reviewed_list:
  - portal-v2/src/App.tsx
  - portal-v2/src/lib/types.ts
  - portal-v2/src/lib/searchNormalize.ts
  - portal-v2/src/lib/variantLabels.ts
  - portal-v2/src/hooks/useDebounce.ts
  - portal-v2/src/hooks/useArtifactsInfinite.ts
  - portal-v2/src/hooks/useDownloadArtifact.ts
  - portal-v2/src/hooks/useArtifacts.ts
  - portal-v2/src/components/artifacts/ArtifactTable.tsx
  - portal-v2/src/components/artifacts/ArtifactTableRow.tsx
  - portal-v2/src/components/artifacts/ArtifactEmptyState.tsx
  - portal-v2/src/components/artifacts/ArtifactSearchBar.tsx
  - portal-v2/src/components/artifacts/VariantFilterBar.tsx
  - portal-v2/src/components/dashboard/DashboardPage.tsx
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-06-01T20:51:00-05:00
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

The phase delivers a virtualized artifact table wired to Supabase, with debounced search, variant filtering, and server-side sort. The overall structure is sound: signed-URL TTL, no service_role key in frontend code, TanStack Query v5 API used correctly (`'pending'` not `'loading'`, `initialPageParam` present), and `React.memo` placed at module level per the pattern requirement.

Two blockers were found. The most serious is that `fetchNextPage` is called unconditionally during the render phase of `ArtifactTable` — this triggers React's "cannot update a component while rendering a different component" warning in dev and causes repeated, unguarded re-renders in production (a side-effect-during-render bug). The second blocker is an incomplete sanitization in `searchNormalize.ts`: the single-quote character is not stripped before interpolation into `.or()`, allowing a malformed PostgREST filter string that will produce a 400 error (or a subtle parse quirk) when a user types a name with an apostrophe.

Six warnings cover: the sort column coercion bypassing TypeScript's type guard, a missing sentinel row in the virtualizer count that means the load-more trigger fires only when the *last real data row* is visible rather than a dedicated loader, the variant-options query fetching every row from the table rather than using `distinct`, a stale-closure risk on `clearFilters` inside `renderBody`, a `ToastContainer` duplicate that renders two independent toast stacks, and the `useArtifacts` stub returning the legacy `Artifact` type (not `BillingArtifact`), which means any future caller that uses the return value will silently get the wrong shape.

---

## Critical Issues

### CR-01: `fetchNextPage` Called During Render Phase (Side Effect During Render)

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:102-111`

**Issue:** The infinite-scroll trigger runs inline in the component body — between hook calls and the `return` statement — not inside a `useEffect`. React prohibits side effects (state updates that cause re-renders of *other* components, or mutations that change observable behaviour) during the render phase. Calling `fetchNextPage()` here causes TanStack Query to update its own internal state synchronously during `ArtifactTable`'s render, which triggers React's warning:

> Warning: Cannot update a component (`QueryClientProvider`) while rendering a different component (`ArtifactTable`).

In StrictMode (default in Vite + React 18 dev) the component renders twice, so `fetchNextPage` is called twice per scroll event, making the fetch fire on the first render of a page rather than only when the scroll threshold is crossed. The existing `!q.isFetchingNextPage` guard prevents duplicate network requests but does not prevent the React invariant violation.

**Fix:** Move the scroll-trigger into a `useEffect` with `virtualItems`, `allRows.length`, `q.hasNextPage`, and `q.isFetchingNextPage` as dependencies.

```tsx
// Replace lines 101-111 with:
useEffect(() => {
  const lastItem = virtualItems[virtualItems.length - 1];
  if (
    lastItem &&
    lastItem.index >= allRows.length - 1 &&
    q.hasNextPage &&
    !q.isFetchingNextPage
  ) {
    void q.fetchNextPage();
  }
}, [virtualItems, allRows.length, q.hasNextPage, q.isFetchingNextPage, q.fetchNextPage]);
```

---

### CR-02: Single-Quote Not Stripped — PostgREST `.or()` Filter Injection

**File:** `portal-v2/src/lib/searchNormalize.ts:19-21`

**Issue:** `sanitizeSearchTerm` strips `,`, `(`, `)`, and `%` but does not strip the single-quote (`'`) character. PostgREST `.or()` syntax is a raw filter string; a single-quote inside the interpolated `ilike` value terminates the string literal and produces a malformed filter:

```
work_request.ilike.%O'Brien%,week_ending_fmt.ilike.%O'Brien%
```

PostgREST will either return a 400 error or silently mis-parse the filter. This is not a SQL injection risk (supabase-js parameterizes the final SQL), but it is a correctness issue that causes visible query failures for any WR# or name containing an apostrophe, and it contradicts the stated purpose of the sanitizer ("strip chars that break the filter string").

The `ilike` wildcard character `_` (matches any single character) is also not neutralized, so a user typing `_` gets an unintended wildcard match — a minor correctness defect but the apostrophe case is the blocker.

**Fix:**

```typescript
export function sanitizeSearchTerm(raw: string): string {
  // Strip chars that break PostgREST .or() filter syntax.
  // Single-quote terminates the ilike literal; _ is an unintended wildcard.
  return raw.replace(/[,()%'_]/g, '').trim();
}
```

If `_` must be preserved for WR-number search (e.g. `WR_123`), escape it instead of stripping:

```typescript
export function sanitizeSearchTerm(raw: string): string {
  return raw.replace(/[,()%']/g, '').trim();
}
```

The single-quote strip is the minimum required fix.

---

## Warnings

### WR-01: Sort Column Cast Bypasses Type Guard — Silent Bad Query Possible

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:57-58`

**Issue:** The sort column is derived with an unchecked `as` cast:

```ts
sortColumn: sort.id as ArtifactsQueryParams['sortColumn'],
```

`sort.id` is a `string` (TanStack Table's `SortingState` uses `string` for `id`). If the user somehow triggers a sort on the `'variant'` or `'download'` column (both have `enableSorting: false`, but that is a UI hint, not a runtime guard), or if a future refactor adds a new column without updating `SORTABLE_IDS`, the cast silently passes an invalid column name to `useArtifactsInfinite`, which then calls `.order()` with an unrecognized column — Supabase returns a 400.

The `SORTABLE_IDS` set exists but is only consulted in the header-click handler for the cursor style; it is not used to validate the `params` object.

**Fix:** Add a runtime guard before building `params`:

```ts
const rawId = sort.id;
const validSortColumn: ArtifactsQueryParams['sortColumn'] = SORTABLE_IDS.has(
  rawId as ArtifactsQueryParams['sortColumn']
)
  ? (rawId as ArtifactsQueryParams['sortColumn'])
  : 'week_ending';

const params: ArtifactsQueryParams = {
  search: debouncedSearch,
  variants,
  sortColumn: validSortColumn,
  sortAscending: !sort.desc,
};
```

---

### WR-02: Virtualizer Sentinel Row Logic — Load-More Fires Only at Last Data Row, Not at Lookahead

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:95, 102-111`

**Issue:** The virtualizer `count` is set to `allRows.length + 1` when `q.hasNextPage` is true (adding a sentinel slot), but the trigger condition checks `lastItem.index >= allRows.length - 1` — that is, it fires when the last *data* row is visible, which is one position *before* the sentinel. This means the load-more never fires at the sentinel skeleton; it fires when the last real row scrolls into view, which is fine but loses the intended visual affordance. More importantly, if `q.hasNextPage` is false but `lastItem.index` equals `allRows.length - 1` (last data row visible, no next page), the condition short-circuits on `q.hasNextPage` correctly — so this is not a fetch loop bug, but it is the wrong semantics for the sentinel pattern.

The canonical pattern is: fire `fetchNextPage` when `lastItem.index >= allRows.length` (i.e., the sentinel slot itself is visible).

**Fix:**

```ts
// In the useEffect from CR-01 fix:
if (
  lastItem &&
  lastItem.index >= allRows.length &&   // sentinel index, not last data row
  q.hasNextPage &&
  !q.isFetchingNextPage
) {
  void q.fetchNextPage();
}
```

---

### WR-03: Variant Options Query Fetches All Columns / All Rows Without Distinct

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:68-76`

**Issue:** The variant-options query does:

```ts
supabase.from('artifacts').select('variant')
```

This fetches the `variant` column for *every row* in the table, then deduplicates in JavaScript with `new Set(...)`. With hundreds or thousands of artifacts this sends a large payload over the wire to compute a result that has at most a handful of distinct values. PostgREST supports `select('variant')` with a `.limit()` or a Postgres distinct query (`select('variant', { count: 'exact', head: false })` plus a Postgres function), but the simplest fix is to add a reasonable row cap, or use a Supabase RPC/view that returns distinct variants.

There is also no `staleTime` or `gcTime` override on this query; it will refetch every time the component remounts (because the global `staleTime: 30_000` from `App.tsx` does apply — so this is bounded, but a dedicated long `staleTime` is more appropriate for data that changes only when new artifact types are introduced).

**Fix (minimal):**

```ts
queryFn: async () => {
  // PostgREST does not support DISTINCT directly; fetch with a high limit
  // and deduplicate. A Supabase RPC returning distinct variants is the
  // long-term solution.
  const { data, error } = await supabase
    .from('artifacts')
    .select('variant')
    .limit(2000);     // cap the wire payload
  if (error) throw error;
  return Array.from(new Set((data ?? []).map((r: { variant: string }) => r.variant)));
},
staleTime: 10 * 60 * 1000, // variant list changes rarely — 10 min
```

---

### WR-04: `clearFilters` Inside `renderBody` — Stale Closure Risk

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:114-117, 120`

**Issue:** `clearFilters` is defined as a plain arrow function inside the component body (not wrapped in `useCallback`) and is passed down to `<NoResultsState onClear={clearFilters} />` from inside `renderBody()`, which is itself called in the JSX. `renderBody` is re-created on every render because it is a plain function defined inline. Because `clearFilters` closes over `setSearchInput` and `setVariants` (stable refs from `useState`), there is no stale-closure *bug* today — but if either setter ever became unstable (e.g. a future refactor wraps state in a reducer), it would silently break.

More concretely, `renderBody` is a non-memoized function defined inside the render scope and called directly as `{renderBody()}`. This is equivalent to inlining the JSX but makes the four-state logic invisible to React's reconciler — React sees the returned JSX nodes, not `renderBody` as a child component, so it cannot short-circuit rendering of the body independently. This is the project's own pattern from `UsersPage.tsx` (acceptable) but pairs poorly with the virtualizer, which already re-renders on scroll.

**Fix:** Either wrap `clearFilters` in `useCallback`, or extract `renderBody` into a named sub-component receiving `onClear` as a prop. The `useCallback` path is minimal:

```ts
const clearFilters = useCallback(() => {
  setSearchInput('');
  setVariants([]);
}, []);
```

---

### WR-05: Duplicate `ToastContainer` — Two Independent Toast Stacks

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:259` and `portal-v2/src/App.tsx:81`

**Issue:** `ArtifactTable` instantiates its own `useToast()` and renders a `<ToastContainer>` at line 259. `App.tsx` also renders a `<ToastContainer>` at line 81, backed by a *separate* `useToast()` instance. These are two independent stacks — each maintains its own `toasts` array in component state. The download-error toast from `useDownloadArtifact` will appear in `ArtifactTable`'s local container; auth toasts from the login/auth flow will appear in App's container. Depending on CSS stacking context and portal placement, both containers may overlap or the local one may be visually buried under the layout.

This is the "Pitfall 7" the comment references, but the solution chosen (hoisting `useToast` inside `ArtifactTable` and co-locating the container) creates a *second* container rather than reusing the app-level one. The correct fix for Pitfall 7 is a shared context, not two containers.

**Fix:** Lift `useToast` into a React context provider (or use a toast library like `sonner`/`react-hot-toast` that manages its own singleton). The `ArtifactTable` component should call `useToast()` from that shared context and not render its own `<ToastContainer>`.

If refactoring to context is out of scope for this phase, remove the `<ToastContainer>` from `ArtifactTable` and pass `addToast` in from a prop or context from `DashboardPage`, which already sits inside `App`'s `<ToastContainer>` scope.

---

### WR-06: `useArtifacts` Stub Returns Legacy `Artifact` Type, Not `BillingArtifact`

**File:** `portal-v2/src/hooks/useArtifacts.ts:10-16`

**Issue:** The stub still imports and returns the old `Artifact` interface (GitHub Actions artifact shape — `archive_download_url`, `expired`, etc.), not `BillingArtifact` (the Supabase row shape). The comment states the file will be cleaned up in Phase 07. If any code path between now and Phase 07 accidentally imports `useArtifacts` expecting `BillingArtifact` rows, TypeScript will accept it (because the stub returns an empty array that satisfies any typed consumer at runtime) but then fail at runtime when actual rows arrive with the wrong shape.

This is a latent type-safety gap, not an active bug, but it is the wrong type for the stub's stated purpose and should be corrected before the stub is widened further.

**Fix:** Change the return type to use `BillingArtifact` or return `never[]` to make misuse a compile error:

```ts
import type { BillingArtifact } from '../lib/types';

export function useArtifacts(
  _runId: number | null
): { artifacts: BillingArtifact[]; loading: boolean; error: undefined } {
  return { artifacts: [], loading: false, error: undefined };
}
```

---

## Info

### IN-01: `normalizeSearchTerm` Order-of-Operations — Sanitize Before Normalize

**File:** `portal-v2/src/hooks/useArtifactsInfinite.ts:44`

**Issue:** The call site does `normalizeSearchTerm(sanitizeSearchTerm(raw))` — sanitize first, then normalize. The comment correctly notes this. However, `sanitizeSearchTerm` strips `%` and parens, and `normalizeSearchTerm` regex-matches an ISO date. If the raw input somehow contains sanitizable chars inside a date string (unlikely but possible with copy-paste), the ISO regex `^\d{4}-\d{2}-\d{2}$` will still match because none of the stripped chars appear in ISO dates. The order is correct; no code change needed. This item documents that the order is intentional and should be preserved if either function is modified.

---

### IN-02: `weekDisplay` Formatting — No Guard for Malformed `week_ending_fmt`

**File:** `portal-v2/src/components/artifacts/ArtifactTableRow.tsx:26-29`

**Issue:** The display formatter checks `row.week_ending_fmt.length === 6` and slices it. If a row arrives from Supabase with a non-6-char value (e.g. a migration inserts a raw date string or the column is NULL-coerced to `''`), the fallback is to render the raw value, which could be an ISO date string or empty string. This is a display-only issue — no crash — but users would see the raw ISO date or blank.

```ts
const weekDisplay =
  row.week_ending_fmt.length === 6
    ? `${row.week_ending_fmt.slice(0, 2)}/${row.week_ending_fmt.slice(2, 4)}/${row.week_ending_fmt.slice(4, 6)}`
    : row.week_ending_fmt;
```

**Fix:** The `BillingArtifact` type declares `week_ending_fmt: string` (not optional), so this is a schema-enforcement concern. No code change is strictly required; a `?? '—'` fallback makes the display intent explicit.

---

### IN-03: `ArtifactTable.test.tsx` — `useQuery` Mock Overrides All `useQuery` Calls

**File:** `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx:10-16`

**Issue:** The mock replaces the entire `useQuery` export for all tests in this file:

```ts
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<...>();
  return { ...actual, useQuery: () => ({ data: [] }) };
});
```

Any future code path inside `ArtifactTable` that calls `useQuery` for a *different* purpose (e.g. user profile, permissions) will silently receive `{ data: [] }`, hiding regressions. The mock should be scoped more narrowly (e.g., mock only the `queryKey: ['artifact-variants']` call using `vi.spyOn` or by passing a custom `QueryClient`).

This does not affect test reliability for the current code, but it is a test-quality gap that can mask future bugs.

---

_Reviewed: 2026-06-01T20:51:00-05:00_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
