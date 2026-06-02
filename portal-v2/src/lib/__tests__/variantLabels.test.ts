import { describe, it, expect } from 'vitest';
import { getVariantLabel } from '../variantLabels';

describe('getVariantLabel', () => {
  it("returns 'Primary' for empty string variant", () => {
    expect(getVariantLabel('')).toBe('Primary');
  });

  it("returns 'Helper' for 'helper'", () => {
    expect(getVariantLabel('helper')).toBe('Helper');
  });

  it("returns 'VAC Crew' for 'vac_crew'", () => {
    expect(getVariantLabel('vac_crew')).toBe('VAC Crew');
  });

  it("returns 'AEP Billable (Sub)' for '_AEPBillable'", () => {
    expect(getVariantLabel('_AEPBillable')).toBe('AEP Billable (Sub)');
  });

  it("returns 'Reduced Sub' for '_ReducedSub'", () => {
    expect(getVariantLabel('_ReducedSub')).toBe('Reduced Sub');
  });

  it("returns 'AEP Billable · Helper' for '_AEPBillable_Helper_jsmith'", () => {
    expect(getVariantLabel('_AEPBillable_Helper_jsmith')).toBe('AEP Billable · Helper');
  });

  it('de-prefixes and humanizes unknown variants', () => {
    expect(getVariantLabel('_SomethingNew')).toBe('SomethingNew');
  });
});
