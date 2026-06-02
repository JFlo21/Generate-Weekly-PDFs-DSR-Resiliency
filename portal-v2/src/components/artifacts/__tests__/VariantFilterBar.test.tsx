import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VariantFilterBar } from '../VariantFilterBar';

const OPTIONS = ['', 'helper', '_AEPBillable'];

describe('VariantFilterBar', () => {
  it('renders friendly labels for all options', () => {
    render(
      <VariantFilterBar options={OPTIONS} selected={[]} onChange={vi.fn()} />
    );
    // getVariantLabel('') = 'Primary'
    expect(screen.getByText('Primary')).toBeTruthy();
    // getVariantLabel('helper') = 'Helper'
    expect(screen.getByText('Helper')).toBeTruthy();
    // getVariantLabel('_AEPBillable') = 'AEP Billable (Sub)'
    expect(screen.getByText('AEP Billable (Sub)')).toBeTruthy();
  });

  it('calls onChange with variant added when an unselected option is clicked', () => {
    const onChange = vi.fn();
    render(
      <VariantFilterBar options={OPTIONS} selected={[]} onChange={onChange} />
    );
    fireEvent.click(screen.getByText('Helper'));
    expect(onChange).toHaveBeenCalledWith(['helper']);
  });

  it('calls onChange with variant removed when a selected chip X is clicked', () => {
    const onChange = vi.fn();
    render(
      <VariantFilterBar
        options={OPTIONS}
        selected={['helper']}
        onChange={onChange}
      />
    );
    // The X button has aria-label "Remove Helper filter"
    const removeBtn = screen.getByRole('button', { name: /remove helper filter/i });
    fireEvent.click(removeBtn);
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('calls onChange with empty array when Clear is clicked', () => {
    const onChange = vi.fn();
    render(
      <VariantFilterBar
        options={OPTIONS}
        selected={['helper', '']}
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByText('Clear'));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('shows Clear affordance when variants are selected', () => {
    render(
      <VariantFilterBar
        options={OPTIONS}
        selected={['helper']}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Clear')).toBeTruthy();
  });

  it('does not show Clear affordance when nothing is selected', () => {
    render(
      <VariantFilterBar options={OPTIONS} selected={[]} onChange={vi.fn()} />
    );
    expect(screen.queryByText('Clear')).toBeNull();
  });
});
