import { AnimatePresence, motion } from 'framer-motion';
import { AlertCircle } from 'lucide-react';
import type { WorkflowRun } from '../../lib/types';
import { RunCard } from './RunCard';
import { Skeleton } from '../ui/Skeleton';

interface RunListProps {
  runs: WorkflowRun[];
  loading: boolean;
  error: string | null;
  selectedId: number | null;
  onSelect: (run: WorkflowRun) => void;
}

export function RunList({ runs, loading, error, selectedId, onSelect }: RunListProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center justify-center py-16 px-4"
      >
        <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-red-50 mb-4">
          <AlertCircle size={20} className="text-red-600" />
        </div>
        <p className="text-sm font-medium text-slate-900 mb-1">Failed to load runs</p>
        <p className="text-xs text-slate-500 max-w-sm">{error}</p>
      </motion.div>
    );
  }

  if (runs.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-center py-12 text-sm text-slate-400"
      >
        No workflow runs found.
      </motion.div>
    );
  }

  return (
    <div className="space-y-3">
      <AnimatePresence initial={false}>
        {runs.map((run, i) => (
          <RunCard
            key={run.id}
            run={run}
            index={i}
            isSelected={run.id === selectedId}
            onClick={() => onSelect(run)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
