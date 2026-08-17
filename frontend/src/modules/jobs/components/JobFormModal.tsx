import { useState } from 'react';
import { X, Briefcase } from 'lucide-react';
import type { Job } from '../lib/jobsTypes';

interface Props {
  job?: Job;
  onSave: (data: { name: string; description?: string }) => Promise<void>;
  onCancel: () => void;
}

export default function JobFormModal({ job, onSave, onCancel }: Props) {
  const isEdit = !!job;
  const [name, setName] = useState(job?.name ?? '');
  const [desc, setDesc] = useState(job?.description ?? '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError('Job name is required.'); return; }
    setError(null);
    setLoading(true);
    try {
      await onSave({ name: name.trim(), description: desc.trim() || undefined });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(e?.response?.data?.detail ?? e?.message ?? 'Failed to save job');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCancel} style={{ zIndex: 100 }}>
      <div
        className="modal-panel"
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(480px, calc(100vw - 2rem))' }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="jfm-title"
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Briefcase size={18} style={{ color: 'var(--color-primary)' }} />
            <span className="modal-title" id="jfm-title">
              {isEdit ? 'Edit job' : 'Create job'}
            </span>
          </div>
          <button type="button" className="btn-icon" onClick={onCancel} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div style={{
                padding: '8px 12px', borderRadius: 6,
                background: 'rgba(220,38,38,0.08)', color: 'var(--color-danger)',
                fontSize: '0.8125rem',
              }}>
                {error}
              </div>
            )}

            <div className="form-field">
              <label className="form-label" htmlFor="jfm-name">Job name *</label>
              <input
                id="jfm-name"
                type="text"
                className="form-input"
                placeholder="e.g. Daily Asset Sync"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="jfm-desc">Description</label>
              <textarea
                id="jfm-desc"
                className="form-input"
                placeholder="What does this job do? (optional)"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <div className="modal-footer" style={{ padding: '0 1.25rem 1.25rem', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? (isEdit ? 'Saving…' : 'Creating…') : (isEdit ? 'Save changes' : 'Create job')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
