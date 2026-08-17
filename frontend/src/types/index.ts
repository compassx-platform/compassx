/** Shared TypeScript types */

// ── Entity types ──────────────────────────────────────────────────────────────

export interface EntityField {
  id: number;
  entity_id: number;
  field_name: string;
  field_type: string;
  is_required: boolean;
  is_indexed: boolean;
  field_source: 'entity' | 'form';
  is_system: boolean;
  system_generated: boolean;
  default_value: string | null;
}

export interface EntityDefinition {
  id: number;
  name: string;
  entity_type: string;
  asset_scoped: boolean;
  time_based: boolean;
  time_series: boolean;
  created_at: string;
  fields?: EntityField[];
}

export interface EntityFieldCreate {
  field_name: string;
  field_type: string;
  is_required: boolean;
  is_indexed: boolean;
}

export interface EntitySystemFieldCreate {
  field_name: string;
  field_type: string;
  default_value?: string | null;
  system_generated: boolean;
  is_indexed: boolean;
}

export interface EntityDefinitionCreate {
  name: string;
  entity_type: string;
  asset_scoped: boolean;
  time_based: boolean;
  time_series: boolean;
  fields: EntityFieldCreate[];
  system_fields: EntitySystemFieldCreate[];
}

// ── Asset types ───────────────────────────────────────────────────────────────

export interface AssetType {
  id: number;
  name: string;
  description?: string;
  is_active?: boolean;
}

export interface Asset {
  id: number;
  name: string;
  description?: string;
  unique_asset_identifier: string;
  asset_type_asset?: AssetType;
  parent_asset_id?: number;
}

export interface FormField {
  id: string;
  type: string;
  label: string;
  layout?: {
    x: number;
    y: number;
    w: number;
    h: number;
    minW?: number;
    minH?: number;
  };
  options?: string[];
  multi_select?: boolean;
  /** For conditional_dropdown: maps a depends_on field value to a list of options */
  options_map?: Record<string, string[]>;
  /** Field ID whose value drives conditional options or clearing */
  depends_on?: string;
  /** Default value; use "today" for date fields or "now" for datetime fields */
  default_value?: string;
  required?: boolean;
  data_source?: {
    type: string;
    endpoint: string;
    depends_on?: string;
    param_name?: string;
    /** For async_select: filter assets by asset type name */
    filter_by_type_name?: string;
  };
  visible_if?: {
    field: string;
    value: string;
  };
  columns?: FormField[];
  show_serial_number?: boolean;
}

export type FormValue = string | string[];
export type FormValues = Record<string, FormValue>;

export interface FormSchema {
  form_id: string;
  entity: string;
  fields: FormField[];
}

export interface BreakdownRecord {
  id: number;
  record_id: number;
  asset_id: string;
  asset_name?: string;
  child_asset_id?: string;
  child_asset_name?: string;
  breakdown_type?: string;
  severity?: string;
  description?: string;
  timestamp?: string;
  status?: string;
  created_by?: string;
}

export interface ExplorerResponse {
  items: BreakdownRecord[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

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
