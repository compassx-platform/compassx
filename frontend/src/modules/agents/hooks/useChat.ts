import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { ChatMessage } from "@/modules/agents/stores/chatStore";

export interface ChatSession {
  id: number;
  agent_id: number;
  title?: string;
  created_at: string;
  updated_at: string;
}

export function useChatSessions(agentId: number | null) {
  return useQuery({
    queryKey: ["agents", agentId, "sessions"],
    queryFn: async () => {
      const { data } = await api.get<ChatSession[]>(`/agents/${agentId}/sessions`);
      return data;
    },
    enabled: agentId != null,
    staleTime: 30_000,
  });
}

export function useChatMessages(
  agentId: number | null,
  sessionId: number | null
) {
  return useQuery({
    queryKey: ["agents", agentId, "sessions", sessionId, "messages"],
    queryFn: async () => {
      const { data } = await api.get<ChatMessage[]>(`/agents/${agentId}/sessions/${sessionId}/messages`);
      return data;
    },
    enabled: agentId != null && sessionId != null,
    staleTime: 0,
  });
}

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
    }: {
      agentId: number;
    }) => {
      const { data } = await api.post<ChatSession>(`/agents/${agentId}/sessions`, {});
      return data;
    },
    onSuccess: (_, { agentId }) => qc.invalidateQueries({ queryKey: ["agents", agentId, "sessions"] }),
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      sessionId,
    }: {
      agentId: number;
      sessionId: number;
    }) => {
      await api.delete(`/agents/${agentId}/sessions/${sessionId}`);
    },
    onSuccess: (_, { agentId }) => qc.invalidateQueries({ queryKey: ["agents", agentId, "sessions"] }),
  });
}

