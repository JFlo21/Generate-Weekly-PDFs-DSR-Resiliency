import { useState } from 'react';
import { motion } from 'framer-motion';
import { useRuns } from '../../hooks/useRuns';
import { useArtifacts } from '../../hooks/useArtifacts';
import { api } from '../../lib/api';
import type { WorkflowRun, Artifact, ExcelSheet } from '../../lib/types';
import { StatsGrid } from './StatsGrid';
import { SearchBar } from './SearchBar';
import { RunList } from './RunList';
import { ArtifactPanel } from './ArtifactPanel';
import { ExcelViewer } from './ExcelViewer';

export function DashboardPage() {
  const { runs, loading, error } = useRuns();
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [search, setSearch] = useState('');
  const [excelArtifact, setExcelArtifact] = useState<Artifact | null>(null);
  const [excelSheets, setExcelSheets] = useState<ExcelSheet[]>([]);
  const [excelLoading, setExcelLoading] = useState(false);
  const [excelError, setExcelError] = useState<string | null>(null);

  const { artifacts, loading: artifactsLoading } = useArtifacts(
    selectedRun?.id ?? null
  );

  const filtered = runs.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.head_branch.toLowerCase().includes(search.toLowerCase())
  );

  async function handleViewExcel(artifact: Artifact) {
    setExcelArtifact(artifact);
    setExcelSheets([]);
    setExcelLoading(true);
    setExcelError(null);
    try {
      const sheets = await api.getExcelData(artifact.id);
      setExcelSheets(sheets);
    } catch (err) {
      setExcelError(
        err instanceof Error ? err.message : 'Failed to load Excel data'
      );
    } finally {
      setExcelLoading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="p-6 space-y-6 max-w-6xl mx-auto"
    >
      <div>
        <h1 className="text-xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Monitor workflow runs and download artifacts
        </p>
      </div>

      <StatsGrid runs={runs} artifacts={artifacts} />

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        {/* Run list */}
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

        {/* Artifact panel */}
        <div className="xl:col-span-2">
          <ArtifactPanel
            run={selectedRun}
            artifacts={artifacts}
            loading={artifactsLoading}
            onClose={() => setSelectedRun(null)}
            onViewExcel={handleViewExcel}
          />
        </div>
      </div>

      <ExcelViewer
        artifact={excelArtifact}
        sheets={excelSheets}
        loading={excelLoading}
        error={excelError}
        onClose={() => setExcelArtifact(null)}
      />
    </motion.div>
  );
}
