---
phase: 06-realtime-and-ui-polish
plan: "02"
subsystem: portal-v2/contexts
tags: [toast, context, react, ui-polish, c-01, c-02]
dependency_graph:
  requires:
    - portal-v2/src/hooks/useToast.ts
    - portal-v2/src/components/ui/Toast.tsx
    - portal-v2/src/lib/types.ts (ToastType)
  provides:
    - portal-v2/src/contexts/ToastContext.tsx
  affects:
    - portal-v2/src/App.tsx
    - portal-v2/src/components/artifacts/ArtifactTable.tsx
tech_stack:
  added:
    - React Context API (createContext / useContext) for global toast state
  patterns:
    - AuthContext null-sentinel pattern mirrored in ToastContext
    - Single-provider singleton UI (ToastContainer inside provider, not at root)
    - useToastContext() consumer guard (throws outside provider)
key_files:
  created:
    - portal-v2/src/contexts/ToastContext.tsx
    - portal-v2/src/contexts/__tests__/ToastContext.test.tsx
  modified:
    - portal-v2/src/App.tsx
    - portal-v2/src/components/artifacts/ArtifactTable.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx
decisions:
  - "C-01: Single global ToastContainer lives inside ToastProvider — never at root App level"
  - "ToastProvider nests inside QueryClientProvider so Plan 03 useQueryClient resolves"
  - "useToastContext() uses null sentinel (not undefined) matching AuthContext established pattern"
  - "C-02: .limit(2000) + staleTime 10min on ['artifact-variants'] query bounds DoS surface T-06-05"
metrics:
  duration: "~12 minutes"
  completed_date: "2026-06-02"
  tasks_completed: 3
  files_changed: 5
---

# Phase 06 Plan 02: Toast Context + Variant Query Cap Summary

Single global toast stack via `ToastContext` (C-01 / D-06) built on the existing `useToast` + `ToastContainer` primitives; variant query bounded with `.limit(2000)` and 10-min `staleTime` (C-02 / D-08).

## What Was Built

### Task 1: ToastContext provider + consumer hook (TDD)

Created `portal-v2/src/contexts/ToastContext.tsx` following the `AuthContext` null-sentinel pattern:

- `ToastProvider` wraps `useToast()` and renders the single global `<ToastContainer>` inside the provider tree
- `useToastContext()` consumer hook throws `"useToastContext must be used within ToastProvider"` when called outside the provider
- Context initialized with `createContext<ToastContextValue | null>(null)` — the established "no provider" sentinel in this codebase

Tests (`src/contexts/__tests__/ToastContext.test.tsx`, 4 tests):
1. `addToast('info', 'hello world')` makes message appear in rendered output
2. `removeToast(id)` removes toast from the context `toasts` array (verified via counter, not animated DOM — framer-motion exit animations don't complete in jsdom)
3. Exactly ONE `.fixed.bottom-6.right-6.z-50` container renders (C-01 single-stack guarantee)
4. `useToastContext()` outside `<ToastProvider>` throws the expected error

### Task 2: Rewire App.tsx + remove ArtifactTable local stack

**App.tsx:**
- Removed `import { ToastContainer }` and `import { useToast }`
- Added `import { ToastProvider } from './contexts/ToastContext'`
- Removed `const { toasts, removeToast } = useToast()` from component body
- Wrapped tree: `<QueryClientProvider> → <ToastProvider> → <BrowserRouter> → ...`
- Removed standalone `<ToastContainer toasts={toasts} onRemove={removeToast} />`

**ArtifactTable.tsx:**
- Removed `import { useToast }` and `import { ToastContainer }`
- Added `import { useToastContext } from '../../contexts/ToastContext'`
- Replaced `const { toasts, addToast, removeToast } = useToast()` with `const { addToast } = useToastContext()`
- Removed local `<ToastContainer toasts={toasts} onRemove={removeToast} />` (the C-01 duplicate)
- `useDownloadArtifact(addToast)` call unchanged — `addToast` still threaded in, just sourced from context

### Task 3: C-02 variant query cap

In `ArtifactTable.tsx`, patched the `['artifact-variants']` query:
- Added `.limit(2000)` to the Supabase `.select('variant')` chain
- Added `staleTime: 10 * 60 * 1000` to useQuery options
- `queryKey`, dedup `Array.from(new Set(...))` logic, and `variantOptions` usage unchanged

Closes threat T-06-05 (DoS via unbounded full-table scan on `artifacts.variant` column).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ArtifactTable.test.tsx broke after C-01 context migration**

- **Found during:** Post-Task-2 full test run (`npm test`)
- **Issue:** Existing `ArtifactTable.test.tsx` rendered `<ArtifactTable />` bare — once `useToast()` was replaced by `useToastContext()`, the 4 existing tests threw `"useToastContext must be used within ToastProvider"` and failed
- **Fix:** Added `renderWithToast()` helper wrapping renders in `<ToastProvider>`, replaced all 4 bare `render(<ArtifactTable />)` calls
- **Files modified:** `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx`
- **Commit:** `d024c14`

**2. [Rule 1 - Bug] Test 2 (removeToast) initially queried framer-motion animated text**

- **Found during:** Task 1 TDD GREEN phase
- **Issue:** `expect(screen.queryByText('to be removed')).not.toBeInTheDocument()` failed because `AnimatePresence` exit animation in `ToastContainer` keeps the `<p>` in the DOM after state removal in jsdom
- **Fix:** Changed Test 2 to verify the `toasts` array state via a `data-testid="toast-count"` counter rendered by the consumer, not the animated `<p>` in `ToastContainer`
- **Files modified:** `portal-v2/src/contexts/__tests__/ToastContext.test.tsx`
- **Commit:** part of `2272e55`

## Known Stubs

None — all wiring is complete. `addToast` flows from `ToastContext` through `ArtifactTable` to `useDownloadArtifact`.

## Threat Flags

No new security-relevant surface introduced. T-06-05 (DoS via unbounded variant query) is now mitigated by `.limit(2000)` per the plan's threat register.

## Verification Results

- `cd portal-v2 && npm test -- ToastContext`: 4/4 pass
- `cd portal-v2 && npm test`: 89/89 pass (16 test files)
- `cd portal-v2 && npm run build`: exits 0 (tsc -b + vite build, 2291 modules)
- Grep confirms exactly zero `<ToastContainer` in `ArtifactTable.tsx`
- Grep confirms `QueryClientProvider` (line 35) → `ToastProvider` (line 36) → `BrowserRouter` (line 37) in `App.tsx`
- `.limit(2000)` and `staleTime: 10 * 60 * 1000` confirmed in `ArtifactTable.tsx` lines 72 + 76

## Self-Check: PASSED
