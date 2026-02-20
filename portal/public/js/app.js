(function () {
  'use strict';

  const runsContainer = document.getElementById('runsContainer');
  const artifactsPanel = document.getElementById('artifactsPanel');
  const userBadge = document.getElementById('userBadge');
  const logoutBtn = document.getElementById('logoutBtn');

  // Session check
  fetch('/auth/session')
    .then(r => r.json())
    .then(data => {
      if (!data.authenticated) {
        window.location.href = '/';
        return;
      }
      userBadge.textContent = data.username;
    })
    .catch(() => { window.location.href = '/'; });

  // Fetch CSRF token for state-changing requests
  let csrfToken = '';
  fetch('/csrf-token').then(r => r.json()).then(d => { csrfToken = d.token; }).catch(() => {});

  // Logout
  logoutBtn.addEventListener('click', async () => {
    await fetch('/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken } });
    window.location.href = '/';
  });

  // Load workflow runs
  async function loadRuns() {
    runsContainer.innerHTML = '<div class="loading"><div class="spinner"></div><span>Loading workflow runs…</span></div>';
    try {
      const res = await fetch('/api/runs');
      if (!res.ok) throw new Error('Failed to load');
      const data = await res.json();

      if (!data.runs || data.runs.length === 0) {
        runsContainer.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>No workflow runs found. Check your GitHub token configuration.</p></div>';
        return;
      }

      runsContainer.innerHTML = data.runs.map(run => {
        const date = new Date(run.createdAt);
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        const isSuccess = run.conclusion === 'success';
        return `
          <div class="run-card ${isSuccess ? 'success' : 'failure'}" data-run-id="${run.id}">
            <div class="run-info">
              <div class="run-title">Run #${run.runNumber}</div>
              <div class="run-meta">${dateStr} · ${run.event} · ${run.headBranch}</div>
            </div>
            <div class="run-actions">
              <span class="badge ${isSuccess ? 'badge-success' : 'badge-failure'}">${run.conclusion || run.status}</span>
            </div>
          </div>`;
      }).join('');

      runsContainer.querySelectorAll('.run-card').forEach(card => {
        card.addEventListener('click', () => loadArtifacts(card.dataset.runId));
      });
    } catch (err) {
      runsContainer.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error loading runs. ${escapeHtml(err.message)}</p></div>`;
    }
  }

  // Load artifacts for a run
  async function loadArtifacts(runId) {
    artifactsPanel.style.display = 'block';
    artifactsPanel.innerHTML = '<div class="artifacts-panel"><div class="loading"><div class="spinner"></div><span>Loading artifacts…</span></div></div>';
    artifactsPanel.scrollIntoView({ behavior: 'smooth' });

    try {
      const res = await fetch(`/api/runs/${runId}/artifacts`);
      if (!res.ok) throw new Error('Failed to load artifacts');
      const data = await res.json();

      if (!data.artifacts || data.artifacts.length === 0) {
        artifactsPanel.innerHTML = '<div class="artifacts-panel"><div class="empty-state"><div class="icon">📦</div><p>No artifacts found for this run.</p></div></div>';
        return;
      }

      const items = data.artifacts
        .filter(a => !a.expired)
        .map(a => {
          const sizeMB = (a.sizeInBytes / (1024 * 1024)).toFixed(2);
          return `
            <li class="artifact-item">
              <div>
                <span class="name">${escapeHtml(a.name)}</span>
                <span class="size">${sizeMB} MB</span>
              </div>
              <div class="actions">
                <button class="btn-sm btn-view" data-artifact-id="${a.id}" data-artifact-name="${escapeHtml(a.name)}">View</button>
                <button class="btn-sm btn-files" data-artifact-id="${a.id}" data-action="files">Files</button>
                <button class="btn-sm btn-download" data-artifact-id="${a.id}" data-artifact-name="${escapeHtml(a.name)}">⬇ ZIP</button>
              </div>
            </li>`;
        }).join('');

      artifactsPanel.innerHTML = `
        <div class="artifacts-panel">
          <h3>Artifacts (${data.artifacts.length})</h3>
          <ul class="artifact-list">${items || '<li class="empty-state">All artifacts have expired.</li>'}</ul>
        </div>`;

      artifactsPanel.querySelectorAll('.btn-view').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          openFileSelector(btn.dataset.artifactId, btn.dataset.artifactName);
        });
      });

      artifactsPanel.querySelectorAll('.btn-files').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          openFileSelector(btn.dataset.artifactId, 'Files');
        });
      });

      artifactsPanel.querySelectorAll('.btn-download').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          downloadArtifactZip(btn.dataset.artifactId, btn.dataset.artifactName);
        });
      });
    } catch (err) {
      artifactsPanel.innerHTML = `<div class="artifacts-panel"><div class="empty-state"><div class="icon">⚠️</div><p>Error: ${escapeHtml(err.message)}</p></div></div>`;
    }
  }

  // Open file selector / viewer for an artifact
  async function openFileSelector(artifactId, artifactName) {
    const overlay = document.getElementById('viewerOverlay');
    const title = document.getElementById('viewerTitle');
    const body = document.getElementById('viewerBody');
    const tabs = document.getElementById('viewerTabs');

    overlay.style.display = 'flex';
    title.textContent = artifactName;
    tabs.innerHTML = '';
    hideExportButtons();
    body.innerHTML = '<div class="loading"><div class="spinner"></div><span>Loading file list…</span></div>';

    try {
      const res = await fetch(`/api/artifacts/${artifactId}/files`);
      if (!res.ok) throw new Error('Failed to load files');
      const data = await res.json();

      const excelFiles = data.files.filter(f => f.isExcel);

      if (excelFiles.length === 0) {
        body.innerHTML = '<div class="empty-state"><div class="icon">📄</div><p>No Excel files found in this artifact.</p></div>';
        return;
      }

      if (excelFiles.length === 1) {
        viewExcelFile(artifactId, excelFiles[0].name, artifactName);
        return;
      }

      body.innerHTML = `
        <ul class="file-list">
          ${excelFiles.map(f => {
            const sizeMB = (f.size / (1024 * 1024)).toFixed(2);
            const shortName = f.name.split('/').pop();
            return `
              <li class="file-list-item">
                <div class="file-list-info" data-file="${escapeHtml(f.name)}">
                  <span class="file-icon">📊</span>
                  <span class="file-name">${escapeHtml(shortName)}</span>
                  <span class="file-size">${sizeMB} MB</span>
                </div>
                <div class="file-list-actions">
                  <button class="btn-sm btn-view" data-file="${escapeHtml(f.name)}" data-name="${escapeHtml(shortName)}">View</button>
                  <button class="btn-sm btn-export" data-artifact-id="${artifactId}" data-file="${escapeHtml(f.name)}" data-format="xlsx">⬇ XLSX</button>
                  <button class="btn-sm btn-export" data-artifact-id="${artifactId}" data-file="${escapeHtml(f.name)}" data-format="csv">⬇ CSV</button>
                </div>
              </li>`;
          }).join('')}
        </ul>`;

      body.querySelectorAll('.file-list-info').forEach(info => {
        info.style.cursor = 'pointer';
        info.addEventListener('click', () => {
          viewExcelFile(artifactId, info.dataset.file, info.querySelector('.file-name').textContent);
        });
      });

      body.querySelectorAll('.btn-view').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          viewExcelFile(artifactId, btn.dataset.file, btn.dataset.name);
        });
      });

      body.querySelectorAll('.btn-export').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          triggerExport(btn.dataset.artifactId, btn.dataset.file, btn.dataset.format);
        });
      });
    } catch (err) {
      body.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${escapeHtml(err.message)}</p></div>`;
    }
  }

  // View a specific Excel file
  async function viewExcelFile(artifactId, filename, displayName) {
    const title = document.getElementById('viewerTitle');
    const body = document.getElementById('viewerBody');
    const tabs = document.getElementById('viewerTabs');

    title.textContent = displayName || filename.split('/').pop();
    tabs.innerHTML = '';
    body.innerHTML = '<div class="loading"><div class="spinner"></div><span>Parsing Excel data…</span></div>';

    try {
      const res = await fetch(`/api/artifacts/${artifactId}/view?file=${encodeURIComponent(filename)}`);
      if (!res.ok) throw new Error('Failed to parse file');
      const data = await res.json();

      if (!data.sheets || data.sheets.length === 0) {
        body.innerHTML = '<div class="empty-state"><div class="icon">📄</div><p>No data found in this file.</p></div>';
        hideExportButtons();
        return;
      }

      showExportButtons(artifactId, filename);
      window.ExcelViewer.render(data.sheets, tabs, body);
    } catch (err) {
      body.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error parsing file: ${escapeHtml(err.message)}</p></div>`;
      hideExportButtons();
    }
  }

  // Download artifact as ZIP
  function downloadArtifactZip(artifactId, artifactName) {
    const a = document.createElement('a');
    a.href = `/api/artifacts/${artifactId}/download`;
    a.download = `${artifactName || 'artifact'}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // Trigger server-side export (CSV or XLSX)
  function triggerExport(artifactId, filename, format) {
    const url = `/api/artifacts/${artifactId}/export?file=${encodeURIComponent(filename)}&format=${format}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // Show/hide export buttons in viewer toolbar
  function showExportButtons(artifactId, filename) {
    const csvBtn = document.getElementById('exportCsv');
    const xlsxBtn = document.getElementById('exportXlsx');
    csvBtn.style.display = '';
    xlsxBtn.style.display = '';
    csvBtn.onclick = () => triggerExport(artifactId, filename, 'csv');
    xlsxBtn.onclick = () => triggerExport(artifactId, filename, 'xlsx');
  }

  function hideExportButtons() {
    document.getElementById('exportCsv').style.display = 'none';
    document.getElementById('exportXlsx').style.display = 'none';
  }

  // Close viewer
  document.getElementById('closeViewer').addEventListener('click', () => {
    document.getElementById('viewerOverlay').style.display = 'none';
    hideExportButtons();
  });

  document.getElementById('viewerOverlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
      document.getElementById('viewerOverlay').style.display = 'none';
      hideExportButtons();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.getElementById('viewerOverlay').style.display = 'none';
      hideExportButtons();
    }
  });

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  loadRuns();
})();
