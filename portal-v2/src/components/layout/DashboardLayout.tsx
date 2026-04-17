import { useCallback, useMemo, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { useRuns } from '../../hooks/useRuns';
import { useCommandPalette } from '../../hooks/useCommandPalette';
import { CommandPalette } from '../dashboard/CommandPalette';
import type { SearchHit, WorkflowRun } from '../../lib/types';

export interface DashboardOutletContext {
  runs: WorkflowRun[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  paletteTarget: { runId: number; artifactId?: number; file?: string } | null;
  clearPaletteTarget: () => void;
  openCommandPalette: () => void;
}

export function DashboardLayout() {
  const { runs, loading, error, countdown, refresh, isConnected } = useRuns();
  const { open, close, openPalette } = useCommandPalette();
  const navigate = useNavigate();

  const [paletteTarget, setPaletteTarget] = useState<
    { runId: number; artifactId?: number; file?: string } | null
  >(null);

  const clearPaletteTarget = useCallback(() => setPaletteTarget(null), []);

  const handleSelect = useCallback(
    (hit: SearchHit) => {
      // All hits ultimately tie back to a run, which the dashboard page can
      // focus. Artifact/file hits additionally tell the page which artifact
      // to open in the Explorer.
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
      runs,
      loading,
      error,
      refresh,
      paletteTarget,
      clearPaletteTarget,
      openCommandPalette: openPalette,
    }),
    [runs, loading, error, refresh, paletteTarget, clearPaletteTarget, openPalette]
  );

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <Navbar
        countdown={countdown}
        isConnected={isConnected}
        onRefresh={refresh}
        onOpenCommandPalette={openPalette}
      />
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
