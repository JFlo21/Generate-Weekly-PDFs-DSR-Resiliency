import { Component, type ErrorInfo, type ReactNode } from 'react';
import * as Sentry from '@sentry/react';
import { AlertTriangle, RefreshCw, RotateCcw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
    Sentry.captureException(error, {
      contexts: { react: { componentStack: info.componentStack ?? '' } },
    });
  }

  // Resets the boundary so the app can retry rendering without a full reload.
  // Useful for transient errors (stale HMR modules, network blips) where a
  // full reload would lose any unsaved state.
  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      const message = this.state.error?.message ?? 'An unexpected error occurred.';

      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
          <div className="w-full max-w-md rounded-2xl bg-white border border-slate-200 shadow-xl shadow-slate-900/5 overflow-hidden">
            {/* Accent bar matching the login page's brand-red palette */}
            <div className="h-1 bg-gradient-to-r from-brand-red to-red-700" />

            <div className="p-7 flex flex-col items-center text-center">
              <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-red-50 ring-4 ring-red-50/50 mb-5">
                <AlertTriangle size={22} className="text-brand-red" />
              </div>

              <h2 className="text-lg font-semibold tracking-tight text-slate-900 mb-1.5">
                Something went wrong
              </h2>
              <p className="text-sm text-slate-500 mb-5 leading-relaxed max-w-sm">
                The dashboard ran into an unexpected error. You can try again without
                losing your session, or reload the page if the problem persists.
              </p>

              {/* Raw error message for debuggability — muted so it doesn't dominate */}
              <div className="w-full mb-5 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[11px] text-slate-600 break-words text-left">
                {message}
              </div>

              <div className="flex flex-col sm:flex-row gap-2 w-full">
                <button
                  onClick={this.handleReset}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-brand-red px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700 transition-colors shadow-sm"
                >
                  <RotateCcw size={14} />
                  Try again
                </button>
                <button
                  onClick={() => window.location.reload()}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-white border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors"
                >
                  <RefreshCw size={14} />
                  Reload page
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
