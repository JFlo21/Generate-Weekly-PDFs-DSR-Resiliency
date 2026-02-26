import { useState, useEffect } from 'react';
import { api } from '../lib/api';
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
        setError(
          err instanceof Error ? err.message : 'Failed to fetch artifacts'
        );
      })
      .finally(() => setLoading(false));
  }, [runId]);

  return { artifacts, loading, error };
}
