import * as ReactLib from 'react';
import * as ReactDOMLib from 'react-dom';
import React, { lazy, Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import './_ingestion_styles.css';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ThemeProvider } from '@/design-system';

// ── MF Singleton check ──────────────────────────────────────────────────────
console.log('[MF] React instance in core-opus App:', ReactLib);
console.log('[MF] ReactDOM instance in core-opus App:', ReactDOMLib);
console.log('[MF] React version in core-opus:', ReactLib.version);
// @ts-ignore
if (window.__CORE_OPUS_REACT__) {
  // @ts-ignore
  console.warn('[MF] DUPLICATE React detected! core-opus React !== window.__CORE_OPUS_REACT__:', ReactLib !== window.__CORE_OPUS_REACT__);
} else {
  // @ts-ignore
  window.__CORE_OPUS_REACT__ = ReactLib;
  console.log('[MF] React singleton registered from core-opus');
}
// ────────────────────────────────────────────────────────────────────────────
import { ToastProvider } from '@/lib/toast';
import AppShell from '@/components/layout/AppShell';
import WorkspaceGuard from '@/components/layout/WorkspaceGuard';
import CreateWorkspacePage from '@/pages/CreateWorkspacePage';
import LandingPage from '@/pages/LandingPage';
import IconsShowcasePage from '@/pages/IconsShowcasePage';
import DataCatalog from '@/modules/data/pages/DataCatalog';
import SqlWarehousePage from '@/modules/sql_warehouse/SqlWarehousePage';
import AgentsPage from '@/modules/agents/pages/AgentsPage';
import AgentToolDetailPage from '@/modules/agents/pages/AgentToolDetailPage';
import AgentBuilderPage from '@/modules/agents/pages/AgentBuilderPage';
import AgentChatPage from '@/modules/agents/pages/AgentChatPage';
import ConnectionsPage from '@/modules/agents/pages/ConnectionsPage';
import CreateConnectionPage from '@/modules/agents/pages/CreateConnectionPage';
import LLMConnectionsPage from '@/modules/agents/pages/LLMConnectionsPage';
import DBConnectionsPage from '@/modules/agents/pages/DBConnectionsPage';
import GitConnectionsPage from '@/modules/agents/pages/GitConnectionsPage';
import NotebookPage from '@/modules/notebooks/pages/NotebookPage';
import NotebooksListPage from '@/modules/notebooks/pages/NotebooksListPage';
import ComputePage from '@/modules/compute/pages/ComputePage';
import ComputeResourceDetailPage from '@/modules/compute/pages/ComputeResourceDetailPage';
import DashboardsPage from '@/modules/dashboards/pages/DashboardsPage';
import DashboardEditorPage from '@/modules/dashboards/pages/DashboardEditorPage';
import AssetTypeFormPage from '@/modules/asset_manager/pages/AssetTypeFormPage';
import AssetExplorerPage from '@/modules/asset_manager/pages/AssetExplorerPage';
import AssetFormPage from '@/modules/asset_manager/pages/AssetFormPage';
import AssetImportPage from '@/modules/asset_manager/pages/AssetImportPage';
import JobsListPage from '@/modules/jobs/pages/JobsListPage';
import JobDetailPage from '@/modules/jobs/pages/JobDetailPage';
import RunDetailPage from '@/modules/jobs/pages/RunDetailPage';
import AppsListPage from '@/modules/apps_development/pages/AppsListPage';
import AppEditorPage from '@/modules/apps_development/pages/AppEditorPage';
import MonitoringPage from '@/modules/monitoring/pages/MonitoringPage';
import IngestionConnectionsPage from '@/modules/ingestion/pages/ConnectionsPage';
import IngestionConnectionDetailPage from '@/modules/ingestion/pages/ConnectionDetailPage';
import IngestionJobConfigsPage from '@/modules/ingestion/pages/JobConfigsPage';
import IngestionJobConfigDetailPage from '@/modules/ingestion/pages/JobConfigDetailPage';
import IngestionRunDetailPage from '@/modules/ingestion/pages/IngestionRunDetailPage';
import LogoShowcasePage from '@/pages/LogoShowcasePage';
import DesignSystemShowcasePage from '@/pages/DesignSystemShowcasePage';
import { DEFAULT_APP_ID, isAppId, normalizeAppId, stripAppScope, getDefaultPathForApp } from '@/lib/appNavigation';
import { useMyWorkspaces } from '@/lib/workspaceApi';

// ── User Manager v1 pages (lazy loaded) ─────────────────────────────────────
import { isLoggedIn, getToken, getRefreshToken, isTokenExpired, refreshAccessToken } from '@/lib/auth';
import { fetchSetupStatus, fetchEntryPoint } from '@/lib/userManagerApi';
const LoginPage          = lazy(() => import('@/pages/auth/LoginPage'));
const SetupWizardPage    = lazy(() => import('@/pages/setup/SetupWizardPage'));
const AccountConsolePage = lazy(() => import('@/pages/account/AccountConsolePage'));
const WorkspaceMembersPage = lazy(() => import('@/pages/workspace/WorkspaceMembersPage'));
const InviteAcceptancePage = lazy(() => import('@/pages/invite/InviteAcceptancePage'));
const WorkspacePickerPage  = lazy(() => import('@/pages/workspace-picker/WorkspacePickerPage'));
const NoWorkspacePage      = lazy(() => import('@/pages/no-workspace/NoWorkspacePage'));

const UMSuspense: React.FC<React.PropsWithChildren> = ({ children }) => (
  <Suspense
    fallback={
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--color-bg)' }}>
        <Loader2 size={24} className="spin" style={{ color: 'var(--color-text-muted)' }} />
      </div>
    }
  >
    {children}
  </Suspense>
);

function RootRedirect() {
  const { data: workspaces, isLoading, isError, error } = useMyWorkspaces();
  if (isLoading) return null;
  if (isError) {
    const status = (error as any)?.response?.status;
    if (status === 401 || status === 403) {
      return <Navigate to="/login" replace />;
    }
    // For 500/network errors, fallback to EntryPointGuard to render error screen
    return <EntryPointGuard />;
  }
  if (!workspaces || workspaces.length === 0) {
    return <Navigate to="/no-workspace-access" replace />;
  }
  const lastWs = localStorage.getItem('compassx_last_workspace');
  const matched = workspaces.find(w => w.id === lastWs || w.slug === lastWs);
  const targetSlug = matched ? matched.slug : workspaces[0].slug;
  return <Navigate to={`/w/${targetSlug}`} replace />;
}

/** EntryPointGuard — checks login → setup → entry-point resolution → redirect.
 */
function EntryPointGuard() {
  const navigate = useNavigate();
  const [checking, setChecking] = React.useState(true);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  const resolve = React.useCallback(async () => {
    setChecking(true);
    setErrorMsg(null);
    try {
      // 1. Check if setup is needed
      const { needs_setup } = await fetchSetupStatus();
      if (needs_setup) { navigate('/setup', { replace: true }); return; }

      // 2. Check if logged in
      if (!isLoggedIn()) { navigate('/login', { replace: true }); return; }

      // 3. Resolve entry point
      const ep = await fetchEntryPoint();
      if (ep.route === '/workspace-picker') { navigate('/workspace-picker', { replace: true }); return; }
      if (ep.route === '/no-workspace-access') { navigate('/no-workspace-access', { replace: true }); return; }
      if (ep.route === '/workspace/create') { navigate('/workspace/create', { replace: true }); return; }

      // 4. Fall back to resolved entry point route if available
      if (ep.workspace_id || ep.route) {
        navigate(ep.route, { replace: true });
      } else {
        navigate('/login', { replace: true });
      }
    } catch (err: any) {
      const status = err?.response?.status;
      // Only redirect to login if explicitly unauthenticated
      if (status === 401) {
        navigate('/login', { replace: true });
        return;
      }
      // If 404 on UM endpoints (backend running older legacy version without UM routes), fall back to legacy
      if (status === 404) {
        setChecking(false);
        return;
      }
      // Backend unreachable / network error / 500 error: display connection error screen
      const detailMsg = err?.response?.data?.detail;
      setErrorMsg(
        typeof detailMsg === "string" ? detailMsg : (err?.message || "Failed to connect to backend server")
      );
      setChecking(false);
    }
  }, [navigate]);

  React.useEffect(() => {
    resolve();
  }, [resolve]);

  if (checking) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--color-bg)' }}>
        <Loader2 size={24} className="spin" style={{ color: 'var(--color-text-muted)' }} />
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--color-bg)', padding: 24 }}>
        <div className="glass" style={{ maxWidth: 440, width: '100%', padding: '36px 28px', textAlign: 'center', borderRadius: 'var(--radius-lg)', background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔌</div>
          <h2 style={{ margin: '0 0 8px', fontSize: 18, color: 'var(--color-text)' }}>Backend Connection Error</h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 14, marginBottom: 20 }}>
            Unable to connect to the Compass backend server. Please ensure the backend service is running.
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button className="btn-primary" style={{ padding: '8px 16px', borderRadius: 8, cursor: 'pointer' }} onClick={() => resolve()}>
              Retry Connection
            </button>
            <button className="btn-outline" style={{ padding: '8px 16px', borderRadius: 8, cursor: 'pointer' }} onClick={() => navigate('/login')}>
              Go to Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Legacy fallback
  return <RootRedirect />;
}

function WorkspaceIndex() {
  const { workspaceSlug } = useParams<{ workspaceSlug: string }>();
  return <Navigate to={`/w/${workspaceSlug}/${DEFAULT_APP_ID}`} replace />;
}

function AppHomeRedirect() {
  const { workspaceSlug, appId } = useParams<{ workspaceSlug: string; appId: string }>();
  const normalized = normalizeAppId(appId);
  if (!normalized) return <Navigate to={`/w/${workspaceSlug}/${DEFAULT_APP_ID}`} replace />;

  if (normalized === 'business_center') {
    // Scan localStorage for custom Business Center links (by slug, by UUID, or any key)
    let foundFirstUrl: string | null = null;
    try {
      const bySlug = localStorage.getItem(`compassx_bc_links_${workspaceSlug}`);
      if (bySlug) {
        const parsed = JSON.parse(bySlug);
        if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].url) {
          foundFirstUrl = parsed[0].url;
        }
      }
      if (!foundFirstUrl) {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith('compassx_bc_links_')) {
            const raw = localStorage.getItem(key);
            if (raw) {
              const parsed = JSON.parse(raw);
              if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].url) {
                foundFirstUrl = parsed[0].url;
                break;
              }
            }
          }
        }
      }
    } catch (e) {
      console.error('Failed to parse custom sidebar links for redirect', e);
    }

    if (foundFirstUrl) {
      if (foundFirstUrl.startsWith('/w/')) {
        return <Navigate to={foundFirstUrl} replace />;
      }
      const cleanPath = foundFirstUrl.startsWith('/') ? foundFirstUrl : `/${foundFirstUrl}`;
      return <Navigate to={`/w/${workspaceSlug}/business_center${cleanPath}`} replace />;
    }
  }

  return <Navigate to={`/w/${workspaceSlug}/${normalized}${getDefaultPathForApp(normalized)}`} replace />;
}

function AppScopeGuard() {
  const location = useLocation();
  const { workspaceSlug, appId } = useParams<{ workspaceSlug: string; appId: string }>();

  if (isAppId(appId)) return <AppShell />;

  const normalizedAppId = normalizeAppId(appId);
  if (normalizedAppId) {
    const scopedPath = stripAppScope(location.pathname);
    return <Navigate to={`/w/${workspaceSlug}/${normalizedAppId}${scopedPath}${location.search}${location.hash}`} replace />;
  }
  return <Navigate to={`/w/${workspaceSlug}/${DEFAULT_APP_ID}`} replace />;
}

function AutoTokenRefresh() {
  React.useEffect(() => {
    const checkAndRefresh = async () => {
      const token = getToken();
      const refreshToken = getRefreshToken();
      if (token && refreshToken && isTokenExpired(token, 180)) {
        try {
          await refreshAccessToken();
        } catch (e) {
          console.warn("Background auto token refresh failed:", e);
        }
      }
    };

    checkAndRefresh();
    const interval = setInterval(checkAndRefresh, 60_000);
    return () => clearInterval(interval);
  }, []);

  return null;
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <AutoTokenRefresh />
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <Routes>
              {/* User Manager v1 routes */}
              <Route path="/login"               element={<UMSuspense><LoginPage /></UMSuspense>} />
              <Route path="/setup"               element={<UMSuspense><SetupWizardPage /></UMSuspense>} />
              <Route path="/invite/:token"        element={<UMSuspense><InviteAcceptancePage /></UMSuspense>} />
              <Route path="/workspace-picker"    element={<UMSuspense><WorkspacePickerPage /></UMSuspense>} />
              <Route path="/no-workspace-access" element={<UMSuspense><NoWorkspacePage /></UMSuspense>} />
              <Route path="/account"             element={<UMSuspense><AccountConsolePage /></UMSuspense>} />
              <Route path="/account/workspaces/:workspaceId/members" element={<UMSuspense><WorkspaceMembersPage /></UMSuspense>} />
              <Route path="/design-system"        element={<DesignSystemShowcasePage />} />
              {/* Root: try new entry-point resolution, fall back to legacy workspace routing */}
              <Route path="/" element={<EntryPointGuard />} />
              <Route path="workspace/create" element={<CreateWorkspacePage />} />
              <Route path="w/:workspaceSlug" element={<WorkspaceGuard />}>
                <Route index element={<WorkspaceIndex />} />
                <Route path=":appId" element={<AppScopeGuard />}>
                  <Route index element={<AppHomeRedirect />} />
                  <Route path="home" element={<LandingPage />} />
                  <Route path="data-catalog" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema/table/:table" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema/volume/:volume" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema/notebook/:notebook" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema/dashboard/:dashboard" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema/tool/:tool" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema/:table" element={<DataCatalog />} />
                  <Route path="sql-warehouse" element={<Navigate to="editor" replace />} />
                  <Route path="sql-warehouse/:tab" element={<SqlWarehousePage />} />
                  <Route path="sql-warehouse/:tab/:warehouseId" element={<SqlWarehousePage />} />
                  <Route path="sql-warehouse/:tab/:warehouseId/:subtab" element={<SqlWarehousePage />} />
                  <Route path="agents" element={<AgentsPage />} />
                  <Route path="agents/new" element={<AgentBuilderPage />} />
                  <Route path="agents/create" element={<AgentBuilderPage />} />
                  <Route path="agents/tools/:toolKey" element={<AgentToolDetailPage />} />
                  <Route path="agents/:agentId" element={<AgentChatPage />} />
                  <Route path="agents/:agentId/sessions" element={<AgentChatPage />} />
                  <Route path="agents/:agentId/sessions/:sessionId" element={<AgentChatPage />} />
                  <Route path="agents/:agentId/edit" element={<AgentChatPage initialView="customizations" />} />
                  <Route path="agents/:agentId/builder" element={<AgentBuilderPage />} />
                  <Route path="agents/:agentId/customizations" element={<AgentChatPage initialView="customizations" />} />
                  <Route path="agents/:agentId/chat" element={<AgentChatPage />} />
                  <Route path="agents/:agentId/chat/:sessionId" element={<AgentChatPage />} />
                  <Route path="connections" element={<ConnectionsPage />} />
                  <Route path="connections/create" element={<CreateConnectionPage />} />
                  <Route path="connections/new" element={<CreateConnectionPage />} />
                  <Route path="connections/llm-models" element={<LLMConnectionsPage />} />
                  <Route path="connections/databases" element={<DBConnectionsPage />} />
                  <Route path="connections/git-servers" element={<GitConnectionsPage />} />
                  <Route path="notebooks" element={<NotebooksListPage />} />
                  <Route path="notebooks/open" element={<NotebookPage />} />
                  <Route path="compute" element={<ComputePage />} />
                  <Route path="compute/:resourceId" element={<ComputeResourceDetailPage />} />
                  <Route path="monitoring" element={<MonitoringPage />} />
                  <Route path="dashboards" element={<DashboardsPage />} />
                  <Route path="dashboards/:dashboardId" element={<DashboardEditorPage />} />
                  <Route path="dashboards/:dashboardId/edit" element={<DashboardEditorPage />} />
                  <Route path="assets" element={<AssetExplorerPage />} />
                  <Route path="assets/search" element={<AssetExplorerPage view="search" />} />
                  <Route path="assets/new" element={<AssetFormPage />} />
                  <Route path="assets/import" element={<AssetImportPage />} />
                  <Route path="assets/import/new" element={<AssetImportPage startNew />} />
                  <Route path="assets/import/:jobId" element={<AssetImportPage />} />
                  <Route path="assets/types" element={<AssetExplorerPage view="types" />} />
                  <Route path="assets/types/hierarchy" element={<Navigate to="../.." replace />} />
                  <Route path="assets/types/new" element={<AssetTypeFormPage />} />
                  <Route path="assets/types/:typeId/edit" element={<AssetTypeFormPage />} />
                  <Route path="assets/:instanceId" element={<AssetExplorerPage />} />
                  <Route path="assets/:instanceId/edit" element={<AssetFormPage />} />
                  <Route path="jobs" element={<JobsListPage />} />
                  <Route path="jobs/:jobId" element={<JobDetailPage />} />
                  <Route path="jobs/:jobId/runs/:runId" element={<RunDetailPage />} />
                  {/* API Ingestion */}
                  <Route path="ingestion/connections" element={<IngestionConnectionsPage />} />
                  <Route path="ingestion/connections/:connectionId" element={<IngestionConnectionDetailPage />} />
                  <Route path="ingestion/job-configs" element={<IngestionJobConfigsPage />} />
                  <Route path="ingestion/job-configs/:jobConfigId" element={<IngestionJobConfigDetailPage />} />
                  <Route path="ingestion/runs/:runId" element={<IngestionRunDetailPage />} />
                  {/* CompassX Apps */}
                  <Route path="apps_development" element={<AppsListPage />} />
                  <Route path="apps_development/:compassAppId/:branchId" element={<AppEditorPage />} />
                  {/* Custom Technology & Data Icons Showcase */}
                  <Route path="icons" element={<IconsShowcasePage />} />
                  {/* CompassX Brand & Logo Visualizer */}
                  <Route path="logo" element={<LogoShowcasePage />} />
                  <Route path="brand-logo" element={<LogoShowcasePage />} />
                  {/* CompassX Centralized Design System Showcase */}
                  <Route path="design-system" element={<DesignSystemShowcasePage />} />
                  {/* Fallback for unhandled sub-routes inside an app */}
                  <Route path="*" element={<AppHomeRedirect />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
