import * as ReactLib from 'react';
import * as ReactDOMLib from 'react-dom';
import React, { lazy, Suspense } from 'react';
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
import PublicShell from '@/components/layout/PublicShell';
import NovaLandingPage from '@/modules/nova/pages/NovaLandingPage';
import FormsPage from '@/modules/workflows/pages/FormsPage';
import VisualFormBuilder from '@/modules/workflows/pages/VisualFormBuilder';
import FormViewer from '@/modules/workflows/pages/FormViewer';
import FormBulkUpload from '@/modules/workflows/pages/FormBulkUpload';
import Entities from '@/modules/workflows/pages/Entities';
import EntityEditPage from '@/modules/workflows/pages/EntityEditPage';
import EntityRecordsPage from '@/modules/workflows/pages/EntityRecordsPage';
import EntityRecordEditor from '@/modules/workflows/pages/EntityRecordEditor';
import DataCatalog from '@/modules/data/pages/DataCatalog';
import SqlWarehousePage from '@/modules/sql_warehouse/SqlWarehousePage';
import BreakdownForm from '@/modules/workflows/pages/BreakdownForm';
import BreakdownExplorer from '@/modules/workflows/pages/BreakdownExplorer';
import AgentsPage from '@/modules/agents/pages/AgentsPage';
import AgentToolDetailPage from '@/modules/agents/pages/AgentToolDetailPage';
import AgentBuilderPage from '@/modules/agents/pages/AgentBuilderPage';
import AgentChatPage from '@/modules/agents/pages/AgentChatPage';
import WorkspaceConnectionsPage from '@/modules/agents/pages/WorkspaceConnectionsPage';
import ConnectionsPage from '@/modules/agents/pages/ConnectionsPage';
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
  <Suspense fallback={<div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', background:'#0A0A0F', color:'#6366f1', fontSize:24 }}>⟳</div>}>
    {children}
  </Suspense>
);

function RootRedirect() {
  const { data: workspaces, isLoading } = useMyWorkspaces();
  if (isLoading) return null;
  if (!workspaces || workspaces.length === 0) {
    return <Navigate to="/workspace/create" replace />;
  }
  return <Navigate to={`/w/${workspaces[0].slug}`} replace />;
}

/** EntryPointGuard — replaces RootRedirect for new auth system.
 *  Checks login → setup → entry-point resolution → redirect.
 */
function EntryPointGuard() {
  const navigate = useNavigate();
  const [checking, setChecking] = React.useState(true);

  React.useEffect(() => {
    (async () => {
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
      } catch {
        // If new auth fails (e.g. backend not migrated), fall through to legacy workspace routing
        setChecking(false);
      }
    })();
  }, []);

  if (checking) return <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', background:'#0A0A0F' }} />;
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
              {/* Root: try new entry-point resolution, fall back to legacy workspace routing */}
              <Route path="/" element={<EntryPointGuard />} />
              <Route path="workspace/create" element={<CreateWorkspacePage />} />
              <Route path="w/:workspaceSlug" element={<WorkspaceGuard />}>
                <Route index element={<WorkspaceIndex />} />
                <Route path=":appId" element={<AppScopeGuard />}>
                  <Route index element={<AppHomeRedirect />} />
                  <Route path="forms" element={<FormsPage />} />
                  <Route path="forms/builder" element={<VisualFormBuilder />} />
                  <Route path="forms/builder/:formId" element={<VisualFormBuilder />} />
                  <Route path="forms/:formId/view" element={<FormViewer />} />
                  <Route path="forms/:formId/bulk-upload" element={<FormBulkUpload />} />
                  <Route path="entities" element={<Entities />} />
                  <Route path="entities/:entityName/edit" element={<EntityEditPage />} />
                  <Route path="entities/:entityName/records" element={<EntityRecordsPage />} />
                  <Route path="entities/:entity_name/records/:record_id/edit" element={<EntityRecordEditor />} />
                  <Route path="data-catalog" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema" element={<DataCatalog />} />
                  <Route path="data-catalog/:catalog/:schema/:table" element={<DataCatalog />} />
                  <Route path="sql-warehouse" element={<Navigate to="editor" replace />} />
                  <Route path="sql-warehouse/:tab" element={<SqlWarehousePage />} />
                  <Route path="agents" element={<AgentsPage />} />
                  <Route path="agents/tools/:toolKey" element={<AgentToolDetailPage />} />
                  <Route path="agents/new" element={<AgentBuilderPage />} />
                  <Route path="agents/:agentId/edit" element={<AgentBuilderPage />} />
                  <Route path="agents/:agentId/chat" element={<AgentChatPage />} />
                  <Route path="agents/:agentId/chat/:sessionId" element={<AgentChatPage />} />
                  <Route path="agents/connections" element={<WorkspaceConnectionsPage />} />
                  <Route path="connections" element={<ConnectionsPage />} />
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
                  <Route path="breakdown/new" element={<BreakdownForm />} />
                  <Route path="breakdown/explorer" element={<BreakdownExplorer />} />
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
                  {/* Fallback for unhandled sub-routes inside an app */}
                  <Route path="*" element={<AppHomeRedirect />} />
                </Route>
              </Route>
              <Route path="/public" element={<PublicShell />}>
                <Route path="forms/:formId" element={<FormViewer />} />
                <Route path="forms/:formId/edit/:record_id" element={<EntityRecordEditor />} />
                <Route path="forms/:formId/bulk-upload" element={<FormBulkUpload />} />
                <Route path="entities/:entityName/records" element={<EntityRecordsPage />} />
                <Route path="entities/:entity_name/records/:record_id/edit" element={<EntityRecordEditor />} />
                <Route path="breakdown/new" element={<BreakdownForm />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
