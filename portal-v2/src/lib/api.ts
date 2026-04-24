import type {
  WorkflowRun,
  Artifact,
  ExcelSheet,
  ArtifactFile,
  ParsedWorkbook,
  TextPreview,
  SearchHit,
  Job,
} from './types';
import * as Sentry from '@sentry/react';
import {
  USE_MOCK,
  MOCK_RUNS,
  MOCK_ARTIFACTS,
  MOCK_FILES,
  MOCK_WORKBOOKS,
  MOCK_LOG,
  MOCK_MANIFEST,
  MOCK_JOBS,
  mockSearch,
} from './mockData';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

type RunsResponse = { total?: number; runs?: WorkflowRun[] };
type ArtifactsResponse = { total?: number; artifacts?: Artifact[] };

function normalizeRun(run: Record<string, unknown>): WorkflowRun {
  return {
    id: Number(run.id),
    name: String(run.name ?? 'Workflow Run'),
    status: String(run.status ?? 'unknown'),
    conclusion: (run.conclusion as string | null) ?? null,
    run_number: Number(run.run_number ?? run.runNumber ?? 0),
    created_at: String(run.created_at ?? run.createdAt ?? ''),
    updated_at: String(run.updated_at ?? run.updatedAt ?? ''),
    html_url: String(run.html_url ?? run.htmlUrl ?? ''),
    head_branch: String(run.head_branch ?? run.headBranch ?? ''),
    head_sha: String(run.head_sha ?? run.headSha ?? ''),
    event: run.event ? String(run.event) : undefined,
    actor: run.actor as WorkflowRun['actor'],
  };
}

function normalizeArtifact(artifact: Record<string, unknown>): Artifact {
  return {
    id: Number(artifact.id),
    name: String(artifact.name ?? 'artifact.zip'),
    size_in_bytes: Number(artifact.size_in_bytes ?? artifact.sizeInBytes ?? 0),
    archive_download_url: String(
      artifact.archive_download_url ?? artifact.archiveDownloadUrl ?? ''
    ),
    expired: Boolean(artifact.expired),
    created_at: String(artifact.created_at ?? artifact.createdAt ?? ''),
    expires_at: String(artifact.expires_at ?? artifact.expiresAt ?? ''),
  };
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    credentials: 'include',
    ...options,
  });
  if (!res.ok) {
    Sentry.addBreadcrumb({
      category: 'api',
      message: `${options?.method ?? 'GET'} ${url} → ${res.status}`,
      level: 'error',
      data: { status: res.status, statusText: res.statusText },
    });
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getRuns(): Promise<WorkflowRun[]> {
    if (USE_MOCK) return Promise.resolve(MOCK_RUNS);
    return request<WorkflowRun[] | RunsResponse>('/api/runs').then((payload) => {
      const runs = Array.isArray(payload) ? payload : payload.runs ?? [];
      return runs.map((run) => normalizeRun(run as unknown as Record<string, unknown>));
    });
  },

  getArtifacts(runId: number): Promise<Artifact[]> {
    if (USE_MOCK) return Promise.resolve(MOCK_ARTIFACTS[runId] ?? []);
    return request<Artifact[] | ArtifactsResponse>(`/api/runs/${runId}/artifacts`).then((payload) => {
      const artifacts = Array.isArray(payload) ? payload : payload.artifacts ?? [];
      return artifacts.map((artifact) => normalizeArtifact(artifact as unknown as Record<string, unknown>));
    });
  },

  getLatestRun(): Promise<WorkflowRun> {
    if (USE_MOCK) return Promise.resolve(MOCK_RUNS[0]);
    return request<WorkflowRun>('/api/latest');
  },

  getExcelData(artifactId: number): Promise<ExcelSheet[]> {
    if (USE_MOCK) {
      const files = MOCK_FILES[artifactId] ?? [];
      const xlsx = files.find(f => f.isExcel);
      const wb = xlsx ? MOCK_WORKBOOKS[xlsx.name] : null;
      if (wb) {
        return Promise.resolve(wb.sheets.map(s => ({ name: s.name, rows: s.rows.map(r => r.cells.map(c => c.value)) })));
      }
      return Promise.resolve([]);
    }
    return request<ExcelSheet[]>(`/api/artifacts/${artifactId}/excel`);
  },

  getArtifactFiles(artifactId: number): Promise<{ files: ArtifactFile[] }> {
    if (USE_MOCK) return Promise.resolve({ files: MOCK_FILES[artifactId] ?? [] });
    return request<{ files: ArtifactFile[] }>(`/api/artifacts/${artifactId}/files`);
  },

  getExcelPreview(
    artifactId: number,
    file: string,
    sheet?: string
  ): Promise<ParsedWorkbook> {
    if (USE_MOCK) {
      const wb = MOCK_WORKBOOKS[file];
      if (wb) return Promise.resolve(wb);
      return Promise.reject(new Error('File not found'));
    }
    const q = new URLSearchParams({ file, as: 'json' });
    if (sheet) q.set('sheet', sheet);
    return request<ParsedWorkbook>(
      `/api/artifacts/${artifactId}/preview?${q.toString()}`
    );
  },

  getTextPreview(artifactId: number, file: string): Promise<TextPreview> {
    if (USE_MOCK) {
      if (file === 'build.log') return Promise.resolve(MOCK_LOG);
      if (file === 'manifest.json') {
        return Promise.resolve({
          filename: file,
          text: JSON.stringify(MOCK_MANIFEST, null, 2),
          truncated: false,
          totalSize: 256,
        });
      }
      return Promise.resolve({ filename: file, text: 'No preview available', truncated: false, totalSize: 0 });
    }
    const q = new URLSearchParams({ file, as: 'text' });
    return request<TextPreview>(
      `/api/artifacts/${artifactId}/preview?${q.toString()}`
    );
  },

  /** URL for the styled-HTML snapshot — fed straight into <iframe src> */
  getExcelHtmlUrl(artifactId: number, file: string, sheet?: string): string {
    const q = new URLSearchParams({ file, as: 'html' });
    if (sheet) q.set('sheet', sheet);
    return `${API_BASE}/api/artifacts/${artifactId}/preview?${q.toString()}`;
  },

  /** URL for inline image preview. */
  getFileInlineUrl(artifactId: number, file: string): string {
    const q = new URLSearchParams({ file, inline: '1' });
    return `${API_BASE}/api/artifacts/${artifactId}/file?${q.toString()}`;
  },

  /** Download a single file out of the zip with its original filename. */
  downloadFile(artifactId: number, file: string): void {
    const q = new URLSearchParams({ file });
    const url = `${API_BASE}/api/artifacts/${artifactId}/file?${q.toString()}`;
    const a = document.createElement('a');
    a.href = url;
    a.rel = 'noopener';
    a.click();
  },

  downloadArtifact(artifactId: number, filename: string): void {
    const url = `${API_BASE}/api/artifacts/${artifactId}/download`;
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
  },

  async search(
    q: string,
    scope: 'all' | 'runs' | 'artifacts' | 'files' = 'all',
    limit = 20
  ): Promise<{ hits: SearchHit[]; total: number }> {
    if (USE_MOCK) {
      const hits = mockSearch(q).slice(0, limit);
      return { hits, total: hits.length };
    }
    const params = new URLSearchParams({ q, scope, limit: String(limit) });
    try {
      return await request<{ hits: SearchHit[]; total: number }>(
        `/api/search?${params.toString()}`
      );
    } catch (err) {
      // Fall back to the in-memory mock index if the backend is unreachable
      // (CORS/offline/DNS) so the palette still returns useful results.
      const msg = err instanceof Error ? err.message : String(err);
      if (err instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(msg)) {
        const hits = mockSearch(q).slice(0, limit);
        return { hits, total: hits.length };
      }
      throw err;
    }
  },

  getJobs(runId: number): Promise<{ jobs: Job[] }> {
    if (USE_MOCK) return Promise.resolve({ jobs: MOCK_JOBS[runId] ?? [] });
    return request<{ jobs: Job[] }>(`/api/runs/${runId}/jobs`);
  },

  healthCheck(): Promise<{ status: string }> {
    return request<{ status: string }>('/health');
  },
};
