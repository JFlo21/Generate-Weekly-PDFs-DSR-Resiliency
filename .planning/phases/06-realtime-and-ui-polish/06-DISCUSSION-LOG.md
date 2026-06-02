# Phase 06: Realtime and UI Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 06-realtime-and-ui-polish
**Areas discussed:** Design-pass latitude, Toast fix (ctx vs sonner), Realtime role-gating, A11y (WCAG AA) verification

**Framing note:** Phase 06's visual/interaction system is already fully locked by
the **approved `06-UI-SPEC.md`** design contract. Discussion deliberately
targeted only the genuinely-open decisions the UI-SPEC left unresolved or that
span beyond it. The user selected all four candidate gray areas to discuss.

---

## Design-pass latitude

> Tension: the ROADMAP build note mandates invoking `/frontend-design` for the
> table + search/filter surface, but `06-UI-SPEC.md` is already an approved,
> detailed visual contract. Which is authoritative?

| Option | Description | Selected |
|--------|-------------|----------|
| Polish within UI-SPEC | `/frontend-design` elevates execution inside the locked tokens (microinteractions, hover/focus, density, empty/loading/error polish); does NOT change brand-red/glass/typography/layout. UI-SPEC stays authoritative; conflicts → deferred v2. | ✓ |
| Re-imagine; UI-SPEC yields | `/frontend-design` gets full creative freedom; conflicts win and UI-SPEC is updated. More distinctive, but reopens an approved contract and risks time blowout. | |
| Skip the pass | Treat UI-SPEC AS the distinctive design; drop the mandated `/frontend-design` invocation. Cleanest, but contradicts the ROADMAP operator requirement. | |

**User's choice:** Polish within UI-SPEC.
**Notes:** Reconciles both authorities — honors the operator's "MUST invoke
`/frontend-design`" requirement while keeping the approved contract governing.
Paired with the propose-then-approve handling (D-02) so the polish pass cannot
silently override the UI-SPEC. → CONTEXT D-01, D-02.

---

## Toast fix (C-01: dual ToastContainer → single global region)

| Option | Description | Selected |
|--------|-------------|----------|
| Custom ToastContext | Lift `useToast` into a React context + single `<ToastContainer>`; `ArtifactTable` consumes context. Reuses `Toast.tsx` spring + swipe + a11y. No new dependency. | ✓ |
| Adopt sonner | Replace with the `sonner` singleton toast lib: less code, accessible defaults; +~7KB and one more runtime dep. | |
| Let the planner decide | Defer the mechanism to planning (what UI-SPEC currently says). | |

**User's choice:** Custom ToastContext.
**Notes:** Honors the project's "minimize external deps" value; the existing
primitive already provides the spring/swipe/a11y, so context-wrapping is a small
change. `sonner` consciously rejected. → CONTEXT D-06.

---

## Realtime role-gating (security posture for the INSERT subscription)

| Option | Description | Selected |
|--------|-------------|----------|
| Defense-in-depth (gate + RLS) | Subscribe only when `isBilling`/`isAdmin`; payload count-only (no row data to UI); AND confirm in research that `supabase_realtime` publication + RLS withholds rows from pending/anon sockets. | ✓ |
| Count-only, lean on RLS | Always subscribe; only surface an integer count, relying entirely on Realtime RLS. Simpler, but a pending socket may still receive events. | |
| Research-gated decision | Have the researcher confirm 2026 Supabase Realtime authorization behavior first, then lock the exact gating. | |

**User's choice:** Defense-in-depth (gate + RLS).
**Notes:** Matches the project's UI-gate + DB-RLS pattern and is built to pass the
Phase 07 security audit with nothing to fix. The "confirm RLS in research"
element of the research-gated option was folded into the chosen decision. →
CONTEXT D-04.

---

## A11y (WCAG AA) verification method

| Option | Description | Selected |
|--------|-------------|----------|
| Both: jest-axe + manual | `jest-axe` component assertions in vitest/CI (regression net) PLUS a manual keyboard/focus/screen-reader walkthrough against the UI-SPEC contrast pairs + ARIA roles at close. | ✓ |
| Manual walkthrough only | Disciplined manual verification; no new dependency. | |
| Automated jest-axe only | CI assertions as the gate; skips keyboard-flow / screen-reader-announce coverage. | |

**User's choice:** Both: jest-axe + manual.
**Notes:** Matches the Fortune-500 quality bar set in Phase 05; `jest-axe` is a
test-only dev dependency (low "minimize-deps" cost). → CONTEXT D-07.

---

## Smaller items (locked with sensible defaults — user chose "I'm ready for context")

- **Toast + pill relationship** — both fire on INSERT: the toast announces and
  auto-dismisses; the "Load new" pill persists with the load action until clicked
  or dismissed. One stack (per C-01). → CONTEXT D-03.
- **Realtime test approach** — mock the Supabase channel in vitest for unit
  tests; verify live behavior during UAT. → CONTEXT D-05.
- **`/frontend-design` output handling** — propose-then-approve, so it cannot
  silently override the UI-SPEC. → CONTEXT D-02.

## Claude's Discretion

- `useInfiniteQuery` page-size / TanStack-Virtual overscan tuning (carried from
  Phase 05).
- Internal structure of the row-entrance stagger within the locked animation
  catalog.
- Exact mount point of the `ToastContext` provider (inside `QueryClientProvider`).
- File/module layout of the 4 net-new components, per their UI-SPEC contracts.

## Deferred Ideas

- Any `/frontend-design` proposal conflicting with the locked UI-SPEC tokens →
  v2 visual-refresh idea, not applied in Phase 06.
- Live Realtime integration test in CI (vs the chosen mock + UAT approach).
- Filename search (still deferred from Phase 05).
- Excel preview / bulk ZIP / CSV export / Cmd+K — v2.
- Physical deletion of Express backend (`portal/`) + legacy components — Phase 07.
