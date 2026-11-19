import {
  AlarmClock,
  BarChart2,
  Building2,
  FolderClosed,
  GitBranch,
  Globe,
  Inbox,
  Layers,
  LayoutGrid,
  ListChecks,
  PenTool,
  Printer,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { CURATED_TECH_DATA_ICONS } from '@/components/icons/TechDataIcons';

export interface SidebarIconChoice {
  name: string;
  label: string;
  component: LucideIcon;
}

/** Same glyphs the EAM menu uses. These were not in the custom icon catalog. */
export const EAM_NAV_ICONS: SidebarIconChoice[] = [
  { name: 'Inbox', label: 'Records', component: Inbox },
  { name: 'FolderClosed', label: 'Documents', component: FolderClosed },
  { name: 'GitBranch', label: 'Workflows', component: GitBranch },
  { name: 'Layers', label: 'Entities', component: Layers },
  { name: 'PenTool', label: 'Forms', component: PenTool },
  { name: 'Printer', label: 'Reports', component: Printer },
  { name: 'ListChecks', label: 'Lists', component: ListChecks },
  { name: 'ShieldCheck', label: 'Conditions', component: ShieldCheck },
  { name: 'Users', label: 'People', component: Users },
  { name: 'Building2', label: 'Asset hierarchy', component: Building2 },
  { name: 'ShieldAlert', label: 'Safety', component: ShieldAlert },
  { name: 'AlarmClock', label: 'Escalations', component: AlarmClock },
  { name: 'Settings', label: 'Settings', component: Settings },
  { name: 'LayoutGrid', label: 'Grid', component: LayoutGrid },
  { name: 'BarChart2', label: 'Dashboard', component: BarChart2 },
  { name: 'Globe', label: 'Link', component: Globe },
  { name: 'Sparkles', label: 'Spark', component: Sparkles },
];

const EAM_ICON_FOR_PATH: Record<string, string> = {
  '#/records': 'Inbox',
  '#/documents': 'FolderClosed',
  '#/workflows': 'GitBranch',
  '#/entities': 'Layers',
  '#/forms': 'PenTool',
  '#/reports': 'Printer',
  '#/lists': 'ListChecks',
  '#/conditions': 'ShieldCheck',
  '#/people': 'Users',
  '#/organizations': 'Building2',
  '#/safety': 'ShieldAlert',
  '#/escalations': 'AlarmClock',
  '#/settings': 'Settings',
};

export function iconForPath(path?: string | null): string | undefined {
  if (!path) return undefined;
  return EAM_ICON_FOR_PATH[path];
}

export function findSidebarIcon(name?: string | null): SidebarIconChoice | undefined {
  if (!name) return undefined;
  return EAM_NAV_ICONS.find((icon) => icon.name === name);
}

export function resolveScreenIcon(item: { icon?: string | null; type: string; app_type?: string | null; path?: string | null }) {
  const named = findSidebarIcon(item.icon);
  if (named && item.icon !== 'LayoutGrid') return named.component;
  const curated = CURATED_TECH_DATA_ICONS.find((icon) => icon.name === item.icon);
  if (curated) return curated.component;
  const fromPath = findSidebarIcon(iconForPath(item.path));
  if (fromPath) return fromPath.component;
  if (named) return named.component;
  if (item.type === 'dashboard') return BarChart2;
  if (item.type === 'external_link') return Globe;
  if (item.app_type === 'streamlit') return Sparkles;
  return LayoutGrid;
}

export function selectedIconName(item: { icon?: string | null; path?: string | null }): string {
  if (item.icon && item.icon !== 'LayoutGrid' && (findSidebarIcon(item.icon) || CURATED_TECH_DATA_ICONS.some((icon) => icon.name === item.icon))) {
    return item.icon;
  }
  return iconForPath(item.path) || (findSidebarIcon(item.icon) ? item.icon || '' : '');
}
