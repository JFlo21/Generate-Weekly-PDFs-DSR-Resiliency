# Render Backend Setup Guide

Step-by-step guide to deploy the Express backend (`portal-v2/server`) to Render and connect it to the Vercel-hosted React frontend.

## Prerequisites

- [x] A GitHub account with access to `JFlo21/Generate-Weekly-PDFs-DSR-Resiliency`
- [x] A [Render account](https://render.com) (free tier works for staging)
- [x] A Supabase project (for `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_ANON_KEY`)
- [x] The frontend already deployed to Vercel

---

## Step 1 — Create the Render Web Service

1. Sign in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** → **Web Service**.
3. Choose **Build and deploy from a Git repository** → **Connect** the `Generate-Weekly-PDFs-DSR-Resiliency` repo.
4. Fill in the service form:

   | Field              | Value                                                                 |
   |--------------------|-----------------------------------------------------------------------|
   | **Name**           | `linetec-report-portal` (or any slug — becomes your `*.onrender.com`) |
   | **Region**         | `Oregon (US West)` — closest to most Vercel edge regions              |
   | **Branch**         | `master`                                                              |
   | **Root Directory** | `portal-v2`                                                           |
   | **Runtime**        | `Node`                                                                |
   | **Build Command**  | `npm install && npm run build:server`                                 |
   | **Start Command**  | `npm run start:server`                                                |
   | **Instance Type**  | `Starter` ($7/mo) for always-on, or `Free` for testing (sleeps after 15 min idle) |

5. Click **Create Web Service**. The first build takes 3–5 minutes.

---

## Step 2 — Configure environment variables

In the Render service settings, go to **Environment** and add these variables. They mirror what was running on Railway.

### Required

| Key                           | Example value                                | Notes                                                  |
|-------------------------------|----------------------------------------------|--------------------------------------------------------|
| `NODE_ENV`                    | `production`                                 | Enables production logging and disables source maps    |
| `PORT`                        | `10000`                                      | Render injects this automatically — the server listens on `process.env.PORT` |
| `SUPABASE_URL`                | `https://xxxxx.supabase.co`                  | From Supabase → Project Settings → API                 |
| `SUPABASE_SERVICE_ROLE_KEY`   | `eyJhbGciOi...`                              | Marked as **secret** — never commit this               |
| `SUPABASE_ANON_KEY`           | `eyJhbGciOi...`                              | Used for RLS-scoped queries                            |
| `CORS_ORIGIN`                 | `https://your-app.vercel.app,https://*.vusercontent.net` | Comma-separated list; include the v0 preview domain so in-app previews work |

### Optional but recommended

| Key                  | Example value                  | Notes                                                          |
|----------------------|--------------------------------|----------------------------------------------------------------|
| `SENTRY_DSN`         | `https://xxx@sentry.io/xxx`    | Enables server-side error tracking                             |
| `LOG_LEVEL`          | `info`                         | `debug` / `info` / `warn` / `error`                            |
| `SSE_HEARTBEAT_MS`   | `15000`                        | How often the runs event stream sends keep-alive pings         |

**Tip:** Click **Add Secret File** for any `.json` service account keys rather than pasting them as plaintext env vars.

---

## Step 3 — Configure the health check

Render automatically restarts services that fail their health check. The Express server exposes `GET /api/health` which returns `{ status: 'ok' }`.

1. In the Render service settings, go to **Settings** → **Health Check Path**.
2. Set it to: `/api/health`
3. Save. Render will ping this endpoint every 30 seconds.

---

## Step 4 — Update Vercel frontend environment variables

Once Render gives you a URL (e.g., `https://linetec-report-portal.onrender.com`), wire the frontend to it.

1. Go to your Vercel project → **Settings** → **Environment Variables**.
2. Add or update:

   | Key                  | Value                                              | Environments         |
   |----------------------|----------------------------------------------------|----------------------|
   | `VITE_API_BASE_URL`  | `https://linetec-report-portal.onrender.com`       | Production, Preview  |
   | `VITE_DOCS_URL`      | `https://docs.linetec.app` (or your Docusaurus URL)| Production, Preview  |
   | `VITE_SUPABASE_URL`  | Same as server `SUPABASE_URL`                      | Production, Preview  |
   | `VITE_SUPABASE_ANON_KEY` | Same as server `SUPABASE_ANON_KEY`             | Production, Preview  |

3. Trigger a redeploy: **Deployments** → top deployment → **⋯** → **Redeploy**, and check **Use existing Build Cache: off** so the new env vars are baked in.

---

## Step 5 — Verify the wiring

1. Open the Vercel production URL. You should see the dashboard header logo load correctly.
2. The connection pill in the top-right should turn **green "Live"** instead of the amber "Sample data" banner.
3. Click **Dashboard → pick a run**. The artifact panel should show real Excel files from Supabase / Render.
4. Open DevTools → Network. Requests to `/api/runs` and `/api/events` should return 200 from your Render domain.

If the pill stays amber:
- Check the browser console for CORS errors — your domain may not be in `CORS_ORIGIN` on Render.
- Check the Render service logs (**Logs** tab) for startup errors.
- Confirm `VITE_API_BASE_URL` has no trailing slash.

---

## Step 6 — Automatic deploys from GitHub

Render auto-deploys every push to `master` by default. To change:
1. Service → **Settings** → **Build & Deploy** → **Auto-Deploy**.
2. Recommended: keep auto-deploy **on** for `master`, and use Vercel preview deployments + manual Render deploys for feature branches to avoid burning free-tier build minutes.

---

## Rollback plan

If a bad deploy breaks production:
1. Render dashboard → **Events** tab → find the last known-good deploy.
2. Click **⋯** → **Rollback to this deploy**. Takes ~10 seconds.
3. The frontend will automatically reconnect once the rollback is live — no Vercel redeploy needed.

---

## Troubleshooting

### "Application failed to respond"
- The server took too long to start (free tier cold start > 60s). Bump to Starter tier, or add an external pinger (UptimeRobot, cron-job.org) to `/api/health` every 10 minutes.

### Static artifact URLs 404 from the browser
- The Express server serves artifacts from Supabase Storage, not disk. Confirm `SUPABASE_SERVICE_ROLE_KEY` is set and that the bucket has a read policy for the service role.

### SSE stream keeps reconnecting
- Render's proxy closes idle HTTP connections after 60s. The `SSE_HEARTBEAT_MS=15000` setting keeps the stream alive. If it still drops, double-check you're using HTTPS, not HTTP.

### CORS errors despite setting `CORS_ORIGIN`
- `CORS_ORIGIN` must be a comma-separated list with NO spaces and NO trailing slashes: `https://a.com,https://b.com` (correct) vs `https://a.com/, https://b.com` (wrong).
- Wildcards like `https://*.vusercontent.net` only work if the server uses a matcher library; check `portal-v2/server/cors.ts` for the current parsing logic.

---

## Migrating from Railway

If you're switching an existing Railway deployment to Render:

1. Export your Railway env vars: `railway variables` → copy the output.
2. Paste them into Render's **Environment** tab (as described in Step 2).
3. Point `VITE_API_BASE_URL` at the Render URL.
4. Once the Render service is stable for 24 hours, delete the Railway project to stop billing.

The database stays on Supabase — only the compute layer moves.
