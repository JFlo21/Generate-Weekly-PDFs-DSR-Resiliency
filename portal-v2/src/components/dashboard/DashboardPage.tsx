import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useArtifacts } from '../../hooks/useArtifacts';
import { api } from '../../lib/api';
import type { WorkflowRun, Artifact } from '../../lib/types';
import type { DashboardOutletContext } from '../layout/DashboardLayout';
import { StatsGrid } from './StatsGrid';
import { SearchBar } from './SearchBar';
import { RunList } from './RunList';
import { ArtifactPanel } from './ArtifactPanel';
import { ArtifactExplorer } from './ArtifactExplorer';

export function DashboardPage() {
  const {
    runs,
    loading,
    error,
    paletteTarget,
    clearPaletteTarget,
  } = useOutletContext<DashboardOutletContext>();

  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [search, setSearch] = useState('');
  const [exploringArtifact, setExploringArtifact] = useState<Artifact | null>(null);
  const [pendingArtifactId, setPendingArtifactId] = useState<number | null>(null);
  const [pendingFile, setPendingFile] = useState<string | null>(null);

  const { artifacts, loading: artifactsLoading } = useArtifacts(
    selectedRun?.id ?? null
  );

  // Respond to a Cmd+K selection: focus the run, remember the target artifact
  // (to be opened when useArtifacts returns), and optionally remember the
  // file to auto-select inside the explorer.
  useEffect(() => {
    if (!paletteTarget) return;
    const { runId, artifactId, file } = paletteTarget;
    const match = runs.find((r) => r.id === runId);
    if (match) setSelectedRun(match);
    setPendingArtifactId(artifactId ?? null);
    setPendingFile(file ?? null);
    clearPaletteTarget();
  }, [paletteTarget, runs, clearPaletteTarget]);

  // Once artifacts load for the selected run, open the stashed target.
  useEffect(() => {
    if (!pendingArtifactId) return;
    if (artifacts.length === 0) return;
    const art = artifacts.find((a) => a.id === pendingArtifactId);
    if (art) {
      setExploringArtifact(art);
      setPendingArtifactId(null);
    }
  }, [pendingArtifactId, artifacts]);

  // If the palette pointed at an artifact whose parent run is outside the
  // currently-loaded list, fetch it directly so the Explorer can still open.
  useEffect(() => {
    if (!pendingArtifactId) return;
    if (selectedRun) return; // will be picked up by the effect above
    let cancelled = false;
    api
      .getArtifactFiles(pendingArtifactId)
      .then(() => {
        if (cancelled) return;
        setExploringArtifact({
          id: pendingArtifactId,
          name: `Artifact #${pendingArtifactId}`,
          size_in_bytes: 0,
          archive_download_url: '',
          expired: false,
          created_at: new Date().toISOString(),
          expires_at: new Date().toISOString(),
        });
        setPendingArtifactId(null);
      })
      .catch(() => !cancelled && setPendingArtifactId(null));
    return () => {
      cancelled = true;
    };
  }, [pendingArtifactId, selectedRun]);

  const filtered = runs.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.head_branch.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="p-6 lg:p-8 space-y-6 max-w-6xl mx-auto"
    >
      <motion.div
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="flex flex-col gap-1.5"
      >
        <div className="flex items-center gap-2">
          <div className="w-1 h-6 rounded-full bg-gradient-to-b from-brand-red to-red-700" />
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Dashboard
          </h1>
        </div>
        <p className="text-sm text-slate-500 ml-3">
          Monitor workflow runs and explore artifact contents. Press{' '}
          <kbd className="inline-flex items-center font-mono text-[10px] border border-slate-200 rounded px-1.5 py-0.5 bg-white shadow-[0_1px_0_rgba(0,0,0,0.04)] text-slate-700">
            ⌘K
          </kbd>{' '}
          to search runs and artifacts.
        </p>
      </motion.div>

      <StatsGrid runs={runs} artifacts={artifacts} />

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        <div className="xl:col-span-3 space-y-4">
          <SearchBar value={search} onChange={setSearch} />
          <RunList
            runs={filtered}
            loading={loading}
            error={error}
            selectedId={selectedRun?.id ?? null}
            onSelect={(run) =>
              setSelectedRun((prev) => (prev?.id === run.id ? null : run))
            }
          />
        </div>

        <div className="xl:col-span-2">
          <ArtifactPanel
            run={selectedRun}
            artifacts={artifacts}
            loading={artifactsLoading}
            onClose={() => setSelectedRun(null)}
            onExplore={setExploringArtifact}
          />
        </div>
      </div>

      <ArtifactExplorer
        run={selectedRun}
        artifact={exploringArtifact}
        initialFile={pendingFile}
        onClose={() => {
          setExploringArtifact(null);
          setPendingFile(null);
        }}
      />
    </motion.div>
  );
}
