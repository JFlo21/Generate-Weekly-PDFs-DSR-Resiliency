import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import type { WorkflowRun } from '../lib/types';

const POLL_INTERVAL_MS = 120_000; // 2 minutes

export function useRuns() {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [countdown, setCountdown] = useState(POLL_INTERVAL_MS / 1000);
  const [isConnected, setIsConnected] = useState(false);
  const runsRef = useRef(runs);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    runsRef.current = runs;
  }, [runs]);

  const fetchRuns = useCallback(async () => {
    try {
      const data = await api.getRuns();
      const existingIds = new Set(runsRef.current.map((r) => r.id));
      const withNew = data.map((r) => ({
        ...r,
        isNew: !existingIds.has(r.id) && existingIds.size > 0,
      }));
      setRuns(withNew);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs');
    } finally {
      setLoading(false);
    }

    // Schedule next poll
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      fetchRuns();
    }, POLL_INTERVAL_MS);

    // Reset countdown
    setCountdown(POLL_INTERVAL_MS / 1000);
  }, []);

  // Initial fetch + SSE
  useEffect(() => {
    fetchRuns();

    // SSE for real-time updates
    const es = new EventSource('/api/events');
    es.addEventListener('open', () => setIsConnected(true));
    es.addEventListener('runs-updated', () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      fetchRuns();
    });
    es.addEventListener('error', () => setIsConnected(false));

    // Countdown ticker
    countdownRef.current = setInterval(() => {
      setCountdown((c) => Math.max(0, c - 1));
    }, 1000);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
      es.close();
    };
  }, [fetchRuns]);

  return { runs, loading, error, lastUpdated, countdown, isConnected, refresh: fetchRuns };
}
