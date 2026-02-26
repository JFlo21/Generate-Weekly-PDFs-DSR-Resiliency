import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { supabase } from '../../lib/supabase';
import type { Profile, UserRole } from '../../lib/types';
import { formatDate } from '../../lib/utils';
import { Skeleton } from '../ui/Skeleton';
import { Badge } from '../ui/Badge';
import { useToast } from '../../hooks/useToast';
import { ToastContainer } from '../ui/Toast';

const ROLES: UserRole[] = ['viewer', 'biller', 'admin'];

export function UsersPage() {
  const [users, setUsers] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toasts, addToast, removeToast } = useToast();

  useEffect(() => {
    supabase
      .from('profiles')
      .select('*')
      .order('created_at', { ascending: false })
      .then(({ data, error: err }) => {
        if (err) setError(err.message);
        else setUsers((data ?? []) as Profile[]);
        setLoading(false);
      });
  }, []);

  async function updateRole(userId: string, role: UserRole) {
    const { error: err } = await supabase
      .from('profiles')
      .update({ role })
      .eq('id', userId);
    if (err) {
      addToast('error', `Failed to update role: ${err.message}`);
    } else {
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role } : u))
      );
      addToast('success', `Role updated to ${role}`);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 max-w-5xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-xl font-bold text-slate-900">Users</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Manage user roles and access
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : error ? (
          <p className="p-6 text-sm text-red-500">{error}</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  User
                </th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Role
                </th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Joined
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((user, i) => (
                <motion.tr
                  key={user.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.04 }}
                  className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-brand-red/10 text-brand-red flex items-center justify-center text-xs font-bold uppercase">
                        {(user.display_name ?? user.email)[0]}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-800">
                          {user.display_name ?? '—'}
                        </p>
                        <p className="text-xs text-slate-400">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <select
                      value={user.role}
                      onChange={(e) =>
                        updateRole(user.id, e.target.value as UserRole)
                      }
                      className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-red/40"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant={user.is_active ? 'success' : 'default'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-400">
                    {formatDate(user.created_at)}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </motion.div>
  );
}
