'use strict';

/**
 * Sentry bootstrap module for the Linetec portal Express backend.
 *
 * Reads PORTAL_SENTRY_DSN from the environment. When the DSN is absent or
 * empty the Sentry SDK no-ops safely, so this module is safe to import
 * unconditionally.
 *
 * Environment variables consumed:
 *   PORTAL_SENTRY_DSN      – DSN for this backend project (optional)
 *   SENTRY_RELEASE         – release string, e.g. "myrepo@<sha>" (optional)
 *   RELEASE                – legacy fallback for release
 *   VERCEL_GIT_COMMIT_SHA  – populated automatically on Vercel
 *   RENDER_GIT_COMMIT      – populated automatically on Render
 *   SENTRY_ENVIRONMENT     – environment override (optional)
 *   ENVIRONMENT            – legacy fallback for environment
 *   NODE_ENV               – last-resort environment fallback
 */

const Sentry = require('@sentry/node');

const dsn = process.env.PORTAL_SENTRY_DSN || '';

const release =
  process.env.SENTRY_RELEASE ||
  process.env.RELEASE ||
  process.env.VERCEL_GIT_COMMIT_SHA ||
  process.env.RENDER_GIT_COMMIT ||
  'dev';

const environment =
  process.env.SENTRY_ENVIRONMENT ||
  process.env.ENVIRONMENT ||
  process.env.NODE_ENV ||
  'development';

/**
 * Strip sensitive headers from Sentry event request data so that
 * auth tokens, session cookies, and CSRF tokens are never sent.
 *
 * @param {object} requestData – the request object inside a Sentry event
 * @returns {object} sanitised copy
 */
function stripSensitiveHeaders(requestData) {
  if (!requestData || !requestData.headers) return requestData;
  const SENSITIVE = ['authorization', 'cookie', 'set-cookie', 'x-csrf-token'];
  const headers = Object.assign({}, requestData.headers);
  for (const key of SENSITIVE) {
    if (headers[key] !== undefined) {
      headers[key] = '[Filtered]';
    }
  }
  return Object.assign({}, requestData, { headers });
}

Sentry.init({
  dsn,
  environment,
  release,

  // Tracing: 20 % sample rate — conservative for an internal billing portal with
  // low traffic volume. Increase only when spans are needed for specific debugging.
  tracesSampleRate: 0.2,

  // Never send personally identifiable information automatically
  sendDefaultPii: false,

  /**
   * Strip sensitive headers from every outgoing error event.
   * @param {import('@sentry/node').Event} event
   * @returns {import('@sentry/node').Event | null}
   */
  beforeSend(event) {
    if (event.request) {
      event.request = stripSensitiveHeaders(event.request);
    }
    return event;
  },

  /**
   * Strip sensitive headers from every outgoing transaction/span event.
   * @param {import('@sentry/node').Event} event
   * @returns {import('@sentry/node').Event | null}
   */
  beforeSendTransaction(event) {
    if (event.request) {
      event.request = stripSensitiveHeaders(event.request);
    }
    return event;
  },

  initialScope: {
    tags: {
      component: 'portal_backend',
      repo: 'Generate-Weekly-PDFs-DSR-Resiliency',
    },
  },
});

module.exports = Sentry;
