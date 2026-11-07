// @ts-nocheck
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Search,
  SquarePen,
  Trash2,
  Loader2,
  Lock,
  Play,
  AlertCircle,
  Server,
  PanelLeft,
  PanelLeftClose,
  MoreHorizontal,
  Plus,
  Folder,
  ChevronRight,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { agentRuntimeApi, type AgentCatalogItem, type AgentRuntimeProject, type AgentRuntimeSession } from '@/modules/agents/agentRuntimeApi';
import { AgentRuntimeComposer, type RuntimeAgentType } from '@/modules/agents/components/AgentRuntimeComposer';
import { AgentRuntimeChat } from '@/modules/agents/components/AgentRuntimeChat';
import { AgentRuntimeRail } from '@/modules/agents/components/AgentRuntimeRail';
import { SandboxTerminal } from '@/components/sandbox/SandboxTerminal';
import { computeApi } from '@/modules/compute/computeApi';
import { fetchAIGatewayModels } from '@/modules/ai_gateway/api';

const AGENT_CONFIGS: Record<string, { name: string; tag: string; badge: string; color: string; bg: string }> = {
  nova: {
    name: 'Nova',
    tag: 'nova',
    badge: 'CompassX',
    color: '#4f46e5',
    bg: 'rgba(79, 70, 229, 0.12)',
  },
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
  claude: {
    name: 'Claude Code',
    tag: 'claude',
    badge: 'Anthropic',
    color: '#d97706',
    bg: 'rgba(217, 119, 6, 0.12)',
  },
  codex: {
    name: 'Codex',
    tag: 'codex',
    badge: 'OpenAI',
    color: '#10b981',
    bg: 'rgba(16, 185, 129, 0.12)',
  },
  cursor: {
    name: 'Cursor',
    tag: 'cursor',
    badge: 'Agent CLI',
    color: '#6366f1',
    bg: 'rgba(99, 102, 241, 0.12)',
  },
};

const sidebarIconButton = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 26,
  height: 26,
  border: 'none',
  background: 'transparent',
  color: '#3f3f46',
  borderRadius: 6,
  cursor: 'pointer',
  padding: 0,
};

const sidebarRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  border: 'none',
  borderRadius: 6,
  padding: '6px 8px',
  color: '#1c1c1f',
  fontSize: '0.82rem',
  textAlign: 'left',
  cursor: 'pointer',
};

const sidebarSectionLabel = {
  padding: '10px 8px 4px',
  fontSize: '0.75rem',
  fontWeight: 500,
  color: '#8a8a93',
};

function relativeTime(value) {
  const then = new Date(value).getTime();
  if (!Number.isFinite(then)) return '';
  const minutes = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(value).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function isCliAgent(agentType?: string | null) {
  const id = (agentType || '').toLowerCase().trim();
  return Boolean(id) && id !== 'nova' && id !== 'compassx' && id !== 'compass';
}

export default function AgentRuntimePage() {
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useScopedNavigate();
  const toast = useToast();

  const [sessions, setSessions] = useState<AgentRuntimeSession[]>([]);
  const [projects, setProjects] = useState<AgentRuntimeProject[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(() => sessionStorage.getItem('agent-runtime-project'));
  const [expandedProjectIds, setExpandedProjectIds] = useState<string[]>([]);
  const [creatingProject, setCreatingProject] = useState(false);
  const [projectDraft, setProjectDraft] = useState('');
  const [savingProject, setSavingProject] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(routeSessionId || null);
  const [activeSession, setActiveSession] = useState<AgentRuntimeSession | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => sessionStorage.getItem('agent-runtime-sidebar') === 'collapsed');
  const [draftMessage, setDraftMessage] = useState('');
  const [draftSandboxId, setDraftSandboxId] = useState(() => sessionStorage.getItem('agent-runtime-sandbox') || 'new');
  const [draftAgent, setDraftAgent] = useState<string>(() => sessionStorage.getItem('agent-runtime-agent') || 'nova');
  const [draftLlmModel, setDraftLlmModel] = useState<string>(() => sessionStorage.getItem('agent-runtime-llm') || '');
  const [gatewayModels, setGatewayModels] = useState<{ id: string; label?: string }[]>([]);
  const [gatewayModelsLoading, setGatewayModelsLoading] = useState(false);
  const [draftBranch, setDraftBranch] = useState('');
  const [gitBranches, setGitBranches] = useState<string[]>([]);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [agentCatalog, setAgentCatalog] = useState<AgentCatalogItem[]>([
    { id: 'nova', label: 'Nova' },
    { id: 'antigravity', label: 'Antigravity' },
    { id: 'pi', label: 'Pi' },
    { id: 'opencode', label: 'OpenCode' },
    { id: 'claude', label: 'Claude Code' },
    { id: 'codex', label: 'Codex' },
    { id: 'cursor', label: 'Cursor' },
  ]);
  const [surface, setSurface] = useState<'terminal' | 'chat'>(() => (sessionStorage.getItem('agent-runtime-surface') === 'chat' ? 'chat' : 'terminal'));
  const showCliSurface = isCliAgent(activeSession?.agent_type);
  const activeSurface = showCliSurface ? surface : 'chat';
  const [sandboxes, setSandboxes] = useState<{ id: string; name: string; status?: string }[]>([]);
  const [sandboxesLoading, setSandboxesLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [workspaceRefresh, setWorkspaceRefresh] = useState(0);
  const [railOpen, setRailOpen] = useState(false);
  const [railFull, setRailFull] = useState(false);
  const [railWidth, setRailWidth] = useState(() => {
    const limit = Math.max(320, window.innerWidth - 980);
    const saved = Number(sessionStorage.getItem('agent-runtime-rail-width'));
    const next = Number.isFinite(saved) && saved >= 320 ? saved : 480;
    return Math.min(next, limit);
  });
  const [sessionMenuId, setSessionMenuId] = useState<string | null>(null);
  const [sessionMenuPos, setSessionMenuPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);

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

      if (routeSessionId && data && data.length > 0) {
        const matched = data.find((s) => s.id === routeSessionId);
        if (matched) {
          setActiveSessionId(matched.id);
          setActiveSession(matched);
        }
      } else if (!routeSessionId) {
        setActiveSessionId(null);
        setActiveSession(null);
      }
      if (autoSelectLatest && data && data[0]) {
        setActiveSessionId(data[0].id);
        setActiveSession(data[0]);
        navigate(`/agent-runtime/${data[0].id}`, { replace: true });
      }
    } catch (err: any) {
      console.error('Failed to load agent sessions:', err);
      toast.error('Failed to load agent sessions');
    } finally {
      setLoadingSessions(false);
    }
  }, [routeSessionId, activeSessionId, navigate, toast]);

  useEffect(() => {
    sessionStorage.setItem('agent-runtime-sidebar', sidebarCollapsed ? 'collapsed' : 'expanded');
  }, [sidebarCollapsed]);

  useEffect(() => {
    fetchSessions();
    agentRuntimeApi.listProjects().then((data) => setProjects(data || [])).catch(() => toast.error('Failed to load projects'));
    agentRuntimeApi.listAgents().then((data) => {
      if (data?.length) setAgentCatalog(data);
    }).catch(() => undefined);
    setGatewayModelsLoading(true);
    fetchAIGatewayModels()
      .then((models) => {
        const options = (models || []).map((model) => ({ id: model.id, label: model.id }));
        setGatewayModels(options);
        setDraftLlmModel((current) => {
          if (current && options.some((item) => item.id === current)) return current;
          const fallback = options.find((item) => models.find((model) => model.id === item.id && model.is_default)) || options[0];
          const next = fallback?.id || '';
          if (next) sessionStorage.setItem('agent-runtime-llm', next);
          return next;
        });
      })
      .catch(() => setGatewayModels([]))
      .finally(() => setGatewayModelsLoading(false));
  }, []);

  // Sync route param change
  useEffect(() => {
    if (!routeSessionId) {
      setActiveSessionId(null);
      setActiveSession(null);
      return;
    }
    if (routeSessionId !== activeSessionId) {
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

  useEffect(() => {
    if (activeSession) return;
    setSandboxesLoading(true);
    computeApi
      .listSandboxes()
      .then((list) => {
        const options = (list || []).map((sandbox) => ({
          id: sandbox.id,
          name: sandbox.name || sandbox.id,
          status: sandbox.status,
        }));
        setSandboxes(options);
        setDraftSandboxId((current) => (current !== 'new' && !options.some((item) => item.id === current) ? 'new' : current));
      })
      .catch(() => {
        setSandboxes([]);
      })
      .finally(() => setSandboxesLoading(false));
  }, [activeSession]);

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
    if (s.project_id) {
      setActiveProjectId(s.project_id);
      setExpandedProjectIds((current) => (current.includes(s.project_id) ? current : [...current, s.project_id]));
    }
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

  const promptStorageKey = (sessionId: string) => `agent-runtime-prompt:${sessionId}`;
  const startedPromptIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!activeSession) return;
    const next = isCliAgent(activeSession.agent_type) ? 'terminal' : 'chat';
    setSurface(next);
    sessionStorage.setItem('agent-runtime-surface', next);
  }, [activeSession?.id, activeSession?.agent_type]);

  useEffect(() => {
    if (!activeSession || !isSandboxReady) return;
    const key = promptStorageKey(activeSession.id);
    const pending = sessionStorage.getItem(key);
    if (!pending) return;
    if ((activeSession.messages || []).some((message) => message.role === 'user')) {
      sessionStorage.removeItem(key);
      return;
    }
    if (startedPromptIds.current.has(activeSession.id)) return;
    startedPromptIds.current.add(activeSession.id);
    sessionStorage.removeItem(key);
    setStarting(true);
    agentRuntimeApi
      .startSession(
        activeSession.id,
        pending,
        isCliAgent(activeSession.agent_type) ? undefined : activeSession.llm_model || draftLlmModel || undefined,
      )
      .then((userMessage) => {
        setActiveSession((prev) => (prev ? { ...prev, messages: [...(prev.messages || []), userMessage] } : prev));
        setWorkspaceRefresh((value) => value + 1);
      })
      .catch((err) => {
        startedPromptIds.current.delete(activeSession.id);
        toast.error(err?.response?.data?.detail || err?.message || 'Failed to start the agent');
      })
      .finally(() => setStarting(false));
  }, [activeSession, isSandboxReady, toast]);

  const beginNewSession = (projectId?: string) => {
    if (projectId) {
      setActiveProjectId(projectId);
      sessionStorage.setItem('agent-runtime-project', projectId);
      setExpandedProjectIds((current) => (current.includes(projectId) ? current : [...current, projectId]));
    }
    setDraftMessage('');
    navigate('/agent-runtime');
  };

  useEffect(() => {
    if (activeProjectId) sessionStorage.setItem('agent-runtime-project', activeProjectId);
    else sessionStorage.removeItem('agent-runtime-project');
  }, [activeProjectId]);

  useEffect(() => {
    if (!projects.length || !activeProjectId) return;
    if (!projects.some((project) => project.id === activeProjectId)) setActiveProjectId(null);
  }, [projects, activeProjectId]);

  useEffect(() => {
    if (!draftSandboxId || draftSandboxId === 'new') {
      setGitBranches([]);
      setDraftBranch('');
      setBranchesLoading(false);
      return undefined;
    }
    let cancelled = false;
    setBranchesLoading(true);
    agentRuntimeApi
      .sandboxGit(draftSandboxId)
      .then((info) => {
        if (cancelled) return;
        if (!info.repo || !info.branches.length) {
          setGitBranches([]);
          setDraftBranch('');
          return;
        }
        const saved = sessionStorage.getItem(`agent-runtime-branch:${draftSandboxId}`) || '';
        const next = info.branches.includes(saved) ? saved : info.branch || info.branches[0];
        setGitBranches(info.branches);
        setDraftBranch(next);
      })
      .catch(() => {
        if (!cancelled) {
          setGitBranches([]);
          setDraftBranch('');
        }
      })
      .finally(() => {
        if (!cancelled) setBranchesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [draftSandboxId]);

  const handleCreateProject = async (eventOrName?: { preventDefault?: () => void } | string) => {
    if (typeof eventOrName !== 'string') eventOrName?.preventDefault?.();
    const name = (typeof eventOrName === 'string' ? eventOrName : projectDraft).trim();
    if (!name || savingProject) return;
    setSavingProject(true);
    try {
      const created = await agentRuntimeApi.createProject(name);
      setProjects((current) => [created, ...current.filter((project) => project.id !== created.id)]);
      setActiveProjectId(created.id);
      sessionStorage.setItem('agent-runtime-project', created.id);
      setExpandedProjectIds((current) => (current.includes(created.id) ? current : [...current, created.id]));
      setProjectDraft('');
      setCreatingProject(false);
      navigate('/agent-runtime');
    } catch (err) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create project');
    } finally {
      setSavingProject(false);
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    if (!window.confirm('Delete this project? Its sessions stay in No project.')) return;
    try {
      await agentRuntimeApi.deleteProject(projectId);
      setProjects((current) => current.filter((project) => project.id !== projectId));
      setSessions((current) => current.map((session) => (session.project_id === projectId ? { ...session, project_id: null } : session)));
      if (activeProjectId === projectId) setActiveProjectId(null);
      setExpandedProjectIds((current) => current.filter((id) => id !== projectId));
    } catch (err) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete project');
    }
  };

  const handleCreateFromComposer = async () => {
    const content = draftMessage.trim();
    if (!content || starting) return;
    setStarting(true);
    try {
      const title = content.replace(/\s+/g, ' ').slice(0, 72);
      sessionStorage.setItem('agent-runtime-sandbox', draftSandboxId);
      sessionStorage.setItem('agent-runtime-agent', draftAgent);
      const nextSurface = isCliAgent(draftAgent) ? 'terminal' : 'chat';
      setSurface(nextSurface);
      sessionStorage.setItem('agent-runtime-surface', nextSurface);
      if (draftBranch && draftSandboxId !== 'new') {
        sessionStorage.setItem(`agent-runtime-branch:${draftSandboxId}`, draftBranch);
      }
      const created = await agentRuntimeApi.createSession({
        title,
        agent_type: draftAgent as RuntimeAgentType,
        sandbox_mode: draftSandboxId === 'new' ? 'new' : 'existing',
        sandbox_id: draftSandboxId === 'new' ? undefined : draftSandboxId,
        project_id: activeProjectId || undefined,
        branch: draftSandboxId !== 'new' && draftBranch ? draftBranch : undefined,
        llm_model: draftAgent === 'nova' ? draftLlmModel || undefined : undefined,
      });
      sessionStorage.setItem(promptStorageKey(created.id), content);
      setDraftMessage('');
      setSessions((prev) => [created, ...prev.filter((session) => session.id !== created.id)]);
      setActiveSessionId(created.id);
      setActiveSession(created);
      navigate(`/agent-runtime/${created.id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create agent session');
    } finally {
      setStarting(false);
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

  const projectIds = useMemo(() => new Set(projects.map((project) => project.id)), [projects]);
  const looseSessions = filteredSessions.filter((session) => !session.project_id || !projectIds.has(session.project_id));
  const sidebarEntries = [];
  projects.forEach((project) => {
    sidebarEntries.push({ kind: 'project', id: `project-${project.id}`, project });
    if (!expandedProjectIds.includes(project.id)) return;
    const children = filteredSessions.filter((session) => session.project_id === project.id);
    if (children.length === 0) sidebarEntries.push({ kind: 'empty', id: `empty-${project.id}` });
    children.forEach((session) => sidebarEntries.push({ kind: 'session', id: session.id, session, nested: true }));
  });
  if (looseSessions.length > 0) {
    sidebarEntries.push({ kind: 'label', id: 'loose-label' });
    looseSessions.forEach((session) => sidebarEntries.push({ kind: 'session', id: session.id, session, nested: false }));
  }

  useEffect(() => {
    if (!sessionMenuId) return undefined;
    const close = (event) => {
      const target = event.target;
      if (target instanceof Element && target.closest('[data-session-menu], [data-session-menu-panel]')) return;
      setSessionMenuId(null);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [sessionMenuId]);

  return (
    <div
      className="agent-runtime-page"
      style={{
        display: 'flex',
        flex: 1,
        height: '100%',
        minHeight: 0,
        width: '100%',
        overflow: 'hidden',
        background: '#f8fafc',
        color: '#0f172a',
      }}
    >
      {/* ── Left Sidebar: Sessions List (Refined App UI styling) ── */}
      <aside
        style={{
          width: sidebarCollapsed ? 48 : 272,
          minWidth: sidebarCollapsed ? 48 : 272,
          flexShrink: 0,
          borderRight: '1px solid #e7e7e9',
          display: 'flex',
          flexDirection: 'column',
          background: '#f7f7f8',
          color: '#1c1c1f',
          overflow: 'hidden',
          transition: 'width 160ms ease, min-width 160ms ease',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: sidebarCollapsed ? 'center' : 'space-between', gap: 2, padding: '8px 8px 2px' }}>
          {!sidebarCollapsed && (
            <button
              type="button"
              aria-label="Search sessions"
              title="Search sessions"
              onClick={() => {
                setSearchOpen(true);
                requestAnimationFrame(() => document.getElementById('agent-runtime-search')?.focus());
              }}
              style={{ ...sidebarIconButton }}
              className="agent-runtime-sidebar-icon"
            >
              <Search size={15} />
            </button>
          )}
          <button
            type="button"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
            style={{ ...sidebarIconButton }}
            className="agent-runtime-sidebar-icon"
          >
            {sidebarCollapsed ? <PanelLeft size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>

        {sidebarCollapsed ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '8px 0' }}>
            <button
              type="button"
              aria-label="Search sessions"
              title="Search sessions"
              className="agent-runtime-sidebar-icon"
              style={sidebarIconButton}
              onClick={() => {
                setSidebarCollapsed(false);
                setSearchOpen(true);
                requestAnimationFrame(() => document.getElementById('agent-runtime-search')?.focus());
              }}
            >
              <Search size={15} />
            </button>
            <button
              type="button"
              aria-label="New session"
              title="New session"
              className="agent-runtime-sidebar-icon"
              style={sidebarIconButton}
              onClick={() => beginNewSession()}
            >
              <SquarePen size={15} />
            </button>
            <button
              type="button"
              aria-label="New project"
              title="New project"
              className="agent-runtime-sidebar-icon"
              style={sidebarIconButton}
              onClick={() => {
                setProjectDraft('');
                setCreatingProject(true);
              }}
            >
              <Plus size={15} />
            </button>
          </div>
        ) : (
        <>

        {(searchOpen || searchQuery) && (
          <div style={{ padding: '0 10px 6px' }}>
            <input
              id="agent-runtime-search"
              type="text"
              placeholder="Search sessions"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onBlur={() => {
                if (!searchQuery.trim()) setSearchOpen(false);
              }}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                background: '#ffffff',
                border: '1px solid #e4e4e7',
                borderRadius: 6,
                outline: 'none',
                color: '#1c1c1f',
                fontSize: '0.8rem',
                padding: '5px 8px',
              }}
            />
          </div>
        )}

        <button
          type="button"
          className={!activeSession ? 'agent-runtime-new-session is-active' : 'agent-runtime-new-session'}
          onClick={() => beginNewSession()}
          style={{
            ...sidebarRow,
            margin: '2px 8px',
            fontWeight: 500,
          }}
        >
          <SquarePen size={15} style={{ flexShrink: 0, color: '#3f3f46' }} />
          <span>New session</span>
        </button>

        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 8px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 2 }}>
            <div style={sidebarSectionLabel}>Projects</div>
            <button
              type="button"
              aria-label="New project"
              title="New project"
              className="agent-runtime-sidebar-icon"
              onClick={() => {
                setCreatingProject(true);
                setProjectDraft('');
              }}
              style={sidebarIconButton}
            >
              <Plus size={14} />
            </button>
          </div>
          {projects.length === 0 && (
            <div style={{ padding: '2px 8px 8px', color: '#8a8a93', fontSize: '0.75rem' }}>Create a project, then add a session.</div>
          )}
          {loadingSessions ? (
            <div style={{ padding: '10px 8px', color: '#8a8a93', fontSize: '0.78rem' }}>Loading…</div>
          ) : (
            sidebarEntries.map((entry) => {
              if (entry.kind === 'label') {
                return <div key={entry.id} style={sidebarSectionLabel}>No project</div>;
              }
              if (entry.kind === 'empty') {
                return <div key={entry.id} style={{ padding: '2px 8px 8px 28px', color: '#8a8a93', fontSize: '0.75rem' }}>No sessions yet</div>;
              }
              if (entry.kind === 'project') {
                const project = entry.project;
                const open = expandedProjectIds.includes(project.id);
                return (
                  <div
                    key={entry.id}
                    className="agent-runtime-project"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      setExpandedProjectIds((current) => (
                        current.includes(project.id) ? current.filter((id) => id !== project.id) : [...current, project.id]
                      ));
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '5px 6px',
                      borderRadius: 6,
                      cursor: 'pointer',
                      background: activeProjectId === project.id && !activeSession ? '#ececef' : 'transparent',
                    }}
                  >
                    <ChevronRight size={14} style={{ transform: open ? 'rotate(90deg)' : undefined, color: '#71717a', flexShrink: 0 }} />
                    <Folder size={14} style={{ color: '#71717a', flexShrink: 0 }} />
                    <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.82rem', fontWeight: 500 }}>
                      {project.name}
                    </span>
                    <button
                      type="button"
                      aria-label={`New session in ${project.name}`}
                      title="New session"
                      onClick={(event) => {
                        event.stopPropagation();
                        beginNewSession(project.id);
                      }}
                      style={{ border: 'none', background: 'transparent', color: '#3f3f46', cursor: 'pointer', padding: 2, display: 'inline-flex' }}
                    >
                      <Plus size={14} />
                    </button>
                    <button
                      type="button"
                      data-project-delete
                      aria-label={`Delete ${project.name}`}
                      title="Delete project"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDeleteProject(project.id);
                      }}
                      style={{ border: 'none', background: 'transparent', color: '#a1a1aa', cursor: 'pointer', padding: 2 }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              }
              const s = entry.session;
              const nested = entry.nested;
              const isActive = s.id === activeSessionId;
              const menuOpen = sessionMenuId === s.id;
              const cfg = AGENT_CONFIGS[s.agent_type] || AGENT_CONFIGS.antigravity;
              const updated = new Date(s.updated_at || s.created_at).toLocaleString([], {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              });
              const when = relativeTime(s.updated_at || s.created_at);
              return (
                <div
                  key={s.id}
                  data-session-menu-root
                  className="agent-runtime-session"
                  onClick={() => handleSelectSession(s)}
                  style={{
                    position: 'relative',
                    padding: nested ? '5px 8px 5px 26px' : '5px 8px',
                    borderRadius: 6,
                    marginBottom: 1,
                    cursor: 'pointer',
                    background: isActive ? '#ececef' : hoveredSessionId === s.id ? '#efeff1' : 'transparent',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 8,
                    minWidth: 0,
                  }}
                  onMouseEnter={() => setHoveredSessionId(s.id)}
                  onMouseLeave={() => setHoveredSessionId((current) => (current === s.id ? null : current))}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      marginTop: 6,
                      borderRadius: '50%',
                      flexShrink: 0,
                      background: isActive ? '#3f3f46' : '#c4c4cc',
                    }}
                  />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                      <span
                        style={{
                          fontSize: '0.82rem',
                          fontWeight: 500,
                          color: '#1c1c1f',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          minWidth: 0,
                          flex: 1,
                          lineHeight: 1.3,
                        }}
                        title={s.title}
                      >
                        {s.title}
                      </span>
                      <span style={{ position: 'relative', width: 32, height: 16, flexShrink: 0 }}>
                        <span
                          className="agent-runtime-session-time"
                          style={{
                            position: 'absolute',
                            right: 0,
                            top: 0,
                            fontSize: '0.72rem',
                            color: '#8a8a93',
                            lineHeight: '16px',
                          }}
                        >
                          {when}
                        </span>
                        <button
                          type="button"
                          data-session-menu
                          className={menuOpen ? 'is-open' : undefined}
                          aria-label="Session actions"
                          title="Session actions"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (menuOpen) {
                              setSessionMenuId(null);
                              return;
                            }
                            const row = e.currentTarget.closest('[data-session-menu-root]');
                            const rect = row.getBoundingClientRect();
                            setSessionMenuPos({ top: rect.bottom + 2, left: rect.left, width: rect.width });
                            setSessionMenuId(s.id);
                          }}
                          style={{
                            position: 'absolute',
                            right: -4,
                            top: -3,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 22,
                            height: 22,
                            background: menuOpen ? '#e4e4e7' : 'transparent',
                            border: 'none',
                            color: '#3f3f46',
                            cursor: 'pointer',
                            padding: 0,
                            borderRadius: 4,
                          }}
                        >
                          <MoreHorizontal size={14} />
                        </button>
                      </span>
                    </div>
                    <div
                      style={{
                        marginTop: 1,
                        fontSize: '0.72rem',
                        color: '#8a8a93',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        lineHeight: 1.3,
                      }}
                      title={`${cfg.name} · ${s.sandbox_id}`}
                    >
                      {cfg.tag} · {s.sandbox_id}
                    </div>
                  </div>
                  {menuOpen && (
                    <div
                      data-session-menu-panel
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        position: 'fixed',
                        top: sessionMenuPos?.top ?? 0,
                        left: sessionMenuPos?.left ?? 0,
                        zIndex: 40,
                        width: sessionMenuPos?.width ?? 220,
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: 8,
                        boxShadow: '0 8px 24px rgba(15, 23, 42, 0.12)',
                        padding: 6,
                      }}
                    >
                      <div style={{ padding: '6px 8px 8px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ fontSize: '0.68rem', fontWeight: 650, color: '#94a3b8', letterSpacing: '0.04em' }}>SANDBOX</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: '50%',
                              flexShrink: 0,
                              background: s.status === 'failed' ? '#ef4444' : s.status === 'provisioning' ? '#f59e0b' : '#10b981',
                            }}
                          />
                          <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {s.sandbox_id}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                          {s.status || 'unknown'} · {updated}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          setSessionMenuId(null);
                          handleDeleteSession(e, s.id);
                        }}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          background: 'transparent',
                          border: 'none',
                          borderTop: '1px solid #f1f5f9',
                          color: '#dc2626',
                          cursor: 'pointer',
                          padding: '8px',
                          borderRadius: 6,
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          textAlign: 'left',
                        }}
                      >
                        <Trash2 size={13} /> Delete session
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
        </>
        )}
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
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 24px',
              background: '#f8fafc',
            }}
          >
            <div style={{ width: 'min(680px, 100%)', margin: '0 auto' }}>
              <AgentRuntimeComposer
                mode="new"
                projects={projects}
                projectId={activeProjectId}
                sandboxes={sandboxes}
                sandboxesLoading={sandboxesLoading}
                sandboxId={draftSandboxId}
                agentType={draftAgent}
                branch={draftBranch}
                branches={gitBranches}
                branchesLoading={branchesLoading}
                value={draftMessage}
                submitting={starting}
                creatingProject={savingProject}
                agents={agentCatalog}
                llmModel={draftLlmModel}
                llmModels={gatewayModels}
                llmModelsLoading={gatewayModelsLoading}
                onLlmModelChange={(modelId) => {
                  setDraftLlmModel(modelId);
                  sessionStorage.setItem('agent-runtime-llm', modelId);
                }}
                onProjectChange={(projectId) => {
                  setActiveProjectId(projectId);
                }}
                onCreateProject={(name) => {
                  void handleCreateProject(name);
                }}
                onSandboxChange={(sandboxId) => {
                  setDraftSandboxId(sandboxId);
                  sessionStorage.setItem('agent-runtime-sandbox', sandboxId);
                }}
                onAgentChange={(agentId) => {
                  setDraftAgent(agentId);
                  sessionStorage.setItem('agent-runtime-agent', agentId);
                }}
                onBranchChange={(nextBranch) => {
                  setDraftBranch(nextBranch);
                  if (draftSandboxId !== 'new') sessionStorage.setItem(`agent-runtime-branch:${draftSandboxId}`, nextBranch);
                }}
                onChange={setDraftMessage}
                onSubmit={handleCreateFromComposer}
              />
            </div>
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
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ flex: 1, minHeight: 0, display: 'flex', position: 'relative' }}>
              <div style={{ flex: 1, minWidth: 560, minHeight: 0, overflow: 'hidden', display: railFull ? 'none' : 'flex', flexDirection: 'column' }}>
                <div
                  style={{
                    height: 35,
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    padding: '0 12px',
                    borderBottom: '1px solid #e2e8f0',
                    background: '#ffffff',
                  }}
                >
                  <div style={{ minWidth: 0, fontSize: '0.84rem', fontWeight: 650, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {activeSession.title}
                  </div>
                  {showCliSurface && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    <div role="tablist" aria-label="Agent surface" style={{ display: 'inline-flex', border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
                      {(['terminal', 'chat'] as const).map((item) => (
                        <button
                          key={item}
                          type="button"
                          role="tab"
                          aria-selected={activeSurface === item}
                          onClick={() => {
                            setSurface(item);
                            sessionStorage.setItem('agent-runtime-surface', item);
                          }}
                          style={{
                            border: 'none',
                            background: activeSurface === item ? '#18181b' : '#ffffff',
                            color: activeSurface === item ? '#ffffff' : '#475569',
                            padding: '4px 10px',
                            fontSize: '0.75rem',
                            fontWeight: 650,
                            cursor: 'pointer',
                          }}
                        >
                          {item === 'terminal' ? 'Terminal' : 'Chat'}
                        </button>
                      ))}
                    </div>
                  </div>
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0, minHeight: 0, width: '100%', display: activeSurface === 'terminal' ? 'flex' : 'none', flexDirection: 'column', overflow: 'hidden', background: '#ffffff' }}>
                  {showCliSurface && (
                  <SandboxTerminal
                    key={activeSession.id}
                    sandboxId={activeSession.sandbox_id}
                    sandboxName={activeSession.title}
                    workingDir="/workspace"
                    agent={activeSession.agent_type}
                    sessionId={activeSession.id}
                    isRunning={isSandboxReady}
                    onResume={handleResumeSandbox}
                    isDark={false}
                    embedded
                    fullHeight
                    visible={activeSurface === 'terminal'}
                  />
                  )}
                </div>
                {activeSurface === 'chat' && (
                  <AgentRuntimeChat
                    sessionId={activeSession.id}
                    agentLabel={agentCatalog.find((agent) => agent.id === activeSession.agent_type)?.label || AGENT_CONFIGS[activeSession.agent_type]?.name || activeSession.agent_type}
                    messages={activeSession.messages || []}
                    sandboxReady={isSandboxReady}
                    agentType={activeSession.agent_type}
                    llmModel={activeSession.llm_model || draftLlmModel}
                    llmModels={gatewayModels}
                    llmModelsLoading={gatewayModelsLoading}
                    onLlmModelChange={(modelId) => {
                      setDraftLlmModel(modelId);
                      sessionStorage.setItem('agent-runtime-llm', modelId);
                      setActiveSession((prev) => (prev ? { ...prev, llm_model: modelId } : prev));
                    }}
                    onMessage={(message) => {
                      setActiveSession((prev) => (prev ? { ...prev, messages: [...(prev.messages || []), message] } : prev));
                    }}
                    onSync={(messages) => {
                      setActiveSession((prev) => (prev ? { ...prev, messages } : prev));
                    }}
                  />
                )}
              </div>
              <AgentRuntimeRail
                key={activeSession.id}
                sessionId={activeSession.id}
                sandboxId={activeSession.sandbox_id}
                sandboxReady={isSandboxReady}
                onResume={handleResumeSandbox}
                refreshToken={workspaceRefresh}
                width={railWidth}
                fullscreen={railFull}
                collapsed={!railOpen}
                onWidthChange={(next) => {
                  setRailWidth(next);
                  sessionStorage.setItem('agent-runtime-rail-width', String(next));
                }}
                onToggleFullscreen={() => setRailFull((value) => !value)}
                onClose={() => {
                  setRailFull(false);
                  setRailOpen(false);
                }}
                onOpen={() => setRailOpen(true)}
                showTerminal={showCliSurface}
                onNote={(message) => {
                  setActiveSession((prev) => (prev ? { ...prev, messages: [...(prev.messages || []), message] } : prev));
                  setSurface('chat');
                }}
              />
            </div>
          </div>
        )}
      </main>
      {creatingProject && (
        <div
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setCreatingProject(false);
              setProjectDraft('');
            }
          }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 80,
            background: 'rgba(15, 23, 42, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
        >
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-project-title"
            onSubmit={handleCreateProject}
            style={{
              width: 'min(400px, 100%)',
              background: '#ffffff',
              borderRadius: 12,
              boxShadow: '0 16px 48px rgba(15, 23, 42, 0.18)',
              padding: 20,
            }}
          >
            <h2 id="new-project-title" style={{ margin: '0 0 6px', fontSize: '1.05rem', fontWeight: 650, color: '#0f172a' }}>
              New project
            </h2>
            <p style={{ margin: '0 0 14px', fontSize: '0.82rem', color: '#64748b' }}>
              Sessions you start are kept inside this project.
            </p>
            <input
              autoFocus
              value={projectDraft}
              placeholder="Project name"
              aria-label="Project name"
              onChange={(event) => setProjectDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setCreatingProject(false);
                  setProjectDraft('');
                }
              }}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                border: '1px solid #e4e4e7',
                borderRadius: 8,
                padding: '9px 12px',
                fontSize: '0.9rem',
                outline: 'none',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button
                type="button"
                onClick={() => {
                  setCreatingProject(false);
                  setProjectDraft('');
                }}
                style={{
                  border: '1px solid #e4e4e7',
                  background: '#ffffff',
                  color: '#334155',
                  borderRadius: 8,
                  padding: '8px 12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingProject || !projectDraft.trim()}
                style={{
                  border: 'none',
                  background: '#18181b',
                  color: '#ffffff',
                  borderRadius: 8,
                  padding: '8px 14px',
                  fontWeight: 600,
                  cursor: savingProject || !projectDraft.trim() ? 'default' : 'pointer',
                  opacity: savingProject || !projectDraft.trim() ? 0.5 : 1,
                }}
              >
                Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
