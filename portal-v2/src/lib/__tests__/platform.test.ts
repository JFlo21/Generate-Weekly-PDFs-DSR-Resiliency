import { describe, it, expect } from 'vitest';
import { isMacPlatform, commandPaletteHint } from '../platform';

describe('isMacPlatform', () => {
  it('detects macOS via navigator.platform', () => {
    expect(isMacPlatform({ platform: 'MacIntel', userAgent: '' })).toBe(true);
  });

  it('detects iPhone / iPad / iPod', () => {
    expect(isMacPlatform({ platform: 'iPhone', userAgent: '' })).toBe(true);
    expect(isMacPlatform({ platform: 'iPad', userAgent: '' })).toBe(true);
    expect(
      isMacPlatform({ platform: '', userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)' })
    ).toBe(true);
  });

  it('falls back to userAgent when platform is empty', () => {
    expect(
      isMacPlatform({ platform: '', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' })
    ).toBe(true);
  });

  it('returns false on Windows', () => {
    expect(
      isMacPlatform({ platform: 'Win32', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' })
    ).toBe(false);
  });

  it('returns false on Linux', () => {
    expect(
      isMacPlatform({ platform: 'Linux x86_64', userAgent: 'Mozilla/5.0 (X11; Linux x86_64)' })
    ).toBe(false);
  });
});

describe('commandPaletteHint', () => {
  it('shows the Command glyph on Apple platforms', () => {
    expect(commandPaletteHint(true)).toBe('⌘K');
  });

  it('shows Ctrl on everything else', () => {
    expect(commandPaletteHint(false)).toBe('Ctrl K');
  });
});
