/** DetailDrawer – slide-in panel for viewing/editing a breakdown record */

import { BreakdownRecord } from '@/types';
import { X } from 'lucide-react';

interface DetailDrawerProps {
  record: BreakdownRecord | null;
  onClose: () => void;
  onEdit: (record: BreakdownRecord) => void;
}

function Field({ label, value }: { label: string; value?: string }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="label">{label}</div>
      <div style={{ fontSize: '0.9rem' }}>{value || '—'}</div>
    </div>
  );
}

export default function DetailDrawer({ record, onClose, onEdit }: DetailDrawerProps) {
  if (!record) return null;

  const severityClass = `badge badge-${record.severity || 'low'}`;
  const statusClass = record.status?.toLowerCase() === 'open' ? 'badge badge-open' : 'badge badge-closed';

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.5)',
          zIndex: 40,
        }}
      />
      {/* Drawer */}
      <div
        className="animate-slide-in"
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: 420,
          background: 'var(--color-surface)',
          borderLeft: '1px solid var(--color-border)',
          padding: '1.5rem',
          overflowY: 'auto',
          zIndex: 50,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600 }}>Event Detail</h2>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        <Field label="Breakdown Type" value={record.breakdown_type} />
        <Field label="Asset" value={record.asset_name || record.asset_id} />
        <Field label="Child Asset" value={record.child_asset_name || record.child_asset_id} />

        <div style={{ marginBottom: 16 }}>
          <div className="label">Severity</div>
          <span className={severityClass}>{record.severity || '—'}</span>
        </div>

        <div style={{ marginBottom: 16 }}>
          <div className="label">Status</div>
          <span className={statusClass}>{record.status || '—'}</span>
        </div>

        <Field label="Description" value={record.description} />
        <Field label="Timestamp" value={record.timestamp ? new Date(record.timestamp).toLocaleString() : undefined} />
        <Field label="Created By" value={record.created_by} />

        <div style={{ paddingTop: 16, borderTop: '1px solid var(--color-border)', marginTop: 24 }}>
          <button className="btn-primary" onClick={() => onEdit(record)} style={{ width: '100%' }}>
            Edit Event
          </button>
        </div>
      </div>
    </>
  );
}
