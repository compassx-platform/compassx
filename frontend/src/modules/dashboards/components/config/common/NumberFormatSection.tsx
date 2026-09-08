import type { NumberFormat } from '@/types/dashboard';
import CollapsibleSection from './CollapsibleSection';
import FieldRow from './FieldRow';

interface NumberFormatSectionProps {
  numberFormat?: NumberFormat;
  onChange: (updated?: NumberFormat) => void;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div style={{ display: 'flex', gap: 4, width: '100%' }}>
      {options.map((opt) => {
        const isSelected = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            style={{
              flex: 1,
              padding: '3px 6px',
              fontSize: '0.72rem',
              fontWeight: isSelected ? 600 : 400,
              color: isSelected ? '#0052cc' : '#475569',
              background: isSelected ? '#e7f0ff' : '#f8fafc',
              border: `1px solid ${isSelected ? '#0052cc' : '#e2e8f0'}`,
              borderRadius: 4,
              cursor: 'pointer',
              transition: 'all 0.12s ease',
              textAlign: 'center',
              whiteSpace: 'nowrap',
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export default function NumberFormatSection({
  numberFormat,
  onChange,
  collapsible = true,
  defaultOpen = false,
}: NumberFormatSectionProps) {
  const currentType = numberFormat?.type ?? 'number';
  const currentAbbr = numberFormat?.abbreviation ?? 'none';
  const currentDecMode = numberFormat?.decimalMode ?? (numberFormat?.decimals !== undefined ? 'exact' : 'all');

  const content = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Type Segmented Buttons */}
      <FieldRow label="Type">
        <SegmentedControl
          value={currentType}
          onChange={(v) =>
            onChange({
              ...(numberFormat ?? {}),
              type: v,
            })
          }
          options={[
            { value: 'number', label: 'Number' },
            { value: 'currency', label: 'Currency' },
            { value: 'percent', label: 'Percent' },
          ]}
        />
      </FieldRow>

      {/* Abbreviation Segmented Buttons */}
      <FieldRow label="Abbreviation">
        <SegmentedControl
          value={currentAbbr}
          onChange={(v) =>
            onChange({
              ...(numberFormat ?? {}),
              type: numberFormat?.type ?? 'number',
              abbreviation: v,
            })
          }
          options={[
            { value: 'none', label: 'None' },
            { value: 'compact', label: 'Compact' },
            { value: 'scientific', label: 'Scientific' },
          ]}
        />
      </FieldRow>

      {/* Decimals Mode Segmented Buttons */}
      <FieldRow label="Decimals">
        <SegmentedControl
          value={currentDecMode}
          onChange={(v) =>
            onChange({
              ...(numberFormat ?? {}),
              type: numberFormat?.type ?? 'number',
              decimalMode: v,
              decimals: v === 'all' ? undefined : (numberFormat?.decimals ?? 2),
            })
          }
          options={[
            { value: 'all', label: 'All' },
            { value: 'exact', label: 'Exact' },
            { value: 'max', label: 'Max' },
          ]}
        />
      </FieldRow>

      {/* Decimal Places Input (only when Exact or Max is chosen) */}
      {(currentDecMode === 'exact' || currentDecMode === 'max') && (
        <FieldRow label="Decimal Places">
          <input
            type="number"
            min={0}
            max={10}
            value={numberFormat?.decimals ?? 2}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : Math.max(0, Math.min(10, parseInt(e.target.value, 10) || 0));
              onChange({
                ...(numberFormat ?? {}),
                type: numberFormat?.type ?? 'number',
                decimals: val,
              });
            }}
            style={{
              width: '100%',
              padding: '5px 8px',
              fontSize: '0.77rem',
              border: '1px solid var(--color-border)',
              borderRadius: 4,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
            }}
          />
        </FieldRow>
      )}

      {/* Currency Symbol (only when Currency is selected) */}
      {currentType === 'currency' && (
        <FieldRow label="Currency Symbol">
          <input
            type="text"
            value={numberFormat?.currencySymbol ?? '$'}
            onChange={(e) =>
              onChange({
                ...(numberFormat ?? {}),
                type: 'currency',
                currencySymbol: e.target.value,
              })
            }
            placeholder="$"
            style={{
              width: '100%',
              padding: '5px 8px',
              fontSize: '0.77rem',
              border: '1px solid var(--color-border)',
              borderRadius: 4,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
            }}
          />
        </FieldRow>
      )}

      {/* Unit / Suffix */}
      <FieldRow label="Unit / Suffix">
        <input
          type="text"
          value={numberFormat?.unit ?? ''}
          onChange={(e) =>
            onChange({
              ...(numberFormat ?? {}),
              type: numberFormat?.type ?? 'number',
              unit: e.target.value || undefined,
            })
          }
          placeholder="e.g. ms, GB, kg, %, pts"
          style={{
            width: '100%',
            padding: '5px 8px',
            fontSize: '0.77rem',
            border: '1px solid var(--color-border)',
            borderRadius: 4,
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
          }}
        />
      </FieldRow>
    </div>
  );

  if (!collapsible) {
    return content;
  }

  return (
    <CollapsibleSection title="Number Format Details" defaultOpen={defaultOpen}>
      {content}
    </CollapsibleSection>
  );
}
