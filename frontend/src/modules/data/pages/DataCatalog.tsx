import { useMemo, useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Database,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Table2,
  X,
  SlidersHorizontal,
  Folder,
  RefreshCcw,
  Settings,
  Copy,
  Star,
  Pencil,
  MoreVertical,
  Search,
  Check,
  FileText,
  FileCode,
  Calendar,
  Clock,
  Upload,
  Braces,
  Trash,
  Play,
  PanelLeftClose,
  PanelLeftOpen,
  Wrench,
  BookOpen,
  LayoutDashboard,
  Layers,
  HardDrive,
  GitCommit,
  History,
} from 'lucide-react';
import api from '@/lib/api';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useParams, useSearchParams } from 'react-router-dom';
import { PageTabs } from '@/components/common/PageTabs';
import { Table } from '@/components/common/Table';
import NotebookPage from '@/modules/notebooks/pages/NotebookPage';
import DashboardEditorPage from '@/modules/dashboards/pages/DashboardEditorPage';
import { useNotebookStore } from '@/modules/notebooks/store/notebookStore';
import { CatalogQueryEditorTab, CatalogQueryVersion } from '../components/CatalogQueryEditorTab';
import { useCatalogConnections } from '@/modules/agents/hooks/useCatalogConnections';

const CATALOG_TABS_STORAGE_KEY = 'compassx_catalog_open_tabs_v1';

type TableType = 'postgres_native' | 'iceberg';
type Selection = 
  | { kind: 'root' }
  | { kind: 'catalog'; catalog: string } 
  | { kind: 'schema'; catalog: string; schema: string } 
  | { kind: 'table'; catalog: string; schema: string; table: string } 
  | { kind: 'volume'; catalog: string; schema: string; volume: string } 
  | { kind: 'notebook'; catalog: string; schema: string; notebook: string; blob_path?: string }
  | { kind: 'dashboard'; catalog: string; schema: string; dashboard: string; dashboard_id?: string }
  | { kind: 'tool'; catalog: string; schema: string; tool: string; tool_id?: string }
  | { kind: 'query'; catalog: string; schema: string; query: string }
  | null;

type DBConnection = { 
  id: number; 
  name: string; 
  db_type: string; 
};

interface PersistedTabsState {
  openPanels: Array<{ id: string; label: string; selection: Exclude<Selection, null | { kind: 'root' }>; }>;
  mainTabId: string;
  detailsSelection: Selection;
}

function loadPersistedTabs(): PersistedTabsState | null {
  try {
    const raw = localStorage.getItem(CATALOG_TABS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && Array.isArray(parsed.openPanels)) {
      return {
        openPanels: parsed.openPanels.filter((p: any) => p && p.id && p.selection && p.selection.kind),
        mainTabId: typeof parsed.mainTabId === 'string' ? parsed.mainTabId : 'details',
        detailsSelection: parsed.detailsSelection && parsed.detailsSelection.kind ? parsed.detailsSelection : { kind: 'root' },
      };
    }
    return null;
  } catch {
    return null;
  }
}

function savePersistedTabs(state: PersistedTabsState) {
  try {
    localStorage.setItem(CATALOG_TABS_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage quota errors
  }
}

type CatalogSummary = {
  id: string;
  name: string;
  description?: string | null;
  catalog_type?: string | null;
  connection_id?: number | null;
  database_name?: string | null;
  storage_backend_id?: string | null;
  base_path?: string | null;
  schema_count: number;
  table_count: number;
  schemas: Array<{
    id: string;
    name: string;
    description?: string | null;
    table_count: number;
    read_roles?: string[];
    write_roles?: string[];
  }>;
};

type CatalogTable = { 
  id: string; 
  fqn: string; 
  catalog: string; 
  schema_name: string; 
  name: string; 
  table_type: TableType; 
  created_at: string;
  description?: string | null; 
  owner: string; 
  read_roles: string[]; 
  write_roles: string[]; 
  connection_name?: string | null; 
  source_database?: string | null; 
  pg_schema?: string | null; 
  pg_table?: string | null; 
  metadata_location?: string | null; 
  storage_location?: string | null; 
  columns: Array<{ 
    name: string; 
    data_type: string; 
    nullable: boolean; 
    description?: string | null; 
    ordinal: number; 
  }>; 
};

type CatalogVolume = {
  id: string;
  schema_id: string;
  name: string;
  description?: string | null;
  storage_location?: string | null;
  owner: string;
  created_by: string;
  created_at: string;
};

type CatalogNotebook = {
  id: string;
  catalog_name: string;
  schema_name: string;
  name: string;
  full_name: string;
  blob_path: string;
  storage_location?: string | null;
  owner: string;
  comment?: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
};

type CatalogDashboard = {
  id: string;
  catalog_name: string;
  schema_name: string;
  name: string;
  full_name: string;
  dashboard_id?: string | null;
  owner: string;
  comment?: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
};

type CatalogToolVersion = {
  id: string;
  tool_id: string;
  version: number;
  source_notebook_object_id?: string | null;
  source_code: string;
  param_schema: Record<string, any>;
  connection_dependencies: string[];
  promoted_by: string;
  promoted_at: string;
};

type CatalogTool = {
  id: string;
  catalog: string;
  schema_name: string;
  name: string;
  full_name: string;
  description?: string | null;
  param_schema: Record<string, any>;
  connection_dependencies: string[];
  source_notebook_object_id?: string | null;
  source_code: string;
  owner: string;
  current_version: number;
  created_at: string;
  updated_at: string;
  versions?: CatalogToolVersion[];
};

type VolumeFileInfo = {
  file_path: string;
  file_name: string;
  size_bytes: number;
  content_type: string;
  last_modified: string;
  uploaded_by?: string;
};

type LineageGraph = {
  upstream: Array<{ source_fqn: string }>;
  downstream: Array<{ target_fqn: string }>;
};

type SampleData = {
  columns: string[];
  rows: (string | null)[][];
  row_count: number;
};

type CatalogForm = {
  name: string;
  description: string;
  catalog_type: 'postgres' | 'iceberg';
  connection_id: string;
  database_name: string;
  storageBackend: string;
};

type CatalogQuery = {
  id: string;
  catalog_name: string;
  schema_name: string;
  name: string;
  full_name: string;
  sql_text: string;
  owner: string;
  description?: string | null;
  current_version?: number;
  versions?: CatalogQueryVersion[];
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
};

type CatalogAssetKind = 'table' | 'volume' | 'notebook' | 'dashboard' | 'tool' | 'query';

type PendingCatalogAsset = {
  id: string;
  kind: CatalogAssetKind;
  catalog: string;
  schema: string;
  name: string;
  status: 'creating' | 'failed';
  error?: string;
};

type PendingAssetContext = {
  pendingId: string;
  catalog: string;
  schema: string;
  name: string;
};

const catalogApi = {
  listCatalogs: () => api.get<CatalogSummary[]>('/catalog/catalogs').then((r) => r.data),
  createCatalog: (body: Record<string, any>) => api.post<any>('/catalog/catalogs', body).then((r) => r.data),
  createSchema: (catalogName: string, body: Record<string, any>) => api.post<any>(`/catalog/catalogs/${encodeURIComponent(catalogName)}/schemas`, body).then((r) => r.data),
  createTable: (catalogName: string, schemaName: string, body: Record<string, any>) => api.post<any>(`/catalog/catalogs/${encodeURIComponent(catalogName)}/schemas/${encodeURIComponent(schemaName)}/tables`, body).then((r) => r.data),
  createVolume: (catalogName: string, schemaName: string, body: Record<string, any>) => api.post<any>(`/catalog/catalogs/${encodeURIComponent(catalogName)}/schemas/${encodeURIComponent(schemaName)}/volumes`, body).then((r) => r.data),
  deleteCatalog: (name: string) => api.delete(`/catalog/catalogs/${encodeURIComponent(name)}`).then((r) => r.data),
  syncCatalog: (name: string) => api.post(`/catalog/catalogs/${encodeURIComponent(name)}/sync`).then((r) => r.data),
  listTables: (catalog?: string, schema_name?: string) => api.get<CatalogTable[]>('/catalog/tables', { params: { catalog: catalog, schema_name: schema_name } }).then((r) => r.data),
  listVolumes: (catalog?: string, schema_name?: string) => api.get<CatalogVolume[]>('/catalog/volumes', { params: { catalog: catalog, schema_name: schema_name } }).then((r) => r.data),
  listNotebooks: (catalog: string, schema_name: string) => api.get<CatalogNotebook[]>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/notebooks`).then((r) => r.data),
  createNotebook: (catalog: string, schema_name: string, body: { name: string; comment?: string }) => api.post<CatalogNotebook>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/notebooks`, body).then((r) => r.data),
  getNotebook: (catalog: string, schema_name: string, notebook: string) => api.get<CatalogNotebook>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/notebooks/${encodeURIComponent(notebook)}`).then((r) => r.data),
  updateNotebook: (catalog: string, schema_name: string, notebook: string, body: { name?: string; comment?: string; owner?: string }) => api.patch<CatalogNotebook>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/notebooks/${encodeURIComponent(notebook)}`, body).then((r) => r.data),
  moveNotebook: (catalog: string, schema: string, notebook: string, body: { target_catalog: string; target_schema: string; new_name?: string }) => api.post<CatalogNotebook>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/notebooks/${encodeURIComponent(notebook)}/move`, body).then((r) => r.data),
  deleteNotebook: (catalog: string, schema: string, notebook: string) => api.delete(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/notebooks/${encodeURIComponent(notebook)}`).then((r) => r.data),
  runNotebook: (catalog: string, schema: string, notebook: string) => api.post<{ status: string; notebook: CatalogNotebook; cells: any[] }>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/notebooks/${encodeURIComponent(notebook)}/run`).then((r) => r.data),
  listDashboards: (catalog: string, schema_name: string) => api.get<CatalogDashboard[]>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/dashboards`).then((r) => r.data),
  createDashboard: (catalog: string, schema_name: string, body: { name: string; comment?: string }) => api.post<CatalogDashboard>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/dashboards`, body).then((r) => r.data),
  getDashboard: (catalog: string, schema_name: string, dashboard: string) => api.get<CatalogDashboard>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/dashboards/${encodeURIComponent(dashboard)}`).then((r) => r.data),
  updateDashboard: (catalog: string, schema_name: string, dashboard: string, body: { name?: string; comment?: string; owner?: string }) => api.patch<CatalogDashboard>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/dashboards/${encodeURIComponent(dashboard)}`, body).then((r) => r.data),
  moveDashboard: (catalog: string, schema: string, dashboard: string, body: { target_catalog: string; target_schema: string; new_name?: string }) => api.post<CatalogDashboard>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/dashboards/${encodeURIComponent(dashboard)}/move`, body).then((r) => r.data),
  deleteDashboard: (catalog: string, schema: string, dashboard: string) => api.delete(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/dashboards/${encodeURIComponent(dashboard)}`).then((r) => r.data),
  listQueries: (catalog: string, schema_name: string) => api.get<CatalogQuery[]>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries`).then((r) => r.data),
  createQuery: (catalog: string, schema_name: string, body: { name: string; sql_text: string; description?: string }) => api.post<CatalogQuery>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries`, body).then((r) => r.data),
  getQuery: (catalog: string, schema_name: string, query: string) => api.get<CatalogQuery>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries/${encodeURIComponent(query)}`).then((r) => r.data),
  updateQuery: (catalog: string, schema_name: string, query: string, body: { name?: string; sql_text?: string; description?: string; owner?: string; change_summary?: string }) => api.patch<CatalogQuery>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries/${encodeURIComponent(query)}`, body).then((r) => r.data),
  deleteQuery: (catalog: string, schema: string, query: string) => api.delete(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/queries/${encodeURIComponent(query)}`),
  getQueryVersions: (catalog: string, schema_name: string, query: string) => api.get<CatalogQueryVersion[]>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries/${encodeURIComponent(query)}/versions`).then((r) => r.data),
  createQueryVersion: (catalog: string, schema_name: string, query: string, body: { sql_text: string; description?: string; change_summary?: string }) => api.post<CatalogQueryVersion>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries/${encodeURIComponent(query)}/versions`, body).then((r) => r.data),
  getQueryVersion: (catalog: string, schema_name: string, query: string, version: number) => api.get<CatalogQueryVersion>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries/${encodeURIComponent(query)}/versions/${version}`).then((r) => r.data),
  restoreQueryVersion: (catalog: string, schema_name: string, query: string, version: number) => api.post<CatalogQuery>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema_name)}/queries/${encodeURIComponent(query)}/versions/${version}/restore`).then((r) => r.data),
  listTools: (catalog?: string, schema_name?: string) => api.get<CatalogTool[]>('/catalog/tools', { params: { catalog: catalog, schema: schema_name, schema_name: schema_name } }).then((r) => r.data),
  getTool: (toolId: string) => api.get<CatalogTool>(`/catalog/tools/${encodeURIComponent(toolId)}`).then((r) => r.data),
  listVolumeFiles: (volume_id: string) => api.get<VolumeFileInfo[]>(`/catalog/volumes/${volume_id}/files`).then((r) => r.data),
  uploadVolumeFile: (volume_id: string, file: File, sub_path: string = "") => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<VolumeFileInfo>(`/catalog/volumes/${volume_id}/files`, formData, { params: { sub_path }, headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  createVolumeDirectory: (volume_id: string, dir_name: string, sub_path: string = "") => api.post<VolumeFileInfo>(`/catalog/volumes/${volume_id}/directories`, { dir_name }, { params: { sub_path } }).then((r) => r.data),
  deleteVolumeFile: (volume_id: string, file_path: string) => api.delete(`/catalog/volumes/${volume_id}/files`, { params: { file_path } }).then((r) => r.data),
  renameVolumeFile: (volume_id: string, old_path: string, new_name: string) => api.post<VolumeFileInfo>(`/catalog/volumes/${volume_id}/files/rename`, { old_path, new_name }).then((r) => r.data),
  getTable: (catalog: string, schema: string, table: string) => api.get<CatalogTable>('/catalog/tables/' + catalog + '/' + schema + '/' + table).then((r) => r.data),
  deleteTable: (catalog: string, schema: string, table: string) => api.delete(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/tables/${encodeURIComponent(table)}`).then((r) => r.data),
  refreshTable: (catalog: string, schema: string, table: string) => api.post<CatalogTable>('/catalog/tables/' + catalog + '/' + schema + '/' + table + '/refresh-columns').then((r) => r.data),
  getLineage: (catalog: string, schema: string, table: string) => api.get<LineageGraph>('/catalog/lineage/' + catalog + '/' + schema + '/' + table).then((r) => r.data),
  getSampleData: (catalog: string, schema: string, table: string, limit = 100) =>
    api.get<{ columns: string[]; rows: (string | null)[][]; row_count: number }>(`/catalog/tables/${catalog}/${schema}/${table}/sample-data`, { params: { limit } }).then((r) => r.data),
  // Remote database browsing endpoints using app-wide DB Connection IDs or External Connection IDs
  browseDatabases: (connId: number | string) => api.get<Array<{ name: string }>>(`/catalog/connections/${connId}/browse/databases`).then((r) => r.data),
  browseSchemas: (connId: number | string, database: string) => api.get<Array<{ name: string }>>(`/catalog/connections/${connId}/browse/schemas`, { params: { database } }).then((r) => r.data),
  browseTables: (connId: number | string, database: string, schemaName: string) => api.get<Array<{ name: string }>>(`/catalog/connections/${connId}/browse/tables`, { params: { database, schema_name: schemaName } }).then((r) => r.data),
  // Iceberg blob-storage routes
  createIcebergSchema: (catalog: string, schemaName: string, storageBacked: string, description?: string) =>
    api.post<any>(`/catalog/iceberg/schemas`, null, { params: { catalog, schema_name: schemaName, storage_backend: storageBacked, description } }).then((r) => r.data),
  createIcebergTable: (body: Record<string, any>) => api.post<any>('/catalog/iceberg/tables', body).then((r) => r.data),
  createTableFromFile: (catalogName: string, schemaName: string, formData: FormData) =>
    api.post<any>(`/catalog/catalogs/${encodeURIComponent(catalogName)}/schemas/${encodeURIComponent(schemaName)}/tables-from-file`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then((r) => r.data),
  // Storage backend management
  listStorageBackends: () => api.get<Array<{ id: string; name: string; provider: string; is_default: boolean; container_or_bucket: string; base_path: string }>>('/storage/backends').then((r) => r.data),
  createStorageBackend: (body: Record<string, any>) => api.post<any>('/storage/backends', body).then((r) => r.data),
  testStorageBackend: (name: string) => api.get<any>(`/storage/backends/${encodeURIComponent(name)}/test`).then((r) => r.data),
};

function cx(...parts: Array<string | false | null | undefined>) { return parts.filter(Boolean).join(' '); }

function getMutationErrorMessage(error: unknown) {
  const apiMessage = (error as any)?.response?.data?.detail;
  return typeof apiMessage === 'string' ? apiMessage : 'Creation failed. Try again.';
}

function Dialog({ title, subtitle, onClose, children }: { title: string; subtitle: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="uc-modal-overlay" onClick={onClose}>
      <div className="uc-modal" onClick={(e) => e.stopPropagation()}>
        <div className="uc-modal-header">
          <div><h3>{title}</h3><p>{subtitle}</p></div>
          <button className="uc-icon-btn" onClick={onClose}><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function DataCatalog() {
  const qc = useQueryClient();
  const queryClient = qc;
  const navigate = useScopedNavigate();
  const {
    catalog: urlCatalog,
    schema: urlSchema,
    table: urlTable,
    volume: urlVolume,
    notebook: urlNotebook,
    dashboard: urlDashboard,
    tool: urlTool,
    query: urlQuery,
  } = useParams<{
    catalog?: string;
    schema?: string;
    table?: string;
    volume?: string;
    notebook?: string;
    dashboard?: string;
    tool?: string;
    query?: string;
  }>();
  const [searchParams] = useSearchParams();

  // Derive initial selection from URL params & query string
  const initialSelection = useMemo<Selection>(() => {
    if (urlCatalog && urlSchema) {
      if (urlNotebook) {
        const decodedNb = decodeURIComponent(urlNotebook);
        const nbName = decodedNb.endsWith('.ipynb') ? decodedNb.slice(0, -6) : decodedNb;
        const blob_path = searchParams.get('path') || `${urlCatalog}/${urlSchema}/${nbName}.ipynb`;
        return { kind: 'notebook', catalog: urlCatalog, schema: urlSchema, notebook: nbName, blob_path };
      }
      if (urlDashboard) {
        const decoded = decodeURIComponent(urlDashboard);
        const dashboardId = searchParams.get('dashboard_id') || undefined;
        return { kind: 'dashboard', catalog: urlCatalog, schema: urlSchema, dashboard: decoded, dashboard_id: dashboardId };
      }
      if (urlVolume) {
        const decoded = decodeURIComponent(urlVolume);
        return { kind: 'volume', catalog: urlCatalog, schema: urlSchema, volume: decoded };
      }
      if (urlTool) {
        const decoded = decodeURIComponent(urlTool);
        const toolId = searchParams.get('tool_id') || undefined;
        return { kind: 'tool', catalog: urlCatalog, schema: urlSchema, tool: decoded, tool_id: toolId };
      }
      if (urlQuery || searchParams.get('kind') === 'query') {
        const decoded = decodeURIComponent(urlQuery || searchParams.get('query') || '');
        return { kind: 'query', catalog: urlCatalog, schema: urlSchema, query: decoded };
      }
      if (urlTable) {
        const decoded = decodeURIComponent(urlTable);
        if (decoded.endsWith('.ipynb') || searchParams.get('kind') === 'notebook') {
          const nbName = decoded.endsWith('.ipynb') ? decoded.slice(0, -6) : decoded;
          const blob_path = searchParams.get('path') || `${urlCatalog}/${urlSchema}/${nbName}.ipynb`;
          return { kind: 'notebook', catalog: urlCatalog, schema: urlSchema, notebook: nbName, blob_path };
        }
        if (searchParams.get('kind') === 'dashboard') {
          return { kind: 'dashboard', catalog: urlCatalog, schema: urlSchema, dashboard: decoded, dashboard_id: searchParams.get('dashboard_id') || undefined };
        }
        if (searchParams.get('kind') === 'volume') {
          return { kind: 'volume', catalog: urlCatalog, schema: urlSchema, volume: decoded };
        }
        if (searchParams.get('kind') === 'tool') {
          return { kind: 'tool', catalog: urlCatalog, schema: urlSchema, tool: decoded, tool_id: searchParams.get('tool_id') || undefined };
        }
        if (searchParams.get('kind') === 'query') {
          return { kind: 'query', catalog: urlCatalog, schema: urlSchema, query: decoded };
        }
        return { kind: 'table', catalog: urlCatalog, schema: urlSchema, table: decoded };
      }
    }
    if (searchParams.get('path')) {
      const queryPath = searchParams.get('path')!;
      const clean = queryPath.replace(/\\/g, '/').replace(/^\//, '');
      const parts = clean.split('/');
      if (parts.length >= 3) {
        const catalog = parts[0];
        const schema = parts[1];
        const filename = parts.slice(2).join('/');
        const nbName = filename.endsWith('.ipynb') ? filename.slice(0, -6) : filename;
        return { kind: 'notebook', catalog, schema, notebook: nbName, blob_path: clean };
      } else {
        const filename = parts[parts.length - 1];
        const nbName = filename.endsWith('.ipynb') ? filename.slice(0, -6) : filename;
        const catalog = urlCatalog || 'main';
        const schema = urlSchema || 'default';
        return { kind: 'notebook', catalog, schema, notebook: nbName, blob_path: clean };
      }
    }
    if (urlCatalog && urlSchema) return { kind: 'schema', catalog: urlCatalog, schema: urlSchema };
    if (urlCatalog) return { kind: 'catalog', catalog: urlCatalog };
    return { kind: 'root' };
  }, [urlCatalog, urlSchema, urlTable, urlVolume, urlNotebook, urlDashboard, urlTool, urlQuery, searchParams]);

  // Selection and Search States
  const [selection, setSelection] = useState<Selection>(initialSelection);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Expanded Nodes state — pre-open if URL has catalog/schema
  const [expandedCatalogs, setExpandedCatalogs] = useState<Record<string, boolean>>(
    urlCatalog ? { [urlCatalog]: true } : {}
  );
  const [expandedSchemas, setExpandedSchemas] = useState<Record<string, boolean>>(
    urlCatalog && urlSchema ? { [`${urlCatalog}.${urlSchema}`]: true } : {}
  );
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    if (!urlCatalog || !urlSchema) return {};
    const base = `${urlCatalog}.${urlSchema}`;
    if (urlNotebook || searchParams.get('kind') === 'notebook' || urlTable?.endsWith('.ipynb')) {
      return { [`${base}.notebooks`]: true };
    }
    if (urlVolume || searchParams.get('kind') === 'volume') {
      return { [`${base}.volumes`]: true };
    }
    if (urlDashboard || searchParams.get('kind') === 'dashboard') {
      return { [`${base}.dashboards`]: true };
    }
    if (urlTool || searchParams.get('kind') === 'tool') {
      return { [`${base}.tools`]: true };
    }
    if (urlQuery || searchParams.get('kind') === 'query') {
      return { [`${base}.queries`]: true };
    }
    if (urlTable) {
      return { [`${base}.tables`]: true };
    }
    return {};
  });

  // Tree item caches
  const [schemaTablesCache, setSchemaTablesCache] = useState<Record<string, CatalogTable[]>>({});
  const [loadingSchemaTables, setLoadingSchemaTables] = useState<Record<string, boolean>>({});

  const [schemaVolumesCache, setSchemaVolumesCache] = useState<Record<string, CatalogVolume[]>>({});
  const [loadingSchemaVolumes, setLoadingSchemaVolumes] = useState<Record<string, boolean>>({});

  const [schemaNotebooksCache, setSchemaNotebooksCache] = useState<Record<string, CatalogNotebook[]>>({});
  const [loadingSchemaNotebooks, setLoadingSchemaNotebooks] = useState<Record<string, boolean>>({});

  const [schemaDashboardsCache, setSchemaDashboardsCache] = useState<Record<string, CatalogDashboard[]>>({});
  const [loadingSchemaDashboards, setLoadingSchemaDashboards] = useState<Record<string, boolean>>({});

  const [schemaToolsCache, setSchemaToolsCache] = useState<Record<string, CatalogTool[]>>({});
  const [loadingSchemaTools, setLoadingSchemaTools] = useState<Record<string, boolean>>({});

  const [schemaQueriesCache, setSchemaQueriesCache] = useState<Record<string, CatalogQuery[]>>({});
  const [loadingSchemaQueries, setLoadingSchemaQueries] = useState<Record<string, boolean>>({});
  const [pendingCatalogAssets, setPendingCatalogAssets] = useState<PendingCatalogAsset[]>([]);

  // Governed Notebook editing / execution states
  const [editingNbComment, setEditingNbComment] = useState<string | null>(null);
  const [editingNbOwner, setEditingNbOwner] = useState<string | null>(null);
  const [showMoveNbModal, setShowMoveNbModal] = useState(false);
  const [moveNbTargetCatalog, setMoveNbTargetCatalog] = useState('');
  const [moveNbTargetSchema, setMoveNbTargetSchema] = useState('');
  const [moveNbNewName, setMoveNbNewName] = useState('');
  const [executingNotebook, setExecutingNotebook] = useState(false);
  const [executionOutput, setExecutionOutput] = useState<any[] | null>(null);
  
  // Modal & Dropdown states
  const [showCatalogModal, setShowCatalogModal] = useState(false);
  const [showSettingsDropdown, setShowSettingsDropdown] = useState(false);
  const [showMoreActionsDropdown, setShowMoreActionsDropdown] = useState(false);
  const [showDeleteCatalogModal, setShowDeleteCatalogModal] = useState(false);
  const [deleteCatalogConfirmText, setDeleteCatalogConfirmText] = useState('');
  const [tableToDelete, setTableToDelete] = useState<{ catalog: string; schema: string; table: string } | null>(null);
  const moreActionsBtnRef = useRef<HTMLButtonElement>(null);
  const moreActionsDropdownRef = useRef<HTMLDivElement>(null);
  const [showPlusDropdown, setShowPlusDropdown] = useState(false);
  const [showCreateDropdown, setShowCreateDropdown] = useState(false);

  // Create Schema state
  const [showSchemaModal, setShowSchemaModal] = useState(false);
  const [schemaForm, setSchemaForm] = useState({ name: '', description: '', storageBackend: '' });

  // Notebook states
  const [showNbModal, setShowNbModal] = useState(false);
  const [nbForm, setNbForm] = useState({ name: '', blob_path: '', owner: 'catalog-admin', comment: '' });

  // Dashboard states
  const [showDashboardModal, setShowDashboardModal] = useState(false);
  const [dbForm, setDbForm] = useState({ name: '', comment: '' });
  const [showMoveDbModal, setShowMoveDbModal] = useState(false);
  const [moveDbTargetCatalog, setMoveDbTargetCatalog] = useState('');
  const [moveDbTargetSchema, setMoveDbTargetSchema] = useState('');
  const [moveDbNewName, setMoveDbNewName] = useState('');
  const [editingDbComment, setEditingDbComment] = useState<string | null>(null);
  const [editingDbOwner, setEditingDbOwner] = useState<string | null>(null);

  // Schema overview subtab state
  const [schemaSubTab, setSchemaSubTab] = useState<'tables' | 'volumes' | 'notebooks' | 'dashboards' | 'tools' | 'queries'>(() => {
    if (urlNotebook || searchParams.get('kind') === 'notebook' || urlTable?.endsWith('.ipynb')) return 'notebooks';
    if (urlVolume || searchParams.get('kind') === 'volume') return 'volumes';
    if (urlDashboard || searchParams.get('kind') === 'dashboard') return 'dashboards';
    if (urlTool || searchParams.get('kind') === 'tool') return 'tools';
    if (urlQuery || searchParams.get('kind') === 'query') return 'queries';
    return 'tables';
  });
  const [selectedToolVersionId, setSelectedToolVersionId] = useState<string | null>(null);

  // Create Table state
  const [showTableModal, setShowTableModal] = useState(false);
  const [tableForm, setTableForm] = useState({ name: '', description: '' });
  const [tableColumns, setTableColumns] = useState<Array<{ name: string; data_type: string; nullable: boolean }>>([]);

  // Create Table from File Upload state
  const [realUploadedFile, setRealUploadedFile] = useState<File | null>(null);
  const [tableNameInput, setTableNameInput] = useState('');
  const [tableDescriptionInput, setTableDescriptionInput] = useState('');
  const [selectedCatalogName, setSelectedCatalogName] = useState('');
  const [selectedSchemaName, setSelectedSchemaName] = useState('');
  const [previewMode, setPreviewMode] = useState<'table' | 'json'>('table');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [previewColumns, setPreviewColumns] = useState<string[]>([]);
  const [previewRows, setPreviewRows] = useState<string[][]>([]);
  const [inferredTypes, setInferredTypes] = useState<Record<string, string>>({});
  const [isDragOver, setIsDragOver] = useState(false);

  // Create Volume state
  const [showVolumeModal, setShowVolumeModal] = useState(false);
  const [volumeForm, setVolumeForm] = useState({ name: '', description: '' });
  const [currentVolumePath, setCurrentVolumePath] = useState('');

  // Storage backends cache
  const [storageBackends, setStorageBackends] = useState<Array<{ id: string; name: string; provider: string; is_default: boolean }>>([]);
  const [showStorageModal, setShowStorageModal] = useState(false);
  const [storageForm, setStorageForm] = useState({ name: '', provider: 'azure', bucket: '', base_path: 'compassx/', account_name: '', container: '', account_key: '', region: 'us-east-1', access_key: '', secret_key: '', endpoint_url: '', is_default: false });

  // Dropdown anchor refs for fixed positioning
  const settingsBtnRef = useRef<HTMLButtonElement>(null);
  const plusBtnRef = useRef<HTMLButtonElement>(null);
  const createBtnRef = useRef<HTMLButtonElement>(null);

  const settingsDropdownRef = useRef<HTMLDivElement>(null);
  const plusDropdownRef = useRef<HTMLDivElement>(null);
  const createDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    if (!showSettingsDropdown && !showPlusDropdown && !showCreateDropdown && !showMoreActionsDropdown) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (showSettingsDropdown && settingsDropdownRef.current && !settingsDropdownRef.current.contains(target) && !settingsBtnRef.current?.contains(target)) {
        setShowSettingsDropdown(false);
      }
      if (showPlusDropdown && plusDropdownRef.current && !plusDropdownRef.current.contains(target) && !plusBtnRef.current?.contains(target)) {
        setShowPlusDropdown(false);
      }
      if (showCreateDropdown && createDropdownRef.current && !createDropdownRef.current.contains(target) && !createBtnRef.current?.contains(target)) {
        setShowCreateDropdown(false);
      }
      if (showMoreActionsDropdown && moreActionsDropdownRef.current && !moreActionsDropdownRef.current.contains(target) && !moreActionsBtnRef.current?.contains(target)) {
        setShowMoreActionsDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showSettingsDropdown, showPlusDropdown, showCreateDropdown, showMoreActionsDropdown]);

  const getDropdownPos = (btnRef: React.RefObject<HTMLButtonElement | null>) => {
    const rect = btnRef.current?.getBoundingClientRect();
    if (!rect) return { top: 0, right: 0 };
    return { top: rect.bottom + 4, right: window.innerWidth - rect.right };
  };

  // Dynamic Db Connection Browsing States (Catalog Creation)
  const [catalogFormDbs, setCatalogFormDbs] = useState<Array<{ name: string }>>([]);
  const [loadingCatalogDbs, setLoadingCatalogDbs] = useState(false);
  const [catalogBrowseError, setCatalogBrowseError] = useState('');

  const [catalogForm, setCatalogForm] = useState<CatalogForm>({
    name: '',
    description: '',
    catalog_type: 'iceberg',
    connection_id: '',
    database_name: '',
    storageBackend: '',
  });

  // Active tab per selection level
  const [activeTab, setActiveTab] = useState<string>('overview');

  // Secondary sidebar collapse state
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('compassx_catalog_sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const toggleSidebarCollapse = useCallback(() => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('compassx_catalog_sidebar_collapsed', String(next));
      } catch {}
      return next;
    });
  }, []);

  // Restore open tabs from localStorage
  const persistedTabs = useMemo(() => loadPersistedTabs(), []);
  
  const getOpenPanelId = useCallback((next: Exclude<Selection, null | { kind: 'root' }>) => {
    if (next.kind === 'notebook') return `notebook:${next.catalog}.${next.schema}.${next.notebook}`;
    if (next.kind === 'dashboard') return `dashboard:${next.catalog}.${next.schema}.${next.dashboard}`;
    if (next.kind === 'query') return `query:${next.catalog}.${next.schema}.${next.query}`;
    return 'details';
  }, []);

  const getOpenPanelLabel = useCallback((next: Exclude<Selection, null | { kind: 'root' }>) => {
    if (next.kind === 'notebook') return next.notebook;
    if (next.kind === 'dashboard') return next.dashboard;
    if (next.kind === 'query') return next.query;
    return 'Details';
  }, []);

  const initialOpenPanels = useMemo(() => {
    const saved = persistedTabs?.openPanels || [];
    if (initialSelection && (initialSelection.kind === 'notebook' || initialSelection.kind === 'dashboard' || initialSelection.kind === 'query')) {
      const id = getOpenPanelId(initialSelection);
      const label = getOpenPanelLabel(initialSelection);
      if (!saved.some((p) => p.id === id)) {
        return [...saved, { id, label, selection: initialSelection }];
      }
    }
    return saved;
  }, [initialSelection, persistedTabs, getOpenPanelId, getOpenPanelLabel]);

  const initialMainTabId = useMemo(() => {
    if (initialSelection && (initialSelection.kind === 'notebook' || initialSelection.kind === 'dashboard' || initialSelection.kind === 'query')) {
      return getOpenPanelId(initialSelection);
    }
    return persistedTabs?.mainTabId || 'details';
  }, [initialSelection, persistedTabs, getOpenPanelId]);

  const [openPanels, setOpenPanels] = useState<Array<{ id: string; label: string; selection: Exclude<Selection, null | { kind: 'root' }>; }>>(initialOpenPanels);
  const [mainTabId, setMainTabId] = useState<string>(initialMainTabId);
  const [detailsSelection, setDetailsSelection] = useState<Selection>(persistedTabs?.detailsSelection || (initialSelection?.kind === 'catalog' || initialSelection?.kind === 'schema' || initialSelection?.kind === 'table' ? initialSelection : { kind: 'root' }));

  // Save open tabs state to localStorage whenever tabs or selections change
  useEffect(() => {
    savePersistedTabs({ openPanels, mainTabId, detailsSelection });
  }, [openPanels, mainTabId, detailsSelection]);

  // Synchronize route/URL changes to selection, open panels, and active tab
  useEffect(() => {
    if (!initialSelection) return;
    setSelection(initialSelection);
    if (initialSelection.kind === 'notebook' || initialSelection.kind === 'dashboard' || initialSelection.kind === 'query') {
      const id = getOpenPanelId(initialSelection);
      const label = getOpenPanelLabel(initialSelection);
      setOpenPanels((prev) => {
        if (!prev.some((p) => p.id === id)) {
          return [...prev, { id, label, selection: initialSelection }];
        }
        return prev;
      });
      setMainTabId(id);
    } else {
      setDetailsSelection(initialSelection);
      setMainTabId('details');
    }

    if ('catalog' in initialSelection && initialSelection.catalog) {
      setExpandedCatalogs((prev) => ({ ...prev, [initialSelection.catalog]: true }));
      if ('schema' in initialSelection && initialSelection.schema) {
        const schemaKey = `${initialSelection.catalog}.${initialSelection.schema}`;
        setExpandedSchemas((prev) => ({ ...prev, [schemaKey]: true }));
        if (initialSelection.kind === 'notebook') {
          setExpandedGroups((prev) => ({ ...prev, [`${schemaKey}.notebooks`]: true, [`${schemaKey}-notebooks`]: true }));
        }
        if (initialSelection.kind === 'dashboard') {
          setExpandedGroups((prev) => ({ ...prev, [`${schemaKey}.dashboards`]: true, [`${schemaKey}-dashboards`]: true }));
        }
        if (initialSelection.kind === 'query') {
          setExpandedGroups((prev) => ({ ...prev, [`${schemaKey}.queries`]: true, [`${schemaKey}-queries`]: true }));
        }
      }
    }
  }, [initialSelection, getOpenPanelId, getOpenPanelLabel]);

  // Synchronize notebook store active path whenever a notebook is selected
  useEffect(() => {
    if (selection && selection.kind === 'notebook') {
      const path = selection.blob_path || `${selection.catalog}/${selection.schema}/${selection.notebook}.ipynb`;
      useNotebookStore.getState().setNotebookPath(path);
    }
  }, [selection]);

  const setDetailsPanelSelection = useCallback((next: Selection) => {
    setDetailsSelection(next);
    setSelection(next);
    setMainTabId('details');
  }, []);

  const syncOpenPanel = useCallback((next: Exclude<Selection, null | { kind: 'root' }>) => {
    const id = getOpenPanelId(next);
    const label = getOpenPanelLabel(next);
    setDetailsSelection(next);
    setOpenPanels((prev) => {
      const existing = prev.find((panel) => panel.id === id);
      if (existing) {
        return prev.map((panel) => (panel.id === id ? { ...panel, label, selection: next } : panel));
      }
      return [...prev, { id, label, selection: next }];
    });
    setMainTabId(id);
    setSelection(next);
  }, [getOpenPanelId, getOpenPanelLabel]);

  const replaceOpenPanel = useCallback((oldSelection: Exclude<Selection, null | { kind: 'root' }>, next: Exclude<Selection, null | { kind: 'root' }>) => {
    const oldId = getOpenPanelId(oldSelection);
    const newId = getOpenPanelId(next);
    const label = getOpenPanelLabel(next);
    setDetailsSelection(next);
    setOpenPanels((prev) => {
      const withoutOld = prev.filter((panel) => panel.id !== oldId);
      const updated = withoutOld.some((panel) => panel.id === newId)
        ? withoutOld.map((panel) => (panel.id === newId ? { ...panel, label, selection: next } : panel))
        : [...withoutOld, { id: newId, label, selection: next }];
      return updated;
    });
    setMainTabId(newId);
    setSelection(next);
  }, [getOpenPanelId, getOpenPanelLabel]);

  const closeOpenPanel = useCallback((panelId: string) => {
    setOpenPanels((prev) => prev.filter((panel) => panel.id !== panelId));
    if (mainTabId === panelId) {
      setMainTabId('details');
      setSelection(detailsSelection);
      if (!detailsSelection || detailsSelection.kind === 'root') {
        navigate('/data-catalog');
      } else if (detailsSelection.kind === 'catalog') {
        navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}`);
      } else if (detailsSelection.kind === 'schema') {
        navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}`);
      } else if (detailsSelection.kind === 'table') {
        navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}/table/${encodeURIComponent(detailsSelection.table)}`);
      } else if (detailsSelection.kind === 'volume') {
        navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}/volume/${encodeURIComponent(detailsSelection.volume)}`);
      } else if (detailsSelection.kind === 'tool') {
        const q = (detailsSelection as any).tool_id ? `?tool_id=${encodeURIComponent((detailsSelection as any).tool_id)}` : '';
        navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}/tool/${encodeURIComponent((detailsSelection as any).tool)}${q}`);
      } else if (detailsSelection.kind === 'query') {
        navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}?kind=query&query=${encodeURIComponent(detailsSelection.query)}`);
      } else {
        navigate('/data-catalog');
      }
    }
  }, [detailsSelection, mainTabId, navigate]);

  // Navigate selection + push RESTful URL / open right-side tabs
  const selectAndNavigate = useCallback((next: Selection) => {
    if (!next || next.kind === 'root') {
      setDetailsPanelSelection(next);
      navigate('/data-catalog');
      return;
    }

    if (next.kind === 'notebook' || next.kind === 'dashboard' || next.kind === 'query') {
      syncOpenPanel(next);
      if (next.kind === 'notebook') {
        const path = next.blob_path ? `?path=${encodeURIComponent(next.blob_path)}` : '';
        const nbName = next.notebook.endsWith('.ipynb') ? next.notebook.slice(0, -6) : next.notebook;
        navigate(`/data-catalog/${encodeURIComponent(next.catalog)}/${encodeURIComponent(next.schema)}/notebook/${encodeURIComponent(nbName)}${path}`);
      } else if (next.kind === 'dashboard') {
        const q = next.dashboard_id ? `?dashboard_id=${encodeURIComponent(next.dashboard_id)}` : '';
        navigate(`/data-catalog/${encodeURIComponent(next.catalog)}/${encodeURIComponent(next.schema)}/dashboard/${encodeURIComponent(next.dashboard)}${q}`);
      } else if (next.kind === 'query') {
        navigate(`/data-catalog/${encodeURIComponent(next.catalog)}/${encodeURIComponent(next.schema)}?kind=query&query=${encodeURIComponent(next.query)}`);
      }
      return;
    }

    setDetailsPanelSelection(next);
    if (next.kind === 'catalog') {
      navigate(`/data-catalog/${encodeURIComponent(next.catalog)}`);
    } else if (next.kind === 'schema') {
      navigate(`/data-catalog/${encodeURIComponent(next.catalog)}/${encodeURIComponent(next.schema)}`);
    } else if (next.kind === 'table') {
      navigate(`/data-catalog/${encodeURIComponent(next.catalog)}/${encodeURIComponent(next.schema)}/table/${encodeURIComponent(next.table)}`);
    } else if (next.kind === 'volume') {
      navigate(`/data-catalog/${encodeURIComponent(next.catalog)}/${encodeURIComponent(next.schema)}/volume/${encodeURIComponent(next.volume)}`);
    } else if (next.kind === 'tool') {
      const q = (next as any).tool_id ? `?tool_id=${encodeURIComponent((next as any).tool_id)}` : '';
      navigate(`/data-catalog/${encodeURIComponent(next.catalog)}/${encodeURIComponent(next.schema)}/tool/${encodeURIComponent((next as any).tool)}${q}`);
    }
  }, [navigate, setDetailsPanelSelection, syncOpenPanel]);

  // Interactive details page states
  const [favorites, setFavorites] = useState<Record<string, boolean>>({});
  const [copiedFqn, setCopiedFqn] = useState<string | null>(null);
  const [schemaTableFilter, setSchemaTableFilter] = useState('');
  const [schemaTableSort, setSchemaTableSort] = useState<'name' | 'created_at'>('name');
  const [fileSearchQuery, setFileSearchQuery] = useState('');
  
  // Custom metadata states for simulated persistence
  const [dynamicOwners, setDynamicOwners] = useState<Record<string, string>>({});
  const [editingOwnerId, setEditingOwnerId] = useState<string | null>(null);
  const [newOwnerValue, setNewOwnerValue] = useState('');

  const [selectedWarehouseId, setSelectedWarehouseId] = useState<string>('');

  // Schema permissions roles states
  const [customReadRoles, setCustomReadRoles] = useState<Record<string, string[]>>({});
  const [customWriteRoles, setCustomWriteRoles] = useState<Record<string, string[]>>({});
  const [newReadRole, setNewReadRole] = useState('');
  const [newWriteRole, setNewWriteRole] = useState('');

  const catalogsQuery = useQuery({ queryKey: ['uc-catalogs'], queryFn: catalogApi.listCatalogs });
  
  // Query external connections from '/connections'
  const externalConnectionsQuery = useCatalogConnections();

  // Query application-wide DB Connections from '/db-connections'
  const connectionsQuery = useQuery({ 
    queryKey: ['db-connections'], 
    queryFn: () => api.get<DBConnection[]>('/db-connections').then((r) => r.data) 
  });

  const warehousesQuery = useQuery({
    queryKey: ['sql-warehouses-list'],
    queryFn: () => api.get<any[]>('/warehouses').then((r) => r.data),
  });

  const warehouses = warehousesQuery.data || [];
  
  useEffect(() => {
    if (!selectedWarehouseId && warehouses.length > 0) {
      const runningWh = warehouses.find(w => w.status?.toUpperCase() === 'RUNNING') || warehouses[0];
      if (runningWh) {
        setSelectedWarehouseId(runningWh.id);
      }
    }
  }, [warehouses, selectedWarehouseId]);

  // Keep selectedCatalogName and selectedSchemaName in sync with selection / available catalogs
  useEffect(() => {
    if (catalogsQuery.data && catalogsQuery.data.length > 0) {
      const activeCat = selectedCatalogName || (selection as any)?.catalog || catalogsQuery.data[0].name;
      if (activeCat !== selectedCatalogName) {
        setSelectedCatalogName(activeCat);
      }
      const catObj = catalogsQuery.data.find(c => c.name === activeCat) || catalogsQuery.data[0];
      const activeSch = selectedSchemaName || (selection as any)?.schema || (catObj?.schemas?.[0]?.name || '');
      if (activeSch !== selectedSchemaName) {
        setSelectedSchemaName(activeSch);
      }
    }
  }, [catalogsQuery.data, selection, selectedCatalogName, selectedSchemaName, showTableModal]);

  // Filter connections list to only show Postgres connections (external connections + db connections)
  const postgresConnections = useMemo(() => {
    const extList = (externalConnectionsQuery.data || [])
      .filter((conn) => {
        const t = (conn.connector_type || (conn as any).type_id || '').toLowerCase();
        return t === 'postgres' || t === 'postgresql';
      })
      .map((conn) => ({
        id: String(conn.id),
        name: conn.name,
        type: 'external' as const,
      }));

    const dbList = (connectionsQuery.data || [])
      .filter((conn) => {
        const t = (conn.db_type || '').toLowerCase();
        return t === 'postgres' || t === 'postgresql';
      })
      .map((conn) => ({
        id: String(conn.id),
        name: conn.name,
        type: 'db' as const,
      }));

    const combined: Array<{ id: string; name: string; type: 'external' | 'db' }> = [...extList];
    for (const dbConn of dbList) {
      if (!combined.some((item) => item.id === dbConn.id || item.name === dbConn.name)) {
        combined.push(dbConn);
      }
    }
    return combined;
  }, [externalConnectionsQuery.data, connectionsQuery.data]);

  const activeCatalog = selection && selection.kind !== 'root' ? selection.catalog : null;
  const activeSchema = selection && selection.kind !== 'root' && selection.kind !== 'catalog' ? selection.schema : null;

  const schemaTablesQuery = useQuery({
    queryKey: ['uc-schema-tables', activeCatalog, activeSchema],
    queryFn: () => catalogApi.listTables(activeCatalog || undefined, activeSchema || undefined),
    enabled: !!activeCatalog && !!activeSchema,
  });

  const schemaVolumesQuery = useQuery({
    queryKey: ['uc-schema-volumes', activeCatalog, activeSchema],
    queryFn: () => catalogApi.listVolumes(activeCatalog || undefined, activeSchema || undefined),
    enabled: !!activeCatalog && !!activeSchema,
  });

  const schemaNotebooksQuery = useQuery({
    queryKey: ['uc-schema-notebooks', activeCatalog, activeSchema],
    queryFn: () => catalogApi.listNotebooks(activeCatalog!, activeSchema!),
    enabled: !!activeCatalog && !!activeSchema,
  });

  const schemaDashboardsQuery = useQuery({
    queryKey: ['uc-schema-dashboards', activeCatalog, activeSchema],
    queryFn: () => catalogApi.listDashboards(activeCatalog!, activeSchema!),
    enabled: !!activeCatalog && !!activeSchema,
  });

  const schemaQueriesQuery = useQuery({
    queryKey: ['uc-schema-queries', activeCatalog, activeSchema],
    queryFn: () => catalogApi.listQueries(activeCatalog!, activeSchema!),
    enabled: !!activeCatalog && !!activeSchema,
  });

  const beginPendingAsset = useCallback((kind: CatalogAssetKind, catalog: string, schema: string, name: string): PendingAssetContext => {
    const pendingId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setPendingCatalogAssets((current) => [
      ...current.filter((asset) => !(asset.kind === kind && asset.catalog === catalog && asset.schema === schema && asset.name === name)),
      { id: pendingId, kind, catalog, schema, name, status: 'creating' }
    ]);
    setExpandedCatalogs((current) => ({ ...current, [catalog]: true }));
    setExpandedSchemas((current) => ({ ...current, [`${catalog}.${schema}`]: true }));
    setExpandedGroups((current) => ({ ...current, [`${catalog}.${schema}-${kind}s`]: true }));
    return { pendingId, catalog, schema, name };
  }, []);

  const failPendingAsset = useCallback((context: PendingAssetContext | undefined, error: unknown) => {
    if (!context) return;
    setPendingCatalogAssets((current) => current.map((asset) => (
      asset.id === context.pendingId
        ? { ...asset, status: 'failed', error: getMutationErrorMessage(error) }
        : asset
    )));
  }, []);

  const finishPendingAsset = useCallback((kind: CatalogAssetKind, context: PendingAssetContext | undefined, createdAsset: any) => {
    if (!context) return;
    const schemaKey = `${context.catalog}.${context.schema}`;
    const asset = { ...createdAsset, id: createdAsset?.id || context.pendingId, name: createdAsset?.name || context.name };
    const upsert = <T extends { name: string },>(items: T[] | undefined) => [
      ...(items || []).filter((item) => item.name !== context.name),
      asset as T
    ];

    if (kind === 'table') {
      setSchemaTablesCache((current) => ({ ...current, [schemaKey]: upsert(current[schemaKey]) }));
      queryClient.setQueryData<CatalogTable[]>(['uc-schema-tables', context.catalog, context.schema], upsert);
    } else if (kind === 'volume') {
      setSchemaVolumesCache((current) => ({ ...current, [schemaKey]: upsert(current[schemaKey]) }));
      queryClient.setQueryData<CatalogVolume[]>(['uc-schema-volumes', context.catalog, context.schema], upsert);
    } else if (kind === 'notebook') {
      setSchemaNotebooksCache((current) => ({ ...current, [schemaKey]: upsert(current[schemaKey]) }));
      queryClient.setQueryData<CatalogNotebook[]>(['uc-schema-notebooks', context.catalog, context.schema], upsert);
    } else {
      setSchemaDashboardsCache((current) => ({ ...current, [schemaKey]: upsert(current[schemaKey]) }));
      queryClient.setQueryData<CatalogDashboard[]>(['uc-schema-dashboards', context.catalog, context.schema], upsert);
    }

    setPendingCatalogAssets((current) => current.filter((item) => item.id !== context.pendingId));
  }, [queryClient]);

  const activeVolume = useMemo(() => {
    if (selection?.kind !== 'volume') return undefined;
    const vols = schemaVolumesCache[`${selection.catalog}.${selection.schema}`] || [];
    return vols.find(v => v.name === selection.volume);
  }, [selection, schemaVolumesCache]);

  const volumeFilesQuery = useQuery({
    queryKey: ['uc-volume-files', activeVolume?.id],
    queryFn: () => catalogApi.listVolumeFiles(activeVolume!.id),
    enabled: !!activeVolume?.id,
  });

  const currentLevelItems = useMemo(() => {
    const files = volumeFilesQuery.data || [];
    const itemsMap = new Map<string, VolumeFileInfo>();

    files.forEach(file => {
      if (!file.file_path.startsWith(currentVolumePath)) return;
      
      const relative = file.file_path.substring(currentVolumePath.length);
      if (relative === '' || relative === '.keep') return;
      
      const parts = relative.split('/');
      
      if (parts.length > 1 || (parts.length === 1 && file.file_path.endsWith('/'))) {
        const dirName = parts[0];
        const dirPath = currentVolumePath + dirName + '/';
        if (!itemsMap.has(dirPath)) {
          itemsMap.set(dirPath, {
            file_path: dirPath,
            file_name: dirName + '/',
            size_bytes: 0,
            content_type: 'application/x-directory',
            last_modified: file.last_modified,
            uploaded_by: file.uploaded_by
          });
        }
      } else {
        itemsMap.set(file.file_path, file);
      }
    });

    return Array.from(itemsMap.values());
  }, [volumeFilesQuery.data, currentVolumePath]);

  const filteredFiles = useMemo(() => {
    if (!fileSearchQuery.trim()) return currentLevelItems;
    return currentLevelItems.filter(f => f.file_name.toLowerCase().includes(fileSearchQuery.toLowerCase()));
  }, [currentLevelItems, fileSearchQuery]);

  const tableQuery = useQuery({
    queryKey: ['uc-table', selection?.kind === 'table' ? selection.catalog : null, selection?.kind === 'table' ? selection.schema : null, selection?.kind === 'table' ? selection.table : null],
    queryFn: () => catalogApi.getTable((selection as { catalog: string }).catalog, (selection as { schema: string }).schema, (selection as { table: string }).table),
    enabled: !!selection && selection.kind === 'table',
  });

  const notebookQuery = useQuery({
    queryKey: ['uc-notebook', selection?.kind === 'notebook' ? selection.catalog : null, selection?.kind === 'notebook' ? selection.schema : null, selection?.kind === 'notebook' ? selection.notebook : null],
    queryFn: () => catalogApi.getNotebook((selection as any).catalog, (selection as any).schema, (selection as any).notebook),
    enabled: !!selection && selection.kind === 'notebook',
  });

  const dashboardQuery = useQuery({
    queryKey: ['uc-dashboard', selection?.kind === 'dashboard' ? selection.catalog : null, selection?.kind === 'dashboard' ? selection.schema : null, selection?.kind === 'dashboard' ? (selection as any).dashboard : null],
    queryFn: () => catalogApi.getDashboard((selection as any).catalog, (selection as any).schema, (selection as any).dashboard),
    enabled: !!selection && selection.kind === 'dashboard',
  });

  const toolQuery = useQuery({
    queryKey: ['uc-tool', selection?.kind === 'tool' ? selection.catalog : null, selection?.kind === 'tool' ? selection.schema : null, selection?.kind === 'tool' ? (selection as any).tool : null, selection?.kind === 'tool' ? (selection as any).tool_id : null],
    queryFn: async () => {
      if (!selection || selection.kind !== 'tool') return null;
      if ((selection as any).tool_id) {
        return catalogApi.getTool((selection as any).tool_id);
      }
      const tools = await catalogApi.listTools(selection.catalog, selection.schema);
      return tools.find(t => t.name === selection.tool) || null;
    },
    enabled: !!selection && selection.kind === 'tool',
  });

  const queryQuery = useQuery({
    queryKey: ['uc-query', selection?.kind === 'query' ? selection.catalog : null, selection?.kind === 'query' ? selection.schema : null, selection?.kind === 'query' ? selection.query : null],
    queryFn: () => catalogApi.getQuery((selection as any).catalog, (selection as any).schema, (selection as any).query),
    enabled: !!selection && selection.kind === 'query',
  });

  const queryVersionsQuery = useQuery({
    queryKey: ['uc-query-versions', selection?.kind === 'query' ? selection.catalog : null, selection?.kind === 'query' ? selection.schema : null, selection?.kind === 'query' ? selection.query : null],
    queryFn: () => catalogApi.getQueryVersions((selection as any).catalog, (selection as any).schema, (selection as any).query),
    enabled: !!selection && selection.kind === 'query',
  });

  const notebookContentQuery = useQuery({
    queryKey: ['uc-notebook-content', notebookQuery.data?.blob_path],
    queryFn: () => api.get<any>(`/notebook/files/${notebookQuery.data!.blob_path}`).then((r) => r.data),
    enabled: !!notebookQuery.data?.blob_path,
  });

  const lineageQuery = useQuery({
    queryKey: ['uc-lineage', selection?.kind === 'table' ? selection.catalog : null, selection?.kind === 'table' ? selection.schema : null, selection?.kind === 'table' ? selection.table : null],
    queryFn: () => catalogApi.getLineage((selection as { catalog: string }).catalog, (selection as { schema: string }).schema, (selection as { table: string }).table),
    enabled: !!selection && selection.kind === 'table',
  });

  const sampleDataQuery = useQuery<SampleData>({
    queryKey: ['uc-sample', selection?.kind === 'table' ? selection.catalog : null, selection?.kind === 'table' ? selection.schema : null, selection?.kind === 'table' ? selection.table : null],
    queryFn: () => catalogApi.getSampleData((selection as any).catalog, (selection as any).schema, (selection as any).table),
    enabled: !!selection && selection.kind === 'table' && activeTab === 'sample',
  });

  const [bindAll, setBindAll] = useState(false);
  const [selectedWs, setSelectedWs] = useState<Record<string, boolean>>({});

  const { data: bindingData, isLoading: bindingsLoading } = useQuery({
    queryKey: ['uc-catalog-bindings', selection?.kind === 'catalog' ? selection.catalog : null],
    queryFn: () => api.get(`/catalog/catalogs/${encodeURIComponent((selection as { catalog: string }).catalog)}/workspace-bindings`).then(r => r.data),
    enabled: !!selection && selection.kind === 'catalog' && activeTab === 'workspaces',
  });

  const { data: allWorkspaces, isLoading: workspacesLoading } = useQuery({
    queryKey: ['uc-all-workspaces'],
    queryFn: () => api.get((api.defaults.baseURL || '').replace(/\/api\/v1\/?$/, '') + '/api/account/workspaces').then(r => r.data),
    enabled: !!selection && selection.kind === 'catalog' && activeTab === 'workspaces',
  });

  useEffect(() => {
    if (bindingData) {
      setBindAll(bindingData.all_workspaces);
      const initialSelected: Record<string, boolean> = {};
      bindingData.bindings.forEach((b: any) => {
        initialSelected[b.workspace_id] = true;
      });
      setSelectedWs(initialSelected);
    }
  }, [bindingData]);

  const saveBindingsMutation = useMutation({
    mutationFn: (payload: { all_workspaces: boolean; workspace_ids: string[] }) =>
      api.post(`/catalog/catalogs/${encodeURIComponent((selection as { catalog: string }).catalog)}/workspace-bindings`, payload).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uc-catalog-bindings'] });
      queryClient.invalidateQueries({ queryKey: ['uc-catalogs'] });
      alert('Workspace bindings saved successfully!');
    },
    onError: (err: any) => {
      alert('Failed to save bindings: ' + (err.response?.data?.detail || err.message));
    }
  });

  const handleSaveBindings = () => {
    const workspaceIds = Object.keys(selectedWs).filter(id => selectedWs[id]);
    saveBindingsMutation.mutate({
      all_workspaces: bindAll,
      workspace_ids: workspaceIds,
    });
  };

  const renderWorkspaceBindings = () => {
    if (bindingsLoading || workspacesLoading) {
      return (
        <div className="uc-tab-content">
          <div className="uc-empty-inline">
            <Loader2 size={16} className="spin" style={{ marginRight: 8, display: 'inline' }} />
            Loading workspace bindings...
          </div>
        </div>
      );
    }

    const workspacesList = allWorkspaces || [];

    return (
      <div className="uc-tab-content">
        <div className="uc-detail-card" style={{ maxWidth: 640 }}>
          <div className="uc-detail-title">Catalog Workspace Bindings</div>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginBottom: 20 }}>
            Configure which workspaces can view and access the <strong>{selection && 'catalog' in selection ? selection.catalog : ''}</strong> catalog.
          </p>

          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 10 }}>
              <input
                type="radio"
                name="bindMode"
                checked={bindAll}
                onChange={() => setBindAll(true)}
              />
              <span style={{ fontWeight: 500, marginLeft: 8 }}>Bind to all workspaces</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="radio"
                name="bindMode"
                checked={!bindAll}
                onChange={() => setBindAll(false)}
              />
              <span style={{ fontWeight: 500, marginLeft: 8 }}>Bind to selected workspaces</span>
            </label>
          </div>

          {!bindAll && (
            <div style={{
              border: '1px solid var(--color-border)',
              borderRadius: 6,
              maxHeight: 300,
              overflowY: 'auto',
              padding: 12,
              backgroundColor: 'var(--color-bg-light)',
              marginBottom: 20
            }}>
              {workspacesList.length === 0 ? (
                <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>No workspaces found.</div>
              ) : (
                workspacesList.map((ws: any) => (
                  <label
                    key={ws.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '6px 0',
                      cursor: 'pointer',
                      borderBottom: '1px solid var(--color-border-light)',
                      fontSize: '0.875rem'
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={!!selectedWs[ws.id]}
                      onChange={(e) => {
                        setSelectedWs(prev => ({
                          ...prev,
                          [ws.id]: e.target.checked
                        }));
                      }}
                    />
                    <div style={{ marginLeft: 8 }}>
                      <span style={{ fontWeight: 500 }}>{ws.name}</span>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem', marginLeft: 8 }}>({ws.slug})</span>
                    </div>
                  </label>
                ))
              )}
            </div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="btn btn-primary"
              onClick={handleSaveBindings}
              disabled={saveBindingsMutation.isPending}
            >
              {saveBindingsMutation.isPending ? 'Saving...' : 'Save Bindings'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // Keep table cache updated whenever schemaTablesQuery yields data
  useEffect(() => {
    if (schemaTablesQuery.data && activeCatalog && activeSchema) {
      const key = `${activeCatalog}.${activeSchema}`;
      setSchemaTablesCache((prev) => ({
        ...prev,
        [key]: schemaTablesQuery.data
      }));
    }
  }, [schemaTablesQuery.data, activeCatalog, activeSchema]);

  // Keep volumes cache updated
  useEffect(() => {
    if (schemaVolumesQuery.data && activeCatalog && activeSchema) {
      const key = `${activeCatalog}.${activeSchema}`;
      setSchemaVolumesCache((prev) => ({
        ...prev,
        [key]: schemaVolumesQuery.data
      }));
    }
  }, [schemaVolumesQuery.data, activeCatalog, activeSchema]);

  // Keep notebooks cache updated
  useEffect(() => {
    if (schemaNotebooksQuery.data && activeCatalog && activeSchema) {
      const key = `${activeCatalog}.${activeSchema}`;
      setSchemaNotebooksCache((prev) => ({
        ...prev,
        [key]: schemaNotebooksQuery.data
      }));
    }
  }, [schemaNotebooksQuery.data, activeCatalog, activeSchema]);

  // Keep dashboards cache updated
  useEffect(() => {
    if (schemaDashboardsQuery.data && activeCatalog && activeSchema) {
      const key = `${activeCatalog}.${activeSchema}`;
      setSchemaDashboardsCache((prev) => ({
        ...prev,
        [key]: schemaDashboardsQuery.data
      }));
    }
  }, [schemaDashboardsQuery.data, activeCatalog, activeSchema]);

  // Keep queries cache updated
  useEffect(() => {
    if (schemaQueriesQuery.data && activeCatalog && activeSchema) {
      const key = `${activeCatalog}.${activeSchema}`;
      setSchemaQueriesCache((prev) => ({
        ...prev,
        [key]: schemaQueriesQuery.data!
      }));
    }
  }, [schemaQueriesQuery.data, activeCatalog, activeSchema]);

  // Reset tab when selection changes
  useEffect(() => { 
    setActiveTab('overview'); 
    setCurrentVolumePath('');
  }, [selection?.kind,
    selection && 'catalog' in selection ? selection.catalog : '',
    selection && 'schema' in selection ? selection.schema : '',
    selection && 'table' in selection ? (selection as any).table : '',
  ]);

  const loadingSchemasRef = useRef<Record<string, boolean>>({});

  // Load tables for all expanded schemas automatically
  useEffect(() => {
    Object.keys(expandedSchemas).forEach((schemaKey) => {
      if (expandedSchemas[schemaKey]) {
        const parts = schemaKey.split('.');
        if (parts.length === 2) {
          const [catalogName, schemaName] = parts;
          
          if (!schemaTablesCache[schemaKey] && !loadingSchemasRef.current[`${schemaKey}-tables`]) {
            loadingSchemasRef.current[`${schemaKey}-tables`] = true;
            setLoadingSchemaTables(prev => ({ ...prev, [schemaKey]: true }));
            catalogApi.listTables(catalogName, schemaName)
              .then((tbls) => {
                setSchemaTablesCache(prev => ({ ...prev, [schemaKey]: tbls }));
              })
              .catch((err) => console.error("Failed to load tables for schema", schemaKey, err))
              .finally(() => {
                loadingSchemasRef.current[`${schemaKey}-tables`] = false;
                setLoadingSchemaTables(prev => ({ ...prev, [schemaKey]: false }));
              });
          }
          
          if (!schemaVolumesCache[schemaKey] && !loadingSchemasRef.current[`${schemaKey}-volumes`]) {
            loadingSchemasRef.current[`${schemaKey}-volumes`] = true;
            setLoadingSchemaVolumes(prev => ({ ...prev, [schemaKey]: true }));
            catalogApi.listVolumes(catalogName, schemaName)
              .then((vols) => {
                setSchemaVolumesCache(prev => ({ ...prev, [schemaKey]: vols }));
              })
              .catch((err) => console.error("Failed to load volumes for schema", schemaKey, err))
              .finally(() => {
                loadingSchemasRef.current[`${schemaKey}-volumes`] = false;
                setLoadingSchemaVolumes(prev => ({ ...prev, [schemaKey]: false }));
              });
          }

          if (!schemaNotebooksCache[schemaKey] && !loadingSchemasRef.current[`${schemaKey}-notebooks`]) {
            loadingSchemasRef.current[`${schemaKey}-notebooks`] = true;
            setLoadingSchemaNotebooks(prev => ({ ...prev, [schemaKey]: true }));
            catalogApi.listNotebooks(catalogName, schemaName)
              .then((nbs) => {
                setSchemaNotebooksCache(prev => ({ ...prev, [schemaKey]: nbs }));
              })
              .catch((err) => console.error("Failed to load notebooks for schema", schemaKey, err))
              .finally(() => {
                loadingSchemasRef.current[`${schemaKey}-notebooks`] = false;
                setLoadingSchemaNotebooks(prev => ({ ...prev, [schemaKey]: false }));
              });
          }

          if (!schemaDashboardsCache[schemaKey] && !loadingSchemasRef.current[`${schemaKey}-dashboards`]) {
            loadingSchemasRef.current[`${schemaKey}-dashboards`] = true;
            setLoadingSchemaDashboards(prev => ({ ...prev, [schemaKey]: true }));
            catalogApi.listDashboards(catalogName, schemaName)
              .then((dbs) => {
                setSchemaDashboardsCache(prev => ({ ...prev, [schemaKey]: dbs }));
              })
              .catch((err) => console.error("Failed to load dashboards for schema", schemaKey, err))
              .finally(() => {
                loadingSchemasRef.current[`${schemaKey}-dashboards`] = false;
                setLoadingSchemaDashboards(prev => ({ ...prev, [schemaKey]: false }));
              });
          }

          if (!schemaToolsCache[schemaKey] && !loadingSchemasRef.current[`${schemaKey}-tools`]) {
            loadingSchemasRef.current[`${schemaKey}-tools`] = true;
            setLoadingSchemaTools(prev => ({ ...prev, [schemaKey]: true }));
            catalogApi.listTools(catalogName, schemaName)
              .then((toolsList) => {
                setSchemaToolsCache(prev => ({ ...prev, [schemaKey]: toolsList }));
              })
              .catch((err) => console.error("Failed to load tools for schema", schemaKey, err))
              .finally(() => {
                loadingSchemasRef.current[`${schemaKey}-tools`] = false;
                setLoadingSchemaTools(prev => ({ ...prev, [schemaKey]: false }));
              });
          }

          if (!schemaQueriesCache[schemaKey] && !loadingSchemasRef.current[`${schemaKey}-queries`]) {
            loadingSchemasRef.current[`${schemaKey}-queries`] = true;
            setLoadingSchemaQueries(prev => ({ ...prev, [schemaKey]: true }));
            catalogApi.listQueries(catalogName, schemaName)
              .then((qList) => {
                setSchemaQueriesCache(prev => ({ ...prev, [schemaKey]: qList }));
              })
              .catch((err) => console.error("Failed to load queries for schema", schemaKey, err))
              .finally(() => {
                loadingSchemasRef.current[`${schemaKey}-queries`] = false;
                setLoadingSchemaQueries(prev => ({ ...prev, [schemaKey]: false }));
              });
          }
        }
      }
    });
  }, [expandedSchemas, schemaTablesCache, schemaVolumesCache, schemaNotebooksCache, schemaDashboardsCache, schemaToolsCache, schemaQueriesCache]);

  // Keep connection lists refetched whenever catalog modal opens
  useEffect(() => {
    if (showCatalogModal) {
      connectionsQuery.refetch();
    }
  }, [showCatalogModal]);

  const uploadVolumeFileMutation = useMutation({
    mutationFn: (data: { volume_id: string, file: File, sub_path?: string }) => catalogApi.uploadVolumeFile(data.volume_id, data.file, data.sub_path || ""),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files'] });
    },
  });

  const createVolumeDirectoryMutation = useMutation({
    mutationFn: (data: { volume_id: string, dir_name: string, sub_path?: string }) => catalogApi.createVolumeDirectory(data.volume_id, data.dir_name, data.sub_path),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files'] });
    },
  });

  const renameVolumeFileMutation = useMutation({
    mutationFn: (data: { volume_id: string, old_path: string, new_name: string }) => catalogApi.renameVolumeFile(data.volume_id, data.old_path, data.new_name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files'] });
    },
  });

  const deleteVolumeFileMutation = useMutation({
    mutationFn: (data: { volume_id: string, file_path: string }) => catalogApi.deleteVolumeFile(data.volume_id, data.file_path),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files'] });
    },
  });

  const updateNotebookMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; notebook: string; body: { name?: string; comment?: string; owner?: string } }) =>
      catalogApi.updateNotebook(data.catalog, data.schema, data.notebook, data.body),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['uc-notebook'] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-notebooks', updated.catalog_name, updated.schema_name] });
      setEditingNbComment(null);
      setEditingNbOwner(null);
      if (selection?.kind === 'notebook') {
        replaceOpenPanel(selection, { kind: 'notebook', catalog: updated.catalog_name, schema: updated.schema_name, notebook: updated.name, blob_path: updated.blob_path });
      }
    },
  });

  const moveNotebookMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; notebook: string; body: { target_catalog: string; target_schema: string; new_name?: string } }) =>
      catalogApi.moveNotebook(data.catalog, data.schema, data.notebook, data.body),
    onSuccess: (updated, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uc-notebook'] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-notebooks', variables.catalog, variables.schema] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-notebooks', updated.catalog_name, updated.schema_name] });
      setShowMoveNbModal(false);
      if (selection?.kind === 'notebook') {
        replaceOpenPanel({ kind: 'notebook', catalog: variables.catalog, schema: variables.schema, notebook: variables.notebook, blob_path: selection.blob_path }, { kind: 'notebook', catalog: updated.catalog_name, schema: updated.schema_name, notebook: updated.name, blob_path: updated.blob_path });
      }
    },
  });

  const deleteNotebookMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; notebook: string }) =>
      catalogApi.deleteNotebook(data.catalog, data.schema, data.notebook),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uc-schema-notebooks', variables.catalog, variables.schema] });
      if (selection?.kind === 'notebook') {
        closeOpenPanel(`notebook:${variables.catalog}.${variables.schema}.${variables.notebook}`);
        setDetailsPanelSelection({ kind: 'schema', catalog: variables.catalog, schema: variables.schema });
      }
    },
  });

  const updateDashboardMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; dashboard: string; body: { name?: string; comment?: string; owner?: string } }) =>
      catalogApi.updateDashboard(data.catalog, data.schema, data.dashboard, data.body),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['uc-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-dashboards', updated.catalog_name, updated.schema_name] });
      setEditingDbComment(null);
      setEditingDbOwner(null);
      if (selection?.kind === 'dashboard') {
        replaceOpenPanel(selection, { kind: 'dashboard', catalog: updated.catalog_name, schema: updated.schema_name, dashboard: updated.name, dashboard_id: updated.dashboard_id ?? undefined });
      }
    },
  });

  const moveDashboardMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; dashboard: string; body: { target_catalog: string; target_schema: string; new_name?: string } }) =>
      catalogApi.moveDashboard(data.catalog, data.schema, data.dashboard, data.body),
    onSuccess: (updated, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uc-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-dashboards', variables.catalog, variables.schema] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-dashboards', updated.catalog_name, updated.schema_name] });
      setShowMoveDbModal(false);
      if (selection?.kind === 'dashboard') {
        replaceOpenPanel({ kind: 'dashboard', catalog: variables.catalog, schema: variables.schema, dashboard: variables.dashboard, dashboard_id: selection.dashboard_id }, { kind: 'dashboard', catalog: updated.catalog_name, schema: updated.schema_name, dashboard: updated.name, dashboard_id: updated.dashboard_id ?? undefined });
      }
    },
  });

  const deleteDashboardMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; dashboard: string }) =>
      catalogApi.deleteDashboard(data.catalog, data.schema, data.dashboard),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uc-schema-dashboards', variables.catalog, variables.schema] });
      if (selection?.kind === 'dashboard') {
        closeOpenPanel(`dashboard:${variables.catalog}.${variables.schema}.${variables.dashboard}`);
        setDetailsPanelSelection({ kind: 'schema', catalog: variables.catalog, schema: variables.schema });
      }
    },
  });

  const deleteQueryMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; query: string }) =>
      catalogApi.deleteQuery(data.catalog, data.schema, data.query),
    onSuccess: (_, variables) => {
      const schemaKey = `${variables.catalog}.${variables.schema}`;
      setSchemaQueriesCache((prev) => ({
        ...prev,
        [schemaKey]: (prev[schemaKey] || []).filter((q) => q.name !== variables.query),
      }));
      queryClient.invalidateQueries({ queryKey: ['uc-schema-queries', variables.catalog, variables.schema] });
      closeOpenPanel(`query:${variables.catalog}.${variables.schema}.${variables.query}`);
      if (selection?.kind === 'query') {
        setDetailsPanelSelection({ kind: 'schema', catalog: variables.catalog, schema: variables.schema });
      }
    },
  });

  const restoreQueryVersionMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; query: string; version: number }) =>
      catalogApi.restoreQueryVersion(data.catalog, data.schema, data.query, data.version),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uc-query', variables.catalog, variables.schema, variables.query] });
      queryClient.invalidateQueries({ queryKey: ['uc-query-versions', variables.catalog, variables.schema, variables.query] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-queries', variables.catalog, variables.schema] });
    },
  });

  const deleteCatalogMutation = useMutation({
    mutationFn: (name: string) => catalogApi.deleteCatalog(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setShowDeleteCatalogModal(false);
      setDeleteCatalogConfirmText('');
      selectAndNavigate({ kind: 'root' });
    },
  });

  const syncCatalogMutation = useMutation({
    mutationFn: (name: string) => catalogApi.syncCatalog(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      qc.invalidateQueries({ queryKey: ['uc-schema-tables'] });
      setShowMoreActionsDropdown(false);
    },
  });

  const createCatalogMutation = useMutation({
    mutationFn: () => catalogApi.createCatalog({
      name: catalogForm.name,
      description: catalogForm.description || null,
      catalog_type: catalogForm.catalog_type,
      connection_id: catalogForm.catalog_type === 'postgres' ? (catalogForm.connection_id || null) : null,
      database_name: catalogForm.catalog_type === 'postgres' ? catalogForm.database_name : null,
      storage_backend_id: catalogForm.storageBackend
        ? (storageBackends.find(b => b.name === catalogForm.storageBackend)?.id ?? null)
        : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setShowCatalogModal(false);
      setCatalogForm({
        name: '',
        description: '',
        catalog_type: 'iceberg',
        connection_id: '',
        database_name: '',
        storageBackend: '',
      });
      setCatalogFormDbs([]);
      setCatalogBrowseError('');
    }
  });

  const createSchemaMutation = useMutation({
    mutationFn: () => {
      if (selection?.kind !== 'catalog') throw new Error('No catalog selected');
      // If user picked a storage backend, use the Iceberg schema endpoint
      if (schemaForm.storageBackend) {
        return catalogApi.createIcebergSchema(
          selection.catalog,
          schemaForm.name,
          schemaForm.storageBackend,
          schemaForm.description || undefined
        );
      }
      return catalogApi.createSchema(selection.catalog, {
        name: schemaForm.name,
        description: schemaForm.description || null
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setShowSchemaModal(false);
      setSchemaForm({ name: '', description: '', storageBackend: '' });
    }
  });

  const createTableMutation = useMutation({
    mutationFn: () => {
      if (selection?.kind !== 'schema') throw new Error('No schema selected');
      return catalogApi.createTable(selection.catalog, selection.schema, {
        name: tableForm.name,
        description: tableForm.description || null
      });
    },
    onMutate: () => {
      if (selection?.kind !== 'schema') return undefined;
      const context = beginPendingAsset('table', selection.catalog, selection.schema, tableForm.name.trim());
      setShowTableModal(false);
      return context;
    },
    onSuccess: (newTable, _variables, context) => {
      finishPendingAsset('table', context, newTable);
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setTableForm({ name: '', description: '' });
      setTableColumns([]);
    },
    onError: (error, _variables, context) => failPendingAsset(context, error)
  });

  const createIcebergTableMutation = useMutation({
    mutationFn: () => {
      if (selection?.kind !== 'schema') throw new Error('No schema selected');
      if (tableColumns.length === 0) throw new Error('At least one column is required');
      return catalogApi.createIcebergTable({
        catalog: selection.catalog,
        schema_name: selection.schema,
        table_name: tableForm.name,
        description: tableForm.description || null,
        columns: tableColumns,
        properties: {},
      });
    },
    onMutate: () => {
      if (selection?.kind !== 'schema') return undefined;
      const context = beginPendingAsset('table', selection.catalog, selection.schema, tableForm.name.trim());
      setShowTableModal(false);
      return context;
    },
    onSuccess: (newTable, _variables, context) => {
      finishPendingAsset('table', context, newTable);
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setTableForm({ name: '', description: '' });
      setTableColumns([]);
    },
    onError: (error, _variables, context) => failPendingAsset(context, error)
  });

  const createTableFromFileMutation = useMutation({
    mutationFn: (formData: FormData) => {
      const catName = selectedCatalogName || (selection as any)?.catalog || catalogsQuery.data?.[0]?.name || '';
      const catObj = (catalogsQuery.data || []).find(c => c.name === catName) || catalogsQuery.data?.[0];
      const schName = selectedSchemaName || (selection as any)?.schema || catObj?.schemas?.[0]?.name || '';
      if (!catName || !schName) {
        throw new Error('Please select a valid Catalog and Schema.');
      }
      return catalogApi.createTableFromFile(catName, schName, formData);
    },
    onMutate: () => {
      const catName = selectedCatalogName || (selection as any)?.catalog || catalogsQuery.data?.[0]?.name || '';
      const catObj = (catalogsQuery.data || []).find(c => c.name === catName) || catalogsQuery.data?.[0];
      const schName = selectedSchemaName || (selection as any)?.schema || catObj?.schemas?.[0]?.name || '';
      const context = beginPendingAsset('table', catName, schName, tableNameInput.trim());
      setShowTableModal(false);
      return context;
    },
    onSuccess: (newTable, _variables, context) => {
      finishPendingAsset('table', context, newTable);
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setRealUploadedFile(null);
      setPreviewColumns([]);
      setPreviewRows([]);
      setInferredTypes({});
      // Select the newly created table
      if (newTable && newTable.name) {
        const catName = selectedCatalogName || (selection as any)?.catalog || catalogsQuery.data?.[0]?.name || '';
        const catObj = (catalogsQuery.data || []).find(c => c.name === catName) || catalogsQuery.data?.[0];
        const schName = selectedSchemaName || (selection as any)?.schema || catObj?.schemas?.[0]?.name || '';
        selectAndNavigate({
          kind: 'table',
          catalog: catName,
          schema: schName,
          table: newTable.name
        });
      }
    },
    onError: (error, _variables, context) => failPendingAsset(context, error)
  });

  const createStorageBackendMutation = useMutation({
    mutationFn: (body: Record<string, any>) => catalogApi.createStorageBackend(body),
    onSuccess: () => {
      catalogApi.listStorageBackends().then(setStorageBackends).catch(() => {});
      setShowStorageModal(false);
      setStorageForm({ name: '', provider: 'azure', bucket: '', base_path: 'compassx/', account_name: '', container: '', account_key: '', region: 'us-east-1', access_key: '', secret_key: '', endpoint_url: '', is_default: false });
    }
  });

  const createVolumeMutation = useMutation({
    mutationFn: () => {
      if (selection?.kind !== 'schema') throw new Error('No schema selected');
      return catalogApi.createVolume(selection.catalog, selection.schema, {
        name: volumeForm.name,
        description: volumeForm.description || null
      });
    },
    onMutate: () => {
      if (selection?.kind !== 'schema') return undefined;
      const context = beginPendingAsset('volume', selection.catalog, selection.schema, volumeForm.name.trim());
      setShowVolumeModal(false);
      return context;
    },
    onSuccess: (newVolume, _variables, context) => {
      finishPendingAsset('volume', context, newVolume);
      setVolumeForm({ name: '', description: '' });
    },
    onError: (error, _variables, context) => failPendingAsset(context, error)
  });

  const registerNotebookMutation = useMutation({
    mutationFn: () => {
      if (selection?.kind !== 'schema') throw new Error('No schema selected');
      return catalogApi.createNotebook(selection.catalog, selection.schema, {
        name: nbForm.name,
        comment: nbForm.comment || undefined
      });
    },
    onMutate: () => {
      if (selection?.kind !== 'schema') return undefined;
      const context = beginPendingAsset('notebook', selection.catalog, selection.schema, nbForm.name.trim());
      setShowNbModal(false);
      return context;
    },
    onSuccess: (newNb, _variables, context) => {
      finishPendingAsset('notebook', context, newNb);
      setNbForm({ name: '', blob_path: '', owner: 'catalog-admin', comment: '' });
      if (context) syncOpenPanel({ kind: 'notebook', catalog: context.catalog, schema: context.schema, notebook: newNb.name, blob_path: newNb.blob_path });
    },
    onError: (error, _variables, context) => failPendingAsset(context, error)
  });

  const registerDashboardMutation = useMutation({
    mutationFn: () => {
      if (selection?.kind !== 'schema') throw new Error('No schema selected');
      return catalogApi.createDashboard(selection.catalog, selection.schema, {
        name: dbForm.name,
        comment: dbForm.comment || undefined
      });
    },
    onMutate: () => {
      if (selection?.kind !== 'schema') return undefined;
      const context = beginPendingAsset('dashboard', selection.catalog, selection.schema, dbForm.name.trim());
      setShowDashboardModal(false);
      return context;
    },
    onSuccess: (newDb, _variables, context) => {
      finishPendingAsset('dashboard', context, newDb);
      setDbForm({ name: '', comment: '' });
      if (context) syncOpenPanel({ kind: 'dashboard', catalog: context.catalog, schema: context.schema, dashboard: newDb.name, dashboard_id: newDb.dashboard_id ?? undefined });
    },
    onError: (error, _variables, context) => failPendingAsset(context, error)
  });

  const refreshMutation = useMutation({
    mutationFn: () => catalogApi.refreshTable((selection as { catalog: string }).catalog, (selection as { schema: string }).schema, (selection as { table: string }).table),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uc-table'] });
      qc.invalidateQueries({ queryKey: ['uc-schema-tables'] });
    },
  });

  const deleteTableMutation = useMutation({
    mutationFn: (data: { catalog: string; schema: string; table: string }) =>
      catalogApi.deleteTable(data.catalog, data.schema, data.table),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['uc-tables'] });
      qc.invalidateQueries({ queryKey: ['uc-table', vars.catalog, vars.schema, vars.table] });
      qc.invalidateQueries({ queryKey: ['uc-schema-tables'] });
      qc.invalidateQueries({ queryKey: ['uc-catalogs'] });
      qc.invalidateQueries({ queryKey: ['explorer-catalogs'] });
      setTableToDelete(null);
      if (selection?.kind === 'table' && selection.catalog === vars.catalog && selection.schema === vars.schema && selection.table === vars.table) {
        selectAndNavigate({ kind: 'schema', catalog: vars.catalog, schema: vars.schema });
      }
    },
  });

  // Dynamic connection browse handlers (Catalog Creation)
  const handleCatalogConnectionChange = async (connIdVal: string) => {
    setCatalogForm(prev => ({
      ...prev,
      connection_id: connIdVal,
      database_name: ''
    }));
    setCatalogFormDbs([]);
    setCatalogBrowseError('');
    if (!connIdVal) return;

    setLoadingCatalogDbs(true);
    try {
      const dbs = await catalogApi.browseDatabases(connIdVal);
      setCatalogFormDbs(dbs);
    } catch (err: any) {
      console.error("Failed to browse databases for catalog form", err);
      setCatalogBrowseError(err.response?.data?.detail || 'Failed to browse connection databases.');
    } finally {
      setLoadingCatalogDbs(false);
    }
  };

  // Dynamic lists search filtering
  const filteredTreeCatalogs = useMemo(() => {
    const term = searchTerm.toLowerCase().trim();
    const list = catalogsQuery.data || [];
    
    if (!term) return list;

    return list.map(catalog => {
      const catalogMatches = catalog.name.toLowerCase().includes(term);
      const matchedSchemas = catalog.schemas.map(schema => {
        const schemaMatches = schema.name.toLowerCase().includes(term);
        const tables = schemaTablesCache[`${catalog.name}.${schema.name}`] || [];
        const matchedTables = tables.filter(t => t.name.toLowerCase().includes(term));
        
        if (schemaMatches || matchedTables.length > 0) {
          return {
            ...schema,
            matchedTables
          };
        }
        return null;
      }).filter(Boolean);

      if (catalogMatches || matchedSchemas.length > 0) {
        return {
          ...catalog,
          schemas: matchedSchemas as any
        };
      }
      return null;
    }).filter(Boolean) as CatalogSummary[];
  }, [catalogsQuery.data, searchTerm, schemaTablesCache]);

  interface FlatAssetItem {
    id: string;
    name: string;
    namespace?: string;
    type: 'Catalog' | 'Schema' | 'Table' | 'Volume' | 'Notebook';
    catalog: string;
    schema?: string;
    blob_path?: string;
  }

  // Compile list of assets for main explorer view
  const mainPanelAssets = useMemo<FlatAssetItem[]>(() => {
    const term = searchTerm.toLowerCase().trim();
    const catalogs = catalogsQuery.data || [];

    // Search Result Panel
    if (term) {
      const results: FlatAssetItem[] = [];
      catalogs.forEach(catalog => {
        if (catalog.name.toLowerCase().includes(term)) {
          results.push({ id: `c-${catalog.id}`, name: catalog.name, type: 'Catalog', catalog: catalog.name });
        }
        catalog.schemas.forEach(schema => {
          if (schema.name.toLowerCase().includes(term)) {
            results.push({ id: `s-${schema.id}`, name: schema.name, namespace: catalog.name, type: 'Schema', catalog: catalog.name, schema: schema.name });
          }
          const tables = schemaTablesCache[`${catalog.name}.${schema.name}`] || [];
          tables.forEach(table => {
            if (table.name.toLowerCase().includes(term)) {
              results.push({ id: `t-${table.id}`, name: table.name, namespace: `${catalog.name}.${schema.name}`, type: 'Table', catalog: catalog.name, schema: schema.name });
            }
          });
        });
      });
      return results;
    }

    // Root Explorer Selected
    if (!selection || selection.kind === 'root') {
      return catalogs.map((cat): FlatAssetItem => ({
        id: `glob-cat-${cat.id}`,
        name: cat.name,
        type: 'Catalog',
        catalog: cat.name
      }));
    }

    // Catalog Selected
    if (selection.kind === 'catalog') {
      const catalogName = selection.catalog;
      const cat = catalogs.find(c => c.name === catalogName);
      if (!cat) return [];
      
      const schemasList: FlatAssetItem[] = cat.schemas.map(s => ({
        id: `c-s-${s.id}`,
        name: s.name,
        namespace: catalogName,
        type: 'Schema',
        catalog: catalogName,
        schema: s.name
      }));

      const tablesList: FlatAssetItem[] = [];
      cat.schemas.forEach(s => {
        const tables = schemaTablesCache[`${catalogName}.${s.name}`] || [];
        tables.forEach(t => {
          tablesList.push({
            id: `c-t-${t.id}`,
            name: t.name,
            namespace: `${catalogName}.${s.name}`,
            type: 'Table',
            catalog: catalogName,
            schema: s.name
          });
        });
      });

      return [...schemasList, ...tablesList];
    }

    // Schema Selected
    if (selection.kind === 'schema') {
      const catalogName = selection.catalog;
      const schemaName = selection.schema;
      const tables = schemaTablesCache[`${catalogName}.${schemaName}`] || [];
      const volumes = schemaVolumesCache[`${catalogName}.${schemaName}`] || [];
      const notebooks = schemaNotebooksCache[`${catalogName}.${schemaName}`] || [];
      
      return [
        ...tables.map((t): FlatAssetItem => ({
          id: `s-t-${t.id}`,
          name: t.name,
          namespace: `${catalogName}.${schemaName}`,
          type: 'Table',
          catalog: catalogName,
          schema: schemaName
        })),
        ...volumes.map((v): FlatAssetItem => ({
          id: `s-v-${v.id}`,
          name: v.name,
          namespace: `${catalogName}.${schemaName}`,
          type: 'Volume',
          catalog: catalogName,
          schema: schemaName
        })),
        ...notebooks.map((n): FlatAssetItem => ({
          id: `s-n-${n.id}`,
          name: n.name,
          namespace: `${catalogName}.${schemaName}`,
          type: 'Notebook',
          catalog: catalogName,
          schema: schemaName,
          blob_path: n.blob_path
        }))
      ];
    }

    return [];
  }, [selection, catalogsQuery.data, searchTerm, schemaTablesCache, schemaVolumesCache, schemaNotebooksCache]);

  // Helper to get FQN or Unique Key
  const getFqn = (sel: Selection): string => {
    if (!sel) return '';
    if (sel.kind === 'catalog') return sel.catalog;
    if (sel.kind === 'schema') return `${sel.catalog}.${sel.schema}`;
    if (sel.kind === 'table') return `${sel.catalog}.${sel.schema}.${sel.table}`;
    if (sel.kind === 'volume') return `${sel.catalog}.${sel.schema}.${sel.volume}`;
    if (sel.kind === 'notebook') return `${sel.catalog}.${sel.schema}.${sel.notebook}`;
    if (sel.kind === 'dashboard') return `${sel.catalog}.${sel.schema}.${sel.dashboard}`;
    if (sel.kind === 'tool') return `${sel.catalog}.${sel.schema}.${sel.tool}`;
    if (sel.kind === 'query') return `${sel.catalog}.${sel.schema}.${sel.query}`;
    return '';
  };

  const getEntityOwner = (sel: Selection, fallback: string) => {
    const key = getFqn(sel);
    return dynamicOwners[key] ?? fallback;
  };
  const handleSaveOwner = (sel: Selection, value: string) => {
    const key = getFqn(sel);
    setDynamicOwners(prev => ({ ...prev, [key]: value }));
    setEditingOwnerId(null);
  };

  const handleRunNotebook = async () => {
    if (selection?.kind !== 'notebook') return;
    setExecutingNotebook(true);
    try {
      const res = await catalogApi.runNotebook(selection.catalog, selection.schema, selection.notebook);
      setExecutionOutput(res.cells);
      notebookContentQuery.refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to run notebook');
    } finally {
      setExecutingNotebook(false);
    }
  };

  const getEntityReadRoles = (sel: Selection, fallback: string[]) => {
    const key = getFqn(sel);
    return customReadRoles[key] ?? fallback;
  };

  const getEntityWriteRoles = (sel: Selection, fallback: string[]) => {
    const key = getFqn(sel);
    return customWriteRoles[key] ?? fallback;
  };

  const handleAddReadRole = (sel: Selection, role: string) => {
    if (!role.trim()) return;
    const key = getFqn(sel);
    setCustomReadRoles(prev => ({
      ...prev,
      [key]: [...(prev[key] ?? []), role.trim()]
    }));
    setNewReadRole('');
  };

  const handleRemoveReadRole = (sel: Selection, roleToRemove: string) => {
    const key = getFqn(sel);
    setCustomReadRoles(prev => ({
      ...prev,
      [key]: (prev[key] ?? []).filter(r => r !== roleToRemove)
    }));
  };

  const handleAddWriteRole = (sel: Selection, role: string) => {
    if (!role.trim()) return;
    const key = getFqn(sel);
    setCustomWriteRoles(prev => ({
      ...prev,
      [key]: [...(prev[key] ?? []), role.trim()]
    }));
    setNewWriteRole('');
  };

  const handleRemoveWriteRole = (sel: Selection, roleToRemove: string) => {
    const key = getFqn(sel);
    setCustomWriteRoles(prev => ({
      ...prev,
      [key]: (prev[key] ?? []).filter(r => r !== roleToRemove)
    }));
  };

  const renderDetailHeader = (title: string, kind: 'catalog' | 'schema' | 'table' | 'volume' | 'notebook' | 'dashboard' | 'tool' | 'query') => {
    const fqn = getFqn(selection);
    const isFav = !!favorites[fqn];

    let isIcebergCatalog = false;
    if (selection && selection.kind !== 'root') {
      const cat = catalogsQuery.data?.find(c => c.name === selection.catalog);
      if (cat?.catalog_type === 'iceberg') {
        isIcebergCatalog = true;
      }
    }
    return (
      <div >
        {/* Breadcrumbs */}
        <div className="asset-detail-breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
          <button 
            type="button" 
            onClick={() => selectAndNavigate({ kind: 'root' })}
            className="asset-breadcrumb-link"
          >
            Catalog Explorer
          </button>
          {selection && selection.kind !== 'root' && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <button 
                type="button" 
                onClick={() => selectAndNavigate({ kind: 'catalog', catalog: selection.catalog })}
                className={cx('asset-breadcrumb-link', selection.kind === 'catalog' && 'asset-breadcrumb-current')}
                disabled={selection.kind === 'catalog'}
              >
                {selection.catalog}
              </button>
            </>
          )}
          {selection && (selection.kind === 'schema' || selection.kind === 'table' || selection.kind === 'volume' || selection.kind === 'notebook' || selection.kind === 'dashboard' || selection.kind === 'tool' || selection.kind === 'query') && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <button 
                type="button" 
                onClick={() => selectAndNavigate({ kind: 'schema', catalog: selection.catalog, schema: selection.schema })}
                className={cx('asset-breadcrumb-link', selection.kind === 'schema' && 'asset-breadcrumb-current')}
                disabled={selection.kind === 'schema'}
              >
                {selection.schema}
              </button>
            </>
          )}
          {selection && selection.kind === 'table' && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <span className="asset-breadcrumb-current">{selection.table}</span>
            </>
          )}
          {selection && selection.kind === 'volume' && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <span className="asset-breadcrumb-current">{selection.volume}</span>
            </>
          )}
          {selection && selection.kind === 'notebook' && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <span className="asset-breadcrumb-current">{selection.notebook}</span>
            </>
          )}
          {selection && selection.kind === 'dashboard' && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <span className="asset-breadcrumb-current">{selection.dashboard}</span>
            </>
          )}
          {selection && selection.kind === 'tool' && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <span className="asset-breadcrumb-current">{selection.tool}</span>
            </>
          )}
          {selection && selection.kind === 'query' && (
            <>
              <span style={{ color: 'var(--color-text-subtle)' }}>&gt;</span>
              <span className="asset-breadcrumb-current">{selection.query}</span>
            </>
          )}
        </div>

        {/* Title row with icon and interactive buttons */}
        <div className="uc-panel-header-row">
          <div className="uc-panel-header-title">
            {kind === 'catalog' && <Database size={22} className="text-primary" />}
            {kind === 'schema' && <Folder size={22} className="text-primary" />}
            {kind === 'table' && <Table2 size={22} className="text-primary" />}
            {kind === 'volume' && <Folder size={22} className="text-primary" />}
            {kind === 'notebook' && <FileCode size={22} className="text-primary" />}
            {kind === 'dashboard' && <SlidersHorizontal size={22} className="text-primary" />}
            {kind === 'tool' && <Wrench size={22} className="text-primary" style={{ color: '#2563eb' }} />}
            {kind === 'query' && <FileCode size={22} className="text-primary" />}
            <h2>{title}</h2>
            
            {/* Copy button */}
            <button 
              type="button"
              className="uc-icon-btn"
              onClick={() => {
                navigator.clipboard.writeText(fqn);
                setCopiedFqn(fqn);
                setTimeout(() => setCopiedFqn(null), 2000);
              }}
              title="Copy FQN"
            >
              {copiedFqn === fqn ? <Check size={14} style={{ color: 'var(--color-success)' }} /> : <Copy size={14} />}
            </button>

            {/* Favorite button */}
            <button 
              type="button"
              className="uc-icon-btn"
              onClick={() => setFavorites(prev => ({ ...prev, [fqn]: !prev[fqn] }))}
              title="Favorite"
            >
              <Star size={14} fill={isFav ? '#eab308' : 'none'} stroke={isFav ? '#eab308' : 'currentColor'} />
            </button>
          </div>

          {/* Action buttons (Create / Delete) */}
          <div className="uc-hero-actions" style={{ position: 'relative' }}>
            {/* Delete button for Iceberg tables */}
            {kind === 'table' && tableQuery.data?.table_type === 'iceberg' && (
              <button
                type="button"
                className="btn-outline flex items-center gap-1"
                style={{ color: 'var(--color-danger)', borderColor: 'var(--color-danger)', fontSize: '13px' }}
                onClick={() => {
                  if (selection && selection.kind === 'table') {
                    setTableToDelete({ catalog: selection.catalog, schema: selection.schema, table: selection.table });
                  }
                }}
                disabled={deleteTableMutation.isPending}
              >
                <Trash size={13} /> Delete table
              </button>
            )}

            {/* Ellipsis menu button — only shows actions at catalog level */}
            {kind === 'catalog' && (
              <button
                ref={moreActionsBtnRef}
                type="button"
                className="uc-icon-btn"
                title="More actions"
                onClick={() => { setShowMoreActionsDropdown(v => !v); setShowCreateDropdown(false); }}
              >
                <MoreVertical size={16} />
              </button>
            )}

            {/* Create Dropdown */}
            {kind === 'volume' ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => document.getElementById('volume-file-upload')?.click()}
                  disabled={uploadVolumeFileMutation.isPending}
                >
                  {uploadVolumeFileMutation.isPending ? <Loader2 size={14} className="spin" /> : 'Upload to this volume'}
                </button>
              </div>
            ) : (
              <div className="uc-action-menu-container">
                <button 
                  ref={createBtnRef}
                  type="button"
                  className="btn-primary flex items-center gap-1"
                  onClick={() => setShowCreateDropdown(!showCreateDropdown)}
                >
                  Create <ChevronDown size={14} />
                </button>
                {showCreateDropdown && (
                  <div 
                    ref={createDropdownRef}
                    className="uc-action-dropdown-menu" 
                    style={{ right: 0 }}
                  >
                    {kind === 'catalog' && isIcebergCatalog && (
                      <button 
                        type="button"
                        onClick={() => {
                          setShowCreateDropdown(false);
                          setShowSchemaModal(true);
                        }}
                      >
                        <strong>Create schema</strong>
                        <span>Add a new schema to this catalog</span>
                      </button>
                    )}

                    {kind === 'schema' && (
                      <>
                        <button 
                          type="button"
                          onClick={() => {
                            setShowCreateDropdown(false);
                            setShowTableModal(true);
                          }}
                        >
                          <strong>Create table</strong>
                          <span>Create a new table in this schema</span>
                        </button>
                        <button 
                          type="button"
                          onClick={() => {
                            setShowCreateDropdown(false);
                            setShowVolumeModal(true);
                          }}
                        >
                          <strong>Create volume</strong>
                          <span>Create a new volume in this schema</span>
                        </button>
                        <button 
                          type="button"
                          onClick={() => {
                            setShowCreateDropdown(false);
                            const schemaKey = selection?.kind === 'schema' ? `${selection.catalog}.${selection.schema}` : '';
                            const existing = (schemaKey && schemaNotebooksCache[schemaKey]) || [];
                            let idx = 1;
                            while (existing.some(n => n.name.toLowerCase() === `untitled_notebook_${idx}` || n.name.toLowerCase() === `untitled_notebook_${idx}.ipynb`)) {
                              idx++;
                            }
                            setNbForm({ name: `untitled_notebook_${idx}`, blob_path: '', owner: 'catalog-admin', comment: '' });
                            setShowNbModal(true);
                          }}
                        >
                          <strong>Create notebook</strong>
                          <span>Register a new governed notebook in this schema</span>
                        </button>
                        <button 
                          type="button"
                          onClick={() => {
                            setShowCreateDropdown(false);
                            const schemaKey = selection?.kind === 'schema' ? `${selection.catalog}.${selection.schema}` : '';
                            const existing = (schemaKey && schemaDashboardsCache[schemaKey]) || [];
                            let idx = 1;
                            while (existing.some(d => d.name.toLowerCase() === `untitled_dashboard_${idx}`)) {
                              idx++;
                            }
                            setDbForm({ name: `untitled_dashboard_${idx}`, comment: '' });
                            setShowDashboardModal(true);
                          }}
                        >
                          <strong>Create dashboard</strong>
                          <span>Create a new governed dashboard in this schema</span>
                        </button>
                      </>
                    )}

                    <button 
                      type="button"
                      onClick={() => {
                        setShowCreateDropdown(false);
                        setShowCatalogModal(true);
                      }}
                    >
                      <strong>Create new catalog</strong>
                      <span>Define iceberg/postgres connections</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderMetadataSidebar = (
    defaultOwner: string, 
    kindLabel: string
  ) => {
    const fqn = getFqn(selection);
    const currentOwner = getEntityOwner(selection, defaultOwner);

    return (
      <div className="uc-metadata-sidebar-section">
        {/* Block 1: About */}
        <div className="uc-sidebar-block">
          <h4>About this {kindLabel}</h4>
          <div className="uc-sidebar-owner-row">
            <span>Owner</span>
            {editingOwnerId === fqn ? (
              <form 
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSaveOwner(selection, newOwnerValue);
                }}
                style={{ flex: 1, display: 'flex', gap: '4px' }}
              >
                <input 
                  type="text" 
                  className="uc-sidebar-owner-input"
                  value={newOwnerValue}
                  onChange={(e) => setNewOwnerValue(e.target.value)}
                  autoFocus
                />
                <button type="submit" className="btn-primary" style={{ padding: '2px 6px', minHeight: 'unset', fontSize: '11px' }}>Save</button>
              </form>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <strong style={{ color: 'var(--color-text)' }}>{currentOwner}</strong>
                <button 
                  type="button" 
                  className="uc-icon-btn" 
                  style={{ padding: '2px' }}
                  onClick={() => {
                    setEditingOwnerId(fqn);
                    setNewOwnerValue(currentOwner);
                  }}
                >
                  <Pencil size={11} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };



  const renderSchemaOverviewTab = (tables: CatalogTable[]) => {
    const schemaKey = selection && selection.kind === 'schema' ? `${selection.catalog}.${selection.schema}` : '';
    const volumes = schemaVolumesCache[schemaKey] || [];
    const notebooks = schemaNotebooksCache[schemaKey] || [];
    const dashboards = schemaDashboardsCache[schemaKey] || [];
    const tools = schemaToolsCache[schemaKey] || [];
    const queries = schemaQueriesCache[schemaKey] || [];

    let itemsToRender: any[] = [];
    if (schemaSubTab === 'tables') {
      itemsToRender = tables;
    } else if (schemaSubTab === 'volumes') {
      itemsToRender = volumes;
    } else if (schemaSubTab === 'notebooks') {
      itemsToRender = notebooks;
    } else if (schemaSubTab === 'dashboards') {
      itemsToRender = dashboards;
    } else if (schemaSubTab === 'tools') {
      itemsToRender = tools;
    } else if (schemaSubTab === 'queries') {
      itemsToRender = queries;
    }

    const filtered = itemsToRender.filter(item => 
      item.name.toLowerCase().includes(schemaTableFilter.toLowerCase())
    );

    const sorted = [...filtered].sort((a, b) => {
      if (schemaTableSort === 'name') {
        return a.name.localeCompare(b.name);
      }
      const dateA = new Date(a.created_at || a.updated_at || 0).getTime();
      const dateB = new Date(b.created_at || b.updated_at || 0).getTime();
      return dateB - dateA;
    });

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Toolbar: Filter + tabs + Sort */}
        <div className="uc-subtab-toolbar">
          <div className="uc-subtab-left">
            <div className="uc-search-wrapper">
              <Search size={14} className="uc-search-icon" />
              <input 
                type="text" 
                placeholder={`Filter ${schemaSubTab}`}
                value={schemaTableFilter}
                onChange={(e) => setSchemaTableFilter(e.target.value)}
              />
            </div>
            
            <button 
              type="button" 
              className={cx("uc-subtab-btn", schemaSubTab === 'tables' && "is-active")}
              onClick={() => { setSchemaSubTab('tables'); setSchemaTableFilter(''); }}
            >
              Tables {tables.length}
            </button>
            <button 
              type="button" 
              className={cx("uc-subtab-btn", schemaSubTab === 'volumes' && "is-active")}
              onClick={() => { setSchemaSubTab('volumes'); setSchemaTableFilter(''); }}
            >
              Volumes {volumes.length}
            </button>
            <button 
              type="button" 
              className={cx("uc-subtab-btn", schemaSubTab === 'notebooks' && "is-active")}
              onClick={() => { setSchemaSubTab('notebooks'); setSchemaTableFilter(''); }}
            >
              Notebooks {notebooks.length}
            </button>
            <button 
              type="button" 
              className={cx("uc-subtab-btn", schemaSubTab === 'dashboards' && "is-active")}
              onClick={() => { setSchemaSubTab('dashboards'); setSchemaTableFilter(''); }}
            >
              Dashboards {dashboards.length}
            </button>
            <button 
              type="button" 
              className={cx("uc-subtab-btn", schemaSubTab === 'tools' && "is-active")}
              onClick={() => { setSchemaSubTab('tools'); setSchemaTableFilter(''); }}
            >
              Tools {tools.length}
            </button>
            <button 
              type="button" 
              className={cx("uc-subtab-btn", schemaSubTab === 'queries' && "is-active")}
              onClick={() => { setSchemaSubTab('queries'); setSchemaTableFilter(''); }}
            >
              Queries {queries.length}
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>Sort</span>
            <select 
              className="uc-sort-select"
              value={schemaTableSort}
              onChange={(e) => setSchemaTableSort(e.target.value as any)}
            >
              <option value="name">Name</option>
              <option value="created_at">Created at</option>
            </select>
          </div>
        </div>

        {/* Assets list */}
        <div className="uc-assets-table-wrap">
          <table className="uc-assets-table">
            <thead>
              {schemaSubTab === 'tables' && (
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Owner</th>
                  <th>Created at</th>
                  <th>Popularity</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              )}
              {schemaSubTab === 'volumes' && (
                <tr>
                  <th>Name</th>
                  <th>Storage Location</th>
                  <th>Created by</th>
                  <th>Created at</th>
                </tr>
              )}
              {schemaSubTab === 'notebooks' && (
                <tr>
                  <th>Name</th>
                  <th>Owner</th>
                  <th>Storage Location</th>
                  <th>Last Modified</th>
                </tr>
              )}
              {schemaSubTab === 'dashboards' && (
                <tr>
                  <th>Name</th>
                  <th>Owner</th>
                  <th>Dashboard ID</th>
                  <th>Last Modified</th>
                </tr>
              )}
              {schemaSubTab === 'tools' && (
                <tr>
                  <th>Tool Name</th>
                  <th>Version</th>
                  <th>Connections</th>
                  <th>Owner</th>
                  <th>Last Modified</th>
                </tr>
              )}
              {schemaSubTab === 'queries' && (
                <tr>
                  <th>Query Name</th>
                  <th>Owner</th>
                  <th>Description</th>
                  <th>Created at</th>
                  <th>Actions</th>
                </tr>
              )}
            </thead>
            <tbody>
              {schemaSubTab === 'tables' && sorted.map(t => {
                const isIceberg = t.table_type === 'iceberg';
                return (
                  <tr 
                    key={t.id} 
                    onClick={() => selectAndNavigate({ kind: 'table', catalog: t.catalog, schema: t.schema_name, table: t.name })}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div className="uc-item-meta-row" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Table2 size={15} className="text-muted" style={{ flexShrink: 0 }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-primary)' }}>{t.name}</span>
                      </div>
                    </td>
                    <td>
                      <span className="uc-chip" style={{ fontSize: 11 }}>
                        {isIceberg ? 'Iceberg' : 'Postgres Native'}
                      </span>
                    </td>
                    <td>{getEntityOwner({ kind: 'table', catalog: t.catalog, schema: t.schema_name, table: t.name } as Selection, 'catalog-admin')}</td>
                    <td>{new Date(t.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="uc-popularity-bars">
                        <span className="uc-popularity-bar is-active" style={{ height: '4px' }} />
                        <span className="uc-popularity-bar is-active" style={{ height: '8px' }} />
                        <span className="uc-popularity-bar is-active" style={{ height: '12px' }} />
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                      {isIceberg ? (
                        <button
                          type="button"
                          className="uc-icon-btn"
                          style={{ color: 'var(--color-danger)' }}
                          title="Delete Iceberg table"
                          onClick={() => setTableToDelete({ catalog: t.catalog, schema: t.schema_name, table: t.name })}
                        >
                          <Trash size={13} />
                        </button>
                      ) : (
                        <span style={{ color: 'var(--color-text-subtle)', fontSize: 11 }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}

              {schemaSubTab === 'volumes' && sorted.map(vol => {
                return (
                  <tr 
                    key={vol.id} 
                    onClick={() => selectAndNavigate({ kind: 'volume', catalog: vol.catalog, schema: vol.schema_name, volume: vol.name })}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div className="uc-item-meta-row" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Folder size={15} className="text-muted" style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-primary)' }}>{vol.name}</span>
                      </div>
                    </td>
                    <td style={{ fontSize: '11px', fontFamily: 'monospace' }}>{vol.storage_location}</td>
                    <td>{vol.owner}</td>
                    <td>{new Date(vol.created_at).toLocaleDateString()}</td>
                  </tr>
                );
              })}

              {schemaSubTab === 'notebooks' && sorted.map(nb => {
                return (
                  <tr 
                    key={nb.id} 
                    onClick={() => selectAndNavigate({ kind: 'notebook', catalog: (selection as any)?.catalog || '', schema: (selection as any)?.schema || '', notebook: nb.name, blob_path: nb.blob_path })}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div className="uc-item-meta-row" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileCode size={15} className="text-muted" style={{ flexShrink: 0 }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-primary)' }}>{nb.name}</span>
                      </div>
                    </td>
                    <td>{nb.owner || 'catalog-admin'}</td>
                    <td style={{ fontSize: '11px', fontFamily: 'monospace' }}>{nb.blob_path}</td>
                    <td>{new Date(nb.updated_at || nb.created_at).toLocaleDateString()}</td>
                  </tr>
                );
              })}

              {schemaSubTab === 'dashboards' && sorted.map(dbItem => {
                return (
                  <tr 
                    key={dbItem.id} 
                    onClick={() => selectAndNavigate({ kind: 'dashboard', catalog: (selection as any)?.catalog || '', schema: (selection as any)?.schema || '', dashboard: dbItem.name, dashboard_id: dbItem.dashboard_id ?? undefined })}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div className="uc-item-meta-row" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <SlidersHorizontal size={15} className="text-muted" style={{ flexShrink: 0 }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-primary)' }}>{dbItem.name}</span>
                      </div>
                    </td>
                    <td>{dbItem.owner || 'catalog-admin'}</td>
                    <td style={{ fontSize: '11px', fontFamily: 'monospace' }}>{dbItem.dashboard_id || 'Not initialized'}</td>
                    <td>{new Date(dbItem.updated_at || dbItem.created_at).toLocaleDateString()}</td>
                  </tr>
                );
              })}

              {schemaSubTab === 'tools' && sorted.map(tItem => {
                return (
                  <tr 
                    key={tItem.id} 
                    onClick={() => selectAndNavigate({ kind: 'tool', catalog: (selection as any)?.catalog || '', schema: (selection as any)?.schema || '', tool: tItem.name, tool_id: tItem.id })}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div className="uc-item-meta-row" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Wrench size={15} className="text-muted" style={{ color: '#2563eb', flexShrink: 0 }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-primary)' }}>{tItem.name}</span>
                      </div>
                    </td>
                    <td>
                      <span className="uc-chip" style={{ fontSize: 11, background: '#eff6ff', color: '#1d4ed8' }}>
                        v{tItem.current_version}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {(tItem.connection_dependencies || []).map((conn: string) => (
                          <span key={conn} style={{ fontSize: 11, padding: '1px 6px', borderRadius: 4, background: '#f1f5f9', color: '#475569' }}>
                            {conn}
                          </span>
                        ))}
                        {(tItem.connection_dependencies || []).length === 0 && (
                          <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>None</span>
                        )}
                      </div>
                    </td>
                    <td>{tItem.owner || 'default_user'}</td>
                    <td>{new Date(tItem.updated_at || tItem.created_at).toLocaleDateString()}</td>
                  </tr>
                );
              })}

              {schemaSubTab === 'queries' && sorted.map((qItem: CatalogQuery) => {
                return (
                  <tr 
                    key={qItem.id} 
                    onClick={() => selectAndNavigate({ kind: 'query', catalog: qItem.catalog_name, schema: qItem.schema_name, query: qItem.name })}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div className="uc-item-meta-row" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileCode size={15} className="text-muted" style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-primary)' }}>{qItem.name}</span>
                      </div>
                    </td>
                    <td>{qItem.owner || '—'}</td>
                    <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {qItem.description || '—'}
                    </td>
                    <td>{new Date(qItem.created_at).toLocaleDateString()}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          className="btn-primary flex items-center gap-1"
                          style={{ fontSize: 11, padding: '2px 8px' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            selectAndNavigate({ kind: 'query', catalog: qItem.catalog_name, schema: qItem.schema_name, query: qItem.name });
                          }}
                        >
                          <Play size={10} fill="currentColor" /> Open in Editor
                        </button>
                        <button
                          className="btn-outline flex items-center gap-1"
                          style={{ fontSize: 11, padding: '2px 8px' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/sql-warehouse?catalog=${encodeURIComponent(qItem.catalog_name)}&schema=${encodeURIComponent(qItem.schema_name)}&query_name=${encodeURIComponent(qItem.name)}&sql=${encodeURIComponent(qItem.sql_text)}`);
                          }}
                        >
                          <Database size={10} /> Warehouse
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}

              {sorted.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '24px', color: 'var(--color-text-muted)' }}>
                    No {schemaSubTab} match your filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // ── Shared tab bar ──────────────────────────────────────────────────────────
  const renderTabs = (tabs: { id: string; label: string }[]) => (
    <div className="uc-tab-bar">
      {tabs.map((t) => (
        <button
          key={t.id}
          className={cx('uc-tab', activeTab === t.id && 'is-active')}
          onClick={() => setActiveTab(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );

  // ── Assets grid (shared by catalog-overview + schema-overview) ─────────────
  const renderAssetsGrid = () => (
    <div className="uc-assets-table-wrap">
      <table className="uc-assets-table">
        <thead>
          <tr><th>Name</th><th>Type</th></tr>
        </thead>
        <tbody>
          {mainPanelAssets.map((asset) => {
            let icon = <Database size={16} />;
            if (asset.type === 'Schema') icon = <Folder size={16} />;
            if (asset.type === 'Table') icon = <Table2 size={16} />;
            if (asset.type === 'Volume') icon = <Folder size={16} style={{ color: 'var(--color-primary)' }} />;
            if (asset.type === 'Notebook') icon = <FileCode size={16} />;
            return (
              <tr key={asset.id} onClick={() => {
                if (asset.type === 'Catalog') {
                  setExpandedCatalogs(prev => ({ ...prev, [asset.name]: true }));
                  selectAndNavigate({ kind: 'catalog', catalog: asset.name });
                } else if (asset.type === 'Schema') {
                  setExpandedSchemas(prev => ({ ...prev, [`${asset.catalog}.${asset.name}`]: true }));
                  selectAndNavigate({ kind: 'schema', catalog: asset.catalog, schema: asset.name });
                } else if (asset.type === 'Table') {
                  selectAndNavigate({ kind: 'table', catalog: asset.catalog, schema: asset.schema || '', table: asset.name });
                } else if (asset.type === 'Volume') {
                  selectAndNavigate({ kind: 'volume', catalog: asset.catalog, schema: asset.schema || '', volume: asset.name });
                } else if (asset.type === 'Notebook') {
                  selectAndNavigate({ kind: 'notebook', catalog: asset.catalog, schema: asset.schema || '', notebook: asset.name, blob_path: asset.blob_path });
                }
              }}>
                <td>
                  <div className="uc-item-meta-cell">
                    <div className="uc-item-icon-container">{icon}</div>
                    <div className="uc-item-details">
                      <span className="uc-item-name">{asset.name}</span>
                      {asset.namespace && <span className="uc-item-namespace">{asset.namespace}</span>}
                    </div>
                  </div>
                </td>
                <td><span className="uc-item-type">{asset.type}</span></td>
              </tr>
            );
          })}
          {mainPanelAssets.length === 0 && (
            <tr>
              <td colSpan={2} style={{ textAlign: 'center', padding: '24px', color: 'var(--color-text-muted)' }}>
                No assets registered under this level.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );

  const renderMainContent = () => {
    // ── Empty state ────────────────────────────────────────────────────────────
    const catalogs = catalogsQuery.data || [];
    if (catalogs.length === 0 && !catalogsQuery.isLoading && !selection) {
      return (
        <div className="uc-empty-state">
          <div className="uc-empty-badge">Unity Catalog-inspired</div>
          <h2>Register your first governed data asset.</h2>
          <p>Start by creating a Catalog or registering a Postgres or Iceberg table namespace directly into CompassX.</p>
          <div className="uc-empty-actions">
            <button className="btn-primary flex items-center gap-1" onClick={() => setShowCatalogModal(true)}>
              <Plus size={15} /> Create Catalog
            </button>
          </div>
        </div>
      );
    }

    //  VOLUME level 
    if (selection && selection.kind === 'volume') {
      const vol = activeVolume;
      if (!vol) return <div className="uc-empty-state"><Loader2 className="spin" size={24} /><p>Loading volume...</p></div>;

      const files = volumeFilesQuery.data || [];
      const isLoadingFiles = volumeFilesQuery.isLoading;

      const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
      };

      type VolumeFileInfo = {
        file_path: string;
        file_name: string;
        size_bytes: number;
        content_type: string;
        last_modified: string;
      };

      const fileColumns = [
        {
          key: 'name',
          header: 'Name',
          render: (row: VolumeFileInfo) => {
            const isDir = row.file_path.endsWith('/') || row.content_type === 'application/x-directory';
            return (
              <div 
                className={`font-medium flex items-center gap-2 ${isDir ? 'cursor-pointer text-blue-600 hover:underline' : ''}`}
                onClick={() => {
                  if (isDir) {
                    setCurrentVolumePath(row.file_path);
                    setFileSearchQuery('');
                  }
                }}
              >
                {isDir ? <Folder size={16} className="text-blue-500" style={{ minWidth: 16 }} /> : <FileText size={16} className="text-subtle" style={{ minWidth: 16 }} />}
                <span>{isDir ? row.file_name.replace(/\/$/, '') : row.file_name}</span>
              </div>
            );
          }
        },
        {
          key: 'size',
          header: 'Size',
          render: (row: VolumeFileInfo) => formatBytes(row.size_bytes)
        },
        {
          key: 'last_modified',
          header: 'Last modified',
          render: (row: VolumeFileInfo) => new Date(row.last_modified).toLocaleString()
        }
      ];

      const fileRowActions = [
        {
          label: 'Rename',
          icon: Pencil,
          onClick: (row: VolumeFileInfo) => {
            const isDir = row.file_path.endsWith('/') || row.content_type === 'application/x-directory';
            const cleanName = isDir ? row.file_name.replace(/\/$/, '') : row.file_name;
            const newName = prompt(`Enter new name for ${cleanName}:`, cleanName);
            if (newName && newName !== cleanName) {
              renameVolumeFileMutation.mutate({ volume_id: vol.id, old_path: row.file_path, new_name: newName });
            }
          }
        },
        {
          label: 'Delete file',
          icon: X,
          variant: 'danger' as const,
          onClick: (row: VolumeFileInfo) => {
            if (confirm(`Delete ${row.file_name}?`)) {
              deleteVolumeFileMutation.mutate({ volume_id: vol.id, file_path: row.file_path });
            }
          }
        }
      ];

      const volumeTabs = [
        { value: 'overview', label: 'Overview' },
        { value: 'files', label: 'Files' },
        { value: 'details', label: 'Details' },
        { value: 'permissions', label: 'Permissions' },
      ] as const;

      return (
        <div className="uc-panel">
          {renderDetailHeader(vol.name, 'volume')}

          <PageTabs tabs={volumeTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content">
              {/* Main Card Container */}
              <div className="uc-detail-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2 font-mono text-sm bg-gray-50 p-2 rounded border flex-wrap" style={{ color: 'var(--color-text-muted)', backgroundColor: 'var(--color-bg-subtle)' }}>
                    {currentVolumePath && (
                      <button 
                        className="uc-icon-btn mr-1"
                        onClick={() => {
                          const parts = currentVolumePath.split('/').filter(Boolean);
                          parts.pop();
                          setCurrentVolumePath(parts.length ? parts.join('/') + '/' : '');
                          setFileSearchQuery('');
                        }}
                        title="Go up one level"
                      >
                        <ChevronLeft size={16} />
                      </button>
                    )}
                    
                    <div className="flex items-center gap-1 flex-wrap break-all">
                      <span 
                        className={`cursor-pointer hover:underline font-medium ${!currentVolumePath ? 'text-gray-900 no-underline' : 'text-blue-600'}`}
                        onClick={() => {
                          setCurrentVolumePath('');
                          setFileSearchQuery('');
                        }}
                      >
                        {vol.name}
                      </span>
                      {currentVolumePath.split('/').filter(Boolean).map((part, idx, arr) => {
                        const pathToHere = arr.slice(0, idx + 1).join('/') + '/';
                        const isLast = idx === arr.length - 1;
                        return (
                          <span key={pathToHere} className="flex items-center gap-1">
                            <span className="text-subtle mx-1">/</span>
                            <span 
                              className={`cursor-pointer hover:underline font-medium ${isLast ? 'text-gray-900 no-underline' : 'text-blue-600'}`}
                              onClick={() => {
                                if (!isLast) {
                                  setCurrentVolumePath(pathToHere);
                                  setFileSearchQuery('');
                                }
                              }}
                            >
                              {part}
                            </span>
                          </span>
                        );
                      })}
                    </div>

                    <button 
                      className="uc-icon-btn ml-2" 
                      onClick={() => {
                        const fullPath = `/${vol.name}${currentVolumePath ? '/' + currentVolumePath.replace(/\/$/, '') : ''}`;
                        navigator.clipboard.writeText(fullPath);
                      }}
                      title="Copy Volume Path"
                    >
                      <Copy size={12} />
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="btn-secondary flex items-center gap-1" onClick={() => volumeFilesQuery.refetch()}>
                      <RefreshCw size={14} /> Refresh
                    </button>
                    <button 
                      className="btn-secondary"
                      onClick={() => {
                        const dir = prompt("Enter directory name:");
                        if (dir && vol.id) {
                          createVolumeDirectoryMutation.mutate({ volume_id: vol.id, dir_name: dir, sub_path: currentVolumePath });
                        }
                      }}
                      disabled={createVolumeDirectoryMutation.isPending}
                    >
                      {createVolumeDirectoryMutation.isPending ? <Loader2 size={14} className="spin" /> : 'Create directory'}
                    </button>
                  </div>
                </div>

                {/* Filter Search Input */}
                <div style={{ position: 'relative' }}>
                  <Search size={16} className="text-subtle" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input 
                    type="text" 
                    placeholder="Filter files and directories at this level" 
                    className="uc-search-input w-full"
                    style={{ paddingLeft: '36px' }}
                    value={fileSearchQuery}
                    onChange={(e) => setFileSearchQuery(e.target.value)}
                  />
                </div>

                {/* Table containing the files */}
                <div style={{ marginTop: '12px' }}>
                  <Table
                    columns={fileColumns}
                    rows={filteredFiles}
                    keyExtractor={(row) => row.file_path}
                    rowActions={fileRowActions}
                    emptyState={
                      <div className="flex flex-col items-center gap-2 py-4">
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <span style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#cbd5e1', display: 'inline-block' }}></span>
                          <span style={{ width: '40px', height: '12px', borderRadius: '4px', backgroundColor: '#e2e8f0', display: 'inline-block' }}></span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <span style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#cbd5e1', display: 'inline-block' }}></span>
                          <span style={{ width: '60px', height: '12px', borderRadius: '4px', backgroundColor: '#e2e8f0', display: 'inline-block' }}></span>
                        </div>
                        <p style={{ margin: '8px 0 0 0', color: 'var(--color-text-subtle)' }}>No content in volume</p>
                      </div>
                    }
                    loading={isLoadingFiles}
                    actionsColumnWidth={50}
                  />
                </div>
              </div>

              {/* About this volume */}
              <div className="mt-6 border-t pt-4">
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '8px' }}>About this volume</h4>
                <div className="flex items-center gap-2 text-sm text-subtle">
                  <span>Owner:</span>
                  <strong>{vol.owner}</strong>
                  <button className="uc-icon-btn" onClick={() => {
                    const newOwner = prompt("Change owner:", vol.owner);
                    if (newOwner) {
                      alert("Owner change is local only in this prototype.");
                    }
                  }}>
                    <Pencil size={12} />
                  </button>
                </div>
              </div>

              {/* Tags Section */}
              <div className="mt-6 border-t pt-4">
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '8px' }}>Tags</h4>
                <p className="text-sm text-subtle">No tags applied</p>
              </div>
            </div>
          )}

          {activeTab === 'files' && (
            <div className="uc-tab-content">
              {/* Main Card Container simplified for files only */}
              <div className="uc-detail-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ position: 'relative' }}>
                  <Search size={16} className="text-subtle" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input 
                    type="text" 
                    placeholder="Filter files and directories at this level" 
                    className="uc-search-input w-full"
                    style={{ paddingLeft: '36px' }}
                    value={fileSearchQuery}
                    onChange={(e) => setFileSearchQuery(e.target.value)}
                  />
                </div>
                <div>
                  <Table
                    columns={fileColumns}
                    rows={filteredFiles}
                    keyExtractor={(row) => row.file_path}
                    rowActions={fileRowActions}
                    emptyState={<div className="text-center py-8 text-subtle">No content in volume</div>}
                    loading={isLoadingFiles}
                    actionsColumnWidth={50}
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'details' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card">
                <div className="uc-detail-title">Volume Details</div>
                <div className="uc-key-values">
                  <div><span>Name</span><strong>{vol.name}</strong></div>
                  <div><span>ID</span><strong>{vol.id}</strong></div>
                  <div>
                    <span>Storage Location</span>
                    <strong>{vol.storage_location || `${selection.catalog}/${selection.schema}/volumes/${vol.name}/`}</strong>
                  </div>
                  <div><span>Created By</span><strong>{vol.created_by}</strong></div>
                  <div><span>Created At</span><strong>{new Date(vol.created_at).toLocaleString()}</strong></div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'permissions' && (
            <div className="uc-tab-content">
              <p className="text-sm text-subtle">Permissions management is handled at the schema level.</p>
            </div>
          )}

          {/* Hidden file input for header row button upload */}
          <input 
            type="file" 
            id="volume-file-upload" 
            style={{ display: 'none' }} 
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file && vol.id) {
                uploadVolumeFileMutation.mutate({ volume_id: vol.id, file, sub_path: currentVolumePath });
              }
              e.target.value = '';
            }} 
          />
        </div>
      );
    }

    // ── Embedded notebook/dashboard interfaces ───────────────────────────────
    if (mainTabId !== 'details' && selection && selection.kind === 'notebook') {
      return (
        <div style={{ height: '100%', overflow: 'hidden' }}>
          <NotebookPage 
            notebookPath={selection.blob_path || notebookQuery.data?.blob_path || 'notebooks/untitled.ipynb'} 
            embedded 
            onDelete={() => {
              queryClient.invalidateQueries({ queryKey: ['uc-schema-notebooks', selection.catalog, selection.schema] });
              closeOpenPanel(mainTabId);
              setDetailsPanelSelection({ kind: 'schema', catalog: selection.catalog, schema: selection.schema });
            }}
          />
        </div>
      );
    }

    if (mainTabId !== 'details' && selection && selection.kind === 'dashboard') {
      const dashboardId = selection.dashboard_id || dashboardQuery.data?.dashboard_id;
      if (!dashboardId) {
        return <div className="uc-empty-state"><p>Dashboard editor is not initialized yet.</p></div>;
      }
      return (
        <div style={{ height: '100%', overflow: 'hidden' }}>
          <DashboardEditorPage dashboardId={dashboardId} embedded />
        </div>
      );
    }

    if (mainTabId !== 'details' && selection && selection.kind === 'query') {
      return (
        <div style={{ height: '100%', overflow: 'hidden' }}>
          <CatalogQueryEditorTab
            catalog={selection.catalog}
            schema={selection.schema}
            queryName={selection.query}
            onDelete={() => {
              queryClient.invalidateQueries({ queryKey: ['uc-schema-queries', selection.catalog, selection.schema] });
              closeOpenPanel(mainTabId);
              setDetailsPanelSelection({ kind: 'schema', catalog: selection.catalog, schema: selection.schema });
            }}
          />
        </div>
      );
    }

    // ── NOTEBOOK level ─────────────────────────────────────────────────────────
    if (selection && selection.kind === 'notebook') {
      if (notebookQuery.isLoading) {
        return <div className="uc-empty-state"><Loader2 size={24} className="spin" /><p>Loading notebook details...</p></div>;
      }
      const notebook = notebookQuery.data;
      if (!notebook) {
        return <div className="uc-empty-state"><p>Failed to load notebook details.</p></div>;
      }

      const notebookTabs = [
        { value: 'overview', label: 'Overview' },
        { value: 'cells', label: 'Execution & Cells' },
      ] as const;

      const cells = executionOutput || notebookContentQuery.data?.cells || [];

      return (
        <div className="uc-panel">
          {renderDetailHeader(notebook.name, 'notebook')}

          <PageTabs tabs={notebookTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content">
              <div className="uc-detail-grid">
                
                {/* Properties card */}
                <div className="uc-detail-card">
                  <div className="uc-detail-title">Properties</div>
                  <div className="uc-key-values">
                    <div>
                      <span>Owner</span>
                      <div className="flex items-center gap-2">
                        {editingNbOwner !== null ? (
                          <div className="flex items-center gap-1">
                            <input
                              className="uc-sidebar-owner-input"
                              style={{ width: '130px', padding: '2px 6px', fontSize: '12px' }}
                              value={editingNbOwner}
                              onChange={(e) => setEditingNbOwner(e.target.value)}
                            />
                            <button
                              className="btn-primary"
                              style={{ padding: '2px 6px', fontSize: '11px', minHeight: 'unset' }}
                              onClick={() =>
                                updateNotebookMutation.mutate({
                                  catalog: selection.catalog,
                                  schema: selection.schema,
                                  notebook: selection.notebook,
                                  body: { owner: editingNbOwner },
                                })
                              }
                              disabled={updateNotebookMutation.isPending}
                            >
                              Save
                            </button>
                            <button
                              className="btn-outline"
                              style={{ padding: '2px 6px', fontSize: '11px', minHeight: 'unset' }}
                              onClick={() => setEditingNbOwner(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <>
                            <strong>{notebook.owner || 'catalog-admin'}</strong>
                            <button
                              className="uc-icon-btn"
                              style={{ padding: '2px' }}
                              onClick={() => setEditingNbOwner(notebook.owner || 'catalog-admin')}
                              title="Edit Owner"
                            >
                              <Pencil size={12} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                    <div><span>Catalog</span><strong>{notebook.catalog_name}</strong></div>
                    <div><span>Schema</span><strong>{notebook.schema_name}</strong></div>
                    <div><span>Name</span><strong>{notebook.name}</strong></div>
                    <div><span>Type</span><strong>Governed Notebook</strong></div>
                    <div><span>Storage Location</span><strong style={{ wordBreak: 'break-all', fontSize: 11 }}>{notebook.storage_location || notebook.blob_path}</strong></div>
                  </div>

                  {/* Actions (Rename, Delete) */}
                  <div style={{ marginTop: '20px', display: 'flex', gap: '8px' }}>
                    <button
                      className="btn-outline flex items-center gap-1"
                      onClick={() => {
                        setMoveNbTargetCatalog(notebook.catalog_name);
                        setMoveNbTargetSchema(notebook.schema_name);
                        setMoveNbNewName(notebook.name);
                        setShowMoveNbModal(true);
                      }}
                    >
                      <Pencil size={12} /> Rename / Move
                    </button>
                    <button
                      className="btn-outline flex items-center gap-1"
                      style={{ color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
                      onClick={() => {
                        if (window.confirm(`Are you sure you want to delete "${notebook.name}"? This will permanently delete its registration in CompassX.`)) {
                          deleteNotebookMutation.mutate({ catalog: selection.catalog, schema: selection.schema, notebook: selection.notebook });
                        }
                      }}
                      disabled={deleteNotebookMutation.isPending}
                    >
                      <Trash size={12} /> Delete
                    </button>
                  </div>
                </div>

                {/* Description / Comment Card */}
                <div className="uc-detail-card" style={{ display: 'flex', flexDirection: 'column' }}>
                  <div className="uc-detail-title">Description</div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {editingNbComment !== null ? (
                      <div className="flex flex-col gap-2" style={{ width: '100%' }}>
                        <textarea
                          className="input-field"
                          style={{ width: '100%', minHeight: '100px', fontSize: '13px', padding: '8px' }}
                          value={editingNbComment}
                          onChange={(e) => setEditingNbComment(e.target.value)}
                          placeholder="Add a comment or description for this governed notebook..."
                        />
                        <div className="flex gap-2">
                          <button
                            className="btn-primary"
                            onClick={() =>
                              updateNotebookMutation.mutate({
                                catalog: selection.catalog,
                                schema: selection.schema,
                                notebook: selection.notebook,
                                body: { comment: editingNbComment },
                              })
                            }
                            disabled={updateNotebookMutation.isPending}
                          >
                            Save
                          </button>
                          <button
                            className="btn-outline"
                            onClick={() => setEditingNbComment(null)}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                        <p style={{
                          fontSize: '13.5px',
                          color: notebook.comment ? 'var(--color-text)' : 'var(--color-text-muted)',
                          fontStyle: notebook.comment ? 'normal' : 'italic',
                          margin: 0,
                          lineHeight: '1.5',
                          flex: 1
                        }}>
                          {notebook.comment || 'No description provided. Click below to add a description.'}
                        </p>
                        <button
                          className="btn-outline flex items-center gap-1 mt-4"
                          style={{ alignSelf: 'flex-start' }}
                          onClick={() => setEditingNbComment(notebook.comment || '')}
                        >
                          <Pencil size={12} /> Edit Description
                        </button>
                      </div>
                    )}
                  </div>
                </div>

              </div>
            </div>
          )}

          {activeTab === 'cells' && (
            <div className="uc-tab-content" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Execution Toolbar */}
              <div className="uc-detail-card" style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontSize: '14px', fontWeight: 600 }}>Jupyter Notebook Context</span>
                  <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                    Run Python cells in the sandboxed, state-preserving kernel execution environment.
                  </span>
                </div>
                <button
                  className="btn-primary flex items-center gap-1.5"
                  onClick={handleRunNotebook}
                  disabled={executingNotebook}
                  style={{ minWidth: '130px', justifyContent: 'center' }}
                >
                  {executingNotebook ? (
                    <>
                      <Loader2 size={14} className="spin" /> Executing...
                    </>
                  ) : (
                    <>
                      <Play size={14} fill="currentColor" /> Run Notebook
                    </>
                  )}
                </button>
              </div>

              {/* Cells list */}
              {notebookContentQuery.isLoading && !executionOutput ? (
                <div className="uc-empty-inline">
                  <Loader2 size={16} className="spin" /> Loading notebook cells...
                </div>
              ) : cells.length === 0 ? (
                <div className="uc-empty-inline">
                  No cells found in this notebook.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {cells.map((cell: any, idx: number) => {
                    const cellType = cell.cell_type || 'code';
                    const sourceText = Array.isArray(cell.source) ? cell.source.join('') : cell.source || '';
                    const executionCount = cell.execution_count != null ? cell.execution_count : null;
                    const outputs = cell.outputs || [];

                    return (
                      <div
                        key={idx}
                        style={{
                          border: '1px solid var(--color-border)',
                          borderRadius: '8px',
                          overflow: 'hidden',
                          backgroundColor: 'var(--color-surface)',
                          display: 'flex',
                          flexDirection: 'column'
                        }}
                      >
                        {/* Cell Header */}
                        <div
                          style={{
                            padding: '8px 12px',
                            background: 'var(--color-bg-subtle)',
                            borderBottom: '1px solid var(--color-border)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            fontSize: '11.5px',
                            color: 'var(--color-text-muted)'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{
                              fontWeight: 600,
                              textTransform: 'uppercase',
                              fontSize: '10px',
                              letterSpacing: '0.05em',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: cellType === 'code' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                              color: cellType === 'code' ? 'var(--color-primary)' : '#10b981'
                            }}>
                              {cellType}
                            </span>
                            <span>Cell #{idx + 1}</span>
                          </div>
                          {cellType === 'code' && (
                            <span style={{ fontFamily: 'monospace' }}>
                              In [{executionCount !== null ? executionCount : ' '}]
                            </span>
                          )}
                        </div>

                        {/* Cell Source Code */}
                        <div style={{ padding: '12px', backgroundColor: cellType === 'code' ? '#f8fafc' : '#fff' }}>
                          {cellType === 'code' ? (
                            <pre style={{
                              margin: 0,
                              fontFamily: 'monospace',
                              fontSize: '13px',
                              color: '#1e293b',
                              overflowX: 'auto',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all'
                            }}>
                              <code>{sourceText}</code>
                            </pre>
                          ) : (
                            <div style={{
                              fontSize: '14px',
                              lineHeight: '1.6',
                              color: 'var(--color-text)'
                            }}>
                              {sourceText}
                            </div>
                          )}
                        </div>

                        {/* Cell Outputs */}
                        {cellType === 'code' && outputs.length > 0 && (
                          <div style={{
                            padding: '12px',
                            borderTop: '1px solid var(--color-border)',
                            backgroundColor: '#1e293b',
                            color: '#f8fafc',
                            fontFamily: 'monospace',
                            fontSize: '12.5px',
                            overflowX: 'auto'
                          }}>
                            {outputs.map((out: any, oIdx: number) => {
                              const outputType = out.output_type;
                              if (outputType === 'stream') {
                                const text = Array.isArray(out.text) ? out.text.join('') : out.text || '';
                                return (
                                  <pre key={oIdx} style={{ margin: 0, whiteSpace: 'pre-wrap', color: out.name === 'stderr' ? '#f87171' : '#f8fafc' }}>
                                    {text}
                                  </pre>
                                );
                              }
                              if (outputType === 'execute_result' || outputType === 'display_data') {
                                const data = out.data || {};
                                const text = data['text/plain'] ? (Array.isArray(data['text/plain']) ? data['text/plain'].join('') : data['text/plain']) : '';
                                return (
                                  <pre key={oIdx} style={{ margin: 0, whiteSpace: 'pre-wrap', color: '#60a5fa' }}>
                                    {text}
                                  </pre>
                                );
                              }
                              if (outputType === 'error') {
                                const traceback = Array.isArray(out.traceback) ? out.traceback.join('\n') : out.traceback || '';
                                return (
                                  <pre key={oIdx} style={{ margin: 0, whiteSpace: 'pre-wrap', color: '#f87171' }}>
                                    {traceback}
                                  </pre>
                                );
                              }
                              return null;
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      );
    }

    // ── DASHBOARD level ────────────────────────────────────────────────────────
    if (selection && selection.kind === 'dashboard') {
      if (dashboardQuery.isLoading) {
        return <div className="uc-empty-state"><Loader2 size={24} className="spin" /><p>Loading dashboard details...</p></div>;
      }
      const dashboard = dashboardQuery.data;
      if (!dashboard) {
        return <div className="uc-empty-state"><p>Failed to load dashboard details.</p></div>;
      }

      const dashboardTabs = [
        { value: 'overview', label: 'Overview' },
      ] as const;

      return (
        <div className="uc-panel">
          {renderDetailHeader(dashboard.name, 'dashboard')}

          <PageTabs tabs={dashboardTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content" style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '20px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                
                {/* Dashboard metadata summary */}
                <div className="uc-detail-card">
                  <div className="uc-detail-title font-semibold">General Information</div>
                  <div className="uc-detail-grid">
                    <div><span>Name</span><strong>{dashboard.name}</strong></div>
                    <div><span>Type</span><strong>Governed Dashboard</strong></div>
                    <div><span>Dashboard Link</span>
                      <strong>
                        {dashboard.dashboard_id ? (
                          <a 
                            href={`/dashboards/${dashboard.dashboard_id}/edit`} 
                            style={{ color: 'var(--color-primary)', textDecoration: 'underline' }}
                          >
                            Open Dashboard Editor
                          </a>
                        ) : 'Not initialized'}
                      </strong>
                    </div>
                  </div>

                  {/* Actions (Launch, Rename, Delete) */}
                  <div style={{ marginTop: '20px', display: 'flex', gap: '8px' }}>
                    {dashboard.dashboard_id && (
                      <button
                        className="btn-primary flex items-center gap-1.5"
                        onClick={() => navigate(`/dashboards/${dashboard.dashboard_id}/edit`)}
                      >
                        <Play size={12} fill="currentColor" /> Open Editor
                      </button>
                    )}
                    <button
                      className="btn-outline flex items-center gap-1"
                      onClick={() => {
                        setMoveDbTargetCatalog(dashboard.catalog_name);
                        setMoveDbTargetSchema(dashboard.schema_name);
                        setMoveDbNewName(dashboard.name);
                        setShowMoveDbModal(true);
                      }}
                    >
                      <Pencil size={12} /> Rename / Move
                    </button>
                    <button
                      className="btn-outline flex items-center gap-1"
                      style={{ color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
                      onClick={() => {
                        if (confirm(`Are you sure you want to delete the dashboard "${dashboard.name}"? This will permanently delete its registration in CompassX and the dashboard design.`)) {
                          deleteDashboardMutation.mutate({ catalog: selection.catalog, schema: selection.schema, dashboard: selection.dashboard });
                        }
                      }}
                      disabled={deleteDashboardMutation.isPending}
                    >
                      <Trash size={12} /> Delete
                    </button>
                  </div>
                </div>

                {/* Description / Comment Card */}
                <div className="uc-detail-card" style={{ display: 'flex', flexDirection: 'column' }}>
                  <div className="uc-detail-title">Description</div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {editingDbComment !== null ? (
                      <div className="flex flex-col gap-2" style={{ width: '100%' }}>
                        <textarea
                          className="input-field"
                          style={{ width: '100%', minHeight: '100px', fontSize: '13px', padding: '8px' }}
                          value={editingDbComment}
                          onChange={(e) => setEditingDbComment(e.target.value)}
                          placeholder="Add a comment or description for this governed dashboard..."
                        />
                        <div className="flex gap-2">
                          <button
                            className="btn-primary"
                            onClick={() =>
                              updateDashboardMutation.mutate({
                                catalog: selection.catalog,
                                schema: selection.schema,
                                dashboard: selection.dashboard,
                                body: { comment: editingDbComment },
                              })
                            }
                            disabled={updateDashboardMutation.isPending}
                          >
                            Save
                          </button>
                          <button
                            className="btn-outline"
                            onClick={() => setEditingDbComment(null)}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                        <p style={{
                          fontSize: '13.5px',
                          color: dashboard.comment ? 'var(--color-text)' : 'var(--color-text-muted)',
                          fontStyle: dashboard.comment ? 'normal' : 'italic',
                          margin: 0,
                          lineHeight: '1.5',
                          flex: 1
                        }}>
                          {dashboard.comment || 'No description provided. Click below to add a description.'}
                        </p>
                        <button
                          className="btn-outline flex items-center gap-1 mt-4"
                          style={{ alignSelf: 'flex-start' }}
                          onClick={() => setEditingDbComment(dashboard.comment || '')}
                        >
                          <Pencil size={12} /> Edit Description
                        </button>
                      </div>
                    )}
                  </div>
                </div>

              </div>
            </div>
          )}
        </div>
      );
    }

    // ── TOOL level ─────────────────────────────────────────────────────────────
    if (selection && selection.kind === 'tool') {
      if (toolQuery.isLoading) {
        return <div className="uc-empty-state"><Loader2 size={24} className="spin" /><p>Loading tool details...</p></div>;
      }
      const tool = toolQuery.data;
      if (!tool) {
        return <div className="uc-empty-state"><p>Failed to load tool details.</p></div>;
      }

      const toolTabs = [
        { value: 'overview', label: 'Overview' },
        { value: 'params', label: 'Parameter Schema' },
        { value: 'source', label: 'Source Code' },
        { value: 'versions', label: `Version History (${tool.versions?.length || 1})` },
      ] as const;

      const properties = tool.param_schema?.properties || {};
      const requiredProps = new Set(tool.param_schema?.required || []);

      return (
        <div className="uc-panel">
          {renderDetailHeader(tool.name, 'tool')}

          <PageTabs tabs={toolTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content" style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '20px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Tool description */}
                <div className="uc-detail-card">
                  <div className="uc-detail-title font-semibold">Tool Description</div>
                  <p style={{ fontSize: '13.5px', color: 'var(--color-text)', lineHeight: 1.5, margin: 0 }}>
                    {tool.description || 'No prompt description provided for this tool.'}
                  </p>
                </div>

                {/* Connection Dependencies */}
                <div className="uc-detail-card">
                  <div className="uc-detail-title font-semibold">Declared Connection Dependencies</div>
                  <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: 8 }}>
                    Credentials for these connections are decrypted and injected at runtime during agent tool invocation.
                  </p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(tool.connection_dependencies || []).map((c: string) => (
                      <span key={c} className="uc-chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#eff6ff', color: '#1d4ed8', padding: '3px 8px', borderRadius: 4, fontWeight: 500 }}>
                        <Link2 size={12} /> {c}
                      </span>
                    ))}
                    {(tool.connection_dependencies || []).length === 0 && (
                      <span style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>No external connections required (Standalone tool).</span>
                    )}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Properties */}
                <div className="uc-detail-card">
                  <div className="uc-detail-title font-semibold">General Information</div>
                  <div className="uc-key-values">
                    <div><span>FQN</span><strong style={{ fontFamily: 'monospace', fontSize: 12 }}>{tool.full_name}</strong></div>
                    <div><span>Current Version</span><strong style={{ color: '#2563eb' }}>v{tool.current_version}</strong></div>
                    <div><span>Owner</span><strong>{tool.owner}</strong></div>
                    <div><span>Created</span><strong>{new Date(tool.created_at).toLocaleString()}</strong></div>
                    <div><span>Last Updated</span><strong>{new Date(tool.updated_at).toLocaleString()}</strong></div>
                    <div>
                      <span>Source Notebook</span>
                      {(() => {
                        const nbId = tool.source_notebook_object_id;
                        if (!nbId) return <strong style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>Standalone (No linked notebook)</strong>;
                        const isPath = nbId.includes('/') || nbId.endsWith('.ipynb');
                        const targetUrl = isPath ? `/notebooks/open?path=${encodeURIComponent(nbId)}` : null;
                        return (
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                            {targetUrl ? (
                              <a 
                                href={targetUrl} 
                                target="_blank" 
                                rel="noreferrer"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-primary)', textDecoration: 'underline', fontWeight: 600, fontSize: 12 }}
                                title="Open source notebook in new tab"
                              >
                                <FileCode size={13} /> {nbId.split('/').pop()}
                              </a>
                            ) : (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: 'monospace', fontSize: 12 }}>
                                <FileCode size={13} /> {nbId}
                              </span>
                            )}
                          </div>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'params' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card">
                <div className="uc-section-header" style={{ marginBottom: 12 }}>
                  <div className="uc-detail-title">Parameters (OpenAI / Anthropic Tool Schema)</div>
                  <span className="uc-chip">{Object.keys(properties).length} parameters</span>
                </div>
                {Object.keys(properties).length === 0 ? (
                  <div className="uc-empty-inline">This tool accepts no arguments (0 parameters).</div>
                ) : (
                  <div className="uc-table-responsive">
                    <table className="uc-columns-table">
                      <thead>
                        <tr>
                          <th>Parameter</th>
                          <th>Type</th>
                          <th>Requirement</th>
                          <th>Default Value</th>
                          <th>Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(properties).map(([pName, pMeta]: [string, any]) => (
                          <tr key={pName}>
                            <td style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--color-primary)' }}>{pName}</td>
                            <td><span className="uc-type-badge">{pMeta.type || 'any'}</span></td>
                            <td>
                              {requiredProps.has(pName) ? (
                                <span className="uc-chip" style={{ background: '#fef2f2', color: '#b91c1c', fontSize: 11 }}>Required</span>
                              ) : (
                                <span className="uc-chip" style={{ background: '#f1f5f9', color: '#64748b', fontSize: 11 }}>Optional</span>
                              )}
                            </td>
                            <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                              {pMeta.default !== undefined ? JSON.stringify(pMeta.default) : '—'}
                            </td>
                            <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                              {pMeta.description || '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div style={{ marginTop: 24 }}>
                  <div className="uc-detail-title" style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                    Raw Tool JSON Schema
                  </div>
                  <pre style={{ background: '#0f172a', color: '#e2e8f0', padding: 12, borderRadius: 6, fontSize: 11, overflowX: 'auto' }}>
                    {JSON.stringify(tool.param_schema, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'source' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card">
                <div className="uc-section-header" style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div className="uc-detail-title">Function Source Code (Current v{tool.current_version})</div>
                  <button
                    type="button"
                    className="btn-outline"
                    style={{ padding: '3px 8px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    onClick={() => {
                      navigator.clipboard.writeText(tool.source_code);
                      setCopiedFqn('source');
                      setTimeout(() => setCopiedFqn(null), 2000);
                    }}
                  >
                    {copiedFqn === 'source' ? <Check size={12} style={{ color: 'var(--color-success)' }} /> : <Copy size={12} />}
                    {copiedFqn === 'source' ? 'Copied' : 'Copy Code'}
                  </button>
                </div>
                <pre style={{ background: '#0f172a', color: '#38bdf8', padding: 16, borderRadius: 8, fontSize: 12, fontFamily: 'monospace', lineHeight: 1.6, overflowX: 'auto' }}>
                  {tool.source_code}
                </pre>
              </div>
            </div>
          )}

          {activeTab === 'versions' && (() => {
            const versions = tool.versions || [];
            const activeVer = versions.find(v => v.id === selectedToolVersionId) || versions[versions.length - 1] || null;
            const verProperties = activeVer?.param_schema?.properties || {};
            const verRequiredProps = new Set(activeVer?.param_schema?.required || []);

            return (
              <div className="uc-tab-content" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div className="uc-detail-card">
                  <div className="uc-detail-title" style={{ marginBottom: 12 }}>Immutable Version History ({versions.length})</div>
                  <div className="uc-table-responsive">
                    <table className="uc-columns-table">
                      <thead>
                        <tr>
                          <th>Version</th>
                          <th>Source Notebook</th>
                          <th>Declared Connections</th>
                          <th>Promoted By</th>
                          <th>Promoted At</th>
                          <th style={{ textAlign: 'right' }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {versions.map((v) => {
                          const isSelected = activeVer?.id === v.id;
                          return (
                            <tr 
                              key={v.id} 
                              onClick={() => setSelectedToolVersionId(v.id)}
                              style={{ cursor: 'pointer', background: isSelected ? 'var(--color-bg-subtle, #f8fafc)' : undefined }}
                            >
                              <td>
                                <span className="uc-chip" style={{ background: v.version === tool.current_version ? '#dcfce7' : '#f1f5f9', color: v.version === tool.current_version ? '#15803d' : '#475569', fontWeight: 600 }}>
                                  v{v.version} {v.version === tool.current_version && '(Current)'}
                                </span>
                              </td>
                              <td>
                                {v.source_notebook_object_id ? (
                                  <span style={{ fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-primary)' }}>
                                    <FileCode size={12} /> {v.source_notebook_object_id.split('/').pop()}
                                  </span>
                                ) : (
                                  <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>—</span>
                                )}
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                  {(v.connection_dependencies || []).map((c: string) => (
                                    <span key={c} style={{ fontSize: 11, padding: '1px 6px', borderRadius: 4, background: '#f1f5f9', color: '#475569' }}>
                                      {c}
                                    </span>
                                  ))}
                                  {(v.connection_dependencies || []).length === 0 && (
                                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>None</span>
                                  )}
                                </div>
                              </td>
                              <td>{v.promoted_by}</td>
                              <td>{new Date(v.promoted_at).toLocaleString()}</td>
                              <td style={{ textAlign: 'right' }}>
                                <button
                                  type="button"
                                  className={cx("btn-outline", isSelected && "btn-primary")}
                                  style={{ padding: '2px 8px', fontSize: 11 }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedToolVersionId(v.id);
                                  }}
                                >
                                  {isSelected ? 'Viewing' : 'Inspect Code'}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Historical Version Detail Inspector */}
                {activeVer && (
                  <div className="uc-detail-card" style={{ borderLeft: '3px solid #2563eb' }}>
                    <div className="uc-section-header" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div className="uc-detail-title font-semibold" style={{ fontSize: 15 }}>
                          Inspecting Version v{activeVer.version} {activeVer.version === tool.current_version ? '(Current Active Version)' : '(Historical Archive)'}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
                          Promoted by <strong>{activeVer.promoted_by}</strong> on {new Date(activeVer.promoted_at).toLocaleString()}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          type="button"
                          className="btn-outline"
                          style={{ padding: '3px 8px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                          onClick={() => {
                            navigator.clipboard.writeText(activeVer.source_code);
                            setCopiedFqn(`v${activeVer.version}`);
                            setTimeout(() => setCopiedFqn(null), 2000);
                          }}
                        >
                          {copiedFqn === `v${activeVer.version}` ? <Check size={12} style={{ color: 'var(--color-success)' }} /> : <Copy size={12} />}
                          {copiedFqn === `v${activeVer.version}` ? 'Copied' : `Copy v${activeVer.version} Code`}
                        </button>
                      </div>
                    </div>

                    {/* Source Code */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                        Python Source Code (v{activeVer.version})
                      </div>
                      <pre style={{ background: '#0f172a', color: '#38bdf8', padding: 16, borderRadius: 8, fontSize: 12, fontFamily: 'monospace', lineHeight: 1.6, overflowX: 'auto' }}>
                        {activeVer.source_code}
                      </pre>
                    </div>

                    {/* Parameter Schema for this version */}
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                        Parameter Schema (v{activeVer.version})
                      </div>
                      {Object.keys(verProperties).length === 0 ? (
                        <div className="uc-empty-inline" style={{ padding: 8, fontSize: 12 }}>No parameters required.</div>
                      ) : (
                        <div className="uc-table-responsive">
                          <table className="uc-columns-table">
                            <thead>
                              <tr>
                                <th>Parameter</th>
                                <th>Type</th>
                                <th>Requirement</th>
                                <th>Default</th>
                                <th>Description</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(verProperties).map(([pName, pMeta]: [string, any]) => (
                                <tr key={pName}>
                                  <td style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--color-primary)' }}>{pName}</td>
                                  <td><span className="uc-type-badge">{pMeta.type || 'any'}</span></td>
                                  <td>
                                    {verRequiredProps.has(pName) ? (
                                      <span className="uc-chip" style={{ background: '#fef2f2', color: '#b91c1c', fontSize: 11 }}>Required</span>
                                    ) : (
                                      <span className="uc-chip" style={{ background: '#f1f5f9', color: '#64748b', fontSize: 11 }}>Optional</span>
                                    )}
                                  </td>
                                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                                    {pMeta.default !== undefined ? JSON.stringify(pMeta.default) : '—'}
                                  </td>
                                  <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                                    {pMeta.description || '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      );
    }

    // ── QUERY level ────────────────────────────────────────────────────────────
    if (selection && selection.kind === 'query') {
      if (queryQuery.isLoading) {
        return <div className="uc-empty-state"><Loader2 size={24} className="spin" /><p>Loading query details...</p></div>;
      }
      const q = queryQuery.data;
      if (!q) {
        return <div className="uc-empty-state"><p>Failed to load query details.</p></div>;
      }

      const allQueryVersions = queryVersionsQuery.data || q.versions || [];
      const queryTabs = [
        { value: 'overview', label: 'Overview' },
        { value: 'versions', label: `Version History (${allQueryVersions.length || 1})` },
        { value: 'sql', label: 'SQL Query' },
      ] as const;

      return (
        <div className="uc-panel">
          {renderDetailHeader(q.name, 'query')}

          <PageTabs tabs={queryTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content" style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '20px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                
                {/* Query metadata summary */}
                <div className="uc-detail-card">
                  <div className="uc-detail-title font-semibold">General Information</div>
                  <div className="uc-detail-grid">
                    <div><span>Name</span><strong>{q.name}</strong></div>
                    <div><span>Active Version</span><strong style={{ color: 'var(--color-primary)' }}>v{q.current_version || 1}</strong></div>
                    <div><span>Full Name</span><strong className="font-mono text-xs">{q.full_name}</strong></div>
                    <div><span>Catalog</span><strong>{q.catalog_name}</strong></div>
                    <div><span>Schema</span><strong>{q.schema_name}</strong></div>
                    <div><span>Owner</span><strong>{q.owner || '—'}</strong></div>
                    <div><span>Created At</span><strong>{new Date(q.created_at).toLocaleString()}</strong></div>
                    <div><span>Updated At</span><strong>{new Date(q.updated_at).toLocaleString()}</strong></div>
                  </div>

                  {/* Actions (Open in Query Editor, Delete) */}
                  <div style={{ marginTop: '20px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      className="btn-primary flex items-center gap-1.5"
                      onClick={() => syncOpenPanel(selection)}
                    >
                      <Play size={12} fill="currentColor" /> Open in Query Editor
                    </button>
                    <button
                      className="btn-outline flex items-center gap-1"
                      onClick={() => navigate(`/sql-warehouse?catalog=${encodeURIComponent(q.catalog_name)}&schema=${encodeURIComponent(q.schema_name)}&query_name=${encodeURIComponent(q.name)}&sql=${encodeURIComponent(q.sql_text)}`)}
                    >
                      <Database size={12} /> Open in SQL Warehouse
                    </button>
                    <button
                      className="btn-outline flex items-center gap-1"
                      style={{ color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
                      onClick={() => {
                        if (confirm(`Are you sure you want to delete the query "${q.name}" from the catalog?`)) {
                          deleteQueryMutation.mutate({ catalog: selection.catalog, schema: selection.schema, query: selection.query });
                        }
                      }}
                      disabled={deleteQueryMutation.isPending}
                    >
                      <Trash size={12} /> Delete
                    </button>
                  </div>
                </div>

                {/* Description Card */}
                <div className="uc-detail-card" style={{ display: 'flex', flexDirection: 'column' }}>
                  <div className="uc-detail-title">Description</div>
                  <div style={{ fontSize: 13, color: q.description ? 'var(--color-text)' : 'var(--color-text-muted)' }}>
                    {q.description || 'No description provided.'}
                  </div>
                </div>

                {/* SQL Preview snippet in Overview */}
                <div className="uc-detail-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <div className="uc-detail-title font-semibold">SQL Preview (v{q.current_version || 1})</div>
                    <button
                      className="btn-outline flex items-center gap-1"
                      style={{ fontSize: 11, padding: '2px 8px' }}
                      onClick={() => {
                        navigator.clipboard.writeText(q.sql_text);
                        setCopiedFqn('sql_overview');
                        setTimeout(() => setCopiedFqn(null), 2000);
                      }}
                    >
                      {copiedFqn === 'sql_overview' ? <Check size={11} style={{ color: 'var(--color-success)' }} /> : <Copy size={11} />}
                      {copiedFqn === 'sql_overview' ? 'Copied' : 'Copy SQL'}
                    </button>
                  </div>
                  <pre
                    style={{
                      background: '#0f172a',
                      border: '1px solid var(--color-border)',
                      borderRadius: 6,
                      padding: '12px 14px',
                      fontSize: 12,
                      fontFamily: 'monospace',
                      maxHeight: 240,
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap',
                      color: '#f8fafc',
                      margin: 0,
                    }}
                  >
                    {q.sql_text}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'versions' && (
            <div className="uc-tab-content" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Immutable Version History</h3>
                  <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--color-text-muted)' }}>
                    Every revision of this query is tracked with author attribution, change summary, and full SQL snapshot.
                  </p>
                </div>
                <button
                  className="btn-primary flex items-center gap-1.5"
                  onClick={() => syncOpenPanel(selection)}
                >
                  <Play size={12} fill="currentColor" /> Open in Editor
                </button>
              </div>

              {queryVersionsQuery.isLoading && (
                <div className="uc-empty-state"><Loader2 size={20} className="spin" /><p>Loading version history...</p></div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {allQueryVersions.map((v) => {
                  const isCurrent = v.version === (q.current_version || 1);
                  return (
                    <div
                      key={v.version}
                      className="uc-detail-card"
                      style={{
                        borderLeft: isCurrent ? '3px solid var(--color-primary)' : '1px solid var(--color-border)',
                        padding: 16,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: 4,
                              fontWeight: 700,
                              fontSize: 12,
                              background: isCurrent ? 'var(--color-primary)' : 'var(--color-surface-2)',
                              color: isCurrent ? '#ffffff' : 'inherit',
                            }}
                          >
                            v{v.version}
                          </span>
                          {isCurrent && (
                            <span className="uc-chip" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 600 }}>
                              Active Version
                            </span>
                          )}
                          <span style={{ fontSize: 13, fontWeight: 600 }}>
                            {v.change_summary || (v.version === 1 ? 'Initial query registration' : `Revision ${v.version}`)}
                          </span>
                        </div>

                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            className="btn-outline flex items-center gap-1"
                            style={{ fontSize: 11, padding: '2px 8px' }}
                            onClick={() => {
                              navigator.clipboard.writeText(v.sql_text);
                              setCopiedFqn(`sql_ver_${v.version}`);
                              setTimeout(() => setCopiedFqn(null), 2000);
                            }}
                          >
                            {copiedFqn === `sql_ver_${v.version}` ? <Check size={11} style={{ color: 'var(--color-success)' }} /> : <Copy size={11} />}
                            {copiedFqn === `sql_ver_${v.version}` ? 'Copied' : 'Copy SQL'}
                          </button>

                          {!isCurrent && (
                            <button
                              className="btn-outline flex items-center gap-1"
                              style={{ fontSize: 11, padding: '2px 8px' }}
                              onClick={() => {
                                if (confirm(`Restore query to version ${v.version}? This will create a new version with this snapshot's SQL.`)) {
                                  restoreQueryVersionMutation.mutate({
                                    catalog: selection.catalog,
                                    schema: selection.schema,
                                    query: selection.query,
                                    version: v.version,
                                  });
                                }
                              }}
                              disabled={restoreQueryVersionMutation.isPending}
                            >
                              <History size={11} /> Restore this Version
                            </button>
                          )}
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 10 }}>
                        <span>Author: <strong style={{ color: 'var(--color-text)' }}>{v.created_by || q.owner}</strong></span>
                        <span>Committed: <strong style={{ color: 'var(--color-text)' }}>{new Date(v.created_at).toLocaleString()}</strong></span>
                      </div>

                      <pre
                        style={{
                          background: '#0f172a',
                          border: '1px solid var(--color-border)',
                          borderRadius: 6,
                          padding: '10px 12px',
                          fontSize: 12,
                          fontFamily: 'monospace',
                          maxHeight: 160,
                          overflowY: 'auto',
                          whiteSpace: 'pre-wrap',
                          color: '#f8fafc',
                          margin: 0,
                        }}
                      >
                        {v.sql_text}
                      </pre>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === 'sql' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div className="uc-detail-title font-semibold">Full SQL Query</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      className="btn-outline flex items-center gap-1"
                      style={{ fontSize: 12, padding: '4px 10px' }}
                      onClick={() => {
                        navigator.clipboard.writeText(q.sql_text);
                        setCopiedFqn('sql_tab');
                        setTimeout(() => setCopiedFqn(null), 2000);
                      }}
                    >
                      {copiedFqn === 'sql_tab' ? <Check size={12} style={{ color: 'var(--color-success)' }} /> : <Copy size={12} />}
                      {copiedFqn === 'sql_tab' ? 'Copied' : 'Copy SQL'}
                    </button>
                    <button
                      className="btn-primary flex items-center gap-1"
                      style={{ fontSize: 12, padding: '4px 10px' }}
                      onClick={() => syncOpenPanel(selection)}
                    >
                      <Play size={12} fill="currentColor" /> Open in Query Editor
                    </button>
                  </div>
                </div>
                <pre
                  style={{
                    background: '#0f172a',
                    border: '1px solid var(--color-border)',
                    borderRadius: 6,
                    padding: '16px',
                    fontSize: 13,
                    fontFamily: 'monospace',
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                    color: '#f8fafc',
                    margin: 0,
                  }}
                >
                  {q.sql_text}
                </pre>
              </div>
            </div>
          )}
        </div>
      );
    }

    // ── TABLE level ────────────────────────────────────────────────────────────
    if (selection && selection.kind === 'table') {
      if (tableQuery.isLoading) {
        return <div className="uc-empty-state"><Loader2 size={24} className="spin" /><p>Loading table details...</p></div>;
      }
      const table = tableQuery.data;
      if (!table) {
        return <div className="uc-empty-state"><p>Failed to load table details.</p></div>;
      }
      const lineage = lineageQuery.data;
      
      const tableTabs = [
        { value: 'overview', label: 'Overview' },
        { value: 'columns', label: 'Columns' },
        { value: 'sample', label: 'Sample Data' },
        { value: 'lineage', label: 'Lineage' },
        { value: 'details', label: 'Details' },
      ] as const;

      const defaultOwner = table.owner || 'catalog-admin';

      return (
        <div className="uc-panel">
          {renderDetailHeader(table.name, 'table')}

          <PageTabs tabs={tableTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content">
              <div className="uc-detail-grid">
                <div className="uc-detail-card">
                  <div className="uc-detail-title">Properties</div>
                  <div className="uc-key-values">
                    <div><span>Owner</span><strong>{getEntityOwner(selection, defaultOwner)}</strong></div>
                    <div><span>Catalog</span><strong>{table.catalog}</strong></div>
                    <div><span>Schema</span><strong>{table.schema_name}</strong></div>
                    <div><span>Table</span><strong>{table.name}</strong></div>
                    <div><span>Type</span><strong>{table.table_type === 'iceberg' ? 'Iceberg' : 'Postgres Native'}</strong></div>
                    {table.connection_name && <div><span>Connection</span><strong>{table.connection_name}</strong></div>}
                    {table.source_database && <div><span>Database</span><strong>{table.source_database}</strong></div>}
                    {table.storage_location && <div><span>Storage</span><strong style={{ wordBreak: 'break-all', fontSize: 11 }}>{table.storage_location}</strong></div>}
                  </div>

                  {/* Actions (Refresh columns, Delete if Iceberg table) */}
                  <div style={{ marginTop: '20px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn-outline flex items-center gap-1"
                      onClick={() => refreshMutation.mutate()}
                      disabled={refreshMutation.isPending}
                    >
                      <RefreshCw size={12} className={refreshMutation.isPending ? 'spin' : ''} />
                      Refresh columns
                    </button>
                    {table.table_type === 'iceberg' && (
                      <button
                        type="button"
                        className="btn-outline flex items-center gap-1"
                        style={{ color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
                        onClick={() => setTableToDelete({ catalog: table.catalog, schema: table.schema_name, table: table.name })}
                        disabled={deleteTableMutation.isPending}
                      >
                        <Trash size={12} /> Delete table
                      </button>
                    )}
                  </div>
                </div>
                <div className="uc-detail-card">
                  <div className="uc-detail-title">Schema Summary</div>
                  <div className="uc-key-values">
                    <div><span>Columns</span><strong>{table.columns.length}</strong></div>
                    <div><span>Read Roles</span><strong>{getEntityReadRoles(selection, table.read_roles).length > 0 ? getEntityReadRoles(selection, table.read_roles).join(', ') : '—'}</strong></div>
                    <div><span>Write Roles</span><strong>{getEntityWriteRoles(selection, table.write_roles).length > 0 ? getEntityWriteRoles(selection, table.write_roles).join(', ') : '—'}</strong></div>
                  </div>
                  {table.columns.length > 0 && (
                    <div className="uc-col-preview">
                      {table.columns.slice(0, 5).map(c => (
                        <div key={c.name} className="uc-col-pill">
                          <span className="uc-col-pill-name">{c.name}</span>
                          <span className="uc-col-pill-type">{c.data_type}</span>
                        </div>
                      ))}
                      {table.columns.length > 5 && <span className="uc-col-pill-more">+{table.columns.length - 5} more</span>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'columns' && (
            <div className="uc-tab-content">
              <div className="uc-section-header" style={{ marginBottom: 12 }}>
                <h3>Schema Definition</h3>
                <span className="uc-chip">{table.columns.length} columns</span>
              </div>
              {table.columns.length === 0 ? (
                <div className="uc-empty-inline">No columns introspected yet. Click Refresh Columns.</div>
              ) : (
                <div className="uc-columns-table-wrap">
                  <table className="uc-columns-table">
                    <thead>
                      <tr><th>#</th><th>Column Name</th><th>Data Type</th><th>Nullable</th></tr>
                    </thead>
                    <tbody>
                      {table.columns.map((col) => (
                        <tr key={col.name}>
                          <td>{col.ordinal}</td>
                          <td style={{ fontWeight: 500 }}>{col.name}</td>
                          <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{col.data_type}</td>
                          <td>{col.nullable ? 'YES' : 'NO'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {activeTab === 'sample' && (
            <div className="uc-tab-content">
              {sampleDataQuery.isLoading && (
                <div className="uc-empty-inline"><Loader2 size={16} className="spin" style={{ display: 'inline' }} /> Loading sample data...</div>
              )}
              {sampleDataQuery.isError && (
                <div className="uc-empty-inline" style={{ color: 'var(--color-danger)' }}>
                  {(sampleDataQuery.error as any)?.response?.data?.detail || 'Failed to load sample data.'}
                </div>
              )}
              {sampleDataQuery.data && sampleDataQuery.data.columns.length === 0 && (
                <div className="uc-empty-inline">No rows returned.</div>
              )}
              {sampleDataQuery.data && sampleDataQuery.data.columns.length > 0 && (
                <>
                  <div className="uc-section-header" style={{ marginBottom: 12 }}>
                    <h3>Sample Data</h3>
                    <span className="uc-chip">{sampleDataQuery.data.row_count} rows</span>
                  </div>
                  <div className="uc-sample-table-wrap">
                    <table className="uc-columns-table uc-sample-table">
                      <thead>
                        <tr>{sampleDataQuery.data.columns.map(c => <th key={c}>{c}</th>)}</tr>
                      </thead>
                      <tbody>
                        {sampleDataQuery.data.rows.map((row, ri) => (
                          <tr key={ri}>
                            {row.map((cell, ci) => (
                              <td key={ci} style={{ fontFamily: 'monospace', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {cell === null ? <span style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>NULL</span> : cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'lineage' && (
            <div className="uc-tab-content">
              <div className="uc-lineage-section">
                <div className="uc-detail-title" style={{ marginBottom: 8 }}>Upstream</div>
                {(lineage?.upstream?.length ?? 0) === 0 ? (
                  <div className="uc-empty-inline">No upstream lineage.</div>
                ) : lineage!.upstream.map(e => (
                  <div key={e.source_fqn} className="uc-lineage-row"><Link2 size={13} /><span>{e.source_fqn}</span></div>
                ))}
              </div>
              <div className="uc-lineage-section" style={{ marginTop: 20 }}>
                <div className="uc-detail-title" style={{ marginBottom: 8 }}>Downstream</div>
                {(lineage?.downstream?.length ?? 0) === 0 ? (
                  <div className="uc-empty-inline">No downstream lineage.</div>
                ) : lineage!.downstream.map(e => (
                  <div key={e.target_fqn} className="uc-lineage-row"><Link2 size={13} /><span>{e.target_fqn}</span></div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'details' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card" style={{ maxWidth: 560 }}>
                <div className="uc-detail-title">Full Metadata</div>
                <div className="uc-key-values">
                  <div><span>FQN</span><strong style={{ fontFamily: 'monospace', fontSize: 12 }}>{table.fqn}</strong></div>
                  <div><span>ID</span><strong style={{ fontFamily: 'monospace', fontSize: 11 }}>{table.id}</strong></div>
                  <div><span>Owner</span><strong>{getEntityOwner(selection, defaultOwner)}</strong></div>
                  <div><span>Type</span><strong>{table.table_type}</strong></div>
                  {table.connection_name && <div><span>Connection</span><strong>{table.connection_name}</strong></div>}
                  {table.source_database && <div><span>Source DB</span><strong>{table.source_database}</strong></div>}
                  {table.pg_schema && <div><span>PG Schema</span><strong>{table.pg_schema}</strong></div>}
                  {table.pg_table && <div><span>PG Table</span><strong>{table.pg_table}</strong></div>}
                  {table.metadata_location && <div><span>Metadata</span><strong style={{ wordBreak: 'break-all', fontSize: 11 }}>{table.metadata_location}</strong></div>}
                  {table.storage_location && <div><span>Storage</span><strong style={{ wordBreak: 'break-all', fontSize: 11 }}>{table.storage_location}</strong></div>}
                  <div><span>Read Roles</span><strong>{getEntityReadRoles(selection, table.read_roles).join(', ') || '—'}</strong></div>
                  <div><span>Write Roles</span><strong>{getEntityWriteRoles(selection, table.write_roles).join(', ') || '—'}</strong></div>
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }

    // ── CATALOG level ──────────────────────────────────────────────────────────
    if (selection && selection.kind === 'catalog') {
      const cat = catalogs.find(c => c.name === selection.catalog);
      const catalogTabs = [
        { value: 'overview', label: 'Overview' },
        { value: 'schemas', label: 'Schemas' },
        { value: 'workspaces', label: 'Workspaces' },
        { value: 'details', label: 'Details' },
      ] as const;

      const defaultOwner = 'catalog-admin';

      return (
        <div className="uc-panel">
          {renderDetailHeader(selection.catalog, 'catalog')}

          <PageTabs tabs={catalogTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content">
              <div className="uc-detail-grid">
                <div className="uc-detail-card">
                  <div className="uc-detail-title">Properties</div>
                  <div className="uc-key-values">
                    <div><span>Name</span><strong>{selection.catalog}</strong></div>
                    <div><span>Type</span><strong>{cat?.catalog_type || 'iceberg'}</strong></div>
                    {cat?.database_name && <div><span>Database</span><strong>{cat.database_name}</strong></div>}
                    {cat?.storage_backend_id && (
                      <div><span>Storage</span><strong>{storageBackends.find(b => b.id === cat.storage_backend_id)?.name ?? cat.storage_backend_id}</strong></div>
                    )}
                    <div><span>Schemas</span><strong>{cat?.schema_count ?? 0}</strong></div>
                    <div><span>Tables</span><strong>{cat?.table_count ?? 0}</strong></div>
                  </div>
                </div>
                <div className="uc-detail-card">
                  <div className="uc-detail-title">Schemas</div>
                  <div className="uc-child-list">
                    {(cat?.schemas || []).slice(0, 8).map(s => (
                      <div
                        key={s.id}
                        className="uc-child-item"
                        onClick={() => { setExpandedSchemas(prev => ({ ...prev, [`${selection.catalog}.${s.name}`]: true })); selectAndNavigate({ kind: 'schema', catalog: selection.catalog, schema: s.name }); }}
                      >
                        <Folder size={13} />
                        <span>{s.name}</span>
                        <span className="uc-child-badge">{s.table_count}</span>
                      </div>
                    ))}
                    {(cat?.schemas.length ?? 0) === 0 && <div className="uc-empty-inline">No schemas yet.</div>}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'schemas' && (
            <div className="uc-tab-content">
              {renderAssetsGrid()}
            </div>
          )}

          {activeTab === 'workspaces' && renderWorkspaceBindings()}

          {activeTab === 'details' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card" style={{ maxWidth: 560 }}>
                <div className="uc-detail-title">Full Metadata</div>
                <div className="uc-key-values">
                  <div><span>ID</span><strong style={{ fontFamily: 'monospace', fontSize: 11 }}>{cat?.id}</strong></div>
                  <div><span>Name</span><strong>{selection.catalog}</strong></div>
                  <div><span>Type</span><strong>{cat?.catalog_type || '—'}</strong></div>
                  {cat?.database_name && <div><span>Database</span><strong>{cat.database_name}</strong></div>}
                  {cat?.connection_id && <div><span>Connection ID</span><strong>{cat.connection_id}</strong></div>}
                  {cat?.storage_backend_id && <div><span>Storage Backend ID</span><strong style={{ fontFamily: 'monospace', fontSize: 11 }}>{cat.storage_backend_id}</strong></div>}
                  {cat?.base_path && <div><span>Base Path</span><strong style={{ fontFamily: 'monospace', fontSize: 11 }}>{cat.base_path}</strong></div>}
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }

    // ── SCHEMA level ───────────────────────────────────────────────────────────
    if (selection && selection.kind === 'schema') {
      const cat = catalogs.find(c => c.name === selection.catalog);
      const schemaInfo = cat?.schemas.find(s => s.name === selection.schema);
      const tables = schemaTablesCache[`${selection.catalog}.${selection.schema}`] || [];
      const schemaTabs = [
        { value: 'overview', label: 'Overview' },
        { value: 'details', label: 'Details' },
        { value: 'permissions', label: 'Permissions' },
      ] as const;

      const defaultOwner = 'catalog-admin';
      const fqn = getFqn(selection);

      return (
        <div className="uc-panel">
          {renderDetailHeader(selection.schema, 'schema')}

          <PageTabs tabs={schemaTabs} value={activeTab} onChange={setActiveTab} />

          {activeTab === 'overview' && (
            <div className="uc-tab-content">
              {renderSchemaOverviewTab(tables)}
            </div>
          )}

          {activeTab === 'permissions' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card" style={{ maxWidth: '640px' }}>
                <div className="uc-detail-title">Schema Permissions</div>
                <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
                  Manage roles and access permissions for this schema namespace.
                </p>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {/* Read Roles */}
                  <div>
                    <h4 style={{ fontSize: '13.5px', fontWeight: 600, marginBottom: '8px' }}>Read Roles</h4>
                    <div className="uc-tags-list" style={{ marginBottom: '8px' }}>
                      {getEntityReadRoles(selection, schemaInfo?.read_roles || []).map(role => (
                        <span key={role} className="uc-tag-badge" style={{ background: 'var(--color-primary-bg)', color: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}>
                          {role}
                          <button type="button" onClick={() => handleRemoveReadRole(selection, role)}>
                            <X size={10} />
                          </button>
                        </span>
                      ))}
                      {getEntityReadRoles(selection, schemaInfo?.read_roles || []).length === 0 && (
                        <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>No read roles configured.</span>
                      )}
                    </div>
                    <form 
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleAddReadRole(selection, newReadRole);
                      }}
                      style={{ display: 'flex', gap: '8px', maxWidth: '320px' }}
                    >
                      <input 
                        type="text" 
                        className="uc-sidebar-owner-input"
                        placeholder="Add read role..."
                        value={newReadRole}
                        onChange={(e) => setNewReadRole(e.target.value)}
                      />
                      <button type="submit" className="btn-primary" style={{ padding: '4px 10px', minHeight: 'unset', fontSize: '12px' }}>Add</button>
                    </form>
                  </div>

                  <hr style={{ border: 'none', borderBottom: '1px solid var(--color-border)', margin: 0 }} />

                  {/* Write Roles */}
                  <div>
                    <h4 style={{ fontSize: '13.5px', fontWeight: 600, marginBottom: '8px' }}>Write Roles</h4>
                    <div className="uc-tags-list" style={{ marginBottom: '8px' }}>
                      {getEntityWriteRoles(selection, schemaInfo?.write_roles || []).map(role => (
                        <span key={role} className="uc-tag-badge" style={{ background: 'rgba(16, 185, 129, 0.08)', color: '#059669', borderColor: '#a7f3d0' }}>
                          {role}
                          <button type="button" onClick={() => handleRemoveWriteRole(selection, role)}>
                            <X size={10} />
                          </button>
                        </span>
                      ))}
                      {getEntityWriteRoles(selection, schemaInfo?.write_roles || []).length === 0 && (
                        <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>No write roles configured.</span>
                      )}
                    </div>
                    <form 
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleAddWriteRole(selection, newWriteRole);
                      }}
                      style={{ display: 'flex', gap: '8px', maxWidth: '320px' }}
                    >
                      <input 
                        type="text" 
                        className="uc-sidebar-owner-input"
                        placeholder="Add write role..."
                        value={newWriteRole}
                        onChange={(e) => setNewWriteRole(e.target.value)}
                      />
                      <button type="submit" className="btn-primary" style={{ padding: '4px 10px', minHeight: 'unset', fontSize: '12px' }}>Add</button>
                    </form>
                  </div>
                </div>
              </div>
            </div>
          )}



          {activeTab === 'details' && (
            <div className="uc-tab-content">
              <div className="uc-detail-card" style={{ maxWidth: 560 }}>
                <div className="uc-detail-title">Full Metadata</div>
                <div className="uc-key-values">
                  {schemaInfo?.id && <div><span>ID</span><strong style={{ fontFamily: 'monospace', fontSize: 11 }}>{schemaInfo.id}</strong></div>}
                  <div><span>Catalog</span><strong>{selection.catalog}</strong></div>
                  <div><span>Schema</span><strong>{selection.schema}</strong></div>
                  <div><span>Table Count</span><strong>{tables.length}</strong></div>
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }

    // ── ROOT level (no selection) ──────────────────────────────────────────────
    return (
      <div className="uc-panel">
        <div className="uc-panel-hero">
          <div>
            <div className="uc-panel-eyebrow uc-chip">Workspace</div>
            <h2>Data Catalog</h2>
            <p>Unity Catalog — select a catalog, schema, or table from the sidebar.</p>
          </div>
        </div>
        <PageTabs tabs={[{ value: 'overview', label: 'Overview' }] as const} value={activeTab} onChange={setActiveTab} />
        <div className="uc-tab-content">
          {renderAssetsGrid()}
        </div>
      </div>
    );
  };

  const [showWarehouseDropdown, setShowWarehouseDropdown] = useState(false);
  const [activeHeaderDropdown, setActiveHeaderDropdown] = useState<string | null>(null);

  const MOCK_CSV_CONTENT = `asset_id,asset_name,timestamp,generation_kw,date
20,INVERTER-01,2026-06-15T00:00:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:01:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:02:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:03:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:04:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:05:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:06:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:07:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:08:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:09:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:10:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:11:00.000Z,0.0,2026-06-15
20,INVERTER-01,2026-06-15T00:12:00.000Z,0.0,2026-06-15`;

  const parseCSV = (text: string) => {
    const lines: string[][] = [];
    let row: string[] = [];
    let inQuotes = false;
    let currentField = '';

    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      const nextChar = text[i + 1];

      if (inQuotes) {
        if (char === '"') {
          if (nextChar === '"') {
            currentField += '"';
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          currentField += char;
        }
      } else {
        if (char === '"') {
          inQuotes = true;
        } else if (char === ',') {
          row.push(currentField.trim());
          currentField = '';
        } else if (char === '\r' || char === '\n') {
          row.push(currentField.trim());
          currentField = '';
          if (row.length > 0 && (row.length > 1 || row[0] !== '')) {
            lines.push(row);
          }
          row = [];
          if (char === '\r' && nextChar === '\n') {
            i++;
          }
        } else {
          currentField += char;
        }
      }
    }
    if (currentField || row.length > 0) {
      row.push(currentField.trim());
      lines.push(row);
    }
    return lines;
  };

  const inferType = (values: string[]): string => {
    const nonNulls = values.filter(v => v !== '' && v !== null && v !== undefined && v.toLowerCase() !== 'null');
    if (nonNulls.length === 0) return 'string';

    let isInt = true;
    let isFloat = true;
    let isBool = true;
    let isDate = true;
    let isTimestamp = true;

    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    const timestampRegex = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/;

    for (const val of nonNulls) {
      const lower = val.toLowerCase();
      if (isNaN(Number(val)) || val.includes('.')) {
        isInt = false;
      }
      if (isNaN(Number(val))) {
        isFloat = false;
      }
      if (lower !== 'true' && lower !== 'false' && lower !== '1' && lower !== '0' && lower !== 'yes' && lower !== 'no') {
        isBool = false;
      }
      if (!dateRegex.test(val)) {
        isDate = false;
      }
      if (!timestampRegex.test(val)) {
        isTimestamp = false;
      }
    }

    if (isInt) {
      const maxVal = Math.max(...nonNulls.map(v => Number(v)));
      const minVal = Math.min(...nonNulls.map(v => Number(v)));
      return (maxVal > 2147483647 || minVal < -2147483648) ? 'int64' : 'int32';
    }
    if (isFloat) return 'float64';
    if (isBool) return 'bool';
    if (isTimestamp) return 'timestamp';
    if (isDate) return 'date';
    return 'string';
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'int32':
      case 'int64':
        return <span style={{ fontFamily: 'monospace', fontWeight: 'bold', fontSize: '12px', marginRight: '6px', color: 'var(--color-primary)' }}>123</span>;
      case 'float32':
      case 'float64':
      case 'decimal':
        return <span style={{ fontFamily: 'monospace', fontWeight: 'bold', fontSize: '12px', marginRight: '6px', color: 'var(--color-primary)' }}>.00</span>;
      case 'bool':
      case 'boolean':
        return <span style={{ fontFamily: 'monospace', fontWeight: 'bold', fontSize: '10px', marginRight: '6px', color: 'var(--color-success)' }}>T/F</span>;
      case 'timestamp':
        return <Clock size={12} className="text-primary mr-1.5" style={{ color: 'var(--color-primary)' }} />;
      case 'date':
        return <Calendar size={12} className="text-primary mr-1.5" style={{ color: 'var(--color-primary)' }} />;
      case 'json':
        return <span style={{ fontFamily: 'monospace', fontWeight: 'bold', fontSize: '10px', marginRight: '6px', color: 'var(--color-warning)' }}>{`{}`}</span>;
      default:
        return <span style={{ fontFamily: 'monospace', fontWeight: 'bold', fontSize: '12px', marginRight: '6px', color: 'var(--color-text-subtle)' }}>Abc</span>;
    }
  };

  const handleFileUpload = (file: File) => {
    setRealUploadedFile(file);
    const baseName = file.name.split('.').slice(0, -1).join('.');
    const sanitized = baseName.toLowerCase().replace(/[^a-z0-9_]/g, '_');
    setTableNameInput(sanitized);

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const rows = parseCSV(text);
      if (rows.length > 0) {
        const headers = rows[0];
        const dataRows = rows.slice(1);
        setPreviewColumns(headers);
        setPreviewRows(dataRows.slice(0, 50));

        const types: Record<string, string> = {};
        headers.forEach((header, idx) => {
          const colValues = dataRows.map(r => r[idx]);
          types[header] = inferType(colValues);
        });
        setInferredTypes(types);
      }
    };
    reader.readAsText(file);
  };

  const renderCreateTableFromFileFlow = () => {
    const selectedCatalog = (catalogsQuery.data || []).find(c => c.name === selectedCatalogName);
    const availableSchemas = selectedCatalog?.schemas || [];
    const selectedWarehouse = warehouses.find(w => w.id === selectedWarehouseId);

    const handleBack = () => {
      setShowTableModal(false);
      setRealUploadedFile(null);
      setPreviewColumns([]);
      setPreviewRows([]);
      setInferredTypes({});
    };

    const handleCreate = () => {
      if (!tableNameInput.trim()) return;
      
      const columnsList = previewColumns.map((colName) => ({
        name: colName,
        data_type: inferredTypes[colName] || 'string',
        nullable: true,
      }));

      const formData = new FormData();
      formData.append('table_name', tableNameInput);
      formData.append('description', tableDescriptionInput || '');
      formData.append('columns_json', JSON.stringify(columnsList));
      
      if (realUploadedFile) {
        formData.append('file', realUploadedFile);
      } else {
        const blob = new Blob([MOCK_CSV_CONTENT], { type: 'text/csv' });
        formData.append('file', blob, 'inverter_generation_data_2026-06-15.csv');
      }

      createTableFromFileMutation.mutate(formData);
    };

    const handleResumePreview = () => {
      const rows = parseCSV(MOCK_CSV_CONTENT);
      if (rows.length > 0) {
        const headers = rows[0];
        const dataRows = rows.slice(1);
        setPreviewColumns(headers);
        setPreviewRows(dataRows.slice(0, 50));
        setTableNameInput('inverter_generation_data_2026_06_15');
        
        const types: Record<string, string> = {};
        headers.forEach((header, idx) => {
          const colValues = dataRows.map(r => r[idx]);
          types[header] = inferType(colValues);
        });
        setInferredTypes(types);
      }
    };

    const hasFile = realUploadedFile !== null || previewRows.length > 0;

    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--color-bg, #f8fafc)',
        zIndex: 1000,
        overflow: 'hidden'
      }}>
        {/* Top Header */}
        <header style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 24px',
          borderBottom: '1px solid var(--color-border, #e2e8f0)',
          backgroundColor: '#fff',
          zIndex: 10
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--color-text-subtle, #64748b)' }}>
              <button 
                onClick={handleBack}
                style={{ background: 'none', border: 'none', padding: 0, color: 'var(--color-primary, #0284c7)', cursor: 'pointer', fontWeight: 500 }}
              >
                Add data
              </button>
              <span>&gt;</span>
            </div>
            <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text, #0f172a)', margin: 0 }}>
              Create or modify table from file upload
            </h1>
          </div>

          {/* Warehouse Selector */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowWarehouseDropdown(!showWarehouseDropdown)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border, #cbd5e1)',
                backgroundColor: '#fff',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 500
              }}
            >
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#22c55e',
                display: 'inline-block'
              }} />
              <span>{selectedWarehouse?.name || 'Serverless Starter Warehouse'}</span>
              <ChevronDown size={14} style={{ color: '#64748b' }} />
            </button>
            {showWarehouseDropdown && (
              <div style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: '4px',
                width: '240px',
                backgroundColor: '#fff',
                border: '1px solid var(--color-border, #e2e8f0)',
                borderRadius: '6px',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                zIndex: 20,
                padding: '4px 0'
              }}>
                {warehouses.map((w) => (
                  <button
                    key={w.id}
                    onClick={() => {
                      setSelectedWarehouseId(w.id);
                      setShowWarehouseDropdown(false);
                    }}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      border: 'none',
                      backgroundColor: selectedWarehouseId === w.id ? '#f1f5f9' : 'transparent',
                      textAlign: 'left',
                      cursor: 'pointer',
                      fontSize: '13px'
                    }}
                  >
                    <span style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: w.status?.toUpperCase() === 'RUNNING' ? '#22c55e' : '#cbd5e1',
                      display: 'inline-block'
                    }} />
                    <span>{w.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </header>

        {/* Workspace Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {!hasFile ? (
            /* Upload Empty State */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '960px', margin: '0 auto', width: '100%' }}>
              <div 
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragOver(false);
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleFileUpload(e.dataTransfer.files[0]);
                  }
                }}
                style={{
                  border: isDragOver ? '2px dashed var(--color-primary, #0284c7)' : '2px dashed var(--color-border, #cbd5e1)',
                  borderRadius: '12px',
                  padding: '60px 20px',
                  textAlign: 'center',
                  backgroundColor: isDragOver ? 'rgba(2, 132, 199, 0.02)' : '#fff',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative'
                }}
                onClick={() => {
                  const input = document.getElementById('file-upload-input');
                  if (input) input.click();
                }}
              >
                <input 
                  type="file" 
                  id="file-upload-input" 
                  style={{ display: 'none' }} 
                  accept=".csv,.tsv,.tab,.json,.jsonl"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileUpload(e.target.files[0]);
                    }
                  }}
                />
                <div style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(2, 132, 199, 0.05)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px auto',
                  color: 'var(--color-primary, #0284c7)'
                }}>
                  <Upload size={32} />
                </div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-text, #0f172a)', marginBottom: '8px' }}>
                  Drop one or more files here, or <span style={{ color: 'var(--color-primary, #0284c7)', textDecoration: 'underline' }}>browse</span>
                </h3>
                <p style={{ fontSize: '13px', color: '#64748b', margin: '0 0 16px 0' }}>
                  Upload up to 10 files (max total upload size 2GB)
                </p>
                <p style={{ fontSize: '11px', color: '#94a3b8', margin: '0 0 6px 0', fontWeight: 500 }}>
                  Requires a SQL warehouse or a cluster with Databricks Runtime 12.2 and above
                </p>
                <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0, maxWidth: '600px', marginLeft: 'auto', marginRight: 'auto', lineHeight: '1.4' }}>
                  Supported file formats: .csv, .tsv, .tab, .json, .jsonl, .avro, .parquet, .txt, .xml, .xlsx, .xls, or .xlsm
                </p>
              </div>

              {/* Resume Preview Banner */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 20px',
                borderRadius: '8px',
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: 'rgba(2, 132, 199, 0.1)',
                    color: 'var(--color-primary, #0284c7)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '13px',
                    fontWeight: 'bold'
                  }}>i</span>
                  <div>
                    <h4 style={{ margin: '0 0 2px 0', fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>Resume preview</h4>
                    <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>
                      A past upload <strong>inverter_generation_data_2026-06-15.csv</strong> was found. This upload is valid for 23 hours. Do you want to resume previewing this upload?
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleResumePreview}
                  style={{
                    padding: '6px 14px',
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    backgroundColor: '#fff',
                    color: '#334155',
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontWeight: 600,
                    transition: 'all 0.15s ease'
                  }}
                >
                  Resume preview
                </button>
              </div>

              {/* Volume text */}
              <p style={{ fontSize: '11px', color: '#94a3b8', textAlign: 'center', marginTop: '10px' }}>
                For larger files, for other file formats, or for uploading files to a non-tabular dataset without creating a table, <a href="#" style={{ color: 'var(--color-primary, #0284c7)' }}>upload to a Volume in Unity Catalog</a>.
              </p>
            </div>
          ) : (
            /* File Uploaded - Preview Grid State */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%' }}>
              {/* File details bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: '#f1f5f9',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  color: '#334155',
                  border: '1px solid #e2e8f0'
                }}>
                  <span>{realUploadedFile?.name || 'inverter_generation_data_2026-06-15.csv'} uploaded</span>
                  <span style={{ color: '#94a3b8', fontSize: '11px' }}>({realUploadedFile ? (realUploadedFile.size / (1024 * 1024)).toFixed(2) + 'MB' : '7.25MB'})</span>
                  <button 
                    onClick={handleBack} 
                    style={{ background: 'none', border: 'none', padding: 0, display: 'flex', alignItems: 'center', cursor: 'pointer', color: '#64748b', marginLeft: '4px' }}
                  >
                    <X size={14} />
                  </button>
                </div>

                <select
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border, #cbd5e1)',
                    backgroundColor: '#fff',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer'
                  }}
                >
                  <option>Create new table</option>
                </select>
              </div>

              {/* Form and Controls row */}
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'flex-end',
                gap: '16px',
                backgroundColor: '#fff',
                padding: '16px 20px',
                borderRadius: '8px',
                border: '1px solid var(--color-border, #e2e8f0)'
              }}>
                {/* Preview mode toggle */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Preview mode</span>
                  <div style={{ display: 'flex', border: '1px solid #cbd5e1', borderRadius: '6px', overflow: 'hidden' }}>
                    <button
                      onClick={() => setPreviewMode('table')}
                      style={{
                        padding: '6px 10px',
                        backgroundColor: previewMode === 'table' ? '#f1f5f9' : '#fff',
                        border: 'none',
                        cursor: 'pointer',
                        color: previewMode === 'table' ? 'var(--color-primary, #0284c7)' : '#64748b',
                        display: 'flex',
                        alignItems: 'center'
                      }}
                    >
                      <Table2 size={16} />
                    </button>
                    <button
                      onClick={() => setPreviewMode('json')}
                      style={{
                        padding: '6px 10px',
                        backgroundColor: previewMode === 'json' ? '#f1f5f9' : '#fff',
                        border: 'none',
                        cursor: 'pointer',
                        color: previewMode === 'json' ? 'var(--color-primary, #0284c7)' : '#64748b',
                        display: 'flex',
                        alignItems: 'center'
                      }}
                    >
                      <Braces size={16} />
                    </button>
                  </div>
                </div>

                {/* Catalog select */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', minWidth: '180px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Catalog</span>
                  <select
                    value={selectedCatalogName}
                    onChange={(e) => {
                      const catName = e.target.value;
                      setSelectedCatalogName(catName);
                      const cat = (catalogsQuery.data || []).find(c => c.name === catName);
                      if (cat && cat.schemas.length > 0) {
                        setSelectedSchemaName(cat.schemas[0].name);
                      } else {
                        setSelectedSchemaName('');
                      }
                    }}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--color-border, #cbd5e1)',
                      backgroundColor: '#fff',
                      fontSize: '13px',
                      outline: 'none'
                    }}
                  >
                    {(catalogsQuery.data || []).map(c => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>

                {/* Schema select */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', minWidth: '180px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Schema</span>
                  <select
                    value={selectedSchemaName}
                    onChange={(e) => setSelectedSchemaName(e.target.value)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--color-border, #cbd5e1)',
                      backgroundColor: '#fff',
                      fontSize: '13px',
                      outline: 'none'
                    }}
                  >
                    {availableSchemas.map(s => (
                      <option key={s.id} value={s.name}>{s.name}</option>
                    ))}
                  </select>
                </div>

                {/* Table Name */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', minWidth: '240px', flex: 1 }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Table name</span>
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <span style={{ position: 'absolute', left: '10px', color: '#94a3b8' }}><Table2 size={14} /></span>
                    <input
                      type="text"
                      value={tableNameInput}
                      onChange={(e) => setTableNameInput(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
                      placeholder="Table name"
                      style={{
                        padding: '6px 12px 6px 32px',
                        width: '100%',
                        borderRadius: '6px',
                        border: '1px solid var(--color-border, #cbd5e1)',
                        backgroundColor: '#fff',
                        fontSize: '13px',
                        outline: 'none'
                      }}
                    />
                  </div>
                </div>

                {/* Advanced Attributes toggle */}
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-primary, #0284c7)',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    paddingBottom: '8px'
                  }}
                >
                  Advanced attributes
                </button>

                {/* Right summary text */}
                <div style={{ marginLeft: 'auto', fontSize: '12px', color: '#64748b', paddingBottom: '8px' }}>
                  Previewing {previewRows.length} rows, {previewColumns.length} columns
                </div>
              </div>

              {/* Advanced Fields container if toggled */}
              {showAdvanced && (
                <div style={{
                  backgroundColor: '#fff',
                  padding: '16px 20px',
                  borderRadius: '8px',
                  border: '1px solid var(--color-border, #e2e8f0)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Description</span>
                    <input
                      type="text"
                      value={tableDescriptionInput}
                      onChange={(e) => setTableDescriptionInput(e.target.value)}
                      placeholder="Provide optional description for the governing table metadata"
                      style={{
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--color-border, #cbd5e1)',
                        fontSize: '13px',
                        outline: 'none'
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Preview mode Table or JSON */}
              {previewMode === 'table' ? (
                /* Tabular Preview */
                <div style={{
                  border: '1px solid var(--color-border, #e2e8f0)',
                  borderRadius: '8px',
                  overflow: 'hidden',
                  backgroundColor: '#fff'
                }}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #cbd5e1' }}>
                          {previewColumns.map((colName) => {
                            const inferredType = inferredTypes[colName] || 'string';
                            const isDropdownOpen = activeHeaderDropdown === colName;

                            return (
                              <th 
                                key={colName} 
                                style={{
                                  padding: '10px 16px',
                                  color: '#334155',
                                  fontWeight: 600,
                                  borderRight: '1px solid #e2e8f0',
                                  position: 'relative'
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setActiveHeaderDropdown(isDropdownOpen ? null : colName);
                                    }}
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '4px',
                                      background: 'none',
                                      border: 'none',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      cursor: 'pointer',
                                      fontSize: '12px',
                                      color: 'var(--color-text)'
                                    }}
                                    className="header-type-btn"
                                  >
                                    {getTypeIcon(inferredType)}
                                    <span style={{ fontWeight: 600 }}>{colName}</span>
                                    <ChevronDown size={12} style={{ color: '#94a3b8' }} />
                                  </button>
                                </div>

                                {/* Custom Datatype Dropdown */}
                                {isDropdownOpen && (
                                  <div style={{
                                    position: 'absolute',
                                    top: '100%',
                                    left: '16px',
                                    marginTop: '4px',
                                    width: '140px',
                                    backgroundColor: '#fff',
                                    border: '1px solid #cbd5e1',
                                    borderRadius: '6px',
                                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                                    zIndex: 30,
                                    padding: '4px 0'
                                  }}>
                                    {['string','int32','int64','float32','float64','bool','timestamp','date','decimal','binary','json'].map((t) => (
                                      <button
                                        key={t}
                                        onClick={() => {
                                          setInferredTypes({ ...inferredTypes, [colName]: t });
                                          setActiveHeaderDropdown(null);
                                        }}
                                        style={{
                                          width: '100%',
                                          padding: '6px 12px',
                                          border: 'none',
                                          backgroundColor: inferredType === t ? '#f1f5f9' : 'transparent',
                                          textAlign: 'left',
                                          cursor: 'pointer',
                                          fontSize: '12px',
                                          color: '#334155',
                                          display: 'flex',
                                          alignItems: 'center',
                                          gap: '6px'
                                        }}
                                      >
                                        {getTypeIcon(t)}
                                        <span>{t}</span>
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody>
                        {previewRows.map((row, rIdx) => (
                          <tr key={rIdx} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: rIdx % 2 === 0 ? '#fff' : '#f8fafc' }}>
                            {previewColumns.map((colName, cIdx) => (
                              <td 
                                key={cIdx} 
                                style={{
                                  padding: '8px 16px',
                                  color: '#475569',
                                  borderRight: '1px solid #e2e8f0',
                                  fontFamily: 'monospace',
                                  fontSize: '12px'
                                }}
                              >
                                {row[cIdx] === null || row[cIdx] === undefined || row[cIdx] === '' ? (
                                  <span style={{ color: '#cbd5e1', fontStyle: 'italic' }}>null</span>
                                ) : (
                                  row[cIdx]
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                /* JSON Schema Preview */
                <pre style={{
                  backgroundColor: '#0f172a',
                  color: '#38bdf8',
                  padding: '20px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  overflowX: 'auto',
                  border: '1px solid #1e293b'
                }}>
                  {JSON.stringify(
                    previewColumns.map((c) => ({
                      name: c,
                      type: inferredTypes[c] || 'string',
                      nullable: true
                    })),
                    null,
                    2
                  )}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Bottom Footer Actions */}
        <footer style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 24px',
          borderTop: '1px solid var(--color-border, #e2e8f0)',
          backgroundColor: '#fff'
        }}>
          <button
            onClick={handleBack}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-primary, #0284c7)',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          
          <button
            onClick={handleCreate}
            disabled={createTableFromFileMutation.isPending || !tableNameInput.trim() || !hasFile}
            className="btn-primary"
            style={{
              padding: '8px 20px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              opacity: (!tableNameInput.trim() || !hasFile) ? 0.6 : 1
            }}
          >
            {createTableFromFileMutation.isPending && <Loader2 size={14} className="spin" />}
            Create table
          </button>
        </footer>
      </div>
    );
  };

  const renderPendingAssets = (assets: PendingCatalogAsset[]) => assets.map((asset) => {
    const icon = asset.kind === 'table'
      ? <Table2 size={10} />
      : asset.kind === 'volume'
        ? <Folder size={10} />
        : asset.kind === 'notebook'
          ? <FileCode size={10} />
          : <SlidersHorizontal size={10} />;

    return (
      <div
        key={asset.id}
        className={cx('uc-tree-row', 'is-pending', asset.status === 'failed' && 'is-failed')}
        title={asset.error || `${asset.name} is being created`}
      >
        <span style={{ width: '12px' }} />
        <span className={'uc-tree-row-icon'}>{asset.status === 'creating' ? <Loader2 size={10} className={'spin'} /> : icon}</span>
        <span className={'uc-tree-row-label'}>{asset.name}</span>
        <span className={'uc-pending-status'}>{asset.status === 'creating' ? 'Creating' : 'Failed'}</span>
        {asset.status === 'failed' && (
          <button
            type={'button'}
            className={'uc-pending-dismiss'}
            aria-label={`Dismiss failed creation for ${asset.name}`}
            onClick={() => setPendingCatalogAssets((current) => current.filter((item) => item.id !== asset.id))}
          >
            <X size={10} />
          </button>
        )}
      </div>
    );
  });

  if (showTableModal) {
    return renderCreateTableFromFileFlow();
  }

  return (
    <div className="uc-shell">
      <div className="uc-workspace" style={{ gridTemplateColumns: isSidebarCollapsed ? '1fr' : '280px minmax(0, 1fr)' }}>
        {/* Left Explorer Sidebar */}
        {!isSidebarCollapsed && (
          <aside className="uc-sidebar">
            <div className="uc-sidebar-header">
              <div className="uc-sidebar-title-row">
                <span className="uc-sidebar-title">Catalog</span>
                <div className="uc-sidebar-actions">
                  <button
                    className="uc-icon-btn"
                    title="Collapse Catalog Sidebar"
                    onClick={toggleSidebarCollapse}
                  >
                    <PanelLeftClose size={14} />
                  </button>
                  <button className="uc-icon-btn" title="Refetch Schema" onClick={() => catalogsQuery.refetch()}>
                    <RefreshCcw size={14} />
                  </button>
                <button
                  ref={settingsBtnRef}
                  className="uc-icon-btn"
                  title="Connection Settings"
                  onClick={() => { setShowSettingsDropdown((v) => !v); setShowPlusDropdown(false); }}
                >
                  <Settings size={14} />
                </button>

                <button
                  ref={plusBtnRef}
                  className="uc-icon-btn"
                  title="Add"
                  onClick={() => { setShowPlusDropdown((v) => !v); setShowSettingsDropdown(false); }}
                >
                  <Plus size={14} />
                </button>

              </div>
            </div>
          </div>

          {/* Search Row */}
          <div className="uc-sidebar-search-row">
            <input 
              type="text" 
              placeholder="Type to search..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            <button className="uc-search-filter-btn">
              <SlidersHorizontal size={14} />
            </button>
          </div>

          {/* Collapsible tree explorer */}
          <div className="uc-sidebar-tree">
            {filteredTreeCatalogs.map((catalog) => {
              const catalogOpen = !!expandedCatalogs[catalog.name];
              const isCatalogSelected = selection?.kind === 'catalog' && selection.catalog === catalog.name;
              
              return (
                <div key={catalog.id} className="uc-tree-group">
                  <button 
                    className={cx('uc-tree-row', isCatalogSelected && 'is-selected')}
                    onClick={() => {
                      setExpandedCatalogs(prev => ({ ...prev, [catalog.name]: !catalogOpen }));
                      selectAndNavigate({ kind: 'catalog', catalog: catalog.name });
                    }}
                  >
                    <span className="uc-tree-row-chevron">
                      {catalogOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    </span>
                    <span className="uc-tree-row-icon">
                      <Database size={12} />
                    </span>
                    <span className="uc-tree-row-label">{catalog.name}</span>
                  </button>

                  {catalogOpen && (
                    <div className="uc-tree-indent">
                      {catalog.schemas.map((schema) => {
                        const schemaKey = `${catalog.name}.${schema.name}`;
                        const schemaOpen = !!expandedSchemas[schemaKey];
                        const isSchemaSelected = selection?.kind === 'schema' && selection.catalog === catalog.name && selection.schema === schema.name;
                        const tables = schemaTablesCache[schemaKey] || [];
                        const volumes = schemaVolumesCache[schemaKey] || [];
                        const notebooks = schemaNotebooksCache[schemaKey] || [];
                        const dashboards = schemaDashboardsCache[schemaKey] || [];
                        const tools = schemaToolsCache[schemaKey] || [];
                        const queries = schemaQueriesCache[schemaKey] || [];
                        const schemaPendingAssets = pendingCatalogAssets.filter((asset) => asset.catalog === catalog.name && asset.schema === schema.name);
                        const pendingTables = schemaPendingAssets.filter((asset) => asset.kind === 'table');
                        const pendingVolumes = schemaPendingAssets.filter((asset) => asset.kind === 'volume');
                        const pendingNotebooks = schemaPendingAssets.filter((asset) => asset.kind === 'notebook');
                        const pendingDashboards = schemaPendingAssets.filter((asset) => asset.kind === 'dashboard');
                        
                        const hasTables = tables.length + pendingTables.length > 0;
                        const hasVolumes = volumes.length + pendingVolumes.length > 0;
                        const hasNotebooks = notebooks.length + pendingNotebooks.length > 0;
                        const hasDashboards = dashboards.length + pendingDashboards.length > 0;
                        const hasTools = tools.length > 0;
                        const hasQueries = queries.length > 0;
                        const typesCount = (hasTables ? 1 : 0) + (hasVolumes ? 1 : 0) + (hasNotebooks ? 1 : 0) + (hasDashboards ? 1 : 0) + (hasTools ? 1 : 0) + (hasQueries ? 1 : 0);
                        const showGroups = typesCount > 1;

                        return (
                          <div key={schema.id} className="uc-tree-group">
                            <button 
                              className={cx('uc-tree-row', isSchemaSelected && 'is-selected')}
                              onClick={() => {
                                setExpandedSchemas(prev => ({ ...prev, [schemaKey]: !schemaOpen }));
                                selectAndNavigate({ kind: 'schema', catalog: catalog.name, schema: schema.name });
                              }}
                            >
                              <span className="uc-tree-row-chevron">
                                {schemaOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                              </span>
                              <span className="uc-tree-row-icon">
                                <Folder size={11} />
                              </span>
                              <span className="uc-tree-row-label">{schema.name}</span>
                            </button>

                            {schemaOpen && (
                              <div className="uc-tree-indent">
                                {showGroups ? (
                                  <>
                                    {/* Tables Group */}
                                    {hasTables && (
                                      <div className="uc-tree-group">
                                        {(() => {
                                          const tablesGroupOpen = expandedGroups[`${schemaKey}-tables`] !== false;
                                          return (
                                            <>
                                              <button 
                                                className="uc-tree-row"
                                                onClick={() => {
                                                  setExpandedGroups(prev => ({ ...prev, [`${schemaKey}-tables`]: !tablesGroupOpen }));
                                                }}
                                              >
                                                <span className="uc-tree-row-chevron">
                                                  {tablesGroupOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                                </span>
                                                <span className="uc-tree-row-label">Tables ({tables.length + pendingTables.length})</span>
                                              </button>
                                              {tablesGroupOpen && (
                                                <div className="uc-tree-indent">
                                                  {renderPendingAssets(pendingTables)}
                                                  {tables.map((table) => {
                                                    const isTableSelected = selection?.kind === 'table' && selection.catalog === catalog.name && selection.schema === schema.name && selection.table === table.name;
                                                    return (
                                                      <button 
                                                        key={table.id}
                                                        className={cx('uc-tree-row', isTableSelected && 'is-selected')}
                                                        onClick={() => {
                                                          selectAndNavigate({ kind: 'table', catalog: catalog.name, schema: schema.name, table: table.name });
                                                        }}
                                                      >
                                                        <span style={{ width: '12px' }} />
                                                        <span className="uc-tree-row-icon">
                                                          <Table2 size={10} />
                                                        </span>
                                                        <span className="uc-tree-row-label">{table.name}</span>
                                                      </button>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </>
                                          );
                                        })()}
                                      </div>
                                    )}

                                    {/* Volumes Group */}
                                    {hasVolumes && (
                                      <div className="uc-tree-group">
                                        {(() => {
                                          const volumesGroupOpen = expandedGroups[`${schemaKey}-volumes`] !== false;
                                          return (
                                            <>
                                              <button 
                                                className="uc-tree-row"
                                                onClick={() => {
                                                  setExpandedGroups(prev => ({ ...prev, [`${schemaKey}-volumes`]: !volumesGroupOpen }));
                                                }}
                                              >
                                                <span className="uc-tree-row-chevron">
                                                  {volumesGroupOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                                </span>
                                                <span className="uc-tree-row-label">Volumes ({volumes.length + pendingVolumes.length})</span>
                                              </button>
                                              {volumesGroupOpen && (
                                                <div className="uc-tree-indent">
                                                  {renderPendingAssets(pendingVolumes)}
                                                  {volumes.map((vol) => {
                                                    const isVolSelected = selection?.kind === 'volume' && selection.catalog === catalog.name && selection.schema === schema.name && selection.volume === vol.name;
                                                    return (
                                                      <button 
                                                        key={`vol-${vol.id}`}
                                                        className={cx('uc-tree-row', isVolSelected && 'is-selected')}
                                                        onClick={() => {
                                                          selectAndNavigate({ kind: 'volume', catalog: catalog.name, schema: schema.name, volume: vol.name });
                                                        }}
                                                      >
                                                        <span style={{ width: '12px' }} />
                                                        <span className="uc-tree-row-icon">
                                                          <Folder size={10} style={{ color: 'var(--color-primary)' }} />
                                                        </span>
                                                        <span className="uc-tree-row-label">{vol.name}</span>
                                                      </button>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </>
                                          );
                                        })()}
                                      </div>
                                    )}

                                    {/* Notebooks Group */}
                                    {hasNotebooks && (
                                      <div className="uc-tree-group">
                                        {(() => {
                                          const notebooksGroupOpen = expandedGroups[`${schemaKey}-notebooks`] !== false;
                                          return (
                                            <>
                                              <button 
                                                className="uc-tree-row"
                                                onClick={() => {
                                                  setExpandedGroups(prev => ({ ...prev, [`${schemaKey}-notebooks`]: !notebooksGroupOpen }));
                                                }}
                                              >
                                                <span className="uc-tree-row-chevron">
                                                  {notebooksGroupOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                                </span>
                                                <span className="uc-tree-row-label">Notebooks ({notebooks.length + pendingNotebooks.length})</span>
                                              </button>
                                              {notebooksGroupOpen && (
                                                <div className="uc-tree-indent">
                                                  {renderPendingAssets(pendingNotebooks)}
                                                  {notebooks.map((nb) => {
                                                    const isNbSelected = selection?.kind === 'notebook' && selection.catalog === catalog.name && selection.schema === schema.name && selection.notebook === nb.name;
                                                    return (
                                                      <button
                                                        key={`nb-${nb.id}`}
                                                        className={cx('uc-tree-row', isNbSelected && 'is-selected')}
                                                        onClick={() => {
                                                          selectAndNavigate({ kind: 'notebook', catalog: catalog.name, schema: schema.name, notebook: nb.name, blob_path: nb.blob_path });
                                                        }}
                                                      >
                                                        <span style={{ width: '12px' }} />
                                                        <span className="uc-tree-row-icon">
                                                          <FileCode size={10} />
                                                        </span>
                                                        <span className="uc-tree-row-label">{nb.name}</span>
                                                      </button>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </>
                                          );
                                        })()}
                                      </div>
                                    )}

                                    {/* Dashboards Group */}
                                    {hasDashboards && (
                                      <div className="uc-tree-group">
                                        {(() => {
                                          const dashboardsGroupOpen = expandedGroups[`${schemaKey}-dashboards`] !== false;
                                          return (
                                            <>
                                              <button 
                                                className="uc-tree-row"
                                                onClick={() => {
                                                  setExpandedGroups(prev => ({ ...prev, [`${schemaKey}-dashboards`]: !dashboardsGroupOpen }));
                                                }}
                                              >
                                                <span className="uc-tree-row-chevron">
                                                  {dashboardsGroupOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                                </span>
                                                <span className="uc-tree-row-label">Dashboards ({dashboards.length + pendingDashboards.length})</span>
                                              </button>
                                              {dashboardsGroupOpen && (
                                                <div className="uc-tree-indent">
                                                  {renderPendingAssets(pendingDashboards)}
                                                  {dashboards.map((dbItem) => {
                                                    const isDbSelected = selection?.kind === 'dashboard' && selection.catalog === catalog.name && selection.schema === schema.name && selection.dashboard === dbItem.name;
                                                    return (
                                                      <button
                                                        key={`db-${dbItem.id}`}
                                                        className={cx('uc-tree-row', isDbSelected && 'is-selected')}
                                                        onClick={() => {
                                                          selectAndNavigate({ kind: 'dashboard', catalog: catalog.name, schema: schema.name, dashboard: dbItem.name, dashboard_id: dbItem.dashboard_id ?? undefined });
                                                        }}
                                                      >
                                                        <span style={{ width: '12px' }} />
                                                        <span className="uc-tree-row-icon">
                                                          <SlidersHorizontal size={10} />
                                                        </span>
                                                        <span className="uc-tree-row-label">{dbItem.name}</span>
                                                      </button>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </>
                                          );
                                        })()}
                                      </div>
                                    )}

                                    {/* Tools Group */}
                                    {hasTools && (
                                      <div className="uc-tree-group">
                                        {(() => {
                                          const toolsGroupOpen = expandedGroups[`${schemaKey}-tools`] !== false;
                                          return (
                                            <>
                                              <button 
                                                className="uc-tree-row"
                                                onClick={() => {
                                                  setExpandedGroups(prev => ({ ...prev, [`${schemaKey}-tools`]: !toolsGroupOpen }));
                                                }}
                                              >
                                                <span className="uc-tree-row-chevron">
                                                  {toolsGroupOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                                </span>
                                                <span className="uc-tree-row-label">Tools ({tools.length})</span>
                                              </button>
                                              {toolsGroupOpen && (
                                                <div className="uc-tree-indent">
                                                  {tools.map((toolItem) => {
                                                    const isToolSelected = selection?.kind === 'tool' && selection.catalog === catalog.name && selection.schema === schema.name && selection.tool === toolItem.name;
                                                    return (
                                                      <button
                                                        key={`tool-${toolItem.id}`}
                                                        className={cx('uc-tree-row', isToolSelected && 'is-selected')}
                                                        onClick={() => {
                                                          selectAndNavigate({ kind: 'tool', catalog: catalog.name, schema: schema.name, tool: toolItem.name, tool_id: toolItem.id });
                                                        }}
                                                      >
                                                        <span style={{ width: '12px' }} />
                                                        <span className="uc-tree-row-icon">
                                                          <Wrench size={10} />
                                                        </span>
                                                        <span className="uc-tree-row-label">{toolItem.name}</span>
                                                      </button>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </>
                                          );
                                        })()}
                                      </div>
                                    )}

                                    {/* Queries Group */}
                                    {hasQueries && (
                                      <div className="uc-tree-group">
                                        {(() => {
                                          const queriesGroupOpen = expandedGroups[`${schemaKey}-queries`] !== false;
                                          return (
                                            <>
                                              <button 
                                                className="uc-tree-row"
                                                onClick={() => {
                                                  setExpandedGroups(prev => ({ ...prev, [`${schemaKey}-queries`]: !queriesGroupOpen }));
                                                }}
                                              >
                                                <span className="uc-tree-row-chevron">
                                                  {queriesGroupOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                                </span>
                                                <span className="uc-tree-row-label">Queries ({queries.length})</span>
                                              </button>
                                              {queriesGroupOpen && (
                                                <div className="uc-tree-indent">
                                                  {queries.map((qItem) => {
                                                    const isQSelected = selection?.kind === 'query' && selection.catalog === catalog.name && selection.schema === schema.name && selection.query === qItem.name;
                                                    return (
                                                      <button
                                                        key={`q-${qItem.id}`}
                                                        className={cx('uc-tree-row', isQSelected && 'is-selected')}
                                                        onClick={() => {
                                                          selectAndNavigate({ kind: 'query', catalog: catalog.name, schema: schema.name, query: qItem.name });
                                                        }}
                                                      >
                                                        <span style={{ width: '12px' }} />
                                                        <span className="uc-tree-row-icon">
                                                          <FileCode size={10} />
                                                        </span>
                                                        <span className="uc-tree-row-label">{qItem.name}</span>
                                                      </button>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </>
                                          );
                                        })()}
                                      </div>
                                    )}
                                  </>
                                ) : (
                                  <>
                                    {renderPendingAssets(schemaPendingAssets)}
                                    {tables.map((table) => {
                                      const isTableSelected = selection?.kind === 'table' && selection.catalog === catalog.name && selection.schema === schema.name && selection.table === table.name;
                                      
                                      return (
                                        <button 
                                          key={table.id}
                                          className={cx('uc-tree-row', isTableSelected && 'is-selected')}
                                          onClick={() => {
                                            selectAndNavigate({ kind: 'table', catalog: catalog.name, schema: schema.name, table: table.name });
                                          }}
                                        >
                                          <span style={{ width: '12px' }} />
                                          <span className="uc-tree-row-icon">
                                            <Table2 size={10} />
                                          </span>
                                          <span className="uc-tree-row-label">{table.name}</span>
                                        </button>
                                      );
                                    })}
                                    {volumes.map((vol) => {
                                      const isVolSelected = selection?.kind === 'volume' && selection.catalog === catalog.name && selection.schema === schema.name && selection.volume === vol.name;
                                      
                                      return (
                                        <button 
                                          key={`vol-${vol.id}`}
                                          className={cx('uc-tree-row', isVolSelected && 'is-selected')}
                                          onClick={() => {
                                            selectAndNavigate({ kind: 'volume', catalog: catalog.name, schema: schema.name, volume: vol.name });
                                          }}
                                        >
                                          <span style={{ width: '12px' }} />
                                          <span className="uc-tree-row-icon">
                                            <Folder size={10} style={{ color: 'var(--color-primary)' }} />
                                          </span>
                                          <span className="uc-tree-row-label">{vol.name}</span>
                                        </button>
                                      );
                                    })}
                                    {notebooks.map((nb) => {
                                      const isNbSelected = selection?.kind === 'notebook' && selection.catalog === catalog.name && selection.schema === schema.name && selection.notebook === nb.name;

                                      return (
                                        <button
                                          key={`nb-${nb.id}`}
                                          className={cx('uc-tree-row', isNbSelected && 'is-selected')}
                                          onClick={() => {
                                            selectAndNavigate({ kind: 'notebook', catalog: catalog.name, schema: schema.name, notebook: nb.name, blob_path: nb.blob_path });
                                          }}
                                        >
                                          <span style={{ width: '12px' }} />
                                          <span className="uc-tree-row-icon">
                                            <FileCode size={10} style={{ color: 'var(--color-primary)' }} />
                                          </span>
                                          <span className="uc-tree-row-label">{nb.name}</span>
                                        </button>
                                      );
                                    })}
                                    {dashboards.map((dbItem) => {
                                       const isDbSelected = selection?.kind === 'dashboard' && selection.catalog === catalog.name && selection.schema === schema.name && selection.dashboard === dbItem.name;

                                       return (
                                         <button
                                           key={`db-${dbItem.id}`}
                                           className={cx('uc-tree-row', isDbSelected && 'is-selected')}
                                           onClick={() => {
                                             selectAndNavigate({ kind: 'dashboard', catalog: catalog.name, schema: schema.name, dashboard: dbItem.name, dashboard_id: dbItem.dashboard_id ?? undefined });
                                           }}
                                         >
                                           <span style={{ width: '12px' }} />
                                           <span className="uc-tree-row-icon">
                                             <SlidersHorizontal size={10} style={{ color: 'var(--color-primary)' }} />
                                           </span>
                                           <span className="uc-tree-row-label">{dbItem.name}</span>
                                         </button>
                                       );
                                     })}
                                     {queries.map((qItem) => {
                                       const isQSelected = selection?.kind === 'query' && selection.catalog === catalog.name && selection.schema === schema.name && selection.query === qItem.name;

                                       return (
                                         <button
                                           key={`q-${qItem.id}`}
                                           className={cx('uc-tree-row', isQSelected && 'is-selected')}
                                           onClick={() => {
                                             selectAndNavigate({ kind: 'query', catalog: catalog.name, schema: schema.name, query: qItem.name });
                                           }}
                                         >
                                           <span style={{ width: '12px' }} />
                                           <span className="uc-tree-row-icon">
                                             <FileCode size={10} style={{ color: 'var(--color-primary)' }} />
                                           </span>
                                           <span className="uc-tree-row-label">{qItem.name}</span>
                                         </button>
                                       );
                                     })}
                                     {tables.length === 0 && volumes.length === 0 && notebooks.length === 0 && dashboards.length === 0 && tools.length === 0 && queries.length === 0 && schemaPendingAssets.length === 0 && (
                                       <div style={{ fontSize: '10px', color: 'var(--color-text-subtle)', padding: '2px 8px 2px 28px' }}>
                                         {loadingSchemaTables[schemaKey] || loadingSchemaNotebooks[schemaKey] || loadingSchemaDashboards[schemaKey] || loadingSchemaQueries[schemaKey] ? 'Loading...' : 'No assets registered'}
                                       </div>
                                     )}
                                   </>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
            {filteredTreeCatalogs.length === 0 && !catalogsQuery.isLoading && (
              <div style={{ padding: '16px', fontSize: '12px', color: 'var(--color-text-muted)', textAlign: 'center' }}>
                No catalogs registered yet.
              </div>
            )}
          </div>
        </aside>
        )}

        {/* Right Main Content area */}
        <main className="uc-main" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="uc-main-tab-strip">
            {isSidebarCollapsed && (
              <button
                type="button"
                className="uc-icon-btn"
                title="Expand Catalog Sidebar"
                onClick={toggleSidebarCollapse}
                style={{ marginRight: 4, flexShrink: 0 }}
              >
                <PanelLeftOpen size={16} />
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setMainTabId('details');
                setSelection(detailsSelection);
                if (!detailsSelection || detailsSelection.kind === 'root') {
                  navigate('/data-catalog');
                } else if (detailsSelection.kind === 'catalog') {
                  navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}`);
                } else if (detailsSelection.kind === 'schema') {
                  navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}`);
                } else if (detailsSelection.kind === 'table') {
                  navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}/table/${encodeURIComponent(detailsSelection.table)}`);
                } else if (detailsSelection.kind === 'volume') {
                  navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}/volume/${encodeURIComponent(detailsSelection.volume)}`);
                } else if (detailsSelection.kind === 'tool') {
                  const q = (detailsSelection as any).tool_id ? `?tool_id=${encodeURIComponent((detailsSelection as any).tool_id)}` : '';
                  navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}/tool/${encodeURIComponent((detailsSelection as any).tool)}${q}`);
                } else if (detailsSelection.kind === 'query') {
                  navigate(`/data-catalog/${encodeURIComponent(detailsSelection.catalog)}/${encodeURIComponent(detailsSelection.schema)}?kind=query&query=${encodeURIComponent(detailsSelection.query)}`);
                } else {
                  navigate('/data-catalog');
                }
              }}
              className={cx('uc-main-tab', mainTabId === 'details' && 'is-active')}
              title="Details overview"
            >
              <Layers size={13} color="#6B7280" />
              <span className="uc-main-tab-title">Details</span>
            </button>

            {openPanels.map((panel) => {
              const isNotebook = panel.selection.kind === 'notebook';
              const isDashboard = panel.selection.kind === 'dashboard';
              const isVolume = panel.selection.kind === 'volume';
              const isActive = mainTabId === panel.id;

              return (
                <div
                  key={panel.id}
                  className={cx('uc-main-tab', isActive && 'is-active')}
                  onClick={() => {
                    setMainTabId(panel.id);
                    setSelection(panel.selection);
                    if (panel.selection.kind === 'notebook') {
                      const path = panel.selection.blob_path ? `?path=${encodeURIComponent(panel.selection.blob_path)}` : '';
                      const nbName = panel.selection.notebook.endsWith('.ipynb') ? panel.selection.notebook.slice(0, -6) : panel.selection.notebook;
                      navigate(`/data-catalog/${encodeURIComponent(panel.selection.catalog)}/${encodeURIComponent(panel.selection.schema)}/notebook/${encodeURIComponent(nbName)}${path}`);
                    } else if (panel.selection.kind === 'dashboard') {
                      const q = panel.selection.dashboard_id ? `?dashboard_id=${encodeURIComponent(panel.selection.dashboard_id)}` : '';
                      navigate(`/data-catalog/${encodeURIComponent(panel.selection.catalog)}/${encodeURIComponent(panel.selection.schema)}/dashboard/${encodeURIComponent(panel.selection.dashboard)}${q}`);
                    }
                  }}
                  title={panel.label}
                >
                  {isNotebook && <BookOpen size={13} color="#6B7280" />}
                  {isDashboard && <LayoutDashboard size={13} color="#6B7280" />}
                  {isVolume && <HardDrive size={13} color="#6B7280" />}
                  {!isNotebook && !isDashboard && !isVolume && <FileCode size={13} color="#6B7280" />}
                  <span className="uc-main-tab-title">{panel.label}</span>
                  <button
                    type="button"
                    className="uc-main-tab-close"
                    onClick={(e) => {
                      e.stopPropagation();
                      closeOpenPanel(panel.id);
                    }}
                    title="Close tab"
                  >
                    <X size={12} />
                  </button>
                </div>
              );
            })}
          </div>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {renderMainContent()}
          </div>
        </main>
      </div>

      {/* Create Catalog Modal */}
      {showCatalogModal && (
        <Dialog title="Create Catalog" subtitle="Initialize a governed catalog metadata layer." onClose={() => setShowCatalogModal(false)}>
          <div className="uc-form-grid uc-form-grid-large">
            <label className="uc-field">
              <span className="uc-field-label">Catalog Name</span>
              <input 
                className="input-field" 
                value={catalogForm.name} 
                onChange={(e) => setCatalogForm({ ...catalogForm, name: e.target.value })} 
                placeholder="e.g. engineering_catalog"
              />
            </label>
            <label className="uc-field">
              <span className="uc-field-label">Catalog Type</span>
              <select 
                className="input-field" 
                value={catalogForm.catalog_type} 
                onChange={(e) => setCatalogForm({ ...catalogForm, catalog_type: e.target.value as 'postgres' | 'iceberg', connection_id: '', database_name: '' })}
              >
                <option value="iceberg">Iceberg</option>
                <option value="postgres">Postgres</option>
              </select>
            </label>

            {catalogForm.catalog_type === 'postgres' && (
              <>
                <label className="uc-field">
                  <span className="uc-field-label">Connection</span>
                  <select
                    className="input-field"
                    value={catalogForm.connection_id}
                    onChange={(e) => handleCatalogConnectionChange(e.target.value)}
                  >
                    <option value="">Select Connection</option>
                    {postgresConnections.map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>

                {catalogForm.connection_id && (
                  <label className="uc-field">
                    <span className="uc-field-label flex items-center gap-1">
                      Database Name
                      {loadingCatalogDbs && <Loader2 size={12} className="spin" />}
                    </span>
                    <select
                      className="input-field"
                      value={catalogForm.database_name}
                      onChange={(e) => setCatalogForm({ ...catalogForm, database_name: e.target.value })}
                      disabled={loadingCatalogDbs}
                    >
                      <option value="">Select Database</option>
                      {catalogFormDbs.map((db) => (
                        <option key={db.name} value={db.name}>{db.name}</option>
                      ))}
                    </select>
                  </label>
                )}
              </>
            )}

            {catalogForm.catalog_type === 'iceberg' && (
              <label className="uc-field">
                <span className="uc-field-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  Storage Backend
                  <span style={{ fontSize: '10px', color: 'var(--color-text-subtle)', fontWeight: 400 }}>(default for all schemas in this catalog)</span>
                </span>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <select
                    className="input-field"
                    style={{ flex: 1 }}
                    value={catalogForm.storageBackend}
                    onChange={(e) => setCatalogForm({ ...catalogForm, storageBackend: e.target.value })}
                  >
                    <option value="">None</option>
                    {storageBackends.map((b) => (
                      <option key={b.id} value={b.name}>{b.name} ({b.provider})</option>
                    ))}
                  </select>
                  <button type="button" className="uc-icon-btn" style={{ padding: '0 8px', fontSize: '12px' }} onClick={() => setShowStorageModal(true)} title="Add new storage backend">
                    + New
                  </button>
                </div>
              </label>
            )}

            <label className="uc-field">
              <span className="uc-field-label">Description</span>
              <input 
                className="input-field" 
                value={catalogForm.description} 
                onChange={(e) => setCatalogForm({ ...catalogForm, description: e.target.value })} 
                placeholder="Optional description"
              />
            </label>
          </div>

          {catalogBrowseError && (
            <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
              <span>{catalogBrowseError}</span>
            </div>
          )}

          <div className="uc-modal-footer">
            <div className="uc-inline-hint">Create Catalog schema container under Unity Catalog guidelines.</div>
            <button className="btn-primary" onClick={() => createCatalogMutation.mutate()} disabled={createCatalogMutation.isPending}>
              {createCatalogMutation.isPending && <Loader2 size={14} className="spin" />}
              Create Catalog
            </button>
          </div>
        </Dialog>
      )}

      {showSchemaModal && selection?.kind === 'catalog' && (
        <Dialog 
          title={`Create schema in ${selection.catalog}`}
          subtitle="A schema contains tables, views, and volumes."
          onClose={() => { setShowSchemaModal(false); setSchemaForm({ name: '', description: '', storageBackend: '' }); }}
        >
          <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <label className="uc-field">
              <span className="uc-field-label">Name</span>
              <input 
                className="input-field" 
                value={schemaForm.name} 
                onChange={(e) => setSchemaForm({ ...schemaForm, name: e.target.value })} 
                placeholder="e.g. analytics" 
                autoFocus
              />
            </label>

            <label className="uc-field">
              <span className="uc-field-label">Description</span>
              <input 
                className="input-field" 
                value={schemaForm.description} 
                onChange={(e) => setSchemaForm({ ...schemaForm, description: e.target.value })} 
                placeholder="Optional description"
              />
            </label>

            <label className="uc-field">
              <span className="uc-field-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                Storage Override
                <span style={{ fontSize: '10px', color: 'var(--color-text-subtle)', fontWeight: 400 }}>(optional — leave blank to inherit catalog storage)</span>
              </span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <select
                  className="input-field"
                  style={{ flex: 1 }}
                  value={schemaForm.storageBackend}
                  onChange={(e) => setSchemaForm({ ...schemaForm, storageBackend: e.target.value })}
                >
                  <option value="">Inherit from catalog</option>
                  {storageBackends.map((b) => (
                    <option key={b.id} value={b.name}>{b.name} ({b.provider})</option>
                  ))}
                </select>
                <button type="button" className="uc-icon-btn" style={{ padding: '0 8px', fontSize: '12px' }} onClick={() => setShowStorageModal(true)} title="Add new storage backend">
                  + New
                </button>
              </div>
            </label>
          </div>

          {createSchemaMutation.isError && (
            <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
              <span>{(createSchemaMutation.error as any)?.response?.data?.detail || 'Failed to create schema.'}</span>
            </div>
          )}

          <div className="uc-modal-footer">
            <button className="btn-primary" onClick={() => createSchemaMutation.mutate()} disabled={createSchemaMutation.isPending || !schemaForm.name.trim()}>
              {createSchemaMutation.isPending && <Loader2 size={14} className="spin" />}
              Create Schema
            </button>
          </div>
        </Dialog>
      )}

      {showTableModal && selection?.kind === 'schema' && (() => {
        const hasStorageBackend = (() => {
          // Can't know from frontend alone; the user will find out on submit if the schema has no backend
          return true; // Always show Iceberg column builder if user wants
        })();
        const useIceberg = tableColumns.length > 0;

        return (
          <Dialog 
            title={`Create table in ${selection.schema}`}
            subtitle="Define a table — add columns below to create an Iceberg table with blob storage metadata."
            onClose={() => { setShowTableModal(false); setTableForm({ name: '', description: '' }); setTableColumns([]); }}
          >
            <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <label className="uc-field">
                <span className="uc-field-label">Table Name</span>
                <input 
                  className="input-field" 
                  value={tableForm.name} 
                  onChange={(e) => setTableForm({ ...tableForm, name: e.target.value })} 
                  placeholder="e.g. tag_readings_bronze" 
                  autoFocus
                />
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Description</span>
                <input 
                  className="input-field" 
                  value={tableForm.description} 
                  onChange={(e) => setTableForm({ ...tableForm, description: e.target.value })} 
                  placeholder="Optional description"
                />
              </label>

              {/* Column builder */}
              <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text)' }}>
                    Columns {useIceberg && <span style={{ fontSize: '10px', color: 'var(--color-primary)', marginLeft: '4px' }}>• Iceberg mode</span>}
                  </span>
                  <button type="button" className="btn-primary" style={{ padding: '3px 10px', fontSize: '11px' }}
                    onClick={() => setTableColumns([...tableColumns, { name: '', data_type: 'string', nullable: true }])}
                  >
                    + Add Column
                  </button>
                </div>
                {tableColumns.length === 0 && (
                  <div style={{ fontSize: '11px', color: 'var(--color-text-subtle)', fontStyle: 'italic' }}>
                    No columns defined. Add columns to create an Iceberg table with blob storage metadata, or leave empty to register a metadata-only table.
                  </div>
                )}
                {tableColumns.map((col, idx) => (
                  <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 140px 80px 28px', gap: '6px', marginBottom: '6px', alignItems: 'center' }}>
                    <input
                      className="input-field" style={{ padding: '4px 8px', fontSize: '12px' }}
                      placeholder="column name"
                      value={col.name}
                      onChange={(e) => {
                        const cols = [...tableColumns]; cols[idx] = { ...cols[idx], name: e.target.value }; setTableColumns(cols);
                      }}
                    />
                    <select
                      className="input-field" style={{ padding: '4px 8px', fontSize: '12px' }}
                      value={col.data_type}
                      onChange={(e) => {
                        const cols = [...tableColumns]; cols[idx] = { ...cols[idx], data_type: e.target.value }; setTableColumns(cols);
                      }}
                    >
                      {['string','int32','int64','float64','float32','bool','timestamp','date','decimal','binary','json'].map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', cursor: 'pointer' }}>
                      <input type="checkbox" checked={col.nullable} onChange={(e) => {
                        const cols = [...tableColumns]; cols[idx] = { ...cols[idx], nullable: e.target.checked }; setTableColumns(cols);
                      }} />
                      nullable
                    </label>
                    <button type="button" style={{ color: 'var(--color-danger, #ef4444)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px', lineHeight: 1 }}
                      onClick={() => setTableColumns(tableColumns.filter((_, i) => i !== idx))}>×</button>
                  </div>
                ))}
              </div>
            </div>

            {(createTableMutation.isError || createIcebergTableMutation.isError) && (
              <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
                <span>{((createIcebergTableMutation.error || createTableMutation.error) as any)?.response?.data?.detail || 'Failed to create table.'}</span>
              </div>
            )}

            <div className="uc-modal-footer">
              {useIceberg ? (
                <button className="btn-primary" onClick={() => createIcebergTableMutation.mutate()} disabled={createIcebergTableMutation.isPending || !tableForm.name.trim() || tableColumns.some(c => !c.name.trim())}>
                  {createIcebergTableMutation.isPending && <Loader2 size={14} className="spin" />}
                  Create Iceberg Table
                </button>
              ) : (
                <button className="btn-primary" onClick={() => createTableMutation.mutate()} disabled={createTableMutation.isPending || !tableForm.name.trim()}>
                  {createTableMutation.isPending && <Loader2 size={14} className="spin" />}
                  Create Table
                </button>
              )}
            </div>
          </Dialog>
        );
      })()}

      {showVolumeModal && selection?.kind === 'schema' && (
        <Dialog 
          title={`Create volume in ${selection.schema}`}
          subtitle="A volume represents non-tabular storage."
          onClose={() => { setShowVolumeModal(false); setVolumeForm({ name: '', description: '' }); }}
        >
          <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <label className="uc-field">
              <span className="uc-field-label">Name</span>
              <input 
                className="input-field" 
                value={volumeForm.name} 
                onChange={(e) => setVolumeForm({ ...volumeForm, name: e.target.value })} 
                placeholder="e.g. raw_files" 
                autoFocus
              />
            </label>

            <label className="uc-field">
              <span className="uc-field-label">Description</span>
              <input 
                className="input-field" 
                value={volumeForm.description} 
                onChange={(e) => setVolumeForm({ ...volumeForm, description: e.target.value })} 
                placeholder="Optional description"
              />
            </label>
          </div>

          {createVolumeMutation.isError && (
            <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
              <span>{(createVolumeMutation.error as any)?.response?.data?.detail || 'Failed to create volume.'}</span>
            </div>
          )}

          <div className="uc-modal-footer">
            <button className="btn-primary" onClick={() => createVolumeMutation.mutate()} disabled={createVolumeMutation.isPending || !volumeForm.name.trim()}>
              {createVolumeMutation.isPending && <Loader2 size={14} className="spin" />}
              Create Volume
            </button>
          </div>
        </Dialog>
      )}

      {showNbModal && selection?.kind === 'schema' && (
        <Dialog
          title={`Register governed notebook in ${selection.schema}`}
          subtitle="Create and register a new notebook catalog object under this schema namespace."
          onClose={() => { setShowNbModal(false); setNbForm({ name: '', blob_path: '', owner: 'catalog-admin', comment: '' }); }}
        >
          <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <label className="uc-field">
              <span className="uc-field-label">Notebook Name</span>
              <input
                className="input-field"
                value={nbForm.name}
                onChange={(e) => setNbForm({ ...nbForm, name: e.target.value })}
                placeholder="e.g. data_cleanup"
                autoFocus
              />
            </label>

            <label className="uc-field">
              <span className="uc-field-label">Description (Comment)</span>
              <textarea
                className="input-field"
                style={{ minHeight: '80px' }}
                value={nbForm.comment}
                onChange={(e) => setNbForm({ ...nbForm, comment: e.target.value })}
                placeholder="Optional description of the notebook"
              />
            </label>
          </div>

          {registerNotebookMutation.isError && (
            <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
              <span>{(registerNotebookMutation.error as any)?.response?.data?.detail || 'Failed to register notebook.'}</span>
            </div>
          )}

          <div className="uc-modal-footer">
            <button
              className="btn-primary"
              onClick={() => registerNotebookMutation.mutate()}
              disabled={registerNotebookMutation.isPending || !nbForm.name.trim()}
            >
              {registerNotebookMutation.isPending && <Loader2 size={14} className="spin" />}
              Register Notebook
            </button>
          </div>
        </Dialog>
      )}

      {showDashboardModal && selection?.kind === 'schema' && (
        <Dialog
          title={`Register governed dashboard in ${selection.schema}`}
          subtitle="Create and register a new dashboard catalog object under this schema namespace."
          onClose={() => { setShowDashboardModal(false); setDbForm({ name: '', comment: '' }); }}
        >
          <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <label className="uc-field">
              <span className="uc-field-label">Dashboard Name</span>
              <input
                className="input-field"
                value={dbForm.name}
                onChange={(e) => setDbForm({ ...dbForm, name: e.target.value })}
                placeholder="e.g. sales_kpis"
                autoFocus
              />
            </label>

            <label className="uc-field">
              <span className="uc-field-label">Description (Comment)</span>
              <textarea
                className="input-field"
                style={{ minHeight: '80px' }}
                value={dbForm.comment}
                onChange={(e) => setDbForm({ ...dbForm, comment: e.target.value })}
                placeholder="Optional description of the dashboard"
              />
            </label>
          </div>

          {registerDashboardMutation.isError && (
            <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
              <span>{(registerDashboardMutation.error as any)?.response?.data?.detail || 'Failed to register dashboard.'}</span>
            </div>
          )}

          <div className="uc-modal-footer">
            <button
              className="btn-primary"
              onClick={() => registerDashboardMutation.mutate()}
              disabled={registerDashboardMutation.isPending || !dbForm.name.trim()}
            >
              {registerDashboardMutation.isPending && <Loader2 size={14} className="spin" />}
              Register Dashboard
            </button>
          </div>
        </Dialog>
      )}

      {showMoveNbModal && selection?.kind === 'notebook' && (() => {
        const targetCatalogObj = (catalogsQuery.data || []).find(c => c.name === moveNbTargetCatalog);
        const targetSchemas = targetCatalogObj?.schemas || [];

        return (
          <Dialog
            title="Rename / Move Notebook"
            subtitle="Change the catalog, schema, or name of this governed notebook."
            onClose={() => setShowMoveNbModal(false)}
          >
            <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <label className="uc-field">
                <span className="uc-field-label">Target Catalog</span>
                <select
                  className="input-field"
                  value={moveNbTargetCatalog}
                  onChange={(e) => {
                    setMoveNbTargetCatalog(e.target.value);
                    const catObj = (catalogsQuery.data || []).find(c => c.name === e.target.value);
                    if (catObj && catObj.schemas.length > 0) {
                      setMoveNbTargetSchema(catObj.schemas[0].name);
                    } else {
                      setMoveNbTargetSchema('');
                    }
                  }}
                >
                  {(catalogsQuery.data || []).map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Target Schema</span>
                <select
                  className="input-field"
                  value={moveNbTargetSchema}
                  onChange={(e) => setMoveNbTargetSchema(e.target.value)}
                  disabled={targetSchemas.length === 0}
                >
                  {targetSchemas.length === 0 && <option value="">No schemas available</option>}
                  {targetSchemas.map(s => (
                    <option key={s.id} value={s.name}>{s.name}</option>
                  ))}
                </select>
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Notebook Name</span>
                <input
                  className="input-field"
                  value={moveNbNewName}
                  onChange={(e) => setMoveNbNewName(e.target.value)}
                  placeholder="Notebook name"
                />
              </label>
            </div>

            {moveNotebookMutation.isError && (
              <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
                <span>{(moveNotebookMutation.error as any)?.response?.data?.detail || 'Failed to move notebook.'}</span>
              </div>
            )}

            <div className="uc-modal-footer">
              <button
                className="btn-primary"
                onClick={() =>
                  moveNotebookMutation.mutate({
                    catalog: selection.catalog,
                    schema: selection.schema,
                    notebook: selection.notebook,
                    body: {
                      target_catalog: moveNbTargetCatalog,
                      target_schema: moveNbTargetSchema,
                      new_name: moveNbNewName !== selection.notebook ? moveNbNewName : undefined,
                    },
                  })
                }
                disabled={moveNotebookMutation.isPending || !moveNbTargetCatalog || !moveNbTargetSchema || !moveNbNewName.trim()}
              >
                {moveNotebookMutation.isPending && <Loader2 size={14} className="spin" />}
                Move Notebook
              </button>
            </div>
          </Dialog>
        );
      })()}

      {showMoveDbModal && selection?.kind === 'dashboard' && (() => {
        const targetCatalogObj = (catalogsQuery.data || []).find(c => c.name === moveDbTargetCatalog);
        const targetSchemas = targetCatalogObj?.schemas || [];

        return (
          <Dialog
            title="Rename / Move Dashboard"
            subtitle="Change the catalog, schema, or name of this governed dashboard."
            onClose={() => setShowMoveDbModal(false)}
          >
            <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <label className="uc-field">
                <span className="uc-field-label">Target Catalog</span>
                <select
                  className="input-field"
                  value={moveDbTargetCatalog}
                  onChange={(e) => {
                    setMoveDbTargetCatalog(e.target.value);
                    const catObj = (catalogsQuery.data || []).find(c => c.name === e.target.value);
                    if (catObj && catObj.schemas.length > 0) {
                      setMoveDbTargetSchema(catObj.schemas[0].name);
                    } else {
                      setMoveDbTargetSchema('');
                    }
                  }}
                >
                  {(catalogsQuery.data || []).map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Target Schema</span>
                <select
                  className="input-field"
                  value={moveDbTargetSchema}
                  onChange={(e) => setMoveDbTargetSchema(e.target.value)}
                  disabled={targetSchemas.length === 0}
                >
                  {targetSchemas.length === 0 && <option value="">No schemas available</option>}
                  {targetSchemas.map(s => (
                    <option key={s.id} value={s.name}>{s.name}</option>
                  ))}
                </select>
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Dashboard Name</span>
                <input
                  className="input-field"
                  value={moveDbNewName}
                  onChange={(e) => setMoveDbNewName(e.target.value)}
                  placeholder="Dashboard name"
                />
              </label>
            </div>

            {moveDashboardMutation.isError && (
              <div className="uc-banner is-error mt-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
                <span>{(moveDashboardMutation.error as any)?.response?.data?.detail || 'Failed to move dashboard.'}</span>
              </div>
            )}

            <div className="uc-modal-footer">
              <button
                className="btn-primary"
                onClick={() =>
                  moveDashboardMutation.mutate({
                    catalog: selection.catalog,
                    schema: selection.schema,
                    dashboard: selection.dashboard,
                    body: {
                      target_catalog: moveDbTargetCatalog,
                      target_schema: moveDbTargetSchema,
                      new_name: moveDbNewName !== selection.dashboard ? moveDbNewName : undefined,
                    },
                  })
                }
                disabled={moveDashboardMutation.isPending || !moveDbTargetCatalog || !moveDbTargetSchema || !moveDbNewName.trim()}
              >
                {moveDashboardMutation.isPending && <Loader2 size={14} className="spin" />}
                Move Dashboard
              </button>
            </div>
          </Dialog>
        );
      })()}

      {/* Register Storage Backend modal */}
      {showStorageModal && (
        <Dialog
          title="Register Storage Backend"
          subtitle="Connect Azure, AWS S3, or MinIO for Iceberg table and volume storage."
          onClose={() => setShowStorageModal(false)}
        >
          <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <label className="uc-field">
                <span className="uc-field-label">Backend Name</span>
                <input className="input-field" value={storageForm.name} onChange={(e) => setStorageForm({ ...storageForm, name: e.target.value })} placeholder="e.g. azure_prod" autoFocus />
              </label>
              <label className="uc-field">
                <span className="uc-field-label">Provider</span>
                <select className="input-field" value={storageForm.provider} onChange={(e) => setStorageForm({ ...storageForm, provider: e.target.value })}>
                  <option value="azure">Azure Blob / ADLS Gen2</option>
                  <option value="s3">AWS S3</option>
                  <option value="minio">MinIO</option>
                </select>
              </label>
            </div>

            {storageForm.provider === 'azure' && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <label className="uc-field">
                    <span className="uc-field-label">Account Name</span>
                    <input className="input-field" value={storageForm.account_name} onChange={(e) => setStorageForm({ ...storageForm, account_name: e.target.value })} placeholder="myaccount" />
                  </label>
                  <label className="uc-field">
                    <span className="uc-field-label">Container</span>
                    <input className="input-field" value={storageForm.container} onChange={(e) => setStorageForm({ ...storageForm, container: e.target.value })} placeholder="compassx" />
                  </label>
                </div>
                <label className="uc-field">
                  <span className="uc-field-label">Account Key</span>
                  <input className="input-field" type="password" value={storageForm.account_key} onChange={(e) => setStorageForm({ ...storageForm, account_key: e.target.value })} placeholder="Storage account key (leave blank for service principal)" />
                </label>
              </>
            )}

            {(storageForm.provider === 's3' || storageForm.provider === 'minio') && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <label className="uc-field">
                    <span className="uc-field-label">Bucket</span>
                    <input className="input-field" value={storageForm.bucket} onChange={(e) => setStorageForm({ ...storageForm, bucket: e.target.value })} placeholder="compassx" />
                  </label>
                  <label className="uc-field">
                    <span className="uc-field-label">{storageForm.provider === 'minio' ? 'Endpoint URL' : 'Region'}</span>
                    <input className="input-field" value={storageForm.provider === 'minio' ? storageForm.endpoint_url : storageForm.region} onChange={(e) => setStorageForm(storageForm.provider === 'minio' ? { ...storageForm, endpoint_url: e.target.value } : { ...storageForm, region: e.target.value })} placeholder={storageForm.provider === 'minio' ? 'http://localhost:9000' : 'us-east-1'} />
                  </label>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <label className="uc-field">
                    <span className="uc-field-label">Access Key</span>
                    <input className="input-field" value={storageForm.access_key} onChange={(e) => setStorageForm({ ...storageForm, access_key: e.target.value })} placeholder="Access key ID" />
                  </label>
                  <label className="uc-field">
                    <span className="uc-field-label">Secret Key</span>
                    <input className="input-field" type="password" value={storageForm.secret_key} onChange={(e) => setStorageForm({ ...storageForm, secret_key: e.target.value })} placeholder="Secret access key" />
                  </label>
                </div>
              </>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '12px', alignItems: 'center' }}>
              <label className="uc-field" style={{ margin: 0 }}>
                <span className="uc-field-label">Base Path</span>
                <input className="input-field" value={storageForm.base_path} onChange={(e) => setStorageForm({ ...storageForm, base_path: e.target.value })} placeholder="compassx/" />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer', paddingTop: '18px' }}>
                <input type="checkbox" checked={storageForm.is_default} onChange={(e) => setStorageForm({ ...storageForm, is_default: e.target.checked })} />
                Set as default
              </label>
            </div>
          </div>

          {createStorageBackendMutation.isError && (
            <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '10px', borderRadius: '4px', fontSize: '12px', margin: '0 20px' }}>
              {(createStorageBackendMutation.error as any)?.response?.data?.detail || 'Failed to register storage backend.'}
            </div>
          )}

          <div className="uc-modal-footer">
            <button className="btn-primary"
              disabled={createStorageBackendMutation.isPending || !storageForm.name.trim()}
              onClick={() => {
                const body: Record<string, any> = {
                  name: storageForm.name,
                  provider: storageForm.provider,
                  is_default: storageForm.is_default,
                };
                if (storageForm.provider === 'azure') {
                  body.azure = { account_name: storageForm.account_name, container: storageForm.container, base_path: storageForm.base_path, account_key: storageForm.account_key || undefined };
                } else {
                  body.s3 = { bucket: storageForm.bucket, base_path: storageForm.base_path, region: storageForm.region, access_key: storageForm.access_key, secret_key: storageForm.secret_key, endpoint_url: storageForm.endpoint_url || undefined };
                }
                createStorageBackendMutation.mutate(body);
              }}
            >
              {createStorageBackendMutation.isPending && <Loader2 size={14} className="spin" />}
              Register Backend
            </button>
          </div>
        </Dialog>
      )}

      {/* Settings dropdown — fixed position to escape sidebar overflow:auto */}

      {showSettingsDropdown && (() => {
        const pos = getDropdownPos(settingsBtnRef);
        return (
          <div
            ref={settingsDropdownRef}
            style={{
              position: 'fixed',
              top: pos.top,
              right: pos.right,
              width: 200,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              zIndex: 9999,
              padding: '4px 0',
            }}
          >
            <button
              className="uc-dropdown-item"
              onClick={() => { navigate('/connections'); setShowSettingsDropdown(false); }}
            >
              Manage Connections
            </button>
          </div>
        );
      })()}

      {/* Plus dropdown — fixed position */}
      {showPlusDropdown && (() => {
        const pos = getDropdownPos(plusBtnRef);
        return (
          <div
            ref={plusDropdownRef}
            style={{
              position: 'fixed',
              top: pos.top,
              right: pos.right,
              width: 180,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              zIndex: 9999,
              padding: '4px 0',
            }}
          >
            <button
              className="uc-dropdown-item"
              onClick={() => { setShowCatalogModal(true); setShowPlusDropdown(false); }}
            >
              Create catalog
            </button>
          </div>
        );
      })()}

      {/* More Actions dropdown (three-dot, catalog level only) */}
      {showMoreActionsDropdown && selection?.kind === 'catalog' && (() => {
        const pos = getDropdownPos(moreActionsBtnRef);
        const cat = (catalogsQuery.data || []).find(c => c.name === selection.catalog);
        const isPostgres = cat?.catalog_type === 'postgres';
        return (
          <div
            ref={moreActionsDropdownRef}
            style={{
              position: 'fixed',
              top: pos.top,
              right: pos.right,
              width: 210,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              boxShadow: '0 8px 24px rgba(0,0,0,0.14)',
              zIndex: 9999,
              padding: '4px 0',
            }}
          >
            {isPostgres && (
              <button
                className="uc-dropdown-item"
                disabled={syncCatalogMutation.isPending}
                onClick={() => {
                  if (cat) syncCatalogMutation.mutate(cat.name);
                }}
              >
                {syncCatalogMutation.isPending ? 'Syncing…' : 'Sync schema'}
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', display: 'block', marginTop: '2px' }}>
                  Import tables & columns from Postgres
                </span>
              </button>
            )}
            <button
              className="uc-dropdown-item"
              style={{ color: '#ef4444' }}
              onClick={() => {
                setShowMoreActionsDropdown(false);
                setDeleteCatalogConfirmText('');
                setShowDeleteCatalogModal(true);
              }}
            >
              Delete catalog
              {isPostgres && (
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', display: 'block', marginTop: '2px' }}>
                  Catalog-level only (Postgres)
                </span>
              )}
            </button>
          </div>
        );
      })()}

      {/* Delete Catalog Confirmation Modal */}
      {showDeleteCatalogModal && selection?.kind === 'catalog' && (() => {
        const cat = (catalogsQuery.data || []).find(c => c.name === selection.catalog);
        const isPostgres = cat?.catalog_type === 'postgres';
        const nameMatch = deleteCatalogConfirmText === selection.catalog;
        return (
          <div className="uc-modal-overlay" onClick={() => { setShowDeleteCatalogModal(false); setDeleteCatalogConfirmText(''); }}>
            <div className="uc-modal" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}>
              <div className="uc-modal-header">
                <div>
                  <h3 style={{ color: '#ef4444' }}>Delete catalog</h3>
                  <p>This action is permanent and cannot be undone.</p>
                </div>
                <button className="uc-icon-btn" onClick={() => { setShowDeleteCatalogModal(false); setDeleteCatalogConfirmText(''); }}>
                  <X size={16} />
                </button>
              </div>

              <div style={{ padding: '0 24px 24px' }}>
                {/* Warning banner */}
                <div style={{
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  borderRadius: 8,
                  padding: '12px 16px',
                  marginBottom: 20,
                  fontSize: 13,
                  color: 'var(--color-text)',
                  lineHeight: 1.6,
                }}>
                  <strong style={{ color: '#ef4444' }}>⚠ Warning — irreversible action</strong>
                  <p style={{ margin: '6px 0 0' }}>
                    Deleting <strong>{selection.catalog}</strong> will permanently remove the catalog registration from CompassX.
                    {isPostgres
                      ? ' Because this is a Postgres catalog, only the catalog metadata is deleted — schemas and tables in the underlying database are NOT affected.'
                      : ' All registered schemas and table metadata within this catalog will also be removed.'}
                  </p>
                </div>

                {isPostgres && (
                  <div style={{
                    background: 'rgba(234,179,8,0.08)',
                    border: '1px solid rgba(234,179,8,0.3)',
                    borderRadius: 6,
                    padding: '10px 14px',
                    marginBottom: 20,
                    fontSize: 12,
                    color: 'var(--color-text-muted)',
                  }}>
                    Schema and table-level deletion is not available for Postgres catalogs. Only the catalog-level registration can be deleted here.
                  </div>
                )}

                <label className="uc-field" style={{ marginBottom: 20 }}>
                  <span className="uc-field-label">
                    Type <strong>{selection.catalog}</strong> to confirm deletion
                  </span>
                  <input
                    className="input-field"
                    value={deleteCatalogConfirmText}
                    onChange={(e) => setDeleteCatalogConfirmText(e.target.value)}
                    placeholder={selection.catalog}
                    autoFocus
                    style={{ borderColor: nameMatch ? '#ef4444' : undefined }}
                  />
                </label>

                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                  <button
                    className="btn-outline"
                    onClick={() => { setShowDeleteCatalogModal(false); setDeleteCatalogConfirmText(''); }}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn-primary"
                    style={{
                      background: nameMatch ? '#ef4444' : undefined,
                      opacity: nameMatch ? 1 : 0.4,
                      cursor: nameMatch ? 'pointer' : 'not-allowed',
                      border: 'none',
                    }}
                    disabled={!nameMatch || deleteCatalogMutation.isPending}
                    onClick={() => { if (nameMatch) deleteCatalogMutation.mutate(selection.catalog); }}
                  >
                    {deleteCatalogMutation.isPending && <Loader2 size={14} className="spin" style={{ marginRight: 4 }} />}
                    Delete catalog
                  </button>
                </div>

                {deleteCatalogMutation.isError && (
                  <p style={{ color: '#ef4444', fontSize: 12, marginTop: 10 }}>
                    {(deleteCatalogMutation.error as any)?.response?.data?.detail || 'Failed to delete catalog. Please try again.'}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Delete Table Confirmation Modal */}
      {tableToDelete && (
        <div className="uc-modal-overlay" onClick={() => setTableToDelete(null)}>
          <div className="uc-modal" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}>
            <div className="uc-modal-header">
              <div>
                <h3 style={{ color: '#ef4444' }}>Delete table</h3>
                <p>Remove <strong>{tableToDelete.table}</strong> from the catalog</p>
              </div>
              <button className="uc-icon-btn" onClick={() => setTableToDelete(null)}>
                <X size={16} />
              </button>
            </div>

            <div style={{ padding: '0 24px 24px' }}>
              {/* Warning banner */}
              <div style={{
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 8,
                padding: '12px 16px',
                marginBottom: 16,
                fontSize: 13,
                color: 'var(--color-text)',
                lineHeight: 1.5,
              }}>
                <strong style={{ color: '#ef4444' }}>⚠ Confirm Table Deletion</strong>
                <p style={{ margin: '6px 0 0' }}>
                  Are you sure you want to delete table <strong>{tableToDelete.catalog}.{tableToDelete.schema}.{tableToDelete.table}</strong> from the catalog?
                </p>
              </div>

              {/* Soft delete explanation notice */}
              <div style={{
                background: 'rgba(234,179,8,0.08)',
                border: '1px solid rgba(234,179,8,0.3)',
                borderRadius: 6,
                padding: '10px 14px',
                marginBottom: 20,
                fontSize: 12,
                color: 'var(--color-text-muted)',
                lineHeight: 1.4,
              }}>
                <strong>Soft delete:</strong> This operation deletes the table metadata registration from the CompassX Data Catalog. The actual data files in the storage backend will <strong>not</strong> be deleted.
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => setTableToDelete(null)}
                  disabled={deleteTableMutation.isPending}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  style={{
                    background: '#ef4444',
                    border: 'none',
                    color: '#ffffff',
                  }}
                  disabled={deleteTableMutation.isPending}
                  onClick={() => deleteTableMutation.mutate(tableToDelete)}
                >
                  {deleteTableMutation.isPending && <Loader2 size={14} className="spin" style={{ marginRight: 4 }} />}
                  Delete table
                </button>
              </div>

              {deleteTableMutation.isError && (
                <p style={{ color: '#ef4444', fontSize: 12, marginTop: 10 }}>
                  {(deleteTableMutation.error as any)?.response?.data?.detail || 'Failed to delete table. Please try again.'}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
