function requireAuth(req, res, next) {
  if (req.session && req.session.authenticated) {
    return next();
  }
  if ((req.headers && req.headers['x-requested-with'] === 'XMLHttpRequest') || req.path.startsWith('/api/')) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  return res.redirect('/');
}

module.exports = { requireAuth };
