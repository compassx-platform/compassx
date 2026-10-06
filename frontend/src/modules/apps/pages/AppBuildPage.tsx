import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Boxes,
  Hammer,
  Loader2,
  Clock,
  AlertCircle,
  RefreshCw,
  Server,
  MoreVertical,
  Square,
  Play,
  Terminal,
  ChevronDown,
  ChevronUp,
  Copy,
  FolderTree,
  Layers,
  PanelLeftOpen,
  PanelLeftClose,
  ExternalLink,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import {
  useApp,
  useDevStatus,
  useStartDevSession,
  useStopDevSession,
  useVerifyGitWorkspace,
  useInstallDevDependencies,
  useRunDevApp,
  useDevLogs,
  useDevFiles,
  useDevSessions,
  useCreateDevSession,
  useDeleteDevSession,
  useDevWorkspaces,
  useActivateDevWorkspace,
  type DevSession,
  type DevWorkspace,
} from '../hooks/useApps';
import { DevTerminal } from '../components/DevTerminal';
import { SessionsSidebar } from '../components/SessionsSidebar';
import { useNewShellHotkey } from '../hooks/useNewShellHotkey';
import { NewSessionModal } from '../components/NewSessionModal';
import { SandboxSelector } from '../components/SandboxSelector';
import { NewSandboxModal } from '../components/NewSandboxModal';
import { FileExplorerSidepanel } from '../components/files/FileExplorerSidepanel';
import { FilesPanel } from '../components/files/FilesPanel';
import { FileViewer } from '../components/files/FileViewer';

interface BuildStep {
  id: string;
  title: string;
  description: string;
}

const BUILD_STEPS: BuildStep[] = [
  {
    id: 'sandbox',
    title: 'Starting Dev Sandbox',
    description: 'Spinning up container runtime and verifying dev sandbox environment...',
  },
  {
    id: 'code_prep',
    title: 'Preparing Workspace Code',
    description: 'Verifying repository codebase and preparing dev environment...',
  },
  {
    id: 'install_libs',
    title: 'Installing Libraries',
    description: 'Checking and installing application libraries and dependencies...',
  },
  {
    id: 'run_app',
    title: 'Running Application',
    description: 'Starting application services and verifying dev server...',
  },
];

type SandboxStage = 'running' | 'starting' | 'stopping' | 'stopped';

export type SupportedAgent = 'pi' | 'opencode' | 'antigravity' | 'bash';

export interface AgentOption {
  id: SupportedAgent;
  name: string;
  binary: string;
  tagline: string;
  badge: string;
  description: string;
  color: string;
  accentBg: string;
  borderColor: string;
}

export const AGENT_OPTIONS: AgentOption[] = [
  {
    id: 'pi',
    name: 'Pi CLI',
    binary: 'pi',
    tagline: 'Lightweight & Minimal',
    badge: 'FAST',
    description: 'Minimalist terminal coding agent with interactive tools and native sub-process orchestration.',
    color: '#c084fc',
    accentBg: 'rgba(192, 132, 252, 0.12)',
    borderColor: 'rgba(192, 132, 252, 0.35)',
  },
  {
    id: 'opencode',
    name: 'OpenCode',
    binary: 'opencode',
    tagline: 'Full-featured TUI',
    badge: 'POPULAR',
    description: 'Autonomous open-source AI software engineer with native multi-file editing and ACP/MCP protocols.',
    color: '#38bdf8',
    accentBg: 'rgba(56, 189, 248, 0.12)',
    borderColor: 'rgba(56, 189, 248, 0.35)',
  },
  {
    id: 'antigravity',
    name: 'Antigravity',
    binary: 'agy',
    tagline: 'Deep Reasoning',
    badge: 'ADVANCED',
    description: 'Advanced agentic assistant with planning workflows, recursive subagents, and deep tool use.',
    color: '#4ade80',
    accentBg: 'rgba(74, 222, 128, 0.12)',
    borderColor: 'rgba(74, 222, 128, 0.35)',
  },
  {
    id: 'bash',
    name: 'Bash Shell',
    binary: 'bash',
    tagline: 'Interactive System Shell',
    badge: 'SHELL',
    description: 'Interactive Linux Bash shell inside the active workspace container with full PTY and toolchain access.',
    color: '#f59e0b',
    accentBg: 'rgba(245, 158, 11, 0.12)',
    borderColor: 'rgba(245, 158, 11, 0.35)',
  },
];

export default function AppBuildPage() {
  const params = useParams<{ applicationId?: string; appId?: string }>();
  const resolvedAppId =
    params.applicationId ||
    (params.appId && params.appId !== 'apps' && params.appId !== 'platform' && params.appId !== 'portal' ? params.appId : undefined);

  const navigate = useScopedNavigate();
  const toast = useToast();

  const { data: app, isLoading: isAppLoading } = useApp(resolvedAppId);
  const { data: devStatus, isLoading: isDevLoading, refetch: refetchDevStatus } = useDevStatus(resolvedAppId);
  const startDevMutation = useStartDevSession();
  const stopDevMutation = useStopDevSession();
  const verifyGitMutation = useVerifyGitWorkspace();
  const installDepsMutation = useInstallDevDependencies();
  const runAppMutation = useRunDevApp();
  const { data: devWorkspaces = [], refetch: refetchDevWorkspaces } = useDevWorkspaces(resolvedAppId);
  const activateWorkspaceMutation = useActivateDevWorkspace();
  const [isNewSandboxModalOpen, setIsNewSandboxModalOpen] = useState<boolean>(false);
  const [isSwitchingSandbox, setIsSwitchingSandbox] = useState<boolean>(false);

  // Current active sandbox/workspace
  const activeWorkspace =
    devWorkspaces.find((w) => w.id === devStatus?.workspace_id || w.name === devStatus?.workspace_name) ||
    devWorkspaces.find((w) => w.status === 'active') ||
    devWorkspaces[0];

  const handleSelectWorkspace = async (workspaceId: string) => {
    if (!resolvedAppId || workspaceId === activeWorkspace?.id) return;
    try {
      setIsSwitchingSandbox(true);
      await activateWorkspaceMutation.mutateAsync({
        appId: resolvedAppId,
        workspaceId,
      });
      toast.success('Switched active sandbox.');
      refetchDevStatus();
      refetchDevWorkspaces();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to switch sandbox');
    } finally {
      setIsSwitchingSandbox(false);
    }
  };

  const [startError, setStartError] = useState<string | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
  const [userExplicitlyStopped, setUserExplicitlyStopped] = useState<boolean>(false);
  const selectedHost: 'compassx' | 'omnigent' = 'compassx';
  const selectedAgent: SupportedAgent = 'opencode';

  const [initStep, setInitStep] = useState<number>(0);
  const [step2Completed, setStep2Completed] = useState<boolean>(false);
  const [step3Completed, setStep3Completed] = useState<boolean>(false);
  const [step4Completed, setStep4Completed] = useState<boolean>(false);
  const [hasCompletedInit, setHasCompletedInit] = useState<boolean>(false);
  const [isLogViewerOpen, setIsLogViewerOpen] = useState<boolean>(false);
  const [gitOutput, setGitOutput] = useState<string>('');
  const [installOutput, setInstallOutput] = useState<string>('');
  const [runAppOutput, setRunAppOutput] = useState<string>('');
  const [autoScrollLogs, setAutoScrollLogs] = useState<boolean>(true);

  const menuRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const hasTriggeredInitialStart = useRef<boolean>(false);
  const initialChecked = useRef<boolean>(false);
  const verifyGitTriggered = useRef<boolean>(false);
  const installDepsTriggered = useRef<boolean>(false);
  const runAppTriggered = useRef<boolean>(false);

  // ── Unified Sandbox Stage Calculation ──────────────────────────────────────────
  const isContainerRunning = devStatus?.status === 'active' || devStatus?.phase === 'Running';
  const isStoppingOperation =
    stopDevMutation.isPending ||
    devStatus?.status === 'stopping' ||
    devStatus?.phase === 'Terminating';

  let stage: SandboxStage;
  if (isStoppingOperation) {
    stage = 'stopping';
  } else if (userExplicitlyStopped) {
    stage = 'stopped';
  } else if (isContainerRunning && hasCompletedInit) {
    stage = 'running';
  } else if (startDevMutation.isPending || devStatus?.status === 'provisioning' || (isContainerRunning && !hasCompletedInit)) {
    stage = 'starting';
  } else {
    stage = 'stopped';
  }

  // Live container logs query (active when log viewer is open)
  const { data: devLogsData } = useDevLogs(resolvedAppId, isLogViewerOpen && stage === 'starting');

  // ── Multi-Session State (App-Scoped) ──────────────────────────────────────────
  const { data: devSessions = [] } = useDevSessions(resolvedAppId, isContainerRunning);
  const createDevSessionMutation = useCreateDevSession(resolvedAppId);
  const deleteDevSessionMutation = useDeleteDevSession(resolvedAppId);

  const [justCreatedSession, setJustCreatedSession] = useState<DevSession | null>(null);

  // Merge newly created session into list until backend query refetches and includes it
  const allSessions: DevSession[] = useMemo(() => {
    const list: DevSession[] = devSessions || [];
    if (!justCreatedSession) return list;
    if (list.some((s: DevSession) => s.id === justCreatedSession.id)) return list;
    return [justCreatedSession, ...list];
  }, [devSessions, justCreatedSession]);

  // Once backend devSessions includes the created session, clear justCreatedSession
  useEffect(() => {
    if (justCreatedSession && devSessions.some((s: DevSession) => s.id === justCreatedSession.id)) {
      setJustCreatedSession(null);
    }
  }, [devSessions, justCreatedSession]);

  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(`compassx_active_session_${resolvedAppId}`) || null;
    } catch (_) {
      return null;
    }
  });

  // Synchronize activeSessionId when switching apps
  useEffect(() => {
    if (!resolvedAppId) return;
    try {
      const saved = localStorage.getItem(`compassx_active_session_${resolvedAppId}`);
      if (saved) {
        setActiveSessionId(saved);
      }
    } catch (_) {}
  }, [resolvedAppId]);

  const [isNewSessionModalOpen, setIsNewSessionModalOpen] = useState(false);
  const [isSwitchingSession, setIsSwitchingSession] = useState(false);

  // Auto-select first session if none selected or selected was deleted
  useEffect(() => {
    if (allSessions.length > 0) {
      const exists = allSessions.some((s: DevSession) => s.id === activeSessionId);
      if (!activeSessionId || !exists) {
        const firstId = allSessions[0].id;
        setActiveSessionId(firstId);
        try {
          localStorage.setItem(`compassx_active_session_${resolvedAppId}`, firstId);
        } catch (_) {}
      }
    }
  }, [allSessions, activeSessionId, resolvedAppId]);

  const activeSession = allSessions.find((s: DevSession) => s.id === activeSessionId) || allSessions[0];
  const currentAgent = (activeSession?.agent as SupportedAgent) || selectedAgent;

  const handleSelectSession = (sessionId: string) => {
    if (sessionId !== activeSessionId) {
      setIsSwitchingSession(true);
    }
    setActiveSessionId(sessionId);
    try {
      localStorage.setItem(`compassx_active_session_${resolvedAppId}`, sessionId);
    } catch (_) {}
  };

  const handleCreateSession = async (title: string, agent: SupportedAgent, model?: string) => {
    try {
      setIsSwitchingSession(true);
      const created = await createDevSessionMutation.mutateAsync({
        title,
        agent,
        workspace_id: activeWorkspace?.id || devStatus?.workspace_id,
        model,
      });
      setJustCreatedSession(created);
      setActiveSessionId(created.id);
      try {
        localStorage.setItem(`compassx_active_session_${resolvedAppId}`, created.id);
      } catch (_) {}
      setIsNewSessionModalOpen(false);
      const modelSuffix = created.model ? ` (${created.model})` : '';
      toast.success(`Session "${created.title}" started with ${created.agent}${modelSuffix}.`);
    } catch (err: any) {
      setIsSwitchingSession(false);
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create session');
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteDevSessionMutation.mutateAsync(sessionId);
      if (justCreatedSession?.id === sessionId) {
        setJustCreatedSession(null);
      }
      toast.success('Session deleted.');
      if (activeSessionId === sessionId) {
        const remaining = allSessions.filter((s: DevSession) => s.id !== sessionId);
        if (remaining.length > 0) {
          handleSelectSession(remaining[0].id);
        } else {
          setActiveSessionId(null);
          try {
            localStorage.removeItem(`compassx_active_session_${resolvedAppId}`);
          } catch (_) {}
        }
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete session');
    }
  };

  const handleCreateShellSession = async () => {
    try {
      setIsSwitchingSession(true);
      const shellCount = (allSessions || []).filter((s) => s.agent === 'bash').length + 1;
      const created = await createDevSessionMutation.mutateAsync({
        title: `Shell ${shellCount}`,
        agent: 'bash',
        workspace_id: activeWorkspace?.id || devStatus?.workspace_id,
      });
      setJustCreatedSession(created);
      setActiveSessionId(created.id);
      try {
        localStorage.setItem(`compassx_active_session_${resolvedAppId}`, created.id);
      } catch (_) {}
      setIsNewSessionModalOpen(false);
      toast.success(`Started new Bash Shell #${shellCount}`);
    } catch (err: any) {
      setIsSwitchingSession(false);
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to start shell session');
    }
  };

  useNewShellHotkey(handleCreateShellSession, isContainerRunning);

  // ── Sessions Secondary Sidebar State ──────────────────────────────────────────
  const [showSessionsSidebar, setShowSessionsSidebar] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('compassx_show_sessions_sidebar');
      if (saved !== null) return saved === 'true';
    } catch (_) {}
    return true;
  });

  const [sessionsSidebarWidth, setSessionsSidebarWidth] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('compassx_sessions_sidebar_width');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (Number.isFinite(parsed) && parsed >= 200 && parsed <= 450) return parsed;
      }
    } catch (_) {}
    return 260;
  });

  const [isSessionsResizing, setIsSessionsResizing] = useState<boolean>(false);
  const isSessionsResizingRef = useRef<boolean>(false);
  const startSessionsXRef = useRef<number>(0);
  const startSessionsWidthRef = useRef<number>(260);
  const sessionsSidebarWidthRef = useRef<number>(sessionsSidebarWidth);

  useEffect(() => {
    sessionsSidebarWidthRef.current = sessionsSidebarWidth;
  }, [sessionsSidebarWidth]);

  const [isSessionsMaximized, setIsSessionsMaximized] = useState<boolean>(false);
  const toggleSessionsMaximized = () => {
    setIsSessionsMaximized((prev) => {
      const next = !prev;
      const targetWidth = next ? 420 : 260;
      setSessionsSidebarWidth(targetWidth);
      sessionsSidebarWidthRef.current = targetWidth;
      try {
        localStorage.setItem('compassx_sessions_sidebar_width', String(targetWidth));
      } catch (_) {}
      return next;
    });
  };

  // ── File Explorer State ────────────────────────────────────────────────────────
  const [showFileExplorer, setShowFileExplorer] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('compassx_show_file_explorer');
      if (saved !== null) return saved === 'true';
    } catch (_) {}
    return true;
  });
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [isExplorerMaximized, setIsExplorerMaximized] = useState<boolean>(false);

  // Clear selected file when switching active sandbox/workspace
  useEffect(() => {
    setSelectedFilePath(null);
  }, [activeWorkspace?.id]);

  // User-adjustable widths for Tree view vs Viewer mode (persisted to localStorage)
  const [treeWidth, setTreeWidth] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('compassx_file_tree_width') || localStorage.getItem('compassx_file_explorer_width');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (Number.isFinite(parsed) && parsed >= 260 && parsed <= 1600) return parsed;
      }
    } catch (_) {}
    return 360;
  });

  const [viewerWidth, setViewerWidth] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('compassx_file_viewer_width');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (Number.isFinite(parsed) && parsed >= 280 && parsed <= 1600) return parsed;
      }
    } catch (_) {}
    return 540;
  });

  const [isExplorerResizing, setIsExplorerResizing] = useState<boolean>(false);

  // Refs to ensure mousemove/mouseup handlers have direct access without stale closures
  const isResizingRef = useRef<boolean>(false);
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(360);
  const treeWidthRef = useRef<number>(treeWidth);
  const viewerWidthRef = useRef<number>(viewerWidth);
  const selectedFilePathRef = useRef<string | null>(selectedFilePath);
  const asideRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    treeWidthRef.current = treeWidth;
  }, [treeWidth]);

  useEffect(() => {
    viewerWidthRef.current = viewerWidth;
  }, [viewerWidth]);

  useEffect(() => {
    selectedFilePathRef.current = selectedFilePath;
  }, [selectedFilePath]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      // Left-side sessions panel: moving cursor right increases width
      if (isSessionsResizingRef.current) {
        e.preventDefault();
        const deltaX = e.clientX - startSessionsXRef.current;
        const rawWidth = startSessionsWidthRef.current + deltaX;
        const clampedWidth = Math.min(Math.max(200, rawWidth), 450);
        setSessionsSidebarWidth(clampedWidth);
        sessionsSidebarWidthRef.current = clampedWidth;
        return;
      }

      if (!isResizingRef.current) return;
      e.preventDefault();

      // Right-side panel: moving cursor left (e.clientX decreases) increases width
      const deltaX = startXRef.current - e.clientX;
      const rawWidth = startWidthRef.current + deltaX;

      const minWidth = 280;
      const maxWidth = Math.max(minWidth, Math.floor(window.innerWidth * 0.75));
      const clampedWidth = Math.min(Math.max(minWidth, rawWidth), maxWidth);

      if (selectedFilePathRef.current) {
        setViewerWidth(clampedWidth);
        viewerWidthRef.current = clampedWidth;
      } else {
        setTreeWidth(clampedWidth);
        treeWidthRef.current = clampedWidth;
      }
    };

    const handleMouseUp = () => {
      if (isSessionsResizingRef.current) {
        isSessionsResizingRef.current = false;
        setIsSessionsResizing(false);
        try {
          localStorage.setItem('compassx_sessions_sidebar_width', String(sessionsSidebarWidthRef.current));
        } catch (_) {}
      }

      if (!isResizingRef.current) return;
      isResizingRef.current = false;
      setIsExplorerResizing(false);

      try {
        if (selectedFilePathRef.current) {
          localStorage.setItem('compassx_file_viewer_width', String(viewerWidthRef.current));
        } else {
          localStorage.setItem('compassx_file_tree_width', String(treeWidthRef.current));
          localStorage.setItem('compassx_file_explorer_width', String(treeWidthRef.current));
        }
      } catch (_) {}
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const handleSessionsResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isSessionsResizingRef.current = true;
    setIsSessionsResizing(true);
    startSessionsXRef.current = e.clientX;
    startSessionsWidthRef.current = sessionsSidebarWidthRef.current;
  };

  const handleResetSessionsWidth = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setSessionsSidebarWidth(260);
    sessionsSidebarWidthRef.current = 260;
    try {
      localStorage.setItem('compassx_sessions_sidebar_width', '260');
    } catch (_) {}
  };

  const handleResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    isResizingRef.current = true;
    setIsExplorerResizing(true);
    startXRef.current = e.clientX;

    if (isExplorerMaximized) {
      setIsExplorerMaximized(false);
      startWidthRef.current = asideRef.current?.getBoundingClientRect().width ?? (selectedFilePath ? viewerWidth : treeWidth);
    } else {
      startWidthRef.current = selectedFilePath ? viewerWidthRef.current : treeWidthRef.current;
    }
  };

  const handleResetWidth = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (selectedFilePath) {
      setViewerWidth(540);
      viewerWidthRef.current = 540;
      try {
        localStorage.removeItem('compassx_file_viewer_width');
      } catch (_) {}
    } else {
      setTreeWidth(360);
      treeWidthRef.current = 360;
      try {
        localStorage.removeItem('compassx_file_tree_width');
        localStorage.removeItem('compassx_file_explorer_width');
      } catch (_) {}
    }
  };

  const toggleFileExplorer = () => {
    setShowFileExplorer((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('compassx_show_file_explorer', String(next));
      } catch (_) {}
      return next;
    });
  };

  const {
    data: devFiles = [],
    isLoading: isDevFilesLoading,
    refetch: refetchDevFiles,
  } = useDevFiles(resolvedAppId, activeWorkspace?.id || devStatus?.workspace_id, stage === 'running');

  // Preview URL for the running application sandbox
  const previewUrl = useMemo(() => {
    return (
      devStatus?.dev_url ||
      (devStatus?.dev_port ? `http://localhost:${devStatus.dev_port}` : '') ||
      (app?.slug ? `https://${app.slug}-dev.135.13.180.167.nip.io` : '') ||
      'http://localhost:9201'
    );
  }, [devStatus?.dev_url, devStatus?.dev_port, app?.slug]);

  // Auto-scroll logs to bottom as lines arrive
  useEffect(() => {
    if (isLogViewerOpen && autoScrollLogs && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [isLogViewerOpen, autoScrollLogs, installOutput, runAppOutput, devLogsData]);

  // Close 3-dot dropdown menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    }
    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isMenuOpen]);

  // Initial check on mount: If container was already running, skip startup wait
  useEffect(() => {
    if (!devStatus || isDevLoading) return;
    if (!initialChecked.current) {
      initialChecked.current = true;
      if (devStatus.status === 'active' || devStatus.phase === 'Running') {
        setHasCompletedInit(true);
        setStep2Completed(true);
        setStep3Completed(true);
        setStep4Completed(true);
        setInitStep(3);
      }
    } else if (!isContainerRunning && !isStoppingOperation) {
      setHasCompletedInit(false);
      setStep2Completed(false);
      setStep3Completed(false);
      setStep4Completed(false);
      setInitStep(0);
      setGitOutput('');
      setInstallOutput('');
      setRunAppOutput('');
      setIsLogViewerOpen(false);
      verifyGitTriggered.current = false;
      installDepsTriggered.current = false;
      runAppTriggered.current = false;
    }
  }, [devStatus, isDevLoading, isContainerRunning, isStoppingOperation]);

  // Track running container status
  useEffect(() => {
    if (devStatus && (devStatus.status === 'active' || devStatus.phase === 'Running')) {
      hasTriggeredInitialStart.current = true;
    }
  }, [devStatus]);

  // Clean & simple: start CompassX host by default on page load if not running and not explicitly stopped
  useEffect(() => {
    if (
      !isDevLoading &&
      !isContainerRunning &&
      !userExplicitlyStopped &&
      !hasTriggeredInitialStart.current &&
      resolvedAppId &&
      app &&
      !startDevMutation.isPending &&
      devStatus?.status !== 'provisioning'
    ) {
      hasTriggeredInitialStart.current = true;
      handleStartDev('compassx');
    }
  }, [isDevLoading, isContainerRunning, userExplicitlyStopped, resolvedAppId, app, devStatus, startDevMutation.isPending]);

  // ── Step 1 -> Step 2 -> Step 3 -> Step 4 -> Studio Canvas Progression ──────────────────
  useEffect(() => {
    if (!isContainerRunning || hasCompletedInit || startError) return;

    // Phase 1 -> 2: If container runtime is active and we are at Step 1, advance to Step 2
    if (initStep === 0) {
      setInitStep(1);
      return;
    }

    // Phase 2: Execute Git workspace verification
    if (initStep === 1 && !step2Completed && !verifyGitTriggered.current) {
      verifyGitTriggered.current = true;
      verifyGitMutation.mutate(
        { appId: resolvedAppId! },
        {
          onSuccess: (res) => {
            if (res.output) {
              setGitOutput(res.output);
            }
            if (res.success) {
              setStep2Completed(true);
              setInitStep(2);
            } else {
              setStartError(res.message || 'Workspace codebase preparation failed.');
              setIsLogViewerOpen(true);
            }
          },
          onError: (err: any) => {
            const msg = err?.response?.data?.detail || err?.message || 'Failed to verify workspace git codebase.';
            setStartError(msg);
            setIsLogViewerOpen(true);
          },
        }
      );
      return;
    }

    // Phase 3: Execute dependency installation
    if (initStep === 2 && step2Completed && !step3Completed && !installDepsTriggered.current) {
      installDepsTriggered.current = true;
      installDepsMutation.mutate(
        { appId: resolvedAppId! },
        {
          onSuccess: (res) => {
            if (res.output) {
              setInstallOutput(res.output);
            }
            if (res.success) {
              setStep3Completed(true);
              setInitStep(3);
            } else {
              setStartError(res.message || 'Dependency installation failed.');
              setIsLogViewerOpen(true);
            }
          },
          onError: (err: any) => {
            const msg = err?.response?.data?.detail || err?.message || 'Failed to install application dependencies.';
            setStartError(msg);
            setIsLogViewerOpen(true);
          },
        }
      );
      return;
    }

    // Phase 4: Execute Run Application
    if (initStep === 3 && step3Completed && !step4Completed && !runAppTriggered.current) {
      runAppTriggered.current = true;
      runAppMutation.mutate(
        { appId: resolvedAppId! },
        {
          onSuccess: (res) => {
            if (res.output) {
              setRunAppOutput(res.output);
            }
            if (res.success) {
              setStep4Completed(true);
              const t2 = setTimeout(() => {
                setHasCompletedInit(true);
              }, 700);
              return () => clearTimeout(t2);
            } else {
              setStartError(res.message || 'Starting application failed.');
              setIsLogViewerOpen(true);
            }
          },
          onError: (err: any) => {
            const msg = err?.response?.data?.detail || err?.message || 'Failed to start application.';
            setStartError(msg);
            setIsLogViewerOpen(true);
          },
        }
      );
    }
  }, [
    isContainerRunning,
    hasCompletedInit,
    startError,
    initStep,
    step2Completed,
    step3Completed,
    step4Completed,
    resolvedAppId,
    verifyGitMutation,
    installDepsMutation,
    runAppMutation,
  ]);

  // Reset errors and user stopped flag when container becomes active
  useEffect(() => {
    if (stage === 'running') {
      setStartError(null);
      setUserExplicitlyStopped(false);
    }
  }, [stage]);

  // Manual Start Dev Sandbox
  function handleStartDev(hostOverride?: 'compassx' | 'omnigent') {
    if (!resolvedAppId || !app) return;
    const hostToUse = hostOverride || selectedHost;
    setStartError(null);
    setUserExplicitlyStopped(false);
    setInitStep(0);
    setStep2Completed(false);
    setStep3Completed(false);
    setStep4Completed(false);
    setHasCompletedInit(false);
    setGitOutput('');
    setInstallOutput('');
    setRunAppOutput('');
    setIsLogViewerOpen(false);
    verifyGitTriggered.current = false;
    installDepsTriggered.current = false;
    runAppTriggered.current = false;
    hasTriggeredInitialStart.current = true;
    startDevMutation.mutate(
      { appId: resolvedAppId, hostType: hostToUse },
      {
        onError: (err: any) => {
          setStartError(err?.response?.data?.detail || err?.message || 'Failed to start dev sandbox.');
        },
      }
    );
  }

  // Retry Git Workspace Verification on Step 2
  function handleRetryGit() {
    setStartError(null);
    verifyGitTriggered.current = false;
    setInitStep(1);
    setStep2Completed(false);
  }

  // Retry Dependency Installation on Step 3
  function handleRetryInstall() {
    setStartError(null);
    installDepsTriggered.current = false;
    setInitStep(2);
    setStep3Completed(false);
  }

  // Retry Running Application on Step 4
  function handleRetryRunApp() {
    setStartError(null);
    runAppTriggered.current = false;
    setInitStep(3);
    setStep4Completed(false);
  }

  // Manual Stop Dev Sandbox
  async function handleStopDev() {
    setIsMenuOpen(false);
    if (!resolvedAppId || !app) return;
    if (!confirm(`Stop development sandbox for "${app.name}"?`)) return;
    try {
      setUserExplicitlyStopped(true);
      setStartError(null);
      setInitStep(0);
      setStep2Completed(false);
      setStep3Completed(false);
      setStep4Completed(false);
      setHasCompletedInit(false);
      setGitOutput('');
      setInstallOutput('');
      setRunAppOutput('');
      setIsLogViewerOpen(false);
      verifyGitTriggered.current = false;
      installDepsTriggered.current = false;
      runAppTriggered.current = false;
      toast.info(`Stopping dev sandbox for "${app.name}"...`);
      await stopDevMutation.mutateAsync(resolvedAppId);
      toast.success('Dev sandbox stopped.');
      refetchDevStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to stop dev sandbox.');
    }
  }

  // Initial loading screen while waiting for app or initial dev status query
  if (isAppLoading || (isDevLoading && !devStatus)) {
    return (
      <div
        className="app-build-page-root"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          width: '100%',
          flex: 1,
          background: 'var(--color-bg, #0f172a)',
          color: 'var(--color-text, #f8fafc)',
          gap: 12,
        }}
      >
        <Loader2 size={28} className="spin" color="var(--color-primary, #38bdf8)" />
        <span style={{ fontSize: '0.9rem', color: 'var(--color-text-muted, #94a3b8)' }}>Connecting to Build Studio...</span>
      </div>
    );
  }

  return (
    <div
      className="app-build-page-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        flex: 1,
        minHeight: 0,
        position: 'relative',
        background: 'var(--color-bg, #0f172a)',
        color: 'var(--color-text, #f8fafc)',
        overflow: 'hidden',
      }}
    >
      <style>{`
        @keyframes capsulePulse {
          0% {
            background-position: 0% 50%;
            box-shadow: 0 0 6px rgba(34, 197, 94, 0.3);
          }
          50% {
            background-position: 100% 50%;
            box-shadow: 0 0 14px rgba(34, 197, 94, 0.7);
          }
          100% {
            background-position: 0% 50%;
            box-shadow: 0 0 6px rgba(34, 197, 94, 0.3);
          }
        }
        .step-capsule-active {
          background: linear-gradient(90deg, #16a34a, #4ade80, #22c55e, #16a34a);
          background-size: 250% 250%;
          animation: capsulePulse 1.8s ease-in-out infinite;
        }
        .step-capsule-complete {
          background: #22c55e;
          box-shadow: 0 0 8px rgba(34, 197, 94, 0.45);
        }
        .step-capsule-error {
          background: #ef4444;
          box-shadow: 0 0 8px rgba(239, 68, 68, 0.45);
        }
        .step-capsule-pending {
          background: #cbd5e1;
        }
        [data-theme="dark"] .step-capsule-pending,
        .dark .step-capsule-pending {
          background: #475569;
        }
      `}</style>

      {/* Top Header Bar */}
      <header
        style={{
          height: 52,
          padding: '0 20px',
          background: 'var(--color-surface, #1e293b)',
          borderBottom: '1px solid var(--color-border, #334155)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          zIndex: 10,
        }}
      >
        {/* Left: Breadcrumbs & Header Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <nav aria-label="Breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              type="button"
              onClick={() => navigate('/apps')}
              title="Back to Apps"
              style={{
                background: 'none',
                border: 'none',
                padding: '2px 4px',
                borderRadius: 4,
                cursor: 'pointer',
                color: 'var(--color-text-muted, #94a3b8)',
                fontSize: '0.84rem',
                fontWeight: 500,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#f8fafc';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text-muted, #94a3b8)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              Apps
            </button>

            <span style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.8rem', userSelect: 'none' }}>/</span>

            <button
              type="button"
              onClick={() => navigate(`/apps/${resolvedAppId}`)}
              title="Back to App Details"
              style={{
                background: 'none',
                border: 'none',
                padding: '2px 4px',
                borderRadius: 4,
                cursor: 'pointer',
                color: 'var(--color-text, #f8fafc)',
                fontSize: '0.92rem',
                fontWeight: 600,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#1B6EF3';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text, #f8fafc)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              {app?.name || 'App'}
            </button>
          </nav>

            {/* Host name in muted font */}
            {(stage === 'running' || stage === 'starting') && (
              <span
                style={{
                  fontSize: '0.78rem',
                  color: 'var(--color-text-muted, #94a3b8)',
                  marginLeft: 2,
                }}
                title={devStatus?.host_image || 'compassx-host:latest'}
              >
                CompassX Host
              </span>
            )}

            {/* Sandbox (Git Worktree) Selector Dropdown */}
            {(stage === 'running' || stage === 'starting') && (
              <SandboxSelector
                appId={resolvedAppId!}
                workspaces={devWorkspaces}
                activeWorkspaceId={activeWorkspace?.id}
                onSelectWorkspace={handleSelectWorkspace}
                onOpenNewSandboxModal={() => setIsNewSandboxModalOpen(true)}
                isSwitching={isSwitchingSandbox}
                disabled={!isContainerRunning}
              />
            )}
          </div>

        {/* Right: Preview Link, Files Toggle Button & Three Dots Action Menu */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {stage === 'running' && (
            <>
              {/* Preview Link */}
              <a
                href={previewUrl}
                target="_blank"
                rel="noopener noreferrer"
                title={`Open App Preview (${previewUrl})`}
                aria-label="Open App Preview"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '4px 10px',
                  borderRadius: 6,
                  fontSize: '0.76rem',
                  fontWeight: 600,
                  color: '#1B6EF3',
                  background: 'rgba(27, 110, 243, 0.08)',
                  border: '1px solid rgba(27, 110, 243, 0.22)',
                  textDecoration: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: '0 1px 2px rgba(0, 0, 0, 0.04)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(27, 110, 243, 0.16)';
                  e.currentTarget.style.borderColor = 'rgba(27, 110, 243, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(27, 110, 243, 0.08)';
                  e.currentTarget.style.borderColor = 'rgba(27, 110, 243, 0.22)';
                }}
              >
                <ExternalLink size={13} />
                <span>Preview</span>
              </a>

              {/* Files Toggle Button */}
              <button
                type="button"
                onClick={toggleFileExplorer}
                title={showFileExplorer ? 'Hide File Explorer' : 'Show File Explorer'}
                aria-label="Toggle Files Explorer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: showFileExplorer ? '#f1f5f9' : 'transparent',
                  border: showFileExplorer ? '1px solid #e2e8f0' : '1px solid transparent',
                  borderRadius: 6,
                  padding: 5,
                  color: showFileExplorer ? '#0f172a' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!showFileExplorer) {
                    e.currentTarget.style.background = '#f8fafc';
                    e.currentTarget.style.color = '#0f172a';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!showFileExplorer) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = '#64748b';
                  }
                }}
              >
                <FolderTree size={15} />
              </button>
            </>
          )}

          <div ref={menuRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setIsMenuOpen((prev) => !prev)}
            title="More options"
            aria-label="More options"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: isMenuOpen ? '#f1f5f9' : 'transparent',
              border: isMenuOpen ? '1px solid #e2e8f0' : '1px solid transparent',
              borderRadius: 6,
              padding: 5,
              color: isMenuOpen ? '#0f172a' : '#64748b',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (!isMenuOpen) {
                e.currentTarget.style.background = '#f8fafc';
                e.currentTarget.style.color = '#0f172a';
              }
            }}
            onMouseLeave={(e) => {
              if (!isMenuOpen) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = '#64748b';
              }
            }}
          >
            <MoreVertical size={17} />
          </button>

          {isMenuOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                right: 0,
                width: 200,
                background: '#ffffff',
                border: '1px solid #e5e7eb',
                borderRadius: 8,
                boxShadow: '0 4px 16px -2px rgba(0, 0, 0, 0.08), 0 2px 6px -1px rgba(0, 0, 0, 0.04)',
                padding: 4,
                zIndex: 50,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                animation: 'fadeIn 0.12s ease-out',
              }}
            >
              {stage === 'running' && (
                <a
                  href={previewUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => setIsMenuOpen(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '7px 10px',
                    background: 'transparent',
                    border: 'none',
                    borderRadius: 6,
                    color: '#1B6EF3',
                    fontSize: '0.78rem',
                    fontWeight: 500,
                    textDecoration: 'none',
                    textAlign: 'left',
                    transition: 'background 0.12s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(27, 110, 243, 0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <ExternalLink size={13} />
                  <span>Open Live Preview</span>
                </a>
              )}
              <button
                onClick={handleStopDev}
                disabled={isStoppingOperation || (stage === 'stopped' && !isContainerRunning)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '7px 10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: 6,
                  color: isStoppingOperation || (stage === 'stopped' && !isContainerRunning)
                    ? '#9ca3af'
                    : '#dc2626',
                  fontSize: '0.78rem',
                  fontWeight: 500,
                  cursor: isStoppingOperation || (stage === 'stopped' && !isContainerRunning)
                    ? 'not-allowed'
                    : 'pointer',
                  opacity: isStoppingOperation || (stage === 'stopped' && !isContainerRunning)
                    ? 0.5
                    : 1,
                  textAlign: 'left',
                  transition: 'background 0.12s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isStoppingOperation && !(stage === 'stopped' && !isContainerRunning)) {
                    e.currentTarget.style.background = '#fef2f2';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                {isStoppingOperation ? (
                  <Loader2 size={13} className="spin" />
                ) : (
                  <Square size={13} />
                )}
                <span>{isStoppingOperation ? 'Stopping Sandbox...' : 'Stop Dev Sandbox'}</span>
              </button>
            </div>
          )}
        </div>
      </div>
      </header>

      {/* Main Page Area */}
      <main
        style={{
          flex: 1,
          width: '100%',
          minHeight: 0,
          background: 'var(--color-bg, #0f172a)',
          position: 'relative',
          overflow: stage === 'running' ? 'hidden' : 'auto',
          padding: stage === 'running' ? '10px 14px' : '24px 32px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {stage === 'running' ? (
          /* Stage: Running -> Split Layout (Sessions Sidebar on Left, DevTerminal in Middle, File Explorer on Right) */
          <div
            style={{
              flex: 1,
              height: '100%',
              minHeight: 0,
              display: 'flex',
              gap: 0,
              borderRadius: 8,
              overflow: 'hidden',
              animation: 'fadeIn 0.3s ease-in-out',
            }}
          >
            {/* Left Column: Sessions Secondary Sidebar */}
            {showSessionsSidebar ? (
              <>
                <aside
                  style={{
                    width: `${sessionsSidebarWidth}px`,
                    minWidth: 200,
                    maxWidth: 450,
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    flexShrink: 0,
                    borderRadius: '8px 0 0 8px',
                    overflow: 'hidden',
                    border: '1px solid #e2e8f0',
                    background: '#ffffff',
                    transition: isSessionsResizing ? 'none' : 'width 0.15s ease',
                    boxShadow: '0 4px 20px -2px rgba(0, 0, 0, 0.08)',
                  }}
                >
                  <SessionsSidebar
                    sessions={allSessions}
                    activeSessionId={activeSession?.id || activeSessionId}
                    onSelectSession={handleSelectSession}
                    onOpenNewSession={() => setIsNewSessionModalOpen(true)}
                    onOpenNewShell={handleCreateShellSession}
                    onDeleteSession={handleDeleteSession}
                    disabled={!isContainerRunning}
                    isSwitching={isSwitchingSession}
                    isMaximized={isSessionsMaximized}
                    onToggleMaximized={toggleSessionsMaximized}
                    onClose={() =>
                      setShowSessionsSidebar(() => {
                        try {
                          localStorage.setItem('compassx_show_sessions_sidebar', 'false');
                        } catch (_) {}
                        return false;
                      })
                    }
                  />
                </aside>

                {/* Draggable Divider Handle between Sessions Sidebar & Terminal */}
                <div
                  role="separator"
                  aria-orientation="vertical"
                  title="Drag to resize sessions sidebar • Double-click to reset"
                  onMouseDown={handleSessionsResizeMouseDown}
                  onDoubleClick={handleResetSessionsWidth}
                  style={{
                    width: 10,
                    flexShrink: 0,
                    cursor: 'col-resize',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    zIndex: 20,
                    userSelect: 'none',
                  }}
                  className="group"
                >
                  <div
                    style={{
                      width: 3,
                      height: 36,
                      borderRadius: 9999,
                      backgroundColor: isSessionsResizing ? '#1B6EF3' : '#cbd5e1',
                      transition: 'background-color 0.15s ease, height 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#1B6EF3';
                      e.currentTarget.style.height = '48px';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = isSessionsResizing ? '#1B6EF3' : '#cbd5e1';
                      e.currentTarget.style.height = '36px';
                    }}
                  />
                </div>
              </>
            ) : (
              /* Collapsed Secondary Sidebar: slim rail with small expand button */
              <div
                style={{
                  width: 34,
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  paddingTop: 8,
                  gap: 8,
                  flexShrink: 0,
                  borderRadius: '8px 0 0 8px',
                  border: '1px solid #e2e8f0',
                  background: '#ffffff',
                  zIndex: 10,
                }}
              >
                <button
                  type="button"
                  onClick={() =>
                    setShowSessionsSidebar(() => {
                      try {
                        localStorage.setItem('compassx_show_sessions_sidebar', 'true');
                      } catch (_) {}
                      return true;
                    })
                  }
                  title="Expand Sessions Sidebar"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 24,
                    height: 24,
                    borderRadius: 5,
                    border: '1px solid #e2e8f0',
                    background: '#f8fafc',
                    color: '#64748b',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = '#0f172a';
                    e.currentTarget.style.background = '#f1f5f9';
                    e.currentTarget.style.borderColor = '#cbd5e1';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = '#64748b';
                    e.currentTarget.style.background = '#f8fafc';
                    e.currentTarget.style.borderColor = '#e2e8f0';
                  }}
                >
                  <PanelLeftOpen size={13} />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setShowSessionsSidebar(() => {
                      try {
                        localStorage.setItem('compassx_show_sessions_sidebar', 'true');
                      } catch (_) {}
                      return true;
                    })
                  }
                  title={`${allSessions.length} active sessions (Click to expand)`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'transparent',
                    border: 'none',
                    color: '#94a3b8',
                    cursor: 'pointer',
                    padding: 4,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = '#1B6EF3';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = '#94a3b8';
                  }}
                >
                  <Layers size={13} />
                </button>
              </div>
            )}

            {/* Middle/Main Column: DevTerminal */}
            <div
              style={{
                flex: 1,
                minWidth: 0,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                borderRadius: showSessionsSidebar ? 0 : 8,
                overflow: 'hidden',
              }}
            >
              <DevTerminal
                appId={resolvedAppId!}
                appName={app?.name || 'app'}
                workspaceId={activeWorkspace?.id || devStatus?.workspace_id}
                workspaceName={activeWorkspace?.name || devStatus?.workspace_name}
                isDevPodRunning={isContainerRunning}
                agent={currentAgent}
                sessionId={activeSession?.id}
                sessionTitle={activeSession?.title}
                isSwitchingSession={isSwitchingSession || isSwitchingSandbox}
                onSessionReady={() => setIsSwitchingSession(false)}
                fullHeight={true}
              />
            </div>

            {/* Draggable Divider Handle between Terminal & Explorer */}
            {showFileExplorer && (
              <div
                role="separator"
                aria-orientation="vertical"
                title="Drag to resize sidebar • Double-click to reset"
                onMouseDown={handleResizeMouseDown}
                onDoubleClick={handleResetWidth}
                style={{
                  width: 10,
                  flexShrink: 0,
                  cursor: 'col-resize',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                  zIndex: 20,
                  userSelect: 'none',
                }}
                className="group"
              >
                {/* Visual grab pill */}
                <div
                  style={{
                    width: 3,
                    height: 36,
                    borderRadius: 9999,
                    backgroundColor: isExplorerResizing ? '#3b82f6' : '#cbd5e1',
                    transition: 'background-color 0.15s ease, height 0.15s ease',
                  }}
                  className="group-hover:bg-blue-500 group-hover:h-12"
                />
              </div>
            )}

            {/* Right Column: File Explorer Sidepanel */}
            {showFileExplorer && (
              <aside
                ref={asideRef}
                style={{
                  width: isExplorerMaximized ? '62vw' : (selectedFilePath ? `${viewerWidth}px` : `${treeWidth}px`),
                  maxWidth: isExplorerMaximized ? '85vw' : '75vw',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  borderRadius: 8,
                  overflow: 'hidden',
                  border: '1px solid #e2e8f0',
                  background: '#ffffff',
                  boxShadow: '0 4px 20px -2px rgba(0, 0, 0, 0.08)',
                  transition: isExplorerResizing ? 'none' : 'width 0.15s ease',
                  flexShrink: 0,
                }}
              >
                <FileExplorerSidepanel
                  appId={resolvedAppId!}
                  appName={app?.slug || app?.name || 'app'}
                  workspaceId={activeWorkspace?.id || devStatus?.workspace_id}
                  workspaceName={activeWorkspace?.name || devStatus?.workspace_name}
                  files={devFiles}
                  isLoading={isDevFilesLoading}
                  onRefresh={() => refetchDevFiles()}
                  selectedFilePath={selectedFilePath}
                  onSelectFilePath={setSelectedFilePath}
                  onClose={toggleFileExplorer}
                  isMaximized={isExplorerMaximized}
                  onToggleMaximized={() => setIsExplorerMaximized((prev) => !prev)}
                />
              </aside>
            )}
          </div>
        ) : stage === 'stopping' ? (
          /* Stage: Stopping View */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 20px',
              maxWidth: 480,
              margin: '0 auto',
              width: '100%',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: 16,
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f87171',
                marginBottom: 20,
              }}
            >
              <Loader2 size={28} className="spin" />
            </div>
            <h2 style={{ margin: '0 0 6px', fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-text, #f8fafc)' }}>
              Stopping Dev Sandbox...
            </h2>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-muted, #94a3b8)' }}>
              Gracefully tearing down container environment and freeing ports.
            </p>
          </div>
        ) : stage === 'stopped' ? (
          /* Stage: Sandbox Stopped View */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 20px',
              maxWidth: 480,
              margin: '0 auto',
              width: '100%',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: 16,
                background: 'rgba(27, 110, 243, 0.08)',
                border: '1px solid rgba(27, 110, 243, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#1B6EF3',
                marginBottom: 20,
                boxShadow: '0 8px 24px rgba(27, 110, 243, 0.1)',
              }}
            >
              <Server size={28} />
            </div>

            <h2 style={{ margin: '0 0 8px', fontSize: '1.35rem', fontWeight: 700, color: '#0f172a' }}>
              Development Sandbox Stopped
            </h2>
            <p style={{ margin: '0 0 24px', fontSize: '0.88rem', color: '#64748b', lineHeight: 1.5, maxWidth: 420 }}>
              Start the CompassX dev sandbox to open the Build Studio canvas and launch agent coding sessions.
            </p>

            {startError && (
              <div
                style={{
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: 8,
                  padding: '10px 14px',
                  fontSize: '0.8rem',
                  color: '#b91c1c',
                  marginBottom: 20,
                  width: '100%',
                  textAlign: 'left',
                }}
              >
                {startError}
              </div>
            )}

            <button
              onClick={() => handleStartDev('compassx')}
              disabled={startDevMutation.isPending}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                background: '#1B6EF3',
                border: 'none',
                borderRadius: 8,
                color: '#ffffff',
                padding: '11px 28px',
                fontSize: '0.92rem',
                fontWeight: 600,
                cursor: startDevMutation.isPending ? 'not-allowed' : 'pointer',
                opacity: startDevMutation.isPending ? 0.6 : 1,
                boxShadow: '0 4px 14px rgba(27, 110, 243, 0.35)',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!startDevMutation.isPending) {
                  e.currentTarget.style.background = '#1558c7';
                  e.currentTarget.style.boxShadow = '0 6px 18px rgba(27, 110, 243, 0.45)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#1B6EF3';
                e.currentTarget.style.boxShadow = '0 4px 14px rgba(27, 110, 243, 0.35)';
              }}
            >
              {startDevMutation.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Starting Sandbox...</span>
                </>
              ) : (
                <>
                  <Play size={16} fill="currentColor" />
                  <span>Start Dev Sandbox</span>
                </>
              )}
            </button>
          </div>
        ) : (
          /* Stage: Starting / Initializing View with Segmented Progress Bar */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 20px',
              maxWidth: 520,
              margin: '0 auto',
              width: '100%',
              textAlign: 'center',
            }}
          >
            {/* Icon Graphic */}
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%)',
                border: '1px solid rgba(129, 140, 248, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8',
                marginBottom: 20,
                boxShadow: '0 8px 24px rgba(99, 102, 241, 0.2)',
              }}
            >
              {startError ? (
                <AlertCircle size={32} color="#f87171" />
              ) : (
                <Server size={30} style={{ animation: 'spin 12s linear infinite' }} />
              )}
            </div>

            {/* Title & Subtitle */}
            <h2 style={{ margin: '0 0 6px', fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text, #f8fafc)' }}>
              {startError ? 'Sandbox Startup Failed' : 'Preparing Build Environment'}
            </h2>
            <p style={{ margin: '0 0 24px', fontSize: '0.85rem', color: 'var(--color-text-muted, #94a3b8)' }}>
              {startError
                ? 'An error occurred during sandbox initialization.'
                : step4Completed
                ? 'Step 4 of 4 • Application Running'
                : `Step ${initStep + 1} of ${BUILD_STEPS.length} • ${BUILD_STEPS[initStep].title}`}
            </p>

            {/* Segmented Pill Progress Bar */}
            <div
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 20,
                padding: '4px 0',
              }}
            >
              {BUILD_STEPS.map((step, idx) => {
                let capsuleClass = 'step-capsule-pending';
                if (!startError) {
                  if (
                    idx < initStep ||
                    (idx === 1 && step2Completed) ||
                    (idx === 2 && step3Completed) ||
                    (idx === 3 && step4Completed) ||
                    hasCompletedInit
                  ) {
                    capsuleClass = 'step-capsule-complete';
                  } else if (idx === initStep) {
                    capsuleClass = 'step-capsule-active';
                  }
                } else {
                  if (idx < initStep) {
                    capsuleClass = 'step-capsule-complete';
                  } else if (idx === initStep) {
                    capsuleClass = 'step-capsule-error';
                  }
                }

                return (
                  <div
                    key={step.id}
                    className={capsuleClass}
                    style={{
                      flex: 1,
                      height: 7,
                      borderRadius: 9999,
                      transition: 'all 0.3s ease',
                    }}
                    title={`${step.title} (${
                      idx < initStep ||
                      (idx === 1 && step2Completed) ||
                      (idx === 2 && step3Completed) ||
                      (idx === 3 && step4Completed) ||
                      hasCompletedInit
                        ? 'Complete'
                        : idx === initStep
                        ? startError
                          ? 'Failed'
                          : 'In Progress'
                        : 'Pending'
                    })`}
                  />
                );
              })}
            </div>

            {/* Step Description / Status Details */}
            {!startError ? (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: '0.82rem',
                  color: 'var(--color-text-muted, #94a3b8)',
                }}
              >
                {step4Completed ? (
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
                ) : (
                  <Loader2 size={14} className="spin" color="#38bdf8" />
                )}
                <span>
                  {step4Completed
                    ? 'Application services running and dev server responsive.'
                    : BUILD_STEPS[initStep].description}
                </span>
              </div>
            ) : null}

            {/* On-Demand Logs Section */}
            {(initStep >= 1 || startError || isLogViewerOpen) && (
              <div style={{ marginTop: 16, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => setIsLogViewerOpen((prev) => !prev)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    background: isLogViewerOpen ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--color-border, #334155)',
                    borderRadius: 6,
                    color: 'var(--color-text, #cbd5e1)',
                    padding: '5px 12px',
                    fontSize: '0.78rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <Terminal size={13} color="#38bdf8" />
                  <span>
                    {isLogViewerOpen
                      ? 'Hide Initialization Logs'
                      : initStep === 1
                      ? 'View Preparation Logs'
                      : initStep === 2
                      ? 'View Installation Logs'
                      : 'View Application Logs'}
                  </span>
                  {isLogViewerOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                </button>

                {isLogViewerOpen && (
                  <div
                    style={{
                      marginTop: 12,
                      width: '100%',
                      background: '#090d16',
                      border: '1px solid #1e293b',
                      borderRadius: 8,
                      display: 'flex',
                      flexDirection: 'column',
                      overflow: 'hidden',
                      textAlign: 'left',
                      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
                    }}
                  >
                    {/* Log Console Header Bar */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 12px',
                        background: '#0f172a',
                        borderBottom: '1px solid #1e293b',
                        fontSize: '0.72rem',
                        color: '#94a3b8',
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: startError
                              ? '#ef4444'
                              : verifyGitMutation.isPending || installDepsMutation.isPending || runAppMutation.isPending
                              ? '#38bdf8'
                              : '#22c55e',
                          }}
                        />
                        <span>
                          {initStep === 1
                            ? 'Git Workspace Preparation Console'
                            : initStep === 2
                            ? 'Dependency Installation Console'
                            : 'Application Runtime Console'}
                        </span>
                      </span>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <button
                          type="button"
                          onClick={() => setAutoScrollLogs((prev) => !prev)}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: autoScrollLogs ? '#38bdf8' : '#64748b',
                            fontSize: '0.7rem',
                            cursor: 'pointer',
                            fontWeight: 500,
                          }}
                        >
                          Auto-scroll: {autoScrollLogs ? 'ON' : 'OFF'}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            const raw =
                              [gitOutput, installOutput, runAppOutput].filter(Boolean).join('\n\n') ||
                              (Array.isArray(devLogsData) ? devLogsData.join('\n') : String(devLogsData || ''));
                            navigator.clipboard.writeText(raw);
                            toast.success('Logs copied to clipboard');
                          }}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#cbd5e1',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: '0.7rem',
                          }}
                          title="Copy logs"
                        >
                          <Copy size={11} />
                          <span>Copy</span>
                        </button>
                      </div>
                    </div>

                    {/* Console Output Body */}
                    <div
                      ref={logsContainerRef}
                      style={{
                        height: 160,
                        maxHeight: 180,
                        padding: '10px 12px',
                        overflowY: 'auto',
                        fontSize: '0.73rem',
                        fontFamily:
                          'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                        color: startError ? '#fca5a5' : '#cbd5e1',
                        lineHeight: 1.55,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                      }}
                    >
                      {(() => {
                        if (initStep === 1) {
                          return gitOutput || 'Verifying git repository, branch, and working tree...';
                        }
                        if (initStep === 2) {
                          if (gitOutput && installOutput) {
                            return `${gitOutput}\n\n${installOutput}`;
                          }
                          return installOutput || gitOutput || 'Checking dependency manifests and running package installer inside sandbox...';
                        }
                        if (initStep === 3) {
                          const parts = [gitOutput, installOutput, runAppOutput].filter(Boolean);
                          if (parts.length > 0) {
                            return parts.join('\n\n');
                          }
                          return runAppOutput || 'Starting application processes and verifying dev server...';
                        }
                        const parts = [gitOutput, installOutput, runAppOutput].filter(Boolean);
                        if (parts.length > 0) {
                          return parts.join('\n\n');
                        }
                        return (
                          (Array.isArray(devLogsData) && devLogsData.length > 0 ? devLogsData.join('\n') : '') ||
                          (typeof devLogsData === 'string' && devLogsData ? devLogsData : '') ||
                          'Initializing dev environment...'
                        );
                      })()}
                    </div>
                  </div>
                )}
              </div>
            )}

            {startError && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 12,
                  width: '100%',
                  marginTop: 16,
                }}
              >
                <div
                  style={{
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    borderRadius: 8,
                    padding: '10px 14px',
                    fontSize: '0.8rem',
                    color: '#fca5a5',
                    maxWidth: 440,
                    wordBreak: 'break-word',
                  }}
                >
                  {startError}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {initStep === 1 && (
                    <button
                      type="button"
                      onClick={handleRetryGit}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                        border: 'none',
                        borderRadius: 6,
                        color: '#ffffff',
                        padding: '8px 18px',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        boxShadow: '0 2px 8px rgba(16, 185, 129, 0.3)',
                      }}
                    >
                      <RefreshCw size={14} />
                      <span>Retry Code Preparation</span>
                    </button>
                  )}
                  {initStep === 2 && (
                    <button
                      type="button"
                      onClick={handleRetryInstall}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                        border: 'none',
                        borderRadius: 6,
                        color: '#ffffff',
                        padding: '8px 18px',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        boxShadow: '0 2px 8px rgba(16, 185, 129, 0.3)',
                      }}
                    >
                      <RefreshCw size={14} />
                      <span>Retry Installing Libs</span>
                    </button>
                  )}
                  {initStep === 3 && (
                    <button
                      type="button"
                      onClick={handleRetryRunApp}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                        border: 'none',
                        borderRadius: 6,
                        color: '#ffffff',
                        padding: '8px 18px',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        boxShadow: '0 2px 8px rgba(16, 185, 129, 0.3)',
                      }}
                    >
                      <RefreshCw size={14} />
                      <span>Retry Running App</span>
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => handleStartDev()}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                      border: 'none',
                      borderRadius: 6,
                      color: '#ffffff',
                      padding: '8px 18px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      boxShadow: '0 2px 8px rgba(37, 99, 235, 0.3)',
                    }}
                  >
                    <RefreshCw size={14} />
                    <span>Restart Sandbox</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Transparent overlay during sidebar resize to lock cursor and prevent iframe/xterm event loss */}
        {isExplorerResizing && (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 99999,
              cursor: 'col-resize',
              userSelect: 'none',
              backgroundColor: 'transparent',
            }}
          />
        )}
      </main>

      {/* New Session Modal */}
      <NewSessionModal
        isOpen={isNewSessionModalOpen}
        onClose={() => setIsNewSessionModalOpen(false)}
        onSubmit={handleCreateSession}
        appId={resolvedAppId}
        isCreating={createDevSessionMutation.isPending}
      />

      {/* New Sandbox (Git Worktree) Modal */}
      <NewSandboxModal
        isOpen={isNewSandboxModalOpen}
        onClose={() => setIsNewSandboxModalOpen(false)}
        appId={resolvedAppId!}
        appName={app?.name}
        onCreated={() => {
          refetchDevWorkspaces();
          refetchDevStatus();
        }}
      />
    </div>
  );
}
