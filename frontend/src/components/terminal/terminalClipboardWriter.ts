interface TerminalClipboardWrite {
  text: string;
  isCurrent: () => boolean;
  onResult: (copied: boolean) => void;
}

let writing = false;
let pending: TerminalClipboardWrite | null = null;

export function isTerminalClipboardWritePending(): boolean {
  return writing;
}

export function queueTerminalClipboardWrite(request: TerminalClipboardWrite): void {
  pending = request;
  if (writing) return;
  writing = true;
  void drain();
}

/**
 * Universal clipboard writer supporting modern Clipboard API (HTTPS)
 * and execCommand('copy') fallback for HTTP / IP origins.
 */
export async function writeToClipboard(text: string): Promise<boolean> {
  if (!text) return false;

  // 1. Try modern async Clipboard API (HTTPS / secure contexts)
  if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fallback below
    }
  }

  // 2. Fallback for HTTP / non-secure contexts: textarea + document.execCommand('copy')
  if (typeof document !== 'undefined') {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.top = '-9999px';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      textarea.setSelectionRange(0, text.length);
      const successful = document.execCommand('copy');
      document.body.removeChild(textarea);
      if (successful) return true;
    } catch (e) {
      console.debug('execCommand copy fallback failed:', e);
    }
  }

  return false;
}

/**
 * Universal clipboard reader.
 */
export async function readFromClipboard(): Promise<string> {
  if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.readText) {
    try {
      return await navigator.clipboard.readText();
    } catch {
      // Fallback
    }
  }
  return '';
}

async function drain(): Promise<void> {
  try {
    while (pending !== null) {
      const request = pending;
      pending = null;
      if (!request.isCurrent()) continue;
      const copied = await writeToClipboard(request.text);
      if (request.isCurrent()) request.onResult(copied);
    }
  } finally {
    writing = false;
  }
}
