import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import { useArtifactsInfinite, PAGE_SIZE } from '../useArtifactsInfinite';

// --- Spy references so individual tests can assert calls ---
let spyFrom: ReturnType<typeof vi.fn>;
let spySelect: ReturnType<typeof vi.fn>;
let spyOr: ReturnType<typeof vi.fn>;
let spyIn: ReturnType<typeof vi.fn>;
let spyOrder: ReturnType<typeof vi.fn>;
let spyRange: ReturnType<typeof vi.fn>;

/** Build a fresh query-builder mock that tracks calls and resolves range(). */
function makeChain(rangeResult: { data: unknown[]; error: unknown; count: number | null }) {
  // All methods return the same chain object so method chaining works.
  const chain: Record<string, ReturnType<typeof vi.fn>> = {};
  spyRange = vi.fn().mockResolvedValue(rangeResult);
  spyOrder = vi.fn().mockReturnValue(chain);
  spyIn = vi.fn().mockReturnValue(chain);
  spyOr = vi.fn().mockReturnValue(chain);
  spySelect = vi.fn().mockReturnValue(chain);
  chain.select = spySelect;
  chain.or = spyOr;
  chain.in = spyIn;
  chain.order = spyOrder;
  chain.range = spyRange;
  return chain;
}

// The module mock replaces the whole supabase module. We re-wire `from` per test.
vi.mock('../../lib/supabase', () => ({
  supabase: { from: vi.fn() },
}));

// Import AFTER vi.mock so we get the mocked version.
import { supabase } from '../../lib/supabase';

// --- QueryClientProvider wrapper with retry: false ---
function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

const DEFAULT_PARAMS = {
  search: '',
  variants: [] as string[],
  sortColumn: 'week_ending' as const,
  sortAscending: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  spyFrom = supabase.from as ReturnType<typeof vi.fn>;
  // Default: empty result, no error
  spyFrom.mockReturnValue(makeChain({ data: [], error: null, count: 0 }));
});

describe('useArtifactsInfinite', () => {
  it('calls supabase.from("artifacts") on first mount with empty params', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(spyFrom).toHaveBeenCalledWith('artifacts');
  });

  it('calls .select with count: exact', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(spySelect).toHaveBeenCalledWith(
      expect.stringContaining('work_request'),
      { count: 'exact' }
    );
  });

  it('calls .order("week_ending", { ascending: false }) by default', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(spyOrder).toHaveBeenCalledWith('week_ending', { ascending: false });
  });

  it('calls .range(0, PAGE_SIZE - 1) for first page', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(spyRange).toHaveBeenCalledWith(0, PAGE_SIZE - 1);
  });

  it('does NOT call .or() when search is empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(spyOr).not.toHaveBeenCalled();
  });

  it('calls .or() with sanitized+normalized term when search is non-empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, search: 'WR123' }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    const orArg = spyOr.mock.calls[0][0] as string;
    expect(orArg).toContain('work_request.ilike.%WR123%');
    expect(orArg).toContain('week_ending_fmt.ilike.%WR123%');
  });

  it('strips forbidden chars from raw search before interpolation into .or()', async () => {
    // Raw "12%(3),4" → sanitized "1234" → normalized "1234"
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, search: '12%(3),4' }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    const orArg = spyOr.mock.calls[0][0] as string;
    expect(orArg).not.toContain('%(3)');
    expect(orArg).toContain('1234');
  });

  it('normalizes "05/26/25" to "052625" in the .or() term', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, search: '05/26/25' }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    const orArg = spyOr.mock.calls[0][0] as string;
    expect(orArg).toContain('052625');
  });

  it('calls .in("variant", variants) when variants is non-empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, variants: ['helper', 'vac_crew'] }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(spyIn).toHaveBeenCalledWith('variant', ['helper', 'vac_crew']);
  });

  it('does NOT call .in() when variants is empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(spyIn).not.toHaveBeenCalled();
  });

  it('throws (status becomes error) when supabase returns an error object', async () => {
    spyFrom.mockReturnValue(
      makeChain({ data: null, error: { message: 'DB error' }, count: null })
    );
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('error'));
  });

  it('getNextPageParam returns undefined when loaded rows >= count (no more pages)', async () => {
    const rows = Array.from({ length: PAGE_SIZE }, (_, i) => ({ id: String(i) }));
    spyFrom.mockReturnValue(
      makeChain({ data: rows, error: null, count: PAGE_SIZE })
    );
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(result.current.hasNextPage).toBe(false);
  });
});
