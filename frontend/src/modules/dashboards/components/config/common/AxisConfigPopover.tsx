interface AxisConfigPopoverProps {
  fieldName: string;
  fieldType: string;
  axisConfig?: Record<string, any>;
  seriesTitle?: string;
  fieldOptions?: Array<{ value: string; label: string }>;
  onFieldChange?: (newFieldName: string) => void;
  onUpdateSeriesTitle?: (title: string) => void;
  onUpdate: (config: Record<string, any>) => void;
  onClose: () => void;
  hideDisplayName?: boolean;
  hideScaleType?: boolean;
  hideErrorBar?: boolean;
}

const TRANSFORMS = [
  'NONE', 'SUM', 'AVG', 'MEDIAN', 'MIN',
  'MAX', 'COUNT', 'COUNT DISTINCT', 'VAR', 'STD',
  'PERCENTILE', 'FIRST', 'LAST'
];

export default function AxisConfigPopover({
  fieldName,
  fieldType,
  axisConfig = {},
  seriesTitle,
  fieldOptions,
  onFieldChange,
  onUpdateSeriesTitle,
  onUpdate,
  onClose,
  hideDisplayName = false,
  hideScaleType = false,
  hideErrorBar = false,
}: AxisConfigPopoverProps) {
  const isNumeric = ['integer', 'float', 'number', 'double', 'decimal'].includes((fieldType || '').toLowerCase());
  const scaleType = axisConfig.scaleType ?? (isNumeric ? 'continuous' : 'categorical');
  const transform = axisConfig.transform ?? 'NONE';
  const displayName = seriesTitle ?? axisConfig.displayName ?? axisConfig.title ?? fieldName;
  const errorBar = axisConfig.errorBar ?? false;

  function handleSelectTransform(tf: string) {
    onUpdate({
      transform: tf,
    });
  }

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
        {/* Field Selection / Display */}
        <div>
          <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
            Field
          </label>
          {fieldOptions && onFieldChange ? (
            <select
              value={fieldName}
              onChange={(e) => onFieldChange(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 8px',
                fontSize: '0.76rem',
                border: '1px solid #cbd5e1',
                borderRadius: 6,
                background: '#f8fafc',
                color: '#0f172a',
                fontWeight: 500,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              {fieldOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: 6,
                padding: '5px 8px',
                fontWeight: 500,
                color: '#0f172a',
              }}
            >
              <span
                style={{
                  fontSize: '0.62rem',
                  fontWeight: 700,
                  color: '#475569',
                  background: '#e2e8f0',
                  padding: '1px 4px',
                  borderRadius: 3,
                }}
              >
                {isNumeric ? '1.2' : 'Abc'}
              </span>
              <span>{fieldName}</span>
            </div>
          )}
        </div>

        {/* Scale Type Segmented Toggle (Charts only) */}
        {!hideScaleType && (
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
        )}

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
                  onClick={() => handleSelectTransform(tf)}
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

        {/* Display Name Input (Charts only) */}
        {!hideDisplayName && (
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
        )}

        {/* Error Bar Switch (Charts only) */}
        {!hideErrorBar && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 2 }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 500, color: '#334155' }}>Error bar</span>
            <label style={{ position: 'relative', display: 'inline-block', width: 32, height: 18, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={errorBar}
                onChange={(e) => onUpdate({ errorBar: e.target.checked })}
                style={{ opacity: 0, width: 0, height: 0 }}
              />
              <span
                style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundColor: errorBar ? '#0052cc' : '#cbd5e1',
                  borderRadius: 20,
                  transition: '0.2s',
                }}
              >
                <span
                  style={{
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
                  }}
                />
              </span>
            </label>
          </div>
        )}
      </div>
    </>
  );
}
