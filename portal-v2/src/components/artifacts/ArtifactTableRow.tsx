import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Download, Loader2 } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { getVariantLabel } from '../../lib/variantLabels';
import { formatSize, formatDate } from '../../lib/utils';
import type { BillingArtifact } from '../../lib/types';

interface ArtifactTableRowProps {
  row: BillingArtifact;
  onDownload: (rowId: string, storagePath: string, filename: string) => void;
  isDownloading: boolean;
  staggerDelay: number;  // 0 after initial load; index * 0.02 capped at 0.2 on initial load
}

/**
 * Module-level React.memo row for the virtualizer.
 * MUST stay at module level — inline definitions break memo (Pitfall 3).
 * Renders 6 cells in a flex grid matching the table header column order.
 */
export const ArtifactTableRow = React.memo(function ArtifactTableRow({
  row,
  onDownload,
  isDownloading,
  staggerDelay,
}: ArtifactTableRowProps) {
  // Respect prefers-reduced-motion — zero out animation when user opts out (UI-SPEC §Reduced Motion)
  const prefersReduced = useReducedMotion();
  // Format week_ending_fmt (MMDDYY "052625") → "05/26/25" for readability.
  // Never use raw ISO week_ending in display cells (Pitfall 8).
  const weekDisplay =
    row.week_ending_fmt.length === 6
      ? `${row.week_ending_fmt.slice(0, 2)}/${row.week_ending_fmt.slice(2, 4)}/${row.week_ending_fmt.slice(4, 6)}`
      : row.week_ending_fmt;

  return (
    // Opacity-only entrance — NO y/x animation (Pitfall 2 / A3: avoids transform
    // conflict with the virtualizer's outer translateY positioning wrapper).
    <motion.div
      role="row"
      className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_auto] items-center border-b border-slate-50 hover:bg-slate-50/50 transition-colors w-full h-14"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={
        prefersReduced
          ? { duration: 0 }
          : { duration: 0.15, ease: 'easeOut', delay: staggerDelay }
      }
    >
      {/* 1. Work Request # */}
      <div role="cell" className="px-5 py-3 text-sm font-medium text-slate-800 truncate">
        {row.work_request}
      </div>

      {/* 2. Week Ending — MMDDYY display (never raw ISO) */}
      <div role="cell" className="px-5 py-3 text-sm text-slate-700 truncate">
        {weekDisplay}
      </div>

      {/* 3. Variant */}
      <div role="cell" className="px-5 py-3">
        <Badge>{getVariantLabel(row.variant)}</Badge>
      </div>

      {/* 4. File Size */}
      <div role="cell" className="px-5 py-3 text-sm text-slate-600 truncate">
        {formatSize(row.size_bytes)}
      </div>

      {/* 5. Created */}
      <div role="cell" className="px-5 py-3 text-xs text-slate-500 truncate">
        {formatDate(row.created_at)}
      </div>

      {/* 6. Download */}
      <div role="cell" className="px-5 py-3">
        <button
          onClick={() => onDownload(row.id, row.storage_path, row.filename)}
          disabled={isDownloading}
          aria-label={isDownloading ? `Downloading ${row.filename}` : `Download ${row.filename}`}
          aria-disabled={isDownloading}
          className="inline-flex items-center gap-1.5 text-xs text-brand-red hover:text-red-700
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors rounded
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50"
        >
          {isDownloading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Download size={14} />
          )}
          <span>{isDownloading ? 'Downloading…' : 'Download'}</span>
        </button>
      </div>
    </motion.div>
  );
});
