import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Terminal,
  RotateCw,
  Copy,
  Trash2,
  Minimize2,
  Maximize2,
  ChevronDown,
  ChevronUp,
  X,
  AlertCircle,
  CheckCircle2,
  Plus,
} from 'lucide-react';
import { useToast } from '@/lib/toast';
import { DevTerminal } from '../DevTerminal';

export type OutputTab = 'devServer' | 'console' | 'terminal';

interface OutputDrawerProps {
  devLogs: string;
  isDevRunning: boolean;
  onRefreshLogs?: () => void;
  isRefreshing?: boolean;
  isCollapsed: boolean;
  onToggleCollapsed: () => void;
  height: number;
  onHeightChange?: (height: number) => void;
  onClose?: () => void;
  appId?: string;
  appName?: string;
  workspaceId?: string;
  workspaceName?: string;
  isDevPodRunning?: boolean;
  initialTab?: OutputTab;
}

export function OutputDrawer({
  devLogs,
  isDevRunning,
  onRefreshLogs,
  isRefreshing = false,
  isCollapsed,
  onToggleCollapsed,
  height,
  onHeightChange,
  onClose,
  appId,
  appName,
  workspaceId,
  workspaceName,
  isDevPodRunning,
  initialTab = 'devServer',
}: OutputDrawerProps) {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<OutputTab>(initialTab);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [isMaximized, setIsMaximized] = useState<boolean>(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current && !isCollapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [devLogs, autoScroll, isCollapsed, activeTab]);

  const handleCopyLogs = () => {
    if (!devLogs) {
      toast.info('No logs to copy.');
      return;
    }
    navigator.clipboard.writeText(devLogs);
    toast.success('Logs copied to clipboard');
  };

  // Filter errors/warnings for Console tab
  const consoleLogs = useMemo(() => {
    if (!devLogs) return 'No runtime console logs recorded.';
    const lines = devLogs.split('\n');
    const filtered = lines.filter((l) =>
      /error|warn|exception|fail|rejected|uncaught|traceback/i.test(l)
    );
    return filtered.length > 0
      ? filtered.join('\n')
      : 'No client or runtime warnings/errors detected.\nAll processes running nominally.';
  }, [devLogs]);

  const toggleMaximize = () => {
    setIsMaximized((prev) => !prev);
  };

  if (isCollapsed) return null;

  const drawerHeight = isMaximized ? 460 : height;

  return (
    <div
      style={{
        height: `${drawerHeight}px`,
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#ffffff',
        borderTop: '1px solid #e2e8f0',
        color: '#334155',
        overflow: 'hidden',
        transition: 'height 0.15s ease',
        flexShrink: 0,
        zIndex: 10,
      }}
    >
      {/* ── Output Header Bar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 34,
          padding: '0 12px',
          background: '#f8fafc',
          borderBottom: isCollapsed ? 'none' : '1px solid #e2e8f0',
          fontSize: '0.74rem',
          userSelect: 'none',
          flexShrink: 0,
        }}
      >
        {/* Left: Title + Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 700, color: '#475569', letterSpacing: '0.04em' }}>
            Output
          </span>

          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {/* Dev Server Tab */}
            <button
              type="button"
              onClick={() => {
                setActiveTab('devServer');
                if (isCollapsed) onToggleCollapsed();
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 8px',
                borderRadius: 4,
                border: activeTab === 'devServer' && !isCollapsed ? '1px solid #e2e8f0' : '1px solid transparent',
                background: activeTab === 'devServer' && !isCollapsed ? '#ffffff' : 'transparent',
                color: activeTab === 'devServer' && !isCollapsed ? '#0f172a' : '#64748b',
                fontWeight: activeTab === 'devServer' && !isCollapsed ? 600 : 500,
                fontSize: '0.72rem',
                cursor: 'pointer',
                boxShadow: activeTab === 'devServer' && !isCollapsed ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: isDevRunning ? '#16a34a' : '#f59e0b',
                  boxShadow: isDevRunning ? '0 0 4px #22c55e' : 'none',
                }}
              />
              <span>Dev Server</span>
            </button>

            {/* Console Tab */}
            <button
              type="button"
              onClick={() => {
                setActiveTab('console');
                if (isCollapsed) onToggleCollapsed();
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '3px 8px',
                borderRadius: 4,
                border: activeTab === 'console' && !isCollapsed ? '1px solid #e2e8f0' : '1px solid transparent',
                background: activeTab === 'console' && !isCollapsed ? '#ffffff' : 'transparent',
                color: activeTab === 'console' && !isCollapsed ? '#0f172a' : '#64748b',
                fontWeight: activeTab === 'console' && !isCollapsed ? 600 : 500,
                fontSize: '0.72rem',
                cursor: 'pointer',
                boxShadow: activeTab === 'console' && !isCollapsed ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              <Terminal size={12} />
              <span>Console</span>
            </button>

            {/* Terminal (Shell) Tab */}
            <button
              type="button"
              onClick={() => {
                setActiveTab('terminal');
                if (isCollapsed) onToggleCollapsed();
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '3px 8px',
                borderRadius: 4,
                border: activeTab === 'terminal' && !isCollapsed ? '1px solid #e2e8f0' : '1px solid transparent',
                background: activeTab === 'terminal' && !isCollapsed ? '#ffffff' : 'transparent',
                color: activeTab === 'terminal' && !isCollapsed ? '#0f172a' : '#64748b',
                fontWeight: activeTab === 'terminal' && !isCollapsed ? 600 : 500,
                fontSize: '0.72rem',
                cursor: 'pointer',
                boxShadow: activeTab === 'terminal' && !isCollapsed ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              <Terminal size={12} style={{ color: activeTab === 'terminal' && !isCollapsed ? '#16a34a' : '#64748b' }} />
              <span>Terminal</span>
            </button>
          </div>
        </div>

        {/* Right: Actions & Window Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {!isCollapsed && (
            <>
              {/* Auto Scroll toggle (for log tabs) */}
              {activeTab !== 'terminal' && (
                <button
                  type="button"
                  onClick={() => setAutoScroll((prev) => !prev)}
                  title="Toggle Auto-scroll"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: autoScroll ? '#2563eb' : '#64748b',
                    fontSize: '0.7rem',
                    cursor: 'pointer',
                    fontWeight: 500,
                    marginRight: 4,
                  }}
                >
                  Auto-scroll: {autoScroll ? 'ON' : 'OFF'}
                </button>
              )}

              {/* Refresh Logs */}
              {activeTab !== 'terminal' && onRefreshLogs && (
                <button
                  type="button"
                  onClick={onRefreshLogs}
                  disabled={isRefreshing}
                  title="Refresh logs"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#64748b',
                    cursor: 'pointer',
                    padding: 3,
                    borderRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <RotateCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
                </button>
              )}

              {/* Copy Logs */}
              {activeTab !== 'terminal' && (
                <button
                  type="button"
                  onClick={handleCopyLogs}
                  title="Copy output logs"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#64748b',
                    cursor: 'pointer',
                    padding: 3,
                    borderRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <Copy size={12} />
                </button>
              )}
            </>
          )}

          {/* Minimize / Expand Toggle */}
          <button
            type="button"
            onClick={onToggleCollapsed}
            title={isCollapsed ? 'Expand drawer' : 'Minimize drawer'}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              padding: 3,
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {isCollapsed ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>

          {/* Maximize Toggle */}
          {!isCollapsed && (
            <button
              type="button"
              onClick={toggleMaximize}
              title={isMaximized ? 'Restore height' : 'Maximize output'}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                padding: 3,
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {isMaximized ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
            </button>
          )}

          {/* Close button */}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              title="Close drawer"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                padding: 3,
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* ── Output Body ── */}
      {!isCollapsed && (
        <div style={{ flex: 1, minHeight: 0, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {activeTab === 'terminal' ? (
            <div style={{ flex: 1, minHeight: 0, height: '100%', overflow: 'hidden', background: '#090d16' }}>
              <DevTerminal
                appId={appId || ''}
                appName={appName || 'app'}
                workspaceId={workspaceId}
                workspaceName={workspaceName}
                isDevPodRunning={isDevPodRunning ?? isDevRunning}
                agent="bash"
                fullHeight={true}
              />
            </div>
          ) : (
            <div
              ref={scrollRef}
              style={{
                flex: 1,
                minHeight: 0,
                padding: '8px 14px',
                overflowY: 'auto',
                background: '#ffffff',
                fontFamily:
                  'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                fontSize: '0.74rem',
                lineHeight: 1.6,
                color: activeTab === 'console' ? '#b45309' : '#334155',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {activeTab === 'devServer' ? (
                devLogs || 'Starting dev server output stream...'
              ) : (
                consoleLogs
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
