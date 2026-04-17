/**
 * Artifact cache — downloads a GitHub Actions artifact zip once, parses it
 * into a convenient in-memory structure, and keeps it around in an LRU for
 * the TTL so that browsing multiple files / previews / searches in one
 * artifact doesn't re-download the zip.
 *
 * Structure returned by `get(artifactId)`:
 *   {
 *     artifactId: string,
 *     files: [{ name, size, isExcel, isText, isImage, isJson }],
 *     // lazy readers (called on demand, result cached per file):
 *     getBuffer(name) -> Buffer,
 *     getText(name)   -> string,
 *     getExcel(name)  -> Promise<ParsedWorkbook>   // memoized
 *   }
 */

const AdmZip = require('adm-zip');
const path = require('node:path');
const { LRUCache } = require('./lruCache');
const github = require('./github');
const excel = require('./excel');

const MAX_ENTRIES = parseInt(process.env.ARTIFACT_CACHE_MAX || '32', 10);
const TTL_MS = parseInt(process.env.ARTIFACT_CACHE_TTL_MS || String(15 * 60 * 1000), 10);

const cache = new LRUCache({ max: MAX_ENTRIES, ttlMs: TTL_MS });

function classify(name) {
  const lower = name.toLowerCase();
  const ext = path.extname(lower);
  return {
    isExcel: ext === '.xlsx' || ext === '.xls',
    isText: ['.txt', '.log', '.md', '.csv', '.json', '.yml', '.yaml'].includes(ext),
    isImage: ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].includes(ext),
    isJson: ext === '.json',
    isMarkdown: ext === '.md',
    isCsv: ext === '.csv',
    isLog: ext === '.log' || lower.includes('log'),
  };
}

async function buildEntry(artifactId) {
  const zipBuffer = await github.downloadArtifact(artifactId);
  const zip = new AdmZip(zipBuffer);
  const entries = zip.getEntries().filter((e) => !e.isDirectory);

  const fileIndex = new Map();
  for (const e of entries) fileIndex.set(e.entryName, e);

  const parsedExcel = new Map(); // filename -> ParsedWorkbook

  const files = entries.map((e) => ({
    name: e.entryName,
    size: e.header.size,
    ...classify(e.entryName),
  }));

  return {
    artifactId: String(artifactId),
    fetchedAt: Date.now(),
    files,
    getBuffer(name) {
      const entry = fileIndex.get(name);
      if (!entry) return null;
      return entry.getData();
    },
    getText(name) {
      const buf = this.getBuffer(name);
      return buf ? buf.toString('utf8') : null;
    },
    async getExcel(name) {
      if (parsedExcel.has(name)) return parsedExcel.get(name);
      const buf = this.getBuffer(name);
      if (!buf) return null;
      const parsed = await excel.parseExcelBuffer(buf);
      parsedExcel.set(name, parsed);
      return parsed;
    },
  };
}

/**
 * Get the cached artifact bundle, fetching + parsing lazily.
 * Concurrent requests for the same artifactId share a single in-flight promise.
 */
const inflight = new Map();

async function get(artifactId) {
  const key = String(artifactId);
  const cached = cache.get(key);
  if (cached) return cached;

  if (inflight.has(key)) return inflight.get(key);

  const p = (async () => {
    try {
      const entry = await buildEntry(artifactId);
      cache.set(key, entry);
      return entry;
    } finally {
      inflight.delete(key);
    }
  })();

  inflight.set(key, p);
  return p;
}

function invalidate(artifactId) {
  cache.delete(String(artifactId));
}

function stats() {
  return { ...cache.stats(), inflight: inflight.size };
}

module.exports = { get, invalidate, stats };
