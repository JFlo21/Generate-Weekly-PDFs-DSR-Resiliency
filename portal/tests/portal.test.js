import { describe, it, expect, beforeAll } from 'vitest';
import http from 'node:http';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

// Set test password hash before importing the app
const bcrypt = require('bcryptjs');
process.env.ADMIN_PASSWORD_HASH = bcrypt.hashSync('testpass', 4);

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
    const req = http.request(url, {
      method: options.method || 'GET',
      headers: options.headers || {},
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString();
        try {
          resolve({ status: res.statusCode, headers: res.headers, body: JSON.parse(body) });
        } catch {
          resolve({ status: res.statusCode, headers: res.headers, body });
        }
      });
    });
    req.on('error', reject);
    if (options.body) req.write(JSON.stringify(options.body));
    req.end();
  });
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
  it('blocks unauthenticated API access', async () => {
    const res = await request('/api/runs');
    expect(res.status).toBe(302);
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
