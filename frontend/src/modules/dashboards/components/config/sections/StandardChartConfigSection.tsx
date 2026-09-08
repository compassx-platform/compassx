import { useState } from 'react';
import { ArrowUpDown } from 'lucide-react';
import type { VisualizationConfigProps } from '../types';
import SectionRow from '../common/SectionRow';
import FieldPill from '../common/FieldPill';
import Select from '../common/Select';
import FieldRow from '../common/FieldRow';
import AxisConfigPopover from '../common/AxisConfigPopover';
import AxisSettingsPopover from '../common/AxisSettingsPopover';
import SeriesColorPicker from '../common/SeriesColorPicker';
import CollapsibleSection from '../common/CollapsibleSection';
import NumberFormatSection from '../common/NumberFormatSection';

export default function StandardChartConfigSection({
  config,
  fieldOptions,
  getFieldType,
  patch,
  patchAxis,
}: VisualizationConfigProps) {
  const [openAxisSettings, setOpenAxisSettings] = useState<'xAxis' | 'yAxis' | 'y2Axis' | null>(null);
  const [openSeriesPopover, setOpenSeriesPopover] = useState<string | null>(null);
  const [showXFieldSelect, setShowXFieldSelect] = useState(false);
  const [showYFieldSelect, setShowYFieldSelect] = useState(false);
  const [showY2FieldSelect, setShowY2FieldSelect] = useState(false);
  const [showTooltipSelect, setShowTooltipSelect] = useState(false);

  const isMultiSeriesAllowed = !['counter', 'pie', 'funnel', 'choropleth', 'point_map'].includes(
    config.chartType ?? 'bar'
  );

  function handleSwapAxes() {
    const x = config.xField;
    const y = config.yFields?.[0];
    patch({ xField: y, yFields: x ? [x] : [] });
  }

  const tooltipFields = config.tooltipFields ?? [];

  return (
    <>
      {/* X Axis Section */}
      <div style={{ position: 'relative' }}>
        <SectionRow
          title="X axis"
          onPlus={!config.xField ? () => setShowXFieldSelect(!showXFieldSelect) : undefined}
          onKebab={() => setOpenAxisSettings(openAxisSettings === 'xAxis' ? null : 'xAxis')}
        >
          {config.xField ? (
            <FieldPill
              name={config.xField}
              type={getFieldType(config.xField)}
              transform={config.xAxis?.transform}
              displayName={config.xAxis?.displayName ?? config.xAxis?.title}
              onClick={() => setOpenSeriesPopover(openSeriesPopover === 'xAxis' ? null : 'xAxis')}
              onRemove={() => {
                patch({ xField: '' });
                if (openSeriesPopover === 'xAxis') setOpenSeriesPopover(null);
                setShowXFieldSelect(false);
              }}
            />
          ) : showXFieldSelect ? (
            <div style={{ marginTop: 4 }}>
              <Select
                value={config.xField ?? ''}
                onChange={(v) => {
                  patch({ xField: v });
                  setShowXFieldSelect(false);
                }}
                options={fieldOptions}
                placeholder="Add field..."
              />
            </div>
          ) : null}
        </SectionRow>

        {openAxisSettings === 'xAxis' && (
          <AxisSettingsPopover
            axisType="xAxis"
            axisConfig={config.xAxis}
            fieldOptions={fieldOptions}
            onUpdate={(updated) => patchAxis('xAxis', updated)}
            onClose={() => setOpenAxisSettings(null)}
          />
        )}

        {openSeriesPopover === 'xAxis' && config.xField && (
          <AxisConfigPopover
            fieldName={config.xField}
            fieldType={getFieldType(config.xField)}
            axisConfig={config.xAxis}
            fieldOptions={fieldOptions}
            onFieldChange={(newField) => {
              patch({ xField: newField });
            }}
            onUpdate={(updated) => patchAxis('xAxis', updated)}
            onClose={() => setOpenSeriesPopover(null)}
          />
        )}
      </div>

      {/* Swap Axes Divider Button */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          margin: '4px 0',
          position: 'relative',
        }}
      >
        <button
          type="button"
          onClick={handleSwapAxes}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: '0.72rem',
            color: 'var(--color-primary)',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 12,
            padding: '2px 10px',
            cursor: 'pointer',
            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
          }}
        >
          <ArrowUpDown size={12} />
          Swap axes
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
          {(config.yFields ?? []).map((yf, idx) => {
            const seriesTitleVal = config.seriesTitles?.find((st) => st.field === yf)?.title;
            return (
              <FieldPill
                key={`${yf}-${idx}`}
                name={yf}
                type={getFieldType(yf)}
                transform={config.yAxis?.transform}
                displayName={
                  seriesTitleVal ??
                  (config.yAxis?.transform && config.yAxis.transform !== 'NONE'
                    ? `${config.yAxis.transform}(${yf})`
                    : yf)
                }
                onClick={() => setOpenSeriesPopover(openSeriesPopover === `yAxis_${yf}` ? null : `yAxis_${yf}`)}
                onRemove={() => {
                  const updated = (config.yFields ?? []).filter((_, i) => i !== idx);
                  patch({ yFields: updated });
                  if (openSeriesPopover === `yAxis_${yf}`) setOpenSeriesPopover(null);
                }}
              />
            );
          })}

          {(showYFieldSelect || (config.yFields ?? []).length === 0) && (
            <div style={{ marginTop: (config.yFields ?? []).length > 0 ? 4 : 0 }}>
              <Select
                value=""
                onChange={(v) => {
                  if (v) {
                    const current = config.yFields ? [...config.yFields] : [];
                    if (!current.includes(v)) {
                      patch({ yFields: [...current, v] });
                    }
                    setShowYFieldSelect(false);
                  }
                }}
                options={fieldOptions.filter((o) => !(config.yFields ?? []).includes(o.value))}
                placeholder="Add field..."
              />
            </div>
          )}

          {(config.yFields ?? []).length > 1 && (
            <div
              style={{
                marginTop: 8,
                padding: '6px 8px',
                background: '#f8fafc',
                borderRadius: 6,
                border: '1px solid #e2e8f0',
              }}
            >
              <label
                style={{
                  fontSize: '0.74rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  cursor: 'pointer',
                  color: '#1e293b',
                  fontWeight: 500,
                }}
              >
                <input
                  type="checkbox"
                  checked={config.enableSeriesSwitcher ?? false}
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
            axisConfig={config.yAxis}
            fieldOptions={fieldOptions}
            onUpdate={(updated) => patchAxis('yAxis', updated)}
            onClose={() => setOpenAxisSettings(null)}
          />
        )}

        {(config.yFields ?? []).map((yf, yIdx) => {
          const seriesTitleVal = config.seriesTitles?.find((st) => st.field === yf)?.title;
          return openSeriesPopover === `yAxis_${yf}` ? (
            <AxisConfigPopover
              key={yf}
              fieldName={yf}
              fieldType={getFieldType(yf)}
              axisConfig={config.yAxis}
              seriesTitle={seriesTitleVal}
              fieldOptions={fieldOptions}
              onFieldChange={(newField) => {
                const updated = [...(config.yFields ?? [])];
                updated[yIdx] = newField;
                patch({ yFields: updated });
                setOpenSeriesPopover(`yAxis_${newField}`);
              }}
              onUpdateSeriesTitle={(title) => {
                const current = config.seriesTitles ? [...config.seriesTitles] : [];
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
      {config.chartType === 'combo' && (
        <div style={{ position: 'relative', marginTop: 8 }}>
          <SectionRow
            title="Y2 axis (Line series)"
            onPlus={() => setShowY2FieldSelect(!showY2FieldSelect)}
            onKebab={() => setOpenAxisSettings(openAxisSettings === 'y2Axis' ? null : 'y2Axis')}
          >
            {(config.y2Fields ?? []).map((yf, idx) => (
              <FieldPill
                key={`${yf}-${idx}`}
                name={yf}
                type={getFieldType(yf)}
                transform={config.y2Axis?.transform}
                displayName={config.y2Axis?.displayName ?? config.y2Axis?.title}
                onClick={() => setOpenSeriesPopover(openSeriesPopover === `y2Axis_${yf}` ? null : `y2Axis_${yf}`)}
                onRemove={() => {
                  const updated = (config.y2Fields ?? []).filter((_, i) => i !== idx);
                  patch({ y2Fields: updated });
                  if (openSeriesPopover === `y2Axis_${yf}`) setOpenSeriesPopover(null);
                }}
              />
            ))}

            {(showY2FieldSelect || (config.y2Fields ?? []).length === 0) && (
              <div style={{ marginTop: (config.y2Fields ?? []).length > 0 ? 4 : 0 }}>
                <Select
                  value=""
                  onChange={(v) => {
                    if (v) {
                      patch({ y2Fields: [...(config.y2Fields ?? []), v] });
                    }
                    setShowY2FieldSelect(false);
                  }}
                  options={fieldOptions.filter((o) => !(config.y2Fields ?? []).includes(o.value))}
                  placeholder="Add line metric series..."
                />
              </div>
            )}
          </SectionRow>

          {openAxisSettings === 'y2Axis' && (
            <AxisSettingsPopover
              axisType="y2Axis"
              axisConfig={config.y2Axis}
              fieldOptions={fieldOptions}
              onUpdate={(updated) => patchAxis('y2Axis', updated)}
              onClose={() => setOpenAxisSettings(null)}
            />
          )}

          {(config.y2Fields ?? []).map((yf) =>
            openSeriesPopover === `y2Axis_${yf}` ? (
              <AxisConfigPopover
                key={yf}
                fieldName={yf}
                fieldType={getFieldType(yf)}
                axisConfig={config.y2Axis}
                onUpdate={(updated) => patchAxis('y2Axis', updated)}
                onClose={() => setOpenSeriesPopover(null)}
              />
            ) : null
          )}
        </div>
      )}

      {/* Color Section */}
      <div style={{ position: 'relative' }}>
        <SectionRow
          title="Color"
          onPlus={() => {}}
          onKebab={
            config.colorField
              ? () => setOpenSeriesPopover(openSeriesPopover === 'color' ? null : 'color')
              : undefined
          }
        >
          {config.colorField ? (
            <FieldPill
              name={config.colorField}
              type={getFieldType(config.colorField)}
              onClick={() => setOpenSeriesPopover(openSeriesPopover === 'color' ? null : 'color')}
              onRemove={() => {
                patch({ colorField: '' });
                if (openSeriesPopover === 'color') setOpenSeriesPopover(null);
              }}
            />
          ) : (
            <Select
              value={config.colorField ?? ''}
              onChange={(v) => patch({ colorField: v })}
              options={fieldOptions}
              placeholder="Add group field..."
            />
          )}
          <SeriesColorPicker
            yFields={[...(config.yFields ?? []), ...(config.y2Fields ?? [])]}
            seriesColors={config.seriesColors}
            onChange={(updated) => patch({ seriesColors: updated })}
          />
        </SectionRow>

        {openSeriesPopover === 'color' && config.colorField && (
          <AxisConfigPopover
            fieldName={config.colorField}
            fieldType={getFieldType(config.colorField)}
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

      {/* Tooltip Section */}
      <SectionRow title="Tooltip" onPlus={() => setShowTooltipSelect(!showTooltipSelect)}>
        {tooltipFields.map((field) => (
          <FieldPill
            key={field}
            name={field}
            type={getFieldType(field)}
            onRemove={() => patch({ tooltipFields: tooltipFields.filter((f) => f !== field) })}
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
              options={fieldOptions.filter((o) => !tooltipFields.includes(o.value))}
              placeholder="Add field..."
            />
          </div>
        )}
      </SectionRow>

      {/* Labels Section */}
      <div
        style={{
          padding: '12px 14px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1a1a1a' }}>Labels</span>
        <label style={{ position: 'relative', display: 'inline-block', width: 34, height: 20 }}>
          <input
            type="checkbox"
            checked={config.showValueLabels ?? false}
            onChange={(e) => patch({ showValueLabels: e.target.checked })}
            style={{ opacity: 0, width: 0, height: 0 }}
          />
          <span
            style={{
              position: 'absolute',
              cursor: 'pointer',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: config.showValueLabels ? '#0052cc' : '#e1e4e8',
              transition: '.2s',
              borderRadius: 20,
            }}
          >
            <span
              style={{
                position: 'absolute',
                content: '""',
                height: 14,
                width: 14,
                left: 3,
                bottom: 3,
                backgroundColor: 'white',
                transition: '.2s',
                borderRadius: '50%',
                transform: config.showValueLabels ? 'translateX(14px)' : 'none',
              }}
            />
          </span>
        </label>
      </div>

      {/* Collapsible Details Sections */}
      <div style={{ marginTop: 10 }}>
        <CollapsibleSection title="Style Details">
          <label style={{ fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={config.showGridlines !== false}
              onChange={(e) => patch({ showGridlines: e.target.checked })}
            />
            Show gridlines
          </label>
          <div style={{ marginTop: 8 }}>
            <FieldRow label="Legend Position">
              <Select
                value={config.legend?.position ?? 'bottom'}
                onChange={(v) => patch({ legend: { ...config.legend, position: v as any } })}
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

        <NumberFormatSection
          numberFormat={config.numberFormat}
          onChange={(updated) => patch({ numberFormat: updated })}
          collapsible={true}
          defaultOpen={false}
        />
      </div>
    </>
  );
}
