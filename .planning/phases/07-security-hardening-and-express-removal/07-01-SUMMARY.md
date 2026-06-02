---
phase: 07-security-hardening-and-express-removal
plan: "01"
subsystem: portal-v2 / vercel-edge-headers
tags: [security, csp, security-headers, vercel, SEC-02, report-only]
dependency_graph:
  requires: []
  provides: [vercel-sec02-headers, csp-report-only-baseline]
  affects: [portal-v2/vercel.json]
tech_stack:
  added: []
  patterns: [vercel-headers-source-glob, csp-report-only-then-enforce]
key_files:
  created: []
  modified:
    - portal-v2/vercel.json
decisions:
  - "Ship Content-Security-Policy-Report-Only FIRST (D-04) — enforcing CSP flip deferred to plan 07-03 Task 2, gated on the live zero-violation walkthrough"
  - "Sentry region CONFIRMED US — connect-src uses https://*.ingest.sentry.io (no EU *.ingest.de.sentry.io needed); confirmed live via walkthrough step 7 (no ingest violation)"
  - "Ship BOTH X-Frame-Options: DENY AND CSP frame-ancestors 'none' (belt-and-suspenders for older browsers, RESEARCH Pitfall 3 / T-07-02-clickjack)"
  - "HSTS max-age=63072000; includeSubDomains — preload deliberately omitted (operator-only, permanent; D-03/A3)"
  - "headers source glob /(.*) covers ALL Vercel responses (assets + SPA catch-all); rewrites block left byte-for-byte intact"
metrics:
  duration: "~15 minutes (incl. human checkpoint wait)"
  completed: "2026-06-02"
  tasks_completed: 2
  files_modified: 1
---

# Phase 07 Plan 01: SEC-02 Security Headers + Report-Only CSP Summary

**One-liner:** Added the 4 named SEC-02 security headers (X-Frame-Options,
X-Content-Type-Options, Referrer-Policy, HSTS) plus a full allowlist
`Content-Security-Policy-Report-Only` to `portal-v2/vercel.json`, then verified
ZERO CSP Report-Only violations across all 7 origins on the live Vercel deploy —
unblocking the enforce-flip in plan 07-03.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add SEC-02 headers + Report-Only CSP to vercel.json | `d8c9344` | `portal-v2/vercel.json` |
| 2 | Manual zero-CSP-violation walkthrough against the live deploy (human-verify, blocking) | (observation-only; no file change — zero violations, no amendment needed) | `portal-v2/vercel.json` (observed only) |

---

## Final CSP Value Shipped (Report-Only)

Shipped on every Vercel response via the `"source": "/(.*)"` headers glob, as
`Content-Security-Policy-Report-Only` (NOT enforcing):

```
default-src 'self'; script-src 'self' https://hcaptcha.com https://*.hcaptcha.com; style-src 'self' https://hcaptcha.com https://*.hcaptcha.com; connect-src 'self' https://poeyztlmsawfoqlanucc.supabase.co wss://poeyztlmsawfoqlanucc.supabase.co https://*.ingest.sentry.io; frame-src https://hcaptcha.com https://*.hcaptcha.com; img-src 'self' data: blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'
```

**The 4 named SEC-02 headers shipped alongside it:**

| Header | Value |
|--------|-------|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` (no `preload`) |

**Sentry region CONFIRMED: US** — `connect-src` uses `https://*.ingest.sentry.io`.
No EU pattern (`https://*.ingest.de.sentry.io`) was required (confirmed live via
walkthrough step 7).

**The SPA rewrite is byte-for-byte intact:**
```json
{ "source": "/(.*)", "destination": "/index.html" }
```

---

## Task 1 Verification (automated)

- **Node JSON assertion** (plan `<verify>` block): `PASS: headers + Report-Only CSP + rewrite intact` — confirmed all 5 header keys present, CSP contains every required origin token (`frame-ancestors 'none'`, Supabase REST + Realtime wss, `*.hcaptcha.com`, `ingest.sentry.io`, `img-src 'self' data: blob:`), and rewrite destination `/index.html` unchanged.
- `grep -c "Content-Security-Policy-Report-Only"` = **1** (Report-Only present).
- `grep -c '"Content-Security-Policy"'` = **0** (enforcing form NOT shipped — deferred to 07-03).
- `grep -c "preload"` = **0** (HSTS preload NOT added).
- `cd portal-v2 && npm run build` — **exit 0** (`tsc -b && vite build`, 2294 modules, built in 4.25s). The vercel.json change does not break the build.

---

## Task 2 Walkthrough Outcome (live deploy — for 07-04's 07-SECURITY.md "Header Verification (SEC-02)")

**Verbatim outcome recorded by the operator (lift this block into 07-04's
`07-SECURITY.md` "Header Verification (SEC-02)" section):**

- The vercel.json change (commit `d8c9344`) was pushed to `origin/master` and promoted to production on Vercel by the operator.
- **Live-deploy 7-step zero-CSP-violation walkthrough: PASS.** ZERO `Content-Security-Policy-Report-Only` violations across all 7 steps:
  1. Logged-out redirect to `/login` — no violation, no 404.
  2. Login + Supabase REST (`https://poeyztlmsawfoqlanucc.supabase.co`) + Realtime websocket (`wss://poeyztlmsawfoqlanucc.supabase.co`) connect — no `connect-src` violation.
  3. Artifact table renders real rows — Supabase REST not blocked.
  4. Signed-URL download resolves — `img-src blob:` + Supabase Storage connect not blocked.
  5. hCaptcha challenge iframe + script load — no `frame-src`/`script-src` violation.
  6. `/dashboard/admin/users` (admin) — no violation.
  7. Sentry events still arriving — no `*.ingest.sentry.io` violation.
- **Sentry region CONFIRMED US:** no `*.ingest.sentry.io` violation appeared in step 7, so the default US `connect-src` token `https://*.ingest.sentry.io` is correct — NO change to the EU pattern needed.
- **Only non-CSP console message observed:** a benign browser-extension artifact ("A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received") on the users page. This is NOT a CSP violation (no "Refused to…"/"Content-Security-Policy directive" wording, no blocked origin) — it originates from a browser extension's content script, not the app or the headers. **Recorded as a non-issue.**

**Enforce-flip status:** This plan ships **Report-Only ONLY**. The flip to the
enforcing `Content-Security-Policy` (identical value, key renamed) is **deferred to
plan 07-03 Task 2** and is now **unblocked** by this passing walkthrough (D-04
prerequisite satisfied).

---

## Deviations from Plan

None — plan executed exactly as written. The CSP required no amendment because the
live walkthrough showed zero violations on the first deploy (US Sentry region was
correct by default; no EU re-run needed).

---

## Known Stubs

None. This plan adds CDN-edge response headers only — no UI components, data
sources, or placeholder values were introduced.

---

## Threat Flags

No new security-relevant surface beyond the plan's `<threat_model>`. This plan
MITIGATES T-07-02-clickjack, T-07-02-xss, T-07-02-mime, T-07-02-downgrade,
T-07-02-referrer-leak, and T-07-02-csp-breakage (Report-Only first), and
verifies T-07-02-sentry-region as US (events flow; no ingest violation).

---

## Self-Check: PASSED

- `portal-v2/vercel.json` — exists; contains `Content-Security-Policy-Report-Only`, all 5 header keys, intact `rewrites` block, no `preload`, no enforcing `"Content-Security-Policy"` key ✓
- Task 1 commit `d8c9344` exists ✓
- Node assertion `PASS`, build exit 0 ✓
- Task 2 live walkthrough recorded PASS (zero violations, US Sentry confirmed) ✓
