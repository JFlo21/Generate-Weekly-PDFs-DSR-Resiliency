# Daily Code Review & Code Quality Check — 2026-11-26

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-idn0fm` (even with `master` + 2 docs commits)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code since the last review (pipeline corrections + foreman-notes holds), then a live auth/security verification of `portal-v2/` + the shared Supabase project.

---

## 1. Executive Summary

**No application code shipped in the daily window.** The last substantive code commit is
`e385504` (`fix(foreman-notes): hold pilot groups whose notes token failed`, #450) from
**2026-11-05**. Every commit in the 21 days since is an automated `docs(runbook)` update from
the Notion Worker. Today's review therefore covers (a) the Python changes that landed since the
previous (2026-10-20) review — `#444`, `#447`, `#450`, `#451`, which are the focus here — and
(b) a state-of-repo security verification weighted to the portal auth flow the task flags.
**Scope caveat (per PR review):** the foreman-notes GF-pilot *feature* itself landed as `#437`
(`85fac23`, 2026-10-30), also after the last review; this run examined its follow-up hardening
(`#444`, `#450`) and the reporting-corrections feature (`#447`/`#451`) in depth, but did **not**
re-review the full `#437` feature diff — so the "safe" read below applies to what was reviewed,
not a blanket clearance of every post-10-20 production change.

**Overall health: good.** `py_compile` is clean on `generate_weekly_pdfs.py`,
`pipeline/reporting_corrections.py`, `pipeline/orchestrate.py`, and `pipeline/foreman_notes.py`.
The new reporting-corrections subsystem (#447, 1,950 lines in one cohesive module) and its
fail-closed hardening (#451) are careful, defensive, and notably PII-conscious — path
traversal is guarded, failure paths drop the file path from captured frame locals, and no
person's name reaches logs. The foreman-notes token-hold (#450) and GF-lookup hold (#444)
correctly fail closed without ever publishing a hash that is missing its notes fingerprint.

**The headline new result:** the prior review (2026-10-20) left as *"needs verification"* whether
the portal's row-level-security schema was actually applied to the live Supabase project. **I
verified it directly this run** — RLS on `public.profiles` is enabled and **default-deny**, with
only two policies: admin-only writes and self-read. A non-admin **cannot** escalate their own
`role` through the browser client. The client-side `RoleGuard`/`canDemote` checks are confirmed
to be UX, properly backstopped server-side. This closes the single biggest open auth question.

One **confirmed Medium** did surface in the portal, though: a sole admin can delete their own
`profiles` row and lock everyone out (no `BEFORE DELETE` guard — verified live, §2). Everything else
is Medium/Low hardening plus an **operational backlog** worth a glance: nine unmerged `docs(review)`
daily-review PRs and several stale security-relevant Dependabot PRs are accumulating.

**Verdict: Safe to merge (billing pipeline)** — nothing in the review window is broken and the core
auth backstop is confirmed — but fix the confirmed last-admin-DELETE portal gap and the other Medium
items (see the Daily Verdict) as follow-ups.

---

## 2. Top Findings

### [Low] `anon`/`authenticated` hold a needless EXECUTE grant on SECURITY DEFINER trigger functions
- **Where:** Supabase project `poeyztlmsawfoqlanucc` (the portal's DB) — `public.handle_new_user()`,
  `public.prevent_last_admin_demotion()` (Supabase security advisor `0028`/`0029`).
- **Problem:** Both are trigger functions (they return `trigger`), and Supabase's advisor flags that
  `anon`/`authenticated` have an EXECUTE grant on them. **Correction (per PR review):** PostgREST does
  **not** expose `trigger`-returning functions as RPC, so — contrary to the advisor's `/rest/v1/rpc/…`
  wording — they are almost certainly **not** reachable as REST endpoints. The actionable item is the
  stray EXECUTE grant itself, not a live RPC surface. *Needs verification:* confirm PostgREST returns
  404 for `POST /rest/v1/rpc/handle_new_user` on this project.
- **Why it matters:** Low. There is no legitimate caller for these grants, so removing them is clean
  least-privilege hardening; the practical exposure today is negligible.
- **Fix:** Revoke the unused EXECUTE grant. **Must include `PUBLIC`** — Postgres grants `EXECUTE`
  on new functions to `PUBLIC` by default, so `anon`/`authenticated` keep inherited access if only
  their direct grants are revoked (this is what Supabase's own advisor remediation does):
  ```sql
  REVOKE EXECUTE ON FUNCTION public.handle_new_user()            FROM PUBLIC, anon, authenticated;
  REVOKE EXECUTE ON FUNCTION public.prevent_last_admin_demotion() FROM PUBLIC, anon, authenticated;
  ```
  (`public.current_user_role()` being callable is fine — it only returns the caller's own role.)

### [Medium] Weak password policy — only the 6-char Supabase default, set no higher
- **Where:** `portal-v2/src/components/auth/LoginPage.tsx:137`,
  `ResetPasswordPage.tsx:118,148` (client `minLength={6}`).
- **Problem:** The client `minLength={6}` is cosmetic, **but** — correction per PR review — Supabase
  Auth does enforce a server-side minimum, so a sub-6-char password is rejected regardless of the
  client. The real gap is that the policy sits at Supabase's **default floor of 6** with no stronger
  requirement (no raised minimum, no leaked-password protection observed).
- **Why it matters:** A 6-char minimum is weak for a billing/admin portal; it should be raised and
  backed by leaked-password protection, enforced server-side where it can't be bypassed.
- **Fix:** In the Supabase Auth dashboard → *Authentication → Policies*, raise the minimum password
  length (≥8) and enable leaked-password protection; raise the client `minLength` to match. This is a
  config change, not a code change.

### [Medium] Stale security-relevant Dependabot PRs
- **Where:** open PRs `#427` (pillow 12.3.0 → 13.0.0), `#324` (pandas 2 → 3, major),
  `#424`/`#425` (react/react-dom 18 → 19 on `/website`, major), `#323` (pytest-cov 6 → 7),
  `#456`/`#452`/`#414` (portal/scripts npm bumps).
- **Problem:** Security-relevant dependencies are behind, and **four are major-version bumps** —
  `pillow 12 → 13` (typically carries CVE fixes), `pandas 2 → 3`, `react 18 → 19`, and
  `pytest-cov 6 → 7` — plus the npm patch bumps. (Correction per PR review: `pillow 12 → 13` **and**
  `pytest-cov 6 → 7` are *major* bumps, not patches.)
- **Why it matters:** `pillow` and `pandas` run inside the production Excel pipeline; unreviewed
  **major** bumps can silently break it. `pytest-cov` is dev-only (lower blast radius) but is still a
  major and shouldn't be treated as a routine patch.
- **Fix:** Triage this week — merge only the npm patch bumps after CI; gate every major
  (`pillow 13`, `pandas 3`, `react 19`, `pytest-cov 7`) behind a focused compatibility/test pass,
  don't auto-merge.

### [Low] `website/vercel.json` sets no security headers
- **Where:** `website/vercel.json` (Docusaurus docs site).
- **Problem:** The portal (`portal-v2/vercel.json`) ships a full CSP + HSTS + `X-Frame-Options`
  header set; the docs site ships none.
- **Why it matters:** Low — it serves static public docs with no auth — but HSTS and
  `X-Content-Type-Options: nosniff` are free hardening.
- **Fix:** Mirror the non-CSP headers (`Strict-Transport-Security`, `X-Content-Type-Options`,
  `Referrer-Policy`, `X-Frame-Options: DENY`) into `website/vercel.json`.

### [Medium · CONFIRMED this run] A sole admin can delete their own `profiles` row → portal lockout
- **Where:** `public.profiles` (live DB) + `portal-v2/src/components/admin/UsersPage.tsx`.
- **Problem:** Verified against the live DB this run — the only trigger on `profiles` is
  `check_last_admin`, defined **`BEFORE UPDATE` only** (`EXECUTE FUNCTION prevent_last_admin_demotion()`);
  there is **no `BEFORE DELETE` trigger and no DELETE-denying policy**. The `profiles_admin_all` policy
  grants cmd `ALL` to admins, so an admin is authorized to **DELETE their own profile row**. When they
  are the last admin, that leaves the portal with no administrator able to promote anyone — a lockout.
  (Upgraded from the prior "needs-verification Low": the demotion guard genuinely does not cover DELETE.)
- **Why it matters:** Irreversible loss of all admin access (recoverable only via `service_role`/SQL).
- **Fix:** Add a `BEFORE DELETE` trigger mirroring `prevent_last_admin_demotion`, or a DELETE-denying
  RLS policy for the last-admin case (concurrency-safe count).

### [Low · carry-over — needs verification] Other portal auth bugs from the 2026-10-20 review
- **Where:** `portal-v2/src/hooks/useAuth.ts`, `UsersPage.tsx` — **unchanged since that review**
  (no `portal-v2/src` commits in between).
- **Problem:** The prior review flagged a "Remember me"-off same-tab-refresh logout and a swallowed
  `signOut()` error. Code is unchanged, so they likely still stand.
- **Why it matters:** Availability/UX on the auth flow.
- **Fix:** Confirm whether these were addressed; if not, carry them into the portal-v2 backlog.

---

## 3. Code Quality Improvements

- **`pipeline/reporting_corrections.py` is cohesive but large (1,950 lines).** Per
  `.claude/rules/python-module-architecture.md`, treat line count as a review signal: the
  parse/validate layer, the run-lifecycle seams (`prepare_run`, `register_displaced`,
  `apply_credit_overrides`), and the CLI are three separable responsibilities. Not urgent — the
  module is well-organized and single-purpose — but flag for extraction before the *next* new
  responsibility lands in it.
- **`apply_credit_overrides` (`reporting_corrections.py:1640`) is correctly non-mutating** — it
  copies stamped rows rather than touching the shared dicts and pops them from the frozen-claimer
  maps so a correction always wins. Good pattern; no change needed.
- **Broad `except Exception` with `# noqa: BLE001` is heavily used** across `foreman_notes.py`
  (the never-raises helpers). It is intentional and documented (fail-closed/fail-safe), but it is
  dense enough that a real bug inside one of these helpers would be silently swallowed. Consider a
  single debug-level log line in the `except` arms so swallowed errors are at least observable.
- **Supabase advisor `0011` (mutable `search_path`)** on 5 functions incl.
  `public.smartsheet_*_audit` and `public.project_list_audit` — add `SET search_path = ''` (or an
  explicit schema) to each `CREATE FUNCTION` for determinism/hardening.

## 4. Security Review

- **CONFIRMED GOOD — `profiles` RLS is a real server-side boundary.** Live policies on
  `public.profiles`: `profiles_admin_all` (cmd `ALL`, `USING`/`WITH CHECK` =
  `current_user_role() = 'admin'`) and `profiles_self_read` (cmd `SELECT`, `auth.uid() = id`).
  No UPDATE policy exists for non-admins, and RLS is default-deny → **self-role-escalation is not
  possible via the anon client.** Client guards (`AuthGuard`, `RoleGuard`, `canDemote`) are UX only
  and are correctly backstopped.
- **CONFIRMED CLEAN (from the source scan):** no XSS sinks (`dangerouslySetInnerHTML`/`innerHTML`/
  `eval` absent across `portal-v2/**` + `website/**`); no `service_role` key or hardcoded secret in
  any frontend/committed env file; only `VITE_SUPABASE_ANON_KEY` is used client-side; portal CSP is
  clean (no `unsafe-inline`/`unsafe-eval`). Forgot-password
  avoids user enumeration (`ForgotPasswordPage.tsx:25-28`).
- **[Low · needs verification — correction per PR review] hCaptcha missing from CSP `connect-src`.**
  Verified against `portal-v2/vercel.json`: `connect-src` is `'self'` + the Supabase hosts + Sentry
  only — hCaptcha appears in `script-src`/`style-src`/`frame-src` but **not** `connect-src`. hCaptcha's
  own guidance asks for `https://hcaptcha.com` + `https://*.hcaptcha.com` in `connect-src`. In config­
  urations where the challenge makes a page-governed XHR, this could block token generation and the
  token-gated login/signup/reset submits. (This reopens the prior review's hCaptcha-login concern.)
  *Verify* against a live preview before deciding; if it reproduces, add the two hosts to `connect-src`.
- **Token storage:** Supabase JWT lives in `localStorage` (default; JS-readable). Standard for a
  Supabase SPA and mitigated by the clean CSP + zero XSS sinks — accept as-is unless a cookie-based
  session is ever adopted.
- **No MFA/2FA** on any role, including `admin`. For a billing/admin portal, consider enabling
  Supabase MFA (TOTP) at least for the admin role. (Medium-Low; roadmap item.)
- **[ERROR — cross-project, not this repo] SECURITY DEFINER views.** Advisor `0010` flags 6
  `promax_engine.*` views as `SECURITY DEFINER`. That schema belongs to the sibling
  *Promax Portal* app (repo `supabase-smartsheet-promax-offload`), which shares this Supabase
  project. It is a real ERROR-level finding but should be fixed in that repo, not here — noted for
  routing. The views bypass RLS and run as their creator; they should be recreated
  `SECURITY INVOKER` (PG15+ `WITH (security_invoker=on)`).
- **Housekeeping — `rls_enabled_no_policy` (advisor `0008`, 24 tables):** RLS-on-no-policy is
  fail-safe (default-deny; only `service_role` reaches them), so not a vulnerability. Some look like
  snapshot tables (`backup.scorecard_*_20261117`, `linetec_uploader.dedup_backup_20260525`) that may
  be droppable to cut advisor noise — **but do not DROP on this evidence alone.** This is a shared
  live project, `scorecard_*_20261117` is only ~9 days old, and this review establishes no ownership,
  retention, or dependency facts. Route candidates to their owner and verify retention/backups first.

## 5. Testing Gaps

- **Test suite could not be executed in this review container.** The only interpreter with
  `pytest` available is Python 3.13, and the pinned `pandas` (requirements.txt) has no cp313 wheel
  and fails to compile from source there (`standard attributes in middle of decl-specifiers`). This
  is an environment/toolchain mismatch, **not** a product defect — CI (on a compatible Python 3.11/
  3.12) is the authority. `py_compile` passed on all four changed modules. *Needs verification:* run
  `pytest tests/ -v` in CI/local to confirm green. (Side note: this reinforces the `pandas 3` bump in
  PR #324 — the pin is now behind the available wheels.)
- The changed code is well-covered by the authors' own RED-first suites: `#450` added 19 tests
  with pinned master hashes + AST placement; `#451` added `tests/test_reporting_corrections.py`
  (249 lines). No net-new gap introduced by these PRs.
- **Portal auth has no automated test for the RLS boundary.** The most valuable missing test is a
  negative one: an `authenticated` (non-admin) client attempting `profiles.update({ role: 'admin' })`
  must be rejected. Today that guarantee is verified only manually (as in this review). Add a
  Supabase RLS integration test (or a `pgTAP`/SQL assertion) so a future policy edit can't silently
  open it.
- **Last-admin DELETE** (§2, confirmed) has no test; add one alongside the DELETE guard.

## 6. Suggested Next Actions

1. **Guard last-admin DELETE on `profiles`** (§2, confirmed) — add a `BEFORE DELETE` trigger or a
   DELETE-denying RLS policy so a sole admin can't lock everyone out. Highest security value.
2. **Raise the password policy + optional admin MFA** in the Supabase Auth dashboard (min ≥8 +
   leaked-password protection; the current floor is Supabase's default 6); raise client `minLength`
   to match.
3. **Revoke the unused `EXECUTE`** grant (incl. `PUBLIC`) on `handle_new_user()` /
   `prevent_last_admin_demotion()` (§2) — least-privilege cleanup; low urgency (likely not
   RPC-reachable, verify).
4. **Triage the Dependabot backlog:** merge only the npm patch bumps after CI; gate every major
   (`pillow 13`, `pandas 3`, `react 19`, `pytest-cov 7`) behind a focused compatibility/test pass.
5. **Clear the review-PR backlog:** nine `docs(review)` PRs (#422–#446) are open and unmerged —
   merge or close them so the daily routine isn't piling up stale branches.
6. **Add the RLS negative test** for `profiles.role` self-escalation (§5) so the server-side
   boundary is CI-guarded.
7. **Route the `promax_engine` SECURITY DEFINER view ERROR** to the `supabase-smartsheet-promax-offload`
   repo owners (§4) — it's not this repo's code. Set explicit `search_path` on the flagged functions
   (§3). Do **not** drop the RLS-no-policy `backup.*` tables without owner/retention verification (§4).

---

## Daily Verdict

**Safe to merge (billing pipeline) — but the portal has a confirmed Medium to fix.** No code shipped
in the review window, and the reviewed changes (#444/#447/#450/#451) are production-safe, fail-closed,
and PII-conscious; the billing cron is unaffected. The portal's core authorization boundary is correct
— a non-admin cannot self-escalate (verified live). **However, this run confirmed a portal availability
risk: a sole admin can delete their own `profiles` row and lock everyone out (no `BEFORE DELETE`
guard).** That is a real Medium that should be fixed before relying on the portal's admin model, though
it does not touch the billing pipeline. Everything else is Medium/Low hardening or operational backlog.
Next follow-ups: the last-admin DELETE guard (§2), the password policy (§2), and the Dependabot
major-bump triage (§2). (Scope caveat in §1: the `#437` foreman-notes feature diff was not fully
re-reviewed this run.)
