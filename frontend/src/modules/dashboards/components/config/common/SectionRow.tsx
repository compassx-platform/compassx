import { HelpCircle, MoreVertical, Plus } from 'lucide-react';

interface SectionRowProps {
  title: React.ReactNode;
  tooltip?: string;
  onPlus?: () => void;
  plusDisabled?: boolean;
  onKebab?: () => void;
  children: React.ReactNode;
  actionText?: string;
}

export default function SectionRow({
  title,
  tooltip,
  onPlus,
  plusDisabled = false,
  onKebab,
  children,
  actionText,
}: SectionRowProps) {
  return (
    <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1a1a1a' }}>{title}</span>
          {tooltip && (
            <span
              title={tooltip}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                color: '#94a3b8',
                cursor: 'help',
              }}
            >
              <HelpCircle size={12} />
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {actionText && (
            <button
              onClick={plusDisabled ? undefined : onPlus}
              disabled={plusDisabled}
              style={{
                background: 'none',
                border: 'none',
                color: plusDisabled ? '#a1a1aa' : 'var(--color-primary)',
                fontSize: '0.72rem',
                cursor: plusDisabled ? 'not-allowed' : 'pointer',
                fontWeight: 500,
                padding: 0,
              }}
            >
              {actionText}
            </button>
          )}
          {onKebab && (
            <button
              onClick={onKebab}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                opacity: 0.6,
                display: 'flex',
                alignItems: 'center',
                padding: 0,
                color: '#334155',
              }}
            >
              <MoreVertical size={13} />
            </button>
          )}
          {onPlus && !actionText && (
            <button
              onClick={plusDisabled ? undefined : onPlus}
              disabled={plusDisabled}
              title={plusDisabled ? 'Multiple series not supported for this chart type' : 'Add metric series'}
              style={{
                background: 'none',
                border: 'none',
                cursor: plusDisabled ? 'not-allowed' : 'pointer',
                opacity: plusDisabled ? 0.3 : 0.75,
                display: 'flex',
                alignItems: 'center',
                padding: 0,
                color: plusDisabled ? '#94a3b8' : '#334155',
              }}
            >
              <Plus size={14} strokeWidth={2} />
            </button>
          )}
        </div>
      </div>
      {children}
    </div>
  );
}
