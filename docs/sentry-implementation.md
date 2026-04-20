# Sentry Implementation Guide

This document describes the Sentry error-monitoring setup across all three components of this production billing automation repository.

---

## Overview

| Component | Instrumented? | DSN env var | Notes |
|-----------|---------------|-------------|-------|
| Python billing engine (`generate_weekly_pdfs.py`) | ✅ Yes (existing + standardised) | `SENTRY_DSN` | Cron check-in, tracing, custom helpers, **Sentry Logs (`enable_logs=True`)** |
| Express backend (`portal/`) | ✅ Yes (new) | `PORTAL_SENTRY_DSN` | Error handler, header scrubbing |
| React frontend (`portal-v2/`) | ✅ Yes (new) | `VITE_SENTRY_DSN` | Browser tracing, ErrorBoundary, API breadcrumbs |

All three surfaces are **opt-in via DSN**. When the DSN is absent or empty, Sentry no-ops completely — the app works unchanged.

---

## Environment Variables

### Python Billing Engine

| Variable | Required | Description |
|----------|----------|-------------|
| `SENTRY_DSN` | Optional | DSN for the Python billing-engine Sentry project |
| `SENTRY_RELEASE` | Optional | Release string, e.g. `myrepo@<sha>`. Takes priority over `RELEASE`. |
| `SENTRY_ENVIRONMENT` | Optional | Environment tag, e.g. `production`. Takes priority over `ENVIRONMENT`. |
| `RELEASE` | Optional | Legacy fallback release (e.g. git SHA). |
| `ENVIRONMENT` | Optional | Legacy fallback environment (default `production`). |
| `SENTRY_DEBUG` | Optional | Set to `true` to enable Sentry SDK debug logging. |

### Express Backend (`portal/`)

| Variable | Required | Description |
|----------|----------|-------------|
| `PORTAL_SENTRY_DSN` | Optional | DSN for the backend Sentry project (separate from Python) |
| `SENTRY_RELEASE` | Optional | Release string (shared across components) |
| `SENTRY_ENVIRONMENT` | Optional | Environment override (falls back to `ENVIRONMENT` → `NODE_ENV`) |
| `ENVIRONMENT` | Optional | Legacy fallback environment |

### React Frontend (`portal-v2/`)

All frontend vars are prefixed `VITE_` (Vite build-time injection):

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_SENTRY_DSN` | Optional | DSN for the frontend Sentry project (separate from backend) |
| `VITE_SENTRY_ENVIRONMENT` | Optional | Environment tag (defaults to Vite `MODE`, i.e. `development`/`production`) |
| `VITE_SENTRY_RELEASE` | Optional | Release string (set by CI or hosting provider) |

#### Source-map upload (build-time, not required at runtime)

| Variable | Required | Description |
|----------|----------|-------------|
| `SENTRY_AUTH_TOKEN` | Optional | Sentry auth token for source-map upload during `npm run build` |
| `SENTRY_ORG` | Optional | Sentry organisation slug |
| `SENTRY_PROJECT_FRONTEND` | Optional | Sentry project slug for the frontend |

---

## GitHub Secrets / Variables

Add these in **Settings → Secrets and variables → Actions**:

### Secrets

| Secret | Used by | Purpose |
|--------|---------|---------|
| `SENTRY_DSN` | Python workflow, health check | Python billing-engine DSN (already exists) |
| `SENTRY_AUTH_TOKEN` | `weekly-excel-generation.yml` | sentry-cli auth for release creation |

### Variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `SENTRY_ORG` | `weekly-excel-generation.yml` | Sentry org slug for sentry-cli |
| `SENTRY_PROJECT_WORKFLOW` | `weekly-excel-generation.yml` | Sentry project slug for the Python workflow |
| `SENTRY_PROJECT_FRONTEND` | `portal-v2` build | Sentry project slug for the React frontend |

> **Note:** `PORTAL_SENTRY_DSN` and `VITE_SENTRY_DSN` should be set on the hosting provider (Render for the Express backend, Vercel for the frontend), not in GitHub Actions unless the portal is deployed from CI.

---

## Local Development

### Python engine

```bash
# .env (copy from .env.example)
SENTRY_DSN=https://your_dsn@o123456.ingest.sentry.io/123456
SENTRY_ENVIRONMENT=development
SENTRY_RELEASE=local-dev

python generate_weekly_pdfs.py
```

### Express backend

```bash
# portal/.env (copy from portal/.env.example)
PORTAL_SENTRY_DSN=https://your_backend_dsn@o123456.ingest.sentry.io/789
SENTRY_ENVIRONMENT=development

cd portal && npm install && npm start
```

### React frontend

```bash
# portal-v2/.env.local (copy from portal-v2/.env.example)
VITE_SENTRY_DSN=https://your_frontend_dsn@o123456.ingest.sentry.io/456
VITE_SENTRY_ENVIRONMENT=development

cd portal-v2 && npm install && npm run dev
```

To test source-map upload locally:
```bash
SENTRY_AUTH_TOKEN=sntrys_xxx SENTRY_ORG=my-org SENTRY_PROJECT_FRONTEND=portal-frontend \
  VITE_SENTRY_RELEASE=local-test npm run build
```

---

## Hosting Notes

### Vercel (React frontend)

Add these environment variables in the Vercel project dashboard:

```
VITE_SENTRY_DSN=https://...
VITE_SENTRY_ENVIRONMENT=production
VITE_SENTRY_RELEASE=$VERCEL_GIT_COMMIT_SHA   # Vercel expands this automatically
```

For source-map upload via Vercel build, also add:
```
SENTRY_AUTH_TOKEN=sntrys_...
SENTRY_ORG=your-org-slug
SENTRY_PROJECT_FRONTEND=your-project-slug
```

### Render / VPS (Express backend)

Add these environment variables in your hosting dashboard:

```
PORTAL_SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
# SENTRY_RELEASE is set automatically by RENDER_GIT_COMMIT on Render.
# For a VPS or other host, set it manually in your deploy script:
#   SENTRY_RELEASE=myrepo@$(git rev-parse HEAD)
```

---

## Privacy / Security

The following data is **intentionally NOT captured** or sent to Sentry:

| Data | How it's excluded |
|------|-------------------|
| Smartsheet API token | Never included in Sentry context; filtered in `before_send` |
| Session cookies | `Authorization`, `Cookie`, `Set-Cookie` headers stripped in backend `beforeSend`/`beforeSendTransaction` |
| CSRF tokens | `X-CSRF-Token` header stripped in backend |
| Supabase keys | Only VITE_SUPABASE_ANON_KEY is in the frontend bundle; it is not added to Sentry context |
| Raw request bodies | `sendDefaultPii: false` on all surfaces; Python engine uses `max_request_body_size: "medium"` (not applicable to Express backend) |
| Session Replay | `replaysSessionSampleRate` and `replaysOnErrorSampleRate` are **not set** |
| Excel file binaries | Not included in any Sentry context |
| PII from billing rows | Python `before_send_filter` does not forward row data |

---

## Verification

### Python billing engine

```bash
# Trigger a test exception via Sentry CLI or directly:
python -c "
import os; os.environ['SENTRY_DSN'] = 'https://...';
import sentry_sdk; sentry_sdk.init(dsn=os.environ['SENTRY_DSN'])
sentry_sdk.capture_message('Test event from Python billing engine', level='info')
sentry_sdk.flush()
"
```

Or run a workflow dispatch in GitHub Actions — Sentry will receive the cron check-in event.

#### Sentry Logs (structured logs product)

`generate_weekly_pdfs.py` initializes the SDK with `enable_logs=True` (requires `sentry-sdk>=2.35.0`, already pinned in `requirements.txt`). With that flag on, two paths reach the Sentry **Logs** product:

1. **Stdlib `logging` → Sentry Logs.** Existing `logger.info(...)`, `logger.warning(...)`, `logger.error(...)` calls throughout the billing engine are forwarded automatically via `LoggingIntegration`. No call-site changes are required.
2. **Direct `sentry_sdk.logger` API.** For log records that should bypass the stdlib logger (e.g. structured spans or attribute-rich events), use the SDK's logger directly:

   ```python
   import sentry_sdk

   sentry_sdk.logger.info("This is an info log message")
   sentry_sdk.logger.warning("This is a warning message")
   sentry_sdk.logger.error("This is an error message")
   ```

Issue-creation behavior is unchanged — the `LoggingIntegration` is still configured with `event_level=logging.ERROR`, so only `ERROR`+ records create Sentry issues. Lower-level records (`INFO`, `WARNING`) now surface as searchable logs instead of being dropped.

### Express backend

```bash
cd portal && npm start
# To test Sentry error capture, add a temporary test route in server.js:
#   app.get('/sentry-test', (req, res) => { throw new Error('Sentry test'); });
# Then trigger it:
#   curl http://localhost:3000/sentry-test
# Or use Sentry.captureMessage() directly in Node.js:
node -e "require('dotenv').config(); const Sentry = require('./lib/sentry'); Sentry.captureMessage('Test from Express backend', 'info'); setTimeout(() => {}, 1000);"
# Check your Sentry project for the captured event.
```

### React frontend

Open the browser console on the deployed/local frontend and run:

```js
// Sentry is already initialised by the app's entry point.
// Use the global SDK namespace to send a test event:
window.__SENTRY__ && import('@sentry/react').then(Sentry => {
  Sentry.captureMessage('Frontend test event', 'info');
});
// Or simply call from any component:
//   import * as Sentry from '@sentry/react';
//   Sentry.captureMessage('Frontend test event', 'info');
```

Or deliberately throw an error inside the app to exercise the `ErrorBoundary`.

---

## Rollback / Disabling Sentry per Surface

Each surface is independently controlled by its DSN. To disable Sentry for any surface, simply **unset or empty the DSN**:

| Surface | How to disable |
|---------|---------------|
| Python engine | Remove / empty `SENTRY_DSN` in GitHub secret or `.env` |
| Express backend | Remove / empty `PORTAL_SENTRY_DSN` in hosting environment |
| React frontend | Remove / empty `VITE_SENTRY_DSN` in hosting environment, then redeploy |
| CI release automation | Remove / empty `SENTRY_AUTH_TOKEN` secret — the release step skips automatically |

No code changes are required. All Sentry instrumentation is gated behind the presence of a non-empty DSN.
