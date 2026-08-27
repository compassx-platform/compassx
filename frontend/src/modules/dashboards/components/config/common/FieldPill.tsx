interface FieldPillProps {
  name: string;
  type?: string;
  transform?: string;
  displayName?: string;
  onClick?: () => void;
  onRemove: () => void;
}

export default function FieldPill({
  name,
  type = 'string',
  displayName,
  onClick,
  onRemove,
}: FieldPillProps) {
  const isNumeric = ['integer', 'float', 'number', 'double', 'decimal'].includes((type || '').toLowerCase());
  const displayLabel = displayName || name;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
        borderRadius: 5,
        padding: '6px 8px',
        marginTop: 4,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.15s ease',
        userSelect: 'none',
      }}
      title={onClick ? 'Click to configure options' : undefined}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        <span
          style={{
            fontSize: '0.6rem',
            fontWeight: 'bold',
            color: '#475569',
            background: '#e2e8f0',
            padding: '1px 4px',
            borderRadius: 3,
            letterSpacing: '0.3px',
          }}
        >
          {isNumeric ? '1.2' : 'Abc'}
        </span>
        <span
          style={{
            fontSize: '0.77rem',
            fontWeight: 500,
            color: '#0f172a',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {displayLabel}
        </span>
      </div>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '0 2px',
          color: '#64748b',
          fontSize: '0.8rem',
          display: 'flex',
          alignItems: 'center',
        }}
        title="Remove field"
      >
        —
      </button>
    </div>
  );
}
