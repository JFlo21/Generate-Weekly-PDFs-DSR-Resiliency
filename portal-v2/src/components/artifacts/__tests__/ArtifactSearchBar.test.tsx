import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ArtifactSearchBar } from '../ArtifactSearchBar';

describe('ArtifactSearchBar', () => {
  it('calls onChange with typed value', () => {
    const onChange = vi.fn();
    render(<ArtifactSearchBar value="" onChange={onChange} />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'WR-90001' } });
    expect(onChange).toHaveBeenCalledWith('WR-90001');
  });

  it('does not show clear button when value is empty', () => {
    render(<ArtifactSearchBar value="" onChange={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /clear search/i })).toBeNull();
  });

  it('shows clear button when value is non-empty', () => {
    render(<ArtifactSearchBar value="90001" onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: /clear search/i })).toBeTruthy();
  });

  it('calls onChange with empty string when clear button is clicked', () => {
    const onChange = vi.fn();
    render(<ArtifactSearchBar value="90001" onChange={onChange} />);
    const clearBtn = screen.getByRole('button', { name: /clear search/i });
    fireEvent.click(clearBtn);
    expect(onChange).toHaveBeenCalledWith('');
  });
});
