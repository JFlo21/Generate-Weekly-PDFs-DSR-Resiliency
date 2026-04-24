import { describe, it, expect, beforeAll } from 'vitest';
import crypto from 'node:crypto';
import http from 'node:http';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

// Set test password hash before importing the app
const bcrypt = require('bcryptjs');
process.env.ADMIN_PASSWORD_HASH = bcrypt.hashSync('testpass', 4);
process.env.API_AUTH_REQUIRED = 'false';
process.env.SEARCH_INDEX_RUN_LIMIT = '0';

const githubServicePath = require.resolve('../services/github');
const mockWorkflowRun = {
  id: 123,
  run_number: 42,
  status: 'completed',
  conclusion: 'success',
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:01:00Z',
  event: 'workflow_dispatch',
  head_branch: 'master',
};

function installGithubMock() {
  require.cache[githubServicePath] = {
    id: githubServicePath,
    filename: githubServicePath,
    loaded: true,
    exports: {
      listWorkflowRuns: async () => ({ total_count: 1, workflow_runs: [mockWorkflowRun] }),
      listRunArtifacts: async () => ({ total_count: 0, artifacts: [] }),
      downloadArtifact: async () => {
        throw new Error('mock artifact unavailable');
      },
    },
  };
}

installGithubMock();

let server;
let baseUrl;

beforeAll(async () => {
  const app = require('../server');
  await new Promise((resolve) => {
    server = app.listen(0, () => {
      baseUrl = `http://127.0.0.1:${server.address().port}`;
      resolve();
    });
  });

  return () => {
    server.close();
  };
});

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, baseUrl);
    let settled = false;
    const settle = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    const req = http.request(url, {
      method: options.method || 'GET',
      headers: options.headers || {},
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => {
        chunks.push(c);
        if (options.resolveOnFirstChunk) {
          settle({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString() });
          req.destroy();
        }
      });
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString();
        try {
          settle({ status: res.statusCode, headers: res.headers, body: JSON.parse(body) });
        } catch {
          settle({ status: res.statusCode, headers: res.headers, body });
        }
      });
    });
    req.on('error', (err) => {
      if (settled) return;
      reject(err);
    });
    if (options.timeoutMs) {
      req.setTimeout(options.timeoutMs, () => {
        settle({ status: 0, headers: {}, body: '' });
        req.destroy();
      });
    }
    if (options.body) req.write(JSON.stringify(options.body));
    req.end();
  });
}

function clearPortalRequireCache() {
  const portalRoot = path.resolve(process.cwd());
  for (const key of Object.keys(require.cache)) {
    if (key.startsWith(portalRoot + path.sep) && !key.includes(`${path.sep}node_modules${path.sep}`)) {
      delete require.cache[key];
    }
  }
}

async function withFreshApp(env, callback) {
  const previousEnv = {};
  for (const key of Object.keys(env)) {
    previousEnv[key] = process.env[key];
    process.env[key] = env[key];
  }
  process.env.ADMIN_PASSWORD_HASH = bcrypt.hashSync('testpass', 4);
  clearPortalRequireCache();
  installGithubMock();

  const app = require('../server');
  let freshServer;
  let freshBaseUrl;
  try {
    await new Promise((resolve) => {
      freshServer = app.listen(0, () => {
        freshBaseUrl = `http://127.0.0.1:${freshServer.address().port}`;
        resolve();
      });
    });
    return await callback((requestPath, options = {}) => {
      const originalBaseUrl = baseUrl;
      baseUrl = freshBaseUrl;
      return request(requestPath, options).finally(() => {
        baseUrl = originalBaseUrl;
      });
    });
  } finally {
    if (freshServer) {
      await new Promise((resolve) => freshServer.close(resolve));
    }
    for (const [key, value] of Object.entries(previousEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    clearPortalRequireCache();
    installGithubMock();
  }
}

function signSupabaseJwt(payload, secret = 'test-secret') {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const signature = crypto
    .createHmac('sha256', secret)
    .update(`${header}.${body}`)
    .digest('base64url');
  return `${header}.${body}.${signature}`;
}

describe('Health endpoint', () => {
  it('returns healthy status', async () => {
    const res = await request('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('healthy');
    expect(res.body.uptime).toBeGreaterThan(0);
  });
});

describe('Auth endpoints', () => {
  it('returns unauthenticated session', async () => {
    const res = await request('/auth/session');
    expect(res.status).toBe(200);
    expect(res.body.authenticated).toBe(false);
  });

  it('rejects POST without CSRF token', async () => {
    const res = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { username: 'admin', password: 'test' },
    });
    expect(res.status).toBe(403);
  });

  it('rejects login with missing fields (with CSRF)', async () => {
    const csrfRes = await request('/csrf-token');
    const cookie = csrfRes.headers['set-cookie']?.[0]?.split(';')[0] || '';
    const res = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfRes.body.token, 'Cookie': cookie },
      body: { username: '' },
    });
    expect(res.status).toBe(400);
  });

  it('rejects invalid credentials (with CSRF)', async () => {
    const csrfRes = await request('/csrf-token');
    const cookie = csrfRes.headers['set-cookie']?.[0]?.split(';')[0] || '';
    const res = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfRes.body.token, 'Cookie': cookie },
      body: { username: 'wrong', password: 'wrong' },
    });
    expect(res.status).toBe(401);
  });
});

describe('API protection', () => {
  it('allows unauthenticated read API access when API auth is optional', async () => {
    const res = await request('/api/runs');
    expect([200, 502]).toContain(res.status);
  });
});

describe('CORS configuration', () => {
  it('allows configured origins', async () => {
    const res = await request('/health', {
      headers: { Origin: 'http://localhost:5173' },
    });
    expect(res.status).toBe(200);
    expect(res.headers['access-control-allow-origin']).toBe('http://localhost:5173');
  });

  it('denies unexpected origins without raising a server error', async () => {
    const res = await request('/health', {
      headers: { Origin: 'https://unexpected.example.com' },
    });
    expect(res.status).toBe(200);
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
  });

  it('allows no-origin server-to-server requests', async () => {
    const res = await request('/health');
    expect(res.status).toBe(200);
  });
});

describe('Static files', () => {
  it('serves the login page', async () => {
    const res = await request('/');
    expect(res.status).toBe(200);
    expect(res.body).toContain('Report Portal');
  });

  it('serves CSS', async () => {
    const res = await request('/css/styles.css');
    expect(res.status).toBe(200);
    expect(res.body).toContain('--brand-red');
  });
});

describe('Excel service', () => {
  it('parses an Excel buffer', async () => {
    const ExcelJS = require('exceljs');
    const excel = require('../services/excel');

    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Test');
    sheet.addRow(['Name', 'Value']);
    sheet.addRow(['Item A', 100]);
    sheet.addRow(['Item B', 200]);

    const buffer = await workbook.xlsx.writeBuffer();
    const result = await excel.parseExcelBuffer(buffer);

    expect(result.sheetCount).toBe(1);
    expect(result.sheets[0].name).toBe('Test');
    expect(result.sheets[0].rows.length).toBeGreaterThanOrEqual(3);
  });

  it('exports Excel to CSV correctly', async () => {
    const ExcelJS = require('exceljs');
    const excel = require('../services/excel');

    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Export');
    sheet.addRow(['Name', 'Amount', 'Note']);
    sheet.addRow(['Alpha', 1000, 'with, comma']);
    sheet.addRow(['Beta', 2000, 'clean']);

    const buffer = await workbook.xlsx.writeBuffer();
    const parsed = await excel.parseExcelBuffer(buffer);
    const rows = parsed.sheets[0].rows;

    const maxCol = Math.max(...rows.map(r =>
      r.cells.length > 0 ? Math.max(...r.cells.map(c => c.col)) : 0
    ));

    const csvRows = rows.map(row => {
      const cellMap = {};
      for (const cell of row.cells) {
        cellMap[cell.col] = cell;
      }
      const cols = [];
      for (let col = 1; col <= maxCol; col++) {
        const cell = cellMap[col];
        let val = cell ? String(cell.value ?? '') : '';
        if (val.includes(',') || val.includes('"') || val.includes('\n')) {
          val = '"' + val.replace(/"/g, '""') + '"';
        }
        cols.push(val);
      }
      return cols.join(',');
    });

    expect(csvRows[0]).toContain('Name');
    expect(csvRows[1]).toContain('"with, comma"');
    expect(csvRows[2]).toBe('Beta,2000,clean');
  });
});

describe('sanitizeFilename', () => {
  const { sanitizeFilename } = require('../routes/api');

  it('returns undefined for empty input', () => {
    expect(sanitizeFilename('')).toBeUndefined();
    expect(sanitizeFilename(null)).toBeUndefined();
    expect(sanitizeFilename(undefined)).toBeUndefined();
  });

  it('allows normal filenames', () => {
    expect(sanitizeFilename('report.xlsx')).toBe('report.xlsx');
    expect(sanitizeFilename('folder/report.xlsx')).toBe('folder/report.xlsx');
  });

  it('blocks parent directory traversal', () => {
    expect(sanitizeFilename('../secret.txt')).toBeUndefined();
    expect(sanitizeFilename('../../etc/passwd')).toBeUndefined();
    expect(sanitizeFilename('folder/../../../etc/passwd')).toBeUndefined();
  });

  it('blocks absolute paths', () => {
    expect(sanitizeFilename('/etc/passwd')).toBeUndefined();
    expect(sanitizeFilename('/root/.ssh/id_rsa')).toBeUndefined();
  });

  it('blocks encoded traversal patterns after normalization', () => {
    expect(sanitizeFilename('folder/..%2f..%2fetc/passwd')).toBeUndefined();
    expect(sanitizeFilename('a/b/../../../c')).toBeUndefined();
  });
});

describe('New API endpoints protection', () => {
  it('allows unauthenticated access to /api/latest when API auth is optional', async () => {
    const res = await request('/api/latest');
    expect([200, 502]).toContain(res.status);
  });

  it('allows unauthenticated access to /api/poll when API auth is optional', async () => {
    const res = await request('/api/poll');
    expect([200, 502]).toContain(res.status);
  });

  it('allows unauthenticated access to /api/events when API auth is optional', async () => {
    const res = await request('/api/events', { resolveOnFirstChunk: true, timeoutMs: 1000 });
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toContain('text/event-stream');
  });

  it('keeps unauthenticated access to /api/poller-status protected', async () => {
    const res = await request('/api/poller-status');
    expect(res.status).toBe(401);
  });
});

describe('Vendor static files', () => {
  it('serves React production build', async () => {
    const res = await request('/vendor/react/react.production.min.js');
    expect(res.status).toBe(200);
    expect(typeof res.body).toBe('string');
    expect(res.body.length).toBeGreaterThan(0);
  });

  it('serves ReactDOM production build', async () => {
    const res = await request('/vendor/react-dom/react-dom.production.min.js');
    expect(res.status).toBe(200);
  });

  it('serves htm UMD build', async () => {
    const res = await request('/vendor/htm/htm.umd.js');
    expect(res.status).toBe(200);
    expect(res.body).toContain('htm');
  });

  it('serves dashboard-app.js', async () => {
    const res = await request('/js/dashboard-app.js');
    expect(res.status).toBe(200);
    expect(res.body).toContain('React');
  });
});

describe('Poller service', () => {
  it('exports a poller singleton with expected methods', () => {
    const poller = require('../services/poller');
    expect(typeof poller.start).toBe('function');
    expect(typeof poller.stop).toBe('function');
    expect(typeof poller.addClient).toBe('function');
    expect(typeof poller.getStatus).toBe('function');
    expect(typeof poller.poll).toBe('function');
  });

  it('returns status with expected fields', () => {
    const poller = require('../services/poller');
    const status = poller.getStatus();
    expect(status).toHaveProperty('running');
    expect(status).toHaveProperty('lastPollTime');
    expect(status).toHaveProperty('lastKnownRunId');
    expect(status).toHaveProperty('connectedClients');
    expect(status).toHaveProperty('intervalMs');
    expect(typeof status.intervalMs).toBe('number');
  });

  it('starts and stops without error', () => {
    const poller = require('../services/poller');
    poller.start();
    expect(poller.getStatus().running).toBe(true);
    poller.stop();
    expect(poller.getStatus().running).toBe(false);
  });
});

describe('Config polling settings', () => {
  it('has polling configuration', () => {
    const config = require('../config/default');
    expect(config.polling).toBeDefined();
    expect(typeof config.polling.intervalMs).toBe('number');
    expect(config.polling.intervalMs).toBeGreaterThan(0);
  });
});

describe('Authenticated API endpoints', () => {
  let sessionCookie;

  beforeAll(async () => {
    const csrfRes = await request('/csrf-token');
    const csrfCookie = csrfRes.headers['set-cookie']?.[0]?.split(';')[0] || '';
    const loginRes = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfRes.body.token, 'Cookie': csrfCookie },
      body: { username: 'admin', password: 'testpass' },
    });
    sessionCookie = loginRes.headers['set-cookie']?.[0]?.split(';')[0] || '';
  });

  it('returns data from /api/latest when authenticated', async () => {
    const res = await request('/api/latest', { headers: { 'Cookie': sessionCookie } });
    // 502 means it reached the handler but GitHub token is not set — not a 302 redirect
    expect([200, 502]).toContain(res.status);
  });

  it('returns data from /api/poll when authenticated', async () => {
    const res = await request('/api/poll', { headers: { 'Cookie': sessionCookie } });
    expect([200, 502]).toContain(res.status);
  });

  it('returns data from /api/poller-status when authenticated', async () => {
    const res = await request('/api/poller-status', { headers: { 'Cookie': sessionCookie } });
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('running');
    expect(res.body).toHaveProperty('connectedClients');
    expect(res.body).toHaveProperty('intervalMs');
  });
});

describe('New API routes: auth protection', () => {
  it('allows unauthenticated GET /api/search when API auth is optional', async () => {
    const res = await request('/api/search?q=test');
    expect([200, 502]).toContain(res.status);
  });

  it('blocks unauthenticated GET /api/cache/stats', async () => {
    const res = await request('/api/cache/stats');
    expect(res.status).toBe(401);
  });

  it('allows unauthenticated GET /api/runs when API auth is optional', async () => {
    const res = await request('/api/runs');
    expect(res.status).toBe(200);
    expect(res.body.runs).toHaveLength(1);
  });

  it('allows unauthenticated GET /api/artifacts/:id/file validation when API auth is optional', async () => {
    const res = await request('/api/artifacts/1/file');
    expect(res.status).toBe(400);
  });

  it('allows unauthenticated GET /api/artifacts/:id/preview validation when API auth is optional', async () => {
    const res = await request('/api/artifacts/1/preview');
    expect(res.status).toBe(400);
  });

  it('blocks unauthenticated POST /api/search/rebuild before rebuilding the index', async () => {
    const res = await request('/api/search/rebuild', { method: 'POST' });
    expect(res.status).toBe(401);
  });
});

describe('New API routes: authenticated happy path', () => {
  let sessionCookie;

  beforeAll(async () => {
    const csrfRes = await request('/csrf-token');
    const csrfCookie = csrfRes.headers['set-cookie']?.[0]?.split(';')[0] || '';
    const loginRes = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfRes.body.token, 'Cookie': csrfCookie },
      body: { username: 'admin', password: 'testpass' },
    });
    sessionCookie = loginRes.headers['set-cookie']?.[0]?.split(';')[0] || '';
  });

  it('GET /api/cache/stats returns stats object shape', async () => {
    const res = await request('/api/cache/stats', { headers: { Cookie: sessionCookie } });
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('artifactCache');
    expect(res.body).toHaveProperty('searchIndex');
    expect(res.body.searchIndex).toHaveProperty('documents');
    expect(res.body.searchIndex).toHaveProperty('tokens');
    expect(typeof res.body.searchIndex.documents).toBe('number');
  });

  it('GET /api/search?q=test reaches handler when authenticated', async () => {
    const res = await request('/api/search?q=test', { headers: { Cookie: sessionCookie } });
    // 502 if GitHub is unreachable in test env; 200 on success
    expect([200, 502]).toContain(res.status);
    if (res.status === 200) {
      expect(res.body).toHaveProperty('hits');
      expect(Array.isArray(res.body.hits)).toBe(true);
      expect(res.body).toHaveProperty('total');
      expect(typeof res.body.total).toBe('number');
    }
  });

  it('GET /api/artifacts/:id/file returns 400 when file param is missing', async () => {
    const res = await request('/api/artifacts/999/file', { headers: { Cookie: sessionCookie } });
    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/file/i);
  });

  it('GET /api/artifacts/:id/preview returns 400 when file param is missing', async () => {
    const res = await request('/api/artifacts/999/preview', { headers: { Cookie: sessionCookie } });
    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/file/i);
  });

  it('GET /api/runs reaches handler when authenticated', async () => {
    const res = await request('/api/runs', { headers: { Cookie: sessionCookie } });
    expect(res.status).toBe(200);
    expect(res.body.runs).toHaveLength(1);
  });

  it('POST /api/search/rebuild still requires CSRF when authenticated', async () => {
    const res = await request('/api/search/rebuild', {
      method: 'POST',
      headers: { Cookie: sessionCookie },
    });
    expect(res.status).toBe(403);
  });

  it('POST /api/search/rebuild reaches handler with valid session and CSRF', async () => {
    // Get a CSRF token for the existing session
    const csrfRes = await request('/csrf-token', { headers: { Cookie: sessionCookie } });
    const csrfToken = csrfRes.body.token;
    const res = await request('/api/search/rebuild', {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrfToken, Cookie: sessionCookie },
    });
    // 502 if GitHub is unreachable in test env; 200 on success
    expect([200, 502]).toContain(res.status);
    if (res.status === 200) {
      expect(res.body).toHaveProperty('status', 'ok');
      expect(res.body).toHaveProperty('documents');
      expect(res.body).toHaveProperty('tokens');
    }
  });
});

describe('searchIndex service', () => {
  it('exports expected functions', () => {
    const searchIndex = require('../services/searchIndex');
    expect(typeof searchIndex.search).toBe('function');
    expect(typeof searchIndex.rebuild).toBe('function');
    expect(typeof searchIndex.ensureBuilt).toBe('function');
    expect(typeof searchIndex.indexArtifact).toBe('function');
    expect(typeof searchIndex.stats).toBe('function');
  });

  it('stats() returns expected shape without network calls', () => {
    const searchIndex = require('../services/searchIndex');
    const s = searchIndex.stats();
    expect(s).toHaveProperty('documents');
    expect(s).toHaveProperty('tokens');
    expect(s).toHaveProperty('lastBuiltAt');
    expect(typeof s.documents).toBe('number');
    expect(typeof s.tokens).toBe('number');
    // lastBuiltAt is null until a successful rebuild completes
    expect(s.lastBuiltAt === null || typeof s.lastBuiltAt === 'string').toBe(true);
  });

  it('stats() reports non-negative document and token counts', () => {
    const searchIndex = require('../services/searchIndex');
    const s = searchIndex.stats();
    expect(s.documents).toBeGreaterThanOrEqual(0);
    expect(s.tokens).toBeGreaterThanOrEqual(0);
  });
});

describe('artifactCache service', () => {
  it('exports expected functions', () => {
    const artifactCache = require('../services/artifactCache');
    expect(typeof artifactCache.get).toBe('function');
    expect(typeof artifactCache.invalidate).toBe('function');
    expect(typeof artifactCache.stats).toBe('function');
  });

  it('stats() returns cache stats shape without network calls', () => {
    const artifactCache = require('../services/artifactCache');
    const s = artifactCache.stats();
    expect(s).toHaveProperty('inflight');
    expect(typeof s.inflight).toBe('number');
    expect(s).toHaveProperty('size');
    expect(typeof s.size).toBe('number');
  });

  it('invalidate() removes an entry without throwing', () => {
    const artifactCache = require('../services/artifactCache');
    // Invalidating a non-existent key should be a no-op
    expect(() => artifactCache.invalidate('nonexistent-id')).not.toThrow();
    const s = artifactCache.stats();
    expect(s.inflight).toBe(0);
  });

  it('get() rejects for a non-existent artifact (network unavailable)', async () => {
    const artifactCache = require('../services/artifactCache');
    // In test env GitHub is blocked, so get() should reject rather than hang
    await expect(artifactCache.get('999999')).rejects.toThrow();
  });
});

describe('API_AUTH_REQUIRED=true', () => {
  it('gates read API endpoints with the legacy session auth flow', async () => {
    await withFreshApp({ API_AUTH_REQUIRED: 'true' }, async (freshRequest) => {
      const res = await freshRequest('/api/latest');
      expect(res.status).toBe(401);
      expect(res.body).toHaveProperty('error', 'Authentication required');
    });
  });

  it('accepts a valid Supabase bearer token for cross-origin portal-v2 API calls', async () => {
    const token = signSupabaseJwt({
      aud: 'authenticated',
      sub: 'user-123',
      email: 'user@example.com',
      exp: Math.floor(Date.now() / 1000) + 300,
    });

    await withFreshApp(
      { API_AUTH_REQUIRED: 'true', SUPABASE_JWT_SECRET: 'test-secret' },
      async (freshRequest) => {
        const res = await freshRequest('/api/search?q=test', {
          headers: { Authorization: `Bearer ${token}` },
        });
        expect(res.status).toBe(200);
        expect(res.body).toHaveProperty('hits');
        expect(res.headers['set-cookie']?.[0]).toContain('linetec.sid');
      }
    );
  });
});
