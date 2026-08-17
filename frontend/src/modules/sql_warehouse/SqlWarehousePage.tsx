import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Database, Loader2, Play, Plus, Power, Square, TerminalSquare, Code2, Server, History, CheckCircle2, ChevronRight, Activity, Clock, Search, ServerCog, Folder, ChevronDown, Star, Sparkles, Download, Maximize2, BarChart2, Settings, MoreVertical, Share2, FileText, RefreshCw, XCircle, HelpCircle, ExternalLink, Zap, LayoutGrid, List, X, GitBranch } from 'lucide-react';
import api from '@/lib/api';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import { PageTabs } from '@/components/common/PageTabs';
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
  query: (warehouse_id: string, sql: string, catalog?: string, schema_name?: string, source?: string) => api.post<QueryResult>('/sql/query', { warehouse_id, sql, max_rows: 1000, catalog, schema_name, source }).then((r) => r.data),
  validate: (sql: string) => api.post<{ valid: boolean; error?: string; statement_count?: number }>('/sql/validate', { sql }).then((r) => r.data),
  history: (warehouse_id?: string, scope: 'me' | 'all' = 'me') => api.get<{ records: HistoryRecord[] }>('/sql/history', { params: { warehouse_id, limit: 25, scope } }).then((r) => r.data.records),
  catalogs: () => api.get<{ catalogs: { name: string; catalog_type: string }[] }>('/sql-warehouse/catalog/catalogs').then((r) => r.data.catalogs),
  schemas: (catalog: string) => api.get<{ schemas: string[] }>('/sql-warehouse/catalog/schemas', { params: { catalog } }).then((r) => r.data.schemas),
  tables: (catalog: string, schema: string) => api.get<{ tables: string[] }>('/sql-warehouse/catalog/tables', { params: { catalog, schema } }).then((r) => r.data.tables),
};

export default function SqlWarehousePage() {
  const qc = useQueryClient();
  const { tab } = useParams();
  const activeTab = tab || 'editor';
  const navigate = useNavigate();
  
  const [search, setSearch] = useState('');
  
  const [detailsWarehouseId, setDetailsWarehouseId] = useState<string | null>(null);
  const [detailsTab, setDetailsTab] = useState<'overview' | 'monitoring'>('monitoring');
  
  const [activeWarehouseId, setActiveWarehouseId] = useState('');
  const [activeCatalog, setActiveCatalog] = useState('');
  const [activeSchema, setActiveSchema] = useState('');
  const [sql, setSql] = useState("SELECT 1 AS id, 'CompassX SQL Warehouse' AS name;");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState('');

  const [queryTabs, setQueryTabs] = useState([
    { id: 'q1', name: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 100;", sql: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 100;", catalog: 'development_catalog', schema: 'alarm_manager' },
    { id: 'q2', name: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' where error_id = 5961229;", sql: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' where error_id = 5961229;", catalog: 'development_catalog', schema: 'alarm_manager' }
  ]);
  const [activeQueryTabId, setActiveQueryTabId] = useState('q1');
  const [sidebarSearch, setSidebarSearch] = useState('');
  const [draftsExpanded, setDraftsExpanded] = useState(true);

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

  useEffect(() => {
    if (activeTabObj) {
      setSql(activeTabObj.sql);
      if (activeTabObj.catalog) setActiveCatalog(activeTabObj.catalog);
      if (activeTabObj.schema) setActiveSchema(activeTabObj.schema);
    }
  }, [activeQueryTabId]);

  const handleSqlChange = (newSql: string) => {
    setSql(newSql);
    setQueryTabs(prev => prev.map(t => {
      if (t.id === activeQueryTabId) {
        const trimmed = newSql.trim();
        const firstLine = trimmed.split('\n')[0] || 'New Query';
        const name = firstLine.length > 45 ? firstLine.slice(0, 42) + '...' : firstLine;
        return { ...t, sql: newSql, name };
      }
      return t;
    }));
  };

  const handleSelectDraft = (item: { id: string; name: string; sql: string; catalog?: string; schema?: string }) => {
    if (queryTabs.some(t => t.id === item.id)) {
      setActiveQueryTabId(item.id);
    } else {
      setQueryTabs(prev => [...prev, { id: item.id, name: item.name, sql: item.sql, catalog: item.catalog || 'development_catalog', schema: item.schema || 'alarm_manager' }]);
      setActiveQueryTabId(item.id);
    }
  };

  const handleAddTab = () => {
    const newId = 'q_' + Date.now();
    const name = `select * from ...`;
    const newTab = { id: newId, name, sql: 'select * from ...', catalog: activeCatalog, schema: activeSchema };
    setQueryTabs(prev => [...prev, newTab]);
    setActiveQueryTabId(newId);
  };

  const handleCloseTab = (id: string) => {
    if (queryTabs.length <= 1) return;
    const activeIndex = queryTabs.findIndex(t => t.id === activeQueryTabId);
    const newTabs = queryTabs.filter(t => t.id !== id);
    setQueryTabs(newTabs);
    if (activeQueryTabId === id) {
      const nextActive = newTabs[Math.max(activeIndex - 1, 0)];
      setActiveQueryTabId(nextActive.id);
    }
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
  const tablesQuery = useQuery({ queryKey: ['swh-tables', activeCatalog, activeSchema], queryFn: () => warehouseApi.tables(activeCatalog, activeSchema), enabled: !!activeCatalog && !!activeSchema });
  const historyQuery = useQuery({
    queryKey: ['swh-history', detailsWarehouseId || 'all', historyUser],
    queryFn: () => warehouseApi.history(detailsWarehouseId || undefined, historyUser as 'me' | 'all')
  });

  const drafts = useMemo(() => {
    const items = [
      { id: 'mock1', name: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 10;", sql: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 10;" },
      { id: 'mock2', name: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 20;", sql: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 20;" },
      { id: 'mock3', name: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 30;", sql: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 30;" },
      { id: 'mock4', name: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 40;", sql: "select * from 'development_catalog'.'alarm_manager'.'alarm_error_v1' limit 40;" },
      ...queryTabs
    ];
    const seen = new Set();
    const uniqueItems = [];
    for (const item of items) {
      if (!seen.has(item.name)) {
        seen.add(item.name);
        uniqueItems.push(item);
      }
    }
    return uniqueItems.filter(item => !sidebarSearch || item.name.toLowerCase().includes(sidebarSearch.toLowerCase()));
  }, [queryTabs, sidebarSearch]);

  useEffect(() => {
    if (!activeWarehouseId && warehouses[0]) setActiveWarehouseId(warehouses[0].id);
  }, [activeWarehouseId, warehouses]);

  useEffect(() => {
    const firstCatalog = catalogsQuery.data?.[0]?.name;
    if (!activeCatalog && firstCatalog) setActiveCatalog(firstCatalog);
  }, [activeCatalog, catalogsQuery.data]);

  useEffect(() => {
    const firstSchema = schemasQuery.data?.[0];
    if (firstSchema && !schemasQuery.data?.includes(activeSchema)) setActiveSchema(firstSchema);
  }, [activeSchema, schemasQuery.data]);

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
    mutationFn: () => warehouseApi.query(activeWarehouse!.id, sql, activeCatalog, activeSchema),
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
        {activeTab === 'explorer' && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
            <div className="swh-view-header" style={{ padding: '0 0 24px 0', borderBottom: 'none' }}>
              <div className="swh-view-title">
                <h1>Data Explorer</h1>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '24px', flex: 1, minHeight: 0 }}>
              <div style={{ width: '280px', display: 'flex', flexDirection: 'column', gap: '16px', background: 'var(--color-background-subtle)', padding: '16px', borderRadius: '8px', border: '1px solid var(--color-border, var(--color-border))' }}>
                <div className="swh-select-wrap">
                  <label>Catalog</label>
                  <select className="swh-select" value={activeCatalog} onChange={e => { setActiveCatalog(e.target.value); setActiveSchema(''); }}>
                    {(catalogsQuery.data || []).map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                  </select>
                </div>
                <div className="swh-select-wrap">
                  <label>Schema</label>
                  <select className="swh-select" value={activeSchema} onChange={e => setActiveSchema(e.target.value)}>
                    {(schemasQuery.data || []).map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ flex: 1, overflow: 'auto', background: 'var(--color-background-subtle)', padding: '16px', borderRadius: '8px', border: '1px solid var(--color-border, var(--color-border))', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px', alignContent: 'start' }}>
                {(tablesQuery.data || []).map(t => (
                  <button key={t} className="swh-table-item" onClick={() => {
                    const queryText = `SELECT * FROM "${activeCatalog}"."${activeSchema}"."${t}" LIMIT 100;`;
                    setSql(queryText);
                    setQueryTabs(prev => prev.map(tab => {
                      if (tab.id === activeQueryTabId) {
                        return { ...tab, sql: queryText, name: queryText };
                      }
                      return tab;
                    }));
                    navigate('../editor', { relative: 'path' });
                  }} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', padding: '12px' }}>
                    <Database size={14} /> {t}
                  </button>
                ))}
                {(!tablesQuery.data || tablesQuery.data.length === 0) && (
                  <div className="swh-empty" style={{ gridColumn: '1 / -1' }}>No tables found.</div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'editor' && (
          <div className="swh-editor-layout">
            {/* Left Sidebar */}
            <div className="swh-editor-sidebar">
              <div className="swh-sidebar-header">
                <h2>SQL Editor</h2>
                <div className="swh-sidebar-header-actions">
                  <RefreshCw size={13} className="cursor-pointer" />
                  <Folder size={13} className="cursor-pointer" />
                </div>
              </div>
              <div className="swh-sidebar-tree-control">
                <span>Tree view: ON</span>
                <ChevronDown size={12} />
              </div>
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
                        onClick={() => handleSelectDraft(item)}
                        title={item.name}
                      >
                        <FileText size={12} />
                        <span>{item.name}</span>
                      </div>
                    ))}
                    {drafts.length === 0 && (
                      <div className="text-center text-muted py-2" style={{ fontSize: 11 }}>No drafts found</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Main Area */}
            <div className="swh-editor-main">
              {/* Tab Bar */}
              <div className="swh-editor-tabs-bar">
                {queryTabs.map(tab => (
                  <div 
                    key={tab.id} 
                    className={`swh-editor-tab-item ${activeQueryTabId === tab.id ? 'is-active' : ''}`}
                    onClick={() => setActiveQueryTabId(tab.id)}
                  >
                    <FileText size={12} className="text-muted" />
                    <span>{tab.name}</span>
                    <button 
                      className="swh-tab-close-btn" 
                      onClick={(e) => { e.stopPropagation(); handleCloseTab(tab.id); }}
                    >
                      &times;
                    </button>
                  </div>
                ))}
                <button className="swh-add-tab-btn" onClick={handleAddTab} title="New query">
                  <Plus size={14} />
                </button>
              </div>

              {/* Sub-header Toolbar */}
              <div className="swh-editor-toolbar-db">
                <div className="swh-toolbar-left">
                  <button 
                    className="btn btn-primary btn-sm swh-run-btn" 
                    disabled={!canRun} 
                    onClick={() => runMutation.mutate()}
                  >
                    {runMutation.isPending ? <Loader2 size={13} className="spin" /> : <Play size={13} />}
                    <span>Run all (1000)</span>
                  </button>

                  <div className="swh-toolbar-meta">
                    {runMutation.isPending && (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--color-primary)' }}>
                        <Loader2 size={12} className="spin" /> Running
                      </span>
                    )}
                    {!runMutation.isPending && result && (
                      <span className="text-success" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        ✓ {result.duration_ms / 1000}s ({result.rows_returned} rows)
                      </span>
                    )}
                    {!runMutation.isPending && error && (
                      <span className="text-danger" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        ✗ Error
                      </span>
                    )}

                    <div className="swh-catalog-schema-selector-db">
                      <select value={activeCatalog} onChange={e => { setActiveCatalog(e.target.value); setActiveSchema(''); }}>
                        {(catalogsQuery.data || []).map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                      </select>
                      <span className="text-muted">.</span>
                      <select value={activeSchema} onChange={e => setActiveSchema(e.target.value)}>
                        {(schemasQuery.data || []).map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>

                    <Star size={13} className="cursor-pointer text-muted hover:text-warning" />
                    <span style={{ fontSize: 11 }}>Last edit was just now</span>
                  </div>
                </div>

                <div className="swh-toolbar-right">
                  <div className="swh-wh-selector-db">
                    <div className={`swh-dot ${activeWarehouse?.status === 'running' ? 'is-running' : ''}`} />
                    <select value={activeWarehouseId} onChange={e => setActiveWarehouseId(e.target.value)}>
                      {warehouses.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
                    </select>
                    <span className="swh-wh-size-badge">2XS</span>
                  </div>
                  <button className="btn btn-secondary btn-sm" style={{ height: 28, padding: '0 8px' }}>Schedule</button>
                  <button className="btn btn-secondary btn-sm" style={{ height: 28, padding: '0 8px' }}>Share</button>
                  <button className="btn btn-secondary btn-sm" style={{ height: 28, padding: '0 8px' }}>Save</button>
                  <button className="ghost-icon-btn"><MoreVertical size={13} /></button>
                </div>
              </div>

              {/* IDE Editor Area */}
              <div className="swh-ide-editor-container">
                <div className="swh-line-numbers">
                  {lineNumbers.map(n => <div key={n}>{n}</div>)}
                </div>
                <textarea 
                  className="swh-editor-textarea" 
                  value={sql} 
                  onChange={e => handleSqlChange(e.target.value)} 
                  spellCheck={false} 
                  onKeyDown={e => {
                    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                      e.preventDefault();
                      if (canRun) runMutation.mutate();
                    }
                  }}
                />
              </div>

              {/* Editor bottom bar */}
              <div className="swh-editor-bottom-bar">
                <button className="btn btn-secondary btn-sm" style={{ height: 26, padding: '0 8px', fontSize: 11 }}>+ Add parameter</button>
              </div>

              {/* Results Panel */}
              <div className="swh-results-pane-db">
                <div className="swh-results-header-db">
                  <div className="swh-results-tabs">
                    <div className="swh-results-tab is-active">Table</div>
                    <div className="swh-results-tab">+</div>
                  </div>
                  <div className="swh-results-header-actions">
                    <Search size={13} className="cursor-pointer" />
                    <BarChart2 size={13} className="cursor-pointer" />
                    <Maximize2 size={13} className="cursor-pointer" />
                  </div>
                </div>

                <div className="swh-results-table-wrap" style={{ flex: 1, minHeight: 0 }}>
                  {runMutation.isPending && (
                    <div className="swh-empty">
                      <Loader2 size={24} className="spin text-primary" />
                      <span>Running query...</span>
                    </div>
                  )}
                  {error && (
                    <div className="swh-empty text-danger">
                      <CheckCircle2 size={24} />
                      <span>{error}</span>
                    </div>
                  )}
                  {!runMutation.isPending && !error && result && (
                    <table className="swh-results-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          {result.columns.map(c => (
                            <th key={c}>
                              <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                                {getHeaderIcon(c)}
                                {c}
                              </span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.rows.map((r, i) => (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            {r.map((cell, j) => <td key={j}>{cell == null ? 'NULL' : String(cell)}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {!runMutation.isPending && !error && !result && (
                    <div className="swh-empty">
                      <Play size={24} className="text-muted" />
                      <span>Run a query to view results</span>
                    </div>
                  )}
                </div>

                {/* Results Footer */}
                {result && (
                  <div className="swh-results-footer">
                    <div className="swh-results-footer-left">
                      <Download size={13} className="cursor-pointer text-muted hover:text-primary" />
                      <span>{result.rows_returned} rows | {result.duration_ms / 1000}s runtime</span>
                      <a href="#" className="swh-performance-link" onClick={e => { e.preventDefault(); setSelectedQueryForProfile(result); }}>See performance</a>
                    </div>
                    <div className="swh-results-footer-right">
                      <button className="btn btn-secondary btn-sm" style={{ height: 22, padding: '0 6px', fontSize: 10, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                        <Sparkles size={9} />
                        Optimize
                      </button>
                      <span>Refreshed just now</span>
                    </div>
                  </div>
                )}
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
