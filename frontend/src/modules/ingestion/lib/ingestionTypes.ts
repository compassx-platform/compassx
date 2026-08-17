// TypeScript types for the Ingestion module — mirrors backend Pydantic schemas.
// Raw secret values are NEVER present in any of these types (server-side only).

export type AuthType =
  | 'none'
  | 'api_key_header'
  | 'api_key_query'
  | 'bearer_token'
  | 'basic_auth';

export type PaginationType = 'none' | 'offset' | 'page' | 'cursor_field';
export type ParamSourceType = 'static' | 'catalog_query' | 'parent_api';
export type HttpMethod = 'GET' | 'POST';
export type RunStatus = 'running' | 'succeeded' | 'failed' | 'partial';
export type RunItemStatus = 'succeeded' | 'failed' | 'skipped';

// ── Connection ────────────────────────────────────────────────────────────────

export interface Connection {
  id: string;
  workspace_id: string;
  name: string;
  description?: string;
  base_url: string;
  auth_type: AuthType;
  auth_config: Record<string, unknown>;
  has_secret: boolean;
  default_headers: Record<string, unknown>;
  rate_limit_rps: number;
  max_concurrency: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ConnectionCreate {
  name: string;
  description?: string;
  base_url: string;
  auth_type: AuthType;
  auth_config?: Record<string, unknown>;
  secret_value?: string;        // write-only — never returned
  default_headers?: Record<string, unknown>;
  rate_limit_rps?: number;
  max_concurrency?: number;
}

export interface ConnectionUpdate {
  name?: string;
  description?: string;
  base_url?: string;
  auth_type?: AuthType;
  auth_config?: Record<string, unknown>;
  default_headers?: Record<string, unknown>;
  rate_limit_rps?: number;
  max_concurrency?: number;
}

// ── Job Config ────────────────────────────────────────────────────────────────

export interface JobConfig {
  id: string;
  workspace_id: string;
  connection_id: string;
  name: string;
  http_method: HttpMethod;
  path_template: string;
  query_template: Record<string, unknown>;
  body_template?: Record<string, unknown>;
  pagination_type: PaginationType;
  pagination_config: Record<string, unknown>;
  cursor_field_path?: string;
  cursor_query_param?: string;
  param_source_type: ParamSourceType;
  param_source_config: Record<string, unknown>;
  target_bronze_bucket: string;
  schedule_cron: string;
  is_enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface JobConfigCreate {
  connection_id: string;
  name: string;
  http_method?: HttpMethod;
  path_template: string;
  query_template?: Record<string, unknown>;
  body_template?: Record<string, unknown>;
  pagination_type?: PaginationType;
  pagination_config?: Record<string, unknown>;
  cursor_field_path?: string;
  cursor_query_param?: string;
  param_source_type?: ParamSourceType;
  param_source_config?: Record<string, unknown>;
  target_bronze_bucket?: string;
  schedule_cron: string;
  is_enabled?: boolean;
}

export interface JobConfigUpdate {
  name?: string;
  http_method?: HttpMethod;
  path_template?: string;
  query_template?: Record<string, unknown>;
  body_template?: Record<string, unknown>;
  pagination_type?: PaginationType;
  pagination_config?: Record<string, unknown>;
  cursor_field_path?: string;
  cursor_query_param?: string;
  param_source_type?: ParamSourceType;
  param_source_config?: Record<string, unknown>;
  target_bronze_bucket?: string;
  schedule_cron?: string;
}

// ── Run ───────────────────────────────────────────────────────────────────────

export interface IngestionRun {
  id: string;
  job_config_id: string;
  airflow_dag_run_id?: string;
  status: RunStatus;
  started_at: string;
  finished_at?: string;
  total_params: number;
  succeeded_params: number;
  failed_params: number;
  total_rows_landed: number;
  total_bytes_landed: number;
  error_summary?: string;
}

export interface IngestionRunItem {
  id: string;
  run_id: string;
  param_value: string;
  status: RunItemStatus;
  pages_fetched: number;
  rows_landed: number;
  bytes_landed: number;
  bronze_path?: string;
  error_message?: string;
  started_at: string;
  finished_at?: string;
}

export interface TriggerResponse {
  run_id: string;
  status: string;
  message: string;
}
