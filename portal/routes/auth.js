const express = require('express');
const bcrypt = require('bcryptjs');
const router = express.Router();

const ADMIN_USERNAME = process.env.ADMIN_USERNAME || 'admin';
const DEFAULT_HASH = bcrypt.hashSync('linetec2025', 12);
const ADMIN_PASSWORD_HASH = process.env.ADMIN_PASSWORD_HASH || DEFAULT_HASH;

router.post('/login', express.json(), async (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }

  if (username !== ADMIN_USERNAME) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const valid = await bcrypt.compare(password, ADMIN_PASSWORD_HASH);
  if (!valid) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  req.session.authenticated = true;
  req.session.username = username;
  req.session.loginTime = new Date().toISOString();

  return res.json({ success: true, username });
});

router.post('/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      return res.status(500).json({ error: 'Logout failed' });
    }
    res.clearCookie('connect.sid');
    return res.json({ success: true });
  });
});

router.get('/session', (req, res) => {
  if (req.session && req.session.authenticated) {
    return res.json({
      authenticated: true,
      username: req.session.username,
      loginTime: req.session.loginTime,
    });
  }
  return res.json({ authenticated: false });
});

module.exports = router;
