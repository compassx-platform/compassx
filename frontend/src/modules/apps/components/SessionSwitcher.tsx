import React, { useState, useRef, useEffect } from 'react';
import {
  ChevronDown,
  Plus,
  Terminal,
  Lock,
  Trash2,
  Check,
  Clock,
  Sparkles,
  Layers,
  Loader2,
} from 'lucide-react';
import type { DevSession } from '../hooks/useApps';
import { AGENT_OPTIONS, type SupportedAgent } from '../pages/AppBuildPage';

interface SessionSwitcherProps {
  sessions: DevSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onOpenNewSession: () => void;
  onDeleteSession?: (sessionId: string) => void;
  disabled?: boolean;
  isSwitching?: boolean;
}

export function SessionSwitcher({
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenNewSession,
  onDeleteSession,
  disabled = false,
  isSwitching = false,
}: SessionSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];
  const activeAgentConfig = AGENT_OPTIONS.find((a) => a.id === activeSession?.agent);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const formatRelativeTime = (dateStr?: string | null) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      const diffSecs = Math.floor((Date.now() - date.getTime()) / 1000);
      if (diffSecs < 60) return 'just now';
      const diffMins = Math.floor(diffSecs / 60);
      if (diffMins < 60) return `${diffMins}m ago`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  return (
    <div
      ref={dropdownRef}
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
      }}
    >
      {/* ── Main Session Trigger Bar ── */}
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid var(--color-border, #334155)',
          borderRadius: 8,
          padding: '2px 4px',
          gap: 6,
        }}
      >
        <button
          type="button"
          onClick={() => !disabled && setIsOpen((prev) => !prev)}
          disabled={disabled}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '3px 8px',
            background: 'transparent',
            border: 'none',
            color: 'var(--color-text, #f8fafc)',
            fontSize: '0.78rem',
            fontWeight: 500,
            cursor: disabled ? 'not-allowed' : 'pointer',
            borderRadius: 6,
            transition: 'background 0.15s ease',
          }}
          title="Switch Active Dev Session"
        >
          {/* Active status pulse or loader */}
          {isSwitching ? (
            <Loader2
              size={11}
              className="spin"
              color="#818cf8"
              style={{ flexShrink: 0 }}
            />
          ) : (
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#22c55e',
                boxShadow: '0 0 6px rgba(34, 197, 94, 0.6)',
                flexShrink: 0,
              }}
            />
          )}

          {/* Session Title */}
          <span
            style={{
              maxWidth: 160,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontWeight: 600,
              opacity: isSwitching ? 0.75 : 1,
            }}
          >
            {isSwitching ? 'Loading session...' : (activeSession ? activeSession.title : 'No Session')}
          </span>

          {/* Locked Agent Badge */}
          {activeAgentConfig && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '1px 6px',
                borderRadius: 4,
                fontSize: '0.68rem',
                fontWeight: 650,
                background: activeAgentConfig.accentBg,
                color: activeAgentConfig.color,
                border: `1px solid ${activeAgentConfig.borderColor}`,
              }}
              title={`Agent locked: ${activeAgentConfig.name} (${activeAgentConfig.binary}). 1 Agent per session.${activeSession?.model ? ` Model: ${activeSession.model}` : ''}`}
            >
              <Lock size={9} style={{ opacity: 0.8 }} />
              <span>{activeAgentConfig.name}</span>
              {activeSession?.model && (
                <span style={{ opacity: 0.75, fontWeight: 500, fontSize: '0.64rem' }}>
                  · {activeSession.model}
                </span>
              )}
            </span>
          )}

          <ChevronDown
            size={13}
            color="var(--color-text-muted, #94a3b8)"
            style={{
              transform: isOpen ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.15s ease',
            }}
          />
        </button>

        {/* Quick "+ New Session" Button */}
        <button
          type="button"
          onClick={onOpenNewSession}
          disabled={disabled}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 24,
            height: 24,
            borderRadius: 5,
            border: '1px solid rgba(99, 102, 241, 0.4)',
            background: 'rgba(99, 102, 241, 0.15)',
            color: '#818cf8',
            cursor: disabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s ease',
          }}
          title="Create New Dev Session"
        >
          <Plus size={13} />
        </button>
      </div>

      {/* ── Dropdown Menu ── */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            width: 320,
            background: 'var(--color-surface, #1e293b)',
            border: '1px solid var(--color-border, #334155)',
            borderRadius: 10,
            boxShadow: '0 15px 35px -5px rgba(0, 0, 0, 0.65)',
            padding: 6,
            zIndex: 100,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            animation: 'fadeIn 0.15s ease-out',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '6px 8px 6px 10px',
              borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                color: 'var(--color-text-muted, #94a3b8)',
                textTransform: 'uppercase',
                letterSpacing: '0.4px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
              }}
            >
              <Layers size={11} />
              App Sessions ({sessions.length})
            </span>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenNewSession();
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: '0.7rem',
                fontWeight: 600,
                background: 'rgba(99, 102, 241, 0.2)',
                color: '#a5b4fc',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <Plus size={11} />
              New
            </button>
          </div>

          {/* Session Items List */}
          <div
            style={{
              maxHeight: 240,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            {sessions.map((sess) => {
              const isSelected = sess.id === activeSession?.id;
              const agentCfg = AGENT_OPTIONS.find((a) => a.id === sess.agent);

              return (
                <div
                  key={sess.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 10px',
                    borderRadius: 6,
                    background: isSelected
                      ? 'rgba(99, 102, 241, 0.15)'
                      : 'transparent',
                    border: isSelected
                      ? '1px solid rgba(99, 102, 241, 0.3)'
                      : '1px solid transparent',
                    cursor: 'pointer',
                    transition: 'all 0.12s ease',
                  }}
                  onClick={() => {
                    onSelectSession(sess.id);
                    setIsOpen(false);
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      flex: 1,
                      minWidth: 0,
                    }}
                  >
                    {/* Agent Pill */}
                    {agentCfg ? (
                      <span
                        style={{
                          fontSize: '0.62rem',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: 4,
                          background: agentCfg.accentBg,
                          color: agentCfg.color,
                          border: `1px solid ${agentCfg.borderColor}`,
                          flexShrink: 0,
                        }}
                      >
                        {agentCfg.name}
                      </span>
                    ) : (
                      <Terminal size={12} color="#94a3b8" />
                    )}

                    {/* Title & Metadata */}
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        minWidth: 0,
                        flex: 1,
                      }}
                    >
                      <span
                        style={{
                          fontSize: '0.78rem',
                          fontWeight: isSelected ? 650 : 500,
                          color: isSelected
                            ? '#f8fafc'
                            : 'var(--color-text, #cbd5e1)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {sess.title}
                      </span>
                      <span
                        style={{
                          fontSize: '0.66rem',
                          color: 'var(--color-text-muted, #64748b)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          marginTop: 1,
                        }}
                      >
                        <Clock size={9} />
                        {formatRelativeTime(sess.last_active_at || sess.created_at)}
                        {sess.model && (
                          <span style={{ color: '#818cf8', marginLeft: 4 }}>
                            · {sess.model}
                          </span>
                        )}
                      </span>
                    </div>
                  </div>

                  {/* Actions / Status */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      flexShrink: 0,
                    }}
                  >
                    {isSelected && (
                      isSwitching ? (
                        <Loader2 size={13} className="spin" color="#818cf8" />
                      ) : (
                        <Check size={14} color="#818cf8" strokeWidth={2.5} />
                      )
                    )}

                    {/* Delete session button (only if more than 1 session) */}
                    {sessions.length > 1 && onDeleteSession && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (
                            window.confirm(
                              `Delete session "${sess.title}"? Background process will be terminated.`,
                            )
                          ) {
                            onDeleteSession(sess.id);
                          }
                        }}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          padding: 4,
                          color: 'var(--color-text-muted, #64748b)',
                          cursor: 'pointer',
                          borderRadius: 4,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = '#f87171';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = 'var(--color-text-muted, #64748b)';
                        }}
                        title="Delete Session"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bottom create session button */}
          <div
            style={{
              paddingTop: 4,
              borderTop: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenNewSession();
              }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                padding: '7px 10px',
                background: 'rgba(99, 102, 241, 0.1)',
                border: '1px dashed rgba(99, 102, 241, 0.35)',
                borderRadius: 6,
                color: '#a5b4fc',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(99, 102, 241, 0.2)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(99, 102, 241, 0.1)';
              }}
            >
              <Sparkles size={12} />
              <span>Create New Dev Session</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
