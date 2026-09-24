import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useCurrentWorkspaceSlug } from '@/lib/appNavigation';
import { getToken } from '@/lib/auth';

export interface PortalItem {
  id: string;
  type: 'app' | 'dashboard' | 'external_link';
  target_id: string;
  title: string;
  icon?: string | null;
  is_visible: boolean;
  order: number;
  url?: string | null;
  app_type?: string | null;
  status?: string | null;
}

export interface PortalSection {
  id: string;
  title: string;
  items: PortalItem[];
}

export interface PortalConfig {
  id?: string;
  workspace_id: string;
  workspace_slug?: string | null;
  sections: PortalSection[];
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

function getAuthHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function usePortalConfig() {
  const workspaceSlug = useCurrentWorkspaceSlug();

  return useQuery<PortalConfig>({
    queryKey: ['portal-config', workspaceSlug],
    queryFn: async () => {
      const { data } = await axios.get('/api/v1/portal/config', {
        params: { workspace_slug: workspaceSlug },
        headers: getAuthHeaders(),
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
      const { data } = await axios.put(
        '/api/v1/portal/config',
        { sections },
        {
          params: { workspace_slug: workspaceSlug },
          headers: getAuthHeaders(),
        }
      );
      return data;
    },
    onSuccess: (updatedConfig) => {
      queryClient.setQueryData(['portal-config', workspaceSlug], updatedConfig);
      queryClient.invalidateQueries({ queryKey: ['portal-config', workspaceSlug] });
    },
  });
}

export function usePortalAvailableItems() {
  const workspaceSlug = useCurrentWorkspaceSlug();

  return useQuery<PortalAvailableItems>({
    queryKey: ['portal-available-items', workspaceSlug],
    queryFn: async () => {
      const { data } = await axios.get('/api/v1/portal/available-items', {
        params: { workspace_slug: workspaceSlug },
        headers: getAuthHeaders(),
      });
      return data;
    },
    staleTime: 1000 * 15,
    enabled: Boolean(workspaceSlug),
  });
}
