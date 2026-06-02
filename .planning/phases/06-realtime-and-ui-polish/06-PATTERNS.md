# Phase 06: Realtime and UI Polish — Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 10 (4 CREATE, 6 MODIFY)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/contexts/ToastContext.tsx` | provider/context | event-driven | `src/hooks/useAuth.ts` (AuthContext + AuthProvider pattern) | exact |
| `src/hooks/useRealtimeArtifacts.ts` | hook | event-driven | `src/hooks/useArtifactsInfinite.ts` (supabase client, queryClient.invalidateQueries, `['artifacts']` key) | role-match |
| `src/components/artifacts/NewArtifactPill.tsx` | component | event-driven | `src/components/ui/Toast.tsx` (AnimatePresence + motion.div, lucide X icon, aria-live) | role-match |
| `src/components/artifacts/ArtifactCard.tsx` | component | request-response | `src/components/artifacts/ArtifactTableRow.tsx` (fields/columns) + `src/components/ui/GlassCard.tsx` (container) + `src/components/ui/Badge.tsx` (variant display) | exact (composite) |
| `src/components/artifacts/ArtifactTable.tsx` | component | request-response | self (MODIFY — remove local toast stack, add responsive swap, wire stagger prop) | self |
| `src/components/artifacts/ArtifactTableRow.tsx` | component | request-response | self (MODIFY — wrap root in motion.div, accept staggerDelay prop) | self |
| `src/hooks/useArtifactsInfinite.ts` (C-02 fix) | hook | CRUD | self (MODIFY — add .limit(2000) + staleTime to variants query in ArtifactTable) | self |
| `src/App.tsx` | config/entry | request-response | self (MODIFY — mount ToastProvider, remove duplicate useToast/ToastContainer) | self |
| `src/test/setup.ts` | test | — | self (MODIFY — add jest-axe expect.extend) | self |
| `src/hooks/useDownloadArtifact.ts` | hook | request-response | self (MODIFY — no signature change; caller sources addToast from context) | self |

---

## Pattern Assignments

### `src/contexts/ToastContext.tsx` (CREATE — provider, event-driven)

**Analog:** `src/hooks/useAuth.ts`

The AuthContext pattern is the direct structural template: `createContext<T | null>(null)`, a provider function that calls an existing hook and wraps children, and a consuming hook that throws when called outside the provider. `ToastContext` replicates this pattern exactly — wrapping `useToast()` instead of `useAuthState()`.

**Imports pattern to copy** (`useAuth.ts` lines 1–4, adapted):
```typescript
import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { useToast } from '../hooks/useToast';
import { ToastContainer } from '../components/ui/Toast';
import type { ToastType } from '../lib/types';
```

**Context + interface pattern** (`useAuth.ts` lines 6–22, adapted):
```typescript
interface ToastContextValue {
  toasts: ReturnType<typeof useToast>['toasts'];
  addToast: (type: ToastType, message: string) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);
```
Note: `createContext<T | null>(null)` — matches `AuthContext` at line 21. Never `undefined` as the default value (project prefers `undefined` over `null` for values, but `null` is the established sentinel for "no provider" in this codebase's context pattern).

**Provider function pattern** (`App.tsx` lines 29–32, adapted — `AuthProvider` is the template):
```typescript
export function ToastProvider({ children }: { children: ReactNode }) {
  const { toasts, addToast, removeToast } = useToast();
  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}
```
`AuthProvider` (`App.tsx` lines 29–32) is exactly `const auth = useAuthState(); return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>`. `ToastProvider` extends the same pattern by also rendering the single global `<ToastContainer>` inside the provider.

**Consumer hook pattern** (`useAuth.ts` lines 138–142, verbatim structure):
```typescript
export function useToastContext(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToastContext must be used within ToastProvider');
  return ctx;
}
```
Matches `useAuth()` exactly: `const ctx = useContext(AuthContext); if (!ctx) throw new Error(...); return ctx;`

**Mount point in `App.tsx`** (MODIFY — lines 38–41 of current `App.tsx`):
```typescript
// BEFORE (App.tsx lines 35, 81 — DELETE both):
// const { toasts, removeToast } = useToast();   // line 35
// <ToastContainer toasts={toasts} onRemove={removeToast} />  // line 81

// AFTER — ToastProvider wraps inside QueryClientProvider, before BrowserRouter:
<QueryClientProvider client={queryClient}>
  <ToastProvider>
    <BrowserRouter>
      <ErrorBoundary>
        <AuthProvider>
          {/* routes unchanged */}
        </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  </ToastProvider>
</QueryClientProvider>
```
Also delete the `import { useToast } from './hooks/useToast'` and `import { ToastContainer } from './components/ui/Toast'` lines from `App.tsx` (lines 15–17) once replaced by `import { ToastProvider } from './contexts/ToastContext'`.

---

### `src/hooks/useRealtimeArtifacts.ts` (CREATE — hook, event-driven)

**Analog:** `src/hooks/useArtifactsInfinite.ts`

Shares: supabase client import path, `useQueryClient` + `queryClient.invalidateQueries({ queryKey: ['artifacts'] })` pattern, `useCallback` wrapper. Extends with: Supabase channel subscription, `useEffect` cleanup, `useRef` for channel handle, `useAuth` gate.

**Imports pattern** (`useArtifactsInfinite.ts` lines 1–4, adapted):
```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { supabase } from '../lib/supabase';
import { useAuth } from './useAuth';
```
Note: `supabase` import path is `'../lib/supabase'` — same as `useArtifactsInfinite.ts` line 2.

**queryClient invalidation pattern** (`useArtifactsInfinite.ts` queryKey at line 22–27, adapted):
```typescript
const clearPending = useCallback(() => {
  setPendingCount(0);
  void queryClient.invalidateQueries({ queryKey: ['artifacts'] });
}, [queryClient]);
```
The `['artifacts']` key exactly matches the `queryKey` array root in `useArtifactsInfinite.ts` line 22. `void` prefix for fire-and-forget promise — consistent with `useArtifactsInfinite.ts` line 62 `void q.fetchNextPage()` pattern in `ArtifactTable.tsx`.

**Channel subscription + cleanup pattern** (no analog in codebase — use RESEARCH.md Pattern 1 verbatim):
```typescript
const channelRef = useRef<ReturnType<typeof supabase.channel> | undefined>(undefined);

useEffect(() => {
  // D-04: gate on !loading to avoid subscribe/unsubscribe cycle on auth init
  if (loading || (!isBilling && !isAdmin)) return;

  const channel = supabase
    .channel('artifacts')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'artifacts' },
      (_payload) => {
        // Count-only — _payload data NEVER enters state (D-04)
        setPendingCount((n) => n + 1);
      }
    )
    .subscribe();

  channelRef.current = channel;

  return () => {
    void channel.unsubscribe();
  };
}, [isBilling, isAdmin, loading]);
```
`useRef` pattern for cleanup reference matches `useToast.ts` lines 9–11 (`timeoutsRef`). `useEffect` cleanup with `void asyncCall()` matches `useAuth.ts` line 77 (`return () => listener.subscription.unsubscribe()`).

**Return shape:**
```typescript
return { pendingCount, clearPending };
// Never return addToast — hook is pure data (RESEARCH.md Open Question 3)
// ArtifactTable watches pendingCount in a useEffect and calls addToast there
```

**Auth fields to destructure from useAuth:**
```typescript
const { isBilling, isAdmin, loading } = useAuth();
// loading field confirmed present at useAuth.ts line 10 and returned at line 131
```

---

### `src/components/artifacts/NewArtifactPill.tsx` (CREATE — component, event-driven)

**Analog:** `src/components/ui/Toast.tsx`

Shares: `AnimatePresence` wrapping a conditional `motion.div`, `framer-motion` spring/ease transitions, lucide `X` icon for dismiss, `aria-label` on dismiss button, `cn()` utility for class composition.

**Imports pattern** (`Toast.tsx` lines 1–4, adapted):
```typescript
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';
```

**AnimatePresence + conditional motion.div pattern** (`Toast.tsx` lines 32–50, adapted):
```typescript
// Toast.tsx uses AnimatePresence initial={false} at line 32 — copy this
<AnimatePresence initial={false}>
  {count > 0 && (
    <motion.div
      role="status"
      aria-live="polite"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={
        prefersReduced
          ? { duration: 0 }
          : { duration: 0.2, ease: 'easeOut' }
      }
      className={cn(
        'sticky top-0 z-10 flex items-center gap-2 px-4 py-2',
        'backdrop-blur-sm bg-white/80 border border-slate-200 shadow-md rounded-full',
        'sm:inline-flex w-full sm:w-auto',
        // Mobile: brand-red banner; desktop: glass pill
        'bg-brand-red text-white sm:bg-white/80 sm:text-slate-700'
      )}
    >
      {/* ... buttons ... */}
    </motion.div>
  )}
</AnimatePresence>
```

**Dismiss button pattern** (`Toast.tsx` lines 61–67, adapted):
```typescript
<button
  onClick={onDismiss}
  aria-label="Dismiss new artifact notification"
  className="shrink-0 text-slate-400 hover:text-slate-600 transition-colors sm:text-slate-400 text-white/80 hover:text-white"
>
  <X size={14} />
</button>
```
The dismiss button in `Toast.tsx` line 61–67 uses `aria-label="Dismiss"` + `X` icon — extend the same pattern with the pill-specific label from the Copywriting Contract.

**Copywriting** (UI-SPEC §Copywriting Contract):
- 1 new: `"Load 1 new artifact"` — `count === 1`
- N new: `` `Load ${count} new artifacts` `` — `count > 1`
- Dismiss: `aria-label="Dismiss new artifact notification"`

**Props interface:**
```typescript
interface NewArtifactPillProps {
  count: number;
  onLoad: () => void;
  onDismiss: () => void;
}
```

**`useReducedMotion` pattern** (no existing usage in codebase — use RESEARCH.md Pattern 3):
```typescript
const prefersReduced = useReducedMotion();
// Then in transition: prefersReduced ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }
```

---

### `src/components/artifacts/ArtifactCard.tsx` (CREATE — component, request-response)

**Analog (fields/data):** `src/components/artifacts/ArtifactTableRow.tsx`
**Analog (container):** `src/components/ui/GlassCard.tsx`
**Analog (variant display):** `src/components/ui/Badge.tsx`

`ArtifactCard` is the mobile equivalent of `ArtifactTableRow` — same 6 fields, same data types, same `BillingArtifact` row shape, same download callback signature. Container is L1 glass (NOT full GlassCard backdrop-blur — use `bg-white rounded-2xl border border-slate-100 shadow-sm` directly).

**Imports pattern** (`ArtifactTableRow.tsx` lines 1–6, adapted):
```typescript
import React from 'react';
import { Download, Loader2 } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { getVariantLabel } from '../../lib/variantLabels';
import { formatSize, formatDate } from '../../lib/utils';
import type { BillingArtifact } from '../../lib/types';
```
All imports identical to `ArtifactTableRow.tsx`. `formatSize` and `formatDate` are in `../../lib/utils` (confirmed used in `ArtifactTableRow.tsx` lines 5–6).

**React.memo at module level** (`ArtifactTableRow.tsx` lines 19–23, verbatim pattern):
```typescript
export const ArtifactCard = React.memo(function ArtifactCard({
  row,
  onDownload,
  isDownloading,
}: ArtifactCardProps) {
  // ...
});
```
This is the exact pattern from `ArtifactTableRow.tsx` line 19. `React.memo` MUST be at module level — never inside a render function.

**Props interface** (mirrors `ArtifactTableRowProps` at `ArtifactTableRow.tsx` lines 8–12):
```typescript
interface ArtifactCardProps {
  row: BillingArtifact;
  onDownload: (rowId: string, storagePath: string, filename: string) => void;
  isDownloading: boolean;
}
```
Identical signature to `ArtifactTableRow` — `ArtifactTable` can pass the same props to both.

**week_ending_fmt display pattern** (`ArtifactTableRow.tsx` lines 26–29, verbatim):
```typescript
const weekDisplay =
  row.week_ending_fmt.length === 6
    ? `${row.week_ending_fmt.slice(0, 2)}/${row.week_ending_fmt.slice(2, 4)}/${row.week_ending_fmt.slice(4, 6)}`
    : row.week_ending_fmt;
```
Copy this exactly — never use `row.week_ending` (ISO) in display cells.

**Card shell** (L1 styling — NOT the full GlassCard `backdrop-blur-xl`; use the `ArtifactTable.tsx` line 211 card shell pattern):
```typescript
<div
  role="listitem"
  className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 space-y-2"
>
```

**Variant badge** (`ArtifactTableRow.tsx` line 49, verbatim):
```typescript
<Badge>{getVariantLabel(row.variant)}</Badge>
```

**Download button** (`ArtifactTableRow.tsx` lines 63–75, adapted for mobile with 44px touch target):
```typescript
<button
  onClick={() => onDownload(row.id, row.storage_path, row.filename)}
  disabled={isDownloading}
  aria-label={isDownloading ? `Downloading ${row.filename}` : `Download ${row.filename}`}
  className="inline-flex items-center gap-1.5 min-h-[44px] py-3 px-4 rounded-lg
             bg-brand-red text-white text-sm font-medium
             disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
>
  {isDownloading ? (
    <Loader2 size={14} className="animate-spin" />
  ) : (
    <Download size={14} />
  )}
</button>
```
`min-h-[44px]` is the WCAG 2.5.5 touch-target floor from UI-SPEC §Spacing Scale. `aria-label` copy matches UI-SPEC §Copywriting Contract.

**Color contract:** `text-slate-500` for meta text (NOT `text-slate-400` — WCAG AA upgrade, UI-SPEC §Accessibility Contract).

---

### `src/components/artifacts/ArtifactTable.tsx` (MODIFY)

**Analog:** self — surgical modifications only.

**Change 1: Remove local toast stack (C-01/D-06)**

Delete lines 14–15:
```typescript
// DELETE:
import { useToast } from '../../hooks/useToast';
import { ToastContainer } from '../ui/Toast';
```

Add import:
```typescript
import { useToastContext } from '../../contexts/ToastContext';
```

Replace line 41:
```typescript
// DELETE line 41:
const { toasts, addToast, removeToast } = useToast();
// ADD:
const { addToast } = useToastContext();
```

Delete line 266:
```typescript
// DELETE (the local ToastContainer):
<ToastContainer toasts={toasts} onRemove={removeToast} />
```

**Change 2: C-02 variant query fix (D-08)**

Lines 67–76 current:
```typescript
const { data: variantOptionsData } = useQuery({
  queryKey: ['artifact-variants'],
  queryFn: async () => {
    const { data, error } = await supabase
      .from('artifacts')
      .select('variant');   // ← unbounded
    if (error) throw error;
    return Array.from(new Set((data ?? []).map((r: { variant: string }) => r.variant)));
  },
});
```

Replace with:
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
  staleTime: 10 * 60 * 1000, // C-02: 10-min staleTime
});
```

**Change 3: Add initialLoadComplete stagger gate**

After the `allRows` derivation (after line 63), add:
```typescript
const [initialLoadComplete, setInitialLoadComplete] = useState(false);

useEffect(() => {
  if (q.status === 'success' && allRows.length > 0 && !initialLoadComplete) {
    setInitialLoadComplete(true);
  }
}, [q.status, allRows.length, initialLoadComplete]);
```

**Change 4: Pass staggerDelay to ArtifactTableRow** (inside `virtualItems.map`):
```typescript
const staggerDelay = !initialLoadComplete
  ? Math.min(virtualRow.index * 0.02, 0.2)
  : 0;

<ArtifactTableRow
  row={row}
  onDownload={download}
  isDownloading={downloading === row.id}
  staggerDelay={staggerDelay}   // NEW prop
/>
```

**Change 5: Responsive swap + ArtifactCard list**

Wrap the existing `<div className="bg-white rounded-2xl ...">` card in `hidden sm:block`:
```typescript
{/* Desktop/tablet: virtualized table (sm+) */}
<div className="hidden sm:block">
  <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
    {/* header + renderBody() unchanged */}
  </div>
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

**Change 6: Mount NewArtifactPill + wire pendingCount toast**

Add `useRealtimeArtifacts` call and toast effect after the `useDownloadArtifact` call:
```typescript
const { pendingCount, clearPending } = useRealtimeArtifacts();

// Toast on new artifact arrival — hook is pure data; toast fires from component
useEffect(() => {
  if (pendingCount > 0) {
    const label = pendingCount === 1
      ? '1 new artifact'
      : `${pendingCount} new artifacts`;
    addToast('info', label);
  }
}, [pendingCount]); // intentionally exclude addToast (stable ref from context)
```

Place `<NewArtifactPill>` just above the responsive swap section:
```typescript
<NewArtifactPill
  count={pendingCount}
  onLoad={clearPending}
  onDismiss={() => { /* reset pill without refetch */ }}
/>
```
`onDismiss` resets the pill without triggering `clearPending` (no refetch). Implement with a separate `dismissPill` callback that calls `setPendingCount(0)` — or expose a `dismissPending` from the hook.

---

### `src/components/artifacts/ArtifactTableRow.tsx` (MODIFY)

**Analog:** self — add `motion.div` wrapper + `staggerDelay` prop.

**Add imports** (after existing line 1):
```typescript
import { motion, useReducedMotion } from 'framer-motion';
```

**Extend props interface** (after `isDownloading: boolean;` at line 11):
```typescript
staggerDelay: number;   // 0 after initial load; index * 0.02 capped at 0.2 on initial load
```

**Wrap root `<div>` in `motion.div`** — current `ArtifactTableRow.tsx` line 31 root:
```typescript
// BEFORE (line 31):
<div
  role="row"
  className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_auto] ..."
>

// AFTER — change tag to motion.div, add animation props:
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
    {/* cells unchanged — lines 36–77 */}
  </motion.div>
);
```
**Critical:** Only `opacity` is animated — no `y` or `x` transforms. This prevents any conflict with the virtualizer's `transform: translateY(Npx)` on the outer positioning wrapper (RESEARCH.md Pitfall 2, Assumption A3). The outer positioning `<div>` in `ArtifactTable.tsx` (lines 166–175) is NEVER changed to `motion.div`.

**Upgrade `text-slate-400` to `text-slate-500`** (line 57 — Created cell):
```typescript
// BEFORE line 57:
className="px-5 py-3 text-xs text-slate-400 truncate"
// AFTER (WCAG AA upgrade — UI-SPEC §Accessibility Contract):
className="px-5 py-3 text-xs text-slate-500 truncate"
```

---

### `src/test/setup.ts` (MODIFY)

**Analog:** self — add 2 lines.

**Current file** (line 1 only):
```typescript
import '@testing-library/jest-dom';
```

**After modification:**
```typescript
import '@testing-library/jest-dom';
import { toHaveNoViolations } from 'jest-axe';   // ADD — D-07
expect.extend(toHaveNoViolations);               // ADD — D-07
```
`jest-axe` must be installed first: `npm install -D jest-axe @types/jest-axe` (from `portal-v2/`).

---

### `src/hooks/useDownloadArtifact.ts` (MODIFY — caller change only)

**Analog:** self — the hook signature is unchanged. Only `ArtifactTable.tsx` changes where it sources `addToast` from.

The hook's public API is:
```typescript
// useDownloadArtifact.ts lines 8–10 — UNCHANGED:
export function useDownloadArtifact(
  addToast: (type: ToastType, message: string) => void
) {
```
The `addToast` parameter is still threaded in from the caller (`ArtifactTable`). No modification to this file is needed. The only change is in `ArtifactTable.tsx`: `addToast` now comes from `useToastContext()` instead of a local `useToast()`.

---

## Shared Patterns

### Context Creation Pattern
**Source:** `src/hooks/useAuth.ts` lines 21–22, 138–142
**Apply to:** `src/contexts/ToastContext.tsx`
```typescript
// Null-initialized context — the established sentinel for "no provider" in this codebase
export const SomeContext = createContext<SomeContextValue | null>(null);

// Consumer hook with guard
export function useSomeContext(): SomeContextValue {
  const ctx = useContext(SomeContext);
  if (!ctx) throw new Error('useSomeContext must be used within SomeProvider');
  return ctx;
}
```

### Provider Function Pattern
**Source:** `src/App.tsx` lines 29–32 (`AuthProvider`)
**Apply to:** `src/contexts/ToastContext.tsx` (`ToastProvider`)
```typescript
function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuthState();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}
```
`ToastProvider` follows the same shape: call the existing hook, provide the value, render children + any singleton UI (the `<ToastContainer>`).

### React.memo at Module Level
**Source:** `src/components/artifacts/ArtifactTableRow.tsx` lines 19–23
**Apply to:** `src/components/artifacts/ArtifactCard.tsx`
```typescript
export const ComponentName = React.memo(function ComponentName({ ...props }: Props) {
  // ...
});
```
NEVER wrap `memo()` inside another component's render scope.

### AnimatePresence + motion.div Conditional Pattern
**Source:** `src/components/ui/Toast.tsx` lines 32–50
**Apply to:** `src/components/artifacts/NewArtifactPill.tsx`
```typescript
<AnimatePresence initial={false}>
  {condition && (
    <motion.div
      initial={{ /* enter from */ }}
      animate={{ /* target */ }}
      exit={{ /* leave to */ }}
      transition={prefersReduced ? { duration: 0 } : { ... }}
    >
      {/* content */}
    </motion.div>
  )}
</AnimatePresence>
```
`initial={false}` on `AnimatePresence` prevents the enter animation from firing on first render if the element is already present (e.g., hot reload). Scope `AnimatePresence` tightly — do NOT place it around the whole table body.

### void + async fire-and-forget
**Source:** `src/components/artifacts/ArtifactTable.tsx` line 116 (`void q.fetchNextPage()`)
**Apply to:** `src/hooks/useRealtimeArtifacts.ts` (`void channel.unsubscribe()`, `void queryClient.invalidateQueries(...)`)
```typescript
// Suppress floating promise lint errors on intentional fire-and-forget:
void someAsyncFunction();
```

### Supabase Client Import Path
**Source:** `src/hooks/useArtifactsInfinite.ts` line 2
**Apply to:** `src/hooks/useRealtimeArtifacts.ts`
```typescript
import { supabase } from '../lib/supabase';
```

### cn() Utility for Conditional Classes
**Source:** `src/components/ui/Badge.tsx` line 1, `src/components/ui/Toast.tsx` line 4
**Apply to:** `src/components/artifacts/NewArtifactPill.tsx`, `src/components/artifacts/ArtifactCard.tsx`
```typescript
import { cn } from '../../lib/utils';
// Usage: className={cn('base classes', conditional && 'extra classes')}
```

### Error Handling in Async Hooks
**Source:** `src/hooks/useDownloadArtifact.ts` lines 33–35
**Apply to:** Any new async operation in hooks
```typescript
} catch (err) {
  addToast('error', err instanceof Error ? err.message : 'Fallback message');
}
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/hooks/useRealtimeArtifacts.ts` (Realtime channel wiring) | hook | event-driven | No existing Supabase Realtime channel usage in the codebase. Channel subscription + `postgres_changes` wiring has no analog — use RESEARCH.md Pattern 1 verbatim. |

---

## Key Constraints Extracted from Analog Reading

1. **`ArtifactTable.tsx` line 266** is the exact `<ToastContainer>` to delete (C-01).
2. **`ArtifactTable.tsx` lines 41–42** are the exact `useToast()` + `useDownloadArtifact(addToast)` lines to replace with `useToastContext()`.
3. **`ArtifactTable.tsx` lines 67–76** are the exact variant query block to patch (C-02).
4. **`ArtifactTableRow.tsx` line 31** is the exact root `<div>` to promote to `motion.div`.
5. **`ArtifactTableRow.tsx` line 57** is the `text-slate-400` to upgrade to `text-slate-500`.
6. **`App.tsx` lines 15–17** contain the imports to replace; **line 35** is the `useToast()` call to delete; **line 81** is the `<ToastContainer>` to delete.
7. **`App.tsx` line 38** (`<QueryClientProvider>`) is the mount point — `<ToastProvider>` nests immediately inside it.
8. **`src/test/setup.ts`** is currently 1 line — append 2 lines for jest-axe.
9. **`useDownloadArtifact.ts`** signature is unchanged — no modification to this file needed.

---

## Metadata

**Analog search scope:** `portal-v2/src/` (hooks, components/artifacts, components/ui, contexts, test)
**Files read:** 12 (useAuth.ts, useArtifactsInfinite.ts, useToast.ts, useDownloadArtifact.ts, ArtifactTableRow.tsx, ArtifactTable.tsx, Toast.tsx, Badge.tsx, GlassCard.tsx, App.tsx, test/setup.ts, plus 3 planning docs)
**Pattern extraction date:** 2026-06-02
