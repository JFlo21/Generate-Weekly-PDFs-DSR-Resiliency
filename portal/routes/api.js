const express = require('express');
const path = require('node:path');
const { requireAuth } = require('../middleware/auth');
const github = require('../services/github');
const excel = require('../services/excel');
const excelHtml = require('../services/excelHtml');
const poller = require('../services/poller');
const artifactCache = require('../services/artifactCache');
const searchIndex = require('../services/searchIndex');
const config = require('../config/default');

const router = express.Router();

function sanitizeFilename(name) {
  if (!name) return undefined;
  const normalized = path.posix.normalize(name);
  if (path.posix.isAbsolute(normalized) || normalized.includes('..')) return undefined;
  return normalized;
}

if (config.auth.apiRequired) {
  router.use(requireAuth);
} else {
  router.use((req, res, next) => {
    if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      return next();
    }
    return requireAuth(req, res, next);
  });
}

const requireOperationalAuth = config.auth.apiRequired
  ? (_req, _res, next) => next()
  : requireAuth;

router.get('/runs', async (req, res) => {
  try {
    const page = parseInt(req.query.page, 10) || 1;
    const data = await github.listWorkflowRuns(page, 10);
    const runs = (data.workflow_runs || []).map((r) => ({
      id: r.id,
      runNumber: r.run_number,
      status: r.status,
      conclusion: r.conclusion,
      createdAt: r.created_at,
      updatedAt: r.updated_at,
      event: r.event,
      headBranch: r.head_branch,
    }));
    return res.json({ total: data.total_count, runs });
  } catch (err) {
    console.error('Error fetching runs:', err.message);
    return res.status(502).json({ error: 'Failed to fetch workflow runs' });
  }
});

router.get('/runs/:runId/artifacts', async (req, res) => {
  try {
    const data = await github.listRunArtifacts(req.params.runId);
    const artifacts = (data.artifacts || []).map((a) => ({
      id: a.id,
      name: a.name,
      sizeInBytes: a.size_in_bytes,
      expired: a.expired,
      createdAt: a.created_at,
      expiresAt: a.expires_at,
    }));
    return res.json({ total: data.total_count, artifacts });
  } catch (err) {
    console.error('Error fetching artifacts:', err.message);
    return res.status(502).json({ error: 'Failed to fetch artifacts' });
  }
});

/**
 * Per-job step status for a run. Powers the "View logs on GitHub" chips
 * in the redesigned dashboard.
 */
router.get('/runs/:runId/jobs', async (req, res) => {
  try {
    // github.js doesn't have listRunJobs; inline a minimal fetch.
    const https = require('node:https');
    const { owner, repo, token } = config.github;

    const jobs = await new Promise((resolve, reject) => {
      const req2 = https.request(
        {
          hostname: 'api.github.com',
          path: `/repos/${owner}/${repo}/actions/runs/${req.params.runId}/jobs?per_page=30`,
          headers: {
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'LinetecReportPortal/1.0',
            'X-GitHub-Api-Version': '2022-11-28',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        },
        (r) => {
          const chunks = [];
          r.on('data', (c) => chunks.push(c));
          r.on('end', () => {
            try {
              resolve(JSON.parse(Buffer.concat(chunks).toString()));
            } catch (e) {
              reject(e);
            }
          });
        }
      );
      req2.on('error', reject);
      req2.setTimeout(15000, () => {
        req2.destroy();
        reject(new Error('jobs request timeout'));
      });
      req2.end();
    });

    const mapped = (jobs.jobs || []).map((j) => ({
      id: j.id,
      name: j.name,
      status: j.status,
      conclusion: j.conclusion,
      startedAt: j.started_at,
      completedAt: j.completed_at,
      htmlUrl: j.html_url,
      steps: (j.steps || []).map((s) => ({
        name: s.name,
        status: s.status,
        conclusion: s.conclusion,
        number: s.number,
        startedAt: s.started_at,
        completedAt: s.completed_at,
      })),
    }));

    return res.json({ jobs: mapped });
  } catch (err) {
    console.error('Error fetching jobs:', err.message);
    return res.status(502).json({ error: 'Failed to fetch jobs' });
  }
});

/**
 * Full zip download (unchanged — preserves original .xlsx bytes for users
 * who want the raw artifact).
 */
router.get('/artifacts/:artifactId/download', async (req, res) => {
  try {
    const zipBuffer = await github.downloadArtifact(req.params.artifactId);
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="artifact-${req.params.artifactId}.zip"`);
    return res.send(zipBuffer);
  } catch (err) {
    console.error('Error downloading artifact:', err.message);
    return res.status(502).json({ error: 'Failed to download artifact' });
  }
});

/**
 * Stream a single file out of the artifact zip with its original filename.
 * This is the v1 "download original .xlsx" entry point the UI uses — it
 * preserves the xlsx bytes exactly and sets the right Content-Type so the
 * browser renders the correct Save As dialog.
 */
router.get('/artifacts/:artifactId/file', async (req, res) => {
  try {
    const filename = sanitizeFilename(req.query.file);
    if (!filename) return res.status(400).json({ error: 'file query required' });

    const bundle = await artifactCache.get(req.params.artifactId);
    const buf = bundle.getBuffer(filename);
    if (!buf) return res.status(404).json({ error: 'File not found in artifact' });

    const lower = filename.toLowerCase();
    let type = 'application/octet-stream';
    if (lower.endsWith('.xlsx')) {
      type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    } else if (lower.endsWith('.csv')) type = 'text/csv; charset=utf-8';
    else if (lower.endsWith('.json')) type = 'application/json';
    else if (lower.endsWith('.txt') || lower.endsWith('.log')) type = 'text/plain; charset=utf-8';
    else if (lower.endsWith('.md')) type = 'text/markdown; charset=utf-8';
    else if (lower.endsWith('.png')) type = 'image/png';
    else if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) type = 'image/jpeg';

    res.setHeader('Content-Type', type);
    const disposition = req.query.inline === '1' ? 'inline' : 'attachment';
    const base = path.posix.basename(filename);
    res.setHeader('Content-Disposition', `${disposition}; filename="${base}"`);
    return res.send(buf);
  } catch (err) {
    console.error('Error serving artifact file:', err.message);
    return res.status(502).json({ error: 'Failed to read file from artifact' });
  }
});

router.get('/artifacts/:artifactId/view', async (req, res) => {
  try {
    const bundle = await artifactCache.get(req.params.artifactId);

    const filename = sanitizeFilename(req.query.file);
    let target = filename
      ? bundle.files.find((f) => f.name === filename)
      : bundle.files.find((f) => f.isExcel);

    if (!target) {
      return res.json({ files: bundle.files, message: 'No Excel file found. Listing contents.' });
    }

    const parsed = await bundle.getExcel(target.name);
    return res.json({ filename: target.name, ...parsed });
  } catch (err) {
    console.error('Error viewing artifact:', err.message);
    return res.status(502).json({ error: 'Failed to parse artifact' });
  }
});

router.get('/artifacts/:artifactId/files', async (req, res) => {
  try {
    const bundle = await artifactCache.get(req.params.artifactId);
    return res.json({
      files: bundle.files.map((f) => ({
        name: f.name,
        size: f.size,
        isExcel: f.isExcel,
        isText: f.isText,
        isImage: f.isImage,
        isJson: f.isJson,
        isMarkdown: f.isMarkdown,
        isCsv: f.isCsv,
        isLog: f.isLog,
      })),
    });
  } catch (err) {
    console.error('Error listing files:', err.message);
    return res.status(502).json({ error: 'Failed to list artifact files' });
  }
});

/**
 * Preview a specific file inside an artifact in the requested format.
 *   ?as=json    JSON for the React interactive Excel table (default for .xlsx)
 *   ?as=html    styled HTML snapshot for <iframe srcdoc> rendering
 *   ?as=csv     converted CSV (Excel files only)
 *   ?as=text    UTF-8 text (logs, md, json — up to 2 MB)
 *   ?sheet=Name specific sheet for html/json/csv on multi-sheet workbooks
 */
router.get('/artifacts/:artifactId/preview', async (req, res) => {
  try {
    const filename = sanitizeFilename(req.query.file);
    if (!filename) return res.status(400).json({ error: 'file query required' });

    const bundle = await artifactCache.get(req.params.artifactId);
    const entry = bundle.files.find((f) => f.name === filename);
    if (!entry) return res.status(404).json({ error: 'File not found' });

    const asParam = String(req.query.as || '').toLowerCase();
    const sheetName = req.query.sheet ? String(req.query.sheet) : undefined;
    const as = asParam || (entry.isExcel ? 'json' : entry.isText ? 'text' : 'raw');

    if (entry.isExcel && as === 'json') {
      const parsed = await bundle.getExcel(filename);
      return res.json({ filename, ...parsed });
    }

    if (entry.isExcel && as === 'html') {
      const parsed = await bundle.getExcel(filename);
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      return res.send(excelHtml.renderHtml(parsed, { sheet: sheetName }));
    }

    if (entry.isExcel && as === 'csv') {
      const parsed = await bundle.getExcel(filename);
      const sheet = sheetName
        ? parsed.sheets.find((s) => s.name === sheetName) || parsed.sheets[0]
        : parsed.sheets[0];
      if (!sheet || !sheet.rows || sheet.rows.length === 0) {
        return res.status(404).json({ error: 'Sheet is empty' });
      }
      const maxCol = Math.max(
        ...sheet.rows.map((r) =>
          r.cells.length > 0 ? Math.max(...r.cells.map((c) => c.col)) : 0
        )
      );
      const lines = sheet.rows.map((row) => {
        const map = {};
        for (const c of row.cells) map[c.col] = c;
        const cols = [];
        for (let col = 1; col <= maxCol; col++) {
          const cell = map[col];
          let v = cell ? String(cell.value ?? '') : '';
          if (v.includes(',') || v.includes('"') || v.includes('\n')) {
            v = '"' + v.replace(/"/g, '""') + '"';
          }
          cols.push(v);
        }
        return cols.join(',');
      });
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader(
        'Content-Disposition',
        `inline; filename="${path.basename(filename, path.extname(filename))}.csv"`
      );
      return res.send(lines.join('\r\n'));
    }

    if (as === 'text' || entry.isText) {
      const buf = bundle.getBuffer(filename);
      if (!buf) return res.status(404).json({ error: 'File not found' });
      const MAX = 2 * 1024 * 1024; // 2 MB cap
      const truncated = buf.length > MAX;
      const text = (truncated ? buf.slice(0, MAX) : buf).toString('utf8');
      return res.json({ filename, text, truncated, totalSize: buf.length });
    }

    return res.status(400).json({ error: `Cannot preview ${filename} as ${as}` });
  } catch (err) {
    console.error('Error previewing artifact file:', err.message);
    return res.status(502).json({ error: 'Failed to preview file' });
  }
});

router.get('/artifacts/:artifactId/export', async (req, res) => {
  try {
    const format = req.query.format || 'xlsx';
    const filename = sanitizeFilename(req.query.file);

    const bundle = await artifactCache.get(req.params.artifactId);
    let target = filename
      ? bundle.files.find((f) => f.name === filename)
      : bundle.files.find((f) => f.isExcel);
    if (!target) return res.status(404).json({ error: 'No file found in artifact' });

    const buf = bundle.getBuffer(target.name);
    const baseName = path.basename(target.name, path.extname(target.name));

    if (format === 'csv') {
      const parsed = await bundle.getExcel(target.name);
      const sheet = parsed.sheets[0];
      if (!sheet || !sheet.rows || sheet.rows.length === 0) {
        return res.status(404).json({ error: 'Sheet is empty' });
      }
      const maxCol = Math.max(
        ...sheet.rows.map((r) =>
          r.cells.length > 0 ? Math.max(...r.cells.map((c) => c.col)) : 0
        )
      );
      const lines = sheet.rows.map((row) => {
        const map = {};
        for (const c of row.cells) map[c.col] = c;
        const cols = [];
        for (let col = 1; col <= maxCol; col++) {
          const cell = map[col];
          let v = cell ? String(cell.value ?? '') : '';
          if (v.includes(',') || v.includes('"') || v.includes('\n')) {
            v = '"' + v.replace(/"/g, '""') + '"';
          }
          cols.push(v);
        }
        return cols.join(',');
      });
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${baseName}.csv"`);
      return res.send(lines.join('\r\n'));
    }

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${baseName}.xlsx"`);
    return res.send(buf);
  } catch (err) {
    console.error('Error exporting artifact:', err.message);
    return res.status(502).json({ error: 'Failed to export artifact' });
  }
});

/**
 * Global search — powers the Cmd+K palette.
 *   ?q=...              required
 *   ?scope=all|runs|artifacts|files
 *   ?limit=20
 */
router.get('/search', async (req, res) => {
  try {
    const q = String(req.query.q || '');
    const scope = String(req.query.scope || 'all');
    const limit = Math.min(parseInt(req.query.limit, 10) || 20, 50);
    const result = await searchIndex.search({ q, scope, limit });
    return res.json(result);
  } catch (err) {
    console.error('Search error:', err.message);
    return res.status(502).json({ error: 'Search failed' });
  }
});

/**
 * Force a search-index rebuild (admin / debugging).
 */
router.post('/search/rebuild', requireOperationalAuth, async (req, res) => {
  try {
    await searchIndex.rebuild();
    return res.json({ status: 'ok', ...searchIndex.stats() });
  } catch (err) {
    console.error('Search rebuild error:', err.message);
    return res.status(502).json({ error: 'Rebuild failed' });
  }
});

router.get('/cache/stats', requireOperationalAuth, (req, res) => {
  return res.json({
    artifactCache: artifactCache.stats(),
    searchIndex: searchIndex.stats(),
  });
});

router.get('/latest', async (req, res) => {
  try {
    const data = await github.listWorkflowRuns(1, 1);
    const runs = data.workflow_runs || [];
    if (runs.length === 0) {
      return res.json({ run: null, artifacts: [] });
    }
    const run = runs[0];
    const artifactsData = await github.listRunArtifacts(run.id);
    const artifacts = (artifactsData.artifacts || []).map((a) => ({
      id: a.id,
      name: a.name,
      sizeInBytes: a.size_in_bytes,
      expired: a.expired,
      createdAt: a.created_at,
      expiresAt: a.expires_at,
    }));
    return res.json({
      run: {
        id: run.id,
        runNumber: run.run_number,
        status: run.status,
        conclusion: run.conclusion,
        createdAt: run.created_at,
        updatedAt: run.updated_at,
        event: run.event,
        headBranch: run.head_branch,
      },
      artifacts,
    });
  } catch (err) {
    console.error('Error fetching latest run:', err.message);
    return res.status(502).json({ error: 'Failed to fetch latest run' });
  }
});

router.get('/poll', async (req, res) => {
  try {
    const lastRunId = req.query.lastRunId;
    const data = await github.listWorkflowRuns(1, 10);
    const allRuns = data.workflow_runs || [];

    let newRuns = allRuns;
    if (lastRunId) {
      const idx = allRuns.findIndex((r) => String(r.id) === String(lastRunId));
      newRuns = idx > 0 ? allRuns.slice(0, idx) : (idx === 0 ? [] : allRuns);
    }

    const runs = newRuns.map((r) => ({
      id: r.id,
      runNumber: r.run_number,
      status: r.status,
      conclusion: r.conclusion,
      createdAt: r.created_at,
      updatedAt: r.updated_at,
      event: r.event,
      headBranch: r.head_branch,
    }));

    return res.json({ hasNew: runs.length > 0, runs });
  } catch (err) {
    console.error('Error polling for new runs:', err.message);
    return res.status(502).json({ error: 'Failed to poll for updates' });
  }
});

router.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  res.write(`data: ${JSON.stringify({ type: 'connected', timestamp: new Date().toISOString() })}\n\n`);

  poller.addClient(res);

  const keepAlive = setInterval(() => {
    try {
      res.write(': keepalive\n\n');
    } catch {
      clearInterval(keepAlive);
    }
  }, 30000);

  req.on('close', () => {
    clearInterval(keepAlive);
  });
});

router.get('/poller-status', requireOperationalAuth, (req, res) => {
  return res.json(poller.getStatus());
});

module.exports = router;
module.exports.sanitizeFilename = sanitizeFilename;
