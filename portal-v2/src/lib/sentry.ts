/**
 * Sentry init module for the Linetec portal React frontend.
 *
 * This file must be imported as the very first import in main.tsx so that
 * Sentry is active before any other application code runs.
 *
 * When VITE_SENTRY_DSN is absent or empty the SDK no-ops safely, so this
 * import is unconditional and harmless during local development.
 *
 * Vite env vars consumed (all optional):
 *   VITE_SENTRY_DSN         – DSN for this frontend project
 *   VITE_SENTRY_ENVIRONMENT – e.g. "production", "staging" (defaults to Vite MODE)
 *   VITE_SENTRY_RELEASE     – e.g. "myrepo@<sha>" (defaults to 'dev')
 *
 * Intentionally NOT enabled:
 *   - Session Replay (replaysSessionSampleRate / replaysOnErrorSampleRate)
 *   - PII capture (sendDefaultPii is false)
 */

import * as Sentry from '@sentry/react';

const dsn = import.meta.env.VITE_SENTRY_DSN ?? '';

Sentry.init({
  dsn,
  environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? import.meta.env.MODE ?? 'development',
  release: import.meta.env.VITE_SENTRY_RELEASE ?? 'dev',

  // Conservative tracing — no session replay
  tracesSampleRate: 0.2,

  // Never send personally identifiable information automatically
  sendDefaultPii: false,

  // Replay is intentionally omitted (internal billing system with sensitive data)

  integrations: [
    Sentry.browserTracingIntegration(),
  ],

  initialScope: {
    tags: {
      component: 'portal_frontend',
      repo: 'Generate-Weekly-PDFs-DSR-Resiliency',
    },
  },
});

export { Sentry };
