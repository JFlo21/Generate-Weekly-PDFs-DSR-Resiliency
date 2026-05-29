---
id: auth-rbac-bootstrap
title: Auth & RBAC bootstrap
sidebar_position: 7
---

# Auth & RBAC bootstrap

**Component ownership:** This flow is owned by the Supabase web app tier
(`portal-v2` + `supabase/portal_schema.sql`), separate from the Python
billing pipeline. No changes to `generate_weekly_pdfs.py` are involved.

This page documents the one-time operator steps required to make signup and
role-based access control work on the live Supabase project. Build and type
checks pass without these steps applied — that is a false-positive trap.
The database trigger **must** exist before any user can sign up successfully.

---

## 1. Apply the Phase 04 DDL

**Why:** The production schema needs three additions before auth works:
an `email` column on `public.profiles` (populated by the signup trigger),
a `created_at` column, and two triggers — one that atomically creates a
`pending` profile row on every signup (`handle_new_user`), and one that
prevents demoting the last admin at the database level
(`prevent_last_admin_demotion`).

**How:** This project applies SQL manually — there is no `supabase db push`
or migrations directory.

1. Open your Supabase project → **SQL Editor**.
2. Paste the Phase 04 DDL blocks from `supabase/portal_schema.sql` (the
   section starting with `-- Phase 04 D-01`). The DDL is idempotent — safe
   to run even if part of it was applied before.
3. Run it. Confirm no errors appear.
4. Verify the triggers exist:
   ```sql
   SELECT tgname FROM pg_trigger
   WHERE tgname IN ('on_auth_user_created', 'check_last_admin');
   ```
   Expect both rows returned.
5. Verify the columns exist:
   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'profiles'
   ORDER BY column_name;
   ```
   Expect: `created_at`, `email`, `id`, `role`.

---

## 2. First-admin bootstrap

**Why:** Every signup defaults to `role = 'pending'`. Someone must become
admin before anyone else can be approved. The first admin is seeded directly
via SQL — there is no other path, by design.

**How:**

1. Sign up normally through the portal login page (your account starts as
   `pending`).
2. Find your auth UID: Supabase Dashboard → **Authentication** → **Users** →
   click your account → copy the **UUID** in the user detail panel.
3. In the **SQL Editor**, promote your account to admin:
   ```sql
   UPDATE public.profiles SET role='admin' WHERE id='<your-auth-uid>';
   ```
4. Sign out and sign back in. You should now reach the dashboard and see the
   **Admin → Users** menu.

From that point, approve other users from `/admin/users` without touching
the SQL editor again.

---

## 3. Disable email confirmation

**Why (D-15):** When "Confirm email" is ON, Supabase returns a session only
after the user clicks a verification link. The portal's signup flow routes
directly to the pending-approval screen instead — a confirmation email adds
unnecessary friction and breaks the UX contract. The application code
tolerates a null session in case this setting is re-enabled later.

**How:** Supabase Dashboard → **Authentication** → **Sign In / Providers** →
**Email** → turn **"Confirm email"** OFF → Save.

---

## 4. Configure hCaptcha bot protection

**Why (D-10):** The login and signup forms include an hCaptcha widget to
prevent automated account creation. Supabase validates the captcha token
server-side before completing the auth request. Without the **Secret Key**
configured in the dashboard, Supabase rejects all attempts with a captcha
error even if the widget renders correctly.

**How:**

1. Supabase Dashboard → **Authentication** → **Bot and Abuse Protection** →
   **Enable CAPTCHA** → select **hCaptcha**.
2. Paste the hCaptcha **Secret Key** (the server-side key — NOT the sitekey).
   - The sitekey goes in the `VITE_HCAPTCHA_SITEKEY` environment variable in
     Vercel (and `.env.local` for local dev).
3. Save.

**Dev / preview testing:** hCaptcha provides a test keypair that always
passes verification:

| Setting | Value |
|---|---|
| Sitekey (`VITE_HCAPTCHA_SITEKEY`) | `10000000-ffff-ffff-ffff-000000000001` |
| Secret Key (Supabase dashboard) | `0x0000000000000000000000000000000000000000` |

Use the test keypair in preview environments; use real production keys in the
live Supabase project.

---

## 5. Configure password-reset redirect URLs

**Why (Pitfall 2):** Supabase's password-reset flow sends the user an email
with a redirect URL pointing back to the app's `/auth/reset` path. If that
URL is not in the allowed list, Supabase rejects the redirect with "Redirect
URL not allowed" and the reset link fails.

**How:** Supabase Dashboard → **Authentication** → **URL Configuration** →
**Redirect URLs** → add:

- `https://*.vercel.app/auth/reset` — covers all Vercel preview deployments.
- `https://<your-production-domain>/auth/reset` — the live production URL.
- `http://localhost:5173/auth/reset` — local dev (optional but convenient).

Save. Without at least the production URL, reset emails will not work for
end users.

---

## 6. Reviewing and approving pending signups

**Why (D-06):** Every new signup lands in `role = 'pending'` and sees an
"Account pending approval" screen. Admins must explicitly promote users to
`billing` or `admin` before they can reach the artifact table.

**How:** Navigate to **Admin → Users** (`/admin/users`). Pending users appear
with an amber row tint and a count badge next to the page heading. Use the
role dropdown on each row to promote them.

No email notification is sent to the user when approved (deferred to a later
phase). Communicate approval out-of-band until notifications are implemented.

---

## Checklist (one-time setup)

| Step | Done |
|------|------|
| Phase 04 DDL applied; both triggers confirmed present | ☐ |
| First-admin account promoted via SQL | ☐ |
| "Confirm email" turned OFF in dashboard | ☐ |
| hCaptcha Secret Key pasted in Supabase dashboard | ☐ |
| `VITE_HCAPTCHA_SITEKEY` set in Vercel env vars | ☐ |
| `*.vercel.app/auth/reset` added to Redirect URLs | ☐ |
| Production redirect URL added | ☐ |
