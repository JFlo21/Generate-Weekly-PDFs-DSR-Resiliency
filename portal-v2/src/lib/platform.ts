// Platform detection for keyboard-shortcut hints.
//
// Centralizes the macOS/iOS sniff that was previously inlined in Navbar so the
// command-palette (Cmd/Ctrl+K) hint renders consistently across Navbar,
// Sidebar, and the dashboard empty state. The hotkey binding itself
// (useCommandPalette) handles `metaKey || ctrlKey` regardless of platform —
// this only controls the *label* shown to the user.

/**
 * Best-effort Apple-platform detection from a navigator-like object.
 * `navigator.platform` is deprecated but still the most reliable signal; we
 * fall back to the user-agent string when it is empty. Accepts an injected
 * navigator so the logic is pure and unit-testable.
 */
export function isMacPlatform(
  nav: Pick<Navigator, 'platform' | 'userAgent'> = navigator
): boolean {
  const probe = `${nav.platform ?? ''} ${nav.userAgent ?? ''}`;
  return /Mac|iPhone|iPad|iPod/i.test(probe);
}

/** Command-palette modifier hint: "⌘K" on Apple platforms, "Ctrl K" elsewhere. */
export function commandPaletteHint(isMac: boolean): string {
  return isMac ? '⌘K' : 'Ctrl K';
}
