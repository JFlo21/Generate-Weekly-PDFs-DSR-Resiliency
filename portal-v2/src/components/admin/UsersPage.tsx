import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { supabase } from '../../lib/supabase';
import type { Profile, UserRole } from '../../lib/types';
import { formatDate, cn } from '../../lib/utils';
import { Skeleton } from '../ui/Skeleton';
import { Badge } from '../ui/Badge';
import { useToast } from '../../hooks/useToast';
import { ToastContainer } from '../ui/Toast';
import { useAuth } from '../../hooks/useAuth';

const ROLES: UserRole[] = ['admin', 'billing', 'pending'];

/**
 * Returns true if the role change is allowed, false if it must be blocked.
 * Exported for unit-testing (RBAC-04). This is the exact condition used in
 * updateRole — no duplicated logic.
 */
export function canDemote(
  targetCurrentRole: string,
  newRole: string,
  adminCount: number
): boolean {
  if (targetCurrentRole === 'admin' && newRole !== 'admin' && adminCount <= 1) {
    return false; // blocked — last admin
  }
  return true;
}

const roleBadgeVariant: Record<UserRole, 'info' | 'success' | 'warning'> = {
  admin: 'info',
  billing: 'success',
  pending: 'warning',
};

export function UsersPage() {
  const [users, setUsers] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toasts, addToast, removeToast } = useToast();
  const { user } = useAuth();
  const currentUserId = user?.id;

  const adminCount = users.filter((u) => u.role === 'admin').length;

  const loadUsers = useCallback(() => {
    setLoading(true);
    setError(null);
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

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  async function updateRole(userId: string, role: UserRole) {
    const targetUser = users.find((u) => u.id === userId);
    if (!canDemote(targetUser?.role ?? '', role, adminCount)) {
      addToast('error', 'Cannot demote the last admin. Promote another user to admin first.');
      return;
    }
    const { error: err } = await supabase
      .from('profiles')
      .update({ role })
      .eq('id', userId);
    if (err) {
      addToast('error', 'Role update failed. Please try again.');
    } else {
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
      addToast('success', `Role updated to ${role}.`);
    }
  }

  const pendingCount = users.filter((u) => u.role === 'pending').length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 max-w-5xl mx-auto space-y-6"
    >
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-900">Users</h1>
          {pendingCount > 0 && (
            <Badge variant="warning">{pendingCount} pending</Badge>
          )}
        </div>
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
          <div className="p-6">
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 flex items-center justify-between">
              <span>Could not load users. Check your connection and try again.</span>
              <button
                onClick={() => loadUsers()}
                className="text-xs text-red-600 hover:underline ml-4 shrink-0"
              >
                Retry
              </button>
            </div>
          </div>
        ) : users.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-12">No users found.</p>
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
              {users.map((u, i) => {
                const isLastAdmin = u.id === currentUserId && adminCount <= 1;
                return (
                  <motion.tr
                    key={u.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.04 }}
                    className={cn(
                      'border-b border-slate-50 hover:bg-slate-50/50 transition-colors',
                      u.role === 'pending' && 'bg-amber-50/40'
                    )}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-brand-red/10 text-brand-red flex items-center justify-center text-xs font-bold uppercase">
                          {u.email[0].toUpperCase()}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-800">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => updateRole(u.id, e.target.value as UserRole)}
                        disabled={isLastAdmin}
                        aria-disabled={isLastAdmin ? 'true' : undefined}
                        title={
                          isLastAdmin
                            ? 'You are the last admin and cannot change your own role'
                            : undefined
                        }
                        className={cn(
                          'text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-red/40',
                          isLastAdmin && 'opacity-50 cursor-not-allowed'
                        )}
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-5 py-3">
                      <Badge variant={roleBadgeVariant[u.role]}>{u.role}</Badge>
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400">
                      {formatDate(u.created_at)}
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </motion.div>
  );
}
