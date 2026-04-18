import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { MOCK_ARTIFACTS } from '../lib/mockData';
import type { Artifact } from '../lib/types';

export function useArtifacts(runId: number | null) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (runId === null) {
      setArtifacts([]);
      return;
    }
    setLoading(true);
    setError(null);

    api
      .getArtifacts(runId)
      .then((data) => {
        setArtifacts(data);
      })
      .catch((err) => {
        // Fall back to mock artifacts on network errors (CORS/offline/DNS)
        // so the preview stays interactive even when the backend is
        // unreachable. Real HTTP errors (4xx/5xx) still surface.
        const msg = err instanceof Error ? err.message : String(err);
        const isNetworkError =
          err instanceof TypeError ||
          /failed to fetch|networkerror|load failed/i.test(msg);
        const mock = MOCK_ARTIFACTS[runId] ?? MOCK_ARTIFACTS[1]; // fallback to first mock run
        if (isNetworkError && mock) {
          console.warn('[v0] Artifacts backend unreachable, using sample data.');
          setArtifacts(mock);
          setError(null);
        } else {
          setError(msg || 'Failed to fetch artifacts');
        }
      })
      .finally(() => setLoading(false));
  }, [runId]);

  return { artifacts, loading, error };
}
