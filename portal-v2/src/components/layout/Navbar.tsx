import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { RefreshCw, LogOut, Wifi, WifiOff, Search, Beaker, BookOpen } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../lib/utils';
import { LinetecLogo } from '../ui/LinetecLogo';

const POLL_SECONDS = 120;
const CIRCUMFERENCE = 2 * Math.PI * 16; // r=16

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
    <header className="sticky top-0 z-30 flex items-center justify-between gap-4 h-16 px-4 sm:px-6 bg-white border-b border-slate-200 shadow-sm">
      {/* Logo — official Linetec Services wordmark. The `shrink-0` prevents
          the logo from getting squeezed when the right cluster grows. */}
      <Link
        to="/dashboard"
        className="flex items-center shrink-0 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50"
        aria-label="Go to dashboard"
      >
        <LinetecLogo size="sm" />
      </Link>

      {/* Right side — `min-w-0` allows flex children to shrink below their
          content width, preventing the search box from pushing siblings off
          screen. Gap shrinks on smaller screens. */}
      <div className="flex items-center gap-2 lg:gap-3 min-w-0">
        {/* Command palette trigger — shrinks responsively instead of forcing
            a min-width, which was pushing the user pill off-screen on small
            laptops. On xl+ it gets a comfortable fixed width. */}
        {onOpenCommandPalette && (
          <button
            onClick={onOpenCommandPalette}
            className="hidden md:flex items-center gap-2 pl-2.5 pr-1.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-500 hover:bg-white hover:border-slate-300 transition-colors w-40 xl:w-56"
            title="Search runs and artifacts"
            type="button"
          >
            <Search size={13} className="shrink-0" />
            <span className="text-xs flex-1 text-left truncate">Search runs, artifacts…</span>
            <kbd className="hidden xl:inline-flex text-[10px] font-mono text-slate-400 border border-slate-200 rounded px-1.5 py-0.5 bg-white shrink-0">
              {isMac ? '⌘K' : 'Ctrl K'}
            </kbd>
          </button>
        )}

        {/* Docs shortcut — internal link to /dashboard/docs.
            Label hides below xl so the row doesn't wrap. */}
        <Link
          to="/dashboard/docs"
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors shrink-0"
          title="Docs & Updates"
        >
          <BookOpen size={13} />
          <span className="hidden xl:inline">Docs</span>
        </Link>

        {/* Connection status — three distinct visual states:
            sample data (amber), live (emerald), offline (slate).
            Label hides below lg to save horizontal space on tablets. */}
        <div
          className={cn(
            'flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border shrink-0',
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
          <span className="hidden lg:inline">
            {isSampleData ? 'Sample data' : isConnected ? 'Live' : 'Offline'}
          </span>
        </div>

        {/* Refresh countdown ring */}
        <button
          onClick={onRefresh}
          className="relative flex items-center justify-center w-9 h-9 rounded-full hover:bg-slate-100 transition-colors shrink-0"
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

        {/* User info — avatar always visible, text label hides below lg */}
        {profile && (
          <div className="flex items-center gap-2 shrink-0 min-w-0">
            <div className="w-7 h-7 rounded-full bg-brand-red text-white flex items-center justify-center text-xs font-semibold uppercase shrink-0">
              {(profile.display_name ?? profile.email)[0]}
            </div>
            <div className="hidden lg:flex flex-col min-w-0">
              <span className="text-xs font-medium text-slate-800 leading-none truncate">
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
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 transition-colors shrink-0 px-1.5 py-1 rounded hover:bg-slate-100"
          title="Sign out"
        >
          <LogOut size={14} />
          <span className="hidden lg:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}
