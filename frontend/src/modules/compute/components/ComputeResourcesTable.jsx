import { useState } from 'react';
import { Check, Play, Square, Trash2, X } from 'lucide-react';
import { AppTable } from '@/components/common/AppTable';

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
  const [confirmDelete, setConfirmDelete] = useState(null);

  const isRunning = (resource) => resource.phase === 'Running';
  const isPending = (resource) => resource.phase === 'Pending';
  const isStarting = (resource) => resource.desired_status === 'running' && !isRunning(resource);

  const columns = [
    {
      key: 'state',
      header: 'State',
      className: 'app-table-muted',
      render: (resource) => {
        const phase = resource.phase || 'Unknown';
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center' }} title={`Status: ${phase}`}>
            <span
              aria-hidden="true"
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: stateColorMap[phase] || stateColorMap.Unknown,
                flexShrink: 0,
              }}
            />
          </span>
        );
      },
    },
    {
      key: 'name',
      header: 'Name',
      render: (resource) => (
        <span style={{ fontWeight: 500 }}>
          {resource.name}
          {resource.is_default ? <span className="compute-default-pill">Default</span> : null}
        </span>
      ),
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
      render: (resource) => confirmDelete === resource.id ? (
        <>
          <button
            className="ghost-icon-btn"
            onClick={(event) => {
              event.stopPropagation();
              setConfirmDelete(null);
              onDelete(resource.id);
            }}
            disabled={loadingId === resource.id}
            title="Confirm delete"
            aria-label={`Confirm delete ${resource.name}`}
            style={{ color: 'var(--color-danger, #ef4444)' }}
          >
            {loadingId === resource.id ? '...' : <Check size={13} />}
          </button>
          <button
            className="ghost-icon-btn"
            onClick={(event) => {
              event.stopPropagation();
              setConfirmDelete(null);
            }}
            disabled={loadingId === resource.id}
            title="Cancel"
            aria-label={`Cancel delete ${resource.name}`}
          >
            <X size={13} />
          </button>
        </>
      ) : (
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
              setConfirmDelete(resource.id);
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
    <AppTable
      columns={columns}
      rows={resources}
      rowKey={(resource) => resource.id}
      onRowClick={onSelect}
      rowClassName={(resource) => confirmDelete === resource.id ? 'is-danger' : undefined}
      emptyText="No compute resources yet"
    />
  );
}
