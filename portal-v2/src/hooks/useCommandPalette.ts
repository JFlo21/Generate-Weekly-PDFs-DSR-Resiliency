import { useCallback, useEffect, useState } from 'react';

/**
 * Global Cmd+K / Ctrl+K hotkey binding + open/close state.
 * Lives at the DashboardLayout level so the palette is available from every
 * dashboard route.
 */
export function useCommandPalette() {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => setOpen((v) => !v), []);
  const close = useCallback(() => setOpen(false), []);
  const openPalette = useCallback(() => setOpen(true), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const isModifier = e.metaKey || e.ctrlKey;
      if (isModifier && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
      // Escape is handled inside CommandPalette's own onKeyDown so that
      // we don't accidentally swallow Escape events meant for other modals
      // (like ArtifactExplorer) when the palette isn't even open.
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return { open, toggle, close, openPalette };
}
