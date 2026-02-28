require('dotenv').config();

const express = require('express');
const session = require('express-session');
const cors = require('cors');
const path = require('node:path');
const config = require('./config/default');
const { setupSecurity, csrfProtection } = require('./middleware/security');
const authRoutes = require('./routes/auth');
const apiRoutes = require('./routes/api');
const healthRoutes = require('./routes/health');
const poller = require('./services/poller');

const app = express();

// Trust first proxy (Railway, Render, Heroku, etc.)
// Required: without this, express-rate-limit throws
// ERR_ERL_UNEXPECTED_X_FORWARDED_FOR and crashes every request
app.set('trust proxy', 1);

// ─── CORS (must be before Helmet/security) ───────────────────
// Allows the Vercel-hosted frontend to call this backend
const ALLOWED_ORIGINS = [
  process.env.CORS_ORIGIN,               // e.g. https://linetec-portal.vercel.app
  process.env.CORS_ORIGIN_2,             // optional second origin
  'http://localhost:5173',                // local Vite dev server
].filter(Boolean);

app.use(cors({
  origin: ALLOWED_ORIGINS,
  credentials: true,                      // Required — api.ts uses { credentials: 'include' }
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'X-CSRF-Token'],
}));
// ──────────────────────────────────────────────────────────────

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

app.use('/vendor/react', express.static(path.join(__dirname, 'node_modules/react/umd'), { maxAge: '7d' }));
app.use('/vendor/react-dom', express.static(path.join(__dirname, 'node_modules/react-dom/umd'), { maxAge: '7d' }));
app.use('/vendor/htm', express.static(path.join(__dirname, 'node_modules/htm/dist'), { maxAge: '7d' }));

app.use(express.static(config.staticDir));

app.get('/csrf-token', (req, res) => {
  const crypto = require('node:crypto');
  if (!req.session.csrfToken) {
    req.session.csrfToken = crypto.randomBytes(32).toString('hex');
  }
  res.json({ token: req.session.csrfToken });
});

app.use(csrfProtection);

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
    if (config.polling.enabled) {
      poller.start();
      console.log(`Artifact polling started (interval: ${config.polling.intervalMs}ms)`);
    }
  });
}

module.exports = app;
