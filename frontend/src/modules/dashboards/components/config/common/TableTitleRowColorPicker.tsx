import { useState } from 'react';
import { X } from 'lucide-react';

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

interface TableTitleRowColorPickerProps {
  titleRowBg?: string;
  onChange: (bg?: string) => void;
}

export default function TableTitleRowColorPicker({
  titleRowBg,
  onChange,
}: TableTitleRowColorPickerProps) {
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
