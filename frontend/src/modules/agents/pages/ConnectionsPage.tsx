import { useEffect, useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Cable,
  Edit2,
  Loader2,
  Plus,
  Power,
  PowerOff,
  Search,
  Trash2,
  Zap,
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
  extractErrorMessage,
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
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const initialTab: ConnectionsTab =
    tabParam === 'llm' || tabParam === 'git' || tabParam === 'all'
      ? tabParam
      : 'all';
  const [tab, setTab] = useState<ConnectionsTab>(initialTab);

  useEffect(() => {
    const t = searchParams.get('tab');
    if (t === 'llm' || t === 'git' || t === 'all') {
      setTab(t);
    } else if (!t) {
      setTab('all');
    }
  }, [searchParams]);

  const handleTabChange = (newTab: ConnectionsTab) => {
    setTab(newTab);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (newTab === 'all') {
          next.delete('tab');
        } else {
          next.set('tab', newTab);
        }
        return next;
      },
      { replace: true },
    );
  };

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
      toast.error(extractErrorMessage(err, 'Connection test failed'));
    } finally {
      setTestingRowId(null);
    }
  }

  async function handleToggleStatus(row: CatalogConnection) {
    try {
      const res = await toggleStatus.mutateAsync(row.id);
      toast.success(`Connection is now ${res.status}`);
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to update connection status'));
    }
  }

  async function confirmDelete(name: string, action: () => Promise<unknown>) {
    if (!confirm(`Delete connection "${name}"?`)) return;
    try {
      await action();
      toast.success('Connection deleted');
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to delete connection'));
    }
  }

  // ── Unified Catalog Connections Columns ──────────────────────────────────────
  const catalogColumns: AppTableColumn<CatalogConnection>[] = [
    {
      key: 'name',
      header: 'Connection / Asset',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ProviderLogo typeId={row.connector_type} size={24} />
          <div>
            <div style={{ fontWeight: 500, fontSize: '0.88rem', color: 'var(--color-text)' }}>{row.name}</div>
            <div style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)', fontFamily: 'monospace', marginTop: 1 }}>
              {row.catalog && row.schema_name
                ? (row.full_name || `${row.catalog}.${row.schema_name}.${row.name}`)
                : 'Account Level'}
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
            fontSize: '0.70rem',
            fontWeight: 500,
            letterSpacing: '0.03em',
            padding: '2px 7px',
            borderRadius: 4,
            background: 'var(--color-surface-hover, #f1f5f9)',
            color: 'var(--color-text-muted)',
            border: '1px solid var(--color-border-subtle, transparent)',
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
        <span style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>
          {row.connector_type}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: row.status === 'active' ? 'var(--color-success, #10b981)' : 'var(--color-text-muted, #94a3b8)',
              opacity: row.status === 'active' ? 1 : 0.6,
            }}
          />
          <span
            style={{
              fontSize: '0.82rem',
              fontWeight: 450,
              color: row.status === 'active' ? 'var(--color-text)' : 'var(--color-text-muted)',
            }}
          >
            {row.status === 'active' ? 'Active' : 'Disabled'}
          </span>
        </div>
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
            {testingRowId === row.id ? <Loader2 size={13} className="spin" /> : <Zap size={13} />}
          </button>
          <button
            className="ghost-icon-btn"
            title={row.status === 'active' ? 'Disable' : 'Enable'}
            onClick={() => handleToggleStatus(row)}
          >
            {row.status === 'active' ? <Power size={13} /> : <PowerOff size={13} />}
          </button>
          <button
            className="ghost-icon-btn"
            title="Delete"
            onClick={() => confirmDelete(row.name, () => deleteCatalogConn.mutateAsync(row.id))}
          >
            <Trash2 size={13} />
          </button>
        </div>
      ),
    },
  ];

  // ── LLM Models Columns ─────────────────────────────────────────────────────
  const llmColumns: AppTableColumn<LLMConnection>[] = [
    { key: 'name', header: 'Name', render: (row) => <div style={{ fontWeight: 500, fontSize: '0.88rem' }}>{row.name}</div> },
    { key: 'provider', header: 'Provider', className: 'app-table-muted', render: (row) => <span style={{ fontSize: '0.82rem' }}>{row.provider}</span> },
    { key: 'model', header: 'Model', render: (row) => <code style={{ fontSize: '0.80rem' }}>{row.model_name}</code> },
    { key: 'api_key', header: 'API Key', className: 'app-table-muted', render: (row) => <span style={{ fontSize: '0.80rem', fontFamily: 'monospace' }}>{row.api_key_masked ?? '—'}</span> },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4 }}>
          <button className="ghost-icon-btn" title="Ping" onClick={() => pingLlm.mutateAsync({ connId: row.id })}>
            <Cable size={13} />
          </button>
          <button className="ghost-icon-btn" title="Edit" onClick={() => navigate(`/connections/llm-models?edit=${row.id}`)}>
            <Edit2 size={13} />
          </button>
          <button className="ghost-icon-btn" title="Delete" onClick={() => confirmDelete(row.name, () => deleteLlm.mutateAsync({ connId: row.id }))}>
            <Trash2 size={13} />
          </button>
        </div>
      ),
    },
  ];

  // ── Git Servers Columns ────────────────────────────────────────────────────
  const gitColumns: AppTableColumn<GitConnection>[] = [
    { key: 'name', header: 'Name', render: (row) => <div style={{ fontWeight: 500, fontSize: '0.88rem' }}>{row.name}</div> },
    { key: 'provider', header: 'Provider', render: (row) => <span style={{ fontSize: '0.82rem' }}>{row.provider === 'azure_devops' ? 'Azure DevOps' : 'GitHub'}</span> },
    { key: 'organization', header: 'Organization', className: 'app-table-muted', render: (row) => <span style={{ fontSize: '0.82rem' }}>{row.organization || '—'}</span> },
    { key: 'project', header: 'Project', render: (row) => <span style={{ fontSize: '0.82rem' }}>{row.default_project || '—'}</span> },
    { key: 'pat', header: 'PAT', render: (row) => <span style={{ fontSize: '0.80rem', color: 'var(--color-text-muted)' }}>{row.pat_configured ? 'Configured' : '—'}</span> },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4 }}>
          <button className="ghost-icon-btn" title="Test" onClick={() => testGit.mutateAsync({ connId: row.id })}>
            <Cable size={13} />
          </button>
          <button className="ghost-icon-btn" title="Edit" onClick={() => navigate(`/connections/git-servers?edit=${row.id}`)}>
            <Edit2 size={13} />
          </button>
          <button className="ghost-icon-btn" title="Delete" onClick={() => confirmDelete(row.name, () => deleteGit.mutateAsync({ connId: row.id }))}>
            <Trash2 size={13} />
          </button>
        </div>
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
    <div className="page-section connections-page">
      {/* Header */}
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>
          Connections
        </h1>
        <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.84rem' }}>
          Manage external connections for databases, REST APIs, Loki, Git, and LLM providers.
        </p>
      </div>

      {/* Main Tabs */}
      <PageTabs tabs={CONNECTION_TABS} value={tab} onChange={handleTabChange} />

      {tab === 'all' && (
        <>
          {/* Quick Connect Row */}
          <div className="quick-connect-scroll-row" style={{ marginTop: 14, marginBottom: 14 }}>
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
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  cursor: 'pointer',
                  fontSize: '0.78rem',
                  fontWeight: 450,
                  color: 'var(--color-text)',
                  transition: 'background 0.12s ease, border-color 0.12s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-border-strong, var(--color-border))';
                  e.currentTarget.style.background = 'var(--color-surface-hover)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-border)';
                  e.currentTarget.style.background = 'var(--color-surface)';
                }}
              >
                <ProviderLogo typeId={pc.type_id} size={15} />
                <span style={{ whiteSpace: 'nowrap' }}>{pc.name}</span>
              </button>
            ))}
          </div>

          {/* Search & Actions Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <div className="search-bar-wrapper" style={{ width: 260 }}>
                <Search size={14} className="search-icon" />
                <input
                  className="search-input"
                  placeholder="Search connections..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', gap: 4 }}>
                {(['all', 'database', 'api', 'observability'] as const).map((cat) => {
                  const isActive = categoryFilter === cat;
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setCategoryFilter(cat)}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        border: '1px solid',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        borderColor: isActive ? 'var(--color-border-strong, #94a3b8)' : 'var(--color-border)',
                        background: isActive ? 'var(--color-surface-hover)' : 'transparent',
                        color: isActive ? 'var(--color-text)' : 'var(--color-text-muted)',
                        fontWeight: isActive ? 500 : 400,
                        transition: 'all 0.12s ease',
                      }}
                    >
                      {cat === 'all' ? 'All' : cat === 'database' ? 'Databases' : cat === 'api' ? 'REST APIs' : 'Observability'}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <button className="btn btn-primary" onClick={() => navigate('/connections/create')} style={{ fontSize: '0.82rem' }}>
                <Plus size={14} /> Create Connection
              </button>
            </div>
          </div>

          {/* Table */}
          <AppTable
            columns={catalogColumns}
            rows={filteredCatalogConnections}
            rowKey={(row) => row.id}
            emptyText="No external connections found. Click 'Create Connection' or select a connector above to get started."
            isLoading={isLoadingCatalog}
          />
        </>
      )}

      {tab !== 'all' && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 14, marginBottom: 14 }}>
          <div className="search-bar-wrapper" style={{ width: 260 }}>
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
              <button className="btn btn-primary" onClick={() => navigate('/connections/llm-models')} style={{ fontSize: '0.82rem' }}>
                <Plus size={14} /> Add LLM Model
              </button>
            ) : (
              <button className="btn btn-primary" onClick={() => navigate('/connections/git-servers')} style={{ fontSize: '0.82rem' }}>
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
