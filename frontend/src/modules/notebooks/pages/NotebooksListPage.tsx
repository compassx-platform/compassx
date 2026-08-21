import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, FileText, Plus, Search, Trash2, X } from 'lucide-react';
import api from '@/lib/api';
import ScheduleDialog from '@/modules/notebooks/components/ScheduleDialog';
import { listJobs } from '@/modules/jobs/lib/jobsApi';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';

interface NotebookEntry {
  path: string;
  name: string;
  full_name?: string;
  storage_location?: string;
}

interface CatalogSchemaSummary {
  id: string;
  name: string;
}

interface CatalogSummary {
  id: string;
  name: string;
  schemas: CatalogSchemaSummary[];
}

async function fetchNotebooks(): Promise<NotebookEntry[]> {
  const res = await api.get<{ notebooks: NotebookEntry[] }>('/notebook/list');
  return res.data.notebooks;
}

async function createNotebook(payload: { name: string; catalog_name: string; schema_name: string }): Promise<{
  path: string;
  catalog_name?: string;
  schema_name?: string;
  name?: string;
}> {
  const res = await api.post<{ path: string; catalog_name?: string; schema_name?: string; name?: string }>('/notebook/create', payload);
  return res.data;
}

async function deleteNotebook(path: string): Promise<void> {
  await api.delete(`/notebook/files/${path}`);
}

export default function NotebooksListPage() {
  const navigate = useScopedNavigate();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [selectedCatalog, setSelectedCatalog] = useState('');
  const [selectedSchema, setSelectedSchema] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [scheduleTarget, setScheduleTarget] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const { data: notebooks = [], isLoading } = useQuery({
    queryKey: ['notebooks-list'],
    queryFn: fetchNotebooks,
  });

  const { data: catalogs = [], isLoading: loadingCatalogs } = useQuery({
    queryKey: ['uc-catalogs'],
    queryFn: () => api.get<CatalogSummary[]>('/catalog/catalogs').then((r) => r.data),
  });

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => listJobs(),
  });

  const currentCatalogObj = catalogs.find((c) => c.name === selectedCatalog);
  const availableSchemas = currentCatalogObj?.schemas || [];
  const isFormValid = newName.trim().length > 0 && Boolean(selectedCatalog) && Boolean(selectedSchema);

  function generateDefaultNotebookName() {
    const existingNames = new Set(notebooks.map((n) => n.name.toLowerCase()));
    let index = 1;
    while (existingNames.has(`untitled_notebook_${index}`) || existingNames.has(`untitled_notebook_${index}.ipynb`)) {
      index++;
    }
    return `untitled_notebook_${index}`;
  }

  function handleOpenCreateModal() {
    const defaultName = generateDefaultNotebookName();
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

  const scheduledPaths = new Set(
    jobs.flatMap((job) => job.task_definitions)
      .filter((task) => task.task_type === 'notebook' && task.target_ref)
      .map((task) => task.target_ref as string),
  );
  const filtered = notebooks.filter((notebook) => {
    const query = search.trim().toLowerCase();
    return !query
      || notebook.name.toLowerCase().includes(query)
      || notebook.path.toLowerCase().includes(query)
      || notebook.full_name?.toLowerCase().includes(query)
      || notebook.storage_location?.toLowerCase().includes(query);
  });

  function openNotebookInCatalog(path: string, catalogName?: string, schemaName?: string, nbName?: string) {
    const clean = path.replace(/\\/g, '/').replace(/^\//, '');
    const parts = clean.split('/');
    if (catalogName && schemaName && nbName) {
      const safeNb = nbName.endsWith('.ipynb') ? nbName.slice(0, -6) : nbName;
      navigate(`/data-catalog/${encodeURIComponent(catalogName)}/${encodeURIComponent(schemaName)}/notebook/${encodeURIComponent(safeNb)}?path=${encodeURIComponent(clean)}`);
    } else if (parts.length >= 3) {
      const catalog = parts[0];
      const schema = parts[1];
      const filename = parts.slice(2).join('/');
      const safeNb = filename.endsWith('.ipynb') ? filename.slice(0, -6) : filename;
      navigate(`/data-catalog/${encodeURIComponent(catalog)}/${encodeURIComponent(schema)}/notebook/${encodeURIComponent(safeNb)}?path=${encodeURIComponent(clean)}`);
    } else {
      navigate(`/data-catalog?path=${encodeURIComponent(clean)}`);
    }
  }

  const createMut = useMutation({
    mutationFn: createNotebook,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['notebooks-list'] });
      queryClient.invalidateQueries({ queryKey: ['uc-catalogs'] });
      setCreating(false);
      setNewName('');
      setSelectedCatalog('');
      setSelectedSchema('');
      setFormError(null);
      openNotebookInCatalog(data.path, data.catalog_name, data.schema_name, data.name);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to create notebook.';
      setFormError(msg);
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteNotebook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebooks-list'] }),
  });

  function handleCreate(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const name = newName.trim();
    if (!name) {
      setFormError('Please enter a notebook name.');
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
      catalog_name: selectedCatalog,
      schema_name: selectedSchema,
    });
  }

  function handleOpen(path: string) {
    openNotebookInCatalog(path);
  }

  function handleDelete(event: React.MouseEvent, path: string) {
    event.stopPropagation();
    if (confirm(`Delete "${path}"?`)) {
      deleteMut.mutate(path);
    }
  }

  const columns: AppTableColumn<NotebookEntry>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (notebook) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <FileText size={14} color="var(--color-text-muted)" />
          <span style={{ fontWeight: 500 }}>{notebook.name}</span>
        </span>
      ),
    },
    {
      key: 'path',
      header: 'Path',
      className: 'app-table-muted',
      render: (notebook) => notebook.storage_location || notebook.path,
    },
    {
      key: 'schedule',
      header: 'Schedule',
      render: (notebook) => scheduledPaths.has(notebook.path) ? (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <CalendarClock size={13} className="nb-schedule-icon" />
          Scheduled
        </span>
      ) : '-',
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (notebook) => (
        <>
          <button
            className="ghost-icon-btn"
            title="Schedule notebook"
            aria-label={`Schedule ${notebook.name}`}
            onClick={(event) => {
              event.stopPropagation();
              setScheduleTarget(notebook.path);
            }}
          >
            <CalendarClock size={13} />
          </button>
          <button
            className="ghost-icon-btn"
            title="Delete notebook"
            aria-label={`Delete ${notebook.name}`}
            onClick={(event) => handleDelete(event, notebook.path)}
          >
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

  return (
    <div className="page-section notebooks-page">
      <div className="db-page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <FileText size={22} color="var(--color-primary)" />
          <h1 className="db-page-title">Notebooks</h1>
        </div>
        <button className="btn btn-primary" onClick={handleOpenCreateModal}>
          <Plus size={14} /> New Notebook
        </button>
      </div>

      <div className="db-filter-row">
        <div className="search-bar-wrapper" style={{ flex: '0 0 300px' }}>
          <Search size={13} className="search-icon" />
          <input
            className="search-input"
            placeholder="Search notebooks..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
          {filtered.length} notebook{filtered.length !== 1 ? 's' : ''}
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
                <h3>Create New Notebook</h3>
                <p>Select a catalog and schema namespace to register and store your notebook.</p>
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
                    Notebook Name <span style={{ color: '#ef4444' }}>*</span>
                  </span>
                  <input
                    autoFocus
                    type="text"
                    placeholder="e.g. data_transformation"
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
                  {createMut.isPending ? 'Creating...' : 'Create Notebook'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <AppTable
        columns={columns}
        rows={filtered}
        rowKey={(notebook) => notebook.path}
        onRowClick={(notebook) => handleOpen(notebook.path)}
        emptyText="No notebooks yet. Create one to get started."
        isLoading={isLoading}
      />

      {scheduleTarget && (
        <ScheduleDialog
          notebookPath={scheduleTarget}
          onClose={() => {
            setScheduleTarget(null);
            queryClient.invalidateQueries({ queryKey: ['jobs'] });
          }}
        />
      )}
    </div>
  );
}
