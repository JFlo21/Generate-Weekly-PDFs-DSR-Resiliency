import { describe, it, expect } from 'vitest';
import { normalizeSearchTerm, sanitizeSearchTerm } from '../searchNormalize';

describe('normalizeSearchTerm', () => {
  it('passes through MMDDYY unchanged', () => {
    expect(normalizeSearchTerm('052625')).toBe('052625');
  });

  it('strips slashes from MM/DD/YY', () => {
    expect(normalizeSearchTerm('05/26/25')).toBe('052625');
  });

  it('converts ISO date YYYY-MM-DD to MMDDYY', () => {
    expect(normalizeSearchTerm('2025-05-26')).toBe('052625');
  });

  it('leaves WR# substring intact', () => {
    expect(normalizeSearchTerm('123')).toBe('123');
  });
});

describe('sanitizeSearchTerm', () => {
  it('strips percent sign', () => {
    expect(sanitizeSearchTerm('100%')).toBe('100');
  });

  it('strips comma, parens', () => {
    expect(sanitizeSearchTerm('a,b(c)')).toBe('abc');
  });

  it('trims whitespace and preserves underscores', () => {
    expect(sanitizeSearchTerm('  WR_123 ')).toBe('WR_123');
  });

  it('strips single quote so an apostrophe name cannot break .or() (CR-02)', () => {
    expect(sanitizeSearchTerm("O'Brien")).toBe('OBrien');
  });

  it('strips double-quote and ilike wildcard', () => {
    expect(sanitizeSearchTerm('"WR*123"')).toBe('WR123');
  });
});
