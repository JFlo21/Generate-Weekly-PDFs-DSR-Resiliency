# Daily Code Review & Code Quality Check — 2026-11-01

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-omkk6p` (even with `master` + 1 automated docs commit)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code first (Foreman Notes GF-hold pilot), then the auth/security sweep the task mandates.

---

## 1. Executive Summary

**Today's substantive delta is the Foreman Notes General-Foreman (GF) pilot hold** —
`fix(15): hold pilot groups on GF lookup failure` (#444, merged `cf4fc14`, 2026-10-31) and
`ci(15): Foreman Notes pilot upload switch` (#445, `d589ede`). Supporting recent code work:
`fix(11): carry every unconfirmed group as regen debt` (#439, `e63dc3f`). Everything else in
the window is automated `docs(runbook)` churn from the Notion Worker.

**The changed code is high quality and safe.** `pipeline/foreman_notes.py`,
`pipeline/orchestrate.py`, `pipeline/observability.py` and `pipeline/cleanup.py` follow a
strict fail-closed, never-raises discipline: every new helper swallows its own exceptions and
degrades to the safe default (hold / skip / count-zero), the GF-lookup hold sits **before**
`generate_excel` and the billing-audit freeze so no pilot workbook is ever re-sent in the
no-notes layout, and held groups are deliberately **not** skip-confirmed so they persist as
regeneration debt. The RESET_* purge is correctly skipped while a hold is active (it would
delete attachments the hold then refuses to rebuild). The owner-approved Sentry PII exception
(held WR numbers allowed only inside the structured `foreman_notes` context, never in message
text, tags, GF names, or note text) is implemented exactly as documented in
`docs/DECISIONS.md`. `py_compile` is clean on all touched modules; **190 of the relevant
changed-code tests pass** (the 8 "failures" are a local env artifact — openpyxl cannot load
the logo asset under ad-hoc Pillow/openpyxl versions; they are not code defects and pass in
CI with pinned deps). **I found no functional or security defect in today's changed code.**

**The portal-v2 web-app auth layer, however, still carries the two open findings from the
2026-10-20 review** — no fix has landed (the auth files have not changed since). The
client-swap same-tab refresh-logout (High) and the perpetual-loading-skeleton (Medium) both
remain. Because the task makes authentication a hard special-focus area and these can lock a
legitimate user out, the repo-wide verdict stays **Merge with fixes** even though today's
billing-pipeline delta is clean.

---

## 2. Top Findings

Ranked most-important first. The two auth items are **re-flags of 2026-10-20 findings that
are still open**, not new regressions; they are listed first because they are the highest-
severity live issues in the repo and the task prioritizes auth.

### HIGH — `setSessionStorage` swaps the Supabase client after the auth listener is already bound (STILL OPEN)
- **Severity:** High (authentication / availability)
- **File:** `portal-v2/src/lib/supabase.ts:36` + `portal-v2/src/hooks/useAuth.ts:47-95`
- **Problem:** `supabase` is an exported `let` that `setSessionStorage(useSession)` **reassigns
  to a brand-new client instance** on every login (`useAuth.login` calls it before
  `signInWithPassword`). But `useAuthState`'s `useEffect` registers `onAuthStateChange` **once at
  mount**, bound to the *original* instance. After the swap, `signInWithPassword` runs on the new
  instance and emits `SIGNED_IN` there — the mounted listener (old instance) never hears it.
  Separately, the startup singleton is **always** created against `localStorage`, so a session
  written to `sessionStorage` (Remember-me **unchecked**) is invisible to the default client on
  the next page load → the user is silently logged out on a same-tab refresh.
- **Why it matters:** Auth state can fail to propagate after a successful login (context `user`
  stays `null` → `AuthGuard` bounces to `/login`), and Remember-me-off sessions do not survive a
  refresh. This is a core login-flow correctness bug, not cosmetic.
- **Needs verification:** confirm against the live app whether a post-swap login actually
  propagates (a Supabase build may rebroadcast `INITIAL_SESSION` on the next `getSession`). Even
  if it limps through today, the pattern is fragile and should be fixed.
- **Recommended fix:** do **not** recreate the client. Create it once with a storage adapter whose
  backend is chosen dynamically (read a `remember_me` flag from a stable key), or set
  `persistSession`/storage via Supabase's supported runtime options, and re-run `getSession()`
  immediately after `signInWithPassword` to seed context. Add a test (see §5) that logs in with
  Remember-me off, simulates a reload, and asserts the session resolves.

### MEDIUM — `AuthGuard` can hang on an infinite skeleton when the profile fetch fails or lags (STILL OPEN)
- **Severity:** Medium (availability / UX)
- **File:** `portal-v2/src/components/auth/AuthGuard.tsx:22` + `portal-v2/src/hooks/useAuth.ts:29-45`
- **Problem:** `resolving = loading || (Boolean(user) && !profile)`. `fetchProfile` returns
  **without setting `profile`** on any error (logs `console.warn` only) *and* when `maybeSingle()`
  legitimately returns `null` (brand-new user whose `handle_new_user` row hasn't materialized yet
  — the very case the `maybeSingle()` comment calls out). In either case `profile` stays `null`
  forever, so `resolving` never clears and the user is pinned on the loading skeleton with no
  retry, timeout, or error surface. The AuthGuard comment ("a logged-in user always has a profiles
  row") directly contradicts the useAuth comment that anticipates a missing row.
- **Why it matters:** a transient network blip on the profile query, or trigger lag on first
  login, locks a legitimate user out of the entire app until they manually reload.
- **Recommended fix:** give `fetchProfile` a bounded retry + a terminal state (e.g. set a
  `profileError` flag), and in `AuthGuard` resolve to a visible error / sign-out affordance rather
  than an indefinite skeleton when the profile cannot be loaded.

### LOW — raw Supabase error strings surfaced to users; weak client-side password floor
- **Severity:** Low (security hygiene / UX)
- **Files:** `portal-v2/src/components/auth/LoginPage.tsx:39`,
  `ResetPasswordPage.tsx:66-72,118,148`, `useAuth.ts:41`
- **Problem:** login/reset surface `err.message` from Supabase directly; password inputs enforce
  only `minLength={6}`; `fetchProfile` logs a leftover `'[v0]'` debug prefix.
- **Why it matters:** raw provider messages can leak backend detail and are not user-friendly; a
  6-char floor is below the strength the portal should require; the `[v0]` prefix is dead
  scaffolding.
- **Recommended fix:** map known Supabase error codes to friendly copy, raise the password floor
  (and align it with the server-side policy), and drop the `[v0]` prefix.

---

## 3. Code Quality Improvements

- **`pipeline/foreman_notes.py` (changed) — exemplary defensive style.** Every new counter/report
  helper is `try/except … pass` with a "Never raises" docstring, state is extended additively so
  `FnState()` equality is preserved, and `observability` is imported lazily to avoid the import
  cycle. No action needed; call it out as the pattern to copy.
- **`pipeline/orchestrate.py` (changed) — good extraction.** `_run_reset_purge` pulls the inline
  purge block into a named, documented function with a clear `hold_active` short-circuit;
  `_source_wr_raws_by_key` / `_quarantined_group_keys` are marked PURE and scanned on the
  *unfiltered* groups, which is the correct fix for the QUAR-01 time-budget race.
- **Minor — `orchestrate.py` is 6,733 lines and `main()` is thousands of lines.** This is pre-
  existing and out of scope for a surgical change, but the growing `_fn_*` hoist block at the top
  of `main()` is a signal the function should eventually be decomposed into phase helpers. Note,
  don't act, on a billing-critical file.
- **`setSessionStorage`'s mutable module-level `export let`** (see §2 HIGH) is the one quality
  smell worth fixing now: a reassigned shared singleton is hard to reason about and is the root of
  the auth propagation bug.

---

## 4. Security Review

- **Billing-pipeline Sentry PII (changed code): correct.** The owner-approved exception is tightly
  scoped — `_FOREMAN_NOTES_MESSAGES` is fixed per `kind`, WR numbers live only in the structured
  `foreman_notes` context, tags carry counts only, and GF names + note text never leave. Matches
  `docs/DECISIONS.md` (2026-10-30) and the CLAUDE.md Sentry rule. No leak introduced.
- **No `@cell` usage, no new secrets, token only via env** in the changed code — guardrails
  respected.
- **Frontend auth (standing code):** the two §2 items are the live concerns. Client-side
  `RoleGuard`/`AuthGuard` are UX only and must be backed by Supabase RLS; the 2026-10-20 review
  noted the RLS schema (`supabase/portal_schema.sql`) is applied by hand with no CLI migration —
  **re-confirm the live project's policies still match the committed schema** (a non-admin must
  not be able to self-promote via the anon client). Treat as Needs-verification until checked
  against the hosted DB.
- **hCaptcha is enforced on login/signup** and the submit button is gated on a captcha token —
  good.

---

## 5. Testing Gaps

- **No test exercises the client-swap / auth-state propagation path** (`setSessionStorage` →
  `onAuthStateChange`). A test that logs in with Remember-me off, swaps storage, simulates a
  reload, and asserts the session resolves would have caught the §2 HIGH. This is the single most
  valuable missing test.
- **No test for the `AuthGuard` perpetual-skeleton path** — add one where `fetchProfile` rejects
  and assert the guard does not hang indefinitely.
- **Changed Python code is well-covered** (gf-hold, state, regen-debt, Sentry PII all have
  dedicated suites — `test_foreman_notes_gf_hold.py`, `_state.py`, `_sentry.py`,
  `test_regen_debt_carry.py`). No gap in the daily delta.
- **Environment note (not a code issue):** the pinned `pandas` in `requirements.txt` fails to
  build from source on Python 3.13 in a fresh container; this environment ships py3.11 at
  `/usr/local/bin/python` but pip defaults to py3.13, so `python -m pip` is required. CI uses the
  correct pinned toolchain — flagging only so a future local run doesn't lose time to it.

---

## 6. Suggested Next Actions

1. **Fix the `setSessionStorage` client-swap** (§2 HIGH): stop recreating the client; choose the
   storage backend once via a dynamic adapter, and re-seed context with `getSession()` after
   login. Add the propagation test.
2. **Make `AuthGuard` fail visibly** (§2 MEDIUM): bounded profile-fetch retry + terminal error
   state instead of an indefinite skeleton.
3. **Re-verify live Supabase RLS** matches `supabase/portal_schema.sql` (hand-applied schema; no
   migration) — confirm no anon-client self-promotion.
4. **Tidy auth UX/hygiene** (§2 LOW): friendly error mapping, stronger password floor, drop the
   `[v0]` debug prefix.
5. **Keep the Foreman Notes pilot on its current discipline** — the fail-closed hold is the right
   model; when promoting scope beyond pilot, re-run the full `pytest tests/` gate in a correct env.

---

## Daily Verdict

**Changed code (Foreman Notes GF-hold pilot #444/#445 + regen-debt #439): Safe to merge.** It is
additive, fail-closed, PII-safe, sits ahead of generation/upload, and its dedicated test suites
pass. I found no defect in the daily delta.

**Repo-wide: Merge with fixes.** The portal-v2 authentication flow still carries the High
(client-swap refresh-logout) and Medium (perpetual skeleton) findings first reported 2026-10-20,
with no fix landed. Because the task treats authentication as a hard focus area and both can lock
a legitimate user out, these should be scheduled before the next portal release. None of this
touches the Python billing cron, which is healthy.
