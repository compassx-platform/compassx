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

async function drain(): Promise<void> {
  try {
    while (pending !== null) {
      const request = pending;
      pending = null;
      if (!request.isCurrent()) continue;
      let copied = false;
      try {
        if (navigator?.clipboard?.writeText) {
          await navigator.clipboard.writeText(request.text);
          copied = true;
        }
      } catch {
        /* User/browser denied permission */
      }
      if (request.isCurrent()) request.onResult(copied);
    }
  } finally {
    writing = false;
  }
}
