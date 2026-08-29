import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface AgentTool {
  id?: number;
  tool_name: string;
}

export interface AgentListItem {
  id: number;
  name: string;
  description?: string;
  avatar?: string;
  color?: string;
  model?: string;
  is_orchestrator: boolean;
  visibility: "shared" | "private";
  is_active: boolean;
  status: "active" | "paused";
  tool_count: number;
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: number;
  name: string;
  description?: string;
  avatar?: string;
  color?: string;
  prompt?: string;
  model?: string;
  max_tokens: number;
  is_orchestrator: boolean;
  visibility: "shared" | "private";
  is_active: boolean;
  status: "active" | "paused";
  manifest?: Record<string, any>;
  llm_connection_id?: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
  tools: AgentTool[];
  skills?: any[];
}

// ── Agents ────────────────────────────────────────────────────────────────────

export function useAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: async () => {
      const { data } = await api.get<AgentListItem[]>("/agents");
      return data;
    },
    staleTime: 30_000,
  });
}

export function useAgent(agentId: number | null) {
  return useQuery({
    queryKey: ["agents", agentId],
    queryFn: async () => {
      const { data } = await api.get<Agent>(`/agents/${agentId}`);
      return data;
    },
    enabled: agentId != null,
    staleTime: 30_000,
  });
}

export function useCreateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      payload,
    }: {
      payload: {
        name: string;
        description?: string;
        avatar?: string;
        color?: string;
        prompt?: string;
        model?: string;
        max_tokens?: number;
        is_orchestrator?: boolean;
        visibility?: string;
        manifest?: Record<string, any>;
        llm_connection_id?: number;
        tools?: { tool_name: string }[];
      };
    }) => {
      const { data } = await api.post<Agent>("/agents", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });
}

export function useUpdateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      payload,
    }: {
      agentId: number;
      payload: {
        name?: string;
        description?: string;
        avatar?: string;
        color?: string;
        prompt?: string;
        model?: string;
        max_tokens?: number;
        is_orchestrator?: boolean;
        visibility?: string;
        is_active?: boolean;
        status?: "active" | "paused";
        manifest?: Record<string, any>;
        llm_connection_id?: number | null;
        tools?: { tool_name: string }[];
      };
    }) => {
      const { data } = await api.put<Agent>(`/agents/${agentId}`, payload);
      return data;
    },
    onSuccess: (_, { agentId }) => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      qc.invalidateQueries({ queryKey: ["agents", agentId] });
    },
  });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
    }: {
      agentId: number;
    }) => {
      await api.delete(`/agents/${agentId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });
}

export function useCloneAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
    }: {
      agentId: number;
    }) => {
      const { data } = await api.post<Agent>(`/agents/${agentId}/clone`, {});
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });
}
