import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { ChatMessage } from "@/modules/agents/stores/chatStore";

export interface ChatSession {
  id: number;
  agent_id: number;
  title?: string;
  created_at: string;
  updated_at: string;
  last_message?: string;
  message_count?: number;
  has_changes?: boolean;
  files_changed_count?: number;
}

export interface SessionContextUsage {
  total_tokens: number;
  context_window: number;
  high_watermark: number;
  usage_percent: number;
  total_turns: number;
  retained_turns: number;
  has_summary: boolean;
  summary?: string | null;
  summary_updated_at?: string | null;
  model_name?: string | null;
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
      return data ?? [];
    },
    enabled: agentId != null && sessionId != null,
    staleTime: 30_000,
    gcTime: 5 * 60 * 1000,
  });
}

export function useSessionContext(
  agentId: number | null,
  sessionId: number | null
) {
  return useQuery({
    queryKey: ["agents", agentId, "sessions", sessionId, "context"],
    queryFn: async () => {
      const { data } = await api.get<SessionContextUsage>(`/agents/${agentId}/sessions/${sessionId}/context`);
      return data;
    },
    enabled: agentId != null && sessionId != null,
    staleTime: 5_000,
  });
}

export function useSessionPlans(
  agentId: number | null,
  sessionId: number | null
) {
  return useQuery({
    queryKey: ["agents", agentId, "sessions", sessionId, "plans"],
    queryFn: async () => {
      const { data } = await api.get<any[]>(`/agents/${agentId}/sessions/${sessionId}/plans`);
      return data ?? [];
    },
    enabled: agentId != null && sessionId != null,
    staleTime: 5_000,
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

