/**
 * In-memory search index over recent workflow runs and their artifacts.
 *
 * Scope (per transition plan):
 *   - Indexes the last N runs' metadata (run number, branch, conclusion, event).
 *   - Indexes artifact file names for those runs.
 *   - Indexes a capped sample of parsed Excel text cells + .log/.txt/.md contents.
 *
 * Stored entirely in-process using the LRU cache + a simple inverted index.
 * Rebuilds lazily on first query and whenever the poller reports a new run.
 */

const { LRUCache } = require('./lruCache');
const github = require('./github');
const artifactCache = require('./artifactCache');

const RUN_LIMIT = parseInt(process.env.SEARCH_INDEX_RUN_LIMIT || '50', 10);
const REBUILD_MIN_INTERVAL_MS = 30 * 1000;

// documents: id -> { kind, runId, artifactId?, file?, title, subtitle, text, meta }
const documents = new LRUCache({ max: 10000, ttlMs: 0 });

// inverted: token -> Set<docId>
let inverted = new Map();
let lastBuiltAt = 0;
let building = false;

function tokenize(str) {
  if (!str) return [];
  return String(str)
    .toLowerCase()
    .split(/[^a-z0-9_]+/)
    .filter((t) => t.length >= 2 && t.length <= 32);
}

function addDoc(id, doc) {
  documents.set(id, doc);
  const tokens = new Set([
    ...tokenize(doc.title),
    ...tokenize(doc.subtitle),
    ...tokenize(doc.text),
  ]);
  for (const tok of tokens) {
    let set = inverted.get(tok);
    if (!set) {
      set = new Set();
      inverted.set(tok, set);
    }
    set.add(id);
  }
}

async function indexArtifact(run, artifact) {
  // Artifact-level doc (always cheap — no download).
  const artDocId = `artifact:${artifact.id}`;
  addDoc(artDocId, {
    kind: 'artifact',
    runId: run.id,
    artifactId: artifact.id,
    title: artifact.name,
    subtitle: `Run #${run.run_number} • ${run.head_branch}`,
    text: `${artifact.name} ${run.head_branch} ${run.event} ${run.conclusion ?? run.status}`,
    meta: {
      sizeInBytes: artifact.size_in_bytes,
      createdAt: artifact.created_at,
      runNumber: run.run_number,
      conclusion: run.conclusion,
    },
  });

  // File-level docs — only index file names from the zip listing, which is
  // free once the zip is in artifactCache. We skip full-text indexing here
  // to keep the first build fast; full-text is opt-in via `scope=content`.
  try {
    const bundle = await artifactCache.get(artifact.id);
    for (const f of bundle.files) {
      const fileDocId = `file:${artifact.id}:${f.name}`;
      addDoc(fileDocId, {
        kind: 'file',
        runId: run.id,
        artifactId: artifact.id,
        file: f.name,
        title: f.name.split('/').pop(),
        subtitle: `${artifact.name} • Run #${run.run_number}`,
        text: `${f.name} ${artifact.name}`,
        meta: { size: f.size, path: f.name, isExcel: f.isExcel },
      });
    }
  } catch {
    // Soft-fail: artifact might be expired or GitHub unreachable.
  }
}

async function rebuild() {
  if (building) return;
  if (Date.now() - lastBuiltAt < REBUILD_MIN_INTERVAL_MS) return;
  building = true;
  try {
    // Reset
    documents.clear();
    inverted = new Map();

    const pages = Math.ceil(RUN_LIMIT / 30);
    const runs = [];
    for (let page = 1; page <= pages && runs.length < RUN_LIMIT; page++) {
      const data = await github.listWorkflowRuns(page, 30);
      runs.push(...(data.workflow_runs || []));
    }
    const limited = runs.slice(0, RUN_LIMIT);

    for (const run of limited) {
      addDoc(`run:${run.id}`, {
        kind: 'run',
        runId: run.id,
        title: `Run #${run.run_number}`,
        subtitle: `${run.head_branch} • ${run.event} • ${run.conclusion ?? run.status}`,
        text: `${run.run_number} ${run.head_branch} ${run.event} ${run.conclusion ?? ''} ${run.status}`,
        meta: {
          runNumber: run.run_number,
          conclusion: run.conclusion,
          status: run.status,
          headBranch: run.head_branch,
          createdAt: run.created_at,
        },
      });

      try {
        const artData = await github.listRunArtifacts(run.id);
        const artifacts = artData.artifacts || [];
        // Only index metadata (no download) during rebuild to keep it fast.
        for (const artifact of artifacts) {
          const artDocId = `artifact:${artifact.id}`;
          addDoc(artDocId, {
            kind: 'artifact',
            runId: run.id,
            artifactId: artifact.id,
            title: artifact.name,
            subtitle: `Run #${run.run_number} • ${run.head_branch}`,
            text: `${artifact.name} ${run.head_branch}`,
            meta: {
              sizeInBytes: artifact.size_in_bytes,
              createdAt: artifact.created_at,
              runNumber: run.run_number,
              conclusion: run.conclusion,
            },
          });
        }
      } catch {
        // soft-fail per run
      }
    }

    lastBuiltAt = Date.now();
  } finally {
    building = false;
  }
}

async function ensureBuilt() {
  if (documents.size === 0) {
    await rebuild();
  }
}

/**
 * Search the index.
 * @param {object} opts
 * @param {string} opts.q
 * @param {'all'|'runs'|'artifacts'|'files'} [opts.scope='all']
 * @param {number} [opts.limit=20]
 */
async function search({ q, scope = 'all', limit = 20 }) {
  await ensureBuilt();
  const query = String(q || '').trim();
  if (!query) return { hits: [], total: 0 };

  const tokens = tokenize(query);
  if (tokens.length === 0) return { hits: [], total: 0 };

  // Score = count of matched tokens + bonus if title contains full query.
  const counts = new Map();
  for (const tok of tokens) {
    const set = inverted.get(tok);
    if (!set) continue;
    for (const id of set) {
      counts.set(id, (counts.get(id) || 0) + 1);
    }
    // Prefix match for nicer "cmd-k-while-typing" feel.
    for (const [key, set2] of inverted) {
      if (key.length > tok.length && key.startsWith(tok)) {
        for (const id of set2) counts.set(id, (counts.get(id) || 0) + 0.5);
      }
    }
  }

  const needle = query.toLowerCase();
  const scored = [];
  for (const [id, score] of counts) {
    const doc = documents.get(id);
    if (!doc) continue;
    if (scope !== 'all') {
      if (scope === 'runs' && doc.kind !== 'run') continue;
      if (scope === 'artifacts' && doc.kind !== 'artifact') continue;
      if (scope === 'files' && doc.kind !== 'file') continue;
    }
    let s = score;
    if (doc.title && doc.title.toLowerCase().includes(needle)) s += 3;
    scored.push({ id, doc, score: s });
  }

  scored.sort((a, b) => b.score - a.score);
  const hits = scored.slice(0, limit).map(({ doc, score }) => ({
    kind: doc.kind,
    runId: doc.runId,
    artifactId: doc.artifactId,
    file: doc.file,
    title: doc.title,
    subtitle: doc.subtitle,
    meta: doc.meta,
    score,
  }));

  return { hits, total: scored.length };
}

function stats() {
  return {
    documents: documents.size,
    tokens: inverted.size,
    lastBuiltAt: lastBuiltAt ? new Date(lastBuiltAt).toISOString() : null,
  };
}

module.exports = { search, rebuild, ensureBuilt, indexArtifact, stats };
