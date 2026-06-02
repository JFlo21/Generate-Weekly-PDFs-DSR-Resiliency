---
phase: 06-realtime-and-ui-polish
reviewed: 2026-06-02T18:20:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - portal-v2/src/contexts/ToastContext.tsx
  - portal-v2/src/hooks/useRealtimeArtifacts.ts
  - portal-v2/src/components/artifacts/NewArtifactPill.tsx
  - portal-v2/src/components/artifacts/ArtifactCard.tsx
  - portal-v2/src/components/artifacts/ArtifactTable.tsx
  - portal-v2/src/components/artifacts/ArtifactTableRow.tsx
  - portal-v2/src/components/artifacts/ArtifactEmptyState.tsx
  - portal-v2/src/components/artifacts/ArtifactSearchBar.tsx
  - portal-v2/src/components/artifacts/VariantFilterBar.tsx
  - portal-v2/src/App.tsx
  - portal-v2/src/test/setup.ts
  - portal-v2/package.json
  - portal-v2/src/contexts/__tests__/ToastContext.test.tsx
  - portal-v2/src/hooks/__tests__/useRealtimeArtifacts.test.ts
  - portal-v2/src/components/artifacts/__tests__/NewArtifactPill.test.tsx
  - portal-v2/src/components/artifacts/__tests__/ArtifactCard.test.tsx
  - portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-06-02T18:20:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Phase 06 delivers the Realtime subscription hook, toast notification wiring,
new-artifact pill, virtualized table row/card components, search/filter bars,
and their test suites. The security layering in `useRealtimeArtifacts` is
structurally sound: the auth guard correctly blocks subscription for
unqualified roles and the loading-race guard is present. The C-01
single-`ToastContainer` constraint is satisfied — `ToastProvider` owns the
container and `App.tsx` nests it inside `QueryClientProvider` as required.

Two blockers exist: the Realtime channel name is hardcoded to `'artifacts'`,
which causes the cleanup from React StrictMode's double-invoke to silently
unsubscribe the live channel; and the toast-on-new-artifact effect fires on
every `pendingCount` increment (not only on the 0→1 transition), producing a
toast storm during burst inserts. Five warnings cover the `y`-transform
violation in `NewArtifactPill` (conflicts with `position: sticky`), an unsafe
`sortColumn` cast that bypasses the type union, an `initialLoadComplete` ref
pattern that causes an extra render cycle, a magic-number `.limit(2000)` in
the inline variants query, and an inconsistency between the desktop and mobile
empty-state branches. Three informational items round out the report.

---

## Critical Issues

### CR-01: Hardcoded Realtime channel name causes silent unsubscription in StrictMode

**File:** `portal-v2/src/hooks/useRealtimeArtifacts.ts:39`

**Issue:** The channel is created with the static string `'artifacts'`.
Supabase's `supabase-js` client deduplicates channels that share the same
name on a single client instance. In React 18 StrictMode, `useEffect` fires
twice (mount → cleanup → mount). The cleanup from the first invocation calls
`channel.unsubscribe()` on the *shared* channel object, which tears down the
channel that the second mount just re-registered. The result: the hook
silently stops receiving INSERT events without any error or warning.
In production (StrictMode off), a single unmount/remount cycle — e.g. a route
transition that briefly removes and re-adds `ArtifactTable` — produces the
same failure if the channel was not fully removed before the re-subscription.

Additionally, `channelRef` is populated after `.subscribe()` returns but is
never read elsewhere (cleanup uses the local `channel` variable captured by
the closure, not `channelRef.current`). The ref is therefore dead code.

**Fix:**
```ts
// Use a stable but unique name so StrictMode double-invoke creates two
// independent channels, each with its own cleanup.
const channelName = useRef(`artifacts:${Math.random().toString(36).slice(2)}`);

// Inside useEffect:
const channel = supabase
  .channel(channelName.current)
  .on( /* ... */ )
  .subscribe();

// Remove the now-unused channelRef.
```
Drop `channelRef` entirely — the local `channel` variable in the closure is
sufficient for cleanup.

---

### CR-02: Toast fires on every `pendingCount` increment, not only on first arrival

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:50-59`

**Issue:** The `useEffect` depends on `[pendingCount]` and fires whenever
`pendingCount` changes to any positive value. A burst of INSERT events in
rapid succession (e.g. a CI run uploading 10 artifacts in 2 seconds) produces
10 stacked toasts: "1 new artifact", "2 new artifacts", …, "10 new artifacts".
The `addToast` eslint-disable comment acknowledges that `addToast` is
intentionally excluded from the dependency array, but does not address the
increment-storm problem. The D-03 design intent is a single "you have new
artifacts" notification on first arrival, not a per-increment counter.

**Fix:**
```ts
// Track whether a toast is already live for this pending batch.
const toastFiredRef = useRef(false);

useEffect(() => {
  if (pendingCount > 0 && !toastFiredRef.current) {
    toastFiredRef.current = true;
    addToast('info', 'New artifacts are available — click to load.');
  }
  if (pendingCount === 0) {
    // Reset so the next batch can fire a fresh toast.
    toastFiredRef.current = false;
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [pendingCount]);
```
The toast message should not embed the count (which the user will not see
refresh as new events arrive); instead the pill already shows the live count.

---

## Warnings

### WR-01: `y` transform in `NewArtifactPill` breaks `position: sticky` in Safari/Chrome

**File:** `portal-v2/src/components/artifacts/NewArtifactPill.tsx:38-40`

**Issue:** The pill uses `sticky top-0` positioning together with Framer
Motion's `initial={{ opacity: 0, y: -8 }}` / `exit={{ opacity: 0, y: -8 }}`.
Applying a CSS `transform` (which Framer Motion uses for `y`) creates a new
stacking context, breaking `position: sticky` in all major browsers — the
element stops sticking and shifts with the transform offset instead. The
phase context explicitly mandates opacity-only animation to avoid transform
conflicts; `ArtifactTableRow` correctly follows this rule. `NewArtifactPill`
does not.

**Fix:** Remove `y` from all motion variants:
```tsx
initial={{ opacity: 0 }}
animate={{ opacity: 1 }}
exit={{ opacity: 0 }}
transition={prefersReduced ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }}
```

---

### WR-02: Unsafe `sortColumn` cast allows invalid column through to query layer

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:75`

**Issue:** `sort.id as ArtifactsQueryParams['sortColumn']` force-casts
whatever string TanStack Table puts into `sorting[0].id`. Columns `'download'`
and `'variant'` have `enableSorting: false` which prevents the UI toggle, but
`sorting` state can be set programmatically or pre-populated with any id.
The default sort at line 68 uses `'week_ending'` which is valid, but nothing
prevents a future caller from passing `{ id: 'download', desc: false }` via
`setSorting`. When that invalid column reaches `useArtifactsInfinite`, it
either silently uses the default order or errors — both are incorrect from a
UX standpoint and the cast hides the type error.

**Fix:** Validate before casting:
```ts
const rawId = sorting[0]?.id ?? 'week_ending';
const sortColumn: ArtifactsQueryParams['sortColumn'] = SORTABLE_IDS.has(
  rawId as ArtifactsQueryParams['sortColumn']
)
  ? (rawId as ArtifactsQueryParams['sortColumn'])
  : 'week_ending';
```

---

### WR-03: `initialLoadComplete` uses state instead of a ref, causing an extra render cycle

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:84-89`

**Issue:** `initialLoadComplete` is `useState(false)`. The `useEffect` at
line 85 sets it to `true`, which schedules a re-render. During that re-render
the `initialLoadComplete` check at line 196 correctly switches all
`staggerDelay` values to `0`, so correctness is preserved. However, using
state for a "has fired once" gate is the wrong primitive — `useRef` does not
trigger a re-render. The extra render wastes a cycle and can cause
already-animated rows to briefly re-evaluate their `staggerDelay` (which
evaluates to `0`, so no visual artifact, but the work is wasted).

Because `initialLoadComplete` is also read in the JSX at line 196, switching
to a plain ref requires reading `.current` in the render path, which is
acceptable for a stable gate value:

**Fix:**
```ts
const initialLoadRef = useRef(false);

// In the effect:
useEffect(() => {
  if (q.status === 'success' && allRows.length > 0 && !initialLoadRef.current) {
    initialLoadRef.current = true;
  }
}, [q.status, allRows.length]);

// In JSX:
const staggerDelay = !initialLoadRef.current
  ? Math.min(virtualRow.index * 0.02, 0.2)
  : 0;
```

---

### WR-04: Magic number `.limit(2000)` and inline raw Supabase call in `ArtifactTable`

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:99`

**Issue:** The variant options query executes a raw `supabase.from('artifacts').select('variant').limit(2000)` directly inside `ArtifactTable`. Two problems:
1. `2000` is a magic number with no named constant or comment explaining the ceiling choice. If the production dataset exceeds 2000 unique artifact rows the options list silently truncates (though practically, `variant` has only ~5 distinct values today).
2. Bypasses the query abstraction layer used elsewhere (`useArtifactsInfinite`). Any future column-level security or response-transformation logic added to that layer will not apply here.

**Fix:**
```ts
// At module level:
const VARIANT_OPTIONS_ROW_CAP = 2000; // distinct variant values cap; variants are ~5 in practice

// In queryFn:
const { data, error } = await supabase
  .from('artifacts')
  .select('variant')
  .limit(VARIANT_OPTIONS_ROW_CAP);
```
Consider extracting a `useArtifactVariants()` hook so the raw query is not
inside the table component.

---

### WR-05: Desktop and mobile empty-state branches diverge in structure, creating maintenance hazard

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx:170-177` vs `344-352`

**Issue:** The desktop path (`renderBody()`) uses early-return guards for
`'pending'` and `'error'`, then checks `allRows.length === 0 && !debouncedSearch && variants.length === 0`
for `EmptyDBState`, followed by `allRows.length === 0` for `NoResultsState`.
The mobile path uses explicit `q.status === 'success'` guards on each branch.
These two code paths are logically equivalent today, but they are written in
different structural styles. Any future change to the empty-state conditions
(e.g. adding a loading-skeleton branch to mobile, or a new filter type) will
require simultaneous edits to two structurally different branches. A shared
helper or extracted component would eliminate this drift risk.

**Fix:** Extract a `renderArtifactBody(rows, status, filters)` pure function
(or component) and call it from both the desktop and mobile branches with
appropriate props. This is a refactor, not an emergency fix.

---

## Info

### IN-01: `ArtifactCard` uses `y: 4` transform — inconsistent with `ArtifactTableRow` opacity-only rule

**File:** `portal-v2/src/components/artifacts/ArtifactCard.tsx:40`

**Issue:** `initial={{ opacity: 0, y: 4 }}` applies a `transform` on the
mobile card. `ArtifactCard` is rendered in the `sm:hidden` non-virtualized
list, so there is no translateY conflict today. However, the phase convention
(and the explicit comment in `ArtifactTableRow`) mandates opacity-only
animation. The inconsistency will confuse future maintainers about whether the
rule applies to all artifact-list items or only virtualized rows.

**Fix:** Remove `y: 4` from `ArtifactCard`'s motion variants to match
`ArtifactTableRow`:
```tsx
initial={{ opacity: 0 }}
animate={{ opacity: 1 }}
transition={prefersReduced ? { duration: 0 } : { duration: 0.15, ease: 'easeOut' }}
```

---

### IN-02: Dead `channelRef` in `useRealtimeArtifacts`

**File:** `portal-v2/src/hooks/useRealtimeArtifacts.ts:29-31, 50`

**Issue:** `channelRef` is declared, populated at line 50 (`channelRef.current = channel`),
but never read. The cleanup function at line 52 correctly uses the
closure-captured `channel` variable, not `channelRef.current`. The ref is
unreachable dead code and will confuse reviewers into thinking it serves a
purpose (e.g. an imperative unsubscribe from outside the hook).

**Fix:** Delete the `channelRef` declaration and the `channelRef.current = channel` assignment.
If a future API needs external unsubscription, expose a returned `disconnect` callback instead.

---

### IN-03: `useRealtimeArtifacts.test.ts` uses top-level `await import` — fragile mock-ordering dependency

**File:** `portal-v2/src/hooks/__tests__/useRealtimeArtifacts.test.ts:67`

**Issue:** `const { useRealtimeArtifacts } = await import('../useRealtimeArtifacts');`
at module scope depends on Vitest's mock-hoisting having already registered
the `vi.mock('../../lib/supabase', ...)` and `vi.mock('../useAuth', ...)` stubs
before the dynamic import resolves. Vitest hoists `vi.mock` calls to the top
of the module, so this works today. However, it is a non-obvious ordering
dependency: the comment block labeling it "Import under test (after mocks are
registered)" is the only documentation. If the file is refactored or the mock
registrations are moved below the import, the test suite silently tests the
real Supabase client.

**Fix:** Use a static import at the top of the file (the normal pattern), which
is guaranteed safe after `vi.mock` hoisting:
```ts
import { useRealtimeArtifacts } from '../useRealtimeArtifacts';
```
Remove the dynamic `await import` at line 67.

---

_Reviewed: 2026-06-02T18:20:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
