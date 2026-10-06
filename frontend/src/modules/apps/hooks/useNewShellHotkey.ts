// ⌘⌥T (Ctrl+Alt+T on Win/Linux) opens a new shell in the workspace rail,
// matching Omnigent's interactive shell hotkey pattern.
import { useEffect, useRef } from 'react';

/** Editor/terminal surfaces that own their own keystrokes; the chord defers. */
const TEXT_ENTRY_SURFACE = '.monaco-editor, .xterm';

function isMacPlatform(): boolean {
  if (typeof navigator === 'undefined') return false;
  const uaData = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData;
  const platform = uaData?.platform ?? navigator.platform ?? navigator.userAgent ?? '';
  return /Mac|iPhone|iPad|iPod/i.test(platform);
}

/** True for Cmd+Alt+T on Apple platforms or Ctrl+Alt+T elsewhere. */
export function isNewShellHotkey(e: globalThis.KeyboardEvent, isMac = isMacPlatform()): boolean {
  const platformModifier = isMac ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
  if (!platformModifier || !e.altKey || e.shiftKey) return false;
  // AltGr reports as Ctrl+Alt on Windows/Linux, so an ordinary AltGr+T
  // keystroke on an international layout would otherwise match this chord. Bail.
  if (typeof e.getModifierState === 'function' && e.getModifierState('AltGraph')) return false;
  // Match the physical key: Alt remaps character on many layouts.
  return e.code === 'KeyT';
}

/**
 * Bind ⌘/Ctrl+Alt+T to open a new shell session.
 *
 * The chord defers to a focused Monaco editor or xterm terminal — those
 * surfaces own their keystrokes, and stealing the chord mid-edit would surprise
 * the user. It fires only when ``enabled`` (the sandbox is running).
 *
 * @param onLaunch Open the shell session
 * @param enabled  Pass ``false`` to disable (e.g. when container is stopped).
 */
export function useNewShellHotkey(
  onLaunch: () => void,
  enabled = true,
  isMac = isMacPlatform(),
): void {
  const latest = useRef(onLaunch);
  latest.current = onLaunch;

  useEffect(() => {
    if (!enabled) return;
    const handler = (e: globalThis.KeyboardEvent): void => {
      // Ignore auto-repeat: holding the chord would spawn a shell per tick.
      if (e.repeat || !isNewShellHotkey(e, isMac)) return;
      // Leave the chord to a focused editor/terminal that consumes keystrokes.
      const el = document.activeElement;
      if (el instanceof Element && el.closest(TEXT_ENTRY_SURFACE) !== null) return;
      e.preventDefault();
      e.stopPropagation();
      latest.current();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enabled, isMac]);
}
