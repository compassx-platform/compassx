import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AppItem, useDevStatus, useStartDevSession, useDevHeartbeat } from '../../hooks/useApps';
import { useOmnigentSession } from '../../hooks/useOmnigentChat';
import { AppPreviewPanel } from './AppPreviewPanel';
import { OmnigentChatPanel } from './OmnigentChatPanel';
import { useToast } from '@/lib/toast';

interface AppBuildStudioProps {
  app: AppItem;
  resolvedAppId: string;
}

export function AppBuildStudio({ app, resolvedAppId }: AppBuildStudioProps) {
  const toast = useToast();
  const [splitRatio, setSplitRatio] = useState<number>(50); // 50% / 50%
  const [isDragging, setIsDragging] = useState(false);
  const [refreshTriggerKey, setRefreshTriggerKey] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);

  // Dev Pod Status & Session Hooks
  const { data: devStatus, refetch: refetchDevStatus } = useDevStatus(resolvedAppId);
  const { data: omnigentSession } = useOmnigentSession(resolvedAppId, devStatus?.workspace_id);
  const startDevMutation = useStartDevSession();
  const heartbeatMutation = useDevHeartbeat();

  const isDevPodStarting = startDevMutation.isPending || devStatus?.status === 'provisioning';
  const isDevPodRunning =
    (devStatus?.status === 'active' || devStatus?.phase === 'Running') &&
    devStatus?.status !== 'stopping' &&
    devStatus?.phase !== 'Terminating';

  // Keep sandbox alive with heartbeat while user is in Build Studio
  useEffect(() => {
    if (!isDevPodRunning || !resolvedAppId) return;

    heartbeatMutation.mutate({ appId: resolvedAppId });
    const interval = setInterval(() => {
      heartbeatMutation.mutate({ appId: resolvedAppId });
    }, 45_000);

    return () => clearInterval(interval);
  }, [isDevPodRunning, resolvedAppId]);

  // Handle Drag Resizing
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
      // Clamp between 25% and 75%
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
    try {
      toast.info(`Starting dev sandbox pod for "${app.name}"...`);
      await startDevMutation.mutateAsync({ appId: resolvedAppId });
      toast.success(`Dev sandbox started! Connecting live preview...`);
      refetchDevStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to start dev sandbox.');
    }
  }

  function handleCodeUpdated() {
    setRefreshTriggerKey((prev) => prev + 1);
  }

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        width: '100%',
        height: 'calc(100vh - 220px)',
        minHeight: '600px',
        background: '#090d16',
        borderRadius: 12,
        overflow: 'hidden',
        border: '1px solid var(--color-border)',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.25)',
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
          resolvedAppId={resolvedAppId}
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
          zIndex: 20,
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
            height: 36,
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
          resolvedAppId={resolvedAppId}
          session={omnigentSession}
          devStatus={devStatus}
          isDevPodRunning={isDevPodRunning}
          onCodeUpdated={handleCodeUpdated}
        />
      </div>
    </div>
  );
}
