import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  FileText,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  Sparkles,
  CircleUserRound,
  Settings,
  Sliders,
  LogOut,
  FlaskConical,
  Grid2x2,
  Palette,
  Image,
  ArrowDownToLine,
  BarChart2,
  Globe,
  LayoutGrid,
} from 'lucide-react';
import { CompassXLogo } from '@/components/common/CompassXLogo';
import AgentSidePanel from '@/modules/agents/components/side_panel/AgentSidePanel';
import { useAgentSidePanelStore } from '@/modules/agents/stores/agentSidePanelStore';
import { usePortalConfig } from '@/modules/portal/hooks/usePortalConfig';
import { CustomizeSidebarDrawer } from '@/modules/portal/components/CustomizeSidebarDrawer';
import {
  APP_IDS,
  APP_DEFINITIONS,
  DEFAULT_APP_ID,
  getDefaultPathForApp,
  getNavGroupsForApp,
  getNavItemsForApp,
  isAppId,
  resolveAppSwitchPath,
  type NavItem,
  type AppId,
  useCurrentAppId,
  useCurrentWorkspaceSlug,
  useScopedLocationPath,
  useScopedNavigate,
  useScopedPath,
} from '@/lib/appNavigation';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useMe, useMyWorkspaces, setDefaultWorkspace } from '@/lib/userManagerApi';
import { RoleSwitcherDropdown } from './RoleSwitcherDropdown';
import { AssumedContextBanner } from './AssumedContextBanner';


const EXPERIMENTAL_NAV: NavItem[] = [
  { to: '/documents', icon: FileText, label: 'Documents', end: false },
  { to: '/ingestion/connections', icon: ArrowDownToLine, label: 'API Ingestion', end: false },
  { to: '/icons', icon: Sparkles, label: 'Custom Icons', end: false },
  { to: '/logo', icon: Image, label: 'Logo Showcase', end: false },
  { to: '/design-system', icon: Palette, label: 'Design System', end: false },
];

export default function AppShell() {
  const { data: me } = useMe();
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [appMenuOpen, setAppMenuOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth < 768;
  });
  const navigate = useScopedNavigate();
  const rawNavigate = useNavigate();
  const location = useLocation();
  const scopedPathname = useScopedLocationPath();
  const appId = useCurrentAppId();
  const appPath = useScopedPath();
  const workspaceSlug = useCurrentWorkspaceSlug();
  const workspaceCtx = useWorkspaceContext();
  const isAccountAdmin = Boolean(me?.account_role === "account_admin" || me?.is_account_admin || workspaceCtx?.is_account_admin);
  const isWorkspaceAdmin = Boolean(isAccountAdmin || workspaceCtx?.current_user_role === "workspace_admin" || workspaceCtx?.current_user_role === "admin");
  const isWorkspaceDeveloper = Boolean(isWorkspaceAdmin || workspaceCtx?.current_user_role === "workspace_developer");
  const [searchParams] = useSearchParams();
  const hideSidebar = searchParams.get('sidebar') === 'false' || searchParams.get('embed') === '1';
  const isAgentSidePanelOpen = useAgentSidePanelStore((s) => s.isOpen);
  const toggleAgentSidePanel = useAgentSidePanelStore((s) => s.toggleOpen);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);
  const appMenuRef = useRef<HTMLDivElement | null>(null);
  const workspaceMenuRef = useRef<HTMLDivElement | null>(null);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [isCustomizeDrawerOpen, setIsCustomizeDrawerOpen] = useState(false);
  const { data: workspaces = [] } = useMyWorkspaces();
  const { data: portalConfig, refetch: refetchPortalConfig } = usePortalConfig();

  const activeAppId: AppId = isAppId(appId) ? appId : DEFAULT_APP_ID;

  // Role-based visible modules in top switcher:
  // Standard members/viewers only see 'portal'. Admins & Developers see Platform, Apps, Portal.
  const candidateAppIds = useMemo(() => {
    if (!isAccountAdmin && !isWorkspaceDeveloper) {
      return ['portal'] as AppId[];
    }
    return APP_IDS;
  }, [isAccountAdmin, isWorkspaceDeveloper]);

  const navGroups = useMemo(() => getNavGroupsForApp(activeAppId), [activeAppId]);
  const navItems = useMemo(() => getNavItemsForApp(activeAppId), [activeAppId]);

  const pageTitle = useMemo(() => {
    if (scopedPathname.startsWith('/home')) return activeAppId === 'apps' ? 'Apps' : activeAppId === 'portal' ? 'Portal' : 'Home';
    if (scopedPathname.startsWith('/portal')) return 'Workspace Portal';
    if (scopedPathname.startsWith('/apps')) return 'Apps';
    if (scopedPathname.startsWith('/notebooks/open')) return 'Notebook';
    if (scopedPathname.startsWith('/notebooks')) return 'Notebooks';
    if (scopedPathname.startsWith('/dashboards')) return 'Dashboards';
    if (scopedPathname.startsWith('/agents')) return 'Agents';
    if (scopedPathname.startsWith('/ai-gateway')) return 'AI Gateway';
    if (/^\/jobs\/[^/]+\/runs\//.test(scopedPathname)) return 'Run Detail';
    if (/^\/jobs\/[^/]+/.test(scopedPathname)) return 'Job Detail';
    if (scopedPathname.startsWith('/jobs')) return 'Jobs';
    if (scopedPathname.startsWith('/ingestion/connections/')) return 'Connection Detail';
    if (scopedPathname.startsWith('/ingestion/connections')) return 'API Connections';
    if (scopedPathname.startsWith('/ingestion/job-configs/')) return 'Job Config';
    if (scopedPathname.startsWith('/ingestion/job-configs')) return 'Job Configs';
    if (scopedPathname.startsWith('/ingestion/runs/')) return 'Ingestion Run';
    if (/^\/compute\/[^/]+/.test(scopedPathname)) return 'Compute Detail';
    if (scopedPathname.startsWith('/compute')) return 'Compute';
    if (scopedPathname.startsWith('/icons')) return 'Custom Icons';
    if (scopedPathname.startsWith('/logo') || scopedPathname.startsWith('/brand-logo')) return 'Logo Showcase';
    if (scopedPathname.startsWith('/design-system')) return 'Design System';
    if (scopedPathname.startsWith('/settings') || scopedPathname.startsWith('/workspace-settings')) return 'Workspace Settings';
    if (scopedPathname.startsWith('/account-settings') || scopedPathname.startsWith('/account/settings')) return 'Account Settings';
    if (scopedPathname.startsWith('/ontology') || scopedPathname.startsWith('/topology')) return 'Ontology';
    return 'CompassX';

  }, [scopedPathname, activeAppId]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!appMenuRef.current?.contains(event.target as Node)) {
        setAppMenuOpen(false);
      }
      if (!workspaceMenuRef.current?.contains(event.target as Node)) {
        setWorkspaceMenuOpen(false);
      }
      if (!profileMenuRef.current?.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
    }
    window.addEventListener('mousedown', handlePointerDown);
    return () => window.removeEventListener('mousedown', handlePointerDown);
  }, []);

  useEffect(() => {
    const updateSidebarMode = () => {
      if (typeof window === 'undefined') return;
      setIsSidebarCollapsed(window.innerWidth < 768);
    };

    updateSidebarMode();
    window.addEventListener('resize', updateSidebarMode);
    return () => window.removeEventListener('resize', updateSidebarMode);
  }, []);

  return (
    <div className="app-shell">
      {!hideSidebar && (
        <nav className={`app-sidebar glass ${isSidebarCollapsed ? 'is-collapsed' : ''}`}>
          {/* Edge Toggle Handle sitting right on the border */}
          <button
            type="button"
            className="app-sidebar-edge-toggle"
            onClick={() => setIsSidebarCollapsed((open) => !open)}
            aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isSidebarCollapsed ? <ChevronRight size={12} strokeWidth={2.4} /> : <ChevronLeft size={12} strokeWidth={2.4} />}
          </button>

          <div className="app-sidebar-header">
            <div
              className="app-sidebar-logo"
              onClick={() => navigate(getDefaultPathForApp(activeAppId))}
              style={{ cursor: 'pointer' }}
              title="Go to home"
            >
              <CompassXLogo size={26} color="var(--color-primary, #1B6EF3)" />
              <div className="app-sidebar-logo-text-wrap">
                <span className="app-sidebar-logo-text">
                  Compass<span style={{ color: 'var(--color-primary, #1B6EF3)' }}>X</span>
                </span>
              </div>
            </div>
          </div>

          {activeAppId === 'portal' ? (
            <div className="app-sidebar-section" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ flex: 1, overflowY: 'auto' }}>
                {portalConfig?.sections.map((sec) => {
                  const visibleItems = sec.items.filter((it) => it.is_visible);
                  if (visibleItems.length === 0) return null;
                  return (
                    <div key={sec.id} className="app-sidebar-group">
                      {sec.title && (
                        <div className="app-sidebar-divider-label">
                          {sec.title}
                        </div>
                      )}
                      {visibleItems.map((it) => {
                        const itemTo =
                          it.type === 'app'
                            ? `/portal/app/${it.target_id}`
                            : it.type === 'dashboard'
                            ? `/portal/dashboard/${it.target_id}`
                            : it.url || '/portal';

                        const ItemIcon =
                          it.type === 'app'
                            ? (it.app_type === 'streamlit' ? Sparkles : LayoutGrid)
                            : it.type === 'dashboard'
                            ? BarChart2
                            : Globe;

                        if (it.type === 'external_link' && it.url) {
                          return (
                            <a
                              key={it.id}
                              href={it.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="app-sidebar-link"
                              title={it.title}
                            >
                              <ItemIcon size={16} className="app-sidebar-link-icon" />
                              <span className="app-sidebar-link-label">{it.title}</span>
                            </a>
                          );
                        }

                        return (
                          <NavLink
                            key={it.id}
                            to={appPath(itemTo)}
                            className={({ isActive }) => `app-sidebar-link ${isActive ? 'is-active' : ''}`}
                            title={it.title}
                          >
                            <ItemIcon size={16} className="app-sidebar-link-icon" />
                            <span className="app-sidebar-link-label">{it.title}</span>
                          </NavLink>
                        );
                      })}
                    </div>
                  );
                })}

                {(!portalConfig?.sections || portalConfig.sections.every((s) => s.items.filter((i) => i.is_visible).length === 0)) && (
                  <div style={{ padding: '16px 12px', fontSize: '0.8rem', color: 'var(--color-text-muted)', textAlign: 'center' }}>
                    No items pinned to sidebar.
                  </div>
                )}
              </div>

              {/* Admin Customize Sidebar Button */}
              {isWorkspaceAdmin && (
                <div className="app-sidebar-group" style={{ marginTop: 'auto', paddingTop: 12, borderTop: '1px solid var(--color-border)' }}>
                  <button
                    type="button"
                    onClick={() => setIsCustomizeDrawerOpen(true)}
                    className="app-sidebar-link"
                    style={{ width: '100%', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left', color: 'var(--color-primary)' }}
                    title="Customize Sidebar"
                  >
                    <Sliders size={16} className="app-sidebar-link-icon" />
                    <span className="app-sidebar-link-label" style={{ fontWeight: 600 }}>Customize Sidebar</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="app-sidebar-section">
              {navGroups.map((group, groupIdx) => (
                <div key={group.title || `group-${groupIdx}`} className="app-sidebar-group">
                  {group.title && (
                    <div className="app-sidebar-divider-label">
                      {group.title}
                    </div>
                  )}
                  {group.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={appPath(item.to)}
                      end={item.end}
                      className={({ isActive }) => `app-sidebar-link ${isActive ? 'is-active' : ''}`}
                      title={item.label}
                    >
                      <item.icon size={16} className="app-sidebar-link-icon" />
                      <span className="app-sidebar-link-label">{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              ))}
            </div>
          )}
        </nav>
      )}

      <main className="app-main">
        <header className="app-topbar">
          <div className="app-topbar-title">{pageTitle}</div>
          <div className="app-topbar-actions">
            {/* In-Session Role Switcher */}
            <RoleSwitcherDropdown />

            {/* Workspace Switcher */}
            {workspaces.length > 1 || isAccountAdmin ? (
              <div ref={workspaceMenuRef} style={{ position: 'relative' }}>
                <button
                  className="workspace-switcher-btn glass"
                  type="button"
                  title="Switch workspace"
                  aria-expanded={workspaceMenuOpen}
                  onClick={() => setWorkspaceMenuOpen((open) => !open)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 10px',
                    height: 32,
                    borderRadius: 8,
                    fontSize: '0.82rem',
                    fontWeight: 500,
                    color: 'var(--color-text)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-surface)',
                    cursor: 'pointer',
                    transition: 'background 0.12s ease',
                  }}
                >
                  <span>{workspaceCtx?.name || 'Loading...'}</span>
                  <ChevronDown size={14} style={{ opacity: 0.7 }} />
                </button>
                {workspaceMenuOpen && (
                  <div 
                    className="app-switcher-menu glass animate-fade-in" 
                    style={{ 
                      position: 'absolute',
                      top: 'calc(100% + 8px)',
                      right: 0,
                      minWidth: 220,
                      padding: 8,
                      borderRadius: 14,
                      boxShadow: '0 18px 48px rgba(15, 23, 42, 0.18)',
                      zIndex: 99999,
                    }}
                  >
                    <div className="app-switcher-menu-header">
                      <div className="app-switcher-menu-title">Switch workspace</div>
                    </div>
                    {workspaces.map((ws) => {
                      const wsSlug = ws.workspace_slug || ws.workspace_id;
                      const wsName = ws.workspace_name || wsSlug;
                      const isActive = wsSlug === workspaceSlug || ws.workspace_id === workspaceCtx?.id;
                      return (
                        <button
                          key={ws.workspace_id}
                          type="button"
                          onClick={() => {
                            setWorkspaceMenuOpen(false);
                            try {
                              localStorage.setItem("compassx_last_workspace", ws.workspace_id);
                            } catch {}
                            setDefaultWorkspace(ws.workspace_id).catch(() => {});
                            window.location.href = `/w/${wsSlug}/${activeAppId}${scopedPathname}${location.search}${location.hash}`;
                          }}
                          className={`app-switcher-option ${isActive ? 'is-active' : ''}`}
                        >
                          <span>{wsName}</span>
                          {isActive && <span className="app-switcher-option-badge">Active</span>}
                        </button>
                      );
                    })}
                    {workspaces.length === 0 && (
                      <div style={{ padding: '8px 12px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                        No other workspaces
                      </div>
                    )}
                    {isAccountAdmin && (
                      <>
                        <div style={{ borderTop: '1px solid var(--color-border)', margin: '6px 0' }} />
                        <button
                          type="button"
                          onClick={() => {
                            setWorkspaceMenuOpen(false);
                            rawNavigate('/workspace/create');
                          }}
                          className="app-switcher-option"
                          style={{
                            color: 'var(--color-primary)',
                            fontWeight: 500,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                          }}
                        >
                          <span>+ Create workspace</span>
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ) : (
              /* Single workspace & no creation permission — render static workspace label without dropdown */
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '4px 10px',
                  height: 32,
                  borderRadius: 8,
                  fontSize: '0.82rem',
                  fontWeight: 500,
                  color: 'var(--color-text-muted)',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  userSelect: 'none',
                }}
              >
                <span>{workspaceCtx?.name || ''}</span>
              </div>
            )}

            <div ref={appMenuRef} style={{ position: 'relative' }}>
              <button
                className="app-switcher-btn"
                type="button"
                title="Switch app"
                aria-expanded={appMenuOpen}
                onClick={() => setAppMenuOpen((open) => !open)}
              >
                <span className="app-switcher-dots" aria-hidden="true" />
              </button>
              {appMenuOpen && (
                <div className="app-switcher-menu glass">
                  <div className="app-switcher-menu-header">
                    <div className="app-switcher-menu-title">Switch app</div>
                  </div>
                  {candidateAppIds.map((candidate) => (
                    <button
                    key={candidate}
                    type="button"
                    onClick={() => {
                      setAppMenuOpen(false);
                        rawNavigate(`${resolveAppSwitchPath(candidate, scopedPathname, workspaceSlug)}${location.search}${location.hash}`);
                      }}
                      className={`app-switcher-option ${candidate === activeAppId ? 'is-active' : ''}`}
                    >
                      <span>{APP_DEFINITIONS[candidate].label}</span>
                      {candidate === activeAppId && <span className="app-switcher-option-badge">Current</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              className={`app-topbar-icon-btn app-nova-btn ${isAgentSidePanelOpen ? 'is-active' : ''}`}
              type="button"
              onClick={toggleAgentSidePanel}
              title={isAgentSidePanelOpen ? 'Close Agent Copilot' : 'Open Agent Copilot'}
            >
              <Sparkles size={16} strokeWidth={2.1} />
            </button>
            <div ref={profileMenuRef} style={{ position: 'relative' }}>
              <button
                className="app-topbar-avatar"
                type="button"
                title={me ? `${me.display_name || me.email}` : "User menu"}
                aria-expanded={profileMenuOpen}
                onClick={() => setProfileMenuOpen((open) => !open)}
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: me ? "var(--color-primary)" : "transparent",
                  color: me ? "#ffffff" : "var(--color-text-muted)",
                  fontWeight: 700,
                  fontSize: 13,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: me ? "none" : "none",
                }}
              >
                {me ? (me.display_name || me.email || 'U')[0].toUpperCase() : <CircleUserRound size={18} />}
              </button>
              {profileMenuOpen && (
                <div
                  className="glass"
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 8px)',
                    right: 0,
                    minWidth: 240,
                    padding: 8,
                    borderRadius: 14,
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-surface)',
                    zIndex: 99999,
                    boxShadow: 'var(--shadow-md)',
                  }}
                >
                  {/* Logged-In User Profile Header */}
                  <div
                    style={{
                      padding: '12px 14px',
                      borderBottom: '1px solid var(--color-border)',
                      marginBottom: '8px',
                      background: 'var(--color-surface-hover)',
                      borderRadius: '10px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div
                        style={{
                          width: '36px',
                          height: '36px',
                          borderRadius: '50%',
                          background: 'var(--color-primary)',
                          color: '#fff',
                          fontWeight: 700,
                          fontSize: '14px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        {(me?.display_name || me?.email || 'U')[0].toUpperCase()}
                      </div>
                      <div style={{ overflow: 'hidden', minWidth: 0 }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: '0.88rem',
                            color: 'var(--color-text)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {me?.display_name || 'User Profile'}
                        </div>
                        <div
                          style={{
                            fontSize: '0.76rem',
                            color: 'var(--color-text-muted)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {me?.email || ''}
                        </div>
                      </div>
                    </div>
                    <div style={{ marginTop: '10px', display: 'flex', gap: '6px' }}>
                      {isAccountAdmin ? (
                        <span
                          title="Account Administrator"
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '999px',
                            background: 'var(--color-success-bg)',
                            color: 'var(--color-success)',
                            border: '1px solid var(--color-success)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                          }}
                        >
                          ACCOUNT ADMIN
                        </span>
                      ) : workspaceCtx?.current_user_role ? (
                        <span
                          title="Workspace Role"
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '999px',
                            background: 'var(--color-primary-bg)',
                            color: 'var(--color-primary)',
                            border: '1px solid var(--color-primary)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                          }}
                        >
                          {workspaceCtx.current_user_role.replace(/_/g, ' ')}
                        </span>
                      ) : me?.account_role ? (
                        <span
                          title="Account Role"
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '999px',
                            background: 'var(--color-primary-bg)',
                            color: 'var(--color-primary)',
                            border: '1px solid var(--color-primary)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                          }}
                        >
                          {me.account_role.replace(/_/g, ' ')}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  {/* Account Console & Account Settings — Account Admin Only */}
                  {isAccountAdmin && (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          setProfileMenuOpen(false);
                          rawNavigate('/account');
                        }}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          padding: '8px 12px',
                          borderRadius: 8,
                          border: 'none',
                          background: 'transparent',
                          color: 'var(--color-text)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          fontSize: '0.84rem',
                        }}
                      >
                        <Settings size={15} />
                        <span style={{ flex: 1 }}>Account Console</span>
                        <ChevronRight size={13} style={{ opacity: 0.45 }} />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setProfileMenuOpen(false);
                          navigate('/account/settings');
                        }}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          padding: '8px 12px',
                          borderRadius: 8,
                          border: 'none',
                          background: 'transparent',
                          color: 'var(--color-text)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          fontSize: '0.84rem',
                        }}
                      >
                        <Sliders size={15} />
                        <span style={{ flex: 1 }}>Account Settings</span>
                        <ChevronRight size={13} style={{ opacity: 0.45 }} />
                      </button>
                    </>
                  )}

                  {/* Workspace Settings */}
                  <button
                    type="button"
                    onClick={() => {
                      setProfileMenuOpen(false);
                      navigate('/settings');
                    }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 12px',
                      borderRadius: 8,
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--color-text)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: '0.84rem',
                    }}
                  >
                    <Sliders size={15} />
                    <span style={{ flex: 1 }}>Workspace Settings</span>
                    <ChevronRight size={13} style={{ opacity: 0.45 }} />
                  </button>

                  {/* Workspace Members — Workspace / Account Admin Only */}
                  {isWorkspaceAdmin && workspaceCtx && (
                    <button
                      type="button"
                      onClick={() => {
                        setProfileMenuOpen(false);
                        rawNavigate(`/account/workspaces/${workspaceCtx.id}/members`);
                      }}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '8px 12px',
                        borderRadius: 8,
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--color-text)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        fontSize: '0.84rem',
                      }}
                    >
                      <CircleUserRound size={15} />
                      <span style={{ flex: 1 }}>Workspace Members</span>
                      <ChevronRight size={13} style={{ opacity: 0.45 }} />
                    </button>
                  )}

                  <div
                    style={{
                      margin: '6px 0',
                      padding: '10px 12px 6px',
                      borderTop: '1px solid var(--color-border)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        fontSize: '0.76rem',
                        fontWeight: 600,
                        color: 'var(--color-text-muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
                      <FlaskConical size={13} />
                      <span>Experimental Features</span>
                    </div>
                  </div>
                  {EXPERIMENTAL_NAV.map((item) => (
                    <button
                      key={item.to}
                      type="button"
                      onClick={() => {
                        setProfileMenuOpen(false);
                        navigate(item.to);
                      }}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '8px 12px',
                        borderRadius: 8,
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--color-text)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        fontSize: '0.84rem',
                      }}
                    >
                      <item.icon size={15} />
                      <span style={{ flex: 1 }}>{item.label}</span>
                      <ChevronRight size={13} style={{ opacity: 0.45 }} />
                    </button>
                  ))}

                  <div style={{ borderTop: '1px solid var(--color-border)', margin: '6px 0' }} />
                  <button
                    type="button"
                    onClick={() => {
                      setProfileMenuOpen(false);
                      import('@/lib/queryClient').then((m) => m.purgeAllClientState());
                      rawNavigate('/login');
                    }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 12px',
                      borderRadius: 8,
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--color-danger)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: '0.84rem',
                    }}
                  >
                    <LogOut size={15} />
                    <span style={{ flex: 1 }}>Log Out</span>
                  </button>

                  <div
                    style={{
                      borderTop: '1px solid var(--color-border)',
                      margin: '6px 0 0',
                      padding: '8px 12px 2px',
                      textAlign: 'center',
                      fontSize: '0.73rem',
                      fontWeight: 500,
                      color: 'var(--color-text-muted)',
                      letterSpacing: '0.02em',
                      userSelect: 'none',
                    }}
                  >
                    CompassX v{typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.4.0'}
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>
        <AssumedContextBanner />

        <div className={`app-workspace ${isAgentSidePanelOpen ? 'has-nova-sidebar' : ''}`}>
          <div className="app-content">
            <div className="page-content">
              <Outlet />
            </div>
          </div>

          {isAgentSidePanelOpen && (
            <aside className="app-nova-sidebar" style={{ width: 'auto', flexShrink: 0 }}>
              <AgentSidePanel />
            </aside>
          )}
        </div>
      </main>

      <CustomizeSidebarDrawer
        isOpen={isCustomizeDrawerOpen}
        onClose={() => {
          setIsCustomizeDrawerOpen(false);
          refetchPortalConfig();
        }}
        currentConfig={portalConfig}
      />
    </div>
  );
}
