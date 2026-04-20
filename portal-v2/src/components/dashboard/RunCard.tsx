import { motion } from 'framer-motion';
import { GitBranch, Clock } from 'lucide-react';
import type { WorkflowRun } from '../../lib/types';
import { timeAgo, cn } from '../../lib/utils';
import { Badge } from '../ui/Badge';

interface RunCardProps {
  run: WorkflowRun;
  index: number;
  isSelected: boolean;
  onClick: () => void;
}

function conclusionVariant(
  conclusion: string | null
): 'success' | 'error' | 'warning' | 'default' {
  if (conclusion === 'success') return 'success';
  if (conclusion === 'failure') return 'error';
  if (conclusion === 'cancelled') return 'warning';
  return 'default';
}

function accentColor(conclusion: string | null): string {
  if (conclusion === 'success') return 'bg-emerald-500';
  if (conclusion === 'failure') return 'bg-red-500';
  if (conclusion === 'cancelled') return 'bg-amber-500';
  return 'bg-slate-300';
}

export function RunCard({ run, index, isSelected, onClick }: RunCardProps) {
  return (
    <motion.div
      layout
      // Set `boxShadow` on both `initial` and `animate` so Framer Motion has
      // a valid, parseable starting value when `whileHover` interpolates to
      // a new boxShadow. Without this Framer reads Tailwind's `shadow-sm`
      // CSS variable chain and produces `NaN NaNpx NaNpx rgba(NaN, ...)`
      // which spams the console on every hover.
      initial={{ opacity: 0, x: -16, boxShadow: '0 1px 2px 0 rgba(0,0,0,0.05)' }}
      animate={{ opacity: 1, x: 0, boxShadow: '0 1px 2px 0 rgba(0,0,0,0.05)' }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ delay: index * 0.05, type: 'spring', stiffness: 200, damping: 22 }}
      whileHover={{ y: -2, boxShadow: '0 6px 24px rgba(0,0,0,0.07)' }}
      whileTap={{ scale: 0.99 }}
      onClick={onClick}
      className={cn(
        'relative flex items-start gap-4 p-4 rounded-2xl bg-white border cursor-pointer transition-colors overflow-hidden',
        // Removed `shadow-sm` Tailwind class — the shadow is now controlled
        // entirely by Framer Motion's animate prop to avoid conflicts.
        isSelected
          ? 'border-brand-red ring-1 ring-brand-red/30'
          : 'border-slate-100 hover:border-slate-200'
      )}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      aria-pressed={isSelected}
    >
      {/* Left accent bar */}
      <motion.div
        initial={{ scaleY: 0 }}
        animate={{ scaleY: 1 }}
        transition={{ delay: index * 0.05 + 0.1, type: 'spring' }}
        className={cn('absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl origin-top', accentColor(run.conclusion))}
      />

      <div className="flex-1 min-w-0 pl-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold text-slate-800 truncate">
            {run.name}
          </span>
          {run.isNew && (
            <motion.span
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
              className="shrink-0 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-brand-red text-white"
            >
              NEW
            </motion.span>
          )}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <GitBranch size={11} />
            <span className="truncate max-w-[120px]">{run.head_branch}</span>
          </div>
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <Clock size={11} />
            <span>{timeAgo(run.created_at)}</span>
          </div>
          <Badge variant={conclusionVariant(run.conclusion)} className="capitalize">
            {run.conclusion ?? run.status}
          </Badge>
        </div>
      </div>

      <span className="shrink-0 text-xs text-slate-400 mt-0.5">
        #{run.run_number}
      </span>
    </motion.div>
  );
}
