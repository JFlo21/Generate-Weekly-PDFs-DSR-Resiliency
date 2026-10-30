# Daily Code Review & Code Quality Check — 2026-10-30

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-etpddu` (even with `origin/master`)
**Reviewer:** automated senior-engineer pass · **Scope:** newly changed code first (PR #435), then a
re-check of the `portal-v2/` auth flow against the open findings from the 2026-10-20 review.
**Validation run this session:** full Python suite **2617 passed, 5 skipped** (`pytest tests/ -q`);
`py_compile` clean on all changed modules; portal-v2 auth/hooks vitest **51 passed**.

---

## 1. Executive Summary

**New code since the last review is healthy.** The one substantive commit in the window is
`4345656` — **`feat(11): G-11-37 parity gap closure (11-11..11-14)` (#435)**, merged 2026-10-30.
It is a large but well-contained change to the shadow/parity memory layer: two new pure modules
(`pipeline/memory_candidate.py`, `pipeline_memory/audit_findings.py`) plus additive edits to
`pipeline_memory/writer.py`, `pipeline/orchestrate.py`, and `audit_billing_changes.py`. Everything
else in the window is automated `docs(runbook)` noise. The change ships with ~6,000 lines of new
tests, and the **full suite is green here (2617 passed)**. The Python billing engine is **not**
degraded — the change is shadow-mode/no-DDL and fail-open by construction.

**The portal auth flow has not moved.** Every `portal-v2/src/.../auth/*`, `hooks/useAuth.ts`, and
`lib/supabase.ts` file is unchanged since `2bfe169` (2026-09-26). That means **all auth findings
from the 2026-10-20 review are still open** — including the High-severity "Remember me" /
client-swap issue, the swallowed `signOut()` error, the last-admin self-DELETE gap, the
perpetual-skeleton lockout, and the missing `useAuth` test. None were actioned in the ~10 days
since. They are re-surfaced below as **carried-over (still open)**, not re-discovered.

**Verdict: Merge with fixes** — scoped to `portal-v2`. The new Python (#435) is safe to merge on its
own; this review document is safe to merge. The portal auth bugs remain the blocker for the next
auth change.

---

## 2. Top Findings

Ordered by severity. New findings are marked **[NEW]**; previously reported ones **[OPEN since
2026-10-20]** with a one-line re-confirmation.

### HIGH — "Remember me" swap orphans the auth listener / breaks session persistence
- **[OPEN since 2026-10-20]** · `portal-v2/src/lib/supabase.ts:36`, `src/hooks/useAuth.ts:47-78,88`
- **Problem:** `login()` calls `setSessionStorage(!rememberMe)`, which **replaces** the exported
  `supabase` client with a brand-new `createClient()` instance, then signs in on that new instance.
  The `onAuthStateChange` listener registered once at `useAuthState` mount is bound to the *original*
  (module-load, `localStorage`) instance and is never rebound. On top of that, `sessionStorage`-backed
  sessions are never read back after a reload because the singleton re-initializes to `localStorage`
  at module load.
- **Why it matters:** In an environment with no cross-instance sync, the new client's `SIGNED_IN`
  never reaches React state, so `AuthGuard` sees `user === null` and bounces a just-authenticated user
  to `/login`. Repeated logins also accumulate multiple `GoTrueClient` instances on one storage key —
  explicitly "undefined behavior" per Supabase.
- **Verification note (why not Critical outright):** `@supabase/supabase-js` uses a
  `BroadcastChannel` keyed on the shared `storageKey`, which *may* relay the new instance's
  `SIGNED_IN` to the old instance's listener in a real browser and mask the failure. A focused
  jsdom reproduction (no `BroadcastChannel`) **did** reproduce `user === null` after login, so the
  failure is real whenever that relay is absent (tests, older browsers, disabled channel). Treat as
  **High / needs live-browser verification**, but fix regardless — the multi-instance pattern is a
  defect on its own.
- **Recommended fix:** Use a **single** client with a storage-routing adapter that dispatches to
  `localStorage`/`sessionStorage` per the remember-me flag, and initialize it at startup from
  whichever store holds a session. Do not swap the singleton. (Same fix as the 2026-10-20 review;
  still unimplemented.)

### MEDIUM — `logout()` ignores the `signOut()` error (UI logs out, session stays live)
- **[OPEN since 2026-10-20]** · `portal-v2/src/hooks/useAuth.ts:112-114`
- **Problem:** `await supabase.auth.signOut();` discards the returned `{ error }`.
- **Why it matters:** On a failed revocation the UI takes the success path and "logs out" visually
  while the session token remains valid — a real security gap on shared machines.
- **Fix:** `const { error } = await supabase.auth.signOut(); if (error) throw error;` and surface it.

### MEDIUM — Perpetual loading skeleton locks a user out when the profile fetch fails
- **[OPEN since 2026-10-20]** · `portal-v2/src/hooks/useAuth.ts:29-45`, `src/components/auth/AuthGuard.tsx:22`
- **Problem:** `fetchProfile` on error only `console.warn`s and returns, leaving `profile === null`.
  `AuthGuard`'s `resolving = loading || (Boolean(user) && !profile)` then stays `true` **forever**,
  rendering the skeleton with no retry and no error state.
- **Why it matters:** A transient RLS/network error on the `profiles` read permanently bricks the
  app for a legitimate, authenticated user until a full reload — and reload re-hits the same path.
- **Fix:** Add a profile-fetch error state + retry/backoff, and let `AuthGuard` render a recoverable
  error rather than an infinite skeleton. Route the error to Sentry (see §3).

### MEDIUM — Last admin can DELETE their own profile → zero admins (defense-in-depth)
- **[OPEN since 2026-10-20]** · `supabase/portal_schema.sql` (`profiles_admin_all` `FOR ALL`)
- **Problem:** `prevent_last_admin_demotion` guards `BEFORE UPDATE` only; DELETE is ungated, so the
  sole admin can delete their own `profiles` row, bypassing both UI and trigger.
- **Fix:** Add a concurrency-safe `BEFORE DELETE` guard, or deny DELETE on `profiles`. *(Needs live
  confirmation that the committed schema is the applied schema — see §4.)*

### LOW — `shadow_candidate_pairs` narrows the candidate set on internal error  **[NEW]**
- `pipeline/memory_candidate.py:252-259`
- **Problem:** The module's whole philosophy is "on uncertainty, widen — scope can only grow." But
  `shadow_candidate_pairs`'s `except` returns an **empty** set, which *narrows* the candidate (the
  unsafe direction) rather than signalling unknown → full.
- **Why it matters:** Low in practice — callers pass already-materialized sets, so the union is very
  unlikely to throw, and the surrounding `debt is None → full mode` path dominates. But it is the one
  spot where the never-raise fallback points the wrong way relative to every sibling function.
- **Fix:** Have the caller treat a failure here as "debt unknown → full" (so scope widens), rather
  than letting this function return a candidate set at all on error. Returning `set(affected)` is
  *not* a safe fallback — it still drops the carried debt, and it can re-raise if `affected` is what
  caused the original error.

---

## 3. Code Quality Improvements

- **[NEW] #435 Python quality is high.** `memory_candidate.py` and `audit_findings.py` are pure,
  fully type-hinted, PEP-257-documented, and carry explicit fail-open contracts, atomic counters, and
  a Python↔SQL lockstep contract test (`test_audit_findings_sql_contract.py`). The `PR #435 feedback`
  annotations in `writer.py` show the review loop already caught the subtle `run_ledger_start`/
  `note_pending` return-value and `started_at`-insert traps. No structural changes requested; it
  respects the facade rule (new behavior lives in `pipeline_memory/*`, not the entry point).
- **[OPEN] Remove the `[v0]` console tag** (`useAuth.ts:41`) and route profile-fetch errors through
  Sentry instead of `console.warn`. (Carried from 2026-10-20 §6.5.)
- **[OPEN] Weak password minimum.** `minLength={6}` on `LoginPage.tsx:137` and
  `ResetPasswordPage.tsx:118,148`. Raise to ≥8 on the client **and** in Supabase Auth settings, kept
  in sync. Client `minLength` is UX only — server enforcement is the control.
- **[OPEN] Missing-`VITE_HCAPTCHA_SITEKEY` handling.** The submit button is gated on `!captchaToken`;
  if the sitekey env var is absent the widget silently never issues a token and login is unreachable
  with no diagnostic. Render a visible config banner (mirror `isSupabaseConfigured`'s ConfigError
  surface).

---

## 4. Security Review

- **New code (#435):** No new attack surface. The audit-memory write path logs **counts and error
  codes only** (no WR/CU/price/personnel), matching the Sentry PII guardrail; `finding_key` is hashed
  on exactly one side (Python), per the module docstring. No secrets, no new network calls beyond the
  existing Supabase RPC. Fail-open is correct here: a write failure is treated as "not recorded,"
  never as "finding fixed."
- **Auth flow (carried, still open):** the High client-swap issue (§2), the `signOut()` error-swallow
  (§2), and the last-admin DELETE gap (§2) are the live security-relevant items. Additionally still
  **needs live verification** from 2026-10-20: (a) the `excel-artifacts` Supabase bucket is actually
  `public:false` (object RLS is bypassed on a public bucket); (b) `vercel.json` CSP `connect-src`
  does not break hCaptcha's challenge XHR in production; (c) the committed `portal_schema.sql` RLS is
  the schema actually applied to the hosted project (it is hand-applied, no CLI migration).
- **No-enumeration contract holds** on `ForgotPasswordPage` (generic error, no email existence leak) —
  unchanged and still correct.

---

## 5. Testing Gaps

- **[NEW] #435 coverage is strong** — new modules are pinned byte-for-byte on finding keys, the
  regen-debt reducer, the shadow fallback model, and the SQL contract. No gap found in the new code.
- **[OPEN · important] No `useAuth` / login test exists.** Confirmed: no test references
  `signInWithPassword` or `setSessionStorage`. (`ResetPasswordPage.test.tsx` *does* exercise
  `onAuthStateChange` for the `PASSWORD_RECOVERY` path — the gap is the login flow, not the listener
  in general.) The single most impactful bug in
  the repo (the client-swap, §2) is entirely untested. Add `useAuth.test.ts` covering (i) the
  remember-me storage swap and listener rebinding, (ii) the `fetchProfile` error path (asserting the
  app does not hang), and (iii) `logout()` error propagation.
- **[OPEN] `ForgotPasswordPage` no-enumeration test** to pin the generic-error contract against
  regressions.

---

## 6. Suggested Next Actions

1. **Rewrite the auth client as a single `createClient` with a storage-routing adapter** (fixes the
   High client-swap *and* the sessionStorage-on-reload issue in one change). This is the oldest and
   highest-value open item.
2. **Add `useAuth.test.ts`** covering the storage swap, the profile-fetch error path, and `logout()`
   error handling — lock the §2 fixes in before they regress.
3. **Fix `logout()` error handling** (`const { error } = ...; if (error) throw error;`).
4. **Add a profile-fetch error/retry state** so a transient `profiles` read failure cannot brick the
   app (perpetual skeleton).
5. **Add a `BEFORE DELETE` last-admin guard** (or deny DELETE) on `profiles`, and confirm the live
   Supabase schema matches the committed one.
6. **Raise the password minimum** to ≥8 on client + Supabase settings; drop the `[v0]` tag and route
   profile errors to Sentry.
7. **Tighten `shadow_candidate_pairs`'s error branch** (§2, Low) so the never-raise fallback widens
   rather than narrows the candidate set — small, keeps the module internally consistent.

---

### Daily Verdict

**Merge with fixes** (scoped to `portal-v2`). The new code in the window — PR #435's shadow/parity
memory work — is well-structured, fail-open, and lands with a green full suite (2617 passed here), so
it is safe on its own and does not touch the billing cron. The blocker is the portal auth flow, which
is **unchanged since September**: the High-severity client-swap/"Remember me" defect and the
Medium logout-error-swallow, last-admin-DELETE, and perpetual-skeleton issues reported on 2026-10-20
are **all still open**. Fix the auth client (single-client adapter) and add the missing `useAuth`
test before the next auth-facing change; the Python side needs only the minor §2 Low cleanup.
