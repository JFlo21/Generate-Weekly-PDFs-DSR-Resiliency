const express = require('express');
const path = require('node:path');
const { requireAuth } = require('../middleware/auth');
const github = require('../services/github');
const excel = require('../services/excel');

const router = express.Router();

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
    const zipBuffer = await github.downloadArtifact(req.params.artifactId);

    const AdmZip = require('adm-zip');
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
    const format = req.query.format || 'xlsx';
    const filename = sanitizeFilename(req.query.file);

    const zipBuffer = await github.downloadArtifact(req.params.artifactId);
    const AdmZip = require('adm-zip');
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
          let val = cell ? String(cell.value ?? '') : '';
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
    return res.status(502).json({ error: 'Failed to export artifact' });
  }
});

module.exports = router;
module.exports.sanitizeFilename = sanitizeFilename;
