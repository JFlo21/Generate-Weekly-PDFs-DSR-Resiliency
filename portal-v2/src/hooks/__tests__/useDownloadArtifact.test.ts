import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// vi.hoisted allows variables referenced in vi.mock factory to be defined first.
const { mockCreateSignedUrl, mockStorageFrom } = vi.hoisted(() => {
  const mockCreateSignedUrl = vi.fn();
  const mockStorageFrom = vi.fn().mockReturnValue({ createSignedUrl: mockCreateSignedUrl });
  return { mockCreateSignedUrl, mockStorageFrom };
});

vi.mock('../../lib/supabase', () => ({
  supabase: {
    storage: {
      from: mockStorageFrom,
    },
  },
}));

import { useDownloadArtifact } from '../useDownloadArtifact';

// --- DOM spy helpers ---
let fakeAnchor: HTMLAnchorElement;
let appendChildSpy: ReturnType<typeof vi.spyOn>;
let removeChildSpy: ReturnType<typeof vi.spyOn>;
let clickSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();

  // Reset storage mock for each test
  mockStorageFrom.mockReturnValue({ createSignedUrl: mockCreateSignedUrl });

  // Create a fake <a> element with a click spy
  fakeAnchor = document.createElement('a');
  clickSpy = vi.fn();
  fakeAnchor.click = clickSpy;

  // Only intercept 'a' tag creation; let the spy passthrough for other tags
  vi.spyOn(document, 'createElement').mockImplementation(
    (tag: string, ...rest: unknown[]) => {
      if (tag === 'a') return fakeAnchor;
      // Use the original HTMLDocument prototype so we don't recurse
      return HTMLDocument.prototype.createElement.call(document, tag, ...(rest as []));
    }
  );

  appendChildSpy = vi.spyOn(document.body, 'appendChild').mockReturnValue(fakeAnchor);
  removeChildSpy = vi.spyOn(document.body, 'removeChild').mockReturnValue(fakeAnchor);
});

afterEach(() => {
  vi.restoreAllMocks();
});

const addToast = vi.fn();

describe('useDownloadArtifact', () => {
  it('calls supabase.storage.from("excel-artifacts").createSignedUrl with path and TTL 300', async () => {
    mockCreateSignedUrl.mockResolvedValue({
      data: { signedUrl: 'https://example.com/file.xlsx' },
      error: null,
    });

    const { result } = renderHook(() => useDownloadArtifact(addToast));

    await act(async () => {
      await result.current.download('row-1', '2026-05-17/file.xlsx', 'file.xlsx');
    });

    expect(mockStorageFrom).toHaveBeenCalledWith('excel-artifacts');
    expect(mockCreateSignedUrl).toHaveBeenCalledWith('2026-05-17/file.xlsx', 300);
  });

  it('creates an <a> with href=signedUrl and download=filename, appends, clicks, removes on success', async () => {
    mockCreateSignedUrl.mockResolvedValue({
      data: { signedUrl: 'https://example.com/file.xlsx' },
      error: null,
    });

    const { result } = renderHook(() => useDownloadArtifact(addToast));

    await act(async () => {
      await result.current.download('row-1', '2026-05-17/file.xlsx', 'file.xlsx');
    });

    expect(fakeAnchor.href).toContain('example.com/file.xlsx');
    expect(fakeAnchor.download).toBe('file.xlsx');
    expect(appendChildSpy).toHaveBeenCalledWith(fakeAnchor);
    expect(clickSpy).toHaveBeenCalled();
    expect(removeChildSpy).toHaveBeenCalledWith(fakeAnchor);
  });

  it('sets downloading to rowId while in flight and resets to undefined in finally', async () => {
    let resolveSignedUrl!: (v: unknown) => void;
    mockCreateSignedUrl.mockReturnValue(
      new Promise((resolve) => { resolveSignedUrl = resolve; })
    );

    const { result } = renderHook(() => useDownloadArtifact(addToast));

    // Start download but don't await — check mid-flight state
    let downloadPromise!: Promise<void>;
    act(() => {
      downloadPromise = result.current.download('row-abc', 'path', 'name.xlsx');
    });

    // While in flight, downloading should be set
    expect(result.current.downloading).toBe('row-abc');

    // Resolve the promise
    await act(async () => {
      resolveSignedUrl({ data: { signedUrl: 'https://x.com/f' }, error: null });
      await downloadPromise;
    });

    // After completion, downloading resets to undefined
    expect(result.current.downloading).toBeUndefined();
  });

  it('calls addToast("error", ...) and does NOT click anchor when createSignedUrl returns an error', async () => {
    mockCreateSignedUrl.mockResolvedValue({
      data: null,
      error: { message: 'Storage permission denied' },
    });

    const { result } = renderHook(() => useDownloadArtifact(addToast));

    await act(async () => {
      await result.current.download('row-1', 'path/file.xlsx', 'file.xlsx');
    });

    expect(addToast).toHaveBeenCalledWith('error', expect.stringContaining('Storage permission denied'));
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it('calls addToast("error", ...) when createSignedUrl rejects (thrown error)', async () => {
    mockCreateSignedUrl.mockRejectedValue(new Error('Network failure'));

    const { result } = renderHook(() => useDownloadArtifact(addToast));

    await act(async () => {
      await result.current.download('row-1', 'path/file.xlsx', 'file.xlsx');
    });

    expect(addToast).toHaveBeenCalledWith('error', 'Network failure');
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it('resets downloading to undefined in finally even when download fails', async () => {
    mockCreateSignedUrl.mockResolvedValue({
      data: null,
      error: { message: 'Forbidden' },
    });

    const { result } = renderHook(() => useDownloadArtifact(addToast));

    await act(async () => {
      await result.current.download('row-err', 'path/file.xlsx', 'file.xlsx');
    });

    expect(result.current.downloading).toBeUndefined();
  });
});
