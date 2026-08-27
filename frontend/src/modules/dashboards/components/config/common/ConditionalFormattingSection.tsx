import { Plus, Trash2 } from 'lucide-react';
import CollapsibleSection from './CollapsibleSection';

interface ConditionalRule {
  min?: number;
  max?: number;
  color: string;
}

interface ConditionalFormattingSectionProps {
  rules?: ConditionalRule[];
  onChange: (rules?: ConditionalRule[]) => void;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export default function ConditionalFormattingSection({
  rules = [],
  onChange,
  collapsible = true,
  defaultOpen = false,
}: ConditionalFormattingSectionProps) {
  function handleAddRule() {
    const newRule: ConditionalRule = {
      color: '#10B981',
      min: undefined,
      max: undefined,
    };
    onChange([...rules, newRule]);
  }

  function handleUpdateRule(index: number, patch: Partial<ConditionalRule>) {
    const updated = rules.map((r, i) => (i === index ? { ...r, ...patch } : r));
    onChange(updated);
  }

  function handleRemoveRule(index: number) {
    const updated = rules.filter((_, i) => i !== index);
    onChange(updated.length > 0 ? updated : undefined);
  }

  const content = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
          Color number based on value threshold
        </span>
        <button
          type="button"
          onClick={handleAddRule}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--color-primary)',
            fontSize: '0.72rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: 0,
          }}
        >
          <Plus size={12} /> Add Rule
        </button>
      </div>

      {rules.length === 0 ? (
        <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
          No conditional formatting rules set (uses default theme color).
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {rules.map((rule, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 8px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 6,
              }}
            >
              <input
                type="color"
                value={rule.color || '#10B981'}
                onChange={(e) => handleUpdateRule(idx, { color: e.target.value })}
                style={{ width: 22, height: 22, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
                title="Rule color"
              />
              <span style={{ fontSize: '0.7rem', color: '#64748b' }}>≥</span>
              <input
                type="number"
                placeholder="Min"
                value={rule.min !== undefined ? rule.min : ''}
                onChange={(e) =>
                  handleUpdateRule(idx, {
                    min: e.target.value !== '' ? Number(e.target.value) : undefined,
                  })
                }
                style={{
                  width: 55,
                  padding: '2px 4px',
                  fontSize: '0.72rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: 4,
                }}
              />
              <span style={{ fontSize: '0.7rem', color: '#64748b' }}>&lt;</span>
              <input
                type="number"
                placeholder="Max"
                value={rule.max !== undefined ? rule.max : ''}
                onChange={(e) =>
                  handleUpdateRule(idx, {
                    max: e.target.value !== '' ? Number(e.target.value) : undefined,
                  })
                }
                style={{
                  width: 55,
                  padding: '2px 4px',
                  fontSize: '0.72rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: 4,
                }}
              />
              <button
                type="button"
                onClick={() => handleRemoveRule(idx)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#ef4444',
                  cursor: 'pointer',
                  padding: '2px',
                  marginLeft: 'auto',
                }}
                title="Remove rule"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  if (!collapsible) {
    return content;
  }

  return (
    <CollapsibleSection title="Conditional Formatting" defaultOpen={defaultOpen}>
      {content}
    </CollapsibleSection>
  );
}
