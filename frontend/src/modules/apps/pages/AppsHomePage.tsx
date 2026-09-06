import { useState, useMemo } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import {
  LayoutGrid,
  Plus,
  Search,
  ExternalLink,
  Pencil,
  Trash2,
  Boxes,
  Globe,
  CheckCircle2,
  Clock,
  Code2,
  GitBranch,
  FolderGit2,
  ShieldCheck,
  Loader2,
} from 'lucide-react';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import { useToast } from '@/lib/toast';
import { CreateAppModal, type AppCreatePayload } from '../components/CreateAppModal';
import { useApps, useCreateApp, useDeleteApp, type AppItem } from '../hooks/useApps';

export default function AppsHomePage() {
  const navigate = useScopedNavigate();
  const toast = useToast();

  const { data: apps = [], isLoading, error } = useApps();
  const createMutation = useCreateApp();
  const deleteMutation = useDeleteApp();

  const [search, setSearch] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const filteredApps = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return apps;
    return apps.filter(
      (app) =>
        app.name.toLowerCase().includes(query) ||
        (app.description && app.description.toLowerCase().includes(query)) ||
        app.app_type.toLowerCase().includes(query) ||
        app.route.toLowerCase().includes(query) ||
        app.git_repo_url.toLowerCase().includes(query) ||
        app.git_branch.toLowerCase().includes(query)
    );
  }, [apps, search]);

  async function handleCreateApp(payload: AppCreatePayload) {
    try {
      await createMutation.mutateAsync({
        name: payload.name,
        description: payload.description,
        app_type: payload.type,
        route: payload.route,
        git_provider: payload.gitProvider,
        git_repo_url: payload.gitRepoUrl,
        git_ref: payload.gitRef,
        git_ref_type: payload.gitRefType,
        git_branch: payload.gitRef,
        git_subdir: payload.gitSubdir,
        entrypoint: payload.entrypoint,
        git_credential_type: payload.gitCredentialType,
        git_credential_nickname: payload.gitCredentialNickname,
        git_connection_id: payload.gitConnectionId,
        git_pat: payload.gitPat,
      });
      setIsCreateModalOpen(false);
      toast.success(`App "${payload.name}" created and registered in system DB.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create app.');
    }
  }

  async function handleDelete(id: string, appName: string) {
    if (!confirm(`Are you sure you want to delete "${appName}"?`)) return;
    try {
      await deleteMutation.mutateAsync(id);
      toast.success(`Deleted "${appName}".`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to delete app.');
    }
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  function formatGitUrl(url: string) {
    return url.replace(/^https?:\/\//, '').replace(/\.git$/, '');
  }

  const columns: AppTableColumn<AppItem>[] = [
    {
      key: 'name',
      header: 'App Name',
      width: '26%',
      render: (app) => (
        <div style={{ cursor: 'pointer' }} onClick={() => navigate(`/apps/${app.id}`)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Boxes size={15} color="var(--color-primary)" style={{ flexShrink: 0 }} />
            <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-primary)' }}>
              {app.name}
            </span>
          </div>
          {app.description && (
            <div
              style={{
                fontSize: '0.75rem',
                color: 'var(--color-text-muted)',
                marginTop: 2,
                paddingLeft: 23,
              }}
            >
              {app.description}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'type',
      header: 'Framework / Type',
      width: '16%',
      render: (app) => (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: '0.8rem',
            color: 'var(--color-text)',
          }}
        >
          <Code2 size={13} color="var(--color-text-muted)" />
          {app.app_type}
        </span>
      ),
    },
    {
      key: 'git',
      header: 'Git Repository',
      width: '22%',
      render: (app) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.8rem',
              color: 'var(--color-text)',
            }}
          >
            <FolderGit2 size={13} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
            <span
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: 180,
              }}
              title={app.git_repo_url}
            >
              {formatGitUrl(app.git_repo_url)}
            </span>
          </div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.72rem',
              color: 'var(--color-text-muted)',
              paddingLeft: 19,
            }}
          >
            <GitBranch size={11} />
            <span>{app.git_branch}</span>
            {app.entrypoint && <span>• {app.entrypoint}</span>}
          </div>
        </div>
      ),
    },
    {
      key: 'identity',
      header: 'Workspace Identity',
      width: '14%',
      render: (app) => (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: '0.72rem',
            fontWeight: 500,
            color: 'var(--color-primary, #1B6EF3)',
            background: 'var(--color-primary-bg, #EBF2FF)',
          }}
          title={`Role: ${app.workspace_identity?.role || 'app_executor'}\nScopes: ${app.workspace_identity?.scopes?.join(', ') || 'N/A'}`}
        >
          <ShieldCheck size={11} />
          {app.workspace_identity?.role || 'Scoped Identity'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '10%',
      render: (app) => (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: '0.72rem',
            fontWeight: 600,
            color: app.status === 'active' ? '#2E7D32' : '#6B6B6B',
            background: app.status === 'active' ? '#E8F5E9' : '#F0F0F0',
          }}
        >
          {app.status === 'active' ? <CheckCircle2 size={11} /> : <Clock size={11} />}
          {app.status.toUpperCase()}
        </span>
      ),
    },
    {
      key: 'route',
      header: 'Endpoint / Port',
      width: '16%',
      className: 'app-table-muted',
      render: (app) => {
        const livePort = app.config?.runtime?.host_port;
        const liveUrl = app.config?.runtime?.url || (livePort ? `http://localhost:${livePort}` : null);
        return (
          <a
            href={liveUrl || app.route}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.78rem',
              color: liveUrl ? 'var(--color-primary)' : 'inherit',
              textDecoration: 'none',
            }}
          >
            <code
              style={{
                fontSize: '0.78rem',
                background: liveUrl ? 'var(--color-primary-bg, #ebf2ff)' : 'var(--color-surface-hover, rgba(0,0,0,0.04))',
                padding: '2px 6px',
                borderRadius: 4,
                color: liveUrl ? 'var(--color-primary)' : 'inherit',
                fontWeight: liveUrl ? 600 : 400,
              }}
            >
              {livePort ? `localhost:${livePort}` : app.route}
            </code>
            {liveUrl && <ExternalLink size={11} />}
          </a>
        );
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (app) => {
        const livePort = app.config?.runtime?.host_port;
        const liveUrl = app.config?.runtime?.url || (livePort ? `http://localhost:${livePort}` : app.route);
        return (
          <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }} onClick={(e) => e.stopPropagation()}>
            <button
              className="ghost-icon-btn"
              title="Open Container in Browser"
              aria-label={`Open ${app.name}`}
              onClick={() => window.open(liveUrl, '_blank')}
            >
              <ExternalLink size={13} />
            </button>
            <button
              className="ghost-icon-btn"
              title="Configure / Manage App"
              aria-label={`Configure ${app.name}`}
              onClick={() => navigate(`/apps/${app.id}?tab=configuration`)}
            >
              <Pencil size={13} />
            </button>
            <button
              className="ghost-icon-btn"
              title="Delete App"
              aria-label={`Delete ${app.name}`}
              onClick={() => handleDelete(app.id, app.name)}
            >
              <Trash2 size={13} />
            </button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="page-section apps-page">
      {/* Header */}
      <div className="db-page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <LayoutGrid size={22} color="var(--color-primary)" />
          <div>
            <h1 className="db-page-title">Apps</h1>
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setIsCreateModalOpen(true)}>
          <Plus size={14} /> Add app
        </button>
      </div>

      {/* Filter / Search Row */}
      <div className="db-filter-row">
        <div className="search-bar-wrapper" style={{ flex: '0 0 300px' }}>
          <Search size={13} className="search-icon" />
          <input
            className="search-input"
            placeholder="Search apps by name, repo, or branch..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
          {filteredApps.length} app{filteredApps.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* 2-Step Add App Modal */}
      <CreateAppModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateApp}
      />

      {/* Loading & Error States */}
      {isLoading ? (
        <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--color-text-muted)' }}>
          <Loader2 size={24} className="spin" style={{ margin: '0 auto 8px' }} />
          <div>Loading workspace applications...</div>
        </div>
      ) : error ? (
        <div className="table-empty error">Failed to load applications for this workspace.</div>
      ) : apps.length === 0 ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '64px 24px',
            border: '1px dashed var(--color-border)',
            borderRadius: 'var(--radius-lg, 8px)',
            background: 'var(--color-surface)',
            textAlign: 'center',
            width: '100%',
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: '50%',
              background: 'var(--color-primary-bg, #EBF2FF)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
              color: 'var(--color-primary)',
            }}
          >
            <Boxes size={24} />
          </div>
          <h3
            style={{
              fontSize: '1rem',
              fontWeight: 600,
              color: 'var(--color-text)',
              marginBottom: 6,
            }}
          >
            No apps yet
          </h3>
          <p
            style={{
              fontSize: '0.85rem',
              color: 'var(--color-text-muted)',
              maxWidth: 420,
              marginBottom: 20,
              lineHeight: 1.5,
            }}
          >
            Connect a Git repository to deploy interactive Streamlit applications, custom web apps, or agentic dashboards.
          </p>
          <button className="btn btn-primary" onClick={() => setIsCreateModalOpen(true)}>
            <Plus size={14} /> Add app
          </button>
        </div>
      ) : (
        <AppTable
          columns={columns}
          rows={filteredApps}
          rowKey={(app) => app.id}
          onRowClick={(app) => navigate(`/apps/${app.id}`)}
          emptyText="No matching apps found."
        />
      )}
    </div>
  );
}
