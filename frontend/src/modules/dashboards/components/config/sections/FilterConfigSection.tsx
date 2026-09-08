import { useState } from 'react';
import { X, MoreVertical } from 'lucide-react';
import type { Widget, FilterWidgetConfig, FilterWidgetType } from '@/types/dashboard';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useFieldValues } from '@/modules/dashboards/hooks/useDashboard';
import SectionRow from '../common/SectionRow';
import FieldPill from '../common/FieldPill';
import FieldRow from '../common/FieldRow';
import Select from '../common/Select';
import ColumnPickerPopover from '../common/ColumnPickerPopover';
import AxisConfigPopover from '../common/AxisConfigPopover';

interface FilterConfigSectionProps {
  widget: Widget;
  updateWidget: (id: string, patch: Partial<Widget>) => void;
  onClose: () => void;
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
              fontSize: '0.71rem',
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

export default function FilterConfigSection({
  widget,
  updateWidget,
  onClose,
}: FilterConfigSectionProps) {
  const { activeDashboard, deleteWidget, cloneWidget } = useDashboardStore();
  const [showColumnPicker, setShowColumnPicker] = useState(false);
  const [showFieldPopover, setShowFieldPopover] = useState(false);
  const [showWidgetMenu, setShowWidgetMenu] = useState(false);

  const cfg: FilterWidgetConfig = widget.filterConfig ?? {
    scope: 'page',
    filterType: 'single_value',
    placement: 'both',
    datasetIds: [],
  };

  const currentDatasetId = cfg.dynamicDatasetId ?? cfg.datasetIds?.[0] ?? activeDashboard?.datasets[0]?.id;
  const currentDataset = activeDashboard?.datasets.find((d) => d.id === currentDatasetId);

  const fieldOptions = (currentDataset?.schema ?? []).map((f) => ({
    value: f.name,
    label: f.name,
    type: f.type || 'string',
  }));

  const { data: distinctValues = [] } = useFieldValues(currentDatasetId, cfg.field);

  function patchFilter(p: Partial<FilterWidgetConfig>) {
    const nextCfg = { ...cfg, ...p };
    updateWidget(widget.id, { filterConfig: nextCfg });
  }

  function getFieldType(fieldName: string): string {
    const field = currentDataset?.schema.find((f) => f.name === fieldName);
    return field?.type || 'string';
  }

  const filterTypeOptions: { value: FilterWidgetType; label: string }[] = [
    { value: 'single_value', label: 'Single Value' },
    { value: 'multi_value', label: 'Multi Select' },
    { value: 'date_picker', label: 'Date' },
    { value: 'date_range', label: 'Date Range' },
    { value: 'text_entry', label: 'Text' },
  ];

  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1a1a1a' }}>Filter Configuration</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }}>
            <button
              type="button"
              className="btn-icon"
              onClick={() => setShowWidgetMenu(!showWidgetMenu)}
              title="Filter actions"
              style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            >
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
                    style={{ background: 'none', border: 'none', padding: '6px 12px', fontSize: '0.76rem', textAlign: 'left', cursor: 'pointer', color: '#1e293b' }}
                    onClick={() => { setShowWidgetMenu(false); cloneWidget(widget.id); }}
                  >
                    📋 Duplicate filter
                  </button>
                  <div style={{ height: 1, background: '#e2e8f0', margin: '4px 0' }} />
                  <button
                    type="button"
                    style={{ background: 'none', border: 'none', padding: '6px 12px', fontSize: '0.76rem', textAlign: 'left', cursor: 'pointer', color: '#dc2626', fontWeight: 500 }}
                    onClick={() => {
                      setShowWidgetMenu(false);
                      if (confirm('Delete this filter?')) {
                        deleteWidget(widget.id);
                        onClose();
                      }
                    }}
                  >
                    🗑️ Delete filter
                  </button>
                </div>
              </>
            )}
            <button
              type="button"
              className="btn-icon"
              onClick={onClose}
              style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Filter Title */}
        <FieldRow label="Title">
          <input
            type="text"
            value={widget.title ?? ''}
            onChange={(e) => updateWidget(widget.id, { title: e.target.value })}
            placeholder="e.g. Region, Date Range, Category"
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

      {/* Filter Type */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: '0.74rem', fontWeight: 600, color: '#475569' }}>Filter Type</span>
        <SegmentedControl
          value={cfg.filterType}
          onChange={(v) => patchFilter({ filterType: v, defaultValue: undefined })}
          options={filterTypeOptions}
        />
      </div>

      {/* Filter Placement */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: '0.74rem', fontWeight: 600, color: '#475569' }}>Placement</span>
        <SegmentedControl
          value={cfg.placement ?? 'both'}
          onChange={(v) => patchFilter({ placement: v })}
          options={[
            { value: 'both', label: 'Top Bar & Canvas' },
            { value: 'bar', label: 'Top Bar Only' },
            { value: 'canvas', label: 'Canvas Widget Only' },
          ]}
        />
      </div>

      {/* Dataset Selection */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0' }}>
        <FieldRow label="Target Dataset">
          <Select
            value={currentDatasetId ?? ''}
            onChange={(v) =>
              patchFilter({
                datasetIds: [v],
                dynamicDatasetId: v,
                field: undefined,
                defaultValue: undefined,
              })
            }
            options={(activeDashboard?.datasets ?? []).map((d) => ({ value: d.id, label: d.name }))}
            placeholder="Select dataset..."
          />
        </FieldRow>
      </div>

      {/* Column / Field Selection (Minimalist UI) */}
      <div style={{ position: 'relative' }}>
        <SectionRow
          title="Filter Field"
          onPlus={cfg.field ? undefined : () => setShowColumnPicker(!showColumnPicker)}
        >
          {cfg.field ? (
            <div style={{ marginTop: 2 }}>
              <FieldPill
                name={cfg.field}
                type={getFieldType(cfg.field)}
                displayName={cfg.field}
                onClick={() => setShowFieldPopover(!showFieldPopover)}
                onRemove={() => patchFilter({ field: undefined, defaultValue: undefined })}
              />
            </div>
          ) : (
            <div
              onClick={() => setShowColumnPicker(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '10px',
                border: '1px dashed #cbd5e1',
                borderRadius: 6,
                fontSize: '0.75rem',
                color: '#0052cc',
                cursor: 'pointer',
                background: '#f8fafc',
              }}
            >
              + Select column to filter on
            </div>
          )}
        </SectionRow>

        {showColumnPicker && (
          <ColumnPickerPopover
            allColumns={fieldOptions}
            selectedColumns={cfg.field ? [cfg.field] : []}
            onChange={(cols) => {
              patchFilter({ field: cols[0], defaultValue: undefined });
              setShowColumnPicker(false);
            }}
            onClose={() => setShowColumnPicker(false)}
          />
        )}

        {showFieldPopover && cfg.field && (
          <AxisConfigPopover
            fieldName={cfg.field}
            fieldType={getFieldType(cfg.field)}
            fieldOptions={fieldOptions}
            onFieldChange={(newField) => patchFilter({ field: newField, defaultValue: undefined })}
            onUpdate={(updated) => patchFilter(updated)}
            hideDisplayName
            hideScaleType
            hideErrorBar
            onClose={() => setShowFieldPopover(false)}
          />
        )}
      </div>

      {/* Default Value & Behavior Settings */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1a1a1a' }}>Default Value & Options</span>

        {/* Single value default */}
        {cfg.filterType === 'single_value' && (
          <>
            <FieldRow label="Default Value">
              <Select
                value={String(cfg.defaultValue ?? '')}
                onChange={(v) => patchFilter({ defaultValue: v || undefined })}
                options={[
                  { value: '', label: '(None / All)' },
                  ...distinctValues.map((val) => ({ value: val, label: val })),
                ]}
                placeholder="None (Show all)"
              />
            </FieldRow>
            <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#344054', marginTop: 2 }}>
              <input
                type="checkbox"
                checked={cfg.allowAll ?? true}
                onChange={(e) => patchFilter({ allowAll: e.target.checked })}
                style={{ accentColor: '#0052cc' }}
              />
              Allow "All" option in dropdown
            </label>
          </>
        )}

        {/* Multi value default */}
        {cfg.filterType === 'multi_value' && (
          <>
            <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#344054' }}>
              <input
                type="checkbox"
                checked={cfg.allowAll ?? true}
                onChange={(e) => patchFilter({ allowAll: e.target.checked })}
                style={{ accentColor: '#0052cc' }}
              />
              Allow "All" quick select button
            </label>
          </>
        )}

        {/* Date picker default */}
        {cfg.filterType === 'date_picker' && (
          <FieldRow label="Default Date">
            <input
              type="date"
              value={String(cfg.defaultValue ?? '')}
              onChange={(e) => patchFilter({ defaultValue: e.target.value || undefined })}
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
          </FieldRow>
        )}

        {/* Date range default */}
        {cfg.filterType === 'date_range' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 500 }}>Default Date Range:</span>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="date"
                value={Array.isArray(cfg.defaultValue) ? (cfg.defaultValue[0] ?? '') : ''}
                onChange={(e) => {
                  const currentEnd = Array.isArray(cfg.defaultValue) ? (cfg.defaultValue[1] ?? '') : '';
                  patchFilter({ defaultValue: [e.target.value, currentEnd] });
                }}
                style={{ flex: 1, padding: '4px 6px', fontSize: '0.72rem', border: '1px solid var(--color-border)', borderRadius: 4, background: 'var(--color-surface)', color: 'var(--color-text)' }}
              />
              <span style={{ fontSize: '0.75rem', alignSelf: 'center', color: '#94a3b8' }}>→</span>
              <input
                type="date"
                value={Array.isArray(cfg.defaultValue) ? (cfg.defaultValue[1] ?? '') : ''}
                onChange={(e) => {
                  const currentStart = Array.isArray(cfg.defaultValue) ? (cfg.defaultValue[0] ?? '') : '';
                  patchFilter({ defaultValue: [currentStart, e.target.value] });
                }}
                style={{ flex: 1, padding: '4px 6px', fontSize: '0.72rem', border: '1px solid var(--color-border)', borderRadius: 4, background: 'var(--color-surface)', color: 'var(--color-text)' }}
              />
            </div>
          </div>
        )}

        {/* Text entry default */}
        {cfg.filterType === 'text_entry' && (
          <>
            <FieldRow label="Default Search">
              <input
                type="text"
                value={String(cfg.defaultValue ?? '')}
                onChange={(e) => patchFilter({ defaultValue: e.target.value || undefined })}
                placeholder="Default search query..."
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
            </FieldRow>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
              <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 500 }}>Match Mode</span>
              <SegmentedControl
                value={cfg.matchMode ?? 'contains'}
                onChange={(v) => patchFilter({ matchMode: v as 'contains' | 'exact' | 'starts_with' })}
                options={[
                  { value: 'contains', label: 'Contains' },
                  { value: 'exact', label: 'Exact' },
                  { value: 'starts_with', label: 'Starts With' },
                ]}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
