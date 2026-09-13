import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Play,
  Square,
  ExternalLink,
  Globe,
  Loader2,
  CheckCircle2,
  HardDrive,
  Plus,
  Trash2,
  GitBranch,
  RotateCw,
  Terminal,
  UploadCloud,
  FolderGit2,
  RefreshCw,
  Check,
  AlertCircle,
  Clock,
  Layers,
} from 'lucide-react';
import { useToast } from '@/lib/toast';
import {
  AppItem,
  DevWorkspace,
  DevSessionStatus,
  useStartDevSession,
  useStopDevSession,
  useDeleteDevWorkspace,
  useCreateDevWorkspace,
  useDevStatus,
  useDevWorkspaces,
  usePublishDevChanges,
  useDevLogs,
} from '../hooks/useApps';

interface AppDevelopmentTabProps {
  app: AppItem;
  resolvedAppId: string;
}

export function AppDevelopmentTab({ app, resolvedAppId }: AppDevelopmentTabProps) {
  const toast = useToast();

  // Queries & Mutations
  const { data: devStatus, refetch: refetchDevStatus, isFetching: devStatusFetching } = useDevStatus(resolvedAppId);
  const { data: devWorkspaces, refetch: refetchDevWorkspaces, isFetching: workspacesFetching } = useDevWorkspaces(resolvedAppId);
  const { data: devLogsData, refetch: refetchDevLogs } = useDevLogs(resolvedAppId, true);

  const startDevMutation = useStartDevSession();
  const stopDevMutation = useStopDevSession();
  const deleteWorkspaceMutation = useDeleteDevWorkspace();
  const createWorkspaceMutation = useCreateDevWorkspace();
  const publishMutation = usePublishDevChanges();

  // Local State
  const [isStoppingDevPod, setIsStoppingDevPod] = useState(false);
  const [launchStep, setLaunchStep] = useState(0);
  const [launchStatusText, setLaunchStatusText] = useState('');
  const [previewTab, setPreviewTab] = useState<'preview' | 'logs'>('preview');
  const [publishModalOpen, setPublishModalOpen] = useState(false);
  const [commitMessage, setCommitMessage] = useState('');
  const [createWorkspaceModalOpen, setCreateWorkspaceModalOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceBranch, setNewWorkspaceBranch] = useState(app.git_branch || 'main');
  const [isCreatingAndLaunching, setIsCreatingAndLaunching] = useState(false);
  const [logFilter, setLogFilter] = useState('');
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);

  const logsEndRef = useRef<HTMLDivElement>(null);

  const isDevPodStopping =
    isStoppingDevPod ||
    stopDevMutation.isPending ||
    devStatus?.status === 'stopping' ||
    devStatus?.phase === 'Terminating';

  const isDevPodStarting =
    startDevMutation.isPending ||
    isCreatingAndLaunching ||
    devStatus?.status === 'provisioning' ||
    (launchStep > 0 && launchStep < 4);

  const isDevPodRunning =
    (devStatus?.status === 'active' || devStatus?.phase === 'Running') && !isDevPodStopping;

  const liveDevUrl =
    devStatus?.dev_url || `https://${app.slug}-dev.135.13.180.167.nip.io`;

  // Start Dev Pod & optionally open studio
  async function handleStartDevPod(workspaceId?: string, openStudio: boolean = false, workspaceName?: string) {
    if (!resolvedAppId || !app) return;
    try {
      setLaunchStep(1);
      setLaunchStatusText('1. Probing Omnigent central server health and endpoints...');
      await new Promise((r) => setTimeout(r, 400));

      setLaunchStep(2);
      setLaunchStatusText('2. Initializing isolated dev sandbox pod & mounting workspace...');

      const session = await startDevMutation.mutateAsync({ appId: resolvedAppId, workspaceId, workspaceName });

      setLaunchStep(3);
      setLaunchStatusText('3. Establishing WebSocket runner tunnel with Omnigent server...');
      await new Promise((r) => setTimeout(r, 500));

      setLaunchStep(4);
      setLaunchStatusText('4. Dev pod is running and ready!');

      if (openStudio) {
        const targetUrl =
          session?.omnigent_session_url ||
          session?.omnigent_server_url ||
          'https://devstudio.135.13.180.167.nip.io';
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

  // Create Workspace
  async function handleCreateWorkspace(andLaunch: boolean = false) {
    if (!resolvedAppId || !newWorkspaceName.trim()) {
      toast.error('Please enter a workspace name.');
      return;
    }
    const cleanName = newWorkspaceName.trim().toLowerCase().replace(/[^a-z0-9-_]/g, '-');
    try {
      setIsCreatingAndLaunching(true);
      if (andLaunch) {
        setCreateWorkspaceModalOpen(false);
        await handleStartDevPod(undefined, true, cleanName);
        setNewWorkspaceName('');
      } else {
        await createWorkspaceMutation.mutateAsync({
          appId: resolvedAppId,
          name: cleanName,
          gitBranch: newWorkspaceBranch.trim() || app.git_branch || 'main',
        });
        toast.success(`Workspace "${cleanName}" created successfully.`);
        setCreateWorkspaceModalOpen(false);
        setNewWorkspaceName('');
        refetchDevWorkspaces();
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to create workspace.');
    } finally {
      setIsCreatingAndLaunching(false);
    }
  }

  // Stop Dev Pod
  async function handleStopDevPod() {
    if (!resolvedAppId || !app) return;
    if (
      !confirm(
        `Stop the development sandbox pod for "${app.name}"? This will terminate the dev container and release AKS cluster resources.`
      )
    ) {
      return;
    }
    setIsStoppingDevPod(true);
    setLaunchStep(0);
    setLaunchStatusText('Shutting down dev container and releasing cluster resources...');
    try {
      toast.info(`Shutting down dev pod for "${app.name}"...`);
      await stopDevMutation.mutateAsync(resolvedAppId);

      // Poll until status is stopped
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const res = await refetchDevStatus();
        const curStatus = res.data?.status;
        const curPhase = res.data?.phase;
        if (
          !curStatus ||
          curStatus === 'stopped' ||
          curStatus === 'inactive' ||
          curStatus === 'not_found' ||
          curPhase === 'NotFound' ||
          curPhase === 'Unknown'
        ) {
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

  // Delete Workspace
  async function handleDeleteWorkspace(ws: DevWorkspace) {
    if (!resolvedAppId) return;
    if (!confirm(`Delete workspace "${ws.name}"? The workspace folder and files will be permanently removed.`)) {
      return;
    }
    try {
      await deleteWorkspaceMutation.mutateAsync({ appId: resolvedAppId, workspaceId: ws.id });
      toast.success(`Workspace "${ws.name}" deleted.`);
    } catch {
      toast.error('Failed to delete workspace.');
    }
  }

  // Publish Dev Changes
  async function handlePublish() {
    if (!resolvedAppId) return;
    try {
      await publishMutation.mutateAsync({
        appId: resolvedAppId,
        commitMessage: commitMessage.trim() || undefined,
      });
      toast.success('Changes committed and pushed to Git. Redeployment triggered!');
      setPublishModalOpen(false);
      setCommitMessage('');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to publish changes.');
    }
  }

  // Auto scroll logs
  useEffect(() => {
    if (autoScrollLogs && logsEndRef.current) {
      logsEndRef.current.scrollTop = logsEndRef.current.scrollHeight;
    }
  }, [devLogsData, autoScrollLogs]);

  const rawLogs = Array.isArray(devLogsData) ? devLogsData : [];
  const filteredLogs = rawLogs.filter((l) =>
    !logFilter ? true : l.toLowerCase().includes(logFilter.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* ── Top Hero Banner: Development Studio Control Center ── */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(168, 85, 247, 0.08) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          borderRadius: 'var(--radius-lg, 8px)',
          padding: '22px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                boxShadow: '0 4px 14px rgba(99, 102, 241, 0.3)',
              }}
            >
              <Sparkles size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-text)' }}>
                  Interactive Development Sandbox
                </h3>

                {/* Omnigent Server Status Pill */}
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '3px 9px',
                    borderRadius: 12,
                    fontSize: '0.74rem',
                    fontWeight: 600,
                    color: devStatus?.omnigent_server_available ? '#15803d' : '#b45309',
                    background: devStatus?.omnigent_server_available ? '#dcfce7' : '#fef3c7',
                    border: devStatus?.omnigent_server_available ? '1px solid #bbf7d0' : '1px solid #fde68a',
                  }}
                  title={devStatus?.omnigent_server_available ? 'Central Omnigent Server online' : 'Server starts on demand'}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: devStatus?.omnigent_server_available ? '#22c55e' : '#f59e0b',
                    }}
                  />
                  {devStatus?.omnigent_server_available ? 'Server: Online' : 'Server: On-Demand'}
                </span>

                {/* Dev Pod Status Pill */}
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '3px 9px',
                    borderRadius: 12,
                    fontSize: '0.74rem',
                    fontWeight: 600,
                    color: isDevPodRunning ? '#15803d' : isDevPodStopping ? '#b91c1c' : isDevPodStarting ? '#0284c7' : '#4b5563',
                    background: isDevPodRunning ? '#dcfce7' : isDevPodStopping ? '#fee2e2' : isDevPodStarting ? '#e0f2fe' : '#f3f4f6',
                    border: isDevPodRunning ? '1px solid #bbf7d0' : isDevPodStopping ? '1px solid #fecaca' : isDevPodStarting ? '1px solid #bae6fd' : '1px solid #e5e7eb',
                  }}
                >
                  {isDevPodRunning ? (
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#22c55e' }} />
                  ) : isDevPodStopping ? (
                    <Loader2 size={11} className="spin" color="#b91c1c" />
                  ) : isDevPodStarting ? (
                    <Loader2 size={11} className="spin" color="#0284c7" />
                  ) : (
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#9ca3af' }} />
                  )}
                  {isDevPodRunning
                    ? 'Dev Pod: Running'
                    : isDevPodStopping
                    ? 'Dev Pod: Shutting Down...'
                    : isDevPodStarting
                    ? 'Dev Pod: Starting...'
                    : 'Dev Pod: Stopped'}
                </span>
              </div>

              <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: 'var(--color-text-muted)', maxWidth: 620, lineHeight: 1.4 }}>
                Dedicated container environment with hot-reloading Vite/Uvicorn dev servers, isolated workspace storage, and Omnigent AI pair programming.
              </p>
            </div>
          </div>

          {/* Action Buttons Toolbar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {isDevPodStopping ? (
              <button
                className="btn"
                style={{
                  background: '#fee2e2',
                  color: '#b91c1c',
                  border: '1px solid #fecaca',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '8px 16px',
                  borderRadius: 6,
                  fontWeight: 600,
                  cursor: 'not-allowed',
                }}
                disabled={true}
              >
                <Loader2 size={14} className="spin" color="#b91c1c" />
                <span>Shutting down...</span>
              </button>
            ) : isDevPodRunning ? (
              <>
                <button
                  className="btn"
                  style={{
                    background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                    color: '#ffffff',
                    border: 'none',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 16px',
                    borderRadius: 6,
                    boxShadow: '0 2px 8px rgba(99, 102, 241, 0.3)',
                    cursor: 'pointer',
                  }}
                  onClick={() => handleStartDevPod(undefined, true)}
                  disabled={startDevMutation.isPending}
                  title="Open Omnigent Dev Studio in new tab"
                >
                  <ExternalLink size={14} />
                  <span>Launch Dev Studio</span>
                </button>

                <button
                  className="btn btn-outline"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 14px',
                    borderRadius: 6,
                  }}
                  onClick={() => window.open(liveDevUrl, '_blank')}
                  title="Open live dev app URL"
                >
                  <Globe size={14} />
                  <span>Open Dev App</span>
                </button>

                <button
                  className="btn"
                  style={{
                    background: '#f0fdf4',
                    color: '#16a34a',
                    border: '1px solid #bbf7d0',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 14px',
                    borderRadius: 6,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                  onClick={() => setPublishModalOpen(true)}
                  title="Commit changes and deploy"
                >
                  <UploadCloud size={14} />
                  <span>Publish to Git</span>
                </button>

                <button
                  className="btn"
                  style={{
                    background: '#fee2e2',
                    color: '#b91c1c',
                    border: '1px solid #fecaca',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 14px',
                    borderRadius: 6,
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                  onClick={handleStopDevPod}
                  title="Stop development container to release cluster resources"
                >
                  <Square size={13} />
                  <span>Stop Dev Pod</span>
                </button>
              </>
            ) : (
              <>
                <button
                  className="btn btn-outline"
                  style={{
                    borderColor: '#6366f1',
                    color: '#4f46e5',
                    background: '#f5f3ff',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 16px',
                    borderRadius: 6,
                    cursor: isDevPodStarting ? 'not-allowed' : 'pointer',
                  }}
                  onClick={() => handleStartDevPod(undefined, false)}
                  disabled={isDevPodStarting}
                  title="Start dev sandbox pod in background"
                >
                  {isDevPodStarting ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                  <span>{isDevPodStarting ? 'Starting Dev Pod...' : 'Start Dev Pod'}</span>
                </button>

                <button
                  className="btn"
                  style={{
                    background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                    color: '#ffffff',
                    border: 'none',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 18px',
                    borderRadius: 6,
                    cursor: isDevPodStarting ? 'not-allowed' : 'pointer',
                    boxShadow: '0 2px 8px rgba(99, 102, 241, 0.3)',
                  }}
                  onClick={() => handleStartDevPod(undefined, true)}
                  disabled={isDevPodStarting}
                  title="Start dev pod and open Omnigent Dev Studio"
                >
                  {isDevPodStarting ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                  <span>{isDevPodStarting ? 'Launching Studio...' : 'Launch Dev Studio'}</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Multi-Step Pipeline Indicator */}
        <div
          style={{
            background: 'var(--color-surface)',
            border: '1px solid rgba(99, 102, 241, 0.2)',
            borderRadius: 8,
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            {[
              {
                id: 1,
                title: '1. Omnigent Server',
                desc: devStatus?.omnigent_server_available ? 'Online' : 'Starts on-demand',
                done: devStatus?.omnigent_server_available || launchStep > 1,
                active: launchStep === 1,
              },
              {
                id: 2,
                title: '2. Dev Sandbox Pod',
                desc: devStatus?.status === 'active' ? (devStatus?.pod_name ? `${devStatus.pod_name.slice(0, 16)}...` : 'Running') : 'Workspace mounted',
                done: devStatus?.status === 'active' || launchStep > 2,
                active: launchStep === 2 || devStatus?.status === 'provisioning',
              },
              {
                id: 3,
                title: '3. Runner WebSocket',
                desc: devStatus?.status === 'active' ? 'Tunnel Paired' : 'Agent tunnel relay',
                done: devStatus?.status === 'active' || launchStep > 3,
                active: launchStep === 3,
              },
              {
                id: 4,
                title: '4. Dev Studio Ready',
                desc: devStatus?.status === 'active' ? 'Active & Ready' : 'Standby',
                done: devStatus?.status === 'active' || launchStep === 4,
                active: launchStep === 4,
              },
            ].map((step) => (
              <div
                key={step.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 3,
                  padding: '8px 10px',
                  background: step.active ? '#eff6ff' : step.done ? '#f0fdf4' : 'var(--color-surface-hover, #f8fafc)',
                  border: step.active ? '1px solid #3b82f6' : step.done ? '1px solid #86efac' : '1px solid var(--color-border)',
                  borderRadius: 6,
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text)' }}>
                    {step.title}
                  </span>
                  {step.active ? (
                    <Loader2 size={12} className="spin" color="#2563eb" />
                  ) : step.done ? (
                    <CheckCircle2 size={12} color="#16a34a" />
                  ) : (
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-border)' }} />
                  )}
                </div>
                <span style={{ fontSize: '0.7rem', color: step.active ? '#1d4ed8' : step.done ? '#15803d' : 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {step.desc}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            <span style={{ color: launchStatusText ? '#2563eb' : 'var(--color-text-muted)', fontWeight: launchStatusText ? 500 : 400 }}>
              {launchStatusText || (devStatus?.status === 'active' ? 'Dev container is active with live hot-reloading and paired with Omnigent server.' : 'Click "Launch Dev Studio" to start interactive pair-programming.')}
            </span>
            {devStatus?.dev_url && (
              <span style={{ fontSize: '0.72rem' }}>
                Dev Endpoint: <code style={{ color: 'var(--color-primary)' }}>{devStatus.dev_url}</code>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Main Two-Column Layout ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: 20, alignItems: 'start' }}>
        {/* Left Column: Workspaces Management & Git Context */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Workspaces Card */}
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '18px 20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 650, fontSize: '0.95rem' }}>
                <HardDrive size={18} color="var(--color-primary)" />
                <span>Dev Workspaces</span>
                {devWorkspaces && devWorkspaces.length > 0 && (
                  <span style={{ background: 'var(--color-primary)', color: '#fff', borderRadius: 10, padding: '1px 7px', fontSize: '0.72rem', fontWeight: 600 }}>
                    {devWorkspaces.length}
                  </span>
                )}
              </div>
              <button
                onClick={() => {
                  setNewWorkspaceName('');
                  setNewWorkspaceBranch(app.git_branch || 'main');
                  setCreateWorkspaceModalOpen(true);
                }}
                disabled={isDevPodStarting}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '5px 12px',
                  background: 'var(--color-primary)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                  cursor: isDevPodStarting ? 'not-allowed' : 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  opacity: isDevPodStarting ? 0.6 : 1,
                }}
              >
                <Plus size={14} />
                New Workspace
              </button>
            </div>

            {(!devWorkspaces || devWorkspaces.length === 0) ? (
              <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                <HardDrive size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
                <p style={{ margin: '0 0 10px' }}>No workspaces yet.</p>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => {
                    setNewWorkspaceName('');
                    setNewWorkspaceBranch(app.git_branch || 'main');
                    setCreateWorkspaceModalOpen(true);
                  }}
                >
                  <Plus size={13} style={{ marginRight: 4 }} />
                  Create Workspace
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {devWorkspaces.map((ws) => (
                  <div
                    key={ws.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      background: ws.status === 'active' ? 'rgba(34,197,94,0.06)' : 'var(--color-surface-alt, rgba(0,0,0,0.02))',
                      border: ws.status === 'active' ? '1px solid rgba(34,197,94,0.3)' : '1px solid var(--color-border)',
                      borderRadius: 8,
                      gap: 12,
                      flexWrap: 'wrap',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
                      <HardDrive size={16} color={ws.status === 'active' ? '#16a34a' : 'var(--color-text-muted)'} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 650, fontSize: '0.875rem', color: 'var(--color-text)' }}>{ws.name}</span>
                          {ws.status === 'active' && (
                            <span style={{ background: '#dcfce7', color: '#15803d', border: '1px solid #bbf7d0', borderRadius: 10, padding: '1px 7px', fontSize: '0.7rem', fontWeight: 600 }}>
                              ● Active
                            </span>
                          )}
                          {ws.git_branch && (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>
                              <GitBranch size={11} /> {ws.git_branch}
                            </span>
                          )}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 3, flexWrap: 'wrap' }}>
                          <span style={{ fontFamily: 'monospace', color: '#6366f1', background: 'rgba(99,102,241,0.08)', padding: '1px 5px', borderRadius: 4 }}>
                            📁 {ws.folder_path || `app-${app.id.slice(0, 8)}/${ws.name}`}
                          </span>
                          <span>
                            {ws.last_active_at
                              ? `Last active: ${new Date(ws.last_active_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
                              : `Created: ${new Date(ws.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`}
                          </span>
                          {ws.size_bytes ? <span>· {(ws.size_bytes / 1024 / 1024).toFixed(0)} MB</span> : null}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                      <button
                        onClick={() => handleStartDevPod(ws.id, true)}
                        disabled={isDevPodStarting}
                        title="Launch Dev Studio with this workspace"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 5,
                          padding: '5px 12px',
                          background: 'var(--color-primary)',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 6,
                          cursor: isDevPodStarting ? 'not-allowed' : 'pointer',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          opacity: isDevPodStarting ? 0.6 : 1,
                        }}
                      >
                        <Play size={12} />
                        Launch
                      </button>
                      <button
                        onClick={() => handleDeleteWorkspace(ws)}
                        disabled={ws.status === 'active'}
                        title={ws.status === 'active' ? 'Stop dev pod before deleting workspace' : 'Delete this workspace'}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          padding: '5px 8px',
                          background: 'transparent',
                          color: ws.status === 'active' ? 'var(--color-text-muted)' : '#dc2626',
                          border: '1px solid var(--color-border)',
                          borderRadius: 6,
                          cursor: ws.status === 'active' ? 'not-allowed' : 'pointer',
                          opacity: ws.status === 'active' ? 0.4 : 1,
                        }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Git Branch & Sync Info */}
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '18px 20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 650, fontSize: '0.95rem', marginBottom: 12 }}>
              <FolderGit2 size={18} color="var(--color-primary)" />
              <span>Git Sync & Repository</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.82rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Repository URL</span>
                <a
                  href={app.git_repo_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: 'var(--color-primary)', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                >
                  {app.git_repo_url.replace(/^https?:\/\//, '')}
                  <ExternalLink size={12} />
                </a>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Target Branch</span>
                <span style={{ fontWeight: 500 }}>{app.git_branch || app.git_ref || 'main'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Host ID</span>
                <code>{devStatus?.host_id ? `${devStatus.host_id.slice(0, 12)}...` : 'Deterministic Host'}</code>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Live Dev Preview & Real-time Dev Logs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '18px 20px',
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
            }}
          >
            {/* Header Tabs: Preview vs Logs */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border)', paddingBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <button
                  onClick={() => setPreviewTab('preview')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    border: 'none',
                    background: 'none',
                    fontWeight: previewTab === 'preview' ? 600 : 500,
                    color: previewTab === 'preview' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                    cursor: 'pointer',
                    fontSize: '0.88rem',
                  }}
                >
                  <Globe size={15} />
                  <span>Live Dev App Preview</span>
                </button>

                <button
                  onClick={() => setPreviewTab('logs')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    border: 'none',
                    background: 'none',
                    fontWeight: previewTab === 'logs' ? 600 : 500,
                    color: previewTab === 'logs' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                    cursor: 'pointer',
                    fontSize: '0.88rem',
                  }}
                >
                  <Terminal size={15} />
                  <span>Sandbox Logs</span>
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {previewTab === 'preview' ? (
                  <>
                    <button
                      className="btn btn-outline"
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                      onClick={() => window.open(liveDevUrl, '_blank')}
                    >
                      <ExternalLink size={12} /> Open in Dedicated Window
                    </button>
                  </>
                ) : (
                  <>
                    <input
                      type="text"
                      placeholder="Filter logs..."
                      value={logFilter}
                      onChange={(e) => setLogFilter(e.target.value)}
                      style={{
                        padding: '4px 8px',
                        fontSize: '0.75rem',
                        borderRadius: 4,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                      }}
                    />
                    <button
                      className="btn btn-outline"
                      style={{ fontSize: '0.75rem', padding: '4px 8px' }}
                      onClick={() => refetchDevLogs()}
                    >
                      <RefreshCw size={12} />
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Tab Body: Live Preview */}
            {previewTab === 'preview' && (
              <>
                {isDevPodRunning ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ border: '1px solid var(--color-border)', borderRadius: 8, overflow: 'hidden', height: 460, background: '#fff' }}>
                      <iframe
                        src={liveDevUrl}
                        title={`Dev - ${app.name}`}
                        style={{ width: '100%', height: '100%', border: 'none' }}
                      />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--color-text-muted)', padding: '0 4px' }}>
                      <span>Live Dev Endpoint: <code style={{ color: 'var(--color-primary)' }}>{liveDevUrl}</code></span>
                      <button
                        className="ghost-icon-btn"
                        onClick={() => window.open(liveDevUrl, '_blank')}
                        style={{ fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      >
                        <ExternalLink size={12} /> Popout Window
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      height: 320,
                      border: '1px dashed var(--color-border)',
                      borderRadius: 8,
                      background: 'var(--color-surface-hover, #f8fafc)',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 24,
                      textAlign: 'center',
                    }}
                  >
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: '50%',
                        background: 'var(--color-primary-bg)',
                        color: 'var(--color-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: 12,
                      }}
                    >
                      <Sparkles size={24} />
                    </div>
                    <h4 style={{ margin: '0 0 6px', fontSize: '1rem', fontWeight: 600 }}>Development Pod is Not Running</h4>
                    <p style={{ margin: '0 0 16px', fontSize: '0.82rem', color: 'var(--color-text-muted)', maxWidth: 400 }}>
                      Start the dev sandbox to preview code changes live, run background agents, and edit files interactively.
                    </p>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleStartDevPod(undefined, false)}
                      disabled={isDevPodStarting}
                    >
                      {isDevPodStarting ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                      <span>Start Dev Pod</span>
                    </button>
                  </div>
                )}
              </>
            )}

            {/* Tab Body: Dev Logs */}
            {previewTab === 'logs' && (
              <div
                ref={logsEndRef}
                style={{
                  height: 460,
                  background: '#0f172a',
                  color: '#e2e8f0',
                  borderRadius: 8,
                  padding: '12px 14px',
                  fontFamily: 'monospace',
                  fontSize: '0.78rem',
                  lineHeight: 1.5,
                  overflowY: 'auto',
                  border: '1px solid #334155',
                }}
              >
                {filteredLogs.length === 0 ? (
                  <div style={{ color: '#64748b', fontStyle: 'italic', padding: 8 }}>
                    {isDevPodRunning ? 'No logs captured yet...' : 'Dev pod stopped. Start the dev sandbox to stream runtime logs.'}
                  </div>
                ) : (
                  filteredLogs.map((logLine, idx) => (
                    <div key={idx} style={{ wordBreak: 'break-all' }}>
                      {logLine}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Publish Changes to Git Modal ── */}
      {publishModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: 'var(--color-surface)',
              borderRadius: 8,
              border: '1px solid var(--color-border)',
              width: '100%',
              maxWidth: 500,
              padding: 24,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 650, fontSize: '1.05rem' }}>
              <UploadCloud size={20} color="var(--color-primary)" />
              <span>Publish Dev Changes to Git</span>
            </div>

            <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--color-text-muted)' }}>
              All code modifications in the active dev workspace will be staged, committed, pushed to branch{' '}
              <strong>{app.git_branch || app.git_ref || 'main'}</strong>, and trigger a production redeployment.
            </p>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: 6 }}>
                Commit Message
              </label>
              <textarea
                rows={3}
                value={commitMessage}
                onChange={(e) => setCommitMessage(e.target.value)}
                placeholder="e.g. feat: add task kanban board and fix API proxy"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: 6,
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-bg)',
                  fontSize: '0.85rem',
                  resize: 'vertical',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
              <button
                className="btn btn-outline"
                onClick={() => setPublishModalOpen(false)}
                disabled={publishMutation.isPending}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handlePublish}
                disabled={publishMutation.isPending}
              >
                {publishMutation.isPending ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
                <span>{publishMutation.isPending ? 'Publishing...' : 'Commit & Push'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Create Workspace Modal ── */}
      {createWorkspaceModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: 'var(--color-surface)',
              borderRadius: 8,
              border: '1px solid var(--color-border)',
              width: '100%',
              maxWidth: 520,
              padding: 24,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 650, fontSize: '1.05rem' }}>
              <HardDrive size={20} color="var(--color-primary)" />
              <span>Create Dev Workspace</span>
            </div>

            <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--color-text-muted)' }}>
              Create an isolated development workspace. The workspace name you specify will be used directly as the folder name on disk and in Omnigent Server.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: 6 }}>
                  Workspace Name / Folder Name *
                </label>
                <input
                  type="text"
                  value={newWorkspaceName}
                  onChange={(e) => setNewWorkspaceName(e.target.value)}
                  placeholder="e.g. feature-auth, eam-fixes, task-42"
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 6,
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    fontSize: '0.85rem',
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleCreateWorkspace(false);
                    }
                  }}
                />
                {newWorkspaceName.trim() && (
                  <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
                    Omnigent folder path:{' '}
                    <code style={{ color: 'var(--color-primary)' }}>
                      /workspaces/app-{app.id.replace(/[^a-zA-Z0-9_-]/g, '')}/{newWorkspaceName.trim().toLowerCase().replace(/[^a-z0-9-_]/g, '-')}
                    </code>
                  </div>
                )}
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: 6 }}>
                  Git Branch (optional)
                </label>
                <input
                  type="text"
                  value={newWorkspaceBranch}
                  onChange={(e) => setNewWorkspaceBranch(e.target.value)}
                  placeholder="e.g. main or feature/branch-name"
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 6,
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    fontSize: '0.85rem',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
              <button
                className="btn btn-outline"
                onClick={() => setCreateWorkspaceModalOpen(false)}
                disabled={isCreatingAndLaunching || createWorkspaceMutation.isPending}
              >
                Cancel
              </button>
              <button
                className="btn btn-outline"
                onClick={() => handleCreateWorkspace(false)}
                disabled={!newWorkspaceName.trim() || isCreatingAndLaunching || createWorkspaceMutation.isPending}
                style={{ fontWeight: 500 }}
              >
                {createWorkspaceMutation.isPending ? <Loader2 size={14} className="spin" /> : null}
                <span>Create Only</span>
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleCreateWorkspace(true)}
                disabled={!newWorkspaceName.trim() || isCreatingAndLaunching || createWorkspaceMutation.isPending}
              >
                {isCreatingAndLaunching ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                <span>Create & Launch Studio</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
