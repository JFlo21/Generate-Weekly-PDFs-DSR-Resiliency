---
phase: 04-auth-rbac-and-deployment
plan: 06
type: execute
status: complete
completed: 2026-06-01
requirements: [DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04]
commits:
  - 860af87  # Task 1: vercel.json SPA rewrite + service_role grep + deployment runbook
  - ef4fd07  # Task 2: full pre-deploy build/test gate
closes_phase: true
---

# 04-06 SUMMARY — Vercel Deployment Correctness (DEPLOY-01..04)

**This plan closes Phase 04 (Auth, RBAC, and Deployment).**

## What was delivered

### Task 1 — SPA rewrite + service_role grep + runbook (`860af87`)
- `portal-v2/vercel.json` confirmed to contain the SPA rewrite
  (`/(.*) -> /index.html`) so deep links don't 404 (DEPLOY-02).
- `grep -rni service_role portal-v2/src` → **0 matches** — no service_role key in
  the frontend (DEPLOY-03; the anon key is the only Supabase key in the bundle,
  RLS is the data guard).
- `website/docs/runbook/vercel-deployment.md` created: Root Directory = `portal-v2`,
  build `npm run build`, output `dist`, per-scope `VITE_*` env-var matrix,
  `SUPABASE_SERVICE_ROLE_KEY` prohibition, and the DEPLOY-04 "not connecting"
  diagnosis checklist.

### Task 2 — pre-deploy build gate (`ef4fd07`)
- `npm run build` (`tsc -b && vite build`) exits 0; `dist/index.html` produced.
- Unit tests green (`npm test`).
- **Caveat (honest):** `npm run lint` is **non-functional** — `eslint` is not a
  declared devDependency and there is no eslint config in `portal-v2` (no
  `node_modules/.bin/eslint`, no `eslint.config.*`). This is a pre-existing
  tooling gap, not a code defect. Type-safety is still enforced via `tsc -b`
  (exit 0). Wiring up ESLint is logged as a candidate follow-up quick task.

### Task 3 — operator deployment checkpoint (blocking) — RESOLVED 2026-06-01
Completed live with the operator (this session):
- **Vercel project config** correct — the production build is `READY` and serves
  the real app bundle, confirming Root Directory / build command / output dir
  (DEPLOY-01).
- **Env vars** `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_HCAPTCHA_SITEKEY`
  set on **both** Production and Preview scopes (operator-confirmed).
- **Latest `master` build promoted to Production** and **Production Branch = master**
  (durable auto-promote going forward).
- **Vercel Authentication (Deployment Protection) DISABLED** — root cause of the
  long-standing DEPLOY-04 "not connecting" symptom. The project has no custom
  domain, so Standard Protection kept the production `*.vercel.app` URL 401-gated
  for end users; disabling Vercel Authentication makes Production public. The
  portal's own Supabase login + RLS remain the real security boundary.

## Verification evidence (DEPLOY-01/02/04)

Unauthenticated fetch of the production URL
(`generate-weekly-pd-fs-dsr-linetec-resiliency-project-s-projects.vercel.app`),
i.e. exactly how an end user hits it — **before** the fix all paths returned `401`;
**after** disabling Vercel Authentication:

| Path | Status | Result |
|------|--------|--------|
| `/` | 200 | title "Linetec Report Portal", `<div id="root">`, `/assets/index-DM4ShKVg.js` |
| `/auth/reset` | 200 | same SPA shell — **SPA rewrite works, no 404** |
| `/dashboard/admin/users` | 200 | same SPA shell — deep link resolves, no 404 |

Plus, proven earlier this session:
- **Login works end-to-end** — operator authenticated and reached the dashboard
  (admin) on the live project (`auth.users.last_sign_in_at` = 2026-06-01).
- **Password reset works end-to-end** (AUTH-04 / success criterion 6) — operator
  reset their password via the corrected `{{ .RedirectTo }}` + token_hash flow
  (portal change shipped as quick task 260601-k34) and signed in.
- **First-admin bootstrap** applied: `juflores@ltspower.com` → `role=admin` in the
  live project `poeyztlmsawfoqlanucc` (the account predated the signup trigger, so
  it had no profile row — created via INSERT).

## must_haves — status

- ✅ `service_role` absent from `portal-v2` source + documented as forbidden.
- ✅ `vercel.json` SPA rewrite present and verified (live deep links 200).
- ✅ Deployment runbook documents Root Directory, build command, output dir,
  per-scope env vars, and the DEPLOY-04 diagnosis flow.
- ✅ Deployed portal serves at its URL, deep links do not 404, ConfigError surface
  remains the fail-loud path for missing env.

## Phase 04 — closure

All six plans (04-01..04-06) complete. Auth gate (hCaptcha login/signup/reset),
`profiles`-backed RBAC (admin/billing/pending), admin user management with
last-admin guard, and a correctly connected public Vercel deployment are all
verified working end-to-end on production.

## Carried into Phase 05

- The portal still shows **sample data** because `portal-v2/src/lib/api.ts` reads
  the removed Express `/api`, not Supabase. The live project
  (`poeyztlmsawfoqlanucc`) already holds **2,383 real artifact rows** (cron publish
  working). Phase 05 must rewrite `getRuns`/`getArtifacts`/`search`/downloads to
  read Supabase directly (`supabase.from('artifacts')` + `createSignedUrl`).
- Follow-up candidate: wire ESLint into `portal-v2` (currently a no-op script).
- Branding quick task pending: `linetec-services-logo.png` is staged in
  `portal-v2/public/` awaiting wiring (Phase 06 / parallel).
