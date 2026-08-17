import { AlertTriangle, Info, X } from 'lucide-react';

interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'info';
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;
}

export default function ConfirmActionModal({
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  isLoading = false,
  onConfirm,
  onCancel,
  children,
}: Props) {
  const colors = {
    danger:  { icon: '#dc2626', btn: 'var(--color-danger, #dc2626)' },
    warning: { icon: '#d97706', btn: '#d97706' },
    info:    { icon: 'var(--color-primary)', btn: 'var(--color-primary)' },
  }[variant];

  const Icon = variant === 'info' ? Info : AlertTriangle;

  return (
    <div
      className="modal-backdrop"
      onClick={onCancel}
      style={{ zIndex: 100 }}
    >
      <div
        className="modal-panel"
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(440px, calc(100vw - 2rem))', padding: 0 }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cam-title"
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          padding: '1.25rem 1.25rem 0',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: colors.icon, display: 'flex', flexShrink: 0 }}>
              <Icon size={20} />
            </span>
            <h3 id="cam-title" style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>
              {title}
            </h3>
          </div>
          <button
            type="button"
            className="btn-icon"
            onClick={onCancel}
            aria-label="Close"
            style={{ marginTop: -4 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '1rem 1.25rem', color: 'var(--color-text-muted)', fontSize: '0.875rem', lineHeight: 1.55 }}>
          {message}
          {children}
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', justifyContent: 'flex-end', gap: 8,
          padding: '0.75rem 1.25rem 1.25rem',
          borderTop: '1px solid var(--color-border)',
        }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={isLoading}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className="btn"
            onClick={onConfirm}
            disabled={isLoading}
            style={{ background: colors.btn, color: '#fff' }}
          >
            {isLoading ? `${confirmLabel}…` : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
