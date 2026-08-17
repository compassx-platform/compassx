/**
 * FilterWidget — renders interactive filter on canvas.
 * Reference:
 *   filter-multi-value-9e1ad2031c3f91167e0d5a22afc58442.png
 *   filter-single-value-7a9ffd07855603d52d03a383e16e62b5.png
 *   filter-date-picker-54b6e948f1ca0f1d3d89a8bb9d7ae38b.png
 *   filter-date-range-af081a657f9e8a27626dfae000a5747d.png
 *   filter-text-entry-3a8555777735f9039df3ba7fbd28c01a.png
 *   filter-range-slider-cb724ee4d18f4c9041294666d6fcb814.png
 */

import { useState } from 'react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useFieldValues } from '@/modules/dashboards/hooks/useDashboard';
import type { Widget, FilterValue } from '@/types/dashboard';

interface Props {
  widget: Widget;
}

export default function FilterWidget({ widget }: Props) {
  const { filterState, setFilterValue, activeDashboard } = useDashboardStore();
  const cfg = widget.filterConfig;

  const filterId = widget.id;
  const currentValue = filterState[filterId] ?? null;

  // Dynamic field values for dropdowns
  const dynamicDatasetId = cfg?.dynamicDatasetId ?? cfg?.datasetIds?.[0];
  const { data: fieldValues = [] } = useFieldValues(dynamicDatasetId, cfg?.field);

  function setValue(val: FilterValue) {
    setFilterValue(filterId, val);
  }

  if (!cfg) return <div style={{ padding: 8, fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Filter not configured</div>;

  const label = cfg.field ?? widget.title ?? 'Filter';
  const opts = cfg.listMode === 'static' ? (cfg.staticOptions ?? []) : fieldValues;

  return (
    <div style={{ padding: '6px 10px', height: '100%', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
        {label}
      </label>

      {cfg.filterType === 'multi_value' && (
        <MultiValueFilter value={currentValue as string[]} options={opts} onChange={setValue} allowAll={cfg.allowAll} />
      )}
      {cfg.filterType === 'single_value' && (
        <SingleValueFilter value={currentValue as string} options={opts} onChange={setValue} allowAll={cfg.allowAll} />
      )}
      {cfg.filterType === 'date_picker' && (
        <DatePickerFilter value={currentValue as string} onChange={setValue} />
      )}
      {cfg.filterType === 'date_range' && (
        <DateRangeFilter value={currentValue as [string, string]} onChange={setValue} />
      )}
      {cfg.filterType === 'text_entry' && (
        <TextEntryFilter value={currentValue as string} onChange={setValue} matchMode={cfg.matchMode} />
      )}
      {cfg.filterType === 'range_slider' && (
        <RangeSliderFilter value={currentValue as [number, number]} onChange={setValue} />
      )}
    </div>
  );
}

// ── Multi-value ───────────────────────────────────────────────────────────────

function MultiValueFilter({ value, options, onChange, allowAll }: {
  value: string[] | null;
  options: string[];
  onChange: (v: FilterValue) => void;
  allowAll?: boolean;
}) {
  const selected = value ?? [];
  function toggle(opt: string) {
    if (selected.includes(opt)) {
      onChange(selected.filter((s) => s !== opt));
    } else {
      onChange([...selected, opt]);
    }
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, overflowY: 'auto', maxHeight: 80 }}>
      {allowAll && (
        <button
          onClick={() => onChange(null)}
          style={{
            fontSize: '0.7rem',
            padding: '2px 7px',
            borderRadius: 10,
            border: '1px solid',
            borderColor: !selected.length ? 'var(--color-primary)' : 'var(--color-border)',
            background: !selected.length ? 'var(--color-primary-bg)' : 'var(--color-surface)',
            color: !selected.length ? 'var(--color-primary)' : 'var(--color-text-muted)',
            cursor: 'pointer',
          }}
        >
          All
        </button>
      )}
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => toggle(opt)}
          style={{
            fontSize: '0.7rem',
            padding: '2px 7px',
            borderRadius: 10,
            border: '1px solid',
            borderColor: selected.includes(opt) ? 'var(--color-primary)' : 'var(--color-border)',
            background: selected.includes(opt) ? 'var(--color-primary-bg)' : 'var(--color-surface)',
            color: selected.includes(opt) ? 'var(--color-primary)' : 'var(--color-text)',
            cursor: 'pointer',
          }}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

// ── Single value ──────────────────────────────────────────────────────────────

function SingleValueFilter({ value, options, onChange, allowAll }: {
  value: string | null;
  options: string[];
  onChange: (v: FilterValue) => void;
  allowAll?: boolean;
}) {
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
      style={{
        width: '100%',
        padding: '4px 6px',
        fontSize: '0.77rem',
        border: '1px solid var(--color-border)',
        borderRadius: 4,
        background: 'var(--color-surface)',
        color: 'var(--color-text)',
      }}
    >
      {allowAll && <option value="">All</option>}
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

// ── Date picker ───────────────────────────────────────────────────────────────

function DatePickerFilter({ value, onChange }: {
  value: string | null;
  onChange: (v: FilterValue) => void;
}) {
  return (
    <input
      type="date"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
      style={{
        padding: '4px 6px',
        fontSize: '0.77rem',
        border: '1px solid var(--color-border)',
        borderRadius: 4,
        background: 'var(--color-surface)',
        color: 'var(--color-text)',
        width: '100%',
      }}
    />
  );
}

// ── Date range ────────────────────────────────────────────────────────────────

const DATE_PRESETS = [
  { label: 'Last 7 days', value: '7d' },
  { label: 'Last 30 days', value: '30d' },
  { label: 'Last 90 days', value: '90d' },
  { label: 'This year', value: 'ytd' },
];

function DateRangeFilter({ value, onChange }: {
  value: [string, string] | null;
  onChange: (v: FilterValue) => void;
}) {
  const [start, end] = value ?? ['', ''];
  const [preset, setPreset] = useState('');

  function applyPreset(p: string) {
    setPreset(p);
    const now = new Date();
    const fmt = (d: Date) => d.toISOString().split('T')[0];
    const days = p === '7d' ? 7 : p === '30d' ? 30 : p === '90d' ? 90 : 0;
    if (days) {
      const from = new Date(now);
      from.setDate(from.getDate() - days);
      onChange([fmt(from), fmt(now)]);
    } else if (p === 'ytd') {
      onChange([`${now.getFullYear()}-01-01`, fmt(now)]);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', gap: 4 }}>
        <input type="date" value={start} onChange={(e) => onChange([e.target.value, end])}
          style={{ flex: 1, padding: '3px 5px', fontSize: '0.72rem', border: '1px solid var(--color-border)', borderRadius: 4, background: 'var(--color-surface)', color: 'var(--color-text)' }} />
        <span style={{ fontSize: '0.72rem', alignSelf: 'center', color: 'var(--color-text-muted)' }}>→</span>
        <input type="date" value={end} onChange={(e) => onChange([start, e.target.value])}
          style={{ flex: 1, padding: '3px 5px', fontSize: '0.72rem', border: '1px solid var(--color-border)', borderRadius: 4, background: 'var(--color-surface)', color: 'var(--color-text)' }} />
      </div>
      <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        {DATE_PRESETS.map((p) => (
          <button
            key={p.value}
            onClick={() => applyPreset(p.value)}
            style={{
              fontSize: '0.65rem',
              padding: '2px 6px',
              borderRadius: 10,
              border: '1px solid var(--color-border)',
              background: preset === p.value ? 'var(--color-primary-bg)' : 'var(--color-surface)',
              color: preset === p.value ? 'var(--color-primary)' : 'var(--color-text-muted)',
              cursor: 'pointer',
            }}
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Text entry ────────────────────────────────────────────────────────────────

function TextEntryFilter({ value, onChange, matchMode }: {
  value: string | null;
  onChange: (v: FilterValue) => void;
  matchMode?: string;
}) {
  return (
    <input
      type="text"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
      placeholder={matchMode === 'exact' ? 'Exact match…' : matchMode === 'starts_with' ? 'Starts with…' : 'Contains…'}
      style={{
        width: '100%',
        padding: '4px 6px',
        fontSize: '0.77rem',
        border: '1px solid var(--color-border)',
        borderRadius: 4,
        background: 'var(--color-surface)',
        color: 'var(--color-text)',
      }}
    />
  );
}

// ── Range slider ──────────────────────────────────────────────────────────────

function RangeSliderFilter({ value, onChange }: {
  value: [number, number] | null;
  onChange: (v: FilterValue) => void;
}) {
  const [min, setMin] = useState(value?.[0] ?? 0);
  const [max, setMax] = useState(value?.[1] ?? 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
        <span>{min}</span>
        <span>{max}</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={min}
        onChange={(e) => { const v = Number(e.target.value); setMin(v); onChange([v, max]); }}
        style={{ width: '100%' }}
      />
      <input
        type="range"
        min={0}
        max={100}
        value={max}
        onChange={(e) => { const v = Number(e.target.value); setMax(v); onChange([min, v]); }}
        style={{ width: '100%' }}
      />
    </div>
  );
}

