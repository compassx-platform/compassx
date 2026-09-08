import { useState } from 'react';
import { Play, Square, Trash2 } from 'lucide-react';
import { AppTable } from '@/components/common/AppTable';
import ConfirmDialog from '@/components/common/ConfirmDialog';

const stateColorMap = {
  Running: '#10b981',
  Pending: '#f59e0b',
  Succeeded: '#6366f1',
  Failed: '#ef4444',
  Unknown: '#6b7280',
  Stopped: '#6b7280',
  Missing: '#f97316',
};

const runtimeIconMap = {
  spark: 'Spark',
  flink: 'Flink',
  ray: 'Ray',
  duckdb: 'DuckDB',
};

/**
 * Table showing compute resources with actions to start/stop/delete.
 * @param {{ resources: any[], onStart: (id: string) => void, onStop: (id: string) => void, onDelete: (id: string) => void, onSelect: (resource: any) => void, loadingId?: string }} props
 */
export default function ComputeResourcesTable({ resources, onStart, onStop, onDelete, onSelect, loadingId }) {
  const [resourceToDelete, setResourceToDelete] = useState(null);

  const isRunning = (resource) => resource.phase === 'Running';
  const isPending = (resource) => resource.phase === 'Pending';
  const isStarting = (resource) => resource.desired_status === 'running' && !isRunning(resource);

  const handleConfirmDelete = async () => {
    if (!resourceToDelete) return;
    try {
      await onDelete(resourceToDelete.id);
    } finally {
      setResourceToDelete(null);
    }
  };

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (resource) => {
        const phase = resource.phase || 'Unknown';
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontWeight: 500 }}>
            <span
              title={`Status: ${phase}`}
              aria-label={`Status: ${phase}`}
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: stateColorMap[phase] || stateColorMap.Unknown,
                flexShrink: 0,
              }}
            />
            <span>{resource.name}</span>
            {resource.is_default ? <span className="compute-default-pill">Default</span> : null}
          </span>
        );
      },
    },
    {
      key: 'runtime',
      header: 'Runtime',
      render: (resource) => runtimeIconMap[resource.runtime] || resource.runtime,
    },
    {
      key: 'profile',
      header: 'Profile',
      render: (resource) => resource.profile,
    },
    {
      key: 'created_by',
      header: 'Created By',
      className: 'app-table-muted',
      render: (resource) => resource.created_by,
    },
    {
      key: 'created',
      header: 'Created',
      className: 'app-table-muted',
      render: (resource) => new Date(resource.created_at).toLocaleDateString(),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (resource) => (
        <>
          {isRunning(resource) || isStarting(resource) ? (
            <button
              className="ghost-icon-btn"
              onClick={(event) => {
                event.stopPropagation();
                onStop(resource.id);
              }}
              disabled={loadingId === resource.id || isPending(resource)}
              title="Stop"
              aria-label={`Stop ${resource.name}`}
            >
              {loadingId === resource.id ? '...' : <Square size={13} fill="#5A5A5A" strokeWidth={0} />}
            </button>
          ) : (
            <button
              className="ghost-icon-btn"
              onClick={(event) => {
                event.stopPropagation();
                onStart(resource.id);
              }}
              disabled={loadingId === resource.id}
              title="Start"
              aria-label={`Start ${resource.name}`}
            >
              {loadingId === resource.id ? '...' : <Play size={13} fill="#5A5A5A" strokeWidth={0} />}
            </button>
          )}
          <button
            className="ghost-icon-btn"
            onClick={(event) => {
              event.stopPropagation();
              setResourceToDelete(resource);
            }}
            disabled={loadingId === resource.id}
            title="Delete"
            aria-label={`Delete ${resource.name}`}
          >
            <Trash2 size={13} />
          </button>
        </>
      ),
    },
  ];

  return (
    <>
      <AppTable
        columns={columns}
        rows={resources}
        rowKey={(resource) => resource.id}
        onRowClick={onSelect}
        emptyText="No compute resources yet"
      />

      {resourceToDelete && (
        <ConfirmDialog
          title="Delete Compute Resource"
          message={`Are you sure you want to delete "${resourceToDelete.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          onCancel={() => setResourceToDelete(null)}
          onConfirm={handleConfirmDelete}
          isLoading={loadingId === resourceToDelete.id}
          isDestructive
        />
      )}
    </>
  );
}
