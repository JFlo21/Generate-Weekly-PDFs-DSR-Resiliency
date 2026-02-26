import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '../../lib/supabase';
import type { ActivityLog } from '../../lib/types';
import { timeAgo } from '../../lib/utils';
import { Skeleton } from '../ui/Skeleton';

export function ActivityPage() {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    supabase
      .from('activity_logs')
      .select('*, profiles(email, display_name)')
      .order('created_at', { ascending: false })
      .limit(100)
      .then(({ data, error: err }) => {
        if (err) setError(err.message);
        else setLogs((data ?? []) as ActivityLog[]);
        setLoading(false);
      });

    // Real-time subscription
    const channel = supabase
      .channel('activity_logs_changes')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'activity_logs' },
        (payload) => {
          setLogs((prev) => [payload.new as ActivityLog, ...prev]);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel).catch((err: unknown) => {
        console.error('Failed to remove channel:', err);
      });
    };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 max-w-4xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-xl font-bold text-slate-900">Activity</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Real-time activity feed
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <p className="p-6 text-sm text-red-500">{error}</p>
        ) : logs.length === 0 ? (
          <p className="p-6 text-sm text-slate-400 text-center">
            No activity yet.
          </p>
        ) : (
          <ul className="divide-y divide-slate-50">
            <AnimatePresence initial={false}>
              {logs.map((log, i) => (
                <motion.li
                  key={log.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 12 }}
                  transition={{ delay: i < 10 ? i * 0.03 : 0 }}
                  className="flex items-start gap-4 px-5 py-3"
                >
                  <div className="w-7 h-7 mt-0.5 rounded-full bg-brand-red/10 text-brand-red flex items-center justify-center text-xs font-bold uppercase shrink-0">
                    {(log.profiles?.display_name ?? log.profiles?.email ?? '?')[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-800">
                      <span className="font-medium">
                        {log.profiles?.display_name ??
                          log.profiles?.email ??
                          'Unknown'}
                      </span>{' '}
                      <span className="text-slate-500">{log.action}</span>
                      {log.resource && (
                        <>
                          {' '}
                          <span className="font-mono text-xs bg-slate-100 px-1 rounded">
                            {log.resource}
                          </span>
                        </>
                      )}
                    </p>
                  </div>
                  <span className="text-xs text-slate-400 shrink-0 mt-0.5">
                    {timeAgo(log.created_at)}
                  </span>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </motion.div>
  );
}
