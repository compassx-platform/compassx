import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Loader2,
  Server,
  ExternalLink,
  RotateCw,
  AlertCircle,
  Check,
  Terminal,
  RefreshCw,
  FolderGit2,
  Package,
  Radio,
  ChevronDown,
  ChevronUp,
  Copy,
  ArrowRight,
  Code2,
} from 'lucide-react';
import { useToast } from '@/lib/toast';

interface LivePreviewCanvasProps {
  previewUrl: string;
  route: string;
  isContainerRunning: boolean;
  reloadKey: number;
  onReload: () => void;
  onStartDevPod?: () => void;
  isStartingDevPod?: boolean;
  // 4-Step startup progression
  initStep?: number;
  step2Completed?: boolean;
  step3Completed?: boolean;
  step4Completed?: boolean;
  hasCompletedInit?: boolean;
  startError?: string | null;
  onRetryGit?: () => void;
  onRetryInstall?: () => void;
  onRetryRunApp?: () => void;
  isRetrying?: boolean;
  onToggleLogs?: () => void;
  isOutputCollapsed?: boolean;
  devLogs?: string;
  onSwitchToCode?: () => void;
  onProceedToStep3?: () => void;
  isProceedingToStep3?: boolean;
}

const STEP_DEFINITIONS = [
  {
    stepNum: 1,
    id: 'sandbox',
    title: 'Dev Sandbox Runtime',
    description: 'Spinning up container runtime and verifying port mappings.',
    icon: Server,
  },
  {
    stepNum: 2,
    id: 'code_prep',
    title: 'Workspace Codebase',
    description: 'Verifying repository branch and active git workspace.',
    icon: FolderGit2,
  },
  {
    stepNum: 3,
    id: 'install_libs',
    title: 'Dependencies & Libraries',
    description: 'Checking package manifests and resolving dependencies.',
    icon: Package,
  },
  {
    stepNum: 4,
    id: 'run_app',
    title: 'Application Server',
    description: 'Starting development server and verifying live HTTP endpoint.',
    icon: Radio,
  },
];

export function LivePreviewCanvas({
  previewUrl,
  route,
  isContainerRunning,
  reloadKey,
  onReload,
  onStartDevPod,
  isStartingDevPod = false,
  initStep = 0,
  step2Completed = false,
  step3Completed = false,
  step4Completed = false,
  hasCompletedInit = false,
  startError = null,
  onRetryGit,
  onRetryInstall,
  onRetryRunApp,
  isRetrying = false,
  onToggleLogs,
  isOutputCollapsed = true,
  devLogs,
  onSwitchToCode,
  onProceedToStep3,
  isProceedingToStep3 = false,
}: LivePreviewCanvasProps) {
  const toast = useToast();
  const [isIframeLoading, setIsIframeLoading] = useState<boolean>(true);
  const [isServerReachable, setIsServerReachable] = useState<boolean>(false);
  const [isProbing, setIsProbing] = useState<boolean>(false);
  const [iframeError, setIframeError] = useState<boolean>(false);
  const [isInlineLogsOpen, setIsInlineLogsOpen] = useState<boolean>(false);
  const [autoScrollInlineLogs, setAutoScrollInlineLogs] = useState<boolean>(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const inlineLogsRef = useRef<HTMLDivElement>(null);

  // Compute full target URL
  const targetUrl = useMemo(() => {
    if (!previewUrl) return '';
    const cleanRoute = route ? (route.startsWith('/') ? route : `/${route}`) : '';
    const base = `${previewUrl}${cleanRoute}`;
    const separator = base.includes('?') ? '&' : '?';
    return reloadKey > 0 ? `${base}${separator}_t=${reloadKey}` : base;
  }, [previewUrl, route, reloadKey]);

  // Auto-scroll inline logs container when logs update
  useEffect(() => {
    if (isInlineLogsOpen && autoScrollInlineLogs && inlineLogsRef.current) {
      inlineLogsRef.current.scrollTop = inlineLogsRef.current.scrollHeight;
    }
  }, [isInlineLogsOpen, autoScrollInlineLogs, devLogs]);

  // Auto-expand logs terminal when an error occurs so error details are immediately visible
  useEffect(() => {
    if (startError) {
      setIsInlineLogsOpen(true);
    }
  }, [startError]);

  // Probe target dev server endpoint using fetch (mode: 'no-cors')
  // Only probe when the application server step is active or completed to prevent premature connection refused errors.
  useEffect(() => {
    if (!isContainerRunning || !targetUrl || (!hasCompletedInit && !step4Completed)) {
      setIsServerReachable(false);
      setIsProbing(false);
      return;
    }

    // If server is already verified reachable, no need to re-probe
    if (isServerReachable) return;

    let isCancelled = false;
    let pollTimeout: any = null;

    const probeServer = async () => {
      if (isCancelled) return;
      setIsProbing(true);
      try {
        await fetch(targetUrl, { mode: 'no-cors', cache: 'no-cache' });
        if (!isCancelled) {
          setIsServerReachable(true);
          setIsProbing(false);
        }
      } catch (_) {
        if (!isCancelled) {
          setIsServerReachable(false);
          setIsProbing(false);
          pollTimeout = setTimeout(probeServer, 3000);
        }
      }
    };

    probeServer();

    return () => {
      isCancelled = true;
      if (pollTimeout) clearTimeout(pollTimeout);
    };
  }, [targetUrl, isContainerRunning, reloadKey, step4Completed, hasCompletedInit, isServerReachable]);

  // When explicit reloadKey changes or on first mount, handle iframe loading state smoothly
  const prevReloadKeyRef = useRef(reloadKey);
  useEffect(() => {
    if (isContainerRunning && targetUrl && isServerReachable) {
      if (reloadKey !== prevReloadKeyRef.current) {
        prevReloadKeyRef.current = reloadKey;
        setIsIframeLoading(true);
        setIframeError(false);
        const timer = setTimeout(() => {
          setIsIframeLoading(false);
        }, 3000);
        return () => clearTimeout(timer);
      }
    }
  }, [targetUrl, isContainerRunning, reloadKey, isServerReachable]);

  // ── View 1: Dev Sandbox Not Running ─────────────────────────────────────────
  if (!isContainerRunning) {
    return (
      <div
        style={{
          flex: 1,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#ffffff',
          color: '#64748b',
          padding: 24,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: 'rgba(2, 132, 199, 0.08)',
            border: '1px solid rgba(2, 132, 199, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#0284c7',
            marginBottom: 14,
          }}
        >
          <Server size={24} />
        </div>
        <h3 style={{ margin: '0 0 6px', fontSize: '1rem', fontWeight: 600, color: '#0f172a' }}>
          Dev Server Not Running
        </h3>
        <p style={{ margin: '0 0 16px', fontSize: '0.82rem', color: '#64748b', maxWidth: 320, lineHeight: 1.5 }}>
          Start the sandbox dev server to preview the live application running in your active workspace.
        </p>
        {onStartDevPod && (
          <button
            type="button"
            onClick={onStartDevPod}
            disabled={isStartingDevPod}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: 6,
              padding: '7px 16px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: isStartingDevPod ? 'not-allowed' : 'pointer',
              opacity: isStartingDevPod ? 0.7 : 1,
              boxShadow: '0 2px 6px rgba(2, 132, 199, 0.25)',
            }}
          >
            {isStartingDevPod ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                <span>Starting Sandbox...</span>
              </>
            ) : (
              <span>Start Dev Sandbox</span>
            )}
          </button>
        )}
      </div>
    );
  }

  // ── View 2: Application Starting / 4-Step Progress View ───────────────────────
  // Displayed until the dev server is fully booted and responsive
  if (!isServerReachable || (!step4Completed && !hasCompletedInit)) {
    // Determine overall active step state
    const currentStepIndex = Math.min(Math.max(initStep, 0), 3);
    const isStep1Done = isContainerRunning;
    const isStep2Done = step2Completed;
    const isStep3Done = step3Completed;
    const isStep4Done = step4Completed;
    const isWaitingAfterStep2 = isStep2Done && !isStep3Done && !startError && !isProceedingToStep3 && initStep < 2;

    return (
      <div
        style={{
          flex: 1,
          height: '100%',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f8fafc',
          padding: '24px 20px',
          overflowY: 'auto',
        }}
      >
        <div
          style={{
            maxWidth: 520,
            width: '100%',
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 12,
            padding: '22px 24px',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.04)',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {/* Card Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: startError
                  ? '#fef2f2'
                  : isWaitingAfterStep2
                  ? 'rgba(16, 185, 129, 0.1)'
                  : 'rgba(2, 132, 199, 0.1)',
                border: `1px solid ${
                  startError
                    ? '#fecaca'
                    : isWaitingAfterStep2
                    ? 'rgba(16, 185, 129, 0.25)'
                    : 'rgba(2, 132, 199, 0.25)'
                }`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: startError ? '#ef4444' : isWaitingAfterStep2 ? '#10b981' : '#0284c7',
                flexShrink: 0,
              }}
            >
              {startError ? (
                <AlertCircle size={20} />
              ) : isWaitingAfterStep2 ? (
                <Check size={20} strokeWidth={2.5} />
              ) : (
                <Loader2 size={20} className="animate-spin" />
              )}
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <h3
                style={{
                  margin: 0,
                  fontSize: '0.94rem',
                  fontWeight: 600,
                  color: '#0f172a',
                  lineHeight: 1.3,
                }}
              >
                {startError
                  ? 'Startup Paused • Error Detected'
                  : isStep4Done
                  ? 'Waiting for Application Server...'
                  : isWaitingAfterStep2
                  ? 'Step 2 Complete • Workspace Code Prepared'
                  : 'Initializing Application Preview'}
              </h3>
              <p
                style={{
                  margin: '3px 0 0',
                  fontSize: '0.78rem',
                  color: '#64748b',
                  lineHeight: 1.4,
                }}
              >
                {startError
                  ? 'An issue occurred during initialization. Review below to retry.'
                  : isStep4Done
                  ? 'Dev server process is starting up. Checking connection...'
                  : isWaitingAfterStep2
                  ? 'Codebase has been fetched and verified. Files are ready in the Code view.'
                  : `Step ${currentStepIndex + 1} of 4 • ${STEP_DEFINITIONS[currentStepIndex].title}`}
              </p>
            </div>
          </div>

          {/* Segmented Horizontal Step Bar */}
          <div style={{ display: 'flex', gap: 6, width: '100%' }}>
            {STEP_DEFINITIONS.map((s, idx) => {
              const isDone =
                (idx === 0 && isStep1Done) ||
                (idx === 1 && isStep2Done) ||
                (idx === 2 && isStep3Done) ||
                (idx === 3 && isStep4Done);
              const isActive = idx === currentStepIndex && !isDone;
              const isFailed = idx === currentStepIndex && !!startError;

              let bg = '#e2e8f0';
              if (isDone) bg = '#10b981';
              else if (isFailed) bg = '#ef4444';
              else if (isActive) bg = '#0284c7';

              return (
                <div
                  key={s.id}
                  style={{
                    flex: 1,
                    height: 5,
                    borderRadius: 9999,
                    background: bg,
                    transition: 'all 0.3s ease',
                  }}
                  title={`${s.title} (${isDone ? 'Complete' : isFailed ? 'Failed' : isActive ? 'In Progress' : 'Pending'})`}
                />
              );
            })}
          </div>

          {/* 4-Step Checklist */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: '10px 12px',
            }}
          >
            {STEP_DEFINITIONS.map((s, idx) => {
              const isDone =
                (idx === 0 && isStep1Done) ||
                (idx === 1 && isStep2Done) ||
                (idx === 2 && isStep3Done) ||
                (idx === 3 && isStep4Done);
              const isActive = idx === currentStepIndex && !isDone;
              const isFailed = idx === currentStepIndex && !!startError;
              const isNextAfterStep2 = isWaitingAfterStep2 && idx === 2;
              const Icon = s.icon;

              return (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 8px',
                    borderRadius: 6,
                    background: isActive ? '#ffffff' : 'transparent',
                    border: isActive ? '1px solid #e0f2fe' : '1px solid transparent',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    <div
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: isDone
                          ? '#dcfce7'
                          : isFailed
                          ? '#fee2e2'
                          : isActive
                          ? '#e0f2fe'
                          : '#f1f5f9',
                        color: isDone
                          ? '#16a34a'
                          : isFailed
                          ? '#ef4444'
                          : isActive
                          ? '#0284c7'
                          : '#94a3b8',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        flexShrink: 0,
                      }}
                    >
                      {isDone ? (
                        <Check size={13} strokeWidth={2.5} />
                      ) : isFailed ? (
                        <AlertCircle size={13} strokeWidth={2.5} />
                      ) : isActive ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <span>{s.stepNum}</span>
                      )}
                    </div>
                    <div>
                      <div
                        style={{
                          fontSize: '0.8rem',
                          fontWeight: isActive || isDone ? 600 : 500,
                          color: isDone
                            ? '#0f172a'
                            : isActive
                            ? '#0284c7'
                            : isFailed
                            ? '#dc2626'
                            : '#64748b',
                        }}
                      >
                        {s.title}
                      </div>
                    </div>
                  </div>

                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 500,
                      color: isDone
                        ? '#16a34a'
                        : isFailed
                        ? '#dc2626'
                        : isNextAfterStep2
                        ? '#0284c7'
                        : isActive
                        ? '#0284c7'
                        : '#94a3b8',
                    }}
                  >
                    {isDone ? 'Ready' : isFailed ? 'Failed' : isNextAfterStep2 ? 'Next (Pending)' : isActive ? 'Running...' : 'Pending'}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Step 2 Verified Informative Box */}
          {isWaitingAfterStep2 && (
            <div
              style={{
                background: 'rgba(2, 132, 199, 0.04)',
                border: '1px solid rgba(2, 132, 199, 0.18)',
                borderRadius: 8,
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                textAlign: 'left',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#0369a1', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Code2 size={14} color="#0284c7" />
                  <span>Code Panel Ready for Testing</span>
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '2px 8px',
                    borderRadius: 10,
                    background: 'rgba(16, 185, 129, 0.12)',
                    color: '#059669',
                  }}
                >
                  ● STEP 2 VERIFIED
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.76rem', color: '#475569', lineHeight: 1.45 }}>
                Repository codebase has been fetched and verified in your sandbox. Switch to the <strong>Code</strong> view to inspect the File Explorer and code editor, or proceed when ready.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', paddingTop: 2 }}>
                {onSwitchToCode && (
                  <button
                    type="button"
                    onClick={onSwitchToCode}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: 6,
                      padding: '6px 12px',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      color: '#0f172a',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#f8fafc';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#ffffff';
                    }}
                  >
                    <Code2 size={13} color="#0284c7" />
                    <span>Switch to Code View</span>
                  </button>
                )}
                {onProceedToStep3 && (
                  <button
                    type="button"
                    onClick={onProceedToStep3}
                    disabled={isProceedingToStep3}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      background: '#0284c7',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: 6,
                      padding: '6px 14px',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      cursor: isProceedingToStep3 ? 'not-allowed' : 'pointer',
                      opacity: isProceedingToStep3 ? 0.7 : 1,
                      transition: 'all 0.15s ease',
                      marginLeft: 'auto',
                    }}
                  >
                    {isProceedingToStep3 ? (
                      <>
                        <Loader2 size={13} className="animate-spin" />
                        <span>Installing Dependencies...</span>
                      </>
                    ) : (
                      <>
                        <Package size={13} />
                        <span>Proceed to Step 3</span>
                        <ArrowRight size={13} />
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Error Message Box */}
          {startError && (
            <div
              style={{
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: 6,
                padding: '10px 12px',
                fontSize: '0.78rem',
                color: '#b91c1c',
                lineHeight: 1.45,
                wordBreak: 'break-word',
              }}
            >
              {startError}
            </div>
          )}

          {/* Inline Log Terminal (Expandable) */}
          {isInlineLogsOpen && (
            <div
              style={{
                width: '100%',
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                textAlign: 'left',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)',
              }}
            >
              {/* Header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  background: '#f8fafc',
                  borderBottom: '1px solid #e2e8f0',
                  fontSize: '0.72rem',
                  color: '#475569',
                }}
              >
                <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Terminal size={12} color="#0284c7" />
                  <span>Build & Runtime Output</span>
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => setAutoScrollInlineLogs((prev) => !prev)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: autoScrollInlineLogs ? '#0284c7' : '#64748b',
                      fontSize: '0.68rem',
                      cursor: 'pointer',
                      fontWeight: 500,
                    }}
                  >
                    Auto-scroll: {autoScrollInlineLogs ? 'ON' : 'OFF'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (devLogs) {
                        navigator.clipboard.writeText(devLogs);
                        toast.success('Logs copied to clipboard');
                      }
                    }}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#64748b',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 3,
                      fontSize: '0.68rem',
                    }}
                    title="Copy logs"
                  >
                    <Copy size={11} />
                    <span>Copy</span>
                  </button>
                </div>
              </div>

              {/* Console Body */}
              <div
                ref={inlineLogsRef}
                style={{
                  height: 140,
                  maxHeight: 180,
                  padding: '8px 10px',
                  overflowY: 'auto',
                  fontSize: '0.72rem',
                  fontFamily:
                    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                  color: startError ? '#dc2626' : '#334155',
                  lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {devLogs || 'Awaiting build logs...'}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginTop: 2, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {/* Inline Logs Toggle */}
              <button
                type="button"
                onClick={() => setIsInlineLogsOpen((prev) => !prev)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  background: isInlineLogsOpen ? '#e0f2fe' : 'transparent',
                  border: '1px solid #cbd5e1',
                  borderRadius: 6,
                  padding: '5px 10px',
                  fontSize: '0.76rem',
                  fontWeight: 500,
                  color: isInlineLogsOpen ? '#0284c7' : '#475569',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Terminal size={12} color="#0284c7" />
                <span>{isInlineLogsOpen ? 'Hide Logs' : 'View Logs'}</span>
                {isInlineLogsOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>

              {/* Bottom Output Drawer Toggle */}
              {onToggleLogs && (
                <button
                  type="button"
                  onClick={onToggleLogs}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    background: !isOutputCollapsed ? '#e0f2fe' : 'transparent',
                    border: '1px solid #cbd5e1',
                    borderRadius: 6,
                    padding: '5px 10px',
                    fontSize: '0.76rem',
                    fontWeight: 500,
                    color: !isOutputCollapsed ? '#0284c7' : '#475569',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span>{isOutputCollapsed ? 'Open Drawer' : 'Close Drawer'}</span>
                </button>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
              {startError && initStep === 1 && onRetryGit && (
                <button
                  type="button"
                  onClick={onRetryGit}
                  disabled={isRetrying}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    background: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: 6,
                    padding: '6px 14px',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: isRetrying ? 'not-allowed' : 'pointer',
                    opacity: isRetrying ? 0.7 : 1,
                  }}
                >
                  <RefreshCw size={12} className={isRetrying ? 'animate-spin' : ''} />
                  <span>Retry Step 2</span>
                </button>
              )}

              {startError && initStep === 2 && onRetryInstall && (
                <button
                  type="button"
                  onClick={onRetryInstall}
                  disabled={isRetrying}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    background: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: 6,
                    padding: '6px 14px',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: isRetrying ? 'not-allowed' : 'pointer',
                    opacity: isRetrying ? 0.7 : 1,
                  }}
                >
                  <RefreshCw size={12} className={isRetrying ? 'animate-spin' : ''} />
                  <span>Retry Step 3</span>
                </button>
              )}

              {startError && initStep === 3 && onRetryRunApp && (
                <button
                  type="button"
                  onClick={onRetryRunApp}
                  disabled={isRetrying}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    background: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: 6,
                    padding: '6px 14px',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: isRetrying ? 'not-allowed' : 'pointer',
                    opacity: isRetrying ? 0.7 : 1,
                  }}
                >
                  <RefreshCw size={12} className={isRetrying ? 'animate-spin' : ''} />
                  <span>Retry Step 4</span>
                </button>
              )}

              {!startError && (
                <button
                  type="button"
                  onClick={onReload}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    background: '#f1f5f9',
                    border: '1px solid #cbd5e1',
                    borderRadius: 6,
                    padding: '5px 12px',
                    fontSize: '0.76rem',
                    fontWeight: 500,
                    color: '#334155',
                    cursor: 'pointer',
                  }}
                >
                  <RotateCw size={12} />
                  <span>Check Again</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── View 3: Live Application Iframe ──────────────────────────────────────────
  return (
    <div
      style={{
        flex: 1,
        height: '100%',
        width: '100%',
        position: 'relative',
        background: '#ffffff',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Loading Overlay */}
      {isIframeLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(2px)',
            zIndex: 10,
            gap: 10,
          }}
        >
          <Loader2 size={24} className="animate-spin" style={{ color: '#0284c7' }} />
          <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 500 }}>
            Rendering preview...
          </span>
        </div>
      )}

      {/* Main Iframe */}
      {targetUrl ? (
        <iframe
          key={`${targetUrl}-${reloadKey}`}
          ref={iframeRef}
          src={targetUrl}
          title="Live Application Preview"
          onLoad={() => setIsIframeLoading(false)}
          onError={() => {
            setIsIframeLoading(false);
            setIframeError(true);
          }}
          style={{
            flex: 1,
            width: '100%',
            height: '100%',
            border: 'none',
            background: '#ffffff',
          }}
          sandbox="allow-forms allow-modals allow-popups allow-same-origin allow-scripts allow-downloads"
        />
      ) : (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#94a3b8',
            fontSize: '0.85rem',
          }}
        >
          No preview URL available
        </div>
      )}

      {/* Cross-Origin / Connection Notice Footer */}
      {iframeError && (
        <div
          style={{
            position: 'absolute',
            bottom: 12,
            left: 12,
            right: 12,
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 6,
            padding: '8px 12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.78rem',
            color: '#b91c1c',
            zIndex: 20,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertCircle size={14} />
            <span>Could not embed preview directly due to frame security policies.</span>
          </div>
          <a
            href={targetUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              color: '#0284c7',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            <span>Open in Tab</span>
            <ExternalLink size={12} />
          </a>
        </div>
      )}
    </div>
  );
}
