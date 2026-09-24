import api from '@/lib/api';
import {
  AIProvider,
  MCPServer,
  MCPToolDefinition,
  InferenceLog,
} from './types';

// --- Provider Endpoints ---

export async function fetchAIProviders(): Promise<AIProvider[]> {
  const { data } = await api.get('/ai-gateway/providers');
  return data;
}

export async function createAIProvider(payload: Partial<AIProvider> & { api_key?: string }): Promise<AIProvider> {
  const { data } = await api.post('/ai-gateway/providers', payload);
  return data;
}

export async function updateAIProvider(id: number, payload: Partial<AIProvider> & { api_key?: string }): Promise<AIProvider> {
  const { data } = await api.put(`/ai-gateway/providers/${id}`, payload);
  return data;
}

export async function deleteAIProvider(id: number): Promise<void> {
  await api.delete(`/ai-gateway/providers/${id}`);
}

export async function pingAIProvider(id: number): Promise<{ success: boolean; message: string; latency_ms: number; available_models: string[] }> {
  const { data } = await api.post(`/ai-gateway/providers/${id}/ping`);
  return data;
}

export async function discoverAIProviderModels(
  payload: {
    provider_type: string;
    api_key?: string;
    base_url?: string;
    config?: Record<string, any>;
  },
  signal?: AbortSignal
): Promise<{ success: boolean; message: string; latency_ms: number; available_models: string[] }> {
  const { data } = await api.post('/ai-gateway/providers/discover-models', payload, { signal });
  return data;
}

// --- MCP Servers & Tools ---

export async function fetchMCPServers(): Promise<MCPServer[]> {
  const { data } = await api.get('/ai-gateway/mcp/servers');
  return data;
}

export async function createMCPServer(payload: Partial<MCPServer> & { auth_headers?: Record<string, string>; env_vars?: Record<string, string> }): Promise<MCPServer> {
  const { data } = await api.post('/ai-gateway/mcp/servers', payload);
  return data;
}

export async function updateMCPServer(id: number, payload: Partial<MCPServer> & { auth_headers?: Record<string, string>; env_vars?: Record<string, string> }): Promise<MCPServer> {
  const { data } = await api.put(`/ai-gateway/mcp/servers/${id}`, payload);
  return data;
}

export async function deleteMCPServer(id: number): Promise<void> {
  await api.delete(`/ai-gateway/mcp/servers/${id}`);
}

export async function syncMCPServer(id: number): Promise<{ server_id: number; server_name: string; tools_count: number; tools: MCPToolDefinition[] }> {
  const { data } = await api.post(`/ai-gateway/mcp/servers/${id}/ping`);
  return data;
}

export async function fetchMCPServerTools(
  serverId: string | number
): Promise<{
  success: boolean;
  message: string;
  latency_ms: number;
  called_endpoint?: string;
  http_method?: string;
  mcp_method?: string;
  mcp_protocol?: string;
  upstream_target?: string;
  server_name: string;
  server_type: string;
  endpoint_url?: string;
  tools_count: number;
  tools: any[];
  raw_response?: any;
}> {
  const { data } = await api.get(`/ai-gateway/mcp/servers/${serverId}/tools`);
  return data;
}

export const pingMCPServer = fetchMCPServerTools;

export async function fetchMCPTools(): Promise<MCPToolDefinition[]> {
  const { data } = await api.get('/ai-gateway/mcp/tools');
  return data;
}

export async function executeMCPTool(toolName: string, args: Record<string, any>): Promise<{ tool_name: string; server_name: string; result: any; is_error: boolean; error_message?: string; latency_ms: number }> {
  const { data } = await api.post('/ai-gateway/mcp/tools/call', {
    tool_name: toolName,
    arguments: args,
  });
  return data;
}

// --- Inference Logs ---

export async function fetchInferenceLogs(endpointName?: string, limit = 50): Promise<InferenceLog[]> {
  const params: Record<string, any> = { limit };
  if (endpointName) params.endpoint_name = endpointName;
  const { data } = await api.get('/ai-gateway/logs/inferences', { params });
  return data;
}
