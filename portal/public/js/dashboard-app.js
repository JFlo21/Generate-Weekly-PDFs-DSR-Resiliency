/* Linetec Report Portal – React Dashboard Application */
(function () {
  'use strict';

  var h = htm.bind(React.createElement);
  var useState = React.useState;
  var useEffect = React.useEffect;
  var useRef = React.useRef;
  var useCallback = React.useCallback;

  // ─── Helpers ───
  function escapeHtml(str) {
    var d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function formatSize(bytes) {
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  }

  function timeAgo(iso) {
    var secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (secs < 60) return secs + 's ago';
    if (secs < 3600) return Math.floor(secs / 60) + 'm ago';
    if (secs < 86400) return Math.floor(secs / 3600) + 'h ago';
    return Math.floor(secs / 86400) + 'd ago';
  }

  // ─── API Helpers ───
  var csrfToken = '';

  async function fetchCsrf() {
    try {
      var res = await fetch('/csrf-token');
      var data = await res.json();
      csrfToken = data.token;
    } catch (e) { /* ignore */ }
  }

  async function api(path) {
    var res = await fetch(path);
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    return res.json();
  }

  // ─── Toast Notifications Component ───
  function ToastContainer(props) {
    return h`<div class="toast-container">
      ${props.toasts.map(function (t) {
        return h`<div key=${t.id} class="toast toast-${t.type}" onClick=${function () { props.onDismiss(t.id); }}>
          <span class="toast-icon">${t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : 'ℹ️'}</span>
          <span class="toast-msg">${t.message}</span>
        </div>`;
      })}
    </div>`;
  }

  // ─── Connection Status Component ───
  function ConnectionStatus(props) {
    var color = props.connected ? '#22c55e' : '#ef4444';
    var label = props.connected ? 'Live' : 'Reconnecting…';
    return h`<div class="connection-status">
      <span class="status-dot" style=${{ backgroundColor: color }}></span>
      <span class="status-label">${label}</span>
      ${props.lastPoll && h`<span class="status-time">${timeAgo(props.lastPoll)}</span>`}
    </div>`;
  }

  // ─── Auto-Refresh Countdown ───
  function RefreshCountdown(props) {
    var ref = useRef(null);
    var _s = useState(props.intervalSec);
    var secs = _s[0]; var setSecs = _s[1];

    useEffect(function () {
      setSecs(props.intervalSec);
      ref.current = setInterval(function () {
        setSecs(function (prev) { return prev <= 1 ? props.intervalSec : prev - 1; });
      }, 1000);
      return function () { clearInterval(ref.current); };
    }, [props.intervalSec]);

    var pct = ((props.intervalSec - secs) / props.intervalSec) * 100;

    return h`<div class="refresh-countdown" title="Auto-refresh in ${secs}s">
      <svg viewBox="0 0 36 36" class="countdown-ring">
        <path class="countdown-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
        <path class="countdown-fg" strokeDasharray="${pct}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
      </svg>
      <span class="countdown-text">${secs}s</span>
    </div>`;
  }

  // ─── Header Component ───
  function Header(props) {
    return h`<header class="app-header">
      <div class="header-left">
        <img src="/assets/logo.png" alt="Linetec Services" class="logo" />
        <span class="header-title">Report Portal</span>
      </div>
      <div class="header-right">
        <${ConnectionStatus} connected=${props.connected} lastPoll=${props.lastPoll} />
        <${RefreshCountdown} intervalSec=${props.refreshInterval} />
        <span class="user-badge">${props.username}</span>
        <button class="btn-outline" onClick=${props.onLogout}>Sign Out</button>
      </div>
    </header>`;
  }

  // ─── Search Bar ───
  function SearchBar(props) {
    return h`<div class="search-bar">
      <span class="search-icon">🔍</span>
      <input type="text" class="search-input" placeholder="Search runs, artifacts…"
        value=${props.value} onInput=${function (e) { props.onChange(e.target.value); }} />
      ${props.value && h`<button class="search-clear" onClick=${function () { props.onChange(''); }}>✕</button>`}
    </div>`;
  }

  // ─── Run Card Component ───
  function RunCard(props) {
    var run = props.run;
    var isSuccess = run.conclusion === 'success';
    var isNew = props.isNew;
    var cls = 'run-card ' + (isSuccess ? 'success' : 'failure') + (props.selected ? ' selected' : '') + (isNew ? ' new-item' : '');

    return h`<div class=${cls} onClick=${function () { props.onSelect(run.id); }}>
      <div class="run-info">
        <div class="run-title">
          Run #${run.runNumber}
          ${isNew && h`<span class="badge badge-new">NEW</span>`}
        </div>
        <div class="run-meta">${formatDate(run.createdAt)} · ${run.event} · ${run.headBranch}</div>
      </div>
      <div class="run-actions">
        <span class="badge ${isSuccess ? 'badge-success' : 'badge-failure'}">${run.conclusion || run.status}</span>
      </div>
    </div>`;
  }

  // ─── Run List Component ───
  function RunList(props) {
    if (props.loading) {
      return h`<div class="runs-grid">
        <div class="loading"><div class="spinner"></div><span>Loading workflow runs…</span></div>
      </div>`;
    }
    if (props.error) {
      return h`<div class="runs-grid">
        <div class="empty-state"><div class="icon">⚠️</div><p>Error: ${props.error}</p></div>
      </div>`;
    }
    if (!props.runs || props.runs.length === 0) {
      return h`<div class="runs-grid">
        <div class="empty-state"><div class="icon">📭</div><p>No workflow runs found.</p></div>
      </div>`;
    }

    var filtered = props.runs;
    if (props.search) {
      var q = props.search.toLowerCase();
      filtered = filtered.filter(function (r) {
        return ('#' + r.runNumber).includes(q) || r.event.toLowerCase().includes(q) ||
          r.headBranch.toLowerCase().includes(q) || (r.conclusion || '').toLowerCase().includes(q);
      });
    }

    return h`<div class="runs-grid">
      ${filtered.map(function (run) {
        return h`<${RunCard}
          key=${run.id} run=${run}
          selected=${props.selectedRunId === run.id}
          isNew=${props.newRunIds.has(run.id)}
          onSelect=${props.onSelect} />`;
      })}
    </div>`;
  }

  // ─── Artifact List Component ───
  function ArtifactPanel(props) {
    if (!props.visible) return null;
    if (props.loading) {
      return h`<div class="artifacts-panel slide-in">
        <div class="loading"><div class="spinner"></div><span>Loading artifacts…</span></div>
      </div>`;
    }
    if (!props.artifacts || props.artifacts.length === 0) {
      return h`<div class="artifacts-panel slide-in">
        <div class="empty-state"><div class="icon">📦</div><p>No artifacts found for this run.</p></div>
      </div>`;
    }

    var active = props.artifacts.filter(function (a) { return !a.expired; });

    return h`<div class="artifacts-panel slide-in">
      <h3>Artifacts (${props.artifacts.length})</h3>
      <ul class="artifact-list">
        ${active.map(function (a) {
          return h`<li key=${a.id} class="artifact-item">
            <div>
              <span class="name">${a.name}</span>
              <span class="size">${formatSize(a.sizeInBytes)}</span>
            </div>
            <div class="actions">
              <button class="btn-sm btn-view" onClick=${function () { props.onView(a.id, a.name); }}>View</button>
              <button class="btn-sm btn-files" onClick=${function () { props.onView(a.id, a.name); }}>Files</button>
              <button class="btn-sm btn-download" onClick=${function () { props.onDownload(a.id, a.name); }}>⬇ ZIP</button>
            </div>
          </li>`;
        })}
        ${active.length === 0 && h`<li class="empty-state">All artifacts have expired.</li>`}
      </ul>
    </div>`;
  }

  // ─── Excel Viewer Modal ───
  function ExcelViewerModal(props) {
    var _s1 = useState(null); var files = _s1[0]; var setFiles = _s1[1];
    var _s2 = useState(null); var sheetData = _s2[0]; var setSheetData = _s2[1];
    var _s3 = useState(true); var loading = _s3[0]; var setLoading = _s3[1];
    var _s4 = useState(null); var error = _s4[0]; var setError = _s4[1];
    var _s5 = useState(null); var currentFile = _s5[0]; var setCurrentFile = _s5[1];
    var _s6 = useState(0); var activeSheet = _s6[0]; var setActiveSheet = _s6[1];
    var bodyRef = useRef(null);

    useEffect(function () {
      if (!props.artifactId) return;
      setLoading(true);
      setSheetData(null);
      setFiles(null);
      setError(null);
      setCurrentFile(null);
      setActiveSheet(0);

      api('/api/artifacts/' + props.artifactId + '/files')
        .then(function (data) {
          var excelFiles = data.files.filter(function (f) { return f.isExcel; });
          if (excelFiles.length === 0) {
            setError('No Excel files found in this artifact.');
            setLoading(false);
          } else if (excelFiles.length === 1) {
            loadExcelFile(excelFiles[0].name);
          } else {
            setFiles(excelFiles);
            setLoading(false);
          }
        })
        .catch(function (err) { setError(err.message); setLoading(false); });
    }, [props.artifactId]);

    function loadExcelFile(filename) {
      setLoading(true);
      setCurrentFile(filename);
      setActiveSheet(0);
      api('/api/artifacts/' + props.artifactId + '/view?file=' + encodeURIComponent(filename))
        .then(function (data) {
          setSheetData(data.sheets || []);
          setLoading(false);
        })
        .catch(function (err) { setError(err.message); setLoading(false); });
    }

    function renderTable(sheet) {
      if (!sheet || !sheet.rows || sheet.rows.length === 0) {
        return h`<div class="empty-state"><p>This sheet is empty.</p></div>`;
      }
      var maxCol = Math.max.apply(null, sheet.rows.map(function (r) {
        return r.cells.length > 0 ? Math.max.apply(null, r.cells.map(function (c) { return c.col; })) : 0;
      }));
      return h`<table class="excel-table">
        <tbody>
          ${sheet.rows.map(function (row, ri) {
            var cellMap = {};
            row.cells.forEach(function (c) { cellMap[c.col] = c; });
            var tds = [];
            for (var col = 1; col <= maxCol; col++) {
              var cell = cellMap[col];
              var style = {};
              if (cell && cell.style) {
                if (cell.style.bold) style.fontWeight = '700';
                if (cell.style.fontSize) style.fontSize = cell.style.fontSize + 'pt';
                if (cell.style.color) style.color = cell.style.color;
                if (cell.style.bgColor && cell.style.bgColor !== '#000000') style.backgroundColor = cell.style.bgColor;
                if (cell.style.align) style.textAlign = cell.style.align;
              }
              var val = cell ? (cell.value != null ? String(cell.value) : '') : '';
              if (typeof cell?.value === 'number') {
                val = Number.isInteger(cell.value) ? cell.value.toLocaleString('en-US') :
                  cell.value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
              }
              tds.push(h`<td key=${col} style=${style}>${val}</td>`);
            }
            return h`<tr key=${ri}>${tds}</tr>`;
          })}
        </tbody>
      </table>`;
    }

    if (!props.visible) return null;

    return h`<div class="viewer-overlay" onClick=${function (e) { if (e.target === e.currentTarget) props.onClose(); }}>
      <div class="viewer-container scale-in">
        <div class="viewer-header">
          <h3>${props.title || 'Viewer'}</h3>
          <div class="viewer-toolbar">
            ${currentFile && h`<>
              <button class="btn-sm btn-export" onClick=${function () {
                window.open('/api/artifacts/' + props.artifactId + '/export?file=' + encodeURIComponent(currentFile) + '&format=csv');
              }}>⬇ CSV</button>
              <button class="btn-sm btn-export" onClick=${function () {
                window.open('/api/artifacts/' + props.artifactId + '/export?file=' + encodeURIComponent(currentFile) + '&format=xlsx');
              }}>⬇ XLSX</button>
            </>`}
            <button class="btn-close-viewer" onClick=${props.onClose}>✕</button>
          </div>
        </div>

        ${sheetData && sheetData.length > 1 && h`<div class="viewer-tabs">
          ${sheetData.map(function (sheet, idx) {
            return h`<button key=${idx}
              class=${'viewer-tab' + (idx === activeSheet ? ' active' : '')}
              onClick=${function () { setActiveSheet(idx); }}>
              ${sheet.name || 'Sheet ' + (idx + 1)}
            </button>`;
          })}
        </div>`}

        <div class="viewer-body" ref=${bodyRef}>
          ${loading && h`<div class="loading"><div class="spinner"></div><span>Loading…</span></div>`}
          ${error && h`<div class="empty-state"><div class="icon">⚠️</div><p>${error}</p></div>`}
          ${!loading && !error && files && !sheetData && h`<ul class="file-list">
            ${files.map(function (f) {
              var shortName = f.name.split('/').pop();
              return h`<li key=${f.name} class="file-list-item">
                <div class="file-list-info" style=${{ cursor: 'pointer' }}
                  onClick=${function () { loadExcelFile(f.name); }}>
                  <span class="file-icon">📊</span>
                  <span class="file-name">${shortName}</span>
                  <span class="file-size">${formatSize(f.size)}</span>
                </div>
              </li>`;
            })}
          </ul>`}
          ${!loading && !error && sheetData && renderTable(sheetData[activeSheet])}
        </div>
      </div>
    </div>`;
  }

  // ─── Main App Component ───
  function App() {
    var _s1 = useState(null); var username = _s1[0]; var setUsername = _s1[1];
    var _s2 = useState([]); var runs = _s2[0]; var setRuns = _s2[1];
    var _s3 = useState(true); var runsLoading = _s3[0]; var setRunsLoading = _s3[1];
    var _s4 = useState(null); var runsError = _s4[0]; var setRunsError = _s4[1];
    var _s5 = useState(null); var selectedRunId = _s5[0]; var setSelectedRunId = _s5[1];
    var _s6 = useState([]); var artifacts = _s6[0]; var setArtifacts = _s6[1];
    var _s7 = useState(false); var artifactsLoading = _s7[0]; var setArtifactsLoading = _s7[1];
    var _s8 = useState(null); var viewerArtifact = _s8[0]; var setViewerArtifact = _s8[1];
    var _s9 = useState(null); var viewerTitle = _s9[0]; var setViewerTitle = _s9[1];
    var _s10 = useState(''); var search = _s10[0]; var setSearch = _s10[1];
    var _s11 = useState([]); var toasts = _s11[0]; var setToasts = _s11[1];
    var _s12 = useState(true); var connected = _s12[0]; var setConnected = _s12[1];
    var _s13 = useState(null); var lastPoll = _s13[0]; var setLastPoll = _s13[1];
    var _s14 = useState(new Set()); var newRunIds = _s14[0]; var setNewRunIds = _s14[1];

    var REFRESH_INTERVAL = 120;
    var toastIdRef = useRef(0);
    var pollTimerRef = useRef(null);
    var sseRef = useRef(null);

    function addToast(message, type) {
      var id = ++toastIdRef.current;
      setToasts(function (prev) { return prev.concat([{ id: id, message: message, type: type || 'info' }]); });
      setTimeout(function () {
        setToasts(function (prev) { return prev.filter(function (t) { return t.id !== id; }); });
      }, 5000);
    }

    function dismissToast(id) {
      setToasts(function (prev) { return prev.filter(function (t) { return t.id !== id; }); });
    }

    // Session check
    useEffect(function () {
      fetch('/auth/session').then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.authenticated) { window.location.href = '/'; return; }
          setUsername(data.username);
        })
        .catch(function () { window.location.href = '/'; });

      fetchCsrf();
    }, []);

    // Load runs
    var loadRuns = useCallback(async function () {
      try {
        setRunsLoading(function (prev) { return runs.length === 0 ? true : prev; });
        var data = await api('/api/runs');
        var prevIds = new Set(runs.map(function (r) { return r.id; }));
        var nextRuns = data.runs || [];

        if (runs.length > 0) {
          var freshIds = new Set();
          nextRuns.forEach(function (r) {
            if (!prevIds.has(r.id)) freshIds.add(r.id);
          });
          if (freshIds.size > 0) {
            setNewRunIds(freshIds);
            addToast(freshIds.size + ' new workflow run(s) detected!', 'success');
            setTimeout(function () { setNewRunIds(new Set()); }, 15000);
          }
        }

        setRuns(nextRuns);
        setRunsError(null);
        setLastPoll(new Date().toISOString());
      } catch (err) {
        setRunsError(err.message);
      } finally {
        setRunsLoading(false);
      }
    }, [runs]);

    // Initial load + periodic polling
    useEffect(function () {
      loadRuns();
      pollTimerRef.current = setInterval(loadRuns, REFRESH_INTERVAL * 1000);
      return function () { clearInterval(pollTimerRef.current); };
    }, []);

    // SSE connection for real-time updates
    useEffect(function () {
      function connectSSE() {
        var es = new EventSource('/api/events');
        sseRef.current = es;

        es.onopen = function () { setConnected(true); };
        es.onerror = function () {
          setConnected(false);
          es.close();
          setTimeout(connectSSE, 5000);
        };
        es.addEventListener('newRun', function (e) {
          try {
            var payload = JSON.parse(e.data);
            addToast('New artifacts from Run #' + payload.run.runNumber, 'success');
            loadRuns();
          } catch (err) { /* ignore parse errors */ }
        });
      }

      connectSSE();

      return function () {
        if (sseRef.current) sseRef.current.close();
      };
    }, []);

    // Session keep-alive (every 5 minutes)
    useEffect(function () {
      var keepAlive = setInterval(function () {
        fetch('/auth/session').then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.authenticated) { window.location.href = '/'; }
          }).catch(function () {});
      }, 5 * 60 * 1000);
      return function () { clearInterval(keepAlive); };
    }, []);

    // Load artifacts when a run is selected
    useEffect(function () {
      if (!selectedRunId) return;
      setArtifactsLoading(true);
      api('/api/runs/' + selectedRunId + '/artifacts')
        .then(function (data) { setArtifacts(data.artifacts || []); })
        .catch(function () { setArtifacts([]); })
        .finally(function () { setArtifactsLoading(false); });
    }, [selectedRunId]);

    async function handleLogout() {
      await fetch('/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken } });
      window.location.href = '/';
    }

    function handleViewArtifact(artifactId, name) {
      setViewerArtifact(artifactId);
      setViewerTitle(name);
    }

    function handleDownload(artifactId, name) {
      var a = document.createElement('a');
      a.href = '/api/artifacts/' + artifactId + '/download';
      a.download = (name || 'artifact') + '.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }

    if (!username) {
      return h`<div class="loading"><div class="spinner"></div><span>Initializing…</span></div>`;
    }

    return h`<div class="app-root">
      <${Header}
        username=${username}
        connected=${connected}
        lastPoll=${lastPoll}
        refreshInterval=${REFRESH_INTERVAL}
        onLogout=${handleLogout} />

      <main class="main-content">
        <div class="page-header-row">
          <div>
            <h1 class="page-title">Workflow Reports</h1>
            <p class="page-desc">Auto-updating dashboard – new artifacts appear in real-time.</p>
          </div>
          <${SearchBar} value=${search} onChange=${setSearch} />
        </div>

        <${RunList}
          runs=${runs} loading=${runsLoading} error=${runsError}
          selectedRunId=${selectedRunId} search=${search}
          newRunIds=${newRunIds}
          onSelect=${function (id) { setSelectedRunId(id); }} />

        <${ArtifactPanel}
          visible=${!!selectedRunId}
          artifacts=${artifacts} loading=${artifactsLoading}
          onView=${handleViewArtifact}
          onDownload=${handleDownload} />
      </main>

      ${viewerArtifact && h`<${ExcelViewerModal}
        visible=${true} artifactId=${viewerArtifact} title=${viewerTitle}
        onClose=${function () { setViewerArtifact(null); }} />`}

      <${ToastContainer} toasts=${toasts} onDismiss=${dismissToast} />
    </div>`;
  }

  // ─── Mount ───
  var root = ReactDOM.createRoot(document.getElementById('app-root'));
  root.render(h`<${App} />`);
})();
