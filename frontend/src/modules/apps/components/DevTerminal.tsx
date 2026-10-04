import React, { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { Terminal as TerminalIcon, Play, Send, Loader2, Lock, Cpu, Sparkles } from 'lucide-react';
import { getAccessToken } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  TerminalView,
  type TerminalViewHandle,
} from '@/components/terminal/TerminalView';
import type { ConnectionState } from '@/components/terminal/TerminalSession';

const AGENT_META: Record<string, { name: string; color: string; accentBg: string; borderColor: string }> = {
  opencode: {
    name: 'OpenCode',
    color: '#38bdf8',
    accentBg: 'rgba(56, 189, 248, 0.15)',
    borderColor: 'rgba(56, 189, 248, 0.4)',
  },
  pi: {
    name: 'Pi CLI',
    color: '#c084fc',
    accentBg: 'rgba(192, 132, 252, 0.15)',
    borderColor: 'rgba(192, 132, 252, 0.4)',
  },
  antigravity: {
    name: 'Antigravity',
    color: '#4ade80',
    accentBg: 'rgba(74, 222, 128, 0.15)',
    borderColor: 'rgba(74, 222, 128, 0.4)',
  },
  agy: {
    name: 'Antigravity',
    color: '#4ade80',
    accentBg: 'rgba(74, 222, 128, 0.15)',
    borderColor: 'rgba(74, 222, 128, 0.4)',
  },
};

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
          background: '#0d1117',
          border: '1px solid #30363d',
          borderRadius: 8,
          padding: '32px 24px',
          textAlign: 'center',
          color: '#8b949e',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <TerminalIcon size={36} color="#484f58" />
        <div style={{ fontSize: '1rem', fontWeight: 600, color: '#c9d1d9' }}>
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
  const agentKey = (agent || 'opencode').toLowerCase();
  const activeMeta = AGENT_META[agentKey] || AGENT_META.opencode;

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
        gap: 6,
      }}
    >
      {/* ── Omnigent TerminalView Surface (Chrome-Free Full Canvas) ── */}
      <div
        style={{
          height: '100%',
          flex: 1,
          width: '100%',
          background: '#0a0e17',
          border: '1px solid #1f2937',
          borderRadius: 8,
          overflow: 'hidden',
          boxShadow: 'inset 0 2px 8px rgba(0, 0, 0, 0.4)',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}
      >
        {/* Session Transition Loader Overlay */}
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
              background: 'rgba(9, 13, 22, 0.88)',
              backdropFilter: 'blur(6px)',
              padding: '24px',
              animation: 'fadeIn 0.2s ease-out',
            }}
          >
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 16,
                maxWidth: 440,
                textAlign: 'center',
              }}
            >
              {/* Glowing Agent Icon with Spinning Ring */}
              <div
                style={{
                  position: 'relative',
                  width: 58,
                  height: 58,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    borderRadius: '50%',
                    border: `2.5px solid ${activeMeta.accentBg}`,
                    borderTopColor: activeMeta.color,
                    animation: 'spin 0.9s linear infinite',
                  }}
                />
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: '50%',
                    background: activeMeta.accentBg,
                    border: `1px solid ${activeMeta.borderColor}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: activeMeta.color,
                    boxShadow: `0 0 24px ${activeMeta.accentBg}`,
                  }}
                >
                  <Cpu size={22} />
                </div>
              </div>

              {/* Status Header */}
              <div>
                <div
                  style={{
                    fontSize: '1rem',
                    fontWeight: 650,
                    color: '#f8fafc',
                    letterSpacing: '-0.2px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                  }}
                >
                  <span>{sessionTitle ? `Loading "${sessionTitle}"` : 'Loading Dev Session...'}</span>
                </div>
                <div
                  style={{
                    fontSize: '0.78rem',
                    color: '#94a3b8',
                    marginTop: 4,
                    lineHeight: 1.4,
                  }}
                >
                  Connecting to container tmux session & initializing {activeMeta.name}...
                </div>
              </div>

              {/* Status Badges */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  flexWrap: 'wrap',
                  justifyContent: 'center',
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '3px 8px',
                    borderRadius: 6,
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    background: activeMeta.accentBg,
                    color: activeMeta.color,
                    border: `1px solid ${activeMeta.borderColor}`,
                  }}
                >
                  <Lock size={10} />
                  <span>Locked: {activeMeta.name}</span>
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '3px 8px',
                    borderRadius: 6,
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    background: 'rgba(255, 255, 255, 0.06)',
                    color: '#cbd5e1',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                >
                  <Loader2 size={10} className="spin" color="#38bdf8" />
                  <span>Attaching tmux PTY...</span>
                </span>
              </div>

              {/* Slim Indeterminate Progress Bar */}
              <div
                style={{
                  width: 220,
                  height: 3,
                  background: 'rgba(255, 255, 255, 0.08)',
                  borderRadius: 2,
                  overflow: 'hidden',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    bottom: 0,
                    width: '50%',
                    background: `linear-gradient(90deg, transparent, ${activeMeta.color}, transparent)`,
                    animation: 'indeterminateProgress 1.4s ease-in-out infinite',
                  }}
                />
              </div>
            </div>
            <style>{`
              @keyframes indeterminateProgress {
                0% { left: -45%; width: 40%; }
                50% { left: 25%; width: 55%; }
                100% { left: 100%; width: 40%; }
              }
            `}</style>
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
            background: '#111827',
            border: '1px solid #1f2937',
            borderRadius: 6,
            padding: '6px 10px',
          }}
        >
          <span style={{ color: '#a855f7', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem' }}>
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
              color: '#f8fafc',
              fontFamily: 'JetBrains Mono, Menlo, monospace',
              fontSize: '0.82rem',
            }}
          />
          <button
            type="submit"
            className="btn"
            disabled={!customCommand.trim() || !isConnected}
            style={{
              background: '#6366f1',
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
