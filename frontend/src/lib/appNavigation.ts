import { useCallback } from 'react';
import { useLocation, useNavigate, useParams, type NavigateOptions, type To } from 'react-router-dom';
import type { ElementType } from 'react';
import { Briefcase, Code2, Layers, Zap, LayoutDashboard, FileText, Database, GitBranch, Cable, BookOpen, ServerCog, History, Activity, ArrowDownToLine, Home } from 'lucide-react';

export const APP_IDS = ['platform', 'apps', 'business_center'] as const;
export type AppId = (typeof APP_IDS)[number];

export const DEFAULT_APP_ID: AppId = 'platform';

const UNSCOPED_PREFIXES = ['/public', '/workspace'];
const LEGACY_APP_ID_ALIASES: Record<string, AppId> = {
  business: 'business_center',
  business_center: 'business_center',
};

export type NavItem = {
  to: string;
  icon: ElementType;
  label: string;
  end?: boolean;
};

type AppDefinition = {
  id: AppId;
  label: string;
  defaultPath: string;
  navItems: NavItem[];
  allowedPrefixes: string[];
};

export const APP_DEFINITIONS: Record<AppId, AppDefinition> = {
  platform: {
    id: 'platform',
    label: 'Platform',
    defaultPath: '/home',
    navItems: [
      { to: '/home', icon: Home, label: 'Home', end: true },
      { to: '/jobs', icon: Briefcase, label: 'Jobs', end: false },
      { to: '/notebooks', icon: Code2, label: 'Notebooks', end: false },
      { to: '/dashboards', icon: LayoutDashboard, label: 'Dashboards', end: false },      { to: '/agents', icon: Layers, label: 'Agents', end: false },
      { to: '/data-catalog', icon: BookOpen, label: 'Data Catalog', end: false },
      { to: '/sql-warehouse/explorer', icon: Database, label: 'Data Explorer', end: false },
      { to: '/sql-warehouse/editor', icon: Code2, label: 'SQL Editor', end: false },
      { to: '/sql-warehouse/warehouses', icon: ServerCog, label: 'SQL Warehouses', end: false },
      { to: '/sql-warehouse/history', icon: History, label: 'Query History', end: false },
      { to: '/connections', icon: Cable, label: 'Connections', end: false },
      { to: '/ingestion/connections', icon: ArrowDownToLine, label: 'API Ingestion', end: false },
      { to: '/compute', icon: Zap, label: 'Compute', end: false },
      { to: '/monitoring', icon: Activity, label: 'Monitoring', end: false },
    ],
    allowedPrefixes: ['/home', '/jobs', '/notebooks', '/agents', '/data-catalog', '/sql-warehouse', '/connections', '/ingestion', '/compute', '/monitoring', '/dashboards', '/apps_development'],
  },
  apps: {
    id: 'apps',
    label: 'Apps',
    defaultPath: '/assets',
    navItems: [
      { to: '/assets', icon: GitBranch, label: 'Assets', end: true },
      { to: '/apps_development', icon: Code2, label: 'App Developer', end: false },
    ],
    allowedPrefixes: ['/assets', '/apps_development'],
  },
  business_center: {
    id: 'business_center',
    label: 'Business Center',
    defaultPath: '/dashboards',
    navItems: [
      { to: '/dashboards', icon: LayoutDashboard, label: 'Dashboards', end: false },
    ],
    allowedPrefixes: ['/dashboards'],
  },
};

export function isAppId(value: string | undefined | null): value is AppId {
  return !!value && APP_IDS.includes(value as AppId);
}

export function normalizeAppId(value: string | undefined | null): AppId | null {
  if (isAppId(value)) return value;
  return value ? LEGACY_APP_ID_ALIASES[value] ?? null : null;
}

export function getDefaultPathForApp(appId: AppId): string {
  return APP_DEFINITIONS[appId].defaultPath;
}

export function getNavItemsForApp(appId: AppId): NavItem[] {
  return APP_DEFINITIONS[appId].navItems;
}

export function stripAppScope(pathname: string): string {
  const segments = pathname.split('/').filter(Boolean);
  if (!segments.length) return '/';
  // Strip /w/:slug/:appId prefix
  if (segments[0] === 'w' && segments.length >= 3) {
    const rest = segments.slice(3).join('/');
    return rest ? `/${rest}` : '/';
  }
  // Strip /:appId prefix (legacy)
  if (isAppId(segments[0]) || segments[0] in LEGACY_APP_ID_ALIASES) {
    const rest = segments.slice(1).join('/');
    return rest ? `/${rest}` : '/';
  }
  return pathname.startsWith('/') ? pathname : `/${pathname}`;
}

export function isPathAllowedForApp(appId: AppId, pathname: string): boolean {
  const normalized = stripAppScope(pathname);
  if (normalized === '/') return false;
  return APP_DEFINITIONS[appId].allowedPrefixes.some(
    (prefix) => normalized === prefix || normalized.startsWith(`${prefix}/`) || normalized.startsWith(`${prefix}?`),
  );
}

export function resolveAppSwitchPath(targetAppId: AppId, pathname: string, workspaceSlug?: string): string {
  const normalized = stripAppScope(pathname);
  const featurePath = isPathAllowedForApp(targetAppId, normalized)
    ? normalized
    : getDefaultPathForApp(targetAppId);
  if (workspaceSlug) {
    return `/w/${workspaceSlug}/${targetAppId}${featurePath}`;
  }
  return `/${targetAppId}${featurePath}`;
}

export function scopePath(appId: AppId, to: string, workspaceSlug?: string): string {
  if (!to) return workspaceSlug ? `/w/${workspaceSlug}/${appId}` : `/${appId}`;
  if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(to)) return to;
  if (UNSCOPED_PREFIXES.some((prefix) => to === prefix || to.startsWith(`${prefix}/`))) return to;
  if (to.startsWith('/')) {
    const normalized = stripAppScope(to);
    if (workspaceSlug) {
      return normalized === '/' ? `/w/${workspaceSlug}/${appId}` : `/w/${workspaceSlug}/${appId}${normalized}`;
    }
    return normalized === '/' ? `/${appId}` : `/${appId}${normalized}`;
  }
  return to;
}

/** Get workspace slug from current URL params (expects /w/:workspaceSlug/:appId/*) */
export function useCurrentWorkspaceSlug(): string | undefined {
  const { workspaceSlug } = useParams();
  return workspaceSlug;
}

export function useCurrentAppId(): AppId {
  const { appId } = useParams();
  return normalizeAppId(appId) ?? DEFAULT_APP_ID;
}

export function useScopedPath() {
  const appId = useCurrentAppId();
  const workspaceSlug = useCurrentWorkspaceSlug();
  return useCallback((to: string) => scopePath(appId, to, workspaceSlug), [appId, workspaceSlug]);
}

export function useScopedNavigate() {
  const navigate = useNavigate();
  const appId = useCurrentAppId();
  const workspaceSlug = useCurrentWorkspaceSlug();

  return useCallback(
    (to: To | number, options?: NavigateOptions) => {
      if (typeof to === 'number') {
        navigate(to);
        return;
      }
      if (typeof to === 'string') {
        navigate(scopePath(appId, to, workspaceSlug), options);
        return;
      }
      navigate(to, options);
    },
    [appId, workspaceSlug, navigate],
  );
}

export function useScopedLocationPath() {
  const location = useLocation();
  return stripAppScope(location.pathname);
}

