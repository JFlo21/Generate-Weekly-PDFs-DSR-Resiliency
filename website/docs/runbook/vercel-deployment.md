---
id: vercel-deployment
title: Vercel deployment
sidebar_position: 8
---

# Vercel deployment

**Component ownership:** This deployment is owned by the Supabase web app
tier (`portal-v2`), deployed to Vercel — separate from the Python billing
pipeline (`generate_weekly_pdfs.py`). No changes to the Python pipeline are
involved.

This page documents how to connect the `portal-v2` frontend to Vercel
correctly, diagnose a "portal not connecting" failure, and confirm a healthy
live deployment.

---

## 1. Project settings (DEPLOY-01)

These three settings are the most common source of a failed or blank
deployment. All three must be set in the Vercel project.

**Where:** Vercel project → Settings → Build & Output Settings

| Setting | Value | Why |
|---------|-------|-----|
| Root Directory | `portal-v2` | The repository root has no Vite app. If Root Directory is wrong, Vercel finds nothing to build and the deployment silently produces a 404. This is the **prime suspect** for "portal not connecting." |
| Build Command | `npm run build` | Runs `tsc -b && vite build`. Vercel must run this inside `portal-v2/`, not at the repo root. |
| Output Directory | `dist` | Vite outputs to `portal-v2/dist/`. Vercel serves `dist/index.html` as the entry point. |

After changing Root Directory, trigger a new deployment (push or "Redeploy")
to apply the setting.

---

## 2. Environment variables (DEPLOY-03)

Vite bakes `VITE_*` variables into the client bundle at build time. Vercel
must supply them **before the build runs** — setting them after a build has
no effect; a redeploy is required.

**Where:** Vercel project → Settings → Environment Variables

Set all three variables for **BOTH Production AND Preview scopes**:

| Variable | Source | Scope |
|----------|--------|-------|
| `VITE_SUPABASE_URL` | Supabase project → Settings → API | Production + Preview |
| `VITE_SUPABASE_ANON_KEY` | Supabase project → Settings → API (anon/public key) | Production + Preview |
| `VITE_HCAPTCHA_SITEKEY` | hCaptcha dashboard (real sitekey for Production; test sitekey `10000000-ffff-ffff-ffff-000000000001` is acceptable for Preview only) | Production + Preview |

**Vercel scopes are independent.** Setting a variable on Production does
**not** automatically set it on Preview. A missing Preview variable causes
PR preview deployments to show the "Configuration error" screen (the
intended fail-loud behavior, not a bug — it confirms the ConfigError surface
is working correctly). Re-set the missing variable and redeploy to fix.

### Forbidden variable — absolute prohibition (DEPLOY-03, T-04-22)

`SUPABASE_SERVICE_ROLE_KEY` **MUST NOT exist in any Vercel env scope**
(Production, Preview, or Development).

The service_role key bypasses all Supabase Row Level Security. If it were
baked into the client bundle — which Vite would do for any `VITE_SUPABASE_SERVICE_ROLE_KEY`
var, or if it appears in the bundle via any other path — every visitor to
the portal URL would have unrestricted read/write access to the entire
database.

**Correct locations for service_role:**
- GitHub Actions Secrets only (for the CI publish step)
- Supabase project settings

**How to verify it is absent:** Vercel project → Settings → Environment
Variables → scan the full list for any key containing `SERVICE_ROLE`.
This check is part of the operator deployment confirmation (see section 5).

---

## 3. SPA rewrite (DEPLOY-02)

`portal-v2/vercel.json` contains the rewrite rule that makes deep links
and browser refreshes work on Vercel:

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

**Why this matters:** React Router handles routing client-side. If a user
refreshes on `/auth/reset` or navigates directly to `/admin/users`, Vercel
would normally return a 404 (no file exists at that path on disk). The
rewrite tells Vercel's CDN to serve `dist/index.html` for every path, and
React Router takes over from there.

This file is already committed to the repository. It requires no operator
action. Verify it is present with:

```bash
grep -c "index.html" portal-v2/vercel.json
# expected output: 1
```

---

## 4. Pre-deploy verification

Before deploying or after any code change, confirm the build is clean
locally. A green local run means a red Vercel build is almost always a
missing-env or Root-Directory misconfiguration, not a code problem.

```bash
cd portal-v2 && npm ci && npm run build && npm run lint && npm test
```

Expected results:
- `npm run build` exits 0 and produces `dist/index.html`
- `npm run lint` exits 0 (no ESLint warnings or errors)
- `npm test` exits 0 (all unit tests green)

**Phase 04 verified results (2026-05-31):**
- `npm run build`: EXIT 0 — `dist/index.html` produced (2237 modules, 2.46 s)
- `npm run lint`: non-functional — `eslint` is not in `devDependencies` and
  there is no ESLint config file. This is a **pre-existing gap** (not
  introduced by Phase 04). `tsc -b` (inside `npm run build`) and vitest
  (15 tests, 4 test files) serve as the equivalent type-checking and
  correctness gate. ESLint setup is deferred to Phase 07 (security hardening).
- `npm test`: EXIT 0 — 15 tests pass across AuthGuard, RoleGuard, UsersPage,
  and types (4 test files)

**Note on lint:** Until ESLint is added, `npm run lint` will fail with
"'eslint' is not recognized". This does not block a Vercel deployment —
Vercel only runs `npm run build`. Use `tsc -b` errors as the type gate.

---

## 5. Diagnosing "portal not connecting" (DEPLOY-04)

Work through this checklist in order — each item rules out the next:

1. **Root Directory wrong** → Vercel build produces nothing or a generic
   404. The Vercel build log shows no Vite output, or a "no framework
   detected" message. Fix: set Root Directory to `portal-v2` in Vercel
   project settings and redeploy.

2. **Missing `VITE_*` env vars** → The ConfigError "Configuration error"
   screen renders instead of the login page. This is the intended
   fail-loud behavior (not a blank page). Fix: set all three `VITE_*`
   variables for the affected scope (Production or Preview) and redeploy.

3. **Build failure** → The Vercel deployment dashboard shows a red build.
   Open the build log and look for `tsc` type errors or Vite errors.
   Reproduce locally with `cd portal-v2 && npm ci && npm run build`.

4. **Wrong domain or cross-host redirect** → The production URL resolves
   but auth calls fail. Verify `VITE_SUPABASE_URL` matches the correct
   Supabase project URL and that the Supabase project's Auth settings
   allow the Vercel domain.

**Healthy signal:** The login page renders at the production URL with the
hCaptcha widget visible (not the ConfigError screen, not a blank page).

---

## 6. Supabase redirect URLs (cross-reference)

The password-reset flow requires `https://<your-vercel-url>/auth/reset` to
be in the Supabase Auth Redirect URL allowlist. Without this, the reset
email link will fail with "Redirect URL not allowed."

Add both of the following to Supabase Auth → URL Configuration → Redirect URLs:
- `https://*.vercel.app/auth/reset` (covers all Preview deployments)
- `https://<your-production-domain>/auth/reset`

See [Auth & RBAC bootstrap](./auth-rbac-bootstrap.md) for the full
Supabase dashboard configuration checklist, including hCaptcha Bot
Protection setup.
