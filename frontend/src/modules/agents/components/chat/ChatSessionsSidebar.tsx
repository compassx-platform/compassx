import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import {
  SquarePen,
  PanelLeftClose,
  PanelLeftOpen,
  MessageSquare,
  SlidersHorizontal,
  Terminal,
  Search,
  Check,
  MoreVertical,
  Trash2,
  X as XIcon,
  Zap,
  Loader2,
  History,
  Database,
} from 'lucide-react';
import type { ChatSession } from '@/modules/agents/hooks/useChat';
import { CatalogExplorerTree } from '@/modules/data/components/CatalogExplorerTree';

export function formatRelativeTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    if (diffMs < 0) return 'Just now';

    const diffMins = Math.floor(diffMs / (1000 * 60));
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w`;

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = months[d.getMonth()];
    const day = d.getDate();
    return `${month} ${day}`;
  } catch {
    return '';
  }
}

interface SessionListItemProps {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
}

export function SessionListItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: SessionListItemProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

  const title = session.title?.trim() || `Session #${session.id}`;
  const snippet = session.last_message?.trim() || 'No messages yet';
  const timeFormatted = formatRelativeTime(session.updated_at || session.created_at);
  const hasFileChanges = Boolean(session.has_changes || (session.files_changed_count ?? 0) > 0);

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        padding: '9px 12px',
        borderRadius: 8,
        cursor: 'pointer',
        background: isActive
          ? '#f1f5f9'
          : isHovered
          ? '#f8fafc'
          : 'transparent',
        transition: 'background 0.15s ease',
        marginBottom: 2,
        position: 'relative',
      }}
    >
      <div
        style={{
          width: 14,
          height: 14,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          paddingTop: 3,
          flexShrink: 0,
        }}
      >
        {hasFileChanges ? (
          <Check size={13} color="#16a34a" title="Files modified in this session" />
        ) : null}
      </div>

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
          <span
            style={{
              fontSize: '0.81rem',
              fontWeight: isActive ? 600 : 500,
              color: isActive ? '#0f172a' : '#1e293b',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flex: 1,
            }}
          >
            {title}
          </span>
          <span
            style={{
              fontSize: '0.71rem',
              color: '#94a3b8',
              flexShrink: 0,
            }}
          >
            {timeFormatted}
          </span>
        </div>

        <div
          style={{
            fontSize: '0.73rem',
            color: '#64748b',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            lineHeight: 1.35,
          }}
        >
          {snippet}
        </div>
      </div>

      {(isHovered || menuOpen) && (
        <div
          ref={menuRef}
          onClick={(e) => e.stopPropagation()}
          style={{ position: 'relative', flexShrink: 0, paddingTop: 1 }}
        >
          <button
            type="button"
            onClick={() => setMenuOpen(!menuOpen)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '2px',
              color: '#94a3b8',
              display: 'flex',
              alignItems: 'center',
              borderRadius: 4,
            }}
            title="Session options"
          >
            <MoreVertical size={13} />
          </button>
          {menuOpen && (
            <div
              style={{
                position: 'absolute',
                right: 0,
                top: 20,
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 6,
                boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                zIndex: 50,
                minWidth: 100,
                padding: 4,
              }}
            >
              <button
                type="button"
                onClick={(e) => {
                  setMenuOpen(false);
                  onDelete(e);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  width: '100%',
                  padding: '5px 8px',
                  border: 'none',
                  background: 'none',
                  color: '#dc2626',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  borderRadius: 4,
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#fee2e2')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
              >
                <Trash2 size={12} />
                <span>Delete</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ChatSessionsSidebarProps {
  agent: any;
  sessions: ChatSession[];
  activeSessionId: number | null;
  onSelectSession: (id: number) => void;
  onNewSession: () => void;
  onDeleteSession: (e: React.MouseEvent, s: ChatSession) => void;
  mainView: 'chat' | 'customizations' | 'logs';
  onSetMainView: (view: 'chat' | 'customizations' | 'logs') => void;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  sidebarWidth?: number;
  onSidebarWidthChange?: (w: number) => void;
  sidebarMode?: 'chats' | 'catalog';
  onSidebarModeChange?: (mode: 'chats' | 'catalog') => void;
  onInsertTable?: (identifier: string) => void;
}

export function ChatSessionsSidebar({
  agent,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  mainView,
  onSetMainView,
  isSidebarOpen,
  onToggleSidebar,
  sidebarWidth = 260,
  onSidebarWidthChange,
  sidebarMode: propSidebarMode,
  onSidebarModeChange,
  onInsertTable,
}: ChatSessionsSidebarProps) {
  const [internalSidebarMode, setInternalSidebarMode] = useState<'chats' | 'catalog'>('chats');
  const currentSidebarMode = propSidebarMode ?? internalSidebarMode;
  const setSidebarMode = (mode: 'chats' | 'catalog') => {
    if (onSidebarModeChange) {
      onSidebarModeChange(mode);
    } else {
      setInternalSidebarMode(mode);
    }
  };

  const [searchQuery, setSearchQuery] = useState('');
  const [visibleSessionLimit, setVisibleSessionLimit] = useState(25);
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);
  const [agentMenuOpen, setAgentMenuOpen] = useState(false);
  const agentMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (agentMenuRef.current && !agentMenuRef.current.contains(e.target as Node)) {
        setAgentMenuOpen(false);
      }
    }
    if (agentMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [agentMenuOpen]);

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter((s) => {
      const title = (s.title ?? '').toLowerCase();
      const lastMsg = (s.last_message ?? '').toLowerCase();
      return title.includes(q) || lastMsg.includes(q);
    });
  }, [sessions, searchQuery]);

  const visibleSessions = useMemo(
    () => filteredSessions.slice(0, visibleSessionLimit),
    [filteredSessions, visibleSessionLimit]
  );

  const startSidebarResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsResizingSidebar(true);
      const startX = e.clientX;
      const startW = sidebarWidth;

      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        const newW = Math.max(180, Math.min(500, startW + delta));
        onSidebarWidthChange?.(newW);
      };

      const onMouseUp = () => {
        setIsResizingSidebar(false);
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      };

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    },
    [sidebarWidth, onSidebarWidthChange]
  );

  const [hoverPopoverOpen, setHoverPopoverOpen] = useState(false);
  const popoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleRailChatsMouseEnter = () => {
    if (popoverTimeoutRef.current) {
      clearTimeout(popoverTimeoutRef.current);
      popoverTimeoutRef.current = null;
    }
    setHoverPopoverOpen(true);
  };

  const handleRailChatsMouseLeave = () => {
    popoverTimeoutRef.current = setTimeout(() => {
      setHoverPopoverOpen(false);
    }, 200);
  };

  // ── Collapsed Vertical Icon Rail (Matching Image 2) ────────────────────────
  if (!isSidebarOpen) {
    return (
      <div
        style={{
          width: 44,
          borderRight: '1px solid #e2e8f0',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          background: '#ffffff',
          height: '100%',
          flexShrink: 0,
          padding: '12px 0 16px',
          zIndex: 10,
          position: 'relative',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, width: '100%' }}>
          {/* 1. Expand sidebar */}
          <button
            type="button"
            onClick={onToggleSidebar}
            title="Expand sidebar"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px',
              color: '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
          >
            <PanelLeftOpen size={16} />
          </button>

          {/* 2. New chat */}
          <button
            type="button"
            onClick={onNewSession}
            title="New chat"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px',
              color: '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
          >
            <SquarePen size={16} />
          </button>

          {/* 3. Customizations */}
          <button
            type="button"
            onClick={() => onSetMainView(mainView === 'customizations' ? 'chat' : 'customizations')}
            title="Customizations"
            style={{
              background: mainView === 'customizations' ? '#f1f5f9' : 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px',
              color: mainView === 'customizations' ? '#0f172a' : '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
            onMouseLeave={(e) => (e.currentTarget.style.color = mainView === 'customizations' ? '#0f172a' : '#475569')}
          >
            <SlidersHorizontal size={16} />
          </button>

          {/* 4. Session Logs */}
          <button
            type="button"
            onClick={() => onSetMainView(mainView === 'logs' ? 'chat' : 'logs')}
            title="Session Logs"
            style={{
              background: mainView === 'logs' ? '#f1f5f9' : 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px',
              color: mainView === 'logs' ? '#0f172a' : '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
            onMouseLeave={(e) => (e.currentTarget.style.color = mainView === 'logs' ? '#0f172a' : '#475569')}
          >
            <Terminal size={16} />
          </button>

          {/* 5. Chat history with Hover Popover */}
          <div
            style={{ position: 'relative' }}
            onMouseEnter={handleRailChatsMouseEnter}
            onMouseLeave={handleRailChatsMouseLeave}
          >
            <button
              type="button"
              onClick={() => {
                if (!isSidebarOpen) onToggleSidebar();
                setSidebarMode('chats');
              }}
              title="Chat History"
              style={{
                background: currentSidebarMode === 'chats' ? '#f1f5f9' : 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '6px',
                color: currentSidebarMode === 'chats' ? '#0f172a' : '#475569',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 6,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
              onMouseLeave={(e) => (e.currentTarget.style.color = currentSidebarMode === 'chats' ? '#0f172a' : '#475569')}
            >
              <MessageSquare size={16} />
            </button>

            {/* Quick Switch Popover on Hover */}
            {hoverPopoverOpen && (
              <div
                style={{
                  position: 'absolute',
                  left: 36,
                  top: -8,
                  width: 290,
                  maxHeight: 380,
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 10,
                  boxShadow: '0 10px 28px rgba(0, 0, 0, 0.14)',
                  zIndex: 9999,
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  animation: 'fadeIn 0.15s ease',
                }}
                onMouseEnter={handleRailChatsMouseEnter}
                onMouseLeave={handleRailChatsMouseLeave}
              >
                {/* Popover Header */}
                <div
                  style={{
                    padding: '10px 12px 8px',
                    borderBottom: '1px solid #f1f5f9',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: '#f8fafc',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <MessageSquare size={13} color="#2563eb" />
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#0f172a' }}>
                      Recent Chats
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setHoverPopoverOpen(false);
                      onNewSession();
                    }}
                    title="Start new chat"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      fontSize: '0.72rem',
                      fontWeight: 500,
                      color: '#2563eb',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      borderRadius: 4,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#eff6ff')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                  >
                    <SquarePen size={12} />
                    <span>New</span>
                  </button>
                </div>

                {/* Popover Sessions List */}
                <div
                  className="sidebar-hover-scrollbar"
                  style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '6px 8px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                    maxHeight: 280,
                  }}
                >
                  {sessions.length === 0 ? (
                    <div style={{ padding: '16px 8px', fontSize: '0.75rem', color: '#94a3b8', textAlign: 'center' }}>
                      No chats yet
                    </div>
                  ) : (
                    sessions.slice(0, 10).map((s) => {
                      const isItemActive = activeSessionId === s.id;
                      const title = s.title?.trim() || `Session #${s.id}`;
                      const timeStr = formatRelativeTime(s.updated_at || s.created_at);
                      return (
                        <div
                          key={s.id}
                          onClick={() => {
                            setHoverPopoverOpen(false);
                            onSelectSession(s.id);
                          }}
                          style={{
                            padding: '6px 8px',
                            borderRadius: 6,
                            cursor: 'pointer',
                            background: isItemActive ? '#f1f5f9' : 'transparent',
                            transition: 'background 0.12s ease',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 2,
                          }}
                          onMouseEnter={(e) => {
                            if (!isItemActive) e.currentTarget.style.background = '#f8fafc';
                          }}
                          onMouseLeave={(e) => {
                            if (!isItemActive) e.currentTarget.style.background = 'transparent';
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                            <span
                              style={{
                                fontSize: '0.78rem',
                                fontWeight: isItemActive ? 600 : 500,
                                color: isItemActive ? '#0f172a' : '#334155',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {title}
                            </span>
                            <span style={{ fontSize: '0.68rem', color: '#94a3b8', flexShrink: 0 }}>
                              {timeStr}
                            </span>
                          </div>
                          {s.last_message && (
                            <span
                              style={{
                                fontSize: '0.7rem',
                                color: '#64748b',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {s.last_message}
                            </span>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Popover Footer */}
                <div
                  style={{
                    padding: '6px 10px',
                    borderTop: '1px solid #f1f5f9',
                    background: '#f8fafc',
                    display: 'flex',
                    justifyContent: 'center',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      setHoverPopoverOpen(false);
                      if (!isSidebarOpen) onToggleSidebar();
                      setSidebarMode('chats');
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '0.72rem',
                      fontWeight: 500,
                      color: '#64748b',
                      padding: '3px 8px',
                      borderRadius: 4,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#64748b')}
                  >
                    Open full sidebar &rarr;
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 6. Data Catalog */}
          <button
            type="button"
            onClick={() => {
              if (!isSidebarOpen) onToggleSidebar();
              setSidebarMode('catalog');
            }}
            title="Data Catalog"
            style={{
              background: currentSidebarMode === 'catalog' ? '#f1f5f9' : 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px',
              color: currentSidebarMode === 'catalog' ? '#0f172a' : '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
            onMouseLeave={(e) => (e.currentTarget.style.color = currentSidebarMode === 'catalog' ? '#0f172a' : '#475569')}
          >
            <Database size={16} />
          </button>
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* 6. Bottom More Options */}
        <button
          type="button"
          onClick={onToggleSidebar}
          title="More options"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '6px',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 6,
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
          onMouseLeave={(e) => (e.currentTarget.style.color = '#64748b')}
        >
          <MoreVertical size={16} />
        </button>
      </div>
    );
  }

  // ── Expanded Sidebar (Matching Image 1) ────────────────────────────────────
  return (
    <div
      style={{
        width: sidebarWidth,
        minWidth: 180,
        maxWidth: 500,
        borderRight: '1px solid #e2e8f0',
        display: 'flex',
        flexDirection: 'column',
        background: '#ffffff',
        height: '100%',
        flexShrink: 0,
        position: 'relative',
        userSelect: isResizingSidebar ? 'none' : 'auto',
      }}
    >
      {/* Header Row: Agent Name + Collapse + More Options */}
      <div
        style={{
          padding: '14px 14px 10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span
          style={{
            fontSize: '1rem',
            fontWeight: 600,
            color: '#0f172a',
            letterSpacing: '-0.01em',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {agent?.name ?? 'Nova'}
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <button
            type="button"
            onClick={onToggleSidebar}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '4px',
              color: '#64748b',
              display: 'flex',
              alignItems: 'center',
              borderRadius: 4,
              transition: 'color 0.15s ease, background 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#0f172a';
              e.currentTarget.style.background = '#f1f5f9';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#64748b';
              e.currentTarget.style.background = 'none';
            }}
            title="Collapse sidebar"
          >
            <PanelLeftClose size={16} />
          </button>

          <div style={{ position: 'relative' }} ref={agentMenuRef}>
            <button
              type="button"
              onClick={() => setAgentMenuOpen(!agentMenuOpen)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '4px',
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                borderRadius: 4,
                transition: 'color 0.15s ease, background 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#0f172a';
                e.currentTarget.style.background = '#f1f5f9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#64748b';
                e.currentTarget.style.background = 'none';
              }}
              title="Agent options"
            >
              <MoreVertical size={16} />
            </button>
            {agentMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 28,
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 6,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  padding: '4px 0',
                  zIndex: 100,
                  minWidth: 150,
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    setAgentMenuOpen(false);
                    onSetMainView('customizations');
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '6px 12px',
                    border: 'none',
                    background: 'transparent',
                    color: '#1e293b',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <SlidersHorizontal size={14} />
                  <span>Customizations</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mode Switcher: Chats vs Catalog */}
      <div style={{ padding: '0 10px 10px' }}>
        <div
          style={{
            display: 'flex',
            background: 'var(--color-background-subtle, #f1f5f9)',
            border: '1px solid var(--color-border, #e2e8f0)',
            borderRadius: 6,
            padding: 2,
            gap: 2,
          }}
        >
          <button
            type="button"
            onClick={() => setSidebarMode('chats')}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              padding: '5px 8px',
              fontSize: '0.75rem',
              fontWeight: currentSidebarMode === 'chats' ? 600 : 500,
              color: currentSidebarMode === 'chats' ? 'var(--color-text, #0f172a)' : 'var(--color-text-muted, #64748b)',
              background: currentSidebarMode === 'chats' ? 'var(--color-surface, #ffffff)' : 'transparent',
              borderRadius: 5,
              border: 'none',
              cursor: 'pointer',
              boxShadow: currentSidebarMode === 'chats' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              transition: 'all 0.15s ease',
            }}
            title="View Agent Chat Sessions"
          >
            <MessageSquare size={13} />
            <span>Chats</span>
          </button>
          <button
            type="button"
            onClick={() => setSidebarMode('catalog')}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              padding: '5px 8px',
              fontSize: '0.75rem',
              fontWeight: currentSidebarMode === 'catalog' ? 600 : 500,
              color: currentSidebarMode === 'catalog' ? 'var(--color-text, #0f172a)' : 'var(--color-text-muted, #64748b)',
              background: currentSidebarMode === 'catalog' ? 'var(--color-surface, #ffffff)' : 'transparent',
              borderRadius: 5,
              border: 'none',
              cursor: 'pointer',
              boxShadow: currentSidebarMode === 'catalog' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              transition: 'all 0.15s ease',
            }}
            title="Explore Data Catalog schemas and tables (click to insert into prompt)"
          >
            <Database size={13} />
            <span>Catalog</span>
          </button>
        </div>
      </div>

      {currentSidebarMode === 'chats' ? (
        <>
          {/* Action Items List: New chat, Customizations, Session Logs */}
          <div style={{ padding: '0 10px 8px', display: 'flex', flexDirection: 'column', gap: 1 }}>
            <button
              type="button"
              onClick={onNewSession}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '7px 8px',
                border: 'none',
                background: 'transparent',
                color: '#1e293b',
                fontSize: '0.84rem',
                fontWeight: 500,
                cursor: 'pointer',
                borderRadius: 6,
                textAlign: 'left',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#f1f5f9')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <SquarePen size={15} color="#475569" />
              <span>New chat</span>
            </button>

            <button
              type="button"
              onClick={() => onSetMainView(mainView === 'customizations' ? 'chat' : 'customizations')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '7px 8px',
                border: 'none',
                background: mainView === 'customizations' ? '#f1f5f9' : 'transparent',
                color: mainView === 'customizations' ? '#0f172a' : '#1e293b',
                fontSize: '0.84rem',
                fontWeight: mainView === 'customizations' ? 600 : 500,
                cursor: 'pointer',
                borderRadius: 6,
                textAlign: 'left',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#f1f5f9')}
              onMouseLeave={(e) =>
                (e.currentTarget.style.background =
                  mainView === 'customizations' ? '#f1f5f9' : 'transparent')
              }
            >
              <SlidersHorizontal
                size={15}
                color={mainView === 'customizations' ? '#0f172a' : '#475569'}
              />
              <span>Customizations</span>
            </button>

            <button
              type="button"
              onClick={() => onSetMainView(mainView === 'logs' ? 'chat' : 'logs')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '7px 8px',
                border: 'none',
                background: mainView === 'logs' ? '#f1f5f9' : 'transparent',
                color: mainView === 'logs' ? '#0f172a' : '#1e293b',
                fontSize: '0.84rem',
                fontWeight: mainView === 'logs' ? 600 : 500,
                cursor: 'pointer',
                borderRadius: 6,
                textAlign: 'left',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#f1f5f9')}
              onMouseLeave={(e) =>
                (e.currentTarget.style.background =
                  mainView === 'logs' ? '#f1f5f9' : 'transparent')
              }
            >
              <Terminal size={15} color={mainView === 'logs' ? '#0f172a' : '#475569'} />
              <span>Session Logs</span>
            </button>
          </div>
          {/* Search chats */}
          <div style={{ padding: '0 10px 10px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: '#f1f5f9',
                borderRadius: 8,
                padding: '6px 10px',
              }}
            >
              <Search size={14} color="#94a3b8" />
              <input
                type="text"
                placeholder="Search chats"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  border: 'none',
                  outline: 'none',
                  background: 'transparent',
                  fontSize: '0.78rem',
                  color: '#1e293b',
                  lineHeight: 1.3,
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    color: '#94a3b8',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <XIcon size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Session list */}
          <div className="sidebar-hover-scrollbar" style={{ flex: 1, padding: '0 6px 12px' }}>
            {visibleSessions.map((s) => (
              <SessionListItem
                key={s.id}
                session={s}
                isActive={activeSessionId === s.id}
                onSelect={() => onSelectSession(s.id)}
                onDelete={(e) => onDeleteSession(e, s)}
              />
            ))}

            {filteredSessions.length === 0 && (
              <div
                style={{
                  padding: '24px 8px',
                  fontSize: '0.75rem',
                  color: '#94a3b8',
                  textAlign: 'center',
                }}
              >
                {searchQuery ? 'No matching chats found' : 'No chats yet'}
              </div>
            )}

            {filteredSessions.length > visibleSessionLimit && (
              <div style={{ padding: '8px 4px 4px', textAlign: 'center' }}>
                <button
                  type="button"
                  onClick={() => setVisibleSessionLimit((prev) => prev + 15)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#64748b',
                    fontSize: '0.75rem',
                    fontWeight: 500,
                    padding: '4px 8px',
                    borderRadius: 4,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#0f172a')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = '#64748b')}
                >
                  Show more
                </button>
              </div>
            )}
          </div>
        </>
      ) : (
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <CatalogExplorerTree mode="exploration" onInsert={onInsertTable} />
        </div>
      )}

      {/* Draggable resize splitter on right border */}
      <div
        onMouseDown={startSidebarResize}
        style={{
          position: 'absolute',
          top: 0,
          right: -3,
          width: 6,
          height: '100%',
          cursor: 'col-resize',
          zIndex: 50,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        onMouseEnter={(e) => {
          const line = e.currentTarget.querySelector('.sidebar-resizer-line') as HTMLElement;
          if (line && !isResizingSidebar) line.style.background = '#2563eb';
        }}
        onMouseLeave={(e) => {
          const line = e.currentTarget.querySelector('.sidebar-resizer-line') as HTMLElement;
          if (line && !isResizingSidebar) line.style.background = 'transparent';
        }}
      >
        <div
          className="sidebar-resizer-line"
          style={{
            width: 2,
            height: '100%',
            background: isResizingSidebar ? '#2563eb' : 'transparent',
            transition: 'background 0.15s ease',
          }}
        />
      </div>
    </div>
  );
}
export default ChatSessionsSidebar;
