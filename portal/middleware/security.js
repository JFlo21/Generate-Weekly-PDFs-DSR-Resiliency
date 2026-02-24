'use strict';

/**
 * ============================================================
 * portal/middleware/security.js
 * ============================================================
 * Security middleware:
 *   - Helmet (CSP, HSTS, referrer policy)
 *   - Rate limiting
 *   - CSRF protection (token validated from JWT payload)
 *   - trust proxy for Vercel / reverse proxies
 *
 * Changes from original:
 *   - trust proxy = 1 (required for Vercel deployment)
 *   - CSRF token read from req.user.csrfToken (JWT payload)
 *     instead of req.session.csrfToken
 *   - POST /auth/login excluded from CSRF (no JWT exists yet)
 *   - CSP updated: allows Google Fonts for React/Tailwind frontend
 * ============================================================
 */

const helmet    = require('helmet');
const rateLimit = require('express-rate-limit');
const config    = require('../config/default');

/**
 * CSRF protection middleware.
 *
 * Safe methods (GET/HEAD/OPTIONS) are always allowed.
 * POST /auth/login is excluded — user has no JWT yet.
 * All other mutating requests must supply X-CSRF-Token header
 * matching the csrfToken embedded in the user's JWT payload.
 */
function csrfProtection(req, res, next) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
    return next();
  }

  // Login route has no JWT yet — skip CSRF
  if (req.path === '/auth/login' || req.originalUrl.endsWith('/auth/login')) {
    return next();
  }

  const headerToken  = req.headers['x-csrf-token'];
  const sessionToken = req.user && req.user.csrfToken;

  if (!headerToken || !sessionToken || headerToken !== sessionToken) {
    return res.status(403).json({ error: 'Invalid or missing CSRF token' });
  }

  next();
}

/**
 * Register all global security middleware on the Express app.
 */
function setupSecurity(app) {
  // Trust one level of reverse proxy (Vercel, nginx, load balancers)
  app.set('trust proxy', 1);

  app.use(helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc:     ["'self'"],
        styleSrc:       ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com'],
        scriptSrc:      ["'self'", "'unsafe-inline'"],
        imgSrc:         ["'self'", 'data:', 'https:'],
        connectSrc:     ["'self'"],
        fontSrc:        ["'self'", 'https://fonts.gstatic.com'],
        objectSrc:      ["'none'"],
        frameAncestors: ["'none'"],
      },
    },
    referrerPolicy: { policy: 'strict-origin-when-cross-origin' },
  }));

  app.use(rateLimit({
    windowMs:        config.rateLimit.windowMs,
    max:             config.rateLimit.max,
    standardHeaders: true,
    legacyHeaders:   false,
    message:         { error: 'Too many requests, please try again later.' },
  }));

  app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    next();
  });
}

module.exports = { setupSecurity, csrfProtection };