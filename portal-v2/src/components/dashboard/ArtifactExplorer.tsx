import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Package,
  X,
  Download,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  FileJson,
  FileCode,
  Search,
} from 'lucide-react';
import { api } from '../../lib/api';
import type { Artifact, ArtifactFile, WorkflowRun } from '../../lib/types';
import { formatSize, cn } from '../../lib/utils';
import { Skeleton } from '../ui/Skeleton';
import { FilePreview } from './FilePreview';

interface ArtifactExplorerProps {
  run: WorkflowRun | null;
  artifact: Artifact | null;
  /** Optional file path to auto-select when the explorer opens. */
  initialFile?: string | null;
  onClose: () => void;
}

type FileTypeFilter = 'all' | 'excel' | 'text' | 'json' | 'image' | 'log';

const TYPE_FILTERS: Array<{ value: FileTypeFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'excel', label: 'Excel' },
  { value: 'log', label: 'Logs' },
  { value: 'json', label: 'JSON' },
  { value: 'text', label: 'Text' },
  { value: 'image', label: 'Images' },
];

function matchesType(f: ArtifactFile, t: FileTypeFilter) {
  switch (t) {
    case 'excel':
      return f.isExcel;
    case 'text':
      return f.isText && !f.isJson && !f.isLog && !f.isMarkdown;
    case 'json':
      return f.isJson;
    case 'image':
      return f.isImage;
    case 'log':
      return f.isLog;
    default:
      return true;
  }
}

function fileIcon(f: ArtifactFile) {
  if (f.isExcel) return <FileSpreadsheet size={14} className="text-emerald-600" />;
  if (f.isJson) return <FileJson size={14} className="text-amber-600" />;
  if (f.isImage) return <ImageIcon size={14} className="text-violet-600" />;
  if (f.isMarkdown) return <FileCode size={14} className="text-sky-600" />;
  if (f.isLog) return <FileText size={14} className="text-slate-500" />;
  return <FileText size={14} className="text-slate-400" />;
}

export function ArtifactExplorer({ run, artifact, initialFile, onClose }: ArtifactExplorerProps) {
  const [files, setFiles] = useState<ArtifactFile[] | null>(null);
  const [selected, setSelected] = useState<ArtifactFile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState<FileTypeFilter>('all');
  const [filterText, setFilterText] = useState('');

  useEffect(() => {
    if (!artifact) {
      setFiles(null);
      setSelected(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setFiles(null);
    setSelected(null);
    api
      .getArtifactFiles(artifact.id)
      .then((r) => {
        if (cancelled) return;
        setFiles(r.files);
        // If the palette targeted a specific file, prefer that. Otherwise
        // auto-select the first previewable file — Excel preferred.
        const initial = initialFile
          ? r.files.find((f) => f.name === initialFile)
          : undefined;
        const first =
          initial ??
          r.files.find((f) => f.isExcel) ??
          r.files.find((f) => f.isText || f.isJson || f.isImage) ??
          r.files[0] ??
          null;
        setSelected(first);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [artifact?.id, initialFile]);

  const filtered = useMemo(() => {
    if (!files) return [];
    const needle = filterText.toLowerCase();
    return files
      .filter((f) => matchesType(f, typeFilter))
      .filter((f) => (needle ? f.name.toLowerCase().includes(needle) : true));
  }, [files, typeFilter, filterText]);

  if (!run || !artifact) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm flex"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          initial={{ x: 40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 40, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 280, damping: 28 }}
          className="ml-auto bg-white w-full max-w-[1400px] h-full shadow-2xl flex flex-col"
        >
          {/* Top bar */}
          <header className="flex items-center justify-between gap-4 px-5 py-3 border-b border-slate-100 shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-brand-red/10 text-brand-red flex items-center justify-center shrink-0">
                <Package size={16} />
              </div>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-slate-900 truncate">
                  {artifact.name}
                </h2>
                <p className="text-xs text-slate-500 truncate">
                  {run.name} &middot; Run #{run.run_number} &middot;{' '}
                  {formatSize(artifact.size_in_bytes)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => api.downloadArtifact(artifact.id, `${artifact.name}.zip`)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
                title="Download full artifact zip"
              >
                <Download size={12} />
                Download zip
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>
          </header>

          {/* Body */}
          <div className="flex-1 min-h-0 flex">
            {/* Left pane — files */}
            <aside className="w-80 shrink-0 border-r border-slate-100 flex flex-col min-h-0 bg-slate-50">
              <div className="px-3 pt-3 pb-2 shrink-0 space-y-2.5 border-b border-slate-100 bg-white">
                <div className="relative">
                  <Search
                    size={13}
                    className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
                  />
                  <input
                    type="search"
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    placeholder="Filter files..."
                    className="w-full pl-7 pr-3 py-1.5 rounded-lg text-xs bg-slate-50 border border-slate-200 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
                  />
                </div>
                <div className="flex flex-wrap gap-1">
                  {TYPE_FILTERS.map((t) => (
                    <button
                      key={t.value}
                      onClick={() => setTypeFilter(t.value)}
                      className={cn(
                        'px-2 py-0.5 rounded-full text-[11px] font-medium transition-colors',
                        typeFilter === t.value
                          ? 'bg-slate-900 text-white'
                          : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                      )}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-2">
                {loading ? (
                  <div className="space-y-1.5 p-1">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <Skeleton key={i} className="h-9 w-full rounded-lg" />
                    ))}
                  </div>
                ) : error ? (
                  <p className="text-xs text-red-500 p-3">{error}</p>
                ) : filtered.length === 0 ? (
                  <p className="text-xs text-slate-400 p-3 text-center">
                    {files && files.length > 0
                      ? 'No files match your filters.'
                      : 'This artifact is empty.'}
                  </p>
                ) : (
                  <ul className="space-y-0.5">
                    {filtered.map((f) => {
                      const base = f.name.split('/').pop() ?? f.name;
                      const active = selected?.name === f.name;
                      return (
                        <li key={f.name}>
                          <button
                            onClick={() => setSelected(f)}
                            className={cn(
                              'w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left transition-colors min-w-0',
                              active
                                ? 'bg-white border border-slate-200 shadow-sm'
                                : 'hover:bg-white'
                            )}
                          >
                            <span className="shrink-0">{fileIcon(f)}</span>
                            <span className="flex-1 min-w-0">
                              <span className="block text-xs font-medium text-slate-800 truncate">
                                {base}
                              </span>
                              <span className="block text-[10px] text-slate-400 tabular-nums">
                                {formatSize(f.size)}
                              </span>
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              {files && files.length > 0 && (
                <div className="px-3 py-2 border-t border-slate-100 shrink-0 bg-white">
                  <p className="text-[10px] text-slate-400 tabular-nums">
                    {filtered.length} of {files.length} files
                  </p>
                </div>
              )}
            </aside>

            {/* Right pane — preview */}
            <section className="flex-1 min-w-0 bg-white flex flex-col min-h-0">
              <FilePreview artifactId={artifact.id} file={selected} />
            </section>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
