import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useExplorerQuery, useDeleteBreakdown } from '@/modules/workflows/hooks/useBreakdownEvents';
import FilterPanel from '@/components/explorer/FilterPanel';
import DetailDrawer from '@/components/explorer/DetailDrawer';
import type { BreakdownRecord } from '@/types';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import ConfirmDialog from '@/components/common/ConfirmDialog';
import { ChevronLeft, ChevronRight, Edit, Eye, Plus, Trash2 } from 'lucide-react';

function SeverityBadge({ severity }: { severity?: string }) {
  const cls = `badge badge-${severity || 'low'}`;
  return <span className={cls}>{severity || '-'}</span>;
}

function StatusBadge({ status }: { status?: string }) {
  const s = (status || '').toLowerCase();
  const cls = s === 'open' ? 'badge badge-open' : 'badge badge-closed';
  return <span className={cls}>{status || '-'}</span>;
}

export default function BreakdownExplorer() {
  const navigate = useScopedNavigate();
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const size = 15;

  const { data, isLoading, refetch } = useExplorerQuery({
    dataset: 'breakdown_events',
    filters,
    pagination: { page, size },
  });

  const deleteMut = useDeleteBreakdown();
  const [selectedRecord, setSelectedRecord] = useState<BreakdownRecord | null>(null);
  const [recordPendingDelete, setRecordPendingDelete] = useState<BreakdownRecord | null>(null);

  const handleDelete = async (record: BreakdownRecord) => {
    await deleteMut.mutateAsync(record.record_id);
    setRecordPendingDelete(null);
    refetch();
  };

  const handleEdit = (record: BreakdownRecord) => {
    navigate(`/breakdown/new?edit_id=${record.record_id}`);
  };

  const columns: AppTableColumn<BreakdownRecord>[] = [
    { key: 'type', header: 'Type', render: (row) => row.breakdown_type || '-' },
    { key: 'asset', header: 'Asset', render: (row) => row.asset_name || row.asset_id },
    { key: 'child_asset', header: 'Child Asset', render: (row) => row.child_asset_name || row.child_asset_id || '-' },
    { key: 'severity', header: 'Severity', render: (row) => <SeverityBadge severity={row.severity} /> },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'timestamp', header: 'Timestamp', render: (row) => row.timestamp ? new Date(row.timestamp).toLocaleString() : '-' },
    { key: 'created_by', header: 'Created By', render: (row) => row.created_by || '-' },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <div style={{ display: 'inline-flex', gap: 6 }} onClick={(event) => event.stopPropagation()}>
          <button className="btn-outline" style={{ padding: '0.3rem 0.5rem' }} title="View" onClick={() => setSelectedRecord(row)}>
            <Eye size={14} />
          </button>
          <button className="btn-outline" style={{ padding: '0.3rem 0.5rem' }} title="Edit" onClick={() => handleEdit(row)}>
            <Edit size={14} />
          </button>
          <button className="btn-danger" style={{ padding: '0.3rem 0.5rem' }} title="Delete" onClick={() => setRecordPendingDelete(row)}>
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 600 }}>Event Explorer</h1>
        <button
          className="btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          onClick={() => navigate('/breakdown/new')}
        >
          <Plus size={16} /> New Event
        </button>
      </div>

      <FilterPanel filters={filters} onChange={(f) => { setFilters(f); setPage(1); }} />

      <div style={{ flex: 1 }}>
        <AppTable
          columns={columns}
          rows={data?.items || []}
          rowKey={(row) => row.id}
          onRowClick={setSelectedRecord}
          isLoading={isLoading}
          emptyText="No records found."
        />
        {(data?.items?.length ?? 0) > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 0', fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
            <span>{data?.total || 0} record{(data?.total || 0) !== 1 && 's'}</span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button className="btn-outline" style={{ padding: '0.3rem 0.5rem' }} disabled={(data?.page || 1) <= 1} onClick={() => setPage((data?.page || 1) - 1)}>
                <ChevronLeft size={14} />
              </button>
              <span>Page {data?.page || 1} of {data?.pages || 0}</span>
              <button className="btn-outline" style={{ padding: '0.3rem 0.5rem' }} disabled={(data?.page || 1) >= (data?.pages || 0)} onClick={() => setPage((data?.page || 1) + 1)}>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {selectedRecord && (
        <DetailDrawer
          record={selectedRecord}
          onClose={() => setSelectedRecord(null)}
          onEdit={(r) => {
            setSelectedRecord(null);
            handleEdit(r);
          }}
        />
      )}
      {recordPendingDelete && (
        <ConfirmDialog
          title="Delete event"
          message="Delete this event? This action cannot be undone."
          confirmLabel="Delete"
          onCancel={() => setRecordPendingDelete(null)}
          onConfirm={() => handleDelete(recordPendingDelete)}
          isLoading={deleteMut.isPending}
        />
      )}
    </div>
  );
}


