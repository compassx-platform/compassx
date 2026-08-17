/**
 * FilterBar — strip showing active filter chips + clear all.
 * Reference: active-filters-bar-55a23a25064855200d1edaf8bcbe8bd5.png
 */

import { X } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';

export default function FilterBar() {
  const { filterState, activeDashboard, activePageId, setFilterValue, clearAllFilters, activeDashboard: db, editMode } = useDashboardStore();

  const activeFilters = Object.entries(filterState).filter(([, v]) => v !== null && v !== '' && !(Array.isArray(v) && v.length === 0));

  if (activeFilters.length === 0) return null;

  function getLabelForFilter(id: string): string {
    const widget = db?.widgets.find((w) => w.id === id || id.startsWith(`cross_${w.id}`));
    if (id.startsWith('cross_')) return `${widget?.title ?? 'Chart'} selection`;
    return widget?.filterConfig?.field ?? widget?.title ?? id;
  }

  function formatValue(v: unknown): string {
    if (Array.isArray(v)) return v.join(', ');
    if (typeof v === 'string') return v;
    if (typeof v === 'number') return String(v);
    return JSON.stringify(v);
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      padding: editMode ? '4px 12px' : '8px 16px',
      borderBottom: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
      flexWrap: 'wrap',
      flexShrink: 0,
    }}>
      <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)', marginRight: 2 }}>
        Active filters:
      </span>
      {activeFilters.map(([id, value]) => (
        <div
          key={id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            background: 'var(--color-primary-bg)',
            color: 'var(--color-primary)',
            borderRadius: 12,
            padding: '2px 8px 2px 10px',
            fontSize: '0.72rem',
            fontWeight: 500,
          }}
        >
          <span style={{ color: 'var(--color-text-muted)', marginRight: 2 }}>{getLabelForFilter(id)}:</span>
          <span>{formatValue(value)}</span>
          <button
            onClick={() => setFilterValue(id, null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', padding: 0, color: 'var(--color-primary)', marginLeft: 2 }}
          >
            <X size={10} />
          </button>
        </div>
      ))}
      <button
        onClick={clearAllFilters}
        style={{
          marginLeft: 4,
          fontSize: '0.7rem',
          color: 'var(--color-text-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textDecoration: 'underline',
        }}
      >
        Clear all
      </button>
    </div>
  );
}

