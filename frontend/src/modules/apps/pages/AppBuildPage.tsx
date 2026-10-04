import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  ArrowLeft,
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
  Check,
  Cpu,
  Sparkles,
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
} from '../hooks/useApps';

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

  const [startError, setStartError] = useState<string | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
  const [userExplicitlyStopped, setUserExplicitlyStopped] = useState<boolean>(false);
  const [selectedHost, setSelectedHost] = useState<'compassx' | 'omnigent'>(() => {
    try {
      const saved = localStorage.getItem('compassx_preferred_dev_host');
      if (saved === 'compassx' || saved === 'omnigent') return saved;
    } catch (_) {}
    return 'compassx';
  });

  const handleSelectHost = (host: 'compassx' | 'omnigent') => {
    setSelectedHost(host);
    try {
      localStorage.setItem('compassx_preferred_dev_host', host);
    } catch (_) {}
  };

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

  // Sync host selection with running container if available
  useEffect(() => {
    if (devStatus?.host_type === 'compassx' || devStatus?.host_type === 'omnigent') {
      setSelectedHost(devStatus.host_type);
    }
    if (devStatus && (devStatus.status === 'active' || devStatus.phase === 'Running')) {
      hasTriggeredInitialStart.current = true;
    }
  }, [devStatus]);

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
        {/* Left: Back button & Breadcrumbs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <button
            onClick={() => navigate(`/apps/${resolvedAppId}`)}
            title="Back to App Details"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: 'var(--color-surface-hover, rgba(255,255,255,0.06))',
              border: '1px solid var(--color-border, #334155)',
              borderRadius: 6,
              color: 'var(--color-text, #cbd5e1)',
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <ArrowLeft size={14} />
            <span>App Details</span>
          </button>

          <div style={{ width: 1, height: 20, background: 'var(--color-border, #334155)' }} />

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
              }}
            >
              <Boxes size={16} />
            </div>

            <span style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--color-text, #f8fafc)' }}>
              {app?.name || 'App'}
            </span>

            <span style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.85rem' }}>/</span>

            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: '0.82rem',
                fontWeight: 600,
                color: '#818cf8',
              }}
            >
              <Hammer size={13} />
              Build
            </span>

            {/* Dev Sandbox Status Pill in Header (Always matches stage) */}
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '2px 8px',
                borderRadius: 12,
                fontSize: '0.72rem',
                fontWeight: 600,
                marginLeft: 6,
                color:
                  stage === 'stopping' || (stage === 'starting' && startError)
                    ? '#fca5a5'
                    : stage === 'starting'
                    ? step4Completed
                      ? '#86efac'
                      : '#93c5fd'
                    : stage === 'running'
                    ? '#86efac'
                    : '#94a3b8',
                background:
                  stage === 'stopping' || (stage === 'starting' && startError)
                    ? 'rgba(239, 68, 68, 0.15)'
                    : stage === 'starting'
                    ? step4Completed
                      ? 'rgba(34, 197, 94, 0.15)'
                      : 'rgba(59, 130, 246, 0.15)'
                    : stage === 'running'
                    ? 'rgba(34, 197, 94, 0.15)'
                    : 'rgba(255, 255, 255, 0.05)',
                border:
                  stage === 'stopping' || (stage === 'starting' && startError)
                    ? '1px solid rgba(239, 68, 68, 0.3)'
                    : stage === 'starting'
                    ? step4Completed
                      ? '1px solid rgba(34, 197, 94, 0.3)'
                      : '1px solid rgba(59, 130, 246, 0.3)'
                    : stage === 'running'
                    ? '1px solid rgba(34, 197, 94, 0.3)'
                    : '1px solid rgba(255, 255, 255, 0.1)',
              }}
            >
              {stage === 'stopping' ? (
                <>
                  <Loader2 size={11} className="spin" />
                  <span>STOPPING SANDBOX</span>
                </>
              ) : stage === 'starting' ? (
                startError ? (
                  <>
                    <AlertCircle size={11} />
                    <span>
                      {initStep === 3
                        ? 'APP START FAILED'
                        : initStep === 2
                        ? 'INSTALLATION FAILED'
                        : initStep === 1
                        ? 'CODEBASE PREP FAILED'
                        : 'STARTUP FAILED'}
                    </span>
                  </>
                ) : (
                  <>
                    {step4Completed ? (
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
                    ) : (
                      <Loader2 size={11} className="spin" />
                    )}
                    <span>
                      {initStep === 3
                        ? step4Completed
                          ? 'APPLICATION READY'
                          : 'STARTING APPLICATION'
                        : initStep === 2
                        ? step3Completed
                          ? 'LIBRARIES READY'
                          : 'INSTALLING LIBRARIES'
                        : initStep === 1
                        ? step2Completed
                          ? 'WORKSPACE READY'
                          : 'PREPARING CODEBASE'
                        : 'STARTING SANDBOX'}
                    </span>
                  </>
                )
              ) : stage === 'running' ? (
                <>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
                  <span>
                    SANDBOX ACTIVE {devStatus?.dev_port ? `• :${devStatus.dev_port}` : ''}
                  </span>
                </>
              ) : (
                <>
                  <Clock size={11} />
                  <span>SANDBOX STOPPED</span>
                </>
              )}
            </span>

            {/* Dev Host Pill in Header */}
            {(stage === 'running' || stage === 'starting') && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '2px 8px',
                  borderRadius: 12,
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  marginLeft: 4,
                  color: '#c7d2fe',
                  background: 'rgba(99, 102, 241, 0.14)',
                  border: '1px solid rgba(99, 102, 241, 0.28)',
                }}
                title={
                  devStatus?.host_image ||
                  (selectedHost === 'compassx' ? 'compassx-host:latest' : 'ghcr.io/omnigent-ai/omnigent-host:latest')
                }
              >
                <Cpu size={11} />
                <span>
                  Host: {devStatus?.host_type === 'omnigent' || (!devStatus?.host_type && selectedHost === 'omnigent') ? 'Omnigent' : 'CompassX'}
                </span>
              </span>
            )}
          </div>
        </div>

        {/* Right: Three Dots Action Menu (Icon Only) */}
        <div ref={menuRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setIsMenuOpen((prev) => !prev)}
            title="More options"
            aria-label="More options"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: 'none',
              padding: 6,
              color: isMenuOpen ? 'var(--color-text, #f8fafc)' : 'var(--color-text-muted, #94a3b8)',
              cursor: 'pointer',
              transition: 'color 0.15s ease',
            }}
          >
            <MoreVertical size={18} />
          </button>

          {isMenuOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                right: 0,
                width: 190,
                background: 'var(--color-surface, #1e293b)',
                border: '1px solid var(--color-border, #334155)',
                borderRadius: 8,
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)',
                padding: 4,
                zIndex: 50,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
              }}
            >
              <button
                onClick={handleStopDev}
                disabled={isStoppingOperation || (stage === 'stopped' && !isContainerRunning)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '8px 12px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: 6,
                  color: isStoppingOperation || (stage === 'stopped' && !isContainerRunning)
                    ? 'var(--color-text-muted, #64748b)'
                    : '#f87171',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  cursor: isStoppingOperation || (stage === 'stopped' && !isContainerRunning)
                    ? 'not-allowed'
                    : 'pointer',
                  opacity: isStoppingOperation || (stage === 'stopped' && !isContainerRunning)
                    ? 0.5
                    : 1,
                  textAlign: 'left',
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isStoppingOperation && !(stage === 'stopped' && !isContainerRunning)) {
                    e.currentTarget.style.background = 'rgba(239, 68, 68, 0.12)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                {isStoppingOperation ? (
                  <Loader2 size={14} className="spin" />
                ) : (
                  <Square size={14} />
                )}
                <span>{isStoppingOperation ? 'Stopping Sandbox...' : 'Stop Dev Sandbox'}</span>
              </button>
            </div>
          )}
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
          overflow: 'auto',
          padding: '24px 32px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {stage === 'running' ? (
          /* Stage: Running -> Main Blank Workspace Canvas Area */
          <div
            style={{
              flex: 1,
              minHeight: 280,
              border: '2px dashed var(--color-border, #334155)',
              borderRadius: 10,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--color-text, #f8fafc)',
              gap: 12,
              padding: 32,
              textAlign: 'center',
              animation: 'fadeIn 0.3s ease-in-out',
            }}
          >
            <Hammer size={32} color="#818cf8" style={{ opacity: 0.8 }} />
            <div>
              <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 650, color: 'var(--color-text, #f8fafc)' }}>
                Build Studio Canvas Ready
              </h4>
              <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: 'var(--color-text-muted, #94a3b8)', maxWidth: 460 }}>
                Dev sandbox is running. Ready for the next UI components and live editor tools.
              </p>
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
            <h2 style={{ margin: '0 0 6px', fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-text, #f8fafc)' }}>
              Stopping Dev Sandbox...
            </h2>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-muted, #94a3b8)' }}>
              Gracefully tearing down container environment and freeing ports.
            </p>
          </div>
        ) : stage === 'stopped' ? (
          /* Stage: Sandbox Stopped View with Host Environment Selection */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 20px',
              maxWidth: 620,
              margin: '0 auto',
              width: '100%',
              textAlign: 'center',
            }}
          >
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
                boxShadow: '0 8px 24px rgba(99, 102, 241, 0.15)',
              }}
            >
              <Server size={30} />
            </div>

            <h2 style={{ margin: '0 0 8px', fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-text, #f8fafc)' }}>
              Select Host Environment
            </h2>
            <p style={{ margin: '0 0 28px', fontSize: '0.86rem', color: 'var(--color-text-muted, #94a3b8)', lineHeight: 1.5, maxWidth: 480 }}>
              Choose the runtime host image for your dev sandbox before opening the Build Studio canvas.
            </p>

            {startError && (
              <div
                style={{
                  background: 'rgba(239, 68, 68, 0.12)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  borderRadius: 8,
                  padding: '10px 14px',
                  fontSize: '0.8rem',
                  color: '#fca5a5',
                  marginBottom: 20,
                  width: '100%',
                  textAlign: 'left',
                }}
              >
                {startError}
              </div>
            )}

            {/* Host Cards Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                gap: 16,
                width: '100%',
                marginBottom: 20,
                textAlign: 'left',
              }}
            >
              {/* CompassX Host Card */}
              <div
                onClick={() => handleSelectHost('compassx')}
                style={{
                  border: selectedHost === 'compassx' ? '2px solid #6366f1' : '1px solid var(--color-border, #334155)',
                  background: selectedHost === 'compassx' ? 'rgba(99, 102, 241, 0.09)' : 'var(--color-surface, #1e293b)',
                  borderRadius: 12,
                  padding: '18px 18px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: selectedHost === 'compassx' ? '0 0 18px rgba(99, 102, 241, 0.22)' : 'none',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <div
                      style={{
                        width: 20,
                        height: 20,
                        borderRadius: '50%',
                        border: selectedHost === 'compassx' ? 'none' : '2px solid #64748b',
                        background: selectedHost === 'compassx' ? '#6366f1' : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {selectedHost === 'compassx' && <Check size={13} color="#ffffff" strokeWidth={3} />}
                    </div>

                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                        color: '#ffffff',
                        fontSize: '0.66rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: 10,
                        letterSpacing: '0.4px',
                      }}
                    >
                      <Sparkles size={10} /> RECOMMENDED
                    </span>
                  </div>

                  <div style={{ fontSize: '1.02rem', fontWeight: 650, color: 'var(--color-text, #f8fafc)' }}>
                    CompassX Host
                  </div>
                  <div
                    style={{
                      fontSize: '0.72rem',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                      color: '#818cf8',
                      marginTop: 4,
                    }}
                  >
                    compassx-host:latest
                  </div>
                </div>

                <p
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--color-text-muted, #94a3b8)',
                    lineHeight: 1.45,
                    marginTop: 12,
                    marginBottom: 0,
                  }}
                >
                  Tailored runtime environment pre-bundled with CompassX agent bindings and platform tools.
                </p>
              </div>

              {/* Omnigent Host Card */}
              <div
                onClick={() => handleSelectHost('omnigent')}
                style={{
                  border: selectedHost === 'omnigent' ? '2px solid #6366f1' : '1px solid var(--color-border, #334155)',
                  background: selectedHost === 'omnigent' ? 'rgba(99, 102, 241, 0.09)' : 'var(--color-surface, #1e293b)',
                  borderRadius: 12,
                  padding: '18px 18px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: selectedHost === 'omnigent' ? '0 0 18px rgba(99, 102, 241, 0.22)' : 'none',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <div
                      style={{
                        width: 20,
                        height: 20,
                        borderRadius: '50%',
                        border: selectedHost === 'omnigent' ? 'none' : '2px solid #64748b',
                        background: selectedHost === 'omnigent' ? '#6366f1' : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {selectedHost === 'omnigent' && <Check size={13} color="#ffffff" strokeWidth={3} />}
                    </div>

                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        background: 'rgba(255, 255, 255, 0.08)',
                        color: '#94a3b8',
                        fontSize: '0.66rem',
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: 10,
                      }}
                    >
                      UPSTREAM
                    </span>
                  </div>

                  <div style={{ fontSize: '1.02rem', fontWeight: 650, color: 'var(--color-text, #f8fafc)' }}>
                    Omnigent Host
                  </div>
                  <div
                    style={{
                      fontSize: '0.72rem',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                      color: '#94a3b8',
                      marginTop: 4,
                    }}
                  >
                    omnigent-host:latest
                  </div>
                </div>

                <p
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--color-text-muted, #94a3b8)',
                    lineHeight: 1.45,
                    marginTop: 12,
                    marginBottom: 0,
                  }}
                >
                  Standard upstream Omnigent developer runtime container for generic workspace execution.
                </p>
              </div>
            </div>

            {/* Subtext info */}
            <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted, #64748b)', marginBottom: 24, maxWidth: 520 }}>
              CompassX Host is cloned from the Omnigent Host base image and serves as the starting foundation for platform customizations.
            </div>

            {/* Start Button */}
            <button
              onClick={() => handleStartDev(selectedHost)}
              disabled={startDevMutation.isPending}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                border: 'none',
                borderRadius: 8,
                color: '#ffffff',
                padding: '11px 26px',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: startDevMutation.isPending ? 'not-allowed' : 'pointer',
                opacity: startDevMutation.isPending ? 0.6 : 1,
                boxShadow: '0 4px 14px rgba(79, 70, 229, 0.4)',
                transition: 'transform 0.1s ease, box-shadow 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!startDevMutation.isPending) {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 6px 18px rgba(79, 70, 229, 0.5)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 4px 14px rgba(79, 70, 229, 0.4)';
              }}
            >
              {startDevMutation.isPending ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <Play size={16} fill="currentColor" />
              )}
              <span>
                Start Dev Sandbox with {selectedHost === 'compassx' ? 'CompassX Host' : 'Omnigent Host'}
              </span>
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
      </main>
    </div>
  );
}
