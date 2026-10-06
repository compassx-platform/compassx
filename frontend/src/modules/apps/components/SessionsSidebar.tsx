import React, { useState, useMemo } from 'react';
import {
  Plus,
  Trash2,
  Search,
  Loader2,
  PanelLeftClose,
  Maximize2,
  Minimize2,
  Terminal,
} from 'lucide-react';
import type { DevSession } from '../hooks/useApps';
import { AGENT_OPTIONS } from '../pages/AppBuildPage';

export interface SessionsSidebarProps {
  sessions: DevSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onOpenNewSession: () => void;
  onOpenNewShell?: () => void;
  onDeleteSession?: (sessionId: string) => void;
  disabled?: boolean;
  isSwitching?: boolean;
  onClose?: () => void;
  isMaximized?: boolean;
  onToggleMaximized?: () => void;
}

const AGENT_NAMES: Record<string, string> = {
  opencode: 'OpenCode',
  pi: 'Pi',
  antigravity: 'Antigravity',
  bash: 'Bash Shell',
};


export function SessionsSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenNewSession,
  onOpenNewShell,
  onDeleteSession,
  disabled = false,
  isSwitching = false,
  onClose,
  isMaximized = false,
  onToggleMaximized,
}: SessionsSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Filter sessions based on search
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const query = searchQuery.toLowerCase().trim();
    return sessions.filter(
      (s) =>
        s.title.toLowerCase().includes(query) ||
        s.agent.toLowerCase().includes(query)
    );
  }, [sessions, searchQuery]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        background: '#ffffff',
        color: '#0f172a',
        fontFamily: 'inherit',
        overflow: 'hidden',
      }}
    >
      {/* ── Top Header ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px',
          borderBottom: '1px solid #e2e8f0',
          background: '#ffffff',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {/* New Session Button */}
          <button
            type="button"
            onClick={onOpenNewSession}
            disabled={disabled}
            title="Start New Session with an AI Agent"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '3px 7px',
              borderRadius: 5,
              border: 'none',
              background: '#1B6EF3',
              color: '#ffffff',
              fontSize: '0.69rem',
              fontWeight: 600,
              cursor: disabled ? 'not-allowed' : 'pointer',
              boxShadow: '0 1px 2px rgba(27, 110, 243, 0.2)',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (!disabled) e.currentTarget.style.background = '#1558C7';
            }}
            onMouseLeave={(e) => {
              if (!disabled) e.currentTarget.style.background = '#1B6EF3';
            }}
          >
            <Plus size={11} strokeWidth={2.5} />
            <span>New Session</span>
          </button>

          {/* New Shell Button */}
          {onOpenNewShell && (
            <button
              type="button"
              onClick={onOpenNewShell}
              disabled={disabled}
              title="Start Interactive Bash Shell (Ctrl+Alt+T)"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '3px 7px',
                borderRadius: 5,
                border: '1px solid #cbd5e1',
                background: '#f8fafc',
                color: '#334155',
                fontSize: '0.69rem',
                fontWeight: 600,
                cursor: disabled ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!disabled) {
                  e.currentTarget.style.background = '#f1f5f9';
                  e.currentTarget.style.color = '#0f172a';
                }
              }}
              onMouseLeave={(e) => {
                if (!disabled) {
                  e.currentTarget.style.background = '#f8fafc';
                  e.currentTarget.style.color = '#334155';
                }
              }}
            >
              <Terminal size={11} strokeWidth={2.5} color="#d97706" />
              <span>Shell</span>
            </button>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {/* Expand / Minimize Width Button */}
          {onToggleMaximized && (
            <button
              type="button"
              onClick={onToggleMaximized}
              title={isMaximized ? 'Restore Width' : 'Expand Width'}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 24,
                height: 24,
                borderRadius: 5,
                border: 'none',
                background: 'transparent',
                color: '#64748b',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#0f172a';
                e.currentTarget.style.background = '#f1f5f9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#64748b';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              {isMaximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          )}

          {/* Collapse Sidebar Button */}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              title="Collapse Sessions Sidebar"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 24,
                height: 24,
                borderRadius: 5,
                border: 'none',
                background: 'transparent',
                color: '#64748b',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#0f172a';
                e.currentTarget.style.background = '#f1f5f9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#64748b';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <PanelLeftClose size={13} />
            </button>
          )}
        </div>
      </div>

      {/* ── Search Bar (Shown when 4+ sessions exist) ── */}
      {sessions.length >= 4 && (
        <div
          style={{
            padding: '6px 10px 4px',
            borderBottom: '1px solid #f1f5f9',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '3px 7px',
              borderRadius: 5,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
            }}
          >
            <Search size={11} color="#94a3b8" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter sessions..."
              style={{
                flex: 1,
                minWidth: 0,
                border: 'none',
                background: 'transparent',
                color: '#0f172a',
                fontSize: '0.72rem',
                outline: 'none',
              }}
            />
          </div>
        </div>
      )}

      {/* ── Sessions Single-Line List ── */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '6px 6px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {filteredSessions.length === 0 ? (
          <div
            style={{
              padding: '24px 10px',
              textAlign: 'center',
              color: '#94a3b8',
              fontSize: '0.74rem',
            }}
          >
            {searchQuery ? 'No matching sessions' : 'No sessions yet'}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            const isHovered = hoveredSessionId === session.id;
            const fallbackAgentConfig = AGENT_OPTIONS.find((a) => a.id === session.agent);
            const agentName = AGENT_NAMES[session.agent] || fallbackAgentConfig?.name || session.agent;
            const isConfirmingDelete = deleteConfirmId === session.id;

            return (
              <div
                key={session.id}
                onClick={() => !disabled && onSelectSession(session.id)}
                onMouseEnter={() => setHoveredSessionId(session.id)}
                onMouseLeave={() => setHoveredSessionId(null)}
                style={{
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  height: 32,
                  minHeight: 32,
                  padding: '0 8px',
                  borderRadius: 6,
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  border: isActive
                    ? '1px solid #bfdbfe'
                    : isHovered
                    ? '1px solid #e2e8f0'
                    : '1px solid transparent',
                  background: isActive
                    ? '#EBF2FF'
                    : isHovered
                    ? '#f8fafc'
                    : 'transparent',
                  transition: 'all 0.12s ease',
                  userSelect: 'none',
                }}
              >
                {/* Left Side: Session Title */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    flex: 1,
                    minWidth: 0,
                    marginRight: 6,
                  }}
                >
                  {session.agent === 'bash' && (
                    <Terminal
                      size={12}
                      style={{
                        marginRight: 6,
                        color: isActive ? '#d97706' : '#b45309',
                        flexShrink: 0,
                      }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: '0.78rem',
                      fontWeight: isActive ? 600 : 475,
                      color: isActive ? '#1558C7' : '#334155',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={session.title}
                  >
                    {session.title}
                  </span>
                </div>

                {/* Right Side: Shown on Hover (Agent Name + Delete Action) or when Active/Switching */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    flexShrink: 0,
                  }}
                >
                  {/* Switching spinner if this session is switching */}
                  {isActive && isSwitching && (
                    <Loader2 size={11} className="spin" style={{ color: '#1B6EF3' }} />
                  )}

                  {/* Agent Name: Visible ONLY on Hover (Simple text, no box, no color) */}
                  {(isHovered || isConfirmingDelete) && (
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 450,
                        color: '#64748b',
                        flexShrink: 0,
                        userSelect: 'none',
                      }}
                    >
                      {agentName}
                    </span>
                  )}

                  {/* Inline Delete Button: Visible ONLY on Hover */}
                  {onDeleteSession && (isHovered || isConfirmingDelete) && (
                    <div onClick={(e) => e.stopPropagation()} style={{ display: 'inline-flex', alignItems: 'center' }}>
                      {isConfirmingDelete ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                          <button
                            type="button"
                            onClick={() => {
                              onDeleteSession(session.id);
                              setDeleteConfirmId(null);
                            }}
                            style={{
                              padding: '1px 5px',
                              borderRadius: 3,
                              background: '#ef4444',
                              color: '#ffffff',
                              border: 'none',
                              fontSize: '0.6rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            Del
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteConfirmId(null)}
                            style={{
                              padding: '1px 4px',
                              borderRadius: 3,
                              background: '#ffffff',
                              color: '#64748b',
                              border: '1px solid #cbd5e1',
                              fontSize: '0.6rem',
                              cursor: 'pointer',
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setDeleteConfirmId(session.id)}
                          title="Delete Session"
                          style={{
                            padding: '2px',
                            borderRadius: 4,
                            background: 'transparent',
                            border: 'none',
                            color: '#94a3b8',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            transition: 'color 0.15s ease',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.color = '#ef4444';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.color = '#94a3b8';
                          }}
                        >
                          <Trash2 size={11} />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
