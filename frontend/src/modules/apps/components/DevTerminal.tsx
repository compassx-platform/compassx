import React, { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { Terminal as TerminalIcon, Play, Send, Loader2 } from 'lucide-react';
import { getAccessToken } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  TerminalView,
  type TerminalViewHandle,
} from '@/components/terminal/TerminalView';
import type { ConnectionState } from '@/components/terminal/TerminalSession';


interface DevTerminalProps {
  appId: string;
  appName?: string;
  workspaceId?: string;
  workspaceName?: string;
  isDevPodRunning: boolean;
  onStartDevPod?: () => void;
  agent?: string;
  sessionId?: string;
  sessionTitle?: string;
  isSwitchingSession?: boolean;
  onSessionReady?: () => void;
  fullHeight?: boolean;
}

export function DevTerminal({
  appId,
  workspaceId,
  workspaceName,
  isDevPodRunning,
  onStartDevPod,
  agent,
  sessionId,
  sessionTitle,
  isSwitchingSession = false,
  onSessionReady,
  fullHeight = false,
}: DevTerminalProps) {
  const toast = useToast();
  const terminalViewRef = useRef<TerminalViewHandle>(null);
  const [connState, setConnState] = useState<ConnectionState | null>({ kind: 'connecting' });
  const [customCommand, setCustomCommand] = useState('');
  const [isSessionLoading, setIsSessionLoading] = useState(true);
  const [hasReceivedOutput, setHasReceivedOutput] = useState(false);

  // Compute WebSocket URL
  const wsUrl = useMemo(() => {
    if (!appId) return '';
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
    if (workspaceId) params.set('workspace_id', workspaceId);
    if (workspaceName) params.set('workspace_name', workspaceName);
    if (token) params.set('token', token);
    if (agent) params.set('agent', agent);
    if (sessionId) params.set('session_id', sessionId);
    return `${protocol}//${host}/api/v1/apps/${encodeURIComponent(appId)}/dev/terminal/ws?${params.toString()}`;
  }, [appId, workspaceId, workspaceName, agent, sessionId]);

  // When sessionId or wsUrl changes, reset loading state
  useEffect(() => {
    setIsSessionLoading(true);
    setHasReceivedOutput(false);
  }, [sessionId, wsUrl]);

  // Terminal activity callback from TerminalView
  const handleTerminalActivity = useCallback(() => {
    setHasReceivedOutput(true);
    setIsSessionLoading(false);
    onSessionReady?.();
  }, [onSessionReady]);

  // Fallback: If connected for 1.8 seconds, clear loader even if no terminal activity arrived yet
  useEffect(() => {
    if (connState?.kind === 'connected') {
      const timer = setTimeout(() => {
        setIsSessionLoading(false);
        onSessionReady?.();
      }, 1800);
      return () => clearTimeout(timer);
    }
  }, [connState?.kind, sessionId, onSessionReady]);

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

  if (!isDevPodRunning) {
    return (
      <div
        style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: 8,
          padding: '32px 24px',
          textAlign: 'center',
          color: '#64748b',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        }}
      >
        <TerminalIcon size={36} color="#94a3b8" />
        <div style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a' }}>
          Dev Container is Stopped
        </div>
        <div style={{ fontSize: '0.82rem', maxWidth: 420 }}>
          The interactive terminal requires an active development container. Start the container to begin debugging.
        </div>
        {onStartDevPod && (
          <button
            onClick={onStartDevPod}
            className="btn btn-primary"
            style={{
              marginTop: 8,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 16px',
              fontSize: '0.85rem',
            }}
          >
            <Play size={14} />
            <span>Start Dev Sandbox</span>
          </button>
        )}
      </div>
    );
  }

  const isConnected = connState?.kind === 'connected';
  const showLoader = isSessionLoading || isSwitchingSession || connState?.kind === 'connecting';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: fullHeight ? '100%' : 520,
        flex: fullHeight ? 1 : 'none',
        width: '100%',
        position: 'relative',
        overflow: 'hidden',
        gap: 0,
      }}
    >
      {/* ── Omnigent TerminalView Surface (Clean Light Canvas) ── */}
      <div
        style={{
          height: '100%',
          flex: 1,
          width: '100%',
          background: '#ffffff',
          border: 'none',
          borderRadius: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}
      >
        {/* Simple Session Loader Overlay */}
        {showLoader && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 35,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(255, 255, 255, 0.88)',
              backdropFilter: 'blur(3px)',
              gap: 10,
            }}
          >
            <Loader2 size={24} className="spin" style={{ color: '#1B6EF3' }} />
            <span
              style={{
                fontSize: '0.82rem',
                color: '#64748b',
                fontWeight: 500,
              }}
            >
              Loading session...
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
            isDark={false}
            className="w-full h-full"
          />
        )}
      </div>

      {/* ── Direct Command Input Bar (Hidden for native agents since each has its own interactive CLI prompt) ── */}
      {!['pi', 'opencode', 'antigravity', 'agy'].includes(agent || '') && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendCommandToTerminal(customCommand);
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: '#ffffff',
            borderTop: '1px solid #e2e8f0',
            borderLeft: 'none',
            borderRight: 'none',
            borderBottom: 'none',
            borderRadius: 0,
            padding: '7px 12px',
          }}
        >
          <span style={{ color: '#7c3aed', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem' }}>
            $
          </span>
          <input
            type="text"
            value={customCommand}
            onChange={(e) => setCustomCommand(e.target.value)}
            placeholder="Type any command and press Enter (e.g. npm test, ls -la, python app.py)..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#0f172a',
              fontFamily: 'JetBrains Mono, Menlo, monospace',
              fontSize: '0.82rem',
            }}
          />
          <button
            type="submit"
            className="btn"
            disabled={!customCommand.trim() || !isConnected}
            style={{
              background: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: 4,
              padding: '4px 10px',
              fontSize: '0.76rem',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: customCommand.trim() && isConnected ? 'pointer' : 'not-allowed',
              opacity: customCommand.trim() && isConnected ? 1 : 0.5,
            }}
          >
            <Send size={11} />
            <span>Run</span>
          </button>
        </form>
      )}
    </div>
  );
}
