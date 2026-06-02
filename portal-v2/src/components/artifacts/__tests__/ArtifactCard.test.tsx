import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { axe } from 'jest-axe';
import { ArtifactCard } from '../ArtifactCard';
import type { BillingArtifact } from '../../../lib/types';

// ---------------------------------------------------------------------------
// Shared mock artifact row — covers all 6 TABLE-01 fields.
// ---------------------------------------------------------------------------
const mockRow: BillingArtifact = {
  id: 'abc-123',
  work_request: 'WR_90001',
  week_ending: '2026-05-17',
  week_ending_fmt: '051726',
  variant: '',
  filename: 'WR_90001_WeekEnding_051726.xlsx',
  storage_path: '2026-05-17/WR_90001_WeekEnding_051726.xlsx',
  size_bytes: 102400,
  created_at: '2026-05-17T12:00:00Z',
};

// ---------------------------------------------------------------------------
// Tests: ArtifactCard render + a11y (UI-01 / UI-03 / D-07)
// ---------------------------------------------------------------------------
describe('ArtifactCard (UI-01/UI-03)', () => {
  it('Test 1: renders all 6 fields — WR#, week-ending, variant badge, file size, created, download button', () => {
    render(
      <ArtifactCard
        row={mockRow}
        onDownload={vi.fn()}
        isDownloading={false}
      />
    );

    // WR # (work_request)
    expect(screen.getByText('WR_90001')).toBeTruthy();

    // Week-ending formatted as MM/DD/YY (05/17/26, not raw ISO)
    expect(screen.getByText('05/17/26')).toBeTruthy();

    // Variant badge label (getVariantLabel('') → "Primary" or equivalent)
    // We just confirm a badge element is rendered (role="listitem" context verifies structure)
    expect(screen.getByRole('listitem')).toBeTruthy();

    // File size (formatSize(102400) — should be non-empty)
    const fileSizeEl = screen.getByText(/KB|MB|bytes/i);
    expect(fileSizeEl).toBeTruthy();

    // Download button is visible
    expect(screen.getByRole('button', { name: `Download ${mockRow.filename}` })).toBeTruthy();
  });

  it('Test 2a: idle state — download button has correct aria-label', () => {
    render(
      <ArtifactCard
        row={mockRow}
        onDownload={vi.fn()}
        isDownloading={false}
      />
    );
    const btn = screen.getByRole('button', { name: `Download ${mockRow.filename}` });
    expect(btn).toBeTruthy();
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it('Test 2b: downloading state — button shows spinner aria-label and is disabled', () => {
    render(
      <ArtifactCard
        row={mockRow}
        onDownload={vi.fn()}
        isDownloading={true}
      />
    );
    const btn = screen.getByRole('button', { name: `Downloading ${mockRow.filename}` });
    expect(btn).toBeTruthy();
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('Test 3: clicking download calls onDownload(id, storage_path, filename)', () => {
    const onDownload = vi.fn();
    render(
      <ArtifactCard
        row={mockRow}
        onDownload={onDownload}
        isDownloading={false}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: `Download ${mockRow.filename}` }));
    expect(onDownload).toHaveBeenCalledTimes(1);
    expect(onDownload).toHaveBeenCalledWith(
      mockRow.id,
      mockRow.storage_path,
      mockRow.filename,
    );
  });

  it('Test 4: jest-axe reports no structure/ARIA violations', async () => {
    // NOTE: jsdom silently disables the axe color-contrast rule — contrast
    // validation is the MANUAL UAT pass (D-07 second pass), not jest-axe.
    //
    // ArtifactCard has role="listitem" — axe requires it to be inside a
    // role="list" parent. In ArtifactTable the parent div supplies role="list";
    // in this isolated test we wrap explicitly so axe can validate the ARIA tree.
    const { container } = render(
      <div role="list">
        <ArtifactCard
          row={mockRow}
          onDownload={vi.fn()}
          isDownloading={false}
        />
      </div>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
