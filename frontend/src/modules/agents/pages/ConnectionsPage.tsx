import { type Dispatch, type SetStateAction, useState } from 'react';
import { Cable, CheckCircle2, Edit2, Loader2, Plus, Search, Trash2, XCircle } from 'lucide-react';
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
  useDBConnections,
  useDeleteDBConnection,
  useTestDBConnection,
  type DBConnection,
} from '@/modules/agents/hooks/useDBConnections';
import {
  useDeleteGitConnection,
  useGitConnections,
  useTestGitConnection,
  type GitConnection,
} from '@/modules/agents/hooks/useGitConnections';
import { useToast } from '@/lib/toast';

type ConnectionsTab = 'llm' | 'databases' | 'git';
type TestStatus = 'ok' | 'fail' | 'testing';

const CONNECTION_TABS = [
  { value: 'llm', label: 'LLM Models' },
  { value: 'databases', label: 'Databases' },
  { value: 'git', label: 'Git Servers' },
] as const satisfies readonly { value: ConnectionsTab; label: string }[];

function ResultIcon({ status }: { status?: TestStatus }) {
  if (status === 'testing') return <Loader2 size={13} className="spin" />;
  if (status === 'ok') return <CheckCircle2 size={13} color="#2E7D32" />;
  if (status === 'fail') return <XCircle size={13} color="#D32F2F" />;
  return <Cable size={14} color="#5A5A5A" strokeWidth={2.4} />;
}

export default function ConnectionsPage() {
  const navigate = useScopedNavigate();
  const toast = useToast();
  const [tab, setTab] = useState<ConnectionsTab>('llm');
  const [llmStatus, setLlmStatus] = useState<Record<number, TestStatus>>({});
  const [dbStatus, setDbStatus] = useState<Record<number, TestStatus>>({});
  const [gitStatus, setGitStatus] = useState<Record<number, TestStatus>>({});
  const [search, setSearch] = useState('');

  const { data: llmConnections = [], isLoading: isLoadingLlm } = useLLMConnections();
  const { data: dbConnections = [], isLoading: isLoadingDb } = useDBConnections();
  const { data: gitConnections = [], isLoading: isLoadingGit } = useGitConnections();
  const pingLlm = usePingLLMConnection();
  const testDb = useTestDBConnection();
  const testGit = useTestGitConnection();
  const deleteLlm = useDeleteLLMConnection();
  const deleteDb = useDeleteDBConnection();
  const deleteGit = useDeleteGitConnection();

  function getConnectionEditorPath(targetTab: ConnectionsTab = tab) {
    if (targetTab === 'llm') return '/connections/llm-models';
    if (targetTab === 'databases') return '/connections/databases';
    return '/connections/git-servers';
  }

  function getAddButtonLabel() {
    if (tab === 'llm') return 'Add LLM Model';
    if (tab === 'databases') return 'Add Database';
    return 'Add Git Server';
  }

  function matchesSearch(values: Array<unknown>) {
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return values
      .filter((value) => value !== undefined && value !== null)
      .some((value) => String(value).toLowerCase().includes(query));
  }

  async function runCheck(
    id: number,
    setter: Dispatch<SetStateAction<Record<number, TestStatus>>>,
    action: () => Promise<{ success: boolean; message: string }>,
  ) {
    setter((state) => ({ ...state, [id]: 'testing' }));
    try {
      const result = await action();
      setter((state) => ({ ...state, [id]: result.success ? 'ok' : 'fail' }));
      result.success ? toast.success(result.message) : toast.error(result.message);
    } catch {
      setter((state) => ({ ...state, [id]: 'fail' }));
      toast.error('Connection check failed');
    }
  }

  async function confirmDelete(name: string, action: () => Promise<unknown>) {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await action();
      toast.success('Connection deleted');
    } catch {
      toast.error('Failed to delete connection');
    }
  }

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
          <button className="ghost-icon-btn" title="Ping" onClick={() => runCheck(row.id, setLlmStatus, () => pingLlm.mutateAsync({ connId: row.id }))}>
            <ResultIcon status={llmStatus[row.id]} />
          </button>
          <button className="ghost-icon-btn" title="Edit" onClick={() => navigate(`${getConnectionEditorPath('llm')}?edit=${row.id}`)}>
            <Edit2 size={13} />
          </button>
          <button className="ghost-icon-btn" title="Delete" onClick={() => confirmDelete(row.name, () => deleteLlm.mutateAsync({ connId: row.id }))}>
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

  const dbColumns: AppTableColumn<DBConnection>[] = [
    { key: 'name', header: 'Name', render: (row) => <b style={{ fontWeight: 500 }}>{row.name}</b> },
    { key: 'type', header: 'Type', render: (row) => row.db_type },
    { key: 'host', header: 'Host', className: 'app-table-muted', render: (row) => row.host ? `${row.host}:${row.port ?? ''}` : '-' },
    { key: 'database', header: 'Database', render: (row) => row.db_name ?? '-' },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <>
          <button className="ghost-icon-btn" title="Test" onClick={() => runCheck(row.id, setDbStatus, () => testDb.mutateAsync({ connId: row.id }))}>
            <ResultIcon status={dbStatus[row.id]} />
          </button>
          <button className="ghost-icon-btn" title="Edit" onClick={() => navigate(`${getConnectionEditorPath('databases')}?edit=${row.id}`)}>
            <Edit2 size={13} />
          </button>
          <button className="ghost-icon-btn" title="Delete" onClick={() => confirmDelete(row.name, () => deleteDb.mutateAsync({ connId: row.id }))}>
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

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
          <button className="ghost-icon-btn" title="Test" onClick={() => runCheck(row.id, setGitStatus, () => testGit.mutateAsync({ connId: row.id }))}>
            <ResultIcon status={gitStatus[row.id]} />
          </button>
          <button className="ghost-icon-btn" title="Edit" onClick={() => navigate(`${getConnectionEditorPath('git')}?edit=${row.id}`)}>
            <Edit2 size={13} />
          </button>
          <button className="ghost-icon-btn" title="Delete" onClick={() => confirmDelete(row.name, () => deleteGit.mutateAsync({ connId: row.id }))}>
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

  const filteredLlmConnections = llmConnections.filter((row) =>
    matchesSearch([row.name, row.provider, row.model_name, row.api_key_masked, row.base_url])
  );
  const filteredDbConnections = dbConnections.filter((row) =>
    matchesSearch([row.name, row.db_type, row.host, row.port, row.db_name])
  );
  const filteredGitConnections = gitConnections.filter((row) =>
    matchesSearch([row.name, row.provider, row.organization, row.default_project, row.base_url])
  );
  const count = tab === 'llm' ? filteredLlmConnections.length : tab === 'databases' ? filteredDbConnections.length : filteredGitConnections.length;

  return (
    <div className="page-section connections-page">
      <div className="db-page-header">
        <h1 className="db-page-title">Connections</h1>
      </div>

      <PageTabs tabs={CONNECTION_TABS} value={tab} onChange={setTab} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="search-bar-wrapper" style={{ flex: '0 0 300px' }}>
            <Search size={13} className="search-icon" />
            <input
              className="search-input"
              placeholder="Search connections..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>{count} connection{count === 1 ? '' : 's'}</div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate(getConnectionEditorPath())}>
          <Plus size={14} /> {getAddButtonLabel()}
        </button>
      </div>

      {tab === 'llm' && <AppTable columns={llmColumns} rows={filteredLlmConnections} rowKey={(row) => row.id} emptyText="No LLM connections found." isLoading={isLoadingLlm} />}
      {tab === 'databases' && <AppTable columns={dbColumns} rows={filteredDbConnections} rowKey={(row) => row.id} emptyText="No database connections found." isLoading={isLoadingDb} />}
      {tab === 'git' && <AppTable columns={gitColumns} rows={filteredGitConnections} rowKey={(row) => row.id} emptyText="No Git connections found." isLoading={isLoadingGit} />}
    </div>
  );
}
