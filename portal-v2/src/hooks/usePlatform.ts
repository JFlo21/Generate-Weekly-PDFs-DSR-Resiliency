import { useEffect, useState } from 'react';
import { isMacPlatform } from '../lib/platform';

/**
 * Reactively reports whether the client is an Apple (macOS/iOS) platform.
 *
 * Starts `false` (SSR-safe / pre-mount) and resolves after mount, mirroring the
 * detection that used to live inline in Navbar. Used to pick the correct
 * command-palette modifier glyph (⌘ vs Ctrl).
 */
export function useIsMac(): boolean {
  const [isMac, setIsMac] = useState(false);
  useEffect(() => {
    if (typeof navigator !== 'undefined') setIsMac(isMacPlatform(navigator));
  }, []);
  return isMac;
}
