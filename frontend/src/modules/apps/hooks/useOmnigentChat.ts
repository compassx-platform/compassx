import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

export interface OmnigentAgent {
  id: string;
  name: string;
  display_name?: string;
  provider?: string;
  description?: string;
  role?: string;
  mode?: string;
  icon?: string;
  badge?: string;
  color?: string;
}

export interface OmnigentSession {
  session_id: string;
  agent_id?: string;
  agent_name?: string;
  title?: string;
  host_id?: string;
  host_name?: string;
  host_online?: boolean;
  dev_url?: string;
  dev_status?: string;
  workspace_id?: string;
  workspace_name?: string;
  workspace_folder?: string;
  is_running?: boolean;
}

export interface ToolCallData {
  name: string;
  input?: any;
  output?: any;
  status?: string;
  duration_ms?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  type?: 'message' | 'thought' | 'tool_call' | 'tool_result' | 'command' | 'file_edit' | 'error' | string;
  content: string;
  agent?: string;
  status?: 'pending' | 'running' | 'completed' | 'error';
  created_at?: string;
  tool?: ToolCallData;
}

export function useOmnigentAgents(appId?: string) {
  return useQuery({
    queryKey: ['omnigent-agents', appId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const res = await api.get<OmnigentAgent[] | { agents: OmnigentAgent[] }>(`/apps/${appId}/dev/omnigent/agents`);
      if (Array.isArray(res.data)) return res.data;
      return (res.data as any)?.agents || (res.data as any)?.data || [];
    },
    enabled: !!appId,
    staleTime: 60_000,
  });
}

export function useOmnigentSession(appId?: string, workspaceId?: string) {
  return useQuery({
    queryKey: ['omnigent-build-session', appId, workspaceId],
    queryFn: async () => {
      if (!appId) throw new Error('App ID required');
      const params = workspaceId ? { workspace_id: workspaceId } : {};
      const res = await api.get<OmnigentSession>(`/apps/${appId}/dev/build/session`, { params });
      return res.data;
    },
    enabled: !!appId,
    staleTime: 10_000,
  });
}

export function useOmnigentMessages(appId?: string, sessionId?: string, isPolling = false) {
  return useQuery({
    queryKey: ['omnigent-messages', appId, sessionId],
    queryFn: async () => {
      if (!appId || !sessionId) return [];
      const res = await api.get<ChatMessage[]>(`/apps/${appId}/dev/build/messages`, {
        params: { session_id: sessionId },
      });
      return Array.isArray(res.data) ? res.data : [];
    },
    enabled: !!appId && !!sessionId,
    refetchInterval: isPolling ? 2000 : 5000,
  });
}

export function useSendOmnigentPrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      appId,
      prompt,
      sessionId,
      agentName,
      workspaceId,
    }: {
      appId: string;
      prompt: string;
      sessionId?: string;
      agentName?: string;
      workspaceId?: string;
    }) => {
      const res = await api.post(`/apps/${appId}/dev/build/prompt`, {
        prompt,
        session_id: sessionId ?? null,
        agent_name: agentName ?? 'polly',
        workspace_id: workspaceId ?? null,
      });
      return res.data;
    },
    onSuccess: (_, { appId, sessionId }) => {
      if (sessionId) {
        qc.invalidateQueries({ queryKey: ['omnigent-messages', appId, sessionId] });
      }
    },
  });
}

export function useClearOmnigentSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ appId, workspaceId, sessionId }: { appId: string; workspaceId?: string; sessionId?: string }) => {
      const res = await api.post<OmnigentSession>(`/apps/${appId}/dev/build/clear`, {
        workspace_id: workspaceId ?? null,
        session_id: sessionId ?? null,
      });
      return res.data;
    },
    onSuccess: (data, { appId, workspaceId }) => {
      qc.setQueryData(['omnigent-build-session', appId, workspaceId], data);
      qc.invalidateQueries({ queryKey: ['omnigent-build-session', appId] });
      if (data?.session_id) {
        qc.setQueryData(['omnigent-messages', appId, data.session_id], []);
      }
    },
  });
}
