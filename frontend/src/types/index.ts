/** Shared TypeScript types */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ── Data Catalog ──────────────────────────────────────────────────────────────

export interface CatalogConnection {
  id: number;
  name: string;
  host: string;
  port: number;
  username: string;
  default_database: string;
  created_at: string;
  updated_at: string;
}

export interface ConnectionCreate {
  name: string;
  host: string;
  port: number;
  username: string;
  password: string;
  default_database: string;
}

export interface ConnectionTestRequest {
  host: string;
  port: number;
  username: string;
  password: string;
  database: string;
}

export interface ConnectionTestResponse {
  success: boolean;
  message: string;
  server_version?: string;
}

export interface DatabaseItem {
  name: string;
  owner?: string;
}

export interface SchemaItem {
  name: string;
  owner?: string;
}

export interface TableItem {
  name: string;
  schema_name: string;
  table_type: string;
  row_estimate?: number;
}

export interface ColumnInfo {
  name: string;
  data_type: string;
  is_nullable: boolean;
  column_default?: string;
  ordinal_position: number;
  character_maximum_length?: number;
}

export interface TablePreviewResponse {
  columns: ColumnInfo[];
  rows: Record<string, unknown>[];
  total_rows: number;
  truncated: boolean;
}

export interface SqlExecuteRequest {
  connection_id: number;
  database: string;
  sql: string;
  limit?: number;
}

export interface SqlExecuteResponse {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
  error?: string;
}

// Tree node types for the catalog browser
export type TreeNodeType = 'connection' | 'database' | 'schema' | 'table' | 'view';

export interface TreeNode {
  id: string;
  label: string;
  type: TreeNodeType;
  children?: TreeNode[];
  loaded?: boolean;
  loading?: boolean;
  meta?: Record<string, unknown>;
}
