require('dotenv').config();

const express = require('express');
const session = require('express-session');
const path = require('node:path');
const config = require('./config/default');
const { setupSecurity } = require('./middleware/security');
const authRoutes = require('./routes/auth');
const apiRoutes = require('./routes/api');
const healthRoutes = require('./routes/health');

const app = express();

setupSecurity(app);

app.use(session({
  secret: config.session.secret,
  resave: false,
  saveUninitialized: false,
  name: 'linetec.sid',
  cookie: {
    httpOnly: true,
    secure: config.env === 'production',
    sameSite: 'lax',
    maxAge: config.session.maxAge,
  },
}));

app.use(express.static(config.staticDir));

app.use('/auth', authRoutes);
app.use('/api', apiRoutes);
app.use('/health', healthRoutes);

app.get('/dashboard', (req, res) => {
  if (!req.session || !req.session.authenticated) {
    return res.redirect('/');
  }
  res.sendFile(path.join(config.staticDir, 'dashboard.html'));
});

app.use((err, req, res, _next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

if (require.main === module) {
  app.listen(config.port, () => {
    console.log(`Linetec Report Portal running on http://localhost:${config.port}`);
  });
}

module.exports = app;
