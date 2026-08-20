import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ExternalConnection {
  id: string;
  workspace_id?: string | null;
  name: string;
  connector_type: string;
  base_url: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CreateExternalConnectionPayload {
  name: string;
  connector_type: string;
  base_url: string;
  auth_config?: Record<string, unknown> | string;
  status?: string;
}

export interface UpdateExternalConnectionPayload {
  name?: string;
  connector_type?: string;
  base_url?: string;
  auth_config?: Record<string, unknown> | string;
  status?: string;
}

export function useExternalConnections(statusFilter?: string) {
  return useQuery({
    queryKey: ["external-connections", statusFilter],
    queryFn: async () => {
      const params = statusFilter ? { status: statusFilter } : undefined;
      const { data } = await api.get<ExternalConnection[]>("/external-connections", { params });
      return data;
    },
    staleTime: 30_000,
  });
}

export function useCreateExternalConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateExternalConnectionPayload) => {
      const { data } = await api.post<ExternalConnection>("/external-connections", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["external-connections"] });
    },
  });
}

export function useUpdateExternalConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: string;
      payload: UpdateExternalConnectionPayload;
    }) => {
      const { data } = await api.put<ExternalConnection>(`/external-connections/${id}`, payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["external-connections"] });
    },
  });
}

export function useDisableExternalConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post<ExternalConnection>(`/external-connections/${id}/disable`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["external-connections"] });
    },
  });
}

export function useDeleteExternalConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/external-connections/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["external-connections"] });
    },
  });
}
