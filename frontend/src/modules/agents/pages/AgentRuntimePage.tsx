// @ts-nocheck
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  TerminalSquare,
  Plus,
  Trash2,
  Search,
  Bot,
  Sparkles,
  Lock,
  Play,
  Loader2,
  AlertCircle,
  Server,
  Layers,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { agentRuntimeApi, type AgentRuntimeSession, type AgentChatMessage } from '@/modules/agents/agentRuntimeApi';
import { CreateAgentSessionModal } from '@/modules/agents/components/CreateAgentSessionModal';
import { computeApi } from '@/modules/compute/computeApi';
import { OmnigentChatPanel } from '@/modules/apps/components/build/OmnigentChatPanel';
import type { ChatMessage } from '@/modules/apps/hooks/useOmnigentChat';

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

export default function AgentRuntimePage() {
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useScopedNavigate();
  const toast = useToast();

  const [sessions, setSessions] = useState<AgentRuntimeSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(routeSessionId || null);
  const [activeSession, setActiveSession] = useState<AgentRuntimeSession | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

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

  // Resume or Retry failed sandbox
  const handleResumeSandbox = async () => {
    if (!activeSession?.sandbox_id) return;
    try {
      setResumingSandbox(true);
      await computeApi.resumeSandbox(activeSession.sandbox_id);
      toast.success('Requested sandbox provision / resume');
      await refreshSandboxStatus(activeSession.sandbox_id);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to resume sandbox');
    } finally {
      setResumingSandbox(false);
    }
  };

  // Send message using Agent Runtime API
  const handleSendMessage = async (promptText: string) => {
    if (!promptText.trim() || !activeSession) return;

    const userMsg: AgentChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: promptText.trim(),
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

    try {
      const assistantMsg = await agentRuntimeApi.sendMessage(activeSession.id, promptText.trim());
      setActiveSession((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          messages: [...(prev.messages || []), assistantMsg],
        };
      });
      setSessions((prevList) =>
        prevList.map((s) => (s.id === activeSession.id ? { ...s, updated_at: new Date().toISOString() } : s))
      );
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to send prompt to agent');
      throw err;
    }
  };

  // Map AgentChatMessage[] to Omnigent ChatMessage[]
  const mappedMessages: ChatMessage[] = useMemo(() => {
    if (!activeSession?.messages) return [];
    return activeSession.messages.map((m) => ({
      id: m.id,
      role: m.role as any,
      type: 'message',
      content: m.content,
      created_at: m.timestamp,
      status: 'completed',
    }));
  }, [activeSession?.messages]);

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
        background: '#f8fafc',
        color: '#0f172a',
      }}
    >
      {/* ── Left Sidebar: Sessions List (Refined App UI styling) ── */}
      <aside
        style={{
          width: '320px',
          minWidth: '320px',
          borderRight: '1px solid #e2e8f0',
          display: 'flex',
          flexDirection: 'column',
          background: '#ffffff',
        }}
      >
        {/* Sidebar Header */}
        <div
          style={{
            padding: '16px',
            borderBottom: '1px solid #e2e8f0',
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
                background: '#eff6ff',
                border: '1px solid #dbeafe',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563eb',
              }}
            >
              <Bot size={18} />
            </div>
            <div>
              <div style={{ fontWeight: 650, fontSize: '0.92rem', color: '#0f172a' }}>Agent Runtime</div>
              <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
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
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.15s ease',
            }}
            title="Start new agent session"
          >
            <Plus size={15} /> New
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '10px 16px', borderBottom: '1px solid #e2e8f0' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 6,
              padding: '6px 10px',
            }}
          >
            <Search size={14} style={{ color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Search sessions or sandboxes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#0f172a',
                fontSize: '0.82rem',
                width: '100%',
              }}
            />
          </div>
        </div>

        {/* Sessions Scroll List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          {loadingSessions ? (
            <div style={{ padding: '32px 16px', textAlign: 'center', color: '#64748b' }}>
              <Loader2 size={20} className="spin" style={{ margin: '0 auto 8px auto' }} />
              <div style={{ fontSize: '0.82rem' }}>Loading sessions...</div>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
              <Bot size={28} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
              <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#0f172a', marginBottom: 4 }}>No sessions found</div>
              <p style={{ fontSize: '0.78rem', margin: '0 0 16px 0', color: '#64748b' }}>
                Launch an AI agent attached to an isolated compute sandbox container.
              </p>
              <button
                onClick={() => setIsCreateModalOpen(true)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: 6,
                  padding: '7px 14px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <Plus size={14} /> Create Session
              </button>
            </div>
          ) : (
            filteredSessions.map((s) => {
              const isActive = s.id === activeSessionId;
              const cfg = AGENT_CONFIGS[s.agent_type] || AGENT_CONFIGS.antigravity;
              return (
                <div
                  key={s.id}
                  onClick={() => handleSelectSession(s)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 8,
                    marginBottom: 4,
                    cursor: 'pointer',
                    background: isActive ? '#eff6ff' : 'transparent',
                    border: `1px solid ${isActive ? '#bfdbfe' : 'transparent'}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                    transition: 'all 0.12s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.background = '#f8fafc';
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                      <span
                        style={{
                          fontSize: '0.66rem',
                          fontFamily: 'monospace',
                          padding: '1px 5px',
                          borderRadius: 4,
                          background: cfg.bg,
                          color: cfg.color,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {cfg.tag}
                      </span>
                      <span
                        style={{
                          fontSize: '0.84rem',
                          fontWeight: isActive ? 650 : 500,
                          color: isActive ? '#1d4ed8' : '#0f172a',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                        title={s.title}
                      >
                        {s.title}
                      </span>
                    </div>
                    <button
                      onClick={(e) => handleDeleteSession(e, s.id)}
                      title="Delete session"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#94a3b8',
                        cursor: 'pointer',
                        padding: 2,
                        borderRadius: 4,
                        opacity: isActive ? 1 : 0.4,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = '#dc2626';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = '#94a3b8';
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: '#64748b' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: s.status === 'failed' ? '#ef4444' : s.status === 'provisioning' ? '#f59e0b' : '#10b981',
                        }}
                      />
                      <span style={{ fontFamily: 'monospace', color: '#475569' }}>{s.sandbox_id}</span>
                    </div>
                    <span>{new Date(s.updated_at || s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* ── Main Workspace: Reusing Refined App Studio UI ── */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: '#ffffff',
          position: 'relative',
        }}
      >
        {!activeSession ? (
          /* Empty Selection State */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px',
              textAlign: 'center',
              background: '#f8fafc',
            }}
          >
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: 14,
                background: '#eff6ff',
                border: '1px solid #dbeafe',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563eb',
                marginBottom: 16,
              }}
            >
              <TerminalSquare size={28} />
            </div>
            <h3 style={{ margin: '0 0 6px', fontSize: '1.15rem', fontWeight: 650, color: '#0f172a' }}>
              Select or Create an Agent Session
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: '0.84rem', color: '#64748b', maxWidth: 420, lineHeight: 1.5 }}>
              Choose a running session from the left panel or create a new session with Google Antigravity, Pi, or OpenCode.
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
                borderRadius: 7,
                padding: '9px 18px',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Plus size={15} /> Create Agent Session
            </button>
          </div>
        ) : isSandboxProvisioning ? (
          /* Dedicated Provisioning State Screen */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 24px',
              textAlign: 'center',
              background: '#f8fafc',
            }}
          >
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: 14,
                background: '#eff6ff',
                border: '1px solid #dbeafe',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563eb',
                marginBottom: 18,
                boxShadow: '0 8px 24px rgba(37, 99, 235, 0.12)',
              }}
            >
              <Server size={30} className="spin" />
            </div>
            <h2 style={{ margin: '0 0 8px', fontSize: '1.2rem', fontWeight: 650, color: '#0f172a' }}>
              {sandboxInfo?.progress?.stage === 'allocating'
                ? 'Allocating Compute Sandbox'
                : sandboxInfo?.progress?.stage === 'starting'
                ? 'Starting Container Environment'
                : 'Provisioning Agent Sandbox Compute'}
            </h2>
            <p style={{ margin: '0 0 20px', fontSize: '0.84rem', color: '#64748b', maxWidth: 460, lineHeight: 1.5 }}>
              {sandboxInfo?.progress?.message ||
                'The Kubernetes cluster is preparing isolated container compute for this agent session.'}
            </p>

            <div
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '12px 20px',
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                fontSize: '0.78rem',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Lock size={13} style={{ color: '#64748b' }} />
                <span style={{ color: '#64748b' }}>Bound Sandbox:</span>
                <span style={{ fontFamily: 'monospace', color: '#0f172a', fontWeight: 600 }}>{activeSession.sandbox_id}</span>
              </div>
              <div style={{ height: 14, width: 1, background: '#e2e8f0' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#64748b' }}>Status:</span>
                <span style={{ color: '#d97706', textTransform: 'capitalize', fontWeight: 600 }}>
                  {currentSandboxStatus}
                </span>
              </div>
            </div>

            <div style={{ marginTop: 18, fontSize: '0.75rem', color: '#94a3b8' }}>
              The Chat and Terminal workspace will automatically unlock once the sandbox container is fully running and healthy.
            </div>
          </div>
        ) : isSandboxFailed ? (
          /* Dedicated Failure State Screen */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 24px',
              textAlign: 'center',
              background: '#f8fafc',
            }}
          >
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: 14,
                background: '#fee2e2',
                border: '1px solid #fecaca',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#dc2626',
                marginBottom: 18,
                boxShadow: '0 8px 24px rgba(220, 38, 38, 0.12)',
              }}
            >
              <AlertCircle size={30} />
            </div>
            <h2 style={{ margin: '0 0 8px', fontSize: '1.2rem', fontWeight: 650, color: '#0f172a' }}>
              Sandbox Compute Failed to Start
            </h2>
            <p style={{ margin: '0 0 20px', fontSize: '0.84rem', color: '#64748b', maxWidth: 480, lineHeight: 1.5 }}>
              The sandbox container encountered an infrastructure error during cluster startup.
            </p>

            {/* Diagnostic Error Box */}
            <div
              style={{
                maxWidth: 580,
                width: '100%',
                background: '#ffffff',
                border: '1px solid #fecaca',
                borderRadius: 8,
                padding: '14px 18px',
                textAlign: 'left',
                marginBottom: 24,
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.04)',
              }}
            >
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#dc2626', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={14} /> Diagnostic Error
              </div>
              <div
                style={{
                  fontFamily: 'monospace',
                  fontSize: '0.75rem',
                  color: '#334155',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.5,
                  background: '#f8fafc',
                  padding: '8px 10px',
                  borderRadius: 6,
                  border: '1px solid #e2e8f0',
                }}
              >
                {sandboxInfo?.error_message ||
                  sandboxInfo?.progress?.message ||
                  'Container failed to pull runtime image or schedule onto a cluster node (ImagePullBackOff / ErrImagePull).'}
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 12, fontSize: '0.72rem', color: '#64748b' }}>
                <span>Sandbox ID: <code style={{ color: '#0f172a', fontWeight: 600 }}>{activeSession.sandbox_id}</code></span>
                <span>Image: <code style={{ color: '#0f172a' }}>{sandboxInfo?.image || 'compassx-sandbox-host'}</code></span>
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
                  background: '#ffffff',
                  color: '#64748b',
                  border: '1px solid #cbd5e1',
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
          /* ── Full Refined App UI Workspace: OmnigentChatPanel Reused ── */
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <OmnigentChatPanel
              sandboxId={activeSession.sandbox_id}
              sessionId={activeSession.id}
              sessionTitle={activeSession.title}
              agentName={activeSession.agent_type}
              isDevPodRunning={isSandboxReady}
              showHeader={true}
              messages={mappedMessages}
              onSendMessage={handleSendMessage}
              onAgentChange={(newAgent) => {
                // Keep local state in sync if agent is changed
                setActiveSession((prev) => (prev ? { ...prev, agent_type: newAgent } : null));
              }}
            />
          </div>
        )}
      </main>

      {/* ── Create Session Modal (Refined Light App UI Styling) ── */}
      <CreateAgentSessionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={async (payload) => {
          try {
            const newSession = await agentRuntimeApi.createSession(payload);
            toast.success(`Agent session created (${newSession.agent_type})`);
            setIsCreateModalOpen(false);
            await fetchSessions(true);
          } catch (err: any) {
            toast.error(err?.response?.data?.detail || 'Failed to create agent session');
            throw err;
          }
        }}
      />
    </div>
  );
}
