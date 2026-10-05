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

export interface DeploymentItem {
  deployment_id: string;
  app_id: string;
  status: 'success' | 'failed' | 'building' | 'pending' | string;
  commit_sha?: string;
  git_ref: string;
  commit_message?: string;
  message?: string;
  duration_seconds?: number;
  triggered_by?: string;
  created_at: string;
  logs: string[];
}

export function useDeployApp() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async (appId: string) => {
      const res = await api.post<DeploymentItem>(`/apps/${appId}/deploy`, null, { timeout: 120000 });
      return res.data;
    },
    onSuccess: (_, appId) => {
      qc.invalidateQueries({ queryKey: ['app-detail', appId] });
      qc.invalidateQueries({ queryKey: ['app-deployments', appId] });
      qc.invalidateQueries({ queryKey: ['app-logs', appId] });
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
    },
  });
}

export function useAppDeployments(appId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-deployments', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<DeploymentItem[]>(`/apps/${appId}/deployments`);
      return res.data;
    },
    enabled: !!appId && enabled,
    refetchInterval: (query) => {
      if (!enabled) return false;
      const data = query.state.data;
      const hasInProgress = Array.isArray(data) && data.some((d: any) => d.status === 'in_progress' || d.status === 'building' || d.status === 'starting' || d.status === 'queued');
      return hasInProgress ? 1000 : 5000;
    },
  });
}

export function useAppLogs(
  appId?: string,
  enabled = true,
  refetchInterval?: number | false | ((query: any) => number | false)
) {
  return useQuery({
    queryKey: ['app-logs', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<{ app_id: string; status: string; logs: string[] }>(`/apps/${appId}/logs`);
      return res.data;
    },
    enabled: !!appId && enabled,
    refetchInterval: refetchInterval !== undefined ? refetchInterval : (enabled ? 2000 : false),
  });
}

export interface AppRuntimeStatus {
  app_id: string;
  status: 'active' | 'running' | 'provisioning' | 'starting' | 'stopping' | 'stopped' | 'error' | string;
  phase?: 'Running' | 'Pending' | 'ContainerCreating' | 'Terminating' | 'Stopped' | 'CrashLoopBackOff' | 'NotFound' | string;
  mode?: 'kubernetes' | 'docker' | 'local' | string;
  container_name?: string;
  container_id?: string;
  pod_name?: string;
  replicas?: number;
  ready_replicas?: number;
  available_replicas?: number;
  step?: number;
  step_description?: string;
  message?: string;
  url?: string;
  last_updated?: string;
}

export function useAppRuntimeStatus(appId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-runtime-status', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<AppRuntimeStatus>(`/apps/${appId}/runtime-status`);
      return res.data;
    },
    enabled: !!appId && enabled,
    refetchInterval: (query) => {
      if (!enabled) return false;
      const st = query.state.data?.status;
      if (st === 'provisioning' || st === 'starting' || st === 'stopping') {
        return 1500;
      }
      return 6000;
    },
  });
}

export function useStartApp() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async (appId: string) => {
      const res = await api.post<AppRuntimeStatus>(`/apps/${appId}/start`);
      return res.data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['app-runtime-status', data.app_id] });
      qc.invalidateQueries({ queryKey: ['app-detail', data.app_id] });
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
    },
  });
}

export function useStopApp() {
  const qc = useQueryClient();
  const workspace = useWorkspaceContext();
  const wsId = workspace?.id;

  return useMutation({
    mutationFn: async (appId: string) => {
      const res = await api.post<AppRuntimeStatus>(`/apps/${appId}/stop`);
      return res.data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['app-runtime-status', data.app_id] });
      qc.invalidateQueries({ queryKey: ['app-detail', data.app_id] });
      qc.invalidateQueries({ queryKey: ['apps-list', wsId] });
    },
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
      qc.invalidateQueries({ queryKey: ['app-runtime-status', data.id] });
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

// ── Omnigent Dev Studio Hooks ──────────────────────────────────────────

export interface DevWorkspace {
  id: string;
  name: string;
  folder_path: string;
  git_branch?: string;
  status: 'active' | 'stopped' | string;
  size_bytes?: number;
  created_by?: string;
  created_at: string;
  last_active_at?: string;
}

export interface DevSessionStatus {
  app_id: string;
  status: 'active' | 'provisioning' | 'stopping' | 'stopped' | 'inactive' | string;
  mode?: 'docker' | 'kubernetes' | 'local' | string;
  container_id?: string;
  container_name?: string;
  pod_name?: string;
  phase?: string;
  dev_port?: number;
  dev_url?: string;
  repo_dir?: string;
  workspace_id?: string;
  workspace_name?: string;
  workspace_folder?: string;
  omnigent_attached?: boolean;
  omnigent_server_available?: boolean;
  omnigent_server_url?: string;
  omnigent_server_connected?: boolean;
  omnigent_session_id?: string;
  omnigent_session_url?: string;
  host_id?: string;
  host_name?: string;
  host_online?: boolean;
  host_type?: 'compassx' | 'omnigent' | string;
  host_image?: string;
  workspace?: string;
  started_at?: string;
}

export function useDevWorkspaces(appId?: string) {
  return useQuery({
    queryKey: ['app-dev-workspaces', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<DevWorkspace[]>(`/apps/${appId}/dev/workspaces`);
      return res.data;
    },
    enabled: !!appId,
    staleTime: 10_000,
  });
}

export function useDevStatus(appId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-dev-status', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<DevSessionStatus>(`/apps/${appId}/dev/status`);
      return res.data;
    },
    enabled: !!appId && enabled,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      return st === 'active' || st === 'provisioning' ? 3000 : 6000;
    },
  });
}

export function useStartDevSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      appId,
      workspaceId,
      workspaceName,
      hostType,
    }: {
      appId: string;
      workspaceId?: string;
      workspaceName?: string;
      hostType?: 'compassx' | 'omnigent' | string;
    }) => {
      const res = await api.post<DevSessionStatus>(
        `/apps/${appId}/dev/start`,
        {
          workspace_id: workspaceId ?? null,
          workspace_name: workspaceName ?? null,
          host_type: hostType ?? 'compassx',
        },
        { timeout: 120000 }
      );
      return res.data;
    },
    onSuccess: (data, { appId }) => {
      qc.setQueryData(['app-dev-status', appId], data);
      qc.invalidateQueries({ queryKey: ['app-dev-status', appId] });
      qc.invalidateQueries({ queryKey: ['app-dev-workspaces', appId] });
    },
  });
}

export function useCreateDevWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      appId,
      name,
      gitBranch,
    }: {
      appId: string;
      name: string;
      gitBranch?: string;
    }) => {
      const res = await api.post<DevWorkspace>(
        `/apps/${appId}/dev/workspaces`,
        {
          name,
          git_branch: gitBranch ?? null,
        },
        { timeout: 60000 }
      );
      return res.data;
    },
    onSuccess: (_, { appId }) => {
      qc.invalidateQueries({ queryKey: ['app-dev-workspaces', appId] });
    },
  });
}

export function useStopDevSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (appId: string) => {
      const res = await api.post(`/apps/${appId}/dev/stop`, null, { timeout: 60000 });
      return res.data;
    },
    onSuccess: (data, appId) => {
      qc.setQueryData(['app-dev-status', appId], {
        app_id: appId,
        status: 'stopped',
        phase: 'Stopped',
      });
      qc.invalidateQueries({ queryKey: ['app-dev-status', appId] });
      qc.invalidateQueries({ queryKey: ['app-dev-workspaces', appId] });
    },
  });
}

export function useDeleteDevWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ appId, workspaceId }: { appId: string; workspaceId: string }) => {
      const res = await api.delete(`/apps/${appId}/dev/workspaces/${workspaceId}`);
      return res.data;
    },
    onSuccess: (_, { appId }) => {
      qc.invalidateQueries({ queryKey: ['app-dev-workspaces', appId] });
    },
  });
}

export function useActivateDevWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ appId, workspaceId }: { appId: string; workspaceId: string }) => {
      const res = await api.post(`/apps/${appId}/dev/workspaces/${workspaceId}/activate`);
      return res.data;
    },
    onSuccess: (_, { appId }) => {
      qc.invalidateQueries({ queryKey: ['app-dev-workspaces', appId] });
      qc.invalidateQueries({ queryKey: ['app-dev-status', appId] });
      qc.invalidateQueries({ queryKey: ['app-dev-sessions', appId] });
    },
  });
}

export function usePublishDevChanges() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      appId,
      commitMessage,
      workspaceId,
      workspaceName,
    }: {
      appId: string;
      commitMessage?: string;
      workspaceId?: string;
      workspaceName?: string;
    }) => {
      const res = await api.post(`/apps/${appId}/dev/publish`, {
        commit_message: commitMessage || 'Update application via Omnigent Dev Studio',
        workspace_id: workspaceId ?? null,
        workspace_name: workspaceName ?? null,
      });
      return res.data;
    },
    onSuccess: (_, { appId }) => {
      qc.invalidateQueries({ queryKey: ['app-detail', appId] });
      qc.invalidateQueries({ queryKey: ['app-deployments', appId] });
      qc.invalidateQueries({ queryKey: ['app-dev-status', appId] });
      qc.invalidateQueries({ queryKey: ['app-dev-workspaces', appId] });
    },
  });
}

export function useDevLogs(appId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-dev-logs', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<{ app_id: string; logs: string[] } | string[]>(`/apps/${appId}/dev/logs`, {
        params: { tail: 200 },
      });
      if (Array.isArray(res.data)) return res.data;
      return (res.data as any)?.logs || [];
    },
    enabled: !!appId && enabled,
    refetchInterval: enabled ? 3000 : false,
  });
}

export interface VerifyGitResult {
  success: boolean;
  branch?: string;
  output?: string;
  message?: string;
}

export function useVerifyGitWorkspace() {
  return useMutation({
    mutationFn: async ({
      appId,
      workspaceId,
      workspaceName,
    }: {
      appId: string;
      workspaceId?: string;
      workspaceName?: string;
    }): Promise<VerifyGitResult> => {
      const res = await api.post(`/apps/${appId}/dev/verify-git`, {
        workspace_id: workspaceId ?? null,
        workspace_name: workspaceName ?? null,
      });
      return res.data;
    },
  });
}

export interface InstallDepsResult {
  success: boolean;
  cached?: boolean;
  manifests?: string[];
  exit_code?: number;
  output?: string;
  message?: string;
}

export function useInstallDevDependencies() {
  return useMutation({
    mutationFn: async ({
      appId,
      workspaceId,
      workspaceName,
      force = false,
    }: {
      appId: string;
      workspaceId?: string;
      workspaceName?: string;
      force?: boolean;
    }): Promise<InstallDepsResult> => {
      const res = await api.post(`/apps/${appId}/dev/install-deps`, {
        workspace_id: workspaceId ?? null,
        workspace_name: workspaceName ?? null,
        force,
      });
      return res.data;
    },
  });
}

export interface RunAppResult {
  success: boolean;
  dev_url?: string;
  output?: string;
  message?: string;
}

export function useRunDevApp() {
  return useMutation({
    mutationFn: async ({
      appId,
      workspaceId,
      workspaceName,
    }: {
      appId: string;
      workspaceId?: string;
      workspaceName?: string;
    }): Promise<RunAppResult> => {
      const res = await api.post(`/apps/${appId}/dev/run-app`, {
        workspace_id: workspaceId ?? null,
        workspace_name: workspaceName ?? null,
      });
      return res.data;
    },
  });
}

export interface ExecCommandResult {
  success: boolean;
  exit_code?: number;
  output?: string;
  workdir?: string;
}

export function useExecDevCommand() {
  return useMutation({
    mutationFn: async ({
      appId,
      command,
      workspaceId,
      workspaceName,
    }: {
      appId: string;
      command: string;
      workspaceId?: string;
      workspaceName?: string;
    }): Promise<ExecCommandResult> => {
      const res = await api.post(`/apps/${appId}/dev/exec`, {
        command,
        workspace_id: workspaceId || null,
        workspace_name: workspaceName || null,
      });
      return res.data;
    },
  });
}

export function useDevHeartbeat() {
  return useMutation({
    mutationFn: async ({
      appId,
      workspaceId,
    }: {
      appId: string;
      workspaceId?: string;
    }) => {
      const params = workspaceId ? { workspace_id: workspaceId } : {};
      const res = await api.post(`/apps/${appId}/dev/heartbeat`, null, { params });
      return res.data;
    },
  });
}

export interface AppLifecycleData {
  app_id: string;
  app_name: string;
  dev_sandbox: {
    auto_suspend_enabled: boolean;
    idle_timeout_minutes: number;
    auto_reap_enabled: boolean;
    stale_reap_days: number;
    status?: string;
    last_active_at?: string | null;
  };
  app_runtime: {
    auto_suspend_enabled: boolean;
    idle_timeout_minutes: number;
    status?: string;
    last_accessed_at?: string | null;
  };
}

export function useAppLifecycle(appId?: string) {
  return useQuery({
    queryKey: ['app-lifecycle', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<AppLifecycleData>(`/apps/${appId}/lifecycle`);
      return res.data;
    },
    enabled: !!appId,
    staleTime: 10_000,
  });
}

export function useUpdateAppLifecycle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      appId,
      payload,
    }: {
      appId: string;
      payload: {
        dev_sandbox?: {
          auto_suspend_enabled?: boolean;
          idle_timeout_minutes?: number;
          auto_reap_enabled?: boolean;
          stale_reap_days?: number;
        };
        app_runtime?: {
          auto_suspend_enabled?: boolean;
          idle_timeout_minutes?: number;
        };
      };
    }) => {
      const res = await api.put<AppLifecycleData>(`/apps/${appId}/lifecycle`, payload);
      return res.data;
    },
    onSuccess: (_, { appId }) => {
      qc.invalidateQueries({ queryKey: ['app-lifecycle', appId] });
      qc.invalidateQueries({ queryKey: ['app-detail', appId] });
    },
  });
}

export interface WorkspaceFile {
  path: string;
  name: string;
  size?: number;
  bytes?: number | null;
  ext?: string;
  modified_at?: number | null;
  type?: 'file' | 'directory';
}

export interface WorkspaceFileContent {
  path: string;
  content: string;
  size: number;
  ext: string;
}

export function useDevFiles(appId?: string, workspaceId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-dev-files', appId, workspaceId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const params: Record<string, string> = {};
      if (workspaceId) params.workspace_id = workspaceId;
      const res = await api.get<WorkspaceFile[]>(`/apps/${appId}/dev/files`, { params });
      return res.data;
    },
    enabled: !!appId && enabled,
    refetchInterval: enabled ? 5000 : false,
  });
}

export function useDevFileContent(appId?: string, filePath?: string | null, workspaceId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-dev-file-content', appId, filePath, workspaceId],
    queryFn: async () => {
      if (!appId || !filePath) throw new Error('App ID and File path required');
      const params: Record<string, string> = { path: filePath };
      if (workspaceId) params.workspace_id = workspaceId;
      const res = await api.get<WorkspaceFileContent>(`/apps/${appId}/dev/file`, {
        params,
      });
      return res.data;
    },
    enabled: !!appId && !!filePath && enabled,
    staleTime: 5000,
  });
}

export function useWriteDevFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      appId,
      path,
      content,
      workspaceId,
    }: {
      appId: string;
      path: string;
      content: string;
      workspaceId?: string;
    }) => {
      const params: Record<string, string> = {};
      if (workspaceId) params.workspace_id = workspaceId;
      const res = await api.put<WorkspaceFileContent>(`/apps/${appId}/dev/file`, {
        path,
        content,
        workspace_id: workspaceId,
      }, { params });
      return res.data;
    },
    onSuccess: (_, { appId, path, workspaceId }) => {
      qc.invalidateQueries({ queryKey: ['app-dev-files', appId, workspaceId] });
      qc.invalidateQueries({ queryKey: ['app-dev-files', appId] });
      qc.invalidateQueries({ queryKey: ['app-dev-file-content', appId, path, workspaceId] });
      qc.invalidateQueries({ queryKey: ['app-dev-file-content', appId, path] });
    },
  });
}

export interface DevSession {
  id: string;
  app_id: string;
  workspace_id?: string | null;
  title: string;
  agent: 'pi' | 'opencode' | 'antigravity';
  model?: string | null;
  external_session_id?: string | null;
  tmux_session_name?: string | null;
  status: string;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  last_active_at?: string | null;
}

export interface CreateDevSessionPayload {
  title: string;
  agent: 'pi' | 'opencode' | 'antigravity';
  workspace_id?: string;
  model?: string;
}

export interface AppDevModel {
  id: string;
  name: string;
  is_default?: boolean;
  provider?: string;
}

export function useAppDevModels(appId?: string) {
  return useQuery({
    queryKey: ['app-dev-models', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<AppDevModel[]>(`/apps/${appId}/dev/models`);
      return res.data;
    },
    enabled: !!appId,
    staleTime: 60_000,
  });
}

export interface UpdateDevSessionPayload {
  title?: string;
  status?: string;
}

export function useDevSessions(appId?: string, enabled = true) {
  return useQuery<DevSession[]>({
    queryKey: ['app-dev-sessions', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<DevSession[]>(`/apps/${appId}/dev/sessions`);
      return res.data;
    },
    enabled: !!appId && enabled,
    refetchInterval: enabled ? 10000 : false,
    staleTime: 5000,
  });
}

export function useCreateDevSession(appId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateDevSessionPayload) => {
      if (!appId) throw new Error('App ID required');
      const res = await api.post<DevSession>(`/apps/${appId}/dev/sessions`, payload);
      return res.data;
    },
    onSuccess: (newSession) => {
      qc.setQueryData<DevSession[]>(['app-dev-sessions', appId], (old = []) => {
        const exists = old.some((s) => s.id === newSession.id);
        if (exists) {
          return old.map((s) => (s.id === newSession.id ? newSession : s));
        }
        return [newSession, ...old];
      });
      qc.invalidateQueries({ queryKey: ['app-dev-sessions', appId] });
    },
  });
}

export function useUpdateDevSession(appId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      sessionId,
      payload,
    }: {
      sessionId: string;
      payload: UpdateDevSessionPayload;
    }) => {
      if (!appId) throw new Error('App ID required');
      const res = await api.patch<DevSession>(`/apps/${appId}/dev/sessions/${sessionId}`, payload);
      return res.data;
    },
    onSuccess: (updated) => {
      qc.setQueryData<DevSession[]>(['app-dev-sessions', appId], (old = []) =>
        old.map((s) => (s.id === updated.id ? updated : s))
      );
      qc.invalidateQueries({ queryKey: ['app-dev-sessions', appId] });
    },
  });
}

export function useDeleteDevSession(appId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      if (!appId) throw new Error('App ID required');
      const res = await api.delete<{ status: string; session_id: string }>(
        `/apps/${appId}/dev/sessions/${sessionId}`,
      );
      return res.data;
    },
    onSuccess: (_, sessionId) => {
      qc.setQueryData<DevSession[]>(['app-dev-sessions', appId], (old = []) =>
        old.filter((s) => s.id !== sessionId)
      );
      qc.invalidateQueries({ queryKey: ['app-dev-sessions', appId] });
    },
  });
}

