import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Boxes,
  Sparkles,
  ExternalLink,
  RotateCw,
  Play,
  Square,
  Loader2,
  CheckCircle2,
  Clock,
  Globe,
  Settings,
  ShieldCheck,
  Radio,
  Layers,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import {
  useApp,
  useDevStatus,
  useStartDevSession,
  useStopDevSession,
  useDevHeartbeat,
  useDevWorkspaces,
} from '../hooks/useApps';
import { useOmnigentSession } from '../hooks/useOmnigentChat';
import { AppPreviewPanel } from '../components/build/AppPreviewPanel';
import { OmnigentChatPanel } from '../components/build/OmnigentChatPanel';

export default function AppBuildPage() {
  const params = useParams<{ applicationId?: string; appId?: string }>();
  const resolvedAppId =
    params.applicationId ||
    (params.appId && params.appId !== 'apps' && params.appId !== 'platform' && params.appId !== 'portal' ? params.appId : undefined);

  const navigate = useScopedNavigate();
  const toast = useToast();

  const [splitRatio, setSplitRatio] = useState<number>(50); // 50% left, 50% right
  const [isDragging, setIsDragging] = useState(false);
  const [refreshTriggerKey, setRefreshTriggerKey] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);

  // App & Dev Pod Queries
  const { data: app, isLoading: isAppLoading } = useApp(resolvedAppId);
  const { data: devStatus, refetch: refetchDevStatus } = useDevStatus(resolvedAppId);
  const { data: omnigentSession } = useOmnigentSession(resolvedAppId, devStatus?.workspace_id);
  const { data: devWorkspaces } = useDevWorkspaces(resolvedAppId);

  const startDevMutation = useStartDevSession();
  const stopDevMutation = useStopDevSession();
  const heartbeatMutation = useDevHeartbeat();

  const isDevPodStarting = startDevMutation.isPending || devStatus?.status === 'provisioning';
  const isDevPodStopping = stopDevMutation.isPending || devStatus?.status === 'stopping';
  const isDevPodRunning =
    (devStatus?.status === 'active' || devStatus?.phase === 'Running') &&
    !isDevPodStopping;

  const liveDevUrl =
    devStatus?.dev_url || (app ? `https://${app.slug}-dev.135.13.180.167.nip.io` : '');

  // Keep sandbox alive with periodic heartbeat
  useEffect(() => {
    if (!isDevPodRunning || !resolvedAppId) return;

    heartbeatMutation.mutate({ appId: resolvedAppId });
    const interval = setInterval(() => {
      heartbeatMutation.mutate({ appId: resolvedAppId });
    }, 45_000);

    return () => clearInterval(interval);
  }, [isDevPodRunning, resolvedAppId]);

  // Handle Drag Resizing between panels
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const currentX = e.clientX - rect.left;
      const newRatio = (currentX / rect.width) * 100;
      const clampedRatio = Math.max(25, Math.min(75, newRatio));
      setSplitRatio(clampedRatio);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  async function handleStartDevPod() {
    if (!resolvedAppId || !app) return;
    try {
      toast.info(`Starting dev sandbox pod for "${app.name}"...`);
      await startDevMutation.mutateAsync({ appId: resolvedAppId });
      toast.success(`Dev sandbox started! Connecting live preview...`);
      refetchDevStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to start dev sandbox.');
    }
  }

  async function handleStopDevPod() {
    if (!resolvedAppId || !app) return;
    if (!confirm(`Stop development sandbox pod for "${app.name}"?`)) return;
    try {
      toast.info(`Stopping dev pod for "${app.name}"...`);
      await stopDevMutation.mutateAsync(resolvedAppId);
      toast.success(`Dev sandbox stopped.`);
      refetchDevStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to stop dev sandbox.');
    }
  }

  function handleCodeUpdated() {
    setRefreshTriggerKey((prev) => prev + 1);
  }

  if (isAppLoading || !app) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          width: '100vw',
          background: '#090d16',
          color: '#f8fafc',
          gap: 12,
        }}
      >
        <Loader2 size={24} className="spin" color="#38bdf8" />
        <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>Loading App Build Studio...</span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        background: '#090d16',
        overflow: 'hidden',
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: 50,
      }}
    >
      {/* Studio Top Navigation Bar */}
      <header
        style={{
          height: 48,
          background: '#131c2e',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          gap: 16,
          flexShrink: 0,
          zIndex: 60,
        }}
      >
        {/* Left: Back Arrow & App Metadata */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => navigate(`/apps/${resolvedAppId}`)}
            title="Back to App Details"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 6,
              color: '#cbd5e1',
              padding: '5px 10px',
              fontSize: '0.78rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <ArrowLeft size={14} />
            <span>App Details</span>
          </button>

          <div style={{ width: 1, height: 20, background: '#334155' }} />

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 7,
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
              }}
            >
              <Boxes size={16} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#f8fafc' }}>
                {app.name}
              </span>

              <span
                style={{
                  fontSize: '0.7rem',
                  padding: '1px 7px',
                  borderRadius: 4,
                  background: '#1e293b',
                  color: '#94a3b8',
                  fontWeight: 500,
                }}
              >
                {app.app_type}
              </span>

              {/* Dev Pod Status Pill */}
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '2px 8px',
                  borderRadius: 12,
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  color: isDevPodStopping
                    ? '#fca5a5'
                    : isDevPodStarting
                    ? '#93c5fd'
                    : isDevPodRunning
                    ? '#86efac'
                    : '#94a3b8',
                  background: isDevPodStopping
                    ? 'rgba(239, 68, 68, 0.15)'
                    : isDevPodStarting
                    ? 'rgba(59, 130, 246, 0.15)'
                    : isDevPodRunning
                    ? 'rgba(34, 197, 94, 0.15)'
                    : '#1e293b',
                  border: isDevPodStopping
                    ? '1px solid rgba(239, 68, 68, 0.3)'
                    : isDevPodStarting
                    ? '1px solid rgba(59, 130, 246, 0.3)'
                    : isDevPodRunning
                    ? '1px solid rgba(34, 197, 94, 0.3)'
                    : '1px solid #334155',
                }}
              >
                {isDevPodStopping ? (
                  <>
                    <Loader2 size={11} className="spin" />
                    <span>STOPPING...</span>
                  </>
                ) : isDevPodStarting ? (
                  <>
                    <Loader2 size={11} className="spin" />
                    <span>PROVISIONING...</span>
                  </>
                ) : isDevPodRunning ? (
                  <>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
                    <span>RUNNING • Port {devStatus?.dev_port || 9201}</span>
                  </>
                ) : (
                  <>
                    <Clock size={11} />
                    <span>STOPPED</span>
                  </>
                )}
              </span>

              {/* Active Workspace Tag */}
              {devStatus?.workspace_name && (
                <span
                  style={{
                    fontSize: '0.72rem',
                    color: '#a5b4fc',
                    background: 'rgba(99, 102, 241, 0.12)',
                    padding: '2px 8px',
                    borderRadius: 4,
                    border: '1px solid rgba(99, 102, 241, 0.25)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <Sparkles size={11} />
                  <span>ws: {devStatus.workspace_name}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Studio Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {isDevPodRunning ? (
            <button
              onClick={handleStopDevPod}
              disabled={isDevPodStopping}
              title="Stop development sandbox pod"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 10px',
                borderRadius: 6,
                background: '#1e293b',
                border: '1px solid #f87171',
                color: '#f87171',
                fontSize: '0.75rem',
                fontWeight: 500,
                cursor: isDevPodStopping ? 'not-allowed' : 'pointer',
              }}
            >
              {isDevPodStopping ? <Loader2 size={12} className="spin" /> : <Square size={12} />}
              <span>Stop Sandbox</span>
            </button>
          ) : (
            <button
              onClick={handleStartDevPod}
              disabled={isDevPodStarting}
              title="Start development sandbox pod"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 12px',
                borderRadius: 6,
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                border: 'none',
                color: '#ffffff',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: isDevPodStarting ? 'not-allowed' : 'pointer',
                boxShadow: '0 2px 6px rgba(16, 185, 129, 0.3)',
              }}
            >
              {isDevPodStarting ? <Loader2 size={12} className="spin" /> : <Play size={12} fill="#fff" />}
              <span>Start Sandbox</span>
            </button>
          )}

          <button
            onClick={() => window.open(liveDevUrl, '_blank', 'noopener,noreferrer')}
            title="Open Live App in Dedicated Window"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 10px',
              borderRadius: 6,
              background: '#1e293b',
              border: '1px solid #334155',
              color: '#cbd5e1',
              fontSize: '0.75rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            <ExternalLink size={13} />
            <span>Open in Tab</span>
          </button>

          <button
            onClick={() => navigate(`/apps/${resolvedAppId}?tab=configuration`)}
            title="Configure App Settings"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 10px',
              borderRadius: 6,
              background: '#1e293b',
              border: '1px solid #334155',
              color: '#cbd5e1',
              fontSize: '0.75rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            <Settings size={13} />
            <span>Settings</span>
          </button>
        </div>
      </header>

      {/* Main Full-Screen Split Workspace */}
      <main
        ref={containerRef}
        style={{
          flex: 1,
          display: 'flex',
          width: '100%',
          height: 'calc(100vh - 48px)',
          overflow: 'hidden',
          position: 'relative',
          userSelect: isDragging ? 'none' : 'auto',
        }}
      >
        {/* Left Pane: App Live Preview */}
        <div
          style={{
            width: `${splitRatio}%`,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
            pointerEvents: isDragging ? 'none' : 'auto',
          }}
        >
          <AppPreviewPanel
            app={app}
            resolvedAppId={resolvedAppId!}
            devStatus={devStatus}
            isDevPodRunning={isDevPodRunning}
            isDevPodStarting={isDevPodStarting}
            onStartDevPod={handleStartDevPod}
            externalRefreshKey={refreshTriggerKey}
          />
        </div>

        {/* Draggable Divider Handle */}
        <div
          onMouseDown={handleMouseDown}
          style={{
            width: 8,
            height: '100%',
            background: isDragging ? '#3b82f6' : '#1e293b',
            cursor: 'col-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            zIndex: 30,
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => {
            if (!isDragging) e.currentTarget.style.background = '#334155';
          }}
          onMouseLeave={(e) => {
            if (!isDragging) e.currentTarget.style.background = '#1e293b';
          }}
        >
          <div
            style={{
              width: 3,
              height: 42,
              borderRadius: 2,
              background: isDragging ? '#ffffff' : '#64748b',
            }}
          />
        </div>

        {/* Right Pane: Omnigent AI Chat */}
        <div
          style={{
            width: `${100 - splitRatio}%`,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
            pointerEvents: isDragging ? 'none' : 'auto',
          }}
        >
          <OmnigentChatPanel
            app={app}
            resolvedAppId={resolvedAppId!}
            session={omnigentSession}
            devStatus={devStatus}
            isDevPodRunning={isDevPodRunning}
            onCodeUpdated={handleCodeUpdated}
          />
        </div>
      </main>
    </div>
  );
}
