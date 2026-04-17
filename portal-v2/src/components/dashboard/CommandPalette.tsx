import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Search, Loader2, Package, PlayCircle, FileText, CornerDownLeft } from 'lucide-react';
import { api } from '../../lib/api';
import type { SearchHit } from '../../lib/types';
import { cn, formatSize } from '../../lib/utils';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSelect: (hit: SearchHit) => void;
}

const SCOPES: Array<{ value: 'all' | 'runs' | 'artifacts' | 'files'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'runs', label: 'Runs' },
  { value: 'artifacts', label: 'Artifacts' },
  { value: 'files', label: 'Files' },
];

function useDebouncedValue<T>(value: T, delay = 150): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function HitIcon({ kind }: { kind: SearchHit['kind'] }) {
  if (kind === 'run')
    return (
      <div className="w-7 h-7 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center shrink-0">
        <PlayCircle size={14} />
      </div>
    );
  if (kind === 'artifact')
    return (
      <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
        <Package size={14} />
      </div>
    );
  return (
    <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center shrink-0">
      <FileText size={14} />
    </div>
  );
}

export function CommandPalette({ open, onClose, onSelect }: CommandPaletteProps) {
  const [q, setQ] = useState('');
  const [scope, setScope] = useState<'all' | 'runs' | 'artifacts' | 'files'>('all');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const debounced = useDebouncedValue(q, 150);

  useEffect(() => {
    if (!open) return;
    setActive(0);
    setHits([]);
    setQ('');
    setError(null);
    const id = window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => window.clearTimeout(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (!debounced.trim()) {
      setHits([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .search(debounced, scope, 20)
      .then((r) => {
        if (cancelled) return;
        setHits(r.hits);
        setActive(0);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : 'Search failed'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open, debounced, scope]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const hit = hits[active];
      if (hit) {
        onSelect(hit);
        onClose();
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4"
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
            className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden"
          >
            {/* Input */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
              {loading ? (
                <Loader2 size={16} className="text-slate-400 animate-spin shrink-0" />
              ) : (
                <Search size={16} className="text-slate-400 shrink-0" />
              )}
              <input
                ref={inputRef}
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search runs, artifacts, files…"
                className="flex-1 text-sm bg-transparent outline-none text-slate-900 placeholder-slate-400"
              />
              <kbd className="text-[10px] font-mono text-slate-400 border border-slate-200 rounded px-1.5 py-0.5 shrink-0">
                Esc
              </kbd>
            </div>

            {/* Scope tabs */}
            <div className="flex items-center gap-1 px-3 py-2 border-b border-slate-100 bg-slate-50">
              {SCOPES.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setScope(s.value)}
                  className={cn(
                    'px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors',
                    scope === s.value
                      ? 'bg-white text-slate-900 shadow-sm border border-slate-200'
                      : 'text-slate-500 hover:text-slate-700'
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>

            {/* Results */}
            <div className="max-h-[50vh] overflow-y-auto">
              {error && <p className="px-4 py-6 text-sm text-red-500 text-center">{error}</p>}
              {!error && hits.length === 0 && !loading && (
                <p className="px-4 py-10 text-xs text-slate-400 text-center">
                  {debounced.trim()
                    ? 'No matches.'
                    : 'Type to search across recent runs, artifacts, and files.'}
                </p>
              )}
              {!error && hits.length > 0 && (
                <ul>
                  {hits.map((h, i) => (
                    <li key={`${h.kind}-${h.artifactId ?? h.runId}-${h.file ?? ''}-${i}`}>
                      <button
                        onMouseEnter={() => setActive(i)}
                        onClick={() => {
                          onSelect(h);
                          onClose();
                        }}
                        className={cn(
                          'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors',
                          i === active ? 'bg-slate-50' : 'hover:bg-slate-50'
                        )}
                      >
                        <HitIcon kind={h.kind} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">
                            {h.title}
                          </p>
                          <p className="text-[11px] text-slate-500 truncate">{h.subtitle}</p>
                        </div>
                        <span className="text-[10px] text-slate-400 tabular-nums shrink-0">
                          {h.kind === 'artifact' && h.meta?.sizeInBytes
                            ? formatSize(Number(h.meta.sizeInBytes))
                            : h.kind.toUpperCase()}
                        </span>
                        {i === active && (
                          <CornerDownLeft size={12} className="text-slate-400 shrink-0" />
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-t border-slate-100 text-[10px] text-slate-400">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <kbd className="font-mono border border-slate-200 rounded px-1 py-0.5 bg-white">
                    ↑↓
                  </kbd>
                  navigate
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="font-mono border border-slate-200 rounded px-1 py-0.5 bg-white">
                    ↵
                  </kbd>
                  open
                </span>
              </div>
              <span>In-memory index on Render</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
