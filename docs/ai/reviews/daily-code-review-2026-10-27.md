# Daily Code Review & Code Quality Check — 2026-10-27

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-x9e65n` (even with `master`)
**Reviewer:** automated senior-engineer pass · **Scope:** changed-code check → confirmed no code delta → state-of-repo + process audit.

---

## 1. Executive Summary

**No application code changed in the review window — and none has changed for ~6 weeks.**
The application-code tree is unchanged from `origin/master`: before this review doc was
committed, `git rev-list --left-right --count origin/master...HEAD` returned `0 0` (this PR
then adds only this report). Every commit since the 2026-10-20 review (`b60c3a6`, #421) is either an automated
`docs(runbook)` prose update to `website/docs/runbook/whats-new.md` or a prior daily-review
doc. The last substantive code commit remains `1c52d10` (#409, 2026-09-14); the auth files
(`portal-v2/src/hooks/useAuth.ts`, `AuthGuard.tsx`) last changed 2026-09-15 and are
unchanged today.

**Engine health: good.** `python -m py_compile generate_weekly_pdfs.py audit_billing_changes.py`
passes clean. The Python billing cron is untouched and not at risk from anything in this window.

**The important finding today is not a code bug — it is a process failure.** Because the code
has not moved, every portal-v2 auth defect flagged on 2026-10-20 (#421) **still stands,
verbatim**. Meanwhile the daily-review routine keeps opening a new PR each run — **#422
(10-21), #426 (10-22), #428 (10-23), #429 (10-25) are all still OPEN and unmerged**, alongside
this one. The reviews are being generated but neither merged nor acted on, so the auth fixes
they recommend are never applied. **The automation is producing documentation, not change.**

**Verdict: Merge with fixes** — but the fixes needed are (a) triage/close the backlog of
review + dependabot PRs, and (b) finally apply the known `portal-v2` auth patches. There is
nothing new to merge from today's window itself.

---

## 2. Top Findings

> All code findings below are **carried forward unchanged** from #421 because the underlying
> files have not been modified. They are re-stated here only to confirm they are still live,
> not re-discovered. Full patches are in `docs/ai/reviews/daily-code-review-2026-10-20.md`.

### HIGH (process) — Daily-review + dependabot PR backlog is accumulating unmerged
- **Severity:** High (operational / the automation is not achieving its purpose)
- **Where:** GitHub PRs #422, #426, #428, #429 (daily reviews) + #427 pillow, #424/#425
  react 18→19, #423 supabase-js, #420 @types/node, #383 fast-uri, #320 brace-expansion,
  #322/#321 Sentry seer fixes.
- **Problem:** A new review branch/PR is opened every run and left open. Five review PRs now
  sit unmerged; the recommended auth fixes are therefore never applied. Separately, ~15
  dependabot/seer PRs are open, several security-relevant (`pillow 12.3.0→13.0.0`,
  `brace-expansion`, `fast-uri`), some open since August.
- **Why it matters:** The review automation's entire value is that someone acts on it. Right
  now it generates a daily doc that lands in a PR nobody merges, so the same auth bugs have
  survived 5+ consecutive reviews. This is the single highest-leverage thing to fix.
- **Recommended fix:** (1) Pick one review PR to merge (or switch the routine to append to a
  single rolling `whats-new`-style review log instead of one PR/day). (2) Triage dependabot:
  merge the security bumps after CI, close what you won't take. (3) Open one tracked issue for
  the portal-v2 auth fixes and actually land them.

### HIGH (resilience) — Perpetual loading skeleton when profile fetch fails *(still live)*
- **File:** `portal-v2/src/hooks/useAuth.ts` `fetchProfile` (L38–43) + `AuthGuard.tsx`
- **Problem:** `fetchProfile` swallows any query error (`console.warn` then `return`) and never
  sets an error state. `maybeSingle()` returning `data:null, error:null` (missing row) is also
  silent. `AuthGuard` treats `user && !profile` as "fetch in flight", so a logged-in user whose
  profile fetch fails is pinned on the skeleton with no error UI and no retry until some later
  `onAuthStateChange` event happens to recover it.
- **Fix:** give `fetchProfile` a terminal `profileError` state; have `AuthGuard` render an
  inline error + Retry instead of the skeleton. Treat a missing row as terminal too.

### MEDIUM (security/observability) — `logout()` swallows `signOut()` failure *(still live)*
- **File:** `portal-v2/src/hooks/useAuth.ts` L112–114
- **Problem:** `async function logout() { await supabase.auth.signOut(); }` — the result/error
  is never inspected. If `signOut` fails (network/revocation error), the UI may navigate to a
  logged-out view while the session token is still valid in storage, and nothing is logged.
- **Fix:** capture and surface the error; on a shared device, failing to clear the session is a
  security-relevant event worth a Sentry breadcrumb and a user-visible "could not sign out".
  ```ts
  async function logout(): Promise<void> {
    const { error } = await supabase.auth.signOut();
    if (error) { sentryCapture(error); throw error; }
  }
  ```

### MEDIUM — "Remember me" off + same-tab refresh behaviour *(needs verification, still live)*
- **File:** `useAuth.ts` `login` (L80–95) + `setSessionStorage` in `lib/supabase`.
- **Problem flagged in #421:** with "Remember me" unchecked the client is swapped to
  `sessionStorage`; confirm a same-tab reload keeps the session as intended and that the
  storage swap at `createClient` time composes correctly with `getSession()` on reload. Label:
  **Needs verification** against a live build — unchanged since first raised.

---

## 3. Code Quality Improvements

- **Review-automation design.** One PR/day that never merges is an anti-pattern. Prefer a
  single rolling review log (mirroring the `whats-new.md` Notion-worker pattern already in the
  repo) or auto-close superseded review PRs so the queue reflects reality.
- `fetchProfile`'s `[v0]` log prefix (L41) looks like leftover scaffolding — standardize log
  prefixes across the hook.
- No type-safety or structural regressions introduced in this window (nothing changed).

## 4. Security Review

- **No new attack surface** — auth code is unchanged since 2026-09-15.
- **Standing items:** the swallowed-`signOut` gap (§2 MEDIUM) and the swallowed
  profile-fetch error (§2 HIGH) are the only auth-logic concerns, both pre-existing.
- **Dependency security debt:** `pillow 12.3.0→13.0.0` (#427), `fast-uri` (#383),
  `brace-expansion` (#320) bumps are open and unreviewed. Triage these — a stale security bump
  is a silent exposure. (Needs verification that any are CVE-driven vs. routine.)
- **RLS reminder (from #421):** client-side role guards are backed by server-side RLS in
  `supabase/portal_schema.sql`, but that schema is applied by hand with no CLI migration —
  confirm the deployed policies match the committed file against the hosted DB.

## 5. Testing Gaps

- **No dedicated test for the core auth hook.** `portal-v2/src/hooks/__tests__/` has tests for
  `useArtifacts`, `useDebounce`, `useRealtimeArtifacts`, etc. — but **no `useAuth.test.ts`**.
  The `fetchProfile` error path, `login` storage swap, and `logout` are untested. This is the
  highest-value test to add and would have caught the §2 findings.
- No direct test of the `logout`/`signOut` flow (only an incidental reference in
  `PendingApprovalPage.test.tsx`).

## 6. Suggested Next Actions

1. **Stop the PR pile-up.** Decide: merge one review PR, or convert the routine to a rolling
   log. Close superseded review PRs #422/#426/#428/#429.
2. **Land the portal-v2 auth fixes** (perpetual-skeleton + swallowed `signOut`) as one real
   code PR — they have now survived 5+ reviews.
3. **Add `useAuth.test.ts`** covering the `fetchProfile` error/empty path, `login` storage
   swap, and `logout`.
4. **Triage dependabot security bumps** (#427 pillow, #383 fast-uri, #320 brace-expansion):
   run CI, merge or close.
5. Verify RLS policies on the hosted Supabase project match `portal_schema.sql`.
6. Verify the "Remember me"-off same-tab-refresh behaviour on a live build.

---

## Daily Verdict

**Merge with fixes.** No code changed in this window, so there is nothing new to break — the
billing engine compiles clean and is unaffected. But the review automation is not translating
into change: five daily-review PRs are open and unmerged, and the portal-v2 auth defects first
raised weeks ago remain live and unpatched. The correct next step is process, not more review:
clear the PR backlog and finally apply the known auth fixes.
