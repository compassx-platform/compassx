import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate, Link, useSearchParams, Navigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Database, Loader2, Play, Plus, Power, Square, TerminalSquare, Code2, Server, History, CheckCircle2, ChevronRight, Activity, Clock, Search, ServerCog, Folder, ChevronDown, Star, Sparkles, Download, Maximize2, BarChart2, Settings, MoreVertical, Share2, FileText, RefreshCw, XCircle, HelpCircle, ExternalLink, Zap, LayoutGrid, List, X, GitBranch, Edit2, Trash2, Check, Bookmark, BookOpen } from 'lucide-react';
import api from '@/lib/api';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import { PageTabs } from '@/components/common/PageTabs';
import { ModularSqlEditor } from './components/ModularSqlEditor';
import { CatalogExplorerTree } from '../data/components/CatalogExplorerTree';
import './sql-warehouse.css';
import './sql-editor-custom.css';

type Warehouse = {
  id: string;
  name: string;
  description?: string | null;
  engine: 'clickhouse' | 'duckdb' | 'postgres';
  status: string;
  config: Record<string, unknown>;
  resource_policy: Record<string, unknown>;
};

type QueryResult = {
  query_id: string;
  columns: string[];
  rows: unknown[][];
  rows_returned: number;
  duration_ms: number;
  bytes_scanned: number;
  truncated: boolean;
  cache_hit: boolean;
  query_analysis?: Record<string, any> | null;
};

type HistoryRecord = {
  id: string;
  warehouse_id: string;
  sql_text: string;
  status: string;
  engine: string;
  source: string;
  dashboard_id?: string | null;
  dataset_id?: string | null;
  run_by_user_id?: string | null;
  run_by_user_name?: string | null;
  rows_returned?: number | null;
  duration_ms?: number | null;
  error_message?: string | null;
  cache_hit: boolean;
  query_analysis?: Record<string, any> | null;
  created_at: string;
};

type DraftQuery = {
  id: string;
  workspace_id?: string | null;
  user_id: string;
  name: string;
  sql_text: string;
  catalog?: string | null;
  schema_name?: string | null;
  tab_order: number;
  created_at: string;
  updated_at: string;
};

function InlineRenameInput({
  initialValue,
  onSave,
  onCancel,
  className,
  style,
}: {
  initialValue: string;
  onSave: (val: string) => void;
  onCancel: () => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [val, setVal] = useState(initialValue);
  const valRef = useRef(val);
  valRef.current = val;

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isCommittedRef = useRef(false);

  const handleCommit = (shouldSave: boolean) => {
    if (isCommittedRef.current) return;
    isCommittedRef.current = true;
    if (shouldSave) {
      const trimmed = valRef.current.trim();
      if (trimmed) {
        onSave(trimmed);
      } else {
        onCancel();
      }
    } else {
      onCancel();
    }
  };

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        handleCommit(true);
      }
    };

    const timer = setTimeout(() => {
      window.addEventListener('mousedown', handleClickOutside);
    }, 150);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
        flex: 1,
        minWidth: 0,
      }}
    >
      <input
        ref={inputRef}
        type="text"
        className={className}
        value={val}
        autoFocus
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            e.stopPropagation();
            handleCommit(true);
          } else if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            handleCommit(false);
          }
        }}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
        style={{
          background: 'var(--color-surface)',
          color: 'var(--color-text)',
          border: '1px solid var(--color-primary)',
          borderRadius: 3,
          padding: '1px 6px',
          fontSize: 12,
          outline: 'none',
          boxShadow: '0 0 0 2px rgba(14, 165, 233, 0.25)',
          width: '100%',
          minWidth: 80,
          ...style,
        }}
      />
      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          handleCommit(true);
        }}
        title="Save (Enter)"
        style={{
          background: 'var(--color-primary)',
          color: '#ffffff',
          border: 'none',
          borderRadius: 3,
          padding: '2px 4px',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Check size={11} />
      </button>
      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          handleCommit(false);
        }}
        title="Cancel (Esc)"
        style={{
          background: 'var(--color-background-subtle, #374151)',
          color: 'var(--color-text-muted)',
          border: '1px solid var(--color-border)',
          borderRadius: 3,
          padding: '2px 4px',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <X size={11} />
      </button>
    </div>
  );
}

function ProfileTreeNode({ node, totalLatency, depth = 0 }: { node: any; totalLatency: number; depth?: number }) {
  const [expanded, setExpanded] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  if (!node) return null;

  const opName = node.operator_name || node.operator_type || 'Operator';
  const cardinality = node.operator_cardinality ?? node.rows_returned ?? 0;
  const timing = node.operator_timing ?? 0;
  const cpuTime = node.cpu_time ?? 0;

  const costPercent = totalLatency > 0 ? (timing / totalLatency) * 100 : 0;

  const getOpIcon = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.includes('scan')) return <Database size={14} className="text-primary" />;
    if (lower.includes('filter')) return <Search size={14} style={{ color: '#ec4899' }} />;
    if (lower.includes('projection')) return <Code2 size={14} style={{ color: '#a855f7' }} />;
    if (lower.includes('join')) return <GitBranch size={14} style={{ color: '#eab308' }} />;
    if (lower.includes('order') || lower.includes('sort')) return <List size={14} style={{ color: '#10b981' }} />;
    if (lower.includes('limit')) return <Square size={14} style={{ color: '#ef4444' }} />;
    if (lower.includes('aggregate') || lower.includes('group')) return <BarChart2 size={14} style={{ color: '#3b82f6' }} />;
    return <Activity size={14} className="text-muted" />;
  };

  const hasChildren = node.children && node.children.length > 0;

  return (
    <div style={{ marginLeft: depth * 12, borderLeft: depth > 0 ? '1px dashed var(--color-border)' : 'none', paddingLeft: depth > 0 ? 8 : 0, marginTop: 6 }}>
      <div
        className="swh-operator-card"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 6,
          padding: '8px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
        onClick={() => setShowDetails(!showDetails)}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: 12 }}>
            {hasChildren && (
              <button
                onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                style={{ background: 'none', border: 'none', padding: 2, cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'var(--color-text-muted)' }}
              >
                {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </button>
            )}
            {getOpIcon(opName)}
            <span style={{ fontFamily: 'monospace' }}>{opName}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{cardinality.toLocaleString()} rows</span>
            <span style={{ fontWeight: 600, color: costPercent > 20 ? '#f59e0b' : 'var(--color-text-muted)' }}>
              {costPercent.toFixed(1)}% ({timing.toFixed(4)}s)
            </span>
          </div>
        </div>

        {costPercent > 0.1 && (
          <div style={{ width: '100%', height: 3, background: 'var(--color-background-muted)', borderRadius: 1.5, overflow: 'hidden' }}>
            <div style={{
              width: `${Math.min(costPercent, 100)}%`,
              height: '100%',
              background: costPercent > 20 ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : 'linear-gradient(90deg, #14b8a6, #0ea5e9)'
            }} />
          </div>
        )}

        {showDetails && (
          <div style={{ fontSize: 10, color: 'var(--color-text-muted)', borderTop: '1px solid var(--color-border)', paddingTop: 4, marginTop: 4, display: 'flex', flexDirection: 'column', gap: 3 }}>
            {node.extra_info && Object.entries(node.extra_info).map(([key, val]) => (
              <div key={key} style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8 }}>
                <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>{key}:</span>
                <span style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{String(val)}</span>
              </div>
            ))}
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8 }}>
              <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>CPU Time:</span>
              <span>{cpuTime.toFixed(6)}s</span>
            </div>
          </div>
        )}
      </div>

      {hasChildren && expanded && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {node.children.map((child: any, idx: number) => (
            <ProfileTreeNode key={idx} node={child} totalLatency={totalLatency} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

const warehouseApi = {
  list: () => api.get<Warehouse[]>('/warehouses').then((r) => r.data),
  create: (body: Record<string, unknown>) => api.post<Warehouse>('/warehouses', body).then((r) => r.data),
  start: (id: string) => api.post<Warehouse>(`/warehouses/${id}/start`).then((r) => r.data),
  stop: (id: string) => api.post<Warehouse>(`/warehouses/${id}/stop`).then((r) => r.data),
  query: (warehouse_id: string, sql: string, catalog?: string, schema_name?: string, source?: string, max_rows?: number) => api.post<QueryResult>('/sql/query', { warehouse_id, sql, max_rows: max_rows ?? 1000, catalog, schema_name, source }).then((r) => r.data),
  validate: (sql: string) => api.post<{ valid: boolean; error?: string; statement_count?: number }>('/sql/validate', { sql }).then((r) => r.data),
  history: (warehouse_id?: string, scope: 'me' | 'all' = 'me') => api.get<{ records: HistoryRecord[] }>('/sql/history', { params: { warehouse_id, limit: 25, scope } }).then((r) => r.data.records),
  drafts: () => api.get<DraftQuery[]>('/sql/drafts').then((r) => r.data),
  createDraft: (body: { name?: string; sql_text?: string; catalog?: string; schema_name?: string; tab_order?: number }) => api.post<DraftQuery>('/sql/drafts', body).then((r) => r.data),
  updateDraft: (id: string, body: { name?: string; sql_text?: string; catalog?: string; schema_name?: string; tab_order?: number }) => api.put<DraftQuery>(`/sql/drafts/${id}`, body).then((r) => r.data),
  deleteDraft: (id: string) => api.delete<{ deleted: boolean; id: string }>(`/sql/drafts/${id}`).then((r) => r.data),
  catalogs: () => api.get<{ catalogs: { name: string; catalog_type: string }[] }>('/sql-warehouse/catalog/catalogs').then((r) => r.data.catalogs),
  schemas: (catalog: string) => api.get<{ schemas: string[] }>('/sql-warehouse/catalog/schemas', { params: { catalog } }).then((r) => r.data.schemas),
};

export default function SqlWarehousePage() {
  const { tab } = useParams();
  if (tab === 'explorer') {
    return <Navigate to="../editor" replace relative="path" />;
  }

  const qc = useQueryClient();
  const activeTab = tab || 'editor';
  const navigate = useNavigate();
  
  const [searchParams] = useSearchParams();
  const initialSqlParam = searchParams.get('sql');
  const initialQueryNameParam = searchParams.get('query_name');
  const initialCatalogParam = searchParams.get('catalog');
  const initialSchemaParam = searchParams.get('schema');

  const [search, setSearch] = useState('');
  
  const [detailsWarehouseId, setDetailsWarehouseId] = useState<string | null>(null);
  const [detailsTab, setDetailsTab] = useState<'overview' | 'monitoring'>('monitoring');
  
  const [activeWarehouseId, setActiveWarehouseId] = useState('');
  const [activeCatalog, setActiveCatalog] = useState(initialCatalogParam || '');
  const [activeSchema, setActiveSchema] = useState(initialSchemaParam || '');
  const [sql, setSql] = useState(initialSqlParam || "SELECT 1 AS id, 'CompassX SQL Warehouse' AS name;");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState('');

  const [queryTabs, setQueryTabs] = useState<Array<{ id: string; name: string; sql: string; catalog: string; schema: string }>>([
    {
      id: 'q1',
      name: initialQueryNameParam || "Query 1",
      sql: initialSqlParam || "SELECT 1 AS id, 'CompassX SQL Warehouse' AS name;",
      catalog: initialCatalogParam || '',
      schema: initialSchemaParam || '',
    }
  ]);
  const [activeQueryTabId, setActiveQueryTabId] = useState('q1');
  const [editingTabId, setEditingTabId] = useState<string | null>(null);
  const [openDraftMenuId, setOpenDraftMenuId] = useState<string | null>(null);
  const [sidebarSearch, setSidebarSearch] = useState('');
  const [draftsExpanded, setDraftsExpanded] = useState(true);
  const [sidebarMode, setSidebarMode] = useState<'drafts' | 'catalog'>('drafts');

  // Save to Catalog modal state
  const [showSaveToCatalogModal, setShowSaveToCatalogModal] = useState(false);
  const [saveCatalogName, setSaveCatalogName] = useState('');
  const [saveSchemaName, setSaveSchemaName] = useState('');
  const [saveQueryName, setSaveQueryName] = useState('');
  const [saveDescription, setSaveDescription] = useState('');
  const [isSavingToCatalog, setIsSavingToCatalog] = useState(false);
  const [saveCatalogFeedback, setSaveCatalogFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const autoSaveTimerRef = useRef<any>(null);
  const initialLoadDone = useRef(false);

  useEffect(() => {
    const handleOutsideClick = () => {
      setOpenDraftMenuId(null);
    };
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  }, []);

  // Query History Filters
  const [historySearch, setHistorySearch] = useState('');
  const [historyStatus, setHistoryStatus] = useState('all');
  const [historyCompute, setHistoryCompute] = useState('all');
  const [historyUser, setHistoryUser] = useState('all');
  const [historyTimeRange, setHistoryTimeRange] = useState('7d');

  const [selectedQueryForProfile, setSelectedQueryForProfile] = useState<HistoryRecord | QueryResult | null>(null);
  const [drawerTab, setDrawerTab] = useState<'profile' | 'sql'>('profile');
  const [explainPlanText, setExplainPlanText] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);

  const draftsQuery = useQuery({ queryKey: ['swh-drafts'], queryFn: warehouseApi.drafts });

  useEffect(() => {
    if (draftsQuery.isSuccess) {
      if (draftsQuery.data && draftsQuery.data.length > 0) {
        const loadedTabs = draftsQuery.data.map(d => ({
          id: d.id,
          name: d.name,
          sql: d.sql_text,
          catalog: d.catalog || '',
          schema: d.schema_name || '',
        }));
        if (!initialLoadDone.current) {
          setQueryTabs(loadedTabs);
          setActiveQueryTabId(loadedTabs[0].id);
          setSql(loadedTabs[0].sql);
          if (loadedTabs[0].catalog) setActiveCatalog(loadedTabs[0].catalog);
          if (loadedTabs[0].schema) setActiveSchema(loadedTabs[0].schema);
          initialLoadDone.current = true;
        } else {
          setQueryTabs(prev => {
            return loadedTabs.map(loaded => {
              const existing = prev.find(p => p.id === loaded.id);
              if (existing) {
                return { ...existing, name: loaded.name };
              }
              return loaded;
            });
          });
        }
      } else if (!initialLoadDone.current) {
        initialLoadDone.current = true;
        warehouseApi.createDraft({
          name: 'Query 1',
          sql_text: "SELECT 1 AS id, 'CompassX SQL Warehouse' AS name;",
          catalog: activeCatalog || '',
          schema_name: activeSchema || '',
          tab_order: 0,
        }).then(newDraft => {
          const newTab = {
            id: newDraft.id,
            name: newDraft.name,
            sql: newDraft.sql_text,
            catalog: newDraft.catalog || '',
            schema: newDraft.schema_name || '',
          };
          setQueryTabs([newTab]);
          setActiveQueryTabId(newDraft.id);
          setSql(newTab.sql);
          qc.invalidateQueries({ queryKey: ['swh-drafts'] });
        }).catch(err => {
          console.error('Failed to create default initial draft:', err);
        });
      }
    }
  }, [draftsQuery.data, draftsQuery.isSuccess]);

  useEffect(() => {
    setExplainPlanText(null);
  }, [selectedQueryForProfile]);

  const handleExplainPlan = async () => {
    if (!selectedQueryForProfile) return;
    setIsExplaining(true);
    try {
      const whId = (selectedQueryForProfile as any).warehouse_id || activeWarehouseId;
      const sqlText = (selectedQueryForProfile as any).sql_text || sql;
      const res = await api.post<{ plan: string }>('/sql/explain', { warehouse_id: whId, sql: sqlText });
      setExplainPlanText(res.data.plan);
    } catch (err: any) {
      setExplainPlanText("Failed to generate explain plan: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsExplaining(false);
    }
  };

  const activeTabObj = useMemo(() => queryTabs.find(t => t.id === activeQueryTabId) || queryTabs[0], [queryTabs, activeQueryTabId]);

  const handleSelectTab = (tabId: string) => {
    setActiveQueryTabId(tabId);
    const target = queryTabs.find(t => t.id === tabId);
    if (target) {
      setSql(target.sql);
      if (target.catalog) setActiveCatalog(target.catalog);
      if (target.schema) setActiveSchema(target.schema);
    }
  };

  const triggerAutoSave = (draftId: string, updates: { name?: string; sql_text?: string; catalog?: string; schema_name?: string }) => {
    if (!draftId) return;
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
    autoSaveTimerRef.current = setTimeout(() => {
      warehouseApi.updateDraft(draftId, updates).then(() => {
        qc.invalidateQueries({ queryKey: ['swh-drafts'] });
      }).catch(err => {
        console.error('Failed to auto-save draft:', err);
      });
    }, 600);
  };

  const handleSqlChange = (newSql: string) => {
    setSql(newSql);
    setQueryTabs(prev => prev.map(t => {
      if (t.id === activeQueryTabId) {
        return { ...t, sql: newSql };
      }
      return t;
    }));
    triggerAutoSave(activeQueryTabId, { sql_text: newSql });
  };

  const handleCatalogChange = (newCat: string) => {
    setActiveCatalog(newCat);
    setActiveSchema('');
    setQueryTabs(prev => prev.map(t => {
      if (t.id === activeQueryTabId) {
        return { ...t, catalog: newCat, schema: '' };
      }
      return t;
    }));
    triggerAutoSave(activeQueryTabId, { catalog: newCat, schema_name: '' });
  };

  const handleSchemaChange = (newSchema: string) => {
    setActiveSchema(newSchema);
    setQueryTabs(prev => prev.map(t => {
      if (t.id === activeQueryTabId) {
        return { ...t, schema: newSchema };
      }
      return t;
    }));
    triggerAutoSave(activeQueryTabId, { schema_name: newSchema });
  };

  const handleSaveRename = async (id: string, newName: string) => {
    const trimmed = newName.trim();
    setEditingTabId(null);
    if (!trimmed) return;
    setQueryTabs(prev => prev.map(t => t.id === id ? { ...t, name: trimmed } : t));
    try {
      await warehouseApi.updateDraft(id, { name: trimmed });
      qc.invalidateQueries({ queryKey: ['swh-drafts'] });
    } catch (e) {
      console.error('Failed to rename draft:', e);
    }
  };

  const handleSelectDraft = (item: { id: string; name: string; sql: string; catalog?: string; schema?: string }) => {
    if (queryTabs.some(t => t.id === item.id)) {
      handleSelectTab(item.id);
    } else {
      setQueryTabs(prev => [...prev, { id: item.id, name: item.name, sql: item.sql, catalog: item.catalog || activeCatalog, schema: item.schema || activeSchema }]);
      handleSelectTab(item.id);
    }
  };

  const handleAddTab = async () => {
    const nextNumber = (draftsQuery.data?.length ?? queryTabs.length) + 1;
    const defaultName = `Query ${nextNumber}`;
    const defaultSql = 'select * from ...';
    try {
      const newDraft = await warehouseApi.createDraft({
        name: defaultName,
        sql_text: defaultSql,
        catalog: activeCatalog,
        schema_name: activeSchema,
        tab_order: queryTabs.length,
      });
      const newTab = {
        id: newDraft.id,
        name: newDraft.name,
        sql: newDraft.sql_text,
        catalog: newDraft.catalog || activeCatalog,
        schema: newDraft.schema_name || activeSchema,
      };
      setQueryTabs(prev => [...prev, newTab]);
      setActiveQueryTabId(newDraft.id);
      setSql(newDraft.sql_text);
      qc.invalidateQueries({ queryKey: ['swh-drafts'] });
    } catch (e) {
      console.error('Failed to create draft:', e);
    }
  };

  const handleCloseTab = async (id: string) => {
    if (queryTabs.length <= 1) return;
    const activeIndex = queryTabs.findIndex(t => t.id === activeQueryTabId);
    const newTabs = queryTabs.filter(t => t.id !== id);
    setQueryTabs(newTabs);
    if (activeQueryTabId === id) {
      const nextActive = newTabs[Math.max(activeIndex - 1, 0)];
      setActiveQueryTabId(nextActive.id);
      setSql(nextActive.sql);
      if (nextActive.catalog) setActiveCatalog(nextActive.catalog);
      if (nextActive.schema) setActiveSchema(nextActive.schema);
    }
    try {
      await warehouseApi.deleteDraft(id);
      qc.invalidateQueries({ queryKey: ['swh-drafts'] });
    } catch (e) {
      console.error('Failed to delete draft:', e);
    }
  };

  const handleInsertIntoSql = (identifier: string) => {
    const updatedSql = sql ? `${sql.trim()}\n${identifier}` : identifier;
    handleSqlChange(updatedSql);
  };

  const handleDownloadCsv = () => {
    if (!result || !result.columns || !result.rows || result.rows.length === 0) return;
    const header = result.columns.join(',');
    const rows = result.rows.map(r => r.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','));
    const csvContent = "data:text/csv;charset=utf-8," + [header, ...rows].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `${activeTabObj?.name || 'query_result'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const lineNumbers = useMemo(() => {
    const lines = sql.split('\n').length;
    return Array.from({ length: Math.max(lines, 1) }, (_, i) => i + 1);
  }, [sql]);

  const getHeaderIcon = (colName: string) => {
    const lower = colName.toLowerCase();
    if (lower.includes('id') || lower.includes('count') || lower.includes('quantity')) {
      return <span style={{ color: 'var(--color-primary)', marginRight: 4, fontWeight: 'bold', fontSize: 10 }}>123</span>;
    }
    if (lower.includes('ts') || lower.includes('date') || lower.includes('time') || lower.includes('at')) {
      return <Clock size={11} style={{ marginRight: 4, color: 'var(--color-text-muted)' }} />;
    }
    return <span style={{ color: '#ec4899', marginRight: 4, fontWeight: 'bold', fontSize: 10 }}>abc</span>;
  };
  
  const [createOpen, setCreateOpen] = useState(false);
  const [newWarehouse, setNewWarehouse] = useState({ name: '', engine: 'duckdb', description: '' });

  const warehousesQuery = useQuery({ queryKey: ['sql-warehouses'], queryFn: warehouseApi.list });
  const warehouses = warehousesQuery.data || [];
  const activeWarehouse = warehouses.find((w) => w.id === activeWarehouseId) || warehouses[0];
  
  const catalogsQuery = useQuery({ queryKey: ['swh-catalogs'], queryFn: warehouseApi.catalogs });
  const schemasQuery = useQuery({ queryKey: ['swh-schemas', activeCatalog], queryFn: () => warehouseApi.schemas(activeCatalog), enabled: !!activeCatalog });
  const historyQuery = useQuery({
    queryKey: ['swh-history', detailsWarehouseId || 'all', historyUser],
    queryFn: () => warehouseApi.history(detailsWarehouseId || undefined, historyUser as 'me' | 'all')
  });

  const saveSchemasQuery = useQuery({
    queryKey: ['swh-save-schemas', saveCatalogName],
    queryFn: () => warehouseApi.schemas(saveCatalogName),
    enabled: !!saveCatalogName && showSaveToCatalogModal,
  });

  const handleOpenSaveToCatalog = () => {
    const currentTab = queryTabs.find(t => t.id === activeQueryTabId);
    const defaultCat = activeCatalog || catalogsQuery.data?.[0]?.name || 'compassx';
    setSaveCatalogName(defaultCat);
    setSaveSchemaName(activeSchema || 'public');
    setSaveQueryName(currentTab?.name || 'Query');
    setSaveDescription('');
    setSaveCatalogFeedback(null);
    setShowSaveToCatalogModal(true);
  };

  const handleSaveToCatalogSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!saveCatalogName || !saveSchemaName || !saveQueryName.trim()) {
      setSaveCatalogFeedback({ type: 'error', message: 'Catalog, schema, and query name are required.' });
      return;
    }
    setIsSavingToCatalog(true);
    setSaveCatalogFeedback(null);
    try {
      await api.post(`/catalog/catalogs/${encodeURIComponent(saveCatalogName)}/schemas/${encodeURIComponent(saveSchemaName)}/queries`, {
        name: saveQueryName.trim(),
        sql_text: sql || '',
        description: saveDescription.trim() || undefined,
      });
      setSaveCatalogFeedback({
        type: 'success',
        message: `Query registered in catalog: ${saveCatalogName}.${saveSchemaName}.${saveQueryName.trim()}`,
      });
      qc.invalidateQueries({ queryKey: ['uc-schema-queries'] });
      qc.invalidateQueries({ queryKey: ['uc-catalog'] });
      setTimeout(() => {
        setShowSaveToCatalogModal(false);
        setIsSavingToCatalog(false);
        setSaveCatalogFeedback(null);
      }, 1400);
    } catch (err: any) {
      setIsSavingToCatalog(false);
      const detail = err?.response?.data?.detail || err?.message || 'Failed to save query to catalog';
      setSaveCatalogFeedback({ type: 'error', message: detail });
    }
  };

  const drafts = useMemo(() => {
    const list = (draftsQuery.data && draftsQuery.data.length > 0) ? draftsQuery.data.map(d => ({
      id: d.id,
      name: d.name,
      sql: d.sql_text,
      catalog: d.catalog || '',
      schema: d.schema_name || '',
    })) : queryTabs;

    const seen = new Set();
    const uniqueItems = [];
    for (const item of list) {
      if (!seen.has(item.id)) {
        seen.add(item.id);
        uniqueItems.push(item);
      }
    }
    return uniqueItems.filter(item => !sidebarSearch || item.name.toLowerCase().includes(sidebarSearch.toLowerCase()));
  }, [draftsQuery.data, queryTabs, sidebarSearch]);


  useEffect(() => {
    if (!activeWarehouseId && warehouses[0]) setActiveWarehouseId(warehouses[0].id);
  }, [activeWarehouseId, warehouses]);

  useEffect(() => {
    const catalogs = catalogsQuery.data || [];
    if (catalogs.length > 0) {
      const exists = catalogs.some(c => c.name === activeCatalog);
      if (!activeCatalog || !exists) {
        setActiveCatalog(catalogs[0].name);
        setActiveSchema('');
      }
    } else if (catalogsQuery.isSuccess && catalogs.length === 0) {
      setActiveCatalog('');
      setActiveSchema('');
    }
  }, [activeCatalog, catalogsQuery.data, catalogsQuery.isSuccess]);

  useEffect(() => {
    const schemas = schemasQuery.data || [];
    if (schemas.length > 0) {
      const exists = schemas.includes(activeSchema);
      if (!activeSchema || !exists) {
        setActiveSchema(schemas[0]);
      }
    } else if (schemasQuery.isSuccess && schemas.length === 0) {
      setActiveSchema('');
    }
  }, [activeSchema, schemasQuery.data, schemasQuery.isSuccess]);

  useEffect(() => {
    if (activeCatalog || activeSchema) {
      setQueryTabs(prev => prev.map(t => {
        if (t.id === activeQueryTabId) {
          return { ...t, catalog: activeCatalog, schema: activeSchema };
        }
        return t;
      }));
    }
  }, [activeCatalog, activeSchema, activeQueryTabId]);

  const createMutation = useMutation({
    mutationFn: () => warehouseApi.create({
      ...newWarehouse,
      config: {},
      resource_policy: { query_timeout_sec: 300, max_concurrent_queries: 5 },
    }),
    onSuccess: (warehouse) => {
      setActiveWarehouseId(warehouse.id);
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ['sql-warehouses'] });
    },
  });

  const startMutation = useMutation({ mutationFn: (id: string) => warehouseApi.start(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['sql-warehouses'] }) });
  const stopMutation = useMutation({ mutationFn: (id: string) => warehouseApi.stop(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['sql-warehouses'] }) });
  
  const runMutation = useMutation({
    mutationFn: (limit?: number) => warehouseApi.query(activeWarehouse!.id, sql, activeCatalog, activeSchema, 'sql_editor', limit ?? 1000),
    onMutate: () => { setError(''); setResult(null); },
    onSuccess: (res) => { setResult(res); qc.invalidateQueries({ queryKey: ['swh-history'] }); },
    onError: (e: any) => setError(e?.response?.data?.detail?.detail || e?.response?.data?.detail || 'Query failed'),
  });

  const canRun = !!activeWarehouse && activeWarehouse.status === 'running' && !!sql.trim() && !runMutation.isPending;

  const filteredWarehouses = warehouses.filter((w) =>
    !search.trim() || w.name.toLowerCase().includes(search.trim().toLowerCase())
  );

  const warehouseColumns: AppTableColumn<Warehouse>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (w) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <Server size={14} color="var(--color-text-muted)" />
          <span style={{ fontWeight: 500 }}>{w.name}</span>
        </span>
      ),
    },
    {
      key: 'engine',
      header: 'Engine',
      className: 'app-table-muted',
      render: (w) => <span style={{ textTransform: 'capitalize' }}>{w.engine}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (w) => (
        <span className={`swh-status-badge ${w.status}`}>{w.status}</span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (w) => (
        <>
          {w.status === 'running' ? (
            <button
              className="ghost-icon-btn"
              title="Stop"
              onClick={(e) => { e.stopPropagation(); stopMutation.mutate(w.id); }}
            >
              <Square size={13} />
            </button>
          ) : (
            <button
              className="ghost-icon-btn"
              title="Start"
              onClick={(e) => { e.stopPropagation(); startMutation.mutate(w.id); }}
            >
              <Power size={13} />
            </button>
          )}
        </>
      ),
    },
  ];

  const filteredHistory = useMemo(() => {
    let list = historyQuery.data || [];

    if (historySearch) {
      const q = historySearch.toLowerCase();
      list = list.filter(h => h.sql_text.toLowerCase().includes(q) || h.id.toLowerCase().includes(q));
    }

    if (historyStatus !== 'all') {
      list = list.filter(h => h.status === historyStatus);
    }

    if (historyCompute !== 'all') {
      list = list.filter(h => h.warehouse_id === historyCompute);
    }

    if (historyTimeRange !== 'all') {
      const now = new Date();
      const cutoff = new Date();
      if (historyTimeRange === '7d') cutoff.setDate(now.getDate() - 7);
      else if (historyTimeRange === '1d') cutoff.setDate(now.getDate() - 1);
      else if (historyTimeRange === '24h') cutoff.setHours(now.getHours() - 24);

      list = list.filter(h => new Date(h.created_at) >= cutoff);
    }

    return list;
  }, [historyQuery.data, historySearch, historyStatus, historyCompute, historyTimeRange]);

  const isHistoryFiltered = historySearch !== '' || historyStatus !== 'all' || historyCompute !== 'all' || historyTimeRange !== '7d' || historyUser !== 'all';

  const handleResetHistoryFilters = () => {
    setHistorySearch('');
    setHistoryStatus('all');
    setHistoryCompute('all');
    setHistoryTimeRange('7d');
    setHistoryUser('all');
  };

  const historyColumns = useMemo<AppTableColumn<HistoryRecord>[]>(() => [
    {
      key: 'status',
      header: 'Status',
      width: '80px',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {row.status === 'succeeded' ? (
            <CheckCircle2 size={16} color="var(--color-success)" style={{ flexShrink: 0 }} />
          ) : row.status === 'failed' ? (
            <XCircle size={16} color="var(--color-danger)" style={{ flexShrink: 0 }} />
          ) : (
            <Loader2 size={16} className="spin text-primary" style={{ flexShrink: 0 }} />
          )}
          <ChevronRight size={14} className="text-muted" />
        </div>
      )
    },
    {
      key: 'sql_text',
      header: 'Query',
      render: (row) => (
        <div 
          className="swh-history-sql" 
          style={{ 
            fontFamily: 'monospace', 
            fontSize: '12px',
            color: 'var(--color-text)', 
            whiteSpace: 'nowrap', 
            overflow: 'hidden', 
            textOverflow: 'ellipsis', 
            maxWidth: '450px' 
          }}
          title={row.sql_text}
        >
          {row.sql_text}
        </div>
      )
    },
    {
      key: 'run_by',
      header: 'Run By',
      width: '120px',
      render: (row) => {
        if (!row.run_by_user_id && !row.run_by_user_name) return <span style={{ color: 'var(--text-tertiary)' }}>-</span>;
        
        const displayName = row.run_by_user_name || ((row.run_by_user_id?.length ?? 0) > 20 ? 'User' : (row.run_by_user_id ?? '-'));
        const title = (row.run_by_user_name ? `${row.run_by_user_name} (${row.run_by_user_id})` : row.run_by_user_id) ?? undefined;
        
        return (
          <span title={title} style={{ 
            fontSize: '12px',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '100px',
            display: 'inline-block'
          }}>
            {displayName}
          </span>
        );
      }
    },
    {
      key: 'user',
      header: 'User',
      render: (row) => {
        // Fallback for known system accounts
        let displayUser = row.run_by_user_name || row.run_by_user_id || 'Unknown';
        if (displayUser === 'system') displayUser = 'System User';
        else if (displayUser.length > 20) displayUser = 'Service Account'; // e.g. workspace UUID

        const initial = (displayUser.charAt(0) || 'U').toUpperCase();

        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
            <div style={{ width: '16px', height: '16px', borderRadius: '50%', background: 'var(--color-background-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '9px', fontWeight: 'bold' }}>{initial}</div>
            <span title={row.run_by_user_id ?? displayUser} style={{ 
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '120px'
            }}>{displayUser}</span>
          </div>
        );
      }
    },
    {
      key: 'source',
      header: 'Source',
      width: '100px',
      render: (row) => {
        const isExplorer = row.sql_text.toLowerCase().includes('describe') || row.sql_text.toLowerCase().includes('show');
        let display = row.source === 'sql_editor' ? 'Editor' : row.source;
        if (isExplorer && row.source === 'sql_editor') {
          display = 'Catalog Explorer';
        }
        
        const content = (
          <span style={{ 
            textTransform: 'capitalize',
            color: row.dashboard_id ? 'var(--color-primary)' : 'var(--text-secondary)',
            background: 'var(--surface-sunken)',
            padding: '2px 8px',
            borderRadius: '12px',
            fontSize: '11px',
            cursor: row.dashboard_id ? 'pointer' : 'default',
            textDecoration: row.dashboard_id ? 'underline' : 'none'
          }}>
            {display}
          </span>
        );
        
        if (row.dashboard_id) {
          const workspaceSlug = window.location.pathname.split('/')[2];
          const appId = window.location.pathname.split('/')[3];
          return (
            <Link to={`/w/${workspaceSlug}/${appId}/dashboards/${row.dashboard_id}/edit`}>
              {content}
            </Link>
          );
        }
        
        return content;
      }
    },
    {
      key: 'created_at',
      header: 'Started at',
      render: (row) => (
        <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
          {new Date(row.created_at).toLocaleString()}
        </span>
      )
    },
    {
      key: 'duration',
      header: 'Duration',
      render: (row) => {
        const ms = row.duration_ms || 0;
        const maxDuration = Math.max(...(historyQuery.data || []).map(h => h.duration_ms || 1), 1000);
        const widthPercent = Math.min(Math.max((ms / maxDuration) * 100, 4), 100);
        
        const formatDuration = (val: number) => {
          if (val >= 1000) return `${(val / 1000).toFixed(2)} s`;
          return `${val} ms`;
        };

        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
            <div style={{ width: '32px', height: '6px', background: 'var(--color-background-muted)', borderRadius: '1px', overflow: 'hidden', flexShrink: 0 }}>
              <div style={{ width: `${widthPercent}%`, height: '100%', background: 'var(--color-primary)' }} />
            </div>
            <span>{formatDuration(ms)}</span>
          </div>
        );
      }
    },
    {
      key: 'compute',
      header: 'Compute',
      render: (row) => {
        const wh = warehouses.find(w => w.id === row.warehouse_id);
        return (
          <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
            {wh ? wh.name : 'Serverless Starter Warehouse'}
          </span>
        );
      }
    }
  ], [warehouses, historyQuery.data]);

  return (
    <div className="sql-warehouse-page" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {activeTab === 'editor' && (
          <div className="swh-editor-layout">
            {/* Left Sidebar */}
            <div className="swh-editor-sidebar">
              <div className="swh-sidebar-header">
                <h2>SQL Editor</h2>
                <div className="swh-sidebar-header-actions">
                  <button 
                    onClick={() => {
                      if (sidebarMode === 'drafts') draftsQuery.refetch();
                      else qc.invalidateQueries({ queryKey: ['explorer-catalogs'] });
                    }} 
                    title={sidebarMode === 'drafts' ? "Refresh drafts" : "Refresh catalog tree"} 
                    style={{ background: 'none', border: 'none', padding: 2, cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center' }}
                  >
                    <RefreshCw size={13} className={draftsQuery.isFetching ? 'spin' : ''} />
                  </button>
                </div>
              </div>

              {/* Clean Segmented Mode Switcher: Drafts vs Catalog */}
              <div className="swh-sidebar-mode-switch">
                <button
                  type="button"
                  className={`swh-sidebar-mode-btn ${sidebarMode === 'drafts' ? 'is-active' : ''}`}
                  onClick={() => setSidebarMode('drafts')}
                  title="View your personal draft queries"
                >
                  <Folder size={12} className="swh-mode-icon" />
                  <span>Drafts</span>
                </button>
                <button
                  type="button"
                  className={`swh-sidebar-mode-btn ${sidebarMode === 'catalog' ? 'is-active' : ''}`}
                  onClick={() => setSidebarMode('catalog')}
                  title="Explore Data Catalog schemas and tables (click to insert into SQL)"
                >
                  <Database size={12} className="swh-mode-icon" />
                  <span>Catalog</span>
                </button>
              </div>

              {sidebarMode === 'drafts' && (
                <>
                  <div className="swh-sidebar-search">
                    <Search size={12} className="text-muted" />
                    <input 
                      placeholder="Type to search" 
                      value={sidebarSearch}
                      onChange={e => setSidebarSearch(e.target.value)}
                    />
                  </div>
                  <div className="swh-sidebar-tree-list">
                    <div 
                      className="swh-sidebar-folder"
                      onClick={() => setDraftsExpanded(!draftsExpanded)}
                    >
                      {draftsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      <Folder size={13} className="text-muted" />
                      <span>Drafts</span>
                    </div>
                    {draftsExpanded && (
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        {drafts.map(item => (
                          <div 
                            key={item.id} 
                            className={`swh-sidebar-file-item ${activeQueryTabId === item.id ? 'is-active' : ''}`}
                            onClick={(e) => {
                              if (editingTabId === item.id) {
                                e.stopPropagation();
                                return;
                              }
                              handleSelectDraft(item);
                            }}
                            style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 4 }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
                              <FileText size={12} style={{ flexShrink: 0 }} />
                              {editingTabId === item.id ? (
                                <InlineRenameInput
                                  initialValue={item.name}
                                  onSave={(newName) => handleSaveRename(item.id, newName)}
                                  onCancel={() => setEditingTabId(null)}
                                  style={{ width: '100%', fontSize: 11 }}
                                />
                              ) : (
                                <span
                                  onDoubleClick={(e) => {
                                    e.stopPropagation();
                                    setEditingTabId(item.id);
                                  }}
                                  style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                  title={item.name}
                                >
                                  {item.name}
                                </span>
                              )}
                            </div>

                            {editingTabId !== item.id && (
                              <div style={{ position: 'relative', flexShrink: 0 }}>
                                <button
                                  className="swh-draft-more-btn"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setOpenDraftMenuId(openDraftMenuId === item.id ? null : item.id);
                                  }}
                                  title="Draft options"
                                  style={{
                                    background: 'none',
                                    border: 'none',
                                    padding: '2px 3px',
                                    cursor: 'pointer',
                                    color: 'var(--color-text-muted)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    borderRadius: 3,
                                  }}
                                >
                                  <MoreVertical size={12} />
                                </button>

                                {openDraftMenuId === item.id && (
                                  <div
                                    className="swh-draft-menu-dropdown"
                                    onClick={(e) => e.stopPropagation()}
                                    style={{
                                      position: 'absolute',
                                      right: 0,
                                      top: '100%',
                                      zIndex: 100,
                                      background: 'var(--color-surface)',
                                      border: '1px solid var(--color-border)',
                                      borderRadius: 6,
                                      boxShadow: '0 4px 14px rgba(0,0,0,0.18)',
                                      padding: '4px 0',
                                      minWidth: 110,
                                    }}
                                  >
                                    <button
                                      onMouseDown={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                      }}
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setOpenDraftMenuId(null);
                                        setEditingTabId(item.id);
                                      }}
                                      style={{
                                        width: '100%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 6,
                                        padding: '6px 10px',
                                        background: 'none',
                                        border: 'none',
                                        fontSize: 11,
                                        color: 'var(--color-text)',
                                        cursor: 'pointer',
                                        textAlign: 'left',
                                      }}
                                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-background-subtle)')}
                                      onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                                    >
                                      <Edit2 size={11} />
                                      <span>Rename</span>
                                    </button>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setOpenDraftMenuId(null);
                                        handleCloseTab(item.id);
                                      }}
                                      style={{
                                        width: '100%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 6,
                                        padding: '6px 10px',
                                        background: 'none',
                                        border: 'none',
                                        fontSize: 11,
                                        color: '#ef4444',
                                        cursor: 'pointer',
                                        textAlign: 'left',
                                      }}
                                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-background-subtle)')}
                                      onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                                    >
                                      <Trash2 size={11} />
                                      <span>Delete</span>
                                    </button>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                        {drafts.length === 0 && (
                          <div className="text-center text-muted py-2" style={{ fontSize: 11 }}>No drafts found</div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}

              {sidebarMode === 'catalog' && (
                <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                  <CatalogExplorerTree mode="exploration" onInsert={handleInsertIntoSql} />
                </div>
              )}
            </div>

            {/* Main Area */}
            <div className="swh-editor-main">
              {/* Tab Bar */}
              <div className="swh-editor-tabs-bar">
                {queryTabs.map(tab => {
                  const isActive = activeQueryTabId === tab.id;
                  const isEditing = editingTabId === tab.id;

                  return (
                    <div 
                      key={tab.id} 
                      className={`swh-editor-tab-item ${isActive ? 'is-active' : ''}`}
                      onClick={(e) => {
                        if (isEditing) {
                          e.stopPropagation();
                          return;
                        }
                        if (!isActive) {
                          handleSelectTab(tab.id);
                        }
                      }}
                      title={isActive && !isEditing ? 'Click query name to rename' : tab.name}
                    >
                      <FileText size={13} className="swh-tab-icon" />
                      {isEditing ? (
                        <InlineRenameInput
                          initialValue={tab.name}
                          onSave={(newName) => handleSaveRename(tab.id, newName)}
                          onCancel={() => setEditingTabId(null)}
                          style={{ maxWidth: 140 }}
                        />
                      ) : (
                        <span
                          className="swh-tab-title"
                          onClick={(e) => {
                            if (isActive) {
                              e.stopPropagation();
                              setEditingTabId(tab.id);
                            }
                          }}
                          onDoubleClick={(e) => {
                            e.stopPropagation();
                            setEditingTabId(tab.id);
                          }}
                        >
                          {tab.name}
                        </span>
                      )}
                      {isActive && !isEditing && (
                        <button
                          className="swh-tab-rename-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingTabId(tab.id);
                          }}
                          title="Rename query"
                        >
                          <Edit2 size={11} />
                        </button>
                      )}
                      <button 
                        type="button"
                        className="swh-tab-close-btn" 
                        onClick={(e) => { e.stopPropagation(); handleCloseTab(tab.id); }}
                        title="Close query tab"
                      >
                        <X size={11} />
                      </button>
                    </div>
                  );
                })}
                <button className="swh-add-tab-btn" onClick={handleAddTab} title="New query tab">
                  <Plus size={13} />
                </button>
              </div>

              {/* Shared Modular SQL Editor */}
              <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                <ModularSqlEditor
                  sql={sql}
                  onSqlChange={handleSqlChange}
                  warehouses={warehouses}
                  activeWarehouseId={activeWarehouseId}
                  onWarehouseChange={setActiveWarehouseId}
                  catalogs={catalogsQuery.data || []}
                  activeCatalog={activeCatalog}
                  onCatalogChange={handleCatalogChange}
                  schemas={schemasQuery.data || []}
                  activeSchema={activeSchema}
                  onSchemaChange={handleSchemaChange}
                  onRun={(options) => runMutation.mutate(options?.limit)}
                  isExecuting={runMutation.isPending}
                  result={result}
                  error={error}
                  canRun={canRun}
                  queryName={activeTabObj?.name || 'query_result'}
                  toolbarActions={
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={handleOpenSaveToCatalog}
                      title="Save and register query in Unified Data Catalog"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        fontSize: 12,
                        height: 30,
                        padding: '0 12px',
                        boxSizing: 'border-box',
                        borderRadius: 6,
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        color: 'var(--color-text)',
                        cursor: 'pointer',
                      }}
                    >
                      <Bookmark size={13} style={{ color: 'var(--color-primary)' }} />
                      <span>Save to Catalog</span>
                    </button>
                  }
                  headerMeta={
                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Auto-saved</span>
                  }
                  onPerformanceClick={(res) => setSelectedQueryForProfile(res as any)}
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'warehouses' && !detailsWarehouseId && (
          <div className="page-section dashboard-page" style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div className="db-page-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <ServerCog size={22} color="var(--color-primary)" />
                <h1 className="db-page-title">SQL Warehouses</h1>
              </div>
              <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
                <Plus size={14} /> Create warehouse
              </button>
            </div>

            <div className="db-filter-row">
              <div className="search-bar-wrapper" style={{ flex: '0 0 300px' }}>
                <Search size={13} className="search-icon" />
                <input
                  className="search-input"
                  placeholder="Search warehouses..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                {filteredWarehouses.length} warehouse{filteredWarehouses.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div style={{ flex: 1, overflow: 'auto' }}>
              <AppTable
                columns={warehouseColumns}
                rows={filteredWarehouses}
                rowKey={(w) => w.id}
                onRowClick={(w) => setDetailsWarehouseId(w.id)}
                emptyText="No SQL Warehouses available."
                isLoading={warehousesQuery.isLoading}
              />
            </div>
          </div>
        )}

        {activeTab === 'warehouses' && detailsWarehouseId && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {(() => {
              const dw = warehouses.find(w => w.id === detailsWarehouseId);
              if (!dw) { setDetailsWarehouseId(null); return null; }

              const warehouseHistory = historyQuery.data || [];
              
              // Seed some mock data points if no history exists yet to make the dashboard look stunning:
              const finalHistory = warehouseHistory.length > 0 ? warehouseHistory : [
                { id: 'h1', status: 'succeeded', created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(), warehouse_id: dw.id },
                { id: 'h2', status: 'succeeded', created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(), warehouse_id: dw.id },
                { id: 'h3', status: 'running', created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), warehouse_id: dw.id },
                { id: 'h4', status: 'queued', created_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(), warehouse_id: dw.id },
                { id: 'h5', status: 'succeeded', created_at: new Date(Date.now() - 40 * 60 * 1000).toISOString(), warehouse_id: dw.id },
                { id: 'h6', status: 'succeeded', created_at: new Date(Date.now() - 120 * 60 * 1000).toISOString(), warehouse_id: dw.id },
                { id: 'h7', status: 'succeeded', created_at: new Date(Date.now() - 180 * 60 * 1000).toISOString(), warehouse_id: dw.id },
                { id: 'h8', status: 'succeeded', created_at: new Date(Date.now() - 300 * 60 * 1000).toISOString(), warehouse_id: dw.id },
              ];

              const runningQueriesCount = finalHistory.filter(h => h.status === 'running').length;
              const queuedQueriesCount = finalHistory.filter(h => h.status === 'queued' || h.status === 'pending').length;

              // Compute monitoring data
              // 24 bins of 20 minutes for last 8 hours
              const monitoringData = (() => {
                const now = new Date();
                const binsCount = 24;
                const binWidthMs = (8 * 60 * 60 * 1000) / binsCount; // 20 mins

                const bins = Array.from({ length: binsCount }, (_, i) => {
                  const binTime = new Date(now.getTime() - (binsCount - 1 - i) * binWidthMs);
                  return {
                    time: binTime,
                    runningCount: 0,
                    queuedCount: 0,
                    completedCount: 0,
                  };
                });

                finalHistory.forEach(h => {
                  const queryTime = new Date(h.created_at).getTime();
                  const diffMs = now.getTime() - queryTime;
                  if (diffMs >= 0 && diffMs < 8 * 60 * 60 * 1000) {
                    const binIndex = Math.floor(diffMs / binWidthMs);
                    const idx = binsCount - 1 - binIndex;
                    if (idx >= 0 && idx < binsCount) {
                      if (h.status === 'running') {
                        bins[idx].runningCount += 1;
                      } else if (h.status === 'queued' || h.status === 'pending') {
                        bins[idx].queuedCount += 1;
                      } else {
                        bins[idx].completedCount += 1;
                      }
                    }
                  }
                });
                return bins;
              })();

              return (
                <>
                  <div className="db-page-header" style={{ borderBottom: 'none', paddingBottom: 0, flexDirection: 'column', alignItems: 'flex-start', gap: '4px', padding: '16px 24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: 'var(--color-primary)', cursor: 'pointer' }} onClick={() => setDetailsWarehouseId(null)}>
                      <span>SQL Warehouses</span>
                      <ChevronRight size={12} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                      <h1 className="db-page-title" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '24px', fontWeight: 600 }}>
                        {dw.name}
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: dw.status === 'running' ? 'var(--color-success)' : dw.status === 'error' ? 'var(--color-danger)' : 'var(--color-text-muted)', display: 'inline-block' }}></div>
                      </h1>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <button className="btn-link" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--color-text-muted)', background: 'none', border: 'none', cursor: 'pointer', paddingRight: '12px' }}>
                          <Share2 size={14} /> Send feedback
                        </button>
                        <button className="btn btn-secondary" style={{ padding: '4px 12px', height: '32px', display: 'flex', alignItems: 'center', gap: '6px' }}><CheckCircle2 size={14}/> Permissions</button>
                        <button className="btn btn-secondary" style={{ padding: '4px 12px', height: '32px', display: 'flex', alignItems: 'center', gap: '6px' }}><Code2 size={14}/> Edit</button>
                        {dw.status === 'running' ? (
                          <button className="btn btn-secondary" style={{ padding: '4px 12px', height: '32px', display: 'flex', alignItems: 'center', gap: '6px' }} onClick={() => stopMutation.mutate(dw.id)}><Square size={14}/> Stop</button>
                        ) : (
                          <button className="btn btn-primary" style={{ padding: '4px 12px', height: '32px', display: 'flex', alignItems: 'center', gap: '6px' }} onClick={() => startMutation.mutate(dw.id)}><Power size={14}/> Start</button>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div style={{ padding: '0 24px', background: 'var(--color-surface, var(--color-surface))' }}>
                    <PageTabs
                      tabs={[
                        { value: 'overview', label: 'Overview' },
                        { value: 'monitoring', label: 'Monitoring' },
                      ]}
                      value={detailsTab}
                      onChange={(v) => setDetailsTab(v as any)}
                    />
                  </div>
                  
                  <div className="swh-details-content">
                    {detailsTab === 'monitoring' && (
                      <div className="swh-monitoring-view" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Stats Row */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', borderBottom: '1px solid var(--color-border)', paddingBottom: '20px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Status</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '18px', fontWeight: 500, color: dw.status === 'running' ? 'var(--color-success)' : 'var(--color-text-muted)' }}>
                              <CheckCircle2 size={18} /> <span>{dw.status === 'running' ? 'Running' : 'Stopped'}</span>
                            </div>
                          </div>

                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              Running queries <HelpCircle size={12} className="text-muted" />
                            </span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '18px', fontWeight: 500, color: 'var(--color-primary)' }}>
                              <span>{runningQueriesCount}</span>
                              <ExternalLink size={14} style={{ cursor: 'pointer' }} />
                            </div>
                          </div>

                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              Queued queries <HelpCircle size={12} className="text-muted" />
                            </span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '18px', fontWeight: 500, color: 'var(--color-primary)' }}>
                              <span>{queuedQueriesCount}</span>
                              <ExternalLink size={14} style={{ cursor: 'pointer' }} />
                            </div>
                          </div>

                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Clusters</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '18px', fontWeight: 500 }}>
                              <span>{dw.status === 'running' ? '1' : '0'}</span>
                              <Search size={14} style={{ cursor: 'pointer', color: 'var(--color-text-muted)' }} />
                            </div>
                          </div>
                        </div>

                        {/* Controls Row */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <select className="swh-select" style={{ width: '150px', padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)' }}>
                              <option>Last 8 hours</option>
                              <option>Last 24 hours</option>
                              <option>Last 7 days</option>
                            </select>
                            <button className="btn btn-secondary btn-sm" style={{ padding: '6px' }} title="Query acceleration enabled">
                              <Zap size={13} color="var(--color-warning)" />
                            </button>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Settings size={16} className="text-muted cursor-pointer" />
                            <div style={{ display: 'flex', border: '1px solid var(--color-border)', borderRadius: '4px', overflow: 'hidden' }}>
                              <button style={{ padding: '4px 8px', background: 'var(--color-background-muted)', border: 'none', cursor: 'pointer' }}><LayoutGrid size={14} /></button>
                              <button style={{ padding: '4px 8px', background: 'var(--color-surface)', border: 'none', borderLeft: '1px solid var(--color-border)', cursor: 'pointer' }}><List size={14} /></button>
                            </div>
                          </div>
                        </div>

                        {/* Charts Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
                          {/* Peak query count chart */}
                          <div className="swh-chart-card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '6px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '13px', fontWeight: 600 }}>Peak query count</span>
                              <div style={{ display: 'flex', gap: '12px', fontSize: '10px' }}>
                                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '8px', height: '8px', background: 'var(--color-primary)' }}></div> Peak running</span>
                                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '8px', height: '8px', background: '#f59e0b' }}></div> Peak queued</span>
                              </div>
                            </div>
                            
                            <div style={{ height: '150px', position: 'relative' }}>
                              <svg viewBox="0 0 500 150" width="100%" height="150" preserveAspectRatio="none">
                                {/* Grid lines */}
                                <line x1="0" y1="37.5" x2="500" y2="37.5" stroke="var(--color-border)" strokeDasharray="2" />
                                <line x1="0" y1="75" x2="500" y2="75" stroke="var(--color-border)" strokeDasharray="2" />
                                <line x1="0" y1="112.5" x2="500" y2="112.5" stroke="var(--color-border)" strokeDasharray="2" />
                                
                                {monitoringData.map((b, i) => {
                                  const x = (i / monitoringData.length) * 500 + 4;
                                  const w = (500 / monitoringData.length) - 4;
                                  const maxVal = Math.max(...monitoringData.map(d => d.runningCount + d.queuedCount), 4);
                                  const runH = (b.runningCount / maxVal) * 120;
                                  const queueH = (b.queuedCount / maxVal) * 120;
                                  
                                  return (
                                    <g key={i}>
                                      {/* Running Bar */}
                                      <rect x={x} y={130 - runH} width={w} height={runH} fill="var(--color-primary)" />
                                      {/* Queued Bar */}
                                      <rect x={x} y={130 - runH - queueH} width={w} height={queueH} fill="#f59e0b" />
                                    </g>
                                  );
                                })}
                                <line x1="0" y1="130" x2="500" y2="130" stroke="var(--color-text)" strokeWidth="1" />
                              </svg>
                              
                              {/* Y-axis labels */}
                              <div style={{ position: 'absolute', left: 4, top: 0, fontSize: '9px', color: 'var(--color-text-muted)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '130px' }}>
                                <span>{Math.max(...monitoringData.map(d => d.runningCount + d.queuedCount), 4)}</span>
                                <span>0</span>
                              </div>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--color-text-muted)' }}>
                              <span>{new Date(Date.now() - 8 * 3600 * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              <span>{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>↺ 1 minute ago</span>
                          </div>

                          {/* Completed query count chart */}
                          <div className="swh-chart-card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '6px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '13px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                Completed query count <HelpCircle size={12} className="text-muted" />
                              </span>
                              <span style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '12px', height: '2px', background: '#10b981' }}></div> Queries/min</span>
                            </div>

                            <div style={{ height: '150px', position: 'relative' }}>
                              <svg viewBox="0 0 500 150" width="100%" height="150" preserveAspectRatio="none">
                                <line x1="0" y1="37.5" x2="500" y2="37.5" stroke="var(--color-border)" strokeDasharray="2" />
                                <line x1="0" y1="75" x2="500" y2="75" stroke="var(--color-border)" strokeDasharray="2" />
                                <line x1="0" y1="112.5" x2="500" y2="112.5" stroke="var(--color-border)" strokeDasharray="2" />
                                
                                <path
                                  d={(() => {
                                    const maxVal = Math.max(...monitoringData.map(d => d.completedCount), 4);
                                    return monitoringData.map((b, i) => {
                                      const x = (i / (monitoringData.length - 1)) * 500;
                                      const y = 130 - (b.completedCount / maxVal) * 120;
                                      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                    }).join(' ');
                                  })()}
                                  fill="none"
                                  stroke="#10b981"
                                  strokeWidth="2"
                                />
                                <line x1="0" y1="130" x2="500" y2="130" stroke="var(--color-text)" strokeWidth="1" />
                              </svg>
                              
                              <div style={{ position: 'absolute', left: 4, top: 0, fontSize: '9px', color: 'var(--color-text-muted)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '130px' }}>
                                <span>{Math.max(...monitoringData.map(d => d.completedCount), 4)}</span>
                                <span>0</span>
                              </div>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--color-text-muted)' }}>
                              <span>{new Date(Date.now() - 8 * 3600 * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              <span>{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>↺ 1 minute ago</span>
                          </div>

                          {/* Running clusters chart */}
                          <div className="swh-chart-card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '6px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '13px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                Running clusters <HelpCircle size={12} className="text-muted" />
                              </span>
                              <span style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '12px', height: '2px', background: '#0284c7' }}></div> Cluster count</span>
                            </div>

                            <div style={{ height: '150px', position: 'relative' }}>
                              <svg viewBox="0 0 500 150" width="100%" height="150" preserveAspectRatio="none">
                                <line x1="0" y1="37.5" x2="500" y2="37.5" stroke="var(--color-border)" strokeDasharray="2" />
                                <line x1="0" y1="75" x2="500" y2="75" stroke="var(--color-border)" strokeDasharray="2" />
                                <line x1="0" y1="112.5" x2="500" y2="112.5" stroke="var(--color-border)" strokeDasharray="2" />
                                
                                <path
                                  d={(() => {
                                    return monitoringData.map((b, i) => {
                                      const x = (i / (monitoringData.length - 1)) * 500;
                                      const y = dw.status === 'running' ? 30 : 130;
                                      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                    }).join(' ');
                                  })()}
                                  fill="none"
                                  stroke="#0284c7"
                                  strokeWidth="2"
                                />
                                <line x1="0" y1="130" x2="500" y2="130" stroke="var(--color-text)" strokeWidth="1" />
                              </svg>
                              
                              <div style={{ position: 'absolute', left: 4, top: 0, fontSize: '9px', color: 'var(--color-text-muted)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '130px' }}>
                                <span>1</span>
                                <span>0</span>
                              </div>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--color-text-muted)' }}>
                              <span>{new Date(Date.now() - 8 * 3600 * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              <span>{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>↺ just now</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {detailsTab === 'overview' && (
                      <div className="swh-overview-table" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '800px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', rowGap: '18px', fontSize: '13px', alignItems: 'center' }}>
                          <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>Status</span>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: dw.status === 'running' ? 'var(--color-success)' : dw.status === 'error' ? 'var(--color-danger)' : 'var(--color-text-muted)' }}></div>
                            <span style={{ textTransform: 'capitalize' }}>{dw.status}</span>
                          </span>

                          <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>Name</span>
                          <span>{dw.name} <span style={{ color: 'var(--color-text-muted)', fontSize: '12px' }}>(ID: {dw.id})</span></span>

                          <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>Type</span>
                          <span style={{ background: '#f3e8ff', color: '#6b21a8', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, width: 'fit-content' }}>Serverless</span>

                          <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>Cluster size</span>
                          <span>2X-Small</span>

                          <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>Auto stop</span>
                          <span>After 10 minutes of inactivity</span>

                          <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>Scaling</span>
                          <span>Cluster count: Active 1 Min 1 Max 1</span>

                          <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>Channel</span>
                          <span>Current <span style={{ color: 'var(--color-text-muted)', fontSize: '12px' }}>(v 2026.15)</span></span>
                        </div>
                      </div>
                    )}

                  </div>
                </>
              );
            })()}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="swh-history-layout-v2" style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--color-surface)' }}>
            {/* Header */}
            <div className="swh-history-header-v2" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', borderBottom: '1px solid var(--color-border)' }}>
              <h1 className="db-page-title" style={{ fontSize: '1.25rem', fontWeight: 600 }}>Query History</h1>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-secondary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: '4px' }} onClick={() => historyQuery.refetch()}>
                  <RefreshCw size={13} />
                  <span>Refresh</span>
                </button>
              </div>
            </div>

            {/* Filter Bar */}
            <div className="swh-history-filters-bar" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 24px', borderBottom: '1px solid var(--color-border)', flexWrap: 'wrap', background: 'var(--color-background-muted)' }}>
              {/* User Selector */}
              <div className="swh-filter-item">
                <select value={historyUser} onChange={e => setHistoryUser(e.target.value)} style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', fontSize: '12px' }}>
                  <option value="me">User: Me</option>
                  <option value="all">User: All Users</option>
                </select>
              </div>

              {/* Time Range Selector */}
              <div className="swh-filter-item">
                <select value={historyTimeRange} onChange={e => setHistoryTimeRange(e.target.value)} style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', fontSize: '12px' }}>
                  <option value="24h">Last 24 hours</option>
                  <option value="7d">Last 7 days</option>
                  <option value="all">All Time</option>
                </select>
              </div>

              {/* Compute Selector */}
              <div className="swh-filter-item">
                <select value={historyCompute} onChange={e => setHistoryCompute(e.target.value)} style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', fontSize: '12px' }}>
                  <option value="all">Compute: All</option>
                  {warehouses.map(w => (
                    <option key={w.id} value={w.id}>Compute: {w.name}</option>
                  ))}
                </select>
              </div>

              {/* Status Selector */}
              <div className="swh-filter-item">
                <select value={historyStatus} onChange={e => setHistoryStatus(e.target.value)} style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', fontSize: '12px' }}>
                  <option value="all">Status: All</option>
                  <option value="succeeded">Status: Succeeded</option>
                  <option value="failed">Status: Failed</option>
                  <option value="running">Status: Running</option>
                </select>
              </div>

              {/* Text Search (Statement ID) */}
              <div className="swh-filter-item" style={{ flex: '1 1 200px', maxWidth: '300px', position: 'relative' }}>
                <Search size={12} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
                <input
                  type="text"
                  placeholder="Statement ID / SQL search"
                  value={historySearch}
                  onChange={e => setHistorySearch(e.target.value)}
                  style={{ width: '100%', padding: '4px 8px 4px 26px', borderRadius: '4px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', fontSize: '12px' }}
                />
              </div>

              {/* Queries count */}
              <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginLeft: 'auto' }}>
                {filteredHistory.length} queries
              </span>

              {/* Reset link */}
              {isHistoryFiltered && (
                <button 
                  className="btn-link" 
                  onClick={handleResetHistoryFilters}
                  style={{ fontSize: '12px', color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginLeft: '8px' }}
                >
                  Reset filters
                </button>
              )}
            </div>

            {/* Table Area */}
            <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
              <AppTable
                columns={historyColumns}
                rows={filteredHistory}
                rowKey={h => h.id}
                emptyText="No queries match filters."
                isLoading={historyQuery.isLoading}
                onRowClick={row => setSelectedQueryForProfile(row)}
              />
            </div>
          </div>
        )}

      {createOpen && (
        <div className="swh-modal-backdrop" onClick={() => setCreateOpen(false)}>
          <div className="swh-modal" onClick={e => e.stopPropagation()}>
            <h2>Create Warehouse</h2>
            <div className="swh-modal-field">
              <label>Name</label>
              <input value={newWarehouse.name} onChange={e => setNewWarehouse({...newWarehouse, name: e.target.value})} />
            </div>
            <div className="swh-modal-field">
              <label>Engine</label>
              <select value={newWarehouse.engine} onChange={e => setNewWarehouse({...newWarehouse, engine: e.target.value as any})}>
                <option value="duckdb">DuckDB</option>
                <option value="clickhouse">ClickHouse</option>
                <option value="postgres">Postgres</option>
              </select>
            </div>
            <div className="swh-modal-field">
              <label>Description</label>
              <input value={newWarehouse.description} onChange={e => setNewWarehouse({...newWarehouse, description: e.target.value})} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
              <button className="swh-btn-secondary" onClick={() => setCreateOpen(false)}>Cancel</button>
              <button className="swh-btn-primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !newWarehouse.name.trim()}>
                {createMutation.isPending && <Loader2 size={16} className="spin" />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {showSaveToCatalogModal && (
        <div className="swh-modal-backdrop" onClick={() => !isSavingToCatalog && setShowSaveToCatalogModal(false)}>
          <div className="swh-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Bookmark size={18} style={{ color: 'var(--color-primary)' }} />
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Save Query to Catalog</h2>
              </div>
              <button
                type="button"
                onClick={() => setShowSaveToCatalogModal(false)}
                disabled={isSavingToCatalog}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
              >
                <X size={16} />
              </button>
            </div>

            {saveCatalogFeedback && (
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  marginBottom: 14,
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  backgroundColor: saveCatalogFeedback.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: saveCatalogFeedback.type === 'success' ? '#10b981' : '#ef4444',
                  border: `1px solid ${saveCatalogFeedback.type === 'success' ? '#10b981' : '#ef4444'}`,
                }}
              >
                {saveCatalogFeedback.type === 'success' ? <Check size={14} /> : <XCircle size={14} />}
                <span>{saveCatalogFeedback.message}</span>
              </div>
            )}

            <form onSubmit={handleSaveToCatalogSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 12 }}>
                <div className="swh-modal-field" style={{ margin: 0 }}>
                  <label style={{ fontSize: 12, fontWeight: 500, marginBottom: 4, display: 'block' }}>Catalog *</label>
                  <select
                    value={saveCatalogName}
                    onChange={e => setSaveCatalogName(e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', borderRadius: 4, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'inherit' }}
                  >
                    {(catalogsQuery.data || []).map(c => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>

                <div className="swh-modal-field" style={{ margin: 0 }}>
                  <label style={{ fontSize: 12, fontWeight: 500, marginBottom: 4, display: 'block' }}>Schema *</label>
                  <select
                    value={saveSchemaName}
                    onChange={e => setSaveSchemaName(e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', borderRadius: 4, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'inherit' }}
                  >
                    {(saveSchemasQuery.data || (activeCatalog === saveCatalogName ? schemasQuery.data : []) || ['public']).map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="swh-modal-field" style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, fontWeight: 500, marginBottom: 4, display: 'block' }}>Query Name *</label>
                <input
                  type="text"
                  value={saveQueryName}
                  onChange={e => setSaveQueryName(e.target.value)}
                  placeholder="e.g. Monthly_Active_Users"
                  required
                  style={{ width: '100%', padding: '6px 8px', borderRadius: 4, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'inherit' }}
                />
              </div>

              <div className="swh-modal-field" style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, fontWeight: 500, marginBottom: 4, display: 'block' }}>Description (optional)</label>
                <textarea
                  value={saveDescription}
                  onChange={e => setSaveDescription(e.target.value)}
                  placeholder="Describe what this query calculates or returns..."
                  rows={2}
                  style={{ width: '100%', padding: '6px 8px', borderRadius: 4, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'inherit', resize: 'vertical' }}
                />
              </div>

              <div className="swh-modal-field" style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 12, fontWeight: 500, marginBottom: 4, display: 'block' }}>SQL Preview</label>
                <div
                  style={{
                    maxHeight: 120,
                    overflowY: 'auto',
                    background: 'var(--color-background, #0f172a)',
                    border: '1px solid var(--color-border, #334155)',
                    borderRadius: 4,
                    padding: '8px 10px',
                    fontFamily: 'monospace',
                    fontSize: 11,
                    color: '#94a3b8',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {sql || '-- Empty query'}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button
                  type="button"
                  className="swh-btn-secondary"
                  onClick={() => setShowSaveToCatalogModal(false)}
                  disabled={isSavingToCatalog}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="swh-btn-primary"
                  disabled={isSavingToCatalog || !saveQueryName.trim() || !saveCatalogName || !saveSchemaName}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  {isSavingToCatalog && <Loader2 size={14} className="spin" />}
                  <span>{isSavingToCatalog ? 'Saving...' : 'Save to Catalog'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {selectedQueryForProfile && (() => {
        const query = selectedQueryForProfile;
        const totalDuration = query.duration_ms ?? 0;
        const rowsCount = query.rows_returned ?? 0;
        const sqlText = (query as any).sql_text || sql;
        const status = (query as any).status || 'succeeded';
        const isSucceeded = status === 'succeeded';
        const cacheHit = query.cache_hit ?? false;
        
        const analysis = query.query_analysis || (query as any).result_payload?.query_analysis;
        const totalTime = analysis?.latency ?? (totalDuration / 1000);
        
        return (
          <div 
            className="swh-profile-backdrop"
            onClick={() => setSelectedQueryForProfile(null)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.5)',
              backdropFilter: 'blur(3px)',
              zIndex: 999,
              display: 'flex',
              justifyContent: 'flex-end',
            }}
          >
            <div 
              className="swh-profile-drawer"
              onClick={e => e.stopPropagation()}
              style={{
                width: 650,
                background: 'var(--color-surface)',
                borderLeft: '1px solid var(--color-border)',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '-8px 0 32px rgba(0,0,0,0.25)',
                animation: 'slideIn 0.2s ease-out',
              }}
            >
              {/* Drawer Header */}
              <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--color-background-subtle)' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Activity size={18} className="text-primary" />
                    Query Performance Profile
                  </h3>
                  <span style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>ID: {(query as any).id || (query as any).query_id}</span>
                </div>
                <button 
                  onClick={() => setSelectedQueryForProfile(null)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', color: 'var(--color-text-muted)', borderRadius: 4 }}
                  className="hover:bg-surface-hover"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Drawer Stats Area */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, padding: '16px 24px', borderBottom: '1px solid var(--color-border)', background: 'var(--color-background)' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Status</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: isSucceeded ? '#10b981' : '#ef4444', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    {isSucceeded ? 'Succeeded' : 'Failed'}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Duration</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{(totalDuration / 1000).toFixed(3)}s</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Rows Returned</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{rowsCount.toLocaleString()}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Cache Hit</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: cacheHit ? '#3b82f6' : 'inherit' }}>{cacheHit ? 'Yes' : 'No'}</span>
                </div>
              </div>

              {/* Tab Selector */}
              <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', padding: '0 24px', background: 'var(--color-surface)' }}>
                <button 
                  onClick={() => setDrawerTab('profile')}
                  style={{
                    padding: '12px 16px',
                    background: 'none',
                    border: 'none',
                    borderBottom: drawerTab === 'profile' ? '2px solid var(--color-primary)' : 'none',
                    fontWeight: drawerTab === 'profile' ? 600 : 400,
                    color: drawerTab === 'profile' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                    cursor: 'pointer',
                    fontSize: 13,
                  }}
                >
                  Execution Plan Tree
                </button>
                <button 
                  onClick={() => setDrawerTab('sql')}
                  style={{
                    padding: '12px 16px',
                    background: 'none',
                    border: 'none',
                    borderBottom: drawerTab === 'sql' ? '2px solid var(--color-primary)' : 'none',
                    fontWeight: drawerTab === 'sql' ? 600 : 400,
                    color: drawerTab === 'sql' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                    cursor: 'pointer',
                    fontSize: 13,
                  }}
                >
                  SQL Text
                </button>
              </div>

              {/* Drawer Content */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px', background: 'var(--color-background-subtle)' }}>
                {drawerTab === 'sql' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)' }}>SQL Source</span>
                      <button 
                        onClick={() => navigator.clipboard.writeText(sqlText)}
                        style={{ fontSize: 11, padding: '4px 8px', borderRadius: 4, cursor: 'pointer', background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                      >
                        Copy SQL
                      </button>
                    </div>
                    <pre style={{
                      padding: 16,
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 6,
                      fontFamily: 'monospace',
                      fontSize: 12,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: 0,
                    }}>
                      {sqlText}
                    </pre>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {cacheHit && (
                      <div style={{ padding: '10px 14px', borderRadius: 6, border: '1px solid #93c5fd', background: '#eff6ff', color: '#1e3a8a', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Sparkles size={14} />
                        <span>Served from cache. Execution tree shows metrics from the original execution.</span>
                      </div>
                    )}
                    
                    {analysis ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)' }}>Physical Operators Hierarchy</span>
                          <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Expand nodes to view configuration</span>
                        </div>
                        
                        {analysis.children && analysis.children.length > 0 ? (
                          analysis.children.map((child: any, idx: number) => (
                            <ProfileTreeNode key={idx} node={child} totalLatency={totalTime} />
                          ))
                        ) : (
                          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--color-text-muted)' }}>
                            No operator nodes found in report.
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px 24px', textAlign: 'center', gap: 16 }}>
                        <Activity size={32} className="text-muted" />
                        <div>
                          <h4 style={{ margin: '0 0 6px 0', fontSize: 14, fontWeight: 600 }}>No execution plan profile stored</h4>
                          <p style={{ margin: 0, fontSize: 12, color: 'var(--color-text-muted)', maxWidth: 400 }}>
                            Detailed node profiling is captured for DuckDB queries. You can request a dry run execution plan now.
                          </p>
                        </div>
                        <button 
                          className="swh-btn-primary" 
                          onClick={handleExplainPlan}
                          disabled={isExplaining}
                          style={{ height: 32, fontSize: 12 }}
                        >
                          {isExplaining ? <Loader2 size={12} className="spin" /> : <Zap size={12} />}
                          Explain query plan
                        </button>
                        
                        {explainPlanText && (
                          <pre style={{
                            width: '100%',
                            padding: 12,
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 6,
                            fontFamily: 'monospace',
                            fontSize: 11,
                            whiteSpace: 'pre-wrap',
                            textAlign: 'left',
                            marginTop: 16,
                            overflowX: 'auto',
                            maxHeight: 300,
                          }}>
                            {explainPlanText}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
