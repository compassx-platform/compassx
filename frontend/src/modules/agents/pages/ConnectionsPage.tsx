import { useState, useMemo } from 'react';
import {
  Cable,
  CheckCircle2,
  Edit2,
  Globe,
  Loader2,
  Plus,
  Power,
  PowerOff,
  Search,
  Trash2,
  XCircle,
  Zap,
  Sparkles,
  Database,
  Activity,
  Layers,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { PageTabs } from '@/components/common/PageTabs';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import {
  useDeleteLLMConnection,
  useLLMConnections,
  usePingLLMConnection,
  type LLMConnection,
} from '@/modules/agents/hooks/useLLMConnections';
import {
  useDeleteGitConnection,
  useGitConnections,
  useTestGitConnection,
  type GitConnection,
} from '@/modules/agents/hooks/useGitConnections';
import {
  useCatalogConnections,
  useDeleteCatalogConnection,
  useToggleConnectionStatus,
  useTestConnection,
  type CatalogConnection,
} from '@/modules/agents/hooks/useCatalogConnections';
import { ProviderLogo } from '@/modules/agents/components/CreateConnectionWizard';
import { useToast } from '@/lib/toast';

type ConnectionsTab = 'all' | 'llm' | 'git';
type CategoryFilter = 'all' | 'database' | 'api' | 'observability';

const CONNECTION_TABS = [
  { value: 'all', label: 'External Connections' },
  { value: 'llm', label: 'LLM Models' },
  { value: 'git', label: 'Git Servers' },
] as const satisfies readonly { value: ConnectionsTab; label: string }[];

const POPULAR_CONNECTORS = [
  { type_id: 'postgres', name: 'PostgreSQL', category: 'database' },
  { type_id: 'mysql', name: 'MySQL', category: 'database' },
  { type_id: 'mssql', name: 'SQL Server', category: 'database' },
  { type_id: 'snowflake', name: 'Snowflake', category: 'database' },
  { type_id: 'rest_api', name: 'REST API', category: 'api' },
  { type_id: 'loki', name: 'Grafana Loki', category: 'observability' },
  { type_id: 'prometheus', name: 'Prometheus', category: 'observability' },
  { type_id: 'bigquery', name: 'BigQuery', category: 'database' },
  { type_id: 'databricks', name: 'Databricks', category: 'database' },
  { type_id: 'oracle', name: 'Oracle', category: 'database' },
  { type_id: 'sqlite', name: 'SQLite', category: 'database' },
  { type_id: 'custom', name: 'Custom Webhook', category: 'custom' },
];

export default function ConnectionsPage() {
  const navigate = useScopedNavigate();
  const toast = useToast();
  const [tab, setTab] = useState<ConnectionsTab>('all');
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');

  // Testing feedback states
  const [testingRowId, setTestingRowId] = useState<string | null>(null);

  // Queries
  const { data: catalogConnections = [], isLoading: isLoadingCatalog } = useCatalogConnections();
  const { data: llmConnections = [], isLoading: isLoadingLlm } = useLLMConnections();
  const { data: gitConnections = [], isLoading: isLoadingGit } = useGitConnections();

  const pingLlm = usePingLLMConnection();
  const testGit = useTestGitConnection();
  const deleteLlm = useDeleteLLMConnection();
  const deleteGit = useDeleteGitConnection();

  const deleteCatalogConn = useDeleteCatalogConnection();
  const toggleStatus = useToggleConnectionStatus();
  const testConn = useTestConnection();

  async function handleTestCatalogConnection(row: CatalogConnection) {
    setTestingRowId(row.id);
    try {
      const res = await testConn.mutateAsync({ connection_id: row.id });
      if (res.success) {
        toast.success(`Connection "${row.name}" OK (${res.latency_ms}ms)`);
      } else {
        toast.error(`Test failed: ${res.message}`);
      }
    } catch (err: any) {
      toast.error(err.message || 'Connection test failed');
    } finally {
      setTestingRowId(null);
    }
  }

  async function handleToggleStatus(row: CatalogConnection) {
    try {
      const res = await toggleStatus.mutateAsync(row.id);
      toast.success(`Connection is now ${res.status}`);
    } catch {
      toast.error('Failed to update connection status');
    }
  }

  async function confirmDelete(name: string, action: () => Promise<unknown>) {
    if (!confirm(`Delete connection "${name}"?`)) return;
    try {
      await action();
      toast.success('Connection deleted');
    } catch {
      toast.error('Failed to delete connection');
    }
  }

  // ── Unified Catalog Connections Columns ──────────────────────────────────────
  const catalogColumns: AppTableColumn<CatalogConnection>[] = [
    {
      key: 'name',
      header: 'Connection / Asset',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ProviderLogo typeId={row.connector_type} size={26} />
          <div>
            <b style={{ fontWeight: 600, fontSize: '0.92rem' }}>{row.name}</b>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
              {row.catalog && row.schema_name
                ? (row.full_name || `${row.catalog}.${row.schema_name}.${row.name}`)
                : <span style={{ color: '#2563eb', fontWeight: 500 }}>Account Level</span>}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'category',
      header: 'Category',
      render: (row) => (
        <span
          style={{
            textTransform: 'uppercase',
            fontSize: '0.72rem',
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 4,
            background: 'var(--color-bg-subtle, #f1f5f9)',
            color: 'var(--color-text-muted, #64748b)',
          }}
        >
          {row.category}
        </span>
      ),
    },
    {
      key: 'connector_type',
      header: 'Type',
      render: (row) => (
        <span style={{ fontSize: '0.85rem' }}>
          <code>{row.connector_type}</code>
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span
          style={{
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: '0.75rem',
            fontWeight: 600,
            background: row.status === 'active' ? '#E8F5E9' : '#FFEBEE',
            color: row.status === 'active' ? '#2E7D32' : '#C62828',
          }}
        >
          {row.status}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4 }}>
          <button
            className="ghost-icon-btn"
            title="Test Connection"
            onClick={() => handleTestCatalogConnection(row)}
            disabled={testingRowId === row.id}
          >
            {testingRowId === row.id ? <Loader2 size={14} className="spin" /> : <Zap size={14} color="#F59E0B" />}
          </button>
          <button
            className="ghost-icon-btn"
            title={row.status === 'active' ? 'Disable' : 'Enable'}
            onClick={() => handleToggleStatus(row)}
          >
            {row.status === 'active' ? <Power size={14} color="#2E7D32" /> : <PowerOff size={14} color="#D32F2F" />}
          </button>
          <button
            className="ghost-icon-btn"
            title="Delete"
            onClick={() => confirmDelete(row.name, () => deleteCatalogConn.mutateAsync(row.id))}
          >
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ];

  // ── LLM Models Columns ─────────────────────────────────────────────────────
  const llmColumns: AppTableColumn<LLMConnection>[] = [
    { key: 'name', header: 'Name', render: (row) => <b style={{ fontWeight: 500 }}>{row.name}</b> },
    { key: 'provider', header: 'Provider', className: 'app-table-muted', render: (row) => row.provider },
    { key: 'model', header: 'Model', render: (row) => <code>{row.model_name}</code> },
    { key: 'api_key', header: 'API Key', className: 'app-table-muted', render: (row) => row.api_key_masked ?? '-' },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <>
          <button className="ghost-icon-btn" title="Ping" onClick={() => pingLlm.mutateAsync({ connId: row.id })}>
            <Cable size={14} />
          </button>
          <button className="ghost-icon-btn" title="Edit" onClick={() => navigate(`/connections/llm-models?edit=${row.id}`)}>
            <Edit2 size={13} />
          </button>
          <button className="ghost-icon-btn" title="Delete" onClick={() => confirmDelete(row.name, () => deleteLlm.mutateAsync({ connId: row.id }))}>
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

  // ── Git Servers Columns ────────────────────────────────────────────────────
  const gitColumns: AppTableColumn<GitConnection>[] = [
    { key: 'name', header: 'Name', render: (row) => <b style={{ fontWeight: 500 }}>{row.name}</b> },
    { key: 'provider', header: 'Provider', render: (row) => row.provider === 'azure_devops' ? 'Azure DevOps' : 'GitHub' },
    { key: 'organization', header: 'Organization', className: 'app-table-muted', render: (row) => row.organization || '-' },
    { key: 'project', header: 'Project', render: (row) => row.default_project || '-' },
    { key: 'pat', header: 'PAT', render: (row) => row.pat_configured ? 'Configured' : '-' },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <>
          <button className="ghost-icon-btn" title="Test" onClick={() => testGit.mutateAsync({ connId: row.id })}>
            <Cable size={14} />
          </button>
          <button className="ghost-icon-btn" title="Edit" onClick={() => navigate(`/connections/git-servers?edit=${row.id}`)}>
            <Edit2 size={13} />
          </button>
          <button className="ghost-icon-btn" title="Delete" onClick={() => confirmDelete(row.name, () => deleteGit.mutateAsync({ connId: row.id }))}>
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

  const filteredCatalogConnections = useMemo(() => {
    const q = search.trim().toLowerCase();
    return catalogConnections.filter((row) => {
      const matchCat = categoryFilter === 'all' || row.category === categoryFilter;
      const matchSearch =
        !q ||
        row.name.toLowerCase().includes(q) ||
        row.full_name?.toLowerCase().includes(q) ||
        row.connector_type.toLowerCase().includes(q) ||
        row.description?.toLowerCase().includes(q);
      return matchCat && matchSearch;
    });
  }, [catalogConnections, search, categoryFilter]);

  const filteredLlmConnections = llmConnections.filter((row) =>
    !search.trim() || row.name.toLowerCase().includes(search.toLowerCase()) || row.provider.toLowerCase().includes(search.toLowerCase())
  );
  const filteredGitConnections = gitConnections.filter((row) =>
    !search.trim() || row.name.toLowerCase().includes(search.toLowerCase()) || row.provider.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page-section connections-page" style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div className="db-page-header" style={{ marginBottom: 20 }}>
        <div>
          <h1 className="db-page-title" style={{ margin: 0, fontSize: '1.4rem' }}>Connections</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
            First-class unified catalog connections for SQL databases, REST APIs, Loki, and observability.
          </p>
        </div>
      </div>

      {/* Main Tabs */}
      <PageTabs tabs={CONNECTION_TABS} value={tab} onChange={setTab} />

      {tab === 'all' && (
        <>
          {/* Minimal Compact Quick Connect Row */}
          <div className="quick-connect-scroll-row">
            {POPULAR_CONNECTORS.map((pc) => (
              <button
                key={pc.type_id}
                type="button"
                onClick={() => navigate(`/connections/create?provider=${pc.type_id}`)}
                style={{
                  flex: '0 0 auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 10px',
                  borderRadius: 6,
                  background: 'var(--color-bg-subtle, #f8fafc)',
                  border: '1px solid var(--color-border, #e2e8f0)',
                  cursor: 'pointer',
                  fontSize: '0.78rem',
                  fontWeight: 500,
                  color: 'var(--color-text-primary, #1e293b)',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-primary, #2563eb)';
                  e.currentTarget.style.background = 'var(--color-primary-light, #eff6ff)';
                  e.currentTarget.style.color = 'var(--color-primary, #2563eb)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-border, #e2e8f0)';
                  e.currentTarget.style.background = 'var(--color-bg-subtle, #f8fafc)';
                  e.currentTarget.style.color = 'var(--color-text-primary, #1e293b)';
                }}
              >
                <ProviderLogo typeId={pc.type_id} size={16} />
                <span style={{ whiteSpace: 'nowrap' }}>{pc.name}</span>
              </button>
            ))}
          </div>

          {/* Search & Actions Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <div className="search-bar-wrapper" style={{ flex: '0 0 280px' }}>
                <Search size={14} className="search-icon" />
                <input
                  className="search-input"
                  placeholder="Search connections..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', gap: 6 }}>
                {(['all', 'database', 'api', 'observability'] as const).map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setCategoryFilter(cat)}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 6,
                      border: '1px solid',
                      fontSize: '0.78rem',
                      cursor: 'pointer',
                      borderColor: categoryFilter === cat ? 'var(--color-primary, #2563eb)' : 'var(--color-border, #e2e8f0)',
                      background: categoryFilter === cat ? 'var(--color-primary-light, #eff6ff)' : 'transparent',
                      color: categoryFilter === cat ? 'var(--color-primary, #2563eb)' : 'inherit',
                      fontWeight: categoryFilter === cat ? 600 : 400,
                    }}
                  >
                    {cat === 'all' ? 'All' : cat === 'database' ? 'Databases' : cat === 'api' ? 'REST APIs' : 'Observability'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <button className="btn btn-primary" onClick={() => navigate('/connections/create')}>
                <Plus size={14} /> Create Connection
              </button>
            </div>
          </div>

          {/* Table */}
          <AppTable
            columns={catalogColumns}
            rows={filteredCatalogConnections}
            rowKey={(row) => row.id}
            emptyText="No external connections found. Click 'Create Connection' or select a popular connector above to get started."
            isLoading={isLoadingCatalog}
          />
        </>
      )}

      {tab !== 'all' && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 16, marginBottom: 16 }}>
          <div className="search-bar-wrapper" style={{ flex: '0 0 280px' }}>
            <Search size={14} className="search-icon" />
            <input
              className="search-input"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div>
            {tab === 'llm' ? (
              <button className="btn btn-primary" onClick={() => navigate('/connections/llm-models')}>
                <Plus size={14} /> Add LLM Model
              </button>
            ) : (
              <button className="btn btn-primary" onClick={() => navigate('/connections/git-servers')}>
                <Plus size={14} /> Add Git Server
              </button>
            )}
          </div>
        </div>
      )}

      {tab === 'llm' && (
        <AppTable
          columns={llmColumns}
          rows={filteredLlmConnections}
          rowKey={(row) => row.id}
          emptyText="No LLM connections found."
          isLoading={isLoadingLlm}
        />
      )}

      {tab === 'git' && (
        <AppTable
          columns={gitColumns}
          rows={filteredGitConnections}
          rowKey={(row) => row.id}
          emptyText="No Git connections found."
          isLoading={isLoadingGit}
        />
      )}
    </div>
  );
}
