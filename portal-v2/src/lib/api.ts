import type { WorkflowRun, Artifact, ExcelSheet } from './types';

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    credentials: 'include',
    ...options,
  });
  if (!res.ok) {
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

  async downloadArtifact(artifactId: number, filename: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/artifacts/${artifactId}/download`, {
      credentials: 'include',
    });
    if (!res.ok) throw new Error(`Download failed: ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },

  healthCheck(): Promise<{ status: string }> {
    return request<{ status: string }>('/health');
  },
};
