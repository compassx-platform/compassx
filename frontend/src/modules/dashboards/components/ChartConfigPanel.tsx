/**
 * ChartConfigPanel — right-side config panel when widget selected.
 * Reference: visualization-config-48682eb308e0636dc74e5bfb208907b8.png
 *            x-y-axis-kebabs-74f2dacc0093a0a0981befb2fe0988a9.png
 */

import { useMemo, useState } from 'react';
import {
  X, BarChart2, LineChart, PieChart, ScatterChart, Table2, Hash,
  MoreVertical, Plus, ArrowUpDown
} from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import type { ChartType, Widget } from '@/types/dashboard';
import DashboardSidePanel from './DashboardSidePanel';

const CHART_TYPES: { type: ChartType; label: string }[] = [
  { type: 'bar', label: 'Bar' },
  { type: 'line', label: 'Line' },
  { type: 'area', label: 'Area' },
  { type: 'scatter', label: 'Scatter' },
  { type: 'pie', label: 'Pie' },
  { type: 'counter', label: 'Counter' },
  { type: 'table', label: 'Table' },
  { type: 'pivot', label: 'Pivot' },
  { type: 'heatmap', label: 'Heatmap' },
  { type: 'histogram', label: 'Histogram' },
  { type: 'box', label: 'Box' },
  { type: 'funnel', label: 'Funnel' },
  { type: 'waterfall', label: 'Waterfall' },
  { type: 'combo', label: 'Combo' },
  { type: 'bubble', label: 'Bubble' },
  { type: 'sankey', label: 'Sankey' },
  { type: 'choropleth', label: 'Map' },
  { type: 'point_map', label: 'Point Map' },
  { type: 'cohort', label: 'Cohort' },
];

function CollapsibleSection({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderBottom: '1px solid var(--color-border)' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          padding: '8px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '0.76rem',
          fontWeight: 600,
          color: 'var(--color-text)',
          textAlign: 'left',
        }}
      >
        {title}
        <span style={{ opacity: 0.4, fontSize: '0.65rem' }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && <div style={{ padding: '0 14px 10px' }}>{children}</div>}
    </div>
  );
}

function SectionRow({
  title,
  onPlus,
  plusDisabled = false,
  onKebab,
  children,
  actionText
}: {
  title: string;
  onPlus?: () => void;
  plusDisabled?: boolean;
  onKebab?: () => void;
  children: React.ReactNode;
  actionText?: string;
}) {
  return (
    <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1a1a1a' }}>{title}</span>
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
                padding: 0
              }}
            >
              {actionText}
            </button>
          )}
          {onKebab && (
            <button onClick={onKebab} style={{ background: 'none', border: 'none', cursor: 'pointer', opacity: 0.6, display: 'flex', alignItems: 'center', padding: 0, color: '#334155' }}>
              <MoreVertical size={13} />
            </button>
          )}
          {onPlus && !actionText && (
            <button
              onClick={plusDisabled ? undefined : onPlus}
              disabled={plusDisabled}
              title={plusDisabled ? "Multiple series not supported for this chart type" : "Add metric series"}
              style={{
                background: 'none',
                border: 'none',
                cursor: plusDisabled ? 'not-allowed' : 'pointer',
                opacity: plusDisabled ? 0.3 : 0.75,
                display: 'flex',
                alignItems: 'center',
                padding: 0,
                color: plusDisabled ? '#94a3b8' : '#334155'
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

function Select({ value, onChange, options, placeholder }: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        width: '100%',
        padding: '5px 8px',
        fontSize: '0.77rem',
        border: '1px solid var(--color-border)',
        borderRadius: 4,
        background: 'var(--color-surface)',
        color: 'var(--color-text)',
      }}
    >
      <option value="">{placeholder || '— select field —'}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 3 }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function FieldPill({
  name,
  type,
  transform,
  displayName,
  onClick,
  onRemove,
}: {
  name: string;
  type: string;
  transform?: string;
  displayName?: string;
  onClick?: () => void;
  onRemove: () => void;
}) {
  const isNumeric = ['integer', 'float', 'number', 'double', 'decimal'].includes((type || '').toLowerCase());
  const displayLabel = displayName || (transform && transform !== 'NONE' ? `${transform}(${name})` : name);

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
      title={onClick ? "Click to configure axis options" : undefined}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        <span style={{
          fontSize: '0.6rem',
          fontWeight: 'bold',
          color: '#475569',
          background: '#e2e8f0',
          padding: '1px 4px',
          borderRadius: 3,
          letterSpacing: '0.3px',
        }}>
          {isNumeric ? '1.2' : 'Abc'}
        </span>
        <span style={{ fontSize: '0.77rem', fontWeight: 500, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {displayLabel}
        </span>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(); }}
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

function AxisConfigPopover({
  fieldName,
  fieldType,
  axisConfig = {},
  seriesTitle,
  onUpdateSeriesTitle,
  onUpdate,
  onClose,
}: {
  fieldName: string;
  fieldType: string;
  axisConfig?: Record<string, any>;
  seriesTitle?: string;
  onUpdateSeriesTitle?: (title: string) => void;
  onUpdate: (config: Record<string, any>) => void;
  onClose: () => void;
}) {
  const isNumeric = ['integer', 'float', 'number', 'double', 'decimal'].includes((fieldType || '').toLowerCase());
  const scaleType = axisConfig.scaleType ?? (isNumeric ? 'continuous' : 'categorical');
  const transform = axisConfig.transform ?? 'NONE';
  const defaultDisplayName = transform !== 'NONE' ? `${transform}(${fieldName})` : fieldName;
  const displayName = seriesTitle ?? axisConfig.displayName ?? axisConfig.title ?? defaultDisplayName;
  const errorBar = axisConfig.errorBar ?? false;

  const TRANSFORMS = [
    'NONE', 'SUM', 'AVG', 'MEDIAN', 'MIN',
    'MAX', 'COUNT', 'COUNT DISTINCT', 'VAR', 'STD',
    'PERCENTILE', 'FIRST', 'LAST'
  ];

  return (
    <>
      {/* Click outside overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 998,
        }}
      />

      {/* Popover container */}
      <div
        style={{
          position: 'absolute',
          top: '100%',
          left: 10,
          right: 10,
          marginTop: 4,
          background: '#ffffff',
          borderRadius: 8,
          border: '1px solid #cbd5e1',
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.15), 0 8px 10px -6px rgba(0,0,0,0.1)',
          padding: 12,
          zIndex: 999,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          color: '#1e293b',
          fontSize: '0.78rem',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Field Name Display */}
        <div>
          <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
            Field
          </label>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: '#f8fafc',
            border: '1px solid #cbd5e1',
            borderRadius: 6,
            padding: '5px 8px',
            fontWeight: 500,
            color: '#0f172a',
          }}>
            <span style={{
              fontSize: '0.62rem',
              fontWeight: 700,
              color: '#475569',
              background: '#e2e8f0',
              padding: '1px 4px',
              borderRadius: 3,
            }}>
              {isNumeric ? '1.2' : 'Abc'}
            </span>
            <span>{fieldName}</span>
          </div>
        </div>

        {/* Scale Type Segmented Toggle */}
        <div>
          <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
            Scale type
          </label>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              onClick={() => onUpdate({ scaleType: 'continuous' })}
              style={{
                flex: 1,
                padding: '5px 8px',
                fontSize: '0.74rem',
                fontWeight: scaleType === 'continuous' ? 600 : 400,
                color: scaleType === 'continuous' ? '#0052cc' : '#475569',
                background: scaleType === 'continuous' ? '#e7f0ff' : '#ffffff',
                border: `1px solid ${scaleType === 'continuous' ? '#0052cc' : '#cbd5e1'}`,
                borderRadius: 6,
                cursor: 'pointer',
                transition: 'all 0.12s ease',
              }}
            >
              Continuous
            </button>
            <button
              type="button"
              onClick={() => onUpdate({ scaleType: 'categorical' })}
              style={{
                flex: 1,
                padding: '5px 8px',
                fontSize: '0.74rem',
                fontWeight: scaleType === 'categorical' ? 600 : 400,
                color: scaleType === 'categorical' ? '#0052cc' : '#475569',
                background: scaleType === 'categorical' ? '#e7f0ff' : '#ffffff',
                border: `1px solid ${scaleType === 'categorical' ? '#0052cc' : '#cbd5e1'}`,
                borderRadius: 6,
                cursor: 'pointer',
                transition: 'all 0.12s ease',
              }}
            >
              Categorical
            </button>
          </div>
        </div>

        {/* Transform / Aggregation Grid */}
        <div>
          <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 6 }}>
            Transform
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {TRANSFORMS.map((tf) => {
              const active = (transform || 'NONE').toUpperCase() === tf;
              return (
                <button
                  key={tf}
                  type="button"
                  onClick={() => {
                    const newLabel = tf !== 'NONE' ? `${tf}(${fieldName})` : fieldName;
                    onUpdate({ transform: tf });
                    if (onUpdateSeriesTitle) onUpdateSeriesTitle(newLabel);
                    else onUpdate({ displayName: newLabel, title: newLabel });
                  }}
                  style={{
                    padding: '3px 7px',
                    fontSize: '0.68rem',
                    fontWeight: active ? 700 : 500,
                    color: active ? '#0052cc' : '#475569',
                    background: active ? '#e7f0ff' : '#ffffff',
                    border: `1px solid ${active ? '#0052cc' : '#cbd5e1'}`,
                    borderRadius: 4,
                    cursor: 'pointer',
                    transition: 'all 0.12s ease',
                  }}
                >
                  {tf === 'NONE' ? 'None' : tf}
                </button>
              );
            })}
          </div>
        </div>

        {/* Display Name Input */}
        <div>
          <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
            Display name
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => {
              const val = e.target.value;
              if (onUpdateSeriesTitle) onUpdateSeriesTitle(val);
              else onUpdate({ displayName: val, title: val });
            }}
            placeholder="Custom axis label"
            style={{
              width: '100%',
              padding: '5px 8px',
              fontSize: '0.76rem',
              border: '1px solid #cbd5e1',
              borderRadius: 6,
              background: '#ffffff',
              color: '#0f172a',
              outline: 'none',
            }}
          />
        </div>

        {/* Error Bar Switch */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 2 }}>
          <span style={{ fontSize: '0.74rem', fontWeight: 500, color: '#334155' }}>Error bar</span>
          <label style={{ position: 'relative', display: 'inline-block', width: 32, height: 18, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={errorBar}
              onChange={(e) => onUpdate({ errorBar: e.target.checked })}
              style={{ opacity: 0, width: 0, height: 0 }}
            />
            <span style={{
              position: 'absolute',
              inset: 0,
              backgroundColor: errorBar ? '#0052cc' : '#cbd5e1',
              borderRadius: 20,
              transition: '0.2s',
            }}>
              <span style={{
                position: 'absolute',
                content: '""',
                height: 14,
                width: 14,
                left: 2,
                bottom: 2,
                backgroundColor: '#ffffff',
                borderRadius: '50%',
                transition: '0.2s',
                transform: errorBar ? 'translateX(14px)' : 'none',
              }} />
            </span>
          </label>
        </div>
      </div>
    </>
  );
}

function ColumnPickerPopover({
  allColumns,
  selectedColumns,
  onChange,
  onClose,
}: {
  allColumns: Array<{ value: string; label: string; type?: string }>;
  selectedColumns: string[];
  onChange: (cols: string[]) => void;
  onClose: () => void;
}) {
  const [filterText, setFilterText] = useState('');

  const filtered = useMemo(() => {
    if (!filterText.trim()) return allColumns;
    const term = filterText.toLowerCase();
    return allColumns.filter((c) => c.label.toLowerCase().includes(term));
  }, [allColumns, filterText]);

  const allVisibleSelected = filtered.length > 0 && filtered.every((c) => selectedColumns.includes(c.value));

  function toggleColumn(val: string) {
    if (selectedColumns.includes(val)) {
      onChange(selectedColumns.filter((c) => c !== val));
    } else {
      onChange([...selectedColumns, val]);
    }
  }

  function handleToggleAllVisible() {
    if (allVisibleSelected) {
      const visibleVals = new Set(filtered.map((c) => c.value));
      onChange(selectedColumns.filter((c) => !visibleVals.has(c)));
    } else {
      const visibleVals = filtered.map((c) => c.value);
      const combined = Array.from(new Set([...selectedColumns, ...visibleVals]));
      onChange(combined);
    }
  }

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 998 }} />
      <div
        style={{
          position: 'absolute',
          top: '100%',
          left: 10,
          right: 10,
          marginTop: 4,
          background: '#ffffff',
          borderRadius: 8,
          border: '1px solid #cbd5e1',
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.15), 0 8px 10px -6px rgba(0,0,0,0.1)',
          padding: 12,
          zIndex: 999,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          color: '#1e293b',
          fontSize: '0.78rem',
          maxHeight: 340,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9', paddingBottom: 6 }}>
          <span style={{ fontWeight: 700, fontSize: '0.8rem', color: '#0f172a' }}>Column Manager</span>
          <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 500 }}>
            {selectedColumns.length} / {allColumns.length} selected
          </span>
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Search columns..."
            style={{
              width: '100%',
              padding: '5px 8px',
              fontSize: '0.76rem',
              border: '1px solid #cbd5e1',
              borderRadius: 6,
              outline: 'none',
            }}
          />
        </div>

        {/* Bulk Actions Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem' }}>
          <button
            type="button"
            onClick={handleToggleAllVisible}
            style={{
              background: 'none',
              border: 'none',
              color: '#0052cc',
              cursor: 'pointer',
              fontWeight: 600,
              padding: 0,
            }}
          >
            {allVisibleSelected ? 'Deselect visible' : 'Select all visible'}
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => onChange(allColumns.map((c) => c.value))}
              style={{ background: 'none', border: 'none', color: '#0052cc', cursor: 'pointer', fontWeight: 500, padding: 0 }}
            >
              Select All ({allColumns.length})
            </button>
            <span style={{ color: '#cbd5e1' }}>|</span>
            <button
              type="button"
              onClick={() => onChange([])}
              style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontWeight: 500, padding: 0 }}
            >
              Clear All
            </button>
          </div>
        </div>

        {/* Checkbox List */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, paddingRight: 4 }}>
          {filtered.length > 0 ? (
            filtered.map((col) => {
              const isChecked = selectedColumns.includes(col.value);
              return (
                <label
                  key={col.value}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '4px 6px',
                    borderRadius: 4,
                    background: isChecked ? '#eff6ff' : 'transparent',
                    cursor: 'pointer',
                    fontSize: '0.74rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleColumn(col.value)}
                      style={{ accentColor: '#0052cc' }}
                    />
                    <span style={{ fontWeight: isChecked ? 600 : 400, color: isChecked ? '#1e40af' : '#334155' }}>
                      {col.label}
                    </span>
                  </div>
                  {col.type && (
                    <span style={{ fontSize: '0.62rem', color: '#64748b', background: '#e2e8f0', padding: '1px 4px', borderRadius: 3 }}>
                      {col.type}
                    </span>
                  )}
                </label>
              );
            })
          ) : (
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textAlign: 'center', padding: 12 }}>
              No matching columns found
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function getChartIcon(type: ChartType) {
  const size = 13;
  switch (type) {
    case 'bar':
    case 'histogram':
    case 'waterfall':
    case 'combo':
      return <BarChart2 size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'line':
    case 'area':
      return <LineChart size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'pie':
    case 'funnel':
      return <PieChart size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'scatter':
    case 'bubble':
      return <ScatterChart size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'table':
    case 'pivot':
      return <Table2 size={size} style={{ color: 'var(--color-primary)' }} />;
    default:
      return <BarChart2 size={size} style={{ color: 'var(--color-primary)' }} />;
  }
}

function lintHtmlWidget(content: string): string[] {
  const findings: string[] = [];
  if (!content) return findings;
  if (/fetch\(|XMLHttpRequest|WebSocket/i.test(content)) {
    findings.push("Network access attempts detected (fetch, XMLHttpRequest, WebSocket). Direct network requests are blocked by Content Security Policy.");
  }
  if (/window\.top|window\.parent|parent\.location|parent\.document/i.test(content)) {
    findings.push("Attempts to access parent window context detected (window.top, window.parent, etc.). Access is restricted by iframe sandbox.");
  }
  if (/document\.cookie|localStorage|sessionStorage/i.test(content)) {
    findings.push("Storage access detected (document.cookie, localStorage, sessionStorage). Sandboxed iframe runs with unique origin and cannot access parent store.");
  }
  if (/eval\(|new Function\(/i.test(content)) {
    findings.push("Dynamic evaluation detected (eval, new Function). Use with caution.");
  }
  return findings;
}

const PRESET_COLORS = [
  '#1B6EF3', // Royal Blue
  '#10B981', // Emerald Green
  '#8B5CF6', // Vivid Purple
  '#F59E0B', // Amber
  '#EF4444', // Red
  '#06B6D4', // Cyan
  '#EC4899', // Pink
  '#64748B', // Slate Gray
  '#F97316', // Orange
  '#14B8A6', // Teal
];

function SeriesColorPicker({
  yFields,
  seriesColors,
  onChange,
}: {
  yFields: string[];
  seriesColors?: Array<{ field: string; color: string }>;
  onChange: (updated: Array<{ field: string; color: string }>) => void;
}) {
  const [activePickerField, setActivePickerField] = useState<string | null>(null);

  const fieldsToRender = yFields.length > 0 ? yFields : ['value'];

  function getColorForField(field: string, index: number): string {
    const found = seriesColors?.find((sc) => sc.field === field);
    if (found?.color) return found.color;
    return PRESET_COLORS[index % PRESET_COLORS.length];
  }

  function handleSelectColor(field: string, color: string) {
    const current = seriesColors ? [...seriesColors] : [];
    const idx = current.findIndex((sc) => sc.field === field);
    if (idx >= 0) {
      current[idx] = { field, color };
    } else {
      current.push({ field, color });
    }
    onChange(current);
    setActivePickerField(null);
  }

  return (
    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6, width: '100%' }}>
      <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569' }}>Series Color</span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {fieldsToRender.map((yf, i) => {
          const currentColor = getColorForField(yf, i);
          const isOpen = activePickerField === yf;
          return (
            <div key={yf} style={{ position: 'relative' }}>
              <div
                onClick={() => setActivePickerField(isOpen ? null : yf)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  background: '#f8fafc',
                  border: '1px solid #cbd5e1',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: 3,
                      backgroundColor: currentColor,
                      border: '1px solid rgba(0,0,0,0.15)',
                    }}
                  />
                  <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#1e293b' }}>{yf}</span>
                </div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'monospace' }}>{currentColor}</span>
              </div>

              {isOpen && (
                <>
                  <div
                    style={{ position: 'fixed', inset: 0, zIndex: 998 }}
                    onClick={() => setActivePickerField(null)}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      top: 30,
                      left: 0,
                      zIndex: 999,
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: 6,
                      boxShadow: '0 6px 20px rgba(0,0,0,0.15)',
                      padding: 10,
                      width: 210,
                    }}
                  >
                    <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', marginBottom: 8 }}>
                      Select Color
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 8 }}>
                      {PRESET_COLORS.map((c) => (
                        <div
                          key={c}
                          onClick={() => handleSelectColor(yf, c)}
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 4,
                            backgroundColor: c,
                            cursor: 'pointer',
                            border: currentColor === c ? '2px solid #0f172a' : '1px solid rgba(0,0,0,0.15)',
                            transform: currentColor === c ? 'scale(1.1)' : 'none',
                            transition: 'all 0.1s ease',
                          }}
                        />
                      ))}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, borderTop: '1px solid #f1f5f9', paddingTop: 6 }}>
                      <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Custom:</span>
                      <input
                        type="color"
                        value={currentColor}
                        onChange={(e) => handleSelectColor(yf, e.target.value)}
                        style={{ width: 26, height: 24, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
                      />
                      <input
                        type="text"
                        value={currentColor}
                        onChange={(e) => handleSelectColor(yf, e.target.value)}
                        style={{
                          width: 70,
                          fontSize: '0.72rem',
                          fontFamily: 'monospace',
                          padding: '2px 4px',
                          border: '1px solid #cbd5e1',
                          borderRadius: 3,
                        }}
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const TABLE_TITLE_ROW_PRESETS = [
  { label: 'Default Light Slate', color: '#f1f5f9' },
  { label: 'Neutral Gray', color: '#e2e8f0' },
  { label: 'Medium Slate', color: '#94a3b8' },
  { label: 'Dark Slate', color: '#334155' },
  { label: 'Deep Charcoal', color: '#0f172a' },
  { label: 'CompassX Blue', color: '#0052cc' },
  { label: 'Navy Blue', color: '#1e40af' },
  { label: 'Sky Blue Pastel', color: '#dbeafe' },
  { label: 'Teal Pastel', color: '#ccfbf1' },
  { label: 'Deep Teal', color: '#0f766e' },
  { label: 'Emerald Pastel', color: '#d1fae5' },
  { label: 'Forest Green', color: '#166534' },
  { label: 'Indigo Pastel', color: '#e0e7ff' },
  { label: 'Deep Indigo', color: '#4338ca' },
  { label: 'Purple Pastel', color: '#f3e8ff' },
  { label: 'Deep Purple', color: '#7e22ce' },
  { label: 'Amber Pastel', color: '#fef3c7' },
  { label: 'Deep Amber', color: '#b45309' },
  { label: 'Rose Pastel', color: '#ffe4e6' },
  { label: 'Crimson', color: '#be123c' },
];

function TableTitleRowColorPicker({
  titleRowBg,
  onChange,
}: {
  titleRowBg?: string;
  onChange: (bg?: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const currentBg = titleRowBg || '#f1f5f9';
  const isDefault = !titleRowBg || titleRowBg.toLowerCase() === '#f1f5f9';

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569' }}>Title Row Background</span>
        {!isDefault && (
          <button
            type="button"
            onClick={() => onChange(undefined)}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              fontSize: '0.68rem',
              color: '#0052cc',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Reset to default
          </button>
        )}
      </div>

      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '5px 8px',
          background: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: 4,
          cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 18,
              height: 18,
              borderRadius: 3,
              backgroundColor: currentBg,
              border: '1px solid rgba(0,0,0,0.15)',
              boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.4)',
            }}
          />
          <span style={{ fontSize: '0.75rem', color: '#1e293b', fontWeight: 500 }}>
            {isDefault ? 'Default (#f1f5f9)' : currentBg}
          </span>
        </div>
        <span style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'monospace' }}>
          {currentBg}
        </span>
      </div>

      {isOpen && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 998 }}
            onClick={() => setIsOpen(false)}
          />
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              marginTop: 4,
              zIndex: 999,
              background: '#ffffff',
              border: '1px solid #cbd5e1',
              borderRadius: 6,
              boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
              padding: 10,
              width: 240,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Preset Backgrounds</span>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 0 }}
              >
                <X size={13} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 10 }}>
              {TABLE_TITLE_ROW_PRESETS.map((preset) => {
                const isSelected = currentBg.toLowerCase() === preset.color.toLowerCase();
                return (
                  <div
                    key={preset.color}
                    onClick={() => {
                      onChange(preset.color === '#f1f5f9' ? undefined : preset.color);
                    }}
                    title={`${preset.label} (${preset.color})`}
                    style={{
                      width: 32,
                      height: 28,
                      borderRadius: 4,
                      backgroundColor: preset.color,
                      cursor: 'pointer',
                      border: isSelected ? '2px solid #0052cc' : '1px solid rgba(0,0,0,0.15)',
                      transform: isSelected ? 'scale(1.08)' : 'none',
                      transition: 'all 0.1s ease',
                      boxShadow: isSelected ? '0 0 0 2px rgba(0,82,204,0.2)' : undefined,
                    }}
                  />
                );
              })}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
              <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 500 }}>Custom:</span>
              <input
                type="color"
                value={currentBg.startsWith('#') && currentBg.length === 7 ? currentBg : '#f1f5f9'}
                onChange={(e) => onChange(e.target.value)}
                style={{ width: 26, height: 24, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
              />
              <input
                type="text"
                value={titleRowBg ?? ''}
                placeholder="#f1f5f9"
                onChange={(e) => onChange(e.target.value || undefined)}
                style={{
                  flex: 1,
                  fontSize: '0.72rem',
                  fontFamily: 'monospace',
                  padding: '3px 6px',
                  border: '1px solid #cbd5e1',
                  borderRadius: 4,
                  outline: 'none',
                }}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function AxisSettingsPopover({
  axisType,
  axisConfig = {},
  fieldOptions,
  onUpdate,
  onClose,
}: {
  axisType: 'xAxis' | 'yAxis' | 'y2Axis';
  axisConfig?: Record<string, any>;
  fieldOptions: { value: string; label: string }[];
  onUpdate: (updated: Record<string, any>) => void;
  onClose: () => void;
}) {
  return (
    <>
      <div style={{ position: 'fixed', inset: 0, zIndex: 998 }} onClick={onClose} />
      <div
        style={{
          position: 'absolute',
          top: '100%',
          right: 0,
          marginTop: 4,
          background: '#ffffff',
          borderRadius: 8,
          border: '1px solid #cbd5e1',
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.15), 0 8px 10px -6px rgba(0,0,0,0.1)',
          padding: 12,
          zIndex: 999,
          width: 240,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          color: '#1e293b',
          fontSize: '0.78rem',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9', paddingBottom: 6 }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#0f172a' }}>
            {axisType === 'xAxis' ? 'X Axis Settings' : axisType === 'y2Axis' ? 'Y2 Axis Settings' : 'Y Axis Settings'}
          </span>
          <button className="btn-icon" onClick={onClose} style={{ padding: 2 }}><X size={13} /></button>
        </div>

        {/* Title */}
        <FieldRow label="Title">
          <input
            value={axisConfig.title ?? ''}
            onChange={(e) => onUpdate({ title: e.target.value })}
            placeholder="Custom axis title..."
            style={{ width: '100%', padding: '4px 6px', fontSize: '0.76rem', border: '1px solid #cbd5e1', borderRadius: 4, outline: 'none' }}
          />
        </FieldRow>

        {/* Min & Max Range */}
        <div style={{ display: 'flex', gap: 6 }}>
          <FieldRow label="Min">
            <input
              type="number"
              value={axisConfig.min ?? ''}
              onChange={(e) => onUpdate({ min: e.target.value !== '' ? Number(e.target.value) : undefined })}
              placeholder="Auto"
              style={{ width: '100%', padding: '4px 6px', fontSize: '0.76rem', border: '1px solid #cbd5e1', borderRadius: 4 }}
            />
          </FieldRow>
          <FieldRow label="Max">
            <input
              type="number"
              value={axisConfig.max ?? ''}
              onChange={(e) => onUpdate({ max: e.target.value !== '' ? Number(e.target.value) : undefined })}
              placeholder="Auto"
              style={{ width: '100%', padding: '4px 6px', fontSize: '0.76rem', border: '1px solid #cbd5e1', borderRadius: 4 }}
            />
          </FieldRow>
        </div>

        {/* Max Ticks */}
        <FieldRow label="Max ticks">
          <input
            type="number"
            min={2}
            max={50}
            value={axisConfig.tickCount ?? ''}
            onChange={(e) => onUpdate({ tickCount: e.target.value !== '' ? Number(e.target.value) : undefined })}
            placeholder="Auto (e.g. 5, 10, 20)"
            style={{ width: '100%', padding: '4px 6px', fontSize: '0.76rem', border: '1px solid #cbd5e1', borderRadius: 4, outline: 'none' }}
          />
        </FieldRow>

        {/* Label Angle */}
        <FieldRow label="Label angle">
          <Select
            value={axisConfig.labelAngle !== undefined ? String(axisConfig.labelAngle) : 'auto'}
            onChange={(v) => onUpdate({ labelAngle: v !== 'auto' ? Number(v) : undefined })}
            options={[
              { value: 'auto', label: 'Auto' },
              { value: '0', label: 'Horizontal (0°)' },
              { value: '-45', label: 'Slanted (-45°)' },
              { value: '45', label: 'Slanted (45°)' },
              { value: '-90', label: 'Vertical (-90°)' },
            ]}
          />
        </FieldRow>

        {/* Sort Controls */}
        <FieldRow label="Sort by">
          <Select
            value={axisConfig.sortByField ?? ''}
            onChange={(v) => onUpdate({ sortByField: v })}
            options={fieldOptions}
            placeholder="Default (X-axis order)"
          />
        </FieldRow>
        <FieldRow label="Sort order">
          <div style={{ display: 'flex', gap: 6, width: '100%' }}>
            <button
              type="button"
              onClick={() => onUpdate({ sortByOrder: axisConfig.sortByOrder === 'asc' ? undefined : 'asc' })}
              style={{
                flex: 1,
                padding: '4px 6px',
                fontSize: '0.72rem',
                fontWeight: 500,
                borderRadius: 4,
                border: '1px solid',
                borderColor: axisConfig.sortByOrder === 'asc' ? '#0052cc' : '#cbd5e1',
                background: axisConfig.sortByOrder === 'asc' ? '#eff6ff' : '#f8fafc',
                color: axisConfig.sortByOrder === 'asc' ? '#0052cc' : '#475569',
                cursor: 'pointer',
              }}
            >
              ASC (1-9)
            </button>
            <button
              type="button"
              onClick={() => onUpdate({ sortByOrder: axisConfig.sortByOrder === 'desc' ? undefined : 'desc' })}
              style={{
                flex: 1,
                padding: '4px 6px',
                fontSize: '0.72rem',
                fontWeight: 500,
                borderRadius: 4,
                border: '1px solid',
                borderColor: axisConfig.sortByOrder === 'desc' ? '#0052cc' : '#cbd5e1',
                background: axisConfig.sortByOrder === 'desc' ? '#eff6ff' : '#f8fafc',
                color: axisConfig.sortByOrder === 'desc' ? '#0052cc' : '#475569',
                cursor: 'pointer',
              }}
            >
              DESC (9-1)
            </button>
          </div>
        </FieldRow>

        {/* Checkbox Options */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
          <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={axisConfig.reversed ?? false}
              onChange={(e) => onUpdate({ reversed: e.target.checked })}
              style={{ accentColor: '#0052cc' }}
            />
            Reverse axis direction
          </label>
          <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={axisConfig.logScale ?? false}
              onChange={(e) => onUpdate({ logScale: e.target.checked })}
              style={{ accentColor: '#0052cc' }}
            />
            Logarithmic scale
          </label>
        </div>
      </div>
    </>
  );
}

interface Props {
  onClose: () => void;
}


export default function ChartConfigPanel({ onClose }: Props) {
  const { activeDashboard, selectedWidgetId, updateWidget, cloneWidget, deleteWidget } = useDashboardStore();

  const [showTitleInput, setShowTitleInput] = useState(true);
  const [showDescInput, setShowDescInput] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showTooltipSelect, setShowTooltipSelect] = useState(false);
  const [showYFieldSelect, setShowYFieldSelect] = useState(false);
  const [showY2FieldSelect, setShowY2FieldSelect] = useState(false);
  const [showWidgetMenu, setShowWidgetMenu] = useState(false);
  const [openAxisSettings, setOpenAxisSettings] = useState<'xAxis' | 'yAxis' | 'y2Axis' | null>(null);
  const [openSeriesPopover, setOpenSeriesPopover] = useState<string | null>(null);
  const [showColumnPicker, setShowColumnPicker] = useState(false);

  const widget: Widget | undefined = activeDashboard?.widgets.find((w) => w.id === selectedWidgetId);
  if (!widget) {
    return (
      <DashboardSidePanel style={{ alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', textAlign: 'center' }}>
          Select a widget to configure
        </span>
      </DashboardSidePanel>
    );
  }

  const datasetOptions = (activeDashboard?.datasets ?? []).map((d) => ({ value: d.id, label: d.name }));

  if (widget.widgetType === 'html') {
    return (
      <DashboardSidePanel>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1a1a1a' }}>HTML widget</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: 2 }}>Write HTML/CSS to render custom UI</div>
          </div>
          <button className="btn-icon" onClick={onClose}><X size={14} /></button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <FieldRow label="Title">
            <input
              value={widget.title ?? ''}
              onChange={(e) => updateWidget(widget.id, { title: e.target.value })}
              placeholder="Widget title"
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

          <FieldRow label="Dataset (optional)">
            <Select
              value={widget.htmlConfig?.datasetId ?? ''}
              onChange={(v) => updateWidget(widget.id, { htmlConfig: { ...(widget.htmlConfig ?? {}), datasetId: v || undefined } })}
              options={datasetOptions}
              placeholder="Bind a dataset for data-driven HTML"
            />
          </FieldRow>

          {widget.htmlConfig?.datasetId && (
            <FieldRow label="Dataset Alias">
              <input
                value={widget.htmlConfig?.alias ?? ''}
                onChange={(e) => updateWidget(widget.id, { htmlConfig: { ...(widget.htmlConfig ?? {}), alias: e.target.value } })}
                placeholder="Alias used in JS (e.g. kpiData)"
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

          <FieldRow label="HTML / CSS / JS">
            <textarea
              value={widget.content ?? ''}
              onChange={(e) => updateWidget(widget.id, { content: e.target.value })}
              placeholder={`<div style="padding:16px">\n  <h3>My custom widget</h3>\n  <p>Build any HTML layout here.</p>\n</div>`}
              style={{
                width: '100%',
                minHeight: 280,
                resize: 'vertical',
                padding: '8px 10px',
                fontSize: '0.75rem',
                lineHeight: 1.5,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                border: '1px solid var(--color-border)',
                borderRadius: 6,
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
              }}
            />
          </FieldRow>

          {/* Real-time Static Analysis / Lint Warnings */}
          {(() => {
            const findings = lintHtmlWidget(widget.content ?? '');
            if (findings.length === 0) return null;
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 10, background: 'var(--color-danger-bg)', border: '1px solid var(--color-border)', borderRadius: 6 }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--color-danger)' }}>Static Analysis Alerts</span>
                {findings.map((f, i) => (
                  <div key={i} style={{ fontSize: '0.7rem', color: 'var(--color-danger)', lineHeight: 1.4 }}>
                    ⚠️ {f}
                  </div>
                ))}
              </div>
            );
          })()}

          <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', lineHeight: 1.5, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, padding: 10 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Template tokens</div>
            <div>{'{{table}}'} inserts an auto-rendered data table.</div>
            <div>{'{{rowsJson}}'} inserts the dataset rows as JSON.</div>
            <div>{'{{columnsJson}}'} inserts the column list as JSON.</div>
            <div style={{ marginTop: 6 }}>JavaScript execution is enabled via sandboxed <code>platform</code> SDK.</div>
          </div>

        </div>
      </DashboardSidePanel>
    );
  }

  if (!widget.chartConfig) {
    return (
      <DashboardSidePanel style={{ alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', textAlign: 'center' }}>
          Select a widget to configure
        </span>
      </DashboardSidePanel>
    );
  }

  const cfg = widget.chartConfig;
  const isMultiSeriesAllowed = !['counter', 'pie', 'funnel', 'choropleth', 'point_map'].includes(cfg.chartType ?? 'bar');

  const dataset = activeDashboard?.datasets.find((d) => d.id === cfg.datasetId);
  const fieldOptions = (dataset?.schema ?? []).map((f) => ({ value: f.name, label: f.name }));

  function patch(p: Partial<typeof cfg>) {
    updateWidget(widget!.id, { chartConfig: { ...cfg, ...p } as typeof cfg });
  }

  function patchAxis(axis: 'xAxis' | 'yAxis' | 'y2Axis', p: Record<string, unknown>) {
    patch({ [axis]: { ...(cfg as any)[axis], ...p } } as any);
  }

  function getFieldType(fieldName: string): string {
    const field = dataset?.schema.find(f => f.name === fieldName);
    return field?.type || 'string';
  }

  function handleSwapAxes() {
    const x = cfg.xField;
    const y = cfg.yFields?.[0];
    patch({ xField: y, yFields: x ? [x] : [] });
  }

  const tooltipFields = cfg.tooltipFields ?? [];

  return (
    <DashboardSidePanel>
      {/* Scrollable Container */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>

        {/* Widget Header Section */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1a1a1a' }}>Widget</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }}>
              <button className="btn-icon" onClick={() => setShowWidgetMenu(!showWidgetMenu)} title="Widget actions">
                <MoreVertical size={13} />
              </button>
              {showWidgetMenu && (
                <>
                  <div style={{ position: 'fixed', inset: 0, zIndex: 998 }} onClick={() => setShowWidgetMenu(false)} />
                  <div
                    style={{
                      position: 'absolute',
                      top: 24,
                      right: 20,
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: 6,
                      boxShadow: '0 4px 14px rgba(0,0,0,0.15)',
                      zIndex: 999,
                      width: 150,
                      padding: '4px 0',
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: '6px 12px',
                        fontSize: '0.76rem',
                        textAlign: 'left',
                        cursor: 'pointer',
                        color: '#1e293b',
                      }}
                      onClick={() => {
                        setShowWidgetMenu(false);
                        cloneWidget(widget.id);
                      }}
                    >
                      📋 Duplicate widget
                    </button>
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: '6px 12px',
                        fontSize: '0.76rem',
                        textAlign: 'left',
                        cursor: 'pointer',
                        color: '#1e293b',
                      }}
                      onClick={() => {
                        setShowWidgetMenu(false);
                        if (widget.chartConfig) {
                          updateWidget(widget.id, {
                            chartConfig: {
                              chartType: widget.chartConfig.chartType,
                              datasetId: widget.chartConfig.datasetId,
                            },
                          });
                        }
                      }}
                    >
                      🔄 Reset config
                    </button>
                    <div style={{ height: 1, background: '#e2e8f0', margin: '4px 0' }} />
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: '6px 12px',
                        fontSize: '0.76rem',
                        textAlign: 'left',
                        cursor: 'pointer',
                        color: '#dc2626',
                        fontWeight: 500,
                      }}
                      onClick={() => {
                        setShowWidgetMenu(false);
                        if (confirm('Delete this widget?')) {
                          deleteWidget(widget.id);
                          onClose();
                        }
                      }}
                    >
                      🗑️ Delete widget
                    </button>
                  </div>
                </>
              )}
              <button className="btn-icon" onClick={onClose}><X size={14} /></button>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
            <label style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#172b4d' }}>
              <input
                type="checkbox"
                checked={showTitleInput}
                onChange={(e) => setShowTitleInput(e.target.checked)}
                style={{ accentColor: '#0052cc' }}
              />
              Title
            </label>
            <label style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#172b4d' }}>
              <input
                type="checkbox"
                checked={showDescInput}
                onChange={(e) => setShowDescInput(e.target.checked)}
                style={{ accentColor: '#0052cc' }}
              />
              Description
            </label>
          </div>
          {showTitleInput && (
            <div style={{ marginTop: 8 }}>
              <input
                value={widget.title ?? ''}
                onChange={(e) => updateWidget(widget.id, { title: e.target.value })}
                placeholder="Widget title"
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
            </div>
          )}
          {showDescInput && (
            <div style={{ marginTop: 8 }}>
              <input
                value={widget.content ?? ''}
                onChange={(e) => updateWidget(widget.id, { content: e.target.value })}
                placeholder="Widget description"
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
            </div>
          )}
        </div>

        {/* Dataset Section */}
        <SectionRow title="Dataset" onPlus={() => setShowFilters(!showFilters)} actionText={showFilters ? "Hide filters" : "Show filters"}>
          <Select
            value={cfg.datasetId ?? ''}
            onChange={(v) => patch({ datasetId: v })}
            options={datasetOptions}
            placeholder="Select dataset..."
          />
          {showFilters && (
            <div style={{ marginTop: 8, padding: '6px 8px', background: '#f4f5f7', borderRadius: 4 }}>
              <span style={{ fontSize: '0.7rem', color: '#5e6c84', display: 'block', marginBottom: 2 }}>Static Filters</span>
              {widget.staticFilters && widget.staticFilters.length > 0 ? (
                widget.staticFilters.map(f => (
                  <div key={f.id} style={{ fontSize: '0.72rem', color: '#172b4d', display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                    <span>{f.field}</span>
                    <span style={{ fontWeight: 600 }}>{String(f.value)}</span>
                  </div>
                ))
              ) : (
                <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>No static filters configured</span>
              )}
            </div>
          )}
        </SectionRow>

        {/* Parameters Section */}
        <SectionRow title="Parameters" onPlus={() => {}}>
          {dataset && dataset.params.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {dataset.params.map(p => (
                <div key={p.keyword} style={{ fontSize: '0.72rem', display: 'flex', justifyContent: 'space-between', background: '#f4f5f7', padding: '4px 6px', borderRadius: 4 }}>
                  <span>{p.displayName || p.keyword}</span>
                  <span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>{p.type}</span>
                </div>
              ))}
            </div>
          ) : (
            <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>No parameters in dataset</span>
          )}
        </SectionRow>

        {/* Visualization Section */}
        <SectionRow title="Visualization">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative' }}>
            <div style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', pointerEvents: 'none', opacity: 0.6 }}>
              {getChartIcon(cfg.chartType)}
            </div>
            <select
              value={cfg.chartType}
              onChange={(e) => patch({ chartType: e.target.value as ChartType })}
              style={{
                width: '100%',
                padding: '6px 8px 6px 28px',
                fontSize: '0.77rem',
                border: '1px solid var(--color-border)',
                borderRadius: 4,
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
              }}
            >
              {CHART_TYPES.map((ct) => (
                <option key={ct.type} value={ct.type}>
                  {ct.label}
                </option>
              ))}
            </select>
          </div>
        </SectionRow>

        {/* Visualization Specific Configuration: Table vs Standard Charts */}
        {cfg.chartType === 'table' ? (
          <>
            {/* Columns Section for Table */}
            <div style={{ position: 'relative' }}>
              <SectionRow
                title="Columns"
                onPlus={() => setShowColumnPicker(!showColumnPicker)}
                actionText="Manage"
              >
                <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => patch({ yFields: fieldOptions.map((o) => o.value) })}
                    style={{
                      padding: '3px 8px',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      background: '#eff6ff',
                      color: '#0052cc',
                      border: '1px solid #bfdbfe',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    Select All ({fieldOptions.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowColumnPicker(true)}
                    style={{
                      padding: '3px 8px',
                      fontSize: '0.7rem',
                      fontWeight: 500,
                      background: '#f8fafc',
                      color: '#334155',
                      border: '1px solid #cbd5e1',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    Column Manager 🔍
                  </button>
                  {(cfg.yFields ?? []).length > 0 && (
                    <button
                      type="button"
                      onClick={() => patch({ yFields: [] })}
                      style={{
                        padding: '3px 8px',
                        fontSize: '0.7rem',
                        fontWeight: 500,
                        background: '#fff1f2',
                        color: '#e11d48',
                        border: '1px solid #fecdd3',
                        borderRadius: 4,
                        cursor: 'pointer',
                      }}
                    >
                      Clear
                    </button>
                  )}
                </div>

                {(cfg.yFields ?? []).length > 0 ? (
                  (cfg.yFields ?? []).map((col, idx) => {
                    const seriesTitleVal = cfg.seriesTitles?.find((st) => st.field === col)?.title;
                    return (
                      <FieldPill
                        key={`${col}-${idx}`}
                        name={col}
                        type={getFieldType(col)}
                        displayName={seriesTitleVal ?? col}
                        onClick={() => setOpenSeriesPopover(openSeriesPopover === `table_${col}` ? null : `table_${col}`)}
                        onRemove={() => {
                          const updated = (cfg.yFields ?? []).filter((_, i) => i !== idx);
                          patch({ yFields: updated });
                          if (openSeriesPopover === `table_${col}`) setOpenSeriesPopover(null);
                        }}
                      />
                    );
                  })
                ) : (
                  <div style={{ fontSize: '0.72rem', color: '#64748b', fontStyle: 'italic', marginBottom: 6 }}>
                    All dataset columns showing by default. Use Column Manager or Select All to pick specific columns.
                  </div>
                )}
              </SectionRow>

              {showColumnPicker && (
                <ColumnPickerPopover
                  allColumns={fieldOptions.map((o) => ({ value: o.value, label: o.label, type: getFieldType(o.value) }))}
                  selectedColumns={cfg.yFields ?? []}
                  onChange={(updatedCols) => patch({ yFields: updatedCols })}
                  onClose={() => setShowColumnPicker(false)}
                />
              )}

              {(cfg.yFields ?? []).map((col) => {
                const seriesTitleVal = cfg.seriesTitles?.find((st) => st.field === col)?.title;
                return openSeriesPopover === `table_${col}` ? (
                  <AxisConfigPopover
                    key={col}
                    fieldName={col}
                    fieldType={getFieldType(col)}
                    axisConfig={cfg.yAxis}
                    seriesTitle={seriesTitleVal}
                    onUpdateSeriesTitle={(title) => {
                      const current = cfg.seriesTitles ? [...cfg.seriesTitles] : [];
                      const idx = current.findIndex((st) => st.field === col);
                      if (idx >= 0) {
                        current[idx] = { field: col, title };
                      } else {
                        current.push({ field: col, title });
                      }
                      patch({ seriesTitles: current });
                    }}
                    onUpdate={(updated) => patchAxis('yAxis', updated)}
                    onClose={() => setOpenSeriesPopover(null)}
                  />
                ) : null;
              })}
            </div>

            {/* Table Settings & Formatting Section */}
            <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1a1a1a' }}>Table Settings</span>

              <TableTitleRowColorPicker
                titleRowBg={cfg.titleRowBg ?? cfg.headerBg}
                onChange={(bg) => {
                  patch({
                    titleRowBg: bg,
                    headerBg: bg,
                  });
                }}
              />

              <FieldRow label="Rows per page">
                <Select
                  value={String(cfg.pageSize ?? 25)}
                  onChange={(v) => patch({ pageSize: Number(v) })}
                  options={[
                    { value: '10', label: '10 rows' },
                    { value: '25', label: '25 rows' },
                    { value: '50', label: '50 rows' },
                    { value: '100', label: '100 rows' },
                    { value: '500', label: '500 rows (Max)' },
                  ]}
                />
              </FieldRow>

              <FieldRow label="Sort column">
                <Select
                  value={cfg.xAxis?.sortByField ?? ''}
                  onChange={(v) => patchAxis('xAxis', { sortByField: v })}
                  options={fieldOptions}
                  placeholder="Default dataset order"
                />
              </FieldRow>

              {cfg.xAxis?.sortByField && (
                <FieldRow label="Sort direction">
                  <Select
                    value={cfg.xAxis?.sortByOrder ?? 'asc'}
                    onChange={(v) => patchAxis('xAxis', { sortByOrder: v as any })}
                    options={[
                      { value: 'asc', label: 'Ascending (A-Z / 0-9)' },
                      { value: 'desc', label: 'Descending (Z-A / 9-0)' },
                    ]}
                  />
                </FieldRow>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#344054' }}>
                  <input
                    type="checkbox"
                    checked={cfg.showSearch ?? true}
                    onChange={(e) => patch({ showSearch: e.target.checked })}
                    style={{ accentColor: '#0052cc' }}
                  />
                  Show search bar
                </label>
                <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#344054' }}>
                  <input
                    type="checkbox"
                    checked={cfg.wrapText ?? false}
                    onChange={(e) => patch({ wrapText: e.target.checked })}
                    style={{ accentColor: '#0052cc' }}
                  />
                  Wrap cell text
                </label>
                <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#344054' }}>
                  <input
                    type="checkbox"
                    checked={cfg.showRowNumbers ?? false}
                    onChange={(e) => patch({ showRowNumbers: e.target.checked })}
                    style={{ accentColor: '#0052cc' }}
                  />
                  Show row numbers
                </label>
              </div>
            </div>
          </>
        ) : (
          <>
            {/* X Axis Section */}
            <div style={{ position: 'relative' }}>
              <SectionRow
                title="X axis"
                onPlus={() => {}}
                onKebab={() => setOpenAxisSettings(openAxisSettings === 'xAxis' ? null : 'xAxis')}
              >
                {cfg.xField ? (
                  <FieldPill
                    name={cfg.xField}
                    type={getFieldType(cfg.xField)}
                    transform={cfg.xAxis?.transform}
                    displayName={cfg.xAxis?.displayName ?? cfg.xAxis?.title}
                    onClick={() => setOpenSeriesPopover(openSeriesPopover === 'xAxis' ? null : 'xAxis')}
                    onRemove={() => {
                      patch({ xField: '' });
                      if (openSeriesPopover === 'xAxis') setOpenSeriesPopover(null);
                    }}
                  />
                ) : (
                  <Select
                    value={cfg.xField ?? ''}
                    onChange={(v) => patch({ xField: v })}
                    options={fieldOptions}
                    placeholder="Add field..."
                  />
                )}
              </SectionRow>

              {openAxisSettings === 'xAxis' && (
                <AxisSettingsPopover
                  axisType="xAxis"
                  axisConfig={cfg.xAxis}
                  fieldOptions={fieldOptions}
                  onUpdate={(updated) => patchAxis('xAxis', updated)}
                  onClose={() => setOpenAxisSettings(null)}
                />
              )}

              {openSeriesPopover === 'xAxis' && cfg.xField && (
                <AxisConfigPopover
                  fieldName={cfg.xField}
                  fieldType={getFieldType(cfg.xField)}
                  axisConfig={cfg.xAxis}
                  onUpdate={(updated) => patchAxis('xAxis', updated)}
                  onClose={() => setOpenSeriesPopover(null)}
                />
              )}
            </div>

            {/* Swap Axes Divider Button */}
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', margin: '4px 0', position: 'relative' }}>
              <div style={{ position: 'absolute', left: 14, right: 14, height: 1, borderBottom: '1px dashed #e1e4e8', zIndex: 1 }} />
              <button
                onClick={handleSwapAxes}
                style={{
                  background: 'white',
                  border: '1px solid #e1e4e8',
                  borderRadius: 4,
                  cursor: 'pointer',
                  padding: 4,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 2,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                  color: '#5e6c84',
                }}
                title="Swap X and Y axes"
              >
                <ArrowUpDown size={12} />
              </button>
            </div>

            {/* Y Axis Section (Multiple Series Support) */}
            <div style={{ position: 'relative' }}>
              <SectionRow
                title="Y axis"
                onPlus={() => isMultiSeriesAllowed && setShowYFieldSelect(!showYFieldSelect)}
                plusDisabled={!isMultiSeriesAllowed}
                onKebab={() => setOpenAxisSettings(openAxisSettings === 'yAxis' ? null : 'yAxis')}
              >
                {(cfg.yFields ?? []).map((yf, idx) => {
                  const seriesTitleVal = cfg.seriesTitles?.find((st) => st.field === yf)?.title;
                  return (
                    <FieldPill
                      key={`${yf}-${idx}`}
                      name={yf}
                      type={getFieldType(yf)}
                      transform={cfg.yAxis?.transform}
                      displayName={seriesTitleVal ?? (cfg.yAxis?.transform && cfg.yAxis.transform !== 'NONE' ? `${cfg.yAxis.transform}(${yf})` : yf)}
                      onClick={() => setOpenSeriesPopover(openSeriesPopover === `yAxis_${yf}` ? null : `yAxis_${yf}`)}
                      onRemove={() => {
                        const updated = (cfg.yFields ?? []).filter((_, i) => i !== idx);
                        patch({ yFields: updated });
                        if (openSeriesPopover === `yAxis_${yf}`) setOpenSeriesPopover(null);
                      }}
                    />
                  );
                })}

                {(showYFieldSelect || (cfg.yFields ?? []).length === 0) && (
                  <div style={{ marginTop: (cfg.yFields ?? []).length > 0 ? 4 : 0 }}>
                    <Select
                      value=""
                      onChange={(v) => {
                        if (v) {
                          patch({ yFields: [...(cfg.yFields ?? []), v] });
                        }
                        setShowYFieldSelect(false);
                      }}
                      options={fieldOptions.filter((o) => !(cfg.yFields ?? []).includes(o.value))}
                      placeholder="Add metric series..."
                    />
                  </div>
                )}

                {(cfg.yFields ?? []).length > 1 && (
                  <div style={{ marginTop: 8, padding: '6px 8px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                    <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#1e293b', fontWeight: 500 }}>
                      <input
                        type="checkbox"
                        checked={cfg.enableSeriesSwitcher ?? false}
                        onChange={(e) => patch({ enableSeriesSwitcher: e.target.checked })}
                        style={{ accentColor: '#0052cc' }}
                      />
                      Enable Series Switcher Tab
                    </label>
                    <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 2, paddingLeft: 20 }}>
                      Shows interactive metric tabs above chart to quickly toggle between series
                    </div>
                  </div>
                )}
              </SectionRow>

              {openAxisSettings === 'yAxis' && (
                <AxisSettingsPopover
                  axisType="yAxis"
                  axisConfig={cfg.yAxis}
                  fieldOptions={fieldOptions}
                  onUpdate={(updated) => patchAxis('yAxis', updated)}
                  onClose={() => setOpenAxisSettings(null)}
                />
              )}

              {(cfg.yFields ?? []).map((yf) => {
                const seriesTitleVal = cfg.seriesTitles?.find((st) => st.field === yf)?.title;
                return openSeriesPopover === `yAxis_${yf}` ? (
                  <AxisConfigPopover
                    key={yf}
                    fieldName={yf}
                    fieldType={getFieldType(yf)}
                    axisConfig={cfg.yAxis}
                    seriesTitle={seriesTitleVal}
                    onUpdateSeriesTitle={(title) => {
                      const current = cfg.seriesTitles ? [...cfg.seriesTitles] : [];
                      const idx = current.findIndex((st) => st.field === yf);
                      if (idx >= 0) {
                        current[idx] = { field: yf, title };
                      } else {
                        current.push({ field: yf, title });
                      }
                      patch({ seriesTitles: current });
                    }}
                    onUpdate={(updated) => patchAxis('yAxis', updated)}
                    onClose={() => setOpenSeriesPopover(null)}
                  />
                ) : null;
              })}
            </div>

            {/* Y2 Axis Section for Combo Charts (Line series) */}
            {cfg.chartType === 'combo' && (
              <div style={{ position: 'relative', marginTop: 8 }}>
                <SectionRow
                  title="Y2 axis (Line series)"
                  onPlus={() => setShowY2FieldSelect(!showY2FieldSelect)}
                  onKebab={() => setOpenAxisSettings(openAxisSettings === 'y2Axis' ? null : 'y2Axis')}
                >
                  {(cfg.y2Fields ?? []).map((yf, idx) => (
                    <FieldPill
                      key={`${yf}-${idx}`}
                      name={yf}
                      type={getFieldType(yf)}
                      transform={cfg.y2Axis?.transform}
                      displayName={cfg.y2Axis?.displayName ?? cfg.y2Axis?.title}
                      onClick={() => setOpenSeriesPopover(openSeriesPopover === `y2Axis_${yf}` ? null : `y2Axis_${yf}`)}
                      onRemove={() => {
                        const updated = (cfg.y2Fields ?? []).filter((_, i) => i !== idx);
                        patch({ y2Fields: updated });
                        if (openSeriesPopover === `y2Axis_${yf}`) setOpenSeriesPopover(null);
                      }}
                    />
                  ))}

                  {(showY2FieldSelect || (cfg.y2Fields ?? []).length === 0) && (
                    <div style={{ marginTop: (cfg.y2Fields ?? []).length > 0 ? 4 : 0 }}>
                      <Select
                        value=""
                        onChange={(v) => {
                          if (v) {
                            patch({ y2Fields: [...(cfg.y2Fields ?? []), v] });
                          }
                          setShowY2FieldSelect(false);
                        }}
                        options={fieldOptions.filter((o) => !(cfg.y2Fields ?? []).includes(o.value))}
                        placeholder="Add line metric series..."
                      />
                    </div>
                  )}
                </SectionRow>

                {openAxisSettings === 'y2Axis' && (
                  <AxisSettingsPopover
                    axisType="yAxis"
                    axisConfig={cfg.y2Axis}
                    fieldOptions={fieldOptions}
                    onUpdate={(updated) => patchAxis('y2Axis', updated)}
                    onClose={() => setOpenAxisSettings(null)}
                  />
                )}

                {(cfg.y2Fields ?? []).map((yf) => (
                  openSeriesPopover === `y2Axis_${yf}` ? (
                    <AxisConfigPopover
                      key={yf}
                      fieldName={yf}
                      fieldType={getFieldType(yf)}
                      axisConfig={cfg.y2Axis}
                      onUpdate={(updated) => patchAxis('y2Axis', updated)}
                      onClose={() => setOpenSeriesPopover(null)}
                    />
                  ) : null
                ))}
              </div>
            )}

            {/* Color Section */}
            <div style={{ position: 'relative' }}>
              <SectionRow
                title="Color"
                onPlus={() => {}}
                onKebab={cfg.colorField ? () => setOpenSeriesPopover(openSeriesPopover === 'color' ? null : 'color') : undefined}
              >
                {cfg.colorField ? (
                  <FieldPill
                    name={cfg.colorField}
                    type={getFieldType(cfg.colorField)}
                    onClick={() => setOpenSeriesPopover(openSeriesPopover === 'color' ? null : 'color')}
                    onRemove={() => {
                      patch({ colorField: '' });
                      if (openSeriesPopover === 'color') setOpenSeriesPopover(null);
                    }}
                  />
                ) : (
                  <Select
                    value={cfg.colorField ?? ''}
                    onChange={(v) => patch({ colorField: v })}
                    options={fieldOptions}
                    placeholder="Add group field..."
                  />
                )}
                <SeriesColorPicker
                  yFields={[...(cfg.yFields ?? []), ...(cfg.y2Fields ?? [])]}
                  seriesColors={cfg.seriesColors}
                  onChange={(updated) => patch({ seriesColors: updated })}
                />
              </SectionRow>

              {openSeriesPopover === 'color' && cfg.colorField && (
                <AxisConfigPopover
                  fieldName={cfg.colorField}
                  fieldType={getFieldType(cfg.colorField)}
                  axisConfig={{}}
                  onUpdate={(updated) => {
                    if (updated.displayName) {
                      patch({ colorField: updated.displayName });
                    }
                  }}
                  onClose={() => setOpenSeriesPopover(null)}
                />
              )}
            </div>
          </>
        )}

        {/* Tooltip Section */}
        <SectionRow title="Tooltip" onPlus={() => setShowTooltipSelect(!showTooltipSelect)}>
          {tooltipFields.map((field) => (
            <FieldPill
              key={field}
              name={field}
              type={getFieldType(field)}
              onRemove={() => patch({ tooltipFields: tooltipFields.filter(f => f !== field) })}
            />
          ))}
          {(showTooltipSelect || tooltipFields.length === 0) && (
            <div style={{ marginTop: tooltipFields.length > 0 ? 4 : 0 }}>
              <Select
                value=""
                onChange={(v) => {
                  if (v && !tooltipFields.includes(v)) {
                    patch({ tooltipFields: [...tooltipFields, v] });
                  }
                  setShowTooltipSelect(false);
                }}
                options={fieldOptions.filter(o => !tooltipFields.includes(o.value))}
                placeholder="Add field..."
              />
            </div>
          )}
        </SectionRow>

        {/* Labels Section */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1a1a1a' }}>Labels</span>
          <label style={{ position: 'relative', display: 'inline-block', width: 34, height: 20 }}>
            <input
              type="checkbox"
              checked={cfg.showValueLabels ?? false}
              onChange={(e) => patch({ showValueLabels: e.target.checked })}
              style={{ opacity: 0, width: 0, height: 0 }}
            />
            <span style={{
              position: 'absolute',
              cursor: 'pointer',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: cfg.showValueLabels ? '#0052cc' : '#e1e4e8',
              transition: '.2s',
              borderRadius: 20,
            }}>
              <span style={{
                position: 'absolute',
                content: '""',
                height: 14,
                width: 14,
                left: 3,
                bottom: 3,
                backgroundColor: 'white',
                transition: '.2s',
                borderRadius: '50%',
                transform: cfg.showValueLabels ? 'translateX(14px)' : 'none',
              }} />
            </span>
          </label>
        </div>

        {/* Collapsible Details Sections */}
        <div style={{ marginTop: 10 }}>

          <CollapsibleSection title="Style Details">
            <label style={{ fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" checked={cfg.showGridlines !== false} onChange={(e) => patch({ showGridlines: e.target.checked })} />
              Show gridlines
            </label>
            <div style={{ marginTop: 8 }}>
              <FieldRow label="Legend Position">
                <Select
                  value={cfg.legend?.position ?? 'bottom'}
                  onChange={(v) => patch({ legend: { ...cfg.legend, position: v as any } })}
                  options={[
                    { value: 'top', label: 'Top' },
                    { value: 'bottom', label: 'Bottom' },
                    { value: 'left', label: 'Left' },
                    { value: 'right', label: 'Right' },
                  ]}
                />
              </FieldRow>
            </div>
          </CollapsibleSection>

          <CollapsibleSection title="Number Format Details">
            <FieldRow label="Type">
              <Select
                value={cfg.numberFormat?.type ?? 'number'}
                onChange={(v) => patch({ numberFormat: { ...cfg.numberFormat, type: v as 'number' | 'currency' | 'percent' } })}
                options={[
                  { value: 'number', label: 'Number' },
                  { value: 'currency', label: 'Currency' },
                  { value: 'percent', label: 'Percent' },
                ]}
              />
            </FieldRow>
            <FieldRow label="Abbreviation">
              <Select
                value={cfg.numberFormat?.abbreviation ?? 'none'}
                onChange={(v) => patch({ numberFormat: { ...cfg.numberFormat, abbreviation: v as 'none' | 'compact' | 'scientific' } } as any)}
                options={[
                  { value: 'none', label: 'None' },
                  { value: 'compact', label: 'Compact (K/M/B)' },
                  { value: 'scientific', label: 'Scientific' },
                ]}
              />
            </FieldRow>
          </CollapsibleSection>
        </div>

      </div>
    </DashboardSidePanel>
  );
}
