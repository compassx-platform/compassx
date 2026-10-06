import type { ITheme } from 'xterm';

const STORAGE_KEY = 'compassx:terminal-theme';

export const terminalThemeModes = ['auto', 'light', 'dark'] as const;
export type TerminalThemeMode = (typeof terminalThemeModes)[number];
export const TERMINAL_THEME_DEFAULT: TerminalThemeMode = 'auto';

const subscribers = new Set<(mode: TerminalThemeMode) => void>();

export function isTerminalThemeMode(value: string | null | undefined): value is TerminalThemeMode {
  return value === 'auto' || value === 'light' || value === 'dark';
}

export function normalizeTerminalThemeMode(value: string | null | undefined): TerminalThemeMode {
  return isTerminalThemeMode(value) ? value : TERMINAL_THEME_DEFAULT;
}

export function readTerminalThemeMode(): TerminalThemeMode {
  if (typeof window === 'undefined') return TERMINAL_THEME_DEFAULT;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return TERMINAL_THEME_DEFAULT;
    return normalizeTerminalThemeMode(raw);
  } catch {
    return TERMINAL_THEME_DEFAULT;
  }
}

export function writeTerminalThemeMode(mode: TerminalThemeMode): void {
  const normalized = normalizeTerminalThemeMode(mode);
  if (typeof window !== 'undefined') {
    try {
      if (normalized === TERMINAL_THEME_DEFAULT) {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, normalized);
      }
    } catch {
      /* ignore storage errors */
    }
  }
  for (const listener of subscribers) {
    listener(normalized);
  }
}

export function subscribeTerminalTheme(listener: (mode: TerminalThemeMode) => void): () => void {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
}

export function resolveTerminalIsDark(mode: TerminalThemeMode, appIsDark: boolean): boolean {
  if (mode === 'dark') return true;
  if (mode === 'light') return false;
  return appIsDark;
}

// Card background colors matching Omnigent palette
const CARD_LIGHT = '#ffffff';
const CARD_DARK = '#000000';

export function terminalTheme(isDark: boolean): ITheme {
  const bg = isDark ? CARD_DARK : CARD_LIGHT;
  return isDark
    ? {
        background: bg,
        foreground: '#e4e4e7',
        cursor: '#22d3ee',
        cursorAccent: bg,
        selectionBackground: '#22d3ee33',
        black: '#09090b',
        brightBlack: '#71717a',
        red: '#f87171',
        brightRed: '#ef4444',
        green: '#4ade80',
        brightGreen: '#22c55e',
        yellow: '#facc15',
        brightYellow: '#eab308',
        blue: '#60a5fa',
        brightBlue: '#3b82f6',
        magenta: '#c084fc',
        brightMagenta: '#a855f7',
        cyan: '#22d3ee',
        brightCyan: '#06b6d4',
        white: '#e4e4e7',
        brightWhite: '#ffffff',
      }
    : {
        background: bg,
        foreground: '#18181b',
        cursor: '#0891b2',
        cursorAccent: bg,
        selectionBackground: '#0891b233',
        black: '#18181b',
        brightBlack: '#71717a',
        red: '#dc2626',
        brightRed: '#b91c1c',
        green: '#16a34a',
        brightGreen: '#15803d',
        yellow: '#ca8a04',
        brightYellow: '#a16207',
        blue: '#2563eb',
        brightBlue: '#1d4ed8',
        magenta: '#9333ea',
        brightMagenta: '#7e22ce',
        cyan: '#0891b2',
        brightCyan: '#0e7490',
        white: '#3f3f46',
        brightWhite: '#18181b',
      };
}
