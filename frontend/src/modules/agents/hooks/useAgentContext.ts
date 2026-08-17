import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface AgentContextEntry {
  id: number;
  agent_id: number;
  text: string;
  tags: string[];
  version: number;
  is_active: boolean;
  created_by?: string;
  created_at: string;
}

export function useAgentContext(
  agentId: number | null,
  search?: string
) {
  return useQuery({
    queryKey: ["agents", agentId, "context", search],
    queryFn: async () => {
      const params = search ? `?search=${encodeURIComponent(search)}` : "";
      const { data } = await api.get<AgentContextEntry[]>(`/agents/${agentId}/context${params}`);
      return data;
    },
    enabled: agentId != null,
    staleTime: 30_000,
  });
}

export function useCreateAgentContext() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      payload,
    }: {
      agentId: number;
      payload: { text: string; tags?: string[] };
    }) => {
      const { data } = await api.post<AgentContextEntry>(`/agents/${agentId}/context`, payload);
      return data;
    },
    onSuccess: (_, { agentId }) => qc.invalidateQueries({ queryKey: ["agents", agentId, "context"] }),
  });
}

export function useUpdateAgentContext() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      entryId,
      payload,
    }: {
      agentId: number;
      entryId: number;
      payload: { text?: string; tags?: string[]; is_active?: boolean };
    }) => {
      const { data } = await api.put<AgentContextEntry>(`/agents/${agentId}/context/${entryId}`, payload);
      return data;
    },
    onSuccess: (_, { agentId }) => qc.invalidateQueries({ queryKey: ["agents", agentId, "context"] }),
  });
}

export function useDeleteAgentContext() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      entryId,
    }: {
      agentId: number;
      entryId: number;
    }) => {
      await api.delete(`/agents/${agentId}/context/${entryId}`);
    },
    onSuccess: (_, { agentId }) => qc.invalidateQueries({ queryKey: ["agents", agentId, "context"] }),
  });
}
