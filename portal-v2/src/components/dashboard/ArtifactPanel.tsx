import { AnimatePresence, motion } from 'framer-motion';
import { Package, Eye, Download, X, Lock } from 'lucide-react';
import type { Artifact, WorkflowRun } from '../../lib/types';
import { formatSize } from '../../lib/utils';
import { Skeleton } from '../ui/Skeleton';
import { api } from '../../lib/api';
import { useAuth } from '../../hooks/useAuth';

interface ArtifactPanelProps {
  run: WorkflowRun | null;
  artifacts: Artifact[];
  loading: boolean;
  onClose: () => void;
  onViewExcel: (artifact: Artifact) => void;
}

export function ArtifactPanel({
  run,
  artifacts,
  loading,
  onClose,
  onViewExcel,
}: ArtifactPanelProps) {
  const { profile } = useAuth();
  const canDownload = profile?.role === 'admin' || profile?.role === 'biller';
  return (
    <AnimatePresence>
      {run && (
        <motion.div
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
          className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Package size={16} className="text-brand-red" />
              <span className="text-sm font-semibold text-slate-800">
                Artifacts — {run.name} #{run.run_number}
              </span>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 transition-colors"
              aria-label="Close artifact panel"
            >
              <X size={16} />
            </button>
          </div>

          {/* Content */}
          <div className="p-4">
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : artifacts.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-6">
                No artifacts for this run.
              </p>
            ) : (
              <div className="space-y-2">
                {artifacts.map((artifact, i) => (
                  <motion.div
                    key={artifact.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Package size={14} className="text-slate-400 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">
                          {artifact.name}
                        </p>
                        <p className="text-xs text-slate-400">
                          {formatSize(artifact.size_in_bytes)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {/\.(xlsx|xls)$/i.test(artifact.name) ||
                      artifact.name.toLowerCase().includes('excel') ? (
                        <button
                          onClick={() => onViewExcel(artifact)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-violet-50 text-violet-700 hover:bg-violet-100 transition-colors"
                        >
                          <Eye size={12} />
                          View
                        </button>
                      ) : null}
                      {canDownload ? (
                        <button
                          onClick={() => api.downloadArtifact(artifact.id, artifact.name)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-brand-red/10 text-brand-red hover:bg-brand-red/20 transition-colors"
                        >
                          <Download size={12} />
                          Download
                        </button>
                      ) : (
                        <button
                          disabled
                          aria-label="Download not available — Biller or Admin role required"
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-400 cursor-not-allowed select-none"
                        >
                          <Lock size={12} />
                          Download
                        </button>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
