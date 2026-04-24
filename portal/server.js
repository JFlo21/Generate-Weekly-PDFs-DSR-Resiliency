require('dotenv').config();
// Sentry must be initialised as early as possible so it can instrument later requires
const Sentry = require('./lib/sentry');

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
const searchIndex = require('./services/searchIndex');

const app = express();
app.set('trust proxy', 1);

// ─── CORS (must be before Helmet/security) ───────────────────
// Allows the Vercel-hosted frontend to call this backend
function splitCsv(input) {
  return String(input || '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}

const ALLOWED_ORIGINS = [
  ...splitCsv(process.env.CORS_ORIGIN),   // backward-compatible single value
  ...splitCsv(process.env.CORS_ORIGINS),  // preferred: comma-separated list
  'http://localhost:5173',                // local Vite dev server
];

app.use(cors({
  origin(origin, callback) {
    if (!origin) return callback(null, true);
    if (ALLOWED_ORIGINS.includes(origin)) return callback(null, true);
    return callback(null, false);
  },
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
    // Cross-site cookies are required for Vercel(frontend) -> Render(api)
    // when credentials: 'include' is used.
    sameSite: config.env === 'production' ? 'none' : 'lax',
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

// Sentry error handler must come after all routes and before the custom error middleware.
// setupExpressErrorHandler is the Sentry Node v8 API; guard for forward-compat.
if (typeof Sentry.setupExpressErrorHandler === 'function') {
  Sentry.setupExpressErrorHandler(app);
}

app.use((err, req, res, _next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// Keep the in-memory LRU search index warm: rebuild when the poller reports a
// new run so Cmd+K results stay current without a user-initiated refresh.
poller.on('newRun', () => {
  searchIndex.rebuild().catch((err) => {
    console.warn('[searchIndex] rebuild after newRun failed:', err.message);
  });
});

if (require.main === module) {
  app.listen(config.port, () => {
    console.log(`Linetec Report Portal running on http://localhost:${config.port}`);
    if (config.polling.enabled) {
      poller.start();
      console.log(`Artifact polling started (interval: ${config.polling.intervalMs}ms)`);
    }
    // Prime the search index on boot so the first Cmd+K query returns instantly.
    searchIndex.ensureBuilt().catch((err) => {
      console.warn('[searchIndex] initial build failed:', err.message);
    });
  });
}

module.exports = app;
