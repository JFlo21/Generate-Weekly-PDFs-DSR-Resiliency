import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, LogOut, Wifi, WifiOff, Search, Beaker, BookOpen } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../lib/utils';

const POLL_SECONDS = 120;
const CIRCUMFERENCE = 2 * Math.PI * 16; // r=16

// Docusaurus docs URL. Same env var as the sidebar link so they stay in sync.
const DOCS_URL = (import.meta.env.VITE_DOCS_URL ?? '').trim();

interface NavbarProps {
  countdown: number;
  isConnected: boolean;
  isSampleData?: boolean;
  onRefresh: () => void;
  onOpenCommandPalette?: () => void;
}

export function Navbar({
  countdown,
  isConnected,
  isSampleData = false,
  onRefresh,
  onOpenCommandPalette,
}: NavbarProps) {
  const [isMac, setIsMac] = useState(false);
  useEffect(() => {
    if (typeof navigator !== 'undefined') {
      setIsMac(/Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent));
    }
  }, []);
  const { profile, logout } = useAuth();
  const progress = countdown / POLL_SECONDS;
  const dashOffset = CIRCUMFERENCE * (1 - progress);

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-6 bg-white border-b border-slate-200 shadow-sm">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-brand-red flex items-center justify-center">
          <span className="text-white text-xs font-bold">L</span>
        </div>
        <span className="font-semibold text-slate-900 text-sm">
          Linetec Portal
        </span>
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
              {isMac ? '⌘K' : 'Ctrl K'}
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

        {/* Connection status — three distinct visual states:
            sample data (amber), live (emerald), offline (slate). */}
        <div
          className={cn(
            'flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border',
            isSampleData
              ? 'text-amber-700 bg-amber-50 border-amber-200'
              : isConnected
              ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
              : 'text-slate-500 bg-slate-50 border-slate-200'
          )}
          title={
            isSampleData
              ? 'Sample data — backend unreachable'
              : isConnected
              ? 'Live — backend connected'
              : 'Offline — no backend connection'
          }
        >
          {isSampleData ? (
            <Beaker size={12} />
          ) : isConnected ? (
            <Wifi size={12} />
          ) : (
            <WifiOff size={12} />
          )}
          <span className="hidden sm:inline">
            {isSampleData ? 'Sample data' : isConnected ? 'Live' : 'Offline'}
          </span>
        </div>

        {/* Refresh countdown ring */}
        <button
          onClick={onRefresh}
          className="relative flex items-center justify-center w-9 h-9 rounded-full hover:bg-slate-100 transition-colors"
          aria-label="Refresh now"
          title={`Next refresh in ${countdown}s`}
        >
          <svg
            width="36"
            height="36"
            viewBox="0 0 36 36"
            className="absolute inset-0 -rotate-90"
            aria-hidden="true"
          >
            <circle
              cx="18"
              cy="18"
              r="16"
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="2"
            />
            <motion.circle
              cx="18"
              cy="18"
              r="16"
              fill="none"
              stroke="#C41230"
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={dashOffset}
              transition={{ duration: 1, ease: 'linear' }}
            />
          </svg>
          <RefreshCw size={14} className="text-slate-500 relative" />
        </button>

        {/* User info */}
        {profile && (
          <div className="hidden sm:flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-brand-red text-white flex items-center justify-center text-xs font-semibold uppercase">
              {(profile.display_name ?? profile.email)[0]}
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-medium text-slate-800 leading-none">
                {profile.display_name ?? profile.email.split('@')[0]}
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
