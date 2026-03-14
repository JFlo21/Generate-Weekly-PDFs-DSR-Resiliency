import { motion } from 'framer-motion';
import { RefreshCw, LogOut, Wifi, WifiOff } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../lib/utils';

const POLL_SECONDS = 120;
const CIRCUMFERENCE = 2 * Math.PI * 16; // r=16

interface NavbarProps {
  countdown: number;
  isConnected: boolean;
  onRefresh: () => void;
}

export function Navbar({ countdown, isConnected, onRefresh }: NavbarProps) {
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
        {/* Connection status */}
        <div
          className={cn(
            'flex items-center gap-1.5 text-xs font-medium',
            isConnected ? 'text-emerald-600' : 'text-slate-400'
          )}
          title={isConnected ? 'Live' : 'Offline'}
        >
          {isConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
          <span className="hidden sm:inline">
            {isConnected ? 'Live' : 'Offline'}
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
          onClick={() => logout().catch(console.error)}
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
