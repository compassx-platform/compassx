/**
 * DashboardsPage — lists all dashboards, create/clone/delete actions.
 */

import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Copy, LayoutDashboard, Pencil, Plus, Search, Trash2, X } from 'lucide-react';
import { useDashboards, useDeleteDashboard, useCloneDashboard } from '@/modules/dashboards/hooks/useDashboard';
import { useToast } from '@/lib/toast';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import api from '@/lib/api';

type DashboardRow = {
  id: string;
  name: string;
  isDraft?: boolean;
  updatedAt: string;
};

interface CatalogSchemaSummary {
  id: string;
  name: string;
}

interface CatalogSummary {
  id: string;
  name: string;
  schemas: CatalogSchemaSummary[];
}

interface CreatedCatalogDashboard {
  id: string;
  catalog_name: string;
  schema_name: string;
  name: string;
  dashboard_id?: string;
}

async function createCatalogDashboard(catalog: string, schema: string, payload: { name: string; comment?: string }): Promise<CreatedCatalogDashboard> {
  const res = await api.post<CreatedCatalogDashboard>(
    `/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/dashboards`,
    payload
  );
  return res.data;
}

export default function DashboardsPage() {
  const navigate = useScopedNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: dashboards, isLoading } = useDashboards();
  const deleteMutation = useDeleteDashboard();
  const cloneMutation = useCloneDashboard();

  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [selectedCatalog, setSelectedCatalog] = useState('');
  const [selectedSchema, setSelectedSchema] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const { data: catalogs = [], isLoading: loadingCatalogs } = useQuery({
    queryKey: ['uc-catalogs'],
    queryFn: () => api.get<CatalogSummary[]>('/catalog/catalogs').then((r) => r.data),
  });

  const currentCatalogObj = catalogs.find((c) => c.name === selectedCatalog);
  const availableSchemas = currentCatalogObj?.schemas || [];
  const isFormValid = newName.trim().length > 0 && Boolean(selectedCatalog) && Boolean(selectedSchema);

  const filtered = ((dashboards ?? []) as DashboardRow[]).filter((dashboard) =>
    !search.trim() || dashboard.name.toLowerCase().includes(search.trim().toLowerCase())
  );

  function generateDefaultDashboardName() {
    const existingNames = new Set(((dashboards ?? []) as DashboardRow[]).map((d) => d.name.toLowerCase()));
    let index = 1;
    while (existingNames.has(`untitled_dashboard_${index}`)) {
      index++;
    }
    return `untitled_dashboard_${index}`;
  }

  function handleOpenCreateModal() {
    const defaultName = generateDefaultDashboardName();
    setNewName(defaultName);

    // Pick default catalog: 'main' > 'default' > first catalog with schemas > first catalog
    const preferredCatalog =
      catalogs.find((c) => c.name.toLowerCase() === 'main' && c.schemas && c.schemas.length > 0) ||
      catalogs.find((c) => c.name.toLowerCase() === 'default' && c.schemas && c.schemas.length > 0) ||
      catalogs.find((c) => c.schemas && c.schemas.length > 0) ||
      catalogs[0];

    const catalogName = preferredCatalog?.name || '';
    setSelectedCatalog(catalogName);

    // Pick default schema: 'default' > 'public' > first schema
    const preferredSchema =
      preferredCatalog?.schemas.find((s) => s.name.toLowerCase() === 'default') ||
      preferredCatalog?.schemas.find((s) => s.name.toLowerCase() === 'public') ||
      preferredCatalog?.schemas[0];

    const schemaName = preferredSchema?.name || '';
    setSelectedSchema(schemaName);

    setFormError(null);
    setCreating(true);
  }

  function handleCatalogChange(catalogName: string) {
    setSelectedCatalog(catalogName);
    const cat = catalogs.find((c) => c.name === catalogName);
    const preferredSchema =
      cat?.schemas.find((s) => s.name.toLowerCase() === 'default') ||
      cat?.schemas.find((s) => s.name.toLowerCase() === 'public') ||
      cat?.schemas[0];
    setSelectedSchema(preferredSchema?.name || '');
    setFormError(null);
  }

  const createMut = useMutation({
    mutationFn: (vars: { name: string; catalog: string; schema: string }) =>
      createCatalogDashboard(vars.catalog, vars.schema, { name: vars.name }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['dashboards'] });
      queryClient.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setCreating(false);
      setNewName('');
      setSelectedCatalog('');
      setSelectedSchema('');
      setFormError(null);
      toast.success(`Created dashboard "${data.name}"`);
      const dashId = data.dashboard_id || data.id;
      navigate(`/data-catalog/${encodeURIComponent(data.catalog_name)}/${encodeURIComponent(data.schema_name)}/dashboard/${encodeURIComponent(data.name)}?dashboard_id=${encodeURIComponent(dashId)}`);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to create dashboard.';
      setFormError(msg);
      toast.error(msg);
    },
  });

  function handleCreate(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const name = newName.trim();
    if (!name) {
      setFormError('Please enter a dashboard name.');
      return;
    }
    if (!selectedCatalog) {
      setFormError('Please select a catalog.');
      return;
    }
    if (!selectedSchema) {
      setFormError('Please select a schema.');
      return;
    }
    setFormError(null);
    createMut.mutate({
      name,
      catalog: selectedCatalog,
      schema: selectedSchema,
    });
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
        <button className="btn btn-primary" onClick={handleOpenCreateModal}>
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

      {creating && (
        <div
          className="uc-modal-overlay"
          onClick={() => {
            if (!createMut.isPending) {
              setCreating(false);
              setFormError(null);
            }
          }}
        >
          <div
            className="uc-modal"
            style={{ maxWidth: 500 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="uc-modal-header">
              <div>
                <h3>Create New Dashboard</h3>
                <p>Select a catalog and schema namespace to register and store your dashboard.</p>
              </div>
              <button
                className="uc-icon-btn"
                onClick={() => {
                  if (!createMut.isPending) {
                    setCreating(false);
                    setFormError(null);
                  }
                }}
                title="Close"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreate}>
              <div className="uc-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {formError && (
                  <div
                    style={{
                      padding: '10px 12px',
                      background: '#fef2f2',
                      border: '1px solid #fecaca',
                      borderRadius: 6,
                      color: '#b91c1c',
                      fontSize: 13,
                    }}
                  >
                    {formError}
                  </div>
                )}

                <label className="uc-field">
                  <span className="uc-field-label">
                    Dashboard Name <span style={{ color: '#ef4444' }}>*</span>
                  </span>
                  <input
                    autoFocus
                    type="text"
                    placeholder="e.g. sales_performance_analytics"
                    value={newName}
                    onChange={(event) => {
                      setNewName(event.target.value);
                      setFormError(null);
                    }}
                    className="input-field"
                    required
                  />
                </label>

                <label className="uc-field">
                  <span className="uc-field-label">
                    Catalog <span style={{ color: '#ef4444' }}>*</span>
                  </span>
                  <select
                    className="input-field"
                    value={selectedCatalog}
                    onChange={(event) => handleCatalogChange(event.target.value)}
                    required
                    disabled={loadingCatalogs || createMut.isPending}
                  >
                    <option value="">-- Select Catalog --</option>
                    {catalogs.map((cat) => (
                      <option key={cat.id || cat.name} value={cat.name}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="uc-field">
                  <span className="uc-field-label">
                    Schema <span style={{ color: '#ef4444' }}>*</span>
                  </span>
                  <select
                    className="input-field"
                    value={selectedSchema}
                    onChange={(event) => {
                      setSelectedSchema(event.target.value);
                      setFormError(null);
                    }}
                    required
                    disabled={!selectedCatalog || createMut.isPending}
                  >
                    <option value="">
                      {!selectedCatalog ? 'Select a catalog first...' : '-- Select Schema --'}
                    </option>
                    {availableSchemas.map((sch) => (
                      <option key={sch.id || sch.name} value={sch.name}>
                        {sch.name}
                      </option>
                    ))}
                  </select>
                  {!selectedCatalog ? (
                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>
                      Select a catalog to load its schemas.
                    </span>
                  ) : availableSchemas.length === 0 ? (
                    <span style={{ fontSize: 11, color: '#f59e0b', marginTop: 2 }}>
                      No schemas found in this catalog.
                    </span>
                  ) : null}
                </label>
              </div>

              <div className="uc-modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: 16 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setCreating(false);
                    setNewName('');
                    setSelectedCatalog('');
                    setSelectedSchema('');
                    setFormError(null);
                  }}
                  disabled={createMut.isPending}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!isFormValid || createMut.isPending}
                >
                  {createMut.isPending ? 'Creating...' : 'Create Dashboard'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
