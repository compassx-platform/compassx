import React, { useState, useEffect } from 'react';
import { Loader2, Play, AlertCircle, RefreshCw, ExternalLink, Globe } from 'lucide-react';
import { useApp, useAppRuntimeStatus, useStartApp } from '@/modules/apps/hooks/useApps';
import { useToast } from '@/lib/toast';

interface PortalAppViewProps {
  appId: string;
}

export function PortalAppView({ appId }: PortalAppViewProps) {
  const toast = useToast();
  const { data: app, isLoading: appLoading, error: appError, refetch: refetchApp } = useApp(appId);
  const { data: runtimeStatus, isLoading: runtimeLoading, refetch: refetchRuntime } = useAppRuntimeStatus(appId);
  const startAppMutation = useStartApp();

  const [iframeLoading, setIframeLoading] = useState(true);
  const [iframeError, setIframeError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setIframeLoading(true);
    setIframeError(false);
  }, [appId, refreshKey]);

  if (appLoading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-muted)', gap: 8 }}>
        <Loader2 size={24} className="spin" />
        <span>Loading application...</span>
      </div>
    );
  }

  if (appError || !app) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16, padding: 24, textAlign: 'center' }}>
        <div style={{ padding: 16, borderRadius: '50%', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--color-danger)' }}>
          <AlertCircle size={32} />
        </div>
        <div>
          <h3 style={{ margin: '0 0 8px', fontSize: '1.1rem', color: 'var(--color-text)' }}>Application Not Found</h3>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.88rem' }}>
            The requested application could not be loaded. It may have been deleted or moved.
          </p>
        </div>
        <button
          className="btn-outline"
          onClick={() => refetchApp()}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, cursor: 'pointer' }}
        >
          <RefreshCw size={14} /> Retry
        </button>
      </div>
    );
  }

  const isStarting = runtimeStatus?.status === 'starting' || runtimeStatus?.status === 'provisioning' || startAppMutation.isPending;
  const isStopped = app.status === 'stopped' || app.status === 'inactive' || runtimeStatus?.status === 'stopped' || runtimeStatus?.status === 'inactive';

  if (isStopped && !isStarting) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 20, padding: 32, textAlign: 'center' }}>
        <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--color-surface)', border: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)' }}>
          <Globe size={32} />
        </div>
        <div style={{ maxWidth: 460 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text)' }}>
            {app.name} is currently offline
          </h3>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.9rem', lineHeight: 1.5 }}>
            This application is stopped to save compute resources. Click the button below to start the container instance.
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={async () => {
            try {
              await startAppMutation.mutateAsync(app.id);
              toast.success(`Starting ${app.name}...`);
            } catch (err: any) {
              toast.error(err?.response?.data?.detail || 'Failed to start application.');
            }
          }}
          disabled={startAppMutation.isPending}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 24px',
            borderRadius: 8,
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: '0.92rem',
          }}
        >
          {startAppMutation.isPending ? <Loader2 size={16} className="spin" /> : <Play size={16} fill="currentColor" />}
          Start Application
        </button>
      </div>
    );
  }

  if (isStarting) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16, textAlign: 'center' }}>
        <Loader2 size={36} className="spin" style={{ color: 'var(--color-primary)' }} />
        <div>
          <h3 style={{ margin: '0 0 6px', fontSize: '1.1rem', color: 'var(--color-text)' }}>Starting {app.name}...</h3>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.88rem' }}>
            {runtimeStatus?.step_description || 'Provisioning runtime container and establishing networking...'}
          </p>
        </div>
      </div>
    );
  }

  // Determine iframe target URL:
  // 1. Runtime URL if available
  // 2. Fallback to API proxy URL: /api/v1/apps/{appId}/proxy/
  const resolvedTargetUrl = runtimeStatus?.url || `/api/v1/apps/${app.id}/proxy/`;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#ffffff' }}>
      {iframeLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--color-bg)',
            zIndex: 10,
            gap: 8,
            color: 'var(--color-text-muted)',
          }}
        >
          <Loader2 size={24} className="spin" style={{ color: 'var(--color-primary)' }} />
          <span>Loading {app.name}...</span>
        </div>
      )}

      <iframe
        key={`${app.id}-${refreshKey}`}
        src={resolvedTargetUrl}
        title={app.name}
        onLoad={() => setIframeLoading(false)}
        onError={() => {
          setIframeLoading(false);
          setIframeError(true);
        }}
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          display: 'block',
          flex: 1,
        }}
        allow="accelerometer; ambient-light-sensor; camera; encrypted-media; geolocation; gyroscope; hid; microphone; midi; payment; usb; vr; xr-spatial-tracking"
        sandbox="allow-forms allow-modals allow-popups allow-presentation allow-same-origin allow-scripts allow-downloads"
      />
    </div>
  );
}
