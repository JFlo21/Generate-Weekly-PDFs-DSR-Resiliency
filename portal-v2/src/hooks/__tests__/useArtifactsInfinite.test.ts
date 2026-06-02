import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import { useArtifactsInfinite, PAGE_SIZE } from '../useArtifactsInfinite';

// --- Mock supabase module (PATTERNS.md lines 696-709) ---
const mockRange = vi.fn().mockResolvedValue({ data: [], error: null, count: 0 });
const mockOrder = vi.fn().mockReturnThis();
const mockIn = vi.fn().mockReturnThis();
const mockOr = vi.fn().mockReturnThis();
const mockSelect = vi.fn().mockReturnThis();
const mockFrom = vi.fn().mockReturnValue({
  select: mockSelect,
  or: mockOr,
  in: mockIn,
  order: mockOrder,
  range: mockRange,
});

vi.mock('../../../lib/supabase', () => ({
  supabase: {
    from: mockFrom,
  },
}));

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
  // Reset the chain mocks — each must return the right thing
  mockFrom.mockReturnValue({
    select: mockSelect,
    or: mockOr,
    in: mockIn,
    order: mockOrder,
    range: mockRange,
  });
  mockSelect.mockReturnValue({ or: mockOr, in: mockIn, order: mockOrder, range: mockRange });
  mockOr.mockReturnValue({ in: mockIn, order: mockOrder, range: mockRange });
  mockIn.mockReturnValue({ order: mockOrder, range: mockRange });
  mockOrder.mockReturnValue({ range: mockRange });
  mockRange.mockResolvedValue({ data: [], error: null, count: 0 });
});

describe('useArtifactsInfinite', () => {
  it('calls supabase.from("artifacts") on first mount with empty params', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(mockFrom).toHaveBeenCalledWith('artifacts');
  });

  it('calls .select with count: exact', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(mockSelect).toHaveBeenCalledWith(
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
    expect(mockOrder).toHaveBeenCalledWith('week_ending', { ascending: false });
  });

  it('calls .range(0, PAGE_SIZE - 1) for first page', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(mockRange).toHaveBeenCalledWith(0, PAGE_SIZE - 1);
  });

  it('does NOT call .or() when search is empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(mockOr).not.toHaveBeenCalled();
  });

  it('calls .or() with sanitized+normalized term when search is non-empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, search: 'WR123' }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(mockOr).toHaveBeenCalledWith(
      expect.stringMatching(/work_request\.ilike\.%WR123%/)
    );
    expect(mockOr).toHaveBeenCalledWith(
      expect.stringMatching(/week_ending_fmt\.ilike\.%WR123%/)
    );
  });

  it('strips forbidden chars from raw search before interpolation into .or()', async () => {
    // Raw "12%(3),4" → sanitized "1234" → normalized "1234"
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, search: '12%(3),4' }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    const orCall = mockOr.mock.calls[0][0] as string;
    expect(orCall).not.toContain('%12%(3)');
    expect(orCall).toContain('1234');
  });

  it('normalizes "05/26/25" to "052625" in the .or() term', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, search: '05/26/25' }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    const orCall = mockOr.mock.calls[0][0] as string;
    expect(orCall).toContain('052625');
  });

  it('calls .in("variant", variants) when variants is non-empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite({ ...DEFAULT_PARAMS, variants: ['helper', 'vac_crew'] }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(mockIn).toHaveBeenCalledWith('variant', ['helper', 'vac_crew']);
  });

  it('does NOT call .in() when variants is empty', async () => {
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(mockIn).not.toHaveBeenCalled();
  });

  it('throws (status becomes error) when supabase returns an error object', async () => {
    mockRange.mockResolvedValue({ data: null, error: { message: 'DB error' }, count: null });
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('error'));
  });

  it('getNextPageParam returns undefined when loaded rows >= count (no more pages)', async () => {
    const rows = Array.from({ length: PAGE_SIZE }, (_, i) => ({ id: String(i) }));
    mockRange.mockResolvedValue({ data: rows, error: null, count: PAGE_SIZE });
    const { result } = renderHook(
      () => useArtifactsInfinite(DEFAULT_PARAMS),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(result.current.hasNextPage).toBe(false);
  });
});
