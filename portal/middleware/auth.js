function requireAuth(req, res, next) {
  if (req.session && req.session.authenticated) {
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

module.exports = { requireAuth };
