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

  // Logout
  logoutBtn.addEventListener('click', async () => {
    await fetch('/auth/logout', { method: 'POST' });
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
    body.innerHTML = '<div class="loading"><div class="spinner"></div><span>Loading file list…</span></div>';

    try {
      const res = await fetch(`/api/artifacts/${artifactId}/files`);
      if (!res.ok) throw new Error('Failed to load files');
      const data = await res.json();

      const excelFiles = data.files.filter(f => f.isExcel);
      const otherFiles = data.files.filter(f => !f.isExcel);

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
              <li class="file-list-item" data-file="${escapeHtml(f.name)}">
                <div>
                  <span class="file-icon">📊</span>
                  <span class="file-name">${escapeHtml(shortName)}</span>
                </div>
                <span class="file-size">${sizeMB} MB</span>
              </li>`;
          }).join('')}
        </ul>`;

      body.querySelectorAll('.file-list-item').forEach(item => {
        item.addEventListener('click', () => {
          viewExcelFile(artifactId, item.dataset.file, item.querySelector('.file-name').textContent);
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
        return;
      }

      window.ExcelViewer.render(data.sheets, tabs, body);
    } catch (err) {
      body.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error parsing file: ${escapeHtml(err.message)}</p></div>`;
    }
  }

  // Close viewer
  document.getElementById('closeViewer').addEventListener('click', () => {
    document.getElementById('viewerOverlay').style.display = 'none';
  });

  document.getElementById('viewerOverlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
      document.getElementById('viewerOverlay').style.display = 'none';
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.getElementById('viewerOverlay').style.display = 'none';
    }
  });

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  loadRuns();
})();
