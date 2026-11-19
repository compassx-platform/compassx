import api from '@/lib/api';

export interface AgentChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_calls?: any[];
  kind?: 'thinking' | 'tool' | 'reply' | 'plan' | 'debug' | 'error' | null;
  source_id?: string | null;
  image?: string | null;
}

export interface AgentRuntimeSession {
  id: string;
  workspace_id?: string;
  title: string;
  agent_type: string;
  sandbox_id: string;
  project_id?: string | null;
  llm_model?: string | null;
  nova_chat_session_id?: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  messages: AgentChatMessage[];
}

export interface AgentRuntimeProject {
  id: string;
  workspace_id?: string | null;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface AgentRuntimeTaskEvent {
  at: string;
  actor: string;
  action: string;
  from_stage: string;
  to_stage: string;
  note: string;
}

export interface AgentRuntimeTask {
  id: string;
  workspace_id?: string | null;
  project_id?: string | null;
  title: string;
  brief: string;
  stage: string;
  waiting_reason: string;
  start_error: string;
  source_session_id?: string | null;
  session_id?: string | null;
  agent_type: string;
  llm_model?: string | null;
  events: AgentRuntimeTaskEvent[];
  created_at: string;
  updated_at: string;
}

export interface CreateAgentSessionPayload {
  title: string;
  agent_type: string;
  sandbox_mode: 'new' | 'existing';
  sandbox_id?: string;
  project_id?: string;
  branch?: string;
  llm_model?: string;
}

export interface SandboxGitInfo {
  repo: boolean;
  branch: string;
  branches: string[];
}

export const agentRuntimeApi = {
  listProjects: async (): Promise<AgentRuntimeProject[]> => {
    const res = await api.get('/agent-runtime/projects');
    return res.data;
  },

  createProject: async (name: string): Promise<AgentRuntimeProject> => {
    const res = await api.post('/agent-runtime/projects', { name });
    return res.data;
  },

  deleteProject: async (projectId: string): Promise<{ deleted: boolean; project_id: string }> => {
    const res = await api.delete(`/agent-runtime/projects/${projectId}`);
    return res.data;
  },

  listSessions: async (): Promise<AgentRuntimeSession[]> => {
    const res = await api.get('/agent-runtime/sessions');
    return res.data;
  },

  getSession: async (sessionId: string): Promise<AgentRuntimeSession> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}`);
    return res.data;
  },

  sandboxGit: async (sandboxId: string): Promise<SandboxGitInfo> => {
    const res = await api.get(`/agent-runtime/sandboxes/${sandboxId}/git`);
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

  stopSession: async (sessionId: string): Promise<AgentRuntimeSession> => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/stop`, {}, { timeout: 30000 });
    return res.data;
  },

  sendMessage: async (sessionId: string, content: string, llmModel?: string, mode?: string): Promise<AgentChatMessage> => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/messages`, { content, llm_model: llmModel || undefined, mode: mode || undefined }, { timeout: 120000 });
    return res.data;
  },

  startSession: async (sessionId: string, content: string, llmModel?: string, mode?: string): Promise<AgentChatMessage> => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/start`, { content, llm_model: llmModel || undefined, mode: mode || undefined }, { timeout: 120000 });
    return res.data;
  },

  listFiles: async (sessionId: string): Promise<WorkspaceFilesResponse> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}/files`);
    return res.data;
  },

  readFile: async (sessionId: string, path: string): Promise<FileContentResponse> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}/files/content`, { params: { path } });
    return res.data;
  },

  writeFile: async (sessionId: string, path: string, content: string): Promise<{ path: string; bytes: number }> => {
    const res = await api.put(`/agent-runtime/sessions/${sessionId}/files/content`, { path, content });
    return res.data;
  },

  listChanges: async (sessionId: string): Promise<ChangesResponse> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}/changes`);
    return res.data;
  },

  readDiff: async (sessionId: string, path: string): Promise<DiffResponse> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}/changes/diff`, { params: { path } });
    return res.data;
  },

  readPatch: async (sessionId: string): Promise<DiffResponse> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}/changes/patch`);
    return res.data;
  },

  listAgents: async (): Promise<AgentCatalogItem[]> => {
    const res = await api.get('/agent-runtime/agents');
    return res.data;
  },

  syncNotices: async (sessionId: string): Promise<AgentRuntimeSession> => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/notices/sync`);
    return res.data;
  },

  readOutput: async (sessionId: string): Promise<string> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}/output`);
    return res.data?.output || '';
  },

  openBrowser: async (sessionId: string, tabId: string, url: string, width: number, height: number): Promise<{ url: string; width: number; height: number; error?: string }> => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/browser/open`, { url, width, height, tab_id: tabId });
    return res.data;
  },

  browserFrame: async (sessionId: string, tabId: string): Promise<Blob> => {
    const res = await api.get(`/agent-runtime/sessions/${sessionId}/browser/frame`, {
      params: { tab_id: tabId },
      responseType: 'blob',
    });
    return res.data;
  },

  inspectBrowser: async (sessionId: string, tabId: string, x: number, y: number) => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/browser/inspect`, { tab_id: tabId, x, y });
    return res.data as { label: string; detail: string; box: { left: number; top: number; width: number; height: number } };
  },

  browserInput: async (sessionId: string, tabId: string, body: { kind: string; x?: number; y?: number; delta_y?: number; key?: string; text?: string }) => {
    await api.post(`/agent-runtime/sessions/${sessionId}/browser/input`, { tab_id: tabId, ...body });
  },

  sendBrowserNote: async (sessionId: string, tabId: string, body: { instruction: string; x: number; y: number; width: number; height: number }): Promise<AgentChatMessage> => {
    const res = await api.post(`/agent-runtime/sessions/${sessionId}/browser/note`, { tab_id: tabId, ...body });
    return res.data;
  },

  listTasks: async (): Promise<AgentRuntimeTask[]> => {
    const res = await api.get('/agent-runtime/tasks');
    return res.data;
  },

  createTask: async (payload: { title: string; brief?: string; project_id?: string; source_session_id?: string; agent_type?: string; llm_model?: string; actor?: string }): Promise<AgentRuntimeTask> => {
    const res = await api.post('/agent-runtime/tasks', payload);
    return res.data;
  },

  parkTask: async (taskId: string, note: string, actor: 'person' | 'agent' = 'person'): Promise<AgentRuntimeTask> => {
    const res = await api.post(`/agent-runtime/tasks/${taskId}/waiting`, { note, actor });
    return res.data;
  },

  readyTask: async (taskId: string): Promise<AgentRuntimeTask> => {
    const res = await api.post(`/agent-runtime/tasks/${taskId}/ready`);
    return res.data;
  },

  submitTask: async (taskId: string, note = ''): Promise<AgentRuntimeTask> => {
    const res = await api.post(`/agent-runtime/tasks/${taskId}/submit`, { note, actor: 'agent' });
    return res.data;
  },

  acceptTask: async (taskId: string): Promise<AgentRuntimeTask> => {
    const res = await api.post(`/agent-runtime/tasks/${taskId}/accept`);
    return res.data;
  },

  requestTaskChanges: async (taskId: string, note: string): Promise<AgentRuntimeTask> => {
    const res = await api.post(`/agent-runtime/tasks/${taskId}/changes`, { note, actor: 'person' });
    return res.data;
  },

  cancelTask: async (taskId: string, note = ''): Promise<AgentRuntimeTask> => {
    const res = await api.post(`/agent-runtime/tasks/${taskId}/cancel`, { note, actor: 'person' });
    return res.data;
  },
};

export interface WorkspaceEntry {
  path: string;
  type: 'file' | 'dir' | string;
  size: number;
}

export interface WorkspaceFilesResponse {
  root: string;
  entries: WorkspaceEntry[];
}

export interface FileContentResponse {
  path: string;
  content: string;
  truncated: boolean;
  missing: boolean;
}

export interface ChangeEntry {
  path: string;
  status: string;
  additions: number;
  deletions: number;
  staged?: boolean;
  unstaged?: boolean;
}

export interface CommitEntry {
  hash: string;
  subject: string;
  author: string;
  date: string;
}

export interface ChangesResponse {
  entries: ChangeEntry[];
  branch?: string;
  commits?: CommitEntry[];
}

export interface DiffResponse {
  path: string;
  diff: string;
}

export interface AgentCatalogItem {
  id: string;
  label: string;
}
