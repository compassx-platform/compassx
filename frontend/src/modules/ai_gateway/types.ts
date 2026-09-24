export type AIProviderType =
  | 'openai'
  | 'anthropic'
  | 'azure'
  | 'gemini'
  | 'bedrock'
  | 'vertex'
  | 'ollama'
  | 'compatible';

export interface AIProvider {
  id: number;
  workspace_id?: string | null;
  catalog_name?: string | null;
  schema_name?: string | null;
  name: string;
  provider_type: AIProviderType;
  has_api_key: boolean;
  masked_api_key?: string | null;
  base_url?: string | null;
  config: Record<string, any>;
  is_active: boolean;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIModelEndpoint {
  id: number;
  workspace_id?: string | null;
  name: string;
  provider_id: number;
  provider_name?: string | null;
  provider_type?: AIProviderType | null;
  upstream_model_name: string;
  fallback_endpoint_ids: number[];
  timeout_s: number;
  max_tokens: number;
  temperature_default?: number | null;
  rate_limit_rpm?: number | null;
  rate_limit_tpm?: number | null;
  input_cost_per_1k_tokens?: number | null;
  output_cost_per_1k_tokens?: number | null;
  cost_currency?: string | null;
  use_for_embedding: boolean;
  is_default: boolean;
  guardrail_config: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type MCPServerType = 'native' | 'remote_sse' | 'subprocess';

export interface MCPServer {
  id: number;
  workspace_id?: string | null;
  catalog_name?: string | null;
  schema_name?: string | null;
  full_name?: string | null;
  name: string;
  description?: string | null;
  server_type: MCPServerType;
  endpoint_url?: string | null;
  has_auth: boolean;
  command?: string | null;
  is_enabled: boolean;
  created_by?: string | null;
  is_builtin?: boolean;
  cached_tools: Array<{
    name: string;
    description?: string;
    inputSchema?: Record<string, any>;
  }>;
  last_synced_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MCPToolDefinition {
  name: string;
  description?: string | null;
  input_schema: Record<string, any>;
  server_id?: number | string | null;
  server_name?: string | null;
}

export interface InferenceLog {
  id: number;
  workspace_id?: string | null;
  caller_type: string;
  caller_id?: string | null;
  endpoint_id?: number | null;
  endpoint_name: string;
  provider_type: string;
  upstream_model_name: string;
  request_messages: any[];
  tools_passed?: any[] | null;
  response_text?: string | null;
  response_tool_calls?: any[] | null;
  finish_reason?: string | null;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  latency_ms: number;
  status_code: number;
  error_message?: string | null;
  created_at: string;
}
