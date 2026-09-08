import { useState } from 'react';

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

interface SeriesColorPickerProps {
  yFields: string[];
  seriesColors?: Array<{ field: string; color: string }>;
  onChange: (updated: Array<{ field: string; color: string }>) => void;
}

export default function SeriesColorPicker({
  yFields,
  seriesColors,
  onChange,
}: SeriesColorPickerProps) {
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
