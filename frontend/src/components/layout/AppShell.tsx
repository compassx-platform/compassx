import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  FileText,
  Database,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  CircleUserRound,
  Settings,
  LogOut,
  FlaskConical,
  Grid2x2,
  Plus,
  Pencil,
  Trash2,
  LayoutDashboard,
  Palette,
  Image,
  ArrowDownToLine,
} from 'lucide-react';
import { CompassXLogo } from '@/components/common/CompassXLogo';
import AppNovaSidebar from '@/modules/nova/components/AppNovaSidebar';
import { useNovaStore } from '@/modules/nova/stores/novaStore';
import { useDashboards } from '@/modules/dashboards/hooks/useDashboard';
import { useApps } from '@/modules/apps_development/hooks/useApps';
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
  const isWorkspaceAdmin = Boolean(isAccountAdmin || workspaceCtx?.current_user_role === "workspace_admin");
  const [searchParams] = useSearchParams();
  const hideSidebar = searchParams.get('sidebar') === 'false' || searchParams.get('embed') === '1';
  const isNovaOpen = useNovaStore((s) => s.isOpen);
  const toggleNova = useNovaStore((s) => s.toggleOpen);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);
  const appMenuRef = useRef<HTMLDivElement | null>(null);
  const workspaceMenuRef = useRef<HTMLDivElement | null>(null);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const { data: workspaces = [] } = useMyWorkspaces();

  // Queries for custom links picker
  const { data: dashboards = [] } = useDashboards();
  const { data: apps = [] } = useApps(workspaceCtx?.id ?? '');

  // State for custom links
  const [customLinks, setCustomLinks] = useState<Array<{ id: string; name: string; url: string; type: 'dashboard' | 'app' }>>([]);
  
  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLinkId, setEditingLinkId] = useState<string | null>(null);
  const [targetType, setTargetType] = useState<'dashboard' | 'app'>('dashboard');
  const [selectedItem, setSelectedItem] = useState<string>('');
  const [customName, setCustomName] = useState('');
  const [customUrl, setCustomUrl] = useState('');

  // Load custom links on workspace change
  useEffect(() => {
    if (workspaceCtx?.id) {
      const stored = localStorage.getItem(`compassx_bc_links_${workspaceCtx.id}`);
      if (stored) {
        try {
          setCustomLinks(JSON.parse(stored));
        } catch (e) {
          console.error("Failed to parse custom links", e);
        }
      } else {
        setCustomLinks([]);
      }
    } else {
      setCustomLinks([]);
    }
  }, [workspaceCtx?.id]);

  const handleSaveLink = () => {
    if (!customName.trim() || !customUrl.trim() || !workspaceCtx?.id) return;

    let updatedLinks = [...customLinks];
    if (editingLinkId) {
      updatedLinks = updatedLinks.map(link => 
        link.id === editingLinkId 
          ? { ...link, name: customName.trim(), url: customUrl.trim() }
          : link
      );
    } else {
      updatedLinks.push({
        id: Math.random().toString(36).substring(2, 9),
        name: customName.trim(),
        url: customUrl.trim(),
        type: targetType,
      });
    }

    localStorage.setItem(`compassx_bc_links_${workspaceCtx.id}`, JSON.stringify(updatedLinks));
    setCustomLinks(updatedLinks);
    setIsModalOpen(false);
  };

  const handleDeleteLink = (id: string) => {
    if (!workspaceCtx?.id) return;
    if (!confirm('Are you sure you want to delete this custom sidebar link?')) return;
    const updatedLinks = customLinks.filter(link => link.id !== id);
    localStorage.setItem(`compassx_bc_links_${workspaceCtx.id}`, JSON.stringify(updatedLinks));
    setCustomLinks(updatedLinks);
  };

  const handleEditLink = (link: { id: string; name: string; url: string; type: 'dashboard' | 'app' }) => {
    setEditingLinkId(link.id);
    setTargetType(link.type);
    setCustomName(link.name);
    setCustomUrl(link.url);
    
    const match = link.url.match(/\/([^/]+)\/(edit|main)$/);
    if (match) {
      setSelectedItem(match[1]);
    } else {
      setSelectedItem('');
    }
    
    setIsModalOpen(true);
  };

  const handleOpenAddModal = () => {
    setEditingLinkId(null);
    setTargetType('dashboard');
    setSelectedItem('');
    setCustomName('');
    setCustomUrl('');
    setIsModalOpen(true);
  };

  const activeAppId: AppId = isAppId(appId) ? appId : DEFAULT_APP_ID;

  const navGroups = useMemo(() => getNavGroupsForApp(activeAppId), [activeAppId]);
  const navItems = useMemo(() => getNavItemsForApp(activeAppId), [activeAppId]);

  const pageTitle = useMemo(() => {
    if (scopedPathname.startsWith('/home')) return 'Home';
    if (scopedPathname.startsWith('/apps_development')) return 'App Developer';
    if (scopedPathname.startsWith('/notebooks/open')) return 'Notebook';
    if (scopedPathname.startsWith('/notebooks')) return 'Notebooks';
    if (scopedPathname.startsWith('/dashboards')) return 'Dashboards';
    if (scopedPathname.startsWith('/agents')) return 'Agents';
    if (scopedPathname.startsWith('/assets/types')) return 'Asset Types';
    if (scopedPathname.startsWith('/assets')) return 'Assets';
    if (/^\/jobs\/[^/]+\/runs\//.test(scopedPathname)) return 'Run Detail';
    if (/^\/jobs\/[^/]+/.test(scopedPathname)) return 'Job Detail';
    if (scopedPathname.startsWith('/jobs')) return 'Jobs';
    if (scopedPathname.startsWith('/ingestion/connections/')) return 'Connection Detail';
    if (scopedPathname.startsWith('/ingestion/connections')) return 'API Connections';
    if (scopedPathname.startsWith('/ingestion/job-configs/')) return 'Job Config';
    if (scopedPathname.startsWith('/ingestion/job-configs')) return 'Job Configs';
    if (scopedPathname.startsWith('/ingestion/runs/')) return 'Ingestion Run';
    if (scopedPathname.startsWith('/icons')) return 'Custom Icons';
    if (scopedPathname.startsWith('/logo') || scopedPathname.startsWith('/brand-logo')) return 'Logo Showcase';
    if (scopedPathname.startsWith('/design-system')) return 'Design System';
    return 'CompassX';

  }, [scopedPathname]);

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

          <div className="app-sidebar-section">
            {activeAppId === 'business_center' ? (
              <>
                {customLinks.map((link) => (
                  <div key={link.id} className="app-sidebar-link-container">
                    <NavLink
                      to={link.url}
                      className={({ isActive }) => `app-sidebar-link ${isActive ? 'is-active' : ''}`}
                      style={{ flex: 1, paddingRight: '2.5rem' }}
                      title={link.name}
                    >
                      {link.type === 'dashboard' ? (
                        <LayoutDashboard size={16} className="app-sidebar-link-icon" />
                      ) : (
                        <Grid2x2 size={16} className="app-sidebar-link-icon" />
                      )}
                      <span className="app-sidebar-link-label" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {link.name}
                      </span>
                    </NavLink>
                    <div className="custom-link-actions">
                      <button
                        type="button"
                        style={{
                          border: 'none',
                          background: 'transparent',
                          color: 'var(--sb-muted)',
                          cursor: 'pointer',
                          padding: '2px',
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleEditLink(link);
                        }}
                        title="Edit link"
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        type="button"
                        style={{
                          border: 'none',
                          background: 'transparent',
                          color: 'var(--color-danger)',
                          cursor: 'pointer',
                          padding: '2px',
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleDeleteLink(link.id);
                        }}
                        title="Delete link"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                ))}
                
                <button
                  type="button"
                  className="app-sidebar-link"
                  title="Add Link"
                  style={{
                    marginTop: '0.5rem',
                    border: '1px dashed var(--sb-border)',
                    background: 'transparent',
                    color: 'var(--color-primary)',
                    justifyContent: 'center',
                    cursor: 'pointer',
                  }}
                  onClick={handleOpenAddModal}
                >
                  <Plus size={14} />
                  <span className="app-sidebar-link-label">Add Link</span>
                </button>
              </>
            ) : (
              navGroups.map((group, groupIdx) => (
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
              ))
            )}
          </div>
        </nav>
      )}

      <main className="app-main">
        <header className="app-topbar">
          <div className="app-topbar-title">{pageTitle}</div>
          <div className="app-topbar-actions">
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
                  {APP_IDS.map((candidate) => (
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
                  <div style={{ borderTop: '1px solid var(--color-border)', margin: '6px 0' }} />
                  <button
                    type="button"
                    onClick={() => {
                      setAppMenuOpen(false);
                      rawNavigate(`/w/${workspaceSlug}/${activeAppId}/apps_development${location.search}${location.hash}`);
                    }}
                    className={`app-switcher-option ${scopedPathname.startsWith('/apps_development') ? 'is-active' : ''}`}
                  >
                    <span>App Developer</span>
                    {scopedPathname.startsWith('/apps_development') && <span className="app-switcher-option-badge">Current</span>}
                  </button>
                </div>
              )}
            </div>
            <button
              className={`app-topbar-icon-btn app-nova-btn ${isNovaOpen ? 'is-active' : ''}`}
              type="button"
              onClick={toggleNova}
              title={isNovaOpen ? 'Close Nova' : 'Open Nova'}
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

                  {/* Account Console — Account Admin Only */}
                  {isAccountAdmin && (
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
                  )}

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
                    CompassX v{typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.3.0'}
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className={`app-workspace ${isNovaOpen ? 'has-nova-sidebar' : ''}`}>
          <div className="app-content">
            <div className="page-content">
              <Outlet />
            </div>
          </div>

          {isNovaOpen && (
            <aside className="app-nova-sidebar">
              <AppNovaSidebar />
            </aside>
          )}
        </div>
      </main>

      {isModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            backdropFilter: 'blur(4px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onClick={(e) => e.target === e.currentTarget && setIsModalOpen(false)}
        >
          <div
            className="glass"
            style={{
              borderRadius: '16px',
              padding: '24px',
              width: '480px',
              maxWidth: '90%',
              display: 'flex',
              flexDirection: 'column',
              gap: '18px',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              boxShadow: '0 20px 50px rgba(0,0,0,0.2)',
              animation: 'fadeIn 0.2s ease-out',
            }}
          >
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
              {editingLinkId ? 'Edit Sidebar Link' : 'Add Link to Sidebar'}
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label className="label">Type</label>
              <div className="toggle-group">
                <button
                  type="button"
                  className={`toggle-btn ${targetType === 'dashboard' ? 'active' : ''}`}
                  onClick={() => {
                    setTargetType('dashboard');
                    setSelectedItem('');
                    setCustomName('');
                    setCustomUrl('');
                  }}
                >
                  Dashboard
                </button>
                <button
                  type="button"
                  className={`toggle-btn ${targetType === 'app' ? 'active' : ''}`}
                  onClick={() => {
                    setTargetType('app');
                    setSelectedItem('');
                    setCustomName('');
                    setCustomUrl('');
                  }}
                >
                  App
                </button>
              </div>
            </div>

            {targetType === 'dashboard' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label className="label">Select Dashboard</label>
                <select
                  className="form-input"
                  value={selectedItem}
                  onChange={(e) => {
                    const id = e.target.value;
                    setSelectedItem(id);
                    const found = dashboards.find(d => d.id === id);
                    if (found) {
                      setCustomName(found.name);
                      setCustomUrl(`/w/${workspaceSlug}/business_center/dashboards/${found.id}`);
                    }
                  }}
                >
                  <option value="">-- Choose Dashboard --</option>
                  {dashboards.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} {d.isDraft ? '(Draft)' : ''}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label className="label">Select App</label>
                <select
                  className="form-input"
                  value={selectedItem}
                  onChange={(e) => {
                    const id = e.target.value;
                    setSelectedItem(id);
                    const found = apps.find(a => a.app_id === id);
                    if (found) {
                      setCustomName(found.name);
                      setCustomUrl(`/w/${workspaceSlug}/business_center/apps_development/${found.app_id}/main`);
                    }
                  }}
                >
                  <option value="">-- Choose App --</option>
                  {apps.map((a) => (
                    <option key={a.app_id} value={a.app_id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label className="label">Display Name</label>
              <input
                type="text"
                className="form-input"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="Link Label"
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label className="label">URL</label>
              <input
                type="text"
                className="form-input"
                value={customUrl}
                onChange={(e) => setCustomUrl(e.target.value)}
                placeholder="/w/workspace/..."
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
              <button
                className="btn-outline"
                type="button"
                onClick={() => setIsModalOpen(false)}
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                type="button"
                onClick={handleSaveLink}
                disabled={!customName.trim() || !customUrl.trim()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}






