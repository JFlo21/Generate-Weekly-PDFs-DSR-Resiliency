import { useCallback, useMemo, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { useCommandPalette } from '../../hooks/useCommandPalette';
import { CommandPalette } from '../dashboard/CommandPalette';
import type { SearchHit } from '../../lib/types';

export interface DashboardOutletContext {
  paletteTarget: { runId: number; artifactId?: number; file?: string } | null;
  clearPaletteTarget: () => void;
  openCommandPalette: () => void;
}

/**
 * DashboardLayout — Supabase-native shell.
 *
 * The legacy `useRuns()` run-polling (an EventSource to the removed Express/Railway
 * `/api/events` backend, plus `/api/runs` polling) was removed here: it 404'd in
 * production, leaked the Supabase JWT cross-origin to a dead host, and flipped a
 * false "Showing sample data — backend unreachable" banner above the real Supabase
 * table. The artifact data path is `useArtifactsInfinite` → Supabase (D-02). The
 * remaining `api.ts`-coupled bits (CommandPalette search) are dormant until opened
 * and are slated for removal with the rest of the Express surface in Phase 07.
 */
export function DashboardLayout() {
  const { open, close, openPalette } = useCommandPalette();
  const navigate = useNavigate();

  const [paletteTarget, setPaletteTarget] = useState<
    { runId: number; artifactId?: number; file?: string } | null
  >(null);

  const clearPaletteTarget = useCallback(() => setPaletteTarget(null), []);

  const handleSelect = useCallback(
    (hit: SearchHit) => {
      if (hit.runId) {
        setPaletteTarget({
          runId: hit.runId,
          artifactId: hit.artifactId,
          file: hit.file,
        });
      }
      navigate('/dashboard');
    },
    [navigate]
  );

  const ctx: DashboardOutletContext = useMemo(
    () => ({
      paletteTarget,
      clearPaletteTarget,
      openCommandPalette: openPalette,
    }),
    [paletteTarget, clearPaletteTarget, openPalette]
  );

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <Navbar onOpenCommandPalette={openPalette} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Outlet context={ctx} />
        </main>
      </div>

      <CommandPalette open={open} onClose={close} onSelect={handleSelect} />
    </div>
  );
}
