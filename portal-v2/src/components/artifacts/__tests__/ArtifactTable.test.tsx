import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArtifactTable } from '../ArtifactTable';
import { ToastProvider } from '../../../contexts/ToastContext';
import type { BillingArtifact } from '../../../lib/types';

// Helper: wrap renders with the global ToastProvider (required since C-01
// moved useToast out of ArtifactTable into context — without it,
// useToastContext() throws).
function renderWithToast(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

// ---------------------------------------------------------------------------
// Mock useQuery (used inside ArtifactTable for dynamic variant options).
// Returns an empty options list so tests focus on table states, not variant UI.
// ---------------------------------------------------------------------------
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>();
  return {
    ...actual,
    useQuery: () => ({ data: [] }),
  };
});

// ---------------------------------------------------------------------------
// Mock TanStack Query hooks
// ---------------------------------------------------------------------------
const mockQuery = {
  status: 'pending' as 'pending' | 'error' | 'success',
  data: undefined as
    | { pages: Array<{ rows: BillingArtifact[]; count: number }> }
    | undefined,
  error: null as unknown,
  fetchNextPage: vi.fn(),
  hasNextPage: false,
  isFetchingNextPage: false,
  refetch: vi.fn(),
};

vi.mock('../../../hooks/useArtifactsInfinite', () => ({
  useArtifactsInfinite: () => mockQuery,
}));

// Mock useDownloadArtifact — the component threads addToast into it.
const mockDownload = vi.fn();
vi.mock('../../../hooks/useDownloadArtifact', () => ({
  useDownloadArtifact: () => ({ download: mockDownload, downloading: undefined }),
}));

// Mock useRealtimeArtifacts — DATA-06 hook; tested separately in its own suite.
vi.mock('../../../hooks/useRealtimeArtifacts', () => ({
  useRealtimeArtifacts: () => ({
    pendingCount: 0,
    clearPending: vi.fn(),
    dismissPending: vi.fn(),
  }),
}));

// ---------------------------------------------------------------------------
// Mock useVirtualizer — JSDOM has no layout, getVirtualItems() would be empty.
// We return one virtual item per row so the ArtifactTableRow renders in tests.
// ---------------------------------------------------------------------------
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (opts: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: opts.count }, (_, i) => ({
        key: i,
        index: i,
        start: i * 56,
        size: 56,
      })),
    getTotalSize: () => opts.count * 56,
  }),
}));

// ---------------------------------------------------------------------------
// Sample fixture
// ---------------------------------------------------------------------------
const SAMPLE_ROW: BillingArtifact = {
  id: 'row-uuid-1',
  work_request: 'WR-90001',
  week_ending: '2026-05-26',
  week_ending_fmt: '052626',
  variant: '',
  filename: 'WR_90001_WeekEnding_052626.xlsx',
  storage_path: '2026-05-26/WR_90001_WeekEnding_052626.xlsx',
  size_bytes: 204800,
  created_at: '2026-05-26T21:00:00.000Z',
};

beforeEach(() => {
  mockQuery.status = 'pending';
  mockQuery.data = undefined;
  mockQuery.error = null;
  mockQuery.hasNextPage = false;
  mockQuery.isFetchingNextPage = false;
  mockQuery.fetchNextPage.mockClear();
  mockQuery.refetch.mockClear();
  mockDownload.mockClear();
});

// ---------------------------------------------------------------------------
// Tests: four D-07 states
// ---------------------------------------------------------------------------
describe('ArtifactTable (TABLE-05 / D-07)', () => {
  it('renders Skeleton rows while pending', () => {
    mockQuery.status = 'pending';
    renderWithToast(<ArtifactTable />);
    // Skeletons render as animate-pulse divs.
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders error state with retry when status is error', () => {
    mockQuery.status = 'error';
    mockQuery.error = new Error('network failure');
    renderWithToast(<ArtifactTable />);
    // A-01: copy updated to match UI-SPEC §Copywriting Contract
    expect(screen.getAllByText('Could not load artifacts. Check your connection and try again.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Try again').length).toBeGreaterThan(0);
  });

  it('renders EmptyDBState when success with empty rows and no filters', () => {
    mockQuery.status = 'success';
    mockQuery.data = { pages: [{ rows: [], count: 0 }] };
    renderWithToast(<ArtifactTable />);
    // A-01: copy updated to match UI-SPEC §Copywriting Contract
    expect(screen.getAllByText('No artifacts yet').length).toBeGreaterThan(0);
    expect(
      screen.getAllByText('Billing artifacts will appear here after the next CI run completes.').length
    ).toBeGreaterThan(0);
  });

  it('renders row data when one row is returned', () => {
    mockQuery.status = 'success';
    mockQuery.data = { pages: [{ rows: [SAMPLE_ROW], count: 1 }] };
    renderWithToast(<ArtifactTable />);
    // UI-01: responsive swap renders WR# in BOTH the desktop table (ArtifactTableRow)
    // and the mobile card list (ArtifactCard) — getAllByText handles both matches.
    expect(screen.getAllByText('WR-90001').length).toBeGreaterThanOrEqual(1);
    // Download button present (column header + button both say "Download")
    expect(screen.getAllByText('Download').length).toBeGreaterThan(0);
  });
});
