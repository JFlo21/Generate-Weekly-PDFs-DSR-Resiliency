# Phase 5: Artifact Table and Search - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 05-artifact-table-and-search
**Areas discussed:** Table placement / legacy UI, Dependency strategy, Pagination/sort/states, Search & variant filters

**Overarching user steer:** Build an upgraded, production/enterprise-grade table
(Fortune-500 quality) using the correct modern frontend methods senior engineers
recommend and use today. This lens was applied to every option below.

---

## Table placement / legacy UI

### Q1 — Primary dashboard view vs alongside?

| Option | Description | Selected |
|--------|-------------|----------|
| Replace — table IS the dashboard | Artifact table becomes the post-login landing at `/dashboard`; Express-era runs list retired from the primary path | ✓ |
| Add alongside (new route/tab) | Keep runs dashboard, add artifact table as a separate route/tab; leaves a mock-coupled surface live | |

**User's choice:** Replace — table IS the dashboard.

### Q2 — Fate of legacy run/explorer code this phase?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove mock path now, leave rest for Phase 07 | Delete only the silent mock fallback + mock-coupled `useArtifacts(runId)`; stop rendering legacy UI; leave Express-coupled files for Phase 07 deletion | ✓ |
| Delete all legacy run/explorer UI now | Aggressively remove ArtifactExplorer/ArtifactPanel/useRuns/api.ts/mockData.ts this phase | |
| You decide | Defer to Claude | |

**User's choice:** Remove mock path now, leave rest for Phase 07.
**Notes:** Keeps the blast radius minimal and avoids straying into Phase 07's Express-removal scope.

---

## Dependency strategy

### Q1 — Table/virtualization/state stack?

| Option | Description | Selected |
|--------|-------------|----------|
| TanStack Table + Virtual + Query | TanStack Table v8 (headless) + TanStack Virtual + TanStack Query v5 (server-state, useInfiniteQuery); ~3 headless deps; current senior-engineer enterprise standard | ✓ |
| Minimal: TanStack Virtual + custom hooks | Add only TanStack Virtual; hand-roll supabase-js range fetch + debounce | |
| Fully hand-rolled (no new deps) | Custom virtualization + fetching + debounce, zero new deps | |

**User's choice:** TanStack Table + Virtual + Query.
**Notes:** Conscious, accepted trade-off against the project's "minimize external deps" value — these are best-in-class and the quality bar wins.

### Q2 — Headless vs pre-built grid?

| Option | Description | Selected |
|--------|-------------|----------|
| Headless + your existing primitives | Tailwind + GlassCard/Badge/Skeleton/Toast + Linetec brand on TanStack headless logic; full control of the look | ✓ |
| Pre-built data-grid (MUI / AG Grid) | Batteries-included grid; heavy, opinionated styling, AG Grid enterprise licensing | |
| You decide | Defer to Claude | |

**User's choice:** Headless + your existing primitives.

---

## Pagination, sort & states

### Q1 — Scroll/pagination model?

| Option | Description | Selected |
|--------|-------------|----------|
| Infinite windowed scroll | useInfiniteQuery + supabase range() + TanStack Virtual; shallow DOM, flat memory | ✓ |
| Numbered pages | Classic pagination with page-size selector | |
| Load more button | Manual append of next page | |

**User's choice:** Infinite windowed scroll.

### Q2 — Default sort?

| Option | Description | Selected |
|--------|-------------|----------|
| Week-ending DESC (newest week first) | Matches billing-cycle mental model + existing (week_ending DESC) index | ✓ |
| Created DESC (newest generated first) | Surfaces newest files but mixes weeks | |
| You decide | Defer to Claude | |

**User's choice:** Week-ending DESC.

### Q3 — Loading/empty/error state explicitness?

| Option | Description | Selected |
|--------|-------------|----------|
| Three tailored states with distinct copy/CTA | Skeleton / "no artifacts yet" / "no matches — clear filters" / "couldn't load — retry" | ✓ |
| Generic empty + generic error | One empty + one error message regardless of cause | |
| You decide | Defer to Claude | |

**User's choice:** Three tailored states with distinct copy/CTA.

---

## Search & variant filters

### Q1 — Week-ending date input format?

| Option | Description | Selected |
|--------|-------------|----------|
| Flexible — accept MMDDYY, MM/DD/YY, ISO | Normalize whatever the operator types before querying | ✓ |
| MMDDYY only (matches week_ending_fmt) | Accept only the MMDDYY filename form | |
| You decide | Defer to Claude | |

**User's choice:** Flexible — accept MMDDYY, MM/DD/YY, ISO.

### Q2 — Match semantics?

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive substring (ilike %term%) | Matches WR # or week-ending anywhere; forgiving for partial recall | ✓ |
| Prefix match (ilike term%) | Matches from start only; more index-efficient, less forgiving | |
| You decide | Defer to Claude | |

**User's choice:** Case-insensitive substring (ilike %term%).
**Notes:** Search scope stays on WR # + week-ending only; filename search deferred.

### Q3 — Variant filter labeling?

| Option | Description | Selected |
|--------|-------------|----------|
| Human-friendly labels via a known mapping | Primary / Helper / VAC Crew / AEP Billable (Sub) / Reduced Sub / combo labels; options dynamic from data present | ✓ |
| Raw variant values as-is | Literal column values as chips; cryptic | |
| You decide | Defer to Claude | |

**User's choice:** Human-friendly labels via a known mapping.

---

## Claude's Discretion

- Download-button in-progress UX (spinner-on-button vs row busy state); single `.xlsx` browser download via click-time signed URL; failures via existing Toast.
- Redefined `Artifact` TS type matching `public.artifacts`; whether to alias the old type until Phase 07.
- `useInfiniteQuery` `.range()` window/page size + TanStack Virtual overscan tuning.
- Thin supabase-js data-access layer + TanStack Query query-key design (new artifacts hook).
- Column presentation within the locked TABLE-01 column set (responsive collapse is Phase 06).
- `QueryClientProvider` mount point.

## Deferred Ideas

- Filename search (out of SEARCH-01 scope).
- Deep animation polish, full responsive breakpoints, WCAG-AA accessibility audit — Phase 06.
- Realtime new-artifact toast (DATA-06) — Phase 06.
- Physical deletion of Express-coupled run/explorer components + `mockData.ts` + `portal/` — Phase 07.
- Excel content preview / in-browser rendering — out of v1.
