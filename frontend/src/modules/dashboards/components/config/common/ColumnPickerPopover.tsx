import { useState, useMemo } from 'react';

interface ColumnOption {
  value: string;
  label: string;
  type?: string;
}

interface ColumnPickerPopoverProps {
  allColumns: ColumnOption[];
  selectedColumns: string[];
  onChange: (cols: string[]) => void;
  onClose: () => void;
}

export default function ColumnPickerPopover({
  allColumns,
  selectedColumns,
  onChange,
  onClose,
}: ColumnPickerPopoverProps) {
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
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f1f5f9',
            paddingBottom: 6,
          }}
        >
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
