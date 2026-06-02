/**
 * useArtifacts — stub (TABLE-02 / D-02)
 *
 * The mock fallback and Express-coupled api.getArtifacts() call have been
 * removed. The real artifact data path is useArtifactsInfinite (Plan 02).
 * This file stays in the tree until Phase 07 performs the final Express
 * cleanup (D-02 minimal-blast-radius rule). Any lingering import will still
 * type-check until then.
 */
import type { Artifact } from '../lib/types';

export function useArtifacts(
  _runId: number | null
): { artifacts: Artifact[]; loading: boolean; error: undefined } {
  return { artifacts: [], loading: false, error: undefined };
}
