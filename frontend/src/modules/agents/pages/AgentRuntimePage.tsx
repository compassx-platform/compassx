// @ts-nocheck
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  TerminalSquare,
  MessageSquare,
  Plus,
  Trash2,
  Search,
  Bot,
  Sparkles,
  Lock,
  RefreshCw,
  Play,
  Square,
  Copy,
  Check,
  Send,
  Loader2,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  Zap,
  Code,
  Terminal as TerminalIcon,
  HelpCircle,
  AlertCircle,
  Server,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { agentRuntimeApi, type AgentRuntimeSession, type AgentChatMessage } from '@/modules/agents/agentRuntimeApi';
import { CreateAgentSessionModal } from '@/modules/agents/components/CreateAgentSessionModal';
import { SandboxTerminal } from '@/components/sandbox/SandboxTerminal';
import { computeApi } from '@/modules/compute/computeApi';

const AGENT_CONFIGS: Record<string, { name: string; tag: string; badge: string; color: string; bg: string }> = {
  antigravity: {
    name: 'Google Antigravity',
    tag: 'agy',
    badge: 'DeepMind Core',
    color: '#38bdf8',
    bg: 'rgba(56, 189, 248, 0.12)',
  },
  pi: {
    name: 'Pi Coding Agent',
    tag: 'pi',
    badge: 'Codebase Specialist',
    color: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.12)',
  },
  opencode: {
    name: 'OpenCode AI',
    tag: 'opencode',
    badge: 'Multi-Model',
    color: '#10b981',
    bg: 'rgba(16, 185, 129, 0.12)',
  },
  bash: {
    name: 'Shell Agent',
    tag: 'bash',
    badge: 'System Shell',
    color: '#a855f7',
    bg: 'rgba(168, 85, 247, 0.12)',
  },
};

const STATUS_COLORS: Record<string, string> = {
  ready: '#10b981',
  running: '#10b981',
  provisioning: '#f59e0b',
  pending: '#f59e0b',
  suspended: '#64748b',
  stopped: '#64748b',
  failed: '#ef4444',
  active: '#10b981',
};

const SUGGESTED_QUERIES: Record<string, string[]> = {
  antigravity: [
    'Inspect the repository layout and summarize architecture',
    'Run tests with pytest and explain any failures',
    'List all files in /workspace and git status',
    'What skills and subagents are configured?',
  ],
  pi: [
    'Find all references to SandboxTerminal in the codebase',
    'Search for authentication middleware usage',
    'Examine recent git commits and branch status',
    'Refactor error handling in agent runtime routes',
  ],
  opencode: [
    'Generate unit tests for agent session persistence',
    'Review code quality and potential memory leaks',
    'Check Docker container resources and environment vars',
    'Run full build verification and report warnings',
  ],
};

export default function AgentRuntimePage() {
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useScopedNavigate();
  const toast = useToast();

  const [sessions, setSessions] = useState<AgentRuntimeSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(routeSessionId || null);
  const [activeSession, setActiveSession] = useState<AgentRuntimeSession | null>(null);

  const [activeTab, setActiveTab] = useState<'chat' | 'terminal'>('chat');
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Chat input state
  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const chatMessagesEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);

  // Sandbox status
  const [sandboxInfo, setSandboxInfo] = useState<any>(null);
  const [loadingSandbox, setLoadingSandbox] = useState(false);
  const [resumingSandbox, setResumingSandbox] = useState(false);

  // Load sessions on mount
  const fetchSessions = useCallback(async (autoSelectLatest = false) => {
    try {
      setLoadingSessions(true);
      const data = await agentRuntimeApi.listSessions();
      setSessions(data || []);

      if (data && data.length > 0) {
        if (autoSelectLatest) {
          const latest = data[0];
          setActiveSessionId(latest.id);
          setActiveSession(latest);
          navigate(`/agent-runtime/${latest.id}`, { replace: true });
        } else if (routeSessionId) {
          const matched = data.find((s) => s.id === routeSessionId);
          if (matched) {
            setActiveSessionId(matched.id);
            setActiveSession(matched);
          } else {
            setActiveSessionId(data[0].id);
            setActiveSession(data[0]);
            navigate(`/agent-runtime/${data[0].id}`, { replace: true });
          }
        } else if (!activeSessionId) {
          setActiveSessionId(data[0].id);
          setActiveSession(data[0]);
          navigate(`/agent-runtime/${data[0].id}`, { replace: true });
        }
      } else {
        setActiveSessionId(null);
        setActiveSession(null);
      }
    } catch (err: any) {
      console.error('Failed to load agent sessions:', err);
      toast.error('Failed to load agent sessions');
    } finally {
      setLoadingSessions(false);
    }
  }, [routeSessionId, activeSessionId, navigate, toast]);

  useEffect(() => {
    fetchSessions();
  }, []);

  // Sync route param change
  useEffect(() => {
    if (routeSessionId && routeSessionId !== activeSessionId) {
      setActiveSessionId(routeSessionId);
      const found = sessions.find((s) => s.id === routeSessionId);
      if (found) {
        setActiveSession(found);
      } else {
        // Fetch specific session
        agentRuntimeApi.getSession(routeSessionId).then((sess) => {
          setActiveSession(sess);
        }).catch(() => {
          // Fallback
        });
      }
    }
  }, [routeSessionId, sessions, activeSessionId]);

  // Load sandbox status when active session changes
  const refreshSandboxStatus = useCallback(async (sbId: string) => {
    if (!sbId) return;
    try {
      setLoadingSandbox(true);
      const sb = await computeApi.getSandbox(sbId);
      setSandboxInfo(sb);
    } catch (err) {
      console.warn('Failed to fetch sandbox details:', err);
    } finally {
      setLoadingSandbox(false);
    }
  }, []);

  const currentSandboxStatus = useMemo(() => {
    if (sandboxInfo?.status) return sandboxInfo.status.toLowerCase();
    if (activeSession?.status && activeSession.status !== 'active') return activeSession.status.toLowerCase();
    return loadingSandbox ? 'provisioning' : 'ready';
  }, [sandboxInfo?.status, activeSession?.status, loadingSandbox]);

  const isSandboxReady = currentSandboxStatus === 'running' || currentSandboxStatus === 'ready';
  const isSandboxFailed = currentSandboxStatus === 'failed';
  const isSandboxProvisioning = !isSandboxReady && !isSandboxFailed;

  useEffect(() => {
    if (!activeSession?.sandbox_id) {
      setSandboxInfo(null);
      return;
    }
    refreshSandboxStatus(activeSession.sandbox_id);

    // Actively poll status while the compute sandbox is in transitional provisioning stages
    const isTransitional = ['provisioning', 'pending', 'starting', 'initializing', 'allocating'].includes(currentSandboxStatus);
    if (isTransitional) {
      const interval = setInterval(() => {
        refreshSandboxStatus(activeSession.sandbox_id);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [activeSession?.sandbox_id, currentSandboxStatus, refreshSandboxStatus]);

  // Scroll chat to bottom when messages update
  useEffect(() => {
    if (activeTab === 'chat') {
      chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeSession?.messages, activeTab]);

  // Handle Session Select
  const handleSelectSession = (s: AgentRuntimeSession) => {
    setActiveSessionId(s.id);
    setActiveSession(s);
    navigate(`/agent-runtime/${s.id}`);
  };

  // Handle Session Delete
  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this agent runtime session?')) {
      return;
    }
    try {
      await agentRuntimeApi.deleteSession(sid);
      toast.success('Agent session deleted');
      const remaining = sessions.filter((s) => s.id !== sid);
      setSessions(remaining);
      if (activeSessionId === sid) {
        if (remaining.length > 0) {
          handleSelectSession(remaining[0]);
        } else {
          setActiveSessionId(null);
          setActiveSession(null);
          navigate('/agent-runtime');
        }
      }
    } catch (err: any) {
      toast.error('Failed to delete session');
    }
  };

  // Handle Resume Sandbox
  const handleResumeSandbox = async () => {
    if (!activeSession?.sandbox_id) return;
    try {
      setResumingSandbox(true);
      await computeApi.resumeSandbox(activeSession.sandbox_id);
      toast.success('Sandbox resume requested');
      await refreshSandboxStatus(activeSession.sandbox_id);
    } catch (err: any) {
      toast.error('Failed to resume sandbox');
    } finally {
      setResumingSandbox(false);
    }
  };

  // Send message
  const handleSendMessage = async (customContent?: string) => {
    const textToSend = customContent || inputMessage;
    if (!textToSend.trim() || !activeSession || isSending) return;

    const userMsg: AgentChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: textToSend.trim(),
      timestamp: new Date().toISOString(),
    };

    // Optimistically update
    setActiveSession((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        messages: [...(prev.messages || []), userMsg],
      };
    });
    setInputMessage('');
    setIsSending(true);

    try {
      const assistantMsg = await agentRuntimeApi.sendMessage(activeSession.id, textToSend.trim());
      // Append assistant message
      setActiveSession((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          messages: [...(prev.messages || []), assistantMsg],
        };
      });
      // Update session list timestamp
      setSessions((prevList) =>
        prevList.map((s) => (s.id === activeSession.id ? { ...s, updated_at: new Date().toISOString() } : s))
      );
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to send message');
    } finally {
      setIsSending(false);
      setTimeout(() => {
        chatInputRef.current?.focus();
      }, 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Filter sessions
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.agent_type.toLowerCase().includes(q) ||
        s.sandbox_id.toLowerCase().includes(q)
    );
  }, [sessions, searchQuery]);

  const currentAgentConfig = activeSession
    ? AGENT_CONFIGS[activeSession.agent_type] || AGENT_CONFIGS.antigravity
    : AGENT_CONFIGS.antigravity;

  const statusColor = STATUS_COLORS[currentSandboxStatus] || (isSandboxProvisioning ? '#f59e0b' : '#10b981');

  return (
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - 56px)',
        overflow: 'hidden',
        background: 'var(--color-bg, #0f172a)',
        color: 'var(--color-text, #f8fafc)',
      }}
    >
      {/* ── Left Sidebar: Sessions List ── */}
      <aside
        style={{
          width: '320px',
          minWidth: '320px',
          borderRight: '1px solid var(--color-border, #1e293b)',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--color-surface, #1e293b80)',
        }}
      >
        {/* Sidebar Header */}
        <div
          style={{
            padding: '16px',
            borderBottom: '1px solid var(--color-border, #1e293b)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(16, 185, 129, 0.2))',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#38bdf8',
              }}
            >
              <Bot size={18} />
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.92rem' }}>Agent Runtime</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted, #94a3b8)' }}>
                {sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}
              </div>
            </div>
          </div>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: 6,
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'background 0.15s ease',
            }}
            title="Start new agent session"
          >
            <Plus size={15} /> New
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--color-border, #1e293b)' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid var(--color-border, #334155)',
              borderRadius: 6,
              padding: '6px 10px',
            }}
          >
            <Search size={14} style={{ color: 'var(--color-text-muted, #94a3b8)' }} />
            <input
              type="text"
              placeholder="Search sessions or sandboxes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'inherit',
                fontSize: '0.82rem',
                width: '100%',
              }}
            />
          </div>
        </div>

        {/* Sessions Scroll List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          {loadingSessions ? (
            <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-muted, #94a3b8)' }}>
              <Loader2 size={20} className="spin" style={{ margin: '0 auto 8px auto' }} />
              <div style={{ fontSize: '0.82rem' }}>Loading sessions...</div>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--color-text-muted, #94a3b8)' }}>
              <Bot size={28} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
              <div style={{ fontSize: '0.88rem', fontWeight: 500, marginBottom: 4 }}>No sessions found</div>
              <p style={{ fontSize: '0.78rem', margin: '0 0 16px 0' }}>
                Launch an AI agent attached to an isolated compute sandbox container.
              </p>
              <button
                onClick={() => setIsCreateModalOpen(true)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: 'rgba(37, 99, 235, 0.15)',
                  color: '#60a5fa',
                  border: '1px solid rgba(37, 99, 235, 0.3)',
                  borderRadius: 6,
                  padding: '6px 12px',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <Plus size={14} /> Start Session
              </button>
            </div>
          ) : (
            filteredSessions.map((s) => {
              const isSelected = s.id === activeSessionId;
              const cfg = AGENT_CONFIGS[s.agent_type] || AGENT_CONFIGS.antigravity;
              return (
                <div
                  key={s.id}
                  onClick={() => handleSelectSession(s)}
                  style={{
                    padding: '12px',
                    borderRadius: 8,
                    marginBottom: 6,
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                    border: `1px solid ${isSelected ? 'rgba(56, 189, 248, 0.3)' : 'transparent'}`,
                    transition: 'all 0.15s ease',
                    position: 'relative',
                  }}
                  className="agent-session-item"
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          padding: '2px 6px',
                          borderRadius: 4,
                          background: cfg.bg,
                          color: cfg.color,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                          flexShrink: 0,
                        }}
                      >
                        {cfg.tag}
                      </span>
                      <div
                        style={{
                          fontWeight: isSelected ? 600 : 500,
                          fontSize: '0.85rem',
                          color: isSelected ? '#ffffff' : 'var(--color-text, #f1f5f9)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {s.title}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDeleteSession(e, s.id)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--color-text-muted, #64748b)',
                        cursor: 'pointer',
                        padding: 2,
                        borderRadius: 4,
                        display: 'flex',
                        alignItems: 'center',
                      }}
                      title="Delete session"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginTop: 8,
                      fontSize: '0.72rem',
                      color: 'var(--color-text-muted, #94a3b8)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Lock size={11} style={{ color: '#94a3b8' }} />
                      <span style={{ fontFamily: 'monospace' }}>
                        {s.sandbox_id.length > 14 ? `${s.sandbox_id.slice(0, 14)}...` : s.sandbox_id}
                      </span>
                    </div>
                    <div>
                      {s.messages ? `${s.messages.length} msg` : '0 msg'}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* ── Main Work Area ── */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
          background: '#090d16',
        }}
      >
        {!activeSession ? (
          <div
            style={{
              flex: 1,
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
                width: 64,
                height: 64,
                borderRadius: '50%',
                background: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#38bdf8',
                marginBottom: 20,
              }}
            >
              <TerminalSquare size={32} />
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: '0 0 8px 0' }}>
              Welcome to Agent Runtime
            </h2>
            <p
              style={{
                fontSize: '0.88rem',
                color: 'var(--color-text-muted, #94a3b8)',
                maxWidth: 480,
                lineHeight: 1.5,
                margin: '0 0 24px 0',
              }}
            >
              Run autonomous developer agents (<code style={{ color: '#38bdf8' }}>Google Antigravity</code>,{' '}
              <code style={{ color: '#f59e0b' }}>Pi Coding Agent</code>, or{' '}
              <code style={{ color: '#10b981' }}>OpenCode AI</code>) inside isolated container sandboxes. Switch
              between live conversation and interactive PTY terminal at any time.
            </p>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                background: '#2563eb',
                color: '#ffffff',
                border: 'none',
                borderRadius: 8,
                padding: '10px 20px',
                fontSize: '0.88rem',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)',
              }}
            >
              <Plus size={16} /> Launch Agent Session
            </button>
          </div>
        ) : (
          <>
            {/* ── Active Session Top Bar ── */}
            <header
              style={{
                height: 60,
                borderBottom: '1px solid var(--color-border, #1e293b)',
                background: 'rgba(15, 23, 42, 0.85)',
                backdropFilter: 'blur(8px)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 20px',
                gap: 16,
              }}
            >
              {/* Left Details */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                {/* Agent Identity Pill */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    background: currentAgentConfig.bg,
                    border: `1px solid ${currentAgentConfig.color}40`,
                    borderRadius: 6,
                    padding: '4px 10px',
                  }}
                >
                  <Bot size={16} style={{ color: currentAgentConfig.color }} />
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: currentAgentConfig.color }}>
                    {currentAgentConfig.name}
                  </span>
                  <span
                    style={{
                      fontSize: '0.68rem',
                      background: 'rgba(0,0,0,0.25)',
                      padding: '1px 5px',
                      borderRadius: 4,
                      color: '#cbd5e1',
                    }}
                  >
                    {currentAgentConfig.badge}
                  </span>
                </div>

                <div style={{ height: 20, width: 1, background: 'var(--color-border, #334155)' }} />

                {/* Session Title */}
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: '0.92rem',
                    color: '#ffffff',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    maxWidth: 220,
                  }}
                  title={activeSession.title}
                >
                  {activeSession.title}
                </div>

                {/* Bound Sandbox Pill (Immutable) */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    background: 'rgba(30, 41, 59, 0.7)',
                    border: '1px solid var(--color-border, #334155)',
                    borderRadius: 6,
                    padding: '3px 8px',
                    fontSize: '0.75rem',
                  }}
                  title="Immutable session sandbox binding"
                >
                  <Lock size={12} style={{ color: '#94a3b8' }} />
                  <span style={{ color: '#94a3b8' }}>Sandbox:</span>
                  <span style={{ fontFamily: 'monospace', color: '#e2e8f0', fontWeight: 500 }}>
                    {activeSession.sandbox_id}
                  </span>
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: statusColor,
                      boxShadow: `0 0 6px ${statusColor}`,
                    }}
                  />
                  <span style={{ textTransform: 'capitalize', color: statusColor, fontSize: '0.72rem' }}>
                    {currentSandboxStatus}
                  </span>

                  {currentSandboxStatus === 'suspended' && (
                    <button
                      onClick={handleResumeSandbox}
                      disabled={resumingSandbox}
                      style={{
                        marginLeft: 4,
                        background: '#2563eb',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: 4,
                        padding: '2px 6px',
                        fontSize: '0.7rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 3,
                      }}
                    >
                      {resumingSandbox ? <Loader2 size={10} className="spin" /> : <Play size={10} />} Resume
                    </button>
                  )}
                </div>
              </div>

              {/* Right: Tab Switcher (Chat vs Terminal) */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    background: 'rgba(30, 41, 59, 0.8)',
                    border: '1px solid var(--color-border, #334155)',
                    borderRadius: 8,
                    padding: 3,
                    gap: 4,
                  }}
                >
                  <button
                    onClick={() => isSandboxReady && setActiveTab('chat')}
                    disabled={!isSandboxReady}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      background: activeTab === 'chat' ? '#2563eb' : 'transparent',
                      color: activeTab === 'chat' ? '#ffffff' : 'var(--color-text-muted, #94a3b8)',
                      border: 'none',
                      borderRadius: 6,
                      padding: '6px 14px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      cursor: isSandboxReady ? 'pointer' : 'not-allowed',
                      opacity: isSandboxReady ? 1 : 0.6,
                      transition: 'all 0.15s ease',
                      boxShadow: activeTab === 'chat' ? '0 2px 8px rgba(37, 99, 235, 0.3)' : 'none',
                    }}
                  >
                    <MessageSquare size={14} /> Chat
                  </button>
                  <button
                    onClick={() => isSandboxReady && setActiveTab('terminal')}
                    disabled={!isSandboxReady}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      background: activeTab === 'terminal' ? '#2563eb' : 'transparent',
                      color: activeTab === 'terminal' ? '#ffffff' : 'var(--color-text-muted, #94a3b8)',
                      border: 'none',
                      borderRadius: 6,
                      padding: '6px 14px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      cursor: isSandboxReady ? 'pointer' : 'not-allowed',
                      opacity: isSandboxReady ? 1 : 0.6,
                      transition: 'all 0.15s ease',
                      boxShadow: activeTab === 'terminal' ? '0 2px 8px rgba(37, 99, 235, 0.3)' : 'none',
                    }}
                  >
                    <TerminalSquare size={14} /> Terminal
                  </button>
                </div>
              </div>
            </header>

            {/* ── Sandbox Contract Gate ── */}
            {isSandboxProvisioning ? (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '40px 24px',
                  textAlign: 'center',
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 16,
                    background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.15) 0%, rgba(37, 99, 235, 0.15) 100%)',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#38bdf8',
                    marginBottom: 20,
                    boxShadow: '0 8px 24px rgba(56, 189, 248, 0.2)',
                  }}
                >
                  <Server size={32} className="spin" />
                </div>
                <h2 style={{ margin: '0 0 8px', fontSize: '1.25rem', fontWeight: 600, color: '#f8fafc' }}>
                  {sandboxInfo?.progress?.stage === 'allocating'
                    ? 'Allocating Compute Sandbox'
                    : sandboxInfo?.progress?.stage === 'starting'
                    ? 'Starting Container Environment'
                    : 'Provisioning Agent Sandbox Compute'}
                </h2>
                <p style={{ margin: '0 0 24px', fontSize: '0.85rem', color: '#94a3b8', maxWidth: 460, lineHeight: 1.5 }}>
                  {sandboxInfo?.progress?.message ||
                    'The Kubernetes cluster is initializing worker nodes and preparing isolated container compute for this agent session.'}
                </p>

                <div
                  style={{
                    background: 'rgba(30, 41, 59, 0.6)',
                    border: '1px solid var(--color-border, #334155)',
                    borderRadius: 8,
                    padding: '12px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16,
                    fontSize: '0.78rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Lock size={13} style={{ color: '#94a3b8' }} />
                    <span style={{ color: '#94a3b8' }}>Bound Sandbox:</span>
                    <span style={{ fontFamily: 'monospace', color: '#e2e8f0' }}>{activeSession.sandbox_id}</span>
                  </div>
                  <div style={{ height: 14, width: 1, background: '#334155' }} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: '#94a3b8' }}>Status:</span>
                    <span style={{ color: '#f59e0b', textTransform: 'capitalize', fontWeight: 500 }}>
                      {currentSandboxStatus}
                    </span>
                  </div>
                </div>

                <div style={{ marginTop: 20, fontSize: '0.75rem', color: '#64748b' }}>
                  The Chat and Terminal workspace will automatically unlock once the sandbox container is fully running and healthy.
                </div>
              </div>
            ) : isSandboxFailed ? (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '40px 24px',
                  textAlign: 'center',
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 16,
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#f87171',
                    marginBottom: 20,
                    boxShadow: '0 8px 24px rgba(239, 68, 68, 0.2)',
                  }}
                >
                  <AlertCircle size={32} />
                </div>
                <h2 style={{ margin: '0 0 8px', fontSize: '1.25rem', fontWeight: 600, color: '#f8fafc' }}>
                  Sandbox Compute Failed to Start
                </h2>
                <p style={{ margin: '0 0 20px', fontSize: '0.85rem', color: '#94a3b8', maxWidth: 480, lineHeight: 1.5 }}>
                  The sandbox container encountered an infrastructure error during cluster startup.
                </p>

                {/* Diagnostic Error Box */}
                <div
                  style={{
                    maxWidth: 580,
                    width: '100%',
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    borderRadius: 8,
                    padding: '14px 18px',
                    textAlign: 'left',
                    marginBottom: 24,
                  }}
                >
                  <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#f87171', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertCircle size={14} /> Diagnostic Error
                  </div>
                  <div
                    style={{
                      fontFamily: 'monospace',
                      fontSize: '0.75rem',
                      color: '#cbd5e1',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      lineHeight: 1.5,
                    }}
                  >
                    {sandboxInfo?.error_message ||
                      sandboxInfo?.progress?.message ||
                      'Container failed to pull runtime image or schedule onto a cluster node (ImagePullBackOff / ErrImagePull).'}
                  </div>
                  <div style={{ marginTop: 10, display: 'flex', gap: 12, fontSize: '0.72rem', color: '#64748b' }}>
                    <span>Sandbox ID: <code style={{ color: '#94a3b8' }}>{activeSession.sandbox_id}</code></span>
                    <span>Image: <code style={{ color: '#94a3b8' }}>{sandboxInfo?.image || 'compassx-sandbox-host'}</code></span>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <button
                    onClick={handleResumeSandbox}
                    disabled={resumingSandbox}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      background: '#2563eb',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: 6,
                      padding: '8px 18px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {resumingSandbox ? <Loader2 size={14} className="spin" /> : <Play size={14} />} Retry Provisioning
                  </button>
                  <button
                    onClick={(e) => handleDeleteSession(e, activeSession.id)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      background: 'transparent',
                      color: '#94a3b8',
                      border: '1px solid #334155',
                      borderRadius: 6,
                      padding: '8px 14px',
                      fontSize: '0.82rem',
                      cursor: 'pointer',
                    }}
                  >
                    <Trash2 size={14} /> Delete Session
                  </button>
                </div>
              </div>
            ) : (
              /* ── Content Panes (Zero-Drop DOM Persistence) ── */
              <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              {/* ── Chat View Pane ── */}
              <div
                style={{
                  display: activeTab === 'chat' ? 'flex' : 'none',
                  flexDirection: 'column',
                  height: '100%',
                  width: '100%',
                }}
              >
                {/* Messages Stream */}
                <div
                  style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '24px 32px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 16,
                  }}
                >
                  {/* System Welcome Card */}
                  <div
                    style={{
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(56, 189, 248, 0.2)',
                      borderRadius: 8,
                      padding: '16px 20px',
                      marginBottom: 8,
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 14,
                    }}
                  >
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 8,
                        background: currentAgentConfig.bg,
                        color: currentAgentConfig.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <Sparkles size={18} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.88rem', color: '#f8fafc', marginBottom: 4 }}>
                        {currentAgentConfig.name} is running in container {activeSession.sandbox_id}
                      </div>
                      <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 10px 0', lineHeight: 1.5 }}>
                        This session is bound to dedicated container compute. Use this chat to instruct the agent to
                        search code, run tests, or plan modifications. Switch to the <strong>Terminal</strong> tab at
                        any time to interact directly with the PTY shell.
                      </p>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            background: 'rgba(30, 41, 59, 0.8)',
                            padding: '2px 8px',
                            borderRadius: 4,
                            color: '#cbd5e1',
                            fontFamily: 'monospace',
                          }}
                        >
                          Workspace: /workspace
                        </span>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            background: 'rgba(30, 41, 59, 0.8)',
                            padding: '2px 8px',
                            borderRadius: 4,
                            color: '#cbd5e1',
                            fontFamily: 'monospace',
                          }}
                        >
                          CLI: {currentAgentConfig.tag}
                        </span>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            background: 'rgba(30, 41, 59, 0.8)',
                            padding: '2px 8px',
                            borderRadius: 4,
                            color: '#34d399',
                          }}
                        >
                          ✓ Zero-Drop Switch Enabled
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Messages List */}
                  {(activeSession.messages || []).map((msg) => {
                    const isUser = msg.role === 'user';
                    const isSystem = msg.role === 'system';

                    if (isSystem) {
                      return (
                        <div
                          key={msg.id}
                          style={{
                            textAlign: 'center',
                            fontSize: '0.78rem',
                            color: 'var(--color-text-muted, #94a3b8)',
                            margin: '8px 0',
                            fontStyle: 'italic',
                          }}
                        >
                          {msg.content}
                        </div>
                      );
                    }

                    return (
                      <div
                        key={msg.id}
                        style={{
                          display: 'flex',
                          flexDirection: isUser ? 'row-reverse' : 'row',
                          alignItems: 'flex-start',
                          gap: 12,
                          maxWidth: '85%',
                          alignSelf: isUser ? 'flex-end' : 'flex-start',
                        }}
                      >
                        {/* Avatar */}
                        <div
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            background: isUser ? '#2563eb' : currentAgentConfig.bg,
                            border: `1px solid ${isUser ? '#3b82f6' : currentAgentConfig.color}40`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: isUser ? '#ffffff' : currentAgentConfig.color,
                            flexShrink: 0,
                            marginTop: 2,
                          }}
                        >
                          {isUser ? 'U' : <Bot size={16} />}
                        </div>

                        {/* Bubble */}
                        <div
                          style={{
                            background: isUser ? '#1e3a8a' : 'rgba(30, 41, 59, 0.7)',
                            border: `1px solid ${isUser ? '#2563eb' : 'var(--color-border, #334155)'}`,
                            borderRadius: 12,
                            borderTopRightRadius: isUser ? 2 : 12,
                            borderTopLeftRadius: isUser ? 12 : 2,
                            padding: '12px 16px',
                            color: '#f8fafc',
                            fontSize: '0.88rem',
                            lineHeight: 1.55,
                            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                            wordBreak: 'break-word',
                          }}
                        >
                          {isUser ? (
                            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                          ) : (
                            <div className="agent-markdown-content">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {msg.content}
                              </ReactMarkdown>
                            </div>
                          )}
                          <div
                            style={{
                              marginTop: 6,
                              fontSize: '0.68rem',
                              color: isUser ? 'rgba(255,255,255,0.6)' : '#64748b',
                              textAlign: isUser ? 'right' : 'left',
                            }}
                          >
                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {/* Sending Indicator */}
                  {isSending && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        alignSelf: 'flex-start',
                        color: 'var(--color-text-muted, #94a3b8)',
                        fontSize: '0.82rem',
                        padding: '8px 14px',
                        background: 'rgba(30, 41, 59, 0.5)',
                        borderRadius: 8,
                      }}
                    >
                      <Loader2 size={16} className="spin" style={{ color: currentAgentConfig.color }} />
                      <span>{currentAgentConfig.name} is reasoning and executing...</span>
                    </div>
                  )}

                  <div ref={chatMessagesEndRef} />
                </div>

                {/* Quick Prompts Bar */}
                <div
                  style={{
                    padding: '8px 24px',
                    borderTop: '1px solid var(--color-border, #1e293b)',
                    background: 'rgba(15, 23, 42, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    overflowX: 'auto',
                  }}
                >
                  <span style={{ fontSize: '0.72rem', color: '#64748b', whiteSpace: 'nowrap' }}>
                    Quick queries:
                  </span>
                  {(SUGGESTED_QUERIES[activeSession.agent_type] || SUGGESTED_QUERIES.antigravity).map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(q)}
                      disabled={isSending}
                      style={{
                        background: 'rgba(30, 41, 59, 0.7)',
                        border: '1px solid var(--color-border, #334155)',
                        borderRadius: 14,
                        padding: '4px 10px',
                        fontSize: '0.72rem',
                        color: '#cbd5e1',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>

                {/* Input Composer */}
                <div
                  style={{
                    padding: '14px 24px',
                    borderTop: '1px solid var(--color-border, #1e293b)',
                    background: 'rgba(15, 23, 42, 0.85)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-end',
                      gap: 10,
                      background: 'rgba(30, 41, 59, 0.6)',
                      border: '1px solid var(--color-border, #334155)',
                      borderRadius: 10,
                      padding: '8px 12px',
                    }}
                  >
                    <textarea
                      ref={chatInputRef}
                      rows={2}
                      placeholder={`Ask ${currentAgentConfig.name} to execute tasks, search files, run tests... (Enter to send, Shift+Enter for new line)`}
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={isSending}
                      style={{
                        flex: 1,
                        background: 'transparent',
                        border: 'none',
                        outline: 'none',
                        color: 'inherit',
                        fontSize: '0.88rem',
                        resize: 'none',
                        lineHeight: 1.4,
                      }}
                    />
                    <button
                      onClick={() => handleSendMessage()}
                      disabled={!inputMessage.trim() || isSending}
                      style={{
                        background: !inputMessage.trim() || isSending ? 'rgba(37, 99, 235, 0.3)' : '#2563eb',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: 8,
                        width: 36,
                        height: 36,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: !inputMessage.trim() || isSending ? 'not-allowed' : 'pointer',
                        transition: 'background 0.15s ease',
                        flexShrink: 0,
                      }}
                      title="Send message"
                    >
                      {isSending ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
                    </button>
                  </div>
                </div>
              </div>

              {/* ── Terminal View Pane (Persistent in DOM) ── */}
              <div
                style={{
                  display: activeTab === 'terminal' ? 'flex' : 'none',
                  flexDirection: 'column',
                  height: '100%',
                  width: '100%',
                }}
              >
                {/* Terminal Sub-header Bar */}
                <div
                  style={{
                    padding: '8px 20px',
                    borderBottom: '1px solid var(--color-border, #1e293b)',
                    background: '#0d1117',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#94a3b8' }}>
                      <TerminalIcon size={14} style={{ color: '#38bdf8' }} />
                      <span>Direct PTY Shell</span>
                      <span>•</span>
                      <span style={{ fontFamily: 'monospace', color: '#cbd5e1' }}>/workspace</span>
                      <span>•</span>
                      <span style={{ color: '#34d399' }}>Tools: agy, pi, opencode, python3, git</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      onClick={() => refreshSandboxStatus(activeSession.sandbox_id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                        background: 'transparent',
                        border: '1px solid var(--color-border, #334155)',
                        borderRadius: 4,
                        padding: '3px 8px',
                        fontSize: '0.72rem',
                        color: '#94a3b8',
                        cursor: 'pointer',
                      }}
                      title="Refresh status"
                    >
                      <RefreshCw size={11} className={loadingSandbox ? 'spin' : ''} /> Refresh
                    </button>
                  </div>
                </div>

                {/* Terminal Container */}
                <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
                  <SandboxTerminal
                    sandboxId={activeSession.sandbox_id}
                    fullHeight={true}
                    isRunning={currentSandboxStatus !== 'suspended' && currentSandboxStatus !== 'stopped'}
                    onResume={handleResumeSandbox}
                  />
                </div>
              </div>
            </div>
            )}
          </>
        )}
      </main>

      {/* ── New Session Modal ── */}
      <CreateAgentSessionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={async (payload) => {
          const newSess = await agentRuntimeApi.createSession(payload);
          setSessions((prev) => [newSess, ...prev]);
          setActiveSessionId(newSess.id);
          setActiveSession(newSess);
          navigate(`/agent-runtime/${newSess.id}`);
          toast.success(`Started session with ${payload.agent_type.toUpperCase()}`);
        }}
      />
    </div>
  );
}
