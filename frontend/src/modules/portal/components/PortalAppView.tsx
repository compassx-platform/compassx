import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useApp, useAppRuntimeStatus, useStartApp } from '@/modules/apps/hooks/useApps';
import { getAccessToken } from '@/lib/auth';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { moduleFrameSrc } from '../moduleFrame';
import { COMPASSX_USER_CONTEXT, COMPASSX_USER_CONTEXT_REQUEST } from '../userContextMessage';

interface PortalAppViewProps {
  appId: string;
  moduleTitle?: string;
  modulePath?: string | null;
}

export function PortalAppView({ appId, moduleTitle, modulePath }: PortalAppViewProps) {
  const { data: app, isLoading: appLoading, error: appError, refetch: refetchApp } = useApp(appId);
  const { data: runtimeStatus } = useAppRuntimeStatus(appId);
  const startAppMutation = useStartApp();
  const workspace = useWorkspaceContext();
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const postUserContext = useCallback((frame: HTMLIFrameElement) => {
    const accessToken = getAccessToken();
    if (!accessToken || !frame.contentWindow) return;
    let targetOrigin = '';
    try {
      targetOrigin = new URL(frame.src, window.location.href).origin;
    } catch {
      return;
    }
    frame.contentWindow.postMessage(
      {
        type: COMPASSX_USER_CONTEXT,
        accessToken,
        workspaceId: workspace.id,
        workspaceSlug: workspace.slug,
      },
      targetOrigin,
    );
  }, [workspace.id, workspace.slug]);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      const frame = iframeRef.current;
      if (!frame?.contentWindow) return;
      let frameOrigin = '';
      try {
        frameOrigin = new URL(frame.src, window.location.href).origin;
      } catch {
        return;
      }
      if (event.origin !== frameOrigin || event.source !== frame.contentWindow) return;
      if (event.data?.type !== COMPASSX_USER_CONTEXT_REQUEST) return;
      postUserContext(frame);
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [postUserContext]);

  const [iframeLoading, setIframeLoading] = useState(true);
  const [openError, setOpenError] = useState<string | null>(null);
  const attemptedStart = useRef<string | null>(null);

  const screenTitle = moduleTitle || app?.name || '';

  useEffect(() => {
    setIframeLoading(true);
    setOpenError(null);
    attemptedStart.current = null;
  }, [appId, modulePath]);

  const isStarting = runtimeStatus?.status === 'starting' || runtimeStatus?.status === 'provisioning' || startAppMutation.isPending;
  const isStopped = Boolean(
    app && (
      app.status === 'stopped'
      || app.status === 'inactive'
      || runtimeStatus?.status === 'stopped'
      || runtimeStatus?.status === 'inactive'
    ),
  );

  useEffect(() => {
    if (!app || !isStopped || isStarting || openError) return;
    if (attemptedStart.current === app.id) return;
    attemptedStart.current = app.id;
    startAppMutation.mutate(app.id, {
      onError: (err: any) => {
        setOpenError(err?.response?.data?.detail || err?.message || 'Could not open this screen.');
      },
    });
  }, [app, isStopped, isStarting, openError, startAppMutation]);

  if (appLoading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-muted)', gap: 8 }}>
        <Loader2 size={24} className="spin" />
        <span>{screenTitle ? `Opening ${screenTitle}...` : 'Opening...'}</span>
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
          <h3 style={{ margin: '0 0 8px', fontSize: '1.1rem', color: 'var(--color-text)' }}>This screen could not be opened</h3>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.88rem' }}>
            The linked application is missing. It may have been removed from this workspace.
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

  if (isStopped || isStarting) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16, textAlign: 'center' }}>
        {openError ? (
          <>
            <AlertCircle size={32} style={{ color: 'var(--color-danger)' }} />
            <div>
              <h3 style={{ margin: '0 0 6px', fontSize: '1.1rem', color: 'var(--color-text)' }}>{screenTitle || 'This screen'}</h3>
              <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.88rem' }}>{openError}</p>
            </div>
            <button
              className="btn-outline"
              onClick={() => {
                setOpenError(null);
                attemptedStart.current = null;
              }}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, cursor: 'pointer' }}
            >
              <RefreshCw size={14} /> Retry
            </button>
          </>
        ) : (
          <>
            <Loader2 size={36} className="spin" style={{ color: 'var(--color-primary)' }} />
            <div>
              <h3 style={{ margin: '0 0 6px', fontSize: '1.1rem', color: 'var(--color-text)' }}>
                {screenTitle ? `Opening ${screenTitle}` : 'Opening'}
              </h3>
              <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.88rem' }}>
                {runtimeStatus?.step_description || 'Getting this screen ready.'}
              </p>
            </div>
          </>
        )}
      </div>
    );
  }

  const resolvedTargetUrl = moduleFrameSrc(runtimeStatus?.url || `/api/v1/apps/${app.id}/proxy/`, modulePath);

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
          <span>{screenTitle ? `Opening ${screenTitle}...` : 'Opening...'}</span>
        </div>
      )}

      <iframe
        ref={iframeRef}
        key={`${app.id}-${modulePath || ''}`}
        src={resolvedTargetUrl}
        title={screenTitle || app.name}
        onLoad={(event) => {
          setIframeLoading(false);
          postUserContext(event.currentTarget);
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
