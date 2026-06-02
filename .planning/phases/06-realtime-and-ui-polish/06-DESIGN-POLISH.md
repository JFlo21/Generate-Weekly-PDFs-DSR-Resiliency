# Phase 06 — Frontend-Design Polish Proposal

**Plan:** 06-05 | **Task:** 1 (propose-then-approve, D-01/D-02)
**Generated:** 2026-06-02
**Status:** AWAITING OPERATOR APPROVAL — no component edits applied yet

---

## Section A: Proposed Polish — Within Locked Tokens

Each item is mapped to the exact UI-SPEC token it operates within. All changes
are microinteraction / hover-state / density / copy refinements — no new accent
color, no 4th depth level, no new type weight/size, no non-4px spacing.

---

### A-01 · ArtifactEmptyState.tsx — WCAG contrast + copy alignment

**File:** `portal-v2/src/components/artifacts/ArtifactEmptyState.tsx`

**Issues found (two correctness gaps):**

1. `EmptyDBState` uses `text-slate-400` for a content-carrying sentence. The
   UI-SPEC §Accessibility Contract lists `text-slate-400/white` at ~2.8:1 —
   explicitly a **FAIL** for normal text. The spec requires upgrading to
   `text-slate-500` (4.6:1, AA) for text that carries meaning.
2. The copy in `EmptyDBState` (`"No artifacts yet — they'll appear here after
   the next billing run."`) diverges from the locked Copywriting Contract which
   specifies `"No artifacts yet"` as heading + `"Billing artifacts will appear
   here after the next CI run completes."` as body. `NoResultsState` copy also
   diverges: spec says `"No matches found"` + `"Try adjusting your search or
   clearing the filters."` + `"Clear filters"` CTA, and `ErrorState` should read
   `"Could not load artifacts. Check your connection and try again."` + `"Try
   again"` (not `"Retry"`).
3. `NoResultsState` body text `text-slate-400` also fails the contrast check.

**Token authority:**
- `text-slate-500` — UI-SPEC §Accessibility Contract: "upgrade secondary meta
  text to text-slate-500 ... already reflected in ArtifactCard contract"
- Copy strings — UI-SPEC §Copywriting Contract (exact locked strings)
- `text-sm font-semibold text-slate-900` heading / `text-sm text-slate-500`
  body — UI-SPEC §Typography (14px/400 body, 14px/600 emphasis)
- `focus-visible:ring-brand-red/50` — UI-SPEC §Accessibility Contract keyboard nav

**Proposed change — verbatim replacement for the entire file:**

```tsx
/**
 * ArtifactEmptyState — three presentational state components for the artifact table.
 * D-07: exact copy per UI-SPEC §Copywriting Contract.
 * All text uses text-slate-500 minimum (WCAG AA — slate-400 fails at 2.8:1).
 */

/** Empty database state — no artifacts exist yet. No action available. */
export function EmptyDBState() {
  return (
    <div className="flex flex-col items-center gap-2 py-12">
      <p className="text-sm font-semibold text-slate-700">No artifacts yet</p>
      <p className="text-sm text-slate-500 text-center max-w-sm">
        Billing artifacts will appear here after the next CI run completes.
      </p>
    </div>
  );
}

interface NoResultsStateProps {
  onClear: () => void;
}

/** Zero matches while search/filter active — offers a clear-filters action. */
export function NoResultsState({ onClear }: NoResultsStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-12">
      <p className="text-sm font-semibold text-slate-700">No matches found</p>
      <p className="text-sm text-slate-500">
        Try adjusting your search or clearing the filters.
      </p>
      <button
        onClick={onClear}
        className="text-xs text-brand-red hover:text-red-700 underline transition-colors
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded"
      >
        Clear filters
      </button>
    </div>
  );
}

interface ErrorStateProps {
  onRetry: () => void;
}

/** Error loading artifacts — mirrors UsersPage.tsx banner styling. */
export function ErrorState({ onRetry }: ErrorStateProps) {
  return (
    <div className="p-6">
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 flex items-center justify-between">
        <span>Could not load artifacts. Check your connection and try again.</span>
        <button
          onClick={onRetry}
          className="text-xs text-red-600 hover:text-red-800 underline ml-4 shrink-0 transition-colors
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50 rounded"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
```

---

### A-02 · ArtifactTableRow.tsx — focus-visible ring + hover transition refinement

**File:** `portal-v2/src/components/artifacts/ArtifactTableRow.tsx`

**Issue:** The Download button in the table row has no `focus-visible` ring.
Tab-navigating to it shows no focus indicator, violating the UI-SPEC §Keyboard
Navigation table. The hover color transition is already correct but the button
lacks `rounded` on the focus ring — it would render as a box clipping outside.

**Token authority:**
- `focus-visible:ring-2 focus-visible:ring-brand-red/50` — UI-SPEC
  §Accessibility Contract, keyboard nav table: "Download button — Tab-reachable"
- `transition-colors` — existing pattern (already present on the button)
- `hover:text-red-700` — already present, keep as-is
- `rounded` — spacing/shape; consistent with the `4px scale` (border-radius
  comes from Tailwind defaults, not spacing scale, so no token conflict)

**Proposed change — replace the `<button>` in cell 6 (lines 76-90):**

```tsx
      {/* 6. Download */}
      <div role="cell" className="px-5 py-3">
        <button
          onClick={() => onDownload(row.id, row.storage_path, row.filename)}
          disabled={isDownloading}
          aria-label={isDownloading ? `Downloading ${row.filename}` : `Download ${row.filename}`}
          aria-disabled={isDownloading}
          className="inline-flex items-center gap-1.5 text-xs text-brand-red hover:text-red-700
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors rounded
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50"
        >
          {isDownloading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Download size={14} />
          )}
          <span>{isDownloading ? 'Downloading…' : 'Download'}</span>
        </button>
      </div>
```

Note: added `aria-disabled={isDownloading}` alongside `disabled` so assistive
tech receives the disabled signal even when the element is focusable.
Note: updated `aria-label` to distinguish "Downloading …" vs "Download …" to
match the UI-SPEC Copywriting Contract.

---

### A-03 · ArtifactTableRow.tsx — sortable column header keyboard accessibility

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx`

**Issue:** Sort headers in the table are `div[role="columnheader"]` with an
`onClick` handler but no `tabIndex`, no `onKeyDown`, and no `aria-sort`
attribute. The UI-SPEC §Keyboard Navigation requires: "Column sort headers —
Tab-reachable (tabIndex={0}); Enter/Space triggers sort; aria-sort updates."

**Token authority:**
- `tabIndex={0}` — UI-SPEC §Accessibility Contract, keyboard nav table
- `aria-sort="ascending"/"descending"/"none"` — UI-SPEC §Accessibility Contract
- `focus-visible:ring-2 focus-visible:ring-brand-red/50` — UI-SPEC §Accessibility Contract
- `transition-colors` + `hover:text-slate-700` — already present, preserved

**Proposed change — replace the `return (` block inside the
`table.getFlatHeaders().map(...)` (lines 269-299 of ArtifactTable.tsx):**

```tsx
                return (
                  <div
                    key={header.id}
                    role="columnheader"
                    tabIndex={isSortable ? 0 : undefined}
                    aria-sort={
                      isSortable
                        ? isAsc
                          ? 'ascending'
                          : isDesc
                            ? 'descending'
                            : 'none'
                        : undefined
                    }
                    onClick={
                      isSortable
                        ? header.column.getToggleSortingHandler()
                        : undefined
                    }
                    onKeyDown={
                      isSortable
                        ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              header.column.getToggleSortingHandler()?.(e);
                            }
                          }
                        : undefined
                    }
                    className={[
                      'text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide',
                      isSortable
                        ? 'cursor-pointer select-none hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded transition-colors'
                        : '',
                    ].join(' ')}
                  >
                    <span className="inline-flex items-center gap-1">
                      {typeof header.column.columnDef.header === 'string'
                        ? header.column.columnDef.header
                        : header.id}
                      {isSortable && (
                        <span className="text-slate-400">
                          {isAsc ? (
                            <ArrowUp size={12} />
                          ) : isDesc ? (
                            <ArrowDown size={12} />
                          ) : (
                            <ArrowUpDown size={12} />
                          )}
                        </span>
                      )}
                    </span>
                  </div>
                );
```

---

### A-04 · ArtifactSearchBar.tsx — focus-visible ring strength + clear button focus ring

**File:** `portal-v2/src/components/artifacts/ArtifactSearchBar.tsx`

**Issues:**
1. The search input uses `focus:ring-2 focus:ring-brand-red/30` (the non-`focus-visible`
   variant). The UI-SPEC §Keyboard Navigation specifies `focus-visible:ring-2
   focus-visible:ring-brand-red/50` — the `/50` opacity (not `/30`) and the
   `focus-visible` pseudo-class (not bare `focus`) to avoid showing the ring on
   mouse click.
2. The clear (×) button has no focus ring at all.
3. The search icon uses `text-slate-400`. It is decorative (pointer-events-none,
   never read by screen readers directly) so this is acceptable per the UI-SPEC
   note ("leave decorative uses as-is") — no change needed there.

**Token authority:**
- `focus-visible:ring-2 focus-visible:ring-brand-red/50` — UI-SPEC §Accessibility
  Contract, keyboard nav table row for search bar
- `focus-visible:ring-brand-red/50` — UI-SPEC §Color, accent reserved list item 4

**Proposed change — replace the `<input>` and `<button>` className (lines 23-43):**

```tsx
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-9 py-2.5 rounded-xl border border-slate-200 bg-white
                   text-sm text-slate-800 placeholder-slate-400
                   focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50
                   focus-visible:border-brand-red/40 transition-all"
      />
      {value && (
        <button
          onClick={() => {
            onChange('');
            inputRef.current?.focus();
          }}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600
                     transition-colors rounded
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50"
          aria-label="Clear search"
        >
          <X size={14} />
        </button>
      )}
```

---

### A-05 · VariantFilterBar.tsx — active chip color corrected to brand-red per UI-SPEC

**File:** `portal-v2/src/components/artifacts/VariantFilterBar.tsx`

**Issue:** The active/selected filter chip uses `bg-blue-100 text-blue-700
border-blue-200` — this is the info semantic color from the existing Badge
primitive, not the locked accent. The UI-SPEC §Color "Accent reserved for
exactly these elements" item 3 explicitly states: "Active/selected variant
filter chip: `bg-brand-red/10 text-brand-red border-brand-red/30`." The current
implementation also uses `bg-blue-100 text-blue-700 border-blue-200` on the
clearable chip duplicate, and the separator `text-slate-300` is decorative (OK).

Additionally, option toggles and chip buttons lack `focus-visible` rings and
`aria-pressed` for accessibility.

**Token authority:**
- `bg-brand-red/10 text-brand-red border-brand-red/30` — UI-SPEC §Color, Accent
  reserved list item 3: "Active/selected variant filter chip"
- `focus-visible:ring-2 focus-visible:ring-brand-red/50` — UI-SPEC §Accessibility
  Contract
- `aria-pressed` — UI-SPEC §Accessibility Contract keyboard nav table: "Variant
  filter chips — aria-pressed or aria-checked"

**Proposed change — replace the entire `VariantFilterBar.tsx` component:**

```tsx
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { getVariantLabel } from '../../lib/variantLabels';

interface VariantFilterBarProps {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}

export function VariantFilterBar({
  options,
  selected,
  onChange,
}: VariantFilterBarProps) {
  const toggle = (variant: string) => {
    if (selected.includes(variant)) {
      onChange(selected.filter((v) => v !== variant));
    } else {
      onChange([...selected, variant]);
    }
  };

  const remove = (variant: string) => {
    onChange(selected.filter((v) => v !== variant));
  };

  if (options.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Option toggles — aria-pressed communicates selected state (UI-SPEC §Keyboard Nav) */}
      {options.map((option) => {
        const isSelected = selected.includes(option);
        return (
          <button
            key={option}
            onClick={() => toggle(option)}
            aria-pressed={isSelected}
            className={cn(
              'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50',
              isSelected
                ? 'bg-brand-red/10 text-brand-red border-brand-red/30'
                : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200'
            )}
          >
            {getVariantLabel(option)}
          </button>
        );
      })}

      {/* Clearable chips for selected variants */}
      {selected.length > 0 && (
        <>
          <span className="text-slate-300" aria-hidden="true">|</span>
          {selected.map((variant) => (
            <span
              key={`chip-${variant}`}
              className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-brand-red/10 text-brand-red border-brand-red/30"
            >
              {getVariantLabel(variant)}
              <button
                onClick={() => remove(variant)}
                aria-label={`Remove ${getVariantLabel(variant)} filter`}
                className="ml-0.5 hover:text-red-700 transition-colors rounded
                           focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50"
              >
                <X size={10} />
              </button>
            </span>
          ))}
          <button
            onClick={() => onChange([])}
            className="text-xs text-slate-500 hover:text-slate-700 transition-colors underline
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded"
          >
            Clear
          </button>
        </>
      )}
    </div>
  );
}
```

---

### A-06 · NewArtifactPill.tsx — Escape key dismissal + separator aria-hidden

**File:** `portal-v2/src/components/artifacts/NewArtifactPill.tsx`

**Issue:** The UI-SPEC §Keyboard Navigation requires the pill to support
`Escape` to dismiss. The current implementation only supports clicking the `×`
button; keyboard users who Tab into the pill cannot dismiss with Escape. Also,
the pill container itself (`motion.div`) should gain a `tabIndex` and `onKeyDown`
handler to catch the Escape event.

**Token authority:**
- "Load new pill — Tab-reachable; Enter/Space loads; Escape dismisses (or
  explicit × button)" — UI-SPEC §Accessibility Contract keyboard nav table
- `focus-visible:ring-2 focus-visible:ring-brand-red/50` — UI-SPEC §Color accent
  item 4 (existing on the buttons already)
- `rounded-full` — already present, consistent with the pill shape

**Proposed change — add `onKeyDown` on the pill `motion.div` container:**

```tsx
        <motion.div
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={
            prefersReduced ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }
          }
          onKeyDown={(e: React.KeyboardEvent) => {
            if (e.key === 'Escape') {
              e.stopPropagation();
              onDismiss();
            }
          }}
          className={cn(
            'sticky top-0 z-10 mb-2 flex items-center gap-2 px-4 py-2',
            'backdrop-blur-sm border shadow-md rounded-full sm:inline-flex',
            'w-full sm:w-auto',
            'bg-brand-red text-white border-transparent',
            'sm:bg-white/80 sm:text-slate-700 sm:border-slate-200'
          )}
        >
```

Note: `React.KeyboardEvent` import is already available from React — no new
import needed (`import { AnimatePresence, motion, useReducedMotion } from
'framer-motion'` already present; add `import type { KeyboardEvent } from
'react'` or use the inline `React.KeyboardEvent` form with `import React`).
Alternatively the handler can be typed as `(e: React.KeyboardEvent<HTMLDivElement>)`
with the existing React import pattern used by sibling files.

---

### A-07 · ArtifactCard.tsx — entrance animation on initial load (mobile parity)

**File:** `portal-v2/src/components/artifacts/ArtifactCard.tsx`

**Issue:** The UI-SPEC §Animation Catalog specifies "Mobile card entrance:
opacity 0→1, y 4→0 | 150ms ease-out | On initial load only; no stagger on
scroll." The current `ArtifactCard` has no entrance animation — it renders
immediately. This is a minor density/feel gap vs. the table which does animate.

This item requires adding a `motion.div` wrapper and importing `motion` +
`useReducedMotion` from `framer-motion`. No new dependency (framer-motion
already used in `ArtifactTableRow` and `NewArtifactPill`).

**Token authority:**
- `opacity 0→1, y 4→0 | 150ms ease-out` — UI-SPEC §Animation Catalog, "Mobile
  card entrance" row (exact prescribed values)
- `useReducedMotion` check — UI-SPEC §Reduced Motion: "All Framer Motion
  variants MUST also check useReducedMotion()"
- No new spacing/color/type tokens introduced

**Proposed change — replace the outer `<div role="listitem">` with a
`motion.div`, add imports:**

```tsx
import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Download, Loader2 } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { getVariantLabel } from '../../lib/variantLabels';
import { formatSize, formatDate } from '../../lib/utils';
import type { BillingArtifact } from '../../lib/types';
```

And the `return` block root element:

```tsx
  const prefersReduced = useReducedMotion();

  return (
    <motion.div
      role="listitem"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        prefersReduced
          ? { duration: 0 }
          : { duration: 0.15, ease: 'easeOut' }
      }
      className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 space-y-2 mb-2"
    >
      {/* ... card rows unchanged ... */}
    </motion.div>
  );
```

---

### A-08 · ArtifactTable.tsx — mobile states: loading skeletons + error/empty parity

**File:** `portal-v2/src/components/artifacts/ArtifactTable.tsx`

**Issue:** The mobile card list (`sm:hidden div[role="list"]`) renders nothing
when `q.status === 'pending'`, `'error'`, or when `allRows.length === 0`. The
comment in the code acknowledges this: "Empty/loading: allRows is [] so nothing
renders — acceptable for Phase 06." However, this leaves mobile users with a
blank screen on first load — a clear UX gap. The fix is to mirror the four-state
render into the mobile section using the existing `Skeleton`, `EmptyDBState`,
`NoResultsState`, and `ErrorState` components.

**Token authority:**
- `Skeleton` — `animate-pulse rounded-lg bg-slate-200` — UI-SPEC §Existing
  Primitives (the established loading pattern)
- `EmptyDBState`, `NoResultsState`, `ErrorState` — already built in
  `ArtifactEmptyState.tsx`; no new tokens
- `space-y-2` — Tailwind 4px scale (8px gap between skeletons on mobile)

**Proposed change — replace the mobile list block (lines 314-323):**

```tsx
      {/* Mobile: stacked ArtifactCard list (<640px) — UI-01 responsive swap */}
      <div className="sm:hidden">
        {q.status === 'pending' && (
          <div role="list" className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-2xl" />
            ))}
          </div>
        )}

        {q.status === 'error' && <ErrorState onRetry={() => q.refetch()} />}

        {q.status === 'success' && allRows.length === 0 && !debouncedSearch && variants.length === 0 && (
          <EmptyDBState />
        )}

        {q.status === 'success' && allRows.length === 0 && (debouncedSearch || variants.length > 0) && (
          <NoResultsState onClear={clearFilters} />
        )}

        {q.status === 'success' && allRows.length > 0 && (
          <div role="list">
            {allRows.map((row) => (
              <ArtifactCard
                key={row.id}
                row={row}
                onDownload={download}
                isDownloading={downloading === row.id}
              />
            ))}
          </div>
        )}
      </div>
```

Note: the `role="list"` is moved inside each conditional branch (only rendered
when there are items or skeletons) to avoid an empty `role="list"` element
being announced by screen readers.

---

## Section B: Deferred to v2 — Conflicts With Locked Tokens

These ideas emerged from the frontend-design review but cannot be applied without
violating one or more locked UI-SPEC tokens. Each is captured here for a future
v2 visual-refresh pass.

---

### B-01 · Active chip accent: info-blue → brand-red (ALREADY in A-05)

Resolved above as an A-05 item (the spec explicitly requires brand-red for active
chips). No separate v2 deferral needed.

---

### B-02 · Hover row highlight: stronger background

**Idea:** Increase `ArtifactTableRow` hover from `hover:bg-slate-50/50` to
`hover:bg-slate-100` for a more pronounced row hover effect.

**Conflict:** `bg-slate-100` is not in the approved color palette. The 60/30/10
rule (UI-SPEC §Color) reserves the dominant surface as `bg-slate-50` and the
card as `bg-white`. Introducing `bg-slate-100` as a hover state would add an
undocumented fourth color to the hierarchy. The current `hover:bg-slate-50/50`
(50% opacity of the bg-slate-50 surface tint) is the correct approved in-spec
hover treatment.

**Deferred:** v2 visual refresh — requires updating the color section of the
UI-SPEC to add a `bg-slate-100` hover state to the approved palette.

---

### B-03 · Typography: medium weight (500) for table meta / date cells

**Idea:** Use `font-medium` (weight 500) for secondary cell content (dates, file
sizes) to improve visual hierarchy in the table body.

**Conflict:** UI-SPEC §Typography is explicit: "Exactly 2 weight values: 400
(regular) and 600 (semibold). No heavier weights, no new sizes." Weight 500
would introduce a third weight value.

**Deferred:** v2 visual refresh — requires a typography section update in the
UI-SPEC.

---

### B-04 · Spacing: 6px gap between sort icon and header label

**Idea:** Increase `gap-1` (4px) between column header text and sort icon to
`gap-1.5` (6px) for slightly better readability.

**Conflict:** `gap-1.5` = 6px, which is not a multiple of 4 (the Tailwind
default 4px scale in use). UI-SPEC §Spacing: "Every declared spacing value in
this spec is a multiple of 4." `gap-1.5` would be the first non-4px spacing in
the locked surface.

**Deferred:** v2 — either stay at `gap-1` (4px) or jump to `gap-2` (8px); the
latter would be within the spec. Operator may approve `gap-2` upgrade separately
as it IS within the 4px scale — request operator guidance at that time.

---

### B-05 · Depth: subtle drop-shadow on NewArtifactPill on desktop (4th visual layer)

**Idea:** Give the desktop pill a `shadow-lg` upgrade to increase separation from
the L1 table card beneath it.

**Conflict:** The pill already uses `shadow-md` (the L2 glass spec). Escalating
to `shadow-lg` would create a visual distinction beyond the 3-level depth
hierarchy defined by UI-SPEC §Glass-Morphism Depth Layering. While not strictly
a "4th layer," it would push the pill past the L2 ceiling — the spec prescribes
`shadow-xl` only for full GlassCard modals, not for the pill.

**Deferred:** v2 — keep `shadow-md` on the pill per the locked L2 spec.

---

### B-06 · Backdrop blur: stronger blur on pill desktop (`backdrop-blur-md`)

**Idea:** Increase the pill's `backdrop-blur-sm` to `backdrop-blur-md` for a
more pronounced glass effect on desktop.

**Conflict:** The UI-SPEC §Component Inventory §NewArtifactPill contract
explicitly specifies `backdrop-blur-sm` for the desktop pill. Upgrading to
`backdrop-blur-md` would override a locked component contract value. Full
`backdrop-blur-xl` is reserved for `GlassCard` (L2 floating overlays).

**Deferred:** v2 visual refresh — requires updating the Component Inventory
contract for NewArtifactPill.

---

## Approval

> **This section is populated by the operator after reviewing sections A and B.**

Status: PENDING

<!-- Operator: fill in below when approving/rejecting -->

**Approved items (A-xx):** [PENDING]
**Rejected items (A-xx with reason):** [PENDING]
**Change requests:** [PENDING]
**Approved by:** [PENDING]
**Date:** [PENDING]
