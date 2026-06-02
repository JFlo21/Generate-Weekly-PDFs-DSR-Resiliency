import { LogOut, Search, BookOpen } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { useIsMac } from '../../hooks/usePlatform';
import { commandPaletteHint } from '../../lib/platform';

// Docusaurus docs URL. Same env var as the sidebar link so they stay in sync.
const DOCS_URL = (import.meta.env.VITE_DOCS_URL ?? '').trim();

interface NavbarProps {
  onOpenCommandPalette?: () => void;
}

/**
 * Navbar — Supabase-native top bar.
 *
 * The legacy run-polling UI (the Live/Offline/Sample-data connection pill and the
 * 120s refresh countdown ring) was removed alongside `useRuns()` in DashboardLayout;
 * it reflected the now-removed Express/Railway backend, not the Supabase data path.
 */
export function Navbar({ onOpenCommandPalette }: NavbarProps) {
  const isMac = useIsMac();
  const { profile, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-6 bg-white border-b border-slate-200 shadow-sm">
      {/* Logo */}
      <div className="flex items-center">
        <img
          src="/linetec-services-logo.png"
          alt="Linetec Services"
          className="h-10 w-auto"
        />
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Command palette trigger */}
        {onOpenCommandPalette && (
          <button
            onClick={onOpenCommandPalette}
            className="hidden md:flex items-center gap-2 pl-2.5 pr-1.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-500 hover:bg-white hover:border-slate-300 transition-colors min-w-[220px]"
            title="Search runs and artifacts"
            type="button"
          >
            <Search size={13} className="shrink-0" />
            <span className="text-xs flex-1 text-left">Search runs, artifacts…</span>
            <kbd className="text-[10px] font-mono text-slate-400 border border-slate-200 rounded px-1.5 py-0.5 bg-white">
              {commandPaletteHint(isMac)}
            </kbd>
          </button>
        )}

        {/* Docs shortcut — opens the Docusaurus site in a new tab.
            Hidden when VITE_DOCS_URL is not configured. */}
        {DOCS_URL && (
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            title="Docs & Updates (opens in a new tab)"
          >
            <BookOpen size={13} />
            <span>Docs</span>
          </a>
        )}

        {/* User info */}
        {profile && (
          <div className="hidden sm:flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-brand-red text-white flex items-center justify-center text-xs font-semibold uppercase">
              {profile.email[0]}
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-medium text-slate-800 leading-none">
                {profile.email.split('@')[0]}
              </span>
              <span className="text-[10px] text-slate-500 capitalize leading-none mt-0.5">
                {profile.role}
              </span>
            </div>
          </div>
        )}

        {/* Sign out */}
        <button
          onClick={logout}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 transition-colors"
          title="Sign out"
        >
          <LogOut size={14} />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}
