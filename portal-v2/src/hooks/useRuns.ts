import { useState, useEffect, useRef, useCallback } from 'react';
import { api, getApiAuthHeaders } from '../lib/api';
import { USE_MOCK, MOCK_RUNS } from '../lib/mockData';
import type { WorkflowRun } from '../lib/types';

const POLL_INTERVAL_MS = 120_000; // 2 minutes
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

type EventStreamHandlers = {
  onOpen: () => void;
  onRunsUpdated: () => void;
  onError: () => void;
};

function handleSseBlock(block: string, handlers: EventStreamHandlers) {
  const eventLine = block
    .split('\n')
    .find((line) => line.startsWith('event:'));
  const eventName = eventLine?.slice('event:'.length).trim();
  if (eventName === 'runs-updated') handlers.onRunsUpdated();
}

function consumeSseBuffer(buffer: string, handlers: EventStreamHandlers): string {
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const blocks = normalized.split('\n\n');
  for (const block of blocks.slice(0, -1)) {
    handleSseBlock(block, handlers);
  }
  return blocks[blocks.length - 1] ?? '';
}

function openFetchEventStream(
  url: string,
  headers: Headers,
  handlers: EventStreamHandlers
): () => void {
  const controller = new AbortController();
  let closed = false;

  fetch(url, {
    credentials: 'include',
    headers,
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok || !res.body) {
        throw new Error(`SSE connection failed with HTTP ${res.status}`);
      }

      handlers.onOpen();
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer = consumeSseBuffer(
          buffer + decoder.decode(value, { stream: true }),
          handlers
        );
      }

      buffer = consumeSseBuffer(buffer + decoder.decode(), handlers);
      if (!closed) handlers.onError();
    })
    .catch(() => {
      if (!closed) handlers.onError();
    });

  return () => {
    closed = true;
    controller.abort();
  };
}

async function openRunsEventStream(
  url: string,
  handlers: EventStreamHandlers
): Promise<() => void> {
  const authHeaders = await getApiAuthHeaders();
  if (authHeaders.has('Authorization')) {
    return openFetchEventStream(url, authHeaders, handlers);
  }

  let es: EventSource | null = new EventSource(url, { withCredentials: true });
  es.addEventListener('open', handlers.onOpen);
  es.addEventListener('runs-updated', handlers.onRunsUpdated);
  es.addEventListener('error', () => {
    handlers.onError();
    es?.close();
    es = null;
  });

  return () => {
    es?.close();
    es = null;
  };
}

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
    const initialFetch = fetchRef.current?.() ?? Promise.resolve();

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

    let closeEvents: (() => void) | null = null;
    let cancelled = false;
    initialFetch.finally(() => {
      if (cancelled) return;
      const sseUrl = `${API_BASE}/api/events`;
      openRunsEventStream(sseUrl, {
        onOpen: () => {
          if (!cancelled) setIsConnected(true);
        },
        onRunsUpdated: () => {
          if (cancelled) return;
          if (timerRef.current) clearTimeout(timerRef.current);
          fetchRef.current?.();
        },
        onError: () => {
          if (cancelled) return;
          setIsConnected(false);
          closeEvents?.();
          closeEvents = null;
        },
      })
        .then((close) => {
          if (cancelled) {
            close();
            return;
          }
          closeEvents = close;
        })
        .catch(() => {
          if (!cancelled) setIsConnected(false);
        });
    });

    // Countdown ticker
    countdownRef.current = setInterval(() => {
      setCountdown((c) => Math.max(0, c - 1));
    }, 1000);

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
      closeEvents?.();
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
