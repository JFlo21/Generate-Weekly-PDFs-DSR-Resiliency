const path = require('node:path');
const crypto = require('node:crypto');

const env = process.env.NODE_ENV || 'development';

function getSessionSecret() {
  if (process.env.SESSION_SECRET) {
    return process.env.SESSION_SECRET;
  }
  if (env === 'production') {
    throw new Error('SESSION_SECRET environment variable must be set in production.');
  }
  console.warn('SESSION_SECRET is not set. Generated a random secret for non-production use.');
  return crypto.randomBytes(32).toString('hex');
}

const DEFAULT_POLL_INTERVAL_MS = 2 * 60 * 1000; // 2 minutes
const MIN_POLL_INTERVAL_MS = 1000; // 1 second
const MAX_POLL_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

function parseInterval() {
  const raw = process.env.POLL_INTERVAL_MS;
  if (!raw) {
    return DEFAULT_POLL_INTERVAL_MS;
  }
  const value = parseInt(raw, 10);
  if (Number.isNaN(value)) {
    return DEFAULT_POLL_INTERVAL_MS;
  }
  if (value < MIN_POLL_INTERVAL_MS) {
    return MIN_POLL_INTERVAL_MS;
  }
  if (value > MAX_POLL_INTERVAL_MS) {
    return MAX_POLL_INTERVAL_MS;
  }
  return value;
}

const githubToken = process.env.GITHUB_TOKEN || '';
if (!githubToken) {
  console.warn('WARNING: GITHUB_TOKEN not set. GitHub API rate limit is 60 req/hr.');
}

const githubOwner = process.env.GITHUB_OWNER || '';
if (!githubOwner) {
  console.warn('WARNING: GITHUB_OWNER not set. GitHub API calls will fail.');
}

const githubRepo = process.env.GITHUB_REPO || '';
if (!githubRepo) {
  console.warn('WARNING: GITHUB_REPO not set. GitHub API calls will fail.');
}

module.exports = {
  port: process.env.PORT != null ? parseInt(process.env.PORT, 10) : 3000,
  env,

  session: {
    secret: getSessionSecret(),
    maxAge: 8 * 60 * 60 * 1000, // 8 hours
  },

  github: {
    token: githubToken,
    owner: githubOwner,
    repo: githubRepo,
  },

  rateLimit: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10) || 15 * 60 * 1000,
    max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS, 10) || 100,
  },

  polling: {
    intervalMs: parseInterval(),
    enabled: process.env.POLLING_ENABLED !== 'false',
  },

  staticDir: path.join(__dirname, '..', 'public'),
};
