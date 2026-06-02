import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * NewArtifactPill — DATA-06 / UI-02 / UI-03
 *
 * Sticky pill displayed above the artifact table when new Realtime INSERT
 * events have arrived. Persists until the user acts (D-03 — no auto-insert).
 *
 * - onLoad  : clearPending — resets count + invalidates ['artifacts'] query
 * - onDismiss : dismissPending — resets count WITHOUT refetch
 *
 * Accessibility: role="status" + aria-live="polite" so screen readers
 * announce the pill when it appears. Dismiss button has an explicit
 * aria-label. AnimatePresence initial={false} prevents re-animation on
 * hot-reload if pill is already visible (Pitfall 3 scope guard).
 * useReducedMotion zeroes transition duration when OS prefers reduced motion.
 */

interface NewArtifactPillProps {
  count: number;
  onLoad: () => void;
  onDismiss: () => void;
}

export function NewArtifactPill({ count, onLoad, onDismiss }: NewArtifactPillProps) {
  const prefersReduced = useReducedMotion();
  const label = count === 1 ? 'Load 1 new artifact' : `Load ${count} new artifacts`;

  return (
    <AnimatePresence initial={false}>
      {count > 0 && (
        <motion.div
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={
            prefersReduced ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }
          }
          className={cn(
            'sticky top-0 z-10 mb-2 flex items-center gap-2 px-4 py-2',
            'backdrop-blur-sm border shadow-md rounded-full sm:inline-flex',
            'w-full sm:w-auto',
            // Mobile: full-width brand-red banner; desktop: L2 glass pill
            'bg-brand-red text-white border-transparent',
            'sm:bg-white/80 sm:text-slate-700 sm:border-slate-200'
          )}
        >
          <button
            onClick={onLoad}
            className="text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded"
          >
            {label}
          </button>
          <button
            onClick={onDismiss}
            aria-label="Dismiss new artifact notification"
            className={cn(
              'ml-2 shrink-0 transition-colors rounded',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50',
              // Mobile text color: white/80 → white on hover
              'text-white/80 hover:text-white',
              // Desktop text color override: slate-500 → slate-600 (WCAG AA — never slate-400)
              'sm:text-slate-500 sm:hover:text-slate-600'
            )}
          >
            <X size={14} />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
