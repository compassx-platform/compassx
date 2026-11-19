import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useCurrentWorkspaceSlug } from '@/lib/appNavigation';

export interface PortalItem {
  id: string;
  type: 'app' | 'dashboard' | 'external_link';
  target_id: string;
  title: string;
  icon?: string | null;
  is_visible: boolean;
  order: number;
  url?: string | null;
  path?: string | null;
  app_type?: string | null;
  status?: string | null;
}

export interface PortalSection {
  id: string;
  title: string;
  items: PortalItem[];
}

export interface PortalSettings {
  logo?: string | null;
}

export interface PortalConfig {
  id?: string;
  workspace_id: string;
  workspace_slug?: string | null;
  sections: PortalSection[];
  settings?: PortalSettings | null;
  updated_at?: string | null;
}

export interface AvailableAppItem {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  app_type: string;
  status: string;
  route: string;
}

export interface AvailableDashboardItem {
  id: string;
  name: string;
  description?: string | null;
  is_draft: boolean;
  published_at?: string | null;
}

export interface PortalAvailableItems {
  apps: AvailableAppItem[];
  dashboards: AvailableDashboardItem[];
}

export function usePortalConfig() {
  const workspaceSlug = useCurrentWorkspaceSlug();

  return useQuery<PortalConfig>({
    queryKey: ['portal-config', workspaceSlug],
    queryFn: async () => {
      const { data } = await api.get('/portal/config', {
        params: { workspace_slug: workspaceSlug },
      });
      return data;
    },
    staleTime: 1000 * 30, // 30s
    enabled: Boolean(workspaceSlug),
  });
}

export function useUpdatePortalConfig() {
  const queryClient = useQueryClient();
  const workspaceSlug = useCurrentWorkspaceSlug();

  return useMutation({
    mutationFn: async (sections: PortalSection[]) => {
      const { data } = await api.put(
        '/portal/config',
        { sections },
        { params: { workspace_slug: workspaceSlug } }
      );
      return data;
    },
    onSuccess: (updatedConfig: PortalConfig) => {
      queryClient.setQueryData(['portal-config', workspaceSlug], (current: PortalConfig | undefined) => ({
        ...updatedConfig,
        settings: updatedConfig.settings ?? current?.settings,
      }));
      queryClient.invalidateQueries({ queryKey: ['portal-config', workspaceSlug] });
    },
  });
}

export function useUpdatePortalSettings() {
  const queryClient = useQueryClient();
  const workspaceSlug = useCurrentWorkspaceSlug();

  return useMutation({
    mutationFn: async (logo: string | null) => {
      const { data } = await api.patch(
        '/portal/settings',
        { logo },
        { params: { workspace_slug: workspaceSlug } }
      );
      return data as PortalSettings;
    },
    onSuccess: (settings) => {
      queryClient.setQueryData(['portal-config', workspaceSlug], (current: PortalConfig | undefined) => (
        current ? { ...current, settings } : current
      ));
    },
  });
}

export function usePortalAvailableItems() {
  const workspaceSlug = useCurrentWorkspaceSlug();

  return useQuery<PortalAvailableItems>({
    queryKey: ['portal-available-items', workspaceSlug],
    queryFn: async () => {
      const { data } = await api.get('/portal/available-items', {
        params: { workspace_slug: workspaceSlug },
      });
      return data;
    },
    staleTime: 1000 * 15,
    enabled: Boolean(workspaceSlug),
  });
}
