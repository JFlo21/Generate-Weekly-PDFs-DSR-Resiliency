import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebounce } from '../useDebounce';

describe('useDebounce', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns the initial value immediately on first render', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDebounce('initial', 250));
    expect(result.current).toBe('initial');
  });

  it('still returns old value before delayMs elapses after a change', () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 250),
      { initialProps: { value: 'first' } }
    );

    rerender({ value: 'second' });
    // Before 250ms, still shows old value
    act(() => { vi.advanceTimersByTime(100); });
    expect(result.current).toBe('first');
  });

  it('returns the new value after delayMs elapses', () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 250),
      { initialProps: { value: 'first' } }
    );

    rerender({ value: 'second' });
    act(() => { vi.advanceTimersByTime(250); });
    expect(result.current).toBe('second');
  });

  it('only emits the final value after rapid successive changes', () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 250),
      { initialProps: { value: 'a' } }
    );

    rerender({ value: 'b' });
    act(() => { vi.advanceTimersByTime(100); });
    rerender({ value: 'c' });
    act(() => { vi.advanceTimersByTime(100); });
    rerender({ value: 'd' });
    // 200ms elapsed since last change — not yet
    expect(result.current).toBe('a');

    // Advance to 250ms after last change
    act(() => { vi.advanceTimersByTime(250); });
    expect(result.current).toBe('d');
  });
});
