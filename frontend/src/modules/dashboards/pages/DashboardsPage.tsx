/**
 * DashboardsPage — lists all dashboards, create/clone/delete actions.
 */

import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { Copy, LayoutDashboard, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { useDashboards, useCreateDashboard, useDeleteDashboard, useCloneDashboard } from '@/modules/dashboards/hooks/useDashboard';
import { useToast } from '@/lib/toast';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';

type DashboardRow = {
  id: string;
  name: string;
  isDraft?: boolean;
  updatedAt: string;
};

export default function DashboardsPage() {
  const navigate = useScopedNavigate();
  const toast = useToast();
  const { data: dashboards, isLoading } = useDashboards();
  const createMutation = useCreateDashboard();
  const deleteMutation = useDeleteDashboard();
  const cloneMutation = useCloneDashboard();

  const [search, setSearch] = useState('');

  const filtered = ((dashboards ?? []) as DashboardRow[]).filter((dashboard) =>
    !search.trim() || dashboard.name.toLowerCase().includes(search.trim().toLowerCase())
  );

  async function handleCreate() {
    const name = prompt('Dashboard name:');
    if (!name?.trim()) return;
    try {
      const dashboard = await createMutation.mutateAsync(name.trim());
      navigate(`/dashboards/${dashboard.id}/edit`);
    } catch {
      toast.error('Failed to create dashboard');
    }
  }

  async function handleClone(id: string, name: string) {
    try {
      const dashboard = await cloneMutation.mutateAsync(id);
      toast.success(`Cloned "${name}"`);
      navigate(`/dashboards/${dashboard.id}/edit`);
    } catch {
      toast.error('Failed to clone dashboard');
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete dashboard "${name}"? This cannot be undone.`)) return;
    try {
      await deleteMutation.mutateAsync(id);
      toast.success(`Deleted "${name}"`);
    } catch {
      toast.error('Failed to delete dashboard');
    }
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  const columns: AppTableColumn<DashboardRow>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (dashboard) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <LayoutDashboard size={14} color="var(--color-text-muted)" />
          <span style={{ fontWeight: 500 }}>{dashboard.name}</span>
          {dashboard.isDraft && <span className="dashboard-draft-pill">DRAFT</span>}
        </span>
      ),
    },
    {
      key: 'updated',
      header: 'Updated',
      className: 'app-table-muted',
      render: (dashboard) => formatDate(dashboard.updatedAt),
    },
    {
      key: 'status',
      header: 'Status',
      render: (dashboard) => dashboard.isDraft ? 'Draft' : 'Published',
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (dashboard) => (
        <>
          <button
            className="ghost-icon-btn"
            title="Open"
            aria-label={`Open ${dashboard.name}`}
            onClick={(event) => {
              event.stopPropagation();
              navigate(`/dashboards/${dashboard.id}/edit`);
            }}
          >
            <Pencil size={13} />
          </button>
          <button
            className="ghost-icon-btn"
            title="Clone"
            aria-label={`Clone ${dashboard.name}`}
            onClick={(event) => {
              event.stopPropagation();
              handleClone(dashboard.id, dashboard.name);
            }}
          >
            <Copy size={13} />
          </button>
          <button
            className="ghost-icon-btn"
            title="Delete"
            aria-label={`Delete ${dashboard.name}`}
            onClick={(event) => {
              event.stopPropagation();
              handleDelete(dashboard.id, dashboard.name);
            }}
          >
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

  return (
    <div className="page-section dashboard-page">
      <div className="db-page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <LayoutDashboard size={22} color="var(--color-primary)" />
          <h1 className="db-page-title">Dashboards</h1>
        </div>
        <button className="btn btn-primary" onClick={handleCreate} disabled={createMutation.isPending}>
          <Plus size={14} /> Create dashboard
        </button>
      </div>

      <div className="db-filter-row">
        <div className="search-bar-wrapper" style={{ flex: '0 0 300px' }}>
          <Search size={13} className="search-icon" />
          <input
            className="search-input"
            placeholder="Search dashboards..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
          {filtered.length} dashboard{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      <AppTable
        columns={columns}
        rows={filtered}
        rowKey={(dashboard) => dashboard.id}
        onRowClick={(dashboard) => navigate(`/dashboards/${dashboard.id}/edit`)}
        emptyText="No dashboards yet."
        isLoading={isLoading}
      />
    </div>
  );
}
