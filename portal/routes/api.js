const express = require('express');
const path = require('node:path');
const AdmZip = require('adm-zip');
const { requireAuth } = require('../middleware/auth');
const github = require('../services/github');
const excel = require('../services/excel');
const poller = require('../services/poller');

const router = express.Router();
const MAX_SSE_CLIENTS = 100;

function validateIntParam(value) {
  const num = parseInt(value, 10);
  if (!Number.isFinite(num) || num <= 0) return null;
  return num;
}

function sanitizeBaseName(name) {
  return name.replace(/[^a-zA-Z0-9._\- ]/g, '_');
}

function sanitizeFilename(name) {
  if (!name) return undefined;
  const normalized = path.posix.normalize(name);
  if (path.posix.isAbsolute(normalized) || normalized.includes('..')) return undefined;
  return normalized;
}

router.use(requireAuth);

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
    const runId = validateIntParam(req.params.runId);
    if (!runId) return res.status(400).json({ error: 'Invalid run ID' });
    const data = await github.listRunArtifacts(runId);
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

router.get('/artifacts/:artifactId/download', async (req, res) => {
  try {
    const artifactId = validateIntParam(req.params.artifactId);
    if (!artifactId) return res.status(400).json({ error: 'Invalid artifact ID' });
    const zipBuffer = await github.downloadArtifact(artifactId);
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="artifact-${artifactId}.zip"`);
    return res.send(zipBuffer);
  } catch (err) {
    console.error('Error downloading artifact:', err.message);
    return res.status(502).json({ error: 'Failed to download artifact' });
  }
});

router.get('/artifacts/:artifactId/view', async (req, res) => {
  try {
    const artifactId = validateIntParam(req.params.artifactId);
    if (!artifactId) return res.status(400).json({ error: 'Invalid artifact ID' });
    const zipBuffer = await github.downloadArtifact(artifactId);

    const zip = new AdmZip(zipBuffer);
    const entries = zip.getEntries();

    const filename = sanitizeFilename(req.query.file);
    let targetEntry;

    if (filename) {
      targetEntry = entries.find((e) => e.entryName === filename);
    }
    if (!targetEntry) {
      targetEntry = entries.find((e) => e.entryName.endsWith('.xlsx'));
    }

    if (!targetEntry) {
      const fileList = entries.map((e) => ({
        name: e.entryName,
        size: e.header.size,
        isDirectory: e.isDirectory,
      }));
      return res.json({ files: fileList, message: 'No Excel file found. Listing contents.' });
    }

    const excelBuffer = targetEntry.getData();
    const parsed = await excel.parseExcelBuffer(excelBuffer);

    return res.json({
      filename: targetEntry.entryName,
      ...parsed,
    });
  } catch (err) {
    console.error('Error viewing artifact:', err.message);
    return res.status(502).json({ error: 'Failed to parse artifact' });
  }
});

router.get('/artifacts/:artifactId/files', async (req, res) => {
  try {
    const artifactId = validateIntParam(req.params.artifactId);
    if (!artifactId) return res.status(400).json({ error: 'Invalid artifact ID' });
    const zipBuffer = await github.downloadArtifact(artifactId);

    const zip = new AdmZip(zipBuffer);
    const entries = zip.getEntries();

    const files = entries
      .filter((e) => !e.isDirectory)
      .map((e) => ({
        name: e.entryName,
        size: e.header.size,
        isExcel: e.entryName.endsWith('.xlsx'),
      }));

    return res.json({ files });
  } catch (err) {
    console.error('Error listing files:', err.message);
    return res.status(502).json({ error: 'Failed to list artifact files' });
  }
});

router.get('/artifacts/:artifactId/export', async (req, res) => {
  try {
    const artifactId = validateIntParam(req.params.artifactId);
    if (!artifactId) return res.status(400).json({ error: 'Invalid artifact ID' });

    const format = req.query.format || 'xlsx';
    if (format !== 'xlsx' && format !== 'csv') {
      return res.status(400).json({ error: 'Unsupported format. Use "xlsx" or "csv".' });
    }
    const filename = sanitizeFilename(req.query.file);

    const zipBuffer = await github.downloadArtifact(artifactId);
    const zip = new AdmZip(zipBuffer);
    const entries = zip.getEntries();

    let targetEntry;
    if (filename) {
      targetEntry = entries.find((e) => e.entryName === filename);
    }
    if (!targetEntry) {
      targetEntry = entries.find((e) => e.entryName.endsWith('.xlsx'));
    }
    if (!targetEntry) {
      return res.status(404).json({ error: 'No file found in artifact' });
    }

    const excelBuffer = targetEntry.getData();
    const baseName = path.basename(targetEntry.entryName, '.xlsx');

    if (format === 'csv') {
      const parsed = await excel.parseExcelBuffer(excelBuffer);
      const sheet = parsed.sheets[0];
      if (!sheet || !sheet.rows || sheet.rows.length === 0) {
        return res.status(404).json({ error: 'Sheet is empty' });
      }

      let maxCol = 0;
      for (const r of sheet.rows) {
        for (const c of r.cells) {
          if (c.col > maxCol) maxCol = c.col;
        }
      }

      const csvRows = sheet.rows.map(row => {
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

      const csvContent = csvRows.join('\r\n');
      const safeName = sanitizeBaseName(baseName);
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${safeName}.csv"`);
      return res.send(csvContent);
    }

    const safeName = sanitizeBaseName(baseName);
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${safeName}.xlsx"`);
    return res.send(excelBuffer);
  } catch (err) {
    console.error('Error exporting artifact:', err.message);
    return res.status(502).json({ error: 'Failed to export artifact' });
  }
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
  if (poller.clients.size >= MAX_SSE_CLIENTS) {
    return res.status(503).json({ error: 'Too many connections' });
  }
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

router.get('/poller-status', (req, res) => {
  return res.json(poller.getStatus());
});

module.exports = router;
module.exports.sanitizeFilename = sanitizeFilename;
