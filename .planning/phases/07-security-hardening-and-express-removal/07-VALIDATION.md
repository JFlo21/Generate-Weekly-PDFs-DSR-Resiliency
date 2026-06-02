---
phase: 07
slug: security-hardening-and-express-removal
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `07-RESEARCH.md` §"Validation Architecture". Plans attach
> concrete validation requirements per SEC requirement; this scaffold is
> populated by the planner with the real per-task map.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (portal-v2) + standalone Node/TS live-security probe in `scripts/` |
| **Config file** | `portal-v2/vitest.config.ts`; probe is run-standalone (no test runner) |
| **Quick run command** | `cd portal-v2 && npm test` |
| **Full suite command** | `cd portal-v2 && npm test && node scripts/<security-probe>.mjs` |
| **Estimated runtime** | ~30–60 seconds (unit) + live probe network latency |

---

## Sampling Rate

- **After every task commit:** Run `cd portal-v2 && npm test` (for portal-v2 edits)
- **After every plan wave:** Run the full suite + the live security probe against `poeyztlmsawfoqlanucc`
- **Before `/gsd-verify-work`:** Full suite green + live probe assertions all pass + live SPA smoke test
- **Max feedback latency:** ~60 seconds (unit) — live probe is gated to wave verification, not per-task

---

## Per-Task Verification Map

> Populated by the planner. Each SEC requirement maps to an observable check
> (see `07-RESEARCH.md` §Validation Architecture):
> SEC-01/05 → live probe assertions; SEC-02 → header-presence checks against the
> live Vercel deploy; SEC-03 → grep gates; SEC-04 → /security-review + gsd-secure-phase
> audit dispositions in 07-SECURITY.md; Express removal → post-removal SPA smoke test.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {N}-01-01 | 01 | 1 | SEC-{XX} | T-07-{XX} / — | {expected secure behavior} | {probe / grep / unit} | `{command}` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/<security-probe>` — live RLS/signed-URL assertions (anon key + pending-role JWT only; never service_role)
- [ ] `pending`-role test account provisioned + JWT acquisition path (per D-08; fixture vs pre-created user — planner's call)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One-time live sign-off recorded in 07-SECURITY.md | SEC-01, SEC-05 | Live-deploy human confirmation per D-07 | Run probe against live Vercel deploy; record outcome in 07-SECURITY.md |
| CSP Report-Only → enforce flip with zero console violations | SEC-02 | Requires observing the live app (Realtime ws, hCaptcha, Sentry, downloads, Vite assets) | Load live deploy, confirm zero CSP console violations, then flip header |
| /security-review checklist disposition | SEC-04 | Skill-driven audit + human sign-off on findings | Run /security-review + gsd-secure-phase 07; resolve HIGH/critical; document in 07-SECURITY.md |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
