import { X } from 'lucide-react';
import FieldRow from './FieldRow';
import Select from './Select';

interface AxisSettingsPopoverProps {
  axisType: 'xAxis' | 'yAxis' | 'y2Axis';
  axisConfig?: Record<string, any>;
  fieldOptions: { value: string; label: string }[];
  onUpdate: (updated: Record<string, any>) => void;
  onClose: () => void;
}

export default function AxisSettingsPopover({
  axisType,
  axisConfig = {},
  fieldOptions,
  onUpdate,
  onClose,
}: AxisSettingsPopoverProps) {
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
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f1f5f9',
            paddingBottom: 6,
          }}
        >
          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#0f172a' }}>
            {axisType === 'xAxis' ? 'X Axis Settings' : axisType === 'y2Axis' ? 'Y2 Axis Settings' : 'Y Axis Settings'}
          </span>
          <button
            type="button"
            className="btn-icon"
            onClick={onClose}
            style={{ padding: 2, background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <X size={13} />
          </button>
        </div>

        {/* Title */}
        <FieldRow label="Title">
          <input
            value={axisConfig.title ?? ''}
            onChange={(e) => onUpdate({ title: e.target.value })}
            placeholder="Custom axis title..."
            style={{
              width: '100%',
              padding: '4px 6px',
              fontSize: '0.76rem',
              border: '1px solid #cbd5e1',
              borderRadius: 4,
              outline: 'none',
            }}
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
