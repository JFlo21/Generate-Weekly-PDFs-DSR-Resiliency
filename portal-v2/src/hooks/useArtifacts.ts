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
      setError(null);
      return;
    }
    let stale = false;
    setLoading(true);
    setError(null);

    api
      .getArtifacts(runId)
      .then((data) => {
        if (!stale) setArtifacts(data);
      })
      .catch((err) => {
        if (!stale) {
          setError(
            err instanceof Error ? err.message : 'Failed to fetch artifacts'
          );
        }
      })
      .finally(() => {
        if (!stale) setLoading(false);
      });

    return () => { stale = true; };
  }, [runId]);

  return { artifacts, loading, error };
}
