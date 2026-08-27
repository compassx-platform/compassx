import { useState } from 'react';
import type { VisualizationConfigProps } from '../types';
import SectionRow from '../common/SectionRow';
import FieldPill from '../common/FieldPill';
import Select from '../common/Select';
import FieldRow from '../common/FieldRow';
import AxisConfigPopover from '../common/AxisConfigPopover';
import ColumnPickerPopover from '../common/ColumnPickerPopover';
import TableHeaderStylePopover from '../common/TableHeaderStylePopover';

export default function TableConfigSection({
  config,
  fieldOptions,
  getFieldType,
  patch,
  patchAxis,
}: VisualizationConfigProps) {
  const [showColumnPicker, setShowColumnPicker] = useState(false);
  const [showHeaderStylePopover, setShowHeaderStylePopover] = useState(false);
  const [openSeriesPopover, setOpenSeriesPopover] = useState<string | null>(null);

  return (
    <>
      {/* Columns Section for Table */}
      <div style={{ position: 'relative' }}>
        <SectionRow
          title="Columns"
          onPlus={() => setShowColumnPicker(!showColumnPicker)}
          onKebab={() => setShowHeaderStylePopover(!showHeaderStylePopover)}
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
            {(config.yFields ?? []).length > 0 && (
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

          {(config.yFields ?? []).length > 0 ? (
            (config.yFields ?? []).map((col, idx) => {
              const seriesTitleVal = config.seriesTitles?.find((st) => st.field === col)?.title;
              return (
                <FieldPill
                  key={`${col}-${idx}`}
                  name={col}
                  type={getFieldType(col)}
                  displayName={seriesTitleVal ?? col}
                  onClick={() =>
                    setOpenSeriesPopover(openSeriesPopover === `table_${col}` ? null : `table_${col}`)
                  }
                  onRemove={() => {
                    const updated = (config.yFields ?? []).filter((_, i) => i !== idx);
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

        {showHeaderStylePopover && (
          <TableHeaderStylePopover
            config={config}
            onPatch={patch}
            onClose={() => setShowHeaderStylePopover(false)}
          />
        )}

        {showColumnPicker && (
          <ColumnPickerPopover
            allColumns={fieldOptions.map((o) => ({ value: o.value, label: o.label, type: getFieldType(o.value) }))}
            selectedColumns={config.yFields ?? []}
            onChange={(updatedCols) => patch({ yFields: updatedCols })}
            onClose={() => setShowColumnPicker(false)}
          />
        )}

        {(config.yFields ?? []).map((col) => {
          const seriesTitleVal = config.seriesTitles?.find((st) => st.field === col)?.title;
          return openSeriesPopover === `table_${col}` ? (
            <AxisConfigPopover
              key={col}
              fieldName={col}
              fieldType={getFieldType(col)}
              axisConfig={config.yAxis}
              seriesTitle={seriesTitleVal}
              onUpdateSeriesTitle={(title) => {
                const current = config.seriesTitles ? [...config.seriesTitles] : [];
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

        <FieldRow label="Rows per page">
          <Select
            value={String(config.pageSize ?? 25)}
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
            value={config.xAxis?.sortByField ?? ''}
            onChange={(v) => patchAxis('xAxis', { sortByField: v })}
            options={fieldOptions}
            placeholder="Default dataset order"
          />
        </FieldRow>

        {config.xAxis?.sortByField && (
          <FieldRow label="Sort direction">
            <Select
              value={config.xAxis?.sortByOrder ?? 'asc'}
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
              checked={config.showSearch ?? true}
              onChange={(e) => patch({ showSearch: e.target.checked })}
              style={{ accentColor: '#0052cc' }}
            />
            Show search bar
          </label>
          <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#344054' }}>
            <input
              type="checkbox"
              checked={config.wrapText ?? false}
              onChange={(e) => patch({ wrapText: e.target.checked })}
              style={{ accentColor: '#0052cc' }}
            />
            Wrap cell text
          </label>
          <label style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#344054' }}>
            <input
              type="checkbox"
              checked={config.showRowNumbers ?? false}
              onChange={(e) => patch({ showRowNumbers: e.target.checked })}
              style={{ accentColor: '#0052cc' }}
            />
            Show row numbers
          </label>
        </div>
      </div>
    </>
  );
}
