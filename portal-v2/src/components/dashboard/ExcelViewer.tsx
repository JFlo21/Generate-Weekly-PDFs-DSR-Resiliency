import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X, Download } from 'lucide-react';
import type { Artifact, ExcelSheet } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';

interface ExcelViewerProps {
  artifact: Artifact | null;
  sheets: ExcelSheet[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export function ExcelViewer({
  artifact,
  sheets,
  loading,
  error,
  onClose,
}: ExcelViewerProps) {
  const [activeSheet, setActiveSheet] = useState(0);

  function exportCSV() {
    const sheet = sheets[activeSheet];
    if (!sheet) return;
    const csv = sheet.rows
      .map((row) =>
        row
          .map((cell) => {
            const val = String(cell ?? '');
            // Escape double-quotes per RFC 4180
            const escaped = val.replace(/"/g, '""');
            return `"${escaped}"`;
          })
          .join(',')
      )
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sheet.name}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <AnimatePresence>
      {artifact && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            initial={{ scale: 0.96, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 24 }}
            className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 shrink-0">
              <h2 className="text-sm font-semibold text-slate-800 truncate">
                {artifact.name}
              </h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={exportCSV}
                  disabled={sheets.length === 0}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-40"
                >
                  <Download size={12} />
                  Export CSV
                </button>
                <button
                  onClick={onClose}
                  className="text-slate-400 hover:text-slate-700 transition-colors"
                  aria-label="Close"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Sheet tabs */}
            {sheets.length > 1 && (
              <div className="flex gap-1 px-4 pt-2 border-b border-slate-100 shrink-0 overflow-x-auto">
                {sheets.map((s, i) => (
                  <button
                    key={s.name}
                    onClick={() => setActiveSheet(i)}
                    className={`px-3 py-1.5 rounded-t-lg text-xs font-medium whitespace-nowrap transition-colors ${
                      activeSheet === i
                        ? 'bg-brand-red text-white'
                        : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
                    }`}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            )}

            {/* Table */}
            <div className="flex-1 overflow-auto p-4">
              {loading ? (
                <div className="space-y-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full" />
                  ))}
                </div>
              ) : error ? (
                <p className="text-sm text-red-500 text-center py-8">{error}</p>
              ) : sheets.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-8">
                  No data available.
                </p>
              ) : (
                <table className="w-full text-xs border-collapse">
                  <tbody>
                    {sheets[activeSheet]?.rows.map((row, ri) => (
                      <tr
                        key={ri}
                        className={ri === 0 ? 'bg-slate-100 font-semibold' : 'hover:bg-slate-50'}
                      >
                        {row.map((cell, ci) => (
                          <td
                            key={ci}
                            className="border border-slate-200 px-3 py-1.5 text-slate-700 whitespace-nowrap"
                          >
                            {cell ?? ''}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
