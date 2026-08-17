import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, FileText, Plus, Search, Trash2 } from 'lucide-react';
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

async function fetchNotebooks(): Promise<NotebookEntry[]> {
  const res = await api.get<{ notebooks: NotebookEntry[] }>('/notebook/list');
  return res.data.notebooks;
}

async function createNotebook(payload: { name: string; folder: string }): Promise<{ path: string }> {
  const res = await api.post<{ path: string }>('/notebook/create', payload);
  return res.data;
}

async function deleteNotebook(path: string): Promise<void> {
  await api.delete(`/notebook/files/${path}`);
}

export default function NotebooksListPage() {
  const navigate = useScopedNavigate();
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [scheduleTarget, setScheduleTarget] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const { data: notebooks = [], isLoading } = useQuery({
    queryKey: ['notebooks-list'],
    queryFn: fetchNotebooks,
  });

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => listJobs(),
  });

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

  function openNotebookInCatalog(path: string) {
    const clean = path.replace(/\\/g, '/').replace(/^\//, '');
    const parts = clean.split('/');
    if (parts.length >= 3) {
      const catalog = parts[0];
      const schema = parts[1];
      const filename = parts.slice(2).join('/');
      navigate(`/data-catalog/${encodeURIComponent(catalog)}/${encodeURIComponent(schema)}/${encodeURIComponent(filename)}`);
    } else {
      navigate(`/data-catalog?path=${encodeURIComponent(clean)}`);
    }
  }

  const createMut = useMutation({
    mutationFn: createNotebook,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['notebooks-list'] });
      openNotebookInCatalog(data.path);
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteNotebook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebooks-list'] }),
  });

  function handleCreate() {
    const name = newName.trim() || 'untitled';
    createMut.mutate({ name, folder: '' });
    setNewName('');
    setCreating(false);
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
        <button className="btn btn-primary" onClick={() => setCreating(true)}>
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
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <input
            autoFocus
            type="text"
            placeholder="Notebook name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') handleCreate();
              if (event.key === 'Escape') {
                setCreating(false);
                setNewName('');
              }
            }}
            className="form-input"
            style={{ flex: 1 }}
          />
          <button className="btn btn-primary" onClick={handleCreate}>Create</button>
          <button className="btn btn-secondary" onClick={() => { setCreating(false); setNewName(''); }}>Cancel</button>
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
