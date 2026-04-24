import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import { USE_MOCK, MOCK_RUNS } from '../lib/mockData';
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
  // True when the current `runs` array came from the MOCK_RUNS fallback
  // instead of a live API call. Used to drive UI indicators (banner, pill).
  const [isSampleData, setIsSampleData] = useState<boolean>(USE_MOCK);
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
      // A successful real response clears any prior sample-data state
      // unless we were started in forced mock mode.
      if (!USE_MOCK) setIsSampleData(false);
    } catch (err) {
      // Distinguish network errors (CORS blocks, offline, DNS failures) from
      // legitimate HTTP errors (4xx/5xx where the backend DID respond).
      // `fetch()` throws `TypeError: Failed to fetch` for network-level issues
      // — in that case we swap in mock data so the preview stays usable.
      // Real HTTP errors get surfaced so production debugging still works.
      const msg = err instanceof Error ? err.message : String(err);
      const isNetworkError =
        err instanceof TypeError ||
        /failed to fetch|networkerror|load failed/i.test(msg);
      if (isNetworkError) {
        console.warn('[v0] Backend unreachable, falling back to sample data.', err);
        setRuns(MOCK_RUNS);
        setLastUpdated(new Date());
        setError(null);
        setIsConnected(true);
        setIsSampleData(true);
      } else {
        setError(msg || 'Failed to fetch runs');
      }
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

    // In mock/demo mode, mark as connected (simulated) and skip SSE entirely.
    if (USE_MOCK) {
      setIsConnected(true);
      countdownRef.current = setInterval(() => {
        setCountdown((c) => Math.max(0, c - 1));
      }, 1000);
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        if (countdownRef.current) clearInterval(countdownRef.current);
      };
    }

    // Only open an SSE connection if we have a backend URL configured.
    let es: EventSource | null = null;
    const sseUrl = `${API_BASE}/api/events`;
    try {
      es = new EventSource(sseUrl, { withCredentials: true });
      es.addEventListener('open', () => setIsConnected(true));
      es.addEventListener('runs-updated', () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        fetchRef.current?.();
      });
      es.addEventListener('error', () => {
        setIsConnected(false);
        // Close on ANY error — CORS blocks leave EventSource stuck in
        // CONNECTING state and the browser auto-retries every ~3s forever,
        // flooding the console. The 2-minute poll covers updates regardless.
        if (es) {
          es.close();
          es = null;
        }
      });
    } catch {
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

  return {
    runs,
    loading,
    error,
    lastUpdated,
    countdown,
    isConnected,
    isSampleData,
    refresh: fetchRuns,
  };
}
