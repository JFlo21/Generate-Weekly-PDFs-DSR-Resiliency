import { describe, it, expect, beforeAll } from 'vitest';
import http from 'node:http';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

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

  it('rejects login with missing fields', async () => {
    const res = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { username: '' },
    });
    expect(res.status).toBe(400);
  });

  it('rejects invalid credentials', async () => {
    const res = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
