// Pure-JS session bridging xterm.js to an agent's terminal WebSocket.
// Copied and adapted directly from Omnigent's battle-tested TerminalSession.ts.
//
// Wire protocol:
//   - Server → client: binary pane output → term.write; text frames for
//     JSON control messages or text streams.
//   - Client → server: binary frames for keystrokes (term.onData);
//     text frames for JSON control messages (e.g. resize).

import { FitAddon } from '@xterm/addon-fit';
import { type FontWeight, type ITheme, Terminal } from 'xterm';
import 'xterm/css/xterm.css';
import { type CodeFont, codeFontFamilyForEditor, readCodeFont } from './codeFontPreferences';
import { CodexTerminalPalette, codexTerminalTheme } from './CodexTerminalPalette';
import { terminalTheme } from './terminalThemePreferences';

const TERMINAL_BOLD_WEIGHT_OFFSET = 300;

function terminalFontOptions({ sizePx, family, weight }: CodeFont) {
  return {
    fontFamily: codeFontFamilyForEditor(family),
    fontSize: sizePx,
    fontWeight: weight as FontWeight,
    fontWeightBold: (weight + TERMINAL_BOLD_WEIGHT_OFFSET) as FontWeight,
  };
}

export const WS_CLOSE_WRONG_REPLICA = 4400;

export type TerminalFileLinkListener = (uri: string) => boolean;

export function openTerminalLink(
  event: MouseEvent,
  uri: string,
  onFileLink?: TerminalFileLinkListener,
): void {
  event.preventDefault();
  if (onFileLink?.(uri)) return;
  try {
    const url = new URL(uri, window.location.href);
    if (url.protocol === 'http:' || url.protocol === 'https:') {
      window.open(uri, '_blank', 'noopener,noreferrer');
    }
  } catch {
    /* ignore invalid urls */
  }
}

export type ConnectionState =
  | { kind: 'connecting' }
  | { kind: 'connected' }
  | { kind: 'closed'; reason: string; code: number }
  | { kind: 'error' };

export function isUnexpectedTerminalClose(code: number): boolean {
  return (
    code === 1001 ||
    code === 1005 ||
    code === 1006 ||
    code === 1011 ||
    code === 1012 ||
    code === 1013 ||
    code === 1014
  );
}

export type ConnectionStateListener = (state: ConnectionState) => void;
export type TerminalActivityListener = () => void;
export type TerminalInputListener = () => void;

/** Kitty Keyboard Protocol / CSI-u encoding for Shift+Enter. */
export const SHIFT_ENTER_CSI_U = '\x1b[13;2u';

/** Readline line-editing bytes for macOS Cmd key mappings. */
export const CMD_BACKSPACE_LINE_KILL = '\x15'; // Ctrl-U
export const CMD_LEFT_LINE_START = '\x01'; // Ctrl-A
export const CMD_RIGHT_LINE_END = '\x05'; // Ctrl-E

export function terminalKeyEventPayload(event: KeyboardEvent): string | null {
  if (event.isComposing || event.keyCode === 229) {
    return null;
  }
  if (
    event.key === 'Enter' &&
    event.shiftKey &&
    !event.altKey &&
    !event.ctrlKey &&
    !event.metaKey
  ) {
    return SHIFT_ENTER_CSI_U;
  }
  if (event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey) {
    if (event.key === 'Backspace') return CMD_BACKSPACE_LINE_KILL;
    if (event.key === 'ArrowLeft') return CMD_LEFT_LINE_START;
    if (event.key === 'ArrowRight') return CMD_RIGHT_LINE_END;
  }
  return null;
}

const INPUT_ENCODER = new TextEncoder();

interface TerminalCore {
  _core?: {
    coreMouseService?: { activeEncoding?: string };
  };
}

export function applyTerminalCopy(
  event: Pick<ClipboardEvent, 'clipboardData' | 'preventDefault'>,
  selection: string,
): boolean {
  if (!selection) return false;
  event.clipboardData?.setData('text/plain', selection);
  event.preventDefault();
  return true;
}

export const TERMINAL_CLIPBOARD_MAX_BYTES = 1024 * 1024;
export const TERMINAL_CLIPBOARD_INPUT_WINDOW_MS = 5000;

const STRICT_BASE64_RE = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;

export function decodeTerminalClipboardBase64(encoded: string): string | null {
  if (
    encoded.length === 0 ||
    encoded.length > Math.ceil(TERMINAL_CLIPBOARD_MAX_BYTES / 3) * 4 ||
    encoded.length % 4 !== 0 ||
    !STRICT_BASE64_RE.test(encoded)
  ) {
    return null;
  }
  let binary: string;
  try {
    binary = atob(encoded);
  } catch {
    return null;
  }
  if (binary.length === 0 || binary.length > TERMINAL_CLIPBOARD_MAX_BYTES) return null;
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function parseTerminalClipboardMessage(message: string): string | null {
  let value: unknown;
  try {
    value = JSON.parse(message);
  } catch {
    return null;
  }
  if (
    typeof value !== 'object' ||
    value === null ||
    (value as { type?: unknown }).type !== 'clipboard-write' ||
    (value as { encoding?: unknown }).encoding !== 'base64' ||
    typeof (value as { data?: unknown }).data !== 'string'
  ) {
    return null;
  }
  return decodeTerminalClipboardBase64((value as { data: string }).data);
}

export function hadRecentTerminalInput(lastInputAt: number, now: number): boolean {
  return (
    lastInputAt > 0 && now >= lastInputAt && now - lastInputAt <= TERMINAL_CLIPBOARD_INPUT_WINDOW_MS
  );
}

export type TerminalClipboardListener = (text: string, copyEvent?: ClipboardEvent) => void;

export const WHEEL_REPORTS_MAX_PER_EVENT = 50;

export interface WheelMouseState {
  mouseTrackingMode: 'none' | 'x10' | 'vt200' | 'drag' | 'any';
  sgrEncoding: boolean;
}

export interface WheelScreenMetrics {
  left: number;
  top: number;
  cellWidth: number;
  cellHeight: number;
  cols: number;
  rows: number;
}

export function sgrWheelReports(lines: number, col: number, row: number): string {
  if (lines === 0) return '';
  const button = lines < 0 ? 64 : 65;
  return `\x1b[<${button};${col};${row}M`.repeat(Math.abs(lines));
}

export function wheelReportPayload(
  event: Pick<WheelEvent, 'deltaY' | 'deltaMode' | 'shiftKey' | 'clientX' | 'clientY'>,
  mouse: WheelMouseState,
  screen: WheelScreenMetrics | null,
  partial: number,
): { consume: boolean; data: string; partial: number } {
  if (mouse.mouseTrackingMode === 'none' || !mouse.sgrEncoding) {
    return { consume: false, data: '', partial: 0 };
  }
  if (event.shiftKey || event.deltaY === 0 || screen === null) {
    return { consume: false, data: '', partial };
  }
  let lines: number;
  switch (event.deltaMode) {
    case WheelEvent.DOM_DELTA_LINE:
      lines = event.deltaY;
      break;
    case WheelEvent.DOM_DELTA_PAGE:
      lines = event.deltaY * screen.rows;
      break;
    default:
      lines = event.deltaY / screen.cellHeight;
  }
  const total = partial + lines;
  const whole = Math.trunc(total);
  const capped = Math.max(
    -WHEEL_REPORTS_MAX_PER_EVENT,
    Math.min(WHEEL_REPORTS_MAX_PER_EVENT, whole),
  );
  const clamp = (v: number, max: number) => Math.min(Math.max(v, 1), max);
  const col = clamp(Math.floor((event.clientX - screen.left) / screen.cellWidth) + 1, screen.cols);
  const row = clamp(Math.floor((event.clientY - screen.top) / screen.cellHeight) + 1, screen.rows);
  return {
    consume: true,
    data: sgrWheelReports(capped, col, row),
    partial: capped === whole ? total - whole : 0,
  };
}

export const TOUCH_SCROLL_SLOP_PX = 8;

export function touchScrollPayload(
  move: { previousY: number; currentY: number; clientX: number },
  mouse: WheelMouseState,
  screen: WheelScreenMetrics | null,
  partial: number,
): { consume: boolean; lines: number; data: string; partial: number } {
  if (screen === null || screen.cellHeight <= 0) {
    return { consume: false, lines: 0, data: '', partial };
  }
  const total = partial + (move.previousY - move.currentY) / screen.cellHeight;
  const whole = Math.trunc(total);
  if (mouse.mouseTrackingMode === 'none' || !mouse.sgrEncoding) {
    return { consume: true, lines: whole, data: '', partial: total - whole };
  }
  const capped = Math.max(
    -WHEEL_REPORTS_MAX_PER_EVENT,
    Math.min(WHEEL_REPORTS_MAX_PER_EVENT, whole),
  );
  const clamp = (v: number, max: number) => Math.min(Math.max(v, 1), max);
  const col = clamp(Math.floor((move.clientX - screen.left) / screen.cellWidth) + 1, screen.cols);
  const row = clamp(Math.floor((move.currentY - screen.top) / screen.cellHeight) + 1, screen.rows);
  return {
    consume: true,
    lines: 0,
    data: sgrWheelReports(capped, col, row),
    partial: capped === whole ? total - whole : 0,
  };
}

export const RECONNECT_BACKOFF_MS = [
  500, 1000, 2000, 4000, 8000, 15000,
  30000, 30000, 30000, 30000, 30000, 30000,
] as const;

export const RECONNECT_STABLE_MS = 30_000;

export class TerminalSession {
  private readonly term: Terminal;
  private readonly fit: FitAddon;
  private readonly ws: WebSocket;
  private readonly listenerCtl: AbortController;
  private readonly resizeObserver: ResizeObserver;
  private readonly dataDispose: { dispose: () => void };
  private readonly selectionDispose: { dispose: () => void };
  private readonly osc52Dispose: { dispose: () => void };
  private readonly codexPalette: CodexTerminalPalette | null;
  private readonly onClipboardRequest?: TerminalClipboardListener;
  private clipboardEnabled: boolean;
  private focusOnConnect: boolean;
  private lastUserInputAt = 0;
  private disposed = false;
  private lastSentSize: { cols: number; rows: number } | null = null;
  private wheelPartialLines = 0;
  private touchStart: { x: number; y: number } | null = null;
  private touchScrolling = false;
  private touchLastY = 0;
  private touchPartialLines = 0;

  constructor(
    container: HTMLElement,
    url: string,
    onState: ConnectionStateListener,
    isDark = true,
    onActivity?: TerminalActivityListener,
    onInput?: TerminalInputListener,
    clipboardEnabled = true,
    onClipboardRequest?: TerminalClipboardListener,
    focusOnConnect = true,
    adaptCodexPalette = false,
    onFileLink?: TerminalFileLinkListener,
  ) {
    this.codexPalette = adaptCodexPalette ? new CodexTerminalPalette() : null;
    this.clipboardEnabled = clipboardEnabled;
    this.focusOnConnect = focusOnConnect;
    this.onClipboardRequest = onClipboardRequest;

    const activateLink = (event: MouseEvent, uri: string) =>
      openTerminalLink(event, uri, onFileLink);

    this.term = new Terminal({
      ...terminalFontOptions(readCodeFont()),
      scrollback: 50000,
      cursorBlink: true,
      theme: this.theme(isDark),
      minimumContrastRatio: 4.5,
      allowProposedApi: true,
      linkHandler: { activate: activateLink, allowNonHttpProtocols: true },
    });

    this.osc52Dispose = this.term.parser.registerOscHandler(52, () => true);
    this.fit = new FitAddon();
    this.term.loadAddon(this.fit);
    this.term.open(container);

    try {
      this.fit.fit();
    } catch {
      this.term.resize(80, 24);
    }

    // Auto-copy on highlight / mouse selection
    this.selectionDispose = this.term.onSelectionChange(() => {
      if (this.term.hasSelection()) {
        const selection = this.term.getSelection();
        if (selection && selection.length > 0) {
          if (navigator.clipboard) {
            navigator.clipboard.writeText(selection).catch(() => {});
          }
          this.onClipboardRequest?.(selection);
        }
      }
    });

    this.ws = new WebSocket(url);
    this.ws.binaryType = 'arraybuffer';

    this.listenerCtl = new AbortController();
    const { signal } = this.listenerCtl;

    container.addEventListener(
      'copy',
      (event) => {
        const selection = this.term.getSelection();
        if (!selection) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        this.onClipboardRequest?.(selection, event);
      },
      { capture: true, signal },
    );

    this.ws.addEventListener(
      'open',
      () => {
        this.sendResize();
        if (this.focusOnConnect) this.term.focus();
        onState({ kind: 'connected' });
      },
      { signal },
    );

    let lastActivityTs = 0;
    this.ws.addEventListener(
      'message',
      (ev) => {
        if (ev.data instanceof ArrayBuffer) {
          const bytes = new Uint8Array(ev.data);
          this.term.write(this.codexPalette?.write(bytes) ?? bytes);
          const now = performance.now();
          if (now - lastActivityTs > 300) {
            lastActivityTs = now;
            onActivity?.();
          }
        } else if (typeof ev.data === 'string') {
          const text = parseTerminalClipboardMessage(ev.data);
          if (text !== null) {
            this.requestClipboardWrite(text);
          } else {
            // Write direct text frames (supports banners, text chunks, etc.)
            this.term.write(ev.data);
            const now = performance.now();
            if (now - lastActivityTs > 300) {
              lastActivityTs = now;
              onActivity?.();
            }
          }
        }
      },
      { signal },
    );

    this.ws.addEventListener(
      'close',
      (ev) => {
        onState({ kind: 'closed', reason: ev.reason || `code ${ev.code}`, code: ev.code });
      },
      { signal },
    );

    this.ws.addEventListener(
      'error',
      () => {
        onState({ kind: 'error' });
      },
      { signal },
    );

    this.dataDispose = this.term.onData((d) => {
      onInput?.();
      this.lastUserInputAt = performance.now();
      if (this.ws.readyState !== WebSocket.OPEN) return;
      this.ws.send(INPUT_ENCODER.encode(d));
    });

    this.term.attachCustomKeyEventHandler((e) => {
      // Ctrl+C / Cmd+C / Ctrl+Shift+C: Copy when text is highlighted, without sending SIGINT (\x03)
      if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'c' || e.code === 'KeyC')) {
        if (this.term.hasSelection()) {
          if (e.type === 'keydown') {
            const selection = this.term.getSelection();
            if (selection) {
              if (navigator.clipboard) {
                navigator.clipboard.writeText(selection).catch(() => {});
              }
              this.onClipboardRequest?.(selection);
            }
          }
          return false; // Prevent sending \x03 to terminal process
        }
        return true; // No selection: allow standard Ctrl+C to send SIGINT
      }

      // Ctrl+V / Cmd+V / Ctrl+Shift+V: allow paste event
      if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'v' || e.code === 'KeyV')) {
        return true;
      }

      const payload = terminalKeyEventPayload(e);
      if (payload === null) return true;
      if (e.type === 'keydown') {
        e.preventDefault();
        onInput?.();
        this.lastUserInputAt = performance.now();
        if (this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(INPUT_ENCODER.encode(payload));
        }
      }
      return false;
    });

    const onWheel = (e: WheelEvent) => {
      const result = wheelReportPayload(
        e,
        {
          mouseTrackingMode: this.term.modes.mouseTrackingMode,
          sgrEncoding: this.sgrMouseEncodingActive(),
        },
        this.screenMetrics(),
        this.wheelPartialLines,
      );
      this.wheelPartialLines = result.partial;
      if (result.consume) {
        e.preventDefault();
        e.stopPropagation();
        if (result.data) {
          onInput?.();
          this.lastUserInputAt = performance.now();
          if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(INPUT_ENCODER.encode(result.data));
          }
        }
        return;
      }
      // If the active buffer is alternate (e.g. tmux or full-screen TUI) and mouse tracking
      // is not active, prevent xterm's default fallback of synthesizing Up/Down arrow keystrokes
      // which cycles prompt history into the message composer input line.
      if (this.term.buffer.active.type === 'alternate') {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    container.addEventListener('wheel', onWheel, { passive: false, capture: true, signal });

    container.addEventListener(
      'touchstart',
      (e) => {
        if (e.touches.length !== 1) {
          this.touchStart = null;
          this.touchScrolling = false;
          return;
        }
        this.touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        this.touchScrolling = false;
        this.touchPartialLines = 0;
      },
      { signal },
    );

    container.addEventListener(
      'touchmove',
      (e) => {
        if (this.touchStart === null || e.touches.length !== 1) return;
        const touch = e.touches[0];
        if (!this.touchScrolling) {
          const dx = Math.abs(touch.clientX - this.touchStart.x);
          const dy = Math.abs(touch.clientY - this.touchStart.y);
          if (Math.max(dx, dy) < TOUCH_SCROLL_SLOP_PX) return;
          if (dx > dy) {
            this.touchStart = null;
            return;
          }
          this.touchScrolling = true;
          this.touchLastY = this.touchStart.y;
        }
        const result = touchScrollPayload(
          { previousY: this.touchLastY, currentY: touch.clientY, clientX: touch.clientX },
          {
            mouseTrackingMode: this.term.modes.mouseTrackingMode,
            sgrEncoding: this.sgrMouseEncodingActive(),
          },
          this.screenMetrics(),
          this.touchPartialLines,
        );
        this.touchLastY = touch.clientY;
        this.touchPartialLines = result.partial;
        if (!result.consume) return;
        if (e.cancelable) e.preventDefault();
        if (result.data) {
          onInput?.();
          this.lastUserInputAt = performance.now();
          if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(INPUT_ENCODER.encode(result.data));
          }
        }
        if (result.lines !== 0) this.term.scrollLines(result.lines);
      },
      { passive: false, signal },
    );

    const endTouch = () => {
      this.touchStart = null;
      this.touchScrolling = false;
      this.touchPartialLines = 0;
    };
    container.addEventListener('touchend', endTouch, { signal });
    container.addEventListener('touchcancel', endTouch, { signal });

    this.resizeObserver = new ResizeObserver(() => this.sendResize());
    this.resizeObserver.observe(container);
  }

  setTheme(isDark: boolean): void {
    this.term.options.theme = this.theme(isDark);
  }

  private theme(isDark: boolean): ITheme {
    const theme = terminalTheme(isDark);
    return this.codexPalette ? codexTerminalTheme(theme, isDark) : theme;
  }

  setClipboardEnabled(enabled: boolean): void {
    this.clipboardEnabled = enabled;
  }

  focus(): void {
    this.term.focus();
  }

  clear(): void {
    this.term.clear();
  }

  write(data: string | Uint8Array): void {
    this.term.write(data);
  }

  sendInput(data: string): void {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(INPUT_ENCODER.encode(data));
    }
  }

  setFont(font: CodeFont): void {
    Object.assign(this.term.options, terminalFontOptions(font));
    this.sendResize();
  }

  getSelection(): string {
    return this.term.getSelection();
  }

  hasSelection(): boolean {
    return this.term.hasSelection();
  }

  selectAll(): void {
    this.term.selectAll();
  }

  clearSelection(): void {
    this.term.clearSelection();
  }

  paste(data: string): void {
    this.term.paste(data);
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.listenerCtl.abort();
    this.resizeObserver.disconnect();
    this.dataDispose.dispose();
    this.selectionDispose.dispose();
    this.osc52Dispose.dispose();
    try {
      this.ws.close();
    } catch {
      /* noop */
    }
    this.term.dispose();
  }

  private requestClipboardWrite(text: string): void {
    if (
      !this.clipboardEnabled ||
      !hadRecentTerminalInput(this.lastUserInputAt, performance.now())
    ) {
      return;
    }
    this.onClipboardRequest?.(text);
  }

  private sgrMouseEncodingActive(): boolean {
    const core = (this.term as unknown as TerminalCore)._core;
    return core?.coreMouseService?.activeEncoding === 'SGR';
  }

  private screenMetrics(): WheelScreenMetrics | null {
    const { cols, rows } = this.term;
    const rect = this.term.element?.querySelector('.xterm-screen')?.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0 || cols <= 0 || rows <= 0) return null;
    return {
      left: rect.left,
      top: rect.top,
      cellWidth: rect.width / cols,
      cellHeight: rect.height / rows,
      cols,
      rows,
    };
  }

  private sendResize(): void {
    if (this.ws.readyState !== WebSocket.OPEN) return;
    try {
      this.fit.fit();
    } catch {
      return;
    }
    const { cols, rows } = this.term;
    if (this.lastSentSize && this.lastSentSize.cols === cols && this.lastSentSize.rows === rows) {
      return;
    }
    this.lastSentSize = { cols, rows };
    this.ws.send(JSON.stringify({ type: 'resize', cols, rows }));
  }
}
