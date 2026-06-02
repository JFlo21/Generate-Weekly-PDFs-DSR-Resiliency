# Phase 06: Realtime and UI Polish — Research

**Researched:** 2026-06-02
**Domain:** React 18 / Supabase Realtime / Framer Motion / Tailwind responsive / jest-axe accessibility
**Confidence:** HIGH (all critical claims verified via Context7, npm registry, or official Supabase documentation)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `06-UI-SPEC.md` is the authoritative visual/interaction contract. The `/frontend-design` pass runs as an execution-polish layer ONLY within locked tokens. Any conflicting proposal is a deferred v2 idea.
- **D-02:** `/frontend-design` output is propose-then-approve; it must not silently override the approved UI-SPEC.
- **D-03:** Notification = count-only toast + "Load new" pill, both fire on INSERT. No auto-insert of rows mid-scroll. Toast (info variant) auto-dismisses; pill persists until user loads or dismisses.
- **D-04:** Realtime gating is defense-in-depth. Subscribe ONLY when `isBilling`/`isAdmin`. Payload surfaced to UI is count-only. Researcher MUST confirm RLS withholds row payloads from unauthorized sockets.
- **D-05:** Realtime is unit-tested by mocking the Supabase channel in vitest. Live end-to-end behavior verified during UAT only.
- **D-06:** Build a custom `ToastContext` on the existing `Toast.tsx` + `useToast.ts` primitives. `sonner` rejected. Provider nests inside `QueryClientProvider`.
- **D-07:** Verify WCAG AA with both jest-axe automated + manual keyboard/focus-ring/screen-reader walkthrough.
- **D-08:** Apply C-02 fix verbatim — `.limit(2000)` + `staleTime: 10 * 60 * 1000` on `['artifact-variants']` query.

### Claude's Discretion

- `useInfiniteQuery` page-size / TanStack-Virtual overscan tuning.
- Exact internal stagger implementation within the locked animation catalog (index × 20ms, capped 200ms / 10 rows).
- Precise mount point of `ToastContext` provider (must be inside `QueryClientProvider`).
- File/module layout of the 4 net-new components, provided each matches its UI-SPEC §Component Inventory contract.

### Deferred Ideas (OUT OF SCOPE)

- Any `/frontend-design` proposal conflicting with locked UI-SPEC tokens — captured as v2 visual-refresh idea.
- Live Realtime integration test in CI.
- Filename search (SEARCH scope is WR # + week-ending only).
- Excel preview / bulk ZIP / CSV export / Cmd+K.
- Physical deletion of `portal/` + orphaned legacy components — Phase 07.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-06 | Supabase Realtime delivers new-artifact INSERT events; `artifacts` table added to `supabase_realtime` publication | §Standard Stack, §Architecture Patterns (Realtime wiring), §D-04 Authorization Model |
| UI-01 | Portal is responsive across desktop/tablet/mobile widths | §Architecture Patterns (responsive swap), §Common Pitfalls (card list virtualization) |
| UI-02 | Tasteful Framer Motion animations without degrading table performance | §Architecture Patterns (stagger pattern), §Common Pitfalls (virtualized row animation footgun) |
| UI-03 | Accessible, consistent visual design (keyboard nav, WCAG-AA contrast) | §Architecture Patterns (jest-axe wiring), §Validation Architecture, §Common Pitfalls (jsdom color-contrast) |
</phase_requirements>

---

## Summary

Phase 06 polishes the stable Phase 05 artifact table with four capabilities: Supabase Realtime INSERT notifications (DATA-06), responsive mobile layout (UI-01), Framer Motion entrance animations (UI-02), and WCAG-AA accessibility (UI-03), plus two locked carryover fixes (C-01 dual-toast consolidation, C-02 variant query cap).

**The highest-risk item is the Supabase Realtime RLS authorization model (D-04).** Research confirms that `postgres_changes` DOES enforce RLS per-event before delivering payloads to clients — an `anon` or `pending`-role client that subscribes receives zero row data because the `artifacts_select_billing_or_admin` policy evaluates to false for them. The D-04 design (subscribe only when `isBilling`/`isAdmin` + surface count-only) is safe-by-construction AND has a second layer of defense from RLS itself. One gap: `public.artifacts` is NOT confirmed to be in the `supabase_realtime` publication yet — the schema file has no `ALTER PUBLICATION` statement. This is a required Wave 0 SQL step.

**The trickiest UI item is the Framer Motion row-entrance stagger over the TanStack-Virtual absolute-positioned table.** The key constraint is that animation must be placed on `ArtifactTableRow`'s inner root `<div>` (the `role="row"` element), NOT on the virtualizer's positioning wrapper `<div>`. `AnimatePresence initial={false}` on the table body wrapper prevents re-animation on scroll/filter. Stagger is applied per-row via `transition={{ delay: Math.min(index * 0.02, 0.2) }}` passed as a prop from `ArtifactTable`.

**Primary recommendation:** Build in four waves — (1) publication enablement + ToastContext scaffolding, (2) `useRealtimeArtifacts` hook + NewArtifactPill, (3) responsive layout + ArtifactCard, (4) Framer Motion animations + jest-axe a11y tests.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Realtime INSERT subscription | Browser / Client | — | WebSocket connection lives in the browser; `supabase-js` manages the channel; Supabase server enforces RLS before payload delivery |
| RLS enforcement on Realtime payloads | Database / Supabase | — | Server-side; the Realtime server runs RLS checks before broadcasting each change event to each subscriber |
| `pendingCount` state | Browser / Client | — | In-memory React state; never persisted |
| Toast / pill display | Browser / Client | — | React state in ToastContext provider; no server involvement |
| Responsive layout switch | Browser / Client | — | Pure CSS (Tailwind `sm:` breakpoint); no server involvement |
| Framer Motion animations | Browser / Client | — | DOM animation; no server involvement |
| WCAG-AA automated checks | CI (test runner) | Manual UAT | jest-axe in vitest catches structure/ARIA violations; color-contrast requires manual browser check |
| `['artifact-variants']` query cap (C-02) | Browser / Client | Supabase DB | Client-side query change; DB executes the limited query |

---

## Standard Stack

### Core (already installed — no new runtime deps needed)

| Library | Version in project | Latest | Purpose | Why Standard |
|---------|-------------------|--------|---------|--------------|
| `@supabase/supabase-js` | `^2.45.4` (pinned in pkg) | `2.107.0` | Realtime channel + DB queries | Official Supabase JS client; the `supabase` singleton already initialized in `portal-v2/src/lib/supabase.ts` |
| `framer-motion` | `^11.11.17` (pinned in pkg) | `12.40.0` | Row-entrance stagger, pill appear/disappear, existing toast animations | Already a dependency; 11.x is the installed major — stay on 11.x, do NOT upgrade to 12.x in this phase |
| `lucide-react` | `^0.460.0` | latest | `Loader2` spinner, Download icon, X dismiss icon | Already installed; `Loader2 className="animate-spin"` for download in-progress state |
| `@tanstack/react-virtual` | `^3.14.1` | `3.14.2` | Virtualizer that owns the absolute-positioned row positioning | Already installed; Phase 06 must NOT change virtualizer container structure |
| `@tanstack/react-query` | `^5.100.14` | `5.100.14` | `queryClient.invalidateQueries` in `clearPending`; `useQuery` for variants | Already installed |
| `tailwindcss` | `^3.4.14` | latest | `sm:hidden` / `hidden sm:block` responsive swap, all spacing tokens | Already installed |

### New Dev Dependencies (test-only)

| Library | Version | Purpose | Install |
|---------|---------|---------|---------|
| `jest-axe` | `10.0.0` (latest) | Axe-core WCAG assertions in vitest | `npm install -D jest-axe @types/jest-axe` |
| `@types/jest-axe` | latest | TypeScript types for `toHaveNoViolations` | bundled with jest-axe install |

**Version verification:** [VERIFIED: npm registry 2026-06-02]
- `jest-axe`: `10.0.0`
- `vitest-axe` (alternative): `0.1.0` — too early/unstable; use `jest-axe` directly per D-07
- `@supabase/supabase-js`: `2.107.0` (project pins `^2.45.4`; compatible — no upgrade needed this phase)
- `framer-motion`: `12.40.0` available but project pins `^11.11.17` — **do NOT upgrade**; the v12 API has breaking changes to `AnimatePresence` and `motion` component signatures. Stay on 11.x.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `jest-axe` | `vitest-axe` | `vitest-axe` 0.1.0 is immature; `jest-axe` 10.0.0 works correctly with vitest via `expect.extend(toHaveNoViolations)` |
| Custom `ToastContext` | `sonner` | D-06 explicitly rejects `sonner` to minimize deps; existing primitives are sufficient |
| Per-row `motion.div` with inline `delay` prop | Container `staggerChildren` variant | Virtualizer only mounts window rows — parent-driven `staggerChildren` never has all children present simultaneously. Per-row `delay` prop is the correct approach for virtualized lists. |

**Installation (dev dependencies only):**
```bash
npm install -D jest-axe @types/jest-axe
```

---

## D-04: Supabase Realtime RLS Authorization Model (HIGHEST PRIORITY FINDING)

### Confirmed Behavior [VERIFIED: Context7 /supabase/realtime + WebSearch official docs 2026-06-02]

**How `postgres_changes` enforces RLS:**

1. The Realtime server receives WAL (Write-Ahead Log) events from Postgres for all tables in the `supabase_realtime` publication.
2. For each change event, before broadcasting to any subscriber, the server runs a privilege check: it uses `pg_catalog.has_column_privilege(working_role, table, column, 'SELECT')` against the subscribing client's JWT role. Columns the client lacks SELECT privilege on are stripped from the payload.
3. If the client's role has no SELECT access to the row (RLS policy evaluates to false), the client receives **nothing** — the event is silently dropped per-subscriber.

**What this means for `public.artifacts`:**

The deployed RLS policy is:
```sql
CREATE POLICY artifacts_select_billing_or_admin ON public.artifacts
    FOR SELECT TO authenticated
    USING (public.current_user_role() IN ('admin','billing'));
```

- `admin` / `billing` role: RLS evaluates to TRUE → full column payload delivered.
- `pending` role: RLS evaluates to FALSE → zero payload delivered even if socket is open.
- `anon` role (unauthenticated): The `TO authenticated` scoping means this policy does not apply at all to `anon` → zero rows, zero payload.

**Does an anon/pending socket get the INSERT event?** No row payload reaches the client. The Realtime server checks RLS per-subscriber before each broadcast. An unauthenticated socket connecting with the anon JWT gets no artifact data. [CITED: https://supabase.com/docs/guides/realtime/postgres-changes]

**Is D-04's client-side gate sufficient alone?** No — the client-side gate (`isBilling`/`isAdmin` before subscribing) is the first layer of defense. RLS is the second. The design is correct defense-in-depth. If the client-side gate were missing (e.g., a `billing` user who temporarily becomes `pending`), RLS would still deliver zero rows. The count-only payload surfaced to React state is a third layer that prevents any row data from entering component state even if somehow a payload arrived.

**Gap for Phase 07 audit:** The current schema has NO `ALTER PUBLICATION supabase_realtime ADD TABLE artifacts` statement. This is a required enablement step. Until it is applied, `postgres_changes` subscriptions on `artifacts` receive no events regardless of authorization. [VERIFIED: portal_schema.sql — no such statement present]

**JWT / auth-refresh handling:** `supabase-js` automatically propagates token refreshes to Realtime via `_handleTokenChanged` → `realtime.setAuth()`. When `onAuthStateChange` fires `TOKEN_REFRESHED`, the new JWT is sent to the Realtime channel and the access policy cache is refreshed. No manual `channel.setAuth()` call needed in the hook. [VERIFIED: Context7 /supabase/supabase-js SupabaseClient source]

**Private channels vs. standard `postgres_changes`:** The "private channel" concept in Supabase Realtime is for Broadcast/Presence features (it checks `realtime.messages` table RLS). `postgres_changes` uses the **table's own RLS policies directly** — the `private: true` channel flag is irrelevant for `postgres_changes`. Do not confuse the two. [CITED: Supabase Realtime Authorization docs]

### Exact Enablement SQL

```sql
-- Required: add artifacts to the supabase_realtime publication
-- Run once in the Supabase SQL Editor for project poeyztlmsawfoqlanucc
ALTER PUBLICATION supabase_realtime ADD TABLE public.artifacts;

-- Verify (run in SQL Editor):
SELECT tablename FROM pg_publication_tables
WHERE pubname = 'supabase_realtime';
-- artifacts should appear in the result
```

[VERIFIED: Context7 /supabase/realtime DEVELOPERS.md — exact SQL pattern]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (portal-v2)
  │
  ├── AuthProvider (useAuth → isBilling / isAdmin)
  │     └── gate: only if isBilling || isAdmin ──────────────┐
  │                                                           │
  ├── ToastContext (new, D-06)                                │
  │     └── single <ToastContainer> (bottom-right z-50)      │
  │                                                           ▼
  ├── useRealtimeArtifacts hook              supabase.channel('artifacts')
  │     ├── INSERT event ──────────────►    .on('postgres_changes', INSERT)
  │     │     ├── pendingCount++             │
  │     │     └── addToast('info', ...)      │  Supabase Realtime Server
  │     ├── clearPending()                   │  (checks RLS per-subscriber
  │     │     ├── pendingCount = 0           │   before delivering payload)
  │     │     └── invalidateQueries(['artifacts']) │
  │     └── unmount → channel.unsubscribe()  │
  │                                          │
  ├── ArtifactTable (existing Phase 05)      ▼
  │     ├── <table> hidden sm:block ◄── QueryClient ['artifacts']
  │     │     └── ArtifactTableRow          (infinite scroll)
  │     │           └── motion.div (entrance stagger, initial load only)
  │     └── ArtifactCard list sm:hidden ◄── same allRows data
  │           └── GlassCard per row
  │
  └── NewArtifactPill (sticky top, z-10)
        └── visible when pendingCount > 0
              ├── "Load N" → clearPending()
              └── "×" → dismiss (no load)
```

### Recommended Project Structure (new files only)

```
portal-v2/src/
├── contexts/
│   └── ToastContext.tsx          # C-01 fix: single global toast provider (D-06)
├── hooks/
│   └── useRealtimeArtifacts.ts   # DATA-06: Realtime channel hook
├── components/artifacts/
│   ├── NewArtifactPill.tsx       # DATA-06: "Load N new artifacts" pill
│   └── ArtifactCard.tsx          # UI-01: mobile stacked card (<640px)
```

### Pattern 1: `useRealtimeArtifacts` Hook — Exact Channel Wiring

**What:** Subscribe to `postgres_changes` INSERT events on `public.artifacts`, count-only.
**When to use:** Called from `ArtifactTable` (or its parent), gated by `isBilling || isAdmin`.

```typescript
// Source: Context7 /supabase/supabase-js README + /supabase/realtime DEVELOPERS.md
import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { supabase } from '../lib/supabase';
import { useAuth } from './useAuth';

export function useRealtimeArtifacts() {
  const { isBilling, isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [pendingCount, setPendingCount] = useState(0);
  const channelRef = useRef<ReturnType<typeof supabase.channel> | undefined>(undefined);

  useEffect(() => {
    // D-04: defense-in-depth gate — only authorized roles subscribe
    if (!isBilling && !isAdmin) return;

    const channel = supabase
      .channel('artifacts')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'artifacts' },
        (_payload) => {
          // Count-only: never place payload data into state (D-04)
          setPendingCount((n) => n + 1);
        }
      )
      .subscribe((status) => {
        // Optional: log subscription status for debugging
        if (status === 'SUBSCRIBED') {
          // channel is live
        }
      });

    channelRef.current = channel;

    return () => {
      // Zero subscription leak on unmount (UI-SPEC contract)
      void channel.unsubscribe();
    };
  }, [isBilling, isAdmin]); // Re-subscribe if role changes

  const clearPending = useCallback(() => {
    setPendingCount(0);
    void queryClient.invalidateQueries({ queryKey: ['artifacts'] });
  }, [queryClient]);

  return { pendingCount, clearPending };
}
```

**Key points:**
- `_payload` is received but NEVER stored — count increment only. This satisfies the D-04 "count-only" contract.
- `channel.unsubscribe()` in cleanup — zero subscription leak.
- JWT is auto-propagated by `supabase-js`'s `_handleTokenChanged` → `realtime.setAuth()` on `TOKEN_REFRESHED`. No manual `setAuth` needed.
- `supabase.realtime` reconnects automatically on WebSocket drop. No reconnect logic needed in the hook.
- **Status callback values:** `'SUBSCRIBED'` | `'TIMED_OUT'` | `'CLOSED'` | `'CHANNEL_ERROR'` — per supabase-js source. Only `'SUBSCRIBED'` means live; the others are failure states. For Phase 06 the spec says silent reconnect (no copy needed in Copywriting Contract); no error toast for connection failure is required.

### Pattern 2: `ToastContext` — C-01 Fix

**Current broken state (confirmed by reading `App.tsx` line 81 + `ArtifactTable.tsx` line 267):**
- `App.tsx` has its own `useToast()` + `<ToastContainer>` (line 81).
- `ArtifactTable.tsx` has its own `useToast()` + `<ToastContainer>` (line 267).
- Two independent toast stacks. The `useDownloadArtifact` hook receives `addToast` from `ArtifactTable`'s local instance.

**Fix pattern:**

```typescript
// Source: existing AuthProvider pattern in App.tsx (line 29-31) — mirrors this exactly
// portal-v2/src/contexts/ToastContext.tsx

import React, { createContext, useContext, ReactNode } from 'react';
import { useToast } from '../hooks/useToast';
import { ToastContainer } from '../components/ui/Toast';
import type { ToastType } from '../lib/types';

interface ToastContextValue {
  toasts: ReturnType<typeof useToast>['toasts'];
  addToast: (type: ToastType, message: string) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const { toasts, addToast, removeToast } = useToast();
  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToastContext(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToastContext must be used within ToastProvider');
  return ctx;
}
```

**App.tsx tree change:**
```typescript
// BEFORE (App.tsx):
// const { toasts, removeToast } = useToast();  // DELETE
// <ToastContainer toasts={toasts} onRemove={removeToast} />  // DELETE

// AFTER — wrap inside QueryClientProvider, outside BrowserRouter:
<QueryClientProvider client={queryClient}>
  <ToastProvider>          {/* NEW — inside QueryClientProvider (D-06) */}
    <BrowserRouter>
      <ErrorBoundary>
        <AuthProvider>
          {/* ... routes unchanged ... */}
        </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  </ToastProvider>
</QueryClientProvider>
```

**ArtifactTable.tsx changes:**
- Delete lines 41-42: `const { toasts, addToast, removeToast } = useToast();` and `const { download, downloading } = useDownloadArtifact(addToast);`
- Replace with: `const { addToast } = useToastContext();` + `const { download, downloading } = useDownloadArtifact(addToast);`
- Delete line 267: `<ToastContainer toasts={toasts} onRemove={removeToast} />`

**`useDownloadArtifact` signature is unchanged** — it still accepts `addToast` as a prop parameter. No refactor of that hook required; only the caller (`ArtifactTable`) changes where it sources `addToast` from.

### Pattern 3: Row-Entrance Stagger Over TanStack-Virtual

**The core problem:** TanStack-Virtual renders rows as absolutely-positioned `<div>` wrappers with `transform: translateY(Npx)`. The virtualizer only mounts the window of visible rows — not all rows simultaneously. Framer Motion's parent-driven `staggerChildren` variant depends on all children being present in the render tree; that assumption fails for virtualized lists.

**Why parent `staggerChildren` breaks here:**
When the user scrolls, new virtual rows mount (rows 10-20 replace rows 0-10). If `staggerChildren` is on the container, newly mounted scroll rows would re-animate. The UI-SPEC explicitly forbids animating rows fetched by infinite scroll.

**The correct pattern — per-row `delay` prop, initial-load gate:**

```typescript
// In ArtifactTable.tsx — pass stagger delay to each row
// The virtualizer wrapper div is untouched; animation is on ArtifactTableRow's root
// Source: Framer Motion docs (Context7 /grx7/framer-motion stagger + AnimatePresence)

// 1. Track whether the initial page load has completed
const [initialLoadComplete, setInitialLoadComplete] = useState(false);

useEffect(() => {
  if (q.status === 'success' && allRows.length > 0 && !initialLoadComplete) {
    setInitialLoadComplete(true);
  }
}, [q.status, allRows.length, initialLoadComplete]);

// 2. In the virtualizer render, pass stagger delay only for initial load
{virtualItems.map((virtualRow) => {
  const row = allRows[virtualRow.index];
  // Stagger delay: index × 20ms, capped at 200ms (10 rows max). UI-SPEC contract.
  // After initial load completes, pass delay=0 (no animation for scroll rows).
  const staggerDelay = !initialLoadComplete
    ? Math.min(virtualRow.index * 0.02, 0.2)
    : 0;

  return (
    <div
      key={virtualRow.key}
      style={{
        position: 'absolute',
        top: 0, left: 0, width: '100%',
        height: `${virtualRow.size}px`,
        transform: `translateY(${virtualRow.start}px)`,
      }}
    >
      {row ? (
        <ArtifactTableRow
          row={row}
          onDownload={download}
          isDownloading={downloading === row.id}
          staggerDelay={staggerDelay}  // NEW prop
        />
      ) : (
        <Skeleton className="h-12 w-full mx-5 my-1" />
      )}
    </div>
  );
})}
```

```typescript
// In ArtifactTableRow.tsx — apply animation on the root div
// Source: Framer Motion docs; useReducedMotion from framer-motion
import { motion, useReducedMotion } from 'framer-motion';

interface ArtifactTableRowProps {
  // ... existing props ...
  staggerDelay: number;   // NEW
}

export const ArtifactTableRow = React.memo(function ArtifactTableRow({
  row, onDownload, isDownloading, staggerDelay,
}: ArtifactTableRowProps) {
  const prefersReduced = useReducedMotion();

  return (
    <motion.div
      role="row"
      className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_auto] items-center border-b border-slate-50 hover:bg-slate-50/50 transition-colors w-full h-14"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={
        prefersReduced
          ? { duration: 0 }
          : { duration: 0.15, ease: 'easeOut', delay: staggerDelay }
      }
    >
      {/* ... cells unchanged ... */}
    </motion.div>
  );
});
```

**Why this works with virtualization:**
- The animation is on `motion.div` (the `role="row"` element inside the virtualizer's positioning wrapper).
- The positioning wrapper's `position: absolute` + `transform: translateY()` is NOT changed.
- `staggerDelay=0` for all rows after initial load → subsequent scroll rows appear instantly.
- `useReducedMotion()` sets `duration: 0` — CSS `prefers-reduced-motion` override in `globals.css` is the belt; this is the suspenders.
- No `AnimatePresence` wrapping on the virtualizer body is needed for row entrance — `AnimatePresence` is only needed for exit animations (rows never exit in the virtualized table; they unmount when scrolled out). Per UI-SPEC: "animation plays ONCE on initial mount of the row batch."

**`AnimatePresence initial={false}` for `NewArtifactPill`:**
The pill uses `AnimatePresence` because it has an exit animation (slides up on dismiss). The pill is NOT inside the virtualized container. `initial={false}` on the `AnimatePresence` wrapper prevents the pill from animating in on first render if it's already visible (e.g., on hot reload). [VERIFIED: Context7 /grx7/framer-motion AnimatePresence docs]

### Pattern 4: Responsive Table ↔ Card Swap (UI-01)

**Tailwind pattern:**
```tsx
{/* Desktop/tablet: virtualized table (sm+) */}
<div className="hidden sm:block">
  {/* existing ArtifactTable with virtualizer */}
</div>

{/* Mobile: stacked card list (<640px) */}
<div className="sm:hidden" role="list">
  {allRows.map((row) => (
    <ArtifactCard
      key={row.id}
      row={row}
      onDownload={download}
      isDownloading={downloading === row.id}
    />
  ))}
</div>
```

**Mobile card list and virtualization:** With ~2,383 rows, rendering all `ArtifactCard` elements without virtualization is a risk. However:
- The `allRows` array is built from `useArtifactsInfinite` — it only holds loaded pages (75 rows per page). On initial render only 75 rows are in `allRows`.
- The card list uses `overflow-y-auto` natural scroll (no fixed height cap per UI-SPEC).
- `React.memo` on `ArtifactCard` prevents re-renders on unrelated state changes.
- As the user scrolls the page, the existing `useEffect` infinite-scroll trigger (watching `lastItemIndex`) still fires and loads more pages.
- **Verdict:** No separate mobile virtualization needed for Phase 06. The existing infinite-load mechanism provides sufficient performance. [ASSUMED — based on 75-row page size and React.memo; monitor real device performance during UAT]

### Pattern 5: C-02 Variant Query Cap

**Current code (ArtifactTable.tsx lines 67-76):**
```typescript
const { data: variantOptionsData } = useQuery({
  queryKey: ['artifact-variants'],
  queryFn: async () => {
    const { data, error } = await supabase
      .from('artifacts')
      .select('variant');
    if (error) throw error;
    return Array.from(new Set((data ?? []).map((r: { variant: string }) => r.variant)));
  },
});
```

**Fix (D-08):**
```typescript
const { data: variantOptionsData } = useQuery({
  queryKey: ['artifact-variants'],
  queryFn: async () => {
    const { data, error } = await supabase
      .from('artifacts')
      .select('variant')
      .limit(2000);           // C-02: cap unbounded query
    if (error) throw error;
    return Array.from(new Set((data ?? []).map((r: { variant: string }) => r.variant)));
  },
  staleTime: 10 * 60 * 1000, // C-02: 10-min staleTime (variants don't change often)
});
```

**Why safe:** Variant values are a small fixed set (primary, AEP, base, VacCrew variants). 2,383 rows max today; 2,000 limit captures all distinct variant values with headroom. As the dataset grows beyond 2,000 in future, only the variant deduplication set is affected — new variants beyond row 2,000 would not appear in the filter bar. This is acceptable for Phase 06; Phase 07 can add a proper `SELECT DISTINCT variant` query if needed. [ASSUMED — acceptable tradeoff for Phase 06]

### Anti-Patterns to Avoid

- **`AnimatePresence` + `staggerChildren` on the virtualizer container:** Parent-driven stagger assumes all children are mounted simultaneously. Virtualized lists only mount visible rows. Use per-row `delay` prop instead.
- **Placing `motion.*` on the virtualizer's positioning wrapper `<div>`:** This `<div>` uses `transform: translateY(Npx)` for scroll position. Framer Motion would conflict with the virtualizer's transform. Animation MUST go on the inner `ArtifactTableRow` root element.
- **`layout` prop on rows inside the virtualizer:** Would fire layout recalculation on every scroll tick. UI-SPEC explicitly forbids it.
- **`will-change: transform` on row elements:** Acceptable only on the Download spinner (bounded count). On rows it creates a new stacking context per row and inflates GPU memory.
- **Calling `channel.unsubscribe()` synchronously during render:** Must be in `useEffect` cleanup, not render body.
- **Opening the Realtime channel before `isBilling`/`isAdmin` is resolved:** `useAuth` starts with `loading: true`; hook should also gate on `!loading` to avoid a brief subscribe-then-immediately-unsubscribe cycle if role is pending auth state resolution.
- **Calling `addToast` from `useRealtimeArtifacts` directly:** The toast for new artifacts should be triggered in `ArtifactTable` (which has context access), not inside `useRealtimeArtifacts` (which should be a pure data hook returning `pendingCount`). This keeps the hook testable without a ToastContext wrapper.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Realtime WebSocket management | Custom WebSocket + reconnect logic | `supabase.channel().on().subscribe()` | Auto-reconnect, JWT propagation, RLS enforcement all handled by supabase-js |
| Toast auto-dismiss timers | Custom setTimeout management | Existing `useToast.ts` (already handles timers + cleanup) | `useToast` already has `DISMISS_AFTER_MS=4000`, timeout cleanup on unmount, `Map<id, timeoutId>` — wrapping in context is 20 lines |
| Accessibility rule engine | Custom ARIA checker | `jest-axe` (`axe-core` under the hood) | axe-core covers 57% of WCAG issues automatically; hand-rolling misses dynamic content, aria relationships, keyboard trap detection |
| Reduced motion detection | `window.matchMedia('(prefers-reduced-motion)')` directly | `useReducedMotion()` from framer-motion | Reactive — updates when OS preference changes; SSR-safe |
| Stagger timing calculation | Complex stagger logic | `Math.min(index * 0.02, 0.2)` inline | Trivially correct; the UI-SPEC defines the exact formula |

**Key insight:** Every non-trivial problem in this phase has a solution already installed. The only new dev dependency is `jest-axe`.

---

## Common Pitfalls

### Pitfall 1: `artifacts` Table Not in `supabase_realtime` Publication
**What goes wrong:** `postgres_changes` subscriptions fire but no INSERT events are ever received. Hook sits silently with `pendingCount` always 0.
**Why it happens:** `portal_schema.sql` has no `ALTER PUBLICATION supabase_realtime ADD TABLE public.artifacts` statement. The publication must be explicitly configured.
**How to avoid:** Wave 0 must include this SQL applied to project `poeyztlmsawfoqlanucc`. Verify with `SELECT tablename FROM pg_publication_tables WHERE pubname = 'supabase_realtime'`.
**Warning signs:** Subscription status reaches `'SUBSCRIBED'` but zero INSERT events received even after a CI run publishes new artifacts.

### Pitfall 2: Framer Motion `motion.div` Conflicting with Virtualizer `transform`
**What goes wrong:** Row positions are wrong — rows stack at top or are offset incorrectly. The virtualizer's `transform: translateY(Npx)` and Framer Motion's `y` animation transform conflict.
**Why it happens:** `motion.div` applied to the virtualizer's positioning wrapper (the `<div style={{ position:'absolute', transform:'translateY(...)' }}>`) means Framer Motion overrides or merges its own transform.
**How to avoid:** The virtualizer positioning wrapper `<div>` is NEVER a `motion.*` element. Animation goes on `ArtifactTableRow`'s root element only (which is already inside the wrapper). Per UI-SPEC: "Row entrance animations go on the inner ArtifactTableRow component's root element, not on the virtualizer's positioning wrapper."
**Warning signs:** Rows pile up at `y=0` on first render; table appears to have all rows stacked at the top.

### Pitfall 3: `AnimatePresence initial={false}` Scope Is Global Below the Wrapper
**What goes wrong:** `AnimatePresence initial={false}` suppresses the `initial` state for ALL `motion.*` descendants, not just direct children with `exit` props. If placed too high in the tree (e.g., around `<Routes>`), it will suppress initial animations elsewhere.
**Why it happens:** Known behavior documented in Framer Motion GitHub issue #724.
**How to avoid:** Place `AnimatePresence initial={false}` only around the `NewArtifactPill` (which needs it for its exit animation), not around the entire table body. The row entrance animation uses `initial={{ opacity: 0 }}` on each row independently — this is NOT inside an `AnimatePresence`.
**Warning signs:** Page transition animations (existing `PageTransition`) stop working; rows appear with no entrance animation.

### Pitfall 4: `useAuth` `loading` State Race on Channel Subscribe
**What goes wrong:** The hook subscribes briefly with `isBilling=false` during the auth loading phase, then immediately unsubscribes when `loading` becomes `false` and `isBilling` becomes `true`. This creates a subscribe/unsubscribe/subscribe cycle on every page load.
**Why it happens:** `useAuth` starts with `loading: true`; `isBilling` and `isAdmin` are both `false` until the session + profile are loaded.
**How to avoid:** Gate the subscription on `!loading && (isBilling || isAdmin)`:
```typescript
const { isBilling, isAdmin, loading } = useAuth();
// in useEffect dependency and guard:
if (loading || (!isBilling && !isAdmin)) return;
```
**Warning signs:** Two rapid `SUBSCRIBED` → `CLOSED` → `SUBSCRIBED` status events in console on login.

### Pitfall 5: `jest-axe` Color-Contrast Checks Are Silently Skipped in jsdom
**What goes wrong:** `toHaveNoViolations()` passes even with failing color-contrast ratios. The test gives false confidence that all WCAG AA color pairs are validated.
**Why it happens:** jsdom does not implement `document.createRange()` and `getClientRects()` fully — these are required by axe-core's color-contrast rule. axe-core automatically disables the `color-contrast` rule when these APIs are unavailable. [VERIFIED: dequelabs/axe-core issue #595]
**How to avoid:** Document this explicitly in acceptance criteria. The jest-axe regression net catches structure/ARIA violations (roles, labels, keyboard traps). Color-contrast validation (the §Accessibility Contract contrast pairs) must be done in the **manual browser walkthrough** at phase close (D-07 second pass). The contrast pairs in the UI-SPEC are already pre-validated analytically.
**Warning signs:** All `toHaveNoViolations` assertions pass — assume color-contrast was NOT checked.

### Pitfall 6: `ToastContext` Provider Placed Outside `QueryClientProvider`
**What goes wrong:** `useRealtimeArtifacts` (which needs `useQueryClient`) and `ToastContext` (which renders inside `App`) are in separate provider trees. `useQueryClient` throws "No QueryClient set" if called outside `QueryClientProvider`.
**Why it happens:** Provider ordering in `App.tsx` puts `ToastProvider` before `QueryClientProvider`.
**How to avoid:** `ToastProvider` must be INSIDE `QueryClientProvider` (D-06). The correct tree is `QueryClientProvider > ToastProvider > BrowserRouter > ErrorBoundary > AuthProvider`.
**Warning signs:** "No QueryClient set, use QueryClientProvider to set one" runtime error.

### Pitfall 7: `React.memo` Must Be at Module Level for `ArtifactCard`
**What goes wrong:** Memo is applied inside the component (e.g., as a variable inside a function), creating a new `memo`-wrapped component on every render of the parent. The memo comparison never fires and the card list re-renders fully on every parent state change.
**Why it happens:** `memo(Component)` defined inside another component's render scope creates a new component type each render, invalidating React's bail-out.
**How to avoid:** `ArtifactCard` must be exported as `export const ArtifactCard = React.memo(function ArtifactCard(...) {...})` at the module's top level — identical to the existing `ArtifactTableRow` pattern.
**Warning signs:** React DevTools shows `ArtifactCard` re-rendering on every `pendingCount` change.

---

## Code Examples

### jest-axe Setup in Existing Vitest Infrastructure

```typescript
// 1. Install:
// npm install -D jest-axe @types/jest-axe

// 2. portal-v2/src/test/setup.ts — ADD these two lines:
import '@testing-library/jest-dom';
import { toHaveNoViolations } from 'jest-axe';     // ADD
expect.extend(toHaveNoViolations);                  // ADD

// 3. portal-v2/vitest.config.ts — no changes needed (setupFiles already wired)

// 4. Sample component-level a11y test:
// portal-v2/src/components/artifacts/__tests__/ArtifactCard.a11y.test.tsx
import { render } from '@testing-library/react';
import { axe } from 'jest-axe';
import { ArtifactCard } from '../ArtifactCard';

const mockRow = {
  id: 'test-id', work_request: 'WR_12345',
  week_ending: '2025-05-26', week_ending_fmt: '052625',
  variant: 'primary', filename: 'WR_12345_WeekEnding_052625.xlsx',
  storage_path: '052625/WR_12345_WeekEnding_052625.xlsx',
  size_bytes: 204800, sha256: 'abc123', run_id: 'run-1',
  created_at: '2025-05-26T20:00:00Z',
};

it('ArtifactCard has no axe violations', async () => {
  const { container } = render(
    <ArtifactCard row={mockRow} onDownload={() => undefined} isDownloading={false} />
  );
  const results = await axe(container);
  expect(results).toHaveNoViolations();
  // NOTE: color-contrast is NOT checked by axe in jsdom — manual browser check required
});
```

[VERIFIED: jest-axe README + npm registry version 10.0.0]

### `NewArtifactPill` with `AnimatePresence`

```typescript
// Source: Framer Motion AnimatePresence docs (Context7 /grx7/framer-motion)
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

export function NewArtifactPill({ count, onLoad, onDismiss }: NewArtifactPillProps) {
  const prefersReduced = useReducedMotion();
  const label = count === 1 ? 'Load 1 new artifact' : `Load ${count} new artifacts`;

  return (
    <AnimatePresence initial={false}>
      {count > 0 && (
        <motion.div
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={prefersReduced ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }}
          className="sticky top-0 z-10 flex items-center gap-2 px-4 py-2 
                     backdrop-blur-sm bg-white/80 border border-slate-200 
                     shadow-md rounded-full sm:inline-flex
                     w-full sm:w-auto bg-brand-red sm:bg-white/80 text-white sm:text-slate-700"
        >
          <button onClick={onLoad} className="text-sm font-medium">{label}</button>
          <button
            onClick={onDismiss}
            aria-label="Dismiss new artifact notification"
            className="ml-2 text-slate-400 hover:text-slate-600"
          >
            <X size={14} />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

---

## Runtime State Inventory

> Phase 06 is a frontend-polish phase. No renames, rebrands, or data migrations are in scope. This section is included for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `supabase_realtime` publication — `artifacts` table NOT confirmed as member | SQL migration: `ALTER PUBLICATION supabase_realtime ADD TABLE public.artifacts` applied to live project `poeyztlmsawfoqlanucc` |
| Live service config | None | — |
| OS-registered state | None | — |
| Secrets/env vars | None | — |
| Build artifacts | None | — |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | npm install, vitest | ✓ | (project running) | — |
| Supabase project `poeyztlmsawfoqlanucc` | DATA-06 Realtime | ✓ | Live, 2,383 rows | — |
| `@supabase/supabase-js` | DATA-06 Realtime channel | ✓ | `^2.45.4` in pkg | — |
| `framer-motion` | UI-02 animations | ✓ | `^11.11.17` in pkg | — |
| `jest-axe` | UI-03 a11y tests (D-07) | ✗ (not yet installed) | — | No fallback; install required |
| Supabase CLI | Publication verification | ✗ | — | Verify via SQL Editor in Supabase dashboard |

**Missing dependencies with no fallback:**
- `jest-axe` — required for D-07 automated a11y regression tests. Install: `npm install -D jest-axe @types/jest-axe`

**Missing dependencies with fallback:**
- Supabase CLI — not available; publication verification done via Supabase SQL Editor instead.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest `2.1.9` |
| Config file | `portal-v2/vitest.config.ts` |
| Environment | `jsdom` (already configured) |
| Setup file | `portal-v2/src/test/setup.ts` |
| Quick run command | `npm test` (from `portal-v2/`) |
| Full suite command | `npm test` (from `portal-v2/`) — same; no separate watch mode in CI |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-06 | `useRealtimeArtifacts`: INSERT event increments `pendingCount` | unit (mock channel) | `npm test -- --reporter=verbose` | ❌ Wave 0: create `src/hooks/__tests__/useRealtimeArtifacts.test.ts` |
| DATA-06 | `clearPending` resets `pendingCount` to 0 | unit (mock channel) | same | ❌ Wave 0 |
| DATA-06 | `clearPending` calls `queryClient.invalidateQueries({ queryKey: ['artifacts'] })` | unit (mock channel + mock queryClient) | same | ❌ Wave 0 |
| DATA-06 | unmount calls `channel.unsubscribe()` | unit (mock channel) | same | ❌ Wave 0 |
| DATA-06 | `pending`/unauthenticated role does NOT open channel | unit (mock useAuth) | same | ❌ Wave 0 |
| UI-01 | `ArtifactCard` renders all required fields (WR#, week-ending, variant badge, download btn) | unit (RTL) | same | ❌ Wave 0: create `src/components/artifacts/__tests__/ArtifactCard.test.tsx` |
| UI-01 | `ArtifactCard` has no axe violations (structure/ARIA, NOT color-contrast) | a11y (jest-axe) | same | ❌ Wave 0 |
| UI-02 | `NewArtifactPill` renders with `count > 0`, absent when `count === 0` | unit (RTL) | same | ❌ Wave 0: create `src/components/artifacts/__tests__/NewArtifactPill.test.tsx` |
| UI-02 | `NewArtifactPill` has no axe violations | a11y (jest-axe) | same | ❌ Wave 0 |
| UI-03 | `ToastContext` — `addToast` called → toast appears; `removeToast` → toast disappears | unit (RTL) | same | ❌ Wave 0: create `src/contexts/__tests__/ToastContext.test.tsx` |
| UI-03 | `ToastContext` provider renders single `<ToastContainer>` (no duplicate) | unit (RTL) | same | ❌ Wave 0 |
| C-02 | `['artifact-variants']` query includes `.limit(2000)` and `staleTime: 10*60*1000` | code review / unit (mock supabase) | manual | ❌ Wave 0 (optional: snapshot test of query params) |

### Manual UAT Boundary (deferred from CI)

The following CANNOT be validated in vitest/CI and require manual verification at phase close:

| Behavior | Why Manual | Owner |
|----------|-----------|-------|
| A real CI INSERT event surfaces the pill + toast within seconds of a billing run | Requires live Supabase Realtime socket; no test doubles for WebSocket timing | Developer UAT session |
| Keyboard navigation: Tab order through table headers → filter chips → download buttons → pill → toast dismiss | Requires real browser + keyboard | Developer walkthrough |
| Screen reader announces pill `role="status"` on INSERT (aria-live="polite") | Requires NVDA/VoiceOver — jsdom does not implement ARIA live region announcement | Developer walkthrough |
| Color-contrast pairs from §Accessibility Contract (slate-500 on white = 4.6:1, white on brand-red = 5.1:1, etc.) | jsdom `color-contrast` axe rule is silently disabled | Developer browser check with axe browser extension |
| Mobile card list renders correctly at 375px viewport | jsdom has no real viewport; breakpoint behavior requires a real browser | Responsive DevTools check |
| `prefers-reduced-motion` eliminates animations | Requires OS-level setting toggle | Developer DevTools override |

### Sampling Rate

- **Per task commit:** `npm test` from `portal-v2/` — all unit + a11y vitest tests must pass
- **Per wave merge:** same — `npm test` must be green
- **Phase gate:** Full suite green + manual UAT checklist signed off before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `src/hooks/__tests__/useRealtimeArtifacts.test.ts` — covers DATA-06 mock-channel assertions (D-05)
- [ ] `src/components/artifacts/__tests__/ArtifactCard.test.tsx` — covers UI-01 rendering + jest-axe
- [ ] `src/components/artifacts/__tests__/NewArtifactPill.test.tsx` — covers UI-02 pill visibility + jest-axe
- [ ] `src/contexts/__tests__/ToastContext.test.tsx` — covers C-01 single-container assertion
- [ ] `src/test/setup.ts` — add `jest-axe` `expect.extend(toHaveNoViolations)` (2 lines)
- [ ] `npm install -D jest-axe @types/jest-axe` — install before any a11y test runs

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Express SSE poller for new-run notifications | Supabase Realtime `postgres_changes` WebSocket | Phase 06 (DATA-06) | Removes polling; push-based; RLS-enforced |
| Multiple `useToast()` instances per component | Single `ToastContext` provider + global `<ToastContainer>` | Phase 06 (C-01) | One toast region; correct z-stacking; all toasts coexist |
| No mobile layout (table-only) | Responsive swap: `<table>` at sm+, `ArtifactCard` list at <640px | Phase 06 (UI-01) | Works on phone; all 6 data fields preserved |
| No entrance animations | Framer Motion stagger (initial load only), reduced-motion respected | Phase 06 (UI-02) | Perceived performance improvement without scroll cost |

**Deprecated/outdated in this phase:**
- The `useToast()` call and `<ToastContainer>` in `ArtifactTable.tsx` (lines 41-42, 267): replaced by `useToastContext()`.
- The `useToast()` call and `<ToastContainer>` in `App.tsx` (lines 35, 81): replaced by `ToastProvider`.

---

## Security Domain

> `security_enforcement` is not explicitly disabled in config. Including this section.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (Phase 04 complete) | — |
| V3 Session Management | no (Phase 04 complete) | — |
| V4 Access Control | **yes — Realtime gate** | `useAuth`/`isBilling`/`isAdmin` client gate + RLS server gate; `pending`/anon never subscribe |
| V5 Input Validation | no (Phase 06 adds no new inputs) | — |
| V6 Cryptography | no | — |

### Known Threat Patterns for Supabase Realtime

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized Realtime subscription by `pending` user | Information Disclosure | Client-side gate (`!isBilling && !isAdmin` → no subscribe) + RLS server-side filter (zero payload delivered) |
| Row data leaking through `pendingCount` payload | Information Disclosure | `_payload` argument is received but NEVER stored; only `n + 1` integer enters state |
| JWT expiry causing stale auth on channel | Elevation of Privilege | `supabase-js` auto-propagates `TOKEN_REFRESHED` via `realtime.setAuth()`; RLS re-evaluated on token refresh |
| `supabase_realtime` publication exposing unintended tables | Information Disclosure | Publication is table-specific; only `ALTER PUBLICATION supabase_realtime ADD TABLE public.artifacts` — no wildcard |

**Phase 07 audit note:** The D-04 defense-in-depth design (client gate + count-only + RLS) is deliberately constructed to leave nothing for the Phase 07 audit to find in the Realtime surface. The Phase 07 audit will still need to verify (1) the publication is scoped only to `artifacts` (not `profiles`), and (2) the `anon` role has no SELECT grant on `artifacts` outside RLS (it inherits `TO authenticated` scoping — anon is not `authenticated`).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Mobile card list with 75-row initial page does not need separate virtualization | §Pattern 4 (Responsive) | If users scroll fast on mobile and trigger many page loads, 200+ unmemoized `ArtifactCard` renders could cause jank. Mitigation: `React.memo` is required; monitor during UAT. |
| A2 | `artifacts` table is NOT currently in the `supabase_realtime` publication | §Runtime State Inventory | If it IS already in the publication, no SQL migration needed (harmless no-op to add again). Run verification SQL before Wave 1 to confirm. |
| A3 | `framer-motion` v11.x `motion.div` on `ArtifactTableRow`'s root `<div>` does not conflict with the virtualizer's absolute positioning | §Pattern 3 (Row stagger) | If Framer Motion's internal transform merging interferes with `translateY`, rows will be mispositioned. Mitigation: use only `opacity` animation (not `y`) so no transform is applied. |
| A4 | C-02 `.limit(2000)` captures all distinct variant values for the current and near-future dataset | §Pattern 5 (C-02) | If the dataset grows past 2,000 rows with new variant types only appearing beyond row 2,000, some variants would be missing from the filter bar. Acceptable for Phase 06; Phase 07 should add `SELECT DISTINCT variant`. |

---

## Open Questions

1. **Is `artifacts` already in the `supabase_realtime` publication on `poeyztlmsawfoqlanucc`?**
   - What we know: `portal_schema.sql` has no `ALTER PUBLICATION` statement. The Supabase dashboard allows toggling this via Settings → Replication.
   - What's unclear: Whether the publication was enabled manually via the dashboard (outside of SQL files tracked in git).
   - Recommendation: Wave 0 executor runs `SELECT tablename FROM pg_publication_tables WHERE pubname = 'supabase_realtime'` in the SQL Editor before applying the migration.

2. **`framer-motion` v11 vs. v12 breaking changes**
   - What we know: Project pins `^11.11.17`; npm latest is `12.40.0`.
   - What's unclear: Whether any Phase 06 animation patterns require v12 APIs.
   - Recommendation: All patterns specified in this research use the v11 API (`motion.div`, `AnimatePresence`, `useReducedMotion`). Do NOT upgrade to v12 in this phase.

3. **Should `useRealtimeArtifacts` call `addToast` internally or delegate to the caller?**
   - What we know: The UI-SPEC §Component Inventory says "On INSERT: increments `pendingCount`" — toast is triggered separately in `ArtifactTable`.
   - Recommendation: The hook returns `{ pendingCount, clearPending }` only. The `ArtifactTable` (which has `useToastContext()` access) calls `addToast` in a `useEffect` watching `pendingCount`. This keeps `useRealtimeArtifacts` testable in isolation without a `ToastProvider` wrapper.

---

## Sources

### Primary (HIGH confidence)

- Context7 `/supabase/supabase-js` — `postgres_changes` channel wiring, JWT auto-propagation via `_handleTokenChanged`, subscribe/unsubscribe lifecycle
- Context7 `/supabase/realtime` — `ALTER PUBLICATION supabase_realtime ADD TABLE` SQL, RLS column-level filtering via `has_column_privilege`, `postgres_cdc_rls` model
- Context7 `/grx7/framer-motion` — `AnimatePresence initial={false}`, `staggerChildren` vs per-item `delay`, `useReducedMotion` hook implementation
- npm registry — `jest-axe@10.0.0`, `framer-motion@12.40.0` (confirmed 11.x is installed), `@supabase/supabase-js@2.107.0` (project pins 2.45.4, compatible)
- `portal_schema.sql` — confirmed RLS policy `artifacts_select_billing_or_admin`, confirmed NO `ALTER PUBLICATION` statement
- `portal-v2/src/App.tsx` — confirmed dual toast bug (lines 35+81 vs ArtifactTable line 267), confirmed existing provider nesting order
- `portal-v2/src/components/artifacts/ArtifactTableRow.tsx` — confirmed `React.memo` at module level pattern, confirmed `role="row"` root `<div>` is the animation target
- `portal-v2/vitest.config.ts` + `src/test/setup.ts` — confirmed `jsdom` environment, confirmed `setupFiles` path for jest-axe injection

### Secondary (MEDIUM confidence)

- [Supabase Realtime Postgres Changes docs](https://supabase.com/docs/guides/realtime/postgres-changes) — WebSearch verified: "database records are sent only to clients who are allowed to read them based on your RLS policies"
- [Supabase Realtime Authorization docs](https://supabase.com/docs/guides/realtime/authorization) — WebSearch verified: "Postgres Changes already adheres to RLS policies on the tables you're listening to" (private channel concept applies to Broadcast/Presence only, not postgres_changes)
- [dequelabs/axe-core issue #595](https://github.com/dequelabs/axe-core/issues/595) — confirmed color-contrast rule is silently disabled in jsdom environments

### Tertiary (LOW confidence — assumptions flagged)

- Mobile card list performance without virtualization (A1 in Assumptions Log) — based on 75-row page size and `React.memo`; needs UAT validation
- `framer-motion` `opacity`-only animation not conflicting with virtualizer `translateY` (A3) — pattern is consistent with official docs but not explicitly tested in this codebase

---

## Metadata

**Confidence breakdown:**
- Realtime RLS authorization model: HIGH — verified via Context7 source + official docs + WebSearch cross-reference
- supabase-js channel wiring: HIGH — verified via Context7 /supabase/supabase-js source
- Framer Motion stagger pattern: HIGH — verified via Context7 /grx7/framer-motion; per-row `delay` approach confirmed correct for virtualized lists
- jest-axe vitest wiring: HIGH — verified via npm registry + official README
- jsdom color-contrast limitation: HIGH — confirmed via axe-core issue tracker
- Package versions: HIGH — verified via npm registry 2026-06-02
- Publication state on live project: LOW — not verified live (Supabase CLI unavailable; requires SQL Editor check)

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (stable libraries; Supabase Realtime auth model unlikely to change; framer-motion v11 API is frozen)
