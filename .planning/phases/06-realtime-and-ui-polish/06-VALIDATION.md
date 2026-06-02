---
phase: 06
slug: realtime-and-ui-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `06-RESEARCH.md` §Validation Architecture. Per-task IDs are
> finalized once `*-PLAN.md` files are written; the Req→Test map below is the
> authoritative coverage contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest `2.1.9` (jsdom env, already configured) |
| **Config file** | `portal-v2/vitest.config.ts` |
| **Setup file** | `portal-v2/src/test/setup.ts` (jest-axe `expect.extend` added in Wave 0) |
| **Quick run command** | `cd portal-v2 && npm test` |
| **Full suite command** | `cd portal-v2 && npm test` (no separate watch mode in CI) |
| **Estimated runtime** | ~15–30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd portal-v2 && npm test` — all unit + a11y vitest tests must pass.
- **After every plan wave:** Run `cd portal-v2 && npm test` — must be green.
- **Before `/gsd-verify-work`:** Full suite green **AND** the Manual UAT checklist below signed off.
- **Max feedback latency:** ~30 seconds.

---

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| DATA-06 | `useRealtimeArtifacts`: INSERT event increments `pendingCount` | unit (mock channel) | `npm test` | ❌ W0 |
| DATA-06 | `clearPending` resets `pendingCount` to 0 | unit (mock channel) | `npm test` | ❌ W0 |
| DATA-06 | `clearPending` calls `queryClient.invalidateQueries({ queryKey: ['artifacts'] })` | unit (mock channel + queryClient) | `npm test` | ❌ W0 |
| DATA-06 | unmount calls `channel.unsubscribe()` (zero subscription leak) | unit (mock channel) | `npm test` | ❌ W0 |
| DATA-06 | `pending`/unauthenticated role does NOT open the channel (D-04 gate) | unit (mock useAuth) | `npm test` | ❌ W0 |
| DATA-06 | `artifacts` is in `supabase_realtime` publication | SQL verify (Wave 0 live check) | SQL Editor query | ❌ W0 |
| UI-01 | `ArtifactCard` renders WR#, week-ending, variant badge, download btn | unit (RTL) | `npm test` | ❌ W0 |
| UI-01 | `ArtifactCard` has no axe violations (structure/ARIA) | a11y (jest-axe) | `npm test` | ❌ W0 |
| UI-02 | `NewArtifactPill` renders when `count > 0`, absent when `count === 0` | unit (RTL) | `npm test` | ❌ W0 |
| UI-02 | `NewArtifactPill` has no axe violations | a11y (jest-axe) | `npm test` | ❌ W0 |
| UI-02 | Row-entrance stagger animates initial-load rows only (no re-animate on scroll) | unit (RTL — assert delay prop / initialLoadComplete gate) | `npm test` | ❌ W0 |
| UI-03 | `ToastContext`: `addToast` → toast appears; `removeToast` → disappears | unit (RTL) | `npm test` | ❌ W0 |
| UI-03 | Single global `<ToastContainer>` (no duplicate — C-01) | unit (RTL) | `npm test` | ❌ W0 |
| C-02 | `['artifact-variants']` query includes `.limit(2000)` + `staleTime: 10*60*1000` | unit (mock supabase) / code review | `npm test` | ❌ W0 |

*Status legend: ✅ green · ❌ red/missing · ⬜ pending · W0 = created in Wave 0*

---

## Wave 0 Requirements

- [ ] `cd portal-v2 && npm install -D jest-axe @types/jest-axe` — install before any a11y test runs
- [ ] `portal-v2/src/test/setup.ts` — add `import { toHaveNoViolations } from 'jest-axe'` + `expect.extend(toHaveNoViolations)` (2 lines)
- [ ] `src/hooks/__tests__/useRealtimeArtifacts.test.ts` — DATA-06 mock-channel assertions (D-05)
- [ ] `src/components/artifacts/__tests__/ArtifactCard.test.tsx` — UI-01 rendering + jest-axe
- [ ] `src/components/artifacts/__tests__/NewArtifactPill.test.tsx` — UI-02 pill visibility + jest-axe
- [ ] `src/contexts/__tests__/ToastContext.test.tsx` — C-01 single-container assertion
- [ ] **Live SQL verify (Wave 0, gating DATA-06):** confirm `artifacts` ∈ `supabase_realtime` publication; if absent, apply `ALTER PUBLICATION supabase_realtime ADD TABLE public.artifacts;` (the "nothing works" footgun per RESEARCH.md finding #2)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real CI INSERT surfaces the pill + toast within seconds | DATA-06 | Live Supabase Realtime socket; no WebSocket-timing test double | UAT: trigger/await a CI billing run with the portal open; observe toast + pill |
| Keyboard nav: Tab order headers → filter chips → download → pill → toast dismiss | UI-03 | Requires real browser + keyboard | Developer walkthrough against UI-SPEC §Accessibility Contract |
| Screen reader announces pill `role="status"` (`aria-live="polite"`) on INSERT | UI-03 | jsdom does not implement ARIA live-region announcement | NVDA/VoiceOver walkthrough |
| Color-contrast pairs (slate-500/white = 4.6:1, white/brand-red = 5.1:1, …) | UI-03 | jsdom `color-contrast` axe rule is silently disabled | axe browser extension against the live UI-SPEC contrast pairs |
| Mobile card list renders correctly at 375px viewport | UI-01 | jsdom has no real viewport; breakpoint behavior needs a real browser | Responsive DevTools check at 375 / 768 / 1280px |
| `prefers-reduced-motion` eliminates animations | UI-02 | Requires OS-level setting toggle | DevTools "Emulate prefers-reduced-motion: reduce" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (jest-axe install + setup, 4 test files, publication SQL)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (after plans map every req to a verify)

**Approval:** pending
