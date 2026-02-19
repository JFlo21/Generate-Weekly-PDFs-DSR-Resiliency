const path = require('node:path');

module.exports = {
  port: parseInt(process.env.PORT, 10) || 3000,
  env: process.env.NODE_ENV || 'development',

  session: {
    secret: process.env.SESSION_SECRET || 'dev-secret-change-in-production',
    maxAge: 8 * 60 * 60 * 1000, // 8 hours
  },

  github: {
    token: process.env.GITHUB_TOKEN || '',
    owner: process.env.GITHUB_OWNER || 'JFlo21',
    repo: process.env.GITHUB_REPO || 'Generate-Weekly-PDFs-DSR-Resiliency',
  },

  rateLimit: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10) || 15 * 60 * 1000,
    max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS, 10) || 100,
  },

  staticDir: path.join(__dirname, '..', 'public'),
};
