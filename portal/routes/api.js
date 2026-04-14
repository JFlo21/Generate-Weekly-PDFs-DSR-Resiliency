const express = require('express');
const path = require('node:path');
const { requireAuth } = require('../middleware/auth');
const github = require('../services/github');
const excel = require('../services/excel');
const poller = require('../services/poller');

const router = express.Router();
const MAX_ARTIFACT_SIZE_BYTES = 50 * 1024 * 1024; // 50MB
const MAX_ZIP_ENTRIES = 1000;
const MAX_ZIP_ENTRY_SIZE_BYTES = 20 * 1024 * 1024; // 20MB

function sanitizeFilename(name) {
  if (!name) return undefined;
  const normalized = path.posix.normalize(name);
  if (path.posix.isAbsolute(normalized) || normalized.includes('..')) return undefined;
  return normalized;
}

function sanitizeCsvCellValue(value) {
  let safeValue = String(value ?? '');
  const trimmed = safeValue.trimStart();
  if (/^[=+\-@]/.test(trimmed)) {
    safeValue = `'${safeValue}`;
  }
  return safeValue;
}

function validateArtifactZip(zipBuffer, entries) {
  if (zipBuffer.length > MAX_ARTIFACT_SIZE_BYTES) {
    const err = new Error('Artifact zip exceeds maximum allowed size');
    err.statusCode = 413;
    throw err;
  }
  if (entries.length > MAX_ZIP_ENTRIES) {
    const err = new Error('Artifact zip has too many files');
    err.statusCode = 413;
    throw err;
  }
}

function validateZipEntry(entry) {
  if (!entry || entry.isDirectory) return;
  if (entry.header && entry.header.size > MAX_ZIP_ENTRY_SIZE_BYTES) {
    const err = new Error('Artifact file exceeds maximum allowed size');
    err.statusCode = 413;
    throw err;
  }
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

router.get('/artifacts/:artifactId/view', async (req, res) => {
  try {
    const zipBuffer = await github.downloadArtifact(req.params.artifactId);

    const AdmZip = require('adm-zip');
    const zip = new AdmZip(zipBuffer);
    const entries = zip.getEntries();
    validateArtifactZip(zipBuffer, entries);

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

    validateZipEntry(targetEntry);
    const excelBuffer = targetEntry.getData();
    const parsed = await excel.parseExcelBuffer(excelBuffer);

    return res.json({
      filename: targetEntry.entryName,
      ...parsed,
    });
  } catch (err) {
    console.error('Error viewing artifact:', err.message);
    return res.status(err.statusCode || 502).json({ error: 'Failed to parse artifact' });
  }
});

router.get('/artifacts/:artifactId/files', async (req, res) => {
  try {
    const zipBuffer = await github.downloadArtifact(req.params.artifactId);

    const AdmZip = require('adm-zip');
    const zip = new AdmZip(zipBuffer);
    const entries = zip.getEntries();
    validateArtifactZip(zipBuffer, entries);

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
    return res.status(err.statusCode || 502).json({ error: 'Failed to list artifact files' });
  }
});

router.get('/artifacts/:artifactId/export', async (req, res) => {
  try {
    const format = req.query.format || 'xlsx';
    const filename = sanitizeFilename(req.query.file);

    const zipBuffer = await github.downloadArtifact(req.params.artifactId);
    const AdmZip = require('adm-zip');
    const zip = new AdmZip(zipBuffer);
    const entries = zip.getEntries();
    validateArtifactZip(zipBuffer, entries);

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

    validateZipEntry(targetEntry);
    const excelBuffer = targetEntry.getData();
    const baseName = path.basename(targetEntry.entryName, '.xlsx');

    if (format === 'csv') {
      const parsed = await excel.parseExcelBuffer(excelBuffer);
      const sheet = parsed.sheets[0];
      if (!sheet || !sheet.rows || sheet.rows.length === 0) {
        return res.status(404).json({ error: 'Sheet is empty' });
      }

      const maxCol = Math.max(...sheet.rows.map(r =>
        r.cells.length > 0 ? Math.max(...r.cells.map(c => c.col)) : 0
      ));

      const csvRows = sheet.rows.map(row => {
        const cellMap = {};
        for (const cell of row.cells) {
          cellMap[cell.col] = cell;
        }
        const cols = [];
        for (let col = 1; col <= maxCol; col++) {
          const cell = cellMap[col];
          let val = cell ? sanitizeCsvCellValue(cell.value) : '';
          if (val.includes(',') || val.includes('"') || val.includes('\n')) {
            val = '"' + val.replace(/"/g, '""') + '"';
          }
          cols.push(val);
        }
        return cols.join(',');
      });

      const csvContent = csvRows.join('\r\n');
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${baseName}.csv"`);
      return res.send(csvContent);
    }

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${baseName}.xlsx"`);
    return res.send(excelBuffer);
  } catch (err) {
    console.error('Error exporting artifact:', err.message);
    return res.status(err.statusCode || 502).json({ error: 'Failed to export artifact' });
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
module.exports.sanitizeCsvCellValue = sanitizeCsvCellValue;
