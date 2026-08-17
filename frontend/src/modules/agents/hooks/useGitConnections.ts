import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface GitConnection {
  id: number;
  name: string;
  provider: string;         // "github" | "azure_devops"
  base_url?: string;
  organization?: string;
  default_project?: string;
  pat_configured: boolean;
  created_at: string;
  updated_at: string;
}

export function useGitConnections() {
  return useQuery({
    queryKey: ["git-connections"],
    queryFn: async () => {
      const { data } = await api.get<GitConnection[]>("/git-connections");
      return data;
    },
    staleTime: 60_000,
  });
}

export function useCreateGitConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      payload,
    }: {
      payload: {
        name: string;
        provider: string;
        base_url?: string;
        organization?: string;
        default_project?: string;
        pat?: string;
      };
    }) => {
      const { data } = await api.post<GitConnection>("/git-connections", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["git-connections"] }),
  });
}

export function useUpdateGitConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      connId,
      payload,
    }: {
      connId: number;
      payload: {
        name?: string;
        base_url?: string;
        organization?: string;
        default_project?: string;
        pat?: string;
      };
    }) => {
      const { data } = await api.put<GitConnection>(`/git-connections/${connId}`, payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["git-connections"] }),
  });
}

export function useDeleteGitConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      connId,
    }: {
      connId: number;
    }) => {
      await api.delete(`/git-connections/${connId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["git-connections"] }),
  });
}

export function useTestGitConnection() {
  return useMutation({
    mutationFn: async ({
      connId,
    }: {
      connId: number;
    }) => {
      const { data } = await api.post<{ success: boolean; message: string }>(`/git-connections/${connId}/test`, {});
      return data;
    },
  });
}
