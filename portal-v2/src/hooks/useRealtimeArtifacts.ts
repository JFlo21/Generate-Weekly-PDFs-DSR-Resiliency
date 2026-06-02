import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { supabase } from '../lib/supabase';
import { useAuth } from './useAuth';

/**
 * useRealtimeArtifacts — DATA-06 / D-03 / D-04 / D-05
 *
 * Subscribes to Supabase Realtime postgres_changes INSERT events on
 * public.artifacts when the authenticated user holds a billing or admin role.
 *
 * Defense-in-depth design:
 *   Layer 1 — client-side gate: !loading && (isBilling || isAdmin)
 *   Layer 2 — RLS: artifacts_select_billing_or_admin evaluated server-side
 *   Layer 3 — count-only: _payload data NEVER enters React state
 *
 * Returns { pendingCount, clearPending, dismissPending }:
 *   clearPending  — resets count + invalidates ['artifacts'] query (triggers refetch)
 *   dismissPending — resets count WITHOUT refetch (pill dismiss, D-03 no-auto-insert)
 */
export function useRealtimeArtifacts(): {
  pendingCount: number;
  clearPending: () => void;
  dismissPending: () => void;
} {
  const { isBilling, isAdmin, loading } = useAuth();
  const queryClient = useQueryClient();
  const [pendingCount, setPendingCount] = useState(0);
  const channelRef = useRef<ReturnType<typeof supabase.channel> | undefined>(
    undefined
  );

  useEffect(() => {
    // D-04 defense-in-depth + Pitfall 4 loading-race:
    // Only subscribe when auth is resolved AND the role qualifies.
    if (loading || (!isBilling && !isAdmin)) return;

    const channel = supabase
      .channel('artifacts')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'artifacts' },
        (_payload) => {
          // Count-only — _payload data NEVER enters state (D-04 Layer 3)
          setPendingCount((n) => n + 1);
        }
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      void channel.unsubscribe(); // zero subscription leak (D-04 / UI-SPEC)
    };
  }, [isBilling, isAdmin, loading]);

  // Load action: reset count + invalidate ['artifacts'] so the table refetches
  const clearPending = useCallback(() => {
    setPendingCount(0);
    void queryClient.invalidateQueries({ queryKey: ['artifacts'] });
  }, [queryClient]);

  // Dismiss action: reset count WITHOUT refetch (D-03 — no mid-scroll auto-insert)
  const dismissPending = useCallback(() => {
    setPendingCount(0);
  }, []);

  return { pendingCount, clearPending, dismissPending };
}
