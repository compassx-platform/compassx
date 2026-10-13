import React, { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { Terminal as TerminalIcon, Play, Send, Loader2 } from 'lucide-react';
import { getAccessToken } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  TerminalView,
  type TerminalViewHandle,
} from '@/components/terminal/TerminalView';
import type { ConnectionState } from '@/components/terminal/TerminalSession';

export interface SandboxTerminalProps {
  sandboxId: string;
  sandboxName?: string;
  workingDir?: string;
  command?: string;
  isRunning?: boolean;
  onResume?: () => void;
  onSessionReady?: () => void;
  fullHeight?: boolean;
  className?: string;
}

/**
 * Reusable, decoupled Terminal component for ANY compute sandbox (SOLID / SRP).
 * Works seamlessly with Apps, Agent Runtimes, Notebooks, and Custom Sandboxes.
 */
export function SandboxTerminal({
  sandboxId,
  sandboxName,
  workingDir,
  command,
  isRunning = true,
  onResume,
  onSessionReady,
  fullHeight = true,
  className = '',
}: SandboxTerminalProps) {
  const toast = useToast();
  const terminalViewRef = useRef<TerminalViewHandle>(null);
  const [connState, setConnState] = useState<ConnectionState | null>({ kind: 'connecting' });
  const [customCommand, setCustomCommand] = useState('');
  const [isSessionLoading, setIsSessionLoading] = useState(true);

  // Compute WebSocket URL directed to the generic /sandboxes/{sandbox_id}/terminal/ws endpoint
  const wsUrl = useMemo(() => {
    if (!sandboxId) return '';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const token = getAccessToken() || '';
    const initialCols = typeof window !== 'undefined'
      ? Math.max(80, Math.floor((window.innerWidth - 320) / 9.2))
      : 120;
    const initialRows = typeof window !== 'undefined'
      ? Math.max(24, Math.floor((window.innerHeight - 160) / 18))
      : 36;
    const params = new URLSearchParams();
    params.set('cols', String(initialCols));
    params.set('rows', String(initialRows));
    if (workingDir) params.set('working_dir', workingDir);
    if (command) params.set('command', command);
    if (token) params.set('token', token);
    return `${protocol}//${host}/api/v1/sandboxes/${encodeURIComponent(sandboxId)}/terminal/ws?${params.toString()}`;
  }, [sandboxId, workingDir, command]);

  useEffect(() => {
    setIsSessionLoading(true);
  }, [wsUrl]);

  const handleTerminalActivity = useCallback(() => {
    setIsSessionLoading(false);
    onSessionReady?.();
  }, [onSessionReady]);

  useEffect(() => {
    if (connState?.kind === 'connected') {
      const timer = setTimeout(() => {
        setIsSessionLoading(false);
        onSessionReady?.();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [connState?.kind, onSessionReady]);

  const sendCommandToTerminal = useCallback(
    (cmd: string) => {
      const cleanCmd = cmd.trim();
      if (!cleanCmd) return;
      if (connState?.kind !== 'connected') {
        toast.error('Terminal is not connected.');
        return;
      }
      terminalViewRef.current?.sendInput(`${cleanCmd}\r`);
      setCustomCommand('');
    },
    [connState, toast],
  );

  if (!isRunning) {
    return (
      <div
        style={{
          background: 'var(--color-surface, #ffffff)',
          border: '1px solid var(--color-border, #e2e8f0)',
          borderRadius: 8,
          padding: '32px 24px',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 16,
        }}
        className={className}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: '50%',
            background: 'rgba(100, 116, 139, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-text-muted, #64748b)',
          }}
        >
          <TerminalIcon size={24} />
        </div>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 6px 0', color: 'var(--color-text, #0f172a)' }}>
            Sandbox Compute is Inactive
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted, #64748b)', margin: 0, maxWidth: 380 }}>
            {sandboxName ? `The sandbox '${sandboxName}' is suspended.` : 'The compute sandbox is suspended.'} Resume it to open an interactive terminal.
          </p>
        </div>
        {onResume && (
          <button
            onClick={onResume}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              background: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: 6,
              padding: '8px 16px',
              fontSize: '0.85rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            <Play size={14} /> Resume Sandbox
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: fullHeight ? '100%' : '520px',
        minHeight: '360px',
        border: '1px solid var(--color-border, #e2e8f0)',
        borderRadius: 8,
        overflow: 'hidden',
        background: '#0d1117',
      }}
      className={className}
    >
      {/* ── Terminal Inner Stream Container ── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {isSessionLoading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(13, 17, 23, 0.85)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 10,
              gap: 8,
            }}
          >
            <Loader2 size={24} className="spin" style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '0.82rem', color: '#94a3b8', fontWeight: 500 }}>
              Connecting to sandbox shell...
            </span>
          </div>
        )}

        {wsUrl && (
          <TerminalView
            key={wsUrl}
            ref={terminalViewRef}
            wsUrl={wsUrl}
            onStateChange={setConnState}
            onActivity={handleTerminalActivity}
            adaptCodexPalette={true}
            isDark={true}
            className="w-full h-full"
          />
        )}
      </div>

      {/* ── Direct Command Input Bar ── */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendCommandToTerminal(customCommand);
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: '#161b22',
          borderTop: '1px solid #30363d',
          padding: '6px 12px',
        }}
      >
        <span style={{ color: '#38bdf8', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem' }}>
          $
        </span>
        <input
          type="text"
          value={customCommand}
          onChange={(e) => setCustomCommand(e.target.value)}
          placeholder="Type a command and press Enter..."
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#f0f6fc',
            fontFamily: 'monospace',
            fontSize: '0.85rem',
          }}
        />
        <button
          type="submit"
          disabled={!customCommand.trim()}
          style={{
            background: customCommand.trim() ? '#238636' : 'transparent',
            color: customCommand.trim() ? '#ffffff' : '#8b949e',
            border: 'none',
            borderRadius: 4,
            padding: '4px 10px',
            fontSize: '0.8rem',
            cursor: customCommand.trim() ? 'pointer' : 'default',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <Send size={12} /> Run
        </button>
      </form>
    </div>
  );
}
