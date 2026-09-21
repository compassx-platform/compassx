import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Terminal as TerminalIcon,
  X,
  Trash2,
  Maximize2,
  Minimize2,
  Play,
  Loader2,
  CornerDownLeft,
  Square,
  Sparkles,
} from 'lucide-react';
import { useNotebookStore } from '../../store/notebookStore';
import type { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';

interface TerminalLine {
  id: string;
  type: 'cmd' | 'stdout' | 'stderr' | 'system';
  content: string;
}

export default function NotebookBottomTerminal() {
  const isBottomTerminalOpen = useNotebookStore((s) => s.isBottomTerminalOpen);
  const setBottomTerminalOpen = useNotebookStore((s) => s.setBottomTerminalOpen);
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const kernelRef = useNotebookStore((s) => s.kernelRef);
  const kernelStatus = useNotebookStore((s) => s.kernelStatus);

  const [inputCommand, setInputCommand] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [history, setHistory] = useState<TerminalLine[]>([
    {
      id: 'init-1',
      type: 'system',
      content: 'CompassX Pod Interactive Terminal',
    },
    {
      id: 'init-2',
      type: 'system',
      content: 'Connected to compute container environment. Type any shell command (e.g. ls, pip list, env, python -V) and press Enter.',
    },
  ]);

  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState<number>(-1);

  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeFutureRef = useRef<any>(null);

  // Auto-scroll to bottom on output
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  // Focus input on mount or opening
  useEffect(() => {
    if (isBottomTerminalOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isBottomTerminalOpen]);

  // Run shell command directly inside pod container via kernel
  const handleExecute = useCallback(
    async (cmdToRun?: string) => {
      const command = (cmdToRun ?? inputCommand).trim();
      if (!command) return;

      const kernel = kernelRef as IKernelConnection | null;
      const cmdId = Date.now().toString();

      // Append command to terminal history
      setHistory((prev) => [
        ...prev,
        { id: `cmd-${cmdId}`, type: 'cmd', content: command },
      ]);
      setCmdHistory((prev) => [...prev, command]);
      setHistoryIdx(-1);
      setInputCommand('');

      if (!kernel || kernelStatus === 'dead' || kernelStatus === 'unknown') {
        setHistory((prev) => [
          ...prev,
          {
            id: `err-${cmdId}`,
            type: 'stderr',
            content: 'Error: No compute pod kernel is connected. Please attach compute first.',
          },
        ]);
        return;
      }

      setIsRunning(true);

      try {
        // Execute shell command using IPython bang syntax '! cmd'
        const future = kernel.requestExecute({
          code: `! ${command}`,
          store_history: false,
          silent: false,
        });
        activeFutureRef.current = future;

        future.onIOPub = (msg) => {
          const msgType = msg.header.msg_type;
          const content = msg.content as Record<string, unknown>;

          if (msgType === 'stream') {
            const streamName = (content.name as string) ?? 'stdout';
            const text = (content.text as string) ?? '';
            const lines = text.split('\n');

            lines.forEach((line, lIdx) => {
              if (line || lIdx < lines.length - 1) {
                setHistory((prev) => [
                  ...prev,
                  {
                    id: `out-${Date.now()}-${Math.random()}`,
                    type: streamName === 'stderr' ? 'stderr' : 'stdout',
                    content: line,
                  },
                ]);
              }
            });
          } else if (msgType === 'error') {
            const traceback = (content.traceback as string[]) || [];
            const evalue = (content.evalue as string) || 'Command failed';
            setHistory((prev) => [
              ...prev,
              {
                id: `err-${Date.now()}`,
                type: 'stderr',
                content: traceback.join('\n') || evalue,
              },
            ]);
          }
        };

        await future.done;
      } catch (err: any) {
        setHistory((prev) => [
          ...prev,
          {
            id: `exc-${Date.now()}`,
            type: 'stderr',
            content: err?.message ?? 'Execution error',
          },
        ]);
      } finally {
        setIsRunning(false);
        activeFutureRef.current = null;
        setTimeout(() => {
          if (inputRef.current) inputRef.current.focus();
        }, 50);
      }
    },
    [inputCommand, kernelRef, kernelStatus],
  );

  // Keyboard navigation (history up/down)
  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleExecute();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdHistory.length === 0) return;
      const nextIdx = historyIdx === -1 ? cmdHistory.length - 1 : Math.max(0, historyIdx - 1);
      setHistoryIdx(nextIdx);
      setInputCommand(cmdHistory[nextIdx] || '');
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx === -1) return;
      const nextIdx = historyIdx + 1;
      if (nextIdx >= cmdHistory.length) {
        setHistoryIdx(-1);
        setInputCommand('');
      } else {
        setHistoryIdx(nextIdx);
        setInputCommand(cmdHistory[nextIdx]);
      }
    }
  }

  function handleInterrupt() {
    if (kernelRef) {
      kernelRef.interrupt();
      setIsRunning(false);
      setHistory((prev) => [
        ...prev,
        { id: `int-${Date.now()}`, type: 'system', content: '^C (Interrupted)' },
      ]);
    }
  }

  if (!isBottomTerminalOpen) return null;

  return (
    <div className={`dbx-bottom-terminal ${isMaximized ? 'is-maximized' : ''}`}>
      {/* ── Terminal Header ── */}
      <div className="dbx-term-header">
        <div className="dbx-term-header-left">
          <TerminalIcon size={14} className="dbx-term-header-icon" />
          <span className="dbx-term-title">Terminal</span>
          <span className="dbx-term-subtitle">
            {selectedPod?.runtime ? `pod: ${selectedPod.runtime}` : 'pod shell'}
          </span>
          <span
            className={`dbx-term-dot ${
              kernelStatus === 'idle' || kernelStatus === 'busy'
                ? 'is-connected'
                : 'is-disconnected'
            }`}
            title={`Kernel: ${kernelStatus}`}
          />
        </div>

        <div className="dbx-term-header-right">
          {isRunning && (
            <button
              type="button"
              className="dbx-term-btn dbx-term-btn--cancel"
              onClick={handleInterrupt}
              title="Interrupt running command (Ctrl+C)"
            >
              <Square size={11} />
              <span>Cancel</span>
            </button>
          )}

          <button
            type="button"
            className="dbx-term-icon-btn"
            onClick={() => setHistory([])}
            title="Clear terminal screen"
          >
            <Trash2 size={13} />
          </button>

          <button
            type="button"
            className="dbx-term-icon-btn"
            onClick={() => setIsMaximized(!isMaximized)}
            title={isMaximized ? 'Restore height' : 'Maximize terminal'}
          >
            {isMaximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>

          <button
            type="button"
            className="dbx-term-icon-btn"
            onClick={() => setBottomTerminalOpen(false)}
            title="Close terminal"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* ── Console Output Stream ── */}
      <div
        className="dbx-term-body"
        ref={scrollRef}
        onClick={() => {
          if (inputRef.current) inputRef.current.focus();
        }}
      >
        {history.map((line) => {
          if (line.type === 'system') {
            return (
              <div key={line.id} className="dbx-term-line dbx-term-line--system">
                {line.content}
              </div>
            );
          }
          if (line.type === 'cmd') {
            return (
              <div key={line.id} className="dbx-term-line dbx-term-line--cmd">
                <span className="dbx-term-prompt-prefix">compassx@pod:~$</span>
                <span className="dbx-term-cmd-text">{line.content}</span>
              </div>
            );
          }
          if (line.type === 'stderr') {
            return (
              <div key={line.id} className="dbx-term-line dbx-term-line--stderr">
                {line.content}
              </div>
            );
          }
          return (
            <div key={line.id} className="dbx-term-line dbx-term-line--stdout">
              {line.content}
            </div>
          );
        })}

        {/* ── Interactive Command Input Prompt ── */}
        <div className="dbx-term-input-row">
          <span className="dbx-term-prompt-prefix">compassx@pod:~$</span>
          <input
            ref={inputRef}
            type="text"
            className="dbx-term-cli-input"
            value={inputCommand}
            onChange={(e) => setInputCommand(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isRunning}
            placeholder={isRunning ? 'Executing...' : 'Type bash command...'}
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
          />
          {isRunning ? (
            <Loader2 size={12} className="notebook-pod-spinner dbx-term-spinner" />
          ) : (
            <button
              type="button"
              className="dbx-term-enter-btn"
              onClick={() => handleExecute()}
              title="Execute command (Enter)"
            >
              <CornerDownLeft size={11} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
