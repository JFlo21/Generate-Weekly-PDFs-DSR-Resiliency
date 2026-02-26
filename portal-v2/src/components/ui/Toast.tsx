import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';
import type { Toast as ToastType } from '../../lib/types';
import { cn } from '../../lib/utils';

interface ToastProps {
  toasts: ToastType[];
  onRemove: (id: string) => void;
}

const icons = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
} as const;

const borderColors = {
  success: 'border-l-emerald-500',
  error: 'border-l-red-500',
  info: 'border-l-blue-500',
} as const;

const iconColors = {
  success: 'text-emerald-500',
  error: 'text-red-500',
  info: 'text-blue-500',
} as const;

export function ToastContainer({ toasts, onRemove }: ToastProps) {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
      <AnimatePresence initial={false}>
        {toasts.map((toast) => {
          const Icon = icons[toast.type];
          return (
            <motion.div
              key={toast.id}
              layout
              initial={{ x: 100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 100, opacity: 0, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 300, damping: 25 }}
              drag="x"
              dragConstraints={{ left: 0, right: 200 }}
              onDragEnd={(_, info) => {
                if (info.offset.x > 80) onRemove(toast.id);
              }}
              className={cn(
                'pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl',
                'bg-white shadow-xl border border-slate-100 border-l-4 min-w-[280px] max-w-[360px] cursor-grab',
                borderColors[toast.type]
              )}
            >
              <Icon
                size={18}
                className={cn('mt-0.5 shrink-0', iconColors[toast.type])}
              />
              <p className="text-sm text-slate-700 flex-1 leading-snug">
                {toast.message}
              </p>
              <button
                onClick={() => onRemove(toast.id)}
                className="shrink-0 text-slate-400 hover:text-slate-600 transition-colors"
                aria-label="Dismiss"
              >
                <X size={14} />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
