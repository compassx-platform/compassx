import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface Workspace {
  id: number;
  name: string;
  description?: string;
  fallback_llm_connection_id?: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMember {
  id: number;
  workspace_id: number;
  user_id: string;
  role: "admin" | "editor" | "viewer";
  created_at: string;
}

// ── Workspaces ────────────────────────────────────────────────────────────────

export function useWorkspaces() {
  return useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const { data } = await api.get<Workspace[]>("/workspaces");
      return data;
    },
    staleTime: 30_000,
  });
}

export function useWorkspace(workspaceId: number | null) {
  return useQuery({
    queryKey: ["workspaces", workspaceId],
    queryFn: async () => {
      const { data } = await api.get<Workspace>(`/workspaces/${workspaceId}`);
      return data;
    },
    enabled: workspaceId != null,
    staleTime: 30_000,
  });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string; description?: string }) => {
      const { data } = await api.post<Workspace>("/workspaces", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });
}

export function useUpdateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      workspaceId,
      payload,
    }: {
      workspaceId: number;
      payload: { name?: string; description?: string; fallback_llm_connection_id?: number | null };
    }) => {
      const { data } = await api.put<Workspace>(`/workspaces/${workspaceId}`, payload);
      return data;
    },
    onSuccess: (_, { workspaceId }) => {
      qc.invalidateQueries({ queryKey: ["workspaces"] });
      qc.invalidateQueries({ queryKey: ["workspaces", workspaceId] });
    },
  });
}

export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (workspaceId: number) => {
      await api.delete(`/workspaces/${workspaceId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });
}

// ── Members ───────────────────────────────────────────────────────────────────

export function useWorkspaceMembers(workspaceId: number | null) {
  return useQuery({
    queryKey: ["workspaces", workspaceId, "members"],
    queryFn: async () => {
      const { data } = await api.get<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`);
      return data;
    },
    enabled: workspaceId != null,
    staleTime: 60_000,
  });
}

export function useAddMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      workspaceId,
      payload,
    }: {
      workspaceId: number;
      payload: { user_id: string; role: string };
    }) => {
      await api.post(`/workspaces/${workspaceId}/members`, payload);
    },
    onSuccess: (_, { workspaceId }) =>
      qc.invalidateQueries({ queryKey: ["workspaces", workspaceId, "members"] }),
  });
}

export function useRemoveMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      workspaceId,
      userId,
    }: {
      workspaceId: number;
      userId: string;
    }) => {
      await api.delete(`/workspaces/${workspaceId}/members/${userId}`);
    },
    onSuccess: (_, { workspaceId }) =>
      qc.invalidateQueries({ queryKey: ["workspaces", workspaceId, "members"] }),
  });
}
