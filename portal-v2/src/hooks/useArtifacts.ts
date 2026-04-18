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
        // Runtime fallback: if the run id matches a mock run, serve mock
        // artifacts instead of an error so the preview stays interactive.
        const mock = MOCK_ARTIFACTS[runId];
        if (import.meta.env.DEV && mock) {
          setArtifacts(mock);
          setError(null);
        } else {
          setError(
            err instanceof Error ? err.message : 'Failed to fetch artifacts'
          );
        }
      })
      .finally(() => setLoading(false));
  }, [runId]);

  return { artifacts, loading, error };
}
