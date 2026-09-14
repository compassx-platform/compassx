import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from '@xterm/addon-fit';
import 'xterm/css/xterm.css';
import {
  Terminal as TerminalIcon,
  Play,
  RotateCw,
  Trash2,
  Maximize2,
  Minimize2,
  Sparkles,
  Command,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Send,
} from 'lucide-react';
import { getAccessToken } from '@/lib/auth';
import { useToast } from '@/lib/toast';

interface DevTerminalProps {
  appId: string;
  appName: string;
  workspaceId?: string;
  workspaceName?: string;
  isDevPodRunning: boolean;
  onStartDevPod?: () => void;
}

const PRESET_COMMANDS = [
  { label: 'npm install', cmd: 'npm install', icon: '📦' },
  { label: 'npm run build', cmd: 'npm run build', icon: '⚡' },
  { label: 'pip install reqs', cmd: 'pip install -r requirements.txt', icon: '🐍' },
  { label: 'pip list', cmd: 'pip list', icon: '📋' },
  { label: 'git status', cmd: 'git status', icon: '🌿' },
  { label: 'git log', cmd: 'git log -n 5 --oneline', icon: '📜' },
  { label: 'ps aux', cmd: 'ps aux', icon: '⚙️' },
  { label: 'ls -la', cmd: 'ls -la', icon: '📁' },
];

export function DevTerminal({
  appId,
  appName,
  workspaceId,
  workspaceName,
  isDevPodRunning,
  onStartDevPod,
}: DevTerminalProps) {
  const toast = useToast();
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [connStatus, setConnStatus] = useState<'connected' | 'connecting' | 'disconnected' | 'error'>('disconnected');
  const [customCommand, setCustomCommand] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Send command to the active terminal
  const sendCommandToTerminal = useCallback((cmd: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      toast.error('Terminal is not connected.');
      return;
    }
    const cleanCmd = cmd.trim();
    if (!cleanCmd) return;
    wsRef.current.send(`${cleanCmd}\r`);
    setCustomCommand('');
  }, [toast]);


  // Connect WebSocket
  const connectTerminal = useCallback(() => {
    if (!isDevPodRunning || !appId) return;

    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        // ignore
      }
    }

    setConnStatus('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const token = getAccessToken() || '';
    const wsUrl = `${protocol}//${host}/api/v1/apps/${appId}/dev/terminal/ws?workspace_id=${encodeURIComponent(
      workspaceId || ''
    )}&workspace_name=${encodeURIComponent(workspaceName || '')}&token=${encodeURIComponent(token)}`;

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setConnStatus('connected');
        if (xtermInstanceRef.current && fitAddonRef.current) {
          fitAddonRef.current.fit();
          const { cols, rows } = xtermInstanceRef.current;
          socket.send(JSON.stringify({ type: 'resize', cols, rows }));
        }
      };

      socket.onmessage = (event) => {
        if (xtermInstanceRef.current) {
          xtermInstanceRef.current.write(event.data);
        }
      };

      socket.onclose = () => {
        setConnStatus('disconnected');
      };

      socket.onerror = () => {
        setConnStatus('error');
      };
    } catch {
      setConnStatus('error');
    }
  }, [appId, isDevPodRunning, workspaceId, workspaceName]);

  // Initialize XTerm
  useEffect(() => {
    if (!terminalRef.current) return;

    // Dispose prior instance if any
    if (xtermInstanceRef.current) {
      xtermInstanceRef.current.dispose();
    }

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'block',
      fontFamily: 'JetBrains Mono, Menlo, Monaco, "Courier New", monospace',
      fontSize: 13,
      lineHeight: 1.25,
      letterSpacing: 0,
      theme: {
        background: '#0a0e17',
        foreground: '#e2e8f0',
        cursor: '#a855f7',
        cursorAccent: '#0a0e17',
        selectionBackground: 'rgba(168, 85, 247, 0.35)',
        black: '#1e293b',
        red: '#f43f5e',
        green: '#10b981',
        yellow: '#f59e0b',
        blue: '#3b82f6',
        magenta: '#d946ef',
        cyan: '#06b6d4',
        white: '#f8fafc',
        brightBlack: '#475569',
        brightRed: '#fb7185',
        brightGreen: '#34d399',
        brightYellow: '#fbbf24',
        brightBlue: '#60a5fa',
        brightMagenta: '#e879f9',
        brightCyan: '#22d3ee',
        brightWhite: '#ffffff',
      },
      convertEol: true,
      scrollback: 5000,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermInstanceRef.current = term;
    fitAddonRef.current = fitAddon;

    // Handle user input
    term.onData((data) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      }
    });

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
        }
      } catch {
        // ignore
      }
    });

    if (terminalRef.current) {
      resizeObserver.observe(terminalRef.current);
    }

    if (isDevPodRunning) {
      connectTerminal();
    }

    return () => {
      resizeObserver.disconnect();
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          // ignore
        }
      }
      term.dispose();
      xtermInstanceRef.current = null;
      fitAddonRef.current = null;
    };
  }, [isDevPodRunning, connectTerminal]);

  // Handle clear
  const handleClear = () => {
    if (xtermInstanceRef.current) {
      xtermInstanceRef.current.clear();
    }
  };

  if (!isDevPodRunning) {
    return (
      <div
        style={{
          height: 480,
          border: '1px dashed var(--color-border)',
          borderRadius: 8,
          background: 'var(--color-surface-hover, #f8fafc)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 32,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 52,
            height: 52,
            borderRadius: '50%',
            background: 'rgba(99, 102, 241, 0.12)',
            color: '#6366f1',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 16,
          }}
        >
          <TerminalIcon size={26} />
        </div>
        <h4 style={{ margin: '0 0 8px', fontSize: '1.05rem', fontWeight: 600 }}>
          Interactive Dev Terminal Offline
        </h4>
        <p style={{ margin: '0 0 20px', fontSize: '0.84rem', color: 'var(--color-text-muted)', maxWidth: 440, lineHeight: 1.5 }}>
          The dev pod is not running. Start the dev sandbox to access the live container terminal, run commands, and manage workspace files directly.
        </p>
        {onStartDevPod && (
          <button className="btn btn-primary" onClick={onStartDevPod} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Play size={14} />
            <span>Start Dev Pod & Open Terminal</span>
          </button>
        )}
      </div>
    );
  }

  const containerStyle: React.CSSProperties = isFullscreen
    ? {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 9999,
        background: '#0a0e17',
        padding: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }
    : {
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      };

  return (
    <div style={containerStyle}>
      {/* ── Top Toolbar & Status ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 10,
          background: '#111827',
          border: '1px solid #1f2937',
          borderRadius: '8px 8px 0 0',
          padding: '8px 14px',
        }}
      >
        {/* Left: Terminal Identity & Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f3f4f6', fontWeight: 600, fontSize: '0.84rem' }}>
            <TerminalIcon size={15} color="#a855f7" />
            <span>Dev Container Terminal</span>
          </div>

          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '2px 8px',
              borderRadius: 10,
              fontSize: '0.72rem',
              fontWeight: 600,
              background:
                connStatus === 'connected'
                  ? 'rgba(16, 185, 129, 0.15)'
                  : connStatus === 'connecting'
                  ? 'rgba(245, 158, 11, 0.15)'
                  : 'rgba(239, 68, 68, 0.15)',
              color:
                connStatus === 'connected'
                  ? '#34d399'
                  : connStatus === 'connecting'
                  ? '#fbbf24'
                  : '#f87171',
              border:
                connStatus === 'connected'
                  ? '1px solid rgba(16, 185, 129, 0.3)'
                  : connStatus === 'connecting'
                  ? '1px solid rgba(245, 158, 11, 0.3)'
                  : '1px solid rgba(239, 68, 68, 0.3)',
            }}
          >
            {connStatus === 'connected' ? (
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
            ) : connStatus === 'connecting' ? (
              <Loader2 size={10} className="spin" color="#f59e0b" />
            ) : (
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444' }} />
            )}
            {connStatus === 'connected'
              ? 'Connected'
              : connStatus === 'connecting'
              ? 'Connecting...'
              : 'Disconnected'}
          </span>

          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
            Workdir: <code style={{ color: '#cbd5e1' }}>{workspaceName ? `/workspaces/.../${workspaceName}` : '/workspaces/.../default'}</code>
          </span>
        </div>

        {/* Right: Actions (Clear, Reconnect, Fullscreen) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            onClick={handleClear}
            className="btn"
            style={{
              background: '#1f2937',
              color: '#94a3b8',
              border: '1px solid #374151',
              padding: '4px 10px',
              fontSize: '0.74rem',
              borderRadius: 4,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title="Clear terminal screen"
          >
            <Trash2 size={12} />
            <span>Clear</span>
          </button>

          <button
            onClick={connectTerminal}
            className="btn"
            style={{
              background: '#1f2937',
              color: '#94a3b8',
              border: '1px solid #374151',
              padding: '4px 10px',
              fontSize: '0.74rem',
              borderRadius: 4,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title="Reconnect terminal session"
          >
            <RotateCw size={12} />
            <span>Reconnect</span>
          </button>

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="btn"
            style={{
              background: '#1f2937',
              color: '#94a3b8',
              border: '1px solid #374151',
              padding: '4px 8px',
              fontSize: '0.74rem',
              borderRadius: 4,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title={isFullscreen ? 'Exit Fullscreen' : 'Expand Fullscreen'}
          >
            {isFullscreen ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
          </button>
        </div>
      </div>

      {/* ── Quick Command Presets Bar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          overflowX: 'auto',
          padding: '4px 2px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.74rem', color: 'var(--color-text-muted)', fontWeight: 600, flexShrink: 0 }}>
          <Sparkles size={13} color="var(--color-primary)" />
          <span>Quick Commands:</span>
        </div>

        {PRESET_COMMANDS.map((item) => (
          <button
            key={item.label}
            onClick={() => sendCommandToTerminal(item.cmd)}
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 6,
              padding: '3px 8px',
              fontSize: '0.74rem',
              fontWeight: 500,
              color: 'var(--color-text)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
            title={`Run "${item.cmd}" inside the container`}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      {/* ── XTerm Terminal Canvas ── */}
      <div
        ref={terminalRef}
        style={{
          height: isFullscreen ? 'calc(100vh - 170px)' : 460,
          background: '#0a0e17',
          border: '1px solid #1f2937',
          borderRadius: 8,
          padding: '10px 12px',
          overflow: 'hidden',
          boxShadow: 'inset 0 2px 8px rgba(0, 0, 0, 0.4)',
        }}
      />

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
          background: '#111827',
          border: '1px solid #1f2937',
          borderRadius: 6,
          padding: '6px 10px',
        }}
      >
        <span style={{ color: '#a855f7', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem' }}>$</span>
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
          disabled={!customCommand.trim() || connStatus !== 'connected'}
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
            cursor: customCommand.trim() && connStatus === 'connected' ? 'pointer' : 'not-allowed',
            opacity: customCommand.trim() && connStatus === 'connected' ? 1 : 0.5,
          }}
        >
          <Send size={11} />
          <span>Run</span>
        </button>
      </form>
    </div>
  );
}
