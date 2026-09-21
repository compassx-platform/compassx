/**
 * API client and React Query hooks for Account-level Settings.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from './workspaceApi';

export interface AirflowAccountSettings {
  webserver_enabled: boolean;
  webserver_status?: 'running' | 'stopped' | 'starting' | 'unknown';
  webserver_replicas?: number;
  webserver_available_replicas?: number;
  webserver_url?: string | null;
}

export interface VmSizeOption {
  id: string;
  name: string;
  label: string;
  cpu: number;
  memory_gib: number;
  architecture: string;
  category: string;
  description: string;
  recommended: boolean;
}

export interface AppNodePoolSettings {
  dedicated_pool_enabled: boolean;
  pool_name?: string;
  default_pool_name?: string;
  vm_size?: string;
  min_count?: number;
  max_count?: number;
  auto_scale?: boolean;
  status?: 'active' | 'starting' | 'provisioning' | 'disabled' | 'pending' | 'error';
  status_message?: string;
  is_provisioning?: boolean;
  app_pool?: {
    name: string;
    vm_size: string;
    architecture: string;
    os: string;
    total_nodes: number;
    ready_nodes: number;
    nodes: Array<{ name: string; ready: boolean; vm_size: string }>;
  } | null;
  user_pool?: {
    name: string;
    vm_size: string;
    architecture: string;
    os: string;
    total_nodes: number;
    ready_nodes: number;
    nodes: Array<{ name: string; ready: boolean; vm_size: string }>;
  } | null;
  cluster_pools?: any[];
  app_workloads?: {
    total_apps: number;
    apps: Array<{
      name: string;
      is_dev: boolean;
      replicas: number;
      ready_replicas: number;
      assigned_pool: string;
      node_selector: Record<string, string>;
    }>;
  };
  vm_sizes_catalog?: VmSizeOption[];
}

export interface ComputeAccountSettings {
  auto_stop_enabled: boolean;
  auto_stop_minutes: number;
  dedicated_pool_enabled?: boolean;
  pool_name?: string;
  default_pool_name?: string;
  vm_size?: string;
  vm_capacity_gib?: number;
  min_count?: number;
  max_count?: number;
  auto_scale?: boolean;
  status?: 'active' | 'starting' | 'provisioning' | 'disabled' | 'pending' | 'error';
  status_message?: string;
  is_provisioning?: boolean;
  compute_pool?: {
    name: string;
    vm_size: string;
    architecture: string;
    os: string;
    total_nodes: number;
    ready_nodes: number;
    nodes: Array<{ name: string; ready: boolean; vm_size: string }>;
  } | null;
  vm_sizes_catalog?: VmSizeOption[];
}

export interface AccountSettingsData {
  airflow?: AirflowAccountSettings;
  app_node_pool?: AppNodePoolSettings;
  compute?: ComputeAccountSettings;
  [key: string]: any;
}

export interface AccountSettingsResponse {
  account_id: string;
  account_name: string;
  account_slug: string;
  settings: AccountSettingsData;
}

export async function fetchAccountSettings(): Promise<AccountSettingsResponse> {
  const resp = await authApi.get<AccountSettingsResponse>('/api/account/settings');
  return resp.data;
}

export async function patchAccountSettings(body: Partial<AccountSettingsData>): Promise<AccountSettingsResponse> {
  const resp = await authApi.patch<AccountSettingsResponse>('/api/account/settings', body);
  return resp.data;
}

export async function triggerNodepoolSwitchover(targetPool?: string): Promise<any> {
  const resp = await authApi.post('/api/account/settings/nodepool/switchover', null, {
    params: targetPool ? { target_pool: targetPool } : {},
  });
  return resp.data;
}

export function useAccountSettings() {
  return useQuery({
    queryKey: ['account-settings'],
    queryFn: fetchAccountSettings,
    staleTime: 10_000,
    refetchInterval: (query) => {
      // Poll every 4 seconds if webserver or node pool is in transition
      const wsStatus = query.state.data?.settings?.airflow?.webserver_status;
      const poolStatus = query.state.data?.settings?.app_node_pool?.status;
      const isProvisioning = query.state.data?.settings?.app_node_pool?.is_provisioning;
      if (wsStatus === 'starting' || poolStatus === 'starting' || poolStatus === 'provisioning' || isProvisioning) {
        return 4000;
      }
      return false;
    },
  });
}

export function useUpdateAccountSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: patchAccountSettings,
    onSuccess: (data) => {
      qc.setQueryData(['account-settings'], data);
      qc.invalidateQueries({ queryKey: ['account-settings'] });
    },
  });
}

export function useSwitchoverAppNodePool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (targetPool?: string) => triggerNodepoolSwitchover(targetPool),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['account-settings'] });
    },
  });
}
