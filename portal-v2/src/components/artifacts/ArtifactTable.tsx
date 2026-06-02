import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import {
  useReactTable,
  getCoreRowModel,
  type SortingState,
} from '@tanstack/react-table';
import { useArtifactsInfinite, type ArtifactsQueryParams } from '../../hooks/useArtifactsInfinite';
import { useDownloadArtifact } from '../../hooks/useDownloadArtifact';
import { useToast } from '../../hooks/useToast';
import { ToastContainer } from '../ui/Toast';
import { Skeleton } from '../ui/Skeleton';
import { ArtifactTableRow } from './ArtifactTableRow';
import { EmptyDBState, NoResultsState, ErrorState } from './ArtifactEmptyState';
import type { BillingArtifact } from '../../lib/types';
import type { ColumnDef } from '@tanstack/react-table';

// Column definitions (TABLE-01). manualSorting/manualPagination — no client-side ops.
// Interactive header clicks are wired in Plan 04; these defs land now.
const COLUMNS: ColumnDef<BillingArtifact>[] = [
  { id: 'work_request',   accessorKey: 'work_request',   header: 'Work Request #' },
  { id: 'week_ending',    accessorKey: 'week_ending_fmt', header: 'Week Ending'   },
  { id: 'variant',        accessorKey: 'variant',         header: 'Variant'       },
  { id: 'size_bytes',     accessorKey: 'size_bytes',      header: 'File Size'     },
  { id: 'created_at',     accessorKey: 'created_at',      header: 'Created'       },
  { id: 'download',       header: 'Download',             enableSorting: false    },
];

const DEFAULT_SORTING: SortingState = [{ id: 'week_ending', desc: true }];

// D-06 default: week_ending DESC; Plan 04 lifts these into interactive state.
const FIXED_PARAMS: ArtifactsQueryParams = {
  search: '',
  variants: [],
  sortColumn: 'week_ending',
  sortAscending: false,
};

export function ArtifactTable() {
  // Pitfall 7: hoist useToast here, thread addToast to useDownloadArtifact.
  const { toasts, addToast, removeToast } = useToast();
  const { download, downloading } = useDownloadArtifact(addToast);

  const params = FIXED_PARAMS;
  const q = useArtifactsInfinite(params);

  const allRows = q.data?.pages.flatMap((p) => p.rows) ?? [];

  // TanStack Table headless setup (Pattern 4 / manualSorting).
  useReactTable({
    data: allRows,
    columns: COLUMNS,
    state: { sorting: DEFAULT_SORTING },
    manualSorting: true,
    manualFiltering: true,
    manualPagination: true,
    getCoreRowModel: getCoreRowModel(),
  });

  // Virtualizer scroll container ref (Pattern 3 / Pitfall 5).
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: q.hasNextPage ? allRows.length + 1 : allRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 56,
    overscan: 5,
  });

  // Guarded infinite-scroll trigger (Pitfall 6 — no re-fire while fetching).
  const virtualItems = rowVirtualizer.getVirtualItems();
  const lastItem = virtualItems[virtualItems.length - 1];
  if (
    lastItem &&
    lastItem.index >= allRows.length - 1 &&
    q.hasNextPage &&
    !q.isFetchingNextPage
  ) {
    void q.fetchNextPage();
  }

  // Four-state render (D-07 / TABLE-05). TanStack Query v5: 'pending' not 'loading'.
  const renderBody = () => {
    if (q.status === 'pending') {
      return (
        <div className="p-6 space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      );
    }

    if (q.status === 'error') {
      return <ErrorState onRetry={() => q.refetch()} />;
    }

    if (allRows.length === 0 && !params.search && params.variants.length === 0) {
      return <EmptyDBState />;
    }

    if (allRows.length === 0) {
      // Filters active but zero matches.
      return <NoResultsState onClear={() => { /* Plan 04 wires the clear action */ }} />;
    }

    // Virtualized table (Pattern 3 — fixed-height container, Pitfall 5).
    return (
      <div
        ref={parentRef}
        style={{ height: 'calc(100vh - 280px)', overflow: 'auto' }}
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            position: 'relative',
          }}
        >
          {virtualItems.map((virtualRow) => {
            const row = allRows[virtualRow.index];
            return (
              <div
                key={virtualRow.key}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                {row ? (
                  <ArtifactTableRow
                    row={row}
                    onDownload={download}
                    isDownloading={downloading === row.id}
                  />
                ) : (
                  <Skeleton className="h-12 w-full mx-5 my-1" />
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <>
      {/* UsersPage.tsx card shell — bg-white rounded-2xl border shadow-sm */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        {/* Sticky header row (6 column labels) */}
        <div className="border-b border-slate-100">
          <div
            role="row"
            className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_auto] items-center"
          >
            {COLUMNS.map((col) => (
              <div
                key={col.id}
                role="columnheader"
                className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide"
              >
                {typeof col.header === 'string' ? col.header : col.id}
              </div>
            ))}
          </div>
        </div>

        {/* Body: 4-state render */}
        {renderBody()}
      </div>

      {/* Toast container co-located here (Pitfall 7) */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </>
  );
}
