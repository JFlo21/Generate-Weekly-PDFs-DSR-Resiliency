/**
 * ArtifactEmptyState — three presentational state components for the artifact table.
 * D-07: exact copy for empty-DB, no-results, and error states.
 */

/** Empty database state — no artifacts exist yet. No action available. */
export function EmptyDBState() {
  return (
    <p className="text-slate-400 text-sm text-center py-12">
      No artifacts yet — they&apos;ll appear here after the next billing run.
    </p>
  );
}

interface NoResultsStateProps {
  onClear: () => void;
}

/** Zero matches while search/filter active — offers a clear-filters action. */
export function NoResultsState({ onClear }: NoResultsStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-12">
      <p className="text-slate-400 text-sm">
        No results match your search/filters.
      </p>
      <button
        onClick={onClear}
        className="text-xs text-brand-red hover:underline"
      >
        Clear filters
      </button>
    </div>
  );
}

interface ErrorStateProps {
  onRetry: () => void;
}

/** Error loading artifacts — mirrors UsersPage.tsx lines 110–119 banner styling. */
export function ErrorState({ onRetry }: ErrorStateProps) {
  return (
    <div className="p-6">
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 flex items-center justify-between">
        <span>Couldn&apos;t load artifacts.</span>
        <button
          onClick={onRetry}
          className="text-xs text-red-600 hover:underline ml-4 shrink-0"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
