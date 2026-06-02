/**
 * ArtifactEmptyState — three presentational state components for the artifact table.
 * D-07: exact copy per UI-SPEC §Copywriting Contract.
 * All text uses text-slate-500 minimum (WCAG AA — slate-400 fails at 2.8:1).
 */

/** Empty database state — no artifacts exist yet. No action available. */
export function EmptyDBState() {
  return (
    <div className="flex flex-col items-center gap-2 py-12">
      <p className="text-sm font-semibold text-slate-700">No artifacts yet</p>
      <p className="text-sm text-slate-500 text-center max-w-sm">
        Billing artifacts will appear here after the next CI run completes.
      </p>
    </div>
  );
}

interface NoResultsStateProps {
  onClear: () => void;
}

/** Zero matches while search/filter active — offers a clear-filters action. */
export function NoResultsState({ onClear }: NoResultsStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-12">
      <p className="text-sm font-semibold text-slate-700">No matches found</p>
      <p className="text-sm text-slate-500">
        Try adjusting your search or clearing the filters.
      </p>
      <button
        onClick={onClear}
        className="text-xs text-brand-red hover:text-red-700 underline transition-colors
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded"
      >
        Clear filters
      </button>
    </div>
  );
}

interface ErrorStateProps {
  onRetry: () => void;
}

/** Error loading artifacts — mirrors UsersPage.tsx banner styling. */
export function ErrorState({ onRetry }: ErrorStateProps) {
  return (
    <div className="p-6">
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 flex items-center justify-between">
        <span>Could not load artifacts. Check your connection and try again.</span>
        <button
          onClick={onRetry}
          className="text-xs text-red-600 hover:text-red-800 underline ml-4 shrink-0 transition-colors
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50 rounded"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
