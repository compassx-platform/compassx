import { useState } from 'react';
import { X, Filter, Plus, Calendar, Search, Check, ChevronDown } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useFieldValues } from '@/modules/dashboards/hooks/useDashboard';
import { randomUUID } from '@/lib/utils';
import type { Widget, FilterValue, FilterWidgetConfig } from '@/types/dashboard';

export default function FilterBar() {
  const {
    activeDashboard,
    activePageId,
    filterState,
    setFilterValue,
    clearAllFilters,
    editMode,
    selectedWidgetId,
    setSelectedWidget,
    addWidget,
  } = useDashboardStore();

  const pageFilterWidgets = (activeDashboard?.widgets ?? []).filter(
    (w) => w.pageId === activePageId && w.widgetType === 'filter' && w.filterConfig?.placement !== 'canvas'
  );

  const hasActiveFilterValues = Object.entries(filterState).some(
    ([, v]) => v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)
  );

  function handleAddFilter() {
    if (!activePageId || !activeDashboard) return;
    const id = randomUUID();
    const defaultDataset = activeDashboard.datasets[0];
    const defaultField = defaultDataset?.schema[0]?.name;
    const widget: Widget = {
      id,
      pageId: activePageId,
      widgetType: 'filter',
      title: 'New filter',
      gridItem: { i: id, x: 0, y: 0, w: 3, h: 2, minW: 2, minH: 1 },
      filterConfig: {
        scope: 'page',
        filterType: 'single_value',
        placement: 'both',
        field: defaultField,
        datasetIds: defaultDataset ? [defaultDataset.id] : [],
        allowAll: true,
      },
    };
    addWidget(widget);
    setSelectedWidget(id);
  }

  // If in view mode and no filters exist on this page, don't render anything
  if (!editMode && pageFilterWidgets.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '6px 14px',
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
        minHeight: 40,
        flexWrap: 'wrap',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--color-text-muted)', fontSize: '0.74rem', fontWeight: 600 }}>
        <Filter size={13} style={{ color: 'var(--color-primary)' }} />
        <span>Filters:</span>
      </div>

      {pageFilterWidgets.length === 0 && editMode ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
            No page filters yet.
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: '0.72rem', padding: '2px 8px', gap: 4 }}
            onClick={handleAddFilter}
          >
            <Plus size={11} /> Add filter
          </button>
        </div>
      ) : (
        pageFilterWidgets.map((filterWidget) => (
          <FilterBarItem
            key={filterWidget.id}
            widget={filterWidget}
            editMode={editMode}
            isSelected={selectedWidgetId === filterWidget.id}
            onSelect={() => setSelectedWidget(filterWidget.id)}
          />
        ))
      )}

      {/* Action buttons at right end */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        {hasActiveFilterValues && (
          <button
            onClick={clearAllFilters}
            style={{
              fontSize: '0.70rem',
              color: 'var(--color-primary)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 500,
              textDecoration: 'underline',
              padding: 0,
            }}
          >
            Clear all
          </button>
        )}

        {editMode && pageFilterWidgets.length > 0 && (
          <button
            type="button"
            onClick={handleAddFilter}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 3,
              fontSize: '0.70rem',
              color: '#0052cc',
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              borderRadius: 4,
              padding: '2px 6px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            <Plus size={11} /> Add filter
          </button>
        )}
      </div>
    </div>
  );
}

// ── Individual Inline Filter Component in FilterBar ───────────────────────────

interface FilterBarItemProps {
  widget: Widget;
  editMode: boolean;
  isSelected: boolean;
  onSelect: () => void;
}

function FilterBarItem({ widget, editMode, isSelected, onSelect }: FilterBarItemProps) {
  const { filterState, setFilterValue, activeDashboard } = useDashboardStore();
  const cfg = widget.filterConfig;
  const filterId = widget.id;
  const currentValue = filterState[filterId] ?? null;

  const datasetId = cfg?.dynamicDatasetId ?? cfg?.datasetIds?.[0] ?? activeDashboard?.datasets[0]?.id;
  const { data: fieldValues = [] } = useFieldValues(datasetId, cfg?.field);

  function setValue(val: FilterValue) {
    setFilterValue(filterId, val);
  }

  const label = widget.title || cfg?.field || 'Filter';
  const options = cfg?.listMode === 'static' ? (cfg.staticOptions ?? []) : fieldValues;

  return (
    <div
      onClick={editMode ? onSelect : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 8px',
        borderRadius: 6,
        background: isSelected ? 'var(--color-primary-bg)' : '#f8fafc',
        border: `1px solid ${isSelected ? 'var(--color-primary)' : '#e2e8f0'}`,
        cursor: editMode ? 'pointer' : 'default',
        transition: 'all 0.12s ease',
        boxShadow: isSelected ? '0 0 0 2px rgba(0, 82, 204, 0.2)' : 'none',
      }}
    >
      <span style={{ fontSize: '0.72rem', fontWeight: 600, color: isSelected ? 'var(--color-primary)' : '#475569', whiteSpace: 'nowrap' }}>
        {label}:
      </span>

      {/* Render based on filterType */}
      {(!cfg?.filterType || cfg.filterType === 'single_value') && (
        <InlineSingleSelect
          value={currentValue as string}
          options={options}
          onChange={setValue}
          allowAll={cfg?.allowAll ?? true}
        />
      )}

      {cfg?.filterType === 'multi_value' && (
        <InlineMultiSelect
          value={currentValue as string[]}
          options={options}
          onChange={setValue}
          allowAll={cfg?.allowAll ?? true}
        />
      )}

      {cfg?.filterType === 'date_picker' && (
        <input
          type="date"
          value={String(currentValue ?? '')}
          onChange={(e) => setValue(e.target.value || null)}
          onClick={(e) => e.stopPropagation()}
          style={{
            padding: '2px 5px',
            fontSize: '0.72rem',
            border: '1px solid #cbd5e1',
            borderRadius: 4,
            background: '#ffffff',
            color: '#1e293b',
            outline: 'none',
          }}
        />
      )}

      {cfg?.filterType === 'date_range' && (
        <InlineDateRange
          value={currentValue as [string, string]}
          onChange={setValue}
        />
      )}

      {cfg?.filterType === 'text_entry' && (
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }} onClick={(e) => e.stopPropagation()}>
          <Search size={11} style={{ position: 'absolute', left: 6, color: '#94a3b8', pointerEvents: 'none' }} />
          <input
            type="text"
            value={String(currentValue ?? '')}
            onChange={(e) => setValue(e.target.value || null)}
            placeholder="Search..."
            style={{
              padding: '2px 6px 2px 22px',
              fontSize: '0.72rem',
              border: '1px solid #cbd5e1',
              borderRadius: 4,
              background: '#ffffff',
              color: '#1e293b',
              outline: 'none',
              width: 120,
            }}
          />
          {currentValue && (
            <button
              onClick={() => setValue(null)}
              style={{ position: 'absolute', right: 4, background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: '#94a3b8' }}
            >
              <X size={10} />
            </button>
          )}
        </div>
      )}

      {/* Clear single filter button */}
      {currentValue !== null && currentValue !== '' && !(Array.isArray(currentValue) && currentValue.length === 0) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setValue(null);
          }}
          title="Reset filter"
          style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', padding: 1, color: '#94a3b8' }}
        >
          <X size={11} />
        </button>
      )}
    </div>
  );
}

// ── Inline Select Components ──────────────────────────────────────────────────

function InlineSingleSelect({
  value,
  options,
  onChange,
  allowAll,
}: {
  value: string | null;
  options: string[];
  onChange: (v: FilterValue) => void;
  allowAll?: boolean;
}) {
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
      onClick={(e) => e.stopPropagation()}
      style={{
        padding: '2px 6px',
        fontSize: '0.72rem',
        border: '1px solid #cbd5e1',
        borderRadius: 4,
        background: '#ffffff',
        color: '#1e293b',
        outline: 'none',
        cursor: 'pointer',
        maxWidth: 140,
      }}
    >
      {allowAll && <option value="">All</option>}
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

function InlineMultiSelect({
  value,
  options,
  onChange,
  allowAll,
}: {
  value: string[] | null;
  options: string[];
  onChange: (v: FilterValue) => void;
  allowAll?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const selected = value ?? [];

  function toggle(opt: string) {
    if (selected.includes(opt)) {
      onChange(selected.filter((s) => s !== opt));
    } else {
      onChange([...selected, opt]);
    }
  }

  return (
    <div style={{ position: 'relative' }} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '2px 8px',
          fontSize: '0.72rem',
          border: '1px solid #cbd5e1',
          borderRadius: 4,
          background: '#ffffff',
          color: '#1e293b',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        <span>
          {selected.length === 0 ? 'All' : `${selected.length} selected`}
        </span>
        <ChevronDown size={11} style={{ opacity: 0.6 }} />
      </button>

      {isOpen && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 998 }} onClick={() => setIsOpen(false)} />
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
              boxShadow: '0 6px 20px rgba(0,0,0,0.15)',
              padding: 6,
              minWidth: 160,
              maxHeight: 200,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            {allowAll && (
              <button
                type="button"
                onClick={() => onChange(null)}
                style={{
                  textAlign: 'left',
                  padding: '4px 6px',
                  fontSize: '0.72rem',
                  fontWeight: selected.length === 0 ? 600 : 400,
                  color: selected.length === 0 ? '#0052cc' : '#334155',
                  background: selected.length === 0 ? '#eff6ff' : 'transparent',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>Select All (Clear)</span>
                {selected.length === 0 && <Check size={11} />}
              </button>
            )}
            {options.map((opt) => {
              const isChecked = selected.includes(opt);
              return (
                <label
                  key={opt}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 6px',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                    borderRadius: 4,
                    color: '#1e293b',
                    background: isChecked ? '#eff6ff' : 'transparent',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggle(opt)}
                    style={{ accentColor: '#0052cc' }}
                  />
                  <span>{opt}</span>
                </label>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function InlineDateRange({
  value,
  onChange,
}: {
  value: [string, string] | null;
  onChange: (v: FilterValue) => void;
}) {
  const [start, end] = value ?? ['', ''];

  function applyPreset(days: number) {
    const now = new Date();
    const fmt = (d: Date) => d.toISOString().split('T')[0];
    const from = new Date(now);
    from.setDate(from.getDate() - days);
    onChange([fmt(from), fmt(now)]);
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }} onClick={(e) => e.stopPropagation()}>
      <input
        type="date"
        value={start}
        onChange={(e) => onChange([e.target.value, end])}
        style={{ padding: '2px 4px', fontSize: '0.70rem', border: '1px solid #cbd5e1', borderRadius: 4, background: '#ffffff', color: '#1e293b' }}
      />
      <span style={{ fontSize: '0.70rem', color: '#94a3b8' }}>→</span>
      <input
        type="date"
        value={end}
        onChange={(e) => onChange([start, e.target.value])}
        style={{ padding: '2px 4px', fontSize: '0.70rem', border: '1px solid #cbd5e1', borderRadius: 4, background: '#ffffff', color: '#1e293b' }}
      />
      <button
        type="button"
        onClick={() => applyPreset(7)}
        style={{ fontSize: '0.66rem', padding: '1px 5px', borderRadius: 3, border: '1px solid #cbd5e1', background: '#ffffff', color: '#475569', cursor: 'pointer' }}
      >
        7d
      </button>
      <button
        type="button"
        onClick={() => applyPreset(30)}
        style={{ fontSize: '0.66rem', padding: '1px 5px', borderRadius: 3, border: '1px solid #cbd5e1', background: '#ffffff', color: '#475569', cursor: 'pointer' }}
      >
        30d
      </button>
    </div>
  );
}
