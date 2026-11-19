import React, { useEffect, useMemo } from 'react';
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { Loader2, Sparkles } from 'lucide-react';
import { usePortalConfig } from '../hooks/usePortalConfig';
import { activePortalItem, portalItemTo, portalTargetFromPath } from '../moduleFrame';
import { PortalAppView } from '../components/PortalAppView';
import { PortalDashboardView } from '../components/PortalDashboardView';
import { scopePath } from '@/lib/appNavigation';

export default function PortalPage() {
  const params = useParams<{
    workspaceSlug: string;
    portalAppId?: string;
    applicationId?: string;
    appId?: string;
    dashboardId?: string;
  }>();

  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { data: config, isLoading } = usePortalConfig();

  const activeAppTargetId =
    params.portalAppId ||
    params.applicationId ||
    (params.appId && params.appId !== 'portal' && params.appId !== 'apps' && params.appId !== 'platform' ? params.appId : undefined);

  const activeDashboardTargetId = params.dashboardId;

  // Flatten all visible items in order
  const allVisibleItems = useMemo(() => {
    if (!config?.sections) return [];
    return config.sections.flatMap((sec) => sec.items.filter((it) => it.is_visible));
  }, [config]);

  const located = portalTargetFromPath(location.pathname);
  const activeItem = activePortalItem(
    config?.sections,
    searchParams.get('item'),
    located?.id || activeAppTargetId || activeDashboardTargetId,
    located?.kind || (activeAppTargetId ? 'app' : activeDashboardTargetId ? 'dashboard' : undefined),
  );

  // If on /w/:slug/portal with no item selected in URL, navigate to the first visible item
  useEffect(() => {
    if (isLoading || !config || !params.workspaceSlug) return;

    const isRootPortal = !activeAppTargetId && !activeDashboardTargetId;
    if (isRootPortal && allVisibleItems.length > 0) {
      const first = allVisibleItems.find((item) => item.type === 'app' || item.type === 'dashboard');
      if (first) {
        navigate(scopePath('portal', portalItemTo(first), params.workspaceSlug), { replace: true });
      }
      return;
    }

    if ((activeAppTargetId || activeDashboardTargetId) && !searchParams.get('item') && activeItem) {
      navigate(scopePath('portal', portalItemTo(activeItem), params.workspaceSlug), { replace: true });
    }
  }, [
    isLoading,
    config,
    allVisibleItems,
    activeAppTargetId,
    activeDashboardTargetId,
    activeItem,
    navigate,
    params.workspaceSlug,
    searchParams,
  ]);

  if (isLoading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-muted)', gap: 8 }}>
        <Loader2 size={24} className="spin" />
        <span>Loading Portal...</span>
      </div>
    );
  }

  // Active view resolution
  if (activeAppTargetId) {
    return (
      <PortalAppView
        appId={activeAppTargetId}
        moduleTitle={activeItem?.type === 'app' ? activeItem.title : undefined}
        modulePath={activeItem?.type === 'app' ? activeItem.path : undefined}
      />
    );
  }

  if (activeDashboardTargetId) {
    return <PortalDashboardView dashboardId={activeDashboardTargetId} />;
  }

  // If no items are configured or workspace is empty
  return (
    <div
      style={{
        flex: 1,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 32,
        textAlign: 'center',
        background: 'var(--color-bg)',
      }}
    >
      <div
        style={{
          maxWidth: 520,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: '50%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-primary)',
          }}
        >
          <Sparkles size={36} />
        </div>

        <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-text)' }}>
          Welcome to Workspace Portal
        </h2>

        <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.92rem', lineHeight: 1.6 }}>
          This is your centralized hub for business applications and dashboards. No items have been published to the sidebar navigation yet.
        </p>

      </div>
    </div>
  );
}
