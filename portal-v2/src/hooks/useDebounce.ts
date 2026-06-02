import { useState, useEffect } from 'react';

/**
 * Debounces a value, only emitting it after `delayMs` have elapsed
 * since the last change. Used for search input (250ms) to avoid
 * firing a Supabase query on every keystroke.
 */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}
