import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Loader2, Plus, Sparkles, LayoutGrid, BarChart2, Globe, Sliders } from 'lucide-react';
import { usePortalConfig } from '../hooks/usePortalConfig';
import { PortalAppView } from '../components/PortalAppView';
import { PortalDashboardView } from '../components/PortalDashboardView';
import { CustomizeSidebarDrawer } from '../components/CustomizeSidebarDrawer';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useMe } from '@/lib/userManagerApi';

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
  const { data: me } = useMe();
  const workspaceCtx = useWorkspaceContext();
  const { data: config, isLoading, refetch } = usePortalConfig();

  const activeAppTargetId =
    params.portalAppId ||
    params.applicationId ||
    (params.appId && params.appId !== 'portal' && params.appId !== 'apps' && params.appId !== 'platform' ? params.appId : undefined);

  const activeDashboardTargetId = params.dashboardId;

  const isAccountAdmin = Boolean(me?.account_role === 'account_admin' || me?.is_account_admin || workspaceCtx?.is_account_admin);
  const isWorkspaceAdmin = Boolean(isAccountAdmin || workspaceCtx?.current_user_role === 'workspace_admin' || workspaceCtx?.current_user_role === 'admin');

  const [isCustomizeOpen, setIsCustomizeOpen] = useState(false);

  // Flatten all visible items in order
  const allVisibleItems = useMemo(() => {
    if (!config?.sections) return [];
    return config.sections.flatMap((sec) => sec.items.filter((it) => it.is_visible));
  }, [config]);

  // If on /w/:slug/portal with no item selected in URL, navigate to the first visible item
  useEffect(() => {
    if (isLoading || !config) return;

    const isRootPortal = !activeAppTargetId && !activeDashboardTargetId;
    if (isRootPortal && allVisibleItems.length > 0) {
      const first = allVisibleItems[0];
      if (first.type === 'app') {
        navigate(`/w/${params.workspaceSlug}/portal/app/${first.target_id}`, { replace: true });
      } else if (first.type === 'dashboard') {
        navigate(`/w/${params.workspaceSlug}/portal/dashboard/${first.target_id}`, { replace: true });
      }
    }
  }, [isLoading, config, allVisibleItems, activeAppTargetId, activeDashboardTargetId, navigate, params.workspaceSlug]);

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
    return <PortalAppView appId={activeAppTargetId} />;
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

        {isWorkspaceAdmin && (
          <button
            className="btn-primary"
            onClick={() => setIsCustomizeOpen(true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 20px',
              borderRadius: 8,
              fontWeight: 600,
              cursor: 'pointer',
              marginTop: 8,
            }}
          >
            <Sliders size={16} /> Customize Sidebar
          </button>
        )}
      </div>

      <CustomizeSidebarDrawer
        isOpen={isCustomizeOpen}
        onClose={() => {
          setIsCustomizeOpen(false);
          refetch();
        }}
        currentConfig={config}
      />
    </div>
  );
}
