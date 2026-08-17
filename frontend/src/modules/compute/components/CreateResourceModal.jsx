import { useState } from 'react';

const RUNTIMES = [
  { id: 'spark', label: 'Spark', icon: '⚡', description: 'Distributed batch processing' },
  { id: 'flink', label: 'Flink', icon: '🌊', description: 'Stream processing' },
  { id: 'ray', label: 'Ray', icon: '🤖', description: 'ML / distributed Python' },
  { id: 'duckdb', label: 'DuckDB', icon: '🦆', description: 'In-process analytical SQL' },
];

const cardStyle = (selected, disabled) => ({
  padding: '12px 16px',
  border: `1px solid ${selected ? 'var(--color-accent, #6366f1)' : 'var(--color-border)'}`,
  borderRadius: '8px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  background: selected
    ? 'var(--color-accent-muted, rgba(99,102,241,0.1))'
    : disabled
    ? 'var(--color-surface-disabled, #f3f4f6)'
    : 'var(--color-surface)',
  opacity: disabled ? 0.5 : 1,
  transition: 'border-color 0.15s, background 0.15s',
});

/**
 * Modal to create a new compute resource.
 * @param {{ isOpen: boolean, profiles: any[], onClose: () => void, onCreate: (resource: any) => Promise<void> }} props
 */
export default function CreateResourceModal({ isOpen, profiles, onClose, onCreate }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    runtime: null,
    profile: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleRuntimeSelect = (runtime) => {
    setFormData((prev) => ({ ...prev, runtime }));
  };

  const handleProfileSelect = (profileId) => {
    setFormData((prev) => ({ ...prev, profile: profileId }));
  };

  async function handleSubmit(e) {
    e.preventDefault();
    if (!formData.name.trim() || !formData.runtime || !formData.profile) {
      setError('Please fill in all required fields');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await onCreate({
        name: formData.name,
        description: formData.description || null,
        runtime: formData.runtime,
        profile: formData.profile,
      });
      setFormData({ name: '', description: '', runtime: null, profile: null });
      onClose();
    } catch (err) {
      setError(err?.response?.data?.message || err?.message || 'Failed to create resource');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.3)',
          zIndex: 999,
        }}
      />
      {/* Modal */}
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1000,
          background: 'var(--color-surface)',
          borderRadius: '12px',
          border: '1px solid var(--color-border)',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.2)',
          maxWidth: '600px',
          width: '90vw',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        <div style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Create Compute Resource</h2>
            <button
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '20px',
                cursor: 'pointer',
                color: 'var(--color-text-muted)',
              }}
            >
              ×
            </button>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Name and Description */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Name *
              </label>
              <input
                type="text"
                name="name"
                placeholder="e.g., Data Processing Pipeline"
                value={formData.name}
                onChange={handleInputChange}
                style={{
                  padding: '10px 12px',
                  border: '1px solid var(--color-border)',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontFamily: 'inherit',
                }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Description
              </label>
              <textarea
                name="description"
                placeholder="Optional description of this compute resource"
                value={formData.description}
                onChange={handleInputChange}
                style={{
                  padding: '10px 12px',
                  border: '1px solid var(--color-border)',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontFamily: 'inherit',
                  minHeight: '60px',
                  resize: 'none',
                }}
              />
            </div>

            {/* Runtime Selector */}
            <div>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-muted)', display: 'block', marginBottom: '8px' }}>
                Runtime *
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                {RUNTIMES.map((rt) => (
                  <div
                    key={rt.id}
                    style={cardStyle(formData.runtime === rt.id, false)}
                    onClick={() => handleRuntimeSelect(rt.id)}
                  >
                    <div style={{ fontSize: '20px', marginBottom: '4px' }}>{rt.icon}</div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>{rt.label}</div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                      {rt.description}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Profile Selector */}
            <div>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-muted)', display: 'block', marginBottom: '8px' }}>
                Compute Profile *
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                {profiles.map((p) => (
                  <div
                    key={p.id}
                    title={p.available ? p.description : p.reason}
                    style={cardStyle(formData.profile === p.id, !p.available)}
                    onClick={() => p.available && handleProfileSelect(p.id)}
                  >
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>{p.label}</div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                      {p.available ? p.description : p.reason}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Error */}
            {error && (
              <div
                style={{
                  padding: '10px 12px',
                  background: 'var(--color-error-muted, rgba(239,68,68,0.1))',
                  border: '1px solid var(--color-error, #ef4444)',
                  borderRadius: '6px',
                  fontSize: '13px',
                  color: 'var(--color-error, #ef4444)',
                }}
              >
                {error}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', paddingTop: '12px' }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: '10px 16px',
                  background: 'var(--color-surface-secondary)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '6px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  color: 'var(--color-text)',
                }}
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                style={{
                  padding: '10px 16px',
                  background: 'var(--color-accent, #6366f1)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.6 : 1,
                }}
                disabled={loading}
              >
                {loading ? 'Creating…' : 'Create Resource'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
