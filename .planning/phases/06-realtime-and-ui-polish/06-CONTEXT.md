# Phase 06: Realtime and UI Polish - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the now-stable Phase 05 artifact table **feel alive and polished**. Four
requirements:

- **DATA-06** — Supabase Realtime delivers new-artifact INSERT events to the
  open portal (replacing the dead Express SSE poller); the `artifacts` table is
  added to the `supabase_realtime` publication.
- **UI-01** — the portal is responsive across desktop, tablet, and narrow-mobile
  widths (priority columns always visible; mobile collapses to stacked cards).
- **UI-02** — tasteful Framer Motion animations (row-entrance stagger, "Load
  new" pill, toasts) enhance the experience **without** degrading table scroll
  performance.
- **UI-03** — consistent, modern, **accessible** visual design (keyboard
  navigable, WCAG-AA contrast) built on the existing `GlassCard` / `Badge` /
  `Skeleton` / `Toast` primitives.

**This phase is unusual: the visual/interaction "HOW" is already locked.**
`06-UI-SPEC.md` is an **approved, exhaustive design contract** (glass-morphism
depth, typography, color, spacing, full animation catalog, responsive
breakpoints, mobile `ArtifactCard`, accessibility contract, copywriting, and the
4 net-new component contracts). Discussion therefore focused only on the
genuinely-open decisions the UI-SPEC left unresolved or that span beyond it.

**In scope (DATA-06, UI-01..03 + two locked carryover fixes):**
- `useRealtimeArtifacts` hook + `NewArtifactPill` + Realtime toast (count-only,
  no mid-scroll auto-insert, unsubscribe on unmount).
- Responsive layout: `ArtifactCard` stacked list `<640px`; `<table>` at `sm+`;
  page padding `p-4 → p-6 lg:p-8`.
- Framer Motion: initial-load row-entrance stagger only, pill appear/disappear,
  reduced-motion respected (`useReducedMotion`).
- A11y: keyboard nav, ARIA roles, `text-slate-400 → text-slate-500` upgrade.
- **C-01** (single global toast region) and **C-02** (`['artifact-variants']`
  `.limit(2000)` + 10-min `staleTime`) — locked carryovers from `05-REVIEW.md`.
- The mandated `/frontend-design` execution-polish pass (see D-01).

**Out of scope (other phases):**
- **Phase 07** — security headers / CSP, full RLS + signed-URL scoping audit,
  secret-handling audit, and **physical deletion of the Express backend
  (`portal/`)** + orphaned legacy run/explorer components. Phase 06 only *uses*
  the live Supabase Realtime/RLS surface; it does not perform the security
  review or remove Express.
- New capabilities (Excel preview, bulk ZIP, CSV export, Cmd+K) — deferred to v2
  per REQUIREMENTS.md.

**Carried-forward foundation (already locked — do NOT re-decide):**
- **06-UI-SPEC.md (approved 2026-06-01)** — the authoritative visual/interaction
  contract. Realtime UX = toast + "Load new" pill, count-only; mobile = stacked
  GlassCards `<640px`; animation durations/easings/stagger all prescriptive;
  typography (2 weights / 3 sizes), color (60/30/10, brand-red accent), 4px
  spacing scale; full accessibility contract (keyboard/ARIA/contrast pairs).
- **Phase 05 table (D-01..D-10)** — TanStack Table/Virtual/Query, infinite
  windowed scroll, `week_ending DESC` default sort, server-side
  search/filter/sort, the 4 distinct loading/empty/error states. Phase 06
  animates and subscribes against this — it does not rebuild it.
- **Data contract (Phase 03)** — `public.artifacts` shape, role-aware RLS
  (`admin`/`billing` SELECT; `pending`/anon zero rows), private
  `excel-artifacts` bucket, 5-min single-object signed URLs.
- **Live grounding** — deployed Supabase project is `poeyztlmsawfoqlanucc`
  (~2,383 real `public.artifacts` rows, CI publish live). The table is NOT empty
  on day one.

</domain>

<decisions>
## Implementation Decisions

### Design-pass authority (the `/frontend-design` vs UI-SPEC tension)
- **D-01:** **`06-UI-SPEC.md` is the authoritative visual/interaction contract.**
  The ROADMAP build note mandates invoking `/frontend-design` for the table +
  search/filter surface — that pass runs as an **execution-polish layer ONLY**:
  microinteractions, hover/focus states, density rhythm, and empty/loading/error
  refinement **within the locked tokens** (brand-red, glass-morphism depth,
  typography, color, spacing, layout). It does **not** change the UI-SPEC's
  visual identity or layout. Any `/frontend-design` idea that conflicts with the
  locked tokens is **captured as a deferred v2 idea, not applied** (see Deferred).
- **D-02:** **`/frontend-design` output is propose-then-approve.** The polish
  pass proposes its refinements for operator approval before they land — it must
  not silently override the approved UI-SPEC. This keeps the approved contract
  from being re-litigated mid-execution.

### Realtime new-artifact notification (DATA-06)
- **D-03:** **Notification = count-only toast + "Load new" pill, both fire on
  INSERT.** The toast announces ("N new artifact(s)", `info` variant) and
  auto-dismisses; the `NewArtifactPill` persists with the **load action** until
  the user clicks it (→ `clearPending` invalidates `['artifacts']` and refetches)
  or dismisses it. **No auto-insert of rows mid-scroll.** Both live in the single
  C-01 toast/overlay layer. (Reaffirms the UI-SPEC contract; resolves the
  toast-vs-pill ambiguity: they coexist, not either/or.)
- **D-04:** **Realtime gating is defense-in-depth.** (1) Subscribe to the
  `artifacts` channel **only when `useAuth` reports `isBilling`/`isAdmin`** —
  `pending`/anon sessions never open the channel. (2) The payload surfaced to the
  UI is **count-only** — no artifact row data ever reaches the client state.
  (3) **Researcher MUST confirm** that the `supabase_realtime` publication +
  table RLS withholds row payloads from unauthorized sockets in current (2026)
  Supabase behavior, and document the exact authorization model. This must be
  clean for the Phase 07 security audit. Hook still `channel.unsubscribe()` on
  unmount — zero subscription leak (UI-SPEC contract).
- **D-05:** **Realtime is unit-tested by mocking the Supabase channel** in
  vitest — assert: INSERT increments `pendingCount`; `clearPending` resets to 0
  AND calls `queryClient.invalidateQueries({ queryKey: ['artifacts'] })`;
  unmount calls `unsubscribe()`. Live end-to-end behavior (a real CI INSERT
  surfacing the toast/pill within seconds) is verified during **UAT**, not in CI.

### Toast consolidation (C-01)
- **D-06:** **Build a custom `ToastContext`** (`src/contexts/ToastContext.tsx`)
  on the **existing `Toast.tsx` + `useToast.ts` primitives** — single global
  `<ToastContainer>` in the provider; `ArtifactTable` consumes the context and
  **removes its own local `<ToastContainer>`/`useToast()`**; `useDownloadArtifact`
  sources `addToast` from context. **`sonner` was considered and rejected** to
  honor the project's "minimize external deps" value (the existing primitive
  already provides spring + swipe-to-dismiss + a11y; wrapping it in context is a
  small change). Provider nests inside `QueryClientProvider`, matching the
  existing `AuthProvider` nesting pattern.

### Accessibility verification (UI-03)
- **D-07:** **Verify WCAG AA with BOTH automated and manual passes.** Add
  **`jest-axe`** (test-only dev dependency) for component-level a11y assertions
  in vitest/CI as a regression net on every push; AND perform a **manual
  keyboard / focus-ring / screen-reader-announce walkthrough at phase close**
  against the UI-SPEC's enumerated contrast pairs (§Accessibility Contract) and
  ARIA roles. Matches the Fortune-500 quality bar set in Phase 05; the dev-only
  dep is a low "minimize-deps" cost.

### Variant query cap (C-02)
- **D-08:** Apply the UI-SPEC C-02 fix verbatim — add `.limit(2000)` to the
  `['artifact-variants']` query and set `staleTime: 10 * 60 * 1000`. Data-layer
  fix, no visible UI change; part of the polish pass.

### Claude's Discretion
- `useInfiniteQuery` page-size / TanStack-Virtual overscan tuning (carried from
  Phase 05 discretion — unchanged here).
- Exact internal structure of the stagger implementation **within** the locked
  animation catalog (index × 20ms, capped 200ms / 10 rows) — as long as it
  animates initial-load rows only and never re-animates on scroll/filter
  (`AnimatePresence initial={false}`).
- Precise mount point of the `ToastContext` provider in the app tree (must sit
  inside `QueryClientProvider`, per D-06).
- File/module layout of the 4 net-new components, provided each matches its
  UI-SPEC §Component Inventory contract.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & THE design authority
- `.planning/phases/06-realtime-and-ui-polish/06-UI-SPEC.md` — **THE
  authoritative, approved visual/interaction contract for this phase (D-01).**
  Read in full before planning: §Existing Primitives, §Phase 06 Constraints
  (C-01/C-02), §Component Inventory (the 4 net-new contracts:
  `useRealtimeArtifacts`, `NewArtifactPill`, `ArtifactCard`, `ToastContext`),
  §Responsive Layout Contract, §Animation Contract, §Accessibility Contract,
  §Copywriting Contract.
- `.planning/ROADMAP.md` §"Phase 06: Realtime and UI Polish" — goal + 4 success
  criteria + the **Build note** mandating the `/frontend-design` pass and the
  WR-05/WR-03 carryovers.
- `.planning/REQUIREMENTS.md` — DATA-06, UI-01, UI-02, UI-03 (the 4 requirements
  this phase covers); plus the Out-of-Scope table (no `generate_weekly_pdfs.py`
  changes; `service_role` never on Vercel; iframe embedding forbidden).

### The surface being polished (built in Phase 05)
- `.planning/phases/05-artifact-table-and-search/05-CONTEXT.md` — D-01..D-10
  (TanStack stack, infinite scroll, `week_ending DESC`, server-side
  search/filter/sort, the 4 honest states) + the code-context map. Phase 06
  animates/subscribes against this table; it does not rebuild it.
- `.planning/phases/05-artifact-table-and-search/05-REVIEW.md` — source of the
  WR-05 (dual `ToastContainer`) and WR-03 (variant query) findings that became
  UI-SPEC **C-01 / C-02** (D-06 / D-08).

### Data layer + Realtime + RLS (built in Phase 03)
- `.planning/phases/03-supabase-data-layer-foundation/03-CONTEXT.md` —
  `public.artifacts` schema, role-aware RLS (`admin`/`billing` SELECT;
  `pending`/anon zero rows), private bucket + signed-URL policy. The RLS model
  D-04's Realtime gating must align with.
- `supabase/portal_schema.sql` — the **deployed, authoritative** schema + RLS
  policies. The researcher must verify the `supabase_realtime` publication
  includes `artifacts` (DATA-06) and confirm RLS behavior for Realtime
  postgres_changes (D-04).
- `.planning/STATE.md` §"Infrastructure Topology … READ BEFORE PHASE 05" — live
  project `poeyztlmsawfoqlanucc` (~2,383 real rows, CI publish live). Realtime
  subscribes against THIS project. (Ignore the red-herring `iixetbhhntwjinnwoegi`.)

### Design tokens & primitives (the locked vocabulary)
- `portal-v2/tailwind.config.ts` — brand-red `#C41230`, brand-gray, default 4px
  spacing scale (no custom overrides), default breakpoints.
- `portal-v2/src/styles/globals.css` — `bg-slate-50 text-slate-900` body;
  `prefers-reduced-motion` override already wired (D-07 / UI-SPEC §Reduced Motion).
- `portal-v2/src/components/ui/` — `GlassCard.tsx`, `Badge.tsx`, `Skeleton.tsx`,
  `Toast.tsx`, `src/hooks/useToast.ts` — the primitives the new components and
  `ToastContext` (D-06) are built from. **Do not re-specify or replace them.**

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **UI primitives** `GlassCard` / `Badge` / `Skeleton` / `Toast` + `useToast`
  (`portal-v2/src/components/ui/`, `src/hooks/useToast.ts`) — the `ToastContext`
  (D-06), `NewArtifactPill`, and `ArtifactCard` are built from these as-is.
- **Phase 05 table** — `ArtifactTable.tsx`, `ArtifactTableRow.tsx`,
  `ArtifactSearchBar.tsx`, `VariantFilterBar.tsx`, `ArtifactEmptyState.tsx`
  (`portal-v2/src/components/artifacts/`). Row-entrance animation goes on the
  inner `ArtifactTableRow` root, NOT the virtualizer's positioning wrapper.
- **Data hooks** — `useArtifactsInfinite.ts` (TanStack Query infinite scroll;
  `clearPending` invalidates its `['artifacts']` key), `useDownloadArtifact.ts`
  (signed-URL download + error toast; will source `addToast` from `ToastContext`).
- **`useAuth`** (`role` / `isAdmin` / `isBilling`) — the gate for the
  defense-in-depth Realtime subscription (D-04).
- **Framer Motion 11.11** + **lucide-react 0.460** — already dependencies
  (`package.json`); no new runtime UI deps needed (D-06 keeps it that way).
- `formatSize` / `cn` in `portal-v2/src/lib/utils.ts` — for the mobile card.

### Established Patterns
- `portal-v2` is ES2022+ ESM, React 18; prefer `undefined` over `null`,
  `async`/`await`, functions over classes. New deps must be ESM/React-18 safe.
- **Defense in depth:** UI gate (`useAuth`/`RoleGuard`) + DB RLS for every
  privileged read — D-04 extends this to the Realtime subscription.
- **Honest states, no fake rows** — preserved from Phase 05; Realtime never
  injects rows, only a count.
- **`React.memo` at module level** for virtualized/list rows (Phase 05 Pitfall 3)
  — applies to the new `ArtifactCard` too.
- Single global toast layer after C-01; provider nests inside
  `QueryClientProvider` matching the `AuthProvider` pattern.

### Integration Points
- **Realtime seam:** `useRealtimeArtifacts` → `supabase.channel('artifacts')
  .on('postgres_changes', { event: 'INSERT', schema: 'public', table:
  'artifacts' })` → `pendingCount` → `NewArtifactPill` / toast; gated by
  `isBilling`/`isAdmin` (D-04). `clearPending` →
  `queryClient.invalidateQueries(['artifacts'])`.
- **Toast seam:** new `src/contexts/ToastContext.tsx` provider → single
  `<ToastContainer>`; `ArtifactTable` + `useDownloadArtifact` consume it; remove
  the second `<ToastContainer>` from `ArtifactTable.tsx` (C-01 / D-06).
- **Responsive seam:** `<table>` wrapper `hidden sm:block`; new `ArtifactCard`
  list `sm:hidden` at `<640px` (UI-01).
- **A11y test seam:** `jest-axe` wired into the existing vitest setup (D-07).

</code_context>

<specifics>
## Specific Ideas

- **Quality bar (carried from Phase 05, still operative):** Fortune-500-grade,
  using the correct modern methods senior front-end engineers use today. The
  polish pass must *elevate* the already-polished glass/Linetec aesthetic, never
  fight it.
- **Reconcile, don't re-open:** the operator explicitly wanted a `/frontend-design`
  distinctive pass, but also approved the UI-SPEC. The resolution (D-01/D-02) is
  to run the pass as a propose-then-approve *polish* layer governed by the
  UI-SPEC — getting the distinctive-execution benefit without reopening an
  approved contract or risking a time blowout.
- **Security-clean by construction:** the Realtime decision (D-04) is shaped so
  the Phase 07 audit finds nothing to fix — count-only payload + role-gated
  subscription + verified RLS.

</specifics>

<deferred>
## Deferred Ideas

- **Any `/frontend-design` proposal that conflicts with the locked UI-SPEC
  tokens** (new color identity, different layout paradigm, heavier typography,
  non-4px spacing) → captured as a **v2 visual-refresh idea**, NOT applied in
  Phase 06 (per D-01).
- **Live Realtime integration test in CI** (vs the chosen mock-channel unit test
  + UAT live check, D-05) — could be added later if Realtime regressions become
  a recurring problem.
- **Filename search** — still deferred from Phase 05 (SEARCH scope is WR # +
  week-ending only).
- **Excel preview / bulk ZIP / CSV export / Cmd+K** — v2 per REQUIREMENTS.md;
  not in v1.1.
- **Physical deletion of the Express backend (`portal/`) + orphaned legacy
  run/explorer components** — Phase 07.

</deferred>

---

*Phase: 06-realtime-and-ui-polish*
*Context gathered: 2026-06-02*
