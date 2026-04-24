const crypto = require('node:crypto');

function decodeBase64Url(value) {
  return Buffer.from(value.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8');
}

function parseJsonSegment(value) {
  try {
    return JSON.parse(decodeBase64Url(value));
  } catch {
    return null;
  }
}

function getBearerToken(req) {
  const header = req.headers && req.headers.authorization;
  if (typeof header !== 'string') return null;
  const trimmed = header.trim();
  if (trimmed.length <= 7 || trimmed.slice(0, 6).toLowerCase() !== 'bearer') return null;
  const separator = trimmed.charAt(6);
  if (separator !== ' ' && separator !== '\t') return null;
  return trimmed.slice(7).trim() || null;
}

function verifySupabaseJwt(token) {
  const secret = process.env.SUPABASE_JWT_SECRET;
  if (!secret || !token) return null;

  const parts = token.split('.');
  if (parts.length !== 3) return null;

  const [encodedHeader, encodedPayload, signature] = parts;
  const header = parseJsonSegment(encodedHeader);
  const payload = parseJsonSegment(encodedPayload);
  if (!header || !payload || header.alg !== 'HS256') return null;

  const expected = crypto
    .createHmac('sha256', secret)
    .update(`${encodedHeader}.${encodedPayload}`)
    .digest('base64url');

  const expectedBuffer = Buffer.from(expected);
  const actualBuffer = Buffer.from(signature);
  if (
    expectedBuffer.length !== actualBuffer.length ||
    !crypto.timingSafeEqual(expectedBuffer, actualBuffer)
  ) {
    return null;
  }

  const now = Math.floor(Date.now() / 1000);
  if (typeof payload.exp === 'number' && payload.exp <= now) return null;
  if (typeof payload.nbf === 'number' && payload.nbf > now) return null;
  if (payload.aud && payload.aud !== 'authenticated') return null;

  const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL;
  if (supabaseUrl) {
    const expectedIssuer = `${supabaseUrl.replace(/\/+$/, '')}/auth/v1`;
    if (payload.iss && payload.iss !== expectedIssuer) return null;
  }

  return payload;
}

function authenticateSupabaseRequest(req) {
  const payload = verifySupabaseJwt(getBearerToken(req));
  if (!payload) return false;

  req.user = {
    id: payload.sub,
    email: payload.email,
    provider: 'supabase',
  };
  req.auth = { type: 'bearer', provider: 'supabase' };

  return true;
}

function requireAuth(req, res, next) {
  if (req.session && req.session.authenticated) {
    return next();
  }
  if (authenticateSupabaseRequest(req)) {
    return next();
  }

  const requestedWith = req.headers && req.headers['x-requested-with'];
  const acceptsJson = typeof req.accepts === 'function' && req.accepts(['json', 'html']) === 'json';
  const isApiRequest =
    (typeof req.originalUrl === 'string' && req.originalUrl.startsWith('/api/')) ||
    (typeof req.baseUrl === 'string' && req.baseUrl.startsWith('/api')) ||
    requestedWith === 'XMLHttpRequest' ||
    acceptsJson;

  if (isApiRequest) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  return res.redirect('/');
}

module.exports = { requireAuth, verifySupabaseJwt };
