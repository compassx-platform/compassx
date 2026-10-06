import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Clock,
  Plus,
  Terminal,
  Trash2,
  Search,
  Check,
  X,
  Bot,
  Sparkles,
} from 'lucide-react';
import type { DevSession } from '../../hooks/useApps';

export interface SessionHistoryPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: DevSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onOpenNewSession: () => void;
  onOpenNewShell?: () => void;
  onDeleteSession?: (sessionId: string) => void;
  disabled?: boolean;
}

function timeAgo(dateString?: string): string {
  if (!dateString) return 'recently';
  try {
    const diff = (Date.now() - new Date(dateString).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch (_) {
    return 'recently';
  }
}

const AGENT_LABELS: Record<string, string> = {
  opencode: 'OpenCode',
  pi: 'Pi CLI',
  antigravity: 'Antigravity',
  bash: 'Bash Shell',
};

export function SessionHistoryPopover({
  isOpen,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenNewSession,
  onOpenNewShell,
  onDeleteSession,
  disabled = false,
}: SessionHistoryPopoverProps) {
  const [search, setSearch] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  // Filtered sessions
  const filtered = useMemo(() => {
    if (!search.trim()) return sessions;
    const q = search.toLowerCase().trim();
    return sessions.filter(
      (s) => s.title.toLowerCase().includes(q) || s.agent.toLowerCase().includes(q)
    );
  }, [sessions, search]);

  if (!isOpen) return null;

  return (
    <div
      ref={popoverRef}
      style={{
        position: 'absolute',
        top: 'calc(100% + 6px)',
        right: 0,
        zIndex: 1000,
        width: 360,
        maxWidth: 420,
        background: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: 10,
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04)',
        overflow: 'hidden',
        animation: 'fadeIn 0.12s ease-out',
        padding: '6px',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* ── Header: Title & Count ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 8px 6px',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Clock size={13} style={{ color: '#6b7280' }} />
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#374151' }}>
            Sessions
          </span>
          <span
            style={{
              fontSize: '0.68rem',
              color: '#6b7280',
              background: '#f3f4f6',
              padding: '1px 6px',
              borderRadius: 999,
              fontWeight: 500,
            }}
          >
            {sessions.length}
          </span>
        </div>

        <button
          type="button"
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#9ca3af',
            cursor: 'pointer',
            padding: 2,
            borderRadius: 4,
            display: 'flex',
            alignItems: 'center',
          }}
          title="Close"
        >
          <X size={13} />
        </button>
      </div>

      {/* ── Search Input (if > 3 sessions) ── */}
      {sessions.length > 3 && (
        <div style={{ padding: '0 4px 6px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#f9fafb',
              border: '1px solid #e5e7eb',
              borderRadius: 6,
              padding: '3px 8px',
            }}
          >
            <Search size={12} style={{ color: '#9ca3af' }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter sessions..."
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                fontSize: '0.74rem',
                color: '#111827',
                padding: '2px 0',
              }}
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#9ca3af',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={11} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Recents Label ── */}
      <div
        style={{
          padding: '2px 8px 4px',
          fontSize: '0.7rem',
          fontWeight: 500,
          color: '#6b7280',
          userSelect: 'none',
        }}
      >
        Recents
      </div>

      {/* ── Sessions List ── */}
      <div
        style={{
          maxHeight: 260,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {filtered.length === 0 ? (
          <div
            style={{
              padding: '16px 8px',
              textAlign: 'center',
              color: '#9ca3af',
              fontSize: '0.75rem',
            }}
          >
            {search ? 'No matching sessions' : 'No active sessions'}
          </div>
        ) : (
          filtered.map((s) => {
            const isActive = s.id === activeSessionId;
            const isDeleting = confirmDeleteId === s.id;
            const isHovered = hoveredSessionId === s.id;
            const agentName = AGENT_LABELS[s.agent] || s.agent || 'Agent';

            return (
              <div
                key={s.id}
                onClick={() => {
                  onSelectSession(s.id);
                  onClose();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  borderRadius: 6,
                  border: isActive ? '1.5px solid #111827' : '1.5px solid transparent',
                  background: isActive ? '#f3f4f6' : isHovered ? '#f9fafb' : 'transparent',
                  cursor: isActive ? 'default' : 'pointer',
                  transition: 'all 0.12s ease',
                  gap: 8,
                }}
                onMouseEnter={() => setHoveredSessionId(s.id)}
                onMouseLeave={() => setHoveredSessionId(null)}
              >
                {/* Left: Agent Icon + Title & Details */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                  {s.agent === 'bash' ? (
                    <Terminal
                      size={14}
                      style={{
                        color: isActive ? '#111827' : '#6b7280',
                        flexShrink: 0,
                      }}
                    />
                  ) : (
                    <Bot
                      size={14}
                      style={{
                        color: isActive ? '#111827' : '#6b7280',
                        flexShrink: 0,
                      }}
                    />
                  )}

                  <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
                    <span
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: isActive ? 600 : 500,
                        color: isActive ? '#111827' : '#374151',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={s.title}
                    >
                      {s.title}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 1 }}>
                      <span
                        style={{
                          fontSize: '0.65rem',
                          fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                          color: '#4b5563',
                          background: '#e5e7eb',
                          padding: '0 4px',
                          borderRadius: 3,
                        }}
                      >
                        {agentName}
                      </span>
                      <span style={{ fontSize: '0.66rem', color: '#9ca3af' }}>
                        {timeAgo(s.created_at)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right: Active Checkmark or Delete Button */}
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {onDeleteSession && (isHovered || isDeleting) && (
                    isDeleting ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                        <button
                          type="button"
                          onClick={() => {
                            onDeleteSession(s.id);
                            setConfirmDeleteId(null);
                          }}
                          style={{
                            background: '#fee2e2',
                            color: '#dc2626',
                            border: '1px solid #fecaca',
                            borderRadius: 4,
                            padding: '2px 6px',
                            fontSize: '0.68rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Delete
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(null)}
                          style={{
                            background: 'transparent',
                            color: '#6b7280',
                            border: 'none',
                            cursor: 'pointer',
                            padding: 2,
                            display: 'flex',
                            alignItems: 'center',
                          }}
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(s.id)}
                        title="Delete session"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: '#9ca3af',
                          cursor: 'pointer',
                          padding: 3,
                          borderRadius: 4,
                          display: 'flex',
                          alignItems: 'center',
                          transition: 'all 0.12s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = '#ef4444';
                          e.currentTarget.style.background = '#fee2e2';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = '#9ca3af';
                          e.currentTarget.style.background = 'transparent';
                        }}
                      >
                        <Trash2 size={13} />
                      </button>
                    )
                  )}

                  {isActive && !isDeleting && (
                    <span title="Active Session" style={{ display: 'inline-flex', alignItems: 'center' }}>
                      <Check
                        size={14}
                        strokeWidth={2.5}
                        style={{ color: '#111827', marginLeft: 2 }}
                      />
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Divider ── */}
      <div style={{ height: 1, background: '#f3f4f6', margin: '4px 0' }} />

      {/* ── Action Rows (Matching SandboxSelector Style) ── */}
      {/* 1. New Agent Session */}
      <div
        onClick={() => {
          if (!disabled) {
            onClose();
            onOpenNewSession();
          }
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 8px',
          borderRadius: 6,
          cursor: disabled ? 'not-allowed' : 'pointer',
          color: '#111827',
          fontSize: '0.78rem',
          fontWeight: 500,
          transition: 'background 0.12s ease',
          opacity: disabled ? 0.6 : 1,
        }}
        onMouseEnter={(e) => {
          if (!disabled) e.currentTarget.style.background = '#f9fafb';
        }}
        onMouseLeave={(e) => {
          if (!disabled) e.currentTarget.style.background = 'transparent';
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Plus size={14} style={{ color: '#4b5563' }} />
          <span>New agent session</span>
        </div>
        <span
          style={{
            fontSize: '0.67rem',
            color: '#6b7280',
            background: '#f1f5f9',
            padding: '1px 6px',
            borderRadius: 4,
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
          }}
        >
          OpenCode / Pi / AGY
        </span>
      </div>

      {/* 2. New Bash Shell */}
      {onOpenNewShell && (
        <div
          onClick={() => {
            if (!disabled) {
              onClose();
              onOpenNewShell();
            }
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 8px',
            borderRadius: 6,
            cursor: disabled ? 'not-allowed' : 'pointer',
            color: '#111827',
            fontSize: '0.78rem',
            fontWeight: 500,
            transition: 'background 0.12s ease',
            opacity: disabled ? 0.6 : 1,
          }}
          onMouseEnter={(e) => {
            if (!disabled) e.currentTarget.style.background = '#f9fafb';
          }}
          onMouseLeave={(e) => {
            if (!disabled) e.currentTarget.style.background = 'transparent';
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Terminal size={14} style={{ color: '#4b5563' }} />
            <span>New bash shell</span>
          </div>
          <span
            style={{
              fontSize: '0.67rem',
              color: '#6b7280',
              background: '#f1f5f9',
              padding: '1px 6px',
              borderRadius: 4,
              fontFamily: 'ui-monospace, SFMono-Regular, monospace',
            }}
          >
            Alt+N
          </span>
        </div>
      )}
    </div>
  );
}
