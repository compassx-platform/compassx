export type TerminalClipboardPreference = 'ask' | 'allow' | 'block';

const STORAGE_PREFIX = 'compassx:terminal-clipboard:v1';
const CHANGE_EVENT = 'compassx:terminal-clipboard-change';

export function canRememberTerminalClipboardPreference(): boolean {
  return typeof window !== 'undefined';
}

export function readTerminalClipboardPreference(): TerminalClipboardPreference {
  if (typeof window === 'undefined') return 'ask';
  try {
    const value = window.localStorage.getItem(STORAGE_PREFIX);
    return value === 'ask' || value === 'allow' || value === 'block' ? value : 'ask';
  } catch {
    return 'ask';
  }
}

export function writeTerminalClipboardPreference(value: TerminalClipboardPreference): boolean {
  if (typeof window === 'undefined') return false;
  try {
    if (value === 'ask') window.localStorage.removeItem(STORAGE_PREFIX);
    else window.localStorage.setItem(STORAGE_PREFIX, value);
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: value }));
    return true;
  } catch {
    return false;
  }
}

export function subscribeTerminalClipboardPreference(
  listener: (value: TerminalClipboardPreference) => void,
): () => void {
  if (typeof window === 'undefined') return () => {};

  const onChange = (event: Event) => {
    listener(readTerminalClipboardPreference());
  };
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}
