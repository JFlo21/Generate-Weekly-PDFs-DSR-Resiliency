'use strict';

/**
 * ============================================================
 * portal/routes/auth.js
 * ============================================================
 * Authentication routes using JWT cookies + Supabase users.
 *
 * POST /auth/login       — validate credentials, issue JWT cookie
 * POST /auth/logout      — clear JWT cookie
 * GET  /auth/session     — return current user info from JWT
 * GET  /auth/csrf        — return CSRF token for mutation requests
 *
 * Backwards compatibility:
 *   GET /auth/session still returns { authenticated, username }
 *   so any existing frontend code continues to work.
 * ============================================================
 */

const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const crypto = require('node:crypto');
const { getUserByUsername, updateLastLogin } = require('../services/users');
const { requireAuth, COOKIE_NAME, getJwtSecret } = require('../middleware/auth');

const router = express.Router();

const IS_PRODUCTION = process.env.NODE_ENV === 'production';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '8h';
const COOKIE_MAX_AGE_MS = 8 * 60 * 60 * 1000; // 8 hours

/**
 * Issue a signed JWT for a user and generate a CSRF token.
 * @param {object} user - User record from Supabase
 * @returns {{ token: string, csrfToken: string }}
 */
function issueToken(user) {
  const csrfToken = crypto.randomBytes(32).toString('hex');

  const payload = {
    sub:      user.id,
    username: user.username,
    role:     user.role,
    csrfToken,
  };

  const token = jwt.sign(payload, getJwtSecret(), {
    expiresIn: JWT_EXPIRES_IN,
  });

  return { token, csrfToken };
}

// ── POST /auth/login ────────────────────────────────────────
router.post('/login', express.json(), async (req, res) => {
  const { username, password } = req.body || {};

  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }

  try {
    const user = await getUserByUsername(username.trim());

    if (!user) {
      // Constant-time response to prevent username enumeration
      await bcrypt.hash('dummy', 1);
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Update last login in background — non-blocking
    updateLastLogin(username.trim()).catch(() => {});

    const { token, csrfToken } = issueToken(user);

    // Set secure httpOnly cookie
    res.cookie(COOKIE_NAME, token, {
      httpOnly: true,
      secure:   IS_PRODUCTION,
      sameSite: 'lax',
      maxAge:   COOKIE_MAX_AGE_MS,
    });

    return res.json({
      success:             true,
      username:            user.username,
      role:                user.role,
      csrfToken,
      forcePasswordChange: user.force_password_change || false,
    });
  } catch (err) {
    console.error('Login error:', err.message);
    return res.status(500).json({ error: 'An error occurred during login. Please try again.' });
  }
});

// ── POST /auth/logout ───────────────────────────────────────outer.post('/logout', (req, res) => {
  res.clearCookie(COOKIE_NAME, {
    httpOnly: true,
    secure:   IS_PRODUCTION,
    sameSite: 'lax',
  });
  return res.json({ success: true });
});

// ── GET /auth/session ───────────────────────────────────────
// Returns current auth state — used by frontend on page load
router.get('/session', requireAuth, (req, res) => {
  return res.json({
    authenticated: true,
    username:      req.user.username,
    role:          req.user.role,
    csrfToken:     req.user.csrfToken,
  });
});

// ── GET /auth/csrf ──────────────────────────────────────────
// Convenience endpoint to fetch the CSRF token
router.get('/csrf', requireAuth, (req, res) => {
  return res.json({ token: req.user.csrfToken });
});

module.exports = router;
