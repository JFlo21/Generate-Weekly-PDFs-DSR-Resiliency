const https = require('node:https');
const { Readable } = require('node:stream');
const config = require('../config/default');

const API_BASE = 'https://api.github.com';

function makeHeaders() {
  const headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'LinetecReportPortal/1.0',
    'X-GitHub-Api-Version': '2022-11-28',
  };
  if (config.github.token) {
    headers['Authorization'] = `Bearer ${config.github.token}`;
  }
  return headers;
}

function request(urlPath, options = {}) {
  return new Promise((resolve, reject) => {
    const url = urlPath.startsWith('http') ? new URL(urlPath) : new URL(`${API_BASE}${urlPath}`);
    const reqOptions = {
      hostname: url.hostname,
      path: url.pathname + url.search,
      method: options.method || 'GET',
      headers: { ...makeHeaders(), ...options.headers },
    };

    const req = https.request(reqOptions, (res) => {
      if (options.followRedirect && (res.statusCode === 301 || res.statusCode === 302)) {
        return resolve(request(res.headers.location, options));
      }
      if (options.rawStream) {
        return resolve({ statusCode: res.statusCode, headers: res.headers, stream: res });
      }
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const body = Buffer.concat(chunks);
        if (options.binary) {
          return resolve({ statusCode: res.statusCode, body });
        }
        try {
          resolve({ statusCode: res.statusCode, body: JSON.parse(body.toString()) });
        } catch {
          resolve({ statusCode: res.statusCode, body: body.toString() });
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('Request timeout')); });
    req.end();
  });
}

async function listWorkflowRuns(page = 1, perPage = 30) {
  const { owner, repo } = config.github;
  const path = `/repos/${owner}/${repo}/actions/workflows/weekly-excel-generation.yml/runs?status=completed&per_page=${perPage}&page=${page}`;
  const { statusCode, body } = await request(path);
  if (statusCode !== 200) {
    throw new Error(`GitHub API error ${statusCode}: ${JSON.stringify(body)}`);
  }
  return body;
}

async function listRunArtifacts(runId) {
  const { owner, repo } = config.github;
  const path = `/repos/${owner}/${repo}/actions/runs/${runId}/artifacts?per_page=100`;
  const { statusCode, body } = await request(path);
  if (statusCode !== 200) {
    throw new Error(`GitHub API error ${statusCode}: ${JSON.stringify(body)}`);
  }
  return body;
}

async function downloadArtifact(artifactId) {
  const { owner, repo } = config.github;
  const path = `/repos/${owner}/${repo}/actions/artifacts/${artifactId}/zip`;
  const result = await request(path, { followRedirect: true, binary: true });
  if (result.statusCode !== 200) {
    throw new Error(`Download failed with status ${result.statusCode}`);
  }
  return result.body;
}

async function getArtifactsByWorkRequest() {
  const runsData = await listWorkflowRuns(1, 10);
  const runs = runsData.workflow_runs || [];

  const artifactsByWR = {};

  for (const run of runs) {
    const artifactsData = await listRunArtifacts(run.id);
    const artifacts = artifactsData.artifacts || [];

    for (const artifact of artifacts) {
      const match = artifact.name.match(/^By-WorkRequest/);
      const isManifest = artifact.name.match(/^Manifest/);
      const isComplete = artifact.name.match(/^Excel-Reports-Complete/);

      if (match || isManifest || isComplete) {
        const runInfo = {
          artifactId: artifact.id,
          artifactName: artifact.name,
          runId: run.id,
          runNumber: run.run_number,
          createdAt: run.created_at,
          updatedAt: run.updated_at,
          sizeInBytes: artifact.size_in_bytes,
          expired: artifact.expired,
        };

        const key = isManifest ? '__manifest__' : (isComplete ? '__complete__' : artifact.name);
        if (!artifactsByWR[key]) {
          artifactsByWR[key] = [];
        }
        artifactsByWR[key].push(runInfo);
      }
    }
  }

  return artifactsByWR;
}

module.exports = {
  listWorkflowRuns,
  listRunArtifacts,
  downloadArtifact,
  getArtifactsByWorkRequest,
};
