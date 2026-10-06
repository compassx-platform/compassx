// xterm.js view bridged to a dev container or agent over WebSocket.
// Copied and adapted directly from Omnigent's battle-tested TerminalView.tsx.

import { Loader2Icon, RefreshCwIcon } from 'lucide-react';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import {
  type ConnectionState,
  isUnexpectedTerminalClose,
  RECONNECT_BACKOFF_MS,
  RECONNECT_STABLE_MS,
  type TerminalActivityListener,
  type TerminalInputListener,
  TerminalSession,
} from './TerminalSession';
import {
  readTerminalThemeMode,
  resolveTerminalIsDark,
  subscribeTerminalTheme,
  terminalTheme,
  type TerminalThemeMode,
} from './terminalThemePreferences';

export interface TerminalViewHandle {
  focus: () => void;
  clear: () => void;
  sendInput: (data: string) => void;
  reconnect: () => void;
}

export interface TerminalViewProps {
  /** Explicit WebSocket URL to connect to */
  wsUrl: string;
  readOnly?: boolean;
  onStateChange?: (state: ConnectionState | null) => void;
  onActivity?: TerminalActivityListener;
  onInput?: TerminalInputListener;
  onResume?: () => void | Promise<void>;
  resumePending?: boolean;
  active?: boolean;
  focusOnConnect?: boolean;
  adaptCodexPalette?: boolean;
  className?: string;
  style?: React.CSSProperties;
  isDark?: boolean;
}

export const TerminalView = forwardRef<TerminalViewHandle, TerminalViewProps>(
  function TerminalView(
    {
      wsUrl,
      readOnly = false,
      onStateChange,
      onActivity,
      onInput,
      onResume,
      resumePending = false,
      active = true,
      focusOnConnect = active,
      adaptCodexPalette = false,
      className = '',
      style,
      isDark: isDarkProp,
    },
    ref,
  ) {
    const [state, setState] = useState<ConnectionState>({ kind: 'connecting' });
    const [connectAttempt, setConnectAttempt] = useState(0);
    const [resumeError, setResumeError] = useState<string | null>(null);
    const [reconnectPending, setReconnectPending] = useState(false);
    const reconnectAttemptsRef = useRef(0);
    const connectedAtRef = useRef<number | null>(null);

    const [terminalMode, setTerminalMode] = useState<TerminalThemeMode>(() =>
      readTerminalThemeMode(),
    );
    useEffect(() => subscribeTerminalTheme(setTerminalMode), []);

    // Resolve dark vs light mode (defaults to light mode if not configured)
    const isDark = isDarkProp !== undefined ? isDarkProp : resolveTerminalIsDark(terminalMode, false);
    const terminalBackground = terminalTheme(isDark).background;
    const isDarkRef = useRef(isDark);
    isDarkRef.current = isDark;

    const sessionRef = useRef<TerminalSession | null>(null);
    const onStateChangeRef = useRef(onStateChange);
    onStateChangeRef.current = onStateChange;
    const onActivityRef = useRef(onActivity);
    onActivityRef.current = onActivity;
    const onInputRef = useRef(onInput);
    onInputRef.current = onInput;
    const activeRef = useRef(active);
    activeRef.current = active;
    const focusOnConnectRef = useRef(focusOnConnect);
    focusOnConnectRef.current = focusOnConnect;
    const attachGenerationRef = useRef(0);

    const notifyState = useCallback((next: ConnectionState) => {
      setState(next);
      onStateChangeRef.current?.(next);
    }, []);

    const notifyActivity = useCallback(() => {
      onActivityRef.current?.();
    }, []);

    const notifyInput = useCallback(() => {
      onInputRef.current?.();
    }, []);

    const disposeActiveSession = useCallback(() => {
      sessionRef.current?.dispose();
      sessionRef.current = null;
    }, []);

    const handleResume = useCallback(async () => {
      if (!onResume) return;
      setResumeError(null);
      try {
        await onResume();
        disposeActiveSession();
        setConnectAttempt((attempt) => attempt + 1);
      } catch (error) {
        setResumeError(error instanceof Error ? error.message : 'Failed to resume');
      }
    }, [onResume, disposeActiveSession]);

    useImperativeHandle(
      ref,
      () => ({
        focus: () => sessionRef.current?.focus(),
        clear: () => sessionRef.current?.clear(),
        sendInput: (data: string) => sessionRef.current?.sendInput(data),
        reconnect: () => {
          disposeActiveSession();
          setConnectAttempt((a) => a + 1);
        },
      }),
      [disposeActiveSession],
    );

    const attachSession = useCallback(
      (node: HTMLDivElement | null) => {
        if (node === null) return;
        const generation = (attachGenerationRef.current += 1);
        disposeActiveSession();
        node.replaceChildren();
        notifyState({ kind: 'connecting' });

        let terminalSession: TerminalSession | null = null;
        let cancelled = false;
        const superseded = () => cancelled || attachGenerationRef.current !== generation;

        void (async () => {
          await Promise.resolve();
          if (superseded()) return;

          terminalSession = new TerminalSession(
            node,
            wsUrl,
            notifyState,
            isDarkRef.current,
            notifyActivity,
            notifyInput,
            !readOnly && activeRef.current,
            (text) => {
              if (navigator.clipboard) {
                navigator.clipboard.writeText(text).catch(() => {});
              }
            },
            focusOnConnectRef.current,
            adaptCodexPalette,
          );
          sessionRef.current = terminalSession;
        })();

        return () => {
          cancelled = true;
          terminalSession?.dispose();
          sessionRef.current = null;
          onStateChangeRef.current?.(null);
        };
      },
      [
        wsUrl,
        readOnly,
        adaptCodexPalette,
        notifyState,
        notifyActivity,
        notifyInput,
        disposeActiveSession,
      ],
    );

    useEffect(() => {
      sessionRef.current?.setTheme(isDark);
    }, [isDark]);

    useEffect(() => {
      sessionRef.current?.setClipboardEnabled(!readOnly && active);
    }, [readOnly, active]);

    // Handle auto-reconnect on transport drops (background freezes, server restart)
    useEffect(() => {
      if (state.kind === 'connected') {
        connectedAtRef.current = Date.now();
        setReconnectPending(false);
        return;
      }
      if (state.kind !== 'closed') return;

      if (!isUnexpectedTerminalClose(state.code)) {
        setReconnectPending(false);
        return;
      }

      if (
        connectedAtRef.current !== null &&
        Date.now() - connectedAtRef.current >= RECONNECT_STABLE_MS
      ) {
        reconnectAttemptsRef.current = 0;
      }
      connectedAtRef.current = null;

      if (reconnectAttemptsRef.current >= RECONNECT_BACKOFF_MS.length) {
        setReconnectPending(false);
        return;
      }

      const delay = RECONNECT_BACKOFF_MS[reconnectAttemptsRef.current];
      reconnectAttemptsRef.current += 1;
      setReconnectPending(true);

      let redialed = false;
      const redial = () => {
        if (redialed) return;
        redialed = true;
        disposeActiveSession();
        setConnectAttempt((attempt) => attempt + 1);
      };

      const timer = window.setTimeout(redial, delay);
      const onVisible = () => {
        if (document.visibilityState === 'visible') redial();
      };
      document.addEventListener('visibilitychange', onVisible);
      return () => {
        window.clearTimeout(timer);
        document.removeEventListener('visibilitychange', onVisible);
      };
    }, [state, disposeActiveSession]);

    return (
      <div
        data-state={state.kind}
        className={`relative isolate flex min-h-0 flex-1 flex-col ${className}`}
        style={style}
      >
        <style>{`
          .xterm .xterm-viewport {
            overflow-y: auto !important;
            scrollbar-width: thin;
          }
          .xterm .xterm-viewport::-webkit-scrollbar {
            width: 4px;
          }
          .xterm .xterm-viewport::-webkit-scrollbar-thumb {
            background: rgba(0, 0, 0, 0.15);
            border-radius: 2px;
          }
          .xterm,
          .xterm-screen,
          .xterm-helpers {
            overflow: hidden !important;
          }
          .xterm .xterm-helpers {
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
          }
          .xterm .xterm-helper-textarea {
            position: absolute !important;
            opacity: 0 !important;
            width: 0 !important;
            height: 0 !important;
            left: 0 !important;
            top: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            outline: none !important;
            overflow: hidden !important;
            resize: none !important;
            z-index: -10 !important;
            pointer-events: none !important;
          }
        `}</style>
        <div
          className="relative min-h-0 flex-1 overflow-hidden p-0"
          style={{ backgroundColor: terminalBackground }}
        >
          <div
            key={connectAttempt}
            ref={attachSession}
            className="h-full w-full overflow-hidden"
          />
          {state.kind !== 'connected' && (
            <StatusOverlay
              state={state}
              reconnectPending={reconnectPending}
              onResume={onResume ? handleResume : () => {
                disposeActiveSession();
                setConnectAttempt((a) => a + 1);
              }}
              resumePending={resumePending}
              resumeError={resumeError}
              isDark={isDark}
            />
          )}
        </div>
      </div>
    );
  },
);

function StatusOverlay({
  state,
  reconnectPending,
  onResume,
  resumePending,
  resumeError,
  isDark = false,
}: {
  state: ConnectionState;
  reconnectPending: boolean;
  onResume?: () => void | Promise<void>;
  resumePending: boolean;
  resumeError: string | null;
  isDark?: boolean;
}) {
  return (
    <div
      className={`absolute inset-0 z-50 flex items-center justify-center backdrop-blur-[2px] ${
        isDark ? 'bg-black/80 text-white' : 'bg-white/85 text-slate-800'
      }`}
    >
      {state.kind === 'connecting' && (
        <span
          className={`flex items-center gap-2.5 text-sm font-medium ${
            isDark ? 'text-zinc-300' : 'text-slate-600'
          }`}
        >
          <Loader2Icon className="h-4 w-4 animate-spin text-blue-600" />
          Connecting to sandbox terminal…
        </span>
      )}
      {state.kind === 'closed' && reconnectPending && (
        <span className="flex items-center gap-2.5 text-sm font-medium text-amber-500">
          <Loader2Icon className="h-4 w-4 animate-spin" />
          Connection interrupted • Reconnecting…
        </span>
      )}
      {state.kind === 'closed' && !reconnectPending && (
        <div
          className={`flex flex-col items-center justify-center gap-3 px-5 py-4 rounded-xl shadow-xl max-w-md text-center border ${
            isDark
              ? 'bg-zinc-900 border-zinc-700/80 text-zinc-200'
              : 'bg-white border-slate-200 text-slate-800'
          }`}
        >
          <span className="text-sm font-semibold">
            Terminal connection closed ({state.reason})
          </span>
          {onResume && (
            <button
              type="button"
              onClick={onResume}
              disabled={resumePending}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-50 cursor-pointer"
            >
              <RefreshCwIcon className={`h-3.5 w-3.5 ${resumePending ? 'animate-spin' : ''}`} />
              {resumePending ? 'Reconnecting…' : 'Reconnect Session'}
            </button>
          )}
          {resumeError && (
            <span className="text-xs text-rose-500">{resumeError}</span>
          )}
        </div>
      )}
      {state.kind === 'error' && (
        <div className="flex flex-col items-center gap-2">
          <span className="text-sm font-medium text-rose-500">WebSocket Bridge Error</span>
          {onResume && (
            <button
              type="button"
              onClick={onResume}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors cursor-pointer ${
                isDark
                  ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-800 border-slate-300'
              }`}
            >
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}
