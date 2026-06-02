import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Mock supabase channel (D-05 mock-channel assertions)
// ---------------------------------------------------------------------------
let capturedInsertCallback: ((_payload: unknown) => void) | null = null;
const unsubscribeSpy = vi.fn().mockResolvedValue(undefined);

// Build channelMock without circular self-reference at declaration time.
// subscribe() returns the channel object itself (chainable API).
const channelMock: {
  on: ReturnType<typeof vi.fn>;
  subscribe: ReturnType<typeof vi.fn>;
  unsubscribe: ReturnType<typeof vi.fn>;
} = {
  on: vi.fn().mockImplementation(
    (_event: string, _filter: unknown, cb: (_payload: unknown) => void) => {
      capturedInsertCallback = cb;
      return channelMock; // chainable — safe to reference after declaration
    }
  ),
  subscribe: vi.fn().mockImplementation(() => channelMock),
  unsubscribe: unsubscribeSpy,
};

const channelSpy = vi.fn().mockReturnValue(channelMock);

vi.mock('../../lib/supabase', () => ({
  supabase: {
    channel: channelSpy,
  },
}));

// ---------------------------------------------------------------------------
// Mock useAuth — drive role/loading states per test
// ---------------------------------------------------------------------------
const mockAuth = {
  loading: false,
  isBilling: true,
  isAdmin: false,
};

vi.mock('../useAuth', () => ({
  useAuth: () => mockAuth,
}));

// ---------------------------------------------------------------------------
// QueryClient wrapper factory
// ---------------------------------------------------------------------------
function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children),
    queryClient,
  };
}

// ---------------------------------------------------------------------------
// Import under test (after mocks are registered)
// ---------------------------------------------------------------------------
const { useRealtimeArtifacts } = await import('../useRealtimeArtifacts');

// ---------------------------------------------------------------------------
// Reset spies between tests
// ---------------------------------------------------------------------------
beforeEach(() => {
  capturedInsertCallback = null;
  channelSpy.mockClear();
  channelMock.on.mockClear();
  channelMock.subscribe.mockClear();
  unsubscribeSpy.mockClear();
  channelMock.on.mockImplementation(
    (_event: string, _filter: unknown, cb: (_payload: unknown) => void) => {
      capturedInsertCallback = cb;
      return channelMock;
    }
  );
  channelMock.subscribe.mockImplementation(() => channelMock);
  mockAuth.loading = false;
  mockAuth.isBilling = true;
  mockAuth.isAdmin = false;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('useRealtimeArtifacts (D-05 mock-channel assertions)', () => {
  it('Test 1: INSERT event fires once → pendingCount=1; fires twice → pendingCount=2', async () => {
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useRealtimeArtifacts(), { wrapper });

    expect(result.current.pendingCount).toBe(0);

    act(() => {
      capturedInsertCallback?.({ eventType: 'INSERT' });
    });
    expect(result.current.pendingCount).toBe(1);

    act(() => {
      capturedInsertCallback?.({ eventType: 'INSERT' });
    });
    expect(result.current.pendingCount).toBe(2);
  });

  it('Test 2: clearPending() resets pendingCount to 0 AND calls invalidateQueries', async () => {
    const { wrapper, queryClient } = makeWrapper();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useRealtimeArtifacts(), { wrapper });

    act(() => {
      capturedInsertCallback?.({ eventType: 'INSERT' });
    });
    expect(result.current.pendingCount).toBe(1);

    await act(async () => {
      result.current.clearPending();
    });

    expect(result.current.pendingCount).toBe(0);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['artifacts'] });
  });

  it('Test 3: unmount calls channel.unsubscribe() exactly once', () => {
    const { wrapper } = makeWrapper();
    const { unmount } = renderHook(() => useRealtimeArtifacts(), { wrapper });

    expect(unsubscribeSpy).not.toHaveBeenCalled();
    unmount();
    expect(unsubscribeSpy).toHaveBeenCalledTimes(1);
  });

  it('Test 4: pending role (isBilling=false, isAdmin=false) — supabase.channel is NEVER called', () => {
    mockAuth.isBilling = false;
    mockAuth.isAdmin = false;

    const { wrapper } = makeWrapper();
    renderHook(() => useRealtimeArtifacts(), { wrapper });

    expect(channelSpy).not.toHaveBeenCalled();
  });

  it('Test 4b (CR-01): two hook instances use distinct channel names', () => {
    const { wrapper: wrapperA } = makeWrapper();
    const { wrapper: wrapperB } = makeWrapper();

    renderHook(() => useRealtimeArtifacts(), { wrapper: wrapperA });
    renderHook(() => useRealtimeArtifacts(), { wrapper: wrapperB });

    expect(channelSpy).toHaveBeenCalledTimes(2);
    const nameA = channelSpy.mock.calls[0][0] as string;
    const nameB = channelSpy.mock.calls[1][0] as string;
    expect(nameA).toMatch(/^artifacts:/);
    expect(nameB).toMatch(/^artifacts:/);
    expect(nameA).not.toBe(nameB);
  });

  it('Test 5 (loading race, Pitfall 4): loading=true → no subscribe even if role would qualify', () => {
    mockAuth.loading = true;
    mockAuth.isBilling = true;

    const { wrapper } = makeWrapper();
    renderHook(() => useRealtimeArtifacts(), { wrapper });

    expect(channelSpy).not.toHaveBeenCalled();
  });

  it('Test 6: dismissPending() resets pendingCount to 0 WITHOUT calling invalidateQueries (D-03)', async () => {
    const { wrapper, queryClient } = makeWrapper();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useRealtimeArtifacts(), { wrapper });

    act(() => {
      capturedInsertCallback?.({ eventType: 'INSERT' });
    });
    expect(result.current.pendingCount).toBe(1);

    act(() => {
      result.current.dismissPending();
    });

    expect(result.current.pendingCount).toBe(0);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
