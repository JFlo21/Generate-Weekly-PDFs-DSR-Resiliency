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

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

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
    return request<WorkflowRun[]>('/api/runs');
  },

  getArtifacts(runId: number): Promise<Artifact[]> {
    return request<Artifact[]>(`/api/runs/${runId}/artifacts`);
  },

  getLatestRun(): Promise<WorkflowRun> {
    return request<WorkflowRun>('/api/latest');
  },

  getExcelData(artifactId: number): Promise<ExcelSheet[]> {
    return request<ExcelSheet[]>(`/api/artifacts/${artifactId}/excel`);
  },

  getArtifactFiles(artifactId: number): Promise<{ files: ArtifactFile[] }> {
    return request<{ files: ArtifactFile[] }>(`/api/artifacts/${artifactId}/files`);
  },

  getExcelPreview(
    artifactId: number,
    file: string,
    sheet?: string
  ): Promise<ParsedWorkbook> {
    const q = new URLSearchParams({ file, as: 'json' });
    if (sheet) q.set('sheet', sheet);
    return request<ParsedWorkbook>(
      `/api/artifacts/${artifactId}/preview?${q.toString()}`
    );
  },

  getTextPreview(artifactId: number, file: string): Promise<TextPreview> {
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

  search(
    q: string,
    scope: 'all' | 'runs' | 'artifacts' | 'files' = 'all',
    limit = 20
  ): Promise<{ hits: SearchHit[]; total: number }> {
    const params = new URLSearchParams({ q, scope, limit: String(limit) });
    return request<{ hits: SearchHit[]; total: number }>(
      `/api/search?${params.toString()}`
    );
  },

  getJobs(runId: number): Promise<{ jobs: Job[] }> {
    return request<{ jobs: Job[] }>(`/api/runs/${runId}/jobs`);
  },

  healthCheck(): Promise<{ status: string }> {
    return request<{ status: string }>('/health');
  },
};
