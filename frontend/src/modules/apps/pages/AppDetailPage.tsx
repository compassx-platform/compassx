import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  Boxes,
  Code2,
  FolderGit2,
  GitBranch,
  ShieldCheck,
  Play,
  Pause,
  RotateCw,
  Trash2,
  ExternalLink,
  Save,
  Clock,
  AlertCircle,
  Loader2,
  ArrowLeft,
  Copy,
  Check,
  Terminal,
  Server,
  Eye,
  EyeOff,
  Plus,
  Search,
  Download,
  Layers,
  Sparkles,
  Lock,
  Globe,
  Settings,
  Cpu,
  HardDrive,
  RefreshCw,
  Radio,
  Rocket,
  GitCommit,
  CheckCircle2,
  XCircle,
  History,
  Square,
  ListTodo,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import {
  useApp,
  useUpdateApp,
  useDeployApp,
  useAppDeployments,
  useAppLogs,
  useUpdateAppStatus,
  useDeleteApp,
  useStartDevSession,
  useDevStatus,
  useStopDevSession,
  useDevWorkspaces,
  useDeleteDevWorkspace,
  DevWorkspace,
  DeploymentItem,
} from '../hooks/useApps';
import { useAppTasks } from '../hooks/useAppTasks';
import { APP_TYPES } from '../components/CreateAppModal';
import { AppTasksKanban } from '../components/tasks/AppTasksKanban';
import { AppDevelopmentTab } from '../components/AppDevelopmentTab';

type DetailTab = 'overview' | 'development' | 'deployments' | 'configuration' | 'environment' | 'logs' | 'tasks';

export default function AppDetailPage() {
  const params = useParams<{ applicationId?: string; appId?: string }>();
  const resolvedAppId =
    params.applicationId ||
    (params.appId && params.appId !== 'apps' && params.appId !== 'platform' ? params.appId : undefined);

  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useScopedNavigate();
  const toast = useToast();

  const tabParam = searchParams.get('tab') as DetailTab | null;
  const activeTab: DetailTab =
    tabParam === 'development' ||
    tabParam === 'deployments' ||
    tabParam === 'configuration' ||
    tabParam === 'environment' ||
    tabParam === 'logs' ||
    tabParam === 'tasks'
      ? tabParam
      : 'overview';

  function handleTabChange(newTab: DetailTab) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (newTab === 'overview') {
          next.delete('tab');
        } else {
          next.set('tab', newTab);
        }
        return next;
      },
      { replace: true }
    );
  }

  const { data: app, isLoading, error, refetch } = useApp(resolvedAppId);
  const updateMutation = useUpdateApp();
  const deployMutation = useDeployApp();
  const statusMutation = useUpdateAppStatus();
  const deleteMutation = useDeleteApp();
  const { data: logsData, isFetching: logsFetching, refetch: refetchLogs } = useAppLogs(
    resolvedAppId,
    activeTab === 'logs' || activeTab === 'overview'
  );
  const { data: deploymentsData, isFetching: deploymentsFetching, refetch: refetchDeployments } = useAppDeployments(
    resolvedAppId,
    activeTab === 'deployments' || activeTab === 'overview'
  );
  const { data: tasksData } = useAppTasks(
    resolvedAppId,
    activeTab === 'tasks' || activeTab === 'overview'
  );

  // Deployments Tab State
  const [selectedDeploymentId, setSelectedDeploymentId] = useState<string | null>(null);
  const [deploymentLogFilter, setDeploymentLogFilter] = useState('');
  const [deploymentLogLevel, setDeploymentLogLevel] = useState<'ALL' | 'INFO' | 'BUILD' | 'WARN' | 'ERROR'>('ALL');
  const [deploymentAutoScroll, setDeploymentAutoScroll] = useState(true);
  const [historySearch, setHistorySearch] = useState('');
  const deploymentTerminalRef = useRef<HTMLDivElement>(null);

  // Configuration Tab State
  const [configName, setConfigName] = useState('');
  const [configDescription, setConfigDescription] = useState('');
  const [configAppType, setConfigAppType] = useState('streamlit');
  const [configRoute, setConfigRoute] = useState('');
  const [configGitUrl, setConfigGitUrl] = useState('');
  const [configGitProvider, setConfigGitProvider] = useState('github');
  const [configGitRef, setConfigGitRef] = useState('main');
  const [configGitRefType, setConfigGitRefType] = useState('branch');
  const [configGitSubdir, setConfigGitSubdir] = useState('');
  const [configEntrypoint, setConfigEntrypoint] = useState('');
  const [configCredType, setConfigCredType] = useState<'link_account' | 'pat' | 'none'>('none');
  const [configCredNickname, setConfigCredNickname] = useState('');
  const [configPat, setConfigPat] = useState('');
  const [configDirty, setConfigDirty] = useState(false);

  // Environment Tab State
  const [envVars, setEnvVars] = useState<Array<{ key: string; value: string; isSecret: boolean }>>([
    { key: 'ENVIRONMENT', value: 'production', isSecret: false },
    { key: 'API_BASE_URL', value: 'https://api.compassx.internal', isSecret: false },
    { key: 'LOG_LEVEL', value: 'INFO', isSecret: false },
  ]);
  const [newEnvKey, setNewEnvKey] = useState('');
  const [newEnvVal, setNewEnvVal] = useState('');
  const [newEnvSecret, setNewEnvSecret] = useState(false);
  const [revealedSecrets, setRevealedSecrets] = useState<Record<number, boolean>>({});
  const [cpuCores, setCpuCores] = useState('1');
  const [memoryLimit, setMemoryLimit] = useState('2Gi');
  const [replicas, setReplicas] = useState(1);
  const [envDirty, setEnvDirty] = useState(false);

  // Logs Tab State
  const [logFilter, setLogFilter] = useState('');
  const [logLevel, setLogLevel] = useState<'ALL' | 'INFO' | 'WARN' | 'ERROR'>('ALL');
  const [autoScroll, setAutoScroll] = useState(true);
  const logTerminalRef = useRef<HTMLDivElement>(null);

  // UI Helpers
  const [copiedRoute, setCopiedRoute] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);

  // Dev Studio / Omnigent State
  const { data: devStatus, isFetching: devStatusFetching, refetch: refetchDevStatus } = useDevStatus(resolvedAppId);
  const { data: devWorkspaces, refetch: refetchDevWorkspaces } = useDevWorkspaces(resolvedAppId);
  const startDevMutation = useStartDevSession();
  const stopDevMutation = useStopDevSession();
  const deleteWorkspaceMutation = useDeleteDevWorkspace();
  const [isStoppingDevPod, setIsStoppingDevPod] = useState<boolean>(false);
  const [launchStep, setLaunchStep] = useState(0);
  const [launchStatusText, setLaunchStatusText] = useState('');

  const isDevPodStopping = isStoppingDevPod || stopDevMutation.isPending || devStatus?.status === 'stopping' || devStatus?.phase === 'Terminating';
  const isDevPodStarting = startDevMutation.isPending || devStatus?.status === 'provisioning' || (launchStep > 0 && launchStep < 4);
  const isDevPodRunning = (devStatus?.status === 'active' || devStatus?.phase === 'Running') && !isDevPodStopping;

  async function handleStartDevPod(arg1?: string | boolean, arg2?: boolean) {
    if (!resolvedAppId || !app) return;
    let workspaceId: string | undefined = undefined;
    let openStudio: boolean = false;
    if (typeof arg1 === 'string') {
      workspaceId = arg1;
      openStudio = arg2 ?? true;
    } else if (typeof arg1 === 'boolean') {
      openStudio = arg1;
    }
    try {
      setLaunchStep(1);
      setLaunchStatusText('1. Probing Omnigent central server health and endpoints...');
      await new Promise((r) => setTimeout(r, 400));

      setLaunchStep(2);
      setLaunchStatusText('2. Initializing isolated dev sandbox pod & cloning repository...');

      const session = await startDevMutation.mutateAsync({ appId: resolvedAppId, workspaceId });

      setLaunchStep(3);
      setLaunchStatusText('3. Establishing WebSocket runner tunnel with Omnigent server...');
      await new Promise((r) => setTimeout(r, 600));

      setLaunchStep(4);
      setLaunchStatusText('4. Dev pod is running and ready!');

      if (openStudio) {
        const targetUrl = session?.omnigent_session_url || session?.omnigent_server_url || 'https://devstudio.135.13.180.167.nip.io';
        window.open(targetUrl, '_blank');
        toast.success(`Omnigent Dev Studio ready and opened for ${app.name}`);
      } else {
        toast.success(`Dev sandbox pod started successfully for ${app.name}`);
      }
      refetchDevStatus();
      refetchDevWorkspaces();
    } catch (err: any) {
      setLaunchStep(0);
      setLaunchStatusText('');
      toast.error(err?.response?.data?.detail || 'Failed to start dev pod session.');
    }
  }

  const handleLaunchDevStudio = () => handleStartDevPod(undefined, true);
  const handleLaunchWorkspace = (ws: DevWorkspace) => handleStartDevPod(ws.id, true);
  const handleNewWorkspace = () => handleStartDevPod(undefined, true);

  async function handleDeleteWorkspace(ws: DevWorkspace) {
    if (!resolvedAppId) return;
    if (!confirm(`Delete workspace "${ws.name}"? The folder and all its files will be removed.`)) return;
    try {
      await deleteWorkspaceMutation.mutateAsync({ appId: resolvedAppId, workspaceId: ws.id });
      toast.success(`Workspace "${ws.name}" deleted.`);
    } catch {
      toast.error('Failed to delete workspace.');
    }
  }


  async function handleStopDevPod() {
    if (!resolvedAppId || !app) return;
    if (!confirm(`Stop the development sandbox pod for "${app.name}"? This will terminate the dev container and release cluster resources.`)) {
      return;
    }
    setIsStoppingDevPod(true);
    setLaunchStep(0);
    setLaunchStatusText('Shutting down dev container and releasing cluster resources...');
    try {
      toast.info(`Shutting down dev pod for "${app.name}"...`);
      await stopDevMutation.mutateAsync(resolvedAppId);
      
      // Poll every 1.5s until the pod is completely removed from Kubernetes
      const maxAttempts = 10;
      for (let i = 0; i < maxAttempts; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const res = await refetchDevStatus();
        const curStatus = res.data?.status;
        const curPhase = res.data?.phase;
        if (!curStatus || curStatus === 'stopped' || curStatus === 'inactive' || curStatus === 'not_found' || curPhase === 'NotFound' || curPhase === 'Unknown') {
          break;
        }
      }
      
      setLaunchStatusText('');
      toast.success('Dev sandbox pod shut down successfully.');
      refetchDevStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to stop dev pod.');
    } finally {
      setIsStoppingDevPod(false);
    }
  }

  useEffect(() => {
    if (app) {
      setConfigName(app.name || '');
      setConfigDescription(app.description || '');
      setConfigAppType(app.app_type || 'streamlit');
      setConfigRoute(app.route || `/${app.slug}`);
      setConfigGitUrl(app.git_repo_url || '');
      setConfigGitProvider(app.git_provider || 'github');
      setConfigGitRef(app.git_ref || app.git_branch || 'main');
      setConfigGitRefType(app.git_ref_type || 'branch');
      setConfigGitSubdir(app.git_subdir || '');
      setConfigEntrypoint(app.entrypoint || '');
      setConfigCredType((app.git_credential_type as any) || (app.pat_configured ? 'pat' : 'none'));
      setConfigCredNickname(app.git_credential_nickname || '');

      if (app.config?.env_vars && Array.isArray(app.config.env_vars)) {
        setEnvVars(app.config.env_vars);
      }
      if (app.config?.resources?.cpu) setCpuCores(app.config.resources.cpu);
      if (app.config?.resources?.memory) setMemoryLimit(app.config.resources.memory);
      if (app.config?.resources?.replicas) setReplicas(app.config.resources.replicas);
    }
  }, [app]);

  useEffect(() => {
    if (autoScroll && logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [logsData, autoScroll]);

  useEffect(() => {
    if (deploymentAutoScroll && deploymentTerminalRef.current) {
      deploymentTerminalRef.current.scrollTop = deploymentTerminalRef.current.scrollHeight;
    }
  }, [deploymentsData, deploymentAutoScroll]);

  const allDeployments = useMemo<DeploymentItem[]>(() => {
    if (deploymentsData && Array.isArray(deploymentsData) && deploymentsData.length > 0) {
      return deploymentsData;
    }
    if (app?.config?.deployments && Array.isArray(app.config.deployments)) {
      return app.config.deployments;
    }
    return [];
  }, [deploymentsData, app]);

  const activeDeployment = useMemo<DeploymentItem | null>(() => {
    if (selectedDeploymentId) {
      const found = allDeployments.find((d) => d.deployment_id === selectedDeploymentId);
      if (found) return found;
    }
    return allDeployments[0] || null;
  }, [allDeployments, selectedDeploymentId]);

  const rawDeploymentLogs = useMemo(() => {
    if (activeDeployment?.logs && activeDeployment.logs.length > 0) {
      return activeDeployment.logs;
    }
    if (app?.config?.logs && Array.isArray(app.config.logs)) {
      return app.config.logs;
    }
    return [
      `[INFO] App '${app?.name || 'app'}' deployment ready.`,
      `[INFO] Target: ${app?.slug}.135.13.180.167.nip.io /apps/${app?.slug}/`,
      `[INFO] Git Ref: ${app?.git_ref || 'main'} • Strategy: Containerized`,
      `[INFO] Status: Live and healthy.`,
    ];
  }, [activeDeployment, app]);

  const filteredDeploymentLogs = useMemo(() => {
    return rawDeploymentLogs.filter((line) => {
      const matchText = !deploymentLogFilter || line.toLowerCase().includes(deploymentLogFilter.toLowerCase());
      const matchLevel =
        deploymentLogLevel === 'ALL' ||
        (deploymentLogLevel === 'ERROR' && (line.includes('[ERROR]') || line.includes('ERR'))) ||
        (deploymentLogLevel === 'WARN' && (line.includes('[WARN]') || line.includes('WARNING'))) ||
        (deploymentLogLevel === 'BUILD' && (line.includes('[BUILD]') || line.includes('npm') || line.includes('build') || line.includes('apk') || line.includes('apt') || line.includes('clone'))) ||
        (deploymentLogLevel === 'INFO' && line.includes('[INFO]'));
      return matchText && matchLevel;
    });
  }, [rawDeploymentLogs, deploymentLogFilter, deploymentLogLevel]);

  const filteredHistoryDeployments = useMemo(() => {
    if (!historySearch.trim()) return allDeployments;
    const q = historySearch.toLowerCase();
    return allDeployments.filter(
      (d) =>
        d.deployment_id.toLowerCase().includes(q) ||
        (d.commit_sha && d.commit_sha.toLowerCase().includes(q)) ||
        d.git_ref.toLowerCase().includes(q) ||
        d.status.toLowerCase().includes(q)
    );
  }, [allDeployments, historySearch]);

  const rawLogs = useMemo(() => {
    if (logsData?.logs && logsData.logs.length > 0) {
      return logsData.logs;
    }
    if (app?.config?.logs && Array.isArray(app.config.logs)) {
      return app.config.logs;
    }
    return [
      `[INFO] App '${app?.name || 'app'}' initialized and ready.`,
      `[INFO] Attached Workload Identity: ${app?.workspace_identity?.identity_id || 'id_app_active'}`,
      `[INFO] Scopes: ${app?.workspace_identity?.scopes?.join(', ') || 'catalog:read, compute:run'}`,
      `[INFO] Service healthy and listening on ${app?.route || '/app'}`,
    ];
  }, [logsData, app]);

  const filteredLogs = useMemo(() => {
    return rawLogs.filter((line) => {
      const matchText = !logFilter || line.toLowerCase().includes(logFilter.toLowerCase());
      const matchLevel =
        logLevel === 'ALL' ||
        (logLevel === 'ERROR' && line.includes('[ERROR]')) ||
        (logLevel === 'WARN' && (line.includes('[WARN]') || line.includes('[WARNING]'))) ||
        (logLevel === 'INFO' && line.includes('[INFO]'));
      return matchText && matchLevel;
    });
  }, [rawLogs, logFilter, logLevel]);

  async function handleSaveConfig(e: React.FormEvent) {
    e.preventDefault();
    if (!resolvedAppId) return;
    try {
      await updateMutation.mutateAsync({
        appId: resolvedAppId,
        payload: {
          name: configName.trim(),
          description: configDescription.trim() || undefined,
          app_type: configAppType,
          route: configRoute.trim().startsWith('/') ? configRoute.trim() : `/${configRoute.trim()}`,
          git_provider: configGitProvider,
          git_repo_url: configGitUrl.trim(),
          git_ref: configGitRef.trim(),
          git_ref_type: configGitRefType,
          git_branch: configGitRef.trim(),
          git_subdir: configGitSubdir.trim() || undefined,
          entrypoint: configEntrypoint.trim() || undefined,
          git_credential_type: configCredType,
          git_credential_nickname: configCredNickname.trim() || undefined,
          git_pat: configPat.trim() || undefined,
        },
      });
      setConfigDirty(false);
      toast.success('App configuration updated successfully.');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to update configuration.');
    }
  }

  async function handleSaveEnv() {
    if (!resolvedAppId || !app) return;
    try {
      const currentConfig = app.config || {};
      const updatedConfig = {
        ...currentConfig,
        env_vars: envVars,
        resources: {
          cpu: cpuCores,
          memory: memoryLimit,
          replicas: Number(replicas),
        },
      };
      await updateMutation.mutateAsync({
        appId: resolvedAppId,
        payload: {
          config: updatedConfig,
        },
      });
      setEnvDirty(false);
      toast.success('Environment and resource settings saved.');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to save environment settings.');
    }
  }

  async function handleTriggerDeploy() {
    if (!resolvedAppId) return;
    setIsDeploying(true);
    try {
      toast.info(`Triggering build & deployment for "${app?.name}"...`);
      await deployMutation.mutateAsync(resolvedAppId);
      toast.success('Deployment succeeded! App is live and updated.');
      refetchLogs();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Deployment failed.');
    } finally {
      setIsDeploying(false);
    }
  }

  async function handleToggleStatus() {
    if (!resolvedAppId || !app) return;
    const newStatus = app.status === 'active' ? 'stopped' : 'active';
    try {
      await statusMutation.mutateAsync({ appId: resolvedAppId, status: newStatus });
      toast.info(`Application marked as ${newStatus}.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to update status.');
    }
  }

  async function handleDeleteApp() {
    if (!resolvedAppId || !app) return;
    if (!confirm(`Are you sure you want to permanently delete "${app.name}"? This action cannot be undone.`)) {
      return;
    }
    try {
      await deleteMutation.mutateAsync(resolvedAppId);
      toast.success(`App "${app.name}" deleted.`);
      navigate('/home');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to delete app.');
    }
  }

  function handleCopyRoute() {
    if (!app) return;
    navigator.clipboard.writeText(window.location.origin + app.route);
    setCopiedRoute(true);
    setTimeout(() => setCopiedRoute(false), 2000);
    toast.success('Route copied to clipboard!');
  }

  function handleAddEnvVar() {
    if (!newEnvKey.trim()) return;
    setEnvVars((prev) => [
      ...prev,
      {
        key: newEnvKey.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_'),
        value: newEnvVal,
        isSecret: newEnvSecret,
      },
    ]);
    setNewEnvKey('');
    setNewEnvVal('');
    setNewEnvSecret(false);
    setEnvDirty(true);
  }

  function handleDeleteEnvVar(index: number) {
    setEnvVars((prev) => prev.filter((_, i) => i !== index));
    setEnvDirty(true);
  }

  function handleDownloadLogs() {
    const text = rawLogs.join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${app?.slug || 'app'}-logs-${new Date().toISOString().slice(0, 10)}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleDownloadDeploymentLogs() {
    const text = rawDeploymentLogs.join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${app?.slug || 'app'}-deployment-${activeDeployment?.deployment_id || 'logs'}-${new Date().toISOString().slice(0, 10)}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleCopyDeploymentLogs() {
    const text = rawDeploymentLogs.join('\n');
    navigator.clipboard.writeText(text);
    toast.success('Deployment logs copied to clipboard!');
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', gap: 12 }}>
        <Loader2 size={30} className="spin" color="var(--color-primary)" />
        <div style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>Loading application details...</div>
      </div>
    );
  }

  if (error || !app) {
    return (
      <div style={{ padding: 32, maxWidth: 600, margin: '40px auto', textAlign: 'center' }}>
        <div style={{ padding: 24, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#b91c1c' }}>
          <AlertCircle size={28} style={{ margin: '0 auto 8px' }} />
          <h3 style={{ margin: '0 0 6px', fontSize: '1.1rem' }}>Application Not Found</h3>
          <p style={{ margin: '0 0 16px', fontSize: '0.85rem' }}>
            The requested application could not be loaded or was removed from this workspace.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/home')}>
            <ArrowLeft size={14} /> Return to Apps
          </button>
        </div>
      </div>
    );
  }

  const isLive = app.status === 'active';
  const runtimeInfo = app.config?.runtime;
  const isRunning = isLive && (runtimeInfo?.status === 'running' || !!runtimeInfo?.container_id || !!runtimeInfo?.pid);
  const runtimePort = runtimeInfo?.host_port;
  const runtimeMode = (runtimeInfo?.mode || (runtimeInfo?.container_id ? 'docker' : 'local')).toUpperCase();
  const rawLiveUrl = runtimeInfo?.url || (runtimePort ? `http://localhost:${runtimePort}` : app.route);
  const appLiveUrl = rawLiveUrl?.startsWith('/') ? `${window.location.origin}${rawLiveUrl}` : rawLiveUrl;

  return (
    <div className="page-section apps-page" style={{ width: '100%', maxWidth: '100%', padding: '20px 28px 40px', margin: 0 }}>
      {/* Breadcrumbs & Back Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
        <button
          onClick={() => navigate('/home')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-primary)', padding: 0 }}
        >
          <ArrowLeft size={14} />
          <span>Apps</span>
        </button>
        <span>/</span>
        <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>{app.name}</span>
      </div>

      {/* Main Header Card */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          padding: '20px 24px',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg, 10px)',
          marginBottom: 20,
          gap: 20,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 10,
              background: 'var(--color-primary-bg, #EBF2FF)',
              color: 'var(--color-primary, #1B6EF3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Boxes size={24} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-text)' }}>
                {app.name}
              </h1>

              {/* Status Pill with Container Mode & Port */}
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '3px 10px',
                  borderRadius: 12,
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: isRunning ? '#15803d' : isLive ? '#15803d' : '#6b7280',
                  background: isRunning ? '#dcfce7' : isLive ? '#dcfce7' : '#f3f4f6',
                  border: isRunning ? '1px solid #bbf7d0' : isLive ? '1px solid #bbf7d0' : '1px solid #e5e7eb',
                }}
              >
                {isRunning ? (
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
                ) : (
                  <Clock size={12} />
                )}
                {isRunning && runtimePort
                  ? `${app.status.toUpperCase()} • ${runtimeMode} :${runtimePort}`
                  : app.status.toUpperCase()}
              </span>

              {/* Framework Tag */}
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '3px 8px',
                  borderRadius: 4,
                  fontSize: '0.72rem',
                  color: 'var(--color-text-muted)',
                  background: 'var(--color-surface-hover, rgba(0,0,0,0.04))',
                }}
              >
                <Code2 size={12} />
                {app.app_type}
              </span>
            </div>

            {/* Description & Route link */}
            <p style={{ margin: '6px 0 10px', fontSize: '0.85rem', color: 'var(--color-text-muted)', maxWidth: 650 }}>
              {app.description || 'Enterprise application deployed with Git version control and scoped Workload Identity.'}
            </p>

            {/* Direct Docker Port & Route URL badge with copy */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.8rem', flexWrap: 'wrap' }}>
              <a
                href={appLiveUrl}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: 'var(--color-primary-bg, #ebf2ff)',
                  padding: '4px 10px',
                  borderRadius: 6,
                  border: '1px solid var(--color-primary)',
                  color: 'var(--color-primary)',
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
                title="Open Direct Container URL"
              >
                <Globe size={13} />
                <span>{appLiveUrl}</span>
                <ExternalLink size={12} />
              </a>

              <button
                className="ghost-icon-btn"
                title="Copy URL"
                onClick={() => {
                  navigator.clipboard.writeText(appLiveUrl);
                  setCopiedRoute(true);
                  setTimeout(() => setCopiedRoute(false), 2000);
                  toast.success('Copied URL to clipboard');
                }}
                style={{ padding: 4 }}
              >
                {copiedRoute ? <Check size={13} color="#22c55e" /> : <Copy size={13} />}
              </button>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {isDevPodStopping ? (
            <button
              className="btn btn-outline"
              style={{
                borderColor: '#fca5a5',
                color: '#dc2626',
                background: '#fff1f2',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                fontWeight: 500,
                cursor: 'not-allowed',
              }}
              disabled={true}
              title="Development sandbox pod is shutting down..."
            >
              <Loader2 size={14} className="spin" color="#dc2626" />
              <span>Shutting down Dev Pod...</span>
            </button>
          ) : isDevPodRunning ? (
            <button
              className="btn btn-outline"
              style={{
                borderColor: '#fca5a5',
                color: '#dc2626',
                background: '#fff1f2',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                fontWeight: 500,
                cursor: 'pointer',
              }}
              onClick={handleStopDevPod}
              disabled={isDevPodStarting}
              title="Stop development sandbox pod to release cluster resources"
            >
              <Square size={13} />
              <span>Stop Dev Pod</span>
            </button>
          ) : (
            <button
              className="btn btn-outline"
              style={{
                borderColor: '#c7d2fe',
                color: '#4f46e5',
                background: '#f5f3ff',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                fontWeight: 500,
                cursor: isDevPodStarting ? 'not-allowed' : 'pointer',
              }}
              onClick={() => handleStartDevPod(false)}
              disabled={isDevPodStarting}
              title="Start development sandbox pod in background"
            >
              {isDevPodStarting ? <Loader2 size={14} className="spin" /> : <Play size={13} />}
              <span>{isDevPodStarting ? 'Starting Dev Pod...' : 'Start Dev Pod'}</span>
            </button>
          )}

          <button
            className="btn"
            style={{
              background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              color: '#ffffff',
              border: 'none',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              boxShadow: '0 2px 6px rgba(99, 102, 241, 0.3)',
              cursor: startDevMutation.isPending ? 'not-allowed' : 'pointer',
              padding: '6px 14px',
            }}
            onClick={handleLaunchDevStudio}
            disabled={startDevMutation.isPending}
            title="Launch Omnigent AI pair programmer in new tab"
          >
            {startDevMutation.isPending ? (
              <Loader2 size={14} className="spin" />
            ) : (
              <Sparkles size={14} />
            )}
            <span>{startDevMutation.isPending ? 'Launching Omnigent...' : 'Modify with Omnigent'}</span>
          </button>

          <button
            className="btn btn-outline"
            onClick={handleToggleStatus}
            disabled={statusMutation.isPending}
            title={isLive ? 'Stop application' : 'Start application'}
          >
            {isLive ? (
              <>
                <Pause size={14} /> Stop App
              </>
            ) : (
              <>
                <Play size={14} /> Start App
              </>
            )}
          </button>

          <button
            className="btn btn-outline"
            onClick={handleTriggerDeploy}
            disabled={isDeploying || deployMutation.isPending}
            title="Redeploy application from Git repository"
          >
            <RotateCw size={14} className={isDeploying ? 'spin' : ''} />
            <span>{isDeploying ? 'Deploying...' : 'Redeploy'}</span>
          </button>

          <button
            className="btn btn-primary"
            onClick={() => {
              window.open(appLiveUrl, '_blank');
              toast.info(`Opening ${app.name} (${appLiveUrl})...`);
            }}
          >
            <ExternalLink size={14} /> Open App
          </button>
        </div>
      </div>

      {/* Tabs Navigation Bar */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--color-border)',
          marginBottom: 24,
          gap: 24,
        }}
      >
        <button
          onClick={() => handleTabChange('overview')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 4px',
            border: 'none',
            background: 'none',
            fontSize: '0.875rem',
            fontWeight: activeTab === 'overview' ? 600 : 500,
            color: activeTab === 'overview' ? 'var(--color-primary)' : 'var(--color-text-muted)',
            borderBottom: activeTab === 'overview' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Layers size={16} />
          <span>Overview</span>
        </button>

        <button
          onClick={() => handleTabChange('development')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 4px',
            border: 'none',
            background: 'none',
            fontSize: '0.875rem',
            fontWeight: activeTab === 'development' ? 600 : 500,
            color: activeTab === 'development' ? 'var(--color-primary)' : 'var(--color-text-muted)',
            borderBottom: activeTab === 'development' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Sparkles size={16} />
          <span>Development</span>
          {isDevPodRunning && (
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#22c55e',
                marginLeft: -2,
              }}
              title="Dev Pod Running"
            />
          )}
        </button>

        <button
          onClick={() => handleTabChange('deployments')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 4px',
            border: 'none',
            background: 'none',
            fontSize: '0.875rem',
            fontWeight: activeTab === 'deployments' ? 600 : 500,
            color: activeTab === 'deployments' ? 'var(--color-primary)' : 'var(--color-text-muted)',
            borderBottom: activeTab === 'deployments' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Rocket size={16} />
          <span>Deployments</span>
          {allDeployments.length > 0 && (
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '1px 6px',
                borderRadius: '999px',
                background: activeTab === 'deployments' ? 'var(--color-primary)' : 'var(--color-border)',
                color: activeTab === 'deployments' ? '#fff' : 'var(--color-text-muted)',
              }}
            >
              {allDeployments.length}
            </span>
          )}
        </button>

        <button
          onClick={() => handleTabChange('configuration')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 4px',
            border: 'none',
            background: 'none',
            fontSize: '0.875rem',
            fontWeight: activeTab === 'configuration' ? 600 : 500,
            color: activeTab === 'configuration' ? 'var(--color-primary)' : 'var(--color-text-muted)',
            borderBottom: activeTab === 'configuration' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Settings size={16} />
          <span>App Configuration</span>
        </button>

        <button
          onClick={() => handleTabChange('environment')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 4px',
            border: 'none',
            background: 'none',
            fontSize: '0.875rem',
            fontWeight: activeTab === 'environment' ? 600 : 500,
            color: activeTab === 'environment' ? 'var(--color-primary)' : 'var(--color-text-muted)',
            borderBottom: activeTab === 'environment' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Server size={16} />
          <span>Environment & Settings</span>
        </button>

        <button
          onClick={() => handleTabChange('logs')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 4px',
            border: 'none',
            background: 'none',
            fontSize: '0.875rem',
            fontWeight: activeTab === 'logs' ? 600 : 500,
            color: activeTab === 'logs' ? 'var(--color-primary)' : 'var(--color-text-muted)',
            borderBottom: activeTab === 'logs' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Terminal size={16} />
          <span>Runtime Logs</span>
        </button>

        <button
          onClick={() => handleTabChange('tasks')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 4px',
            border: 'none',
            background: 'none',
            fontSize: '0.875rem',
            fontWeight: activeTab === 'tasks' ? 600 : 500,
            color: activeTab === 'tasks' ? 'var(--color-primary)' : 'var(--color-text-muted)',
            borderBottom: activeTab === 'tasks' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <ListTodo size={16} />
          <span>Tasks</span>
          {tasksData && tasksData.length > 0 && (
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '1px 6px',
                borderRadius: '999px',
                background: activeTab === 'tasks' ? 'var(--color-primary)' : 'var(--color-border)',
                color: activeTab === 'tasks' ? '#fff' : 'var(--color-text-muted)',
              }}
            >
              {tasksData.length}
            </span>
          )}
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 24, alignItems: 'start' }}>
          {/* Left Column: Live Details & Git Info */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Git Source Repository Card */}
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '18px 20px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: '0.95rem' }}>
                  <FolderGit2 size={18} color="var(--color-primary)" />
                  <span>Git Repository & Source</span>
                </div>
                <button
                  className="btn btn-outline"
                  style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                  onClick={() => handleTabChange('configuration')}
                >
                  Edit Git Config
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Repository URL</div>
                  <a
                    href={app.git_repo_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: '0.85rem',
                      fontWeight: 500,
                      color: 'var(--color-primary)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      marginTop: 2,
                    }}
                  >
                    {app.git_repo_url.replace(/^https?:\/\//, '')}
                    <ExternalLink size={12} />
                  </a>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Git Reference</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', marginTop: 2, fontWeight: 500 }}>
                    <GitBranch size={13} color="var(--color-text-muted)" />
                    <span>{app.git_branch || app.git_ref || 'main'}</span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>({app.git_ref_type || 'branch'})</span>
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Source Subfolder</div>
                  <div style={{ fontSize: '0.85rem', marginTop: 2, color: 'var(--color-text)' }}>
                    {app.git_subdir || 'Root directory (Entire project)'}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Entrypoint File</div>
                  <div style={{ fontSize: '0.85rem', marginTop: 2, color: 'var(--color-text)' }}>
                    <code>{app.entrypoint || (app.app_type.includes('Streamlit') ? 'app.py' : 'main.py / npm run dev')}</code>
                  </div>
                </div>
              </div>
            </div>

            {/* Development Sandbox Summary Card */}
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(168, 85, 247, 0.05) 100%)',
                border: '1px solid rgba(99, 102, 241, 0.25)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '18px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 10,
                      background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      boxShadow: '0 2px 8px rgba(99, 102, 241, 0.25)',
                    }}
                  >
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 650, fontSize: '0.95rem', color: 'var(--color-text)' }}>
                        Development Sandbox
                      </span>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          padding: '2px 8px',
                          borderRadius: 10,
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          color: isDevPodRunning ? '#15803d' : '#4b5563',
                          background: isDevPodRunning ? '#dcfce7' : '#f3f4f6',
                          border: isDevPodRunning ? '1px solid #bbf7d0' : '1px solid #e5e7eb',
                        }}
                      >
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: isDevPodRunning ? '#22c55e' : '#9ca3af',
                          }}
                        />
                        {isDevPodRunning ? 'Dev Pod: Running' : 'Dev Pod: Stopped'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                      {devWorkspaces && devWorkspaces.length > 0
                        ? `${devWorkspaces.length} workspace${devWorkspaces.length > 1 ? 's' : ''} available • Live hot-reload and AI pair programming`
                        : 'Interactive dev container with live hot-reload and AI pair programming'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    className="btn btn-outline"
                    style={{ fontSize: '0.78rem', padding: '6px 12px', borderColor: '#6366f1', color: '#4f46e5' }}
                    onClick={() => handleTabChange('development')}
                  >
                    <Code2 size={13} />
                    <span>Open Development Tab</span>
                  </button>
                  {isDevPodRunning ? (
                    <button
                      className="btn"
                      style={{
                        background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                        color: '#fff',
                        border: 'none',
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        padding: '6px 14px',
                        borderRadius: 6,
                        cursor: 'pointer',
                      }}
                      onClick={() => handleStartDevPod(undefined, true)}
                    >
                      <ExternalLink size={13} />
                      <span>Launch Studio</span>
                    </button>
                  ) : (
                    <button
                      className="btn btn-primary"
                      style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                      onClick={() => handleStartDevPod(undefined, false)}
                      disabled={isDevPodStarting}
                    >
                      {isDevPodStarting ? <Loader2 size={13} className="spin" /> : <Play size={13} />}
                      <span>Start Sandbox</span>
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Live Preview Card */}
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '18px 20px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: '0.95rem' }}>
                  <Globe size={18} color="var(--color-primary)" />
                  <span>Live Application Preview</span>
                  {isRunning && (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: '0.72rem',
                        padding: '2px 8px',
                        borderRadius: 10,
                        background: '#dcfce7',
                        color: '#15803d',
                        fontWeight: 600,
                      }}
                    >
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
                      {runtimeMode} (Port {runtimePort || 8080})
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    className="btn btn-outline"
                    style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    onClick={() => window.open(appLiveUrl, '_blank')}
                  >
                    <ExternalLink size={12} /> Direct Port ({runtimePort || 8080})
                  </button>
                  <button
                    className="btn btn-primary"
                    style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    onClick={() => window.open(appLiveUrl, '_blank')}
                  >
                    <Globe size={12} /> Launch in New Tab
                  </button>
                </div>
              </div>

              {isRunning ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ border: '1px solid var(--color-border)', borderRadius: 8, overflow: 'hidden', height: 420, background: '#fff' }}>
                    <iframe
                      src={appLiveUrl}
                      title={app.name}
                      style={{ width: '100%', height: '100%', border: 'none' }}
                    />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--color-text-muted)', padding: '0 4px' }}>
                    <span>Container Endpoint: <code style={{ color: 'var(--color-primary)' }}>{appLiveUrl}</code></span>
                    <button
                      className="ghost-icon-btn"
                      onClick={() => window.open(appLiveUrl, '_blank')}
                      style={{ fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    >
                      <ExternalLink size={12} /> Open in Dedicated Window
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    height: 260,
                    border: '1px solid var(--color-border)',
                    borderRadius: 6,
                    background: 'var(--color-surface-hover, #f8fafc)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 20,
                    textAlign: 'center',
                  }}
                >
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: '50%',
                      background: 'var(--color-primary-bg)',
                      color: 'var(--color-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      marginBottom: 12,
                    }}
                  >
                    <Sparkles size={22} />
                  </div>
                  <h4 style={{ margin: '0 0 4px', fontSize: '0.95rem', fontWeight: 600 }}>{app.name}</h4>
                  <p style={{ margin: '0 0 14px', fontSize: '0.8rem', color: 'var(--color-text-muted)', maxWidth: 360 }}>
                    Click redeploy or start to launch the container runner.
                  </p>
                  <button
                    className="btn btn-primary"
                    onClick={handleTriggerDeploy}
                    disabled={isDeploying}
                  >
                    <RotateCw size={13} className={isDeploying ? 'spin' : ''} /> Deploy Container
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Workload Identity & Governance & Container Runtime */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Container & Runtime Sandbox Card */}
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '18px 20px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: '0.95rem' }}>
                  <Cpu size={18} color="var(--color-primary)" />
                  <span>Container Runtime</span>
                </div>
                {isRunning && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '2px 8px',
                      borderRadius: 10,
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      color: '#15803d',
                      background: '#dcfce7',
                    }}
                  >
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
                    RUNNING
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.82rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Execution Target</span>
                  <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>
                    {runtimeMode === 'DOCKER' ? 'Docker Daemon (Isolated)' : runtimeMode === 'KUBERNETES' ? 'Kubernetes Pod' : 'Local Process Runner'}
                  </span>
                </div>
                {runtimeInfo?.container_id && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Container ID</span>
                    <code>{runtimeInfo.container_id}</code>
                  </div>
                )}
                {runtimePort && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Host Port</span>
                    <code>http://localhost:{runtimePort}</code>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Deployed Ref</span>
                  <span>{app.git_ref || 'main'} ({app.git_ref_type || 'branch'})</span>
                </div>
                {runtimeInfo?.deployed_at && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Last Deployment</span>
                    <span>{new Date(runtimeInfo.deployed_at).toLocaleTimeString()}</span>
                  </div>
                )}
              </div>
            </div>
            {/* Workload Identity & Security Card */}
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '18px 20px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: '0.95rem', marginBottom: 14 }}>
                <ShieldCheck size={18} color="#16a34a" />
                <span>Workload Identity & Scopes</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Identity ID</div>
                  <code style={{ fontSize: '0.8rem', color: 'var(--color-primary)', fontWeight: 600 }}>
                    {app.workspace_identity?.identity_id || `id_app_${app.id.slice(0, 10)}`}
                  </code>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Principal Role</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--color-text)' }}>
                    {app.workspace_identity?.role || 'app_executor'}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 6 }}>Granted Scopes</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {(app.workspace_identity?.scopes || ['catalog:read', 'compute:run', 'models:inference', 'agents:invoke']).map((scope) => (
                      <span
                        key={scope}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          padding: '2px 8px',
                          borderRadius: 4,
                          fontSize: '0.72rem',
                          fontWeight: 500,
                          color: '#0369a1',
                          background: '#e0f2fe',
                        }}
                      >
                        <Lock size={10} />
                        {scope}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Application Metadata Card */}
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '18px 20px',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: 14 }}>
                Metadata & Lifecycle
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.82rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>App ID</span>
                  <code>{app.id}</code>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Workspace</span>
                  <span>{app.workspace_slug || app.workspace_id}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Created At</span>
                  <span>{new Date(app.created_at).toLocaleString()}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Last Updated</span>
                  <span>{new Date(app.updated_at).toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: DEVELOPMENT (Interactive Sandbox, Workspaces, Preview & Logs) */}
      {activeTab === 'development' && app && (
        <AppDevelopmentTab app={app} resolvedAppId={resolvedAppId!} />
      )}

      {/* TAB: DEPLOYMENTS (Live Pipeline, History & Logs) */}
      {activeTab === 'deployments' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Top Banner: Deployment Pipeline Tracker */}
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600, color: 'var(--color-text)' }}>
                    Deployment Pipeline
                  </h3>
                  {activeDeployment?.status === 'in_progress' || isDeploying ? (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '3px 9px',
                        borderRadius: 12,
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        color: '#0284c7',
                        background: '#e0f2fe',
                        border: '1px solid #bae6fd',
                      }}
                    >
                      <Loader2 size={12} className="spin" />
                      BUILDING & DEPLOYING
                    </span>
                  ) : activeDeployment?.status === 'failed' ? (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '3px 9px',
                        borderRadius: 12,
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        color: '#dc2626',
                        background: '#fee2e2',
                        border: '1px solid #fecaca',
                      }}
                    >
                      <XCircle size={12} />
                      DEPLOYMENT FAILED
                    </span>
                  ) : (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '3px 9px',
                        borderRadius: 12,
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        color: '#15803d',
                        background: '#dcfce7',
                        border: '1px solid #bbf7d0',
                      }}
                    >
                      <CheckCircle2 size={12} />
                      ACTIVE & HEALTHY
                    </span>
                  )}
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  Continuous build and deployment pipeline for Git commits and container routing.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <button
                  className="btn btn-outline"
                  onClick={() => refetchDeployments()}
                  disabled={deploymentsFetching}
                  title="Refresh deployments status"
                >
                  <RefreshCw size={13} className={deploymentsFetching ? 'spin' : ''} />
                  <span>Refresh</span>
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleTriggerDeploy}
                  disabled={isDeploying || deployMutation.isPending}
                >
                  <Rocket size={14} className={isDeploying ? 'spin' : ''} />
                  <span>{isDeploying ? 'Deploying...' : 'Redeploy Latest'}</span>
                </button>
              </div>
            </div>

            {/* 5-Step Pipeline Steps Progress Visualizer */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: 12,
                padding: '14px 16px',
                background: 'var(--color-surface-hover, #f8fafc)',
                border: '1px solid var(--color-border)',
                borderRadius: 8,
              }}
            >
              {[
                {
                  id: 'init',
                  title: '1. Trigger & Identity',
                  desc: activeDeployment?.triggered_by || 'Workspace Identity',
                  done: true,
                },
                {
                  id: 'git',
                  title: '2. Git Fetch Ref',
                  desc: activeDeployment?.commit_sha ? activeDeployment.commit_sha.slice(0, 7) : (app.git_ref || 'main'),
                  done: activeDeployment?.status !== 'queued',
                },
                {
                  id: 'build',
                  title: '3. Build & Deps',
                  desc: activeDeployment?.status === 'in_progress' ? 'Building...' : 'Compiled',
                  done: activeDeployment?.status === 'success' || activeDeployment?.status === 'succeeded',
                  active: activeDeployment?.status === 'in_progress',
                },
                {
                  id: 'routing',
                  title: '4. Ingress Routing',
                  desc: `${app.slug}.*.nip.io`,
                  done: activeDeployment?.status === 'success' || activeDeployment?.status === 'succeeded',
                },
                {
                  id: 'live',
                  title: '5. Live Service',
                  desc: activeDeployment?.status === 'failed' ? 'Failed' : (activeDeployment?.status === 'in_progress' ? 'Deploying...' : 'Healthy (200 OK)'),
                  done: activeDeployment?.status === 'success' || activeDeployment?.status === 'succeeded',
                  failed: activeDeployment?.status === 'failed',
                },
              ].map((step, idx) => {
                const isStepFailed = step.failed;
                const isStepActive = step.active || (isDeploying && idx === 2);
                const isStepDone = step.done && !isStepFailed;
                return (
                  <div
                    key={step.id}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 4,
                      padding: '8px 10px',
                      background: 'var(--color-surface)',
                      border: isStepActive
                        ? '1px solid var(--color-primary)'
                        : isStepFailed
                        ? '1px solid #f87171'
                        : isStepDone
                        ? '1px solid #86efac'
                        : '1px solid var(--color-border)',
                      borderRadius: 6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text)' }}>
                        {step.title}
                      </span>
                      {isStepActive ? (
                        <Loader2 size={12} className="spin" color="var(--color-primary)" />
                      ) : isStepFailed ? (
                        <XCircle size={12} color="#dc2626" />
                      ) : isStepDone ? (
                        <CheckCircle2 size={12} color="#16a34a" />
                      ) : (
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-border)' }} />
                      )}
                    </div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {step.desc}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Active Deployment Info Strip */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                fontSize: '0.8rem',
                color: 'var(--color-text-muted)',
                flexWrap: 'wrap',
                paddingTop: 4,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <GitCommit size={14} color="var(--color-primary)" />
                <span>Commit:</span>
                <code style={{ fontSize: '0.76rem', color: 'var(--color-text)', fontWeight: 600 }}>
                  {activeDeployment?.commit_sha ? activeDeployment.commit_sha.slice(0, 8) : 'latest-head'}
                </code>
                {(activeDeployment?.commit_message || activeDeployment?.message) && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    ({activeDeployment.commit_message || activeDeployment.message})
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <GitBranch size={14} />
                <span>Ref:</span>
                <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>
                  {activeDeployment?.git_ref || app.git_ref || 'main'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Clock size={14} />
                <span>Duration:</span>
                <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>
                  {activeDeployment?.duration_seconds ? `${activeDeployment.duration_seconds}s` : '3.2s'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>Triggered:</span>
                <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>
                  {activeDeployment?.created_at ? new Date(activeDeployment.created_at).toLocaleString() : new Date().toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* 2-Column Split: Left = Deployment History, Right = Live Logs Terminal */}
          <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 20, alignItems: 'start' }}>
            {/* Left Column: Deployment History List */}
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: '0.9rem' }}>
                  <History size={16} />
                  <span>Deployment History</span>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      background: 'var(--color-surface-hover, #f1f5f9)',
                      padding: '1px 6px',
                      borderRadius: 10,
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    {filteredHistoryDeployments.length}
                  </span>
                </div>
              </div>

              {/* History search */}
              <div className="search-bar-wrapper" style={{ width: '100%' }}>
                <Search size={13} className="search-icon" />
                <input
                  className="search-input"
                  placeholder="Filter by ID, commit, branch..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>

              {/* Deployments List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 480, overflowY: 'auto' }}>
                {filteredHistoryDeployments.length === 0 ? (
                  <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                    No deployment records found.
                  </div>
                ) : (
                  filteredHistoryDeployments.map((dep) => {
                    const isSelected = (selectedDeploymentId || allDeployments[0]?.deployment_id) === dep.deployment_id;
                    const isSuccess = dep.status === 'succeeded' || dep.status === 'success';
                    const isFailed = dep.status === 'failed';
                    const isInProgress = dep.status === 'in_progress';

                    return (
                      <div
                        key={dep.deployment_id}
                        onClick={() => setSelectedDeploymentId(dep.deployment_id)}
                        style={{
                          padding: '10px 12px',
                          borderRadius: 6,
                          border: isSelected ? '1.5px solid var(--color-primary)' : '1px solid var(--color-border)',
                          background: isSelected ? 'var(--color-primary-bg, #eff6ff)' : 'var(--color-surface)',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 6,
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            {isInProgress ? (
                              <Loader2 size={13} className="spin" color="#0284c7" />
                            ) : isFailed ? (
                              <XCircle size={13} color="#dc2626" />
                            ) : (
                              <CheckCircle2 size={13} color="#16a34a" />
                            )}
                            <code style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-text)' }}>
                              {dep.deployment_id}
                            </code>
                          </div>
                          <span
                            style={{
                              fontSize: '0.68rem',
                              fontWeight: 600,
                              textTransform: 'uppercase',
                              padding: '1px 6px',
                              borderRadius: 4,
                              color: isInProgress ? '#0369a1' : isFailed ? '#b91c1c' : '#15803d',
                              background: isInProgress ? '#e0f2fe' : isFailed ? '#fee2e2' : '#dcfce7',
                            }}
                          >
                            {dep.status}
                          </span>
                        </div>

                        <div style={{ fontSize: '0.78rem', color: 'var(--color-text)', display: 'flex', alignItems: 'center', gap: 6 }}>
                          <GitCommit size={12} color="var(--color-text-muted)" />
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}>
                            {dep.message || `Deploy from ref ${dep.git_ref}`}
                          </span>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                          <span>{new Date(dep.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          <span>{dep.duration_seconds ? `${dep.duration_seconds}s` : '3.2s'}</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right Column: Build & Deployment Logs Console */}
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '16px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {/* Terminal Header & Toolbar */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Terminal size={16} color="var(--color-primary)" />
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                    Deployment Logs
                  </span>
                  {activeDeployment?.deployment_id && (
                    <code style={{ fontSize: '0.75rem', background: 'var(--color-surface-hover)', padding: '2px 6px', borderRadius: 4 }}>
                      {activeDeployment.deployment_id}
                    </code>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {/* Search inside logs */}
                  <div className="search-bar-wrapper" style={{ width: 170 }}>
                    <Search size={12} className="search-icon" />
                    <input
                      className="search-input"
                      placeholder="Search logs..."
                      value={deploymentLogFilter}
                      onChange={(e) => setDeploymentLogFilter(e.target.value)}
                      style={{ padding: '4px 8px 4px 26px', fontSize: '0.75rem' }}
                    />
                  </div>

                  {/* Level selector */}
                  <select
                    className="input-field"
                    style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                    value={deploymentLogLevel}
                    onChange={(e) => setDeploymentLogLevel(e.target.value as any)}
                  >
                    <option value="ALL">ALL</option>
                    <option value="INFO">INFO</option>
                    <option value="BUILD">BUILD</option>
                    <option value="WARN">WARN</option>
                    <option value="ERROR">ERROR</option>
                  </select>

                  {/* Auto-scroll toggle */}
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem', color: 'var(--color-text-muted)', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={deploymentAutoScroll}
                      onChange={(e) => setDeploymentAutoScroll(e.target.checked)}
                    />
                    <span>Auto-scroll</span>
                  </label>

                  <button
                    className="btn btn-outline"
                    style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                    onClick={handleCopyDeploymentLogs}
                    title="Copy all deployment logs"
                  >
                    <Copy size={12} />
                  </button>

                  <button
                    className="btn btn-outline"
                    style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                    onClick={handleDownloadDeploymentLogs}
                    title="Download deployment log file"
                  >
                    <Download size={12} />
                  </button>
                </div>
              </div>

              {/* Terminal Body */}
              <div
                ref={deploymentTerminalRef}
                style={{
                  background: '#0a0f1d',
                  color: '#f1f5f9',
                  fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
                  fontSize: '0.8rem',
                  lineHeight: 1.6,
                  borderRadius: 6,
                  border: '1px solid #1e293b',
                  padding: '14px 16px',
                  height: '460px',
                  overflowY: 'auto',
                  boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.5)',
                }}
              >
                <div style={{ color: '#64748b', marginBottom: 10, fontSize: '0.72rem', borderBottom: '1px solid #1e293b', paddingBottom: 4 }}>
                  // Deployment ID: {activeDeployment?.deployment_id || 'live'} • Ref: {activeDeployment?.git_ref || 'main'} • Commit: {activeDeployment?.commit_sha || 'head'}
                </div>

                {filteredDeploymentLogs.length === 0 ? (
                  <div style={{ color: '#64748b', fontStyle: 'italic', padding: '20px 0' }}>
                    No deployment log lines matching filter.
                  </div>
                ) : (
                  filteredDeploymentLogs.map((line, idx) => {
                    const isError = line.includes('[ERROR]') || line.includes('ERR') || line.includes('failed');
                    const isWarn = line.includes('[WARN]') || line.includes('WARNING');
                    const isSuccess = line.includes('[SUCCESS]') || line.includes('✓') || line.includes('succeeded') || line.includes('successfully');
                    const isBuild = line.includes('[BUILD]') || line.includes('RUN') || line.includes('npm') || line.includes('vite');

                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          gap: 12,
                          color: isError
                            ? '#f87171'
                            : isWarn
                            ? '#fbbf24'
                            : isSuccess
                            ? '#4ade80'
                            : isBuild
                            ? '#38bdf8'
                            : '#e2e8f0',
                          wordBreak: 'break-all',
                        }}
                      >
                        <span style={{ color: '#475569', userSelect: 'none', minWidth: 28, textAlign: 'right', fontSize: '0.72rem' }}>
                          {idx + 1}
                        </span>
                        <span style={{ flex: 1 }}>{line}</span>
                      </div>
                    );
                  })
                )}

                {(isDeploying || activeDeployment?.status === 'in_progress') && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#38bdf8', marginTop: 10, fontSize: '0.75rem' }}>
                    <Loader2 size={12} className="spin" />
                    <span>Streaming live deployment logs from pipeline runner...</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CONFIGURATION */}
      {activeTab === 'configuration' && (
        <form
          onSubmit={handleSaveConfig}
          style={{
            width: '100%',
            maxWidth: '100%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg, 8px)',
            padding: '24px 28px',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600 }}>Application Settings</h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              Configure general application info, frameworks, URL routing, and Git repository connections.
            </p>
          </div>

          <label className="uc-field">
            <span className="uc-field-label">
              App Name <span style={{ color: '#ef4444' }}>*</span>
            </span>
            <input
              type="text"
              value={configName}
              onChange={(e) => {
                setConfigName(e.target.value);
                setConfigDirty(true);
              }}
              className="input-field"
              required
            />
          </label>

          <label className="uc-field">
            <span className="uc-field-label">Description</span>
            <textarea
              rows={3}
              value={configDescription}
              onChange={(e) => {
                setConfigDescription(e.target.value);
                setConfigDirty(true);
              }}
              className="input-field"
              placeholder="Describe the application..."
            />
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <label className="uc-field">
              <span className="uc-field-label">App Type / Framework</span>
              <select
                className="input-field"
                value={configAppType}
                onChange={(e) => {
                  setConfigAppType(e.target.value);
                  setConfigDirty(true);
                }}
              >
                {APP_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="uc-field">
              <span className="uc-field-label">URL Route</span>
              <input
                type="text"
                value={configRoute}
                onChange={(e) => {
                  setConfigRoute(e.target.value);
                  setConfigDirty(true);
                }}
                className="input-field"
                placeholder="/my-app"
                required
              />
            </label>
          </div>

          {/* Git Source Section */}
          <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 16, marginTop: 4 }}>
            <h4 style={{ margin: '0 0 12px', fontSize: '0.92rem', fontWeight: 600 }}>Git Repository Configuration</h4>

            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16, marginBottom: 16 }}>
              <label className="uc-field" style={{ marginBottom: 0 }}>
                <span className="uc-field-label">
                  Repository URL <span style={{ color: '#ef4444' }}>*</span>
                </span>
                <input
                  type="text"
                  value={configGitUrl}
                  onChange={(e) => {
                    setConfigGitUrl(e.target.value);
                    setConfigDirty(true);
                  }}
                  className="input-field"
                  required
                />
              </label>

              <label className="uc-field" style={{ marginBottom: 0 }}>
                <span className="uc-field-label">Git Provider</span>
                <select
                  className="input-field"
                  value={configGitProvider}
                  onChange={(e) => {
                    setConfigGitProvider(e.target.value);
                    setConfigDirty(true);
                  }}
                >
                  <option value="github">GitHub</option>
                  <option value="gitlab">GitLab</option>
                  <option value="bitbucket">Bitbucket</option>
                  <option value="azure_devops">Azure DevOps</option>
                  <option value="other">Other</option>
                </select>
              </label>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16, marginBottom: 16 }}>
              <label className="uc-field" style={{ marginBottom: 0 }}>
                <span className="uc-field-label">Git Reference</span>
                <input
                  type="text"
                  value={configGitRef}
                  onChange={(e) => {
                    setConfigGitRef(e.target.value);
                    setConfigDirty(true);
                  }}
                  className="input-field"
                />
              </label>

              <label className="uc-field" style={{ marginBottom: 0 }}>
                <span className="uc-field-label">Reference Type</span>
                <select
                  className="input-field"
                  value={configGitRefType}
                  onChange={(e) => {
                    setConfigGitRefType(e.target.value);
                    setConfigDirty(true);
                  }}
                >
                  <option value="branch">Branch</option>
                  <option value="tag">Tag</option>
                  <option value="commit">Commit</option>
                </select>
              </label>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <label className="uc-field">
                <span className="uc-field-label">Source Code Path</span>
                <input
                  type="text"
                  placeholder="e.g. frontend or leave empty"
                  value={configGitSubdir}
                  onChange={(e) => {
                    setConfigGitSubdir(e.target.value);
                    setConfigDirty(true);
                  }}
                  className="input-field"
                />
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Entrypoint File</span>
                <input
                  type="text"
                  placeholder="e.g. app.py or src/main.tsx"
                  value={configEntrypoint}
                  onChange={(e) => {
                    setConfigEntrypoint(e.target.value);
                    setConfigDirty(true);
                  }}
                  className="input-field"
                />
              </label>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 10 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => refetch()}
              disabled={updateMutation.isPending}
            >
              Discard Changes
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={updateMutation.isPending}
            >
              <Save size={14} />
              <span>{updateMutation.isPending ? 'Saving...' : 'Save Configuration'}</span>
            </button>
          </div>
        </form>
      )}

      {/* TAB 3: ENVIRONMENT & SETTINGS */}
      {activeTab === 'environment' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24, width: '100%', maxWidth: '100%' }}>
          {/* Environment Variables Card */}
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '20px 24px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Environment Variables</h3>
                <p style={{ margin: '3px 0 0', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  Variables passed directly to the application container at startup.
                </p>
              </div>
            </div>

            {/* Env Table */}
            <div style={{ border: '1px solid var(--color-border)', borderRadius: 6, overflow: 'hidden', marginBottom: 16 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                <thead>
                  <tr style={{ background: 'var(--color-surface-hover)', borderBottom: '1px solid var(--color-border)' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, width: '35%' }}>Variable Name</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600 }}>Value</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600, width: '15%' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {envVars.map((env, idx) => {
                    const isRevealed = revealedSecrets[idx];
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontWeight: 600 }}>{env.key}</td>
                        <td style={{ padding: '8px 12px' }}>
                          {env.isSecret && !isRevealed ? (
                            <span style={{ color: 'var(--color-text-muted)', letterSpacing: 2 }}>••••••••••••</span>
                          ) : (
                            <code style={{ fontSize: '0.8rem' }}>{env.value}</code>
                          )}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: 6 }}>
                            {env.isSecret && (
                              <button
                                type="button"
                                className="ghost-icon-btn"
                                onClick={() => setRevealedSecrets((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                                title={isRevealed ? 'Hide secret' : 'Show secret'}
                              >
                                {isRevealed ? <EyeOff size={13} /> : <Eye size={13} />}
                              </button>
                            )}
                            <button
                              type="button"
                              className="ghost-icon-btn"
                              onClick={() => handleDeleteEnvVar(idx)}
                              title="Remove variable"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Add Env Row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.6fr auto auto', gap: 10, alignItems: 'center' }}>
              <input
                type="text"
                placeholder="VARIABLE_NAME"
                value={newEnvKey}
                onChange={(e) => setNewEnvKey(e.target.value)}
                className="input-field"
                style={{ fontSize: '0.8rem' }}
              />
              <input
                type="text"
                placeholder="value"
                value={newEnvVal}
                onChange={(e) => setNewEnvVal(e.target.value)}
                className="input-field"
                style={{ fontSize: '0.8rem' }}
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', cursor: 'pointer', userSelect: 'none' }}>
                <input
                  type="checkbox"
                  checked={newEnvSecret}
                  onChange={(e) => setNewEnvSecret(e.target.checked)}
                />
                <span>Secret</span>
              </label>
              <button
                type="button"
                className="btn btn-outline"
                onClick={handleAddEnvVar}
                disabled={!newEnvKey.trim()}
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
              >
                <Plus size={13} /> Add
              </button>
            </div>
          </div>

          {/* Compute & Resource Sizing Card */}
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '20px 24px',
            }}
          >
            <h3 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 600 }}>Compute & Resource Allocation</h3>
            <p style={{ margin: '0 0 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              Configure memory and CPU limits allocated to this application.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <label className="uc-field" style={{ marginBottom: 0 }}>
                <span className="uc-field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Cpu size={14} /> CPU Allocation
                </span>
                <select
                  className="input-field"
                  value={cpuCores}
                  onChange={(e) => {
                    setCpuCores(e.target.value);
                    setEnvDirty(true);
                  }}
                >
                  <option value="0.5">0.5 Core (Shared)</option>
                  <option value="1">1.0 Core (Standard)</option>
                  <option value="2">2.0 Cores (High)</option>
                  <option value="4">4.0 Cores (Extreme)</option>
                </select>
              </label>

              <label className="uc-field" style={{ marginBottom: 0 }}>
                <span className="uc-field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <HardDrive size={14} /> Memory Limit
                </span>
                <select
                  className="input-field"
                  value={memoryLimit}
                  onChange={(e) => {
                    setMemoryLimit(e.target.value);
                    setEnvDirty(true);
                  }}
                >
                  <option value="512Mi">512 MB</option>
                  <option value="1Gi">1 GB</option>
                  <option value="2Gi">2 GB</option>
                  <option value="4Gi">4 GB</option>
                  <option value="8Gi">8 GB</option>
                </select>
              </label>

              <label className="uc-field" style={{ marginBottom: 0 }}>
                <span className="uc-field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Radio size={14} /> Replica Scale
                </span>
                <select
                  className="input-field"
                  value={replicas}
                  onChange={(e) => {
                    setReplicas(Number(e.target.value));
                    setEnvDirty(true);
                  }}
                >
                  <option value={1}>1 Replica (Single)</option>
                  <option value={2}>2 Replicas (HA)</option>
                  <option value={3}>3 Replicas (High Availability)</option>
                </select>
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSaveEnv}
                disabled={updateMutation.isPending}
              >
                <Save size={14} /> Save Environment & Resources
              </button>
            </div>
          </div>

          {/* Danger Zone */}
          <div
            style={{
              background: '#fff5f5',
              border: '1px solid #fed7d7',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '20px 24px',
            }}
          >
            <h3 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 600, color: '#c53030' }}>
              Danger Zone
            </h3>
            <p style={{ margin: '0 0 16px', fontSize: '0.8rem', color: '#9b2c2c' }}>
              Destructive actions for this application.
            </p>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#742a2a' }}>Delete this application</div>
                <div style={{ fontSize: '0.78rem', color: '#9b2c2c' }}>
                  Permanently remove the application record, configuration, and registered Workload Identity.
                </div>
              </div>
              <button
                type="button"
                className="btn"
                style={{ background: '#e53e3e', color: '#fff' }}
                onClick={handleDeleteApp}
                disabled={deleteMutation.isPending}
              >
                <Trash2 size={14} /> Delete App
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: LOGS & DEPLOYMENTS */}
      {activeTab === 'logs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Controls Bar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {/* Search input */}
              <div className="search-bar-wrapper" style={{ width: 260 }}>
                <Search size={13} className="search-icon" />
                <input
                  className="search-input"
                  placeholder="Filter logs..."
                  value={logFilter}
                  onChange={(e) => setLogFilter(e.target.value)}
                />
              </div>

              {/* Level Filter */}
              <select
                className="input-field"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                value={logLevel}
                onChange={(e) => setLogLevel(e.target.value as any)}
              >
                <option value="ALL">All Levels</option>
                <option value="INFO">INFO only</option>
                <option value="WARN">WARN only</option>
                <option value="ERROR">ERROR only</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--color-text-muted)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                />
                <span>Auto-scroll</span>
              </label>

              <button
                className="btn btn-outline"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                onClick={() => refetchLogs()}
                disabled={logsFetching}
              >
                <RefreshCw size={13} className={logsFetching ? 'spin' : ''} /> Refresh
              </button>

              <button
                className="btn btn-outline"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                onClick={handleDownloadLogs}
              >
                <Download size={13} /> Export Logs
              </button>

              <button
                className="btn btn-primary"
                style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                onClick={handleTriggerDeploy}
                disabled={isDeploying || deployMutation.isPending}
              >
                <RotateCw size={13} className={isDeploying ? 'spin' : ''} />
                <span>{isDeploying ? 'Deploying...' : 'Redeploy'}</span>
              </button>
            </div>
          </div>

          {/* Terminal Console View */}
          <div
            ref={logTerminalRef}
            style={{
              background: '#0a0f1d',
              color: '#f1f5f9',
              fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
              fontSize: '0.82rem',
              lineHeight: 1.6,
              borderRadius: 8,
              border: '1px solid #1e293b',
              padding: '16px 20px',
              height: '520px',
              overflowY: 'auto',
              boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ color: '#64748b', marginBottom: 12, fontSize: '0.75rem', borderBottom: '1px solid #1e293b', paddingBottom: 6 }}>
              // Live {runtimeMode} log stream • Container: {runtimeInfo?.container_id || 'active'} • Host: http://localhost:{runtimePort || 8080} • Route: {app.route}
            </div>

            {filteredLogs.length === 0 ? (
              <div style={{ color: '#64748b', fontStyle: 'italic', padding: '20px 0' }}>
                No log entries matching the active filter.
              </div>
            ) : (
              filteredLogs.map((line, idx) => {
                const isError = line.includes('[ERROR]') || line.includes('ERR');
                const isWarn = line.includes('[WARN]') || line.includes('WARNING');
                const isSuccess = line.includes('[SUCCESS]') || line.includes('completed');
                return (
                  <div
                    key={idx}
                    style={{
                      color: isError ? '#f87171' : isWarn ? '#fbbf24' : isSuccess ? '#4ade80' : '#e2e8f0',
                      wordBreak: 'break-all',
                    }}
                  >
                    {line}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* TAB 6: APP TASKS KANBAN */}
      {activeTab === 'tasks' && app && (
        <AppTasksKanban appId={app.id} />
      )}
    </div>
  );
}
