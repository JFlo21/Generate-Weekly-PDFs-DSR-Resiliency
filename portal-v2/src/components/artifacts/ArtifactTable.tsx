import { useEffect, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import {
  useReactTable,
  getCoreRowModel,
  type SortingState,
  type ColumnDef,
} from '@tanstack/react-table';
import { useQuery } from '@tanstack/react-query';
import { ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import { useArtifactsInfinite, type ArtifactsQueryParams } from '../../hooks/useArtifactsInfinite';
import { useDownloadArtifact } from '../../hooks/useDownloadArtifact';
import { useDebounce } from '../../hooks/useDebounce';
import { useToastContext } from '../../contexts/ToastContext';
import { useRealtimeArtifacts } from '../../hooks/useRealtimeArtifacts';
import { Skeleton } from '../ui/Skeleton';
import { ArtifactTableRow } from './ArtifactTableRow';
import { ArtifactCard } from './ArtifactCard';
import { NewArtifactPill } from './NewArtifactPill';
import { EmptyDBState, NoResultsState, ErrorState } from './ArtifactEmptyState';
import { ArtifactSearchBar } from './ArtifactSearchBar';
import { VariantFilterBar } from './VariantFilterBar';
import { supabase } from '../../lib/supabase';
import type { BillingArtifact } from '../../lib/types';

// Column definitions (TABLE-01). manualSorting/manualPagination — no client-side ops.
const COLUMNS: ColumnDef<BillingArtifact>[] = [
  { id: 'work_request',   accessorKey: 'work_request',   header: 'Work Request #' },
  { id: 'week_ending',    accessorKey: 'week_ending_fmt', header: 'Week Ending'   },
  { id: 'variant',        accessorKey: 'variant',         header: 'Variant',        enableSorting: false },
  { id: 'size_bytes',     accessorKey: 'size_bytes',      header: 'File Size'     },
  { id: 'created_at',     accessorKey: 'created_at',      header: 'Created'       },
  { id: 'download',       header: 'Download',             enableSorting: false    },
];

// Sortable column IDs (subset of COLUMNS — T-05-12: typed union prevents injection)
const SORTABLE_IDS = new Set<ArtifactsQueryParams['sortColumn']>([
  'work_request', 'week_ending', 'size_bytes', 'created_at',
]);

export function ArtifactTable() {
  // C-01: addToast sourced from global ToastContext (single stack).
  const { addToast } = useToastContext();
  const { download, downloading } = useDownloadArtifact(addToast);

  // DATA-06: count-only Realtime INSERT notification (D-03/D-04)
  const { pendingCount, clearPending, dismissPending } = useRealtimeArtifacts();

  // CR-02: track whether a toast has already fired for the current pending batch.
  // A burst of INSERT events must produce exactly ONE toast, not N.
  // The flag is reset to false when pendingCount returns to 0 (user loaded or
  // dismissed), so the next batch can fire a fresh toast.
  const toastFiredRef = useRef(false);

  // Toast on new-artifact arrival (D-03). Hook is pure data; toast fires here.
  useEffect(() => {
    if (pendingCount > 0 && !toastFiredRef.current) {
      toastFiredRef.current = true;
      addToast('info', 'New artifacts are available — click to load.');
    }
    if (pendingCount === 0) {
      // Reset so the next batch can fire a fresh toast.
      toastFiredRef.current = false;
    }
    // addToast is a stable context ref — depend only on pendingCount to avoid re-firing
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingCount]);

  // --- Search / filter / sort state (lifted from FIXED_PARAMS in Plan 03) ---
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebounce(searchInput, 250); // SEARCH-01 / D-09

  const [variants, setVariants] = useState<string[]>([]);

  // D-06 default: week_ending DESC
  const [sorting, setSorting] = useState<SortingState>([{ id: 'week_ending', desc: true }]);

  // Derive ArtifactsQueryParams from state (SEARCH-03 / SEARCH-04)
  const sort = sorting[0] ?? { id: 'week_ending', desc: true };
  // WR-02: validate before casting so non-sortable column ids (e.g. 'download',
  // 'variant') cannot reach the query layer. SORTABLE_IDS is the whitelist.
  const rawSortId = sort.id;
  const validatedSortColumn: ArtifactsQueryParams['sortColumn'] = SORTABLE_IDS.has(
    rawSortId as ArtifactsQueryParams['sortColumn']
  )
    ? (rawSortId as ArtifactsQueryParams['sortColumn'])
    : 'week_ending';
  const params: ArtifactsQueryParams = {
    search: debouncedSearch,
    variants,
    sortColumn: validatedSortColumn,
    sortAscending: !sort.desc,
  };

  const q = useArtifactsInfinite(params);
  const allRows = q.data?.pages.flatMap((p) => p.rows) ?? [];

  // UI-02: initial-load gate — stagger animation fires once on first data arrival;
  // scroll-loaded rows get delay=0 so they never re-animate (RESEARCH.md Pattern 3).
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  useEffect(() => {
    if (q.status === 'success' && allRows.length > 0 && !initialLoadComplete) {
      setInitialLoadComplete(true);
    }
  }, [q.status, allRows.length, initialLoadComplete]);

  // Dynamic variant options: dedicated lightweight query for the FULL dataset (SEARCH-04 / D-10)
  // so a narrow filter doesn't hide unselected variants in the options list.
  const { data: variantOptionsData } = useQuery({
    queryKey: ['artifact-variants'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('artifacts')
        .select('variant')
        .limit(2000);           // C-02: cap unbounded query
      if (error) throw error;
      return Array.from(new Set((data ?? []).map((r: { variant: string }) => r.variant)));
    },
    staleTime: 10 * 60 * 1000, // C-02: 10-min staleTime (variants change rarely)
  });
  const variantOptions = variantOptionsData ?? [];

  // TanStack Table headless setup (Pattern 4 / manualSorting). SEARCH-03: onSortingChange wired.
  const table = useReactTable({
    data: allRows,
    columns: COLUMNS,
    state: { sorting },
    onSortingChange: setSorting,
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

  // Virtual items drive both the effect below and the render pass.
  const virtualItems = rowVirtualizer.getVirtualItems();
  const lastItemIndex = virtualItems[virtualItems.length - 1]?.index;

  // Guarded infinite-scroll trigger (Pitfall 6 — no re-fire while fetching).
  // CR-01: run as an effect, never during render. A bare `fetchNextPage()` in
  // the component body is a render-phase side effect — React 18/StrictMode
  // fires it twice and warns about updating a component while rendering.
  useEffect(() => {
    if (
      lastItemIndex !== undefined &&
      lastItemIndex >= allRows.length - 1 &&
      q.hasNextPage &&
      !q.isFetchingNextPage
    ) {
      void q.fetchNextPage();
    }
  }, [lastItemIndex, allRows.length, q.hasNextPage, q.isFetchingNextPage, q.fetchNextPage]);

  // Clear all active filters (search + variants; sort stays at default)
  const clearFilters = () => {
    setSearchInput('');
    setVariants([]);
  };

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

    if (allRows.length === 0 && !debouncedSearch && variants.length === 0) {
      return <EmptyDBState />;
    }

    if (allRows.length === 0) {
      // Filters active but zero matches.
      return <NoResultsState onClear={clearFilters} />;
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
            // UI-02: per-row delay on initial load only (index × 20ms, cap 200ms / 10 rows).
            // After initialLoadComplete flips to true, all subsequent scroll-loaded rows
            // get delay=0 and never animate (RESEARCH.md Pattern 3 / Pitfall 2).
            const staggerDelay = !initialLoadComplete
              ? Math.min(virtualRow.index * 0.02, 0.2)
              : 0;
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
                    staggerDelay={staggerDelay}
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
      {/* DATA-06: new-artifact pill — persists until user loads or dismisses (D-03) */}
      <NewArtifactPill
        count={pendingCount}
        onLoad={clearPending}
        onDismiss={dismissPending}
      />

      {/* Search + variant filter controls (SEARCH-01, SEARCH-02) */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="flex-1 min-w-[240px]">
          <ArtifactSearchBar value={searchInput} onChange={setSearchInput} />
        </div>
        {variantOptions.length > 0 && (
          <VariantFilterBar
            options={variantOptions}
            selected={variants}
            onChange={setVariants}
          />
        )}
      </div>

      {/* Desktop/tablet: virtualized table (sm+) — UI-01 responsive swap */}
      <div className="hidden sm:block">
        {/* UsersPage.tsx card shell — bg-white rounded-2xl border shadow-sm */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          {/* Sticky header row (6 column labels) with interactive sort (SEARCH-03) */}
          <div className="border-b border-slate-100">
            <div
              role="row"
              className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_auto] items-center"
            >
              {table.getFlatHeaders().map((header) => {
                const colId = header.column.id as ArtifactsQueryParams['sortColumn'];
                const isSortable = SORTABLE_IDS.has(colId);
                const isSorted = sort.id === colId;
                const isDesc = isSorted && sort.desc;
                const isAsc = isSorted && !sort.desc;

                return (
                  <div
                    key={header.id}
                    role="columnheader"
                    tabIndex={isSortable ? 0 : undefined}
                    aria-sort={
                      isSortable
                        ? isAsc
                          ? 'ascending'
                          : isDesc
                            ? 'descending'
                            : 'none'
                        : undefined
                    }
                    onClick={
                      isSortable
                        ? header.column.getToggleSortingHandler()
                        : undefined
                    }
                    onKeyDown={
                      isSortable
                        ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              header.column.getToggleSortingHandler()?.(e);
                            }
                          }
                        : undefined
                    }
                    className={[
                      'text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide',
                      isSortable
                        ? 'cursor-pointer select-none hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded transition-colors'
                        : '',
                    ].join(' ')}
                  >
                    <span className="inline-flex items-center gap-1">
                      {typeof header.column.columnDef.header === 'string'
                        ? header.column.columnDef.header
                        : header.id}
                      {isSortable && (
                        <span className="text-slate-400">
                          {isAsc ? (
                            <ArrowUp size={12} />
                          ) : isDesc ? (
                            <ArrowDown size={12} />
                          ) : (
                            <ArrowUpDown size={12} />
                          )}
                        </span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Body: 4-state render */}
          {renderBody()}
        </div>
      </div>

      {/* Mobile: stacked ArtifactCard list (<640px) — UI-01 responsive swap */}
      <div className="sm:hidden">
        {q.status === 'pending' && (
          <div role="list" className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-2xl" />
            ))}
          </div>
        )}

        {q.status === 'error' && <ErrorState onRetry={() => q.refetch()} />}

        {q.status === 'success' && allRows.length === 0 && !debouncedSearch && variants.length === 0 && (
          <EmptyDBState />
        )}

        {q.status === 'success' && allRows.length === 0 && (debouncedSearch || variants.length > 0) && (
          <NoResultsState onClear={clearFilters} />
        )}

        {q.status === 'success' && allRows.length > 0 && (
          <div role="list">
            {allRows.map((row) => (
              <ArtifactCard
                key={row.id}
                row={row}
                onDownload={download}
                isDownloading={downloading === row.id}
              />
            ))}
          </div>
        )}
      </div>

    </>
  );
}
