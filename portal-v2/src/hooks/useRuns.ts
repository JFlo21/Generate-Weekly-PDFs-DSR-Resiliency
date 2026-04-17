import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import type { WorkflowRun } from '../lib/types';

const POLL_INTERVAL_MS = 120_000; // 2 minutes
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

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
  const fetchRef = useRef<() => Promise<void>>();

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

    // Schedule next poll via ref to avoid stale closure
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      fetchRef.current?.();
    }, POLL_INTERVAL_MS);

    // Reset countdown
    setCountdown(POLL_INTERVAL_MS / 1000);
  }, []);

  // Keep fetchRef in sync
  fetchRef.current = fetchRuns;

  // Initial fetch + SSE — runs once on mount
  useEffect(() => {
    fetchRef.current?.();

    // Only open an SSE connection if we have a backend URL configured.
    // When API_BASE is empty (no VITE_API_BASE_URL) and the Vite dev
    // server doesn't proxy /api/events, EventSource would continuously
    // error-loop and flood the console.
    let es: EventSource | null = null;
    const sseUrl = `${API_BASE}/api/events`;
    try {
      es = new EventSource(sseUrl);
      es.addEventListener('open', () => setIsConnected(true));
      es.addEventListener('runs-updated', () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        fetchRef.current?.();
      });
      es.addEventListener('error', () => {
        setIsConnected(false);
        // If the backend is unreachable, close the EventSource to stop the
        // automatic reconnect loop that browsers do every ~3s.
        if (es && es.readyState === EventSource.CLOSED) {
          es.close();
          es = null;
        }
      });
    } catch {
      // EventSource constructor can throw if the URL is invalid.
      setIsConnected(false);
    }

    // Countdown ticker
    countdownRef.current = setInterval(() => {
      setCountdown((c) => Math.max(0, c - 1));
    }, 1000);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
      es?.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { runs, loading, error, lastUpdated, countdown, isConnected, refresh: fetchRuns };
}
