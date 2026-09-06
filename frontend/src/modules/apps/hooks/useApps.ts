import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useWorkspaceContext } from '@/lib/workspaceContext';

export interface AppItem {
  id: string;
  workspace_id: string;
  workspace_slug?: string;
  name: string;
  slug: string;
  description?: string;
  app_type: string;
  status: string;
  route: string;
  git_provider?: string;
  git_repo_url: string;
  git_ref?: string;
  git_ref_type?: string;
  git_branch: string;
  git_subdir?: string;
  entrypoint?: string;
  git_credential_type?: string;
  git_credential_nickname?: string;
  git_connection_id?: number;
  pat_configured: boolean;
  workspace_identity?: {
    identity_id: string;
    principal_type: string;
    role: string;
    scopes: string[];
    created_at?: string;
  };
  config?: Record<string, any>;
  created_by_user_id?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateAppPayload {
  name: string;
  description?: string;
  app_type: string;
  route?: string;
  slug?: string;
  git_provider?: string;
  git_repo_url: string;
  git_ref?: string;
  git_ref_type?: string;
  git_branch?: string;
  git_subdir?: string;
  entrypoint?: string;
  git_credential_type?: string;
  git_credential_nickname?: string;
  git_connection_id?: number | null;
  git_pat?: string;
  config?: Record<string, any>;
}

export function useApps() {
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useQuery({
    queryKey: ['apps-list', wsId],
    queryFn: async () => {
      const params = wsId ? { workspace_id: wsId } : {};
      const res = await api.get<AppItem[]>('/apps', { params });
      return res.data;
    },
    staleTime: 30_000,
  });
}

export function useCreateApp() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async (payload: CreateAppPayload) => {
      const res = await api.post<AppItem>('/apps', payload);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
      qc.invalidateQueries({ queryKey: ['apps-list'] });
    },
  });
}

export function useApp(appId?: string) {
  return useQuery({
    queryKey: ['app-detail', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<AppItem>(`/apps/${appId}`);
      return res.data;
    },
    enabled: !!appId,
    staleTime: 10_000,
  });
}

export function useUpdateApp() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async ({ appId, payload }: { appId: string; payload: Partial<CreateAppPayload> & { status?: string } }) => {
      const res = await api.put<AppItem>(`/apps/${appId}`, payload);
      return res.data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['app-detail', data.id] });
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
      qc.invalidateQueries({ queryKey: ['apps-list'] });
    },
  });
}

export function useDeployApp() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async (appId: string) => {
      const res = await api.post(`/apps/${appId}/deploy`);
      return res.data;
    },
    onSuccess: (_, appId) => {
      qc.invalidateQueries({ queryKey: ['app-detail', appId] });
      qc.invalidateQueries({ queryKey: ['app-logs', appId] });
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
    },
  });
}

export function useAppLogs(appId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-logs', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<{ app_id: string; status: string; logs: string[] }>(`/apps/${appId}/logs`);
      return res.data;
    },
    enabled: !!appId && enabled,
    refetchInterval: enabled ? 3000 : false,
  });
}

export function useUpdateAppStatus() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async ({ appId, status }: { appId: string; status: string }) => {
      const res = await api.post<AppItem>(`/apps/${appId}/status`, null, {
        params: { status },
      });
      return res.data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['app-detail', data.id] });
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
    },
  });
}

export function useDeleteApp() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async (appId: string) => {
      await api.delete(`/apps/${appId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
      qc.invalidateQueries({ queryKey: ['apps-list'] });
    },
  });
}
