import React from 'react';
import { Download, Loader2 } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { getVariantLabel } from '../../lib/variantLabels';
import { formatSize, formatDate } from '../../lib/utils';
import type { BillingArtifact } from '../../lib/types';

interface ArtifactCardProps {
  row: BillingArtifact;
  onDownload: (rowId: string, storagePath: string, filename: string) => void;
  isDownloading: boolean;
}

/**
 * Mobile stacked card view for a single billing artifact.
 * Rendered ONLY at <640px (sm:hidden on parent list wrapper in ArtifactTable).
 * Module-level React.memo — MUST stay at module level (Pitfall 3).
 * All meta text uses text-slate-500 (WCAG AA — never text-slate-400).
 * Download button floors at min-h-[44px] per WCAG 2.5.5 touch-target.
 */
export const ArtifactCard = React.memo(function ArtifactCard({
  row,
  onDownload,
  isDownloading,
}: ArtifactCardProps) {
  // Format week_ending_fmt (MMDDYY "052625") → "05/26/25" for readability.
  // Never use raw ISO week_ending in display cells (Pitfall 8).
  const weekDisplay =
    row.week_ending_fmt.length === 6
      ? `${row.week_ending_fmt.slice(0, 2)}/${row.week_ending_fmt.slice(2, 4)}/${row.week_ending_fmt.slice(4, 6)}`
      : row.week_ending_fmt;

  return (
    <div
      role="listitem"
      className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 space-y-2 mb-2"
    >
      {/* Row 1: WR # + week-ending — always visible (UI-SPEC §Column Visibility) */}
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 truncate">
          {row.work_request}
        </span>
        <span className="text-xs text-slate-500 shrink-0">
          {weekDisplay}
        </span>
      </div>

      {/* Row 2: Variant badge + file size */}
      <div className="flex items-center justify-between gap-2">
        <Badge>{getVariantLabel(row.variant)}</Badge>
        <span className="text-xs text-slate-500">{formatSize(row.size_bytes)}</span>
      </div>

      {/* Row 3: Created date + Download button */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-slate-500">{formatDate(row.created_at)}</span>
        <button
          onClick={() => onDownload(row.id, row.storage_path, row.filename)}
          disabled={isDownloading}
          aria-label={isDownloading ? `Downloading ${row.filename}` : `Download ${row.filename}`}
          className="inline-flex items-center gap-1.5 min-h-[44px] py-3 px-4 rounded-lg
                     bg-brand-red text-white text-sm font-medium
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50"
        >
          {isDownloading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Download size={14} />
          )}
        </button>
      </div>
    </div>
  );
});
