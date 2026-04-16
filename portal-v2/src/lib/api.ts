import type { WorkflowRun, Artifact, ExcelSheet } from './types';
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

  downloadArtifact(artifactId: number, filename: string): void {
    const url = `${API_BASE}/api/artifacts/${artifactId}/download`;
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
  },

  healthCheck(): Promise<{ status: string }> {
    return request<{ status: string }>('/health');
  },
};
