# Daily Code Review & Code Quality Check — 2026-11-26

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-idn0fm` (even with `master` + 2 docs commits)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code since the last review (pipeline corrections + foreman-notes holds), then a live auth/security verification of `portal-v2/` + the shared Supabase project.

---

## 1. Executive Summary

**No application code shipped in the daily window.** The last substantive code commit is
`e385504` (`fix(foreman-notes): hold pilot groups whose notes token failed`, #450) from
**2026-11-05**. Every commit in the 21 days since is an automated `docs(runbook)` update from
the Notion Worker. Today's review therefore covers (a) the four Python changes that landed
since the previous review's window — `#444`, `#447`, `#450`, `#451` — and (b) a state-of-repo
security verification weighted to the portal auth flow the task flags.

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

Remaining items are all **Medium/Low hardening**, plus an **operational backlog** worth a glance:
nine unmerged `docs(review)` daily-review PRs and several stale security-relevant Dependabot PRs
are accumulating.

**Verdict: Safe to merge** (see §7) — nothing in the review window is broken, and the auth
backstop is confirmed. Address the Medium items as follow-ups.

---

## 2. Top Findings

### [Medium] SECURITY DEFINER trigger functions are callable by `anon`/`authenticated` over REST
- **Where:** Supabase project `poeyztlmsawfoqlanucc` (the portal's DB) — `public.handle_new_user()`,
  `public.prevent_last_admin_demotion()` (Supabase security advisor `0028`/`0029`).
- **Problem:** Both are trigger functions but are exposed as PostgREST RPC endpoints
  (`/rest/v1/rpc/handle_new_user`, `/rest/v1/rpc/prevent_last_admin_demotion`) executable by the
  `anon` and `authenticated` roles.
- **Why it matters:** These should only ever run inside their triggers. Direct RPC invocation is
  an unintended surface. Real-world risk is low today (both read `NEW`, which is `NULL` outside a
  trigger, so a direct call errors out), but it is attack surface with no legitimate caller.
- **Fix:** Revoke REST execute on both:
  ```sql
  REVOKE EXECUTE ON FUNCTION public.handle_new_user()            FROM anon, authenticated;
  REVOKE EXECUTE ON FUNCTION public.prevent_last_admin_demotion() FROM anon, authenticated;
  ```
  (`public.current_user_role()` being callable is fine — it only returns the caller's own role.)

### [Medium] Password policy enforced only client-side (`minLength={6}`)
- **Where:** `portal-v2/src/components/auth/LoginPage.tsx:137`,
  `ResetPasswordPage.tsx:118,148` (client attribute only; no server policy observed).
- **Problem:** The 6-char minimum is a browser `minLength` attribute. A direct Supabase Auth call
  (or a modified client) can set a 1-char password.
- **Why it matters:** Password strength for a billing/admin portal should be enforced where it
  can't be bypassed.
- **Fix:** Set the minimum password length (and leaked-password protection) in the Supabase Auth
  dashboard → *Authentication → Policies*; raise the client `minLength` to match (≥8). This is a
  config change, not a code change.

### [Medium] Stale security-relevant Dependabot PRs
- **Where:** open PRs `#427` (pillow 12.3.0 → 13.0.0), `#324` (pandas 2 → 3, major),
  `#424`/`#425` (react/react-dom 18 → 19 on `/website`, major), `#323` (pytest-cov 6 → 7),
  `#456`/`#452`/`#414` (portal/scripts npm bumps).
- **Problem:** Image/data libraries used in the billing pipeline are a patch release behind,
  including a Pillow major bump that typically carries CVE fixes.
- **Why it matters:** `pillow` and `pandas` run inside the production Excel pipeline; unreviewed
  major bumps (`pandas 3`) can also silently break it.
- **Fix:** Triage this week — merge the low-risk patch bumps (pillow, pytest-cov) after CI;
  schedule the `pandas 3` / `react 19` majors behind a focused test pass, don't auto-merge.

### [Low] `website/vercel.json` sets no security headers
- **Where:** `website/vercel.json` (Docusaurus docs site).
- **Problem:** The portal (`portal-v2/vercel.json`) ships a full CSP + HSTS + `X-Frame-Options`
  header set; the docs site ships none.
- **Why it matters:** Low — it serves static public docs with no auth — but HSTS and
  `X-Content-Type-Options: nosniff` are free hardening.
- **Fix:** Mirror the non-CSP headers (`Strict-Transport-Security`, `X-Content-Type-Options`,
  `Referrer-Policy`, `X-Frame-Options: DENY`) into `website/vercel.json`.

### [Low · carry-over — needs verification] Portal auth bugs from the 2026-10-20 review still stand
- **Where:** `portal-v2/src/hooks/useAuth.ts`, `UsersPage.tsx` — **unchanged since that review**
  (no `portal-v2/src` commits in between).
- **Problem:** The prior review flagged a "Remember me"-off same-tab-refresh logout, a swallowed
  `signOut()` error, and a **last-admin self-DELETE** gap (the DB trigger
  `prevent_last_admin_demotion` guards role *demotion* via UPDATE, but a last-admin **row DELETE**
  is a separate path and should be confirmed blocked).
- **Why it matters:** Availability/UX and a potential lock-everyone-out edge on the admin role.
- **Fix:** Confirm whether these were addressed; if not, carry them into the portal-v2 backlog.
  For the DELETE gap, verify with an RLS/trigger test or add a `BEFORE DELETE` guard mirroring the
  demotion trigger.

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
  clean (no `unsafe-inline`/`unsafe-eval`) and includes `hcaptcha` in `connect-src`. Forgot-password
  avoids user enumeration (`ForgotPasswordPage.tsx:25-28`).
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
  fail-safe (default-deny; only `service_role` reaches them), so not a vulnerability. But several
  are stale `backup.*` snapshots (`scorecard_*_20261117`, `dedup_backup_20260525`) — drop them to
  cut clutter and the advisor noise.

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
- **Last-admin DELETE** (see §2 carry-over) has no test; add one alongside the DELETE guard.

## 6. Suggested Next Actions

1. **Revoke REST `EXECUTE`** on `handle_new_user()` and `prevent_last_admin_demotion()` (§2) — one
   migration, highest security value for the effort.
2. **Enforce password policy + optional admin MFA** in the Supabase Auth dashboard; raise client
   `minLength` to ≥8 to match.
3. **Triage the Dependabot backlog:** merge pillow/pytest-cov patch bumps after CI; gate
   `pandas 3` / `react 19` majors behind a focused test pass.
4. **Clear the review-PR backlog:** nine `docs(review)` PRs (#422–#446) are open and unmerged —
   merge or close them so the daily routine isn't piling up stale branches.
5. **Add the RLS negative test** for `profiles.role` self-escalation (§5) so the server-side
   boundary is CI-guarded.
6. **Route the `promax_engine` SECURITY DEFINER view ERROR** to the `supabase-smartsheet-promax-offload`
   repo owners (§4) — it's not this repo's code.
7. **Drop stale `backup.*` snapshot tables** and set explicit `search_path` on the flagged
   functions (§3) to quiet the security advisor to signal-only.

---

## Daily Verdict

**Safe to merge.** No code shipped in the review window, and the four changes that landed just
before it (#444/#447/#450/#451) are production-safe, fail-closed, and PII-conscious. The portal's
server-side authorization boundary was verified live this run and is correct — a non-admin cannot
self-escalate. Every open item is Medium/Low hardening or operational backlog, none of which blocks
the billing cron or weakens auth as deployed. Address the two Medium DB/auth items (§2) as the next
follow-ups.
