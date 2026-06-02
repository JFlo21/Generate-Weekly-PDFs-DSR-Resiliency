import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { axe } from 'jest-axe';
import { NewArtifactPill } from '../NewArtifactPill';

// ---------------------------------------------------------------------------
// Tests: NewArtifactPill render + a11y (UI-02 / UI-03 / D-07)
// ---------------------------------------------------------------------------
describe('NewArtifactPill (UI-02/UI-03)', () => {
  it('Test 1: renders nothing when count=0', () => {
    const { container } = render(
      <NewArtifactPill count={0} onLoad={vi.fn()} onDismiss={vi.fn()} />
    );
    // No load button should be present
    expect(screen.queryByRole('button')).toBeNull();
    expect(container.firstChild).toBeNull();
  });

  it('Test 2a: renders "Load 1 new artifact" for count=1', () => {
    render(
      <NewArtifactPill count={1} onLoad={vi.fn()} onDismiss={vi.fn()} />
    );
    expect(screen.getByText('Load 1 new artifact')).toBeTruthy();
  });

  it('Test 2b: renders "Load 3 new artifacts" for count=3', () => {
    render(
      <NewArtifactPill count={3} onLoad={vi.fn()} onDismiss={vi.fn()} />
    );
    expect(screen.getByText('Load 3 new artifacts')).toBeTruthy();
  });

  it('Test 3a: clicking load button calls onLoad', () => {
    const onLoad = vi.fn();
    render(
      <NewArtifactPill count={2} onLoad={onLoad} onDismiss={vi.fn()} />
    );
    // The load button text matches the label
    fireEvent.click(screen.getByText('Load 2 new artifacts'));
    expect(onLoad).toHaveBeenCalledTimes(1);
  });

  it('Test 3b: clicking dismiss button (aria-label) calls onDismiss', () => {
    const onDismiss = vi.fn();
    render(
      <NewArtifactPill count={2} onLoad={vi.fn()} onDismiss={onDismiss} />
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Dismiss new artifact notification' })
    );
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('Test 4: jest-axe reports no structure/ARIA violations', async () => {
    // NOTE: jsdom silently disables the axe color-contrast rule — contrast
    // validation is the MANUAL UAT pass (D-07 second pass), not jest-axe.
    const { container } = render(
      <NewArtifactPill count={1} onLoad={vi.fn()} onDismiss={vi.fn()} />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
