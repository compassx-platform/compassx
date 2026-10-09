import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
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
  ChevronLeft,
  Copy,
  FolderTree,
  Layers,
  ExternalLink,
  Plus,
  Sparkles,
  History,
  SquarePen,
  Bot,
  Check,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { useQueryClient } from '@tanstack/react-query';
import {
  useApp,
  useDevStatus,
  useStartDevSession,
  useRestartDevSandbox,
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
  useDeployApp,
  useAppDeployments,
  useEnsureAppSandbox,
  useAppSandboxStatus,
  type DevSession,
  type DevWorkspace,
} from '../hooks/useApps';

import { DevTerminal } from '../components/DevTerminal';
import { OmnigentChatPanel } from '../components/build/OmnigentChatPanel';
import { SessionHistoryPopover } from '../components/build/SessionHistoryPopover';
import { CompassXLogo } from '@/components/common/CompassXLogo';
import { useNewShellHotkey } from '../hooks/useNewShellHotkey';
import { NewSessionModal } from '../components/NewSessionModal';
import { SandboxSelector } from '../components/SandboxSelector';
import { NewSandboxModal } from '../components/NewSandboxModal';
import { FileExplorerSidepanel } from '../components/files/FileExplorerSidepanel';
import { FilesPanel } from '../components/files/FilesPanel';
import { FileViewer } from '../components/files/FileViewer';
import { BrowserToolbar, type CanvasViewMode } from '../components/build/BrowserToolbar';
import { LivePreviewCanvas } from '../components/build/LivePreviewCanvas';
import { CodeEditorCanvas } from '../components/build/CodeEditorCanvas';
import { OutputDrawer } from '../components/build/OutputDrawer';

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

export type SupportedAgent = 'pi' | 'opencode' | 'antigravity';

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
  const ensureAppSandboxMutation = useEnsureAppSandbox();
  const { data: sandboxStatus, refetch: refetchSandboxStatus } = useAppSandboxStatus(resolvedAppId, true);
  const qc = useQueryClient();
  const startDevMutation = useStartDevSession();
  const restartDevMutation = useRestartDevSandbox();
  const stopDevMutation = useStopDevSession();
  const verifyGitMutation = useVerifyGitWorkspace();
  const installDepsMutation = useInstallDevDependencies();
  const runAppMutation = useRunDevApp();
  const { data: devWorkspaces = [], refetch: refetchDevWorkspaces } = useDevWorkspaces(resolvedAppId);
  const activateWorkspaceMutation = useActivateDevWorkspace();
  const [selectedWsId, setSelectedWsId] = useState<string | null>(null);
  const [isNewSandboxModalOpen, setIsNewSandboxModalOpen] = useState<boolean>(false);
  const [isSwitchingSandbox, setIsSwitchingSandbox] = useState<boolean>(false);

  // Current active sandbox/workspace
  const activeWorkspace = useMemo(() => {
    if (selectedWsId) {
      const found = devWorkspaces.find((w) => w.id === selectedWsId || w.name === selectedWsId);
      if (found) return found;
    }
    return (
      devWorkspaces.find((w) => w.id === devStatus?.workspace_id || w.name === devStatus?.workspace_name) ||
      devWorkspaces.find((w) => w.status === 'active') ||
      devWorkspaces[0]
    );
  }, [selectedWsId, devWorkspaces, devStatus?.workspace_id, devStatus?.workspace_name]);

  const handleSelectWorkspace = async (workspaceId: string) => {
    if (!resolvedAppId || workspaceId === activeWorkspace?.id) return;
    try {
      setSelectedWsId(workspaceId);
      setIsSwitchingSandbox(true);
      await activateWorkspaceMutation.mutateAsync({
        appId: resolvedAppId,
        workspaceId,
      });
      toast.success('Switched active sandbox.');
      setPreviewReloadKey(Date.now());
      qc.invalidateQueries({ queryKey: ['app-dev-files', resolvedAppId] });
      qc.invalidateQueries({ queryKey: ['app-dev-status', resolvedAppId] });
      qc.invalidateQueries({ queryKey: ['app-dev-workspaces', resolvedAppId] });
      refetchDevStatus();
      refetchDevWorkspaces();
      refetchDevFiles();
      refetchDevLogs();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to switch sandbox');
    } finally {
      setIsSwitchingSandbox(false);
    }
  };

  const [startError, setStartError] = useState<string | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
  const [leftPanelMode, setLeftPanelMode] = useState<'chat' | 'cli' | 'split'>('chat');
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
  const isContainerRunning =
    (sandboxStatus?.status === 'ready' || sandboxStatus?.status === 'running' || devStatus?.status === 'active' || devStatus?.phase === 'Running') &&
    devStatus?.status !== 'provisioning' &&
    devStatus?.phase !== 'Pending' &&
    devStatus?.phase !== 'ContainerCreating' &&
    devStatus?.phase !== 'Terminating' &&
    !devStatus?.is_scaling_node &&
    sandboxStatus?.status !== 'failed';

  const isStoppingOperation =
    stopDevMutation.isPending ||
    devStatus?.status === 'stopping' ||
    devStatus?.phase === 'Terminating';

  let stage: SandboxStage;
  if (isStoppingOperation) {
    stage = 'stopping';
  } else if (userExplicitlyStopped) {
    stage = 'stopped';
  } else if (isContainerRunning) {
    stage = 'running';
  } else if (
    ensureAppSandboxMutation.isPending ||
    startDevMutation.isPending ||
    restartDevMutation.isPending ||
    devStatus?.status === 'provisioning' ||
    devStatus?.is_scaling_node ||
    sandboxStatus?.status === 'provisioning' ||
    sandboxStatus?.status === 'initializing'
  ) {
    stage = 'starting';
  } else {
    stage = 'stopped';
  }


  // Live container logs query (active when log viewer is open, starting/running, or initializing)
  const {
    data: devLogsData,
    refetch: refetchDevLogs,
    isLoading: isDevLogsLoading,
  } = useDevLogs(resolvedAppId, stage === 'running' || stage === 'starting' || isLogViewerOpen || initStep >= 1 || !hasCompletedInit);

  // ── Deployment State & Handler ───────────────────────────────────────────────
  const deployMutation = useDeployApp();
  const { data: appDeployments = [] } = useAppDeployments(resolvedAppId, stage === 'running');
  const latestDeployment = appDeployments?.[0];

  const handleDeployApp = async () => {
    if (!resolvedAppId) return;
    try {
      toast.info('Starting deployment to cluster...');
      await deployMutation.mutateAsync(resolvedAppId);
      toast.success('Deployment initiated successfully!');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Deployment failed');
    }
  };

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

  // Hotkey opens the bottom terminal drawer
  const handleOpenBottomTerminal = () => {
    setIsOutputCollapsed(false);
  };

  useNewShellHotkey(handleOpenBottomTerminal, isContainerRunning);

  // ── Session History Popover & More Menu State ──────────────────────────────
  const [isHistoryPopoverOpen, setIsHistoryPopoverOpen] = useState<boolean>(false);
  const [isMoreMenuOpen, setIsMoreMenuOpen] = useState<boolean>(false);

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

  // ── Studio 2-Column Split & Output Drawer State ────────────────────────────────
  const [canvasViewMode, setCanvasViewMode] = useState<CanvasViewMode>('preview');
  const [previewRoute, setPreviewRoute] = useState<string>('/');
  const [previewReloadKey, setPreviewReloadKey] = useState<number>(0);
  const [isCanvasMaximized, setIsCanvasMaximized] = useState<boolean>(false);
  const [isOutputCollapsed, setIsOutputCollapsed] = useState<boolean>(true);

  const [outputHeight, setOutputHeight] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('compassx_build_output_height');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (Number.isFinite(parsed) && parsed >= 120 && parsed <= 600) return parsed;
      }
    } catch (_) {}
    return 220;
  });

  const [studioSplitRatio, setStudioSplitRatio] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('compassx_build_split_ratio');
      if (saved) {
        const parsed = parseFloat(saved);
        if (Number.isFinite(parsed) && parsed >= 25 && parsed <= 75) return parsed;
      }
    } catch (_) {}
    return 42;
  });

  const [isStudioResizing, setIsStudioResizing] = useState<boolean>(false);
  const [isStudioSplitterHovered, setIsStudioSplitterHovered] = useState<boolean>(false);
  const isStudioResizingRef = useRef<boolean>(false);
  const studioContainerRef = useRef<HTMLDivElement>(null);
  const studioSplitRatioRef = useRef<number>(studioSplitRatio);

  const [isOutputResizing, setIsOutputResizing] = useState<boolean>(false);
  const isOutputResizingRef = useRef<boolean>(false);
  const startOutputYRef = useRef<number>(0);
  const startOutputHeightRef = useRef<number>(220);
  const outputHeightRef = useRef<number>(outputHeight);

  useEffect(() => {
    studioSplitRatioRef.current = studioSplitRatio;
  }, [studioSplitRatio]);

  useEffect(() => {
    outputHeightRef.current = outputHeight;
  }, [outputHeight]);

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
      // 1. Studio vertical divider (Left vs Right column)
      if (isStudioResizingRef.current && studioContainerRef.current) {
        e.preventDefault();
        const rect = studioContainerRef.current.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const newRatio = (mouseX / rect.width) * 100;
        const clampedRatio = Math.min(Math.max(25, newRatio), 75);
        setStudioSplitRatio(clampedRatio);
        studioSplitRatioRef.current = clampedRatio;
        return;
      }

      // 2. Output horizontal divider (Top Canvas vs Bottom Output Drawer)
      if (isOutputResizingRef.current) {
        e.preventDefault();
        const deltaY = startOutputYRef.current - e.clientY;
        const newHeight = startOutputHeightRef.current + deltaY;
        const clampedHeight = Math.min(Math.max(120, newHeight), 600);
        setOutputHeight(clampedHeight);
        outputHeightRef.current = clampedHeight;
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
      if (isStudioResizingRef.current) {
        isStudioResizingRef.current = false;
        setIsStudioResizing(false);
        try {
          localStorage.setItem('compassx_build_split_ratio', String(studioSplitRatioRef.current));
        } catch (_) {}
      }

      if (isOutputResizingRef.current) {
        isOutputResizingRef.current = false;
        setIsOutputResizing(false);
        try {
          localStorage.setItem('compassx_build_output_height', String(outputHeightRef.current));
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

  const handleStudioResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isStudioResizingRef.current = true;
    setIsStudioResizing(true);
  };

  const handleOutputResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isOutputResizingRef.current = true;
    setIsOutputResizing(true);
    startOutputYRef.current = e.clientY;
    startOutputHeightRef.current = outputHeightRef.current;
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
  } = useDevFiles(resolvedAppId, activeWorkspace?.id || devStatus?.workspace_id, !!resolvedAppId);

  // Preview URL for the running application sandbox
  const previewUrl = useMemo(() => {
    return (
      devStatus?.dev_url ||
      (devStatus?.dev_port ? `http://localhost:${devStatus.dev_port}` : '') ||
      (app?.slug ? `https://${app.slug}-dev.135.13.180.167.nip.io` : '') ||
      'http://localhost:9201'
    );
  }, [devStatus?.dev_url, devStatus?.dev_port, app?.slug]);

  // Combined stdout/stderr output for Dev Server log viewer
  const combinedLogs = useMemo(() => {
    const parts: string[] = [];
    if (gitOutput) parts.push(`[git] ${gitOutput}`);
    if (installOutput) parts.push(`[install] ${installOutput}`);
    if (runAppOutput) parts.push(`[run] ${runAppOutput}`);
    if (Array.isArray(devLogsData) && devLogsData.length > 0) {
      parts.push(devLogsData.join('\n'));
    } else if (typeof devLogsData === 'string' && devLogsData.trim()) {
      parts.push(devLogsData);
    }
    return parts.join('\n\n') || (isContainerRunning ? 'Dev server is running. Awaiting output...' : 'Dev server stopped.');
  }, [gitOutput, installOutput, runAppOutput, devLogsData, isContainerRunning]);

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

  // Initial check on mount: Ensure sandbox is requested
  useEffect(() => {
    if (!resolvedAppId || !app) return;

    if (sandboxStatus?.status === 'failed' && !startError) {
      setStartError(sandboxStatus.error_message || sandboxStatus.progress?.message || 'Sandbox initialization failed');
      setIsLogViewerOpen(true);
      return;
    }

    if (
      !isDevLoading &&
      !userExplicitlyStopped &&
      !hasTriggeredInitialStart.current &&
      !ensureAppSandboxMutation.isPending &&
      !startDevMutation.isPending &&
      !restartDevMutation.isPending &&
      devStatus?.status !== 'provisioning' &&
      !devStatus?.is_scaling_node
    ) {
      hasTriggeredInitialStart.current = true;
      ensureAppSandboxMutation.mutate(
        { appId: resolvedAppId },
        {
          onSuccess: (instance) => {
            if (instance.status === 'failed') {
              setStartError(instance.error_message || instance.progress?.message || 'Sandbox initialization failed');
              setIsLogViewerOpen(true);
            }
          },
          onError: (err: any) => {
            const msg = err?.response?.data?.detail || err?.message || 'Failed to start dev sandbox.';
            setStartError(msg);
          },
        }
      );
    }
  }, [resolvedAppId, app, sandboxStatus, isContainerRunning, userExplicitlyStopped, startError, isDevLoading, devStatus]);


  // Staged Progression: Step 4 (Run App)
  const handleProceedToStep4 = useCallback(async () => {
    if (!resolvedAppId) return;
    try {
      setStartError(null);
      setInitStep(3);
      toast.info('Step 4: Starting application server...');
      const res = await runAppMutation.mutateAsync({
        appId: resolvedAppId,
        workspaceId: activeWorkspace?.id || devStatus?.workspace_id,
        workspaceName: activeWorkspace?.name || devStatus?.workspace_name,
      });
      const out = res?.output || res?.message || 'Application running.';
      setRunAppOutput(out);
      setStep4Completed(true);
      setHasCompletedInit(true);
      setPreviewReloadKey(Date.now());
      toast.success('Step 4 Complete: Application running.');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to start application processes.';
      setStartError(msg);
      toast.error(msg);
    }
  }, [resolvedAppId, activeWorkspace?.id, activeWorkspace?.name, devStatus?.workspace_id, devStatus?.workspace_name, runAppMutation, toast]);

  // Staged Progression: Step 3 (Dependencies) & Auto-Trigger Step 4
  const handleProceedToStep3 = useCallback(async () => {
    if (!resolvedAppId) return;
    try {
      setStartError(null);
      setInitStep(2);
      toast.info('Step 3: Installing dependencies...');
      const res = await installDepsMutation.mutateAsync({
        appId: resolvedAppId,
        workspaceId: activeWorkspace?.id || devStatus?.workspace_id,
        workspaceName: activeWorkspace?.name || devStatus?.workspace_name,
      });
      const out = res?.output || res?.message || 'Dependencies installed successfully.';
      setInstallOutput(out);
      setStep3Completed(true);
      toast.success('Step 3 Complete: Dependencies installed.');

      // Automatically launch Step 4 (Application Server)
      await handleProceedToStep4();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to install dependencies.';
      setStartError(msg);
      toast.error(msg);
    }
  }, [resolvedAppId, activeWorkspace?.id, activeWorkspace?.name, devStatus?.workspace_id, devStatus?.workspace_name, installDepsMutation, handleProceedToStep4, toast]);

  // ── Step 1 -> Step 2 -> Step 3 -> Step 4 Auto-Progression ──
  // Step 1 is complete when stage === 'running' (Dev sandbox compute is ready).
  // Step 2 prepares workspace code, then automatically triggers dependency install (Step 3) and app start (Step 4).
  useEffect(() => {
    if (
      stage === 'running' &&
      resolvedAppId &&
      !step2Completed &&
      !verifyGitTriggered.current &&
      !startError &&
      !verifyGitMutation.isPending
    ) {
      verifyGitTriggered.current = true;
      setInitStep(1);
      verifyGitMutation.mutate(
        {
          appId: resolvedAppId,
          workspaceId: activeWorkspace?.id || devStatus?.workspace_id,
          workspaceName: activeWorkspace?.name || devStatus?.workspace_name,
        },
        {
          onSuccess: (data) => {
            const out = data?.output || data?.message || 'Workspace codebase verified and ready.';
            setGitOutput(out);
            setStep2Completed(true);
            setStartError(null);
            // Invalidate files and git commits queries to populate Code panel
            qc.invalidateQueries({ queryKey: ['app-dev-files', resolvedAppId] });
            qc.invalidateQueries({ queryKey: ['apps', resolvedAppId, 'dev', 'commits'] });
            refetchDevFiles();
            toast.success('Step 2 Complete: Workspace code prepared & ready.');

            // Automatically move directly to Step 3 (dependencies) & Step 4 (server start)
            void handleProceedToStep3();
          },
          onError: (err: any) => {
            const msg = err?.response?.data?.detail || err?.message || 'Failed to prepare workspace codebase.';
            setStartError(msg);
            setIsLogViewerOpen(true);
            toast.error(msg);
          },
        }
      );
    }
  }, [
    stage,
    resolvedAppId,
    step2Completed,
    startError,
    activeWorkspace?.id,
    activeWorkspace?.name,
    devStatus?.workspace_id,
    devStatus?.workspace_name,
    handleProceedToStep3,
    qc,
    refetchDevFiles,
    toast,
    verifyGitMutation,
  ]);

  const handleProceedToStudio = () => {
    setHasCompletedInit(true);
    setStep2Completed(true);
    setStep3Completed(true);
    setStep4Completed(true);
    setInitStep(3);
  };

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
    ensureAppSandboxMutation.mutate(
      { appId: resolvedAppId },
      {
        onError: () => {
          startDevMutation.mutate(
            { appId: resolvedAppId, hostType: hostToUse },
            {
              onError: (err: any) => {
                setStartError(err?.response?.data?.detail || err?.message || 'Failed to start dev sandbox.');
              },
            }
          );
        },
      }
    );
  }

  // Clean Restart Dev Sandbox
  function handleRestartSandbox() {
    if (!resolvedAppId || !app) return;
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

    // Optimistically update dev status to provisioning
    qc.setQueryData(['app-dev-status', resolvedAppId], (prev: any) => ({
      ...prev,
      status: 'provisioning',
      phase: 'Pending',
      is_scaling_node: false,
      provisioning_message: 'Restarting sandbox and recreating pod...',
    }));

    restartDevMutation.mutate(
      {
        appId: resolvedAppId,
        hostType: selectedHost,
        workspaceId: activeWorkspace?.id || devStatus?.workspace_id,
        workspaceName: activeWorkspace?.name || devStatus?.workspace_name,
      },
      {
        onSuccess: (data) => {
          setStartError(null);
          qc.setQueryData(['app-dev-status', resolvedAppId], data);
          qc.invalidateQueries({ queryKey: ['app-dev-status', resolvedAppId] });
          qc.invalidateQueries({ queryKey: ['app-dev-workspaces', resolvedAppId] });
        },
        onError: (err: any) => {
          const msg = err?.response?.data?.detail || err?.message || 'Failed to restart dev sandbox.';
          setStartError(msg);
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
          background: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          position: 'relative',
          zIndex: 100,
        }}
      >
        {/* Left: Brand, Apps Breadcrumb, App Name & Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Platform Brand */}
          <div
            onClick={() => navigate('/apps')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              userSelect: 'none',
              padding: '2px 4px',
              borderRadius: 6,
              transition: 'background 0.15s ease',
            }}
            title="Go to Apps"
          >
            <CompassXLogo size={20} color="#1B6EF3" />
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.01em' }}>
                Compass<span style={{ color: '#1B6EF3' }}>X</span>
              </span>
              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#64748b' }}>
                App Builder
              </span>
            </div>
          </div>

          <div style={{ height: 16, width: 1, background: '#e2e8f0', margin: '0 2px' }} />

          {/* Breadcrumb back to Apps: "< Apps" matching screenshot */}
          <button
            type="button"
            onClick={() => navigate('/apps')}
            title="Back to Apps"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              background: 'transparent',
              border: 'none',
              padding: '3px 8px',
              borderRadius: 5,
              cursor: 'pointer',
              color: '#64748b',
              fontSize: '0.84rem',
              fontWeight: 500,
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
            <ChevronLeft size={14} />
            <span>Apps</span>
          </button>

          <div style={{ height: 16, width: 1, background: '#e2e8f0', margin: '0 2px' }} />

          {/* App Name with Status Indicator Dot */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: stage === 'running' ? '#10b981' : stage === 'starting' ? '#f59e0b' : '#94a3b8',
                boxShadow: stage === 'running' ? '0 0 6px rgba(16, 185, 129, 0.5)' : 'none',
                display: 'inline-block',
                flexShrink: 0,
              }}
              title={stage === 'running' ? 'Sandbox Running' : stage === 'starting' ? 'Starting...' : 'Stopped'}
            />
            <button
              type="button"
              onClick={() => navigate(`/apps/${resolvedAppId}`)}
              title="View App Details"
              style={{
                background: 'transparent',
                border: 'none',
                padding: '2px 6px',
                borderRadius: 4,
                cursor: 'pointer',
                color: '#0f172a',
                fontSize: '0.88rem',
                fontWeight: 600,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#1B6EF3';
                e.currentTarget.style.background = '#f1f5f9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#0f172a';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              {app?.name || 'App'}
            </button>
          </div>

          {/* Sandbox (Git Worktree) Selector Dropdown & Quick Restart Action */}
          {/* Sandbox (Git Worktree) Selector Dropdown */}
          {(stage === 'running' || stage === 'starting') && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 2 }}>
              <SandboxSelector
                appId={resolvedAppId!}
                workspaces={devWorkspaces}
                activeWorkspaceId={activeWorkspace?.id}
                baseBranch={app?.git_branch || 'main'}
                onSelectWorkspace={handleSelectWorkspace}
                onOpenNewSandboxModal={() => setIsNewSandboxModalOpen(true)}
                isSwitching={isSwitchingSandbox}
                disabled={!isContainerRunning}
              />
            </div>
          )}
        </div>

        {/* Right: Refresh Sandbox Button & Three Dots Action Menu */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {/* Quick Restart Sandbox Button */}
          {(stage === 'running' || stage === 'starting') && (
            <button
              type="button"
              onClick={handleRestartSandbox}
              disabled={restartDevMutation.isPending || !isContainerRunning}
              title="Restart Dev Sandbox"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                borderRadius: 4,
                border: 'none',
                background: 'transparent',
                color: '#64748b',
                cursor: restartDevMutation.isPending || !isContainerRunning ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (isContainerRunning) {
                  e.currentTarget.style.color = '#1e293b';
                  e.currentTarget.style.background = '#f1f5f9';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#64748b';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <RefreshCw
                size={14}
                className={restartDevMutation.isPending ? 'animate-spin text-blue-600' : ''}
              />
            </button>
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
          background: '#f8fafc',
          position: 'relative',
          overflow: stage === 'running' ? 'hidden' : 'auto',
          padding: stage === 'running' ? 0 : '24px 32px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {stage === 'running' ? (
          /* Stage: Running -> 2-Column Split Studio Layout */
          <div
            ref={studioContainerRef}
            style={{
              flex: 1,
              height: '100%',
              minHeight: 0,
              display: 'flex',
              gap: 0,
              borderRadius: 0,
              overflow: 'hidden',
              animation: 'fadeIn 0.3s ease-in-out',
              background: '#ffffff',
              border: 'none',
              boxShadow: 'none',
            }}
          >
            {/* ── Left Column: Agent & Terminal Studio ── */}
            <div
              style={{
                width: `${studioSplitRatio}%`,
                height: '100%',
                minWidth: 320,
                display: 'flex',
                flexDirection: 'column',
                background: '#ffffff',
                overflow: 'hidden',
                position: 'relative',
                flexShrink: 0,
              }}
            >
              {/* Left Column Header / Toolstrip */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 12px',
                  borderBottom: '1px solid #e2e8f0',
                  background: '#ffffff',
                  flexShrink: 0,
                  height: 46,
                  minHeight: 46,
                }}
              >
                {/* Left: Active Session Title & Sandbox Subtitle */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          color: '#0f172a',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {activeSession?.title || 'Agent Session'}
                      </span>

                      {activeSession?.agent && (
                        <span
                          style={{
                            fontSize: '0.66rem',
                            padding: '1px 5px',
                            borderRadius: 4,
                            background: '#f1f5f9',
                            color: '#475569',
                            fontWeight: 500,
                            fontFamily: 'monospace',
                            flexShrink: 0,
                          }}
                        >
                          {activeSession.agent}
                        </span>
                      )}
                    </div>

                    <span
                      style={{
                        fontSize: '0.69rem',
                        color: '#64748b',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {activeWorkspace?.name || devStatus?.workspace_name || 'default'}
                    </span>
                  </div>
                </div>

                {/* Right: Quick Action Buttons & More Menu */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                  {/* 1. Session History Popover Trigger */}
                  <div style={{ position: 'relative' }}>
                    <button
                      type="button"
                      onClick={() => {
                        setIsMoreMenuOpen(false);
                        setIsHistoryPopoverOpen((prev) => !prev);
                      }}
                      title="Session History"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 28,
                        height: 28,
                        borderRadius: 4,
                        border: 'none',
                        background: isHistoryPopoverOpen ? '#e0f2fe' : 'transparent',
                        color: isHistoryPopoverOpen ? '#0284c7' : '#52525b',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (!isHistoryPopoverOpen) {
                          e.currentTarget.style.background = '#f4f4f5';
                          e.currentTarget.style.color = '#18181b';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isHistoryPopoverOpen) {
                          e.currentTarget.style.background = 'transparent';
                          e.currentTarget.style.color = '#52525b';
                        }
                      }}
                    >
                      <History size={16} strokeWidth={1.75} />
                    </button>

                    <SessionHistoryPopover
                      isOpen={isHistoryPopoverOpen}
                      onClose={() => setIsHistoryPopoverOpen(false)}
                      sessions={(allSessions || []).filter((s: DevSession) => s.agent !== 'bash')}
                      activeSessionId={activeSession?.id || activeSessionId}
                      onSelectSession={(sid) => {
                        handleSelectSession(sid);
                        setIsHistoryPopoverOpen(false);
                      }}
                      onOpenNewSession={() => {
                        setIsHistoryPopoverOpen(false);
                        setIsNewSessionModalOpen(true);
                      }}
                      onDeleteSession={handleDeleteSession}
                      disabled={!isContainerRunning}
                    />
                  </div>

                  {/* 2. New Session (SquarePen / Compose) Button */}
                  <button
                    type="button"
                    onClick={() => {
                      setIsHistoryPopoverOpen(false);
                      setIsMoreMenuOpen(false);
                      setIsNewSessionModalOpen(true);
                    }}
                    disabled={!isContainerRunning}
                    title="Start New Session with an AI Agent"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 28,
                      height: 28,
                      borderRadius: 4,
                      border: 'none',
                      background: 'transparent',
                      color: '#52525b',
                      cursor: isContainerRunning ? 'pointer' : 'not-allowed',
                      opacity: isContainerRunning ? 1 : 0.5,
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (isContainerRunning) {
                        e.currentTarget.style.background = '#f4f4f5';
                        e.currentTarget.style.color = '#18181b';
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                      e.currentTarget.style.color = '#52525b';
                    }}
                  >
                    <SquarePen size={16} strokeWidth={1.75} />
                  </button>

                  {/* 3. More Options Menu (Three Dots) Button */}
                  <div style={{ position: 'relative' }}>
                    <button
                      type="button"
                      onClick={() => {
                        setIsHistoryPopoverOpen(false);
                        setIsMoreMenuOpen((prev) => !prev);
                      }}
                      title="More options"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 28,
                        height: 28,
                        borderRadius: 4,
                        border: 'none',
                        background: isMoreMenuOpen ? '#e0f2fe' : 'transparent',
                        color: isMoreMenuOpen ? '#0284c7' : '#52525b',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (!isMoreMenuOpen) {
                          e.currentTarget.style.background = '#f4f4f5';
                          e.currentTarget.style.color = '#18181b';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isMoreMenuOpen) {
                          e.currentTarget.style.background = 'transparent';
                          e.currentTarget.style.color = '#52525b';
                        }
                      }}
                    >
                      <MoreVertical size={16} strokeWidth={1.75} />
                    </button>

                    {isMoreMenuOpen && (
                      <>
                        {/* Dismiss backdrop */}
                        <div
                          style={{ position: 'fixed', inset: 0, zIndex: 45 }}
                          onClick={() => setIsMoreMenuOpen(false)}
                        />
                        {/* Dropdown Menu */}
                        <div
                          style={{
                            position: 'absolute',
                            right: 0,
                            top: '100%',
                            marginTop: 4,
                            zIndex: 50,
                            width: 190,
                            background: '#ffffff',
                            borderRadius: 8,
                            border: '1px solid #e2e8f0',
                            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
                            padding: 5,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 2,
                          }}
                        >
                          {/* View Mode Section */}
                          <div style={{ padding: '4px 8px 2px 8px', fontSize: '0.66rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            View Mode
                          </div>

                          <button
                            type="button"
                            onClick={() => {
                              setIsMoreMenuOpen(false);
                              setLeftPanelMode('cli');
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              width: '100%',
                              padding: '6px 8px',
                              borderRadius: 5,
                              border: 'none',
                              background: leftPanelMode === 'cli' ? '#f0fdf4' : 'transparent',
                              color: leftPanelMode === 'cli' ? '#166534' : '#1e293b',
                              fontSize: '0.78rem',
                              textAlign: 'left',
                              cursor: 'pointer',
                              transition: 'background 0.12s ease',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <Terminal size={14} color={leftPanelMode === 'cli' ? '#16a34a' : '#64748b'} />
                              <span style={{ fontWeight: leftPanelMode === 'cli' ? 600 : 500 }}>Terminal (CLI)</span>
                            </div>
                            {leftPanelMode === 'cli' && <Check size={14} color="#16a34a" />}
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              setIsMoreMenuOpen(false);
                              setLeftPanelMode('chat');
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              width: '100%',
                              padding: '6px 8px',
                              borderRadius: 5,
                              border: 'none',
                              background: leftPanelMode === 'chat' ? '#eef2ff' : 'transparent',
                              color: leftPanelMode === 'chat' ? '#4338ca' : '#1e293b',
                              fontSize: '0.78rem',
                              textAlign: 'left',
                              cursor: 'pointer',
                              transition: 'background 0.12s ease',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <Bot size={14} color={leftPanelMode === 'chat' ? '#6366f1' : '#64748b'} />
                              <span style={{ fontWeight: leftPanelMode === 'chat' ? 600 : 500 }}>Chat UI</span>
                            </div>
                            {leftPanelMode === 'chat' && <Check size={14} color="#6366f1" />}
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              setIsMoreMenuOpen(false);
                              setLeftPanelMode('split');
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              width: '100%',
                              padding: '6px 8px',
                              borderRadius: 5,
                              border: 'none',
                              background: leftPanelMode === 'split' ? '#f5f3ff' : 'transparent',
                              color: leftPanelMode === 'split' ? '#6d28d9' : '#1e293b',
                              fontSize: '0.78rem',
                              textAlign: 'left',
                              cursor: 'pointer',
                              transition: 'background 0.12s ease',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <Layers size={14} color={leftPanelMode === 'split' ? '#8b5cf6' : '#64748b'} />
                              <span style={{ fontWeight: leftPanelMode === 'split' ? 600 : 500 }}>Split (Dual)</span>
                            </div>
                            {leftPanelMode === 'split' && <Check size={14} color="#8b5cf6" />}
                          </button>

                          <div style={{ height: 1, background: '#e2e8f0', margin: '4px 0' }} />

                          {/* Sandbox Actions */}
                          <button
                            type="button"
                            onClick={() => {
                              setIsMoreMenuOpen(false);
                              handleRestartSandbox();
                            }}
                            disabled={!isContainerRunning}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '6px 8px',
                              borderRadius: 5,
                              border: 'none',
                              background: 'transparent',
                              color: '#1e293b',
                              fontSize: '0.78rem',
                              textAlign: 'left',
                              cursor: isContainerRunning ? 'pointer' : 'not-allowed',
                              opacity: isContainerRunning ? 1 : 0.5,
                              transition: 'background 0.12s ease',
                            }}
                            onMouseEnter={(e) => {
                              if (isContainerRunning) e.currentTarget.style.background = '#f1f5f9';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent';
                            }}
                          >
                            <RefreshCw size={14} color="#0284c7" />
                            <span style={{ fontWeight: 500 }}>Restart Sandbox</span>
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Main Left Content: OmnigentChatPanel exclusively for AI Agent Studio */}
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  background: '#ffffff',
                }}
              >
                <OmnigentChatPanel
                  app={app || ({ id: resolvedAppId, name: 'CompassX App' } as any)}
                  resolvedAppId={resolvedAppId!}
                  devStatus={devStatus}
                  isDevPodRunning={isContainerRunning}
                  viewMode={leftPanelMode}
                  onViewModeChange={setLeftPanelMode}
                  showHeader={false}
                  agentName={currentAgent}
                  sessionId={activeSession?.id}
                  sessionTitle={activeSession?.title}
                  workspaceId={activeWorkspace?.id || devStatus?.workspace_id}
                  workspaceName={activeWorkspace?.name || devStatus?.workspace_name}
                  onCodeUpdated={() => {
                    qc.invalidateQueries({ queryKey: ['app-dev-files', resolvedAppId] });
                    qc.invalidateQueries({ queryKey: ['app-dev-file-content', resolvedAppId] });
                    qc.invalidateQueries({ queryKey: ['apps', resolvedAppId, 'dev', 'commits'] });
                    setPreviewReloadKey(Date.now());
                  }}
                />
              </div>
            </div>

            {/* ── Draggable Splitter between Left & Right Column ── */}
            <div
              role="separator"
              aria-orientation="vertical"
              title="Drag to resize columns • Double-click to reset"
              onMouseDown={handleStudioResizeMouseDown}
              onDoubleClick={() => setStudioSplitRatio(42)}
              onMouseEnter={() => setIsStudioSplitterHovered(true)}
              onMouseLeave={() => setIsStudioSplitterHovered(false)}
              style={{
                width: 1,
                flexShrink: 0,
                cursor: 'col-resize',
                position: 'relative',
                zIndex: 20,
                userSelect: 'none',
                background: isStudioSplitterHovered || isStudioResizing ? '#2563eb' : '#e2e8f0',
                boxShadow: isStudioSplitterHovered || isStudioResizing ? '0 0 6px rgba(37, 99, 235, 0.5)' : 'none',
                transition: 'background-color 0.15s ease, box-shadow 0.15s ease',
              }}
            >
              {/* Invisible 8px wide grab area centered on the 1px line */}
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  bottom: 0,
                  left: -4,
                  right: -4,
                  cursor: 'col-resize',
                }}
              />
            </div>

            {/* ── Right Column: Dual Canvas & Runtime Diagnostics ── */}
            <div
              style={{
                flex: 1,
                minWidth: 360,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                background: '#ffffff',
                overflow: 'hidden',
              }}
            >
              {/* Top Browser Toolbar with View Switcher, Address Bar & Deploy Button */}
              <BrowserToolbar
                viewMode={canvasViewMode}
                onViewModeChange={setCanvasViewMode}
                previewUrl={previewUrl}
                route={previewRoute}
                onRouteChange={setPreviewRoute}
                onReload={() => setPreviewReloadKey(Date.now())}
                isReloading={false}
                onDeploy={handleDeployApp}
                isDeploying={deployMutation.isPending}
                isCanvasMaximized={isCanvasMaximized}
                onToggleCanvasMaximized={() => setIsCanvasMaximized((prev) => !prev)}
                isOutputCollapsed={isOutputCollapsed}
                onToggleOutputCollapsed={() => setIsOutputCollapsed((prev) => !prev)}
                disabled={!isContainerRunning}
                appId={resolvedAppId}
                workspaceId={activeWorkspace?.id || devStatus?.workspace_id}
                workspaceName={activeWorkspace?.name || devStatus?.workspace_name}
                baseBranch={app?.git_branch || 'main'}
              />

              {/* Main Top Canvas (Preview or Code) */}
              <div
                style={{
                  flex: 1,
                  minHeight: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  position: 'relative',
                }}
              >
                {canvasViewMode === 'preview' ? (
                  <LivePreviewCanvas
                    previewUrl={previewUrl}
                    route={previewRoute}
                    isContainerRunning={isContainerRunning}
                    reloadKey={previewReloadKey}
                    onReload={() => setPreviewReloadKey(Date.now())}
                    onStartDevPod={() => handleStartDev('compassx')}
                    isStartingDevPod={startDevMutation.isPending}
                    initStep={initStep}
                    step2Completed={step2Completed}
                    step3Completed={step3Completed}
                    step4Completed={step4Completed}
                    hasCompletedInit={hasCompletedInit}
                    startError={startError}
                    onRetryGit={handleRetryGit}
                    onRetryInstall={handleRetryInstall}
                    onRetryRunApp={handleRetryRunApp}
                    isRetrying={
                      verifyGitMutation.isPending ||
                      installDepsMutation.isPending ||
                      runAppMutation.isPending
                    }
                    onToggleLogs={() => setIsOutputCollapsed((prev) => !prev)}
                    isOutputCollapsed={isOutputCollapsed}
                    devLogs={combinedLogs}
                    onSwitchToCode={() => setCanvasViewMode('code')}
                    onProceedToStep3={handleProceedToStep3}
                    isProceedingToStep3={installDepsMutation.isPending}
                  />
                ) : (
                  <CodeEditorCanvas
                    appId={resolvedAppId!}
                    appName={app?.name}
                    workspaceId={activeWorkspace?.id || devStatus?.workspace_id}
                    workspaceName={activeWorkspace?.name || devStatus?.workspace_name}
                    files={devFiles}
                    isLoading={isDevFilesLoading}
                    onRefresh={() => refetchDevFiles()}
                    selectedFilePath={selectedFilePath}
                    onSelectFilePath={setSelectedFilePath}
                  />
                )}
              </div>

              {/* Horizontal Resizer & Bottom Output Drawer (when not maximized) */}
              {!isCanvasMaximized && (
                <>
                  {/* Draggable Divider Handle between Canvas & Output Drawer */}
                  {!isOutputCollapsed && (
                    <div
                      role="separator"
                      aria-orientation="horizontal"
                      title="Drag to resize output drawer • Double-click to reset"
                      onMouseDown={handleOutputResizeMouseDown}
                      onDoubleClick={() => setOutputHeight(220)}
                      style={{
                        height: 6,
                        flexShrink: 0,
                        cursor: 'row-resize',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        position: 'relative',
                        zIndex: 20,
                        userSelect: 'none',
                        background: '#f1f5f9',
                        borderTop: '1px solid #e2e8f0',
                      }}
                    >
                      <div
                        style={{
                          width: 36,
                          height: 2,
                          borderRadius: 9999,
                          backgroundColor: isOutputResizing ? '#2563eb' : '#cbd5e1',
                          transition: 'background-color 0.15s ease',
                        }}
                      />
                    </div>
                  )}

                  {/* Bottom Output Drawer */}
                  <OutputDrawer
                    devLogs={combinedLogs}
                    isDevRunning={isContainerRunning}
                    onRefreshLogs={() => refetchDevLogs()}
                    isRefreshing={isDevLogsLoading}
                    isCollapsed={isOutputCollapsed}
                    onToggleCollapsed={() => setIsOutputCollapsed((prev) => !prev)}
                    onClose={() => setIsOutputCollapsed(true)}
                    height={outputHeight}
                    onHeightChange={setOutputHeight}
                    appId={resolvedAppId}
                    appName={app?.name || 'app'}
                    workspaceId={activeWorkspace?.id || devStatus?.workspace_id}
                    workspaceName={activeWorkspace?.name || devStatus?.workspace_name}
                    isDevPodRunning={isContainerRunning}
                  />
                </>
              )}
            </div>
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
            <h2 style={{ margin: '0 0 6px', fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>
              Stopping Dev Sandbox...
            </h2>
            <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>
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
            <h2 style={{ margin: '0 0 6px', fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>
              {startError
                ? 'Sandbox Startup Failed'
                : isContainerRunning || sandboxStatus?.status === 'ready' || sandboxStatus?.status === 'running'
                ? 'Sandbox Provisioned & Ready'
                : sandboxStatus?.progress?.stage === 'allocating'
                ? 'Allocating Compute Sandbox'
                : sandboxStatus?.progress?.stage === 'starting'
                ? 'Starting Container Runtime'
                : sandboxStatus?.progress?.stage === 'initializing'
                ? `Step ${sandboxStatus.progress.step_index} of ${sandboxStatus.progress.total_steps} • ${sandboxStatus.progress.step_name}`
                : devStatus?.is_scaling_node
                ? 'Allocating Cloud Cluster Compute'
                : 'Preparing Build Environment'}
            </h2>
            <p style={{ margin: '0 0 24px', fontSize: '0.85rem', color: '#64748b' }}>
              {startError
                ? (sandboxStatus?.error_message || startError || 'An error occurred during sandbox initialization.')
                : isContainerRunning || sandboxStatus?.status === 'ready' || sandboxStatus?.status === 'running'
                ? 'Dev sandbox compute is provisioned and running. (Test paused before app build)'
                : sandboxStatus?.progress?.message
                ? sandboxStatus.progress.message
                : devStatus?.is_scaling_node
                ? 'Cluster is scaling worker node to allocate compute resources (1-3 min)...'
                : `Step ${initStep + 1} of ${BUILD_STEPS.length} • ${BUILD_STEPS[initStep].title}`}
            </p>

            {/* Sandbox Provisioned Info Box (When Ready) */}
            {(isContainerRunning || sandboxStatus?.status === 'ready' || sandboxStatus?.status === 'running') && !startError && (
              <div
                style={{
                  width: '100%',
                  margin: '0 0 20px',
                  padding: '14px 18px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: 10,
                  textAlign: 'left',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#1e293b' }}>
                    Compute Sandbox Details
                  </span>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 12,
                      background: 'rgba(16, 185, 129, 0.12)',
                      color: '#059669',
                    }}
                  >
                    ● READY
                  </span>
                </div>
                <div style={{ fontSize: '0.76rem', color: '#64748b', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div><strong>Sandbox ID:</strong> {sandboxStatus?.id || `dev-app-${resolvedAppId}`}</div>
                  <div><strong>Consumer Module:</strong> App Engine (app)</div>
                  <div><strong>Compute Status:</strong> Visible under <strong>Compute &gt; Sandboxes</strong> tab</div>
                </div>
                <div style={{ marginTop: 8, display: 'flex', gap: 10 }}>
                  <button
                    type="button"
                    onClick={handleProceedToStudio}
                    style={{
                      flex: 1,
                      padding: '8px 16px',
                      background: '#2563eb',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: 6,
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Proceed to Studio Canvas</span>
                  </button>
                </div>
              </div>
            )}

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

            {/* Node Scaling Information Banner */}
            {devStatus?.is_scaling_node && !startError && (
              <div
                style={{
                  margin: '4px 0 16px',
                  padding: '12px 16px',
                  background: 'rgba(245, 158, 11, 0.08)',
                  border: '1px solid rgba(245, 158, 11, 0.25)',
                  borderRadius: 8,
                  maxWidth: 480,
                  width: '100%',
                  textAlign: 'left',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  boxShadow: '0 4px 16px rgba(245, 158, 11, 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#f59e0b', fontSize: '0.84rem', fontWeight: 600 }}>
                  <Loader2 size={15} className="spin" />
                  <span>Cluster Worker Node Autoscaling in Progress</span>
                </div>
                <div style={{ fontSize: '0.78rem', color: '#475569', lineHeight: 1.55 }}>
                  {devStatus.provisioning_message ||
                    'The Kubernetes cluster is provisioning a new worker node to allocate compute resources for this sandbox. This usually takes 1-3 minutes. The sandbox will initialize automatically once the node joins the cluster.'}
                </div>
              </div>
            )}

            {/* Step Description / Status Details */}
            {!startError ? (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: '0.82rem',
                  color: '#64748b',
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
                    : sandboxStatus?.progress?.message
                    ? sandboxStatus.progress.message
                    : devStatus?.is_scaling_node
                    ? 'Waiting for cluster worker node to become ready (1-3 min)...'
                    : devStatus?.status === 'provisioning' && devStatus?.provisioning_message
                    ? devStatus.provisioning_message
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
                    background: isLogViewerOpen ? '#e2e8f0' : '#f1f5f9',
                    border: '1px solid #cbd5e1',
                    borderRadius: 6,
                    color: '#334155',
                    padding: '5px 12px',
                    fontSize: '0.78rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <Terminal size={13} color="#2563eb" />
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
                      background: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                      display: 'flex',
                      flexDirection: 'column',
                      overflow: 'hidden',
                      textAlign: 'left',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
                    }}
                  >
                    {/* Log Console Header Bar */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 12px',
                        background: '#f8fafc',
                        borderBottom: '1px solid #e2e8f0',
                        fontSize: '0.72rem',
                        color: '#475569',
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
                            color: autoScrollLogs ? '#2563eb' : '#64748b',
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
                            color: '#64748b',
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
                        color: startError ? '#dc2626' : '#334155',
                        lineHeight: 1.55,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                      }}
                    >
                      {(() => {
                        const rawLogs = (Array.isArray(devLogsData) && devLogsData.length > 0 ? devLogsData.join('\n') : (typeof devLogsData === 'string' && devLogsData ? devLogsData : '')).trim();
                        const parts = [gitOutput, installOutput, runAppOutput].filter(Boolean);
                        if (rawLogs) {
                          return rawLogs;
                        }
                        if (parts.length > 0) {
                          return parts.join('\n\n');
                        }
                        if (initStep === 1) {
                          return 'Verifying git repository, branch, and working tree...';
                        }
                        if (initStep === 2) {
                          return 'Checking dependency manifests and running package installer inside sandbox...';
                        }
                        if (initStep === 3) {
                          return 'Starting application processes and verifying dev server...';
                        }
                        return 'Initializing dev environment...';
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
                    onClick={handleRestartSandbox}
                    disabled={restartDevMutation.isPending || startDevMutation.isPending}
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
                      cursor: restartDevMutation.isPending || startDevMutation.isPending ? 'not-allowed' : 'pointer',
                      opacity: restartDevMutation.isPending || startDevMutation.isPending ? 0.7 : 1,
                      boxShadow: '0 2px 8px rgba(37, 99, 235, 0.3)',
                    }}
                  >
                    {restartDevMutation.isPending ? (
                      <>
                        <Loader2 size={14} className="spin" />
                        <span>Restarting Sandbox...</span>
                      </>
                    ) : (
                      <>
                        <RefreshCw size={14} />
                        <span>Restart Sandbox</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Transparent overlay during resize to lock cursor and prevent iframe/xterm event loss */}
        {(isStudioResizing || isOutputResizing || isExplorerResizing) && (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 99999,
              cursor: isOutputResizing ? 'row-resize' : 'col-resize',
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
        activeBranch={activeWorkspace?.git_branch}
        defaultBaseBranch={app?.git_branch || 'main'}
        onCreated={(newWsId) => {
          if (newWsId) setSelectedWsId(newWsId);
          setPreviewReloadKey(Date.now());
          qc.invalidateQueries({ queryKey: ['app-dev-files', resolvedAppId] });
          qc.invalidateQueries({ queryKey: ['app-dev-status', resolvedAppId] });
          qc.invalidateQueries({ queryKey: ['app-dev-workspaces', resolvedAppId] });
          refetchDevWorkspaces();
          refetchDevStatus();
          refetchDevFiles();
          refetchDevLogs();
        }}
      />
    </div>
  );
}
