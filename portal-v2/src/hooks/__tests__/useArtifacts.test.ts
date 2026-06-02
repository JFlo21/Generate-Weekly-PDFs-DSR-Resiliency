import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { useArtifacts } from '../useArtifacts';

/**
 * TABLE-02: Assert the mock fallback is gone.
 * The hook must be a stub — no MOCK_ARTIFACTS reference, no [v0] log.
 */
describe('useArtifacts (stub — TABLE-02)', () => {
  it('module source contains no reference to MOCK_ARTIFACTS', () => {
    // Read the source file directly to assert at the text level
    const src = readFileSync(
      resolve(__dirname, '../useArtifacts.ts'),
      'utf-8'
    );
    expect(src).not.toContain('MOCK_ARTIFACTS');
  });

  it('module source contains no [v0] mock-fallback log line', () => {
    const src = readFileSync(
      resolve(__dirname, '../useArtifacts.ts'),
      'utf-8'
    );
    expect(src).not.toContain('[v0]');
  });

  it('rendering the hook never yields mock rows — artifacts is always empty array', () => {
    const { result } = renderHook(() => useArtifacts(1));
    expect(result.current.artifacts).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeUndefined();
  });

  it('rendering with null runId also returns empty artifacts', () => {
    const { result } = renderHook(() => useArtifacts(null));
    expect(result.current.artifacts).toEqual([]);
  });

  it('exports function useArtifacts (name preserved for Phase 07 cleanup)', () => {
    expect(typeof useArtifacts).toBe('function');
  });
});
