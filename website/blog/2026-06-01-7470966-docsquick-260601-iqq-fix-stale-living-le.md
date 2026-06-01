---
slug: 7470966-docsquick-260601-iqq-fix-stale-living-le
title: "docs(quick-260601-iqq): fix stale Living Ledger test file paths blocking pre-push gate (7470966)"
authors: [runbook-bot]
tags: [docs, other, portal, project, tests]
date: 2026-06-01T18:46:28.438823+00:00
---

**Branch:** `master` &middot; **Commit:** [`7470966`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/74709663a6bd86d04b1b657053db3e3f2c5604cd) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/26774848267).

<!-- truncate -->

## Commits in this push

- [`7470966`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/7470966) — docs(quick-260601-iqq): fix stale Living Ledger test file paths blocking pre-push gate
- [`65c18f6`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/65c18f6) — test(260601-iqq): fix stale ledger path and E-flag assertion
- [`233a389`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/233a389) — feat(04-06): run full pre-deploy gate; record verified results in runbook
- [`9720a27`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/9720a27) — feat(04-06): add Vercel deployment runbook and verify SPA rewrite
- [`66a0915`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/66a0915) — docs(04-05): complete RBAC integration wave plan — UsersPage, ActivityPage removal, auth routes
- [`5980d78`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/5980d78) — feat(04-05): wire App.tsx — auth routes + RoleGuard around /admin/users
- [`3c98727`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3c98727) — feat(04-05): delete ActivityPage + remove dead route, nav entry, and types (D-14)
- [`ee7cdbf`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/ee7cdbf) — feat(04-05): reconcile UsersPage — roles, last-admin guard, pending highlight, states
- [`c2a75a5`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/c2a75a5) — test(04-05): add failing test for UsersPage last-admin guard (RBAC-04)
- [`fad861b`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/fad861b) — docs(04-04): complete auth UI pages plan — hCaptcha, forgot/reset/pending pages
- [`7595217`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/7595217) — feat(04-04): create ResetPasswordPage — PASSWORD_RECOVERY gate + updateUser
- [`4916197`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/4916197) — feat(04-04): create ForgotPasswordPage and PendingApprovalPage
- [`96e157f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/96e157f) — feat(04-04): extend LoginPage — hCaptcha, remember-me, forgot link, fix signup→/pending
- [`6617d01`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/6617d01) — docs(04-03): complete auth core plan — useAuth extended, AuthGuard hardened, RoleGuard created
- [`ac709e6`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/ac709e6) — feat(04-03): create RoleGuard with inline 403 for disallowed roles (RBAC-05, D-16)
- [`a5b9c9b`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a5b9c9b) — test(04-03): add failing RoleGuard tests for inline 403 and allow-list (RBAC-05)
- [`c3995c1`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/c3995c1) — feat(04-03): harden AuthGuard — remove USE_MOCK bypass, add pending-role routing
- [`ec9cf9f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/ec9cf9f) — test(04-03): add failing AuthGuard tests for pending routing and USE_MOCK removal (AUTH-06)
- [`2e348c2`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/2e348c2) — feat(04-03): extend useAuth with captcha, remember-me, resetPassword, role helpers
- [`5c757b8`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/5c757b8) — docs(phase-04): update tracking after wave 1 (recover 04-01)
- [`6e2c6ee`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/6e2c6ee) — docs(04-01): add foundation plan summary
- [`735e7ac`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/735e7ac) — chore(04-01): install hCaptcha widget and document VITE_HCAPTCHA_SITEKEY
- [`49a5247`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/49a5247) — feat(04-01): add ConfigError surface and gate main.tsx on isConfigured
- [`1723bdf`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/1723bdf) — feat(04-01): replace supabase.ts with fail-loud factory + Remember-Me swap
- [`68f7bb7`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/68f7bb7) — feat(04-01): reconcile types.ts to deployed schema (D-01/D-02)
- [`816705c`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/816705c) — test(04-01): add failing types contract test for D-01/D-02
- [`ab8f970`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/ab8f970) — chore(04-01): add vitest test infrastructure to portal-v2
- [`bac881e`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/bac881e) — docs(04-02): add auth/RBAC bootstrap runbook page
- [`f30f010`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/f30f010) — feat(04-02): append idempotent Phase 04 DDL to portal_schema.sql
- [`4e3829a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/4e3829a) — docs(04): record planning completion (6 plans, ready to execute)
- [`8a8faa4`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/8a8faa4) — docs(04): cite CONTEXT decisions in plan must_haves
- [`b23fa35`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/b23fa35) — docs(04): create phase plan (6 plans, 5 waves)
- [`ddf0b32`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/ddf0b32) — docs(04): add validation strategy
- [`a306758`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a306758) — docs(04): research phase domain — auth, RBAC, and deployment
- [`3e44ad3`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3e44ad3) — docs(04): approve UI design contract (6/6 dimensions PASS)
- [`72fd320`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/72fd320) — docs(04): fix UI-SPEC typography to 2-weight contract
- [`0265860`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/0265860) — docs(04): UI design contract for auth, RBAC, and deployment
- [`b8e8f4f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/b8e8f4f) — docs(state): record phase 04 context session
- [`b275947`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/b275947) — docs(04): capture phase context

## Changed files

### Tests

- `tests/test_subcontractor_pricing.py`
- `tests/test_subproject_e_hash_store.py`

### Portal v2 (React)

- `portal-v2/.env.example`
- `portal-v2/package-lock.json`
- `portal-v2/package.json`
- `portal-v2/src/App.tsx`
- `portal-v2/src/components/admin/ActivityPage.tsx`
- `portal-v2/src/components/admin/UsersPage.tsx`
- `portal-v2/src/components/admin/__tests__/UsersPage.test.tsx`
- `portal-v2/src/components/auth/AuthGuard.tsx`
- `portal-v2/src/components/auth/ForgotPasswordPage.tsx`
- `portal-v2/src/components/auth/LoginPage.tsx`
- `portal-v2/src/components/auth/PendingApprovalPage.tsx`
- `portal-v2/src/components/auth/ResetPasswordPage.tsx`
- `portal-v2/src/components/auth/RoleGuard.tsx`
- `portal-v2/src/components/auth/__tests__/AuthGuard.test.tsx`
- `portal-v2/src/components/auth/__tests__/RoleGuard.test.tsx`
- `portal-v2/src/components/layout/Navbar.tsx`
- `portal-v2/src/components/layout/Sidebar.tsx`
- `portal-v2/src/components/ui/ConfigError.tsx`
- `portal-v2/src/hooks/useAuth.ts`
- `portal-v2/src/lib/__tests__/types.test.ts`
- `portal-v2/src/lib/supabase.ts`
- `portal-v2/src/lib/types.ts`
- `portal-v2/src/main.tsx`
- `portal-v2/src/test/setup.ts`
- `portal-v2/vitest.config.ts`

### Docs site

- `website/docs/runbook/auth-rbac-bootstrap.md`
- `website/docs/runbook/vercel-deployment.md`

### Project docs

- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-01-PLAN.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-01-SUMMARY.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-02-PLAN.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-02-SUMMARY.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-03-PLAN.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-03-SUMMARY.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-04-PLAN.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-04-SUMMARY.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-05-PLAN.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-05-SUMMARY.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-06-PLAN.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-CONTEXT.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-DISCUSSION-LOG.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-PATTERNS.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-RESEARCH.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-UI-SPEC.md`
- `.planning/phases/04-auth-rbac-and-deployment/04-VALIDATION.md`
- `.planning/quick/260601-iqq-fix-stale-living-ledger-test-file-paths-/260601-iqq-PLAN.md`
- `.planning/quick/260601-iqq-fix-stale-living-ledger-test-file-paths-/260601-iqq-SUMMARY.md`

### Other

- `supabase/portal_schema.sql`
