import api from '@/lib/api';

export interface AgentChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_calls?: any[];
}

export interface AgentRuntimeSession {
  id: string;
  workspace_id?: string;
  title: string;
  agent_type: 'antigravity' | 'pi' | 'opencode' | 'bash';
  sandbox_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  messages: AgentChatMessage[];
}

export interface CreateAgentSessionPayload {
  title: string;
  agent_type: 'antigravity' | 'pi' | 'opencode';
  sandbox_mode: 'new' | 'existing';
  sandbox_id?: string;
}

export const agentRuntimeApi = {
  listSessions: async (): Promise<AgentRuntimeSession[]> => {
    const res = await api.get('/agent-runtime/sessions');
    return res.data;
  },

  getSession: async (sessionId: string): Promise<AgentRuntimeSession> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}`);
    return res.data;
  },

  createSession: async (payload: CreateAgentSessionPayload): Promise<AgentRuntimeSession> => {
    const res = await api.post('/agent-runtime/sessions', payload);
    return res.data;
  },

  deleteSession: async (sessionId: string): Promise<{ deleted: boolean; session_id: string }> => {
    const res = await api.delete(`/agent-runtime/sessions/${sessionId}`);
    return res.data;
  },

  sendMessage: async (sessionId: string, content: string): Promise<AgentChatMessage> => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/messages`, { content });
    return res.data;
  },
};
